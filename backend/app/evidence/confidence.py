"""Confianza por dato, calibrada 0..1 y separada en dos ejes.

Capacidad: DOC-011 (score numérico de confianza por campo, distinguiendo la
confianza de EXTRACCIÓN de la de INTERPRETACIÓN).

Por qué DOS ejes y no uno:

  - **Confianza de extracción**: ¿leímos bien el dato de la fuente? Depende de
    cómo se obtuvo (celda de Excel = casi 1.0; texto digital de pdfplumber =
    alto; OCR de un escaneo malo = variable, con la ``confidence`` que reporta
    Vision por palabra), de si se pudo ubicar en su página (bounding-box
    presente o no) y de si el valor parseó limpio (formato numérico regional
    reconocido, ver CLAUDE.md "Formatos numéricos en parsers SRI").

  - **Confianza de interpretación**: ¿el dato significa lo que creemos y casó
    con su contraparte? Depende del score del emparejamiento (``matcher``), de
    si el match fue único o ambiguo, y de la calidad del mapeo (casillero
    conocido vs heurístico).

Un importe puede estar PERFECTAMENTE extraído (1.0) pero mal interpretado
(casó con dos facturas → interpretación baja), y al revés. Colapsarlos a un
solo número ocultaría cuál de los dos problemas tiene el auditor enfrente.

Patrón de evidencia: se reutiliza el estilo de ``mayor/clasificador.py`` —
cada confianza es la suma de ``AporteConfianza`` con su motivo, de modo que el
papel de trabajo pueda mostrar POR QUÉ un dato tiene la confianza que tiene
(no solo el número). Esto también alimenta el control 5 del CLAUDE.md
("Confianza autoreportada" — bajo = borde rojo + "Revisar manualmente").
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # evita import circular en runtime
    from backend.app.evidence.citation import SourceReference
    from backend.app.evidence.matcher import ResultadoEmparejamiento


class NivelConfianza(enum.Enum):
    """Corte cualitativo del score, alineado con el CLAUDE.md (control 5)."""

    ALTA = "alta"     # >= UMBRAL_ALTA
    MEDIA = "media"   # >= UMBRAL_MEDIA
    BAJA = "baja"     # < UMBRAL_MEDIA → marcar "Revisar manualmente"


UMBRAL_ALTA = 0.85
UMBRAL_MEDIA = 0.60


@dataclass(frozen=True)
class AporteConfianza:
    """Un factor que sube o baja la confianza, con su motivo (trazable)."""

    factor: str          # p.ej. "ocr_word_confidence", "bbox_ausente"
    delta: float         # aporte firmado, típicamente en [-1, 1]
    motivo: str = ""


@dataclass
class ConfianzaCampo:
    """Confianza de UN dato, en dos ejes, con su desglose."""

    campo: str
    metodo_extraccion: str                    # "excel"|"csv"|"pdfplumber"|"ocr"|"manual"
    confianza_extraccion: float               # 0..1
    confianza_interpretacion: float           # 0..1
    aportes_extraccion: list[AporteConfianza] = field(default_factory=list)
    aportes_interpretacion: list[AporteConfianza] = field(default_factory=list)

    @property
    def nivel_extraccion(self) -> NivelConfianza:
        raise NotImplementedError("P1-E: implementar en el servidor")

    @property
    def nivel_interpretacion(self) -> NivelConfianza:
        raise NotImplementedError("P1-E: implementar en el servidor")

    @property
    def confianza_global(self) -> float:
        """Combinación conservadora de ambos ejes.

        Se usa el MÍNIMO (la cadena es tan fuerte como su eslabón más débil):
        un dato bien extraído pero mal interpretado NO es un dato confiable.
        Se expone además cada eje por separado para el papel de trabajo.
        """
        raise NotImplementedError("P1-E: implementar en el servidor")

    @property
    def requiere_revision_humana(self) -> bool:
        """True si cualquiera de los dos ejes cae bajo ``UMBRAL_MEDIA``.

        Alimenta el control 6 del CLAUDE.md (``requiere_revision_humana`` →
        ícono dedicado) y el estado inicial de la matriz de evidencia.
        """
        raise NotImplementedError("P1-E: implementar en el servidor")


# ---------------------------------------------------------------------------
# Cálculo del eje de EXTRACCIÓN
# ---------------------------------------------------------------------------

# Piso de confianza por método, antes de penalizaciones/bonos.
CONFIANZA_BASE_METODO: dict[str, float] = {
    "manual": 1.00,
    "excel": 0.98,
    "csv": 0.95,
    "pdfplumber": 0.90,
    "ocr": 0.70,
}


def confianza_extraccion(
    metodo: str,
    *,
    source_ref: "SourceReference | None" = None,
    ocr_word_confidence: float | None = None,
    parseo_limpio: bool = True,
) -> tuple[float, list[AporteConfianza]]:
    """Confianza de que el dato se leyó bien de la fuente (0..1) + desglose.

    Factores:
      - base por ``metodo`` (``CONFIANZA_BASE_METODO``).
      - OCR: se pondera por ``ocr_word_confidence`` (la que reporta Vision).
      - ``bounding_box``/celda ausente en la ``source_ref`` → penaliza (no se
        pudo localizar el dato).
      - ``parseo_limpio=False`` (formato numérico no reconocido, texto raro) →
        penaliza.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


# ---------------------------------------------------------------------------
# Cálculo del eje de INTERPRETACIÓN
# ---------------------------------------------------------------------------


def confianza_interpretacion(
    *,
    resultado_match: "ResultadoEmparejamiento | None" = None,
    mapeo_conocido: bool = True,
) -> tuple[float, list[AporteConfianza]]:
    """Confianza de que el dato significa/casó lo que creemos (0..1) + desglose.

    Factores:
      - score del emparejamiento (``resultado_match.mejor.score``).
      - estado AMBIGUA → penaliza fuerte (casó con más de uno).
      - estado SIN_COINCIDENCIA → interpretación baja pero no nula (el dato
        existe; simplemente no encontró par).
      - ``mapeo_conocido=False`` (casillero/cuenta resuelto por heurística, no
        por catálogo oficial) → penaliza.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def evaluar_campo(
    campo: str,
    metodo: str,
    *,
    source_ref: "SourceReference | None" = None,
    ocr_word_confidence: float | None = None,
    parseo_limpio: bool = True,
    resultado_match: "ResultadoEmparejamiento | None" = None,
    mapeo_conocido: bool = True,
) -> ConfianzaCampo:
    """Arma la ``ConfianzaCampo`` completa combinando ambos ejes.

    Punto de entrada único del módulo: el resto de la plataforma llama a esto
    por cada dato extraído y guarda el resultado en la matriz de evidencia.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def nivel_de(score: float) -> NivelConfianza:
    """Traduce un score 0..1 a ALTA/MEDIA/BAJA con los umbrales del módulo."""
    raise NotImplementedError("P1-E: implementar en el servidor")
