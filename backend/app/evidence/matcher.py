"""Emparejamiento de registros por múltiples modos y con tolerancias.

Capacidades: DOC-005/006/007 (cruce documento↔documento: factura↔auxiliar,
factura↔XML SRI, factura↔pago), DQ-006 (calidad: detectar el registro que
falta / el que sobra) y ANA-020 (join analítico difuso).

Cuatro modos, de más estricto a más laxo: EXACTO, NORMALIZADO (defecto), FUZZY
(rapidfuzz) y SEMANTICO (embeddings opcional). Cada campo puede además llevar
tolerancia numérica (Decimal) o de fecha.

Regla de oro (CLAUDE.md): el emparejador NO decide por el auditor. Cuando hay
más de un candidato por encima del umbral, el estado es ``AMBIGUA`` y se
entregan TODOS los candidatos ordenados; nunca se elige uno en silencio.
"""

from __future__ import annotations

import datetime
import enum
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, Sequence

# Un registro es un dict campo→valor (factura, línea de auxiliar, pago, etc.).
Registro = dict[str, Any]


class ModoEmparejamiento(enum.Enum):
    EXACTO = "exacto"
    NORMALIZADO = "normalizado"
    FUZZY = "fuzzy"
    SEMANTICO = "semantico"


class TipoCampo(enum.Enum):
    TEXTO = "texto"
    NUMERO = "numero"
    FECHA = "fecha"


class EstadoEmparejamiento(enum.Enum):
    """Resultado a nivel de una consulta contra sus candidatos."""

    UNICA = "unica"
    AMBIGUA = "ambigua"
    SIN_COINCIDENCIA = "sin_coincidencia"


@dataclass(frozen=True)
class CampoEmparejamiento:
    """Cómo comparar UN campo entre consulta y candidato."""

    nombre: str
    tipo: TipoCampo = TipoCampo.TEXTO
    modo: ModoEmparejamiento = ModoEmparejamiento.NORMALIZADO
    peso: float = 1.0
    umbral_fuzzy: float = 0.85
    tolerancia_absoluta: Decimal = Decimal("0.00")
    tolerancia_relativa: float = 0.0
    tolerancia_dias: int = 0
    obligatorio: bool = False


@dataclass(frozen=True)
class CriterioEmparejamiento:
    """Conjunto de campos + umbral global para declarar match."""

    campos: tuple[CampoEmparejamiento, ...]
    umbral: float = 0.80

    def pesos_normalizados(self) -> dict[str, float]:
        """Pesos de cada campo re-escalados para sumar 1."""
        total = sum(c.peso for c in self.campos)
        if total <= 0:
            n = len(self.campos) or 1
            return {c.nombre: 1.0 / n for c in self.campos}
        return {c.nombre: c.peso / total for c in self.campos}


@dataclass
class Coincidencia:
    """Un candidato evaluado contra la consulta."""

    candidato: Registro
    score: float
    por_campo: dict[str, float]
    es_match: bool
    indice_candidato: int = -1


@dataclass
class ResultadoEmparejamiento:
    """Resultado de emparejar UNA consulta contra sus candidatos."""

    consulta: Registro
    coincidencias: list[Coincidencia]
    estado: EstadoEmparejamiento
    modo: ModoEmparejamiento

    @property
    def mejor(self) -> Coincidencia | None:
        """La mejor coincidencia (mayor score entre los match), o None."""
        for c in self.coincidencias:  # ya vienen ordenadas por score desc
            if c.es_match:
                return c
        return None

    @property
    def es_unica(self) -> bool:
        return self.estado is EstadoEmparejamiento.UNICA


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------


def _criterio_por_defecto(
    consulta: Registro, candidatos: Sequence[Registro], modo: ModoEmparejamiento
) -> CriterioEmparejamiento:
    comunes = set(consulta)
    for c in candidatos:
        comunes &= set(c)
    campos = tuple(
        CampoEmparejamiento(nombre=n, tipo=TipoCampo.TEXTO, modo=modo)
        for n in sorted(comunes)
    )
    return CriterioEmparejamiento(campos=campos)


