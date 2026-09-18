"""Orquesta el análisis de pérdidas crediticias esperadas de cuentas por cobrar.

Secuencia: leer los tres cortes -> derivar tasas de la cohorte más antigua ->
anclar la exposición a los estados financieros -> separar los saldos de evaluación
individual -> medir -> comparar contra la política del cliente -> armar hallazgos
y pendientes. Ningún parámetro se inventa: lo que falta se reporta.
"""
from __future__ import annotations

from typing import Any

from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO, desdoblar
from backend.app.aud.pce_cxc.cohortes import tasas_por_permanencia
from backend.app.aud.pce_cxc.lectura import leer_cartera
from backend.app.aud.pce_cxc.motor import (
    ParametrosECL, evaluar_individual, medir_ecl, redondear,
)

SEGMENTOS = ("NO-RELACIONADOS", "RELACIONADOS")


def analizar(cortes: list[dict[str, Any]], parametros: dict[str, Any]) -> dict[str, Any]:
    if len(cortes) != 3:
        raise ValueError("Se requieren los tres análisis de antigüedad: sin tres cierres no existe "
                         "una cohorte con ventana completa de 24 meses")
    umbral_dias = int(parametros.get("umbral_dias_incumplimiento") or 730)
    bandas = desdoblar(BANDAS_POR_DEFECTO, umbral_dias)
    nombres = [b["nombre"] for b in bandas]

    leidos = [leer_cartera(c["contenido"], c["nombre"], c["fecha"], bandas,
                           c.get("hoja"), c.get("mapeo")) for c in cortes]
    cohorte, _intermedio, actual = leidos

    coh = tasas_por_permanencia(cohorte["filas"], actual["filas"])
    tasas = coh["tasas"]

    # Evaluación individual: los clientes por encima del umbral salen de la matriz.
    umbral_ind = float(parametros.get("umbral_individual") or 0)
    por_cliente: dict[tuple[str, str], float] = {}
    for f in actual["filas"]:
        clave = (f["segmento"], f["cliente"] or "(sin nombre)")
        por_cliente[clave] = por_cliente.get(clave, 0.0) + f["saldo"]
    individuales = {k for k, v in por_cliente.items() if umbral_ind and v > umbral_ind}

    # Exposición por segmento y banda, anclada a los estados financieros.
    eeff = parametros.get("eeff") or {}
    meta = {"NO-RELACIONADOS": float(eeff.get("no_relacionados") or 0),
            "RELACIONADOS": float(eeff.get("relacionados") or 0)}
    ancla = sum(meta.values()) > 0
    total_seg = {s: 0.0 for s in SEGMENTOS}
    for f in actual["filas"]:
        total_seg[f["segmento"]] += f["saldo"]
    factor, sin_estratificar = {}, {}
    for s in SEGMENTOS:
        if not ancla:
            factor[s], sin_estratificar[s] = 1.0, 0.0
        elif total_seg[s] > 0:
            factor[s], sin_estratificar[s] = meta[s] / total_seg[s], 0.0
        else:
            factor[s], sin_estratificar[s] = 1.0, meta[s]

    # La matriz se mide POR SEGMENTO: terceros y relacionadas tienen comportamiento
    # de pago distinto y no pueden agruparse (NIIF 9 B5.5.35).
    colectiva = {s: {b: 0.0 for b in nombres} for s in SEGMENTOS}
    casos: dict[tuple[str, str], dict[str, Any]] = {}
    for f in actual["filas"]:
        clave = (f["segmento"], f["cliente"] or "(sin nombre)")
        saldo = f["saldo"] * factor[f["segmento"]]
        if clave in individuales:
            caso = casos.setdefault(clave, {"identificacion": clave[1], "segmento": clave[0],
                                            "saldo": 0.0, "bandas": {}})
            caso["saldo"] += saldo
            caso["bandas"][f["banda"]] = caso["bandas"].get(f["banda"], 0.0) + saldo
        else:
            colectiva[f["segmento"]][f["banda"]] += saldo

    # Tasas aplicadas: las observadas de cada segmento, o las sustituidas con
    # justificación escrita. Sin ninguna de las dos, la banda queda sin medir.
    sustitutas = parametros.get("tasas_sustitutas") or {}
    factores_solicitados = parametros.get("factor_prospectivo") or {}
    justificacion = str(parametros.get("justificacion_prospectivo") or "")
    aplicadas: dict[str, dict[str, float]] = {}
    for s in SEGMENTOS:
        aplicadas[s] = {}
        for b in nombres:
            obs = tasas.get(s, {}).get(b)
            sus = sustitutas.get(f"{s}|{b}")
            if sus and str(sus.get("justificacion", "")).strip():
                aplicadas[s][b] = float(sus["tasa"])
            elif obs is not None:
                aplicadas[s][b] = obs

    # El ajuste prospectivo pedido solo se aplica si viene con justificación
    # escrita (NIIF 9 B5.5.51-52). Sin ella se ignora en silencio aquí (nunca
    # se levanta una excepción por esto) y queda expuesto como hallazgo.
    factor_prospectivo_aplicado: dict[str, float] = {}
    for s in SEGMENTOS:
        solicitado = float(factores_solicitados.get(s, 1.0))
        if solicitado != 1.0 and not justificacion.strip():
            factor_prospectivo_aplicado[s] = 1.0
        else:
            factor_prospectivo_aplicado[s] = solicitado

    evaluaciones = parametros.get("evaluaciones_individuales") or {}
    lista_casos = []
    for clave, caso in casos.items():
        est = evaluaciones.get(f"{clave[0]}|{clave[1]}")
        provisional = sum(v * aplicadas[clave[0]].get(b, 0.0) for b, v in caso["bandas"].items())
        propia = bool(est and str(est.get("justificacion", "")).strip())
        ecl_caso = float(est["ecl"]) if propia else provisional
        lista_casos.append({
            "identificacion": f"{caso['identificacion']} ({clave[0]})", "tramo": None,
            "saldo": caso["saldo"], "recuperacion_estimada": caso["saldo"] - ecl_caso,
            "sustento": (est or {}).get("justificacion",
                                        "Medido con la tasa de la matriz (provisional)"),
        })

    saldo_contable = sum(meta.values()) if ancla else None
    # Se mide cada segmento por separado y luego se consolidan los tramos.
    medidos, tramos, ecl_colectiva, exp_colectiva, sin_medir = {}, [], 0.0, 0.0, 0.0
    for s in SEGMENTOS:
        p = ParametrosECL(tasas_perdida=aplicadas[s], lgd=1.0,
                          ajuste_prospectivo=factor_prospectivo_aplicado[s] - 1.0,
                          justificacion_ajuste=justificacion,
                          fuente_tasas="Permanencia a 24 meses sobre la cohorte del corte más antiguo")
        medidos[s] = medir_ecl(colectiva[s], p)
        for t in medidos[s]["tramos"]:
            tramos.append({**t, "segmento": s})
        ecl_colectiva += medidos[s]["ecl_total"]
        exp_colectiva += medidos[s]["exposicion_total"]
        sin_medir += medidos[s]["exposicion_sin_medir"]

    individual = evaluar_individual(lista_casos)
    exposicion_total = redondear(exp_colectiva + individual["saldo_total"])
    ecl_total = redondear(ecl_colectiva + individual["ecl_total"])
    resumen = {
        "colectivo": {"tramos": tramos, "exposicion_total": redondear(exp_colectiva),
                      "ecl_total": redondear(ecl_colectiva),
                      "exposicion_sin_medir": redondear(sin_medir),
                      "descuento_aplicado": False,
                      "ajuste_prospectivo": dict(factor_prospectivo_aplicado),
                      "justificacion_ajuste": justificacion,
                      "fuente_tasas": "Permanencia a 24 meses"},
        "individual": individual,
        "exposicion_total": exposicion_total,
        "ecl_total": ecl_total,
        "tributario": {
            "limite_ejercicio_1pct": redondear(exposicion_total * 0.01),
            "tope_acumulado_10pct": redondear(exposicion_total * 0.10),
            "excede_limite_ejercicio": ecl_total > exposicion_total * 0.01,
            "nota": "Límite de deducción (LORTI art. 10 num. 11). No condiciona la estimación "
                    "contable; la diferencia es temporaria.",
        },
    }
    if saldo_contable is not None:
        diferencia = redondear(exposicion_total - float(saldo_contable))
        resumen["conciliacion"] = {"cartera_total": exposicion_total,
                                   "saldo_contable": redondear(float(saldo_contable)),
                                   "diferencia": diferencia, "cuadra": abs(diferencia) < 0.01}

    total_sin_estratificar = redondear(sum(sin_estratificar.values()))
    exposicion = {
        "colectiva": resumen["colectivo"]["exposicion_total"],
        "individual": resumen["individual"]["saldo_total"],
        "sin_estratificar": total_sin_estratificar,
        "total": redondear(resumen["exposicion_total"] + total_sin_estratificar),
        "segun_archivo": actual["total_saldo"],
        "factores_anclaje": factor,
    }

    politica = _comparar_politica(parametros.get("politica") or {}, bandas, colectiva, tramos)
    hallazgos = _hallazgos(resumen, politica, parametros, factor_prospectivo_aplicado, justificacion)
    pendientes = _pendientes(resumen, parametros, coh, leidos)

    return {
        "exposicion": exposicion, "tasas": tasas, "detalle_cohorte": coh["detalle"],
        "trazabilidad": coh["trazabilidad"], "anomalias": coh["anomalias"],
        "matriz": resumen["colectivo"],
        "individual": resumen["individual"], "conciliacion": resumen.get("conciliacion", {
            "cartera_total": exposicion["total"], "saldo_contable": None,
            "diferencia": None, "cuadra": None}),
        "tributario": resumen["tributario"], "politica": politica,
        "ecl_total": resumen["ecl_total"], "hallazgos": hallazgos, "pendientes": pendientes,
        "bitacora": {
            "bandas": nombres, "umbral_incumplimiento": umbral_dias,
            "umbral_individual": umbral_ind,
            "cortes": [{"archivo": c["nombre"], "fecha": c["fecha"].isoformat(),
                        "hoja": l["hoja"], "fila_encabezado": l["fila_encabezado"],
                        "mapeo": l["mapeo"], "formato_fecha": l["formato_fecha"],
                        "documentos": len(l["filas"]), "duplicados_exactos": l["duplicados_exactos"],
                        "documentos_repetidos": l["documentos_repetidos"],
                        "descartados": len(l["descartados"]), "total": l["total_saldo"]}
                       for c, l in zip(cortes, leidos)],
            "metodo": "Permanencia a 24 meses", "descuento": "No aplicado (NIIF 9 B5.5.44)",
        },
    }


