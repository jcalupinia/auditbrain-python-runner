"""Wrapper de email transaccional con Resend + retry."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_RESEND_URL = "https://api.resend.com/emails"


def render_job_ready(*, client_name: str, tool_label: str, download_url: str) -> str:
    tpl = (_TEMPLATES_DIR / "job_ready.html").read_text(encoding="utf-8")
    return (
        tpl.replace("{{tool_label}}", tool_label)
        .replace("{{download_url}}", download_url)
        .replace("{{client_name}}", client_name)
    )


def _post_to_resend(*, to: str, subject: str, html: str) -> dict:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "no-reply@auditconsulting.com").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY no configurado.")
    resp = requests.post(
        _RESEND_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"from": from_email, "to": [to], "subject": subject, "html": html},
        timeout=15,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Resend {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def send_email(
    *, to: str, subject: str, html: str, max_retries: int = 3
) -> dict | None:
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            return _post_to_resend(to=to, subject=subject, html=html)
        except Exception as e:  # noqa: BLE001
            log.warning("send_email attempt %d/%d failed: %s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
    log.error("send_email FAILED after %d retries to=%s subject=%r", max_retries, to, subject)
    return None


def send_job_ready_email(*, job_id: int, to: str, tool_label: str) -> dict | None:
    portal_base = os.getenv(
        "CLIENT_PORTAL_URL", "https://auditbrain-clientes.onrender.com"
    )
    download_url = f"{portal_base}/jobs/{job_id}"
    html = render_job_ready(
        client_name="Cliente",
        tool_label=tool_label,
        download_url=download_url,
    )
    return send_email(
        to=to,
        subject=f"Su entregable '{tool_label}' está listo (disponible 24h)",
        html=html,
    )
