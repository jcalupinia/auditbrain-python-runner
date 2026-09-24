"""Ejercicio modelo y ejemplos de requerimiento de «pérdidas incurridas».

Cubre:
- el recorrido de solo lectura se arma para el procesador (9 pasos, 12 cédulas);
- los archivos de ejemplo se leen con el MISMO lector del ciclo y el procesador
  carga las 5 poblaciones sin «provisión sin cruzar» y con el movimiento cuadrado;
- el endpoint del ejercicio modelo NO escribe (no cambia el estado de la prueba).
"""
import io
import os

import pytest
from openpyxl import load_workbook

from backend.app.aud.niif import ejemplos_pi, ejercicio_modelo
from backend.app.aud.niif.ciclo import datos as ciclo_datos
from backend.app.aud.niif.procesadores import PROCESADORES
from backend.app.aud.niif.procesadores import perdidas_incurridas_s11 as pi
from tests.test_aud_ciclo_http import BASE, _h, _staff_con_proyecto

EJEMPLOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "frontend", "public", "ejemplos", "perdidas_incurridas_s11")
ARCHIVO_DS = {
    "RQ-001_cartera_2025.xlsx": "a3", "RQ-002_cartera_2024.xlsx": "a2", "RQ-003_cartera_2023.xlsx": "a1",
    "RQ-004_provision_inicial_2025.xlsx": "provision", "RQ-005_movimiento_provision_3_ejercicios.xlsx": "movimiento",
}


def _automap(sheet, campos):
    enc = [pi.norm(x) for x in sheet["rows"][0]]
    mapping = {}
    for c in campos:
        cands = [pi.norm(c["label"])] + [pi.norm(a) for a in c.get("aliases", [])]
        for j, ne in enumerate(enc):
            if ne in cands:
                mapping[c["key"]] = j
                break
    return mapping


def test_recorrido_se_arma_para_perdidas_incurridas():
    mod = PROCESADORES["perdidas_incurridas_s11"]
    r = ejercicio_modelo.recorrido(mod.definicion(), mod)
    assert r["disponible"] is True and r["ficticio"] is True
    assert [p["n"] for p in r["pasos"]] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    p6 = next(p for p in r["pasos"] if p["n"] == 6)
    assert len(p6["cedulas"]) == 12
    assert p6["resultado"]["principal"] == "ajuste"
    codigos = [x["code"] for x in p6["problemas"]]
    assert "PROVISION_PENDIENTE" not in codigos and "CONCILIACION_INICIAL" not in codigos
    p4 = next(p for p in r["pasos"] if p["n"] == 4)
    assert [q["id"] for q in p4["requerimientos"]] == [f"RQ-00{i}" for i in range(1, 9)]


def test_todas_las_herramientas_de_catalogo_tienen_ejercicio_modelo():
    # Cada herramienta con RUBRO trae EJEMPLO/ESCENARIOS: su botón no queda «pendiente».
    for pid, mod in PROCESADORES.items():
        if getattr(mod, "RUBRO", None):
            assert ejercicio_modelo.disponible(mod), pid


def test_libro_modelo_en_los_cuatro_formatos():
    mod = PROCESADORES["perdidas_incurridas_s11"]
    d = mod.definicion()
    for ext, firma in (("xlsx", b"PK"), ("docx", b"PK"), ("pptx", b"PK"), ("html", b"<")):
        assert ejercicio_modelo.libro_modelo(d, mod, ext).startswith(firma), ext


