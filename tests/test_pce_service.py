"""Servicio que orquesta el análisis completo de pérdidas esperadas."""
import io
from datetime import date

import pytest
from openpyxl import Workbook

from backend.app.aud.pce_cxc.service import analizar


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Documento", "Tipo", "Emisión", "Vencimiento", "Saldo"])
    for f in filas:
        ws.append(list(f))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _cortes():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0),
                 ("BETA", "F-2", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 3, 1), 50000.0)])
    c24 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 20000.0)])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0),
                 ("GAMMA", "F-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 200000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_mide_la_cartera_con_las_tasas_de_la_cohorte():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    # F-1 estaba en "0 a 30 días" en 2023 con 100.000 y quedaron vivos 10.000 -> 10 %
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(0.10)
    # F-9 (200.000, 30 días de mora) se mide al 10 %; F-1 cayó en "Más de 730 días",
    # banda sin historia en la cohorte, así que queda sin medir y no suma cero.
    assert r["matriz"]["ecl_total"] == pytest.approx(20000.0)
    assert r["matriz"]["exposicion_sin_medir"] == pytest.approx(10000.0)


def test_el_saldo_contable_manda_sobre_el_archivo_y_la_diferencia_se_informa():
    r = analizar(_cortes(), {"eeff": {"no_relacionados": 220000.0, "relacionados": 0.0}})
    # La exposición se ancla a los estados financieros y la conciliación cierra...
    assert r["exposicion"]["total"] == pytest.approx(220000.0)
    assert r["conciliacion"]["cuadra"] is True
    # ...pero la diferencia contra el archivo queda a la vista como partida conciliatoria.
    assert r["exposicion"]["segun_archivo"] == pytest.approx(210000.0)
    assert r["exposicion"]["factores_anclaje"]["NO-RELACIONADOS"] == pytest.approx(220000 / 210000)


def test_el_factor_prospectivo_sin_justificacion_genera_hallazgo():
    r = analizar(_cortes(), {})
    titulos = [h["titulo"] for h in r["hallazgos"]]
    assert "Ausencia del componente prospectivo" in titulos


def test_sin_materialidad_no_concluye():
    r = analizar(_cortes(), {})
    assert any(p["variable"] == "Materialidad de desempeño" for p in r["pendientes"])


def test_exige_los_tres_cortes():
    with pytest.raises(ValueError, match="tres"):
        analizar(_cortes()[:2], {})


def _cortes_anomalia():
    # DELTA / F-7 crece de 1.000 (cohorte, 2023) a 5.000 (corte actual, 2025):
    # el remanente supera al inicial, lo que dispara la anomalía de la cohorte
    # (tasas_por_permanencia la acota a 1.0 y la deja registrada).
    c23 = _xlsx([("DELTA", "F-7", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 11, 1), 1000.0)])
    c24 = _xlsx([("DELTA", "F-7", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 11, 1), 3000.0)])
    c25 = _xlsx([("DELTA", "F-7", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 11, 1), 5000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_las_anomalias_de_cohorte_se_exponen_y_generan_pendiente():
    r = analizar(_cortes_anomalia(), {})
    assert len(r["anomalias"]) == 1
    anomalia = r["anomalias"][0]
    assert anomalia["tipo"] == "remanente_mayor_que_inicial"
    assert anomalia["segmento"] == "NO-RELACIONADOS"

    variables = [p["variable"] for p in r["pendientes"]]
    assert "Tasas de cohorte fuera de rango" in variables
    pendiente = next(p for p in r["pendientes"] if p["variable"] == "Tasas de cohorte fuera de rango")
    assert pendiente["responsable"] == "Gerente / Socio"
    assert pendiente["criticidad"] == "Alta"


def _cortes_banda_medida_en_un_segmento_y_sin_historia_en_el_otro():
    # NO-RELACIONADOS tiene historia en "0 a 30 días" (H-1: de 100.000 a 10.000 ->
    # tasa observada 10 %). RELACIONADOS no tiene ni una fila en la cohorte, así
    # que ninguna de sus bandas tiene tasa. Ambos segmentos exponen saldo en
    # "0 a 30 días" en el corte actual: terceros 200.000 (medido, ECL 20.000) y
    # relacionadas 700.000 (sin medir). Si la política diluyera lo no medido en el
    # denominador, la tasa observada de la fila bajaría de 10 % a 900.000/20.000≈2,2 %.
    cohorte = _xlsx([
        ("HIST", "H-1", "NO-RELACIONADOS", date(2020, 1, 1), date(2020, 1, 15), 100000.0),
    ])
    intermedio = _xlsx([])
    actual = _xlsx([
        ("HIST", "H-1", "NO-RELACIONADOS", date(2020, 1, 1), date(2020, 1, 15), 10000.0),
        ("TERCERO", "T-1", "NO-RELACIONADOS", date(2025, 1, 1), date(2025, 1, 15), 200000.0),
        ("RELACIONADA", "R-1", "RELACIONADOS", date(2025, 1, 1), date(2025, 1, 15), 700000.0),
    ])
    return [{"nombre": "cohorte.xlsx", "contenido": cohorte, "fecha": date(2020, 1, 31)},
            {"nombre": "intermedio.xlsx", "contenido": intermedio, "fecha": date(2020, 6, 30)},
            {"nombre": "actual.xlsx", "contenido": actual, "fecha": date(2025, 1, 31)}]


def test_la_comparacion_contra_la_politica_no_diluye_lo_no_medido():
    # La política del cliente se ingresa: el 0 % de esta banda es una afirmación
    # suya, no un hueco que el sistema rellene (C2).
    r = analizar(_cortes_banda_medida_en_un_segmento_y_sin_historia_en_el_otro(),
                 {"politica": {"0 a 30 días": 0.0}})
    fila = next(f for f in r["politica"]["filas"] if f["banda"] == "0 a 30 días")

    assert fila["exposicion"] == pytest.approx(900000.0)
    assert fila["exposicion_medida"] == pytest.approx(200000.0)
    assert fila["exposicion_sin_medir"] == pytest.approx(700000.0)
    assert fila["exposicion_medida"] + fila["exposicion_sin_medir"] == pytest.approx(fila["exposicion"])
    assert fila["ecl"] == pytest.approx(20000.0)
    # 20.000 / 200.000 (lo medido), no 20.000 / 900.000 (diluido con lo sin medir)
    assert fila["tasa_observada"] == pytest.approx(0.10)

    titulos = [h["titulo"] for h in r["hallazgos"]]
    assert "Política de deterioro no sustentada en el comportamiento observado" in titulos


def _cortes_individual_sin_tasa():
    # Cohorte vacía: ninguna banda de ningún segmento tiene tasa observada.
    cohorte = _xlsx([])
    intermedio = _xlsx([])
    actual = _xlsx([
        ("GRANDE", "G-1", "NO-RELACIONADOS", date(2024, 11, 1), date(2024, 12, 15), 1000000.0),
    ])
    return [{"nombre": "cohorte.xlsx", "contenido": cohorte, "fecha": date(2020, 1, 31)},
            {"nombre": "intermedio.xlsx", "contenido": intermedio, "fecha": date(2022, 1, 31)},
            {"nombre": "actual.xlsx", "contenido": actual, "fecha": date(2025, 1, 31)}]


def test_caso_individual_sin_tasa_no_reporta_perdida_cero_en_silencio():
    r = analizar(_cortes_individual_sin_tasa(), {"umbral_individual": 500000.0})
    caso = r["individual"]["casos"][0]
    assert "USD 1,000,000.00 sin medir por falta de tasa" in caso["sustento"]
    # El monto no solo vive dentro del texto del sustento: el Excel del papel
    # de trabajo lo necesita como campo numérico propio, no parseado de una frase.
    assert caso["saldo_sin_tasa"] == pytest.approx(1000000.0)

    assert r["exposicion"]["sin_medir"] == pytest.approx(1000000.0)
    suma_sin_tasa_casos = sum(c["saldo_sin_tasa"] for c in r["individual"]["casos"])
    assert suma_sin_tasa_casos + r["matriz"]["exposicion_sin_medir"] == pytest.approx(
        r["exposicion"]["sin_medir"])

    variables = [p["variable"] for p in r["pendientes"]]
    assert "Saldos individuales sin tasa aplicable" in variables
    pendiente = next(p for p in r["pendientes"] if p["variable"] == "Saldos individuales sin tasa aplicable")
    assert pendiente["responsable"] == "Gerente / Socio"
    assert pendiente["criticidad"] == "Alta"


def test_caso_individual_con_estimacion_propia_no_deja_saldo_sin_tasa():
    # Misma cartera del caso anterior (GRANDE, banda sin historia en la
    # cohorte), pero ahora con una estimación propia justificada: cubre todo
    # el caso y no debe quedar saldo sin medir.
    parametros = {
        "umbral_individual": 500000.0,
        "evaluaciones_individuales": {
            "NO-RELACIONADOS|GRANDE": {
                "ecl": 300000.0,
                "justificacion": "Informe legal Pérez & Asociados 2025-01-20: recupero estimado 70 %.",
            },
        },
    }
    r = analizar(_cortes_individual_sin_tasa(), parametros)
    caso = r["individual"]["casos"][0]
    assert caso["saldo_sin_tasa"] == pytest.approx(0.0)
    assert caso["sustento"] == parametros["evaluaciones_individuales"]["NO-RELACIONADOS|GRANDE"]["justificacion"]
    assert caso["ecl"] == pytest.approx(300000.0)

    suma_sin_tasa_casos = sum(c["saldo_sin_tasa"] for c in r["individual"]["casos"])
    assert suma_sin_tasa_casos + r["matriz"]["exposicion_sin_medir"] == pytest.approx(
        r["exposicion"]["sin_medir"])

    variables = [p["variable"] for p in r["pendientes"]]
    assert "Saldos individuales sin tasa aplicable" not in variables


# ---------------------------------------------------------------------------
# C1 - La cartera descartada por el lector no puede desaparecer
# ---------------------------------------------------------------------------

def _cortes_con_descartes():
    # Corte actual de tres filas: 1.000,00 validos, 750.000,00 sin numero de
    # documento y 1.250.000,00 sin fecha de vencimiento.
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)])
    c24 = _xlsx([])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 1000.0),
                 ("BETA", "", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 750000.0),
                 ("GAMA", "F-3", "NO-RELACIONADOS", date(2025, 9, 1), None, 1250000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_el_importe_descartado_en_la_lectura_no_desaparece_del_resultado():
    r = analizar(_cortes_con_descartes(), {})
    corte_actual = r["bitacora"]["cortes"][2]
    # El conteo sigue estando (lo usa 02-Fuentes)...
    assert corte_actual["descartados"] == 2
    # ...y ahora el importe tambien.
    assert corte_actual["descartados_importe"] == pytest.approx(2000000.0)
    assert corte_actual["cartera_no_leida"] == pytest.approx(2000000.0)
    por_motivo = {d["motivo"]: d["importe"] for d in corte_actual["descartados_por_motivo"]}
    assert por_motivo["sin número de documento"] == pytest.approx(750000.0)
    assert por_motivo["sin fecha de vencimiento"] == pytest.approx(1250000.0)
    assert r["exposicion"]["descartado_en_lectura"] == pytest.approx(2000000.0)


def test_el_anclaje_no_reparte_en_silencio_lo_que_el_lector_descarto():
    """Con anclaje, `factor = cartera_EEFF / total_del_archivo` absorbe el hueco:
    la exposicion perdida se convierte en exposicion inventada sobre las filas
    que si entraron. Eso tiene que quedar dicho en el papel."""
    r = analizar(_cortes_con_descartes(), {"eeff": {"no_relacionados": 5000.0, "relacionados": 0.0}})
    assert r["exposicion"]["factores_anclaje"]["NO-RELACIONADOS"] == pytest.approx(5.0)
    hallazgo = next(h for h in r["hallazgos"]
                    if h["titulo"] == "Cartera descartada en la lectura del corte actual")
    assert hallazgo["riesgo"] == "Alto"
    assert "anclaje" in hallazgo["efecto"].lower()


def test_sin_descartes_no_se_inventa_el_hallazgo():
    r = analizar(_cortes(), {})
    assert all(h["titulo"] != "Cartera descartada en la lectura del corte actual"
               for h in r["hallazgos"])
    assert r["exposicion"]["descartado_en_lectura"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# C3 - Una nota de credito no genera "ganancia esperada"
# ---------------------------------------------------------------------------

def _cortes_con_nota_de_credito():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)])
    c24 = _xlsx([])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0),
                 ("GAMMA", "F-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 200000.0),
                 ("GAMMA", "NC-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), -250000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_una_nota_de_credito_no_produce_perdida_esperada_negativa():
    r = analizar(_cortes_con_nota_de_credito(), {})
    banda = next(t for t in r["matriz"]["tramos"]
                 if t["segmento"] == "NO-RELACIONADOS" and t["tramo"] == "0 a 30 días")
    assert banda["exposicion"] == pytest.approx(-50000.0)
    assert banda["ecl"] == pytest.approx(0.0)
    assert banda["ecl_sin_acotar"] == pytest.approx(-5000.0)
    assert banda["acotado"] == "piso_cero"
    assert r["matriz"]["ecl_total"] >= 0
    assert r["ecl_total"] >= 0
    # El saldo acreedor se totaliza y se declara, no se disimula.
    assert r["matriz"]["exposicion_negativa"] == pytest.approx(-50000.0)
    assert r["matriz"]["ecl_acotada_por_piso"] == pytest.approx(5000.0)
    assert r["exposicion"]["negativa"] == pytest.approx(-50000.0)
    assert "Saldos acreedores en la cartera medida" in [h["titulo"] for h in r["hallazgos"]]


# ---------------------------------------------------------------------------
# C4 - Una nota de credito en un cliente de evaluacion individual no aborta
# ---------------------------------------------------------------------------

def _cortes_individual_con_nota_de_credito():
    # DELTA supera el umbral individual con 300.000 en una banda sin tasa
    # observada y una nota de credito de -100.000 en "0 a 30 dias" (tasa 10 %).
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)])
    c24 = _xlsx([])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0),
                 ("DELTA", "F-5", "NO-RELACIONADOS", date(2024, 1, 1), date(2024, 6, 1), 300000.0),
                 ("DELTA", "NC-5", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), -100000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_una_nota_de_credito_en_un_cliente_individual_no_aborta_la_corrida():
    r = analizar(_cortes_individual_con_nota_de_credito(), {"umbral_individual": 100000.0})
    caso = next(c for c in r["individual"]["casos"] if c["identificacion"].startswith("DELTA"))
    assert caso["saldo"] == pytest.approx(200000.0)
    assert caso["ecl"] == pytest.approx(0.0)
    assert caso["recuperacion_estimada"] == pytest.approx(200000.0)
    assert caso["ecl_sin_acotar"] == pytest.approx(-10000.0)
    assert caso["acotado"] == "piso_cero"
    assert r["individual"]["ecl_acotada_por_piso"] == pytest.approx(10000.0)


