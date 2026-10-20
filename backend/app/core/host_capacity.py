"""Lectura de capacidad del host para la admisión dinámica de previews (docs/previews-coolify.md §11).

Solo biblioteca estándar y archivos de /proc: en un contenedor Docker, ``/proc/meminfo``, ``/proc/loadavg`` y
``/proc/pressure/memory`` reflejan el HOST completo (no el cgroup), que es exactamente lo que necesita la política
de capacidad; el disco se mide sobre la raíz del contenedor (overlay sobre el sistema de archivos del host).
No devuelve nada sensible: números agregados del host, sin nombres de contenedores, IP ni variables.
Los eventos OOM no son observables desde un contenedor sin privilegios: ``oom_recent`` es ``None`` (desconocido).
"""
from __future__ import annotations

import datetime as _dt
import os
import shutil


def _meminfo(path: str) -> dict:
    out: dict[str, int] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for linea in f:
                k, _, resto = linea.partition(":")
                partes = resto.split()
                if partes and partes[0].isdigit():
                    out[k.strip()] = int(partes[0])  # kB
    except OSError:
        pass
    return out


def _psi_some_avg60(path: str) -> float | None:
    try:
        with open(path, encoding="utf-8") as f:
            for linea in f:
                if linea.startswith("some"):
                    for campo in linea.split():
                        if campo.startswith("avg60="):
                            return float(campo.split("=", 1)[1])
    except (OSError, ValueError):
        return None
    return None


def _load1(path: str) -> float | None:
    try:
        with open(path, encoding="utf-8") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def host_capacity_snapshot(*, meminfo: str = "/proc/meminfo", psi: str = "/proc/pressure/memory",
                           loadavg: str = "/proc/loadavg", disk_path: str | None = None) -> dict:
    m = _meminfo(meminfo)
    swap_total = m.get("SwapTotal", 0)
    swap_used = max(0, swap_total - m.get("SwapFree", 0))
    disk_path = disk_path or os.getenv("HOST_CAPACITY_DISK_PATH", "/")
    try:
        libre = shutil.disk_usage(disk_path).free
    except OSError:
        libre = None
    return {
        "observed_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "proc",
        "mem_total_mib": m.get("MemTotal", 0) // 1024,
        "mem_available_mib": m.get("MemAvailable", 0) // 1024,   # RAM real disponible; la swap NO cuenta
        "swap_total_mib": swap_total // 1024,
        "swap_used_mib": swap_used // 1024,
        "swap_used_pct": round(swap_used * 100 / swap_total, 1) if swap_total else 0.0,
        "psi_mem_some_avg60": _psi_some_avg60(psi),
        "load1": _load1(loadavg),
        "cpus": os.cpu_count(),
        "disk_path": disk_path,
        "disk_free_gib": None if libre is None else round(libre / 1024 ** 3, 2),
        "oom_recent": None,
    }
