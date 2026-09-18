"""Lectura de los archivos de cartera del cliente.

Los archivos llegan con el formato regional del sistema que los generó. Aquí se
normalizan importes y fechas antes de que el motor vea un solo número.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable

_PATRON_DMY = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$")
_PATRON_ISO = re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})")


def a_numero(valor: Any) -> float:
    """Convierte a número respetando cualquier formato regional.

    El separador decimal es el último que aparece; el otro es de miles. Un único
    separador seguido de exactamente tres dígitos es de miles: "1.500" son mil
    quinientos. Los paréntesis indican negativo.
    """
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return 0.0
    negativo = s.startswith("(") and s.endswith(")") or "-" in s
    s = re.sub(r"[^0-9.,]", "", s)
    if not s:
        return 0.0
    i = max(s.rfind(","), s.rfind("."))
    entero, decimal = s, ""
    if i >= 0:
        cola = s[i + 1:]
        unico = len(re.sub(r"[^.,]", "", s)) == 1
        if not (unico and len(cola) == 3):
            entero, decimal = s[:i], cola
    entero = re.sub(r"[.,]", "", entero)
    try:
        n = float(f"{entero}.{decimal}" if decimal else entero or "0")
    except ValueError:
        return 0.0
    return -n if negativo and n > 0 else n


def inferir_formato_fecha(valores: Iterable[Any]) -> str:
    """Deduce si las fechas del archivo son día/mes/año o mes/día/año."""
    dmy = mdy = total = 0
    for v in valores:
        if isinstance(v, (date, datetime)):
            return "nativo"
        m = _PATRON_DMY.match(str(v or "").strip())
        if not m:
            continue
        total += 1
        if int(m.group(1)) > 12:
            dmy += 1
        if int(m.group(2)) > 12:
            mdy += 1
    if not total:
        return "nativo"
    if dmy and mdy:
        return "inconsistente"
    if dmy:
        return "dmy"
    if mdy:
        return "mdy"
    return "ambiguo"


def a_fecha(valor: Any, formato: str = "dmy") -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if valor is None or valor == "":
        return None
    s = str(valor).strip()
    m = _PATRON_DMY.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        anio = int(m.group(3))
        anio += 2000 if anio < 100 else 0
        dia, mes = (b, a) if formato == "mdy" else (a, b)
        try:
            return date(anio, mes, dia)
        except ValueError:
            return None
    m = _PATRON_ISO.match(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None
