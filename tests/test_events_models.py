import uuid

import pytest

from backend.app.db.session import SessionLocal, init_db
from backend.app.events.models import EventRegistration


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_can_insert_registration():
    db = SessionLocal()
    try:
        reg = EventRegistration(
            event_slug="charla-anexos-2026-06",
            nombre="María Pérez",
            email=f"maria-{uuid.uuid4().hex[:8]}@example.com",
            telefono_e164="+593987654321",
            documento="1791240154001",
            empresa="Empresa S.A.",
        )
        db.add(reg)
        db.commit()
        db.refresh(reg)
        assert reg.id is not None
        assert reg.estado == "registrado"
        assert reg.email_enviado is False
        assert reg.aviso_interno_enviado is False
        assert reg.created_at is not None
    finally:
        db.close()
