"""Patrimonio: movimiento patrimonial, capital y aportes, reserva legal, dividendos, recompra de acciones
propias y clasificación deuda / patrimonio.

Dos anexos alimentan las pruebas:

- ``movimientos`` (principal): una fila por cuenta patrimonial (capital, aportes para futuras
  capitalizaciones, reserva legal, otras reservas, ORI, resultados acumulados, resultado del ejercicio,
  acciones propias). Saldos con signo del patrimonio (acreedor positivo; acciones propias negativo);
  aumentos y disminuciones en positivo.
  1. Movimiento recalculado = inicial + aumentos − disminuciones vs final según cliente vs mayor
     (NIC 1 106 d); PYMES Sección 6).
  2. Reserva legal (Ley de Compañías arts. 297 y 109, parámetros «vigente al corte»): requerida =
     mín(máx(utilidad líquida, 0) × %, máx(nivel mínimo % × capital − reserva inicial, 0)) vs apropiada (aumentos
     de la cuenta reserva legal del período).
  3. Capital según cliente vs escritura / Supercias.
- ``transacciones``: actas y movimientos del período (o instrumentos vigentes al corte).
  4. Dividendos declarados del período ≤ utilidades disponibles (resultados acumulados + resultado del
     ejercicio anterior − reserva legal requerida + reservas expresas de libre disposición (Ley de
     Compañías art. 298), o el importe que fije el auditor por utilidades líquidas y realizadas), y
     ≥ el mínimo legal (art. 297: al menos el 50 % de los beneficios líquidos del ejercicio luego de las
     deducciones, salvo resolución unánime de la junta; 30 % en emisores inscritos en el Catastro Público
     del Mercado de Valores).
  5. Dividendo declarado después del cierre registrado como pasivo: error (NIC 10 12–13; PYMES 32.8);
     se revela en notas (NIC 1 137).
  6. Aumento de capital sin inscripción en el Registro Mercantil al corte.
  7. Aporte con obligación de devolución y todo instrumento con obligación contractual de entregar
     efectivo → pasivo (NIC 32 11, 15–16, 18 a); PYMES 22.3–22.6).
  8. Recompra: acciones propias deducidas del patrimonio sin pérdida ni ganancia en resultados (NIC 32 33;
     PYMES 22.16).

El cálculo es el mismo en ambos marcos; solo cambian las citas (se enruta con es_pymes).
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m,
    n2, norm, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "patrimonio 1.0"
RUBRO = "PATRIMONIO"

CLASES = ["Capital", "Aportes futuras capitalizaciones", "Reserva legal", "Otras reservas", "Otros resultados integrales",
          "Resultados acumulados", "Resultado del ejercicio", "Acciones propias", "Otra"]
TIPOS_TX = ["Aumento de capital", "Aporte", "Dividendo declarado", "Dividendo pagado", "Apropiación de reserva", "Recompra", "Otro"]
_CON_ACTA = ("Aumento de capital", "Aporte", "Dividendo declarado", "Apropiación de reserva", "Recompra")

_MOV = [
    campo("id", "Código de la cuenta", alias=("codigo", "cuenta contable", "codigo cuenta", "cod"), ejemplo="301"),
    campo("cuenta", "Nombre de la cuenta patrimonial", alias=("nombre", "descripcion", "nombre de la cuenta", "detalle"), ejemplo="Capital suscrito y pagado"),
    campo("clase", "Clase (capital, aportes, reserva legal, otras reservas, ORI, resultados acumulados, resultado del ejercicio, acciones propias)",
          "text", False, ("clase", "tipo", "componente", "grupo"), "Capital"),
    campo("inicial", "Saldo inicial", "number", alias=("saldo inicial", "saldo anterior", "inicio"), ejemplo="400000.00"),
    campo("aumentos", "Aumentos del período", "number", False, ("aumentos", "creditos", "incrementos", "adiciones"), "100000.00"),
    campo("disminuciones", "Disminuciones del período", "number", False, ("disminuciones", "debitos", "reducciones", "bajas"), "0.00"),
    campo("final", "Saldo final según cliente", "number", alias=("saldo final", "saldo cliente", "saldo final cliente", "saldo al corte"), ejemplo="500000.00"),
    campo("mayor", "Saldo final según el mayor", "number", False, ("saldo mayor", "mayor", "balance de comprobacion", "saldo final mayor")),
]
_TX = [
    campo("id", "Referencia (acta, asiento o documento)", alias=("referencia", "documento", "acta", "asiento", "comprobante"), ejemplo="JGA-2025-01"),
    campo("fecha", "Fecha de la transacción o registro", "date", alias=("fecha", "fecha registro", "fecha contable"), ejemplo="2025-03-28"),
    campo("tipo", "Tipo (aumento de capital, aporte, dividendo declarado, dividendo pagado, apropiación de reserva, recompra, otro)",
          alias=("tipo", "tipo de transaccion", "concepto tipo", "clase de movimiento"), ejemplo="Aumento de capital"),
    campo("importe", "Importe", "number", alias=("valor", "monto", "importe"), ejemplo="60000.00"),
    campo("acta", "¿Acta de junta? (sí/no)", "text", False, ("acta de junta", "acta", "aprobado por junta")),
    campo("fecha_acta", "Fecha del acta de junta", "date", False, ("fecha acta", "fecha de junta", "fecha de declaracion")),
    campo("inscripcion", "Fecha de inscripción en el Registro Mercantil", "date", False, ("inscripcion", "registro mercantil", "fecha inscripcion")),
    campo("devolucion", "¿Obligación de devolución? (sí/no)", "text", False, ("devolucion", "reembolsable", "obligacion de devolucion")),
    campo("obligacion", "¿Obligación contractual de entregar efectivo? (sí/no)", "text", False,
          ("obligacion contractual", "rescatable", "instrumento con obligacion", "redimible")),
    campo("cuenta", "Cuenta afectada", "text", False, ("cuenta afectada", "cuenta", "cuenta patrimonial")),
    campo("pasivo_corte", "¿Registrado como pasivo al corte? (sí/no)", "text", False, ("pasivo al corte", "registrado como pasivo", "dividendo por pagar")),
    campo("resultado", "Importe reconocido en resultados (ganancia + / pérdida −)", "number", False,
          ("resultado", "efecto en resultados", "ganancia o perdida")),
    campo("concepto", "Concepto", "text", False, ("detalle", "descripcion", "observacion")),
]
CAMPOS = {"movimientos": _MOV, "transacciones": _TX}
TIPOS = {"movimientos": "movimientos", "transacciones": "transacciones"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "movimientos"
CONTROL = "final"

PARAMETROS = {"tipoCompania": "Anónima", "utilidadNeta": None, "pctReserva": None, "topeReserva": None,
              "capitalEscritura": None, "utilidadesDisponibles": None, "reservasLibreDisposicion": None,
              "pctDividendoMinimo": None, "resolucionUnanime": "No"}
PARAM_NEGATIVOS = ("utilidadNeta",)
# Ley de Compañías art. 297: al menos el 50 % de los beneficios líquidos anuales, luego de las deducciones que
# correspondieren, salvo resolución unánime del capital concurrente a la junta; 30 % en los emisores cuyas acciones
# están inscritas en el Catastro Público del Mercado de Valores (vigente al corte; VERIFICAR).
PCT_DIV_MINIMO = 50.0
ETIQUETAS_PARAM = {
    "tipoCompania": "Tipo de compañía (Anónima / Limitada)",
    "utilidadNeta": "Utilidad líquida sobre la que se apropia la reserva legal (vacío: saldo inicial del resultado del ejercicio)",
    "pctReserva": "% de la utilidad para reserva legal (vacío: mínimo 10 % de la utilidad líquida hasta por lo menos el 50 % del capital (Ley de Compañías art. 297, anónimas); 5 % de las utilidades líquidas y realizadas hasta por lo menos 20 % (art. 109, limitadas); vigente al corte)",
    "topeReserva": "Nivel mínimo de la reserva legal a partir del cual cesa la apropiación obligatoria, % del capital (vacío: mínimo 10 % de la utilidad líquida hasta por lo menos el 50 % del capital (Ley de Compañías art. 297, anónimas); 5 % de las utilidades líquidas y realizadas hasta por lo menos 20 % (art. 109, limitadas); vigente al corte)",
    "capitalEscritura": "Capital suscrito según escritura inscrita / Supercias",
    "utilidadesDisponibles": "Utilidades líquidas y realizadas disponibles para dividendos (vacío: se calculan)",
    "reservasLibreDisposicion": "Reservas expresas efectivas de libre disposición (se suman a las utilidades disponibles; Ley de Compañías art. 298; vacío: ninguna)",
    "pctDividendoMinimo": f"% mínimo de los beneficios líquidos a repartir como dividendos (vacío: {PCT_DIV_MINIMO:g} % — Ley de Compañías art. 297; 30 % en emisores con acciones inscritas en el Catastro Público del Mercado de Valores; vigente al corte)",
    "resolucionUnanime": "¿Resolución unánime del capital concurrente a la junta sobre el destino de las utilidades? (Sí: no aplica el mínimo del art. 297)",
}
TOTAL_EJEMPLO = "ajusteNeto"
_DEF_RESERVA = {"Anónima": (10.0, 50.0), "Limitada": (5.0, 20.0)}

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Movimiento", "Movimiento patrimonial"),
    ("04_Transacciones", "Actas y transacciones"), ("05_Reserva_legal", "Reserva legal"), ("06_Dividendos", "Dividendos"),
    ("07_Capital", "Capital y aumentos"), ("08_Clasificacion", "Clasificación deuda / patrimonio"),
    ("09_Recompra", "Recompra de acciones propias"), ("10_Ajuste", "Patrimonio auditado y ajustes"),
    ("11_Asientos", "Asientos propuestos"), ("12_Problemas", "Problemas encontrados"),
]

_SI = {"si", "s", "x", "yes", "y", "1", "true", "verdadero"}
_NO = {"no", "n", "0", "false", "falso"}


def _sino(v):
    k = norm(v)
    if not k:
        return ""
    return "Sí" if k in _SI else ("No" if k in _NO else None)


def _clase(*textos):
    for t in textos:
        k = norm(t)
        if not k:
            continue
        if any(x in k for x in ("accionespropias", "encartera", "recompra", "tesoreria", "readquirid")):
            return "Acciones propias"
        if "futura" in k or "aporte" in k:
            return "Aportes futuras capitalizaciones"
        if "reservalegal" in k:
            return "Reserva legal"
        if "reserva" in k:
            return "Otras reservas"
        if k == "ori" or "otrosresultadosintegrales" in k or "otroresultadointegral" in k or "superavit" in k:
            return "Otros resultados integrales"
        if "acumulad" in k:
            return "Resultados acumulados"
        if "ejercicio" in k or "periodo" in k:
            return "Resultado del ejercicio"
        if "capital" in k:
            return "Capital"
        if k in {norm(c) for c in ("otra", "otro", "otras")}:
            return "Otra"
    return "Otra"


def _tipo(v):
    k = norm(v)
    if not k:
        return None
    if "aumento" in k and "capital" in k:
        return "Aumento de capital"
    if "dividendo" in k:
        return "Dividendo pagado" if "pag" in k else "Dividendo declarado"
    if "aporte" in k or "futura" in k:
        return "Aporte"
    if "reserva" in k or "apropiacion" in k:
        return "Apropiación de reserva"
    if "recompra" in k or "accionespropias" in k or "readquisicion" in k:
        return "Recompra"
    if k.startswith("otro"):
        return "Otro"
    return None


def _tipo_cia(v):
    k = norm(v)
    if k in ("anonima", "sa", "companiaanonima", "sociedadanonima"):
        return "Anónima"
    if k in ("limitada", "ltda", "cialtda", "companialimitada", "responsabilidadlimitada"):
        return "Limitada"
    return None


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    r = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        if tipo == "transacciones":
            if _tipo(f.get("tipo")) is None and str(f.get("tipo", "") or "").strip():
                r["errors"].append({"row": f.get("_row"), "field": "tipo", "message": "Tipo no reconocido: use " + ", ".join(TIPOS_TX) + "."})
            for k in ("acta", "devolucion", "obligacion", "pasivo_corte"):
                if _sino(f.get(k)) is None:
                    r["errors"].append({"row": f.get("_row"), "field": k, "message": "Responda «sí» o «no»."})
        else:
            for k in ("aumentos", "disminuciones"):
                x = a_num(f.get(k))
                if x is not None and x < 0:
                    r["errors"].append({"row": f.get("_row"), "field": k, "message": "Informe aumentos y disminuciones en positivo."})
    r["ok"] = not r["errors"]
    return r


# --- cálculo -----------------------------------------------------------------

def _pnum(p, k):
    v = p.get(k)
    return None if v is None or str(v).strip() == "" else float(a_num(v))


def _citas(pymes: bool) -> dict:
    if pymes:
        return {"clas": "PYMES 22.3–22.6", "emision": "PYMES 22.7–22.10", "propias": "PYMES 22.16", "dist": "PYMES 22.17",
                "ecp": "PYMES Sección 6", "post": "PYMES 32.8", "rev": "PYMES 32.8 (presentación) y 32.10 (revelación)", "especie": "PYMES 22.18"}
    return {"clas": "NIC 32 11, 15–16, 18 a)", "emision": "NIC 32 35", "propias": "NIC 32 33", "dist": "NIC 32 35",
            "ecp": "NIC 1 106–110", "post": "NIC 10 12–13", "rev": "NIC 1 137 a)", "especie": "CINIIF 17 10–11"}


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    pymes = es_pymes(p)
    cit = _citas(pymes)
    tipo_cia = _tipo_cia(p.get("tipoCompania"))
    if tipo_cia is None:
        raise ValueError("Tipo de compañía no reconocido: indique «Anónima» o «Limitada».")
    pct = _pnum(p, "pctReserva")
    tope = _pnum(p, "topeReserva")
    pct = _DEF_RESERVA[tipo_cia][0] if pct is None else pct
    tope = _DEF_RESERVA[tipo_cia][1] if tope is None else tope
    if not 0 <= pct <= 100 or not 0 <= tope <= 100:
        raise ValueError("El % de reserva legal y el tope deben estar entre 0 y 100.")
    cap_esc = _pnum(p, "capitalEscritura")
    disp_aud = _pnum(p, "utilidadesDisponibles")
    libres = _pnum(p, "reservasLibreDisposicion")
    pct_min = _pnum(p, "pctDividendoMinimo")
    pct_min = PCT_DIV_MINIMO if pct_min is None else pct_min
    if not 0 <= pct_min <= 100:
        raise ValueError("El % mínimo de dividendos debe estar entre 0 y 100.")
    if libres is not None and libres < 0:
        raise ValueError("Las reservas de libre disposición no pueden ser negativas.")
    unanime = _sino(p.get("resolucionUnanime"))
    if unanime is None:
        raise ValueError("Responda «sí» o «no» en «¿Resolución unánime de la junta?».")
    unanime = unanime or "No"
    if cap_esc is not None and cap_esc < 0:
        raise ValueError("El capital según escritura no puede ser negativo.")
    if disp_aud is not None and disp_aud < 0:
        raise ValueError("Las utilidades disponibles no pueden ser negativas.")

    cuentas = []
    for f in datasets.get("movimientos") or []:
        ini, fin = a_num(f.get("inicial")), a_num(f.get("final"))
        if ini is None or fin is None:
            raise ValueError(f"Cuenta {f.get('id')}: faltan el saldo inicial o el saldo final según cliente.")
        aum, dis = a_num(f.get("aumentos")) or 0.0, a_num(f.get("disminuciones")) or 0.0
        if aum < 0 or dis < 0:
            raise ValueError(f"Cuenta {f.get('id')}: informe aumentos y disminuciones en positivo.")
        may = a_num(f.get("mayor")) if str(f.get("mayor", "") or "").strip() else None
        recal = ini + aum - dis
        cuentas.append({"id": str(f.get("id", "")).strip(), "cuenta": str(f.get("cuenta", "")).strip() or "(sin nombre)",
                        "clase": _clase(f.get("clase"), f.get("cuenta")), "inicial": ini, "aumentos": aum, "disminuciones": dis,
                        "recalculado": recal, "final": fin, "difMov": fin - recal, "mayor": may,
                        "difMayor": None if may is None else fin - may, "_row": f.get("_row")})
    if not cuentas:
        raise ValueError("Cargue el movimiento de las cuentas patrimoniales (saldo inicial, aumentos, disminuciones y saldo final).")

    txs = []
    for f in datasets.get("transacciones") or []:
        tp, imp, fe = _tipo(f.get("tipo")), a_num(f.get("importe")), fecha(f.get("fecha"))
        if tp is None or imp is None or fe is None:
            raise ValueError(f"Transacción {f.get('id')}: faltan o no se reconocen el tipo, el importe o la fecha.")
        sn = {k: _sino(f.get(k)) for k in ("acta", "devolucion", "obligacion", "pasivo_corte")}
        if any(v is None for v in sn.values()):
            raise ValueError(f"Transacción {f.get('id')}: responda «sí» o «no» en acta, devolución, obligación contractual y pasivo al corte.")
        fa, ins = fecha(f.get("fecha_acta")), fecha(f.get("inscripcion"))
        res_txt = str(f.get("resultado", "") or "").strip()
        resul = a_num(res_txt) if res_txt else None
        efectiva = fa or fe
        post = efectiva > corte_a
        aporte_pas = tp == "Aporte" and sn["devolucion"] == "Sí"
        cta = str(f.get("cuenta", "") or "").strip()
        txs.append({
            "doc": str(f.get("id", "")).strip(), "fecha": fe, "tipo": tp, "importe": imp, "acta": sn["acta"], "fechaActa": fa,
            "inscripcion": ins, "devolucion": sn["devolucion"], "obligacion": sn["obligacion"],
            "cuenta": _clase(cta) if cta else "", "pasivoCorte": sn["pasivo_corte"], "resultado": resul,
            "efectiva": efectiva, "posterior": post,
            "divPeriodo": imp if tp == "Dividendo declarado" and not post else 0,
            "divPostPasivo": imp if tp == "Dividendo declarado" and post and sn["pasivo_corte"] == "Sí" else 0,
            "noInscrito": imp if tp == "Aumento de capital" and fe <= corte_a and (ins is None or ins > corte_a) else 0,
            "aportePasivo": imp if aporte_pas else 0,
            "instrPasivo": imp if sn["obligacion"] == "Sí" and not aporte_pas else 0,
            "resRecompra": resul if tp == "Recompra" and resul is not None else 0,
            "sinActa": "Sí" if sn["acta"] != "Sí" and tp in _CON_ACTA else "No",
            "concepto": str(f.get("concepto", "") or "").strip(), "_row": f.get("_row"),
        })

    def s_cl(clase, k):
        return sum(c[k] for c in cuentas if c["clase"] == clase)

    cliente = sum(c["final"] for c in cuentas)
    con_mayor = [c for c in cuentas if c["mayor"] is not None]
    mayor = sum(c["mayor"] for c in con_mayor) if con_mayor else None
    dif_mov = sum(abs(c["difMov"]) for c in cuentas)

    # Reserva legal.
    hay_re = any(c["clase"] == "Resultado del ejercicio" for c in cuentas)
    base_dada = _pnum(p, "utilidadNeta")
    base = base_dada if base_dada is not None else (s_cl("Resultado del ejercicio", "inicial") if hay_re else None)
    capital = s_cl("Capital", "final")
    tope_imp = capital * (tope / 100)
    rl_ini = s_cl("Reserva legal", "inicial")
    margen = max(tope_imp - rl_ini, 0)
    calc = None if base is None else max(base, 0) * (pct / 100)
    requerida = None if calc is None else min(calc, margen)
    apropiada = s_cl("Reserva legal", "aumentos")
    aj_res = None if requerida is None else requerida - apropiada
    rl_fin = s_cl("Reserva legal", "final")

    # Dividendos.
    ra_ini, re_ini = s_cl("Resultados acumulados", "inicial"), s_cl("Resultado del ejercicio", "inicial")
    antes = max(ra_ini + re_ini, 0)
    # Ley de Compañías art. 298: también se pueden pagar dividendos con reservas expresas efectivas de libre disposición.
    disp_calc = max(antes - (requerida or 0), 0) + (libres or 0)
    disp = disp_aud if disp_aud is not None else disp_calc
    declarados = sum(t["divPeriodo"] for t in txs)
    exceso = max(declarados - disp, 0)
    # Ley de Compañías art. 297: mínimo legal sobre los beneficios líquidos del ejercicio, luego de las deducciones
    # (aquí, la reserva legal requerida); no aplica si hubo resolución unánime de la junta.
    base_min = None if base is None else max(base - (requerida or 0), 0)
    min_div = None if base_min is None or unanime == "Sí" else base_min * pct_min / 100
    falta_div = None if min_div is None else max(min_div - declarados, 0)
    post_total = sum(t["importe"] for t in txs if t["tipo"] == "Dividendo declarado" and t["posterior"])
    post_pasivo = sum(t["divPostPasivo"] for t in txs)
    pagados = sum(t["importe"] for t in txs if t["tipo"] == "Dividendo pagado" and not t["posterior"])

    # Capital.
    aumentos_cap = sum(t["importe"] for t in txs if t["tipo"] == "Aumento de capital")
    no_insc = sum(t["noInscrito"] for t in txs)
    dif_cap = None if cap_esc is None else capital - cap_esc
    no_expl = None if cap_esc is None else capital - no_insc - cap_esc
    aportes_cli = s_cl("Aportes futuras capitalizaciones", "final")

    ap_pas = sum(t["aportePasivo"] for t in txs)
    in_pas = sum(t["instrPasivo"] for t in txs)
    res_rec = sum(t["resRecompra"] for t in txs)
    auditado = cliente - ap_pas - in_pas + post_pasivo
    ajuste = auditado - cliente

    problemas = []
    for c in cuentas:
        if abs(c["difMov"]) > 0.005:
            problemas.append(problema("MOVIMIENTO_NO_CUADRA", f"{c['id']} {c['cuenta']}: inicial {m(c['inicial'])} + aumentos {m(c['aumentos'])} − disminuciones "
                                      f"{m(c['disminuciones'])} = {m(c['recalculado'])}, pero el saldo final informado es {m(c['final'])} "
                                      f"(diferencia {m(c['difMov'])}); el estado de cambios en el patrimonio debe conciliar cada componente ({cit['ecp']}).", c["difMov"]))
    for c in con_mayor:
        if abs(c["difMayor"]) > 0.005:
            problemas.append(problema("DIF_MAYOR", f"{c['id']} {c['cuenta']}: saldo del cliente {m(c['final'])} vs mayor {m(c['mayor'])} "
                                      f"(diferencia {m(c['difMayor'])}) (NIA 500).", c["difMayor"]))
    if mayor is None:
        problemas.append(problema("SIN_SALDO_MAYOR", "No se informó el saldo final según el mayor: concilie cada cuenta patrimonial con el mayor (NIA 500)."))
    if requerida is None:
        problemas.append(problema("RESERVA_SIN_BASE", "No hay utilidad líquida para medir la reserva legal ni el mínimo legal de dividendos: ingrésela en "
                                  "parámetros o incluya la cuenta «resultado del ejercicio» en el movimiento (Ley de Compañías arts. 297 y 109)."))
    elif aj_res > 0.005:
        problemas.append(problema("RESERVA_LEGAL_NO_APROPIADA", f"Reserva legal requerida {m(requerida)} ({m(pct)} % de la utilidad {m(base)}, hasta el "
                                  f"{m(tope)} % del capital) frente a {m(apropiada)} apropiada: falta apropiar {m(aj_res)} (Ley de Compañías arts. 297/109, "
                                  f"compañía {tipo_cia.lower()}; vigente al corte).", aj_res))
    elif aj_res < -0.005:
        problemas.append(problema("RESERVA_LEGAL_EN_EXCESO", f"Se apropiaron {m(apropiada)} a la reserva legal, más que lo requerido {m(requerida)} "
                                  f"(exceso {m(-aj_res)}). Apropiación mayor que el mínimo legal (arts. 297/109): no es incumplimiento; verificar que la junta la aprobó.", aj_res))
    if exceso > 0.005:
        problemas.append(problema("DIVIDENDOS_SOBRE_UTILIDADES_NO_DISPONIBLES", f"Dividendos declarados en el período {m(declarados)} superan las utilidades "
                                  f"disponibles {m(disp)} en {m(exceso)}: Ley de Compañías arts. 208 y 298: solo beneficios realmente obtenidos y percibidos "
                                  f"o reservas de libre disposición — evalúe la legalidad y la revelación ({cit['dist']}).", exceso))
    if falta_div is not None and falta_div > 0.005:
        problemas.append(problema("DIVIDENDO_MINIMO_NO_ASIGNADO", f"Dividendos declarados {m(declarados)} por debajo del mínimo legal {m(min_div)} "
                                  f"({m(pct_min)} % de los beneficios líquidos {m(base_min)} = utilidad {m(base)} − reserva legal requerida "
                                  f"{m(requerida or 0)}): faltan {m(falta_div)}. Salvo resolución unánime del capital concurrente a la junta, debe "
                                  "asignarse ese mínimo a los accionistas que lo soliciten expresamente (Ley de Compañías art. 297; 30 % en emisores "
                                  "inscritos en el Catastro Público del Mercado de Valores).", falta_div))
    for t in txs:
        if t["divPostPasivo"]:
            problemas.append(problema("DIVIDENDO_POSTERIOR_COMO_PASIVO", f"{t['doc']}: dividendo declarado el {t['efectiva'].isoformat()} (después del cierre) "
                                      f"registrado como pasivo al corte por {m(t['importe'])}: no existía obligación al cierre; revertir contra el "
                                      f"patrimonio y revelar en notas ({cit['post']}; {cit['rev']}).", t["importe"]))
    if post_total > 0.005:
        problemas.append(problema("DIVIDENDO_POSTERIOR_REVELAR", f"Dividendos declarados después del cierre por {m(post_total)}: revelar el importe y el "
                                  f"importe por acción en las notas ({cit['rev']}).", post_total))
    if cap_esc is None:
        problemas.append(problema("SIN_CAPITAL_ESCRITURA", "No se informó el capital suscrito según la escritura inscrita / Supercias: no se pudo cotejar el capital."))
    elif abs(dif_cap) > 0.005:
        problemas.append(problema("CAPITAL_NO_COINCIDE_ESCRITURA", f"Capital según cliente {m(capital)} vs escritura / Supercias {m(cap_esc)}: diferencia "
                                  f"{m(dif_cap)}" + (f" (de ella {m(no_insc)} por aumentos no inscritos)" if no_insc > 0.005 else "") + ".", dif_cap))
    for t in txs:
        if t["noInscrito"]:
            problemas.append(problema("AUMENTO_NO_INSCRITO", f"{t['doc']}: aumento de capital de {m(t['importe'])} sin inscripción en el Registro Mercantil al "
                                      "corte: presentarlo como aporte para futura capitalización hasta la inscripción (Ley de Compañías art. 33: el aumento sigue las solemnidades de la constitución; VERIFICAR registro).",
                                      t["importe"]))
        if t["aportePasivo"]:
            problemas.append(problema("APORTE_ES_PASIVO", f"{t['doc']}: aporte de {m(t['importe'])} con obligación de devolución: es un pasivo financiero, "
                                      f"no patrimonio ({cit['clas']}; resolución Supercias vigente — VERIFICAR).", t["importe"]))
        if t["instrPasivo"]:
            problemas.append(problema("INSTRUMENTO_MAL_CLASIFICADO", f"{t['doc']}: instrumento de {m(t['importe'])} con obligación contractual de entregar "
                                      f"efectivo (p. ej. acciones preferentes rescatables) presentado en patrimonio: reclasificar a pasivo ({cit['clas']}).",
                                      t["importe"]))
        if t["tipo"] == "Recompra" and t["resultado"] is not None and abs(t["resultado"]) > 0.005:
            problemas.append(problema("RECOMPRA_CON_RESULTADO", f"{t['doc']}: la recompra reconoció {m(t['resultado'])} en resultados: la contraprestación de "
                                      f"acciones propias se reconoce directamente en el patrimonio, sin pérdida ni ganancia ({cit['propias']}).", abs(t["resultado"])))
        if t["tipo"] == "Recompra" and t["cuenta"] and t["cuenta"] != "Acciones propias":
            problemas.append(problema("RECOMPRA_NO_DEDUCIDA", f"{t['doc']}: recompra registrada en «{t['cuenta']}»: las acciones propias se presentan como "
                                      f"deducción del patrimonio ({cit['propias']}).", t["importe"]))
        if t["sinActa"] == "Sí":
            problemas.append(problema("SIN_ACTA", f"{t['doc']}: {t['tipo'].lower()} de {m(t['importe'])} sin acta de junta informada: obtenga la resolución "
                                      "que la autoriza (Ley de Compañías; NIA 500).", t["importe"]))
    if not txs:
        problemas.append(problema("SIN_TRANSACCIONES", "No se cargaron actas ni transacciones patrimoniales: no se probaron dividendos, aumentos, aportes, "
                                  "recompras ni la clasificación deuda / patrimonio."))

    iso = lambda d: d.isoformat() if d else ""
    rows = [{"id": c["id"], "cuenta": c["cuenta"], "clase": c["clase"], "inicial": r2(c["inicial"]), "aumentos": r2(c["aumentos"]),
             "disminuciones": r2(c["disminuciones"]), "recalculado": r2(c["recalculado"]), "final": r2(c["final"]),
             "diferencia": r2(c["difMov"]), "mayor": "" if c["mayor"] is None else r2(c["mayor"]), "_row": c["_row"]} for c in cuentas]
    totales = {"patrimonioCliente": cliente, "patrimonioAuditado": auditado, "ajusteNeto": ajuste, "aportesPasivo": ap_pas,
               "instrumentosPasivo": in_pas, "dividendosPosterioresPasivo": post_pasivo, "difMovimiento": dif_mov}
    etiquetas = {"patrimonioCliente": "Patrimonio según cliente", "patrimonioAuditado": "Patrimonio auditado",
                 "ajusteNeto": "Ajuste neto propuesto al patrimonio", "aportesPasivo": "Aportes con obligación de devolución (a pasivo)",
                 "instrumentosPasivo": "Instrumentos con obligación contractual (a pasivo)",
                 "dividendosPosterioresPasivo": "Dividendos posteriores registrados como pasivo (revertir)",
                 "difMovimiento": "Diferencias del movimiento recalculado (absolutas)"}
    if mayor is not None:
        totales.update(saldoMayor=mayor, difMayor=cliente - mayor)
        etiquetas.update(saldoMayor="Patrimonio según el mayor", difMayor="Diferencia cliente − mayor")
    if requerida is not None:
        totales.update(reservaRequerida=requerida, reservaApropiada=apropiada, ajusteReserva=aj_res)
        etiquetas.update(reservaRequerida="Reserva legal requerida", reservaApropiada="Reserva legal apropiada",
                         ajusteReserva="Reserva legal por apropiar (− exceso)")
    totales.update(dividendosDeclarados=declarados, utilidadesDisponibles=disp, excesoDividendos=exceso, aumentosNoInscritos=no_insc,
                   capitalCliente=capital)
    etiquetas.update(dividendosDeclarados="Dividendos declarados en el período", utilidadesDisponibles="Utilidades disponibles para dividendos",
                     excesoDividendos="Dividendos en exceso de utilidades disponibles", aumentosNoInscritos="Aumentos de capital no inscritos al corte",
                     capitalCliente="Capital según cliente")
    if min_div is not None:
        totales.update(dividendoMinimoLegal=min_div, dividendosBajoMinimo=falta_div)
        etiquetas.update(dividendoMinimoLegal="Dividendo mínimo legal (Ley de Compañías art. 297)",
                         dividendosBajoMinimo="Dividendos por debajo del mínimo legal")
    if cap_esc is not None:
        totales.update(capitalEscritura=cap_esc, difCapital=dif_cap)
        etiquetas.update(capitalEscritura="Capital según escritura / Supercias", difCapital="Diferencia capital cliente − escritura")
    totales["resultadoRecompras"] = res_rec
    etiquetas["resultadoRecompras"] = "Resultado reconocido por recompras (a reclasificar al patrimonio)"

    ser = lambda x: {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in x.items()}
    detalle = {"cortes": {"actual": corte_a.isoformat()}, "parametros": p, "pymes": pymes, "edicion": edicion_pymes(p) if pymes else "",
               "citas": cit, "tipoCompania": tipo_cia, "pct": pct, "tope": tope, "pctDado": _pnum(p, "pctReserva") is not None,
               "topeDado": _pnum(p, "topeReserva") is not None, "baseDada": base_dada, "hayRE": hay_re, "base": base,
               "capitalEscritura": cap_esc, "dispAuditor": disp_aud, "libres": libres, "pctMin": pct_min, "unanime": unanime, "cuentas": [ser(c) for c in cuentas], "txs": [ser(t) for t in txs],
               "reserva": {"calc": calc, "capital": capital, "topeImp": tope_imp, "inicial": rl_ini, "margen": margen, "requerida": requerida,
                           "apropiada": apropiada, "ajuste": aj_res, "final": rl_fin, "excesoTope": max(rl_fin - tope_imp, 0)},
               "div": {"ra": ra_ini, "re": re_ini, "antes": antes, "req": requerida or 0, "calc": disp_calc, "disp": disp,
                       "declarados": declarados, "exceso": exceso, "post": post_total, "postPasivo": post_pasivo, "pagados": pagados,
                       "libres": libres or 0, "minBase": base_min, "minimo": min_div, "falta": falta_div},
               "cap": {"capital": capital, "esc": cap_esc, "dif": dif_cap, "aumentos": aumentos_cap, "noInsc": no_insc, "aportes": aportes_cli,
                       "neto": capital - no_insc, "noExpl": no_expl}}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(v) for k, v in totales.items()}, "labels": etiquetas,
            "primary": "ajusteNeto", "exceptions": problemas, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

P = ref("02_Parametros")
MOV, TX, RES, DIV, CAP, AJ = (ref(n) for n in ("03_Movimiento", "04_Transacciones", "05_Reserva_legal", "06_Dividendos", "07_Capital", "10_Ajuste"))
_PAR = ["corte", "marco", "tipoCompania", "utilidadNeta", "pctReserva", "topeReserva", "capitalEscritura", "utilidadesDisponibles",
        "reservasLibreDisposicion", "pctDividendoMinimo", "resolucionUnanime"]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
_RES = ["base", "pct", "calc", "capital", "tope", "topeImp", "inicial", "margen", "requerida", "apropiada", "ajuste", "final", "excesoTope"]
RSF = {k: FILA0 + i for i, k in enumerate(_RES)}
_DIV = ["ra", "re", "antes", "req", "libres", "calc", "aud", "disp", "declarados", "exceso", "post", "postPasivo", "pagados",
        "minBase", "minimo", "falta"]
DVF = {k: FILA0 + i for i, k in enumerate(_DIV)}
_CAP = ["capital", "esc", "dif", "aumentos", "noInsc", "aportes", "neto", "noExpl"]
CPF = {k: FILA0 + i for i, k in enumerate(_CAP)}
_AJ = ["cliente", "aportesPasivo", "instrumentosPasivo", "divPost", "auditado", "ajusteNeto", "difMov", "mayor", "difMayor",
       "reservaReq", "reservaAprop", "ajusteReserva", "divDeclarados", "disponibles", "excesoDiv", "divMinimo", "divBajoMinimo",
       "noInscritos", "capitalCliente", "capitalEscritura", "difCapital", "resultadoRecompras"]
AJF = {k: FILA0 + i for i, k in enumerate(_AJ)}


def _pb(k):
    return f"{P}$B${PAR[k]}"


def _rg(hoja_ref, col, n):
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    cs, tx, cit = d["cuentas"], d["txs"], d["citas"]
    t = {k: float(v) for k, v in res["totals"].items()}
    nc, nt = len(cs), len(tx)
    fin_c, fin_t = FILA0 + nc - 1, FILA0 + nt - 1
    corte = _pb("corte")
    marco = (MARCO_PYMES + f" {d['edicion']}") if d["pymes"] else MARCO_COMPLETAS
    sumif_c = lambda clase, col: f'SUMIF({_rg(MOV, "C", nc)},"{clase}",{_rg(MOV, col, nc)})'
    rv, dv, cp = d["reserva"], d["div"], d["cap"]
    defecto = "por defecto según el tipo de compañía; " if not d["pctDado"] else ""

    if d["baseDada"] is not None:
        base_cell = d["baseDada"]
    elif d["hayRE"]:
        base_cell = fx(sumif_c("Resultado del ejercicio", "D"), d["base"])
    else:
        base_cell = None
    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Marco contable", marco, "Mismo cálculo en ambos marcos; cambian las citas"],
        ["Tipo de compañía", d["tipoCompania"], "Escritura de constitución"],
        ["Utilidad líquida base de la reserva legal", base_cell,
         "Dato del auditor" if d["baseDada"] is not None else "Saldo inicial del resultado del ejercicio (utilidad que la junta apropia en el período)"],
        ["% de la utilidad para reserva legal", d["pct"], f"{defecto}mínimo 10 % de la utilidad líquida hasta por lo menos el 50 % del capital (Ley de Compañías art. 297, anónimas); 5 % de las utilidades líquidas y realizadas hasta por lo menos 20 % (art. 109, limitadas); vigente al corte"],
        ["Nivel mínimo de la reserva legal a partir del cual cesa la apropiación obligatoria (% del capital)", d["tope"], f"{'por defecto según el tipo de compañía; ' if not d['topeDado'] else ''}mínimo 10 % de la utilidad líquida hasta por lo menos el 50 % del capital (Ley de Compañías art. 297, anónimas); 5 % de las utilidades líquidas y realizadas hasta por lo menos 20 % (art. 109, limitadas); vigente al corte"],
        ["Capital suscrito según escritura / Supercias", d["capitalEscritura"], "Escritura inscrita / portal Supercias"],
        ["Utilidades disponibles según el auditor", d["dispAuditor"], "Vacío: se calculan en 06_Dividendos (Ley de Compañías arts. 208 y 298: solo beneficios realmente obtenidos y percibidos o reservas de libre disposición)"],
        ["Reservas expresas efectivas de libre disposición", d["libres"], "Ley de Compañías art. 298: también sirven para pagar dividendos"],
        ["% mínimo de dividendos sobre los beneficios líquidos", d["pctMin"],
         f"{'' if d['parametros'].get('pctDividendoMinimo') not in (None, '') else 'por defecto; '}Ley de Compañías art. 297: al menos el 50 %, salvo resolución unánime; 30 % en emisores inscritos en el Catastro Público del Mercado de Valores; vigente al corte"],
        ["Resolución unánime de la junta sobre las utilidades", d["unanime"], "Ley de Compañías art. 297: con resolución unánime no aplica el mínimo"],
    ]

    # 03 · Movimiento patrimonial.
    mov = []
    for i, c in enumerate(cs):
        r = FILA0 + i
        mov.append([c["id"], c["cuenta"], c["clase"], n2(c["inicial"]), n2(c["aumentos"]), n2(c["disminuciones"]),
                    fx(f"D{r}+E{r}-F{r}", c["recalculado"]), n2(c["final"]), fx(f"H{r}-G{r}", c["difMov"]),
                    None if c["mayor"] is None else n2(c["mayor"]), fx(f'IF(J{r}<>"",H{r}-J{r},"")', c["difMayor"])])
    tot_mov = ["TOTAL", "", "", suma("D", fin_c, sum(c["inicial"] for c in cs)), suma("E", fin_c, sum(c["aumentos"] for c in cs)),
               suma("F", fin_c, sum(c["disminuciones"] for c in cs)), suma("G", fin_c, sum(c["recalculado"] for c in cs)),
               suma("H", fin_c, t["patrimonioCliente"]), suma("I", fin_c, sum(c["difMov"] for c in cs)),
               fx(f'IF(COUNT(J{FILA0}:J{fin_c})=0,"",SUM(J{FILA0}:J{fin_c}))', t.get("saldoMayor")),
               fx(f'IF(COUNT(J{FILA0}:J{fin_c})=0,"",SUM(K{FILA0}:K{fin_c}))', t.get("difMayor"))]

    # 04 · Actas y transacciones.
    txr = []
    for i, x in enumerate(tx):
        r = FILA0 + i
        txr.append([
            x["doc"], x["fecha"], x["tipo"], n2(x["importe"]), x["acta"], x["fechaActa"] or None, x["inscripcion"] or None,
            x["devolucion"], x["obligacion"], x["cuenta"], x["pasivoCorte"], x["resultado"],
            x["efectiva"],
            fx(f'IF(IF(F{r}<>"",F{r},B{r})>{corte},"Sí","No")', "Sí" if x["posterior"] else "No"),
            fx(f'IF(AND(C{r}="Dividendo declarado",N{r}="No"),D{r},0)', x["divPeriodo"]),
            fx(f'IF(AND(C{r}="Dividendo declarado",N{r}="Sí",K{r}="Sí"),D{r},0)', x["divPostPasivo"]),
            fx(f'IF(AND(C{r}="Aumento de capital",B{r}<={corte},OR(G{r}="",G{r}>{corte})),D{r},0)', x["noInscrito"]),
            fx(f'IF(AND(C{r}="Aporte",H{r}="Sí"),D{r},0)', x["aportePasivo"]),
            fx(f'IF(AND(I{r}="Sí",NOT(AND(C{r}="Aporte",H{r}="Sí"))),D{r},0)', x["instrPasivo"]),
            fx(f'IF(AND(C{r}="Recompra",L{r}<>""),L{r},0)', x["resRecompra"]),
            fx(f'IF(AND(E{r}<>"Sí",OR(C{r}="Aumento de capital",C{r}="Aporte",C{r}="Dividendo declarado",C{r}="Apropiación de reserva",'
               f'C{r}="Recompra")),"Sí","No")', x["sinActa"]),
        ])
    tot_tx = (["TOTAL", None, "", suma("D", fin_t, sum(x["importe"] for x in tx)), "", None, None, "", "", "", "", None, None, "",
               suma("O", fin_t, t["dividendosDeclarados"]), suma("P", fin_t, t["dividendosPosterioresPasivo"]),
               suma("Q", fin_t, t["aumentosNoInscritos"]), suma("R", fin_t, t["aportesPasivo"]), suma("S", fin_t, t["instrumentosPasivo"]),
               suma("T", fin_t, t["resultadoRecompras"]), ""] if tx else None)

    # 05 · Reserva legal.
    b = lambda k: f"B{RSF[k]}"
    c_ = lambda k: f"C{RSF[k]}"
    reserva = [
        ["Utilidad líquida base", fx(f'IF({_pb("utilidadNeta")}="","",{_pb("utilidadNeta")})', d["base"]), None, "02_Parametros"],
        ["% de la utilidad para reserva legal", None, fx(f'{_pb("pctReserva")}/100', d["pct"] / 100), f"Ley de Compañías arts. 297 y 109 ({d['tipoCompania'].lower()})"],
        ["Reserva calculada sobre la utilidad", fx(f'IF({b("base")}="","",MAX({b("base")},0)*{c_("pct")})', rv["calc"]), None, "Utilidad positiva × %"],
        ["Capital según cliente", fx(sumif_c("Capital", "H"), rv["capital"]), None, "03_Movimiento"],
        ["Nivel mínimo de la reserva (% del capital)", None, fx(f'{_pb("topeReserva")}/100', d["tope"] / 100), "Ley de Compañías arts. 297 y 109"],
        ["Nivel mínimo de la reserva legal (cesa la apropiación obligatoria)", fx(f'{b("capital")}*{c_("tope")}', rv["topeImp"]), None, "Capital × % del nivel mínimo"],
        ["Reserva legal inicial", fx(sumif_c("Reserva legal", "D"), rv["inicial"]), None, "03_Movimiento"],
        ["Margen hasta el nivel mínimo", fx(f'MAX({b("topeImp")}-{b("inicial")},0)', rv["margen"]), None, "Nivel mínimo − reserva inicial"],
        ["Reserva legal requerida", fx(f'IF({b("calc")}="","",MIN({b("calc")},{b("margen")}))', rv["requerida"]), None, "mín(calculada, margen)"],
        ["Reserva legal apropiada en el período", fx(sumif_c("Reserva legal", "E"), rv["apropiada"]), None, "Aumentos de la cuenta (03_Movimiento)"],
        ["Por apropiar (+) / exceso (−)", fx(f'IF({b("requerida")}="","",{b("requerida")}-{b("apropiada")})', rv["ajuste"]), None, "Requerida − apropiada"],
        ["Reserva legal final según cliente", fx(sumif_c("Reserva legal", "H"), rv["final"]), None, "03_Movimiento"],
        ["Reserva final sobre el nivel mínimo", fx(f'MAX({b("final")}-{b("topeImp")},0)', rv["excesoTope"]), None, "Informativo"],
    ]

    # 06 · Dividendos.
    bd = lambda k: f"B{DVF[k]}"
    dividendos = [
        ["Resultados acumulados (saldo inicial)", fx(sumif_c("Resultados acumulados", "D"), dv["ra"]), "03_Movimiento"],
        ["Resultado del ejercicio anterior (saldo inicial)", fx(sumif_c("Resultado del ejercicio", "D"), dv["re"]), "03_Movimiento"],
        ["Utilidades antes de la reserva legal", fx(f'MAX({bd("ra")}+{bd("re")},0)', dv["antes"]), ""],
        ["(−) Reserva legal requerida", fx(f'IF({RES}B{RSF["requerida"]}="",0,{RES}B{RSF["requerida"]})', dv["req"]), "05_Reserva_legal"],
        ["(+) Reservas expresas de libre disposición", fx(f'IF({_pb("reservasLibreDisposicion")}="",0,{_pb("reservasLibreDisposicion")})', dv["libres"]),
         "Ley de Compañías art. 298"],
        ["Utilidades disponibles calculadas", fx(f'MAX({bd("antes")}-{bd("req")},0)+{bd("libres")}', dv["calc"]), ""],
        ["Utilidades disponibles según el auditor", fx(f'IF({_pb("utilidadesDisponibles")}="","",{_pb("utilidadesDisponibles")})', d["dispAuditor"]),
         "02_Parametros (líquidas y realizadas)"],
        ["Utilidades disponibles usadas", fx(f'IF({bd("aud")}<>"",{bd("aud")},{bd("calc")})', dv["disp"]), ""],
        ["Dividendos declarados en el período", fx(f"SUM({_rg(TX, 'O', nt)})", dv["declarados"]), f"04_Transacciones · {cit['dist']}"],
        ["Dividendos en exceso de utilidades disponibles", fx(f'MAX({bd("declarados")}-{bd("disp")},0)', dv["exceso"]), "Ley de Compañías arts. 208 y 298"],
        ["Dividendos declarados después del cierre", fx(f'SUMIFS({_rg(TX, "D", nt)},{_rg(TX, "C", nt)},"Dividendo declarado",{_rg(TX, "N", nt)},"Sí")', dv["post"]),
         f"Revelar · {cit['rev']}"],
        ["De ellos registrados como pasivo al corte", fx(f"SUM({_rg(TX, 'P', nt)})", dv["postPasivo"]), f"Error · {cit['post']}"],
        ["Dividendos pagados en el período", fx(f'SUMIFS({_rg(TX, "D", nt)},{_rg(TX, "C", nt)},"Dividendo pagado",{_rg(TX, "N", nt)},"No")', dv["pagados"]), "04_Transacciones"],
        ["Beneficios líquidos base del mínimo legal (utilidad − reserva legal requerida)",
         fx(f'IF({RES}B{RSF["base"]}="","",MAX({RES}B{RSF["base"]}-{bd("req")},0))', dv["minBase"] if dv["minBase"] is not None else ""),
         "05_Reserva_legal · Ley de Compañías art. 297"],
        ["Dividendo mínimo legal", fx(f'IF(OR({bd("minBase")}="",{_pb("resolucionUnanime")}="Sí"),"",{bd("minBase")}*{_pb("pctDividendoMinimo")}/100)',
                                      dv["minimo"] if dv["minimo"] is not None else ""),
         "Art. 297: 50 % salvo resolución unánime (30 % en emisores inscritos en el Catastro Público del Mercado de Valores); vigente al corte"],
        ["Dividendos por debajo del mínimo legal", fx(f'IF({bd("minimo")}="","",MAX({bd("minimo")}-{bd("declarados")},0))',
                                                      dv["falta"] if dv["falta"] is not None else ""), "Faltante por asignar"],
    ]

    # 07 · Capital.
    bc = lambda k: f"B{CPF[k]}"
    capital = [
        ["Capital según cliente", fx(sumif_c("Capital", "H"), cp["capital"]), "03_Movimiento"],
        ["Capital según escritura / Supercias", fx(f'IF({_pb("capitalEscritura")}="","",{_pb("capitalEscritura")})', cp["esc"]), "02_Parametros"],
        ["Diferencia cliente − escritura", fx(f'IF({bc("esc")}="","",{bc("capital")}-{bc("esc")})', cp["dif"]), ""],
        ["Aumentos de capital del período", fx(f'SUMIF({_rg(TX, "C", nt)},"Aumento de capital",{_rg(TX, "D", nt)})', cp["aumentos"]), "04_Transacciones"],
        ["Aumentos no inscritos al corte", fx(f"SUM({_rg(TX, 'Q', nt)})", cp["noInsc"]), "Registro Mercantil"],
        ["Aportes para futuras capitalizaciones según cliente", fx(sumif_c("Aportes futuras capitalizaciones", "H"), cp["aportes"]), "03_Movimiento"],
        ["Capital menos aumentos no inscritos", fx(f'{bc("capital")}-{bc("noInsc")}', cp["neto"]), ""],
        ["Diferencia no explicada por aumentos no inscritos", fx(f'IF({bc("esc")}="","",{bc("neto")}-{bc("esc")})', cp["noExpl"]), ""],
    ]

    # 08 · Clasificación deuda / patrimonio.
    cla = []
    for i, x in enumerate(tx):
        if not (x["aportePasivo"] or x["instrPasivo"]):
            continue
        r, rt = FILA0 + len(cla), FILA0 + i
        motivo = "Aporte con obligación de devolución" if x["aportePasivo"] else "Obligación contractual de entregar efectivo"
        cla.append([x["doc"], x["tipo"], x["cuenta"], fx(f"{TX}D{rt}", n2(x["importe"])), x["devolucion"], x["obligacion"],
                    fx(f"{TX}R{rt}+{TX}S{rt}", x["aportePasivo"] + x["instrPasivo"]), f"{motivo} ({cit['clas']})"])
    fin_cla = FILA0 + len(cla) - 1
    tot_cla = (["TOTAL", "", "", suma("D", fin_cla, t["aportesPasivo"] + t["instrumentosPasivo"]), "", "",
                suma("G", fin_cla, t["aportesPasivo"] + t["instrumentosPasivo"]), ""] if cla else None)

    # 09 · Recompra de acciones propias.
    rec = []
    for i, x in enumerate(tx):
        if x["tipo"] != "Recompra":
            continue
        r, rt = FILA0 + len(rec), FILA0 + i
        rec.append([x["doc"], x["fecha"], fx(f"{TX}D{rt}", n2(x["importe"])), x["cuenta"],
                    fx(f'IF({TX}J{rt}="","",IF({TX}J{rt}="Acciones propias","Sí","No"))',
                       "" if not x["cuenta"] else ("Sí" if x["cuenta"] == "Acciones propias" else "No")),
                    fx(f"{TX}T{rt}", x["resRecompra"]), fx(f"ABS(F{r})", abs(x["resRecompra"]))])
    fin_rec = FILA0 + len(rec) - 1
    tot_rec = (["TOTAL", None, suma("C", fin_rec, sum(x["importe"] for x in tx if x["tipo"] == "Recompra")), "", "",
                suma("F", fin_rec, t["resultadoRecompras"]), suma("G", fin_rec, sum(abs(x["resRecompra"]) for x in tx)) ] if rec else None)

    # 10 · Patrimonio auditado y ajustes.
    a = lambda k: f"B{AJF[k]}"
    ajuste = [
        ["Patrimonio según cliente", fx(f"SUM({_rg(MOV, 'H', nc)})", t["patrimonioCliente"]), "03_Movimiento"],
        ["(−) Aportes con obligación de devolución (a pasivo)", fx(f"SUM({_rg(TX, 'R', nt)})", t["aportesPasivo"]), f"08_Clasificacion · {cit['clas']}"],
        ["(−) Instrumentos con obligación contractual (a pasivo)", fx(f"SUM({_rg(TX, 'S', nt)})", t["instrumentosPasivo"]), f"08_Clasificacion · {cit['clas']}"],
        ["(+) Dividendos posteriores registrados como pasivo (revertir)", fx(f"SUM({_rg(TX, 'P', nt)})", t["dividendosPosterioresPasivo"]), cit["post"]],
        ["Patrimonio auditado", fx(f"{a('cliente')}-{a('aportesPasivo')}-{a('instrumentosPasivo')}+{a('divPost')}", t["patrimonioAuditado"]), ""],
        ["Ajuste neto propuesto al patrimonio", fx(f"{a('auditado')}-{a('cliente')}", t["ajusteNeto"]), "Negativo: disminuye el patrimonio"],
        ["Diferencias del movimiento recalculado (absolutas)", fx(f"SUMPRODUCT(ABS({_rg(MOV, 'I', nc)}))", t["difMovimiento"]), cit["ecp"]],
        ["Patrimonio según el mayor", fx(f'IF(COUNT({_rg(MOV, "J", nc)})=0,"",SUM({_rg(MOV, "J", nc)}))', t.get("saldoMayor")), "03_Movimiento"],
        ["Diferencia cliente − mayor", fx(f'IF({a("mayor")}="","",{a("cliente")}-{a("mayor")})', t.get("difMayor")), "NIA 500"],
        ["Reserva legal requerida", fx(f"{RES}B{RSF['requerida']}", t.get("reservaRequerida")), "05_Reserva_legal"],
        ["Reserva legal apropiada", fx(f"{RES}B{RSF['apropiada']}", rv["apropiada"]), "05_Reserva_legal"],
        ["Reserva legal por apropiar (− exceso)", fx(f"{RES}B{RSF['ajuste']}", t.get("ajusteReserva")), "Reclasificación dentro del patrimonio"],
        ["Dividendos declarados en el período", fx(f"{DIV}B{DVF['declarados']}", t["dividendosDeclarados"]), "06_Dividendos"],
        ["Utilidades disponibles para dividendos", fx(f"{DIV}B{DVF['disp']}", t["utilidadesDisponibles"]), "06_Dividendos"],
        ["Dividendos en exceso de utilidades disponibles", fx(f"{DIV}B{DVF['exceso']}", t["excesoDividendos"]), "06_Dividendos"],
        ["Dividendo mínimo legal (art. 297)", fx(f"{DIV}B{DVF['minimo']}", t.get("dividendoMinimoLegal", "")), "06_Dividendos"],
        ["Dividendos por debajo del mínimo legal", fx(f"{DIV}B{DVF['falta']}", t.get("dividendosBajoMinimo", "")), "06_Dividendos"],
        ["Aumentos de capital no inscritos al corte", fx(f"{CAP}B{CPF['noInsc']}", t["aumentosNoInscritos"]), "07_Capital"],
        ["Capital según cliente", fx(f"{CAP}B{CPF['capital']}", t["capitalCliente"]), "07_Capital"],
        ["Capital según escritura / Supercias", fx(f"{CAP}B{CPF['esc']}", t.get("capitalEscritura")), "07_Capital"],
        ["Diferencia capital cliente − escritura", fx(f"{CAP}B{CPF['dif']}", t.get("difCapital")), "07_Capital"],
        ["Resultado reconocido por recompras", fx(f"SUM({_rg(TX, 'T', nt)})", t["resultadoRecompras"]), f"09_Recompra · {cit['propias']}"],
    ]

    # 11 · Asientos (importes remiten a 10_Ajuste).
    asientos = []

    def asiento(titulo, lineas):
        for i, (cta, formula, valor, debe) in enumerate(lineas):
            v = fx(formula, n2(valor))
            asientos.append([titulo if i == 0 else "", cta, v if debe else None, None if debe else v])

    ajb = lambda k: f"{AJ}B{AJF[k]}"
    if t["aportesPasivo"] > 0.005:
        asiento("1 · Aportes con obligación de devolución", [("Aportes para futuras capitalizaciones (patrimonio)", ajb("aportesPasivo"), t["aportesPasivo"], True),
                                                            ("Cuentas por pagar a accionistas / socios (pasivo)", ajb("aportesPasivo"), t["aportesPasivo"], False)])
    if t["instrumentosPasivo"] > 0.005:
        asiento("2 · Instrumentos con obligación contractual", [("Capital / acciones preferentes (patrimonio)", ajb("instrumentosPasivo"), t["instrumentosPasivo"], True),
                                                               ("Pasivo financiero (acciones rescatables)", ajb("instrumentosPasivo"), t["instrumentosPasivo"], False)])
    if t["dividendosPosterioresPasivo"] > 0.005:
        asiento("3 · Reversión de dividendos posteriores", [("Dividendos por pagar", ajb("divPost"), t["dividendosPosterioresPasivo"], True),
                                                           ("Resultados acumulados", ajb("divPost"), t["dividendosPosterioresPasivo"], False)])
    if abs(t.get("ajusteReserva", 0)) > 0.005:
        pos = t["ajusteReserva"] > 0
        asiento("4 · Reserva legal", [("Resultados acumulados" if pos else "Reserva legal", f"ABS({ajb('ajusteReserva')})", abs(t["ajusteReserva"]), True),
                                      ("Reserva legal" if pos else "Resultados acumulados / reserva facultativa", f"ABS({ajb('ajusteReserva')})", abs(t["ajusteReserva"]), False)])
    if abs(t["resultadoRecompras"]) > 0.005:
        perdida = t["resultadoRecompras"] < 0
        asiento("5 · Resultado de recompras al patrimonio", [
            ("Otras reservas / acciones propias (patrimonio)" if perdida else "Resultados del ejercicio (ganancia por recompra)",
             f"ABS({ajb('resultadoRecompras')})", abs(t["resultadoRecompras"]), True),
            ("Resultados del ejercicio (pérdida por recompra)" if perdida else "Otras reservas / acciones propias (patrimonio)",
             f"ABS({ajb('resultadoRecompras')})", abs(t["resultadoRecompras"]), False)])
    if t["aumentosNoInscritos"] > 0.005:
        asiento("6 · Aumentos de capital no inscritos (VERIFICAR Supercias)", [
            ("Capital social", ajb("noInscritos"), t["aumentosNoInscritos"], True),
            ("Aportes para futuras capitalizaciones", ajb("noInscritos"), t["aumentosNoInscritos"], False)])

    ref_res = {"patrimonioCliente": "cliente", "patrimonioAuditado": "auditado", "ajusteNeto": "ajusteNeto", "aportesPasivo": "aportesPasivo",
               "instrumentosPasivo": "instrumentosPasivo", "dividendosPosterioresPasivo": "divPost", "difMovimiento": "difMov",
               "saldoMayor": "mayor", "difMayor": "difMayor", "reservaRequerida": "reservaReq", "reservaApropiada": "reservaAprop",
               "ajusteReserva": "ajusteReserva", "dividendosDeclarados": "divDeclarados", "utilidadesDisponibles": "disponibles",
               "excesoDividendos": "excesoDiv", "dividendoMinimoLegal": "divMinimo", "dividendosBajoMinimo": "divBajoMinimo",
               "aumentosNoInscritos": "noInscritos", "capitalCliente": "capitalCliente",
               "capitalEscritura": "capitalEscritura", "difCapital": "difCapital", "resultadoRecompras": "resultadoRecompras"}
    resumen = [[res["labels"][k], fx(ajb(ref_res[k]), t[k])] for k in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Movimiento", "Movimiento patrimonial",
             [["Código", "t"], ["Cuenta", "t"], ["Clase", "t"], ["Saldo inicial", "n"], ["Aumentos", "n"], ["Disminuciones", "n"],
              ["Final recalculado", "n"], ["Final según cliente", "n"], ["Diferencia", "n"], ["Final según mayor", "n"], ["Cliente − mayor", "n"]],
             mov, tot_mov),
        hoja("04_Transacciones", "Actas y transacciones",
             [["Referencia", "t"], ["Fecha", "d"], ["Tipo", "t"], ["Importe", "n"], ["Acta", "t"], ["Fecha del acta", "d"], ["Inscripción", "d"],
              ["Devolución", "t"], ["Obligación contractual", "t"], ["Cuenta afectada", "t"], ["Pasivo al corte", "t"], ["Resultado reconocido", "n"],
              ["Fecha efectiva (acta o registro)", "d"], ["Posterior al corte", "t"], ["Dividendo del período", "n"], ["Dividendo posterior como pasivo", "n"],
              ["Aumento no inscrito", "n"], ["Aporte a pasivo", "n"], ["Instrumento a pasivo", "n"], ["Resultado de recompra", "n"], ["Sin acta", "t"]],
             txr, tot_tx),
        hoja("05_Reserva_legal", "Reserva legal", [["Concepto", "t"], ["Importe", "n"], ["Porcentaje", "p"], ["Referencia", "t"]], reserva),
        hoja("06_Dividendos", "Dividendos", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], dividendos),
        hoja("07_Capital", "Capital y aumentos", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], capital),
        hoja("08_Clasificacion", "Clasificación deuda / patrimonio",
             [["Referencia", "t"], ["Tipo", "t"], ["Cuenta", "t"], ["Importe", "n"], ["Devolución", "t"], ["Obligación contractual", "t"],
              ["A reclasificar a pasivo", "n"], ["Fundamento", "t"]], cla, tot_cla),
        hoja("09_Recompra", "Recompra de acciones propias",
             [["Referencia", "t"], ["Fecha", "d"], ["Costo", "n"], ["Cuenta", "t"], ["Deducida como acciones propias", "t"],
              ["Resultado reconocido", "n"], ["A reclasificar al patrimonio", "n"]], rec, tot_rec),
        hoja("10_Ajuste", "Patrimonio auditado y ajustes", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], ajuste),
        hoja("11_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos),
        hoja("12_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -----------------------------------------------------------------

def definicion() -> dict:
    mov = ("Una fila por cuenta patrimonial: código, nombre, clase (capital, aportes para futuras capitalizaciones, reserva legal, otras reservas, "
           "otros resultados integrales, resultados acumulados, resultado del ejercicio, acciones propias), saldo inicial, aumentos y disminuciones "
           "del período (en positivo), saldo final según el cliente y, si se tiene, saldo final según el mayor. Saldos con el signo del patrimonio "
           "(acreedor positivo; acciones propias y pérdidas en negativo). Sin filas de total.")
    tx = ("Una fila por acta o movimiento patrimonial del período (y por cada aporte o instrumento vigente al corte cuya clasificación se prueba): "
          "referencia, fecha, tipo (aumento de capital, aporte, dividendo declarado, dividendo pagado, apropiación de reserva, recompra, otro), "
          "importe, acta de junta (sí/no) y su fecha, fecha de inscripción en el Registro Mercantil, obligación de devolución (sí/no), obligación "
          "contractual de entregar efectivo (sí/no), cuenta afectada, si quedó registrado como pasivo al corte (sí/no) e importe reconocido en "
          "resultados. Incluya los dividendos declarados después del cierre hasta la fecha del informe.")
    return {
        "name": "Patrimonio",
        "area": "Patrimonio",
        "processor": "patrimonio",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Recalcula el movimiento de cada cuenta patrimonial y lo concilia con el cliente y el mayor; mide la reserva legal requerida "
                    "(parámetros de la Ley de Compañías por tipo de compañía) frente a la apropiada; prueba que los dividendos declarados no "
                    "superen las utilidades disponibles y que los declarados después del cierre no estén como pasivo; coteja el capital con la "
                    "escritura / Supercias y la inscripción de los aumentos; reclasifica a pasivo los aportes con obligación de devolución y los "
                    "instrumentos con obligación contractual de entregar efectivo, y verifica que las recompras se deduzcan del patrimonio sin "
                    "resultado. Mismo cálculo en NIIF completas (NIC 32, NIC 1, NIC 10, CINIIF 17) y PYMES (Secciones 22, 6 y 32); cambian las citas."),
        "source": {"organization": "IFRS Foundation (texto en español: Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIC 32 párr. 11 (instrumento de patrimonio: participación residual), 15 (clasificación según el fondo económico), "
                                "16 a) (patrimonio solo si no hay obligación contractual de entregar efectivo), 16A–16D (instrumentos con opción de "
                                "venta), 18 a) (acción preferente rescatable = pasivo financiero), 33 (acciones propias: se deducen del patrimonio; "
                                "sin pérdida ni ganancia en resultados), 35 (distribuciones directamente en el patrimonio); NIC 1 párr. 79 a) "
                                "(revelaciones por clase de capital), 106–110 (estado de cambios en el patrimonio: conciliación por componente), "
                                "107 (dividendos reconocidos y por acción), 137 a) (dividendos propuestos o declarados no reconocidos); NIC 10 párr. "
                                "12–13 (dividendos declarados después del cierre no son pasivo); CINIIF 17 párr. 10–11 (reconocimiento del dividendo "
                                "a pagar y medición de los dividendos en especie a valor razonable; rige distribuciones distintas del efectivo: para dividendos en efectivo el "
                                "soporte es NIC 32.35 y NIC 10.12–13) — leídos en EUR-Lex. Desde 2027: NIC 1.106 → NIIF 18.107; NIC 1.79 → NIIF 18.130; "
                                "NIC 1.137 a) → NIIF 18.132 a)."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015 y 2025: Sección 22 párr. 22.3–22.6 (clasificación como pasivo o patrimonio), "
                                      "22.7–22.10 (emisión de acciones y aportes), 22.16 (acciones propias), 22.17–22.18 (distribuciones y "
                                      "dividendos en especie); Sección 6 (estado de cambios en el patrimonio); párr. 32.8 (dividendos declarados "
                                      "después del período: presentación) y 32.10 (revelación). Leídos en PYMES 2015 (ES) y 2025 (EN): misma "
                                      "numeración para los párrafos citados."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del movimiento patrimonial contra el mayor."},
            {"document": "NIA 330", "section": "párr. 20", "requirement": "Conciliar el estado de cambios en el patrimonio con los registros."},
            {"document": "NIA 250 (Revisada)", "section": "párr. 14", "requirement": "Cumplimiento de la Ley de Compañías (reserva legal, dividendos, inscripción de aumentos)."},
            {"document": "NIA 560", "section": "párr. 6–9", "requirement": "Hechos posteriores: dividendos declarados después del cierre."},
            {"document": "NIA 580", "section": "párr. 11 y 13", "requirement": "Manifestaciones escritas sobre actas de junta entregadas en su totalidad."},
        ],
        "calculo": [
            "Movimiento: final recalculado = saldo inicial + aumentos − disminuciones; diferencia = final según cliente − recalculado; cliente − mayor.",
            "Reserva legal: calculada = máx(utilidad líquida, 0) × % (por defecto: mínimo 10 % de la utilidad líquida hasta por lo menos el 50 % del capital (Ley de Compañías art. 297, anónimas); 5 % de las utilidades líquidas y realizadas hasta por lo menos 20 % (art. 109, limitadas); vigente al corte); "
            "nivel mínimo (a partir del cual cesa la apropiación obligatoria; no es un techo) = capital × % (50 % / 20 %); requerida = mín(calculada, máx(nivel mínimo − reserva inicial, 0)); por apropiar = requerida − aumentos de la reserva.",
            "Dividendos: disponibles = máx(resultados acumulados iniciales + resultado del ejercicio anterior, 0) − reserva legal requerida + reservas "
            "expresas efectivas de libre disposición (Ley de Compañías art. 298) (o el importe de utilidades líquidas y realizadas que fije el auditor); "
            "exceso = declarados del período − disponibles.",
            "Mínimo legal de dividendos (Ley de Compañías art. 297): salvo resolución unánime del capital concurrente a la junta, al menos el 50 % de los "
            "beneficios líquidos del ejercicio luego de las deducciones (aquí, utilidad líquida − reserva legal requerida); 30 % en los emisores cuyas "
            "acciones están inscritas en el Catastro Público del Mercado de Valores. Faltante = mínimo − declarados.",
            "Dividendo declarado después del cierre (fecha del acta posterior al corte) registrado como pasivo al corte: revertir (NIC 10 12; PYMES 32.8) y revelar.",
            "Capital: capital según cliente − escritura / Supercias; aumentos del período sin inscripción en el Registro Mercantil al corte.",
            "Clasificación: aporte con obligación de devolución e instrumento con obligación contractual de entregar efectivo → pasivo (NIC 32 16, 18 a); PYMES 22.3–22.6).",
            "Recompra: resultado reconocido en resultados → se reclasifica al patrimonio; la recompra se presenta como acciones propias deducidas (NIC 32 33; PYMES 22.16).",
            "Patrimonio auditado = patrimonio según cliente − aportes a pasivo − instrumentos a pasivo + dividendos posteriores revertidos; ajuste neto = auditado − cliente.",
        ],
        "fields": _MOV, "rules": [], "control": CONTROL, "primary": "ajusteNeto",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "PAT-01", "objective": "Movimiento patrimonial", "risk": "Estado de cambios en el patrimonio que no concilia", "assertion": "Exactitud / Integridad",
             "procedure": "Recalcular inicial + aumentos − disminuciones por cuenta y conciliar con el cliente y el mayor", "evidence": "Mayor, estado de cambios en el patrimonio",
             "criterion": "Diferencia cero o explicada", "source": "NIC 1 106–110 · PYMES Sección 6 · NIA 500"},
            {"code": "PAT-02", "objective": "Capital y aportes", "risk": "Capital no respaldado por escritura inscrita; aportes que son pasivo", "assertion": "Existencia / Clasificación",
             "procedure": "Cotejar el capital con la escritura y Supercias, la inscripción de los aumentos y las condiciones de devolución de los aportes",
             "evidence": "Escrituras, razón de inscripción, portal Supercias, actas", "criterion": "Capital igual a lo inscrito; aportes sin obligación de devolución",
             "source": "NIC 32 16 · PYMES 22.3–22.10 · Ley de Compañías"},
            {"code": "PAT-03", "objective": "Reserva legal y otras reservas", "risk": "Reserva legal no apropiada o en exceso", "assertion": "Exactitud / Cumplimiento",
             "procedure": "Recalcular la reserva legal requerida con el % y el nivel mínimo del tipo de compañía", "evidence": "Actas de junta, mayor",
             "criterion": "Apropiado igual a lo requerido", "source": "Ley de Compañías arts. 297 y 109"},
            {"code": "PAT-04", "objective": "Dividendos", "risk": "Dividendos sobre utilidades no disponibles; dividendo posterior como pasivo", "assertion": "Ocurrencia / Corte",
             "procedure": "Comparar dividendos declarados con las utilidades disponibles (incluidas las reservas de libre disposición) y con el mínimo legal del art. 297; revisar actas posteriores al cierre",
             "evidence": "Actas, pagos, estados de cuenta", "criterion": "Mínimo legal ≤ declarados ≤ disponibles; posteriores revelados, no registrados",
             "source": "NIC 32 35 · NIC 10 12–13 · NIC 1 137 · CINIIF 17 · PYMES 22.17, 32.8 · Ley de Compañías arts. 297 y 298"},
            {"code": "PAT-05", "objective": "Resultados acumulados", "risk": "Traspasos del resultado mal registrados", "assertion": "Exactitud",
             "procedure": "Verificar el traspaso del resultado del ejercicio anterior, la apropiación de reservas y los dividendos contra resultados acumulados",
             "evidence": "Mayor y actas", "criterion": "Movimiento conciliado", "source": "NIC 1 106 d) · PYMES 6.3"},
            {"code": "PAT-06", "objective": "Recompra de acciones", "risk": "Resultado reconocido por operaciones con acciones propias", "assertion": "Presentación",
             "procedure": "Revisar que las recompras se deduzcan del patrimonio y que no afecten resultados", "evidence": "Actas, contratos de compra, asientos",
             "criterion": "Sin pérdida ni ganancia en resultados", "source": "NIC 32 33 · PYMES 22.16"},
            {"code": "PAT-07", "objective": "Clasificación deuda / patrimonio", "risk": "Instrumentos con obligación contractual presentados como patrimonio", "assertion": "Clasificación",
             "procedure": "Analizar los términos de acciones preferentes, aportes e instrumentos con opción de venta", "evidence": "Estatutos, contratos, actas",
             "criterion": "Pasivo si hay obligación contractual de entregar efectivo", "source": "NIC 32 11, 15–16D, 18 · PYMES 22.3–22.6"},
        ],
        "requests": [
            req("RQ-001", "Movimiento de las cuentas patrimoniales del período con saldos según el mayor", "movimientos", "PAT-01",
                "Población a recalcular y conciliar con el mayor", content=mov),
            req("RQ-002", "Actas y transacciones patrimoniales (aumentos, aportes, dividendos, reservas, recompras, instrumentos)", "transacciones", "PAT-02",
                "Dividendos, capital, clasificación y recompras", content=tx),
            req("RQ-003", "Libro de actas de junta general del período y posteriores al cierre", None, "PAT-04", "Sustento de declaraciones y apropiaciones",
                formats=("pdf",), use="soporte"),
            req("RQ-004", "Escrituras de constitución y aumentos de capital con razón de inscripción; certificado de Supercias", None, "PAT-02",
                "Capital suscrito e inscripción", formats=("pdf",), use="soporte"),
            req("RQ-005", "Contratos o estatutos de acciones preferentes, aportes e instrumentos con opción de venta", None, "PAT-07",
                "Clasificación deuda / patrimonio", formats=("pdf", "docx"), use="soporte", required=False),
            req("RQ-006", "Estado de cambios en el patrimonio y nota de patrimonio", None, "PAT-01", "Presentación y revelación",
                formats=("xlsx", "pdf"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) -------------------------------------------------------

def _mv(id, cuenta, clase, inicial, aumentos, disminuciones, final, mayor):
    return {"id": id, "cuenta": cuenta, "clase": clase, "inicial": inicial, "aumentos": aumentos, "disminuciones": disminuciones,
            "final": final, "mayor": mayor, "_row": 2}


def _tx(id, fecha_, tipo, importe, **extra):
    return {"id": id, "fecha": fecha_, "tipo": tipo, "importe": importe, "_row": 2, **extra}


# Corte 2025-12-31, compañía anónima (10 % hasta 50 % del capital).
# Patrimonio según cliente 935.000; ajuste = −30.000 (aporte reembolsable) − 45.000 (acciones rescatables) + 50.000
# (dividendo de feb-2026 registrado como pasivo) = −25.000 → auditado 910.000.
# Reserva legal: 128.000 × 10 % = 12.800 (tope 250.000 − 60.000 = 190.000) vs 8.000 apropiada → faltan 4.800.
# Dividendos 90.000 vs disponibles 80.000 (auditor) → exceso 10.000 (calculadas: 150.000 + 128.000 − 12.800 + 25.000 de
# reserva facultativa de libre disposición = 290.200; art. 298). Mínimo legal: (128.000 − 12.800) × 50 % = 57.600 ≤ 90.000.
# ORI: 12.000 + 3.500 = 15.500 vs 15.000 informado → −500. Resultado del ejercicio: mayor 143.200 → −1.200.
# Capital 500.000 vs escritura 460.000 → 40.000 = aumento JGA-2025-04 no inscrito.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tipoCompania": "Anónima", "capitalEscritura": 460000, "utilidadesDisponibles": 80000,
                   "reservasLibreDisposicion": 25000, "pctDividendoMinimo": 50, "resolucionUnanime": "No"},
    "datasets": {
        "movimientos": [
            _mv("301", "Capital suscrito y pagado", "Capital", "400000", "100000", "0", "500000", "500000"),
            _mv("302", "Aportes para futuras capitalizaciones", "Aportes", "100000", "30000", "100000", "30000", "30000"),
            _mv("304", "Reserva legal", "Reserva legal", "60000", "8000", "0", "68000", "68000"),
            _mv("305", "Reserva facultativa", "Reserva facultativa", "25000", "0", "0", "25000", "25000"),
            _mv("306", "Otros resultados integrales", "ORI", "12000", "3500", "0", "15000", "15000"),
            _mv("307", "Resultados acumulados", "Resultados acumulados", "150000", "120000", "140000", "130000", "130000"),
            _mv("308", "Resultado del ejercicio", "Resultado del ejercicio", "128000", "142000", "128000", "142000", "143200"),
            _mv("309", "Acciones propias en cartera", "Acciones propias", "0", "0", "20000", "-20000", "-20000"),
            _mv("310", "Acciones preferentes rescatables", "Otra", "0", "45000", "0", "45000", "45000"),
        ],
        "transacciones": [
            _tx("JGA-2025-01", "2025-03-28", "Aumento de capital", "60000", acta="Sí", fecha_acta="2025-03-20", inscripcion="2025-05-15", cuenta="Capital"),
            _tx("JGA-2025-02", "2025-04-15", "Apropiación de reserva", "8000", acta="Sí", fecha_acta="2025-03-20", cuenta="Reserva legal"),
            _tx("JGA-2025-03", "2025-04-15", "Dividendo declarado", "90000", acta="Sí", fecha_acta="2025-03-20", cuenta="Resultados acumulados", pasivo_corte="No"),
            _tx("EG-2025-118", "2025-05-30", "Dividendo pagado", "90000", acta="Sí", fecha_acta="2025-03-20", cuenta="Resultados acumulados"),
            _tx("AP-2025-01", "2025-06-10", "Aporte", "30000", acta="Sí", fecha_acta="2025-06-05", devolucion="Sí", cuenta="Aportes futuras capitalizaciones"),
            _tx("JGA-2025-05", "2025-08-12", "Recompra", "20000", acta="Sí", fecha_acta="2025-08-01", cuenta="Acciones propias", resultado="-1500"),
            _tx("JGA-2025-06", "2025-09-30", "Otro", "45000", acta="Sí", fecha_acta="2025-09-15", obligacion="Sí", cuenta="Otra",
                concepto="Acciones preferentes rescatables en 2028"),
            _tx("JGA-2025-04", "2025-11-30", "Aumento de capital", "40000", acta="No", cuenta="Capital"),
            _tx("AS-2025-ORI", "2025-12-31", "Otro", "3500", acta="", cuenta="ORI", concepto="Revaluación de terrenos"),
            _tx("JGA-2026-01", "2025-12-31", "Dividendo declarado", "50000", acta="Sí", fecha_acta="2026-02-20", cuenta="Resultados acumulados", pasivo_corte="Sí"),
        ],
    },
}

_MOV_SIN_MAYOR = [{k: v for k, v in f.items() if k != "mayor"} for f in EJEMPLO["datasets"]["movimientos"]]
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025_limitada", {"movimientos": _MOV_SIN_MAYOR}, {"_marco": MARCO_PYMES, "_edicion": "2025", "tipoCompania": "Limitada"}, EJEMPLO["corte"]),
    ("completas_perdida", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "utilidadNeta": -5000, "utilidadesDisponibles": None,
                                                "pctReserva": 10, "topeReserva": 50}, EJEMPLO["corte"]),
    ("dividendo_bajo_el_minimo", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "utilidadNeta": 400000, "resolucionUnanime": "No"},
     EJEMPLO["corte"]),
]
