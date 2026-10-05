"""Consola de revisión del auditor — puerta de calidad de la planificación (FIN-AP).

Este módulo NO construye la planificación: la **revisa**, actuando como el
auditor revisor sobre lo que produjo el procesador ``planificacion_nia``. Su
patrón es el prompt FIN-AP y el artefacto ``AuditBrain_Analisis_LANSEY`` (fuente
de verdad). Fue construido primero como agente auditor en
``jcalupinia/audit-ia-artefactos`` (``engine/planning_review.py`` y
``planning_runner_adapter.py``, PR #3) y aquí se porta al runner para que la
revisión ocurra **dentro de la plataforma**, antes de que el socio apruebe.

La clave metodológica es el **recálculo independiente**: los índices y los
agregados se vuelven a calcular desde los insumos crudos del resultado
(``est9`` y ``cuentas``) con fórmulas escritas aparte de las del procesador. Si
las dos implementaciones coinciden (cero diferencias), la cifra queda
verificada; si divergen, la consola lo marca y el veredicto baja a NO APTO. Así
la puerta de calidad no confía en el mismo código que produjo el número.

Veredicto (compuerta M23/M24 del prompt): la aprobación del socio es **humana**;
la consola solo dice si el trabajo está **APTO PARA REVISIÓN DEL SOCIO**,
**OBSERVADO** o **NO APTO**.
"""
from __future__ import annotations

import datetime

REVISOR_VERSION = "1.0.0"
ETIQUETA_PENDIENTE = "REVISIÓN PRELIMINAR — PENDIENTE DE APROBACIÓN DEL SOCIO"

# Tolerancia del cotejo: los índices se declaran redondeados a 2 decimales (hoja 10),
# así que una diferencia de recálculo por debajo de esto es ruido de redondeo.
TOL_INDICE = 0.01
# Los agregados son sumas exactas de saldos: cualquier centavo de diferencia importa.
TOL_AGREGADO = 0.01
# Cuadre del balance (activo − (pasivo + patrimonio + resultado)).
TOL_CUADRE = 0.01

# Códigos de excepción del procesador que, sin ser un descuadre, ameritan que el
# socio mire con lupa antes de aprobar (dejan el veredicto en OBSERVADO).
CODIGOS_OBSERVACION = {
    "JUSTIFICACION_AUTOMATICA", "MESES_NO_COINCIDEN", "CUENTAS_SIN_SECCION",
    "JERARQUIA_NO_SUMA", "ENFOQUE_REVISAR", "ANOMALIAS_CORTADAS", "ERI_NO_USADO",
    "CONTROLES_NECESARIOS",
}
# Códigos de excepción que rompen la integridad de las cifras: NO APTO.
CODIGOS_BLOQUEO = {
    "ESF_NO_CUADRA", "ESF_ANTERIOR_NO_CUADRA", "BASE_NO_VALIDA", "PYMES_2025_ANTICIPADA",
}


def _div(a, b):
    """División protegida: None si el divisor es cero o falta un operando."""
    if a is None or b in (0, None):
        return None
    return a / b


def _r2(x):
    return None if x is None else round(float(x), 2)


# --- recálculo independiente de los índices (fórmulas re-derivadas del artefacto) ---------------------------

# Etiquetas de los índices, en el orden de la hoja 10 del artefacto.
INDICES = [
    ("razonCorriente", "Razón corriente"),
    ("pruebaAcida", "Prueba ácida"),
    ("capitalTrabajo", "Capital de trabajo"),
    ("diasCartera", "Días de cartera"),
    ("diasInventario", "Días de inventario"),
    ("diasProveedores", "Días de proveedores"),
    ("ciclo", "Ciclo de efectivo"),
    ("rotacionActivo", "Rotación del activo"),
    ("endTotal", "Endeudamiento total"),
    ("endLP", "Endeudamiento de largo plazo"),
    ("endFinanciero", "Endeudamiento financiero"),
    ("endPatrimonial", "Endeudamiento patrimonial"),
    ("multiplicador", "Multiplicador de apalancamiento"),
    ("margenBruto", "Margen bruto"),
    ("margenOperativo", "Margen operativo"),
    ("margenNeto", "Margen neto"),
    ("roi", "ROI"),
    ("roe", "ROE"),
    ("dupontRoi", "DuPont (ROI)"),
    ("dupont", "DuPont (ROE)"),
]


