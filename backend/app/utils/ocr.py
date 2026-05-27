"""OCR para PDFs escaneados e imágenes vía Google Cloud Vision API.

Por qué Google Vision (vs Tesseract local):
- Mejor calidad con escaneos de baja resolución (declaraciones del SRI
  antiguas, escrituras notariales, contratos firmados).
- No requiere instalar binarios nativos (Tesseract no se puede instalar
  con el buildpack Python de Render — solo con Docker buildpack).
- Free tier: 1000 unidades/mes = 1000 imágenes O 1000 páginas PDF.
- Si excedes el free tier: $1.50 por 1000 unidades (sigue siendo barato).

Configuración:
1. Crear un Service Account en Google Cloud con rol "Cloud Vision User".
2. Descargar el JSON del Service Account.
3. Pegarlo entero como una sola línea en la env var
   GOOGLE_APPLICATION_CREDENTIALS_JSON de Render.
4. Habilitar la Cloud Vision API en el proyecto de Google Cloud.

Ver `docs/OCR_SETUP_GOOGLE.md` para el paso a paso completo.

Uso típico:

    from backend.app.utils import ocr

    if ocr.is_available():
        result = ocr.ocr_pdf("declaracion_sri_2023.pdf")
        texto = result["text"]
        paginas = result["pages"]
    else:
        # Fallback: usar pdfplumber para PDFs digitales
        ...
"""

from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepciones de dominio
# ---------------------------------------------------------------------------

class OCRUnavailable(RuntimeError):
    """OCR no configurado o librería no instalada en el servidor."""


class OCRError(RuntimeError):
    """OCR falló por error del proveedor o de archivo."""


# ---------------------------------------------------------------------------
# Disponibilidad
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Devuelve True si OCR está configurado y la lib está instalada.

    Permite que el resto del código haga fallback elegante a pdfplumber
    cuando OCR no esté disponible (entornos dev, tests, etc.).
    """
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip():
        return False
    try:
        import google.cloud.vision  # noqa: F401
        return True
    except ImportError:
        return False


def _require_available() -> None:
    """Levanta OCRUnavailable si OCR no está listo. Mensajes claros."""
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip():
        raise OCRUnavailable(
            "OCR no configurado: define GOOGLE_APPLICATION_CREDENTIALS_JSON "
            "en Render con el contenido del service account JSON. "
            "Ver docs/OCR_SETUP_GOOGLE.md."
        )
    try:
        import google.cloud.vision  # noqa: F401
    except ImportError as exc:
        raise OCRUnavailable(
            "Librería google-cloud-vision no instalada en este entorno. "
            "Asegúrate de que requirements-prod.txt esté actualizado."
        ) from exc


# ---------------------------------------------------------------------------
# Cliente Vision API
# ---------------------------------------------------------------------------

_client_cache: Any = None


def _get_client():
    """Crea/cachea el cliente Vision API leyendo credentials del entorno."""
    global _client_cache
    if _client_cache is not None:
        return _client_cache

    _require_available()

    from google.cloud import vision
    from google.oauth2 import service_account

    creds_raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
    try:
        creds_dict = json.loads(creds_raw)
    except json.JSONDecodeError as exc:
        raise OCRUnavailable(
            f"GOOGLE_APPLICATION_CREDENTIALS_JSON no es JSON válido: {exc}"
        ) from exc

    credentials = service_account.Credentials.from_service_account_info(creds_dict)
    _client_cache = vision.ImageAnnotatorClient(credentials=credentials)
    return _client_cache


# ---------------------------------------------------------------------------
# OCR de imagen única
# ---------------------------------------------------------------------------

def ocr_image(path: str | Path) -> dict:
    """OCR de una imagen (PNG, JPG, TIFF, WEBP).

    Returns:
        {
          "text": str,               # texto extraído
          "language_hints": [str],   # códigos de idioma detectados
          "blocks": int,             # bloques de texto detectados
        }
    """
    from google.cloud import vision

    client = _get_client()
    p = Path(path)
    if not p.is_file():
        raise OCRError(f"Archivo no encontrado: {path}")

    with open(p, "rb") as fh:
        content = fh.read()

    image = vision.Image(content=content)
    # DOCUMENT_TEXT_DETECTION es óptimo para documentos densos
    # (vs TEXT_DETECTION que es para texto en escenas / fotos casual).
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise OCRError(f"Vision API error: {response.error.message}")

    annotation = response.full_text_annotation
    if not annotation:
        return {"text": "", "language_hints": [], "blocks": 0}

    languages: set[str] = set()
    block_count = 0
    for page in annotation.pages:
        block_count += len(page.blocks)
        for lang in page.property.detected_languages:
            languages.add(lang.language_code)

    return {
        "text": annotation.text or "",
        "language_hints": sorted(languages),
        "blocks": block_count,
    }


# ---------------------------------------------------------------------------
# OCR de PDF (con split automático para >5 páginas)
# ---------------------------------------------------------------------------

# Vision API sync acepta máx. 5 páginas por request en batch_annotate_files.
_MAX_PAGES_PER_BATCH = 5


def _split_pdf_pages(pdf_bytes: bytes, pages_per_chunk: int) -> list[bytes]:
    """Divide un PDF en bloques de N páginas. Usa pypdf (pure Python)."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise OCRUnavailable(
            "pypdf no instalado — requerido para PDFs >5 páginas. "
            "Añadir 'pypdf' a requirements-prod.txt."
        ) from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    if total_pages <= pages_per_chunk:
        return [pdf_bytes]

    chunks: list[bytes] = []
    for start in range(0, total_pages, pages_per_chunk):
        writer = PdfWriter()
        end = min(start + pages_per_chunk, total_pages)
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        buf = io.BytesIO()
        writer.write(buf)
        chunks.append(buf.getvalue())
    return chunks


