"""Tests de regla A1: signos y fórmula CONTROL del total F-101.

Bug reportado por el usuario:
  1. Los totales de la col C estaban como referencia directa al cas total
     declarado en el F-101 (='DATOS F-101'!Cxx). El usuario quiere que sean
     SUMA de los componentes para servir como CONTROL del F-101.
  2. Las cuentas (-) acumuladas (deterioro, depreciación, etc.) deben
     RESTAR en esa SUMA — no sumar.
  3. La col F (Balance contable) muestra pasivos/patrimonio negativos
     cuando el sistema contable los reporta así. Deben mostrarse positivos
     para coincidir con el signo del F-101.

Esta suite garantiza:
  - C de cada total PRIMARIO es una fórmula =+Cxx+Cyy-Czz+... con signos.
  - F de cada total PRIMARIO es la misma fórmula con signos.
  - F de cuentas individuales en Pasivos/Patrimonio/cuentas-(-) usa ABS().
"""

import pytest

from backend.app.ict.cell_maps.a1 import A1_FIRST_DATA_ROW, A1_SHEET
from backend.app.ict.fillers.a1_mapeo import A1Filler
from backend.app.ict.fillers.base import load_template, reset_trace


def _sess():
    return {"razon_social": "TEST", "ruc": "1", "ejercicio_fiscal": "2025",
            "numero_adhesivo": ""}


# ─────────────────────────────────────────────────────────────────────────────
# Tests de la función helper _build_signed_sum_formula
# ─────────────────────────────────────────────────────────────────────────────

def test_signed_sum_resta_casilleros_negativos():
    """cas 314 (deterioro, en NEGATIVE_CASILLEROS) debe ir con signo -."""
    cas_to_row = {"311": 13, "314": 22, "315": 23}
    formula = A1Filler._build_signed_sum_formula(
        "C", ["311", "314", "315"], cas_to_row
    )
    assert formula == "=+C13-C22+C23", f"Got: {formula}"


def test_signed_sum_skip_casilleros_sin_fila():
    """Si un componente no tiene fila asignada, se omite (no rompe)."""
    cas_to_row = {"311": 13}
    formula = A1Filler._build_signed_sum_formula(
        "C", ["311", "314", "999"], cas_to_row
    )
    assert formula == "=+C13", f"Got: {formula}"


def test_signed_sum_funciona_con_columna_F():
    """Misma lógica para F."""
    cas_to_row = {"311": 13, "317": 25, "320": 28}
    formula = A1Filler._build_signed_sum_formula(
        "F", ["311", "317", "320"], cas_to_row
    )
    assert formula == "=+F13-F25+F28", f"Got: {formula}"


def test_signed_sum_devuelve_none_si_no_hay_componentes():
    assert A1Filler._build_signed_sum_formula("C", [], {}) is None
    assert A1Filler._build_signed_sum_formula("C", ["999"], {}) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests de _needs_abs_normalization
# ─────────────────────────────────────────────────────────────────────────────

def test_normaliza_pasivos_corrientes():
    assert A1Filler._needs_abs_normalization("511") is True
    assert A1Filler._needs_abs_normalization("525") is True
    assert A1Filler._needs_abs_normalization("550") is True


def test_normaliza_pasivos_no_corrientes():
    assert A1Filler._needs_abs_normalization("553") is True
    assert A1Filler._needs_abs_normalization("574") is True  # Desahucio
    assert A1Filler._needs_abs_normalization("589") is True


def test_normaliza_patrimonio():
    assert A1Filler._needs_abs_normalization("601") is True
    assert A1Filler._needs_abs_normalization("612") is True  # pérdidas
    assert A1Filler._needs_abs_normalization("698") is True


def test_normaliza_cuentas_negativas_activo():
    """Deterioro, depreciación, amortización (cuentas (-))."""
    assert A1Filler._needs_abs_normalization("314") is True
    assert A1Filler._needs_abs_normalization("347") is True
    assert A1Filler._needs_abs_normalization("384") is True


def test_NO_normaliza_activos_corrientes_normales():
    """Caja, bancos, etc. — vienen positivos del balance, dejarlos."""
    assert A1Filler._needs_abs_normalization("311") is False
    assert A1Filler._needs_abs_normalization("315") is False
    assert A1Filler._needs_abs_normalization("336") is False


def test_NO_normaliza_ingresos_ni_costos():
    """Cuentas de resultados se manejan sin ABS."""
    assert A1Filler._needs_abs_normalization("6001") is False
    assert A1Filler._needs_abs_normalization("7185") is False


# ─────────────────────────────────────────────────────────────────────────────
# E2E: el filler aplica todo correctamente
# ─────────────────────────────────────────────────────────────────────────────

def _row_of_cas(ws, cas: str, start: int = A1_FIRST_DATA_ROW) -> int | None:
    for r in range(start, ws.max_row + 1):
        if str(ws[f"A{r}"].value or "").strip() == cas:
            return r
    return None


