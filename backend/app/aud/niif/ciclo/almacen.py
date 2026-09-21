"""Dónde se guarda la evidencia de las pruebas (diseño 2026-09-21, §6).

En Render hay un disco persistente de 1 GB montado en ``/var/data``, compartido
con el ICT. La evidencia va a ``/var/data/aud_pruebas/<prueba>/``. En local, a
una carpeta temporal. ``AUD_CICLO_DIR`` permite fijarla a mano.

Guarda de espacio: si quedan menos de ``AUD_CICLO_MIN_LIBRE_MB`` (150 MB por
defecto) se rechaza la subida con un mensaje claro, en vez de llenar el disco y
dejar sin espacio al ICT.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

MAX_ARCHIVO = 25 * 1024 * 1024  # el mismo límite del sitio

TIPOS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "csv": "text/csv", "xml": "application/xml", "pdf": "application/pdf", "txt": "text/plain",
    "md": "text/markdown", "zip": "application/zip", "png": "image/png", "jpg": "image/jpeg",
    "jpeg": "image/jpeg", "webp": "image/webp",
}


class SinEspacio(Exception):
    pass


def carpeta_base() -> Path:
    if os.getenv("AUD_CICLO_DIR"):
        base = Path(os.environ["AUD_CICLO_DIR"])
    elif Path("/var/data").is_dir():
        base = Path("/var/data/aud_pruebas")
    else:
        base = Path(tempfile.gettempdir()) / "auditbrain" / "aud_pruebas"
    base.mkdir(parents=True, exist_ok=True)
    return base


def minimo_libre() -> int:
    return int(os.getenv("AUD_CICLO_MIN_LIBRE_MB", "150")) * 1024 * 1024


def libre() -> int:
    return shutil.disk_usage(carpeta_base()).free


def guardar(prueba_id: int, nombre_interno: str, datos: bytes) -> str:
    if libre() - len(datos) < minimo_libre():
        raise SinEspacio(
            "El almacenamiento del portal está casi lleno. No se guardó el archivo: "
            "avise al administrador para ampliar el disco o liberar espacio."
        )
    carpeta = carpeta_base() / str(prueba_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre_interno
    ruta.write_bytes(datos)
    return str(ruta)


def leer(ruta: str) -> bytes:
    return Path(ruta).read_bytes()


def borrar_prueba(prueba_id: int) -> None:
    shutil.rmtree(carpeta_base() / str(prueba_id), ignore_errors=True)
