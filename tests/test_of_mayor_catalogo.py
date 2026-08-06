"""Catálogo semilla de categorías fiscales."""

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import (
    CATEGORIAS,
    naturaleza_por_codigo,
)


def test_estan_las_siete_categorias_del_modelo_del_auditor():
    assert set(CATEGORIAS) == {
        "IVA_COMPRAS", "IVA_VENTAS", "IVA_RETENIDO",
        "RET_RENTA", "RET_IVA", "VENTAS", "IVA_DIFERIDO",
    }


def test_cada_categoria_declara_su_naturaleza_esperada():
    assert CATEGORIAS["IVA_COMPRAS"].naturaleza_esperada == "activo"
    assert CATEGORIAS["IVA_RETENIDO"].naturaleza_esperada == "activo"
    assert CATEGORIAS["IVA_VENTAS"].naturaleza_esperada == "pasivo"
    assert CATEGORIAS["RET_RENTA"].naturaleza_esperada == "pasivo"
    assert CATEGORIAS["RET_IVA"].naturaleza_esperada == "pasivo"
    assert CATEGORIAS["IVA_DIFERIDO"].naturaleza_esperada == "pasivo"
    assert CATEGORIAS["VENTAS"].naturaleza_esperada == "ingreso"


def test_deriva_la_naturaleza_del_primer_digito_del_codigo():
    assert naturaleza_por_codigo("1.1.5.1.1") == "activo"
    assert naturaleza_por_codigo("2.1.7.2.5") == "pasivo"
    assert naturaleza_por_codigo("3.1") == "patrimonio"
    assert naturaleza_por_codigo("4.1.1.4") == "ingreso"
    assert naturaleza_por_codigo("5.2.1") == "gasto"
    assert naturaleza_por_codigo("6.1") == "gasto"
    assert naturaleza_por_codigo("X") is None
