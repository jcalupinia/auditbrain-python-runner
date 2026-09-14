"""Envío del correo de acceso (corre en BackgroundTask; nunca propaga)."""

from __future__ import annotations

import logging

from backend.app.db.session import SessionLocal
from backend.app.notifications import email as email_mod
from backend.app.recursos.catalog import CONTACTO, get_recurso
from backend.app.recursos.models import RecursoLead
from backend.app.recursos.tokens import crear_token

log = logging.getLogger(__name__)


def enviar_acceso(lead_id: int) -> None:
    db = SessionLocal()
    try:
        lead = db.get(RecursoLead, lead_id)
        rec = get_recurso(lead.recurso_slug) if lead else None
        if lead is None or rec is None:
            log.warning("Lead de recurso %s inexistente; no se envía correo.", lead_id)
            return
        enlace = f"{rec.url}?acceso={crear_token(lead.id, lead.recurso_slug)}"
        try:
            res = email_mod.send_recurso_acceso(
                to=lead.email,
                nombre=lead.nombre,
                titulo=rec.titulo,
                enlace=enlace,
                contacto=CONTACTO,
            )
            if res is not None:
                lead.email_enviado = True
                db.commit()
        except Exception:  # noqa: BLE001
            log.exception("Correo de acceso falló para lead %s.", lead_id)
    finally:
        db.close()
