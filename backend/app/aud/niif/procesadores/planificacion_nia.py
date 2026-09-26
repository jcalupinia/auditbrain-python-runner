"""Planificación de la auditoría: materialidad, procedimientos analíticos preliminares, riesgos,
estrategia global y plan de auditoría (NIA 300, 315, 320, 240, 570, 330).

Versión simple que cumple la norma. Dos anexos:

- ``estados`` (principal): estados financieros comparativos por cuenta, con el grupo del estado
  financiero (activo corriente, pasivo no corriente, ingresos, gastos…), el área de auditoría y los
  saldos del año actual y del anterior. Total de control = suma del saldo actual.
- ``factores``: cuestionario de entendimiento de la entidad y factores de riesgo (respuestas de la
  administración a las indagaciones del auditor): factor, norma, área afectada y respuesta Sí/No.

1. Bases de materialidad (NIA 320 párr. A3–A8): activos, patrimonio, ingresos, gastos totales y
   utilidad antes de impuestos, cada una con su porcentaje de referencia (política de la firma) y la
   materialidad indicativa que resulta.
2. Materialidad (NIA 320 párr. 10–11; NIA 450 párr. 5 y A2): global = base elegida × %; de ejecución
   = global × %; umbral de errores claramente insignificantes = global × %. Base ≤ 0 = problema.
3. Procedimientos analíticos preliminares (NIA 315 párr. 14 b; NIA 520): variación absoluta y
   relativa y peso vertical de cada cuenta; cuenta significativa si |saldo| ≥ materialidad de
   ejecución; variación inusual si |variación| ≥ materialidad de ejecución y |variación %| ≥ umbral.
4. Áreas (sección del balance o resultados × área de auditoría): saldo, variación, variaciones
   inusuales, factores de riesgo de la administración y riesgo inherente preliminar (Alto si el área
   es significativa y tiene variación inusual o factor de riesgo; Medio si es significativa o tiene
   un factor; Bajo en otro caso), enfoque de la respuesta (NIA 330) y herramienta del catálogo AUD
   que la responde.
5. Riesgos de incorrección material: presunción de fraude en el reconocimiento de ingresos (NIA 240
   párr. 26, refutable con documentación, párr. 47) y elusión de controles por la dirección (párr. 31,
   no refutable); áreas de riesgo alto; indicios de empresa en funcionamiento (NIA 570 párr. 10 y A3:
   patrimonio negativo, pérdida, capital de trabajo negativo); factores de riesgo respondidos «Sí».
6. Estrategia global (NIA 300 párr. 7–8) y plan de auditoría por área (párr. 9).

Las NIA se citan por su numeración en la versión en español del IAASB (NIA clarificadas; NIA 315
Revisada 2019). Los porcentajes de referencia de materialidad NO los fija la NIA (320 A8 solo da
ejemplos): son parámetros de la política de la firma. Pendiente M03: cotejar cada párrafo citado con
el texto oficial en español vigente al ejercicio (VERIFICAR).
"""
from __future__ import annotations

import unicodedata

from backend.app.aud.niif.procesadores import problemas as _pr
from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_fecha, a_num, campo, es_pymes, filas_mapeadas, fx, hoja, m, n2, norm,
    problema, r2, ref, req, validar_campos, validar_definicion_generica,
)

VERSION = "planificacion_nia 1.0"
RUBRO = "PLANIFICACION"

# --- grupos del estado financiero y áreas de auditoría --------------------------------------

GRUPOS = ["Activo corriente", "Activo no corriente", "Pasivo corriente", "Pasivo no corriente", "Patrimonio",
          "Ingresos", "Otros ingresos", "Costos", "Gastos", "Otros gastos", "Impuesto a la renta"]
_ALIAS_GRUPO = {
    "activocorriente": "Activo corriente", "activonocorriente": "Activo no corriente",
    "pasivocorriente": "Pasivo corriente", "pasivonocorriente": "Pasivo no corriente",
    "patrimonio": "Patrimonio", "patrimonioneto": "Patrimonio",
    "ingresos": "Ingresos", "ingresosordinarios": "Ingresos", "ventas": "Ingresos", "ingresosdeactividadesordinarias": "Ingresos",
    "otrosingresos": "Otros ingresos", "costos": "Costos", "costo": "Costos", "costodeventas": "Costos",
    "costosdeventas": "Costos", "gastos": "Gastos", "gastosoperacionales": "Gastos", "otrosgastos": "Otros gastos",
    "gastosfinancieros": "Otros gastos", "impuestoalarenta": "Impuesto a la renta",
    "impuestoalaganancias": "Impuesto a la renta", "impuestoalarentacorrienteydiferido": "Impuesto a la renta",
}
SECCION = {"Activo corriente": "Activo", "Activo no corriente": "Activo", "Pasivo corriente": "Pasivo",
           "Pasivo no corriente": "Pasivo", "Patrimonio": "Patrimonio"}  # el resto: «Resultados»

# Área de auditoría → herramienta del catálogo AUD que la responde (NIA 330).
HERRAMIENTAS = {
    "Caja y bancos": "Efectivo y equivalentes de efectivo",
    "Inversiones": "Inversiones e instrumentos financieros",
    "Cuentas por cobrar": "Cuentas por cobrar y pérdida crediticia esperada",
    "Inventarios": "Inventarios: costo y valor neto de realización",
    "Propiedad, planta y equipo": "Propiedad, planta y equipo",
    "Arrendamientos": "Arrendamientos",
    "Propiedades de inversión": "Propiedades de inversión",
    "Activos intangibles": "Activos intangibles y goodwill",
    "Activos biológicos": "Activos biológicos",
    "Proveedores y cuentas por pagar": "Proveedores y cuentas por pagar",
    "Préstamos y obligaciones financieras": "Préstamos y obligaciones financieras",
    "Beneficios a empleados y nómina": "Beneficios sociales y nómina",
    "Provisiones y contingencias": "Provisiones y contingencias",
    "Impuestos": "Impuesto corriente y diferido",
    "Patrimonio": "Patrimonio",
    "Ingresos": "Ingresos de contratos con clientes",
    "Costos y gastos": "Costos y gastos",
}
SIN_HERRAMIENTA = "Procedimientos sustantivos del auditor (sin herramienta del catálogo)"

# Área por defecto cuando el anexo no la trae: palabras clave del nombre de la cuenta.
_PALABRAS_AREA = [
    (("caja", "banco", "efectivo"), ("Activo",), "Caja y bancos"),
    (("inversion",), ("Activo",), "Inversiones"),
    (("cobrar", "cliente", "cartera", "incobrable"), ("Activo",), "Cuentas por cobrar"),
    (("inventario", "mercader", "materiaprima"), ("Activo",), "Inventarios"),
    (("derechodeuso", "arrendamiento"), ("Activo", "Pasivo"), "Arrendamientos"),
    (("propiedaddeinversion",), ("Activo",), "Propiedades de inversión"),
    (("propiedad", "planta", "equipo", "vehicul", "maquinari", "edificio", "terreno", "depreciacion"), ("Activo", "Resultados"),
     "Propiedad, planta y equipo"),
    (("intangible", "software", "licencia", "goodwill", "plusvalia", "amortizacion"), ("Activo", "Resultados"), "Activos intangibles"),
    (("biologic", "plantacion", "ganado"), ("Activo",), "Activos biológicos"),
    (("impuesto", "iva", "retencion", "creditotributario"), ("Activo", "Pasivo", "Resultados"), "Impuestos"),
    (("proveedor", "cuentasporpagar", "porpagarcomerciales"), ("Pasivo",), "Proveedores y cuentas por pagar"),
    (("prestamo", "obligacionesbancarias", "obligacionesfinancieras", "sobregiro", "financier", "interes"), ("Pasivo", "Resultados"),
     "Préstamos y obligaciones financieras"),
    (("sueldo", "beneficio", "nomina", "iess", "jubilacion", "desahucio", "decimo", "vacacion", "participacion"),
     ("Pasivo", "Resultados"), "Beneficios a empleados y nómina"),
    (("provision", "contingencia", "garantia"), ("Pasivo",), "Provisiones y contingencias"),
]


def _grupo(v) -> str | None:
    return _ALIAS_GRUPO.get(norm(v))


def _seccion(grupo: str) -> str:
    return SECCION.get(grupo, "Resultados")


def _area_defecto(cuenta: str, grupo: str) -> str:
    sec, n = _seccion(grupo), norm(cuenta)
    for claves, secciones, area in _PALABRAS_AREA:
        if sec in secciones and any(k in n for k in claves):
            return area
    if sec == "Patrimonio":
        return "Patrimonio"
    if grupo in ("Ingresos", "Otros ingresos"):
        return "Ingresos"
    if grupo == "Impuesto a la renta":
        return "Impuestos"
    if sec == "Resultados":
        return "Costos y gastos"
    return "Otros activos" if sec == "Activo" else "Otros pasivos"


def _herramienta(area: str) -> str:
    k = _clave(area)
    return next((v for a, v in HERRAMIENTAS.items() if _clave(a) == k), SIN_HERRAMIENTA)


def _clave(v) -> str:
    """Igual que SUMIFS/COUNTIFS de Excel: sin espacios de borde y sin distinguir mayúsculas."""
    return str(v if v is not None else "").strip().lower()


