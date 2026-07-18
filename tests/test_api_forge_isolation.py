"""P11 — Un Forge roto NO puede tumbar /api/v1 para los clientes.

Forge (L0-L11) es funcionalidad **nueva y opcional**. El resto de la API —auth,
portal cliente, ICT, AUD— es el núcleo del que dependen los 56 clientes en
producción. Antes de F2b.0, los routers de Forge se importaban al top level de
``api/__init__.py``: un import roto o un router mal formado en ``forge/`` haría
fallar la importación del módulo entero y, con ella, **todo** ``/api/v1``.

Este test fija la garantía: si el import de Forge revienta, la API arranca SIN
Forge (se registra y sigue), no deja de arrancar. El riesgo ya existía antes de
F2b; este es su cierre.
"""

import sys

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from backend.app.api import _montar_forge, api_router, forge_montado


def test_forge_sano_se_monta():
    """En una importación normal (deps completas) Forge está sano y se monta."""
    assert forge_montado is True


def test_health_reporta_si_forge_esta_montado():
    """El healthcheck no debe mentir: expone si Forge quedó montado o no, para
    que un deploy donde Forge no cargó se vea (`mounted: false`) en vez de callar."""
    app = FastAPI()
    app.include_router(api_router)
    r = TestClient(app).get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["forge"] == {"mounted": True}


def test_forge_roto_no_lanza_y_no_monta_nada(monkeypatch):
    """El corazón de P11: sabotear el import de Forge NO puede propagar la excepción."""
    # `None` en sys.modules hace que `from backend.app.forge import ...` lance
    # ModuleNotFoundError, igual que un import realmente roto en producción.
    monkeypatch.setitem(sys.modules, "backend.app.forge", None)

    r = APIRouter()
    montado = _montar_forge(r)  # NO debe lanzar

    assert montado is False
    assert list(r.routes) == []  # no se coló ninguna ruta a medias


def test_el_nucleo_sigue_montado_pase_lo_que_pase_con_forge():
    """`api_router` monta el núcleo ANTES de intentar Forge: un fallo de Forge
    llega tarde para quitar auth/ICT/AUD, que ya están dentro."""
    app = FastAPI()
    app.include_router(api_router)
    paths = set(app.openapi().get("paths", {}))

    assert any("/auth" in p for p in paths), "auth (núcleo) debe estar montado"
    assert any(
        "/informe-cumplimiento-tributario" in p for p in paths
    ), "ICT (núcleo) debe estar montado"
    # Y hay muchas más rutas de núcleo que de Forge: el núcleo no depende de Forge.
    forge = {p for p in paths if "/forge" in p}
    assert len(paths - forge) > len(forge)
