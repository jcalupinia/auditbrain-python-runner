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

# Casilleros de la sección IVA (para DM6) — subset compatibilidad legacy
CASILLEROS_IVA = [
    "411", "412", "413", "414", "415", "416", "417", "418",
    "419", "420", "421", "429", "480", "499", "529",
]

# Casilleros de la sección 'Agente de Retención del IVA' (para DM7)
CASILLEROS_RETENCION_IVA = ["721", "723", "725", "727", "729", "731", "799"]

# ⚠️ REGLA SUPREMA (CLAUDE.md): ALL_CASILLEROS debe cubrir TODOS los
# casilleros del F-104 oficial SRI 2025. Verificado empíricamente
# contra el F-104 real de PROPHAR 01/2025: 145 casilleros únicos en
# el PDF → 145 en esta lista. NO ELIMINAR ninguno sin actualizar
# también backend/app/ict/catalogo_f104.py + tests.
ALL_CASILLEROS = [
    # Ventas bases imponibles (401-410)
    "401", "402", "403", "404", "405", "406", "407", "408", "409", "410",
    # Ventas netas (411-420)
    "411", "412", "413", "414", "415", "416", "417", "418", "419", "420",
    # IVA generado, notas crédito (421-435)
    "421", "422", "423", "424", "425", "429", "430", "431", "434", "435",
    # Transferencias no objeto, NC, reembolsos (441-454)
    "441", "442", "443", "444", "445", "453", "454",
    # Totales ventas y liquidación (480-499)
    "480", "481", "482", "483", "484", "485", "499",
    # Adquisiciones bases (500-510)
    "500", "501", "502", "503", "504", "505", "506", "507", "508", "509", "510",
    # Adquisiciones netas (511-520)
    "511", "512", "513", "514", "515", "516", "517", "518", "519", "520",
    # IVA adquisiciones + total (521-529)
    "521", "522", "523", "524", "525", "526", "527", "529",
    # Adquisiciones especiales + factor (530-565)
    "530", "531", "532", "533", "534", "535",
    "540", "541", "542", "543", "544", "545",
    "550", "554", "555",
    "560", "563", "564", "565",
    # Impuesto causado y crédito tributario (601-625)
    "601", "602", "603", "604", "605", "606", "607", "608", "609", "610",
    "611", "612", "613", "614", "615", "617", "618", "619", "620",
    "621", "622", "623", "624", "625",
    # Totales adquisiciones y recuperaciones (699-702)
    "699", "700", "701", "702",
    # Agente retención IVA (721-799)
    "721", "723", "725", "727", "729", "731", "799",
    # Crédito por retenciones (800-802)
    "800", "801", "802",
    # Total consolidado (859)
    "859",
    # Pago directo y cuotas (880-887)
    "880", "882", "883", "884", "885", "886", "887",
    # Resumen del pago (890-999)
    "890", "897", "898", "899", "902", "903", "904", "999",
]


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
