"""Helper compartido de extracción de texto de PDFs."""

from __future__ import annotations

from io import BytesIO

import pdfplumber


def extract_text(pdf_bytes: bytes, errores: list[str]) -> str:
    try:
        out = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                out.append(page.extract_text() or "")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        errores.append(f"No se pudo leer el PDF: {e}")
        return ""
