"""Deterioro de cuentas por cobrar por pérdidas incurridas (NIIF para las PYMES, Sección 11).

Puerto a Python de la herramienta ``AuditBrain_Prueba_Perdidas_Incurridas.html`` para el
ciclo de pruebas del Command Center. Misma metodología, mismos nombres de pasos:

1. Días de mora al corte de cada año y tramo (8 tramos; los dos últimos, graves).
2. Evidencia histórica: se empareja cada factura de un año con la del año siguiente (por
   número y, de respaldo, por cliente + fechas); la parte que sigue viva no se recuperó.
   Tasa de no recuperación por tramo = saldo que persiste ÷ saldo inicial del tramo.
3. Tasa por tramo: la observada; sin historia, 100 % en los graves con evidencia objetiva
   (saldos de más de 730 días), 0 % en el corriente (11.22: sin evento de pérdida no hay
   deterioro) y «no medible» en los demás. El auditor puede fijarla a mano.
4. Pérdida por factura (11.25): saldo − VP[saldo × (1 − tasa)] a la tasa efectiva.
5. Por cliente: tasa ponderada, evaluación individual (11.24).
6. Movimiento de la provisión por factura (11.26): inicial − reversión − bajas + año.
7. Fiscal (LRTI Art. 10 num. 11): límite anual (1 %) y acumulado (10 %).
8. Impuesto diferido por la parte no deducible.
9. Asientos propuestos.

Regla del HTML que se conserva: cero invención. Lo que no se puede medir se declara no
medible; lo que es juicio queda como parámetro editable y se identifica como tal.
"""
from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from backend.app.aud.niif.procesadores import problemas

VERSION = "pi-s11 1.0"

TRAMOS = [
    {"k": "pv", "n": "Corriente / por vencer", "min": float("-inf"), "max": 0, "grave": False},
    {"k": "t30", "n": "1 a 30 días", "min": 1, "max": 30, "grave": False},
    {"k": "t60", "n": "31 a 60 días", "min": 31, "max": 60, "grave": False},
    {"k": "t90", "n": "61 a 90 días", "min": 61, "max": 90, "grave": False},
    {"k": "t180", "n": "91 a 180 días", "min": 91, "max": 180, "grave": False},
    {"k": "t360", "n": "181 a 360 días", "min": 181, "max": 360, "grave": False},
    {"k": "t730", "n": "361 a 730 días", "min": 361, "max": 730, "grave": True},
    {"k": "tmax", "n": "Más de 730 días", "min": 731, "max": float("inf"), "grave": True},
]
NOMBRE_TRAMO = {t["k"]: t["n"] for t in TRAMOS}

# Columnas de cada anexo. `id` es el identificador de la fila (factura o año) para que
# el ciclo del portal (cobertura, mapeo, modelo) lo trate como a cualquier población.
CAMPOS = {
    "cartera": [
        {"key": "id", "label": "N° de factura", "type": "text", "required": True,
         "aliases": ["numfac", "factura", "documento", "comprobante", "numero de factura", "nro factura"]},
        {"key": "cliente", "label": "Cliente", "type": "text", "required": True,
         "aliases": ["nomcli", "razon social", "nombre del cliente", "deudor", "nombre"]},
        {"key": "emision", "label": "Fecha de emisión", "type": "date", "required": True,
         "aliases": ["emision", "fecha emision", "fecemi", "fecha", "fecha factura"]},
        {"key": "vence", "label": "Fecha de vencimiento", "type": "date", "required": True,
         "aliases": ["vence", "vencimiento", "fecha vencimiento", "fecvto"]},
        {"key": "saldo", "label": "Saldo por cobrar", "type": "number", "required": True,
         "aliases": ["saldo", "saldo pendiente", "por cobrar", "pendiente", "saldo actual"]},
        {"key": "importe", "label": "Importe original", "type": "number", "required": False,
         "aliases": ["importe", "monto factura", "valor factura", "valor original"]},
        {"key": "ruc", "label": "RUC / identificación", "type": "text", "required": False,
         "aliases": ["ruc", "cedula", "identificacion", "codigo cliente"]},
    ],
    "provision": [
        {"key": "id", "label": "N° de factura", "type": "text", "required": True,
         "aliases": ["numfac", "factura", "documento", "comprobante", "numero de factura"]},
        {"key": "cliente", "label": "Cliente", "type": "text", "required": True,
         "aliases": ["nomcli", "razon social", "nombre del cliente", "deudor", "nombre"]},
        {"key": "provision", "label": "Provisión / deterioro", "type": "number", "required": True,
         "aliases": ["provision", "deterioro", "provision inicial", "saldo provision"]},
        {"key": "diferido", "label": "Impuesto diferido", "type": "number", "required": False,
         "aliases": ["diferido", "impuesto diferido", "activo diferido"]},
    ],
    "movimiento": [
        {"key": "id", "label": "Año", "type": "text", "required": True, "aliases": ["anio", "ejercicio", "periodo"]},
        {"key": "inicial", "label": "Provisión inicial", "type": "number", "required": False,
         "aliases": ["saldo inicial", "inicial", "provision inicial"]},
        {"key": "gasto", "label": "Gasto del año", "type": "number", "required": True,
         "aliases": ["gasto", "provision del año", "cargo a resultados"]},
        {"key": "castigos", "label": "Castigos", "type": "number", "required": True,
         "aliases": ["castigos", "bajas", "castigo"]},
        {"key": "recuperaciones", "label": "Recuperaciones", "type": "number", "required": True,
         "aliases": ["recuperaciones", "recuperacion", "reversiones"]},
    ],
}

PARAMETROS = {
    "tasaDesc": 0, "plazoBase": 12, "umbralGrave": 361, "umbralIndividual": 0,
    "pctDeducible": 1, "pctLimite": 10, "tasaImp": 25,
    "provFiscalAnt": None, "dtaIniManual": None, "tasas": {},
}


# --- lectura -----------------------------------------------------------------

