"""Espejo en Python de los esquemas ESF/ER definidos en frontend/src/tax/seed.js.

Esta es la frontera JS↔Python: la duplicación es deliberada y necesaria. Si
cambian los esquemas en seed.js, actualizar aquí también (los nombres de clave
DEBEN coincidir 1:1 con seed.js para que la ingesta y la exportación encajen).
"""

from __future__ import annotations

# Estado de Situación Financiera.
#   ("sec", label)                  -> encabezado de sección
#   ("in", key, label)              -> input editable (el parser debe poblarlo)
#   ("sub"|"tot", key, label, *ops) -> línea calculada (fórmula en el exporter)
ESF_SCHEMA: list[tuple] = [
    ("sec", "ACTIVO CORRIENTE"),
    ("in", "efectivo", "Efectivo y equivalentes"),
    ("in", "inversiones", "Inversiones"),
    ("in", "cxc", "Cuentas por cobrar"),
    ("in", "cxcRel", "CxC relacionadas"),
    ("in", "impRec", "Impuestos por recuperar"),
    ("in", "otrasCxc", "Otras CxC"),
    ("in", "inventario", "Inventario"),
    ("sub", "totalAC", "Total activo corriente"),
    ("sec", "ACTIVO NO CORRIENTE"),
    ("in", "ppe", "Propiedad, planta y equipo"),
    ("in", "actImpDif", "Activos imp. diferidos"),
    ("sub", "totalANC", "Total activo no corriente"),
    ("tot", "totalActivo", "TOTAL ACTIVO"),
    ("sec", "PASIVO CORRIENTE"),
    ("in", "cxp", "Cuentas por pagar"),
    ("in", "impPagar", "Impuestos por pagar"),
    ("in", "benef", "Beneficios sociales"),
    ("in", "anticipos", "Anticipos clientes"),
    ("in", "provisiones", "Provisiones"),
    ("in", "otrasCxp", "Otras CxP"),
    ("sub", "totalPC", "Total pasivo corriente"),
    ("sec", "PASIVO NO CORRIENTE"),
    ("in", "benefPost", "Beneficios post-empleo"),
    ("in", "cxpRel", "CxP relacionadas"),
    ("in", "pasImpDif", "Pasivos imp. diferidos"),
    ("sub", "totalPNC", "Total pasivo no corriente"),
    ("tot", "totalPasivo", "TOTAL PASIVO"),
    ("sec", "PATRIMONIO"),
    ("in", "capital", "Capital"),
    ("in", "reservas", "Reservas"),
    ("in", "ori", "Otros result. integrales"),
    ("in", "resAcum", "Resultados acumulados"),
    ("tot", "totalPat", "TOTAL PATRIMONIO"),
]

ER_SCHEMA: list[tuple] = [
    ("in", "ventas", "Ventas / ingresos ordinarios"),
    ("in", "otrosIng", "Otros ingresos"),
    ("in", "otrosIngFin", "Otros ingresos financieros"),
    ("in", "costo", "(−) Costo de servicios"),
    ("tot", "ub", "UTILIDAD BRUTA"),
    ("in", "gAdmin", "(−) Gastos admin. y ventas"),
    ("tot", "ebit", "UTILIDAD OPERATIVA (EBIT)"),
    ("in", "gFin", "(−) Gastos financieros"),
    ("sub", "uai", "Utilidad antes de impuestos"),
    ("in", "partTrab", "(−) Participación trabajadores"),
    ("in", "irCausado", "(−) Impuesto renta causado"),
    ("in", "impDif", "(−) Impuesto diferido"),
    ("tot", "neta", "RESULTADO NETO"),
]


def _input_keys(schema: list[tuple]) -> list[str]:
    return [row[1] for row in schema if row[0] == "in"]


ESF_INPUT_KEYS: list[str] = _input_keys(ESF_SCHEMA)
ER_INPUT_KEYS: list[str] = _input_keys(ER_SCHEMA)

# Todas las claves que el parser debe poblar (orden estable). Incluye 'dna'
# (depreciación/amortización para EBITDA), que el ER no desglosa.
INPUT_KEYS: list[str] = ESF_INPUT_KEYS + ER_INPUT_KEYS + ["dna"]

# Etiqueta legible por clave (para plantilla y warnings).
LABELS: dict[str, str] = {
    row[1]: row[2]
    for row in (*ESF_SCHEMA, *ER_SCHEMA)
    if row[0] in ("in", "sub", "tot")
}
LABELS.setdefault("dna", "Depreciación y amortización")

# Años por defecto (deben coincidir con ANIOS en seed.js).
ANIOS: list[int] = [2023, 2024, 2025]


def empty_data() -> dict[str, list[float]]:
    """Estructura en blanco: cada clave con 3 años en 0."""
    return {k: [0.0, 0.0, 0.0] for k in INPUT_KEYS}
