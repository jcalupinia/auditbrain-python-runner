"""Clasificación de cabeceras de período de un estado financiero."""
from __future__ import annotations
import re
import datetime as dt

_MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _de_fecha(anio: int, mes: int) -> dict:
    return {"label": f"{_MESES[mes]}-{str(anio)[2:]}", "tipo": "parcial", "meses": mes, "anio": anio}


def clasificar_periodo(cell):
    """Devuelve {label,tipo,meses,anio} o None si la celda no es un período."""
    if isinstance(cell, dt.datetime):
        return _de_fecha(cell.year, cell.month)
    if isinstance(cell, dt.date):
        return _de_fecha(cell.year, cell.month)
    if isinstance(cell, bool):
        return None
    if isinstance(cell, int) and 1900 < cell < 2100:
        return {"label": str(cell), "tipo": "anual", "meses": 12, "anio": cell}
    if isinstance(cell, str):
        s = cell.strip()
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return _de_fecha(int(m.group(1)), int(m.group(2)))
        if s.isdigit() and len(s) == 4 and 1900 < int(s) < 2100:
            return {"label": s, "tipo": "anual", "meses": 12, "anio": int(s)}
    return None
