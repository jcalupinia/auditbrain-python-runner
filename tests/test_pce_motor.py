"""Pruebas del motor de pérdida esperada de cartera comercial (NIIF 9).

Incluye la prueba de aceptación: con los parámetros del archivo del cliente, el
motor debe reproducir su pérdida esperada al centavo.
"""
import pytest

from backend.app.aud.pce_cxc.motor import (
    ParametrosECL, evaluar_individual, medir_ecl, promediar_tasas, resumen_deterioro, tasa_perdida,
)

TRAMOS = ["Corriente", "1-60", "61-180", "181-365", ">365"]

# --- Parámetros tal como están en el archivo del cliente (cartera 2025) ---
EAD_ARCHIVO = {"Corriente": 6859858.669999972, "1-60": 1415098.0, "61-180": 130224.0,
               "181-365": 31304.13, ">365": 526094.41}
PD_ARCHIVO = {"Corriente": 0.01, "1-60": 0.01, "61-180": 0.10233602736990051,
              "181-365": 0.25102458128088406, ">365": 0.7408857024980379}
HORIZONTE = {"Corriente": 1.1700932934255743, "1-60": 0.41168258539212843,
             "61-180": 0.7484791462993428, "181-365": 1.4939591597334276,
             ">365": 2.695890410958904}
LGD_ARCHIVO = 0.505612671307418

# --- La misma cartera medida sobre el saldo pendiente ---
SALDO = {"Corriente": 3903650.55, "1-60": 254409.97, "61-180": 50125.42,
         "181-365": 23768.42, ">365": 526094.41}
TASA_HISTORICA = {"Corriente": 0.006509110090326554, "1-60": 0.0064031553811007376,
                  "61-180": 0.10233602736990051, "181-365": 0.25102458128088406,
                  ">365": 0.7408857024980379}


# ---------------------------------------------------------------------------
# Tasa de pérdida a partir de las cohortes
# ---------------------------------------------------------------------------

def test_tasa_de_perdida_de_una_cohorte():
    # Cartera inicial 50.000, de la que quedó impaga/castigada 500 -> 1 %.
    assert tasa_perdida(inicial=50000, castigado=500) == pytest.approx(0.01)


def test_tasa_de_perdida_exige_cartera_inicial():
    with pytest.raises(ValueError):
        tasa_perdida(inicial=0, castigado=100)


def test_tasa_de_perdida_no_puede_ser_negativa_por_ruido_de_calculo():
    # En el archivo del cliente una cohorte da -0,0000000013 por coma flotante.
    assert tasa_perdida(inicial=5975641.71, castigado=-1.3153567124390975e-09) == 0.0


def test_promedio_de_cohortes():
    tasas = promediar_tasas([{"61-180": 0.0226759}, {"61-180": 0.1819961}])
    assert tasas["61-180"] == pytest.approx(0.102336, abs=1e-6)


# ---------------------------------------------------------------------------
# Medición colectiva
# ---------------------------------------------------------------------------

def test_matriz_sin_descuento_es_saldo_por_tasa_por_lgd():
    p = ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=0.5)
    r = medir_ecl({"1-60": 100000.0}, p)
    assert r["tramos"][0]["ecl"] == pytest.approx(5000.0)
    assert r["ecl_total"] == pytest.approx(5000.0)
    assert r["tramos"][0]["factor_descuento"] == 1.0


def test_el_ajuste_prospectivo_exige_justificacion():
    with pytest.raises(ValueError) as e:
        ParametrosECL(tasas_perdida={"1-60": 0.1}, lgd=1.0, ajuste_prospectivo=0.15)
    assert "justificación" in str(e.value).lower()


def test_el_ajuste_prospectivo_escala_la_tasa():
    p = ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=1.0, ajuste_prospectivo=0.20,
                      justificacion_ajuste="Deterioro esperado del sector comercial")
    r = medir_ecl({"1-60": 100000.0}, p)
    assert r["tramos"][0]["tasa_ajustada"] == pytest.approx(0.12)
    assert r["ecl_total"] == pytest.approx(12000.0)


def test_el_descuento_exige_tasa_y_horizonte():
    with pytest.raises(ValueError):
        ParametrosECL(tasas_perdida={"1-60": 0.1}, lgd=1.0, tasa_descuento=0.12)


def test_no_se_inventa_la_tasa_de_un_tramo_con_saldo():
    # Sin tasa aprobada, la banda no se mide con una tasa cero (eso afirmaría
    # que no hay pérdida): queda sin medir y su exposición se informa aparte.
    p = ParametrosECL(tasas_perdida={"Corriente": 0.01}, lgd=1.0)
    r = medir_ecl({"Corriente": 1000.0, ">365": 5000.0}, p)
    fila = next(t for t in r["tramos"] if t["tramo"] == ">365")
    assert fila["ecl"] is None
    assert fila["tasa_perdida"] is None
    assert r["exposicion_sin_medir"] == pytest.approx(5000.0)


