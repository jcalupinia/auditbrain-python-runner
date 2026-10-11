"""Propuesta determinista de mapeo columna → campo canónico (Fase A3).

Puntúa cada columna contra cada campo del esquema con una heurística SIN IA:
coincidencia del nombre (peso alto) + compatibilidad de tipo inferido (peso
medio). Asigna sin colisiones (un campo, una columna) y clasifica la confianza.
La máquina PROPONE; el auditor confirma (M07). Nada se mapea en silencio: lo
dudoso (LOW/REVIEW) y los obligatorios sin columna van a la cola de revisión.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.ingesta.confidence import NivelConfianza, clasificar_confianza, requiere_revision
from backend.app.ingesta.contract import TipoDato
from backend.app.ingesta.mapeo.esquemas import CampoCanonico, EsquemaCanonico
from backend.app.ingesta.mapeo.perfilador import PerfilColumna, PerfilTabla, norm_texto

# Pesos de la combinación (suman 1.0). El nombre manda; el tipo desempata.
_PESO_NOMBRE = 0.75
_PESO_TIPO = 0.25
# Piso de score por debajo del cual NO se propone el mapeo (columna basura).
_PISO = 0.25

_NUMERICOS = frozenset({TipoDato.MONEDA, TipoDato.DECIMAL, TipoDato.ENTERO, TipoDato.PORCENTAJE})


@dataclass(frozen=True)
class PropuestaMapeo:
    columna_indice: int
    columna_nombre_crudo: str
    campo_canonico: str
    score: float
    confianza: NivelConfianza
    motivo: str


@dataclass
class MapeoPropuesto:
    tipo_documento: str
    propuestas: list[PropuestaMapeo]
    campos_sin_cubrir: list[str]
    review_required: bool


def _match_nombre(col_norm: str, campo: CampoCanonico) -> tuple[float, str]:
    """Puntúa la coincidencia del nombre de columna con el campo.

    - Igualdad exacta con el nombre canónico o un sinónimo de UNA palabra: 1.0
      (pista fuerte → HIGH).
    - Igualdad exacta con una frase sinónima (varias palabras): 0.5 (pista
      débil → a revisión; p. ej. "movimiento deudor").
    - Contención parcial (token dentro del otro): 0.4.
    - Nada: 0.0.
    """
    candidatos = [campo.nombre, *campo.sinonimos]
    # 1) Igualdad exacta.
    for cand in candidatos:
        cn = norm_texto(cand)
        if col_norm == cn and cn:
            if " " in cn:
                return 0.5, f"coincide con la frase «{cand}»"
            return 1.0, f"coincide con «{cand}»"
    # 2) Contención parcial.
    for cand in candidatos:
        cn = norm_texto(cand)
        if cn and (cn in col_norm or col_norm in cn):
            return 0.4, f"contiene «{cand}»"
    return 0.0, "sin coincidencia de nombre"


def _match_tipo(col_tipo: TipoDato, campo_tipo: TipoDato) -> float:
    if col_tipo == campo_tipo:
        return 1.0
    if campo_tipo in _NUMERICOS and col_tipo in _NUMERICOS:
        return 0.8
    if col_tipo is TipoDato.DESCONOCIDO:
        return 0.5
    if campo_tipo is TipoDato.TEXTO:
        return 0.6  # texto tolera casi cualquier contenido
    if campo_tipo is TipoDato.RUC and col_tipo in (TipoDato.ENTERO, TipoDato.TEXTO):
        return 0.6
    return 0.2


def _puntuar(col: PerfilColumna, campo: CampoCanonico) -> tuple[float, str]:
    s_nombre, motivo = _match_nombre(norm_texto(col.nombre_crudo), campo)
    if s_nombre == 0.0:
        return 0.0, motivo
    s_tipo = _match_tipo(col.tipo_inferido, campo.tipo)
    score = round(_PESO_NOMBRE * s_nombre + _PESO_TIPO * s_tipo, 4)
    return score, f"{motivo}; tipo {col.tipo_inferido.value}~{campo.tipo.value}"


def proponer_mapeo(perfil: PerfilTabla, esquema: EsquemaCanonico) -> MapeoPropuesto:
    """Asigna columnas a campos sin colisiones, de mayor a menor score."""
    # Todas las parejas candidatas con score por encima del piso.
    candidatas: list[tuple[float, int, int, str]] = []  # (score, orden_campo, col_idx, motivo)
    for orden, campo in enumerate(esquema.campos):
        for col in perfil.columnas:
            score, motivo = _puntuar(col, campo)
            if score >= _PISO:
                candidatas.append((score, orden, col.indice, motivo))
    # Orden determinista: score desc, luego orden del campo, luego índice de col.
    candidatas.sort(key=lambda t: (-t[0], t[1], t[2]))

    por_indice = {c.indice: c for c in perfil.columnas}
    campos_por_orden = list(esquema.campos)
    col_usada: set[int] = set()
    campo_usado: set[str] = set()
    propuestas: list[PropuestaMapeo] = []
    for score, orden, col_idx, motivo in candidatas:
        campo = campos_por_orden[orden]
        if campo.nombre in campo_usado or col_idx in col_usada:
            continue
        col = por_indice[col_idx]
        confianza = clasificar_confianza(score)
        propuestas.append(PropuestaMapeo(
            columna_indice=col_idx, columna_nombre_crudo=col.nombre_crudo,
            campo_canonico=campo.nombre, score=score, confianza=confianza, motivo=motivo,
        ))
        campo_usado.add(campo.nombre)
        col_usada.add(col_idx)

    # Orden de salida estable: por el orden de los campos del esquema.
    propuestas.sort(key=lambda p: [c.nombre for c in esquema.campos].index(p.campo_canonico))

    cubiertos = {p.campo_canonico for p in propuestas}
    campos_sin_cubrir = [c.nombre for c in esquema.obligatorios if c.nombre not in cubiertos]
    review_required = bool(campos_sin_cubrir) or any(
        requiere_revision(p.confianza) for p in propuestas
    )
    return MapeoPropuesto(
        tipo_documento=esquema.tipo_documento.value,
        propuestas=propuestas,
        campos_sin_cubrir=campos_sin_cubrir,
        review_required=review_required,
    )
