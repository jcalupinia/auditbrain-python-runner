"""Planificación de la auditoría · documentación del encargo (complemento de ``planificacion_nia``; no es una
herramienta del catálogo por sí sola). Faltantes A1–A17 y A19 de la revisión de control de calidad frente a las NIA.

**Todo es automático** (decisión del dueño, 2026-09-26: «todos los documentos tienen que ser automáticos»):

- Lo que sale de los documentos de entrada: componentes del control interno y controles generales de TI (carta de
  control interno, RQ-004), indicios de fraude (balances, carta e informe anterior), materialidad específica (cuentas de
  partes relacionadas y remuneraciones), diferencias de auditoría (notas que no concilian y salvedades con importe),
  estados del año anterior (encargo inicial e informe anterior) y marco contable aceptable (ficha del encargo).
- Lo que no está en ningún documento se registra con un clic en la plataforma y llega en ``parametros["_encargo"]``:
  independencia de cada integrante con su rol (socio, gerente, revisor de calidad…), aprobación de la aceptación por el
  socio, firma de la carta de encargo generada por la plataforma, asistencia a la discusión del equipo y envío de la carta
  de planificación. Esos registros van a la hoja de documentación ``00_Registros`` y las cédulas los leen por fórmula.
- Las indagaciones de fraude a la dirección quedan fuera de la herramienta (decisión de la firma: solo indicios).
- La firma no audita grupos: no hay auditoría de grupo (NIA 600).

Regla de cero invención: lo que falta queda «[PENDIENTE]» y el control de calidad (hoja 16) lo cuenta. Los porcentajes
(confianza, error esperado, materialidad específica, rotación) son política de la firma y los párrafos citados llevan
«VERIFICAR» hasta cotejarlos con el texto oficial vigente.
"""
from __future__ import annotations

import math

from backend.app.aud.niif.procesadores.base import FILA0, a_fecha, a_num, fx, n2, norm

PENDIENTE = "[PENDIENTE]"
SI, NO = "Sí", "No"
NO_APLICA = "No aplica"

REG = "00_Registros"
H24, H25, H26, H27, H28, H29, H30, H32 = (
    "24_Aceptacion", "25_Equipo", "26_Discusion_Fraude", "27_Control_Interno", "28_Afirmaciones", "29_Muestreo",
    "30_Diferencias", "32_Comunicacion")
CEDULAS = [
    (REG, "Registros del encargo en la plataforma (independencia, aceptación, carta de encargo, discusión y comunicación)"),
    (H24, "Aceptación y continuidad, condiciones previas y carta de encargo, materialidad específica y comunicación (NIGC 1; "
          "NIA 210, 220, 260 y 320)"),
    (H25, "Equipo del encargo, independencia, amenazas y salvaguardas, rotación y revisor de calidad (IESBA; NIA 220; NIGC 2)"),
    (H26, "Discusión del equipo e indicios de fraude (NIA 315 y 240)"),
    (H27, "Componentes del control interno y controles generales de TI según la carta de control interno (NIA 315 Revisada 2019)"),
    (H28, "Valoración del riesgo por afirmación y a nivel de estados financieros (NIA 315 y 330)"),
    (H29, "Extensión y tamaño de la muestra por cuenta (NIA 330 y 530)"),
    (H30, "Sumario de diferencias de auditoría (NIA 450)"),
    (H32, "Comunicación de la planificación a los responsables del gobierno y asuntos clave candidatos (NIA 260 y 701)"),
]
R_ = f"'{REG}'!"

# --- registros de la plataforma (00_Registros) -----------------------------------------------------------------------
TIPO_INDEP = "Independencia confirmada"
TIPO_ASIST = "Asistencia a la discusión del equipo"
TIPO_ACEPT = "Aceptación o continuidad aprobada"
TIPO_CARTA = "Carta de encargo firmada"
TIPO_COMUN = "Comunicación al gobierno enviada"
TIPO_INDAG = "Indagación u observación"
TIPO_CONSULTA = "Consulta técnica"
TIPO_DIFERENCIA = "Diferencia de opinión"
ABIERTA, RESUELTA = "Abierta", "Resuelta"
TIPO_ENFOQUE = "Enfoque del ciclo confirmado por el socio"
ROLES = ("Socio", "Gerente", "Senior", "Asistente", "Revisor de calidad", "Experto", "Otro")
ESTADOS_ANTERIORES = ("Auditados por nosotros", "Auditados por otro auditor", "No auditados")
COLS_REGISTROS = [["Registro", "t"], ["Integrante o responsable", "t"], ["Rol", "t"], ["Fecha", "d"],
                  ["Amenazas o limitaciones", "t"], ["Salvaguardas o medio", "t"], ["Años con el cliente", "n"], ["Detalle", "t"]]
GUIA_REGISTROS = ("Los registra la plataforma con un clic de cada usuario en el encargo: su independencia y su rol, la aprobación "
                  "de la aceptación por el socio, la firma de la carta de encargo y el envío de la carta de planificación "
                  "(generadas por la plataforma) y la asistencia a la discusión del equipo. Lo que no se registró queda vacío.")


def _rol(v) -> str:
    k = norm(v)
    for claves, rol in ((("socio", "partner"), "Socio"), (("revisor", "eqr", "calidad"), "Revisor de calidad"),
                        (("gerente", "encargad", "supervisor", "manager"), "Gerente"), (("senior", "semisenior"), "Senior"),
                        (("asistente", "junior", "auxiliar"), "Asistente"), (("experto", "especialista", "actuario"), "Experto")):
        if k.startswith(claves):
            return rol
    return "Otro"


def _fecha(v) -> str:
    f = a_fecha(v) if str(v or "").strip() else None
    return f.isoformat() if f else ""


# Término único de la NIA 570 (2026-09-27): los registros guardados con el nombre anterior del tema se leen con el nuevo.
_TEMA_ANTERIOR = {"Empresa en marcha": "Empresa en funcionamiento"}


def _tema(t: str) -> str:
    return _TEMA_ANTERIOR.get(t, t)


def registros(p: dict) -> dict:
    """Registros que la plataforma inyecta en ``parametros["_encargo"]`` (ciclo/servicio.py)."""
    e = p.get("_encargo") or {}
    r = e.get("registros") or {}
    txt = lambda x, k: str((x or {}).get(k) or "").strip()  # noqa: E731
    equipo = []
    for x in r.get("equipo") or []:
        if not txt(x, "integrante"):
            continue
        an = a_num(x.get("anios")) if str(x.get("anios") or "").strip() else None
        equipo.append({"integrante": txt(x, "integrante"), "rol": _rol(x.get("rol")), "fecha": _fecha(x.get("fecha")),
                       "amenazas": txt(x, "amenazas"), "salvaguardas": txt(x, "salvaguardas"), "anios": None if an is None else float(an)})
    asist = [{"integrante": txt(x, "integrante"), "rol": _rol(x.get("rol")), "fecha": _fecha(x.get("fecha"))}
             for x in r.get("asistencia") or [] if txt(x, "integrante")]

    def uno(k):
        x = r.get(k) or {}
        return {"actor": txt(x, "actor"), "fecha": _fecha(x.get("fecha")), "detalle": txt(x, "detalle")}
    # M7 (NIA 315): indagaciones y observaciones; M3 (NIA 220): consultas y diferencias de opinión con su estado.
    indag = [{"actor": txt(x, "actor"), "fecha": _fecha(x.get("fecha")), "tema": _tema(txt(x, "tema")) or "Otro",
              "procedimiento": txt(x, "procedimiento") or "Indagación", "persona": txt(x, "persona"), "resumen": txt(x, "resumen")}
             for x in r.get("indagaciones") or [] if txt(x, "resumen")]
    consultas = [{"actor": txt(x, "actor"), "fecha": _fecha(x.get("fecha")), "tipo": TIPO_DIFERENCIA if txt(x, "tipo") == "diferencia"
                  else TIPO_CONSULTA, "tema": txt(x, "tema"), "estado": RESUELTA if txt(x, "estado") == RESUELTA else ABIERTA,
                  "detalle": txt(x, "detalle")} for x in r.get("consultas") or [] if txt(x, "tema")]
    return {"equipo": equipo, "asistencia": asist, "aceptacion": uno("aceptacion"), "carta": uno("carta"),
            "comunicacion": uno("comunicacion"), "indagaciones": indag, "consultas": consultas,
            "enfoque": [{"ciclo": txt(x, "ciclo"), "decision": txt(x, "decision"), "actor": txt(x, "actor"),
                         "fecha": _fecha(x.get("fecha")), "motivo": txt(x, "motivo")}
                        for x in r.get("enfoque") or [] if txt(x, "ciclo") and txt(x, "decision")],
            "firma": str(e.get("firma") or "").strip(), "ficha": dict(e.get("ficha") or {})}


