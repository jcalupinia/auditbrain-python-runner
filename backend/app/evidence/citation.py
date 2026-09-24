"""Citación de evidencia: página + bounding-box por cada dato extraído.

Capacidades: DOC-008 (localizar cada dato en su página de origen) y
DOC-009 (bounding-box del dato dentro de esa página). Este módulo define el
contrato ``SourceReference`` (arquitectura de convergencia §2) y las funciones
que capturan la geometría desde las dos fuentes que ya usa la plataforma:

  - **Google Vision** (`backend/app/utils/ocr.py`): hoy el OCR DESCARTA la
    geometría — solo devuelve ``full_text_annotation.text``. Cada palabra de
    Vision trae un ``bounding_poly`` (4 vértices) que se pierde. Aquí lo
    recuperamos SIN tocar ocr.py: reutilizamos su cliente cacheado
    (``ocr._get_client``) y hacemos una segunda lectura que conserva la
    geometría. Ver el plan (tarea "Geometría de Vision sin romper ocr.py").

  - **pdfplumber** (`backend/app/ict/parsers/f101_pdf.py`, `f103_pdf.py`):
    hoy los parsers hacen ``"\n".join(p.extract_text() for p in pdf.pages)``,
    lo que borra la frontera de páginas y toda coordenada. Aquí ofrecemos un
    WRAPPER paralelo (``extraer_paginas_pdfplumber``) que itera
    ``enumerate(pdf.pages)`` conservando el índice de página y las palabras con
    sus coordenadas (``pdfplumber`` expone ``page.extract_words()`` con
    ``x0/x1/top/bottom``). Los parsers actuales NO se modifican; este camino es
    el que consumirá el futuro refactor y el crossref.

Regla de oro (CLAUDE.md · verificación previa): una cita nunca se inventa. Si
no se pudo localizar el dato en la página, ``bounding_box`` queda en ``None`` y
la confianza de extracción baja en consecuencia (ver ``confidence.py``).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

# ---------------------------------------------------------------------------
# Geometría
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundingBox:
    """Rectángulo que encierra un dato dentro de una página.

    Unifica las dos fuentes de coordenadas de la plataforma:

      - pdfplumber: puntos PDF (72 pt = 1 pulgada), origen arriba-izquierda,
        ``top``/``bottom`` crecen hacia abajo → ``unidad="pt"``.
      - Google Vision: vértices en píxeles del render, o normalizados 0..1
        según el response → ``unidad="px"`` o ``unidad="norm"``.

    Se guarda ``ancho_pagina``/``alto_pagina`` cuando se conocen para poder
    normalizar a 0..1 (útil para dibujar el resaltado sobre cualquier render,
    independiente del DPI).
    """

    x0: float
    y0: float
    x1: float
    y1: float
    unidad: str = "pt"  # "pt" | "px" | "norm"
    ancho_pagina: float | None = None
    alto_pagina: float | None = None

    @property
    def ancho(self) -> float:
        return abs(self.x1 - self.x0)

    @property
    def alto(self) -> float:
        return abs(self.y1 - self.y0)

    def normalizado(self) -> "BoundingBox":
        """Devuelve una copia con coordenadas en 0..1.

        Requiere ``ancho_pagina``/``alto_pagina`` salvo que ya sea ``norm``.
        """
        raise NotImplementedError("P1-E: implementar en el servidor")

    @classmethod
    def desde_palabra_pdfplumber(cls, palabra: dict[str, Any]) -> "BoundingBox":
        """Construye la caja desde un dict de ``page.extract_words()``.

        pdfplumber entrega ``{"text", "x0", "x1", "top", "bottom", ...}`` en
        puntos PDF. Mapea ``top→y0`` y ``bottom→y1``.
        """
        raise NotImplementedError("P1-E: implementar en el servidor")

    @classmethod
    def desde_bounding_poly_vision(
        cls,
        bounding_poly: Any,
        *,
        ancho_pagina: float | None = None,
        alto_pagina: float | None = None,
    ) -> "BoundingBox":
        """Construye la caja desde un ``bounding_poly`` de Vision.

        Vision da 4 vértices (``vertices`` en px o ``normalized_vertices`` en
        0..1). Se toma el rectángulo envolvente (min/max de x e y). Si vienen
        ``normalized_vertices`` la unidad es ``"norm"``; si vienen ``vertices``
        la unidad es ``"px"``.
        """
        raise NotImplementedError("P1-E: implementar en el servidor")


# ---------------------------------------------------------------------------
# SourceReference — contrato §2 de la arquitectura de convergencia
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceReference:
    """Referencia trazable de un dato a su origen exacto (contrato §2).

    Todos los campos del contrato: identidad del archivo (hash + nombre),
    ubicación tabular (hoja/tabla, fila, columna), ubicación documental
    (página + bounding-box) y el par de valores original/normalizado. Un dato
    puede tener VARIAS ``SourceReference`` (p.ej. la factura aparece en el
    auxiliar y en el XML SRI): eso lo modela ``crossref.MatrizEvidencia``.
    """

    source_id: str
    file_hash: str
    filename: str
    # Ubicación tabular (Excel/CSV/mayor). None si el origen es documental.
    sheet_or_table: str | None = None
    row_id: str | None = None
    column: str | None = None
    # Ubicación documental (PDF/imagen). None si el origen es tabular.
    page: int | None = None
    bounding_box: BoundingBox | None = None
    # Valores. ``original`` es tal cual aparece en la fuente (texto crudo);
    # ``normalized`` es el valor tras el parseo (Decimal/fecha/RUC limpio).
    original_value: str | None = None
    normalized_value: Any = None
    # Cómo se obtuvo el dato: "pdfplumber" | "ocr" | "excel" | "csv" | "manual".
    metodo: str = ""

    def con_cita_documental(self, page: int, bbox: BoundingBox | None) -> "SourceReference":
        """Devuelve una copia con página y bounding-box (DOC-008/009)."""
        raise NotImplementedError("P1-E: implementar en el servidor")


def source_id_de(file_hash: str, ubicacion: str) -> str:
    """ID estable y determinista de una referencia.

    ``ubicacion`` es algo como ``"p3#cas550"`` o ``"Enero!F12"``. El id combina
    hash de archivo + ubicación para que dos corridas produzcan el MISMO id
    (reproducibilidad, principio no negociable de la arquitectura).
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def hash_de_archivo(contenido: bytes) -> str:
    """SHA-256 hex del archivo (misma convención que la ingesta del mayor)."""
    return hashlib.sha256(contenido).hexdigest()


