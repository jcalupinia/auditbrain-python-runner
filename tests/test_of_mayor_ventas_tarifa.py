"""Separación de las ventas en gravadas / 0% / por asignar, asiento por asiento."""

import datetime
import time

from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento
from backend.app.aud.obligaciones_fiscales.mayor.ventas_tarifa import (
    BUCKETS,
    separar_ventas_por_tarifa,
)

CATEGORIAS = {"4.1.1.1": "VENTAS", "4.1.1.2": "VENTAS", "2.1.7.4.1": "IVA_VENTAS"}


def _venta(codigo, haber, asiento, mes=1):
    return Movimiento(codigo=codigo, cuenta="Ventas", asiento=asiento,
                      fecha=datetime.date(2025, mes, 10), haber=haber)


def _iva(haber, asiento, mes=1):
    return Movimiento(codigo="2.1.7.4.1", cuenta="IVA en ventas", asiento=asiento,
                      fecha=datetime.date(2025, mes, 10), haber=haber)


def test_un_asiento_sin_iva_es_venta_cero_por_ciento():
    desglose = separar_ventas_por_tarifa(
        [_venta("4.1.1.1", 500.0, "VTA 1")], CATEGORIAS
    )
    assert desglose["4.1.1.1"]["cero"]["01"] == 500.0
    assert desglose["4.1.1.1"]["gravada"].get("01", 0.0) == 0.0
    assert desglose["4.1.1.1"]["por_asignar"].get("01", 0.0) == 0.0


def test_si_el_iva_dividido_por_la_tarifa_cuadra_el_total_todo_es_gravado():
    desglose = separar_ventas_por_tarifa(
        [_venta("4.1.1.1", 500.0, "VTA 1"), _iva(75.0, "VTA 1")], CATEGORIAS
    )
    assert desglose["4.1.1.1"]["gravada"]["01"] == 500.0
    assert desglose["4.1.1.1"]["cero"].get("01", 0.0) == 0.0


def test_un_asiento_mixto_se_parte_por_el_subconjunto_que_cuadra_con_el_iva():
    """IVA 45 → base gravada 300. La única combinación que suma 300 es la
    línea de 300; las otras dos (100 y 250) son la parte 0% del asiento."""
    desglose = separar_ventas_por_tarifa(
        [_venta("4.1.1.1", 100.0, "VTA 1"), _venta("4.1.1.1", 250.0, "VTA 1"),
         _venta("4.1.1.2", 300.0, "VTA 1"), _iva(45.0, "VTA 1")],
        CATEGORIAS,
    )
    assert desglose["4.1.1.2"]["gravada"]["01"] == 300.0
    assert desglose["4.1.1.1"]["cero"]["01"] == 350.0
    assert desglose["4.1.1.1"]["gravada"].get("01", 0.0) == 0.0


def test_si_dos_lineas_del_mismo_tamano_cuadran_el_asiento_queda_por_asignar():
    """Dos líneas de 300 y base gravada 300: cuál de las dos es la gravada no
    se puede saber, así que el asiento entero se le muestra al auditor."""
    desglose = separar_ventas_por_tarifa(
        [_venta("4.1.1.1", 300.0, "VTA 1"), _venta("4.1.1.1", 250.0, "VTA 1"),
         _venta("4.1.1.2", 300.0, "VTA 1"), _iva(45.0, "VTA 1")],
        CATEGORIAS,
    )
    assert desglose["4.1.1.1"]["por_asignar"]["01"] == 550.0
    assert desglose["4.1.1.2"]["por_asignar"]["01"] == 300.0
    assert desglose["4.1.1.1"]["gravada"] == {}
    assert desglose["4.1.1.1"]["cero"] == {}


