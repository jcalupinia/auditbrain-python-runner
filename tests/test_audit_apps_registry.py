"""Registro versionado de Audit Apps (P2.1, AUT-002)."""
import copy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.audit_apps.manifest import AuditAppManifest
from backend.app.audit_apps.models import AuditApp
from backend.app.audit_apps.registry import (
    AppNotFoundError,
    AppVersionConflictError,
    AuditAppRegistry,
    manifest_hash,
)
from backend.app.audit_apps.examples.aud_inv_vnr import AUD_INV_VNR


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    from backend.app.audit_apps import models  # noqa: F401
    import backend.app.auth.models  # noqa: F401  (registra users)
    import backend.app.context.models  # noqa: F401  (registra organizations)
    Base.metadata.create_all(eng, tables=[AuditApp.__table__])
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _manifest(**cambios) -> AuditAppManifest:
    data = copy.deepcopy(AUD_INV_VNR)
    data.update(cambios)
    return AuditAppManifest.from_dict(data).validate()


def test_alta_idempotente(db):
    reg = AuditAppRegistry(db)
    m, creado = reg.register(_manifest(), owner_user_id=1, organization_id=None)
    assert creado is True
    _, creado2 = reg.register(_manifest(), owner_user_id=1, organization_id=None)
    assert creado2 is False  # misma versión, mismo contenido → no-op
    assert db.query(AuditApp).count() == 1


def test_conflicto_de_version(db):
    reg = AuditAppRegistry(db)
    reg.register(_manifest(), owner_user_id=1, organization_id=None)
    # misma versión, contenido distinto (cambia el name) → 409
    with pytest.raises(AppVersionConflictError):
        reg.register(_manifest(name="OTRO NOMBRE"), owner_user_id=1, organization_id=None)


def test_get_vigente_y_versiones(db):
    reg = AuditAppRegistry(db)
    reg.register(_manifest(version="1.0.0"), owner_user_id=1, organization_id=None)
    reg.register(_manifest(version="1.2.0"), owner_user_id=1, organization_id=None)
    reg.register(_manifest(version="1.10.0"), owner_user_id=1, organization_id=None)
    assert reg.versions(AUD_INV_VNR["id"]) == ["1.0.0", "1.2.0", "1.10.0"]
    assert reg.get(AUD_INV_VNR["id"]).version == "1.10.0"  # semver, no lexicográfico
    assert reg.get(AUD_INV_VNR["id"], "1.2.0").version == "1.2.0"


def test_get_inexistente(db):
    reg = AuditAppRegistry(db)
    with pytest.raises(AppNotFoundError):
        reg.get("AUD-NO-EXISTE")


def test_list_una_por_app_vigente(db):
    reg = AuditAppRegistry(db)
    reg.register(_manifest(version="1.0.0"), owner_user_id=1, organization_id=7)
    reg.register(_manifest(version="2.0.0"), owner_user_id=1, organization_id=7)
    catalogo = reg.list(organization_id=7)
    assert catalogo == [(AUD_INV_VNR["id"], "2.0.0")]
    assert reg.list(organization_id=999) == []  # aislamiento por tenant


def test_manifest_hash_estable():
    a = manifest_hash(_manifest())
    b = manifest_hash(_manifest())
    assert a == b and a != manifest_hash(_manifest(name="X"))
