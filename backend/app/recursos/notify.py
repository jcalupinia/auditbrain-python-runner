"""Envío del correo con usuario y clave (corre en BackgroundTask; nunca propaga).

La clave llega como argumento del task: nunca se persiste ni se registra en claro."""

from __future__ import annotations

import logging

from backend.app.db.session import SessionLocal
from backend.app.notifications import email as email_mod
from backend.app.recursos import service
from backend.app.recursos.catalog import CONTACTO, get_recurso
from backend.app.recursos.models import RecursoCuenta

log = logging.getLogger(__name__)


def enviar_clave(cuenta_id: int, clave: str, slug: str) -> None:
    db = SessionLocal()
    try:
        cuenta = db.get(RecursoCuenta, cuenta_id)
        rec = get_recurso(slug)
        if cuenta is None or rec is None:
            log.warning("Cuenta de recurso %s inexistente; no se envía correo.", cuenta_id)
            return
        try:
            res = email_mod.send_recurso_acceso(
                to=cuenta.email,
                titulo=rec.titulo,
                enlace=rec.url,
                clave=clave,
                contacto=CONTACTO,
            )
            if res is not None:
                lead = service.buscar(db, slug, cuenta.email)
                if lead is not None and not lead.email_enviado:
                    lead.email_enviado = True
                    db.commit()
        except Exception:  # noqa: BLE001
            log.exception("Correo de clave falló para cuenta %s.", cuenta_id)
    finally:
        db.close()
