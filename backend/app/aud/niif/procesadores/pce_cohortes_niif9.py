"""Pérdida crediticia esperada por análisis de cohortes (NIIF 9, enfoque
simplificado) — matriz de provisiones con ventana de observación de 24 meses.

Herramienta de auditoría externa `AUD-ECL-01`. Recalcula, de forma independiente,
la corrección de valor de las cuentas por cobrar comerciales a partir de TRES
cierres consecutivos de la cartera (t-2, t-1, t), el movimiento de la provisión de
tres ejercicios y la cartera según los estados financieros.

Método (réplica fiel del artefacto de referencia `AuditBrain_NIIF9_Matriz_PCE`,
que es la autoridad numérica):

1. Bandas de mora desde el vencimiento contractual y segmentos NO-RELACIONADOS /
   RELACIONADOS (B5.5.35). La banda abierta se desdobla en el umbral de
   incumplimiento (M18) para no mezclar cartera gestionable con cartera perdida.
2. Tasa observada por cohorte con ventana de 24 meses (t-2 -> t): de los documentos
   vivos al corte t-2, cuánto saldo sigue presente en t. `tasa = remanente / exposición
   inicial`. El documento que ya no está se resolvió (cobro o castigo); el que sigue
   no se recuperó en 24 meses.
3. La exposición se ancla a la cartera contabilizada por segmento
   (`factor = EEFF / archivo`), para que el recálculo cuadre con el balance.
4. Factor prospectivo por segmento (5.5.17 c).
5. `PCE(s,b) = Exposición(s,b) × tasa observada × factor`. `PCE_total = Σ PCE`.
6. Compuertas de auditoría: trazabilidad de documentos entre cortes, validación del
   método contra los castigos (`tasa_castigo < 5 %`), rupturas de la curva y
   hallazgos en formato CCCEER.

Sin módulo fiscal: la deducibilidad y el impuesto diferido se derivan al módulo TAX
(frontera de la especificación §1.2). El libro Excel lleva cada importe calculado
como fórmula viva que remite a Parámetros, Detalle, Cohorte y Matriz.
"""
from __future__ import annotations

from datetime import date

from backend.app.aud.niif.procesadores import problemas
from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (filas_mapeadas se re-exporta para el ciclo)
    FILA0, a_fecha, a_num, campo, filas_mapeadas, fx, hoja, m as money, n2, num, problema, r2, ref, req,
    suma, validar_campos, validar_definicion_generica,
)

VERSION = "pce-cohortes 1.0"
RUBRO = "CXC"

# --- bandas y segmentos ------------------------------------------------------
# Nombres y límites idénticos al artefacto de referencia (autoridad numérica).
BANDAS = [
    {"k": "pv", "n": "Por vencer", "d": -999999, "h": 0},
    {"k": "t30", "n": "0 a 30 días", "d": 1, "h": 30},
    {"k": "t60", "n": "31 a 60 días", "d": 31, "h": 60},
    {"k": "t90", "n": "61 a 90 días", "d": 61, "h": 90},
    {"k": "t180", "n": "91 a 180 días", "d": 91, "h": 180},
    {"k": "t360", "n": "181 a 360 días", "d": 181, "h": 360},
    {"k": "tmax", "n": "Más de 360 días", "d": 361, "h": 999999},
]
SEG = ["NO-RELACIONADOS", "RELACIONADOS"]
IMPAGO_DIAS = 90  # B5.5.37: presunción de impago a los 90 días de mora

# --- anexos (subida de archivos) ---------------------------------------------
_CARTERA = [
    campo("id", "N° de documento", "text", True,
          ["documento", "comprobante", "factura", "numero", "nro", "n°", "num"], "F-0001"),
    campo("cliente", "Cliente", "text", True,
          ["cliente", "razon", "razon social", "nombre", "deudor"], "Cliente A"),
    campo("tipo", "Tipo / relacionadas", "text", False,
          ["tipo", "relacion", "clasif", "categoria"], "NO-RELACIONADO"),
    campo("vence", "Fecha de vencimiento", "date", True,
          ["vencimiento", "vence", "venc", "fecha vencimiento"], "2023-11-15"),
    campo("saldo", "Saldo", "number", True,
          ["saldo", "cuentas por cobrar", "monto", "valor", "importe", "por cobrar"], "1000.00"),
    campo("ruc", "RUC / identificación", "text", False,
          ["ruc", "cedula", "identificacion", "codigo cliente"], ""),
]
CAMPOS = {"cartera": _CARTERA}
# Tres cortes de cartera. El principal es el corte actual (se concilia con el mayor y los EEFF).
# El movimiento de la provisión y la cartera EEFF entran como parámetros (soporte RQ-004).
TIPOS = {"cartera_t2": "cartera", "cartera_t1": "cartera", "cartera_t": "cartera"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "cartera_t"
CONTROL = "saldo"
TOTAL_EJEMPLO = "pce"

# --- parámetros --------------------------------------------------------------
_POL_KEYS = [f"pol_{b['k']}" for b in BANDAS]
PARAMETROS = {
    "umbral": 730, "desdoblar": "Sí", "relKey": "RELACIONAD",
    "fT": 1.0, "fR": 1.0,
    "matDesempeno": None, "umbralIndividual": None,
    "castiga": "", "trasladoJuridico": None,
    # movimiento de la provisión — tres ejercicios (t-2, t-1, t)
    "provIni_t2": None, "provCon_t2": None, "provRev_t2": None, "provCas_t2": None, "provBal_t2": None,
    "provIni_t1": None, "provCon_t1": None, "provRev_t1": None, "provCas_t1": None, "provBal_t1": None,
    "provIni_t": None, "provCon_t": None, "provRev_t": None, "provCas_t": None, "provBal_t": None,
    # cartera según EEFF — tres ejercicios (no relacionados / relacionados)
    "eNR_t2": None, "eR_t2": None, "eNR_t1": None, "eR_t1": None, "eNR_t": None, "eR_t": None,
    # política declarada por la entidad (tasa % por banda, opcional)
    **{k: None for k in _POL_KEYS},
}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "umbral": "Umbral de incumplimiento (días sin cobro)",
    "desdoblar": "Dividir la banda más antigua en el umbral (Sí/No)",
    "relKey": "Texto que identifica partes relacionadas",
    "fT": "Factor prospectivo — terceros", "fR": "Factor prospectivo — relacionadas",
    "matDesempeno": "Materialidad de desempeño", "umbralIndividual": "Umbral de evaluación individual",
    "castiga": "¿La entidad castiga cartera? (Sí/No)", "trasladoJuridico": "Día de traslado a gestión jurídica",
    "provIni_t2": "Provisión inicial (t-2)", "provCon_t2": "Constitución (t-2)", "provRev_t2": "Reversión (t-2)",
    "provCas_t2": "Castigos (t-2)", "provBal_t2": "Saldo según balance (t-2)",
    "provIni_t1": "Provisión inicial (t-1)", "provCon_t1": "Constitución (t-1)", "provRev_t1": "Reversión (t-1)",
    "provCas_t1": "Castigos (t-1)", "provBal_t1": "Saldo según balance (t-1)",
    "provIni_t": "Provisión inicial (t)", "provCon_t": "Constitución (t)", "provRev_t": "Reversión (t)",
    "provCas_t": "Castigos (t)", "provBal_t": "Saldo según balance (t)",
    "eNR_t2": "Cartera EEFF no relacionados (t-2)", "eR_t2": "Cartera EEFF relacionados (t-2)",
    "eNR_t1": "Cartera EEFF no relacionados (t-1)", "eR_t1": "Cartera EEFF relacionados (t-1)",
    "eNR_t": "Cartera EEFF no relacionados (t)", "eR_t": "Cartera EEFF relacionados (t)",
    **{f"pol_{b['k']}": f"Política declarada · {b['n']} (%)" for b in BANDAS},
}

# umbrales de juicio (idénticos al artefacto)
TRAZA_OK, TRAZA_WARN = 0.98, 0.80
TASA_CASTIGO_LIMITE = 0.05
RUPTURA_DELTA = 0.03
MUESTRA_MINIMA = 50
DIF_RELACIONADAS = 0.25
SUBPROVISION = 0.05
SOBREPROVISION = 0.15


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    return validar_campos(CAMPOS[tipo], filas)


# --- helpers de cálculo ------------------------------------------------------

def _clave(v) -> str:
    return str(v if v is not None else "").strip().lower()


