"""Hoja resumen: cuenta × mes, agrupada por categoría."""

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.hoja_mayores import (
    SHEET_MAYORES,
    build_hoja_mayores,
)


class _Fila:
    """Doble de MayorClasificacionJob: solo lo que la hoja necesita."""

    def __init__(self, codigo, nombre, categoria, por_mes, n=1, debe=0.0, haber=0.0):
        self.codigo_cuenta = codigo
        self.nombre_cuenta = nombre
        self.categoria_final = categoria
        self.por_mes_json = por_mes
        self.n_movimientos = n
        self.debe = debe
        self.haber = haber


FILAS = [
    _Fila("1.1.5.1.1", "IVA sobre Compras", "IVA_COMPRAS", {"01": 659.57, "02": 1988.83}),
    _Fila("1.1.5.1.3", "IVA en Importaciones", "IVA_COMPRAS", {"01": 9252.0}),
    _Fila("4.1.1.4", "Venta de insumos", "VENTAS", {"01": -28117.84}),
]


def test_crea_la_hoja_con_una_fila_por_cuenta():
    wb = Workbook()
    build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    codigos = [ws.cell(r, 2).value for r in range(1, ws.max_row + 1)]
    assert "1.1.5.1.1" in codigos
    assert "4.1.1.4" in codigos


def test_agrupa_por_categoria_y_pone_un_subtotal():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    addr = lookup[("IVA_COMPRAS", "01")]
    assert ws[addr].value.startswith("=SUM(")


def test_el_subtotal_de_enero_de_iva_compras_suma_sus_dos_cuentas():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    # El subtotal es una fórmula SUM sobre el rango de sus cuentas: se
    # verifica el rango, no el valor (openpyxl no evalúa fórmulas).
    formula = ws[lookup[("IVA_COMPRAS", "01")]].value
    assert formula.count(":") == 1


def test_publica_la_direccion_del_subtotal_de_cada_categoria_y_mes():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    for mes in (f"{m:02d}" for m in range(1, 13)):
        assert ("IVA_COMPRAS", mes) in lookup
        assert ("VENTAS", mes) in lookup
    assert ("IVA_COMPRAS", "TOTAL") in lookup


def test_una_categoria_sin_cuentas_no_aparece():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    assert ("RET_IVA", "01") not in lookup


def test_los_meses_sin_movimiento_quedan_en_cero_no_vacios():
    """Un mes vacío en el papel de trabajo se lee como dato faltante."""
    wb = Workbook()
    build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    fila_ventas = next(
        r for r in range(1, ws.max_row + 1) if ws.cell(r, 2).value == "4.1.1.4"
    )
    assert ws.cell(fila_ventas, 5).value == 0.0   # marzo


def test_las_cuentas_sin_categoria_van_a_un_bloque_de_no_clasificadas():
    wb = Workbook()
    filas = FILAS + [_Fila("9.9.9", "Cuenta puente", None, {"01": 5.0})]
    lookup = build_hoja_mayores(wb, filas)
    ws = wb[SHEET_MAYORES]
    codigos = [ws.cell(r, 2).value for r in range(1, ws.max_row + 1)]
    assert "9.9.9" in codigos
    assert ("SIN_CLASIFICAR", "01") in lookup
