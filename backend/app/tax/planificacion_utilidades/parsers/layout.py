"""Detecta el formato de un libro de EEFF."""
from __future__ import annotations
import re
from .periodos import clasificar_periodo


def _segs(code):
    return [p.strip() for p in re.split(r"[-.]", str(code)) if p.strip() != ""]


def detect_layout(df) -> str:
    """'codificado' | 'plantilla' | 'resumido_nombre'."""
    hay_codigos = False
    hay_periodos = False
    for _, row in df.iterrows():
        vals = row.tolist()
        c0 = _segs(vals[0]) if vals and vals[0] is not None else []
        if c0 and c0[0] in ("1", "2", "3", "4", "5", "6") and c0[0].isdigit():
            hay_codigos = True
        for v in vals[1:]:
            if clasificar_periodo(v):
                hay_periodos = True
        for v in vals:
            if isinstance(v, str) and v.strip().lower() == "clave":
                return "plantilla"
    if hay_codigos:
        return "codificado"
    if hay_periodos:
        return "resumido_nombre"
    return "resumido_nombre"
