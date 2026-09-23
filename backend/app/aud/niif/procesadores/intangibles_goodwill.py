"""Activos intangibles y goodwill (NIC 38 · NIC 36 · NIIF 3 · NIIF para las PYMES secciones 18, 19 y 27).

Versión simple que cumple la norma, una cédula por prueba de la matriz del socio (MÓDULO 07):

1. Reconocimiento e investigación/desarrollo: la investigación nunca se capitaliza (NIC 38.54; PYMES 18.14);
   el desarrollo se capitaliza en NIIF completas solo si cumple NIC 38.57 y en PYMES va siempre a gasto
   (18.14). Lo no capitalizable se da de baja: su neto auditado es cero.
2. Amortización (NIC 38.97; PYMES 18.21-18.22): amortizable = costo − residual; amortización del año =
   amortizable ÷ vida (meses) × meses en uso del ejercicio (meses completos, el mes de disponibilidad cuenta
   entero), sin pasar del importe pendiente (amortizable − amortización acumulada − deterioro acumulado).
3. Vida finita / indefinida: en NIIF completas un intangible sin vida (en blanco) es de vida indefinida y el
   goodwill no se amortiza (NIC 38.107; NIIF 3.B63 a); ambos exigen prueba anual de deterioro (NIC 36.10, 36.90).
   En PYMES todo intangible y el goodwill tienen vida finita (18.19); si no puede establecerse con fiabilidad se
   usa la mejor estimación de la gerencia, que no excederá de diez años (18.20; 19.23 en 2015 / 19.34 en 2025):
   los diez años (parámetro `vidaMaxPymes`) son el TOPE de esa estimación, no una vida por defecto. Sin estimación
   la partida no se amortiza (importe vacío) y se pide a la gerencia; si la vida viene y excede el tope, se limita.
4. Revisión de vida útil y valor residual: meses transcurridos, vida remanente, amortización acumulada esperada
   vs recalculada, residual distinto de cero (NIC 38.100; PYMES 18.23) y revisión anual (NIC 38.104, 38.109).
5. Deterioro: recuperable = MAX(valor en uso, VR menos costos de disposición) (NIC 36.18; PYMES 27.11);
   deterioro = MAX(importe en libros − recuperable, 0) (NIC 36.59; PYMES 27.5).
6. Reversión: solo con indicio y nunca en goodwill (NIC 36.114, 36.117, 36.124; PYMES 27.28-27.30);
   reversión = MIN(recuperable − importe en libros, deterioro acumulado previo).
7. Ajuste propuesto = neto auditado − neto según el mayor.
Todo importe del Excel es una fórmula que remite a Parámetros y a la hoja del auxiliar.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m, problema, r2, ref, req,
    validar_campos, validar_definicion_generica,
)

VERSION = "intangibles_goodwill 1.0"
RUBRO = "INTANGIBLES"

_INTANGIBLES = [
    campo("id", "Código del intangible", alias=("codigo", "código", "activo", "cuenta"), ejemplo="SW-01"),
    campo("descripcion", "Descripción", alias=("detalle", "nombre"), ejemplo="Software ERP"),
    campo("tipo", "Tipo (software, licencia, marca, desarrollo, investigación, goodwill, otro)",
          alias=("clase", "tipo de intangible", "categoria"), ejemplo="Software"),
    campo("fase", "Fase del proyecto interno (investigación / desarrollo)", requerido=False, alias=("fase proyecto", "etapa"), ejemplo=""),
    campo("cumple_57", "Desarrollo: cumple los criterios de NIC 38.57 (Sí / No)", requerido=False,
          alias=("cumple 57", "criterios 57", "cumple criterios"), ejemplo=""),
    campo("fecha_disponible", "Fecha disponible para su uso", "date", requerido=False,
          alias=("fecha de uso", "fecha disponible", "fecha inicio amortizacion", "fecha adquisicion"), ejemplo="2023-01-01"),
    campo("costo", "Costo", "number", alias=("costo historico", "valor", "costo inicial"), ejemplo=60000),
    campo("residual", "Valor residual", "number", requerido=False, alias=("valor residual", "residual"), ejemplo=0),
    campo("vida_meses", "Vida útil (meses; en blanco = indefinida)", "number", requerido=False,
          alias=("vida util", "vida util meses", "meses de vida"), ejemplo=60),
    campo("amort_acum_inicial", "Amortización acumulada al inicio del año", "number", requerido=False,
          alias=("amortizacion acumulada inicial", "amort acum inicial"), ejemplo=24000),
    campo("amort_registrada", "Amortización del año registrada (en blanco = no registró)", "number", requerido=False,
          alias=("amortizacion del año", "amortizacion registrada", "gasto amortizacion"), ejemplo=12000),
    campo("deterioro_acum", "Deterioro acumulado reconocido en años anteriores", "number", requerido=False,
          alias=("deterioro acumulado", "deterioro previo"), ejemplo=0),
    campo("valor_uso", "Valor en uso", "number", requerido=False, alias=("valor en uso", "viu"), ejemplo=""),
    campo("vr_menos_costos", "Valor razonable menos costos de disposición", "number", requerido=False,
          alias=("valor razonable menos costos", "fvlcd", "vr menos costos"), ejemplo=""),
    campo("deterioro_registrado", "Deterioro reconocido por la entidad en el año", "number", requerido=False,
          alias=("deterioro del año", "deterioro registrado"), ejemplo=""),
    campo("indicio_reversion", "Hay indicio de reversión del deterioro (Sí / No)", requerido=False,
          alias=("indicio reversion", "indicio de reversion"), ejemplo=""),
    campo("reversion_registrada", "Reversión de deterioro registrada en el año", "number", requerido=False,
          alias=("reversion registrada", "reversion del año"), ejemplo=""),
    campo("revision_vida", "Vida útil y método revisados al cierre (Sí / No)", requerido=False,
          alias=("revision vida util", "revisado"), ejemplo="Sí"),
]
CAMPOS = {"intangibles": _INTANGIBLES}
TIPOS = {"intangibles": "intangibles"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "intangibles"
CONTROL = "costo"

PARAMETROS = {"vidaMaxPymes": 120, "saldoMayor": None}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "vidaMaxPymes": "PYMES: vida útil máxima si no es fiable (meses)",
    "saldoMayor": "Intangibles netos según el mayor",
}
TOTAL_EJEMPLO = "ajuste"


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    return validar_campos(CAMPOS[tipo], filas)


# --- cálculo -------------------------------------------------------------------

def _opt(v):
    """Número opcional: vacío → None (M22)."""
    return a_num(v) if str(v if v is not None else "").strip() else None


def _txt(v) -> str:
    return str(v if v is not None else "").strip()


def _si(v: str) -> bool:
    """Igual que LEFT(x,1)="S" en Excel (sin distinguir mayúsculas)."""
    return v.lower().startswith("s")


def _categoria(tipo: str, fase: str) -> str:
    """Igual que la fórmula de 04_Reconocimiento (SEARCH no distingue mayúsculas)."""
    t, f = tipo.lower(), fase.lower()
    if "investig" in t or "investig" in f:
        return "Investigación"
    if "desarroll" in t or "desarroll" in f:
        return "Desarrollo"
    if "goodwill" in t or "plusval" in t:
        return "Goodwill"
    return "Otro"


def _meses(corte, f):
    return (corte.year - f.year) * 12 + corte.month - f.month + 1


def _parametros(parametros: dict) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    v = a_num(p["vidaMaxPymes"])
    if v is None or v <= 0 or v > 120:
        raise ValueError(f"{ETIQUETAS_PARAM['vidaMaxPymes']}: indique meses entre 1 y 120 (PYMES 18.20 y 19.23 (2015) / 19.34 (2025): no más de diez años).")
    p["vidaMaxPymes"] = float(v)
    p["saldoMayor"] = None if p.get("saldoMayor") in (None, "") else a_num(p["saldoMayor"])
    return p


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = _parametros(parametros)
    pymes = es_pymes(p)
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")

    its = []
    for f in datasets.get("intangibles") or []:
        costo = a_num(f.get("costo"))
        if not _txt(f.get("id")) or costo is None:
            continue
        vida = _opt(f.get("vida_meses"))
        if vida is not None and vida <= 0:
            raise ValueError(f"Intangible {_txt(f.get('id'))}: la vida útil debe ser mayor que cero (en blanco si es indefinida).")
        fd = fecha(f.get("fecha_disponible")) if _txt(f.get("fecha_disponible")) else None
        x = {"id": _txt(f.get("id")), "desc": _txt(f.get("descripcion")), "tipo": _txt(f.get("tipo")), "fase": _txt(f.get("fase")),
             "c57": _txt(f.get("cumple_57")), "fd": fd, "costo": costo, "res": _opt(f.get("residual")), "vida": vida,
             "aai": _opt(f.get("amort_acum_inicial")), "areg": _opt(f.get("amort_registrada")), "det": _opt(f.get("deterioro_acum")),
             "viu": _opt(f.get("valor_uso")), "fv": _opt(f.get("vr_menos_costos")), "dreg": _opt(f.get("deterioro_registrado")),
             "ind": _txt(f.get("indicio_reversion")), "rreg": _opt(f.get("reversion_registrada")), "rev_vida": _txt(f.get("revision_vida")),
             "_row": f.get("_row")}
        its.append(x)
    if not its:
        raise ValueError("Cargue el auxiliar de intangibles y goodwill por partida al corte.")

    for x in its:
        aai, areg, det, dreg, rreg, res = (x[k] or 0.0 for k in ("aai", "areg", "det", "dreg", "rreg", "res"))
        # 1 · reconocimiento e I+D.
        x["cat"] = _categoria(x["tipo"], x["fase"])
        if x["cat"] == "Investigación":
            x["cap"] = "No"
        elif x["cat"] == "Desarrollo":
            x["cap"] = "No" if pymes or x["c57"].lower() == "no" else "Sí"
        else:
            x["cap"] = "Sí"
        if x["cat"] == "Investigación":
            x["motivo"] = "Investigación a gasto (NIC 38.54; PYMES 18.14)"
        elif x["cat"] == "Desarrollo" and pymes:
            x["motivo"] = "PYMES: desarrollo a gasto (18.14)"
        elif x["cat"] == "Desarrollo" and x["c57"].lower() == "no":
            x["motivo"] = "No cumple NIC 38.57"
        elif x["cat"] == "Desarrollo" and x["c57"] == "":
            x["motivo"] = "Criterios 57 sin evidencia"
        else:
            x["motivo"] = "Reconocido (NIC 38.21; PYMES 18.4)"
        x["libros"] = x["costo"] - aai - areg - det - dreg + rreg
        x["costoAud"] = x["costo"] if x["cap"] == "Sí" else 0
        x["baja"] = x["libros"] if x["cap"] == "No" else 0
        # 2-3 · amortización y vida finita / indefinida.
        x["resN"] = res
        x["amortizable"] = max(x["costoAud"] - res, 0)
        # PYMES 18.20 y 19.23 (2015) / 19.34 (2025): los diez años son el TOPE de la mejor estimación de la
        # gerencia cuando la vida no se puede establecer con fiabilidad, no una vida por defecto. Sin esa
        # estimación no se amortiza (importe vacío, M22) y se pide; si viene y excede el tope, se limita.
        x["sinVida"] = pymes and x["cap"] == "Sí" and x["vida"] is None
        x["topePymes"] = pymes and x["cap"] == "Sí" and x["vida"] is not None and x["vida"] > p["vidaMaxPymes"]
        if x["cap"] == "No" or x["sinVida"]:
            x["vidaAp"] = None
        elif pymes:
            x["vidaAp"] = min(x["vida"], p["vidaMaxPymes"])
        else:
            x["vidaAp"] = None if x["cat"] == "Goodwill" else x["vida"]
        x["tipoVida"] = ("No aplica" if x["cap"] == "No" else "Finita" if x["vidaAp"] is not None else
                         "Sin estimación (18.20)" if pymes else
                         "Goodwill: indefinida (no se amortiza)" if x["cat"] == "Goodwill" else "Indefinida")
        x["mesesEj"] = 0 if x["fd"] is None else max(0, min(12, _meses(corte_a, x["fd"])))
        x["pendiente"] = max(x["amortizable"] - aai - det, 0)
        x["amort"] = (None if x["sinVida"] else
                      0 if x["vidaAp"] is None or x["mesesEj"] == 0 else min(x["amortizable"] / x["vidaAp"] * x["mesesEj"], x["pendiente"]))
        x["aregN"] = areg
        x["difAmort"] = None if x["amort"] is None else x["amort"] - areg
        x["acum"] = aai + (x["amort"] or 0)
        # 4 · revisión de vida útil y valor residual.
        x["mesesTot"] = None if x["fd"] is None or x["cap"] == "No" else max(0, _meses(corte_a, x["fd"]))
        ok = x["vidaAp"] is not None and x["mesesTot"] is not None
        x["remanente"] = max(x["vidaAp"] - x["mesesTot"], 0) if ok else None
        x["esperada"] = min(x["amortizable"], x["amortizable"] / x["vidaAp"] * x["mesesTot"]) if ok else None
        x["difAcum"] = None if x["esperada"] is None or det > 0 else x["esperada"] - x["acum"]
        x["resNoNulo"] = "Sí" if x["cap"] == "Sí" and res > 0 else "No"
        x["revExig"] = ("No aplica" if x["cap"] == "No" else "Con indicios (PYMES 18.24)" if pymes else
                        "No aplica (prueba NIC 36.10 b y 36.90)" if x["cat"] == "Goodwill" else
                        "Anual (NIC 38.104)" if x["tipoVida"] == "Finita" else "Anual (NIC 38.109)")
        x["totAmort"] = "No" if x["remanente"] is None else ("Sí" if x["remanente"] == 0 else "No")
        # 5 · deterioro.
        x["pruebaExig"] = ("No aplica" if x["cap"] == "No" else "Solo si hay indicios (PYMES 27.7)" if pymes else
                           "Anual (NIC 36.10 b y 36.90)" if x["cat"] == "Goodwill" else
                           "Anual (NIC 36.10 a)" if x["vidaAp"] is None or x["fd"] is None else "Si hay indicios (NIC 36.9)")
        x["librosAntes"] = x["costoAud"] - x["acum"] - det
        vals = [v for v in (x["viu"], x["fv"]) if v is not None]
        x["rec"] = max(vals) if vals else None
        x["detCalc"] = None if x["rec"] is None or x["cap"] == "No" else max(x["librosAntes"] - x["rec"], 0)
        x["dregN"] = dreg
        x["detAud"] = 0 if x["cap"] == "No" else (dreg if x["detCalc"] is None else x["detCalc"])
        x["difDet"] = x["detAud"] - dreg
        # 6 · reversión.
        x["detN"] = det
        if x["cat"] == "Goodwill" or x["cap"] == "No" or det == 0 or not _si(x["ind"]):
            x["revCalc"] = 0
        else:
            x["revCalc"] = None if x["rec"] is None else max(0, min(x["rec"] - x["librosAntes"], det))
        x["rregN"] = rreg
        x["revAud"] = rreg if x["revCalc"] is None else x["revCalc"]
        x["difRev"] = x["revAud"] - rreg
        x["limite"] = x["librosAntes"] + det
        # 7 · neto auditado y ajuste.
        x["aud"] = 0 if x["cap"] == "No" else x["costoAud"] - x["acum"] - det - x["detAud"] + x["revAud"]
        x["ajuste"] = x["aud"] - x["libros"]

    S = lambda k: sum(x[k] for x in its if x[k] is not None)
    t = {"netoAuditado": S("aud")}
    t["netoAuxiliar"] = S("libros")
    t["saldoMayor"] = p["saldoMayor"] if p["saldoMayor"] is not None else t["netoAuxiliar"]
    t["ajuste"] = t["netoAuditado"] - t["saldoMayor"]
    t["difAuxMayor"] = t["netoAuxiliar"] - t["saldoMayor"]
    t["bajaNoCapitalizable"] = S("baja")
    t["amortCalculada"] = S("amort")
    t["amortRegistrada"] = S("aregN")
    t["difAmortizacion"] = S("difAmort")
    t["deterioroAuditado"] = S("detAud")
    t["deterioroRegistrado"] = S("dregN")
    t["reversionAuditada"] = S("revAud")
    t["reversionRegistrada"] = S("rregN")

    # Problemas (M22: cada «debe» de la norma que el cálculo no garantiza).
    lista = lambda xs: ", ".join(xs[:6]) + (" …" if len(xs) > 6 else "")
    ids = lambda cond: [x["id"] for x in its if cond(x)]
    tot = lambda cond, k: sum(x[k] for x in its if cond(x) and x[k] is not None)
    pr, marcados = [], {}

    def add(code, cond, k, texto):
        sel = ids(cond)
        if sel:
            imp = tot(cond, k)
            pr.append(problema(code, texto(lista(sel), imp), imp))
            marcados[code] = set(sel)

    add("INVESTIGACION_CAPITALIZADA", lambda x: x["cat"] == "Investigación" and abs(x["libros"]) > 0.005, "baja",
        lambda l, i: f"Investigación capitalizada en {l}: {m(i)} deben ir a gasto del ejercicio en que se incurrieron (NIC 38.54; PYMES 18.14).")
    if pymes:
        add("DESARROLLO_CAPITALIZADO_PYMES", lambda x: x["cat"] == "Desarrollo" and abs(x["libros"]) > 0.005, "baja",
            lambda l, i: f"Desarrollo capitalizado en {l}: en NIIF para las PYMES todo desembolso interno de investigación y desarrollo es gasto (18.14): baja {m(i)}.")
    else:
        add("DESARROLLO_NO_CUMPLE_57", lambda x: x["cat"] == "Desarrollo" and x["cap"] == "No" and abs(x["libros"]) > 0.005, "baja",
            lambda l, i: f"Desarrollo capitalizado sin cumplir los criterios de NIC 38.57 en {l}: baja {m(i)} (NIC 38.57, 38.68).")
        add("SIN_CRITERIOS_57", lambda x: x["cat"] == "Desarrollo" and x["c57"] == "", "costo",
            lambda l, i: f"Desarrollo capitalizado sin evidencia de los seis criterios de NIC 38.57 en {l} ({m(i)}): documéntelos o dé de baja.")
        add("GOODWILL_AMORTIZADO_NIIF_COMPLETAS", lambda x: x["cap"] == "Sí" and x["cat"] == "Goodwill" and x["aregN"] > 0.005, "aregN",
            lambda l, i: f"La entidad amortizó goodwill ({l}) por {m(i)}: en NIIF completas no se amortiza, se prueba su deterioro anualmente (NIIF 3.B63 a; NIC 36.10 b y 36.90).")
        add("INDEFINIDA_AMORTIZADA", lambda x: x["cap"] == "Sí" and x["cat"] != "Goodwill" and x["vidaAp"] is None and x["aregN"] > 0.005, "aregN",
            lambda l, i: f"Intangibles de vida indefinida amortizados ({l}) por {m(i)}: no se amortizan (NIC 38.107).")
        add("SIN_PRUEBA_DETERIORO", lambda x: x["pruebaExig"].startswith("Anual") and x["rec"] is None, "librosAntes",
            lambda l, i: f"Sin prueba de deterioro en {l} (goodwill, vida indefinida o aún no disponible para su uso): falta el valor en uso o el "
                         f"valor razonable menos costos de disposición; importe en libros sin probar {m(i)} (NIC 36.10, 36.90; NIC 38.108).")
        add("SIN_REVISION_VIDA", lambda x: x["revExig"].startswith("Anual") and not _si(x["rev_vida"]), "librosAntes",
            lambda l, i: f"Sin revisión anual de la vida útil y el método en {l} (NIC 38.104; para vida indefinida, 38.109).")
    if pymes:
        add("VIDA_NO_ESTIMADA", lambda x: x["sinVida"], "librosAntes",
            lambda l, i: f"Sin vida útil estimada en {l}: en PYMES toda vida es finita (18.19) y, si no puede establecerse con fiabilidad, se usa la mejor "
                         f"estimación de la gerencia, que no excederá de diez años (18.20; 19.23 (2015) / 19.34 (2025) para el goodwill). Los "
                         f"{p['vidaMaxPymes']:.0f} meses son el tope de esa estimación, no una vida por defecto: pida la estimación documentada de la "
                         f"gerencia. Hasta tenerla el papel no amortiza estas partidas; importe en libros sin amortizar {m(i)}.")
        add("VIDA_EXCEDE_TOPE_PYMES", lambda x: x["topePymes"], "librosAntes",
            lambda l, i: f"Vida útil mayor que el tope en {l}: si la vida no puede establecerse con fiabilidad, la mejor estimación de la gerencia no "
                         f"excederá de diez años (18.20; 19.23 (2015) / 19.34 (2025)); se amortizó con {p['vidaMaxPymes']:.0f} meses. Si la vida sí es "
                         f"fiable, documéntela y suba el parámetro; importe en libros afectado {m(i)}.")
        add("SIN_AMORTIZAR_PYMES", lambda x: x["cap"] == "Sí" and x["cat"] == "Goodwill" and x["aregN"] == 0 and (x["amort"] or 0) > 0.005,
            "amort", lambda l, i: f"En PYMES el goodwill tiene vida finita y se amortiza (18.19-18.21; 19.23 (2015) / 19.34 (2025)): {l} sin amortizar; "
                                  f"amortización calculada {m(i)} con la vida estimada de la ficha.")
    ya = set().union(*(marcados.get(c, set()) for c in ("GOODWILL_AMORTIZADO_NIIF_COMPLETAS", "INDEFINIDA_AMORTIZADA", "SIN_AMORTIZAR_PYMES")))
    add("DIF_AMORTIZACION", lambda x: x["cap"] == "Sí" and x["id"] not in ya and x["difAmort"] is not None and abs(x["difAmort"]) > 0.005, "difAmort",
        lambda l, i: f"La amortización recalculada difiere de la registrada en {l}: {m(i)} (NIC 38.97; PYMES 18.21).")
    add("ACUMULADA_INCONSISTENTE", lambda x: x["difAcum"] is not None and abs(x["difAcum"]) > 0.005, "difAcum",
        lambda l, i: f"La amortización acumulada recalculada no es la esperada por la vida transcurrida en {l}: {m(i)}; revise la vida útil o "
                     "errores de años anteriores (NIC 8.42; PYMES 10.21).")
    add("RESIDUAL_NO_NULO", lambda x: x["resNoNulo"] == "Sí", "resN",
        lambda l, i: f"Valor residual distinto de cero en {l} ({m(i)}): se supone nulo salvo compromiso de compra o mercado activo (NIC 38.100; PYMES 18.23).")
    add("DETERIORO_NO_RECONOCIDO", lambda x: x["detCalc"] is not None and x["difDet"] > 0.005, "difDet",
        lambda l, i: f"Deterioro no reconocido en {l}: el importe recuperable es menor que el importe en libros; pérdida {m(i)} (NIC 36.59; PYMES 27.5).")
    add("DETERIORO_EN_EXCESO", lambda x: x["detCalc"] is not None and x["difDet"] < -0.005, "difDet",
        lambda l, i: f"Deterioro registrado mayor que el calculado en {l}: {m(i)}.")
    add("REVERSION_GOODWILL", lambda x: x["cat"] == "Goodwill" and x["rregN"] > 0.005, "rregN",
        lambda l, i: f"Reversión de deterioro de goodwill en {l} por {m(i)}: está prohibida (NIC 36.124; PYMES 27.28).")
    add("REVERSION_NO_RECONOCIDA", lambda x: x["cat"] != "Goodwill" and x["revCalc"] is not None and x["difRev"] > 0.005, "difRev",
        lambda l, i: f"Con indicio de reversión y recuperable mayor que el importe en libros en {l}: reversión pendiente {m(i)}, limitada al "
                     "importe en libros sin deterioro (NIC 36.114, 36.117; PYMES 27.30).")
    add("REVERSION_EN_EXCESO", lambda x: x["cat"] != "Goodwill" and x["revCalc"] is not None and x["difRev"] < -0.005, "difRev",
        lambda l, i: f"Reversión registrada mayor que la permitida en {l}: {m(i)} (NIC 36.117; PYMES 27.30 c).")
    add("VALOR_NEGATIVO", lambda x: x["costo"] < 0 or any((x[k] or 0) < 0 for k in ("res", "aai", "det", "viu", "fv")), "costo",
        lambda l, i: f"Importes negativos en {l}: corrija el auxiliar (costo, residual, acumulados o recuperable no pueden ser negativos).")
    if p["saldoMayor"] is None:
        pr.append(problema("SIN_MAYOR", "Ingrese el saldo neto de intangibles según el mayor: sin él se toma el auxiliar y no se prueba la conciliación."))
    elif abs(t["difAuxMayor"]) > 0.005:
        pr.append(problema("AUXILIAR_MAYOR", f"El auxiliar ({m(t['netoAuxiliar'])}) no concilia con el mayor ({m(t['saldoMayor'])}): diferencia "
                           f"{m(t['difAuxMayor'])}.", t["difAuxMayor"]))
    if abs(t["ajuste"]) > 0.005:
        pr.append(problema("AJUSTE", f"Los intangibles netos auditados ({m(t['netoAuditado'])}) difieren del neto según el mayor ({m(t['saldoMayor'])}).", t["ajuste"]))

    filas = [{"id": x["id"], "descripcion": x["desc"], "tipo": x["tipo"], "costo": r2(x["costo"]), "vida_aplicada": "" if x["vidaAp"] is None else str(x["vidaAp"]),
              "amortizacion": "" if x["amort"] is None else r2(x["amort"]), "neto_libros": r2(x["libros"]), "neto_auditado": r2(x["aud"]), "ajuste": r2(x["ajuste"]),
              "_row": x["_row"]} for x in its]
    etiquetas = {
        "netoAuditado": "Intangibles netos auditados", "saldoMayor": "Intangibles netos según el mayor", "ajuste": "Ajuste propuesto (neto)",
        "netoAuxiliar": "Neto según el auxiliar del cliente", "difAuxMayor": "Diferencia auxiliar − mayor",
        "bajaNoCapitalizable": "Investigación / desarrollo no capitalizable (baja)",
        "amortCalculada": "Amortización del año recalculada", "amortRegistrada": "Amortización del año registrada",
        "difAmortizacion": "Diferencia de amortización", "deterioroAuditado": "Deterioro del año auditado",
        "deterioroRegistrado": "Deterioro del año registrado", "reversionAuditada": "Reversión de deterioro auditada",
        "reversionRegistrada": "Reversión de deterioro registrada",
    }
    iso = lambda d: d.isoformat() if hasattr(d, "isoformat") else d
    return {"engine": VERSION, "rows": filas, "totals": {k: r2(t[k]) for k in etiquetas}, "labels": etiquetas, "primary": "ajuste",
            "exceptions": pr, "schedule": [],
            "detalle": {"corte": corte_a.isoformat(), "pymes": pymes, "edicion": edicion_pymes(p), "parametros": p, "tot": t,
                        "items": [{k: iso(v) for k, v in x.items()} for x in its]}}


# --- cédulas con fórmulas ----------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen y ajuste propuesto"), ("02_Parametros", "Parámetros"), ("03_Intangibles", "Auxiliar de intangibles y goodwill"),
    ("04_Reconocimiento", "Reconocimiento e investigación / desarrollo"), ("05_Amortizacion", "Amortización y vida finita / indefinida"),
    ("06_Vida_util", "Revisión de vida útil y valor residual"), ("07_Deterioro", "Deterioro e importe recuperable"),
    ("08_Reversion", "Reversión del deterioro"), ("09_Ajuste", "Valor neto y ajuste propuesto"), ("10_Problemas", "Problemas encontrados"),
]
PARK = ["corte", "marco", "pymes", "edicion", "vidaMaxPymes", "saldoMayor"]
PAR = {k: FILA0 + i for i, k in enumerate(PARK)}
P, INT, REC, AMO, VID, DET, REV, AJU = (ref(n) for n, _ in CEDULAS[1:9])


def _pa(k: str) -> str:
    return f"{P}$B${PAR[k]}"


def _rg(hoja_ref: str, col: str, n: int) -> str:
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _tot(col: str, n: int, v):
    return fx(f"SUM({col}{FILA0}:{col}{FILA0 + max(n, 1) - 1})", v)


def _opc(celda: str) -> str:
    """Referencia a un dato opcional: vacío sigue vacío."""
    return f'IF({celda}="","",{celda})'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, t, its = d["parametros"], d["tot"], d["items"]
    n = len(its)
    pymes = d["pymes"]
    norma = f"NIIF para las PYMES {d['edicion']} · secciones 18, 19 y 27" if pymes else "NIIF completas · NIC 38, NIC 36 y NIIF 3"
    PY, CO = _pa("pymes"), _pa("corte")

    parametros = [
        ["Corte del ejercicio", d["corte"], "Ficha del encargo; ejercicio de 12 meses que termina en el corte"],
        ["Marco contable", norma, "PYMES 2015 y 2025: investigación y desarrollo a gasto y goodwill amortizable en su vida útil; solo si no puede establecerse con fiabilidad, "
                                  "mejor estimación de la gerencia no mayor a diez años (19.23 en 2015; 19.34 en 2025). "
                                  "2025: 18.22A presume que la amortización basada en ingresos no es apropiada; Sección 19 alineada con NIIF 3; "
                                  "la plusvalía sigue amortizándose; vigente desde el 1-1-2027; para cortes 2025–2026 solo con adopción anticipada"],
        ["Ruta PYMES (1 = sí, 0 = NIIF completas)", 1 if pymes else 0,
         "1: todo intangible y el goodwill se amortizan y el desarrollo va a gasto; 0: vida indefinida y goodwill sin amortizar con prueba anual"],
        ["Edición PYMES", d["edicion"], "Ficha del encargo"],
        [ETIQUETAS_PARAM["vidaMaxPymes"], p["vidaMaxPymes"], "PYMES: TOPE de la mejor estimación de la gerencia cuando la vida no se puede establecer con "
                                                              "fiabilidad (18.20 / 19.23 en 2015; 19.34 en 2025). No es una vida por defecto: sin vida en la "
                                                              "ficha la partida no se amortiza y se pide la estimación; si la vida excede el tope, se limita al tope"],
        [ETIQUETAS_PARAM["saldoMayor"], p["saldoMayor"], "Mayor contable (en blanco: se toma el auxiliar)"],
    ]

    aux, rec, amo, vid, det, rev, aju = [], [], [], [], [], [], []
    for k, x in enumerate(its):
        r = FILA0 + k
        X = lambda c: f"{INT}{c}{r}"
        aux.append([x["id"], x["desc"], x["tipo"], x["fase"], x["c57"], x["fd"], x["costo"], x["res"], x["vida"], x["aai"], x["areg"], x["det"],
                    x["viu"], x["fv"], x["dreg"], x["ind"], x["rreg"], x["rev_vida"]])
        libros = f'{X("G")}-{X("J")}-{X("K")}-{X("L")}-{X("O")}+{X("Q")}'
        rec.append([
            x["id"], fx(f'{X("C")}&""', x["tipo"]), fx(f'{X("D")}&""', x["fase"]), fx(f'{X("E")}&""', x["c57"]),
            fx(f'IF(OR(ISNUMBER(SEARCH("investig",B{r})),ISNUMBER(SEARCH("investig",C{r}))),"Investigación",'
               f'IF(OR(ISNUMBER(SEARCH("desarroll",B{r})),ISNUMBER(SEARCH("desarroll",C{r}))),"Desarrollo",'
               f'IF(OR(ISNUMBER(SEARCH("goodwill",B{r})),ISNUMBER(SEARCH("plusval",B{r}))),"Goodwill","Otro")))', x["cat"]),
            fx(f'IF(E{r}="Investigación","No",IF(E{r}="Desarrollo",IF({PY}=1,"No",IF(D{r}="No","No","Sí")),"Sí"))', x["cap"]),
            fx(f'IF(E{r}="Investigación","Investigación a gasto (NIC 38.54; PYMES 18.14)",IF(AND(E{r}="Desarrollo",{PY}=1),'
               f'"PYMES: desarrollo a gasto (18.14)",IF(AND(E{r}="Desarrollo",D{r}="No"),"No cumple NIC 38.57",'
               f'IF(AND(E{r}="Desarrollo",D{r}=""),"Criterios 57 sin evidencia","Reconocido (NIC 38.21; PYMES 18.4)"))))', x["motivo"]),
            fx(X("G"), x["costo"]), fx(f'IF(F{r}="Sí",H{r},0)', x["costoAud"]), fx(f'IF(F{r}="No",{libros},0)', x["baja"]),
        ])
        meses = f"(YEAR({CO})-YEAR({X('F')}))*12+MONTH({CO})-MONTH({X('F')})+1"
        amo.append([
            x["id"], fx(f"{REC}E{r}", x["cat"]), fx(f"{REC}F{r}", x["cap"]), fx(f"{REC}I{r}", x["costoAud"]), fx(f"{X('H')}+0", x["resN"]),
            fx(f"MAX(D{r}-E{r},0)", x["amortizable"]),
            fx(f'IF(C{r}="No","",IF({PY}=1,IF({X("I")}="","",MIN({X("I")},{_pa("vidaMaxPymes")})),'
               f'IF(B{r}="Goodwill","",IF({X("I")}="","",{X("I")}))))', x["vidaAp"]),
            fx(f'IF(C{r}="No","No aplica",IF(G{r}<>"","Finita",IF({PY}=1,"Sin estimación (18.20)",'
               f'IF(B{r}="Goodwill","Goodwill: indefinida (no se amortiza)","Indefinida"))))', x["tipoVida"]),
            fx(f'IF({X("F")}="",0,MAX(0,MIN(12,{meses})))', x["mesesEj"]),
            fx(f"MAX(F{r}-{X('J')}-{X('L')},0)", x["pendiente"]),
            fx(f'IF(AND({PY}=1,C{r}="Sí",G{r}=""),"",IF(OR(G{r}="",I{r}=0),0,MIN(F{r}/G{r}*I{r},J{r})))', x["amort"]),
            fx(f"{X('K')}+0", x["aregN"]), fx(f'IF(K{r}="","",K{r}-L{r})', x["difAmort"]),
            fx(f'{X("J")}+IF(K{r}="",0,K{r})', x["acum"]),
        ])
        vid.append([
            x["id"], fx(f"{AMO}B{r}", x["cat"]), fx(_opc(X("I")), x["vida"]), fx(_opc(f"{AMO}G{r}"), x["vidaAp"]), fx(f"{AMO}H{r}", x["tipoVida"]),
            fx(f'IF(OR({X("F")}="",{AMO}C{r}="No"),"",MAX(0,{meses}))', x["mesesTot"]),
            fx(f'IF(OR(D{r}="",F{r}=""),"",MAX(D{r}-F{r},0))', x["remanente"]),
            fx(f'IF(OR(D{r}="",F{r}=""),"",MIN({AMO}F{r},{AMO}F{r}/D{r}*F{r}))', x["esperada"]),
            fx(f"{AMO}N{r}", x["acum"]), fx(f'IF(OR(H{r}="",{X("L")}>0),"",H{r}-I{r})', x["difAcum"]),
            fx(f"{AMO}E{r}", x["resN"]), fx(f'IF(AND({AMO}C{r}="Sí",K{r}>0),"Sí","No")', x["resNoNulo"]),
            fx(f'{X("R")}&""', x["rev_vida"]),
            fx(f'IF({AMO}C{r}="No","No aplica",IF({PY}=1,"Con indicios (PYMES 18.24)",IF(B{r}="Goodwill","No aplica (prueba NIC 36.10 b y 36.90)",'
               f'IF(E{r}="Finita","Anual (NIC 38.104)","Anual (NIC 38.109)"))))', x["revExig"]),
            fx(f'IF(G{r}="","No",IF(G{r}=0,"Sí","No"))', x["totAmort"]),
        ])
        det.append([
            x["id"], fx(f"{AMO}B{r}", x["cat"]), fx(f"{AMO}C{r}", x["cap"]),
            fx(f'IF(C{r}="No","No aplica",IF({PY}=1,"Solo si hay indicios (PYMES 27.7)",IF(B{r}="Goodwill","Anual (NIC 36.10 b y 36.90)",'
               f'IF(OR({AMO}G{r}="",{X("F")}=""),"Anual (NIC 36.10 a)","Si hay indicios (NIC 36.9)"))))', x["pruebaExig"]),
            fx(f"{AMO}D{r}-{AMO}N{r}-{X('L')}", x["librosAntes"]), fx(_opc(X("M")), x["viu"]), fx(_opc(X("N")), x["fv"]),
            fx(f'IF(AND(F{r}="",G{r}=""),"",MAX(F{r},G{r}))', x["rec"]),
            fx(f'IF(OR(H{r}="",C{r}="No"),"",MAX(E{r}-H{r},0))', x["detCalc"]),
            fx(f"{X('O')}+0", x["dregN"]), fx(f'IF(C{r}="No",0,IF(I{r}="",J{r},I{r}))', x["detAud"]), fx(f"K{r}-J{r}", x["difDet"]),
        ])
        rev.append([
            x["id"], fx(f"{AMO}B{r}", x["cat"]), fx(f"{X('L')}+0", x["detN"]), fx(f'{X("P")}&""', x["ind"]), fx(f"{DET}E{r}", x["librosAntes"]),
            fx(_opc(f"{DET}H{r}"), x["rec"]),
            fx(f'IF(OR(B{r}="Goodwill",{AMO}C{r}="No",C{r}=0,LEFT(D{r},1)<>"S"),0,IF(F{r}="","",MAX(0,MIN(F{r}-E{r},C{r}))))', x["revCalc"]),
            fx(f"{X('Q')}+0", x["rregN"]), fx(f'IF(G{r}="",H{r},G{r})', x["revAud"]), fx(f"I{r}-H{r}", x["difRev"]), fx(f"E{r}+C{r}", x["limite"]),
        ])
        aju.append([
            x["id"], x["desc"], fx(libros, x["libros"]),
            fx(f'IF({AMO}C{r}="No",0,{AMO}D{r}-{AMO}N{r}-{X("L")}-{DET}K{r}+{REV}I{r})', x["aud"]), fx(f"D{r}-C{r}", x["ajuste"]),
        ])

    fr = {k: FILA0 + i for i, k in enumerate(res["labels"])}
    rb = lambda k: f"B{fr[k]}"
    ref_res = {
        "netoAuditado": f"SUM({_rg(AJU, 'D', n)})",
        "saldoMayor": f'IF({_pa("saldoMayor")}="",SUM({_rg(AJU, "C", n)}),{_pa("saldoMayor")})',
        "ajuste": f"{rb('netoAuditado')}-{rb('saldoMayor')}", "netoAuxiliar": f"SUM({_rg(AJU, 'C', n)})",
        "difAuxMayor": f"{rb('netoAuxiliar')}-{rb('saldoMayor')}", "bajaNoCapitalizable": f"SUM({_rg(REC, 'J', n)})",
        "amortCalculada": f"SUM({_rg(AMO, 'K', n)})", "amortRegistrada": f"SUM({_rg(AMO, 'L', n)})", "difAmortizacion": f"SUM({_rg(AMO, 'M', n)})",
        "deterioroAuditado": f"SUM({_rg(DET, 'K', n)})", "deterioroRegistrado": f"SUM({_rg(DET, 'J', n)})",
        "reversionAuditada": f"SUM({_rg(REV, 'I', n)})", "reversionRegistrada": f"SUM({_rg(REV, 'H', n)})",
    }
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]
    S = lambda k: sum(x[k] for x in its if x[k] is not None)
    N = "n"
    return [
        hoja("01_Resumen", CEDULAS[0][1], [["Concepto", "t"], ["Importe", N]], resumen),
        hoja("02_Parametros", CEDULAS[1][1], [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Intangibles", CEDULAS[2][1],
             [["Código", "t"], ["Descripción", "t"], ["Tipo", "t"], ["Fase", "t"], ["Cumple NIC 38.57", "t"], ["Disponible para uso", "d"], ["Costo", N],
              ["Valor residual", N], ["Vida útil (meses)", "i"], ["Amort. acum. inicial", N], ["Amort. del año registrada", N], ["Deterioro acum. previo", N],
              ["Valor en uso", N], ["VR menos costos de disposición", N], ["Deterioro del año registrado", N], ["Indicio de reversión", "t"],
              ["Reversión registrada", N], ["Vida revisada al cierre", "t"]],
             aux, ["TOTAL", "", "", "", "", None, _tot("G", n, S("costo")), None, None, None, None, None, None, None, None, "", None, ""]),
        hoja("04_Reconocimiento", CEDULAS[3][1],
             [["Código", "t"], ["Tipo", "t"], ["Fase", "t"], ["Cumple NIC 38.57", "t"], ["Categoría", "t"], ["Capitalizable", "t"], ["Criterio", "t"],
              ["Costo registrado", N], ["Costo auditado", N], ["Neto a dar de baja (gasto)", N]],
             rec, ["TOTAL", "", "", "", "", "", "", _tot("H", n, S("costo")), _tot("I", n, S("costoAud")), _tot("J", n, t["bajaNoCapitalizable"])]),
        hoja("05_Amortizacion", CEDULAS[4][1],
             [["Código", "t"], ["Categoría", "t"], ["Capitalizable", "t"], ["Costo auditado", N], ["Valor residual", N], ["Importe amortizable", N],
              ["Vida aplicada (meses)", "i"], ["Tipo de vida", "t"], ["Meses en uso del ejercicio", "i"], ["Importe pendiente", N],
              ["Amortización recalculada", N], ["Amortización registrada", N], ["Diferencia", N], ["Amort. acumulada recalculada", N]],
             amo, ["TOTAL", "", "", _tot("D", n, S("costoAud")), None, _tot("F", n, S("amortizable")), None, "", None, None,
                   _tot("K", n, t["amortCalculada"]), _tot("L", n, t["amortRegistrada"]), _tot("M", n, t["difAmortizacion"]), _tot("N", n, S("acum"))]),
        hoja("06_Vida_util", CEDULAS[5][1],
             [["Código", "t"], ["Categoría", "t"], ["Vida registrada (meses)", "i"], ["Vida aplicada (meses)", "i"], ["Tipo de vida", "t"],
              ["Meses transcurridos al cierre", "i"], ["Vida remanente (meses)", "i"], ["Amort. acumulada esperada", N], ["Amort. acumulada recalculada", N],
              ["Diferencia (esperada − recalculada)", N], ["Valor residual", N], ["Residual distinto de cero", "t"], ["Vida revisada al cierre", "t"],
              ["Revisión exigida", "t"], ["Totalmente amortizado", "t"]], vid),
        hoja("07_Deterioro", CEDULAS[6][1],
             [["Código", "t"], ["Categoría", "t"], ["Capitalizable", "t"], ["Prueba exigida", "t"], ["Importe en libros antes del deterioro", N],
              ["Valor en uso", N], ["VR menos costos de disposición", N], ["Importe recuperable", N], ["Deterioro calculado", N],
              ["Deterioro registrado", N], ["Deterioro auditado", N], ["Diferencia", N]],
             det, ["TOTAL", "", "", "", None, None, None, None, None, _tot("J", n, t["deterioroRegistrado"]), _tot("K", n, t["deterioroAuditado"]),
                   _tot("L", n, S("difDet"))]),
        hoja("08_Reversion", CEDULAS[7][1],
             [["Código", "t"], ["Categoría", "t"], ["Deterioro acumulado previo", N], ["Indicio de reversión", "t"], ["Importe en libros", N],
              ["Importe recuperable", N], ["Reversión calculada", N], ["Reversión registrada", N], ["Reversión auditada", N], ["Diferencia", N],
              ["Límite: importe en libros sin deterioro (NIC 36.117)", N]],
             rev, ["TOTAL", "", None, "", None, None, None, _tot("H", n, t["reversionRegistrada"]), _tot("I", n, t["reversionAuditada"]),
                   _tot("J", n, S("difRev")), None]),
        hoja("09_Ajuste", CEDULAS[8][1],
             [["Código", "t"], ["Descripción", "t"], ["Neto en libros (cliente)", N], ["Neto auditado", N], ["Ajuste propuesto", N]],
             aju, ["TOTAL", "", _tot("C", n, t["netoAuxiliar"]), _tot("D", n, t["netoAuditado"]), _tot("E", n, S("ajuste"))]),
        hoja("10_Problemas", CEDULAS[9][1], [["Código", "t"], ["Descripción", "t"], ["Importe", N]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición ------------------------------------------------------------------

def definicion() -> dict:
    contenido = ("Una fila por intangible o goodwill: código, descripción, tipo (software, licencia, marca, desarrollo, investigación, goodwill, "
                 "otro), fase del proyecto interno, si el desarrollo cumple NIC 38.57, fecha disponible para su uso, costo, residual, vida útil "
                 "en meses (en blanco = indefinida), amortización acumulada inicial, amortización del año registrada, deterioro acumulado previo, "
                 "valor en uso, valor razonable menos costos de disposición, deterioro y reversión registrados en el año, indicio de reversión y "
                 "si la vida útil se revisó al cierre; sin filas de total.")
    prog = lambda code, obj, risk, asr, proc, ev, crit, src: {"code": code, "objective": obj, "risk": risk, "assertion": asr, "procedure": proc,
                                                               "evidence": ev, "criterion": crit, "source": src}
    return {
        "name": "Activos intangibles y goodwill",
        "area": "Intangibles",
        "processor": "intangibles_goodwill",
        "frameworks": ["NIIF completas", "NIIF para las PYMES"],
        "summary": ("Prueba integral de intangibles y goodwill: reconocimiento, separación investigación/desarrollo, recálculo de la amortización, "
                    "vida finita e indefinida, revisión de vida útil y valor residual, deterioro con importe recuperable, reversión (prohibida en "
                    "goodwill) y ajuste neto contra el mayor. Enruta por marco: en PYMES todo intangible y el goodwill se amortizan y el "
                    "desarrollo va a gasto."),
        "source": {"organization": "IFRS Foundation · Reglamento (UE) 2023/1803 (texto en español)", "type": "Norma contable", "date": "",
                   "document": "NIC 38 Activos intangibles · párr. 21-23 (reconocimiento), 54 (investigación a gasto), 57 (desarrollo), 71 (lo "
                               "llevado a gasto no se capitaliza después), 88-89 (vida finita o indefinida), 97-98 (amortización), 100 (residual "
                               "nulo), 104 (revisión anual), 107-110 (vida indefinida sin amortizar, prueba anual y revisión). NIC 36 · párr. 10 a "
                               "(prueba anual de vida indefinida y no disponibles), 18 (importe recuperable), 59-60 (pérdida), 10 b y 90 (prueba anual del goodwill), "
                               "114, 117, 119 (reversión y su límite), 124 (sin reversión en goodwill). NIIF 3 · párr. 32 y B63 a (goodwill).",
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable",
                         "document": "NIIF para las PYMES 2015 · Sección 18 (18.4 reconocimiento; 18.14 investigación y desarrollo a gasto; 18.19 "
                                     "toda vida es finita; 18.20 sin estimación fiable, mejor estimación no mayor a diez años; 18.21-18.22 "
                                     "amortización; 18.23 residual cero; 18.24 revisión con indicios), Sección 19 (19.23 en 2015 / 19.34 en 2025: goodwill al costo menos "
                                     "amortización y deterioro; vida útil y, solo si no puede establecerse con fiabilidad, mejor estimación de la gerencia no mayor a diez años) y Sección 27 (27.5-27.7 deterioro e indicios; "
                                     "27.28 sin reversión en plusvalía; 27.29-27.30 reversión). Edición 2025 (tercera): 18.22A presume que la "
                                     "amortización basada en ingresos no es apropiada; Sección 19 alineada con NIIF 3; la plusvalía sigue "
                                     "amortizándose; vigente desde el 1-1-2027; para cortes 2025–2026 solo con adopción anticipada.",
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 16–17, 18–27 y 28–30", "requirement": "Vida útil, residual, valor en uso y VR menos costos son estimaciones: evaluar método, datos y supuestos."},
            {"document": "NIA 500", "section": "párr. 6 y 9", "requirement": "Evidencia suficiente del costo, la fecha de disponibilidad y los criterios de NIC 38.57."},
            {"document": "NIA 500", "section": "párr. 8 (experto de la dirección; NIA 620 solo si lo contrata el auditor)", "requirement": "Evaluar el trabajo del experto en valoración usado para el importe recuperable y la asignación del precio de compra."},
            {"document": "NIA 330", "section": "párr. 18-20", "requirement": "Procedimientos sustantivos y conciliación del auxiliar con el mayor."},
            {"document": "NIA 560", "section": "párr. 6", "requirement": "Hechos posteriores que evidencien deterioro al cierre."},
        ],
        "calculo": [
            "Categoría por tipo y fase: investigación, desarrollo, goodwill u otro. Investigación: no capitalizable. Desarrollo: capitalizable solo en "
            "NIIF completas y si cumple NIC 38.57; en PYMES a gasto (18.14). Lo no capitalizable se da de baja (neto auditado 0).",
            "Importe amortizable = costo auditado − valor residual.",
            "Vida aplicada: en NIIF completas, la registrada; en blanco = indefinida (sin amortización) y el goodwill no se amortiza. En PYMES toda vida "
            "es finita (18.19): se usa la vida registrada limitada al tope del parámetro, porque en 18.20 / 19.23 (19.34 en 2025) los diez años son el "
            "tope de la mejor estimación de la gerencia cuando la vida no puede establecerse con fiabilidad, no una vida por defecto; si la vida no "
            "viene, la partida no se amortiza (importe vacío) y se emite el problema VIDA_NO_ESTIMADA.",
            "Meses en uso del ejercicio = MIN(12, meses desde la fecha disponible hasta el corte, contando entero el mes de disponibilidad).",
            "Amortización = MIN(amortizable ÷ vida × meses en uso, amortizable − amortización acumulada inicial − deterioro acumulado).",
            "Amortización acumulada esperada = MIN(amortizable, amortizable ÷ vida × meses transcurridos); se compara con la recalculada (sin deterioro previo).",
            "Importe recuperable = MAX(valor en uso, VR menos costos de disposición); deterioro = MAX(importe en libros − recuperable, 0).",
            "Reversión (con indicio, nunca en goodwill) = MIN(recuperable − importe en libros, deterioro acumulado previo) (NIC 36.117).",
            "Neto auditado = costo auditado − amortización acumulada recalculada − deterioro previo − deterioro auditado + reversión auditada; "
            "ajuste propuesto = neto auditado − neto según el mayor.",
            "Simplificación: tras un deterioro la amortización sigue sobre el importe amortizable original con tope en el pendiente; NIC 36.63 pide "
            "redistribuir el nuevo importe en libros en la vida restante: revisar a mano en partidas con deterioro previo.",
        ],
        "fields": _INTANGIBLES, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            prog("INT-01", "Reconocimiento", "Intangibles que no cumplen la definición o los criterios de reconocimiento", "Existencia",
                 "Cotejar costo y titularidad con contratos, facturas y registros; evaluar probabilidad de beneficios", "Contratos, facturas, registros de marcas y patentes",
                 "Solo se reconoce lo que cumple NIC 38.21 / PYMES 18.4", "NIC 38.21-23 · PYMES 18.4"),
            prog("INT-02", "Investigación y desarrollo", "Investigación o desarrollo capitalizados indebidamente", "Valoración",
                 "Separar fases; en NIIF completas verificar los seis criterios de NIC 38.57; en PYMES llevar todo a gasto", "Memorias del proyecto, presupuestos, estudios de viabilidad",
                 "Investigación y desarrollo sin criterios a gasto", "NIC 38.54, 38.57 · PYMES 18.14, INT-04"),
            prog("INT-03", "Amortización", "Amortización mal calculada o no registrada", "Valoración",
                 "Recalcular la amortización desde la fecha disponible para su uso con la vida y el residual", "Auxiliar, actas de puesta en marcha",
                 "Amortización recalculada = registrada", "NIC 38.97-100 · PYMES 18.21-18.23, INT-06"),
            prog("INT-04", "Vida útil finita e indefinida", "Vida indefinida sin sustento o amortizada; vida no revisada", "Valoración",
                 "Evaluar la clasificación de la vida, su revisión anual y, en PYMES, que toda vida sea finita (máximo diez años sin estimación fiable)",
                 "Análisis de factores de vida útil, contratos", "Clasificación sustentada y revisada", "NIC 38.88-96, 38.104, 38.107-110 · PYMES 18.19-18.20, 18.24, INT-08"),
            prog("INT-05", "Deterioro", "Importe en libros mayor que el recuperable", "Valoración",
                 "Revisar la prueba de deterioro: valor en uso y VR menos costos; prueba anual de goodwill, vida indefinida y no disponibles (NIIF completas)",
                 "Modelos de flujos, tasas de descuento, tasaciones", "Pérdida reconocida", "NIC 36.10 a y b, 36.18, 36.59, 36.90 · PYMES 27.5-27.7"),
            prog("INT-06", "Goodwill", "Goodwill amortizado en NIIF completas, sin amortizar en PYMES o con reversión de deterioro", "Valoración",
                 "Verificar la medición del goodwill según el marco y la prohibición de revertir su deterioro", "Asignación del precio de compra, pruebas de deterioro",
                 "Tratamiento según el marco", "NIIF 3.32, B63 a · NIC 36.124 · PYMES 19.23 (2015) / 19.34 (2025), 27.28, INT-10"),
            prog("INT-07", "Reversión del deterioro", "Reversión no reconocida o por encima del límite", "Valoración",
                 "Con indicio, recalcular la reversión limitada al importe en libros sin deterioro", "Nuevas estimaciones del recuperable",
                 "Reversión dentro del límite", "NIC 36.114-119 · PYMES 27.29-27.30"),
            prog("INT-08", "Conciliación con el mayor", "Auxiliar que no respalda el saldo contable", "Integridad",
                 "Conciliar el neto del auxiliar con el mayor y proponer el ajuste", "Auxiliar y mayor", "Diferencia explicada o ajustada", "NIA 330"),
        ],
        "requests": [
            req("RQ-001", "Auxiliar de intangibles y goodwill por partida al corte", "intangibles", "INT-01", "Población, amortización, deterioro y reversión",
                content=contenido),
            req("RQ-002", "Memorias de proyectos de desarrollo y evidencia de los criterios de NIC 38.57", None, "INT-02", "Soporte de la capitalización",
                formats=("pdf", "docx", "xlsx"), use="soporte"),
            req("RQ-003", "Pruebas de deterioro (valor en uso, VR menos costos de disposición) y análisis de indicios", None, "INT-05", "Soporte del importe recuperable",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-004", "Asignación del precio de compra de las combinaciones de negocios", None, "INT-06", "Soporte del goodwill",
                formats=("pdf", "xlsx"), use="soporte", required=False),
            req("RQ-005", "Contratos de licencias, registros de marcas y patentes", None, "INT-04", "Soporte de la vida útil y la titularidad",
                formats=("pdf",), use="soporte"),
            req("RQ-006", "Análisis de la vida útil y del valor residual revisados al cierre", None, "INT-04", "Soporte de la revisión anual",
                formats=("pdf", "docx", "xlsx"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) ---------------------------------------------------------

def _i(id, desc, tipo, fd, costo, vida="", aai="", areg="", res="", det="", viu="", fv="", dreg="", ind="", rreg="", rev="Sí", fase="", c57=""):
    return {"id": id, "descripcion": desc, "tipo": tipo, "fase": fase, "cumple_57": c57, "fecha_disponible": fd, "costo": costo,
            "residual": res, "vida_meses": vida, "amort_acum_inicial": aai, "amort_registrada": areg, "deterioro_acum": det,
            "valor_uso": viu, "vr_menos_costos": fv, "deterioro_registrado": dreg, "indicio_reversion": ind,
            "reversion_registrada": rreg, "revision_vida": rev, "_row": 2}


# Cifras a mano (NIIF completas, corte 31-12-2025): neto auxiliar 510.050; neto auditado 467.050; mayor 512.050;
# ajuste −45.000 = LIC-01 +2.000 (36 meses, 9 meses en uso: 6.000 vs 8.000) − MAR-01 10.000 (deterioro 150.000 − 140.000)
# − GW-01 15.000 (reversión de goodwill) − INV-01 18.000 − DES-02 12.000 (bajas) + PAT-01 10.000 (reversión, tope NIC 36.117)
# − 2.000 (auxiliar − mayor). PYMES: MAR-01 y GW-01 se amortizan a 120 meses (15.000 y 20.000) y el desarrollo va a gasto.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"vidaMaxPymes": 120, "saldoMayor": 512050},
    "datasets": {
        "intangibles": [
            _i("SW-01", "Software ERP", "Software", "2023-01-01", 60000, vida=60, aai=24000, areg=12000),
            _i("LIC-01", "Licencia de distribución exclusiva", "Licencia", "2025-04-01", 24000, vida=36, aai=0, areg=8000),
            _i("MAR-01", "Marca comercial adquirida", "Marca", "2022-07-01", 150000, viu=140000, fv=130000),
            _i("GW-01", "Goodwill adquisición Distribuidora Andina", "Goodwill", "2021-01-01", 200000, det=30000, viu=185000, ind="Sí", rreg=15000),
            _i("INV-01", "Estudio de mercado y prototipos nuevo producto", "Proyecto interno", "", 18000, fase="Investigación"),
            _i("DES-01", "Aplicación móvil de pedidos", "Desarrollo", "2025-10-01", 45000, vida=36, aai=0, areg=3750, fase="Desarrollo", c57="Sí"),
            _i("DES-02", "Módulo de comercio electrónico", "Desarrollo", "", 12000, fase="Desarrollo", c57="No"),
            _i("DES-03", "Plataforma logística en desarrollo", "Desarrollo", "", 30000, vida=60, fase="Desarrollo", c57="Sí"),
            _i("PAT-01", "Patente de proceso", "Patente", "2020-01-01", 80000, vida=120, aai=36000, areg=7200, res=8000, det=10000,
               viu=40000, fv=38000, ind="Sí", rev="No"),
            _i("SW-02", "Software CRM", "Software", "2019-01-01", 9000, vida=48, aai=9000, areg=0),
            _i("SW-03", "Software de nómina", "Software", "2024-07-01", 12000, vida=36, aai=1000, areg=4000),
        ],
    },
}

_E = EJEMPLO
_MIN = {"intangibles": [_i("X-1", "Licencia", "Licencia", "2025-07-01", 12000, vida=24, areg=3000)]}
ESCENARIOS = [
    ("niif_completas", _E["datasets"], {**_E["parametros"], "_marco": "NIIF completas"}, _E["corte"]),
    ("pymes_2015", _E["datasets"], {**_E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"}, _E["corte"]),
    ("pymes_2025", _E["datasets"], {"vidaMaxPymes": 96, "_marco": "NIIF para las PYMES", "_edicion": "2025"}, _E["corte"]),
    ("minimo_sin_mayor", _MIN, {}, _E["corte"]),
]
