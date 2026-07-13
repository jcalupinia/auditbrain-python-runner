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


def cargar_no_efectivo() -> dict[str, str]:
    """Devuelve {codigo_eri: categoria} de las cuentas de gasto que NO son
    desembolso de efectivo (DEPRECIACION/AMORTIZACION/DETERIORO), desde
    no_efectivo_eri.csv. Son los add-backs de la conciliación del flujo."""
    out: dict[str, str] = {}
    ruta = os.path.join(_DATA, "no_efectivo_eri.csv")
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cod = (row.get("codigo_eri") or "").strip()
            cat = (row.get("categoria") or "").strip().upper()
            if cod and cat:
                out[cod] = cat
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


def cargar_plan_cuentas() -> dict:
    """Devuelve el plan de cuentas oficial para poblar los selectores del editor
    de balanzas: ``{"super": [{codigo, nombre}...], "sri": [{codigo, nombre}...]}``.

    - ``super``: todas las cuentas Super Cías (código + nombre), en orden de archivo.
    - ``sri``: casilleros SRI únicos (código + nombre), ordenados por código.
    Fuente: ``plan_cuentas_super_sri.csv`` (mismo plan que usa la homologación).
    """
    ruta = os.path.join(_DATA, "plan_cuentas_super_sri.csv")
    super_map: dict[str, str] = {}   # dedup por código (el CSV trae una fila por par super↔SRI)
    sri_map: dict[str, str] = {}
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cs = (row.get("codigo_super_cias") or "").strip()
            if cs and cs not in super_map:
                super_map[cs] = (row.get("nombre_cuenta") or "").strip()
            sri = (row.get("codigo_sri") or "").strip()
            if sri and sri not in sri_map:
                sri_map[sri] = (row.get("nombre_sri") or "").strip()
    super_rows = [{"codigo": k, "nombre": v} for k, v in super_map.items()]
    sri_rows = [{"codigo": k, "nombre": v}
                for k, v in sorted(sri_map.items(), key=lambda kv: (len(kv[0]), kv[0]))]
    return {"super": super_rows, "sri": sri_rows}


def cargar_mapa_super_sri(ruta: str | None = None) -> dict:
    """Mapa de homologación derivado de ``plan_cuentas_super_sri.csv`` para los
    desplegables enlazados Super↔SRI y la homologación contra el plan.

    Devuelve ``{"super_a_sri": {sc: [sri...]}, "sri_a_super": {sri: [sc...]},
    "nombre_super": {sc: nombre}, "nombre_sri": {sri: nombre}}``. Soporta 1:N
    (un código Super puede mapear a varios SRI; ej. ventas por tarifa IVA).
    """
    if ruta is None:
        ruta = os.path.join(_DATA, "plan_cuentas_super_sri.csv")
    super_a_sri: dict[str, list[str]] = {}
    sri_a_super: dict[str, list[str]] = {}
    nombre_super: dict[str, str] = {}
    nombre_sri: dict[str, str] = {}
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sc = (row.get("codigo_super_cias") or "").strip()
            sri = (row.get("codigo_sri") or "").strip()
            if sc and sc not in nombre_super:
                nombre_super[sc] = (row.get("nombre_cuenta") or "").strip()
            if sri and sri not in nombre_sri:
                nombre_sri[sri] = (row.get("nombre_sri") or "").strip()
            if sc and sri:
                super_a_sri.setdefault(sc, [])
                if sri not in super_a_sri[sc]:
                    super_a_sri[sc].append(sri)
                sri_a_super.setdefault(sri, [])
                if sc not in sri_a_super[sri]:
                    sri_a_super[sri].append(sc)
    return {"super_a_sri": super_a_sri, "sri_a_super": sri_a_super,
            "nombre_super": nombre_super, "nombre_sri": nombre_sri}
