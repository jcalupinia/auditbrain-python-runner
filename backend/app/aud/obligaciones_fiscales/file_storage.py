"""Helpers para storage efímero en /tmp del contenedor.

Estructura:
  <AUD_OF_TMP_DIR>/
    <job_id>/
      inputs/
        f103/<safe_filename>
        f104/<safe_filename>
        ats/...
        mayor_compras/...
        mayor_ventas/...
        f101/...
      output.xlsx
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from backend.app.core.config import settings

OUTPUT_FILENAME = "output.xlsx"
INPUTS_DIR = "inputs"


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
