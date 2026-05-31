"""Tests for A8 Comercio Exterior filler."""

import pytest

from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a8_comercio_exterior import A8Filler
from backend.app.ict.cell_maps.a8 import (
    A8_SHEET,
    A8_TABLA_A_START_ROW,
    A8_TABLA_A_MAX_ROWS,
    A8_TABLA_B_START_ROW,
    A8_TABLA_B_MAX_ROWS,
    A8_TABLA_C_START_ROW,
    A8_TABLA_C_MAX_ROWS,
)


def _base_session():
    return {
        "razon_social": "TEST COMPAÑÍA S.A.",
        "ruc": "1234567890001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "",
    }


def _pago_cdi(**kwargs):
    base = {"tipo_regi": "01", "pago_loc_ext": "02", "pais": "USA", "pais_pago_gen": "USA",
            "denop_reg_fiscal": "EIN-123", "sujeto_retencion": "SI", "comentario": "Servicio software"}
    base.update(kwargs)
    return base


def _pago_sin_cdi(**kwargs):
    base = {"tipo_regi": "02", "pago_loc_ext": "02", "pais": "Panama",
            "denop_reg_fiscal": "RUC-456", "sujeto_retencion": "NO", "comentario": "Consultoría"}
    base.update(kwargs)
    return base


def _pago_reembolso(**kwargs):
    base = {"tipo_regi": "03", "pago_loc_ext": "03", "pais": "Mexico",
            "denop_reg_fiscal": "RFC-789", "sujeto_retencion": "NO", "comentario": "Reembolso servicios"}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Test: header se escribe correctamente
# ---------------------------------------------------------------------------
def test_a8_filler_writes_header():
    wb = load_template()
    filler = A8Filler()
    sess = _base_session()
    result = filler.fill(wb, sess, {"ats_pagos_exterior": []})

    ws = wb[A8_SHEET]
    assert ws["C3"].value == "TEST COMPAÑÍA S.A."
    assert ws["C4"].value == "1234567890001"
    assert ws["C5"].value == "2025"


# ---------------------------------------------------------------------------
# Test: clasificación y escritura en 3 tablas
# ---------------------------------------------------------------------------
def test_a8_filler_writes_header_and_classifies_transactions():
    wb = load_template()
    filler = A8Filler()
    sess = _base_session()
    data = {
        "ats_pagos_exterior": [
            _pago_cdi(),         # → Tabla A
            _pago_sin_cdi(),     # → Tabla B
            _pago_reembolso(),   # → Tabla C
        ],
    }
    result = filler.fill(wb, sess, data)

    assert result["filled_cells"] > 0
    assert result["warnings"] == []

    ws = wb[A8_SHEET]
    # Tabla A row 18: pais_residencia columna G
    assert ws[f"G{A8_TABLA_A_START_ROW}"].value == "USA"
    # Tabla B row 40: pais_residencia columna G
    assert ws[f"G{A8_TABLA_B_START_ROW}"].value == "Panama"
    # Tabla C row 61: proveedor_rfc columna I
    assert ws[f"I{A8_TABLA_C_START_ROW}"].value == "RFC-789"


# ---------------------------------------------------------------------------
# Test: solo pagos con CDI van a Tabla A
# ---------------------------------------------------------------------------
def test_a8_filler_only_cdi_goes_to_tabla_a():
    wb = load_template()
    filler = A8Filler()
    sess = _base_session()
    data = {
        "ats_pagos_exterior": [
            _pago_cdi(pais="Canada"),
            _pago_cdi(pais="Spain"),
        ],
    }
    result = filler.fill(wb, sess, data)
    assert result["filled_cells"] > 0
    assert result["warnings"] == []

    ws = wb[A8_SHEET]
    assert ws[f"G{A8_TABLA_A_START_ROW}"].value == "Canada"
    assert ws[f"G{A8_TABLA_A_START_ROW + 1}"].value == "Spain"
    # Tabla B y C deben estar vacías
    assert ws[f"G{A8_TABLA_B_START_ROW}"].value is None
    assert ws[f"I{A8_TABLA_C_START_ROW}"].value is None


