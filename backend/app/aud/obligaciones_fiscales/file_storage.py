"""Helpers para storage efímero en /tmp del contenedor.

Estructura:
  <AUD_OF_TMP_DIR>/
    <job_id>/
      inputs/
        f103/<safe_filename>
        f104/<safe_filename>
        ats/...
        mayor_general/...
        mayor_especifico/...
        f101/...
      output.xlsx
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from backend.app.core.config import settings

OUTPUT_FILENAME = "output.xlsx"
INPUTS_DIR = "inputs"
# Sidecar con el mapeo {archivo: categoria} de los Mayores específicos. Vive en
# la raíz del job (fuera de inputs/), así list_inputs nunca lo devuelve como un
# input más.
MAYOR_ESPECIFICO_MAPEO_FILE = "mayor_especifico_mapeo.json"


def _root() -> Path:
    return settings.aud_of_tmp_dir_path


def _safe_filename(name: str) -> str:
    base = Path(name).name
    return re.sub(r"[^a-zA-Z0-9._-]", "_", base)[:200] or "file"


def job_dir(job_id: int) -> Path:
    return _root() / str(job_id)


def create_job_dir(job_id: int) -> Path:
    d = job_dir(job_id)
    (d / INPUTS_DIR).mkdir(parents=True, exist_ok=True)
    return d


def save_input(job_dir: Path, slot: str, filename: str, data: bytes) -> Path:
    """Guarda un archivo de input bajo inputs/<slot>/<safe_filename>."""
    safe = _safe_filename(filename)
    safe_slot = _safe_filename(slot)
    slot_dir = job_dir / INPUTS_DIR / safe_slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    target = slot_dir / safe
    target.write_bytes(data)
    return target


def list_inputs(job_dir: Path, slot: str | None = None) -> list[Path]:
    """Lista archivos de input. Si slot es None, lista todos."""
    base = job_dir / INPUTS_DIR
    if not base.exists():
        return []
    if slot:
        slot_dir = base / _safe_filename(slot)
        if not slot_dir.exists():
            return []
        return sorted(p for p in slot_dir.iterdir() if p.is_file())
    out = []
    for p in base.rglob("*"):
        if p.is_file():
            out.append(p)
    return sorted(out)


def safe_filename(name: str) -> str:
    """Versión pública de ``_safe_filename`` (el nombre con el que se guarda)."""
    return _safe_filename(name)


def delete_input(job_dir: Path, slot: str, filename: str) -> bool:
    """Borra UN archivo del slot (por nombre ya saneado). Devuelve si existía."""
    slot_dir = job_dir / INPUTS_DIR / _safe_filename(slot)
    target = slot_dir / _safe_filename(filename)
    if target.exists() and target.is_file():
        target.unlink()
        return True
    return False


def _mapeo_path(job_dir: Path) -> Path:
    return job_dir / MAYOR_ESPECIFICO_MAPEO_FILE


def read_mayor_especifico_mapeo(job_dir: Path) -> dict[str, str]:
    """Lee el mapeo {archivo: categoria} de los Mayores específicos."""
    p = _mapeo_path(job_dir)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def write_mayor_especifico_mapeo(job_dir: Path, mapeo: dict[str, str]) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    _mapeo_path(job_dir).write_text(
        json.dumps(mapeo, ensure_ascii=False), encoding="utf-8"
    )


def set_mayor_especifico_categoria(job_dir: Path, filename: str, categoria: str) -> None:
    """Registra la categoría de UN archivo de Mayor específico."""
    mapeo = read_mayor_especifico_mapeo(job_dir)
    mapeo[_safe_filename(filename)] = categoria
    write_mayor_especifico_mapeo(job_dir, mapeo)


def unset_mayor_especifico_categoria(job_dir: Path, filename: str | None = None) -> None:
    """Quita del mapeo un archivo (o todos si filename es None)."""
    if filename is None:
        p = _mapeo_path(job_dir)
        if p.exists():
            p.unlink()
        return
    mapeo = read_mayor_especifico_mapeo(job_dir)
    mapeo.pop(_safe_filename(filename), None)
    write_mayor_especifico_mapeo(job_dir, mapeo)


def output_path(job_dir: Path) -> Path:
    return job_dir / OUTPUT_FILENAME


def delete_job_dir(job_id: int) -> None:
    d = job_dir(job_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def list_orphan_job_dirs(max_age_seconds: int) -> list[Path]:
    """Lista directorios cuya mtime es > max_age_seconds atrás."""
    root = _root()
    if not root.exists():
        return []
    now = time.time()
    orphans = []
    for child in root.iterdir():
        if not child.is_dir() or not child.name.isdigit():
            continue
        age = now - child.stat().st_mtime
        if age > max_age_seconds:
            orphans.append(child)
    return orphans
