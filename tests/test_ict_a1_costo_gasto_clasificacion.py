"""Regresión: el Estado de Resultados del A1 se clasifica POR NATURALEZA.

Bug (2026-06-08): costos y gastos están INTERCALADOS por número en el F-101
(ej. 7040 COSTO / 7041 GASTO / 7247 COSTO > 7172). La clasificación por rango
numérico los mezclaba y los TOTALES 7991/7992 "sumaban otras cosas". Validado
contra el golden master ICT_14 (PROPHAR): 24 costos / 25 gastos sin mezcla.
"""

from backend.app.ict.cell_maps.a1 import (
    A1_CASILLEROS_ORDERED,
    clasificar_resultado,
)
from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES


def test_clasifica_costo_y_gasto_por_nombre_no_por_rango():
    # COSTO aunque el número sea > 7172
    assert clasificar_resultado("7247") == "COSTOS_OP"  # "COSTO OTROS GASTOS"
    assert clasificar_resultado("7208") == "COSTOS_OP"
    # GASTO aunque el número sea < 7172
    assert clasificar_resultado("7041") == "GASTOS"     # "GASTO SUELDOS..."
    assert clasificar_resultado("7044") == "GASTOS"


def test_excepciones_validadas_contra_ict14():
    assert clasificar_resultado("7037") == "COSTOS_OP"  # AJUSTES - COSTO DE VENTAS
    assert clasificar_resultado("7113") == "GASTOS"      # deterioro act. financieros
    assert clasificar_resultado("7654") == "GASTOS"      # amort. derechos uso (GASTO)


def test_ingresos_operacional_vs_no_operacional():
    assert clasificar_resultado("6001") == "ING_ORD"     # ventas
    assert clasificar_resultado("6005") == "ING_ORD"     # prestación de servicios
    assert clasificar_resultado("6033") == "ING_NO_OP"   # diferencias de cambio (no op)
    # "VALOR EXENTO" no suma (no se clasifica)
    assert clasificar_resultado("6002") is None          # VALOR EXENTO ventas


def test_no_deducibles_e_informativos_no_suman():
    # "VALOR NO DEDUCIBLE ..." y "(INFORMATIVO)" no se clasifican (no suman)
    for cas, nom in F101_CASILLERO_NAMES.items():
        U = nom.upper()
        if cas.isdigit() and 7001 <= int(cas) <= 7990 and "NO DEDUCIBLE" in U:
            assert clasificar_resultado(cas) is None, f"{cas} no debería sumar"


def test_orden_agrupa_costos_antes_del_total_7991_y_gastos_antes_del_7992():
    """Todos los COSTOS van antes del TOTAL 7991; todos los GASTOS antes del 7992."""
    pos = {cas: i for i, (cas, _) in enumerate(A1_CASILLEROS_ORDERED)}
    assert "7991" in pos and "7992" in pos
    for cas, _ in A1_CASILLEROS_ORDERED:
        cls = clasificar_resultado(cas)
        if cls == "COSTOS_OP":
            assert pos[cas] < pos["7991"], f"{cas} (costo) debe ir antes de 7991"
        elif cls == "GASTOS":
            assert pos["7991"] < pos[cas] < pos["7992"], f"{cas} (gasto) entre 7991 y 7992"


def test_orden_agrupa_ingresos_operacionales_antes_del_1005():
    pos = {cas: i for i, (cas, _) in enumerate(A1_CASILLEROS_ORDERED)}
    assert "1005" in pos and "1045" in pos
    for cas, _ in A1_CASILLEROS_ORDERED:
        cls = clasificar_resultado(cas)
        if cls == "ING_ORD":
            assert pos[cas] < pos["1005"], f"{cas} (ing operac) antes de 1005"
        elif cls == "ING_NO_OP":
            assert pos["1005"] < pos[cas] < pos["1045"], f"{cas} (ing no op) entre 1005 y 1045"