def _evaluar(
    consulta: Registro,
    candidato: Registro,
    criterio: CriterioEmparejamiento,
    *,
    embeddings: "ProveedorEmbeddings | None",
) -> tuple[float, dict[str, float], bool]:
    pesos = criterio.pesos_normalizados()
    por_campo: dict[str, float] = {}
    score = 0.0
    descartado = False
    for campo in criterio.campos:
        sim = similitud_campo(
            consulta.get(campo.nombre), candidato.get(campo.nombre), campo,
            embeddings=embeddings,
        )
        por_campo[campo.nombre] = sim
        score += sim * pesos.get(campo.nombre, 0.0)
        if campo.obligatorio and sim <= 0.0:
            descartado = True
    es_match = (not descartado) and score >= criterio.umbral
    return score, por_campo, es_match


def emparejar(
    consulta: Registro,
    candidatos: Sequence[Registro],
    modo: ModoEmparejamiento = ModoEmparejamiento.NORMALIZADO,
    *,
    criterio: CriterioEmparejamiento | None = None,
    embeddings: "ProveedorEmbeddings | None" = None,
) -> ResultadoEmparejamiento:
    """Empareja ``consulta`` contra ``candidatos`` según ``modo``/``criterio``."""
    if modo is ModoEmparejamiento.SEMANTICO and embeddings is None and criterio is None:
        raise ValueError("modo SEMANTICO requiere un proveedor de embeddings")
    crit = criterio or _criterio_por_defecto(consulta, candidatos, modo)

    coincidencias: list[Coincidencia] = []
    for i, cand in enumerate(candidatos):
        score, por_campo, es_match = _evaluar(consulta, cand, crit, embeddings=embeddings)
        coincidencias.append(
            Coincidencia(candidato=cand, score=score, por_campo=por_campo,
                         es_match=es_match, indice_candidato=i)
        )
    coincidencias.sort(key=lambda c: c.score, reverse=True)

    n_match = sum(1 for c in coincidencias if c.es_match)
    if n_match == 1:
        estado = EstadoEmparejamiento.UNICA
    elif n_match >= 2:
        estado = EstadoEmparejamiento.AMBIGUA
    else:
        estado = EstadoEmparejamiento.SIN_COINCIDENCIA
    return ResultadoEmparejamiento(
        consulta=consulta, coincidencias=coincidencias, estado=estado, modo=modo
    )


def emparejar_lotes(
    consultas: Sequence[Registro],
    candidatos: Sequence[Registro],
    criterio: CriterioEmparejamiento,
    *,
    uno_a_uno: bool = True,
    embeddings: "ProveedorEmbeddings | None" = None,
) -> list[ResultadoEmparejamiento]:
    """Empareja muchas consultas (conciliación completa)."""
    if not uno_a_uno:
        return [
            emparejar(q, candidatos, criterio=criterio, embeddings=embeddings)
            for q in consultas
        ]

    # Asignación golosa 1:1 por score descendente sobre todos los pares match.
    pares: list[tuple[float, int, int, dict[str, float]]] = []
    for i, q in enumerate(consultas):
        for j, cand in enumerate(candidatos):
            score, por_campo, es_match = _evaluar(q, cand, criterio, embeddings=embeddings)
            if es_match:
                pares.append((score, i, j, por_campo))
    pares.sort(key=lambda t: t[0], reverse=True)

    asignado_q: dict[int, tuple[int, float, dict[str, float]]] = {}
    candidato_tomado: set[int] = set()
    for score, i, j, por_campo in pares:
        if i in asignado_q or j in candidato_tomado:
            continue
        asignado_q[i] = (j, score, por_campo)
        candidato_tomado.add(j)

    resultados: list[ResultadoEmparejamiento] = []
    for i, q in enumerate(consultas):
        if i in asignado_q:
            j, score, por_campo = asignado_q[i]
            coin = Coincidencia(candidato=candidatos[j], score=score, por_campo=por_campo,
                                es_match=True, indice_candidato=j)
            resultados.append(ResultadoEmparejamiento(
                consulta=q, coincidencias=[coin], estado=EstadoEmparejamiento.UNICA,
                modo=ModoEmparejamiento.NORMALIZADO))
        else:
            resultados.append(ResultadoEmparejamiento(
                consulta=q, coincidencias=[], estado=EstadoEmparejamiento.SIN_COINCIDENCIA,
                modo=ModoEmparejamiento.NORMALIZADO))
    return resultados


# ---------------------------------------------------------------------------
# Comparadores por tipo — helpers reutilizables
# ---------------------------------------------------------------------------