def filas_registros(reg: dict) -> tuple[list, dict]:
    filas, pos = [], {"equipo": [], "asistencia": []}
    for x in reg["equipo"]:
        pos["equipo"].append(FILA0 + len(filas))
        filas.append([TIPO_INDEP, x["integrante"], x["rol"], x["fecha"] or None, x["amenazas"], x["salvaguardas"], n2(x["anios"]), ""])
    for x in reg["asistencia"]:
        pos["asistencia"].append(FILA0 + len(filas))
        filas.append([TIPO_ASIST, x["integrante"], x["rol"], x["fecha"] or None, "", "", None, ""])
    for k, tipo, rol, det in (("aceptacion", TIPO_ACEPT, "Socio", "Integridad de la dirección, competencia y recursos (NIGC 1)"),
                              ("carta", TIPO_CARTA, "", "Carta generada por la plataforma (NIA 210); limitaciones en la columna E"),
                              ("comunicacion", TIPO_COMUN, "", "Carta de planificación generada por la plataforma (NIA 260)")):
        x = reg[k]
        pos[k] = FILA0 + len(filas)
        filas.append([tipo, x["actor"], rol if x["actor"] else "", x["fecha"] or None,
                      x["detalle"] if k == "carta" else "", x["detalle"] if k == "comunicacion" else "", None, det])
    # Indagaciones: C procedimiento, E persona entrevistada, F tema, H resumen. Consultas: E tema, F estado, H detalle.
    pos["indagaciones"], pos["consultas"] = [], []
    for x in reg.get("indagaciones") or []:
        pos["indagaciones"].append(FILA0 + len(filas))
        filas.append([TIPO_INDAG, x["actor"], x["procedimiento"], x["fecha"] or None, x["persona"], x["tema"],
                      None, x["resumen"]])
    for x in reg.get("consultas") or []:
        pos["consultas"].append(FILA0 + len(filas))
        filas.append([x["tipo"], x["actor"], "", x["fecha"] or None, x["tema"], x["estado"], None, x["detalle"]])
    # Enfoque por ciclo confirmado por el socio: E ciclo, F decisión, H motivo.
    pos["enfoque"] = {}
    for x in reg.get("enfoque") or []:
        pos["enfoque"][x["ciclo"]] = FILA0 + len(filas)
        filas.append([TIPO_ENFOQUE, x["actor"], "Socio", x["fecha"] or None, x["ciclo"], x["decision"], None, x["motivo"]])
    return filas, pos


def estados_anteriores(valor: str, encargo_inicial: str, hay_informe: bool) -> str:
    """A17: el parámetro si se indicó; si no, se deduce: encargo recurrente → auditados por la firma; encargo inicial con
    informe del año anterior → otro auditor; encargo inicial sin informe → pendiente (no se supone «No auditados»)."""
    if valor:
        return valor
    if encargo_inicial == NO:
        return ESTADOS_ANTERIORES[0]
    return ESTADOS_ANTERIORES[1] if hay_informe else ""


# --- parámetros del encargo (se agregan a la hoja 02) ---------------------------------------------------------------
PARAMETROS = {"estadosAnteriores": "", "aniosRotacionSocio": 7, "pctMatEspecifica": 50,
              "confianzaAlta": 95, "confianzaMedia": 90, "confianzaBaja": 80, "pctErrorEsperado": 10}
ETIQUETAS = {
    "estadosAnteriores": "Estados del año anterior (vacío = se deduce del encargo inicial y del informe anterior)",
    "aniosRotacionSocio": "Años máximos del socio en una entidad de interés público antes de rotar (IESBA — VERIFICAR)",
    "pctMatEspecifica": "Materialidad específica: % de la global para partes relacionadas y remuneraciones (política de la firma)",
    "confianzaAlta": "Muestreo: confianza para riesgos altos o significativos (%)",
    "confianzaMedia": "Muestreo: confianza para riesgos medios (%)",
    "confianzaBaja": "Muestreo: confianza para riesgos bajos (%)",
    "pctErrorEsperado": "Muestreo: error esperado como % del error tolerable (política de la firma)",
}
SUSTENTO = {
    "estadosAnteriores": "NIA 510 párr. 6; NIA 710 párr. 13–14 (VERIFICAR)",
    "aniosRotacionSocio": "Código IESBA sección 540 (VERIFICAR)",
    "pctMatEspecifica": "NIA 320 párr. 10 — política de la firma (VERIFICAR)",
    "confianzaAlta": "NIA 530 — política de la firma", "confianzaMedia": "NIA 530 — política de la firma",
    "confianzaBaja": "NIA 530 — política de la firma", "pctErrorEsperado": "NIA 530 — política de la firma (VERIFICAR)",
}


def _opcion(v, opciones, etiqueta) -> str:
    k = norm(v)
    if not k:
        return ""
    x = next((o for o in opciones if norm(o) == k or norm(o).startswith(k)), None)
    if x is None:
        raise ValueError(f"{etiqueta}: use " + ", ".join(opciones) + ".")
    return x


def _num(p, k, minimo, maximo):
    x = a_num(p.get(k))
    if x is None or not minimo <= float(x) <= maximo:
        raise ValueError(f"{ETIQUETAS[k]}: use un valor de {minimo:g} a {maximo:g}.")
    return float(x)


def parametros(p: dict) -> dict:
    return {"estadosAnteriores": _opcion(p.get("estadosAnteriores"), ESTADOS_ANTERIORES, ETIQUETAS["estadosAnteriores"]),
            "aniosRotacionSocio": _num(p, "aniosRotacionSocio", 1, 30), "pctMatEspecifica": _num(p, "pctMatEspecifica", 1, 100),
            "confianzaAlta": _num(p, "confianzaAlta", 50, 99.9), "confianzaMedia": _num(p, "confianzaMedia", 50, 99.9),
            "confianzaBaja": _num(p, "confianzaBaja", 50, 99.9), "pctErrorEsperado": _num(p, "pctErrorEsperado", 0, 90)}


# --- clasificación de la carta de control interno (hoja 12, columnas O y P) -----------------------------------------
COMPONENTES = ("Entorno de control", "Proceso de valoración del riesgo", "Sistema de información y comunicación",
               "Actividades de control", "Seguimiento del control interno")
_CLAVES_COMP = [
    ("Entorno de control", ("etica", "codigodeconducta", "directorio", "gobiernocorporativo", "organigrama", "manualdefunciones",
                            "competencia", "rotaciondepersonal", "capacitacion", "integridad", "tonodeladireccion")),
    ("Proceso de valoración del riesgo", ("valoraciondelriesgo", "valoraciondelosriesgos", "matrizderiesgo", "gestionderiesgo",
                                          "identificacionderiesgo", "identificaciondelosriesgos", "planestrategico")),
    ("Seguimiento del control interno", ("seguimiento", "monitoreo", "auditoriainterna", "supervisionperiodica", "evaluacionperiodica")),
    ("Sistema de información y comunicación", ("sistemadeinformacion", "reportesfinancieros", "comunicacioninterna", "registrocontable",
                                               "plandecuentas", "cierrecontable", "informacionfinanciera")),
]
TI = ("Accesos", "Cambios en programas", "Operaciones de TI")
_CLAVES_TI = [("Accesos", ("usuario", "acceso", "contrasena", "privilegio", "perfildeusuario")),
              ("Cambios en programas", ("cambiosenprograma", "cambiosalsistema", "controldecambios", "parche", "versiondelsistema",
                                        "desarrollodesistemas")),
              ("Operaciones de TI", ("respaldo", "backup", "incidente", "servidor", "continuidaddelnegocio", "recuperacion"))]


def clasifica(texto: str) -> tuple[str, str]:
    """(componente del control interno, control general de TI o «») de un hallazgo de la carta, por palabras clave.
    Un hallazgo de TI es una actividad de control (controles generales de TI, NIA 315 Revisada 2019)."""
    k = norm(texto)
    ti = next((c for c, claves in _CLAVES_TI if any(x in k for x in claves)), "")
    comp = next((c for c, claves in _CLAVES_COMP if any(x in k for x in claves)), "Actividades de control")
    return comp, ti


# --- evaluaciones automáticas (hojas 24, 26 y 27) -------------------------------------------------------------------
COLS_EVALUACION = [["Bloque", "t"], ["Código", "t"], ["Aspecto", "t"], ["Norma", "t"], ["Resultado", "t"],
                   ["Evidencia o fuente", "t"], ["Fecha", "d"], ["Registrado por", "t"], ["Estado", "t"]]
FUERA = "Fuera de la herramienta: la firma documenta solo indicios automáticos (decisión de la firma)"
_FACTOR_FRAUDE = ("Respuesta global: escepticismo reforzado, elemento de imprevisibilidad y pruebas de asientos de diario, "
                  "estimaciones y transacciones inusuales (NIA 240 párr. 28–33 — VERIFICAR).")


def _estado(kind: str, v) -> str:
    """Espejo de la fórmula de la columna «Estado» según el tipo de evaluación."""
    s = str(v if v is not None else "")
    if kind == "no_eval":
        return "No evaluado"
    if s.startswith(PENDIENTE):
        return "Pendiente"
    if kind == "alerta_si":
        return "Alerta" if s.startswith("Sí") else "Conforme"
    if kind == "alerta_con":
        return "Alerta" if s.startswith("Con") else "Conforme"
    if kind == "alerta_no":
        return "Alerta" if s == "No" else "Conforme"
    if kind == "info":
        return "Documentado"
    return "Conforme"


def _f_estado(kind: str, e: str) -> str:
    pend = f'LEFT({e},{len(PENDIENTE)})="{PENDIENTE}"'
    core = {"alerta_si": f'IF(LEFT({e},2)="Sí","Alerta","Conforme")', "alerta_con": f'IF(LEFT({e},3)="Con","Alerta","Conforme")',
            "alerta_no": f'IF({e}="No","Alerta","Conforme")', "info": '"Documentado"', "registro": '"Conforme"'}
    return '"No evaluado"' if kind == "no_eval" else f'IF({pend},"Pendiente",{core[kind]})'