def test_una_evaluacion_individual_fuera_de_rango_es_un_error_accionable():
    """Aqui el dato SI lo ingreso el operador, asi que el mensaje tiene que
    decirle que corregir y entre que valores."""
    parametros = {
        "umbral_individual": 100000.0,
        "evaluaciones_individuales": {
            "NO-RELACIONADOS|DELTA": {"ecl": 900000.0, "justificacion": "Informe legal"},
        },
    }
    with pytest.raises(ValueError) as e:
        analizar(_cortes_individual_con_nota_de_credito(), parametros)
    mensaje = str(e.value)
    assert "DELTA" in mensaje
    assert "evaluaciones_individuales" in mensaje


# ---------------------------------------------------------------------------
# I6 - El umbral individual se compara contra el saldo anclado
# ---------------------------------------------------------------------------

def _cortes_umbral_anclado():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)])
    c24 = _xlsx([])
    c25 = _xlsx([("MEGA", "F-3", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 90000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_el_umbral_individual_se_compara_contra_el_saldo_anclado():
    """MEGA tiene 90.000 en el archivo y un factor de anclaje de 5,0: son
    450.000 de exposicion. Con umbral de 100.000 no puede quedarse en la matriz
    midiendose con el promedio de su banda."""
    r = analizar(_cortes_umbral_anclado(),
                 {"umbral_individual": 100000.0,
                  "eeff": {"no_relacionados": 450000.0, "relacionados": 0.0}})
    assert r["exposicion"]["factores_anclaje"]["NO-RELACIONADOS"] == pytest.approx(5.0)
    assert [c["identificacion"] for c in r["individual"]["casos"]] == ["MEGA (NO-RELACIONADOS)"]
    assert r["individual"]["saldo_total"] == pytest.approx(450000.0)
    assert r["matriz"]["exposicion_total"] == pytest.approx(0.0)


def test_sin_anclaje_el_umbral_individual_se_comporta_igual_que_antes():
    r = analizar(_cortes_umbral_anclado(), {"umbral_individual": 100000.0})
    assert r["individual"]["casos"] == []


# ---------------------------------------------------------------------------
# I12 - El numero de documento tiene que ser unico
# ---------------------------------------------------------------------------

def _cortes_documento_compartido():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)])
    c24 = _xlsx([])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0),
                 ("BETA", "F-1", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 40000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_un_numero_de_documento_compartido_por_dos_clientes_genera_pendiente():
    r = analizar(_cortes_documento_compartido(), {})
    assert r["documentos_ambiguos_total"] == 1
    assert r["documentos_ambiguos"][0]["documento"] == "F-1"
    pendiente = next(p for p in r["pendientes"]
                     if p["variable"] == "Número de documento no único")
    assert pendiente["criticidad"] == "Alta"


def test_con_numeros_unicos_no_hay_pendiente_de_documento_ambiguo():
    r = analizar(_cortes(), {})
    assert r["documentos_ambiguos_total"] == 0
    assert all(p["variable"] != "Número de documento no único" for p in r["pendientes"])


# ---------------------------------------------------------------------------
# M2 - Los parametros mal formados son error de entrada, no un 500
# ---------------------------------------------------------------------------

def test_un_factor_prospectivo_escalar_se_acepta_como_formato_antiguo():
    r = analizar(_cortes(), {"factor_prospectivo": 1.10,
                             "justificacion_prospectivo": "Proyeccion macro documentada"})
    assert r["matriz"]["ajuste_prospectivo"] == {"NO-RELACIONADOS": 1.10, "RELACIONADOS": 1.10}


@pytest.mark.parametrize("parametros,texto", [
    ({"factor_prospectivo": ["1.10"]}, "factor_prospectivo"),
    ({"tasas_sustitutas": "0.42"}, "tasas_sustitutas"),
    ({"tasas_sustitutas": {"NO-RELACIONADOS|0 a 30 días": "0.42"}}, "tasas_sustitutas"),
    ({"evaluaciones_individuales": [1, 2]}, "evaluaciones_individuales"),
    ({"eeff": [1, 2]}, "eeff"),
    ({"politica": "0.05"}, "politica"),
    ({"umbral_individual": "mucho"}, "umbral_individual"),
    ({"umbral_dias_incumplimiento": "dos años"}, "umbral_dias_incumplimiento"),
])
def test_un_parametro_mal_formado_es_error_de_entrada(parametros, texto):
    with pytest.raises(ValueError) as e:
        analizar(_cortes(), parametros)
    assert texto in str(e.value)


# ---------------------------------------------------------------------------
# M6 - Un umbral de incumplimiento en 0 no se convierte en 730
# ---------------------------------------------------------------------------

def test_un_umbral_de_incumplimiento_en_cero_no_se_convierte_en_730():
    with pytest.raises(ValueError) as e:
        analizar(_cortes(), {"umbral_dias_incumplimiento": 0})
    assert "umbral_dias_incumplimiento" in str(e.value)


def test_un_umbral_de_incumplimiento_explicito_se_respeta():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 365})
    assert r["bitacora"]["umbral_incumplimiento"] == 365


