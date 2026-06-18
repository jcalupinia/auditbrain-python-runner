"""Tests for A5 Conciliación Costos y Gastos filler."""

import uuid

import pytest

from backend.app.ict.fillers.a5_conciliacion_costos import A5Filler
from backend.app.ict.fillers.base import load_template


def _session(tag: str = "") -> dict:
    uid = uuid.uuid4().hex[:8]
    return {
        "razon_social": f"Empresa Test A5 {uid}{tag}",
        "ruc": f"{uid}001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "",
    }


def _full_f101() -> dict:
    return {
        "6999": 18_379_679.21,
        "7999": 12_000_000.00,
        "804": 5_000.00,
        "805": 1_200.00,
        "808": 0.00,
        "806": 50_000.00,
        "807": 0.00,
        "809": 750.00,
        "813": 0.00,
        "1113": 0.00,
    }


def _f101_con_no_deducibles(cas_list: list[str]) -> dict:
    """F-101 base + casilleros no deducibles 7xxx con valor."""
    f101 = _full_f101()
    for i, cas in enumerate(cas_list):
        f101[cas] = 1_000.00 * (i + 1)
    return f101


# ── Test 1: header y casilleros se escriben ──────────────────────────────────

def test_a5_filler_writes_header_and_casilleros():
    wb = load_template()
    filler = A5Filler()
    result = filler.fill(wb, _session(), {"f101": _full_f101()})
    assert result["filled_cells"] > 0


# ── Test 2: anexo_code correcto ───────────────────────────────────────────────

def test_a5_filler_anexo_code():
    assert A5Filler.anexo_code == "A5"


# ── Test 3: advertencia cuando F-101 no declara no deducibles ────────────────

def test_a5_filler_warns_without_no_deducibles():
    """CAMBIO 2026-06-18: el Cuadro A ya NO toma datos del mayor/balance.
    Sin casilleros no deducibles (7xxx) en F-101 → warning del Cuadro A."""
    wb = load_template()
    filler = A5Filler()
    result = filler.fill(wb, _session(), {"f101": _full_f101()})
    assert any("no deducible" in w.lower() for w in result["warnings"])


# ── Test 4: Cuadro A traslada un casillero no deducible del F-101 ─────────────

def test_a5_filler_cuadro_a_traslada_no_deducible():
    """Un cas 7xxx 'VALOR NO DEDUCIBLE' con valor en F-101 → B17 = casillero."""
    wb = load_template()
    filler = A5Filler()
    data = {"f101": _f101_con_no_deducibles(["7042"])}
    result = filler.fill(wb, _session(), data)
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    assert ws["B17"].value == "7042"
    # Ya hay no deducibles → no debe estar el warning de "no declara"
    assert not any("no declara gastos no deducibles" in w.lower()
                   for w in result["warnings"])


# ── Test 5: 5 casilleros no deducibles caben sin inserción ───────────────────

def test_a5_filler_cuadro_a_5_no_deducibles_sin_insercion():
    wb = load_template()
    filler = A5Filler()
    data = {"f101": _f101_con_no_deducibles(
        ["7042", "7048", "7057", "7060", "7063"])}
    filler.fill(wb, _session(), data)
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    casilleros = [ws.cell(r, 2).value for r in range(17, 22)]
    assert "7063" in casilleros
    # 5 cas → sin inserción → Cuadro B sigue en posición original (G34)
    assert ws["G34"].value is not None


# ── Test 6: más de 5 casilleros no deducibles → inserta filas (no trunca) ─────

def test_a5_filler_cuadro_a_7_no_deducibles_inserta():
    wb = load_template()
    filler = A5Filler()
    data = {"f101": _f101_con_no_deducibles(
        ["7042", "7048", "7057", "7060", "7063", "7069", "7177"])}
    result = filler.fill(wb, _session(), data)
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    # 7 cas → 2 filas insertadas → todos presentes en B17:B23
    casilleros = [ws.cell(r, 2).value for r in range(17, 24)]
    assert "7177" in casilleros
    # Nunca se trunca
    assert not any("truncaron" in w for w in result["warnings"])


# ── Test 7: Cuadro B — casilleros 6999 y 7999 se escriben en col G ──────────

def test_a5_filler_cuadro_b_inputs():
    wb = load_template()
    filler = A5Filler()
    data = {"f101": _full_f101()}
    filler.fill(wb, _session(), data)
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    # G34 = casillero 6999, G43 = casillero 7999
    assert ws["G34"].value == 18_379_679.21
    assert ws["G43"].value == 12_000_000.00


# ── Test 8: Cuadro C — casilleros 804, 805, 808 en col H ────────────────────

def test_a5_filler_cuadro_c_participacion():
    wb = load_template()
    filler = A5Filler()
    data = {"f101": _full_f101()}
    filler.fill(wb, _session(), data)
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    assert ws["H58"].value == 5_000.00    # casillero 804
    assert ws["H59"].value == 1_200.00    # casillero 805
    assert ws["H60"].value == 0.00        # casillero 808


# ── Test 9: Cuadro D — casilleros de conciliación en col H ──────────────────

def test_a5_filler_cuadro_d_conciliacion():
    wb = load_template()
    filler = A5Filler()
    data = {"f101": _full_f101()}
    filler.fill(wb, _session(), data)
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    assert ws["H66"].value == 50_000.00   # casillero 806
    assert ws["H67"].value == 0.00        # casillero 807
    assert ws["H69"].value == 750.00      # casillero 809


# ── Test 10: sin f101 emite advertencia de Cuadro B ─────────────────────────

def test_a5_filler_warns_without_f101():
    wb = load_template()
    filler = A5Filler()
    result = filler.fill(wb, _session(), {})
    assert any("f-101" in w.lower() or "6999" in w for w in result["warnings"])


# ── Test 11: resultado siempre devuelve claves esperadas ─────────────────────

def test_a5_filler_result_keys():
    wb = load_template()
    filler = A5Filler()
    result = filler.fill(wb, _session(), {"f101": {}})
    assert "filled_cells" in result
    assert "warnings" in result
    assert isinstance(result["filled_cells"], int)
    assert isinstance(result["warnings"], list)
