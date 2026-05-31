"""Cell map for COSTOS  GASTOS A3 sheet (9 bloques de límites de deducibilidad).

Sheet name has a DOUBLE SPACE: "COSTOS  GASTOS A3" — preserved exactly.

Template inspection (verified rows):
  Header:   B3=razon_social, B4=ruc, B5=ejercicio_fiscal
  Col F = "Valor reportado por el contribuyente" in all bloques (except Cuentas
  Incobrables which uses col G — handled separately).

Each bloque entry: (row, casillero_key, col)
  casillero_key is the string key expected in anexo_data["f101"].
  For compound casilleros like "7205+7206" the filler sums both.
"""

A3_SHEET = "COSTOS  GASTOS A3"  # NOTE: double space

A3_HEADER_MAP = {
    "B3": "razon_social",
    "B4": "ruc",
    "B5": "ejercicio_fiscal",
}

# ---------------------------------------------------------------------------
# Bloque 1: GASTOS DE GESTIÓN (rows 15-25)
# Filler writes: row 15 (cas 7992), row 16 (cas 7185), row 21 (cas 7185 again), row 22 (cas 7186)
# Rows 17-19 and 23-25 are formula rows — NOT touched.
# ---------------------------------------------------------------------------
A3_BLOQUE_GASTOS_GESTION: list[tuple[int, str, str]] = [
    (15, "7992", "F"),   # Total gastos declarados
    (16, "7185", "F"),   # Gastos de gestión declarados
    (21, "7185", "F"),   # Gastos de gestión declarados (sección deducible)
    (22, "7186", "F"),   # Gastos de gestión declarados como no deducibles
]

# ---------------------------------------------------------------------------
# Bloque 2: GASTOS DE VIAJE (rows 32-50)
# Filler writes income base (32-41) + gasto declarado (46-47).
# Rows 42-44 and 48-50 are formulas.
# ---------------------------------------------------------------------------
A3_BLOQUE_GASTOS_VIAJE: list[tuple[int, str, str]] = [
    (32, "6999", "F"),   # Total Ingresos
    (33, "804", "F"),    # Dividendos exentos y efectos método participación
    (34, "805", "F"),    # Otras rentas exentas e ingresos no objeto
    (35, "812", "F"),    # Ingresos sujetos a IR único
    (36, "1116", "F"),   # Diferencias temporarias — contratos de construcción
    (37, "828", "F"),    # Diferencias temporarias — mediciones valor razonable
    (38, "834", "F"),    # Diferencias temporarias — otras diferencias
    (39, "1117", "F"),   # Diferencias temporarias — contratos (positivo)
    (40, "829", "F"),    # Diferencias temporarias — mediciones (positivo)
    (41, "835", "F"),    # Diferencias temporarias — otras (positivo)
    (46, "7182", "F"),   # Gastos de viaje declarados
    (47, "7183", "F"),   # Gastos de viaje declarados como no deducibles
]

# ---------------------------------------------------------------------------
# Bloque 3: GASTOS INDIRECTOS ASIGNADOS DESDE EL EXTERIOR (rows 56-66)
# Compound casillero "7205+7206": filler sums both keys.
# ---------------------------------------------------------------------------
A3_BLOQUE_GASTOS_INDIRECTOS: list[tuple[int, str, str]] = [
    # row 56: utilidad gravable (base) — MANUAL, not from casillero → skip
    (57, "7205+7206", "F"),   # Costos y gastos indirectos asignados declarados (total)
    (62, "7205+7206", "F"),   # Same again (sección deducibilidad)
    (63, "7207", "F"),        # Declarados como no deducibles
]

# ---------------------------------------------------------------------------
# Bloque 4: GASTOS DE PROMOCIÓN Y PUBLICIDAD (rows 72-90)
# Same income base structure as Viaje (6999, 804, 805, etc.)
# ---------------------------------------------------------------------------
A3_BLOQUE_PROMOCION_PUBLICIDAD: list[tuple[int, str, str]] = [
    (72, "6999", "F"),
    (73, "804", "F"),
    (74, "805", "F"),
    (75, "812", "F"),
    (76, "1116", "F"),
    (77, "828", "F"),
    (78, "834", "F"),
    (79, "1117", "F"),
    (80, "829", "F"),
    (81, "835", "F"),
    (86, "7173", "F"),   # Gastos promoción y publicidad declarados
    (87, "7174", "F"),   # Gastos promoción y publicidad declarados como no deducibles
]

# ---------------------------------------------------------------------------
# Bloque 5: GASTOS DE INTERESES POR CRÉDITOS DEL EXTERIOR (rows 97-108)
# rows 97, 101 are reference values (manual/placeholder); rows 104-105 are casilleros.
# Compound "7278+7290" and "7279+7291".
# ---------------------------------------------------------------------------
A3_BLOQUE_INTERESES: list[tuple[int, str, str]] = [
    (98, "698", "F"),          # Total Patrimonio
    (104, "7278+7290", "F"),   # Gastos intereses con inst. financieras del exterior declarados
    (105, "7279+7291", "F"),   # Declarados como no deducibles
]

