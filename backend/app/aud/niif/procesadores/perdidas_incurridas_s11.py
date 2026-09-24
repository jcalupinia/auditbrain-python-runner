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
                    "importe": a_num(f.get("importe")), "ruc": str(f.get("ruc", "")).strip(), "_row": f.get("_row")})
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
    for f in cart["a3"]:
        t = tasa_de(f["tramo"])
        flujo = None if t is None else f["saldo"] * (1 - t)
        vp = None if flujo is None else flujo / (1 + i) ** (plazo / 12)
        perdida = None if vp is None else max(f["saldo"] - vp, 0)
        facturas.append({**f, "tasa": t, "flujo": flujo, "vp": vp, "perdida": perdida,
                         "provIni": prov_ini.get(norm(f["factura"]), 0)})
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
                           "provAnio": det, "saldoFin": det,
                           "tipo": "Con deterioro" if det > 0 else ("Reversión" if ini > 0 else "Sin movimiento")})
    claves = set(prov_ini) | set(dta_ini)
    bajas, pendientes = [], []
    for k in sorted(claves):
        if k in en_cartera:
            continue
        info = info_anexo.get(k, {"cliente": "", "factura": k})
        activo = norm(info["cliente"]) in cli_activos if info["cliente"] else False
        fila = {"k": k, "cliente": info["cliente"] or "(sin nombre en el anexo)", "factura": info["factura"],
                "prov": prov_ini.get(k, 0), "dif": dta_ini.get(k, 0)}
        (pendientes if activo else bajas).append(fila)
    for b in bajas:
        if b["prov"] > 0:
            movimiento.append({"cliente": b["cliente"], "factura": b["factura"], "provIni": b["prov"], "reversion": 0,
                               "bajas": b["prov"], "provAnio": 0, "saldoFin": 0,
                               "tipo": "Baja o castigo: ya no está en la cartera"})
    for q in pendientes:
        if q["prov"] > 0:
            movimiento.append({"cliente": q["cliente"], "factura": q["factura"], "provIni": q["prov"], "reversion": 0,
                               "bajas": 0, "provAnio": 0, "saldoFin": q["prov"],
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
                          "noDeducible": nod, "dtaIni": d_ini, "reversion": d_ini, "dtaNuevo": d_new, "dtaFin": d_new})
    for b in bajas:
        if b["dif"] > 0:
            t_ini += b["dif"]
            t_rev += b["dif"]
            dif_filas.append({"cliente": b["cliente"], "factura": b["factura"], "deterioro": 0, "deducible": 0, "noDeducible": 0,
                              "dtaIni": b["dif"], "reversion": b["dif"], "dtaNuevo": 0, "dtaFin": 0})
    for q in pendientes:
        if q["dif"] > 0:
            t_ini += q["dif"]
            dif_filas.append({"cliente": q["cliente"], "factura": q["factura"], "deterioro": 0, "deducible": 0, "noDeducible": 0,
                              "dtaIni": q["dif"], "reversion": 0, "dtaNuevo": 0, "dtaFin": q["dif"]})
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
               "bajasAnexo": bajas, "pendientesAnexo": pendientes, "parametros": p}
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
]

# Referencias fijas entre cédulas (fila de cada parámetro y de cada concepto fiscal).
P = "'02_Parametros'!"
PAR = {"corte": 5, "corte2": 6, "corte1": 7, "tasaDesc": 8, "plazoBase": 9, "umbralGrave": 10, "umbralIndividual": 11,
       "pctDeducible": 12, "pctLimite": 13, "tasaImp": 14, "provFiscalAnt": 15, "dtaIniManual": 16}
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
DESC = f"(1+{P}$B${PAR['tasaDesc']}/100)^({P}$B${PAR['plazoBase']}/12)"