def test_sin_umbral_de_incumplimiento_se_usa_el_defecto_del_plan():
    r = analizar(_cortes(), {})
    assert r["bitacora"]["umbral_incumplimiento"] == 730


# ---------------------------------------------------------------------------
# I8 — El servicio mide con `motor.resumen_deterioro`, así que las invariantes
# que la suite verifica sobre el motor llegan al producto.
# ---------------------------------------------------------------------------

def test_el_resultado_declara_si_la_medicion_esta_completa():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    # F-1 quedó en "Más de 730 días", banda sin historia: la medición no es completa.
    assert r["medicion_completa"] is False
    assert r["exposicion"]["medida"] == pytest.approx(200000.0)


def test_el_porcentaje_sobre_cartera_se_calcula_sobre_lo_medido():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    # 20.000 de pérdida sobre 200.000 medidos: dividir entre los 210.000 totales
    # diluiría el porcentaje justo cuando hay cartera sin medir.
    assert r["porcentaje_sobre_cartera"] == pytest.approx(0.10)


def test_la_cartera_medida_descuenta_tambien_el_saldo_individual_sin_tasa():
    """Con los dos clientes evaluados individualmente, lo sin medir viene solo de ellos."""
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730, "umbral_individual": 5000})
    identificaciones = [c["identificacion"] for c in r["individual"]["casos"]]
    assert sorted(identificaciones) == ["ALFA (NO-RELACIONADOS)", "GAMMA (NO-RELACIONADOS)"]
    # ALFA cae en "Más de 730 días", banda sin tasa: sus 10.000 no están medidos.
    assert r["exposicion"]["sin_medir"] == pytest.approx(10000.0)
    assert r["exposicion"]["medida"] == pytest.approx(200000.0)
    assert r["medicion_completa"] is False
    assert r["porcentaje_sobre_cartera"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# C2 — La política de deterioro del cliente se compara solo si se ingresó.
# ---------------------------------------------------------------------------

def _titulos(r):
    return [h["titulo"] for h in r["hallazgos"]]


TITULO_POLITICA = "Política de deterioro no sustentada en el comportamiento observado"


def test_sin_la_politica_del_cliente_no_se_acusa_de_no_provisionar():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    assert TITULO_POLITICA not in _titulos(r)
    fila = next(f for f in r["politica"]["filas"] if f["banda"] == "0 a 30 días")
    # Sin dato no hay 0 %: la fila queda sin comparar.
    assert fila["tasa_politica"] is None
    assert fila["provision_politica"] is None
    assert fila["diferencia"] is None
    assert fila["sin_comparar"] is True
    assert r["politica"]["politica_declarada"] is False


def test_sin_la_politica_del_cliente_se_levanta_un_pendiente():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    pendiente = next(p for p in r["pendientes"]
                     if p["variable"] == "Política de deterioro del cliente")
    assert pendiente["responsable"] == "Cliente"
    assert "no fue proporcionada" in pendiente["efecto"]


def test_con_la_politica_en_cero_el_hallazgo_si_se_emite():
    """El 0 % ingresado por el cliente sí es una afirmación suya, y se contrasta."""
    politica = {"0 a 30 días": 0.0}
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730, "politica": politica})
    assert TITULO_POLITICA in _titulos(r)
    fila = next(f for f in r["politica"]["filas"] if f["banda"] == "0 a 30 días")
    assert fila["tasa_politica"] == 0.0
    assert fila["sin_comparar"] is False
    assert fila["diferencia"] == pytest.approx(20000.0)