def _hace_n_anios(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year - n)
    except ValueError:  # 29 de febrero -> 28 (Ecuador no tiene horario de verano)
        return d.replace(year=d.year - n, day=28)


def _bandas_efectivas(umbral: int, desdoblar: bool) -> list:
    """Copia de las bandas con el desdoblamiento de la banda abierta en el umbral (M18)."""
    bandas = [dict(b) for b in BANDAS]
    if desdoblar:
        last = bandas[-1]
        if last["h"] > umbral and last["d"] < umbral:
            n = round(umbral / 365)
            bandas.pop()
            bandas.append({"k": "tumb", "n": f"{last['d']} d — {n} años", "d": last["d"], "h": umbral})
            bandas.append({"k": "tinc", "n": f"Más de {n} años", "d": umbral + 1, "h": 999999})
    return bandas


def _banda_de(dias, bandas: list) -> str:
    if dias is None:
        return bandas[-1]["n"]
    for b in bandas:
        if b["d"] <= dias <= b["h"]:
            return b["n"]
    return bandas[-1]["n"]


def _es_desdoblar(v) -> bool:
    return str(v if v is not None else "Sí").strip().lower() in ("sí", "si", "1", "true", "s")


def _leer(filas: list, corte: date, rel_key: str) -> dict:
    """Depura una cartera como el artefacto: descarta sin documento/vencimiento/saldo, deduplica
    por documento (el primero gana), clasifica el segmento por el texto de tipo y calcula la mora."""
    rows, dup, bad, vistos = [], 0, 0, set()
    for f in filas or []:
        doc = str(f.get("id", "") or "").strip()
        saldo = a_num(f.get("saldo"))
        saldo = 0.0 if saldo is None else float(saldo)
        vence = a_fecha(f.get("vence"))
        if not doc or vence is None or abs(saldo) < 0.005:
            if doc or saldo:
                bad += 1
            continue
        if doc in vistos:
            dup += 1
            continue
        vistos.add(doc)
        tipo = str(f.get("tipo", "") or "").upper()
        rel = rel_key in tipo and ("NO-" + rel_key) not in tipo and ("NO " + rel_key) not in tipo
        dias = (corte - vence).days
        rows.append({"doc": doc, "cliente": str(f.get("cliente", "") or "").strip() or "(sin nombre)",
                     "saldo": saldo, "vence": vence, "dias": dias,
                     "seg": "RELACIONADOS" if rel else "NO-RELACIONADOS",
                     "ruc": str(f.get("ruc", "") or "").strip(), "_row": f.get("_row")})
    return {"rows": rows, "dup": dup, "bad": bad}


