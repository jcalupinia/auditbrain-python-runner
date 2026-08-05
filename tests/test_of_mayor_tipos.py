"""Contratos del dominio del motor de mayores."""

from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    LecturaMayor,
    Movimiento,
    PerfilCuenta,
    ResultadoClasificacion,
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


def test_justificacion_solo_muestra_motivos_de_la_categoria_elegida_sin_duplicados():
    """Defecto 5: la justificacion NO debe imprimir motivos de categorias
    que perdieron (contradice la propia conclusion del papel de trabajo),
    ni duplicar el mismo motivo repetido por varias señales."""
    r = ResultadoClasificacion(
        codigo="2.1.7.2.5",
        nombre="Ret. 10% Honorarios",
        categoria="RET_RENTA",
        confianza="alta",
        origen="reglas",
        senales=[
            Senal("RET_RENTA", 40, "nombre con tarifa 10% de retencion de renta"),
            Senal("IVA_VENTAS", 15, "codigo 2.1.7.2.5 es de naturaleza pasivo"),
            Senal("IVA_DIFERIDO", 15, "codigo 2.1.7.2.5 es de naturaleza pasivo"),
            Senal("RET_IVA", 15, "codigo 2.1.7.2.5 es de naturaleza pasivo"),
            Senal("RET_RENTA", 15, "codigo 2.1.7.2.5 es de naturaleza pasivo"),
            Senal("RET_RENTA", -30, "saldo deudor contradice naturaleza pasivo"),
            Senal("VENTAS", -30, "saldo deudor contradice naturaleza ingreso"),
        ],
    )
    assert r.justificacion == [
        "nombre con tarifa 10% de retencion de renta",
        "codigo 2.1.7.2.5 es de naturaleza pasivo",
    ]


def test_justificacion_de_cuenta_sin_categoria_queda_vacia():
    r = ResultadoClasificacion(
        codigo="9.9", nombre="Cuenta puente varios", categoria=None,
        confianza="baja", origen="reglas",
        senales=[Senal("VENTAS", 20, "nombre menciona retención, sin tarifa")],
    )
    assert r.justificacion == []
