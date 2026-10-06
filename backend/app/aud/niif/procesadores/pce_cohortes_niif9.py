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

from datetime import date, timedelta

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
    campo("factura", "Fecha de facturación", "date", False,
          ["facturacion", "facturación", "emision", "emisión", "fecha factura", "fecha de emision",
           "fecha emision", "fecha de facturacion"], "2023-06-30"),
    campo("vence", "Fecha de vencimiento", "date", False,
          ["vencimiento", "vence", "venc", "fecha vencimiento"], "2023-11-15"),
    campo("saldo", "Saldo", "number", True,
          ["saldo", "cuentas por cobrar", "monto", "valor", "importe", "por cobrar"], "1000.00"),
    campo("ruc", "RUC / identificación", "text", False,
          ["ruc", "cedula", "identificacion", "codigo cliente"], ""),
]
_PROVISION = [
    campo("codigo", "Código", "text", True, ["codigo", "código", "cuenta", "cta", "codigo contable"], "1.1.03.02"),
    campo("descripcion", "Descripción", "text", True, ["descripcion", "descripción", "nombre", "detalle", "concepto"],
          "(-) Provisión cuentas incobrables"),
    campo("saldo_anterior", "Saldo año anterior", "number", True,
          ["saldo anterior", "año anterior", "ano anterior", "anterior", "saldo inicial", "inicial", "apertura"], "1000.00"),
    campo("saldo_actual", "Saldo año actual", "number", True,
          ["saldo actual", "año actual", "ano actual", "actual", "saldo final", "final", "cierre", "segun balance"], "900.00"),
]
_MAYOR = [
    campo("concepto", "Concepto / cuenta", "text", False, ["concepto", "cuenta", "detalle", "descripcion", "glosa"],
          "Constitución del ejercicio"),
    campo("constitucion", "Constitución (gasto)", "number", False,
          ["constitucion", "constitución", "dotacion", "dotación", "cargo", "gasto", "debe"], "0.00"),
    campo("reversion", "Reversión (recuperación)", "number", False,
          ["reversion", "reversión", "recuperacion", "recuperación", "abono", "haber"], "0.00"),
    campo("castigos", "Castigos / bajas", "number", False,
          ["castigo", "castigos", "baja", "bajas", "dado de baja", "write-off"], "0.00"),
]
CAMPOS = {"cartera": _CARTERA, "provision": _PROVISION, "mayor": _MAYOR}
# Obligatorios: 3 cortes de cartera (población) + anexo inicial de la provisión (sumaria con el
# saldo del año anterior y el actual → provisión inicial, registrada y ajuste).
# Opcionales: el mayor de la provisión de cada ejercicio (constitución, reversión, castigos).
# Si no se suben los mayores, se entiende que no hubo movimiento.
TIPOS = {"cartera_t2": "cartera", "cartera_t1": "cartera", "cartera_t": "cartera",
         "provision": "provision", "mayor_t2": "mayor", "mayor_t1": "mayor", "mayor_t": "mayor"}
DATASETS = tuple(TIPOS)
OPCIONALES = ("mayor_t2", "mayor_t1", "mayor_t")  # sin ellos → sin movimiento
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
    # política de crédito declarada por escrito (días). Si falta, se usa el promedio observado de la
    # cartera para imputar el vencimiento de las facturas que no lo traen.
    "polCredito": None,
    # cartera según EEFF — corte actual (no relacionados / relacionados); ancla de la exposición
    "eNR_t": None, "eR_t": None,
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
    "polCredito": "Política de crédito declarada (días; opcional)",
    "eNR_t": "Cartera EEFF no relacionados (corte actual)", "eR_t": "Cartera EEFF relacionados (corte actual)",
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


