"""Efectivo y equivalentes de efectivo: conciliación bancaria, partidas conciliatorias,
antigüedad, confirmación bancaria, corte, efectivo restringido y definición de equivalentes.

Versión simple que cumple la norma (especificación del socio CASH-01..18, lo que sirve a las
pruebas de la matriz):

1. Conciliación por cuenta (CASH-02/03): saldo según estado bancario (o arqueo, en caja)
   + depósitos en tránsito − cheques pendientes − notas de crédito no registradas
   + notas de débito no registradas ± otras partidas = saldo que deberían mostrar los libros.
   Diferencia no explicada = saldo según libros − ese saldo.
2. Saldo ajustado de libros = libros + notas de crédito − notas de débito (las notas del banco
   que la entidad no registró son ajuste a libros).
3. Partidas conciliatorias (CASH-04): días al corte, días hasta la liquidación posterior,
   antigua (más de N días) y no depurada (sin liquidación posterior).
4. Corte (CASH-05): partida originada después del corte; depósito en tránsito acreditado por
   el banco más de N días después del corte o nunca.
5. Confirmación (CASH-07/08): saldo confirmado por el banco frente al estado bancario.
6. Efectivo restringido (CASH-11): la restricción no saca el saldo del efectivo (NIC 7.48 y
   decisión CINIIF abr-2022: solo obliga a revelarlo). Se reclasifica a no corriente únicamente
   la parte cuya restricción termina en doce meses o más desde el corte (NIC 1.66 d / PYMES 4.5 d,
   «al menos doce meses»), salvo que ya se presente por separado; sin fecha de fin no se
   reclasifica nada y se pide la fecha.
7. Equivalentes (CASH-10): una inversión cumple el plazo si vence en tres meses o menos desde la
   adquisición —EDATE(adquisición; 3)— (NIC 7.7 / PYMES 7.2). Es una presunción: la definición
   exige además gran liquidez y riesgo poco significativo de cambios de valor (NIC 7.6).
8. Ajuste propuesto = efectivo auditado − saldo según libros (M09).

Norma leída (M03): NIC 7 párr. 6–8, 45, 46, 48, 49 y NIC 1 párr. 66 d) en el Reglamento (UE)
2023/1803 (EUR-Lex, español); NIIF para las PYMES 2015 párr. 4.5 d), 7.2, 7.20, 7.21 y 11.8 a).
PYMES 2025 (texto oficial en inglés): misma numeración — 4.5 d), 7.2, 7.20, 7.21 y 11.8 a).
"""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date, timedelta

from backend.app.aud.niif.procesadores import problemas
from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, a_num, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m as fmt_m, n2, norm, num, problema,
    r2, ref, req, suma, validar_campos, validar_definicion_generica, campo,
)

VERSION = "efectivo_equivalentes 1.0"
RUBRO = "CAJA_BANCOS"

DT, CP, NC, ND, OT = "Depósito en tránsito", "Cheque pendiente", "Nota de crédito", "Nota de débito", "Otra partida"
BANCO, CAJA, INV = "Banco", "Caja", "Inversión"

_CUENTAS = [
    campo("id", "Código de cuenta", alias=("codigo", "cuenta", "codigo contable", "cuenta contable"), ejemplo="1.1.02.01"),
    campo("nombre", "Banco / caja y número de cuenta", alias=("nombre", "banco", "descripcion", "nombre de la cuenta"),
          ejemplo="Banco Pichincha Cte. ***4521"),
    campo("tipo", "Tipo (Banco, Caja o Inversión)", requerido=False, alias=("tipo", "clase", "tipo de cuenta"), ejemplo="Banco"),
    campo("moneda", "Moneda", requerido=False, alias=("moneda", "divisa", "currency"), ejemplo="USD"),
    campo("saldo_libros", "Saldo según libros", "number", alias=("saldo libros", "saldo contable", "saldo segun libros", "libros"),
          ejemplo="125680.50"),
    campo("saldo_banco", "Saldo según estado bancario (o arqueo en caja)", "number", False,
          ("saldo banco", "saldo estado de cuenta", "saldo segun banco", "estado bancario", "arqueo"), "131210.50"),
    campo("saldo_confirmado", "Saldo confirmado por el banco", "number", False,
          ("saldo confirmado", "confirmacion", "confirmado por el banco"), "131210.50"),
    campo("restringido", "Restringido (Sí/No)", requerido=False, alias=("restringido", "restriccion", "restringida"), ejemplo="No"),
    campo("monto_restringido", "Monto restringido", "number", False, ("monto restringido", "valor restringido", "importe restringido")),
    campo("motivo_restriccion", "Motivo de la restricción", requerido=False, alias=("motivo", "motivo restriccion", "tipo de restriccion")),
    campo("fin_restriccion", "Fin de la restricción", "date", False, ("fin restriccion", "fecha fin restriccion", "hasta")),
    campo("presentado_separado", "Restringido ya presentado aparte (Sí/No)", requerido=False,
          alias=("presentado separado", "presentado aparte", "reclasificado")),
    campo("fecha_adquisicion", "Fecha de adquisición (inversiones)", "date", False, ("fecha adquisicion", "fecha de emision", "emision", "apertura")),
    campo("fecha_vencimiento", "Fecha de vencimiento (inversiones)", "date", False, ("fecha vencimiento", "vencimiento", "vence")),
]
_PARTIDAS = [
    campo("id", "N° de partida", alias=("partida", "numero", "n", "id partida"), ejemplo="P-01"),
    campo("cuenta", "Código de cuenta", alias=("cuenta", "codigo", "codigo de cuenta", "cuenta contable"), ejemplo="1.1.02.01"),
    campo("tipo", "Tipo de partida", alias=("tipo", "clase", "tipo de partida", "concepto"), ejemplo=DT),
    campo("referencia", "Referencia / descripción", requerido=False, alias=("referencia", "descripcion", "documento", "cheque")),
    campo("fecha_origen", "Fecha de origen", "date", alias=("fecha origen", "fecha", "fecha libros", "fecha de registro"), ejemplo="2025-12-30"),
    campo("importe", "Importe", "number", alias=("importe", "valor", "monto"), ejemplo="8500.00"),
    campo("fecha_liquidacion", "Fecha de liquidación posterior", "date", False,
          ("fecha liquidacion", "fecha banco", "liquidada", "fecha de cobro", "fecha de acreditacion"), "2026-01-02"),
]
# Libro mayor (auxiliar de bancos): fuente contable del período. No alimenta el
# cálculo del procesador (que corre sobre el anexo de cuentas y las partidas), pero
# se conserva como evidencia y alimenta la Sumaria/Movimiento del papel formulado DA.
_LIBRO_MAYOR = [
    campo("cuenta", "Código de cuenta", alias=("cuenta", "codigo", "codigo de cuenta", "cuenta contable"), ejemplo="1.1.02.01"),
    campo("descripcion", "Descripción de la cuenta", requerido=False,
          alias=("descripcion", "nombre de la cuenta", "banco", "nombre"), ejemplo="Banco Pichincha Cte. ***4521"),
    campo("fecha", "Fecha", "date", requerido=False, alias=("fecha", "fecha del asiento", "fecha comprobante"), ejemplo="2026-08-15"),
    campo("comprobante", "Comprobante", requerido=False, alias=("comprobante", "comp", "n comprobante", "asiento", "documento")),
    campo("detalle", "Detalle del asiento", requerido=False, alias=("detalle", "descripcion del asiento", "concepto", "glosa")),
    campo("tercero", "Tercero / razón social", requerido=False, alias=("tercero", "razon social", "beneficiario", "contraparte")),
    campo("debito", "Débitos", "number", requerido=False, alias=("debito", "debitos", "debe", "cargo"), ejemplo="8500.00"),
    campo("credito", "Créditos", "number", requerido=False, alias=("credito", "creditos", "haber", "abono"), ejemplo="0.00"),
]
# Estado de cuenta bancario (movimientos transcritos del PDF, revisados por el
# auditor). Se cruza con el libro mayor en la reestructuración de la conciliación.
_ESTADO_CUENTA = [
    campo("cuenta", "Código de cuenta", alias=("cuenta", "codigo", "codigo de cuenta", "cuenta contable"), ejemplo="1.1.02.01"),
    campo("fecha", "Fecha", "date", requerido=False, alias=("fecha", "fecha del movimiento", "fecha valor"), ejemplo="2026-08-15"),
    campo("documento", "Documento / referencia", requerido=False, alias=("documento", "referencia", "concepto", "descripcion", "detalle")),
    campo("debito", "Débitos (cargos del banco)", "number", requerido=False, alias=("debito", "debitos", "cargo", "cargos", "retiro"), ejemplo="0.00"),
    campo("credito", "Créditos (abonos del banco)", "number", requerido=False, alias=("credito", "creditos", "abono", "abonos", "deposito"), ejemplo="1000.00"),
]
# Conciliación bancaria del mes anterior (partidas conciliatorias que quedaron
# abiertas). Se arrastran a la reestructuración si no se depuran este mes.
_CONCILIACION_ANTERIOR = [
    campo("cuenta", "Código de cuenta", alias=("cuenta", "codigo", "codigo de cuenta", "cuenta contable"), ejemplo="1.1.02.01"),
    campo("fecha", "Fecha de origen", "date", requerido=False, alias=("fecha", "fecha origen", "fecha de la partida"), ejemplo="2026-07-31"),
    campo("categoria", "Tipo conciliatorio", requerido=False, alias=("categoria", "tipo", "tipo conciliatorio", "clase"), ejemplo="Cheque sin cobrar"),
    campo("documento", "Documento / referencia", requerido=False, alias=("documento", "referencia", "descripcion", "detalle", "concepto")),
    campo("valor", "Valor", "number", requerido=False, alias=("valor", "importe", "monto"), ejemplo="200.00"),
    campo("observacion", "Observación", requerido=False, alias=("observacion", "observaciones", "nota", "estado")),
]
# Arqueo de caja: recuento del efectivo por denominación (cédula DA-5).
_ARQUEO = [
    campo("denominacion", "Denominación", alias=("denominacion", "billete", "moneda", "corte"), ejemplo="Billete 100"),
    campo("cantidad", "Cantidad", "number", requerido=False, alias=("cantidad", "unidades", "numero", "conteo"), ejemplo="10"),
    campo("valor_unitario", "Valor unitario", "number", requerido=False,
          alias=("valor unitario", "valor", "denominacion valor", "unitario"), ejemplo="100.00"),
    campo("observacion", "Observación", requerido=False, alias=("observacion", "observaciones", "nota")),
]
CAMPOS = {"cuentas": _CUENTAS, "partidas": _PARTIDAS, "libro_mayor": _LIBRO_MAYOR,
          "estado_cuenta": _ESTADO_CUENTA, "conciliacion_anterior": _CONCILIACION_ANTERIOR, "arqueo": _ARQUEO}
TIPOS = {"cuentas": "cuentas", "partidas": "partidas", "libro_mayor": "libro_mayor",
         "estado_cuenta": "estado_cuenta", "conciliacion_anterior": "conciliacion_anterior", "arqueo": "arqueo"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "cuentas"
CONTROL = "saldo_libros"

PARAMETROS = {"diasAntiguedad": 90, "diasCorte": 5, "mesesEquivalente": 3, "mesesRestriccion": 12,
              "tolerancia": 0, "diasPrescripcion": 390}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "diasAntiguedad": "Partida antigua desde (días al corte)",
    "diasCorte": "Días para que el banco acredite un depósito en tránsito",
    "mesesEquivalente": "Plazo de un equivalente (meses desde la adquisición)",
    "mesesRestriccion": "Restricción que la hace no corriente (meses tras el cierre)",
    "tolerancia": "Tolerancia de diferencias (USD)",
    "diasPrescripcion": "Prescripción de una partida (días desde su origen)",
}
TOTAL_EJEMPLO = "auditado"

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Conciliacion", "Conciliación bancaria por cuenta"),
    ("04_Partidas", "Partidas conciliatorias"), ("05_Antiguedad", "Antigüedad de partidas"),
    ("06_Confirmaciones", "Confirmación bancaria"), ("07_Corte", "Prueba de corte"), ("08_Restringido", "Efectivo restringido"),
    ("09_Equivalentes", "Equivalentes de efectivo (definición)"), ("10_Efectivo_auditado", "Efectivo auditado y ajuste"),
    ("11_Asientos", "Asientos propuestos"), ("12_Problemas", "Problemas encontrados"),
    ("13_Conclusion", "Indicadores y conclusión"), ("14_Lectura", "Lectura de resultados"),
    # Papel real DA (calca el papel del cliente; se llena al Procesar y baja también en «Papel formulado (DA)»).
    ("DA0_Libro_Mayor", "DA · Libro Mayor (fuente)"), ("DA1_Sumaria", "DA-1 · Sumaria"),
    ("DA2_Movimiento", "DA-2 · Movimiento de bancos"), ("DA3_Conciliaciones", "DA-3 · Conciliaciones bancarias"),
    ("DA4_Partidas", "DA-4 · Partidas conciliatorias"), ("DA5_Arqueo", "DA-5 · Arqueo de caja"),
    ("DA6_Hallazgos", "DA-6 · Hoja de hallazgos"),
]


def kind(dataset: str) -> str:
    return TIPOS[dataset]


# --- lectura y normalización ---------------------------------------------------------

def _tipo_partida(v) -> str | None:
    s = norm(v)
    if s.startswith(("deposito", "dt", "transito")):
        return DT
    if s.startswith(("cheque", "cp", "pago", "giro", "transferenciapendiente")):
        return CP
    if s.startswith(("notadecredito", "nc", "credito")):
        return NC
    if s.startswith(("notadedebito", "nd", "debito", "comision")):
        return ND
    if s.startswith(("otr",)):
        return OT
    return None


def _tipo_cuenta(v) -> str | None:
    s = norm(v)
    if not s or s.startswith(("banco", "cuenta", "corriente", "ahorro")):
        return BANCO
    if s.startswith(("caja", "fondo")):
        return CAJA
    if s.startswith(("inver", "equiv", "poliza", "certificado", "depositoaplazo", "plazo")):
        return INV
    return None


def _si(v) -> bool:
    return norm(v) in ("si", "s", "x", "yes", "true", "1", "verdadero")


def _texto_si_no(v) -> bool:
    return norm(v) in ("", "si", "s", "x", "yes", "true", "1", "verdadero", "no", "n", "false", "0", "falso")


