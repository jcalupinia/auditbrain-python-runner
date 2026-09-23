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
from datetime import date

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
CAMPOS = {"cuentas": _CUENTAS, "partidas": _PARTIDAS}
TIPOS = {"cuentas": "cuentas", "partidas": "partidas"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "cuentas"
CONTROL = "saldo_libros"

PARAMETROS = {"diasAntiguedad": 90, "diasCorte": 5, "mesesEquivalente": 3, "mesesRestriccion": 12, "tolerancia": 0}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "diasAntiguedad": "Partida antigua desde (días al corte)",
    "diasCorte": "Días para que el banco acredite un depósito en tránsito",
    "mesesEquivalente": "Plazo de un equivalente (meses desde la adquisición)",
    "mesesRestriccion": "Restricción que la hace no corriente (meses tras el cierre)",
    "tolerancia": "Tolerancia de diferencias (USD)",
}
TOTAL_EJEMPLO = "auditado"

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Conciliacion", "Conciliación bancaria por cuenta"),
    ("04_Partidas", "Partidas conciliatorias"), ("05_Antiguedad", "Antigüedad de partidas"),
    ("06_Confirmaciones", "Confirmación bancaria"), ("07_Corte", "Prueba de corte"), ("08_Restringido", "Efectivo restringido"),
    ("09_Equivalentes", "Equivalentes de efectivo (definición)"), ("10_Efectivo_auditado", "Efectivo auditado y ajuste"),
    ("11_Asientos", "Asientos propuestos"), ("12_Problemas", "Problemas encontrados"),
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
    limite_restr = _edate(corte_a, int(p["mesesRestriccion"]))

    cuentas = []
    for f in datasets.get("cuentas") or []:
        if str(f.get("id", "") or "").strip() == "" and _opt(f.get("saldo_libros")) is None:
            continue
        mr = _opt(f.get("monto_restringido"))
        cuentas.append({
            "id": str(f.get("id", "")).strip(), "nombre": str(f.get("nombre", "") or "").strip() or "(sin nombre)",
            "tipo": _tipo_cuenta(f.get("tipo")) or BANCO, "libros": num(f.get("saldo_libros")),
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
            c["clasif"] = "Sin fecha de fin: VERIFICAR" if c["fin"] is None else ("No corriente" if c["fin"] >= limite_restr else "Corriente")
            c["reclasR"] = c["monto"] if (c["clasif"] == "No corriente" and not c["sep"]) else 0.0
        else:
            c["clasif"], c["reclasR"] = None, None
        # 7 · equivalentes: tres meses desde la adquisición (NIC 7.7), no 90 días.
        if c["tipo"] == INV:
            c["plazo"] = (c["venc"] - c["adq"]).days if (c["adq"] and c["venc"]) else None
            c["limite"] = _edate(c["adq"], meses_eq) if c["adq"] else None
            c["califica"] = ("Sin fechas: VERIFICAR" if (c["adq"] is None or c["venc"] is None)
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
    detalle = {"parametros": p, "corte": corte_a.isoformat(), "limiteRestriccion": limite_restr.isoformat(), "refs": rf, "conceptos": con,
               "cuentas": [{k: (iso(v) if isinstance(v, date) else v) for k, v in c.items()} for c in cuentas],
               "partidas": [{k: (iso(v) if isinstance(v, date) else v) for k, v in x.items()} for x in partidas]}
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


def _rango(h: str, col: str, n: int) -> str:
    return f"{h}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _pos(x: str) -> str:
    """Suma de valores absolutos que ignora celdas vacías o con texto (ABS falla con "")."""
    return f'SUMIF({x},">0")-SUMIF({x},"<0")'


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
                          n2(c["auditado"]))])
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
                            fx(f'IF(F{r}="","Sin fecha de fin: VERIFICAR",IF(F{r}>=EDATE({corte},{meses}),"No corriente","Corriente"))', c["clasif"]),
                            "Sí" if c["sep"] else "No",
                            fx(f'IF(OR(H{r}="Sí",G{r}<>"No corriente"),0,IF(D{r}="","",D{r}))', n2(c["reclasR"]))])
    fin_r = FILA0 + nr - 1

    # 09 · Equivalentes.
    equiv = []
    for i, c in enumerate(inv):
        r, rc = FILA0 + i, fila_cta[c["id"]]
        equiv.append([c["id"], c["nombre"], c["adq"] or None, c["venc"] or None, fx(f'IF(OR(C{r}="",D{r}=""),"",D{r}-C{r})', c["plazo"]),
                      fx(f'IF(OR(C{r}="",D{r}=""),"Sin fechas: VERIFICAR",IF(D{r}<=EDATE(C{r},{meses_eq}),"Sí","No"))', c["califica"]),
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

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Conciliacion", "Conciliación bancaria por cuenta",
             [["Cuenta", "t"], ["Banco / caja", "t"], ["Tipo", "t"], ["Saldo estado bancario / arqueo", "n"], ["(+) Depósitos en tránsito", "n"],
              ["(−) Cheques pendientes", "n"], ["(−) Notas de crédito no registradas", "n"], ["(+) Notas de débito no registradas", "n"],
              ["(±) Otras partidas", "n"], ["Saldo que explica la conciliación", "n"], ["Saldo según libros", "n"],
              ["Diferencia no explicada", "n"], ["Saldo ajustado de libros", "n"], ["Efectivo auditado", "n"]], concil,
             ["TOTAL", "", "", None, tot("E", fin_c, sum(c["dt"] for c in cu)), tot("F", fin_c, sum(c["cp"] for c in cu)),
              tot("G", fin_c, con["nc"]), tot("H", fin_c, con["nd"]), tot("I", fin_c, sum(c["ot"] for c in cu)), None,
              tot("K", fin_c, con["saldoLibros"]), None, tot("M", fin_c, sum(c["ajustado"] for c in cu)), tot("N", fin_c, con["auditado"])]),
        hoja("04_Partidas", "Partidas conciliatorias",
             [["Partida", "t"], ["Cuenta", "t"], ["Tipo", "t"], ["Referencia", "t"], ["Fecha de origen", "d"], ["Importe", "n"],
              ["Liquidación posterior", "d"], ["Días al corte", "i"], ["Días hasta la liquidación", "i"], ["Antigua", "t"],
              ["Depurada", "t"], ["Cuenta en el anexo", "t"]], partidas,
             ["TOTAL", "", "", "", None, tot("F", fin_p, sum(x["importe"] for x in pa)), None, None, None, "", "", ""] if np_ else None),
        hoja("05_Antiguedad", "Antigüedad de partidas",
             [["Tramo (días al corte)", "t"], ["Partidas", "i"], ["Importe", "n"], ["No depurado", "n"]], antig,
             ["TOTAL", fx(f"SUM(B{FILA0}:B{fin_a})", sum(1 for x in pa if x["diasCorte"] is not None)),
              tot("C", fin_a, sum(x["importe"] for x in pa if x["diasCorte"] is not None)),
              tot("D", fin_a, sum(x["importe"] for x in pa if x["diasCorte"] is not None and not x["depurada"]))]),
        hoja("06_Confirmaciones", "Confirmación bancaria",
             [["Cuenta", "t"], ["Banco", "t"], ["Saldo según estado bancario", "n"], ["Saldo confirmado por el banco", "n"],
              ["Diferencia (confirmado − estado)", "n"], ["Resultado", "t"]], confir),
        hoja("07_Corte", "Prueba de corte",
             [["Partida", "t"], ["Cuenta", "t"], ["Tipo", "t"], ["Fecha en libros", "d"], ["Fecha en el banco", "d"],
              ["Días después del corte", "i"], ["Resultado", "t"], ["Importe", "n"]], corte_filas,
             ["TOTAL", "", "", None, None, None, "", tot("H", fin_k, sum(x["importe"] for _, x in sel))] if sel else None),
        hoja("08_Restringido", "Efectivo restringido",
             [["Cuenta", "t"], ["Banco", "t"], ["Saldo ajustado", "n"], ["Monto restringido", "n"], ["Motivo", "t"], ["Fin de la restricción", "d"],
              ["Clasificación", "t"], ["Ya presentado aparte", "t"], ["Reclasificación propuesta", "n"]], restringido,
             ["TOTAL", "", None, None, "", None, "", "", tot("I", fin_r, con["reclasRestringido"])] if nr else None),
        hoja("09_Equivalentes", "Equivalentes de efectivo (definición)",
             [["Cuenta", "t"], ["Instrumento", "t"], ["Adquisición", "d"], ["Vencimiento", "d"], ["Plazo original (días)", "i"],
              ["Vence en tres meses o menos (presunción)", "t"], ["Saldo ajustado", "n"], ["Ya reclasificado por restricción", "n"],
              ["Reclasificación propuesta", "n"]],
             equiv, ["TOTAL", "", None, None, None, "", tot("G", fin_e, sum(c["ajustado"] for c in inv)), None,
                     tot("I", fin_e, con["reclasNoEquivalentes"])] if ni else None),
        hoja("10_Efectivo_auditado", "Efectivo auditado y ajuste", [["Concepto", "t"], ["Importe", "n"]], auditado),
        hoja("11_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos),
        hoja("12_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
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
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo numérico de control (M19) ---------------------------------------------------

def _c(id, nombre, tipo, libros, banco, conf="", **extra):
    return {"id": id, "nombre": nombre, "tipo": tipo, "saldo_libros": libros, "saldo_banco": banco, "saldo_confirmado": conf, "_row": 2, **extra}


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
    },
}

_PYMES = {**EJEMPLO["parametros"], "_marco": "NIIF para las PYMES"}
ESCENARIOS = [
    ("completas", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": "NIIF completas"}, EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**_PYMES, "_edicion": "2025", "tolerancia": 1000, "mesesRestriccion": 24}, EJEMPLO["corte"]),
]
