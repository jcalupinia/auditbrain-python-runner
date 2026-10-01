"""Normalización de datos (Fase 3): tipado, moneda, fechas y duplicados.

Toma los datos crudos de un :class:`DatasetNormalizado` / :class:`CampoExtraido`
y los normaliza de forma **determinista** (sin IA):

- **Moneda**: reutiliza el parser regional canónico del repo
  (`obligaciones_fiscales/cedulas/base._parse_amount_sri`), que ya resuelve
  formato US (`178,259.63`) y europeo (`178.259,63`). NO se crea una tercera
  copia de esa heurística (regla anti-duplicación del CLAUDE.md); aquí solo se
  envuelve su resultado en `Decimal` para el contrato.
- **Fechas**: formatos ISO, dd/mm/aaaa (preferencia Ecuador), aaaa/mm/dd,
  "31 de enero de 2025" y periodo "aaaa-mm".
- **Tipado**: infiere `TipoDato` del valor crudo (RUC, fecha, moneda/decimal,
  entero, booleano, texto).
- **Duplicados**: detección determinista por clave (equivale a la primitiva
  `duplicados` del motor analítico; aquí local y en proceso para la capa de
  ingesta, sin red).

Semántica consistente con el motor analítico (Decimal, nunca forzar un valor):
si un dato no se puede normalizar, se deja `None` y se marca para revisión.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from backend.app.aud.obligaciones_fiscales.cedulas.base import _parse_amount_sri
from backend.app.ingesta.contract import (
    CampoExtraido,
    DatasetNormalizado,
    ResultadoValidacion,
    TipoDato,
)

_MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_RE_RUC = re.compile(r"^\d{13}$")
_RE_SOLO_ENTERO = re.compile(r"^-?\d{1,}$")
_RE_NUMERO = re.compile(r"^-?[\d.,]+$")
_RE_FECHA_LARGA = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.IGNORECASE)
_VERDAD = {"true", "si", "sí", "verdadero", "x"}
_FALSO = {"false", "no", "falso"}


def normalizar_monto(raw: Any) -> Optional[Decimal]:
    """Monto SRI (US o europeo) → Decimal. ``None`` si no se puede."""
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, (int, float)):
        try:
            return Decimal(str(raw))
        except (InvalidOperation, ValueError):
            return None
    val = _parse_amount_sri(str(raw))
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def normalizar_fecha(raw: Any) -> Optional[date]:
    """Texto de fecha → ``date``. ``None`` si no se reconoce.

    Preferencia dd/mm/aaaa (Ecuador) cuando el formato con `/` o `-` es
    ambiguo; si el primer grupo > 12 es inequívocamente día.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None

    # "31 de enero de 2025"
    m = _RE_FECHA_LARGA.search(s)
    if m:
        dia, mes_txt, anio = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        mes = _MESES_ES.get(mes_txt)
        if mes:
            return _fecha_segura(anio, mes, dia)

    # ISO estricto aaaa-mm-dd
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        return _fecha_segura(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # aaaa/mm/dd
    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", s)
    if m:
        return _fecha_segura(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # dd/mm/aaaa o dd-mm-aaaa (preferencia día primero)
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        a, b, anio = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 >= b or a > 12:          # a es día
            return _fecha_segura(anio, b, a)
        if b > 12:                          # b es día (formato mm/dd)
            return _fecha_segura(anio, a, b)
        return _fecha_segura(anio, b, a)    # ambiguo → dd/mm (Ecuador)

    return None


def _fecha_segura(anio: int, mes: int, dia: int) -> Optional[date]:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def inferir_tipo(raw: Any) -> TipoDato:
    """Infiere el :class:`TipoDato` del valor crudo (determinista)."""
    if raw is None:
        return TipoDato.DESCONOCIDO
    if isinstance(raw, bool):
        return TipoDato.BOOLEANO
    if isinstance(raw, int):
        return TipoDato.ENTERO
    if isinstance(raw, (float, Decimal)):
        return TipoDato.DECIMAL
    if isinstance(raw, (date, datetime)):
        return TipoDato.FECHA
    s = str(raw).strip()
    if not s:
        return TipoDato.DESCONOCIDO
    bajo = s.lower()
    if bajo in _VERDAD or bajo in _FALSO:
        return TipoDato.BOOLEANO
    if _RE_RUC.match(s):
        return TipoDato.RUC
    if normalizar_fecha(s) is not None:
        return TipoDato.FECHA
    if s.endswith("%") and _RE_NUMERO.match(s[:-1].strip() or "x") is not None:
        return TipoDato.PORCENTAJE
    if _RE_SOLO_ENTERO.match(s):
        return TipoDato.ENTERO
    if _RE_NUMERO.match(s) and normalizar_monto(s) is not None:
        return TipoDato.DECIMAL
    return TipoDato.TEXTO


def normalizar_valor(raw: Any, tipo: Optional[TipoDato] = None) -> tuple[Any, TipoDato]:
    """Normaliza un valor crudo. Devuelve ``(valor_normalizado, tipo)``.

    Si ``tipo`` no se da, se infiere. Un valor que no se puede normalizar al
    tipo esperado vuelve como ``None`` (no se fuerza).
    """
    t = tipo or inferir_tipo(raw)
    if t in (TipoDato.MONEDA, TipoDato.DECIMAL):
        return normalizar_monto(raw), t
    if t is TipoDato.ENTERO:
        v = normalizar_monto(raw)
        return (int(v) if v is not None and v == v.to_integral_value() else v), t
    if t is TipoDato.FECHA:
        return normalizar_fecha(raw), t
    if t is TipoDato.BOOLEANO:
        s = str(raw).strip().lower()
        if s in _VERDAD:
            return True, t
        if s in _FALSO:
            return False, t
        return None, t
    if t is TipoDato.PORCENTAJE:
        return normalizar_monto(str(raw).rstrip("% ").strip()), t
    if t in (TipoDato.RUC, TipoDato.TEXTO):
        return (str(raw).strip() if raw is not None else None), t
    return raw, t


def normalizar_campo(campo: CampoExtraido) -> CampoExtraido:
    """Completa ``data_type`` y ``normalized_value`` de un campo si faltan.

    Reutiliza el ``raw_value`` como fuente. No baja ni sube la confianza; si no
    se pudo normalizar un valor crudo presente, agrega una advertencia.
    """
    if campo.normalized_value is not None:
        if campo.data_type is TipoDato.DESCONOCIDO:
            campo.data_type = inferir_tipo(campo.normalized_value)
        return campo
    if campo.raw_value is None:
        return campo
    tipo = campo.data_type if campo.data_type is not TipoDato.DESCONOCIDO else None
    valor, t = normalizar_valor(campo.raw_value, tipo)
    campo.data_type = t
    campo.normalized_value = valor
    if valor is None:
        campo.warnings.append(f"no se pudo normalizar {campo.raw_value!r} como {t.value}")
    return campo


def detectar_duplicados(
    filas: list[dict], claves: Iterable[str]
) -> list[list[int]]:
    """Grupos de índices de filas duplicadas según las ``claves`` (determinista).

    Equivale a la primitiva ``duplicados`` del motor analítico. Las filas se
    comparan por la tupla de valores de las claves (normalizados a texto).
    """
    claves = list(claves)
    grupos: dict[tuple, list[int]] = {}
    for i, fila in enumerate(filas or []):
        clave = tuple(str(fila.get(k, "")).strip().lower() for k in claves)
        grupos.setdefault(clave, []).append(i)
    return [idx for idx in grupos.values() if len(idx) > 1]


def normalizar_dataset(
    ds: DatasetNormalizado,
    *,
    claves_duplicado: Optional[Iterable[str]] = None,
) -> DatasetNormalizado:
    """Normaliza los campos del dataset y, si se piden claves, detecta
    duplicados en sus filas. Agrega los resultados a ``validation_results``.
    """
    for campo in ds.campos:
        normalizar_campo(campo)

    if claves_duplicado is not None:
        grupos = detectar_duplicados(ds.rows, claves_duplicado)
        total = sum(len(g) for g in grupos)
        ds.validation_results.append(
            ResultadoValidacion(
                regla="duplicados",
                ok=not grupos,
                detalle=(
                    None if not grupos
                    else f"{len(grupos)} grupo(s), {total} filas duplicadas por "
                         f"{list(claves_duplicado)}"
                ),
            )
        )
        if grupos:
            ds.warnings.append(
                f"duplicados detectados: {len(grupos)} grupo(s) en {total} filas"
            )

    # Un campo que quedó marcado para revisión contagia al dataset.
    if any(c.review_required for c in ds.campos):
        ds.review_required = True
    return ds
