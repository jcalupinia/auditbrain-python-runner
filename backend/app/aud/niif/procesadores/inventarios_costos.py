"""Inventarios, producción y costo de ventas (NIC 2 · NIIF para las PYMES secciones 13 y 27).

Versión simple que cumple la norma, una cédula por prueba de la matriz del socio (MÓDULO 03):

1. Existencia / conteo: diferencias físicas = (cantidad contada − kardex) × costo unitario.
2. Prueba de costo: extensión (cantidad × costo unitario vs valor del kardex) y costo unitario
   soportado por el auditor (factura o costeo) vs el registrado (NIC 2.10-2.11; PYMES 13.5-13.6).
3. Conciliación kardex–mayor: valor del kardex vs saldo del mayor, y puente hasta el costo auditado.
4. Costo de producción (INV-17): MP + MOD + CIF variable + CIF fijo absorbido − desperdicio anormal;
   tasa CIF fijo = CIF fijo ÷ capacidad normal; absorbido = MIN(CIF fijo, tasa × producción real);
   no absorbido a gasto (NIC 2.12-2.13 y 2.16 a; PYMES 13.8-13.9, 13.13).
5. Costo de ventas (INV-16): COGS = inventario inicial + compras netas (+ COGM) − inventario final;
   COGM = WIP inicial + costos de manufactura − WIP final (NIC 2.34; PYMES 13.20).
6. VNR (cédula simplificada; la herramienta VNR del catálogo es la completa): VNR = precio estimado de
   venta − costos de terminación − costos de venta; rebaja = MIN(costo de la partida,
   MAX(0, costo unitario − VNR) × cantidad) — el inventario no puede quedar negativo (NIC 2.9,
   2.28-2.33; PYMES 13.19 y 27.2-27.4).
6.b Excepción de NIC 2.32 (materias primas): los materiales y suministros para la producción no se rebajan
   por debajo del costo si el producto terminado al que se incorporan se venderá al costo o por encima.
   La excepción solo se aplica cuando el cliente informa el producto terminado asociado y su costo y precio
   esperados y el margen (precio − costo) es cero o positivo; si faltan esos datos o el margen es negativo
   se mide al menor entre costo y VNR como cualquier partida y se emite un problema con el papel que falta.
   La NIIF para las PYMES (Secc. 13.19 y 27.2-27.4, igual en 2015 y 2025) no recoge esta excepción: en ese
   marco nunca se aplica.
7. Obsolescencia / lenta rotación: % por tramo de días sin movimiento (parámetros). NIC 2.9 y PYMES 13.4
   miden al MENOR entre costo y VNR: si el ítem tiene precio de venta informado, la provisión estimada es
   solo la rebaja a VNR; el tramo de obsolescencia sustituye al VNR únicamente cuando NO hay precio de venta
   (estimación del VNR por antigüedad, NIC 2.30) y en ese caso se emite un problema.
8. Corte: fecha del documento (recepción / despacho) vs fecha de registro respecto al corte.

Ajuste propuesto = (costo auditado − provisión estimada) − (saldo del mayor − provisión registrada).
El libro Excel lleva cada importe como fórmula que remite a Parámetros y a la hoja de Inventario.
"""
from __future__ import annotations

from datetime import date

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m, problema, r2, ref, req,
    validar_campos, validar_definicion_generica,
)

VERSION = "inventarios_costos 1.0"
RUBRO = "INVENTARIOS"

_INVENTARIO = [
    campo("id", "Código del ítem", alias=("codigo", "item", "sku", "referencia", "cod item"), ejemplo="A-001"),
    campo("descripcion", "Descripción", alias=("detalle", "nombre", "producto", "articulo"), ejemplo="Tornillo 1/4"),
    campo("bodega", "Bodega", requerido=False, alias=("almacen", "ubicacion", "local"), ejemplo="BOD1"),
    campo("cant_kardex", "Cantidad según kardex", "number", alias=("cantidad", "existencia", "saldo unidades", "stock"), ejemplo=1000),
    campo("cant_contada", "Cantidad contada (en blanco si no se contó)", "number", requerido=False,
          alias=("conteo", "cantidad fisica", "toma fisica", "contado"), ejemplo=1000),
    campo("costo_unitario", "Costo unitario registrado", "number", alias=("costo", "costo promedio", "cu", "precio costo"), ejemplo=2.5),
    campo("valor_kardex", "Valor según kardex (inventario valorado)", "number",
          alias=("valor", "costo total", "total", "saldo valor", "valor inventario"), ejemplo=2500),
    campo("costo_soportado", "Costo unitario soportado (factura o costeo verificado)", "number", requerido=False,
          alias=("costo factura", "costo verificado", "costo auditado"), ejemplo=2.5),
    campo("fecha_ult_mov", "Fecha del último movimiento", "date", requerido=False,
          alias=("ultimo movimiento", "fecha ultima salida", "ultima venta", "fecha movimiento"), ejemplo="2025-12-10"),
    campo("precio_venta", "Precio estimado de venta unitario", "number", requerido=False,
          alias=("precio", "pvp", "precio venta", "precio posterior"), ejemplo=4),
    campo("costo_terminacion", "Costos de terminación unitarios", "number", requerido=False,
          alias=("terminacion", "costo para terminar"), ejemplo=0),
    campo("costo_venta", "Costos de venta unitarios", "number", requerido=False,
          alias=("gastos de venta", "comision", "costo de venta unitario"), ejemplo=0.3),
    campo("materia_prima", "¿Es materia prima o suministro para la producción? (Sí/No)", requerido=False,
          alias=("materia prima", "mp", "es materia prima", "clase de inventario", "tipo de inventario"), ejemplo="No"),
    campo("pt_producto", "Producto terminado asociado (solo materias primas)", requerido=False,
          alias=("producto terminado", "pt", "producto final", "articulo terminado", "producto asociado"), ejemplo="Tanque 200 L"),
    campo("pt_costo_esperado", "Costo esperado del producto terminado (unitario)", "number", requerido=False,
          alias=("costo producto terminado", "costo esperado", "costo pt", "costo esperado pt"), ejemplo=300),
    campo("pt_precio_esperado", "Precio de venta esperado del producto terminado (unitario)", "number", requerido=False,
          alias=("precio producto terminado", "precio esperado", "precio pt", "precio venta pt"), ejemplo=330),
]
CAMPOS = {
    "inventario": _INVENTARIO,
    "produccion": [
        campo("id", "Período u orden de producción", alias=("periodo", "orden", "mes", "op"), ejemplo="OP-01"),
        campo("mp", "Materia prima consumida", "number", alias=("materia prima", "materiales"), ejemplo=20000),
        campo("mod", "Mano de obra directa", "number", alias=("mano de obra", "mo directa"), ejemplo=8000),
        campo("cif_variable", "CIF variables", "number", alias=("costos indirectos variables", "cif var"), ejemplo=3000),
        campo("cif_fijo", "CIF fijos elegibles", "number", alias=("costos indirectos fijos", "cif fijos"), ejemplo=12000),
        campo("unidades", "Unidades producidas (producción real)", "number", alias=("produccion real", "unidades producidas"), ejemplo=800),
        campo("capacidad_normal", "Capacidad normal (unidades)", "number", alias=("capacidad", "capacidad normal"), ejemplo=1000),
        campo("desperdicio_anormal", "Desperdicio anormal incluido en los importes", "number", requerido=False,
              alias=("desperdicio", "merma anormal"), ejemplo=0),
        campo("cif_fijo_capitalizado", "CIF fijo cargado al inventario por la entidad", "number", requerido=False,
              alias=("cif fijo capitalizado", "cif aplicado", "cif absorbido entidad"), ejemplo=12000),
    ],
    "movimiento": [
        campo("id", "Línea de inventario vendido (mercadería / productos terminados)", alias=("linea", "cuenta", "clase"), ejemplo="Mercaderías"),
        campo("inv_inicial", "Inventario inicial", "number", alias=("saldo inicial", "inventario inicial"), ejemplo=10000),
        campo("inv_final_anterior", "Inventario final del ejercicio anterior (auditado)", "number", requerido=False,
              alias=("cierre anterior", "saldo auditado anterior"), ejemplo=10000),
        campo("compras_netas", "Compras netas (de devoluciones y descuentos)", "number", alias=("compras", "compras netas"), ejemplo=60000),
        campo("wip_inicial", "Productos en proceso inicial", "number", requerido=False, alias=("wip inicial", "en proceso inicial"), ejemplo=0),
        campo("costos_manufactura", "Costos de manufactura del período (registrados)", "number", requerido=False,
              alias=("costos de produccion", "costo de manufactura"), ejemplo=0),
        campo("wip_final", "Productos en proceso final", "number", requerido=False, alias=("wip final", "en proceso final"), ejemplo=0),
        campo("inv_final", "Inventario final", "number", alias=("saldo final", "inventario final"), ejemplo=12000),
        campo("costo_ventas_contable", "Costo de ventas contable", "number", alias=("costo de ventas", "costo ventas mayor"), ejemplo=58000),
    ],
    "corte": [
        campo("id", "Documento", alias=("factura", "guia", "comprobante", "numero"), ejemplo="FC-901"),
        campo("tipo", "Tipo (Compra / Venta)", alias=("tipo", "movimiento"), ejemplo="Compra"),
        campo("fecha_documento", "Fecha de recepción o despacho", "date", alias=("fecha recepcion", "fecha despacho", "fecha guia"), ejemplo="2025-12-29"),
        campo("fecha_registro", "Fecha de registro contable", "date", alias=("fecha contable", "fecha asiento"), ejemplo="2025-12-30"),
        campo("importe", "Importe", "number", alias=("valor", "costo", "monto"), ejemplo=1500),
    ],
}
TIPOS = {"inventario": "inventario", "produccion": "produccion", "movimiento": "movimiento", "corte": "corte"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "inventario"
CONTROL = "valor_kardex"

PARAMETROS = {
    "obsDias1": 180, "obsPct1": 25, "obsDias2": 365, "obsPct2": 50, "obsDias3": 730, "obsPct3": 100,
    "saldoMayor": None, "provisionRegistrada": None,
}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "obsDias1": "Tramo 1: días sin movimiento (más de)", "obsPct1": "Tramo 1: % de provisión",
    "obsDias2": "Tramo 2: días sin movimiento (más de)", "obsPct2": "Tramo 2: % de provisión",
    "obsDias3": "Tramo 3: días sin movimiento (más de)", "obsPct3": "Tramo 3: % de provisión",
    "saldoMayor": "Saldo del inventario según el mayor", "provisionRegistrada": "Provisión registrada (VNR / obsolescencia)",
}
TOTAL_EJEMPLO = "ajuste"