# ---------------------------------------------------------------------------
# Captura desde pdfplumber (wrapper que NO toca los parsers)
# ---------------------------------------------------------------------------


@dataclass
class PalabraUbicada:
    """Una palabra del PDF con su texto y su caja."""

    texto: str
    bbox: BoundingBox


@dataclass
class PaginaTexto:
    """Texto de UNA página con sus palabras geolocalizadas.

    Reemplaza al ``"\\n".join(...)`` de los parsers: conserva ``numero`` (1-based,
    como espera el auditor) y ``palabras`` para poder citar cada dato.
    """

    numero: int
    ancho: float
    alto: float
    texto: str
    palabras: list[PalabraUbicada] = field(default_factory=list)


def extraer_paginas_pdfplumber(pdf_bytes: bytes) -> list[PaginaTexto]:
    """Itera ``enumerate(pdf.pages)`` conservando página y geometría.

    Wrapper paralelo a los parsers F-101/F-103 (que hoy pierden la página).
    Para cada página: ``page.extract_text()`` (texto) y ``page.extract_words()``
    (palabras con ``x0/x1/top/bottom``). Es el reemplazo geometría-consciente
    del ``"\\n".join(p.extract_text() ...)``.

    NO modifica los parsers: es un segundo camino que el crossref y el futuro
    refactor consumen.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def localizar_en_pagina(
    pagina: PaginaTexto,
    valor: str,
    *,
    cerca_de: str | None = None,
) -> BoundingBox | None:
    """Ubica ``valor`` dentro de una página y devuelve su bounding-box.

    ``cerca_de`` (p.ej. el número de casillero "550") desambigua cuando el
    mismo valor aparece varias veces: se prefiere la ocurrencia más cercana al
    ancla. Si no se encuentra, devuelve ``None`` (nunca se inventa la caja).
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def source_reference_desde_pdfplumber(
    pdf_bytes: bytes,
    filename: str,
    pagina: PaginaTexto,
    *,
    column: str,
    original_value: str,
    normalized_value: Any,
    ancla: str | None = None,
) -> SourceReference:
    """Arma una ``SourceReference`` documental para un dato de un PDF digital.

    Usa ``localizar_en_pagina`` para la caja. ``column`` identifica el dato
    (p.ej. el casillero "550"). Camino DOC-008/009 para F-101/F-103 sin tocar
    los parsers.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


# ---------------------------------------------------------------------------
# Captura desde Google Vision (wrapper que NO toca ocr.py)
# ---------------------------------------------------------------------------


@dataclass
class PalabraVision:
    """Palabra devuelta por Vision con su caja y su confianza propia."""

    texto: str
    bbox: BoundingBox
    confianza: float  # Vision reporta confidence 0..1 por símbolo/palabra


@dataclass
class PaginaVision:
    """Página OCR con palabras geolocalizadas y confianza de Vision."""

    numero: int
    ancho: float
    alto: float
    texto: str
    palabras: list[PalabraVision] = field(default_factory=list)


def ocr_pdf_con_geometria(pdf_bytes: bytes) -> list[PaginaVision]:
    """OCR que CONSERVA la geometría, reutilizando el cliente de ocr.py.

    ``ocr.ocr_pdf`` descarta ``bounding_poly``. Aquí reutilizamos
    ``ocr._get_client()`` (mismo split de 5 páginas, mismas credenciales) pero
    recorremos ``full_text_annotation.pages[].blocks[].paragraphs[].words[]``
    quedándonos con ``word.bounding_box`` y ``symbol.confidence``. ocr.py NO se
    modifica; este wrapper vive en el paquete evidence.

    Depende de que ``ocr.is_available()`` sea True; si no, se cae con la misma
    ``OCRUnavailable`` que el resto de la plataforma.
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


