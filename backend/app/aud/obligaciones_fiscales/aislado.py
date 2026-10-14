"""O2 · Aislamiento del armado del Libro DM en un SUBPROCESO (anti-OOM).

El Libro DM de Obligaciones Fiscales materializa TODOS los movimientos del mayor y escribe
una celda openpyxl por movimiento, sin tope: es el único generador que crece con el volumen
transaccional del cliente. Hoy corre dentro del proceso de ``uvicorn`` (``jobs.process_job``,
un BackgroundTask), así que un cliente con un mayor grande puede disparar el OOM del
contenedor y matar el backend para todos (mismo incidente que motivó el O2 del NIIF).

Este módulo corre ese armado en un **proceso hijo** con ``multiprocessing`` en modo **``spawn``**
(NO ``fork``: ``uvicorn`` tiene hilos y un ``fork`` heredaría locks → deadlock). El hijo
re-lee TODO desde ``job_id`` (los mayores del disco y la clasificación desde su propia sesión
de BD) y escribe ``output.xlsx`` él mismo; por la cola solo viaja el ``summary`` (pequeño).
Al terminar el hijo, el sistema operativo recupera el 100 % de su memoria.

Capacidades (mismas que el O2 del NIIF):
  * Tope de RSS por trabajo: watchdog desde el padre leyendo ``/proc/<pid>/statm`` (no se usa
    ``RLIMIT_AS``, que mataría pandas/numpy por su reserva virtual enorme).
  * Tiempo máximo por trabajo (``timeout_s``).
  * El error del hijo se re-lanza como ``GeneracionLibroAislada``; el hijo se termina/mata/join
    siempre.
  * Concurrencia: el llamador (``jobs.process_job``) lo envuelve en
    ``concurrencia.limite_proceso_pesado`` (el mismo cupo global que NIIF y nómina).

Flag: ``OF_O2_SUBPROCESO`` (ver ``jobs._o2_activo``). Apagado = armado en proceso (reversión).

ponytail: el motor spawn/watchdog/timeout está duplicado de ``niif/procesadores/aislado.py``
(firmas de salida distintas: allí ``(xlsx, html)`` por archivos; aquí un ``summary`` + el output
al disco). Si un tercer sitio lo necesita, unificar en un helper común ``subproceso.py``.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import queue as _queue
import time
import traceback

MEM_MB = int(os.getenv("AUD_O2_MEM_MB", "0") or "0")          # tope de RSS por trabajo (0 = sin watchdog)
TIMEOUT_S = float(os.getenv("AUD_O2_TIMEOUT_S", "300") or "300")
_PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


class GeneracionLibroAislada(RuntimeError):
    """El armado del Libro DM en el subproceso falló (error, OOM del trabajo o timeout)."""


def _rss_mb(pid: int) -> float:
    try:
        with open(f"/proc/{pid}/statm", "r") as f:
            return int(f.read().split()[1]) * _PAGE / 1048576.0
    except Exception:
        return 0.0


def _trabajo(job_id: int, cola) -> None:
    """Corre en el HIJO: abre su propia sesión de BD, arma el Libro DM (lee mayores del disco +
    clasificación de la BD, escribe ``output.xlsx``) y manda el ``summary`` por la cola. NO marca
    el estado del job (eso lo hace el padre)."""
    try:
        from backend.app.aud.obligaciones_fiscales import jobs
        from backend.app.aud.obligaciones_fiscales.models import ToolJob
        from backend.app.db.session import SessionLocal
        db = SessionLocal()
        try:
            job = db.get(ToolJob, job_id)
            if job is None:
                cola.put(("err", f"ToolJob {job_id} no encontrado en el subproceso", ""))
                return
            summary = jobs._generar_output_libro(db, job, job_id)
            cola.put(("ok", summary))
        finally:
            db.close()
    except MemoryError:
        cola.put(("mem", None))
    except BaseException as e:  # noqa: BLE001
        cola.put(("err", f"{type(e).__name__}: {e}", traceback.format_exc()[-2000:]))


def generar_libro_aislado(job_id: int, mem_mb: int | None = None,
                          timeout_s: float | None = None) -> dict:
    """Arma el Libro DM del ``job_id`` en un subproceso aislado. El hijo escribe ``output.xlsx``;
    esta función devuelve el ``summary`` o lanza ``GeneracionLibroAislada`` (error/OOM/timeout)."""
    mem_mb = MEM_MB if mem_mb is None else mem_mb
    timeout_s = TIMEOUT_S if timeout_s is None else timeout_s
    ctx = mp.get_context("spawn")
    cola = ctx.Queue()
    hijo = ctx.Process(target=_trabajo, args=(job_id, cola), daemon=True)
    hijo.start()
    limite = time.monotonic() + timeout_s
    pico = 0.0
    estado = None
    try:
        while True:
            try:
                estado = cola.get(timeout=0.2)   # drena activamente (desbloquea al hijo)
                break
            except _queue.Empty:
                pass
            if mem_mb:
                r = _rss_mb(hijo.pid)
                pico = max(pico, r)
                if r > mem_mb:
                    raise GeneracionLibroAislada(
                        f"El Libro DM superó el tope de memoria ({r:.0f} MB > {mem_mb} MB).")
            if time.monotonic() > limite:
                raise GeneracionLibroAislada(
                    f"El armado del Libro DM superó el tiempo máximo ({timeout_s:.0f}s).")
            if not hijo.is_alive():
                try:
                    estado = cola.get(timeout=2)
                    break
                except _queue.Empty:
                    raise GeneracionLibroAislada(
                        f"El subproceso del Libro DM terminó sin resultado "
                        f"(posible OOM del sistema; pico ~{pico:.0f} MB).")
        tipo = estado[0]
        if tipo == "ok":
            return estado[1]
        if tipo == "mem":
            raise GeneracionLibroAislada(
                "El Libro DM agotó la memoria asignada (MemoryError en el subproceso).")
        raise GeneracionLibroAislada(estado[1])
    finally:
        if hijo.is_alive():
            hijo.terminate()
        hijo.join(5)
        if hijo.is_alive():
            try:
                hijo.kill()
            except Exception:
                pass
            hijo.join(2)