# Dashboard (formato en graficos.py): la población es el inventario según el kardex del cliente; la
# cifra que el auditor recalcula frente a la registrada es la provisión (rebaja a VNR / obsolescencia).
PANEL = {
    "poblacion":    {"rotulo": "Inventario según kardex", "hoja": "03_Inventario", "col": "Valor kardex"},
    "recalculado":  {"rotulo": "Provisión estimada", "total": "provisionEstimada"},
    "registrado":   {"rotulo": "Provisión registrada", "total": "provisionRegistrada"},
    "composicion":  {"rotulo": "Provisión estimada por ítem", "hoja": "10_Obsolescencia", "etiqueta": "Descripción",
                     "valor": "Provisión estimada (neta de la excepción NIC 2.32)"},
    "distribucion": {"rotulo": "Inventario por bodega", "hoja": "03_Inventario", "etiqueta": "Bodega", "valor": "Valor kardex"},
}


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    return validar_campos(CAMPOS[tipo], filas, unico=None if tipo == "inventario" else "id")


# --- cálculo -------------------------------------------------------------------

def _opt(v):
    """Número opcional: vacío → None (M22: lo no medido queda vacío, nunca 0)."""
    return a_num(v) if str(v if v is not None else "").strip() else None


def _txt(v) -> str:
    return str(v if v is not None else "").strip()


def _parametros(parametros: dict) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    for k in ("obsDias1", "obsPct1", "obsDias2", "obsPct2", "obsDias3", "obsPct3"):
        x = a_num(p[k])
        if x is None or x < 0:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: indique un número no negativo.")
        p[k] = float(x)
    for k in ("obsPct1", "obsPct2", "obsPct3"):
        if p[k] > 100:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: use un porcentaje entre 0 y 100.")
    if not p["obsDias1"] < p["obsDias2"] < p["obsDias3"]:
        raise ValueError("Los tramos de días sin movimiento deben ser crecientes (tramo 1 < tramo 2 < tramo 3).")
    for k in ("saldoMayor", "provisionRegistrada"):
        p[k] = None if p.get(k) in (None, "") else a_num(p[k])
    return p


# Motivos de la excepción de NIC 2.32 (el mismo texto lo arma la fórmula de la cédula 11: no tocar uno sin el otro).
_MOT_NO_MP = "No es materia prima"
_MOT_PYMES = "La NIIF para las PYMES no recoge la excepción de la NIC 2.32: se mide al menor entre costo y precio de venta menos costos (27.2)"
_MOT_FALTA = "Faltan el costo o el precio esperados del producto terminado"
_MOT_SI = "El producto terminado se vendería al costo o por encima (NIC 2.32)"
_MOT_NEG = "Margen esperado negativo: el costo del producto terminado excedería su valor realizable neto (NIC 2.32)"
_NO = ("", "no", "n", "0", "false", "falso")


def _es_mp(txt: str, pt_id: str, pt_c, pt_p) -> bool:
    """Materia prima: la marca del anexo, o el hecho de que informen el producto terminado asociado."""
    return txt.strip().lower() not in _NO or bool(pt_id) or pt_c is not None or pt_p is not None