def _leer(filas: list, corte: date, rel_key: str, pol_credito: float | None = None) -> dict:
    """Depura una cartera como el artefacto: descarta sin documento/saldo, deduplica por documento
    (el primero gana), clasifica el segmento por el texto de tipo y calcula la mora.

    Novedad: cada factura puede traer la fecha de facturación. Los días de crédito concedidos
    (vencimiento − facturación) dan una política de crédito promedio (simple) que, en las facturas
    SIN fecha de vencimiento, se usa para imputarla (vencimiento = facturación + días de crédito):
    `pol_credito` (política declarada por el auditor) manda; si no hay, se usa el promedio observado.
    """
    # Primera pasada: parseo y política de crédito observada (promedio simple de vencidas con ambas fechas).
    base, dup, bad, vistos, creditos = [], 0, 0, set(), []
    for f in filas or []:
        doc = str(f.get("id", "") or "").strip()
        saldo = a_num(f.get("saldo"))
        saldo = 0.0 if saldo is None else float(saldo)
        factura = a_fecha(f.get("factura"))
        vence = a_fecha(f.get("vence"))
        if not doc or abs(saldo) < 0.005:
            if doc or saldo:
                bad += 1
            continue
        if doc in vistos:
            dup += 1
            continue
        vistos.add(doc)
        if factura is not None and vence is not None:
            creditos.append((vence - factura).days)
        base.append((f, doc, saldo, factura, vence))

    pol_obs = round(sum(creditos) / len(creditos)) if creditos else None
    impute = pol_credito if (pol_credito is not None) else pol_obs   # días para imputar el vencimiento

    # Segunda pasada: imputa el vencimiento faltante, calcula mora y días de crédito por factura.
    rows, imputados = [], 0
    for f, doc, saldo, factura, vence in base:
        venc_imp = False
        if vence is None:
            if factura is not None and impute is not None:
                vence = factura + timedelta(days=int(impute))
                venc_imp = True
                imputados += 1
            else:
                bad += 1
                continue
        tipo = str(f.get("tipo", "") or "").upper()
        rel = rel_key in tipo and ("NO-" + rel_key) not in tipo and ("NO " + rel_key) not in tipo
        dias_credito = (vence - factura).days if factura is not None else None
        rows.append({"doc": doc, "cliente": str(f.get("cliente", "") or "").strip() or "(sin nombre)",
                     "saldo": saldo, "factura": factura, "vence": vence, "dias": (corte - vence).days,
                     "diasCredito": dias_credito, "vencImputado": venc_imp,
                     "seg": "RELACIONADOS" if rel else "NO-RELACIONADOS",
                     "ruc": str(f.get("ruc", "") or "").strip(), "_row": f.get("_row")})
    return {"rows": rows, "dup": dup, "bad": bad, "polObs": pol_obs, "imputados": imputados}


def _p(p, k):
    v = a_num(p.get(k))
    return 0.0 if v is None else float(v)


def _leer_provision(filas: list) -> list:
    """Anexo inicial de la provisión (sumaria): código, descripción, saldo anterior y actual."""
    out = []
    for f in filas or []:
        cod = str(f.get("codigo", "") or "").strip()
        desc = str(f.get("descripcion", "") or "").strip()
        ant = a_num(f.get("saldo_anterior"))
        act = a_num(f.get("saldo_actual"))
        if not cod and not desc and ant is None and act is None:
            continue
        out.append({"codigo": cod, "descripcion": desc or "(sin descripción)",
                    "anterior": 0.0 if ant is None else float(ant),
                    "actual": 0.0 if act is None else float(act), "_row": f.get("_row")})
    return out


