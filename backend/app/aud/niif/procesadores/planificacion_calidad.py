"""Planificación de la auditoría · pendientes M1–M21 de la revisión de control de calidad (complemento de
``planificacion_nia``; no es una herramienta del catálogo por sí sola).

Todo es automático, como el resto de la planificación: sale de los documentos de entrada (balances, carta de control
interno, informe y notas del año anterior), de la ficha del encargo o de un clic en la plataforma (indagaciones,
consultas y la versión anterior de la planificación). Lo que falta queda «[PENDIENTE]».

Hojas: 34 factores de riesgo inherente (M5), 35 entendimiento estructurado e indagaciones (M7), 36 stand-back y
revelaciones significativas (M8), 37 analíticos sustantivos (M11), 38 estimaciones (M12), 39 leyes y reglamentos (M13),
40 partes relacionadas (M14), 41 empresa en marcha (M15), 42 cambios frente a la versión anterior (M4) y 43 equipo,
horas, supervisión y cierre del archivo (M1 y M2). Los porcentajes y horas son política de la firma.
"""
from __future__ import annotations

import unicodedata

from backend.app.aud.niif.procesadores.base import FILA0, a_num, fx, n2

PENDIENTE = "[PENDIENTE]"
H34, H35, H36, H37, H38, H39, H40, H41, H42, H43 = (
    "34_Factores_Riesgo", "35_Entendimiento", "36_Stand_back", "37_Analiticos", "38_Estimaciones", "39_Leyes",
    "40_Partes_Relacionadas", "41_Empresa_Marcha", "42_Cambios", "43_Equipo_Horas")
VERSION_ANT = "00_Version_anterior"
CEDULAS = [
    (H34, "Factores de riesgo inherente y riesgos que exigen probar controles (NIA 315 Revisada 2019)"),
    (H35, "Entendimiento de la entidad y su entorno, con indagaciones y observaciones (NIA 315 Revisada 2019)"),
    (H36, "Stand-back: cuentas materiales sin riesgo identificado y revelaciones significativas (NIA 315 y 330)"),
    (H37, "Procedimientos analíticos sustantivos: expectativa, diferencia y umbral (NIA 520)"),
    (H38, "Estimaciones contables: incertidumbre y revisión retrospectiva (NIA 540)"),
    (H39, "Leyes y reglamentos con efecto directo e indirecto (NIA 250)"),
    (H40, "Partes relacionadas y transacciones fuera del curso normal (NIA 550)"),
    (H41, "Empresa en marcha: indicios financieros y no financieros y período de la evaluación (NIA 570)"),
    (H42, "Cambios frente a la versión anterior de la planificación: materialidad y riesgos (NIA 300 y 320)"),
    (H43, "Equipo, presupuesto de horas, supervisión y cierre del archivo (NIA 220, 230 y 300)"),
]