def _it(hoja_, codigo, bloque, aspecto, norma, kind, resultado, evid="", fecha=None, por="", sev="", nia="", alerta="", resp="",
        eeff=False):
    return {"hoja": hoja_, "codigo": codigo, "bloque": bloque, "aspecto": aspecto, "norma": norma, "kind": kind, "res": resultado,
            "evid": evid, "fecha": fecha, "por": por, "sev": sev, "nia": nia, "alerta": alerta, "resp": resp, "eeff": eeff}


def _partes(conds: list) -> tuple[str, str]:
    """[(fórmula de la condición, texto, valor Python)] → (fórmula «Sí: …»/«No», valor)."""
    f_ = "&".join(f'IF({c},"{t}; ","")' for c, t, _v in conds)
    v_ = "".join(f"{t}; " for _c, t, v in conds if v)
    return (f'IF({f_}="","No","Sí: "&LEFT({f_},LEN({f_})-2))', f"Sí: {v_[:-2]}" if v_ else "No")


def evaluaciones(c: dict) -> list[dict]:
    """Las evaluaciones de las hojas 24, 26 y 27, en orden. ``c`` trae las referencias y los datos de ``planificacion_nia``."""
    reg, pos, R12, R13, H8 = c["reg"], c["pos"], c["R12"], c["R13"], c["H8"]
    n12, n13, n8, n_inf = c["n12"], c["n13"], c["n8"], c["n_inf"]
    rng = lambda pref, col, n: f"{pref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"  # noqa: E731
    a12, b12, c12, j12, o12, p12 = (rng(R12, x, n12) for x in "ABCJOP")
    b13, f13, h13, i13 = (rng(R13, x, n13) for x in "BFHI")
    b8 = rng(H8, "B", n8)
    carta, riesgos = c["carta"], c["riesgos"]
    out = []

    def reg1(k, pend, ok):
        r = pos[k]
        x = reg[k]
        return (fx(f'IF({R_}D{r}="","{pend}","{ok}")', ok if x["fecha"] else pend),
                fx(f'IF({R_}D{r}="","",{R_}D{r})', x["fecha"] or ""), fx(f'IF({R_}B{r}="","",{R_}B{r})', x["actor"]))
    # 24 · aceptación, condiciones previas, materialidad específica y comunicación
    res, fch, por = reg1("aceptacion", f"{PENDIENTE} aprobación del socio en la plataforma", "Aprobada")
    out.append(_it(H24, "ACE-01", "Aceptación y continuidad", "Aceptación o continuidad aprobada por el socio (integridad de la "
                   "dirección, competencia y recursos)", "NIGC 1; NIA 220 (Revisada) párr. 22–24 (VERIFICAR)", "registro", res,
                   "Registro de la plataforma (hoja 00_Registros)", fch, por))
    n_eq, eq_est = c["n_eq"], c["eq_estados"]
    h25 = f"'{H25}'!$H${FILA0}:$H${FILA0 + max(n_eq, 1) - 1}"
    v = (f"{PENDIENTE} confirmaciones de independencia en la plataforma" if not n_eq else
         "Con alertas (hoja 25)" if any(e.startswith("Alerta") for e in eq_est) else "Confirmada por todo el equipo")
    out.append(_it(H24, "ACE-02", "Aceptación y continuidad", "Independencia de la firma y del equipo del encargo",
                   "Código IESBA; NIA 220 (Revisada) párr. 16–21 (VERIFICAR)", "alerta_con",
                   fx(f'IF({n_eq}=0,"{PENDIENTE} confirmaciones de independencia en la plataforma",IF(COUNTIF({h25},"Alerta*")>0,'
                      f'"Con alertas (hoja 25)","Confirmada por todo el equipo"))', v), "Hoja 25 · registros de independencia"))
    alto_inf = any(x["origen"] == "Informe anterior" and x["presenta"] == "Sí" and x["sev"] == "Alto" for x in riesgos)
    v = ("Sí: ver los riesgos del informe anterior (hoja 13)" if alto_inf else
         f"{PENDIENTE} sin informe del año anterior (RQ-005)" if not n_inf else "No")
    out.append(_it(H24, "ACE-03", "Aceptación y continuidad", "Asuntos del encargo anterior que afectan la continuidad (opinión "
                   "modificada, salvedades, empresa en funcionamiento)", "NIA 220 (Revisada) párr. 23; NIA 510 (VERIFICAR)", "alerta_si",
                   fx(f'IF(COUNTIFS({b13},"Informe anterior",{f13},"Sí",{h13},"Alto")>0,"Sí: ver los riesgos del informe anterior '
                      f'(hoja 13)",IF({n_inf}=0,"{PENDIENTE} sin informe del año anterior (RQ-005)","No"))', v),
                   "Informe de auditoría del año anterior (RQ-005) y hoja 13"))
    out.append(_it(H24, "CON-01", "Condiciones previas y carta de encargo", "Marco de información financiera aplicable aceptable",
                   "NIA 210 párr. 6 a)", "registro", fx(f'"Sí: "&{c["par"]("marco")}', f"Sí: {c['marco']}"),
                   "Ficha del encargo (marco contable)"))
    res, fch, por = reg1("carta", f"{PENDIENTE} registrar la firma de la carta generada por la plataforma", "Firmada")
    out.append(_it(H24, "CON-02", "Condiciones previas y carta de encargo", "Carta de encargo firmada: responsabilidades de la "
                   "dirección, acceso a la información y términos del encargo", "NIA 210 párr. 6 b), 9 y 10", "registro", res,
                   "Carta de encargo generada por la plataforma y registro de su firma", fch, por))
    r = pos["carta"]
    lim = reg["carta"]["detalle"]
    v = f"{PENDIENTE} se registra con la firma de la carta" if not reg["carta"]["fecha"] else f"Sí: {lim}" if lim else "No"
    out.append(_it(H24, "CON-03", "Condiciones previas y carta de encargo", "Limitaciones al alcance impuestas por la dirección",
                   "NIA 210 párr. 7; NIA 705", "alerta_si",
                   fx(f'IF({R_}D{r}="","{PENDIENTE} se registra con la firma de la carta",IF({R_}E{r}="","No","Sí: "&{R_}E{r}))', v),
                   "Registro de la firma de la carta (hoja 00_Registros)", sev="Alto", nia="NIA 210",
                   alerta="Limitación al alcance impuesta por la dirección: puede impedir emitir una opinión (NIA 210 párr. 7; NIA 705).",
                   resp="Pedir a la dirección que retire la limitación; si no la retira, evaluar el efecto en la opinión.", eeff=True))
    claves = ("relacionad", "accionista", "remuneraci", "directores")
    ctas = [x["cuenta"] for x in c["cuentas"] if any(k in x["cuenta"].lower() for k in claves)]
    v = "Sí" if ctas else "No"
    out.append(_it(H24, "MES-01", "Materialidad específica", "Partidas que requieren una materialidad inferior (partes relacionadas, "
                   "accionistas, remuneración de la dirección)", "NIA 320 párr. 10 y A10–A11 (VERIFICAR)", "info",
                   fx("IF(" + "+".join(f'COUNTIF({b8},"*{k}*")' for k in claves) + '>0,"Sí","No")', v),
                   ("Cuentas del balance: " + "; ".join(dict.fromkeys(ctas))) if ctas else
                   "Sin cuentas de partes relacionadas, accionistas o remuneraciones en el balance"))
    r = pos["comunicacion"]
    x = reg["comunicacion"]
    pend = f"{PENDIENTE} registrar el envío de la carta de planificación generada por la plataforma"
    v = pend if not x["fecha"] else "Enviada" + (f" · {x['detalle']}" if x["detalle"] else "")
    out.append(_it(H24, "COM-01", "Comunicación con el gobierno", "Comunicación de la planificación a los responsables del gobierno "
                   "(alcance, momento y riesgos significativos)", "NIA 260 (Revisada) párr. 15", "registro",
                   fx(f'IF({R_}D{r}="","{pend}","Enviada"&IF({R_}F{r}="",""," · "&{R_}F{r}))', v),
                   "Carta de planificación generada por la plataforma (hoja 32)",
                   fx(f'IF({R_}D{r}="","",{R_}D{r})', x["fecha"] or ""), fx(f'IF({R_}B{r}="","",{R_}B{r})', x["actor"])))
    # 26 · discusión del equipo e indicios de fraude
    ra = pos["asistencia"]
    n_as = len(ra)
    cnt = f'COUNTIF({R_}$A${FILA0}:$A${FILA0 + c["n_reg"] - 1},"{TIPO_ASIST}")'
    pend = f"{PENDIENTE} confirmaciones de asistencia en la plataforma"
    f_min = f'MIN({",".join(f"{R_}D{r}" for r in ra)})' if ra else '""'
    v_min = min((x["fecha"] for x in reg["asistencia"] if x["fecha"]), default="")
    out.append(_it(H26, "DIS-01", "Discusión del equipo del encargo", "Discusión del equipo: fecha y asistentes",
                   "NIA 315 (Revisada 2019) párr. 17; NIA 240 párr. 15 (VERIFICAR)", "registro",
                   fx(f'IF({cnt}=0,"{pend}",{cnt}&" asistentes")', f"{n_as} asistentes" if n_as else pend),
                   "Registros de asistencia (hoja 00_Registros)", fx(f_min, v_min) if ra else None))
    socio = any(x["rol"] == "Socio" for x in reg["asistencia"])
    out.append(_it(H26, "DIS-02", "Discusión del equipo del encargo", "Participación del socio del encargo en la discusión",
                   "NIA 315 (Revisada 2019) párr. 17 (VERIFICAR)", "alerta_no",
                   fx(f'IF({cnt}=0,"{pend}",IF(COUNTIFS({R_}$A${FILA0}:$A${FILA0 + c["n_reg"] - 1},"{TIPO_ASIST}",'
                      f'{R_}$C${FILA0}:$C${FILA0 + c["n_reg"] - 1},"Socio")>0,"Sí","No"))',
                      pend if not n_as else "Sí" if socio else "No"), "Registros de asistencia (hoja 00_Registros)"))
    acta = "Acta generada por la plataforma: riesgos de las hojas 12, 13 y 28 e indicios de fraude de esta hoja"
    out.append(_it(H26, "DIS-03", "Discusión del equipo del encargo", "Temas: susceptibilidad a incorrección material, incluida la "
                   "debida a fraude, y conclusiones", "NIA 315 (Revisada 2019) párr. 17; NIA 240 párr. 15 (VERIFICAR)", "info",
                   fx(f'IF({cnt}=0,"{pend}","{acta}")', acta if n_as else pend), "Acta de la discusión (documento de la plataforma)"))
    out.append(_it(H26, "FRA-01", "Fraude: indagaciones e indicios", "Indagaciones sobre fraude a la dirección, al gobierno y a la "
                   "auditoría interna", "NIA 240 párr. 17–21 (VERIFICAR)", "no_eval", FUERA, "Decisión de la firma"))
    d = c["datos"]
    E9, F9, I10, F10, par = c["E9"], c["F9"], c["I10"], c["F10"], c["par"]
    conds = [(f"{E9}D{F9['Utilidad neta']}<0", "pérdida del período", d["ut"] < 0),
             (f"{E9}D{F9['PATRIMONIO TOTAL']}<=0", "patrimonio negativo o nulo", d["pat"] <= 0),
             (f"N({I10}E{F10['endTotal']})>70", "endeudamiento del activo mayor al 70 %", (d["end"] or 0) > 70),
             (f'AND(ISNUMBER({E9}F{F9["Ventas netas"]}),N({E9}F{F9["Ventas netas"]})*100<=-{par("umbralVarPct")})',
              "caída de las ventas mayor al umbral de variación", d["vven"] is not None and d["vven"] * 100 <= -d["umbral"])]
    f_, v_ = _partes(conds)
    out.append(_it(H26, "FRA-02", "Fraude: indagaciones e indicios", "Indicios de incentivos o presiones (resultados, patrimonio, "
                   "endeudamiento, ventas)", "NIA 240 párr. 24 y Anexo 1 (VERIFICAR)", "alerta_si", fx(f_, v_),
                   "Estados resumidos (hoja 09) e índices (hoja 10)", sev="Alto", nia="NIA 240",
                   alerta="Incentivos o presiones para manipular la información financiera: factor de riesgo de fraude.",
                   resp=_FACTOR_FRAUDE, eeff=True))
    fila27 = c["fila27"]
    alto_carta = any(x["nivel"] == "Alto" for x in carta)
    conds = [(f'COUNTIF({j12},"Alto")>0', "hallazgos altos o significativos en la carta de control interno", alto_carta),
             (f'COUNTIF({fila27},"Alerta")>0', "deficiencias en el control interno o en TI (hoja 27)", c["alertas27"])]
    f_, v_ = _partes(conds)
    out.append(_it(H26, "FRA-03", "Fraude: indagaciones e indicios", "Indicios de oportunidades (deficiencias de control interno o "
                   "de TI)", "NIA 240 párr. 24 y Anexo 1 (VERIFICAR)", "alerta_si", fx(f_, v_), "Carta de control interno (hoja 12) "
                   "y hoja 27", sev="Alto", nia="NIA 240", alerta="Oportunidades para cometer fraude: factor de riesgo de fraude.",
                   resp=_FACTOR_FRAUDE, eeff=True))
    act = any(x["origen"] == "Informe anterior" and x["presenta"] == "Sí" and x["norma"] == "NIA 705 y 710" for x in riesgos)
    v = "Sí: opinión modificada o salvedades del año anterior (hoja 13)" if act else "No"
    out.append(_it(H26, "FRA-04", "Fraude: indagaciones e indicios", "Indicios de actitudes o racionalización (opinión modificada "
                   "o salvedades del año anterior)", "NIA 240 párr. 24 y Anexo 1 (VERIFICAR)", "alerta_si",
                   fx(f'IF(COUNTIFS({b13},"Informe anterior",{f13},"Sí",{i13},"NIA 705 y 710")>0,"Sí: opinión modificada o salvedades '
                      f'del año anterior (hoja 13)","No")', v), "Informe del año anterior (RQ-005) y hoja 13", sev="Alto", nia="NIA 240",
                   alerta="Actitudes o racionalización de la dirección: factor de riesgo de fraude.", resp=_FACTOR_FRAUDE, eeff=True))
    fr = any("fraude" in (x["proceso"] + " " + x["hallazgo"]).lower() for x in carta)
    out.append(_it(H26, "FRA-05", "Fraude: indagaciones e indicios", "Hallazgos de la carta de control interno que mencionan fraude",
                   "NIA 240 párr. 26–27", "alerta_si",
                   fx(f'IF(COUNTIF({b12},"*fraude*")+COUNTIF({c12},"*fraude*")>0,"Sí: riesgo significativo (hoja 12)","No")',
                      "Sí: riesgo significativo (hoja 12)" if fr else "No"), "Carta de control interno (hoja 12)"))
    # 27 · componentes del control interno y controles generales de TI (según la carta)
    for k, comp in enumerate(COMPONENTES):
        cods = [x["id"] for x in carta if x["comp"] == comp]
        out.append(_eval_carta(f"CI-{k + 1:02d}", "Componentes del control interno", comp, o12, comp, cods, n12,
                               "Alto" if k == 0 else "Medio", k == 0))
    for k, cat in enumerate(TI):
        cods = [x["id"] for x in carta if x["ti"] == cat]
        out.append(_eval_carta(f"TI-{k + 1:02d}", "Controles generales de TI", cat, p12, cat, cods, n12, "Medio", False))
    # M16 (NIA 402): procesos a cargo de organizaciones de servicio (nómina tercerizada, sistemas en la nube, custodia).
    so = [x["id"] for x in carta if any(k in norm(x["proceso"] + " " + x["hallazgo"]) for k in SERVICIOS)]
    f_so = "+".join(f'COUNTIF({b12},"*{k}*")+COUNTIF({c12},"*{k}*")' for k in SERVICIOS)
    pend = f"{PENDIENTE} sin carta de control interno (RQ-004)"
    v = pend if not n12 else f"Sí: {', '.join(so)} (hoja 12)" if so else "No"
    out.append(_it(H27, "SO-01", "Organizaciones de servicio", "Procesos a cargo de terceros (nómina, sistemas en la nube, "
                   "custodia) que afectan la información financiera", "NIA 402 párr. 9–12 (VERIFICAR)", "alerta_si",
                   fx(f'IF({n12}=0,"{pend}",IF({f_so}>0,"Sí: organización de servicio en la carta (hoja 12)","No"))',
                      pend if not n12 else "Sí: organización de servicio en la carta (hoja 12)" if so else "No"),
                   ("Hallazgos " + ", ".join(so) + " (hoja 12)") if so else "Carta de control interno (hoja 12)",
                   sev="Medio", nia="NIA 402",
                   alerta="Proceso a cargo de una organización de servicio: el control está fuera de la entidad.",
                   resp=("Obtener el informe tipo 1 o tipo 2 del auditor de la organización de servicio y evaluar los controles "
                         "complementarios de la entidad (NIA 402 párr. 12–17 — VERIFICAR).")))
    # Prioridad baja (NIA 610): función de auditoría interna según la carta. Es informativa: si existe, el programa evalúa su
    # objetividad y competencia antes de usar su trabajo; si no consta, no hay nada que hacer.
    ai = [x["id"] for x in carta if any(k in norm(x["proceso"] + " " + x["hallazgo"]) for k in AUDITORIA_INTERNA)]
    f_ai = "+".join(f'COUNTIF({b12},"*{k}*")+COUNTIF({c12},"*{k}*")' for k in AUDITORIA_INTERNA_TXT)
    v = pend if not n12 else AI_SI if ai else AI_NO
    out.append(_it(H27, "AI-01", "Auditoría interna", "Función de auditoría interna: existencia y uso de su trabajo",
                   "NIA 610 (Revisada 2013) párr. 15 y 18 (VERIFICAR)", "info",
                   fx(f'IF({n12}=0,"{pend}",IF({f_ai}>0,"{AI_SI}","{AI_NO}"))', v),
                   ("Hallazgos " + ", ".join(ai) + " (hoja 12)") if ai else "Carta de control interno (hoja 12)"))
    for x in out:
        x["estado"] = _estado(x["kind"], x["res"]["v"] if isinstance(x["res"], dict) else x["res"])
    return out


