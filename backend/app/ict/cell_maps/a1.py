"""Cell map para MAPEO A1 — Informe de Cumplimiento Tributario 2025.

Contiene TODOS los casilleros del F-101 SRI Ecuador 2025 que
corresponden a:

  - Estado de Situación Financiera (Activos 311-499, Pasivos 511-599)
  - Patrimonio (601-699)
  - Estado de Resultados (Ingresos 6001-6999/1005, Costos/Gastos 7001-7999)

El A1 cruza cada casillero declarado en el F-101 contra el saldo
contable agregado del Balance Mapeado del cliente. La fórmula G
calcula =SUM(saldos_balance) - valor_declarado para evidenciar
diferencias.

REGLA SUPREMA: A1_CASILLEROS_ORDERED debe contener TODOS los casilleros
del balance (rango 311-699) del catálogo OFICIAL F101_CASILLERO_NAMES.
NO se permite tener listas hardcoded en paralelo — eso causa "saldos
de línea" (casilleros que el F-101 declara pero el A1 no muestra).

Para garantizarlo, la lista se DERIVA en runtime del catálogo oficial.
El bloque LEGACY abajo (lista hardcoded) se conserva solo como
referencia documental del orden esperado por los TOTALS hardcodeados
en a1_mapeo.py. La fuente de verdad es BALANCE_RANGE filtrado del
catálogo.
"""

from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES

A1_SHEET = "MAPEO DE LA DECLARACIÓN A1"
A1_FIRST_DATA_ROW = 13

A1_HEADER_MAP = {
    "C3": "razon_social",
    "C4": "ruc",
    "C5": "ejercicio_fiscal",
    "C6": "numero_adhesivo",
}

# ====================================================================
# A1_CASILLEROS_ORDERED — DERIVADO DEL CATÁLOGO OFICIAL F-101
# ====================================================================
# Antes (PRE-fix-2026-06-04): lista hardcoded de 193 casilleros que
# perdía 164 casilleros del balance oficial (ej: 490, 491, 593, etc.).
# Causaba el bug "saldos de línea": el F-101 declaraba valor pero el
# A1 nunca los mostraba.
#
# Ahora: se genera dinámicamente filtrando el catálogo OFICIAL por el
# rango del balance (311-699). Garantiza TODOS los 267 casilleros.
def _en_rango_a1(cas: str) -> bool:
    """¿Pertenece este cas al universo del A1?

    REGLA SUPREMA (CLAUDE.md / pedido cliente 2026-06-04):
    "TODOS los casilleros del formulario 101 que se encuentran en la
     pestaña de datos f-101 deben trasladarse a la pestaña A1".

    Por tanto: A1 cubre TODOS los casilleros del catálogo OFICIAL F-101
    (los 888 publicados por SRI). Esto incluye:
      - Estado de Situación Financiera: 311-699
      - Estado de Resultados (subtotales): 1005, 1025, 1030, 1040, 1045, etc.
      - Estado de Resultados (detalle ingresos): 6001-6999
      - Estado de Resultados (detalle costos/gastos): 7001-7999
      - Conciliación tributaria: 800-849 (utilidad, gastos no deducibles)
      - Anticipo IR + retenciones: 850-899
      - Cálculo IR: 900-999
      - Anexos especiales y otros: 1100+, 5xxx, etc.

    El único filtro es que el cas sea numérico. Cas con valor 0 en F-101
    aparecen igualmente en A1 (la regla del proyecto exige "no saldos de
    línea" — preferimos mostrar 0 a omitir un cas que el SRI declara).
    """
    return cas.isdigit()


