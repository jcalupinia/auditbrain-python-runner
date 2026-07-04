from backend.app.tax.planificacion_utilidades.parsers.balance_resumido_nombre import (
    extract_balance_resumido_nombre,
)
from tests.fixtures.eeff_sintetico import libro_resumido_nombre


def test_periodos_esf_y_eri():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    assert [p["label"] for p in r["periodos_esf"]] == ["may-26", "2025", "2024", "2023"]
    assert [p["tipo"] for p in r["periodos_esf"]] == ["parcial", "anual", "anual", "anual"]
    assert [p["label"] for p in r["periodos_eri"]] == ["may-26", "may-25", "2025", "2024", "2023"]


def test_rubros_no_se_fusionan():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    d = r["data"]
    assert d["efectivo"][0] == 100 and d["inventario"][0] == 300 and d["ppe"][0] == 400
    assert d["cxc"][0] == 200  # CxC separada de efectivo/inventario


def test_ingresos_por_periodo_eri():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    # ventas: may-26=500, may-25=450, 2025=1200, 2024=1500, 2023=1400
    assert r["data"]["ventas"] == [500, 450, 1200, 1500, 1400]


def test_descuadre_emite_warning():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    assert any("descuadre" in w.lower() or "cuadr" in w.lower() for w in r["warnings"])


def test_comparaciones_en_salida():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    assert r["comparaciones"]["esf"] == [
        ["may-26", "2025"], ["2025", "2024"], ["2024", "2023"]
    ]
    eri = r["comparaciones"]["eri"]
    assert ["may-26", "may-25"] in eri
    assert ["2025", "2024"] in eri
    assert ["may-26", "2025"] not in eri  # jamás cruza parcial/anual
