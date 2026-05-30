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
# Cada clave mapea a una LISTA de casilleros que se COMBINAN. Un casillero con
# prefijo "-" se RESTA (deterioros, depreciaciones acumuladas, capital no pagado,
# pérdidas). Lista vacía = "completar a mano". El parser detecta el formato y
# elige el mapeo correcto.

# ---- Formato vigente: "Declaración de Impuesto a la Renta Sociedades" -------
# (códigos verificados contra declaración real 2024/2025 — cuadra al centavo)
# ESF: ACTIVO 311–499 · PASIVO 511–599 · PATRIMONIO 601–698.
# Estado de Resultados detallado en casilleros de 4 dígitos: ingresos 6xxx,
# costos/gastos 7xxx (7991 total costos, 7992 total gastos).
F101_MAP_DECLARACION: dict[str, list[str]] = {
    # ---- ACTIVO CORRIENTE ----
    "efectivo": ["311"],
    "inversiones": ["328", "330", "-329"],
    "cxc": ["315", "316", "-317"],                       # comerciales no relacionadas (neto)
    "cxcRel": ["312", "313", "-314", "322", "323", "-324"],  # comerciales/otras relacionadas
    "impRec": ["335", "336", "337", "338"],              # créditos tributarios (ISD/IVA/IR/otros)
    "otrasCxc": ["318", "319", "320", "321", "325", "326", "-327",
                  "356", "357", "358", "359", "360"],     # otras CxC + dividendos + prepagados
    "inventario": ["339", "340", "341", "342", "343", "344", "345", "346", "-347"],
    # ---- ACTIVO NO CORRIENTE ----
    "ppe": ["362", "363", "364", "365", "366", "367", "368", "369", "370", "371",
             "372", "373", "374", "375", "376", "377", "378", "379", "380", "381",
             "382", "383", "-384", "-385", "-386"],       # PP&E neto de depreciación
    "actImpDif": ["440", "441", "442", "443", "444", "445",
                   "432", "433", "-434", "435", "-436", "437", "438", "439"],
    # ---- PASIVO CORRIENTE ----
    "cxp": ["511", "512", "513", "514"],                 # CxP comerciales
    "impPagar": ["532"],                                 # IR por pagar del ejercicio
    "benef": ["533", "534", "535", "536"],               # part. trab. + IESS + beneficios
    "anticipos": ["545"],
    "provisiones": ["537", "538", "539", "540", "541", "542", "543", "544"],
    "otrasCxp": ["515", "516", "517", "518", "519", "520", "521", "522", "523",
                  "524", "525", "526", "527", "528", "529", "530", "531",
                  "546", "547", "548", "549"],
    # ---- PASIVO NO CORRIENTE ----
    "benefPost": ["573", "574", "575"],                  # jubilación patronal + desahucio
    "cxpRel": ["553", "554", "555", "556", "557", "558", "559", "560", "561",
                "562", "563", "564", "565", "566", "567", "568", "569", "570", "571"],
    "pasImpDif": ["572"],
    # ---- PATRIMONIO ----
    "capital": ["601", "-602", "603"],
    "reservas": ["604", "605", "606"],
    "ori": ["607", "608", "609", "610", "618", "619", "620", "621", "622",
             "623", "624", "625", "626", "627"],
    "resAcum": ["611", "-612", "613", "614", "615", "-616", "617"],
    # ---- ESTADO DE RESULTADOS (casilleros de 4 dígitos) ----
    "ventas": ["6001", "6003", "6005", "6007"],          # ventas bienes + servicios
    "otrosIng": ["6115"],                                # otros ingresos
    "otrosIngFin": ["6111", "6113"],                     # ingresos financieros
    "costo": ["7991"],                                   # total costos operacionales
    "gAdmin": ["7992"],                                  # total gastos
    "gFin": [],                                          # incluido en 7992; a mano si se separa
    "partTrab": ["803"],                                 # 15% participación trabajadores
    "irCausado": ["854"],                                # IR causado
    "impDif": ["889"],                                   # gasto/(ingreso) impuesto diferido
    "dna": [],                                           # D&A: completar a mano
}

# ---- Formato legacy (numeración anterior del 101) ---------------------------
# Se conserva como respaldo; el parser lo usa si NO detecta el formato vigente.
F101_MAP_LEGACY: dict[str, list[str]] = {
    "efectivo": ["311"],
    "inversiones": ["312", "313"],
    "cxc": ["315", "316"],
    "cxcRel": ["317"],
    "impRec": ["322", "323"],
    "otrasCxc": ["324"],
    "inventario": ["331", "332", "333", "334", "335"],
    "ppe": ["341", "342", "343", "344", "345", "346", "347"],
    "actImpDif": ["398"],
    "cxp": ["411", "412"],
    "impPagar": ["421", "422"],
    "benef": ["431"],
    "anticipos": ["415"],
    "provisiones": ["441"],
    "otrasCxp": ["419"],
    "benefPost": ["451"],
    "cxpRel": ["413"],
    "pasImpDif": ["452"],
    "capital": ["471"],
    "reservas": ["481", "482"],
    "ori": ["483"],
    "resAcum": ["484", "485", "498"],
    "ventas": ["601", "602", "603"],
    "otrosIng": ["605", "606"],
    "otrosIngFin": ["608"],
    "costo": ["701", "702", "703"],
    "gAdmin": ["711", "712", "713", "714"],
    "gFin": ["721"],
    "partTrab": ["801"],
    "irCausado": ["839"],
    "impDif": ["841"],
    "dna": [],
}

# Por defecto se usa el formato vigente (Declaración de Renta Sociedades).
F101_MAP: dict[str, list[str]] = F101_MAP_DECLARACION

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
