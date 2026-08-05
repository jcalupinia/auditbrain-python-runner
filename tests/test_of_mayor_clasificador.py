"""Combinación de señales en una categoría con confianza y justificación."""

from backend.app.aud.obligaciones_fiscales.mayor.clasificador import (
    clasificar,
    clasificar_cuenta,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import PerfilCuenta


def _perfil(codigo, nombre, **kw):
    return PerfilCuenta(codigo=codigo, nombre=nombre, **kw)


def test_iva_sobre_compras_se_clasifica_con_confianza_alta():
    r = clasificar_cuenta(
        _perfil("1.1.5.1.1", "IVA sobre Compras", prefijos_asiento={"COM": 100})
    )
    assert r.categoria == "IVA_COMPRAS"
    assert r.confianza == "alta"
    assert r.origen == "reglas"


def test_retencion_del_70_por_ciento_va_a_retenciones_de_iva():
    r = clasificar_cuenta(
        _perfil("2.1.7.3.2", "Ret. 70% Servicios", prefijos_asiento={"RET": 149})
    )
    assert r.categoria == "RET_IVA"
    assert r.tarifa == 70.0


def test_retencion_del_10_por_ciento_va_a_retenciones_de_renta():
    r = clasificar_cuenta(
        _perfil("2.1.7.2.5", "Ret. 10% Honorarios Profesionales y Dietas",
                prefijos_asiento={"RET": 889})
    )
    assert r.categoria == "RET_RENTA"
    assert r.tarifa == 10.0


def test_el_historial_gana_aunque_las_reglas_digan_otra_cosa():
    r = clasificar_cuenta(
        _perfil("1.1.5.1.1", "IVA sobre Compras"),
        historial={"1.1.5.1.1": "IVA_DIFERIDO"},
    )
    assert r.categoria == "IVA_DIFERIDO"
    assert r.confianza == "alta"
    assert r.origen == "historial"


def test_una_cuenta_irreconocible_queda_en_baja_confianza():
    r = clasificar_cuenta(_perfil("9.9.9", "Cuenta puente varios"))
    assert r.confianza == "baja"


def test_el_resultado_explica_por_que():
    r = clasificar_cuenta(_perfil("1.1.5.1.1", "IVA sobre Compras"))
    assert any("nombre" in m.lower() for m in r.justificacion)
    assert r.puntajes["IVA_COMPRAS"] > 0


def test_la_segunda_pasada_propaga_la_categoria_a_las_hermanas():
    """2.1.7.2.11 no tiene tarifa en el nombre; sus hermanas la resuelven."""
    perfiles = {
        "2.1.7.2.5": _perfil("2.1.7.2.5", "Ret. 10% Honorarios Profesionales",
                             prefijos_asiento={"RET": 889}),
        "2.1.7.2.8": _perfil("2.1.7.2.8", "Ret. 2.75% Servicios",
                             prefijos_asiento={"RET": 170}),
        "2.1.7.2.11": _perfil("2.1.7.2.11", "Retencion imptos relacion dependencia",
                              prefijos_asiento={"NOM": 18}),
    }
    resultados = {r.codigo: r for r in clasificar(perfiles)}
    assert resultados["2.1.7.2.11"].categoria == "RET_RENTA"


def test_clasificar_cuenta_guarda_tambien_las_senales_negativas():
    """Defecto 5: las penalizaciones (puntaje < 0) son la señal mas
    informativa para el auditor ('saldo deudor contradice naturaleza
    ingreso') y hoy se descartaban al guardar el resultado."""
    r = clasificar_cuenta(
        _perfil("4.1.1.4", "Venta de insumos odontologicos", debe=100.0)
    )
    negativas = [s for s in r.senales if s.puntaje < 0]
    assert negativas, "las señales negativas (penalizaciones) deben conservarse"


def test_clasificar_devuelve_un_resultado_por_cuenta():
    perfiles = {
        "1.1.5.1.1": _perfil("1.1.5.1.1", "IVA sobre Compras"),
        "4.1.1.4": _perfil("4.1.1.4", "Venta de insumos odontologicos"),
    }
    assert len(clasificar(perfiles)) == 2