def test_una_banda_sin_tasa_queda_sin_medir_y_no_en_cero():
    p = ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=1.0)
    r = medir_ecl({"1-60": 100000.0, "361+": 50000.0}, p)
    fila = next(t for t in r["tramos"] if t["tramo"] == "361+")
    assert fila["ecl"] is None
    assert r["exposicion_sin_medir"] == pytest.approx(50000.0)
    assert r["ecl_total"] == pytest.approx(10000.0)


# ---------------------------------------------------------------------------
# Evaluación individual (cartera en litigio / con deterioro crediticio)
# ---------------------------------------------------------------------------

def test_los_casos_individuales_se_miden_uno_por_uno():
    casos = [
        {"identificacion": "Cliente X · juicio 2024-0031", "saldo": 200000.0,
         "recuperacion_estimada": 50000.0},
        {"identificacion": "Cliente Y · concurso", "saldo": 66000.0,
         "recuperacion_estimada": 0.0},
    ]
    r = evaluar_individual(casos)
    assert r["saldo_total"] == pytest.approx(266000.0)
    assert r["ecl_total"] == pytest.approx(216000.0)
    assert r["casos"][0]["ecl"] == pytest.approx(150000.0)


def test_la_recuperacion_no_puede_superar_al_saldo():
    with pytest.raises(ValueError):
        evaluar_individual([{"identificacion": "X", "saldo": 100.0,
                             "recuperacion_estimada": 150.0}])


# ---------------------------------------------------------------------------
# Resumen: colectivo + individual + conciliación + tributario
# ---------------------------------------------------------------------------

def test_el_saldo_evaluado_individualmente_sale_de_la_matriz_colectiva():
    p = ParametrosECL(tasas_perdida=TASA_HISTORICA, lgd=1.0)
    r = resumen_deterioro(
        exposiciones=SALDO,
        parametros=p,
        casos_individuales=[{"identificacion": "Litigios", "saldo": 266000.0,
                             "recuperacion_estimada": 0.0, "tramo": ">365"}],
        saldo_contable=4758048.77,
    )
    # La matriz ya no mide los 266.000 que se evaluaron caso por caso.
    por_tramo = {t["tramo"]: t for t in r["colectivo"]["tramos"]}
    assert por_tramo[">365"]["exposicion"] == pytest.approx(260094.41)
    assert r["exposicion_total"] == pytest.approx(4758048.77)
    assert r["conciliacion"]["cuadra"] is True
    assert r["ecl_total"] == pytest.approx(
        r["colectivo"]["ecl_total"] + r["individual"]["ecl_total"]
    )


def test_el_cuadro_tributario_usa_los_limites_de_la_lorti():
    p = ParametrosECL(tasas_perdida={"Corriente": 0.01}, lgd=1.0)
    r = resumen_deterioro(exposiciones={"Corriente": 1000000.0}, parametros=p)
    assert r["tributario"]["limite_ejercicio_1pct"] == pytest.approx(10000.0)
    assert r["tributario"]["tope_acumulado_10pct"] == pytest.approx(100000.0)


# ---------------------------------------------------------------------------
# PRUEBA DE ACEPTACIÓN: reproducir el archivo del cliente
# ---------------------------------------------------------------------------

def test_reproduce_la_perdida_esperada_del_archivo_del_cliente():
    p = ParametrosECL(
        tasas_perdida=PD_ARCHIVO,
        lgd=LGD_ARCHIVO,
        tasa_descuento=0.1233,
        horizontes=HORIZONTE,
    )
    r = medir_ecl(EAD_ARCHIVO, p)
    esperado = {"Corriente": 30272.51, "1-60": 6820.50, "61-180": 6176.50,
                "181-365": 3339.62, ">365": 144046.20}
    for tramo in TRAMOS:
        obtenido = next(t for t in r["tramos"] if t["tramo"] == tramo)["ecl"]
        assert obtenido == pytest.approx(esperado[tramo], abs=0.01), tramo
    assert r["ecl_total"] == pytest.approx(190655.33, abs=0.01)


def test_la_misma_cartera_bajo_el_criterio_niif9():
    """Saldo pendiente, sin descuento, con la recuperación observada (0 %)."""
    p = ParametrosECL(tasas_perdida=TASA_HISTORICA, lgd=1.0)
    r = medir_ecl(SALDO, p)
    assert r["ecl_total"] == pytest.approx(427910.25, abs=0.01)
    assert r["ecl_total"] / sum(SALDO.values()) == pytest.approx(0.0899, abs=0.0001)