def test_la_politica_parcial_deja_pendiente_solo_las_bandas_que_faltan():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730,
                             "politica": {"0 a 30 días": 0.02}})
    fila = next(f for f in r["politica"]["filas"] if f["banda"] == "0 a 30 días")
    assert fila["sin_comparar"] is False
    assert fila["provision_politica"] == pytest.approx(4000.0)
    # Las demás bandas no se ingresaron: no se comparan ni suman provisión.
    assert r["politica"]["bandas_sin_politica"]
    assert "0 a 30 días" not in r["politica"]["bandas_sin_politica"]
    assert r["politica"]["provision_politica_total"] == pytest.approx(4000.0)
    assert any(p["variable"] == "Política de deterioro del cliente" for p in r["pendientes"])


def test_con_la_politica_completa_no_queda_pendiente_de_politica():
    bandas = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})["bitacora"]["bandas"]
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730,
                             "politica": {b: 0.01 for b in bandas}})
    assert not any(p["variable"] == "Política de deterioro del cliente" for p in r["pendientes"])
    assert r["politica"]["politica_declarada"] is True
    assert all(f["sin_comparar"] is False for f in r["politica"]["filas"])


# ---------------------------------------------------------------------------
# I5 — El corte intermedio controla la cohorte.
# ---------------------------------------------------------------------------