def test_e2e_total_C_es_suma_de_componentes_no_referencia_directa():
    """Cas 361 (Total Activos Corrientes) ya NO debe ser ='DATOS F-101'!Cxx
    sino una fórmula =+C13+C22-C25+... que SUMA los componentes."""
    wb = load_template()
    reset_trace()
    A1Filler().fill(wb, _sess(), {
        "f101": {"311": 100, "314": 10, "315": 50, "361": 140},
        "balance_mapeado": [],
    })
    ws = wb[A1_SHEET]
    row_361 = _row_of_cas(ws, "361")
    assert row_361 is not None
    c_value = ws[f"C{row_361}"].value
    assert isinstance(c_value, str) and c_value.startswith("="), \
        f"Esperaba fórmula, recibí {c_value!r}"
    # NO debe ser referencia directa al F-101
    assert "DATOS F-101" not in c_value, \
        f"C del total NO debe referenciar el F-101 directo: {c_value!r}"
    # Sí debe sumar referencias intra-A1
    assert c_value.startswith("=+C") or c_value.startswith("=C"), \
        f"Debe ser fórmula de suma intra-A1: {c_value!r}"


def test_e2e_total_C_resta_cuentas_negativas():
    """En la fórmula del total, cas 314 (deterioro) debe ir con signo -."""
    wb = load_template()
    reset_trace()
    A1Filler().fill(wb, _sess(), {
        "f101": {"311": 100, "314": 10, "315": 50, "361": 140},
        "balance_mapeado": [],
    })
    ws = wb[A1_SHEET]
    row_361 = _row_of_cas(ws, "361")
    row_314 = _row_of_cas(ws, "314")
    c_total = ws[f"C{row_361}"].value
    assert f"-C{row_314}" in c_total, \
        f"Cas 314 debe restarse en el total. Fórmula: {c_total!r}"


def test_e2e_total_F_es_suma_de_componentes_con_signos():
    """F del total también debe ser =+F13-F25+... no =SUM(F:F) simple."""
    wb = load_template()
    reset_trace()
    A1Filler().fill(wb, _sess(), {
        "f101": {"311": 100, "314": 10, "315": 50, "361": 140},
        "balance_mapeado": [],
    })
    ws = wb[A1_SHEET]
    row_361 = _row_of_cas(ws, "361")
    f_total = ws[f"F{row_361}"].value
    assert isinstance(f_total, str) and f_total.startswith("="), \
        f"F del total debe ser fórmula: {f_total!r}"
    row_314 = _row_of_cas(ws, "314")
    # cas 314 debe restarse
    assert f"-F{row_314}" in f_total, \
        f"F total debe restar cas 314 (deterioro): {f_total!r}"


def test_e2e_balance_pasivo_negativo_se_normaliza_con_ABS():
    """Pasivo cargado en el balance como -100000 (convención contable
    de algunos sistemas) debe aparecer como ABS() en F del A1 para
    coincidir con el signo positivo del F-101."""
    wb = load_template()
    reset_trace()
    A1Filler().fill(wb, _sess(), {
        "f101": {"511": 100000},
        "balance_mapeado": [
            {"casillero_sri": "511", "codigo": "X", "descripcion": "Cuenta x pagar",
             "saldo": -100000.0},  # ← negativo (convención contable)
        ],
        # Forzar el lookup para que F genere ='DATOS BALANCE'!D<row>
        "_balance_lookup": [4],
    })
    ws = wb[A1_SHEET]
    row_511 = _row_of_cas(ws, "511")
    f_value = ws[f"F{row_511}"].value
    # F debe envolver con ABS() para normalizar el signo
    assert isinstance(f_value, str), f"F debe ser fórmula: {f_value!r}"
    assert f_value.startswith("=ABS("), \
        f"F de cas pasivo debe usar ABS para normalizar signo: {f_value!r}"


def test_e2e_balance_activo_normal_NO_lleva_ABS():
    """Caja (cas 311) viene positiva del balance — no aplicar ABS."""
    wb = load_template()
    reset_trace()
    A1Filler().fill(wb, _sess(), {
        "f101": {"311": 5000},
        "balance_mapeado": [
            {"casillero_sri": "311", "codigo": "X", "descripcion": "Caja",
             "saldo": 5000.0},
        ],
        "_balance_lookup": [4],
    })
    ws = wb[A1_SHEET]
    row_311 = _row_of_cas(ws, "311")
    f_value = ws[f"F{row_311}"].value
    # F debe ser referencia simple sin ABS
    assert isinstance(f_value, str) and f_value.startswith("=") and "ABS" not in f_value, \
        f"F de cas 311 (Caja, activo normal) NO debe llevar ABS: {f_value!r}"


def test_e2e_balance_cuenta_negativa_activo_se_normaliza():
    """Cas 314 (deterioro, NEGATIVE_CASILLEROS): si el balance lo trae
    -31857 (signo contable), debe mostrarse positivo en F para coincidir
    con el F-101 (que lo trae positivo)."""
    wb = load_template()
    reset_trace()
    A1Filler().fill(wb, _sess(), {
        "f101": {"314": 31857.79},
        "balance_mapeado": [
            {"casillero_sri": "314", "codigo": "X", "descripcion": "Provisión",
             "saldo": -31857.79},
        ],
        "_balance_lookup": [4],
    })
    ws = wb[A1_SHEET]
    row_314 = _row_of_cas(ws, "314")
    f_value = ws[f"F{row_314}"].value
    assert f_value.startswith("=ABS("), \
        f"F de cas 314 (deterioro, viene negativo) debe llevar ABS: {f_value!r}"
