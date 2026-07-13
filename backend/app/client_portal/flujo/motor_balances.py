# backend/app/client_portal/flujo/motor_balances.py
"""Motor de balances multi-período: consolida balances crudos de varios
archivos/años, propaga la homologación por cuenta y calcula el cuadre A=P+Pat
por período agrupando por sección del Código Super Cías (1/2/3). El cuadre se
REPORTA, nunca se fuerza; las cuentas huérfanas (sin Super Cías) se listan aparte.
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
                val = float(saldos[idx]) if idx < len(saldos) else 0.0
                f["saldos"][p] = f["saldos"].get(p, 0.0) + val
    periodos.sort(key=_orden_periodo)
    for f in fichas.values():
        for p in periodos:
            f["saldos"].setdefault(p, 0.0)
    return {"periodos": periodos, "filas": list(fichas.values()), "avisos": avisos}


def propagar_homologacion(filas: list[dict], mapeo: dict[str, tuple[str, str]]) -> list[dict]:
    """Asigna ``super_cias``/``sri`` a cada ficha según ``mapeo`` (cuenta cliente ->
    (super, sri)). Las que no están en el mapeo quedan con "" (huérfanas). No pierde
    ninguna cuenta. Devuelve nuevas fichas (no muta las de entrada)."""
    out = []
    for f in filas:
        sc, sri = mapeo.get(f["cuenta"], ("", ""))
        out.append({**f, "super_cias": sc, "sri": sri})
    return out


def huerfanas(filas: list[dict]) -> list[str]:
    """Códigos de cuenta cliente sin Super Cías asignado, en orden de aparición."""
    return [f["cuenta"] for f in filas if not f.get("super_cias")]


def cuadre_por_periodo(filas: list[dict], periodos: list[str], tolerancia: float = 1.0) -> dict:
    """Cuadre A = P + Patrimonio por período, agrupando por sección del Código Super
    Cías (1=activo, 2=pasivo, 3=patrimonio; 2 y 3 son crédito/negativo). **Reporta,
    nunca fuerza.** Devuelve ``{periodo: {"activo","pas_pat","diferencia","cuadra"}}``.
    Las cuentas huérfanas (sin super_cias) NO entran al cuadre."""
    out: dict[str, dict] = {}
    for p in periodos:
        sec = {"1": 0.0, "2": 0.0, "3": 0.0}
        for f in filas:
            sc = str(f.get("super_cias") or "")
            if sc[:1] in sec:
                sec[sc[:1]] += float(f["saldos"].get(p, 0.0))
        activo = round(sec["1"], 2)
        pas_pat = round(-(sec["2"] + sec["3"]), 2)
        dif = round(activo - pas_pat, 2)
        out[p] = {"activo": activo, "pas_pat": pas_pat, "diferencia": dif,
                  "cuadra": abs(dif) <= tolerancia}
    return out


def _vacio() -> dict:
    return {"periodos": [], "filas": [], "avisos": []}


def homologar_archivos(archivos: list[tuple[str, bytes]]) -> dict:
    """Orquesta la ingesta: por cada archivo detecta si es un "balance mapeado"
    (trae columnas Super Cías/SRI → fuente de homologación) o un balance CRUDO
    multi-período; consolida los crudos por estado (ESF/ERI), propaga la
    homologación del mapeado, y calcula huérfanas y cuadre por período.
    ``archivos``: lista de ``(nombre, bytes)``.
    Devuelve ``{"esf": {periodos, filas, avisos, cuadre, huerfanas},
    "eri": {periodos, filas, avisos, huerfanas}}``."""
    from . import parser  # import diferido
    mapeo: dict[str, tuple[str, str]] = {}
    esf_raw: list[dict] = []
    eri_raw: list[dict] = []
    for _nombre, contenido in archivos:
        mapeados = parser.parse_balanza(contenido)
        if mapeados:
            for f in mapeados:
                if f.get("super_cias") and f["cuenta"] not in mapeo:
                    mapeo[f["cuenta"]] = (f["super_cias"], f.get("sri", ""))
            continue
        res = parser.parse_balanza_multiperiodo(contenido)
        (esf_raw if res["estado"] == "esf" else eri_raw).append(res)
    cons_esf = consolidar_multiarchivo(esf_raw) if esf_raw else _vacio()
    cons_eri = consolidar_multiarchivo(eri_raw) if eri_raw else _vacio()
    esf_h = propagar_homologacion(cons_esf["filas"], mapeo)
    eri_h = propagar_homologacion(cons_eri["filas"], mapeo)
    return {
        "esf": {"periodos": cons_esf["periodos"], "filas": esf_h,
                "avisos": cons_esf["avisos"],
                "cuadre": cuadre_por_periodo(esf_h, cons_esf["periodos"]),
                "huerfanas": huerfanas(esf_h)},
        "eri": {"periodos": cons_eri["periodos"], "filas": eri_h,
                "avisos": cons_eri["avisos"], "huerfanas": huerfanas(eri_h)},
    }


def recalcular_homologado(esf: dict, eri: dict) -> dict:
    """Recalcula cuadre (ESF) y huérfanas (ESF y ERI) a partir de las tablas
    editadas por el usuario (mismos dicts que devuelve ``homologar_archivos``,
    con super_cias/sri corregidos). No re-parsea archivos."""
    return {
        "esf": {**esf,
                "cuadre": cuadre_por_periodo(esf.get("filas", []), esf.get("periodos", [])),
                "huerfanas": huerfanas(esf.get("filas", []))},
        "eri": {**eri, "huerfanas": huerfanas(eri.get("filas", []))},
    }
