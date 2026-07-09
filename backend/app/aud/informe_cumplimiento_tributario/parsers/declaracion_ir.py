# backend/app/aud/informe_cumplimiento_tributario/parsers/declaracion_ir.py
"""Parser del F-101 (Declaración IR Sociedades) PDF.

Extrae la FECHA RECAUDACIÓN (= fecha de declaración del IR, param 5) y el
período fiscal. Verificado contra PDF real AXXIS (recaudación 09-04-2026).
"""

from __future__ import annotations

import re

from backend.app.aud.informe_cumplimiento_tributario.helpers import (
    fecha_larga_from_ddmmyyyy,
)
from backend.app.aud.informe_cumplimiento_tributario.parsers import _pdf


def parse(pdf_bytes: bytes) -> dict:
    errores: list[str] = []
    text = _pdf.extract_text(pdf_bytes, errores)
    fecha = _fecha_recaudacion(text)
    periodo = _periodo_fiscal(text)
    if fecha is None:
        errores.append("No se encontró la FECHA RECAUDACIÓN en el F-101.")
    return {
        "fecha_declaracion_ir": fecha,
        "ejercicio": periodo,
        "errores": errores,
    }


def _fecha_recaudacion(text: str) -> str | None:
    m = re.search(r"FECHA\s+RECAUDACI[OÓ]N", text, re.IGNORECASE)
    scope = text[m.start():] if m else text
    d = re.search(r"(\d{2}-\d{2}-\d{4})", scope)
    if not d:
        return None
    return fecha_larga_from_ddmmyyyy(d.group(1))


def _periodo_fiscal(text: str) -> str | None:
    m = re.search(r"Periodo\s+Fiscal:\s*A[NÑ]O\s*(\d{4})", text, re.IGNORECASE)
    return m.group(1) if m else None
