"""Pruebas del motor de pérdida esperada de cartera comercial (NIIF 9).

Incluye la prueba de aceptación: con los parámetros del archivo del cliente, el
motor debe reproducir su pérdida esperada al centavo.
"""
import pytest

from backend.app.aud.pce_cxc.motor import (
    ParametrosECL, evaluar_individual, medir_ecl, promediar_tasas, redondear, resumen_deterioro,
    tasa_perdida,
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


def test_el_resumen_informa_la_exposicion_que_no_pudo_medirse():
    p = ParametrosECL(tasas_perdida={"Corriente": 0.02}, lgd=1.0)
    r = resumen_deterioro({"Corriente": 100000.0, "361+": 50000.0}, p)
    assert r["exposicion_total"] == pytest.approx(150000.0)
    assert r["exposicion_sin_medir"] == pytest.approx(50000.0)
    assert r["exposicion_medida"] == pytest.approx(100000.0)
    assert r["medicion_completa"] is False
    # El porcentaje se mide sobre lo medido, no sobre una base diluida.
    assert r["porcentaje_sobre_cartera"] == pytest.approx(0.02)


def test_cuando_todo_se_mide_la_medicion_es_completa():
    p = ParametrosECL(tasas_perdida={"Corriente": 0.02}, lgd=1.0)
    r = resumen_deterioro({"Corriente": 100000.0}, p)
    assert r["exposicion_sin_medir"] == pytest.approx(0.0)
    assert r["medicion_completa"] is True
    assert r["porcentaje_sobre_cartera"] == pytest.approx(0.02)


def test_la_conciliacion_compara_el_total_de_la_cartera():
    p = ParametrosECL(tasas_perdida={"Corriente": 0.02}, lgd=1.0)
    r = resumen_deterioro({"Corriente": 100000.0}, p, saldo_contable=100000.0)
    assert r["conciliacion"]["cartera_total"] == pytest.approx(100000.0)
    assert r["conciliacion"]["cuadra"] is True


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


# ---------------------------------------------------------------------------
# Cotas de NIIF 9: la corrección de valor no puede ser negativa ni superar el
# importe en libros bruto de la banda (B5.5.35)
# ---------------------------------------------------------------------------

def test_una_banda_con_exposicion_negativa_no_produce_perdida_negativa():
    """Una nota de crédito entra a la matriz como exposición negativa. Sin piso,
    su "pérdida" negativa neutraliza en silencio la pérdida medida en las demás
    bandas del mismo segmento."""
    p = ParametrosECL(tasas_perdida={"0 a 30 días": 0.10}, lgd=1.0)
    r = medir_ecl({"0 a 30 días": -50000.0}, p)
    fila = r["tramos"][0]
    assert fila["ecl"] == pytest.approx(0.0)
    assert fila["ecl_sin_acotar"] == pytest.approx(-5000.0)
    assert fila["acotado"] == "piso_cero"
    assert r["ecl_total"] == pytest.approx(0.0)
    # El acotamiento no se hace en silencio: queda declarado y se puede sumar.
    assert r["exposicion_negativa"] == pytest.approx(-50000.0)
    assert r["ecl_acotada_por_piso"] == pytest.approx(5000.0)


def test_una_nota_de_credito_no_compensa_la_perdida_de_otra_banda():
    p = ParametrosECL(tasas_perdida={"0 a 30 días": 0.10, "91 a 180 días": 0.50}, lgd=1.0)
    r = medir_ecl({"0 a 30 días": -50000.0, "91 a 180 días": 100000.0}, p)
    assert r["ecl_total"] == pytest.approx(50000.0)


def test_el_factor_prospectivo_no_lleva_la_perdida_sobre_el_importe_en_libros():
    """Con factor 12,0 la tasa 0,10 se convertía en 1,20 y la PCE daba 240.000
    sobre una exposición de 200.000 (cobertura del 120 %). B5.5.35 mide sobre el
    importe en libros bruto."""
    p = ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=1.0, ajuste_prospectivo=11.0,
                      justificacion_ajuste="Escenario severo documentado por el socio")
    r = medir_ecl({"1-60": 200000.0}, p)
    fila = r["tramos"][0]
    assert fila["tasa_ajustada_sin_acotar"] == pytest.approx(1.20)
    assert fila["tasa_ajustada"] == pytest.approx(1.0)
    assert fila["ecl"] == pytest.approx(200000.0)
    assert fila["acotado"] == "tasa_maxima"
    assert r["ecl_total"] <= r["exposicion_total"]
    assert r["ecl_acotada_por_techo"] == pytest.approx(40000.0)


