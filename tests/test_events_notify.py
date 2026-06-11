import uuid

import pytest

from backend.app.db.session import SessionLocal, init_db
from backend.app.events import notify, service
from backend.app.events.models import EventRegistration
from backend.app.events.schemas import RegistrationCreate


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _make_reg():
    db = SessionLocal()
    try:
        data = RegistrationCreate(
            nombre="María Pérez",
            email=f"n-{uuid.uuid4().hex[:8]}@example.com",
            telefono="0987654321",
            telefono_pais="+593",
            documento="1791240154001",
            empresa="Empresa S.A.",
        )
        reg, _ = service.create_registration(
            db, event_slug="charla-anexos-2026-06", data=data
        )
        return reg.id
    finally:
        db.close()


def test_notify_sets_flags_when_senders_succeed(monkeypatch):
    monkeypatch.setattr(
        notify.email_mod, "send_charla_confirmacion", lambda **k: {"id": "e1"}
    )
    monkeypatch.setattr(
        notify.email_mod, "send_charla_aviso_interno", lambda **k: {"id": "e2"}
    )
    monkeypatch.setattr(
        notify.wa_mod, "send_template_message", lambda **k: {"id": "w1"}
    )

    reg_id = _make_reg()
    notify.process_registration_notifications(reg_id)

    db = SessionLocal()
    try:
        reg = db.get(EventRegistration, reg_id)
        assert reg.email_enviado is True
        assert reg.aviso_interno_enviado is True
        assert reg.whatsapp_enviado is True
    finally:
        db.close()


def test_notify_whatsapp_failure_does_not_break(monkeypatch):
    monkeypatch.setattr(
        notify.email_mod, "send_charla_confirmacion", lambda **k: {"id": "e1"}
    )
    monkeypatch.setattr(
        notify.email_mod, "send_charla_aviso_interno", lambda **k: {"id": "e2"}
    )
    monkeypatch.setattr(notify.wa_mod, "send_template_message", lambda **k: None)

    reg_id = _make_reg()
    notify.process_registration_notifications(reg_id)

    db = SessionLocal()
    try:
        reg = db.get(EventRegistration, reg_id)
        assert reg.email_enviado is True
        assert reg.whatsapp_enviado is False
    finally:
        db.close()


def test_notify_unknown_registration_is_noop():
    # No debe lanzar excepción.
    notify.process_registration_notifications(999999)
