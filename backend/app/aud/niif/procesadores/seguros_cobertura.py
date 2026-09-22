"""Cobertura de seguros de activos: activos asegurados vs registrados, vigencia de pólizas, suma asegurada,
infraseguro y sobreseguro, deducibles, activos sin cobertura, exposición máxima, siniestros pendientes y
devengo de la prima pagada por anticipado.

Naturaleza (especificación del socio, MÓDULO 09): prueba de auditoría y de riesgo, NO una medición NIIF
autónoma. La cobertura es evidencia de riesgo y de continuidad operativa (NIA 315/330, NIA 570); nunca
se concluye cumplimiento normativo solo por cobertura. Lo único contable que se mide es:
- la prima pagada por anticipado (devengo: NIC 1 párr. 27–28; PYMES 2.36): se reconoce como gasto por el
  tiempo transcurrido de la vigencia y el saldo anticipado es la parte no transcurrida al corte;
- los siniestros pendientes, que se evalúan para revelación de contingencias (NIC 37 párr. 86 y 89; el
  reembolso solo se reconoce cuando es prácticamente seguro, NIC 37 párr. 53; PYMES Sección 21).

Versión simple (igual en NIIF completas y PYMES 2015/2025):
1. Referencia del activo = valor de reposición o tasación; si falta, el valor en libros (se señala).
2. Suma asegurada del activo = la asignada; si la póliza no la asigna, prorrata de la suma total de la
   póliza por el valor de referencia. Solo cuenta si la póliza está vigente al corte.
3. % cobertura = suma asegurada / referencia; déficit = max(referencia − suma, 0); sobreseguro =
   max(suma − referencia, 0); infraseguro si % < umbral; sobreseguro si % > umbral superior.
4. Cláusula de infraseguro (regla proporcional): indemnización = pérdida × min(suma / referencia, 1) −
   deducible; pérdida no cubierta ante pérdida total = referencia − indemnización neta; exposición máxima
   = la mayor pérdida no cubierta de un solo activo.
5. Prima anticipada al corte = prima × días restantes de vigencia ÷ días de vigencia, frente a la registrada.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja,
    m, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "seguros_cobertura 1.0"
RUBRO = "SEGUROS"

_ACTIVOS = [
    campo("id", "Código del activo", alias=("codigo", "código", "activo", "codigo activo", "placa"), ejemplo="EDIF-01"),
    campo("descripcion", "Descripción", alias=("detalle", "nombre", "descripcion del activo"), ejemplo="Edificio administrativo"),
    campo("clase", "Clase", requerido=False, alias=("grupo", "tipo de activo", "categoria", "cuenta"), ejemplo="Edificios"),
    campo("valor_libros", "Valor en libros", "number", alias=("valor en libros", "vnl", "valor neto", "saldo contable"), ejemplo="437500"),
    campo("valor_referencia", "Valor de referencia (reposición o tasación)", "number", False,
          ("valor de reposicion", "valor reposicion", "tasacion", "avaluo", "valor de referencia", "valor asegurable"), "650000"),
    campo("poliza", "Póliza asignada", requerido=False, alias=("poliza", "póliza", "numero de poliza", "n poliza"), ejemplo="POL-01"),
    campo("suma_asignada", "Suma asegurada asignada", "number", False,
          ("suma asegurada", "valor asegurado", "suma asignada", "monto asegurado"), ""),
    campo("deducible_pct", "Deducible (% de la pérdida)", "number", False, ("deducible", "deducible %", "porcentaje deducible"), "2"),
]
_POLIZAS = [
    campo("id", "N° de póliza", alias=("poliza", "póliza", "numero de poliza", "n poliza"), ejemplo="POL-01"),
    campo("aseguradora", "Aseguradora", alias=("compania", "compañia", "aseguradora", "compania de seguros"), ejemplo="Aseguradora Alfa S.A."),
    campo("ramo", "Ramo", requerido=False, alias=("ramo", "tipo de seguro", "cobertura"), ejemplo="Incendio y líneas aliadas"),
    campo("vigencia_desde", "Vigencia desde", "date", alias=("desde", "inicio vigencia", "vigencia desde", "fecha inicio"), ejemplo="2025-07-01"),
    campo("vigencia_hasta", "Vigencia hasta", "date", alias=("hasta", "fin vigencia", "vigencia hasta", "fecha fin", "vencimiento"), ejemplo="2026-07-01"),
    campo("suma_total", "Suma asegurada total", "number", alias=("suma asegurada", "suma asegurada total", "valor asegurado"), ejemplo="700000"),
    campo("prima_total", "Prima total", "number", False, ("prima", "prima neta", "prima total"), "7300"),
    campo("prima_anticipada", "Prima pagada por anticipado registrada al corte", "number", False,
          ("prima anticipada", "seguro prepagado", "seguros pagados por anticipado", "saldo anticipado"), "3640"),
    campo("siniestro", "Siniestro pendiente (descripción)", requerido=False, alias=("siniestro", "reclamo", "siniestro pendiente"), ejemplo=""),
    campo("monto_siniestro", "Monto del siniestro pendiente", "number", False, ("monto siniestro", "valor reclamado", "monto reclamo"), ""),
    campo("siniestro_revelado", "Siniestro revelado en notas (Sí/No)", requerido=False, alias=("revelado", "revelacion", "en notas"), ejemplo=""),
]
CAMPOS = {"activos": _ACTIVOS, "polizas": _POLIZAS}
TIPOS = {"activos": "activos", "polizas": "polizas"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "activos"
CONTROL = "valor_libros"
TOTAL_EJEMPLO = "deficitCobertura"

PARAMETROS = {"coberturaMinima": 80, "sobreseguroDesde": 120, "diasAlerta": 30, "tolerancia": 1, "mayorPrimaAnticipada": None}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "coberturaMinima": "Cobertura mínima (% del valor de referencia)",
    "sobreseguroDesde": "Sobreseguro desde (% del valor de referencia)",
    "diasAlerta": "Alerta de póliza por vencer (días)",
    "tolerancia": "Tolerancia de diferencias (importe)",
    "mayorPrimaAnticipada": "Mayor: seguros pagados por anticipado al corte",
}


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    v = validar_campos(CAMPOS[tipo], filas)
    nums = ("valor_libros", "valor_referencia", "suma_asignada", "deducible_pct") if tipo == "activos" else \
        ("suma_total", "prima_total", "prima_anticipada", "monto_siniestro")
    for f in filas:
        for k in nums:
            x = a_num(f.get(k)) if _t(f.get(k)) else None
            if x is not None and x < 0:
                v["errors"].append({"row": f.get("_row"), "field": k, "message": "Use importes positivos."})
        if tipo == "activos":
            d = a_num(f.get("deducible_pct")) if _t(f.get("deducible_pct")) else None
            if d is not None and d > 100:
                v["errors"].append({"row": f.get("_row"), "field": "deducible_pct", "message": "Deducible: porcentaje entre 0 y 100."})
        else:
            a, b = fecha(f.get("vigencia_desde")), fecha(f.get("vigencia_hasta"))
            if a and b and b <= a:
                v["errors"].append({"row": f.get("_row"), "field": "vigencia_hasta", "message": "La vigencia hasta debe ser posterior a la vigencia desde."})
    v["ok"] = not v["errors"]
    return v


# --- cálculo -----------------------------------------------------------------

def _t(v) -> str:
    return str(v if v is not None else "").strip()


def _opc(v):
    return a_num(v) if _t(v) else None


def _p(p, k):
    v = p.get(k)
    return None if v is None or _t(v) == "" else float(a_num(v))


def _si_no(v) -> bool:
    return _t(v).lower() in ("sí", "si")


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    pymes = es_pymes(p)
    cmin, csob = _p(p, "coberturaMinima"), _p(p, "sobreseguroDesde")
    alerta, tol = _p(p, "diasAlerta"), _p(p, "tolerancia") or 0.0
    if cmin is None or not 0 < cmin <= 100:
        raise ValueError("La cobertura mínima debe ser un porcentaje entre 0 y 100.")
    if csob is None or csob < 100:
        raise ValueError("El umbral de sobreseguro debe ser 100 % o más.")
    if alerta is None or alerta < 0:
        raise ValueError("Los días de alerta deben ser cero o más.")

    # Pólizas y vigencia al corte.
    polizas, por_pol = [], {}
    for f in datasets.get("polizas") or []:
        if not _t(f.get("id")):
            continue
        x = {"id": _t(f.get("id")), "aseg": _t(f.get("aseguradora")), "ramo": _t(f.get("ramo")),
             "desde": fecha(f.get("vigencia_desde")), "hasta": fecha(f.get("vigencia_hasta")),
             "suma": _opc(f.get("suma_total")), "prima": _opc(f.get("prima_total")), "reg": _opc(f.get("prima_anticipada")),
             "sin": _t(f.get("siniestro")), "msin": _opc(f.get("monto_siniestro")), "rev": _t(f.get("siniestro_revelado")),
             "_row": f.get("_row")}
        if x["desde"] is None or x["hasta"] is None or x["hasta"] <= x["desde"]:
            raise ValueError(f"Póliza {x['id']}: indique una vigencia válida (hasta posterior a desde).")
        if x["suma"] is None or x["suma"] < 0:
            raise ValueError(f"Póliza {x['id']}: indique la suma asegurada total (positiva).")
        x["dias"] = (x["hasta"] - x["desde"]).days
        x["estado"] = "Vencida" if x["hasta"] < corte_a else ("No iniciada" if x["desde"] > corte_a else "Vigente")
        x["por_vencer"] = (x["hasta"] - corte_a).days if x["estado"] == "Vigente" else None
        x["alerta"] = "" if x["por_vencer"] is None else ("Por vencer" if x["por_vencer"] <= alerta else "")
        polizas.append(x)
        por_pol.setdefault(x["id"].lower(), x)

    activos = []
    for f in datasets.get("activos") or []:
        if not _t(f.get("id")):
            continue
        a = {"id": _t(f.get("id")), "desc": _t(f.get("descripcion")), "clase": _t(f.get("clase")),
             "libros": _opc(f.get("valor_libros")), "vref": _opc(f.get("valor_referencia")), "pol": _t(f.get("poliza")),
             "asig": _opc(f.get("suma_asignada")), "ded": _opc(f.get("deducible_pct")), "_row": f.get("_row")}
        if a["libros"] is None:
            raise ValueError(f"Activo {a['id']}: indique el valor en libros.")
        if min(a["libros"], a["vref"] or 0, a["asig"] or 0) < 0:
            raise ValueError(f"Activo {a['id']}: los importes deben ser positivos.")
        activos.append(a)
    if not activos:
        raise ValueError("Cargue el maestro de activos asegurables con su póliza y valor de referencia.")

    # Cobertura por activo (misma aritmética que 06_Cobertura_activo).
    ref_pol = {}
    for a in activos:
        a["ref"] = a["vref"] if a["vref"] is not None else a["libros"]
        a["base"] = "Reposición/tasación" if a["vref"] is not None else "Valor en libros"
        ref_pol[a["pol"].lower()] = ref_pol.get(a["pol"].lower(), 0) + a["ref"]
    for a in activos:
        pol = por_pol.get(a["pol"].lower()) if a["pol"] else None
        a["estado"] = "Sin póliza" if not a["pol"] else ("Póliza no encontrada" if pol is None else pol["estado"])
        if pol is None:
            a["suma"] = 0.0
        elif a["asig"] is not None:
            a["suma"] = a["asig"]
        else:
            s = ref_pol[a["pol"].lower()]
            a["suma"] = 0.0 if s == 0 else pol["suma"] * a["ref"] / s
        a["efec"] = a["suma"] if a["estado"] == "Vigente" else 0.0
        a["cob"] = None if a["ref"] == 0 else a["efec"] / a["ref"]
        a["deficit"] = max(a["ref"] - a["efec"], 0)
        a["exceso"] = max(a["efec"] - a["ref"], 0)
        if a["efec"] == 0:
            a["clasif"] = "Sin cobertura"
        elif a["cob"] is None:
            a["clasif"] = ""
        else:
            a["clasif"] = "Infraseguro" if a["cob"] < cmin / 100 else ("Sobreseguro" if a["cob"] > csob / 100 else "Adecuada")
        # Deducible y pérdida no cubierta ante pérdida total (08_Deducibles_exposicion).
        a["factor"] = 0 if a["ref"] == 0 else min(a["efec"] / a["ref"], 1)
        a["indem_bruta"] = a["ref"] * a["factor"]
        a["ded_pct"] = a["ded"] or 0
        a["deducible"] = 0 if a["indem_bruta"] == 0 else min(a["ref"] * a["ded_pct"] / 100, a["indem_bruta"])
        a["indem"] = a["indem_bruta"] - a["deducible"]
        a["no_cubierta"] = a["ref"] - a["indem"]

    # Cobertura por póliza (07_Cobertura_poliza) y prima anticipada (10_Prima_anticipada).
    for x in polizas:
        k = x["id"].lower()
        grupo = [a for a in activos if a["pol"].lower() == k]
        x["ref"] = sum(a["ref"] for a in grupo)
        x["n"] = len(grupo)
        x["cob"] = None if x["ref"] == 0 else x["suma"] / x["ref"]
        x["factor"] = None if x["cob"] is None else min(x["cob"], 1)
        x["deficit"] = max(x["ref"] - x["suma"], 0)
        x["asignada"] = sum(a["suma"] for a in grupo)
        x["dif_asig"] = x["suma"] - x["asignada"]
        x["clasif"] = "Sin activos asignados" if x["cob"] is None else (
            "Infraseguro" if x["cob"] < cmin / 100 else ("Sobreseguro" if x["cob"] > csob / 100 else "Adecuada"))
        x["restantes"] = max(min((x["hasta"] - corte_a).days, x["dias"]), 0)
        x["calc"] = None if x["prima"] is None else x["prima"] * x["restantes"] / x["dias"]
        x["dif"] = None if x["reg"] is None or x["calc"] is None else x["reg"] - x["calc"]
        x["tiene_sin"] = bool(x["sin"]) or (x["msin"] or 0) > 0
        x["evaluacion"] = "Revelado" if _si_no(x["rev"]) else "Sin revelación: evaluar NIC 37.86/37.89 · Secc. 21"

    s = lambda it, k: sum(x[k] or 0 for x in it)
    sin_cob = [a for a in activos if a["efec"] == 0]
    siniestros = [x for x in polizas if x["tiene_sin"]]
    k = {
        "valorReferencia": s(activos, "ref"), "sumaAsegurada": s(activos, "efec"),
        "deficitCobertura": s(activos, "deficit"), "sinCoberturaLibros": s(sin_cob, "libros"),
        "sinCoberturaReferencia": s(sin_cob, "ref"),
        "sobreseguro": sum(a["exceso"] for a in activos if a["clasif"] == "Sobreseguro"),
        "exposicionMaxima": max(a["no_cubierta"] for a in activos),
        "siniestrosSinRevelar": sum(x["msin"] or 0 for x in siniestros if x["evaluacion"] != "Revelado"),
        "primaRegistrada": s(polizas, "reg"), "primaRecalculada": s(polizas, "calc"), "difPrima": s(polizas, "dif"),
    }
    k["coberturaGlobal"] = None if k["valorReferencia"] == 0 else k["sumaAsegurada"] / k["valorReferencia"]
    k["ajustePrima"] = -k["difPrima"]
    k["mayorPrima"] = _p(p, "mayorPrimaAnticipada")
    k["difMayorPrima"] = None if k["mayorPrima"] is None else k["primaRegistrada"] - k["mayorPrima"]
    k["nSinCobertura"] = len(sin_cob)
    k["nInfraseguro"] = sum(1 for a in activos if a["clasif"] == "Infraseguro")
    k["nVencidas"] = sum(1 for x in polizas if x["estado"] == "Vencida")
    k["nPorVencer"] = sum(1 for x in polizas if x["alerta"] == "Por vencer")
    mayor = max(activos, key=lambda a: a["no_cubierta"])

    # Problemas.
    pr = []
    for x in polizas:
        if x["estado"] == "Vencida":
            pr.append(problema("POLIZA_VENCIDA", f"Póliza {x['id']} ({x['ramo'] or x['aseg']}) vencida el {x['hasta'].isoformat()}: "
                               f"{x['n']} activo(s) sin cobertura al corte; pida la renovación o el endoso vigente.", x["ref"]))
        elif x["estado"] == "No iniciada":
            pr.append(problema("POLIZA_NO_INICIADA", f"Póliza {x['id']}: su vigencia empieza el {x['desde'].isoformat()}, después del corte; "
                               "no cubre los activos al corte.", x["ref"]))
        if x["alerta"]:
            pr.append(problema("POLIZA_POR_VENCER", f"Póliza {x['id']}: vence en {x['por_vencer']} días ({x['hasta'].isoformat()}); "
                               "verifique la renovación posterior al corte.", x["suma"]))
        if x["clasif"] == "Infraseguro" and x["estado"] == "Vigente":
            pr.append(problema("INFRASEGURO_POLIZA", f"Póliza {x['id']}: suma asegurada {m(x['suma'])} cubre el {x['cob'] * 100:.2f} % del valor "
                               f"de referencia {m(x['ref'])}; con la regla proporcional cada siniestro se indemniza al {x['factor'] * 100:.2f} %.", x["deficit"]))
        if x["dif_asig"] < -tol:
            pr.append(problema("SUMAS_ASIGNADAS_EXCEDEN", f"Póliza {x['id']}: las sumas asignadas a los activos ({m(x['asignada'])}) superan la "
                               f"suma asegurada total ({m(x['suma'])}); corrija la asignación.", -x["dif_asig"]))
        if x["dif"] is not None and abs(x["dif"]) > tol:
            pr.append(problema("PRIMA_MAL_DEVENGADA", f"Póliza {x['id']}: prima anticipada registrada {m(x['reg'])} ≠ recalculada {m(x['calc'])} "
                               f"({x['restantes']} de {x['dias']} días por transcurrir) (devengo: NIC 1.27–28; PYMES 2.36).", x["dif"]))
        elif x["reg"] is None and (x["calc"] or 0) > 0.005:
            pr.append(problema("PRIMA_ANTICIPADA_NO_INFORMADA", f"Póliza {x['id']}: al corte quedan {m(x['calc'])} de prima por devengar y no se "
                               "informó la prima anticipada registrada.", x["calc"]))
        if x["tiene_sin"] and x["evaluacion"] != "Revelado":
            pr.append(problema("SINIESTRO_SIN_REVELACION", f"Póliza {x['id']}: siniestro pendiente «{x['sin']}» por {m(x['msin'] or 0)} sin revelación; "
                               "evalúe la pérdida y el reembolso (NIC 37.53, 86, 89; PYMES Sección 21) y la NIA 560 si se resolvió después del corte.",
                               x["msin"] or 0))
    for a in activos:
        if a["clasif"] == "Sin cobertura":
            motivo = {"Sin póliza": "no tiene póliza asignada", "Póliza no encontrada": f"la póliza {a['pol']} no está en el detalle de pólizas",
                     "No iniciada": f"la vigencia de la póliza {a['pol']} empieza después del corte"}.get(
                a["estado"], f"la póliza {a['pol']} está {a['estado'].lower()} al corte")
            pr.append(problema("ACTIVO_SIN_COBERTURA", f"{a['id']} ({a['desc']}): {motivo}; exposición total {m(a['ref'])}.", a["ref"]))
        elif a["clasif"] == "Infraseguro":
            pr.append(problema("INFRASEGURO", f"{a['id']}: cobertura {a['cob'] * 100:.2f} % (< {cmin:g} %); déficit {m(a['deficit'])}.", a["deficit"]))
        elif a["clasif"] == "Sobreseguro":
            pr.append(problema("SOBRESEGURO", f"{a['id']}: suma asegurada {m(a['efec'])} supera el valor de referencia {m(a['ref'])}; la aseguradora "
                               "no indemniza más del valor real: prima pagada en exceso.", a["exceso"]))
    en_libros = [a["id"] for a in activos if a["vref"] is None]
    if en_libros:
        pr.append(problema("REFERENCIA_EN_LIBROS", f"Sin valor de reposición o tasación: {', '.join(en_libros)}; se usó el valor en libros, que "
                           "puede subestimar la exposición. Pida el valor asegurable.", 0))
    if mayor["no_cubierta"] > 0.005:
        pr.append(problema("EXPOSICION_MAXIMA", f"Pérdida total de {mayor['id']} ({mayor['desc']}) no cubierta por {m(mayor['no_cubierta'])} "
                           "(déficit + deducible): evalúe su efecto en el riesgo y la continuidad operativa (NIA 315, 330 y 570).", mayor["no_cubierta"]))
    if k["mayorPrima"] is None:
        pr.append(problema("SIN_MAYOR", "Ingrese el saldo de seguros pagados por anticipado según el mayor para conciliar el detalle de pólizas.", 0))
    elif abs(k["difMayorPrima"]) > tol:
        pr.append(problema("CONCILIACION_PRIMA_MAYOR", f"Prima anticipada del detalle {m(k['primaRegistrada'])} ≠ mayor {m(k['mayorPrima'])}.",
                           k["difMayorPrima"]))

    totales, etiquetas = {}, {}
    for key, lab, v in (
        ("valorReferencia", "Valor de referencia de los activos", k["valorReferencia"]),
        ("sumaAsegurada", "Suma asegurada vigente al corte", k["sumaAsegurada"]),
        ("coberturaGlobal", "Cobertura global (%)", None if k["coberturaGlobal"] is None else k["coberturaGlobal"] * 100),
        ("deficitCobertura", "Déficit de cobertura (exposición no asegurada)", k["deficitCobertura"]),
        ("sinCoberturaLibros", "Activos sin cobertura: valor en libros", k["sinCoberturaLibros"]),
        ("sinCoberturaReferencia", "Activos sin cobertura: valor de referencia", k["sinCoberturaReferencia"]),
        ("sobreseguro", "Sobreseguro (suma sobre el valor de referencia)", k["sobreseguro"]),
        ("exposicionMaxima", "Exposición máxima (pérdida total no cubierta del activo mayor)", k["exposicionMaxima"]),
        ("siniestrosSinRevelar", "Siniestros pendientes sin revelación", k["siniestrosSinRevelar"]),
        ("primaRegistrada", "Prima pagada por anticipado registrada", k["primaRegistrada"]),
        ("primaRecalculada", "Prima pagada por anticipado recalculada", k["primaRecalculada"]),
        ("difMayorPrima", "Diferencia detalle − mayor (prima anticipada)", k["difMayorPrima"]),
        ("ajustePrima", "Ajuste propuesto en resultados (prima anticipada)", k["ajustePrima"]),
    ):
        if v is not None:
            totales[key], etiquetas[key] = r2(v), lab

    filas = [{"id": a["id"], "descripcion": a["desc"], "clase": a["clase"], "valorLibros": r2(a["libros"]), "referencia": r2(a["ref"]),
              "poliza": a["pol"], "estadoPoliza": a["estado"], "sumaAsegurada": r2(a["efec"]),
              "cobertura": "" if a["cob"] is None else r2(a["cob"] * 100), "deficit": r2(a["deficit"]), "clasificacion": a["clasif"],
              "_row": a["_row"]} for a in activos]
    limpia = lambda it: [{kk: (v.isoformat() if hasattr(v, "isoformat") else v) for kk, v in x.items()} for x in it]
    detalle = {"corte": corte_a.isoformat(), "marco": MARCO_PYMES if pymes else MARCO_COMPLETAS, "edicion": edicion_pymes(p) if pymes else "",
               "activos": limpia(activos), "polizas": limpia(polizas), "kpi": k, "mayorActivo": mayor["id"], "parametros": p}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "ajustePrima",
            "exceptions": pr, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Activos", "Activos asegurables (datos del cliente)"),
    ("04_Polizas", "Pólizas (datos del cliente)"), ("05_Vigencia", "Vigencia de pólizas al corte"),
    ("06_Cobertura_activo", "Universo y cobertura por activo"), ("07_Cobertura_poliza", "Cobertura por póliza (infraseguro)"),
    ("08_Deducibles_exposicion", "Deducibles y exposición máxima"), ("09_Sin_cobertura", "Activos sin cobertura"),
    ("10_Prima_anticipada", "Prima pagada por anticipado"), ("11_Siniestros", "Siniestros pendientes y revelación"),
    ("12_Conclusion", "Indicadores y conclusión"), ("13_Ajustes", "Ajustes propuestos y conciliación"),
    ("14_Problemas", "Problemas encontrados"),
]
P = ref("02_Parametros")
ACT, POL, VIG, COB, CPO, DED, PRI, SIN, CON, AJ = (ref(n) for n in (
    "03_Activos", "04_Polizas", "05_Vigencia", "06_Cobertura_activo", "07_Cobertura_poliza", "08_Deducibles_exposicion",
    "10_Prima_anticipada", "11_Siniestros", "12_Conclusion", "13_Ajustes"))
_PAR = ["corte", "marco", "edicion", "coberturaMinima", "sobreseguroDesde", "diasAlerta", "tolerancia", "mayorPrimaAnticipada"]
PAR = {k: f"{P}$B${FILA0 + i}" for i, k in enumerate(_PAR)}


def _rng(h: str, col: str, n: int) -> str:
    return f"{h}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _si(celda: str) -> str:
    """Celda opcional: vacía queda vacía (M22)."""
    return f'IF({celda}="","",{celda})'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, A, PO, k = d["parametros"], d["activos"], d["polizas"], d["kpi"]
    n, npol = len(A), len(PO)
    fa = {a["id"]: FILA0 + i for i, a in enumerate(A)}
    pv = lambda kk: None if p.get(kk) in (None, "") else float(a_num(p.get(kk)))
    fin = lambda nn: FILA0 + nn - 1

    parametros = [
        ["Corte del ejercicio", d["corte"], "Ficha del encargo"],
        ["Marco contable", d["marco"], "Mismo tratamiento en NIIF completas y PYMES: prueba de riesgo, no medición NIIF"],
        ["Edición PYMES", d["edicion"], "2015 y 2025: sin diferencias para esta prueba (VERIFICAR contra el texto oficial)"],
        ["Cobertura mínima (%)", pv("coberturaMinima"), "Juicio del auditor / política de seguros de la entidad"],
        ["Sobreseguro desde (%)", pv("sobreseguroDesde"), "Juicio del auditor"],
        ["Alerta por vencer (días)", pv("diasAlerta"), "Juicio del auditor"],
        ["Tolerancia (importe)", pv("tolerancia"), "Materialidad de ejecución"],
        ["Mayor: seguros pagados por anticipado", pv("mayorPrimaAnticipada"), "Mayor contable"],
    ]

    act = [[a["id"], a["desc"], a["clase"], a["libros"], a["vref"], a["pol"], a["asig"], a["ded"]] for a in A]
    pol = [[x["id"], x["aseg"], x["ramo"], x["desde"], x["hasta"], x["suma"], x["prima"], x["reg"], x["sin"], x["msin"], x["rev"]] for x in PO]

    # 05 · vigencia (fila alineada con 04).
    vig = []
    for i, x in enumerate(PO):
        r = FILA0 + i
        X = lambda c: f"{POL}{c}{r}"
        vig.append([x["id"], x["desde"], x["hasta"], fx(f'{X("E")}-{X("D")}', x["dias"]),
                    fx(f'IF({X("E")}<{PAR["corte"]},"Vencida",IF({X("D")}>{PAR["corte"]},"No iniciada","Vigente"))', x["estado"]),
                    fx(f'IF(E{r}="Vigente",{X("E")}-{PAR["corte"]},"")', x["por_vencer"]),
                    fx(f'IF(F{r}="","",IF(F{r}<={PAR["diasAlerta"]},"Por vencer",""))', x["alerta"])])

    # 06 · cobertura por activo (fila alineada con 03).
    rp, re_, rf_ = _rng(POL, "A", npol), _rng(VIG, "E", npol), _rng(POL, "F", npol)
    raf, rcc = _rng(ACT, "F", n), _rng(COB, "C", n)
    cob = []
    for i, a in enumerate(A):
        r = FILA0 + i
        X = lambda c: f"{ACT}{c}{r}"
        mt = f"MATCH({X('F')},{rp},0)"
        cob.append([
            a["id"], a["pol"], fx(f'IF({X("E")}<>"",{X("E")},{X("D")})', a["ref"]),
            fx(f'IF({X("E")}<>"","Reposición/tasación","Valor en libros")', a["base"]),
            fx(f'IF({X("F")}="","Sin póliza",IF(ISNA({mt}),"Póliza no encontrada",INDEX({re_},{mt})))', a["estado"]),
            fx(f'IF(OR(E{r}="Sin póliza",E{r}="Póliza no encontrada"),0,IF({X("G")}<>"",{X("G")},'
               f'IF(SUMIF({raf},{X("F")},{rcc})=0,0,INDEX({rf_},{mt})*C{r}/SUMIF({raf},{X("F")},{rcc}))))', a["suma"]),
            fx(f'IF(E{r}="Vigente",F{r},0)', a["efec"]),
            fx(f'IF(C{r}=0,"",G{r}/C{r})', a["cob"]),
            fx(f"MAX(C{r}-G{r},0)", a["deficit"]),
            fx(f"MAX(G{r}-C{r},0)", a["exceso"]),
            fx(f'IF(G{r}=0,"Sin cobertura",IF(H{r}="","",IF(H{r}<{PAR["coberturaMinima"]}/100,"Infraseguro",'
               f'IF(H{r}>{PAR["sobreseguroDesde"]}/100,"Sobreseguro","Adecuada"))))', a["clasif"]),
        ])

    # 07 · cobertura por póliza (fila alineada con 04).
    rcf = _rng(COB, "F", n)
    cpo = []
    for i, x in enumerate(PO):
        r = FILA0 + i
        cpo.append([
            x["id"], fx(f"{VIG}E{r}", x["estado"]), fx(f"{POL}F{r}", x["suma"]),
            fx(f"SUMIF({raf},A{r},{rcc})", x["ref"]), fx(f"COUNTIF({raf},A{r})", x["n"]),
            fx(f'IF(D{r}=0,"",C{r}/D{r})', x["cob"]), fx(f'IF(F{r}="","",MIN(F{r},1))', x["factor"]),
            fx(f"MAX(D{r}-C{r},0)", x["deficit"]), fx(f"SUMIF({raf},A{r},{rcf})", x["asignada"]), fx(f"C{r}-I{r}", x["dif_asig"]),
            fx(f'IF(F{r}="","Sin activos asignados",IF(F{r}<{PAR["coberturaMinima"]}/100,"Infraseguro",'
               f'IF(F{r}>{PAR["sobreseguroDesde"]}/100,"Sobreseguro","Adecuada")))', x["clasif"]),
        ])

    # 08 · deducibles y pérdida no cubierta ante pérdida total (fila alineada con 03).
    ded = []
    for i, a in enumerate(A):
        r = FILA0 + i
        ded.append([
            a["id"], fx(f"{COB}C{r}", a["ref"]), fx(f"IF(B{r}=0,0,MIN({COB}G{r}/B{r},1))", a["factor"]),
            fx(f"B{r}*C{r}", a["indem_bruta"]), fx(f'IF({ACT}H{r}="",0,{ACT}H{r})', a["ded_pct"]),
            fx(f"IF(D{r}=0,0,MIN(B{r}*E{r}/100,D{r}))", a["deducible"]), fx(f"D{r}-F{r}", a["indem"]), fx(f"B{r}-G{r}", a["no_cubierta"]),
        ])

    # 09 · activos sin cobertura.
    S = [a for a in A if a["efec"] == 0]
    sin_cob = []
    for i, a in enumerate(S):
        s = fa[a["id"]]
        sin_cob.append([a["id"], a["desc"], a["pol"], fx(f"{COB}E{s}", a["estado"]), fx(f"{ACT}D{s}", a["libros"]), fx(f"{COB}C{s}", a["ref"])])

    # 10 · prima pagada por anticipado (fila alineada con 04).
    pri = []
    for i, x in enumerate(PO):
        r = FILA0 + i
        pri.append([
            x["id"], fx(_si(f"{POL}G{r}"), x["prima"]), fx(f"{VIG}D{r}", x["dias"]),
            fx(f"MAX(MIN({POL}E{r}-{PAR['corte']},C{r}),0)", x["restantes"]),
            fx(f'IF(B{r}="","",B{r}*D{r}/C{r})', x["calc"]), fx(_si(f"{POL}H{r}"), x["reg"]),
            fx(f'IF(OR(E{r}="",F{r}=""),"",F{r}-E{r})', x["dif"]),
        ])

    # 11 · siniestros pendientes.
    SI = [(i, x) for i, x in enumerate(PO) if x["tiene_sin"]]
    sini = []
    for j, (i, x) in enumerate(SI):
        s = FILA0 + i
        sini.append([x["id"], x["aseg"], x["sin"], fx(_si(f"{POL}J{s}"), x["msin"]),
                     x["rev"], fx(f"{VIG}E{s}", x["estado"]),
                     fx(f'IF(OR({POL}K{s}="Sí",{POL}K{s}="Si"),"Revelado","Sin revelación: evaluar NIC 37.86/37.89 · Secc. 21")', x["evaluacion"])])
    nsi = len(SI)

    # 12 · indicadores y conclusión.  Columnas: concepto, importe, porcentaje, cantidad.
    b = lambda kk: f"B{FILA0 + kk}"
    con = [
        ["Valor de referencia de los activos", fx(f"SUM({_rng(COB, 'C', n)})", k["valorReferencia"]), None, None],
        ["Suma asegurada vigente al corte", fx(f"SUM({_rng(COB, 'G', n)})", k["sumaAsegurada"]), None, None],
        ["% de cobertura global = suma asegurada / referencia", None, fx(f'IF({b(0)}=0,"",{b(1)}/{b(0)})', k["coberturaGlobal"]), None],
        ["Déficit de cobertura = Σ max(referencia − suma, 0)", fx(f"SUM({_rng(COB, 'I', n)})", k["deficitCobertura"]), None, None],
        ["Activos sin cobertura: valor en libros (cantidad a la derecha)", fx(f"SUMIF({_rng(COB, 'G', n)},0,{_rng(ACT, 'D', n)})", k["sinCoberturaLibros"]),
         None, fx(f"COUNTIF({_rng(COB, 'G', n)},0)", k["nSinCobertura"])],
        ["Activos sin cobertura: valor de referencia", fx(f"SUMIF({_rng(COB, 'G', n)},0,{_rng(COB, 'C', n)})", k["sinCoberturaReferencia"]), None, None],
        ["Activos con infraseguro (cantidad)", None, None, fx(f'COUNTIF({_rng(COB, "K", n)},"Infraseguro")', k["nInfraseguro"])],
        ["Sobreseguro", fx(f'SUMIF({_rng(COB, "K", n)},"Sobreseguro",{_rng(COB, "J", n)})', k["sobreseguro"]), None, None],
        [f"Exposición máxima (pérdida total no cubierta; activo {d['mayorActivo']})", fx(f"MAX({_rng(DED, 'H', n)})", k["exposicionMaxima"]), None, None],
        ["Pólizas vencidas al corte (cantidad)", None, None, fx(f'COUNTIF({_rng(VIG, "E", npol)},"Vencida")', k["nVencidas"])],
        ["Pólizas por vencer (cantidad)", None, None, fx(f'COUNTIF({_rng(VIG, "G", npol)},"Por vencer")', k["nPorVencer"])],
        ["Siniestros pendientes sin revelación", fx(f'SUMIF({_rng(SIN, "G", nsi)},"Sin revelación*",{_rng(SIN, "D", nsi)})', k["siniestrosSinRevelar"])
         if nsi else fx("0", 0.0), None, None],
        ["Ajuste propuesto en resultados (prima anticipada)", fx(f"{AJ}B{FILA0 + 3}", k["ajustePrima"]), None, None],
        ["Conclusión: la cobertura es evidencia de riesgo y continuidad operativa (NIA 315, 330, 570); no concluye cumplimiento de las NIIF.",
         None, None, None],
    ]

    # 13 · ajustes y conciliación.
    c = lambda kk: f"B{FILA0 + kk}"
    ajus = [
        ["Prima anticipada registrada (detalle)", fx(f"SUM({_rng(PRI, 'F', npol)})", k["primaRegistrada"]), "", "", "Detalle de pólizas"],
        ["Prima anticipada recalculada (días por transcurrir)", fx(f"SUM({_rng(PRI, 'E', npol)})", k["primaRecalculada"]), "", "",
         "NIC 1.27–28; PYMES 2.36 (devengo)"],
        ["Registrada − recalculada (pólizas con registro)", fx(f"SUM({_rng(PRI, 'G', npol)})", k["difPrima"]), "", "", ""],
        ["Ajuste en resultados = −(registrada − recalculada)", fx(f"-{c(2)}", k["ajustePrima"]), "Seguros pagados por anticipado",
         "Gasto de seguros", "Si es negativo: débito a gasto de seguros y crédito al anticipo"],
        ["Seguros pagados por anticipado según el mayor", fx(_si(PAR["mayorPrimaAnticipada"]), k["mayorPrima"]), "", "", "Mayor contable"],
        ["Diferencia detalle − mayor", fx(f'IF({c(4)}="","",{c(0)}-{c(4)})', k["difMayorPrima"]), "", "", ""],
    ]

    celda = {"valorReferencia": f"{CON}B{FILA0}", "sumaAsegurada": f"{CON}B{FILA0 + 1}", "coberturaGlobal": f"{CON}C{FILA0 + 2}*100",
             "deficitCobertura": f"{CON}B{FILA0 + 3}", "sinCoberturaLibros": f"{CON}B{FILA0 + 4}",
             "sinCoberturaReferencia": f"{CON}B{FILA0 + 5}", "sobreseguro": f"{CON}B{FILA0 + 7}", "exposicionMaxima": f"{CON}B{FILA0 + 8}",
             "siniestrosSinRevelar": f"{CON}B{FILA0 + 11}", "primaRegistrada": f"{AJ}B{FILA0}", "primaRecalculada": f"{AJ}B{FILA0 + 1}",
             "difMayorPrima": f"{AJ}B{FILA0 + 5}", "ajustePrima": f"{AJ}B{FILA0 + 3}"}
    valor = {**k, "coberturaGlobal": None if k["coberturaGlobal"] is None else k["coberturaGlobal"] * 100}
    resumen = [[res["labels"][kk], fx(celda[kk], valor[kk])] for kk in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Activos", "Activos asegurables (datos del cliente)",
             [["Código", "t"], ["Descripción", "t"], ["Clase", "t"], ["Valor en libros", "n"], ["Valor de referencia", "n"], ["Póliza", "t"],
              ["Suma asignada", "n"], ["Deducible %", "n"]], act,
             ["TOTAL", "", "", suma("D", fin(n), sum(a["libros"] for a in A)), None, "", None, None]),
        hoja("04_Polizas", "Pólizas (datos del cliente)",
             [["Póliza", "t"], ["Aseguradora", "t"], ["Ramo", "t"], ["Vigencia desde", "d"], ["Vigencia hasta", "d"], ["Suma asegurada total", "n"],
              ["Prima total", "n"], ["Prima anticipada registrada", "n"], ["Siniestro pendiente", "t"], ["Monto del siniestro", "n"],
              ["Revelado", "t"]], pol),
        hoja("05_Vigencia", "Vigencia de pólizas al corte",
             [["Póliza", "t"], ["Desde", "d"], ["Hasta", "d"], ["Días de vigencia", "i"], ["Estado al corte", "t"], ["Días por vencer", "i"],
              ["Alerta", "t"]], vig),
        hoja("06_Cobertura_activo", "Universo y cobertura por activo",
             [["Código", "t"], ["Póliza", "t"], ["Valor de referencia", "n"], ["Base de referencia", "t"], ["Estado de la póliza", "t"],
              ["Suma asegurada asignada", "n"], ["Suma asegurada vigente", "n"], ["% cobertura", "p"], ["Déficit", "n"], ["Exceso", "n"],
              ["Clasificación", "t"]], cob,
             ["TOTAL", "", suma("C", fin(n), k["valorReferencia"]), "", "", None, suma("G", fin(n), k["sumaAsegurada"]), None,
              suma("I", fin(n), k["deficitCobertura"]), None, ""]),
        hoja("07_Cobertura_poliza", "Cobertura por póliza (infraseguro)",
             [["Póliza", "t"], ["Estado", "t"], ["Suma asegurada total", "n"], ["Referencia asignada", "n"], ["Activos", "i"], ["% cobertura", "p"],
              ["Factor proporcional", "p"], ["Déficit", "n"], ["Sumas asignadas", "n"], ["Total − asignadas", "n"], ["Clasificación", "t"]], cpo),
        hoja("08_Deducibles_exposicion", "Deducibles y exposición máxima",
             [["Código", "t"], ["Pérdida total (referencia)", "n"], ["Factor proporcional", "p"], ["Indemnización bruta", "n"], ["Deducible %", "n"],
              ["Deducible", "n"], ["Indemnización neta", "n"], ["Pérdida no cubierta", "n"]], ded,
             ["TOTAL", None, None, None, None, suma("F", fin(n), sum(a["deducible"] for a in A)), None, suma("H", fin(n), sum(a["no_cubierta"] for a in A))]),
        hoja("09_Sin_cobertura", "Activos sin cobertura",
             [["Código", "t"], ["Descripción", "t"], ["Póliza", "t"], ["Motivo", "t"], ["Valor en libros", "n"], ["Valor de referencia", "n"]], sin_cob,
             ["TOTAL", "", "", "", suma("E", fin(len(S)), k["sinCoberturaLibros"]), suma("F", fin(len(S)), k["sinCoberturaReferencia"])] if S else None),
        hoja("10_Prima_anticipada", "Prima pagada por anticipado",
             [["Póliza", "t"], ["Prima total", "n"], ["Días de vigencia", "i"], ["Días por transcurrir", "i"], ["Anticipada recalculada", "n"],
              ["Anticipada registrada", "n"], ["Registrada − recalculada", "n"]], pri,
             ["TOTAL", None, None, None, suma("E", fin(npol), k["primaRecalculada"]), suma("F", fin(npol), k["primaRegistrada"]),
              suma("G", fin(npol), k["difPrima"])] if npol else None),
        hoja("11_Siniestros", "Siniestros pendientes y revelación",
             [["Póliza", "t"], ["Aseguradora", "t"], ["Siniestro", "t"], ["Monto", "n"], ["Revelado", "t"], ["Estado de la póliza", "t"],
              ["Evaluación", "t"]], sini),
        hoja("12_Conclusion", "Indicadores y conclusión", [["Indicador", "t"], ["Importe", "n"], ["Porcentaje", "p"], ["Cantidad", "i"]], con),
        hoja("13_Ajustes", "Ajustes propuestos y conciliación",
             [["Concepto", "t"], ["Importe", "n"], ["Débito (si positivo)", "t"], ["Crédito (si positivo)", "t"], ["Base", "t"]], ajus),
        hoja("14_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -------------------------------------------------------------------

def definicion() -> dict:
    act = ("Una fila por activo asegurable (excluya terrenos): código, descripción, clase, valor en libros, valor de referencia "
           "(reposición o tasación), póliza asignada, suma asegurada asignada (en blanco: prorrata de la póliza) y deducible %. Sin filas de total.")
    pol = ("Una fila por póliza: número, aseguradora, ramo, vigencia desde y hasta, suma asegurada total, prima total, prima pagada por "
           "anticipado registrada al corte y, si hay, siniestro pendiente, monto y si está revelado (Sí/No).")
    return {
        "name": "Cobertura de seguros de activos",
        "area": "Seguros",
        "processor": "seguros_cobertura",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Compara los activos registrados con las pólizas vigentes al corte: % de cobertura, déficit (infraseguro), sobreseguro, "
                    "deducibles, activos sin cobertura, exposición máxima y siniestros pendientes; recalcula la prima pagada por anticipado. "
                    "Es una prueba de riesgo y continuidad operativa: no concluye cumplimiento de las NIIF por sí sola."),
        "source": {"organization": "IFRS Foundation (texto en español del Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIC 1 párr. 27–28 (base de acumulación o devengo: prima anticipada); NIC 37 párr. 53 (reembolsos), 86 (revelación "
                                "de pasivos contingentes), 89 (activos contingentes); NIC 16 párr. 65–66 (compensaciones de terceros por "
                                "elementos deteriorados o perdidos). Párrafos no leídos en esta versión contra el texto oficial: VERIFICAR."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015 y 2025: Sección 2 (2.36, devengo), Sección 4 (presentación del anticipo como "
                                      "activo corriente), Sección 21 (21.9 reembolsos, 21.15 pasivos contingentes, 21.16 activos contingentes), "
                                      "Sección 17 (compensación de terceros). VERIFICAR la numeración y el texto de cada edición."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 315 (Revisada 2019)", "section": "(VERIFICAR párrafos)", "requirement": "Entender el entorno y los riesgos: pérdida de activos no asegurados como factor de riesgo."},
            {"document": "NIA 330", "section": "(VERIFICAR párrafos)", "requirement": "Respuestas a los riesgos valorados; evidencia sobre la cobertura."},
            {"document": "NIA 570 (Revisada)", "section": "párr. 10–16 (VERIFICAR)", "requirement": "Empresa en marcha: pérdida no asegurada de activos clave."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del maestro de activos y del detalle de pólizas."},
            {"document": "NIA 501 / NIA 560", "section": "(VERIFICAR párrafos)", "requirement": "Litigios y reclamaciones (siniestros) y hechos posteriores al cierre."},
        ],
        "calculo": [
            "Referencia = valor de reposición o tasación; si falta, valor en libros (se señala).",
            "Suma asegurada del activo = la asignada o, si falta, suma total de la póliza × referencia ÷ referencia de todos sus activos; cuenta solo si la póliza está vigente al corte.",
            "% cobertura = suma asegurada ÷ referencia; déficit = max(referencia − suma, 0); infraseguro si % < mínimo; sobreseguro si % > umbral.",
            "Regla proporcional: indemnización = pérdida × min(suma ÷ referencia, 1) − deducible; pérdida no cubierta = referencia − indemnización neta.",
            "Exposición máxima = mayor pérdida total no cubierta de un solo activo (déficit + deducible).",
            "Prima anticipada al corte = prima × días por transcurrir ÷ días de vigencia (devengo, NIC 1.27–28; PYMES 2.36), frente a la registrada y al mayor.",
            "Siniestro pendiente sin revelación: evaluar pasivo o activo contingente (NIC 37.86, 89; PYMES 21.15–21.16).",
        ],
        "fields": _ACTIVOS, "rules": [], "control": CONTROL, "primary": "ajustePrima",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[a, b] for a, b in CEDULAS],
        "program": [
            {"code": "INS-01", "objective": "Universo de activos vs pólizas", "risk": "Activos registrados sin póliza", "assertion": "Integridad (riesgo)",
             "procedure": "Cruzar el maestro de activos con el detalle de pólizas", "evidence": "Maestro de activos, pólizas y endosos",
             "criterion": "Todo activo significativo con póliza vigente", "source": "NIA 315 · NIA 330"},
            {"code": "INS-02", "objective": "Vigencia", "risk": "Pólizas vencidas o no renovadas al corte", "assertion": "Riesgo operativo",
             "procedure": "Comparar la vigencia de cada póliza con la fecha de corte y alertar las próximas a vencer", "evidence": "Pólizas y renovaciones",
             "criterion": "Póliza vigente al corte", "source": "NIA 330 · NIA 570"},
            {"code": "INS-03", "objective": "Suma asegurada e infraseguro", "risk": "Suma asegurada inferior al valor de reposición", "assertion": "Riesgo de pérdida",
             "procedure": "Calcular el % de cobertura por activo y por póliza y aplicar la regla proporcional", "evidence": "Tasaciones, valores de reposición",
             "criterion": "Cobertura ≥ mínimo definido", "source": "Especificación MÓDULO 09 · NIA 315"},
            {"code": "INS-04", "objective": "Sobreseguro y deducibles", "risk": "Primas pagadas en exceso; deducibles altos", "assertion": "Riesgo",
             "procedure": "Identificar sumas sobre el valor real y calcular el deducible ante pérdida total", "evidence": "Condiciones particulares de la póliza",
             "criterion": "Sumas razonables frente al valor asegurable", "source": "Especificación MÓDULO 09"},
            {"code": "INS-05", "objective": "Exposición máxima", "risk": "Pérdida no cubierta de un activo clave", "assertion": "Continuidad operativa",
             "procedure": "Determinar la mayor pérdida total no cubierta y evaluar su efecto", "evidence": "Cédula de exposición",
             "criterion": "Exposición informada al encargado del gobierno", "source": "NIA 570 · NIA 260"},
            {"code": "INS-06", "objective": "Prima pagada por anticipado", "risk": "Anticipo sobrevalorado o gasto no devengado", "assertion": "Valoración / Corte",
             "procedure": "Recalcular la prima por devengar al corte y conciliar con el mayor", "evidence": "Pólizas, facturas de prima, mayor",
             "criterion": "Diferencia dentro de tolerancia", "source": "NIC 1.27–28 · PYMES 2.36"},
            {"code": "INS-07", "objective": "Siniestros pendientes y revelación", "risk": "Contingencia no revelada o reembolso reconocido sin certeza", "assertion": "Presentación y revelación",
             "procedure": "Revisar siniestros pendientes, su estado y su revelación", "evidence": "Reclamos, cartas de la aseguradora, notas",
             "criterion": "Revelado según NIC 37 / Sección 21", "source": "NIC 37.53, 86, 89 · PYMES 21 · NIA 501 · NIA 560"},
        ],
        "requests": [
            req("RQ-001", "Maestro de activos asegurables con póliza, valor de referencia y suma asegurada", "activos", "INS-01",
                "Población a cruzar con las pólizas", content=act),
            req("RQ-002", "Detalle de pólizas vigentes y vencidas en el ejercicio", "polizas", "INS-02", "Vigencia, sumas, primas y siniestros", content=pol),
            req("RQ-003", "Pólizas y endosos (condiciones particulares, deducibles)", None, "INS-04", "Sustento de sumas y deducibles", formats=("pdf",), use="soporte"),
            req("RQ-004", "Tasaciones o valores de reposición", None, "INS-03", "Sustento del valor de referencia", required=False, formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-005", "Reclamos de siniestros y comunicaciones de la aseguradora", None, "INS-07", "Estado de los siniestros pendientes", required=False,
                formats=("pdf",), use="soporte"),
            req("RQ-006", "Mayor de seguros pagados por anticipado y facturas de prima", None, "INS-06", "Conciliación de la prima anticipada",
                formats=("xlsx", "pdf"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


def _a(id, desc, clase, libros, **x):
    return {"id": id, "descripcion": desc, "clase": clase, "valor_libros": libros, "_row": 2, **x}


def _pz(id, aseg, ramo, desde, hasta, suma_total, **x):
    return {"id": id, "aseguradora": aseg, "ramo": ramo, "vigencia_desde": desde, "vigencia_hasta": hasta, "suma_total": suma_total, "_row": 2, **x}


# Ejemplo de control (M19), corte 2025-12-31 (aseguradoras ficticias):
# POL-01 incendio: suma 700.000 / referencia 950.000 (EDIF-01 650.000 + BOD-01 300.000) = 73,68 % → infraseguro;
#   prorrata EDIF-01 = 700.000 × 650.000 ÷ 950.000 = 478.947,37; déficit 171.052,63.
#   Pérdida total EDIF-01: indemnización 478.947,37 − deducible 2 % × 650.000 (13.000) = 465.947,37 → no cubierta 184.052,63 (exposición máxima).
# POL-02 vehículos: prima 5.475 × 60 ÷ 365 = 900 recalculada vs 2.500 registrada → sobrevaloración 1.600; siniestro 18.000 sin revelar.
# POL-03 vencida el 15-dic-2025 y POL-05 no iniciada: EQC-01, EQC-02 y BOD-02 sin cobertura; MOB-01 sin póliza; GEN-01 póliza inexistente.
# Totales: referencia 1.499.000; suma vigente 1.050.000 (70,05 %); déficit 482.000; sobreseguro 33.000 (VEH-02 25.000 + VEH-03 8.000).
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "coberturaMinima": 80, "sobreseguroDesde": 120, "diasAlerta": 30, "tolerancia": 1,
                   "mayorPrimaAnticipada": 8000},
    "datasets": {
        "activos": [
            _a("EDIF-01", "Edificio administrativo", "Edificios", "437500", valor_referencia="650000", poliza="POL-01", deducible_pct="2"),
            _a("BOD-01", "Bodega central", "Edificios", "180000", valor_referencia="300000", poliza="POL-01", deducible_pct="2"),
            _a("MAQ-01", "Línea de envasado", "Maquinaria", "40000", valor_referencia="160000", poliza="POL-04", suma_asignada="160000", deducible_pct="10"),
            _a("MAQ-02", "Compresor industrial", "Maquinaria", "25000", valor_referencia="60000", poliza="POL-04", suma_asignada="40000", deducible_pct="10"),
            _a("VEH-01", "Camioneta 4x4", "Vehículos", "21600", valor_referencia="35000", poliza="POL-02", suma_asignada="35000", deducible_pct="5"),
            _a("VEH-02", "Camión de reparto", "Vehículos", "60000", valor_referencia="70000", poliza="POL-02", suma_asignada="95000", deducible_pct="5"),
            _a("VEH-03", "Furgoneta", "Vehículos", "12000", poliza="POL-02", suma_asignada="20000", deducible_pct="5"),
            _a("EQC-01", "Servidores", "Equipo de cómputo", "10000", valor_referencia="30000", poliza="POL-03", suma_asignada="30000"),
            _a("EQC-02", "Computadores portátiles", "Equipo de cómputo", "6000", valor_referencia="12000", poliza="POL-03", suma_asignada="10000"),
            _a("BOD-02", "Bodega norte", "Edificios", "90000", valor_referencia="110000", poliza="POL-05", suma_asignada="80000"),
            _a("MOB-01", "Mobiliario de oficinas", "Muebles y enseres", "8000", valor_referencia="15000"),
            _a("GEN-01", "Generador eléctrico", "Maquinaria", "15000", valor_referencia="45000", poliza="POL-09", suma_asignada="45000"),
        ],
        "polizas": [
            _pz("POL-01", "Aseguradora Alfa S.A.", "Incendio y líneas aliadas", "2025-07-01", "2026-07-01", "700000", prima_total="7300", prima_anticipada="3640"),
            _pz("POL-02", "Aseguradora Beta S.A.", "Vehículos", "2025-03-01", "2026-03-01", "150000", prima_total="5475", prima_anticipada="2500",
                siniestro="Choque del camión VEH-02", monto_siniestro="18000", siniestro_revelado="No"),
            _pz("POL-03", "Aseguradora Gamma S.A.", "Equipo electrónico", "2024-12-15", "2025-12-15", "40000", prima_total="1200", prima_anticipada="0"),
            _pz("POL-04", "Aseguradora Alfa S.A.", "Rotura de maquinaria", "2025-01-20", "2026-01-20", "200000", prima_total="3650", prima_anticipada="200",
                siniestro="Daño en compresor", monto_siniestro="5000", siniestro_revelado="Sí"),
            _pz("POL-05", "Aseguradora Beta S.A.", "Incendio bodega norte", "2026-01-15", "2027-01-15", "80000", prima_total="1460", prima_anticipada="1460"),
        ],
    },
}

_MIN = {"activos": [_a("A-1", "Equipo", "Maquinaria", "1000")], "polizas": []}
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025"}, EJEMPLO["corte"]),
    ("minimo", _MIN, {}, "2025-12-31"),
]