def test_un_factor_prospectivo_negativo_se_rechaza_con_un_mensaje_accionable():
    with pytest.raises(ValueError) as e:
        ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=1.0, ajuste_prospectivo=-2.0,
                      justificacion_ajuste="Reversión esperada")
    mensaje = str(e.value).lower()
    assert "prospectivo" in mensaje and "negativo" in mensaje


def test_un_factor_prospectivo_de_cero_se_rechaza_con_un_mensaje_accionable():
    """Un factor de 0,000 no es un ajuste prospectivo: anula la pérdida esperada
    ENTERA (toda banda en 0,00 cualquiera que sea su tasa observada) y archiva
    un papel que afirma que no hay pérdida. B5.5.51-52 pide ajustar la tasa
    histórica por las previsiones, no sustituirla por cero.

    El servicio lo rechaza antes de llegar aquí, así que sin esta prueba el
    guarda del motor quedaba sin cubrir: quitarlo dejaba toda la suite en
    verde."""
    with pytest.raises(ValueError) as e:
        ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=1.0, ajuste_prospectivo=-1.0,
                      justificacion_ajuste="Contracción del sector prevista")
    mensaje = str(e.value)
    assert "0,000" in mensaje
    assert "cero" in mensaje.lower()


def test_un_ajuste_prospectivo_no_numerico_se_rechaza():
    with pytest.raises(ValueError, match="prospectivo"):
        ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=1.0, ajuste_prospectivo="mucho",
                      justificacion_ajuste="x")


def test_sin_acotamiento_los_campos_nuevos_quedan_neutros():
    p = ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=1.0)
    r = medir_ecl({"1-60": 100000.0}, p)
    assert r["tramos"][0]["acotado"] is None
    assert r["tramos"][0]["ecl_sin_acotar"] == pytest.approx(10000.0)
    assert r["exposicion_negativa"] == pytest.approx(0.0)
    assert r["ecl_acotada_por_piso"] == pytest.approx(0.0)
    assert r["ecl_acotada_por_techo"] == pytest.approx(0.0)


def test_un_caso_individual_con_saldo_acreedor_se_mide_en_cero():
    """Un cliente cuyo saldo neto es acreedor (nota de crédito) no genera
    "ganancia esperada": su corrección de valor es 0,00 y la corrida no aborta."""
    r = evaluar_individual([{"identificacion": "NC", "saldo": -1000.0,
                             "recuperacion_estimada": -1000.0}])
    assert r["casos"][0]["ecl"] == pytest.approx(0.0)
    assert r["ecl_total"] == pytest.approx(0.0)


def test_la_recuperacion_que_supera_al_saldo_sigue_siendo_un_error_accionable():
    with pytest.raises(ValueError) as e:
        evaluar_individual([{"identificacion": "X", "saldo": 100.0,
                             "recuperacion_estimada": 150.0}])
    assert "X" in str(e.value)


# ---------------------------------------------------------------------------
# I8 — El resumen del motor es el que usa producción: medición por segmento,
# deducción de los casos individuales de CADA banda en la que tienen saldo, y
# el saldo individual sin tasa contado como exposición sin medir.
# ---------------------------------------------------------------------------

