"""Emparejamiento de registros por múltiples modos y con tolerancias.

Capacidades: DOC-005/006/007 (cruce documento↔documento: factura↔auxiliar,
factura↔XML SRI, factura↔pago), DQ-006 (calidad: detectar el registro que
falta / el que sobra) y ANA-020 (join analítico difuso).

Cuatro modos, de más estricto a más laxo:

  - **EXACTO**: igualdad literal del valor (incluye mayúsculas/espacios).
  - **NORMALIZADO**: igualdad tras normalizar (trim, minúsculas, colapsar
    espacios, quitar tildes/puntuación). Es el modo por defecto: casi todas
    las conciliaciones reales lo necesitan (el ERP escribe "ANDES S.A." y el
    XML "Andes S A").
  - **FUZZY**: similitud de cadenas con ``rapidfuzz`` (dependencia NUEVA);
    umbral configurable. Para razones sociales con typos o abreviaturas.
  - **SEMANTICO**: similitud de embeddings (OPCIONAL, requiere proveedor de
    embeddings; hoy no hay librería en el runner — ver plan). Para conceptos
    que significan lo mismo con palabras distintas ("servicios de flete" ↔
    "transporte de carga").

Además del modo textual, cada campo puede llevar:
  - **tolerancia numérica** (DQ-006/ANA-020): dos importes casan si difieren
    en ≤ ``tolerancia_absoluta`` o ≤ ``tolerancia_relativa`` (p.ej. centavos de
    redondeo, o 0.5%). Todo en ``Decimal`` (principio no negociable).
  - **tolerancia de fecha**: casan si difieren en ≤ ``tolerancia_dias`` (la
    factura y su pago no caen el mismo día).

Regla de oro (CLAUDE.md): el emparejador NO decide por el auditor. Cuando hay
más de un candidato por encima del umbral, el estado es ``AMBIGUA`` y se
entregan TODOS los candidatos ordenados; nunca se elige uno en silencio.
"""

from __future__ import annotations

import datetime
import enum
from dataclasses import dataclass, field
from decimal import Decimal
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

    UNICA = "unica"                # exactamente un candidato sobre el umbral
    AMBIGUA = "ambigua"            # >1 candidato sobre el umbral (revisar)
    SIN_COINCIDENCIA = "sin_coincidencia"


@dataclass(frozen=True)
class CampoEmparejamiento:
    """Cómo comparar UN campo entre consulta y candidato."""

    nombre: str
    tipo: TipoCampo = TipoCampo.TEXTO
    modo: ModoEmparejamiento = ModoEmparejamiento.NORMALIZADO
    peso: float = 1.0
    # Texto/fuzzy/semántico: mínimo de similitud 0..1 para que el campo aporte.
    umbral_fuzzy: float = 0.85
    # Numérico:
    tolerancia_absoluta: Decimal = Decimal("0.00")
    tolerancia_relativa: float = 0.0  # fracción, 0.005 = 0.5%
    # Fecha:
    tolerancia_dias: int = 0
    # Si el campo es obligatorio, un 0 en él descarta al candidato entero.
    obligatorio: bool = False


@dataclass(frozen=True)
class CriterioEmparejamiento:
    """Conjunto de campos + umbral global para declarar match."""

    campos: tuple[CampoEmparejamiento, ...]
    # Score combinado (promedio ponderado 0..1) mínimo para considerar match.
    umbral: float = 0.80

    def pesos_normalizados(self) -> dict[str, float]:
        """Pesos de cada campo re-escalados para sumar 1."""
        raise NotImplementedError("P1-E: implementar en el servidor")


@dataclass
class Coincidencia:
    """Un candidato evaluado contra la consulta."""

    candidato: Registro
    score: float                      # combinado 0..1
    por_campo: dict[str, float]       # similitud 0..1 de cada campo
    es_match: bool                    # score >= criterio.umbral
    indice_candidato: int = -1        # posición en la lista original


@dataclass
class ResultadoEmparejamiento:
    """Resultado de emparejar UNA consulta contra sus candidatos."""

    consulta: Registro
    coincidencias: list[Coincidencia]  # ordenadas por score desc
    estado: EstadoEmparejamiento
    modo: ModoEmparejamiento

    @property
    def mejor(self) -> Coincidencia | None:
        """La mejor coincidencia, o None si no hubo match."""
        raise NotImplementedError("P1-E: implementar en el servidor")

    @property
    def es_unica(self) -> bool:
        return self.estado is EstadoEmparejamiento.UNICA


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------