def validar_filas(tipo: str, filas: list) -> dict:
    """Faltantes, números y fechas ilegibles, totales, claves repetidas y tipos reconocibles."""
    v = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        fila = f.get("_row")
        if tipo == "partidas":
            t = _tipo_partida(f.get("tipo"))
            if str(f.get("tipo", "") or "").strip() and t is None:
                v["errors"].append({"row": fila, "field": "tipo", "message": "Tipo de partida: use Depósito en tránsito, Cheque pendiente, "
                                                                           "Nota de crédito, Nota de débito u Otra partida."})
            imp = a_num(f.get("importe"))
            if t not in (None, OT) and imp is not None and imp < 0:
                v["errors"].append({"row": fila, "field": "importe", "message": "Importe positivo: el tipo de partida ya define si suma o resta "
                                                                              "(solo «Otra partida» lleva signo)."})
        else:
            if _tipo_cuenta(f.get("tipo")) is None:
                v["errors"].append({"row": fila, "field": "tipo", "message": "Tipo de cuenta: use Banco, Caja o Inversión."})
            for k in ("restringido", "presentado_separado"):
                if not _texto_si_no(f.get(k)):
                    v["errors"].append({"row": fila, "field": k, "message": "Use Sí o No."})
            mr = a_num(f.get("monto_restringido"))
            if mr is not None and mr < 0:
                v["errors"].append({"row": fila, "field": "monto_restringido", "message": "Monto restringido: use un importe positivo."})
    v["ok"] = not v["errors"]
    return v


def _clave(v) -> str:
    """Como SUMIFS/COUNTIF de Excel: sin distinguir mayúsculas (los códigos se escriben sin espacios de borde)."""
    return str(v if v is not None else "").strip().lower()


def _edate(d: date, meses: int) -> date:
    """EDATE de Excel."""
    y, mm = divmod(d.month - 1 + meses, 12)
    y += d.year
    return date(y, mm + 1, min(d.day, calendar.monthrange(y, mm + 1)[1]))


def _opt(v):
    return None if str(v if v is not None else "").strip() == "" else a_num(v)


def _refs(p: dict) -> dict:
    if not es_pymes(p):
        return {"marco": "NIIF completas", "def": "NIC 7.6–7.7", "sob": "NIC 7.8", "restr": "NIC 7.48 y NIC 1.66 d)", "revel": "NIC 7.48",
                "comp": "NIC 7.45–7.46", "ifrs18": " (al corte 2025 aplica la NIC 1; la NIIF 18 rige para ejercicios desde el 1-1-2027; desde 2027 el requisito pasa a NIIF 18 párr. 99 d))"}
    ed = edicion_pymes(p)
    return {"marco": f"NIIF para las PYMES {ed}", "def": "Sección 7.2", "sob": "Sección 7.2",
            "restr": "Secciones 7.21 y 4.5 d)", "revel": "Sección 7.21", "comp": "Sección 7.20", "ifrs18": ""}


def _parametros(parametros: dict) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    for k in PARAMETROS:
        x = a_num(p[k])
        if x is None or x < 0:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: use un número no negativo.")
        p[k] = float(x)
    for k in ("diasAntiguedad", "mesesEquivalente", "mesesRestriccion"):
        if p[k] <= 0:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: debe ser mayor que cero.")
    for k in ("mesesEquivalente", "mesesRestriccion"):
        if p[k] != int(p[k]):
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: use meses enteros.")
    return p


# --- cálculo ---------------------------------------------------------------------------

