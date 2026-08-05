"""El constructor de fixtures debe producir un xlsx legible por openpyxl."""

from io import BytesIO

import pytest
from openpyxl import load_workbook

from tests._mayor_fixtures import ENCABEZADO_REAL, mayor_xlsx, mayor_xlsx_multihoja
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


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("178.259,63", 178259.63),   # europeo
        ("178,259.63", 178259.63),   # US
        ("183724.10", 183724.10),    # plano
        ("-150,00", -150.0),         # negativo con coma decimal
        ("0,00", 0.0),
    ],
)
def test_importes_en_cualquier_formato_regional(texto, esperado):
    lectura = leer_mayor(
        mayor_xlsx([["1.1.5.1.1", "IVA", "2025-01-05", "A1", "", "", "", "",
                     "", texto, None, texto]])
    )
    assert lectura.movimientos[0].debe == esperado


def test_descarta_filas_de_total_sin_codigo_de_cuenta():
    filas = [
        ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 1", "", "", "",
         "", "", 10, 0, 10],
        [None, "TOTAL GENERAL", None, None, None, None, None, None, None,
         999, 0, 999],
    ]
    lectura = leer_mayor(mayor_xlsx(filas))
    assert len(lectura.movimientos) == 1
    assert lectura.filas_descartadas == 1


def test_descarta_un_encabezado_repetido_a_mitad_del_listado():
    filas = [
        ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 1", "", "", "",
         "", "", 10, 0, 10],
        list(ENCABEZADO_REAL),
        ["1.1.5.1.3", "IVA en Importaciones", "2025-01-06", "COM 2", "", "",
         "", "", "", 20, 0, 20],
    ]
    lectura = leer_mayor(mayor_xlsx(filas))
    assert [m.codigo for m in lectura.movimientos] == ["1.1.5.1.1", "1.1.5.1.3"]


def test_lee_todas_las_hojas_cuando_el_mayor_esta_repartido():
    """Defecto 1: un ERP que exporta una hoja por mes no debe perder las
    demás hojas en silencio."""
    fila_enero = ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 1",
                  "", "", "", "", "", 10, 0, 10]
    fila_febrero = ["1.1.5.1.3", "IVA en Importaciones", "2025-02-05", "COM 2",
                     "", "", "", "", "", 20, 0, 20]
    data = mayor_xlsx_multihoja({"ENERO": [fila_enero], "FEBRERO": [fila_febrero]})

    lectura = leer_mayor(data)

    assert len(lectura.movimientos) == 2
    assert lectura.hojas_leidas == ["ENERO", "FEBRERO"]
    assert lectura.hoja == "ENERO"  # la primera hoja leída, por compatibilidad
    assert lectura.filas_descartadas == 0


def test_celda_vacia_de_haber_cuenta_como_cero():
    lectura = leer_mayor(
        mayor_xlsx([["1.1.5.1.1", "IVA", "2025-01-05", "A1", "", "", "", "",
                     "", 2.39, None, 2.39]])
    )
    assert lectura.movimientos[0].haber == 0.0
    assert lectura.movimientos[0].neto == 2.39
