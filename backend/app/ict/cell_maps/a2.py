"""Cell map for INGRESOS A2 sheet (3 cuadros, fixed dimensions).

Template inspection confirmed:
  Header: C3=razon_social, C4=ruc, C5=ejercicio_fiscal
  Cuadro 1 (Ingresos Ordinarios):  rows 14-21, cols B-E
  Cuadro 2 (IVA vs Facturación):   rows 35-44, cols B-N
  Cuadro 3 (Conciliación IVA→IR):  rows 51-65, col B (valor neto)
"""

A2_SHEET = "INGRESOS A2"

A2_HEADER_MAP = {
    "C3": "razon_social",
    "C4": "ruc",
    "C5": "ejercicio_fiscal",
}

# ---------------------------------------------------------------------------
# Cuadro 1: Ingresos Ordinarios (F-101 declaración IR)
# Columns:
#   B = Tarifa 0% de IVA o exentas
#   C = Tarifa diferente de 0% de IVA
#   D = Exportaciones
#   E = Otros Ingresos gravados
# Row 25 = totals (formula, NOT touched)
# ---------------------------------------------------------------------------
A2_CUADRO1_ROWS = {
    14: "ventas_bienes",
    15: "ventas_servicios",
    16: "otros_ingresos",
    17: "exportaciones_bienes",
    18: "exportaciones_servicios",
    19: "construccion",
    20: "comisiones",
    21: "arrendamientos",
}

# Map: (concepto, column_letter) → F-101 casillero
# Column B = tarifa 0%, C = tarifa dif 0%, D = exportaciones, E = otros gravados
A2_CUADRO1_CASILLERO_MAP: dict[tuple[str, str], str] = {
    ("ventas_bienes", "B"): "6003",          # Ventas bienes tarifa 0%
    ("ventas_bienes", "C"): "6001",          # Ventas bienes tarifa dif 0%
    ("ventas_servicios", "B"): "6013",       # Servicios tarifa 0%
    ("ventas_servicios", "C"): "6011",       # Servicios tarifa dif 0%
    ("exportaciones_bienes", "D"): "6005",   # Exportaciones bienes
    ("exportaciones_servicios", "D"): "6015", # Exportaciones servicios
    ("otros_ingresos", "E"): "6017",         # Otros ingresos gravados
    ("construccion", "E"): "6019",           # Construcción (modalidad)
    ("comisiones", "E"): "6021",             # Comisiones
    ("arrendamientos", "E"): "6023",         # Arrendamientos operativos
}

# ---------------------------------------------------------------------------
# Cuadro 2: IVA vs Facturación
# Rows from template:
#   35 = Ventas locales (excl. activos fijos) tarifa dif 0%
#   36 = Ventas activos fijos tarifa dif 0%
#   37 = Ventas locales tarifa 0% sin derecho crédito
#   38 = Ventas activos fijos tarifa 0% sin derecho crédito
#   39 = Ventas locales tarifa 0% con derecho crédito
#   40 = Ventas activos fijos tarifa 0% con derecho crédito
#   41 = Exportaciones bienes
#   42 = Exportaciones servicios
#   43 = Total ventas y otras operaciones
#   44 = Transferencias no objeto o exentas
#
# Columns (per template inspection):
#   B = IVA tarifa 0%
#   C = IVA tarifa dif 0%
#   D = IVA exportaciones
#   E = Notas de crédito
#   G = Facturación electrónica emitidas
#   H = Facturación electrónica anuladas / NC
#   J = Facturación física emitidas
#   K = Facturación física anuladas / NC
# ---------------------------------------------------------------------------
A2_CUADRO2_ROWS = {
    35: "ventas_locales_diff_iva",
    36: "ventas_activos_fijos_diff",
    37: "ventas_locales_0_sin_derecho",
    38: "ventas_activos_0_sin_derecho",
    39: "ventas_locales_0_con_derecho",
    40: "ventas_activos_0_con_derecho",
    41: "exportaciones_bienes",
    42: "exportaciones_servicios",
    43: "total_ventas",
    44: "transferencias_no_objeto",
}

