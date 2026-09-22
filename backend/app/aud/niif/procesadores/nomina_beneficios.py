"""Beneficios sociales y nómina: recálculo de nómina, aportes IESS, décimo tercero, décimo cuarto, vacaciones,
fondo de reserva, conciliación nómina–mayor y beneficios post-empleo (jubilación patronal y desahucio) con el
informe actuarial.

Especificación del socio: MÓDULO 14 (PAY-01 a PAY-20). Norma:
- NIIF completas, NIC 19: beneficios a corto plazo (párr. 11–24), ausencias remuneradas acumulativas —vacaciones—
  (13–18); post-empleo de beneficio definido (55–152) medido con la unidad de crédito proyectada (67) según el
  informe actuarial; componentes del costo (120) y nuevas mediciones en otro resultado integral (120 c, 127–130).
- NIIF para las PYMES 2015 y 2025, Sección 28: corto plazo (28.3–28.8), post-empleo (28.14–28.28), simplificaciones
  si el cálculo supone costo o esfuerzo desproporcionado (28.19) y ganancias/pérdidas actuariales en resultados u
  ORI según la política elegida (28.24).
  Ruta: en NIIF completas las nuevas mediciones van a ORI; en PYMES a donde diga el parámetro «actuarialesEn».
- Ecuador (Código del Trabajo y Ley de Seguridad Social): todas las tasas y el SBU son parámetros «vigente al corte;
  VERIFICAR».

Convenciones del cálculo (iguales en Python y en el Excel):
- Días trabajados en el ejercicio (1-ene al corte) en base comercial 30/360: DAYS360(desde, hasta + 1, TRUE).
- Sueldo del período = sueldo mensual × días ÷ 30 (ponytail: sueldo constante en el año; si hubo aumentos, cargar
  el sueldo vigente y revisar la diferencia de remuneración).
- Remuneración diaria = bruto recalculado ÷ días trabajados (equivale a 1/360 del año: vacaciones = 1/24).
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja,
    m, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "nomina_beneficios 1.0"
RUBRO = "NOMINA"

SIERRA, COSTA = "Sierra/Oriente", "Costa/Galápagos"
ORI, RESULTADOS = "ORI", "Resultados"

_EMPLEADOS = [
    campo("id", "Cédula o código del empleado", alias=("cedula", "cédula", "codigo", "código", "identificacion", "empleado"), ejemplo="1712345678"),
    campo("nombre", "Nombre", alias=("nombres", "apellidos y nombres", "trabajador"), ejemplo="Ana Pérez"),
    campo("fecha_ingreso", "Fecha de ingreso", "date", alias=("ingreso", "fecha ingreso", "fecha de entrada"), ejemplo="2015-03-01"),
    campo("fecha_salida", "Fecha de salida", "date", False, ("salida", "fecha salida", "fecha de baja", "fecha de terminacion"), ""),
    campo("region", "Región (Sierra/Oriente o Costa/Galápagos)", requerido=False, alias=("region", "región", "zona"), ejemplo="Sierra/Oriente"),
    campo("sueldo_mensual", "Sueldo mensual", "number", alias=("sueldo", "sueldo mensual", "salario", "remuneracion mensual"), ejemplo="1200"),
    campo("horas_50", "Horas suplementarias (50 %) del año", "number", False, ("horas 50", "horas suplementarias", "he 50"), "20"),
    campo("horas_100", "Horas extraordinarias (100 %) del año", "number", False, ("horas 100", "horas extraordinarias", "he 100"), "10"),
    campo("horas_extras", "Valor de horas extras del año (registrado)", "number", False, ("horas extras", "valor horas extras", "sobretiempo"), "250"),
    campo("comisiones", "Comisiones y bonos del año", "number", False, ("comisiones", "bonos", "bonificaciones", "comisiones y bonos"), "0"),
    campo("remuneracion_anual", "Remuneración total anual registrada (materia gravada IESS)", "number",
          alias=("remuneracion anual", "total ingresos", "total remuneracion", "materia gravada"), ejemplo="14650"),
    campo("otras_deducciones", "Otras deducciones del año (préstamos, IR retenido…)", "number", False, ("otras deducciones", "descuentos", "deducciones"), "300"),
    campo("neto_pagado", "Neto pagado en el año", "number", False, ("neto pagado", "liquido a recibir", "neto a recibir", "neto"), "12965.58"),
    campo("base_iess_planilla", "Base de aportación según planillas IESS", "number", False, ("base iess", "base planilla", "base de aportacion"), "14650"),
    campo("aporte_personal", "Aporte personal IESS registrado", "number", False, ("aporte personal", "aporte individual", "iess personal"), "1384.43"),
    campo("aporte_patronal", "Aporte patronal IESS registrado (con IECE y SECAP)", "number", False, ("aporte patronal", "iess patronal"), "1779.98"),
    campo("mensualiza_d13", "Décimo tercero mensualizado (Sí/No)", requerido=False, alias=("mensualiza decimo tercero", "d13 mensual"), ejemplo="No"),
    campo("mensualiza_d14", "Décimo cuarto mensualizado (Sí/No)", requerido=False, alias=("mensualiza decimo cuarto", "d14 mensual"), ejemplo="No"),
    campo("d13_provisionado", "Décimo tercero provisionado al corte", "number", False, ("decimo tercero", "provision decimo tercero", "d13"), "101.74"),
    campo("d14_provisionado", "Décimo cuarto provisionado al corte", "number", False, ("decimo cuarto", "provision decimo cuarto", "d14"), "195.83"),
    campo("vac_saldo_inicial", "Saldo inicial de días de vacaciones", "number", False, ("saldo inicial vacaciones", "dias pendientes inicio"), "10"),
    campo("vac_gozados", "Días de vacaciones gozados en el año", "number", False, ("dias gozados", "vacaciones gozadas"), "15"),
    campo("vacaciones_provisionadas", "Vacaciones provisionadas al corte", "number", False, ("provision vacaciones", "vacaciones por pagar"), "610.42"),
    campo("fondo_reserva", "Fondo de reserva pagado o depositado en el año", "number", False, ("fondo de reserva", "fondos de reserva"), "1220.35"),
    campo("en_estudio", "Incluido en el estudio actuarial (Sí/No)", requerido=False, alias=("estudio actuarial", "en estudio", "censo actuarial"), ejemplo="Sí"),
]
_ACTUARIAL = [
    campo("id", "Código del plan", alias=("plan", "codigo", "código"), ejemplo="JUB"),
    campo("tipo", "Tipo (Jubilación patronal / Desahucio)", alias=("tipo", "beneficio", "tipo de beneficio"), ejemplo="Jubilación patronal"),
    campo("dbo_inicial", "Obligación (DBO) inicial", "number", alias=("dbo inicial", "saldo inicial", "obligacion inicial"), ejemplo="85000"),
    campo("costo_servicio", "Costo del servicio del período", "number", alias=("costo laboral", "costo del servicio", "costo servicio actual"), ejemplo="9500"),
    campo("costo_interes", "Costo por intereses", "number", alias=("costo financiero", "interes", "costo por intereses"), ejemplo="6800"),
    campo("costo_servicios_pasados", "Costo de servicios pasados (modificaciones)", "number", False, ("servicios pasados", "modificaciones"), "0"),
    campo("nuevas_mediciones", "Nuevas mediciones: pérdida (+) / ganancia (−) actuarial", "number",
          alias=("perdida actuarial", "ganancia actuarial", "nuevas mediciones", "ori actuarial"), ejemplo="3200"),
    campo("beneficios_pagados", "Beneficios pagados", "number", alias=("beneficios pagados", "pagos", "pagos del periodo"), ejemplo="2500"),
    campo("dbo_final", "DBO final según el informe actuarial", "number", alias=("dbo final", "saldo final", "obligacion final"), ejemplo="102000"),
    campo("provision_registrada", "Provisión registrada al cierre", "number", alias=("provision registrada", "saldo contable", "provision"), ejemplo="95000"),
    campo("remediciones_en", "Nuevas mediciones registradas en (ORI/Resultados)", requerido=False,
          alias=("registrado en", "remediciones en", "contrapartida"), ejemplo="ORI"),
    campo("empleados_estudio", "Empleados incluidos en el estudio", "number", False, ("empleados", "censo", "numero de empleados"), "6"),
    campo("tasa_descuento", "Tasa de descuento (%)", "number", False, ("tasa de descuento", "tasa descuento"), "7.5"),
    campo("incremento_salarial", "Incremento salarial (%)", "number", False, ("incremento salarial", "tasa de incremento"), "2.5"),
    campo("fecha_informe", "Fecha del informe actuarial", "date", False, ("fecha informe", "fecha del estudio"), "2026-01-20"),
]
CAMPOS = {"empleados": _EMPLEADOS, "actuarial": _ACTUARIAL}
TIPOS = {"empleados": "empleados", "actuarial": "actuarial"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "empleados"
CONTROL = "remuneracion_anual"
TOTAL_EJEMPLO = "ajustePasivos"

_MAYORES = ("mayorGastoNomina", "mayorAportePatronal", "mayorD13", "mayorD14", "mayorVacaciones", "mayorFondoReserva", "mayorProvisionActuarial")
PARAMETROS = {
    "sbu": 470, "aportePersonal": 9.45, "aportePatronal": 11.15, "aporteIece": 0.5, "aporteSecap": 0.5, "fondoReserva": 8.33,
    "diasVacaciones": 15, "aniosVacacionAdicional": 5, "maxDiasAdicionales": 15, "horasMes": 240,
    "recargoSuplementarias": 50, "recargoExtraordinarias": 100, "desahucioPct": 25,
    "regionPorDefecto": SIERRA, "mesInicioD13": 12, "mesInicioD14Sierra": 8, "mesInicioD14Costa": 3,
    "actuarialesEn": ORI, "tolerancia": 1, **{k: None for k in _MAYORES},
}
PARAM_NEGATIVOS = ()
_V = " (vigente al corte; VERIFICAR)"
ETIQUETAS_PARAM = {
    "sbu": "Salario básico unificado (USD)" + _V,
    "aportePersonal": "Aporte personal IESS (%)" + _V,
    "aportePatronal": "Aporte patronal IESS (%)" + _V,
    "aporteIece": "IECE (%)" + _V,
    "aporteSecap": "SECAP (%)" + _V,
    "fondoReserva": "Fondo de reserva (% de la remuneración, CT art. 196)" + _V,
    "diasVacaciones": "Días de vacaciones por año (CT art. 69)" + _V,
    "aniosVacacionAdicional": "Años tras los cuales se gana un día adicional por año (CT art. 69)" + _V,
    "maxDiasAdicionales": "Máximo de días adicionales de vacaciones (CT art. 69)" + _V,
    "horasMes": "Horas del mes para el valor hora (CT art. 55)" + _V,
    "recargoSuplementarias": "Recargo horas suplementarias (%)" + _V,
    "recargoExtraordinarias": "Recargo horas extraordinarias (%)" + _V,
    "desahucioPct": "Desahucio: % de la última remuneración por año (CT art. 185)" + _V,
    "regionPorDefecto": "Región por defecto para el décimo cuarto (Sierra/Oriente o Costa/Galápagos)",
    "mesInicioD13": "Mes de inicio del período del décimo tercero (dic = 12)" + _V,
    "mesInicioD14Sierra": "Mes de inicio del décimo cuarto Sierra/Oriente (ago = 8)" + _V,
    "mesInicioD14Costa": "Mes de inicio del décimo cuarto Costa/Galápagos (mar = 3)" + _V,
    "actuarialesEn": "PYMES: ganancias/pérdidas actuariales en (Resultados/ORI), política 28.24",
    "tolerancia": "Tolerancia de diferencias (importe)",
    "mayorGastoNomina": "Mayor: gasto de remuneraciones (sueldos, horas extras, comisiones)",
    "mayorAportePatronal": "Mayor: gasto aporte patronal IESS",
    "mayorD13": "Mayor: décimo tercero por pagar",
    "mayorD14": "Mayor: décimo cuarto por pagar",
    "mayorVacaciones": "Mayor: provisión de vacaciones",
    "mayorFondoReserva": "Mayor: gasto fondo de reserva",
    "mayorProvisionActuarial": "Mayor: provisión jubilación patronal y desahucio",
}


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def _t(v) -> str:
    return str(v if v is not None else "").strip()


def _opc(v):
    return a_num(v) if _t(v) else None


def validar_filas(tipo: str, filas: list) -> dict:
    v = validar_campos(CAMPOS[tipo], filas)
    libres = ("nuevas_mediciones",)
    for f in filas:
        for c in CAMPOS[tipo]:
            k = c["key"]
            if c["type"] == "number" and k not in libres:
                x = _opc(f.get(k))
                if x is not None and x < 0:
                    v["errors"].append({"row": f.get("_row"), "field": k, "message": "Use importes positivos."})
        if tipo == "empleados":
            a, b = fecha(f.get("fecha_ingreso")), fecha(f.get("fecha_salida"))
            if a and b and b < a:
                v["errors"].append({"row": f.get("_row"), "field": "fecha_salida", "message": "La salida no puede ser anterior al ingreso."})
        elif _t(f.get("tipo")) and _tipo(f.get("tipo")) is None:
            v["errors"].append({"row": f.get("_row"), "field": "tipo", "message": "Tipo: Jubilación patronal o Desahucio."})
    v["ok"] = not v["errors"]
    return v


# --- utilidades de fechas (idénticas a las funciones de Excel) --------------------

def d360(a: date, b: date) -> int:
    """DAYS360(a, b, TRUE): método europeo, el día 31 cuenta como 30."""
    return (b.year - a.year) * 360 + (b.month - a.month) * 30 + (min(b.day, 30) - min(a.day, 30))


def edate(d: date, meses: int) -> date:
    y, mm = divmod(d.month - 1 + meses, 12)
    y, mm = d.year + y, mm + 1
    return date(y, mm, min(d.day, monthrange(y, mm)[1]))


def _inicio_mes(corte: date, mes: int) -> date:
    """Último 1.º del mes indicado que no supera el corte (inicio del período del décimo)."""
    return date(corte.year if corte.month >= mes else corte.year - 1, mes, 1)


def _si_no(v) -> bool:
    return _t(v).lower() in ("sí", "si", "s", "x", "yes")


def _region(v, defecto):
    s = _t(v).lower()
    if not s:
        return defecto
    if any(x in s for x in ("costa", "galáp", "galap", "insular")):
        return COSTA
    if any(x in s for x in ("sierra", "oriente", "amaz")):
        return SIERRA
    return None


def _tipo(v):
    s = _t(v).lower()
    return "Jubilación patronal" if "jub" in s else ("Desahucio" if "desah" in s else None)


def _destino(v):
    s = _t(v).lower()
    if not s:
        return ""
    if s == "ori" or "otro resultado" in s:
        return ORI
    if "result" in s or s in ("pyg", "p&g", "pérdidas y ganancias", "perdidas y ganancias"):
        return RESULTADOS
    return None


def _p(p, k):
    v = p.get(k)
    return None if v is None or _t(v) == "" else float(a_num(v))


# --- cálculo -----------------------------------------------------------------

def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    pymes = es_pymes(p)
    q = {k: _p(p, k) for k in ("sbu", "aportePersonal", "aportePatronal", "aporteIece", "aporteSecap", "fondoReserva", "diasVacaciones",
                               "aniosVacacionAdicional", "maxDiasAdicionales", "horasMes", "recargoSuplementarias",
                               "recargoExtraordinarias", "desahucioPct", "mesInicioD13", "mesInicioD14Sierra", "mesInicioD14Costa")}
    for k in ("aportePersonal", "aportePatronal", "aporteIece", "aporteSecap", "fondoReserva", "desahucioPct", "recargoSuplementarias", "recargoExtraordinarias"):
        if q[k] is None or not 0 <= q[k] <= 100:
            raise ValueError(f"{ETIQUETAS_PARAM[k].split(' (vigente')[0]}: porcentaje entre 0 y 100.")
    if q["sbu"] is None or q["sbu"] <= 0 or q["horasMes"] is None or q["horasMes"] <= 0:
        raise ValueError("Indique el SBU y las horas del mes (positivos).")
    for k in ("mesInicioD13", "mesInicioD14Sierra", "mesInicioD14Costa"):
        if q[k] is None or q[k] != int(q[k]) or not 1 <= q[k] <= 12:
            raise ValueError("Los meses de inicio de los décimos deben ser enteros entre 1 y 12.")
    for k in ("diasVacaciones", "aniosVacacionAdicional", "maxDiasAdicionales"):
        if q[k] is None or q[k] < 0:
            raise ValueError("Los días y años de vacaciones deben ser cero o más.")
    tol = _p(p, "tolerancia") or 0.0
    defecto = _region(p.get("regionPorDefecto"), None)
    if defecto is None:
        raise ValueError("Región por defecto: Sierra/Oriente o Costa/Galápagos.")
    politica = _destino(p.get("actuarialesEn"))
    if politica in (None, ""):
        raise ValueError("Ganancias y pérdidas actuariales en: Resultados u ORI.")
    ruta = politica if pymes else ORI      # NIC 19.120 c y 127–130: siempre ORI; PYMES 28.24: política.

    inicio = date(corte_a.year, 1, 1)
    i13 = _inicio_mes(corte_a, int(q["mesInicioD13"]))
    i14 = {SIERRA: _inicio_mes(corte_a, int(q["mesInicioD14Sierra"])), COSTA: _inicio_mes(corte_a, int(q["mesInicioD14Costa"]))}
    pp, tasa_pat = q["aportePersonal"], (q["aportePatronal"] + q["aporteIece"] + q["aporteSecap"]) / 100

    E = []
    for f in datasets.get("empleados") or []:
        if not _t(f.get("id")):
            continue
        g = lambda k: _opc(f.get(k))
        e = {"id": _t(f.get("id")), "nombre": _t(f.get("nombre")), "ing": fecha(f.get("fecha_ingreso")), "sal": fecha(f.get("fecha_salida")),
             "region": _region(f.get("region"), defecto), "sueldo": g("sueldo_mensual"), "h50": g("horas_50"), "h100": g("horas_100"),
             "he_reg": g("horas_extras"), "com": g("comisiones"), "rem": g("remuneracion_anual"), "otras": g("otras_deducciones"),
             "neto_reg": g("neto_pagado"), "base_pl": g("base_iess_planilla"), "ap_reg": g("aporte_personal"), "pat_reg": g("aporte_patronal"),
             "m13": "Sí" if _si_no(f.get("mensualiza_d13")) else "No", "m14": "Sí" if _si_no(f.get("mensualiza_d14")) else "No",
             "d13_reg": g("d13_provisionado"), "d14_reg": g("d14_provisionado"), "vi": g("vac_saldo_inicial"), "vg": g("vac_gozados"),
             "vac_reg": g("vacaciones_provisionadas"), "fr_reg": g("fondo_reserva"), "estudio": _t(f.get("en_estudio")), "_row": f.get("_row")}
        if e["ing"] is None:
            raise ValueError(f"Empleado {e['id']}: indique la fecha de ingreso.")
        if e["sal"] is not None and e["sal"] < e["ing"]:
            raise ValueError(f"Empleado {e['id']}: la salida es anterior al ingreso.")
        if e["sueldo"] is None or e["rem"] is None:
            raise ValueError(f"Empleado {e['id']}: indique el sueldo mensual y la remuneración anual registrada.")
        if e["region"] is None:
            raise ValueError(f"Empleado {e['id']}: región no reconocida (Sierra/Oriente o Costa/Galápagos).")
        if e["estudio"]:
            e["estudio"] = "Sí" if _si_no(e["estudio"]) else "No"
        E.append(e)
    if not E:
        raise ValueError("Cargue el anexo de empleados (una fila por empleado del ejercicio).")

    activos = 0
    for e in E:
        # 05 · tiempo de servicio
        e["desde"], e["hasta"] = max(e["ing"], inicio), min(e["sal"] or corte_a, corte_a)
        e["dias"] = 0 if e["hasta"] < e["desde"] else d360(e["desde"], e["hasta"] + timedelta(1))
        e["activo"] = "Sí" if e["ing"] <= corte_a and (e["sal"] is None or e["sal"] > corte_a) else "No"
        activos += e["activo"] == "Sí"
        e["anios"] = 0 if e["hasta"] < e["ing"] else int(d360(e["ing"], e["hasta"] + timedelta(1)) / 360)
        e["fr_ini"] = edate(e["ing"], 12)
        dfr = max(e["fr_ini"], inicio)
        e["dias_fr"] = 0 if e["hasta"] < dfr else d360(dfr, e["hasta"] + timedelta(1))
        # 06 · recálculo de nómina
        e["sueldo_per"] = e["sueldo"] * e["dias"] / 30
        e["vh"] = e["sueldo"] / q["horasMes"]
        e["he_calc"] = None if e["h50"] is None and e["h100"] is None else \
            e["vh"] * ((e["h50"] or 0) * (1 + q["recargoSuplementarias"] / 100) + (e["h100"] or 0) * (1 + q["recargoExtraordinarias"] / 100))
        e["he"] = e["he_reg"] or 0
        e["he_dif"] = None if e["he_calc"] is None else e["he"] - e["he_calc"]
        e["com0"] = e["com"] or 0
        e["bruto"] = e["sueldo_per"] + e["he"] + e["com0"]
        e["dif_rem"] = e["rem"] - e["bruto"]
        e["pers_b"] = e["bruto"] * pp / 100
        e["otras0"] = e["otras"] or 0
        e["neto"] = e["bruto"] - e["pers_b"] - e["otras0"]
        e["neto_dif"] = None if e["neto_reg"] is None else e["neto_reg"] - e["neto"]
        # 07 · IESS (base = remuneración registrada)
        e["dif_pl"] = None if e["base_pl"] is None else e["base_pl"] - e["rem"]
        e["ap"] = e["rem"] * pp / 100
        e["ap_dif"] = None if e["ap_reg"] is None else e["ap_reg"] - e["ap"]
        e["pat"] = e["rem"] * tasa_pat
        e["pat_dif"] = None if e["pat_reg"] is None else e["pat_reg"] - e["pat"]
        e["diaria"] = 0 if e["dias"] == 0 else e["bruto"] / e["dias"]
        # 08 · décimo tercero (1/12 de lo percibido desde el inicio del período)
        e["d13_dias"] = 0 if e["activo"] == "No" or e["m13"] == "Sí" else d360(max(e["ing"], i13), corte_a + timedelta(1))
        e["d13"] = e["diaria"] * e["d13_dias"] / 12
        e["d13_dif"] = None if e["d13_reg"] is None else e["d13_reg"] - e["d13"]
        # 09 · décimo cuarto (un SBU por año, prorrateado)
        e["d14_ini"] = i14[e["region"]]
        e["d14_dias"] = 0 if e["activo"] == "No" or e["m14"] == "Sí" else d360(max(e["ing"], e["d14_ini"]), corte_a + timedelta(1))
        e["d14"] = q["sbu"] * e["d14_dias"] / 360
        e["d14_dif"] = None if e["d14_reg"] is None else e["d14_reg"] - e["d14"]
        # 10 · vacaciones
        e["dias_anuales"] = q["diasVacaciones"] + min(max(e["anios"] - q["aniosVacacionAdicional"], 0), q["maxDiasAdicionales"])
        e["devengados"] = e["dias_anuales"] * e["dias"] / 360
        e["saldo"] = (e["vi"] or 0) + e["devengados"] - (e["vg"] or 0)
        e["vac"] = 0 if e["activo"] == "No" else max(e["saldo"], 0) * e["diaria"]
        e["vac_dif"] = None if e["vac_reg"] is None else e["vac_reg"] - e["vac"]
        # 11 · fondo de reserva (desde el 13.º mes)
        e["fr"] = 0 if e["dias"] == 0 else e["bruto"] * q["fondoReserva"] / 100 * e["dias_fr"] / e["dias"]
        e["fr_dif"] = None if e["fr_reg"] is None else e["fr_reg"] - e["fr"]
        # 14 · censo y desahucio legal referencial
        e["des_ref"] = e["sueldo"] * q["desahucioPct"] / 100 * e["anios"]

    A = []
    for f in datasets.get("actuarial") or []:
        if not _t(f.get("id")):
            continue
        g = lambda k: _opc(f.get(k))
        a = {"id": _t(f.get("id")), "tipo": _tipo(f.get("tipo")), "ini": g("dbo_inicial"), "sc": g("costo_servicio"), "ic": g("costo_interes"),
             "pc": g("costo_servicios_pasados"), "nm": g("nuevas_mediciones"), "bp": g("beneficios_pagados"), "inf": g("dbo_final"),
             "prov": g("provision_registrada"), "reg_en": _destino(f.get("remediciones_en")), "n_est": g("empleados_estudio"),
             "tasa": g("tasa_descuento"), "inc": g("incremento_salarial"), "fecha": fecha(f.get("fecha_informe")), "_row": f.get("_row")}
        if a["tipo"] is None:
            raise ValueError(f"Plan {a['id']}: tipo Jubilación patronal o Desahucio.")
        if a["reg_en"] is None:
            raise ValueError(f"Plan {a['id']}: nuevas mediciones registradas en ORI o Resultados.")
        if any(a[k] is None for k in ("ini", "sc", "ic", "nm", "bp", "inf", "prov")):
            raise ValueError(f"Plan {a['id']}: indique DBO inicial, costo del servicio, intereses, nuevas mediciones, pagos, DBO final y provisión.")
        a["recalc"] = a["ini"] + a["sc"] + a["ic"] + (a["pc"] or 0) + a["nm"] - a["bp"]
        a["dif_rf"] = a["inf"] - a["recalc"]
        a["dif_prov"] = a["prov"] - a["inf"]
        a["activos"] = activos
        a["dif_censo"] = None if a["n_est"] is None else a["n_est"] - activos
        a["gasto"] = a["sc"] + a["ic"] + (a["pc"] or 0) + (a["nm"] if ruta == RESULTADOS else 0)
        a["ori"] = a["nm"] if ruta == ORI else 0
        a["conforme"] = "Sin dato" if not a["reg_en"] else ("Sí" if a["reg_en"] == ruta else "No")
        A.append(a)

    s = lambda it, k: sum(x[k] or 0 for x in it)
    mayor = {k: _p(p, k) for k in _MAYORES}
    con = [  # concepto, registrado, recalculado, clave del mayor
        ("Remuneraciones (sueldos, horas extras, comisiones)", s(E, "rem"), s(E, "bruto"), "mayorGastoNomina"),
        ("Aporte patronal IESS (con IECE y SECAP)", s(E, "pat_reg"), s(E, "pat"), "mayorAportePatronal"),
        ("Décimo tercero por pagar", s(E, "d13_reg"), s(E, "d13"), "mayorD13"),
        ("Décimo cuarto por pagar", s(E, "d14_reg"), s(E, "d14"), "mayorD14"),
        ("Provisión de vacaciones", s(E, "vac_reg"), s(E, "vac"), "mayorVacaciones"),
        ("Fondo de reserva", s(E, "fr_reg"), s(E, "fr"), "mayorFondoReserva"),
        ("Provisión jubilación patronal y desahucio (recalculado = informe)", s(A, "prov"), s(A, "inf"), "mayorProvisionActuarial"),
    ]
    conc = [{"concepto": c, "reg": r, "rec": x, "clave": k, "mayor": mayor[k], "dif_mayor": None if mayor[k] is None else r - mayor[k],
             "dif_rec": r - x} for c, r, x, k in con]
    aj = [
        ("Décimo tercero", -s(E, "d13_dif"), "Gasto décimo tercero", "Décimo tercero por pagar"),
        ("Décimo cuarto", -s(E, "d14_dif"), "Gasto décimo cuarto", "Décimo cuarto por pagar"),
        ("Vacaciones", -s(E, "vac_dif"), "Gasto vacaciones", "Provisión de vacaciones"),
        ("Fondo de reserva no pagado", -s(E, "fr_dif"), "Gasto fondo de reserva", "Fondo de reserva por pagar"),
        ("Aporte patronal IESS", -s(E, "pat_dif"), "Gasto aporte patronal", "IESS por pagar"),
        ("Jubilación patronal y desahucio (informe − registrada)", -s(A, "dif_prov"),
         "Gasto / ORI (nuevas mediciones)" if ruta == ORI else "Gasto de beneficios post-empleo", "Provisión por beneficios post-empleo"),
    ]
    k = {"remuneracionRegistrada": s(E, "rem"), "remuneracionRecalculada": s(E, "bruto"), "difRemuneracion": s(E, "rem") - s(E, "bruto"),
         "difAportePersonal": s(E, "ap_dif"), "aportePatronalRecalculado": s(E, "pat"), "d13Recalculado": s(E, "d13"),
         "d14Recalculado": s(E, "d14"), "vacacionesRecalculadas": s(E, "vac"), "fondoReservaEsperado": s(E, "fr"),
         "dboInforme": s(A, "inf"), "provisionActuarialRegistrada": s(A, "prov"), "gastoActuarialResultados": s(A, "gasto"),
         "oriActuarial": s(A, "ori"), "desahucioLegalReferencial": sum(e["des_ref"] for e in E if e["activo"] == "Sí"),
         "ajustePasivos": sum(x[1] for x in aj), "difMayorNomina": conc[0]["dif_mayor"], "activos": activos}

    # Problemas.
    pr = []
    for e in E:
        n = f"{e['id']} ({e['nombre']})"
        if abs(e["dif_rem"]) > tol:
            pr.append(problema("RECALCULO_NOMINA", f"{n}: remuneración registrada {m(e['rem'])} ≠ recalculada {m(e['bruto'])} "
                               f"(sueldo {m(e['sueldo'])} × {e['dias']} días ÷ 30 + horas extras + comisiones).", e["dif_rem"]))
        if e["he_dif"] is not None and abs(e["he_dif"]) > tol:
            pr.append(problema("HORAS_EXTRAS", f"{n}: horas extras registradas {m(e['he'])} ≠ recalculadas {m(e['he_calc'])} "
                               "(valor hora = sueldo ÷ horas del mes, con recargo; CT art. 55, VERIFICAR).", e["he_dif"]))
        if e["neto_dif"] is not None and abs(e["neto_dif"]) > tol:
            pr.append(problema("NETO_NOMINA", f"{n}: neto pagado {m(e['neto_reg'])} ≠ neto recalculado {m(e['neto'])}.", e["neto_dif"]))
        if e["dif_pl"] is not None and abs(e["dif_pl"]) > tol:
            pr.append(problema("PLANILLA_IESS", f"{n}: base de las planillas IESS {m(e['base_pl'])} ≠ remuneración de la nómina {m(e['rem'])}.", e["dif_pl"]))
        for key, lab in (("ap_dif", "personal"), ("pat_dif", "patronal")):
            if e[key] is not None and abs(e[key]) > tol:
                rec = e["ap"] if key == "ap_dif" else e["pat"]
                pr.append(problema("APORTE_IESS", f"{n}: aporte {lab} IESS registrado {m(rec + e[key])} ≠ recalculado {m(rec)} "
                                   "sobre la remuneración registrada (Ley de Seguridad Social; tasas VERIFICAR).", e[key]))
        for key, cod, lab, art in (("d13_dif", "DECIMO_TERCERO", "décimo tercero", "CT art. 111"), ("d14_dif", "DECIMO_CUARTO", "décimo cuarto", "CT art. 113")):
            if e[key] is not None and abs(e[key]) > tol:
                rec = e[key[:3]]
                pr.append(problema(cod, f"{n}: {lab} provisionado {m(rec + e[key])} ≠ recalculado {m(rec)} ({art}; NIC 19.11–13 · PYMES 28.3–28.6).", e[key]))
        if e["activo"] == "Sí" and e["vac"] > tol and not e["vac_reg"]:
            pr.append(problema("VACACIONES_NO_PROVISIONADAS", f"{n}: saldo de {e['saldo']:.2f} días de vacaciones por {m(e['vac'])} sin provisión "
                               f"{'(no informada)' if e['vac_reg'] is None else '(registrada en cero)'}: ausencia remunerada acumulativa "
                               "(NIC 19.13–16 · PYMES 28.6).", e["vac"]))
        elif e["vac_dif"] is not None and abs(e["vac_dif"]) > tol:
            pr.append(problema("VACACIONES_DIFERENCIA", f"{n}: vacaciones provisionadas {m(e['vac_reg'])} ≠ recalculadas {m(e['vac'])} "
                               f"({e['saldo']:.2f} días × {m(e['diaria'])}).", e["vac_dif"]))
        if e["activo"] == "Sí" and e["saldo"] < -0.005:
            pr.append(problema("VACACIONES_SALDO_NEGATIVO", f"{n}: gozó {abs(e['saldo']):.2f} días más de los devengados; verifique anticipos de vacaciones.", 0))
        if e["activo"] == "Sí" and (e["vi"] is None or e["vg"] is None):
            pr.append(problema("VACACIONES_SIN_DATOS", f"{n}: falta el saldo inicial o los días gozados; se tomaron como cero y el saldo puede estar mal.", 0))
        if e["fr_dif"] is not None and e["fr_dif"] < -tol:
            pr.append(problema("FONDO_RESERVA_NO_PAGADO", f"{n}: fondo de reserva pagado {m(e['fr_reg'])} < debido {m(e['fr'])} "
                               f"({e['dias_fr']} días con derecho desde el 13.º mes; CT art. 196).", -e["fr_dif"]))
        elif e["fr_dif"] is not None and e["fr_dif"] > tol:
            pr.append(problema("FONDO_RESERVA_EXCESO", f"{n}: fondo de reserva pagado {m(e['fr_reg'])} > debido {m(e['fr'])}; "
                               "revise el derecho (desde el 13.º mes).", e["fr_dif"]))
        falt = [lab for key, lab, val in (("d13_reg", "décimo tercero", e["d13"]), ("d14_reg", "décimo cuarto", e["d14"]),
                                          ("ap_reg", "aporte personal", e["ap"]), ("pat_reg", "aporte patronal", e["pat"]),
                                          ("fr_reg", "fondo de reserva", e["fr"])) if e[key] is None and val > 0.005]
        if falt:
            pr.append(problema("REGISTRO_NO_INFORMADO", f"{n}: no se informó el valor registrado de {', '.join(falt)}; la diferencia queda en blanco (M22).", 0))
        if e["activo"] == "Sí" and e["estudio"] == "No":
            pr.append(problema("EMPLEADO_SIN_ESTUDIO", f"{n}: activo al corte y fuera del estudio actuarial; la jubilación patronal y el desahucio "
                               "quedan subestimados (NIC 19.67 · PYMES 28.18).", e["des_ref"]))

    for a in A:
        if abs(a["dif_rf"]) > tol:
            pr.append(problema("DBO_ROLLFORWARD", f"Plan {a['id']} ({a['tipo']}): el DBO final del informe {m(a['inf'])} no cuadra con inicial + costo del servicio "
                               f"+ intereses + servicios pasados + nuevas mediciones − pagos = {m(a['recalc'])}; pida la conciliación al actuario.", a["dif_rf"]))
        if abs(a["dif_prov"]) > tol:
            pr.append(problema("PROVISION_ACTUARIAL", f"Plan {a['id']} ({a['tipo']}): provisión registrada {m(a['prov'])} ≠ DBO del informe actuarial {m(a['inf'])}.",
                               a["dif_prov"]))
        if a["conforme"] == "No" and not pymes:
            pr.append(problema("NUEVAS_MEDICIONES_EN_RESULTADOS", f"Plan {a['id']}: las nuevas mediciones ({m(a['nm'])}) se registraron en resultados; en NIIF "
                               "completas van a otro resultado integral y no se reclasifican (NIC 19.120 c, 122, 127–130; VERIFICAR).", a["nm"]))
        elif a["conforme"] == "No":
            pr.append(problema("POLITICA_ACTUARIAL_PYMES", f"Plan {a['id']}: las ganancias/pérdidas actuariales ({m(a['nm'])}) se registraron en {a['reg_en']} y la "
                               f"política elegida es {ruta} (Sección 28.24: aplicar la misma política a todos los planes).", a["nm"]))
        if a["dif_censo"] is not None and abs(a["dif_censo"]) > 0:
            pr.append(problema("CENSO_ACTUARIAL", f"Plan {a['id']}: el estudio incluye {a['n_est']:g} empleados y hay {activos} activos al corte en la nómina.", 0))
        if a["tasa"] is None:
            pr.append(problema("SUPUESTOS_ACTUARIALES", f"Plan {a['id']}: sin tasa de descuento informada; evalúe los supuestos (NIC 19.75–98, tasa 83 · "
                               "PYMES 28.17; NIA 540).", 0))
    if activos and not A:
        pr.append(problema("SIN_ESTUDIO_ACTUARIAL", f"{activos} empleados activos y ningún informe actuarial: jubilación patronal y desahucio sin medir "
                           "(NIC 19.67; en PYMES evalúe la simplificación de 28.19 solo si hay costo o esfuerzo desproporcionado).", k["desahucioLegalReferencial"]))
    elif A:
        faltan = {"Jubilación patronal", "Desahucio"} - {a["tipo"] for a in A}
        if faltan:
            pr.append(problema("PLAN_SIN_ESTUDIO", f"El informe actuarial no incluye: {', '.join(sorted(faltan))}.", 0))
    for c in conc:
        if c["dif_mayor"] is not None and abs(c["dif_mayor"]) > tol:
            pr.append(problema("CONCILIACION_MAYOR", f"{c['concepto']}: detalle {m(c['reg'])} ≠ mayor {m(c['mayor'])}.", c["dif_mayor"]))
    if all(v is None for v in mayor.values()):
        pr.append(problema("SIN_MAYOR", "Ingrese los saldos del mayor (gasto de nómina y pasivos laborales) para conciliar nómina y contabilidad.", 0))

    totales, etiquetas = {}, {}
    for key, lab in (
        ("remuneracionRegistrada", "Remuneraciones registradas en la nómina"), ("remuneracionRecalculada", "Remuneraciones recalculadas"),
        ("difRemuneracion", "Diferencia registrada − recalculada"), ("difMayorNomina", "Diferencia nómina − mayor (remuneraciones)"),
        ("difAportePersonal", "Diferencia aporte personal IESS (registrado − recalculado)"),
        ("aportePatronalRecalculado", "Aporte patronal IESS recalculado"), ("d13Recalculado", "Décimo tercero por pagar recalculado"),
        ("d14Recalculado", "Décimo cuarto por pagar recalculado"), ("vacacionesRecalculadas", "Provisión de vacaciones recalculada"),
        ("fondoReservaEsperado", "Fondo de reserva debido en el ejercicio"), ("dboInforme", "Obligación post-empleo según informe actuarial"),
        ("provisionActuarialRegistrada", "Provisión post-empleo registrada"), ("gastoActuarialResultados", "Gasto post-empleo en resultados"),
        ("oriActuarial", "Nuevas mediciones en ORI"), ("desahucioLegalReferencial", "Desahucio legal referencial de los activos (no es el DBO)"),
        ("ajustePasivos", "Ajuste propuesto a pasivos laborales (+ aumenta el pasivo)"),
    ):
        if k[key] is not None:
            totales[key], etiquetas[key] = r2(k[key]), lab

    filas = [{"id": e["id"], "nombre": e["nombre"], "ingreso": e["ing"].isoformat(), "activo": e["activo"], "dias": e["dias"],
              "remuneracion": r2(e["rem"]), "brutoRecalculado": r2(e["bruto"]), "d13": r2(e["d13"]), "d14": r2(e["d14"]),
              "vacaciones": r2(e["vac"]), "fondoReserva": r2(e["fr"]), "_row": e["_row"]} for e in E]
    limpia = lambda it: [{kk: (v.isoformat() if hasattr(v, "isoformat") else v) for kk, v in x.items()} for x in it]
    detalle = {"corte": corte_a.isoformat(), "inicio": inicio.isoformat(), "i13": i13.isoformat(), "i14s": i14[SIERRA].isoformat(),
               "i14c": i14[COSTA].isoformat(), "marco": MARCO_PYMES if pymes else MARCO_COMPLETAS, "pymes": pymes,
               "edicion": edicion_pymes(p) if pymes else "", "ruta": ruta, "empleados": limpia(E), "actuarial": limpia(A),
               "conciliacion": conc, "ajustes": aj, "kpi": k, "parametros": p}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "ajustePasivos",
            "exceptions": pr, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Empleados", "Empleados (datos del cliente)"),
    ("04_Actuarial", "Informe actuarial (datos del cliente)"), ("05_Tiempo_servicio", "Tiempo de servicio"),
    ("06_Recalculo_nomina", "Recálculo de nómina: bruto y neto"), ("07_IESS", "Aportes IESS y planillas"),
    ("08_Decimo_tercero", "Décimo tercero"), ("09_Decimo_cuarto", "Décimo cuarto"), ("10_Vacaciones", "Vacaciones"),
    ("11_Fondo_reserva", "Fondo de reserva"), ("12_DBO_actuarial", "Jubilación patronal y desahucio: DBO"),
    ("13_Resultados_ORI", "Costo post-empleo: resultados y ORI"), ("14_Censo_actuarial", "Censo actuarial y desahucio legal"),
    ("15_Conciliacion_GL", "Conciliación nómina–mayor"), ("16_Ajustes", "Ajustes propuestos"), ("17_Problemas", "Problemas encontrados"),
]
P = ref("02_Parametros")
EMP, ACT, TS, NOM, IE, D13, D14, VAC, FR, DBO, ORIH, CEN, CG, AJ = (ref(n) for n, _ in CEDULAS[2:16])
_PAR = ["corte", "inicio", "marco", "edicion", "ruta", "sbu", "aportePersonal", "aportePatronal", "aporteIece", "aporteSecap", "fondoReserva",
        "diasVacaciones", "aniosVacacionAdicional", "maxDiasAdicionales", "horasMes", "recargoSuplementarias", "recargoExtraordinarias",
        "desahucioPct", "regionPorDefecto", "mesInicioD13", "i13", "mesInicioD14Sierra", "i14s", "mesInicioD14Costa", "i14c",
        "actuarialesEn", "tolerancia", *_MAYORES]
PAR = {k: f"{P}$B${FILA0 + i}" for i, k in enumerate(_PAR)}


def _rng(h: str, col: str, n: int) -> str:
    return f"{h}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _si(celda: str) -> str:
    return f'IF({celda}="","",{celda})'


def _cero(celda: str) -> str:
    return f'IF({celda}="",0,{celda})'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, Em, Ac, k = d["parametros"], d["empleados"], d["actuarial"], d["kpi"]
    n, na = len(Em), len(Ac)
    fin = lambda nn: FILA0 + nn - 1
    pv = lambda kk: None if p.get(kk) in (None, "") else float(a_num(p.get(kk)))
    c = PAR["corte"]
    V = " — vigente al corte; VERIFICAR"

    parametros = [
        ["Corte del ejercicio", d["corte"], "Ficha del encargo"],
        ["Inicio del ejercicio", d["inicio"], "1 de enero del año del corte"],
        ["Marco contable", d["marco"], "Enruta el destino de las nuevas mediciones actuariales"],
        ["Edición PYMES", d["edicion"], "Sección 28 sin cambios de fondo entre 2015 y 2025 para esta prueba (VERIFICAR)"],
        ["Nuevas mediciones van a", d["ruta"], "NIC 19.120 c y 127–130: ORI" if not d["pymes"] else "Sección 28.24: política elegida (parámetro)"],
        ["SBU (USD)", pv("sbu"), "Acuerdo ministerial del año" + V],
        ["Aporte personal IESS (%)", pv("aportePersonal"), "Ley de Seguridad Social / resoluciones IESS" + V],
        ["Aporte patronal IESS (%)", pv("aportePatronal"), "Ley de Seguridad Social" + V],
        ["IECE (%)", pv("aporteIece"), V[3:]],
        ["SECAP (%)", pv("aporteSecap"), V[3:]],
        ["Fondo de reserva (%)", pv("fondoReserva"), "CT art. 196" + V],
        ["Días de vacaciones por año", pv("diasVacaciones"), "CT art. 69" + V],
        ["Años para día adicional", pv("aniosVacacionAdicional"), "CT art. 69" + V],
        ["Máximo días adicionales", pv("maxDiasAdicionales"), "CT art. 69" + V],
        ["Horas del mes (valor hora)", pv("horasMes"), "CT art. 55" + V],
        ["Recargo suplementarias (%)", pv("recargoSuplementarias"), "CT art. 55" + V],
        ["Recargo extraordinarias (%)", pv("recargoExtraordinarias"), "CT art. 55" + V],
        ["Desahucio (% por año)", pv("desahucioPct"), "CT art. 185" + V],
        ["Región por defecto", p.get("regionPorDefecto"), "Para empleados sin región"],
        ["Mes de inicio décimo tercero", pv("mesInicioD13"), "CT art. 111 (dic–nov)" + V],
        ["Inicio del período décimo tercero", d["i13"], "Derivado del corte y del mes de inicio"],
        ["Mes de inicio décimo cuarto Sierra/Oriente", pv("mesInicioD14Sierra"), "CT art. 113 (ago–jul)" + V],
        ["Inicio del período décimo cuarto Sierra/Oriente", d["i14s"], "Derivado del corte y del mes de inicio"],
        ["Mes de inicio décimo cuarto Costa/Galápagos", pv("mesInicioD14Costa"), "CT art. 113 (mar–feb)" + V],
        ["Inicio del período décimo cuarto Costa/Galápagos", d["i14c"], "Derivado del corte y del mes de inicio"],
        ["PYMES: actuariales en", p.get("actuarialesEn"), "Política contable (Sección 28.24); en NIIF completas no aplica"],
        ["Tolerancia (importe)", pv("tolerancia"), "Materialidad de ejecución"],
        *[[ETIQUETAS_PARAM[kk], pv(kk), "Mayor contable"] for kk in _MAYORES],
    ]

    emp = [[e["id"], e["nombre"], e["ing"], e["sal"], e["region"], e["sueldo"], e["h50"], e["h100"], e["he_reg"], e["com"], e["rem"],
            e["otras"], e["neto_reg"], e["base_pl"], e["ap_reg"], e["pat_reg"], e["m13"], e["m14"], e["d13_reg"], e["d14_reg"], e["vi"],
            e["vg"], e["vac_reg"], e["fr_reg"], e["estudio"]] for e in Em]
    act = [[a["id"], a["tipo"], a["ini"], a["sc"], a["ic"], a["pc"], a["nm"], a["bp"], a["inf"], a["prov"], a["reg_en"], a["n_est"],
            a["tasa"], a["inc"], a["fecha"]] for a in Ac]

    ts, nom, ies, t13, t14, vac, frs = [], [], [], [], [], [], []
    for i, e in enumerate(Em):
        r = FILA0 + i
        X = lambda col: f"{EMP}{col}{r}"
        HT = f'MIN(IF({X("D")}="",{c},{X("D")}),{c})'
        DS = f'MAX({X("C")},{PAR["inicio"]})'
        DF = f'MAX(EDATE({X("C")},12),{PAR["inicio"]})'
        ts.append([e["id"], e["desde"], e["hasta"], fx(f"IF({HT}<{DS},0,DAYS360({DS},{HT}+1,TRUE))", e["dias"]),
                   fx(f'IF(AND({X("C")}<={c},OR({X("D")}="",{X("D")}>{c})),"Sí","No")', e["activo"]),
                   fx(f'IF({HT}<{X("C")},0,INT(DAYS360({X("C")},{HT}+1,TRUE)/360))', e["anios"]), e["fr_ini"],
                   fx(f"IF({HT}<{DF},0,DAYS360({DF},{HT}+1,TRUE))", e["dias_fr"])])
        nom.append([
            e["id"], fx(X("F"), e["sueldo"]), fx(f"{TS}D{r}", e["dias"]), fx(f"B{r}*C{r}/30", e["sueldo_per"]),
            fx(f"B{r}/{PAR['horasMes']}", e["vh"]), fx(_si(X("G")), e["h50"]), fx(_si(X("H")), e["h100"]),
            fx(f'IF(AND(F{r}="",G{r}=""),"",E{r}*(IF(F{r}="",0,F{r})*(1+{PAR["recargoSuplementarias"]}/100)'
               f'+IF(G{r}="",0,G{r})*(1+{PAR["recargoExtraordinarias"]}/100)))', e["he_calc"]),
            fx(_cero(X("I")), e["he"]), fx(f'IF(H{r}="","",I{r}-H{r})', e["he_dif"]), fx(_cero(X("J")), e["com0"]),
            fx(f"D{r}+I{r}+K{r}", e["bruto"]), fx(X("K"), e["rem"]), fx(f"M{r}-L{r}", e["dif_rem"]),
            fx(f"L{r}*{PAR['aportePersonal']}/100", e["pers_b"]), fx(_cero(X("L")), e["otras0"]), fx(f"L{r}-O{r}-P{r}", e["neto"]),
            fx(_si(X("M")), e["neto_reg"]), fx(f'IF(R{r}="","",R{r}-Q{r})', e["neto_dif"]),
        ])
        ies.append([
            e["id"], fx(X("K"), e["rem"]), fx(_si(X("N")), e["base_pl"]), fx(f'IF(C{r}="","",C{r}-B{r})', e["dif_pl"]),
            fx(f"B{r}*{PAR['aportePersonal']}/100", e["ap"]), fx(_si(X("O")), e["ap_reg"]), fx(f'IF(F{r}="","",F{r}-E{r})', e["ap_dif"]),
            fx(f"({PAR['aportePatronal']}+{PAR['aporteIece']}+{PAR['aporteSecap']})/100",
               (float(a_num(p["aportePatronal"])) + float(a_num(p["aporteIece"])) + float(a_num(p["aporteSecap"]))) / 100),
            fx(f"B{r}*H{r}", e["pat"]), fx(_si(X("P")), e["pat_reg"]), fx(f'IF(J{r}="","",J{r}-I{r})', e["pat_dif"]),
        ])
        diaria = fx(f"IF({TS}D{r}=0,0,{NOM}L{r}/{TS}D{r})", e["diaria"])
        t13.append([e["id"], fx(f"{TS}E{r}", e["activo"]), e["m13"],
                    fx(f'IF(OR(B{r}="No",C{r}="Sí"),0,DAYS360(MAX({X("C")},{PAR["i13"]}),{c}+1,TRUE))', e["d13_dias"]), diaria,
                    fx(f"E{r}*D{r}/12", e["d13"]), fx(_si(X("S")), e["d13_reg"]), fx(f'IF(G{r}="","",G{r}-F{r})', e["d13_dif"])])
        t14.append([e["id"], fx(f"{TS}E{r}", e["activo"]), e["m14"], e["region"], e["d14_ini"],
                    fx(f'IF(OR(B{r}="No",C{r}="Sí"),0,DAYS360(MAX({X("C")},IF(D{r}="{COSTA}",{PAR["i14c"]},{PAR["i14s"]})),{c}+1,TRUE))', e["d14_dias"]),
                    fx(f"{PAR['sbu']}*F{r}/360", e["d14"]), fx(_si(X("T")), e["d14_reg"]), fx(f'IF(H{r}="","",H{r}-G{r})', e["d14_dif"])])
        vac.append([
            e["id"], fx(f"{TS}E{r}", e["activo"]), fx(f"{TS}F{r}", e["anios"]),
            fx(f"{PAR['diasVacaciones']}+MIN(MAX(C{r}-{PAR['aniosVacacionAdicional']},0),{PAR['maxDiasAdicionales']})", e["dias_anuales"]),
            fx(f"D{r}*{TS}D{r}/360", e["devengados"]), fx(_cero(X("U")), e["vi"] or 0), fx(_cero(X("V")), e["vg"] or 0),
            fx(f"F{r}+E{r}-G{r}", e["saldo"]), fx(f"IF({TS}D{r}=0,0,{NOM}L{r}/{TS}D{r})", e["diaria"]),
            fx(f'IF(B{r}="No",0,MAX(H{r},0)*I{r})', e["vac"]), fx(_si(X("W")), e["vac_reg"]), fx(f'IF(K{r}="","",K{r}-J{r})', e["vac_dif"]),
        ])
        frs.append([e["id"], fx(f"{TS}D{r}", e["dias"]), fx(f"{TS}H{r}", e["dias_fr"]), fx(f"{NOM}L{r}", e["bruto"]),
                    fx(f"IF(B{r}=0,0,D{r}*{PAR['fondoReserva']}/100*C{r}/B{r})", e["fr"]), fx(_si(X("X")), e["fr_reg"]),
                    fx(f'IF(F{r}="","",F{r}-E{r})', e["fr_dif"])])

    dbo, ori = [], []
    for i, a in enumerate(Ac):
        r = FILA0 + i
        X = lambda col: f"{ACT}{col}{r}"
        dbo.append([
            a["id"], a["tipo"], *[fx(X(col), a[kk] or 0) for col, kk in zip("CDEFGH", ("ini", "sc", "ic", "pc", "nm", "bp"))],
            fx(f"C{r}+D{r}+E{r}+F{r}+G{r}-H{r}", a["recalc"]), fx(X("I"), a["inf"]), fx(f"J{r}-I{r}", a["dif_rf"]),
            fx(X("J"), a["prov"]), fx(f"L{r}-J{r}", a["dif_prov"]), fx(f'COUNTIF({_rng(TS, "E", n)},"Sí")', a["activos"]),
            fx(_si(X("L")), a["n_est"]), fx(f'IF(O{r}="","",O{r}-N{r})', a["dif_censo"]),
        ])
        ori.append([
            a["id"], fx(f'{DBO}D{r}+{DBO}E{r}+{DBO}F{r}+IF({PAR["ruta"]}="{RESULTADOS}",{DBO}G{r},0)', a["gasto"]),
            fx(f'IF({PAR["ruta"]}="{ORI}",{DBO}G{r},0)', a["ori"]), fx(PAR["ruta"], d["ruta"]), a["reg_en"],
            fx(f'IF(E{r}="","Sin dato",IF(E{r}=D{r},"Sí","No"))', a["conforme"]),
        ])

    fa = {e["id"]: FILA0 + i for i, e in enumerate(Em)}
    AC = [e for e in Em if e["activo"] == "Sí"]
    cen = []
    for e in AC:
        s_ = fa[e["id"]]
        cen.append([e["id"], e["nombre"], fx(f"{TS}F{s_}", e["anios"]), fx(f"{EMP}F{s_}", e["sueldo"]), e["estudio"],
                    fx(f"{EMP}F{s_}*{PAR['desahucioPct']}/100*{TS}F{s_}", e["des_ref"])])

    # 15 · conciliación: registrado, recalculado, mayor.
    fuentes = [(_rng(EMP, "K", n), _rng(NOM, "L", n)), (_rng(EMP, "P", n), _rng(IE, "I", n)), (_rng(EMP, "S", n), _rng(D13, "F", n)),
               (_rng(EMP, "T", n), _rng(D14, "G", n)), (_rng(EMP, "W", n), _rng(VAC, "J", n)), (_rng(EMP, "X", n), _rng(FR, "E", n)),
               (_rng(ACT, "J", na), _rng(ACT, "I", na))]
    cg = []
    for i, (x, (rr, rc)) in enumerate(zip(d["conciliacion"], fuentes)):
        r = FILA0 + i
        cg.append([x["concepto"], fx(f"SUM({rr})", x["reg"]), fx(f"SUM({rc})", x["rec"]), fx(_si(PAR[x["clave"]]), x["mayor"]),
                   fx(f'IF(D{r}="","",B{r}-D{r})', x["dif_mayor"]), fx(f"B{r}-C{r}", x["dif_rec"])])

    difs = [_rng(D13, "H", n), _rng(D14, "I", n), _rng(VAC, "L", n), _rng(FR, "G", n), _rng(IE, "K", n), _rng(DBO, "M", na)]
    ajus = [[con_, fx(f"-SUM({rg})", v), deb, cre, "Recalculado − registrado (filas con registro informado)"]
            for (con_, v, deb, cre), rg in zip(d["ajustes"], difs)]
    naj = len(ajus)

    celda = {"remuneracionRegistrada": f"{CG}B{FILA0}", "remuneracionRecalculada": f"{CG}C{FILA0}", "difRemuneracion": f"{CG}F{FILA0}",
             "difMayorNomina": f"{CG}E{FILA0}", "difAportePersonal": f"SUM({_rng(IE, 'G', n)})", "aportePatronalRecalculado": f"{CG}C{FILA0 + 1}",
             "d13Recalculado": f"{CG}C{FILA0 + 2}", "d14Recalculado": f"{CG}C{FILA0 + 3}", "vacacionesRecalculadas": f"{CG}C{FILA0 + 4}",
             "fondoReservaEsperado": f"{CG}C{FILA0 + 5}", "dboInforme": f"{CG}C{FILA0 + 6}", "provisionActuarialRegistrada": f"{CG}B{FILA0 + 6}",
             "gastoActuarialResultados": f"SUM({_rng(ORIH, 'B', na)})", "oriActuarial": f"SUM({_rng(ORIH, 'C', na)})",
             "desahucioLegalReferencial": f"SUM({_rng(CEN, 'F', len(AC))})", "ajustePasivos": f"{AJ}B{FILA0 + naj}"}
    resumen = [[res["labels"][kk], fx(celda[kk], k[kk])] for kk in res["labels"]]

    tot = lambda col, nn, v: suma(col, fin(nn), v)
    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Empleados", "Empleados (datos del cliente)",
             [["Cédula/código", "t"], ["Nombre", "t"], ["Ingreso", "d"], ["Salida", "d"], ["Región", "t"], ["Sueldo mensual", "n"],
              ["Horas 50 %", "n"], ["Horas 100 %", "n"], ["Horas extras registradas", "n"], ["Comisiones y bonos", "n"],
              ["Remuneración anual registrada", "n"], ["Otras deducciones", "n"], ["Neto pagado", "n"], ["Base planillas IESS", "n"],
              ["Aporte personal registrado", "n"], ["Aporte patronal registrado", "n"], ["D13 mensualizado", "t"], ["D14 mensualizado", "t"],
              ["D13 provisionado", "n"], ["D14 provisionado", "n"], ["Saldo inicial días vacaciones", "n"], ["Días gozados", "n"],
              ["Vacaciones provisionadas", "n"], ["Fondo de reserva pagado", "n"], ["En estudio actuarial", "t"]], emp,
             ["TOTAL", "", "", "", "", None, None, None, None, None, tot("K", n, k["remuneracionRegistrada"])] + [None] * 14),
        hoja("04_Actuarial", "Informe actuarial (datos del cliente)",
             [["Plan", "t"], ["Tipo", "t"], ["DBO inicial", "n"], ["Costo del servicio", "n"], ["Costo por intereses", "n"],
              ["Servicios pasados", "n"], ["Nuevas mediciones", "n"], ["Beneficios pagados", "n"], ["DBO final (informe)", "n"],
              ["Provisión registrada", "n"], ["Nuevas mediciones registradas en", "t"], ["Empleados en el estudio", "i"],
              ["Tasa de descuento %", "n"], ["Incremento salarial %", "n"], ["Fecha del informe", "d"]], act),
        hoja("05_Tiempo_servicio", "Tiempo de servicio",
             [["Cédula/código", "t"], ["Desde (en el ejercicio)", "d"], ["Hasta", "d"], ["Días trabajados (30/360)", "i"], ["Activo al corte", "t"],
              ["Años de servicio", "i"], ["Derecho a fondo de reserva desde (13.º mes)", "d"], ["Días con derecho a fondo de reserva", "i"]], ts),
        hoja("06_Recalculo_nomina", "Recálculo de nómina: bruto y neto",
             [["Cédula/código", "t"], ["Sueldo mensual", "n"], ["Días", "i"], ["Sueldo del período", "n"], ["Valor hora", "n"], ["Horas 50 %", "n"],
              ["Horas 100 %", "n"], ["Horas extras recalculadas", "n"], ["Horas extras registradas", "n"], ["Dif. horas extras", "n"],
              ["Comisiones y bonos", "n"], ["Bruto recalculado", "n"], ["Remuneración registrada", "n"], ["Registrada − recalculada", "n"],
              ["Aporte personal s/ bruto", "n"], ["Otras deducciones", "n"], ["Neto recalculado", "n"], ["Neto pagado", "n"], ["Dif. neto", "n"]], nom,
             ["TOTAL", None, None, None, None, None, None, None, None, None, None, tot("L", n, k["remuneracionRecalculada"]),
              tot("M", n, k["remuneracionRegistrada"]), tot("N", n, k["difRemuneracion"]), None, None, None, None, None]),
        hoja("07_IESS", "Aportes IESS y planillas",
             [["Cédula/código", "t"], ["Base (remuneración registrada)", "n"], ["Base planillas IESS", "n"], ["Dif. planilla − nómina", "n"],
              ["Aporte personal recalculado", "n"], ["Aporte personal registrado", "n"], ["Dif. personal", "n"], ["Tasa patronal total", "p"],
              ["Aporte patronal recalculado", "n"], ["Aporte patronal registrado", "n"], ["Dif. patronal", "n"]], ies,
             ["TOTAL", None, None, None, tot("E", n, sum(e["ap"] for e in Em)), None, tot("G", n, k["difAportePersonal"]), None,
              tot("I", n, k["aportePatronalRecalculado"]), None, tot("K", n, sum(e["pat_dif"] or 0 for e in Em))]),
        hoja("08_Decimo_tercero", "Décimo tercero",
             [["Cédula/código", "t"], ["Activo", "t"], ["Mensualizado", "t"], ["Días del período al corte", "i"], ["Remuneración diaria", "n"],
              ["Provisión recalculada (1/12)", "n"], ["Provisionado", "n"], ["Provisionado − recalculado", "n"]], t13,
             ["TOTAL", "", "", None, None, tot("F", n, k["d13Recalculado"]), None, tot("H", n, sum(e["d13_dif"] or 0 for e in Em))]),
        hoja("09_Decimo_cuarto", "Décimo cuarto",
             [["Cédula/código", "t"], ["Activo", "t"], ["Mensualizado", "t"], ["Región", "t"], ["Inicio del período", "d"], ["Días del período al corte", "i"],
              ["Provisión recalculada (SBU × días ÷ 360)", "n"], ["Provisionado", "n"], ["Provisionado − recalculado", "n"]], t14,
             ["TOTAL", "", "", "", None, None, tot("G", n, k["d14Recalculado"]), None, tot("I", n, sum(e["d14_dif"] or 0 for e in Em))]),
        hoja("10_Vacaciones", "Vacaciones",
             [["Cédula/código", "t"], ["Activo", "t"], ["Años de servicio", "i"], ["Días por año", "n"], ["Días devengados en el año", "n"],
              ["Saldo inicial días", "n"], ["Días gozados", "n"], ["Saldo final días", "n"], ["Valor por día", "n"], ["Provisión recalculada", "n"],
              ["Provisionado", "n"], ["Provisionado − recalculado", "n"]], vac,
             ["TOTAL", "", None, None, None, None, None, None, None, tot("J", n, k["vacacionesRecalculadas"]), None,
              tot("L", n, sum(e["vac_dif"] or 0 for e in Em))]),
        hoja("11_Fondo_reserva", "Fondo de reserva",
             [["Cédula/código", "t"], ["Días trabajados", "i"], ["Días con derecho", "i"], ["Bruto recalculado", "n"], ["Fondo de reserva debido", "n"],
              ["Pagado o depositado", "n"], ["Pagado − debido", "n"]], frs,
             ["TOTAL", None, None, None, tot("E", n, k["fondoReservaEsperado"]), None, tot("G", n, sum(e["fr_dif"] or 0 for e in Em))]),
        hoja("12_DBO_actuarial", "Jubilación patronal y desahucio: DBO",
             [["Plan", "t"], ["Tipo", "t"], ["DBO inicial", "n"], ["Costo del servicio", "n"], ["Intereses", "n"], ["Servicios pasados", "n"],
              ["Nuevas mediciones", "n"], ["Beneficios pagados", "n"], ["DBO final recalculado", "n"], ["DBO final (informe)", "n"],
              ["Informe − recalculado", "n"], ["Provisión registrada", "n"], ["Registrada − informe", "n"], ["Activos al corte (nómina)", "i"],
              ["Empleados en el estudio", "i"], ["Estudio − nómina", "i"]], dbo,
             ["TOTAL", "", None, None, None, None, None, None, None, tot("J", na, k["dboInforme"]), None,
              tot("L", na, k["provisionActuarialRegistrada"]), tot("M", na, sum(a["dif_prov"] for a in Ac)), None, None, None] if na else None),
        hoja("13_Resultados_ORI", "Costo post-empleo: resultados y ORI",
             [["Plan", "t"], ["Gasto en resultados", "n"], ["Otro resultado integral", "n"], ["Destino según marco", "t"],
              ["Registrado por el cliente en", "t"], ["Conforme", "t"]], ori,
             ["TOTAL", tot("B", na, k["gastoActuarialResultados"]), tot("C", na, k["oriActuarial"]), "", "", ""] if na else None),
        hoja("14_Censo_actuarial", "Censo actuarial y desahucio legal",
             [["Cédula/código", "t"], ["Nombre", "t"], ["Años de servicio", "i"], ["Sueldo mensual", "n"], ["En estudio actuarial", "t"],
              ["Desahucio legal referencial (25 % × sueldo × años)", "n"]], cen,
             ["TOTAL", "", None, None, "", tot("F", len(AC), k["desahucioLegalReferencial"])] if AC else None),
        hoja("15_Conciliacion_GL", "Conciliación nómina–mayor",
             [["Concepto", "t"], ["Detalle registrado", "n"], ["Recalculado", "n"], ["Mayor", "n"], ["Detalle − mayor", "n"],
              ["Registrado − recalculado", "n"]], cg),
        hoja("16_Ajustes", "Ajustes propuestos",
             [["Concepto", "t"], ["Importe (+ aumenta el pasivo)", "n"], ["Débito (si positivo)", "t"], ["Crédito (si positivo)", "t"], ["Base", "t"]],
             ajus, ["TOTAL", tot("B", naj, k["ajustePasivos"]), "", "", ""]),
        hoja("17_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -------------------------------------------------------------------

def definicion() -> dict:
    emp = ("Una fila por empleado que trabajó en el ejercicio (activos y salidos): cédula o código, nombre, fechas de ingreso y salida, región, "
           "sueldo mensual, horas suplementarias y extraordinarias del año y su valor, comisiones y bonos, remuneración anual registrada, "
           "otras deducciones y neto pagado, base de las planillas IESS, aportes personal y patronal registrados, si mensualiza los décimos, "
           "décimos y vacaciones provisionados al corte, saldo inicial y días gozados de vacaciones, fondo de reserva pagado y si está en el "
           "estudio actuarial. Sin filas de total.")
    act = ("Una fila por plan del informe actuarial (jubilación patronal y desahucio): DBO inicial, costo del servicio, intereses, servicios "
           "pasados, nuevas mediciones (pérdida + / ganancia −), beneficios pagados, DBO final, provisión registrada, dónde se registraron las "
           "nuevas mediciones (ORI/Resultados), empleados del estudio, tasa de descuento, incremento salarial y fecha del informe.")
    return {
        "name": "Beneficios sociales y nómina",
        "area": "Nómina",
        "processor": "nomina_beneficios",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Recalcula la nómina (bruto, horas extras, neto), los aportes IESS, el décimo tercero, el décimo cuarto, las vacaciones y el "
                    "fondo de reserva de cada empleado; concilia nómina y mayor; verifica el movimiento del año (saldo inicial a final) del DBO de jubilación patronal y "
                    "desahucio contra el informe actuarial, la provisión registrada y el destino de las nuevas mediciones según el marco."),
        "source": {"organization": "IFRS Foundation (texto en español del Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIC 19 Retribuciones a los empleados: párr. 11–24 (corto plazo), 13–18 (ausencias remuneradas acumulativas: "
                                "vacaciones), 55–152 (post-empleo de beneficio definido), 67 (unidad de crédito proyectada), 75–98 (suposiciones "
                                "actuariales), 120 (componentes del costo), 122 y 127–130 (nuevas mediciones en otro resultado integral, sin "
                                "reclasificación). Texto oficial no leído en esta versión (la publicación de EUR-Lex excede el tamaño "
                                "descargable): VERIFICAR cada párrafo."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015 y 2025, Sección 28 Beneficios a los empleados: 28.3–28.8 (corto plazo, "
                                      "ausencias acumulativas 28.6), 28.14–28.28 (post-empleo; 28.18 unidad de crédito proyectada, 28.19 "
                                      "simplificaciones por costo o esfuerzo desproporcionado, 28.24 ganancias y pérdidas actuariales en "
                                      "resultados u ORI según política). VERIFICAR la numeración y el texto de cada edición."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "legal": ("Ecuador: Código del Trabajo arts. 55 (horas extras), 69 (vacaciones), 71 (valor 1/24), 111 (décimo tercero), 113 (décimo "
                  "cuarto), 185 (desahucio), 196 (fondo de reserva), 216 (jubilación patronal); Ley de Seguridad Social (aportes). Tasas y "
                  "SBU como parámetros: vigentes al corte; VERIFICAR."),
        "nia": [
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del anexo de empleados contra roles, planillas IESS y mayor."},
            {"document": "NIA 520", "section": "(VERIFICAR párrafos)", "requirement": "Recálculo sustantivo de la nómina y de las provisiones laborales."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 18 (VERIFICAR)", "requirement": "Estimación actuarial: método, datos (censo) y supuestos."},
            {"document": "NIA 500 / 620", "section": "párr. 8 NIA 500 (VERIFICAR)", "requirement": "Uso del trabajo del actuario (experto de la dirección): competencia, objetividad, datos fuente."},
            {"document": "NIA 330", "section": "párr. 18 (VERIFICAR)", "requirement": "Procedimientos sustantivos sobre gasto y pasivos laborales materiales."},
        ],
        "calculo": [
            "Días trabajados en el ejercicio en base comercial 30/360 (DAYS360 europeo); activo si no salió hasta el corte.",
            "Bruto = sueldo mensual × días ÷ 30 + horas extras + comisiones; horas extras = sueldo ÷ horas del mes × (horas × (1 + recargo)); neto = bruto − aporte personal − otras deducciones.",
            "Aporte personal = remuneración registrada × % personal; patronal = remuneración × (% patronal + IECE + SECAP).",
            "Décimo tercero al corte = remuneración diaria × días desde el inicio del período (dic) ÷ 12; décimo cuarto = SBU × días desde el inicio del período por región ÷ 360; cero si se mensualiza o salió.",
            "Vacaciones: días por año (15 + 1 por año sobre 5, máx. 15) × días ÷ 360; saldo = inicial + devengados − gozados; provisión = saldo × remuneración diaria (NIC 19.13–16 · PYMES 28.6).",
            "Fondo de reserva = bruto × 8,33 % × días con derecho (desde el 13.º mes) ÷ días trabajados.",
            "DBO final = inicial + costo del servicio + intereses + servicios pasados + nuevas mediciones − beneficios pagados, frente al informe y a la provisión registrada.",
            "Nuevas mediciones: NIIF completas → ORI (NIC 19.120 c, 127–130); PYMES → resultados u ORI según política (28.24).",
        ],
        "fields": _EMPLEADOS, "rules": [], "control": CONTROL, "primary": "ajustePasivos",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[a, b] for a, b in CEDULAS],
        "program": [
            {"code": "PAY-01", "objective": "Sumaria nómina–mayor–EEFF", "risk": "Gasto o pasivos laborales no conciliados", "assertion": "Integridad / Exactitud",
             "procedure": "Conciliar remuneraciones, aportes, décimos, vacaciones, fondo de reserva y provisión actuarial con el mayor",
             "evidence": "Nómina anual, mayor", "criterion": "Diferencia dentro de tolerancia", "source": "NIA 500 · NIA 330"},
            {"code": "PAY-02", "objective": "Recálculo de sueldos y neto", "risk": "Remuneración mal calculada", "assertion": "Exactitud / Ocurrencia",
             "procedure": "Recalcular bruto y neto por empleado con sueldo, días, horas extras y comisiones", "evidence": "Roles de pago, contratos",
             "criterion": "Registrada = recalculada", "source": "NIC 19.11 · PYMES 28.3"},
            {"code": "PAY-03", "objective": "Horas extras", "risk": "Horas extras sobrevaloradas o sin recargo legal", "assertion": "Exactitud",
             "procedure": "Recalcular con valor hora y recargos 50 %/100 %", "evidence": "Marcaciones, autorizaciones", "criterion": "Valor recalculado",
             "source": "CT art. 55 (VERIFICAR)"},
            {"code": "PAY-05", "objective": "Aportes IESS", "risk": "Aportes mal calculados o no pagados", "assertion": "Exactitud / Integridad",
             "procedure": "Recalcular aportes personal y patronal (con IECE y SECAP) y cruzar la base con las planillas IESS", "evidence": "Planillas y comprobantes IESS",
             "criterion": "Registrado = recalculado; base planilla = nómina", "source": "Ley de Seguridad Social (tasas VERIFICAR)"},
            {"code": "PAY-07", "objective": "Décimo tercero y décimo cuarto", "risk": "Décimos mal provisionados al corte", "assertion": "Valoración / Integridad",
             "procedure": "Recalcular la parte devengada al corte por empleado, período y región", "evidence": "Nómina, formularios de pago de décimos",
             "criterion": "Provisión = recalculada", "source": "CT arts. 111 y 113 · NIC 19.11–13 · PYMES 28.3–28.6"},
            {"code": "PAY-09", "objective": "Vacaciones", "risk": "Vacaciones devengadas no provisionadas", "assertion": "Integridad / Valoración",
             "procedure": "Recalcular el saldo de días y valorarlo con la remuneración diaria", "evidence": "Registro de vacaciones",
             "criterion": "Provisión = saldo × valor día", "source": "CT art. 69 · NIC 19.13–16 · PYMES 28.6"},
            {"code": "PAY-10", "objective": "Fondo de reserva", "risk": "Fondo de reserva no pagado a quien corresponde", "assertion": "Integridad",
             "procedure": "Recalcular el fondo debido desde el 13.º mes y compararlo con lo pagado o depositado", "evidence": "Planillas IESS de fondos de reserva",
             "criterion": "Pagado = debido", "source": "CT art. 196 (VERIFICAR)"},
            {"code": "PAY-13", "objective": "Jubilación patronal y desahucio", "risk": "Provisión distinta del informe actuarial", "assertion": "Valoración",
             "procedure": "Comparar la provisión registrada con el DBO del informe por plan", "evidence": "Informe actuarial", "criterion": "Registrada = DBO",
             "source": "NIC 19.57, 67 · PYMES 28.18 · CT arts. 185, 216"},
            {"code": "PAY-15", "objective": "Censo actuarial", "risk": "Empleados fuera del estudio", "assertion": "Integridad",
             "procedure": "Cruzar los activos de la nómina con el censo del actuario", "evidence": "Censo enviado al actuario", "criterion": "Mismo número y empleados",
             "source": "NIA 500 (experto de la dirección) · NIA 540"},
            {"code": "PAY-16", "objective": "DBO y movimiento del año", "risk": "Informe internamente inconsistente", "assertion": "Valoración",
             "procedure": "Recalcular DBO final = inicial + servicio + intereses + pasados + nuevas mediciones − pagos", "evidence": "Informe actuarial",
             "criterion": "Recalculado = informe", "source": "NIC 19.120, 140–141 (VERIFICAR) · PYMES 28.41"},
            {"code": "PAY-17", "objective": "Supuestos actuariales", "risk": "Supuestos no razonables", "assertion": "Valoración",
             "procedure": "Revisar tasa de descuento, incremento salarial, rotación y mortalidad", "evidence": "Informe actuarial",
             "criterion": "Supuestos sustentados", "source": "NIC 19.75–98 · PYMES 28.17 · NIA 540"},
            {"code": "PAY-18", "objective": "Resultados y ORI por marco", "risk": "Nuevas mediciones en resultados en NIIF completas", "assertion": "Presentación",
             "procedure": "Verificar el destino de las nuevas mediciones según el marco y la política", "evidence": "Asientos del cierre",
             "criterion": "Completas: ORI; PYMES: política 28.24", "source": "NIC 19.120 c, 127–130 · PYMES 28.24"},
        ],
        "requests": [
            req("RQ-001", "Anexo de empleados del ejercicio con remuneraciones, aportes, décimos, vacaciones y fondo de reserva", "empleados", "PAY-02",
                "Población a recalcular y conciliar con el mayor", content=emp),
            req("RQ-002", "Resumen del informe actuarial por plan (jubilación patronal y desahucio)", "actuarial", "PAY-16",
                "Movimiento del año de la obligación actuarial (DBO) y comparación con la provisión", content=act),
            req("RQ-003", "Roles de pago mensuales y contratos de trabajo", None, "PAY-02", "Sustento de sueldos, horas extras y comisiones",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-004", "Planillas y comprobantes de pago del IESS (aportes y fondos de reserva)", None, "PAY-05", "Cruce de bases y pagos",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-005", "Informe actuarial completo y censo enviado al actuario", None, "PAY-15", "Supuestos, censo y DBO", formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-006", "Mayores de gasto de nómina y de pasivos laborales", None, "PAY-01", "Conciliación nómina–mayor", formats=("xlsx",), use="soporte"),
            req("RQ-007", "Registro de vacaciones y comprobantes de pago de décimos", None, "PAY-09", "Saldo de días y pagos", required=False,
                formats=("xlsx", "pdf"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


def _e(id, nombre, ingreso, region, sueldo, rem, **x):
    return {"id": id, "nombre": nombre, "fecha_ingreso": ingreso, "region": region, "sueldo_mensual": sueldo, "remuneracion_anual": rem, "_row": 2, **x}


def _pl(id, tipo, ini, sc, ic, nm, bp, fin_, prov, **x):
    return {"id": id, "tipo": tipo, "dbo_inicial": ini, "costo_servicio": sc, "costo_interes": ic, "nuevas_mediciones": nm,
            "beneficios_pagados": bp, "dbo_final": fin_, "provision_registrada": prov, "_row": 2, **x}


# Ejemplo de control (M19), corte 2025-12-31, SBU 470 (VERIFICAR):
# E01 Ana: 1.200 × 360 ÷ 30 = 14.400 + horas extras 5 × (20 × 1,5 + 10 × 2) = 250 → bruto 14.650; D13 = 14.650 ÷ 360 × 30 ÷ 12 = 101,74;
#   D14 Sierra (1-ago) = 470 × 150 ÷ 360 = 195,83; 10 años → 20 días; saldo 10 + 20 − 15 = 15 × 40,69 = 610,42; FR 14.650 × 8,33 % = 1.220,35.
# E02 Bruno (Costa): aporte personal 900 vs 10.320 × 9,45 % = 975,24; D14 desde 1-mar = 470 × 300 ÷ 360 = 391,67 vs 195,83; vacaciones 143,33 sin provisión.
# E04 Diego: salió el 30-jun: 180 días, FR debido 6.000 × 8,33 % = 499,80 no pagado. E05 Elena: D13 187,50 vs 150.
# E06 Fabián: remuneración registrada 8.290 vs 8.490; horas 16 × 2,9167 × 1,5 = 70 vs 90; planilla 8.490.
# E07 Gabriela: 13.º mes el 15-nov-2025 → 46 días × 5.640 × 8,33 % ÷ 360 = 60,03 no pagado; vacaciones 266,33 no informadas.
# JUB: 85.000 + 9.500 + 6.800 + 3.200 − 2.500 = 102.000 = informe; registrada 95.000 → 7.000; nuevas mediciones en resultados (completas).
# DES: 30.000 + 4.200 + 2.400 − 1.500 − 3.000 = 32.100 vs informe 32.500 (roll-forward 400). Censo 6 vs 7 activos (E03 fuera del estudio).
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tolerancia": 1, "mayorGastoNomina": 95300, "mayorAportePatronal": 11578.96, "mayorD13": 600,
                   "mayorD14": 1566.66, "mayorVacaciones": 5286.34},
    "datasets": {
        "empleados": [
            _e("E01", "Ana Pérez", "2015-03-01", "Sierra", "1200", "14650", horas_50="20", horas_100="10", horas_extras="250", otras_deducciones="300",
               neto_pagado="12965.58", base_iess_planilla="14650", aporte_personal="1384.43", aporte_patronal="1779.98", d13_provisionado="101.74",
               d14_provisionado="195.83", vac_saldo_inicial="10", vac_gozados="15", vacaciones_provisionadas="610.42", fondo_reserva="1220.35", en_estudio="Sí"),
            _e("E02", "Bruno Salazar", "2020-06-15", "Costa", "800", "10320", horas_extras="120", comisiones="600", aporte_personal="900",
               aporte_patronal="1253.88", d13_provisionado="71.67", d14_provisionado="195.83", vac_saldo_inicial="5", vac_gozados="15",
               vacaciones_provisionadas="0", fondo_reserva="859.66", en_estudio="Sí"),
            _e("E03", "Carla Mora", "2025-04-01", "Sierra", "600", "5400", aporte_personal="510.30", aporte_patronal="656.10", d13_provisionado="50",
               d14_provisionado="195.83", vac_saldo_inicial="0", vac_gozados="0", vacaciones_provisionadas="225", fondo_reserva="0", en_estudio="No"),
            _e("E04", "Diego Ruiz", "2018-01-10", "Sierra", "1000", "6000", fecha_salida="2025-06-30", aporte_personal="567", aporte_patronal="729",
               d13_provisionado="0", d14_provisionado="0", vacaciones_provisionadas="0", fondo_reserva="0"),
            _e("E05", "Elena Vásquez", "2010-02-01", "Sierra", "2000", "27000", comisiones="3000", aporte_personal="2551.50", aporte_patronal="3280.50",
               mensualiza_d14="Sí", d13_provisionado="150", d14_provisionado="0", vac_saldo_inicial="30", vac_gozados="25",
               vacaciones_provisionadas="2250", fondo_reserva="2249.10", en_estudio="Sí"),
            _e("E06", "Fabián Torres", "2022-09-01", "Costa", "700", "8290", horas_50="16", horas_extras="90", otras_deducciones="100",
               neto_pagado="7400", base_iess_planilla="8490", aporte_personal="783.41", aporte_patronal="1007.24", mensualiza_d13="Sí",
               d13_provisionado="0", d14_provisionado="391.67", vac_saldo_inicial="12", vac_gozados="10", vacaciones_provisionadas="400.92",
               fondo_reserva="707.22", en_estudio="Sí"),
            _e("E07", "Gabriela León", "2024-11-15", "Sierra", "470", "5640", aporte_personal="532.98", aporte_patronal="685.26",
               d13_provisionado="39.17", d14_provisionado="195.83", vac_saldo_inicial="2", vac_gozados="0", fondo_reserva="0", en_estudio="Sí"),
            _e("E08", "Hugo Cedeño", "2012-07-01", "Costa", "1500", "18000", aporte_personal="1701", aporte_patronal="2187", d13_provisionado="125",
               d14_provisionado="391.67", vac_saldo_inicial="40", vac_gozados="15", vacaciones_provisionadas="1800", fondo_reserva="1499.40", en_estudio="Sí"),
        ],
        "actuarial": [
            _pl("JUB", "Jubilación patronal", "85000", "9500", "6800", "3200", "2500", "102000", "95000", remediciones_en="Resultados",
                empleados_estudio="6", tasa_descuento="7.5", incremento_salarial="2.5", fecha_informe="2026-01-20"),
            _pl("DES", "Desahucio", "30000", "4200", "2400", "-1500", "3000", "32500", "32500", remediciones_en="ORI", empleados_estudio="6",
                incremento_salarial="2.5", fecha_informe="2026-01-20"),
        ],
    },
}

_MIN = {"empleados": [_e("M1", "Empleado mínimo", "2024-01-01", "", "470", "5640")], "actuarial": []}
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015_resultados", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015", "actuarialesEn": RESULTADOS},
     EJEMPLO["corte"]),
    ("pymes_2025_ori", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025", "actuarialesEn": ORI}, EJEMPLO["corte"]),
    ("minimo", _MIN, {}, "2025-12-31"),
]
