"""El constructor de fixtures debe producir un xlsx legible por openpyxl."""

from io import BytesIO

from openpyxl import load_workbook

from tests._mayor_fixtures import ENCABEZADO_REAL, mayor_xlsx
from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor


def test_construye_un_xlsx_con_el_encabezado_en_la_fila_indicada():
    data = mayor_xlsx(
        [["1.1.5.1.1", "IVA sobre Compras", None, "COM 1", "", "", "", "", "", 10, 0, 10]],
        fila_encabezado=3,
    )
    ws = load_workbook(BytesIO(data)).active
    assert [c.value for c in ws[3]] == list(ENCABEZADO_REAL)
    assert ws.cell(4, 1).value == "1.1.5.1.1"


FILA = ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 202501000001",
        "FAC 001-001-000000001", "9999999999001", "PROVEEDOR DEMO S.A.", "",
        "COMPRA DE PRUEBA", 2.39, None, 2.39]


def test_detecta_las_doce_columnas_del_erp_real():
    lectura = leer_mayor(mayor_xlsx([FILA]))
    assert lectura.mapeo_suficiente
    assert lectura.columnas_detectadas["codigo"] == 0
    assert lectura.columnas_detectadas["cuenta"] == 1
    assert lectura.columnas_detectadas["debe"] == 9
    assert lectura.columnas_detectadas["haber"] == 10
    assert lectura.columnas_detectadas["saldo"] == 11


def test_no_confunde_persona_cruce_cuenta_con_la_columna_cuenta():
    """La columna 8 se llama 'Persona Cruce Cuenta' y contiene 'cuenta'."""
    lectura = leer_mayor(mayor_xlsx([FILA]))
    assert lectura.columnas_detectadas["cuenta"] == 1


def test_encuentra_el_encabezado_aunque_no_este_en_la_primera_fila():
    lectura = leer_mayor(mayor_xlsx([FILA], fila_encabezado=6))
    assert lectura.fila_encabezado == 6
    assert len(lectura.movimientos) == 1


def test_reporta_las_columnas_que_no_pudo_mapear():
    lectura = leer_mayor(
        mayor_xlsx([["1.1.5.1.1", 10]], encabezado=("Cta", "Valor"))
    )
    assert lectura.mapeo_suficiente is False
    assert "debe" in lectura.columnas_faltantes


def test_elige_la_hoja_con_mas_columnas_reconocidas():
    data = mayor_xlsx([FILA], hoja="MAYOR", hojas_previas=("Portada",))
    lectura = leer_mayor(data)
    assert lectura.hoja == "MAYOR"


def test_acepta_sinonimos_de_otros_erp():
    lectura = leer_mayor(
        mayor_xlsx(
            [["1.1.5.1.1", "IVA", "2025-01-05", "A1", 10, 0]],
            encabezado=("Cuenta Contable", "Nombre", "Fecha", "Comprobante",
                        "Débito", "Crédito"),
        )
    )
    assert lectura.mapeo_suficiente
    assert lectura.columnas_detectadas["codigo"] == 0
    assert lectura.columnas_detectadas["cuenta"] == 1
    assert lectura.columnas_detectadas["debe"] == 4
