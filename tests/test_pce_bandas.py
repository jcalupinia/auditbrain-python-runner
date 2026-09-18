"""Bandas de mora del papel de trabajo de cuentas por cobrar."""
import pytest

from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO, clasificar, desdoblar


def test_una_factura_no_vencida_esta_por_vencer():
    assert clasificar(0, BANDAS_POR_DEFECTO) == "Por vencer"
    assert clasificar(-30, BANDAS_POR_DEFECTO) == "Por vencer"


def test_limites_de_cada_banda():
    casos = {1: "0 a 30 días", 30: "0 a 30 días", 31: "31 a 60 días", 60: "31 a 60 días",
             61: "61 a 90 días", 90: "61 a 90 días", 91: "91 a 180 días", 180: "91 a 180 días",
             181: "181 a 360 días", 360: "181 a 360 días", 361: "Más de 360 días", 5000: "Más de 360 días"}
    for dias, esperado in casos.items():
        assert clasificar(dias, BANDAS_POR_DEFECTO) == esperado, dias


def test_la_banda_abierta_se_desdobla_en_el_umbral():
    b = desdoblar(BANDAS_POR_DEFECTO, 730)
    assert [x["nombre"] for x in b][-2:] == ["361 a 730 días", "Más de 730 días"]
    assert clasificar(500, b) == "361 a 730 días"
    assert clasificar(731, b) == "Más de 730 días"


def test_la_banda_desdoblada_recuerda_su_banda_de_origen():
    b = desdoblar(BANDAS_POR_DEFECTO, 730)
    assert b[-1]["origen"] == "Más de 360 días"
    assert b[-2]["origen"] == "Más de 360 días"


def test_no_se_desdobla_si_el_umbral_cae_fuera_de_la_banda_abierta():
    assert desdoblar(BANDAS_POR_DEFECTO, 200) == BANDAS_POR_DEFECTO


def test_dias_sin_banda_es_error():
    with pytest.raises(ValueError):
        clasificar(50, [{"nombre": "1 a 30", "desde": 1, "hasta": 30, "origen": "1 a 30"}])


def test_los_nombres_de_banda_estan_fijados_porque_la_pantalla_los_repite():
    """La pantalla pide la política del cliente banda por banda y arma los
    mismos nombres en `frontend/src/aud/pceCxc.js::bandasDeLaPolitica`. Si un
    nombre cambia aquí sin cambiarlo allá, esa banda llega al servicio sin
    política y queda «sin comparar» en silencio."""
    assert [b["nombre"] for b in desdoblar(BANDAS_POR_DEFECTO, 730)] == [
        "Por vencer", "0 a 30 días", "31 a 60 días", "61 a 90 días", "91 a 180 días",
        "181 a 360 días", "361 a 730 días", "Más de 730 días",
    ]
    # Un umbral que no supera el inicio de la banda abierta no la desdobla.
    assert [b["nombre"] for b in desdoblar(BANDAS_POR_DEFECTO, 361)][-1] == "Más de 360 días"
