"""Ejercicio modelo de principio a fin para CADA herramienta del catálogo (procesadores con RUBRO).

Recorre el ciclo real por HTTP: prueba creada desde el catálogo (proc:<id>) → programa y fuentes →
requerimiento → modelos Excel llenados con el EJEMPLO del módulo → mapeo y validación → conciliación →
parámetros → ejecución → papel en los cuatro formatos. Los totales deben ser los mismos que el cálculo
directo del procesador con los mismos datos.
"""
import io

import pytest
from openpyxl import load_workbook

from backend.app.aud.niif import procesadores
from tests.test_aud_ciclo_evidencia import _leer, _subir
from tests.test_aud_ciclo_http import BASE, FICHA, _accion, _staff_con_proyecto
from tests.test_aud_niif_fichas import _h

CATALOGO = sorted(pid for pid, m in procesadores.PROCESADORES.items() if getattr(m, "RUBRO", None))


@pytest.fixture
def disco_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_CICLO_DIR", str(tmp_path / "aud_pruebas"))
    monkeypatch.setenv("AUD_CICLO_MIN_LIBRE_MB", "0")


def _xlsx_modelo(client, tok, p, req, campos, filas):
    r = client.get(f"{BASE}/pruebas/{p['id']}/modelo/{req}", headers=_h(tok))
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    for f in filas:
        wb["Datos"].append([("" if f.get(c["key"]) is None else f.get(c["key"])) for c in campos])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _soporte(formatos):
    if "pdf" in formatos:
        return "soporte.pdf", b"%PDF-1.4 soporte"
    if "csv" in formatos:
        return "soporte.csv", b"detalle;valor\nsoporte;1\n"
    if "txt" in formatos:
        return "soporte.txt", b"soporte"
    if "docx" in formatos:
        return "soporte.docx", b"PK\x03\x04soporte"
    return "soporte.xlsx", b"PK\x03\x04soporte"


@pytest.mark.parametrize("pid", CATALOGO)
def test_ejercicio_modelo_de_principio_a_fin(client, disco_temporal, pid):
    m = procesadores.PROCESADORES[pid]
    ej = m.EJEMPLO
    d = m.definicion()
    marco = (ej.get("parametros") or {}).get("_marco") or d["frameworks"][0]
    edicion = str((ej.get("parametros") or {}).get("_edicion") or "2015")
    tok, pid_proyecto = _staff_con_proyecto(client)

    # Aparece en el catálogo, en la tarjeta de su rubro.
    h = next(x for x in client.get(f"{BASE}/herramientas", headers=_h(tok)).json() if x["origen"] == f"proc:{pid}")
    assert h["area"] == m.RUBRO and h["tipo"] == "herramienta NIIF"

    assert client.put(f"{BASE}/proyectos/{pid_proyecto}/ficha", headers=_h(tok),
                      json={**FICHA, "framework": marco, "edition": edicion, "cutoff": ej["corte"],
                            "year": int(ej["corte"][:4])}).status_code == 200
    p = client.post(f"{BASE}/proyectos/{pid_proyecto}/pruebas", headers=_h(tok), json={"origen": f"proc:{pid}"}).json()
    assert "id" in p, p
    p = _accion(client, tok, p, "research").json()
    p = _accion(client, tok, p, "generate_program").json()
    codigos = [x["code"] for x in p["registro"]["program"]]
    fuentes = p["registro"]["sources"]
    for s in fuentes:
        s.update(verified=True, section=s.get("section") or "Párrafos de la ficha", date="vigente", procedures=codigos)
    p = _accion(client, tok, p, "approve_program", {"program": p["registro"]["program"], "sources": fuentes}).json()
    assert p["estado"] == "PROGRAMA_APROBADO", p
    p = _accion(client, tok, p, "generate_request").json()
    p = _accion(client, tok, p, "approve_request", {"requests": p["registro"]["requests"]}).json()
    assert p["estado"] == "REQUERIMIENTO_APROBADO", p

    reqs = p["registro"]["requests"]
    por_ds = {r["dataset"]: r for r in reqs if r.get("dataset")}
    for ds, filas in ej["datasets"].items():
        r = por_ds[ds]
        p = _leer(client, tok, p)
        contenido = _xlsx_modelo(client, tok, p, r["id"], m.CAMPOS[m.kind(ds)], filas)
        assert _subir(client, tok, p, r["id"], f"{r['id']}.xlsx", contenido).status_code == 201
    for r in reqs:
        if r.get("dataset") or r.get("required") is False:
            continue
        p = _leer(client, tok, p)
        nombre, contenido = _soporte(r.get("formats") or [])
        assert _subir(client, tok, p, r["id"], nombre, contenido).status_code == 201, (r["id"], r.get("formats"))
    p = _leer(client, tok, p)
    assert p["huecos"] == [], p["huecos"]

    arch = {a["requerimiento"]: a["id"] for a in p["archivos"]}
    conjuntos = {ds: [{"fileId": arch[por_ds[ds]["id"]], "sheet": "Datos", "header": 1,
                       "mapping": {c["key"]: i for i, c in enumerate(m.CAMPOS[m.kind(ds)])}}]
                 for ds in ej["datasets"]}
    p = _accion(client, tok, p, "map_validate", {"datasets": conjuntos}).json()
    assert p["registro"]["validation"]["ok"], p["registro"]["validation"]
    total_control = p["registro"]["controlTotal"]
    p = _accion(client, tok, p, "validate", {"evidenceReviewed": True, "evidenceReview": "Ejercicio modelo cotejado.",
                                             "ledger": total_control, "tolerance": "0"}).json()
    assert p["estado"] == "DOCUMENTACION_VALIDADA", p
    param = {k: v for k, v in (ej.get("parametros") or {}).items() if not k.startswith("_")}
    p = _accion(client, tok, p, "configure", {"basis": "Parámetros del ejercicio modelo de la herramienta.",
                                              "parametros": param}).json()
    assert p["estado"] == "PRUEBA_CONFIGURADA", p
    p = _accion(client, tok, p, "approve_methodology").json()
    p = _accion(client, tok, p, "execute", {}).json()
    assert p["estado"] == "PRUEBA_EJECUTADA", p

    # Mismo resultado que el cálculo directo con los datos tal como se leyeron del Excel.
    directo = m.ejecutar(p["registro"]["datasets"], {**param, "_marco": marco, "_edicion": edicion}, ej["corte"])
    assert p["registro"]["run"]["totals"] == directo["totals"]
    assert [x["name"] for x in p["registro"]["run"]["hojas"]] == [n for n, _ in m.CEDULAS]
    for fmt, firma in (("xlsx", b"PK"), ("docx", b"PK"), ("pptx", b"PK"), ("html", b"<!doctype html>")):
        r = client.get(f"{BASE}/pruebas/{p['id']}/libro?formato={fmt}", headers=_h(tok))
        assert r.status_code == 200 and r.content.startswith(firma), fmt
