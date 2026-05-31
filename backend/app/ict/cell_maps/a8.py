"""Cell map for COMERCIO EXTERIOR A8 (3 tablas dinámicas).

Template inspection (verified rows/cols):
  Header:   C3=razon_social, C4=ruc, C5=ejercicio_fiscal

  Tabla A: Pagos CON CDI
    Headers: rows 15-17
    Data rows: 18-21 (4 filas disponibles)
    TOTAL row: 22
    Nota: AA18:AB18, K18:L18 son merged → usar _safe_set

  Tabla B: Pagos SIN CDI
    Headers: rows 37-39
    Data rows: 40-43 (4 filas disponibles)
    TOTAL row: 44

  Tabla C: Reembolsos intermediarios
    Headers: rows 58-60
    Data rows: 61-64 (4 filas disponibles)
    TOTAL row: 65
    Nota: AK61:AL61, AK62:AL62 son merged → usar _safe_set
"""

A8_SHEET = "COMERCIO EXTERIOR A8"

A8_HEADER_MAP = {
    "C3": "razon_social",
    "C4": "ruc",
    "C5": "ejercicio_fiscal",
}

# ---------------------------------------------------------------------------
# Tabla A: Pagos al exterior CON CDI (Convenio Doble Imposición)
# Data rows 18-21 (4 filas)
# ---------------------------------------------------------------------------
A8_TABLA_A_START_ROW = 18
A8_TABLA_A_MAX_ROWS = 4  # rows 18-21

# Columnas verificadas contra plantilla (headers en rows 15-16)
A8_TABLA_A_COLS = {
    "A": "casillero_ir",             # No. Casillero declaración IR
    "B": "codigo_cuenta",            # Código de cuenta contable
    "C": "nombre_cuenta",            # Nombre de cuenta contable
    "D": "ejercicio_fiscal_tx",      # Ejercicio fiscal de la transacción
    "E": "rfc_extranjero",           # No. Identificación tributaria extranjero
    "F": "razon_social_extranjero",  # Nombres / Razón social extranjero
    "G": "pais_residencia",          # País de residencia fiscal
    "H": "certificado_residencia",   # Código/No. Certificado de Residencia
    "I": "es_parte_relacionada",     # ¿Es parte relacionada? (SI/NO)
    "J": "normativa_parte_rel",      # Normativa parte relacionada
    "K": "descripcion_transaccion",  # Descripción de la transacción (merged K:L)
    "M": "pais_cdi",                 # País con el cual se mantiene el CDI
    "N": "tipo_renta_cdi",           # Tipo de renta según CDI
    "O": "articulo_cdi",             # Artículo del CDI aplicado
    "P": "pais_servicio",            # País desde el cual se presta el servicio
    "Q": "moneda",                   # Moneda de transacción
    "R": "monto_moneda",             # Monto en moneda de pago
    "S": "monto_usd",                # Monto en dólares
    "T": "forma_pago",               # Forma de pago
    "U": "es_gravado",               # ¿Es considerado gravado? (SI/NO)
    "V": "efectuo_retencion",        # ¿Efectuó retención? (SI/NO)
    "W": "base_imponible",           # Base imponible para retención (USD)
    "X": "porcentaje_retencion",     # Porcentaje de impuesto aplicado
    "Y": "monto_retencion",          # Monto de retención efectuada (USD)
    "Z": "es_gasto_deducible",       # ¿Es gasto deducible? (SI/NO)
    "AA": "observaciones",           # Observaciones (merged AA:AB)
}

# ---------------------------------------------------------------------------
# Tabla B: Pagos al exterior SIN CDI
# Data rows 40-43 (4 filas)
# ---------------------------------------------------------------------------
A8_TABLA_B_START_ROW = 40
A8_TABLA_B_MAX_ROWS = 4  # rows 40-43

