"""WhatsApp Cloud API (Meta) con degradación elegante + retry.

El lead nunca inicia la conversación (llena un formulario web), por lo que
NO existe ventana de servicio de 24h: el primer mensaje proactivo DEBE ser
una plantilla pre-aprobada por Meta (categoría utility).

Si faltan las env vars, NO se rompe el flujo: se loguea y se retorna None.
"""

from __future__ import annotations

import logging
import os
import time

import requests

log = logging.getLogger(__name__)

_GRAPH_VERSION = "v21.0"


def _config() -> tuple[str, str, str, str]:
    return (
        os.getenv("WHATSAPP_TOKEN", "").strip(),
        os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
        os.getenv("WHATSAPP_TEMPLATE_NAME", "").strip(),
        os.getenv("WHATSAPP_TEMPLATE_LANG", "es").strip() or "es",
    )


def send_template_message(
    *, to_e164: str, variables: list[str], max_retries: int = 3
) -> dict | None:
    token, phone_id, template, lang = _config()
    if not (token and phone_id and template):
        log.warning(
            "WhatsApp no configurado (faltan env vars). Mensaje a %s omitido.", to_e164
        )
        return None

    url = f"https://graph.facebook.com/{_GRAPH_VERSION}/{phone_id}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": to_e164.lstrip("+"),
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": lang},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": v} for v in variables],
                }
            ],
        },
    }

    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=15,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"WhatsApp {resp.status_code}: {resp.text[:200]}")
            return resp.json()
        except Exception as e:  # noqa: BLE001
            log.warning(
                "send_template_message attempt %d/%d failed: %s", attempt, max_retries, e
            )
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
    log.error(
        "send_template_message FAILED after %d retries to=%s", max_retries, to_e164
    )
    return None
