# backend/app/client_portal/flujo/catalogos.py
"""Carga los catálogos oficiales (estructura ESF/ERI, plan Super Cías/SRI) y
construye el árbol jerárquico por prefijo de código."""
from __future__ import annotations
import csv
import os
from dataclasses import dataclass

_DATA = os.path.join(os.path.dirname(__file__), "data")
_ARCHIVOS = {"esf": "estructura_esf.csv", "eri": "estructura_eri.csv"}


@dataclass
class Nodo:
    codigo: str
    etiqueta: str
    padre: str | None
    es_hoja: bool


def _leer(nombre: str) -> list[tuple[str, str]]:
    ruta = os.path.join(_DATA, nombre)
    out = []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cod = (row.get("codigo_super_cias") or "").strip()
            if cod:
                out.append((cod, (row.get("etiqueta") or "").strip()))
    return out


def cargar_estructura(estado: str) -> list[Nodo]:
    """estado ∈ {'esf','eri'}. Devuelve nodos con padre (prefijo más largo
    presente) y es_hoja (ningún otro código lo tiene como prefijo)."""
    filas = _leer(_ARCHIVOS[estado])
    codes = {c for c, _ in filas}

    def padre(cod: str) -> str | None:
        for L in range(len(cod) - 1, 0, -1):
            if cod[:L] in codes:
                return cod[:L]
        return None

    tiene_hijo = {c: False for c in codes}
    for c in codes:
        p = padre(c)
        if p is not None:
            tiene_hijo[p] = True

    return [Nodo(codigo=c, etiqueta=e, padre=padre(c), es_hoja=not tiene_hijo[c])
            for c, e in filas]


def cargar_agregados_f101() -> dict[str, list[str]]:
    """Devuelve {casillero: [tokens con signo]}, ej. {'499': ['+449','+361']}."""
    out: dict[str, list[str]] = {}
    ruta = os.path.join(_DATA, "f101_agregados.csv")
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cas = (row.get("casillero") or "").strip()
            hijos = (row.get("hijos_con_signo") or "").split()
            if cas and hijos:
                out[cas] = hijos
    return out


def cargar_clasificacion_flujo() -> dict[str, str]:
    """Devuelve {codigo_super_cias: actividad} (OPERACION/INVERSION/FINANCIAMIENTO)
    desde flujo_clasificacion_actividad.csv."""
    out: dict[str, str] = {}
    ruta = os.path.join(_DATA, "flujo_clasificacion_actividad.csv")
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cod = (row.get("codigo_super_cias") or "").strip()
            act = (row.get("actividad") or "").strip().upper()
            if cod and act:
                out[cod] = act
    return out
