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
    geometría.

  - **pdfplumber** (`backend/app/ict/parsers/f101_pdf.py`, `f103_pdf.py`):
    hoy los parsers hacen ``"\n".join(p.extract_text() for p in pdf.pages)``,
    lo que borra la frontera de páginas y toda coordenada. Aquí ofrecemos un
    WRAPPER paralelo (``extraer_paginas_pdfplumber``) que itera
    ``enumerate(pdf.pages)`` conservando el índice de página y las palabras con
    sus coordenadas. Los parsers actuales NO se modifican.

Regla de oro (CLAUDE.md · verificación previa): una cita nunca se inventa. Si
no se pudo localizar el dato en la página, ``bounding_box`` queda en ``None`` y
la confianza de extracción baja en consecuencia (ver ``confidence.py``).
"""

from __future__ import annotations

import hashlib
import io
import math
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any, Protocol, Sequence


def _norm_cmp(texto: Any) -> str:
    """Normalización ligera para comparar palabras (minúsculas, sin espacios
    redundantes ni tildes). No quita puntuación: un importe "1,234.56" debe
    seguir siendo comparable tal cual."""
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def _centro(b: "BoundingBox") -> tuple[float, float]:
    return ((b.x0 + b.x1) / 2.0, (b.y0 + b.y1) / 2.0)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ---------------------------------------------------------------------------
# Geometría
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundingBox:
    """Rectángulo que encierra un dato dentro de una página."""

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
        """Devuelve una copia con coordenadas en 0..1."""
        if self.unidad == "norm":
            return self
        if not self.ancho_pagina or not self.alto_pagina:
            raise ValueError(
                "normalizado() requiere ancho_pagina y alto_pagina salvo unidad='norm'"
            )
        return BoundingBox(
            x0=self.x0 / self.ancho_pagina,
            y0=self.y0 / self.alto_pagina,
            x1=self.x1 / self.ancho_pagina,
            y1=self.y1 / self.alto_pagina,
            unidad="norm",
            ancho_pagina=self.ancho_pagina,
            alto_pagina=self.alto_pagina,
        )

    @classmethod
    def desde_palabra_pdfplumber(cls, palabra: dict[str, Any]) -> "BoundingBox":
        """Construye la caja desde un dict de ``page.extract_words()``.

        pdfplumber entrega ``{"text", "x0", "x1", "top", "bottom", ...}`` en
        puntos PDF. Mapea ``top→y0`` y ``bottom→y1``.
        """
        return cls(
            x0=float(palabra["x0"]),
            y0=float(palabra["top"]),
            x1=float(palabra["x1"]),
            y1=float(palabra["bottom"]),
            unidad="pt",
        )

    @classmethod
    def desde_bounding_poly_vision(
        cls,
        bounding_poly: Any,
        *,
        ancho_pagina: float | None = None,
        alto_pagina: float | None = None,
    ) -> "BoundingBox":
        """Construye la caja desde un ``bounding_poly`` de Vision.

        Toma el rectángulo envolvente (min/max de x e y). Si vienen
        ``normalized_vertices`` la unidad es ``"norm"``; si vienen ``vertices``
        la unidad es ``"px"``.
        """
        norms = list(getattr(bounding_poly, "normalized_vertices", None) or [])
        verts = list(getattr(bounding_poly, "vertices", None) or [])
        if norms:
            pts = [(float(v.x), float(v.y)) for v in norms]
            unidad = "norm"
        elif verts:
            pts = [(float(v.x), float(v.y)) for v in verts]
            unidad = "px"
        else:
            raise ValueError("bounding_poly sin vértices")
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return cls(
            x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys),
            unidad=unidad, ancho_pagina=ancho_pagina, alto_pagina=alto_pagina,
        )


# ---------------------------------------------------------------------------
# SourceReference — contrato §2 de la arquitectura de convergencia
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceReference:
    """Referencia trazable de un dato a su origen exacto (contrato §2)."""

    source_id: str
    file_hash: str
    filename: str
    sheet_or_table: str | None = None
    row_id: str | None = None
    column: str | None = None
    page: int | None = None
    bounding_box: BoundingBox | None = None
    original_value: str | None = None
    normalized_value: Any = None
    metodo: str = ""

    def con_cita_documental(self, page: int, bbox: BoundingBox | None) -> "SourceReference":
        """Devuelve una copia con página y bounding-box (DOC-008/009)."""
        return replace(self, page=page, bounding_box=bbox)


def source_id_de(file_hash: str, ubicacion: str) -> str:
    """ID estable y determinista de una referencia.

    ``ubicacion`` es algo como ``"p3#cas550"`` o ``"Enero!F12"``.
    """
    return hashlib.sha256(f"{file_hash}|{ubicacion}".encode("utf-8")).hexdigest()[:16]


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
    """Texto de UNA página con sus palabras geolocalizadas."""

    numero: int
    ancho: float
    alto: float
    texto: str
    palabras: list[PalabraUbicada] = field(default_factory=list)


def extraer_paginas_pdfplumber(pdf_bytes: bytes) -> list[PaginaTexto]:
    """Itera ``enumerate(pdf.pages)`` conservando página y geometría."""
    import pdfplumber

    paginas: list[PaginaTexto] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text() or ""
            palabras = [
                PalabraUbicada(
                    texto=w.get("text", ""),
                    bbox=BoundingBox.desde_palabra_pdfplumber(w),
                )
                for w in page.extract_words()
            ]
            paginas.append(
                PaginaTexto(
                    numero=i,
                    ancho=float(page.width),
                    alto=float(page.height),
                    texto=texto,
                    palabras=palabras,
                )
            )
    return paginas


def localizar_en_pagina(
    pagina: PaginaTexto,
    valor: str,
    *,
    cerca_de: str | None = None,
) -> BoundingBox | None:
    """Ubica ``valor`` dentro de una página y devuelve su bounding-box."""
    objetivo = _norm_cmp(valor)
    candidatas = [w for w in pagina.palabras if _norm_cmp(w.texto) == objetivo]
    if not candidatas:
        return None
    if len(candidatas) == 1 or not cerca_de:
        return candidatas[0].bbox
    anclas = [w for w in pagina.palabras if _norm_cmp(w.texto) == _norm_cmp(cerca_de)]
    if not anclas:
        return candidatas[0].bbox
    centro_ancla = _centro(anclas[0].bbox)
    mejor = min(candidatas, key=lambda w: _dist(_centro(w.bbox), centro_ancla))
    return mejor.bbox


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
    """Arma una ``SourceReference`` documental para un dato de un PDF digital."""
    file_hash = hash_de_archivo(pdf_bytes)
    bbox = localizar_en_pagina(pagina, original_value, cerca_de=ancla)
    ubic = f"p{pagina.numero}#{column}"
    return SourceReference(
        source_id=source_id_de(file_hash, ubic),
        file_hash=file_hash,
        filename=filename,
        page=pagina.numero,
        bounding_box=bbox,
        column=column,
        original_value=original_value,
        normalized_value=normalized_value,
        metodo="pdfplumber",
    )


# ---------------------------------------------------------------------------
# Captura desde Google Vision (wrapper que NO toca ocr.py)
# ---------------------------------------------------------------------------


@dataclass
class PalabraVision:
    """Palabra devuelta por Vision con su caja y su confianza propia."""

    texto: str
    bbox: BoundingBox
    confianza: float


@dataclass
class PaginaVision:
    """Página OCR con palabras geolocalizadas y confianza de Vision."""

    numero: int
    ancho: float
    alto: float
    texto: str
    palabras: list[PalabraVision] = field(default_factory=list)


def _pedir_anotaciones(client, chunks: list[bytes]) -> list:
    """Llama a Vision por cada chunk y devuelve los ``file_response``.

    Aislado para poder inyectarlo/mockearlo en tests sin la librería
    ``google.cloud.vision`` ni red.
    """
    from google.cloud import vision

    feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
    respuestas = []
    for chunk in chunks:
        input_config = vision.InputConfig(content=chunk, mime_type="application/pdf")
        request = vision.AnnotateFileRequest(input_config=input_config, features=[feature])
        response = client.batch_annotate_files(requests=[request])
        if not getattr(response, "responses", None):
            continue
        respuestas.append(response.responses[0])
    return respuestas


def _paginas_desde_respuestas(file_responses: list) -> list[PaginaVision]:
    """Parseo PURO de los ``file_response`` de Vision a ``PaginaVision``."""
    paginas: list[PaginaVision] = []
    numero = 0
    for fr in file_responses:
        for page_resp in getattr(fr, "responses", []) or []:
            fta = getattr(page_resp, "full_text_annotation", None)
            if not fta:
                continue
            texto = getattr(fta, "text", "") or ""
            for page in getattr(fta, "pages", []) or []:
                numero += 1
                ancho = float(getattr(page, "width", 0) or 0)
                alto = float(getattr(page, "height", 0) or 0)
                palabras: list[PalabraVision] = []
                for block in getattr(page, "blocks", []) or []:
                    for para in getattr(block, "paragraphs", []) or []:
                        for word in getattr(para, "words", []) or []:
                            simbolos = list(getattr(word, "symbols", []) or [])
                            wtexto = "".join(getattr(s, "text", "") for s in simbolos)
                            confs = [float(getattr(s, "confidence", 0) or 0) for s in simbolos]
                            conf = sum(confs) / len(confs) if confs else 0.0
                            bbox = BoundingBox.desde_bounding_poly_vision(
                                word.bounding_box,
                                ancho_pagina=ancho or None,
                                alto_pagina=alto or None,
                            )
                            palabras.append(PalabraVision(texto=wtexto, bbox=bbox, confianza=conf))
                paginas.append(
                    PaginaVision(numero=numero, ancho=ancho, alto=alto, texto=texto, palabras=palabras)
                )
    return paginas


def ocr_pdf_con_geometria(pdf_bytes: bytes) -> list[PaginaVision]:
    """OCR que CONSERVA la geometría, reutilizando el cliente de ocr.py."""
    from backend.app.utils import ocr

    if not ocr.is_available():
        raise ocr.OCRUnavailable("OCR no disponible: falta credencial de Google Vision.")
    client = ocr._get_client()
    chunks = ocr._split_pdf_pages(pdf_bytes, getattr(ocr, "_MAX_PAGES_PER_BATCH", 5))
    respuestas = _pedir_anotaciones(client, chunks)
    return _paginas_desde_respuestas(respuestas)


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
    objetivo = _norm_cmp(valor)
    bbox = None
    for w in pagina.palabras:
        if _norm_cmp(w.texto) == objetivo:
            bbox = w.bbox
            break
    ubic = f"p{pagina.numero}#{column}"
    return SourceReference(
        source_id=source_id_de(file_hash, ubic),
        file_hash=file_hash,
        filename=filename,
        page=pagina.numero,
        bounding_box=bbox,
        column=column,
        original_value=valor,
        normalized_value=normalized_value,
        metodo="ocr",
    )


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
    """Referencia a una celda de una hoja/tabla (mayor, auxiliar, balance)."""
    ubic = f"{sheet_or_table}!{row_id}:{column}"
    return SourceReference(
        source_id=source_id_de(file_hash, ubic),
        file_hash=file_hash,
        filename=filename,
        sheet_or_table=sheet_or_table,
        row_id=row_id,
        column=column,
        original_value=original_value,
        normalized_value=normalized_value,
        metodo=metodo,
    )


class ProveedorOCRConGeometria(Protocol):
    """Puerto para inyectar el OCR en tests sin llamar a Vision real."""

    def ocr_pdf_con_geometria(self, pdf_bytes: bytes) -> Sequence[PaginaVision]:
        ...