# ---------------------------------------------------------------------------
# Test: reembolso (pago_loc_ext=03) siempre va a Tabla C, incluso con tipo_regi=01
# ---------------------------------------------------------------------------
def test_a8_reembolso_overrides_cdi():
    wb = load_template()
    filler = A8Filler()
    sess = _base_session()
    data = {
        "ats_pagos_exterior": [
            # tipo_regi=01 pero pago_loc_ext=03 → debe ir a Tabla C, no Tabla A
            {"tipo_regi": "01", "pago_loc_ext": "03", "pais": "Brazil",
             "denop_reg_fiscal": "CNPJ-001", "sujeto_retencion": "SI"},
        ],
    }
    result = filler.fill(wb, sess, data)
    ws = wb[A8_SHEET]
    # Tabla A debe estar vacía
    assert ws[f"G{A8_TABLA_A_START_ROW}"].value is None
    # Tabla C row 61: proveedor_rfc (col I)
    assert ws[f"I{A8_TABLA_C_START_ROW}"].value == "CNPJ-001"


# ---------------------------------------------------------------------------
# Test: warn cuando no hay pagos
# ---------------------------------------------------------------------------
def test_a8_filler_warns_with_no_pagos():
    wb = load_template()
    filler = A8Filler()
    result = filler.fill(wb, _base_session(), {})
    assert any(
        "ats" in w.lower() or "pagos al exterior" in w.lower()
        for w in result["warnings"]
    )


def test_a8_filler_warns_with_empty_list():
    wb = load_template()
    filler = A8Filler()
    result = filler.fill(wb, _base_session(), {"ats_pagos_exterior": []})
    assert any(
        "pagos al exterior" in w.lower()
        for w in result["warnings"]
    )


# ---------------------------------------------------------------------------
# Test: truncamiento cuando hay más transacciones que filas disponibles
# ---------------------------------------------------------------------------
def test_a8_filler_truncates_tabla_a():
    wb = load_template()
    filler = A8Filler()
    pagos = [_pago_cdi(pais=f"PAIS_{i}") for i in range(A8_TABLA_A_MAX_ROWS + 2)]
    result = filler.fill(wb, _base_session(), {"ats_pagos_exterior": pagos})
    assert any("Tabla A" in w and "trunca" in w for w in result["warnings"])


def test_a8_filler_truncates_tabla_b():
    wb = load_template()
    filler = A8Filler()
    pagos = [_pago_sin_cdi(pais=f"PAIS_{i}") for i in range(A8_TABLA_B_MAX_ROWS + 2)]
    result = filler.fill(wb, _base_session(), {"ats_pagos_exterior": pagos})
    assert any("Tabla B" in w and "trunca" in w for w in result["warnings"])


def test_a8_filler_truncates_tabla_c():
    wb = load_template()
    filler = A8Filler()
    pagos = [_pago_reembolso(pais=f"PAIS_{i}") for i in range(A8_TABLA_C_MAX_ROWS + 2)]
    result = filler.fill(wb, _base_session(), {"ats_pagos_exterior": pagos})
    assert any("Tabla C" in w and "trunca" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Test: filled_cells > 0 cuando hay datos válidos
# ---------------------------------------------------------------------------
def test_a8_filler_filled_cells_positive():
    wb = load_template()
    filler = A8Filler()
    data = {
        "ats_pagos_exterior": [
            _pago_cdi(),
            _pago_sin_cdi(),
        ],
    }
    result = filler.fill(wb, _base_session(), data)
    assert result["filled_cells"] > 3  # al menos header + algunos campos


# ---------------------------------------------------------------------------
# Test: rfc_extranjero campo denop_reg_fiscal se mapea correctamente
# ---------------------------------------------------------------------------
def test_a8_filler_maps_denop_reg_fiscal_to_rfc():
    wb = load_template()
    filler = A8Filler()
    data = {
        "ats_pagos_exterior": [
            _pago_cdi(denop_reg_fiscal="EIN-999"),
        ],
    }
    filler.fill(wb, _base_session(), data)
    ws = wb[A8_SHEET]
    # Tabla A, col E = rfc_extranjero → denop_reg_fiscal
    assert ws[f"E{A8_TABLA_A_START_ROW}"].value == "EIN-999"


# ---------------------------------------------------------------------------
# Test: anexo_code correcto
# ---------------------------------------------------------------------------
def test_a8_filler_anexo_code():
    assert A8Filler.anexo_code == "A8"
