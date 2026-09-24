"""Genera los archivos de EJEMPLO (formato válido con datos ficticios) de cada
requerimiento de datos de un grupo de herramientas NIIF, de forma data-driven.

A diferencia de ``scripts/ejemplos_perdidas_incurridas.py`` (que arma datos a la
medida de la herramienta de pérdidas incurridas), este generador es GENÉRICO:
para cada procesador toma su ejemplo canónico —``EJEMPLO`` (o ``ESCENARIOS[0]``
si no hay ``EJEMPLO``)— que el propio autor del procesador diseñó como caso de
control, y escribe un libro por cada requerimiento cuyo ``dataset`` esté en ese
ejemplo. Los datos son ficticios, coherentes entre sí y con resultado válido por
construcción (el procesador corre sobre ellos sin excepciones de carga).

Cada libro trae los datos en la hoja «Datos» con los rótulos de ``CAMPOS`` del
procesador (para que el mapeo del ciclo sea automático: ``mapeoSugerido`` casa el
encabezado con la etiqueta/alias del campo) y una hoja «Léame» con la nota
«EJEMPLO · datos ficticios» aparte, para no estorbar la lectura.

Determinista: reescribe cada zip con fechas fijas, así los archivos comiteados no
cambian entre corridas.

Uso:
    python scripts/ejemplos_lote.py                 # escribe los archivos del lote por defecto
    python scripts/ejemplos_lote.py --verificar     # round-trip (lee y corre el procesador), sin escribir
    python scripts/ejemplos_lote.py --manifiesto     # imprime el fragmento JS para ejemplosRequerimientos.js
    python scripts/ejemplos_lote.py efectivo_equivalentes cxc_cartera   # solo esos procesadores
"""
from __future__ import annotations

import os
import re
import sys
import zipfile
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.aud.niif.procesadores import PROCESADORES  # noqa: E402
from backend.app.aud.niif.ciclo import datos as datos_mod  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(RAIZ, "frontend", "public", "ejemplos")
NOTA = "EJEMPLO · datos ficticios"
FECHA_FIJA = date(2026, 1, 15)
_FIX_DT = (2026, 1, 15, 0, 0, 0)
_FIX = b"2026-01-15T00:00:00Z"

# Lote 1 (decisión del socio): 6 herramientas.
LOTE1 = [
    "efectivo_equivalentes", "cxc_cartera", "inversiones_instrumentos",
    "inventarios_costos", "ppe_propiedad_planta", "propiedades_inversion",
]


def _normalizar(path: str):
    """Reescribe el .xlsx (zip) con fechas fijas en las entradas y en core.xml,
    para que el archivo comiteado sea idéntico entre corridas."""
    with zipfile.ZipFile(path) as z:
        items = [(i.filename, i.external_attr, z.read(i.filename)) for i in z.infolist()]
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, attr, data in items:
            if nombre == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
                              rb"\g<1>" + _FIX + rb"\g<2>", data)
            zi = zipfile.ZipInfo(nombre, date_time=_FIX_DT)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = attr
            z.writestr(zi, data)
    os.replace(tmp, path)


def _iso(v):
    """'2025-12-31' → date(2025,12,31); si no es fecha ISO, None."""
    if isinstance(v, date):
        return v
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(v or "").strip())
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _celda(campo, valor):
    """Presenta el valor del EJEMPLO en el formato que un cliente escribiría:
    fechas dd/mm/aaaa; números tal cual; texto tal cual."""
    if valor is None or valor == "":
        return ""
    if campo["type"] == "date":
        d = _iso(valor)
        return d.strftime("%d/%m/%Y") if d else valor
    return valor


def _ejemplo_de(mod):
    """Devuelve (datasets, parametros, corte) del ejemplo canónico del procesador.
    PCE usa el ejemplo REALISTA compartido con pérdidas incurridas (6 clientes)."""
    if getattr(mod, "__name__", "").endswith("pce_simplificada_niif9"):
        from backend.app.aud.niif import ejemplos_pi
        e = ejemplos_pi.pce_ejemplo()
        return e["datasets"], e["parametros"], e["corte"]
    E = getattr(mod, "EJEMPLO", None)
    if E:
        return E["datasets"], E.get("parametros", {}), E["corte"]
    esc = getattr(mod, "ESCENARIOS", None)
    if esc:
        _, ds, par, corte = esc[0]
        return ds, par, corte
    raise RuntimeError(f"{mod.__name__}: sin EJEMPLO ni ESCENARIOS")


def _archivos_de(pid):
    """Lista de (req, dataset, kind, campos, filas, nombre_archivo) para el procesador."""
    mod = PROCESADORES[pid]
    d = mod.definicion()
    datasets, _par, _corte = _ejemplo_de(mod)
    salida = []
    for r in d.get("requests", []):
        ds = r.get("dataset")
        if not ds or ds not in datasets:
            continue
        kind = mod.kind(ds)
        campos = mod.CAMPOS[kind]
        filas = datasets[ds] or []
        nombre = f"{r['id']}_{ds}.xlsx"
        salida.append((r, ds, kind, campos, filas, nombre))
    return mod, d, salida