def _parametros_por_segmento():
    return {
        "NO-RELACIONADOS": ParametrosECL(
            tasas_perdida={"0 a 30 días": 0.10, "Más de 730 días": 0.50}, lgd=1.0),
        "RELACIONADOS": ParametrosECL(
            tasas_perdida={"0 a 30 días": 0.02}, lgd=1.0),
    }


def test_el_resumen_mide_cada_segmento_con_sus_propios_parametros():
    """Terceros y relacionadas no comparten matriz (NIIF 9 B5.5.35)."""
    r = resumen_deterioro(
        exposiciones={"NO-RELACIONADOS": {"0 a 30 días": 100000.0, "Más de 730 días": 50000.0},
                      "RELACIONADOS": {"0 a 30 días": 200000.0}},
        parametros=_parametros_por_segmento(),
    )
    por_clave = {(t["segmento"], t["tramo"]): t for t in r["colectivo"]["tramos"]}
    assert por_clave[("NO-RELACIONADOS", "0 a 30 días")]["ecl"] == pytest.approx(10000.0)
    assert por_clave[("NO-RELACIONADOS", "Más de 730 días")]["ecl"] == pytest.approx(25000.0)
    assert por_clave[("RELACIONADOS", "0 a 30 días")]["ecl"] == pytest.approx(4000.0)
    assert r["colectivo"]["ecl_total"] == pytest.approx(39000.0)
    assert r["exposicion_total"] == pytest.approx(350000.0)
    assert r["medicion_completa"] is True


def test_el_caso_individual_se_deduce_de_cada_banda_en_la_que_tiene_saldo():
    """Un cliente evaluado individualmente reparte su saldo en varias bandas."""
    r = resumen_deterioro(
        exposiciones={"NO-RELACIONADOS": {"0 a 30 días": 100000.0, "Más de 730 días": 50000.0},
                      "RELACIONADOS": {"0 a 30 días": 200000.0}},
        parametros=_parametros_por_segmento(),
        casos_individuales=[{"identificacion": "MEGA", "segmento": "NO-RELACIONADOS",
                             "saldo": 70000.0, "ecl": 30000.0,
                             "bandas": {"0 a 30 días": 20000.0, "Más de 730 días": 50000.0}}],
    )
    por_clave = {(t["segmento"], t["tramo"]): t for t in r["colectivo"]["tramos"]}
    assert por_clave[("NO-RELACIONADOS", "0 a 30 días")]["exposicion"] == pytest.approx(80000.0)
    assert por_clave[("NO-RELACIONADOS", "Más de 730 días")]["exposicion"] == pytest.approx(0.0)
    # La cartera no se mide dos veces: el total sigue siendo el de origen.
    assert r["exposicion_total"] == pytest.approx(350000.0)


def test_los_casos_individuales_que_superan_su_tramo_son_un_error_accionable():
    with pytest.raises(ValueError, match="superan su exposición"):
        resumen_deterioro(
            exposiciones={"NO-RELACIONADOS": {"0 a 30 días": 100000.0, "Más de 730 días": 50000.0},
                          "RELACIONADOS": {"0 a 30 días": 200000.0}},
            parametros=_parametros_por_segmento(),
            casos_individuales=[{"identificacion": "MEGA", "segmento": "NO-RELACIONADOS",
                                 "saldo": 500000.0, "ecl": 0.0,
                                 "bandas": {"0 a 30 días": 500000.0}}],
        )


