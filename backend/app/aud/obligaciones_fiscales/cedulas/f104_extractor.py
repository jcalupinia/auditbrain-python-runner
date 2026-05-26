"""Extractor común del F-104 (Declaración de IVA SRI Ecuador).

El F-104 contiene tanto la declaración de IVA como la sección de
'Agente de Retención del IVA' con casilleros 721-799. Por eso ambas
cédulas (DM6 IVA y DM7 Retenciones x pagar) consumen el mismo PDF F-104.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pdfplumber

from backend.app.aud.obligaciones_fiscales.cedulas.base import (
    find_casillero_value,
    find_periodo,
)

# Casilleros de la sección IVA (para DM6)
CASILLEROS_IVA = [
    "411", "412", "413", "414", "415", "416", "417", "418",
    "419", "420", "421", "429", "480", "499", "529",
]

# Casilleros de la sección 'Agente de Retención del IVA' (para DM7)
CASILLEROS_RETENCION_IVA = ["721", "723", "725", "727", "729", "731", "799"]

ALL_CASILLEROS = CASILLEROS_IVA + CASILLEROS_RETENCION_IVA


def extract_f104(pdf_bytes: bytes) -> dict | None:
    """Lee un PDF F-104 y devuelve {periodo, casilleros: {num: valor}}.

    Devuelve None si el PDF no se puede abrir o no tiene texto extraíble.
    """
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return None
    if not text.strip():
        return None

    periodo = find_periodo(text)
    casilleros = {num: find_casillero_value(text, num) for num in ALL_CASILLEROS}
    return {"periodo": periodo, "casilleros": casilleros}


def extract_all_f104(paths: list[Path]) -> tuple[dict[str, dict], list[str]]:
    """Lee múltiples PDFs F-104, los agrupa por mes.

    Devuelve (month_data, errors) donde:
    - month_data: {"01": {periodo, casilleros}, "02": ...}
    - errors: lista de mensajes de error por archivo problemático
    """
    month_data: dict[str, dict] = {}
    errors: list[str] = []
    for path in paths:
        data = extract_f104(path.read_bytes())
        if data is None:
            errors.append(f"No se pudo parsear: {path.name}")
            continue
        periodo = data.get("periodo")
        if not periodo:
            errors.append(f"Sin período detectado: {path.name}")
            continue
        mes_key = periodo.split("/")[0]
        if mes_key in month_data:
            errors.append(f"Mes {mes_key} duplicado en {path.name}; se mantiene el primero")
            continue
        month_data[mes_key] = data
    return month_data, errors