def _libro(campos, filas, titulo, explicacion):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Datos"
    ws.append([c["label"] for c in campos])
    for fila in filas:
        ws.append([_celda(c, fila.get(c["key"], "")) for c in campos])
    lee = wb.create_sheet("Léame")
    lee["A1"] = NOTA
    lee["A3"] = titulo
    lee["A5"] = explicacion
    lee["A7"] = ("Formato de ejemplo con datos ficticios que muestra la estructura esperada. "
                 "La hoja «Datos» trae los rótulos que la prueba reconoce automáticamente; "
                 "reemplace las filas por las de su empresa sin cambiar los encabezados.")
    wb.active = 0
    creado = datetime(FECHA_FIJA.year, FECHA_FIJA.month, FECHA_FIJA.day)
    wb.properties.creator = "AuditConsulting Auditores Cía. Ltda. · Ejercicio modelo"
    wb.properties.created = creado
    wb.properties.modified = creado
    return wb


def escribir(pids):
    total = 0
    for pid in pids:
        mod, d, archivos = _archivos_de(pid)
        destino = os.path.join(PUB, pid)
        os.makedirs(destino, exist_ok=True)
        for r, ds, kind, campos, filas, nombre in archivos:
            titulo = r.get("document") or f"{d['name']} — {ds}"
            explic = r.get("content") or r.get("purpose") or ""
            wb = _libro(campos, filas, titulo, explic)
            ruta = os.path.join(destino, nombre)
            wb.save(ruta)
            _normalizar(ruta)
            total += 1
        print(f"  {pid}: {len(archivos)} archivo(s) -> {os.path.relpath(destino, RAIZ)}")
    print(f"Escritos {total} archivos de ejemplo en {len(pids)} herramienta(s).")


def manifiesto(pids):
    print("  // --- Lote 1 (data-driven desde scripts/ejemplos_lote.py) ---")
    for pid in pids:
        _mod, _d, archivos = _archivos_de(pid)
        print(f"  {pid}: {{")
        for r, ds, kind, campos, filas, nombre in archivos:
            print(f'    "{r["id"]}": "{nombre}",')
        print("  },")


def _normal(t):
    import unicodedata
    s = unicodedata.normalize("NFD", str(t or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def _mapeo_sugerido(encabezados, campos):
    """Réplica en Python de cicloLogic.js::mapeoSugerido."""
    cols = [_normal(c) for c in encabezados]
    mapa = {}
    for f in campos:
        nombres = {_normal(x) for x in [f["label"], f["key"], *f.get("aliases", [])]}
        for i, c in enumerate(cols):
            if c and c in nombres:
                mapa[f["key"]] = i
                break
    return mapa


def verificar(pids) -> bool:
    """Round-trip real: lee cada xlsx generado como lo hace el sitio, reconstruye
    los datasets por auto-mapeo y corre el procesador. Falla si algún campo no
    mapea o si el procesador rompe al cargar el ejemplo."""
    ok_global = True
    for pid in pids:
        mod, d, archivos = _archivos_de(pid)
        _ds_orig, par, corte = _ejemplo_de(mod)
        destino = os.path.join(PUB, pid)
        datasets = {}
        detalle = []
        for r, ds, kind, campos, filas, nombre in archivos:
            ruta = os.path.join(destino, nombre)
            if not os.path.exists(ruta):
                print(f"  [FALTA] {pid}/{nombre} (corra sin --verificar primero)")
                ok_global = False
                continue
            with open(ruta, "rb") as fh:
                leido = datos_mod.read_spreadsheet(fh.read(), nombre)
            hoja = next(h for h in leido["sheets"] if h["name"] == "Datos")
            headers = hoja["rows"][0]
            mapa = _mapeo_sugerido(headers, campos)
            faltan = [c["label"] for c in campos if c["key"] not in mapa]
            if faltan:
                print(f"  [MAPEO] {pid}/{nombre}: no mapea {faltan}")
                ok_global = False
            definicion = {"fields": campos}
            res = datos_mod.mapped_rows(hoja, 1, mapa, definicion, {"name": nombre, "id": r["id"]})
            datasets[ds] = res["rows"]
            detalle.append(f"{ds}={len(res['rows'])}f")
        try:
            run = mod.ejecutar(datasets, par, corte)
            hojas = mod.hojas(run)
            n_exc = len(run.get("exceptions", []))
            print(f"  [OK] {pid}: {', '.join(detalle)} -> {len(hojas)} cédulas, "
                  f"primary={run.get('primary')}, {n_exc} hallazgos")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERROR] {pid}: el procesador rompió al cargar el ejemplo: {e}")
            ok_global = False
    print("RESULTADO:", "OK" if ok_global else "REVISAR")
    return ok_global


def _pids_desde_argv():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pids = args or LOTE1
    faltan = [p for p in pids if p not in PROCESADORES]
    if faltan:
        raise SystemExit(f"Procesadores desconocidos: {faltan}")
    return pids


def main():
    pids = _pids_desde_argv()
    if "--manifiesto" in sys.argv:
        manifiesto(pids)
    elif "--verificar" in sys.argv:
        sys.exit(0 if verificar(pids) else 1)
    else:
        escribir(pids)


if __name__ == "__main__":
    main()
