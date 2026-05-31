"""Tests for A6 Beneficios Tributarios filler."""

import uuid

import pytest

from backend.app.ict.fillers.a6_beneficios import A6Filler
from backend.app.ict.fillers.base import load_template


def _session(tag: str = "") -> dict:
    uid = uuid.uuid4().hex[:8]
    return {
        "razon_social": f"Empresa Test A6 {uid}{tag}",
        "ruc": f"{uid}002",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "",
    }


def _f101_with_810(valor: float = 50_000.0) -> dict:
    return {"810": valor}


def _deducciones(n: int = 1) -> list:
    return [
        {
            "codigo_cuenta": f"5.2.9{i}",
            "nombre_cuenta": f"Deducción adicional {i}",
            "valor_libros": 5_000.00 * i,
        }
        for i in range(1, n + 1)
    ]


def _contratos(n: int = 1) -> list:
    return [
        {
            "no_resolucion": f"RES-2025-{i:03d}",
            "fecha": f"2025-01-{i:02d}",
            "monto_incentivo": 100_000.00 * i,
        }
        for i in range(1, n + 1)
    ]


# ── Test 1: casillero 810 se escribe ─────────────────────────────────────────

def test_a6_filler_writes_casillero_810():
    wb = load_template()
    filler = A6Filler()
    data = {"f101": _f101_with_810(50_000.0)}
    result = filler.fill(wb, _session(), data)
    ws = wb["BENEFICIOS TRIBUTARIOS A6"]
    assert ws["G25"].value == 50_000.0
    assert result["filled_cells"] > 0


# ── Test 2: anexo_code correcto ───────────────────────────────────────────────

def test_a6_filler_anexo_code():
    assert A6Filler.anexo_code == "A6"


# ── Test 3: advertencia sin contratos ni exoneraciones ───────────────────────

def test_a6_filler_warns_with_no_contracts_or_exonerations():
    wb = load_template()
    filler = A6Filler()
    result = filler.fill(wb, _session(), {"f101": {}})
    assert any(
        "contratos" in w.lower() or "exoneraciones" in w.lower()
        for w in result["warnings"]
    )


# ── Test 4: Cuadro A detail rows ─────────────────────────────────────────────

def test_a6_filler_cuadro_a_detail():
    wb = load_template()
    filler = A6Filler()
    data = {
        "f101": _f101_with_810(),
        "deducciones_detail": _deducciones(2),
    }
    filler.fill(wb, _session(), data)
    ws = wb["BENEFICIOS TRIBUTARIOS A6"]
    # Fila 17: primera deducción
    assert ws["A17"].value == "5.2.91"
    assert ws["B17"].value == "Deducción adicional 1"
    assert ws["E17"].value == 5_000.00
    # Fila 18: segunda deducción
    assert ws["A18"].value == "5.2.92"
    assert ws["E18"].value == 10_000.00


# ── Test 5: truncamiento con más de 7 deducciones ────────────────────────────

def test_a6_filler_cuadro_a_truncates():
    wb = load_template()
    filler = A6Filler()
    data = {
        "f101": _f101_with_810(),
        "deducciones_detail": _deducciones(9),
    }
    result = filler.fill(wb, _session(), data)
    assert any("truncaron" in w for w in result["warnings"])


# ── Test 6: Cuadro B contratos de inversión ──────────────────────────────────

def test_a6_filler_cuadro_b_contratos():
    wb = load_template()
    filler = A6Filler()
    data = {
        "f101": {},
        "contratos_inversion": _contratos(2),
    }
    result = filler.fill(wb, _session(), data)
    ws = wb["BENEFICIOS TRIBUTARIOS A6"]
    # Fila 32: primer contrato
    assert ws["A32"].value == "RES-2025-001"
    assert ws["B32"].value == "2025-01-01"
    assert ws["K32"].value == 100_000.00
    # Fila 33: segundo contrato
    assert ws["A33"].value == "RES-2025-002"
    # Con contratos no debe haber advertencia de B/C
    assert not any("contratos" in w.lower() for w in result["warnings"])


# ── Test 7: Cuadro C exoneraciones ───────────────────────────────────────────

def test_a6_filler_cuadro_c_exoneraciones():
    wb = load_template()
    filler = A6Filler()
    data = {
        "f101": {},
        "exoneraciones": {
            "exportadores_habituales": {
                "utilizado": "Sí",
                "monto_incentivo": 75_000.00,
                "no_resolucion": "RES-EXP-001",
                "periodo_inicio": "2024",
            }
        },
    }
    result = filler.fill(wb, _session(), data)
    ws = wb["BENEFICIOS TRIBUTARIOS A6"]
    # Fila 44 = exportadores_habituales
    assert ws["G44"].value == "Sí"
    assert ws["H44"].value == 75_000.00
    assert ws["D44"].value == "RES-EXP-001"
    assert ws["E44"].value == "2024"
    assert result["filled_cells"] > 0


# ── Test 8: múltiples exoneraciones ──────────────────────────────────────────

def test_a6_filler_multiple_exoneraciones():
    wb = load_template()
    filler = A6Filler()
    data = {
        "f101": {},
        "exoneraciones": {
            "administradores_zonas_francas": {
                "utilizado": "Sí",
                "monto_incentivo": 20_000.00,
            },
            "deporte": {
                "utilizado": "No",
                "monto_incentivo": 0.0,
            },
        },
    }
    result = filler.fill(wb, _session(), data)
    ws = wb["BENEFICIOS TRIBUTARIOS A6"]
    assert ws["G42"].value == "Sí"   # zonas francas → fila 42
    assert ws["G43"].value == "No"   # deporte → fila 43
    assert result["filled_cells"] > 0


# ── Test 9: resultado siempre devuelve claves esperadas ──────────────────────

def test_a6_filler_result_keys():
    wb = load_template()
    filler = A6Filler()
    result = filler.fill(wb, _session(), {"f101": {}})
    assert "filled_cells" in result
    assert "warnings" in result
    assert isinstance(result["filled_cells"], int)
    assert isinstance(result["warnings"], list)


# ── Test 10: sin f101 no falla ───────────────────────────────────────────────

def test_a6_filler_empty_data_no_crash():
    wb = load_template()
    filler = A6Filler()
    result = filler.fill(wb, _session(), {})
    assert "filled_cells" in result