# ---------------------------------------------------------------------------
# Bloque 6: GASTOS DE INSTALACIÓN, ORGANIZACIÓN Y SIMILARES (rows 114-124)
# Compound "7235+7236".
# ---------------------------------------------------------------------------
A3_BLOQUE_INSTALACION: list[tuple[int, str, str]] = [
    (115, "7235+7236", "F"),   # Costos y gastos de instalación declarados
    (120, "7235+7236", "F"),   # Same (sección deducibilidad)
    (121, "7237", "F"),        # Declarados como no deducibles
]

# ---------------------------------------------------------------------------
# Bloque 7a: DETERIORO ACUMULADO DE ACTIVOS FINANCIEROS (rows 131-138)
# Uses col G (not F) for value. Only reference values, mostly manual.
# ---------------------------------------------------------------------------
A3_BLOQUE_DETERIORO_ACUMULADO: list[tuple[int, str, str]] = [
    (132, "MANUAL_relacionados", "G"),    # Saldo cartera relacionados — manual
    (133, "MANUAL_no_relacionados", "G"), # Saldo cartera no relacionados — manual
    (137, "MANUAL_deterioro_acum", "G"),  # Valor deterioro acumulado correspondiente — manual
]

# ---------------------------------------------------------------------------
# Bloque 7b: GASTOS DETERIORO DE ACTIVOS FINANCIEROS (rows 145-155)
# Uses col G.
# ---------------------------------------------------------------------------
A3_BLOQUE_DETERIORO_GASTO: list[tuple[int, str, str]] = [
    (151, "7113", "G"),   # Gastos por pérdidas netas por deterioro (relacionados)
    (152, "7114", "G"),   # Gastos por pérdidas netas (no relacionados)
]

# ---------------------------------------------------------------------------
# Bloque 8: DONACIONES QUE SE DESTINEN EN CARRERAS TÉCNICAS (rows 162-174)
# ---------------------------------------------------------------------------
A3_BLOQUE_DONACIONES_ED: list[tuple[int, str, str]] = [
    (162, "6999", "F"),   # Total ingresos gravados / Total activos
    (173, "MANUAL_donacion_ed", "F"),  # Valor verificado en declaración — manual
]

# ---------------------------------------------------------------------------
# Bloque 9a: DONACIONES, INVERSIONES Y/O PATROCINIOS (rows 182-195)
# ---------------------------------------------------------------------------
A3_BLOQUE_DONACIONES_INV: list[tuple[int, str, str]] = [
    (182, "6999", "F"),   # Total ingresos gravados
    (193, "MANUAL_donacion_inv", "F"),  # Valor verificado — manual
]

# ---------------------------------------------------------------------------
# Bloque 9b: GASTOS OPERACIONES DE REGALÍAS (rows 202-210)
# Compound "7223+7224+7226+7227" and "7225+7228".
# ---------------------------------------------------------------------------
A3_BLOQUE_REGALIAS: list[tuple[int, str, str]] = [
    (202, "6999", "F"),          # Ingresos gravables
    (206, "7223+7224+7226+7227", "F"),  # Costos y gastos regalías declarados
    (207, "7225+7228", "F"),     # Declarados como no deducibles
]

# ---------------------------------------------------------------------------
# Master list: all bloques that the filler iterates
# Each entry: (bloque_name, list_of_(row, casillero, col))
# ---------------------------------------------------------------------------
A3_BLOQUES: list[tuple[str, list[tuple[int, str, str]]]] = [
    ("gastos_gestion", A3_BLOQUE_GASTOS_GESTION),
    ("gastos_viaje", A3_BLOQUE_GASTOS_VIAJE),
    ("gastos_indirectos", A3_BLOQUE_GASTOS_INDIRECTOS),
    ("promocion_publicidad", A3_BLOQUE_PROMOCION_PUBLICIDAD),
    ("intereses_exterior", A3_BLOQUE_INTERESES),
    ("instalacion_organizacion", A3_BLOQUE_INSTALACION),
    ("deterioro_acumulado", A3_BLOQUE_DETERIORO_ACUMULADO),
    ("deterioro_gasto", A3_BLOQUE_DETERIORO_GASTO),
    ("donaciones_educacion", A3_BLOQUE_DONACIONES_ED),
    ("donaciones_inversion", A3_BLOQUE_DONACIONES_INV),
    ("regalias", A3_BLOQUE_REGALIAS),
]

# Casilleros that are compound (sum of multiple casilleros)
# Map: compound_key → list of individual casillero strings
A3_COMPOUND_CASILLEROS: dict[str, list[str]] = {
    "7205+7206": ["7205", "7206"],
    "7235+7236": ["7235", "7236"],
    "7278+7290": ["7278", "7290"],
    "7279+7291": ["7279", "7291"],
    "7223+7224+7226+7227": ["7223", "7224", "7226", "7227"],
    "7225+7228": ["7225", "7228"],
}

# Keys prefixed MANUAL_ are skipped by automatic filler (require manual input)
MANUAL_PREFIX = "MANUAL_"