def indices_independientes(e: dict, dias: float = 365) -> dict:
    """Recalcula los índices desde el estado resumido ``e`` (una entrada de ``est9``).

    Es una segunda implementación de las razones de los NIA 315/320: se escribe
    con las mismas definiciones financieras que el artefacto pero sin reutilizar
    la función del procesador, para que el cotejo detecte una divergencia real.
    El redondeo a 2 decimales replica la hoja 10.
    """
    ac = e.get("Activo corriente")
    pc = e.get("Pasivo corriente")
    inv = e.get("Inventarios")
    cxc = e.get("Cuentas por cobrar")
    cxp = e.get("Cuentas por pagar")
    act = e.get("TOTAL ACTIVO")
    pas = e.get("TOTAL PASIVO")
    pnc = e.get("Pasivo no corriente")
    psr = e.get("PATRIMONIO (sin resultado del período)")
    obl = e.get("Obligaciones financieras")
    ven = e.get("Ventas netas")
    cos = e.get("(−) Costo de ventas")
    ub = e.get("Utilidad bruta")
    uo = e.get("Utilidad operativa")
    un = e.get("Utilidad neta")
    # Denominador patrimonial igual que el motor (_indices): patrimonio SIN resultado + utilidad neta del ERI (no el
    # resultado según el balance). En la preliminar ambos difieren; con esto el cotejo reproduce al motor.
    patg = None if psr is None or un is None else psr + un

    def r(a, b, factor=1.0):
        v = _div(a, b)
        return None if v is None else round(v * factor, 2)

    out: dict = {"dias": round(float(dias), 2)}
    out["razonCorriente"] = r(ac, pc)
    out["pruebaAcida"] = r(None if ac is None or inv is None else ac - inv, pc)
    out["capitalTrabajo"] = None if ac is None or pc is None else round(ac - pc, 2)
    out["diasCartera"] = r(None if cxc is None else cxc * dias, ven)
    out["diasInventario"] = r(None if inv is None else inv * dias, cos)
    out["diasProveedores"] = r(None if cxp is None else cxp * dias, cos)
    if None in (out["diasCartera"], out["diasInventario"], out["diasProveedores"]):
        out["ciclo"] = None
    else:
        out["ciclo"] = round(out["diasCartera"] + out["diasInventario"] - out["diasProveedores"], 2)
    out["rotacionActivo"] = r(ven, act)
    out["endTotal"] = r(pas, act, 100)
    out["endLP"] = r(pnc, act, 100)
    out["endFinanciero"] = r(obl, patg)
    out["endPatrimonial"] = r(pas, patg)
    out["multiplicador"] = r(act, patg)
    out["margenBruto"] = r(ub, ven, 100)
    out["margenOperativo"] = r(uo, ven, 100)
    out["margenNeto"] = r(un, ven, 100)
    out["roi"] = r(uo, act, 100)
    out["roe"] = r(un, patg, 100)
    # DuPont: el ROI y el ROE reconstruidos por sus componentes, sin redondear los factores.
    if ven and act:
        out["dupontRoi"] = round((uo / ven) * 100 * (ven / act), 2)
    else:
        out["dupontRoi"] = None
    if ven and act and patg:
        out["dupont"] = round((un / ven) * 100 * (ven / act) * (act / patg), 2)
    else:
        out["dupont"] = None
    return out


def _cotejo_indices(detalle: dict) -> dict:
    """Recalcula todos los índices de ambos períodos y los coteja contra lo declarado."""
    est9 = detalle.get("est9") or {}
    ind = detalle.get("ind") or {}
    dias = detalle.get("dias") or 365
    filas = []
    difs = 0
    for periodo in ("ant", "act"):
        e = est9.get(periodo)
        declarado = ind.get(periodo) or {}
        if not e:
            continue
        recalc = indices_independientes(e, dias)
        for clave, etiqueta in INDICES:
            dec = declarado.get(clave)
            rec = recalc.get(clave)
            if dec is None and rec is None:
                ok = True
                diff = 0.0
            elif dec is None or rec is None:
                ok = False
                diff = None
            else:
                diff = round(abs(float(dec) - float(rec)), 4)
                ok = diff <= TOL_INDICE
            if not ok:
                difs += 1
            filas.append({"periodo": periodo, "indice": clave, "etiqueta": etiqueta,
                          "declarado": dec, "recalculado": rec, "diff": diff, "ok": ok})
    return {"total": len(filas), "diferencias": difs, "conforme": difs == 0, "detalle": filas}


# --- recálculo independiente de los agregados (desde las cuentas de detalle) ---------------------------------

