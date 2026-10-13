# -*- coding: utf-8 -*-
"""Límite de concurrencia para el trabajo PESADO del Command Center (motor de nómina +
recálculo con LibreOffice, generación de papeles).

Motivo (decisión del dueño, 2026-10-12): el backend corre en UNA sola instancia
(≈1 CPU / 2 GB). Varios auditores lanzando «Procesar»/abriendo paneles al mismo tiempo
disparaban varios LibreOffice a la vez y la instancia **superaba su límite de memoria
(OOM) → Render la reiniciaba → se caía para todos**. Este semáforo serializa (o limita a N)
el trabajo pesado para que la memoria quede acotada; al resto se le responde «reintente en
unos segundos» en vez de apilarse hasta reventar.

- ``AUD_PROCESO_PESADO_MAX`` (def. 1): cuántos procesos pesados en paralelo se permiten.
  Con 2 GB conviene 1; al subir el plan (más RAM/CPU) se puede subir por env var.
- ``AUD_PROCESO_PESADO_TIMEOUT_S`` (def. 90): cuánto espera una petición por un cupo antes
  de rendirse con ``ProcesoOcupado`` (→ HTTP 429 del lado del router).

Es un semáforo EN PROCESO (válido porque hoy hay una sola instancia/worker). Si algún día se
escala a varias instancias/workers, habría que mover el límite a algo compartido (Redis, etc.).
"""
from __future__ import annotations

import contextlib
import os
import threading

_MAX = max(1, int(os.getenv("AUD_PROCESO_PESADO_MAX", "1") or "1"))
_TIMEOUT_S = float(os.getenv("AUD_PROCESO_PESADO_TIMEOUT_S", "90") or "90")
_SEM = threading.BoundedSemaphore(_MAX)


class ProcesoOcupado(Exception):
    """No se consiguió un cupo de proceso pesado dentro del tiempo de espera."""


@contextlib.contextmanager
def limite_proceso_pesado(timeout: float | None = None):
    """Context manager: toma un cupo del semáforo o lanza ``ProcesoOcupado`` si no hay dentro
    de ``timeout`` segundos. Úsalo SOLO alrededor del trabajo realmente pesado (motor +
    LibreOffice), nunca alrededor de una lectura de caché barata."""
    espera = _TIMEOUT_S if timeout is None else timeout
    adquirido = _SEM.acquire(timeout=espera)
    if not adquirido:
        raise ProcesoOcupado(
            "El servidor está ocupado procesando otra prueba pesada. "
            "Espere unos segundos y vuelva a intentar.")
    try:
        yield
    finally:
        _SEM.release()