def _st(t) -> str:
    t = unicodedata.normalize("NFD", str(t or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def _hay(texto, claves) -> bool:
    n = _st(texto)
    return any(k in n for k in claves)


def q(t) -> str:
    """Texto dentro de una fórmula: las comillas se duplican."""
    return str(t or "").replace('"', '""')


def ref(h: str) -> str:
    return f"'{h}'!"


def rng(h: str, col: str, n: int) -> str:
    return f"'{h}'!${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


# --- parámetros (política de la firma; se agregan a la hoja 02) ------------------------------------------------------
PARAMETROS = {"pctUmbralAnalitico": 50, "horasAlto": 16, "horasMedio": 8, "horasBajo": 3, "horasEncargo": 4,
              "pctHorasSocio": 10, "pctHorasGerente": 20, "pctHorasSenior": 40, "pctHorasAsistente": 30, "diasCierreArchivo": 60}
ETIQUETAS = {
    "pctUmbralAnalitico": "Analíticos sustantivos: umbral como % de la materialidad de desempeño (política de la firma)",
    "horasAlto": "Horas presupuestadas por procedimiento de nivel alto o significativo (política de la firma)",
    "horasMedio": "Horas presupuestadas por procedimiento de nivel medio (política de la firma)",
    "horasBajo": "Horas presupuestadas por procedimiento de nivel bajo (política de la firma)",
    "horasEncargo": "Horas presupuestadas por procedimiento de todo encargo (política de la firma)",
    "pctHorasSocio": "Presupuesto: % de las horas del socio",
    "pctHorasGerente": "Presupuesto: % de las horas del gerente",
    "pctHorasSenior": "Presupuesto: % de las horas del senior",
    "pctHorasAsistente": "Presupuesto: % de las horas de los asistentes",
    "diasCierreArchivo": "Días desde la fecha del informe para cerrar el archivo (NIA 230 párr. A21 — VERIFICAR)",
}
SUSTENTO = {"pctUmbralAnalitico": "NIA 520 párr. 5 c) y A16 — política de la firma (VERIFICAR)",
            **{k: "Política de la firma (NIA 300 párr. 8 e) y NIA 220)" for k in PARAMETROS if k.startswith(("horas", "pctHoras"))},
            "diasCierreArchivo": "NIA 230 párr. 14 y A21 (VERIFICAR)"}
ROLES_HORAS = (("Socio", "pctHorasSocio", "Estrategia, riesgos significativos, revisión y conclusión"),
               ("Gerente", "pctHorasGerente", "Supervisión y revisión de todas las cédulas"),
               ("Senior", "pctHorasSenior", "Ejecución de las áreas de riesgo alto y medio"),
               ("Asistente", "pctHorasAsistente", "Ejecución de los procedimientos de riesgo bajo y de todo encargo"))


def parametros(p: dict) -> dict:
    out = {}
    for k, v0 in PARAMETROS.items():
        v = a_num(p.get(k))
        v = v0 if v is None else float(v)
        tope = 3650 if k == "diasCierreArchivo" else 1000 if k.startswith("horas") else 100
        if not 0 <= v <= tope:
            raise ValueError(f"{ETIQUETAS[k]}: use un valor de 0 a {tope}.")
        out[k] = float(v)
    if abs(sum(out[k] for _r, k, _d in ROLES_HORAS) - 100) > 0.01:
        raise ValueError("Presupuesto de horas: los porcentajes del socio, gerente, senior y asistentes deben sumar 100.")
    return out


# --- M5 · factores de riesgo inherente (hoja 34) --------------------------------------------------------------------
FACTORES = ("Complejidad", "Subjetividad", "Cambio", "Incertidumbre", "Sesgo o fraude")
_CLAVES_FACTOR = {
    "Complejidad": ("instrument", "derivad", "consolid", "combinacion", "arrendamiento", "contrato", "valor razonable",
                    "impuesto diferido", "produccion", "costeo"),
    "Subjetividad": ("estimac", "deterior", "provisi", "valor neto realizable", "obsolesc", "incobrab", "jubilac", "desahucio",
                     "valor razonable", "vida util", "calificacion"),
    "Cambio": ("variacion", "nueva", "cambio", "aumentaron", "rotacion", "baja", "persiste"),
    "Incertidumbre": ("empresa en marcha", "litigio", "contingen", "deterior", "incobrab", "continuidad", "liquidez",
                      "patrimonio", "funcionamiento"),
    "Sesgo o fraude": ("fraude", "elusion", "sesg", "manipul", "incentiv", "presion", "racionaliz"),
}
_NORMA_FACTOR = {"NIA 240": "Sesgo o fraude", "NIA 570": "Incertidumbre", "NIA 540": "Subjetividad"}
_AUTOMATIZADO = ("sistema", "automat", "electronic", "erp", "interfaz", "volumen", "facturacion", "acceso", "usuario")
NO_BASTAN = "No: probar los controles del proceso automatizado (NIA 315 párr. 33; NIA 330 párr. 8 b))"
SI_BASTAN = "Sí"
COLS_FACTORES = ([["Origen", "t"], ["Código", "t"], ["Riesgo", "t"], ["Nivel", "t"], ["¿Se presenta?", "t"]]
                 + [[f, "t"] for f in FACTORES] + [["Factores presentes", "i"],
                                                   ["¿Bastan los procedimientos sustantivos?", "t"]])


def factores(texto: str, norma: str = "") -> dict:
    out = {f: "Sí" if _hay(texto, cl) else "No" for f, cl in _CLAVES_FACTOR.items()}
    for n_, f in _NORMA_FACTOR.items():
        if n_ in str(norma):
            out[f] = "Sí"
    return out


def bastan(texto: str, ti: str = "") -> str:
    return NO_BASTAN if ti or _hay(texto, _AUTOMATIZADO) else SI_BASTAN


def filas_factores(carta: list, riesgos: list, R12: str, R13: str) -> list:
    filas = []

    def cierre(r, fa, b):
        k = sum(1 for f in FACTORES if fa[f] == "Sí")
        return [fa[f] for f in FACTORES] + [fx(f'COUNTIF(F{r}:J{r},"Sí")', k), b]
    for i, x in enumerate(carta):
        r, r12 = FILA0 + len(filas), FILA0 + i
        texto = f"{x['proceso']} {x['hallazgo']}"
        nv = "Significativo" if x["sig"] == "Sí" else x["nivel"]
        filas.append(["Carta de control interno (hoja 12)", x["id"], fx(f"{R12}C{r12}", x["hallazgo"]),
                      fx(f'IF({R12}M{r12}="Sí","Significativo",{R12}J{r12})', nv), "Sí",
                      *cierre(r, factores(texto), bastan(texto, x.get("ti", "")))])
    for j, x in enumerate(riesgos):
        r, r13 = FILA0 + len(filas), FILA0 + j
        texto = f"{x['rubro']} {x['cond']} {x['riesgo']}"
        if x["cod"] in ("presuncion", "elusion"):
            texto += " fraude"
        filas.append(["Posibles riesgos (hoja 13)", x["codigo"], fx(f"{R13}G{r13}", x["riesgo"]), fx(f"{R13}H{r13}", x["sev"]),
                      fx(f"{R13}F{r13}", x["presenta"]), *cierre(r, factores(texto, x["norma"]), bastan(texto))])
    return filas


def controles_necesarios(carta: list) -> list:
    """Hallazgos de la carta cuyo proceso es automatizado y que el auditor no marcó para probar su control."""
    return [x for x in carta if bastan(f"{x['proceso']} {x['hallazgo']}", x.get("ti", "")) == NO_BASTAN and x["probar"] != "Sí"]


# --- M7 · entendimiento estructurado (hoja 35) ----------------------------------------------------------------------
ASPECTOS = ("Sector, actividad y regulación", "Propiedad, gobierno y estructura", "Estrategia, objetivos y modelo de negocio",
            "Medición y revisión del desempeño", "Políticas contables y sus cambios", "Financiamiento",
            "Sistema de información y control interno")
TEMAS = (*ASPECTOS, "Partes relacionadas", "Leyes y reglamentos", "Empresa en marcha", "Otro")
PROCEDIMIENTOS = ("Indagación", "Observación", "Inspección")
COLS_ENTENDIMIENTO = [["Aspecto", "t"], ["Fuente automática", "t"], ["Dato de los documentos", "t"],
                      ["Indagación u observación (plataforma)", "t"], ["Estado", "t"]]
DOCUMENTADO, PENDIENTE_EST = "Documentado", "Pendiente"


def _f_indag(filas_reg: list, tema: str, R_: str) -> tuple[str, str]:
    """Las indagaciones registradas sobre el tema, unidas: (fórmula, valor)."""
    sel = [(r, x) for r, x in filas_reg if x["tema"] == tema]
    if not sel:
        return '""', ""
    f_ = '&"; "&'.join(f'{R_}C{r}&": "&{R_}H{r}&" ("&{R_}E{r}&")"' for r, _x in sel)
    v_ = "; ".join(f"{x['procedimiento']}: {x['resumen']} ({x['persona']})" for _r, x in sel)
    return f_, v_


def filas_entendimiento(c: dict) -> list:
    """``c``: ficha, informe, notas, carta, marco, edicion, indag (fila, registro), refs y valores."""
    E9, F9, I10, F10, R12, N15, R_, par = c["E9"], c["F9"], c["I10"], c["F10"], c["R12"], c["N15"], c["R_"], c["par"]
    fi = c["ficha"]
    act = str(fi.get("activity") or "").strip()
    act_inf = next((x["detalle"] for x in c["informe"] if _hay(x["concepto"], ("actividad", "objeto social"))), "")
    sector = act or act_inf
    prop = [x for x in c["informe"] if _hay(x["concepto"] + " " + x["detalle"], ("accionist", "propiedad", "gobierno", "directorio"))]
    ent = [x for x in c["informe"] if x["tipo"] == "Entendimiento"]
    cap = c["capital"]
    datos = [
        ("Ficha del encargo y actividad del informe anterior", sector or f"{PENDIENTE} actividad en la ficha del encargo", None),
        ("Capital del balance e informe anterior",
         (f"Capital y aportes al corte: US$ {cap['txt']}" + ("; " + "; ".join(x["detalle"] or x["concepto"] for x in prop)
                                                             if prop else "")) if cap["refs"] or prop else
         f"{PENDIENTE} accionistas y gobierno corporativo",
         (f'"Capital y aportes al corte: US$ "&FIXED({"+".join(cap["refs"])},2)'
          + (f'&"; {q("; ".join(x["detalle"] or x["concepto"] for x in prop))}"' if prop else "")) if cap["refs"] else None),
        ("Entendimiento del informe anterior (hoja 14)",
         f"{len(ent)} asuntos del entendimiento de la entidad (hoja 14)" if ent else f"{PENDIENTE} estrategia y modelo de negocio", None),
        ("Índices financieros (hojas 09 y 10)", c["desempeno_v"],
         f'"Margen neto: "&IF(ISNUMBER({I10}E{F10["margenNeto"]}),FIXED({I10}E{F10["margenNeto"]},2)&" %","sin dato")&"; ROE: "&'
         f'IF(ISNUMBER({I10}E{F10["roe"]}),FIXED({I10}E{F10["roe"]},2)&" %","sin dato")&"; variación de las ventas: "&'
         f'IF(ISNUMBER({E9}F{F9["Ventas netas"]}),FIXED({E9}F{F9["Ventas netas"]}*100,1)&" %","sin dato")'),
        ("Ficha del encargo, notas e informe del año anterior", c["politicas_v"],
         f'"Marco: "&{par("marco")}&" (edición: "&{par("edicionMarco")}&"); notas del año anterior: "&COUNTA({N15}$A${FILA0}:$A$'
         f'{FILA0 + max(len(c["notas"]), 1) - 1})&"; "&"{c["cambios_v"]}"'),
        ("Estados resumidos e índices (hojas 09 y 10)", c["financ_v"],
         f'"Endeudamiento del activo: "&IF(ISNUMBER({I10}E{F10["endTotal"]}),FIXED({I10}E{F10["endTotal"]},2)&" %","sin dato")&'
         f'"; obligaciones financieras: US$ "&FIXED({E9}D{F9["Obligaciones financieras"]},2)'),
        ("Carta de control interno (hojas 12 y 27)",
         f"{len(c['carta'])} hallazgos de control interno y TI (hojas 12 y 27)" if c["carta"] else
         f"{PENDIENTE} carta de control interno (RQ-004)",
         f'COUNTA({R12}$A${FILA0}:$A${FILA0 + len(c["carta"]) - 1})&" hallazgos de control interno y TI (hojas 12 y 27)"'
         if c["carta"] else None),
    ]
    filas = []
    for asp, (fuente, v, f_) in zip(ASPECTOS, datos):
        r = FILA0 + len(filas)
        fi_, vi_ = _f_indag(c["indag"], asp, R_)
        est = PENDIENTE_EST if v.startswith(PENDIENTE) and not vi_ else DOCUMENTADO
        filas.append([asp, fuente, fx(f_, v) if f_ else v, fx(fi_, vi_) if vi_ else "",
                      fx(f'IF(AND(LEFT(C{r},{len(PENDIENTE)})="{PENDIENTE}",D{r}=""),"{PENDIENTE_EST}","{DOCUMENTADO}")', est)])
    for tema in TEMAS[len(ASPECTOS):]:
        fi_, vi_ = _f_indag(c["indag"], tema, R_)
        if vi_:
            filas.append([tema, "Plataforma (hoja 00_Registros)", "", fx(fi_, vi_), DOCUMENTADO])
    return filas


# --- M8 · stand-back y revelaciones significativas (hoja 36) --------------------------------------------------------
COLS_STAND = [["Tipo", "t"], ["Código o nota", "t"], ["Cuenta o revelación", "t"], ["Importe", "n"], ["¿Material?", "t"],
              ["Riesgos identificados", "t"], ["Conclusión", "t"]]
SB_NO_MAT = "No material: sin procedimiento adicional"
SB_CON = "Con riesgo identificado: respuesta en el programa (hoja 19)"
SB_SIN = ("Material sin riesgo identificado: procedimientos sustantivos igual (NIA 330 párr. 18); confirmar que no hay "
          "riesgo (NIA 315 párr. 36 — VERIFICAR)")
SB_REV = "Revelación significativa: verificar integridad, exactitud y presentación (NIA 315 párr. 36 — VERIFICAR)"
SB_REV_NO = "No significativa"


def filas_stand_back(rev: list, notas: list, c: dict) -> list:
    C18, N15, GLOBAL, DESEMP = c["C18"], c["N15"], c["GLOBAL"], c["DESEMP"]
    mat = c["mat"]
    filas = []
    for i, x in enumerate(rev):
        r, r18 = FILA0 + len(filas), FILA0 + i
        mt_ = "Sí" if x["x"]["material"] == "Sí" or x["x"]["varMaterial"] == "Sí" else "No"
        rs = " ".join(v for v in (x["riesgo"], x["rb"]) if v)
        concl = SB_NO_MAT if mt_ == "No" else SB_CON if rs else SB_SIN
        filas.append(["Cuenta", x["x"]["codigo"], x["x"]["cuenta"], fx(f"{C18}D{r18}", n2(x["x"]["act"])),
                      fx(f'IF(OR({C18}F{r18}="Sí",{C18}G{r18}="Sí"),"Sí","No")', mt_),
                      fx(f'TRIM({C18}H{r18}&" "&{C18}I{r18})', rs),
                      fx(f'IF(E{r}="No","{SB_NO_MAT}",IF(F{r}<>"","{SB_CON}","{SB_SIN}"))', concl)])
    for j, n in enumerate(notas):
        r, r15 = FILA0 + len(filas), FILA0 + j
        sig = "Pendiente" if mat is None else "Sí" if abs(n["act"]) >= mat else "No"
        filas.append(["Revelación", f"Nota {n['nota']}", n["titulo"], fx(f"{N15}G{r15}", n2(n["act"])),
                      fx(f'IF({DESEMP}="","Pendiente",IF(ABS(D{r})>={GLOBAL},"Sí","No"))', sig), "",
                      fx(f'IF(E{r}="Sí","{SB_REV}","{SB_REV_NO}")', SB_REV if sig == "Sí" else SB_REV_NO)])
    return filas


# --- M11 · analíticos sustantivos (hoja 37) --------------------------------------------------------------------------
COLS_ANALITICOS = [["Código", "t"], ["Cuenta", "t"], ["Sección", "t"], ["Anterior", "n"], ["Actual", "n"],
                   ["Método de la expectativa", "t"], ["Expectativa", "n"], ["Diferencia", "n"], ["Umbral", "n"], ["Resultado", "t"]]
MET_COSTO = "Anterior × ventas actuales ÷ ventas anteriores (margen constante)"
MET_FIJO = "Anterior (gasto de comportamiento fijo)"
MET_INGRESO = "Anterior (tendencia del año anterior)"
AN_PEND = "Pendiente: sin materialidad (NIA 320)"
AN_INV = "Investigar: explicación de la dirección y su corroboración (NIA 520 párr. 7)"
AN_OK = "Conforme con la expectativa"


def analiticos(cuentas: list, ventas: tuple, desemp, pct: float) -> list:
    out = []
    va, vc = ventas
    for x in cuentas:
        met = MET_COSTO if x["sec"] == "Costos" else MET_INGRESO if x["sec"] == "Ingresos" else MET_FIJO
        esp = x["ant"] * vc / va if met == MET_COSTO and va else x["ant"]
        dif = x["act"] - esp
        umb = None if desemp is None else desemp * pct / 100
        res = AN_PEND if umb is None else AN_INV if abs(dif) > umb else AN_OK
        out.append({"x": x, "met": met, "esp": esp, "dif": dif, "umb": umb, "res": res})
    return out


def filas_analiticos(items: list, c: dict) -> list:
    H8, E9, F9, DESEMP, par, fila8 = c["H8"], c["E9"], c["F9"], c["DESEMP"], c["par"], c["fila8"]
    va, vc = f"{E9}C{F9['Ventas netas']}", f"{E9}D{F9['Ventas netas']}"
    filas = []
    for y in items:
        x, r = y["x"], FILA0 + len(filas)
        r8 = fila8[x["codigo"]]
        f_esp = f"IF(N({va})=0,D{r},D{r}*{vc}/{va})" if y["met"] == MET_COSTO else f"D{r}"
        filas.append([x["codigo"], x["cuenta"], fx(f"{H8}F{r8}", x["sec"]), fx(f"{H8}G{r8}", n2(x["ant"])),
                      fx(f"{H8}H{r8}", n2(x["act"])), y["met"], fx(f_esp, y["esp"]), fx(f"E{r}-G{r}", y["dif"]),
                      fx(f'IF({DESEMP}="","",{DESEMP}*{par("pctUmbralAnalitico")}/100)', "" if y["umb"] is None else y["umb"]),
                      fx(f'IF(I{r}="","{AN_PEND}",IF(ABS(H{r})>I{r},"{AN_INV}","{AN_OK}"))', y["res"])])
    return filas


# --- M12 · estimaciones (hoja 38) ------------------------------------------------------------------------------------
_TIPOS_ESTIMACION = [
    (("jubilac", "desahucio"), "Jubilación patronal y desahucio (cálculo actuarial)", "Alta"),
    (("impuesto diferido", "impuestos diferidos"), "Impuesto diferido", "Alta"),
    (("incobrab", "credito esperad", "deterioro de cartera", "deterioro de cuentas"), "Deterioro de cuentas por cobrar", "Alta"),
    (("valor neto realizable", "obsolesc", "deterioro de inventario", "lento movimiento"), "Valor neto realizable de inventarios", "Alta"),
    (("deterior",), "Deterioro de activos", "Alta"),
    (("deprec",), "Depreciación (vidas útiles y valor residual)", "Media"),
    (("amortiz",), "Amortización (vidas útiles)", "Media"),
    (("garantia",), "Garantías", "Media"),
    (("provisi",), "Provisiones", "Media"),
]
COLS_ESTIMACIONES = [["Código", "t"], ["Cuenta", "t"], ["Estimación", "t"], ["Subjetividad", "t"], ["Anterior", "n"],
                     ["Actual", "n"], ["Variación", "n"], ["Incertidumbre", "t"], ["Revisión retrospectiva", "t"]]
SIN_ESTIMACIONES = "Sin estimaciones identificadas por el nombre de las cuentas del balance"


def estimaciones(cuentas: list, desemp) -> list:
    out = []
    for x in cuentas:
        if x["detalle"] != "Sí" or x["sec"] not in ("Activo", "Pasivo"):
            continue
        t = next(((tipo, subj) for claves, tipo, subj in _TIPOS_ESTIMACION if _hay(x["cuenta"], claves)), None)
        if not t:
            continue
        a = abs(x["act"])
        inc = ("Pendiente" if desemp is None else "Alta" if t[1] == "Alta" and a >= desemp else "Media" if a >= desemp else "Baja")
        out.append({"x": x, "tipo": t[0], "subj": t[1], "inc": inc})
    return out


def filas_estimaciones(items: list, c: dict) -> list:
    H8, DESEMP, fila8 = c["H8"], c["DESEMP"], c["fila8"]
    filas = []
    for y in items:
        x, r = y["x"], FILA0 + len(filas)
        r8 = fila8[x["codigo"]]
        filas.append([x["codigo"], x["cuenta"], y["tipo"], y["subj"], fx(f"{H8}G{r8}", n2(x["ant"])), fx(f"{H8}H{r8}", n2(x["act"])),
                      fx(f"F{r}-E{r}", n2(x["act"] - x["ant"])),
                      fx(f'IF({DESEMP}="","Pendiente",IF(AND(D{r}="Alta",ABS(F{r})>={DESEMP}),"Alta",'
                         f'IF(ABS(F{r})>={DESEMP},"Media","Baja")))', y["inc"]),
                      fx(f'"Comparar la estimación del cierre anterior (US$ "&FIXED(ABS(E{r}),2)&") con su desenlace real en el '
                         f'período (NIA 540 párr. 14)"',
                         f"Comparar la estimación del cierre anterior (US$ {_m(abs(x['ant']))}) con su desenlace real en el "
                         "período (NIA 540 párr. 14)")])
    if not filas:
        filas.append(["", SIN_ESTIMACIONES, "", "", None, None, None, "", ""])
    return filas


def _m(v: float) -> str:
    """Como FIXED(v,2): separador de miles «,» y decimal «.» (el verificador intercambia los del equipo)."""
    return f"{v:,.2f}"


# --- M13 · leyes y reglamentos (hoja 39) ----------------------------------------------------------------------------
COLS_LEYES = [["Ley o regulador", "t"], ["Efecto en los estados financieros", "t"], ["Cuentas relacionadas", "t"],
              ["Saldo al corte", "n"], ["¿Aplica?", "t"], ["Procedimiento", "t"], ["Norma", "t"], ["Estado", "t"]]
_AMBIENTAL = ("manufactur", "industri", "miner", "petrol", "agric", "agro", "pesca", "quimic", "construc", "camaron", "palma",
              "flor", "energ", "hidrocarb")
_UAFE = ("inmobiliari", "vehicul", "automotor", "joy", "metales precios", "construc", "seguro", "cooperativ", "notar",
         "casino", "juego", "transporte de valores", "remesa", "courier", "arte", "antiguedad")
LEYES = [
    ("SRI · impuesto a la renta, IVA y retenciones", "Directo", ("impuest", "iva", "retencion", "renta"),
     "Conciliar las declaraciones (formularios 101, 103 y 104) con los registros y revisar la conciliación tributaria.",
     "NIA 250 párr. 13 (VERIFICAR)", None),
    ("Superintendencia de Compañías · presentación de estados, reserva legal y juntas", "Directo", ("reserva legal", "capital"),
     "Verificar la reserva legal, las actas de junta y el cumplimiento de la presentación de los estados financieros.",
     "NIA 250 párr. 13 (VERIFICAR)", None),
    ("IESS · aportes y fondos de reserva", "Directo", ("iess", "aporte", "fondo de reserva", "seguridad social"),
     "Cruzar las planillas del IESS con la nómina y los pagos posteriores al corte.", "NIA 250 párr. 13 (VERIFICAR)", None),
    ("Código del Trabajo · décimos, vacaciones, participación de trabajadores, jubilación y desahucio", "Directo",
     ("decimo", "participacion", "trabajador", "vacacion", "jubilac", "desahucio", "utilidades"),
     "Recalcular los beneficios de ley y el 15 % de participación de los trabajadores.", "NIA 250 párr. 13 (VERIFICAR)", None),
    ("Normativa ambiental (licencias y remediación)", "Indirecto", (), "Indagar sobre licencias, sanciones y obligaciones de "
     "remediación; revisar las provisiones.", "NIA 250 párr. 14 (VERIFICAR)", _AMBIENTAL),
    ("UAFE · prevención de lavado de activos", "Indirecto", (), "Verificar si la entidad es sujeto obligado y si presentó sus "
     "reportes a la UAFE (VERIFICAR).", "NIA 250 párr. 14 (VERIFICAR)", _UAFE),
    ("Otras leyes del sector", "Indirecto", (), "Indagar a la dirección sobre el cumplimiento de las leyes de su sector e "
     "inspeccionar la correspondencia con los reguladores.", "NIA 250 párr. 14 (VERIFICAR)", ()),
]
LEY_TEMA = "Leyes y reglamentos"


def filas_leyes(cuentas: list, actividad: str, c: dict) -> list:
    H8, fila8, n_reg, R_ = c["H8"], c["fila8"], c["n_reg"], c["R_"]
    indag = sum(1 for _r, x in c["indag"] if x["tema"] == LEY_TEMA)
    f_ind = (f'COUNTIFS({R_}$A${FILA0}:$A${FILA0 + max(n_reg, 1) - 1},"Indagación*",{R_}$F${FILA0}:$F$'
             f'{FILA0 + max(n_reg, 1) - 1},"{LEY_TEMA}")')
    filas = []
    for nombre, efecto, claves, proc, norma, sector in LEYES:
        r = FILA0 + len(filas)
        ctas = [x for x in cuentas if claves and x["detalle"] == "Sí" and x["sec"] in ("Activo", "Pasivo", "Patrimonio", "Gastos")
                and _hay(x["cuenta"], claves)]
        saldo = sum(x["act"] for x in ctas)
        f_s = "+".join(f"{H8}H{fila8[x['codigo']]}" for x in ctas) or "0"
        if efecto == "Directo":
            aplica = "Sí"
            est = fx(f'IF(E{r}="Sí","Procedimiento en el programa (hoja 19)","No aplica")', "Procedimiento en el programa (hoja 19)")
        else:
            aplica = ("Sí" if sector and _hay(actividad, sector) else "Evaluar: indagar a la dirección")
            v = "Documentado" if indag else f"{PENDIENTE} indagar a la dirección (NIA 250 párr. 14)"
            est = fx(f'IF({f_ind}>0,"Documentado","{PENDIENTE} indagar a la dirección (NIA 250 párr. 14)")', v)
        filas.append([nombre, efecto, ", ".join(x["codigo"] for x in ctas), fx(f_s, n2(saldo)) if ctas else None, aplica, proc,
                      norma, est])
    return filas


# --- M14 · partes relacionadas (hoja 40) ----------------------------------------------------------------------------
_PARTES = ("relacionad", "accionist", "vinculad", "directores", "dividendos por pagar", "compania relacionada")
COLS_PARTES = [["Código", "t"], ["Cuenta o nota", "t"], ["Anterior", "n"], ["Actual", "n"], ["Variación", "n"], ["Marca", "t"],
               ["¿Fuera del curso normal?", "t"], ["Tratamiento", "t"]]
PR_FUERA = "Sí: transacción fuera del curso normal (NIA 550 párr. 23 — VERIFICAR)"
PR_SIG = "Riesgo significativo (NIA 550 párr. 18 — VERIFICAR)"
PR_PROG = "Procedimientos del programa (hoja 19)"
PR_TEMA = "Partes relacionadas"


def partes(cuentas: list, desemp) -> list:
    out = []
    for x in cuentas:
        if x["detalle"] != "Sí" or not _hay(x["cuenta"], _PARTES):
            continue
        var = x["act"] - x["ant"]
        marca = ("Pendiente" if desemp is None else "Nueva" if x["ant"] == 0 and x["act"] != 0 else "Variación material"
                 if abs(var) >= desemp else "Saldo material" if abs(x["act"]) >= desemp else "Normal")
        out.append({"x": x, "var": var, "marca": marca, "fuera": marca in ("Nueva", "Variación material")})
    return out


def partes_textos(informe: list, notas: list) -> list:
    """Menciones de partes relacionadas en el informe y las notas del año anterior: (referencia, texto)."""
    out = [(f"Nota {n['nota']}", n["titulo"]) for n in notas if _hay(n["titulo"], _PARTES)]
    out += [(f"Informe anterior · {x['concepto']}", x["detalle"] or x["concepto"]) for x in informe
            if _hay(x["concepto"] + " " + x["detalle"], _PARTES)]
    return out


def filas_partes(items: list, textos: list, c: dict) -> list:
    H8, DESEMP, fila8, n_reg, R_ = c["H8"], c["DESEMP"], c["fila8"], c["n_reg"], c["R_"]
    filas = []
    for y in items:
        x, r = y["x"], FILA0 + len(filas)
        r8 = fila8[x["codigo"]]
        filas.append([x["codigo"], x["cuenta"], fx(f"{H8}G{r8}", n2(x["ant"])), fx(f"{H8}H{r8}", n2(x["act"])),
                      fx(f"D{r}-C{r}", n2(y["var"])),
                      fx(f'IF({DESEMP}="","Pendiente",IF(AND(C{r}=0,D{r}<>0),"Nueva",IF(ABS(E{r})>={DESEMP},"Variación material",'
                         f'IF(ABS(D{r})>={DESEMP},"Saldo material","Normal"))))', y["marca"]),
                      fx(f'IF(OR(F{r}="Nueva",F{r}="Variación material"),"{PR_FUERA}","No")', PR_FUERA if y["fuera"] else "No"),
                      fx(f'IF(LEFT(G{r},2)="Sí","{PR_SIG}","{PR_PROG}")', PR_SIG if y["fuera"] else PR_PROG)])
    for ref_, texto in textos:
        filas.append([ref_, texto, None, None, None, "Documento del año anterior", "No",
                      "Identificar la parte y sus transacciones del período y evaluar su revelación (NIA 550 párr. 13 y 25 — VERIFICAR)"])
    n_ind = sum(1 for _r, x in c["indag"] if x["tema"] == PR_TEMA)
    f_ind = (f'COUNTIFS({R_}$A${FILA0}:$A${FILA0 + max(n_reg, 1) - 1},"Indagación*",{R_}$F${FILA0}:$F$'
             f'{FILA0 + max(n_reg, 1) - 1},"{PR_TEMA}")')
    pend = f"{PENDIENTE} indagar a la dirección sobre sus partes relacionadas (NIA 550 párr. 13 — VERIFICAR)"
    filas.append(["", "Indagación a la dirección (plataforma)", None, None, None, "", "No",
                  fx(f'IF({f_ind}>0,"Documentada (hoja 35)","{pend}")', "Documentada (hoja 35)" if n_ind else pend)])
    return filas


# --- M15 · empresa en marcha (hoja 41) -------------------------------------------------------------------------------
_EM_NOFIN = ("litigio", "demanda", "juicio", "huelga", "renuncia", "perdida de un cliente", "cliente principal", "proveedor clave",
             "licencia", "permiso de funcionamiento", "sancion", "multa", "embargo", "concurso", "liquidacion", "disolucion",
             "cese", "clausura", "insolven")
COLS_EM = [["Tipo", "t"], ["Fuente", "t"], ["Descripción", "t"], ["¿Es indicio?", "t"], ["Fecha", "d"], ["Estado", "t"]]
EM_TEMA = "Empresa en marcha"
EM_RUBRO = "Empresa en marcha (hoja 41)"


def em_no_financieros(carta: list, informe: list, notas: list) -> list:
    out = []
    for x in carta:
        if _hay(x["proceso"] + " " + x["hallazgo"], _EM_NOFIN):
            out.append((f"Carta de control interno · {x['id']}", x["hallazgo"]))
    for x in informe:
        if _hay(x["concepto"] + " " + x["detalle"], _EM_NOFIN):
            out.append((f"Informe anterior · {x['concepto']}", x["detalle"] or x["concepto"]))
    for n in notas:
        if _hay(n["titulo"], _EM_NOFIN):
            out.append((f"Nota {n['nota']}", n["titulo"]))
    return out


def filas_empresa_marcha(nofin: list, n570: int, c: dict) -> tuple[list, int]:
    R13, n13, par, corte, n_reg, R_ = c["R13"], c["n13"], c["par"], c["corte"], c["n_reg"], c["R_"]
    f570 = (f'COUNTIFS({R13}$I${FILA0}:$I${FILA0 + n13 - 1},"NIA 570",{R13}$F${FILA0}:$F${FILA0 + n13 - 1},"Sí",'
            f'{R13}$C${FILA0}:$C${FILA0 + n13 - 1},"<>{EM_RUBRO}")')
    filas = [["Indicios financieros", "Posibles riesgos (hoja 13)", fx(f'{f570}&" indicios financieros presentes (NIA 570)"',
                                                                    f"{n570} indicios financieros presentes (NIA 570)"),
              fx(f'IF({f570}>0,"Sí","No")', "Sí" if n570 else "No"), None, ""]]
    for fuente, texto in nofin:
        filas.append(["Indicio no financiero", fuente, texto, "Sí", None, ""])
    if not nofin:
        filas.append(["Indicio no financiero", "Carta, informe y notas del año anterior",
                      "Sin menciones de litigios, pérdida de clientes o proveedores clave, sanciones, licencias o cese", "No", None, ""])
    r_ult = FILA0 + len(filas) - 1
    y, m_, d_ = (int(v) for v in corte.split("-"))
    hasta = f"{y + 1:04d}-{m_:02d}-{min(d_, 28) if m_ == 2 else d_:02d}"
    filas.append(["Período de la evaluación", "Fecha de corte (hoja 02)", "La evaluación de la dirección debe cubrir al menos doce "
                  "meses desde la fecha de los estados financieros (NIA 570 párr. 13 — VERIFICAR)", "", fx(f"EDATE({par('corte')},12)", hasta),
                  ""])
    hay = n570 > 0 or bool(nofin)
    n_ind = sum(1 for _r, x in c["indag"] if x["tema"] == EM_TEMA)
    f_ind = (f'COUNTIFS({R_}$A${FILA0}:$A${FILA0 + max(n_reg, 1) - 1},"Indagación*",{R_}$F${FILA0}:$F$'
             f'{FILA0 + max(n_reg, 1) - 1},"{EM_TEMA}")')
    pend = f"{PENDIENTE} solicitar la evaluación de la dirección y documentarla en la plataforma"
    v = ("No requerida: sin indicios" if not hay else "Documentada (hoja 35)" if n_ind else pend)
    filas.append(["Evaluación de la dirección", "Plataforma (indagación sobre empresa en marcha)", "Planes de la dirección y su "
                  "factibilidad frente a los indicios", "", None,
                  fx(f'IF(COUNTIF(D{FILA0}:D{r_ult},"Sí")=0,"No requerida: sin indicios",IF({f_ind}>0,"Documentada (hoja 35)",'
                     f'"{pend}"))', v)])
    return filas, len(nofin)


# --- M19 · uniformidad de las políticas contables ------------------------------------------------------------------
_CAMBIO_POL = ("cambio de politica", "cambio en la politica", "cambios en politicas", "cambios en las politicas", "reexpres",
               "cambio contable", "primera aplicacion", "adopcion por primera")


def uniformidad(informe: list, notas: list, marco: str) -> dict:
    marco_ant = next((x["detalle"] for x in informe if _hay(x["concepto"], ("marco",))), "")
    cambio_marco = bool(marco_ant) and (("pymes" in _st(marco_ant)) != ("PYMES" in marco))
    cambios = any(_hay(x["concepto"] + " " + x["detalle"], _CAMBIO_POL) for x in informe) or any(
        _hay(n["titulo"], _CAMBIO_POL) for n in notas)
    cond = ("Cambio de marco contable respecto del informe del año anterior" if cambio_marco else
            "Cambio de políticas contables mencionado en el informe o las notas del año anterior" if cambios else
            "Sin cambios de marco ni de políticas en los documentos del año anterior")
    return {"presenta": "Sí" if cambio_marco or cambios else "No", "cond": cond,
            "txt": "cambios de marco o de políticas: " + ("sí (hoja 13)" if cambio_marco or cambios else "no detectados")}


# --- M4 · cambios frente a la versión anterior (hojas 00_Version_anterior y 42) --------------------------------------
COLS_VERSION_ANT = [["Concepto", "t"], ["Detalle", "t"], ["Severidad", "t"], ["¿Se presentaba?", "t"], ["Importe", "n"]]
COLS_CAMBIOS = [["Concepto", "t"], ["Versión anterior", "x"], ["Esta versión", "x"], ["Cambio", "t"]]
SIN_CAMBIO = "Sin cambio"
SIN_ANTERIOR = "Primera versión de la planificación: sin comparativo (NIA 300 párr. 10)"
MAT_KEYS = (("materialidad", "Materialidad global"), ("desempeno", "Materialidad de desempeño"),
            ("trivial", "Umbral de errores claramente insignificantes"))


def version_anterior(p: dict) -> dict | None:
    a = p.get("_anterior")
    if not isinstance(a, dict):
        return None
    tot = a.get("totales") or {}
    return {"version": str(a.get("version") or ""), "fecha": str(a.get("fecha") or "")[:10],
            "totales": {k: float(a_num(tot.get(k)) or 0) for k, _e in MAT_KEYS},
            "riesgos": [{"rubro": str(x.get("rubro") or ""), "cond": str(x.get("cond") or ""), "riesgo": str(x.get("riesgo") or ""),
                         "sev": str(x.get("sev") or ""), "presenta": str(x.get("presenta") or "")} for x in a.get("riesgos") or []]}


def _clave(x: dict) -> str:
    return _st(f"{x['rubro']}|{x['cond']}")


def filas_version_anterior(ant: dict | None) -> list:
    if not ant:
        return [["Versión anterior", "No hay: es la primera versión de la planificación", "", "", None]]
    filas = [["Versión anterior", f"v{ant['version']} · {ant['fecha']}", "", "", None]]
    filas += [[etq, "Materialidad (hoja 11 de esa versión)", "", "", n2(ant["totales"][k])] for k, etq in MAT_KEYS]
    filas += [[f"Riesgo · {x['rubro']}", x["cond"], x["sev"], x["presenta"], None] for x in ant["riesgos"]]
    return filas


def filas_cambios(ant: dict | None, riesgos: list, mt: dict, c: dict) -> list:
    R13, M11, F11 = c["R13"], c["M11"], c["F11"]
    if not ant:
        return [[SIN_ANTERIOR, "", "", SIN_CAMBIO]]
    va = ref(VERSION_ANT)
    filas = []
    act = {"materialidad": mt["global"], "desempeno": mt["desempeno"], "trivial": mt["trivial"]}
    for k_, (k, etq) in enumerate(MAT_KEYS):
        r = FILA0 + len(filas)
        a, v = ant["totales"][k], act[k] or 0
        cam = SIN_CAMBIO if abs(a - v) < 0.005 else "Cambió: documentar el motivo (NIA 320 párr. 12)"
        filas.append([etq, fx(f"{va}E{FILA0 + 1 + k_}", n2(a)), fx(f"N({M11}D{F11[etq]})", n2(v)),
                      fx(f'IF(ABS(B{r}-C{r})<0.005,"{SIN_CAMBIO}","Cambió: documentar el motivo (NIA 320 párr. 12)")', cam)])
    previos = {_clave(x): (FILA0 + 4 + i, x) for i, x in enumerate(ant["riesgos"])}
    vistos = set()
    for j, x in enumerate(riesgos):
        k = _clave(x)
        r13, r = FILA0 + j, FILA0 + len(filas)
        if k in previos:
            vistos.add(k)
            rv, y = previos[k]
            antes = f"{y['sev']} · {y['presenta']}"
            ahora = f"{x['sev']} · {x['presenta']}"
            cam = SIN_CAMBIO if antes == ahora else "Cambió la severidad o su presencia: actualizar la respuesta (NIA 315 párr. 37)"
            filas.append([f"{x['codigo']} · {x['rubro']}", fx(f'{va}C{rv}&" · "&{va}D{rv}', antes),
                          fx(f'{R13}H{r13}&" · "&{R13}F{r13}', ahora),
                          fx(f'IF(B{r}=C{r},"{SIN_CAMBIO}","Cambió la severidad o su presencia: actualizar la respuesta (NIA 315 '
                             f'párr. 37)")', cam)])
        elif x["presenta"] == "Sí":
            filas.append([f"{x['codigo']} · {x['rubro']}", "No estaba", fx(f'{R13}H{r13}&" · "&{R13}F{r13}',
                                                                          f"{x['sev']} · {x['presenta']}"),
                          "Nuevo: incorporarlo a la estrategia y al programa (NIA 300 párr. 10)"])
    for k, (rv, y) in previos.items():
        if k not in vistos and y["presenta"] == "Sí":
            filas.append([f"{y['rubro']} · {y['cond']}", fx(f'{va}C{rv}&" · "&{va}D{rv}', f"{y['sev']} · {y['presenta']}"),
                          "Ya no está", "Ya no se identifica: documentar por qué (NIA 315 párr. 37)"])
    return filas


def n_cambios(filas: list) -> int:
    return sum(1 for f in filas if (f[3]["v"] if isinstance(f[3], dict) else f[3]) not in (SIN_CAMBIO,))


# --- M1 y M2 · equipo, horas, supervisión y cierre del archivo (hoja 43) ---------------------------------------------
COLS_HORAS = [["Concepto", "t"], ["Detalle", "t"], ["Porcentaje", "n"], ["Horas", "n"], ["Cantidad", "i"], ["Fecha", "d"],
              ["Estado", "t"]]
SUP_SOCIO = "Revisión del socio"
SUP_GERENTE = "Revisión del gerente"


def horas_nivel(nivel: str, pc: dict, aplica: str) -> float:
    if aplica == "No":
        return 0.0
    if nivel == "Todo encargo":
        return pc["horasEncargo"]
    if nivel in ("Alto", "Significativo") or str(nivel).startswith("Pendiente"):
        return pc["horasAlto"]
    return pc["horasMedio"] if nivel == "Medio" else pc["horasBajo"]


def f_horas(r: int, par) -> str:
    return (f'IF(K{r}="No",0,IF(D{r}="Todo encargo",{par("horasEncargo")},IF(OR(D{r}="Alto",D{r}="Significativo",'
            f'LEFT(D{r},9)="Pendiente"),{par("horasAlto")},IF(D{r}="Medio",{par("horasMedio")},{par("horasBajo")}))))')


def f_supervision(r: int) -> str:
    return f'IF(OR(D{r}="Alto",D{r}="Significativo",LEFT(D{r},9)="Pendiente"),"{SUP_SOCIO}","{SUP_GERENTE}")'


def supervision(nivel: str) -> str:
    return SUP_SOCIO if nivel in ("Alto", "Significativo") or str(nivel).startswith("Pendiente") else SUP_GERENTE


def filas_horas(total: float, n_prog: int, equipo: list, sup: dict, fechas: dict, pc: dict, c: dict) -> list:
    par, P19, H25, n_eq = c["par"], c["P19"], c["H25"], len(equipo)
    f_tot = f"SUM({P19}$M${FILA0}:$M${FILA0 + max(n_prog, 1) - 1})"
    r_tot = FILA0 + len(ROLES_HORAS)
    filas = []
    for rol, k, det in ROLES_HORAS:
        r = FILA0 + len(filas)
        n = sum(1 for x in equipo if x["rol"] == rol)
        h = total * pc[k] / 100
        est = "Revisar: sin integrante registrado con ese rol (hoja 25)" if h > 0 and n == 0 else "Conforme"
        f_n = f'COUNTIF(\'{H25}\'!$B${FILA0}:$B${FILA0 + max(n_eq, 1) - 1},"{rol}")' if n_eq else "0"
        filas.append([f"Horas · {rol}", det, fx(par(k), pc[k]), fx(f"D{r_tot}*C{r}/100", h), fx(f_n, float(n)), None,
                      fx(f'IF(AND(D{r}>0,E{r}=0),"Revisar: sin integrante registrado con ese rol (hoja 25)","Conforme")', est)])
    suma = sum(pc[k] for _r, k, _d in ROLES_HORAS)
    filas.append(["Total presupuestado", "Horas de los procedimientos del programa (hoja 19, columna M)",
                  fx(f"SUM(C{FILA0}:C{r_tot - 1})", suma), fx(f_tot, n2(total)), fx(f"COUNTA({P19}$A${FILA0}:$A${FILA0 + n_prog - 1})",
                                                                                  float(n_prog)), None,
                  fx(f'IF(ABS(C{r_tot}-100)<0.01,"Conforme","Revisar: los porcentajes no suman 100")', "Conforme")])
    for etq, clave in ((SUP_SOCIO, "Riesgos altos, significativos o pendientes de calificación"),
                       (SUP_GERENTE, "Demás procedimientos del programa")):
        f_c = f'COUNTIF({P19}$N${FILA0}:$N${FILA0 + max(n_prog, 1) - 1},"{etq}")'
        filas.append([f"Supervisión planificada · {etq}", clave, None, None, fx(f_c, float(sup.get(etq, 0))), None, "Conforme"])
    fi = fechas.get("fechaInforme")
    r = FILA0 + len(filas)
    cierre = None
    if fi:
        from datetime import date, timedelta
        cierre = (date.fromisoformat(fi) + timedelta(days=int(pc["diasCierreArchivo"]))).isoformat()
    filas.append(["Cierre del archivo (NIA 230 párr. 14)", "Ensamblar el archivo final dentro del plazo desde la fecha del informe; "
                  "después no se borra ni se descarta documentación (NIA 230 párr. 15 — VERIFICAR)", None, None,
                  fx(par("diasCierreArchivo"), pc["diasCierreArchivo"]),
                  fx(f'IF({par("fechaInforme")}="","",{par("fechaInforme")}+E{r})', cierre or ""),
                  fx(f'IF(F{r}="","{PENDIENTE} falta la fecha del informe (hoja 02)","Conforme")',
                     "Conforme" if cierre else f"{PENDIENTE} falta la fecha del informe (hoja 02)")])
    filas.append(["Cambios posteriores al informe (NIA 230 párr. 16)", "Se documentan en una versión nueva de la prueba con su "
                  "motivo, autor y fecha; la plataforma los registra en la bitácora y los marca si son posteriores al informe.",
                  None, None, None, None, "Conforme"])
    return filas


# --- explicaciones («Cómo se calcula») ------------------------------------------------------------------------------
EXPLICA = {
    H34: {"Riesgo": "Trae el texto del riesgo de la hoja 12 (carta de control interno) o de la hoja 13 (posibles riesgos).",
          "Nivel": "Trae el nivel del hallazgo (hoja 12) o la severidad del riesgo (hoja 13).",
          "¿Se presenta?": "Trae de la hoja 13 si el riesgo se presenta; los hallazgos de la carta siempre se presentan.",
          "Factores presentes": "Cuenta cuántos de los cinco factores de riesgo inherente de la fila dicen «Sí»."},
    H35: {"Dato de los documentos": ("Arma el dato con la ficha del encargo, el capital del balance, los índices (hojas 09 y 10), "
                                     "el marco de la hoja 02, las notas (hoja 15) y la carta de control interno (hoja 12)."),
          "Indagación u observación (plataforma)": ("Trae las indagaciones y observaciones registradas con un clic en la plataforma "
                                                    "sobre ese tema (hoja 00_Registros)."),
          "Estado": "«Pendiente» si no hay dato de los documentos ni indagación registrada; si no, «Documentado»."},
    H36: {"Importe": "Trae el saldo al corte de la cuenta (hoja 18) o de la nota del año anterior (hoja 15).",
          "¿Material?": ("En las cuentas, «Sí» si el saldo o la variación son materiales (hoja 18); en las revelaciones, si el saldo "
                         "iguala o supera la materialidad global (hoja 11)."),
          "Riesgos identificados": "Trae los riesgos de la carta y de la hoja 13 vinculados a la cuenta (hoja 18).",
          "Conclusión": ("Una cuenta material sin riesgo identificado igual recibe procedimientos sustantivos; una revelación "
                         "significativa se revisa en su integridad y presentación.")},
    H37: {"Sección": "Trae de la hoja 08 la sección de la cuenta (ingresos, costos o gastos).",
          "Anterior": "Saldo de la cuenta en el período anterior, tomado de la hoja 08.",
          "Actual": "Saldo de la cuenta en el período actual, tomado de la hoja 08.",
          "Expectativa": ("Costos: saldo anterior por las ventas actuales entre las anteriores (hoja 09), como si el margen no "
                          "cambiara; ingresos y gastos: el saldo anterior."),
          "Diferencia": "Saldo actual menos la expectativa: lo que la dirección debe explicar si supera el umbral.",
          "Umbral": "Materialidad de desempeño (hoja 11) por el porcentaje de umbral de los analíticos de la hoja 02.",
          "Resultado": "«Investigar» si la diferencia supera el umbral; «Conforme» si no; «Pendiente» sin materialidad."},
    H38: {"Anterior": "Saldo de la estimación al cierre anterior (hoja 08).",
          "Actual": "Saldo de la estimación a la fecha de corte, tomado de la hoja 08.",
          "Variación": "Saldo al corte menos el saldo al cierre anterior de la estimación.",
          "Incertidumbre": ("«Alta» si la estimación es muy subjetiva (actuarial, deterioro, valor neto realizable, impuesto diferido) y "
                            "su saldo iguala o supera la materialidad de desempeño (hoja 11); «Media» si otra estimación la supera; "
                            "«Baja» si no."),
          "Revisión retrospectiva": "Arma el procedimiento con el saldo del cierre anterior de la estimación."},
    H39: {"Saldo al corte": "Suma el saldo al corte de las cuentas del balance relacionadas con esa ley (hoja 08).",
          "Estado": ("Las leyes de efecto directo tienen su procedimiento en el programa; las de efecto indirecto quedan "
                     "«Documentado» cuando hay una indagación registrada en la plataforma sobre leyes y reglamentos.")},
    H40: {"Anterior": "Saldo al cierre anterior de la cuenta con la parte relacionada (hoja 08).",
          "Actual": "Saldo al corte (hoja 08).", "Variación": "Saldo actual menos el anterior.",
          "Marca": ("«Nueva» si no tenía saldo antes; «Variación material» o «Saldo material» si supera la materialidad de "
                    "desempeño (hoja 11); si no, «Normal»."),
          "¿Fuera del curso normal?": "Una cuenta nueva o con variación material se trata como transacción fuera del curso normal.",
          "Tratamiento": ("Fuera del curso normal: riesgo significativo (pasa a la hoja 13); si no, los procedimientos del programa. "
                          "La última fila mira si hay una indagación registrada en la plataforma.")},
    H41: {"Descripción": "Cuenta los indicios financieros que se presentan en la hoja 13 (norma NIA 570).",
          "¿Es indicio?": "«Sí» si hay indicios financieros en la hoja 13.",
          "Fecha": "Fecha de corte de la hoja 02 más doce meses: hasta dónde debe llegar la evaluación de la dirección.",
          "Estado": ("Sin indicios, no se requiere; con indicios, «Documentada» si hay una indagación sobre empresa en marcha "
                     "registrada en la plataforma y «[PENDIENTE]» si no.")},
    H42: {"Versión anterior": "Trae la cifra o el riesgo de la versión anterior de la planificación (hoja 00_Version_anterior).",
          "Esta versión": "Trae la cifra de la hoja 11 o la severidad y presencia del riesgo en la hoja 13 de esta versión.",
          "Cambio": "Compara ambas versiones: «Sin cambio», «Cambió», «Nuevo» o «Ya no se identifica»."},
    H43: {"Porcentaje": "Trae de la hoja 02 el porcentaje de las horas de cada rol; en el total, los suma.",
          "Horas": "Total de horas del programa (hoja 19) por el porcentaje del rol; el total suma la columna de horas de la hoja 19.",
          "Cantidad": ("Integrantes registrados con ese rol (hoja 25), procedimientos del programa, cédulas por tipo de revisión "
                       "(hoja 19) o los días para cerrar el archivo (hoja 02)."),
          "Fecha": "Fecha del informe de la hoja 02 más los días para cerrar el archivo.",
          "Estado": ("«Revisar» si un rol tiene horas y nadie registrado con ese rol o si los porcentajes no suman 100; en el cierre "
                     "del archivo, pendiente si falta la fecha del informe.")},
}
