# backend/app/aud/informe_cumplimiento_tributario/parsers/informe_auditoria_externa.py
"""Parser del Informe de Auditoría Externa PDF.

Extrae:
- fecha de emisión (param 4): primera fecha larga tras el título
  'INFORME DE LOS AUDITORES INDEPENDIENTES'. Verificado AXXIS -> 27-feb-2026.
- marco contable (param 7): 'pymes' si menciona NIIF para PYMES, si no 'plenas'.
"""

from __future__ import annotations

import re

from backend.app.aud.informe_cumplimiento_tributario.helpers import normaliza_del
from backend.app.aud.informe_cumplimiento_tributario.parsers import _pdf


def parse(pdf_bytes: bytes) -> dict:
    errores: list[str] = []
    text = _pdf.extract_text(pdf_bytes, errores)
    fecha = _fecha_emision(text)
    marco = _marco_contable(text)
    if fecha is None:
        errores.append("No se encontró la fecha de emisión en el informe.")
    return {"fecha_emision": fecha, "marco_contable": marco, "errores": errores}


def _fecha_emision(text: str) -> str | None:
    idx = text.find("INFORME DE LOS AUDITORES INDEPENDIENTES")
    scope = text[idx:] if idx >= 0 else text
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-zA-ZñÑáéíóúÁÉÍÓÚ]+)\s+del?\s+(\d{4})", scope
    )
    if not m:
        return None
    fecha = f"{m.group(1)} de {m.group(2).lower()} del {m.group(3)}"
    return normaliza_del(fecha)


def _marco_contable(text: str) -> str:
    if re.search(
        r"NIIF\s+para\s+(las\s+)?PYMES|Peque[nñ]as\s+y\s+Medianas",
        text,
        re.IGNORECASE,
    ):
        return "pymes"
    return "plenas"
