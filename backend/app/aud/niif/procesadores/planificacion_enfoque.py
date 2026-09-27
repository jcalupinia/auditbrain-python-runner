"""Planificación de la auditoría · enfoque por ciclo (confianza o no en los controles), matriz de riesgos consolidada y
papel de conocimiento del negocio (complemento de ``planificacion_nia``; no es una herramienta del catálogo).

Decisión del dueño (2026-09-27, «considera todo sustantivo para que no tengamos nada pendiente»): **todos los ciclos son
sustantivos por política de la firma** y nada queda pendiente de confirmar. La herramienta muestra su análisis como
referencia (sale de la carta de control interno —hallazgos del ciclo, riesgo inherente, riesgo significativo—, de si los
procedimientos sustantivos solos bastan (hoja 34) y de las deficiencias del entorno de control y de TI (hoja 27)), pero no
cambia el enfoque. Solo si el socio registra «Confiar en controles» para un ciclo en la plataforma (registro «enfoque»)
ese ciclo confía: **baja un nivel la confianza del muestreo** (hoja 29) y obliga a probar la eficacia del control (hoja 12,
«¿Se probará el control?»).
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import FILA0, fx

H45, H46, H47 = "45_Enfoque_Controles", "46_Matriz_Riesgos", "47_Conocimiento_Negocio"
CEDULAS = [
    (H45, "Enfoque por ciclo: sustantivo por política de la firma, salvo que el socio decida confiar en los controles (NIA 300 y 330)"),
    (H46, "Matriz de riesgos consolidada: inherente, control, incorrección material, respuesta y procedimiento (NIA 315 y 330)"),
    (H47, "Conocimiento del negocio: identificación, entendimiento, cifras clave, ciclos, riesgos y materialidad (NIA 315)"),
]
CICLOS = [
    ("Ingresos y cuentas por cobrar", ("Ingresos", "Cuentas por cobrar")),
    ("Compras y cuentas por pagar", ("Proveedores y cuentas por pagar", "Costos y gastos")),
    ("Inventarios y costo de ventas", ("Inventarios",)),
    ("Nómina y beneficios a empleados", ("Beneficios a empleados y nómina",)),
    ("Tesorería y financiamiento", ("Caja y bancos", "Inversiones", "Préstamos y obligaciones financieras")),
    ("Activos fijos e intangibles", ("Propiedad, planta y equipo", "Arrendamientos", "Propiedades de inversión",
                                     "Activos intangibles", "Activos biológicos", "Seguros")),
    ("Impuestos, provisiones y patrimonio", ("Impuestos", "Provisiones y contingencias", "Patrimonio")),
]
NOMBRES_CICLO = tuple(c for c, _a in CICLOS)
GENERAL = "General (todos los ciclos)"
CONFIAR, SUSTANTIVO = "Confiar en controles", "Sustantivo"
DECISIONES = (CONFIAR, SUSTANTIVO)
PROP_SIN_CARTA = "Sustantivo: sin evaluación del control interno (carta RQ-004)"
PROP_REVISAR = "Revisar: los sustantivos no bastan y hay deficiencias de control (posible limitación al alcance)"
PROP_OBLIGATORIO = "Confiar en controles: obligatorio, los sustantivos solos no bastan (NIA 330 párr. 8 b))"
PROP_DEFICIENCIAS = "Sustantivo: no confiar (deficiencias de control en el ciclo, el entorno de control o TI)"
PROP_CONFIAR = "Se podría confiar en los controles: sin deficiencias informadas (lo decide el socio)"
EST_POLITICA = "Sustantivo por política de la firma"
EST_CONFIRMADO = "Confirmado por el socio"
RC_BAJO = "Bajo si la prueba de controles lo confirma"
RC_MAXIMO = "Máximo: no se confía en los controles"
EF_BAJA = "Confianza del muestreo un nivel menor (hoja 29)"
EF_NADA = "Sin reducción de la muestra"
TIPO_ENFOQUE = "Enfoque del ciclo confirmado por el socio"


def ciclo_de(area: str) -> str:
    return next((c for c, areas in CICLOS if area in areas), "")


def _conf(v) -> bool:
    return str(v or "").startswith("Confiar")


def propuesta(n12: int, no_bastan: bool, defic: bool) -> str:
    if not n12:
        return PROP_SIN_CARTA
    if no_bastan and defic:
        return PROP_REVISAR
    if no_bastan:
        return PROP_OBLIGATORIO
    return PROP_DEFICIENCIAS if defic else PROP_CONFIAR


def enfoque(carta: list, u_alto: float, decisiones: dict) -> list[dict]:
    """Un dict por ciclo con el análisis de la herramienta, la decisión del socio y el enfoque final (la decisión del
    socio o, si no la registró, «Sustantivo» por política de la firma). ``carta`` trae «area», «bastan» (sí/no), «inh» y
    «sig»; ``decisiones`` = {ciclo: decisión registrada por el socio}."""
    # El entorno de control es generalizado: sus deficiencias impiden confiar en cualquier ciclo. Las de TI solo pesan donde el
    # ciclo depende de procesos automatizados (los sustantivos no bastan).
    gen = any(x["comp"] == "Entorno de control" for x in carta)
    ti = any(x["ti"] for x in carta)
    out = []
    for nombre, _areas in CICLOS:
        filas = [i for i, x in enumerate(carta) if ciclo_de(x["area"]) == nombre]
        nob = any(not carta[i]["bastan"] for i in filas)
        defic = gen or (nob and ti) or any(carta[i]["sig"] == "Sí" or (carta[i]["inh"] is not None and carta[i]["inh"] >= u_alto) for i in filas)
        prop = propuesta(len(carta), nob, defic)
        dec = decisiones.get(nombre, "")
        out.append({"ciclo": nombre, "filas": filas, "nob": nob, "defic": defic, "prop": prop, "dec": dec,
                    "final": dec or SUSTANTIVO, "confia": _conf(dec)})
    return out


COLS_ENFOQUE = [["Ciclo", "t"], ["Cuentas del ciclo", "t"], ["Hallazgos de la carta", "t"], ["¿Bastan los sustantivos?", "t"],
                ["Deficiencias de control", "t"], ["Análisis de la herramienta", "t"], ["Decisión del socio", "t"],
                ["Enfoque final", "t"], ["Estado", "t"], ["Riesgo de control", "t"], ["Efecto en la muestra", "t"]]


def filas_enfoque(enf: list, carta: list, cuentas_ciclo: dict, c: dict) -> list:
    """``c``: R12, H34 (prefijo), par, n12, ref_ci (estado CI-01), refs_ti (estados TI), pos_enfoque {ciclo: fila de
    00_Registros}, R_."""
    R12, H34, par, n12, R_ = c["R12"], c["H34"], c["par"], c["n12"], c["R_"]
    gen_f = f'{c["ref_ci"]}="Alerta"'
    ti_f = "OR(" + ",".join(f'{t}="Alerta"' for t in c["refs_ti"]) + ")"
    filas = []
    for k, e in enumerate(enf):
        r = FILA0 + k
        f12 = [FILA0 + i for i in e["filas"]]
        f_nob = ("OR(" + ",".join(f'LEFT({H34}L{fr},3)="No:"' for fr in f12) + ")") if f12 else "FALSE"
        f_def = ("OR(" + ",".join([gen_f, f"AND({f_nob},{ti_f})"] + [f'{R12}M{fr}="Sí"' for fr in f12]
                                  + [f'AND(ISNUMBER({R12}H{fr}),N({R12}H{fr})>={par("umbralAlto")})' for fr in f12]) + ")")
        f_prop = (f'IF({n12}=0,"{PROP_SIN_CARTA}",IF(AND(D{r}="No",E{r}="Sí"),"{PROP_REVISAR}",IF(D{r}="No","{PROP_OBLIGATORIO}",'
                  f'IF(E{r}="Sí","{PROP_DEFICIENCIAS}","{PROP_CONFIAR}"))))')
        fr_reg = c["pos_enfoque"].get(e["ciclo"])
        dec = fx(f'IF({R_}F{fr_reg}="","",{R_}F{fr_reg})', e["dec"]) if fr_reg else ""
        filas.append([e["ciclo"], ", ".join(cuentas_ciclo.get(e["ciclo"], [])),
                      ", ".join(carta[i]["id"] for i in e["filas"]),
                      fx(f'IF({f_nob},"No","Sí")', "No" if e["nob"] else "Sí"), fx(f'IF({f_def},"Sí","No")', "Sí" if e["defic"] else "No"),
                      fx(f_prop, e["prop"]), dec, fx(f'IF(G{r}="","{SUSTANTIVO}",G{r})', e["final"]),
                      fx(f'IF(G{r}="","{EST_POLITICA}","{EST_CONFIRMADO}")', EST_CONFIRMADO if e["dec"] else EST_POLITICA),
                      fx(f'IF(LEFT(H{r},7)="Confiar","{RC_BAJO}","{RC_MAXIMO}")', RC_BAJO if e["confia"] else RC_MAXIMO),
                      fx(f'IF(LEFT(H{r},7)="Confiar","{EF_BAJA}","{EF_NADA}")', EF_BAJA if e["confia"] else EF_NADA)])
    return filas


def rng45(col: str, n: int) -> str:
    return f"'{H45}'!${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def rng46(col: str, n: int) -> str:
    return f"'{H46}'!${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def ref_final(enf: list, ciclo: str) -> str | None:
    """Celda del enfoque final del ciclo (hoja 45, columna H)."""
    for k, e in enumerate(enf):
        if e["ciclo"] == ciclo:
            return f"'{H45}'!H{FILA0 + k}"
    return None


# --- matriz de riesgos consolidada (hoja 46) -------------------------------------------------------------------------
COLS_MATRIZ = [["Código", "t"], ["Origen", "t"], ["Riesgo", "t"], ["Área o rubro", "t"], ["Ciclo", "t"], ["Afirmaciones", "t"],
               ["Riesgo inherente", "t"], ["¿Significativo?", "t"], ["Enfoque del ciclo", "t"], ["Riesgo de control", "t"],
               ["Riesgo de incorrección material", "t"], ["¿Se presenta?", "t"], ["PT del programa", "t"]]
ENF_GENERAL = "Respuesta global (NIA 330 párr. 5)"


def rmm(ri: str, sig: str, rc: str) -> str:
    if sig == "Sí":
        return "Significativo"
    if str(ri).startswith("Pendiente"):
        return "Pendiente de calificación"
    if str(rc).startswith("Bajo"):
        return {"Alto": "Medio", "Medio": "Bajo"}.get(ri, "Bajo")
    return ri


def f_rmm(r: int) -> str:
    return (f'IF(H{r}="Sí","Significativo",IF(LEFT(G{r},9)="Pendiente","Pendiente de calificación",IF(LEFT(J{r},4)="Bajo",'
            f'IF(G{r}="Alto","Medio","Bajo"),G{r})))')


def filas_matriz(carta: list, riesgos: list, enf: list, programa: list, c: dict) -> list:
    """Una fila por hallazgo de la carta (hoja 12) y por posible riesgo (hoja 13), con su enfoque y su procedimiento."""
    R12, R13, P19, par, n19 = c["R12"], c["R13"], c["P19"], c["par"], len(programa)
    pt_de = {str(f[2]): f[0] for f in programa}
    f_pt = lambda cod: (f'IFERROR(INDEX({P19}$A${FILA0}:$A${FILA0 + n19 - 1},MATCH("{cod}",{P19}$C${FILA0}:$C${FILA0 + n19 - 1},0)),"")')  # noqa: E731
    filas = []

    def enfo(ciclo, r, probar_ref=None, probar_v="No"):
        rf = ref_final(enf, ciclo)
        e = next((x for x in enf if x["ciclo"] == ciclo), None)
        if rf:
            return (fx(rf, e["final"]), fx(f'IF(LEFT(I{r},7)="Confiar","{RC_BAJO}","{RC_MAXIMO}")', RC_BAJO if e["confia"] else RC_MAXIMO))
        rc_v = RC_BAJO if probar_v == "Sí" else RC_MAXIMO
        rc_f = fx(f'IF({probar_ref}="Sí","{RC_BAJO}","{RC_MAXIMO}")', rc_v) if probar_ref else RC_MAXIMO
        return ENF_GENERAL, rc_f
    for i, x in enumerate(carta):
        r, r12 = FILA0 + len(filas), FILA0 + i
        ciclo = ciclo_de(x["area"])
        ri = ("Pendiente de calificación" if x["inh"] is None else "Alto" if x["inh"] >= c["u_alto"] else
              "Medio" if x["inh"] >= c["u_medio"] else "Bajo")
        en, rc = enfo(ciclo, r, f"{R12}N{r12}", x["probar"])
        rc_v = rc["v"] if isinstance(rc, dict) else rc
        filas.append([x["id"], "Carta de control interno (hoja 12)", fx(f"{R12}C{r12}", x["hallazgo"]), x["proceso"], ciclo or GENERAL,
                      fx(f'IF({R12}D{r12}="","Todas",{R12}D{r12})', x["aser"] or "Todas"),
                      fx(f'IF({R12}H{r12}="","Pendiente de calificación",IF({R12}H{r12}>={par("umbralAlto")},"Alto",'
                         f'IF({R12}H{r12}>={par("umbralMedio")},"Medio","Bajo")))', ri),
                      fx(f"{R12}M{r12}", x["sig"]), en, rc, fx(f_rmm(r), rmm(ri, x["sig"], rc_v)), "Sí",
                      fx(f_pt(x["id"]), pt_de.get(x["id"], ""))])
    for j, x in enumerate(riesgos):
        r, r13 = FILA0 + len(filas), FILA0 + j
        ciclo = ciclo_de(x.get("area", ""))
        sig = "Sí" if x["sev"] == "Significativo" else "No"
        ri = "Alto" if x["sev"] == "Significativo" else x["sev"]
        en, rc = enfo(ciclo, r)
        rc_v = rc["v"] if isinstance(rc, dict) else rc
        filas.append([x["codigo"], x["origen"], fx(f"{R13}G{r13}", x["riesgo"]), x["rubro"], ciclo or GENERAL, x.get("aser", "Todas"),
                      fx(f'IF({R13}H{r13}="Significativo","Alto",{R13}H{r13})', ri),
                      fx(f'IF({R13}H{r13}="Significativo","Sí","No")', sig), en, rc, fx(f_rmm(r), rmm(ri, sig, rc_v)),
                      fx(f"{R13}F{r13}", x["presenta"]), fx(f_pt(x["codigo"]), pt_de.get(x["codigo"], ""))])
    return filas


# --- conocimiento del negocio (hoja 47) ------------------------------------------------------------------------------
COLS_CONOCIMIENTO = [["Sección", "t"], ["Concepto", "t"], ["Detalle", "x"], ["Fuente", "t"]]


def filas_conocimiento(c: dict) -> tuple[list, list]:
    """Consolidado por fórmula: identificación (hoja 14), entendimiento (hoja 35), cifras clave (hojas 09 a 11), enfoque por
    ciclo (hoja 45) y riesgos (hoja 46)."""
    filas, est = [], []

    def titulo(t):
        filas.append([t, "", "", ""])
        est.append({"tipo": "titulo"})

    def fila(sec, concepto, detalle, fuente):
        filas.append([sec, concepto, detalle, fuente])
        est.append(None)
    titulo("Identificación de la entidad y del encargo")
    for r14, concepto, v in c["ident"]:
        fila("Identificación", concepto, fx(f"'14_Perfil'!C{r14}", v), "Hoja 14 · perfil del encargo")
    titulo("Entendimiento de la entidad y su entorno (NIA 315)")
    for k, (asp, v) in enumerate(c["entend"]):
        fila("Entendimiento", asp, fx(f"'35_Entendimiento'!C{FILA0 + k}", v), "Hoja 35 · documentos e indagaciones")
    titulo("Cifras clave")
    for concepto, ref_, v in c["cifras"]:
        fila("Cifras clave", concepto, fx(ref_, v), "Hojas 09, 10 y 11")
    titulo("Ciclos y enfoque de auditoría")
    for k, e in enumerate(c["enf"]):
        fila("Enfoque", e["ciclo"], fx(f"'{H45}'!H{FILA0 + k}", e["final"]), "Hoja 45 · sustantivo por política de la firma, salvo decisión del socio")
    titulo("Riesgos principales")
    for concepto, f_, v in c["riesgos"]:
        fila("Riesgos", concepto, fx(f_, v), "Hoja 46 · matriz de riesgos")
    return filas, est


EXPLICA = {
    H45: {"¿Bastan los sustantivos?": ("«No» si algún hallazgo de la carta del ciclo es de un proceso automatizado o de alto "
                                       "volumen (hoja 34): hay que probar los controles."),
          "Deficiencias de control": ("«Sí» si algún hallazgo del ciclo es riesgo significativo o su riesgo inherente llega al "
                                      "umbral alto (hoja 12), si hay deficiencias en el entorno de control (hoja 27) o, en un "
                                      "ciclo con procesos automatizados, deficiencias en los controles generales de TI."),
          "Análisis de la herramienta": ("Referencia para el socio, no cambia el enfoque. Sin carta: sustantivo; los sustantivos "
                                         "no bastan y hay deficiencias: revisar; no bastan: confiar (obligatorio); con "
                                         "deficiencias: sustantivo; si no: se podría confiar en los controles."),
          "Decisión del socio": "Trae la decisión que el socio registró para el ciclo en la plataforma (hoja 00_Registros).",
          "Enfoque final": "La decisión del socio o, si no registró ninguna, «Sustantivo» por política de la firma.",
          "Estado": "«Confirmado por el socio» si registró su decisión; si no, «Sustantivo por política de la firma» (nada queda pendiente).",
          "Riesgo de control": "Bajo si se confía en los controles (y la prueba lo confirma); máximo si el enfoque es sustantivo.",
          "Efecto en la muestra": "Si se confía, el muestreo de las cuentas del ciclo usa la confianza del nivel siguiente (hoja 29)."},
    H46: {"Riesgo": "Trae el texto del hallazgo (hoja 12) o del posible riesgo (hoja 13).",
          "Afirmaciones": "Las aseveraciones del hallazgo de la carta; en los riesgos de la hoja 13, las del área.",
          "Riesgo inherente": ("En la carta, el riesgo inherente (probabilidad × impacto) frente a los umbrales de la hoja 02; en "
                               "la hoja 13, la severidad (un riesgo significativo es inherente alto)."),
          "¿Significativo?": "Trae si el riesgo es significativo (hoja 12, columna M, o severidad de la hoja 13).",
          "Enfoque del ciclo": "Trae el enfoque final del ciclo de la hoja 45; los riesgos generales tienen respuesta global.",
          "Riesgo de control": ("Bajo si el ciclo confía en los controles (o, en un hallazgo general, si se probará su control); "
                                "máximo si no."),
          "Riesgo de incorrección material": ("Significativo si lo es; si no, el inherente, que baja un nivel cuando el riesgo "
                                              "de control es bajo."),
          "¿Se presenta?": "Los hallazgos de la carta siempre; los de la hoja 13, según su columna «¿Se presenta?».",
          "PT del programa": "Busca en la hoja 19 el procedimiento que responde a ese riesgo (por su código)."},
    H47: {"Detalle": ("Trae el dato de su hoja de origen: identificación (hoja 14), entendimiento (hoja 35), cifras de los "
                      "estados, índices y materialidad (hojas 09 a 11), enfoque por ciclo (hoja 45) y conteos de la matriz (hoja 46).")},
}
