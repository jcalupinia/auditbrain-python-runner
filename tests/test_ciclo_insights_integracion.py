"""Integración HTTP: el ciclo puebla evidenceMatrix (validate) y riskScoring (analyze).

Reusa el flujo VNR de test_aud_ciclo_ejecucion para probar EMPÍRICAMENTE que el
enriquecimiento aditivo se calcula de punta a punta (no solo en unit tests)."""
import pytest

from tests.test_aud_ciclo_ejecucion import _navegador, _validada
from tests.test_aud_ciclo_http import _accion


@pytest.fixture(autouse=True)
def disco_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_CICLO_DIR", str(tmp_path / "aud_pruebas"))
    monkeypatch.setenv("AUD_CICLO_MIN_LIBRE_MB", "0")


def test_evidence_matrix_y_risk_scoring_se_pueblan(client):
    from tests.test_aud_niif_fichas import _h  # noqa: F401

    tok, p = _validada(client)  # corre validate → DOCUMENTACION_VALIDADA

    # Evidence: la matriz requerimientos ↔ archivos quedó en el registro.
    em = p["registro"]["evidenceMatrix"]
    assert em["resumen"]["requerimientos"] >= 1
    assert em["resumen"]["con_evidencia"] >= 1
    assert em["entradas"] and all("requerimiento" in e for e in em["entradas"])

    # Avanzar hasta analyze.
    p = _accion(client, tok, p, "configure",
                {"basis": "Precios de la lista vigente al corte; costos de venta del ERI."}).json()
    p = _accion(client, tok, p, "approve_methodology").json()
    p = _accion(client, tok, p, "execute", {"navegador": _navegador(p)}).json()
    p = _accion(client, tok, p, "analyze").json()
    assert p["estado"] == "RESULTADOS_ANALIZADOS"

    # Risk: scoring sobre la población (VNR tiene campos numéricos).
    rs = p["registro"]["riskScoring"]
    assert rs["campos"] and "quantity" in rs["campos"]
    assert rs["resumen"]["total"] == len(p["registro"]["rows"])
    # cada anomalía marcada trae su desglose explicable
    assert all(a.get("factores") is not None for a in rs["anomalias"])