def _si(v) -> bool:
    s = unicodedata.normalize("NFD", str(v or "").strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s in ("si", "s", "yes", "y", "x", "true", "1", "verdadero")


def _no(v) -> bool:
    return norm(v) in ("no", "n", "false", "0", "falso")


# --- anexos --------------------------------------------------------------------------------

_ESTADOS = [
    campo("id", "Código de cuenta", alias=("codigo", "código", "cuenta contable", "codigo cuenta", "cta"), ejemplo="1.1.03"),
    campo("cuenta", "Nombre de la cuenta", alias=("nombre", "descripcion", "descripción", "nombre cuenta", "detalle"),
          ejemplo="Cuentas por cobrar clientes"),
    campo("grupo", "Grupo del estado financiero", alias=("grupo", "clasificacion", "clasificación", "tipo", "grupo eeff"),
          ejemplo="Activo corriente"),
    campo("area", "Área de auditoría", requerido=False, alias=("area", "área", "rubro", "ciclo", "area de auditoria"),
          ejemplo="Cuentas por cobrar"),
    campo("saldo_actual", "Saldo actual", "number", alias=("saldo", "saldo al corte", "año actual", "ano actual", "saldo del ejercicio"),
          ejemplo="812300.00"),
    campo("saldo_anterior", "Saldo anterior", "number", requerido=False,
          alias=("año anterior", "ano anterior", "saldo ejercicio anterior", "saldo del año anterior"), ejemplo="690500.00"),
]
_FACTORES = [
    campo("id", "Código del factor", alias=("codigo", "código", "id", "n°"), ejemplo="F-01"),
    campo("factor", "Factor de riesgo o pregunta", alias=("factor", "pregunta", "descripcion", "descripción"),
          ejemplo="¿Existen metas de ventas o bonos de la gerencia ligados a resultados?"),
    campo("norma", "Norma (NIA)", requerido=False, alias=("nia", "norma", "referencia"), ejemplo="NIA 240"),
    campo("area", "Área afectada", requerido=False, alias=("area", "área", "rubro", "area afectada"), ejemplo="Ingresos"),
    campo("respuesta", "Respuesta (Sí/No)", alias=("respuesta", "aplica", "si/no", "sí/no"), ejemplo="Sí"),
    campo("comentario", "Comentario o evidencia", requerido=False, alias=("comentario", "evidencia", "observacion", "observación"),
          ejemplo="Bono anual del gerente comercial sobre ventas"),
]
CAMPOS = {"estados": _ESTADOS, "factores": _FACTORES}
TIPOS = {"estados": "estados", "factores": "factores"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "estados"
CONTROL = "saldo_actual"

BASES = ("Activos totales", "Patrimonio", "Ingresos", "Gastos totales", "Utilidad antes de impuestos")
SI_NO = ("Sí", "No")
PARAMETROS = {
    "baseMaterialidad": "Ingresos", "pctBase": 1, "pctEjecucion": 65, "pctTrivial": 5,
    "refActivos": 1, "refPatrimonio": 2, "refIngresos": 1, "refGastos": 1, "refUAI": 5,
    "umbralVarPct": 10,
    "encargoInicial": "No", "interesPublico": "No", "auditoriaGrupo": "No",
    "refutarIngresos": "No", "motivoRefutacion": "",
    "enfoque": "Sustantivo con pruebas de controles clave",
    "fechaPreliminar": "", "fechaFinal": "", "fechaInforme": "",
    "socio": "", "gerente": "", "expertos": "",
}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "baseMaterialidad": "Base de la materialidad (" + " / ".join(BASES) + ")",
    "pctBase": "Porcentaje aplicado a la base (%)",
    "pctEjecucion": "Materialidad de ejecución: % de la global (política de la firma; usual 50–75 %)",
    "pctTrivial": "Errores claramente insignificantes: % de la global (política de la firma)",
    "refActivos": "Referencia de la firma: % sobre activos totales",
    "refPatrimonio": "Referencia de la firma: % sobre patrimonio",
    "refIngresos": "Referencia de la firma: % sobre ingresos (NIA 320 A8 da 1 % como ejemplo)",
    "refGastos": "Referencia de la firma: % sobre gastos totales (NIA 320 A8 da 1 % como ejemplo)",
    "refUAI": "Referencia de la firma: % sobre utilidad antes de impuestos (NIA 320 A8 da 5 % como ejemplo)",
    "umbralVarPct": "Umbral de variación inusual en los analíticos preliminares (%)",
    "encargoInicial": "Encargo inicial: primer año de auditoría (Sí / No)",
    "interesPublico": "Entidad de interés público o cotizada (Sí / No)",
    "auditoriaGrupo": "Auditoría de estados financieros de un grupo (Sí / No)",
    "refutarIngresos": "Se refuta la presunción de fraude en el reconocimiento de ingresos (Sí / No)",
    "motivoRefutacion": "Motivo documentado de la refutación (NIA 240 párr. 47)",
    "enfoque": "Enfoque general de la auditoría",
    "fechaPreliminar": "Fecha de la visita preliminar",
    "fechaFinal": "Fecha de la visita final",
    "fechaInforme": "Fecha prevista de entrega del informe",
    "socio": "Socio del encargo", "gerente": "Gerente o encargado del equipo",
    "expertos": "Uso de expertos (actuario, tasador, especialista en TI…)",
}
TOTAL_EJEMPLO = "materialidad"


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    out = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        if tipo == "estados":
            g = str(f.get("grupo", "") or "").strip()
            if g and _grupo(g) is None:
                out["errors"].append({"row": f.get("_row"), "field": "grupo",
                                      "message": "Grupo no reconocido: use " + ", ".join(GRUPOS) + "."})
        else:
            r = str(f.get("respuesta", "") or "").strip()
            if r and not (_si(r) or _no(r)):
                out["errors"].append({"row": f.get("_row"), "field": "respuesta", "message": "Respuesta: use Sí o No."})
    out["ok"] = not out["errors"]
    return out


# --- cálculo -------------------------------------------------------------------------------

def _pnum(p, k, minimo=0.0, maximo=100.0):
    v = a_num(p.get(k))
    if v is None or not minimo < float(v) <= maximo:
        raise ValueError(f"{ETIQUETAS_PARAM[k]}: use un porcentaje mayor que {minimo:g} y hasta {maximo:g}.")
    return float(v)


def _psino(p, k) -> str:
    v = str(p.get(k) or "No").strip()
    if _si(v):
        return "Sí"
    if _no(v):
        return "No"
    raise ValueError(f"{ETIQUETAS_PARAM[k]}: responda Sí o No.")


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = a_fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    base_nombre = next((b for b in BASES if norm(b) == norm(p["baseMaterialidad"])), None)
    if base_nombre is None:
        raise ValueError("Base de la materialidad: elija " + ", ".join(BASES) + ".")
    pct_base, pct_ejec, pct_triv = _pnum(p, "pctBase"), _pnum(p, "pctEjecucion"), _pnum(p, "pctTrivial")
    refs = {k: _pnum(p, k) for k in ("refActivos", "refPatrimonio", "refIngresos", "refGastos", "refUAI")}
    umbral = _pnum(p, "umbralVarPct", 0, 1000)
    sino = {k: _psino(p, k) for k in ("encargoInicial", "interesPublico", "auditoriaGrupo", "refutarIngresos")}
    fechas = {}
    for k in ("fechaPreliminar", "fechaFinal", "fechaInforme"):
        v = str(p.get(k) or "").strip()
        if v and a_fecha(v) is None:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: fecha inválida.")
        fechas[k] = a_fecha(v).isoformat() if v else None
    marco = (MARCO_PYMES if es_pymes(p) else MARCO_COMPLETAS)

    # 1 · cuentas
    cuentas = []
    for f in datasets.get("estados") or []:
        act = a_num(f.get("saldo_actual"))
        if act is None:
            continue
        g = _grupo(f.get("grupo"))
        if g is None:
            raise ValueError(f"Cuenta {f.get('id')}: grupo no reconocido ({f.get('grupo')}).")
        ant = a_num(f.get("saldo_anterior")) if str(f.get("saldo_anterior", "") or "").strip() else None
        cuenta = str(f.get("cuenta", "") or "").strip() or "(sin nombre)"
        area = str(f.get("area", "") or "").strip() or _area_defecto(cuenta, g)
        cuentas.append({"id": str(f.get("id", "")).strip(), "cuenta": cuenta, "grupo": g, "seccion": _seccion(g),
                        "area": area, "actual": float(act), "anterior": None if ant is None else float(ant), "_row": f.get("_row")})
    if not cuentas:
        raise ValueError("Cargue los estados financieros comparativos por cuenta (balance y resultados).")
    hay_anterior = any(c["anterior"] is not None for c in cuentas)

    # 2 · bases (mismo orden que la hoja 03)
    def sg(grupo, k="actual"):
        return sum((c[k] or 0) for c in cuentas if c["grupo"] == grupo)

    bases = {}
    for k in ("actual", "anterior"):
        b = {g: sg(g, k) for g in GRUPOS}
        b["Activos totales"] = b["Activo corriente"] + b["Activo no corriente"]
        b["Pasivos totales"] = b["Pasivo corriente"] + b["Pasivo no corriente"]
        b["Diferencia de cuadre"] = b["Activos totales"] - b["Pasivos totales"] - b["Patrimonio"]
        b["Capital de trabajo"] = b["Activo corriente"] - b["Pasivo corriente"]
        b["Gastos totales"] = b["Costos"] + b["Gastos"] + b["Otros gastos"]
        b["Utilidad antes de impuestos"] = b["Ingresos"] + b["Otros ingresos"] - b["Gastos totales"]
        b["Utilidad neta"] = b["Utilidad antes de impuestos"] - b["Impuesto a la renta"]
        bases[k] = b
    ba = bases["actual"]
    ref_de = {"Activos totales": refs["refActivos"], "Patrimonio": refs["refPatrimonio"], "Ingresos": refs["refIngresos"],
              "Gastos totales": refs["refGastos"], "Utilidad antes de impuestos": refs["refUAI"]}
    indicativa = {b: ba[b] * ref_de[b] / 100 for b in BASES}

    # 3 · materialidad
    base_valor = ba[base_nombre]
    mat = base_valor * pct_base / 100
    ejec = mat * pct_ejec / 100
    triv = mat * pct_triv / 100

    # 4 · analíticos por cuenta
    for c in cuentas:
        ant = c["anterior"] or 0
        c["var"] = c["actual"] - ant
        c["varPct"] = None if ant == 0 else c["var"] / ant
        den = ba["Activos totales"] if c["seccion"] != "Resultados" else ba["Ingresos"]
        c["vertical"] = None if den == 0 else c["actual"] / den
        c["significativa"] = "Sí" if abs(c["actual"]) >= ejec else "No"
        if not hay_anterior or abs(c["var"]) < ejec:
            c["inusual"] = "No"
        elif c["varPct"] is None:
            c["inusual"] = "Sí"
        else:
            c["inusual"] = "Sí" if abs(c["varPct"]) >= umbral / 100 else "No"

    # 5 · factores
    factores = []
    for f in datasets.get("factores") or []:
        factores.append({"id": str(f.get("id", "")).strip(), "factor": str(f.get("factor", "") or "").strip(),
                         "norma": str(f.get("norma", "") or "").strip(), "area": str(f.get("area", "") or "").strip(),
                         "respuesta": "Sí" if _si(f.get("respuesta")) else "No",
                         "comentario": str(f.get("comentario", "") or "").strip(), "_row": f.get("_row")})

    # 6 · áreas (sección × área, en el orden en que aparecen)
    areas, idx = [], {}
    for c in cuentas:
        k = (c["seccion"], _clave(c["area"]))
        if k not in idx:
            idx[k] = len(areas)
            areas.append({"seccion": c["seccion"], "area": c["area"], "cuentas": []})
        areas[idx[k]]["cuentas"].append(c)
    for a in areas:
        cs = a["cuentas"]
        a["n"] = len(cs)
        a["actual"] = sum(c["actual"] for c in cs)
        a["anterior"] = sum(c["anterior"] or 0 for c in cs)
        a["var"] = a["actual"] - a["anterior"]
        a["varPct"] = None if a["anterior"] == 0 else a["var"] / a["anterior"]
        a["significativa"] = "Sí" if abs(a["actual"]) >= ejec else "No"
        a["inusuales"] = sum(1 for c in cs if c["inusual"] == "Sí")
        a["factores"] = sum(1 for f in factores if f["respuesta"] == "Sí" and _clave(f["area"]) == _clave(a["area"]))
        if a["significativa"] == "Sí" and (a["inusuales"] > 0 or a["factores"] > 0):
            a["riesgo"] = "Alto"
        elif a["significativa"] == "Sí" or a["factores"] > 0:
            a["riesgo"] = "Medio"
        else:
            a["riesgo"] = "Bajo"
        a["enfoque"] = ENFOQUE[a["riesgo"]]
        a["herramienta"] = _herramienta(a["area"])
        a["oportunidad"] = OPORTUNIDAD["Alto" if a["riesgo"] == "Alto" else "otro"]

    # 7 · riesgos de incorrección material
    riesgos = []

    def riesgo(tipo, texto, norma, area, aser, nivel, respuesta, herramienta, ref_=None, importe=None):
        riesgos.append({"codigo": f"R-{len(riesgos) + 1:02d}", "tipo": tipo, "riesgo": texto, "norma": norma, "area": area,
                        "aseveraciones": aser, "nivel": nivel, "respuesta": respuesta, "herramienta": herramienta,
                        "ref": ref_, "importe": importe})

    riesgo("ingresos", "Fraude en el reconocimiento de ingresos (presunción)", "NIA 240 párr. 26–27", "Ingresos",
           "Ocurrencia, corte", "Refutado (documentado)" if sino["refutarIngresos"] == "Sí" else "Significativo",
           "Pruebas de corte y de detalle de ventas, confirmaciones de saldos, notas de crédito posteriores al cierre",
           HERRAMIENTAS["Ingresos"], ("bases", "Ingresos"), ba["Ingresos"])
    riesgo("elusion", "Elusión de los controles por la dirección", "NIA 240 párr. 31–33", "Todas", "Todas", "Significativo",
           "Pruebas de asientos de diario y otros ajustes, revisión de estimaciones y de transacciones inusuales",
           "Motor de auditoría analítica (pruebas de asientos)")
    for i, a in enumerate(areas):
        if a["riesgo"] == "Alto":
            aser = "Existencia, valoración, integridad" if a["seccion"] == "Activo" else (
                "Integridad, valoración, obligaciones" if a["seccion"] == "Pasivo" else (
                    "Presentación, integridad" if a["seccion"] == "Patrimonio" else "Ocurrencia, integridad, corte"))
            riesgo("area", f"Incorrección material en {a['area']} ({a['seccion'].lower()}): área significativa con variación "
                           "inusual o factor de riesgo", "NIA 315 párr. 28–32", a["area"], aser, "Significativo", a["enfoque"],
                   a["herramienta"], ("area", i), a["actual"])
    ind_570 = []
    if ba["Patrimonio"] < 0:
        ind_570.append(("Patrimonio", "Patrimonio negativo"))
    if ba["Utilidad antes de impuestos"] < 0:
        ind_570.append(("Utilidad antes de impuestos", "Pérdida antes de impuestos en el ejercicio"))
    if ba["Capital de trabajo"] < 0:
        ind_570.append(("Capital de trabajo", "Capital de trabajo negativo"))
    for concepto, texto in ind_570:
        riesgo("570", f"Empresa en funcionamiento: {texto.lower()}", "NIA 570 párr. 10 y A3", "Todas", "Presentación, revelación",
               "Indicio (evaluar)", "Evaluar la capacidad de continuar: flujos proyectados, financiamiento, hechos posteriores",
               SIN_HERRAMIENTA, ("bases", concepto), ba[concepto])
    for f in factores:
        if f["respuesta"] == "Sí":
            riesgo("factor", f["factor"], f["norma"] or "NIA 315", f["area"] or "Todas", "Por definir", "Por evaluar",
                   f["comentario"] or "Evaluar el efecto del factor en el riesgo del área", _herramienta(f["area"]) if f["area"] else SIN_HERRAMIENTA)
    if sino["encargoInicial"] == "Sí":
        riesgo("inicial", "Saldos de apertura de un encargo inicial", "NIA 510 párr. 6", "Todas", "Existencia, valoración",
               "Por evaluar", "Revisar los papeles del auditor predecesor o aplicar procedimientos sobre saldos de apertura",
               SIN_HERRAMIENTA)

    # 8 · problemas
    probs = []
    if base_valor <= 0:
        probs.append(problema("BASE_NO_VALIDA", f"La base elegida ({base_nombre}) es {m(base_valor)}: no sirve para la materialidad; "
                                                "elija otra base (NIA 320 párr. A4–A5).", base_valor))
    if abs(ba["Diferencia de cuadre"]) > 0.005:
        probs.append(problema("ESF_NO_CUADRA", f"El balance no cuadra: activos − pasivos − patrimonio = {m(ba['Diferencia de cuadre'])}. "
                                               "Revise el anexo (¿falta el resultado del ejercicio en el patrimonio?).", ba["Diferencia de cuadre"]))
    for concepto, texto in ind_570:
        probs.append(problema({"Patrimonio": "PATRIMONIO_NEGATIVO", "Utilidad antes de impuestos": "PERDIDA_EJERCICIO",
                               "Capital de trabajo": "CAPITAL_TRABAJO_NEGATIVO"}[concepto],
                              f"{texto}: indicio sobre la empresa en funcionamiento; evalúe (NIA 570 párr. 10).", ba[concepto]))
    if sino["refutarIngresos"] == "Sí":
        if not str(p.get("motivoRefutacion") or "").strip():
            probs.append(problema("REFUTACION_SIN_MOTIVO", "Se refutó la presunción de fraude en ingresos sin documentar el motivo "
                                                           "(NIA 240 párr. 47).", 0))
    else:
        probs.append(problema("RIESGO_FRAUDE_INGRESOS", f"Riesgo significativo presunto de fraude en el reconocimiento de ingresos "
                                                        f"({m(ba['Ingresos'])}): responder con procedimientos específicos (NIA 240 párr. 26 y 30).",
                              ba["Ingresos"]))
    probs.append(problema("ELUSION_CONTROLES", "Riesgo de elusión de controles por la dirección: pruebas de asientos, estimaciones "
                                               "y transacciones inusuales en todo encargo (NIA 240 párr. 31–33).", 0))
    for a in areas:
        if a["riesgo"] == "Alto":
            probs.append(problema("AREA_RIESGO_ALTO", f"{a['seccion']} · {a['area']}: riesgo inherente alto ({a['inusuales']} variación(es) "
                                                      f"inusual(es), {a['factores']} factor(es) de riesgo); respuesta: {a['enfoque'].lower()}.",
                                  a["actual"]))
    for c in cuentas:
        if c["inusual"] == "Sí":
            probs.append(problema("VARIACION_INUSUAL", f"{c['id']} {c['cuenta']}: variación de {m(c['var'])}"
                                                       + ("" if c["varPct"] is None else f" ({c['varPct'] * 100:.1f} %)".replace(".", ","))
                                                       + "; obtenga la explicación de la administración y corrobórela.", c["var"]))
    for f in factores:
        if f["respuesta"] == "Sí":
            probs.append(problema("FACTOR_RIESGO", f"{f['id']}: {f['factor']} ({f['norma'] or 'NIA 315'}).", 0))
    if not factores:
        probs.append(problema("SIN_CUESTIONARIO", "No se cargó el cuestionario de entendimiento y factores de riesgo: documente el "
                                                  "entendimiento de la entidad (NIA 315 párr. 19–27).", 0))
    if not hay_anterior:
        probs.append(problema("SIN_ANIO_ANTERIOR", "Sin saldos del año anterior: los analíticos preliminares no miden variaciones "
                                                   "(NIA 315 párr. 14 b).", 0))
    if sino["encargoInicial"] == "Sí":
        probs.append(problema("ENCARGO_INICIAL", "Encargo inicial: planifique los procedimientos sobre saldos de apertura (NIA 510 párr. 6; "
                                                 "NIA 300 párr. 13).", 0))

    n_sig = sum(1 for a in areas if a["significativa"] == "Sí")
    n_rsig = sum(1 for r in riesgos if r["nivel"] == "Significativo")
    totales = {"activos": r2(ba["Activos totales"]), "ingresos": r2(ba["Ingresos"]), "uai": r2(ba["Utilidad antes de impuestos"]),
               "patrimonio": r2(ba["Patrimonio"]), "materialidad": r2(mat), "ejecucion": r2(ejec), "trivial": r2(triv),
               "areasSignificativas": r2(n_sig), "riesgosSignificativos": r2(n_rsig)}
    etiquetas = {"activos": "Activos totales", "ingresos": "Ingresos", "uai": "Utilidad antes de impuestos",
                 "patrimonio": "Patrimonio", "materialidad": "Materialidad global", "ejecucion": "Materialidad de ejecución",
                 "trivial": "Umbral de errores claramente insignificantes", "areasSignificativas": "Áreas significativas",
                 "riesgosSignificativos": "Riesgos significativos"}
    filas = [{"id": c["id"], "cuenta": c["cuenta"], "grupo": c["grupo"], "area": c["area"], "saldo_actual": r2(c["actual"]),
              "saldo_anterior": "" if c["anterior"] is None else r2(c["anterior"]), "variacion": r2(c["var"]),
              "significativa": c["significativa"], "inusual": c["inusual"], "_row": c["_row"]} for c in cuentas]
    detalle = {"corte": corte_a.isoformat(), "marco": marco, "base": base_nombre, "pct": {"base": pct_base, "ejec": pct_ejec, "triv": pct_triv},
               "refs": refs, "umbral": umbral, "sino": sino, "fechas": fechas, "bases": bases, "indicativa": indicativa,
               "materialidad": {"base": base_valor, "global": mat, "ejecucion": ejec, "trivial": triv},
               "cuentas": cuentas, "factores": factores, "areas": [{k: v for k, v in a.items() if k != "cuentas"} for a in areas],
               "riesgos": riesgos, "hayAnterior": hay_anterior, "parametros": p}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "materialidad",
            "exceptions": probs, "schedule": [], "detalle": detalle}