def test_el_saldo_individual_sin_tasa_es_exposicion_sin_medir():
    """Un caso individual en una banda sin tasa no está medido en 0,00: está sin medir."""
    r = resumen_deterioro(
        exposiciones={"NO-RELACIONADOS": {"0 a 30 días": 100000.0, "Sin historia": 40000.0},
                      "RELACIONADOS": {"0 a 30 días": 0.0}},
        parametros={
            "NO-RELACIONADOS": ParametrosECL(tasas_perdida={"0 a 30 días": 0.10}, lgd=1.0),
            "RELACIONADOS": ParametrosECL(tasas_perdida={"0 a 30 días": 0.02}, lgd=1.0),
        },
        casos_individuales=[{"identificacion": "OMEGA", "segmento": "NO-RELACIONADOS",
                             "saldo": 40000.0, "ecl": 0.0, "saldo_sin_tasa": 40000.0,
                             "bandas": {"Sin historia": 40000.0}}],
    )
    assert r["individual"]["saldo_sin_tasa_total"] == pytest.approx(40000.0)
    assert r["exposicion_sin_medir"] == pytest.approx(40000.0)
    assert r["exposicion_medida"] == pytest.approx(100000.0)
    assert r["medicion_completa"] is False
    assert r["porcentaje_sobre_cartera"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# I10 — El cuadro tributario compara la PCE acumulada contra el tope del 10 %.
# ---------------------------------------------------------------------------

def test_el_cuadro_tributario_compara_contra_el_tope_acumulado_del_10_por_ciento():
    p = ParametrosECL(tasas_perdida={"Corriente": 0.15}, lgd=1.0)
    r = resumen_deterioro(exposiciones={"Corriente": 1000000.0}, parametros=p)
    t = r["tributario"]
    assert t["tope_acumulado_10pct"] == pytest.approx(100000.0)
    assert t["excede_tope_acumulado"] is True
    assert t["exceso_sobre_tope_acumulado"] == pytest.approx(50000.0)


def test_dentro_del_tope_acumulado_no_hay_exceso():
    p = ParametrosECL(tasas_perdida={"Corriente": 0.01}, lgd=1.0)
    r = resumen_deterioro({"Corriente": 1000000.0}, p)
    assert r["tributario"]["excede_tope_acumulado"] is False
    assert r["tributario"]["exceso_sobre_tope_acumulado"] == pytest.approx(0.0)


def test_el_limite_anual_del_1_por_ciento_no_se_calcula_sin_el_movimiento_de_la_provision():
    """El 1 % limita la provisión DEL EJERCICIO; la herramienta no recibe su
    movimiento, así que lo declara en vez de restar un flujo de un stock."""
    p = ParametrosECL(tasas_perdida={"Corriente": 0.15}, lgd=1.0)
    t = resumen_deterioro({"Corriente": 1000000.0}, p)["tributario"]
    assert t["provision_del_ejercicio"] is None
    assert t["limite_ejercicio_verificable"] is False
    # El 1 % de la cartera se conserva como referencia, pero ya no se compara
    # contra la PCE acumulada.
    assert t["limite_ejercicio_1pct"] == pytest.approx(10000.0)
    assert "excede_limite_ejercicio" not in t


def test_el_cero_negativo_no_llega_al_papel():
    """`-0,00` no es un importe: aparecía al multiplicar una banda acreedora por
    una tasa de política del 0 %."""
    assert redondear(-34339.62 * 0.0) == 0.0
    assert str(redondear(-0.001)) == "0.0"
    assert redondear(-0.006) == -0.01


# ---------------------------------------------------------------------------
# T9 — El reparto de centavos no puede inventar una banda acreedora
# ---------------------------------------------------------------------------

def test_el_reparto_de_centavos_no_inventa_una_banda_acreedora():
    """Con sobrante negativo el reparto ordenaba por resto ascendente, así que
    las bandas VACÍAS (resto 0) iban primero y se quedaban en -0,01. Esa banda
    entra en la matriz, se imprime en 05-Matriz y dispara el hallazgo Alto
    «Saldos acreedores en la cartera medida» sobre un centavo que puso la
    propia herramienta."""
    p = ParametrosECL(tasas_perdida={"A": 0.1, "B": 0.1, "C": 0.1, "D": 0.1})
    r = resumen_deterioro({"A": 50.006, "B": 50.006, "C": 0.0, "D": 0.0}, p)
    colectivo = r["colectivo"]

    assert colectivo["exposicion_negativa"] == 0.0, "el reparto creó una banda acreedora"
    acreedoras = [t["tramo"] for t in colectivo["tramos"] if t["exposicion"] < 0]
    assert not acreedoras, f"bandas acreedoras inventadas: {acreedoras}"
    # Y el centavo sigue repartiéndose: el total no se desancla.
    assert colectivo["exposicion_total"] == 100.01


def test_el_centavo_se_quita_de_una_banda_que_puede_absorberlo():
    """No basta con no dejar la banda en negativo: el total tiene que seguir
    cuadrando, así que el centavo va a una banda con saldo suficiente."""
    p = ParametrosECL(tasas_perdida={"A": 0.1, "B": 0.1, "C": 0.1, "D": 0.1})
    r = resumen_deterioro({"A": 50.006, "B": 50.006, "C": 0.0, "D": 0.0}, p)
    exposiciones = {t["tramo"]: t["exposicion"] for t in r["colectivo"]["tramos"]}
    assert exposiciones["C"] == 0.0 and exposiciones["D"] == 0.0
    assert sorted((exposiciones["A"], exposiciones["B"])) == [50.0, 50.01]


def test_el_reparto_solo_toca_bandas_acreedoras_si_no_hay_otra():
    """Cuando ninguna banda puede absorber el centavo, el total manda: se
    reparte igual -el papel no puede descuadrar contra los EEFF- y la bitácora
    lo declara."""
    p = ParametrosECL(tasas_perdida={"A": 0.1, "B": 0.1})
    r = resumen_deterioro({"A": -50.006, "B": -50.006}, p)
    # -100,012 redondea a -100,01, y la suma de las bandas redondeadas es
    # -100,02: falta un centavo y las dos bandas ya son acreedoras.
    assert r["colectivo"]["exposicion_total"] == -100.01


# ---------------------------------------------------------------------------
# T11 — La línea que redondea la exposición ANTES de medir (motor.py:186)
#       no la cubría ninguna prueba: sustituirla por `float(saldo or 0)`
#       dejaba las 216 pruebas en verde.
# ---------------------------------------------------------------------------

def test_la_exposicion_se_redondea_antes_de_multiplicarla_por_la_tasa():
    """El papel imprime la exposición REDONDEADA, así que la pérdida tiene que
    salir de ESA cifra: exposición impresa x tasa impresa = pérdida impresa.

    Con 1.000,005 al 50 %, medir sobre el saldo sin redondear da 500,0025 ->
    500,00; medir sobre la exposición ya redondeada (1.000,01) da 500,005 ->
    500,01. Un centavo de diferencia entre lo que el papel muestra y lo que la
    corrida archiva, que es exactamente lo que el redondeo previo evita.
    """
    p = ParametrosECL(tasas_perdida={"Corriente": 0.5})
    fila = medir_ecl({"Corriente": 1000.005}, p)["tramos"][0]

    assert fila["exposicion"] == 1000.01, "la exposición impresa va redondeada a centavos"
    assert fila["ecl"] == 500.01, (
        "la pérdida tiene que salir de la exposición redondeada: "
        f"{fila['exposicion']} x 0,50 = 500,005 -> 500,01, no 500,00")
    # Y quien rehaga la cuenta desde el papel llega al mismo número.
    assert redondear(fila["exposicion"] * fila["tasa_ajustada"]) == fila["ecl"]


def test_el_total_medido_es_la_suma_de_las_bandas_redondeadas():
    """Redondear después de sumar y sumar las redondeadas no dan lo mismo: el
    papel suma lo que imprime."""
    p = ParametrosECL(tasas_perdida={"A": 0.5, "B": 0.5})
    medido = medir_ecl({"A": 1000.005, "B": 1000.005}, p)
    assert [t["exposicion"] for t in medido["tramos"]] == [1000.01, 1000.01]
    assert medido["ecl_total"] == 1000.02
    assert medido["exposicion_total"] == 2000.02
