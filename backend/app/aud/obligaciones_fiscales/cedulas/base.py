"""Interface base para cédulas DM* + utilidades comunes de parseo SRI."""

from __future__ import annotations

import re
from typing import Protocol

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

_MES_ES_TO_NUM = {
    "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04",
    "MAYO": "05", "JUNIO": "06", "JULIO": "07", "AGOSTO": "08",
    "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12",
}


class CedulaCompute(Protocol):
    code: str

    def expected_inputs(self) -> list[str]: ...

    def compute(self, inputs: dict) -> dict: ...


def find_periodo(text: str) -> str | None:
    """Detecta el periodo fiscal del PDF SRI.

    Soporta:
    - 'Período Fiscal: ENERO 2025'
    - 'Mes: 01 Año: 2025'
    - 'MM/AAAA' literal
    Devuelve 'MM/AAAA' o None.
    """
    m = re.search(
        r"Per[ií]odo\s+Fiscal[:\s]+([A-ZÁÉÍÓÚÑ]+)\s+(20\d{2})",
        text,
        re.IGNORECASE,
    )
    if m:
        mes = _MES_ES_TO_NUM.get(m.group(1).upper())
        if mes:
            return f"{mes}/{m.group(2)}"
    m = re.search(r"Mes[:\s]*0?(\d{1,2})\s*A[ñn]o[:\s]*(\d{4})", text, re.IGNORECASE)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}"
    m = re.search(r"\b(0?\d|1[0-2])\s*/\s*(20\d{2})\b", text)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}"
    return None


def find_casillero_value(text: str, casillero: str) -> float | None:
    """Busca el valor decimal asociado a un casillero SRI.

    REGLA del proyecto (CLAUDE.md): el sistema acepta números en formato
    US (`178,259.63`), europeo (`178.259,63`) o plano (`178259.63`).
    Esto permite que clientes con computadores configurados con coma o
    punto como separador decimal puedan cargar PDFs sin pre-procesar.

    Patrón: '<casillero>\\s+<monto>' (acepta cualquier formato monetario
    SRI). Si hay múltiples coincidencias, devuelve la primera con valor.
    """
    # Monto: dígitos + opcionales grupos "separador+dígitos"
    pattern = rf"\b{casillero}\s+(-?\d+(?:[.,]\d+)*)"
    for raw in re.findall(pattern, text):
        val = _parse_amount_sri(raw)
        if val is not None:
            return val
    return None


def _parse_amount_sri(s: str) -> float | None:
    """Convierte número en formato SRI (US o europeo) a float.

    Reglas:
      - '178,259.63' o '178.259,63'  → 178259.63
      - '178259.63' o '0.00' o '25,50' → directo
      - El SEPARADOR DECIMAL es el ÚLTIMO que aparece (`,` o `.`).
    """
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # euro → US
        else:
            s = s.replace(",", "")                      # US: quitar miles
    elif has_comma:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            s = s.replace(",", ".")                     # coma decimal
        else:
            s = s.replace(",", "")                      # coma de miles US
    try:
        return float(s)
    except ValueError:
        return None
