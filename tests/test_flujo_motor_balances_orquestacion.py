import io
from datetime import datetime

from openpyxl import Workbook

from backend.app.client_portal.flujo import motor_balances as mb


def _xlsx(headers, rows):
    wb = Workbook(); ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()


def test_homologar_archivos_propaga_mapeo_a_crudo():
    mapeado = _xlsx(
        ["Cod.Cuenta.Contable", "Descripción", "CODIFO SUPER CIAS", "Códigos SRI", "Saldos 31 DIC"],
        [("1.01.01.02.001", "Produbanco", "1010103", "311", 100.0)],
    )
    crudo = _xlsx(
        ["Código", "Cuenta", datetime(2023, 12, 31), datetime(2024, 12, 31)],
        [("1.01.01.02.001", "Produbanco", 100.0, 110.0),
         ("1.01.01.01.002", "Caja Chica", 0.0, 5.0)],
    )
    out = mb.homologar_archivos([("mapeo.xlsx", mapeado), ("balance.xlsx", crudo)])
    esf = out["esf"]
    fichas = {f["cuenta"]: f for f in esf["filas"]}
    assert esf["periodos"] == ["31-dic-2023", "31-dic-2024"]
    assert fichas["1.01.01.02.001"]["super_cias"] == "1010103"
    assert fichas["1.01.01.01.002"]["super_cias"] == ""
    assert esf["huerfanas"] == ["1.01.01.01.002"]
    assert "31-dic-2024" in esf["cuadre"]


def test_homologar_archivos_clasifica_eri_aparte():
    crudo_eri = _xlsx(
        ["Código", "Cuenta", 2024],
        [("4.01.01", "Ventas", -100.0), ("5.1.01", "Costo", 60.0)],
    )
    out = mb.homologar_archivos([("resultados.xlsx", crudo_eri)])
    assert out["eri"]["periodos"] == ["2024"]
    assert out["esf"]["periodos"] == []


def test_homologar_archivos_no_crashea_con_archivo_corrupto():
    crudo = _xlsx(["Código", "Cuenta", 2024], [("1.01", "Caja", 100.0)])
    out = mb.homologar_archivos([("bueno.xlsx", crudo), ("malo.xlsx", b"no soy un xlsx")])
    assert out["esf"]["periodos"] == ["2024"]                       # el bueno se procesó
    assert any(e["archivo"] == "malo.xlsx" for e in out["errores"]) # el malo se reporta


def test_recalcular_homologado_actualiza_cuadre_y_huerfanas():
    esf = {"periodos": ["2024"], "filas": [
        {"cuenta": "a", "nombre": "Caja", "super_cias": "1010101", "sri": "311", "saldos": {"2024": 100.0}},
        {"cuenta": "b", "nombre": "X", "super_cias": "", "sri": "", "saldos": {"2024": -60.0}},
    ]}
    eri = {"periodos": [], "filas": []}
    out = mb.recalcular_homologado(esf, eri)
    assert out["esf"]["huerfanas"] == ["b"]
    assert out["esf"]["cuadre"]["2024"]["cuadra"] is False