ENFOQUE = {"Alto": "Sustantivo ampliado: pruebas de detalle con alcance mayor al corte",
           "Medio": "Sustantivo: analíticos sustantivos y pruebas de detalle",
           "Bajo": "Analíticos sustantivos; sin pruebas de detalle adicionales"}
OPORTUNIDAD = {"Alto": "Visita preliminar (controles) y visita final (detalle al corte)", "otro": "Visita final (al corte)"}


# --- cédulas con fórmulas --------------------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen de la planificación"), ("02_Parametros", "Parámetros"),
    ("03_Bases", "Bases de materialidad (NIA 320)"), ("04_Materialidad", "Materialidad (NIA 320 y 450)"),
    ("05_Analitica", "Analíticos preliminares por cuenta (NIA 315 y 520)"), ("06_Areas", "Áreas y riesgo inherente (NIA 315)"),
    ("07_Factores", "Entendimiento y factores de riesgo"), ("08_Riesgos", "Riesgos de incorrección material (NIA 315, 240 y 570)"),
    ("09_Estrategia", "Estrategia global de auditoría (NIA 300)"), ("10_Plan", "Plan de auditoría por área (NIA 300 y 330)"),
    ("11_Problemas", "Asuntos para la planificación"),
]
P, BAS, MAT, ANA, ARE, FAC, RIE = (ref(n) for n in ("02_Parametros", "03_Bases", "04_Materialidad", "05_Analitica", "06_Areas",
                                                  "07_Factores", "08_Riesgos"))
