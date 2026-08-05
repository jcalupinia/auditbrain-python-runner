"""Extractores de señal, uno por fuente de evidencia."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.senales import (
    extraer_tarifa,
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
