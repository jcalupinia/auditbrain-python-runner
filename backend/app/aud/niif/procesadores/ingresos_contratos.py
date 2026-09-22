"""Ingresos de contratos con clientes: existencia, precio, variable, asignación, satisfacción, corte y devoluciones.

Una sola población (una fila por obligación o entregable de cada contrato/factura) alimenta todas las pruebas:

1. Existencia del contrato (NIIF 15 9, 15-16; PYMES 2025 23.7-23.10): sin contrato válido no se reconoce ingreso.
2. Precio de la transacción y contraprestación variable (NIIF 15 47-59; PYMES 2025 23.23-23.31): importe más probable
   o valor esperado, incluido solo si es altamente probable (restricción 56-58; 23.30). PYMES 2015 (23.3, 23.10 c-d):
   valor razonable de la contraprestación, se incluye si es probable (> 50 %).
3. Asignación por precio de venta independiente relativo (NIIF 15 73-80; PYMES 2025 23.39-23.47; PYMES 2015 23.8).
4. Satisfacción: en un momento (NIIF 15 38; 23.57-23.58) o a lo largo del tiempo con método de insumos
   costos incurridos ÷ costos totales (NIIF 15 35, 39-45, B18-B19; 23.54, 23.62-23.66). PYMES 2015: venta de bienes
   por riesgos y beneficios (23.10-23.13) y servicios/construcción por grado de terminación (23.14-23.22).
5. Devoluciones: pasivo por reembolso (NIIF 15 B20-B27; PYMES 2025 23.33-23.35) / provisión (PYMES 2015 23.13,
   Sección 21); notas de crédito posteriores al cierre como evidencia (NIA 560).
6. Componente de financiación significativo (NIIF 15 60-65; PYMES 2025 23.36-23.38; PYMES 2015 23.5): valor presente
   a la tasa de descuento, interés devengado desde la transferencia.
7. Ingreso reconocible del año vs registrado (ajuste), corte, activo/pasivo del contrato (NIIF 15 105-109;
   PYMES 2025 23.77-23.80), modificaciones (NIIF 15 18-21; PYMES 2025 23.12, 23A.2-23A.4) y conciliación con el mayor.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m,
    n2, norm, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "ingresos_contratos 1.0"
RUBRO = "INGRESOS"

TIEMPO, MOMENTO = "A lo largo del tiempo", "En un momento"
METODOS = ("Importe más probable", "Valor esperado")
TIPOS_MOD = {"separado": "Contrato separado", "prospectivo": "Prospectivo", "acumulativo": "Acumulativo"}

_CONTRATOS = [
    campo("id", "Línea / obligación", alias=("linea", "obligacion id", "item", "codigo"), ejemplo="C-001-1"),
    campo("contrato", "N° de contrato / factura", alias=("numero de contrato", "factura", "contrato n", "documento"), ejemplo="C-001"),
    campo("cliente", "Cliente", alias=("razon social", "nombre del cliente", "comprador"), ejemplo="Comercial Andina S.A."),
    campo("obligacion", "Obligación / entregable", "text", False, ("entregable", "descripcion", "bien o servicio", "promesa")),
    campo("evidencia", "Contrato aprobado y con sustancia (Sí/No)", "text", False, ("evidencia contrato", "contrato firmado", "existe contrato")),
    campo("modo", "Momento o a lo largo del tiempo", alias=("satisfaccion", "reconocimiento", "tipo de reconocimiento"), ejemplo="En un momento"),
    campo("fecha_contrato", "Fecha del contrato", "date", False, ("fecha contrato", "fecha de firma")),
    campo("fecha_transferencia", "Fecha de entrega / transferencia del control", "date", False, ("fecha entrega", "fecha transferencia", "fecha despacho")),
    campo("fecha_registro", "Fecha de registro del ingreso", "date", False, ("fecha registro", "fecha contable", "fecha factura")),
    campo("psi", "Precio de venta independiente", "number", False, ("precio de venta independiente", "pvi", "ssp", "valor razonable")),
    campo("precio", "Precio del contrato asignado por el cliente", "number", alias=("precio contrato", "precio fijo", "valor contrato"), ejemplo="90000.00"),
    campo("variable", "Contraprestación variable estimada", "number", False, ("variable", "bono", "incentivo", "rappel")),
    campo("probabilidad", "Probabilidad de la variable (%)", "number", False, ("probabilidad", "prob")),
    campo("variable_cliente", "Variable incluida por el cliente", "number", False, ("variable registrada", "variable cliente")),
    campo("costo_incurrido", "Costos incurridos al corte", "number", False, ("costos incurridos", "costo incurrido")),
    campo("costo_total", "Costos totales estimados", "number", False, ("costos totales", "costo total estimado", "presupuesto")),
    campo("avance_cliente", "Avance según el cliente (%)", "number", False, ("avance", "grado de terminacion", "porcentaje de avance")),
    campo("registrado", "Ingreso registrado en el año", "number", alias=("ingreso registrado", "ingreso del ano", "ventas del ano"), ejemplo="90000.00"),
    campo("anterior", "Ingreso reconocido en años anteriores", "number", False, ("reconocido anterior", "ingreso anos anteriores")),
    campo("facturado", "Facturado acumulado", "number", False, ("facturado", "facturacion acumulada")),
    campo("cobrado", "Cobrado acumulado", "number", False, ("cobrado", "cobros")),
    campo("plazo_cobro", "Plazo de cobro (meses)", "number", False, ("plazo de cobro", "plazo meses", "plazo credito")),
    campo("devolucion", "Devoluciones esperadas (%)", "number", False, ("devoluciones esperadas", "porcentaje devolucion")),
    campo("nc_posterior", "Notas de crédito posteriores al cierre", "number", False, ("notas de credito posteriores", "nc posteriores")),
    campo("modificacion", "Modificación (Contrato separado / Prospectivo / Acumulativo)", "text", False, ("tipo modificacion", "adenda")),
    campo("importe_modificacion", "Importe de la modificación", "number", False, ("importe adenda", "valor modificacion")),
]
CAMPOS = {"contratos": _CONTRATOS}
TIPOS = {"contratos": "contratos"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "contratos"
CONTROL = "registrado"

PARAMETROS = {"tasaDescuento": None, "plazoFinanciacion": 12, "umbralAltamenteProbable": 75, "metodoVariable": METODOS[0],
              "ingresoMayor": None, "activoContratoRegistrado": None, "pasivoContratoRegistrado": None}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "tasaDescuento": "Tasa de descuento anual para la financiación (%)",
    "plazoFinanciacion": "Plazo de cobro que se considera financiación significativa (meses)",
    "umbralAltamenteProbable": "Probabilidad mínima para incluir la variable «altamente probable» (%)",
    "metodoVariable": "Método de estimación de la variable (Importe más probable / Valor esperado)",
    "ingresoMayor": "Ingresos de actividades ordinarias según el mayor",
    "activoContratoRegistrado": "Activo del contrato registrado (mayor)",
    "pasivoContratoRegistrado": "Pasivo del contrato / ingreso diferido registrado (mayor)",
}
TOTAL_EJEMPLO = "ingresoReconocible"

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Detalle", "Detalle por obligación"),
    ("04_Precio_variable", "Precio y contraprestación variable"), ("05_Asignacion", "Asignación del precio"),
    ("06_Satisfaccion", "Satisfacción y porcentaje de avance"), ("07_Devoluciones", "Devoluciones y notas de crédito"),
    ("08_Financiacion", "Componente de financiación"), ("09_Reconocimiento", "Ingreso reconocible vs registrado"),
    ("10_Activo_pasivo", "Activo y pasivo del contrato"), ("11_Corte", "Corte de ingresos"),
    ("12_Modificaciones", "Modificaciones de contratos"), ("13_Conciliacion", "Conciliación y ajustes"),
    ("14_Asientos", "Asientos propuestos"), ("15_Problemas", "Problemas encontrados"),
]

_NO_NEGATIVOS = ("psi", "precio", "variable", "costo_incurrido", "costo_total", "facturado", "cobrado", "plazo_cobro", "nc_posterior")
_PORCENTAJES = ("probabilidad", "avance_cliente", "devolucion")


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def _modo(v):
    t = norm(v or "")
    if any(k in t for k in ("tiempo", "avance", "terminacion", "servicio", "construccion", "obra")):
        return TIEMPO
    if any(k in t for k in ("momento", "punto", "entrega", "bien", "venta")):
        return MOMENTO
    return None


def _tipo_mod(v):
    t = norm(v or "")
    return next((n for k, n in TIPOS_MOD.items() if k in t), None)


def _opc(f, k):
    v = str(f.get(k, "") or "").strip()
    return a_num(v) if v else None


def validar_filas(tipo: str, filas: list) -> dict:
    r = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        fila = f.get("_row")
        if str(f.get("modo", "") or "").strip() and _modo(f.get("modo")) is None:
            r["errors"].append({"row": fila, "field": "modo", "message": "Indique «En un momento» o «A lo largo del tiempo»."})
        for k in _NO_NEGATIVOS:
            x = _opc(f, k)
            if x is not None and x < 0:
                r["errors"].append({"row": fila, "field": k, "message": "No puede ser negativo."})
        for k in _PORCENTAJES:
            x = _opc(f, k)
            if x is not None and not 0 <= x <= 100:
                r["errors"].append({"row": fila, "field": k, "message": "Use un porcentaje entre 0 y 100."})
    r["ok"] = not r["errors"]
    return r


# --- cálculo -----------------------------------------------------------------

def _pnum(p, k):
    v = p.get(k)
    return None if v is None or str(v).strip() == "" else float(a_num(v))


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    pymes = es_pymes(p)
    ed = edicion_pymes(p) if pymes else ""
    s15 = pymes and ed == "2015"          # riesgos y beneficios / grado de terminación
    tasa = _pnum(p, "tasaDescuento")
    umbral = _pnum(p, "plazoFinanciacion")
    uprob = _pnum(p, "umbralAltamenteProbable")
    metodo = str(p.get("metodoVariable") or METODOS[0]).strip()
    if umbral is None or umbral < 0:
        raise ValueError("Indique el plazo de cobro que se considera financiación significativa (meses).")
    if tasa is not None and tasa < 0:
        raise ValueError("La tasa de descuento no puede ser negativa.")
    if uprob is None or not 0 < uprob <= 100:
        raise ValueError("La probabilidad mínima para incluir la variable debe estar entre 0 y 100.")
    if metodo not in METODOS:
        raise ValueError("Método de la variable: use «Importe más probable» o «Valor esperado».")
    mayor = _pnum(p, "ingresoMayor")
    act_reg = _pnum(p, "activoContratoRegistrado")
    pas_reg = _pnum(p, "pasivoContratoRegistrado")

    L = []
    for f in datasets.get("contratos") or []:
        lid, ctr = str(f.get("id", "") or "").strip(), str(f.get("contrato", "") or "").strip()
        if not lid and not ctr:
            continue
        modo = _modo(f.get("modo"))
        precio, reg = _opc(f, "precio"), _opc(f, "registrado")
        if not ctr or modo is None or precio is None or reg is None:
            raise ValueError(f"Línea {lid or '(sin id)'}: faltan contrato, modo de satisfacción, precio o ingreso registrado.")
        x = {k: _opc(f, k) for k in ("psi", "variable", "probabilidad", "variable_cliente", "costo_incurrido", "costo_total",
                                     "avance_cliente", "anterior", "facturado", "cobrado", "plazo_cobro", "devolucion",
                                     "nc_posterior", "importe_modificacion")}
        for k in _NO_NEGATIVOS:
            v = precio if k == "precio" else x.get(k)
            if v is not None and v < 0:
                raise ValueError(f"Línea {lid}: {k} no puede ser negativo.")
        for k in _PORCENTAJES:
            if x[k] is not None and not 0 <= x[k] <= 100:
                raise ValueError(f"Línea {lid}: {k} debe estar entre 0 y 100.")
        ev = norm(f.get("evidencia") or "")
        evid = "No" if ev.startswith("no") else ("Sí" if ev.startswith("s") else "")
        mod_txt = str(f.get("modificacion", "") or "").strip()
        L.append({"id": lid, "contrato": ctr, "cliente": str(f.get("cliente", "") or "").strip() or "(sin nombre)",
                  "obligacion": str(f.get("obligacion", "") or "").strip(), "evidencia": evid, "modo": modo,
                  "transferencia": fecha(f.get("fecha_transferencia")), "registro": fecha(f.get("fecha_registro")),
                  "precio": precio, "registrado": reg, "modTexto": mod_txt, "modTipo": _tipo_mod(mod_txt), **x, "_row": f.get("_row")})
    if not L:
        raise ValueError("Cargue el anexo de contratos con una fila por obligación.")

    # 1. Existencia · 2. variable con restricción.
    for x in L:
        x["valido"] = "No" if x["evidencia"] == "No" else ("Sin dato" if x["evidencia"] == "" else "Sí")
        pr = None if x["probabilidad"] is None else x["probabilidad"] / 100
        x["prob"] = pr
        if x["variable"] is None or pr is None:
            inc = 0.0
        elif (pr > 0.5) if s15 else (pr >= uprob / 100):
            inc = x["variable"] * pr if metodo == "Valor esperado" else x["variable"]
        else:
            inc = 0.0
        x["varIncluida"] = inc
        x["varExceso"] = None if x["variable_cliente"] is None else max(x["variable_cliente"] - inc, 0)
    contratos = list(dict.fromkeys(x["contrato"] for x in L))
    por = {c: [x for x in L if x["contrato"] == c] for c in contratos}
    for c, xs in por.items():
        tp = sum(x["precio"] for x in xs) + sum(x["varIncluida"] for x in xs)
        for x in xs:
            x["psiEf"] = x["psi"] if x["psi"] is not None else x["precio"]
        spsi = sum(x["psiEf"] for x in xs)
        for x in xs:
            x["tp"], x["sumPsi"], x["nLineas"] = tp, spsi, len(xs)
            x["asignado"] = None if spsi == 0 else tp * x["psiEf"] / spsi
            x["asigCliente"] = x["precio"] + (0 if x["variable_cliente"] is None else x["variable_cliente"])
            x["difAsig"] = None if x["asignado"] is None else x["asignado"] - x["asigCliente"]

    # 3. Satisfacción · 4. devoluciones · 5. financiación · 6. reconocible vs registrado.
    for x in L:
        tiempo = x["modo"] == TIEMPO
        ci, ct = x["costo_incurrido"], x["costo_total"]
        x["avance"] = min(ci / ct, 1) if tiempo and ci is not None and (ct or 0) > 0 else None
        x["avanceCli"] = None if x["avance_cliente"] is None else x["avance_cliente"] / 100
        x["difAvance"] = None if x["avance"] is None or x["avanceCli"] is None else x["avanceCli"] - x["avance"]
        x["transferido"] = None if tiempo or x["transferencia"] is None else ("Sí" if x["transferencia"] <= corte_a else "No")
        if x["valido"] == "No":
            fac = 0
        elif tiempo:
            fac = x["avance"]
        else:
            fac = None if x["transferido"] is None else (1 if x["transferido"] == "Sí" else 0)
        x["factor"] = fac
        x["bruto"] = None if fac is None or x["asignado"] is None else x["asignado"] * fac
        dv = 0 if x["devolucion"] is None else x["devolucion"] / 100
        x["dev"] = dv
        x["reembolso"] = None if x["bruto"] is None else x["bruto"] * dv
        x["neto"] = None if x["bruto"] is None else x["bruto"] - x["reembolso"]
        x["ncNoProv"] = 0 if x["nc_posterior"] is None else max(x["nc_posterior"] - (x["reembolso"] or 0), 0)
        x["significativa"] = x["plazo_cobro"] is not None and x["plazo_cobro"] > umbral
        h = None if tasa is None else tasa / 100
        x["tasa"] = h
        if x["neto"] is None:
            x["vp"], x["componente"] = None, None
        elif x["significativa"]:
            x["vp"] = x["neto"] if h is None else x["neto"] / (1 + h) ** (x["plazo_cobro"] / 12)
            x["componente"] = None if h is None else x["neto"] - x["vp"]
        else:
            x["vp"], x["componente"] = x["neto"], 0
        x["diasDev"] = (max(min((corte_a - x["transferencia"]).days, x["plazo_cobro"] * 365 / 12), 0)
                        if x["significativa"] and x["transferencia"] is not None else 0)
        if x["componente"] is None:
            x["interes"] = None
        elif x["componente"] == 0:
            x["interes"] = 0
        else:
            x["interes"] = x["vp"] * ((1 + h) ** (x["diasDev"] / 365) - 1)
        x["anteriorEf"] = x["anterior"] or 0
        x["recAnio"] = None if x["vp"] is None else x["vp"] - x["anteriorEf"]
        x["ajuste"] = None if x["recAnio"] is None else x["recAnio"] - x["registrado"]
        x["perdida"] = (x["costo_total"] - x["asignado"]) if tiempo and x["costo_total"] is not None and x["asignado"] is not None \
            and x["costo_total"] > x["asignado"] else 0
        # corte (líneas en un momento con ambas fechas)
        x["enCorte"] = not tiempo and x["transferencia"] is not None and x["registro"] is not None
        if x["enCorte"]:
            x["regEj"] = x["registro"] <= corte_a
            x["trEj"] = x["transferencia"] <= corte_a
            x["anticipado"] = x["registrado"] if x["regEj"] and not x["trEj"] else 0
            x["omitido"] = (x["bruto"] or 0) if not x["regEj"] and x["trEj"] else 0
        else:
            x["anticipado"] = x["omitido"] = 0

    ap = []
    for c, xs in por.items():
        br = sum(x["bruto"] for x in xs if x["bruto"] is not None)
        fa = sum(x["facturado"] for x in xs if x["facturado"] is not None)
        co = sum(x["cobrado"] for x in xs if x["cobrado"] is not None)
        sin = sum(1 for x in xs if x["bruto"] is None)
        pos = None if sin else br - fa          # M22: con obligaciones sin medir la posición queda vacía
        ap.append({"contrato": c, "cliente": xs[0]["cliente"], "bruto": br, "facturado": fa, "cobrado": co, "posicion": pos,
                   "activo": None if pos is None else max(pos, 0), "pasivo": None if pos is None else max(-pos, 0), "cxc": fa - co, "sinMedir": sin})

    sm = lambda k: sum(x[k] for x in L if x[k] is not None)
    registrado = sm("registrado")
    mayor_ef = mayor if mayor is not None else registrado
    t = {
        "ingresoRegistrado": registrado, "ingresoMayor": mayor_ef, "difMayor": registrado - mayor_ef,
        "ingresoReconocible": sm("recAnio"), "ajuste": sm("ajuste"),
        "corteAnticipado": sm("anticipado"), "corteOmitido": sm("omitido"),
        "componenteFinanciero": sm("componente"), "interesDevengado": sm("interes"),
        "pasivoReembolso": sm("reembolso"), "devolucionesNoProvisionadas": sm("ncNoProv"),
        "activoContrato": sum(a["activo"] or 0 for a in ap), "activoRegistrado": act_reg or 0,
        "pasivoContrato": sum(a["pasivo"] or 0 for a in ap), "pasivoRegistrado": pas_reg or 0,
        "difAsignacion": sum(abs(x["difAsig"]) for x in L if x["difAsig"] is not None and x["nLineas"] > 1), "variableExceso": sm("varExceso"),
    }
    t["difActivo"] = t["activoContrato"] - t["activoRegistrado"]
    t["difPasivo"] = t["pasivoContrato"] - t["pasivoRegistrado"]

    if s15:
        n_act, n_pas = "Importe bruto adeudado por clientes (grado de terminación)", "Ingresos diferidos / anticipos de clientes"
        modelo = f"NIIF para las PYMES 2015 · Sección 23: riesgos y beneficios (23.10-23.13) y grado de terminación (23.14-23.22)"
    else:
        n_act, n_pas = "Activo del contrato", "Pasivo del contrato (ingreso diferido)"
        modelo = ("NIIF para las PYMES 2025 · Sección 23 revisada: modelo de cinco pasos simplificado" if pymes
                  else "NIIF 15 · modelo de cinco pasos")
    cit = {
        "contrato": "PYMES 23.10 (evidencia del acuerdo; VERIFICAR)" if s15 else ("PYMES 2025 23.7-23.10" if pymes else "NIIF 15 9, 15-16"),
        "variable": "PYMES 23.3, 23.10 c-d (probable)" if s15 else ("PYMES 2025 23.28-23.31" if pymes else "NIIF 15 53, 56-58"),
        "asig": "PYMES 23.8 (VERIFICAR método)" if s15 else ("PYMES 2025 23.42-23.47" if pymes else "NIIF 15 73-80"),
        "avance": "PYMES 23.21-23.22" if s15 else ("PYMES 2025 23.62-23.66" if pymes else "NIIF 15 39-45, B18-B19"),
        "fin": "PYMES 23.5 y 11.13" if s15 else ("PYMES 2025 23.36-23.38" if pymes else "NIIF 15 60-65"),
        "dev": "PYMES 23.13 y Sección 21 (VERIFICAR)" if s15 else ("PYMES 2025 23.33-23.35" if pymes else "NIIF 15 B20-B27"),
        "ap": "PYMES 23.32 (VERIFICAR)" if s15 else ("PYMES 2025 23.77-23.80" if pymes else "NIIF 15 105-109"),
        "corte": "PYMES 23.10 a" if s15 else ("PYMES 2025 23.57-23.58" if pymes else "NIIF 15 31, 38"),
        "mod": "PYMES 2015 sin guía específica (VERIFICAR; cambio de estimación, Sección 10)" if s15
               else ("PYMES 2025 23.12, 23A.2-23A.4" if pymes else "NIIF 15 18-21"),
        "perdida": "PYMES 23.26" if s15 else ("PYMES 2025 Sección 21 contratos onerosos (VERIFICAR)" if pymes else "NIC 37 66-69"),
    }

    pr = []
    for x in L:
        if x["valido"] == "No" and x["registrado"] > 0.005:
            pr.append(problema("SIN_CONTRATO", f"{x['id']} ({x['contrato']}): ingreso registrado sin contrato válido; no procede reconocerlo ({cit['contrato']}).", x["registrado"]))
    sin_ev = [x["id"] for x in L if x["valido"] == "Sin dato"]
    if sin_ev:
        pr.append(problema("CONTRATO_SIN_EVIDENCIA", f"{len(sin_ev)} línea(s) sin evidencia del contrato informada ({', '.join(sin_ev)}): obtenga el contrato o la orden aprobada ({cit['contrato']})."))
    for x in L:
        if x["anticipado"] > 0.005:
            pr.append(problema("ERROR_CORTE", f"{x['id']}: ingreso registrado en el ejercicio y control transferido después del corte ({cit['corte']}).", x["anticipado"]))
        if x["omitido"] > 0.005:
            pr.append(problema("ERROR_CORTE", f"{x['id']}: control transferido en el ejercicio e ingreso registrado después del corte ({cit['corte']}).", x["omitido"]))
        if x["modo"] == MOMENTO and x["transferencia"] is None and x["valido"] != "No":
            pr.append(problema("SIN_FECHA_TRANSFERENCIA", f"{x['id']}: sin fecha de transferencia del control; el ingreso no se pudo medir y queda vacío.", x["registrado"]))
        if x["modo"] == TIEMPO and x["avance"] is None and x["valido"] != "No":
            pr.append(problema("AVANCE_SIN_DATOS", f"{x['id']}: sin costos incurridos y totales; el avance no se pudo medir ({cit['avance']}).", x["registrado"]))
        if x["difAvance"] is not None and abs(x["difAvance"]) > 0.005:
            pr.append(problema("AVANCE_MAL_CALCULADO", f"{x['id']}: avance del cliente {m(x['avanceCli'] * 100)} % frente a {m(x['avance'] * 100)} % recalculado con costos ({cit['avance']}).",
                               x["difAvance"] * (x["asignado"] or 0)))
        if x["perdida"] > 0.005:
            pr.append(problema("PERDIDA_ESPERADA", f"{x['id']}: costos totales estimados superan el precio asignado; reconozca la pérdida esperada ({cit['perdida']}).", x["perdida"]))
        if x["nLineas"] > 1 and x["psi"] is None:
            pr.append(problema("PSI_FALTANTE", f"{x['id']}: sin precio de venta independiente en un contrato de {x['nLineas']} obligaciones; se usó el precio del contrato ({cit['asig']})."))
        if x["difAsig"] is not None and x["nLineas"] > 1 and abs(x["difAsig"]) > 0.005:
            pr.append(problema("ASIGNACION_INCORRECTA", f"{x['id']}: asignado por precio independiente relativo {m(x['asignado'])} frente a {m(x['asigCliente'])} del cliente ({cit['asig']}).", x["difAsig"]))
        if x["varExceso"] is not None and x["varExceso"] > 0.005:
            pr.append(problema("VARIABLE_SIN_RESTRICCION", f"{x['id']}: contraprestación variable incluida por el cliente sin cumplir la restricción ({cit['variable']}).", x["varExceso"]))
        if x["variable"] is not None and x["prob"] is None:
            pr.append(problema("VARIABLE_SIN_PROBABILIDAD", f"{x['id']}: variable estimada sin probabilidad; no se incluye en el precio ({cit['variable']}).", x["variable"]))
        if x["ncNoProv"] > 0.005:
            pr.append(problema("DEVOLUCIONES_NO_PROVISIONADAS", f"{x['id']}: notas de crédito posteriores al cierre superan el pasivo por reembolso estimado ({cit['dev']}; NIA 560).", x["ncNoProv"]))
        if x["modTexto"] or x["importe_modificacion"] is not None:
            if x["modTipo"] is None:
                pr.append(problema("MODIFICACION_SIN_TRATAMIENTO", f"{x['id']}: modificación sin tratamiento documentado (contrato separado, prospectivo o acumulativo; {cit['mod']}).", x["importe_modificacion"] or 0))
    fin_st = [x for x in L if x["significativa"] and x["componente"] is None and x["neto"] is not None]
    if fin_st:
        pr.append(problema("FINANCIACION_SIN_TASA", f"{len(fin_st)} línea(s) con plazo de cobro mayor a {m(umbral)} meses sin tasa de descuento: el componente financiero no se pudo medir ({cit['fin']}).",
                           sum(x["neto"] for x in fin_st)))
    if t["componenteFinanciero"] > 0.005:
        pr.append(problema("FINANCIACION_NO_SEPARADA", f"Componente de financiación {m(t['componenteFinanciero'])} que se presenta como interés y no como ingreso ordinario "
                                                        f"({cit['fin']}); el ajuste lo excluye del ingreso y reconoce el interés devengado {m(t['interesDevengado'])}.", t["componenteFinanciero"]))
    for clave, nombre, reg_p in (("Activo", n_act, act_reg), ("Pasivo", n_pas, pas_reg)):
        d = t[f"dif{clave}"]
        if abs(d) > 0.005:
            pr.append(problema(f"{clave.upper()}_CONTRATO_NO_PRESENTADO", f"{nombre} requerido {m(t[clave.lower() + 'Contrato'])} frente a {m(reg_p or 0)} registrado"
                               + (" (dato del mayor no informado)" if reg_p is None else "") + f" ({cit['ap']}).", d))
    if mayor is None:
        pr.append(problema("SIN_MAYOR", "Ingrese los ingresos según el mayor: sin él se toma el anexo y no se prueba la integridad."))
    elif abs(t["difMayor"]) > 0.005:
        pr.append(problema("DIF_MAYOR", f"El anexo ({m(registrado)}) no concilia con el mayor ({m(mayor)}); investigue la diferencia (NIA 500).", t["difMayor"]))
    if abs(t["ajuste"]) > 0.005:
        pr.append(problema("AJUSTE_INGRESOS", f"Ingreso reconocible del año {m(t['ingresoReconocible'])} frente a {m(registrado)} registrado en las líneas medidas: ajuste {m(t['ajuste'])}.", t["ajuste"]))

    iso = lambda d: d.isoformat() if d else ""
    rows = [{"id": x["id"], "contrato": x["contrato"], "cliente": x["cliente"], "obligacion": x["obligacion"], "modo": x["modo"],
             "asignado": "" if x["asignado"] is None else r2(x["asignado"]), "reconocible": "" if x["recAnio"] is None else r2(x["recAnio"]),
             "registrado": r2(x["registrado"]), "ajuste": "" if x["ajuste"] is None else r2(x["ajuste"]), "_row": x["_row"]} for x in L]
    etiquetas = {
        "ingresoReconocible": "Ingreso reconocible del año (líneas medidas)", "ingresoRegistrado": "Ingreso registrado en el año (anexo)",
        "ingresoMayor": "Ingresos según el mayor", "difMayor": "Diferencia anexo − mayor", "ajuste": "Ajuste propuesto a ingresos",
        "corteAnticipado": "Corte: registrado antes de la transferencia", "corteOmitido": "Corte: transferido sin registrar en el ejercicio",
        "componenteFinanciero": "Componente de financiación a separar", "interesDevengado": "Interés devengado al corte",
        "pasivoReembolso": "Pasivo por reembolso (devoluciones esperadas)" if not s15 else "Provisión por devoluciones esperadas",
        "devolucionesNoProvisionadas": "Notas de crédito posteriores no provisionadas",
        "activoContrato": n_act + " requerido", "activoRegistrado": n_act + (" registrado" if act_reg is not None else " registrado (no informado: se toma 0)"), "difActivo": n_act + ": diferencia",
        "pasivoContrato": n_pas + " requerido", "pasivoRegistrado": n_pas + (" registrado" if pas_reg is not None else " registrado (no informado: se toma 0)"), "difPasivo": n_pas + ": diferencia",
        "difAsignacion": "Diferencias de asignación (absolutas)", "variableExceso": "Variable incluida sin cumplir la restricción",
    }
    detalle = {"cortes": {"actual": corte_a.isoformat()}, "parametros": p, "pymes": pymes, "edicion": ed, "s15": s15, "modelo": modelo,
               "tasa": tasa, "umbral": umbral, "uprob": uprob, "metodo": metodo, "mayor": mayor, "actReg": act_reg, "pasReg": pas_reg,
               "nAct": n_act, "nPas": n_pas, "cit": cit, "contratos": ap,
               "lineas": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in x.items()} for x in L]}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(t[k]) for k in etiquetas}, "labels": etiquetas, "primary": "ajuste",
            "exceptions": pr, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

P = ref("02_Parametros")
DET, PV, ASG, SAT, DEV, FIN, REC, AP, COR, CON = (ref(n) for n in (
    "03_Detalle", "04_Precio_variable", "05_Asignacion", "06_Satisfaccion", "07_Devoluciones", "08_Financiacion",
    "09_Reconocimiento", "10_Activo_pasivo", "11_Corte", "13_Conciliacion"))
_PAR = ["corte", "marco", "modelo", "tasaDescuento", "plazoFinanciacion", "umbralAltamenteProbable", "metodoVariable",
        "ingresoMayor", "activoContratoRegistrado", "pasivoContratoRegistrado"]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
_CON = ["ingresoRegistrado", "ingresoMayor", "difMayor", "ingresoReconocible", "ajuste", "corteAnticipado", "corteOmitido",
        "componenteFinanciero", "interesDevengado", "pasivoReembolso", "devolucionesNoProvisionadas", "activoContrato",
        "activoRegistrado", "difActivo", "pasivoContrato", "pasivoRegistrado", "difPasivo", "difAsignacion", "variableExceso"]
CONF = {k: FILA0 + i for i, k in enumerate(_CON)}


def _pb(k):
    return f"{P}$B${PAR[k]}"


def _rango(hoja_ref: str, col: str, n: int) -> str:
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _op(hoja_ref, celda):
    """Dato opcional: vacío si la celda está en blanco (M22)."""
    return f'IF({hoja_ref}{celda}<>"",{hoja_ref}{celda},"")'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    L, ap = d["lineas"], d["contratos"]
    t = {k: float(v) for k, v in res["totals"].items()}
    n = len(L)
    fin = FILA0 + n - 1
    corte = _pb("corte")
    cit = d["cit"]
    rg = lambda h, c: _rango(h, c, n)

    marco = (MARCO_PYMES + " " + d["edicion"]) if d["pymes"] else MARCO_COMPLETAS
    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Marco contable", marco, "Ficha del encargo: enruta el modelo de reconocimiento"],
        ["Modelo aplicado", d["modelo"], ("«A lo largo del tiempo» = servicios y construcción por grado de terminación (23.14-23.22); "
                                          "«En un momento» = venta de bienes al transferir riesgos y beneficios (23.10)") if d["s15"]
         else "Paso 1 contrato · 2 obligaciones · 3 precio · 4 asignación · 5 satisfacción"],
        [ETIQUETAS_PARAM["tasaDescuento"], d["tasa"], f"{cit['fin']} — tasa de una financiación separada con el cliente al inicio del contrato"],
        [ETIQUETAS_PARAM["plazoFinanciacion"], d["umbral"], "NIIF 15 63 / PYMES 2025 23.38: solución práctica de un año; PYMES 2015: plazo mayor al normal (11.13)"],
        [ETIQUETAS_PARAM["umbralAltamenteProbable"], d["uprob"],
         "No se usa en PYMES 2015: allí se incluye si es probable, más de 50 % (23.10 c-d)" if d["s15"]
         else "«Altamente probable» (NIIF 15 56; PYMES 2025 23.30): la norma no fija un porcentaje; umbral de juicio (VERIFICAR)"],
        [ETIQUETAS_PARAM["metodoVariable"], d["metodo"], "NIIF 15 53; PYMES 2025 23.28"],
        [ETIQUETAS_PARAM["ingresoMayor"], d["mayor"], "Mayor contable (en blanco: se toma el anexo)"],
        [ETIQUETAS_PARAM["activoContratoRegistrado"], d["actReg"], "Mayor contable"],
        [ETIQUETAS_PARAM["pasivoContratoRegistrado"], d["pasReg"], "Mayor contable"],
    ]

    # 03 · Detalle (datos del cliente + contrato válido).
    det = []
    for i, x in enumerate(L):
        r = FILA0 + i
        det.append([x["id"], x["contrato"], x["cliente"], x["obligacion"], x["evidencia"], x["modo"], x["transferencia"], x["registro"],
                    x["psi"], n2(x["precio"]), x["variable"], x["probabilidad"], x["variable_cliente"], x["costo_incurrido"], x["costo_total"],
                    x["avance_cliente"], n2(x["registrado"]), x["anterior"], x["facturado"], x["cobrado"], x["plazo_cobro"], x["devolucion"],
                    x["nc_posterior"], x["modTexto"], x["importe_modificacion"],
                    fx(f'IF(E{r}="No","No",IF(E{r}="","Sin dato","Sí"))', x["valido"])])
    tot_det = ["TOTAL"] + [""] * 7 + [None, suma("J", fin, sum(x["precio"] for x in L))] + [None] * 6 + \
              [suma("Q", fin, t["ingresoRegistrado"]), None, suma("S", fin, sum(x["facturado"] or 0 for x in L)),
               suma("T", fin, sum(x["cobrado"] or 0 for x in L))] + [None] * 3 + ["", None, ""]

    # 04 · Precio y variable.
    pv = []
    cond = (lambda r: f"E{r}>0.5") if d["s15"] else (lambda r: f"E{r}>={_pb('umbralAltamenteProbable')}/100")
    for i, x in enumerate(L):
        r = FILA0 + i
        pv.append([x["id"], x["contrato"], fx(f"{DET}J{r}", n2(x["precio"])), fx(_op(DET, f"K{r}"), x["variable"]),
                   fx(f'IF({DET}L{r}<>"",{DET}L{r}/100,"")', x["prob"]),
                   fx(f'IF(OR(D{r}="",E{r}=""),0,IF({cond(r)},IF({_pb("metodoVariable")}="Valor esperado",D{r}*E{r},D{r}),0))', x["varIncluida"]),
                   fx(_op(DET, f"M{r}"), x["variable_cliente"]),
                   fx(f'IF(G{r}="","",MAX(G{r}-F{r},0))', x["varExceso"]),
                   fx(f"SUMIF($B${FILA0}:$B${fin},B{r},$C${FILA0}:$C${fin})+SUMIF($B${FILA0}:$B${fin},B{r},$F${FILA0}:$F${fin})", x["tp"])])
    tot_pv = ["TOTAL", "", suma("C", fin, sum(x["precio"] for x in L)), None, None, suma("F", fin, sum(x["varIncluida"] for x in L)),
              None, suma("H", fin, t["variableExceso"]), None]

    # 05 · Asignación.
    asg = []
    for i, x in enumerate(L):
        r = FILA0 + i
        asg.append([x["id"], x["contrato"], fx(f'IF({DET}I{r}<>"",{DET}I{r},{DET}J{r})', x["psiEf"]),
                    fx(f"SUMIF($B${FILA0}:$B${fin},B{r},$C${FILA0}:$C${fin})", x["sumPsi"]), fx(f"{PV}I{r}", x["tp"]),
                    fx(f'IF(D{r}=0,"",E{r}*C{r}/D{r})', x["asignado"]),
                    fx(f'{PV}C{r}+IF({PV}G{r}="",0,{PV}G{r})', x["asigCliente"]),
                    fx(f'IF(F{r}="","",F{r}-G{r})', x["difAsig"]),
                    fx(f"COUNTIF($B${FILA0}:$B${fin},B{r})", x["nLineas"]),
                    fx(f'IF(OR(H{r}="",I{r}<2),0,ABS(H{r}))', abs(x["difAsig"]) if x["difAsig"] is not None and x["nLineas"] > 1 else 0)])
    tot_asg = ["TOTAL", "", None, None, None, suma("F", fin, sum(x["asignado"] or 0 for x in L)), suma("G", fin, sum(x["asigCliente"] for x in L)),
               None, None, suma("J", fin, sum(abs(x["difAsig"]) for x in L if x["difAsig"] is not None and x["nLineas"] > 1))]

    # 06 · Satisfacción.
    sat = []
    for i, x in enumerate(L):
        r = FILA0 + i
        sat.append([x["id"], fx(f"{DET}F{r}", x["modo"]),
                    fx(f'IF(B{r}="{TIEMPO}",IF(AND({DET}N{r}<>"",N({DET}O{r})>0),MIN({DET}N{r}/{DET}O{r},1),""),"")', x["avance"]),
                    fx(f'IF({DET}P{r}<>"",{DET}P{r}/100,"")', x["avanceCli"]),
                    fx(f'IF(OR(C{r}="",D{r}=""),"",D{r}-C{r})', x["difAvance"]),
                    fx(f'IF(B{r}="{TIEMPO}","",IF({DET}G{r}="","",IF({DET}G{r}<={corte},"Sí","No")))', x["transferido"]),
                    fx(f'IF({DET}Z{r}="No",0,IF(B{r}="{TIEMPO}",C{r},IF(F{r}="","",IF(F{r}="Sí",1,0))))', x["factor"]),
                    fx(f'IF(OR(G{r}="",{ASG}F{r}=""),"",{ASG}F{r}*G{r})', x["bruto"]),
                    fx(f'IF(AND(B{r}="{TIEMPO}",{DET}O{r}<>"",{ASG}F{r}<>""),MAX({DET}O{r}-{ASG}F{r},0),0)', x["perdida"])])
    tot_sat = ["TOTAL", "", None, None, None, "", None, suma("H", fin, sum(x["bruto"] or 0 for x in L)), suma("I", fin, sum(x["perdida"] for x in L))]

    # 07 · Devoluciones.
    dev = []
    for i, x in enumerate(L):
        r = FILA0 + i
        dev.append([x["id"], fx(f"{SAT}H{r}", x["bruto"]), fx(f'IF({DET}V{r}<>"",{DET}V{r}/100,0)', x["dev"]),
                    fx(f'IF(B{r}="","",B{r}*C{r})', x["reembolso"]), fx(f'IF(B{r}="","",B{r}-D{r})', x["neto"]),
                    fx(_op(DET, f"W{r}"), x["nc_posterior"]), fx(f'IF(F{r}="",0,MAX(F{r}-N(D{r}),0))', x["ncNoProv"])])
    tot_dev = ["TOTAL", suma("B", fin, sum(x["bruto"] or 0 for x in L)), None, suma("D", fin, t["pasivoReembolso"]),
               suma("E", fin, sum(x["neto"] or 0 for x in L)), suma("F", fin, sum(x["nc_posterior"] or 0 for x in L)),
               suma("G", fin, t["devolucionesNoProvisionadas"])]

    # 08 · Financiación.
    tasa = _pb("tasaDescuento")
    fn = []
    for i, x in enumerate(L):
        r = FILA0 + i
        fn.append([x["id"], fx(f"{DEV}E{r}", x["neto"]), fx(_op(DET, f"U{r}"), x["plazo_cobro"]),
                   fx(f'IF(AND(C{r}<>"",N(C{r})>{_pb("plazoFinanciacion")}),"Sí","No")', "Sí" if x["significativa"] else "No"),
                   fx(f'IF({tasa}="","",{tasa}/100)', x["tasa"]),
                   fx(f'IF(B{r}="","",IF(D{r}="Sí",IF(E{r}="",B{r},B{r}/(1+E{r})^(C{r}/12)),B{r}))', x["vp"]),
                   fx(f'IF(B{r}="","",IF(D{r}="No",0,IF(E{r}="","",B{r}-F{r})))', x["componente"]),
                   fx(f'IF(AND(D{r}="Sí",{DET}G{r}<>""),MAX(MIN({corte}-{DET}G{r},C{r}*365/12),0),0)', x["diasDev"]),
                   fx(f'IF(G{r}="","",IF(G{r}=0,0,F{r}*((1+E{r})^(H{r}/365)-1)))', x["interes"])])
    tot_fn = ["TOTAL", suma("B", fin, sum(x["neto"] or 0 for x in L)), None, "", None, suma("F", fin, sum(x["vp"] or 0 for x in L)),
              suma("G", fin, t["componenteFinanciero"]), None, suma("I", fin, t["interesDevengado"])]

    # 09 · Reconocible vs registrado.
    rec = []
    for i, x in enumerate(L):
        r = FILA0 + i
        rec.append([x["id"], x["contrato"], fx(f"{FIN}F{r}", x["vp"]), fx(f'IF({DET}R{r}<>"",{DET}R{r},0)', x["anteriorEf"]),
                    fx(f'IF(C{r}="","",C{r}-D{r})', x["recAnio"]), fx(f"{DET}Q{r}", n2(x["registrado"])),
                    fx(f'IF(E{r}="","",E{r}-F{r})', x["ajuste"])])
    tot_rec = ["TOTAL", "", suma("C", fin, sum(x["vp"] or 0 for x in L)), suma("D", fin, sum(x["anteriorEf"] for x in L)),
               suma("E", fin, t["ingresoReconocible"]), suma("F", fin, t["ingresoRegistrado"]), suma("G", fin, t["ajuste"])]

    # 10 · Activo / pasivo del contrato (por contrato).
    apr = []
    for i, a in enumerate(ap):
        r = FILA0 + i
        si = lambda h, c: f"SUMIF({rg(DET, 'B')},A{r},{rg(h, c)})"
        apr.append([a["contrato"], a["cliente"], fx(si(SAT, "H"), a["bruto"]), fx(si(DET, "S"), a["facturado"]), fx(si(DET, "T"), a["cobrado"]),
                    fx(f'IF(J{r}>0,"",C{r}-D{r})', a["posicion"]), fx(f'IF(F{r}="","",MAX(F{r},0))', a["activo"]),
                    fx(f'IF(F{r}="","",MAX(-F{r},0))', a["pasivo"]),
                    fx(f"D{r}-E{r}", a["cxc"]), fx(f'COUNTIFS({rg(DET, "B")},A{r},{rg(SAT, "H")},"")', a["sinMedir"])])
    fin_ap = FILA0 + len(ap) - 1
    tot_ap = ["TOTAL", "", suma("C", fin_ap, sum(a["bruto"] for a in ap)), suma("D", fin_ap, sum(a["facturado"] for a in ap)),
              suma("E", fin_ap, sum(a["cobrado"] for a in ap)), suma("F", fin_ap, sum(a["posicion"] or 0 for a in ap)),
              suma("G", fin_ap, t["activoContrato"]), suma("H", fin_ap, t["pasivoContrato"]), suma("I", fin_ap, sum(a["cxc"] for a in ap)), None]

    # 11 · Corte (líneas en un momento con fecha de registro y de transferencia).
    cor = []
    for i, x in enumerate(L):
        if not x["enCorte"]:
            continue
        r, rd = FILA0 + len(cor), FILA0 + i
        cor.append([x["id"], x["contrato"], x["registro"], x["transferencia"], fx(f"{DET}Q{rd}", n2(x["registrado"])),
                    fx(f'IF(C{r}<={corte},"Sí","No")', "Sí" if x["regEj"] else "No"),
                    fx(f'IF(D{r}<={corte},"Sí","No")', "Sí" if x["trEj"] else "No"),
                    fx(f'IF(AND(F{r}="Sí",G{r}="No"),E{r},0)', x["anticipado"]),
                    fx(f'IF(AND(F{r}="No",G{r}="Sí"),N({SAT}H{rd}),0)', x["omitido"])])
    fin_cor = FILA0 + len(cor) - 1
    tot_cor = (["TOTAL", "", "", "", suma("E", fin_cor, sum(x["registrado"] for x in L if x["enCorte"])), "", "",
                suma("H", fin_cor, t["corteAnticipado"]), suma("I", fin_cor, t["corteOmitido"])] if cor else None)

    # 12 · Modificaciones.
    trat = {"Contrato separado": "Nuevo contrato: bienes diferenciados a su precio independiente (NIIF 15 20; PYMES 2025 23A.2-23A.4)",
            "Prospectivo": "Terminación del contrato original y nuevo contrato para lo pendiente (NIIF 15 21 a)",
            "Acumulativo": "Parte del contrato existente; ajuste acumulado del ingreso a la fecha (NIIF 15 21 b)"}
    mods = []
    for i, x in enumerate(L):
        if not (x["modTexto"] or x["importe_modificacion"] is not None):
            continue
        rd = FILA0 + i
        tipo = x["modTipo"]
        nota = (trat[tipo] if not d["s15"] else f"{tipo}: {cit['mod']}") if tipo else "Falta documentar el tratamiento"
        mods.append([x["id"], x["contrato"], x["modTexto"], fx(_op(DET, f"Y{rd}"), x["importe_modificacion"]), nota,
                     "Documentado" if tipo else "Pendiente"])

    # 13 · Conciliación.
    cb = lambda k: f"B{CONF[k]}"
    mayor = _pb("ingresoMayor")
    con_def = {
        "ingresoRegistrado": (f"SUM({rg(DET, 'Q')})", "Anexo de contratos"),
        "ingresoMayor": (f'IF({mayor}="",{cb("ingresoRegistrado")},{mayor})', "Parámetros (en blanco: el anexo)"),
        "difMayor": (f"{cb('ingresoRegistrado')}-{cb('ingresoMayor')}", "Integridad del anexo (NIA 500)"),
        "ingresoReconocible": (f"{REC}E{fin + 1}", "09_Reconocimiento"),
        "ajuste": (f"{REC}G{fin + 1}", "Incluye corte, asignación, variable, avance, devoluciones y financiación"),
        "corteAnticipado": (f"{COR}H{fin_cor + 1}" if cor else "0", f"Ya incluido en el ajuste ({cit['corte']})"),
        "corteOmitido": (f"{COR}I{fin_cor + 1}" if cor else "0", f"Ya incluido en el ajuste ({cit['corte']})"),
        "componenteFinanciero": (f"{FIN}G{fin + 1}", cit["fin"]),
        "interesDevengado": (f"{FIN}I{fin + 1}", "Ingreso financiero, separado del ingreso ordinario"),
        "pasivoReembolso": (f"{DEV}D{fin + 1}", cit["dev"]),
        "devolucionesNoProvisionadas": (f"{DEV}G{fin + 1}", "Notas de crédito posteriores (NIA 560)"),
        "activoContrato": (f"{AP}G{fin_ap + 1}", cit["ap"]),
        "activoRegistrado": (_pb("activoContratoRegistrado"), "Parámetros"),
        "difActivo": (f"{cb('activoContrato')}-{cb('activoRegistrado')}", "Reclasificación de presentación"),
        "pasivoContrato": (f"{AP}H{fin_ap + 1}", cit["ap"]),
        "pasivoRegistrado": (_pb("pasivoContratoRegistrado"), "Parámetros"),
        "difPasivo": (f"{cb('pasivoContrato')}-{cb('pasivoRegistrado')}", "Reclasificación de presentación"),
        "difAsignacion": (f"{ASG}J{fin + 1}", cit["asig"]),
        "variableExceso": (f"{PV}H{fin + 1}", cit["variable"]),
    }
    con = [[res["labels"][k], fx(con_def[k][0], t[k]), con_def[k][1]] for k in _CON]

    # 14 · Asientos.
    asientos = []

    def asiento(titulo, lineas):
        for i, (cta, formula, valor, debe) in enumerate(lineas):
            v = fx(formula, n2(valor))
            asientos.append([titulo if i == 0 else "", cta, v if debe else None, None if debe else v])

    contra = f"{d['nAct']} / {d['nPas']} / pasivo por reembolso / cuentas por cobrar (ver 07 y 10)"
    aj = f"ABS({CON}{cb('ajuste')})"
    if t["ajuste"] < -0.005:
        asiento("1 · Menor ingreso reconocible", [("Ingresos de actividades ordinarias", aj, -t["ajuste"], True), (contra, aj, -t["ajuste"], False)])
    elif t["ajuste"] > 0.005:
        asiento("1 · Ingreso reconocible no registrado", [(contra, aj, t["ajuste"], True), ("Ingresos de actividades ordinarias", aj, t["ajuste"], False)])
    if t["interesDevengado"] > 0.005:
        ie = f"{CON}{cb('interesDevengado')}"
        asiento("2 · Interés devengado del componente de financiación", [("Cuentas por cobrar (costo amortizado)", ie, t["interesDevengado"], True),
                                                                          ("Ingresos financieros por intereses", ie, t["interesDevengado"], False)])

    ref_res = {k: f"{CON}{cb(k)}" for k in res["labels"]}
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Detalle", "Detalle por obligación",
             [["Línea", "t"], ["Contrato", "t"], ["Cliente", "t"], ["Obligación", "t"], ["Evidencia del contrato", "t"], ["Modo", "t"],
              ["Transferencia del control", "d"], ["Registro del ingreso", "d"], ["Precio de venta independiente", "n"], ["Precio del contrato", "n"],
              ["Variable estimada", "n"], ["Probabilidad (%)", "x"], ["Variable del cliente", "n"], ["Costos incurridos", "n"], ["Costos totales", "n"],
              ["Avance del cliente (%)", "x"], ["Registrado en el año", "n"], ["Reconocido años anteriores", "n"], ["Facturado acumulado", "n"],
              ["Cobrado acumulado", "n"], ["Plazo de cobro (meses)", "x"], ["Devoluciones esperadas (%)", "x"], ["NC posteriores", "n"],
              ["Modificación", "t"], ["Importe modificación", "n"], ["Contrato válido", "t"]], det, tot_det),
        hoja("04_Precio_variable", "Precio y contraprestación variable",
             [["Línea", "t"], ["Contrato", "t"], ["Precio fijo", "n"], ["Variable estimada", "n"], ["Probabilidad", "p"],
              ["Variable incluida (restringida)", "n"], ["Variable del cliente", "n"], ["Exceso sobre la restricción", "n"],
              ["Precio de la transacción del contrato", "n"]], pv, tot_pv),
        hoja("05_Asignacion", "Asignación del precio",
             [["Línea", "t"], ["Contrato", "t"], ["Precio independiente usado", "n"], ["Suma del contrato", "n"], ["Precio de la transacción", "n"],
              ["Asignado (relativo)", "n"], ["Asignación del cliente", "n"], ["Diferencia", "n"], ["Obligaciones del contrato", "i"],
              ["Diferencia absoluta", "n"]], asg, tot_asg),
        hoja("06_Satisfaccion", "Satisfacción y porcentaje de avance",
             [["Línea", "t"], ["Modo", "t"], ["Avance recalculado (costos)", "p"], ["Avance del cliente", "p"], ["Diferencia de avance", "p"],
              ["Control transferido al corte", "t"], ["Factor de satisfacción", "p"], ["Reconocible bruto acumulado", "n"],
              ["Pérdida esperada del contrato", "n"]], sat, tot_sat),
        hoja("07_Devoluciones", "Devoluciones y notas de crédito",
             [["Línea", "t"], ["Reconocible bruto", "n"], ["Devolución esperada", "p"], ["Pasivo por reembolso", "n"],
              ["Reconocible neto de devoluciones", "n"], ["NC posteriores al cierre", "n"], ["NC no provisionadas", "n"]], dev, tot_dev),
        hoja("08_Financiacion", "Componente de financiación",
             [["Línea", "t"], ["Reconocible neto", "n"], ["Plazo de cobro (meses)", "x"], ["Financiación significativa", "t"], ["Tasa anual", "p"],
              ["Valor presente (ingreso ordinario)", "n"], ["Componente de financiación", "n"], ["Días devengados", "x"],
              ["Interés devengado al corte", "n"]], fn, tot_fn),
        hoja("09_Reconocimiento", "Ingreso reconocible vs registrado",
             [["Línea", "t"], ["Contrato", "t"], ["Reconocible acumulado", "n"], ["Reconocido años anteriores", "n"], ["Reconocible del año", "n"],
              ["Registrado en el año", "n"], ["Ajuste", "n"]], rec, tot_rec),
        hoja("10_Activo_pasivo", "Activo y pasivo del contrato",
             [["Contrato", "t"], ["Cliente", "t"], ["Reconocible bruto acumulado", "n"], ["Facturado", "n"], ["Cobrado", "n"], ["Posición", "n"],
              [d["nAct"], "n"], [d["nPas"], "n"], ["Cuenta por cobrar", "n"], ["Obligaciones sin medir", "i"]], apr, tot_ap),
        hoja("11_Corte", "Corte de ingresos",
             [["Línea", "t"], ["Contrato", "t"], ["Registro", "d"], ["Transferencia", "d"], ["Registrado en el año", "n"],
              ["Registrado en el ejercicio", "t"], ["Transferido en el ejercicio", "t"], ["Registrado antes de transferir", "n"],
              ["Transferido sin registrar", "n"]], cor, tot_cor),
        hoja("12_Modificaciones", "Modificaciones de contratos",
             [["Línea", "t"], ["Contrato", "t"], ["Modificación informada", "t"], ["Importe", "n"], ["Tratamiento", "t"], ["Estado", "t"]], mods),
        hoja("13_Conciliacion", "Conciliación y ajustes", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], con),
        hoja("14_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos),
        hoja("15_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -----------------------------------------------------------------

def _prog(code, objective, risk, assertion, procedure, evidence, criterion, source):
    return {"code": code, "objective": objective, "risk": risk, "assertion": assertion, "procedure": procedure,
            "evidence": evidence, "criterion": criterion, "source": source}


def definicion() -> dict:
    contenido = ("Una fila por obligación o entregable de cada contrato/factura: línea, contrato, cliente, modo (en un momento / a lo largo "
                 "del tiempo), precio del contrato asignado por el cliente e ingreso registrado en el año; y, cuando existan: evidencia del "
                 "contrato, fechas de transferencia del control y de registro, precio de venta independiente, variable estimada con su "
                 "probabilidad y la incluida por el cliente, costos incurridos y totales, avance del cliente, ingreso de años anteriores, "
                 "facturado y cobrado acumulados, plazo de cobro, devoluciones esperadas, notas de crédito posteriores y modificaciones.")
    return {
        "name": "Ingresos · contratos con clientes (existencia, precio, asignación, satisfacción, corte y devoluciones)",
        "area": "Ingresos",
        "processor": "ingresos_contratos",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Recalcula por obligación el ingreso reconocible al corte y lo compara con el registrado: valida la existencia del contrato, "
                    "restringe la contraprestación variable, asigna el precio por precio de venta independiente relativo, mide el avance por "
                    "costos o la transferencia del control, descuenta devoluciones esperadas y el componente de financiación significativo, "
                    "prueba el corte, determina el activo o pasivo del contrato y concilia con el mayor. NIIF completas y PYMES 2025 siguen el "
                    "modelo de cinco pasos (NIIF 15; Sección 23 revisada); PYMES 2015 sigue riesgos y beneficios y grado de terminación "
                    "(Sección 23 anterior), con la variable incluida si es probable."),
        "source": {"organization": "IFRS Foundation (texto en español: Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIIF 15 párr. 9, 15-16 (contrato), 18-21 (modificaciones), 22-30 (obligaciones), 31-38 (satisfacción), "
                                "39-45 y B14-B19 (medición del avance), 47-59 (precio y variable; restricción 56-58), 60-65 (financiación; "
                                "solución práctica 63; presentación 65), 73-86 (asignación, 76-80 precio independiente), 105-109 (activo y "
                                "pasivo del contrato), B20-B27 (devoluciones). NIC 37 66-69 (contratos onerosos)."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015, Sección 23: 23.3-23.5 (valor razonable de la contraprestación, financiación "
                                      "implícita), 23.8 (componentes), 23.10-23.13 (venta de bienes), 23.14-23.16 (servicios), 23.17-23.20 "
                                      "(construcción), 23.21-23.22 (grado de terminación), 23.26 (pérdida esperada), 23.30-23.32 (revelación). "
                                      "NIIF para las PYMES 2025, Sección 23 revisada «Ingresos de actividades ordinarias procedentes de contratos "
                                      "con clientes»: 23.6-23.13 (contrato; modificaciones 23.12 y 23A.2-23A.4), 23.14-23.22 (promesas), 23.23-23.38 "
                                      "(precio; variable 23.26-23.31, reembolso 23.33-23.35, financiación 23.36-23.38), 23.39-23.48 (asignación), "
                                      "23.49-23.67 (satisfacción; a lo largo del tiempo 23.54-23.56, en un momento 23.57-23.58, avance 23.62-23.66), "
                                      "23.77-23.80 (activo y pasivo del contrato). Numeración leída en el material educativo oficial en inglés "
                                      "(módulos 23 de 2015 y 2025, ifrs.org); VERIFICAR la redacción en la versión en español y el Apéndice 23A."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 240", "section": "párr. 26-27 (VERIFICAR)", "requirement": "Presunción de riesgo de fraude en el reconocimiento de ingresos."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del anexo de contratos contra el mayor."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13 y 17-30", "requirement": "Estimaciones: variable, avance por costos, devoluciones y tasa de descuento."},
            {"document": "NIA 560", "section": "párr. 6", "requirement": "Notas de crédito y devoluciones posteriores al cierre."},
            {"document": "NIA 330", "section": "párr. 18-20 (VERIFICAR)", "requirement": "Procedimientos sustantivos de corte y ocurrencia."},
        ],
        "calculo": [
            "Contrato válido: sin evidencia de contrato aprobado y con sustancia («No») el ingreso reconocible es cero.",
            "Variable incluida = importe más probable (o valor esperado = importe × probabilidad) solo si la probabilidad ≥ umbral de «altamente probable»; PYMES 2015: si es mayor a 50 %.",
            "Precio de la transacción del contrato = Σ precios fijos + Σ variable incluida.",
            "Asignado = precio de la transacción × precio independiente ÷ Σ precios independientes del contrato (sin precio independiente se usa el precio del contrato).",
            "Avance = costos incurridos ÷ costos totales estimados (máximo 100 %); en un momento: 100 % si el control se transfirió hasta el corte, 0 % si no.",
            "Reconocible bruto = asignado × avance; pasivo por reembolso = bruto × devolución esperada; neto = bruto − reembolso.",
            "Financiación significativa si el plazo de cobro supera el umbral: ingreso = neto ÷ (1 + tasa)^(plazo ÷ 12); componente = neto − valor presente; interés devengado = VP × ((1 + tasa)^(días desde la transferencia ÷ 365) − 1).",
            "Reconocible del año = reconocible acumulado − reconocido en años anteriores; ajuste = reconocible del año − registrado.",
            "Por contrato: posición = reconocible bruto − facturado; positiva = activo del contrato; negativa = pasivo del contrato (ingreso diferido).",
            "Corte: registro en el ejercicio con transferencia posterior (anticipado) y transferencia en el ejercicio con registro posterior (omitido).",
        ],
        "fields": _CONTRATOS, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            _prog("ING-01", "Existencia del contrato (REV-FULL-01 / REV-SME25-01)", "Ingresos sin acuerdo exigible", "Ocurrencia",
                  "Obtener contratos u órdenes aprobadas y evaluar los criterios de existencia", "Contratos, órdenes de compra, adendas",
                  "Ingreso solo con contrato válido", "NIIF 15 9 · PYMES 2025 23.7 · PYMES 2015 23.10"),
            _prog("ING-02", "Obligaciones y asignación (REV-FULL-02, 06 / REV-SME25-02, 04)", "Precio mal distribuido entre entregables", "Exactitud",
                  "Identificar obligaciones diferenciadas y recalcular la asignación por precio de venta independiente relativo",
                  "Listas de precios, cotizaciones", "Diferencia de asignación cuantificada", "NIIF 15 22-30, 73-80 · PYMES 2025 23.14-23.22, 23.42"),
            _prog("ING-03", "Precio y contraprestación variable (REV-FULL-03, 04 / REV-SME25-03, 06 / REV-SME15-05)", "Variable reconocida sin restricción",
                  "Exactitud / Valoración", "Revisar bonos, descuentos y rappels y su probabilidad; aplicar la restricción", "Contratos, historia de cumplimiento",
                  "Variable altamente probable", "NIIF 15 50-59 · PYMES 2025 23.26-23.31 · PYMES 2015 23.3"),
            _prog("ING-04", "Satisfacción y avance (REV-FULL-07, 08 / REV-SME25-05 / REV-SME15-01..03)", "Avance sobrestimado o entrega no ocurrida",
                  "Ocurrencia / Exactitud", "Recalcular el avance por costos y verificar la transferencia del control", "Presupuestos, costos incurridos, actas de entrega",
                  "Avance y transferencia recalculados", "NIIF 15 31-45 · PYMES 2025 23.49-23.66 · PYMES 2015 23.10-23.22"),
            _prog("ING-05", "Corte (REV-03)", "Ingresos en el período equivocado", "Corte",
                  "Comparar fecha de registro con fecha de transferencia alrededor del cierre", "Guías de remisión, actas, facturas",
                  "Ingreso en el período de la transferencia", "NIIF 15 38 · NIA 330"),
            _prog("ING-06", "Devoluciones y notas de crédito (REV-04 / REV-FULL-11 / REV-SME15-07)", "Devoluciones no provisionadas", "Valoración",
                  "Evaluar la tasa de devolución esperada y cotejar notas de crédito posteriores al cierre", "Estadística de devoluciones, NC posteriores",
                  "Pasivo por reembolso suficiente", "NIIF 15 B20-B27 · PYMES 2025 23.33-23.35 · NIA 560"),
            _prog("ING-07", "Componente de financiación (REV-FULL-05 / REV-SME15-06)", "Financiación presentada como ingreso ordinario", "Clasificación",
                  "Identificar cobros diferidos más allá del umbral y descontar a la tasa de mercado", "Contratos, tasas de mercado",
                  "Interés separado del ingreso", "NIIF 15 60-65 · PYMES 2025 23.36-23.38 · PYMES 2015 23.5"),
            _prog("ING-08", "Activo y pasivo del contrato (REV-FULL-12)", "Presentación incorrecta", "Presentación",
                  "Determinar por contrato la posición reconocido − facturado y compararla con el mayor", "Facturación, mayor",
                  "Activo/pasivo presentados", "NIIF 15 105-109 · PYMES 2025 23.77-23.80"),
            _prog("ING-09", "Modificaciones (REV-FULL-09)", "Adendas mal contabilizadas", "Exactitud",
                  "Revisar adendas y su tratamiento (separado, prospectivo, acumulativo)", "Adendas, órdenes de cambio",
                  "Tratamiento documentado", "NIIF 15 18-21 · PYMES 2025 23.12, 23A.2-23A.4"),
            _prog("ING-10", "Sumaria e integridad (REV-01, REV-02)", "Anexo que no respalda el mayor", "Integridad",
                  "Conciliar el anexo de contratos con los ingresos del mayor", "Mayor de ingresos", "Diferencia explicada", "NIA 500 párr. 9"),
        ],
        "requests": [
            req("RQ-001", "Anexo de contratos por obligación al corte", "contratos", "ING-01", "Población a medir y conciliar con el mayor", content=contenido),
            req("RQ-002", "Mayor de ingresos, activo y pasivo del contrato", None, "ING-10", "Conciliación e importes registrados", formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-003", "Contratos, órdenes de compra y adendas", None, "ING-01", "Existencia, obligaciones, precio y modificaciones", formats=("pdf",), use="soporte"),
            req("RQ-004", "Guías de remisión y actas de entrega alrededor del cierre", None, "ING-05", "Transferencia del control y corte", formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-005", "Presupuestos y costos incurridos de contratos a lo largo del tiempo", None, "ING-04", "Porcentaje de avance", formats=("xlsx",), use="soporte", required=False),
            req("RQ-006", "Notas de crédito emitidas después del cierre y estadística de devoluciones", None, "ING-06", "Devoluciones esperadas", formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-007", "Listas de precios o cotizaciones (precio de venta independiente)", None, "ING-02", "Asignación del precio", formats=("pdf", "xlsx"), use="soporte", required=False),
            req("RQ-008", "Sustento de la tasa de descuento de ventas a plazo", None, "ING-07", "Componente de financiación", formats=("pdf",), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) -------------------------------------------------------

def _ej(id, contrato, cliente, modo, precio, registrado, **extra):
    return {"id": id, "contrato": contrato, "cliente": cliente, "modo": modo, "precio": precio, "registrado": registrado, "_row": 2, **extra}


# Corte 2025-12-31, tasa 10 %, umbral 12 meses, altamente probable 75 %.
# C-01: PVI 100.000 + 25.000, precio 100.000 → equipo 80.000, mantenimiento 20.000 × 25 % = 5.000.
# C-02: bono 50.000 al 60 % (excluido) → 500.000 × 45 % = 225.000 (cliente 50 % de 550.000 = 275.000).
# C-05: 121.000 a 24 meses → VP 121.000 ÷ 1,21 = 100.000; componente 21.000.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tasaDescuento": 10, "plazoFinanciacion": 12, "umbralAltamenteProbable": 75,
                   "metodoVariable": "Importe más probable", "ingresoMayor": 670000, "activoContratoRegistrado": 20000},
    "datasets": {"contratos": [
        _ej("C-01-1", "C-01", "Comercial Andina", "En un momento", "90000", "90000", obligacion="Equipo", evidencia="Sí", psi="100000",
            fecha_transferencia="2025-11-15", fecha_registro="2025-11-15", facturado="90000", cobrado="60000"),
        _ej("C-01-2", "C-01", "Comercial Andina", "A lo largo del tiempo", "10000", "2500", obligacion="Mantenimiento 12 meses", evidencia="Sí",
            psi="25000", costo_incurrido="3000", costo_total="12000", avance_cliente="25", facturado="10000"),
        _ej("C-02-1", "C-02", "Constructora Sur", "A lo largo del tiempo", "500000", "275000", obligacion="Obra civil", evidencia="Sí", psi="500000",
            variable="50000", probabilidad="60", variable_cliente="50000", costo_incurrido="180000", costo_total="400000", avance_cliente="50",
            facturado="200000", cobrado="150000"),
        _ej("C-03-1", "C-03", "Distribuidora Norte", "En un momento", "30000", "30000", obligacion="Mercadería", evidencia="Sí",
            fecha_transferencia="2026-01-05", fecha_registro="2025-12-28", facturado="30000"),
        _ej("C-04-1", "C-04", "Retail Express", "En un momento", "40000", "40000", obligacion="Mercadería con derecho a devolución", evidencia="Sí",
            fecha_transferencia="2025-12-10", fecha_registro="2025-12-10", devolucion="5", nc_posterior="3500", facturado="40000", cobrado="20000"),
        _ej("C-05-1", "C-05", "Agro Plazo", "En un momento", "121000", "121000", obligacion="Maquinaria a 24 meses", evidencia="Sí",
            fecha_transferencia="2025-07-01", fecha_registro="2025-07-01", plazo_cobro="24", facturado="121000"),
        _ej("C-06-1", "C-06", "Servicios Beta", "A lo largo del tiempo", "15000", "15000", obligacion="Consultoría", evidencia="No",
            costo_incurrido="5000", costo_total="5000", facturado="15000", cobrado="15000"),
        _ej("C-07-1", "C-07", "Tecnología Gama", "En un momento", "12000", "0", obligacion="Equipos", evidencia="Sí",
            fecha_transferencia="2025-12-20", fecha_registro="2026-01-03"),
        _ej("C-08-1", "C-08", "Software Delta", "A lo largo del tiempo", "48000", "26000", obligacion="Implementación", costo_incurrido="24000",
            costo_total="32000", avance_cliente="75", anterior="10000", facturado="40000", cobrado="40000", modificacion="Prospectivo",
            importe_modificacion="8000"),
        _ej("C-09-1", "C-09", "Mantenimientos Épsilon", "En un momento", "6000", "6000", obligacion="Repuestos", evidencia="Sí",
            fecha_transferencia="2025-12-01", fecha_registro="2025-12-01", facturado="6000", cobrado="6000", modificacion="Adenda de precio",
            importe_modificacion="1000"),
        _ej("C-09-2", "C-09", "Mantenimientos Épsilon", "A lo largo del tiempo", "4000", "2000", obligacion="Servicio técnico", evidencia="Sí",
            psi="4000", costo_incurrido="1000", costo_total="2000", facturado="4000", cobrado="4000"),
        _ej("C-10-1", "C-10", "Obra Zeta", "A lo largo del tiempo", "80000", "26666.67", obligacion="Obra menor", evidencia="Sí", psi="80000",
            costo_incurrido="30000", costo_total="90000", facturado="20000"),
        _ej("C-11-1", "C-11", "Servicios Theta", "En un momento", "20000", "25000", obligacion="Entrega con bono", evidencia="Sí",
            variable="5000", probabilidad="90", variable_cliente="5000", fecha_transferencia="2025-10-01", fecha_registro="2025-10-01",
            facturado="25000", cobrado="25000"),
        _ej("C-12-1", "C-12", "Comercial Iota", "En un momento", "9000", "9000", obligacion="Mercadería", evidencia="Sí", facturado="9000"),
    ]},
}

ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025_valor_esperado", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025",
                                                        "metodoVariable": "Valor esperado", "umbralAltamenteProbable": 55}, EJEMPLO["corte"]),
    ("completas_sin_tasa_ni_mayor", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "tasaDescuento": None, "ingresoMayor": None,
                                                          "activoContratoRegistrado": None, "pasivoContratoRegistrado": 50000}, EJEMPLO["corte"]),
]
