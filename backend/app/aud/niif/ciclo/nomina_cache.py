# -*- coding: utf-8 -*-
"""Caché por prueba del motor de nómina (cédulas) y su recálculo con LibreOffice.

Motivo (decisión del dueño, 2026-10-12): hoy el panel de nómina y las descargas de cédulas
**vuelven a correr el motor completo (parsea los 8 archivos, incl. 85 PDF) + recálculo
LibreOffice de las 15 cédulas en CADA apertura/descarga**. Con varios auditores a la vez eso
dispara la memoria y la instancia hace OOM. Esta caché guarda el resultado por prueba y lo
reutiliza mientras los INSUMOS no cambien, así el trabajo pesado se hace una sola vez.

- **Firma de invalidación:** `sha256`/tamaño de cada archivo fuente + la ficha del encargo.
  Si el auditor sube/quita un archivo o cambia la ficha, la firma cambia y la caché se
  recalcula sola. Además se invalida explícitamente al Procesar, Encerar y en la purga.
- **Dónde vive:** las cédulas (bytes) y los extras (JSON del panel) en memoria; la carpeta
  recalculada en disco (bajo ``<tmp>/nomina_cache``). Tope ``AUD_NOMINA_CACHE_MAX`` (def. 6)
  pruebas; al exceder, se desaloja la más antigua y se borra su carpeta.

Es una caché EN PROCESO (válida con una sola instancia/worker, como hoy). No persiste entre
reinicios (al arrancar se limpia la carpeta base para no dejar basura de corridas previas)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import time

_LOCK = threading.Lock()
_CACHE: dict[int, dict] = {}
_MAX = max(1, int(os.getenv("AUD_NOMINA_CACHE_MAX", "6") or "6"))

# Carpeta base de los recalc cacheados. Se limpia al importar (arranque) para no heredar
# carpetas huérfanas de una corrida anterior del proceso.
BASE = os.path.join(tempfile.gettempdir(), "nomina_cache")
try:
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)
except OSError:  # pragma: no cover - entorno sin /tmp escribible
    pass

# Campos de la ficha que afectan el contenido de las cédulas (van en encabezados/identidad).
_CAMPOS_FICHA = ("client", "cliente", "ruc", "year", "ejercicio", "cutoff", "corte",
                 "visit", "visita", "framework", "marco", "edition", "edicion",
                 "firm", "firma", "preparer", "preparado", "reviewer", "revisado",
                 "currency", "moneda", "country", "pais")


def firma(archivos_rows, engagement: dict | None) -> str:
    """Huella que cambia si cambian los insumos o la ficha. ``archivos_rows`` = filas
    ``PruebaArchivo`` (usa su ``sha256``/``tamano``, ya calculados; no re-hashea bytes)."""
    base = sorted(
        [a.requerimiento, a.componente or "", a.nombre, a.sha256, int(a.tamano or 0)]
        for a in archivos_rows
        if getattr(a, "clase", "source") == "source" and getattr(a, "estado", None) != "rechazado"
    )
    eng = {k: (engagement or {}).get(k) for k in _CAMPOS_FICHA}
    crudo = json.dumps({"arch": base, "eng": eng}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


def _rmtree_recalc(recalc_dir: str | None) -> None:
    """Borra la raíz de trabajo que contiene ``recalc`` (``<raiz>/recalc``)."""
    if recalc_dir:
        shutil.rmtree(os.path.dirname(recalc_dir) or recalc_dir, ignore_errors=True)


def _borrar_locked(pid: int) -> None:
    e = _CACHE.pop(pid, None)
    if e:
        _rmtree_recalc(e.get("recalc_dir"))


def _evict_locked() -> None:
    while len(_CACHE) > _MAX:
        viejo = min(_CACHE, key=lambda k: _CACHE[k]["ts"])
        _borrar_locked(viejo)


def _entrada_locked(pid: int, f: str) -> dict:
    e = _CACHE.get(pid)
    if not e or e["firma"] != f:
        if e:
            _rmtree_recalc(e.get("recalc_dir"))  # firma vieja: su recalc ya no sirve
        e = {"firma": f, "cedulas": None, "extras": None, "recalc_dir": None, "ts": time.time()}
        _CACHE[pid] = e
    return e


def obtener(pid: int, f: str) -> dict | None:
    """Entrada cacheada (copia) si la firma coincide; ``None`` si no hay o cambió el insumo."""
    with _LOCK:
        e = _CACHE.get(pid)
        if e and e["firma"] == f:
            e["ts"] = time.time()
            return dict(e)
        return None


def guardar_cedulas(pid: int, f: str, cedulas: dict, extras: dict | None = None) -> None:
    with _LOCK:
        e = _entrada_locked(pid, f)
        e["cedulas"] = cedulas
        if extras is not None:
            e["extras"] = extras
        e["ts"] = time.time()
        _evict_locked()


def guardar_recalc(pid: int, f: str, recalc_dir: str, extras: dict | None = None) -> None:
    with _LOCK:
        e = _entrada_locked(pid, f)
        if e.get("recalc_dir") and e["recalc_dir"] != recalc_dir:
            _rmtree_recalc(e["recalc_dir"])
        e["recalc_dir"] = recalc_dir
        if extras is not None:
            e["extras"] = extras
        e["ts"] = time.time()
        _evict_locked()


def invalidar(pid: int) -> None:
    """Olvida y borra lo cacheado de una prueba (al Procesar, Encerar o purgar)."""
    with _LOCK:
        _borrar_locked(pid)


def nuevo_dir_recalc() -> str:
    """Raíz de trabajo persistente (NO temporal de un request) para un recalc cacheado."""
    return tempfile.mkdtemp(prefix="p_", dir=BASE)