def _sumar_mayor(filas: list) -> dict:
    """Suma el movimiento del mayor de un ejercicio (constitución, reversión, castigos).
    Mayor opcional: sin filas → todo en cero (sin movimiento)."""
    con = rev = cas = 0.0
    for f in filas or []:
        con += a_num(f.get("constitucion")) or 0.0
        rev += a_num(f.get("reversion")) or 0.0
        cas += a_num(f.get("castigos")) or 0.0
    return {"con": con, "rev": rev, "cas": cas}


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_t = a_fecha(corte)
    if corte_t is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    if not datasets.get("cartera_t2") or not datasets.get("cartera_t1") or not datasets.get("cartera_t"):
        raise ValueError("Cargue los tres análisis de antigüedad de cartera (t-2, t-1 y t). "
                         "Sin tres cierres no existe una cohorte con ventana completa de 24 meses.")
    if not datasets.get("provision"):
        raise ValueError("Cargue el anexo inicial de la provisión (sumaria con el saldo del año anterior "
                         "y el actual) para medir el ajuste.")
    corte_t1 = _hace_n_anios(corte_t, 1)
    corte_t2 = _hace_n_anios(corte_t, 2)
    rel_key = str(p.get("relKey") or "RELACIONAD").upper()
    umbral = int(_p(p, "umbral") or 730)
    bandas = _bandas_efectivas(umbral, _es_desdoblar(p.get("desdoblar")))
    bn = [b["n"] for b in bandas]

    # política de crédito declarada (días) para imputar vencimientos faltantes; si no, el promedio observado
    pol_credito = a_num(p.get("polCredito"))
    pol_credito = float(pol_credito) if pol_credito is not None else None
    # depuración de los tres cortes
    d2 = _leer(datasets.get("cartera_t2"), corte_t2, rel_key, pol_credito)
    d1 = _leer(datasets.get("cartera_t1"), corte_t1, rel_key, pol_credito)
    dt = _leer(datasets.get("cartera_t"), corte_t, rel_key, pol_credito)
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

    # anexo inicial de la provisión (sumaria): saldo del año anterior y el actual
    prov_sumaria = _leer_provision(datasets.get("provision"))
    prov_ini = sum(x["anterior"] for x in prov_sumaria)
    prov_reg = sum(x["actual"] for x in prov_sumaria)

    # movimiento de la provisión — mayores opcionales (sin ellos → sin movimiento)
    may = []
    for suf in ("t2", "t1", "t"):
        mv = _sumar_mayor(datasets.get(f"mayor_{suf}"))
        may.append({"suf": suf, "con": mv["con"], "rev": mv["rev"], "cas": mv["cas"]})
    cargo_acum = sum(mmm["con"] for mmm in may)
    rev_acum = sum(mmm["rev"] for mmm in may)
    cast_acum = sum(mmm["cas"] for mmm in may)
    fin_mov = prov_ini + cargo_acum - rev_acum - cast_acum   # cierre según el movimiento
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
    n_imp = sum(dd["imputados"] for dd in (d2, d1, dt))
    if n_imp:
        fuente = (f"la política de crédito declarada ({int(pol_credito)} días)" if pol_credito is not None
                  else f"la política de crédito promedio observada ({dt['polObs']} días)")
        ex.append(problema("W-VENCIMIENTO-IMPUTADO", f"{n_imp} factura(s) sin fecha de vencimiento: se imputó con "
                           f"{fuente} (vencimiento = facturación + días de crédito). Confirme el vencimiento real "
                           "con la factura o el contrato; la banda de mora de esas facturas depende de este supuesto.", 0))
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

    # Hallazgos CCCEER (los disparadores del artefacto)
    hallazgos = _hallazgos(prov_ini, prov_reg, fin_mov, cargo_acum, cast_acum, pol_rows, pce_total, pol_tot,
                           baja, tot_exp, umbral, tasa_def, ff, tasa, bn, str(p.get("castiga") or ""), (d2, d1, dt))
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
                      "factura": r["factura"].isoformat() if r["factura"] else "",
                      "vence": r["vence"].isoformat(), "vencImputado": r["vencImputado"],
                      "diasCredito": r["diasCredito"], "dias": str(r["dias"]), "banda": r["banda"],
                      "saldo": r2(r["saldo"]), "_row": r["_row"]})

    totals = {"cartera": r2(tot_exp), "pce": r2(pce_total), "provisionRegistrada": r2(prov_reg), "ajuste": r2(ajuste)}
    labels = {"cartera": "Cartera anclada a EEFF", "pce": "Pérdida crediticia esperada",
              "provisionRegistrada": "Provisión registrada", "ajuste": "Ajuste propuesto"}
    detalle = {
        "cortes": {"t": corte_t.isoformat(), "t1": corte_t1.isoformat(), "t2": corte_t2.isoformat()},
        "bandas": bandas, "bn": bn, "umbral": umbral, "traza": traza, "anchor": anchor,
        "factorAnclaje": factor_anclaje, "expFileSeg": exp_file_seg,
        "matriz": matriz, "cohorte": co, "exp": exp, "expFile": exp_file, "tasa": tasa,
        "polRows": pol_rows, "polTot": pol_tot, "may": may, "provReg": prov_reg, "provIni": prov_ini,
        "provSumaria": prov_sumaria, "revAcum": rev_acum, "finMov": fin_mov,
        "cargoAcum": cargo_acum, "castAcum": cast_acum, "cohorteBase": cohorte_base, "tasaCastigo": tasa_castigo,
        "baja": baja, "totFile": tot_file, "totExp": tot_exp, "eNR": e_nr, "eR": e_r, "factores": ff,
        "cartera_t2": d2["rows"], "cartera_t1": d1["rows"], "hallazgos": hallazgos, "parametros": p,
        "dup": {"t2": d2["dup"], "t1": d1["dup"], "t": dt["dup"]},
        "polCredito": pol_credito, "polObs": dt["polObs"], "imputados": n_imp,
    }
    return {"engine": VERSION, "rows": filas, "totals": totals, "labels": labels, "primary": "ajuste",
            "exceptions": ex, "schedule": [], "detalle": detalle}


