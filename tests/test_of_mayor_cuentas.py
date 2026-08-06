"""Agregación de movimientos en perfiles por cuenta."""

import datetime

from backend.app.aud.obligaciones_fiscales.mayor.cuentas import monto_segun_libros, perfilar
from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento


def _mov(codigo, cuenta, mes, debe=0.0, haber=0.0, asiento="COM 1"):
    return Movimiento(
        codigo=codigo, cuenta=cuenta, fecha=datetime.date(2025, mes, 15),
        asiento=asiento, debe=debe, haber=haber,
    )


def test_agrupa_por_codigo_y_suma_debe_y_haber():
    perfiles = perfilar([
        _mov("1.1.5.1.1", "IVA sobre Compras", 1, debe=10.0),
        _mov("1.1.5.1.1", "IVA sobre Compras", 2, debe=5.0),
        _mov("1.1.5.1.1", "IVA sobre Compras", 2, haber=15.0),
    ])
    p = perfiles["1.1.5.1.1"]
    assert p.n_movimientos == 3
    assert p.debe == 15.0
    assert p.haber == 15.0
    assert p.tendencia == "neutro"


def test_mensualiza_el_neto_por_mes():
    perfiles = perfilar([
        _mov("4.1.1.4", "Venta insumos", 1, haber=100.0),
        _mov("4.1.1.4", "Venta insumos", 1, haber=50.0),
        _mov("4.1.1.4", "Venta insumos", 3, haber=20.0),
    ])
    p = perfiles["4.1.1.4"]
    assert p.por_mes["01"] == -150.0
    assert p.por_mes["03"] == -20.0
    assert "02" not in p.por_mes


def test_cuenta_los_prefijos_de_asiento():
    perfiles = perfilar([
        _mov("4.1.1.4", "Venta", 1, asiento="VTA 202501000001"),
        _mov("4.1.1.4", "Venta", 1, asiento="VTA 202501000002"),
        _mov("4.1.1.4", "Venta", 2, asiento="ASI 202502000001"),
    ])
    assert perfiles["4.1.1.4"].prefijos_asiento == {"VTA": 2, "ASI": 1}


def test_conserva_el_nombre_de_la_cuenta():
    perfiles = perfilar([_mov("2.1.7.4.1", "IVA sobre Ventas", 1, haber=9.0)])
    assert perfiles["2.1.7.4.1"].nombre == "IVA sobre Ventas"


def test_movimiento_sin_fecha_no_rompe_la_mensualizacion():
    perfiles = perfilar([Movimiento(codigo="1", cuenta="x", debe=5.0)])
    assert perfiles["1"].por_mes == {}
    assert perfiles["1"].n_movimientos == 1


def test_detecta_las_contrapartidas_del_mismo_asiento():
    movs = [
        _mov("4.1.1.4", "Venta", 1, haber=100.0, asiento="VTA 1"),
        _mov("2.1.7.4.1", "IVA Ventas", 1, haber=15.0, asiento="VTA 1"),
        _mov("1.1.2.1", "Clientes", 1, debe=115.0, asiento="VTA 1"),
        _mov("4.1.1.4", "Venta", 2, haber=200.0, asiento="VTA 2"),
        _mov("1.1.2.1", "Clientes", 2, debe=200.0, asiento="VTA 2"),
    ]
    perfiles = perfilar(movs)
    assert perfiles["4.1.1.4"].contrapartidas[0] == ("1.1.2.1", 2)
    assert ("2.1.7.4.1", 1) in perfiles["4.1.1.4"].contrapartidas


def test_una_cuenta_no_es_contrapartida_de_si_misma():
    movs = [
        _mov("4.1.1.4", "Venta", 1, haber=100.0, asiento="VTA 1"),
        _mov("4.1.1.4", "Venta", 1, debe=10.0, asiento="VTA 1"),
    ]
    assert perfilar(movs)["4.1.1.4"].contrapartidas == []


def test_mayor_filtrado_sin_asientos_compartidos_no_produce_contrapartidas():
    """Caso real: el mayor viene filtrado a cuentas de impuestos."""
    movs = [
        _mov("1.1.5.1.1", "IVA Compras", 1, debe=2.39, asiento="COM 1"),
        _mov("1.1.5.1.1", "IVA Compras", 1, debe=12.0, asiento="COM 2"),
    ]
    assert perfilar(movs)["1.1.5.1.1"].contrapartidas == []


def test_tambien_mensualiza_el_debe_y_el_haber_por_separado():
    """El neto mezcla las compras del mes con la liquidación del mismo mes
    contra el pasivo de IVA. Caso real (cliente IMPUESTOS MEDI, enero):
    659.57 de débito por compras + 659.60 de crédito por la liquidación →
    neto -0.03, pero lo que se declaró al SRI fue el débito bruto: 659.57."""
    perfiles = perfilar([
        _mov("1.1.5.1.1", "IVA sobre Compras", 1, debe=659.57),
        _mov("1.1.5.1.1", "IVA sobre Compras", 1, haber=659.60),
    ])
    p = perfiles["1.1.5.1.1"]
    assert p.por_mes_debe["01"] == 659.57
    assert p.por_mes_haber["01"] == 659.60
    assert p.por_mes["01"] == -0.03  # se conserva el neto para otros usos


def test_monto_segun_libros_usa_el_debe_para_categorias_de_activo():
    perfiles = perfilar([
        _mov("1.1.5.1.1", "IVA sobre Compras", 1, debe=659.57),
        _mov("1.1.5.1.1", "IVA sobre Compras", 1, haber=659.60),
    ])
    assert monto_segun_libros(perfiles["1.1.5.1.1"], "IVA_COMPRAS") == {"01": 659.57}


def test_monto_segun_libros_usa_el_haber_para_categorias_de_pasivo_e_ingreso():
    """Caso real: la cuenta de ventas es acreedora; el neto sale negativo
    (-28.117,84) pero el papel de trabajo del auditor lo muestra en
    positivo: 28.117,84, el crédito bruto del mes."""
    perfiles = perfilar([_mov("4.1.1.4", "Venta de insumos", 1, haber=28117.84)])
    assert monto_segun_libros(perfiles["4.1.1.4"], "VENTAS") == {"01": 28117.84}


def test_monto_segun_libros_sin_categoria_usa_el_debe_por_defecto():
    perfiles = perfilar([_mov("9.9.9", "Cuenta puente", 1, debe=5.0, haber=1.0)])
    assert monto_segun_libros(perfiles["9.9.9"], None) == {"01": 5.0}
