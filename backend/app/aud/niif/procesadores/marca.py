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
