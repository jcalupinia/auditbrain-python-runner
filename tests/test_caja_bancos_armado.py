# -*- coding: utf-8 -*-
"""Puente registro de prueba → papel formulado de Caja y Bancos."""
import io

import openpyxl

from backend.app.aud.niif.procesadores import caja_bancos_armado as arm
from backend.app.aud.niif.procesadores import caja_bancos_papel as papel

REG = {
    "engagement": {"client": "LANSEY S.A", "cutoff": "2026-08-31", "period": "ago-2026",
                   "preparer": "WR", "reviewer": "AT"},
    "datasets": {
        "cuentas": [
            {"id": "11010201", "nombre": "BANCO PICHINCHA", "saldo_libros": 5000,
             "saldo_banco": 5120, "saldo_anterior": 4000, "ncuenta": "3033617504"},
        ],
        "partidas": [
            {"cuenta": "11010201", "tipo": "Cheque pendiente", "referencia": "Cheque 101",
             "fecha_origen": "2026-08-20", "importe": 120},
            {"cuenta": "11010201", "tipo": "Nota de crédito", "referencia": "NC banco",
             "fecha_origen": "2026-08-25", "importe": 30},
        ],
    },
}


def test_hay_datos():
    assert arm.hay_datos(REG) is True
    assert arm.hay_datos({}) is False
    assert arm.hay_datos({"datasets": {"cuentas": []}}) is False


def test_arma_papel_valido_con_mapeo_de_categorias():
    data = arm.armar_desde_registro(REG)
    assert data[:2] == b"PK"  # xlsx (zip)
    wb = openpyxl.load_workbook(io.BytesIO(data))
    # Cédulas del papel, sin Procedimientos.
    assert "Sumaria" in wb.sheetnames and "Procedimientos" not in wb.sheetnames
    # La partida "Cheque pendiente" del procesador se mapeó a la categoría del papel.
    pc = wb["Partidas conciliatorias"]
    categorias = {pc.cell(r, 3).value for r in range(10, 12)}
    assert papel.CHEQUE in categorias
    assert papel.NC_PENDIENTE in categorias
    # El banco de la partida quedó legible (nombre, no código).
    bancos = {pc.cell(r, 2).value for r in range(10, 12)}
    assert "BANCO PICHINCHA" in bancos


def test_sumaria_toma_saldos_del_dataset():
    wb = openpyxl.load_workbook(io.BytesIO(arm.armar_desde_registro(REG)))
    sm = wb["Sumaria"]
    assert sm["A9"].value == "11010201"
    assert sm["C9"].value == 4000   # saldo anterior
    assert sm["E9"].value == 5000   # saldo actual (saldo_libros)