_PAR = ["corte", "marco", "baseMaterialidad", "pctBase", "pctEjecucion", "pctTrivial", "refActivos", "refPatrimonio",
        "refIngresos", "refGastos", "refUAI", "umbralVarPct", "encargoInicial", "interesPublico", "auditoriaGrupo",
        "refutarIngresos", "motivoRefutacion", "enfoque", "fechaPreliminar", "fechaFinal", "fechaInforme", "socio", "gerente", "expertos"]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
_BAS = ["Activo corriente", "Activo no corriente", "Activos totales", "Pasivo corriente", "Pasivo no corriente", "Pasivos totales",
        "Patrimonio", "Diferencia de cuadre", "Capital de trabajo", "Ingresos", "Otros ingresos", "Costos", "Gastos", "Otros gastos",
        "Gastos totales", "Utilidad antes de impuestos", "Impuesto a la renta", "Utilidad neta"]
FB = {k: FILA0 + i for i, k in enumerate(_BAS)}
_MAT = ["base", "pctBase", "global", "pctEjecucion", "ejecucion", "pctTrivial", "trivial"]
FM = {k: FILA0 + i for i, k in enumerate(_MAT)}
EJEC = f"{MAT}$B${FM['ejecucion']}"


EXPLICA = {
    "01_Resumen": {
        "Importe": ("Trae cada cifra de la hoja donde se calcula: activos, ingresos, utilidad y patrimonio de la hoja 03 "
                    "(Bases de materialidad); las tres materialidades de la hoja 04; el número de áreas significativas de "
                    "la hoja 06 y el de riesgos significativos de la hoja 08."),
    },
    "03_Bases": {
        "Año actual": ("Suma el saldo actual de las cuentas de la hoja 05 (Analíticos preliminares) que pertenecen a ese "
                       "grupo del estado financiero; los totales, el cuadre, el capital de trabajo y las utilidades se "
                       "calculan con las filas de arriba de esta misma hoja."),
        "Año anterior": ("Hace lo mismo con el saldo del año anterior de la hoja 05, para ver cómo cambió cada base "
                         "de un año a otro."),
        "% de referencia": ("Trae de la hoja 02 (Parámetros) el porcentaje de referencia que la política de la firma "
                            "fija para cada posible base de la materialidad."),
        "Materialidad indicativa": ("Multiplica el importe del año actual por el porcentaje de referencia y lo divide "
                                    "para 100: es la materialidad que resultaría si se eligiera esa base."),
    },
    "04_Materialidad": {
        "Valor": ("Busca en la hoja 03 el importe de la base elegida en la hoja 02; la materialidad global es la base por "
                  "el porcentaje aplicado ÷ 100; la de ejecución y el umbral de errores claramente insignificantes son la "
                  "global por su porcentaje ÷ 100, con los porcentajes de la hoja 02."),
    },
    "05_Analitica": {
        "Sección": ("Clasifica la cuenta según su grupo: activo corriente o no corriente = Activo, pasivo corriente o no "
                    "corriente = Pasivo, patrimonio = Patrimonio y todo lo demás = Resultados."),
        "Variación": "Resta el saldo del año anterior del saldo actual: cuánto subió (positivo) o bajó (negativo) la cuenta.",
        "Variación %": ("Divide la variación para el saldo del año anterior; si el año anterior es cero o está vacío, queda "
                        "en blanco porque no hay base para el porcentaje."),
        "Peso vertical": ("Divide el saldo actual para los activos totales (cuentas del balance) o para los ingresos (cuentas "
                          "de resultados) de la hoja 03: el peso de la cuenta en su estado financiero."),
        "Significativa": ("Marca «Sí» cuando el saldo actual, sin importar el signo, iguala o supera la materialidad de "
                          "ejecución de la hoja 04 (Materialidad)."),
        "Variación inusual": ("Marca «Sí» cuando la variación iguala o supera la materialidad de ejecución y además su porcentaje "
                              "iguala o supera el umbral de la hoja 02 (o no hay año anterior con qué compararla); sin "
                              "saldos del año anterior en todo el anexo, marca «No»."),
    },
    "06_Areas": {
        "Cuentas": "Cuenta cuántas cuentas de la hoja 05 tienen esta misma sección y esta misma área de auditoría.",
        "Saldo actual": "Suma el saldo actual de las cuentas de la hoja 05 que tienen esta sección y esta área.",
        "Saldo anterior": "Suma el saldo del año anterior de esas mismas cuentas de la hoja 05 (Analíticos preliminares).",
        "Variación": "Resta el saldo anterior del saldo actual del área: su cambio neto en el año.",
        "Variación %": ("Divide la variación del área para su saldo anterior; queda en blanco si el área no tenía saldo el "
                        "año anterior."),
        "Significativa": ("Marca «Sí» cuando el saldo actual del área, sin signo, iguala o supera la materialidad de ejecución "
                          "de la hoja 04."),
        "Variaciones inusuales": ("Cuenta las cuentas del área que en la hoja 05 quedaron marcadas con variación inusual."),
        "Factores de riesgo": ("Cuenta los factores de la hoja 07 (Entendimiento y factores de riesgo) que la administración "
                               "respondió «Sí» para esta área."),
        "Riesgo inherente": ("Alto si el área es significativa y tiene al menos una variación inusual o un factor de riesgo; "
                             "Medio si es significativa o tiene un factor; Bajo en los demás casos (evaluación preliminar que el "
                             "auditor confirma)."),
        "Enfoque": ("Asigna la respuesta según el riesgo inherente: alto = pruebas de detalle con mayor alcance; medio = "
                    "analíticos sustantivos y pruebas de detalle; bajo = solo analíticos sustantivos."),
    },
    "08_Riesgos": {
        "Nivel": ("Para las áreas, repite la calificación de la hoja 06: «Significativo» mientras el riesgo inherente siga "
                  "siendo alto; si cambia, pide revisar la fila."),
        "Importe expuesto": ("Trae el importe sobre el que recae el riesgo: los ingresos, el patrimonio, la utilidad o el "
                             "capital de trabajo de la hoja 03, o el saldo actual del área de la hoja 06."),
    },
    "09_Estrategia": {
        "Decisión": ("Cada decisión remite a su origen: marco, enfoque, fechas, equipo y respuestas Sí/No de la hoja 02; las "
                     "materialidades de la hoja 04; y los conteos de áreas significativas (hoja 06) y riesgos "
                     "significativos (hoja 08)."),
    },
    "10_Plan": {
        "Riesgo inherente": "Trae el riesgo inherente preliminar del área desde la hoja 06 (Áreas y riesgo inherente).",
        "Enfoque": "Trae de la hoja 06 el enfoque de la respuesta asignado al área según su riesgo.",
        "Oportunidad": ("Si el riesgo es alto, planifica trabajo en la visita preliminar (controles) y en la final (detalle "
                        "al corte); si no, concentra el trabajo en la visita final."),
        "Umbral de partida clave": ("Trae la materialidad de ejecución de la hoja 04: toda partida igual o mayor se "
                                    "examina individualmente en el área."),
        "Herramienta del catálogo": "Trae de la hoja 06 la herramienta del catálogo AUD que ejecuta las pruebas del área.",
    },
}

# En la planificación no hay «cifra del cliente frente a la recalculada»: el comparativo muestra los dos
# umbrales que guían el trabajo (graficos.TEXTOS los cambia solo para esta herramienta).
PANEL = {
    "poblacion": {"rotulo": "Activos totales", "total": "activos"},
    "recalculado": {"rotulo": "Materialidad de ejecución", "total": "ejecucion"},
    "registrado": {"rotulo": "Umbral de errores claramente insignificantes", "total": "trivial"},
    "textos": {"comparativo": "Umbrales de la planificación",
               "comparativo_sub": "Materialidad de ejecución (NIA 320) frente al umbral de errores claramente insignificantes (NIA 450), en USD.",
               "nota_recalculado": "NIA 320 párr. 11", "nota_registrado": "NIA 450 párr. 5",
               "problemas": "Asuntos para la planificación"},
    "composicion": {"rotulo": "Activos por área", "hoja": "06_Areas", "etiqueta": "Área", "valor": "Saldo actual",
                    "donde": {"Sección": ["Activo"]}},
    "distribucion": {"rotulo": "Resultados por área", "hoja": "06_Areas", "etiqueta": "Área", "valor": "Saldo actual",
                     "donde": {"Sección": ["Resultados"]}},
}