# Columnas verificadas contra plantilla (headers en rows 37-38)
A8_TABLA_B_COLS = {
    "A": "casillero_ir",             # No. Casillero declaración IR
    "B": "codigo_cuenta",            # Código de cuenta contable
    "C": "nombre_cuenta",            # Nombre de cuenta contable
    "D": "ejercicio_fiscal_tx",      # Ejercicio fiscal de la transacción
    "E": "rfc_extranjero",           # No. Identificación tributaria extranjero
    "F": "razon_social_extranjero",  # Nombres / Razón social extranjero
    "G": "pais_residencia",          # País de residencia fiscal o domicilio
    "H": "es_parte_relacionada",     # ¿Es parte relacionada? (SI/NO)
    "I": "normativa_parte_rel",      # Normativa parte relacionada
    "J": "descripcion_transaccion",  # Descripción de la transacción
    "L": "pais_servicio",            # País desde el cual se presta el servicio
    "M": "moneda",                   # Moneda de transacción
    "N": "monto_moneda",             # Monto en moneda de pago
    "O": "monto_usd",                # Monto en dólares
    "P": "es_gravado",               # ¿Es considerado gravado? (SI/NO)
    "Q": "porque_no_gravado",        # ¿Por qué no es gravado?
    "R": "efectuo_retencion",        # ¿Efectuó retención? (SI/NO)
    "S": "normativa_no_retencion",   # Normativa para no retener
    "T": "base_imponible",           # Base imponible para retención (USD)
    "U": "porcentaje_retencion",     # Porcentaje de retención
    "V": "monto_retencion",          # Monto de retención efectuada (USD)
    "W": "forma_pago",               # Forma de pago
    "X": "requiere_cert_auditor",    # ¿Requiere certificación de auditor independiente?
    "Y": "id_auditor",               # Identificación del auditor independiente
    "Z": "razon_social_auditor",     # Razón social del auditor independiente
    "AA": "pais_auditor",            # País de residencia del auditor
    "AB": "observaciones",           # Observaciones
}

# ---------------------------------------------------------------------------
# Tabla C: Pagos mediante reembolsos (intermediarios)
# Data rows 61-64 (4 filas)
# ---------------------------------------------------------------------------
A8_TABLA_C_START_ROW = 61
A8_TABLA_C_MAX_ROWS = 4  # rows 61-64

# Columnas verificadas contra plantilla (headers en rows 58-59)
A8_TABLA_C_COLS = {
    "A": "casillero_ir",                   # No. Casillero declaración IR
    "B": "codigo_cuenta",                  # Código de cuenta contable
    "C": "nombre_cuenta",                  # Nombre de cuenta contable
    "D": "intermediario_rfc",              # No. Identificación tributaria intermediario
    "E": "intermediario_razon_social",     # Nombres / Razón social intermediario
    "F": "intermediario_pais",             # País de residencia fiscal intermediario
    "G": "intermediario_parte_relacionada",# ¿Es parte relacionada? intermediario
    "H": "intermediario_normativa",        # Normativa parte relacionada intermediario
    "I": "proveedor_rfc",                  # No. Identificación tributaria proveedor
    "J": "proveedor_razon_social",         # Nombres / Razón social proveedor
    "K": "proveedor_pais",                 # País de residencia fiscal proveedor
    "L": "proveedor_parte_relacionada",    # ¿Es parte relacionada? proveedor
    "M": "proveedor_normativa",            # Normativa parte relacionada proveedor
    "N": "descripcion_transaccion",        # Descripción de la transacción
    "P": "pais_servicio",                  # País desde el cual se presta el servicio
    "Q": "aplico_cdi",                     # ¿Se aplicó un CDI? (SI/NO)
    "T": "moneda",                         # Moneda de transacción
    "U": "monto_moneda",                   # Monto en moneda de pago
    "V": "monto_usd",                      # Monto en dólares
    "W": "es_gravado",                     # ¿Es considerado gravado? (SI/NO)
    "Y": "efectuo_retencion",              # ¿Efectuó retención? (SI/NO)
    "Z": "normativa_no_retencion",         # Normativa para no retener
    "AA": "base_imponible",                # Base imponible para retención (USD)
    "AB": "porcentaje_retencion",          # Porcentaje de retención
    "AC": "monto_retencion",               # Monto de retención efectuada (USD)
    "AD": "forma_pago",                    # Forma de pago
    "AE": "requiere_cert_auditor",         # ¿Requiere certificación de auditor?
    "AF": "id_auditor",                    # Identificación del auditor
    "AG": "razon_social_auditor",          # Razón social del auditor
    "AH": "pais_auditor",                  # País de residencia del auditor
    "AK": "observaciones",                 # Observaciones (AK col; AK61:AL61 merged)
}
