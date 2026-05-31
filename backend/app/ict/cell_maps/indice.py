"""Cell map for ÍNDICE sheet of ICT 2025 template."""

INDICE_SHEET = "INDICE"

INDICE_HEADER_MAP = {
    "C3": "razon_social",
    "C4": "ruc",
    "C5": "ejercicio_fiscal",
}

# row → anexo_code (with optional _Cn suffix for sub-cuadros)
INDICE_APLICA_MAP = {
    10: "A1",
    12: "A2_C1",
    13: "A2_C2",
    14: "A2_C3",
    16: "A3",
    19: "A4_C1",
    20: "A4_C2",
    22: "A5",
    25: "A6_C1",
    26: "A6_C2",
    27: "A6_C3",
    29: "A7_C1",
    30: "A7_C2",
    32: "A8_C1",
    33: "A8_C2",
    35: "A9",
}

INDICE_APLICA_COLUMN = "J"
