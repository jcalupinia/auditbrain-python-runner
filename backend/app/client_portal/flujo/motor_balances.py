# backend/app/client_portal/flujo/motor_balances.py
"""Motor de balances multi-período: consolida balances crudos de varios
archivos/años, propaga la homologación por cuenta y calcula el cuadre por
período. Reutiliza ``motor.homologar_balanza`` para la agrupación por Super Cías.
"""
from __future__ import annotations

import re


def _orden_periodo(label: str) -> tuple[int, int]:
    """Clave de orden cronológico: (año, mes). 'may-2026' -> (2026,5); '2025' -> (2025,12);
    '31-may-2026' -> (2026,5)."""
    meses = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
             "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}
    m = re.search(r"([a-z]{3})-(\d{4})", label)
    if m:
        return (int(m.group(2)), meses.get(m.group(1), 12))
    m = re.search(r"(\d{4})", label)
    return (int(m.group(1)), 12) if m else (0, 0)


def consolidar_multiarchivo(archivos: list[dict]) -> dict:
    """Une varios archivos (cada uno ``{estado, periodos, filas}``) de un MISMO
    estado en una tabla multi-período. Devuelve ``{"periodos": [...ordenados...],
    "filas": [{cuenta, nombre, saldos:{periodo:val}}], "avisos": [...]}``.

    - Unión por ``cuenta``; período faltante -> 0.
    - Año duplicado (mismo período en dos archivos): conserva el PRIMERO y avisa,
      nunca suma ni reemplaza en silencio.
    """
    periodos: list[str] = []
    avisos: list[str] = []
    fichas: dict[str, dict] = {}
    vistos: set[str] = set()
    for arch in archivos:
        for p in arch.get("periodos", []):
            if p in vistos:
                avisos.append(f"Período '{p}' duplicado en más de un archivo; se conserva el primero.")
                continue
            vistos.add(p)
            periodos.append(p)
            idx = arch["periodos"].index(p)
            for fila in arch.get("filas", []):
                cta = fila["cuenta"]
                f = fichas.setdefault(cta, {"cuenta": cta, "nombre": fila.get("nombre", ""), "saldos": {}})
                if not f["nombre"]:
                    f["nombre"] = fila.get("nombre", "")
                saldos = fila.get("saldos", [])
                f["saldos"][p] = float(saldos[idx]) if idx < len(saldos) else 0.0
    periodos.sort(key=_orden_periodo)
    for f in fichas.values():
        for p in periodos:
            f["saldos"].setdefault(p, 0.0)
    return {"periodos": periodos, "filas": list(fichas.values()), "avisos": avisos}