# --- origen del importe de cada problema --------------------------------------------------------

def _h(hojas, nombre):
    return next((x for x in hojas if x["name"] == nombre), None)


def _concepto(hoja_, columna, concepto):
    def f(hojas, e):
        h = _h(hojas, hoja_)
        if h is None:
            return None
        j = [c[0] for c in h["cols"]].index(columna)
        for i, fila in enumerate(h["rows"]):
            if _pr._texto(fila[0]).startswith(concepto):
                return _pr.celda(hojas, hoja_, columna, i), fila[j]
        return None
    return f


def _por_prefijo(hoja_, columna, prefijo):
    """Fila cuya clave (prefijo(fila)) abre la descripción del problema seguida de «:»."""
    def f(hojas, e):
        h = _h(hojas, hoja_)
        if h is None:
            return None
        msg = e.get("message") or ""
        j = [c[0] for c in h["cols"]].index(columna)
        for i, fila in enumerate(h["rows"]):
            if msg.startswith(prefijo(fila) + ":"):
                return _pr.celda(hojas, hoja_, columna, i), fila[j]
        return None
    return f


REF_PROBLEMAS = {
    "BASE_NO_VALIDA": _concepto("04_Materialidad", "Valor", "Base elegida"),                 # importe de la base elegida
    "ESF_NO_CUADRA": _concepto("03_Bases", "Año actual", "Diferencia de cuadre"),            # activos − pasivos − patrimonio
    "PATRIMONIO_NEGATIVO": _concepto("03_Bases", "Año actual", "Patrimonio"),
    "PERDIDA_EJERCICIO": _concepto("03_Bases", "Año actual", "Utilidad antes de impuestos"),
    "CAPITAL_TRABAJO_NEGATIVO": _concepto("03_Bases", "Año actual", "Capital de trabajo"),
    "RIESGO_FRAUDE_INGRESOS": _concepto("03_Bases", "Año actual", "Ingresos"),               # ingresos del ejercicio
    "AREA_RIESGO_ALTO": _por_prefijo("06_Areas", "Saldo actual",
                                     lambda f: f"{_pr._texto(f[0])} · {_pr._texto(f[1])}"),  # saldo del área
    "VARIACION_INUSUAL": _por_prefijo("05_Analitica", "Variación",
                                      lambda f: f"{_pr._texto(f[0])} {_pr._texto(f[1])}"),   # variación de la cuenta
}


