"""Cell map for BENEFICIOS TRIBUTARIOS A6 sheet (3 cuadros).

Template inspection (verified rows):
  Header:   C4=razon_social, C5=ruc, C6=ejercicio_fiscal

  Cuadro A (rows 17-23): Detalle deducciones adicionales
    Columns per row:
      A  = Código de cuenta contable
      B  = Nombre de la cuenta contable
      C  = Descripción de la deducción (manual — NOT touched)
      D  = Normativa aplicable (manual — NOT touched)
      E  = Valor en libros contables ← filler writes here
      F  = % de deducción adicional (manual/formula — NOT touched)
      G  = Valor de la deducción adicional = E*F (template formula — NOT touched)
      H  = Diferencia entre libros y declarado (formula — NOT touched)
    Row 24: SUM(E17:E23) y SUM(G17:G23) — formulas, NOT touched
    Row 25: G25 = casillero 810 (Total deducciones adicionales del F-101) ← filler writes
    Row 26: G26 = -G24+G25 diferencia — formula, NOT touched

  Cuadro B (rows 32-38): Contratos de inversión vigentes (dynamic rows)
    Columns per row:
      A  = No. Resolución
      B  = Fecha del contrato
      C  = ¿Contrato vigente? (manual — NOT touched)
      D  = Descripción incentivos (manual — NOT touched)
      F  = Norma que los contiene (manual — NOT touched)
      G  = Años de ejecución (manual — NOT touched)
      H  = Período beneficio (manual — NOT touched)
      I  = Impuesto que aplica (manual — NOT touched)
      J  = ¿Utilizado en el ejercicio? (manual — NOT touched)
      K  = Monto del incentivo (optional — filler writes if provided)
      L  = Tarifa IR utilizada (manual — NOT touched)

  Cuadro C (rows 42-45): Exoneraciones / disminución de tarifa IR
    Columns per row:
      A  = Concepto (pre-filled in template — NOT touched)
      D  = No. Resolución (if applicable) ← filler writes if provided
      E  = Período inicio inversión ← filler writes if provided
      G  = ¿Incentivo utilizado? ← filler writes (Sí/No)
      H  = Monto del incentivo ← filler writes if provided
      I  = Tarifa IR utilizada (manual — NOT touched)
"""

A6_SHEET = "BENEFICIOS TRIBUTARIOS A6"

A6_HEADER_MAP = {
    "C4": "razon_social",
    "C5": "ruc",
    "C6": "ejercicio_fiscal",
}

# Cuadro A: Detalle deducciones adicionales (7 data rows, rows 17-23)
A6_CUADRO_A_RANGE = (17, 23)  # (start_row, end_row) inclusive

# Column mapping for Cuadro A detail rows
A6_CUADRO_A_COLS = {
    "codigo_cuenta": "A",   # Código de cuenta contable
    "nombre_cuenta": "B",   # Nombre de la cuenta contable
    "valor_libros": "E",    # Valor en libros contables
}

# Row 25, col G: Total deducciones adicionales casillero 810 del F-101
A6_CUADRO_A_CASILLERO_810_CELL = "G25"

# Cuadro B: Contratos de inversión vigentes (dynamic, rows 32-38)
A6_CUADRO_B_RANGE = (32, 38)  # (start_row, end_row) inclusive

# Column mapping for Cuadro B
A6_CUADRO_B_COLS = {
    "no_resolucion": "A",   # No. Resolución
    "fecha": "B",           # Fecha del contrato
    "monto_incentivo": "K", # Monto del incentivo utilizado (optional)
}

# Cuadro C: Exoneraciones — fixed rows, one per tipo
# row → dict key in anexo_data["exoneraciones"]
A6_CUADRO_C_ROWS: dict[int, str] = {
    42: "administradores_zonas_francas",
    43: "deporte",
    44: "exportadores_habituales",
    45: "otros_beneficios",
}

# Cuadro C columns used by the filler
A6_CUADRO_C_COLS = {
    "no_resolucion": "D",      # No. de la Resolución (si aplica)
    "periodo_inicio": "E",     # Período en que se inició la inversión
    "utilizado": "G",          # ¿El incentivo fue utilizado? (Sí/No)
    "monto_incentivo": "H",    # Monto del incentivo utilizado
}