_NORMA_CI = {"Entorno de control": "NIA 315 (Revisada 2019) párr. 21 (VERIFICAR)",
             "Proceso de valoración del riesgo": "NIA 315 (Revisada 2019) párr. 22–23 (VERIFICAR)",
             "Sistema de información y comunicación": "NIA 315 (Revisada 2019) párr. 25 (VERIFICAR)",
             "Actividades de control": "NIA 315 (Revisada 2019) párr. 26 (VERIFICAR)",
             "Seguimiento del control interno": "NIA 315 (Revisada 2019) párr. 24 (VERIFICAR)"}


def _eval_carta(codigo, bloque, aspecto, rango, clave, cods, n12, sev, eeff):
    pend = f"{PENDIENTE} sin carta de control interno (RQ-004)"
    v = pend if not n12 else "Con deficiencias" if cods else "Sin deficiencias informadas en la carta"
    ti = bloque.endswith("TI")
    alerta = (("Deficiencias en los controles generales de TI (" + aspecto.lower() + "): no confiar en controles automáticos ni en "
               "informes del sistema sin probar su integridad y exactitud.") if ti else
              "Deficiencias en el entorno de control: riesgo a nivel de estados financieros; no confiar en los controles y ampliar "
              "las pruebas sustantivas." if eeff else
              f"Deficiencias en {aspecto[0].lower() + aspecto[1:]}: considerarlas en la valoración de los riesgos y comunicar las "
              "significativas por escrito (NIA 265).")
    resp = ("Probar la integridad y exactitud de los informes usados como evidencia; considerar un especialista en TI (NIA 620)."
            if ti else "Respuesta global (NIA 330 párr. 5) y comunicación de las deficiencias significativas (NIA 265)." if eeff else
            "Evaluar si son deficiencias significativas, no confiar en esos controles y ampliar las pruebas sustantivas del área.")
    return _it(H27, codigo, bloque, aspecto, "NIA 315 (Revisada 2019) párr. 26 c)–d) (VERIFICAR)" if ti else _NORMA_CI[aspecto],
               "alerta_con", fx(f'IF({n12}=0,"{pend}",IF(COUNTIF({rango},"{clave}")>0,"Con deficiencias",'
                                f'"Sin deficiencias informadas en la carta"))', v),
               ("Hallazgos " + ", ".join(cods) + " (hoja 12)") if cods else "Ningún hallazgo de la carta en este aspecto",
               sev=sev, nia="NIA 315", alerta=alerta, resp=resp, eeff=eeff)


