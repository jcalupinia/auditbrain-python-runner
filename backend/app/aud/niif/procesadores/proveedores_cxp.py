"""Proveedores y cuentas por pagar: pasivos no registrados, pagos posteriores, confirmación, aging,
corte de compras, costo amortizado, intereses implícitos y clasificación corriente / no corriente.

Dos anexos alimentan las pruebas:

- ``proveedores`` (principal): el auxiliar por documento al corte.
  1. Aging: días desde el vencimiento y tramo (mismos tramos que la cartera de clientes).
  2. Pagos posteriores (NIA 500/505): pago con fecha posterior al corte, hasta el saldo; un pago
     posterior mayor al saldo registrado sugiere un pasivo subestimado.
  3. Confirmación de proveedores (NIA 505): saldo confirmado − saldo en libros.
  4. Corte de compras: el pasivo existe desde la recepción del bien o servicio; un documento del
     auxiliar con recepción posterior al corte es una compra registrada antes de la recepción.
  5. Costo amortizado e intereses implícitos (NIIF 9 4.2.1, 5.1.1, B5.1.1; PYMES 11.13): si el plazo
     supera el umbral de financiación, el pasivo inicial es el valor presente del pago descontado a la
     tasa de mercado; TIE = esa tasa (un solo pago al vencimiento); interés = pasivo inicial × TIE por el
     tiempo transcurrido; cierre = inicial + interés − pagos (el saldo informado ya es el pendiente);
     financiación implícita = nominal − valor presente.
  6. Clasificación (NIC 1 69–70; PYMES 4.7–4.8): no corriente la porción que vence después de
     max(12 meses, ciclo normal de operación); los saldos deudores (anticipos) se reclasifican al activo.
- ``pagos_posteriores``: búsqueda de pasivos no registrados. Pago o factura con fecha posterior al corte
  y recepción anterior o igual al corte, no registrado al corte → pasivo omitido.

El modelo es el mismo en ambos marcos; solo cambian las etiquetas y las citas (se enruta con es_pymes).
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m,
    n2, norm, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)
from backend.app.aud.niif.procesadores.cxc_cartera import NOMBRE_TRAMO, TRAMOS, _rango, _tramo, _tramo_formula

VERSION = "proveedores_cxp 1.0"
RUBRO = "PROVEEDORES"

_PROVEEDORES = [
    campo("id", "Documento / N° de factura", alias=("factura", "documento", "comprobante", "numero de factura", "numfac"), ejemplo="001-002-000456"),
    campo("proveedor", "Proveedor", alias=("razon social", "nombre del proveedor", "acreedor", "nomprov"), ejemplo="Aceros del Pacífico S.A."),
    campo("emision", "Fecha de la factura (registro)", "date", alias=("fecha factura", "emision", "fecha emision", "fecha registro"), ejemplo="2025-12-05"),
    campo("vence", "Fecha de vencimiento", "date", alias=("vencimiento", "fecha vencimiento", "fecvto"), ejemplo="2026-01-04"),
    campo("saldo", "Saldo por pagar", "number", alias=("saldo pendiente", "por pagar", "pendiente", "saldo actual"), ejemplo="15000.00"),
    campo("recepcion", "Fecha de recepción del bien o servicio", "date", False, ("fecha recepcion", "recepcion", "fecha ingreso bodega", "fecha entrega")),
    campo("confirmado", "Saldo confirmado por el proveedor", "number", False, ("saldo confirmado", "confirmacion", "circularizacion")),
    campo("pago", "Pago posterior al cierre", "number", False, ("pago posterior", "pagado", "pago")),
    campo("fecha_pago", "Fecha del pago", "date", False, ("fecha pago", "fecha de pago")),
    campo("relacionado", "Parte relacionada (sí/no)", "text", False, ("relacionada", "parte relacionada", "vinculado")),
    campo("moneda", "Moneda", "text", False, ("divisa", "moneda original")),
    campo("ruc", "RUC / identificación", "text", False, ("cedula", "identificacion", "codigo proveedor")),
]
_PAGOS = [
    campo("id", "Documento del pago o factura posterior", alias=("documento", "comprobante", "egreso", "factura", "cheque"), ejemplo="CE-2026-0015"),
    campo("proveedor", "Proveedor", alias=("razon social", "beneficiario", "acreedor"), ejemplo="Aceros del Pacífico S.A."),
    campo("fecha", "Fecha del pago o factura (posterior al corte)", "date", alias=("fecha pago", "fecha factura", "fecha documento"), ejemplo="2026-01-10"),
    campo("recepcion", "Fecha de recepción del bien o servicio", "date", alias=("fecha recepcion", "recepcion", "fecha servicio"), ejemplo="2025-12-22"),
    campo("importe", "Importe", "number", alias=("valor", "monto", "importe pagado"), ejemplo="6200.00"),
    campo("registrado", "¿Registrado al corte? (sí/no)", "text", alias=("registrado", "registrado al corte", "provisionado"), ejemplo="No"),
    campo("concepto", "Concepto", "text", False, ("detalle", "descripcion")),
]
CAMPOS = {"proveedores": _PROVEEDORES, "pagos_posteriores": _PAGOS}
TIPOS = {"proveedores": "proveedores", "pagos_posteriores": "pagos_posteriores"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "proveedores"
CONTROL = "saldo"

PARAMETROS = {"tasaMercado": None, "plazoFinanciacion": 12, "cicloOperacion": 12, "descuentoRegistrado": None,
              "noCorrienteRegistrado": None, "saldoMayor": None}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "tasaMercado": "Tasa de mercado anual para el valor presente (%)",
    "plazoFinanciacion": "Plazo de pago que se considera financiación (meses)",
    "cicloOperacion": "Ciclo normal de operación (meses)",
    "descuentoRegistrado": "Intereses implícitos por devengar registrados (mayor)",
    "noCorrienteRegistrado": "Proveedores presentados como no corrientes (estado financiero)",
    "saldoMayor": "Saldo de proveedores según el mayor / balance de comprobación",
}
TOTAL_EJEMPLO = "ajusteNeto"

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Detalle", "Detalle por documento"),
    ("04_Aging", "Antigüedad de proveedores (aging)"), ("05_Pagos_posteriores", "Pagos posteriores al cierre"),
    ("06_Pasivos_no_registrados", "Búsqueda de pasivos no registrados"), ("07_Confirmaciones", "Confirmación de proveedores"),
    ("08_Corte_compras", "Corte de compras"), ("09_Costo_amortizado", "Costo amortizado e intereses implícitos"),
    ("10_Clasificacion", "Clasificación corriente / no corriente"), ("11_Ajuste", "Saldo auditado y ajustes"),
    ("12_Asientos", "Asientos propuestos"), ("13_Problemas", "Problemas encontrados"),
]

_SI = {"si", "s", "x", "yes", "y", "1", "true", "verdadero"}
_NO = {"no", "n", "0", "false", "falso", ""}


def _sino(v):
    k = norm(v)
    return "Sí" if k in _SI else ("No" if k in _NO else None)


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    r = validar_campos(CAMPOS[tipo], filas)
    k = "registrado" if tipo == "pagos_posteriores" else "relacionado"
    for f in filas:
        if str(f.get(k, "") or "").strip() and _sino(f.get(k)) is None:
            r["errors"].append({"row": f.get("_row"), "field": k, "message": "Responda «sí» o «no»."})
    r["ok"] = not r["errors"]
    return r


# --- cálculo -----------------------------------------------------------------

def _opc(f, k):
    v = str(f.get(k, "") or "").strip()
    return a_num(v) if v else None


def _pnum(p, k):
    v = p.get(k)
    return None if v is None or str(v).strip() == "" else float(a_num(v))


def _citas(pymes: bool) -> dict:
    if pymes:
        return {"fin": "PYMES 11.13", "ca": "PYMES 11.14–11.20", "clas": "PYMES 4.7–4.8", "baja": "PYMES 11.36",
                "rel": "PYMES Sección 33", "me": "PYMES 30.9"}
    return {"fin": "NIIF 9 5.1.1, B5.1.1", "ca": "NIIF 9 4.2.1, 5.4.1", "clas": "NIC 1 69–70 (NIIF 18 desde 2027)", "baja": "NIIF 9 3.3.1",
            "rel": "NIC 24", "me": "NIC 21 23 a)"}


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    pymes = es_pymes(p)
    cit = _citas(pymes)
    tm = _pnum(p, "tasaMercado")
    umbral = _pnum(p, "plazoFinanciacion")
    ciclo = _pnum(p, "cicloOperacion")
    if umbral is None or umbral < 0:
        raise ValueError("Indique el plazo de pago que se considera financiación (meses).")
    if ciclo is None or ciclo < 0:
        raise ValueError("Indique el ciclo normal de operación (meses).")
    if tm is not None and tm < 0:
        raise ValueError("La tasa de mercado no puede ser negativa.")
    desc_reg = _pnum(p, "descuentoRegistrado")
    nc_reg = _pnum(p, "noCorrienteRegistrado")
    mayor = _pnum(p, "saldoMayor")
    limite_nc = max(12, ciclo) * 365 / 12
    t = None if tm is None else tm / 100

    filas = []
    for f in datasets.get("proveedores") or []:
        saldo = a_num(f.get("saldo"))
        emision, vence = fecha(f.get("emision")), fecha(f.get("vence"))
        if saldo is None or saldo == 0:
            continue
        if emision is None or vence is None:
            raise ValueError(f"Documento {f.get('id')}: faltan las fechas de factura o vencimiento.")
        dv = (corte_a - vence).days
        plazo = (vence - emision).days
        financia = saldo > 0 and plazo > umbral * 365 / 12
        transcurridos = min(max((corte_a - emision).days, 0), plazo)
        por_vencer = max((vence - corte_a).days, 0)
        vp = saldo / (1 + t) ** (plazo / 365) if financia and t is not None else None
        interes_dev = vp * ((1 + t) ** (transcurridos / 365) - 1) if vp is not None else None
        ca = vp * (1 + t) ** (transcurridos / 365) if vp is not None else saldo
        interes = None if financia and t is None else saldo - ca
        no_corr = saldo > 0 and por_vencer > limite_nc
        pago, fpago = _opc(f, "pago"), fecha(f.get("fecha_pago"))
        posterior = pago is not None and fpago is not None and fpago > corte_a
        recep = fecha(f.get("recepcion"))
        filas.append({
            "doc": str(f.get("id", "")).strip(), "proveedor": str(f.get("proveedor", "")).strip() or "(sin nombre)",
            "emision": emision, "recepcion": recep, "vence": vence, "saldo": saldo,
            "relacionado": _sino(f.get("relacionado")) or "No", "moneda": str(f.get("moneda", "") or "").strip().upper() or "USD",
            "dv": dv, "tramo": _tramo(dv)["k"], "plazo": plazo, "financia": financia, "transcurridos": transcurridos,
            "porVencer": por_vencer, "vp": vp, "interesDev": interes_dev, "ca": ca, "interes": interes,
            "noCorr": no_corr, "importeNC": ca if no_corr else 0, "deudor": -saldo if saldo < 0 else 0,
            "pago": pago, "fechaPago": fpago, "aplicable": min(pago, saldo) if posterior else 0,
            "exceso": max(pago - saldo, 0) if posterior else 0,
            "pagoNoPosterior": pago is not None and not posterior,
            "confirmado": _opc(f, "confirmado"), "recibida": recep is not None and recep <= corte_a,
            "_row": f.get("_row"),
        })
    if not filas:
        raise ValueError("Cargue el auxiliar de proveedores por documento al corte del ejercicio.")
    for x in filas:
        x["sinPago"] = x["saldo"] - x["aplicable"]
        x["difConf"] = None if x["confirmado"] is None else x["confirmado"] - x["saldo"]
        x["anticipado"] = x["saldo"] if x["recepcion"] is not None and not x["recibida"] else 0

    busqueda = []
    for f in datasets.get("pagos_posteriores") or []:
        imp, fp, rc = a_num(f.get("importe")), fecha(f.get("fecha")), fecha(f.get("recepcion"))
        if imp is None or fp is None or rc is None:
            raise ValueError(f"Pago posterior {f.get('id')}: faltan importe, fecha o fecha de recepción.")
        reg = _sino(f.get("registrado"))
        if reg is None:
            raise ValueError(f"Pago posterior {f.get('id')}: indique «sí» o «no» en «¿Registrado al corte?».")
        post, causa = fp > corte_a, rc <= corte_a
        busqueda.append({"doc": str(f.get("id", "")).strip(), "proveedor": str(f.get("proveedor", "")).strip() or "(sin nombre)",
                         "fecha": fp, "recepcion": rc, "importe": imp, "registrado": reg, "posterior": post, "causa": causa,
                         "omitido": imp if post and causa and reg == "No" else 0})

    total = sum(x["saldo"] for x in filas)
    omitido = sum(b["omitido"] for b in busqueda)
    anticipado = sum(x["anticipado"] for x in filas)
    conf = [x for x in filas if x["confirmado"] is not None]
    dif_conf = sum(abs(x["difConf"]) for x in conf)
    exceso = sum(x["exceso"] for x in filas)
    interes_req = sum(x["interes"] or 0 for x in filas)
    ajuste_fin = interes_req - (desc_reg or 0)
    deudores = sum(x["deudor"] for x in filas)
    libros = total - (desc_reg or 0)
    auditado = libros + omitido - anticipado - ajuste_fin + deudores
    ajuste = auditado - libros
    no_corr = sum(x["importeNC"] for x in filas)
    reclas = no_corr - (nc_reg or 0)
    relacionadas = sum(x["saldo"] for x in filas if x["relacionado"] == "Sí")
    fin = [x for x in filas if x["financia"]]

    matriz = []
    for tr in TRAMOS:
        de = [x for x in filas if x["tramo"] == tr["k"]]
        matriz.append({"k": tr["k"], "tramo": tr["n"], "docs": len(de), "saldo": sum(x["saldo"] for x in de)})

    problemas = []
    if omitido > 0.005:
        n = sum(1 for b in busqueda if b["omitido"])
        problemas.append(problema("PASIVO_NO_REGISTRADO", f"{n} pago(s) o factura(s) posteriores al corte con recepción del bien o servicio hasta el corte "
                                  f"y sin registrar: {m(omitido)}. El pasivo existía al cierre ({cit['ca']}; NIA 500).", omitido))
    if not busqueda:
        problemas.append(problema("SIN_BUSQUEDA_PASIVOS", "No se cargó la búsqueda de pasivos no registrados (pagos y facturas posteriores al corte): "
                                  "documente el procedimiento (NIA 330, NIA 500)."))
    dif = [x for x in conf if abs(x["difConf"]) > 0.005]
    if dif:
        problemas.append(problema("DIF_CONFIRMACION", f"{len(dif)} confirmación(es) con diferencia contra libros: "
                                  + "; ".join(f"{x['doc']} {m(x['difConf'])}" for x in dif)
                                  + ". Un saldo confirmado mayor al registrado sugiere pasivo omitido; investigue y concilie (NIA 505).", dif_conf))
    if not conf:
        problemas.append(problema("SIN_CONFIRMACION", "No se informó ningún saldo confirmado: documente la confirmación de proveedores o los procedimientos alternativos (NIA 505)."))
    for x in filas:
        if x["anticipado"]:
            problemas.append(problema("ERROR_CORTE_COMPRAS", f"{x['doc']}: compra registrada al corte con recepción del bien o servicio el "
                                      f"{x['recepcion'].isoformat()} (posterior al corte): el pasivo aún no existía.", x["anticipado"]))
    for x in filas:
        if x["exceso"] > 0.005:
            problemas.append(problema("PAGO_MAYOR_SALDO", f"{x['doc']}: pago posterior {m(x['pago'])} mayor al saldo registrado {m(x['saldo'])}: "
                                      "posible pasivo subestimado; obtenga la factura que respalda la diferencia.", x["exceso"]))
        if x["pagoNoPosterior"]:
            problemas.append(problema("PAGO_NO_POSTERIOR", f"{x['doc']}: el pago informado no tiene fecha posterior al corte; si se pagó antes del cierre, "
                                      f"el saldo no debería seguir en el auxiliar ({cit['baja']}).", x["pago"]))
    if fin and t is None:
        problemas.append(problema("FINANCIACION_SIN_TASA", f"{len(fin)} documento(s) con plazo mayor a {m(umbral)} meses y sin tasa de mercado: "
                                  f"el costo amortizado no se pudo medir ({cit['fin']}).", sum(x["saldo"] for x in fin)))
    if interes_req > 0.005 and abs(ajuste_fin) > 0.005:
        problemas.append(problema("FINANCIACION_NO_RECONOCIDA", f"Intereses implícitos por devengar {m(interes_req)} frente a {m(desc_reg or 0)} registrados"
                                  + (" (dato del mayor no informado)" if desc_reg is None else "")
                                  + f": proveedores a plazo largo medidos por su nominal ({cit['fin']}; {cit['ca']}).", ajuste_fin))
    if reclas > 0.005:
        problemas.append(problema("NO_CORRIENTE_COMO_CORRIENTE", f"Porción que vence después de {m(max(12, ciclo))} meses {m(no_corr)} frente a {m(nc_reg or 0)} "
                                  f"presentado como no corriente" + (" (dato no informado)" if nc_reg is None else "") + f": reclasificar ({cit['clas']}).", reclas))
    elif reclas < -0.005:
        problemas.append(problema("CORRIENTE_COMO_NO_CORRIENTE", f"Se presenta como no corriente {m(nc_reg or 0)}, más que la porción que vence después de "
                                  f"{m(max(12, ciclo))} meses ({m(no_corr)}) ({cit['clas']}).", reclas))
    if deudores > 0.005:
        n = sum(1 for x in filas if x["deudor"])
        problemas.append(problema("SALDOS_DEUDORES", f"{n} saldo(s) deudor(es) dentro de proveedores (anticipos o notas de crédito) por {m(deudores)}: "
                                  "reclasificar al activo; no se compensan con el pasivo salvo derecho legal y intención de liquidar por el neto (NIC 32 42).", deudores))
    viejos = [x for x in filas if x["dv"] > 360 and x["saldo"] > 0]
    if viejos:
        problemas.append(problema("VENCIDO_MAS_360", f"{len(viejos)} saldo(s) vencido(s) hace más de 360 días por {m(sum(x['saldo'] for x in viejos))}: confirme que la obligación "
                                  f"sigue vigente o si se extinguió o prescribió ({cit['baja']}).", sum(x["saldo"] for x in viejos)))
    me = [x for x in filas if x["moneda"] != "USD"]
    if me:
        problemas.append(problema("MONEDA_EXTRANJERA", f"{len(me)} saldo(s) en moneda extranjera ({', '.join(sorted({x['moneda'] for x in me}))}): verifique la "
                                  f"conversión al tipo de cambio de cierre ({cit['me']}).", sum(x["saldo"] for x in me)))
    if mayor is None:
        problemas.append(problema("SIN_SALDO_MAYOR", "Ingrese el saldo de proveedores según el mayor para conciliar el auxiliar (NIA 500)."))
    elif abs(total - mayor) > 0.005:
        problemas.append(problema("DIF_MAYOR", f"El auxiliar ({m(total)}) no concilia con el mayor ({m(mayor)}): diferencia {m(total - mayor)}.", total - mayor))

    iso = lambda d: d.isoformat() if d else ""
    rows = [{"id": x["doc"], "proveedor": x["proveedor"], "emision": iso(x["emision"]), "recepcion": iso(x["recepcion"]), "vence": iso(x["vence"]),
             "dias": str(x["dv"]), "tramo": NOMBRE_TRAMO[x["tramo"]], "saldo": r2(x["saldo"]), "costoAmortizado": r2(x["ca"]),
             "clasificacion": "Activo (anticipo)" if x["saldo"] < 0 else ("No corriente" if x["noCorr"] else "Corriente"), "_row": x["_row"]}
            for x in filas]
    totales = {"saldo": total}
    etiquetas = {"saldo": "Proveedores según auxiliar (nominal)"}
    if mayor is not None:
        totales.update(saldoMayor=mayor, difMayor=total - mayor)
        etiquetas.update(saldoMayor="Saldo según el mayor", difMayor="Diferencia auxiliar − mayor")
    totales.update(pasivoNoRegistrado=omitido, corteAnticipado=anticipado, difConfirmacion=dif_conf, pagoMayorSaldo=exceso,
                   interesNoDevengado=interes_req, descuentoRegistrado=desc_reg or 0, ajusteFinanciacion=ajuste_fin,
                   saldosDeudores=deudores, saldoAuditado=auditado, ajusteNeto=ajuste, noCorriente=no_corr,
                   noCorrienteRegistrado=nc_reg or 0, reclasificacionNoCorriente=reclas, relacionadas=relacionadas)
    etiquetas.update(pasivoNoRegistrado="Pasivos no registrados", corteAnticipado="Compras registradas antes de la recepción",
                     difConfirmacion="Diferencias de confirmación (absolutas)", pagoMayorSaldo="Pagos posteriores mayores al saldo",
                     interesNoDevengado="Intereses implícitos por devengar", descuentoRegistrado="Intereses por devengar registrados",
                     ajusteFinanciacion="Ajuste por financiación implícita", saldosDeudores="Saldos deudores a reclasificar al activo",
                     saldoAuditado="Saldo de proveedores auditado", ajusteNeto="Ajuste neto propuesto a proveedores",
                     noCorriente="Porción no corriente requerida", noCorrienteRegistrado="Porción no corriente presentada",
                     reclasificacionNoCorriente="Reclasificación a no corriente", relacionadas="Saldos con partes relacionadas")
    ser = lambda x: {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in x.items()}
    detalle = {"cortes": {"actual": corte_a.isoformat()}, "parametros": p, "pymes": pymes, "edicion": edicion_pymes(p) if pymes else "",
               "citas": cit, "tasaMercado": tm, "umbral": umbral, "ciclo": ciclo, "descuentoRegistrado": desc_reg,
               "noCorrienteRegistrado": nc_reg, "saldoMayor": mayor, "matriz": matriz,
               "filas": [ser(x) for x in filas], "busqueda": [ser(b) for b in busqueda],
               "fin": {"vp": sum(x["vp"] or 0 for x in fin), "devengado": sum(x["interesDev"] or 0 for x in fin),
                       "componente": sum(x["saldo"] - x["vp"] for x in fin if x["vp"] is not None)}}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(v) for k, v in totales.items()}, "labels": etiquetas,
            "primary": "ajusteNeto", "exceptions": problemas, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

P = ref("02_Parametros")
DET, PAG, PNR, CNF, COR, CAM, AJ = (ref(n) for n in ("03_Detalle", "05_Pagos_posteriores", "06_Pasivos_no_registrados", "07_Confirmaciones",
                                                    "08_Corte_compras", "09_Costo_amortizado", "11_Ajuste"))
_PAR = ["corte", "marco", "tasaMercado", "plazoFinanciacion", "cicloOperacion", "descuentoRegistrado", "noCorrienteRegistrado", "saldoMayor"]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
_AJ = ["saldo", "descReg", "libros", "omitido", "anticipado", "interesReq", "ajusteFin", "deudores", "auditado", "ajusteNeto",
       "noCorr", "noCorrReg", "reclas", "mayor", "difMayor", "difConf", "pagoMayor", "relacionadas"]
AJF = {k: FILA0 + i for i, k in enumerate(_AJ)}


def _pb(k):
    return f"{P}$B${PAR[k]}"


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    fl, bq, cit = d["filas"], d["busqueda"], d["citas"]
    t = {k: float(v) for k, v in res["totals"].items()}
    nd = len(fl)
    fin_det = FILA0 + nd - 1
    tm, corte = _pb("tasaMercado"), _pb("corte")
    marco = (MARCO_PYMES + f" {d['edicion']}") if d["pymes"] else MARCO_COMPLETAS

    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Marco contable", marco, "Mismo modelo en ambos marcos; cambian las citas"],
        ["Tasa de mercado anual para el valor presente (%)", d["tasaMercado"], f"{cit['fin']} — tasa de un instrumento de deuda similar"],
        ["Plazo que se considera financiación (meses)", d["umbral"], f"{cit['fin']} — juicio: plazo mayor a las condiciones normales de crédito"],
        ["Ciclo normal de operación (meses)", d["ciclo"], f"{cit['clas']} — si no es identificable, 12 meses"],
        ["Intereses implícitos por devengar registrados (mayor)", d["descuentoRegistrado"], "Mayor contable"],
        ["Proveedores presentados como no corrientes", d["noCorrienteRegistrado"], "Estado de situación financiera"],
        ["Saldo de proveedores según el mayor", d["saldoMayor"], "Mayor / balance de comprobación"],
    ]

    # 03 · Detalle por documento.
    detalle = []
    for i, x in enumerate(fl):
        r = FILA0 + i
        detalle.append([
            x["doc"], x["proveedor"], x["emision"], x["recepcion"] or None, x["vence"], n2(x["saldo"]), x["relacionado"], x["moneda"],
            fx(f"{corte}-E{r}", x["dv"]), fx(_tramo_formula(f"I{r}"), NOMBRE_TRAMO[x["tramo"]]), fx(f"E{r}-C{r}", x["plazo"]),
            fx(f'IF(AND(F{r}>0,K{r}>{_pb("plazoFinanciacion")}*365/12),"Sí","No")', "Sí" if x["financia"] else "No"),
            fx(f'IF(AND(L{r}="Sí",{tm}<>""),F{r}/(1+{tm}/100)^(K{r}/365)*(1+{tm}/100)^(MIN(MAX({corte}-C{r},0),K{r})/365),F{r})', x["ca"]),
            fx(f'IF(AND(L{r}="Sí",{tm}=""),"",F{r}-M{r})', x["interes"]),
            fx(f"MAX(E{r}-{corte},0)", x["porVencer"]),
            fx(f'IF(AND(F{r}>0,O{r}>MAX(12,{_pb("cicloOperacion")})*365/12),"Sí","No")', "Sí" if x["noCorr"] else "No"),
            fx(f'IF(P{r}="Sí",M{r},0)', x["importeNC"]),
            fx(f"IF(F{r}<0,-F{r},0)", x["deudor"]),
        ])
    tot_det = ["TOTAL", "", "", "", "", suma("F", fin_det, t["saldo"]), "", "", None, "", None, "", suma("M", fin_det, sum(x["ca"] for x in fl)),
               suma("N", fin_det, t["interesNoDevengado"]), None, "", suma("Q", fin_det, t["noCorriente"]), suma("R", fin_det, t["saldosDeudores"])]

    # 04 · Aging (importe nominal).
    aging = []
    for i, mt in enumerate(d["matriz"]):
        r = FILA0 + i
        aging.append([mt["tramo"], fx(f"COUNTIF({_rango(DET, 'J', nd)},A{r})", mt["docs"]),
                      fx(f"SUMIF({_rango(DET, 'J', nd)},A{r},{_rango(DET, 'F', nd)})", n2(mt["saldo"])),
                      fx(f'IF(SUM({_rango(DET, "F", nd)})=0,"",C{r}/SUM({_rango(DET, "F", nd)}))', mt["saldo"] / t["saldo"] if t["saldo"] else None),
                      "No" if mt["k"] == "pv" else "Sí"])
    fin_ag = FILA0 + len(TRAMOS) - 1

    # 05 · Pagos posteriores (todos los documentos).
    pagos = []
    for i, x in enumerate(fl):
        r = FILA0 + i
        pagos.append([x["doc"], x["proveedor"], fx(f"{DET}I{r}", x["dv"]), fx(f"{DET}F{r}", n2(x["saldo"])), x["pago"], x["fechaPago"] or None,
                      fx(f'IF(OR(E{r}="",F{r}=""),0,IF(F{r}>{corte},MIN(E{r},D{r}),0))', x["aplicable"]),
                      fx(f"D{r}-G{r}", x["sinPago"]),
                      fx(f'IF(OR(E{r}="",F{r}=""),0,IF(F{r}>{corte},MAX(E{r}-D{r},0),0))', x["exceso"])])
    tot_pag = ["TOTAL", "", None, suma("D", fin_det, t["saldo"]), None, None, suma("G", fin_det, sum(x["aplicable"] for x in fl)),
               suma("H", fin_det, sum(x["sinPago"] for x in fl)), suma("I", fin_det, t["pagoMayorSaldo"])]

    # 06 · Búsqueda de pasivos no registrados.
    pnr = []
    for i, b in enumerate(bq):
        r = FILA0 + i
        pnr.append([b["doc"], b["proveedor"], b["fecha"], b["recepcion"], n2(b["importe"]), b["registrado"],
                    fx(f'IF(C{r}>{corte},"Sí","No")', "Sí" if b["posterior"] else "No"),
                    fx(f'IF(D{r}<={corte},"Sí","No")', "Sí" if b["causa"] else "No"),
                    fx(f'IF(AND(G{r}="Sí",H{r}="Sí",F{r}="No"),E{r},0)', b["omitido"])])
    fin_pnr = FILA0 + len(bq) - 1
    tot_pnr = ["TOTAL", "", "", "", suma("E", fin_pnr, sum(b["importe"] for b in bq)), "", "", "", suma("I", fin_pnr, t["pasivoNoRegistrado"])] if bq else None

    # 07 · Confirmaciones.
    cnf = []
    for i, x in enumerate(fl):
        if x["confirmado"] is None:
            continue
        r, rd = FILA0 + len(cnf), FILA0 + i
        cnf.append([x["doc"], x["proveedor"], fx(f"{DET}F{rd}", n2(x["saldo"])), x["confirmado"], fx(f"D{r}-C{r}", x["difConf"]),
                    fx(f"ABS(E{r})", abs(x["difConf"])),
                    fx(f'IF(ABS(E{r})<=0.005,"Conforme",IF(E{r}>0,"Proveedor reporta más","Proveedor reporta menos"))',
                       "Conforme" if abs(x["difConf"]) <= 0.005 else ("Proveedor reporta más" if x["difConf"] > 0 else "Proveedor reporta menos"))])
    fin_cnf = FILA0 + len(cnf) - 1
    conf = [x for x in fl if x["confirmado"] is not None]
    tot_cnf = (["TOTAL", "", suma("C", fin_cnf, sum(x["saldo"] for x in conf)), suma("D", fin_cnf, sum(x["confirmado"] for x in conf)),
                suma("E", fin_cnf, sum(x["difConf"] for x in conf)), suma("F", fin_cnf, t["difConfirmacion"]), ""] if cnf else None)

    # 08 · Corte de compras (documentos con fecha de recepción).
    cor = []
    for i, x in enumerate(fl):
        if not x["recepcion"]:
            continue
        r, rd = FILA0 + len(cor), FILA0 + i
        cor.append([x["doc"], x["proveedor"], x["emision"], x["recepcion"], fx(f"{DET}F{rd}", n2(x["saldo"])),
                    fx(f'IF(D{r}<={corte},"Sí","No")', "Sí" if x["recibida"] else "No"),
                    fx(f'IF(F{r}="No",E{r},0)', x["anticipado"])])
    fin_cor = FILA0 + len(cor) - 1
    tot_cor = (["TOTAL", "", "", "", suma("E", fin_cor, sum(x["saldo"] for x in fl if x["recepcion"])), "", suma("G", fin_cor, t["corteAnticipado"])]
               if cor else None)

    # 09 · Costo amortizado (documentos con financiación implícita).
    cam = []
    for i, x in enumerate(fl):
        if not x["financia"]:
            continue
        r, rd = FILA0 + len(cam), FILA0 + i
        vp = x["vp"]
        h = None if d["tasaMercado"] is None else d["tasaMercado"] / 100
        cam.append([x["doc"], x["proveedor"], x["emision"], x["vence"], fx(f"{DET}F{rd}", n2(x["saldo"])),
                    fx(f"D{r}-C{r}", x["plazo"]), fx(f"MIN(MAX({corte}-C{r},0),F{r})", x["transcurridos"]),
                    fx(f'IF({tm}="","",{tm}/100)', h),
                    fx(f'IF(H{r}="","",E{r}/(1+H{r})^(F{r}/365))', vp),
                    fx(f'IF(H{r}="","",E{r}-I{r})', None if vp is None else x["saldo"] - vp),
                    fx(f'IF(H{r}="","",(E{r}/I{r})^(365/F{r})-1)', h),
                    fx(f'IF(H{r}="","",I{r}*((1+H{r})^(G{r}/365)-1))', x["interesDev"]),
                    fx(f'IF(H{r}="","",I{r}+L{r})', None if vp is None else x["ca"]),
                    fx(f'IF(H{r}="","",E{r}-M{r})', x["interes"])])
    fin_cam = FILA0 + len(cam) - 1
    fi = d["fin"]
    tot_cam = (["TOTAL", "", "", "", suma("E", fin_cam, sum(x["saldo"] for x in fl if x["financia"])), None, None, None,
                suma("I", fin_cam, fi["vp"]), suma("J", fin_cam, fi["componente"]), None, suma("L", fin_cam, fi["devengado"]),
                suma("M", fin_cam, sum(x["ca"] for x in fl if x["financia"] and x["vp"] is not None)),
                suma("N", fin_cam, sum(x["interes"] or 0 for x in fl if x["financia"]))] if cam else None)

    # 10 · Clasificación (todos los documentos).
    cla = []
    for i, x in enumerate(fl):
        r = FILA0 + i
        txt = "Activo (anticipo)" if x["saldo"] < 0 else ("No corriente" if x["noCorr"] else "Corriente")
        cla.append([x["doc"], x["proveedor"], x["vence"], fx(f"{DET}O{r}", x["porVencer"]), fx(f"{DET}M{r}", x["ca"]),
                    fx(f'IF(E{r}<0,"Activo (anticipo)",IF({DET}P{r}="Sí","No corriente","Corriente"))', txt),
                    fx(f'IF(F{r}="Corriente",E{r},0)', x["ca"] if txt == "Corriente" else 0),
                    fx(f"{DET}Q{r}", x["importeNC"]), fx(f"{DET}R{r}", x["deudor"])])
    tot_cla = ["TOTAL", "", None, None, suma("E", fin_det, sum(x["ca"] for x in fl)), "",
               suma("G", fin_det, sum(x["ca"] for x in fl if x["saldo"] > 0 and not x["noCorr"])),
               suma("H", fin_det, t["noCorriente"]), suma("I", fin_det, t["saldosDeudores"])]

    # 11 · Saldo auditado y ajustes.
    tot_ref = lambda hoja_ref, col, fin, ok: f"{hoja_ref}{col}{fin + 1}" if ok else "0"
    b = lambda k: f"B{AJF[k]}"
    ajuste = [
        ["Proveedores según auxiliar (nominal)", fx(f"SUM({_rango(DET, 'F', nd)})", t["saldo"]), "03_Detalle"],
        ["(-) Intereses implícitos por devengar registrados", fx(_pb("descuentoRegistrado"), t["descuentoRegistrado"]), "Parámetros (mayor)"],
        ["Saldo en libros neto", fx(f"{b('saldo')}-{b('descReg')}", t["saldo"] - t["descuentoRegistrado"]), ""],
        ["(+) Pasivos no registrados", fx(tot_ref(PNR, "I", fin_pnr, bq), t["pasivoNoRegistrado"]), f"06_Pasivos_no_registrados · {cit['ca']}"],
        ["(-) Compras registradas antes de la recepción", fx(tot_ref(COR, "G", fin_cor, cor), t["corteAnticipado"]), "08_Corte_compras"],
        ["Intereses implícitos por devengar requeridos", fx(f"SUM({_rango(DET, 'N', nd)})", t["interesNoDevengado"]), f"{cit['fin']}"],
        ["(-) Ajuste por financiación implícita", fx(f"{b('interesReq')}-{b('descReg')}", t["ajusteFinanciacion"]), "Requerido − registrado"],
        ["(+) Saldos deudores reclasificados al activo", fx(f"SUM({_rango(DET, 'R', nd)})", t["saldosDeudores"]), "NIC 32 42 / anticipos"],
        ["Saldo de proveedores auditado", fx(f"{b('libros')}+{b('omitido')}-{b('anticipado')}-{b('ajusteFin')}+{b('deudores')}", t["saldoAuditado"]), ""],
        ["Ajuste neto propuesto a proveedores", fx(f"{b('auditado')}-{b('libros')}", t["ajusteNeto"]), "Positivo: aumenta el pasivo"],
        ["Porción no corriente requerida", fx(f"SUM({_rango(DET, 'Q', nd)})", t["noCorriente"]), cit["clas"]],
        ["Porción no corriente presentada", fx(_pb("noCorrienteRegistrado"), t["noCorrienteRegistrado"]), "Parámetros"],
        ["Reclasificación a no corriente", fx(f"{b('noCorr')}-{b('noCorrReg')}", t["reclasificacionNoCorriente"]), "Positivo: pasar de corriente a no corriente"],
        ["Saldo según el mayor", fx(f'IF({_pb("saldoMayor")}<>"",{_pb("saldoMayor")},"")', d["saldoMayor"]), "Parámetros"],
        ["Diferencia auxiliar − mayor", fx(f'IF({b("mayor")}="","",{b("saldo")}-{b("mayor")})', t.get("difMayor")), "NIA 500"],
        ["Diferencias de confirmación (absolutas)", fx(tot_ref(CNF, "F", fin_cnf, cnf), t["difConfirmacion"]), "NIA 505"],
        ["Pagos posteriores mayores al saldo", fx(f"{PAG}I{fin_det + 1}", t["pagoMayorSaldo"]), "05_Pagos_posteriores"],
        ["Saldos con partes relacionadas", fx(f'SUMIF({_rango(DET, "G", nd)},"Sí",{_rango(DET, "F", nd)})', t["relacionadas"]), cit["rel"]],
    ]

    # 12 · Asientos (importes remiten a 11_Ajuste y 09_Costo_amortizado).
    asientos = []

    def asiento(titulo, lineas):
        for i, (cta, formula, valor, debe) in enumerate(lineas):
            v = fx(formula, n2(valor))
            asientos.append([titulo if i == 0 else "", cta, v if debe else None, None if debe else v])

    ajb = lambda k: f"{AJ}B{AJF[k]}"
    if t["pasivoNoRegistrado"] > 0.005:
        asiento("1 · Pasivos no registrados", [("Inventarios / costos y gastos (bienes y servicios recibidos al corte)", ajb("omitido"), t["pasivoNoRegistrado"], True),
                                              ("Proveedores", ajb("omitido"), t["pasivoNoRegistrado"], False)])
    if t["corteAnticipado"] > 0.005:
        asiento("2 · Compras registradas antes de la recepción", [("Proveedores", ajb("anticipado"), t["corteAnticipado"], True),
                                                                  ("Inventarios / costos y gastos", ajb("anticipado"), t["corteAnticipado"], False)])
    if abs(t["ajusteFinanciacion"]) > 0.005 and cam and d["tasaMercado"] is not None:
        if not d["descuentoRegistrado"]:
            asiento("3 · Financiación implícita no reconocida", [
                ("(-) Intereses implícitos por devengar (proveedores)", f"{CAM}N{fin_cam + 1}", t["interesNoDevengado"], True),
                ("Gasto financiero por intereses devengados", f"{CAM}L{fin_cam + 1}", fi["devengado"], True),
                ("Activo o gasto de la compra (componente de financiación)", f"{CAM}J{fin_cam + 1}", fi["componente"], False)])
        else:
            asiento("3 · Ajuste de intereses implícitos por devengar", [
                ("(-) Intereses implícitos por devengar (proveedores)", f"ABS({ajb('ajusteFin')})", abs(t["ajusteFinanciacion"]), t["ajusteFinanciacion"] > 0),
                ("Gasto financiero / costo de la compra", f"ABS({ajb('ajusteFin')})", abs(t["ajusteFinanciacion"]), t["ajusteFinanciacion"] < 0)])
    if t["saldosDeudores"] > 0.005:
        asiento("4 · Saldos deudores a anticipos", [("Anticipos a proveedores (activo)", ajb("deudores"), t["saldosDeudores"], True),
                                                   ("Proveedores", ajb("deudores"), t["saldosDeudores"], False)])
    if abs(t["reclasificacionNoCorriente"]) > 0.005:
        pos = t["reclasificacionNoCorriente"] > 0
        asiento("5 · Reclasificación corriente / no corriente", [
            ("Proveedores corrientes" if pos else "Proveedores no corrientes", f"ABS({ajb('reclas')})", abs(t["reclasificacionNoCorriente"]), True),
            ("Proveedores no corrientes" if pos else "Proveedores corrientes", f"ABS({ajb('reclas')})", abs(t["reclasificacionNoCorriente"]), False)])

    ref_res = {"saldo": ajb("saldo"), "saldoMayor": ajb("mayor"), "difMayor": ajb("difMayor"), "pasivoNoRegistrado": ajb("omitido"),
               "corteAnticipado": ajb("anticipado"), "difConfirmacion": ajb("difConf"), "pagoMayorSaldo": ajb("pagoMayor"),
               "interesNoDevengado": ajb("interesReq"), "descuentoRegistrado": ajb("descReg"), "ajusteFinanciacion": ajb("ajusteFin"),
               "saldosDeudores": ajb("deudores"), "saldoAuditado": ajb("auditado"), "ajusteNeto": ajb("ajusteNeto"),
               "noCorriente": ajb("noCorr"), "noCorrienteRegistrado": ajb("noCorrReg"), "reclasificacionNoCorriente": ajb("reclas"),
               "relacionadas": ajb("relacionadas")}
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Detalle", "Detalle por documento",
             [["Documento", "t"], ["Proveedor", "t"], ["Fecha factura", "d"], ["Recepción", "d"], ["Vencimiento", "d"], ["Saldo", "n"],
              ["Relacionado", "t"], ["Moneda", "t"], ["Días desde vencimiento", "i"], ["Tramo", "t"], ["Plazo de pago (días)", "i"],
              ["Financiación implícita", "t"], ["Costo amortizado", "n"], ["Interés implícito por devengar", "n"], ["Días por vencer", "i"],
              ["No corriente", "t"], ["Importe no corriente", "n"], ["Saldo deudor", "n"]], detalle, tot_det),
        hoja("04_Aging", "Antigüedad de proveedores (aging)", [["Tramo", "t"], ["Documentos", "i"], ["Saldo", "n"], ["% del saldo", "p"], ["Vencido", "t"]],
             aging, ["TOTAL", suma("B", fin_ag, nd), suma("C", fin_ag, t["saldo"]), None, ""]),
        hoja("05_Pagos_posteriores", "Pagos posteriores al cierre",
             [["Documento", "t"], ["Proveedor", "t"], ["Días desde vencimiento", "i"], ["Saldo al corte", "n"], ["Pago informado", "n"], ["Fecha del pago", "d"],
              ["Pago posterior aplicable", "n"], ["Saldo sin pago posterior", "n"], ["Pago mayor al saldo", "n"]], pagos, tot_pag),
        hoja("06_Pasivos_no_registrados", "Búsqueda de pasivos no registrados",
             [["Documento", "t"], ["Proveedor", "t"], ["Fecha pago / factura", "d"], ["Recepción", "d"], ["Importe", "n"], ["¿Registrado al corte?", "t"],
              ["Posterior al corte", "t"], ["Causa hasta el corte", "t"], ["Pasivo no registrado", "n"]], pnr, tot_pnr),
        hoja("07_Confirmaciones", "Confirmación de proveedores",
             [["Documento", "t"], ["Proveedor", "t"], ["Saldo en libros", "n"], ["Saldo confirmado", "n"], ["Diferencia", "n"], ["Diferencia absoluta", "n"], ["Estado", "t"]],
             cnf, tot_cnf),
        hoja("08_Corte_compras", "Corte de compras",
             [["Documento", "t"], ["Proveedor", "t"], ["Fecha factura", "d"], ["Recepción", "d"], ["Saldo", "n"], ["Recibida en el ejercicio", "t"],
              ["Registrada antes de la recepción", "n"]], cor, tot_cor),
        hoja("09_Costo_amortizado", "Costo amortizado e intereses implícitos",
             [["Documento", "t"], ["Proveedor", "t"], ["Fecha factura", "d"], ["Vencimiento", "d"], ["Nominal", "n"], ["Plazo (días)", "i"],
              ["Días transcurridos", "i"], ["TIE = tasa de mercado", "p"], ["Pasivo inicial (valor presente)", "n"], ["Financiación implícita", "n"],
              ["TIE recalculada", "p"], ["Interés devengado al corte", "n"], ["Costo amortizado al corte", "n"], ["Interés por devengar", "n"]], cam, tot_cam),
        hoja("10_Clasificacion", "Clasificación corriente / no corriente",
             [["Documento", "t"], ["Proveedor", "t"], ["Vencimiento", "d"], ["Días por vencer", "i"], ["Costo amortizado", "n"], ["Clasificación requerida", "t"],
              ["Corriente", "n"], ["No corriente", "n"], ["Saldo deudor (activo)", "n"]], cla, tot_cla),
        hoja("11_Ajuste", "Saldo auditado y ajustes", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], ajuste),
        hoja("12_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos),
        hoja("13_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -----------------------------------------------------------------

def definicion() -> dict:
    prov = ("Una fila por documento pendiente al corte: documento, proveedor, fecha de factura, vencimiento y saldo (negativo si es deudor); "
            "y, cuando existan, fecha de recepción del bien o servicio, saldo confirmado por el proveedor, pago posterior y su fecha, "
            "parte relacionada (sí/no) y moneda. Sin filas de total.")
    pagos = ("Pagos y facturas registrados después del corte (hasta la fecha del informe): documento, proveedor, fecha, fecha de recepción "
             "del bien o servicio, importe y si el pasivo estaba registrado al corte (sí/no).")
    return {
        "name": "Proveedores y cuentas por pagar",
        "area": "Proveedores y cuentas por pagar",
        "processor": "proveedores_cxp",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Busca pasivos no registrados en los pagos y facturas posteriores al corte, contrasta pagos posteriores y confirmaciones "
                    "con el auxiliar, recalcula la antigüedad, prueba el corte de compras contra la fecha de recepción, mide al costo "
                    "amortizado los proveedores con financiación implícita (valor presente a la tasa de mercado, TIE, interés devengado) y "
                    "clasifica la porción no corriente y los saldos deudores. El modelo es el mismo en NIIF completas (NIIF 9, NIC 1) y en "
                    "PYMES (Secciones 11 y 4); cambian solo las citas."),
        "source": {"organization": "IFRS Foundation (texto en español: Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIIF 9 párr. 3.3.1 (baja: obligación satisfecha, cancelada o prescrita), 4.2.1 (pasivos financieros a costo "
                                "amortizado), 5.1.1 (medición inicial a valor razonable), B5.1.1 (financiación sin intereses: valor actual "
                                "descontado al tipo de mercado de un instrumento similar); NIC 1 párr. 69 (pasivo corriente) y 70 (partidas "
                                "del ciclo de explotación); NIIF 7 párr. 39 a) (análisis de vencimientos) — leídos en EUR-Lex. NIC 32 párr. 42 "
                                "(compensación) y NIIF 18 (aplicable desde 2027, reemplaza a la NIC 1): VERIFICAR numeración."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015 y 2025: Sección 11 párr. 11.13 (transacción de financiación: valor presente de "
                                      "los pagos futuros descontados a la tasa de mercado), 11.14–11.20 (costo amortizado y método del interés "
                                      "efectivo), 11.36 (baja de pasivos); Sección 4 párr. 4.7–4.8 (clasificación corriente/no corriente). "
                                      "VERIFICAR la redacción y numeración en el texto oficial de cada edición (no leídos en esta construcción)."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 505", "section": "VERIFICAR párrafos", "requirement": "Confirmaciones externas a proveedores; investigar las diferencias."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del auxiliar contra el mayor."},
            {"document": "NIA 330", "section": "párr. 18 y 20", "requirement": "Procedimientos sustantivos de corte y conciliación de registros con los estados (VERIFICAR párrafos)."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13", "requirement": "La tasa de mercado del valor presente es un supuesto de una estimación."},
            {"document": "NIA 550", "section": "párr. 11", "requirement": "Identificar y revelar saldos con partes relacionadas (VERIFICAR párrafo)."},
        ],
        "calculo": [
            "Aging: días desde el vencimiento = corte − vencimiento; tramos corriente, 1–30, 31–60, 61–90, 91–180, 181–360 y más de 360 días.",
            "Pagos posteriores: pago aplicable = pago con fecha posterior al corte, hasta el saldo; pago mayor al saldo = exceso (posible pasivo subestimado).",
            "Pasivos no registrados: pago o factura posterior al corte con recepción del bien o servicio hasta el corte y no registrado al corte.",
            "Confirmación: diferencia = saldo confirmado por el proveedor − saldo en libros.",
            "Corte de compras: documento del auxiliar con recepción posterior al corte = compra registrada antes de la recepción.",
            "Financiación implícita: plazo de pago (vencimiento − fecha de factura) mayor al umbral (12 meses por defecto).",
            "Pasivo inicial = nominal ÷ (1 + tasa de mercado)^(plazo ÷ 365); TIE = tasa de mercado (un solo pago al vencimiento); financiación implícita = nominal − valor presente.",
            "Interés devengado = pasivo inicial × ((1 + TIE)^(días transcurridos ÷ 365) − 1); costo amortizado al corte = inicial + interés − pagos (el saldo ya es el pendiente); interés por devengar = nominal − costo amortizado.",
            "No corriente: saldo que vence después de max(12 meses, ciclo normal de operación), a costo amortizado (NIC 1 69–70; PYMES 4.7). Saldos deudores: se reclasifican al activo.",
            "Saldo auditado = libros neto + pasivos no registrados − compras antes de la recepción − ajuste por financiación + saldos deudores; ajuste neto = auditado − libros neto.",
        ],
        "fields": _PROVEEDORES, "rules": [], "control": CONTROL, "primary": "ajusteNeto",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "CXP-01", "objective": "Integridad y antigüedad del auxiliar", "risk": "Auxiliar incompleto o no conciliado", "assertion": "Integridad",
             "procedure": "Conciliar el auxiliar por documento con el mayor y recalcular la antigüedad", "evidence": "Auxiliar y mayor",
             "criterion": "Diferencia cero o explicada", "source": "NIA 500 párr. 9"},
            {"code": "CXP-02", "objective": "Búsqueda de pasivos no registrados", "risk": "Pasivos omitidos al cierre", "assertion": "Integridad",
             "procedure": "Revisar pagos y facturas posteriores al corte y comparar la fecha de recepción con el corte", "evidence": "Egresos y facturas posteriores, actas de recepción",
             "criterion": "Pasivos con causa hasta el corte registrados", "source": "NIA 330 · NIIF 9 4.2.1 · PYMES 11"},
            {"code": "CXP-03", "objective": "Pagos posteriores", "risk": "Saldos inexistentes o subestimados", "assertion": "Existencia / Exactitud",
             "procedure": "Cotejar los pagos posteriores con el saldo de cada documento", "evidence": "Estados de cuenta bancarios y comprobantes de egreso",
             "criterion": "Pago igual al saldo o diferencia explicada", "source": "NIA 500"},
            {"code": "CXP-04", "objective": "Confirmación de proveedores", "risk": "Saldos mal medidos u omitidos", "assertion": "Existencia / Integridad",
             "procedure": "Enviar confirmaciones y conciliar las diferencias", "evidence": "Respuestas de proveedores",
             "criterion": "Diferencias conciliadas o ajustadas", "source": "NIA 505"},
            {"code": "CXP-05", "objective": "Corte de compras", "risk": "Compras registradas en un período distinto a la recepción", "assertion": "Corte",
             "procedure": "Comparar la fecha de recepción del bien o servicio con el corte", "evidence": "Ingresos a bodega, actas de servicio",
             "criterion": "Pasivo reconocido desde la recepción", "source": "NIA 330"},
            {"code": "CXP-06", "objective": "Costo amortizado e intereses implícitos", "risk": "Proveedores a plazo largo medidos por su nominal", "assertion": "Valoración",
             "procedure": "Identificar documentos con plazo mayor al umbral y medir su valor presente, TIE e interés devengado", "evidence": "Contratos, términos de pago, tasa de mercado",
             "criterion": "Financiación implícita reconocida", "source": "NIIF 9 5.1.1, B5.1.1, 4.2.1 · PYMES 11.13"},
            {"code": "CXP-07", "objective": "Clasificación y presentación", "risk": "Porción de largo plazo presentada como corriente; anticipos compensados", "assertion": "Presentación",
             "procedure": "Clasificar por vencimiento frente al ciclo de operación y reclasificar saldos deudores", "evidence": "Auxiliar, estado de situación financiera",
             "criterion": "Presentación conforme", "source": "NIC 1 69–70 · PYMES 4.7 · NIIF 7 39"},
        ],
        "requests": [
            req("RQ-001", "Auxiliar de proveedores por documento al corte con recepciones, confirmaciones y pagos posteriores", "proveedores", "CXP-01",
                "Población a medir y conciliar con el mayor", content=prov),
            req("RQ-002", "Pagos y facturas posteriores al corte con fecha de recepción del bien o servicio", "pagos_posteriores", "CXP-02",
                "Búsqueda de pasivos no registrados", content=pagos),
            req("RQ-003", "Mayor / balance de comprobación de proveedores e intereses por devengar", None, "CXP-01", "Conciliación y datos registrados",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-004", "Respuestas de confirmación de proveedores", None, "CXP-04", "Sustento del saldo confirmado", formats=("pdf",), use="soporte"),
            req("RQ-005", "Comprobantes de egreso y estados de cuenta posteriores al cierre", None, "CXP-03", "Sustento de los pagos posteriores",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-006", "Ingresos a bodega o actas de recepción alrededor del cierre", None, "CXP-05", "Sustento de la fecha de recepción",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-007", "Contratos, términos de pago y sustento de la tasa de mercado", None, "CXP-06", "Financiación implícita",
                formats=("pdf", "docx"), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) -------------------------------------------------------

def _ej(id, prov, emision, vence, saldo, **extra):
    return {"id": id, "proveedor": prov, "emision": emision, "vence": vence, "saldo": saldo, "_row": 2, **extra}


def _pp(id, prov, fecha_, recepcion, importe, registrado):
    return {"id": id, "proveedor": prov, "fecha": fecha_, "recepcion": recepcion, "importe": importe, "registrado": registrado, "_row": 2}


# Corte 2025-12-31, tasa de mercado 10 %, umbral 12 meses, ciclo 12 meses.
# P-005: 24.200 a 730 días → pasivo inicial 24.200 ÷ 1,21 = 20.000; financiación implícita 4.200;
# 183 días transcurridos → interés 20.000 × (1,1^(183/365) − 1) = 978,92; costo amortizado 20.978,92;
# por devengar 3.221,08; vence en 547 días (> 365) → no corriente 20.978,92.
# Pasivos no registrados: 6.200 + 1.850 + 950 = 9.000. Compra antes de la recepción: P-002 7.000.
# Ajuste neto = 9.000 − 7.000 − 3.221,08 + 1.800 (saldo deudor P-007) = 578,92.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tasaMercado": 10, "plazoFinanciacion": 12, "cicloOperacion": 12,
                   "noCorrienteRegistrado": 0, "saldoMayor": 80000},
    "datasets": {
        "proveedores": [
            _ej("P-001", "Aceros del Pacífico S.A.", "2025-12-05", "2026-01-04", "15000", recepcion="2025-12-05", confirmado="15000", pago="15000", fecha_pago="2026-01-04"),
            _ej("P-002", "Plásticos Andinos Cía. Ltda.", "2025-12-29", "2026-01-28", "7000", recepcion="2026-01-06"),
            _ej("P-003", "Servicios Logísticos del Sur", "2025-11-10", "2025-12-10", "4000", recepcion="2025-11-10", confirmado="5200"),
            _ej("P-004", "Químicos Unidos S.A.", "2025-09-15", "2025-10-15", "3000", pago="3500", fecha_pago="2026-01-20"),
            _ej("P-005", "Maquinarias Industriales S.A.", "2025-07-01", "2027-07-01", "24200", recepcion="2025-07-01", confirmado="24200"),
            _ej("P-006", "Holding Andes S.A.", "2025-06-30", "2026-06-30", "10000", relacionado="Sí"),
            _ej("P-007", "Transportes Rápidos", "2025-12-20", "2026-01-19", "-1800"),
            _ej("P-008", "Empaques Sierra", "2025-05-02", "2025-06-01", "2500"),
            _ej("P-009", "Importadora Global GmbH", "2025-12-01", "2026-01-30", "9000", moneda="EUR", pago="9000", fecha_pago="2025-12-28"),
            _ej("P-010", "Empresa Eléctrica", "2025-12-15", "2026-01-14", "1300", recepcion="2025-11-30", pago="1300", fecha_pago="2026-01-14"),
            _ej("P-011", "Asesores Legales Asociados", "2024-10-01", "2024-10-31", "600"),
            _ej("P-012", "Mantenimiento Técnico", "2025-12-31", "2026-02-14", "5500", recepcion="2025-12-31", pago="5500", fecha_pago="2026-02-14"),
        ],
        "pagos_posteriores": [
            _pp("CE-001", "Aceros del Pacífico S.A.", "2026-01-10", "2025-12-22", "6200", "No"),
            _pp("CE-002", "Servicios Contables", "2026-01-15", "2025-12-31", "1850", "No"),
            _pp("CE-003", "Plásticos Andinos Cía. Ltda.", "2026-01-20", "2026-01-12", "3100", "No"),
            _pp("CE-004", "Empresa Eléctrica", "2026-01-14", "2025-11-30", "1300", "Sí"),
            _pp("CE-005", "Químicos Unidos S.A.", "2026-02-05", "2025-12-18", "2750", "Sí"),
            _pp("CE-006", "Seguridad Privada", "2026-01-31", "2025-12-31", "950", "No"),
            _pp("CE-007", "Papelería Central", "2025-12-20", "2025-12-15", "300", "No"),
            _pp("CE-008", "Consultora Beta", "2026-02-20", "2026-02-01", "4000", "No"),
        ],
    },
}

_DS_SIN_BUSQUEDA = {"proveedores": EJEMPLO["datasets"]["proveedores"]}
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025_sin_tasa", _DS_SIN_BUSQUEDA, {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025", "tasaMercado": None,
                                              "saldoMayor": None, "noCorrienteRegistrado": None}, EJEMPLO["corte"]),
    ("completas_descuento_registrado", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "descuentoRegistrado": 4000, "noCorrienteRegistrado": 30000,
                                                             "saldoMayor": 80300}, EJEMPLO["corte"]),
]