def norm(s) -> str:
    s = unicodedata.normalize("NFD", str(s if s is not None else "").strip().lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def a_num(v):
    """``aNum`` del HTML: acepta 1.250,00 / 1,250.00 / (150) / $ y %."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[$\s%]", "", str(v if v is not None else "").strip())
    if not s:
        return None
    neg = bool(re.fullmatch(r"\(.*\)", s))
    if neg:
        s = s[1:-1]
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if neg else n


def a_fecha(v):
    """``aFecha`` del HTML: ISO, dd/mm/aaaa o serial de Excel."""
    if isinstance(v, date):
        return v if not isinstance(v, datetime) else v.date()
    if isinstance(v, (int, float)) and 20000 < v < 60000:
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v if v is not None else "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{5}(\.0+)?", s):
        return date(1899, 12, 30) + timedelta(days=int(float(s)))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    try:
        if m:
            return date(int(m[1]), int(m[2]), int(m[3]))
        m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
        if m:
            a = int(m[3])
            return date(a + 2000 if a < 100 else a, int(m[2]), int(m[1]))
    except ValueError:
        return None
    return None


def fin_mes(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def filas_mapeadas(sheet: dict, header: int, mapping: dict, campos: list, archivo: dict) -> dict:
    """Filas de un anexo con su mapeo. Solo exige las columnas obligatorias: las
    opcionales (importe, RUC, diferido) pueden no venir."""
    filas = sheet["rows"]
    if not isinstance(header, int) or header < 1 or header - 1 >= len(filas):
        raise ValueError("Fila de encabezado inválida.")
    enc = filas[header - 1]
    for f in campos:
        col = mapping.get(f["key"])
        if f.get("required") and (not isinstance(col, int) or not 0 <= col < len(enc)):
            raise ValueError(f"{archivo['name']}: falta la columna «{f['label']}».")
    salida, vacias = [], 0
    for i in range(header, len(filas)):
        celdas = filas[i]
        if not any(str(x if x is not None else "").strip() for x in celdas):
            vacias += 1
            continue
        fila = {"_file": archivo["name"], "_fileId": archivo["id"], "_sheet": sheet["name"], "_row": i + 1}
        for f in campos:
            col = mapping.get(f["key"])
            v = celdas[col] if isinstance(col, int) and 0 <= col < len(celdas) else None
            v = str(v if v is not None else "").strip()
            if f["type"] == "date" and re.fullmatch(r"\d{5}(\.0+)?", v):
                v = (date(1904, 1, 1) if sheet.get("date1904") else date(1899, 12, 30)) + timedelta(days=int(float(v)))
                v = v.isoformat()
            fila[f["key"]] = v
        salida.append(fila)
    return {"rows": salida, "blankRows": vacias, "headers": enc}


def validar_filas(tipo: str, filas: list) -> dict:
    """Errores que impiden procesar (faltan datos obligatorios o no se leen) y avisos."""
    errores, avisos = [], []
    for f in filas:
        fila = f.get("_row")
        for c in CAMPOS[tipo]:
            v = f.get(c["key"], "")
            if c.get("required") and not str(v).strip():
                errores.append({"row": fila, "field": c["key"], "message": f"Falta {c['label']}."})
            elif str(v).strip() and c["type"] == "number" and a_num(v) is None:
                errores.append({"row": fila, "field": c["key"], "message": f"{c['label']}: número inválido."})
            elif str(v).strip() and c["type"] == "date" and a_fecha(v) is None:
                errores.append({"row": fila, "field": c["key"], "message": f"{c['label']}: fecha inválida."})
        if tipo == "cartera" and re.match(r"^(total|subtotal)\b", str(f.get("id", "")), re.I):
            errores.append({"row": fila, "message": "Fila de total o subtotal: prepare un anexo de detalle."})
    if tipo == "cartera":
        vistos = {}
        for f in filas:
            k = norm(f.get("id"))
            if k and k in vistos:
                avisos.append({"row": f.get("_row"), "message": f"Factura repetida: {f.get('id')} (también en la fila {vistos[k]})."})
            vistos.setdefault(k, f.get("_row"))
    return {"records": len(filas), "errors": errores, "warnings": avisos, "ok": not errores}


# --- cálculo -----------------------------------------------------------------

def _cartera(filas: list) -> list:
    """``construir`` del HTML para un anexo de cartera: se omiten los saldos cero."""
    out = []
    for f in filas:
        saldo = a_num(f.get("saldo"))
        if saldo is None or saldo == 0:
            continue
        out.append({"factura": str(f.get("id", "")).strip(), "cliente": str(f.get("cliente", "")).strip() or "(sin nombre)",
                    "emision": a_fecha(f.get("emision")), "vence": a_fecha(f.get("vence")), "saldo": saldo,
                    "importe": a_num(f.get("importe")), "ruc": str(f.get("ruc", "")).strip(), "_row": f.get("_row"),
                    "_origen": _origen(f)})
    return out


def _origen(f: dict) -> str:
    """Archivo · hoja · fila de donde salió el dato (trazabilidad al documento del cliente)."""
    partes = [str(f[k]) for k in ("_file", "_sheet") if f.get(k)]
    if f.get("_row") is not None:
        partes.append(f"fila {f['_row']}")
    return " · ".join(partes) or "Cargado por el auditor"


def _claves(f: dict) -> tuple[str, str, str]:
    """Claves de cruce que usan las fórmulas del libro (equivalen a ``norm`` de Python, que Excel
    no puede reproducir): factura, alterna (cliente|emisión|vencimiento) y cliente. El prefijo de
    letra impide que Excel las lea como número (un N° de factura de 15 dígitos perdería precisión)."""
    k, a = norm(f["factura"]), _clave_alt(f)
    return ("F" + k) if k else "", ("A" + a) if len(a) > 2 else "", "C" + norm(f["cliente"])


def _anexos(cart: dict, provision: list, movimiento: list) -> dict:
    """Datos del cliente que viajan dentro del libro (hojas D1–D5), con los resultados del cruce
    año contra año calculados igual que ``migracion``: las fórmulas del libro los reproducen."""
    out = {}
    siguiente = {"a1": "a2", "a2": "a3"}
    for a in ("a3", "a2", "a1"):
        y = siguiente.get(a)
        by_fac, by_alt = {}, {}
        for g in (cart.get(y) or []) if y else []:
            kf, ka, _ = _claves(g)
            if kf:
                by_fac[kf] = by_fac.get(kf, 0) + g["saldo"]
            if ka:
                by_alt[ka] = by_alt.get(ka, 0) + g["saldo"]
        filas = []
        for f in cart[a]:
            kf, ka, kc = _claves(f)
            fila = {"factura": f["factura"], "cliente": f["cliente"], "ruc": f["ruc"],
                    "emision": f["emision"].isoformat() if f["emision"] else "", "vence": f["vence"].isoformat() if f["vence"] else "",
                    "saldo": f["saldo"], "clave": kf, "claveAlt": ka, "claveCli": kc, "dias": f["dv"],
                    "tramo": NOMBRE_TRAMO.get(f["tramo"], "") if f["tramo"] else "", "origen": f["_origen"]}
            if y and cart.get(y):
                q = by_fac[kf] if kf and kf in by_fac else (by_alt[ka] if ka and ka in by_alt else None)
                fila.update({"siguiente": q, "emparejada": ("" if not f["tramo"] else ("Sí" if q is not None else "No")),
                             "viva": 0 if (not f["tramo"] or q is None) else min(q, f["saldo"])})
            filas.append(fila)
        out[a] = filas
    out["provision"] = []
    for f in provision or []:
        k = norm(f.get("id"))
        if not k:
            continue
        out["provision"].append({"factura": str(f.get("id", "")).strip(), "cliente": str(f.get("cliente", "")).strip(),
                                 "provision": a_num(f.get("provision")), "diferido": a_num(f.get("diferido")),
                                 "clave": "F" + k, "claveCli": "C" + norm(f.get("cliente")), "origen": _origen(f)})
    out["movimiento"] = sorted(({"anio": str(f.get("id", "")).strip(), "inicial": a_num(f.get("inicial")),
                                 "gasto": a_num(f.get("gasto")), "castigos": a_num(f.get("castigos")),
                                 "recuperaciones": a_num(f.get("recuperaciones")), "origen": _origen(f)}
                                for f in movimiento or []), key=lambda m: m["anio"])
    return out


def _tramo(dv):
    if dv is None:
        return None
    return next(t for t in TRAMOS if t["min"] <= dv <= t["max"])


def _clave_alt(f) -> str:
    return norm(f["cliente"]) + "|" + (f["emision"].isoformat() if f["emision"] else "") + "|" + (f["vence"].isoformat() if f["vence"] else "")


def migracion(cart: dict) -> list:
    res = []
    for x, y in (("a1", "a2"), ("a2", "a3")):
        if not cart[x] or not cart[y]:
            continue
        by_fac, by_alt = {}, {}
        for f in cart[y]:
            k = norm(f["factura"])
            if k:
                by_fac[k] = by_fac.get(k, 0) + f["saldo"]
            a = _clave_alt(f)
            if len(a) > 2:
                by_alt[a] = by_alt.get(a, 0) + f["saldo"]
        por_t, con_clave, emp_fac, emp_alt, docs = {}, 0, 0, 0, 0
        for f in cart[x]:
            if not f["tramo"]:
                continue
            docs += 1
            p = por_t.setdefault(f["tramo"], {"inicial": 0, "persiste": 0, "docs": 0, "docsPersisten": 0, "emparejados": 0})
            p["inicial"] += f["saldo"]
            p["docs"] += 1
            k = norm(f["factura"])
            if k:
                con_clave += 1
            q = None
            if k and k in by_fac:
                q = by_fac[k]
                emp_fac += 1
                p["emparejados"] += 1
            elif _clave_alt(f) in by_alt:
                q = by_alt[_clave_alt(f)]
                emp_alt += 1
                p["emparejados"] += 1
            if q is not None:
                viva = min(q, f["saldo"])
                p["persiste"] += viva
                if viva > 0.005:
                    p["docsPersisten"] += 1
        antig_y = [f for f in cart[y] if f["dv"] is not None and f["dv"] > 365]
        s_antig = sum(f["saldo"] for f in antig_y)
        emp = emp_fac + emp_alt
        cobertura = emp / docs if docs else 0
        res.append({"de": x, "a": y, "porT": por_t, "diag": {
            "docsX": docs, "conClave": con_clave, "empFac": emp_fac, "empAlt": emp_alt, "emparejadosTot": emp,
            "cobertura": cobertura, "sAntigY": s_antig, "docsAntigY": len(antig_y),
            "usable": emp > 0 and (cobertura >= 0.02 or s_antig == 0)}})
    return res


def tasas_historicas(cart: dict) -> dict:
    mig = migracion(cart)
    usables = [m for m in mig if m["diag"]["usable"]]
    if not usables:
        return {"acc": None, "ventanas": 0, "mig": mig}
    acc = {}
    for m in usables:
        for k, v in m["porT"].items():
            a = acc.setdefault(k, {"inicial": 0, "persiste": 0, "docs": 0, "docsPersisten": 0, "emparejados": 0, "obs": 0})
            for c in ("inicial", "persiste", "docs", "docsPersisten", "emparejados"):
                a[c] += v[c]
            a["obs"] += 1
    for v in acc.values():
        v["medible"] = v["emparejados"] > 0
        v["persistencia"] = v["persiste"] / v["inicial"] if v["medible"] and v["inicial"] > 0 else None
        v["recuperacion"] = None if v["persistencia"] is None else 1 - v["persistencia"]
    return {"acc": acc, "ventanas": len(usables), "mig": mig}


def derivar_tasas(cart: dict) -> dict:
    h = tasas_historicas(cart)
    viejos = [f for f in cart["a3"] if f["dv"] is not None and f["dv"] > 730]
    sev = 1 if sum(f["saldo"] for f in viejos) > 0 else None
    tasas = {}
    for t in TRAMOS:
        hh = (h["acc"] or {}).get(t["k"])
        if hh and hh["medible"] and hh["inicial"] > 0 and hh["persistencia"] is not None:
            tasas[t["k"]] = {"tasa": hh["persistencia"], "origen": "Migración observada",
                             "base": f"De {_m(hh['inicial'])} en este tramo, {_m(hh['persiste'])} seguían vivos un año después "
                                     f"({hh['docsPersisten']} de {hh['docs']} documentos; {h['ventanas']} ventana(s) anual(es))."}
        elif t["grave"] and sev is not None:
            tasas[t["k"]] = {"tasa": sev, "origen": "Evidencia objetiva del tramo",
                             "base": f"Pérdida total del remanente: {len(viejos)} documentos de más de 730 días sin evidencia "
                                     "de recuperación (Sección 11: incumplimiento sostenido)."}
        elif t["k"] == "pv":
            tasas[t["k"]] = {"tasa": 0, "origen": "Sección 11 — sin evidencia objetiva",
                             "base": "Cartera al día sin evento de pérdida: la Sección 11 no admite provisión general."}
        else:
            tasas[t["k"]] = {"tasa": None, "origen": "No medible",
                             "base": ("Ningún documento del tramo se localizó en el ejercicio siguiente: falta la medición, no el cobro."
                                      if hh and not hh["medible"] else
                                      "Sin ejercicios anteriores emparejables: cargue los anexos anteriores o fije la tasa con evidencia de gestión de cobro.")}
        tasas[t["k"]]["tasa"] = None if tasas[t["k"]]["tasa"] is None else max(0, min(tasas[t["k"]]["tasa"], 1))
    return {"tasas": tasas, "historia": h, "severidad": sev}


def _m(x) -> str:
    """Importe con formato de Ecuador: 1.635,00."""
    # Mismo redondeo que r2 (comercial), para que el texto y las cifras no difieran en 0,01.
    return f"{float(r2(x)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def r2(x) -> str:
    """Importe con dos decimales, redondeo comercial."""
    return str(Decimal(repr(float(x or 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) + 0)


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    """Corre la prueba. ``datasets``: {"a1","a2","a3": filas de cartera, "provision": filas,
    "movimiento": filas}. ``corte``: fecha de corte del ejercicio corriente (AAAA-MM-DD)."""
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte3 = a_fecha(corte)
    if corte3 is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    cart = {a: _cartera(datasets.get(a) or []) for a in ("a1", "a2", "a3")}
    if not cart["a3"]:
        raise ValueError("Cargue el anexo de cartera del ejercicio corriente.")
    cortes = {"a3": corte3}
    for a in ("a1", "a2"):
        fechas = [f["emision"] for f in cart[a] if f["emision"]]
        cortes[a] = fin_mes(max(fechas)) if fechas else None
    for a in ("a1", "a2", "a3"):
        for f in cart[a]:
            f["dv"] = (cortes[a] - f["vence"]).days if cortes[a] and f["vence"] else None
            t = _tramo(f["dv"])
            f["tramo"] = t["k"] if t else None

    der = derivar_tasas(cart)
    manual = {k: a_num(v) for k, v in (p.get("tasas") or {}).items() if a_num(v) is not None}
    tasa_de = lambda k: (manual[k] / 100 if k in manual else (der["tasas"].get(k) or {}).get("tasa")) if k else None

    i = float(p["tasaDesc"]) / 100
    plazo = float(p["plazoBase"])
    prov_ini = {}
    dta_ini = {}
    info_anexo = {}
    for f in datasets.get("provision") or []:
        k = norm(f.get("id"))
        if not k:
            continue
        pv, df = a_num(f.get("provision")), a_num(f.get("diferido"))
        if pv:
            prov_ini[k] = prov_ini.get(k, 0) + pv
        if df:
            dta_ini[k] = dta_ini.get(k, 0) + df
        if pv or df:
            info_anexo[k] = {"cliente": str(f.get("cliente", "")).strip(), "factura": str(f.get("id", "")).strip()}

    # 4 · pérdida por factura (11.25)
    facturas = []
    for idx, f in enumerate(cart["a3"]):
        t = tasa_de(f["tramo"])
        flujo = None if t is None else f["saldo"] * (1 - t)
        vp = None if flujo is None else flujo / (1 + i) ** (plazo / 12)
        perdida = None if vp is None else max(f["saldo"] - vp, 0)
        facturas.append({**f, "tasa": t, "flujo": flujo, "vp": vp, "perdida": perdida,
                         "provIni": prov_ini.get(norm(f["factura"]), 0), "_i": idx})
    facturas.sort(key=lambda f: -(f["dv"] if f["dv"] is not None else -9e9))
    perdida_total = sum(f["perdida"] or 0 for f in facturas)
    total = sum(f["saldo"] for f in cart["a3"])

    # 5 · por cliente (11.24)
    mapa = {}
    for f in cart["a3"]:
        c = mapa.setdefault(f["cliente"], {"cliente": f["cliente"], "ruc": f["ruc"], "docs": 0, "saldo": 0, "corriente": 0,
                                           "vencido": 0, "maxdv": 0, "tramos": {}})
        c["docs"] += 1
        c["saldo"] += f["saldo"]
        if f["dv"] is not None and f["dv"] <= 0:
            c["corriente"] += f["saldo"]
        else:
            c["vencido"] += f["saldo"]
        c["tramos"][f["tramo"]] = c["tramos"].get(f["tramo"], 0) + f["saldo"]
        if f["dv"] is not None and f["dv"] > c["maxdv"]:
            c["maxdv"] = f["dv"]
    clientes = []
    for c in mapa.values():
        por_mora = c["maxdv"] >= float(p["umbralGrave"])
        por_saldo = float(p["umbralIndividual"]) > 0 and c["saldo"] >= float(p["umbralIndividual"])
        pond = sum(v * tasa_de(k) for k, v in c["tramos"].items() if tasa_de(k) is not None)
        base = sum(v for k, v in c["tramos"].items() if tasa_de(k) is not None)
        tp = pond / base if base > 0 else None
        flujo = None if tp is None else c["saldo"] * (1 - tp)
        vp = None if flujo is None else flujo / (1 + i) ** (plazo / 12)
        clientes.append({**c, "individual": por_mora or por_saldo,
                         "criterio": "Antigüedad" if por_mora else ("Saldo significativo" if por_saldo else "—"),
                         "tasaPond": tp, "perdida": None if vp is None else c["saldo"] - vp})
    clientes.sort(key=lambda c: -(c["perdida"] or 0))

    # movimiento de la provisión según el mayor (control independiente)
    mov = []
    for f in datasets.get("movimiento") or []:
        mov.append({"anio": str(f.get("id", "")).strip(), "ini": a_num(f.get("inicial")), "gasto": a_num(f.get("gasto")) or 0,
                    "cast": a_num(f.get("castigos")) or 0, "rec": a_num(f.get("recuperaciones")) or 0})
    mov.sort(key=lambda m: m["anio"])
    for j, m in enumerate(mov):
        if m["ini"] is None:
            m["ini"] = mov[j - 1]["fin"] if j > 0 else 0
        m["fin"] = m["ini"] + m["gasto"] - m["cast"] + m["rec"]
    prov_ant = mov[-2]["fin"] if len(mov) > 1 else (mov[-1]["ini"] if mov else None)
    prov_reg = mov[-1]["fin"] if mov else None

    # 7 · fiscal
    corriente = sum(c["corriente"] for c in clientes)
    gasto_ej = perdida_total - (prov_ant or 0)
    lim1 = corriente * float(p["pctDeducible"]) / 100
    lim10 = total * float(p["pctLimite"]) / 100
    pf_ant = a_num(p.get("provFiscalAnt")) if p.get("provFiscalAnt") not in (None, "") else None
    pf_estimada = pf_ant is None
    if pf_ant is None:
        pf_ant = min(prov_ant or 0, lim10)
    margen = max(lim10 - pf_ant, 0)
    deducible = max(min(max(gasto_ej, 0), lim1, margen), 0)
    no_deducible = max(max(gasto_ej, 0) - deducible, 0)
    pf_acum = pf_ant + deducible
    ti = float(p["tasaImp"]) / 100
    dif_fin = max(perdida_total - pf_acum, 0)
    dif_ini = max((prov_ant or 0) - pf_ant, 0)
    dta_ini_man = a_num(p.get("dtaIniManual")) if p.get("dtaIniManual") not in (None, "") else (sum(dta_ini.values()) or None)
    dta_ini_tot = dta_ini_man if dta_ini_man is not None else dif_ini * ti
    fiscal = {"total": total, "corriente": corriente, "perdida": perdida_total, "provAnt": prov_ant, "provReg": prov_reg,
              "gastoEjercicio": gasto_ej, "limite1": lim1, "limite10": lim10, "provFiscalAnt": pf_ant,
              "pfEstimada": pf_estimada, "margenAcum": margen, "deducible": deducible, "noDeducible": no_deducible,
              "provFiscalAcum": pf_acum, "difAcumFin": dif_fin, "difAcumIni": dif_ini, "dtaFin": dif_fin * ti,
              "dtaIni": dta_ini_tot, "dtaMov": dif_fin * ti - dta_ini_tot}

    # 6 · movimiento por factura (11.26)
    en_cartera = {norm(f["factura"]) for f in cart["a3"] if norm(f["factura"])}
    cli_activos = {norm(f["cliente"]) for f in cart["a3"] if norm(f["cliente"])}
    movimiento = []
    for f in facturas:
        ini = f["provIni"]
        det = f["perdida"] or 0
        movimiento.append({"cliente": f["cliente"], "factura": f["factura"], "provIni": ini, "reversion": ini, "bajas": 0,
                           "provAnio": det, "saldoFin": det, "clave": _claves(f)[0], "claveCli": _claves(f)[2],
                           "tipo": "Con deterioro" if det > 0 else ("Reversión" if ini > 0 else "Sin movimiento")})
    claves = set(prov_ini) | set(dta_ini)
    bajas, pendientes = [], []
    for k in sorted(claves):
        if k in en_cartera:
            continue
        info = info_anexo.get(k, {"cliente": "", "factura": k})
        activo = norm(info["cliente"]) in cli_activos if info["cliente"] else False
        fila = {"k": k, "cliente": info["cliente"] or "(sin nombre en el anexo)", "factura": info["factura"],
                "prov": prov_ini.get(k, 0), "dif": dta_ini.get(k, 0), "clave": "F" + k, "claveCli": "C" + norm(info["cliente"])}
        (pendientes if activo else bajas).append(fila)
    for b in bajas:
        if b["prov"] > 0:
            movimiento.append({"cliente": b["cliente"], "factura": b["factura"], "provIni": b["prov"], "reversion": 0,
                               "bajas": b["prov"], "provAnio": 0, "saldoFin": 0, "clave": b["clave"], "claveCli": b["claveCli"],
                               "tipo": "Baja o castigo: ya no está en la cartera"})
    for q in pendientes:
        if q["prov"] > 0:
            movimiento.append({"cliente": q["cliente"], "factura": q["factura"], "provIni": q["prov"], "reversion": 0,
                               "bajas": 0, "provAnio": 0, "saldoFin": q["prov"], "clave": q["clave"], "claveCli": q["claveCli"],
                               "tipo": "Cliente activo, factura sin cruzar: pendiente de decisión del auditor"})
    tot = {k: sum(m[k] for m in movimiento) for k in ("provIni", "reversion", "bajas", "provAnio", "saldoFin")}

    # 8 · impuesto diferido por factura
    facs_dif = [f for f in facturas if (f["perdida"] or 0) > 0 or f["provIni"] > 0]
    total_det = sum(f["perdida"] or 0 for f in facs_dif)
    prop_ded = min(pf_acum, total_det) / total_det if total_det > 0 else 0
    dif_filas, t_ini, t_rev, t_new = [], 0, 0, 0
    for f in facs_dif:
        det = f["perdida"] or 0
        ded = det * prop_ded
        nod = det - ded
        d_ini = dta_ini.get(norm(f["factura"]), 0)
        d_new = nod * ti
        t_ini += d_ini
        t_rev += d_ini
        t_new += d_new
        dif_filas.append({"cliente": f["cliente"], "factura": f["factura"], "deterioro": det, "deducible": ded,
                          "noDeducible": nod, "dtaIni": d_ini, "reversion": d_ini, "dtaNuevo": d_new, "dtaFin": d_new,
                          "clave": _claves(f)[0], "claveCli": _claves(f)[2]})
    for b in bajas:
        if b["dif"] > 0:
            t_ini += b["dif"]
            t_rev += b["dif"]
            dif_filas.append({"cliente": b["cliente"], "factura": b["factura"], "deterioro": 0, "deducible": 0, "noDeducible": 0,
                              "dtaIni": b["dif"], "reversion": b["dif"], "dtaNuevo": 0, "dtaFin": 0,
                              "clave": b["clave"], "claveCli": b["claveCli"]})
    for q in pendientes:
        if q["dif"] > 0:
            t_ini += q["dif"]
            dif_filas.append({"cliente": q["cliente"], "factura": q["factura"], "deterioro": 0, "deducible": 0, "noDeducible": 0,
                              "dtaIni": q["dif"], "reversion": 0, "dtaNuevo": 0, "dtaFin": q["dif"],
                              "clave": q["clave"], "claveCli": q["claveCli"]})
    diferido = {"filas": dif_filas, "ini": t_ini, "rev": t_rev, "nuevo": t_new, "fin": t_ini - t_rev + t_new}

    # 9 · asientos
    asientos = [{"n": "1", "titulo": "Gasto por deterioro de cuentas por cobrar", "lineas": [
        {"cta": "Gasto por deterioro de cuentas incobrables", "d": tot["provAnio"]},
        {"cta": "(-) Provisión de deterioro de cuentas por cobrar", "h": tot["provAnio"]}]}]
    if tot["reversion"] > 0.005:
        asientos.append({"n": "1b", "titulo": "Reversión de la provisión del ejercicio anterior", "lineas": [
            {"cta": "(-) Provisión de deterioro de cuentas por cobrar", "d": tot["reversion"]},
            {"cta": "Ingreso por reversión de deterioro de cuentas incobrables", "h": tot["reversion"]}]})
    if tot["bajas"] > 0.005:
        asientos.append({"n": "1c", "titulo": "Baja y castigo de cartera con provisión constituida", "lineas": [
            {"cta": "(-) Provisión de deterioro de cuentas por cobrar", "d": tot["bajas"]},
            {"cta": "Cuentas por cobrar comerciales", "h": tot["bajas"]}]})
    if t_new > 0.005:
        asientos.append({"n": "2", "titulo": "Activo por impuesto diferido: reconocimiento", "lineas": [
            {"cta": "Activo por impuesto diferido", "d": t_new},
            {"cta": "Ingreso por impuesto a la renta diferido", "h": t_new}]})
    if t_rev > 0.005:
        asientos.append({"n": "3", "titulo": "Activo por impuesto diferido: reversión", "lineas": [
            {"cta": "Gasto por impuesto a la renta diferido", "d": t_rev},
            {"cta": "Activo por impuesto diferido", "h": t_rev}]})

    # problemas encontrados
    problemas = []
    for t in TRAMOS:
        info = der["tasas"][t["k"]]
        saldo_t = sum(f["saldo"] for f in cart["a3"] if f["tramo"] == t["k"])
        if info["tasa"] is None and t["k"] not in manual and saldo_t > 0:
            problemas.append({"code": "TRAMO_NO_MEDIBLE", "message": f"Tramo «{t['n']}» sin tasa medible ({_m(saldo_t)}): fije la tasa con evidencia.", "amount": r2(saldo_t)})
    for m in der["historia"]["mig"]:
        if not m["diag"]["usable"]:
            problemas.append({"code": "VENTANA_NO_USABLE", "message": f"No se pudo emparejar {m['de']}→{m['a']}: cobertura {m['diag']['cobertura']:.0%}. Revise el número de factura.", "amount": "0.00"})
    if der["historia"]["ventanas"] == 0:
        problemas.append({"code": "SIN_HISTORIA", "message": "No hay historia medible: las tasas de los tramos intermedios quedan sin medir.", "amount": "0.00"})
    for c in clientes:
        if c["individual"]:
            problemas.append({"code": "EVALUACION_INDIVIDUAL", "message": f"{c['cliente']}: {c['criterio'].lower()} (mora máxima {c['maxdv']} días); evalúe individualmente (11.24).", "amount": r2(c["perdida"] or 0)})
    for q in pendientes:
        if q["prov"] > 0:
            problemas.append({"code": "PROVISION_PENDIENTE", "message": f"Factura {q['factura']} de {q['cliente']}: provisión inicial sin cruzar con la cartera; decida reversión o baja.", "amount": r2(q["prov"])})
    if prov_reg is not None and abs(perdida_total - prov_reg) > 0.005:
        problemas.append({"code": "AJUSTE", "message": f"La pérdida recalculada ({_m(perdida_total)}) difiere de la provisión registrada según el mayor ({_m(prov_reg)}).", "amount": r2(perdida_total - prov_reg)})
    if mov and abs(tot["provIni"] - (mov[-1]["ini"] or 0)) > 0.005:
        problemas.append({"code": "CONCILIACION_INICIAL", "message": f"La provisión inicial por factura ({_m(tot['provIni'])}) no cuadra con la inicial del mayor ({_m(mov[-1]['ini'] or 0)}).", "amount": r2(tot["provIni"] - (mov[-1]["ini"] or 0))})
    if no_deducible > 0.005:
        problemas.append({"code": "NO_DEDUCIBLE", "message": f"Gasto no deducible del ejercicio: {_m(no_deducible)} (límites LRTI).", "amount": r2(no_deducible)})

    filas = [{"id": f["factura"], "cliente": f["cliente"], "emision": f["emision"].isoformat() if f["emision"] else "",
              "vence": f["vence"].isoformat() if f["vence"] else "", "dias": "" if f["dv"] is None else str(f["dv"]),
              "tramo": NOMBRE_TRAMO.get(f["tramo"], "—"), "saldo": r2(f["saldo"]),
              "tasa": "" if f["tasa"] is None else f"{f['tasa']:.6f}", "vp": "" if f["vp"] is None else r2(f["vp"]),
              "perdida": "" if f["perdida"] is None else r2(f["perdida"]), "provIni": r2(f["provIni"]), "_row": f["_row"]}
             for f in facturas]
    totales = {"saldo": r2(total), "perdida": r2(perdida_total), "provisionRegistrada": r2(prov_reg or 0),
               "ajuste": r2(perdida_total - (prov_reg or 0)), "reversion": r2(tot["reversion"]), "bajas": r2(tot["bajas"]),
               "deducible": r2(deducible), "noDeducible": r2(no_deducible), "dtaFin": r2(fiscal["dtaFin"]), "dtaMov": r2(fiscal["dtaMov"])}
    etiquetas = {"saldo": "Cartera al corte", "perdida": "Pérdida incurrida recalculada", "provisionRegistrada": "Provisión registrada (mayor)",
                 "ajuste": "Ajuste propuesto", "reversion": "Reversión de la provisión anterior", "bajas": "Bajas y castigos",
                 "deducible": "Gasto deducible", "noDeducible": "Gasto no deducible", "dtaFin": "Activo por impuesto diferido",
                 "dtaMov": "Movimiento del diferido"}
    detalle = {"cortes": {k: (v.isoformat() if v else None) for k, v in cortes.items()},
               "tasas": [{"k": t["k"], "tramo": t["n"], "tasa": tasa_de(t["k"]), "origen": "Fijada por el auditor" if t["k"] in manual else der["tasas"][t["k"]]["origen"],
                          "base": der["tasas"][t["k"]]["base"]} for t in TRAMOS],
               "migracion": der["historia"]["mig"], "clientes": clientes, "fiscal": fiscal, "movimiento": movimiento,
               "movimientoTotales": tot, "mayor": mov, "diferido": diferido, "asientos": asientos,
               "bajasAnexo": bajas, "pendientesAnexo": pendientes, "parametros": p,
               # Total del valor presente sin redondear por fila, como lo suma el Excel (SUM de la columna I).
               "vpTotal": r2(sum(f["vp"] for f in facturas if f["vp"] is not None)),
               # Datos del cliente dentro del libro (hojas D1–D5) y fila de D1 de cada factura del detalle.
               "anexos": _anexos(cart, datasets.get("provision") or [], datasets.get("movimiento") or []),
               "ordenA3": [f["_i"] for f in facturas]}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "ajuste",
            "exceptions": problemas, "schedule": [], "detalle": detalle}


# --- cédulas -------------------------------------------------------------------
# Cada cédula: {name, label, cols: [[título, formato]], rows, total}. Formatos:
# "t" texto, "n" importe, "p" porcentaje, "i" entero, "d" fecha, "x" libre.
# Una celda calculada es {"f": fórmula de Excel sin «=», "v": valor de Python}:
# el libro escribe la fórmula (editable y trazable hasta Parámetros, Detalle y
# Matriz) y la pantalla muestra el valor. Los datos van en la fila 5 en
# adelante (título, subtítulo, fila en blanco y encabezados), como en libro.py.

FILA0 = 5


def _n(x):
    return None if x is None else round(float(x), 2)


def _f(x):
    return float(x) if x not in (None, "") else None


def _fx(formula: str, valor):
    return {"f": formula, "v": valor}


CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Evidencia_historica", "Evidencia histórica"),
    ("04_Matriz_deterioro", "Matriz de deterioro"), ("05_Por_cliente", "Por cliente"),
    ("06_Movimiento_provision", "Movimiento de la provisión"), ("07_Mayor", "Provisión según el mayor"), ("08_Fiscal", "Fiscal"),
    ("09_Impuesto_diferido", "Impuesto diferido por factura"), ("10_Asientos", "Asientos propuestos"),
    ("11_Detalle", "Detalle por factura"), ("12_Problemas", "Problemas encontrados"),
    # Datos del cliente dentro del libro (D3 solo si se entregó el anexo de dos ejercicios antes).
    ("D1_Cartera_corte", "Datos del cliente · Cartera al corte (RQ-001)"),
    ("D2_Cartera_anterior", "Datos del cliente · Cartera del ejercicio anterior (RQ-002)"),
    ("D3_Cartera_2_anios_antes", "Datos del cliente · Cartera de dos ejercicios antes (RQ-003)"),
    ("D4_Provision_inicial", "Datos del cliente · Provisión inicial por factura (RQ-004)"),
    ("D5_Mayor_provision", "Datos del cliente · Libro mayor de la provisión (RQ-005)"),
]

# Referencias fijas entre cédulas (fila de cada parámetro y de cada concepto fiscal).
P = "'02_Parametros'!"
PAR = {"corte": 5, "corte2": 6, "corte1": 7, "tasaDesc": 8, "plazoBase": 9, "umbralGrave": 10, "umbralIndividual": 11,
       "pctDeducible": 12, "pctLimite": 13, "tasaImp": 14, "provFiscalAnt": 15, "dtaIniManual": 16,
       "tasaCorriente": 17, "tasaGrave": 18}
FIS = "'08_Fiscal'!"
FISC = ["total", "corriente", "perdida", "provAnt", "gastoEjercicio", "limite1", "limite10", "provFiscalAnt", "margenAcum",
        "deducible", "noDeducible", "provFiscalAcum", "difAcumFin", "dtaFin", "dtaIni", "dtaMov"]
F_ = {k: f"{FIS}$B${FILA0 + i}" for i, k in enumerate(FISC)}
DET = "'11_Detalle'!"
MAT = "'04_Matriz_deterioro'!"
EVI = "'03_Evidencia_historica'!"
MAY = "'07_Mayor'!"
MOV = "'06_Movimiento_provision'!"
DIF = "'09_Impuesto_diferido'!"
# Datos del cliente dentro del libro (una hoja por documento entregado).
D1, D2, D3, D4, D5 = ("D1_Cartera_corte", "D2_Cartera_anterior", "D3_Cartera_2_anios_antes",
                      "D4_Provision_inicial", "D5_Mayor_provision")
HOJA_CARTERA = {"a3": D1, "a2": D2, "a1": D3}
GUIA = {
    D1: ("Documento RQ-001 · anexo de cartera por factura al cierre del ejercicio (fecha de corte del encargo). En el sistema "
         "contable es el reporte de antigüedad de saldos o el auxiliar de clientes de la cuenta «Cuentas por cobrar comerciales»: "
         "una fila por factura con N°, cliente, RUC, emisión, vencimiento y saldo. Su total debe cuadrar con el mayor de esa cuenta "
         "al corte. Las facturas con saldo cero no se listan."),
    D2: ("Documento RQ-002 · el mismo reporte de antigüedad de cartera emitido al cierre del ejercicio anterior (el que se usó en "
         "esa auditoría). Con él se mide qué parte de cada tramo seguía sin cobrarse un año después."),
    D3: ("Documento RQ-003 (opcional) · el reporte de antigüedad de cartera al cierre de dos ejercicios antes: da una segunda "
         "ventana de evidencia histórica."),
    D4: ("Documento RQ-004 · detalle de la provisión por deterioro al inicio del ejercicio, factura por factura (la provisión del "
         "cierre anterior), con su impuesto diferido si se reconoció. Está en el papel de trabajo del año anterior o en el auxiliar "
         "de la cuenta «(-) Provisión cuentas incobrables»."),
    D5: ("Documento RQ-005 · libro mayor de la cuenta «(-) Provisión cuentas incobrables» de los 3 ejercicios: saldo inicial, "
         "gasto del año (débito a resultados), castigos y recuperaciones de cada año."),
}
DESC = f"(1+{P}$B${PAR['tasaDesc']}/100)^({P}$B${PAR['plazoBase']}/12)"


# Explicación humana de cada columna calculada («Cómo se calcula esta hoja»).
_CARTERA = {
    "Días de mora": ("Resta la fecha de vencimiento de la fecha de corte de este anexo (hoja 02, Parámetros): son los días que "
                     "la factura llevaba vencida a esa fecha. Cero o negativo significa que aún no vencía."),
    "Tramo": ("Clasifica la factura por sus días de mora en los mismos tramos de la matriz: corriente/por vencer, 1 a 30, 31 a "
              "60, 61 a 90, 91 a 180, 181 a 360, 361 a 730 y más de 730 días. Sin vencimiento queda en blanco."),
}
_CARTERA_ANTERIOR = {
    **_CARTERA,
    "Saldo al año siguiente": ("Busca la misma factura en el anexo del año siguiente, primero por su número y, si no la "
                               "encuentra, por cliente, emisión y vencimiento; trae el saldo que seguía pendiente. En blanco "
                               "si la factura ya no aparece (se cobró)."),
    "Emparejada": "«Sí» si la factura se encontró en el anexo del año siguiente y «No» si no; en blanco si no tiene tramo.",
    "Sigue viva": ("La parte del saldo que seguía sin cobrarse un año después: el menor entre el saldo de este año y el del año "
                   "siguiente. Es cero si la factura no se encontró."),
}

EXPLICA = {
    "cartera": _CARTERA,
    "cartera_anterior": _CARTERA_ANTERIOR,
    "02_Parametros": {
        "Valor": ("Las fechas de corte de los años anteriores se calculan como el fin del mes de la última factura emitida en "
                  "cada anexo (hojas D2 y D3). El resto de valores los fija el auditor y se pueden cambiar: el libro recalcula."),
    },
    "01_Resumen": {
        "Importe": ("Trae cada importe de la hoja donde se calculó: cartera, pérdida, gasto deducible y no deducible y "
                    "diferido de la hoja 08 (Fiscal); provisión registrada del último año de la hoja 07 (Provisión según "
                    "el mayor); reversión y bajas de los totales de la hoja 06 (Movimiento de la provisión). El ajuste "
                    "propuesto es la pérdida recalculada menos la provisión registrada."),
    },
    "03_Evidencia_historica": {
        "Documentos": "Cuenta las facturas de ese tramo en el anexo del año de partida (hoja D2 o D3).",
        "Emparejados": "Cuenta cuántas de esas facturas se encontraron en el anexo del año siguiente.",
        "Saldo inicial": "Suma el saldo de las facturas del tramo en el anexo del año de partida.",
        "Sigue vivo al año siguiente": ("Suma la parte de esas facturas que seguía sin cobrarse un año después (columna "
                                        "«Sigue viva» del anexo de partida)."),
        "Usable": ("La ventana sirve si se emparejó al menos una factura y al menos el 2 % de los documentos, o si el año "
                   "siguiente no tiene cartera de más de 365 días. Si no sirve, sus tramos no entran en la matriz."),
        "No recuperación": ("Divide el saldo del tramo que seguía sin cobrarse al año siguiente para su saldo inicial en "
                            "esa ventana: es la parte que no se recuperó. Si el saldo inicial es cero, queda en blanco."),
    },
    "04_Matriz_deterioro": {
        "Documentos": "Cuenta cuántas facturas del detalle (hoja 11, Detalle por factura) caen en este tramo de mora.",
        "Saldo": "Suma el saldo de todas las facturas del detalle (hoja 11, Detalle por factura) que caen en este tramo.",
        "Tasa aplicada": ("Si el auditor fijó la tasa del tramo, la toma de la hoja 02 (Parámetros) y la divide para 100; "
                          "si viene de la migración observada, divide el saldo que siguió vivo para el saldo inicial del "
                          "tramo, sumando solo las ventanas marcadas «Sí» como usables en la hoja 03 (Evidencia histórica). "
                          "La del tramo corriente y la de los tramos de más de 360 días sin medición (cuando hay facturas de "
                          "más de 730 días) salen de la hoja 02 (Parámetros)."),
        "Pérdida": ("Suma la pérdida calculada factura por factura en la hoja 11 (Detalle por factura) para las facturas "
                    "de este tramo."),
    },
    "05_Por_cliente": {
        "Documentos": "Cuenta cuántas facturas del cliente hay en el detalle de la hoja 11 (Detalle por factura).",
        "Saldo": "Suma el saldo de todas las facturas del cliente que figuran en la hoja 11 (Detalle por factura).",
        "Corriente": ("Suma el saldo de las facturas del cliente que al corte no están vencidas (días de mora cero o "
                      "negativos) según la hoja 11 (Detalle por factura)."),
        "Vencido": "Resta al saldo total del cliente la parte corriente: lo que queda es la cartera ya vencida del cliente.",
        "Mora máxima (días)": ("Toma los días de mora más altos entre las facturas del cliente en la hoja 11 (Detalle por "
                               "factura); nunca menos de cero."),
        "Tasa ponderada": ("Promedia las tasas de deterioro de las facturas del cliente ponderadas por su saldo (solo las que "
                           "tienen tasa). En blanco si ninguna factura del cliente tiene tasa."),
        "Pérdida": ("Aplica la tasa ponderada del cliente: al saldo le resta el valor presente de la parte que se espera "
                    "cobrar, descontada con la tasa y el plazo de la hoja 02 (Parámetros). Sin tasa ponderada, queda en blanco."),
    },
    "06_Movimiento_provision": {
        "Provisión inicial": "Trae la provisión de la factura desde el anexo de provisión inicial (hoja D4).",
        "Reversión": ("Si la factura sigue en la cartera al corte (hoja D1), su provisión inicial se revierte para volver a "
                      "medirla; si no, es cero."),
        "Bajas": ("Si ni la factura ni su cliente siguen en la cartera al corte (hoja D1), la provisión inicial se da de baja "
                  "(castigo). Si el cliente sigue activo, queda pendiente de decisión del auditor y es cero."),
        "Provisión del año": ("Trae la pérdida recalculada de esta misma factura desde la hoja 11 (Detalle por factura); "
                              "es la provisión que debería constituirse en el año."),
        "Saldo final": ("Parte de la provisión inicial, resta la reversión y las bajas del año y suma la provisión del año: "
                        "es el saldo que debería quedar en la provisión de la factura."),
    },
    "07_Mayor": {
        "Año": "Toma el año del libro mayor de la provisión entregado por el cliente (hoja D5).",
        "Inicial": "Toma el saldo inicial del mayor (hoja D5); si no viene, arrastra el saldo final del año anterior.",
        "Gasto": "Toma el gasto del año registrado en el mayor (hoja D5).",
        "Castigos": "Toma los castigos del año registrados en el mayor (hoja D5).",
        "Recuperaciones": "Toma las recuperaciones del año registradas en el mayor (hoja D5).",
        "Final": ("Parte del saldo inicial del mayor, suma el gasto del año, resta los castigos y suma las recuperaciones: "
                  "es el saldo de la provisión al cierre de ese año."),
    },
    "08_Fiscal": {
        "Importe": ("Cada concepto tiene su propio cálculo: la cartera, la parte corriente y la pérdida se suman del "
                    "detalle de la hoja 11; la provisión anterior viene de la hoja 07 (Provisión según el mayor); los "
                    "límites y el diferido aplican los porcentajes de la hoja 02 (Parámetros); el resto combina las "
                    "filas anteriores de esta hoja (gasto, margen, parte deducible y no deducible). El diferido inicial "
                    "se suma del anexo de provisión (hoja D4); si no viene, se estima sobre la provisión anterior."),
    },
    "09_Impuesto_diferido": {
        "Diferido inicial": "Trae el impuesto diferido de la factura desde el anexo de provisión inicial (hoja D4).",
        "Reversión": ("El diferido inicial se revierte, salvo que la factura ya no esté en la cartera pero su cliente siga "
                      "activo (pendiente de decisión)."),
        "Deterioro": "Trae la pérdida recalculada de esta factura desde la hoja 11 (Detalle por factura).",
        "Deducible": ("Reparte la provisión fiscal acumulada al cierre (hoja 08, Fiscal) entre las facturas en proporción a "
                      "su deterioro, sin pasar del deterioro total; si no hay deterioro, es cero."),
        "No deducible": "Resta al deterioro de la factura su parte deducible: lo que queda no se acepta como gasto fiscal.",
        "Diferido nuevo": ("Multiplica la parte no deducible por la tasa del impuesto de la hoja 02 (Parámetros): es el "
                           "activo por impuesto diferido que genera la factura."),
        "Diferido final": ("Parte del diferido inicial, resta su reversión y suma el diferido nuevo: es el activo por "
                           "impuesto diferido que queda al cierre para la factura."),
    },
    "10_Asientos": {
        "Debe": ("Toma el importe del asiento del total de su cédula: provisión del año, reversión o bajas de la hoja 06 "
                 "(Movimiento de la provisión); diferido nuevo o su reversión de la hoja 09 (Impuesto diferido por factura)."),
        "Haber": ("Lleva a la contrapartida el mismo importe del asiento, tomado del total de la hoja 06 (Movimiento de la "
                  "provisión) o de la hoja 09 (Impuesto diferido por factura), para que debe y haber cuadren."),
    },
    "11_Detalle": {
        "Factura": "Trae el número de factura de su fila del anexo de cartera al corte (hoja D1).",
        "Cliente": "Trae el cliente de su fila del anexo de cartera al corte (hoja D1).",
        "Emisión": "Trae la fecha de emisión de su fila del anexo de cartera al corte (hoja D1).",
        "Vencimiento": "Trae la fecha de vencimiento de su fila del anexo de cartera al corte (hoja D1).",
        "Saldo": "Trae el saldo de la factura de su fila del anexo de cartera al corte (hoja D1).",
        "Provisión inicial": ("Busca la factura en el anexo de provisión inicial (hoja D4) y trae su provisión; cero si no "
                              "tenía provisión."),
        "Días de mora": ("Resta la fecha de vencimiento de la fecha de corte de la hoja 02 (Parámetros); si la factura no "
                         "tiene vencimiento, queda en blanco. Cero o negativo significa que aún no vence."),
        "Tramo": ("Clasifica la factura por sus días de mora: corriente/por vencer si no tiene mora, luego 1 a 30, 31 a 60, "
                  "61 a 90, 91 a 180, 181 a 360, 361 a 730 y más de 730 días. Sin días de mora queda en blanco."),
        "Tasa": ("Busca la tasa aplicada al tramo de esta factura en la hoja 04 (Matriz de deterioro). Si la factura no "
                 "tiene tramo o el tramo no tiene tasa medible, queda en blanco."),
        "Valor presente": ("Toma la parte del saldo que se espera cobrar (saldo por uno menos la tasa) y la descuenta con "
                           "la tasa y el plazo de cobro de la hoja 02 (Parámetros). Sin tasa, queda en blanco."),
        "Pérdida": ("Resta al saldo el valor presente de lo que se espera cobrar; nunca es negativa. Si no hay valor "
                    "presente, queda en blanco."),
    },
}

# Panel del dashboard (formato en graficos.py).
PANEL = {
    "poblacion": {"rotulo": "Cartera al corte", "total": "saldo"},
    "recalculado": {"rotulo": "Pérdida recalculada", "total": "perdida"},
    "registrado": {"rotulo": "Provisión registrada", "total": "provisionRegistrada"},
    "composicion": {"rotulo": "Pérdida por tramo", "hoja": "04_Matriz_deterioro", "etiqueta": "Tramo", "valor": "Pérdida"},
    "distribucion": {"rotulo": "Cartera por tramo", "hoja": "04_Matriz_deterioro", "etiqueta": "Tramo", "valor": "Saldo"},
}


def _corte_formula(anx, a, corte_iso, n, rd):
    """Corte de un anexo anterior: fin del mes de la última emisión de su hoja de datos."""
    if not corte_iso:
        return "Sin anexo"
    if not anx or not n:
        return corte_iso
    return _fx(f"EOMONTH(MAX({rd(HOJA_CARTERA[a], 'D', n)}),0)", corte_iso)


def _tramo_formula(celda: str) -> str:
    """Tramo de mora con IF anidados, en el orden de TRAMOS."""
    f = f'"{TRAMOS[-1]["n"]}"'
    for t in reversed(TRAMOS[:-1]):
        f = f'IF({celda}<={t["max"]},"{t["n"]}",{f})'
    return f'IF({celda}="","",{f})'


def _conciliacion_inicial(hojas, e):
    """Provisión inicial por factura (TOTAL de 06) − saldo inicial del mayor del último año (07)."""
    mov = next(h for h in hojas if h["name"] == "06_Movimiento_provision")
    may = next(h for h in hojas if h["name"] == "07_Mayor")
    if not mov.get("total") or not may.get("rows"):
        return None
    formula = (f"{problemas.celda(hojas, '06_Movimiento_provision', 'Provisión inicial', len(mov['rows']))}"
               f"-{problemas.celda(hojas, '07_Mayor', 'Inicial', len(may['rows']) - 1)}")
    valor = problemas._num(mov["total"][2]) - (problemas._num(may["rows"][-1][1]) or 0)
    return formula, valor


# De qué celda sale el importe de cada problema (ver procesadores/problemas.py).
REF_PROBLEMAS = {
    "TRAMO_NO_MEDIBLE": ("04_Matriz_deterioro", "Saldo"),          # saldo del tramo sin tasa
    "EVALUACION_INDIVIDUAL": ("05_Por_cliente", "Pérdida"),        # pérdida del cliente a evaluar
    "PROVISION_PENDIENTE": ("06_Movimiento_provision", "Provisión inicial"),  # fila de la factura
    "AJUSTE": ("01_Resumen", "Importe"),                           # «Ajuste propuesto»
    "NO_DEDUCIBLE": ("08_Fiscal", "Importe"),                      # «Gasto no deducible»
    "CONCILIACION_INICIAL": _conciliacion_inicial,
}


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    f = d["fiscal"]
    p = d["parametros"]
    t = {k: float(v) for k, v in res["totals"].items()}
    filas = res["rows"]
    n_det = len(filas)
    det_fin = FILA0 + n_det - 1
    rango = lambda col: f"{DET}${col}${FILA0}:${col}${max(det_fin, FILA0)}"
    manual = {k: v for k, v in (p.get("tasas") or {}).items()}
    # Datos del cliente (hojas D1–D5). Un papel guardado antes de esta versión no los trae:
    # entonces las cédulas quedan como estaban (valores del cálculo).
    anx = d.get("anexos")
    n_anx = {a: len((anx or {}).get(a) or []) for a in ("a3", "a2", "a1", "provision", "movimiento")}

    def rd(hoja, col, n):   # rango fijo de una columna de una hoja de datos
        return f"'{hoja}'!${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"

    # 02 · Parámetros: filas fijas (PAR) y luego una por tasa fijada por el auditor.
    num = lambda k: _f(p.get(k))
    parametros = [
        ["Corte del ejercicio corriente", d["cortes"]["a3"], "Ficha del encargo"],
        ["Corte del ejercicio anterior", _corte_formula(anx, "a2", d["cortes"]["a2"], n_anx["a2"], rd),
         "Fin del mes de la última emisión del anexo (hoja D2)"],
        ["Corte de dos ejercicios antes", _corte_formula(anx, "a1", d["cortes"]["a1"], n_anx["a1"], rd),
         "Fin del mes de la última emisión del anexo (hoja D3)"],
        ["Tasa efectiva para descontar (%)", num("tasaDesc"), "Secc. 11 párr. 11.13 y 11.25"],
        ["Plazo esperado de cobro (meses)", num("plazoBase"), "Juicio del auditor"],
        ["Umbral de mora grave (días)", num("umbralGrave"), "Secc. 11 párr. 11.24"],
        ["Umbral de saldo significativo", num("umbralIndividual"), "Secc. 11 párr. 11.24 (0 = desactivado)"],
        ["Límite anual deducible (%)", num("pctDeducible"), "LRTI Art. 10 num. 11"],
        ["Límite acumulado (%)", num("pctLimite"), "LRTI Art. 10 num. 11"],
        ["Tasa del impuesto (%)", num("tasaImp"), "Tarifa del contribuyente"],
        ["Provisión fiscal acumulada anterior", num("provFiscalAnt"), "En blanco: mínimo entre la provisión anterior y el límite acumulado"],
        ["Activo por impuesto diferido inicial", num("dtaIniManual"), "En blanco: el del anexo de provisión inicial"],
        ["Tasa del tramo corriente / por vencer (%)", 0, "Secc. 11: sin evento de pérdida no hay provisión"],
        ["Tasa de los tramos de más de 360 días sin medición (%)", 100,
         "Secc. 11: incumplimiento sostenido, si hay facturas de más de 730 días"],
    ]
    fila_tasa = {}
    for k, v in manual.items():
        fila_tasa[k] = FILA0 + len(parametros)
        parametros.append([f"Tasa fijada por el auditor · {NOMBRE_TRAMO.get(k, k)} (%)", _f(v), "Juicio del auditor con evidencia de cobro"])

    # 03 · Evidencia histórica: una fila por ventana y tramo; «Usable» decide si entra.
    evidencia = []
    for m in d["migracion"]:
        x_h, y_h = HOJA_CARTERA[m["de"]], HOJA_CARTERA[m["a"]]
        nx, ny = n_anx[m["de"]], n_anx[m["a"]]
        anio = lambda a: (d["cortes"].get(a) or "")[:4] or a
        for k, v in m["porT"].items():
            r = FILA0 + len(evidencia)
            usable = "Sí" if m["diag"]["usable"] else "No"
            if anx:
                xk, xm = rd(x_h, "K", nx), rd(x_h, "M", nx)
                fila = [_fx(f"COUNTIF({xk},B{r})", v["docs"]), _fx(f'COUNTIFS({xk},B{r},{xm},"Sí")', v["emparejados"]),
                        _fx(f"SUMIF({xk},B{r},{rd(x_h, 'F', nx)})", _n(v["inicial"])),
                        _fx(f"SUMIF({xk},B{r},{rd(x_h, 'N', nx)})", _n(v["persiste"]))]
                usable = _fx(f'IF(AND(COUNTIF({xm},"Sí")>0,OR(COUNTIF({xm},"Sí")/COUNTIF({xk},"?*")>=0.02,'
                             f'SUMIF({rd(y_h, "J", ny)},">365",{rd(y_h, "F", ny)})=0)),"Sí","No")', usable)
            else:
                fila = [v["docs"], v["emparejados"], _n(v["inicial"]), _n(v["persiste"])]
            evidencia.append([f"{anio(m['de'])} → {anio(m['a'])}", NOMBRE_TRAMO[k], *fila,
                              _fx(f'IF(E{r}=0,"",F{r}/E{r})', (v["persiste"] / v["inicial"]) if v["inicial"] else None),
                              usable])

    # 04 · Matriz: la tasa observada sale de la evidencia; la fijada, de Parámetros.
    saldo_t, perd_t, docs_t = {}, {}, {}
    for r in filas:
        saldo_t[r["tramo"]] = saldo_t.get(r["tramo"], 0) + float(r["saldo"])
        perd_t[r["tramo"]] = perd_t.get(r["tramo"], 0) + (_f(r["perdida"]) or 0)
        docs_t[r["tramo"]] = docs_t.get(r["tramo"], 0) + 1
    matriz = []
    for x in d["tasas"]:
        r = FILA0 + len(matriz)
        if x["k"] in manual:
            tasa = _fx(f"{P}$B${fila_tasa[x['k']]}/100", x["tasa"])
        elif x["origen"] == "Migración observada":
            tasa = _fx(f'SUMIFS({EVI}$F:$F,{EVI}$B:$B,A{r},{EVI}$H:$H,"Sí")/SUMIFS({EVI}$E:$E,{EVI}$B:$B,A{r},{EVI}$H:$H,"Sí")', x["tasa"])
        elif x["origen"].startswith("Sección 11"):
            tasa = _fx(f"{P}$B${PAR['tasaCorriente']}/100", x["tasa"])
        elif x["origen"] == "Evidencia objetiva del tramo":
            tasa = _fx(f'IF(SUMIF({rango("E")},">730",{rango("G")})>0,{P}$B${PAR["tasaGrave"]}/100,"")', x["tasa"])
        else:
            tasa = x["tasa"]
        matriz.append([x["tramo"], _fx(f"COUNTIF({rango('F')},A{r})", docs_t.get(x["tramo"], 0)),
                       _fx(f"SUMIF({rango('F')},A{r},{rango('G')})", _n(saldo_t.get(x["tramo"], 0))), tasa, x["origen"],
                       _fx(f"SUMIF({rango('F')},A{r},{rango('J')})", _n(perd_t.get(x["tramo"], 0))), x["base"]])
    m_fin = FILA0 + len(matriz) - 1
    tot_mat = FILA0 + len(matriz)
    tasa_mat = f"INDEX({MAT}$D${FILA0}:$D${m_fin},MATCH(F{{r}},{MAT}$A${FILA0}:$A${m_fin},0))"

    # 11 · Detalle por factura: días, tramo, tasa, valor presente y pérdida con fórmulas.
    detalle = []
    orden = d.get("ordenA3") if anx else None
    for i, x in enumerate(filas):
        r = FILA0 + i
        tm = tasa_mat.format(r=r)
        if orden:
            # Cada factura remite a su fila del anexo del cliente (hoja D1) y a la provisión inicial (hoja D4).
            src = FILA0 + orden[i]
            ref = lambda col: f"'{D1}'!{col}{src}"  # noqa: E731
            ident = [_fx(ref("A"), x["id"]), _fx(ref("B"), x["cliente"]), _fx(ref("D"), x["emision"]), _fx(ref("E"), x["vence"])]
            saldo = _fx(ref("F"), _n(x["saldo"]))
            prov = _fx(f"SUMIF({rd(D4, 'E', n_anx['provision'])},{ref('G')},{rd(D4, 'C', n_anx['provision'])})", _n(x["provIni"]))
        else:
            ident, saldo, prov = [x["id"], x["cliente"], x["emision"], x["vence"]], _n(x["saldo"]), _n(x["provIni"])
        detalle.append([
            *ident,
            _fx(f'IF(D{r}="","",{P}$B${PAR["corte"]}-D{r})', int(x["dias"]) if x["dias"] else None),
            _fx(_tramo_formula(f"E{r}"), x["tramo"]), saldo,
            _fx(f'IF(F{r}="","",IF({tm}="","",{tm}))', _f(x["tasa"])),
            _fx(f'IF(H{r}="","",G{r}*(1-H{r})/{DESC})', _n(_f(x["vp"]))),
            _fx(f'IF(I{r}="","",MAX(G{r}-I{r},0))', _n(_f(x["perdida"]))), prov,
        ])
    tot_det = FILA0 + n_det
    s = lambda col, fin, v: _fx(f"SUM({col}{FILA0}:{col}{fin})", v)

    # 07 · Mayor: saldo final = inicial + gasto − castigos + recuperaciones.
    mayor = []
    for j, m in enumerate(d["mayor"]):
        r = FILA0 + j
        if anx and n_anx["movimiento"] == len(d["mayor"]):
            # Del libro mayor del cliente (hoja D5); sin saldo inicial, arrastra el final del año anterior.
            q5 = f"'{D5}'!"
            previo = f"F{r - 1}" if j else "0"
            vals = [_fx(f"{q5}A{r}", m["anio"]), _fx(f'IF({q5}B{r}="",{previo},{q5}B{r})', _n(m["ini"])),
                    _fx(f"N({q5}C{r})", _n(m["gasto"])), _fx(f"N({q5}D{r})", _n(m["cast"])), _fx(f"N({q5}E{r})", _n(m["rec"]))]
        else:
            vals = [m["anio"], _n(m["ini"]), _n(m["gasto"]), _n(m["cast"]), _n(m["rec"])]
        mayor.append([*vals, _fx(f"B{r}+C{r}-D{r}+E{r}", _n(m["fin"]))])
    nm = len(mayor)
    prov_ant_ref = f"{MAY}F{FILA0 + nm - 2}" if nm > 1 else (f"{MAY}B{FILA0}" if nm == 1 else "0")
    prov_reg_ref = f"{MAY}F{FILA0 + nm - 1}" if nm else "0"

    # 06 · Movimiento: la provisión del año es la pérdida del Detalle por factura.
    movs = [m for m in d["movimiento"] if m["provIni"] or m["provAnio"]]
    movimiento = []
    for j, m in enumerate(movs):
        r = FILA0 + j
        if anx and "clave" in m:
            # Provisión inicial del anexo (D4); reversión si la factura sigue en la cartera (D1); baja si
            # ni la factura ni el cliente siguen en la cartera; si el cliente sigue activo, queda pendiente.
            d4e, d1g, d1i = rd(D4, "E", n_anx["provision"]), rd(D1, "G", n_anx["a3"]), rd(D1, "I", n_anx["a3"])
            cl, cc = m["clave"], m["claveCli"]
            ini_rev_baja = [_fx(f'SUMIF({d4e},"{cl}",{rd(D4, "C", n_anx["provision"])})', _n(m["provIni"])),
                            _fx(f'IF(COUNTIF({d1g},"{cl}")>0,C{r},0)', _n(m["reversion"])),
                            _fx(f'IF(AND(COUNTIF({d1g},"{cl}")=0,COUNTIF({d1i},"{cc}")=0),C{r},0)', _n(m["bajas"]))]
        else:
            ini_rev_baja = [_n(m["provIni"]), _n(m["reversion"]), _n(m["bajas"])]
        movimiento.append([m["cliente"], m["factura"], *ini_rev_baja,
                           _fx(f"SUMIF({rango('A')},B{r},{rango('J')})", _n(m["provAnio"])),
                           _fx(f"C{r}-D{r}-E{r}+F{r}", _n(m["saldoFin"])), m["tipo"]])
    fin_mov = FILA0 + len(movimiento) - 1
    tot_mov = FILA0 + len(movimiento)
    mt = d["movimientoTotales"]

    # 08 · Fiscal (el orden es FISC).
    pf_ant = f"{P}B{PAR['provFiscalAnt']}" if not f["pfEstimada"] else f"MIN({F_['provAnt']},{F_['limite10']})"
    dta_ini = f"{P}B{PAR['dtaIniManual']}" if p.get("dtaIniManual") not in (None, "") else None
    fiscal = [
        ["Cartera total al corte", _fx(f"SUM({rango('G')})", _n(f["total"]))],
        ["Cartera corriente (créditos del ejercicio)", _fx(f'SUMIF({rango("E")},"<=0",{rango("G")})', _n(f["corriente"]))],
        ["Pérdida incurrida recalculada", _fx(f"SUM({rango('J')})", _n(f["perdida"]))],
        ["Provisión del ejercicio anterior (mayor)", _fx(prov_ant_ref, _n(f["provAnt"] or 0))],
        ["Gasto del ejercicio", _fx(f"{F_['perdida']}-{F_['provAnt']}", _n(f["gastoEjercicio"]))],
        ["Límite anual (% sobre la cartera corriente)", _fx(f"{F_['corriente']}*{P}$B${PAR['pctDeducible']}/100", _n(f["limite1"]))],
        ["Límite acumulado (% sobre la cartera total)", _fx(f"{F_['total']}*{P}$B${PAR['pctLimite']}/100", _n(f["limite10"]))],
        ["Provisión fiscal acumulada anterior" + (" (estimada)" if f["pfEstimada"] else ""), _fx(pf_ant, _n(f["provFiscalAnt"]))],
        ["Margen acumulado disponible", _fx(f"MAX({F_['limite10']}-{F_['provFiscalAnt']},0)", _n(f["margenAcum"]))],
        ["Gasto deducible", _fx(f"MAX(MIN(MAX({F_['gastoEjercicio']},0),{F_['limite1']},{F_['margenAcum']}),0)", _n(f["deducible"]))],
        ["Gasto no deducible", _fx(f"MAX(MAX({F_['gastoEjercicio']},0)-{F_['deducible']},0)", _n(f["noDeducible"]))],
        ["Provisión fiscal acumulada al cierre", _fx(f"{F_['provFiscalAnt']}+{F_['deducible']}", _n(f["provFiscalAcum"]))],
        ["Diferencia temporaria acumulada al cierre", _fx(f"MAX({F_['perdida']}-{F_['provFiscalAcum']},0)", _n(f["difAcumFin"]))],
        ["Activo por impuesto diferido al cierre", _fx(f"{F_['difAcumFin']}*{P}$B${PAR['tasaImp']}/100", _n(f["dtaFin"]))],
        ["Activo por impuesto diferido inicial" + ("" if dta_ini else " (anexo de provisión)"),
         _fx(dta_ini, _n(f["dtaIni"])) if dta_ini else (
             _fx(f"IF(SUM({rd(D4, 'D', n_anx['provision'])})<>0,SUM({rd(D4, 'D', n_anx['provision'])}),"
                 f"MAX({F_['provAnt']}-{F_['provFiscalAnt']},0)*{P}$B${PAR['tasaImp']}/100)", _n(f["dtaIni"]))
             if anx else _n(f["dtaIni"]))],
        ["Movimiento del diferido", _fx(f"{F_['dtaFin']}-{F_['dtaIni']}", _n(f["dtaMov"]))],
    ]

    # 09 · Diferido: la parte deducible se reparte en proporción al deterioro.
    dif_f = d["diferido"]["filas"]
    tot_dif = FILA0 + len(dif_f)
    fin_dif = tot_dif - 1
    diferido = []
    for j, x in enumerate(dif_f):
        r = FILA0 + j
        if anx and "clave" in x:
            # Diferido inicial del anexo (D4); se revierte salvo que la factura esté pendiente (cliente activo).
            d1g, d1i = rd(D1, "G", n_anx["a3"]), rd(D1, "I", n_anx["a3"])
            cl, cc = x["clave"], x["claveCli"]
            ini_rev = [_fx(f'SUMIF({rd(D4, "E", n_anx["provision"])},"{cl}",{rd(D4, "D", n_anx["provision"])})', _n(x["dtaIni"])),
                       _fx(f'IF(AND(COUNTIF({d1g},"{cl}")=0,COUNTIF({d1i},"{cc}")>0),0,F{r})', _n(x["reversion"]))]
        else:
            ini_rev = [_n(x["dtaIni"]), _n(x["reversion"])]
        diferido.append([x["cliente"], x["factura"],
                         _fx(f"SUMIF({rango('A')},B{r},{rango('J')})", _n(x["deterioro"])),
                         _fx(f"IF($C${tot_dif}=0,0,C{r}*MIN({F_['provFiscalAcum']},$C${tot_dif})/$C${tot_dif})", _n(x["deducible"])),
                         _fx(f"C{r}-D{r}", _n(x["noDeducible"])), *ini_rev,
                         _fx(f"E{r}*{P}$B${PAR['tasaImp']}/100", _n(x["dtaNuevo"])), _fx(f"F{r}-G{r}+H{r}", _n(x["dtaFin"]))])
    dt = d["diferido"]
    tot_det_dif = sum(x["deterioro"] for x in dif_f)

    # 10 · Asientos: cada importe apunta al total de su cédula.
    ref_asiento = {"1": (f"{MOV}F{tot_mov}", mt["provAnio"]), "1b": (f"{MOV}D{tot_mov}", mt["reversion"]),
                   "1c": (f"{MOV}E{tot_mov}", mt["bajas"]), "2": (f"{DIF}H{tot_dif}", dt["nuevo"]), "3": (f"{DIF}G{tot_dif}", dt["rev"])}
    asientos = []
    for a in d["asientos"]:
        ref, v = ref_asiento[a["n"]]
        for i, l in enumerate(a["lineas"]):
            celda = _fx(ref, _n(v))
            asientos.append([f"{a['n']} · {a['titulo']}" if i == 0 else "", l["cta"],
                             celda if l.get("d") is not None else None, celda if l.get("h") is not None else None])

    # 05 · Por cliente.
    clientes = []
    for j, c in enumerate(d["clientes"]):
        r = FILA0 + j
        clientes.append([c["cliente"], c["ruc"], _fx(f"COUNTIF({rango('B')},A{r})", c["docs"]),
                         _fx(f"SUMIF({rango('B')},A{r},{rango('G')})", _n(c["saldo"])),
                         _fx(f'SUMIFS({rango("G")},{rango("B")},A{r},{rango("E")},"<=0")', _n(c["corriente"])),
                         _fx(f"D{r}-E{r}", _n(c["vencido"])),
                         _fx(f"MAX(0,_xlfn.MAXIFS({rango('E')},{rango('B')},A{r}))", c["maxdv"]),
                         _fx(f"IF(SUMPRODUCT(--({rango('B')}=A{r}),--ISNUMBER({rango('H')}),{rango('G')})>0,"
                             f"SUMPRODUCT(--({rango('B')}=A{r}),{rango('G')},{rango('H')})/"
                             f"SUMPRODUCT(--({rango('B')}=A{r}),--ISNUMBER({rango('H')}),{rango('G')}),\"\")", c["tasaPond"]),
                         _fx(f'IF(H{r}="","",D{r}*(1-(1-H{r})/{DESC}))', _n(c["perdida"])),
                         c["criterio"] if c["individual"] else "Colectiva"])
    tot_cli = FILA0 + len(clientes)
    fin_cli = tot_cli - 1

    # 01 · Resumen (orden de res["labels"]).
    fila_res = {k: FILA0 + i for i, k in enumerate(res["labels"])}
    ref_res = {"saldo": F_["total"], "perdida": F_["perdida"], "provisionRegistrada": prov_reg_ref,
               "ajuste": f"B{fila_res['perdida']}-B{fila_res['provisionRegistrada']}",
               "reversion": f"{MOV}D{tot_mov}", "bajas": f"{MOV}E{tot_mov}", "deducible": F_["deducible"],
               "noDeducible": F_["noDeducible"], "dtaFin": F_["dtaFin"], "dtaMov": F_["dtaMov"]}
    resumen = [[res["labels"][k], _fx(ref_res[k], _n(t[k]))] for k in res["labels"]]

    hoja = lambda name, label, cols, rows, total=None, explica=None, guia=None, ocultas=None: {  # noqa: E731
        "name": name, "label": label, "cols": cols, "rows": rows, "total": total, "explica": dict(explica or {}),
        **({"guia": guia} if guia else {}), **({"ocultas": ocultas} if ocultas else {})}
    claves = ["Clave de cruce", "Clave alterna", "Clave del cliente"]   # técnicas: agrupadas y ocultas en el Excel

    # D1–D5 · Datos del cliente: lo que entregó, fila por fila, con el archivo de origen.
    datos = []
    if anx:
        siguiente = {"a2": "a3", "a1": "a2"}
        corte_ref = {"a3": f"{P}$B${PAR['corte']}", "a2": f"{P}$B${PAR['corte2']}", "a1": f"{P}$B${PAR['corte1']}"}
        rotulo = {"a3": "Cartera al corte (RQ-001)", "a2": "Cartera del ejercicio anterior (RQ-002)",
                  "a1": "Cartera de dos ejercicios antes (RQ-003)"}
        for a in ("a3", "a2", "a1"):
            fa, y = anx[a], siguiente.get(a)
            if not fa:
                continue
            con_y = bool(y and n_anx[y] and any("siguiente" in f for f in fa))
            filas_d = []
            for i, fd in enumerate(fa):
                r = FILA0 + i
                cr = corte_ref[a]
                fila = [fd["factura"], fd["cliente"], fd["ruc"], fd["emision"], fd["vence"], fd["saldo"],
                        fd["clave"], fd["claveAlt"], fd["claveCli"],
                        _fx(f'IF(OR(E{r}="",NOT(ISNUMBER({cr}))),"",{cr}-E{r})', fd["dias"]),
                        _fx(_tramo_formula(f"J{r}"), fd["tramo"])]
                if con_y:
                    yh, ny = HOJA_CARTERA[y], n_anx[y]
                    yg, ya, yf = rd(yh, "G", ny), rd(yh, "H", ny), rd(yh, "F", ny)
                    fila += [_fx(f'IF(AND(G{r}<>"",COUNTIF({yg},G{r})>0),SUMIF({yg},G{r},{yf}),'
                                 f'IF(AND(H{r}<>"",COUNTIF({ya},H{r})>0),SUMIF({ya},H{r},{yf}),""))',
                                 _n(fd["siguiente"]) if fd["siguiente"] is not None else ""),
                             _fx(f'IF(K{r}="","",IF(L{r}="","No","Sí"))', fd["emparejada"]),
                             _fx(f'IF(OR(K{r}="",L{r}=""),0,MIN(L{r},F{r}))', _n(fd["viva"]))]
                filas_d.append(fila + [fd["origen"]])
            fin = FILA0 + len(filas_d) - 1
            cols = [["Factura", "t"], ["Cliente", "t"], ["RUC", "t"], ["Emisión", "d"], ["Vencimiento", "d"], ["Saldo", "n"],
                    ["Clave de cruce", "t"], ["Clave alterna", "t"], ["Clave del cliente", "t"], ["Días de mora", "i"], ["Tramo", "t"]]
            total = ["TOTAL", "", "", "", "", s("F", fin, _n(sum(fd["saldo"] for fd in fa))), "", "", "", None, ""]
            if con_y:
                cols += [["Saldo al año siguiente", "n"], ["Emparejada", "t"], ["Sigue viva", "n"]]
                total += [None, "", s("N", fin, _n(sum(fd["viva"] for fd in fa)))]
            cols.append(["Origen del dato", "t"])
            total.append("")
            nombre = HOJA_CARTERA[a]
            datos.append(hoja(nombre, "Datos del cliente · " + rotulo[a], cols, filas_d, total,
                              explica=EXPLICA["cartera" if not con_y else "cartera_anterior"], guia=GUIA[nombre],
                              ocultas=claves))
        prov = anx["provision"]
        datos.append(hoja(D4, "Datos del cliente · Provisión inicial por factura (RQ-004)",
                          [["Factura", "t"], ["Cliente", "t"], ["Provisión inicial", "n"], ["Impuesto diferido inicial", "n"],
                           ["Clave de cruce", "t"], ["Clave del cliente", "t"], ["Origen del dato", "t"]],
                          [[x["factura"], x["cliente"], x["provision"], x["diferido"], x["clave"], x["claveCli"], x["origen"]]
                           for x in prov],
                          ["TOTAL", "", s("C", FILA0 + len(prov) - 1, _n(sum(x["provision"] or 0 for x in prov))),
                           s("D", FILA0 + len(prov) - 1, _n(sum(x["diferido"] or 0 for x in prov))), "", "", ""] if prov else None,
                          guia=GUIA[D4], ocultas=claves))
        datos.append(hoja(D5, "Datos del cliente · Libro mayor de la provisión (RQ-005)",
                          [["Año", "t"], ["Saldo inicial", "n"], ["Gasto", "n"], ["Castigos", "n"], ["Recuperaciones", "n"],
                           ["Origen del dato", "t"]],
                          [[x["anio"], x["inicial"], x["gasto"], x["castigos"], x["recuperaciones"], x["origen"]]
                           for x in anx["movimiento"]], guia=GUIA[D5]))
    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros,
             explica=EXPLICA["02_Parametros"],
             guia=("La fecha de corte sale de la ficha del encargo; los cortes anteriores, de los anexos de cartera (hojas D2 y D3). "
                   "Tasas, plazos, umbrales y límites los fija el auditor con su sustento (columna «Sustento»); si cambia un valor, "
                   "todo el libro se recalcula.")),
        hoja("03_Evidencia_historica", "Evidencia histórica",
             [["Ventana", "t"], ["Tramo", "t"], ["Documentos", "i"], ["Emparejados", "i"], ["Saldo inicial", "n"],
              ["Sigue vivo al año siguiente", "n"], ["No recuperación", "p"], ["Usable", "t"]], evidencia,
             explica=EXPLICA["03_Evidencia_historica"]),
        hoja("04_Matriz_deterioro", "Matriz de deterioro",
             [["Tramo", "t"], ["Documentos", "i"], ["Saldo", "n"], ["Tasa aplicada", "p"], ["Origen", "t"],
              ["Pérdida", "n"], ["Base de la tasa", "t"]], matriz,
             ["TOTAL", s("B", m_fin, n_det), s("C", m_fin, _n(t["saldo"])), None, "", s("F", m_fin, _n(t["perdida"])), ""],
             explica=EXPLICA["04_Matriz_deterioro"]),
        hoja("05_Por_cliente", "Por cliente",
             [["Cliente", "t"], ["RUC", "t"], ["Documentos", "i"], ["Saldo", "n"], ["Corriente", "n"], ["Vencido", "n"],
              ["Mora máxima (días)", "i"], ["Tasa ponderada", "p"], ["Pérdida", "n"], ["Evaluación", "t"]], clientes,
             ["TOTAL", "", s("C", fin_cli, n_det), s("D", fin_cli, _n(t["saldo"])), s("E", fin_cli, _n(f["corriente"])),
              s("F", fin_cli, _n(t["saldo"] - f["corriente"])), None, None,
              s("I", fin_cli, _n(sum(c["perdida"] or 0 for c in d["clientes"]))), ""], explica=EXPLICA["05_Por_cliente"]),
        hoja("06_Movimiento_provision", "Movimiento de la provisión",
             [["Cliente", "t"], ["Factura", "t"], ["Provisión inicial", "n"], ["Reversión", "n"], ["Bajas", "n"],
              ["Provisión del año", "n"], ["Saldo final", "n"], ["Tipo", "t"]], movimiento,
             ["TOTAL", "", *[s(c, fin_mov, _n(mt[k])) for c, k in zip("CDEFG", ("provIni", "reversion", "bajas", "provAnio", "saldoFin"))], ""],
             explica=EXPLICA["06_Movimiento_provision"]),
        hoja("07_Mayor", "Provisión según el mayor",
             [["Año", "t"], ["Inicial", "n"], ["Gasto", "n"], ["Castigos", "n"], ["Recuperaciones", "n"], ["Final", "n"]], mayor,
             explica=EXPLICA["07_Mayor"]),
        hoja("08_Fiscal", "Fiscal", [["Concepto", "t"], ["Importe", "n"]], fiscal, explica=EXPLICA["08_Fiscal"]),
        hoja("09_Impuesto_diferido", "Impuesto diferido por factura",
             [["Cliente", "t"], ["Factura", "t"], ["Deterioro", "n"], ["Deducible", "n"], ["No deducible", "n"],
              ["Diferido inicial", "n"], ["Reversión", "n"], ["Diferido nuevo", "n"], ["Diferido final", "n"]], diferido,
             ["TOTAL", "", s("C", fin_dif, _n(tot_det_dif)), s("D", fin_dif, _n(sum(x["deducible"] for x in dif_f))),
              s("E", fin_dif, _n(sum(x["noDeducible"] for x in dif_f))),
              *[s(c, fin_dif, _n(dt[k])) for c, k in zip("FGHI", ("ini", "rev", "nuevo", "fin"))]],
             explica=EXPLICA["09_Impuesto_diferido"]),
        hoja("10_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos,
             explica=EXPLICA["10_Asientos"]),
        hoja("11_Detalle", "Detalle por factura",
             [["Factura", "t"], ["Cliente", "t"], ["Emisión", "d"], ["Vencimiento", "d"], ["Días de mora", "i"], ["Tramo", "t"],
              ["Saldo", "n"], ["Tasa", "p"], ["Valor presente", "n"], ["Pérdida", "n"], ["Provisión inicial", "n"]], detalle,
             ["TOTAL", "", "", "", None, "", s("G", det_fin, _n(t["saldo"])), None, s("I", det_fin, _n(d.get("vpTotal", sum(_f(x["vp"]) or 0 for x in filas)))),
              s("J", det_fin, _n(t["perdida"])), s("K", det_fin, _n(sum(float(x["provIni"]) for x in filas)))],
             explica=EXPLICA["11_Detalle"]),
        hoja("12_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], _n(e["amount"])] for e in res["exceptions"]]),
        *datos,
    ]


# --- definición de la herramienta (ficha CXC-PI-01) ---------------------------

def _req(id, doc, ds, proc, purpose, required=True, formats=("xlsx", "csv"), use="calculo", content=""):
    r = {"id": id, "document": doc, "formats": list(formats), "purpose": purpose, "procedure": proc,
         "required": required, "use": use}
    if ds:
        r["dataset"] = ds
    if content:
        r["content"] = content
    return r


def definicion() -> dict:
    """La definición que se instala en la ficha: base técnica, programa y
    requerimientos. `processor` le dice al ciclo que el cálculo lo hace este
    módulo y no el motor declarativo."""
    cartera = "Una fila por factura: N° de factura, cliente, emisión, vencimiento y saldo; sin filas de total."
    return {
        "name": "Deterioro de cuentas por cobrar · pérdidas incurridas (PYMES)",
        "area": "Cuentas por cobrar",
        "processor": "perdidas_incurridas_s11",
        "frameworks": ["NIIF para las PYMES"],
        "summary": ("Recalcula la provisión por deterioro de la cartera comercial con el modelo de pérdida incurrida de la "
                    "Sección 11: antigüedad de la mora, tasas de no recuperación observadas en los anexos de tres ejercicios, "
                    "valor presente de los flujos, evaluación individual, movimiento de la provisión, límites fiscales e "
                    "impuesto diferido."),
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": "NIIF para las PYMES, Sección 11 · párr. 11.13 y 11.21–11.26 (deterioro de activos financieros al costo amortizado)",
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 540 (Revisada)", "section": "párr. 13 y 17–30",
             "requirement": "La provisión es una estimación: evaluar el método (migración por tramos), los datos (anexos de 3 años), los supuestos (plazo, tasa, umbrales) y el posible sesgo."},
            {"document": "NIA 500", "section": "párr. 9",
             "requirement": "Los anexos de cartera los produce la entidad: evaluar su exactitud e integridad contra el mayor antes de usarlos."},
            {"document": "NIA 505", "section": "párr. 7", "requirement": "Considerar confirmaciones de saldos de clientes significativos."},
            {"document": "NIA 560", "section": "párr. 6", "requirement": "Revisar cobros posteriores al cierre como evidencia de recuperabilidad."},
            {"document": "NIA 330", "section": "párr. 18", "requirement": "Procedimientos sustantivos sobre la valoración de la cartera, saldo material."},
        ],
        "calculo": [
            "Días de mora de cada factura al corte de su año y tramo: corriente, 1–30, 31–60, 61–90, 91–180, 181–360, 361–730 y más de 730 (los dos últimos, graves).",
            "Evidencia histórica (11.22 e): por cada par de años, la parte de la factura que sigue viva al año siguiente no se recuperó; tasa del tramo = saldo que persiste ÷ saldo inicial del tramo.",
            "Tasa por tramo: la observada; sin historia, 100 % en los graves si hay saldos de más de 730 días, 0 % en el corriente (11.22: sin evento de pérdida no hay deterioro) y «no medible» en los demás: la fija el auditor.",
            "Pérdida por factura (11.25) = saldo − saldo × (1 − tasa) ÷ (1 + tasa efectiva)^(plazo/12).",
            "Por cliente: tasa ponderada y evaluación individual por mora grave o saldo significativo (11.24).",
            "Movimiento de la provisión (11.26): inicial − reversión − bajas + provisión del año = saldo final.",
            "Fiscal (LRTI Art. 10 num. 11): límite anual sobre la cartera corriente y límite acumulado sobre la cartera total.",
            "Impuesto diferido por la parte no deducible × tasa del impuesto; asientos propuestos.",
            "Ajuste propuesto = pérdida recalculada − provisión registrada según el mayor.",
        ],
        "fields": CAMPOS["cartera"], "rules": [], "control": "saldo", "primary": "ajuste",
        "campos": CAMPOS, "parametros": {k: v for k, v in PARAMETROS.items() if k != "tasas"},
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "CXCPI-01", "objective": "Integridad de la cartera", "risk": "Anexo incompleto o no conciliado", "assertion": "Integridad",
             "procedure": "Conciliar el anexo de cartera del ejercicio con el mayor al corte", "evidence": "Anexo de cartera y mayor",
             "criterion": "Diferencia dentro de tolerancia o explicada", "source": "NIA 500 párr. 9"},
            {"code": "CXCPI-02", "objective": "Evidencia histórica de recuperación", "risk": "Tasas sin sustento", "assertion": "Valoración",
             "procedure": "Emparejar las facturas de cada año con las del año siguiente y medir la no recuperación por tramo",
             "evidence": "Anexos de cartera de 3 ejercicios", "criterion": "Tasa por tramo medida, o declarada no medible con su causa",
             "source": "Secc. 11 párr. 11.22(e) · NIA 540"},
            {"code": "CXCPI-03", "objective": "Evaluación individual", "risk": "Clientes significativos o en mora grave sin evaluar", "assertion": "Valoración",
             "procedure": "Evaluar individualmente los clientes sobre el umbral de saldo o con mora de 361 días o más",
             "evidence": "Antigüedad por cliente, gestión de cobro", "criterion": "Tasa y plazo por cliente documentados", "source": "Secc. 11 párr. 11.24"},
            {"code": "CXCPI-04", "objective": "Medición de la pérdida", "risk": "Pérdida mal calculada", "assertion": "Valoración",
             "procedure": "Recalcular por factura y por cliente: importe en libros − valor presente de los flujos estimados",
             "evidence": "Detalle por factura", "criterion": "Pérdida recalculada", "source": "Secc. 11 párr. 11.25"},
            {"code": "CXCPI-05", "objective": "Movimiento de la provisión", "risk": "Reversiones o bajas sin sustento", "assertion": "Exactitud",
             "procedure": "Conciliar provisión inicial − reversiones − bajas + provisión del año con el mayor",
             "evidence": "Anexo de provisión inicial, mayor", "criterion": "Movimiento conciliado; reversiones dentro del límite", "source": "Secc. 11 párr. 11.26"},
            {"code": "CXCPI-06", "objective": "Tratamiento fiscal e impuesto diferido", "risk": "Deducción excesiva o diferido mal medido", "assertion": "Presentación",
             "procedure": "Aplicar los límites de deducibilidad y medir el activo por impuesto diferido",
             "evidence": "Parámetros fiscales, provisión fiscal anterior", "criterion": "Deducible y diferido recalculados", "source": "LRTI Art. 10 num. 11 · Secc. 29"},
            {"code": "CXCPI-07", "objective": "Cobros posteriores", "risk": "Recuperaciones no consideradas", "assertion": "Valoración",
             "procedure": "Cotejar cobros posteriores al cierre con las facturas deterioradas", "evidence": "Estados de cuenta, depósitos posteriores",
             "criterion": "Excepciones evaluadas", "source": "NIA 560 párr. 6 · Secc. 32"},
        ],
        "requests": [
            _req("RQ-001", "Anexo de cartera por factura al cierre del ejercicio corriente", "a3", "CXCPI-01",
                 "Población a evaluar y conciliar con el mayor", content=cartera),
            _req("RQ-002", "Anexo de cartera por factura al cierre del ejercicio anterior", "a2", "CXCPI-02",
                 "Medir la no recuperación de un año al siguiente", content=cartera),
            _req("RQ-003", "Anexo de cartera por factura al cierre de dos ejercicios antes", "a1", "CXCPI-02",
                 "Segunda ventana de evidencia histórica", required=False, content=cartera),
            _req("RQ-004", "Anexo de provisión y diferidos por factura al inicio del ejercicio", "provision", "CXCPI-05",
                 "Provisión inicial por factura: reversiones, bajas y diferido inicial",
                 content="Una fila por factura con provisión: N° de factura, cliente, provisión e impuesto diferido."),
            _req("RQ-005", "Movimiento de la provisión según el mayor (3 ejercicios)", "movimiento", "CXCPI-05",
                 "Provisión registrada al cierre y del ejercicio anterior",
                 content="Una fila por año: inicial, gasto, castigos y recuperaciones."),
            _req("RQ-006", "Cobros posteriores al cierre", None, "CXCPI-07", "Evidencia de recuperabilidad posterior",
                 formats=("xlsx", "pdf"), use="soporte"),
            _req("RQ-007", "Política de crédito y cobranza, gestión de cobro de clientes en mora", None, "CXCPI-03",
                 "Sustento de la evaluación individual", formats=("pdf", "docx"), use="soporte"),
            _req("RQ-008", "Ventas por factura de los 3 ejercicios", None, "CXCPI-02",
                 "Contexto de la rotación; no interviene en el cálculo", required=False, use="soporte"),
        ],
    }


DATASETS = ("a1", "a2", "a3", "provision", "movimiento")


# Total que muestra el ejemplo de control en el Estudio.
TOTAL_EJEMPLO = "perdida"
# Anexo que es la población del corte (se concilia con el mayor).
PRINCIPAL = "a3"


def kind(dataset: str) -> str:
    return "cartera" if dataset in ("a1", "a2", "a3") else dataset


def validar_definicion(d: dict) -> dict:
    """Lo que el ciclo exige a una definición con este procesador."""
    ds = [r.get("dataset") for r in d.get("requests") or [] if r.get("dataset")]
    if "a3" not in ds or len(ds) != len(set(ds)) or any(x not in DATASETS for x in ds):
        raise ValueError("La definición necesita un requerimiento por anexo y el de la cartera del ejercicio corriente (a3).")
    if not str(d.get("name") or "").strip() or not str(d.get("area") or "").strip():
        raise ValueError("Indique nombre y rubro de la herramienta.")
    return d


# Ejemplo numérico de control de la ficha (E.6): 91–180 días, 400 ÷ 1.000 = 40 %;
# una factura de 2.000 en ese tramo pierde 800,00.
def _ej(id, cliente, emision, vence, saldo):
    return {"id": id, "cliente": cliente, "emision": emision, "vence": vence, "saldo": saldo, "_row": 2}


EJEMPLO = {
    "corte": "2025-12-31",
    "datasets": {
        "a2": [_ej("F-1", "A", "2024-07-01", "2024-08-15", "1000"), _ej("F-2", "B", "2024-12-15", "2025-01-14", "500")],
        "a3": [_ej("F-1", "A", "2024-07-01", "2024-08-15", "400"), _ej("F-3", "C", "2025-07-01", "2025-08-15", "2.000,00")],
    },
}