def filas_evaluacion(items: list, hoja_: str) -> list:
    filas = []
    for x in (i for i in items if i["hoja"] == hoja_):
        r = FILA0 + len(filas)
        filas.append([x["bloque"], x["codigo"], x["aspecto"], x["norma"], x["res"], x["evid"], x["fecha"], x["por"],
                      fx(_f_estado(x["kind"], f"E{r}"), x["estado"])])
    return filas


def fila_de(items: list) -> dict:
    """Hoja y fila de cada evaluación."""
    out, k = {}, {}
    for x in items:
        k[x["hoja"]] = k.get(x["hoja"], 0) + 1
        out[x["codigo"]] = (x["hoja"], FILA0 + k[x["hoja"]] - 1)
    return out


def riesgos(items: list, sin_herramienta: str) -> list[dict]:
    """Una fila de la hoja 13 por evaluación con alerta que es un riesgo; su «¿Se presenta?» es fórmula al estado."""
    return [{"cod": "cuestionario", "q": x["codigo"], "origen": "Planificación (hojas 24, 26 y 27)", "rubro": x["bloque"],
             "cond": f"{x['codigo']}: {x['aspecto']}", "valor": None, "presenta": "Sí", "riesgo": x["alerta"], "sev": x["sev"],
             "norma": x["nia"], "resp": x["resp"], "herr": sin_herramienta, "eeff": x["eeff"]}
            for x in items if x["estado"] == "Alerta" and x["sev"]]


def ref_estado(pos: dict, codigo: str) -> str:
    h, r = pos[codigo]
    return f"'{h}'!I{r}"


def ref_resultado(pos: dict, codigo: str) -> str:
    h, r = pos[codigo]
    return f"'{h}'!E{r}"


# --- hoja 25 (equipo e independencia, desde los registros) ----------------------------------------------------------
COLS_EQUIPO = [["Integrante", "t"], ["Rol", "t"], ["¿Confirmó su independencia?", "t"], ["Fecha de la confirmación", "d"],
               ["Amenazas identificadas", "t"], ["Salvaguardas aplicadas", "t"], ["Años con el cliente", "n"], ["Estado", "t"]]
ALERTA_AMENAZA = "Alerta · amenaza sin salvaguarda"
ALERTA_ROTACION = "Alerta · rotación del socio (entidad de interés público)"
SIN_EQUIPO = f"{PENDIENTE} nadie confirmó su independencia en la plataforma"


def estado_equipo(x: dict, eip: str, rot: float) -> str:
    if not x["fecha"]:
        return "Pendiente"
    if x["amenazas"] and not x["salvaguardas"]:
        return ALERTA_AMENAZA
    if x["rol"] == "Socio" and eip == SI and (x["anios"] or 0) >= rot:
        return ALERTA_ROTACION
    return "Conforme"


def filas_equipo(reg: dict, pos: dict, eip: str, rot: float, par) -> tuple[list, list]:
    filas, estados = [], []
    for x, rr in zip(reg["equipo"], pos["equipo"]):
        r = FILA0 + len(filas)
        e = estado_equipo(x, eip, rot)
        estados.append(e)
        filas.append([fx(f"{R_}B{rr}", x["integrante"]), fx(f"{R_}C{rr}", x["rol"]),
                      fx(f'IF({R_}D{rr}="","{PENDIENTE}","Sí")', "Sí" if x["fecha"] else PENDIENTE),
                      fx(f'IF({R_}D{rr}="","",{R_}D{rr})', x["fecha"] or ""), fx(f'IF({R_}E{rr}="","",{R_}E{rr})', x["amenazas"]),
                      fx(f'IF({R_}F{rr}="","",{R_}F{rr})', x["salvaguardas"]), fx(f"N({R_}G{rr})", n2(x["anios"] or 0)),
                      fx(f'IF(C{r}="{PENDIENTE}","Pendiente",IF(AND(E{r}<>"",F{r}=""),"{ALERTA_AMENAZA}",IF(AND(B{r}="Socio",'
                         f'{par("interesPublico")}="Sí",G{r}>={par("aniosRotacionSocio")}),"{ALERTA_ROTACION}","Conforme")))', e)])
    if not filas:
        filas.append([SIN_EQUIPO, "", PENDIENTE, None, "", "", None, "Pendiente"])
        estados.append("Pendiente")
    return filas, estados


def rango_equipo(col: str, n: int) -> str:
    return f"'{H25}'!${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


# --- hoja 30 (diferencias, NIA 450; automáticas) --------------------------------------------------------------------
COLS_DIF = [["Referencia", "t"], ["Código", "t"], ["Descripción", "t"], ["Tipo", "t"], ["Período", "t"], ["¿Corregida?", "t"],
            ["Importe de la diferencia", "n"], ["¿Supera el umbral trivial?", "t"], ["¿Se acumula?", "t"], ["Evaluación", "t"]]
TXT_DIF_ACTUAL = "Incorrecciones no corregidas del período (se registran en la ejecución)"
TXT_DIF_ANTERIOR = "Diferencias de apertura y del año anterior no corregidas"
TXT_DIF_TOTAL = "Total acumulado"
TXT_DIF_DESEMP = "Materialidad de desempeño"
TXT_DIF_GLOBAL = "Materialidad global"
TXT_DIF_CONCL = "Conclusión (NIA 450 párr. 11)"
CONCL_SIN_MAT = "Pendiente: sin materialidad (NIA 320)"
CONCL_GLOBAL = "Revisar · supera la materialidad global: incorrección material (NIA 450 párr. 11)"
CONCL_DESEMP = "Revisar · supera la materialidad de desempeño: ampliar los procedimientos"
CONCL_OK = "Conforme · por debajo de la materialidad de desempeño"


def diferencias(notas: list, informe: list, fila14: dict, refs: dict) -> list[dict]:
    """Automáticas: notas del año anterior que no concilian con el balance (saldos de apertura, NIA 510) y salvedades con
    importe del informe anterior (confirmar si se corrigieron). Cada importe es fórmula a su hoja."""
    difs = []
    for i, n in enumerate(notas):
        if abs(n["dif"]) >= 0.01:
            difs.append({"referencia": f"Nota {n['nota']}", "codigo": n["codigos"], "tipo": "Factual", "periodo": "Anterior",
                         "descripcion": f"{n['titulo']}: el balance del cierre anterior difiere de la nota auditada (saldos de apertura)",
                         "corregida": NO, "importe": n["dif"], "f": f"{refs['N15']}F{FILA0 + i}"})
    for j, x in enumerate(informe):
        if x["tipo"] == "Salvedad" and x["importe"] is not None and j in fila14:
            difs.append({"referencia": f"RQ-005 · {x['concepto']}", "codigo": "", "tipo": "Factual", "periodo": "Anterior",
                         "descripcion": f"{x['concepto']}: salvedad del informe anterior (confirmar si se corrigió)", "corregida": NO,
                         "importe": float(x["importe"]), "f": f"{refs['P14']}D{fila14[j]}"})
    return difs