def emparejar(
    consulta: Registro,
    candidatos: Sequence[Registro],
    modo: ModoEmparejamiento = ModoEmparejamiento.NORMALIZADO,
    *,
    criterio: CriterioEmparejamiento | None = None,
    embeddings: "ProveedorEmbeddings | None" = None,
) -> ResultadoEmparejamiento:
    """Empareja ``consulta`` contra ``candidatos`` según ``modo``/``criterio``.

    - Si se pasa ``criterio`` gana su configuración por campo (``modo`` se ignora
      salvo como valor por defecto de los campos que no lo fijen).
    - Sin ``criterio``, se compara con ``modo`` sobre los campos comunes a
      consulta y candidato, todos con peso 1.
    - ``modo=SEMANTICO`` exige ``embeddings``; sin proveedor se levanta
      ``ValueError`` (nunca cae en silencio a otro modo).

    Ejemplos de uso previstos (ver plan):
      - factura↔auxiliar: campos ``numero`` (normalizado), ``ruc`` (exacto),
        ``total`` (numérico, tol. 0.01), ``fecha`` (tol. 0 días).
      - factura↔XML SRI: ``clave_acceso`` (exacto) o, si falta, ``ruc`` +
        ``total`` + ``fecha``.
      - factura↔pago: ``beneficiario`` (fuzzy), ``importe`` (numérico), ``fecha``
        (tol. 5 días).

    Estado del resultado:
      - 1 candidato sobre el umbral → ``UNICA``.
      - >1 → ``AMBIGUA`` (se devuelven todos; decide el auditor).
      - 0 → ``SIN_COINCIDENCIA``.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def emparejar_lotes(
    consultas: Sequence[Registro],
    candidatos: Sequence[Registro],
    criterio: CriterioEmparejamiento,
    *,
    uno_a_uno: bool = True,
    embeddings: "ProveedorEmbeddings | None" = None,
) -> list[ResultadoEmparejamiento]:
    """Empareja muchas consultas (conciliación completa).

    Con ``uno_a_uno=True`` un candidato no se reutiliza: tras asignar el mejor
    par se retira del pool (asignación golosa por score desc). Con ``False``
    cada consulta ve todos los candidatos (útil para detectar duplicados).
    Las consultas sin par y los candidatos sobrantes se reportan como no
    conciliados (DQ-006).
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


# ---------------------------------------------------------------------------
# Comparadores por tipo — helpers reutilizables
# ---------------------------------------------------------------------------


def normalizar_texto(valor: Any) -> str:
    """trim + minúsculas + colapsar espacios + quitar tildes/puntuación.

    Base del modo NORMALIZADO y paso previo de FUZZY. Determinista y sin
    dependencias externas.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def similitud_texto(
    a: Any,
    b: Any,
    modo: ModoEmparejamiento,
    *,
    embeddings: "ProveedorEmbeddings | None" = None,
) -> float:
    """Similitud 0..1 entre dos textos según el modo.

    - EXACTO: 1.0 si iguales literalmente, si no 0.0.
    - NORMALIZADO: 1.0 si ``normalizar_texto`` coincide, si no 0.0.
    - FUZZY: ``rapidfuzz.fuzz.token_sort_ratio`` / 100 (dependencia nueva).
    - SEMANTICO: coseno de embeddings (requiere ``embeddings``).
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def similitud_fuzzy(a: str, b: str) -> float:
    """Wrapper aislado de rapidfuzz (0..1). Único punto que importa la lib.

    Aislarlo permite (a) testear el resto sin la dependencia y (b) cambiar de
    algoritmo (``token_sort_ratio`` vs ``WRatio``) en un solo lugar.
    """
    raise NotImplementedError("P1-E: implementar en el servidor (requiere rapidfuzz)")


def dentro_de_tolerancia_numerica(
    a: Any,
    b: Any,
    *,
    tolerancia_absoluta: Decimal = Decimal("0.00"),
    tolerancia_relativa: float = 0.0,
) -> tuple[bool, float]:
    """¿Casan dos importes? Devuelve (casa, similitud 0..1).

    Casa si ``|a-b| <= tolerancia_absoluta`` o ``|a-b| <= tolerancia_relativa *
    max(|a|,|b|)``. La similitud degrada linealmente con la diferencia
    relativa (1.0 en diferencia 0). Todo en ``Decimal``.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def dentro_de_tolerancia_fecha(
    a: datetime.date | None,
    b: datetime.date | None,
    *,
    tolerancia_dias: int = 0,
) -> tuple[bool, float]:
    """¿Casan dos fechas dentro de ``tolerancia_dias``? (casa, similitud 0..1).

    Similitud = 1 - (dias_diferencia / (tolerancia_dias+1)), acotada a [0,1].
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def similitud_campo(
    valor_consulta: Any,
    valor_candidato: Any,
    campo: CampoEmparejamiento,
    *,
    embeddings: "ProveedorEmbeddings | None" = None,
) -> float:
    """Similitud 0..1 de un campo, despachando por ``campo.tipo``.

    TEXTO → ``similitud_texto`` (aplica ``umbral_fuzzy`` como piso);
    NUMERO → ``dentro_de_tolerancia_numerica``;
    FECHA → ``dentro_de_tolerancia_fecha``.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


class ProveedorEmbeddings(Protocol):
    """Puerto opcional para el modo SEMANTICO.

    Implementación prevista en el servidor: Voyage AI (Anthropic recomienda
    Voyage para embeddings; el SDK ``anthropic`` no expone embeddings). Se
    inyecta para no acoplar el motor a un proveedor ni exigir red en tests.
    """

    def vectorizar(self, textos: Sequence[str]) -> list[list[float]]:
        """Devuelve un vector por texto (mismo orden)."""
        ...
