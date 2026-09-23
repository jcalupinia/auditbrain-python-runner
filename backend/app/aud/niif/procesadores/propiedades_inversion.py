"""Propiedades de inversión (NIC 40 y NIIF 13 · NIIF para las PYMES sección 16; 2025 con la sección 12).

Versión simple que cumple la norma, una cédula por prueba de la matriz del socio (MÓDULO 05):

1. Clasificación (NIC 40.5-14; PYMES 16.2-16.4): alquiler, plusvalía, uso futuro no determinado o en
   construcción → propiedad de inversión; uso propio → PPE; venta en el curso normal → inventario. Uso mixto:
   en NIIF completas, si las partes pueden venderse por separado se contabiliza por partes (NIC 40.10) y si no
   se aplica el umbral de uso propio (parámetro; 40.10 solo es PI si el uso propio es insignificante). En PYMES
   NO hay umbral: las partes se separan siempre (16.4) y, si el VR de la parte de inversión no se mide con
   fiabilidad sin costo o esfuerzo desproporcionado, todo el inmueble va a PPE (sección 17).
2. Costo inicial (NIC 40.20-24; PYMES 16.5): precio de compra + desembolsos directamente atribuibles vs costo
   registrado.
3. Valor razonable (NIC 40.33-55, NIIF 13; PYMES 16.7 y, 2025, sección 12): ajuste = VR − importe en libros, a
   resultados (NIC 40.35). Si una partida no tiene VR fiable → costo (NIC 40.53 / PYMES 16.8).
4. Modelo del costo (NIC 40.56 → NIC 16; PYMES sección 17 y 27): depreciación en meses completos
   (costo − terreno) × MIN(1, meses ÷ (vida × 12)); deterioro = MAX(0, neto − importe recuperable). En PYMES,
   cuando el VR dejó de medirse con fiabilidad, el importe en libros a esa fecha es el nuevo costo y los meses
   se cuentan DESDE esa fecha, no desde la adquisición (16.8); sin la fecha no se recalcula y se avisa.
5. Transferencias (NIC 40.57-65; PYMES 16.8-16.9): diferencia VR − libros a la fecha del cambio a resultados
   (desde inventario, 40.63) o como revaluación NIC 16 (desde PPE, 40.61-62); costo atribuido = VR (40.60).
   Desde PPE revaluada: el aumento va a otro resultado integral y acumula superávit de revaluación (40.62 b ii,
   NIC 16.39); la disminución se imputa primero contra el superávit de ESE mismo inmueble y solo el exceso a
   resultados (40.62 a, NIC 16.40). El superávit permanece en patrimonio y solo puede transferirse directamente
   a resultados acumulados, nunca a resultados del ejercicio (NIC 16.41). La cédula 10 lleva el historial por
   inmueble (saldo inicial, movimiento, uso y saldo final). Sin el dato del superávit el reparto queda vacío (M22).
6. Ingresos por alquiler: según contratos vs registrados.
7. Bajas (NIC 40.66-73): resultado = producto neto − importe en libros (40.69).

Ruta: NIIF completas → modelo elegido por la entidad (parámetro «modelo»); PYMES → valor razonable solo si
«vr_sin_esfuerzo_desproporcionado» = sí, si no costo (16.7-16.8).
Ajuste propuesto = propiedades de inversión auditadas − saldo del mayor.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m, norm, problema, r2, ref, req,
    validar_campos, validar_definicion_generica,
)

VERSION = "propiedades_inversion 1.1"
RUBRO = "PROPIEDADES_INVERSION"

_INMUEBLES = [
    campo("id", "Código del inmueble", alias=("codigo", "inmueble", "referencia", "cod"), ejemplo="IP-01"),
    campo("descripcion", "Descripción", alias=("detalle", "nombre", "ubicacion"), ejemplo="Edificio de oficinas Norte"),
    campo("uso", "Uso actual (Alquiler / Plusvalía / Uso propio / Venta / Uso futuro no determinado / En construcción)",
          alias=("uso actual", "destino", "proposito"), ejemplo="Alquiler"),
    campo("pct_uso_propio", "% de uso propio (0 a 100)", "number", requerido=False, alias=("uso propio", "porcentaje uso propio"), ejemplo=0),
    campo("separable", "¿Las partes pueden venderse por separado? (Sí/No)", requerido=False, alias=("se puede separar", "partes separables"), ejemplo="No"),
    campo("costo", "Costo registrado", "number", alias=("costo historico", "costo de adquisicion", "costo original"), ejemplo=500000),
    campo("fecha_adquisicion", "Fecha de adquisición (disponible para su uso)", "date", requerido=False,
          alias=("fecha compra", "fecha adquisicion", "fecha de alta"), ejemplo="2018-03-01"),
    campo("precio_compra", "Precio de compra (escritura)", "number", requerido=False, alias=("precio", "valor escritura"), ejemplo=""),
    campo("costos_atribuibles", "Desembolsos directamente atribuibles (honorarios, impuestos de transferencia)", "number",
          requerido=False, alias=("costos de transaccion", "gastos notariales", "alcabalas"), ejemplo=""),
    campo("terreno", "Parte del costo que es terreno (no depreciable)", "number", requerido=False, alias=("valor terreno", "costo terreno"), ejemplo=100000),
    campo("vida_util", "Vida útil (años)", "number", requerido=False, alias=("vida", "anos vida util"), ejemplo=40),
    campo("dep_acumulada", "Depreciación acumulada registrada", "number", requerido=False, alias=("depreciacion acumulada", "dep acum"), ejemplo=""),
    campo("vr_anterior", "Valor razonable del año anterior", "number", requerido=False, alias=("vr anterior", "valor razonable anterior"), ejemplo=700000),
    campo("vr_corte", "Valor razonable al corte", "number", requerido=False, alias=("valor razonable", "vr", "avaluo", "tasacion"), ejemplo=720000),
    campo("fuente_vr", "Fuente del valor razonable / tasador", requerido=False, alias=("tasador", "perito", "fuente"), ejemplo="Perito independiente"),
    campo("nivel_vr", "Nivel de jerarquía del VR (1, 2 o 3)", requerido=False, alias=("nivel", "jerarquia"), ejemplo="Nivel 2"),
    campo("importe_libros", "Importe en libros registrado al corte", "number", alias=("saldo", "valor en libros", "importe en libros", "saldo contable"), ejemplo=700000),
    campo("ingresos_alquiler", "Ingresos por alquiler del año según contratos", "number", requerido=False,
          alias=("canon anual", "renta anual", "ingresos segun contrato"), ejemplo=48000),
    campo("ingresos_registrados", "Ingresos por alquiler registrados", "number", requerido=False,
          alias=("ingresos contables", "ingresos registrados", "renta registrada"), ejemplo=48000),
    campo("transferencia", "Cambio de uso en el año (PPE→PI, Inventario→PI, PI→PPE, PI→Inventario)", requerido=False,
          alias=("cambio de uso", "reclasificacion", "traspaso"), ejemplo=""),
    campo("fecha_transferencia", "Fecha del cambio de uso", "date", requerido=False, alias=("fecha cambio de uso", "fecha traspaso"), ejemplo=""),
    campo("libros_transferencia", "Importe en libros a la fecha del cambio", "number", requerido=False, alias=("libros al cambio",), ejemplo=""),
    campo("vr_transferencia", "Valor razonable a la fecha del cambio", "number", requerido=False, alias=("vr al cambio",), ejemplo=""),
    campo("superavit_revaluacion", "Superávit de revaluación acumulado en otro resultado integral de este inmueble a la fecha del cambio de uso",
          "number", requerido=False, alias=("superavit de revaluacion", "reserva de revaluacion", "superavit ori", "superavit revaluacion"), ejemplo=""),
    campo("importe_recuperable", "Importe recuperable (solo si hay indicio de deterioro)", "number", requerido=False,
          alias=("recuperable", "valor recuperable"), ejemplo=""),
]
CAMPOS = {
    "inmuebles": _INMUEBLES,
    "bajas": [
        campo("id", "Código del inmueble dado de baja", alias=("codigo", "inmueble"), ejemplo="B-01"),
        campo("descripcion", "Descripción", requerido=False, alias=("detalle", "nombre"), ejemplo="Local Quevedo"),
        campo("fecha_baja", "Fecha de la venta o retiro", "date", alias=("fecha venta", "fecha de baja"), ejemplo="2025-08-31"),
        campo("producto_neto", "Producto neto de la venta", "number", alias=("precio de venta", "ingreso neto", "producto"), ejemplo=130000),
        campo("importe_libros", "Importe en libros a la fecha de baja", "number", alias=("valor en libros", "costo neto"), ejemplo=110000),
        campo("resultado_registrado", "Ganancia (pérdida) registrada", "number", requerido=False, alias=("utilidad registrada", "resultado"), ejemplo=20000),
    ],
}
TIPOS = {"inmuebles": "inmuebles", "bajas": "bajas"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "inmuebles"
CONTROL = "importe_libros"

PARAMETROS = {"modelo": "valor_razonable", "vr_sin_esfuerzo_desproporcionado": "sí", "umbral_uso_propio": 10, "saldoMayor": None}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "modelo": "Modelo aplicado por la entidad (valor_razonable / costo)",
    "vr_sin_esfuerzo_desproporcionado": "PYMES: ¿el VR se mide con fiabilidad sin costo o esfuerzo desproporcionado? (sí / no)",
    "umbral_uso_propio": "Uso propio significativo desde (% del inmueble)",
    "saldoMayor": "Saldo de propiedades de inversión según el mayor",
}
TOTAL_EJEMPLO = "ajuste"

USOS = ("Alquiler", "Plusvalía", "Uso propio", "Venta", "Uso futuro no determinado", "En construcción")
TRANSFERENCIAS = ("PPE→PI", "Inventario→PI", "PI→PPE", "PI→Inventario")
PI = "Propiedad de inversión"
PI_PARTE = "Propiedad de inversión (parte)"
PPE_MIXTO = "PPE (uso mixto sin VR fiable: sección 17)"
VR = "valor_razonable"
TRAT_PPE = ("Revaluación NIC 16: el aumento a otro resultado integral (superávit de revaluación) y la disminución contra el superávit de ese inmueble, el exceso a resultados (NIC 40.61-62)")
SIN_SUP = "Sin tratamiento: falta el superávit de revaluación a la fecha"
DESTINO_SI = "Permanece en patrimonio: transferible a resultados acumulados, nunca a resultados del ejercicio (NIC 40.62 b ii y NIC 16.41)"
DESTINO_NO = "Sin saldo de superávit al cierre"


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    return validar_campos(CAMPOS[tipo], filas)


# --- normalización ---------------------------------------------------------------

def _opt(v):
    """Número opcional: vacío → None (M22: lo no medido queda vacío, nunca 0)."""
    return a_num(v) if str(v if v is not None else "").strip() else None


def _txt(v) -> str:
    return str(v if v is not None else "").strip()


def _uso(v) -> str:
    s = norm(v)
    for claves, uso in ((("propio", "administr", "oficinaspropias"), "Uso propio"), (("venta", "vender"), "Venta"),
                        (("plusval",), "Plusvalía"), (("futuro", "nodetermin"), "Uso futuro no determinado"),
                        (("construc",), "En construcción"), (("alquil", "arrend", "renta"), "Alquiler")):
        if any(c in s for c in claves):
            return uso
    return _txt(v)


def _si_no(v) -> str:
    s = norm(v)
    return "Sí" if s in ("si", "s", "yes", "x", "true") else ("No" if s in ("no", "n", "false") else _txt(v))


def _transf(v) -> str:
    raw = _txt(v)
    if not raw:
        return ""
    partes = [norm(x) for x in re.split(r"→|->|>|/|\s+a\s+|\s+hacia\s+", raw.lower()) if norm(x)]
    lado = []
    for x in partes:
        if "invent" in x or "existenc" in x:
            lado.append("Inventario")
        elif x in ("pi", "ip") or "inversi" in x:
            lado.append("PI")
        elif "ppe" in x or "propio" in x or "planta" in x:
            lado.append("PPE")
    t = "→".join(lado)
    return t if t in TRANSFERENCIAS else raw


def _meses(a: date | None, b: date) -> int | None:
    """DATEDIF(a, b, "m") de Excel: meses completos; 0 si a es posterior."""
    if a is None:
        return None
    if a > b:
        return 0
    n = (b.year - a.year) * 12 + b.month - a.month
    return n - 1 if b.day < a.day else n


def _parametros(parametros: dict) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    mo = norm(p["modelo"])
    if "cost" in mo:
        p["modelo"] = "costo"
    elif "razonable" in mo or mo in ("vr", "valor", "fv"):
        p["modelo"] = VR
    else:
        raise ValueError("Modelo aplicado por la entidad: indique valor_razonable o costo.")
    s = _si_no(p["vr_sin_esfuerzo_desproporcionado"])
    if s not in ("Sí", "No"):
        raise ValueError("PYMES: indique sí o no en «VR sin costo o esfuerzo desproporcionado».")
    p["vr_sin_esfuerzo_desproporcionado"] = s.lower()
    u = a_num(p["umbral_uso_propio"])
    if u is None or not 0 <= u <= 100:
        raise ValueError(f"{ETIQUETAS_PARAM['umbral_uso_propio']}: use un porcentaje entre 0 y 100.")
    p["umbral_uso_propio"] = float(u)
    p["saldoMayor"] = None if p.get("saldoMayor") in (None, "") else a_num(p["saldoMayor"])
    return p


def _inicio(c: date) -> date:
    try:
        return date(c.year - 1, c.month, c.day) + timedelta(days=1)
    except ValueError:                                   # 29 de febrero
        return date(c.year - 1, c.month, 28) + timedelta(days=1)


# --- cálculo -------------------------------------------------------------------

def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = _parametros(parametros)
    pymes, edicion = es_pymes(p), edicion_pymes(p)
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    inicio = _inicio(corte_a)
    correcto = (VR if p["vr_sin_esfuerzo_desproporcionado"] == "sí" else "costo") if pymes else p["modelo"]
    umbral = p["umbral_uso_propio"]

    its = []
    for f in datasets.get("inmuebles") or []:
        costo, libros = a_num(f.get("costo")), a_num(f.get("importe_libros"))
        if costo is None or libros is None:
            continue
        g = lambda k: _opt(f.get(k))
        fd = lambda k: fecha(f.get(k)) if _txt(f.get(k)) else None
        it = {"id": _txt(f.get("id")), "desc": _txt(f.get("descripcion")), "uso": _uso(f.get("uso")), "pct": g("pct_uso_propio"),
              "sep": _si_no(f.get("separable")), "costo": costo, "fadq": fd("fecha_adquisicion"), "precio": g("precio_compra"),
              "atrib": g("costos_atribuibles"), "terreno": g("terreno"), "vida": g("vida_util"), "depReg": g("dep_acumulada"),
              "vrAnt": g("vr_anterior"), "vr": g("vr_corte"), "fuente": _txt(f.get("fuente_vr")), "nivel": _txt(f.get("nivel_vr")),
              "libros": libros, "alq": g("ingresos_alquiler"), "alqReg": g("ingresos_registrados"),
              "transf": _transf(f.get("transferencia")), "ftr": fd("fecha_transferencia"), "libTr": g("libros_transferencia"),
              "vrTr": g("vr_transferencia"), "sup0": g("superavit_revaluacion"), "rec": g("importe_recuperable"), "_row": f.get("_row")}
        if it["vida"] is not None and it["vida"] <= 0:
            it["vida"] = None
        # 1 · clasificación. PYMES 16.4: el uso mixto NO usa el umbral, se separan las partes; si el VR de la parte de
        # inversión no se mide sin costo o esfuerzo desproporcionado, todo el inmueble va a PPE (sección 17).
        # NIIF completas: con partes separables se contabiliza por partes aunque el uso propio no pase el umbral (NIC 40.10).
        mixto = it["pct"] is not None and 0 < it["pct"] < 100
        if it["uso"] == "Venta":
            it["clase"] = "Inventario (NIC 2)" if not pymes else "Inventario (sección 13)"
        elif it["uso"] == "Uso propio":
            it["clase"] = "PPE (uso propio)"
        elif pymes and mixto:
            it["clase"] = PPE_MIXTO if p["vr_sin_esfuerzo_desproporcionado"] == "no" else PI_PARTE
        elif mixto and not pymes and it["sep"] == "Sí":
            it["clase"] = PI_PARTE
        elif it["pct"] is not None and it["pct"] > umbral:
            it["clase"] = "PPE (uso propio significativo)"
        else:
            it["clase"] = PI
        it["parte"] = 1.0 if it["clase"] == PI else (1 - it["pct"] / 100 if it["clase"] == PI_PARTE else 0.0)
        it["esPI"] = it["parte"] > 0
        it["reclas"] = None if it["parte"] == 1 else -libros * (1 - it["parte"])
        # 2 · costo inicial
        it["costoRec"] = None if it["precio"] is None else it["precio"] + (it["atrib"] if it["atrib"] is not None else 0)
        it["difCosto"] = None if it["costoRec"] is None else it["costoRec"] - costo
        it["costoAud"] = it["costoRec"] if it["costoRec"] is not None else costo
        # 3 · valor razonable
        if not it["esPI"]:
            it["medida"] = "No es PI"
        elif correcto == VR:
            it["medida"] = "Valor razonable" if it["vr"] is not None else "Costo (VR no fiable)"
        else:
            it["medida"] = "Costo"
        it["varVR"] = None if it["vr"] is None or it["vrAnt"] is None else it["vr"] - it["vrAnt"]
        it["ajVR"] = (it["vr"] - libros) * it["parte"] if it["medida"] == "Valor razonable" else None
        # 4 · modelo del costo. PYMES 16.8: si el VR dejó de medirse, el importe en libros a esa fecha es el nuevo
        # costo y la depreciación corre DESDE esa fecha (no desde la adquisición).
        it["aplica"] = it["medida"].startswith("Costo")
        it["p16_8"] = pymes and it["medida"] == "Costo (VR no fiable)"
        c = {k: None for k in ("base", "meses", "dep", "depAnio", "difDep", "neto", "det", "medCosto", "costoDep", "desdeDep")}
        if it["aplica"]:
            c["costoDep"] = (it["libTr"] if it["libTr"] is not None else it["costoAud"]) if it["p16_8"] else it["costoAud"]
            c["desdeDep"] = it["ftr"] if it["p16_8"] else it["fadq"]
            c["base"] = c["costoDep"] - (it["terreno"] if it["terreno"] is not None else 0)
            c["meses"] = _meses(c["desdeDep"], corte_a)
            if c["base"] == 0:
                c["dep"], c["depAnio"] = 0, 0
            elif it["vida"] is not None and c["meses"] is not None:
                c["dep"] = c["base"] * min(1, c["meses"] / (it["vida"] * 12))
                c["depAnio"] = c["dep"] - c["base"] * min(1, max(0, c["meses"] - 12) / (it["vida"] * 12))
            c["difDep"] = None if c["dep"] is None or it["depReg"] is None else c["dep"] - it["depReg"]
            usada = c["dep"] if c["dep"] is not None else (it["depReg"] if it["depReg"] is not None else 0)
            c["neto"] = c["costoDep"] - usada
            c["det"] = None if it["rec"] is None else max(0, c["neto"] - it["rec"])
            c["medCosto"] = c["neto"] - (c["det"] if c["det"] is not None else 0)
        it.update(c)
        # medición auditada (solo la parte que es propiedad de inversión)
        it["aud"] = 0 if not it["esPI"] else (it["vr"] if it["medida"] == "Valor razonable" else it["medCosto"]) * it["parte"]
        it["ajuste"] = it["aud"] - libros
        it["efCosto"] = (it["medCosto"] - libros) * it["parte"] if it["aplica"] else None
        # 6 · alquileres
        it["difAlq"] = None if it["alq"] is None or it["alqReg"] is None else it["alq"] - it["alqReg"]
        its.append(it)
    if not its:
        raise ValueError("Cargue el registro de propiedades de inversión (un inmueble por fila) al corte.")

    # 5 · transferencias
    trs = []
    for k, it in enumerate(its):
        if not it["transf"]:
            continue
        t = it["transf"]
        x = {"k": k, "id": it["id"], "transf": t, "fecha": it["ftr"], "clase": it["clase"], "lib": it["libTr"], "vr": it["vrTr"],
             "sup0": it["sup0"]}
        x["enEj"] = "Sin fecha" if it["ftr"] is None else ("Sí" if inicio <= it["ftr"] <= corte_a else "No")
        x["dif"] = None if pymes or correcto != VR or x["lib"] is None or x["vr"] is None else x["vr"] - x["lib"]
        if pymes:
            x["trat"] = "PYMES 16.9: transferir solo cuando cumple o deja de cumplir la definición de PI; la sección 16 no regula la medición de la diferencia (juicio, sección 10)"
        elif correcto != VR:
            x["trat"] = "Modelo del costo: sin cambio del importe en libros (NIC 40.59)"
        elif t == "PPE→PI":
            x["trat"] = TRAT_PPE
        elif t == "Inventario→PI":
            x["trat"] = "Diferencia a resultados (NIC 40.63)"
        elif t in ("PI→PPE", "PI→Inventario"):
            x["trat"] = "Costo atribuido = VR a la fecha del cambio (NIC 40.60)"
        else:
            x["trat"] = "Transferencia no reconocida"
        # NIC 40.61-62 · NIC 16.39-40: el aumento va a ORI (superávit de revaluación) y la disminución se imputa
        # primero contra el superávit de ESE inmueble; solo el exceso va a resultados. Sin el superávit informado
        # no se puede repartir → vacío y problema (M22), nunca 0 por omisión.
        if x["dif"] is None:
            x["uso"] = x["res"] = x["ori"] = None
        elif t == "Inventario→PI":
            x["uso"], x["res"], x["ori"] = 0, x["dif"], 0
        elif t != "PPE→PI":
            x["uso"], x["res"], x["ori"] = 0, 0, 0
        elif x["dif"] >= 0:
            x["uso"], x["res"], x["ori"] = 0, 0, x["dif"]
        elif x["sup0"] is None:
            x["uso"] = x["res"] = x["ori"] = None
        else:
            x["uso"] = min(x["sup0"], -x["dif"])
            x["res"], x["ori"] = x["dif"] + x["uso"], -x["uso"]
        if t not in TRANSFERENCIAS:
            x["estado"] = "Transferencia no reconocida"
        elif x["fecha"] is None:
            x["estado"] = "Sin tratamiento: falta la fecha del cambio"
        elif not pymes and correcto == VR and (x["lib"] is None or x["vr"] is None):
            x["estado"] = "Sin tratamiento: falta importe en libros o VR a la fecha"
        elif t == "PPE→PI" and x["dif"] is not None and x["dif"] < 0 and x["sup0"] is None:
            x["estado"] = SIN_SUP
        elif (t.endswith("PI") and not it["esPI"]) or (t.startswith("PI") and it["esPI"]):
            x["estado"] = "Incoherente con la clasificación actual"
        else:
            x["estado"] = "Completa"
        trs.append(x)

    # Historial del superávit de revaluación por inmueble (NIC 16.39-41; NIC 40.62).
    sups = []
    for k, it in enumerate(its):
        j = next((n for n, y in enumerate(trs) if y["k"] == k and y["transf"] == "PPE→PI"), None)
        if it["sup0"] is None and j is None:
            continue
        x = trs[j] if j is not None else None
        sup = {"k": k, "t": j, "id": it["id"], "transf": x["transf"] if x else "", "fecha": x["fecha"] if x else None,
               "ini": it["sup0"]}
        if x is None or (not pymes and correcto != VR):
            sup["mov"], sup["uso"] = 0, 0
        elif x["ori"] is None:
            sup["mov"], sup["uso"] = None, None
        else:
            sup["mov"], sup["uso"] = max(0, x["ori"]), x["uso"]
        sup["fin"] = None if sup["ini"] is None or sup["mov"] is None or sup["uso"] is None else sup["ini"] + sup["mov"] - sup["uso"]
        sup["destino"] = "" if sup["fin"] is None else (DESTINO_SI if sup["fin"] > 0.005 else DESTINO_NO)
        sups.append(sup)

    # 7 · bajas
    bajas = []
    for f in datasets.get("bajas") or []:
        fb, pn, lb = fecha(f.get("fecha_baja")), a_num(f.get("producto_neto")), a_num(f.get("importe_libros"))
        if fb is None or pn is None or lb is None:
            continue
        rr = _opt(f.get("resultado_registrado"))
        x = {"id": _txt(f.get("id")), "desc": _txt(f.get("descripcion")), "fecha": fb, "prod": pn, "lib": lb, "res": pn - lb, "reg": rr}
        x["dif"] = None if rr is None else x["res"] - rr
        bajas.append(x)

    # Totales (mismo orden de suma que Excel).
    S = lambda xs: sum(x for x in xs if x is not None)
    libros_t = S(i["libros"] for i in its)
    mayor = p["saldoMayor"] if p["saldoMayor"] is not None else libros_t
    t = {"piAuditado": S(i["aud"] for i in its), "saldoMayor": mayor}
    t["ajuste"] = t["piAuditado"] - mayor
    t["libros"] = libros_t
    t["difDetalleMayor"] = libros_t - mayor
    t["ajusteVR"] = S(i["ajVR"] for i in its)
    t["efectoCosto"] = S(i["efCosto"] for i in its)
    t["reclasificacion"] = S(i["reclas"] for i in its)
    t["depreciacionAnio"] = S(i["depAnio"] for i in its)
    t["difDepreciacion"] = S(i["difDep"] for i in its)
    t["deterioro"] = S(i["det"] for i in its)
    t["variacionVR"] = S(i["varVR"] for i in its)
    t["difCostoInicial"] = S(i["difCosto"] for i in its)
    t["transfResultados"] = S(x["res"] for x in trs)
    t["transfORI"] = S(x["ori"] for x in trs)
    t["usoSuperavit"] = S(x["uso"] for x in trs)
    t["superavitFinal"] = S(x["fin"] for x in sups)
    t["difAlquileres"] = S(i["difAlq"] for i in its)
    t["resultadoBajas"] = S(x["res"] for x in bajas)
    t["difBajas"] = S(x["dif"] for x in bajas)
    conc = {"mayor": mayor, "libros": libros_t, "dif": libros_t - mayor, "vr": t["ajusteVR"], "costo": t["efectoCosto"],
            "reclas": t["reclasificacion"]}
    conc["puente"] = libros_t + conc["vr"] + conc["costo"] + conc["reclas"]
    conc["control"] = t["piAuditado"]
    conc["difControl"] = conc["puente"] - conc["control"]
    conc["ajuste"] = conc["control"] - mayor

    # Problemas (M22: cada «debe» de la norma que el cálculo no garantiza).
    n40 = lambda c, s: s if pymes else c
    lista = lambda xs: ", ".join(xs[:6]) + (" …" if len(xs) > 6 else "")
    pr = []
    mal = [i for i in its if not i["esPI"]]
    if mal:
        pr.append(problema("MAL_CLASIFICADO", f"Inmuebles que no son propiedad de inversión: {lista([i['id'] + ' (' + i['clase'] + ')' for i in mal])}. "
                           f"Reclasificar {m(-sum(i['reclas'] for i in mal))} fuera de la cuenta y medirlos con su norma "
                           f"({n40('NIC 40.9 y 40.10; si venían a VR, el costo atribuido es el VR a la fecha del cambio, 40.60', 'PYMES 16.2 y 16.4')}).",
                           t["reclasificacion"]))
    sep = [i for i in its if i["clase"] == PI_PARTE]
    if sep:
        motivo = ("PYMES 16.4: en el uso mixto se separan las partes sin aplicar umbral alguno" if pymes else
                  "NIC 40.10: las partes pueden venderse por separado, así que se contabilizan por separado")
        pr.append(problema("USO_MIXTO_SEPARADO", f"Uso mixto separado en partes: {lista([i['id'] + ' (' + m(i['pct']) + ' % de uso propio)' for i in sep])}. {motivo}. "
                           f"La parte de uso propio se reclasifica a PPE por {m(-sum(i['reclas'] for i in sep))} y la de inversión se mide como propiedad de "
                           "inversión. La herramienta separa a prorrata del % de uso propio: divida la fila del anexo y mida cada parte por separado.",
                           sum(i["reclas"] for i in sep)))
    mixto_ppe = [i["id"] for i in its if i["clase"] == PPE_MIXTO]
    if mixto_ppe:
        pr.append(problema("USO_MIXTO_A_PPE", f"{lista(mixto_ppe)}: uso mixto en el que el valor razonable de la parte de inversión no se mide con fiabilidad sin "
                           "costo o esfuerzo desproporcionado; todo el inmueble se contabiliza como propiedad, planta y equipo (PYMES 16.4 y sección 17)."))
    raro = [i["id"] for i in its if i["uso"] not in USOS]
    if raro:
        pr.append(problema("USO_NO_RECONOCIDO", f"Uso no reconocido en {lista(raro)}: se trató como propiedad de inversión. Indique Alquiler, Plusvalía, "
                           "Uso propio, Venta, Uso futuro no determinado o En construcción."))
    frac = [i["id"] for i in its if i["pct"] is not None and 0 < i["pct"] < 1]
    if frac:
        pr.append(problema("PCT_USO_FRACCION", f"% de uso propio menor a 1 en {lista(frac)}: el anexo pide 0 a 100 (35 = 35 %). Revise si escribió una fracción."))
    if pymes and p["modelo"] != correcto:
        msg = ("La entidad aplica valor razonable pero el VR no se mide con fiabilidad sin costo o esfuerzo desproporcionado: debe usar el "
               "modelo del costo de la sección 17 (PYMES 16.7-16.8)." if p["modelo"] == VR else
               "La entidad aplica el modelo del costo pero el VR se mide con fiabilidad sin costo o esfuerzo desproporcionado: debe medir al "
               "valor razonable con cambios en resultados (PYMES 16.7).")
        pr.append(problema("PYMES_MODELO", msg + " La herramienta mide con el modelo correcto."))
    if abs(t["ajusteVR"]) > 0.005:
        dif = [i["id"] for i in its if i["ajVR"] and abs(i["ajVR"]) > 0.005]
        pr.append(problema("VR_NO_RECONOCIDO", f"Diferencia entre el valor razonable al corte y el importe en libros no reconocida en {lista(dif)}: "
                           f"{m(t['ajusteVR'])}, a resultados del ejercicio ({n40('NIC 40.35', 'PYMES 16.7')}).", t["ajusteVR"]))
    nf = [i["id"] for i in its if i["medida"] == "Costo (VR no fiable)"]
    if nf:
        pr.append(problema("VR_NO_FIABLE", f"{lista(nf)} sin valor razonable con modelo de VR: se miden al costo. "
                           + ("Solo procede si al adquirirlo o cambiar su uso el VR no podía medirse de forma fiable y continua (NIC 40.53); "
                              "el resto sigue a VR (40.54) y se revela 78." if not pymes else
                              "PYMES 16.8: pasa a la sección 17 hasta que vuelva a haber una medición fiable; revele 16.10(e)(iii).")))
    vr_items = [i for i in its if i["medida"] == "Valor razonable"]
    sf = [i["id"] for i in vr_items if not i["fuente"]]
    if sf:
        pr.append(problema("SIN_FUENTE_VR", f"Valor razonable sin fuente ni tasador en {lista(sf)}: documente la tasación "
                           f"({n40('NIC 40.32 y 75 e; NIIF 13', 'PYMES 16.10 b')}) y evalúe el trabajo del experto (NIA 500.8; NIA 620 si el experto es del auditor)."))
    if not pymes or edicion == "2025":
        sn = [i["id"] for i in vr_items if not i["nivel"]]
        if sn:
            pr.append(problema("SIN_NIVEL_VR", f"Falta el nivel de la jerarquía del VR en {lista(sn)} "
                               f"({n40('NIIF 13.72 y 93 b', 'PYMES 2025 12.22 y 12.28 b')})."))
    if correcto == "costo" and not pymes:
        sv = [i["id"] for i in its if i["esPI"] and i["vr"] is None]
        if sv:
            pr.append(problema("SIN_VR_REVELACION", f"Modelo del costo: falta el valor razonable a revelar de {lista(sv)} (NIC 40.32 y 79 e)."))
    if abs(t["difCostoInicial"]) > 0.005:
        dc = [i["id"] for i in its if i["difCosto"] and abs(i["difCosto"]) > 0.005]
        pr.append(problema("COSTO_INICIAL", f"El costo registrado no es precio de compra + desembolsos directamente atribuibles en {lista(dc)}: "
                           f"{m(t['difCostoInicial'])} ({n40('NIC 40.20-21', 'PYMES 16.5')}).", t["difCostoInicial"]))
    if abs(t["difDepreciacion"]) > 0.005:
        dd = [i["id"] for i in its if i["difDep"] and abs(i["difDep"]) > 0.005]
        pr.append(problema("DEP_DIFERENCIA", f"La depreciación acumulada recalculada difiere de la registrada en {lista(dd)}: {m(t['difDepreciacion'])} "
                           f"({n40('NIC 40.56 → NIC 16', 'PYMES 17.17-17.20')}).", t["difDepreciacion"]))
    sv = [i["id"] for i in its if i["aplica"] and i["dep"] is None]
    if sv:
        pr.append(problema("SIN_VIDA_UTIL", f"Sin vida útil o fecha de base de depreciación en {lista(sv)}: no se recalculó la depreciación (se usa la registrada)."))
    s168 = [i["id"] for i in its if i["p16_8"] and i["ftr"] is None]
    if s168:
        pr.append(problema("SIN_FECHA_FIN_VR", f"{lista(s168)}: el valor razonable dejó de medirse con fiabilidad. Indique la fecha del cambio: desde esa fecha el "
                           "importe en libros pasa a ser el costo y corre la depreciación de la sección 17 (PYMES 16.8); sin ella no se recalcula la depreciación."))
    c168 = [i["id"] for i in its if i["p16_8"] and i["ftr"] is not None and i["libTr"] is None]
    if c168:
        pr.append(problema("SIN_LIBROS_FIN_VR", f"{lista(c168)}: falta el importe en libros a la fecha en que el valor razonable dejó de medirse; ese importe es el "
                           "nuevo costo (PYMES 16.8). Se usa el costo auditado y puede sobrestimar la base depreciable."))
    if t["deterioro"] > 0.005:
        dt = [i["id"] for i in its if i["det"]]
        pr.append(problema("DETERIORO", f"Modelo del costo: el importe recuperable es menor que el valor neto en {lista(dt)}: deterioro {m(t['deterioro'])} "
                           f"({n40('NIC 36.9 y 59', 'PYMES 27.5-27.7')}).", t["deterioro"]))
    if abs(t["difAlquileres"]) > 0.005:
        da = [i["id"] for i in its if i["difAlq"] and abs(i["difAlq"]) > 0.005]
        pr.append(problema("ALQUILER_NO_CONCILIADO", f"Ingresos por alquiler según contratos distintos de los registrados en {lista(da)}: {m(t['difAlquileres'])} "
                           f"({n40('NIIF 16.81 y NIC 40.75 f', 'PYMES 20.25')}).", t["difAlquileres"]))
    sc = [i["id"] for i in its if i["uso"] == "Alquiler" and i["alq"] is None]
    if sc:
        pr.append(problema("ALQUILER_SIN_CONTRATO", f"Inmuebles en alquiler sin ingresos según contrato en {lista(sc)}: no se concilian las rentas."))
    sr = [i["id"] for i in its if i["alq"] is not None and i["alqReg"] is None]
    if sr:
        pr.append(problema("ALQUILER_SIN_REGISTRO", f"Contratos sin ingresos registrados informados en {lista(sr)}: indique lo registrado."))
    st = [x["id"] for x in trs if x["estado"] != "Completa"]
    if st:
        pr.append(problema("TRANSFERENCIA_SIN_TRATAMIENTO", f"Cambios de uso sin tratamiento completo: {lista([x['id'] + ' (' + x['estado'] + ')' for x in trs if x['estado'] != 'Completa'])} "
                           f"({n40('NIC 40.57-65', 'PYMES 16.8-16.9')})."))
    if abs(t["transfResultados"]) > 0.005 or abs(t["transfORI"]) > 0.005:
        pr.append(problema("TRANSFERENCIA", f"Diferencias a la fecha del cambio de uso: a resultados {m(t['transfResultados'])}, a otro resultado integral "
                           f"(superávit de revaluación) {m(t['transfORI'])}. Verifique que se registraron así (NIC 40.61-63).",
                           t["transfResultados"] + t["transfORI"]))
    # Superávit de revaluación (decisión del socio: se mantiene y se arrastra; nunca a resultados del ejercicio).
    sin_sup = [x["id"] for x in sups if x["ini"] is None]
    if sin_sup and not pymes and correcto == VR:
        pr.append(problema("SIN_SUPERAVIT_REVALUACION", f"Falta el superávit de revaluación acumulado en otro resultado integral de {lista(sin_sup)} a la fecha "
                           "del cambio de uso. Papel a revisar: el auxiliar (mayor) de la cuenta de superávit de revaluación de ese inmueble y el estado de "
                           "cambios en el patrimonio del ejercicio. Sin ese dato el saldo del historial queda vacío y, en las disminuciones, no se puede "
                           "repartir entre otro resultado integral y resultados (NIC 40.62 y NIC 16.39-41)."))
    aum = [x["id"] for x in sups if x["mov"] and x["mov"] > 0.005]
    if aum:
        pr.append(problema("SUPERAVIT_AUMENTO", f"Aumento del importe en libros al transferir de propiedad ocupada por el dueño a propiedad de inversión en "
                           f"{lista(aum)}: {m(S(x['mov'] for x in sups))} se reconoce en otro resultado integral e incrementa el superávit de revaluación, no "
                           "en resultados (NIC 40.61-62 b ii y NIC 16.39). Revise el auxiliar de deterioros de esos inmuebles: la parte del aumento que "
                           "revierta una pérdida por deterioro reconocida antes en resultados sí va a resultados (NIC 40.62 b i) y la herramienta no la separa.",
                           S(x["mov"] for x in sups)))
    con = [x["id"] for x in sups if x["uso"] and x["uso"] > 0.005]
    if con:
        exceso = S(x["res"] for x in trs if x["transf"] == "PPE→PI")
        pr.append(problema("SUPERAVIT_CONSUMIDO", f"Disminución del importe en libros al transferir a propiedad de inversión en {lista(con)}: se imputa primero "
                           f"contra el superávit de revaluación de ese mismo inmueble ({m(t['usoSuperavit'])} en otro resultado integral) y solo el exceso a "
                           f"resultados ({m(exceso)}) (NIC 40.62 a y NIC 16.40).", t["usoSuperavit"]))
    if t["superavitFinal"] > 0.005:
        pr.append(problema("SUPERAVIT_EN_PATRIMONIO", f"Superávit de revaluación de propiedades transferidas al cierre: {m(t['superavitFinal'])}. Permanece en "
                           "patrimonio y solo puede transferirse directamente a resultados acumulados (al dar de baja el inmueble o a medida que se usa); esa "
                           "transferencia nunca pasa por el resultado del ejercicio (NIC 40.62 b ii y NIC 16.41). Revise el estado de cambios en el patrimonio.",
                           t["superavitFinal"]))
    ppe_pi = [x["id"] for x in trs if x["transf"] == "PPE→PI"]
    if pymes and ppe_pi:
        pr.append(problema("SUPERAVIT_PYMES", f"{lista(ppe_pi)}: la Sección 16 no regula la medición de la diferencia al transferir a propiedades de inversión "
                           "(PYMES 16.9), así que la herramienta no la calcula en este marco. Si el inmueble se medía con el modelo de revaluación de la "
                           "Sección 17, el aumento va a otro resultado integral y acumula superávit de revaluación, y la disminución se reconoce en otro "
                           "resultado integral en la medida del saldo acreedor del superávit de ese activo (PYMES 17.15C-17.15D); el superávit permanece en "
                           "patrimonio. Documente el tratamiento aplicado."))
    if abs(t["difBajas"]) > 0.005:
        db = [x["id"] for x in bajas if x["dif"] and abs(x["dif"]) > 0.005]
        pr.append(problema("BAJA_RESULTADO", f"Resultado de la baja mal determinado en {lista(db)}: {m(t['difBajas'])}; resultado = producto neto − importe en libros "
                           f"({n40('NIC 40.69', 'PYMES 17.28 y 17.30')}).", t["difBajas"]))
    if p["saldoMayor"] is None:
        pr.append(problema("SIN_MAYOR", "Ingrese el saldo según el mayor: sin él se toma la suma del detalle y no se prueba la conciliación."))
    elif abs(t["difDetalleMayor"]) > 0.005:
        pr.append(problema("DETALLE_MAYOR", f"El detalle de inmuebles ({m(libros_t)}) no concilia con el mayor ({m(mayor)}): {m(t['difDetalleMayor'])}.",
                           t["difDetalleMayor"]))
    if abs(t["ajuste"]) > 0.005:
        pr.append(problema("AJUSTE", f"Las propiedades de inversión auditadas ({m(t['piAuditado'])}) difieren del mayor ({m(mayor)}).", t["ajuste"]))

    iso = lambda d: d.isoformat() if isinstance(d, date) else d
    filas = [{"id": i["id"], "descripcion": i["desc"], "uso": i["uso"], "clasificacion": i["clase"], "medida": i["medida"],
              "importe_libros": r2(i["libros"]), "auditado": r2(i["aud"]), "ajuste": r2(i["ajuste"]), "_row": i["_row"]} for i in its]
    etiquetas = {
        "piAuditado": "Propiedades de inversión auditadas", "saldoMayor": "Saldo según el mayor", "ajuste": "Ajuste propuesto (neto)",
        "libros": "Importe en libros según el detalle", "difDetalleMayor": "Diferencia detalle − mayor",
        "ajusteVR": "Ajuste de valor razonable no reconocido (resultados)", "efectoCosto": "Efecto de la medición al costo (depreciación y deterioro)",
        "reclasificacion": "Reclasificación fuera de propiedades de inversión", "depreciacionAnio": "Depreciación del año (modelo del costo)",
        "difDepreciacion": "Diferencia de depreciación acumulada", "deterioro": "Deterioro (modelo del costo)",
        "variacionVR": "Variación del valor razonable del año", "difCostoInicial": "Diferencia en el costo inicial",
        "transfResultados": "Transferencias: diferencia a resultados", "transfORI": "Transferencias: diferencia a otro resultado integral",
        "usoSuperavit": "Superávit de revaluación usado contra disminuciones", "superavitFinal": "Superávit de revaluación en patrimonio al cierre",
        "difAlquileres": "Diferencia en ingresos por alquiler", "resultadoBajas": "Resultado recalculado en bajas", "difBajas": "Diferencia en el resultado de bajas",
    }
    return {"engine": VERSION, "rows": filas, "totals": {k: r2(t[k]) for k in etiquetas}, "labels": etiquetas, "primary": "ajuste",
            "exceptions": pr, "schedule": [],
            "detalle": {"corte": corte_a.isoformat(), "inicio": inicio.isoformat(), "pymes": pymes, "edicion": edicion, "correcto": correcto,
                        "parametros": p, "tot": t, "conc": conc,
                        "items": [{k: iso(v) for k, v in i.items()} for i in its],
                        "transf": [{k: iso(v) for k, v in x.items()} for x in trs],
                        "sup": [{k: iso(v) for k, v in x.items()} for x in sups],
                        "bajas": [{k: iso(v) for k, v in x.items()} for x in bajas]}}


# --- cédulas con fórmulas ----------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen y ajuste propuesto"), ("02_Parametros", "Parámetros y ruta por marco"), ("03_Inmuebles", "Registro de inmuebles"),
    ("04_Clasificacion", "Clasificación"), ("05_Costo_inicial", "Costo inicial"), ("06_Valor_razonable", "Valor razonable"),
    ("07_Modelo_costo", "Modelo del costo: depreciación y deterioro"), ("08_Medicion", "Medición auditada por inmueble"),
    ("09_Transferencias", "Transferencias"), ("10_Superavit", "Historial del superávit de revaluación"),
    ("11_Alquileres", "Ingresos por alquiler"), ("12_Bajas", "Bajas"),
    ("13_Conciliacion", "Sumaria y conciliación"), ("14_Problemas", "Problemas encontrados"),
]
PARK = ["corte", "inicio", "marco", "esPymes", "modelo", "vr", "correcto", "umbral", "saldoMayor"]
PAR = {k: FILA0 + i for i, k in enumerate(PARK)}
P, INM, CLA, COS, VRZ, MCO, MED, TRA, SUP, ALQ, BAJ = (ref(n) for n, _ in CEDULAS[1:12])


def _pa(k: str) -> str:
    return f"{P}$B${PAR[k]}"


def _rg(hoja_ref: str, col: str, n: int) -> str:
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _tot(col: str, n: int, v):
    return fx(f"SUM({col}{FILA0}:{col}{FILA0 + max(n, 1) - 1})", v)


def _si(celda: str) -> str:
    """Referencia a un dato opcional: vacío sigue vacío (una referencia simple daría 0)."""
    return f'IF({celda}="","",{celda})'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, t, c = d["parametros"], d["tot"], d["conc"]
    its, trs, bajas, sups = d["items"], d["transf"], d["bajas"], d["sup"]
    ni, nt, nb, ns = len(its), len(trs), len(bajas), len(sups)
    pymes = d["pymes"]
    ruta = (f"NIIF para las PYMES {d['edicion']} · sección 16" + (" y sección 12 (medición del VR)" if d["edicion"] == "2025" else " (VR: 11.27-11.32)")
            if pymes else "NIIF completas · NIC 40 y NIIF 13")
    n_ = "n"

    esp_v = "Sí" if pymes else "No"
    parametros = [
        ["Corte del ejercicio", d["corte"], "Ficha del encargo"],
        ["Inicio del ejercicio", d["inicio"], "Corte − 12 meses + 1 día"],
        ["Marco", "NIIF para las PYMES" if pymes else "NIIF completas", ruta],
        ["¿Es PYMES?", fx(f'IF(ISNUMBER(SEARCH("PYMES",{_pa("marco")})),"Sí","No")', esp_v), "Deriva del marco"],
        ["Modelo aplicado por la entidad", p["modelo"], "NIC 40.30 (elección); PYMES 16.7 (no es elección: depende de la medición fiable sin costo o esfuerzo desproporcionado)"],
        ["PYMES: VR fiable sin costo o esfuerzo desproporcionado", p["vr_sin_esfuerzo_desproporcionado"], "Juicio documentado (PYMES 16.7-16.8); sin efecto en NIIF completas"],
        ["Modelo con que se mide (ruta)", fx(f'IF({_pa("esPymes")}="Sí",IF({_pa("vr")}="sí","{VR}","costo"),{_pa("modelo")})', d["correcto"]),
         "Completas: el elegido por la entidad; PYMES: VR solo si es fiable sin esfuerzo desproporcionado"],
        ["Uso propio significativo desde (%)", p["umbral_uso_propio"], "NIC 40.10 exige que la parte de uso propio sea «insignificante»; el umbral es juicio del auditor (NIC 40.10 no fija porcentaje); "
                                                            "solo NIIF completas — en PYMES 16.4 se separan las partes"],
        ["Saldo según el mayor", p["saldoMayor"], "Mayor contable (en blanco: se toma la suma del detalle)"],
    ]

    inm, cla, cos, vrz, mco, med, alq = [], [], [], [], [], [], []
    for k, i in enumerate(its):
        r = FILA0 + k
        inm.append([i["id"], i["desc"], i["uso"], i["pct"], i["sep"], i["costo"], i["fadq"], i["precio"], i["atrib"], i["terreno"], i["vida"],
                    i["depReg"], i["vrAnt"], i["vr"], i["fuente"], i["nivel"], i["libros"], i["alq"], i["alqReg"], i["transf"], i["ftr"],
                    i["libTr"], i["vrTr"], i["sup0"], i["rec"]])
        mixto_f = f'AND(D{r}<>"",D{r}>0,D{r}<100)'
        clase_f = (f'IF(C{r}="Venta",IF({_pa("esPymes")}="Sí","Inventario (sección 13)","Inventario (NIC 2)"),IF(C{r}="Uso propio","PPE (uso propio)",'
                   f'IF(AND({_pa("esPymes")}="Sí",{mixto_f}),IF({_pa("vr")}="no","{PPE_MIXTO}","{PI_PARTE}"),'
                   f'IF(AND({_pa("esPymes")}="No",{mixto_f},E{r}="Sí"),"{PI_PARTE}",'
                   f'IF(AND(D{r}<>"",D{r}>F{r}),"PPE (uso propio significativo)","{PI}")))))')
        cla.append([i["id"], i["desc"], fx(f"{INM}C{r}", i["uso"]), fx(_si(f"{INM}D{r}"), i["pct"]), fx(_si(f"{INM}E{r}"), i["sep"] or None),
                    fx(_pa("umbral"), p["umbral_uso_propio"]), fx(clase_f, i["clase"]), fx(f'IF(K{r}>0,"Sí","No")', "Sí" if i["esPI"] else "No"),
                    fx(f"{INM}Q{r}", i["libros"]), fx(f'IF(K{r}=1,"",-I{r}*(1-K{r}))', i["reclas"]),
                    fx(f'IF(G{r}="{PI}",1,IF(G{r}="{PI_PARTE}",1-D{r}/100,0))', i["parte"])])
        cos.append([i["id"], i["fadq"], fx(_si(f"{INM}H{r}"), i["precio"]), fx(_si(f"{INM}I{r}"), i["atrib"]),
                    fx(f'IF(C{r}="","",C{r}+IF(D{r}="",0,D{r}))', i["costoRec"]), fx(f"{INM}F{r}", i["costo"]),
                    fx(f'IF(E{r}="","",E{r}-F{r})', i["difCosto"]), fx(f'IF(E{r}<>"",E{r},F{r})', i["costoAud"])])
        vrz.append([i["id"], fx(f"{CLA}H{r}", "Sí" if i["esPI"] else "No"),
                    fx(f'IF(B{r}="No","No es PI",IF({_pa("correcto")}="{VR}",IF(E{r}<>"","Valor razonable","Costo (VR no fiable)"),"Costo"))', i["medida"]),
                    fx(_si(f"{INM}M{r}"), i["vrAnt"]), fx(_si(f"{INM}N{r}"), i["vr"]), fx(f'IF(OR(D{r}="",E{r}=""),"",E{r}-D{r})', i["varVR"]),
                    fx(f"{INM}Q{r}", i["libros"]), fx(f'IF(C{r}="Valor razonable",(E{r}-G{r})*{CLA}K{r},"")', i["ajVR"]),
                    fx(_si(f"{INM}O{r}"), i["fuente"] or None), fx(_si(f"{INM}P{r}"), i["nivel"] or None)])
        ap = "Sí" if i["aplica"] else "No"
        mco.append([i["id"], fx(f"{VRZ}C{r}", i["medida"]), fx(f'IF(LEFT(B{r},5)="Costo","Sí","No")', ap),
                    fx(f'IF(C{r}="No","",IF(AND({_pa("esPymes")}="Sí",B{r}="Costo (VR no fiable)",{INM}V{r}<>""),{INM}V{r},{COS}H{r}))', i["costoDep"]),
                    fx(f'IF(C{r}="Sí",IF({INM}J{r}="",0,{INM}J{r}),"")', (i["terreno"] or 0) if i["aplica"] else None),
                    fx(f'IF(C{r}="Sí",D{r}-E{r},"")', i["base"]),
                    fx(f'IF(C{r}="Sí",{_si(f"{INM}K{r}")},"")', i["vida"] if i["aplica"] else None),
                    i["desdeDep"],
                    fx(f'IF(OR(C{r}="No",H{r}=""),"",IF(H{r}>{_pa("corte")},0,DATEDIF(H{r},{_pa("corte")},"m")))', i["meses"]),
                    fx(f'IF(C{r}="No","",IF(F{r}=0,0,IF(OR(G{r}="",I{r}=""),"",F{r}*MIN(1,I{r}/(G{r}*12)))))', i["dep"]),
                    fx(f'IF(J{r}="","",IF(F{r}=0,0,J{r}-F{r}*MIN(1,MAX(0,I{r}-12)/(G{r}*12))))', i["depAnio"]),
                    fx(f'IF(C{r}="Sí",{_si(f"{INM}L{r}")},"")', i["depReg"] if i["aplica"] else None),
                    fx(f'IF(OR(J{r}="",L{r}=""),"",J{r}-L{r})', i["difDep"]),
                    fx(f'IF(C{r}="No","",D{r}-IF(J{r}<>"",J{r},IF(L{r}<>"",L{r},0)))', i["neto"]),
                    fx(f'IF(C{r}="Sí",{_si(f"{INM}Y{r}")},"")', i["rec"] if i["aplica"] else None),
                    fx(f'IF(OR(C{r}="No",O{r}=""),"",MAX(0,N{r}-O{r}))', i["det"]),
                    fx(f'IF(C{r}="No","",N{r}-IF(P{r}="",0,P{r}))', i["medCosto"])])
        med.append([i["id"], fx(f"{CLA}G{r}", i["clase"]), fx(f"{VRZ}C{r}", i["medida"]), fx(f"{INM}Q{r}", i["libros"]),
                    fx(f'IF({CLA}H{r}="No",0,IF(C{r}="Valor razonable",{VRZ}E{r},{MCO}Q{r})*{CLA}K{r})', i["aud"]), fx(f"E{r}-D{r}", i["ajuste"]),
                    fx(_si(f"{VRZ}H{r}"), i["ajVR"]), fx(f'IF({MCO}C{r}="Sí",({MCO}Q{r}-D{r})*{CLA}K{r},"")', i["efCosto"]),
                    fx(_si(f"{CLA}J{r}"), i["reclas"])])
        alq.append([i["id"], fx(f"{INM}C{r}", i["uso"]), fx(_si(f"{INM}R{r}"), i["alq"]), fx(_si(f"{INM}S{r}"), i["alqReg"]),
                    fx(f'IF(OR(C{r}="",D{r}=""),"",C{r}-D{r})', i["difAlq"])])

    tra = []
    for k, x in enumerate(trs):
        r, s = FILA0 + k, FILA0 + x["k"]
        vr_ok = f'OR({_pa("esPymes")}="Sí",{_pa("correcto")}<>"{VR}",F{r}="",G{r}="")'
        trat = (f'IF({_pa("esPymes")}="Sí","PYMES 16.9: transferir solo cuando cumple o deja de cumplir la definición de PI; la sección 16 no regula la medición de la diferencia (juicio, sección 10)",'
                f'IF({_pa("correcto")}<>"{VR}","Modelo del costo: sin cambio del importe en libros (NIC 40.59)",'
                f'IF(B{r}="PPE→PI","{TRAT_PPE}",IF(B{r}="Inventario→PI","Diferencia a resultados (NIC 40.63)",'
                f'IF(OR(B{r}="PI→PPE",B{r}="PI→Inventario"),"Costo atribuido = VR a la fecha del cambio (NIC 40.60)","Transferencia no reconocida")))))')
        estado = (f'IF(AND(B{r}<>"PPE→PI",B{r}<>"Inventario→PI",B{r}<>"PI→PPE",B{r}<>"PI→Inventario"),"Transferencia no reconocida",'
                  f'IF(C{r}="","Sin tratamiento: falta la fecha del cambio",IF(AND({_pa("esPymes")}="No",{_pa("correcto")}="{VR}",OR(F{r}="",G{r}="")),'
                  f'"Sin tratamiento: falta importe en libros o VR a la fecha",'
                  f'IF(AND(B{r}="PPE→PI",H{r}<>"",H{r}<0,I{r}=""),"{SIN_SUP}",'
                  f'IF(OR(AND(RIGHT(B{r},2)="PI",{CLA}H{s}="No"),AND(LEFT(B{r},2)="PI",{CLA}H{s}="Sí")),'
                  f'"Incoherente con la clasificación actual","Completa")))))')
        # NIC 40.62 / NIC 16.39-40: uso del superávit = lo que absorbe la disminución; el exceso va a resultados.
        uso_f = f'IF(H{r}="","",IF(B{r}<>"PPE→PI",0,IF(H{r}>=0,0,IF(I{r}="","",MIN(I{r},-H{r})))))'
        res_f = f'IF(OR(H{r}="",J{r}=""),"",IF(B{r}="Inventario→PI",H{r},IF(B{r}="PPE→PI",IF(H{r}>=0,0,H{r}+J{r}),0)))'
        ori_f = f'IF(OR(H{r}="",J{r}=""),"",IF(B{r}="PPE→PI",IF(H{r}>=0,H{r},-J{r}),0))'
        tra.append([x["id"], x["transf"], x["fecha"],
                    fx(f'IF(C{r}="","Sin fecha",IF(AND(C{r}>={_pa("inicio")},C{r}<={_pa("corte")}),"Sí","No"))', x["enEj"]),
                    fx(f"{CLA}G{s}", x["clase"]), fx(_si(f"{INM}V{s}"), x["lib"]), fx(_si(f"{INM}W{s}"), x["vr"]),
                    fx(f'IF({vr_ok},"",G{r}-F{r})', x["dif"]), fx(_si(f"{INM}X{s}"), x["sup0"]),
                    fx(uso_f, x["uso"]), fx(res_f, x["res"]), fx(ori_f, x["ori"]),
                    fx(trat, x["trat"]), fx(estado, x["estado"])])

    sup = []
    for k, x in enumerate(sups):
        r, si = FILA0 + k, FILA0 + x["k"]
        tr = None if x["t"] is None else FILA0 + x["t"]
        costo_f = f'AND({_pa("esPymes")}="No",{_pa("correcto")}<>"{VR}")'
        mov_f = "0" if tr is None else f'IF({costo_f},0,IF({TRA}L{tr}="","",MAX(0,{TRA}L{tr})))'
        uso_f = "0" if tr is None else f'IF({costo_f},0,IF({TRA}J{tr}="","",{TRA}J{tr}))'
        sup.append([x["id"], x["transf"] if tr is None else fx(f"{TRA}B{tr}", x["transf"]),
                    x["fecha"],                                  # fecha del cambio: mismo dato que 09 (columna de fecha, sin fórmula)
                    fx(_si(f"{INM}X{si}"), x["ini"]), fx(mov_f, x["mov"]), fx(uso_f, x["uso"]),
                    fx(f'IF(OR(D{r}="",E{r}="",F{r}=""),"",D{r}+E{r}-F{r})', x["fin"]),
                    fx(f'IF(G{r}="","",IF(G{r}>0.005,"{DESTINO_SI}","{DESTINO_NO}"))', x["destino"] or None)])

    baj = []
    for k, x in enumerate(bajas):
        r = FILA0 + k
        baj.append([x["id"], x["desc"], x["fecha"], x["prod"], x["lib"], fx(f"D{r}-E{r}", x["res"]), x["reg"],
                    fx(f'IF(G{r}="","",F{r}-G{r})', x["dif"])])

    mayor_f = f'IF({_pa("saldoMayor")}="",SUM({_rg(INM, "Q", ni)}),{_pa("saldoMayor")})'
    b = lambda i: f"B{FILA0 + i}"
    conciliacion = [
        ["Saldo según el mayor", fx(mayor_f, c["mayor"])],
        ["Importe en libros según el detalle", fx(f"SUM({_rg(INM, 'Q', ni)})", c["libros"])],
        ["Diferencia detalle − mayor", fx(f"{b(1)}-{b(0)}", c["dif"])],
        ["(+) Ajuste de valor razonable no reconocido", fx(f"SUM({_rg(VRZ, 'H', ni)})", c["vr"])],
        ["(+) Efecto de la medición al costo", fx(f"SUM({_rg(MED, 'H', ni)})", c["costo"])],
        ["(−) Reclasificación fuera de propiedades de inversión", fx(f"SUM({_rg(CLA, 'J', ni)})", c["reclas"])],
        ["Propiedades de inversión auditadas (puente desde el detalle)", fx(f"{b(1)}+{b(3)}+{b(4)}+{b(5)}", c["puente"])],
        ["Control: medición auditada según 08", fx(f"SUM({_rg(MED, 'E', ni)})", c["control"])],
        ["Diferencia de control (debe ser 0)", fx(f"{b(6)}-{b(7)}", c["difControl"])],
        ["Ajuste propuesto (auditado − mayor)", fx(f"{b(7)}-{b(0)}", c["ajuste"])],
    ]

    fr = {k: FILA0 + i for i, k in enumerate(res["labels"])}
    rb = lambda k: f"B{fr[k]}"
    ref_res = {
        "piAuditado": f"SUM({_rg(MED, 'E', ni)})", "saldoMayor": mayor_f, "ajuste": f"{rb('piAuditado')}-{rb('saldoMayor')}",
        "libros": f"SUM({_rg(INM, 'Q', ni)})", "difDetalleMayor": f"{rb('libros')}-{rb('saldoMayor')}",
        "ajusteVR": f"SUM({_rg(VRZ, 'H', ni)})", "efectoCosto": f"SUM({_rg(MED, 'H', ni)})", "reclasificacion": f"SUM({_rg(CLA, 'J', ni)})",
        "depreciacionAnio": f"SUM({_rg(MCO, 'K', ni)})", "difDepreciacion": f"SUM({_rg(MCO, 'M', ni)})", "deterioro": f"SUM({_rg(MCO, 'P', ni)})",
        "variacionVR": f"SUM({_rg(VRZ, 'F', ni)})", "difCostoInicial": f"SUM({_rg(COS, 'G', ni)})",
        "transfResultados": f"SUM({_rg(TRA, 'K', nt)})", "transfORI": f"SUM({_rg(TRA, 'L', nt)})",
        "usoSuperavit": f"SUM({_rg(TRA, 'J', nt)})", "superavitFinal": f"SUM({_rg(SUP, 'G', ns)})", "difAlquileres": f"SUM({_rg(ALQ, 'E', ni)})",
        "resultadoBajas": f"SUM({_rg(BAJ, 'F', nb)})", "difBajas": f"SUM({_rg(BAJ, 'H', nb)})",
    }
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    S = lambda xs: sum(x for x in xs if x is not None)
    return [
        hoja("01_Resumen", CEDULAS[0][1], [["Concepto", "t"], ["Importe", n_]], resumen),
        hoja("02_Parametros", CEDULAS[1][1], [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Inmuebles", CEDULAS[2][1],
             [["Código", "t"], ["Descripción", "t"], ["Uso actual", "t"], ["% uso propio", n_], ["Separable", "t"], ["Costo registrado", n_],
              ["Fecha de adquisición", "d"], ["Precio de compra", n_], ["Desembolsos atribuibles", n_], ["Terreno", n_], ["Vida útil (años)", n_],
              ["Dep. acumulada registrada", n_], ["VR año anterior", n_], ["VR al corte", n_], ["Fuente del VR", "t"], ["Nivel VR", "t"],
              ["Importe en libros", n_], ["Alquiler según contratos", n_], ["Alquiler registrado", n_], ["Cambio de uso", "t"],
              ["Fecha del cambio", "d"], ["Libros al cambio", n_], ["VR al cambio", n_], ["Superávit de revaluación a esa fecha", n_],
              ["Importe recuperable", n_]],
             inm, ["TOTAL", "", "", None, "", _tot("F", ni, S(i["costo"] for i in its)), None, None, None, None, None, None, None, None, "", "",
                   _tot("Q", ni, t["libros"]), None, None, "", None, None, None, None, None]),
        hoja("04_Clasificacion", CEDULAS[3][1],
             [["Código", "t"], ["Descripción", "t"], ["Uso actual", "t"], ["% uso propio", n_], ["Separable", "t"], ["Umbral (%)", n_],
              ["Clasificación auditada", "t"], ["¿Propiedad de inversión?", "t"], ["Importe en libros", n_], ["Reclasificación", n_],
              ["Parte que es propiedad de inversión", "p"]],
             cla, ["TOTAL", "", "", None, "", None, "", "", _tot("I", ni, t["libros"]), _tot("J", ni, t["reclasificacion"]), None]),
        hoja("05_Costo_inicial", CEDULAS[4][1],
             [["Código", "t"], ["Fecha de adquisición", "d"], ["Precio de compra", n_], ["Desembolsos atribuibles", n_], ["Costo recalculado", n_],
              ["Costo registrado", n_], ["Diferencia", n_], ["Costo auditado", n_]],
             cos, ["TOTAL", None, None, None, None, _tot("F", ni, S(i["costo"] for i in its)), _tot("G", ni, t["difCostoInicial"]),
                   _tot("H", ni, S(i["costoAud"] for i in its))]),
        hoja("06_Valor_razonable", CEDULAS[5][1],
             [["Código", "t"], ["¿PI?", "t"], ["Medición", "t"], ["VR año anterior", n_], ["VR al corte", n_], ["Variación del año", n_],
              ["Importe en libros", n_], ["Ajuste VR no reconocido (VR − libros)", n_], ["Fuente / tasador", "t"], ["Nivel", "t"]],
             vrz, ["TOTAL", "", "", None, None, _tot("F", ni, t["variacionVR"]), _tot("G", ni, t["libros"]), _tot("H", ni, t["ajusteVR"]), "", ""]),
        hoja("07_Modelo_costo", CEDULAS[6][1],
             [["Código", "t"], ["Medición", "t"], ["¿Aplica?", "t"], ["Costo del modelo (PYMES 16.8: libros al cesar el VR)", n_], ["Terreno", n_],
              ["Base depreciable", n_],
              ["Vida útil (años)", n_], ["Fecha base de depreciación", "d"], ["Meses completos", "i"], ["Dep. acumulada recalculada", n_],
              ["Depreciación del año", n_], ["Dep. acumulada registrada", n_], ["Diferencia de depreciación", n_], ["Valor neto", n_],
              ["Importe recuperable", n_], ["Deterioro", n_], ["Medición al costo", n_]],
             mco, ["TOTAL", "", "", None, None, None, None, None, None, None, _tot("K", ni, t["depreciacionAnio"]), None,
                   _tot("M", ni, t["difDepreciacion"]), None, None, _tot("P", ni, t["deterioro"]), _tot("Q", ni, S(i["medCosto"] for i in its))]),
        hoja("08_Medicion", CEDULAS[7][1],
             [["Código", "t"], ["Clasificación", "t"], ["Medición", "t"], ["Importe en libros", n_], ["Auditado en la cuenta", n_], ["Ajuste", n_],
              ["Ajuste VR (resultados)", n_], ["Efecto modelo del costo", n_], ["Reclasificación", n_]],
             med, ["TOTAL", "", "", _tot("D", ni, t["libros"]), _tot("E", ni, t["piAuditado"]), _tot("F", ni, S(i["ajuste"] for i in its)),
                   _tot("G", ni, t["ajusteVR"]), _tot("H", ni, t["efectoCosto"]), _tot("I", ni, t["reclasificacion"])]),
        hoja("09_Transferencias", CEDULAS[8][1],
             [["Código", "t"], ["Cambio de uso", "t"], ["Fecha del cambio", "d"], ["¿En el ejercicio?", "t"], ["Clasificación actual", "t"],
              ["Libros a la fecha", n_], ["VR a la fecha", n_], ["Diferencia VR − libros", n_], ["Superávit de revaluación a la fecha", n_],
              ["Uso del superávit (disminución)", n_], ["A resultados", n_], ["A otro resultado integral", n_], ["Tratamiento", "t"], ["Estado", "t"]],
             tra, ["TOTAL", "", None, "", "", None, None, _tot("H", nt, S(x["dif"] for x in trs)), _tot("I", nt, S(x["sup0"] for x in trs)),
                   _tot("J", nt, t["usoSuperavit"]), _tot("K", nt, t["transfResultados"]), _tot("L", nt, t["transfORI"]), "", ""] if nt else None),
        hoja("10_Superavit", CEDULAS[9][1],
             [["Código", "t"], ["Cambio de uso", "t"], ["Fecha del cambio", "d"], ["Saldo inicial en otro resultado integral", n_],
              ["Movimiento de la transferencia (aumento)", n_], ["Uso contra la disminución", n_], ["Saldo final", n_], ["Destino", "t"]],
             sup, ["TOTAL", "", None, _tot("D", ns, S(x["ini"] for x in sups)), _tot("E", ns, S(x["mov"] for x in sups)),
                   _tot("F", ns, t["usoSuperavit"]), _tot("G", ns, t["superavitFinal"]), ""] if ns else None),
        hoja("11_Alquileres", CEDULAS[10][1],
             [["Código", "t"], ["Uso actual", "t"], ["Ingresos según contratos", n_], ["Ingresos registrados", n_], ["Diferencia", n_]],
             alq, ["TOTAL", "", _tot("C", ni, S(i["alq"] for i in its)), _tot("D", ni, S(i["alqReg"] for i in its)), _tot("E", ni, t["difAlquileres"])]),
        hoja("12_Bajas", CEDULAS[11][1],
             [["Código", "t"], ["Descripción", "t"], ["Fecha de baja", "d"], ["Producto neto", n_], ["Importe en libros", n_],
              ["Resultado recalculado", n_], ["Resultado registrado", n_], ["Diferencia", n_]],
             baj, ["TOTAL", "", None, _tot("D", nb, S(x["prod"] for x in bajas)), _tot("E", nb, S(x["lib"] for x in bajas)),
                   _tot("F", nb, t["resultadoBajas"]), None, _tot("H", nb, t["difBajas"])] if nb else None),
        hoja("13_Conciliacion", CEDULAS[12][1], [["Concepto", "t"], ["Importe", n_]], conciliacion),
        hoja("14_Problemas", CEDULAS[13][1], [["Código", "t"], ["Descripción", "t"], ["Importe", n_]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición ------------------------------------------------------------------

def definicion() -> dict:
    inmuebles = ("Una fila por inmueble: código, descripción, uso actual, % de uso propio, costo registrado, fecha de adquisición, terreno, "
                 "vida útil, depreciación acumulada, VR al corte y del año anterior con su fuente y nivel, importe en libros, ingresos por "
                 "alquiler según contratos y registrados, cambio de uso del año (tipo, fecha, libros y VR a esa fecha) e importe recuperable si "
                 "hay indicio de deterioro; sin filas de total.")
    prog = lambda code, obj, risk, asr, proc, ev, crit, src: {"code": code, "objective": obj, "risk": risk, "assertion": asr, "procedure": proc,
                                                               "evidence": ev, "criterion": crit, "source": src}
    return {
        "name": "Propiedades de inversión",
        "area": "Propiedades de inversión",
        "processor": "propiedades_inversion",
        "frameworks": ["NIIF completas", "NIIF para las PYMES"],
        "summary": ("Clasifica cada inmueble (inversión, uso propio o venta), prueba el costo inicial, mide al valor razonable con cambios en "
                    "resultados o al costo con depreciación y deterioro según el marco y el modelo, trata las transferencias por cambio de uso, "
                    "concilia los ingresos por alquiler, recalcula el resultado de las bajas y propone el ajuste contra el mayor."),
        "source": {"organization": "IFRS Foundation · Reglamento (UE) 2023/1803 (texto en español: «inversiones inmobiliarias»)", "type": "Norma contable",
                   "date": "",
                   "document": "NIC 40 · párr. 5 (definiciones), 7-14 (clasificación; 10 uso mixto: PI solo si el uso propio es insignificante), "
                               "16-24 (reconocimiento y costo inicial: precio + desembolsos directamente atribuibles), 30-32 (elección de modelo; VR "
                               "siempre medido para valorar o revelar), 33-55 (modelo del VR: cambios a resultados, 35; excepción 53-54), 56 (modelo del "
                               "costo → NIC 16), 57-65 (transferencias: 59 costo, 60-65 VR; 65 construcción terminada), 66-73 (bajas: 69 producto neto − importe en libros), "
                               "75-79 (revelación; 79 e VR en el modelo del costo). NIIF 13 · 27-29 (mayor y mejor uso), 72 (jerarquía), 93 (revelación). "
                               "NIC 36 · 9 (indicios), 59 (reducción al importe recuperable). NIC 16 · 50 (depreciación sistemática), 58 (terrenos no se deprecian).",
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable",
                         "document": "NIIF para las PYMES 2015 · Sección 16: 16.1-16.4 (alcance, definición, uso mixto), 16.5 (costo inicial), 16.7 "
                                     "(VR con cambios en resultados solo si se mide con fiabilidad sin costo o esfuerzo desproporcionado; si no, "
                                     "modelo del costo de la sección 17), 16.8-16.9 (transferencias), 16.10 (revelación); VR con la guía 11.27-11.32; "
                                     "Sección 17.17-17.20 (depreciación) y 27.5-27.7 (deterioro). PYMES 2025 (tercera edición) · Sección 12 Medición "
                                     "del valor razonable (12.22 jerarquía; 12.28-12.29 revelación). PYMES 2025 · Sección 16: numeración "
                                     "16.1-16.10 igual a 2015; 16.7 remite a la Sección 12.",
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 18, 22-27 y 28-29", "requirement": "El VR, la vida útil y el importe recuperable son estimaciones: evaluar método, datos y supuestos."},
            {"document": "NIA 500 / NIA 620", "section": "NIA 500.8 (tasador de la entidad = experto de la dirección); NIA 620.9-12 solo si el auditor contrata su propio tasador", "requirement": "Evaluar competencia, objetividad y trabajo del tasador cuando el VR se basa en un experto."},
            {"document": "NIA 500", "section": "párr. 7 y 9", "requirement": "Fiabilidad del registro de inmuebles, escrituras y contratos."},
            {"document": "NIA 500 / NIA 330", "section": "NIA 500 párr. A18-A20 (inspección; titularidad con certificados) · NIA 330 párr. 18", "requirement": "Existencia y titularidad: inspección y certificados del Registro de la Propiedad."},
            {"document": "NIA 520", "section": "párr. 5", "requirement": "Analítica de ingresos por alquiler frente a contratos y ocupación."},
        ],
        "calculo": [
            "Clasificación: Venta → inventario; Uso propio → PPE; uso mixto → por partes si el inmueble es separable (NIC 40.10) y, si no, PPE cuando el "
            "% de uso propio supera el umbral. En PYMES el uso mixto se separa siempre sin umbral (16.4) y va entero a PPE si el VR de la parte de "
            "inversión no se mide sin costo o esfuerzo desproporcionado. Lo que no es PI se reclasifica fuera de la cuenta por su importe en libros; "
            "en el uso mixto se reclasifica la parte de uso propio a prorrata (importe en libros × % de uso propio).",
            "Costo inicial = precio de compra + desembolsos directamente atribuibles; diferencia = recalculado − registrado (NIC 40.20-21; PYMES 16.5).",
            "Ruta: completas → modelo elegido; PYMES → VR si es fiable sin costo o esfuerzo desproporcionado, si no costo (16.7-16.8). "
            "Partida sin VR bajo el modelo de VR → costo (NIC 40.53, residual cero; PYMES 16.1 y 16.7 si nunca fue medible / 16.8 si dejó de serlo: el importe en libros pasa a ser el costo).",
            "Valor razonable: ajuste = VR al corte − importe en libros, a resultados (NIC 40.35; PYMES 16.7).",
            "Modelo del costo: base = costo del modelo − terreno; dep. acumulada = base × MIN(1, meses completos ÷ (vida × 12)); dep. del año = acumulada "
            "− la de 12 meses antes; neto = costo del modelo − dep.; deterioro = MAX(0, neto − importe recuperable). En PYMES, si el VR dejó de medirse "
            "con fiabilidad, el costo del modelo es el importe en libros a esa fecha y los meses se cuentan desde ella (16.8).",
            "Transferencias con VR (completas): diferencia = VR − libros a la fecha; desde inventario a resultados (40.63); hacia PPE o inventario el costo "
            "atribuido es el VR (40.60). Con modelo del costo, sin cambio (40.59).",
            "Desde PPE revaluada a PI a valor razonable (40.61-62, NIC 16.39-41): el aumento se reconoce en otro resultado integral e incrementa el superávit "
            "de revaluación de ese inmueble; la disminución se imputa contra el superávit acreedor de ese mismo inmueble (uso = MIN(superávit, −diferencia)) y "
            "solo el exceso va a resultados. El superávit permanece en patrimonio y solo puede transferirse directamente a resultados acumulados, nunca a "
            "resultados del ejercicio (NIC 16.41). La cédula 10 lleva el historial por inmueble: saldo inicial + movimiento − uso = saldo final y destino. "
            "Sin el superávit informado, el reparto y el saldo final quedan vacíos y se emite un problema (M22). No se separa la parte del aumento que "
            "revierte un deterioro previo (40.62 b i): se señala como problema. En PYMES la Sección 16 no regula esa medición (16.9), así que no se calcula.",
            "Alquileres: diferencia = ingresos según contratos − registrados. Bajas: resultado = producto neto − importe en libros (NIC 40.69).",
            "Ajuste propuesto = propiedades de inversión auditadas − saldo del mayor.",
        ],
        "fields": _INMUEBLES, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            prog("IP-01", "Clasificación", "Inmueble de uso propio o para venta registrado como inversión", "Clasificación",
                 "Revisar uso real, contratos y ocupación de cada inmueble y aplicar el umbral de uso propio", "Contratos, inspección, certificado de uso",
                 "Solo inmuebles para rentas o plusvalías", "NIC 40.5-14 · PYMES 16.2-16.4"),
            prog("IP-02", "Sumaria y conciliación", "Detalle que no respalda el mayor", "Integridad", "Conciliar el registro de inmuebles con el mayor",
                 "Registro de propiedades, mayor", "Diferencia explicada o ajustada", "NIA 500"),
            prog("IP-03", "Costo inicial", "Costo sin desembolsos atribuibles o con costos no capitalizables", "Valoración",
                 "Cotejar precio de escritura y desembolsos directamente atribuibles", "Escrituras, facturas de honorarios, impuestos de transferencia",
                 "Costo = precio + atribuibles", "NIC 40.20-24 · PYMES 16.5"),
            prog("IP-04", "Valor razonable", "VR no actualizado o cambio no llevado a resultados", "Valoración",
                 "Comparar el VR de la tasación con el importe en libros y evaluar al tasador", "Informes de tasación, NIA 620",
                 "Ajuste de VR en resultados", "NIC 40.33-55 · NIIF 13 · PYMES 16.7 (2025: secc. 12)"),
            prog("IP-05", "Modelo del costo", "Depreciación o deterioro mal calculados", "Valoración",
                 "Recalcular depreciación y comparar el valor neto con el importe recuperable", "Vidas útiles, tasaciones, flujos",
                 "Depreciación y deterioro correctos; VR revelado", "NIC 40.56, 79 e · NIC 16 · NIC 36 · PYMES 16.8, secc. 17 y 27"),
            prog("IP-06", "Ingresos por alquiler", "Rentas no registradas o mal devengadas", "Ocurrencia / Integridad",
                 "Recalcular las rentas del año con los contratos y compararlas con lo registrado", "Contratos de arrendamiento, facturas",
                 "Ingresos conciliados", "NIC 40.75 f · NIIF 16"),
            prog("IP-07", "Transferencias", "Cambio de uso sin evidencia o sin tratamiento", "Clasificación / Valoración",
                 "Verificar evidencia del cambio de uso y la medición a la fecha", "Actas, contratos, tasación a la fecha del cambio",
                 "Tratamiento según NIC 40.57-65", "NIC 40.57-65 · PYMES 16.8-16.9"),
            prog("IP-09", "Superávit de revaluación", "Aumento de la transferencia llevado a resultados o superávit consumido sin saldo acreedor",
                 "Presentación / Valoración",
                 "Cotejar el superávit acumulado de cada inmueble transferido con el auxiliar de la cuenta y el estado de cambios en el patrimonio; "
                 "recalcular el aumento a otro resultado integral, el uso contra la disminución y el saldo final",
                 "Auxiliar del superávit de revaluación por inmueble, estado de cambios en el patrimonio, auxiliar de deterioros",
                 "Aumento a otro resultado integral; disminución contra el superávit de ese inmueble y el exceso a resultados; el superávit permanece en "
                 "patrimonio y solo se transfiere a resultados acumulados",
                 "NIC 40.61-62 · NIC 16.39-41 · PYMES 17.15C-17.15D"),
            prog("IP-08", "Bajas", "Resultado de venta mal determinado", "Exactitud", "Recalcular producto neto − importe en libros",
                 "Escrituras de venta, cobros", "Resultado correcto", "NIC 40.66-73"),
        ],
        "requests": [
            req("RQ-001", "Registro de propiedades de inversión al corte", "inmuebles", "IP-01", "Clasificación, medición y conciliación", content=inmuebles),
            req("RQ-002", "Bajas de propiedades de inversión del ejercicio", "bajas", "IP-08", "Resultado de las bajas", required=False,
                content="Una fila por inmueble vendido o retirado: código, descripción, fecha, producto neto, importe en libros y resultado registrado."),
            req("RQ-003", "Informes de tasación al corte", None, "IP-04", "Soporte del valor razonable y del tasador", formats=("pdf",), use="soporte"),
            req("RQ-004", "Contratos de arrendamiento vigentes", None, "IP-06", "Soporte de las rentas y del uso", formats=("pdf",), use="soporte"),
            req("RQ-005", "Escrituras y certificados del Registro de la Propiedad", None, "IP-03", "Titularidad y costo inicial", formats=("pdf",), use="soporte"),
            req("RQ-006", "Evidencia de cambios de uso (actas, contratos, ocupación)", None, "IP-07", "Soporte de las transferencias",
                formats=("pdf", "docx"), use="soporte", required=False),
            req("RQ-007", "Gastos directos de operación por inmueble", None, "IP-06", "Revelación NIC 40.75 f) ii) y iii)", formats=("xlsx", "pdf"), use="soporte", required=False),
            req("RQ-009", "Auxiliar del superávit de revaluación por inmueble y estado de cambios en el patrimonio", None, "IP-09",
                "Saldo acreedor del superávit de cada inmueble transferido y su arrastre en patrimonio", formats=("xlsx", "pdf"), use="soporte",
                required=False),
            req("RQ-008", "Base fiscal de los inmuebles", None, "IP-04", "Impuesto diferido (fuera del cálculo de esta versión)", formats=("xlsx",),
                use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) ---------------------------------------------------------

def _im(id, desc, uso, costo, libros, **kw):
    f = {k["key"]: "" for k in _INMUEBLES}
    f.update({"id": id, "descripcion": desc, "uso": uso, "costo": costo, "importe_libros": libros, "_row": 2}, **kw)
    return f


# Cifras a mano (corte 31-12-2025, NIIF completas, modelo VR): detalle 2.780.000 vs mayor 2.785.000 (−5.000).
# IP-04 es de uso mixto (35 % de uso propio) y sus partes pueden venderse por separado: NIC 40.10 exige
# contabilizarlo por partes aunque el uso propio supere el umbral, así que la parte de inversión es el 65 %.
# Ajuste VR = IP-01 +20.000, IP-03 −20.000, IP-04 +13.000 (20.000 × 65 %), IP-06 +25.000, IP-08 +5.000,
# IP-09 +5.000 = 48.000.
# IP-07 sin VR → costo: base 300.000 − 60.000 = 240.000; 120 meses ÷ 600 → dep. 48.000 (registrada 45.000: +3.000);
# neto 252.000; recuperable 230.000 → deterioro 22.000; medición 230.000 vs libros 255.000 → −25.000.
# Reclasificación IP-04 (parte de uso propio) 190.000 × 35 % = 66.500 + IP-05 (venta) 150.000 = −216.500.
# Auditado 2.780.000 + 48.000 − 25.000 − 216.500 = 2.586.500; ajuste 2.586.500 − 2.785.000 = −198.500.
# IP-08 (PPE→PI): diferencia 205.000 − 125.000 = +80.000 → todo a ORI (NIC 40.62 b ii); superávit del inmueble
# 30.000 + 80.000 − 0 = 110.000, que permanece en patrimonio.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"modelo": "valor_razonable", "vr_sin_esfuerzo_desproporcionado": "sí", "umbral_uso_propio": 10, "saldoMayor": 2785000},
    "datasets": {
        "inmuebles": [
            _im("IP-01", "Edificio de oficinas Norte", "Alquiler", 500000, 700000, pct_uso_propio=0, fecha_adquisicion="2018-03-01",
                terreno=100000, vida_util=40, vr_anterior=700000, vr_corte=720000, fuente_vr="Perito independiente (tasación dic-2025)",
                nivel_vr="Nivel 2", ingresos_alquiler=48000, ingresos_registrados=48000),
            _im("IP-02", "Terreno Samborondón", "Plusvalía", 300000, 380000, terreno=300000, vr_anterior=350000, vr_corte=380000,
                fuente_vr="Perito independiente", nivel_vr="Nivel 2"),
            _im("IP-03", "Local comercial Sur", "Alquiler", 250000, 260000, fecha_adquisicion="2020-06-30", terreno=50000, vida_util=30,
                vr_anterior=260000, vr_corte=240000, fuente_vr="Perito independiente", nivel_vr="Nivel 3", ingresos_alquiler=24000,
                ingresos_registrados=22000),
            _im("IP-04", "Bodega Durán (35 % uso propio)", "Alquiler", 180000, 190000, pct_uso_propio=35, separable="Sí",
                fecha_adquisicion="2019-12-31", terreno=30000, vida_util=30, vr_corte=210000, fuente_vr="Perito independiente", nivel_vr="Nivel 3",
                ingresos_alquiler=9000, ingresos_registrados=9000),
            _im("IP-05", "Departamentos para la venta", "Venta", 150000, 150000),
            _im("IP-06", "Edificio Centro (compra 2025)", "Alquiler", 400000, 400000, fecha_adquisicion="2025-07-01", precio_compra=400000,
                costos_atribuibles=12000, terreno=80000, vida_util=40, vr_corte=425000, fuente_vr="Tasación interna", nivel_vr="Nivel 3",
                ingresos_alquiler=18000, ingresos_registrados=12000),
            _im("IP-07", "Edificio zona sin mercado activo", "Uso futuro no determinado", 300000, 255000, fecha_adquisicion="2015-12-31",
                terreno=60000, vida_util=50, dep_acumulada=45000, importe_recuperable=230000),
            _im("IP-08", "Oficina ex uso propio", "Alquiler", 160000, 205000, fecha_adquisicion="2015-01-01", terreno=40000, vida_util=40,
                dep_acumulada=33000, vr_corte=210000, fuente_vr="Perito independiente", nivel_vr="Nivel 2", ingresos_alquiler=6000,
                ingresos_registrados=6000, transferencia="PPE → PI", fecha_transferencia="2025-09-30", libros_transferencia=125000,
                vr_transferencia=205000, superavit_revaluacion=30000),
            _im("IP-09", "Casa arrendada (ex inventario)", "Alquiler", 70000, 90000, fecha_adquisicion="2019-12-31", terreno=10000, vida_util=30,
                vr_anterior=90000, vr_corte=95000, ingresos_registrados=7000, transferencia="Inventario a PI", fecha_transferencia="2025-05-15"),
            _im("IP-10", "Galpón industrial arrendado", "Alquiler", 120000, 150000, pct_uso_propio=5, fecha_adquisicion="2017-12-31",
                terreno=20000, vida_util=25, vr_anterior=150000, vr_corte=150000, fuente_vr="Perito independiente", nivel_vr="Nivel 2",
                ingresos_alquiler=12000, ingresos_registrados=12000),
        ],
        "bajas": [
            {"id": "B-01", "descripcion": "Local Quevedo", "fecha_baja": "2025-08-31", "producto_neto": 130000, "importe_libros": 110000,
             "resultado_registrado": 20000, "_row": 2},
            {"id": "B-02", "descripcion": "Terreno Manta", "fecha_baja": "2025-11-30", "producto_neto": 85000, "importe_libros": 95000,
             "resultado_registrado": 0, "_row": 3},
        ],
    },
}

_E = EJEMPLO
# PYMES 16.8: IP-07 con la fecha en que el VR dejó de medirse (30-06-2023) y el importe en libros a esa fecha
# (262.000, nuevo costo). Base 262.000 − 60.000 = 202.000; 30 meses ÷ 600 → dep. 10.100; neto 251.900;
# recuperable 230.000 → deterioro 21.900; medición 230.000.
_PYMES_16_8 = {"inmuebles": [dict(f, fecha_transferencia="2023-06-30", libros_transferencia=262000) if f["id"] == "IP-07" else f
                             for f in _E["datasets"]["inmuebles"]],
               "bajas": _E["datasets"]["bajas"]}
# Superávit (decisión del socio): IP-08 pasa a una disminución. Libros al cambio 125.000, VR 100.000 → −25.000.
# Con superávit 10.000: uso 10.000 (a ORI −10.000) y exceso −15.000 a resultados; saldo final 0.
# Sin el dato: no se puede repartir → resultados y ORI vacíos y problema SIN_SUPERAVIT_REVALUACION.
def _ip08(**kw):
    return {"inmuebles": [dict(f, **kw) if f["id"] == "IP-08" else f for f in _E["datasets"]["inmuebles"]],
            "bajas": _E["datasets"]["bajas"]}


_SUP_BAJA = _ip08(vr_transferencia=100000, superavit_revaluacion=10000)
_SUP_SIN_DATO = _ip08(vr_transferencia=100000, superavit_revaluacion="")
ESCENARIOS = [
    ("niif_completas_vr", _E["datasets"], {**_E["parametros"], "_marco": "NIIF completas"}, _E["corte"]),
    ("niif_completas_costo", _E["datasets"], {**_E["parametros"], "modelo": "costo", "_marco": "NIIF completas"}, _E["corte"]),
    ("pymes_2015_sin_vr_fiable", _E["datasets"], {**_E["parametros"], "vr_sin_esfuerzo_desproporcionado": "no", "_marco": "NIIF para las PYMES",
                                                 "_edicion": "2015"}, _E["corte"]),
    ("pymes_2025_vr", _E["datasets"], {**_E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2025"}, _E["corte"]),
    ("pymes_2025_16_8", _PYMES_16_8, {**_E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2025"}, _E["corte"]),
    ("superavit_disminucion", _SUP_BAJA, {**_E["parametros"], "_marco": "NIIF completas"}, _E["corte"]),
    ("superavit_sin_dato", _SUP_SIN_DATO, {**_E["parametros"], "_marco": "NIIF completas"}, _E["corte"]),
    ("solo_inmuebles_sin_mayor", {"inmuebles": _E["datasets"]["inmuebles"][:3]}, {"umbral_uso_propio": 5}, _E["corte"]),
]