def _pct_obs(dv, p):
    if dv is None:
        return None
    if dv > p["obsDias3"]:
        return p["obsPct3"] / 100
    if dv > p["obsDias2"]:
        return p["obsPct2"] / 100
    if dv > p["obsDias1"]:
        return p["obsPct1"] / 100
    return 0


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = _parametros(parametros)
    pymes = es_pymes(p)
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")

    # 1-2 · inventario por ítem: conteo, costo, VNR y obsolescencia.
    items = []
    for f in datasets.get("inventario") or []:
        kx, cu, vk = a_num(f.get("cant_kardex")), a_num(f.get("costo_unitario")), a_num(f.get("valor_kardex"))
        if kx is None or cu is None or vk is None:
            continue
        cc, sop = _opt(f.get("cant_contada")), _opt(f.get("costo_soportado"))
        pv, ct, cv = _opt(f.get("precio_venta")), _opt(f.get("costo_terminacion")) or 0.0, _opt(f.get("costo_venta")) or 0.0
        fum = fecha(f.get("fecha_ult_mov")) if _txt(f.get("fecha_ult_mov")) else None
        pt_id, pt_c, pt_p = _txt(f.get("pt_producto")), _opt(f.get("pt_costo_esperado")), _opt(f.get("pt_precio_esperado"))
        es_mp = _es_mp(_txt(f.get("materia_prima")), pt_id, pt_c, pt_p)
        it = {"id": _txt(f.get("id")), "desc": _txt(f.get("descripcion")), "bodega": _txt(f.get("bodega")), "kx": kx, "cc": cc,
              "cu": cu, "vk": vk, "sop": sop, "fum": fum, "pv": pv, "ct": ct, "cv": cv, "_row": f.get("_row"),
              "esMp": es_mp, "mpTxt": "Sí" if es_mp else "No", "ptId": pt_id, "ptC": pt_c, "ptP": pt_p}
        it["cant"] = cc if cc is not None else kx
        it["cua"] = sop if sop is not None else cu
        it["costo"] = it["cant"] * it["cua"]
        it["difCant"] = None if cc is None else cc - kx
        it["difFis"] = None if cc is None else it["difCant"] * cu
        it["recalc"] = kx * cu
        it["difExt"] = it["recalc"] - vk
        it["difU"] = None if sop is None else sop - cu
        it["difCosto"] = None if sop is None else it["difU"] * it["cant"]
        it["dias"] = None if fum is None else (corte_a - fum).days
        it["pct"] = _pct_obs(it["dias"], p)
        it["obs"] = None if it["pct"] is None else it["costo"] * it["pct"]
        it["vnr"] = None if pv is None else pv - ct - cv
        # NIC 2.9 / PYMES 13.4: se mide al menor entre costo y VNR; la rebaja no puede pasar del costo de la partida.
        it["rebajaBruta"] = None if it["vnr"] is None else max(0, it["cua"] - it["vnr"]) * it["cant"]
        it["rebaja"] = None if it["rebajaBruta"] is None else min(it["costo"], it["rebajaBruta"])
        it["exceso"] = 0.0 if it["rebajaBruta"] is None else it["rebajaBruta"] - it["rebaja"]
        # Con VNR medido manda el VNR; el tramo de obsolescencia solo estima el VNR cuando falta el precio (NIC 2.30).
        it["provBase"] = it["rebaja"] if it["vnr"] is not None else it["obs"]
        # NIC 2.32: la materia prima no se rebaja por debajo del costo si el producto terminado al que se incorpora
        # se venderá al costo o por encima. Sin esa demostración (o con margen negativo) NO hay excepción: menor
        # entre costo y VNR. PYMES 13.19 y 27.2-27.4 no tienen equivalente, así que en ese marco nunca se aplica.
        it["ptMargen"] = None if (pt_c is None or pt_p is None) else pt_p - pt_c
        it["excepcion"] = bool(es_mp and not pymes and it["ptMargen"] is not None and it["ptMargen"] >= 0)
        it["motivoExc"] = (_MOT_NO_MP if not es_mp else _MOT_PYMES if pymes else _MOT_FALTA if it["ptMargen"] is None
                           else _MOT_SI if it["ptMargen"] >= 0 else _MOT_NEG)
        it["prov"] = 0.0 if it["excepcion"] else it["provBase"]
        it["efectoExc"] = (it["provBase"] or 0.0) if it["excepcion"] else 0.0
        items.append(it)
    if not items:
        raise ValueError("Cargue el inventario valorado por ítem (kardex) al corte.")

    # 4 · costo de producción (INV-17).
    prod = []
    for f in datasets.get("produccion") or []:
        mp, mod, cvar, cf, un = (a_num(f.get(k)) for k in ("mp", "mod", "cif_variable", "cif_fijo", "unidades"))
        if None in (mp, mod, cvar, cf, un):
            continue
        cap, desp, cfc = _opt(f.get("capacidad_normal")), _opt(f.get("desperdicio_anormal")) or 0.0, _opt(f.get("cif_fijo_capitalizado"))
        x = {"id": _txt(f.get("id")), "mp": mp, "mod": mod, "cvar": cvar, "cf": cf, "un": un, "cap": cap, "desp": desp, "cfc": cfc}
        x["tasa"] = cf / cap if cap else None
        x["abs"] = None if x["tasa"] is None else min(cf, x["tasa"] * un)
        x["noAbs"] = None if x["abs"] is None else cf - x["abs"]
        x["costo"] = None if x["abs"] is None else mp + mod + cvar + x["abs"] - desp
        x["cu"] = None if x["costo"] is None or un == 0 else x["costo"] / un
        x["exceso"] = None if cfc is None or x["abs"] is None else max(0, cfc - x["abs"])
        prod.append(x)

    # 5 · costo de ventas (INV-16).
    mov = []
    for f in datasets.get("movimiento") or []:
        ii, cn, fi, cvc = (a_num(f.get(k)) for k in ("inv_inicial", "compras_netas", "inv_final", "costo_ventas_contable"))
        if None in (ii, cn, fi, cvc):
            continue
        ant, wi, cm, wf = (_opt(f.get(k)) for k in ("inv_final_anterior", "wip_inicial", "costos_manufactura", "wip_final"))
        x = {"id": _txt(f.get("id")), "ii": ii, "ant": ant, "cn": cn, "wi": wi, "cm": cm, "wf": wf, "fi": fi, "cvc": cvc}
        x["apertura"] = None if ant is None else ii - ant
        x["cogm"] = None if cm is None else (wi or 0) + cm - (wf or 0)
        x["cogs"] = ii + cn + (x["cogm"] if x["cogm"] is not None else 0) - fi
        x["dif"] = x["cogs"] - cvc
        mov.append(x)

    # 8 · corte.
    cortes = []
    for f in datasets.get("corte") or []:
        fd, fr, imp = fecha(f.get("fecha_documento")), fecha(f.get("fecha_registro")), a_num(f.get("importe"))
        if fd is None or fr is None or imp is None:
            continue
        pd_, pr = ("Ejercicio" if fd <= corte_a else "Posterior"), ("Ejercicio" if fr <= corte_a else "Posterior")
        err = pd_ != pr
        cortes.append({"id": _txt(f.get("id")), "tipo": _txt(f.get("tipo")), "fd": fd, "fr": fr, "imp": imp, "pd": pd_, "pr": pr,
                       "err": err, "mal": imp if err else 0,
                       "efecto": "" if not err else ("Registrado en el ejercicio sin haber ocurrido" if pd_ == "Posterior"
                                                     else "Ocurrido en el ejercicio y registrado después")})

    # Totales (mismo orden de suma que Excel).
    S = lambda xs: sum(x for x in xs if x is not None)
    vk_t = S(i["vk"] for i in items)
    mayor = p["saldoMayor"] if p["saldoMayor"] is not None else vk_t
    prov_reg = p["provisionRegistrada"] if p["provisionRegistrada"] is not None else 0.0
    t = {"costoAuditado": S(i["costo"] for i in items), "provisionEstimada": S(i["prov"] for i in items)}
    t["inventarioNeto"] = t["costoAuditado"] - t["provisionEstimada"]
    t["saldoMayor"] = mayor
    t["provisionRegistrada"] = prov_reg
    t["libroNeto"] = mayor - prov_reg
    t["ajuste"] = t["inventarioNeto"] - t["libroNeto"]
    t["difFisicas"] = S(i["difFis"] for i in items)
    t["difExtension"] = S(i["difExt"] for i in items)
    t["difCosto"] = S(i["difCosto"] for i in items)
    t["difKardexMayor"] = vk_t - mayor
    t["rebajaVnr"] = S(i["rebaja"] for i in items)
    t["excepcionNic232"] = S(i["efectoExc"] for i in items)
    t["provObsolescencia"] = S(i["obs"] for i in items)
    t["cifNoAbsorbido"] = S(x["noAbs"] for x in prod)
    t["cifExcesoCapitalizado"] = S(x["exceso"] for x in prod)
    t["difCostoVentas"] = S(x["dif"] for x in mov)
    t["corte"] = S(c["mal"] for c in cortes)
    conc = {"vk": vk_t, "mayor": mayor, "difKM": vk_t - mayor, "ext": t["difExtension"], "fis": t["difFisicas"], "costo": t["difCosto"]}
    conc["puente"] = conc["mayor"] + conc["difKM"] + conc["ext"] + conc["fis"] + conc["costo"]
    conc["control"] = t["costoAuditado"]
    conc["difControl"] = conc["puente"] - conc["control"]
    conc["prodCap"] = S(x["costo"] for x in prod)
    conc["manuf"] = S(x["cm"] for x in mov)
    conc["prodDif"] = conc["manuf"] - conc["prodCap"]
    conc["provBase"] = S(i["provBase"] for i in items)          # provisión antes de la excepción de NIC 2.32

    # Problemas (M22: cada «debe» de la norma que el cálculo no garantiza).
    vnr_n = "precio de venta menos costos de terminación y venta (PYMES 13.4, 27.2)" if pymes else "valor realizable neto (NIC 2.6 y 2.9)"
    lista = lambda xs: ", ".join(xs[:6]) + (" …" if len(xs) > 6 else "")
    pr = []
    fis = [i["id"] for i in items if i["difFis"] not in (None, 0)]
    if fis:
        pr.append(problema("DIFERENCIA_FISICA", f"Diferencias entre el conteo y el kardex en {len(fis)} ítem(s): {lista(fis)}. Neto valorizado {m(t['difFisicas'])}; "
                           f"ajuste las existencias e investigue la causa (pérdidas: gasto del ejercicio, {'PYMES no tiene párrafo expreso: por la jerarquía de 10.6 se toma NIC 2.34' if pymes else 'NIC 2.34'}).", t["difFisicas"]))
    sin_conteo = [i["id"] for i in items if i["cc"] is None]
    if sin_conteo:
        pr.append(problema("SIN_CONTEO", f"{len(sin_conteo)} ítem(s) sin cantidad contada ({lista(sin_conteo)}): se usa el kardex. "
                           "Documente la cobertura del recuento (NIA 501).", S(i["costo"] for i in items if i["cc"] is None)))
    neg = [i["id"] for i in items if i["kx"] < 0 or i["cu"] < 0]
    if neg:
        pr.append(problema("KARDEX_NEGATIVO", f"Existencias o costos negativos en el kardex: {lista(neg)}. Un inventario no puede ser negativo: corrija el kardex.",
                           S(i["vk"] for i in items if i["kx"] < 0 or i["cu"] < 0)))
    if abs(t["difExtension"]) > 0.005:
        ext = [i["id"] for i in items if abs(i["difExt"]) > 0.005]
        pr.append(problema("DIF_EXTENSION", f"Cantidad × costo unitario no da el valor del kardex en {lista(ext)}: diferencia {m(t['difExtension'])}.", t["difExtension"]))
    if abs(t["difCosto"]) > 0.005:
        pr.append(problema("DIF_COSTO_UNITARIO", f"El costo unitario soportado difiere del registrado: efecto {m(t['difCosto'])} (NIC 2.10-2.11; PYMES 13.5-13.6).", t["difCosto"]))
    if p["saldoMayor"] is None:
        pr.append(problema("SIN_MAYOR", "Ingrese el saldo del inventario según el mayor: sin él se toma el valor del kardex y no se prueba la conciliación kardex–mayor."))
    elif abs(t["difKardexMayor"]) > 0.005:
        pr.append(problema("KARDEX_MAYOR", f"El kardex ({m(vk_t)}) no concilia con el mayor ({m(mayor)}): diferencia {m(t['difKardexMayor'])}.", t["difKardexMayor"]))
    for x in mov:
        if x["apertura"] is not None and abs(x["apertura"]) > 0.005:
            pr.append(problema("APERTURA", f"{x['id']}: el inventario inicial ({m(x['ii'])}) no es el cierre auditado anterior ({m(x['ant'])}).", x["apertura"]))
    if t["cifExcesoCapitalizado"] > 0.005:
        pr.append(problema("CIF_NO_ABSORBIDO_CAPITALIZADO", f"La entidad cargó al inventario {m(t['cifExcesoCapitalizado'])} de CIF fijo no absorbido por baja producción: "
                           "debe ir a gasto del ejercicio (NIC 2.13; PYMES 13.9).", t["cifExcesoCapitalizado"]))
    if t["cifNoAbsorbido"] > 0.005:
        pr.append(problema("CIF_NO_ABSORBIDO", f"CIF fijo no absorbido (producción bajo la capacidad normal): {m(t['cifNoAbsorbido'])}; se reconoce como gasto, no como inventario.", t["cifNoAbsorbido"]))
    sin_cap = [x["id"] for x in prod if x["tasa"] is None]
    if sin_cap:
        pr.append(problema("SIN_CAPACIDAD_NORMAL", f"Sin capacidad normal en {lista(sin_cap)}: no se puede medir la absorción del CIF fijo ({'PYMES 13.9' if pymes else 'NIC 2.13'})."))
    sin_cfc = [x["id"] for x in prod if x["cfc"] is None]
    if sin_cfc:
        pr.append(problema("SIN_CIF_CAPITALIZADO", f"Falta el CIF fijo cargado al inventario por la entidad en {lista(sin_cfc)}: no se prueba si capitalizó CIF no absorbido."))
    if prod and any(x["cm"] is not None for x in mov) and abs(conc["prodDif"]) > 0.005:
        pr.append(problema("PRODUCCION_NO_CONCILIADA", f"Los costos de manufactura registrados ({m(conc['manuf'])}) difieren del costo de producción capitalizable recalculado "
                           f"({m(conc['prodCap'])}): {m(conc['prodDif'])}.", conc["prodDif"]))
    if abs(t["difCostoVentas"]) > 0.005:
        dif = [x["id"] for x in mov if abs(x["dif"]) > 0.005]
        pr.append(problema("COSTO_VENTAS", f"El costo de ventas recalculado difiere del contable en {lista(dif)}: {m(t['difCostoVentas'])}.", t["difCostoVentas"]))
    if not mov:
        pr.append(problema("SIN_MOVIMIENTO", "No se cargó el movimiento del inventario: no se recalcula el costo de ventas."))
    if t["rebajaVnr"] > 0.005:
        bajo = [i["id"] for i in items if i["rebaja"]]
        pr.append(problema("VNR_BAJO_COSTO", f"El {vnr_n} está por debajo del costo en {lista(bajo)}: rebaja {m(t['rebajaVnr'])}.", t["rebajaVnr"]))
    exc = [i["id"] for i in items if i["exceso"] > 0.005]
    if exc:
        pr.append(problema("REBAJA_MAYOR_QUE_COSTO", f"El {vnr_n} es negativo en {lista(exc)}: la rebaja calculada supera el costo de la partida y se limitó al costo "
                           f"(el inventario no puede quedar negativo). Exceso no provisionado {m(S(i['exceso'] for i in items))}: revise el precio de venta y "
                           "los costos de terminación y venta, y evalúe si hay una provisión por contrato oneroso.", S(i["exceso"] for i in items)))
    mps = [i for i in items if i["esMp"]]
    aplic = [i for i in mps if i["excepcion"]]
    if aplic:
        pr.append(problema("EXCEPCION_NIC232", f"Excepción de NIC 2.32 aplicada en {len(aplic)} materia(s) prima(s): {lista([i['id'] for i in aplic])}. No se rebajan por debajo del costo "
                           f"porque el producto terminado asociado se vendería al costo o por encima; provisión no reconocida {m(t['excepcionNic232'])}. Revise el costeo del producto "
                           "terminado y la lista de precios que sustentan el costo y el precio esperados informados.", t["excepcionNic232"]))
    if pymes and mps:
        pr.append(problema("EXCEPCION_NIC232_NO_EN_PYMES", f"{len(mps)} materia(s) prima(s) en un encargo bajo NIIF para las PYMES: las Secciones 13.19 y 27.2-27.4 no recogen la excepción "
                           "de la NIC 2.32, así que se mide al menor entre costo y precio de venta menos costos de terminación y venta aunque el producto terminado se venda con margen.",
                           S(i["provBase"] for i in mps)))
    sin_dem = [i for i in mps if i["ptMargen"] is None]
    if sin_dem and not pymes:
        pr.append(problema("MP_SIN_DEMOSTRACION_PT", f"{len(sin_dem)} materia(s) prima(s) sin el costo o el precio esperados del producto terminado asociado ({lista([i['id'] for i in sin_dem])}): "
                           "no se puede demostrar que el producto terminado se venderá al costo o por encima, así que NO se aplica la excepción de la NIC 2.32 y se mide al menor entre costo y "
                           "VNR. Pida el costeo estándar del producto terminado y su lista de precios de venta.", S(i["provBase"] for i in sin_dem)))
    mp_neg = [i for i in mps if i["ptMargen"] is not None and i["ptMargen"] < 0]
    if mp_neg and not pymes:
        pr.append(problema("MP_MARGEN_NEGATIVO", f"El costo esperado del producto terminado supera su precio esperado en {lista([i['id'] for i in mp_neg])}: no aplica la excepción de la "
                           "NIC 2.32 (el costo del producto terminado excedería su valor realizable neto) y la materia prima se rebaja hasta su VNR. Evalúe además el costo de reposición como "
                           "mejor estimación del VNR (NIC 2.32) y si hay un contrato oneroso.", S(i["provBase"] for i in mp_neg)))
    sin_pv = [i["id"] for i in items if i["pv"] is None]
    if sin_pv:
        pr.append(problema("SIN_PRECIO_VENTA", f"{len(sin_pv)} ítem(s) sin precio estimado de venta ({lista(sin_pv)}): el {vnr_n} no se midió ({'PYMES 27.2' if pymes else 'NIC 2.30'})."))
    est = [i["id"] for i in items if i["pv"] is None and i["obs"] not in (None, 0)]
    if est:
        pr.append(problema("VNR_ESTIMADO_ANTIGUEDAD", f"Sin precio de venta en {lista(est)}: el {vnr_n} se estimó por antigüedad con los % de los tramos, no con la "
                           f"evidencia más fiable disponible ({'PYMES 27.2' if pymes else 'NIC 2.30'}). Respalde el precio de venta o el porcentaje aplicado.",
                           S(i["obs"] for i in items if i["pv"] is None and i["obs"] not in (None, 0))))
    sin_f = [i["id"] for i in items if i["fum"] is None]
    if sin_f:
        pr.append(problema("SIN_FECHA_MOVIMIENTO", f"{len(sin_f)} ítem(s) sin fecha del último movimiento ({lista(sin_f)}): no se evaluó la lenta rotación."))
    if t["provObsolescencia"] > 0.005 and t["provisionEstimada"] - prov_reg > 0.005:
        pr.append(problema("LENTA_ROTACION_SIN_PROVISION", f"Hay ítems de lenta rotación u obsoletos (provisión por tramos {m(t['provObsolescencia'])}) y la provisión registrada "
                           f"({m(prov_reg)}) no cubre la estimada ({m(t['provisionEstimada'])}).", t["provisionEstimada"] - prov_reg))
    mal = [c["id"] for c in cortes if c["err"]]
    if mal:
        pr.append(problema("CORTE", f"Documentos registrados en un período distinto al de su recepción o despacho: {lista(mal)} ({m(t['corte'])}).", t["corte"]))
    if p["provisionRegistrada"] is None:
        pr.append(problema("SIN_PROVISION_REGISTRADA", "Ingrese la provisión registrada según el mayor (se toma 0) para medir el ajuste."))
    if abs(t["ajuste"]) > 0.005:
        pr.append(problema("AJUSTE", f"El inventario neto auditado ({m(t['inventarioNeto'])}) difiere del neto en libros ({m(t['libroNeto'])}).", t["ajuste"]))

    iso = lambda d: d.isoformat() if isinstance(d, date) else d
    filas = [{"id": i["id"], "descripcion": i["desc"], "bodega": i["bodega"], "cant_kardex": str(i["kx"]),
              "cant_contada": "" if i["cc"] is None else str(i["cc"]), "costo_unitario": str(i["cu"]), "valor_kardex": r2(i["vk"]),
              "costo_auditado": r2(i["costo"]), "provision": "" if i["prov"] is None else r2(i["prov"]), "_row": i["_row"]} for i in items]
    etiquetas = {
        "costoAuditado": "Inventario al costo auditado",
        "provisionEstimada": "Provisión estimada (rebaja a VNR; tramo solo sin precio; neta de la excepción NIC 2.32)",
        "inventarioNeto": "Inventario neto auditado", "saldoMayor": "Inventario según el mayor",
        "provisionRegistrada": "Provisión registrada", "libroNeto": "Inventario neto en libros", "ajuste": "Ajuste propuesto (neto)",
        "difFisicas": "Diferencias físicas valorizadas", "difExtension": "Diferencia de extensión (cantidad × costo − kardex)",
        "difCosto": "Diferencia de costo unitario", "difKardexMayor": "Diferencia kardex − mayor",
        "rebajaVnr": "Rebaja a VNR" if not pymes else "Deterioro: precio de venta menos costos (27.2)",
        "excepcionNic232": "Provisión no reconocida por la excepción de NIC 2.32 (materias primas)",
        "provObsolescencia": "Provisión por obsolescencia (tramos)", "cifNoAbsorbido": "CIF fijo no absorbido (gasto)",
        "cifExcesoCapitalizado": "CIF no absorbido capitalizado por la entidad", "difCostoVentas": "Diferencia en costo de ventas",
        "corte": "Importe con error de corte",
    }
    return {"engine": VERSION, "rows": filas, "totals": {k: r2(t[k]) for k in etiquetas}, "labels": etiquetas, "primary": "ajuste",
            "exceptions": pr, "schedule": [],
            "detalle": {"corte": corte_a.isoformat(), "pymes": pymes, "edicion": edicion_pymes(p), "parametros": p, "tot": t, "conc": conc,
                        "items": [{k: iso(v) for k, v in i.items()} for i in items], "prod": prod, "mov": mov,
                        "cortes": [{k: iso(v) for k, v in c.items()} for c in cortes]}}


