"""Parser for SRI Formulario 101 (Declaración Renta Sociedades) PDF.

Reuses regex helpers from obligaciones_fiscales for casillero extraction.
"""

from __future__ import annotations

from io import BytesIO

import pdfplumber

from backend.app.aud.obligaciones_fiscales.cedulas.base import find_periodo
# Usamos la versión ROBUSTA de find_casillero_value que sabe lidiar con el
# ruido de columnas del PDF SRI (líneas tipo "550 0.00 0.00 1234.56" donde
# 1234.56 es la columna del año actual). La versión simple en cedulas/base.py
# fallaba en los casilleros TOTAL (550, 589, 698) cuyas líneas tienen varios
# 0.00 antes del valor real.
from backend.app.tax.planificacion_utilidades.parsers.sri_text import (
    find_casillero_value,
)

ALL_F101_CASILLEROS: list[str] = [
    # ── Estado Situación Financiera — Activos corrientes ────────────────
    "311", "312", "313", "314", "315", "316", "317", "318", "319", "320",
    "321", "322", "323", "324", "325", "326", "327", "328", "329", "330",
    "331", "332", "333", "334", "335",                # nuevos (Crédito ISD, otros)
    "336", "337", "338", "339", "340", "341", "342", "343", "344", "345",
    "346", "347", "348", "349", "350", "351", "352", "353", "354", "355",
    "356", "357", "358", "359", "360", "361",
    # ── Activos no corrientes ────────────────────────────────────────────
    "362", "363", "364", "365", "366", "367", "368", "369", "370", "371",
    "372", "373", "374", "375", "376", "377", "378", "379", "380", "381",
    "382", "383", "384", "385", "386", "387", "388", "389", "390",
    "391", "392", "393", "394", "395", "396", "397", "398", "399", "400",
    "401", "402", "403", "404", "405", "406", "407", "408", "409", "410",
    "411", "412", "413", "414", "415", "416", "417", "418", "419", "420",
    "421", "422", "423", "424", "425", "426", "427", "428", "429", "430", "431",
    "432", "433", "434", "435", "436", "437", "438", "439", "440",
    "441", "442", "443", "444", "445", "446", "447", "448", "449",
    "490", "491",                                       # otros activos no corrientes
    "499",                                              # TOTAL DEL ACTIVO
    # ── Pasivos corrientes (511-550 incluyendo TOTAL) ───────────────────
    "511", "512", "513", "514", "515", "516", "517", "518", "519", "520",
    "521", "522", "523", "524", "525", "526", "527", "528", "529", "530",
    "531", "532", "533", "534", "535", "536", "537", "538", "539", "540",
    "541", "542", "543", "544", "545", "546", "547", "548", "549", "550",
    # ── Pasivos no corrientes (553-589 incluyendo TOTAL) ────────────────
    "553", "554", "555", "556", "557", "558", "559", "560", "561", "562",
    "563", "564", "565", "566", "567", "568", "569", "570", "571", "572",
    "573", "574", "575", "576", "577", "578", "579", "580", "581", "582",
    "583", "584", "585", "586", "587", "588", "589",
    "593",                                              # otros pasivos no cte
    "599",                                              # TOTAL DEL PASIVO
    # ── Patrimonio (601-698 incluyendo TOTAL) ────────────────────────────
    "601", "602", "603", "604", "605", "606", "607", "608", "609", "610",
    "611", "612", "613", "614", "615", "616", "617", "618", "619", "620",
    "621", "622", "623", "624", "625", "626", "627",
    "698",
    "699",                                              # TOTAL PASIVO Y PATRIMONIO
    # ── Conciliación tributaria + Diferencias temporarias ───────────────
    "801", "802", "803", "804", "805", "806", "807", "808", "809", "810",
    "811", "812", "813", "814", "815", "816", "817", "818", "819", "820",
    "821", "822", "823", "824", "825", "826", "827", "828", "829", "830",
    "831", "832", "833", "834", "835", "836", "837", "838", "839", "840",
    "841", "842", "843", "844", "845", "846", "847", "848", "849",
    "850", "851",                                       # crédito tributario IR
    "888", "889",                                       # otros conceptos
    "1112", "1113", "1116", "1117",
    # ── Ingresos + Totales de Ingresos ──────────────────────────────────
    "6001", "6005", "6011", "6015", "6021", "6025", "6031", "6035", "6041",
    "6045", "6051", "6055", "6059", "6061", "6065", "6071", "6075", "6081", "6085",
    "6091", "6095",
    "1005",                                             # TOTAL INGRESOS ACT. ORDINARIAS
    "1045",                                             # TOTAL INGRESOS NO OPERACIONALES
    "6152",                                             # INGRESOS BRUTOS SEGÚN CONTABILIDAD
    "6999",                                             # TOTAL INGRESOS
    # ── Costos y gastos + Totales ────────────────────────────────────────
    "7001", "7010", "7013", "7022", "7025", "7028", "7031", "7034", "7037",
    "7113", "7114", "7173", "7174", "7182", "7183", "7185", "7186",
    "7205", "7206", "7207", "7223", "7224", "7225", "7226", "7227", "7228",
    "7235", "7236", "7237",
    "7278", "7279", "7290", "7291",
    "7991",                                             # TOTAL COSTOS OPERACIONALES
    "7992",                                             # TOTAL GASTOS
    "7999",                                             # TOTAL COSTOS Y GASTOS
]


def parse_f101(pdf_bytes: bytes) -> dict:
    """Read F-101 PDF and return {'periodo': str|None, 'casilleros': {num: float}, 'errores': []}."""
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as e:  # noqa: BLE001
        return {"periodo": None, "casilleros": {}, "errores": [f"PDF inválido: {e}"]}

    if not text.strip():
        return {
            "periodo": None,
            "casilleros": {},
            "errores": ["PDF sin texto extraíble (¿escaneado? Aplica OCR e intenta de nuevo)"],
        }

    periodo = find_periodo(text)
    casilleros: dict[str, float] = {}
    for num in ALL_F101_CASILLEROS:
        v = find_casillero_value(text, num)
        if v is not None:
            casilleros[num] = v

    return {"periodo": periodo, "casilleros": casilleros, "errores": []}
