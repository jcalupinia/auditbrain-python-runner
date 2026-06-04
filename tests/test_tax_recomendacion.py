"""Tests del agente de recomendación de escenarios tributarios."""

from backend.app.tax.planificacion_utilidades.schemas import (
    RecomendacionRequest,
    RecomendacionResponse,
)


def test_request_acepta_comparacion():
    req = RecomendacionRequest(
        empresa="ARCOLANDS",
        recomendado="cap",
        comparacion={"sin": {"totales": {"impuesto": 100}}},
    )
    assert req.recomendado == "cap"


def test_response_tiene_controles_ia():
    r = RecomendacionResponse(
        narrativa="texto",
        confianza_modelo="alta",
        requiere_revision_humana=False,
    )
    assert r.confianza_modelo == "alta"