def calcula_diferencias(difs: list, mt: dict) -> dict:
    triv, des, glo = mt["trivial"], mt["desempeno"], mt["global"]
    for x in difs:
        x["supera"] = SI if triv is None or abs(x["importe"]) >= triv else NO
        x["acumula"] = SI if x["corregida"] == NO and x["supera"] == SI else NO
    act = sum(x["importe"] for x in difs if x["periodo"] == "Actual" and x["acumula"] == SI)
    ant = sum(x["importe"] for x in difs if x["periodo"] == "Anterior" and x["acumula"] == SI)
    tot = act + ant
    concl = (CONCL_SIN_MAT if not glo else CONCL_GLOBAL if abs(tot) >= glo - 1e-9 else
             CONCL_DESEMP if abs(tot) >= des - 1e-9 else CONCL_OK)
    return {"actual": act, "anterior": ant, "total": tot, "conclusion": concl}


def filas_diferencias(difs: list, res: dict, mt: dict, refs: dict) -> tuple[list, list, dict]:
    filas, estilos = [], []
    trv = refs["TRIVIAL"]
    for i, x in enumerate(difs):
        r = FILA0 + i
        filas.append([x["referencia"], x["codigo"], x["descripcion"], x["tipo"], x["periodo"], x["corregida"],
                      fx(x["f"], n2(x["importe"])),
                      fx(f'IF({trv}="","Sí",IF(ABS(G{r})>={trv},"Sí","No"))', x["supera"]),
                      fx(f'IF(AND(F{r}="No",H{r}="Sí"),"Sí","No")', x["acumula"]), None])
        estilos.append(None)
    n, a, b = len(difs), FILA0, FILA0 + len(difs) - 1
    fila = {}

    def suma(per):
        return f'SUMIFS(G{a}:G{b},E{a}:E{b},"{per}",I{a}:I{b},"Sí")' if n else "0"
    r1 = FILA0 + n
    fila["actual"], fila["anterior"], fila["total"], fila["desemp"], fila["global"], fila["concl"] = range(r1, r1 + 6)
    filas += [
        [TXT_DIF_ACTUAL, None, None, None, None, None, fx(suma("Actual"), n2(res["actual"])), None, None, None],
        [TXT_DIF_ANTERIOR, None, None, None, None, None, fx(suma("Anterior"), n2(res["anterior"])), None, None, None],
        [TXT_DIF_TOTAL, None, None, None, None, None, fx(f"G{fila['actual']}+G{fila['anterior']}", n2(res["total"])), None, None,
         None],
        [TXT_DIF_DESEMP, None, None, None, None, None, fx(f'IF({refs["DESEMP"]}="","",{refs["DESEMP"]})', n2(mt["desempeno"])),
         None, None, None],
        [TXT_DIF_GLOBAL, None, None, None, None, None, fx(f'IF({refs["GLOBAL"]}="","",{refs["GLOBAL"]})', n2(mt["global"])),
         None, None, None],
        [TXT_DIF_CONCL, None, None, None, None, None, None, None, None,
         fx(f'IF(G{fila["global"]}="","{CONCL_SIN_MAT}",IF(ABS(G{fila["total"]})>=G{fila["global"]},"{CONCL_GLOBAL}",'
            f'IF(ABS(G{fila["total"]})>=G{fila["desemp"]},"{CONCL_DESEMP}","{CONCL_OK}")))', res["conclusion"])],
    ]
    estilos += [{"tipo": "total"}] * 3 + [None, None, {"tipo": "control"}]
    return filas, estilos, fila


# --- hoja 29 (extensión y muestreo) ---------------------------------------------------------------------------------
COLS_MUESTREO = [["PT", "t"], ["Código", "t"], ["Cuenta", "t"], ["Nivel", "t"], ["Confianza (%)", "n"],
                 ["Población (saldo al corte)", "n"], ["Error tolerable", "n"], ["Error esperado", "n"],
                 ["Factor de confiabilidad", "n"], ["Factor de expansión", "n"], ["Tamaño de la muestra", "i"],
                 ["Intervalo de muestreo", "n"], ["Método", "t"]]
METODO_SIN_MAT = "Pendiente: sin materialidad (NIA 320)"
METODO_MENOR = "Sin muestra: saldo menor que el error tolerable"
METODO_REVISAR = "Revisar: el error esperado consume el tolerable"
METODO_MUS = "Unidad monetaria; mayores que el intervalo al 100 %"


def _alto(nivel: str) -> bool:
    return nivel in ("Alto", "Significativo") or str(nivel).startswith("Pendiente")


def _ef(conf: float) -> float:
    """Factor de expansión del error esperado (tabla del muestreo por unidad monetaria — VERIFICAR)."""
    return 1.9 if conf >= 99 else 1.6 if conf >= 95 else 1.5 if conf >= 90 else 1.4 if conf >= 85 else 1.3 if conf >= 80 else 1.2


def filas_muestreo(cuentas: list, mt: dict, pe: dict, refs: dict, par) -> tuple[list, dict]:
    """``cuentas`` = [{pt, codigo, cuenta, nivel, r28, r08, saldo}] (las que tienen su propio procedimiento en la hoja 19;
    el nivel es el más alto de la cuenta en la hoja 28)."""
    filas, tam = [], {}
    des = mt["desempeno"]
    for i, c in enumerate(cuentas):
        r = FILA0 + i
        nivel = c["nivel"]
        # Enfoque del ciclo (hoja 45): si se confía en los controles, la confianza del muestreo baja un nivel.
        if c.get("confia"):
            conf = pe["confianzaMedia"] if _alto(nivel) else pe["confianzaBaja"]
        else:
            conf = pe["confianzaAlta"] if _alto(nivel) else pe["confianzaMedia"] if nivel == "Medio" else pe["confianzaBaja"]
        pob = abs(c["saldo"])
        rf = round(-math.log(1 - conf / 100), 4)
        ef = _ef(conf)
        te = des
        ee = None if te is None else te * pe["pctErrorEsperado"] / 100
        if te is None:
            n, metodo = "", METODO_SIN_MAT
        elif pob < te:
            n, metodo = 0, METODO_MENOR
        elif te - ee * ef <= 0:
            n, metodo = "", METODO_REVISAR
        else:
            n, metodo = math.ceil(round(pob * rf / (te - ee * ef), 6)), METODO_MUS
        inter = "" if n in ("", 0) else _redondeo(pob / n, 2)   # como ROUND de Excel: la mitad se aleja del cero
        tam[c["codigo"]] = (r, n, metodo)
        filas.append([
            c["pt"], c["codigo"], c["cuenta"], fx(f"{refs['P28']}K{c['r28']}", nivel),
            fx(_f_conf(r, c.get("r45"), par), conf),
            fx(f"ABS({refs['H8']}H{c['r08']})", n2(pob)),
            fx(f'IF({refs["DESEMP"]}="","",{refs["DESEMP"]})', n2(te)),
            fx(f'IF(G{r}="","",G{r}*{par("pctErrorEsperado")}/100)', n2(ee)),
            fx(f"ROUND(-LN(1-E{r}/100),4)", rf),
            fx(f"IF(E{r}>=99,1.9,IF(E{r}>=95,1.6,IF(E{r}>=90,1.5,IF(E{r}>=85,1.4,IF(E{r}>=80,1.3,1.2)))))", ef),
            fx(f'IF(G{r}="","",IF(F{r}<G{r},0,IF(G{r}-H{r}*J{r}<=0,"",ROUNDUP(ROUND(F{r}*I{r}/(G{r}-H{r}*J{r}),6),0))))', n),
            fx(f'IF(OR(K{r}="",K{r}=0),"",ROUND(F{r}/K{r},2))', inter),
            fx(f'IF(G{r}="","{METODO_SIN_MAT}",IF(F{r}<G{r},"{METODO_MENOR}",IF(K{r}="","{METODO_REVISAR}","{METODO_MUS}")))', metodo),
        ])
    return filas, tam