def _p(p, k):
    v = a_num(p.get(k))
    return 0.0 if v is None else float(v)


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_t = a_fecha(corte)
    if corte_t is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    if not datasets.get("cartera_t2") or not datasets.get("cartera_t1") or not datasets.get("cartera_t"):
        raise ValueError("Cargue los tres análisis de antigüedad de cartera (t-2, t-1 y t). "
                         "Sin tres cierres no existe una cohorte con ventana completa de 24 meses.")
    corte_t1 = _hace_n_anios(corte_t, 1)
    corte_t2 = _hace_n_anios(corte_t, 2)
    rel_key = str(p.get("relKey") or "RELACIONAD").upper()
    umbral = int(_p(p, "umbral") or 730)
    bandas = _bandas_efectivas(umbral, _es_desdoblar(p.get("desdoblar")))
    bn = [b["n"] for b in bandas]

    # depuración de los tres cortes
    d2 = _leer(datasets.get("cartera_t2"), corte_t2, rel_key)
    d1 = _leer(datasets.get("cartera_t1"), corte_t1, rel_key)
    dt = _leer(datasets.get("cartera_t"), corte_t, rel_key)
    for corte_dep, dd in ((corte_t2, d2), (corte_t1, d1), (corte_t, dt)):
        for r in dd["rows"]:
            r["banda"] = _banda_de(r["dias"], bandas)
    if not d2["rows"] or not d1["rows"] or not dt["rows"]:
        raise ValueError("No se obtuvieron registros válidos de alguno de los cortes. Revise la correspondencia de columnas.")

    # trazabilidad de documentos t-2 -> t
    set_t = {r["doc"] for r in dt["rows"]}
    hits = sum(1 for r in d2["rows"] if r["doc"] in set_t)
    traza = hits / len(d2["rows"]) if d2["rows"] else 0.0

    # exposición del archivo (corte t) por segmento y banda
    exp_file = {s: {b: 0.0 for b in bn} for s in SEG}
    for r in dt["rows"]:
        exp_file[r["seg"]][r["banda"]] += r["saldo"]
    tot_file = sum(r["saldo"] for r in dt["rows"])
    exp_file_seg = {s: sum(exp_file[s][b] for b in bn) for s in SEG}

    # anclaje a EEFF (corte t)
    e_nr, e_r = _p(p, "eNR_t"), _p(p, "eR_t")
    e_tot = e_nr + e_r
    anchor = e_tot > 0
    exp = {}
    factor_anclaje = {}
    for s in SEG:
        base = exp_file_seg[s]
        f = ((e_r if s == "RELACIONADOS" else e_nr) / base) if (anchor and base > 0) else 1.0
        factor_anclaje[s] = f
        exp[s] = {b: exp_file[s][b] * f for b in bn}
    tot_exp = sum(exp[s][b] for s in SEG for b in bn)

    # cohorte t-2 -> t (remanente del mismo documento en t)
    map_t = {}
    for r in dt["rows"]:
        map_t[r["doc"]] = map_t.get(r["doc"], 0.0) + r["saldo"]
    co = {s: {b: {"e": 0.0, "r": 0.0, "n": 0} for b in bn} for s in SEG}
    for r in d2["rows"]:
        c = co[r["seg"]][r["banda"]]
        c["e"] += r["saldo"]
        c["n"] += 1
        c["r"] += map_t.get(r["doc"], 0.0)
    tasa = {s: {b: (co[s][b]["r"] / co[s][b]["e"] if co[s][b]["e"] > 0 else None) for b in bn} for s in SEG}

    # factores prospectivos
    ff = {"NO-RELACIONADOS": _p(p, "fT") or 1.0, "RELACIONADOS": _p(p, "fR") or 1.0}

    # matriz PCE (orden SEG x banda, idéntico al artefacto)
    matriz, pce_total = [], 0.0
    for s in SEG:
        for b in bn:
            t_obs = tasa[s][b]
            t_apl = (0.0 if t_obs is None else t_obs) * ff[s]
            e = exp[s][b]
            pce = e * t_apl
            pce_total += pce
            matriz.append({"seg": s, "banda": b, "clave": f"{s}|{b}", "exp": e, "tasaObs": t_obs,
                           "factor": ff[s], "tasaApl": t_apl, "pce": pce, "docs": co[s][b]["n"]})

    # política declarada
    pol_map = {}
    for b in BANDAS:
        v = a_num(p.get(f"pol_{b['k']}"))
        if v is not None:
            pol_map[b["n"]] = float(v) / 100
    pol_rows, pol_tot = [], 0.0
    for b in bn:
        e = sum(exp[s][b] for s in SEG)
        r = pol_map.get(b)
        if r is None:  # banda desdoblada: hereda de la banda base por prefijo
            base = next((x for x in BANDAS if b.startswith(str(x["d"])) or "Más de" in b), None)
            r = pol_map.get(base["n"], 0.0) if base else 0.0
        pv = e * r
        pol_tot += pv
        pce_b = sum(mm["pce"] for mm in matriz if mm["banda"] == b)
        pol_rows.append({"banda": b, "exp": e, "tasa": r, "prov": pv, "pce": pce_b, "dif": pce_b - pv})

    # movimiento de la provisión
    may = []
    for suf, corte_y in (("t2", corte_t2), ("t1", corte_t1), ("t", corte_t)):
        ini, con, rev, cas = _p(p, f"provIni_{suf}"), _p(p, f"provCon_{suf}"), _p(p, f"provRev_{suf}"), _p(p, f"provCas_{suf}")
        bal = _p(p, f"provBal_{suf}")
        may.append({"suf": suf, "ini": ini, "con": con, "rev": rev, "cas": cas, "bal": bal, "fin": ini + con - rev - cas})
    prov_reg = may[2]["bal"] or may[2]["fin"]
    cargo_acum = sum(mmm["con"] for mmm in may)
    cast_acum = sum(mmm["cas"] for mmm in may)
    cohorte_base = sum(co[s][b]["e"] for s in SEG for b in bn)
    tasa_castigo = cast_acum / cohorte_base if cohorte_base > 0 else 0.0

    # cartera en incumplimiento (última banda)
    ult = bn[-1]
    baja = sum(exp[s][ult] for s in SEG)
    tasa_def = {s: tasa[s][ult] for s in SEG}

    ajuste = pce_total - prov_reg

    # --- problemas (controles, avisos y hallazgos) ---
    ex = []
    # C-controles / avisos
    if any(dd["dup"] > 0 for dd in (d2, d1, dt)):
        det = "; ".join(f"{et} ({dd['dup']})" for et, dd in (("t-2", d2), ("t-1", d1), ("t", dt)) if dd["dup"] > 0)
        ex.append(problema("W-INTEGRIDAD", f"Documentos duplicados depurados en la cartera del cliente: {det}. "
                           "Los duplicados se depuraron antes del cálculo; la deficiencia de control persiste.", 0))
    if traza < TRAZA_WARN:
        ex.append(problema("W-TRAZABILIDAD", f"Trazabilidad de documentos entre cortes {traza * 100:.1f} % (< 80 %): "
                           "el sistema podría renumerar documentos entre períodos y el método de cohortes no sería aplicable.", 0))
    elif traza < TRAZA_OK:
        ex.append(problema("W-TRAZABILIDAD", f"Trazabilidad de documentos entre cortes {traza * 100:.1f} % (< 98 %): "
                           "método aplicable con advertencia.", 0))
    if tasa_castigo >= TASA_CASTIGO_LIMITE:
        ex.append(problema("W-CASTIGOS-MATERIALES", f"Tasa de castigo sobre la cohorte {tasa_castigo * 100:.1f} % "
                           f"(≥ 5 %; castigos {money(cast_acum)}): identifique los documentos castigados y asígnelos a su "
                           "cohorte y banda de origen antes de dar por válidas las tasas por permanencia.", 0))
    for s in SEG:
        seq = [mm["tasaApl"] for mm in matriz if mm["seg"] == s and mm["docs"]]
        if any(b < a - RUPTURA_DELTA for a, b in zip(seq, seq[1:])):
            ex.append(problema("W-RUPTURA-CURVA", f"{s}: la tasa observada cae más de 3 puntos en una banda más antigua. "
                               "Investigue (concentración de un cliente, muestra menor a 50 documentos, o el traslado a "
                               "gestión jurídica) antes de corregir; nunca interpole automáticamente.", 0))
    sin_datos = [mm for mm in matriz if mm["tasaObs"] is None and mm["exp"] > 0]
    if sin_datos:
        tot = sum(mm["exp"] for mm in sin_datos)
        ex.append(problema("W-SIN-DATOS", f"{len(sin_datos)} combinaciones sin historia en la cohorte "
                           f"({money(tot)} de exposición). Fije la tasa con sustento o declare la limitación (5.5.18).", 0))
    for mm in matriz:
        if mm["docs"] and mm["docs"] < MUESTRA_MINIMA and mm["exp"] > 0:
            ex.append(problema("W-MUESTRA", f"{mm['seg']} · {mm['banda']}: {mm['docs']} documentos en la cohorte "
                               "(< 50): tasa observada poco representativa.", 0))
    if not anchor:
        ex.append(problema("W-SIN-ANCLA", "No se informó la cartera según EEFF del corte: el recálculo NO está "
                           "conciliado con la contabilidad (anclado = falso).", 0))

    # Hallazgos CCCEER (los 8 disparadores del artefacto)
    hallazgos = _hallazgos(may, cargo_acum, cast_acum, pol_rows, pce_total, pol_tot, baja, tot_exp, umbral,
                           tasa_def, ff, tasa, bn, str(p.get("castiga") or ""), (d2, d1, dt))
    for h in hallazgos:
        importe = h.get("importe", 0)
        ex.append(problema(h["code"], f"{h['titulo']} (riesgo {h['riesgo'].lower()}). {h['condicion']}", importe))
    if ajuste and abs(ajuste) > 0.005:
        ex.append(problema("AJUSTE", f"La pérdida esperada recalculada ({money(pce_total)}) difiere de la provisión "
                           f"registrada ({money(prov_reg)}).", r2(ajuste)))

    # filas del principal (corte t) — detalle por documento
    filas = []
    for r in dt["rows"]:
        clave = f"{r['seg']}|{r['banda']}"
        mm = next((x for x in matriz if x["clave"] == clave), None)
        t_apl = mm["tasaApl"] if mm else None
        pce_doc = r["saldo"] * t_apl if t_apl is not None else None
        filas.append({"id": r["doc"], "cliente": r["cliente"], "segmento": r["seg"],
                      "vence": r["vence"].isoformat(), "dias": str(r["dias"]), "banda": r["banda"],
                      "saldo": r2(r["saldo"]), "_row": r["_row"]})

    totals = {"cartera": r2(tot_exp), "pce": r2(pce_total), "provisionRegistrada": r2(prov_reg), "ajuste": r2(ajuste)}
    labels = {"cartera": "Cartera anclada a EEFF", "pce": "Pérdida crediticia esperada",
              "provisionRegistrada": "Provisión registrada", "ajuste": "Ajuste propuesto"}
    detalle = {
        "cortes": {"t": corte_t.isoformat(), "t1": corte_t1.isoformat(), "t2": corte_t2.isoformat()},
        "bandas": bandas, "bn": bn, "umbral": umbral, "traza": traza, "anchor": anchor,
        "factorAnclaje": factor_anclaje, "expFileSeg": exp_file_seg,
        "matriz": matriz, "cohorte": co, "exp": exp, "expFile": exp_file, "tasa": tasa,
        "polRows": pol_rows, "polTot": pol_tot, "may": may, "provReg": prov_reg,
        "cargoAcum": cargo_acum, "castAcum": cast_acum, "cohorteBase": cohorte_base, "tasaCastigo": tasa_castigo,
        "baja": baja, "totFile": tot_file, "totExp": tot_exp, "eNR": e_nr, "eR": e_r, "factores": ff,
        "cartera_t2": d2["rows"], "cartera_t1": d1["rows"], "hallazgos": hallazgos, "parametros": p,
        "dup": {"t2": d2["dup"], "t1": d1["dup"], "t": dt["dup"]},
    }
    return {"engine": VERSION, "rows": filas, "totals": totals, "labels": labels, "primary": "ajuste",
            "exceptions": ex, "schedule": [], "detalle": detalle}


