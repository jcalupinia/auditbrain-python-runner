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


def test_reescribir_anexo_remapea_pasivo_y_distingue_del_gasto():
    """El anexo reescrito lleva el pasivo a códigos 5BS.212xx (por nombre, SOLO cuentas que
    empiezan por «2») y conserva los gastos (empiezan por «5»); el gasto «Aporte patronal IESS»
    NO se confunde con el pasivo «Aportes por pagar» aunque ambos digan «aporte»."""
    import datetime
    from backend.app.aud.niif.procesadores.nomina.cedulas_nuevas import leer_anexo

    # Layout del cliente: fila0 encabezados, fila1 fechas (col C/F), fila2+ cuentas (pasivo 2.x, gasto 5.x)
    filas = [
        ["Código", "Descripción", "Saldo", "Variación", "%", "Saldo"],
        [None, None, datetime.datetime(2025, 12, 31), None, None, datetime.datetime(2026, 7, 31)],
        ["2.1.7.1.1", "Aportes por Pagar", 100.0, None, None, 80.0],
        ["2.1.7.6.1", "Décimo Tercer Sueldo por Pagar", 50.0, None, None, 70.0],
        ["2.1.7.6.3", "Vacaciones por Pagar", 30.0, None, None, 40.0],
        ["Total", None, 180.0, None, None, 190.0],
        [None, None, None, None, None, None],
        ["5.2.1.2.1.1", "Sueldos", 1000.0, None, None, 600.0],
        ["5.2.1.2.1.2", "Aporte patronal IESS", 120.0, None, None, 70.0],
    ]
    cliente = os.path.join(tempfile.mkdtemp(), "anexo_cliente.xlsx")
    pd.DataFrame(filas).to_excel(cliente, index=False, header=False)
    destino = os.path.join(tempfile.mkdtemp(), "anexo_adaptado.xlsx")
    PC.reescribir_anexo(cliente, destino)

    pas, gas = leer_anexo(destino)
    pas_cod = {c: (s24, s25) for c, _, s24, s25 in pas}
    assert pas_cod["5BS.21203.001"] == (100.0, 80.0)   # Aportes por pagar (pasivo)
    assert pas_cod["5BS.21204.001"] == (50.0, 70.0)    # Décimo tercero por pagar
    assert pas_cod["5BS.21204.003"] == (30.0, 40.0)    # Vacaciones por pagar
    # el gasto «Aporte patronal IESS» NO entró como pasivo (sigue siendo gasto, código 5.x)
    assert "5BS.21203.001" in pas_cod and len(pas) == 3
    gas_cod = {c for c, _, _, _ in gas}
    assert "5.2.1.2.1.2" in gas_cod and "5.2.1.2.1.1" in gas_cod


def test_reescribir_consolidado_al_formato_del_motor():
    """El Consolidado del IESS del cliente (una hoja, campos sin correr) se reescribe a la hoja
    `detallePlanillaConsolidado` con los campos corridos a col B, y el motor lo parsea bien
    (mes, cédula, patronal, individual, CCC, total)."""
    from backend.app.aud.niif.procesadores.nomina import motor

    cols = ["Periodo", "Cédula", "Nombre", "Rel. Trabajo", "Sueldo", "Días",
            "Patronal", "Individual", "Aporte Adic", "Cesantia", "% CCC", "Valor CCC", "Total Aporte"]
    filas = [
        ["2026-7", "1700000001", "EMPLEADO UNO", "06-CODIGO", 600, 30, 66.9, 56.7, 0, 0, 1, 6.0, 123.6],
        ["2026-6", "1700000001", "EMPLEADO UNO", "06-CODIGO", 600, 30, 66.9, 56.7, 0, 0, 1, 6.0, 123.6],
        ["Totales", None, None, None, None, None, None, None, None, None, None, None, None],
    ]
    cliente = _xlsx(pd.DataFrame(filas, columns=cols))
    destino = os.path.join(tempfile.mkdtemp(), "cons_adaptado.xlsx")
    PC.reescribir_consolidado(cliente, destino)

    rows = motor.leer_consolidado(destino)
    assert len(rows) == 2                      # la fila «Totales» se descarta
    r0 = rows[0]
    assert r0["mes"] == 7 and r0["ced"] == "1700000001"
    assert r0["pat"] == 66.9 and r0["ind"] == 56.7
    assert r0["ccc"] == 6.0 and r0["total"] == 123.6


