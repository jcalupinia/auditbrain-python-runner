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
