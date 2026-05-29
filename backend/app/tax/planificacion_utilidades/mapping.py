"""Mapeos de ingesta: casilleros F-101 → claves ESF/ER y plantilla resumida.

⚠️  VALIDACIÓN HUMANA REQUERIDA
La numeración de casilleros del Formulario 101 (Sociedades, SRI Ecuador) varía
según la versión/año del formulario. Este mapeo es un DEFAULT editable, no una
verdad firme. El parser devuelve además `casilleros_leidos` (casillero→valor)
para que el profesional audite exactamente qué se leyó y ajuste este archivo o
las celdas azules del formulario antes de usar las cifras.

Cada clave de input mapea a una LISTA de casilleros que se SUMAN. Una lista
vacía significa "no hay casillero directo; completar a mano".
"""

from __future__ import annotations

# --- Formulario 101 (Sociedades) → claves ESF/ER -------------------------
# Estructura típica: 3xx activos, 4xx pasivos+patrimonio, 6xx ingresos,
# 7xx costos/gastos. Revisar contra el formulario real del contribuyente.
F101_MAP: dict[str, list[str]] = {
    # ---- ACTIVO ----
    "efectivo": ["311"],
    "inversiones": ["312", "313"],
    "cxc": ["315", "316"],          # CxC clientes (no relacionados)
    "cxcRel": ["317"],              # CxC relacionadas
    "impRec": ["322", "323"],       # crédito tributario / imp. por recuperar
    "otrasCxc": ["324"],
    "inventario": ["331", "332", "333", "334", "335"],
    "ppe": ["341", "342", "343", "344", "345", "346", "347"],
    "actImpDif": ["398"],           # activos por impuesto diferido
    # ---- PASIVO ----
    "cxp": ["411", "412"],          # CxP proveedores (no relacionados)
    "impPagar": ["421", "422"],     # obligaciones fiscales
    "benef": ["431"],               # obligaciones con IESS / beneficios
    "anticipos": ["415"],           # anticipos de clientes
    "provisiones": ["441"],
    "otrasCxp": ["419"],
    "benefPost": ["451"],           # provisiones por beneficios a empleados
    "cxpRel": ["413"],              # CxP relacionadas
    "pasImpDif": ["452"],           # pasivos por impuesto diferido
    # ---- PATRIMONIO ----
    "capital": ["471"],             # capital suscrito / asignado
    "reservas": ["481", "482"],     # reserva legal + otras reservas
    "ori": ["483"],                 # otros resultados integrales
    "resAcum": ["484", "485", "498"],  # resultados acumulados +/-
    # ---- ESTADO DE RESULTADOS ----
    "ventas": ["601", "602", "603"],   # ingresos por ventas/servicios
    "otrosIng": ["605", "606"],
    "otrosIngFin": ["608"],
    "costo": ["701", "702", "703"],    # costo de ventas/servicios
    "gAdmin": ["711", "712", "713", "714"],  # gastos admin. y ventas
    "gFin": ["721"],                   # gastos financieros
    "partTrab": ["801"],               # 15% participación trabajadores
    "irCausado": ["839"],              # impuesto a la renta causado
    "impDif": ["841"],                 # gasto/(ingreso) por impuesto diferido
    "dna": [],                         # D&A: no hay casillero único; a mano
}

# Casilleros de identificación / período (texto).
F101_RUC_LABEL = "RUC"
F101_RAZON_LABEL = "Razón Social"


# --- Plantilla "balance resumido" (.xlsx) --------------------------------
# El parser de balance resumido NO depende de coordenadas fijas: localiza la
# columna de claves/etiquetas y las columnas de año por su encabezado. Estas
# constantes definen cómo se GENERA y se LEE la plantilla en blanco.
PLANTILLA_SHEET = "Balance resumido"
PLANTILLA_KEY_HEADER = "clave"        # encabezado de la columna técnica (key)
PLANTILLA_LABEL_HEADER = "concepto"   # encabezado de la columna legible
# Las columnas de año llevan como encabezado el año (2023, 2024, 2025).