def _cortes_con_intermedio(filas_intermedio):
    """Los mismos cortes de `_cortes()` pero con el corte t-1 a medida."""
    cortes = _cortes()
    cortes[1] = {**cortes[1], "contenido": _xlsx(filas_intermedio)}
    return cortes


def test_el_corte_intermedio_se_usa_para_controlar_la_cohorte():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    control = r["control_corte_intermedio"]
    # F-1 va de 100.000 (t-2) a 20.000 (t-1) a 10.000 (t): se cobra, es coherente.
    # F-2 desaparece en t-1 y no reaparece en t: se cobró, tampoco es un problema.
    assert control["consistente"] is True
    assert control["documentos_cohorte"] == 2
    assert control["vivos_en_intermedio"] == 1
    assert not any(p["variable"] == "Consistencia de la cohorte en el corte intermedio"
                   for p in r["pendientes"])


def test_el_documento_que_reaparece_en_el_corte_actual_se_reporta_y_deja_pendiente():
    # El corte intermedio ya no trae F-1, que sí está vivo en el corte actual.
    r = analizar(_cortes_con_intermedio([
        ("BETA", "F-2", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 3, 1), 30000.0),
    ]), {"umbral_dias_incumplimiento": 730})
    control = r["control_corte_intermedio"]
    assert control["consistente"] is False
    assert control["inconsistencias_total"] == 1
    assert control["inconsistencias"][0]["documento"] == "F-1"
    assert control["inconsistencias"][0]["tipo"] == "reaparece_tras_desaparecer"
    pendiente = next(p for p in r["pendientes"]
                     if p["variable"] == "Consistencia de la cohorte en el corte intermedio")
    assert pendiente["responsable"] == "Cliente"