def _hallazgos(may, cargo_acum, cast_acum, pol_rows, pce_total, pol_tot, baja, tot_exp, umbral,
               tasa_def, ff, tasa, bn, castiga, dups) -> list:
    """Los ocho hallazgos CCCEER del artefacto, con sus mismos disparadores."""
    H = []
    if cargo_acum == 0 and any(mmm["ini"] > 0 for mmm in may):
        H.append({"code": "H-PROV-ESTATICA", "titulo": "Provisión sin movimiento por estimación", "riesgo": "Alto",
                  "condicion": f"El mayor de la provisión no registra constitución con cargo a resultados en los tres "
                  f"ejercicios; el único movimiento fue un castigo de {money(cast_acum)}.",
                  "criterio": "NIIF 9 párr. 5.5.15: la corrección de valor se mide a cada fecha de presentación. NIC 8: las "
                  "estimaciones se revisan cuando cambian las circunstancias.",
                  "causa": "La provisión no se recalcula periódicamente; el saldo proviene del arrastre de ejercicios anteriores.",
                  "efecto": "El importe registrado no responde a la composición de la cartera de cada cierre.",
                  "recomendacion": "Recalcular la provisión a cada cierre con la matriz derivada del comportamiento observado.",
                  "importe": 0})
    sub = [pp for pp in pol_rows if pp["tasa"] == 0 and pp["pce"] > 0 and pp["exp"] > 0 and (pp["pce"] / pp["exp"]) > SUBPROVISION]
    sob = [pp for pp in pol_rows if pp["tasa"] > 0 and pp["prov"] - pp["pce"] > 0 and pp["exp"] > 0 and (pp["tasa"] - (pp["pce"] / pp["exp"])) > SOBREPROVISION]
    if sub or sob:
        H.append({"code": "H-POLITICA", "titulo": "Política de deterioro no sustentada en el comportamiento observado",
                  "riesgo": "Alto",
                  "condicion": (f"Bandas sin provisionar pese a mostrar pérdida observada: {', '.join(pp['banda'] for pp in sub)}. " if sub else "")
                  + (f"Bandas sobreprovisionadas frente a lo observado: {', '.join(pp['banda'] for pp in sob)}." if sob else ""),
                  "criterio": "NIIF 9 párr. 5.5.15 y B5.5.35: la matriz debe basarse en tasas de pérdida históricas de la propia entidad.",
                  "causa": "La política se definió sobre criterios de gestión de cobranza, no sobre el comportamiento de pago observado.",
                  "efecto": f"Diferencia neta {money(pce_total - pol_tot)} y diferencia bruta {money(sum(abs(pp['dif']) for pp in pol_rows))}; "
                  "los errores de signo contrario se compensan y el total parece razonable.",
                  "recomendacion": "Reemplazar los porcentajes fijos por la matriz observada, con revisión anual documentada.",
                  "importe": 0})
    if baja > 0 and castiga.strip() != "Sí":
        H.append({"code": "H-CARTERA-ANTIGUA", "titulo": "Cartera que alcanza el criterio de incumplimiento mantenida en el activo",
                  "riesgo": "Alto",
                  "condicion": f"Al corte permanecen {money(baja)} de cartera que supera el umbral de {umbral} días "
                  f"({(baja / tot_exp * 100) if tot_exp else 0:.2f} % de la cartera bruta).",
                  "criterio": "Marco conceptual: un activo se da de baja cuando no se esperan recuperar flujos.",
                  "causa": "No hay un procedimiento sistemático de depuración de cartera antigua.",
                  "efecto": "Sobrevaloración simultánea del activo bruto y de la provisión; distorsión de la rotación.",
                  "recomendacion": "Aplicar la baja previa verificación documental y coordinar el efecto fiscal con TAX.",
                  "importe": r2(baja)})
    if ff["NO-RELACIONADOS"] == 1 and ff["RELACIONADOS"] == 1:
        H.append({"code": "H-PROSPECTIVO", "titulo": "Ausencia del componente prospectivo", "riesgo": "Alto",
                  "condicion": "La estimación no incorpora información sobre condiciones futuras; el factor es 1,000 en todos los segmentos.",
                  "criterio": "NIIF 9 párr. 5.5.17(c): la estimación debe reflejar información razonable y sustentable sobre condiciones futuras.",
                  "causa": "No se ha desarrollado un procedimiento para incorporar información prospectiva.",
                  "efecto": "Incumplimiento de un requerimiento explícito de la norma.",
                  "recomendacion": "Documentar las variables prospectivas con fuente identificada y su traslación al factor.",
                  "importe": 0})
    dif = len(SEG) > 1 and any(
        tasa["NO-RELACIONADOS"][b] is not None and tasa["RELACIONADOS"][b] is not None
        and abs(tasa["NO-RELACIONADOS"][b] - tasa["RELACIONADOS"][b]) > DIF_RELACIONADAS for b in bn)
    if dif:
        H.append({"code": "H-SEGMENTACION", "titulo": "Comportamiento diferenciado en cartera con partes relacionadas",
                  "riesgo": "Alto",
                  "condicion": "Las tasas de pérdida de la cartera con partes relacionadas difieren sustancialmente de las de terceros.",
                  "criterio": "NIIF 9 B5.5.35: agrupar por características de riesgo compartidas. NIC 24: revelación separada.",
                  "causa": "La entidad no segmenta su análisis de deterioro entre terceros y partes relacionadas.",
                  "efecto": "Riesgo de estimación incorrecta y de revelación insuficiente.",
                  "recomendacion": "Segmentar el análisis y evaluar individualmente los saldos con partes relacionadas.",
                  "importe": 0})
    for mmm in may:
        if mmm["bal"] and abs(mmm["fin"] - mmm["bal"]) > 0.5:
            H.append({"code": "H-NOTA-INCONSISTENTE", "titulo": f"Inconsistencia en el movimiento de la provisión ({mmm['suf']})",
                      "riesgo": "Alto",
                      "condicion": f"El movimiento arroja un saldo final de {money(mmm['fin'])} y el balance presenta "
                      f"{money(mmm['bal'])}; diferencia de {money(mmm['fin'] - mmm['bal'])}.",
                      "criterio": "NIC 1: las notas deben ser consistentes con los importes de los estados principales.",
                      "causa": "Ausencia de control de cuadre entre el movimiento de la provisión y el saldo contabilizado.",
                      "efecto": "Revelación errónea del movimiento del ejercicio.",
                      "recomendacion": "Establecer un control de cuadre antes de la emisión.",
                      "importe": 0})
    dd = [et for et, x in (("t-2", dups[0]), ("t-1", dups[1]), ("t", dups[2])) if x["dup"] > 0]
    if dd:
        H.append({"code": "H-INTEGRIDAD-PT", "titulo": "Deficiencias de integridad en los papeles de trabajo de la entidad",
                  "riesgo": "Medio",
                  "condicion": f"Se detectaron documentos duplicados en el análisis de antigüedad: {', '.join(dd)}.",
                  "criterio": "NIA 500: la evidencia debe ser confiable. Control interno sobre la información financiera.",
                  "causa": "Ausencia de controles de revisión sobre la preparación del análisis de cartera.",
                  "efecto": "Riesgo de duplicación de saldos; los duplicados se depuraron pero la deficiencia persiste.",
                  "recomendacion": "Incorporar una validación de integridad de la población.",
                  "importe": 0})
    if cast_acum == 0 and castiga.strip() == "Sí":
        H.append({"code": "H-POLITICA-NO-APLICADA", "titulo": "Política de castigo declarada pero no aplicada", "riesgo": "Medio",
                  "condicion": "La entidad declara aplicar una política de castigo, pero el mayor no registra bajas en el horizonte analizado.",
                  "criterio": "NIC 8: las políticas contables se aplican de forma uniforme.",
                  "causa": "La política existe formalmente pero no se ejecuta.",
                  "efecto": "La cartera antigua permanece en el activo indefinidamente.",
                  "recomendacion": "Aplicar la política declarada o formalizar su modificación.",
                  "importe": 0})
    return H


# --- cédulas con fórmulas ----------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Exposicion", "Exposición anclada a EEFF"),
    ("04_Cohortes", "Cohortes (ventana 24 meses)"), ("05_Matriz_PCE", "Matriz de pérdida esperada"),
    ("06_Por_banda", "Pérdida por banda de mora"), ("07_Comparacion", "Comparación con la política"),
    ("08_Conciliacion", "Controles y conciliación"), ("09_Movimiento", "Movimiento de la provisión"),
    ("10_Hallazgos", "Hallazgos (CCCEER)"), ("11_Problemas", "Problemas encontrados"),
    ("12_Detalle", "Detalle de cartera al corte"), ("13_Cohorte_t2", "Cohorte del corte t-2"),
]

P = ref("02_Parametros")
DET, COH, EXPO, COHS, MAT, BAN = (ref("12_Detalle"), ref("04_Cohortes"), ref("03_Exposicion"),
                                  ref("13_Cohorte_t2"), ref("05_Matriz_PCE"), ref("06_Por_banda"))

# orden de la hoja de parámetros (para las referencias)
_PAR_ORDEN = ["corteT", "corteT1", "corteT2", "umbral", "relKey", "fT", "fR",
              "eNR_t", "eR_t", "eTot"]
PARFILA = {k: FILA0 + i for i, k in enumerate(_PAR_ORDEN)}


