"""Reglas de DATOS del ciclo (E7) — puerto a Python de las del sitio AuditBrain.

Origen, del sitio:
- ``decimal``, ``formatted``, ``rounded``, ``valid_date``, ``validate_definition``
  (con series y flujos), ``validate_rows``, ``validate_flows``, ``control_total``,
  ``reconcile``, ``create_requests``: ``lib/tools/domain.mjs``.
- ``parse_csv``, ``read_spreadsheet``, ``mapped_rows``: ``lib/tools/files.mjs``.
- ``parse_formats``, ``requests_as_items``, ``tool_gaps``, ``tool_coverage``:
  ``lib/tools/coverage.mjs`` (sobre la cobertura ya portada en
  ``requerimiento.py``).

Vigilado por ``espejo_datos.json``, que genera el propio JavaScript del sitio
(``frontend/src/aud/niif/espejo/generarDatos.mjs``):
``tests/test_aud_ciclo_datos.py`` exige el mismo resultado caso por caso,
incluidos los mensajes de error y los libros XLSX/CSV de prueba byte a byte.

Notas de fidelidad que no son obvias:
- Los importes son enteros escalados a 1e6, como el ``BigInt`` del sitio.
- El XML se lee con ``minidom`` (no con ElementTree ni openpyxl): conserva los
  nombres con prefijo y el texto guardado por Excel, igual que
  ``fast-xml-parser``, que además recorta los espacios de cada texto.
- Una celda vacía queda como ``None`` (el hueco del arreglo en JavaScript).
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import date, timedelta
from xml.dom import minidom

from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida
from backend.app.aud.niif.requerimiento import coverage as _coverage, gaps as _gaps

SCALE = 1_000_000
MAX_ROWS = 100_000
MAX_FLOWS = 100_000
SERIES_OPS = ("add", "subtract", "multiply", "divide", "min", "max")
# RULE_OPS de domain.mjs: la aritmética más comparaciones, if, days y band.
RULE_OPS = SERIES_OPS + ("gt", "gte", "lt", "lte", "eq", "if", "days", "band")
FLOW_KEYS = ("flujos_vp", "flujos_total", "flujos_dias")
SHEETS = (
    "01_Caratula", "02_Programa", "03_Parametros", "04_Fuentes", "05_Data_Original",
    "06_Data_Procesada", "07_Calculos", "08_Pruebas", "09_Excepciones", "10_Sumaria",
    "11_Conclusion", "12_Control_Revision", "13_Cuadro",
)
FORMATS = ("xlsx", "csv", "pdf", "txt", "md", "xml", "docx", "zip", "png", "jpg", "jpeg", "webp")


def _falla(msg: str):
    raise ReglaIncumplida(msg)


def _js(v) -> str:
    """``String(v)`` de JavaScript para los valores que llegan por JSON."""
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _txt(v) -> str:
    """``String(v ?? '')``."""
    return "" if v is None else _js(v)


def _es_entero(v) -> bool:
    """``Number.isInteger`` (un booleano no lo es)."""
    if isinstance(v, bool):
        return False
    return isinstance(v, int) or (isinstance(v, float) and v.is_integer())


# --- números -----------------------------------------------------------------

_NUM = re.compile(r"-?\d{1,12}(\.\d{1,6})?")


def decimal(v) -> int:
    s = _txt(v).strip()
    if not _NUM.fullmatch(s):
        _falla("Número inválido: use punto decimal, sin separadores de miles y hasta 6 decimales.")
    if len(re.sub(r"0+$", "", re.sub(r"^0+", "", re.sub(r"[^0-9]", "", s)))) > 15:
        _falla("Máximo 15 dígitos significativos para compatibilidad con Excel.")
    neg = s.startswith("-")
    a, _, b = s.replace("-", "", 1).partition(".")
    n = int(a) * SCALE + int(b.ljust(6, "0"))
    return -n if neg else n


def rounded(n: int, d: int) -> int:
    if d == 0:
        _falla("División por cero.")
    neg = (n < 0) != (d < 0)
    n, d = abs(n), abs(d)
    return ((n + d // 2) // d) * (-1 if neg else 1)


def formatted(n: int, p: int = 2) -> str:
    v = rounded(n, 10 ** (6 - p))
    a = abs(v)
    return f"{'-' if v < 0 else ''}{a // 10 ** p}.{str(a % 10 ** p).rjust(p, '0')}"


def valid_date(v) -> bool:
    s = _txt(v) if not isinstance(v, str) else v
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    y, m, d = int(s[:4]), int(s[5:7]), int(s[8:])
    if not 1 <= m <= 12:
        return False
    bisiesto = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    dias = [31, 29 if bisiesto else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return 1 <= d <= dias


# --- definición --------------------------------------------------------------

_CLAVE = re.compile(r"[a-z][a-z0-9_]{0,35}")
_CONST = re.compile(r"#-?\d{1,12}(\.\d{1,6})?")
_PROHIBIDAS = ("constructor", "prototype", "__proto__")


def _clave_ok(obj: dict, k: str) -> bool:
    """``/^[a-z][a-z0-9_]{0,35}$/.test(x.key)``: una clave ausente se prueba como
    el texto 'undefined' (y pasa), igual que en JavaScript."""
    valor = "undefined" if k not in obj else _js(obj[k])
    return bool(_CLAVE.fullmatch(valor))


def series_order(d: dict) -> list[str]:
    o = (d.get("series") or {}).get("order") if isinstance(d.get("series"), dict) else None
    if isinstance(d.get("series"), dict) and "order" in d["series"]:
        o = d["series"]["order"]
        if not isinstance(o, list) or not o or len(o) > 2 or len(set(map(_js, o))) != len(o) or any(x not in ("backward", "forward") for x in o):
            _falla("El orden de la serie debe ser backward y forward, sin repetir.")
        return o
    return ["backward", "forward"]


def series_keys(d: dict) -> list[str]:
    s = d.get("series") or {}
    listas = {"backward": s.get("backward") or [], "forward": s.get("forward") or []}
    return [x["key"] for p in series_order(d) for x in listas[p]]


def _validar_regla_serie(x: dict, disponibles: set, vistas: set, del_pase: set) -> None:
    k = x.get("key")
    if not _clave_ok(x, "key") or k in disponibles or k in vistas or k in _PROHIBIDAS:
        _falla(f"Cálculo de serie inválido o código repetido: {_txt(k) if k is not None else 'undefined'}")
    if x.get("op") not in SERIES_OPS or x.get("precision") not in (2, 6):
        _falla(f"Operación o decimales no admitidos en la serie: {k}")
    for a in (x.get("a"), x.get("b")):
        if not isinstance(a, str):
            _falla(f"Operando inválido en la serie: {k}")
        if _CONST.fullmatch(a):
            continue
        base = a[1:] if a[:1] in ("@", "^") else a
        if not base:
            _falla(f"Operando vacío en la serie: {k}")
        if a[:1] == "@":
            if base not in del_pase:
                _falla(f"@{base} debe ser un cálculo del mismo pase de la serie.")
            continue
        if base not in disponibles and base not in vistas:
            _falla(f"Operando no disponible en la serie: {a} (en {k}).")
    if "seed" in x:
        sd = x["seed"]
        if not isinstance(sd, str) or sd[:1] in ("@", "^"):
            _falla(f"La semilla debe ser un campo, un cálculo anterior o una constante: {k}")
        if not _CONST.fullmatch(sd) and sd not in disponibles and sd not in vistas:
            _falla(f"Semilla no disponible: {sd} (en {k}).")


def _validar_serie(d: dict) -> None:
    s = d["series"]
    if not s or not isinstance(s, (dict, list)):
        _falla("La serie debe ser un objeto con períodos y cálculos.")
    s = s if isinstance(s, dict) else {}
    if not any(f.get("key") == s.get("count") and f.get("type") == "number" for f in d["fields"]):
        _falla("La serie debe declarar en `count` un campo numérico con el número de períodos.")
    backward = s["backward"] if isinstance(s.get("backward"), list) else []
    forward = s["forward"] if isinstance(s.get("forward"), list) else []
    if not backward and not forward:
        _falla("Declare al menos un cálculo en la serie.")
    if len(backward) + len(forward) > 40:
        _falla("Máximo 40 cálculos de serie.")
    disponibles = {f["key"] for f in d["fields"] if f.get("type") == "number"} | {"periodo", "periodos"}
    vistas: set = set()
    listas = {"backward": backward, "forward": forward}
    claves = {"backward": {x.get("key") for x in backward}, "forward": {x.get("key") for x in forward}}
    for pase in series_order(d):
        for x in listas[pase]:
            _validar_regla_serie(x, disponibles, vistas, claves[pase])
            vistas.add(x.get("key"))


def _validar_bloque_flujos(d: dict) -> None:
    s = d["flows"]
    if not s or not isinstance(s, (dict, list)):
        _falla("El bloque de flujos debe declarar la fecha de medición y la tasa de descuento.")
    s = s if isinstance(s, dict) else {}
    if not any(f.get("key") == s.get("date") and f.get("type") == "date" for f in d["fields"]):
        _falla("Los flujos deben declarar en `date` un campo de tipo fecha con la fecha de medición.")
    if not any(f.get("key") == s.get("rate") and f.get("type") == "number" for f in d["fields"]):
        _falla("Los flujos deben declarar en `rate` un campo numérico con la tasa de descuento.")


def validate_definition(d) -> dict:
    """Puerto de ``validateDefinition``: mismos controles y mensajes."""
    if not d or not isinstance(d, dict) or not _txt(d.get("name") or "").strip() or not _txt(d.get("area") or "").strip():
        _falla("Indique nombre y rubro de la herramienta.")
    campos, reglas_ = d.get("fields"), d.get("rules")
    if not isinstance(campos, list) or not 2 <= len(campos) <= 25 or not isinstance(reglas_, list) or not 1 <= len(reglas_) <= 25:
        _falla("Defina de 2 a 25 campos y de 1 a 25 cálculos.")
    keys: set = set()
    for x in campos:
        if not _clave_ok(x, "key") or x.get("key") in keys or x.get("key") in _PROHIBIDAS \
                or x.get("type") not in ("number", "date", "text") or not _txt(x.get("label") or "").strip():
            _falla("Campos duplicados o inválidos. Use códigos en minúsculas sin espacios.")
        keys.add(x.get("key"))
    if not any(x.get("key") == "id" and x.get("type") == "text" for x in campos):
        _falla("Incluya un campo de texto con código id para identificar cada registro.")
    numeric = {x["key"] for x in campos if x.get("type") == "number"}
    if d.get("id") == "pce":
        keys |= {"rate", "days"}
        numeric |= {"rate", "days"}
    if "series" in d:
        _validar_serie(d)
        for k in series_keys(d):
            for suf in ("_inicial", "_final", "_total"):
                if k + suf in keys:
                    _falla("Código reservado por la serie: " + k + suf)
                keys.add(k + suf)
                numeric.add(k + suf)
    if "flows" in d:
        _validar_bloque_flujos(d)
        for k in FLOW_KEYS:
            if k in keys:
                _falla("Código reservado por los flujos: " + k)
            keys.add(k)
            numeric.add(k)
    dates = {x["key"] for x in campos if x.get("type") == "date"}
    for x in reglas_:
        _validar_regla(x, keys, numeric, dates)
        keys.add(x["key"])
        numeric.add(x["key"])
    if (d.get("id") == "custom" and not any(f.get("key") == d.get("control") and f.get("type") == "number" for f in campos)) \
            or d.get("control") not in numeric or not any(x.get("key") == d.get("primary") for x in reglas_):
        _falla("Seleccione campo de conciliación y resultado principal válidos.")
    if "sheets" in d and (not isinstance(d["sheets"], list) or not d["sheets"] or any(x not in SHEETS for x in d["sheets"])):
        _falla("Las cedulas declaradas deben ser nombres de SHEETS, al menos una.")
    if "program" in d or "requests" in d:
        _validar_plan(d)
    return d


def _validar_regla(x, keys: set, numeric: set, dates: set) -> None:
    """Puerto de ``validateRule``."""
    if not isinstance(x, dict) or not _clave_ok(x, "key") or x.get("key") in keys or x.get("key") in _PROHIBIDAS \
            or x.get("op") not in RULE_OPS or x.get("precision") not in (2, 6):
        _falla("Cálculo inválido o código repetido.")
    k = _js(x.get("key")) if "key" in x else "undefined"
    if x["op"] == "days":
        for a in (x.get("a"), x.get("b")):
            if not isinstance(a, str) or not (a in dates or a == "corte"):
                _falla(f"{k}: los días se cuentan entre dos campos de fecha o la fecha de corte (corte).")
        return
    ops = [x.get("a")] if x["op"] == "band" else [x.get("a"), x.get("b"), x.get("c")] if x["op"] == "if" else [x.get("a"), x.get("b")]
    for a in ops:
        if not isinstance(a, str) or not (a in numeric or _CONST.fullmatch(a)):
            _falla("Cada operando debe ser numérico: campo, cálculo anterior o constante (#0).")
    if x["op"] == "band":
        t = x.get("table")
        if not isinstance(t, list) or not t or len(t) > 30:
            _falla(f"{k}: declare de 1 a 30 tramos con desde y valor.")
        previo = None
        for b in t:
            try:
                desde = decimal(b.get("from") if isinstance(b, dict) else None)
                decimal(b.get("value") if isinstance(b, dict) else None)
            except ReglaIncumplida:
                _falla(f"{k}: cada tramo necesita desde y valor numéricos.")
            if previo is not None and desde <= previo:
                _falla(f"{k}: los tramos van en orden creciente de desde, sin repetir.")
            previo = desde


_CODIGO_PLAN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,30}", re.ASCII)


def _validar_plan(d: dict) -> None:
    """Puerto de ``validatePlan``: programa y requerimientos propios de la ficha."""
    def texto(v):
        return isinstance(v, str) and v.strip() != ""

    prog = d.get("program")
    if not isinstance(prog, list) or not prog or len(prog) > 20:
        _falla("El programa de la ficha debe tener de 1 a 20 procedimientos.")
    codigos: set = set()
    for x in prog:
        if not isinstance(x, dict) or not _CODIGO_PLAN.fullmatch(_js(x.get("code")) if "code" in x else "undefined") \
                or x.get("code") in codigos \
                or not all(texto(x.get(c)) for c in ("objective", "risk", "assertion", "procedure", "evidence", "criterion")):
            _falla("Cada procedimiento del programa necesita código único, objetivo, riesgo, afirmación, procedimiento, evidencia y criterio.")
        codigos.add(x["code"])
    if "requests" not in d:
        return
    reqs = d["requests"]
    if not isinstance(reqs, list) or not reqs or len(reqs) > 40:
        _falla("Los requerimientos de la ficha deben ser de 1 a 40.")
    ids: set = set()
    for r in reqs:
        if not isinstance(r, dict) or not _CODIGO_PLAN.fullmatch(_js(r.get("id")) if "id" in r else "undefined") \
                or r.get("id") in ids or not texto(r.get("document")) or not texto(r.get("purpose")):
            _falla("Cada requerimiento necesita identificador único, documento y propósito.")
        ids.add(r["id"])
        if r.get("procedure") not in codigos:
            _falla(f"{_js(r['id'])}: vincule un procedimiento del programa de la ficha.")
        f = r.get("formats")
        if not isinstance(f, list) or not f or any(x not in FORMATS for x in f):
            _falla(f"{_js(r['id'])}: formatos admitidos: {', '.join(FORMATS)}.")
        if "components" in r and (not isinstance(r["components"], list) or any(not texto(c) for c in r["components"])):
            _falla(f"{_js(r['id'])}: los componentes son una lista de nombres.")
        if "use" in r and r["use"] not in ("calculo", "soporte"):
            _falla(f"{_js(r['id'])}: el uso es calculo o soporte.")


# --- filas, flujos, control y conciliación -----------------------------------

_TOTAL = re.compile(r"^(total|subtotal)(\b|\s)", re.IGNORECASE | re.ASCII)


def validate_rows(d: dict, rows) -> dict:
    validate_definition(d)
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS:
        _falla(f"Cargue entre 1 y {MAX_ROWS} registros.")
    errors, warnings, seen, ids = [], [], {}, set()
    for i, r in enumerate(rows):
        row = r.get("_row") or i + 2
        firma = json.dumps([_txt(r.get(f["key"])).strip() for f in d["fields"]], ensure_ascii=False)
        if firma in seen:
            errors.append({"row": row, "code": "DUPLICATE", "message": f"Duplicado exacto de fila {seen[firma]}. No se eliminó."})
        else:
            seen[firma] = row
        rid = _js(r["id"]) if "id" in r else "undefined"
        if rid in ids:
            warnings.append({"row": row, "code": "REPEATED_ID", "message": "Identificador repetido: compruebe lotes o partidas."})
        ids.add(rid)
        for field in d["fields"]:
            v = _txt(r.get(field["key"])).strip()
            if v == "FORMULA_SIN_VALOR_GUARDADO" or v.startswith("ERROR_EXCEL:"):
                errors.append({"row": row, "field": field["key"], "code": "CELL_ERROR", "message": "Corrija el error o recalcule y guarde el Excel de origen."})
                continue
            if not v:
                errors.append({"row": row, "field": field["key"], "code": "REQUIRED", "message": f"Falta {field['label']}."})
                continue
            if len(v) > 1000:
                errors.append({"row": row, "field": field["key"], "code": "LENGTH", "message": "Texto demasiado largo."})
                continue
            if field["type"] == "number":
                try:
                    n = decimal(v)
                    if n < 0 or (field.get("positive") and n == 0):
                        errors.append({"row": row, "field": field["key"], "code": "AMOUNT", "message": f"{field['label']}: monto incompatible con el campo."})
                except ReglaIncumplida:
                    errors.append({"row": row, "field": field["key"], "code": "NUMBER", "message": f"{field['label']}: número inválido."})
            if field["type"] == "date" and not valid_date(v):
                errors.append({"row": row, "field": field["key"], "code": "DATE", "message": f"{field['label']}: use una fecha válida AAAA-MM-DD."})
        if _TOTAL.search(rid):
            errors.append({"row": row, "code": "TOTAL_ROW", "message": "Fila de total/subtotal. Prepare un archivo de detalle y conserve el original como evidencia."})
    return {"records": len(rows), "errors": errors, "warnings": warnings, "ok": not errors}


def validate_flows(flows):
    if not isinstance(flows, list) or not flows or len(flows) > MAX_FLOWS:
        _falla(f"Cargue entre 1 y {MAX_FLOWS} flujos en el calendario de pagos.")
    for x in flows:
        x = x if isinstance(x, dict) else {}
        fid = _txt(x.get("id")).strip()
        if not fid or len(fid) > 1000:
            _falla("Cada flujo debe llevar el identificador del contrato al que pertenece.")
        if not valid_date(x.get("fecha")):
            _falla(f"Fecha de flujo inválida en {fid}: use una fecha válida AAAA-MM-DD.")
        decimal(x.get("importe"))
    return flows


def control_total(d: dict, rows: list) -> str:
    total = 0
    for r in rows:
        if d.get("id") == "vnr":
            total += decimal(formatted(rounded(decimal(r.get("quantity")) * decimal(r.get("unit_cost")), SCALE)))
        else:
            total += decimal(r.get(d.get("control")))
    return formatted(total)


def reconcile(total, ledger, tolerance, acceptance="") -> dict:
    if not re.fullmatch(r"-?\d{1,12}(\.\d{1,2})?", _js(ledger)) or not re.fullmatch(r"\d{1,12}(\.\d{1,2})?", _js(tolerance)):
        _falla("Saldo y tolerancia deben expresarse con máximo 2 decimales.")
    delta = decimal(total) - decimal(ledger)
    t = decimal(tolerance)
    if t < 0:
        _falla("La tolerancia no puede ser negativa.")
    within = abs(delta) <= t
    acc = _js(acceptance).strip()
    return {"total": total, "ledger": ledger, "tolerance": tolerance, "difference": formatted(delta),
            "resolved": within or len(acc) >= 15, "acceptance": acc, "within": within}


# --- requerimiento y cobertura -------------------------------------------------

def create_requests(program: list, cutoff: str, definition: dict | None) -> list[dict]:
    propios = (definition or {}).get("requests")
    if isinstance(propios, list) and propios:
        return [{
            "id": r["id"], "document": r["document"], "period": cutoff,
            "format": " / ".join(f.upper() for f in r["formats"]), "formats": list(r["formats"]),
            "purpose": r["purpose"], "procedure": r["procedure"], "required": r.get("required") is not False,
            "components": list(r.get("components") or []), "group": r.get("group") or "",
            "use": r.get("use") or "soporte", "report": r.get("report") or "", "timing": r.get("cutoff") or "",
            "content": r.get("content") or "", "status": "PENDIENTE",
            **({"dataset": r["dataset"]} if r.get("dataset") else {}),
        } for r in propios]
    rows = [{
        "id": f"RQ-{str(i + 1).rjust(3, '0')}", "document": p["evidence"], "period": cutoff,
        "format": "XLSX / CSV" if i == 0 else "XLSX / DOCX / CSV / XML / PDF / TXT / ZIP / imágenes",
        "purpose": p["objective"], "procedure": p["code"], "required": True, "status": "PENDIENTE",
    } for i, p in enumerate(program)]
    if (definition or {}).get("id") == "vnr" and len(rows) >= 3:
        rows[0]["document"] = f"Inventario valorado al {cutoff}"
        rows[1]["document"] = "Lista de precios de venta y evidencia de precios realizables"
        rows[2]["document"] = "Gastos de venta o estado de resultados, costos de terminación y sustento de asignación"
        rows.append({
            "id": "RQ-VNR-04", "document": "Política contable, deterioro registrado y sustento de reversos",
            "period": cutoff, "format": "XLSX / DOCX / CSV / PDF / TXT",
            "purpose": "Contrastar deterioro calculado contra el saldo registrado y evaluar reversos",
            "procedure": program[-1]["code"], "required": True, "status": "PENDIENTE",
        })
    return rows


def parse_formats(value) -> list[str]:
    crudo = _txt(value).lower()
    encontrados = [f for f in FORMATS if re.search(rf"(^|[^a-z]){f}([^a-z]|$)", crudo)]
    if re.search(r"imagen|imágenes|imagenes", crudo):
        return list(dict.fromkeys([*encontrados, "png", "jpg", "jpeg", "webp"]))
    return encontrados


def requests_as_items(requests) -> list[dict]:
    return [{
        "id": r["id"], "text": r.get("document") or r["id"],
        "formats": r["formats"] if isinstance(r.get("formats"), list) and r["formats"] else parse_formats(r.get("format")),
        "required": r.get("required") is not False,
        "components": r["components"] if isinstance(r.get("components"), list) else [],
        "group": r.get("group") or "",
    } for r in (requests or [])]


def files_as_docs(files, rejected) -> list[dict]:
    fuera = set(rejected or [])
    docs = []
    for f in files or []:
        doc = {"kind": "source", "itemId": f.get("requestId")}
        if f.get("component"):
            doc["component"] = f["component"]
        if f.get("id") in fuera:
            doc["state"] = "rechazado"
        docs.append(doc)
    return docs


def tool_gaps(requests, files, rejected) -> list[str]:
    return _gaps(requests_as_items(requests), files_as_docs(files, rejected))


def tool_coverage(requests, files, rejected) -> list[dict]:
    return _coverage(requests_as_items(requests), files_as_docs(files, rejected))


# --- lectura de hojas ----------------------------------------------------------

def parse_csv(text: str, delimiter: str | None = None) -> list[list[str]]:
    if "\0" in text:
        _falla("Archivo de texto inválido.")
    if not delimiter:
        primera = re.split(r"\r?\n", text)[0]
        delimiter = ";" if primera.count(";") > primera.count(",") else ","
    if delimiter not in (",", ";", "\t"):
        _falla("Separador inválido.")
    rows, row, value, quoted = [], [], "", False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            if quoted and i + 1 < n and text[i + 1] == '"':
                value += '"'
                i += 1
            elif quoted or value == "":
                quoted = not quoted
            else:
                value += c
        elif c == delimiter and not quoted:
            row.append(value)
            value = ""
        elif c in ("\n", "\r") and not quoted:
            if c == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
            row.append(value)
            rows.append(row)
            row, value = [], ""
        else:
            value += c
        if len(rows) > MAX_ROWS + 100 or len(row) > 150 or len(value) > 10000:
            _falla("Archivo supera los límites de filas, columnas o longitud.")
        i += 1
    if quoted:
        _falla("CSV ilegible: comillas sin cerrar.")
    if value or row:
        rows.append([*row, value])
    return rows


def _xml(datos: bytes):
    s = datos.decode("utf-8", errors="replace")
    if re.search(r"<!DOCTYPE|<!ENTITY", s, re.IGNORECASE):
        _falla("XML con entidades no permitido.")
    return minidom.parseString(datos).documentElement


def _hijos(nodo, nombre: str) -> list:
    return [c for c in nodo.childNodes if c.nodeType == c.ELEMENT_NODE and c.tagName == nombre] if nodo is not None else []


def _hijo(nodo, nombre: str):
    h = _hijos(nodo, nombre)
    return h[0] if h else None


def _texto(nodo) -> str:
    return "".join(c.data for c in nodo.childNodes if c.nodeType in (c.TEXT_NODE, c.CDATA_SECTION_NODE)).strip()


def _valor_t(nodo) -> str:
    """Texto de un ``<t>``: función ``texto`` de files.mjs. Un ``<t>`` vacío con
    atributos (como escribe el exportador del sitio) es una celda vacía; antes
    el sitio lo leía como "[object Object]" y se corrigió en los dos lados."""
    return _texto(nodo)


def _attr(nodo, nombre: str):
    return nodo.getAttribute(nombre) if nodo is not None and nodo.hasAttribute(nombre) else None


def read_spreadsheet(datos: bytes, nombre: str) -> dict:
    if len(datos) > 15 * 1024 * 1024:
        _falla("El límite por archivo es 15 MB.")
    if re.search(r"\.csv$", nombre, re.IGNORECASE):
        try:
            texto = datos.decode("utf-8")
        except UnicodeDecodeError:
            _falla("The encoded data was not valid for encoding utf-8")
        return {"sheets": [{"name": "CSV", "rows": parse_csv(re.sub(r"^﻿", "", texto))}]}
    if not re.search(r"\.xlsx$", nombre, re.IGNORECASE):
        _falla("Para datos tabulares use XLSX o CSV.")

    patron = re.compile(r"^(xl/(workbook.xml|_rels/workbook.xml.rels|sharedStrings.xml|worksheets/sheet\d+.xml))$")
    z: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(datos)) as zf:
        expandido = 0
        for info in zf.infolist():
            expandido += info.file_size
            if expandido > 60 * 1024 * 1024 or info.file_size > 30 * 1024 * 1024:
                _falla("Libro demasiado grande al descomprimir.")
            if patron.match(info.filename):
                z[info.filename] = zf.read(info.filename)
    if "xl/workbook.xml" not in z or "xl/_rels/workbook.xml.rels" not in z:
        _falla("El contenido no es un libro XLSX válido.")

    libro = _xml(z["xl/workbook.xml"])
    rels = _hijos(_xml(z["xl/_rels/workbook.xml.rels"]), "Relationship")
    compartidos: list = []
    if "xl/sharedStrings.xml" in z:
        for si in _hijos(_xml(z["xl/sharedStrings.xml"]), "si"):
            t = _hijo(si, "t")
            if t is not None:
                compartidos.append(_valor_t(t))
            else:
                partes = []
                for r in _hijos(si, "r"):
                    tr = _hijo(r, "t")
                    partes.append("" if tr is None else _valor_t(tr))
                compartidos.append("".join(partes))

    pr = _hijo(libro, "workbookPr")
    date1904 = _attr(pr, "date1904") in ("1", "true")
    hojas = []
    for s in _hijos(_hijo(libro, "sheets"), "sheet"):
        rel = next((r for r in rels if _attr(r, "Id") == _attr(s, "r:id")), None)
        ruta = _attr(rel, "Target") if rel is not None else None
        if not ruta or _attr(rel, "TargetMode") == "External":
            _falla("Referencia de hoja inválida.")
        ruta = ruta[1:] if ruta.startswith("/") else "xl/" + re.sub(r"^\./", "", ruta)
        if ruta not in z:
            _falla("No se pudo leer la hoja " + _txt(_attr(s, "name")))
        filas: dict[int, list] = {}
        for row in _hijos(_hijo(_xml(z[ruta]), "sheetData"), "row"):
            try:
                n = float(_attr(row, "r")) if _attr(row, "r") is not None else float("nan")
            except ValueError:
                n = float("nan")
            if not (n == n and n.is_integer()) or n > MAX_ROWS + 100 or n < 1:
                _falla(f"La hoja excede {MAX_ROWS} registros.")
            celdas: list = []
            for c in _hijos(row, "c"):
                letras = re.match(r"^[A-Z]+", _attr(c, "r") or "")
                if not letras:
                    _falla("Celda sin referencia.")
                col = 0
                for l in letras.group(0):
                    col = col * 26 + ord(l) - 64
                if col > 150:
                    _falla("El límite es 150 columnas.")
                v_nodo, tipo = _hijo(c, "v"), _attr(c, "t")
                v = _texto(v_nodo) if v_nodo is not None else ""
                if tipo == "s":
                    try:
                        idx = float(v) if v != "" else 0.0
                        v = compartidos[int(idx)] if idx.is_integer() and 0 <= idx < len(compartidos) else ""
                    except ValueError:
                        v = ""
                if tipo == "inlineStr":
                    is_ = _hijo(c, "is")
                    t = _hijo(is_, "t")
                    if t is not None:
                        v = _valor_t(t)
                    else:
                        partes = []
                        for r in _hijos(is_, "r"):
                            tr = _hijo(r, "t")
                            partes.append("" if tr is None else _valor_t(tr))
                        v = "".join(partes)
                if _hijo(c, "f") is not None and v_nodo is None:
                    v = "FORMULA_SIN_VALOR_GUARDADO"
                if tipo == "e":
                    v = "ERROR_EXCEL: " + str(v)
                while len(celdas) < col:
                    celdas.append(None)
                celdas[col - 1] = str(v)
            filas[int(n) - 1] = celdas
        largo = max(filas) + 1 if filas else 0
        hojas.append({"name": _attr(s, "name"), "date1904": date1904, "rows": [filas.get(i, []) for i in range(largo)]})
    if not hojas:
        _falla("Libro sin hojas.")
    return {"sheets": hojas}


def mapped_rows(sheet: dict, header, mapping: dict, definition: dict, file: dict) -> dict:
    filas = sheet["rows"]
    if not _es_entero(header) or header < 1 or header > 100 or int(header) - 1 >= len(filas):
        _falla("Fila de encabezado inválida.")
    header = int(header)
    headers = filas[header - 1]
    for f in definition["fields"]:
        col = mapping.get(f["key"])
        if not _es_entero(col) or col < 0 or col >= len(headers):
            _falla("Falta mapear " + f["label"])
    base = date(1904, 1, 1) if sheet.get("date1904") else date(1899, 12, 30)
    rows, blanks = [], 0
    for i in range(header, len(filas)):
        cells = filas[i]
        if not any(_txt(x).strip() for x in cells):
            blanks += 1
            continue
        row = {"_file": file["name"], "_fileId": file["id"], "_sheet": sheet["name"], "_row": i + 1}
        for f in definition["fields"]:
            idx = int(mapping[f["key"]])
            value = _txt(cells[idx] if idx < len(cells) else None).strip()
            if f["type"] == "date" and re.fullmatch(r"\d{5}(\.0+)?", value):
                value = (base + timedelta(days=int(float(value)))).isoformat()
            row[f["key"]] = value
        rows.append(row)
    return {"rows": rows, "blankRows": blanks, "headers": headers}


# --- E8: parámetros, excepciones, contraste y análisis ------------------------

_SIN = object()  # `undefined` de JavaScript: la clave no vino.


def check_buckets(p: dict) -> None:
    """Puerto de ``checkBuckets``: rangos de mora de la PCE del catálogo."""
    b_ = p.get("buckets") if isinstance(p, dict) else None
    if not valid_date(p.get("cutoff") if isinstance(p, dict) else None) or not isinstance(b_, list) or not b_ or len(b_) > 30:
        _falla("Defina fecha de corte y rangos con tasas aprobadas.")
    siguiente = 0
    for i, b in enumerate(b_):
        mn = b.get("min", _SIN) if isinstance(b, dict) else _SIN
        mx = b.get("max", _SIN) if isinstance(b, dict) else _SIN
        if not _es_entero(mn) or mn != siguiente \
                or (mx is not None and (not _es_entero(mx) or mx < mn)) \
                or (mx is None and i != len(b_) - 1):
            _falla("Los rangos deben cubrir desde cero, sin vacíos ni superposiciones; el último termina sin límite.")
        tasa = decimal(b.get("rate"))
        if tasa < 0 or tasa > SCALE:
            _falla("Cada tasa debe estar entre 0 y 1.")
        siguiente = float("inf") if mx is None else mx + 1
    if siguiente != float("inf"):
        _falla("El último rango debe tener límite superior vacío.")


def excepciones(d: dict, run: dict) -> list[dict]:
    """Las excepciones que ``calculate`` de domain.mjs agrega a cada fila, sobre
    el resultado del motor Python: el servidor no depende de lo que mande el
    navegador. Mismo orden: cuadro que no cierra, VNR negativo, resultado,
    posible reverso."""
    salida: list[dict] = []
    cuadro = run.get("schedule") or []
    pos = 0
    etiqueta = next((x.get("label") for x in d["rules"] if x["key"] == d["primary"]), None)
    # `values` de calculate(): campos numéricos y cálculos. Solo ahí mira el sitio.
    numericas = {f["key"] for f in d["fields"] if f.get("type") == "number"} | {x["key"] for x in d["rules"]}

    def fila(r, i, code, message, amount):
        e = {"row": r.get("_row") or i + 2}
        if "id" in r:
            e["id"] = r["id"]
        e.update(code=code, message=message, amount=amount)
        return e

    for i, r in enumerate(run["rows"]):
        if "series" in d and pos < len(cuadro):
            n = int(cuadro[pos]["periodos"])
            ultimo = cuadro[pos + n - 1]
            pos += n
            if "cierre" in ultimo and decimal(ultimo["cierre"]) != 0:
                salida.append(fila(r, i, "SERIES_NO_CIERRA",
                                   "El cuadro no cierra en cero en el último período: revise la recurrencia y la semilla.",
                                   ultimo["cierre"]))
        if d.get("id") == "vnr" and "nrv_unit" in numericas and decimal(r["nrv_unit"]) < 0:
            salida.append(fila(r, i, "NEGATIVE_NRV",
                               "VNR negativo: deterioro limitado al costo; evaluar obligaciones separadas.",
                               r.get("impairment")))
        if decimal(r[d["primary"]]) > 0:
            salida.append(fila(r, i, "RESULT", f"{_txt(etiqueta) if etiqueta is not None else 'undefined'}: requiere evaluación.",
                               r[d["primary"]]))
        if "adjustment" in numericas and decimal(r["adjustment"]) < 0:
            salida.append(fila(r, i, "REVERSAL", "Posible reversión: verificar límites y sustento antes de registrar.",
                               r["adjustment"]))
    return salida


def _distintas(x: dict, y: dict) -> list[str]:
    x, y = x or {}, y or {}
    claves = list(dict.fromkeys([*x.keys(), *y.keys()]))
    js = lambda d_, k: _js(d_[k]) if k in d_ else "undefined"
    return [k for k in claves if js(x, k) != js(y, k)]


def motivo_contraste(python: dict, navegador: dict | None) -> str:
    """El contraste del sitio, invertido: aquí manda el motor Python y el
    navegador (domain.mjs) verifica. Mismo criterio —unión de claves de filas y
    totales— más las excepciones. Nombra clave y posición, nunca importes."""
    if not isinstance(navegador, dict):
        return "no llegó el resultado del navegador"
    if navegador.get("engine") != python["engine"]:
        return f"versión del motor: Python usa {python['engine']}"
    filas_n = navegador.get("rows") if isinstance(navegador.get("rows"), list) else []
    if len(filas_n) != len(python["rows"]):
        return f"número de filas: {len(python['rows'])} en Python y {len(filas_n)} en el navegador"
    for i, (a, b) in enumerate(zip(python["rows"], filas_n)):
        k = _distintas(a, b if isinstance(b, dict) else {})
        if k:
            return f"fila {i + 1}, campos: {', '.join(k[:8])}"
    k = _distintas(python["totals"], navegador.get("totals") if isinstance(navegador.get("totals"), dict) else {})
    if k:
        return f"totales: {', '.join(k[:8])}"
    if json.dumps(python.get("exceptions"), ensure_ascii=False, sort_keys=True) != \
            json.dumps(navegador.get("exceptions"), ensure_ascii=False, sort_keys=True):
        return "excepciones"
    return ""


def preliminary(t: dict) -> str:
    """Puerto literal de ``preliminary``: la conclusión preliminar que el
    auditor debe reemplazar."""
    r, c = t["run"], t["reconciliation"]
    resultados = "; ".join(f"{k}: {_txt(v)}" for k, v in r["totals"].items())
    conc = "dentro de tolerancia" if c.get("within") else "aceptación documentada: " + _txt(c.get("acceptance"))
    return (
        "CONCLUSIÓN PRELIMINAR — PENDIENTE DE REVISIÓN DEL AUDITOR\n\n"
        f"Alcance: {len(r['rows'])} registros de {_txt(t['definition'].get('name'))}. Motor {_txt(r.get('engine'))}.\n"
        f"Resultados: {resultados}.\n"
        f"Conciliación: diferencia {_txt(c.get('difference'))}; {conc}.\n"
        f"Excepciones identificadas: {len(r['exceptions'])}.\n"
        "El auditor debe evaluar el sustento de parámetros y cada excepción antes de concluir.\n\n"
        "Conclusión del auditor: PENDIENTE."
    )