def _a1_sort_key(cas: str) -> tuple[int, int]:
    """Ordena los cas del A1 con jerarquía:
       grupo 1 = balance 311-699
       grupo 2 = detalle ingresos 6001-6998 (sin TOTAL 6999)
       grupo 3 = subtotales ingresos 1005, 1045
       grupo 4 = TOTAL ingresos 6999
       grupo 5 = detalle costos/gastos 7001-7990
       grupo 6 = subtotales costos/gastos 7991, 7992, 7999
       grupo 7 = otros subtotales del estado de resultados (1025, 1030, ...)
       grupo 8 = conciliación tributaria + anticipo + cálculo IR (800-999)
       grupo 9 = anexos especiales + resto (1100+, 5xxx, etc.)

    Garantiza que el filler procese DETALLE antes que TOTAL (necesario
    porque las fórmulas de TOTAL son SUM(detail_range)) y que los
    casilleros nuevos del catálogo OFICIAL (sección conciliación, IR,
    anexos especiales) aparezcan AL FINAL, después de la cuadratura
    contable, para no romper el flujo visual del A1 tradicional.
    """
    if not cas.isdigit():
        return (99, 0)
    n = int(cas)
    if 311 <= n <= 699:
        return (1, n)
    if 6001 <= n <= 6998:
        return (2, n)
    if n in (1005, 1045):
        return (3, n)
    if n == 6999:
        return (4, n)
    if 7001 <= n <= 7990:
        return (5, n)
    if n in (7991, 7992, 7999):
        return (6, n)
    if 1001 <= n <= 1099:        # otros subtotales (1025, 1030, 1040, etc.)
        return (7, n)
    if 800 <= n <= 999:          # conciliación + anticipo + cálculo IR
        return (8, n)
    return (9, n)                # anexos especiales (1100+, 5xxx, etc.)


A1_CASILLEROS_ORDERED: list[tuple[str, str]] = [
    (cas, F101_CASILLERO_NAMES[cas])
    for cas in sorted(F101_CASILLERO_NAMES.keys(), key=_a1_sort_key)
    if _en_rango_a1(cas)
]