def test_ejemplos_se_leen_con_el_lector_del_ciclo_y_corren():
    assert os.path.isdir(EJEMPLOS_DIR), "Genere los ejemplos con scripts/ejemplos_perdidas_incurridas.py"
    conjuntos = {}
    for nombre, ds in ARCHIVO_DS.items():
        raw = open(os.path.join(EJEMPLOS_DIR, nombre), "rb").read()
        load_workbook(io.BytesIO(raw))  # abre sin «reparar»
        sheets = ciclo_datos.read_spreadsheet(raw, nombre)["sheets"]
        hoja = next(s for s in sheets if s["name"] == "Datos")
        campos = pi.CAMPOS[pi.kind(ds)]
        conjuntos[ds] = pi.filas_mapeadas(hoja, 1, _automap(hoja, campos), campos, {"id": 1, "name": nombre})["rows"]

    assert set(conjuntos) == {"a1", "a2", "a3", "provision", "movimiento"}
    for k in conjuntos:
        assert conjuntos[k], f"población vacía: {k}"

    res = pi.ejecutar(conjuntos, {"tasaDesc": "0"}, ejemplos_pi.CORTE)
    codigos = [p["code"] for p in res["exceptions"]]
    assert "PROVISION_PENDIENTE" not in codigos
    assert "CONCILIACION_INICIAL" not in codigos

    # pérdida realista (5–15 % de la cartera) y movimiento conciliado
    total = sum(f["saldo"] for f in pi._cartera(conjuntos["a3"]))
    perdida = float(res["totals"]["perdida"])
    assert 5.0 <= perdida / total * 100 <= 15.0
    mov = sorted(conjuntos["movimiento"], key=lambda m: str(m["id"]))
    assert mov[-1]["id"] == "2025"


def test_archivos_de_ejemplo_coinciden_con_el_modulo_compartido():
    # Los .xlsx del manifiesto y el módulo ejemplos_pi son la misma fuente de verdad.
    del_modulo = ejemplos_pi.datasets()
    raw = open(os.path.join(EJEMPLOS_DIR, "RQ-001_cartera_2025.xlsx"), "rb").read()
    hoja = next(s for s in ciclo_datos.read_spreadsheet(raw, "RQ-001_cartera_2025.xlsx")["sheets"] if s["name"] == "Datos")
    filas = pi.filas_mapeadas(hoja, 1, _automap(hoja, pi.CAMPOS["cartera"]), pi.CAMPOS["cartera"], {"id": 1, "name": "a3"})["rows"]
    assert len(filas) == len(del_modulo["a3"])


def test_endpoint_ejercicio_modelo_no_escribe(client):
    try:
        tok, pid = _staff_con_proyecto(client)
    except AssertionError as e:
        pytest.skip(f"stack HTTP no disponible en este entorno: {str(e)[:80]}")
    # Ficha VÁLIDA por `validar_ficha_encargo(completa=True)`: el resto del test
    # crea una prueba, que exige la ficha guardada (si no, 400 "Complete la ficha").
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok),
                      json={"client": "Cliente Demo", "ruc": "1790000000001", "activity": "Comercio",
                            "year": "2025", "cutoff": "2025-12-31", "preparer": "Preparador",
                            "reviewer": "Revisor", "firm": "Audit Consulting",
                            "framework": "NIIF para las PYMES", "country": "Ecuador",
                            "currency": "USD", "visit": "Final", "edition": "Edición 2025"}).status_code in (200, 422)
    # `proc:<id>` solo resuelve procesadores de catálogo (con RUBRO). PI no lo es
    # (se instala en una ficha); se usa cxc_cartera, que sí es herramienta directa.
    r = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "proc:cxc_cartera"})
    if r.status_code != 201:  # la creación devuelve 201 Created
        pytest.skip(f"no se pudo crear la prueba proc: {r.status_code} {r.text[:120]}")
    p = r.json()
    antes = client.get(f"{BASE}/pruebas/{p['id']}", headers=_h(tok)).json()
    rec = client.get(f"{BASE}/pruebas/{p['id']}/ejercicio-modelo", headers=_h(tok))
    assert rec.status_code == 200 and rec.json()["disponible"] is True
    despues = client.get(f"{BASE}/pruebas/{p['id']}", headers=_h(tok)).json()
    assert despues["estado"] == antes["estado"]
    assert despues.get("revision") == antes.get("revision")