def _redondeo(v: float, d: int) -> float:
    from decimal import ROUND_HALF_UP, Decimal
    return float(Decimal(str(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def _f_conf(r: int, r45: str | None, par) -> str:
    alto = f'OR(D{r}="Alto",D{r}="Significativo",LEFT(D{r},9)="Pendiente")'
    normal = f'IF({alto},{par("confianzaAlta")},IF(D{r}="Medio",{par("confianzaMedia")},{par("confianzaBaja")}))'
    if not r45:
        return normal
    return f'IF(LEFT({r45},7)="Confiar",IF({alto},{par("confianzaMedia")},{par("confianzaBaja")}),{normal})'


EXT_ALTO = "Pruebas de detalle con confianza alta; partidas clave y mayores que el intervalo al 100 %"
EXT_MEDIO = "Pruebas de detalle con confianza media (muestra por unidad monetaria)"
EXT_BAJO = "Analíticos sustantivos con un umbral igual a la materialidad de desempeño (NIA 520)"
EXT_ENCARGO = "Según el procedimiento (todo el encargo)"


def extension(r19: int, nivel: str, tam: tuple | None, refs: dict) -> dict:
    """Columna «Extensión» del programa: la muestra de la hoja 29 en las cuentas; por nivel en los riesgos."""
    if tam:
        r29, n, metodo = tam
        k, mm = f"{refs['P29']}K{r29}", f"{refs['P29']}M{r29}"
        v = (f"Muestra de {n} partidas por unidad monetaria (hoja 29)" if isinstance(n, int) and n > 0 else metodo)
        return fx(f'IF(AND(ISNUMBER({k}),N({k})>0),"Muestra de "&{k}&" partidas por unidad monetaria (hoja 29)",{mm})', v)
    d = f"D{r19}"
    v = (EXT_ENCARGO if nivel == "Todo encargo" else EXT_ALTO if _alto(nivel) else EXT_MEDIO if nivel == "Medio" else EXT_BAJO)
    return fx(f'IF({d}="Todo encargo","{EXT_ENCARGO}",IF(OR({d}="Alto",{d}="Significativo",LEFT({d},9)="Pendiente"),"{EXT_ALTO}",'
              f'IF({d}="Medio","{EXT_MEDIO}","{EXT_BAJO}")))', v)


# --- hoja 28 (afirmaciones) -----------------------------------------------------------------------------------------
AFIRMACIONES = [("Existencia u ocurrencia", ("existencia", "ocurrencia")), ("Integridad", ("integridad",)),
                ("Exactitud y valuación", ("exactitud", "valuacion", "valoracion", "condicion")), ("Corte", ("corte",)),
                ("Derechos y obligaciones", ("derecho", "obligacion")),
                ("Presentación y clasificación", ("presentacion", "clasificacion", "revelacion"))]
COLS_AFIRMACIONES = ([["Nivel de la valoración", "t"], ["Código", "t"], ["Cuenta o riesgo", "t"], ["Sección u origen", "t"]]
                     + [[a, "t"] for a, _ in AFIRMACIONES]
                     + [["Nivel más alto", "t"], ["Riesgos vinculados", "t"], ["¿Se probará el control?", "t"], ["Respuesta", "t"]])
RANGO = {"Significativo": 4, "Alto": 3, "Medio": 2, "Bajo": 1}
NIVEL_EEFF = "Estados financieros"
NIVEL_AFIRMACION = "Afirmación"
RESP_GLOBAL = "Respuesta global (NIA 330 párr. 5): escepticismo, personal con experiencia, supervisión e imprevisibilidad"
RESP_570 = "Evaluar la capacidad de continuar y los planes de la dirección (NIA 570)"
RESP_AFIRMACION = "Por afirmación en el programa (hoja 19)"


AUDITORIA_INTERNA = ("auditoriainterna", "auditorinterno", "auditoresinternos")
# Mismas claves como texto para COUNTIF (Excel no distingue tildes con comodines: se buscan las dos formas).
AUDITORIA_INTERNA_TXT = ("auditoría interna", "auditoria interna", "auditor interno", "auditores internos")
AI_SI = "Sí: la carta de control interno menciona la función de auditoría interna (hoja 12)"
AI_NO = "No consta una función de auditoría interna en la carta de control interno (hoja 12)"
PROC_AUDITORIA_INTERNA = ("Evaluar la objetividad, la competencia y el enfoque sistemático de la función de auditoría interna y decidir "
                          "si se usa su trabajo y en qué áreas; si se usa, reejecutar parte de él (NIA 610 párr. 15–25 — VERIFICAR).")
EVID_AUDITORIA_INTERNA = "Estatuto de la auditoría interna, plan anual, informes emitidos y papeles de trabajo de la función."
SERVICIOS = ("terceriz", "outsourc", "nube", "externaliz", "proveedor de servicio", "custodi", "servicio externo")


def menciona(texto: str, claves: tuple) -> bool:
    t = norm(texto)
    return t in ("todas", "todo", "") or any(k in t for k in claves)


def filas_afirmaciones(eeff: list, cuentas: list, refs: dict) -> list:
    """``eeff`` = [(j, riesgo)] a nivel de estados financieros; ``cuentas`` = [{codigo, cuenta, sec, r18, material, relevantes,
    vinc: [(tipo, fila, nivel, aseveraciones, codigo, probar)]}] (tipo «12» o «13»)."""
    filas = []
    for j, x in eeff:
        r13 = FILA0 + j
        v = x["sev"] if x["presenta"] == "Sí" else "No se presenta"
        filas.append([NIVEL_EEFF, x["codigo"], x["riesgo"], x["origen"], *(["Todas"] * len(AFIRMACIONES)),
                      fx(f'IF({refs["R13"]}F{r13}="Sí",{refs["R13"]}H{r13},"No se presenta")', v), x["codigo"], "",
                      RESP_570 if x["norma"] == "NIA 570" else RESP_GLOBAL])
    for c in cuentas:
        r = FILA0 + len(filas)
        mat_f = f'OR({refs["C18"]}F{c["r18"]}="Sí",{refs["C18"]}G{c["r18"]}="Sí")'
        celdas = []
        for nombre, claves in AFIRMACIONES:
            conds = {k: [] for k in RANGO}
            vals = []
            for tipo, fila, nivel, aser, _cod, _pr in c["vinc"]:
                if not menciona(aser, claves):
                    continue
                if nivel:
                    vals.append(nivel)
                if tipo == "12":
                    m_, j_ = f"{refs['R12']}M{fila}", f"{refs['R12']}J{fila}"
                    conds["Significativo"].append(f'{m_}="Sí"')
                    conds["Alto"].append(f'OR({j_}="Alto",{j_}="Pendiente de calificación")')
                    conds["Medio"].append(f'{j_}="Medio"')
                    conds["Bajo"].append(f'{j_}="Bajo"')
                else:
                    f_, h_ = f"{refs['R13']}F{fila}", f"{refs['R13']}H{fila}"
                    for k in RANGO:
                        conds[k].append(f'AND({f_}="Sí",{h_}="{k}")')
            relevante = nombre in c["relevantes"]
            if relevante:
                vals.append("Medio" if c["material"] else "Bajo")
            v = max(vals, key=lambda z: RANGO[z]) if vals else "—"
            fin = f'IF({mat_f},"Medio","Bajo")' if relevante else ('IF(OR(' + ",".join(conds["Bajo"]) + '),"Bajo","—")'
                                                                  if conds["Bajo"] else '"—"')
            f_ = fin
            for k in ("Medio", "Alto", "Significativo"):
                if conds[k]:
                    f_ = f'IF(OR({",".join(conds[k])}),"{k}",{f_})'
            celdas.append(fx(f_, v) if (conds["Bajo"] or relevante) else "—")
        niveles = [x["v"] if isinstance(x, dict) else x for x in celdas]
        alto = max((z for z in niveles if z in RANGO), key=lambda z: RANGO[z], default="—")
        rng = f"E{r}:J{r}"
        f_alto = (f'IF(COUNTIF({rng},"Significativo")>0,"Significativo",IF(COUNTIF({rng},"Alto")>0,"Alto",'
                  f'IF(COUNTIF({rng},"Medio")>0,"Medio",IF(COUNTIF({rng},"Bajo")>0,"Bajo","—"))))')
        carta = [fila for tipo, fila, *_r in c["vinc"] if tipo == "12"]
        probar = "Sí" if any(t == "12" and pr_ == "Sí" for t, _f, _n, _a, _c, pr_ in c["vinc"]) else "No"
        f_pr = (fx("IF(OR(" + ",".join(f'{refs["R12"]}N{f}="Sí"' for f in carta) + '),"Sí","No")', probar) if carta else "No")
        filas.append([NIVEL_AFIRMACION, c["codigo"], c["cuenta"], c["sec"], *celdas, fx(f_alto, alto),
                      " ".join(dict.fromkeys(cod for *_r, cod, _p in c["vinc"])), f_pr, RESP_AFIRMACION])
    return filas


# --- hoja 32 (comunicación con el gobierno y asuntos clave candidatos) ----------------------------------------------
COLS_COMUNICACION = [["Asunto", "t"], ["Contenido", "x"], ["Norma", "t"], ["Estado", "t"]]
RESPONSABILIDADES = ("El auditor se forma y expresa una opinión sobre los estados financieros preparados por la dirección bajo la "
                     "supervisión del gobierno; la auditoría no los exime de sus responsabilidades.")
NO_KAM = "No aplica: la entidad no es cotizada ni de interés público (NIA 701 párr. 5)"


def filas_comunicacion(eval_pos: dict, estados: dict, resultados: dict, sino: dict, sig: list, kam_ant: list, revisores: list,
                       refs: dict, par, fechas: dict, n_equipo: int) -> list:
    """``sig`` = riesgos significativos [(hoja, fila, columna_texto, columna_flag, valor_flag, texto, codigo)];
    ``kam_ant`` = asuntos clave del informe anterior [(fila 14, concepto)]."""
    eip = sino.get("interesPublico") == SI

    def fecha(k, etq):
        v = fechas.get(k)
        return [etq, fx(f'IF({par(k)}="","{PENDIENTE}",{par(k)})', v or PENDIENTE), "NIA 260 (Revisada) párr. 15",
                fx(f'IF({par(k)}="","Pendiente","Documentado")', "Documentado" if v else "Pendiente")]
    filas = [
        ["Responsabilidades del auditor", RESPONSABILIDADES, "NIA 260 (Revisada) párr. 14", "Documentado"],
        fecha("fechaPreliminar", "Alcance y momento · visita preliminar"),
        fecha("fechaFinal", "Alcance y momento · visita final"),
        fecha("fechaInforme", "Alcance y momento · entrega del informe"),
        ["Materialidad global (si se decide comunicarla)", fx(f'IF({refs["GLOBAL"]}="","{PENDIENTE}",{refs["GLOBAL"]})',
                                                               n2(refs["mt_global"]) if refs["mt_global"] else PENDIENTE),
         "NIA 260 (Revisada) párr. A13 (VERIFICAR)",
         fx(f'IF({refs["GLOBAL"]}="","Pendiente","Documentado")', "Documentado" if refs["mt_global"] else "Pendiente")],
    ]
    for h_, fila, col_t, col_f, flag, texto, cod in sig:
        filas.append([f"Riesgo significativo · {cod}", fx(f"'{h_}'!{col_t}{fila}", texto), "NIA 260 (Revisada) párr. 15",
                      fx(f'IF(\'{h_}\'!{col_f}{fila}="{flag}","Comunicar","No aplica")', "Comunicar")])
    if not sig:
        filas.append(["Riesgos significativos", "Sin riesgos significativos identificados en las hojas 12 y 13",
                      "NIA 260 (Revisada) párr. 15", "Documentado"])
    ind_v = ("Declaración de independencia de la firma y del equipo (hoja 25)" if eip else
             "Solo si hay amenazas no resueltas (la entidad no es de interés público)")
    filas.append(["Independencia", fx(f'IF({par("interesPublico")}="Sí","Declaración de independencia de la firma y del equipo '
                                      f'(hoja 25)","Solo si hay amenazas no resueltas (la entidad no es de interés público)")', ind_v),
                  "NIA 260 (Revisada) párr. 17", "Documentado" if eip or n_equipo else "Pendiente"])
    h, r = eval_pos["COM-01"]
    filas.append(["Envío de la carta de planificación", fx(f"'{h}'!E{r}", resultados["COM-01"]), "NIA 260 (Revisada) párr. 15",
                  fx(f"'{h}'!I{r}", estados["COM-01"])])
    rev_v = ", ".join(revisores) if revisores else PENDIENTE
    n_rev = f'COUNTIF({rango_equipo("B", n_equipo)},"Revisor de calidad")' if n_equipo else "0"
    filas.append(["Revisor de calidad del encargo (NIGC 2)", rev_v, "NIGC 2; NIA 220 (Revisada) párr. 36 (VERIFICAR)",
                  fx(f'IF({par("interesPublico")}="No","No aplica",IF({n_rev}>0,"Conforme","Revisar"))',
                     "No aplica" if not eip else "Conforme" if revisores else "Revisar")])
    kam = [(f"Asunto clave candidato · {cod}", fx(f"'{h_}'!{col_t}{fila}", texto)) for h_, fila, col_t, _cf, _fl, texto, cod in sig]
    kam += [("Asunto clave candidato · informe anterior", fx(f"{refs['P14']}B{fila}", texto)) for fila, texto in kam_ant]
    for etq, cont in kam:
        filas.append([etq, cont, "NIA 701 párr. 9–10 (VERIFICAR)",
                      fx(f'IF({par("interesPublico")}="Sí","Candidato","No aplica")', "Candidato" if eip else "No aplica")])
    if not kam:
        filas.append(["Asuntos clave de auditoría", fx(f'IF({par("interesPublico")}="Sí","Sin candidatos: documentar por qué",'
                                                       f'"{NO_KAM}")', "Sin candidatos: documentar por qué" if eip else NO_KAM),
                      "NIA 701", "No aplica" if not eip else "Revisar"])
    return filas


# --- explicaciones («Cómo se calcula») ------------------------------------------------------------------------------
_EST = ("«Pendiente» si falta el registro o el documento; «Alerta» si el resultado indica un problema (una limitación, un "
        "indicio de fraude o una deficiencia de control) y la alerta pasa a la hoja 13 como riesgo; «Conforme» o «Documentado» si "
        "está completo; «No evaluado» si la firma decidió no documentarlo en la herramienta.")
_RES = ("Se calcula solo: lee los registros de la plataforma (hoja 00_Registros), los estados e índices (hojas 09 y 10), la carta "
        "de control interno clasificada (hoja 12), los riesgos del informe anterior (hoja 13) o las cuentas del balance (hoja 08).")
EXPLICA = {
    H24: {"Resultado": _RES, "Fecha": "Trae la fecha del registro en la plataforma (hoja 00_Registros).",
          "Registrado por": "Trae quién hizo el registro en la plataforma (hoja 00_Registros).", "Estado": _EST},
    H26: {"Resultado": _RES, "Fecha": "La primera fecha de asistencia registrada en la plataforma.",
          "Estado": _EST},
    H27: {"Resultado": ("Cuenta los hallazgos de la carta de control interno clasificados en ese componente o control de TI "
                        "(hoja 12, columnas O y P): «Con deficiencias» si hay alguno."), "Estado": _EST},
    H25: {"Integrante": "Trae de la hoja 00_Registros a quien confirmó su independencia en la plataforma.",
          "Rol": "El rol que el integrante declaró al confirmar su independencia.",
          "¿Confirmó su independencia?": "«Sí» si el registro tiene fecha de confirmación.",
          "Fecha de la confirmación": "Fecha en que el integrante confirmó su independencia con un clic en la plataforma (hoja 00_Registros).",
          "Amenazas identificadas": "Las amenazas que el integrante declaró al confirmar.",
          "Salvaguardas aplicadas": "Las salvaguardas que el integrante declaró al confirmar.",
          "Años con el cliente": "Años del integrante con el cliente según la plataforma.",
          "Estado": ("Alerta si hay una amenaza sin salvaguarda o si el socio de una entidad de interés público alcanzó los años de "
                     "rotación de la hoja 02; «Pendiente» si falta la confirmación.")},
    H28: {"Nivel más alto": ("El nivel más alto de las seis afirmaciones de la fila; en los riesgos a nivel de estados financieros, "
                             "la severidad de la hoja 13 si el riesgo se presenta."),
          "Existencia u ocurrencia": ("Nivel del riesgo en esa afirmación: el de los riesgos de las hojas 12 y 13 que la mencionan "
                                      "(Significativo, Alto, Medio o Bajo) y, si la afirmación es relevante para la sección, "
                                      "«Medio» cuando la cuenta es material y «Bajo» si no; «—» si no es relevante."),
          "Integridad": "Igual que la primera afirmación, para la integridad (en los pasivos, los pasivos no registrados).",
          "Exactitud y valuación": "Igual que la primera afirmación, para la exactitud y la valuación.",
          "Corte": "Igual que la primera afirmación, para el corte (sobre todo en ingresos, costos y gastos).",
          "Derechos y obligaciones": "Igual que la primera afirmación, para los derechos (activos) y las obligaciones (pasivos).",
          "Presentación y clasificación": "Igual que la primera afirmación, para la presentación, la clasificación y las revelaciones.",
          "¿Se probará el control?": "«Sí» si algún hallazgo de la carta vinculado a la cuenta marca que se probará su control (hoja 12)."},
    H29: {"Nivel": ("Trae el nivel más alto de la cuenta en la valoración por afirmación (hoja 28): si un riesgo significativo "
                    "o alto recae en la cuenta, la muestra se calcula con la confianza alta."),
          "Confianza (%)": ("Según el nivel: alto, significativo o pendiente usa la confianza alta de la hoja 02; medio, la media; "
                            "bajo, la baja. Si el ciclo de la cuenta confía en los controles (hoja 45), baja un nivel."),
          "Población (saldo al corte)": "Saldo al corte de la cuenta en valor absoluto (hoja 08).",
          "Error tolerable": "Es la materialidad de desempeño de la hoja 11.",
          "Error esperado": "Error tolerable por el porcentaje de error esperado de la hoja 02.",
          "Factor de confiabilidad": "Factor de Poisson sin errores para la confianza: −ln(1 − confianza), con 4 decimales.",
          "Factor de expansión": "Factor de la tabla del muestreo por unidad monetaria según la confianza (política de la firma — VERIFICAR).",
          "Tamaño de la muestra": ("Población × factor de confiabilidad ÷ (error tolerable − error esperado × factor de expansión), "
                                   "redondeado hacia arriba; cero si el saldo es menor que el error tolerable."),
          "Intervalo de muestreo": "Población ÷ tamaño de la muestra: toda partida mayor que el intervalo se prueba al 100 %.",
          "Método": "Explica si hay muestra, si el saldo no la necesita o si el error esperado impide calcularla."},
    H30: {"Importe de la diferencia": ("Trae la diferencia de cada nota con el balance anterior (hoja 15) o el importe de la "
                                       "salvedad (hoja 14); abajo suma las que se acumulan y trae las materialidades de la hoja 11."),
          "¿Supera el umbral trivial?": "Compara la diferencia con el umbral de errores claramente insignificantes (hoja 11).",
          "¿Se acumula?": "Se acumula la diferencia no corregida que supera el umbral trivial (NIA 450 párr. 5).",
          "Evaluación": ("Compara el total acumulado con la materialidad global y la de desempeño: supera la global, supera la de "
                         "desempeño o queda por debajo.")},
    H32: {"Contenido": ("Trae las fechas de la hoja 02, la materialidad de la hoja 11, el texto de cada riesgo significativo de "
                        "las hojas 12 y 13, el envío registrado en la plataforma (hoja 24) y los asuntos clave del informe anterior."),
          "Estado": ("«Comunicar» para cada riesgo significativo; «Candidato» para los asuntos clave si la entidad es de interés "
                     "público; el estado del envío de la carta; «Revisar» si una entidad de interés público no tiene revisor de "
                     "calidad en la hoja 25.")},
}