EXPLICA = {
    "01_Resumen": {"Importe": ("Trae cada cifra de la hoja donde se calcula: la cartera anclada de la hoja 03 "
                               "(Exposición), la pérdida esperada de la hoja 05 (Matriz), la provisión registrada de "
                               "la hoja 02 (Parámetros); el ajuste es la pérdida esperada menos la provisión registrada.")},
    "02_Parametros": {"Valor": ("Son datos del encargo o juicio del auditor; solo la exposición EEFF total suma los "
                                "importes de clientes no relacionados y relacionados del corte.")},
    "03_Exposicion": {
        "Exposición del archivo": "Suma el saldo de las facturas del detalle (hoja 12) de este segmento y banda.",
        "Factor de anclaje": ("Divide la cartera según EEFF del segmento (hoja 02) para el total del archivo de ese "
                              "segmento; si no hay cifra EEFF, es 1."),
        "Exposición anclada": "Multiplica la exposición del archivo por el factor de anclaje del segmento.",
    },
    "04_Cohortes": {
        "Documentos": "Cuenta las facturas de la cohorte del corte t-2 (hoja 13) de este segmento y banda.",
        "Exposición inicial": "Suma el saldo que tenían al corte t-2 las facturas de este segmento y banda (hoja 13).",
        "Remanente en t": "Suma lo que de esas mismas facturas sigue presente en el corte actual (hoja 13, columna Remanente).",
        "Tasa observada": ("Divide el remanente en t para la exposición inicial: la fracción del saldo que no se "
                           "resolvió en 24 meses. Sin exposición inicial, queda en blanco."),
    },
    "05_Matriz_PCE": {
        "Exposición anclada": "Trae la exposición anclada del mismo segmento y banda de la hoja 03.",
        "Tasa observada": "Trae la tasa observada del mismo segmento y banda de la hoja 04 (Cohortes).",
        "Factor prospectivo": "Trae el factor prospectivo del segmento de la hoja 02 (Parámetros).",
        "Tasa aplicada": "Multiplica la tasa observada (cero si está en blanco) por el factor prospectivo.",
        "Pérdida esperada": "Multiplica la exposición anclada por la tasa aplicada.",
    },
    "06_Por_banda": {
        "Exposición anclada": "Suma la exposición anclada de todos los segmentos de esta banda (hoja 05).",
        "Pérdida esperada": "Suma la pérdida esperada de todos los segmentos de esta banda (hoja 05).",
        "Tasa promedio": "Divide la pérdida esperada de la banda para su exposición anclada; sin exposición, queda en blanco.",
    },
    "07_Comparacion": {
        "Exposición anclada": "Trae la exposición anclada de la banda de la hoja 06.",
        "Tasa política": "Trae la tasa de la política declarada por la entidad (hoja 02) dividida para 100; sin política declarada, es cero.",
        "Provisión política": "Multiplica la exposición anclada por la tasa de la política declarada (hoja 02).",
        "Pérdida esperada": "Trae la pérdida esperada de la banda de la hoja 06.",
        "Diferencia": "Resta la provisión según la política de la pérdida esperada recalculada.",
    },
    "08_Conciliacion": {"Importe": ("Cada control cuadra su origen: C1 compara la matriz (hoja 05) con la cartera EEFF "
                                    "(hoja 02); C3 recompone el movimiento de la provisión (hoja 09) por ejercicio; la "
                                    "trazabilidad y la tasa de castigo remiten a su cálculo.")},
    "09_Movimiento": {
        "Saldo inicial": "Trae la provisión inicial del ejercicio de la hoja 02 (Parámetros).",
        "Constitución": "Trae la constitución del ejercicio (cargo a resultados) de la hoja 02 (Parámetros).",
        "Reversión": "Trae la reversión del ejercicio de la hoja 02 (Parámetros).",
        "Castigos": "Trae los castigos del ejercicio de la hoja 02 (Parámetros).",
        "Saldo final calculado": ("Parte de la provisión inicial, suma la constitución y resta la reversión y los "
                                  "castigos del ejercicio."),
        "Saldo según balance": "Trae el saldo de la provisión según el balance del ejercicio de la hoja 02 (Parámetros).",
    },
    "12_Detalle": {
        "Días de mora": "Resta la fecha de vencimiento de la fecha de corte (hoja 02); cero o menos aún no vence.",
        "Banda": "Clasifica la factura por sus días de mora en las bandas definidas.",
        "Clave": "Une el segmento y la banda (segmento|banda) para buscar su tasa y agruparla.",
        "Saldo": "Es el saldo del documento entregado por el cliente; la fila TOTAL suma los saldos del corte.",
    },
    "13_Cohorte_t2": {
        "Días de mora": "Resta la fecha de vencimiento de la fecha del corte t-2 (hoja 02).",
        "Banda": "Clasifica la factura en su banda de mora al corte t-2.",
        "Clave": "Une el segmento y la banda al corte t-2 (segmento|banda) para agruparla en la hoja 04.",
        "Saldo": "Es el saldo del documento al corte t-2 entregado por el cliente; la fila TOTAL suma los saldos.",
        "Remanente": "Busca la misma factura en el detalle del corte actual (hoja 12) y toma su saldo; cero si ya no está.",
    },
}

PANEL = {
    "poblacion": {"rotulo": "Cartera anclada a EEFF", "total": "cartera"},
    "recalculado": {"rotulo": "Pérdida esperada recalculada", "total": "pce"},
    "registrado": {"rotulo": "Provisión registrada", "total": "provisionRegistrada"},
    "composicion": {"rotulo": "Pérdida esperada por banda", "hoja": "06_Por_banda", "etiqueta": "Banda de mora",
                    "valor": "Pérdida esperada"},
    "distribucion": {"rotulo": "Cartera por banda", "hoja": "06_Por_banda", "etiqueta": "Banda de mora",
                     "valor": "Exposición anclada"},
}