# ====================================================================
# A1_CASILLEROS_LEGACY_PARCIAL — referencia documental del orden vivo
# ====================================================================
# Lista hardcoded de los 193 casilleros que el A1 ya cubría desde
# 2025. Se conserva sólo para referencia / debugging. El A1 USA
# A1_CASILLEROS_ORDERED arriba.
A1_CASILLEROS_LEGACY_PARCIAL: list[tuple[str, str]] = [
    # ============================================================
    # ACTIVOS CORRIENTES (311-361)
    # ============================================================
    ("311", "EFECTIVO Y EQUIVALENTES AL EFECTIVO"),
    ("312", "CUENTAS Y DOCUMENTOS POR COBRAR COMERCIALES CORRIENTES - RELACIONADAS LOCALES"),
    ("313", "CUENTAS Y DOCUMENTOS POR COBRAR COMERCIALES CORRIENTES - RELACIONADAS DEL EXTERIOR"),
    ("314", "(-) Deterioro acumulado del valor de cuentas y documentos por cobrar comerciales (Relacionadas)"),
    ("315", "CUENTAS Y DOCUMENTOS POR COBRAR COMERCIALES CORRIENTES - NO RELACIONADAS LOCALES"),
    ("316", "CUENTAS Y DOCUMENTOS POR COBRAR COMERCIALES CORRIENTES - NO RELACIONADAS DEL EXTERIOR"),
    ("317", "(-) Deterioro acumulado del valor de cuentas y documentos por cobrar (No Relacionadas)"),
    ("318", "OTRAS CUENTAS Y DOCUMENTOS POR COBRAR - A ACCIONISTAS Y SOCIOS LOCALES"),
    ("319", "OTRAS CUENTAS Y DOCUMENTOS POR COBRAR - A ACCIONISTAS Y SOCIOS DEL EXTERIOR"),
    ("320", "DIVIDENDOS POR COBRAR EN EFECTIVO"),
    ("321", "DIVIDENDOS POR COBRAR EN ACTIVOS DIFERENTES DEL EFECTIVO"),
    ("322", "OTRAS CUENTAS Y DOCUMENTOS POR COBRAR - OTRAS RELACIONADAS LOCALES"),
    ("323", "OTRAS CUENTAS Y DOCUMENTOS POR COBRAR - OTRAS RELACIONADAS DEL EXTERIOR"),
    ("324", "(-) Deterioro acumulado otras cuentas por cobrar (Relacionadas)"),
    ("325", "OTRAS CUENTAS Y DOCUMENTOS POR COBRAR - OTRAS NO RELACIONADAS LOCALES"),
    ("326", "OTRAS CUENTAS Y DOCUMENTOS POR COBRAR - OTRAS NO RELACIONADAS DEL EXTERIOR"),
    ("327", "(-) Deterioro acumulado otras cuentas por cobrar (No Relacionadas)"),
    ("335", "ACTIVOS POR IMPUESTOS CORRIENTES - Crédito Tributario ISD"),
    ("336", "ACTIVOS POR IMPUESTOS CORRIENTES - Crédito Tributario IVA"),
    ("337", "ACTIVOS POR IMPUESTOS CORRIENTES - Crédito Tributario Impuesto a la Renta"),
    ("338", "ACTIVOS POR IMPUESTOS CORRIENTES - Otros"),
    ("339", "INVENTARIOS - Mercaderías en tránsito"),
    ("340", "INVENTARIOS - Materia prima (no para la construcción)"),
    ("341", "INVENTARIOS - Productos en proceso"),
    ("342", "INVENTARIOS - Productos terminados y mercaderías en almacén"),
    ("343", "INVENTARIOS - Suministros, herramientas, repuestos y materiales"),
    ("344", "INVENTARIOS - Materia prima, suministros y materiales para la construcción"),
    ("345", "INVENTARIOS - Obras/inmuebles en construcción para la venta"),
    ("346", "INVENTARIOS - Obras/inmuebles terminados para la venta"),
    ("347", "(-) Deterioro acumulado del valor de inventarios"),
    ("356", "GASTOS PAGADOS POR ANTICIPADO - Propaganda y publicidad prepagada"),
    ("357", "GASTOS PAGADOS POR ANTICIPADO - Arrendamientos operativos prepagados"),
    ("358", "GASTOS PAGADOS POR ANTICIPADO - Primas de seguro prepagadas"),
    ("359", "GASTOS PAGADOS POR ANTICIPADO - Otros prepagados"),
    ("360", "OTROS ACTIVOS CORRIENTES"),
    ("361", "TOTAL ACTIVOS CORRIENTES"),

    # ============================================================
    # ACTIVOS NO CORRIENTES (362-449)
    # ============================================================
    ("362", "PROPIEDADES, PLANTA Y EQUIPO - Terrenos (Costo histórico)"),
    ("363", "PROPIEDADES, PLANTA Y EQUIPO - Terrenos (Ajuste por reexpresiones)"),
    ("364", "PROPIEDADES, PLANTA Y EQUIPO - Edificios y otros inmuebles (Costo histórico)"),
    ("365", "PROPIEDADES, PLANTA Y EQUIPO - Edificios (Ajuste por reexpresiones)"),
    ("368", "PROPIEDADES, PLANTA Y EQUIPO - Maquinaria, equipo, instalaciones (Costo histórico)"),
    ("369", "PROPIEDADES, PLANTA Y EQUIPO - Maquinaria (Ajuste por reexpresiones)"),
    ("372", "PROPIEDADES, PLANTA Y EQUIPO - Construcciones en curso y otros activos en tránsito"),
    ("373", "PROPIEDADES, PLANTA Y EQUIPO - Muebles y enseres"),
    ("374", "PROPIEDADES, PLANTA Y EQUIPO - Equipo de computación"),
    ("375", "PROPIEDADES, PLANTA Y EQUIPO - Vehículos, equipo de transporte"),
    ("383", "PROPIEDADES, PLANTA Y EQUIPO - Otras propiedades, planta y equipo"),
    ("384", "(-) DEPRECIACIÓN ACUMULADA DE PROPIEDADES, PLANTA Y EQUIPO (Costo histórico)"),
    ("385", "(-) DEPRECIACIÓN ACUMULADA (Ajuste por reexpresiones)"),
    ("386", "(-) Deterioro acumulado de propiedades, planta y equipo"),
    ("387", "ACTIVOS INTANGIBLES - Plusvalía o goodwill"),
    ("388", "ACTIVOS INTANGIBLES - Marcas, patentes, licencias y similares"),
    ("392", "(-) Amortización acumulada de activos intangibles"),
    ("420", "CUENTAS POR COBRAR COMERCIALES NO CORRIENTES - RELACIONADAS LOCALES"),
    ("423", "CUENTAS POR COBRAR COMERCIALES NO CORRIENTES - NO RELACIONADAS LOCALES"),
    ("432", "OTRAS CUENTAS POR COBRAR NO CORRIENTES - NO RELACIONADAS LOCALES"),
    ("433", "OTRAS CUENTAS POR COBRAR NO CORRIENTES - NO RELACIONADAS DEL EXTERIOR"),
    ("440", "ACTIVOS POR IMPUESTOS DIFERIDOS - Por diferencias temporarias"),
    ("441", "ACTIVOS POR IMPUESTOS DIFERIDOS - Por pérdidas tributarias"),
    ("445", "OTROS ACTIVOS NO CORRIENTES"),
    ("449", "TOTAL ACTIVOS NO CORRIENTES"),
    ("499", "TOTAL DEL ACTIVO"),

    # ============================================================
    # PASIVOS CORRIENTES (511-550)
    # ============================================================
    ("511", "CUENTAS Y DOCUMENTOS POR PAGAR COMERCIALES CORRIENTES - RELACIONADAS LOCALES"),
    ("512", "CUENTAS Y DOCUMENTOS POR PAGAR COMERCIALES CORRIENTES - RELACIONADAS DEL EXTERIOR"),
    ("513", "CUENTAS Y DOCUMENTOS POR PAGAR COMERCIALES CORRIENTES - NO RELACIONADAS LOCALES"),
    ("514", "CUENTAS Y DOCUMENTOS POR PAGAR COMERCIALES CORRIENTES - NO RELACIONADAS DEL EXTERIOR"),
    ("519", "OTRAS CUENTAS POR PAGAR CORRIENTES - OTRAS RELACIONADAS LOCALES"),
    ("521", "OTRAS CUENTAS POR PAGAR CORRIENTES - OTRAS NO RELACIONADAS LOCALES"),
    ("525", "OBLIGACIONES CON INSTITUCIONES FINANCIERAS CORRIENTES - NO RELACIONADAS LOCALES"),
    ("531", "PORCIÓN CORRIENTE ARRENDAMIENTOS FINANCIEROS POR PAGAR"),
    ("532", "IMPUESTO A LA RENTA POR PAGAR DEL EJERCICIO"),
    ("533", "PARTICIPACIÓN TRABAJADORES POR PAGAR DEL EJERCICIO"),
    ("534", "OBLIGACIONES CON EL IESS"),
    ("535", "JUBILACIÓN PATRONAL (Corriente)"),
    ("536", "OTROS PASIVOS CORRIENTES POR BENEFICIOS A EMPLEADOS"),
    ("544", "PROVISIONES CORRIENTES - Otras"),
    ("545", "PASIVOS POR INGRESOS DIFERIDOS - Anticipos de clientes"),
    ("549", "OTROS PASIVOS CORRIENTES"),
    ("550", "TOTAL PASIVOS CORRIENTES"),

    # ============================================================
    # PASIVOS NO CORRIENTES (553-599)
    # ============================================================
    ("555", "CUENTAS Y DOCUMENTOS POR PAGAR COMERCIALES NO CORRIENTES - NO RELACIONADAS LOCALES"),
    ("565", "OBLIGACIONES CON INSTITUCIONES FINANCIERAS NO CORRIENTES - NO RELACIONADAS LOCALES"),
    ("572", "PASIVO POR IMPUESTO A LA RENTA DIFERIDO"),
    ("573", "JUBILACIÓN PATRONAL (No Corriente)"),
    ("574", "DESAHUCIO"),
    ("584", "PASIVOS POR INGRESOS DIFERIDOS - Anticipos clientes (No Corriente)"),
    ("588", "OTROS PASIVOS NO CORRIENTES"),
    ("589", "TOTAL PASIVOS NO CORRIENTES"),
    ("599", "TOTAL DEL PASIVO"),

    # ============================================================
    # PATRIMONIO (601-699)
    # ============================================================
    ("601", "CAPITAL SUSCRITO Y/O ASIGNADO"),
    ("602", "(-) Capital suscrito no pagado, acciones en tesorería"),
    ("603", "APORTES DE SOCIOS PARA FUTURA CAPITALIZACIÓN"),
    ("604", "RESERVA LEGAL"),
    ("605", "RESERVA FACULTATIVA"),
    ("606", "OTRAS RESERVAS"),
    ("607", "RESULTADOS ACUMULADOS - Reserva de capital"),
    ("611", "UTILIDADES ACUMULADAS DE EJERCICIOS ANTERIORES"),
    ("612", "(-) PÉRDIDAS ACUMULADAS DE EJERCICIOS ANTERIORES"),
    ("614", "RESULTADOS ACUMULADOS POR ADOPCIÓN POR PRIMERA VEZ DE LAS NIIF"),
    ("615", "UTILIDAD DEL EJERCICIO"),
    ("616", "(-) PÉRDIDA DEL EJERCICIO"),
    ("623", "GANANCIAS Y PÉRDIDAS ACTUARIALES ACUMULADAS"),
    ("698", "TOTAL DEL PATRIMONIO"),
    ("699", "TOTAL PASIVO Y PATRIMONIO"),

    # ============================================================
    # INGRESOS (6001-6999, 1005)
    # ============================================================
    ("6001", "VENTAS LOCALES DE BIENES gravadas con tarifa diferente de 0% IVA"),
    ("6003", "VENTAS LOCALES DE BIENES gravadas con tarifa 0% o exentas de IVA"),
    ("6005", "PRESTACIONES LOCALES DE SERVICIOS gravadas con tarifa diferente de 0%"),
    ("6007", "PRESTACIONES LOCALES DE SERVICIOS gravadas con tarifa 0% o exentas"),
    ("6009", "EXPORTACIONES NETAS de bienes"),
    ("6011", "EXPORTACIONES NETAS de servicios"),
    ("6013", "PRESTACIÓN DE SERVICIOS DE CONSTRUCCIÓN"),
    ("6015", "INGRESOS POR COMISIONES O SIMILARES (relaciones de agencia)"),
    ("6017", "INGRESOS POR ARRENDAMIENTOS OPERATIVOS"),
    ("1005", "TOTAL INGRESOS DE ACTIVIDADES ORDINARIAS"),
    ("6033", "GANANCIAS NETAS POR DIFERENCIAS DE CAMBIOS"),
    ("6035", "UTILIDAD EN VENTA DE PROPIEDADES, PLANTA Y EQUIPO"),
    ("6041", "REVERSIONES DE DETERIORO de activos financieros"),
    ("6043", "REVERSIONES DE DETERIORO de inventarios"),
    ("6115", "INTERESES FINANCIEROS NO RELACIONADAS LOCAL"),
    ("6133", "OTROS INGRESOS FINANCIEROS"),
    ("1045", "TOTAL INGRESOS NO OPERACIONALES"),
    ("6999", "TOTAL INGRESOS"),
    ("6150", "INGRESOS NO OBJETO DE IMPUESTO A LA RENTA"),
    ("6152", "INGRESOS BRUTOS TOTALES SEGÚN CONTABILIDAD"),

    # ============================================================
    # COSTOS Y GASTOS (7001-7999)
    # ============================================================
    # Costo de Ventas
    ("7001", "INVENTARIO INICIAL DE BIENES NO PRODUCIDOS POR EL SUJETO PASIVO"),
    ("7004", "COMPRAS NETAS LOCALES DE BIENES NO PRODUCIDOS POR EL SUJETO PASIVO"),
    ("7007", "IMPORTACIONES DE BIENES NO PRODUCIDOS POR EL SUJETO PASIVO"),
    ("7010", "(-) INVENTARIO FINAL DE BIENES NO PRODUCIDOS POR EL SUJETO PASIVO"),
    ("7013", "INVENTARIO INICIAL DE MATERIA PRIMA"),
    ("7016", "COMPRAS NETAS LOCALES DE MATERIA PRIMA"),
    ("7019", "IMPORTACIONES DE MATERIA PRIMA"),
    ("7022", "(-) INVENTARIO FINAL DE MATERIA PRIMA"),
    ("7025", "INVENTARIO INICIAL DE PRODUCTOS EN PROCESO"),
    ("7028", "(-) INVENTARIO FINAL DE PRODUCTOS EN PROCESO"),
    ("7031", "INVENTARIO INICIAL PRODUCTOS TERMINADOS"),
    ("7034", "(-) INVENTARIO FINAL DE PRODUCTOS TERMINADOS"),
    ("7037", "AJUSTES (+/-) en Costo de Ventas"),
    # Beneficios a Empleados
    ("7040", "SUELDOS, SALARIOS Y REMUNERACIONES QUE CONSTITUYEN MATERIA GRAVADA IESS (Costo)"),
    ("7041", "SUELDOS, SALARIOS Y REMUNERACIONES QUE CONSTITUYEN MATERIA GRAVADA IESS (Gasto)"),
    ("7042", "SUELDOS - Valor no deducible"),
    ("7043", "BENEFICIOS SOCIALES, INDEMNIZACIONES (Costo)"),
    ("7044", "BENEFICIOS SOCIALES, INDEMNIZACIONES (Gasto)"),
    ("7045", "BENEFICIOS SOCIALES - Valor no deducible"),
    ("7046", "APORTE A LA SEGURIDAD SOCIAL incluye fondo de reserva (Costo)"),
    ("7047", "APORTE A LA SEGURIDAD SOCIAL (Gasto)"),
    ("7048", "APORTE IESS - Valor no deducible"),
    ("7049", "HONORARIOS PROFESIONALES Y DIETAS (Costo)"),
    ("7050", "HONORARIOS PROFESIONALES Y DIETAS (Gasto)"),
    ("7055", "JUBILACIÓN PATRONAL (Costo)"),
    ("7056", "JUBILACIÓN PATRONAL (Gasto)"),
    ("7057", "JUBILACIÓN PATRONAL - Valor no deducible"),
    ("7058", "DESAHUCIO (Costo)"),
    ("7059", "DESAHUCIO (Gasto)"),
    ("7060", "DESAHUCIO - Valor no deducible"),
    ("7061", "OTROS GASTOS DE PERSONAL (Costo)"),
    ("7062", "OTROS GASTOS DE PERSONAL (Gasto)"),
    ("7063", "OTROS GASTOS DE PERSONAL - Valor no deducible"),
    # Depreciaciones
    ("7067", "DEPRECIACIÓN PROPIEDADES, PLANTA Y EQUIPO NO ACELERADA (Costo)"),
    ("7068", "DEPRECIACIÓN PROPIEDADES, PLANTA Y EQUIPO NO ACELERADA (Gasto)"),
    ("7069", "DEPRECIACIÓN - Valor no deducible"),
    # Amortizaciones
    ("7095", "AMORTIZACIÓN DE ACTIVOS INTANGIBLES (Gasto)"),
    ("7654", "AMORTIZACIÓN DE DERECHOS DE USO POR ACTIVOS ARRENDADOS"),
    # Pérdidas por Deterioro
    ("7113", "DETERIORO DE ACTIVOS FINANCIEROS (Gasto)"),
    ("7114", "DETERIORO ACTIVOS FINANCIEROS - Valor no deducible"),
    ("7116", "DETERIORO DE INVENTARIOS (Gasto)"),
    # Otros Gastos
    ("7173", "PROMOCIÓN Y PUBLICIDAD (Gasto)"),
    ("7176", "TRANSPORTE (Gasto)"),
    ("7178", "CONSUMO DE COMBUSTIBLES Y LUBRICANTES (Costo)"),
    ("7179", "CONSUMO DE COMBUSTIBLES Y LUBRICANTES (Gasto)"),
    ("7182", "GASTOS DE VIAJE (Gasto)"),
    ("7185", "GASTOS DE GESTIÓN (Gasto)"),
    ("7188", "ARRENDAMIENTOS OPERATIVOS (Gasto)"),
    ("7190", "SUMINISTROS, HERRAMIENTAS, MATERIALES Y REPUESTOS (Costo)"),
    ("7191", "SUMINISTROS, HERRAMIENTAS, MATERIALES Y REPUESTOS (Gasto)"),
    ("7192", "SUMINISTROS - Valor no deducible"),
    ("7196", "MANTENIMIENTO Y REPARACIONES (Costo)"),
    ("7197", "MANTENIMIENTO Y REPARACIONES (Gasto)"),
    ("7203", "SEGUROS Y REASEGUROS - PRIMAS Y CESIONES (Gasto)"),
    ("7208", "IMPUESTOS, CONTRIBUCIONES Y OTROS (Costo)"),
    ("7209", "IMPUESTOS, CONTRIBUCIONES Y OTROS (Gasto)"),
    ("7210", "IMPUESTOS - Valor no deducible"),
    # Regalías y servicios técnicos
    ("7229", "OPERACIONES DE REGALÍAS NO RELACIONADAS LOCAL (Costo)"),
    ("7230", "OPERACIONES DE REGALÍAS NO RELACIONADAS LOCAL (Gasto)"),
    ("7233", "OPERACIONES DE REGALÍAS NO RELACIONADAS EXTERIOR (Gasto)"),
    # Servicios públicos
    ("7241", "SERVICIOS PÚBLICOS (Costo)"),
    ("7242", "SERVICIOS PÚBLICOS (Gasto)"),
    ("7247", "OTROS - GASTOS GENERALES (Costo)"),
    ("7248", "OTROS - GASTOS GENERALES (Gasto)"),
    ("7249", "OTROS - Valor no deducible"),
    # Gastos Financieros
    ("7281", "INTERESES CON INSTITUCIONES FINANCIERAS NO RELACIONADAS LOCAL (Gasto)"),
    ("7287", "INTERESES PAGADOS A TERCEROS RELACIONADAS LOCAL (Gasto)"),
    # Totales
    ("7991", "TOTAL COSTOS OPERACIONALES"),
    ("7992", "TOTAL GASTOS"),
    ("7999", "TOTAL COSTOS Y GASTOS"),
]
