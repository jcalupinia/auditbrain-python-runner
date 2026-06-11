"""Wrapper de email transaccional con Resend + retry."""

from __future__ import annotations

import html as _html
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


def render_charla_confirmacion(
    *, nombre: str, titulo: str, fecha: str, hora: str, modalidad: str, zoom_url: str
) -> str:
    tpl = (_TEMPLATES_DIR / "charla_confirmacion.html").read_text(encoding="utf-8")
    if zoom_url:
        zoom_block = (
            '<p style="text-align:center;margin:24px 0">'
            f'<a href="{_html.escape(zoom_url, quote=True)}" '
            'style="background:#8bc34a;color:#0a2540;font-weight:bold;padding:12px 28px;'
            'text-decoration:none;border-radius:6px;display:inline-block">Unirme por Zoom</a></p>'
        )
    else:
        zoom_block = ""
    return (
        tpl.replace("{{nombre}}", _html.escape(nombre))
        .replace("{{titulo}}", _html.escape(titulo))
        .replace("{{fecha}}", _html.escape(fecha))
        .replace("{{hora}}", _html.escape(hora))
        .replace("{{modalidad}}", _html.escape(modalidad))
        .replace("{{zoom_block}}", zoom_block)
    )


def send_charla_confirmacion(
    *, to: str, nombre: str, titulo: str, fecha: str, hora: str, modalidad: str, zoom_url: str
) -> dict | None:
    html_body = render_charla_confirmacion(
        nombre=nombre, titulo=titulo, fecha=fecha, hora=hora, modalidad=modalidad, zoom_url=zoom_url
    )
    return send_email(
        to=to, subject=f"Confirmación de tu reserva — {titulo}", html=html_body
    )


def render_charla_aviso_interno(
    *, nombre: str, email: str, telefono: str, documento: str, empresa: str, titulo: str
) -> str:
    tpl = (_TEMPLATES_DIR / "charla_aviso_interno.html").read_text(encoding="utf-8")
    return (
        tpl.replace("{{nombre}}", _html.escape(nombre))
        .replace("{{email}}", _html.escape(email))
        .replace("{{telefono}}", _html.escape(telefono))
        .replace("{{documento}}", _html.escape(documento))
        .replace("{{empresa}}", _html.escape(empresa))
        .replace("{{titulo}}", _html.escape(titulo))
    )


def send_charla_aviso_interno(
    *, nombre: str, email: str, telefono: str, documento: str, empresa: str, titulo: str
) -> dict | None:
    to = os.getenv("EVENTS_NOTIFY_EMAIL", "info@auditconsulting.ec").strip()
    html_body = render_charla_aviso_interno(
        nombre=nombre, email=email, telefono=telefono, documento=documento, empresa=empresa, titulo=titulo
    )
    return send_email(to=to, subject=f"Nueva inscripción — {titulo}", html=html_body)
