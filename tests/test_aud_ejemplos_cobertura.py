"""Cobertura global de ejemplos por requerimiento en TODAS las herramientas NIIF.

Garantiza la decisión del socio (18 herramientas de catálogo + pérdidas incurridas
+ PCE): cada procesador con requerimientos tiene, para CADA requerimiento, un
ejemplo en el manifiesto del frontend y su archivo en disco; y el «Ejercicio
modelo» está disponible en todas. Este test es el guardián que impide que una
herramienta nueva quede solo con el modelo vacío o sin ejercicio modelo.
"""
import os
import re

from openpyxl import load_workbook

from backend.app.aud.niif import ejercicio_modelo
from backend.app.aud.niif.procesadores import PROCESADORES

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(RAIZ, "frontend", "public", "ejemplos")
MANIFIESTO = os.path.join(RAIZ, "frontend", "src", "aud", "niif", "ejemplosRequerimientos.js")

FIRMAS = {".pdf": b"%PDF-", ".xlsx": b"PK", ".docx": b"PK", ".csv": b""}


def _manifiesto_tool(pid):
    js = open(MANIFIESTO, encoding="utf-8").read()
    m = re.search(rf"\b{pid}:\s*\{{(.*?)\}}", js, re.S)
    return dict(re.findall(r'"(RQ-\d+)":\s*"([^"]+)"', m.group(1))) if m else {}


def _con_requerimientos():
    """Todos los procesadores que exponen requerimientos en su definición."""
    out = []
    for pid, mod in PROCESADORES.items():
        try:
            d = mod.definicion()
        except Exception:  # noqa: BLE001
            continue
        if d.get("requests"):
            out.append(pid)
    return out


def test_todas_las_herramientas_tienen_ejemplo_en_cada_requerimiento():
    pids = _con_requerimientos()
    assert len(pids) >= 20, f"se esperaban >=20 herramientas con requerimientos, hay {len(pids)}"
    faltantes = []
    for pid in pids:
        entradas = _manifiesto_tool(pid)
        for r in PROCESADORES[pid].definicion()["requests"]:
            nombre = entradas.get(r["id"])
            ruta = os.path.join(PUB, pid, nombre) if nombre else None
            if not nombre or not os.path.exists(ruta):
                faltantes.append(f"{pid}/{r['id']}")
                continue
            ext = os.path.splitext(ruta)[1]
            data = open(ruta, "rb").read()
            assert len(data) > 500 and data.startswith(FIRMAS.get(ext, b"")), f"{pid}/{nombre}: archivo inválido"
    assert not faltantes, "requerimientos sin ejemplo: " + ", ".join(faltantes)


def test_ejercicio_modelo_disponible_en_todas():
    sin = [pid for pid in _con_requerimientos() if not ejercicio_modelo.disponible(PROCESADORES[pid])]
    assert not sin, "sin ejercicio modelo: " + ", ".join(sin)


def test_ningun_xlsx_de_ejemplo_levanta_reparacion():
    for pid in _con_requerimientos():
        for nombre in _manifiesto_tool(pid).values():
            if nombre.endswith(".xlsx"):
                load_workbook(os.path.join(PUB, pid, nombre))  # abre sin «reparar»
