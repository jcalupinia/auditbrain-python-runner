"""Endpoints del catálogo de Audit Apps (AUT-002)."""
import copy
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base, get_db
from backend.app.auth.deps import require_staff
from backend.app.audit_apps.models import AuditApp
from backend.app.audit_apps.examples import AUD_INV_VNR

VER = AUD_INV_VNR["version"]
from backend.app.audit_apps.router import router


@pytest.fixture
def client():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    from backend.app.audit_apps import models  # noqa: F401
    import backend.app.auth.models  # noqa: F401
    import backend.app.context.models  # noqa: F401
    Base.metadata.create_all(eng, tables=[AuditApp.__table__])
    db = sessionmaker(bind=eng)()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_staff] = lambda: types.SimpleNamespace(
        id=7, organization_id=None, email="a@x.ec", role="admin"
    )
    yield TestClient(app), db
    db.close()


def test_publicar_es_idempotente_y_cataloga(client):
    c, _ = client
    r = c.post("/audit-apps", json={"manifest": AUD_INV_VNR})
    assert r.status_code == 201 and r.json()["creado"] is True
    # re-publicar idéntico: idempotente (creado=False), no 409
    r2 = c.post("/audit-apps", json={"manifest": AUD_INV_VNR})
    assert r2.status_code == 201 and r2.json()["creado"] is False
    cat = c.get("/audit-apps").json()["apps"]
    assert {"app_id": "AUD-INV-VNR", "version": VER} in cat


def test_misma_version_otro_contenido_es_conflicto(client):
    c, _ = client
    assert c.post("/audit-apps", json={"manifest": AUD_INV_VNR}).status_code == 201
    modificado = copy.deepcopy(AUD_INV_VNR)
    modificado["name"] = "OTRO NOMBRE (mismo id+version)"
    r = c.post("/audit-apps", json={"manifest": modificado})
    assert r.status_code == 409


def test_manifest_invalido_da_400(client):
    c, _ = client
    r = c.post("/audit-apps", json={"manifest": {"id": "x", "name": "y"}})
    assert r.status_code == 400 and "errores" in r.json()["detail"]


def test_leer_y_versiones(client):
    c, _ = client
    c.post("/audit-apps", json={"manifest": AUD_INV_VNR})
    d = c.get("/audit-apps/AUD-INV-VNR")
    assert d.status_code == 200
    assert d.json()["manifest"]["id"] == "AUD-INV-VNR"
    assert d.json()["versions"] == [VER]
    assert c.get("/audit-apps/AUD-INV-VNR/versions").json()["versions"] == [VER]
    assert c.get("/audit-apps/NO-EXISTE").status_code == 404


def test_run_devuelve_trace_reproducible_sin_forzar(client):
    """Con los parámetros requeridos pero sin insumos, los pasos quedan en
    no_disponibles (el executor no fuerza resultados)."""
    c, _ = client
    c.post("/audit-apps", json={"manifest": AUD_INV_VNR})
    r = c.post("/audit-apps/AUD-INV-VNR/run",
               json={"parameters": {"framework": "NIC 2", "selling_method": "retail"}, "inputs": {}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["app_id"] == "AUD-INV-VNR" and body["app_version"] == VER
    assert body["no_disponibles"]  # nada se forzó
    assert body["parameter_snapshot"]["framework"] == "NIC 2"
    assert c.post("/audit-apps/NO-EXISTE/run", json={"parameters": {}}).status_code == 404


def test_run_real_ejecuta_y_devuelve_salidas(client):
    """Con la solicitud VNR como insumo, /run corre los 4 pasos y devuelve el
    Excel/HTML/excepciones reales (base64) — nada queda en no_disponibles."""
    import base64
    import json as _json
    from tests.test_vnr import payload

    c, _ = client
    c.post("/audit-apps", json={"manifest": AUD_INV_VNR})
    r = c.post("/audit-apps/AUD-INV-VNR/run", json={
        "parameters": {"framework": "full", "selling_method": "unit"},
        "inputs": {"inventario": _json.dumps(payload())},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["no_disponibles"] == []
    assert [s["step_id"] for s in body["steps"]] == [
        "extraer_inventario", "calcular_vnr", "papel_trabajo_excel", "papel_trabajo_html"]
    salidas = {o["id"]: o for o in body["outputs"]}
    assert base64.b64decode(salidas["vnr_excel"]["content_b64"])[:2] == b"PK"
    assert "valor neto de realización" in base64.b64decode(
        salidas["vnr_html"]["content_b64"]).decode("utf-8").lower()
    exc = _json.loads(base64.b64decode(salidas["excepciones_vnr"]["content_b64"]))
    assert exc["totals"]["impairment"] == "50.00"


def test_run_solicitud_invalida_da_400(client):
    c, _ = client
    c.post("/audit-apps", json={"manifest": AUD_INV_VNR})
    r = c.post("/audit-apps/AUD-INV-VNR/run", json={
        "parameters": {"framework": "full", "selling_method": "unit"},
        "inputs": {"inventario": "esto no es json"},
    })
    assert r.status_code == 400


def test_run_sin_parametro_requerido_da_400(client):
    c, _ = client
    c.post("/audit-apps", json={"manifest": AUD_INV_VNR})
    r = c.post("/audit-apps/AUD-INV-VNR/run", json={"parameters": {}, "inputs": {}})
    assert r.status_code == 400  # falta 'framework'/'selling_method'