def _comparar_politica(politica, bandas, colectiva, tramos):
    """Compara la matriz observada contra la política fija del cliente.

    La política del cliente es un único porcentaje por banda (`{banda: tasa}`),
    sin distinción de segmento, así que aquí se agregan la exposición y el ECL
    de NO-RELACIONADOS y RELACIONADOS por banda antes de comparar. `colectiva`
    está indexado por segmento -> banda, y `tramos` trae una fila por cada
    combinación segmento/banda (pueden repetirse nombres de banda entre
    segmentos), por lo que ambas dimensiones se consolidan explícitamente en
    vez de leerse como si ya vinieran planas.
    """
    expo_por_banda: dict[str, float] = {b["nombre"]: 0.0 for b in bandas}
    for s in colectiva:
        for nombre, saldo in colectiva[s].items():
            expo_por_banda[nombre] = expo_por_banda.get(nombre, 0.0) + saldo

    ecl_por_banda: dict[str, float | None] = {}
    for t in tramos:
        nombre = t["tramo"]
        if t["ecl"] is None:
            ecl_por_banda.setdefault(nombre, None)
            continue
        previo = ecl_por_banda.get(nombre)
        ecl_por_banda[nombre] = t["ecl"] if previo is None else previo + t["ecl"]

    filas, total = [], 0.0
    for b in bandas:
        nombre = b["nombre"]
        tasa = float(politica.get(nombre, politica.get(b["origen"], 0)) or 0)
        exposicion = expo_por_banda.get(nombre, 0.0)
        provision = redondear(exposicion * tasa)
        total += provision
        ecl = ecl_por_banda.get(nombre)
        filas.append({"banda": nombre, "banda_origen": b["origen"], "exposicion": redondear(exposicion),
                      "tasa_politica": tasa, "provision_politica": provision, "ecl": ecl,
                      "diferencia": None if ecl is None else redondear(ecl - provision)})
    bruta = sum(abs(f["diferencia"]) for f in filas if f["diferencia"] is not None)
    return {"filas": filas, "provision_politica_total": redondear(total),
            "diferencia_bruta": redondear(bruta)}


