"""Helpers compartidos por los parsers de EEFF (versiones canónicas).

Evita la duplicación de `_segs`, `_norm` y `_read_excel` entre `balance_interno`,
`layout`, `mapeo_nombres` y `balance_resumido_nombre`. Las definiciones son las
que históricamente vivían en `balance_interno.py`.
"""
from __future__ import annotations

import io
import re
import unicodedata

import pandas as pd


def _norm(s: str) -> str:
    """Normaliza a mayúsculas ASCII sin acentos, recortando extremos."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.upper().strip()


def _segs(code) -> list[str]:
    """Segmentos del código de cuenta, agnóstico al separador (punto o guion)."""
    return [p.strip() for p in re.split(r"[-.]", str(code)) if p.strip() != ""]


def _read_excel(data: bytes) -> pd.ExcelFile:
    """Abre un libro Excel eligiendo el engine por la firma del archivo."""
    engine = "xlrd" if data[:4] == b"\xd0\xcf\x11\xe0" else "openpyxl"
    return pd.ExcelFile(io.BytesIO(data), engine=engine)
