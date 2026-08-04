"""Contratos del dominio del motor de mayores."""

from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    LecturaMayor,
    Movimiento,
    PerfilCuenta,
    Senal,
)


def test_movimiento_calcula_su_importe_neto():
    m = Movimiento(codigo="1.1.5.1.1", cuenta="IVA sobre Compras", debe=100.0, haber=25.0)
    assert m.neto == 75.0


def test_movimiento_expone_el_mes_de_su_fecha():
    import datetime

    m = Movimiento(codigo="1", cuenta="x", fecha=datetime.date(2025, 3, 17))
    assert m.mes == "03"


def test_movimiento_sin_fecha_no_tiene_mes():
    assert Movimiento(codigo="1", cuenta="x").mes is None


def test_lectura_sabe_si_pudo_mapear_las_columnas_minimas():
    completa = LecturaMayor(columnas_detectadas={"codigo": 0, "debe": 9, "haber": 10})
    incompleta = LecturaMayor(columnas_detectadas={"codigo": 0})
    assert completa.mapeo_suficiente is True
    assert incompleta.mapeo_suficiente is False


def test_perfil_reporta_su_tendencia_de_saldo():
    assert PerfilCuenta(codigo="1", nombre="x", debe=10.0, haber=2.0).tendencia == "deudor"
    assert PerfilCuenta(codigo="2", nombre="x", debe=2.0, haber=10.0).tendencia == "acreedor"
    assert PerfilCuenta(codigo="3", nombre="x", debe=5.0, haber=5.0).tendencia == "neutro"


def test_senal_es_comparable_por_puntaje():
    assert Senal("VENTAS", 40, "por nombre") > Senal("IVA_VENTAS", 15, "por código")
