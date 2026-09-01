"""Processor del Generador de Reels para el pipeline genérico de jobs del portal.

Espeja ``flujo/processor.py``: recibe ``job_id``, marca ``processing``, lee el
audio de voz del slot, y delega la generación pesada al **puente** del servidor
local (endpoints async ``/reels`` del comfy-bridge). El puente corre FLOAT+GFPGAN
+ ffmpeg (varios minutos, con GPU), así que aquí solo hacemos POST → poll →
descarga de los 2 MP4 (16:9 y 9:16), que quedan en ``<job_dir>/artifacts/``.

Config por entorno (mismas del puente que ya usa ``chat/media.py``):
- COMFY_BRIDGE_URL, COMFY_BRIDGE_KEY.
- REELS_POLL_TIMEOUT: segundos máx. de espera (default 1200 = 20 min).

ponytail: glue de I/O verificado E2E contra el puente real (curl); sin unit test
(mockear requests sería más código que la lógica). El núcleo _run(job_dir) es
testeable si más adelante hace falta.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from backend.app.aud.obligaciones_fiscales import file_storage

SLOT_AUDIO = "audio"
ARTIFACTS_DIR = "artifacts"
OUT_H = "reel_horizontal.mp4"
OUT_V = "reel_vertical.mp4"

_URL = os.environ.get("COMFY_BRIDGE_URL", "").rstrip("/")
_KEY = os.environ.get("COMFY_BRIDGE_KEY", "")
_POLL_TIMEOUT = int(os.environ.get("REELS_POLL_TIMEOUT", "1200"))
_H = {"X-Comfy-Key": _KEY}


def _run(job_dir: Path) -> dict:
    """Núcleo: sube el audio al puente, espera, descarga los 2 reels a
    ``job_dir/artifacts/`` y devuelve el summary con la lista de artefactos."""
    if not (_URL and _KEY):
        raise RuntimeError("El Generador de Reels no está configurado (COMFY_BRIDGE_URL/KEY).")
    inputs = file_storage.list_inputs(job_dir, SLOT_AUDIO)
    if not inputs:
        raise ValueError("Falta el audio de voz.")
    audio = inputs[0]

    with audio.open("rb") as f:
        r = requests.post(f"{_URL}/reels", headers=_H,
                          files={"audio": (audio.name, f, "application/octet-stream")},
                          timeout=120)
    if r.status_code == 409:
        raise RuntimeError("El servidor está generando otro reel. Intenta en unos minutos.")
    if r.status_code != 200:
        raise RuntimeError(f"El puente respondió {r.status_code}: {r.text[:200]}")
    bjid = r.json()["job_id"]

    step, deadline = "", time.time() + _POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(10)
        s = requests.get(f"{_URL}/reels/{bjid}", headers=_H, timeout=30).json()
        step = s.get("step", step)
        st = s.get("status")
        if st == "done":
            break
        if st == "error":
            raise RuntimeError(f"La generación falló: {s.get('error')}")
    else:
        raise RuntimeError("Se agotó el tiempo de espera generando el reel.")

    art = job_dir / ARTIFACTS_DIR
    art.mkdir(parents=True, exist_ok=True)
    for fn, fmt in ((OUT_H, "horizontal"), (OUT_V, "vertical")):
        dl = requests.get(f"{_URL}/reels/{bjid}/output", params={"fmt": fmt},
                          headers=_H, timeout=180)
        if dl.status_code != 200:
            raise RuntimeError(f"No se pudo descargar el reel {fmt}: {dl.status_code}")
        (art / fn).write_bytes(dl.content)

    return {
        "artifacts": [
            {"name": OUT_H, "label": "Reel horizontal 16:9 (Facebook · YouTube)", "kind": "mp4"},
            {"name": OUT_V, "label": "Reel vertical 9:16 (Instagram · Estados · TikTok)", "kind": "mp4"},
        ],
        "bridge_job": bjid,
        "last_step": step,
    }


def reels_processor(job_id: int) -> None:
    """Procesa un ToolJob del Generador de Reels. Marca processing → done/error."""
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            return
        job.status = "processing"
        db.commit()
        try:
            summary = _run(file_storage.job_dir(job_id))
        except Exception as exc:  # noqa: BLE001 — se reporta al usuario
            job.status = "error"
            job.error_message = str(exc)[:1000]
            db.commit()
            return
        job.status = "done"
        job.summary_json = summary
        db.commit()
    finally:
        db.close()