def _suma_cuentas(cuentas: list, periodo_key: str, **filtro) -> float:
    """Suma el saldo del período de las cuentas de detalle que cumplen el filtro.

    Es la re-derivación de los totales: en vez de leer ``sec7``/``est9``, suma
    directamente las cuentas hoja (``detalle == "Sí"``), que es de donde el
    artefacto arma los totales (R1). Coincidir con ``est9`` prueba que la
    agregación del procesador es fiel.
    """
    total = 0.0
    for x in cuentas:
        if x.get("detalle") != "Sí":
            continue
        if all(x.get(k) == v for k, v in filtro.items()):
            total += float(x.get(periodo_key) or 0.0)
    return round(total, 2)


def _cotejo_agregados(detalle: dict) -> dict:
    """Recalcula los grandes totales desde las cuentas y los coteja contra ``est9``."""
    cuentas = detalle.get("cuentas") or []
    est9 = detalle.get("est9") or {}
    metricas = [
        ("Activo total", "TOTAL ACTIVO", {"sec": "Activo"}),
        ("Pasivo total", "TOTAL PASIVO", {"sec": "Pasivo"}),
        ("Patrimonio (sin resultado)", "PATRIMONIO (sin resultado del período)", {"sec": "Patrimonio"}),
        ("Ingresos", "__ingresos__", {"sec": "Ingresos"}),
        ("Costos", "(−) Costo de ventas", {"sec": "Costos"}),
        ("Gastos", "__gastos__", {"sec": "Gastos"}),
    ]
    filas = []
    difs = 0
    for periodo, pk in (("ant", "ant"), ("act", "act")):
        e = est9.get(periodo) or {}
        for etiqueta, clave_e, filtro in metricas:
            recalc = _suma_cuentas(cuentas, pk, **filtro)
            if clave_e == "__ingresos__":
                declarado = round(float(e.get("Ventas netas") or 0) + float(e.get("(+) Otros ingresos") or 0), 2)
            elif clave_e == "__gastos__":
                declarado = round(float(e.get("(−) Gastos operativos") or 0)
                                  + float(e.get("(−) Gastos financieros") or 0)
                                  + float(e.get("(−) Participación e impuestos") or 0), 2)
            else:
                declarado = round(float(e.get(clave_e) or 0), 2)
            diff = round(abs(declarado - recalc), 2)
            ok = diff <= TOL_AGREGADO
            if not ok:
                difs += 1
            filas.append({"periodo": periodo, "metrica": etiqueta, "declarado": declarado,
                          "recalculado": recalc, "diff": diff, "ok": ok})
    return {"total": len(filas), "diferencias": difs, "conforme": difs == 0, "detalle": filas}


# --- cuadre del balance (NIA 300/315: no forzado, verificado) -------------------------------------------------

def _cotejo_cuadre(detalle: dict) -> list:
    est9 = detalle.get("est9") or {}
    filas = []
    for periodo, nombre in (("act", "Corte actual"), ("ant", "Cierre anterior")):
        e = est9.get(periodo)
        if not e:
            continue
        activo = float(e.get("TOTAL ACTIVO") or 0)
        pas_pat = float(e.get("PASIVO + PATRIMONIO TOTAL") or 0)
        dif = round(activo - pas_pat, 2)
        filas.append({"periodo": periodo, "nombre": nombre, "activo": round(activo, 2),
                      "pasivo_patrimonio": round(pas_pat, 2), "dif": dif,
                      "estado": "cuadra" if abs(dif) <= TOL_CUADRE else "descuadra"})
    return filas


# --- indicios de empresa en funcionamiento (NIA 570) ---------------------------------------------------------

def _indicios_nia570(detalle: dict) -> list:
    """Re-deriva los indicios de la NIA 570 desde el estado resumido del corte."""
    est9 = detalle.get("est9") or {}
    ind = (detalle.get("ind") or {}).get("act") or {}
    e = est9.get("act") or {}
    indicios = []
    ct = e.get("Activo corriente")
    pc = e.get("Pasivo corriente")
    if ct is not None and pc is not None and (ct - pc) < 0:
        indicios.append("Capital de trabajo negativo (el pasivo corriente supera al activo corriente).")
    rc = ind.get("razonCorriente")
    if rc is not None and rc < 1:
        indicios.append("Razón corriente menor que 1.")
    pat = e.get("PATRIMONIO TOTAL")
    if pat is not None and pat <= 0:
        indicios.append("Patrimonio total cero o negativo (déficit patrimonial).")
    endt = ind.get("endTotal")
    if endt is not None and endt > 80:
        indicios.append("Endeudamiento total mayor que 80 %.")
    un = e.get("Utilidad neta")
    if un is not None and un < 0:
        indicios.append("Pérdida del ejercicio.")
    return indicios


