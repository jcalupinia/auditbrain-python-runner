"""Tests del agente de recomendación de escenarios tributarios."""

from unittest.mock import patch

from backend.app.tax.planificacion_utilidades.schemas import (
    RecomendacionRequest,
    RecomendacionResponse,
)
from backend.app.tax.planificacion_utilidades import recomendacion as rec


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


def test_build_recomendacion_fallback_si_llm_falla():
    # Si el LLM no está disponible, devuelve fallback graceful con revisión humana.
    with patch.object(rec, "_call_llm", side_effect=RuntimeError("no key")):
        out = rec.build_recomendacion(
            empresa="X",
            recomendado="cap",
            comparacion={"cap": {"totales": {"impuesto": 0, "costoMuerto": 0}}},
        )
    assert out.requiere_revision_humana is True
    assert "capitaliz" in out.narrativa.lower()


def test_build_recomendacion_usa_texto_del_llm():
    with patch.object(rec, "_call_llm", return_value="Recomendamos capitalizar."):
        out = rec.build_recomendacion(
            empresa="X",
            recomendado="cap",
            comparacion={"cap": {"totales": {"impuesto": 0, "costoMuerto": 0}}},
        )
    assert out.narrativa == "Recomendamos capitalizar."
