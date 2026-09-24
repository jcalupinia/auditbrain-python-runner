"""Ejemplos de requerimiento y ejercicio modelo del Lote 2 (6 herramientas).

Los archivos de ejemplo se derivan del EJEMPLO canónico de cada procesador con
``scripts/ejemplos_lote.py`` (datos ficticios, coherentes, con resultado válido).
Este test comprueba, para cada herramienta del lote, que:

- el manifiesto del frontend y el disco están en sync (mismos archivos);
- cada .xlsx abre sin «reparar» y se lee con el MISMO lector del ciclo;
- el auto-mapeo casa TODOS los campos y el procesador corre sin romper al cargar;
- el «Ejercicio modelo» está disponible, arma 9 pasos y genera los 4 formatos.
"""
import io
import os
import re
import unicodedata

from openpyxl import load_workbook

from backend.app.aud.niif import ejercicio_modelo
from backend.app.aud.niif.ciclo import datos as ciclo_datos
from backend.app.aud.niif.procesadores import PROCESADORES

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(RAIZ, "frontend", "public", "ejemplos")
MANIFIESTO = os.path.join(RAIZ, "frontend", "src", "aud", "niif", "ejemplosRequerimientos.js")

LOTE1 = [
    "arrendamientos", "intangibles_goodwill", "activos_biologicos",
    "seguros_cobertura", "proveedores_cxp", "prestamos_obligaciones",
]


def _normal(t):
    s = unicodedata.normalize("NFD", str(t or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def _automap(headers, campos):
    cols = [_normal(c) for c in headers]
    mapa = {}
    for f in campos:
        nombres = {_normal(x) for x in [f["label"], f["key"], *f.get("aliases", [])]}
        for j, c in enumerate(cols):
            if c and c in nombres:
                mapa[f["key"]] = j
                break
    return mapa


def _esperados(pid):
    """(req, dataset, kind, campos, filas_ejemplo, nombre) por requerimiento con dataset."""
    mod = PROCESADORES[pid]
    d = mod.definicion()
    E = getattr(mod, "EJEMPLO", None)
    if E:
        datasets, par, corte = E["datasets"], E.get("parametros", {}), E["corte"]
    else:
        _, datasets, par, corte = mod.ESCENARIOS[0]
    out = []
    for r in d.get("requests", []):
        ds = r.get("dataset")
        if ds and ds in datasets:
            out.append((r, ds, mod.kind(ds), mod.CAMPOS[mod.kind(ds)], datasets[ds] or [],
                        f"{r['id']}_{ds}.xlsx"))
    return mod, d, par, corte, out


def _manifiesto_tool(pid):
    """{RQ-id: archivo} del bloque del procesador en ejemplosRequerimientos.js."""
    js = open(MANIFIESTO, encoding="utf-8").read()
    m = re.search(rf"\b{pid}:\s*\{{(.*?)\}}", js, re.S)
    assert m, f"{pid} no está en el manifiesto"
    return dict(re.findall(r'"(RQ-\d+)":\s*"([^"]+)"', m.group(1)))


def test_manifiesto_y_disco_en_sync():
    for pid in LOTE1:
        _mod, _d, _par, _corte, esperados = _esperados(pid)
        assert esperados, f"{pid}: sin requerimientos de datos"
        entradas = _manifiesto_tool(pid)
        for _r, _ds, _k, _c, _f, nombre in esperados:
            assert os.path.exists(os.path.join(PUB, pid, nombre)), f"falta {pid}/{nombre} (corra scripts/ejemplos_lote.py)"
            assert nombre in entradas.values(), f"{pid}/{nombre} no está en el manifiesto"


def test_manifiesto_cubre_todos_los_requerimientos_y_los_archivos_existen():
    # Cada requerimiento (datos y soporte) de las 6 tiene ejemplo en el manifiesto
    # y su archivo en disco: ninguno queda sin modelo descargable.
    firmas = {".pdf": b"%PDF-", ".xlsx": b"PK", ".docx": b"PK", ".csv": b""}
    for pid in LOTE1:
        d = PROCESADORES[pid].definicion()
        entradas = _manifiesto_tool(pid)
        for r in d.get("requests", []):
            assert r["id"] in entradas, f"{pid}/{r['id']} sin ejemplo en el manifiesto"
            ruta = os.path.join(PUB, pid, entradas[r["id"]])
            assert os.path.exists(ruta), f"falta el archivo {pid}/{entradas[r['id']]}"
            ext = os.path.splitext(ruta)[1]
            data = open(ruta, "rb").read()
            assert len(data) > 500, f"{pid}/{entradas[r['id']]} demasiado pequeño"
            assert data.startswith(firmas.get(ext, b"")), f"{pid}/{entradas[r['id']]}: firma {ext} inválida"


def test_cada_ejemplo_se_lee_automapea_y_corre():
    for pid in LOTE1:
        mod, _d, par, corte, esperados = _esperados(pid)
        datasets = {}
        for r, ds, kind, campos, filas_ej, nombre in esperados:
            raw = open(os.path.join(PUB, pid, nombre), "rb").read()
            load_workbook(io.BytesIO(raw))  # abre sin «reparar»
            sheets = ciclo_datos.read_spreadsheet(raw, nombre)["sheets"]
            hoja = next(s for s in sheets if s["name"] == "Datos")
            mapa = _automap(hoja["rows"][0], campos)
            faltan = [c["label"] for c in campos if c["key"] not in mapa]
            assert not faltan, f"{pid}/{nombre}: no auto-mapea {faltan}"
            filas = ciclo_datos.mapped_rows(hoja, 1, mapa, {"fields": campos}, {"id": r["id"], "name": nombre})["rows"]
            assert len(filas) == len(filas_ej), f"{pid}/{nombre}: {len(filas)} filas vs {len(filas_ej)} del ejemplo"
            datasets[ds] = filas
        run = mod.ejecutar(datasets, par, corte)  # no rompe al cargar el ejemplo
        hojas = mod.hojas(run)
        assert hojas and run.get("primary"), pid


def test_ejemplos_abren_sin_celdas_tipo_formula():
    # Ninguna celda de texto empieza con =, + o @ (Excel las tomaría por fórmula).
    for pid in LOTE1:
        _mod, _d, _par, _corte, esperados = _esperados(pid)
        for _r, _ds, _k, _c, _f, nombre in esperados:
            wb = load_workbook(os.path.join(PUB, pid, nombre))
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for c in row:
                        assert not (isinstance(c.value, str) and c.value[:1] in ("=", "+", "@")), \
                            f"{pid}/{nombre} {ws.title}!{c.coordinate}: {c.value!r}"


def test_ejercicio_modelo_disponible_9_pasos_y_4_formatos():
    for pid in LOTE1:
        mod = PROCESADORES[pid]
        d = mod.definicion()
        assert ejercicio_modelo.disponible(mod), pid
        rec = ejercicio_modelo.recorrido(d, mod)
        assert rec["disponible"] is True and rec["ficticio"] is True, pid
        assert [p["n"] for p in rec["pasos"]] == [1, 2, 3, 4, 5, 6, 7, 8, 9], pid
        for ext, firma in (("xlsx", b"PK"), ("docx", b"PK"), ("pptx", b"PK"), ("html", b"<")):
            assert ejercicio_modelo.libro_modelo(d, mod, ext).startswith(firma), (pid, ext)
