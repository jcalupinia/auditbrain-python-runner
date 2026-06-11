"""Orquestación de notificaciones de una inscripción (corre en BackgroundTask)."""

from __future__ import annotations

import logging

from backend.app.db.session import SessionLocal
from backend.app.events.catalog import get_event
from backend.app.events.models import EventRegistration
from backend.app.notifications import email as email_mod
from backend.app.notifications import whatsapp as wa_mod

log = logging.getLogger(__name__)


def process_registration_notifications(registration_id: int) -> None:
    """Envía confirmación (inscrito) + aviso interno + WhatsApp y persiste los
    flags. Defensivo: ninguna falla individual interrumpe a las demás ni
    propaga excepción al runner de background."""
    db = SessionLocal()
    try:
        reg = db.get(EventRegistration, registration_id)
        if reg is None:
            log.warning("Inscripción %s no encontrada; nada que notificar.", registration_id)
            return
        event = get_event(reg.event_slug)
        if event is None:
            log.warning("Evento %s desconocido para inscripción %s.", reg.event_slug, registration_id)
            return

        # 1. Confirmación al inscrito
        try:
            res = email_mod.send_charla_confirmacion(
                to=reg.email,
                nombre=reg.nombre,
                titulo=event.titulo,
                fecha=event.fecha_texto,
                hora=event.hora_texto,
                modalidad=event.modalidad,
                zoom_url=event.zoom_url,
            )
            reg.email_enviado = res is not None
        except Exception:  # noqa: BLE001
            log.exception("Email de confirmación falló para inscripción %s.", registration_id)

        # 2. Aviso interno a la firma
        try:
            res = email_mod.send_charla_aviso_interno(
                nombre=reg.nombre,
                email=reg.email,
                telefono=reg.telefono_e164,
                documento=reg.documento,
                empresa=reg.empresa,
                titulo=event.titulo,
            )
            reg.aviso_interno_enviado = res is not None
        except Exception:  # noqa: BLE001
            log.exception("Aviso interno falló para inscripción %s.", registration_id)

        # 3. WhatsApp al inscrito
        try:
            res = wa_mod.send_template_message(
                to_e164=reg.telefono_e164,
                variables=[reg.nombre, event.fecha_texto, event.hora_texto],
            )
            reg.whatsapp_enviado = res is not None
        except Exception:  # noqa: BLE001
            log.exception("WhatsApp falló para inscripción %s.", registration_id)

        try:
            db.commit()
        except Exception:  # noqa: BLE001
            log.exception(
                "Error al persistir flags de notificación para inscripción %s.",
                registration_id,
            )
    finally:
        db.close()
