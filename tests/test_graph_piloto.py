"""Puente Microsoft Graph aislado: no requiere ni usa credenciales reales."""
import pytest
from fastapi import HTTPException

from backend.app.ingesta.graph_piloto import _config


def test_graph_piloto_falla_cerrado_sin_configuracion(monkeypatch):
    for name in ("MS_GRAPH_TENANT_ID", "MS_GRAPH_CLIENT_ID", "MS_GRAPH_CLIENT_SECRET",
                 "INGESTA_SP_DRIVE_ID", "INGESTA_SP_ITEM_ID"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(HTTPException) as err:
        _config()
    assert err.value.status_code == 503


def test_graph_piloto_requiere_drive_y_item_allowlist(monkeypatch):
    for name in ("MS_GRAPH_TENANT_ID", "MS_GRAPH_CLIENT_ID", "MS_GRAPH_CLIENT_SECRET"):
        monkeypatch.setenv(name, "prueba")
    monkeypatch.setenv("INGESTA_SP_DRIVE_ID", "drive-piloto")
    monkeypatch.delenv("INGESTA_SP_ITEM_ID", raising=False)
    with pytest.raises(HTTPException) as err:
        _config()
    assert err.value.status_code == 503
