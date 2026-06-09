"""Tests de los helpers de Información contable (A4/A5/A9) y su uso en fillers."""

from backend.app.ict.fillers.referential_helpers import (
    balance_codigo_ref,
    libros_sumif_reactivo_formula,
)


def test_balance_codigo_ref_una_cuenta():
    assert balance_codigo_ref([5]) == "='DATOS BALANCE'!B5"


def test_balance_codigo_ref_varias_cuentas_separa_con_barra():
    f = balance_codigo_ref([5, 7])
    assert f == '=TEXTJOIN(" / ",TRUE,\'DATOS BALANCE\'!B5,\'DATOS BALANCE\'!B7)'


def test_balance_codigo_ref_sin_cuentas_devuelve_none():
    assert balance_codigo_ref([]) is None


def test_libros_sumif_reactivo_con_abs():
    f = libros_sumif_reactivo_formula("$B17")
    assert f == ('=IF($B17="","",ABS(SUMIF(\'DATOS BALANCE\'!$A:$A,$B17,'
                 '\'DATOS BALANCE\'!$D:$D)))')


def test_libros_sumif_reactivo_sin_abs():
    f = libros_sumif_reactivo_formula("$B17", take_abs=False)
    assert f == ('=IF($B17="","",SUMIF(\'DATOS BALANCE\'!$A:$A,$B17,'
                 '\'DATOS BALANCE\'!$D:$D))')


from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a9_inventarios import A9Filler


def _a9_session():
    return {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025",
            "numero_adhesivo": ""}


def test_a9_costo_total_inventario_final_usa_abs():
    """7022 (inv. final) tiene saldo negativo en balance → Costo Total con ABS."""
    wb = load_template()
    anexo_data = {
        "balance_mapeado": [
            {"casillero_sri": "7022", "codigo": "5PYG.53602.017",
             "descripcion": "(-) Inventario final de materia prima",
             "saldo": -930768.56},
        ],
        "_balance_lookup": [5],
    }
    A9Filler().fill(wb, _a9_session(), anexo_data)
    ws = wb["INVENTARIOS A9"]
    assert ws["G21"].value == "=ABS('DATOS BALANCE'!D5)"


def test_a9_costo_total_ajustes_7037_respeta_signo():
    """7037 (ajustes) NO usa ABS — mantiene el signo del balance."""
    wb = load_template()
    anexo_data = {
        "balance_mapeado": [
            {"casillero_sri": "7037", "codigo": "5PYG.53602.017",
             "descripcion": "(+/-) Ajustes", "saldo": -223636.86},
        ],
        "_balance_lookup": [9],
    }
    A9Filler().fill(wb, _a9_session(), anexo_data)
    ws = wb["INVENTARIOS A9"]
    assert ws["G26"].value == "='DATOS BALANCE'!D9"
