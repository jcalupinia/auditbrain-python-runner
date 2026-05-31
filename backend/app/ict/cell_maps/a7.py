"""Cell map for CRÉDITO TRIBUTARIO A7 sheet (2 matrices multi-año).

Template inspection (verified rows):
  Header:   C3=razon_social, C4=ruc, C5=ejercicio_fiscal

  Matriz 1: Crédito IR por año generador (rows 15-18, TOTALES row 19)
    A15=2022, A16=2023, A17=2024, A18=(blank extra row)
    Columns:
      D  = Valor del crédito tributario generado {1}
      E  = Devuelto SRI Año 2022 {2}
      F  = Devuelto SRI Año 2023 {3}
      G  = Devuelto SRI Año 2024 {4}
      H  = Total devuelto (fórmula =SUM(E:G)) {5}
      I  = No. Resolución devolución
      J  = Monto aceptado en resolución
      K  = Monto rechazado en resolución
      L  = Se registró monto rechazado como costo/gasto
      M  = Normativa aplicada
      N  = Crédito utilizado directamente Año 2022 {6}
      O  = Crédito utilizado directamente Año 2023 {7}
      P  = Crédito utilizado directamente Año 2024 {8}
      Q  = Total utilizado (fórmula =SUM(N:P)) {9}
      R  = Valor no recuperable {10}
      S  = Saldo pendiente (fórmula) {11}
      T  = Observaciones

  Matriz 2: ISD por año (rows 28-32, TOTALES row 33)
    A28=2021, A29=2022, A30=2023, A31=2024, A32=2025
    Columns:
      B  = Valor total ISD pagado en ejercicio {1}
      C  = ISD utilizado como costo/gasto Año 2021 {2}
      D  = ISD utilizado como costo/gasto Año 2022 {3}
      E  = ISD utilizado como costo/gasto Año 2023 {4}
      F  = ISD utilizado como costo/gasto Año 2024 {5}
      G  = ISD utilizado como costo/gasto Año 2025 {6}
      H  = Subtotal después costo/gasto (fórmula) {7}
      I  = ISD como crédito Año 2021 {8}
      J  = ISD como crédito Año 2022 {9}
      K  = ISD como crédito Año 2023 {10}
      L  = ISD como crédito Año 2024 {11}
      M  = ISD como crédito Año 2025 {12}
      N  = Subtotal después crédito (fórmula) {13}
      O  = ISD devuelto SRI Año 2021 {14}
      P  = ISD devuelto SRI Año 2022 {15}
      Q  = ISD devuelto SRI Año 2023 {16}
      R  = ISD devuelto SRI Año 2024 {17}
      S  = ISD devuelto SRI Año 2025 {18}
      T  = ISD no sujeto a devolución {19}
      U  = Saldo pendiente (fórmula) {20}
      V  = Observaciones
"""

A7_SHEET = "CRÉDITO TRIBUTARIO A7"

A7_HEADER_MAP = {
    "C3": "razon_social",
    "C4": "ruc",
    "C5": "ejercicio_fiscal",
}

# ---------------------------------------------------------------------------
# Matriz 1: Crédito IR por año generador
# ---------------------------------------------------------------------------
A7_MATRIZ_IR = {
    "years": [2022, 2023, 2024],
    "rows": {
        2022: 15,
        2023: 16,
        2024: 17,
    },
    "columns": {
        # Input columns (filled by filler from anexo_data)
        "valor_generado": "D",          # {1} Crédito generado (from F-101 casillero 850/851)
        "devuelto_2022": "E",           # {2} Devuelto SRI en año 2022
        "devuelto_2023": "F",           # {3} Devuelto SRI en año 2023
        "devuelto_2024": "G",           # {4} Devuelto SRI en año 2024
        # H = formula =SUM(E:G) — NOT touched
        "no_resolucion": "I",           # No. Resolución devolución
        "monto_aceptado": "J",          # Monto aceptado en resolución
        "monto_rechazado": "K",         # Monto rechazado en resolución
        "registrado_costo": "L",        # Se registró como costo/gasto (SI/NO)
        "normativa": "M",               # Normativa aplicada
        "utilizado_2022": "N",          # {6} Crédito usado directamente año 2022
        "utilizado_2023": "O",          # {7} Crédito usado directamente año 2023
        "utilizado_2024": "P",          # {8} Crédito usado directamente año 2024
        # Q = formula =SUM(N:P) — NOT touched
        "no_recuperable": "R",          # {10} Valor no recuperable
        # S = formula saldo — NOT touched
        "observaciones": "T",           # Observaciones
    },
}

# ---------------------------------------------------------------------------
# Matriz 2: ISD por año de pago
# ---------------------------------------------------------------------------
A7_MATRIZ_ISD = {
    "years": [2021, 2022, 2023, 2024, 2025],
    "rows": {
        2021: 28,
        2022: 29,
        2023: 30,
        2024: 31,
        2025: 32,
    },
    "columns": {
        # Input columns (filled by filler from anexo_data)
        "total_isd_pagado": "B",        # {1} Valor total ISD pagado en ejercicio
        "costo_gasto_2021": "C",        # {2} Usado como costo/gasto año 2021
        "costo_gasto_2022": "D",        # {3} Usado como costo/gasto año 2022
        "costo_gasto_2023": "E",        # {4} Usado como costo/gasto año 2023
        "costo_gasto_2024": "F",        # {5} Usado como costo/gasto año 2024
        "costo_gasto_2025": "G",        # {6} Usado como costo/gasto año 2025
        # H = formula subtotal — NOT touched
        "credito_2021": "I",            # {8} ISD como crédito año 2021
        "credito_2022": "J",            # {9} ISD como crédito año 2022
        "credito_2023": "K",            # {10} ISD como crédito año 2023
        "credito_2024": "L",            # {11} ISD como crédito año 2024
        "credito_2025": "M",            # {12} ISD como crédito año 2025
        # N = formula subtotal — NOT touched
        "devuelto_2021": "O",           # {14} Devuelto SRI año 2021
        "devuelto_2022": "P",           # {15} Devuelto SRI año 2022
        "devuelto_2023": "Q",           # {16} Devuelto SRI año 2023
        "devuelto_2024": "R",           # {17} Devuelto SRI año 2024
        "devuelto_2025": "S",           # {18} Devuelto SRI año 2025
        "no_sujeto_devolucion": "T",    # {19} ISD no sujeto a devolución
        # U = formula saldo — NOT touched
        "observaciones": "V",           # Observaciones
    },
}
