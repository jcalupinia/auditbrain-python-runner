"""El motor vendorizado da los mismos dígitos que un cuadro independiente.

Este archivo es el que mantiene honesta la copia de
`backend/app/aud/niif/motor/audit_engine.py`. No compara bytes contra el
sitio —el portal no puede ver ese repositorio en CI—: recalcula cada caso con
la fórmula cerrada, en coma flotante, sin tocar el motor, y contrasta.

Es el mismo contraste que `verif-niif16.mjs` hace en el sitio contra
`domain.mjs`. Si el portal y el sitio pasan cada uno su versión de esta
prueba, los dos están sobre el mismo cuadro.
"""
from decimal import Decimal

import pytest

from backend.app.aud.niif.motor import calculate

PAGO, TASA, N, DIRECTOS = 10000, 0.06, 5, 1200

NIIF16 = {
    "id": "custom",
    "name": "Arrendamientos NIIF 16",
    "area": "Arrendamientos",
    "fields": [
        {"key": "id", "label": "Contrato", "type": "text"},
        {"key": "pago", "label": "Pago por período", "type": "number"},
        {"key": "tasa", "label": "Tasa incremental", "type": "number"},
        {"key": "n", "label": "Períodos", "type": "number"},
        {"key": "directos", "label": "Costos directos iniciales", "type": "number"},
    ],
    "series": {
        "count": "n",
        # Hacia atrás se descuenta hasta el valor presente; hacia adelante se
        # devenga. Es la definición literal del sitio: si aquí se copiara mal,
        # el contraste contra la fórmula cerrada lo delata.
        "backward": [
            {"key": "pendiente", "label": "Saldo más pago", "op": "add", "a": "@apertura", "b": "pago", "precision": 6},
            {"key": "factor", "label": "Uno más la tasa", "op": "add", "a": "tasa", "b": "#1", "precision": 6},
            {"key": "apertura", "label": "Pasivo al inicio del período", "op": "divide", "a": "pendiente", "b": "factor", "precision": 6},
        ],
        "forward": [
            {"key": "interes", "label": "Interés del período", "op": "multiply", "a": "apertura", "b": "tasa", "precision": 2},
            {"key": "con_interes", "label": "Pasivo más interés", "op": "add", "a": "apertura", "b": "interes", "precision": 6},
            {"key": "cierre", "label": "Pasivo al cierre", "op": "subtract", "a": "con_interes", "b": "pago", "precision": 2},
            {"key": "activo_inicial", "label": "Activo por derecho de uso inicial", "op": "add", "a": "^apertura", "b": "directos", "precision": 2},
            {"key": "depreciacion", "label": "Depreciación del período", "op": "divide", "a": "^activo_inicial", "b": "periodos", "precision": 2},
            {"key": "acumulada", "label": "Depreciación acumulada", "op": "multiply", "a": "depreciacion", "b": "periodo", "precision": 2},
            {"key": "activo", "label": "Activo al cierre", "op": "subtract", "a": "^activo_inicial", "b": "acumulada", "precision": 2},
        ],
    },
    "rules": [
        {"key": "pasivo_inicial", "label": "Pasivo en el reconocimiento", "op": "add", "a": "apertura_inicial", "b": "#0", "precision": 2},
        {"key": "activo_reconocido", "label": "Activo en el reconocimiento", "op": "add", "a": "pasivo_inicial", "b": "directos", "precision": 2},
        {"key": "interes_plazo", "label": "Interés total del plazo", "op": "add", "a": "interes_total", "b": "#0", "precision": 2},
    ],
    "control": "pago",
    "primary": "pasivo_inicial",
}

FILA = {"id": "L-001", "pago": str(PAGO), "tasa": str(TASA), "n": str(N), "directos": str(DIRECTOS)}


def cuadro_independiente():
    """Anualidad ordinaria y su tabla de amortización, en coma flotante."""
    vp = PAGO * (1 - (1 + TASA) ** -N) / TASA
    filas, saldo = [], vp
    for t in range(1, N + 1):
        interes = saldo * TASA
        cierre = saldo + interes - PAGO
        filas.append({"periodo": t, "apertura": saldo, "interes": interes, "cierre": cierre})
        saldo = cierre
    return vp, filas


@pytest.fixture(scope="module")
def corrida():
    return calculate({"definition": NIIF16, "rows": [FILA], "parameters": {}})


def test_el_cuadro_trae_una_fila_por_periodo(corrida):
    assert len(corrida["schedule"]) == N


def test_el_pasivo_inicial_es_el_valor_presente_de_la_anualidad(corrida):
    vp, _ = cuadro_independiente()
    assert abs(Decimal(corrida["rows"][0]["pasivo_inicial"]) - Decimal(str(vp))) <= Decimal("0.02")


@pytest.mark.parametrize("columna", ["apertura", "interes", "cierre"])
def test_cada_periodo_coincide_con_la_formula_cerrada(corrida, columna):
    _, esperado = cuadro_independiente()
    for motor, teorico in zip(corrida["schedule"], esperado):
        assert abs(Decimal(motor[columna]) - Decimal(str(teorico[columna]))) <= Decimal("0.02"), (
            f"período {motor['periodo']}, columna {columna}: "
            f"motor {motor[columna]} vs independiente {teorico[columna]:.2f}"
        )


def test_el_pasivo_se_extingue_al_final_del_plazo(corrida):
    # Es el control que de verdad importa del cuadro: si el último cierre no
    # es cero, el descuento hacia atrás no llegó al valor presente correcto.
    assert abs(Decimal(corrida["schedule"][-1]["cierre"])) <= Decimal("0.02")


def test_el_activo_por_derecho_de_uso_suma_los_costos_directos(corrida):
    vp, _ = cuadro_independiente()
    fila = corrida["rows"][0]
    assert abs(Decimal(fila["activo_reconocido"]) - Decimal(str(vp + DIRECTOS))) <= Decimal("0.02")
    # Se deprecia lineal sobre el plazo y queda en cero al final.
    assert abs(Decimal(corrida["schedule"][-1]["activo"])) <= Decimal("0.05")


def test_el_interes_del_plazo_es_pagos_menos_principal(corrida):
    vp, _ = cuadro_independiente()
    esperado = PAGO * N - vp
    assert abs(Decimal(corrida["rows"][0]["interes_plazo"]) - Decimal(str(esperado))) <= Decimal("0.05")


def test_los_totales_solo_traen_las_reglas_de_dos_decimales_y_el_control(corrida):
    # Contrato del motor: `totals` no incluye los agregados de la serie.
    assert set(corrida["totals"]) == {"pasivo_inicial", "activo_reconocido", "interes_plazo", "pago"}
    assert Decimal(corrida["totals"]["pago"]) == Decimal(PAGO)


def test_un_importe_absurdo_se_rechaza_con_mensaje_en_vez_de_devolver_un_numero():
    # Sin el tope, el Worker abortaría y Python devolvería un número: el
    # contraste lo marcaría como discrepancia en vez de explicar la causa.
    with pytest.raises((ValueError, ArithmeticError)):
        calculate({
            "definition": NIIF16,
            "rows": [dict(FILA, pago="999999999999999")],
            "parameters": {},
        })