def test_reescribir_rol_mapea_por_seccion_y_nombre():
    """El rol del cliente (otra hoja, secciones Datos Generales/Ingresos/Provisiones) se reescribe
    al layout de 67 columnas de la hoja «normal»; se mapea por sección+nombre (genérico), vacaciones
    gozadas y finiquitos quedan en 0 (pendientes del socio) y los campos clave se reconocen."""
    from backend.app.aud.niif.procesadores.nomina import motor

    # fila0 sección, fila1 campos, fila2+ datos. «Décimo Tercero»/«Fondos reserva» aparecen en
    # Ingresos y en Provisiones: la sección desambigua.
    sec = ["Datos Generales", None, None, "Ingresos", None, None, None, "Provisiones", None, None]
    hdr = ["Cédula", "Empleado", "Cargo", "Sueldo", "Fondos Reserva", "Décimo Tercero", "Décimo Cuarto",
           "Decimo Tercer Sueldo", "Vacaciones", "Fondos de reserva"]
    datos = [
        ["1700000001", "PEREZ JUAN", "Analista", 600, 50.0, 10.0, 0.0, 50.0, 25.0, 0.0],
        ["1700000002", "GOMEZ ANA", "Jefe", 1400, 116.62, 20.0, 0.0, 116.0, 58.0, 0.0],
    ]
    rol = _xlsx(pd.DataFrame([sec, hdr, *datos]))
    destino = os.path.join(tempfile.mkdtemp(), "rol_adaptado.xlsx")
    PC.reescribir_rol(rol, destino, mes=7)
    assert PC.ROL_CAMPOS_FALTANTES == []           # todos los campos clave reconocidos

    rows = motor.leer_rol_normal(destino)
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["mes"] == 7 and r0["nombre"] == "PEREZ JUAN"
    assert r0["sueldo"] == 600 and r0["fr_rol"] == 50.0 and r0["d13mens"] == 10.0
    assert r0["prov_d13"] == 50.0 and r0["prov_vac"] == 25.0   # de la sección Provisiones
    assert r0["vac_gozada"] == 0.0 and r0["finiquito"] == 0.0  # pendientes del socio, no inventados


def test_mayor_se_clasifica_por_contenido_si_el_nombre_no_identifica():
    """El resolver clasifica un mayor RQ-004 por sus códigos de cuenta cuando el nombre no dice
    GASTO/PASIVO (robustez: funciona aunque el archivo se llame «MayorA.xlsx»)."""
    from backend.app.aud.niif.procesadores import nomina_beneficios as nb

    gasto = _xlsx(pd.DataFrame([["Código", "Cuenta"], ["5.2.1.2.1.1", "Sueldos"],
                                ["5.2.1.2.1.2", "Aporte patronal"], ["5.2.1.2.1.3", "Décimo"]]))
    pasivo = _xlsx(pd.DataFrame([["Código", "Cuenta"], ["2.1.7.1.1", "Aportes por pagar"],
                                 ["2.1.7.6.1", "Décimo tercero por pagar"], ["2.1.7.6.3", "Vacaciones"]]))
    assert nb._tipo_mayor_por_contenido(gasto) == "gasto"
    assert nb._tipo_mayor_por_contenido(pasivo) == "pasivo"


def test_mes_de_nombre_del_archivo():
    assert PC.mes_de_nombre("Periodo_enero_S_2.xlsx") == 1
    assert PC.mes_de_nombre("Periodo_julio_S_4.xlsx") == 7
    assert PC.mes_de_nombre("rol diciembre.xlsx") == 12
    assert PC.mes_de_nombre("sin_mes.xlsx") is None   # «S_2» no se confunde con mes 2


def test_reescribir_roles_combina_varios_meses():
    """Varios roles mensuales (cada uno un período) se combinan en una hoja «normal» con una fila
    por empleado y mes; el motor los lee con su mes correcto."""
    from backend.app.aud.niif.procesadores.nomina import motor

    sec = ["Datos Generales", None, None, "Ingresos", "Provisiones", "Provisiones"]
    hdr = ["Cédula", "Empleado", "Cargo", "Sueldo", "Decimo Tercer Sueldo", "Vacaciones"]

    def _rol(sueldo):
        return _xlsx(pd.DataFrame([sec, hdr, ["1700000001", "PEREZ JUAN", "Analista", sueldo, 50.0, 25.0]]))

    enero, julio = _rol(600), _rol(650)
    destino = os.path.join(tempfile.mkdtemp(), "rol_combinado.xlsx")
    PC.reescribir_roles([(enero, 1), (julio, 7)], destino)
    rows = motor.leer_rol_normal(destino)
    meses = {r["mes"]: r["sueldo"] for r in rows}
    assert meses == {1: 600, 7: 650}
