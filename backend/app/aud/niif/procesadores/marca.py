"""Logotipos de la firma (AuditConsulting) y de la plataforma (AUDIT-IA) para los
papeles de trabajo NIIF: Excel, Word, PowerPoint y HTML.

Son los mismos logotipos del portal (``frontend/public/assets``), reducidos para
no inflar los archivos. El HTML los lleva incrustados en base64 para que siga
funcionando sin internet.

- ``auditconsulting_blanco``: letras blancas, para fondos oscuros (banda navy del
  Excel, barra del HTML, PowerPoint).
- ``auditconsulting_oscuro``: letras oscuras, para fondos claros (Word, PDF).
- ``audit_ia``: logotipo de la plataforma (trae su propio fondo oscuro).
"""
from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
ARCHIVOS = {
    "auditconsulting_blanco": "logo_auditconsulting_blanco.png",
    "auditconsulting_oscuro": "logo_auditconsulting_oscuro.png",
    "audit_ia": "logo_audit_ia.jpg",
}
ALT = {
    "auditconsulting_blanco": "AuditConsulting Auditores Cía. Ltda.",
    "auditconsulting_oscuro": "AuditConsulting Auditores Cía. Ltda.",
    "audit_ia": "AUDIT-IA",
}


@lru_cache(maxsize=None)
def datos(nombre: str) -> bytes:
    return (ASSETS / ARCHIVOS[nombre]).read_bytes()


@lru_cache(maxsize=None)
def tamano(nombre: str) -> tuple[int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(datos(nombre))) as im:
        return im.size


def flujo(nombre: str) -> io.BytesIO:
    """Archivo en memoria (openpyxl, python-docx y python-pptx lo aceptan)."""
    return io.BytesIO(datos(nombre))


def data_uri(nombre: str) -> str:
    mime = "image/jpeg" if ARCHIVOS[nombre].endswith(".jpg") else "image/png"
    return f"data:{mime};base64,{base64.b64encode(datos(nombre)).decode()}"


def ancho_para(nombre: str, alto: float) -> float:
    """Ancho que conserva la proporción del logotipo para un alto dado."""
    w, h = tamano(nombre)
    return alto * w / h


def imagen_excel(nombre: str, alto_px: int):
    """``openpyxl.drawing.image.Image`` escalada al alto pedido (en píxeles)."""
    from openpyxl.drawing.image import Image as XLImage

    img = XLImage(flujo(nombre))
    img.height = alto_px
    img.width = round(ancho_para(nombre, alto_px))
    return img


# --- logo del cliente (la compañía auditada) --------------------------------
# A diferencia de los logos de la firma —que viven en ``assets/``—, el logo del
# cliente lo sube el auditor en la ficha del encargo y viaja como *data URI*
# (``FichaEncargo.datos["logoCliente"]``). El HTML lo usa tal cual (acepta SVG);
# el Excel, Word y PowerPoint solo pueden incrustar mapas de bits, así que un
# SVG se omite en esos formatos (el nombre del cliente ya va como texto).

import re as _re

_RASTER_URI = _re.compile(r"^data:image/(png|jpe?g);base64,(.+)$", _re.S)


def bytes_de_uri(uri: str) -> tuple[bytes, str] | None:
    """``(bytes, mime)`` de un *data URI* de imagen **raster** (PNG/JPG).

    Devuelve ``None`` si el URI está vacío, no es base64 válido o no es raster
    (p. ej. SVG) — openpyxl/python-docx/python-pptx no incrustan SVG.
    """
    m = _RASTER_URI.match(str(uri or "").strip())
    if not m:
        return None
    try:
        data = base64.b64decode(m.group(2), validate=False)
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return None
    if not data:
        return None
    mime = "image/jpeg" if m.group(1).lower().startswith("jp") else "image/png"
    return data, mime


def imagen_excel_uri(uri: str, alto_px: int):
    """``XLImage`` del logo del cliente escalada al alto pedido; ``None`` si no es raster."""
    d = bytes_de_uri(uri)
    if d is None:
        return None
    from openpyxl.drawing.image import Image as XLImage
    from PIL import Image

    data, _mime = d
    try:
        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
    except Exception:  # noqa: BLE001 (imagen ilegible → se omite, no rompe el Excel)
        return None
    if not w or not h:
        return None
    img = XLImage(io.BytesIO(data))
    img.height = alto_px
    img.width = round(alto_px * w / h)
    return img


def flujo_uri(uri: str) -> io.BytesIO | None:
    """Archivo en memoria del logo del cliente para python-docx/pptx; ``None`` si no es raster."""
    d = bytes_de_uri(uri)
    return io.BytesIO(d[0]) if d is not None else None


def ancho_uri(uri: str, alto: float) -> float | None:
    """Ancho que conserva la proporción del logo del cliente para un alto dado (mismas unidades)."""
    d = bytes_de_uri(uri)
    if d is None:
        return None
    from PIL import Image

    try:
        with Image.open(io.BytesIO(d[0])) as im:
            w, h = im.size
    except Exception:  # noqa: BLE001
        return None
    return alto * w / h if h else None