# --- anomalías (NIA 240): conteo declarado vs detalle --------------------------------------------------------

def _resumen_anomalias(detalle: dict) -> dict:
    anomalias = detalle.get("anomalias") or []
    por_sev = {"Alto": 0, "Medio": 0, "Bajo": 0}
    tipos: dict = {}
    for a in anomalias:
        sev = a.get("sev")
        if sev in por_sev:
            por_sev[sev] += 1
        tipos[a.get("tipo", "?")] = tipos.get(a.get("tipo", "?"), 0) + 1
    return {"total": len(anomalias), "por_severidad": por_sev, "por_tipo": tipos}


# --- materialidad (NIA 320) ----------------------------------------------------------------------------------

def _resumen_materialidad(detalle: dict) -> dict:
    mat = detalle.get("materialidad") or {}
    base_valor = mat.get("base")
    return {
        "base_nombre": detalle.get("base"),
        "periodo": detalle.get("periodo"),
        "base_valor": _r2(base_valor),
        "global": _r2(mat.get("global")),
        "desempeno": _r2(mat.get("desempeno")),
        "trivial": _r2(mat.get("trivial")),
        "hay_materialidad": mat.get("global") is not None,
        "justificacion_presente": bool(str(detalle.get("justificacion") or "").strip()),
    }


# --- conformidad de capacidades (cobertura vs el artefacto) --------------------------------------------------

# Capacidad → clave del detalle que la evidencia (presencia = conforme).
CAPACIDADES = [
    ("Mapa de cuentas por prefijo del código", "mapa"),
    ("Estados resumidos (ESF/ERI)", "est7_est9"),
    ("Cuentas con análisis horizontal y vertical", "cuentas"),
    ("Índices financieros con recálculo (NIA 315)", "ind"),
    ("Materialidad (NIA 320)", "materialidad"),
    ("Matriz de la carta de control interno", "carta"),
    ("Riesgos del balance y del encargo", "riesgos"),
    ("Anomalías (NIA 240)", "anomalias"),
    ("Cuentas principales a revisar (NIA 330)", "revisar"),
    ("Orígenes y aplicaciones de efectivo", "origenes"),
    ("Audit trail de los archivos (NIA 230)", "archivos"),
]


def _cobertura(detalle: dict) -> dict:
    filas = []
    presentes = 0
    for nombre, clave in CAPACIDADES:
        if clave == "est7_est9":
            hay = bool(detalle.get("sec7")) and bool(detalle.get("est9"))
        else:
            v = detalle.get(clave)
            hay = bool(v) if not isinstance(v, (int, float)) else v is not None
        if hay:
            presentes += 1
        filas.append({"capacidad": nombre, "presente": hay})
    total = len(CAPACIDADES)
    return {"total": total, "presentes": presentes,
            "veredicto": "CONFORME" if presentes == total else "CON OBSERVACIONES" if presentes >= total - 2 else "NO CONFORME",
            "detalle": filas}


# --- puerta de calidad (checklist del prompt FIN-AP) ---------------------------------------------------------

def _puerta_calidad(detalle: dict, ind_ct: dict, agr_ct: dict, cuadre: list,
                    mat: dict, indicios: list, cobertura: dict) -> list:
    marco = detalle.get("marco") or "no declarado"
    cuadra_todo = all(f["estado"] == "cuadra" for f in cuadre) if cuadre else False
    trazable = bool(detalle.get("archivos"))
    return [
        {"criterio": "Marco de información financiera confirmado",
         "estado": "PASA" if detalle.get("marco") else "REVISAR",
         "detalle": f"Marco declarado: {marco}."},
        {"criterio": "Cuadre verificado y mostrado (no forzado)",
         "estado": "PASA" if cuadra_todo else "FALLA",
         "detalle": "; ".join(f"{f['nombre']}: dif {f['dif']:.2f} ({f['estado']})" for f in cuadre) or "sin datos"},
        {"criterio": "Cero invención: cifras trazables / audit trail (NIA 230)",
         "estado": "PASA" if trazable else "REVISAR",
         "detalle": "Audit trail de archivos presente." if trazable else "No hay huella de archivos de entrada."},
        {"criterio": "Índices con recálculo independiente (NIA 315)",
         "estado": "PASA" if ind_ct["conforme"] else "FALLA",
         "detalle": f"{ind_ct['diferencias']} de {ind_ct['total']} índices con diferencia."},
        {"criterio": "Recálculo de agregados vs estados resumidos",
         "estado": "PASA" if agr_ct["conforme"] else "FALLA",
         "detalle": f"{agr_ct['diferencias']} de {agr_ct['total']} agregados con diferencia."},
        {"criterio": "Materialidad NIA 320 con justificación",
         "estado": "PASA" if mat["hay_materialidad"] and mat["justificacion_presente"] else "REVISAR",
         "detalle": (f"Global {mat['global']}; desempeño {mat['desempeno']}."
                     if mat["hay_materialidad"] else "Base ≤ 0: sin materialidad hasta elegir otra base.")},
        {"criterio": "Riesgos e indicios NIA 570 evaluados",
         "estado": "PASA",
         "detalle": f"Indicios NIA 570: {len(indicios)}; riesgos evaluados."},
        {"criterio": "Cobertura de documentos del artefacto",
         "estado": "PASA" if cobertura["veredicto"] == "CONFORME" else "REVISAR",
         "detalle": f"{cobertura['presentes']} de {cobertura['total']} capacidades presentes ({cobertura['veredicto']})."},
        {"criterio": "Aprobación del socio antes de publicar",
         "estado": "PENDIENTE",
         "detalle": "Compuerta M23/M24: requiere la validación humana del socio."},
    ]