def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = _parametros(parametros)
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    rf = _refs(p)
    tol, dias_ant, dias_corte = p["tolerancia"], p["diasAntiguedad"], p["diasCorte"]
    meses_eq = int(p["mesesEquivalente"])
    dias_presc = int(p["diasPrescripcion"])
    limite_restr = _edate(corte_a, int(p["mesesRestriccion"]))

    cuentas = []
    for f in datasets.get("cuentas") or []:
        if str(f.get("id", "") or "").strip() == "" and _opt(f.get("saldo_libros")) is None:
            continue
        mr = _opt(f.get("monto_restringido"))
        cuentas.append({
            "id": str(f.get("id", "")).strip(), "nombre": str(f.get("nombre", "") or "").strip() or "(sin nombre)",
            "tipo": _tipo_cuenta(f.get("tipo")) or BANCO, "moneda": str(f.get("moneda", "") or "").strip().upper(),
            "libros": num(f.get("saldo_libros")),
            "banco": _opt(f.get("saldo_banco")), "conf": _opt(f.get("saldo_confirmado")),
            "restr": _si(f.get("restringido")) or bool(mr), "monto": mr, "motivo": str(f.get("motivo_restriccion", "") or "").strip(),
            "fin": fecha(f.get("fin_restriccion")), "sep": _si(f.get("presentado_separado")),
            "adq": fecha(f.get("fecha_adquisicion")), "venc": fecha(f.get("fecha_vencimiento")), "_row": f.get("_row")})
    if not cuentas:
        raise ValueError("Cargue el anexo de cuentas de caja, bancos e inversiones con su saldo según libros.")
    ids = {_clave(c["id"]) for c in cuentas}

    partidas = []
    for f in datasets.get("partidas") or []:
        if str(f.get("id", "") or "").strip() == "" and _opt(f.get("importe")) is None:
            continue
        o, lq = fecha(f.get("fecha_origen")), fecha(f.get("fecha_liquidacion"))
        x = {"id": str(f.get("id", "")).strip(), "cuenta": str(f.get("cuenta", "") or "").strip(),
             "tipo": _tipo_partida(f.get("tipo")) or OT, "ref": str(f.get("referencia", "") or "").strip(),
             "origen": o, "importe": num(f.get("importe")), "liq": lq, "_row": f.get("_row")}
        x["diasCorte"] = (corte_a - o).days if o else None
        x["diasLiq"] = (lq - o).days if (lq and o) else None
        x["antigua"] = x["diasCorte"] is not None and x["diasCorte"] > dias_ant
        x["depurada"] = lq is not None
        x["existe"] = _clave(x["cuenta"]) in ids
        x["diasPost"] = (lq - corte_a).days if lq else None
        x["prescribe"] = date.fromordinal(o.toordinal() + dias_presc) if o else None
        if o and o > corte_a:
            x["corte"] = "Registrada después del corte"
        elif lq is None:
            x["corte"] = "Sin liquidación posterior"
        elif x["tipo"] == DT and x["diasPost"] > dias_corte:
            x["corte"] = "Depósito acreditado tarde"
        else:
            x["corte"] = "Correcto"
        partidas.append(x)

    # 1–2 · conciliación por cuenta.
    for c in cuentas:
        mias = [x for x in partidas if _clave(x["cuenta"]) == _clave(c["id"])]
        for k, t in (("dt", DT), ("cp", CP), ("nc", NC), ("nd", ND), ("ot", OT)):
            c[k] = sum(x["importe"] for x in mias if x["tipo"] == t)
        c["esperado"] = None if c["banco"] is None else c["banco"] + c["dt"] - c["cp"] - c["nc"] + c["nd"] + c["ot"]
        c["dif"] = None if c["esperado"] is None else round(c["libros"] - c["esperado"], 2)
        c["ajustado"] = c["libros"] + c["nc"] - c["nd"]
        # 5 · confirmación (cuentas de banco e inversiones).
        c["difConf"] = None if (c["conf"] is None or c["banco"] is None) else round(c["conf"] - c["banco"], 2)
        if c["conf"] is None:
            c["estadoConf"] = "Sin respuesta: procedimiento alternativo"
        elif c["difConf"] is None:
            c["estadoConf"] = "Sin estado bancario"
        else:
            c["estadoConf"] = "Coincide" if abs(c["difConf"]) <= tol else "No coincide"
        # 6 · restringido.
        if c["restr"]:
            # NIC 1.66 d) / PYMES 4.5 d): «al menos doce meses» → la restricción que vence en el límite ya es no corriente.
            c["clasif"] = "Sin fecha de fin: revisar el soporte" if c["fin"] is None else ("No corriente" if c["fin"] >= limite_restr else "Corriente")
            c["reclasR"] = c["monto"] if (c["clasif"] == "No corriente" and not c["sep"]) else 0.0
        else:
            c["clasif"], c["reclasR"] = None, None
        # 7 · equivalentes: tres meses desde la adquisición (NIC 7.7), no 90 días.
        if c["tipo"] == INV:
            c["plazo"] = (c["venc"] - c["adq"]).days if (c["adq"] and c["venc"]) else None
            c["limite"] = _edate(c["adq"], meses_eq) if c["adq"] else None
            c["califica"] = ("Sin fechas: revisar el soporte" if (c["adq"] is None or c["venc"] is None)
                             else ("Sí" if c["venc"] <= c["limite"] else "No"))
            c["reclasNE"] = max(c["ajustado"] - (c["reclasR"] or 0), 0) if c["califica"] == "No" else 0.0
        c["auditado"] = c["ajustado"] - (c["reclasR"] or 0) - (c.get("reclasNE") or 0)

    libros = sum(c["libros"] for c in cuentas)
    nc, nd = sum(c["nc"] for c in cuentas), sum(c["nd"] for c in cuentas)
    reclas_r = sum(c["reclasR"] or 0 for c in cuentas)
    reclas_nc = sum(c["reclasR"] or 0 for c in cuentas if c["clasif"] == "No corriente")
    reclas_ne = sum(c.get("reclasNE") or 0 for c in cuentas)
    auditado = libros + (nc - nd) - reclas_r - reclas_ne
    con = {
        "saldoLibros": libros, "nc": nc, "nd": nd, "notas": nc - nd, "reclasRestringido": reclas_r, "reclasNoCorriente": reclas_nc,
        "reclasNoEquivalentes": reclas_ne, "auditado": auditado, "ajuste": auditado - libros,
        "caja": sum(c["auditado"] for c in cuentas if c["tipo"] == CAJA),
        "bancos": sum(c["auditado"] for c in cuentas if c["tipo"] == BANCO),
        "equivalentes": sum(c["auditado"] for c in cuentas if c["tipo"] == INV),
        "difNoExplicada": sum(abs(c["dif"]) for c in cuentas if c["dif"] is not None),
        "difConfirmacion": sum(abs(c["difConf"]) for c in cuentas if c["tipo"] != CAJA and c["difConf"] is not None),
        "partidasAntiguas": sum(x["importe"] for x in partidas if x["antigua"]),
        "partidasNoDepuradas": sum(x["importe"] for x in partidas if not x["depurada"]),
    }

    # Problemas (M22: cada «debe» que el cálculo no garantiza).
    pr = []
    for c in cuentas:
        nom = f"{c['id']} {c['nombre']}"
        if c["banco"] is None:
            pr.append(problema("SIN_ESTADO_BANCARIO", f"{nom}: falta el saldo según estado bancario o arqueo; la conciliación no se puede medir.", c["libros"]))
        elif abs(c["dif"]) > tol:
            pr.append(problema("DIFERENCIA_NO_EXPLICADA", f"{nom}: los libros ({fmt_m(c['libros'])}) difieren en {fmt_m(c['dif'])} del saldo que "
                                                          f"explica la conciliación ({fmt_m(c['esperado'])}). Investigue y evalúe como incorrección (NIA 450).", c["dif"]))
        if c["tipo"] != CAJA:
            if c["conf"] is None:
                pr.append(problema("SIN_CONFIRMACION", f"{nom}: sin respuesta del banco; aplique procedimientos alternativos (NIA 505).", c["libros"]))
            elif c["estadoConf"] == "No coincide":
                pr.append(problema("CONFIRMACION_NO_COINCIDE", f"{nom}: el banco confirma {fmt_m(c['conf'])} y el estado bancario muestra "
                                                               f"{fmt_m(c['banco'])}. Obtenga explicación del banco y del cliente (NIA 505 párr. 14).", c["difConf"]))
        if c["libros"] < 0:
            pr.append(problema("SALDO_ACREEDOR", f"{nom}: saldo acreedor (sobregiro). Solo integra el efectivo si es exigible a la vista y parte "
                                                 f"integrante de la gestión del efectivo ({rf['sob']}); si no, presentarlo como pasivo financiero.", c["libros"]))
        if c["restr"]:
            if c["monto"] is None:
                pr.append(problema("RESTRICCION_SIN_MONTO", f"{nom}: marcada como restringida sin monto restringido; cuantifíquelo.", 0))
            else:
                pr.append(problema("RESTRINGIDO_REVELAR", f"{nom}: {fmt_m(c['monto'])} restringidos ({c['motivo'] or 'motivo no indicado'}). "
                                                          f"La restricción no los saca del efectivo y equivalentes, pero debe revelarse el importe no disponible "
                                                          f"junto con un comentario de la gerencia ({rf['revel']}).", c["monto"]))
                if c["reclasR"]:
                    pr.append(problema("RESTRINGIDO_COMO_DISPONIBLE", f"{nom}: {fmt_m(c['monto'])} restringidos por al menos {int(p['mesesRestriccion'])} meses "
                                                                      f"(hasta el {c['fin'].isoformat()}) presentados como efectivo disponible. "
                                                                      f"Reclasificar a no corriente y revelar ({rf['restr']}).", c["reclasR"]))
            if c["fin"] is None:
                pr.append(problema("RESTRICCION_SIN_FECHA", f"{nom}: restricción sin fecha de fin; indique hasta cuándo dura para decidir si es corriente "
                                                            f"o no corriente ({rf['restr']}). Mientras tanto no se reclasifica nada.", c["monto"] or 0))
        if c["tipo"] == INV:
            if c["plazo"] is None:
                pr.append(problema("INVERSION_SIN_FECHAS", f"{nom}: faltan las fechas de adquisición o vencimiento para evaluar si es equivalente ({rf['def']}).", c["libros"]))
            elif c["califica"] == "No":
                pr.append(problema("NO_ES_EQUIVALENTE", f"{nom}: vence el {c['venc'].isoformat()}, después de los {meses_eq} meses desde la adquisición "
                                                        f"(hasta el {c['limite'].isoformat()}); no es equivalente de efectivo ({rf['def']}). Reclasificar a inversiones.", c["reclasNE"]))
            else:
                pr.append(problema("EQUIVALENTE_PRESUNCION", f"{nom}: vence dentro de los {meses_eq} meses desde la adquisición, lo que es solo una presunción. "
                                                             f"La definición exige además que sea de gran liquidez, fácilmente convertible en importes determinados "
                                                             f"de efectivo y sujeto a un riesgo poco significativo de cambios de valor ({rf['def']}): documéntelo.", c["libros"]))
    if abs(nc - nd) > 0.005:
        pr.append(problema("NOTAS_NO_REGISTRADAS", f"Notas bancarias no registradas en libros: crédito {fmt_m(nc)} y débito {fmt_m(nd)}. Ajustar los libros.", nc - nd))
    for x in partidas:
        nom = f"{x['id']} ({x['tipo']}, cuenta {x['cuenta']})"
        if not x["existe"]:
            pr.append(problema("PARTIDA_SIN_CUENTA", f"{nom}: la cuenta no está en el anexo de cuentas.", x["importe"]))
        if x["antigua"]:
            pr.append(problema("PARTIDA_ANTIGUA", f"{nom}: {x['diasCorte']} días al corte (más de {int(dias_ant)}). Evalúe su reverso o ajuste.", x["importe"]))
        if not x["depurada"]:
            pr.append(problema("PARTIDA_NO_DEPURADA", f"{nom}: sin liquidación posterior al corte; obtenga soporte de su existencia.", x["importe"]))
        if x["corte"] == "Registrada después del corte":
            pr.append(problema("CORTE_POSTERIOR", f"{nom}: originada el {x['origen'].isoformat()}, después del corte; no debe conciliar el saldo al cierre.", x["importe"]))
        elif x["corte"] == "Depósito acreditado tarde":
            pr.append(problema("CORTE_DEPOSITO_TARDIO", f"{nom}: el banco lo acreditó {x['diasPost']} días después del corte (más de {int(dias_corte)}). "
                                                        "Verifique que el ingreso corresponde al ejercicio (NIA 240 párr. 31 y Anexo 2).", x["importe"]))
        if x["tipo"] == OT:
            pr.append(problema("OTRA_PARTIDA", f"{nom}: partida sin naturaleza definida; requiere investigación.", x["importe"]))

    # Partidas duplicadas (posible doble registro) y recurrentes (venían del mes anterior).
    # Importe 0: son avisos de calidad del dato, no cifras monetarias (no requieren enlace a celda).
    conteo = Counter((_clave(x["cuenta"]), x["tipo"], round(x["importe"], 2), x["origen"]) for x in partidas)
    ya_avisadas = set()
    for x in partidas:
        k = (_clave(x["cuenta"]), x["tipo"], round(x["importe"], 2), x["origen"])
        if conteo[k] > 1 and k not in ya_avisadas:
            pr.append(problema("PARTIDA_DUPLICADA", f"{x['id']} ({x['tipo']}, cuenta {x['cuenta']}): partida repetida "
                                                    f"({fmt_m(x['importe'])} en la misma fecha); verifique un posible doble registro.", 0))
            ya_avisadas.add(k)
    previas_por_cuenta: dict = {}
    for a in (datasets.get("conciliacion_anterior") or []):
        v = a_num(a.get("valor"))
        if v is not None:
            previas_por_cuenta.setdefault(_clave(a.get("cuenta")), set()).add(round(v, 2))
    for x in partidas:
        if round(x["importe"], 2) in previas_por_cuenta.get(_clave(x["cuenta"]), set()):
            pr.append(problema("PARTIDA_RECURRENTE", f"{x['id']} ({x['tipo']}, cuenta {x['cuenta']}): {fmt_m(x['importe'])} ya figuraba en "
                                                     "la conciliación del mes anterior; partida recurrente no depurada.", 0))

    # Integridad entre los datasets auxiliares y el anexo de cuentas (importe 0: son avisos de
    # ingesta, no cifras monetarias, y no requieren enlace a celda).
    def _codigos_de(nombre: str) -> list[str]:
        return [str(f.get("cuenta", "") or "").strip() for f in (datasets.get(nombre) or [])
                if str(f.get("cuenta", "") or "").strip()]
    for ds_, cod_, donde in (("estado_cuenta", "ESTADO_SIN_CUENTA", "el estado de cuenta bancario"),
                             ("libro_mayor", "MAYOR_SIN_CUENTA", "el libro mayor"),
                             ("conciliacion_anterior", "CONCILIACION_ANTERIOR_SIN_CUENTA", "la conciliación del mes anterior")):
        for cod in sorted({c for c in _codigos_de(ds_) if _clave(c) not in ids}):
            pr.append(problema(cod_, f"La cuenta {cod} aparece en {donde} pero no está en el anexo de cuentas de caja y "
                                     "bancos. Verifique el código o agréguela al anexo.", 0))
    # Moneda: si el anexo mezcla divisas (los saldos en blanco se asumen USD), avisar; esta
    # herramienta no convierte monedas.
    monedas = sorted({(c.get("moneda") or "USD") for c in cuentas})
    if len(monedas) > 1:
        pr.append(problema("MONEDA_INCONSISTENTE", f"El anexo mezcla monedas ({', '.join(monedas)}). Confirme la moneda de "
                                                   "presentación; esta herramienta no convierte divisas.", 0))

    iso = lambda d: d.isoformat() if d else ""
    filas = [{"id": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "saldo_libros": r2(c["libros"]),
              "saldo_banco": "" if c["banco"] is None else r2(c["banco"]), "diferencia": "" if c["dif"] is None else r2(c["dif"]),
              "saldo_ajustado": r2(c["ajustado"]), "auditado": r2(c["auditado"]), "_row": c["_row"]} for c in cuentas]
    claves = ["saldoLibros", "notas", "reclasRestringido", "reclasNoEquivalentes", "auditado", "ajuste",
              "difNoExplicada", "difConfirmacion", "partidasAntiguas", "partidasNoDepuradas"]
    etiquetas = {"saldoLibros": "Efectivo y equivalentes según libros", "notas": "Notas bancarias no registradas (crédito − débito)",
                 "reclasRestringido": "Reclasificación a no corriente (restricción ≥ 12 meses)", "reclasNoEquivalentes": "Reclasificación de inversiones que no son equivalentes",
                 "auditado": "Efectivo y equivalentes auditado", "ajuste": "Ajuste propuesto (auditado − libros)",
                 "difNoExplicada": "Diferencias de conciliación no explicadas (absolutas)", "difConfirmacion": "Diferencias de confirmación (absolutas)",
                 "partidasAntiguas": "Partidas conciliatorias antiguas", "partidasNoDepuradas": "Partidas no depuradas después del corte"}
    # Anexos crudos que alimentan las cédulas del papel real DA (Sumaria/Movimiento,
    # Libro Mayor fuente y Arqueo). No entran en el cálculo del resultado; se conservan
    # para que ``hojas()`` calque el papel del cliente con fórmulas vivas (SUMIF sobre el
    # Libro Mayor, cantidad × valor del arqueo). El ciclo poda ``detalle`` tras armar las
    # hojas (servicio.py), así que estos anexos no engordan el registro persistido.
    _crudo = lambda filas: [{k: v for k, v in f.items() if not str(k).startswith("_")} for f in (filas or [])]
    detalle = {"parametros": p, "corte": corte_a.isoformat(), "limiteRestriccion": limite_restr.isoformat(), "refs": rf, "conceptos": con,
               "cuentas": [{k: (iso(v) if isinstance(v, date) else v) for k, v in c.items()} for c in cuentas],
               "partidas": [{k: (iso(v) if isinstance(v, date) else v) for k, v in x.items()} for x in partidas],
               "libro_mayor": _crudo(datasets.get("libro_mayor")), "arqueo": _crudo(datasets.get("arqueo")),
               "estado_cuenta": _crudo(datasets.get("estado_cuenta")), "conciliacion_anterior": _crudo(datasets.get("conciliacion_anterior"))}
    return {"engine": VERSION, "rows": filas, "totals": {k: r2(con[k]) for k in claves}, "labels": {k: etiquetas[k] for k in claves},
            "primary": "ajuste", "exceptions": pr, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ----------------------------------------------------------------

P = ref("02_Parametros")
CON_, PAR_, AUD = ref("03_Conciliacion"), ref("04_Partidas"), ref("10_Efectivo_auditado")
RES_, EQU_, CNF_ = ref("08_Restringido"), ref("09_Equivalentes"), ref("06_Confirmaciones")
PAR = {k: FILA0 + i for i, k in enumerate(["corte", "diasAntiguedad", "diasCorte", "mesesEquivalente", "mesesRestriccion", "tolerancia"])}
CONCEPTOS = ["saldoLibros", "nc", "nd", "notas", "reclasRestringido", "reclasNoCorriente", "reclasNoEquivalentes", "auditado", "ajuste",
             "caja", "bancos", "equivalentes", "difNoExplicada", "difConfirmacion", "partidasAntiguas", "partidasNoDepuradas"]
FC = {k: f"{AUD}$B${FILA0 + i}" for i, k in enumerate(CONCEPTOS)}
TRAMOS = [("Posterior al corte", '"<0"', None), ("0 a 30 días", '">=0"', '"<=30"'), ("31 a 60 días", '">=31"', '"<=60"'),
          ("61 a 90 días", '">=61"', '"<=90"'), ("91 a 180 días", '">=91"', '"<=180"'), ("Más de 180 días", '">180"', None)]
TRAMOS_PY = [(None, -1), (0, 30), (31, 60), (61, 90), (91, 180), (181, None)]

# --- papel real DA (calca el papel del cliente con fórmulas vivas y referencias cruzadas) ---
# Nombres de las pestañas DA (≤ 31, únicos frente a 01_…14_) y sus referencias entre hojas.
DA_LM, DA_SUM = "DA0_Libro_Mayor", "DA1_Sumaria"
DA_MOV, DA_CON = "DA2_Movimiento", "DA3_Conciliaciones"
DA_PAR, DA_ARQ, DA_HAL = "DA4_Partidas", "DA5_Arqueo", "DA6_Hallazgos"
LM_, SUM_, PAR_DA = ref(DA_LM), ref(DA_SUM), ref(DA_PAR)
# Categoría conciliatoria del papel DA (los literales alimentan los SUMIFS de DA-3).
DA_CONSIG, DA_SOBREGIRO, DA_CHEQUE = "Consignación no registrada", "Sobregiro/ajuste", "Cheque sin cobrar"
DA_ND, DA_NC = "Nota débito en tránsito", "NC pendiente contabilizar"
_TIPO_A_DACAT = {DT: DA_CONSIG, CP: DA_CHEQUE, ND: DA_ND, NC: DA_NC, OT: DA_SOBREGIRO}
# Denominaciones estándar del arqueo de caja (DA-5) cuando no se cargó el recuento (RQ-012).
DA_DENOMS = [("Billetes de $100.00", 100.0), ("Billetes de $50.00", 50.0), ("Billetes de $20.00", 20.0),
             ("Billetes de $10.00", 10.0), ("Billetes de $5.00", 5.0), ("Billetes de $2.00", 2.0),
             ("Billetes de $1.00", 1.0), ("Monedas de $1.00", 1.0), ("Monedas de $0.50", 0.50),
             ("Monedas de $0.25", 0.25), ("Monedas de $0.10", 0.10), ("Monedas de $0.05", 0.05),
             ("Monedas de $0.01", 0.01)]


# Explicación humana de cada columna calculada («Cómo se calcula esta hoja»).
_TIPO_PARTIDA = ("Suma el importe de las partidas conciliatorias de esta cuenta que en la hoja 04 (Partidas "
                 "conciliatorias) están clasificadas como «{}».")
EXPLICA = {
    "01_Resumen": {
        "Importe": ("Trae cada importe, concepto por concepto, de la hoja 10 (Efectivo auditado y ajuste), donde se "
                    "calcula el efectivo auditado, las reclasificaciones y las diferencias encontradas."),
    },
    "03_Conciliacion": {
        "(+) Depósitos en tránsito": _TIPO_PARTIDA.format(DT),
        "(−) Cheques pendientes": _TIPO_PARTIDA.format(CP),
        "(−) Notas de crédito no registradas": _TIPO_PARTIDA.format(NC),
        "(+) Notas de débito no registradas": _TIPO_PARTIDA.format(ND),
        "(±) Otras partidas": _TIPO_PARTIDA.format(OT),
        "Saldo que explica la conciliación": ("Parte del saldo del estado bancario o arqueo, suma los depósitos en tránsito, "
                                              "resta los cheques pendientes y las notas de crédito, y suma las notas de "
                                              "débito y otras partidas. Sin saldo bancario, queda en blanco."),
        "Diferencia no explicada": ("Resta al saldo según libros el saldo que explica la conciliación, redondeado a "
                                    "centavos: lo que la conciliación no alcanza a justificar. Sin saldo bancario, queda en blanco."),
        "Saldo ajustado de libros": ("Parte del saldo según libros, suma las notas de crédito y resta las notas de débito "
                                     "que el banco registró y los libros todavía no."),
        "Efectivo auditado": ("Al saldo ajustado de libros le resta lo que se reclasifica por restricción (hoja 08, "
                              "Efectivo restringido) y por inversiones que no son equivalentes (hoja 09) para esta cuenta."),
        "Semáforo": ("Estado de la cuenta: «Alerta» si la diferencia no explicada no es cero (hay que investigarla), "
                     "«Conforme» si la conciliación cuadra. Sin saldo bancario, queda en blanco."),
    },
    "04_Partidas": {
        "Días al corte": ("Resta la fecha de origen de la partida de la fecha de corte de la hoja 02 (Parámetros). Negativo "
                          "significa que se originó después del corte; sin fecha de origen, queda en blanco."),
        "Días hasta la liquidación": ("Cuenta los días entre la fecha de origen y la liquidación posterior de la partida; "
                                      "si falta cualquiera de las dos fechas, queda en blanco."),
        "Antigua": ("Marca «Sí» si los días al corte superan el umbral de antigüedad de la hoja 02 (Parámetros); sin "
                    "días al corte, o dentro del umbral, marca «No»."),
        "Depurada": ("Marca «Sí» si la partida tiene fecha de liquidación posterior al corte y «No» si todavía no se ha "
                     "liquidado."),
        "Cuenta en el anexo": ("Marca «Sí» si la cuenta de la partida figura en la hoja 03 (Conciliación bancaria por "
                               "cuenta) y «No» si no está en el anexo de cuentas."),
    },
    "05_Antiguedad": {
        "Partidas": ("Cuenta cuántas partidas de la hoja 04 (Partidas conciliatorias) tienen días al corte dentro de este "
                     "tramo; «Posterior al corte» son las de días negativos."),
        "Importe": "Suma el importe de las partidas de la hoja 04 (Partidas conciliatorias) cuyos días al corte caen en este tramo.",
        "No depurado": ("Suma solo el importe de las partidas de este tramo que en la hoja 04 siguen marcadas como no "
                        "depuradas (sin liquidación posterior)."),
    },
    "06_Confirmaciones": {
        "Saldo según estado bancario": ("Trae el saldo del estado bancario de la misma cuenta desde la hoja 03 "
                                        "(Conciliación bancaria por cuenta); si no hay, queda en blanco."),
        "Diferencia (confirmado − estado)": ("Resta al saldo que confirmó el banco el saldo del estado bancario, redondeado "
                                             "a centavos; si falta cualquiera de los dos, queda en blanco."),
        "Resultado": ("Sin respuesta del banco indica aplicar un procedimiento alternativo; sin estado bancario lo avisa; "
                      "si la diferencia está dentro de la tolerancia de la hoja 02 (Parámetros) dice «Coincide» y, si no, «No coincide»."),
    },
    "07_Corte": {
        "Días después del corte": ("Resta la fecha de corte de la hoja 02 (Parámetros) de la fecha en que el banco "
                                   "registró la partida; sin fecha en el banco, queda en blanco."),
        "Resultado": ("Si la partida se registró en libros después del corte lo marca; si el banco no la registró después, "
                      "dice «Sin liquidación posterior»; un depósito en tránsito acreditado después de los días permitidos "
                      "en la hoja 02 es «Depósito acreditado tarde»; lo demás es «Correcto»."),
        "Importe": "Trae el importe de la misma partida desde la hoja 04 (Partidas conciliatorias).",
    },
    "08_Restringido": {
        "Saldo ajustado": "Trae el saldo ajustado de libros de la misma cuenta desde la hoja 03 (Conciliación bancaria por cuenta).",
        "Clasificación": ("Sin fecha de fin pide revisar el soporte; si la restricción termina en la fecha límite (corte más "
                          "los meses de la hoja 02, Parámetros) o después, es «No corriente»; si termina antes, «Corriente»."),
        "Reclasificación propuesta": ("Propone reclasificar el monto restringido solo si es no corriente y todavía no se "
                                      "presenta aparte; en los demás casos es cero."),
    },
    "09_Equivalentes": {
        "Plazo original (días)": ("Cuenta los días entre la adquisición y el vencimiento de la inversión; si falta alguna "
                                  "de las dos fechas, queda en blanco."),
        "Vence en tres meses o menos (presunción)": ("Marca «Sí» si el vencimiento no pasa de los meses de la hoja 02 "
                                                     "(Parámetros) contados desde la adquisición y «No» si pasa; sin fechas, "
                                                     "pide revisar el soporte."),
        "Saldo ajustado": ("Trae el saldo ajustado de libros de la misma inversión desde la hoja 03 (Conciliación "
                           "bancaria por cuenta)."),
        "Ya reclasificado por restricción": ("Suma lo que la hoja 08 (Efectivo restringido) ya propone reclasificar para "
                                             "esta misma cuenta, para no reclasificarlo dos veces."),
        "Reclasificación propuesta": ("Si la inversión no vence dentro del plazo, propone reclasificar su saldo ajustado "
                                      "menos lo ya reclasificado por restricción (nunca negativo); si califica, es cero."),
    },
    "10_Efectivo_auditado": {
        "Importe": ("Cada concepto tiene su cálculo: libros y notas bancarias se suman de la hoja 03 (Conciliación); las "
                    "reclasificaciones, de las hojas 08 y 09; el auditado es libros + notas − reclasificaciones y el "
                    "ajuste, auditado − libros; la composición suma el efectivo auditado por tipo de cuenta; las "
                    "diferencias y partidas salen de las hojas 03, 04 y 06."),
    },
    "11_Asientos": {
        "Debe": ("Toma cada importe de la hoja 10 (Efectivo auditado y ajuste): notas de crédito y de débito no registradas "
                 "y las reclasificaciones por restricción y por inversiones que no son equivalentes."),
        "Haber": ("Lleva a la contrapartida el mismo importe del asiento, tomado de la hoja 10 (Efectivo auditado y "
                  "ajuste), para que debe y haber cuadren."),
    },
    "13_Conclusion": {
        "Importe": ("Cada indicador trae su importe de la hoja 10 (Efectivo auditado y ajuste): el efectivo auditado, el "
                    "saldo según libros, el ajuste propuesto, las diferencias de conciliación no explicadas y las "
                    "reclasificaciones por restricción e inversiones que no son equivalentes."),
        "Porcentaje": ("Divide el ajuste propuesto en valor absoluto entre el efectivo según libros para medir su peso "
                       "relativo; queda en blanco si el saldo según libros es cero."),
        "Cantidad": ("Cuenta cuántos problemas se detectaron leyendo la columna de códigos de la hoja 12 (Problemas "
                     "encontrados)."),
        "Estado": ("Semáforo del indicador: «Alerta» cuando hay un ajuste o una diferencia por encima de la tolerancia de "
                   "la hoja 02 (Parámetros), «Revisar» cuando hay reclasificaciones o problemas que atender y «Conforme» "
                   "cuando el indicador no presenta desviaciones."),
    },
    "14_Lectura": {
        "Detalle": ("Redacta en lenguaje del auditor la lectura causa-efecto de los resultados e inserta cada cifra con "
                    "FIXED desde la hoja 10 (Efectivo auditado y ajuste): el efectivo auditado frente a los libros, el "
                    "ajuste propuesto y su efecto, las diferencias de conciliación y confirmación, las reclasificaciones "
                    "y las partidas conciliatorias antiguas."),
    },
    # Papel real DA.
    "DA1_Sumaria": {
        "Variación": ("Resta al saldo actual según registros el saldo del período anterior, para mostrar cuánto se movió "
                      "el efectivo de cada cuenta entre el cierre anterior y el corte."),
    },
    "DA2_Movimiento": {
        "Débitos del período": ("Suma con SUMIF los débitos del Libro Mayor (hoja DA0) cuyo código de cuenta coincide con "
                                "el de esta fila: los ingresos y abonos registrados en la cuenta durante el período."),
        "Créditos del período": ("Suma con SUMIF los créditos del Libro Mayor (hoja DA0) de esta misma cuenta: los egresos "
                                 "y cargos registrados en la cuenta durante el período."),
        "Saldo final s/movimiento": ("Parte del saldo inicial, suma los débitos y resta los créditos del período: el saldo "
                                     "que debería mostrar la cuenta según el movimiento del Libro Mayor."),
        "Cuadre s/Sumaria": ("Resta al saldo final por movimiento el saldo actual de la misma cuenta en la Sumaria (DA-1); "
                             "en cero cuando el movimiento del mayor explica el saldo del corte."),
    },
    "DA3_Conciliaciones": {
        "(+) Consignaciones no registradas": ("Suma con SUMIFS el valor de las partidas de DA-4 de este banco clasificadas "
                                              "como consignación no registrada por el banco (depósitos en tránsito)."),
        "(−) Sobregiro / ajustes": ("Suma con SUMIFS el valor de las partidas de DA-4 de este banco marcadas como sobregiro "
                                    "o ajuste, que restan del saldo del extracto."),
        "(−) Cheques sin cobrar": ("Suma con SUMIFS el valor de las partidas de DA-4 de este banco que son cheques girados "
                                   "y todavía no cobrados por el beneficiario."),
        "(+) Nota débito en tránsito": ("Suma con SUMIFS el valor de las partidas de DA-4 de este banco que son notas de "
                                        "débito del banco todavía no registradas en libros."),
        "(−) NC pendiente de contabilizar": ("Suma con SUMIFS el valor de las partidas de DA-4 de este banco que son notas "
                                             "de crédito del banco pendientes de contabilizar en libros."),
        "Saldo s/auditoría": ("Parte del saldo del extracto, suma consignaciones y notas de débito y resta sobregiros, "
                              "cheques sin cobrar y notas de crédito pendientes: el saldo conciliado del banco."),
        "Saldo s/registros contables": ("Trae el saldo actual según registros de la misma cuenta desde la Sumaria (DA-1), "
                                        "para contrastarlo con el saldo conciliado del extracto."),
        "Diferencia": ("Resta al saldo conciliado de auditoría el saldo según registros contables: en cero cuando la "
                       "conciliación cuadra y distinto de cero cuando hay partidas por depurar."),
    },
    "DA4_Partidas": {
        "Días vencidos": ("Resta la fecha de la partida a la fecha de corte del encargo (hoja 02, Parámetros): los días que "
                          "la partida conciliatoria lleva pendiente de depurar; sin fecha, queda en blanco."),
        "Fecha de prescripción": ("Suma a la fecha de la partida 360 + 30 días para estimar la fecha en que prescribe y debe "
                                  "regularizarse; sin fecha de origen, queda en blanco."),
    },
    "DA5_Arqueo": {
        "Total": ("Multiplica la cantidad contada por el valor unitario de cada denominación; las filas de cierre suman el "
                  "arqueo, traen el saldo de caja según libros de la Sumaria (DA-1) y calculan la diferencia."),
    },
}

# Panel del dashboard (formato en graficos.py).
PANEL = {
    "poblacion": {"rotulo": "Cuentas según libros", "hoja": "03_Conciliacion", "col": "Saldo según libros"},
    "recalculado": {"rotulo": "Efectivo auditado", "total": "auditado"},
    "registrado": {"rotulo": "Efectivo según libros", "total": "saldoLibros"},
    "composicion": {"rotulo": "Efectivo auditado por tipo", "hoja": "03_Conciliacion", "etiqueta": "Tipo",
                    "valor": "Efectivo auditado"},
    "distribucion": {"rotulo": "Saldo en libros por cuenta", "hoja": "03_Conciliacion", "etiqueta": "Banco / caja",
                     "valor": "Saldo según libros"},
    # Tablero premium (columnas agrupadas por tramo de antigüedad; ver graficos.tableros_spec).
    # Categorías fijas: los tramos de la constante TRAMOS, que la hoja 05 siempre emite.
    "tableros": [
        {"rotulo": "Antigüedad de las partidas conciliatorias", "sub": "USD por tramo · importe total frente al no depurado.",
         "unidad": "USD", "hoja": "05_Antiguedad", "etiqueta": "Tramo (días al corte)", "seccion": "Antigüedad de partidas",
         "filas": [{"fila": et, "mejor": "bajo"} for et, _a, _b in TRAMOS],
         "series": [["Importe", "Importe"], ["No depurado", "No depurado"]]},
    ],
}


def _rango(h: str, col: str, n: int) -> str:
    return f"{h}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _pos(x: str) -> str:
    """Suma de valores absolutos que ignora celdas vacías o con texto (ABS falla con "")."""
    return f'SUMIF({x},">0")-SUMIF({x},"<0")'


# --- origen del importe de cada problema (ver procesadores/problemas.py) --------------

_T = problemas._texto
def _CUENTA(f) -> str:
    """«id nombre:» con que empieza la descripción de un problema de cuenta (hojas 03, 06, 08 y 09)."""
    return f"{_T(f[0])} {_T(f[1])}:"


def _PARTIDA(f) -> str:
    """«id (tipo, cuenta X):» con que empieza la descripción de un problema de partida (hojas 04 y 07)."""
    return f"{_T(f[0])} ({_T(f[2])}, cuenta {_T(f[1])}):"


def _por_fila(hoja_: str, columna: str, prefijo):
    """Celda de la columna en la fila (cuenta o partida) que abre la descripción del problema."""
    def f(hojas, e):
        h = next((x for x in hojas if x["name"] == hoja_), None)
        if h is None:
            return None
        msg = e.get("message") or ""
        j = [c[0] for c in h["cols"]].index(columna)
        for i, fila in enumerate(h["rows"]):
            if msg.startswith(prefijo(fila)):
                return problemas.celda(hojas, hoja_, columna, i), fila[j]
        return None
    return f


def _concepto(clave: str):
    """Fila de la hoja 10 (Efectivo auditado y ajuste) donde se calcula el concepto."""
    def f(hojas, e):
        i = CONCEPTOS.index(clave)
        h = next(x for x in hojas if x["name"] == "10_Efectivo_auditado")
        return problemas.celda(hojas, "10_Efectivo_auditado", "Importe", i), h["rows"][i][1]
    return f


# De qué celda sale el importe de cada problema.
REF_PROBLEMAS = {
    "SIN_ESTADO_BANCARIO": _por_fila("03_Conciliacion", "Saldo según libros", _CUENTA),         # saldo en libros sin conciliar
    "DIFERENCIA_NO_EXPLICADA": _por_fila("03_Conciliacion", "Diferencia no explicada", _CUENTA),  # libros − saldo explicado
    "SIN_CONFIRMACION": _por_fila("03_Conciliacion", "Saldo según libros", _CUENTA),            # saldo en libros sin confirmar
    "CONFIRMACION_NO_COINCIDE": _por_fila("06_Confirmaciones", "Diferencia (confirmado − estado)", _CUENTA),  # confirmado − estado
    "SALDO_ACREEDOR": _por_fila("03_Conciliacion", "Saldo según libros", _CUENTA),              # sobregiro en libros
    "RESTRINGIDO_REVELAR": _por_fila("08_Restringido", "Monto restringido", _CUENTA),           # monto no disponible a revelar
    "RESTRINGIDO_COMO_DISPONIBLE": _por_fila("08_Restringido", "Reclasificación propuesta", _CUENTA),  # a no corriente
    "RESTRICCION_SIN_FECHA": _por_fila("08_Restringido", "Monto restringido", _CUENTA),         # monto sin fecha de fin
    "INVERSION_SIN_FECHAS": _por_fila("03_Conciliacion", "Saldo según libros", _CUENTA),        # inversión sin evaluar
    "NO_ES_EQUIVALENTE": _por_fila("09_Equivalentes", "Reclasificación propuesta", _CUENTA),    # reclasificación a inversiones
    "EQUIVALENTE_PRESUNCION": _por_fila("03_Conciliacion", "Saldo según libros", _CUENTA),      # inversión a documentar
    "NOTAS_NO_REGISTRADAS": _concepto("notas"),                                                  # notas de crédito − débito
    "PARTIDA_SIN_CUENTA": _por_fila("04_Partidas", "Importe", _PARTIDA),                         # partida sin cuenta en el anexo
    "PARTIDA_ANTIGUA": _por_fila("04_Partidas", "Importe", _PARTIDA),                            # partida antigua
    "PARTIDA_NO_DEPURADA": _por_fila("04_Partidas", "Importe", _PARTIDA),                        # partida sin liquidación
    "CORTE_POSTERIOR": _por_fila("07_Corte", "Importe", _PARTIDA),                               # partida posterior al corte
    "CORTE_DEPOSITO_TARDIO": _por_fila("07_Corte", "Importe", _PARTIDA),                         # depósito acreditado tarde
    "OTRA_PARTIDA": _por_fila("04_Partidas", "Importe", _PARTIDA),                               # partida sin naturaleza
}


# --- papel real DA (7 cédulas calcadas al papel del cliente) --------------------------

def _cedulas_da(res: dict, cu: list, pa: list, fila_cta: dict, corte_cell: str) -> list[dict]:
    """Las 7 cédulas del papel real DA (Libro Mayor fuente, Sumaria, Movimiento,
    Conciliaciones, Partidas, Arqueo y Hallazgos), calcadas al papel del cliente
    LANSEY con FÓRMULAS VIVAS y referencias cruzadas entre pestañas (la Sumaria es la
    fuente de saldos que citan las demás; DA-3 suma las partidas de DA-4 por SUMIFS;
    DA-2 pivota el Libro Mayor por SUMIF; DA-5 recuenta por denominación). Se llenan al
    Procesar, igual que las cédulas de cálculo, y bajan también en «Papel formulado (DA)»."""
    d = res["detalle"]
    lm, arq = d.get("libro_mayor") or [], d.get("arqueo") or []
    nombre_cta = {_clave(c["id"]): c["nombre"] for c in cu}
    banco_de = lambda cod: nombre_cta.get(_clave(cod), str(cod or ""))
    ncu, npa, nlm = len(cu), len(pa), len(lm)

    # DA-0 · Libro Mayor (fuente cruda de RQ-009; DA-2 hace SUMIF sobre ella).
    lm_rows = [[str(f.get("cuenta", "") or ""), str(f.get("descripcion", "") or ""), f.get("fecha") or None,
                str(f.get("comprobante", "") or ""), str(f.get("detalle", "") or ""), str(f.get("tercero", "") or ""),
                n2(num(f.get("debito"))), n2(num(f.get("credito")))] for f in lm]
    da0 = hoja(DA_LM, "DA · Libro Mayor (fuente)",
               [["Cuenta", "t"], ["Descripción", "t"], ["Fecha", "d"], ["Comprobante", "t"], ["Detalle", "t"],
                ["Tercero", "t"], ["Débitos", "n"], ["Créditos", "n"]], lm_rows,
               guia="Documento RQ-009 · Libro mayor (auxiliar de bancos) del período. Fuente del Movimiento (DA-2).")

    # DA-1 · Sumaria (saldo por cuenta; fuente de los saldos que citan DA-2, DA-3 y DA-5).
    sum_rows, ant_t = [], sum(num(c.get("anterior")) for c in cu)
    for i, c in enumerate(cu):
        r = FILA0 + i
        ant = num(c.get("anterior"))
        sum_rows.append([c["id"], c["nombre"], n2(ant), fx(f"E{r}-C{r}", n2(c["libros"] - ant)), n2(c["libros"]), "DA-3"])
    fin_s = FILA0 + ncu - 1
    da1 = hoja(DA_SUM, "DA-1 · Sumaria",
               [["Cuenta", "t"], ["Descripción", "t"], ["Saldo s/registros anterior", "n"], ["Variación", "n"],
                ["Saldo s/registros actual", "n"], ["Ref.", "t"]], sum_rows,
               ["TOTAL EFECTIVO Y EQUIVALENTES", "", suma("C", fin_s, ant_t),
                suma("D", fin_s, sum(c["libros"] for c in cu) - ant_t), suma("E", fin_s, sum(c["libros"] for c in cu)), ""],
               explica=EXPLICA["DA1_Sumaria"])

    # DA-2 · Movimiento de bancos (pivot del Libro Mayor por SUMIF; cuadre contra la Sumaria).
    mov_rows, deb_t, cred_t = [], 0.0, 0.0
    lma, lmg, lmh = _rango(LM_, "A", nlm), _rango(LM_, "G", nlm), _rango(LM_, "H", nlm)
    for i, c in enumerate(cu):
        r = FILA0 + i
        mias = [f for f in lm if _clave(f.get("cuenta")) == _clave(c["id"])]
        deb, cred = sum(num(f.get("debito")) for f in mias), sum(num(f.get("credito")) for f in mias)
        deb_t, cred_t = deb_t + deb, cred_t + cred
        mov_rows.append([c["id"], c["nombre"], n2(0.0),
                         fx(f"SUMIF({lma},A{r},{lmg})", n2(deb)), fx(f"SUMIF({lma},A{r},{lmh})", n2(cred)),
                         fx(f"C{r}+D{r}-E{r}", n2(deb - cred)), fx(f"F{r}-{SUM_}E{FILA0 + i}", n2(deb - cred - c["libros"]))])
    fin_m = FILA0 + ncu - 1
    da2 = hoja(DA_MOV, "DA-2 · Movimiento de bancos",
               [["Código", "t"], ["Cuenta", "t"], ["Saldo inicial", "n"], ["Débitos del período", "n"],
                ["Créditos del período", "n"], ["Saldo final s/movimiento", "n"], ["Cuadre s/Sumaria", "n"]], mov_rows,
               ["TOTAL", "", suma("C", fin_m, 0.0), suma("D", fin_m, deb_t), suma("E", fin_m, cred_t),
                suma("F", fin_m, deb_t - cred_t), suma("G", fin_m, deb_t - cred_t - sum(c["libros"] for c in cu))],
               explica=EXPLICA["DA2_Movimiento"])

    # DA-4 · Partidas conciliatorias (antes de DA-3, que la referencia por SUMIFS).
    par_rows = []
    for i, x in enumerate(pa):
        r = FILA0 + i
        presc = ""
        if x["origen"]:
            od = fecha(x["origen"])
            presc = (od + timedelta(days=390)).isoformat() if od else ""
        par_rows.append([x["origen"] or None, banco_de(x["cuenta"]), _TIPO_A_DACAT.get(x["tipo"], DA_SOBREGIRO),
                         x["ref"] or None, x["ref"] or None, n2(x["importe"]),
                         fx(f'IF(A{r}="","",{corte_cell}-A{r})', x["diasCorte"] if x["diasCorte"] is not None else ""),
                         fx(f'IF(A{r}="","",A{r}+390)', presc), x["corte"]])
    fin_p = FILA0 + npa - 1
    da4 = hoja(DA_PAR, "DA-4 · Partidas conciliatorias",
               [["Fecha", "d"], ["Banco", "t"], ["Tipo conciliatorio", "t"], ["Documento", "t"], ["Beneficiario", "t"],
                ["Valor", "n"], ["Días vencidos", "i"], ["Fecha de prescripción", "d"], ["Observación", "t"]], par_rows,
               ["TOTAL", "", "", "", "", suma("F", fin_p, sum(x["importe"] for x in pa)), None, None, ""] if npa else None,
               explica=EXPLICA["DA4_Partidas"])

    # DA-3 · Conciliaciones bancarias (extracto ± partidas de DA-4; cuadre contra la Sumaria).
    conf = [c for c in cu if c["tipo"] != CAJA]
    pb, pt, pv = _rango(PAR_DA, "B", npa), _rango(PAR_DA, "C", npa), _rango(PAR_DA, "F", npa)
    con_rows = []
    for i, c in enumerate(conf):
        r = FILA0 + i
        mias = [x for x in pa if _clave(x["cuenta"]) == _clave(c["id"])]
        vals = {cat: sum(x["importe"] for x in mias if _TIPO_A_DACAT.get(x["tipo"]) == cat)
                for cat in (DA_CONSIG, DA_SOBREGIRO, DA_CHEQUE, DA_ND, DA_NC)}
        sc = lambda cat: fx(f'SUMIFS({pv},{pb},A{r},{pt},"{cat}")', n2(vals[cat]))
        extr = c["banco"]
        audit = (extr or 0) + vals[DA_CONSIG] - vals[DA_SOBREGIRO] - vals[DA_CHEQUE] + vals[DA_ND] - vals[DA_NC]
        con_rows.append([c["nombre"], c["tipo"], c["id"], "" if extr is None else n2(extr),
                         sc(DA_CONSIG), sc(DA_SOBREGIRO), sc(DA_CHEQUE), sc(DA_ND), sc(DA_NC),
                         fx(f"D{r}+E{r}-F{r}-G{r}+H{r}-I{r}", n2(audit)), fx(f"{SUM_}E{fila_cta[c['id']]}", n2(c["libros"])),
                         fx(f"J{r}-K{r}", n2(audit - c["libros"]))])
    fin_c = FILA0 + len(conf) - 1
    da3 = hoja(DA_CON, "DA-3 · Conciliaciones bancarias",
               [["Banco", "t"], ["Tipo de cuenta", "t"], ["N° cuenta", "t"], ["Saldo extracto", "n"],
                ["(+) Consignaciones no registradas", "n"], ["(−) Sobregiro / ajustes", "n"], ["(−) Cheques sin cobrar", "n"],
                ["(+) Nota débito en tránsito", "n"], ["(−) NC pendiente de contabilizar", "n"], ["Saldo s/auditoría", "n"],
                ["Saldo s/registros contables", "n"], ["Diferencia", "n"]], con_rows,
               ["TOTAL", "", "", suma("D", fin_c, sum(c["banco"] or 0 for c in conf)),
                suma("E", fin_c, sum(x["importe"] for x in pa if _TIPO_A_DACAT.get(x["tipo"]) == DA_CONSIG)),
                suma("F", fin_c, sum(x["importe"] for x in pa if _TIPO_A_DACAT.get(x["tipo"]) == DA_SOBREGIRO)),
                suma("G", fin_c, sum(x["importe"] for x in pa if _TIPO_A_DACAT.get(x["tipo"]) == DA_CHEQUE)),
                suma("H", fin_c, sum(x["importe"] for x in pa if _TIPO_A_DACAT.get(x["tipo"]) == DA_ND)),
                suma("I", fin_c, sum(x["importe"] for x in pa if _TIPO_A_DACAT.get(x["tipo"]) == DA_NC)),
                suma("J", fin_c, 0.0), suma("K", fin_c, sum(c["libros"] for c in conf)), suma("L", fin_c, 0.0)] if conf else None,
               explica=EXPLICA["DA3_Conciliaciones"], colores=[])

    # DA-5 · Arqueo de caja (recuento por denominación; diferencia contra el saldo de caja de la Sumaria).
    if arq:
        denoms = [(str(a.get("denominacion", "") or ""), num(a.get("cantidad")), num(a.get("valor_unitario"))) for a in arq]
    else:
        denoms = [(nom, 0.0, val) for nom, val in DA_DENOMS]
    nden = len(denoms)
    arq_rows = [[nom, n2(cant), n2(vu), fx(f"B{FILA0 + i}*C{FILA0 + i}", n2(cant * vu))]
                for i, (nom, cant, vu) in enumerate(denoms)]
    total_arq = sum(cant * vu for _, cant, vu in denoms)
    caja_filas = [FILA0 + i for i, c in enumerate(cu) if c["tipo"] == CAJA]
    saldo_caja = sum(c["libros"] for c in cu if c["tipo"] == CAJA)
    caja_f = "+".join(f"{SUM_}E{rr}" for rr in caja_filas) if caja_filas else "0"
    r_tot, r_lib = FILA0 + nden, FILA0 + nden + 1
    arq_rows += [["TOTAL ARQUEO", None, None, fx(f"SUM(D{FILA0}:D{FILA0 + nden - 1})", n2(total_arq))],
                 ["Saldo de caja según libros (DA-1)", None, None, fx(caja_f, n2(saldo_caja))],
                 ["Diferencia (arqueo − libros)", None, None, fx(f"D{r_tot}-D{r_lib}", n2(total_arq - saldo_caja))]]
    da5 = hoja(DA_ARQ, "DA-5 · Arqueo de caja",
               [["Denominación", "t"], ["Cantidad", "i"], ["Valor unitario", "n"], ["Total", "n"]], arq_rows,
               explica=EXPLICA["DA5_Arqueo"], estilos=[None] * nden + [{"tipo": "total"}] * 3)

    # DA-6 · Hoja de hallazgos (los problemas del cálculo, uno por fila).
    da6 = hoja(DA_HAL, "DA-6 · Hoja de hallazgos",
               [["No.", "i"], ["Observación", "t"], ["Referencia de PT", "t"], ["Recomendación", "t"]],
               [[i + 1, e.get("message", ""), "DA-1", ""] for i, e in enumerate(res.get("exceptions") or [])])

    return [da0, da1, da2, da3, da4, da5, da6]


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, rf, con = d["parametros"], d["refs"], d["conceptos"]
    cu, pa = d["cuentas"], d["partidas"]
    nc_, np_ = len(cu), len(pa)
    corte, dant, dcor = f"{P}$B${PAR['corte']}", f"{P}$B${PAR['diasAntiguedad']}", f"{P}$B${PAR['diasCorte']}"
    meses_eq, meses, tol = f"{P}$B${PAR['mesesEquivalente']}", f"{P}$B${PAR['mesesRestriccion']}", f"{P}$B${PAR['tolerancia']}"
    fila_cta = {c["id"]: FILA0 + i for i, c in enumerate(cu)}
    restr = [c for c in cu if c["restr"]]
    inv = [c for c in cu if c["tipo"] == INV]
    conf = [c for c in cu if c["tipo"] != CAJA]
    nr, ni, nf = len(restr), len(inv), len(conf)
    pc = lambda col: _rango(PAR_, col, np_)
    cc = lambda col: _rango(CON_, col, nc_)

    parametros = [
        ["Fecha de corte", d["corte"], "Ficha del encargo"],
        ["Partida antigua desde (días al corte)", p["diasAntiguedad"], "Juicio del auditor (antigüedad de partidas conciliatorias)"],
        ["Días para que el banco acredite un depósito en tránsito", p["diasCorte"], "Juicio del auditor (prueba de corte, NIA 240 párr. 31 y Anexo 2)"],
        ["Plazo de un equivalente (meses desde la adquisición)", p["mesesEquivalente"], f"{rf['def']}: «tres meses o menos desde la fecha de adquisición» (presunción: la definición exige además gran liquidez y riesgo poco significativo de cambios de valor)"],
        ["Meses de restricción que la hacen no corriente", p["mesesRestriccion"], f"{rf['restr']}{rf['ifrs18']}"],
        ["Tolerancia de diferencias (USD)", p["tolerancia"], "Juicio del auditor; 0 = toda diferencia se reporta"],
        ["Marco del encargo", rf["marco"], "El cálculo es el mismo en ambos marcos; cambian las referencias citadas"],
        ["Definición de equivalentes", rf["def"], "Inversión a corto plazo, gran liquidez, riesgo poco significativo de cambios de valor"],
        ["Composición y conciliación con el estado de situación", rf["comp"], "Revelar componentes y política de composición"],
        ["Límite de la restricción (corte + meses)", d["limiteRestriccion"], "EDATE(corte; meses): después de esta fecha → no corriente"],
    ]

    # 04 · Partidas conciliatorias.
    partidas = []
    for i, x in enumerate(pa):
        r = FILA0 + i
        partidas.append([x["id"], x["cuenta"], x["tipo"], x["ref"], x["origen"] or None, n2(x["importe"]), x["liq"] or None,
                         fx(f'IF(E{r}="","",{corte}-E{r})', x["diasCorte"]),
                         fx(f'IF(OR(G{r}="",E{r}=""),"",G{r}-E{r})', x["diasLiq"]),
                         fx(f'IF(H{r}="","No",IF(H{r}>{dant},"Sí","No"))', "Sí" if x["antigua"] else "No"),
                         fx(f'IF(G{r}="","No","Sí")', "Sí" if x["depurada"] else "No"),
                         fx(f'IF(COUNTIF({cc("A")},B{r})>0,"Sí","No")', "Sí" if x["existe"] else "No")])
    fin_p = FILA0 + np_ - 1

    # 03 · Conciliación por cuenta.
    concil = []
    for i, c in enumerate(cu):
        r = FILA0 + i
        s = lambda t, v: fx(f'SUMIFS({pc("F")},{pc("B")},A{r},{pc("C")},"{t}")', n2(v))
        concil.append([c["id"], c["nombre"], c["tipo"], n2(c["banco"]), s(DT, c["dt"]), s(CP, c["cp"]), s(NC, c["nc"]), s(ND, c["nd"]), s(OT, c["ot"]),
                       fx(f'IF(D{r}="","",D{r}+E{r}-F{r}-G{r}+H{r}+I{r})', n2(c["esperado"])), n2(c["libros"]),
                       fx(f'IF(J{r}="","",ROUND(K{r}-J{r},2))', c["dif"]), fx(f"K{r}+G{r}-H{r}", n2(c["ajustado"])),
                       fx(f"M{r}-SUMIF({_rango(RES_, 'A', nr)},A{r},{_rango(RES_, 'I', nr)})-SUMIF({_rango(EQU_, 'A', ni)},A{r},{_rango(EQU_, 'I', ni)})",
                          n2(c["auditado"])),
                       fx(f'IF(L{r}="","",IF(ABS(L{r})>=0.005,"Alerta","Conforme"))',
                          "" if c["dif"] is None else ("Alerta" if abs(c["dif"]) >= 0.005 else "Conforme"))])
    fin_c = FILA0 + nc_ - 1

    # 05 · Antigüedad.
    antig = []
    for i, ((et, a, b), (lo, hi)) in enumerate(zip(TRAMOS, TRAMOS_PY)):
        crit = f'{pc("H")},{a}' + (f',{pc("H")},{b}' if b else "")
        en = [x for x in pa if x["diasCorte"] is not None and (lo is None or x["diasCorte"] >= lo) and
              (hi is None or x["diasCorte"] <= hi) and (lo is not None or x["diasCorte"] < 0)]
        antig.append([et, fx(f"COUNTIFS({crit})", len(en)), fx(f'SUMIFS({pc("F")},{crit})', n2(sum(x["importe"] for x in en))),
                      fx(f'SUMIFS({pc("F")},{crit},{pc("K")},"No")', n2(sum(x["importe"] for x in en if not x["depurada"])))])
    fin_a = FILA0 + len(TRAMOS) - 1

    # 06 · Confirmaciones.
    confir = []
    for i, c in enumerate(conf):
        r, rc = FILA0 + i, fila_cta[c["id"]]
        confir.append([c["id"], c["nombre"], fx(f'IF({CON_}D{rc}="","",{CON_}D{rc})', n2(c["banco"])), n2(c["conf"]),
                       fx(f'IF(OR(C{r}="",D{r}=""),"",ROUND(D{r}-C{r},2))', c["difConf"]),
                       fx(f'IF(D{r}="","Sin respuesta: procedimiento alternativo",IF(E{r}="","Sin estado bancario",'
                          f'IF(ABS(E{r})<={tol},"Coincide","No coincide")))', c["estadoConf"])])

    # 07 · Corte (depósitos en tránsito y cheques pendientes, más cualquier partida posterior al corte).
    corte_filas = []
    sel = [(i, x) for i, x in enumerate(pa) if x["tipo"] in (DT, CP) or x["corte"] == "Registrada después del corte"]
    for j, (i, x) in enumerate(sel):
        r, rp = FILA0 + j, FILA0 + i
        corte_filas.append([x["id"], x["cuenta"], x["tipo"], x["origen"] or None, x["liq"] or None,
                            fx(f'IF(E{r}="","",E{r}-{corte})', x["diasPost"]),
                            fx(f'IF(AND(D{r}<>"",D{r}>{corte}),"Registrada después del corte",IF(E{r}="","Sin liquidación posterior",'
                               f'IF(AND(C{r}="{DT}",F{r}>{dcor}),"Depósito acreditado tarde","Correcto")))', x["corte"]),
                            fx(f"{PAR_}F{rp}", n2(x["importe"]))])
    fin_k = FILA0 + len(sel) - 1

    # 08 · Restringido.
    restringido = []
    for i, c in enumerate(restr):
        r, rc = FILA0 + i, fila_cta[c["id"]]
        restringido.append([c["id"], c["nombre"], fx(f"{CON_}M{rc}", n2(c["ajustado"])), n2(c["monto"]), c["motivo"], c["fin"] or None,
                            fx(f'IF(F{r}="","Sin fecha de fin: revisar el soporte",IF(F{r}>=EDATE({corte},{meses}),"No corriente","Corriente"))', c["clasif"]),
                            "Sí" if c["sep"] else "No",
                            fx(f'IF(OR(H{r}="Sí",G{r}<>"No corriente"),0,IF(D{r}="","",D{r}))', n2(c["reclasR"]))])
    fin_r = FILA0 + nr - 1

    # 09 · Equivalentes.
    equiv = []
    for i, c in enumerate(inv):
        r, rc = FILA0 + i, fila_cta[c["id"]]
        equiv.append([c["id"], c["nombre"], c["adq"] or None, c["venc"] or None, fx(f'IF(OR(C{r}="",D{r}=""),"",D{r}-C{r})', c["plazo"]),
                      fx(f'IF(OR(C{r}="",D{r}=""),"Sin fechas: revisar el soporte",IF(D{r}<=EDATE(C{r},{meses_eq}),"Sí","No"))', c["califica"]),
                      fx(f"{CON_}M{rc}", n2(c["ajustado"])),
                      fx(f"SUMIF({_rango(RES_, 'A', nr)},A{r},{_rango(RES_, 'I', nr)})", n2(c["reclasR"] or 0)),
                      fx(f'IF(F{r}="No",MAX(G{r}-H{r},0),0)', n2(c["reclasNE"]))])
    fin_e = FILA0 + ni - 1

    # 10 · Efectivo auditado (orden CONCEPTOS).
    sum_o_cero = lambda h, col, n: f"SUM({_rango(h, col, n)})" if n else "0"
    formulas = {
        "saldoLibros": f"SUM({cc('K')})", "nc": f"SUM({cc('G')})", "nd": f"SUM({cc('H')})", "notas": f"{FC['nc']}-{FC['nd']}",
        "reclasRestringido": sum_o_cero(RES_, "I", nr),
        "reclasNoCorriente": f'SUMIF({_rango(RES_, "G", nr)},"No corriente",{_rango(RES_, "I", nr)})' if nr else "0",
        "reclasNoEquivalentes": sum_o_cero(EQU_, "I", ni),
        "auditado": f"{FC['saldoLibros']}+{FC['notas']}-{FC['reclasRestringido']}-{FC['reclasNoEquivalentes']}",
        "ajuste": f"{FC['auditado']}-{FC['saldoLibros']}",
        "caja": f'SUMIF({cc("C")},"{CAJA}",{cc("N")})', "bancos": f'SUMIF({cc("C")},"{BANCO}",{cc("N")})',
        "equivalentes": f'SUMIF({cc("C")},"{INV}",{cc("N")})',
        "difNoExplicada": _pos(cc("L")), "difConfirmacion": _pos(_rango(CNF_, "E", nf)) if nf else "0",
        "partidasAntiguas": f'SUMIF({pc("J")},"Sí",{pc("F")})', "partidasNoDepuradas": f'SUMIF({pc("K")},"No",{pc("F")})',
    }
    textos = {
        "saldoLibros": "Efectivo y equivalentes según libros", "nc": "Notas de crédito no registradas en libros",
        "nd": "Notas de débito no registradas en libros", "notas": "Ajuste por notas bancarias (crédito − débito)",
        "reclasRestringido": f"(−) Reclasificación a no corriente (restricción ≥ 12 meses) ({rf['restr']})",
        "reclasNoCorriente": "    de lo cual, no corriente",
        "reclasNoEquivalentes": f"(−) Inversiones que no cumplen el plazo de tres meses ({rf['def']})", "auditado": "Efectivo y equivalentes auditado",
        "ajuste": "Ajuste propuesto (auditado − libros)", "caja": f"Composición ({rf['comp']}): caja",
        "bancos": "Composición: bancos (incluye sobregiros)", "equivalentes": "Composición: equivalentes de efectivo",
        "difNoExplicada": "Diferencias de conciliación no explicadas (absolutas)", "difConfirmacion": "Diferencias de confirmación (absolutas)",
        "partidasAntiguas": "Partidas conciliatorias antiguas", "partidasNoDepuradas": "Partidas no depuradas después del corte",
    }
    auditado = [[textos[k], fx(formulas[k], n2(con[k]))] for k in CONCEPTOS]
    # Estilos de cédula sumaria del estado «Efectivo auditado» (una entrada por concepto de CONCEPTOS):
    # las notas bancarias y su subtotal, las reclasificaciones (con «de lo cual» sangrado), el efectivo
    # auditado y el ajuste como subtotales, y la composición (caja/bancos/equivalentes) sangrada.
    _est_sang = {"sangria": 1, "col": "Concepto"}
    _estilos_auditado = {
        "nc": _est_sang, "nd": _est_sang, "notas": {"tipo": "total"},
        "reclasNoCorriente": _est_sang, "auditado": {"tipo": "total"}, "ajuste": {"tipo": "total"},
        "caja": _est_sang, "bancos": _est_sang, "equivalentes": _est_sang,
    }
    estilos_auditado = [_estilos_auditado.get(k) for k in CONCEPTOS]

    # 11 · Asientos.
    asientos = []

    def asiento(titulo, lineas):
        vivas = [x for x in lineas if abs(x[3]) > 0.005]
        for i, (cta, lado, f, v) in enumerate(vivas):
            celda = fx(f, n2(v))
            asientos.append([titulo if i == 0 else "", cta, celda if lado == "d" else None, celda if lado == "h" else None])

    asiento("1 · Notas de crédito del banco no registradas", [("Bancos", "d", FC["nc"], con["nc"]),
                                                            ("Otros ingresos (identificar la cuenta con el soporte)", "h", FC["nc"], con["nc"])])
    asiento("2 · Notas de débito del banco no registradas", [("Gastos bancarios (identificar la cuenta con el soporte)", "d", FC["nd"], con["nd"]),
                                                           ("Bancos", "h", FC["nd"], con["nd"])])
    rc = con["reclasRestringido"] - con["reclasNoCorriente"]
    asiento("3 · Reclasificación del efectivo restringido a no corriente", [
        ("Efectivo restringido — activo no corriente", "d", FC["reclasNoCorriente"], con["reclasNoCorriente"]),
        ("Efectivo restringido — corriente o por clasificar", "d", f"{FC['reclasRestringido']}-{FC['reclasNoCorriente']}", rc),
        ("Efectivo y equivalentes de efectivo", "h", FC["reclasRestringido"], con["reclasRestringido"])])
    asiento("4 · Reclasificación de inversiones que no son equivalentes", [
        ("Inversiones a plazo (activos financieros a costo amortizado)", "d", FC["reclasNoEquivalentes"], con["reclasNoEquivalentes"]),
        ("Efectivo y equivalentes de efectivo", "h", FC["reclasNoEquivalentes"], con["reclasNoEquivalentes"])])

    fila_con = {k: FILA0 + i for i, k in enumerate(CONCEPTOS)}
    resumen = [[res["labels"][k], fx(f"{AUD}B{fila_con[k]}", n2(float(res["totals"][k])))] for k in res["labels"]]
    tot = lambda col, fin, v: suma(col, fin, n2(v))

    # 13 · Indicadores y conclusión (con semáforo coloreable en «Estado»).
    PROB = ref("12_Problemas")
    nprob = len(res["exceptions"])
    libros_v, auditado_v, ajuste_v = con["saldoLibros"], con["auditado"], con["ajuste"]
    dif_v = con["difNoExplicada"]
    reclas_v = con["reclasRestringido"] + con["reclasNoEquivalentes"]
    tol_n = p["tolerancia"]
    pct_v = None if libros_v == 0 else abs(ajuste_v) / libros_v
    fA, fR, fD = FILA0 + 2, FILA0 + 3, FILA0 + 4  # filas ajuste, %, diferencia (para referencias internas)
    fRec, fPr = FILA0 + 5, FILA0 + 6              # filas reclasificación y problemas
    est = lambda cond, alto, ok="Conforme": (alto if cond else ok)
    conclusion = [
        ["Efectivo y equivalentes auditado (resultado principal)", fx(FC["auditado"], n2(auditado_v)), None, None,
         fx(f'IF(ABS(B{fA})>{tol},"Revisar","Conforme")', est(abs(ajuste_v) > tol_n, "Revisar"))],
        ["Efectivo y equivalentes según libros (registrado)", fx(FC["saldoLibros"], n2(libros_v)), None, None, ""],
        ["Ajuste propuesto (auditado − libros)", fx(FC["ajuste"], n2(ajuste_v)), None, None,
         fx(f'IF(ABS(B{fA})>{tol},"Alerta","Conforme")', est(abs(ajuste_v) > tol_n, "Alerta"))],
        ["% de ajuste sobre el efectivo según libros", None,
         fx(f'IF({FC["saldoLibros"]}=0,"",ABS({FC["ajuste"]})/{FC["saldoLibros"]})', pct_v), None,
         fx(f'IF(C{fR}="","",IF(ABS({FC["ajuste"]})>{tol},"Revisar","Conforme"))',
            "" if pct_v is None else est(abs(ajuste_v) > tol_n, "Revisar"))],
        ["Diferencias de conciliación no explicadas (absolutas)", fx(FC["difNoExplicada"], n2(dif_v)), None, None,
         fx(f'IF(B{fD}>{tol},"Alerta","Conforme")', est(dif_v > tol_n, "Alerta"))],
        ["Reclasificaciones propuestas (restringido no corriente e inversiones que no son equivalentes)",
         fx(f'{FC["reclasRestringido"]}+{FC["reclasNoEquivalentes"]}', n2(reclas_v)), None, None,
         fx(f'IF(B{fRec}>0.005,"Revisar","Conforme")', est(reclas_v > 0.005, "Revisar"))],
        ["Problemas encontrados", None, None, fx(f"COUNTA({_rango(PROB, 'A', nprob)})", nprob),
         fx(f'IF(D{fPr}>0,"Revisar","Conforme")', est(nprob > 0, "Revisar"))],
    ]

    # 14 · Lectura de resultados (causa-efecto con las cifras embebidas por FIXED, hoja 10).
    difConf_v, antiguas_v = con["difConfirmacion"], con["partidasAntiguas"]
    _fix = lambda cell: f"FIXED({cell},2)"
    aj_dir = "disminuye" if ajuste_v < -0.005 else ("aumenta" if ajuste_v > 0.005 else "no modifica")
    aj_dir_f = f'IF({FC["ajuste"]}<-0.005,"disminuye",IF({FC["ajuste"]}>0.005,"aumenta","no modifica"))'
    lectura = [
        ["Resultado principal",
         fx(f'"El efectivo y equivalentes auditado asciende a US$ "&{_fix(FC["auditado"])}&", frente a US$ "&{_fix(FC["saldoLibros"])}&" según libros (hoja 10)."',
            f"El efectivo y equivalentes auditado asciende a US$ {fmt_m(auditado_v)}, frente a US$ {fmt_m(libros_v)} según libros (hoja 10).")],
        ["Ajuste propuesto",
         fx(f'"El ajuste propuesto es de US$ "&{_fix(FC["ajuste"])}&" (auditado − saldo según libros), que "&{aj_dir_f}&" el efectivo y equivalentes presentado; su registro exige los asientos de la hoja 11."',
            f"El ajuste propuesto es de US$ {fmt_m(ajuste_v)} (auditado − saldo según libros), que {aj_dir} el efectivo y equivalentes presentado; su registro exige los asientos de la hoja 11.")],
        ["Diferencias de conciliación y confirmación",
         fx(f'"Las conciliaciones dejan US$ "&{_fix(FC["difNoExplicada"])}&" en diferencias no explicadas y US$ "&{_fix(FC["difConfirmacion"])}&" entre lo confirmado por el banco y el estado bancario; investíguelas y evalúelas como incorrecciones (NIA 450 y 505)."',
            f"Las conciliaciones dejan US$ {fmt_m(dif_v)} en diferencias no explicadas y US$ {fmt_m(difConf_v)} entre lo confirmado por el banco y el estado bancario; investíguelas y evalúelas como incorrecciones (NIA 450 y 505).")],
        ["Reclasificaciones",
         fx(f'"Se reclasifican US$ "&{_fix(FC["reclasRestringido"])}&" de efectivo restringido a no corriente y US$ "&{_fix(FC["reclasNoEquivalentes"])}&" de inversiones que no son equivalentes, lo que reduce el efectivo corriente disponible (NIC 1.66 d y NIC 7.7)."',
            f"Se reclasifican US$ {fmt_m(con['reclasRestringido'])} de efectivo restringido a no corriente y US$ {fmt_m(con['reclasNoEquivalentes'])} de inversiones que no son equivalentes, lo que reduce el efectivo corriente disponible (NIC 1.66 d y NIC 7.7).")],
        ["Cierre",
         fx(f'"Las partidas conciliatorias antiguas suman US$ "&{_fix(FC["partidasAntiguas"])}&"; en conjunto, los hallazgos exigen registrar los ajustes propuestos y ampliar las revelaciones de la nota de efectivo (NIC 7.45–7.46)."',
            f"Las partidas conciliatorias antiguas suman US$ {fmt_m(antiguas_v)}; en conjunto, los hallazgos exigen registrar los ajustes propuestos y ampliar las revelaciones de la nota de efectivo (NIC 7.45–7.46).")],
    ]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Conciliacion", "Conciliación bancaria por cuenta",
             [["Cuenta", "t"], ["Banco / caja", "t"], ["Tipo", "t"], ["Saldo estado bancario / arqueo", "n"], ["(+) Depósitos en tránsito", "n"],
              ["(−) Cheques pendientes", "n"], ["(−) Notas de crédito no registradas", "n"], ["(+) Notas de débito no registradas", "n"],
              ["(±) Otras partidas", "n"], ["Saldo que explica la conciliación", "n"], ["Saldo según libros", "n"],
              ["Diferencia no explicada", "n"], ["Saldo ajustado de libros", "n"], ["Efectivo auditado", "n"], ["Semáforo", "t"]], concil,
             ["TOTAL", "", "", None, tot("E", fin_c, sum(c["dt"] for c in cu)), tot("F", fin_c, sum(c["cp"] for c in cu)),
              tot("G", fin_c, con["nc"]), tot("H", fin_c, con["nd"]), tot("I", fin_c, sum(c["ot"] for c in cu)), None,
              tot("K", fin_c, con["saldoLibros"]), None, tot("M", fin_c, sum(c["ajustado"] for c in cu)), tot("N", fin_c, con["auditado"]), ""],
             explica=EXPLICA["03_Conciliacion"], colores=["Semáforo"]),
        hoja("04_Partidas", "Partidas conciliatorias",
             [["Partida", "t"], ["Cuenta", "t"], ["Tipo", "t"], ["Referencia", "t"], ["Fecha de origen", "d"], ["Importe", "n"],
              ["Liquidación posterior", "d"], ["Días al corte", "i"], ["Días hasta la liquidación", "i"], ["Antigua", "t"],
              ["Depurada", "t"], ["Cuenta en el anexo", "t"]], partidas,
             ["TOTAL", "", "", "", None, tot("F", fin_p, sum(x["importe"] for x in pa)), None, None, None, "", "", ""] if np_ else None,
             explica=EXPLICA["04_Partidas"]),
        hoja("05_Antiguedad", "Antigüedad de partidas",
             [["Tramo (días al corte)", "t"], ["Partidas", "i"], ["Importe", "n"], ["No depurado", "n"]], antig,
             ["TOTAL", fx(f"SUM(B{FILA0}:B{fin_a})", sum(1 for x in pa if x["diasCorte"] is not None)),
              tot("C", fin_a, sum(x["importe"] for x in pa if x["diasCorte"] is not None)),
              tot("D", fin_a, sum(x["importe"] for x in pa if x["diasCorte"] is not None and not x["depurada"]))],
             explica=EXPLICA["05_Antiguedad"]),
        hoja("06_Confirmaciones", "Confirmación bancaria",
             [["Cuenta", "t"], ["Banco", "t"], ["Saldo según estado bancario", "n"], ["Saldo confirmado por el banco", "n"],
              ["Diferencia (confirmado − estado)", "n"], ["Resultado", "t"]], confir, explica=EXPLICA["06_Confirmaciones"]),
        hoja("07_Corte", "Prueba de corte",
             [["Partida", "t"], ["Cuenta", "t"], ["Tipo", "t"], ["Fecha en libros", "d"], ["Fecha en el banco", "d"],
              ["Días después del corte", "i"], ["Resultado", "t"], ["Importe", "n"]], corte_filas,
             ["TOTAL", "", "", None, None, None, "", tot("H", fin_k, sum(x["importe"] for _, x in sel))] if sel else None,
             explica=EXPLICA["07_Corte"]),
        hoja("08_Restringido", "Efectivo restringido",
             [["Cuenta", "t"], ["Banco", "t"], ["Saldo ajustado", "n"], ["Monto restringido", "n"], ["Motivo", "t"], ["Fin de la restricción", "d"],
              ["Clasificación", "t"], ["Ya presentado aparte", "t"], ["Reclasificación propuesta", "n"]], restringido,
             ["TOTAL", "", None, None, "", None, "", "", tot("I", fin_r, con["reclasRestringido"])] if nr else None,
             explica=EXPLICA["08_Restringido"]),
        hoja("09_Equivalentes", "Equivalentes de efectivo (definición)",
             [["Cuenta", "t"], ["Instrumento", "t"], ["Adquisición", "d"], ["Vencimiento", "d"], ["Plazo original (días)", "i"],
              ["Vence en tres meses o menos (presunción)", "t"], ["Saldo ajustado", "n"], ["Ya reclasificado por restricción", "n"],
              ["Reclasificación propuesta", "n"]],
             equiv, ["TOTAL", "", None, None, None, "", tot("G", fin_e, sum(c["ajustado"] for c in inv)), None,
                     tot("I", fin_e, con["reclasNoEquivalentes"])] if ni else None, explica=EXPLICA["09_Equivalentes"]),
        hoja("10_Efectivo_auditado", "Efectivo auditado y ajuste", [["Concepto", "t"], ["Importe", "n"]], auditado,
             explica=EXPLICA["10_Efectivo_auditado"], estilos=estilos_auditado),
        hoja("11_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos,
             explica=EXPLICA["11_Asientos"]),
        hoja("12_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
        hoja("13_Conclusion", "Indicadores y conclusión",
             [["Indicador", "t"], ["Importe", "n"], ["Porcentaje", "p"], ["Cantidad", "i"], ["Estado", "t"]], conclusion,
             explica=EXPLICA["13_Conclusion"], colores=["Estado"]),
        hoja("14_Lectura", "Lectura de resultados", [["Concepto", "t"], ["Detalle", "t"]], lectura,
             explica=EXPLICA["14_Lectura"]),
        # Papel real DA (7 cédulas calcadas al papel del cliente, con fórmulas vivas y referencias cruzadas).
        *_cedulas_da(res, cu, pa, fila_cta, corte),
    ]


