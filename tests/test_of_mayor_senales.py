"""Extractores de señal, uno por fuente de evidencia."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.senales import (
    PESO_HISTORIAL,
    _rama,
    extraer_tarifa,
    senal_codigo,
    senal_contrapartidas,
    senal_historial,
    senal_movimientos,
    senal_naturaleza,
    senal_nombre,
    senal_rama,
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


def test_el_historial_del_cliente_manda_sobre_todo_lo_demas():
    senales = senal_historial(
        _perfil("2.1.7.2.11", "Retencion imptos relacion dependencia"),
        {"2.1.7.2.11": "RET_RENTA"},
    )
    assert senales[0].categoria == "RET_RENTA"
    assert senales[0].puntaje == PESO_HISTORIAL
    assert PESO_HISTORIAL > 100


def test_sin_historial_para_esa_cuenta_no_hay_senal():
    assert senal_historial(_perfil("9.9", "x"), {"1.1": "VENTAS"}) == []


def test_senal_historial_ignora_categoria_que_no_existe_en_el_catalogo():
    """Defecto 8b: una categoría obsoleta o mal escrita en el historial
    (ej. persistida antes en base de datos) no debe propagarse; cuando
    llegue al renderer del papel de trabajo explotaría."""
    senales = senal_historial(
        _perfil("2.1.7.2.11", "Retencion imptos relacion dependencia"),
        {"2.1.7.2.11": "CATEGORIA_QUE_NO_EXISTE"},
    )
    assert senales == []


def test_no_existe_una_constante_de_tarifas_de_retencion_de_iva_sin_usar():
    """Defecto 8c: TARIFAS_RET_IVA estaba definida y nunca se usaba."""
    import backend.app.aud.obligaciones_fiscales.mayor.senales as senales_mod
    assert not hasattr(senales_mod, "TARIFAS_RET_IVA")


def test_una_cuenta_hereda_la_categoria_de_sus_hermanas_de_rama():
    """2.1.7.2.11 hereda de 2.1.7.2.5 y 2.1.7.2.8, sus hermanas."""
    senales = senal_rama(
        _perfil("2.1.7.2.11", "Retencion imptos relacion dependencia"),
        {"2.1.7.2.5": "RET_RENTA", "2.1.7.2.8": "RET_RENTA"},
    )
    assert senales[0].categoria == "RET_RENTA"
    assert senales[0].puntaje == 25


def test_hermanas_en_desacuerdo_ganan_por_mayoria():
    senales = senal_rama(
        _perfil("2.1.7.2.11", "x"),
        {"2.1.7.2.5": "RET_RENTA", "2.1.7.2.8": "RET_RENTA", "2.1.7.2.1": "RET_IVA"},
    )
    assert senales[0].categoria == "RET_RENTA"


def test_una_cuenta_de_otra_rama_no_contamina():
    assert senal_rama(_perfil("4.1.1.4", "Venta"), {"2.1.7.2.5": "RET_RENTA"}) == []


def test_codigo_de_un_solo_segmento_no_tiene_rama():
    assert senal_rama(_perfil("4", "Ingresos"), {"5": "VENTAS"}) == []


# --- Defecto 7: _rama debe funcionar con códigos sin puntos ---------------

def test_rama_normaliza_guiones_como_separador():
    assert _rama("2-1-7-2-5") == "2.1.7.2"


def test_rama_normaliza_barras_y_espacios_como_separador():
    assert _rama("2/1/7 2 5") == "2.1.7.2"


def test_rama_de_codigo_plano_numerico_usa_los_dos_ultimos_caracteres():
    """Sin separador, se asume que el subgrupo va en los últimos dos
    dígitos (heurística documentada en el docstring de _rama)."""
    assert _rama("1150101") == "11501"


def test_rama_de_codigo_de_dos_caracteres_o_menos_es_none():
    assert _rama("15") is None
    assert _rama("1") is None
    assert _rama("") is None


def test_la_propagacion_por_rama_funciona_con_codigos_con_guiones():
    """Integración: la propagación (senal_rama) también debe reconocer que
    dos cuentas hermanas con guiones comparten rama."""
    senales = senal_rama(
        _perfil("2-1-7-2-11", "Retencion imptos relacion dependencia"),
        {"2-1-7-2-5": "RET_RENTA", "2-1-7-2-8": "RET_RENTA"},
    )
    assert senales[0].categoria == "RET_RENTA"


def test_la_propagacion_por_rama_funciona_con_codigos_planos():
    """Integración: cuentas hermanas con códigos totalmente numéricos sin
    separador también deben propagar por rama."""
    senales = senal_rama(
        _perfil("1150111", "Retencion sin tarifa en el nombre"),
        {"1150105": "RET_RENTA", "1150108": "RET_RENTA"},
    )
    assert senales[0].categoria == "RET_RENTA"