def _rango(hoja_ref: str, col: str, n: int) -> str:
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, ba, bn = d["parametros"], d["bases"]["actual"], d["bases"]["anterior"]
    cs, fs, ar, rs = d["cuentas"], d["factores"], d["areas"], d["riesgos"]
    nc, nf, na, nr = len(cs), len(fs), len(ar), len(rs)
    mt = d["materialidad"]
    pv = lambda k: None if p.get(k) in (None, "") else p.get(k)  # noqa: E731

    # 02 · parámetros (valores del encargo y juicio del auditor)
    fecha = lambda k: d["fechas"][k]  # noqa: E731
    parametros = [
        ["Corte del ejercicio", d["corte"], "Ficha del encargo"],
        ["Marco de información financiera", d["marco"], "Ficha del encargo"],
        ["Base de la materialidad", d["base"], "NIA 320 párr. A3–A5: elección de la base con juicio profesional"],
        ["Porcentaje aplicado a la base (%)", d["pct"]["base"], "NIA 320 párr. A8: juicio profesional (5 % de la utilidad y 1 % de ingresos o gastos son ejemplos)"],
        ["Materialidad de ejecución (% de la global)", d["pct"]["ejec"], "NIA 320 párr. 11 y A12: política de la firma según el riesgo"],
        ["Errores claramente insignificantes (% de la global)", d["pct"]["triv"], "NIA 450 párr. 5 y A2: política de la firma"],
        ["Referencia: % sobre activos totales", d["refs"]["refActivos"], "Política de la firma (no la fija la NIA)"],
        ["Referencia: % sobre patrimonio", d["refs"]["refPatrimonio"], "Política de la firma (no la fija la NIA)"],
        ["Referencia: % sobre ingresos", d["refs"]["refIngresos"], "Política de la firma; NIA 320 A8 da 1 % como ejemplo"],
        ["Referencia: % sobre gastos totales", d["refs"]["refGastos"], "Política de la firma; NIA 320 A8 da 1 % como ejemplo"],
        ["Referencia: % sobre utilidad antes de impuestos", d["refs"]["refUAI"], "Política de la firma; NIA 320 A8 da 5 % como ejemplo"],
        ["Umbral de variación inusual (%)", d["umbral"], "Juicio del auditor para los analíticos preliminares"],
        ["Encargo inicial", d["sino"]["encargoInicial"], "NIA 300 párr. 13 y NIA 510"],
        ["Entidad de interés público o cotizada", d["sino"]["interesPublico"], "NIA 701 (asuntos clave de auditoría)"],
        ["Auditoría de un grupo", d["sino"]["auditoriaGrupo"], "NIA 600"],
        ["Se refuta la presunción de fraude en ingresos", d["sino"]["refutarIngresos"], "NIA 240 párr. 26 y 47"],
        ["Motivo de la refutación", pv("motivoRefutacion"), "NIA 240 párr. 47"],
        ["Enfoque general", pv("enfoque"), "NIA 300 párr. 8"],
        ["Visita preliminar", fecha("fechaPreliminar"), "Calendario del encargo"],
        ["Visita final", fecha("fechaFinal"), "Calendario del encargo"],
        ["Entrega del informe", fecha("fechaInforme"), "Calendario del encargo"],
        ["Socio del encargo", pv("socio"), "NIA 220"],
        ["Gerente o encargado", pv("gerente"), "NIA 220"],
        ["Uso de expertos", pv("expertos"), "NIA 300 párr. 8 e) y NIA 620"],
    ]

    # 05 · analíticos por cuenta
    A = lambda col: _rango(ANA, col, nc)  # noqa: E731
    ing, act = f"{BAS}$B${FB['Ingresos']}", f"{BAS}$B${FB['Activos totales']}"
    analitica = []
    for i, c in enumerate(cs):
        r = FILA0 + i
        sec = (f'IF(OR(C{r}="Activo corriente",C{r}="Activo no corriente"),"Activo",'
               f'IF(OR(C{r}="Pasivo corriente",C{r}="Pasivo no corriente"),"Pasivo",IF(C{r}="Patrimonio","Patrimonio","Resultados")))')
        analitica.append([
            c["id"], c["cuenta"], c["grupo"], fx(sec, c["seccion"]), c["area"], n2(c["actual"]), n2(c["anterior"]),
            fx(f"F{r}-G{r}", n2(c["var"])),
            fx(f'IF(G{r}=0,"",H{r}/G{r})', c["varPct"]),
            fx(f'IF(D{r}="Resultados",IF({ing}=0,"",F{r}/{ing}),IF({act}=0,"",F{r}/{act}))', c["vertical"]),
            fx(f'IF(ABS(F{r})>={EJEC},"Sí","No")', c["significativa"]),
            fx(f'IF(COUNT({A("G")})=0,"No",IF(ABS(H{r})<{EJEC},"No",IF(I{r}="","Sí",IF(ABS(I{r})>={P}$B${PAR["umbralVarPct"]}/100,"Sí","No"))))',
               c["inusual"]),
        ])

    # 03 · bases
    def sumif(grupo, col):
        return f'SUMIF({A("C")},"{grupo}",{A(col)})'
    refp = {"Activos totales": "refActivos", "Patrimonio": "refPatrimonio", "Ingresos": "refIngresos",
            "Gastos totales": "refGastos", "Utilidad antes de impuestos": "refUAI"}
    deriv = {
        "Activos totales": "{c}{a}+{c}{b}".replace("{a}", str(FB["Activo corriente"])).replace("{b}", str(FB["Activo no corriente"])),
        "Pasivos totales": "{c}" + str(FB["Pasivo corriente"]) + "+{c}" + str(FB["Pasivo no corriente"]),
        "Diferencia de cuadre": "{c}" + str(FB["Activos totales"]) + "-{c}" + str(FB["Pasivos totales"]) + "-{c}" + str(FB["Patrimonio"]),
        "Capital de trabajo": "{c}" + str(FB["Activo corriente"]) + "-{c}" + str(FB["Pasivo corriente"]),
        "Gastos totales": "{c}" + str(FB["Costos"]) + "+{c}" + str(FB["Gastos"]) + "+{c}" + str(FB["Otros gastos"]),
        "Utilidad antes de impuestos": "{c}" + str(FB["Ingresos"]) + "+{c}" + str(FB["Otros ingresos"]) + "-{c}" + str(FB["Gastos totales"]),
        "Utilidad neta": "{c}" + str(FB["Utilidad antes de impuestos"]) + "-{c}" + str(FB["Impuesto a la renta"]),
    }
    sustento = {
        "Activos totales": "Base posible (NIA 320 A4)", "Patrimonio": "Base posible (NIA 320 A4)", "Ingresos": "Base posible (NIA 320 A4 y A8)",
        "Gastos totales": "Base posible (NIA 320 A4 y A8)", "Utilidad antes de impuestos": "Base posible (NIA 320 A4 y A8)",
        "Diferencia de cuadre": "Debe ser cero: activos = pasivos + patrimonio", "Capital de trabajo": "Indicio NIA 570 si es negativo",
    }
    bases = []
    for k in _BAS:
        if k in deriv:
            fa, fp = fx(deriv[k].replace("{c}", "B"), n2(ba[k])), fx(deriv[k].replace("{c}", "C"), n2(bn[k]))
        else:
            fa, fp = fx(sumif(k, "F"), n2(ba[k])), fx(sumif(k, "G"), n2(bn[k]))
        r = FB[k]
        if k in refp:
            pct = fx(f"{P}$B${PAR[refp[k]]}", d["refs"][refp[k]])
            ind = fx(f"B{r}*D{r}/100", n2(d["indicativa"][k]))
        else:
            pct = ind = None
        bases.append([k, fa, fp, pct, ind, sustento.get(k, "Suma por grupo de la hoja 05" if k not in deriv else "Cálculo con las filas anteriores")])

    # 04 · materialidad
    rng_con, rng_imp = f"{BAS}$A${FILA0}:$A${FILA0 + len(_BAS) - 1}", f"{BAS}$B${FILA0}:$B${FILA0 + len(_BAS) - 1}"
    materialidad = [
        [f"Base elegida: {d['base']}", fx(f"INDEX({rng_imp},MATCH({P}$B${PAR['baseMaterialidad']},{rng_con},0))", n2(mt["base"])),
         "NIA 320 párr. A3–A5"],
        ["Porcentaje aplicado (%)", fx(f"{P}$B${PAR['pctBase']}", d["pct"]["base"]), "NIA 320 párr. A8"],
        ["Materialidad global", fx(f"B{FM['base']}*B{FM['pctBase']}/100", n2(mt["global"])), "NIA 320 párr. 10"],
        ["Materialidad de ejecución (% de la global)", fx(f"{P}$B${PAR['pctEjecucion']}", d["pct"]["ejec"]), "NIA 320 párr. A12"],
        ["Materialidad de ejecución", fx(f"B{FM['global']}*B{FM['pctEjecucion']}/100", n2(mt["ejecucion"])), "NIA 320 párr. 11"],
        ["Errores claramente insignificantes (% de la global)", fx(f"{P}$B${PAR['pctTrivial']}", d["pct"]["triv"]), "NIA 450 párr. A2"],
        ["Umbral de errores claramente insignificantes", fx(f"B{FM['global']}*B{FM['pctTrivial']}/100", n2(mt["trivial"])),
         "NIA 450 párr. 5: no se acumulan los errores menores"],
    ]

    # 07 · factores
    factores = [[f["id"], f["factor"], f["norma"], f["area"], f["respuesta"], f["comentario"]] for f in fs]

    # 06 · áreas
    areas = []
    for i, a in enumerate(ar):
        r = FILA0 + i
        crit = f"{A('D')},A{r},{A('E')},B{r}"
        fac = f'COUNTIFS({_rango(FAC, "D", nf)},B{r},{_rango(FAC, "E", nf)},"Sí")' if nf else "0"
        areas.append([
            a["seccion"], a["area"], fx(f"COUNTIFS({crit})", a["n"]),
            fx(f"SUMIFS({A('F')},{crit})", n2(a["actual"])), fx(f"SUMIFS({A('G')},{crit})", n2(a["anterior"])),
            fx(f"D{r}-E{r}", n2(a["var"])), fx(f'IF(E{r}=0,"",F{r}/E{r})', a["varPct"]),
            fx(f'IF(ABS(D{r})>={EJEC},"Sí","No")', a["significativa"]),
            fx(f'COUNTIFS({crit},{A("L")},"Sí")', a["inusuales"]), fx(fac, a["factores"]),
            fx(f'IF(AND(H{r}="Sí",OR(I{r}>0,J{r}>0)),"Alto",IF(OR(H{r}="Sí",J{r}>0),"Medio","Bajo"))', a["riesgo"]),
            fx(f'IF(K{r}="Alto","{ENFOQUE["Alto"]}",IF(K{r}="Medio","{ENFOQUE["Medio"]}","{ENFOQUE["Bajo"]}"))', a["enfoque"]),
            a["herramienta"],
        ])

    # 08 · riesgos
    riesgos = []
    for x in rs:
        if x["tipo"] == "area":
            ra = FILA0 + x["ref"][1]
            nivel = fx(f'IF({ARE}K{ra}="Alto","Significativo","Revisar: el riesgo del área cambió")', x["nivel"])
            imp = fx(f"{ARE}D{ra}", n2(x["importe"]))
        elif x["ref"]:
            nivel = x["nivel"]
            imp = fx(f"{BAS}B{FB[x['ref'][1]]}", n2(x["importe"]))
        else:
            nivel, imp = x["nivel"], None
        riesgos.append([x["codigo"], x["riesgo"], x["norma"], x["area"], x["aseveraciones"], nivel, imp, x["respuesta"], x["herramienta"]])

    # 09 · estrategia
    def par(k):
        return f"{P}$B${PAR[k]}"

    def txt(k, valor):
        return fx(f'IF({par(k)}="","",{par(k)})', valor)
    n_sig = sum(1 for a in ar if a["significativa"] == "Sí")
    n_alto = sum(1 for a in ar if a["riesgo"] == "Alto")
    n_rsig = sum(1 for x in rs if x["nivel"] == "Significativo")
    sino = d["sino"]
    ref_ing = "No refutada: riesgo significativo (NIA 240 párr. 26)"
    estrategia = [
        ["Marco de información financiera", fx(par("marco"), d["marco"]), "NIA 300 párr. 8 a)"],
        ["Enfoque general", txt("enfoque", pv("enfoque") or ""), "NIA 300 párr. 8"],
        ["Encargo inicial", fx(f'IF({par("encargoInicial")}="Sí","Sí: procedimientos sobre saldos de apertura (NIA 510)","No")',
                               "Sí: procedimientos sobre saldos de apertura (NIA 510)" if sino["encargoInicial"] == "Sí" else "No"),
         "NIA 300 párr. 13"],
        ["Entidad de interés público o cotizada", fx(f'IF({par("interesPublico")}="Sí","Sí: comunicar asuntos clave de auditoría (NIA 701)","No")',
                                                     "Sí: comunicar asuntos clave de auditoría (NIA 701)" if sino["interesPublico"] == "Sí" else "No"),
         "NIA 300 párr. 8 b)"],
        ["Auditoría de un grupo", fx(f'IF({par("auditoriaGrupo")}="Sí","Sí: planificar el trabajo sobre los componentes (NIA 600)","No")',
                                     "Sí: planificar el trabajo sobre los componentes (NIA 600)" if sino["auditoriaGrupo"] == "Sí" else "No"),
         "NIA 300 párr. 8 a)"],
        ["Base de la materialidad", fx(par("baseMaterialidad"), d["base"]), "NIA 320 párr. A3–A5"],
        ["Materialidad global", fx(f"{MAT}$B${FM['global']}", n2(mt["global"])), "NIA 320 párr. 10"],
        ["Materialidad de ejecución", fx(f"{MAT}$B${FM['ejecucion']}", n2(mt["ejecucion"])), "NIA 320 párr. 11"],
        ["Umbral de errores claramente insignificantes", fx(f"{MAT}$B${FM['trivial']}", n2(mt["trivial"])), "NIA 450 párr. 5"],
        ["Áreas significativas", fx(f'COUNTIF({_rango(ARE, "H", na)},"Sí")', n_sig), "NIA 315 párr. 29"],
        ["Áreas de riesgo inherente alto", fx(f'COUNTIF({_rango(ARE, "K", na)},"Alto")', n_alto), "NIA 315 párr. 31"],
        ["Riesgos significativos", fx(f'COUNTIF({_rango(RIE, "F", nr)},"Significativo")', n_rsig), "NIA 315 párr. 32; NIA 330 párr. 15 y 21"],
        ["Presunción de fraude en ingresos", fx(f'IF({par("refutarIngresos")}="Sí","Refutada: "&{par("motivoRefutacion")},"{ref_ing}")',
                                                ("Refutada: " + str(pv("motivoRefutacion") or "")) if sino["refutarIngresos"] == "Sí" else ref_ing),
         "NIA 240 párr. 26 y 47"],
        ["Visita preliminar", txt("fechaPreliminar", d["fechas"]["fechaPreliminar"] or ""), "NIA 300 párr. 8 c)"],
        ["Visita final", txt("fechaFinal", d["fechas"]["fechaFinal"] or ""), "NIA 300 párr. 8 c)"],
        ["Entrega del informe", txt("fechaInforme", d["fechas"]["fechaInforme"] or ""), "NIA 300 párr. 8 b)"],
        ["Socio del encargo", txt("socio", pv("socio") or ""), "NIA 220; NIA 300 párr. 8 e)"],
        ["Gerente o encargado", txt("gerente", pv("gerente") or ""), "NIA 300 párr. 8 e) y 11"],
        ["Uso de expertos", txt("expertos", pv("expertos") or ""), "NIA 300 párr. 8 e) y NIA 620"],
        ["Comunicación con los responsables del gobierno", "Alcance y momento planificados de la auditoría y riesgos significativos",
         "NIA 260 párr. 15"],
    ]

    # 10 · plan por área (riesgo alto o medio)
    plan = []
    for i, a in enumerate(ar):
        if a["riesgo"] == "Bajo":
            continue
        ra, r = FILA0 + i, FILA0 + len(plan)
        plan.append([f"{a['seccion']} · {a['area']}", fx(f"{ARE}K{ra}", a["riesgo"]), fx(f"{ARE}L{ra}", a["enfoque"]),
                     fx(f'IF(B{r}="Alto","{OPORTUNIDAD["Alto"]}","{OPORTUNIDAD["otro"]}")', a["oportunidad"]),
                     fx(EJEC, n2(mt["ejecucion"])), fx(f"{ARE}M{ra}", a["herramienta"])])

    # 01 · resumen
    ref_res = {"activos": f"{BAS}B{FB['Activos totales']}", "ingresos": f"{BAS}B{FB['Ingresos']}",
               "uai": f"{BAS}B{FB['Utilidad antes de impuestos']}", "patrimonio": f"{BAS}B{FB['Patrimonio']}",
               "materialidad": f"{MAT}B{FM['global']}", "ejecucion": f"{MAT}B{FM['ejecucion']}", "trivial": f"{MAT}B{FM['trivial']}",
               "areasSignificativas": f'COUNTIF({_rango(ARE, "H", na)},"Sí")',
               "riesgosSignificativos": f'COUNTIF({_rango(RIE, "F", nr)},"Significativo")'}
    t = {k: float(v) for k, v in res["totals"].items()}
    resumen = [[res["labels"][k], fx(ref_res[k], n2(t[k]))] for k in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen de la planificación", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Bases", "Bases de materialidad (NIA 320)",
             [["Concepto", "t"], ["Año actual", "n"], ["Año anterior", "n"], ["% de referencia", "x"], ["Materialidad indicativa", "n"],
              ["Sustento", "t"]], bases, explica=EXPLICA["03_Bases"]),
        hoja("04_Materialidad", "Materialidad (NIA 320 y 450)", [["Concepto", "t"], ["Valor", "n"], ["Sustento", "t"]], materialidad,
             explica=EXPLICA["04_Materialidad"]),
        hoja("05_Analitica", "Analíticos preliminares por cuenta (NIA 315 y 520)",
             [["Código", "t"], ["Cuenta", "t"], ["Grupo", "t"], ["Sección", "t"], ["Área", "t"], ["Saldo actual", "n"],
              ["Saldo anterior", "n"], ["Variación", "n"], ["Variación %", "p"], ["Peso vertical", "p"], ["Significativa", "t"],
              ["Variación inusual", "t"]], analitica, explica=EXPLICA["05_Analitica"]),
        hoja("06_Areas", "Áreas y riesgo inherente (NIA 315)",
             [["Sección", "t"], ["Área", "t"], ["Cuentas", "i"], ["Saldo actual", "n"], ["Saldo anterior", "n"], ["Variación", "n"],
              ["Variación %", "p"], ["Significativa", "t"], ["Variaciones inusuales", "i"], ["Factores de riesgo", "i"],
              ["Riesgo inherente", "t"], ["Enfoque", "t"], ["Herramienta del catálogo", "t"]], areas, explica=EXPLICA["06_Areas"]),
        hoja("07_Factores", "Entendimiento y factores de riesgo",
             [["Código", "t"], ["Factor", "t"], ["Norma", "t"], ["Área", "t"], ["Respuesta", "t"], ["Comentario", "t"]], factores),
        hoja("08_Riesgos", "Riesgos de incorrección material (NIA 315, 240 y 570)",
             [["Código", "t"], ["Riesgo", "t"], ["Norma", "t"], ["Área", "t"], ["Aseveraciones", "t"], ["Nivel", "t"],
              ["Importe expuesto", "n"], ["Respuesta planificada", "t"], ["Herramienta", "t"]], riesgos, explica=EXPLICA["08_Riesgos"]),
        hoja("09_Estrategia", "Estrategia global de auditoría (NIA 300)", [["Aspecto", "t"], ["Decisión", "x"], ["Sustento", "t"]],
             estrategia, explica=EXPLICA["09_Estrategia"]),
        hoja("10_Plan", "Plan de auditoría por área (NIA 300 y 330)",
             [["Área", "t"], ["Riesgo inherente", "t"], ["Enfoque", "t"], ["Oportunidad", "t"], ["Umbral de partida clave", "n"],
              ["Herramienta del catálogo", "t"]], plan, explica=EXPLICA["10_Plan"]),
        hoja("11_Problemas", "Asuntos para la planificación", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(float(e["amount"]))] for e in res["exceptions"]]),
    ]


