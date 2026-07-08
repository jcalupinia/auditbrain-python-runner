# backend/app/aud/informe_cumplimiento_tributario/helpers.py
"""Helpers de formato para el Informe de Cumplimiento Tributario."""

from __future__ import annotations

import re

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

MARCO_PHRASES = {
    "pymes": (
        "Normas Internacionales de Información Financiera para Pequeñas y "
        "Medianas Entidades – NIIF para las PYMES"
    ),
    "plenas": "Normas Internacionales de Información Financiera – NIIF",
}


def fecha_larga_from_ddmmyyyy(s: str) -> str | None:
    """'09-04-2026' -> '09 de abril de 2026'. None si es inválida."""
    m = re.fullmatch(r"\s*(\d{1,2})-(\d{1,2})-(\d{4})\s*", s or "")
    if not m:
        return None
    dd, mm, yyyy = m.group(1), int(m.group(2)), m.group(3)
    if not (1 <= mm <= 12):
        return None
    if not (1 <= int(dd) <= 31):
        return None
    return f"{int(dd):02d} de {MESES[mm - 1]} de {yyyy}"


def normaliza_del(s: str) -> str:
    """'27 de febrero del 2026' -> '27 de febrero de 2026'."""
    return re.sub(r"\bdel\b", "de", s or "", flags=re.IGNORECASE)


def marco_phrase(marco: str) -> str:
    """'pymes'|'plenas' -> frase completa. Default seguro: PYMES."""
    return MARCO_PHRASES.get(marco, MARCO_PHRASES["pymes"])