def test_cambiar_el_corte_intermedio_cambia_el_resultado():
    """Antes, sustituirlo por una cartera distinta dejaba el resultado idéntico."""
    fiel = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    ajeno = analizar(_cortes_con_intermedio([
        ("OTRA EMPRESA", "Z-99", "NO-RELACIONADOS", date(2024, 1, 1), date(2024, 3, 1), 999.0),
    ]), {"umbral_dias_incumplimiento": 730})
    assert fiel["control_corte_intermedio"] != ajeno["control_corte_intermedio"]
    assert ajeno["control_corte_intermedio"]["consistente"] is False


# ---------------------------------------------------------------------------
# I10 — El límite anual del 1 % se declara como no verificable.
# ---------------------------------------------------------------------------

def test_el_limite_del_1_por_ciento_anual_se_declara_como_no_verificable():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    assert r["tributario"]["limite_ejercicio_verificable"] is False
    assert r["tributario"]["provision_del_ejercicio"] is None
    pendiente = next(p for p in r["pendientes"]
                     if p["variable"] == "Movimiento de la provisión del ejercicio")
    assert pendiente["responsable"] == "Cliente"
    assert "1 %" in pendiente["efecto"]


def test_el_exceso_sobre_el_tope_acumulado_se_mide_contra_el_10_por_ciento():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    t = r["tributario"]
    # 210.000 de cartera: tope acumulado 21.000; la PCE es 20.000.
    assert t["tope_acumulado_10pct"] == pytest.approx(21000.0)
    assert t["excede_tope_acumulado"] is False
    assert t["exceso_sobre_tope_acumulado"] == pytest.approx(0.0)
