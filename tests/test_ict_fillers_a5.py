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


def _mayor_nd(n: int = 1) -> list:
    return [
        {
            "codigo": f"5.2.99.{i:02d}",
            "nombre": f"Gasto no deducible {i}",
            "saldo": 10_000.00 * i,
        }
        for i in range(1, n + 1)
    ]


# ── Test 1: header y casilleros se escriben ──────────────────────────────────

def test_a5_filler_writes_header_and_casilleros():
    wb = load_template()
    filler = A5Filler()
    result = filler.fill(wb, _session(), {"f101": _full_f101()})
    assert result["filled_cells"] > 0


# ── Test 2: anexo_code correcto ───────────────────────────────────────────────

def test_a5_filler_anexo_code():
    assert A5Filler.anexo_code == "A5"


# ── Test 3: advertencia sin libro mayor ──────────────────────────────────────

def test_a5_filler_warns_without_mayor():
    wb = load_template()
    filler = A5Filler()
    result = filler.fill(wb, _session(), {"f101": _full_f101()})
    assert any("mayor" in w.lower() for w in result["warnings"])


# ── Test 4: Cuadro A con 1 movimiento escribe celdas ─────────────────────────

def test_a5_filler_cuadro_a_single_row():
    wb = load_template()
    filler = A5Filler()
    data = {
        "f101": _full_f101(),
        "mayor_no_deducibles": _mayor_nd(1),
    }
    result = filler.fill(wb, _session(), data)
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    # Cuadro A row 17 — col K debería tener el saldo del primer movimiento
    assert ws["K17"].value == 10_000.00
    # Sin warning de mayor cuando hay datos
    assert not any("mayor" in w.lower() for w in result["warnings"])


# ── Test 5: Cuadro A con 5 movimientos (máximo) ──────────────────────────────

def test_a5_filler_cuadro_a_max_rows():
    wb = load_template()
    filler = A5Filler()
    data = {
        "f101": _full_f101(),
        "mayor_no_deducibles": _mayor_nd(5),
    }
    result = filler.fill(wb, _session(), data)
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    # Fila 21 (última fila permitida) debería tener el saldo del 5to movimiento
    assert ws["K21"].value == 50_000.00
    # No truncamiento
    assert not any("truncaron" in w for w in result["warnings"])


# ── Test 6: truncamiento con más de 5 movimientos ────────────────────────────

def test_a5_filler_cuadro_a_truncates():
    wb = load_template()
    filler = A5Filler()
    data = {
        "f101": _full_f101(),
        "mayor_no_deducibles": _mayor_nd(7),
    }
    result = filler.fill(wb, _session(), data)
    assert any("truncaron" in w for w in result["warnings"])


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
