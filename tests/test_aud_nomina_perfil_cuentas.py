# -*- coding: utf-8 -*-
"""Adaptador de plan de cuentas de la nómina (`nomina/perfil_cuentas.py`).

Traduce los mayores de un cliente con otro plan de cuentas (clasificando por NOMBRE de cuenta)
a los códigos/conceptos que el motor espera. Datos SINTÉTICOS (ningún dato real de cliente):
estructura tipo «Código/Cuenta/Fecha/Descripción/Debe/Haber/referencia» con códigos punteados.

NB: esto cubre la adaptación de los MAYORES. La adaptación del anexo (RQ-002) y la verificación
de las 15 cédulas con validación del socio quedan como trabajo siguiente (ver PR)."""
import os
import tempfile

import pandas as pd

from backend.app.aud.niif.procesadores.nomina import mayores as MY, perfil_cuentas as PC


def _xlsx(df):
    r = os.path.join(tempfile.mkdtemp(), "m.xlsx")
    df.to_excel(r, index=False)
    return r


def _gasto():
    cols = ["Código", "Cuenta", "Fecha", "Descripción", "Debe", "Haber"]
    filas = [
        ["5.2.1.2.1.1", "Sueldos", "15/01/2025", "rol", 1000, 0],
        ["5.2.1.2.1.2", "Aporte patronal IESS", "15/01/2025", "rol", 120, 0],
        ["5.2.1.2.1.3", "Decimo tercer sueldo", "15/01/2025", "prov", 80, 0],
        ["5.2.1.2.1.5", "Vacaciones", "15/01/2025", "prov", 40, 0],
        ["5.2.1.2.1.6", "Fondos de reserva", "15/01/2025", "prov", 80, 0],
        ["5.2.1.2.1.8", "Comisiones", "15/01/2025", "rol", 30, 0],
        ["5.2.1.2.1.15", "Bonos", "15/01/2025", "rol", 50, 0],
    ]
    return MY._load(_xlsx(pd.DataFrame(filas, columns=cols)))


def _pasivo():
    cols = ["Código", "Cuenta", "Fecha", "Descripción", "Debe", "Haber", "referencia"]
    filas = [
        ["2.1.7.1.1", "Aportes por Pagar", "01/01/2025", "ap", 0, 500, "saldo inicial"],
        ["2.1.7.1.1", "Aportes por Pagar", "31/01/2025", "ap", 0, 120, "provision"],
        ["2.1.7.1.1", "Aportes por Pagar", "15/02/2025", "ap", 300, 0, "pagos"],
        ["2.1.7.1.2", "Prestamos Quirografarios", "31/01/2025", "q", 50, 0, "pagos"],
        ["2.1.7.1.3", "Prestamos Hipotecarios", "31/01/2025", "h", 30, 0, "pagos"],
        ["2.1.7.6.1", "Décimo Tercer Sueldo por Pagar", "31/01/2025", "d13", 0, 80, "provision"],
        ["2.1.7.6.3", "Vacaciones por Pagar", "31/01/2025", "vac", 0, 40, "provision"],
        ["2.1.7.6.3", "Vacaciones por Pagar", "20/02/2025", "vac", 25, 0, "finiquitos"],
        ["2.1.7.6.6", "Fondos de Reservas por Pagar", "31/01/2025", "fr", 0, 80, "provision"],
    ]
    return MY._load(_xlsx(pd.DataFrame(filas, columns=cols)))


def test_gasto_mapea_concepto_por_nombre_de_cuenta():
    G, nr = PC.adaptar_gasto(_gasto())
    conceptos = dict(zip(G["cta"], G["concepto"]))
    assert conceptos["5.2.1.2.1.1"] == "Sueldos"
    assert conceptos["5.2.1.2.1.2"] == "Aporte Patronal"
    assert conceptos["5.2.1.2.1.3"] == "Décimo Tercer Sueldo"
    assert conceptos["5.2.1.2.1.6"] == "Fondos de Reserva"
    assert conceptos["5.2.1.2.1.15"] == "Bono Desempeño"
    assert nr == []  # todas reconocidas


def test_pasivo_remapea_codigo_y_clase():
    P, nr = PC.adaptar_pasivo(_pasivo())
    codigos = set(P["cta"])
    assert "5BS.21203.001" in codigos   # Aportes por pagar
    assert "5BS.21203.003" in codigos   # Quirografarios
    assert "5BS.21203.005" in codigos   # Hipotecarios
    assert "5BS.21203.004" in codigos   # Fondos de reserva por pagar
    assert "5BS.21204.001" in codigos   # Décimo tercero
    assert "5BS.21204.003" in codigos   # Vacaciones
    clases = set(P["clase"])
    assert {"PROVISION", "PAGOS", "FINIQUITOS", "SALDO_INICIAL"} <= clases
    assert nr == []


def test_adaptar_produce_plan_de_referencia_y_concilia():
    """Tras adaptar, el pasivo trae las cuentas que el motor espera (pasa la salvaguarda) y
    el saldo reconstruido reconcilia (saldo inicial + provisión − pagos − finiquitos)."""
    G, I, B, nr = PC.adaptar(_gasto(), _pasivo())
    assert nr["gasto"] == [] and nr["pasivo"] == []
    assert MY._plan_de_cuentas_coincide(I, B)
    # Aportes (5BS.21203.001): saldo = -(Σ Debe−Haber) = -(−500 −120 +300) = 320
    ap = I[I["cta"] == "5BS.21203.001"]["Importe"].sum()
    assert round(-ap, 2) == 320.00


def test_reporta_cuentas_no_reconocidas_sin_inventar():
    """Una cuenta cuyo nombre no se reconoce NO se clasifica a ciegas: queda en el reporte."""
    cols = ["Código", "Cuenta", "Fecha", "Descripción", "Debe", "Haber", "referencia"]
    filas = [["2.9.9.9.9", "Cuenta rara no nómina", "31/01/2025", "x", 0, 10, "otros"]]
    P, nr = PC.adaptar_pasivo(MY._load(_xlsx(pd.DataFrame(filas, columns=cols))))
    assert any(c == "2.9.9.9.9" for c, _ in nr)
    assert "2.9.9.9.9" in set(P["cta"])  # se deja tal cual, no se fuerza a un código del motor
