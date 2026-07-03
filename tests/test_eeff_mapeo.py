from backend.app.tax.planificacion_utilidades.parsers.mapeo_nombres import mapear_concepto


def test_activos_no_se_fusionan():
    assert mapear_concepto("Efectivo y equivalentes de efectivo")[1] == "efectivo"
    assert mapear_concepto("Inventario")[1] == "inventario"
    assert mapear_concepto("Propiedades y equipo")[1] == "ppe"
    assert mapear_concepto("Cuentas por cobrar comerciales")[1] == "cxc"


def test_pasivo_y_patrimonio():
    assert mapear_concepto("Cuentas por pagar comerciales")[1] == "cxp"
    assert mapear_concepto("Anticipos de clientes")[1] == "anticipos"
    assert mapear_concepto("Capital")[1] == "capital"
    assert mapear_concepto("Resultado del ejercicio")[1] == "utilEjercicio"


def test_resultados():
    assert mapear_concepto("Ingresos ordinarios")[1] == "ventas"
    assert mapear_concepto("Costo de venta")[1] == "costo"
    assert mapear_concepto("De administración, ventas y otros")[1] == "gAdmin"


def test_no_mapeado_devuelve_none():
    assert mapear_concepto("Concepto rarísimo XYZ") == (None, None)


def test_totales_se_reconocen_como_total():
    assert mapear_concepto("TOTAL ACTIVOS")[0] == "total"
    assert mapear_concepto("Total pasivos corrientes")[0] == "total"