# --- cédulas con fórmulas ----------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen y ajuste propuesto"), ("02_Parametros", "Parámetros"), ("03_Inventario", "Inventario valorado por ítem"),
    ("04_Conteo", "Existencia: conteo vs kardex"), ("05_Prueba_costo", "Prueba de costo"), ("06_Conciliacion", "Conciliación kardex–mayor"),
    ("07_Costo_produccion", "Costo de producción"), ("08_Costo_ventas", "Costo de ventas"), ("09_VNR", "Valor realizable neto"),
    ("10_Obsolescencia", "Obsolescencia y lenta rotación"), ("11_Excepcion_MP", "Materias primas: excepción de NIC 2.32"),
    ("12_Corte", "Prueba de corte"), ("13_Problemas", "Problemas encontrados"),
]
PARK = ["corte", "marco", "obsDias1", "obsPct1", "obsDias2", "obsPct2", "obsDias3", "obsPct3", "saldoMayor", "provisionRegistrada"]
PAR = {k: FILA0 + i for i, k in enumerate(PARK)}
P, INV, CON, COS, PRO, VEN, VNR, OBS, MP, COR = (ref(n) for n in ("02_Parametros", "03_Inventario", "04_Conteo", "05_Prueba_costo",
                                                                  "07_Costo_produccion", "08_Costo_ventas", "09_VNR", "10_Obsolescencia",
                                                                  "11_Excepcion_MP", "12_Corte"))


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
    its, prod, mov, cor = d["items"], d["prod"], d["mov"], d["cortes"]
    ni, npd, nm, nc = len(its), len(prod), len(mov), len(cor)
    pymes = d["pymes"]
    norma = (f"NIIF para las PYMES {d['edicion']} · secciones 13 y 27" if pymes else "NIIF completas · NIC 2")

    parametros = [
        ["Corte del ejercicio", d["corte"], "Ficha del encargo"],
        ["Marco y ruta de cálculo", norma, "La medición base es la misma en ambos marcos (menor entre costo y VNR / precio de venta menos costos de "
                                           "terminación y venta); cambian las citas. Ruta por marco: la excepción de NIC 2.32 para materias primas solo "
                                           "existe en NIIF completas; PYMES 13.19 y 27.2-27.4 no la recogen, así que en PYMES la cédula 11 la deniega "
                                           "siempre. PYMES 27.3 agrupa solo si es impracticable; costos por préstamos a gasto (Secc. 25)"],
        ["Tramo 1: días sin movimiento (más de)", p["obsDias1"], "Política de la entidad o juicio del auditor (NIC 2.28; PYMES 27.2). Los % solo "
                                                                 "estiman el VNR de los ítems SIN precio de venta (NIC 2.30): con precio informado "
                                                                 "manda la rebaja a VNR (NIC 2.9; PYMES 13.4)"],
        ["Tramo 1: % de provisión", p["obsPct1"], "Juicio del auditor con sustento"],
        ["Tramo 2: días sin movimiento (más de)", p["obsDias2"], "Ídem tramo 1"], ["Tramo 2: % de provisión", p["obsPct2"], "Ídem tramo 1"],
        ["Tramo 3: días sin movimiento (más de)", p["obsDias3"], "Ídem tramo 1"], ["Tramo 3: % de provisión", p["obsPct3"], "Ídem tramo 1"],
        ["Saldo del inventario según el mayor", p["saldoMayor"], "Mayor contable (en blanco: se toma el kardex)"],
        ["Provisión registrada (VNR / obsolescencia)", p["provisionRegistrada"], "Mayor contable (en blanco: 0)"],
    ]

    # 03 · Inventario (datos del cliente + cantidad, costo unitario y costo auditados).
    inventario = []
    for k, i in enumerate(its):
        r = FILA0 + k
        inventario.append([i["id"], i["desc"], i["bodega"], i["kx"], i["cc"], i["cu"], i["vk"], i["sop"], i["fum"], i["pv"],
                           i["ct"] or None, i["cv"] or None,
                           fx(f'IF(E{r}<>"",E{r},D{r})', i["cant"]), fx(f'IF(H{r}<>"",H{r},F{r})', i["cua"]), fx(f"M{r}*N{r}", i["costo"]),
                           i["mpTxt"], i["ptId"] or None, i["ptC"], i["ptP"],
                           fx(f'IF(OR(R{r}="",S{r}=""),"",S{r}-R{r})', i["ptMargen"])])
    pymes_f = f'ISNUMBER(SEARCH("PYMES",{_pa("marco")}))'
    conteo, costo, vnr, mp, obs = [], [], [], [], []
    for k, i in enumerate(its):
        r = FILA0 + k
        conteo.append([i["id"], i["desc"], i["bodega"], fx(f"{INV}D{r}", i["kx"]), fx(_si(f"{INV}E{r}"), i["cc"]),
                       fx(f'IF(E{r}="","",E{r}-D{r})', i["difCant"]), fx(f"{INV}F{r}", i["cu"]), fx(f'IF(F{r}="","",F{r}*G{r})', i["difFis"])])
        costo.append([i["id"], i["desc"], fx(f"{INV}D{r}", i["kx"]), fx(f"{INV}F{r}", i["cu"]), fx(f"C{r}*D{r}", i["recalc"]),
                      fx(f"{INV}G{r}", i["vk"]), fx(f"E{r}-F{r}", i["difExt"]), fx(_si(f"{INV}H{r}"), i["sop"]),
                      fx(f'IF(H{r}="","",H{r}-D{r})', i["difU"]), fx(f'IF(I{r}="","",I{r}*{INV}M{r})', i["difCosto"])])
        med = "Sin precio" if i["vnr"] is None else ("VNR" if i["vnr"] < i["cua"] else "Costo")
        vnr.append([i["id"], i["desc"], fx(f"{INV}M{r}", i["cant"]), fx(f"{INV}N{r}", i["cua"]), fx(_si(f"{INV}J{r}"), i["pv"]),
                    fx(f"{INV}K{r}", i["ct"]), fx(f"{INV}L{r}", i["cv"]), fx(f'IF(E{r}="","",E{r}-F{r}-G{r})', i["vnr"]),
                    fx(f'IF(H{r}="","",MIN(C{r}*D{r},MAX(0,D{r}-H{r})*C{r}))', i["rebaja"]),
                    fx(f'IF(H{r}="","Sin precio",IF(H{r}<D{r},"VNR","Costo"))', med)])
        aplica_f = f'IF(AND(C{r}="Sí",NOT({pymes_f}),G{r}<>"",G{r}>=0),"Sí","No")'
        motivo_f = (f'IF(C{r}<>"Sí","{_MOT_NO_MP}",IF({pymes_f},"{_MOT_PYMES}",IF(G{r}="","{_MOT_FALTA}",'
                    f'IF(G{r}>=0,"{_MOT_SI}","{_MOT_NEG}"))))')
        mp.append([i["id"], i["desc"], fx(f'IF({INV}P{r}="Sí","Sí","No")', i["mpTxt"]), fx(_si(f"{INV}Q{r}"), i["ptId"]),
                   fx(_si(f"{INV}R{r}"), i["ptC"]), fx(_si(f"{INV}S{r}"), i["ptP"]), fx(_si(f"{INV}T{r}"), i["ptMargen"]),
                   fx(aplica_f, "Sí" if i["excepcion"] else "No"), fx(motivo_f, i["motivoExc"]),
                   fx(_si(f"{OBS}I{r}"), i["provBase"]), fx(f'IF(AND(H{r}="Sí",J{r}<>""),J{r},0)', i["efectoExc"])])
        pct = (f'IF(E{r}="","",IF(E{r}>{_pa("obsDias3")},{_pa("obsPct3")}/100,IF(E{r}>{_pa("obsDias2")},{_pa("obsPct2")}/100,'
               f'IF(E{r}>{_pa("obsDias1")},{_pa("obsPct1")}/100,0))))')
        obs.append([i["id"], i["desc"], fx(f"{INV}O{r}", i["costo"]), i["fum"], fx(f'IF(D{r}="","",{_pa("corte")}-D{r})', i["dias"]),
                    fx(pct, i["pct"]), fx(f'IF(F{r}="","",C{r}*F{r})', i["obs"]), fx(_si(f"{VNR}I{r}"), i["rebaja"]),
                    fx(f'IF(H{r}<>"",H{r},G{r})', i["provBase"]), fx(f'IF({MP}H{r}="Sí",0,IF(I{r}="","",I{r}))', i["prov"])])

    # 07 · Costo de producción.
    produccion = []
    for k, x in enumerate(prod):
        r = FILA0 + k
        produccion.append([x["id"], x["mp"], x["mod"], x["cvar"], x["cf"], x["un"], x["cap"], x["desp"] or None,
                           fx(f'IF(OR(G{r}="",G{r}=0),"",E{r}/G{r})', x["tasa"]), fx(f'IF(I{r}="","",MIN(E{r},I{r}*F{r}))', x["abs"]),
                           fx(f'IF(J{r}="","",E{r}-J{r})', x["noAbs"]), fx(f'IF(J{r}="","",B{r}+C{r}+D{r}+J{r}-H{r})', x["costo"]),
                           fx(f'IF(OR(L{r}="",F{r}=0),"",L{r}/F{r})', x["cu"]), x["cfc"],
                           fx(f'IF(OR(N{r}="",J{r}=""),"",MAX(0,N{r}-J{r}))', x["exceso"])])

    # 08 · Costo de ventas.
    ventas = []
    for k, x in enumerate(mov):
        r = FILA0 + k
        ventas.append([x["id"], x["ii"], x["ant"], fx(f'IF(C{r}="","",B{r}-C{r})', x["apertura"]), x["cn"], x["wi"], x["cm"], x["wf"],
                       fx(f'IF(G{r}="","",F{r}+G{r}-H{r})', x["cogm"]), x["fi"], fx(f'B{r}+E{r}+IF(I{r}="",0,I{r})-J{r}', x["cogs"]),
                       x["cvc"], fx(f"K{r}-L{r}", x["dif"])])

    # 11 · Corte.
    corte = []
    for k, x in enumerate(cor):
        r = FILA0 + k
        corte.append([x["id"], x["tipo"], x["fd"], x["fr"], x["imp"],
                      fx(f'IF(C{r}<={_pa("corte")},"Ejercicio","Posterior")', x["pd"]), fx(f'IF(D{r}<={_pa("corte")},"Ejercicio","Posterior")', x["pr"]),
                      fx(f'IF(F{r}<>G{r},"Sí","No")', "Sí" if x["err"] else "No"), fx(f'IF(H{r}="Sí",E{r},0)', x["mal"]),
                      fx(f'IF(H{r}="No","",IF(F{r}="Posterior","Registrado en el ejercicio sin haber ocurrido","Ocurrido en el ejercicio y registrado después"))',
                         x["efecto"])])

    # 06 · Conciliación kardex–mayor y puente al costo auditado.
    mayor_f = f'IF({_pa("saldoMayor")}="",SUM({_rg(INV, "G", ni)}),{_pa("saldoMayor")})'
    b = lambda i: f"B{FILA0 + i}"
    conciliacion = [
        ["Valor según kardex (inventario valorado)", fx(f"SUM({_rg(INV, 'G', ni)})", c["vk"])],
        ["Saldo según el mayor", fx(mayor_f, c["mayor"])],
        ["Diferencia kardex − mayor", fx(f"{b(0)}-{b(1)}", c["difKM"])],
        ["(+) Diferencia de extensión (recalculado − kardex)", fx(f"SUM({_rg(COS, 'G', ni)})", c["ext"])],
        ["(+) Diferencias físicas valorizadas", fx(f"SUM({_rg(CON, 'H', ni)})", c["fis"])],
        ["(+) Diferencias de costo unitario", fx(f"SUM({_rg(COS, 'J', ni)})", c["costo"])],
        ["Inventario al costo auditado (puente desde el mayor)", fx(f"{b(1)}+{b(2)}+{b(3)}+{b(4)}+{b(5)}", c["puente"])],
        ["Control: costo auditado según el detalle", fx(f"SUM({_rg(INV, 'O', ni)})", c["control"])],
        ["Diferencia de control (debe ser 0)", fx(f"{b(6)}-{b(7)}", c["difControl"])],
        ["Costo de producción capitalizable recalculado (07)", fx(f"SUM({_rg(PRO, 'L', npd)})", c["prodCap"])],
        ["Costos de manufactura registrados (08)", fx(f"SUM({_rg(VEN, 'G', nm)})", c["manuf"])],
        ["Producción no conciliada (registrado − recalculado)", fx(f"{b(10)}-{b(9)}", c["prodDif"])],
    ]

    # 01 · Resumen.
    fr = {k: FILA0 + i for i, k in enumerate(res["labels"])}
    rb = lambda k: f"B{fr[k]}"
    ref_res = {
        "costoAuditado": f"SUM({_rg(INV, 'O', ni)})", "provisionEstimada": f"SUM({_rg(OBS, 'J', ni)})",
        "inventarioNeto": f"{rb('costoAuditado')}-{rb('provisionEstimada')}", "saldoMayor": mayor_f,
        "provisionRegistrada": f'IF({_pa("provisionRegistrada")}="",0,{_pa("provisionRegistrada")})',
        "libroNeto": f"{rb('saldoMayor')}-{rb('provisionRegistrada')}", "ajuste": f"{rb('inventarioNeto')}-{rb('libroNeto')}",
        "difFisicas": f"SUM({_rg(CON, 'H', ni)})", "difExtension": f"SUM({_rg(COS, 'G', ni)})", "difCosto": f"SUM({_rg(COS, 'J', ni)})",
        "difKardexMayor": f"SUM({_rg(INV, 'G', ni)})-{rb('saldoMayor')}", "rebajaVnr": f"SUM({_rg(VNR, 'I', ni)})",
        "excepcionNic232": f"SUM({_rg(MP, 'K', ni)})", "provObsolescencia": f"SUM({_rg(OBS, 'G', ni)})", "cifNoAbsorbido": f"SUM({_rg(PRO, 'K', npd)})",
        "cifExcesoCapitalizado": f"SUM({_rg(PRO, 'O', npd)})", "difCostoVentas": f"SUM({_rg(VEN, 'M', nm)})", "corte": f"SUM({_rg(COR, 'I', nc)})",
    }
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    # --- «Cómo se calcula esta hoja»: explicación humana por columna calculada -------------
    h09 = "la hoja 09 (Precio de venta menos costos)" if pymes else "la hoja 09 (Valor realizable neto)"
    ex_resumen = {"Importe": "Trae cada concepto de su hoja de origen: el costo auditado de la hoja 03, la provisión estimada y la "
                             "de obsolescencia de la hoja 10, el mayor y la provisión registrada de la hoja 02 (Parámetros), y las "
                             "diferencias de las hojas 04, 05, 07, 08, 09, 11 y 12; los netos y el ajuste se calculan con esas filas."}
    ex_inv = {
        "Cantidad auditada": "Usa la cantidad contada por el auditor; si el ítem no se contó (celda vacía), toma la cantidad del kardex.",
        "Costo unitario auditado": "Usa el costo unitario soportado por el auditor (factura o costeo); si no hay soporte, toma el "
                                   "costo unitario registrado en el kardex.",
        "Costo auditado": "Multiplica la cantidad auditada por el costo unitario auditado: es el valor del ítem que el auditor acepta.",
        "Margen esperado del producto terminado": "Precio esperado menos costo esperado del producto terminado al que se incorpora la "
                                                  "materia prima; queda en blanco si falta alguno de los dos datos.",
    }
    ex_conteo = {
        "Cantidad kardex": "Trae la cantidad registrada en el kardex para este ítem desde la hoja 03 (Inventario valorado por ítem).",
        "Cantidad contada": "Trae la cantidad contada en la toma física desde la hoja 03 (Inventario valorado por ítem); si el ítem "
                            "no se contó, queda en blanco.",
        "Diferencia (unidades)": "Cantidad contada menos cantidad del kardex: positivo es sobrante y negativo faltante. En blanco "
                                 "si el ítem no se contó.",
        "Costo unitario": "Trae el costo unitario registrado en el kardex desde la hoja 03 (Inventario valorado por ítem).",
        "Diferencia valorizada": "Multiplica la diferencia en unidades por el costo unitario del kardex: es el efecto en dólares "
                                 "del sobrante o faltante. En blanco si el ítem no se contó.",
    }
    ex_costo = {
        "Cantidad kardex": "Trae la cantidad del kardex del ítem desde la hoja 03 (Inventario valorado por ítem).",
        "Costo unitario": "Trae el costo unitario que registró el cliente en el kardex, desde la hoja 03 (Inventario valorado por ítem).",
        "Valor recalculado": "Multiplica la cantidad del kardex por su costo unitario, para comprobar la extensión del valor.",
        "Valor kardex": "Trae el valor total que el kardex del cliente muestra para el ítem, desde la hoja 03 (Inventario valorado por ítem).",
        "Diferencia de extensión": "Valor recalculado menos valor del kardex: si no es cero, el kardex tiene un error de multiplicación.",
        "Costo unitario soportado": "Trae el costo unitario que el auditor verificó con factura o costeo, desde la hoja 03; si no "
                                    "hay soporte, queda en blanco.",
        "Diferencia unitaria": "Costo unitario soportado menos costo unitario del kardex; en blanco si no hay costo soportado.",
        "Efecto en el costo auditado": "Multiplica la diferencia unitaria por la cantidad auditada de la hoja 03: es cuánto cambia "
                                       "el valor del ítem por el costo soportado. En blanco si no hay soporte.",
    }
    ex_conc = {"Importe": "Parte del valor del kardex (suma de la hoja 03) y del mayor (hoja 02; si está vacío, el kardex), suma las "
                          "diferencias de extensión y de costo de la hoja 05 y las físicas de la hoja 04 para llegar al costo auditado, "
                          "lo controla contra la hoja 03 y compara la producción de las hojas 07 y 08."}
    ex_prod = {
        "Tasa CIF fijo": "Divide el CIF fijo del período para la capacidad normal: es el CIF fijo que corresponde a cada unidad. En "
                         "blanco si no hay capacidad normal.",
        "CIF fijo absorbido": "Multiplica la tasa de CIF fijo por las unidades producidas, sin pasar del CIF fijo total: es la parte "
                              "que puede ir al costo del inventario.",
        "CIF fijo no absorbido (gasto)": "CIF fijo total menos el absorbido: es el costo de la capacidad ociosa, que va a gasto del "
                                         "período y no al inventario.",
        "Costo capitalizable": "Suma materia prima, mano de obra directa, CIF variable y CIF fijo absorbido, y resta el desperdicio "
                               "anormal: es el costo que puede quedar en el inventario (en blanco si no hay tasa de CIF fijo).",
        "Costo unitario": "Divide el costo capitalizable para las unidades producidas; en blanco si no hubo producción.",
        "No absorbido capitalizado": "Compara el CIF fijo que la entidad capitalizó con el absorbido recalculado: el exceso (nunca "
                                     "negativo) es CIF que debió ir a gasto. En blanco si falta el dato de la entidad.",
    }
    ex_ventas = {
        "Diferencia de apertura": "Inventario inicial menos el cierre auditado del año anterior: debe ser cero. En blanco si no se "
                                  "informó el cierre anterior.",
        "Costo de producción terminada (COGM)": "WIP inicial más costos de manufactura menos WIP final: es el costo de lo que se "
                                                "terminó de producir. En blanco si no hay costos de manufactura.",
        "Costo de ventas recalculado": "Inventario inicial más compras netas más el costo de producción terminada (cero si no hay) "
                                       "menos inventario final.",
        "Diferencia": "Costo de ventas recalculado menos el costo de ventas contable del cliente para la misma línea.",
    }
    ex_vnr = {
        "Cantidad auditada": "Trae la cantidad auditada del ítem (contada o, si no se contó, la del kardex) desde la hoja 03.",
        "Costo unitario auditado": "Trae el costo unitario auditado (soportado o, sin soporte, el del kardex) desde la hoja 03.",
        "Precio estimado de venta": "Trae el precio de venta unitario informado en la hoja 03 (Inventario valorado por ítem); si no "
                                    "se informó, queda en blanco.",
        "Costos de terminación": "Trae los costos unitarios que faltan para terminar el producto, desde la hoja 03 (Inventario "
                                 "valorado por ítem).",
        "Costos de venta": "Trae los costos unitarios necesarios para vender el producto, desde la hoja 03 (Inventario valorado "
                           "por ítem).",
        "VNR unitario": "Precio estimado de venta menos costos de terminación y de venta; en blanco si no hay precio de venta.",
        "Rebaja a VNR": "Si el VNR unitario es menor que el costo unitario auditado, multiplica la diferencia por la cantidad "
                        "auditada, sin pasar del costo total del ítem; si no, es cero. En blanco si no hay precio.",
        "Medición": "Indica con qué valor queda el ítem: «VNR» si el VNR es menor que el costo, «Costo» si no lo es y «Sin "
                    "precio» si no se informó precio de venta.",
    }
    ex_obs = {
        "Costo auditado": "Trae el costo auditado del ítem (cantidad × costo unitario auditados) desde la hoja 03.",
        "Días sin movimiento": "Resta la fecha del último movimiento de la fecha de corte de la hoja 02 (Parámetros); en blanco si "
                               "no hay fecha de movimiento.",
        "% de provisión": "Busca en la hoja 02 (Parámetros) el tramo de días sin movimiento que supera el ítem y toma su porcentaje "
                          "(el tramo más alto que alcanza); si no pasa del primer tramo, es 0 %.",
        "Provisión por obsolescencia": "Multiplica el costo auditado por el % de provisión del tramo; en blanco si no hay fecha de "
                                       "movimiento.",
        "Rebaja a VNR": f"Trae la rebaja a VNR del ítem desde {h09}; en blanco si el ítem no tiene precio de venta.",
        "Provisión antes de la excepción (VNR; el tramo solo si no hay precio)":
            "Si el ítem tiene precio de venta usa la rebaja a VNR; solo cuando no hay precio usa la provisión por obsolescencia "
            "del tramo como estimación.",
        "Provisión estimada (neta de la excepción NIC 2.32)":
            "Toma la provisión antes de la excepción, salvo que la hoja 11 (Materias primas) diga que aplica la excepción de "
            "NIC 2.32: en ese caso pone cero.",
    }
    ex_mp = {
        "¿Materia prima?": "Responde «Sí» si en la hoja 03 (Inventario valorado por ítem) el ítem está marcado como materia prima "
                           "y «No» en cualquier otro caso.",
        "Producto terminado asociado": "Trae de la hoja 03 el producto terminado al que se incorpora la materia prima; en blanco "
                                       "si no se informó.",
        "Costo esperado del producto terminado": "Trae de la hoja 03 el costo esperado del producto terminado asociado; en blanco "
                                                 "si no se informó.",
        "Precio esperado del producto terminado": "Trae de la hoja 03 el precio de venta esperado del producto terminado asociado; "
                                                  "en blanco si no se informó.",
        "Margen esperado": "Trae de la hoja 03 el margen esperado (precio menos costo) del producto terminado; en blanco si falta "
                           "el costo o el precio.",
        "¿Aplica la excepción de NIC 2.32?": "«Sí» solo cuando el ítem es materia prima, el marco de la hoja 02 no es PYMES y el "
                                             "margen esperado está informado y es cero o positivo; en cualquier otro caso «No».",
        "Motivo": "Explica la decisión anterior: no es materia prima, el marco es PYMES (no tiene la excepción), faltan datos del "
                  "producto terminado, o el margen esperado es positivo o negativo.",
        "Provisión antes de la excepción": "Trae la provisión del ítem antes de la excepción desde la hoja 10 (Obsolescencia y "
                                           "lenta rotación); en blanco si no se pudo calcular.",
        "Efecto: provisión no reconocida": "Si la excepción aplica, es la provisión antes de la excepción que se deja de reconocer; "
                                           "si no aplica, es cero.",
    }
    ex_corte = {
        "Período del hecho": "Compara la fecha de recepción o despacho con la fecha de corte de la hoja 02 (Parámetros): «Ejercicio» "
                             "si es igual o anterior y «Posterior» si es después.",
        "Período del registro": "Compara la fecha del registro contable con la fecha de corte de la hoja 02 (Parámetros): "
                                "«Ejercicio» si es igual o anterior y «Posterior» si es después.",
        "Error de corte": "«Sí» cuando el hecho y su registro caen en períodos distintos (uno en el ejercicio y otro después); "
                          "«No» si coinciden.",
        "Importe mal cortado": "Si hay error de corte, toma el importe del documento; si no lo hay, pone cero.",
        "Efecto": "Describe el error: si el hecho es posterior, se registró en el ejercicio sin haber ocurrido; si no, ocurrió en el "
                  "ejercicio y se registró después. Sin error, queda en blanco.",
    }

    S = lambda xs: sum(x for x in xs if x is not None)
    n_ = "n"
    return [
        hoja("01_Resumen", CEDULAS[0][1], [["Concepto", "t"], ["Importe", n_]], resumen, explica=ex_resumen),
        hoja("02_Parametros", CEDULAS[1][1], [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Inventario", CEDULAS[2][1],
             [["Código", "t"], ["Descripción", "t"], ["Bodega", "t"], ["Cantidad kardex", n_], ["Cantidad contada", n_], ["Costo unitario", n_],
              ["Valor kardex", n_], ["Costo unitario soportado", n_], ["Último movimiento", "d"], ["Precio de venta", n_],
              ["Costos de terminación", n_], ["Costos de venta", n_], ["Cantidad auditada", n_], ["Costo unitario auditado", n_], ["Costo auditado", n_],
              ["¿Materia prima?", "t"], ["Producto terminado asociado", "t"], ["Costo esperado del producto terminado", n_],
              ["Precio esperado del producto terminado", n_], ["Margen esperado del producto terminado", n_]],
             inventario, ["TOTAL", "", "", None, None, None, _tot("G", ni, c["vk"]), None, None, None, None, None, None, None,
                          _tot("O", ni, t["costoAuditado"]), "", "", None, None, None], explica=ex_inv),
        hoja("04_Conteo", CEDULAS[3][1],
             [["Código", "t"], ["Descripción", "t"], ["Bodega", "t"], ["Cantidad kardex", n_], ["Cantidad contada", n_], ["Diferencia (unidades)", n_],
              ["Costo unitario", n_], ["Diferencia valorizada", n_]],
             conteo, ["TOTAL", "", "", None, None, None, None, _tot("H", ni, t["difFisicas"])], explica=ex_conteo),
        hoja("05_Prueba_costo", CEDULAS[4][1],
             [["Código", "t"], ["Descripción", "t"], ["Cantidad kardex", n_], ["Costo unitario", n_], ["Valor recalculado", n_], ["Valor kardex", n_],
              ["Diferencia de extensión", n_], ["Costo unitario soportado", n_], ["Diferencia unitaria", n_], ["Efecto en el costo auditado", n_]],
             costo, ["TOTAL", "", None, None, _tot("E", ni, S(i["recalc"] for i in its)), _tot("F", ni, c["vk"]), _tot("G", ni, t["difExtension"]),
                     None, None, _tot("J", ni, t["difCosto"])], explica=ex_costo),
        hoja("06_Conciliacion", CEDULAS[5][1], [["Concepto", "t"], ["Importe", n_]], conciliacion, explica=ex_conc),
        hoja("07_Costo_produccion", CEDULAS[6][1],
             [["Período / orden", "t"], ["Materia prima", n_], ["MOD", n_], ["CIF variable", n_], ["CIF fijo", n_], ["Unidades producidas", n_],
              ["Capacidad normal", n_], ["Desperdicio anormal", n_], ["Tasa CIF fijo", "x"], ["CIF fijo absorbido", n_], ["CIF fijo no absorbido (gasto)", n_],
              ["Costo capitalizable", n_], ["Costo unitario", "x"], ["CIF fijo capitalizado (entidad)", n_], ["No absorbido capitalizado", n_]],
             produccion, ["TOTAL", _tot("B", npd, S(x["mp"] for x in prod)), _tot("C", npd, S(x["mod"] for x in prod)),
                          _tot("D", npd, S(x["cvar"] for x in prod)), _tot("E", npd, S(x["cf"] for x in prod)), None, None, None, None,
                          _tot("J", npd, S(x["abs"] for x in prod)), _tot("K", npd, t["cifNoAbsorbido"]), _tot("L", npd, c["prodCap"]), None, None,
                          _tot("O", npd, t["cifExcesoCapitalizado"])] if npd else None, explica=ex_prod),
        hoja("08_Costo_ventas", CEDULAS[7][1],
             [["Línea", "t"], ["Inventario inicial", n_], ["Cierre auditado anterior", n_], ["Diferencia de apertura", n_], ["Compras netas", n_],
              ["WIP inicial", n_], ["Costos de manufactura", n_], ["WIP final", n_], ["Costo de producción terminada (COGM)", n_],
              ["Inventario final", n_], ["Costo de ventas recalculado", n_], ["Costo de ventas contable", n_], ["Diferencia", n_]],
             ventas, ["TOTAL", None, None, None, None, None, None, None, None, None, _tot("K", nm, S(x["cogs"] for x in mov)),
                      _tot("L", nm, S(x["cvc"] for x in mov)), _tot("M", nm, t["difCostoVentas"])] if nm else None, explica=ex_ventas),
        hoja("09_VNR", CEDULAS[8][1] if not pymes else "Precio de venta menos costos de terminación y venta (27.2)",
             [["Código", "t"], ["Descripción", "t"], ["Cantidad auditada", n_], ["Costo unitario auditado", n_], ["Precio estimado de venta", n_],
              ["Costos de terminación", n_], ["Costos de venta", n_], ["VNR unitario", n_], ["Rebaja a VNR", n_], ["Medición", "t"]],
             vnr, ["TOTAL", "", None, None, None, None, None, None, _tot("I", ni, t["rebajaVnr"]), ""], explica=ex_vnr),
        hoja("10_Obsolescencia", CEDULAS[9][1],
             [["Código", "t"], ["Descripción", "t"], ["Costo auditado", n_], ["Último movimiento", "d"], ["Días sin movimiento", "i"],
              ["% de provisión", "p"], ["Provisión por obsolescencia", n_], ["Rebaja a VNR", n_],
              ["Provisión antes de la excepción (VNR; el tramo solo si no hay precio)", n_],
              ["Provisión estimada (neta de la excepción NIC 2.32)", n_]],
             obs, ["TOTAL", "", _tot("C", ni, t["costoAuditado"]), None, None, None, _tot("G", ni, t["provObsolescencia"]),
                   _tot("H", ni, t["rebajaVnr"]), _tot("I", ni, c["provBase"]), _tot("J", ni, t["provisionEstimada"])], explica=ex_obs),
        hoja("11_Excepcion_MP", CEDULAS[10][1],
             [["Código", "t"], ["Descripción", "t"], ["¿Materia prima?", "t"], ["Producto terminado asociado", "t"],
              ["Costo esperado del producto terminado", n_], ["Precio esperado del producto terminado", n_], ["Margen esperado", n_],
              ["¿Aplica la excepción de NIC 2.32?", "t"], ["Motivo", "t"], ["Provisión antes de la excepción", n_],
              ["Efecto: provisión no reconocida", n_]],
             mp, ["TOTAL", "", "", "", None, None, None, "", "", _tot("J", ni, c["provBase"]), _tot("K", ni, t["excepcionNic232"])], explica=ex_mp),
        hoja("12_Corte", CEDULAS[11][1],
             [["Documento", "t"], ["Tipo", "t"], ["Recepción / despacho", "d"], ["Registro contable", "d"], ["Importe", n_], ["Período del hecho", "t"],
              ["Período del registro", "t"], ["Error de corte", "t"], ["Importe mal cortado", n_], ["Efecto", "t"]],
             corte, ["TOTAL", "", None, None, _tot("E", nc, S(x["imp"] for x in cor)), "", "", "", _tot("I", nc, t["corte"]), ""] if nc else None, explica=ex_corte),
        hoja("13_Problemas", CEDULAS[12][1], [["Código", "t"], ["Descripción", "t"], ["Importe", n_]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición ------------------------------------------------------------------

def definicion() -> dict:
    inventario = ("Una fila por ítem y bodega: código, descripción, cantidad del kardex, cantidad contada (en blanco si no se contó), "
                  "costo unitario, valor del kardex, fecha del último movimiento y, si los tiene, costo soportado, precio estimado de venta "
                  "y costos unitarios de terminación y de venta. En las materias primas y suministros marque «Sí» en la columna de materia "
                  "prima e informe el producto terminado asociado con su costo y su precio de venta esperados (unitarios): sin esos tres "
                  "datos no se puede aplicar la excepción de la NIC 2.32 y la materia prima se rebaja a VNR. Sin filas de total.")
    prog = lambda code, obj, risk, asr, proc, ev, crit, src: {"code": code, "objective": obj, "risk": risk, "assertion": asr, "procedure": proc,
                                                               "evidence": ev, "criterion": crit, "source": src}
    return {
        "name": "Inventarios, producción y costo de ventas",
        "area": "Inventarios",
        "processor": "inventarios_costos",
        "frameworks": ["NIIF completas", "NIIF para las PYMES"],
        "summary": ("Prueba integral del rubro inventarios: existencia (conteo vs kardex), conciliación kardex–mayor, prueba de costo, costo de "
                    "producción con absorción del CIF fijo sobre la capacidad normal, recálculo del costo de ventas, VNR simplificado, "
                    "obsolescencia por días sin movimiento y corte de compras y ventas; propone el ajuste neto contra el mayor."),
        "source": {"organization": "IFRS Foundation · Reglamento (UE) 2023/1803 (texto en español)", "type": "Norma contable", "date": "",
                   "document": "NIC 2 Existencias · párr. 6 (definición de VNR), 9 (menor entre costo y VNR), 10-12 (costo de adquisición y transformación), 13 (capacidad "
                               "normal; CIF fijos no imputados a gasto), 16 (costos excluidos: desperdicio anormal), 25 (FIFO o costo medio "
                               "ponderado), 28-33 (VNR partida por partida, reversión; 32 materias primas), 34 (reconocimiento como gasto)",
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable",
                         "document": "NIIF para las PYMES 2015 y 2025 · Sección 13 Inventarios (13.4 medición; 13.5-13.13 costo; 13.8 costos de transformación; "
                                     "13.9 capacidad normal y CIF fijos no distribuidos a gasto; 13.18 FIFO o costo promedio ponderado; 13.19-13.20 deterioro y "
                                     "gasto) y Sección 27 (27.2-27.4 deterioro de inventarios y reversión). Ni la Sección 13 ni la 27 recogen la excepción "
                                     "de la NIC 2.32 para materias primas, así que en PYMES no se aplica. Numeración 13.4-13.20 y 27.2-27.4 igual en 2015 y "
                                     "2025; la 3.ª edición rige desde el 1-1-2027",
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 501", "section": "párr. 4 y 7", "requirement": "Presenciar el recuento físico de existencias materiales y probar sus resultados finales."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Evaluar exactitud e integridad del kardex y los anexos contra el mayor."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 16-17, 18-30 y 32", "requirement": "VNR, obsolescencia y capacidad normal son estimaciones: evaluar método, datos y supuestos."},
            {"document": "NIA 330", "section": "párr. 6-7, 18 y 20", "requirement": "Procedimientos sustantivos de corte y de conciliación con los registros."},
            {"document": "NIA 560", "section": "párr. 6 · NIA 540 párr. 21", "requirement": "Precios de venta posteriores al cierre como evidencia del VNR (NIC 2.30)."},
        ],
        "calculo": [
            "Cantidad auditada = contada (o kardex si no se contó); costo unitario auditado = soportado (o registrado); costo auditado = cantidad × costo unitario.",
            "Diferencias físicas = (contada − kardex) × costo unitario registrado.",
            "Prueba de costo: extensión = cantidad kardex × costo unitario − valor kardex; efecto del costo = (soportado − registrado) × cantidad auditada.",
            "Conciliación: valor kardex − saldo del mayor, y puente mayor + diferencias = costo auditado.",
            "Costo de producción: tasa CIF fijo = CIF fijo ÷ capacidad normal; absorbido = MIN(CIF fijo, tasa × producción real); no absorbido a gasto; "
            "costo capitalizable = MP + MOD + CIF variable + CIF fijo absorbido − desperdicio anormal (NIC 2.12, 2.13, 2.16 a).",
            "Costo de ventas = inventario inicial + compras netas + COGM − inventario final; COGM = WIP inicial + costos de manufactura − WIP final.",
            "VNR unitario = precio estimado de venta − costos de terminación − costos de venta; rebaja = MIN(costo de la partida, "
            "MAX(0, costo unitario − VNR) × cantidad), partida por partida (NIC 2.29); si el VNR es negativo la rebaja se limita al costo y se señala.",
            "Obsolescencia: % del tramo de días sin movimiento × costo auditado. La medición es al menor entre costo y VNR (NIC 2.9; PYMES 13.4): "
            "con precio de venta informado la provisión estimada del ítem es solo la rebaja a VNR; sin precio, el tramo estima el VNR por antigüedad "
            "(NIC 2.30) y se emite un problema.",
            "Materias primas (NIC 2.32, solo NIIF completas): margen esperado = precio esperado del producto terminado − costo esperado del producto "
            "terminado. Si la partida es materia prima y el margen es cero o positivo, no se rebaja por debajo del costo (provisión estimada = 0) y se "
            "informa la provisión no reconocida; si faltan el costo o el precio esperados, o el margen es negativo, la excepción NO se aplica y se mide al "
            "menor entre costo y VNR. En NIIF para las PYMES la excepción no existe (13.19 y 27.2-27.4) y nunca se aplica.",
            "Ajuste propuesto = (costo auditado − provisión estimada) − (saldo del mayor − provisión registrada).",
        ],
        "fields": _INVENTARIO, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            prog("INV-01", "Existencia", "Inventario inexistente o conteo no reflejado", "Existencia", "Presenciar el recuento y comparar cantidades contadas con el kardex",
                 "Hojas de conteo, acta e instrucciones", "Diferencias valorizadas y ajustadas", "NIA 501"),
            prog("INV-02", "Conciliación kardex–mayor", "Kardex que no respalda el saldo contable", "Integridad", "Conciliar el valor del kardex con el mayor y probar su extensión",
                 "Kardex valorado y mayor", "Diferencia explicada o ajustada", "NIA 500"),
            prog("INV-03", "Prueba de costo", "Costo unitario sin sustento o mal calculado", "Valoración", "Cotejar el costo unitario con facturas o el costeo (FIFO / promedio)",
                 "Facturas de compra, hojas de costeo", "Costo soportado = registrado", "NIC 2.10-2.11, 2.25 · PYMES 13.5-13.6, 13.18, INV-08"),
            prog("INV-04", "Costo de producción", "CIF fijo no absorbido capitalizado; desperdicio anormal en el costo", "Valoración",
                 "Recalcular la absorción del CIF fijo sobre la capacidad normal y el costo capitalizable", "Costeo de producción, capacidad normal",
                 "Solo el CIF absorbido va al inventario", "NIC 2.12-2.13, 2.16(a) · PYMES 13.8-13.9, 13.13(a), INV-07, INV-17"),
            prog("INV-05", "Costo de ventas", "Costo de ventas mal determinado", "Exactitud", "Recalcular el costo de ventas con inventarios, compras y producción",
                 "Movimiento del inventario, mayor", "Diferencia explicada", "NIC 2.34 · PYMES 13.20"),
            prog("INV-06", "Valor realizable neto", "Inventario por encima de lo recuperable", "Valoración", "Comparar costo con VNR partida por partida con precios posteriores",
                 "Ventas y listas de precios posteriores, costos de terminación y venta", "Rebaja a VNR registrada", "NIC 2.9, 2.28-2.33 · PYMES 27.2-27.4"),
            prog("INV-07", "Obsolescencia y lenta rotación", "Ítems sin movimiento sin provisión", "Valoración", "Clasificar por días sin movimiento y aplicar los % de la política",
                 "Kardex con fechas de último movimiento, política", "Provisión suficiente", "NIC 2.28 · PYMES 27.2"),
            prog("INV-09", "Materias primas: excepción de NIC 2.32", "Materia prima no rebajada apoyándose en una excepción que no se demuestra", "Valoración",
                 "Para cada materia prima con VNR bajo el costo, obtener el costeo del producto terminado asociado y su precio de venta esperado, recalcular "
                 "el margen y aplicar la excepción solo si el producto terminado se venderá al costo o por encima",
                 "Costeo estándar del producto terminado, lista de precios y pedidos en firme; costo de reposición de los materiales",
                 "Excepción aplicada solo con margen demostrado; en caso contrario, rebaja a VNR registrada",
                 "NIC 2.32 · PYMES: sin equivalente (13.19, 27.2-27.4), la excepción no se aplica"),
            prog("INV-08", "Corte", "Compras o ventas registradas en el período equivocado", "Corte", "Comparar la fecha de recepción o despacho con la de registro alrededor del cierre",
                 "Guías, facturas y asientos antes y después del corte", "Sin errores de corte o ajustados", "NIA 330, INV-04"),
        ],
        "requests": [
            req("RQ-001", "Inventario valorado por ítem (kardex) con resultado del conteo", "inventario", "INV-01", "Población, conteo, costo, VNR y obsolescencia", content=inventario),
            req("RQ-002", "Costeo de producción por período u orden", "produccion", "INV-04", "Absorción del CIF fijo y costo de producción", required=False,
                content="Una fila por período u orden: MP, MOD, CIF variable, CIF fijo, unidades producidas, capacidad normal, desperdicio anormal y CIF fijo cargado al inventario."),
            req("RQ-003", "Movimiento del inventario por línea vendida", "movimiento", "INV-05", "Recalcular el costo de ventas",
                content="Una fila por línea (mercadería, productos terminados): inventario inicial, cierre anterior, compras netas, WIP inicial, costos de manufactura, WIP final, inventario final y costo de ventas contable."),
            req("RQ-004", "Documentos de compras y ventas alrededor del corte", "corte", "INV-08", "Prueba de corte", required=False,
                content="Una fila por documento: número, tipo (Compra/Venta), fecha de recepción o despacho, fecha de registro e importe."),
            req("RQ-005", "Actas e instrucciones del recuento físico", None, "INV-01", "Soporte de la existencia", formats=("pdf", "docx"), use="soporte"),
            req("RQ-006", "Ventas y precios posteriores al cierre; costos de terminación y venta", None, "INV-06", "Soporte del VNR", formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-007", "Sustento de la capacidad normal de planta", None, "INV-04", "Soporte de la tasa de CIF fijo", formats=("pdf", "xlsx"), use="soporte", required=False),
            req("RQ-008", "Política de obsolescencia y lenta rotación", None, "INV-07", "Soporte de los tramos y porcentajes", formats=("pdf", "docx"), use="soporte"),
            req("RQ-009", "Inventario de terceros o en consignación", None, "INV-01", "Excluir lo que no es de la entidad", formats=("xlsx", "pdf"), use="soporte", required=False),
            req("RQ-010", "Costeo estándar y lista de precios de los productos terminados que consumen las materias primas", None, "INV-09",
                "Demostrar si el producto terminado se venderá al costo o por encima (excepción de NIC 2.32)", formats=("xlsx", "pdf"), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) ---------------------------------------------------------

def _it(id, desc, kx, cc, cu, vk, fum, pv="", ct="", cv="", sop="", bod="BOD1", mp="", pt="", ptc="", ptp=""):
    return {"id": id, "descripcion": desc, "bodega": bod, "cant_kardex": kx, "cant_contada": cc, "costo_unitario": cu, "valor_kardex": vk,
            "costo_soportado": sop, "fecha_ult_mov": fum, "precio_venta": pv, "costo_terminacion": ct, "costo_venta": cv,
            "materia_prima": mp, "pt_producto": pt, "pt_costo_esperado": ptc, "pt_precio_esperado": ptp, "_row": 2}


def _op(id, mp, mod, cv, cf, un, cap, desp, cfc):
    return {"id": id, "mp": mp, "mod": mod, "cif_variable": cv, "cif_fijo": cf, "unidades": un, "capacidad_normal": cap,
            "desperdicio_anormal": desp, "cif_fijo_capitalizado": cfc, "_row": 2}


def _dc(id, tipo, fd, fr, imp):
    return {"id": id, "tipo": tipo, "fecha_documento": fd, "fecha_registro": fr, "importe": imp, "_row": 2}


# Cifras a mano (corte 31-12-2025): costo auditado 41.016,00. Provisión antes de la excepción 5.575,00 = B-010 850
# (VNR 265 < costo 350) + C-102 525 (VNR 26,50 < costo 30) + C-100 1.800 (sin precio de venta: tramo 100 % sobre
# 1.800) + E-300 1.400 + E-301 500 + E-302 500. B-011 (VNR 1.150) y B-012 (VNR 70) tienen precio de venta por
# encima del costo: NIC 2.9 mide al menor entre costo y VNR, así que su tramo de obsolescencia (800 y 450) NO
# provisiona. Excepción de NIC 2.32 (materias primas), tres rutas: E-300 la aplica (margen 330 − 300 = 30 ≥ 0 →
# no se rebaja: 1.400 no reconocidos), E-301 NO la aplica (margen 560 − 600 = −40 → provisión 500), E-302 NO la
# aplica por falta del costo y el precio esperados del producto terminado (provisión 500); D-200 la aplica pero su
# provisión base es 0 (VNR 5,50 > costo 5), efecto 0. Provisión estimada 5.575 − 1.400 = 4.175,00; neto 36.841,00;
# libros 41.300 − 1.000 = 40.300,00; ajuste −3.459,00. Bajo PYMES no hay excepción: provisión 5.575 y ajuste
# −4.859,00. CIF fijo OP-01: tasa 12.000 ÷ 1.000 = 12; absorbido 12 × 800 = 9.600; no absorbido 2.400,
# capitalizado por la entidad. Costo de ventas PT: 9.000 + (3.000 + 151.750 − 4.000) − 9.900 = 149.850 vs 148.000
# contable → 1.850.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"obsDias1": 180, "obsPct1": 25, "obsDias2": 365, "obsPct2": 50, "obsDias3": 730, "obsPct3": 100,
                   "saldoMayor": 41300, "provisionRegistrada": 1000},
    "datasets": {
        "inventario": [
            _it("A-001", "Tornillo 1/4", 1000, 1000, 2.50, 2500, "2025-12-10", 4.00, "", 0.30),
            _it("A-002", "Tuerca 1/4", 500, 480, 1.20, 600, "2025-11-30", 2.00, "", 0.10),
            _it("A-003", "Arandela", 2000, 2000, 0.50, 1000, "2025-12-20", 0.90, "", "", 0.55),
            _it("B-010", "Motor 2 HP", 10, 10, 350, 3600, "2025-10-15", 300, 20, 15, bod="BOD2"),
            _it("B-011", "Bomba centrífuga", 4, 4, 800, 3200, "2025-03-01", 1200, "", 50, bod="BOD2"),
            _it("B-012", "Válvula 2\"", 20, "", 45, 900, "2024-06-30", 70, bod="BOD2"),
            _it("C-100", "Repuesto modelo descontinuado", 15, 15, 120, 1800, "2023-05-31", bod="BOD3"),
            _it("C-101", "Producto terminado X", 300, 305, 18, 5400, "2025-12-28", 25, "", 2, bod="BOD3"),
            _it("C-102", "Producto terminado Y", 150, 150, 30, 4500, "2025-12-15", 28, "", 1.5, bod="BOD3"),
            _it("D-200", "Materia prima Z", 800, 790, 5, 4000, "2025-12-05", 7, 1.5, bod="BOD4",
                mp="Sí", pt="Ensamble Z-1", ptc=60, ptp=72),
            _it("E-300", "Lámina de acero", 200, 200, 40, 8000, "2025-11-20", 34, "", 1, bod="BOD4",
                mp="Sí", pt="Tanque 200 L", ptc=300, ptp=330),
            _it("E-301", "Perfil de aluminio", 100, 100, 25, 2500, "2025-12-01", 20, bod="BOD4",
                mp="Sí", pt="Estructura AL-2", ptc=600, ptp=560),
            _it("E-302", "Resina industrial", 50, 50, 60, 3000, "2025-12-08", 52, "", 2, bod="BOD4",
                mp="Sí", pt="Envase EX-9"),
        ],
        "produccion": [
            _op("OP-01", 20000, 8000, 3000, 12000, 800, 1000, "", 12000),
            _op("OP-02", 25000, 10000, 3750, 12000, 1000, 1000, 500, 12000),
            _op("OP-03", 30000, 12000, 4500, 12000, 1200, 1000, "", 12000),
        ],
        "movimiento": [
            {"id": "Mercaderías", "inv_inicial": 10000, "inv_final_anterior": 10000, "compras_netas": 60000, "inv_final": 12000,
             "costo_ventas_contable": 58000, "_row": 2},
            {"id": "Productos terminados", "inv_inicial": 9000, "inv_final_anterior": 8500, "compras_netas": 0, "wip_inicial": 3000,
             "costos_manufactura": 151750, "wip_final": 4000, "inv_final": 9900, "costo_ventas_contable": 148000, "_row": 3},
        ],
        "corte": [
            _dc("FC-901", "Compra", "2025-12-29", "2025-12-30", 1500),
            _dc("FC-902", "Compra", "2025-12-30", "2026-01-03", 2200),
            _dc("GR-501", "Venta", "2026-01-02", "2025-12-31", 3100),
            _dc("GR-502", "Venta", "2025-12-31", "2025-12-31", 800),
            _dc("FC-903", "Compra", "2026-01-05", "2026-01-06", 950),
        ],
    },
}

_E = EJEMPLO
_SOLO_INV = {"inventario": [dict(f, cant_contada="", costo_soportado="") for f in _E["datasets"]["inventario"]]}
# Sin el costeo del producto terminado no hay demostración: ninguna excepción de NIC 2.32.
_SIN_PT = {**_E["datasets"], "inventario": [dict(f, pt_costo_esperado="", pt_precio_esperado="") for f in _E["datasets"]["inventario"]]}
# Producto terminado que se vendería por debajo de su costo: la excepción se deniega en todas las materias primas.
_MP_NEG = {**_E["datasets"], "inventario": [dict(f, pt_precio_esperado=(1 if f.get("pt_costo_esperado") not in ("", None) else ""))
                                            for f in _E["datasets"]["inventario"]]}
ESCENARIOS = [
    ("niif_completas", _E["datasets"], {**_E["parametros"], "_marco": "NIIF completas"}, _E["corte"]),
    ("pymes_2015", _E["datasets"], {**_E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"}, _E["corte"]),
    ("pymes_2025", _E["datasets"], {**_E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2025"}, _E["corte"]),
    ("mp_sin_demostracion", _SIN_PT, {**_E["parametros"], "_marco": "NIIF completas"}, _E["corte"]),
    ("mp_margen_negativo", _MP_NEG, {**_E["parametros"], "_marco": "NIIF completas"}, _E["corte"]),
    ("solo_inventario_sin_mayor", _SOLO_INV, {"obsDias1": 90, "obsPct1": 10, "obsDias2": 300, "obsPct2": 40, "obsDias3": 600, "obsPct3": 90}, _E["corte"]),
]