def normalizar_texto(valor: Any) -> str:
    """trim + minúsculas + colapsar espacios + quitar tildes/puntuación."""
    if valor is None:
        return ""
    s = unicodedata.normalize("NFKD", str(valor))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c for c in s if c.isalnum() or c.isspace())
    return " ".join(s.lower().split())


def similitud_fuzzy(a: str, b: str) -> float:
    """Wrapper aislado de rapidfuzz (0..1). Único punto que importa la lib."""
    from rapidfuzz import fuzz, utils

    return fuzz.token_sort_ratio(str(a), str(b), processor=utils.default_process) / 100.0


def similitud_texto(
    a: Any,
    b: Any,
    modo: ModoEmparejamiento,
    *,
    embeddings: "ProveedorEmbeddings | None" = None,
) -> float:
    """Similitud 0..1 entre dos textos según el modo."""
    if modo is ModoEmparejamiento.EXACTO:
        return 1.0 if str(a) == str(b) else 0.0
    if modo is ModoEmparejamiento.NORMALIZADO:
        return 1.0 if normalizar_texto(a) == normalizar_texto(b) else 0.0
    if modo is ModoEmparejamiento.FUZZY:
        return similitud_fuzzy(str(a or ""), str(b or ""))
    if modo is ModoEmparejamiento.SEMANTICO:
        if embeddings is None:
            raise ValueError("modo SEMANTICO requiere un proveedor de embeddings")
        va, vb = embeddings.vectorizar([str(a or ""), str(b or "")])
        return _coseno(va, vb)
    raise ValueError(f"modo desconocido: {modo}")


def _coseno(a: Sequence[float], b: Sequence[float]) -> float:
    import math

    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, num / (na * nb)))


def _a_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def dentro_de_tolerancia_numerica(
    a: Any,
    b: Any,
    *,
    tolerancia_absoluta: Decimal = Decimal("0.00"),
    tolerancia_relativa: float = 0.0,
) -> tuple[bool, float]:
    """¿Casan dos importes? Devuelve (casa, similitud 0..1)."""
    da, db = _a_decimal(a), _a_decimal(b)
    diff = abs(da - db)
    mx = max(abs(da), abs(db))
    casa = diff <= tolerancia_absoluta
    if not casa and tolerancia_relativa > 0 and mx > 0:
        casa = diff <= (Decimal(str(tolerancia_relativa)) * mx)
    sim = 1.0 if mx == 0 else max(0.0, 1.0 - float(diff / mx))
    return casa, sim


def dentro_de_tolerancia_fecha(
    a: datetime.date | None,
    b: datetime.date | None,
    *,
    tolerancia_dias: int = 0,
) -> tuple[bool, float]:
    """¿Casan dos fechas dentro de ``tolerancia_dias``? (casa, similitud 0..1)."""
    if a is None or b is None:
        return False, 0.0
    dd = abs((a - b).days)
    casa = dd <= tolerancia_dias
    sim = max(0.0, 1.0 - dd / (tolerancia_dias + 1))
    return casa, sim


def similitud_campo(
    valor_consulta: Any,
    valor_candidato: Any,
    campo: CampoEmparejamiento,
    *,
    embeddings: "ProveedorEmbeddings | None" = None,
) -> float:
    """Similitud 0..1 de un campo, despachando por ``campo.tipo``."""
    if campo.tipo is TipoCampo.NUMERO:
        casa, sim = dentro_de_tolerancia_numerica(
            valor_consulta, valor_candidato,
            tolerancia_absoluta=campo.tolerancia_absoluta,
            tolerancia_relativa=campo.tolerancia_relativa,
        )
        return sim if casa else 0.0
    if campo.tipo is TipoCampo.FECHA:
        casa, sim = dentro_de_tolerancia_fecha(
            valor_consulta, valor_candidato, tolerancia_dias=campo.tolerancia_dias
        )
        return sim if casa else 0.0
    # TEXTO
    sim = similitud_texto(valor_consulta, valor_candidato, campo.modo, embeddings=embeddings)
    if campo.modo in (ModoEmparejamiento.FUZZY, ModoEmparejamiento.SEMANTICO) and sim < campo.umbral_fuzzy:
        return 0.0
    return sim


class ProveedorEmbeddings(Protocol):
    """Puerto opcional para el modo SEMANTICO."""

    def vectorizar(self, textos: Sequence[str]) -> list[list[float]]:
        ...