def ocr_pdf(path: str | Path) -> dict:
    """OCR de un PDF (escaneado o digital).

    Para PDFs >5 páginas se hace split automático en chunks y se
    concatena el resultado. Cuenta como N unidades en Google Vision
    (una por página).

    Returns:
        {
          "text": str,         # texto concatenado de todas las páginas
          "pages": int,        # total de páginas procesadas
          "chunks": int,       # cuántos batches fueron necesarios
          "language_hints": [str],
        }
    """
    from google.cloud import vision

    client = _get_client()
    p = Path(path)
    if not p.is_file():
        raise OCRError(f"Archivo no encontrado: {path}")

    pdf_bytes = p.read_bytes()
    chunks = _split_pdf_pages(pdf_bytes, _MAX_PAGES_PER_BATCH)

    all_texts: list[str] = []
    all_languages: set[str] = set()
    total_pages = 0

    feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)

    for chunk_idx, chunk_bytes in enumerate(chunks):
        input_config = vision.InputConfig(
            content=chunk_bytes,
            mime_type="application/pdf",
        )
        request = vision.AnnotateFileRequest(
            input_config=input_config,
            features=[feature],
        )

        try:
            response = client.batch_annotate_files(requests=[request])
        except Exception as exc:
            raise OCRError(
                f"Vision API falló en chunk {chunk_idx + 1}/{len(chunks)}: {exc}"
            ) from exc

        if not response.responses:
            continue
        file_response = response.responses[0]
        if file_response.error.message:
            raise OCRError(
                f"Vision API error chunk {chunk_idx + 1}: "
                f"{file_response.error.message}"
            )

        for page_resp in file_response.responses:
            if page_resp.error.message:
                log.warning("Page error: %s", page_resp.error.message)
                continue
            if not page_resp.full_text_annotation:
                continue
            all_texts.append(page_resp.full_text_annotation.text or "")
            total_pages += 1
            for page in page_resp.full_text_annotation.pages:
                for lang in page.property.detected_languages:
                    all_languages.add(lang.language_code)

    return {
        "text": "\n\n".join(all_texts),
        "pages": total_pages,
        "chunks": len(chunks),
        "language_hints": sorted(all_languages),
    }


# ---------------------------------------------------------------------------
# OCR híbrido: intenta extracción rápida, cae a OCR si no hay texto
# ---------------------------------------------------------------------------

def extract_text_smart(path: str | Path) -> dict:
    """Intenta extraer texto del PDF de forma eficiente:
    1) Primero con pdfplumber (rápido, gratis, sirve para PDFs digitales).
    2) Si no encuentra texto significativo, cae a OCR via Vision API.

    Este es el método recomendado para uso general — minimiza llamadas
    pagas a Google Vision sin sacrificar calidad.

    Returns:
        {
          "text": str,
          "method": "pdfplumber" | "ocr" | "ocr_failed_fallback",
          "pages": int,
          "ocr_units_used": int,   # 0 si no se usó Vision
        }
    """
    import pdfplumber

    p = Path(path)
    if not p.is_file():
        raise OCRError(f"Archivo no encontrado: {path}")

    # 1) Intento pdfplumber
    try:
        with pdfplumber.open(p) as pdf:
            texts = []
            for page in pdf.pages:
                texts.append(page.extract_text() or "")
            joined = "\n\n".join(texts).strip()
            pages_count = len(pdf.pages)
    except Exception as exc:
        log.warning("pdfplumber falló: %s; intentando OCR", exc)
        joined = ""
        pages_count = 0

    # Si pdfplumber sacó suficiente texto (>50 chars por página promedio),
    # no necesita OCR.
    if joined and pages_count > 0 and len(joined) > 50 * pages_count:
        return {
            "text": joined,
            "method": "pdfplumber",
            "pages": pages_count,
            "ocr_units_used": 0,
        }

    # 2) Fallback a Vision API
    if not is_available():
        return {
            "text": joined,
            "method": "ocr_failed_fallback",
            "pages": pages_count,
            "ocr_units_used": 0,
        }

    ocr_result = ocr_pdf(path)
    return {
        "text": ocr_result["text"],
        "method": "ocr",
        "pages": ocr_result["pages"],
        "ocr_units_used": ocr_result["pages"],
    }