# Map: (concepto, column_letter) → F-104 casillero declarado (total anual).
# Columna IZQUIERDA del Cuadro 2 = lo DECLARADO en el F-104 por tarifa.
# Casilleros validados contra el golden master ICT_14 (401-408).
A2_CUADRO2_IVA_MAP: dict[tuple[str, str], str] = {
    ("ventas_locales_diff_iva", "C"): "401",
    ("ventas_activos_fijos_diff", "C"): "402",
    ("ventas_locales_0_sin_derecho", "B"): "403",
    ("ventas_activos_0_sin_derecho", "B"): "404",
    ("ventas_locales_0_con_derecho", "B"): "405",
    ("ventas_activos_0_con_derecho", "B"): "406",
    ("exportaciones_bienes", "D"): "407",
    ("exportaciones_servicios", "D"): "408",
    ("transferencias_no_objeto", "B"): "418",  # B44 en ICT_14
}

# Columna F del Cuadro 2 = "Valor neto de Ingresos" (lo FACTURADO), casilleros
# 411-418 del F-104. Cada fila del Cuadro 2 lleva su valor neto en la col F.
# (concepto → casillero F-104). Validado contra ICT_14.
A2_CUADRO2_VALORNETO_MAP: dict[str, str] = {
    "ventas_locales_diff_iva": "411",
    "ventas_activos_fijos_diff": "412",
    "ventas_locales_0_sin_derecho": "413",
    "ventas_activos_0_sin_derecho": "414",
    "ventas_locales_0_con_derecho": "415",
    "ventas_activos_0_con_derecho": "416",
    "exportaciones_bienes": "417",
    "exportaciones_servicios": "418",
}

# Columna fuente (B/C/D) de cada fila del Cuadro 2, para la fórmula de la
# columna E = diferencia = (columna fuente) − F (valor neto). Validado ICT_14.
A2_CUADRO2_SOURCE_COL: dict[str, str] = {
    "ventas_locales_diff_iva": "C",
    "ventas_activos_fijos_diff": "C",
    "ventas_locales_0_sin_derecho": "B",
    "ventas_activos_0_sin_derecho": "B",
    "ventas_locales_0_con_derecho": "B",
    "ventas_activos_0_con_derecho": "B",
    "exportaciones_bienes": "D",
    "exportaciones_servicios": "D",
}

# Cuadro 1 — fórmula del total por fila (col F): cuáles columnas se suman.
# Validado contra ICT_14 (F14=B+C+E, F17=D+E, F19=E, etc.).
A2_CUADRO1_TOTAL_COLS: dict[int, tuple[str, ...]] = {
    14: ("B", "C", "E"), 15: ("B", "C", "E"), 16: ("B", "C", "E"),
    17: ("D", "E"), 18: ("D", "E"),
    19: ("E",), 20: ("E",), 21: ("E",),
}

# Facturación electrónica columns in Cuadro 2
A2_CUADRO2_FACT_ELEC_COLS = {
    "emitidas": "G",
    "anuladas": "H",
}
# Row for total facturación electrónica (row 43 = total ventas)
A2_CUADRO2_TOTAL_ROW = 43

# ---------------------------------------------------------------------------
# Cuadro 3: Conciliación IVA → IR
# Col B = Valor Neto (most are 0 in template; client fills manually)
# Rows with formula: 60 (=SUM), 66 (=(i) formula)
# Rows that accept manual/computed values: 51-59, 61-65
# ---------------------------------------------------------------------------
A2_CUADRO3_ROWS = {
    51: "ventas_locales_diff",
    52: "ventas_activos_fijos_diff",
    53: "ventas_locales_0_sin_derecho",
    54: "ventas_activos_0_sin_derecho",
    55: "ventas_locales_0_con_derecho",
    56: "ventas_activos_0_con_derecho",
    57: "exportaciones_bienes",
    58: "exportaciones_servicios",
    59: "transferencias_no_objeto",
    # row 60 = Total IVA (=SUM formula — NOT written by filler)
    61: "menos_autoconsumo",
    62: "mas_estimacion",
    63: "diferencia_iva_fact",
    64: "menos_provisiones_niif",
    65: "otros",
    # row 66 = Total ingresos IR (formula = (i))
}
