"""Derivación de tasas de pérdida por permanencia a 24 meses."""
import pytest

from backend.app.aud.pce_cxc.cohortes import tasas_por_permanencia


def _doc(documento, banda, saldo, segmento="NO-RELACIONADOS"):
    return {"documento": documento, "banda": banda, "saldo": saldo, "segmento": segmento}


def test_la_tasa_es_el_saldo_que_sigue_vivo_sobre_la_cohorte_inicial():
    cohorte = [_doc("F-1", "0 a 30 días", 100000.0), _doc("F-2", "0 a 30 días", 50000.0)]
    actual = [_doc("F-1", "Más de 360 días", 15000.0)]
    r = tasas_por_permanencia(cohorte, actual)
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(0.10)
    assert r["detalle"]["NO-RELACIONADOS"]["0 a 30 días"]["documentos"] == 2


def test_una_banda_sin_cohorte_no_tiene_tasa():
    r = tasas_por_permanencia([_doc("F-1", "0 a 30 días", 1000.0)], [])
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == 0.0
    assert r["tasas"]["NO-RELACIONADOS"].get("181 a 360 días") is None


def test_cada_segmento_tiene_su_propia_tasa():
    cohorte = [_doc("F-1", "Por vencer", 1000.0), _doc("R-1", "Por vencer", 2000.0, "RELACIONADOS")]
    actual = [_doc("R-1", "Por vencer", 1000.0, "RELACIONADOS")]
    r = tasas_por_permanencia(cohorte, actual)
    assert r["tasas"]["NO-RELACIONADOS"]["Por vencer"] == pytest.approx(0.0)
    assert r["tasas"]["RELACIONADOS"]["Por vencer"] == pytest.approx(0.5)


def test_la_trazabilidad_mide_cuantos_documentos_se_reencuentran():
    cohorte = [_doc("F-1", "Por vencer", 10.0), _doc("F-2", "Por vencer", 10.0)]
    r = tasas_por_permanencia(cohorte, [_doc("F-1", "Por vencer", 5.0)])
    assert r["trazabilidad"] == pytest.approx(0.5)


def test_un_remanente_mayor_que_el_inicial_se_acota_y_se_reporta():
    cohorte = [_doc("F-1", "0 a 30 días", 100.0)]
    actual = [_doc("F-1", "Más de 360 días", 150.0)]
    r = tasas_por_permanencia(cohorte, actual)
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(1.0)
    assert len(r["anomalias"]) == 1
    a = r["anomalias"][0]
    assert a["tipo"] == "remanente_mayor_que_inicial"
    assert a["tasa_bruta"] == pytest.approx(1.5)
    assert a["banda"] == "0 a 30 días"
    # El detalle conserva lo observado, sin recortar.
    assert r["detalle"]["NO-RELACIONADOS"]["0 a 30 días"]["remanente"] == pytest.approx(150.0)


def test_un_remanente_negativo_se_acota_y_se_reporta():
    cohorte = [_doc("F-1", "0 a 30 días", 100.0)]
    actual = [_doc("F-1", "0 a 30 días", -20.0)]
    r = tasas_por_permanencia(cohorte, actual)
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(0.0)
    assert r["anomalias"][0]["tipo"] == "remanente_negativo"
    assert r["anomalias"][0]["tasa_bruta"] == pytest.approx(-0.2)


def test_sin_anomalias_la_lista_va_vacia():
    cohorte = [_doc("F-1", "0 a 30 días", 100.0)]
    actual = [_doc("F-1", "0 a 30 días", 40.0)]
    r = tasas_por_permanencia(cohorte, actual)
    assert r["anomalias"] == []
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(0.40)


def test_un_documento_repetido_en_el_corte_actual_suma_su_saldo():
    cohorte = [_doc("F-1", "0 a 30 días", 100.0)]
    actual = [_doc("F-1", "0 a 30 días", 30.0), _doc("F-1", "0 a 30 días", 20.0)]
    r = tasas_por_permanencia(cohorte, actual)
    assert r["detalle"]["NO-RELACIONADOS"]["0 a 30 días"]["remanente"] == pytest.approx(50.0)
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(0.50)
