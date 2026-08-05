"""Extractores de señal, uno por fuente de evidencia."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.senales import (
    extraer_tarifa,
    senal_codigo,
    senal_contrapartidas,
    senal_movimientos,
    senal_naturaleza,
    senal_nombre,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import PerfilCuenta


def _perfil(codigo, nombre, **kw):
    return PerfilCuenta(codigo=codigo, nombre=nombre, **kw)


def _mejor(senales):
    return max(senales, key=lambda s: s.puntaje).categoria if senales else None


@pytest.mark.parametrize(
    "nombre,esperada",
    [
        ("IVA sobre Compras", 1.0),          # sin tarifa en el nombre
        ("Ret. 1% Bienes Muebles de Naturaleza Corporal", 1.0),
        ("Ret. 1.75% Bienes Muebles de Naturaleza Corporal", 1.75),
        ("Ret. 2.75% Servicios", 2.75),
        ("Ret. 10% Honorarios Profesionales y Dietas", 10.0),
        ("Ret. 100% Honorarios, Arrendamientos", 100.0),
        ("Retención del 70%", 70.0),
    ],
)
def test_extrae_la_tarifa_del_nombre(nombre, esperada):
    tarifa = extraer_tarifa(nombre)
    if "%" not in nombre:
        assert tarifa is None
    else:
        assert tarifa == esperada


def test_no_confunde_el_10_dentro_de_100():
    assert extraer_tarifa("Ret. 100% Honorarios, Arrendamientos") == 100.0


@pytest.mark.parametrize(
    "nombre,categoria",
    [
        ("IVA sobre Compras", "IVA_COMPRAS"),
        ("IVA en Importaciones", "IVA_COMPRAS"),
        ("IVA sobre Ventas", "IVA_VENTAS"),
        ("IVA Retenido", "IVA_RETENIDO"),
        ("IVA Diferido", "IVA_DIFERIDO"),
        ("Ret. 10% Honorarios Profesionales y Dietas", "RET_RENTA"),
        ("Ret. 2.75% Servicios", "RET_RENTA"),
        ("Ret. 30% Bienes", "RET_IVA"),
        ("Ret. 70% Servicios", "RET_IVA"),
        ("Ret. 100% Honorarios, Arrendamientos", "RET_IVA"),
        ("Venta de insumos odontologicos", "VENTAS"),
        ("Servicios Odontologicos", "VENTAS"),
        ("Rebaja y/o Descuentos sobre Ventas", "VENTAS"),
    ],
)
def test_el_nombre_apunta_a_la_categoria_correcta(nombre, categoria):
    assert _mejor(senal_nombre(_perfil("9", nombre))) == categoria


def test_retencion_sin_porcentaje_queda_ambigua_entre_renta_e_iva():
    senales = senal_nombre(_perfil("2.1.7.2.11", "Retencion imptos relacion dependencia"))
    categorias = {s.categoria for s in senales}
    assert categorias == {"RET_RENTA", "RET_IVA"}


def test_nombre_irreconocible_no_produce_senales():
    assert senal_nombre(_perfil("9.9", "Cuenta puente varios")) == []


def test_la_senal_explica_su_motivo():
    senal = senal_nombre(_perfil("1.1.5.1.1", "IVA sobre Compras"))[0]
    assert "nombre" in senal.motivo.lower()


def test_el_codigo_apunta_a_las_categorias_de_su_naturaleza():
    senales = senal_codigo(_perfil("2.1.7.2.5", "Ret. 10% Honorarios"))
    categorias = {s.categoria for s in senales}
    assert categorias == {"IVA_VENTAS", "IVA_DIFERIDO", "RET_RENTA", "RET_IVA"}
    assert all(s.puntaje == 15 for s in senales)


def test_codigo_sin_primer_digito_conocido_no_opina():
    assert senal_codigo(_perfil("XYZ", "algo")) == []


def test_saldo_deudor_penaliza_las_categorias_de_pasivo_e_ingreso():
    senales = senal_naturaleza(_perfil("1.1.5.1.2", "Credito Tributario", debe=100.0))
    positivas = {s.categoria for s in senales if s.puntaje > 0}
    negativas = {s.categoria for s in senales if s.puntaje < 0}
    assert positivas == {"IVA_COMPRAS", "IVA_RETENIDO"}
    assert "VENTAS" in negativas
    assert all(s.puntaje == -30 for s in senales if s.puntaje < 0)


def test_cuenta_liquidada_cada_mes_queda_neutra_y_la_senal_calla():
    """Las cuentas de impuestos se liquidan cada mes y cierran en cero."""
    perfil = _perfil("1.1.5.1.1", "IVA sobre Compras", debe=1000.0, haber=1000.0)
    assert perfil.tendencia == "neutro"
    assert senal_naturaleza(perfil) == []


def test_prefijo_de_asiento_dominante_refuerza_la_categoria():
    perfil = _perfil("4.1.1.4", "Venta", prefijos_asiento={"VTA": 90, "ASI": 10})
    categorias = {s.categoria for s in senal_movimientos(perfil)}
    assert categorias == {"VENTAS", "IVA_VENTAS"}


def test_sin_prefijo_dominante_la_senal_calla():
    perfil = _perfil("4.1.1.4", "Venta", prefijos_asiento={"VTA": 5, "COM": 5})
    assert senal_movimientos(perfil) == []


def test_contrapartida_dominante_ya_clasificada_refuerza_su_categoria():
    perfil = _perfil("4.1.1.9", "Otra venta", contrapartidas=[("4.1.1.4", 30)])
    senales = senal_contrapartidas(perfil, {"4.1.1.4": "VENTAS"})
    assert senales[0].categoria == "VENTAS"
    assert senales[0].puntaje == 15


def test_contrapartida_de_otra_naturaleza_no_aporta():
    perfil = _perfil("2.1.7.4.1", "IVA Ventas", contrapartidas=[("4.1.1.4", 30)])
    assert senal_contrapartidas(perfil, {"4.1.1.4": "VENTAS"}) == []


def test_sin_contrapartidas_la_senal_calla_y_no_penaliza():
    assert senal_contrapartidas(_perfil("1.1.5.1.1", "IVA Compras"), {}) == []
