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


# ---- Marketing-Tools (Creative Studio) ----
def remove_bg(image_base64: str) -> dict:
    return _post("/removebg", {"image_base64": image_base64})


def tts(text: str) -> dict:
    return _post("/tts", {"text": text})


def subtitle(audio_base64: str) -> dict:
    return _post("/subtitle", {"audio_base64": audio_base64})


# ---- Reels (async: el puente mantiene el estado del job; aquí solo proxeamos) ----
def _bridge_get(path: str, params: dict | None = None, timeout: int = 60):
    if not enabled():
        raise MediaUnavailable("La generación de medios no está configurada.")
    try:
        return requests.get(_URL + path, params=params, headers={"X-Comfy-Key": _KEY}, timeout=timeout)
    except requests.RequestException as exc:
        raise MediaUnavailable(f"No se pudo contactar al servidor local: {exc}") from exc


def reel_start(audio_bytes: bytes, filename: str) -> dict:
    if not enabled():
        raise MediaUnavailable("La generación de medios no está configurada.")
    try:
        r = requests.post(
            _URL + "/reels", headers={"X-Comfy-Key": _KEY},
            files={"audio": (filename, audio_bytes, "application/octet-stream")}, timeout=120,
        )
    except requests.RequestException as exc:
        raise MediaUnavailable(f"No se pudo contactar al servidor local: {exc}") from exc
    if r.status_code == 409:
        raise MediaUnavailable("El servidor está generando otro reel. Intenta en unos minutos.")
    if r.status_code != 200:
        raise MediaUnavailable(f"El servidor local respondió {r.status_code}: {r.text[:200]}")
    return r.json()


def reel_status(jid: str) -> dict:
    r = _bridge_get(f"/reels/{jid}", timeout=30)
    if r.status_code != 200:
        raise MediaUnavailable(f"El servidor local respondió {r.status_code}: {r.text[:200]}")
    return r.json()


def reel_output(jid: str, fmt: str) -> bytes:
    r = _bridge_get(f"/reels/{jid}/output", params={"fmt": fmt}, timeout=180)
    if r.status_code != 200:
        raise MediaUnavailable(f"El reel {fmt} no está disponible ({r.status_code}).")
    return r.content