def _hallazgos(resumen, politica, parametros, factor_prospectivo_aplicado, justificacion):
    h = []
    sin_ajuste_efectivo = not any(
        abs(float(v) - 1.0) > 1e-9 for v in factor_prospectivo_aplicado.values()
    )
    if sin_ajuste_efectivo or not justificacion.strip():
        h.append({"titulo": "Ausencia del componente prospectivo", "riesgo": "Alto",
                  "condicion": "La estimación no incorpora información sobre condiciones futuras: "
                               "el factor aplicado es 1,000.",
                  "criterio": "NIIF 9 párr. 5.5.17(c).",
                  "causa": "No se ha desarrollado un procedimiento para incorporar información "
                           "prospectiva, o el ajuste propuesto carece de justificación escrita.",
                  "efecto": "Incumplimiento de un requerimiento explícito de la norma.",
                  "recomendacion": "Documentar las variables prospectivas con fuente identificada y su traslación al factor."})
    sub = [f for f in politica["filas"] if f["tasa_politica"] == 0 and f["ecl"] and f["exposicion"] > 0
           and f["ecl"] / f["exposicion"] > 0.05]
    if sub:
        h.append({"titulo": "Política de deterioro no sustentada en el comportamiento observado",
                  "riesgo": "Alto",
                  "condicion": "Bandas sin provisionar pese a registrar pérdida observada: " +
                               ", ".join(f["banda"] for f in sub) + ".",
                  "criterio": "NIIF 9 párr. 5.5.15 y B5.5.35.",
                  "causa": "La política se definió sobre criterios de gestión y no sobre el comportamiento de pago.",
                  "efecto": f"Diferencia bruta de {politica['diferencia_bruta']:,.2f}.",
                  "recomendacion": "Reemplazar los porcentajes fijos por la matriz derivada del comportamiento observado."})
    if resumen["colectivo"].get("exposicion_sin_medir", 0) > 0.005:
        h.append({"titulo": "Cartera sin tasa histórica", "riesgo": "Alto",
                  "condicion": f"Quedan {resumen['colectivo']['exposicion_sin_medir']:,.2f} sin medir por falta de historia en su banda.",
                  "criterio": "NIIF 9 B5.5.35: la matriz se sustenta en la experiencia propia de la entidad.",
                  "causa": "La cohorte no tiene documentos en esas bandas.",
                  "efecto": "La pérdida esperada no cubre la totalidad de la cartera.",
                  "recomendacion": "Resolver por analogía con un segmento comparable, dejando constancia, o declarar la limitación."})
    return h


