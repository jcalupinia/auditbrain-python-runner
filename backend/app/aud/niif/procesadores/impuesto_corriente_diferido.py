"""Impuesto corriente y diferido: conciliación tributaria (formulario 101), impuesto corriente, bases fiscales,
diferencias temporarias, activo y pasivo por impuesto diferido, pérdidas fiscales, recuperabilidad, tasa de
reversión, resultados frente a ORI, compensación y tasa efectiva (NIC 12.81 c).

Tres anexos:

- ``conciliacion`` (principal): renglones de la conciliación tributaria del cliente con el signo con que suman a
  la base imponible (+ suma, − resta). La suma de la columna «importe» es la base imponible según el cliente: ese
  es el total de control (se compara con el casillero de base imponible del F-101). El tipo de cada renglón
  (utilidad, participación, exentos, no deducibles, gastos atribuibles a exentos, participación atribuible a
  exentos, deducciones, pérdidas, otros) decide cómo lo recalcula el auditor; «importe según auditor» (opcional)
  reemplaza al del cliente (así se agregan gastos no deducibles omitidos).
  1. Participación trabajadores recalculada = 15 % × utilidad contable («utilidades líquidas», Código del Trabajo art. 97).
  2. Participación atribuible a exentos = 15 % del ingreso exento BRUTO informado por el cliente (Reglamento LRTI
     art. 46 num. 5, texto vigente al 15-jul-2025: «Se sumará también el porcentaje de participación laboral en las
     utilidades de las empresas atribuibles a los ingresos exentos; esto es, el 15% de tales ingresos»). Si el cliente
     solo entrega el importe neto, la herramienta **no reconstruye** la base bruta: el importe recalculado queda vacío,
     el renglón conserva el del cliente, ese tramo del cálculo normativo queda bloqueado y se emite un problema que
     pide el ingreso exento bruto y la participación atribuible (cédula 13_Partic_exentos).
  3. Amortización de pérdidas permitida = mín(la solicitada, 25 % de la utilidad gravable, saldo no vencido).
  4. Base imponible × tarifa = tarifa general + puntos de recargo × proporción sujeta (Reglamento LRTI art. 51: la
     proporción es la composición societaria en paraísos fiscales o no informada; si llega o supera el 50 %, el recargo
     grava el 100 % de la base).
  5. Impuesto a pagar = causado − retenciones − anticipos − crédito de años anteriores (negativo: saldo a favor).
- ``partidas``: diferencias temporarias por partida. Activo: libros − base; pasivo: base − libros
  (positivo imponible → pasivo diferido, NIC 12.15; negativo deducible → activo diferido si es probable la
  ganancia fiscal, NIC 12.24, y si la ley admite la deducción futura, Reglamento LRTI, art. innumerado a continuación del art. 28 (num. 5: provisiones distintas de cuentas incobrables y desmantelamiento, utilizables cuando se paguen —jubilación y desahucio solo por la parte no deducible, interpretación: LRTI art. 10 num. 13—; num. 8: pérdidas tributarias)). Tasa de reversión
  = tasa que se espera aplicar en el año de reversión (NIC 12.47, 49) = tarifa aprobada al cierre para ese año
  (general o futura) + el recargo del art. 37 que corresponda a la entidad; sin descuento (NIC 12.53). Movimiento: a
  resultados salvo las partidas de ORI (NIC 12.58, 61A).
- ``perdidas`` (opcional): pérdidas tributarias por año de origen; se amortizan de la más antigua a la más
  reciente; el remanente no vencido genera activo diferido si es probable (NIC 12.34–36).

El cálculo es el mismo en NIIF completas y en PYMES (Sección 29, alineada con la NIC 12 en lo que aquí se
mide); se enruta con es_pymes/edicion_pymes para las citas.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m,
    n2, norm, problema, r2, ref, req, validar_campos, validar_definicion_generica,
)

VERSION = "impuesto_corriente_diferido 1.0"
RUBRO = "IMPUESTOS"

_CONCILIACION = [
    campo("id", "Renglón / casillero", alias=("renglon", "casillero", "linea", "codigo", "numero"), ejemplo="801"),
    campo("concepto", "Concepto", alias=("descripcion", "detalle", "nombre"), ejemplo="Utilidad del ejercicio"),
    campo("tipo", "Tipo (utilidad, participación, exentos, no deducibles, gastos exentos, participación exentos, deducciones, pérdidas, otros)",
          alias=("tipo", "clase", "naturaleza", "categoria"), ejemplo="utilidad"),
    campo("importe", "Importe según cliente (con signo: + suma, − resta)", "number",
          alias=("importe", "valor", "monto", "segun cliente", "importe cliente"), ejemplo="1000000.00"),
    campo("importe_auditor", "Importe según auditor (opcional, con signo)", "number", False,
          ("segun auditor", "importe auditor", "auditado", "recalculado")),
    campo("referencia", "Referencia (casillero F-101 / soporte)", "text", False, ("soporte", "casillero f101", "nota")),
]
_PARTIDAS = [
    campo("id", "Partida", alias=("partida", "concepto", "cuenta", "descripcion"), ejemplo="Provisión jubilación patronal"),
    campo("naturaleza", "Activo o pasivo", alias=("tipo", "naturaleza", "activo pasivo", "clase"), ejemplo="Pasivo"),
    campo("libros", "Importe en libros NIIF", "number", alias=("libros", "importe en libros", "valor en libros", "niif"), ejemplo="120000.00"),
    campo("base_fiscal", "Base fiscal", "number", alias=("base fiscal", "base tributaria", "valor fiscal", "tributario"), ejemplo="0.00"),
    campo("permitido", "Permitido tributariamente (sí/no)", alias=("permitido", "admitido", "art 28", "reconocido sri"), ejemplo="Sí"),
    campo("probable", "Probable ganancia fiscal futura (sí/no)", alias=("probable", "probabilidad", "recuperable"), ejemplo="Sí"),
    campo("anio_reversion", "Año esperado de reversión", "number", False, ("ano reversion", "anio reversion", "reversion", "año")),
    campo("tasa", "Tasa de reversión usada por el cliente (%)", "number", False, ("tasa", "tarifa", "tasa reversion")),
    campo("inicial", "Impuesto diferido registrado al inicio (+ activo / − pasivo)", "number", False, ("saldo inicial", "inicio", "diferido inicial")),
    campo("cierre", "Impuesto diferido registrado al cierre (+ activo / − pasivo)", "number", False, ("saldo final", "cierre", "diferido cierre", "registrado")),
    campo("ori", "Reconocido en ORI (sí/no)", "text", False, ("ori", "otro resultado integral", "patrimonio")),
]
_PERDIDAS = [
    campo("id", "Año de origen de la pérdida", alias=("ano", "anio", "año origen", "ejercicio"), ejemplo="2023"),
    campo("importe", "Pérdida tributaria declarada", "number", alias=("perdida", "importe", "valor"), ejemplo="120000.00"),
    campo("amortizado", "Amortizado acumulado en años anteriores", "number", False, ("amortizado", "amortizacion acumulada", "utilizado")),
    campo("vence", "Último año para amortizar (vacío: origen + plazo)", "number", False, ("vence", "vencimiento", "ano vence")),
]
CAMPOS = {"conciliacion": _CONCILIACION, "partidas": _PARTIDAS, "perdidas": _PERDIDAS}
TIPOS = {"conciliacion": "conciliacion", "partidas": "partidas", "perdidas": "perdidas"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "conciliacion"
CONTROL = "importe"

PARAMETROS = {
    "tasaIR": 25, "puntosRecargo": 3, "proporcionRecargo": 0, "participacion": 15, "limitePerdidas": 25, "plazoPerdidas": 5,
    "ingresoExentoBruto": None, "participacionExentosInformada": None,
    "tasaFutura": None, "anioTasaFutura": None, "perdidasPermitidas": "Sí", "probabilidadPerdidas": "Sí",
    "retenciones": None, "anticipos": None, "creditoAnterior": None, "impuestoCorrienteRegistrado": None,
    "saldoCorrienteRegistrado": None, "gastoDiferidoRegistrado": None, "dtaPerdidasInicial": None, "dtaPerdidasRegistrado": None,
    "derechoCompensar": "Sí", "dtaPresentado": None, "dtlPresentado": None, "umbralTasaEfectiva": 1,
}
PARAM_NEGATIVOS = ("saldoCorrienteRegistrado", "gastoDiferidoRegistrado")
ETIQUETAS_PARAM = {
    "tasaIR": "Tarifa general del impuesto a la renta (%) — LRTI art. 37; vigente al corte",
    "puntosRecargo": "Puntos adicionales por paraísos fiscales / composición societaria — LRTI art. 37; Reglamento art. 51; vigente al corte",
    "proporcionRecargo": "Composición societaria en paraísos fiscales o no informada (%) (la no informada más la ubicada en paraísos fiscales con beneficiario efectivo residente en Ecuador): el recargo se aplica sobre esa misma proporción de la base imponible y, solo cuando en conjunto llega o supera el 50 %, sobre el 100 % (LRTI art. 37; Reglamento art. 51; vigente al corte)",
    "participacion": "Participación de trabajadores (%) sobre las utilidades líquidas — Código del Trabajo art. 97; vigente al corte",
    "ingresoExentoBruto": "Ingreso exento BRUTO del ejercicio, antes de restar los gastos atribuibles (opcional): base del «15% de tales "
                          "ingresos» del Reglamento LRTI art. 46 num. 5. Si no se informa, la participación atribuible no se recalcula",
    "participacionExentosInformada": "Participación atribuible a ingresos exentos informada por el cliente en su papel de trabajo (opcional; "
                                     "se contrasta con el renglón de la conciliación)",
    "limitePerdidas": "Límite anual de amortización de pérdidas (% de la utilidad gravable) — LRTI art. 11; vigente al corte",
    "plazoPerdidas": "Plazo para amortizar pérdidas (años) — LRTI art. 11; vigente al corte",
    "tasaFutura": "Tasa aprobada para años futuros (%) (vacío: no hay cambio aprobado)",
    "anioTasaFutura": "Año desde el que rige la tasa futura",
    "perdidasPermitidas": "¿La ley admite diferido por pérdidas tributarias? (Reglamento LRTI, art. innumerado a continuación del art. 28 (num. 5: provisiones distintas de cuentas incobrables y desmantelamiento, utilizables cuando se paguen —jubilación y desahucio solo por la parte no deducible, interpretación: LRTI art. 10 num. 13—; num. 8: pérdidas tributarias))",
    "probabilidadPerdidas": "¿Es probable la ganancia fiscal para compensar las pérdidas? (NIC 12.35–36)",
    "retenciones": "Retenciones en la fuente del ejercicio",
    "anticipos": "Anticipos de impuesto a la renta pagados",
    "creditoAnterior": "Crédito tributario de años anteriores",
    "impuestoCorrienteRegistrado": "Gasto por impuesto corriente registrado",
    "saldoCorrienteRegistrado": "Impuesto a la renta por pagar registrado (+) / saldo a favor (−)",
    "gastoDiferidoRegistrado": "Gasto (ingreso −) por impuesto diferido registrado en resultados",
    "dtaPerdidasInicial": "Activo diferido por pérdidas registrado al inicio",
    "dtaPerdidasRegistrado": "Activo diferido por pérdidas registrado al cierre",
    "derechoCompensar": "¿Derecho legal de compensar y misma autoridad fiscal? (NIC 12.74)",
    "dtaPresentado": "Activo por impuesto diferido presentado en el estado de situación",
    "dtlPresentado": "Pasivo por impuesto diferido presentado en el estado de situación",
    "umbralTasaEfectiva": "Diferencia tolerable en la tasa efectiva (puntos porcentuales)",
}
TOTAL_EJEMPLO = "ajusteResultados"

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Conciliacion", "Conciliación tributaria"),
    ("04_Impuesto_corriente", "Impuesto corriente"), ("05_Perdidas", "Pérdidas tributarias"),
    ("06_Diferencias_temp", "Diferencias temporarias y diferido"), ("07_Tasa_reversion", "Tasa de reversión"),
    ("08_Recuperabilidad", "Recuperabilidad del activo diferido"), ("09_Movimiento", "Movimiento: resultados y ORI"),
    ("10_Compensacion", "Compensación y presentación"), ("11_Tasa_efectiva", "Tasa efectiva (NIC 12.81 c)"),
    ("12_Ajustes", "Ajustes propuestos"), ("13_Partic_exentos", "Participación atribuible a exentos"),
    ("14_Asientos", "Asientos propuestos"), ("15_Problemas", "Problemas encontrados"),
]

# Tipo → (signo exigido: 1 suma, -1 resta, 0 cualquiera; etiqueta).
_TIPOS_CONC = {
    "utilidad": (0, "Utilidad (pérdida) contable"), "participacion": (-1, "Participación trabajadores"),
    "exentos": (-1, "Ingresos exentos"), "no_deducibles": (1, "Gastos no deducibles"),
    "gastos_exentos": (1, "Gastos atribuibles a ingresos exentos"), "participacion_exentos": (1, "Participación atribuible a exentos"),
    "deducciones": (-1, "Deducciones adicionales"), "perdidas": (-1, "Amortización de pérdidas"), "otros": (0, "Otras partidas"),
}
_ALIAS_TIPO = {
    "utilidad": "utilidad", "utilidadcontable": "utilidad", "resultado": "utilidad", "perdidacontable": "utilidad",
    "participacion": "participacion", "participaciontrabajadores": "participacion", "15participacion": "participacion",
    "exentos": "exentos", "ingresosexentos": "exentos", "exento": "exentos",
    "nodeducibles": "no_deducibles", "gastosnodeducibles": "no_deducibles", "nodeducible": "no_deducibles",
    "gastosexentos": "gastos_exentos", "gastosatribuibles": "gastos_exentos", "gastosatribuiblesaexentos": "gastos_exentos",
    "gastosatribuiblesaingresosexentos": "gastos_exentos",
    "participacionexentos": "participacion_exentos", "participacionatribuible": "participacion_exentos",
    "participacionatribuibleaexentos": "participacion_exentos", "participacionatribuibleaingresosexentos": "participacion_exentos",
    "deducciones": "deducciones", "deduccionesadicionales": "deducciones", "deduccion": "deducciones",
    "perdidas": "perdidas", "amortizaciondeperdidas": "perdidas", "amortizacionperdidas": "perdidas", "perdidastributarias": "perdidas",
    "otros": "otros", "otras": "otros", "otraspartidas": "otros", "diferenciastemporarias": "otros",
}
_SIGNO_TXT = {1: "+ suma", -1: "− resta", 0: "± según signo"}
_SI = {"si", "s", "x", "yes", "y", "1", "true", "verdadero"}
_NO = {"no", "n", "0", "false", "falso"}


def _sino(v, defecto=None):
    k = norm(v)
    if not k:
        return defecto
    return "Sí" if k in _SI else ("No" if k in _NO else None)


def _tipo(v):
    return _ALIAS_TIPO.get(norm(v))


def _nat(v):
    k = norm(v)
    return "Activo" if k.startswith("activo") or k == "a" else ("Pasivo" if k.startswith("pasivo") or k == "p" else None)


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    r = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        fila = f.get("_row")
        if tipo == "conciliacion":
            t = _tipo(f.get("tipo"))
            if str(f.get("tipo", "") or "").strip() and t is None:
                r["errors"].append({"row": fila, "field": "tipo", "message": "Tipo no reconocido: use utilidad, participación, exentos, "
                                    "no deducibles, gastos exentos, participación exentos, deducciones, pérdidas u otros."})
            elif t:
                for k in ("importe", "importe_auditor"):
                    x = a_num(f.get(k))
                    s = _TIPOS_CONC[t][0]
                    if x is not None and s and x * s < 0:
                        r["errors"].append({"row": fila, "field": k, "message": f"{_TIPOS_CONC[t][1]} debe cargarse con signo "
                                            f"{'positivo (suma)' if s > 0 else 'negativo (resta)'} a la base imponible."})
        elif tipo == "partidas":
            if str(f.get("naturaleza", "") or "").strip() and _nat(f.get("naturaleza")) is None:
                r["errors"].append({"row": fila, "field": "naturaleza", "message": "Indique «Activo» o «Pasivo»."})
            for k in ("permitido", "probable", "ori"):
                if str(f.get(k, "") or "").strip() and _sino(f.get(k)) is None:
                    r["errors"].append({"row": fila, "field": k, "message": "Responda «sí» o «no»."})
        elif tipo == "perdidas":
            y = a_num(f.get("id"))
            if str(f.get("id", "") or "").strip() and (y is None or not 1900 < y < 2200):
                r["errors"].append({"row": fila, "field": "id", "message": "Año de origen inválido (AAAA)."})
    r["ok"] = not r["errors"]
    return r


# --- cálculo -----------------------------------------------------------------

def _pnum(p, k):
    v = p.get(k)
    return None if v is None or str(v).strip() == "" else float(a_num(v))


def _opc(f, k):
    v = str(f.get(k, "") or "").strip()
    return a_num(v) if v else None


def _citas(pymes: bool, edicion: str) -> dict:
    if pymes:
        v = "PYMES 2025 Secc. 29" if edicion == "2025" else "PYMES 2015 Secc. 29"
        comp = "29.37A" if edicion == "2025" else "29.37"
        return {"marco": v, "corr": f"{v} 29.4–29.6, 29.32", "dt": f"{v} 29.9–29.13 (bases fiscales), 29.14–29.20 (diferencias temporarias)",
                "dta": f"{v} 29.16, 29.21–29.22 y 29.31", "tasa": f"{v} 29.27–29.28 y 29.32", "ori": f"{v} 29.35",
                "comp": f"{v} {comp}", "etr": f"{v} 29.40 c)"}
    return {"marco": "NIC 12", "corr": "NIC 12.12–14, 46", "dt": "NIC 12.5, 15, 24", "dta": "NIC 12.24, 34–36, 56",
            "tasa": "NIC 12.47, 53", "ori": "NIC 12.58, 61A", "comp": "NIC 12.71, 74", "etr": "NIC 12.81 c)"}


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    anio = corte_a.year
    pymes = es_pymes(p)
    ed = edicion_pymes(p) if pymes else ""
    cit = _citas(pymes, ed)
    num = {k: _pnum(p, k) for k in ("tasaIR", "puntosRecargo", "proporcionRecargo", "participacion", "limitePerdidas", "plazoPerdidas",
                                    "ingresoExentoBruto", "participacionExentosInformada",
                                    "tasaFutura", "anioTasaFutura", "retenciones", "anticipos", "creditoAnterior",
                                    "impuestoCorrienteRegistrado", "saldoCorrienteRegistrado", "gastoDiferidoRegistrado",
                                    "dtaPerdidasInicial", "dtaPerdidasRegistrado", "dtaPresentado", "dtlPresentado", "umbralTasaEfectiva")}
    for k in ("tasaIR", "puntosRecargo", "proporcionRecargo", "participacion", "limitePerdidas", "plazoPerdidas", "umbralTasaEfectiva"):
        if num[k] is None:
            raise ValueError(f"Indique el parámetro «{ETIQUETAS_PARAM[k]}».")
    for k, v in num.items():
        if v is not None and v < 0 and k not in PARAM_NEGATIVOS:
            raise ValueError(f"El parámetro «{ETIQUETAS_PARAM[k]}» no puede ser negativo.")
    if num["tasaIR"] > 100 or num["participacion"] > 100 or num["limitePerdidas"] > 100 or num["proporcionRecargo"] > 100:
        raise ValueError("Las tasas y porcentajes deben estar entre 0 y 100.")
    if (num["tasaFutura"] is None) != (num["anioTasaFutura"] is None):
        raise ValueError("Indique juntos la tasa futura aprobada y el año desde el que rige.")
    sn = {}
    for k in ("perdidasPermitidas", "probabilidadPerdidas", "derechoCompensar"):
        sn[k] = _sino(p.get(k))
        if sn[k] is None:
            raise ValueError(f"Responda «sí» o «no» en «{ETIQUETAS_PARAM[k]}».")
    ti, part, lim, plazo = num["tasaIR"], num["participacion"], num["limitePerdidas"], num["plazoPerdidas"]
    tf, af = num["tasaFutura"], num["anioTasaFutura"]
    # Reglamento LRTI art. 51: el recargo grava la base en la misma proporción de la composición societaria en
    # paraísos fiscales o no informada; solo cuando esa proporción llega o supera el 50 % grava toda la base imponible.
    prop_rec = 100.0 if num["proporcionRecargo"] >= 50 else num["proporcionRecargo"]
    recargo = num["puntosRecargo"] * prop_rec / 100
    tarifa = ti + recargo
    # NIC 12.47 y 12.49: el diferido se mide a la tasa que se espera aplicar al revertir la diferencia; si la entidad
    # está sujeta al recargo, la tasa esperada lo incluye (tarifa general o futura + recargo).
    tf_ef = None if tf is None else tf + recargo
    ret, ant, cred = num["retenciones"] or 0, num["anticipos"] or 0, num["creditoAnterior"] or 0
    ir_reg, saldo_reg = num["impuestoCorrienteRegistrado"], num["saldoCorrienteRegistrado"]
    gdr = num["gastoDiferidoRegistrado"]
    dtal_ini, dtal_reg = num["dtaPerdidasInicial"] or 0, num["dtaPerdidasRegistrado"] or 0

    # 1 · Conciliación tributaria.
    conc = []
    for f in datasets.get("conciliacion") or []:
        t = _tipo(f.get("tipo"))
        imp = a_num(f.get("importe"))
        if t is None:
            raise ValueError(f"Renglón {f.get('id')}: tipo no reconocido «{f.get('tipo')}».")
        if imp is None:
            raise ValueError(f"Renglón {f.get('id')}: falta el importe según cliente.")
        aud = _opc(f, "importe_auditor")
        s = _TIPOS_CONC[t][0]
        for x in (imp, aud):
            if x is not None and s and x * s < 0:
                raise ValueError(f"Renglón {f.get('id')}: {_TIPOS_CONC[t][1]} con signo contrario al de la conciliación.")
        conc.append({"id": str(f.get("id", "")).strip(), "concepto": str(f.get("concepto", "")).strip(), "tipo": t,
                     "signo": _SIGNO_TXT[s], "cliente": imp, "auditor": aud, "usado": aud if aud is not None else imp,
                     "_row": f.get("_row")})
    if not conc:
        raise ValueError("Cargue la conciliación tributaria del cliente (renglones del formulario 101).")
    for c in conc:
        c["dif"] = c["usado"] - c["cliente"]
    if not any(c["tipo"] == "utilidad" for c in conc):
        raise ValueError("La conciliación necesita el renglón de utilidad (pérdida) contable.")
    sc = lambda t, k: sum(c[k] for c in conc if c["tipo"] == t)

    # 2 · Pérdidas tributarias (de la más antigua a la más reciente).
    perd = []
    for f in datasets.get("perdidas") or []:
        y, imp = a_num(f.get("id")), a_num(f.get("importe"))
        if y is None or imp is None:
            raise ValueError(f"Pérdida {f.get('id')}: faltan el año de origen o el importe.")
        if imp < 0:
            raise ValueError(f"Pérdida {f.get('id')}: cargue la pérdida como importe positivo.")
        am = _opc(f, "amortizado") or 0
        v = _opc(f, "vence")
        perd.append({"origen": int(y), "importe": imp, "amortizado": am, "venceDato": v is not None,
                     "vence": int(v) if v is not None else int(y + plazo), "_row": f.get("_row")})
    perd.sort(key=lambda x: x["origen"])
    for x in perd:
        x["disponible"] = x["importe"] - x["amortizado"]
        x["vencida"] = x["vence"] < anio
        x["noVencido"] = 0 if x["vencida"] else x["disponible"]
        x["saldoVencido"] = x["disponible"] if x["vencida"] else 0

    # 3 · Impuesto corriente: según cliente (B) y auditado (C).
    cl = {k: sc(t, "cliente") for k, t in (("u", "utilidad"), ("part", "participacion"), ("ex", "exentos"), ("nd", "no_deducibles"),
                                           ("ge", "gastos_exentos"), ("pe", "participacion_exentos"), ("ded", "deducciones"),
                                           ("otros", "otros"), ("perd", "perdidas"))}
    au = {k: sc(t, "usado") for k, t in (("u", "utilidad"), ("ex", "exentos"), ("nd", "no_deducibles"), ("ge", "gastos_exentos"),
                                         ("ded", "deducciones"), ("otros", "otros"))}
    au["part"] = -max(au["u"], 0) * part / 100
    # Reglamento LRTI art. 46 num. 5 (texto vigente al 15-jul-2025, leído en la biblioteca oficial): «Se sumará también el
    # porcentaje de participación laboral en las utilidades de las empresas atribuibles a los ingresos exentos; esto es, el
    # 15% de tales ingresos» → base BRUTA. Los gastos atribuibles se suman aparte por el num. 4, no minoran esta base.
    # Decisión del socio: sin el ingreso exento bruto informado no se reconstruye la base; el importe queda vacío (M22) y el
    # renglón conserva el del cliente, sin asumir cero.
    ex_bruto, pe_inf = num["ingresoExentoBruto"], num["participacionExentosInformada"]
    ex_neto = -au["ex"]
    if ex_neto <= 0.005:
        pe_calc, pe_estado = 0.0, "Sin ingresos exentos"
    elif au["u"] <= 0:
        pe_calc, pe_estado = 0.0, "Calculado"          # sin utilidad contable no hay participación que atribuir
    elif ex_bruto is None:
        pe_calc, pe_estado = None, "Bloqueado por falta de soporte"
    else:
        pe_calc, pe_estado = ex_bruto * part / 100, "Calculado"
    au["pe"] = cl["pe"] if pe_calc is None else pe_calc
    pex = {"bruto": ex_bruto, "neto": ex_neto, "gastos": au["ge"], "calc": pe_calc, "registrado": cl["pe"], "informado": pe_inf,
           "dif": None if pe_calc is None else pe_calc - cl["pe"], "estado": pe_estado}
    orden = ("u", "part", "ex", "nd", "ge", "pe", "ded", "otros")
    for d in (cl, au):
        d["b0"] = sum(d[k] for k in orden)
        d["lim"] = max(d["b0"], 0) * lim / 100
        d["disp"] = sum(x["noVencido"] for x in perd) if perd else None
    reclamo_aud = -sc("perdidas", "usado")
    au["perd"] = -min(reclamo_aud, au["lim"], au["disp"]) if perd else -min(reclamo_aud, au["lim"])
    for d in (cl, au):
        d["base"] = d["b0"] + d["perd"]
        d["tarifa"] = tarifa
        d["ir"] = max(d["base"], 0) * tarifa / 100
        d["ret"], d["ant"], d["cred"] = ret, ant, cred
        d["pagar"] = d["ir"] - ret - ant - cred
    ir_ef = cl["ir"] if ir_reg is None else ir_reg            # vacío: el impuesto de la conciliación del cliente
    saldo_ef = cl["pagar"] if saldo_reg is None else saldo_reg
    exceso_perd = au["perd"] - sc("perdidas", "usado")
    amort = -au["perd"]
    acum = 0
    for x in perd:
        x["amortAnio"] = max(0, min(x["noVencido"], amort - acum))
        acum += x["amortAnio"]
        x["remanente"] = x["noVencido"] - x["amortAnio"]
        x["arrastrable"] = x["remanente"] if x["vence"] > anio else 0
        x["dtaReq"] = x["arrastrable"] * tarifa / 100 if sn["perdidasPermitidas"] == "Sí" and sn["probabilidadPerdidas"] == "Sí" else 0
        x["dtaNoRec"] = x["arrastrable"] * tarifa / 100 - x["dtaReq"]

    # 4 · Diferencias temporarias por partida.
    part_rows = []
    for f in datasets.get("partidas") or []:
        nat, lb, bf = _nat(f.get("naturaleza")), a_num(f.get("libros")), a_num(f.get("base_fiscal"))
        perm, prob, ori = _sino(f.get("permitido")), _sino(f.get("probable")), _sino(f.get("ori"), "No")
        if nat is None or lb is None or bf is None:
            raise ValueError(f"Partida {f.get('id')}: faltan naturaleza (activo/pasivo), importe en libros o base fiscal.")
        if perm is None or prob is None or ori is None:
            raise ValueError(f"Partida {f.get('id')}: responda «sí» o «no» en permitido, probable y ORI.")
        y = _opc(f, "anio_reversion")
        tc = _opc(f, "tasa")
        dt = lb - bf if nat == "Activo" else bf - lb
        te = tf_ef if (tf is not None and af is not None and y is not None and y >= af) else tarifa
        tcli = tc if tc is not None else te
        dtl = dt * te / 100 if dt > 0 else 0
        dtab = -dt * te / 100 if dt < 0 else 0
        rec = dtab if perm == "Sí" and prob == "Sí" else 0
        ini, cie = _opc(f, "inicial") or 0, _opc(f, "cierre") or 0
        rq = rec - dtl
        mov = rq - ini
        part_rows.append({"partida": str(f.get("id", "")).strip(), "nat": nat, "libros": lb, "base": bf, "dt": dt,
                          "clase": "Imponible" if dt > 0 else ("Deducible" if dt < 0 else "Sin diferencia"),
                          "anio": int(y) if y is not None else None, "tasaDato": tc, "tasaCli": tcli, "tasa": te,
                          "difTasa": tcli - te, "efectoTasa": abs(dt) * (tcli - te) / 100,
                          "dtl": dtl, "dtaBruto": dtab, "perm": perm, "prob": prob, "dtaRec": rec, "dtaNoRec": dtab - rec,
                          "req": rq, "ini": ini, "cie": cie, "aj": rq - cie, "ori": ori, "mov": mov,
                          "res": -mov if ori == "No" else 0, "movOri": -mov if ori == "Sí" else 0, "_row": f.get("_row")})

    # 5 · Movimiento, compensación, ajustes y tasa efectiva.
    sp = lambda k, cond=lambda x: True: sum(x[k] for x in part_rows if cond(x))
    no_ori, si_ori = (lambda x: x["ori"] == "No"), (lambda x: x["ori"] == "Sí")
    dtal_req = sum(x["dtaReq"] for x in perd)
    mv = [
        {"k": "res", "concepto": "Diferencias temporarias con efecto en resultados", "ini": sp("ini", no_ori), "req": sp("req", no_ori),
         "cie": sp("cie", no_ori), "ori": False},
        {"k": "ori", "concepto": "Diferencias temporarias de partidas de ORI / patrimonio", "ini": sp("ini", si_ori), "req": sp("req", si_ori),
         "cie": sp("cie", si_ori), "ori": True},
        {"k": "perd", "concepto": "Pérdidas tributarias no utilizadas", "ini": dtal_ini, "req": dtal_req, "cie": dtal_reg, "ori": False},
    ]
    for x in mv:
        x["mov"] = x["req"] - x["ini"]
        x["aRes"] = 0 if x["ori"] else -x["mov"]
        x["aOri"] = -x["mov"] if x["ori"] else 0
        x["aj"] = x["req"] - x["cie"]
    gasto_dif_req = sum(x["aRes"] for x in mv)
    gasto_dif_saldos = -(mv[0]["cie"] - mv[0]["ini"]) - (mv[2]["cie"] - mv[2]["ini"])
    reclas = 0 if gdr is None else gdr - gasto_dif_saldos

    dta_rec = sp("dtaRec") + dtal_req
    dtl_req = sp("dtl")
    dta_norec = sp("dtaNoRec") + sum(x["dtaNoRec"] for x in perd)
    dif_req = sp("req") + dtal_req
    dif_reg = sp("cie") + dtal_reg
    aj_dif = dif_req - dif_reg
    aj_dif_res = mv[0]["aj"] + mv[2]["aj"]
    aj_dif_ori = mv[1]["aj"]
    aj_corr = au["ir"] - ir_ef
    aj_saldo = au["pagar"] - saldo_ef
    aj_res = aj_corr - aj_dif_res - reclas

    der = sn["derechoCompensar"] == "Sí"
    dta_rg = sum(x["cie"] for x in part_rows if x["cie"] > 0) + max(dtal_reg, 0)
    dtl_rg = -sum(x["cie"] for x in part_rows if x["cie"] < 0)
    comp = {"dtaReg": dta_rg, "dtlReg": dtl_rg,
            "dtaEsp": max(dta_rg - dtl_rg, 0) if der else dta_rg, "dtlEsp": max(dtl_rg - dta_rg, 0) if der else dtl_rg,
            "dtaAud": dta_rec, "dtlAud": dtl_req,
            "dtaPresAud": max(dta_rec - dtl_req, 0) if der else dta_rec, "dtlPresAud": max(dtl_req - dta_rec, 0) if der else dtl_req}
    comp["difDta"] = None if num["dtaPresentado"] is None else num["dtaPresentado"] - comp["dtaEsp"]
    comp["difDtl"] = None if num["dtlPresentado"] is None else num["dtlPresentado"] - comp["dtlEsp"]

    rai = au["u"] + au["part"]
    t100 = tarifa / 100
    etr = {"rai": rai, "teo": rai * t100, "nd": (au["nd"] + au["ge"] + au["pe"]) * t100, "ex": au["ex"] * t100,
           "ded": au["ded"] * t100, "perd": au["perd"] * t100, "otros": au["otros"] * t100}
    etr["neg"] = au["ir"] - (etr["teo"] + etr["nd"] + etr["ex"] + etr["ded"] + etr["perd"] + etr["otros"])
    etr["corr"] = au["ir"]
    etr["dif"] = gasto_dif_req
    etr["req"] = au["ir"] + gasto_dif_req
    etr["reg"] = ir_ef + (gasto_dif_saldos if gdr is None else gdr)
    etr["noexp"] = etr["reg"] - etr["req"]
    etr["tReq"] = None if rai == 0 else etr["req"] / rai
    etr["tReg"] = None if rai == 0 else etr["reg"] / rai
    etr["tApl"] = t100

    # 6 · Problemas.
    pr = []
    if abs(aj_corr) > 0.005:
        pr.append(problema("IR_CORRIENTE_MAL_CALCULADO", f"Impuesto corriente recalculado {m(au['ir'])} frente a {m(ir_ef)} registrado: diferencia "
                           f"{m(aj_corr)}. Se mide con la tarifa vigente al cierre sobre la base imponible auditada ({cit['corr']}; LRTI).", aj_corr))
    if ir_reg is not None and abs(cl["ir"] - ir_reg) > 0.005:
        pr.append(problema("IR_REGISTRADO_NO_CUADRA", f"El impuesto registrado ({m(ir_reg)}) no es la base imponible del propio cliente × tarifa "
                           f"({m(cl['base'])} × {m(tarifa)} % = {m(cl['ir'])}).", ir_reg - cl["ir"]))
    if abs(au["part"] - cl["part"]) > 0.005:
        pr.append(problema("PARTICIPACION_MAL_CALCULADA", f"Participación trabajadores {m(-cl['part'])} en la conciliación frente a {m(-au['part'])} "
                           f"recalculada ({m(part)} % de la utilidad contable; «utilidades líquidas», Código del Trabajo art. 97).", au["part"] - cl["part"]))
    if pex["calc"] is None:
        pr.append(problema("PARTICIPACION_EXENTOS_SIN_BASE_BRUTA",
                           "No se recalculó la participación de trabajadores atribuible a ingresos exentos: el cálculo normativo de ese renglón "
                           f"queda bloqueado. El Reglamento LRTI art. 46 num. 5 la fija en «el 15% de tales ingresos», esto es sobre el ingreso "
                           f"exento BRUTO, y del cliente solo consta el importe restado en la conciliación ({m(ex_neto)}), que puede venir neto de "
                           f"los gastos atribuibles ({m(au['ge'])}, que el num. 4 suma por separado). La herramienta no reconstruye la base bruta sin "
                           "soporte: el importe recalculado queda vacío y el renglón conserva el declarado por el cliente "
                           f"({m(cl['pe'])}). Solicite al cliente: (1) el ingreso exento bruto del ejercicio, antes de restar los gastos "
                           "atribuibles, y (2) el cálculo de la participación atribuible a esos ingresos, con el papel de trabajo que lo sustente. "
                           "Confirmar además que el art. 46 num. 5 sigue vigente al corte."))
    elif abs(au["pe"] - cl["pe"]) > 0.005:
        pr.append(problema("PARTICIPACION_EXENTOS", f"Participación atribuible a ingresos exentos {m(cl['pe'])} en la conciliación frente a "
                           f"{m(au['pe'])} recalculada: {m(part)} % del ingreso exento bruto informado ({m(ex_bruto)}). Reglamento LRTI art. 46 "
                           "num. 5: «el 15% de tales ingresos» (base bruta; los gastos atribuibles se suman aparte por el num. 4, no la minoran). "
                           "Confirmar que el art. 46 num. 5 sigue vigente al corte.", au["pe"] - cl["pe"]))
    if pe_inf is not None and abs(pe_inf - cl["pe"]) > 0.005:
        pr.append(problema("PARTICIPACION_EXENTOS_NO_CUADRA", f"La participación atribuible a exentos informada por el cliente ({m(pe_inf)}) no "
                           f"coincide con el renglón de la conciliación ({m(cl['pe'])}): diferencia {m(pe_inf - cl['pe'])}. Revise el papel de "
                           "trabajo del cliente y el casillero del formulario 101.", pe_inf - cl["pe"]))
    omit = sum(c["dif"] for c in conc if c["tipo"] == "no_deducibles")
    if omit > 0.005:
        pr.append(problema("NO_DEDUCIBLES_OMITIDOS", f"Gastos no deducibles omitidos en la conciliación por {m(omit)}: "
                           + "; ".join(f"{c['id']} {c['concepto']} {m(c['dif'])}" for c in conc if c["tipo"] == "no_deducibles" and c["dif"] > 0.005)
                           + " (LRTI art. 10 y Reglamento art. 35).", omit))
    otras = [c for c in conc if c["tipo"] != "no_deducibles" and abs(c["dif"]) > 0.005]
    if otras:
        pr.append(problema("OTRAS_DIFERENCIAS_CONCILIACION", f"{len(otras)} renglón(es) con importe según auditor distinto al del cliente: "
                           + "; ".join(f"{c['id']} {m(c['dif'])}" for c in otras) + ".", sum(c["dif"] for c in otras)))
    if exceso_perd > 0.005:
        causa = []
        if reclamo_aud - au["lim"] > 0.005:
            causa.append(f"supera el {m(lim)} % de la utilidad gravable ({m(au['lim'])})")
        if perd and reclamo_aud - au["disp"] > 0.005:
            causa.append(f"supera el saldo no vencido ({m(au['disp'])})")
        pr.append(problema("PERDIDAS_SOBRE_LIMITE", f"Amortización de pérdidas solicitada {m(reclamo_aud)}: " + " y ".join(causa)
                           + f". Permitida {m(amort)} (LRTI art. 11: {m(lim)} % anual, {int(plazo) if float(plazo).is_integer() else m(plazo)} años).", exceso_perd))
    if not perd and reclamo_aud > 0.005:
        pr.append(problema("PERDIDAS_SIN_ANEXO", f"Se amortizan pérdidas por {m(reclamo_aud)} sin anexo de pérdidas por año de origen: no se pudo "
                           "verificar el saldo ni el vencimiento."))
    venc = sum(x["saldoVencido"] for x in perd)
    if venc > 0.005:
        pr.append(problema("PERDIDAS_VENCIDAS", f"Pérdidas con plazo vencido y saldo sin amortizar {m(venc)} (años "
                           + ", ".join(str(x["origen"]) for x in perd if x["saldoVencido"] > 0.005)
                           + "): ya no se amortizan y no sustentan activo diferido.", venc))
    for x in part_rows:
        if x["cie"] > 0.005 and x["dtaBruto"] > 0 and x["perm"] == "No":
            pr.append(problema("DTA_NO_PERMITIDO", f"{x['partida']}: activo diferido registrado {m(x['cie'])} por una diferencia marcada como no "
                               "admitida para deducción futura («permitido» = No): revertirlo o corregir la marca. Recuerde que el art. innumerado a "
                               "continuación del art. 28 del Reglamento LRTI sí admite diferido en los casos de su num. 5 (provisiones distintas de "
                               "cuentas incobrables y desmantelamiento y, en su 2.º inciso, el deterioro de cartera que excede el límite en entidades "
                               "no financieras) y num. 8 (pérdidas tributarias).", x["cie"]))
        elif x["cie"] > 0.005 and x["dtaBruto"] > 0 and x["prob"] == "No":
            pr.append(problema("DTA_SIN_PROBABILIDAD", f"{x['partida']}: activo diferido registrado {m(x['cie'])} sin probabilidad de ganancia "
                               f"fiscal futura ({cit['dta']}).", x["cie"]))
    mal_tasa = [x for x in part_rows if abs(x["difTasa"]) > 1e-9 and x["dt"] != 0]
    if mal_tasa:
        pr.append(problema("TASA_REVERSION_INCORRECTA", f"{len(mal_tasa)} partida(s) medida(s) a una tasa distinta de la aprobada para el año de "
                           "reversión: " + "; ".join(f"{x['partida']} {m(x['tasaCli'])} % frente a {m(x['tasa'])} %" for x in mal_tasa)
                           + f" ({cit['tasa']}).", sum(x["efectoTasa"] for x in mal_tasa)))
    if dtal_reg > 0.005 and sn["perdidasPermitidas"] == "No":
        pr.append(problema("DTA_NO_PERMITIDO", f"Activo diferido por pérdidas {m(dtal_reg)} registrado sin que la ley lo admita (revisar el sustento).", dtal_reg))
    elif dtal_reg > 0.005 and sn["probabilidadPerdidas"] == "No":
        pr.append(problema("DTA_SIN_PROBABILIDAD", f"Activo diferido por pérdidas {m(dtal_reg)} sin evidencia convincente de ganancias fiscales "
                           f"({cit['dta']}; NIC 12.35: las pérdidas recientes son indicio de que no las habrá).", dtal_reg))
    elif dtal_reg - dtal_req > 0.005:
        pr.append(problema("DTA_PERDIDAS_EXCESO", f"Activo diferido por pérdidas registrado {m(dtal_reg)} frente a {m(dtal_req)} sustentado por el "
                           "remanente no vencido tras la amortización del año.", dtal_reg - dtal_req))
    if abs(aj_dif) > 0.005:
        n = sum(1 for x in part_rows if abs(x["aj"]) > 0.005) + (1 if abs(mv[2]["aj"]) > 0.005 else 0)
        pr.append(problema("DIFERIDO_MAL_MEDIDO", f"Impuesto diferido neto requerido {m(dif_req)} frente a {m(dif_reg)} registrado ({n} partida(s) con "
                           f"diferencia): ajuste {m(aj_dif)} ({cit['dt']}).", aj_dif))
    ori_mov = mv[1]["mov"]
    if gdr is not None and abs(reclas) > 0.005:
        if abs(ori_mov) > 0.005 and abs(reclas + ori_mov) <= 0.005:
            pr.append(problema("ORI_EN_RESULTADOS", f"El gasto diferido registrado en resultados ({m(gdr)}) incluye {m(reclas)} del diferido de partidas "
                               f"reconocidas en ORI: debe ir a ORI ({cit['ori']}).", reclas))
        else:
            pr.append(problema("GASTO_DIFERIDO_NO_CONCILIA", f"El gasto diferido registrado en resultados ({m(gdr)}) no concilia con la variación de los "
                               f"saldos registrados sin ORI ({m(gasto_dif_saldos)}): diferencia {m(reclas)}"
                               + (f"; el diferido de partidas de ORI movió {m(-ori_mov)}" if abs(ori_mov) > 0.005 else "") + ".", reclas))
    if (comp["difDta"] is not None and abs(comp["difDta"]) > 0.005) or (comp["difDtl"] is not None and abs(comp["difDtl"]) > 0.005):
        if der:
            pr.append(problema("FALTA_COMPENSAR", f"Activo diferido {m(num['dtaPresentado'] or 0)} y pasivo diferido {m(num['dtlPresentado'] or 0)} presentados "
                               f"sin compensar pese al derecho legal y la misma autoridad fiscal: presentar el neto ({cit['comp']}).",
                               abs(comp["difDta"] or 0)))
        else:
            pr.append(problema("COMPENSACION_INDEBIDA", "Activo y pasivo diferidos presentados por el neto sin derecho legal de compensar o con "
                               f"distinta autoridad fiscal ({cit['comp']}).", abs(comp["difDta"] or 0)))
    if rai != 0 and abs(etr["noexp"] / rai) * 100 > num["umbralTasaEfectiva"]:
        pr.append(problema("TASA_EFECTIVA_INEXPLICADA", f"Tasa efectiva registrada {m(etr['tReg'] * 100)} % frente a {m(etr['tReq'] * 100)} % explicada "
                           f"por la conciliación (tasa aplicable {m(tarifa)} %): gasto sin explicar {m(etr['noexp'])} ({cit['etr']}).", etr["noexp"]))
    if abs(aj_saldo - aj_corr) > 0.005:
        pr.append(problema("SALDO_CORRIENTE_NO_CONCILIA", f"El saldo registrado de impuesto por pagar ({m(saldo_ef)}) difiere del recalculado "
                           f"({m(au['pagar'])}) en {m(aj_saldo)}, más que el ajuste al gasto: revise retenciones, anticipos y crédito tributario.",
                           aj_saldo - aj_corr))
    if au["pagar"] < -0.005:
        pr.append(problema("SALDO_A_FAVOR", f"Saldo a favor de impuesto a la renta {m(-au['pagar'])}: se presenta como activo por impuesto corriente "
                           f"({cit['corr']}); evalúe su recuperación (devolución o compensación)."))
    if not part_rows:
        pr.append(problema("SIN_PARTIDAS", "No se cargó el anexo de diferencias temporarias: el impuesto diferido no se pudo medir (NIC 12.15, 24)."))
    falt = [ETIQUETAS_PARAM[k] for k in ("impuestoCorrienteRegistrado", "saldoCorrienteRegistrado", "gastoDiferidoRegistrado", "dtaPresentado", "dtlPresentado")
            if num[k] is None]
    if falt:
        pr.append(problema("SIN_DATOS_REGISTRADOS", "Datos registrados no informados: " + "; ".join(falt) + ". Se asume lo que resulta de la "
                           "conciliación del cliente (impuesto y saldo corriente) o de sus saldos (gasto diferido); la presentación no se prueba."))

    rows = [{"id": c["id"], "concepto": c["concepto"], "tipo": _TIPOS_CONC[c["tipo"]][1], "importe": r2(c["cliente"]),
             "importeAuditor": "" if c["auditor"] is None else r2(c["auditor"]), "importeAuditado": r2(c["usado"]), "_row": c["_row"]}
            for c in conc]
    tot = {"baseImponibleCliente": cl["base"], "baseImponibleAuditada": au["base"], "impuestoCorrienteAuditado": au["ir"],
           "impuestoCorrienteRegistrado": ir_ef, "ajusteCorriente": aj_corr, "impuestoPorPagarAuditado": au["pagar"],
           "saldoCorrienteRegistrado": saldo_ef, "ajusteSaldoCorriente": aj_saldo, "excesoAmortizacionPerdidas": exceso_perd,
           "perdidasVencidas": venc, "dtaReconocido": dta_rec, "dtlRequerido": dtl_req, "dtaNoReconocido": dta_norec,
           "diferidoNetoRequerido": dif_req, "diferidoNetoRegistrado": dif_reg, "ajusteDiferido": aj_dif,
           "ajusteDiferidoResultados": aj_dif_res, "ajusteDiferidoORI": aj_dif_ori, "gastoDiferidoRequerido": gasto_dif_req}
    lab = {"baseImponibleCliente": "Base imponible según el cliente (total de control)", "baseImponibleAuditada": "Base imponible auditada",
           "impuestoCorrienteAuditado": "Impuesto corriente recalculado", "impuestoCorrienteRegistrado": "Impuesto corriente registrado",
           "ajusteCorriente": "Ajuste al impuesto corriente", "impuestoPorPagarAuditado": "Impuesto por pagar (− saldo a favor) recalculado",
           "saldoCorrienteRegistrado": "Impuesto por pagar registrado", "ajusteSaldoCorriente": "Ajuste al saldo de impuesto corriente",
           "excesoAmortizacionPerdidas": "Amortización de pérdidas en exceso", "perdidasVencidas": "Pérdidas vencidas sin amortizar",
           "dtaReconocido": "Activo por impuesto diferido requerido", "dtlRequerido": "Pasivo por impuesto diferido requerido",
           "dtaNoReconocido": "Activo diferido no reconocido (revelar, NIC 12.81 e)", "diferidoNetoRequerido": "Impuesto diferido neto requerido (+ activo)",
           "diferidoNetoRegistrado": "Impuesto diferido neto registrado (+ activo)", "ajusteDiferido": "Ajuste al impuesto diferido neto",
           "ajusteDiferidoResultados": "Ajuste al diferido: parte contra resultados", "ajusteDiferidoORI": "Ajuste al diferido: parte contra ORI",
           "gastoDiferidoRequerido": "Gasto (ingreso) por impuesto diferido requerido en resultados"}
    if gdr is not None:
        tot["gastoDiferidoRegistrado"] = gdr
        lab["gastoDiferidoRegistrado"] = "Gasto (ingreso) por impuesto diferido registrado"
    tot["reclasificacionORI"] = reclas
    lab["reclasificacionORI"] = "Gasto diferido llevado a resultados que corresponde a ORI u otro origen"
    tot["gastoTotalRequerido"] = etr["req"]
    lab["gastoTotalRequerido"] = "Gasto total por impuesto requerido"
    tot.update(gastoTotalRegistrado=etr["reg"], diferenciaNoExplicada=etr["noexp"])
    lab.update(gastoTotalRegistrado="Gasto total por impuesto registrado", diferenciaNoExplicada="Gasto registrado no explicado por la conciliación")
    if etr["tReq"] is not None:
        tot["tasaEfectivaRequerida"] = etr["tReq"] * 100
        lab["tasaEfectivaRequerida"] = "Tasa efectiva requerida (%)"
    if etr["tReg"] is not None:
        tot["tasaEfectivaRegistrada"] = etr["tReg"] * 100
        lab["tasaEfectivaRegistrada"] = "Tasa efectiva registrada (%)"
    tot["ajusteResultados"] = aj_res
    lab["ajusteResultados"] = "Ajuste neto al gasto por impuesto en resultados (+ más gasto)"

    detalle = {"cortes": {"actual": corte_a.isoformat()}, "anio": anio, "parametros": p, "pymes": pymes, "edicion": ed, "citas": cit,
               "num": num, "sn": sn, "irEf": ir_ef, "saldoEf": saldo_ef, "tarifa": tarifa, "propRecargo": prop_rec,
               "recargo": recargo, "tarifaFutura": tf_ef, "conc": conc, "cl": cl, "au": au, "pex": pex, "perd": perd, "partidas": part_rows,
               "tot": tot, "mov": mv, "comp": comp, "etr": etr, "gastoDifSaldos": gasto_dif_saldos, "reclas": reclas}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(v) for k, v in tot.items()}, "labels": lab,
            "primary": "ajusteResultados", "exceptions": pr, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

P = ref("02_Parametros")
CON, IC, PER, DT, TR, MOV, ETR, AJ = (ref(n) for n in ("03_Conciliacion", "04_Impuesto_corriente", "05_Perdidas", "06_Diferencias_temp",
                                                      "07_Tasa_reversion", "09_Movimiento", "11_Tasa_efectiva", "12_Ajustes"))
PE = ref("13_Partic_exentos")
_PEX = ["bruto", "neto", "gastos", "calc", "reg", "inf", "dif", "estado"]
PEF = {k: FILA0 + i for i, k in enumerate(_PEX)}
_PAR = ["corte", "marco", "tasaIR", "puntosRecargo", "proporcionRecargo", "participacion", "ingresoExentoBruto",
        "participacionExentosInformada", "limitePerdidas", "plazoPerdidas", "tasaFutura",
        "anioTasaFutura", "perdidasPermitidas", "probabilidadPerdidas", "retenciones", "anticipos", "creditoAnterior",
        "impuestoCorrienteRegistrado", "saldoCorrienteRegistrado", "gastoDiferidoRegistrado", "dtaPerdidasInicial", "dtaPerdidasRegistrado",
        "derechoCompensar", "dtaPresentado", "dtlPresentado", "umbralTasaEfectiva"]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
_IC = ["u", "part", "ex", "nd", "ge", "pe", "ded", "otros", "b0", "lim", "disp", "perd", "base", "tarifa", "ir", "ret", "ant", "cred", "pagar",
       "irReg", "saldoReg"]
ICF = {k: FILA0 + i for i, k in enumerate(_IC)}
_ETR = ["rai", "teo", "nd", "ex", "ded", "perd", "otros", "neg", "corr", "dif", "req", "reg", "noexp", "tReq", "tReg", "tApl"]
ETRF = {k: FILA0 + i for i, k in enumerate(_ETR)}
_AJ = ["irAud", "irReg", "ajCorr", "pagarAud", "saldoReg", "ajSaldo", "excesoPerd", "vencidas", "dtaRec", "dtl", "dtaNoRec", "difReq", "difReg",
       "ajDif", "ajDifRes", "ajDifOri", "gastoDifReq", "gastoDifSaldos", "gastoDifReg", "reclas", "gastoReq", "gastoReg", "noexp", "ajRes"]
AJF = {k: FILA0 + i for i, k in enumerate(_AJ)}


def _pb(k):
    return f"{P}$B${PAR[k]}"


def _rg(h, col, n):
    return f"{h}${col}${FILA0}:${col}${FILA0 + n - 1}"


def suma(col, fin_fila, valor):
    """Fila TOTAL sin redondear el valor de control (base.suma redondea y difiere de Excel en medios centavos)."""
    return fx(f"SUM({col}{FILA0}:{col}{max(fin_fila, FILA0)})", valor)


def _sum(h, col, n):
    return f"SUM({_rg(h, col, n)})" if n else "0"


def _sumif(h, ccol, crit, col, n):
    return f'SUMIF({_rg(h, ccol, n)},"{crit}",{_rg(h, col, n)})' if n else "0"


# Explicaciones humanas de «Cómo se calcula esta hoja» (una por columna calculada).
EXPLICA = {
    "01_Resumen": {
        "Importe": ("Trae cada importe de la hoja 12 (Ajustes propuestos), concepto por concepto; las bases imponibles vienen "
                    "de la hoja 04 (Impuesto corriente) y las tasas efectivas de la hoja 11 (Tasa efectiva), multiplicadas "
                    "por 100 para mostrarlas en %."),
    },
    "03_Conciliacion": {
        "Importe auditado": ("Usa el importe según el auditor cuando lo hay y, si está vacío, conserva el importe según el "
                             "cliente."),
        "Diferencia": ("Resta el importe según el cliente al importe auditado: muestra cuánto cambió el auditor en cada "
                       "renglón."),
    },
    "04_Impuesto_corriente": {
        "Según cliente": ("Arma la liquidación con los importes del cliente: cada renglón suma en la hoja 03 (Conciliación "
                          "tributaria) el «Importe según cliente» de su tipo y luego calcula subtotales, límite de pérdidas, "
                          "base, tarifa, impuesto y saldo con los parámetros de la hoja 02 y las pérdidas disponibles de la "
                          "hoja 05; las dos últimas filas usan lo registrado en la hoja 02 y, si está vacío, lo calculado."),
        "Auditado": ("Hace la misma liquidación con el «Importe auditado» de la hoja 03, pero recalcula la participación "
                     "trabajadores (% × utilidad), la participación atribuible a exentos (hoja 13, o la del cliente si no "
                     "se puede recalcular) y la amortización de pérdidas como el menor entre la solicitada, el límite y lo "
                     "disponible en la hoja 05."),
        "Diferencia": ("Resta el valor según cliente al valor auditado en cada renglón, para ver en qué punto cambia la "
                       "liquidación."),
    },
    "05_Perdidas": {
        "Último año": ("Suma al año de origen de la pérdida el plazo para amortizarla de la hoja 02 (Parámetros); si el "
                       "cliente informó el año de vencimiento, se usa ese dato."),
        "Disponible": "Resta a la pérdida lo ya amortizado en años anteriores: es lo que queda por amortizar.",
        "Vencida": "Marca «Sí» si el último año para amortizar es anterior al año del corte de la hoja 02 (Parámetros).",
        "Disponible no vencido": "Si la pérdida no está vencida, toma su saldo disponible; si está vencida, cero.",
        "Saldo vencido": ("Si la pérdida está vencida, toma su saldo disponible, que ya no se puede amortizar; si no, "
                          "cero."),
        "Amortización del año": ("Reparte la amortización auditada de la hoja 04 (Impuesto corriente) entre las pérdidas, "
                                 "de la más antigua a la más reciente, sin pasar del saldo no vencido de cada una."),
        "Remanente": "Resta la amortización del año al disponible no vencido: es lo que sigue pendiente de cada pérdida.",
        "Arrastrable a años futuros": ("Si el último año para amortizar es posterior al año del corte, el remanente se "
                                       "puede usar en años futuros; si no, cero."),
        "Activo diferido requerido": ("Si la ley admite diferido por pérdidas y hay probable ganancia fiscal (ambos «Sí» en "
                                      "la hoja 02), multiplica lo arrastrable por la tarifa aplicable de la hoja 04; si no, "
                                      "cero."),
        "Activo diferido no reconocido": ("Multiplica lo arrastrable por la tarifa aplicable de la hoja 04 y le resta el "
                                          "activo diferido requerido: es el activo que no se reconoce y se revela."),
    },
    "06_Diferencias_temp": {
        "Diferencia temporaria (+ imponible)": ("En un activo resta la base fiscal al valor en libros; en un pasivo, resta "
                                                "el valor en libros a la base fiscal. Positiva es imponible y negativa, "
                                                "deducible."),
        "Clase": "Clasifica la diferencia: mayor que cero es «Imponible», menor que cero «Deducible» y cero «Sin diferencia».",
        "Tasa (%)": "Trae la tasa esperada para el año de reversión desde la hoja 07 (Tasa de reversión).",
        "Pasivo diferido": ("Si la diferencia es imponible, la multiplica por la tasa: es el pasivo por impuesto diferido; "
                            "si no, cero."),
        "Activo diferido bruto": ("Si la diferencia es deducible, multiplica su valor absoluto por la tasa: es el activo "
                                  "diferido antes de evaluar si se recupera; si no, cero."),
        "Activo diferido reconocido": ("Reconoce el activo diferido bruto solo si la ley lo permite y es probable "
                                       "recuperarlo (columnas «Permitido» y «Probable» en «Sí»); si no, cero."),
        "Activo diferido no reconocido": "Resta el activo reconocido al activo bruto: es la parte que no se registra y se revela.",
        "Diferido requerido (+ activo)": ("Resta el pasivo diferido al activo diferido reconocido: positivo es activo neto "
                                          "y negativo, pasivo neto."),
        "Ajuste": ("Resta el saldo registrado al cierre al diferido requerido: es lo que falta (+) o sobra (−) en los "
                   "libros."),
        "Movimiento requerido": ("Resta el saldo registrado al inicio al diferido requerido: es cuánto debió moverse el "
                                 "diferido en el año."),
        "A resultados (+ gasto)": ("Si la partida no es de ORI, lleva el movimiento a resultados con el signo cambiado (un "
                                   "aumento del activo es ingreso y se muestra negativo); si es de ORI, cero."),
        "A ORI (+ cargo)": ("Si la partida es de ORI, lleva el movimiento al otro resultado integral con el signo "
                            "cambiado; si no, cero."),
    },
    "07_Tasa_reversion": {
        "Año de reversión": ("Trae el año en que se revierte la diferencia desde la hoja 06 (Diferencias temporarias); "
                             "vacío si no se informó."),
        "Tasa usada por el cliente (%)": ("Es la tasa que informó el cliente; si no la informó, repite la tasa esperada, "
                                          "de modo que la diferencia de tasa queda en cero."),
        "Tasa esperada = aprobada + recargo (%)": (
            "Si hay tasa futura aprobada, su año de inicio y año de reversión, y la reversión cae desde ese año, suma a la "
            "tasa futura el recargo (tarifa aplicable − tarifa general); en los demás casos usa la tarifa aplicable de la "
            "hoja 04 (Impuesto corriente)."),
        "Diferencia de tasa (p.p.)": "Resta la tasa esperada a la tasa usada por el cliente, en puntos porcentuales.",
        "Diferencia temporaria": "Trae la diferencia temporaria de la partida desde la hoja 06 (Diferencias temporarias).",
        "Efecto en el diferido": ("Multiplica el valor absoluto de la diferencia temporaria por la diferencia de tasa: es "
                                  "el error en el diferido por usar una tasa distinta."),
    },
    "08_Recuperabilidad": {
        "Activo diferido bruto": ("Trae el activo diferido bruto de la partida desde la hoja 06; en la fila de pérdidas, "
                                  "multiplica lo arrastrable de la hoja 05 por la tarifa aplicable."),
        "Permitido": ("Trae de la hoja 06 si la ley admite el diferido de la partida; en la fila de pérdidas, el "
                      "parámetro de la hoja 02 (Parámetros)."),
        "Probable": ("Trae de la hoja 06 si es probable recuperar el activo; en la fila de pérdidas, el parámetro de "
                     "probable ganancia fiscal de la hoja 02."),
        "Reconocible": ("Trae el activo diferido reconocido de la hoja 06; en la fila de pérdidas, suma el activo diferido "
                        "requerido de la hoja 05 (Pérdidas tributarias)."),
        "Registrado al cierre": ("Toma el saldo registrado al cierre de la hoja 06 (en pérdidas, el parámetro de la hoja "
                                 "02) y lo deja en cero si es negativo, porque aquí solo cuenta el activo."),
        "Registrado en exceso": ("Resta lo reconocible a lo registrado al cierre, sin bajar de cero: es el activo "
                                 "registrado que no se puede sostener."),
        "Conclusión": ("Si la ley no lo admite, «No admitido tributariamente»; si no hay probable ganancia fiscal, «Sin "
                       "probabilidad de ganancia fiscal»; en otro caso, «Reconocible»."),
    },
    "09_Movimiento": {
        "Registrado al inicio": ("Suma el saldo registrado al inicio de la hoja 06 para las partidas sin ORI (primera fila) "
                                 "o con ORI (segunda); la fila de pérdidas toma el activo por pérdidas al inicio de la hoja "
                                 "02."),
        "Requerido al cierre": ("Suma el diferido requerido de la hoja 06 para las partidas sin ORI o con ORI; la fila de "
                                "pérdidas suma el activo diferido requerido de la hoja 05 (Pérdidas tributarias)."),
        "Movimiento": ("Resta lo registrado al inicio a lo requerido al cierre: es el movimiento del diferido que "
                       "corresponde al año."),
        "A resultados (+ gasto)": ("Lleva el movimiento a resultados con el signo cambiado en la fila sin ORI y en la de "
                                   "pérdidas; en la fila de ORI, cero."),
        "A ORI (+ cargo)": ("Lleva el movimiento al otro resultado integral con el signo cambiado solo en la fila de "
                            "partidas de ORI; en las demás, cero."),
        "Registrado al cierre": ("Suma el saldo registrado al cierre de la hoja 06 para las partidas sin ORI o con ORI; la "
                                 "fila de pérdidas toma el activo por pérdidas al cierre de la hoja 02."),
        "Ajuste": ("Resta lo registrado al cierre a lo requerido al cierre: es la corrección que necesita el saldo del "
                   "diferido (+ más activo o menos pasivo)."),
    },
    "10_Compensacion": {
        "Importe": ("Suma los saldos registrados de la hoja 06 (activos, más el activo por pérdidas de la hoja 02, y "
                    "pasivos por separado) y los requeridos de las hojas 06 y 05; con derecho legal de compensar presenta "
                    "solo el neto, y compara lo presentado según la hoja 02 con lo que corresponde."),
    },
    "11_Tasa_efectiva": {
        "Importe": ("Parte del resultado antes del impuesto (hoja 04) por la tarifa aplicable, suma el efecto de cada "
                    "partida de conciliación de la hoja 04 × tarifa hasta llegar al impuesto corriente recalculado, añade "
                    "el diferido de la hoja 09 y lo compara con el gasto registrado."),
        "% del resultado": ("Divide cada importe para el resultado contable antes del impuesto; las tres últimas filas "
                            "muestran la tasa efectiva requerida, la registrada y la tarifa aplicable."),
    },
    "12_Ajustes": {
        "Importe": ("Trae los importes recalculados y registrados de las hojas 04, 05, 06, 09 y 11 y de la hoja 02 "
                    "(Parámetros); cada ajuste es recalculado − registrado y el ajuste neto al gasto = ajuste corriente − "
                    "ajuste del diferido a resultados − reclasificación."),
    },
    "13_Partic_exentos": {
        "Importe / estado": ("Toma el ingreso exento bruto de la hoja 02 y los renglones de la hoja 04; recalcula la "
                             "participación atribuible como % de participación × ingreso exento bruto (cero si no hay "
                             "exentos o la utilidad no es positiva; vacío si falta el ingreso bruto), la compara con la "
                             "registrada e indica si el cálculo quedó hecho o bloqueado."),
    },
    "14_Asientos": {
        "Debe": ("Trae de la hoja 12 (Ajustes propuestos), en valor absoluto, el ajuste de cada asiento en la cuenta que se "
                 "debita según su signo."),
        "Haber": ("Trae el mismo ajuste de la hoja 12 (Ajustes propuestos), en valor absoluto, en la cuenta que se "
                  "acredita, para que el asiento cuadre."),
    },
}

# Panel del dashboard (formato en graficos.py): la población es la conciliación tributaria del cliente (su base
# imponible); el auditor recalcula el gasto total por impuesto (corriente + diferido) y lo compara con el registrado.
PANEL = {
    "poblacion": {"rotulo": "Base imponible del cliente", "hoja": "03_Conciliacion", "col": "Importe según cliente"},
    "recalculado": {"rotulo": "Gasto por impuesto recalculado", "total": "gastoTotalRequerido"},
    "registrado": {"rotulo": "Gasto por impuesto registrado", "total": "gastoTotalRegistrado"},
    # La dona reparte el gasto recalculado (partes que suman); la conciliación, con partidas que suman y restan,
    # va en barras con su signo y el nombre de cada concepto.
    "composicion": {"rotulo": "Gasto por impuesto recalculado", "totales": [
        ["Impuesto corriente", "impuestoCorrienteAuditado"], ["Impuesto diferido", "gastoDiferidoRequerido"]]},
    "distribucion": {"rotulo": "Conciliación tributaria auditada por concepto", "hoja": "03_Conciliacion", "etiqueta": "Concepto",
                     "valor": "Importe auditado"},
}


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    conc, cl, au, perd, pt, mv, comp, etr, cit, num =(d[k] for k in ("conc", "cl", "au", "perd", "partidas", "mov", "comp", "etr", "citas", "num"))
    pex = d["pex"]
    t = d["tot"]                       # sin redondear: Excel calcula con todos los decimales
    nc, nl, npt = len(conc), len(perd), len(pt)
    marco = (MARCO_PYMES + f" {d['edicion']}") if d["pymes"] else MARCO_COMPLETAS
    ti, yr = _pb("tasaIR"), f"YEAR({_pb('corte')})"
    vr = "vigente al corte"
    # Tarifa aplicable (LRTI art. 37; Reglamento art. 51) y recargo, que también mide la tasa esperada del diferido.
    TARIFA_F = f"{ti}+{_pb('puntosRecargo')}*IF({_pb('proporcionRecargo')}>=50,100,{_pb('proporcionRecargo')})/100"
    TAR = f"{IC}$C${ICF['tarifa']}"                 # tarifa aplicable ya calculada en 04_Impuesto_corriente
    REC = f"({TAR}-{ti})"

    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Marco contable", marco, f"{cit['marco']} — mismo cálculo en ambos marcos; cambian las citas"],
        ["Tarifa general del impuesto a la renta (%)", num["tasaIR"], f"LRTI art. 37 — {vr}"],
        ["Puntos adicionales (paraísos fiscales / composición societaria)", num["puntosRecargo"], f"LRTI art. 37 — {vr}"],
        ["Composición societaria en paraísos fiscales o no informada (%)", num["proporcionRecargo"],
         f"Reglamento art. 51: el recargo grava esa misma proporción de la base y el 100 % cuando llega al 50 % — aplicada {n2(d['propRecargo'])} %"],
        ["Participación de trabajadores (%)", num["participacion"], f"Código del Trabajo art. 97 — {vr}"],
        ["Ingreso exento bruto del ejercicio (antes de gastos atribuibles)", num["ingresoExentoBruto"],
         f"Reglamento LRTI art. 46 num. 5: «el 15% de tales ingresos» — {vr}; vacío: no se recalcula la participación atribuible"],
        ["Participación atribuible a exentos informada por el cliente", num["participacionExentosInformada"],
         "Papel de trabajo del cliente / casillero del F-101"],
        ["Límite anual de amortización de pérdidas (%)", num["limitePerdidas"], f"LRTI art. 11 — {vr}"],
        ["Plazo para amortizar pérdidas (años)", num["plazoPerdidas"], f"LRTI art. 11 — {vr}"],
        ["Tasa aprobada para años futuros (%)", num["tasaFutura"], f"{cit['tasa']} — tasa aprobada o prácticamente aprobada al cierre"],
        ["Año desde el que rige la tasa futura", num["anioTasaFutura"], "Ley publicada al cierre"],
        ["Ley admite diferido por pérdidas", d["sn"]["perdidasPermitidas"], "Reglamento LRTI, art. innumerado a continuación del art. 28 (num. 5: provisiones distintas de cuentas incobrables y desmantelamiento, utilizables cuando se paguen —jubilación y desahucio solo por la parte no deducible, interpretación: LRTI art. 10 num. 13—; num. 8: pérdidas tributarias)"],
        ["Probable ganancia fiscal para las pérdidas", d["sn"]["probabilidadPerdidas"], "NIC 12.35–36 — proyecciones fiscales"],
        ["Retenciones en la fuente del ejercicio", num["retenciones"], "Comprobantes de retención / F-101"],
        ["Anticipos pagados", num["anticipos"], "F-115 / F-101"],
        ["Crédito tributario de años anteriores", num["creditoAnterior"], "F-101"],
        ["Gasto por impuesto corriente registrado", num["impuestoCorrienteRegistrado"], "Mayor"],
        ["Impuesto por pagar registrado (+) / saldo a favor (−)", num["saldoCorrienteRegistrado"], "Estado de situación financiera"],
        ["Gasto (ingreso) por impuesto diferido registrado", num["gastoDiferidoRegistrado"], "Estado de resultados"],
        ["Activo diferido por pérdidas al inicio", num["dtaPerdidasInicial"], "Mayor"],
        ["Activo diferido por pérdidas al cierre", num["dtaPerdidasRegistrado"], "Mayor"],
        ["Derecho legal de compensar (misma autoridad)", d["sn"]["derechoCompensar"], cit["comp"]],
        ["Activo por impuesto diferido presentado", num["dtaPresentado"], "Estado de situación financiera"],
        ["Pasivo por impuesto diferido presentado", num["dtlPresentado"], "Estado de situación financiera"],
        ["Diferencia tolerable en la tasa efectiva (p.p.)", num["umbralTasaEfectiva"], "Juicio del auditor (materialidad)"],
    ]

    # 03 · Conciliación.
    fin_c = FILA0 + nc - 1
    c03 = []
    for i, c in enumerate(conc):
        r = FILA0 + i
        c03.append([c["id"], c["concepto"], c["tipo"], c["signo"], n2(c["cliente"]), c["auditor"],
                    fx(f'IF(F{r}<>"",F{r},E{r})', c["usado"]), fx(f"G{r}-E{r}", c["dif"])])
    tot_c = ["TOTAL", "", "", "", suma("E", fin_c, cl["base"]), None, suma("G", fin_c, sum(c["usado"] for c in conc)),
             suma("H", fin_c, sum(c["dif"] for c in conc))]

    # 04 · Impuesto corriente.
    sb = lambda tp: _sumif(CON, "C", tp, "E", nc)
    sg = lambda tp: _sumif(CON, "C", tp, "G", nc)
    B = lambda k: f"B{ICF[k]}"
    C = lambda k: f"C{ICF[k]}"
    disp_f = _sum(PER, "G", nl)
    perd_c = f"-MIN(-{sg('perdidas')},{C('lim')},{C('disp')})" if nl else f"-MIN(-{sg('perdidas')},{C('lim')})"
    filas04 = [
        ("u", "Utilidad (pérdida) contable antes de participación e impuesto", sb("utilidad"), sg("utilidad"), "03_Conciliacion"),
        ("part", "(−) Participación trabajadores", sb("participacion"), f"-MAX({C('u')},0)*{_pb('participacion')}/100", "Recalculada: % × utilidad"),
        ("ex", "(−) Ingresos exentos", sb("exentos"), sg("exentos"), "LRTI art. 9 (texto oficial hasta 2-jul-2021: contrastar reformas posteriores)"),
        ("nd", "(+) Gastos no deducibles", sb("no_deducibles"), sg("no_deducibles"), "LRTI art. 10"),
        ("ge", "(+) Gastos atribuibles a ingresos exentos", sb("gastos_exentos"), sg("gastos_exentos"), "Reglamento LRTI art. 46 num. 4 (y art. 47, prorrateo)"),
        ("pe", "(+) Participación atribuible a ingresos exentos", sb("participacion_exentos"),
         f'IF({PE}B{PEF["calc"]}="",B{ICF["pe"]},{PE}B{PEF["calc"]})',
         "Reglamento LRTI art. 46 num. 5: «el 15% de tales ingresos» (base bruta) — ver 13_Partic_exentos; sin el ingreso exento bruto "
         "informado el recálculo queda bloqueado y se conserva el importe del cliente"),
        ("ded", "(−) Deducciones adicionales", sb("deducciones"), sg("deducciones"), "LRTI art. 10"),
        ("otros", "(±) Otras partidas de conciliación", sb("otros"), sg("otros"), "03_Conciliacion"),
        ("b0", "Utilidad gravable antes de amortizar pérdidas", f"SUM({B('u')}:{B('otros')})", f"SUM({C('u')}:{C('otros')})", ""),
        ("lim", "Límite de amortización de pérdidas", f"MAX({B('b0')},0)*{_pb('limitePerdidas')}/100", f"MAX({C('b0')},0)*{_pb('limitePerdidas')}/100",
         "LRTI art. 11"),
        ("disp", "Pérdidas disponibles no vencidas", disp_f if nl else None, disp_f if nl else None, "05_Perdidas"),
        ("perd", "(−) Amortización de pérdidas", sb("perdidas"), perd_c, "mín(solicitada, límite, disponible)"),
        ("base", "Base imponible", f"{B('b0')}+{B('perd')}", f"{C('b0')}+{C('perd')}", "Total de control = suma de 03_Conciliacion"),
        ("tarifa", "Tarifa aplicable (%) = general + puntos × proporción (100 % si ≥ 50 %)", TARIFA_F, TARIFA_F,
         "LRTI art. 37; Reglamento art. 51"),
        ("ir", "Impuesto a la renta causado", f"MAX({B('base')},0)*{B('tarifa')}/100", f"MAX({C('base')},0)*{C('tarifa')}/100", cit["corr"]),
        ("ret", "(−) Retenciones en la fuente", _pb("retenciones"), _pb("retenciones"), "Parámetros"),
        ("ant", "(−) Anticipos pagados", _pb("anticipos"), _pb("anticipos"), "Parámetros"),
        ("cred", "(−) Crédito tributario de años anteriores", _pb("creditoAnterior"), _pb("creditoAnterior"), "Parámetros"),
        ("pagar", "Impuesto por pagar (− saldo a favor)", f"{B('ir')}-{B('ret')}-{B('ant')}-{B('cred')}",
         f"{C('ir')}-{C('ret')}-{C('ant')}-{C('cred')}", f"{cit['corr']}: pasivo o activo corriente"),
        ("irReg", "Impuesto corriente registrado (B) frente a recalculado (C)",
         f'IF({_pb("impuestoCorrienteRegistrado")}="",{B("ir")},{_pb("impuestoCorrienteRegistrado")})', C("ir"), "Vacío: el de la conciliación del cliente"),
        ("saldoReg", "Saldo corriente registrado (B) frente a recalculado (C)",
         f'IF({_pb("saldoCorrienteRegistrado")}="",{B("pagar")},{_pb("saldoCorrienteRegistrado")})', C("pagar"), "Vacío: el de la conciliación del cliente"),
    ]
    vals04 = {"irReg": (d["irEf"], au["ir"]), "saldoReg": (d["saldoEf"], au["pagar"])}
    c04 = []
    for k, txt, fb, fc, rf in filas04:
        r = ICF[k]
        vb, vc = vals04[k] if k in vals04 else (cl[k], au[k])
        if fb is None:
            c04.append([txt, None, None, None, rf])
            continue
        c04.append([txt, fx(fb, vb), fx(fc, vc), fx(f"C{r}-B{r}", vc - vb), rf])

    # 05 · Pérdidas.
    c05 = []
    for i, x in enumerate(perd):
        r = FILA0 + i
        c05.append([x["origen"], n2(x["importe"]), n2(x["amortizado"]),
                    x["vence"] if x["venceDato"] else fx(f"A{r}+{_pb('plazoPerdidas')}", x["vence"]),
                    fx(f"B{r}-C{r}", x["disponible"]), fx(f'IF(D{r}<{yr},"Sí","No")', "Sí" if x["vencida"] else "No"),
                    fx(f'IF(F{r}="No",E{r},0)', x["noVencido"]), fx(f'IF(F{r}="Sí",E{r},0)', x["saldoVencido"]),
                    fx(f"MAX(0,MIN(G{r},-{IC}$C${ICF['perd']}-SUM(I${FILA0 - 1}:I{r - 1})))", x["amortAnio"]),
                    fx(f"G{r}-I{r}", x["remanente"]), fx(f"IF(D{r}>{yr},J{r},0)", x["arrastrable"]),
                    fx(f'IF(AND({_pb("perdidasPermitidas")}="Sí",{_pb("probabilidadPerdidas")}="Sí"),K{r}*{TAR}/100,0)', x["dtaReq"]),
                    fx(f"K{r}*{TAR}/100-L{r}", x["dtaNoRec"])])
    fin_l = FILA0 + nl - 1
    sl = lambda k: sum(x[k] for x in perd)
    tot_l = (["TOTAL", suma("B", fin_l, sl("importe")), suma("C", fin_l, sl("amortizado")), None, suma("E", fin_l, sl("disponible")), "",
              suma("G", fin_l, sl("noVencido")), suma("H", fin_l, sl("saldoVencido")), suma("I", fin_l, sl("amortAnio")),
              suma("J", fin_l, sl("remanente")), suma("K", fin_l, sl("arrastrable")), suma("L", fin_l, sl("dtaReq")),
              suma("M", fin_l, sl("dtaNoRec"))] if perd else None)

    # 06 · Diferencias temporarias · 07 · Tasa de reversión.
    tf_, af_ = _pb("tasaFutura"), _pb("anioTasaFutura")
    # Fórmula de la tasa esperada (NIC 12.47 y 49; LRTI art. 37; Reglamento art. 51), visible en la cédula:
    formula_tasa = (f"Tasa esperada = tarifa del año de reversión + recargo = "
                    f"{n2(num['tasaIR'])} % + {n2(num['puntosRecargo'])} puntos × {n2(d['propRecargo'])} % = {n2(d['tarifa'])} %"
                    + (f"; desde {int(num['anioTasaFutura'])}: {n2(num['tasaFutura'])} % + recargo = {n2(d['tarifaFutura'])} %"
                       if num["tasaFutura"] is not None else "") + " (NIC 12.47, 49)")
    c06, c07 = [], []
    for i, x in enumerate(pt):
        r = FILA0 + i
        c06.append([x["partida"], x["nat"], n2(x["libros"]), n2(x["base"]),
                    fx(f'IF(B{r}="Activo",C{r}-D{r},D{r}-C{r})', x["dt"]),
                    fx(f'IF(E{r}>0,"Imponible",IF(E{r}<0,"Deducible","Sin diferencia"))', x["clase"]),
                    x["anio"], fx(f"{TR}D{r}", x["tasa"]), fx(f"IF(E{r}>0,E{r}*H{r}/100,0)", x["dtl"]),
                    fx(f"IF(E{r}<0,-E{r}*H{r}/100,0)", x["dtaBruto"]), x["perm"], x["prob"],
                    fx(f'IF(AND(K{r}="Sí",L{r}="Sí"),J{r},0)', x["dtaRec"]), fx(f"J{r}-M{r}", x["dtaNoRec"]),
                    fx(f"M{r}-I{r}", x["req"]), n2(x["ini"]), n2(x["cie"]), fx(f"O{r}-Q{r}", x["aj"]), x["ori"],
                    fx(f"O{r}-P{r}", x["mov"]), fx(f'IF(S{r}="No",-T{r},0)', x["res"]), fx(f'IF(S{r}="Sí",-T{r},0)', x["movOri"])])
        c07.append([x["partida"], fx(f'IF({DT}G{r}="","",{DT}G{r})', x["anio"] if x["anio"] is not None else ""),
                    n2(x["tasaDato"]) if x["tasaDato"] is not None else fx(f"D{r}", x["tasaCli"]),
                    fx(f'IF(AND({tf_}<>"",{af_}<>"",B{r}<>""),IF(B{r}>={af_},{tf_}+{REC},{TAR}),{TAR})', x["tasa"]),
                    fx(f"C{r}-D{r}", x["difTasa"]), fx(f"{DT}E{r}", x["dt"]), fx(f"ABS(F{r})*E{r}/100", x["efectoTasa"]),
                    formula_tasa])
    fin_p = FILA0 + npt - 1
    s6 = lambda k: sum(x[k] for x in pt)
    tot6 = (["TOTAL", "", suma("C", fin_p, s6("libros")), suma("D", fin_p, s6("base")), suma("E", fin_p, s6("dt")), "", None, None,
             suma("I", fin_p, s6("dtl")), suma("J", fin_p, s6("dtaBruto")), "", "", suma("M", fin_p, s6("dtaRec")), suma("N", fin_p, s6("dtaNoRec")),
             suma("O", fin_p, s6("req")), suma("P", fin_p, s6("ini")), suma("Q", fin_p, s6("cie")), suma("R", fin_p, s6("aj")), "",
             suma("T", fin_p, s6("mov")), suma("U", fin_p, s6("res")), suma("V", fin_p, s6("movOri"))] if pt else None)
    tot7 = (["TOTAL", None, None, None, None, None, suma("G", fin_p, s6("efectoTasa")), ""] if pt else None)

    # 08 · Recuperabilidad.
    c08 = []
    for i, x in enumerate(pt):
        if not (x["dt"] < 0 or x["cie"] > 0):
            continue
        r, rd = FILA0 + len(c08), FILA0 + i
        c08.append([x["partida"], fx(f"{DT}J{rd}", x["dtaBruto"]), fx(f"{DT}K{rd}", x["perm"]), fx(f"{DT}L{rd}", x["prob"]),
                    fx(f"{DT}M{rd}", x["dtaRec"]), fx(f"MAX({DT}Q{rd},0)", max(x["cie"], 0)),
                    fx(f"MAX(F{r}-E{r},0)", max(max(x["cie"], 0) - x["dtaRec"], 0)),
                    fx(f'IF(C{r}="No","No admitido tributariamente",IF(D{r}="No","Sin probabilidad de ganancia fiscal","Reconocible"))',
                       "No admitido tributariamente" if x["perm"] == "No" else ("Sin probabilidad de ganancia fiscal" if x["prob"] == "No" else "Reconocible"))])
    r = FILA0 + len(c08)
    sn = d["sn"]
    bl = sl("arrastrable") * d["tarifa"] / 100
    rl = max(num["dtaPerdidasRegistrado"] or 0, 0)
    c08.append(["Pérdidas tributarias no utilizadas", fx(f"{_sum(PER, 'K', nl)}*{TAR}/100", bl), fx(_pb("perdidasPermitidas"), sn["perdidasPermitidas"]),
                fx(_pb("probabilidadPerdidas"), sn["probabilidadPerdidas"]), fx(_sum(PER, "L", nl), sl("dtaReq")),
                fx(f"MAX({_pb('dtaPerdidasRegistrado')},0)", rl), fx(f"MAX(F{r}-E{r},0)", max(rl - sl("dtaReq"), 0)),
                fx(f'IF(C{r}="No","No admitido tributariamente",IF(D{r}="No","Sin probabilidad de ganancia fiscal","Reconocible"))',
                   "No admitido tributariamente" if sn["perdidasPermitidas"] == "No" else
                   ("Sin probabilidad de ganancia fiscal" if sn["probabilidadPerdidas"] == "No" else "Reconocible"))])
    fin8 = r
    v8 = lambda j: sum(fila[j]["v"] for fila in c08)
    tot8 = ["TOTAL", suma("B", fin8, v8(1)), "", "", suma("E", fin8, v8(4)), suma("F", fin8, v8(5)), suma("G", fin8, v8(6)), ""]

    # 09 · Movimiento.
    c09 = []
    for i, x in enumerate(mv):
        r = FILA0 + i
        if x["k"] == "perd":
            fi, fq, fc = _pb("dtaPerdidasInicial"), _sum(PER, "L", nl), _pb("dtaPerdidasRegistrado")
        else:
            crit = "Sí" if x["ori"] else "No"
            fi, fq, fc = _sumif(DT, "S", crit, "P", npt), _sumif(DT, "S", crit, "O", npt), _sumif(DT, "S", crit, "Q", npt)
        c09.append([x["concepto"], fx(fi, x["ini"]), fx(fq, x["req"]), fx(f"C{r}-B{r}", x["mov"]),
                    fx(f"-D{r}" if not x["ori"] else "0", x["aRes"]), fx(f"-D{r}" if x["ori"] else "0", x["aOri"]),
                    fx(fc, x["cie"]), fx(f"C{r}-G{r}", x["aj"])])
    fin9 = FILA0 + 2
    sm = lambda k: sum(x[k] for x in mv)
    tot9 = ["TOTAL", suma("B", fin9, sm("ini")), suma("C", fin9, sm("req")), suma("D", fin9, sm("mov")), suma("E", fin9, sm("aRes")),
            suma("F", fin9, sm("aOri")), suma("G", fin9, sm("cie")), suma("H", fin9, sm("aj"))]
    fila_tot9 = fin9 + 1

    # 10 · Compensación.
    der = _pb("derechoCompensar")
    q = _rg(DT, "Q", npt)
    dp, lp = num["dtaPresentado"], num["dtlPresentado"]
    c10 = [
        ["Activo diferido bruto registrado", fx((f'SUMIF({q},">0")+' if npt else "") + f"MAX({_pb('dtaPerdidasRegistrado')},0)", comp["dtaReg"]), "06_Diferencias_temp Q > 0 + pérdidas"],
        ["Pasivo diferido bruto registrado", fx(f'-SUMIF({q},"<0")' if npt else "0", comp["dtlReg"]), "06_Diferencias_temp Q < 0"],
        ["Derecho legal de compensar", fx(der, d["sn"]["derechoCompensar"]), cit["comp"]],
        ["Activo diferido a presentar (saldos registrados)", fx(f'IF(B7="Sí",MAX(B5-B6,0),B5)', comp["dtaEsp"]), "Neto si hay derecho"],
        ["Pasivo diferido a presentar (saldos registrados)", fx(f'IF(B7="Sí",MAX(B6-B5,0),B6)', comp["dtlEsp"]), "Neto si hay derecho"],
        ["Activo diferido presentado", fx(f'IF({_pb("dtaPresentado")}<>"",{_pb("dtaPresentado")},"")', dp if dp is not None else ""), "Parámetros"],
        ["Pasivo diferido presentado", fx(f'IF({_pb("dtlPresentado")}<>"",{_pb("dtlPresentado")},"")', lp if lp is not None else ""), "Parámetros"],
        ["Diferencia de presentación del activo", fx('IF(B10="","",B10-B8)', comp["difDta"] if comp["difDta"] is not None else ""), "Compensación indebida o faltante"],
        ["Diferencia de presentación del pasivo", fx('IF(B11="","",B11-B9)', comp["difDtl"] if comp["difDtl"] is not None else ""), ""],
        ["Activo diferido requerido (auditado, bruto)", fx(f"{_sum(DT, 'M', npt)}+{_sum(PER, 'L', nl)}", comp["dtaAud"]), "06 + 05"],
        ["Pasivo diferido requerido (auditado, bruto)", fx(_sum(DT, "I", npt), comp["dtlAud"]), "06"],
        ["Activo diferido a presentar (auditado)", fx('IF(B7="Sí",MAX(B14-B15,0),B14)', comp["dtaPresAud"]), cit["comp"]],
        ["Pasivo diferido a presentar (auditado)", fx('IF(B7="Sí",MAX(B15-B14,0),B15)', comp["dtlPresAud"]), cit["comp"]],
    ]

    # 11 · Tasa efectiva (NIC 12.81 c).
    E_ = lambda k: f"B{ETRF[k]}"
    pct = lambda k: fx(f'IF(OR({E_(k)}="",$B${ETRF["rai"]}=0),"",{E_(k)}/$B${ETRF["rai"]})',
                       None if etr[k] is None or etr["rai"] == 0 else etr[k] / etr["rai"])
    tar = f"{IC}$C${ICF['tarifa']}/100"
    etr_f = {
        "rai": ("Resultado contable antes del impuesto (utilidad − participación)", f"{IC}C{ICF['u']}+{IC}C{ICF['part']}"),
        "teo": ("Impuesto teórico = resultado × tasa aplicable", f"{E_('rai')}*{tar}"),
        "nd": ("Efecto de gastos no deducibles y atribuibles a exentos", f"({IC}C{ICF['nd']}+{IC}C{ICF['ge']}+{IC}C{ICF['pe']})*{tar}"),
        "ex": ("Efecto de ingresos exentos", f"{IC}C{ICF['ex']}*{tar}"),
        "ded": ("Efecto de deducciones adicionales", f"{IC}C{ICF['ded']}*{tar}"),
        "perd": ("Efecto de la amortización de pérdidas", f"{IC}C{ICF['perd']}*{tar}"),
        "otros": ("Efecto de otras partidas de conciliación", f"{IC}C{ICF['otros']}*{tar}"),
        "neg": ("Efecto de base imponible negativa (sin impuesto causado)", f"{IC}C{ICF['ir']}-SUM({E_('teo')}:{E_('otros')})"),
        "corr": ("Impuesto corriente recalculado", f"SUM({E_('teo')}:{E_('neg')})"),
        "dif": ("Gasto (ingreso) por impuesto diferido requerido", f"{MOV}E{fila_tot9}"),
        "req": ("Gasto total por impuesto requerido", f"{E_('corr')}+{E_('dif')}"),
        "reg": ("Gasto total por impuesto registrado",
                f'{IC}B{ICF["irReg"]}+IF({_pb("gastoDiferidoRegistrado")}="",{AJ}B{AJF["gastoDifSaldos"]},{_pb("gastoDiferidoRegistrado")})'),
        "noexp": ("Gasto registrado no explicado", f'{E_("reg")}-{E_("req")}'),
    }
    c11 = []
    for k in _ETR[:13]:
        txt, f = etr_f[k]
        c11.append([txt, fx(f, etr[k] if etr[k] is not None else ""), None if k == "rai" else pct(k)])
    rai = f"$B${ETRF['rai']}"
    c11.append(["Tasa efectiva requerida", None, fx(f'IF({rai}=0,"",{E_("req")}/{rai})', etr["tReq"] if etr["tReq"] is not None else "")])
    c11.append(["Tasa efectiva registrada", None, fx(f'IF({rai}=0,"",{E_("reg")}/{rai})', etr["tReg"] if etr["tReg"] is not None else "")])
    c11.append(["Tasa aplicable", None, fx(tar, etr["tApl"])])

    # 12 · Ajustes.
    A = lambda k: f"B{AJF[k]}"
    gdr = num["gastoDiferidoRegistrado"]
    aj_f = {
        "irAud": ("Impuesto corriente recalculado", f"{IC}C{ICF['ir']}", t["impuestoCorrienteAuditado"], "04_Impuesto_corriente"),
        "irReg": ("Impuesto corriente registrado", f"{IC}B{ICF['irReg']}", t["impuestoCorrienteRegistrado"], "04 (vacío: el de la conciliación)"),
        "ajCorr": ("Ajuste al impuesto corriente (+ más gasto y pasivo)", f"{A('irAud')}-{A('irReg')}", t["ajusteCorriente"], cit["corr"]),
        "pagarAud": ("Impuesto por pagar recalculado (− saldo a favor)", f"{IC}C{ICF['pagar']}", t["impuestoPorPagarAuditado"], "04_Impuesto_corriente"),
        "saldoReg": ("Impuesto por pagar registrado", f"{IC}B{ICF['saldoReg']}", t["saldoCorrienteRegistrado"], "04 (vacío: el de la conciliación)"),
        "ajSaldo": ("Ajuste al saldo de impuesto corriente", f"{A('pagarAud')}-{A('saldoReg')}", t["ajusteSaldoCorriente"], ""),
        "excesoPerd": ("Amortización de pérdidas en exceso", f"MAX({IC}C{ICF['perd']}-{sg('perdidas')},0)", t["excesoAmortizacionPerdidas"], "LRTI art. 11"),
        "vencidas": ("Pérdidas vencidas sin amortizar", _sum(PER, "H", nl), t["perdidasVencidas"], "05_Perdidas"),
        "dtaRec": ("Activo por impuesto diferido requerido", f"{_sum(DT, 'M', npt)}+{_sum(PER, 'L', nl)}", t["dtaReconocido"], cit["dta"]),
        "dtl": ("Pasivo por impuesto diferido requerido", _sum(DT, "I", npt), t["dtlRequerido"], "NIC 12.15"),
        "dtaNoRec": ("Activo diferido no reconocido (revelar)", f"{_sum(DT, 'N', npt)}+{_sum(PER, 'M', nl)}", t["dtaNoReconocido"], "NIC 12.81 e)"),
        "difReq": ("Impuesto diferido neto requerido (+ activo)", f"{_sum(DT, 'O', npt)}+{_sum(PER, 'L', nl)}", t["diferidoNetoRequerido"], ""),
        "difReg": ("Impuesto diferido neto registrado (+ activo)", f"{_sum(DT, 'Q', npt)}+{_pb('dtaPerdidasRegistrado')}", t["diferidoNetoRegistrado"], "06 + parámetros"),
        "ajDif": ("Ajuste al impuesto diferido neto", f"{A('difReq')}-{A('difReg')}", t["ajusteDiferido"], cit["dt"]),
        "ajDifRes": ("Ajuste al diferido: parte contra resultados", f"{MOV}H{FILA0}+{MOV}H{FILA0 + 2}", t["ajusteDiferidoResultados"], "09_Movimiento"),
        "ajDifOri": ("Ajuste al diferido: parte contra ORI", f"{MOV}H{FILA0 + 1}", t["ajusteDiferidoORI"], cit["ori"]),
        "gastoDifReq": ("Gasto (ingreso) diferido requerido en resultados", f"{MOV}E{fila_tot9}", t["gastoDiferidoRequerido"], "09_Movimiento"),
        "gastoDifSaldos": ("Gasto diferido según la variación de los saldos registrados sin ORI",
                           f"-({MOV}G{FILA0}-{MOV}B{FILA0})-({MOV}G{FILA0 + 2}-{MOV}B{FILA0 + 2})", d["gastoDifSaldos"], "09_Movimiento"),
        "gastoDifReg": ("Gasto (ingreso) diferido registrado en resultados",
                        f'IF({_pb("gastoDiferidoRegistrado")}="","",{_pb("gastoDiferidoRegistrado")})', gdr if gdr is not None else "", "Parámetros"),
        "reclas": ("Gasto diferido en resultados que corresponde a ORI u otro origen",
                   f'IF({_pb("gastoDiferidoRegistrado")}="",0,{_pb("gastoDiferidoRegistrado")}-{A("gastoDifSaldos")})', t["reclasificacionORI"], cit["ori"]),
        "gastoReq": ("Gasto total por impuesto requerido", f"{ETR}B{ETRF['req']}", t["gastoTotalRequerido"], "11_Tasa_efectiva"),
        "gastoReg": ("Gasto total por impuesto registrado", f"{ETR}B{ETRF['reg']}", etr["reg"], "11_Tasa_efectiva"),
        "noexp": ("Gasto registrado no explicado", f"{ETR}B{ETRF['noexp']}", etr["noexp"], "11_Tasa_efectiva"),
        "ajRes": ("Ajuste neto al gasto por impuesto en resultados (+ más gasto)", f"{A('ajCorr')}-{A('ajDifRes')}-{A('reclas')}",
                  t["ajusteResultados"], "Corriente − diferido a resultados − reclasificación"),
    }
    c12 = [[aj_f[k][0], fx(aj_f[k][1], aj_f[k][2]), aj_f[k][3]] for k in _AJ]

    # 13 · Participación atribuible a ingresos exentos (Reglamento LRTI art. 46 num. 5: base bruta).
    pb_, pn_, pc_, pr_ = (f"B{PEF[k]}" for k in ("bruto", "neto", "calc", "reg"))
    vac = lambda x: "" if x is None else x
    c13 = [
        ["Ingreso exento bruto informado por el cliente", fx(f'IF({_pb("ingresoExentoBruto")}<>"",{_pb("ingresoExentoBruto")},"")', vac(pex["bruto"])),
         "Parámetros — base del «15% de tales ingresos» (Reglamento LRTI art. 46 num. 5); vacío: no informado"],
        ["Ingresos exentos restados en la conciliación (renglón del cliente)", fx(f"-{IC}C{ICF['ex']}", pex["neto"]),
         "04_Impuesto_corriente — puede venir neto de los gastos atribuibles"],
        ["Gastos atribuibles a ingresos exentos sumados en la conciliación", fx(f"{IC}C{ICF['ge']}", pex["gastos"]),
         "Reglamento LRTI art. 46 num. 4 y art. 47 (prorrateo): se suman aparte, no minoran la base del num. 5"],
        [f"Participación atribuible recalculada = {n2(num['participacion'])} % del ingreso exento bruto",
         fx(f'IF(OR({pn_}<=0.005,{IC}C{ICF["u"]}<=0),0,IF({pb_}="","",{pb_}*{_pb("participacion")}/100))', vac(pex["calc"])),
         "Reglamento LRTI art. 46 num. 5: «el 15% de tales ingresos» — vacío si falta el ingreso exento bruto"],
        ["Participación atribuible registrada por el cliente en la conciliación", fx(f"{IC}B{ICF['pe']}", pex["registrado"]), "03_Conciliacion"],
        ["Participación atribuible informada por el cliente en su papel de trabajo",
         fx(f'IF({_pb("participacionExentosInformada")}<>"",{_pb("participacionExentosInformada")},"")', vac(pex["informado"])), "Parámetros"],
        ["Diferencia (recalculada − registrada)", fx(f'IF({pc_}="","",{pc_}-{pr_})', vac(pex["dif"])), "Ajuste al renglón de la conciliación"],
        ["Estado del cálculo normativo",
         fx(f'IF({pn_}<=0.005,"Sin ingresos exentos",IF({pc_}="","Bloqueado por falta de soporte","Calculado"))', pex["estado"]),
         "Bloqueado: la herramienta no reconstruye la base bruta sin soporte del cliente"],
    ]

    # 14 · Asientos.
    asientos = []

    def asiento(titulo, lineas):
        for i, (cta, formula, valor, debe) in enumerate(lineas):
            v = fx(formula, valor)
            asientos.append([titulo if i == 0 else "", cta, v if debe else None, None if debe else v])

    ajb = lambda k: f"ABS({AJ}B{AJF[k]})"
    if abs(t["ajusteCorriente"]) > 0.005:
        pos = t["ajusteCorriente"] > 0
        asiento("1 · Impuesto corriente", [("Gasto por impuesto a la renta corriente", ajb("ajCorr"), abs(t["ajusteCorriente"]), pos),
                                           ("Impuesto a la renta por pagar", ajb("ajCorr"), abs(t["ajusteCorriente"]), not pos)])
    if abs(t["ajusteDiferidoResultados"]) > 0.005:
        pos = t["ajusteDiferidoResultados"] > 0
        asiento("2 · Impuesto diferido contra resultados", [
            ("Activo / pasivo por impuesto diferido", ajb("ajDifRes"), abs(t["ajusteDiferidoResultados"]), pos),
            ("Ingreso (gasto) por impuesto a la renta diferido", ajb("ajDifRes"), abs(t["ajusteDiferidoResultados"]), not pos)])
    if abs(t["ajusteDiferidoORI"]) > 0.005:
        pos = t["ajusteDiferidoORI"] > 0
        asiento("3 · Impuesto diferido contra ORI", [("Activo / pasivo por impuesto diferido", ajb("ajDifOri"), abs(t["ajusteDiferidoORI"]), pos),
                                                     ("Otro resultado integral (impuesto diferido)", ajb("ajDifOri"), abs(t["ajusteDiferidoORI"]), not pos)])
    if abs(t["reclasificacionORI"]) > 0.005:
        pos = t["reclasificacionORI"] > 0
        asiento("4 · Reclasificación del diferido llevado a resultados", [
            ("Otro resultado integral (impuesto diferido)", ajb("reclas"), abs(t["reclasificacionORI"]), pos),
            ("Gasto por impuesto a la renta diferido", ajb("reclas"), abs(t["reclasificacionORI"]), not pos)])

    ref_res = {"baseImponibleCliente": f"{IC}B{ICF['base']}", "baseImponibleAuditada": f"{IC}C{ICF['base']}",
               "impuestoCorrienteAuditado": f"{AJ}B{AJF['irAud']}", "impuestoCorrienteRegistrado": f"{AJ}B{AJF['irReg']}",
               "ajusteCorriente": f"{AJ}B{AJF['ajCorr']}", "impuestoPorPagarAuditado": f"{AJ}B{AJF['pagarAud']}",
               "saldoCorrienteRegistrado": f"{AJ}B{AJF['saldoReg']}", "ajusteSaldoCorriente": f"{AJ}B{AJF['ajSaldo']}",
               "excesoAmortizacionPerdidas": f"{AJ}B{AJF['excesoPerd']}", "perdidasVencidas": f"{AJ}B{AJF['vencidas']}",
               "dtaReconocido": f"{AJ}B{AJF['dtaRec']}", "dtlRequerido": f"{AJ}B{AJF['dtl']}", "dtaNoReconocido": f"{AJ}B{AJF['dtaNoRec']}",
               "diferidoNetoRequerido": f"{AJ}B{AJF['difReq']}", "diferidoNetoRegistrado": f"{AJ}B{AJF['difReg']}",
               "ajusteDiferido": f"{AJ}B{AJF['ajDif']}", "ajusteDiferidoResultados": f"{AJ}B{AJF['ajDifRes']}",
               "ajusteDiferidoORI": f"{AJ}B{AJF['ajDifOri']}", "gastoDiferidoRequerido": f"{AJ}B{AJF['gastoDifReq']}",
               "gastoDiferidoRegistrado": f"{AJ}B{AJF['gastoDifReg']}", "reclasificacionORI": f"{AJ}B{AJF['reclas']}",
               "gastoTotalRequerido": f"{AJ}B{AJF['gastoReq']}", "gastoTotalRegistrado": f"{AJ}B{AJF['gastoReg']}",
               "diferenciaNoExplicada": f"{AJ}B{AJF['noexp']}", "tasaEfectivaRequerida": f"{ETR}C{ETRF['tReq']}*100",
               "tasaEfectivaRegistrada": f"{ETR}C{ETRF['tReg']}*100", "ajusteResultados": f"{AJ}B{AJF['ajRes']}"}
    val_res = {k: t[k] for k in res["labels"]}
    for k, v in (("tasaEfectivaRequerida", etr["tReq"]), ("tasaEfectivaRegistrada", etr["tReg"])):
        if k in val_res:
            val_res[k] = v * 100
    resumen = [[res["labels"][k], fx(ref_res[k], val_res[k])] for k in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Conciliacion", "Conciliación tributaria",
             [["Renglón", "t"], ["Concepto", "t"], ["Tipo", "t"], ["Signo exigido", "t"], ["Importe según cliente", "n"],
              ["Importe según auditor", "n"], ["Importe auditado", "n"], ["Diferencia", "n"]], c03, tot_c, explica=EXPLICA["03_Conciliacion"]),
        hoja("04_Impuesto_corriente", "Impuesto corriente",
             [["Concepto", "t"], ["Según cliente", "n"], ["Auditado", "n"], ["Diferencia", "n"], ["Referencia", "t"]], c04, explica=EXPLICA["04_Impuesto_corriente"]),
        hoja("05_Perdidas", "Pérdidas tributarias",
             [["Año de origen", "a"], ["Pérdida", "n"], ["Amortizado años anteriores", "n"], ["Último año", "a"], ["Disponible", "n"],
              ["Vencida", "t"], ["Disponible no vencido", "n"], ["Saldo vencido", "n"], ["Amortización del año", "n"], ["Remanente", "n"],
              ["Arrastrable a años futuros", "n"], ["Activo diferido requerido", "n"], ["Activo diferido no reconocido", "n"]], c05, tot_l, explica=EXPLICA["05_Perdidas"]),
        hoja("06_Diferencias_temp", "Diferencias temporarias y diferido",
             [["Partida", "t"], ["Naturaleza", "t"], ["Libros NIIF", "n"], ["Base fiscal", "n"], ["Diferencia temporaria (+ imponible)", "n"],
              ["Clase", "t"], ["Año de reversión", "a"], ["Tasa (%)", "x"], ["Pasivo diferido", "n"], ["Activo diferido bruto", "n"],
              ["Permitido", "t"], ["Probable", "t"], ["Activo diferido reconocido", "n"], ["Activo diferido no reconocido", "n"],
              ["Diferido requerido (+ activo)", "n"], ["Registrado al inicio", "n"], ["Registrado al cierre", "n"], ["Ajuste", "n"],
              ["ORI", "t"], ["Movimiento requerido", "n"], ["A resultados (+ gasto)", "n"], ["A ORI (+ cargo)", "n"]], c06, tot6, explica=EXPLICA["06_Diferencias_temp"]),
        hoja("07_Tasa_reversion", "Tasa de reversión",
             [["Partida", "t"], ["Año de reversión", "x"], ["Tasa usada por el cliente (%)", "x"],
              ["Tasa esperada = aprobada + recargo (%)", "x"],
              ["Diferencia de tasa (p.p.)", "x"], ["Diferencia temporaria", "n"], ["Efecto en el diferido", "n"],
              ["Fórmula de la tasa esperada", "t"]], c07, tot7, explica=EXPLICA["07_Tasa_reversion"]),
        hoja("08_Recuperabilidad", "Recuperabilidad del activo diferido",
             [["Partida", "t"], ["Activo diferido bruto", "n"], ["Permitido", "t"], ["Probable", "t"], ["Reconocible", "n"],
              ["Registrado al cierre", "n"], ["Registrado en exceso", "n"], ["Conclusión", "t"]], c08, tot8, explica=EXPLICA["08_Recuperabilidad"]),
        hoja("09_Movimiento", "Movimiento: resultados y ORI",
             [["Concepto", "t"], ["Registrado al inicio", "n"], ["Requerido al cierre", "n"], ["Movimiento", "n"], ["A resultados (+ gasto)", "n"],
              ["A ORI (+ cargo)", "n"], ["Registrado al cierre", "n"], ["Ajuste", "n"]], c09, tot9, explica=EXPLICA["09_Movimiento"]),
        hoja("10_Compensacion", "Compensación y presentación", [["Concepto", "t"], ["Importe", "x"], ["Referencia", "t"]], c10, explica=EXPLICA["10_Compensacion"]),
        hoja("11_Tasa_efectiva", "Tasa efectiva (NIC 12.81 c)", [["Concepto", "t"], ["Importe", "n"], ["% del resultado", "p"]], c11, explica=EXPLICA["11_Tasa_efectiva"]),
        hoja("12_Ajustes", "Ajustes propuestos", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], c12, explica=EXPLICA["12_Ajustes"]),
        hoja("13_Partic_exentos", "Participación atribuible a exentos",
             [["Concepto", "t"], ["Importe / estado", "x"], ["Sustento", "t"]], c13, explica=EXPLICA["13_Partic_exentos"]),
        hoja("14_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos, explica=EXPLICA["14_Asientos"]),
        hoja("15_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -----------------------------------------------------------------

def definicion() -> dict:
    conc = ("Una fila por renglón de la conciliación tributaria del formulario 101: renglón o casillero, concepto, tipo (utilidad, "
            "participación, exentos, no deducibles, gastos exentos, participación exentos, deducciones, pérdidas, otros) e importe con el "
            "signo con que suma a la base imponible (+ suma, − resta); la suma de la columna es la base imponible declarada. El auditor puede "
            "completar «importe según auditor» (por ejemplo, gastos no deducibles omitidos, con importe del cliente 0). Si el renglón de "
            "ingresos exentos viene neto de los gastos atribuibles, informe además el ingreso exento bruto en los parámetros: sin él no se "
            "recalcula la participación atribuible del Reglamento LRTI art. 46 num. 5.")
    part = ("Una fila por partida con diferencia entre libros NIIF y base fiscal: partida, activo o pasivo, importe en libros, base fiscal, "
            "si la ley admite la deducción futura (Reglamento LRTI, art. innumerado a continuación del art. 28 (num. 5: provisiones distintas de cuentas incobrables y desmantelamiento, utilizables cuando se paguen —jubilación y desahucio solo por la parte no deducible, interpretación: LRTI art. 10 num. 13—; num. 8: pérdidas tributarias)), si es probable la ganancia fiscal futura; y, si existen, año "
            "esperado de reversión, tasa usada, impuesto diferido registrado al inicio y al cierre (+ activo / − pasivo) y si la partida se "
            "reconoce en ORI.")
    perd = "Pérdidas tributarias por año de origen: año, pérdida declarada, amortizado acumulado en años anteriores y, si difiere del plazo legal, último año para amortizar."
    return {
        "name": "Impuesto corriente y diferido",
        "area": "Impuestos",
        "processor": "impuesto_corriente_diferido",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Recalcula la conciliación tributaria del formulario 101 (participación trabajadores, exentos, no deducibles, deducciones y "
                    "amortización de pérdidas con su límite y vencimiento), el impuesto corriente y el saldo por pagar; mide las diferencias "
                    "temporarias por partida a la tasa aprobada de reversión, el activo diferido reconocible (permitido por la ley y con "
                    "probabilidad de ganancia fiscal) y el pasivo diferido; separa el movimiento a resultados y a ORI, prueba la compensación y "
                    "concilia el gasto con el resultado × tasa (NIC 12.81 c). Tasas y límites de Ecuador como parámetros («vigente al corte»; la "
                    "LRTI de la biblioteca es el texto oficial hasta el 2-jul-2021: contrastar reformas posteriores en el Registro Oficial). La tasa esperada del diferido y del activo por pérdidas incluye el recargo del art. 37 que grava a la entidad (NIC 12.47, 49). El cálculo es el mismo en NIIF completas y en PYMES; cambian las citas."),
        "source": {"organization": "IFRS Foundation (texto en español: Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIC 12 párr. 5 (definiciones), 12–14 (impuesto corriente como pasivo o activo; pérdida retrotraída), 15 "
                                "(pasivo diferido por diferencias imponibles), 24–25 (activo diferido por diferencias deducibles si es probable "
                                "la ganancia fiscal), 34–36 (pérdidas y créditos no utilizados; pérdidas recientes como indicio en contra), 46–47 "
                                "(tasas en vigor o aprobadas al cierre; tasa del ejercicio de reversión), 49 (tipos medios si hay tipos distintos por tramos), 53 (sin descuento), 56 (revisión del "
                                "activo diferido), 58–60 y 61A (resultados frente a ORI y patrimonio), 71 y 74 (compensación), 81 c) y e) "
                                "(conciliación del gasto con el resultado × tasa; diferencias no reconocidas) — leídos en EUR-Lex. Párr. 37 "
                                "(reconsideración de activos no reconocidos). CINIIF 23 (incertidumbres) fuera del alcance de este cálculo."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015 y 2025, Sección 29: 29.4–29.6 (corriente), 29.9–29.13 (bases fiscales), 29.14 y "
                                      "29.16 (reconocimiento de pasivo y activo diferido), 29.21–29.22 (pérdidas), 29.27–29.28 (tasas aprobadas), "
                                      "29.31 (revisión), 29.32 (sin descuento), 29.35 (ORI/patrimonio), 29.37 [2025: 29.37A] (compensación), "
                                      "29.40 c) (explicación gasto vs resultado × tasa). Numeración igual en ambas ediciones; 2025 añade 29.3A, "
                                      "29.16A, 29.19A, 29.34A–D (CINIIF 23) y 29.37A. El cálculo de esta herramienta es el mismo en ambas ediciones."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad de la conciliación tributaria frente al F-101 y al mayor."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13 y 24", "requirement": "La probabilidad de ganancias fiscales futuras y la tasa de reversión son supuestos de una estimación."},
            {"document": "NIA 250 (Revisada)", "section": "párr. 14", "requirement": "Cumplimiento de disposiciones legales tributarias (LRTI y Reglamento)."},
            {"document": "NIA 330", "section": "párr. 18", "requirement": "Procedimientos sustantivos sobre saldos y transacciones materiales."},
            {"document": "NIA 450", "section": "párr. 5 y 8", "requirement": "Acumular las incorrecciones (ajustes propuestos) y comunicarlas."},
        ],
        "calculo": [
            "Base imponible del cliente = suma algebraica de la conciliación (total de control).",
            "Participación trabajadores recalculada = % × utilidad contable (si es positiva; «utilidades líquidas», CT art. 97).",
            "Participación atribuible a ingresos exentos = % del ingreso exento BRUTO informado por el cliente (Reglamento LRTI art. 46 num. 5: «el 15% de tales ingresos»; los gastos atribuibles se suman aparte por el num. 4 y no minoran esa base). Si el cliente solo entrega el importe neto, la herramienta no reconstruye la base bruta: el recálculo queda vacío, ese tramo del cálculo normativo se bloquea, el renglón conserva el importe del cliente y se pide el ingreso exento bruto y la participación atribuible (cédula 13_Partic_exentos).",
            "Utilidad gravable antes de pérdidas = utilidad − participación − exentos + no deducibles + gastos atribuibles + participación atribuible − deducciones ± otros.",
            "Amortización de pérdidas permitida = mín(solicitada, límite % × utilidad gravable, saldo no vencido); se aplica de la pérdida más antigua a la más reciente.",
            "Impuesto causado = máx(base, 0) × tarifa aplicable; tarifa aplicable = tarifa general + puntos de recargo × proporción de composición societaria en paraísos fiscales o no informada, y el 100 % de la base cuando esa proporción llega o supera el 50 % (LRTI art. 37; Reglamento art. 51). Por pagar = causado − retenciones − anticipos − crédito (negativo: saldo a favor, NIC 12.12).",
            "Diferencia temporaria: activo = libros − base; pasivo = base − libros; positiva imponible, negativa deducible.",
            "Tasa de reversión = tasa que se espera aplicar (NIC 12.47, 49) = tarifa aprobada para el año de reversión (la futura si el año ≥ año de vigencia; si no, la general) + el recargo del art. 37 que grava a la entidad; la misma tasa mide el activo diferido por pérdidas; sin descuento (NIC 12.53).",
            "Pasivo diferido = diferencia imponible × tasa; activo diferido = diferencia deducible × tasa, solo si la ley lo admite y es probable la ganancia fiscal; el resto se revela.",
            "Activo diferido por pérdidas = remanente no vencido tras la amortización del año × tasa, si se admite y es probable.",
            "Movimiento = requerido al cierre − registrado al inicio; a resultados salvo las partidas de ORI.",
            "Compensación: con derecho legal y misma autoridad se presenta el neto; sin él, bruto.",
            "Tasa efectiva = gasto total por impuesto ÷ resultado antes del impuesto; conciliación resultado × tasa → gasto por efectos de cada partida.",
            "Ajuste neto al gasto = ajuste corriente − ajuste diferido contra resultados − diferido llevado a resultados que corresponde a ORI.",
        ],
        "fields": _CONCILIACION, "rules": [], "control": CONTROL, "primary": "ajusteResultados",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "TAX-01", "objective": "Conciliación tributaria", "risk": "Base imponible subestimada; no deducibles omitidos", "assertion": "Exactitud / Integridad",
             "procedure": "Cotejar la conciliación con el F-101 y el mayor; recalcular participación y revisar gastos no deducibles", "evidence": "F-101, mayor, soporte de gastos",
             "criterion": "Base imponible recalculada igual a la declarada o diferencia ajustada", "source": "LRTI arts. 9, 10 · NIA 500"},
            {"code": "TAX-02", "objective": "Impuesto corriente", "risk": "Impuesto corriente mal calculado o mal presentado", "assertion": "Valoración",
             "procedure": "Recalcular el impuesto causado con la tarifa vigente y el saldo por pagar neto de retenciones, anticipos y crédito", "evidence": "F-101, comprobantes de retención",
             "criterion": "Diferencia cero", "source": "NIC 12.12, 46 · PYMES 29"},
            {"code": "TAX-03", "objective": "Pérdidas tributarias", "risk": "Amortización sobre el límite o de pérdidas vencidas", "assertion": "Exactitud",
             "procedure": "Recalcular el límite anual, el plazo y el saldo por año de origen", "evidence": "Declaraciones de años anteriores",
             "criterion": "Amortización dentro del límite y del plazo", "source": "LRTI art. 11 · NIC 12.34"},
            {"code": "TAX-04", "objective": "Bases fiscales y diferencias temporarias", "risk": "Diferido mal medido u omitido", "assertion": "Valoración / Integridad",
             "procedure": "Comparar libros NIIF con la base fiscal por partida y medir activo y pasivo diferidos", "evidence": "Auxiliares NIIF y fiscales",
             "criterion": "Diferido requerido igual al registrado", "source": "NIC 12.5, 15, 24 · PYMES 29"},
            {"code": "TAX-05", "objective": "Recuperabilidad del activo diferido", "risk": "Activo diferido sin ganancia fiscal probable o no admitido", "assertion": "Valoración",
             "procedure": "Evaluar proyecciones fiscales y el Reglamento LRTI, art. innumerado a continuación del art. 28 (num. 5: provisiones distintas de cuentas incobrables y desmantelamiento, utilizables cuando se paguen —jubilación y desahucio solo por la parte no deducible, interpretación: LRTI art. 10 num. 13—; num. 8: pérdidas tributarias); revisar el importe en libros al cierre", "evidence": "Proyecciones, historial de resultados fiscales",
             "criterion": "Activo diferido solo por lo probable y admitido", "source": "NIC 12.24, 34–36, 56 · Reglamento LRTI, art. innumerado a continuación del art. 28 (num. 5: provisiones distintas de cuentas incobrables y desmantelamiento, utilizables cuando se paguen —jubilación y desahucio solo por la parte no deducible, interpretación: LRTI art. 10 num. 13—; num. 8: pérdidas tributarias)"},
            {"code": "TAX-06", "objective": "Tasa de reversión", "risk": "Diferido medido a tasa no aprobada o distinta a la del año de reversión", "assertion": "Valoración",
             "procedure": "Comparar la tasa usada con la aprobada al cierre para el año de reversión", "evidence": "Ley vigente y reformas publicadas",
             "criterion": "Tasa esperada del año de reversión (aprobada + recargo del art. 37), sin descuento", "source": "NIC 12.47, 49, 53 · LRTI art. 37"},
            {"code": "TAX-07", "objective": "Resultados frente a ORI y compensación", "risk": "Diferido de ORI en resultados; compensación indebida", "assertion": "Presentación",
             "procedure": "Separar el movimiento por origen y probar la compensación de saldos", "evidence": "Estados financieros",
             "criterion": "Presentación conforme", "source": "NIC 12.58, 61A, 71, 74"},
            {"code": "TAX-08", "objective": "Tasa efectiva", "risk": "Gasto por impuesto no explicado", "assertion": "Exactitud / Presentación",
             "procedure": "Conciliar el gasto con el resultado contable × tasa aplicable", "evidence": "Estado de resultados, nota de impuestos",
             "criterion": "Diferencia dentro del umbral", "source": "NIC 12.81 c)"},
        ],
        "requests": [
            req("RQ-001", "Conciliación tributaria del ejercicio (renglones del F-101)", "conciliacion", "TAX-01", "Base imponible e impuesto corriente", content=conc),
            req("RQ-002", "Anexo de diferencias temporarias por partida (libros NIIF, base fiscal, diferido registrado)", "partidas", "TAX-04",
                "Impuesto diferido", content=part),
            req("RQ-003", "Pérdidas tributarias por año de origen", "perdidas", "TAX-03", "Límite, plazo y activo diferido por pérdidas",
                required=False, content=perd),
            req("RQ-004", "Formulario 101 presentado y declaraciones de años con pérdidas", None, "TAX-01", "Sustento de la conciliación",
                formats=("pdf",), use="soporte"),
            req("RQ-005", "Comprobantes de retención, anticipos y crédito tributario", None, "TAX-02", "Sustento del impuesto por pagar",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-006", "Proyecciones de ganancias fiscales y análisis de recuperabilidad", None, "TAX-05", "Probabilidad de ganancia fiscal",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-007", "Mayor de cuentas de impuesto corriente, diferido y gasto por impuesto", None, "TAX-02", "Datos registrados",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-008", "Detalle del ingreso exento bruto del ejercicio (antes de restar los gastos atribuibles) y cálculo de la participación "
                "de trabajadores atribuible a esos ingresos", None, "TAX-01",
                "Base bruta del Reglamento LRTI art. 46 num. 5: sin ella ese renglón no se recalcula", required=False,
                formats=("xlsx", "pdf"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) -------------------------------------------------------

def _c(id, concepto, tipo, importe, auditor=None):
    f = {"id": id, "concepto": concepto, "tipo": tipo, "importe": importe, "_row": 2}
    if auditor is not None:
        f["importe_auditor"] = auditor
    return f


def _pt(id, nat, libros, base, perm, prob, inicial, cierre, ori="No", anio=None, tasa=None):
    f = {"id": id, "naturaleza": nat, "libros": libros, "base_fiscal": base, "permitido": perm, "probable": prob,
         "inicial": inicial, "cierre": cierre, "ori": ori, "_row": 2}
    if anio is not None:
        f["anio_reversion"] = anio
    if tasa is not None:
        f["tasa"] = tasa
    return f


def _pl(anio, importe, amortizado, vence=None):
    f = {"id": anio, "importe": importe, "amortizado": amortizado, "_row": 2}
    if vence is not None:
        f["vence"] = vence
    return f


# Corte 2025-12-31; IR 25 %, participación 15 %, límite de pérdidas 25 %, plazo 5 años.
# Participación atribuible a exentos: el cliente declaró 8.550 (15 % de 60.000 − 3.000, base neta) y el ingreso exento
# bruto informado es 60.000 → recalculada 15 % × 60.000 = 9.000 (Reglamento LRTI art. 46 num. 5) → diferencia +450.
# Auditado: 1.000.000 − 150.000 − 60.000 + (45.000 + 20.000 omitidos) + 3.000 + 9.000 − 12.000 + 30.000 = 885.000;
# límite 25 % = 221.250 (< solicitadas 240.000 y < disponibles 250.000) → base 663.750; IR 165.937,50
# frente a 156.137,50 registrado (base del cliente 624.550 × 25 %) → ajuste corriente 9.800,00.
# Pérdidas FIFO: 2020 30.000 + 2021 100.000 + 2023 91.250 → remanente 28.750 × 25 % = 7.187,50 de activo diferido.
# Diferido de partidas: activo 75.000 (incluye 3.750 del deterioro de cartera sobre el límite, que el num. 5, 2.º inciso,
# del art. innumerado a continuación del art. 28 SÍ admite en entidades no financieras), pasivo 92.500 → neto −17.500
# frente a −13.700 registrado → ajuste −3.800; con pérdidas: requerido −10.312,50 frente a 6.300 → ajuste −16.612,50
# (todo contra resultados). Gasto diferido registrado 19.700 incluye 10.000 de la revaluación en ORI → reclasificación 10.000.
# Ajuste neto al gasto = 9.800,00 + 16.612,50 − 10.000 = 16.412,50 = gasto requerido 192.250 − registrado 175.837,50.
# Tarifa: proporción de recargo 0 → 25 %. En el escenario «recargo_paraisos» la proporción es 60 % ≥ 50 % → 100 % de la
# base con 25 + 3 = 28 %, y esa misma tasa mide el diferido y el activo por pérdidas (NIC 12.47, 49).
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tasaIR": 25, "puntosRecargo": 3, "proporcionRecargo": 0, "participacion": 15,
                   "ingresoExentoBruto": 60000, "participacionExentosInformada": 8550,
                   "limitePerdidas": 25, "plazoPerdidas": 5, "perdidasPermitidas": "Sí", "probabilidadPerdidas": "Sí",
                   "retenciones": 70000, "anticipos": 10000, "creditoAnterior": 5000, "impuestoCorrienteRegistrado": 156137.50,
                   "saldoCorrienteRegistrado": 71137.50, "gastoDiferidoRegistrado": 19700, "dtaPerdidasInicial": 45000,
                   "dtaPerdidasRegistrado": 20000, "derechoCompensar": "Sí", "dtaPresentado": 76300, "dtlPresentado": 70000,
                   "umbralTasaEfectiva": 1},
    "datasets": {
        "conciliacion": [
            _c("801", "Utilidad del ejercicio", "utilidad", "1000000"),
            _c("803", "(-) Participación a trabajadores", "participacion", "-150000"),
            _c("804", "(-) Dividendos exentos", "exentos", "-60000"),
            _c("806", "(+) Gastos no deducibles locales (multas, intereses)", "no_deducibles", "45000"),
            _c("807", "(+) Gastos incurridos para generar ingresos exentos", "gastos_exentos", "3000"),
            _c("808", "(+) Participación atribuible a ingresos exentos", "participacion_exentos", "8550"),
            _c("811", "(-) Deducción por incremento neto de empleos", "deducciones", "-12000"),
            _c("814", "(-) Amortización de pérdidas tributarias", "perdidas", "-240000"),
            _c("816", "(+) Generación de diferencias temporarias (jubilación, garantías)", "otros", "30000"),
            _c("AUD-1", "Gastos sin comprobante de venta válido (hallazgo)", "no_deducibles", "0", "20000"),
        ],
        "partidas": [
            _pt("PPE — depreciación fiscal acelerada", "Activo", "500000", "420000", "Sí", "Sí", "-15000", "-20000", anio=2028),
            _pt("Provisión jubilación patronal", "Pasivo", "120000", "0", "Sí", "Sí", "25000", "30000", anio=2030),
            _pt("Provisión por garantías", "Pasivo", "40000", "0", "Sí", "Sí", "6000", "8800", anio=2026, tasa="22"),
            _pt("Deterioro de inventarios (VNR)", "Activo", "200000", "230000", "Sí", "Sí", "5000", "7500", anio=2026),
            _pt("Deterioro de cartera sobre el límite fiscal", "Activo", "300000", "315000", "Sí", "Sí", "0", "3750"),
            _pt("Revaluación de terrenos", "Activo", "900000", "700000", "Sí", "Sí", "-40000", "-50000", ori="Sí"),
            _pt("Activo por derecho de uso", "Activo", "90000", "0", "Sí", "Sí", "0", "0", anio=2027),
            _pt("Pasivo por arrendamiento", "Pasivo", "95000", "0", "Sí", "Sí", "0", "0", anio=2027),
            _pt("Provisión por litigio laboral", "Pasivo", "25000", "0", "Sí", "No", "0", "6250"),
        ],
        "perdidas": [
            _pl("2021", "150000", "50000"),
            _pl("2019", "100000", "60000"),
            _pl("2023", "120000", "0"),
            _pl("2020", "60000", "30000"),
        ],
    },
}

_MOD_PERDIDA = {"801": "-300000", "803": "0", "808": "0"}   # pérdida contable: sin participación
_CONC_PERDIDA = [dict(f, importe=_MOD_PERDIDA[f["id"]]) if f["id"] in _MOD_PERDIDA else f for f in EJEMPLO["datasets"]["conciliacion"]]
# Sin ingresos exentos: se quitan los renglones de exentos, gastos atribuibles y participación atribuible.
_CONC_SIN_EXENTOS = [f for f in EJEMPLO["datasets"]["conciliacion"] if f["tipo"] not in ("exentos", "gastos_exentos", "participacion_exentos")]
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    # El cliente solo entrega el importe neto: no se reconstruye la base bruta y el tramo queda bloqueado.
    ("exentos_solo_neto", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "ingresoExentoBruto": None}, EJEMPLO["corte"]),
    ("sin_ingresos_exentos", {**EJEMPLO["datasets"], "conciliacion": _CONC_SIN_EXENTOS},
     {**EJEMPLO["parametros"], "ingresoExentoBruto": None, "participacionExentosInformada": None}, EJEMPLO["corte"]),
    ("recargo_paraisos", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "proporcionRecargo": 60}, EJEMPLO["corte"]),
    ("pymes_2015_tasa_futura", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015", "tasaFutura": 22,
                                                      "anioTasaFutura": 2027, "derechoCompensar": "No", "probabilidadPerdidas": "No",
                                                      "impuestoCorrienteRegistrado": None, "gastoDiferidoRegistrado": None}, EJEMPLO["corte"]),
    ("pymes_2025_perdida_sin_anexos", {"conciliacion": _CONC_PERDIDA},
     {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025", "participacionExentosInformada": None,
      "dtaPresentado": None, "dtlPresentado": None}, EJEMPLO["corte"]),
]
