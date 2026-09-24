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
        return nivel_de(self.confianza_extraccion)

    @property
    def nivel_interpretacion(self) -> NivelConfianza:
        return nivel_de(self.confianza_interpretacion)

    @property
    def confianza_global(self) -> float:
        """Combinación conservadora de ambos ejes: el MÍNIMO (la cadena es tan
        fuerte como su eslabón más débil)."""
        return min(self.confianza_extraccion, self.confianza_interpretacion)

    @property
    def requiere_revision_humana(self) -> bool:
        """True si cualquiera de los dos ejes cae bajo ``UMBRAL_MEDIA``."""
        return (
            self.confianza_extraccion < UMBRAL_MEDIA
            or self.confianza_interpretacion < UMBRAL_MEDIA
        )


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
    aportes: list[AporteConfianza] = []
    base = CONFIANZA_BASE_METODO.get(metodo, 0.50)
    score = base
    aportes.append(AporteConfianza("base_metodo", base, f"método de extracción: {metodo}"))

    if metodo == "ocr" and ocr_word_confidence is not None:
        nuevo = base * float(ocr_word_confidence)
        aportes.append(AporteConfianza(
            "ocr_word_confidence", nuevo - score,
            f"confianza OCR de Vision = {float(ocr_word_confidence):.2f}"))
        score = nuevo

    if source_ref is not None and getattr(source_ref, "page", None) is not None \
            and getattr(source_ref, "bounding_box", None) is None:
        aportes.append(AporteConfianza("bbox_ausente", -0.20,
                                       "no se pudo localizar el dato en la página"))
        score -= 0.20

    if not parseo_limpio:
        aportes.append(AporteConfianza("parseo_sucio", -0.15,
                                       "el valor no parseó con un formato reconocido"))
        score -= 0.15

    score = max(0.0, min(1.0, score))
    return score, aportes


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
    from backend.app.evidence.matcher import EstadoEmparejamiento

    aportes: list[AporteConfianza] = []
    if resultado_match is None:
        score = 0.50
        aportes.append(AporteConfianza("sin_match", 0.50, "sin emparejamiento contra otra fuente"))
    else:
        estado = resultado_match.estado
        mejor = resultado_match.mejor
        if estado is EstadoEmparejamiento.UNICA and mejor is not None:
            score = float(mejor.score)
            aportes.append(AporteConfianza("match_unico", score,
                                           f"match único (score {score:.2f})"))
        elif estado is EstadoEmparejamiento.AMBIGUA:
            base = float(mejor.score) if mejor is not None else 0.50
            score = base * 0.5
            aportes.append(AporteConfianza("match_ambiguo", score,
                                           "casó con más de un candidato (revisar)"))
        else:  # SIN_COINCIDENCIA
            score = 0.30
            aportes.append(AporteConfianza("sin_coincidencia", 0.30,
                                           "el dato existe pero no encontró par"))

    if not mapeo_conocido:
        aportes.append(AporteConfianza("mapeo_heuristico", -0.15,
                                       "casillero/cuenta resuelto por heurística, no por catálogo"))
        score -= 0.15

    score = max(0.0, min(1.0, score))
    return score, aportes


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
    """Arma la ``ConfianzaCampo`` completa combinando ambos ejes."""
    ce, aportes_e = confianza_extraccion(
        metodo, source_ref=source_ref, ocr_word_confidence=ocr_word_confidence,
        parseo_limpio=parseo_limpio,
    )
    ci, aportes_i = confianza_interpretacion(
        resultado_match=resultado_match, mapeo_conocido=mapeo_conocido,
    )
    return ConfianzaCampo(
        campo=campo,
        metodo_extraccion=metodo,
        confianza_extraccion=ce,
        confianza_interpretacion=ci,
        aportes_extraccion=aportes_e,
        aportes_interpretacion=aportes_i,
    )


def nivel_de(score: float) -> NivelConfianza:
    """Traduce un score 0..1 a ALTA/MEDIA/BAJA con los umbrales del módulo."""
    if score >= UMBRAL_ALTA:
        return NivelConfianza.ALTA
    if score >= UMBRAL_MEDIA:
        return NivelConfianza.MEDIA
    return NivelConfianza.BAJA