def _hallazgos(prov_ini, prov_reg, fin_mov, cargo_acum, cast_acum, pol_rows, pce_total, pol_tot, baja, tot_exp, umbral,
               tasa_def, ff, tasa, bn, castiga, dups) -> list:
    """Los hallazgos CCCEER del artefacto, con sus mismos disparadores."""
    H = []
    if cargo_acum == 0 and prov_ini > 0:
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
    if abs(fin_mov - prov_reg) > 0.5:
        H.append({"code": "H-NOTA-INCONSISTENTE", "titulo": "El movimiento de la provisión no explica el saldo registrado",
                  "riesgo": "Alto",
                  "condicion": f"La provisión del año anterior ({money(prov_ini)}) más el movimiento de los mayores arroja "
                  f"{money(fin_mov)}, pero el anexo inicial registra un saldo actual de {money(prov_reg)}; "
                  f"diferencia de {money(fin_mov - prov_reg)}.",
                  "criterio": "NIC 1: la información de las notas debe ser consistente con los importes de los estados principales.",
                  "causa": "Falta movimiento (no se cargaron los mayores) o el movimiento no cuadra con el cambio del saldo.",
                  "efecto": "El cambio de la provisión no queda explicado por el movimiento del ejercicio.",
                  "recomendacion": "Cargar el mayor de la provisión o conciliar el movimiento con el saldo del balance.",
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
    ("14_Anexo_inicial", "Anexo inicial de la provisión"), ("15_Movimiento_mayores", "Movimiento del mayor por ejercicio"),
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
    "02_Parametros": {"Valor": ("Son datos del encargo o juicio del auditor; la exposición EEFF total suma los importes "
                                "de clientes no relacionados y relacionados del corte, la política de crédito observada "
                                "promedia los días de crédito del detalle (hoja 12) y la usada toma la declarada o, si "
                                "no hay, la observada.")},
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
                                    "(hoja 02); C3 confronta la provisión según el movimiento con la registrada (hoja 09); "
                                    "la trazabilidad y la tasa de castigo remiten a su cálculo.")},
    "09_Movimiento": {"Importe": ("Reconstruye la provisión: parte del saldo del año anterior del anexo inicial (hoja 14), "
                                  "suma la constitución y resta la reversión y los castigos del movimiento del mayor "
                                  "(hoja 15), y confronta el resultado con la provisión registrada del año actual "
                                  "(hoja 14). Sin mayores cargados, el movimiento es cero y el saldo no cambia.")},
    "14_Anexo_inicial": {},
    "15_Movimiento_mayores": {},
    "12_Detalle": {
        "Vencimiento": ("Es la fecha de vencimiento entregada por el cliente; si la factura no la trae, se imputa "
                        "como facturación + política de crédito usada (hoja 02, «usada para imputar»)."),
        "Días de crédito": ("Resta la facturación del vencimiento: el plazo de crédito concedido en esa factura. "
                            "En las facturas con vencimiento imputado queda en blanco (no es un plazo observado)."),
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
    # Política de crédito (días): declarada por el auditor, observada (promedio de los días de crédito del
    # detalle) y la usada para imputar el vencimiento faltante (la declarada manda; si no, la observada).
    f_decl = FILA0 + len(parametros)
    parametros.append(["Política de crédito declarada (días)",
                       float(d["polCredito"]) if d["polCredito"] is not None else "",
                       "Política de crédito por escrito de la entidad (opcional)"])
    f_obs = FILA0 + len(parametros)
    parametros.append(["Política de crédito observada (días, promedio)",
                       fx(f'IFERROR(ROUND(AVERAGEIF({_rango(DET, "F", nd)},">=0"),0),"")', d["polObs"] if d["polObs"] is not None else ""),
                       "Promedio simple de los días de crédito (vencimiento − facturación) del detalle"])
    f_usada = FILA0 + len(parametros)
    parametros.append(["Política de crédito usada para imputar (días)",
                       fx(f'IF(B{f_decl}="",B{f_obs},B{f_decl})',
                          (d["polCredito"] if d["polCredito"] is not None else d["polObs"]) or ""),
                       "La declarada manda; si no hay, la observada (NIA 520)"])
    fila_pol = {}
    for b in BANDAS:
        v = a_num(p.get(f"pol_{b['k']}"))
        if v is not None:
            fila_pol[b["n"]] = FILA0 + len(parametros)
            parametros.append([f"Política declarada · {b['n']} (%)", float(v), "Política de la entidad (B.2)"])

    # 13 · Cohorte t-2 (población de la ventana)
    coh2 = []
    for i, r in enumerate(d2):
        fila = FILA0 + i
        coh2.append([r["doc"], r["cliente"], r["seg"], r["vence"].isoformat(),
                     fx(f'IF(D{fila}="","",{P}$B${PARFILA["corteT2"]}-D{fila})', r["dias"]),
                     fx(_banda_formula(f"E{fila}", bandas), r["banda"]),
                     fx(f'C{fila}&"|"&F{fila}', f'{r["seg"]}|{r["banda"]}'), n2(r["saldo"]),
                     fx(f"SUMIF({_rango(DET, 'A', nd)},A{fila},{_rango(DET, 'J', nd)})",
                        n2(saldo_t.get(r["doc"], 0.0)))])

    # 12 · Detalle corte t — con facturación, días de crédito y vencimiento imputado cuando falta
    detalle = []
    for i, r in enumerate(dtl):
        fila = FILA0 + i
        # Vencimiento: imputado (= facturación + política usada) por fórmula, o el dato del cliente.
        if r.get("vencImputado"):
            venc_cell = fx(f'D{fila}+{P}$B${f_usada}', r["vence"])
            dc_cell = ""   # imputado: no es un plazo observado, no entra en el promedio
        else:
            venc_cell = r["vence"]
            dc_cell = fx(f'IF(OR(D{fila}="",E{fila}=""),"",E{fila}-D{fila})', r["diasCredito"]) if r.get("factura") else ""
        detalle.append([r["id"], r["cliente"], r["segmento"], r.get("factura") or "", venc_cell, dc_cell,
                        fx(f'IF(E{fila}="","",{P}$B${PARFILA["corteT"]}-E{fila})', int(r["dias"]) if r["dias"] not in ("", None) else None),
                        fx(_banda_formula(f"G{fila}", bandas), r["banda"]),
                        fx(f'C{fila}&"|"&H{fila}', f'{r["segmento"]}|{r["banda"]}'), n2(float(r["saldo"]))])

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
        seg_rango = f'SUMIF({_rango(DET, "C", nd)},A{fila},{_rango(DET, "J", nd)})'
        factor_val = (eeff / segbase) if (d["anchor"] and segbase > 0) else 1.0
        factor_f = (f'IF(AND({P}$B${PARFILA["eTot"]}>0,{seg_rango}>0),{eeff_ref}/{seg_rango},1)')
        exp_arch = fx(f"SUMIF({_rango(DET, 'I', nd)},C{fila},{_rango(DET, 'J', nd)})", n2(ef))
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

    # 14 · Anexo inicial de la provisión (sumaria): código, descripción, saldo anterior y actual
    prov = d["provSumaria"]
    npv = max(len(prov), 1)
    anexo = [[x["codigo"], x["descripcion"], n2(x["anterior"]), n2(x["actual"])] for x in prov] \
        or [["", "(sin datos)", n2(0), n2(0)]]
    fin_pv = FILA0 + npv - 1
    ANEXO = ref("14_Anexo_inicial")
    anexo_total = ["TOTAL", "", suma("C", fin_pv, d["provIni"]), suma("D", fin_pv, d["provReg"])]
    fila_tot_pv = FILA0 + npv            # fila de la fila TOTAL del anexo
    ref_ini = f"{ANEXO}C{fila_tot_pv}"   # provisión del año anterior (TOTAL)
    ref_reg = f"{ANEXO}D{fila_tot_pv}"   # provisión del año actual = registrada (TOTAL)

    # 15 · Movimiento del mayor de la provisión por ejercicio (opcional; sin mayores → sin movimiento)
    etq = {"t2": "Año 1 (t-2)", "t1": "Año 2 (t-1)", "t": "Año 3 (t)"}
    mayores = [[etq[mmm["suf"]], n2(mmm["con"]), n2(mmm["rev"]), n2(mmm["cas"])] for mmm in d["may"]]
    fin_may = FILA0 + len(mayores) - 1
    MAY = ref("15_Movimiento_mayores")
    mayores_total = ["TOTAL", suma("B", fin_may, d["cargoAcum"]), suma("C", fin_may, d["revAcum"]),
                     suma("D", fin_may, d["castAcum"])]
    fila_tot_may = FILA0 + len(mayores)
    con_may, rev_may, cas_may = (f"{MAY}B{fila_tot_may}", f"{MAY}C{fila_tot_may}", f"{MAY}D{fila_tot_may}")

    # 09 · Movimiento de la provisión (reconciliación: año anterior + movimiento = registrada)
    movimiento = [
        ["Provisión al año anterior", fx(ref_ini, n2(d["provIni"]))],
        ["(+) Constitución del período", fx(con_may, n2(d["cargoAcum"]))],
        ["(−) Reversión del período", fx(rev_may, n2(d["revAcum"]))],
        ["(−) Castigos del período", fx(cas_may, n2(d["castAcum"]))],
        ["Provisión según el movimiento", fx(f"B{FILA0}+B{FILA0 + 1}-B{FILA0 + 2}-B{FILA0 + 3}", n2(d["finMov"]))],
        ["Provisión registrada (año actual)", fx(ref_reg, n2(d["provReg"]))],
        ["Diferencia (movimiento − registrada)", fx(f"B{FILA0 + 4}-B{FILA0 + 5}", n2(d["finMov"] - d["provReg"]))],
    ]
    MOV = ref("09_Movimiento")

    # 08 · Controles y conciliación
    con_pce = f"SUM({_rango(MAT, 'I', nmat)})"
    con_cart = f"SUM({_rango(MAT, 'D', nmat)})"
    cont_ref = f"({P}$B${PARFILA['eNR_t']}+{P}$B${PARFILA['eR_t']})" if d["anchor"] else con_cart
    cont_val = (d["eNR"] + d["eR"]) if d["anchor"] else t["cartera"]
    coh_e_rango = _rango(COH, "E", nmat)
    conciliacion = [
        ["C1 · Σ matriz − cartera contabilizada (debe ser 0)",
         fx(f"{con_cart}-{cont_ref}", n2(t["cartera"] - cont_val))],
        ["C3 · Movimiento vs. provisión registrada (debe ser 0)",
         fx(f"{MOV}B{FILA0 + 4}-{MOV}B{FILA0 + 5}", n2(d["finMov"] - d["provReg"]))],
        ["Pérdida crediticia esperada total", fx(con_pce, n2(t["pce"]))],
        ["Provisión registrada al cierre", fx(ref_reg, n2(d["provReg"]))],
        ["Ajuste propuesto (PCE − provisión)", fx(f"{con_pce}-{ref_reg}", n2(t["ajuste"]))],
        ["Tasa de castigo sobre la cohorte",
         fx(f'IF(SUM({coh_e_rango})=0,"",{MAY}D{fila_tot_may}/SUM({coh_e_rango}))', d["tasaCastigo"])],
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
        hoja("09_Movimiento", "Movimiento de la provisión", [["Concepto", "t"], ["Importe", "n"]], movimiento,
             explica=EXPLICA["09_Movimiento"]),
        hoja("10_Hallazgos", "Hallazgos (CCCEER)", hall_cols, hall, colores=["Riesgo"]),
        hoja("11_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
        hoja("12_Detalle", "Detalle de cartera al corte",
             [["Documento", "t"], ["Cliente", "t"], ["Segmento", "t"], ["Fecha de facturación", "d"],
              ["Vencimiento", "d"], ["Días de crédito", "i"], ["Días de mora", "i"],
              ["Banda", "t"], ["Clave", "t"], ["Saldo", "n"]], detalle,
             ["TOTAL", "", "", "", "", None, None, "", "", suma("J", fin_det, d["totFile"])],
             explica=EXPLICA["12_Detalle"]),
        hoja("13_Cohorte_t2", "Cohorte del corte t-2",
             [["Documento", "t"], ["Cliente", "t"], ["Segmento", "t"], ["Vencimiento", "d"], ["Días de mora", "i"],
              ["Banda", "t"], ["Clave", "t"], ["Saldo", "n"], ["Remanente", "n"]], coh2,
             ["TOTAL", "", "", "", None, "", "", suma("H", fin_coh, sum(x["saldo"] for x in d2)),
              suma("I", fin_coh, sum(saldo_t.get(x["doc"], 0.0) for x in d2))] if d2 else None,
             explica=EXPLICA["13_Cohorte_t2"]),
        hoja("14_Anexo_inicial", "Anexo inicial de la provisión",
             [["Código", "t"], ["Descripción", "t"], ["Saldo año anterior", "n"], ["Saldo año actual", "n"]], anexo,
             anexo_total, explica=EXPLICA["14_Anexo_inicial"]),
        hoja("15_Movimiento_mayores", "Movimiento del mayor por ejercicio",
             [["Ejercicio", "t"], ["Constitución", "n"], ["Reversión", "n"], ["Castigos", "n"]], mayores,
             mayores_total, explica=EXPLICA["15_Movimiento_mayores"]),
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
        "name": "Pérdida crediticia esperada (NIIF 9)",
        "area": "Cuentas por cobrar",
        "processor": "pce_cohortes_niif9",
        "principal": PRINCIPAL,   # anexo de cartera del ejercicio corriente (guard de «Procesar» en el frontend)
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
            req("RQ-001", "Cartera — Año 1 (t-2, el más antiguo)", "cartera_t2", "ECL-03",
                "Cohorte inicial de la ventana de 24 meses", content=cartera),
            req("RQ-002", "Cartera — Año 2 (t-1)", "cartera_t1", "ECL-02",
                "Referencia de estabilidad de la cohorte", content=cartera),
            req("RQ-003", "Cartera — Año 3 (t, corte actual)", "cartera_t", "ECL-01",
                "Población a medir; se ancla y concilia", content=cartera),
            req("RQ-004", "Anexo inicial de la provisión (sumaria)", "provision", "ECL-06",
                "Saldo de la provisión del año anterior y del actual → provisión inicial, registrada y ajuste",
                content="Una sumaria: Código · Descripción · Saldo año anterior · Saldo año actual (una fila por cuenta de provisión)."),
            req("RQ-005", "Mayor de la provisión — Año 1 (t-2)", "mayor_t2", "ECL-04",
                "Movimiento del ejercicio (constitución, reversión, castigos). Opcional: sin él, sin movimiento",
                required=False,
                content="Una tabla: Concepto · Constitución · Reversión · Castigos (una o varias filas; se suman)."),
            req("RQ-006", "Mayor de la provisión — Año 2 (t-1)", "mayor_t1", "ECL-04",
                "Movimiento del ejercicio. Opcional: sin él, sin movimiento", required=False,
                content="Una tabla: Concepto · Constitución · Reversión · Castigos."),
            req("RQ-007", "Mayor de la provisión — Año 3 (t)", "mayor_t", "ECL-04",
                "Movimiento del ejercicio. Opcional: sin él, sin movimiento", required=False,
                content="Una tabla: Concepto · Constitución · Reversión · Castigos."),
            req("RQ-008", "Información prospectiva con fuente y política de crédito y cobranza", None, "ECL-05",
                "Sustento del factor prospectivo y de la política declarada", formats=("pdf", "docx"), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) ------------------------------------------------

def _ej(doc, cliente, tipo, vence, saldo, factura=""):
    return {"id": doc, "cliente": cliente, "tipo": tipo, "factura": factura, "vence": vence, "saldo": saldo, "_row": 2}


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
def _mov(concepto, con=0, rev=0, cas=0):
    return {"concepto": concepto, "constitucion": con, "reversion": rev, "castigos": cas, "_row": 2}


EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {
        "umbral": 730, "desdoblar": "No", "relKey": "RELACIONAD", "fT": 1.0, "fR": 1.0, "castiga": "No",
        "eNR_t": 9300, "eR_t": 2000, "pol_t360": 5,
    },
    "datasets": {
        "cartera_t2": [
            _ej("D1", "Cliente A", "NO-RELACIONADO", "2023-06-30", "1000", "2023-03-31"),
            _ej("D2", "Cliente B", "NO-RELACIONADO", "2023-06-30", "1000", "2023-03-31"),
            _ej("D3", "Relac X", "RELACIONADO", "2023-06-30", "2000", "2023-03-31"),
        ],
        "cartera_t1": [
            _ej("D1", "Cliente A", "NO-RELACIONADO", "2023-06-30", "600", "2023-03-31"),
            _ej("D3", "Relac X", "RELACIONADO", "2023-06-30", "2000", "2023-03-31"),
            _ej("G0", "Cliente D", "NO-RELACIONADO", "2024-11-30", "1500", "2024-08-31"),
        ],
        "cartera_t": [
            _ej("D1", "Cliente A", "NO-RELACIONADO", "2023-06-30", "300", "2023-03-31"),
            _ej("D3", "Relac X", "RELACIONADO", "2023-06-30", "2000", "2023-03-31"),
            _ej("G1", "Cliente E", "NO-RELACIONADO", "2025-06-30", "5000", "2025-03-31"),
            _ej("G2", "Cliente F", "NO-RELACIONADO", "2025-12-15", "4000", "2025-09-15"),
        ],
        # Anexo inicial de la provisión (sumaria): saldo del año anterior y el actual.
        "provision": [
            {"codigo": "1.1.03.02", "descripcion": "(-) Provisión cuentas incobrables",
             "saldo_anterior": "1000", "saldo_actual": "1000", "_row": 2},
        ],
        # Mayores opcionales: sin movimiento en el ejemplo (fin = saldo anterior = saldo actual).
        "mayor_t2": [_mov("Sin movimiento en el ejercicio")],
        "mayor_t1": [_mov("Sin movimiento en el ejercicio")],
        "mayor_t": [_mov("Sin movimiento en el ejercicio")],
    },
}
ESCENARIOS = [("base", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"])]