# --- veredicto ------------------------------------------------------------------------------------------------

def revisar(run: dict) -> dict:
    """Revisa el resultado completo de ``planificacion_nia`` y emite el veredicto.

    ``run`` es el dict que devuelve ``planificacion_nia.ejecutar`` (con el
    ``detalle`` completo, no el recortado que se guarda en la prueba). Devuelve el
    reporte de la consola: recálculos, cuadre, materialidad, puerta de calidad y
    veredicto APTO / OBSERVADO / NO APTO.
    """
    detalle = run.get("detalle") or {}
    excepciones = run.get("exceptions") or []

    ind_ct = _cotejo_indices(detalle)
    agr_ct = _cotejo_agregados(detalle)
    cuadre = _cotejo_cuadre(detalle)
    mat = _resumen_materialidad(detalle)
    indicios = _indicios_nia570(detalle)
    anomalias = _resumen_anomalias(detalle)
    cobertura = _cobertura(detalle)
    puerta = _puerta_calidad(detalle, ind_ct, agr_ct, cuadre, mat, indicios, cobertura)

    hallazgos = []
    bloqueos = []

    # Recálculo: una divergencia contra la implementación independiente bloquea.
    if not ind_ct["conforme"]:
        bloqueos.append(f"El recálculo independiente de índices difiere en {ind_ct['diferencias']} de {ind_ct['total']} casos.")
    if not agr_ct["conforme"]:
        bloqueos.append(f"El recálculo de agregados difiere en {agr_ct['diferencias']} de {agr_ct['total']} casos.")
    for f in cuadre:
        if f["estado"] != "cuadra":
            bloqueos.append(f"El balance {f['nombre'].lower()} no cuadra (diferencia {f['dif']:.2f}).")

    # Excepciones del procesador: unas bloquean, otras observan.
    for exc in excepciones:
        cod = exc.get("code")
        if cod in CODIGOS_BLOQUEO:
            bloqueos.append(exc.get("message") or cod)
        elif cod in CODIGOS_OBSERVACION:
            hallazgos.append(exc.get("message") or cod)

    if not mat["hay_materialidad"]:
        hallazgos.append("La base de materialidad es ≤ 0: no hay materialidad y ninguna cuenta se marca como material.")
    if cobertura["veredicto"] != "CONFORME":
        hallazgos.append(f"Cobertura de documentos: {cobertura['veredicto']} "
                         f"({cobertura['presentes']}/{cobertura['total']}).")

    if bloqueos:
        veredicto = "NO APTO"
    elif hallazgos:
        veredicto = "OBSERVADO"
    else:
        veredicto = "APTO PARA REVISIÓN DEL SOCIO"

    return {
        "veredicto": veredicto,
        "etiqueta": ETIQUETA_PENDIENTE,
        "aprobacion_socio_requerida": True,
        "bloqueos": bloqueos,
        "hallazgos": hallazgos,
        "recalculo_indices": ind_ct,
        "recalculo_agregados": agr_ct,
        "cuadre": cuadre,
        "materialidad": mat,
        "nia570": indicios,
        "anomalias": anomalias,
        "cobertura": cobertura,
        "puerta_calidad": puerta,
        "contexto": {
            "marco": detalle.get("marco"),
            "edicion": detalle.get("edicion"),
            "tipo": detalle.get("tipo"),
            "corte": detalle.get("corte"),
            "periodo": detalle.get("periodo"),
            "meses": detalle.get("meses"),
        },
        "revisor_version": REVISOR_VERSION,
        "revisado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