# --- definición --------------------------------------------------------------------------------

def definicion() -> dict:
    estados = ("Una fila por cuenta del estado de situación financiera y del estado de resultados (a nivel de cuenta de mayor o "
               "de agrupación): código, nombre, grupo del estado financiero (" + ", ".join(GRUPOS) + "), área de auditoría "
               "(opcional) y saldos del año actual y del anterior, en positivo tal como se presentan. El patrimonio incluye el "
               "resultado del ejercicio. Sin filas de total.")
    factores = ("Una fila por pregunta del cuestionario de entendimiento de la entidad y factores de riesgo, respondida por la "
                "administración: código, factor, norma (NIA 240, 250, 315, 550, 570…), área afectada, respuesta Sí/No y comentario.")
    return {
        "name": "Planificación de la auditoría · materialidad, analíticos preliminares, riesgos y estrategia (NIA 300, 315, 320)",
        "area": "Planificación",
        "processor": "planificacion_nia",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Arma el expediente de planificación con los estados financieros comparativos y el cuestionario de "
                    "entendimiento: calcula las bases y la materialidad global, de ejecución y el umbral de errores claramente "
                    "insignificantes (NIA 320, 450); corre los analíticos preliminares por cuenta (NIA 315 párr. 14 b, NIA 520) y "
                    "marca cuentas significativas y variaciones inusuales; agrupa por área y asigna un riesgo inherente preliminar; "
                    "lista los riesgos de incorrección material, incluidos los presuntos de fraude (NIA 240) y los indicios de "
                    "empresa en funcionamiento (NIA 570); y documenta la estrategia global y el plan por área con la herramienta "
                    "del catálogo que responde a cada riesgo (NIA 300, 330)."),
        "source": {"organization": "IAASB · Normas Internacionales de Auditoría (versión en español)", "type": "Norma de auditoría",
                   "date": "",
                   "document": ("NIA 300 párr. 7–13; NIA 315 (Revisada 2019) párr. 13–14, 19–32; NIA 320 párr. 10–14 y A3–A13; "
                                "NIA 450 párr. 5 y A2; NIA 240 párr. 26–27, 31–33 y 47; NIA 570 párr. 10 y A3; NIA 330 párr. 5–7, "
                                "15 y 21; NIA 260 párr. 15; NIA 510 párr. 6. VERIFICAR la numeración contra el texto oficial vigente."),
                   "url": "https://www.iaasb.org/standards-pronouncements"},
        "nia": [
            {"document": "NIA 300", "section": "párr. 7–12", "requirement": "Establecer la estrategia global y desarrollar el plan de auditoría; actualizarlos y documentarlos."},
            {"document": "NIA 315 (Revisada 2019)", "section": "párr. 13–14, 19–32",
             "requirement": "Procedimientos de valoración del riesgo (indagación, analíticos, observación); entendimiento de la entidad; identificar y valorar los riesgos y los significativos."},
            {"document": "NIA 320", "section": "párr. 10–14", "requirement": "Determinar la materialidad global y la de ejecución, revisarlas y documentarlas."},
            {"document": "NIA 450", "section": "párr. 5", "requirement": "Acumular las incorrecciones salvo las claramente insignificantes."},
            {"document": "NIA 240", "section": "párr. 26–27, 31–33, 47",
             "requirement": "Presunción de fraude en ingresos (refutable y documentada) y respuesta a la elusión de controles por la dirección."},
            {"document": "NIA 570", "section": "párr. 10", "requirement": "Considerar en la valoración del riesgo los hechos o condiciones sobre la empresa en funcionamiento."},
            {"document": "NIA 330", "section": "párr. 5–7, 15, 21", "requirement": "Respuestas globales y procedimientos posteriores a los riesgos valorados; riesgos significativos."},
        ],
        "calculo": [
            "Bases de materialidad por grupo del estado financiero (SUMIF por grupo): activos, patrimonio, ingresos, gastos totales y utilidad antes de impuestos.",
            "Materialidad global = base elegida × porcentaje; de ejecución = global × %; umbral claramente insignificante = global × % (NIA 320 párr. 10–11; NIA 450).",
            "Analíticos por cuenta: variación = actual − anterior; variación % = variación ÷ anterior; peso vertical sobre activos o ingresos.",
            "Cuenta significativa: |saldo| ≥ materialidad de ejecución. Variación inusual: |variación| ≥ ejecución y |variación %| ≥ umbral.",
            "Riesgo inherente preliminar del área: Alto (significativa con variación inusual o factor de riesgo), Medio (significativa o con factor), Bajo.",
            "Riesgos significativos: fraude en ingresos (presunción, salvo refutación documentada), elusión de controles y áreas de riesgo alto; indicios NIA 570 (patrimonio negativo, pérdida, capital de trabajo negativo).",
            "Estrategia global (NIA 300 párr. 7–8) y plan por área con la herramienta del catálogo que responde a cada riesgo (NIA 300 párr. 9; NIA 330).",
        ],
        "fields": _ESTADOS, "rules": [], "control": CONTROL, "primary": "materialidad",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, etq] for n, etq in CEDULAS],
        "program": [
            {"code": "PLA-01", "objective": "Aceptación, independencia y términos del encargo", "risk": "Encargo aceptado sin evaluar la independencia ni acordar los términos",
             "assertion": "Encargo", "procedure": "Verificar la evaluación de aceptación y continuidad, la independencia del equipo y la carta de encargo firmada",
             "evidence": "Carta de encargo, declaraciones de independencia", "criterion": "Términos acordados por escrito antes de iniciar",
             "source": "NIA 210 párr. 9–10; NIA 220"},
            {"code": "PLA-02", "objective": "Entendimiento de la entidad y de su entorno", "risk": "Riesgos no identificados por falta de entendimiento",
             "assertion": "Todas", "procedure": "Aplicar el cuestionario de entendimiento y factores de riesgo con la administración y documentar las respuestas",
             "evidence": "Cuestionario respondido, actas, organigrama", "criterion": "Factores de riesgo documentados por área",
             "source": "NIA 315 párr. 19–27"},
            {"code": "PLA-03", "objective": "Procedimientos analíticos preliminares", "risk": "Variaciones inusuales no detectadas",
             "assertion": "Todas", "procedure": "Comparar los estados financieros con el año anterior (horizontal y vertical) e identificar variaciones inusuales",
             "evidence": "Estados financieros comparativos", "criterion": "Variaciones inusuales explicadas por la administración",
             "source": "NIA 315 párr. 14 b); NIA 520"},
            {"code": "PLA-04", "objective": "Materialidad", "risk": "Materialidad inadecuada para el usuario de los estados financieros",
             "assertion": "Todas", "procedure": "Elegir la base y el porcentaje, calcular la materialidad global, de ejecución y el umbral claramente insignificante",
             "evidence": "Bases de materialidad", "criterion": "Materialidades calculadas y sustentadas",
             "source": "NIA 320 párr. 10–11, 14; NIA 450 párr. 5"},
            {"code": "PLA-05", "objective": "Identificación y valoración de riesgos", "risk": "Riesgos significativos sin respuesta específica",
             "assertion": "Todas", "procedure": "Valorar el riesgo inherente por área, identificar los riesgos significativos, incluidos los de fraude y de empresa en funcionamiento",
             "evidence": "Matriz de áreas y riesgos", "criterion": "Cada riesgo significativo con respuesta planificada",
             "source": "NIA 315 párr. 28–32; NIA 240 párr. 26–27, 31; NIA 570 párr. 10"},
            {"code": "PLA-06", "objective": "Estrategia global y plan de auditoría", "risk": "Trabajo sin alcance, oportunidad ni recursos definidos",
             "assertion": "Todas", "procedure": "Documentar la estrategia global y el plan por área con naturaleza, oportunidad y extensión de los procedimientos",
             "evidence": "Memorando de estrategia y plan", "criterion": "Estrategia y plan aprobados por el socio",
             "source": "NIA 300 párr. 7–12; NIA 330 párr. 5–7"},
            {"code": "PLA-07", "objective": "Comunicación con los responsables del gobierno", "risk": "Gobierno corporativo sin conocer el alcance ni los riesgos",
             "assertion": "Todas", "procedure": "Comunicar el alcance y el momento de realización planificados y los riesgos significativos",
             "evidence": "Comunicación escrita o acta de reunión", "criterion": "Comunicación documentada", "source": "NIA 260 párr. 15"},
        ],
        "requests": [
            req("RQ-001", "Estados financieros comparativos por cuenta (situación financiera y resultados)", "estados", "PLA-03",
                "Bases de materialidad y analíticos preliminares", content=estados),
            req("RQ-002", "Cuestionario de entendimiento de la entidad y factores de riesgo respondido", "factores", "PLA-02",
                "Factores de riesgo por área (NIA 315, 240, 250, 550 y 570)", content=factores),
            req("RQ-003", "Carta de encargo firmada y declaraciones de independencia del equipo", None, "PLA-01",
                "Aceptación del encargo y términos acordados", formats=("pdf", "docx"), use="soporte"),
            req("RQ-004", "Actas de junta general y de directorio del ejercicio y posteriores al cierre", None, "PLA-02",
                "Decisiones, partes relacionadas y hechos relevantes", formats=("pdf", "docx"), use="soporte"),
            req("RQ-005", "Informe de auditoría y carta de control interno del año anterior", None, "PLA-05",
                "Deficiencias de control y salvedades previas", formats=("pdf", "docx"), use="soporte", required=False),
            req("RQ-006", "Organigrama y descripción de los procesos clave", None, "PLA-02",
                "Entendimiento del control interno y del entorno de TI", formats=("pdf", "docx"), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo (M19) --------------------------------------------------------------------------------

def _c(id, cuenta, grupo, area, actual, anterior):
    return {"id": id, "cuenta": cuenta, "grupo": grupo, "area": area, "saldo_actual": actual, "saldo_anterior": anterior, "_row": 2}


def _f(id, factor, norma, area, resp, comentario=""):
    return {"id": id, "factor": factor, "norma": norma, "area": area, "respuesta": resp, "comentario": comentario, "_row": 2}


_ESTADOS_EJ = [
    _c("1.1.01", "Caja y bancos", "Activo corriente", "Caja y bancos", "185400.00", "176900.00"),
    _c("1.1.02", "Inversiones temporales", "Activo corriente", "Inversiones", "120000.00", "120000.00"),
    _c("1.1.03", "Cuentas por cobrar clientes", "Activo corriente", "Cuentas por cobrar", "812300.00", "690500.00"),
    _c("1.1.04", "(-) Provisión para cuentas incobrables", "Activo corriente", "Cuentas por cobrar", "-48700.00", "-45900.00"),
    _c("1.1.05", "Inventarios de mercadería", "Activo corriente", "Inventarios", "956800.00", "655400.00"),
    _c("1.1.06", "Crédito tributario IVA y renta", "Activo corriente", "Impuestos", "64200.00", "60100.00"),
    _c("1.1.07", "Anticipos a empleados", "Activo corriente", "Otros activos", "12300.00", "11900.00"),
    _c("1.2.01", "Propiedad, planta y equipo", "Activo no corriente", "Propiedad, planta y equipo", "1380000.00", "1310000.00"),
    _c("1.2.02", "(-) Depreciación acumulada", "Activo no corriente", "Propiedad, planta y equipo", "-412600.00", "-380900.00"),
    _c("1.2.03", "Activos por derecho de uso", "Activo no corriente", "Arrendamientos", "96000.00", "102000.00"),
    _c("1.2.04", "Software y licencias", "Activo no corriente", "Activos intangibles", "38500.00", "41300.00"),
    _c("2.1.01", "Proveedores locales", "Pasivo corriente", "Proveedores y cuentas por pagar", "604300.00", "561200.00"),
    _c("2.1.02", "Obligaciones bancarias de corto plazo", "Pasivo corriente", "Préstamos y obligaciones financieras", "250000.00", "180000.00"),
    _c("2.1.03", "Impuestos por pagar", "Pasivo corriente", "Impuestos", "71400.00", "66900.00"),
    _c("2.1.04", "Beneficios sociales por pagar", "Pasivo corriente", "Beneficios a empleados y nómina", "88900.00", "83600.00"),
    _c("2.1.05", "Pasivo por arrendamiento corriente", "Pasivo corriente", "Arrendamientos", "34100.00", "32000.00"),
    _c("2.2.01", "Obligaciones bancarias de largo plazo", "Pasivo no corriente", "Préstamos y obligaciones financieras", "420000.00", "440000.00"),
    _c("2.2.02", "Jubilación patronal y desahucio", "Pasivo no corriente", "Beneficios a empleados y nómina", "146200.00", "137800.00"),
    _c("2.2.03", "Pasivo por arrendamiento no corriente", "Pasivo no corriente", "Arrendamientos", "64800.00", "69900.00"),
    _c("3.1.01", "Capital social", "Patrimonio", "Patrimonio", "700000.00", "700000.00"),
    _c("3.1.02", "Reserva legal", "Patrimonio", "Patrimonio", "96400.00", "78600.00"),
    _c("3.1.03", "Resultados acumulados", "Patrimonio", "Patrimonio", "360450.00", "94750.00"),
    _c("3.1.04", "Resultado del ejercicio", "Patrimonio", "Patrimonio", "367650.00", "296550.00"),
    _c("4.1.01", "Ventas netas", "Ingresos", "Ingresos", "4860500.00", "4215300.00"),
    _c("4.2.01", "Otros ingresos", "Otros ingresos", "Ingresos", "18400.00", "17200.00"),
    _c("5.1.01", "Costo de ventas", "Costos", "Costos y gastos", "3402300.00", "2908600.00"),
    _c("5.2.01", "Sueldos y beneficios sociales", "Gastos", "Beneficios a empleados y nómina", "468900.00", "441300.00"),
    _c("5.2.02", "Gastos de administración y ventas", "Gastos", "Costos y gastos", "391700.00", "368900.00"),
    _c("5.2.03", "Depreciaciones y amortizaciones", "Gastos", "Propiedad, planta y equipo", "67500.00", "63100.00"),
    _c("5.3.01", "Gastos financieros", "Otros gastos", "Préstamos y obligaciones financieras", "58300.00", "55200.00"),
    _c("6.1.01", "Impuesto a la renta", "Impuesto a la renta", "Impuestos", "122550.00", "98850.00"),
]
_FACTORES_EJ = [
    _f("F-01", "¿Existen metas de ventas o bonos de la gerencia ligados a resultados?", "NIA 240", "Ingresos", "Sí",
       "Bono anual del gerente comercial sobre las ventas del año"),
    _f("F-02", "¿Hubo cambios en el sistema contable o ERP durante el ejercicio?", "NIA 315", "", "Sí", "Migración del ERP en julio"),
    _f("F-03", "¿Hay transacciones con partes relacionadas fuera del curso normal del negocio?", "NIA 550", "Cuentas por cobrar", "No"),
    _f("F-04", "¿Hay litigios, reclamos o sanciones de autoridades (SRI, IESS, Superintendencia)?", "NIA 250", "Provisiones y contingencias", "No"),
    _f("F-05", "¿La entidad tiene pérdidas recurrentes, capital de trabajo negativo o deudas vencidas?", "NIA 570", "", "No"),
    _f("F-06", "¿Se identificaron inventarios obsoletos o de lenta rotación?", "NIA 315", "Inventarios", "Sí",
       "Mercadería de la temporada anterior sin rotación"),
    _f("F-07", "¿Hubo incumplimiento de condiciones (covenants) de los préstamos?", "NIA 570", "Préstamos y obligaciones financieras", "No"),
    _f("F-08", "¿La administración cambió políticas o estimaciones contables significativas?", "NIA 315", "", "No"),
    _f("F-09", "¿Existe concentración de ventas o de cartera en pocos clientes?", "NIA 315", "Cuentas por cobrar", "Sí",
       "Tres clientes concentran el 48 % de la cartera"),
    _f("F-10", "¿Hubo denuncias o sospechas de fraude en el ejercicio?", "NIA 240", "", "No"),
    _f("F-11", "¿Se registraron operaciones inusuales cerca del cierre?", "NIA 240", "Ingresos", "No"),
    _f("F-12", "¿Quedan deficiencias de control del año anterior sin corregir?", "NIA 265", "Caja y bancos", "Sí",
       "Conciliaciones bancarias sin firma de revisión"),
]

# Ejemplo de control (a mano): ingresos 4.860.500,00 × 1 % = materialidad global 48.605,00; ejecución 65 % = 31.593,25;
# umbral claramente insignificante 5 % = 2.430,25. Inventarios sube 301.400,00 (46,0 %): variación inusual. Activos
# totales 3.204.200,00 = pasivos 1.679.700,00 + patrimonio 1.524.500,00 (cuadra). Utilidad antes de impuestos 490.200,00.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"baseMaterialidad": "Ingresos", "pctBase": 1, "pctEjecucion": 65, "pctTrivial": 5, "umbralVarPct": 10,
                   "fechaPreliminar": "2025-10-15", "fechaFinal": "2026-01-20", "fechaInforme": "2026-03-31",
                   "socio": "Socio del encargo", "gerente": "Gerente de auditoría", "expertos": "Actuario para jubilación patronal"},
    "datasets": {"estados": _ESTADOS_EJ, "factores": _FACTORES_EJ},
}

# Escenario de pérdida: la utilidad es negativa, la base elegida no sirve y aparecen indicios NIA 570; NIIF para las PYMES.
# Costo de ventas +700.000,00 → utilidad antes de impuestos −209.800,00 (sin impuesto); el resultado del ejercicio
# baja a −209.800,00 y los proveedores suben 577.450,00 para que el balance siga cuadrando.
_CAMBIOS_PERDIDA = {"5.1.01": "4102300.00", "6.1.01": "0.00", "3.1.04": "-209800.00", "2.1.01": "1181750.00"}
_ESTADOS_PERDIDA = [{**x, "saldo_actual": _CAMBIOS_PERDIDA.get(x["id"], x["saldo_actual"])} for x in _ESTADOS_EJ]
ESCENARIOS = [
    ("base", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("perdida_pymes", {"estados": _ESTADOS_PERDIDA, "factores": _FACTORES_EJ},
     {"baseMaterialidad": "Utilidad antes de impuestos", "pctBase": 5, "pctEjecucion": 50, "pctTrivial": 5, "encargoInicial": "Sí",
      "_marco": MARCO_PYMES}, "2025-12-31"),
]
