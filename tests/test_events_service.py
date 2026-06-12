import uuid

import pytest

from backend.app.db.session import SessionLocal, init_db
from backend.app.events import service
from backend.app.events.schemas import RegistrationCreate


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _payload(email):
    return RegistrationCreate(
        nombre="María Pérez",
        email=email,
        telefono="0987654321",
        telefono_pais="+593",
        documento="1791240154001",
        empresa="Empresa S.A.",
    )


def test_create_registration_persists_and_returns_false():
    db = SessionLocal()
    try:
        email = f"a-{uuid.uuid4().hex[:8]}@example.com"
        reg, ya = service.create_registration(
            db, event_slug="charla-anexos-2026-06", data=_payload(email)
        )
        assert ya is False
        assert reg.id is not None
        assert reg.email == email.lower()
        assert reg.telefono_e164 == "+593987654321"
    finally:
        db.close()


def test_create_registration_idempotent_same_email():
    db = SessionLocal()
    try:
        email = f"b-{uuid.uuid4().hex[:8]}@example.com"
        reg1, ya1 = service.create_registration(
            db, event_slug="charla-anexos-2026-06", data=_payload(email)
        )
        reg2, ya2 = service.create_registration(
            db, event_slug="charla-anexos-2026-06", data=_payload(email)
        )
        assert ya1 is False
        assert ya2 is True
        assert reg1.id == reg2.id
    finally:
        db.close()


def test_list_registrations_returns_desc():
    db = SessionLocal()
    try:
        slug = f"evt-{uuid.uuid4().hex[:6]}"
        for i in range(3):
            service.create_registration(
                db, event_slug=slug, data=_payload(f"c{i}-{uuid.uuid4().hex[:6]}@x.com")
            )
        rows = service.list_registrations(db, event_slug=slug, limit=10)
        assert len(rows) == 3
        ids = [r.id for r in rows]
        assert ids == sorted(ids, reverse=True), "Debe venir en orden descendente"
    finally:
        db.close()