# Explicación humana de cada columna calculada («Cómo se calcula esta hoja»).
EXPLICA = {
    "01_Resumen": {
        "Importe": ("Trae cada importe de la hoja donde se calculó: cartera, pérdida, gasto deducible y no deducible y "
                    "diferido de la hoja 08 (Fiscal); provisión registrada del último año de la hoja 07 (Provisión según "
                    "el mayor); reversión y bajas de los totales de la hoja 06 (Movimiento de la provisión). El ajuste "
                    "propuesto es la pérdida recalculada menos la provisión registrada."),
    },
    "03_Evidencia_historica": {
        "No recuperación": ("Divide el saldo del tramo que seguía sin cobrarse al año siguiente para su saldo inicial en "
                            "esa ventana: es la parte que no se recuperó. Si el saldo inicial es cero, queda en blanco."),
    },
    "04_Matriz_deterioro": {
        "Documentos": "Cuenta cuántas facturas del detalle (hoja 11, Detalle por factura) caen en este tramo de mora.",
        "Saldo": "Suma el saldo de todas las facturas del detalle (hoja 11, Detalle por factura) que caen en este tramo.",
        "Tasa aplicada": ("Si el auditor fijó la tasa del tramo, la toma de la hoja 02 (Parámetros) y la divide para 100; "
                          "si viene de la migración observada, divide el saldo que siguió vivo para el saldo inicial del "
                          "tramo, sumando solo las ventanas marcadas «Sí» como usables en la hoja 03 (Evidencia histórica)."),
        "Pérdida": ("Suma la pérdida calculada factura por factura en la hoja 11 (Detalle por factura) para las facturas "
                    "de este tramo."),
    },
    "05_Por_cliente": {
        "Documentos": "Cuenta cuántas facturas del cliente hay en el detalle de la hoja 11 (Detalle por factura).",
        "Saldo": "Suma el saldo de todas las facturas del cliente que figuran en la hoja 11 (Detalle por factura).",
        "Corriente": ("Suma el saldo de las facturas del cliente que al corte no están vencidas (días de mora cero o "
                      "negativos) según la hoja 11 (Detalle por factura)."),
        "Vencido": "Resta al saldo total del cliente la parte corriente: lo que queda es la cartera ya vencida del cliente.",
        "Pérdida": ("Aplica la tasa ponderada del cliente: al saldo le resta el valor presente de la parte que se espera "
                    "cobrar, descontada con la tasa y el plazo de la hoja 02 (Parámetros). Sin tasa ponderada, queda en blanco."),
    },
    "06_Movimiento_provision": {
        "Provisión del año": ("Trae la pérdida recalculada de esta misma factura desde la hoja 11 (Detalle por factura); "
                              "es la provisión que debería constituirse en el año."),
        "Saldo final": ("Parte de la provisión inicial, resta la reversión y las bajas del año y suma la provisión del año: "
                        "es el saldo que debería quedar en la provisión de la factura."),
    },
    "07_Mayor": {
        "Final": ("Parte del saldo inicial del mayor, suma el gasto del año, resta los castigos y suma las recuperaciones: "
                  "es el saldo de la provisión al cierre de ese año."),
    },
    "08_Fiscal": {
        "Importe": ("Cada concepto tiene su propio cálculo: la cartera, la parte corriente y la pérdida se suman del "
                    "detalle de la hoja 11; la provisión anterior viene de la hoja 07 (Provisión según el mayor); los "
                    "límites y el diferido aplican los porcentajes de la hoja 02 (Parámetros); el resto combina las "
                    "filas anteriores de esta hoja (gasto, margen, parte deducible y no deducible)."),
    },
    "09_Impuesto_diferido": {
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


def _tramo_formula(celda: str) -> str:
    """Tramo de mora con IF anidados, en el orden de TRAMOS."""
    f = f'"{TRAMOS[-1]["n"]}"'
    for t in reversed(TRAMOS[:-1]):
        f = f'IF({celda}<={t["max"]},"{t["n"]}",{f})'
    return f'IF({celda}="","",{f})'


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

    # 02 · Parámetros: filas fijas (PAR) y luego una por tasa fijada por el auditor.
    num = lambda k: _f(p.get(k))
    parametros = [
        ["Corte del ejercicio corriente", d["cortes"]["a3"], "Ficha del encargo"],
        ["Corte del ejercicio anterior", d["cortes"]["a2"] or "Sin anexo", "Fin del mes de la última emisión del anexo"],
        ["Corte de dos ejercicios antes", d["cortes"]["a1"] or "Sin anexo", "Fin del mes de la última emisión del anexo"],
        ["Tasa efectiva para descontar (%)", num("tasaDesc"), "Secc. 11 párr. 11.13 y 11.25"],
        ["Plazo esperado de cobro (meses)", num("plazoBase"), "Juicio del auditor"],
        ["Umbral de mora grave (días)", num("umbralGrave"), "Secc. 11 párr. 11.24"],
        ["Umbral de saldo significativo", num("umbralIndividual"), "Secc. 11 párr. 11.24 (0 = desactivado)"],
        ["Límite anual deducible (%)", num("pctDeducible"), "LRTI Art. 10 num. 11"],
        ["Límite acumulado (%)", num("pctLimite"), "LRTI Art. 10 num. 11"],
        ["Tasa del impuesto (%)", num("tasaImp"), "Tarifa del contribuyente"],
        ["Provisión fiscal acumulada anterior", num("provFiscalAnt"), "En blanco: mínimo entre la provisión anterior y el límite acumulado"],
        ["Activo por impuesto diferido inicial", num("dtaIniManual"), "En blanco: el del anexo de provisión inicial"],
    ]
    fila_tasa = {}
    for k, v in manual.items():
        fila_tasa[k] = FILA0 + len(parametros)
        parametros.append([f"Tasa fijada por el auditor · {NOMBRE_TRAMO.get(k, k)} (%)", _f(v), "Juicio del auditor con evidencia de cobro"])

    # 03 · Evidencia histórica: una fila por ventana y tramo; «Usable» decide si entra.
    evidencia = []
    for m in d["migracion"]:
        for k, v in m["porT"].items():
            r = FILA0 + len(evidencia)
            evidencia.append([f"{m['de']} → {m['a']}", NOMBRE_TRAMO[k], v["docs"], v["emparejados"], _n(v["inicial"]), _n(v["persiste"]),
                              _fx(f'IF(E{r}=0,"",F{r}/E{r})', (v["persiste"] / v["inicial"]) if v["inicial"] else None),
                              "Sí" if m["diag"]["usable"] else "No"])

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
    for i, x in enumerate(filas):
        r = FILA0 + i
        tm = tasa_mat.format(r=r)
        detalle.append([
            x["id"], x["cliente"], x["emision"], x["vence"],
            _fx(f'IF(D{r}="","",{P}$B${PAR["corte"]}-D{r})', int(x["dias"]) if x["dias"] else None),
            _fx(_tramo_formula(f"E{r}"), x["tramo"]), _n(x["saldo"]),
            _fx(f'IF(F{r}="","",IF({tm}="","",{tm}))', _f(x["tasa"])),
            _fx(f'IF(H{r}="","",G{r}*(1-H{r})/{DESC})', _n(_f(x["vp"]))),
            _fx(f'IF(I{r}="","",MAX(G{r}-I{r},0))', _n(_f(x["perdida"]))), _n(x["provIni"]),
        ])
    tot_det = FILA0 + n_det
    s = lambda col, fin, v: _fx(f"SUM({col}{FILA0}:{col}{fin})", v)

    # 07 · Mayor: saldo final = inicial + gasto − castigos + recuperaciones.
    mayor = [[m["anio"], _n(m["ini"]), _n(m["gasto"]), _n(m["cast"]), _n(m["rec"]),
              _fx(f"B{FILA0 + j}+C{FILA0 + j}-D{FILA0 + j}+E{FILA0 + j}", _n(m["fin"]))] for j, m in enumerate(d["mayor"])]
    nm = len(mayor)
    prov_ant_ref = f"{MAY}F{FILA0 + nm - 2}" if nm > 1 else (f"{MAY}B{FILA0}" if nm == 1 else "0")
    prov_reg_ref = f"{MAY}F{FILA0 + nm - 1}" if nm else "0"

    # 06 · Movimiento: la provisión del año es la pérdida del Detalle por factura.
    movs = [m for m in d["movimiento"] if m["provIni"] or m["provAnio"]]
    movimiento = []
    for j, m in enumerate(movs):
        r = FILA0 + j
        movimiento.append([m["cliente"], m["factura"], _n(m["provIni"]), _n(m["reversion"]), _n(m["bajas"]),
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
         _fx(dta_ini, _n(f["dtaIni"])) if dta_ini else _n(f["dtaIni"])],
        ["Movimiento del diferido", _fx(f"{F_['dtaFin']}-{F_['dtaIni']}", _n(f["dtaMov"]))],
    ]

    # 09 · Diferido: la parte deducible se reparte en proporción al deterioro.
    dif_f = d["diferido"]["filas"]
    tot_dif = FILA0 + len(dif_f)
    fin_dif = tot_dif - 1
    diferido = []
    for j, x in enumerate(dif_f):
        r = FILA0 + j
        diferido.append([x["cliente"], x["factura"],
                         _fx(f"SUMIF({rango('A')},B{r},{rango('J')})", _n(x["deterioro"])),
                         _fx(f"IF($C${tot_dif}=0,0,C{r}*MIN({F_['provFiscalAcum']},$C${tot_dif})/$C${tot_dif})", _n(x["deducible"])),
                         _fx(f"C{r}-D{r}", _n(x["noDeducible"])), _n(x["dtaIni"]), _n(x["reversion"]),
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
                         _fx(f"D{r}-E{r}", _n(c["vencido"])), c["maxdv"], c["tasaPond"],
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

    hoja = lambda name, label, cols, rows, total=None, explica=None: {"name": name, "label": label, "cols": cols, "rows": rows,
                                                                      "total": total, "explica": dict(explica or {})}
    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
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
             ["TOTAL", "", "", "", None, "", s("G", det_fin, _n(t["saldo"])), None, s("I", det_fin, _n(sum(_f(x["vp"]) or 0 for x in filas))),
              s("J", det_fin, _n(t["perdida"])), s("K", det_fin, _n(sum(float(x["provIni"]) for x in filas)))],
             explica=EXPLICA["11_Detalle"]),
        hoja("12_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], _n(e["amount"])] for e in res["exceptions"]]),
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