def _pendientes(resumen, parametros, coh, leidos):
    p = []
    if not parametros.get("materialidad"):
        p.append({"variable": "Materialidad de desempeño", "responsable": "Socio", "criticidad": "Alta",
                  "efecto": "Impide concluir sobre la significatividad del ajuste"})
    if not parametros.get("umbral_individual"):
        p.append({"variable": "Umbral de evaluación individual", "responsable": "Socio", "criticidad": "Alta",
                  "efecto": "Impide segregar de la matriz los saldos relevantes"})
    if not str(parametros.get("justificacion_prospectivo") or "").strip():
        p.append({"variable": "Información prospectiva documentada", "responsable": "Cliente",
                  "criticidad": "Alta", "efecto": "El factor permanece en 1,000"})
    if not parametros.get("mayor_provision"):
        p.append({"variable": "Mayores de la provisión de los tres ejercicios", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": "Sin ellos no se puede demostrar que los castigos fueron inmateriales, y el método de permanencia queda sin sustento"})
    if coh["trazabilidad"] < 0.8:
        p.append({"variable": "Trazabilidad por número de documento", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": f"Solo el {coh['trazabilidad']:.1%} de la cohorte se localizó en el corte actual: el método de cohortes podría no ser aplicable"})
    if coh.get("anomalias"):
        bandas_afectadas = ", ".join(f"{a['segmento']}/{a['banda']}" for a in coh["anomalias"])
        p.append({"variable": "Tasas de cohorte fuera de rango", "responsable": "Gerente / Socio",
                  "criticidad": "Alta",
                  "efecto": f"En {bandas_afectadas} el saldo remanente en el corte actual superó al "
                            "saldo inicial de la cohorte, o resultó negativo; la tasa se acotó entre "
                            "0 % y 100 % para poder medir, pero el origen del incremento (nueva "
                            "facturación reclasificada al mismo documento, reversión, error de "
                            "carga) debe explicarse antes de aceptar la matriz."})
    for l in leidos:
        if l["formato_fecha"] in ("ambiguo", "inconsistente"):
            p.append({"variable": f"Formato de fecha de {l['hoja']}", "responsable": "Equipo",
                      "criticidad": "Alta", "efecto": "Toda la mora depende del orden día/mes"})
    return p
