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
    assert {"app_id": "AUD-INV-VNR", "version": "1.0.0"} in cat


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
    assert d.json()["versions"] == ["1.0.0"]
    assert c.get("/audit-apps/AUD-INV-VNR/versions").json()["versions"] == ["1.0.0"]
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
    assert body["app_id"] == "AUD-INV-VNR" and body["app_version"] == "1.0.0"
    assert body["no_disponibles"]  # nada se forzó
    assert body["parameter_snapshot"]["framework"] == "NIC 2"
    assert c.post("/audit-apps/NO-EXISTE/run", json={"parameters": {}}).status_code == 404


def test_run_sin_parametro_requerido_da_400(client):
    c, _ = client
    c.post("/audit-apps", json={"manifest": AUD_INV_VNR})
    r = c.post("/audit-apps/AUD-INV-VNR/run", json={"parameters": {}, "inputs": {}})
    assert r.status_code == 400  # falta 'framework'/'selling_method'
