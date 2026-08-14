"""Proxy del Command Center hacia el puente de generación de imágenes/video.

El puente (ComfyUI) vive en el servidor local y se expone por un túnel. El
backend guarda la URL del túnel y la clave secreta; así el frontend **NO**
necesita Tailscale ni conoce el secreto, y solo usuarios con sesión (JWT)
pueden generar.

Config por entorno:
- COMFY_BRIDGE_URL: URL pública del puente (túnel), p. ej. https://xxx.trycloudflare.com
- COMFY_BRIDGE_KEY: clave X-Comfy-Key del puente.
- COMFY_BRIDGE_TIMEOUT: segundos de espera (default 220; la generación + swap tarda).
"""
from __future__ import annotations

import os

import requests

_URL = os.environ.get("COMFY_BRIDGE_URL", "").rstrip("/")
_KEY = os.environ.get("COMFY_BRIDGE_KEY", "")
_TIMEOUT = int(os.environ.get("COMFY_BRIDGE_TIMEOUT", "220"))


class MediaUnavailable(RuntimeError):
    """El puente no está configurado o no respondió correctamente."""


def enabled() -> bool:
    return bool(_URL and _KEY)


def _post(path: str, payload: dict) -> dict:
    if not enabled():
        raise MediaUnavailable("La generación de medios no está configurada.")
    try:
        r = requests.post(
            _URL + path, json=payload,
            headers={"X-Comfy-Key": _KEY}, timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise MediaUnavailable(f"No se pudo contactar al servidor local: {exc}") from exc
    if r.status_code != 200:
        detail = r.text[:300]
        try:
            detail = r.json().get("error", detail)
        except Exception:  # noqa: BLE001
            pass
        raise MediaUnavailable(f"El servidor local respondió {r.status_code}: {detail}")
    return r.json()


def generate_image(prompt: str, model: str = "flux", width: int = 1024, height: int = 1024) -> dict:
    return _post("/generate", {"prompt": prompt, "model": model, "width": width, "height": height})


def generate_video(prompt: str, width: int = 704, height: int = 480, length: int = 65) -> dict:
    return _post("/generate_video", {"prompt": prompt, "width": width, "height": height, "length": length})
