"""Datos del ejemplo realista de cada herramienta NIIF, leídos de los MISMOS
archivos que el cliente descarga con la flecha «↓ Ejemplo».

Fuente única: el manifiesto ``frontend/src/aud/niif/ejemplosRequerimientos.js``
dice qué archivo corresponde a cada requerimiento; para cada requerimiento que
alimenta el cálculo (``dataset``) se lee su .xlsx con el lector del ciclo
(``datos.read_spreadsheet`` + ``mapped_rows``) y el mismo mapeo automático que la
vista (rótulos de ``CAMPOS``). Así el ejercicio modelo y los papeles de muestra se
arman con exactamente lo que ve el cliente (en pérdidas incurridas: 6 clientes y
3 ejercicios), y no con los escenarios mínimos de prueba.

Los parámetros y la fecha de corte salen de la misma fuente con la que se
generaron los archivos: ``ejemplos_pi`` en pérdidas incurridas y PCE (misma cartera
de 6 clientes); el ``EJEMPLO`` del procesador (o su primer escenario) en las demás.
"""
from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache

from backend.app.aud.niif.ciclo import datos as datos_mod

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
PUB = os.path.join(RAIZ, "frontend", "public", "ejemplos")
MANIFIESTO = os.path.join(RAIZ, "frontend", "src", "aud", "niif", "ejemplosRequerimientos.js")


def _normal(t) -> str:
    """Réplica de cicloLogic.js::normal (minúsculas, sin tildes, solo [a-z0-9])."""
    s = unicodedata.normalize("NFD", str(t or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def mapeo_sugerido(encabezados, campos) -> dict:
    """Réplica de cicloLogic.js::mapeoSugerido."""
    cols = [_normal(c) for c in encabezados]
    mapa = {}
    for f in campos:
        nombres = {_normal(x) for x in [f["label"], f["key"], *f.get("aliases", [])]}
        for i, c in enumerate(cols):
            if c and c in nombres:
                mapa[f["key"]] = i
                break
    return mapa


@lru_cache(maxsize=1)
def _manifiesto_js() -> str:
    try:
        with open(MANIFIESTO, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def archivos(pid: str) -> dict:
    """{RQ-xxx: nombre de archivo} del bloque del procesador en el manifiesto."""
    m = re.search(rf"\b{re.escape(pid)}:\s*\{{(.*?)\}}", _manifiesto_js(), re.S)
    return dict(re.findall(r'"(RQ-\d+)":\s*"([^"]+)"', m.group(1))) if m else {}


def _fuente(mod):
    """(parámetros, corte) de la fuente con la que se generaron los archivos."""
    if getattr(mod, "__name__", "").endswith("perdidas_incurridas_s11"):
        from backend.app.aud.niif import ejemplos_pi
        e = ejemplos_pi.ejercicio_modelo()
        return e["parametros"], e["corte"]
    if getattr(mod, "__name__", "").endswith("pce_simplificada_niif9"):
        from backend.app.aud.niif import ejemplos_pi
        e = ejemplos_pi.pce_ejemplo()
        return e["parametros"], e["corte"]
    E = getattr(mod, "EJEMPLO", None)
    if E and E.get("datasets"):
        return E.get("parametros", {}), E["corte"]
    esc = getattr(mod, "ESCENARIOS", None)
    if esc:
        _, _, par, corte = esc[0]
        return par, corte
    return None


def datasets(mod) -> tuple[dict, dict, str] | None:
    """(datasets, parámetros, corte) del ejemplo realista del manifiesto, o None si la
    herramienta no tiene archivos de ejemplo para sus requerimientos de cálculo."""
    pid = getattr(mod, "__name__", "").rsplit(".", 1)[-1]
    fuente = _fuente(mod)
    if fuente is None:
        return None
    entradas = archivos(pid)
    if not entradas:
        return None
    d = mod.definicion()
    conjuntos: dict[str, list] = {}
    for r in d.get("requests", []):
        ds = r.get("dataset")
        nombre = entradas.get(r["id"])
        if not ds or not nombre or not nombre.lower().endswith((".xlsx", ".csv")):
            continue
        ruta = os.path.join(PUB, pid, nombre)
        if not os.path.exists(ruta):
            return None
        with open(ruta, "rb") as fh:
            libro = datos_mod.read_spreadsheet(fh.read(), nombre)
        hoja = next((s for s in libro["sheets"] if s["name"] == "Datos"), libro["sheets"][0])
        campos = mod.CAMPOS[mod.kind(ds)]
        mapa = mapeo_sugerido(hoja["rows"][0] if hoja["rows"] else [], campos)
        faltan = [c["key"] for c in campos if c["key"] not in mapa]
        if faltan:
            return None  # un ejemplo que no mapea no se usa en silencio
        conjuntos[ds] = datos_mod.mapped_rows(hoja, 1, mapa, {"fields": campos}, {"id": r["id"], "name": nombre})["rows"]
    if not conjuntos:
        return None
    par, corte = fuente
    return conjuntos, par, corte