def _rango(pref: str, col: str, n: int) -> str:
    return f"{pref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _banda_formula(celda: str, bandas: list) -> str:
    f = f'"{bandas[-1]["n"]}"'
    for b in reversed(bandas[:-1]):
        f = f'IF({celda}<={b["h"]},"{b["n"]}",{f})'
    return f'IF({celda}="","",{f})'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p = d["parametros"]
    t = {k: float(v) for k, v in res["totals"].items()}
    bandas, bn = d["bandas"], d["bn"]
    matriz, cohorte, exp, tasa = d["matriz"], d["cohorte"], d["exp"], d["tasa"]
    d2, dtl = d["cartera_t2"], res["rows"]
    nd, n2c, nmat = len(dtl), len(d2), len(matriz)
    fin_det, fin_coh, fin_mat = FILA0 + nd - 1, FILA0 + n2c - 1, FILA0 + nmat - 1
    nbanda = len(bn)
    # remanente en t de cada documento (saldo del mismo documento en el corte actual)
    saldo_t = {}
    for r in dtl:
        saldo_t[r["id"]] = saldo_t.get(r["id"], 0.0) + float(r["saldo"])

    # 02 · Parámetros
    parametros = [
        ["Corte del ejercicio (t)", d["cortes"]["t"], "Ficha del encargo"],
        ["Corte anterior (t-1)", d["cortes"]["t1"], "Un año antes"],
        ["Corte de la cohorte (t-2)", d["cortes"]["t2"], "Dos años antes; base de la ventana de 24 meses"],
        ["Umbral de incumplimiento (días)", float(d["umbral"]), "Definición interna de la entidad (M18)"],
        ["Texto de partes relacionadas", str(p.get("relKey") or "RELACIONAD"), "NIC 24"],
        ["Factor prospectivo — terceros", d["factores"]["NO-RELACIONADOS"], "NIIF 9 5.5.17(c)"],
        ["Factor prospectivo — relacionadas", d["factores"]["RELACIONADOS"], "NIIF 9 5.5.17(c)"],
        ["Cartera EEFF no relacionados (t)", d["eNR"], "Estados financieros / mayor"],
        ["Cartera EEFF relacionados (t)", d["eR"], "Estados financieros / mayor"],
        ["Cartera EEFF total (t)", fx(f"B{PARFILA['eNR_t']}+B{PARFILA['eR_t']}", n2(d["eNR"] + d["eR"])), "Ancla de la exposición"],
    ]
    fila_pol = {}
    for b in BANDAS:
        v = a_num(p.get(f"pol_{b['k']}"))
        if v is not None:
            fila_pol[b["n"]] = FILA0 + len(parametros)
            parametros.append([f"Política declarada · {b['n']} (%)", float(v), "Política de la entidad (B.2)"])
    # movimiento de la provisión (parámetros del auditor; las cédulas los referencian por fórmula)
    mov_fila = {}
    _et = {"t2": "t-2", "t1": "t-1", "t": "t"}
    for suf in ("t2", "t1", "t"):
        for k, lab in (("provIni", "Provisión inicial"), ("provCon", "Constitución"), ("provRev", "Reversión"),
                       ("provCas", "Castigos"), ("provBal", "Saldo según balance")):
            mov_fila[(suf, k)] = FILA0 + len(parametros)
            parametros.append([f"{lab} de la provisión ({_et[suf]})", _p(p, f"{k}_{suf}"), "Mayor de la provisión"])

    # 13 · Cohorte t-2 (población de la ventana)
    coh2 = []
    for i, r in enumerate(d2):
        fila = FILA0 + i
        coh2.append([r["doc"], r["cliente"], r["seg"], r["vence"].isoformat(),
                     fx(f'IF(D{fila}="","",{P}$B${PARFILA["corteT2"]}-D{fila})', r["dias"]),
                     fx(_banda_formula(f"E{fila}", bandas), r["banda"]),
                     fx(f'C{fila}&"|"&F{fila}', f'{r["seg"]}|{r["banda"]}'), n2(r["saldo"]),
                     fx(f"SUMIF({_rango(DET, 'A', nd)},A{fila},{_rango(DET, 'H', nd)})",
                        n2(saldo_t.get(r["doc"], 0.0)))])

    # 12 · Detalle corte t
    detalle = []
    for i, r in enumerate(dtl):
        fila = FILA0 + i
        detalle.append([r["id"], r["cliente"], r["segmento"], r["vence"],
                        fx(f'IF(D{fila}="","",{P}$B${PARFILA["corteT"]}-D{fila})', int(r["dias"]) if r["dias"] not in ("", None) else None),
                        fx(_banda_formula(f"E{fila}", bandas), r["banda"]),
                        fx(f'C{fila}&"|"&F{fila}', f'{r["segmento"]}|{r["banda"]}'), n2(float(r["saldo"]))])

    # 04 · Cohortes (tasa observada por segmento y banda)
    cohortes = []
    for i, mm in enumerate(matriz):
        fila = FILA0 + i
        c = cohorte[mm["seg"]][mm["banda"]]
        cohortes.append([mm["seg"], mm["banda"], mm["clave"],
                         fx(f"COUNTIF({_rango(COHS, 'G', n2c)},C{fila})", c["n"]),
                         fx(f"SUMIF({_rango(COHS, 'G', n2c)},C{fila},{_rango(COHS, 'H', n2c)})", n2(c["e"])),
                         fx(f"SUMIF({_rango(COHS, 'G', n2c)},C{fila},{_rango(COHS, 'I', n2c)})", n2(c["r"])),
                         fx(f'IF(E{fila}=0,"",F{fila}/E{fila})', mm["tasaObs"])])

    # 03 · Exposición anclada
    seg_total_fila = {}
    exposicion = []
    for i, mm in enumerate(matriz):
        fila = FILA0 + i
        ef = d["expFile"][mm["seg"]][mm["banda"]]
        segbase = d["expFileSeg"][mm["seg"]]
        eeff = d["eR"] if mm["seg"] == "RELACIONADOS" else d["eNR"]
        eeff_ref = f'{P}$B${PARFILA["eR_t"] if mm["seg"] == "RELACIONADOS" else PARFILA["eNR_t"]}'
        seg_rango = f'SUMIF({_rango(DET, "C", nd)},A{fila},{_rango(DET, "H", nd)})'
        factor_val = (eeff / segbase) if (d["anchor"] and segbase > 0) else 1.0
        factor_f = (f'IF(AND({P}$B${PARFILA["eTot"]}>0,{seg_rango}>0),{eeff_ref}/{seg_rango},1)')
        exp_arch = fx(f"SUMIF({_rango(DET, 'G', nd)},C{fila},{_rango(DET, 'H', nd)})", n2(ef))
        exposicion.append([mm["seg"], mm["banda"], mm["clave"], exp_arch, fx(factor_f, factor_val),
                           fx(f"D{fila}*E{fila}", n2(mm["exp"]))])

    # 05 · Matriz PCE
    matriz_rows = []
    for i, mm in enumerate(matriz):
        fila = FILA0 + i
        matriz_rows.append([mm["seg"], mm["banda"], mm["clave"],
                            fx(f"INDEX({EXPO}$F${FILA0}:$F${fin_mat},MATCH(C{fila},{EXPO}$C${FILA0}:$C${fin_mat},0))", n2(mm["exp"])),
                            fx(f"INDEX({COH}$G${FILA0}:$G${fin_mat},MATCH(C{fila},{COH}$C${FILA0}:$C${fin_mat},0))", mm["tasaObs"]),
                            fx(f'{P}$B${PARFILA["fR"] if mm["seg"] == "RELACIONADOS" else PARFILA["fT"]}', mm["factor"]),
                            fx(f'IF(E{fila}="",0,E{fila})*F{fila}', mm["tasaApl"]),
                            fx(f"D{fila}*G{fila}", n2(mm["pce"]))])

    # 06 · Por banda
    porbanda = []
    for i, b in enumerate(bn):
        fila = FILA0 + i
        e_b = sum(exp[s][b] for s in SEG)
        pce_b = sum(mm["pce"] for mm in matriz if mm["banda"] == b)
        porbanda.append([b, fx(f"SUMIF({_rango(MAT, 'B', nmat)},A{fila},{_rango(MAT, 'D', nmat)})", n2(e_b)),
                         fx(f"SUMIF({_rango(MAT, 'B', nmat)},A{fila},{_rango(MAT, 'I', nmat)})", n2(pce_b)),
                         fx(f'IF(B{fila}=0,"",C{fila}/B{fila})', (pce_b / e_b) if e_b else None)])
    fin_ban = FILA0 + nbanda - 1

    # 07 · Comparación con la política
    comparacion = []
    for i, pr in enumerate(d["polRows"]):
        fila = FILA0 + i
        pol_ref = fila_pol.get(pr["banda"])
        tasa_f = fx(f'{P}$B${pol_ref}/100', pr["tasa"]) if pol_ref else n2(pr["tasa"])
        comparacion.append([pr["banda"],
                            fx(f"INDEX({BAN}$B${FILA0}:$B${fin_ban},MATCH(A{fila},{BAN}$A${FILA0}:$A${fin_ban},0))", n2(pr["exp"])),
                            tasa_f, fx(f"B{fila}*C{fila}", n2(pr["prov"])),
                            fx(f"INDEX({BAN}$C${FILA0}:$C${fin_ban},MATCH(A{fila},{BAN}$A${FILA0}:$A${fin_ban},0))", n2(pr["pce"])),
                            fx(f"E{fila}-D{fila}", n2(pr["dif"]))])

    # 09 · Movimiento de la provisión
    movimiento = []
    etq = {"t2": "Ejercicio t-2", "t1": "Ejercicio t-1", "t": "Ejercicio t"}
    for i, mmm in enumerate(d["may"]):
        fila, suf = FILA0 + i, mmm["suf"]
        movimiento.append([etq[suf],
                           fx(f"{P}$B${mov_fila[(suf, 'provIni')]}", n2(mmm["ini"])),
                           fx(f"{P}$B${mov_fila[(suf, 'provCon')]}", n2(mmm["con"])),
                           fx(f"{P}$B${mov_fila[(suf, 'provRev')]}", n2(mmm["rev"])),
                           fx(f"{P}$B${mov_fila[(suf, 'provCas')]}", n2(mmm["cas"])),
                           fx(f"B{fila}+C{fila}-D{fila}-E{fila}", n2(mmm["fin"])),
                           fx(f"{P}$B${mov_fila[(suf, 'provBal')]}", n2(mmm["bal"]))])

    # 08 · Controles y conciliación
    MOV = ref("09_Movimiento")
    r_may_t = FILA0 + 2  # fila del ejercicio t en 09_Movimiento
    con_pce = f"SUM({_rango(MAT, 'I', nmat)})"
    con_cart = f"SUM({_rango(MAT, 'D', nmat)})"
    cont_ref = f"({P}$B${PARFILA['eNR_t']}+{P}$B${PARFILA['eR_t']})" if d["anchor"] else con_cart
    cont_val = (d["eNR"] + d["eR"]) if d["anchor"] else t["cartera"]
    cas_rango = _rango(MOV, "E", 3)
    coh_e_rango = _rango(COH, "E", nmat)
    conciliacion = [
        ["C1 · Σ matriz − cartera contabilizada (debe ser 0)",
         fx(f"{con_cart}-{cont_ref}", n2(t["cartera"] - cont_val))],
        ["C3 · Movimiento provisión t (ini+con−rev−cas−balance)",
         fx(f"{MOV}B{r_may_t}+{MOV}C{r_may_t}-{MOV}D{r_may_t}-{MOV}E{r_may_t}-{MOV}G{r_may_t}",
            n2(d["may"][2]["fin"] - d["may"][2]["bal"]))],
        ["Pérdida crediticia esperada total", fx(con_pce, n2(t["pce"]))],
        ["Provisión registrada al cierre",
         fx(f"{MOV}G{r_may_t}", n2(d["provReg"])) if d["may"][2]["bal"] else fx(f"{MOV}F{r_may_t}", n2(d["provReg"]))],
        ["Ajuste propuesto (PCE − provisión)", fx(f"{con_pce}-B{FILA0 + 3}", n2(t["ajuste"]))],
        ["Tasa de castigo sobre la cohorte",
         fx(f'IF(SUM({coh_e_rango})=0,"",SUM({cas_rango})/SUM({coh_e_rango}))', d["tasaCastigo"])],
        ["Trazabilidad de documentos t-2 → t (informativa)",
         fx(f'IF(COUNTA({_rango(COHS, "A", n2c)})=0,"",COUNTIF({_rango(COHS, "I", n2c)},">0")/COUNTA({_rango(COHS, "A", n2c)}))',
            (sum(1 for x in d2 if saldo_t.get(x["doc"], 0.0) > 0) / len(d2)) if d2 else None)],
    ]

    # 10 · Hallazgos (CCCEER)
    hall_cols = [["Código", "t"], ["Hallazgo", "t"], ["Riesgo", "t"], ["Condición", "t"], ["Criterio", "t"],
                 ["Causa", "t"], ["Efecto", "t"], ["Recomendación", "t"]]
    hall = [[h["code"], h["titulo"], h["riesgo"], h["condicion"], h["criterio"], h["causa"], h["efecto"], h["recomendacion"]]
            for h in d["hallazgos"]]
    if not hall:
        hall = [["—", "Sin hallazgos que reportar con los datos y parámetros cargados.", "", "", "", "", "", ""]]

    # 01 · Resumen
    resumen = [
        [res["labels"]["cartera"], fx(f"SUM({_rango(MAT, 'D', nmat)})", n2(t["cartera"]))],
        [res["labels"]["pce"], fx(f"SUM({_rango(MAT, 'I', nmat)})", n2(t["pce"]))],
        [res["labels"]["provisionRegistrada"], fx(f"'08_Conciliacion'!B{FILA0 + 3}", n2(t["provisionRegistrada"]))],
        [res["labels"]["ajuste"], fx(f"B{FILA0 + 1}-B{FILA0 + 2}", n2(t["ajuste"]))],
    ]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros,
             explica=EXPLICA["02_Parametros"]),
        hoja("03_Exposicion", "Exposición anclada a EEFF",
             [["Segmento", "t"], ["Banda de mora", "t"], ["Clave", "t"], ["Exposición del archivo", "n"],
              ["Factor de anclaje", "x"], ["Exposición anclada", "n"]], exposicion,
             ["TOTAL", "", "", None, None, suma("F", fin_mat, t["cartera"])], explica=EXPLICA["03_Exposicion"]),
        hoja("04_Cohortes", "Cohortes (ventana 24 meses)",
             [["Segmento", "t"], ["Banda de mora", "t"], ["Clave", "t"], ["Documentos", "i"],
              ["Exposición inicial", "n"], ["Remanente en t", "n"], ["Tasa observada", "p"]], cohortes,
             explica=EXPLICA["04_Cohortes"]),
        hoja("05_Matriz_PCE", "Matriz de pérdida esperada",
             [["Segmento", "t"], ["Banda de mora", "t"], ["Clave", "t"], ["Exposición anclada", "n"],
              ["Tasa observada", "p"], ["Factor prospectivo", "x"], ["Tasa aplicada", "p"], ["Pérdida esperada", "n"]],
             matriz_rows, ["TOTAL", "", "", suma("D", fin_mat, t["cartera"]), None, None, None, suma("I", fin_mat, t["pce"])],
             explica=EXPLICA["05_Matriz_PCE"]),
        hoja("06_Por_banda", "Pérdida por banda de mora",
             [["Banda de mora", "t"], ["Exposición anclada", "n"], ["Pérdida esperada", "n"], ["Tasa promedio", "p"]],
             porbanda, ["TOTAL", suma("B", fin_ban, t["cartera"]), suma("C", fin_ban, t["pce"]), None],
             explica=EXPLICA["06_Por_banda"]),
        hoja("07_Comparacion", "Comparación con la política",
             [["Banda de mora", "t"], ["Exposición anclada", "n"], ["Tasa política", "p"], ["Provisión política", "n"],
              ["Pérdida esperada", "n"], ["Diferencia", "n"]], comparacion,
             ["TOTAL", suma("B", fin_ban, t["cartera"]), None, suma("D", fin_ban, d["polTot"]),
              suma("E", fin_ban, t["pce"]), suma("F", fin_ban, t["pce"] - d["polTot"])],
             explica=EXPLICA["07_Comparacion"]),
        hoja("08_Conciliacion", "Controles y conciliación", [["Control", "t"], ["Importe", "n"]], conciliacion,
             explica=EXPLICA["08_Conciliacion"]),
        hoja("09_Movimiento", "Movimiento de la provisión",
             [["Ejercicio", "t"], ["Saldo inicial", "n"], ["Constitución", "n"], ["Reversión", "n"], ["Castigos", "n"],
              ["Saldo final calculado", "n"], ["Saldo según balance", "n"]], movimiento, explica=EXPLICA["09_Movimiento"]),
        hoja("10_Hallazgos", "Hallazgos (CCCEER)", hall_cols, hall, colores=["Riesgo"]),
        hoja("11_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
        hoja("12_Detalle", "Detalle de cartera al corte",
             [["Documento", "t"], ["Cliente", "t"], ["Segmento", "t"], ["Vencimiento", "d"], ["Días de mora", "i"],
              ["Banda", "t"], ["Clave", "t"], ["Saldo", "n"]], detalle,
             ["TOTAL", "", "", "", None, "", "", suma("H", fin_det, d["totFile"])], explica=EXPLICA["12_Detalle"]),
        hoja("13_Cohorte_t2", "Cohorte del corte t-2",
             [["Documento", "t"], ["Cliente", "t"], ["Segmento", "t"], ["Vencimiento", "d"], ["Días de mora", "i"],
              ["Banda", "t"], ["Clave", "t"], ["Saldo", "n"], ["Remanente", "n"]], coh2,
             ["TOTAL", "", "", "", None, "", "", suma("H", fin_coh, sum(x["saldo"] for x in d2)),
              suma("I", fin_coh, sum(saldo_t.get(x["doc"], 0.0) for x in d2))] if d2 else None,
             explica=EXPLICA["13_Cohorte_t2"]),
    ]