# --- definición (ficha CAJ) ----------------------------------------------------------------

def definicion() -> dict:
    return {
        "name": "Efectivo y equivalentes de efectivo",
        "area": "Caja y bancos",
        "processor": "efectivo_equivalentes",
        "frameworks": ["NIIF completas", "NIIF para las PYMES"],
        "summary": ("Reejecuta la conciliación bancaria de cada cuenta, analiza las partidas conciliatorias (antigüedad, depuración "
                    "posterior y corte), compara el saldo confirmado por el banco con el estado bancario y propone la reclasificación del "
                    "efectivo restringido de largo plazo y de las inversiones que no cumplen la definición de equivalentes de efectivo."),
        "source": {"organization": "IFRS Foundation · Reglamento (UE) 2023/1803", "type": "Norma contable", "date": "",
                   "document": "NIC 7 Estado de flujos de efectivo · párr. 6–8 (definiciones, sobregiros), 45 (componentes y conciliación), "
                               "46 (política de composición), 48–49 (saldos no disponibles); NIC 1 párr. 66 d) (restringido al menos doce meses: no corriente; "
                               "al corte 2025 aplica la NIC 1; la NIIF 18 rige para ejercicios desde el 1-1-2027 y el requisito pasa a su párr. 99 d)); NIIF 9 párr. 5.5.1; NIIF 7 párr. 35H–35M si el depósito exige medir pérdida esperada o revelar riesgo",
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": "NIIF para las PYMES 2015: Sección 7 párr. 7.2 (equivalentes y sobregiros), 7.20 (componentes y conciliación), "
                                     "7.21 (saldos no disponibles); Sección 4 párr. 4.5 d) (restringido no corriente); Sección 11 párr. 11.8 a) "
                                     "(efectivo, instrumento financiero básico). Edición 2025 (texto oficial en inglés): misma numeración — 4.5 d), 7.2, 7.20, 7.21 y 11.8 a).",
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 505", "section": "párr. 7 y 12",
             "requirement": "Confirmación bancaria bajo control del auditor; sin respuesta, procedimientos alternativos."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad de la información del cliente (conciliaciones y anexos)."},
            {"document": "NIA 330", "section": "párr. 20 a)", "requirement": "Conciliar los estados financieros con los registros contables."},
            {"document": "NIA 240", "section": "párr. 27, 31 y Anexo 2 (corte)", "requirement": "Corte y movimientos alrededor del cierre como riesgo de fraude (numeración del Manual IAASB 2023-2024; la NIA 240 revisada de 2025 cambia la numeración)."},
            {"document": "NIA 450", "section": "párr. 5 y 11", "requirement": "Acumular y evaluar las diferencias no explicadas y los ajustes."},
        ],
        "calculo": [
            "Conciliación por cuenta: saldo del estado bancario + depósitos en tránsito − cheques pendientes − notas de crédito no registradas "
            "+ notas de débito no registradas ± otras = saldo que deberían mostrar los libros; diferencia no explicada = libros − ese saldo.",
            "Saldo ajustado de libros = libros + notas de crédito − notas de débito no registradas (ajuste a libros).",
            "Partidas: días al corte = corte − fecha de origen; días hasta la liquidación = liquidación − origen; antigua si supera el parámetro; "
            "no depurada si no se liquidó después del corte.",
            "Corte: partida con origen posterior al corte, o depósito en tránsito acreditado más de N días después del corte.",
            "Confirmación: saldo confirmado por el banco − saldo del estado bancario (con tolerancia).",
            "Restringido: la restricción no saca el saldo del efectivo (NIC 7.48 / PYMES 7.21 solo exigen revelarlo y comentarlo). Se reclasifica a no corriente únicamente la parte cuya restricción termina en doce meses o más desde el corte (NIC 1.66 d / PYMES 4.5 d, «al menos doce meses»), salvo que ya se presente aparte; sin fecha de fin no se reclasifica nada y se pide la fecha.",
            "Equivalentes: la inversión cumple el plazo si vence en tres meses o menos desde la adquisición, EDATE(adquisición; 3) (NIC 7.7 / PYMES 7.2); si no, se reclasifica a inversiones. Cumplir el plazo es solo una presunción: la definición exige además gran liquidez y riesgo poco significativo de cambios de valor (NIC 7.6).",
            "Ajuste propuesto = efectivo auditado − saldo según libros.",
        ],
        "fields": _CUENTAS, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "CAJ-01", "objective": "Integridad y exactitud del saldo", "risk": "Cuentas omitidas o anexo no conciliado con el mayor",
             "assertion": "Integridad", "procedure": "Conciliar el anexo de cuentas con el mayor y el balance de comprobación",
             "evidence": "Anexo de cuentas, mayor, balance", "criterion": "Diferencia dentro de tolerancia", "source": "NIA 500 párr. 9 · NIC 7.45"},
            {"code": "CAJ-02", "objective": "Conciliación bancaria", "risk": "Diferencias sin explicar entre banco y libros", "assertion": "Existencia",
             "procedure": "Reejecutar la conciliación de cada cuenta con el estado bancario y las partidas conciliatorias",
             "evidence": "Conciliaciones y estados bancarios del mes de corte", "criterion": "Diferencia no explicada = 0",
             "source": "NIA 500 · NIA 330"},
            {"code": "CAJ-03", "objective": "Partidas conciliatorias y antigüedad", "risk": "Partidas antiguas o inexistentes que ocultan faltantes",
             "assertion": "Existencia", "procedure": "Cotejar cada partida con su liquidación en el estado bancario posterior y medir su antigüedad",
             "evidence": "Estados bancarios posteriores al corte", "criterion": "Partidas liquidadas y no antiguas", "source": "NIA 500 párr. 6 · NIA 330 párr. 18 (NIA 560 párr. 6 solo si la partida revela un hecho posterior)"},
            {"code": "CAJ-04", "objective": "Confirmación bancaria", "risk": "Saldos o productos no reales", "assertion": "Existencia / Derechos",
             "procedure": "Confirmar saldos, restricciones y garantías con cada banco bajo control del auditor",
             "evidence": "Respuestas de los bancos", "criterion": "Confirmado = estado bancario", "source": "NIA 505"},
            {"code": "CAJ-05", "objective": "Corte", "risk": "Ingresos o pagos registrados en el período incorrecto", "assertion": "Corte",
             "procedure": "Comparar fechas en libros y en el banco de depósitos en tránsito y cheques alrededor del cierre",
             "evidence": "Libro bancos y estados bancarios de diciembre y enero", "criterion": "Acreditación dentro de la ventana", "source": "NIA 240 párr. 31 y Anexo 2 · NIA 330"},
            {"code": "CAJ-06", "objective": "Efectivo restringido", "risk": "Efectivo no disponible presentado como disponible",
             "assertion": "Presentación", "procedure": "Identificar restricciones, garantías y embargos; clasificar y revelar",
             "evidence": "Contratos, respuestas bancarias, actas", "criterion": "Restringido revelado; no corriente el de al menos doce meses",
             "source": "NIC 7.48 · NIC 1.66 d) · PYMES 7.21 y 4.5 d)"},
            {"code": "CAJ-07", "objective": "Definición de equivalentes", "risk": "Inversiones de largo plazo presentadas como efectivo",
             "assertion": "Clasificación", "procedure": "Evaluar plazo desde la adquisición, liquidez y riesgo de cada inversión",
             "evidence": "Certificados y contratos de inversión", "criterion": "Vence en tres meses o menos desde la adquisición, con gran liquidez y riesgo poco significativo; si no, reclasificar",
             "source": "NIC 7.6–7.7 · PYMES 7.2"},
            {"code": "CAJ-08", "objective": "Presentación y revelación", "risk": "Composición y política no reveladas", "assertion": "Presentación",
             "procedure": "Cotejar la nota de efectivo con la composición auditada y la política de composición",
             "evidence": "Estados financieros y nota", "criterion": "Nota completa", "source": "NIC 7.45–7.46 · PYMES 7.20"},
        ],
        "requests": [
            req("RQ-001", "Anexo de cuentas de caja, bancos e inversiones al corte", "cuentas", "CAJ-01",
                "Población a auditar: saldo según libros, estado bancario, confirmación, restricciones y fechas de inversiones",
                content="Una fila por cuenta: código, banco/caja, tipo (Banco, Caja o Inversión), saldo según libros, saldo del estado bancario "
                        "(o arqueo), saldo confirmado, restringido, monto, motivo y fin de la restricción; fechas de adquisición y vencimiento de inversiones."),
            req("RQ-002", "Partidas conciliatorias de cada cuenta al corte", "partidas", "CAJ-02",
                "Reejecutar la conciliación, medir antigüedad, depuración y corte", required=False,
                content="Una fila por partida: N°, código de cuenta, tipo (depósito en tránsito, cheque pendiente, nota de crédito, nota de débito, otra), "
                        "referencia, fecha de origen, importe y fecha de liquidación en el estado bancario posterior."),
            req("RQ-003", "Conciliaciones y estados bancarios del mes de corte", None, "CAJ-02", "Soporte de saldos y partidas",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-004", "Estados bancarios posteriores al corte (ventana de depuración)", None, "CAJ-03", "Liquidación posterior de las partidas",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-005", "Respuestas de confirmación bancaria recibidas por el auditor", None, "CAJ-04", "Evidencia externa de saldos y restricciones",
                formats=("pdf",), use="soporte"),
            req("RQ-006", "Contratos de garantía, pignoración, embargos o fideicomisos", None, "CAJ-06", "Sustento del efectivo restringido",
                formats=("pdf", "docx"), use="soporte", required=False),
            req("RQ-007", "Certificados y contratos de inversiones presentadas como equivalentes", None, "CAJ-07", "Plazo, liquidez y riesgo",
                formats=("pdf",), use="soporte", required=False),
            req("RQ-008", "Política contable de efectivo y equivalentes y actas de arqueo", None, "CAJ-08", "Composición (NIC 7.46) y arqueos de caja",
                formats=("pdf", "docx"), use="soporte"),
            req("RQ-009", "Libro mayor (auxiliar de bancos) del período", "libro_mayor", "CAJ-01",
                "Cuadre de la Sumaria con el mayor y armado del movimiento del papel", required=False,
                content="Una fila por asiento del mayor de bancos: código de cuenta, fecha, comprobante, detalle, "
                        "tercero, débitos y créditos del período."),
            req("RQ-010", "Estado de cuenta bancario del mes (movimientos)", "estado_cuenta", "CAJ-02",
                "Reestructuración de la conciliación: se cruza con el libro mayor", required=False,
                content="Una fila por movimiento del estado de cuenta: código de cuenta, fecha, documento, "
                        "débitos (cargos del banco) y créditos (abonos del banco). Transcrito del PDF y revisado."),
            req("RQ-011", "Conciliación bancaria del mes anterior (partidas abiertas)", "conciliacion_anterior", "CAJ-03",
                "Arrastre de partidas conciliatorias no depuradas a la reestructuración", required=False,
                content="Una fila por partida abierta del mes anterior: código de cuenta, fecha de origen, tipo "
                        "conciliatorio, documento, valor y observación."),
            req("RQ-012", "Arqueo de caja (recuento por denominación)", "arqueo", "CAJ-01",
                "Recuento del efectivo en caja para la cédula de arqueo", required=False,
                content="Una fila por denominación contada: denominación, cantidad, valor unitario y observación."),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo numérico de control (M19) ---------------------------------------------------

def _c(id, nombre, tipo, libros, banco, conf="", **extra):
    return {"id": id, "nombre": nombre, "tipo": tipo, "moneda": "USD", "saldo_libros": libros, "saldo_banco": banco,
            "saldo_confirmado": conf, "_row": 2, **extra}


def _p(id, cuenta, tipo, origen, importe, liq="", ref_=""):
    return {"id": id, "cuenta": cuenta, "tipo": tipo, "referencia": ref_, "fecha_origen": origen, "importe": importe,
            "fecha_liquidacion": liq, "_row": 2}


# Pichincha: 131.210,50 + 8.500 − 12.000 − 1.850 − 300 (NC) + 120 (ND) = 125.680,50 = libros → sin diferencia;
#   saldo ajustado 125.680,50 + 300 − 120 = 125.860,50.
# Guayaquil: 45.900 + 2.100 − 300 − 550 = 47.150; libros 47.700 → diferencia no explicada 550,00.
#   Restricción de 10.000 hasta 2027-06-30 (>= 2026-12-31) → no corriente: se reclasifica.
# Produbanco confirma 21.500 frente a 22.000 del estado → −500. Internacional embargada (1.650) sin fecha de fin:
#   se revela pero NO se reclasifica (NIC 7.48 solo exige revelar).
# Certificado: adquirido el 2025-10-01 y vence el 2026-03-30, después de EDATE(2025-10-01;3) = 2026-01-01 → no es
#   equivalente (30.000). Efectivo auditado = 274.630,50 + 180 − 10.000 − 30.000 = 234.810,50.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"diasAntiguedad": 90, "diasCorte": 5, "mesesEquivalente": 3, "mesesRestriccion": 12, "tolerancia": 0},
    "datasets": {
        "cuentas": [
            _c("1.1.01.01", "Caja general", "Caja", "500.00", "500.00"),
            _c("1.1.01.02", "Caja chica", "Caja", "300.00", "300.00"),
            _c("1.1.02.01", "Banco Pichincha Cte. ***4521", "Banco", "125680.50", "131210.50", "131210.50"),
            _c("1.1.02.02", "Banco Guayaquil Aho. ***7788", "Banco", "47700.00", "45900.00", "45900.00", restringido="Sí",
               monto_restringido="10000.00", motivo_restriccion="Garantía de préstamo (pignoración)", fin_restriccion="2027-06-30",
               presentado_separado="No"),
            _c("1.1.02.03", "Produbanco Cte. ***3390", "Banco", "22000.00", "22000.00", "21500.00"),
            _c("1.1.02.04", "Banco Internacional Cte. ***1102", "Banco", "1650.00", "1200.00", "", restringido="Sí",
               monto_restringido="1650.00", motivo_restriccion="Embargo judicial", presentado_separado="No"),
            _c("1.1.02.05", "Banco Bolivariano Cte. ***5566", "Banco", "-3200.00", "-3200.00", "-3200.00"),
            _c("1.1.03.01", "Póliza de acumulación Pichincha 60 días", "Inversión", "50000.00", "50000.00", "50000.00",
               fecha_adquisicion="2025-11-15", fecha_vencimiento="2026-01-14"),
            _c("1.1.03.02", "Certificado de depósito Produbanco 180 días", "Inversión", "30000.00", "30000.00", "30000.00",
               fecha_adquisicion="2025-10-01", fecha_vencimiento="2026-03-30"),
        ],
        "partidas": [
            _p("P-01", "1.1.02.01", DT, "2025-12-30", "8500.00", "2026-01-02", "Depósito cobranza clientes"),
            _p("P-02", "1.1.02.01", CP, "2025-12-28", "12000.00", "2026-01-05", "Cheque 1520 proveedor"),
            _p("P-03", "1.1.02.01", CP, "2025-08-15", "1850.00", "", "Cheque 1311 anulado sin reversar"),
            _p("P-04", "1.1.02.01", ND, "2025-12-31", "120.00", "2026-01-10", "Comisiones bancarias diciembre"),
            _p("P-05", "1.1.02.01", NC, "2025-12-31", "300.00", "2026-01-10", "Intereses ganados diciembre"),
            _p("P-06", "1.1.02.02", DT, "2025-12-31", "2100.00", "2026-01-12", "Depósito en efectivo"),
            _p("P-07", "1.1.02.02", CP, "2025-12-20", "300.00", "2026-01-03", "Cheque 0870"),
            _p("P-08", "1.1.02.02", CP, "2026-01-02", "550.00", "2026-01-06", "Cheque 0876 fechado en enero"),
            _p("P-09", "1.1.02.04", DT, "2025-09-10", "450.00", "", "Depósito no acreditado"),
        ],
        "libro_mayor": [
            {"cuenta": "1.1.02.01", "descripcion": "Banco Pichincha Cte. ***4521", "fecha": "2025-12-05",
             "comprobante": "IN-1201", "detalle": "Depósito cobranza clientes", "tercero": "Clientes varios",
             "debito": "15000.00", "credito": "0.00"},
            {"cuenta": "1.1.02.01", "descripcion": "Banco Pichincha Cte. ***4521", "fecha": "2025-12-18",
             "comprobante": "CK-1520", "detalle": "Pago proveedor", "tercero": "Proveedor ABC S.A.",
             "debito": "0.00", "credito": "12000.00"},
            {"cuenta": "1.1.02.02", "descripcion": "Banco Guayaquil Aho. ***7788", "fecha": "2025-12-20",
             "comprobante": "CK-0870", "detalle": "Pago servicios", "tercero": "Servicios XYZ",
             "debito": "0.00", "credito": "300.00"},
            {"cuenta": "1.1.02.03", "descripcion": "Produbanco Cte. ***3390", "fecha": "2025-12-22",
             "comprobante": "IN-1330", "detalle": "Transferencia recibida", "tercero": "Cliente DEF",
             "debito": "5000.00", "credito": "0.00"},
            {"cuenta": "1.1.01.01", "descripcion": "Caja general", "fecha": "2025-12-31",
             "comprobante": "AJ-0012", "detalle": "Reposición caja", "tercero": "",
             "debito": "500.00", "credito": "0.00"},
        ],
        "estado_cuenta": [
            {"cuenta": "1.1.02.01", "fecha": "2025-12-05", "documento": "Depósito cobranza",
             "debito": "0.00", "credito": "15000.00"},
            {"cuenta": "1.1.02.01", "fecha": "2025-12-31", "documento": "Comisión mantenimiento",
             "debito": "120.00", "credito": "0.00"},
            {"cuenta": "1.1.02.02", "fecha": "2025-12-20", "documento": "Cheque 0870",
             "debito": "300.00", "credito": "0.00"},
        ],
        "conciliacion_anterior": [
            {"cuenta": "1.1.02.01", "fecha": "2025-11-28", "categoria": "Cheque sin cobrar",
             "documento": "Cheque 1490", "valor": "850.00", "observacion": "Pendiente de cobro"},
            {"cuenta": "1.1.02.04", "fecha": "2025-09-10", "categoria": "Consignación no registrada",
             "documento": "Depósito", "valor": "450.00", "observacion": "No acreditado"},
        ],
        "arqueo": [
            {"denominacion": "Billete 20", "cantidad": "15", "valor_unitario": "20.00", "observacion": ""},
            {"denominacion": "Billete 10", "cantidad": "12", "valor_unitario": "10.00", "observacion": ""},
            {"denominacion": "Moneda 1", "cantidad": "40", "valor_unitario": "1.00", "observacion": ""},
            {"denominacion": "Moneda 0.25", "cantidad": "32", "valor_unitario": "0.25", "observacion": ""},
        ],
    },
}

_PYMES = {**EJEMPLO["parametros"], "_marco": "NIIF para las PYMES"}
ESCENARIOS = [
    ("completas", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": "NIIF completas"}, EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**_PYMES, "_edicion": "2025", "tolerancia": 1000, "mesesRestriccion": 24}, EJEMPLO["corte"]),
]
