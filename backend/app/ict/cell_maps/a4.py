"""Cell map for CONCILIACIÓN INGRESOS A4 sheet (2 cuadros).

Template inspection (verified rows):
  Header:   C3=razon_social, C4=ruc, C5=ejercicio_fiscal

  Cuadro 1 (rows 16-25): Detalle ingresos exentos / no objeto / único / RIMPE
    Columns layout per row:
      A = Identificación del ingreso
      B = No. Casillero declaración
      C = Código cuenta contable
      D = Nombre cuenta contable
      E = Descripción tipo ingreso
      F = Normativa de respaldo
      G = Valor total en libros (input cell)
    Row 26 = SUM(G16:G25) formula — NOT touched

  Cuadro 2 (rows 32-35): Conciliación libros vs declaración
    G32 = casillero 804
    G33 = casillero 805
    G34 = casillero 812
    G35 = casillero 1112
    Row 36 = SUM(G32:G35) formula — NOT touched
    Row 37 = G26-G36 difference formula — NOT touched
"""

A4_SHEET = "CONCILIACIÓN INGRESOS A4"

A4_HEADER_MAP = {
    "C3": "razon_social",
    "C4": "ruc",
    "C5": "ejercicio_fiscal",
}

# Cuadro 1: detalle de cuentas exentas del Libro Mayor
# Rows 16-25 (10 rows), filler writes columns A-G per movimiento
A4_CUADRO1_RANGE = (16, 25)  # (start_row, end_row) inclusive

# Column mapping for Cuadro 1 detail rows
A4_CUADRO1_COLS = {
    "identificacion": "A",   # Identificación del ingreso (a)
    "casillero": "B",         # No. Casillero de la declaración (b)
    "codigo_cuenta": "C",     # Código de cuenta contable (c)
    "nombre_cuenta": "D",     # Nombre de la cuenta contable (d)
    "descripcion": "E",       # Descripción del tipo de ingreso exento (d)
    "normativa": "F",         # Normativa de respaldo (e)
    "valor": "G",             # Valor total en libros contables (f)
}

# Cuadro 2: conciliación libros vs declaración F-101
# Maps row → casillero number (string key in f101 dict)
A4_CUADRO2_CASILLEROS: dict[int, str] = {
    32: "804",   # Dividendos exentos y efectos método participación
    33: "805",   # Otras rentas exentas e ingresos no objeto
    34: "812",   # Ingresos sujetos a IR único
    35: "1112",  # Ingresos sujetos al IR del RIMPE
}

# Column G is the "Valor declarado" column for Cuadro 2
A4_CUADRO2_COL = "G"