def source_reference_desde_vision(
    file_hash: str,
    filename: str,
    pagina: PaginaVision,
    valor: str,
    *,
    column: str,
    normalized_value: Any,
) -> SourceReference:
    """Arma una ``SourceReference`` documental para un dato de un PDF escaneado."""
    raise NotImplementedError("P1-E: implementar en el servidor")


# ---------------------------------------------------------------------------
# Captura tabular (Excel/CSV/mayor) — sin geometría, con celda exacta
# ---------------------------------------------------------------------------


def source_reference_tabular(
    file_hash: str,
    filename: str,
    *,
    sheet_or_table: str,
    row_id: str,
    column: str,
    original_value: str,
    normalized_value: Any,
    metodo: str = "excel",
) -> SourceReference:
    """Referencia a una celda de una hoja/tabla (mayor, auxiliar, balance).

    Para las fuentes tabulares la "cita" es la celda (hoja + fila + columna),
    no un bounding-box. Complementa a la ingesta del mayor (``LecturaMayor``
    ya trae ``sha256`` y el número de fila del ``Movimiento``).
    """
    raise NotImplementedError("P1-E: implementar en el servidor")


class ProveedorOCRConGeometria(Protocol):
    """Puerto para inyectar el OCR en tests sin llamar a Vision real."""

    def ocr_pdf_con_geometria(self, pdf_bytes: bytes) -> Sequence[PaginaVision]:
        ...
