# -*- coding: utf-8 -*-
"""QA del módulo Efectivo y Equivalentes (batería del prompt §36 + export del reproceso E6).

Cubre los casos que faltaban de la §36: archivo/dataset vacío, fechas inválidas, varias
monedas, múltiples cuentas y bancos, conciliación cuadrada y descuadrada, y el Excel del
reproceso (REPROCESO_CONCILIACION.xlsx) con el cuadre por fórmula.
"""
import io

import openpyxl
import pytest

from backend.app.aud.niif.procesadores import caja_bancos_armado as A
from backend.app.aud.niif.procesadores import efectivo_equivalentes as E

CORTE = "2026-09-30"


def _f(cuenta, importe, tipo="Depósito en tránsito", fecha="2026-09-10", liq="2026-10-01"):
    return {"id": "P", "cuenta": cuenta, "tipo": tipo, "fecha_origen": fecha, "importe": importe, "fecha_liquidacion": liq}


def test_dataset_de_cuentas_vacio_da_error_claro():
    with pytest.raises(ValueError, match="anexo de cuentas"):
        E.ejecutar({"cuentas": []}, E.EJEMPLO["parametros"], CORTE)


def test_fecha_invalida_en_partida_se_reporta():
    filas = [{"id": "P-01", "cuenta": "1101", "tipo": "Depósito en tránsito",
              "fecha_origen": "no-es-fecha", "importe": "100", "_row": 2}]
    v = E.validar_filas("partidas", filas)
    assert not v["ok"]
    assert any(e["field"] == "fecha_origen" for e in v["errors"])


def test_varias_monedas_dispara_aviso():
    ds = {"cuentas": [
        {"id": "1101", "nombre": "Banco A", "tipo": "Banco", "moneda": "USD", "saldo_libros": "1000", "saldo_banco": "1000"},
        {"id": "1102", "nombre": "Banco B", "tipo": "Banco", "moneda": "EUR", "saldo_libros": "500", "saldo_banco": "500"},
    ]}
    r = E.ejecutar(ds, E.EJEMPLO["parametros"], CORTE)
    assert any(e["code"] == "MONEDA_INCONSISTENTE" for e in r["exceptions"])


def test_conciliacion_cuadrada_y_descuadrada_end_to_end():
    # Cuadrada: banco 1200, una NC de 200 no registrada → esperado = 1200 - 200 = 1000 = libros.
    ds = {"cuentas": [{"id": "1101", "nombre": "Banco A", "tipo": "Banco", "saldo_libros": "1000", "saldo_banco": "1200"}],
          "partidas": [_f("1101", "200", tipo="Nota de crédito")]}
    r = E.ejecutar(ds, {**E.EJEMPLO["parametros"], "tolerancia": 0}, CORTE)
    assert not any(e["code"] == "DIFERENCIA_NO_EXPLICADA" for e in r["exceptions"])
    # Descuadrada: sin la partida que explique la diferencia.
    ds2 = {"cuentas": [{"id": "1101", "nombre": "Banco A", "tipo": "Banco", "saldo_libros": "1000", "saldo_banco": "1200"}]}
    r2 = E.ejecutar(ds2, {**E.EJEMPLO["parametros"], "tolerancia": 0}, CORTE)
    assert any(e["code"] == "DIFERENCIA_NO_EXPLICADA" for e in r2["exceptions"])


def test_reproceso_multiples_cuentas_y_bancos():
    reg = {
        "engagement": {"client": "X", "cutoff": CORTE},
        "datasets": {
            "cuentas": [
                {"id": "1101", "nombre": "Banco A", "tipo": "Banco", "saldo_libros": "1000", "saldo_banco": "1000"},
                {"id": "1102", "nombre": "Banco B", "tipo": "Banco", "saldo_libros": "2000", "saldo_banco": "2000"},
            ],
            "libro_mayor": [
                {"cuenta": "1101", "fecha": "2026-09-05", "debito": "100", "credito": "0"},
                {"cuenta": "1102", "fecha": "2026-09-06", "debito": "200", "credito": "0"},
            ],
            "estado_cuenta": [
                {"cuenta": "1101", "fecha": "2026-09-05", "documento": "Dep", "debito": "0", "credito": "100"},
                {"cuenta": "1102", "fecha": "2026-09-06", "documento": "Dep", "debito": "0", "credito": "200"},
            ],
        },
    }
    m = A.matriz_reproceso(reg)
    assert len(m) == 2 and {f["cuenta"] for f in m} == {"1101", "1102"}
    assert all(f["coincidencias"] == 1 for f in m)   # cada banco emparejó su depósito


def test_reproceso_excel_cuadre_por_formula():
    reg = {
        "engagement": {"client": "X", "cutoff": CORTE},
        "datasets": {
            "cuentas": [{"id": "1101", "nombre": "Banco A", "tipo": "Banco", "saldo_libros": "1000", "saldo_banco": "1200"}],
            "libro_mayor": [{"cuenta": "1101", "fecha": "2026-09-05", "debito": "500", "credito": "0"}],
            "estado_cuenta": [
                {"cuenta": "1101", "fecha": "2026-09-05", "documento": "Dep", "debito": "0", "credito": "500"},
                {"cuenta": "1101", "fecha": "2026-09-30", "documento": "Comisión", "debito": "200", "credito": "0"},
            ],
        },
    }
    contenido = A.reproceso_excel(reg)
    assert contenido[:2] == b"PK"
    wb = openpyxl.load_workbook(io.BytesIO(contenido))
    ws = wb["Reproceso"]
    # Saldo s/auditoría (col H) y Diferencia (col J) son fórmulas, no valores pegados.
    assert isinstance(ws["G5"].value, str) and ws["G5"].value.startswith("=")   # G = saldo s/auditoría (col 7)
    assert isinstance(ws["I5"].value, str) and ws["I5"].value.startswith("=")   # I = diferencia (col 9)


def test_reproceso_excel_sin_estado_es_none():
    assert A.reproceso_excel({"datasets": {"cuentas": [{"id": "1101", "tipo": "Banco"}]}}) is None