# --- REF_PROBLEMAS -----------------------------------------------------------

REF_PROBLEMAS = {
    "AJUSTE": ("01_Resumen", "Importe"),                        # PCE − provisión registrada
    "H-CARTERA-ANTIGUA": ("06_Por_banda", "Exposición anclada"),  # exposición de la banda de incumplimiento
    "W-SIN-DATOS": ("05_Matriz_PCE", "Exposición anclada"),
}


# --- definición (ficha AUD-ECL-01) -------------------------------------------

def definicion() -> dict:
    cartera = ("Una fila por documento: N° de documento, cliente, tipo (relacionadas), fecha de vencimiento y saldo; "
               "a nivel de documento, nunca consolidado por cliente; sin filas de total.")
    return {
        "name": "Pérdida crediticia esperada por cohortes (NIIF 9)",
        "area": "Cuentas por cobrar",
        "processor": "pce_cohortes_niif9",
        "frameworks": ["NIIF completas"],
        "summary": ("Recálculo independiente de la corrección de valor de las cuentas por cobrar comerciales con el "
                    "enfoque simplificado de la NIIF 9 (5.5.15): matriz de provisiones (B5.5.35) con tasas derivadas por "
                    "análisis de cohortes de ventana 24 meses (t-2 → t), exposición anclada a los estados financieros, "
                    "desdoblamiento de la banda de incumplimiento, ajuste prospectivo (5.5.17 c) y compuertas de "
                    "trazabilidad y validación contra castigos. Sin efecto fiscal (se deriva al módulo TAX)."),
        "source": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                   "document": "NIIF 9 · párr. 5.5.15, 5.5.17, 5.4.4, B5.5.35, B5.5.37, B5.5.51–B5.5.53; NIIF 7 35H, 35M, 35N",
                   "url": "https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/"},
        "nia": [
            {"document": "NIA 540 (Revisada)", "section": "párr. 13 y 17–30",
             "requirement": "Estimación contable: evaluar el método (matriz de cohortes), los datos (tres cortes y castigos) "
             "y los supuestos (factor prospectivo, tasas fijadas) y el posible sesgo."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad de los anexos de cartera contra el mayor y los EEFF."},
            {"document": "NIA 520", "section": "párr. 5", "requirement": "Procedimientos analíticos: rupturas de la curva de pérdida por banda."},
            {"document": "NIA 560", "section": "párr. 6", "requirement": "Cobros posteriores al cierre como evidencia sobre la estimación."},
        ],
        "calculo": [
            "Bandas de mora desde el vencimiento contractual y segmentos NO-RELACIONADOS / RELACIONADOS (B5.5.35).",
            "Desdoblamiento de la banda abierta en el umbral de incumplimiento para separar cartera gestionable de perdida (M18).",
            "Tasa observada por cohorte (ventana 24 meses) = remanente en t ÷ exposición inicial en t-2 (B5.5.35).",
            "Exposición anclada a la cartera contabilizada por segmento (factor = EEFF ÷ archivo).",
            "Factor prospectivo por segmento (5.5.17 c).",
            "PCE(s,b) = exposición anclada × tasa observada × factor; PCE total = Σ PCE.",
            "Compuertas: trazabilidad de documentos entre cortes, validación contra castigos (< 5 %), rupturas de la curva y hallazgos CCCEER.",
        ],
        "fields": _CARTERA, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS,
        "parametros": {k: v for k, v in PARAMETROS.items()},
        "etiquetas_parametros": ETIQUETAS_PARAM, "tramos": [{"k": b["k"], "tramo": b["n"]} for b in BANDAS],
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "ECL-01", "objective": "Integridad de la cartera", "risk": "Anexo incompleto o no conciliado con el mayor/EEFF",
             "assertion": "Integridad", "procedure": "Conciliar la cartera por documento de los tres cortes con el mayor y los EEFF",
             "evidence": "Cartera por documento (t-2, t-1, t), mayor y estados financieros",
             "criterion": "Diferencia dentro de tolerancia o explicada", "source": "NIA 500 párr. 9"},
            {"code": "ECL-02", "objective": "Trazabilidad", "risk": "Renumeración de documentos entre cortes",
             "assertion": "Exactitud", "procedure": "Medir la trazabilidad de documentos t-2 → t y evaluar el identificador",
             "evidence": "Universo de documentos por corte", "criterion": "Trazabilidad ≥ 80 %; método aplicable",
             "source": "NIIF 9 B5.5.35"},
            {"code": "ECL-03", "objective": "Tasas por cohorte", "risk": "Tasas sin sustento en la experiencia de pérdidas",
             "assertion": "Valoración", "procedure": "Medir por banda la fracción del saldo que no se resolvió en 24 meses",
             "evidence": "Cohorte t-2 y remanente en t", "criterion": "Tasa medida o fijada con sustento",
             "source": "NIIF 9 B5.5.35, B5.5.37 · NIA 540"},
            {"code": "ECL-04", "objective": "Validación del método", "risk": "La desaparición del documento se debe a castigo, no a cobro",
             "assertion": "Valoración", "procedure": "Contrastar la tasa de castigo de la cohorte contra el 5 %",
             "evidence": "Movimiento de la provisión (castigos)", "criterion": "Tasa de castigo < 5 % o castigos reasignados",
             "source": "NIIF 9 5.4.4 · NIA 540"},
            {"code": "ECL-05", "objective": "Información prospectiva", "risk": "Historia sin ajustar a condiciones futuras",
             "assertion": "Valoración", "procedure": "Evaluar los factores prospectivos por segmento y su sustento",
             "evidence": "Variables macro con fuente", "criterion": "Factor prospectivo documentado", "source": "NIIF 9 5.5.17(c)"},
            {"code": "ECL-06", "objective": "Medición y ajuste", "risk": "Corrección de valor mal medida",
             "assertion": "Valoración", "procedure": "Recalcular la PCE con la matriz anclada y compararla con la provisión registrada",
             "evidence": "Matriz y detalle", "criterion": "Ajuste cuantificado", "source": "NIIF 9 5.5.15, B5.5.35"},
        ],
        "requests": [
            req("RQ-001", "Análisis de antigüedad de cartera al corte t-2", "cartera_t2", "ECL-03",
                "Cohorte inicial de la ventana de 24 meses", content=cartera),
            req("RQ-002", "Análisis de antigüedad de cartera al corte t-1", "cartera_t1", "ECL-02",
                "Referencia de estabilidad de la cohorte", content=cartera),
            req("RQ-003", "Análisis de antigüedad de cartera al corte t (actual)", "cartera_t", "ECL-01",
                "Población a medir; se ancla y concilia", content=cartera),
            req("RQ-004", "Movimiento de la provisión de incobrables (tres ejercicios) y cartera según EEFF", None, "ECL-01",
                "Se digita en los parámetros: anclaje a la contabilidad y conciliación del movimiento (incluye castigos por año)",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-005", "Información prospectiva con fuente y política de crédito y cobranza", None, "ECL-05",
                "Sustento del factor prospectivo y de la política declarada", formats=("pdf", "docx"), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) ------------------------------------------------

def _ej(doc, cliente, tipo, vence, saldo):
    return {"id": doc, "cliente": cliente, "tipo": tipo, "vence": vence, "saldo": saldo, "_row": 2}


# Ejercicio modelo ficticio: «Comercial Andina de Ejemplo S.A.». Corte 2025-12-31,
# umbral 730, factores 1,000, sin desdoblamiento (7 bandas estándar). La cartera EEFF del
# corte iguala el archivo por segmento (anclaje con factor 1) para un control directo.
#
# Cohorte t-2 → t, banda «181 a 360 días»:
#   NO-RELACIONADOS: D1 (1000, sigue en t con 300) y D2 (1000, cobrado) → tasa 300/2000 = 15 %.
#   RELACIONADOS:    D3 (2000, sigue en t con 2000)                     → tasa 2000/2000 = 100 %.
# Cartera al corte t: D1 y D3 envejecen a «Más de 360 días» (sin tasa medida → W-SIN-DATOS y
#   H-CARTERA-ANTIGUA: baja = 300 + 2000 = 2300). Los créditos nuevos:
#   G1 (5000) en «181 a 360» NO-REL → PCE 5000 × 15 % = 750; G2 (4000) «0 a 30» sin tasa → 0.
#   PCE total = 750. Cartera al corte = 300 + 2000 + 5000 + 4000 = 11.300. Provisión 1000 →
#   ajuste 750 − 1000 = −250.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {
        "umbral": 730, "desdoblar": "No", "relKey": "RELACIONAD", "fT": 1.0, "fR": 1.0, "castiga": "No",
        "eNR_t": 9300, "eR_t": 2000,
        "provIni_t2": 1000, "provIni_t1": 1000, "provBal_t1": 1200,
        "provIni_t": 1000, "provBal_t": 1000,
        "pol_t360": 5,
    },
    "datasets": {
        "cartera_t2": [
            _ej("D1", "Cliente A", "NO-RELACIONADO", "2023-06-30", "1000"),
            _ej("D2", "Cliente B", "NO-RELACIONADO", "2023-06-30", "1000"),
            _ej("D3", "Relac X", "RELACIONADO", "2023-06-30", "2000"),
        ],
        "cartera_t1": [
            _ej("D1", "Cliente A", "NO-RELACIONADO", "2023-06-30", "600"),
            _ej("D3", "Relac X", "RELACIONADO", "2023-06-30", "2000"),
            _ej("G0", "Cliente D", "NO-RELACIONADO", "2024-11-30", "1500"),
        ],
        "cartera_t": [
            _ej("D1", "Cliente A", "NO-RELACIONADO", "2023-06-30", "300"),
            _ej("D3", "Relac X", "RELACIONADO", "2023-06-30", "2000"),
            _ej("G1", "Cliente E", "NO-RELACIONADO", "2025-06-30", "5000"),
            _ej("G2", "Cliente F", "NO-RELACIONADO", "2025-12-15", "4000"),
        ],
    },
}
ESCENARIOS = [("base", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"])]