def test_gana_el_subconjunto_mas_pequeno_que_cuadra():
    """Decisión medida: la búsqueda va por tamaño ascendente. Con base
    gravada 300, la línea de 300 gana sobre la combinación 100+200; leer la
    unicidad de forma global dejaría este asiento POR ASIGNAR y sobre el
    mayor real bajaría de 11 a 10 los asientos resueltos."""
    desglose = separar_ventas_por_tarifa(
        [_venta("4.1.1.1", 100.0, "VTA 1"), _venta("4.1.1.1", 200.0, "VTA 1"),
         _venta("4.1.1.2", 300.0, "VTA 1"), _iva(45.0, "VTA 1")],
        CATEGORIAS,
    )
    assert desglose["4.1.1.2"]["gravada"]["01"] == 300.0
    assert desglose["4.1.1.1"]["cero"]["01"] == 300.0


def test_los_tres_buckets_suman_el_monto_segun_libros_de_cada_mes():
    movimientos = [
        _venta("4.1.1.1", 100.0, "VTA 1"), _venta("4.1.1.1", 250.0, "VTA 1"),
        _venta("4.1.1.2", 300.0, "VTA 1"), _iva(45.0, "VTA 1"),
        _venta("4.1.1.1", 80.0, "VTA 2"),
        _venta("4.1.1.2", 500.0, "VTA 3", mes=2), _iva(75.0, "VTA 3", mes=2),
    ]
    desglose = separar_ventas_por_tarifa(movimientos, CATEGORIAS)
    esperado = {}
    for m in movimientos:
        if CATEGORIAS[m.codigo] == "VENTAS":
            esperado[(m.codigo, m.mes)] = round(
                esperado.get((m.codigo, m.mes), 0.0) + m.haber, 2
            )
    for (codigo, mes), total in esperado.items():
        repartido = round(sum(desglose[codigo][b].get(mes, 0.0) for b in BUCKETS), 2)
        assert repartido == total, (codigo, mes)


def test_solo_se_desglosan_las_cuentas_de_ventas():
    desglose = separar_ventas_por_tarifa(
        [_venta("4.1.1.1", 500.0, "VTA 1"), _iva(75.0, "VTA 1")], CATEGORIAS
    )
    assert set(desglose) == {"4.1.1.1", "4.1.1.2"}


def test_una_venta_registrada_al_debe_no_infla_el_desglose():
    """Una nota de crédito entra en la aritmética del asiento (|neto|), pero
    el monto según libros de un ingreso es el HABER: aporta 0 a los buckets."""
    desglose = separar_ventas_por_tarifa(
        [Movimiento(codigo="4.1.1.1", asiento="NC 1", debe=200.0,
                    fecha=datetime.date(2025, 1, 10))],
        CATEGORIAS,
    )
    assert desglose["4.1.1.1"]["cero"]["01"] == 0.0


def test_un_asiento_de_muchas_lineas_no_cuelga_la_separacion():
    """Los asientos de cierre del mayor real llegan a 174 líneas de venta.

    Peor caso de la búsqueda: 40 importes múltiplos de 2,00 y una base
    gravada que NO es múltiplo de 2,00, así que no existe ninguna
    combinación y las cotas no podan nada. Sin el tope, el árbol es de 2^40.
    """
    importes = [100.0 + 2 * i for i in range(40)]
    lineas = [_venta("4.1.1.1", v, "ASI 1") for v in importes]
    inicio = time.perf_counter()
    desglose = separar_ventas_por_tarifa(lineas + [_iva(300.15, "ASI 1")], CATEGORIAS)
    assert time.perf_counter() - inicio < 2.0
    assert desglose["4.1.1.1"]["por_asignar"]["01"] == round(sum(importes), 2)


def test_un_asiento_ambiguo_de_22_lineas_se_resuelve_rapido():
    lineas = [_venta("4.1.1.1", 10.0 * (i + 1), "VTA 9") for i in range(22)]
    inicio = time.perf_counter()
    separar_ventas_por_tarifa(lineas + [_iva(3.33, "VTA 9")], CATEGORIAS)
    assert time.perf_counter() - inicio < 2.0
