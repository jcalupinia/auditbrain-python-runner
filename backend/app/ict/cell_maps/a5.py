"""Cell map for CONCILIACIÓN COSTOS Y GASTOS A5 sheet (5 cuadros + prorrateo).

Template inspection (verified rows):
  Header:   C3=razon_social, C4=ruc, C5=ejercicio_fiscal

  Cuadro A (rows 17-21): Detalle gastos no deducibles locales y del exterior
    Columns per row:
      A  = Identificación del gasto (filler uses nombre de cuenta)
      B  = No. Casillero de la declaración  (manual — NOT touched)
      C  = Código de cuenta contable
      D  = Nombre de la cuenta contable
      E  = Descripción del tipo de gasto no deducible (manual — NOT touched)
      G  = Normativa aplicable (manual — NOT touched)
      I  = Descripción tipo ingreso exento (manual — NOT touched)
      K  = Valor total en libros contables  ← filler writes here
      L  = Valor declarado (manual — NOT touched)
      M  = Diferencia (formula — NOT touched)
    Row 22 = SUM(K17:K21) formula — NOT touched

  Cuadro B (rows 28-50): Aplicación del ajuste (prorrateo)
    — Input rows for ingresos exentos (rows 28-32): column G
    — Row 33: SUM(G28:G32) — formula, NOT touched
    — Row 34: Total ingresos casillero 6999 — G34 written by filler
    — Rows 36-40: Ajustes ingresos (manual/optional) — NOT touched by filler
    — Row 41: SUM(G34:G40) — formula, NOT touched
    — Row 42: Porcentaje exentos — formula, NOT touched
    — Row 43: Total costos casillero 7999 — G43 written by filler
    — Rows 45-49: Ajustes costos (manual/optional) — NOT touched by filler
    — Row 50: SUM(G43:G49) — formula, NOT touched
    — Row 51: Ajuste = pct * total costos — formula, NOT touched

  Cuadro C (rows 58-60): Participación trabajadores
    H58 = casillero 804
    H59 = casillero 805
    H60 = casillero 808
    Row 61: fórmula participación — NOT touched

  Cuadro D (rows 66-71): Conciliación gastos no deducibles
    H66 = casillero 806
    H67 = casillero 807
    H68 = casillero 808
    H69 = casillero 809
    H70 = casillero 813
    H71 = casillero 1113
    Row 72: SUM fórmula — NOT touched
    Row 73: Diferencias fórmula — NOT touched

  Cuadro E (rows 79-83): Gastos no deducibles con signo negativo (reversos)
    Manual entry — filler leaves blank (MVP)
"""

A5_SHEET = "CONCILIACIÓN COSTOS Y GASTOS A5"

A5_HEADER_MAP = {
    "C3": "razon_social",
    "C4": "ruc",
    "C5": "ejercicio_fiscal",
}

# Cuadro A: Detalle gastos no deducibles (5 data rows)
A5_CUADRO_A_RANGE = (17, 21)  # (start_row, end_row) inclusive

# Column mapping for Cuadro A detail rows
A5_CUADRO_A_COLS = {
    "identificacion": "A",   # Identificación del gasto (nombre de cuenta)
    "casillero": "B",        # No. Casillero de la declaración (no deducible)
    "codigo_cuenta": "C",    # Código de cuenta contable
    "nombre_cuenta": "D",    # Nombre de la cuenta contable
    "valor": "K",            # Valor total en libros contables
    "valor_declarado": "L",  # Valor declarado (ref a DATOS F-101)
}

# Cuadro B: Prorrateo — input casilleros written to column G
# These are the anchored rows from the template; filler writes the declaración totals.
# source: "f101" → valor directo del formulario
A5_CUADRO_B_MAP: dict[int, tuple[str, str]] = {
    34: ("f101", "6999"),   # Total Ingresos declarados
    43: ("f101", "7999"),   # Total Costos y Gastos declarados
}

# Cuadro C: Participación trabajadores — column H
# row → casillero (string key in f101)
A5_CUADRO_C_MAP: dict[int, str] = {
    58: "804",   # Dividendos exentos y efectos método participación
    59: "805",   # Otras rentas exentas e ingresos no objeto
    60: "808",   # Gastos incurridos para generar ingresos exentos
}

# Cuadro D: Conciliación gastos no deducibles — column H
A5_CUADRO_D_MAP: dict[int, str] = {
    66: "806",    # Gastos no deducibles locales
    67: "807",    # Gastos no deducibles del exterior
    68: "808",    # Gastos incurridos para generar ingresos exentos
    69: "809",    # Participación trabajadores atribuibles a exentos
    70: "813",    # Costos deducibles para generar ingresos exentos
    71: "1113",   # Costos y gastos para ingresos sujetos IR único / RIMPE
}

# Cuadro E: Gastos no deducibles con signo negativo (reversos)
# Rows 79-83 — MVP leaves blank; structure reserved for future implementation
A5_CUADRO_E_RANGE = (79, 83)
