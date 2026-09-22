"""Activos biológicos y agricultura (NIC 41 y NIIF 13 · NIIF para las PYMES sección 34).

Versión simple que cumple la norma, una cédula por prueba de la matriz del socio (MÓDULO 06):

1. Existencia / cantidad física: (cantidad contada − cantidad según registros) × valor unitario
   (VR menos costos de venta; si no hay VR, valor en libros por unidad).
2. Valoración (NIC 41.12; PYMES 34.4): FVLCTS_unitario = VR unitario − costo de venta unitario;
   FVLCTS_total = cantidad auditada × FVLCTS_unitario; ajuste = valor auditado − valor en libros.
3. Transformación biológica (NIC 41.26, 41.50-41.51): cambio físico = (cantidad final − inicial) × FVLCTS
   unitario inicial; cambio de precio = cantidad final × (FVLCTS final − FVLCTS inicial). Ganancia por cambio
   de VR recalculada = FVLCTS final − libros inicial − compras + disminuciones, contra la registrada.
4. Conciliación de cambios del importe en libros (NIC 41.50): inicial + compras − disminuciones + ganancia
   registrada = saldo final en libros.
5. Modelo del costo cuando procede (NIC 41.30-41.33; PYMES 34.8-34.10): costo − depreciación − deterioro, y
   deterioro adicional = MAX(0, neto − importe recuperable) (NIC 36; PYMES 27).
6. Producto agrícola (NIC 41.13 y 41.32; PYMES 34.5 activos al VR / 34.9 activos al costo): cantidad × (VR − costo de venta) en el
   punto de cosecha contra el valor registrado en inventario.

Rutas por marco: NIIF completas → plantas productoras fuera de NIC 41 (NIC 16; su producto sí es NIC 41) y el modelo
del costo solo si el VR no es fiable y el activo ya estaba al costo (41.30-41.31). PYMES → sección 34: VR si es
fácilmente determinable sin costo o esfuerzo desproporcionado; si no, costo (34.2).
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m, problema, r2, ref, req,
    validar_campos, validar_definicion_generica,
)

VERSION = "activos_biologicos 1.0"
RUBRO = "BIOLOGICOS"

_ACTIVOS = [
    campo("id", "Lote o grupo", alias=("lote", "grupo", "codigo", "piscina", "bloque"), ejemplo="G-01"),
    campo("categoria", "Categoría (ganado, plantación, camarón, flores…)", alias=("clase", "tipo", "descripcion", "especie"), ejemplo="Ganado lechero"),
    campo("unidad", "Unidad de medida", requerido=False, alias=("unidad", "um", "medida"), ejemplo="cabezas"),
    campo("planta_productora", "¿Es planta productora? (Sí/No)", requerido=False, alias=("planta productora", "bearer plant", "productora"), ejemplo="No"),
    campo("modelo_cliente", "Modelo del cliente (Valor razonable / Costo)", requerido=False, alias=("modelo", "medicion", "base de medicion"), ejemplo="Valor razonable"),
    campo("vr_medible", "VR fiable / sin esfuerzo desproporcionado para este activo (Sí/No; en blanco: parámetro general)",
          requerido=False, alias=("vr fiable", "vr medible", "valor razonable fiable"), ejemplo=""),
    campo("cant_inicial", "Cantidad al inicio del ejercicio", "number", requerido=False, alias=("cantidad inicial", "unidades iniciales"), ejemplo=120),
    campo("cant_final", "Cantidad final según registros", "number", alias=("cantidad", "cantidad final", "existencia", "unidades"), ejemplo=125),
    campo("cant_contada", "Cantidad contada (en blanco si no se contó)", "number", requerido=False, alias=("conteo", "contado", "cantidad fisica", "inventario fisico"), ejemplo=123),
    campo("vr_inicial", "VR unitario al inicio del ejercicio", "number", requerido=False, alias=("precio inicial", "vr inicial", "valor razonable inicial"), ejemplo=1500),
    campo("vr_corte", "VR unitario al corte", "number", requerido=False, alias=("precio", "vr unitario", "valor razonable", "precio de mercado"), ejemplo=1600),
    campo("costo_venta", "Costo de venta unitario", "number", requerido=False, alias=("costos de venta", "costo venta unitario", "comision"), ejemplo=40),
    campo("valor_libros", "Valor en libros registrado al corte", "number", alias=("valor libros", "saldo", "importe en libros", "valor contable"), ejemplo=195000),
    campo("libros_inicial", "Valor en libros al inicio del ejercicio", "number", requerido=False, alias=("saldo inicial", "libros inicial"), ejemplo=175200),
    campo("compras", "Compras y otros incrementos del ejercicio (al costo)", "number", requerido=False, alias=("compras", "adiciones", "nacimientos"), ejemplo=6000),
    campo("bajas", "Disminuciones al valor en libros (ventas, cosecha, depreciación)", "number", requerido=False,
          alias=("ventas", "bajas", "disminuciones", "retiros"), ejemplo=4500),
    campo("ganancia_registrada", "Ganancia (pérdida) por cambio de VR registrada en resultados", "number", requerido=False,
          alias=("ganancia registrada", "cambio vr registrado", "ajuste vr"), ejemplo=18300),
    campo("costo_acumulado", "Costo acumulado (modelo del costo)", "number", requerido=False, alias=("costo", "costo historico"), ejemplo=""),
    campo("depreciacion", "Depreciación acumulada (modelo del costo)", "number", requerido=False, alias=("depreciacion acumulada", "amortizacion"), ejemplo=""),
    campo("deterioro", "Deterioro acumulado registrado (modelo del costo)", "number", requerido=False, alias=("deterioro registrado", "perdida por deterioro"), ejemplo=""),
    campo("recuperable", "Importe recuperable estimado (modelo del costo)", "number", requerido=False, alias=("importe recuperable", "valor recuperable"), ejemplo=""),
]
CAMPOS = {
    "activos": _ACTIVOS,
    "cosecha": [
        campo("id", "Lote de origen o documento de cosecha", alias=("lote", "documento", "cosecha"), ejemplo="H-01"),
        campo("producto", "Producto agrícola cosechado", alias=("producto", "descripcion"), ejemplo="Leche"),
        campo("fecha", "Fecha o período de cosecha", "date", requerido=False, alias=("fecha cosecha", "periodo"), ejemplo="2025-12-31"),
        campo("cantidad", "Cantidad cosechada", "number", alias=("cantidad", "unidades", "kilos"), ejemplo=900000),
        campo("vr_unitario", "VR unitario en el punto de cosecha", "number", alias=("precio", "vr cosecha", "valor razonable"), ejemplo=0.45),
        campo("costo_venta", "Costo de venta unitario", "number", requerido=False, alias=("costos de venta",), ejemplo=0.03),
        campo("valor_registrado", "Valor registrado en inventario", "number", alias=("valor inventario", "registrado", "costo registrado"), ejemplo=378000),
    ],
}
TIPOS = {"activos": "activos", "cosecha": "cosecha"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "activos"
CONTROL = "valor_libros"

PARAMETROS = {"vr_fiable": "Sí", "vr_sin_esfuerzo_desproporcionado": "Sí", "saldoMayor": None}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "vr_fiable": "NIIF completas: ¿el VR de los activos puede medirse con fiabilidad? (Sí/No, NIC 41.30)",
    "vr_sin_esfuerzo_desproporcionado": "PYMES: ¿el VR es fácilmente determinable sin costo o esfuerzo desproporcionado? (Sí/No, 34.2)",
    "saldoMayor": "Saldo de activos biológicos según el mayor",
}
TOTAL_EJEMPLO = "ajuste"

VR, COSTO, NIC16 = "Valor razonable", "Costo", "NIC 16"


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    return validar_campos(CAMPOS[tipo], filas)


# --- cálculo -------------------------------------------------------------------

def _opt(v):
    """Número opcional: vacío → None (M22: lo no medido queda vacío, nunca 0)."""
    return a_num(v) if str(v if v is not None else "").strip() else None


def _txt(v) -> str:
    return str(v if v is not None else "").strip()


def _sino(v) -> str:
    s = _txt(v).lower()
    if s[:1] in ("s", "y") or s in ("1", "true", "verdadero"):
        return "Sí"
    if s[:1] == "n" or s in ("0", "false", "falso"):
        return "No"
    return ""


def _modelo(v) -> str:
    s = _txt(v).lower()
    if "cost" in s:
        return COSTO
    if "razonable" in s or s in ("vr", "fv", "fvlcts"):
        return VR
    return ""


def _parametros(parametros: dict) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    for k in ("vr_fiable", "vr_sin_esfuerzo_desproporcionado"):
        s = _sino(p[k])
        if not s:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: responda Sí o No.")
        p[k] = s
    p["saldoMayor"] = None if p.get("saldoMayor") in (None, "") else a_num(p["saldoMayor"])
    return p


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = _parametros(parametros)
    pymes = es_pymes(p)
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    general = p["vr_sin_esfuerzo_desproporcionado"] if pymes else p["vr_fiable"]

    items = []
    for f in datasets.get("activos") or []:
        cf, vl = a_num(f.get("cant_final")), a_num(f.get("valor_libros"))
        if cf is None or vl is None:
            continue
        a = {"id": _txt(f.get("id")), "cat": _txt(f.get("categoria")), "unidad": _txt(f.get("unidad")),
             "pp": _sino(f.get("planta_productora")), "mc": _modelo(f.get("modelo_cliente")), "vm": _sino(f.get("vr_medible")),
             "qi": _opt(f.get("cant_inicial")), "cf": cf, "cc": _opt(f.get("cant_contada")), "vi": _opt(f.get("vr_inicial")),
             "vc": _opt(f.get("vr_corte")), "cvRaw": _opt(f.get("costo_venta")), "vl": vl, "li": _opt(f.get("libros_inicial")),
             "comRaw": _opt(f.get("compras")), "bajRaw": _opt(f.get("bajas")), "gr": _opt(f.get("ganancia_registrada")),
             "ca": _opt(f.get("costo_acumulado")), "dep": _opt(f.get("depreciacion")), "det": _opt(f.get("deterioro")),
             "rec": _opt(f.get("recuperable")), "_row": f.get("_row")}
        a["cv"] = a["cvRaw"] or 0.0
        a["com"], a["baj"] = a["comRaw"] or 0.0, a["bajRaw"] or 0.0
        # 03 · clasificación y ruta.
        a["med"] = a["vm"] or general
        if pymes:
            a["ruta"] = VR if a["med"] == "Sí" else COSTO
        else:
            a["ruta"] = NIC16 if a["pp"] == "Sí" else (COSTO if a["med"] == "No" and a["mc"] == COSTO else VR)
        a["q"] = a["cc"] if a["cc"] is not None else cf
        a["fu"] = None if a["vc"] is None else a["vc"] - a["cv"]
        a["fi"] = None if a["vi"] is None else a["vi"] - a["cv"]
        # 04 · existencia.
        a["difQ"] = None if a["cc"] is None else a["cc"] - cf
        a["vu"] = a["fu"] if a["fu"] is not None else (vl / cf if cf else None)
        a["difFis"] = None if a["difQ"] is None or a["vu"] is None else a["difQ"] * a["vu"]
        # 08 · modelo del costo.
        a["neto"] = None if a["ruta"] != COSTO or a["ca"] is None else a["ca"] - (a["dep"] or 0) - (a["det"] or 0)
        a["detAd"] = None if a["neto"] is None or a["rec"] is None else max(0, a["neto"] - a["rec"])
        a["vCosto"] = None if a["neto"] is None else a["neto"] - (a["detAd"] or 0)
        # 05 · valoración.
        a["ftot"] = None if a["ruta"] != VR or a["fu"] is None else a["q"] * a["fu"]
        a["aud"] = vl if a["ruta"] == NIC16 else (a["ftot"] if a["ruta"] == VR else a["vCosto"])
        a["aj"] = None if a["aud"] is None else a["aud"] - vl
        # 06 · transformación biológica (NIC 41.51) y ganancia por cambio de VR.
        esvr = a["ruta"] == VR
        a["cFis"] = None if not esvr or a["qi"] is None or a["fi"] is None else (a["q"] - a["qi"]) * a["fi"]
        a["cPre"] = None if not esvr or a["fi"] is None or a["fu"] is None else a["q"] * (a["fu"] - a["fi"])
        a["cTot"] = None if a["cFis"] is None or a["cPre"] is None else a["cFis"] + a["cPre"]
        a["gan"] = None if a["ftot"] is None or a["li"] is None else a["ftot"] - a["li"] - a["com"] + a["baj"]
        a["noRec"] = None if a["gan"] is None or a["gr"] is None else a["gan"] - a["gr"]
        # 07 · conciliación NIC 41.50 con las cifras del cliente.
        a["finCalc"] = None if a["li"] is None else a["li"] + a["com"] - a["baj"] + (a["gr"] or 0)
        a["difConc"] = None if a["finCalc"] is None else vl - a["finCalc"]
        items.append(a)
    if not items:
        raise ValueError("Cargue el anexo de activos biológicos por lote o grupo (cantidad final y valor en libros).")

    cos = []
    for f in datasets.get("cosecha") or []:
        q, vu, vr_ = a_num(f.get("cantidad")), a_num(f.get("vr_unitario")), a_num(f.get("valor_registrado"))
        if None in (q, vu, vr_):
            continue
        cvr = _opt(f.get("costo_venta"))
        fch = fecha(f.get("fecha")) if _txt(f.get("fecha")) else None
        x = {"id": _txt(f.get("id")), "prod": _txt(f.get("producto")), "fecha": fch.isoformat() if fch else None, "q": q, "vu": vu,
             "cvRaw": cvr, "cv": cvr or 0.0, "reg": vr_}
        x["fu"] = vu - x["cv"]
        x["tot"] = q * x["fu"]
        x["dif"] = x["tot"] - vr_
        cos.append(x)

    S = lambda xs: sum(x for x in xs if x is not None)
    t = {"valorAuditado": S(a["aud"] for a in items), "valorLibros": S(a["vl"] for a in items), "ajuste": S(a["aj"] for a in items)}
    t["saldoMayor"] = p["saldoMayor"] if p["saldoMayor"] is not None else t["valorLibros"]
    t["difAnexoMayor"] = t["valorLibros"] - t["saldoMayor"]
    t["difFisicas"] = S(a["difFis"] for a in items)
    t["cambioFisico"] = S(a["cFis"] for a in items)
    t["cambioPrecio"] = S(a["cPre"] for a in items)
    t["cambioTotal"] = S(a["cTot"] for a in items)
    t["gananciaRecalculada"] = S(a["gan"] for a in items)
    t["gananciaRegistrada"] = S(a["gr"] for a in items)
    t["gananciaNoReconocida"] = S(a["noRec"] for a in items)
    t["difConciliacion"] = S(a["difConc"] for a in items)
    t["deterioroAdicional"] = S(a["detAd"] for a in items)
    t["plantasProductoras"] = S(a["vl"] for a in items if a["ruta"] == NIC16)
    t["cosechaRecalculada"] = S(x["tot"] for x in cos)
    t["cosechaRegistrada"] = S(x["reg"] for x in cos)
    t["difCosecha"] = S(x["dif"] for x in cos)

    # Problemas (M22: cada «debe» de la norma que el cálculo no garantiza).
    lista = lambda xs: ", ".join(xs)
    ids = lambda cond: [a["id"] for a in items if cond(a)]
    n12 = "PYMES 34.4" if pymes else "NIC 41.12"
    n26 = "PYMES 34.4" if pymes else "NIC 41.26"
    pr = []
    fis = ids(lambda a: a["difFis"] not in (None, 0))
    if fis:
        pr.append(problema("DIFERENCIA_FISICA", f"Diferencias entre el conteo y los registros en {len(fis)} lote(s): {lista(fis)}. Neto valorizado {m(t['difFisicas'])}; "
                           "ajuste las unidades e investigue la causa (mortalidad, robo, error de registro).", t["difFisicas"]))
    sc = ids(lambda a: a["cc"] is None and a["ruta"] != NIC16)
    if sc:
        pr.append(problema("SIN_CONTEO", f"{len(sc)} lote(s) sin cantidad contada ({lista(sc)}): se usan los registros. Documente el recuento o la "
                           "estimación de biomasa (NIA 501).", S(a["vl"] for a in items if a["id"] in sc)))
    neg = ids(lambda a: a["cf"] < 0 or (a["cc"] is not None and a["cc"] < 0) or a["vl"] < 0)
    if neg:
        pr.append(problema("CANTIDAD_NEGATIVA", f"Cantidades o valores negativos en {lista(neg)}: un activo biológico no puede ser negativo."))
    if abs(t["ajuste"]) > 0.005:
        dif = ids(lambda a: a["aj"] is not None and abs(a["aj"]) > 0.005)
        pr.append(problema("VALORACION_DIFIERE", f"La medición auditada difiere del valor en libros en {lista(dif)}: ajuste {m(t['ajuste'])} "
                           f"(valor razonable menos costos de venta, {n12}; modelo del costo cuando procede).", t["ajuste"]))
    svr = ids(lambda a: a["ruta"] == VR and a["vc"] is None)
    if svr:
        pr.append(problema("SIN_VR", f"{len(svr)} lote(s) a valor razonable sin VR unitario al corte ({lista(svr)}): no se midió el VR menos costos de venta "
                           f"({n12}; {'PYMES 34.6 (2015) / Sección 12 (2025)' if pymes else 'NIIF 13'}).", S(a["vl"] for a in items if a["id"] in svr)))
    scv = ids(lambda a: a["ruta"] == VR and a["cvRaw"] is None)
    if scv:
        pr.append(problema("SIN_COSTO_VENTA", f"Sin costo de venta unitario en {lista(scv)}: se toma 0. Los costos incrementales de venta se restan del VR "
                           "(NIC 41.5 y 41.12)."))
    nr = [a["id"] for a in items if a["noRec"] is not None and abs(a["noRec"]) > 0.005]
    if nr:
        pr.append(problema("CAMBIO_VR_NO_RECONOCIDO", f"La ganancia o pérdida por cambio del VR menos costos de venta recalculada ({m(t['gananciaRecalculada'])}) "
                           f"difiere de la registrada en resultados en {lista(nr)}: {m(t['gananciaNoReconocida'])} ({n26}).", t["gananciaNoReconocida"]))
    sg = ids(lambda a: a["ruta"] == VR and a["ftot"] is not None and (a["li"] is None or a["gr"] is None))
    if sg:
        pr.append(problema("SIN_GANANCIA_REGISTRADA", f"Falta el valor en libros inicial o la ganancia registrada en {lista(sg)}: no se probó que el cambio de VR "
                           "esté en resultados."))
    if abs(t["difConciliacion"]) > 0.005:
        dc = [a["id"] for a in items if a["difConc"] is not None and abs(a["difConc"]) > 0.005]
        pr.append(problema("CONCILIACION_41_50", f"La conciliación de cambios del importe en libros no cuadra en {lista(dc)}: {m(t['difConciliacion'])} "
                           "(inicial + compras − disminuciones + ganancia ≠ saldo final; NIC 41.50; PYMES 34.7 c).", t["difConciliacion"]))
    sd = ids(lambda a: a["ruta"] == VR and a["cTot"] is None)
    if sd:
        pr.append(problema("SIN_DESGLOSE_FISICO_PRECIO", f"Sin cantidad o VR inicial en {lista(sd)}: no se separó el cambio físico del cambio de precio "
                           "(recomendado por NIC 41.51)."))
    mcs = ids(lambda a: a["mc"] == COSTO and a["ruta"] == VR)
    if mcs:
        base = ("el VR es fácilmente determinable sin costo o esfuerzo desproporcionado (34.2)" if pymes else
                "se presume que el VR es fiable y la presunción solo se refuta en el reconocimiento inicial (NIC 41.30-41.31)")
        pr.append(problema("MODELO_COSTO_SIN_JUSTIFICAR", f"El cliente mide al costo {lista(mcs)} pero {base}: documente la justificación o mida a VR menos "
                           "costos de venta.", S(a["aj"] for a in items if a["id"] in mcs)))
    mvr = ids(lambda a: a["mc"] == VR and a["ruta"] == COSTO)
    if mvr:
        pr.append(problema("MODELO_VR_SIN_BASE", f"El cliente mide a VR {lista(mvr)} pero el auditor concluyó que el VR no es determinable sin esfuerzo "
                           "desproporcionado: corresponde el modelo del costo (34.2, 34.8)."))
    sco = ids(lambda a: a["ruta"] == COSTO and a["ca"] is None)
    if sco:
        pr.append(problema("SIN_COSTO", f"Lotes al modelo del costo sin costo acumulado ({lista(sco)}): no se midió costo menos depreciación y deterioro "
                           f"({'PYMES 34.8' if pymes else 'NIC 41.30 y 41.33'}).", S(a["vl"] for a in items if a["id"] in sco)))
    if t["deterioroAdicional"] > 0.005:
        dd = [a["id"] for a in items if a["detAd"]]
        pr.append(problema("DETERIORO_COSTO", f"Activos al costo con importe recuperable menor que su valor neto en {lista(dd)}: deterioro adicional "
                           f"{m(t['deterioroAdicional'])} ({'PYMES 27' if pymes else 'NIC 36 por NIC 41.33'}).", t["deterioroAdicional"]))
    pp = ids(lambda a: a["ruta"] == NIC16)
    if pp:
        pr.append(problema("PLANTA_PRODUCTORA", f"Plantas productoras fuera de NIC 41 ({lista(pp)}, {m(t['plantasProductoras'])}): se miden con NIC 16 "
                           "(herramienta de propiedades, planta y equipo); aquí se dejan al valor en libros. Su producto sí es NIC 41 (41.2 b y 41.5C).",
                           t["plantasProductoras"]))
    if p["saldoMayor"] is None:
        pr.append(problema("SIN_MAYOR", "Ingrese el saldo de activos biológicos según el mayor: sin él se toma la suma del anexo y no se prueba la conciliación."))
    elif abs(t["difAnexoMayor"]) > 0.005:
        pr.append(problema("ANEXO_MAYOR", f"El anexo ({m(t['valorLibros'])}) no concilia con el mayor ({m(t['saldoMayor'])}): {m(t['difAnexoMayor'])}.", t["difAnexoMayor"]))
    if abs(t["difCosecha"]) > 0.005:
        dc = [x["id"] for x in cos if abs(x["dif"]) > 0.005]
        pr.append(problema("COSECHA_NO_A_VR", f"Producto agrícola no medido a VR menos costos de venta en el punto de cosecha en {lista(dc)}: {m(t['difCosecha'])} "
                           f"({'PYMES 34.5 (activos al VR) / 34.9 (activos al costo)' if pymes else 'NIC 41.13 y 41.32'}; ese importe es el costo de la NIC 2).", t["difCosecha"]))
    if not cos:
        pr.append(problema("SIN_COSECHA", "No se cargó la producción agrícola cosechada: no se probó su medición en el punto de cosecha."))

    etiquetas = {
        "valorAuditado": "Activos biológicos auditados", "valorLibros": "Activos biológicos según el anexo (libros)",
        "ajuste": "Ajuste propuesto (partidas medidas)", "saldoMayor": "Activos biológicos según el mayor",
        "difAnexoMayor": "Diferencia anexo − mayor", "difFisicas": "Diferencias físicas valorizadas",
        "cambioFisico": "Cambio de VR por cambios físicos (NIC 41.51)", "cambioPrecio": "Cambio de VR por precios (NIC 41.51)",
        "cambioTotal": "Cambio total del VR menos costos de venta", "gananciaRecalculada": "Ganancia por cambio de VR recalculada",
        "gananciaRegistrada": "Ganancia por cambio de VR registrada", "gananciaNoReconocida": "Cambio de VR no reconocido (recalculado − registrado)",
        "difConciliacion": "Diferencia en la conciliación de cambios (NIC 41.50)", "deterioroAdicional": "Deterioro adicional (modelo del costo)",
        "plantasProductoras": "Plantas productoras fuera de NIC 41 (NIC 16)", "cosechaRecalculada": "Cosecha a VR menos costos de venta",
        "cosechaRegistrada": "Cosecha registrada en inventario", "difCosecha": "Diferencia en la medición de la cosecha",
    }
    if pymes:
        etiquetas["cambioFisico"], etiquetas["cambioPrecio"] = "Cambio de VR por cambios físicos", "Cambio de VR por precios"
        etiquetas["difConciliacion"] = "Diferencia en la conciliación de cambios (34.7 c)"
    filas = [{"id": a["id"], "categoria": a["cat"], "unidad": a["unidad"], "cant_final": str(a["cf"]),
              "cant_contada": "" if a["cc"] is None else str(a["cc"]), "valor_libros": r2(a["vl"]), "modelo_auditado": a["ruta"],
              "valor_auditado": "" if a["aud"] is None else r2(a["aud"]), "ajuste": "" if a["aj"] is None else r2(a["aj"]), "_row": a["_row"]}
             for a in items]
    return {"engine": VERSION, "rows": filas, "totals": {k: r2(t[k]) for k in etiquetas}, "labels": etiquetas, "primary": "ajuste",
            "exceptions": pr, "schedule": [],
            "detalle": {"corte": corte_a.isoformat(), "pymes": pymes, "edicion": edicion_pymes(p), "parametros": p, "tot": t,
                        "items": items, "cos": cos}}


# --- cédulas con fórmulas ----------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen y ajuste propuesto"), ("02_Parametros", "Parámetros y ruta por marco"),
    ("03_Activos", "Activos biológicos: clasificación y datos"), ("04_Existencia", "Existencia: conteo vs registros"),
    ("05_Valoracion", "Valoración: VR menos costos de venta"), ("06_Transformacion", "Transformación biológica y cambio de VR"),
    ("07_Conciliacion", "Conciliación de cambios (NIC 41.50)"), ("08_Modelo_costo", "Modelo del costo y deterioro"),
    ("09_Cosecha", "Producto agrícola en el punto de cosecha"), ("10_Problemas", "Problemas encontrados"),
]
PARK = ["corte", "marco", "vr_fiable", "vr_sin_esfuerzo_desproporcionado", "saldoMayor"]
PAR = {k: FILA0 + i for i, k in enumerate(PARK)}
P, ACT, EXI, VAL, TRA, CON, CST, COS = (ref(n) for n, _ in CEDULAS[1:9])


def _pa(k: str) -> str:
    return f"{P}$B${PAR[k]}"


def _rg(hoja_ref: str, col: str, n: int) -> str:
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _tot(col: str, n: int, v):
    return fx(f"SUM({col}{FILA0}:{col}{FILA0 + max(n, 1) - 1})", v)


def _si(celda: str) -> str:
    """Referencia a un dato opcional: vacío sigue vacío (una referencia simple daría 0)."""
    return f'IF({celda}="","",{celda})'


def _z(celda: str) -> str:
    return f'IF({celda}="",0,{celda})'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, t, its, cos = d["parametros"], d["tot"], d["items"], d["cos"]
    na, nc = len(its), len(cos)
    pymes = d["pymes"]
    norma = (f"NIIF para las PYMES {d['edicion']} · sección 34" + (" (PYMES 2025: 34.6 remite a la Sección 12 para el valor razonable (se sustituye la guía de 2015); vigente desde el 1-1-2027; para cortes 2025–2026 solo con adopción anticipada)" if d["edicion"] == "2025" else "")
             if pymes else "NIIF completas · NIC 41 y NIIF 13")
    ruta = ("PYMES: VR menos costos de venta si el VR es fácilmente determinable sin costo o esfuerzo desproporcionado; si no, costo menos "
            "depreciación y deterioro (34.2, 34.4, 34.8). PYMES 2015: plantas productoras dentro de la Sección 34. PYMES 2025: las plantas "
            "productoras que puedan medirse por separado sin costo o esfuerzo desproporcionado pasan a la Sección 17 (34.2 y 34.2A; 17.3 a; si no pueden medirse por separado, toda la planta sigue en la Sección 34); "
            "su producto sigue en la Sección 34 — pendiente de implementar en el cálculo" if pymes else
            "NIC 41: VR menos costos de venta (41.12); costo solo si el VR no es fiable y el activo ya estaba al costo (41.30-41.31); "
            "plantas productoras a NIC 16 (41.2 b)")
    parametros = [
        ["Corte del ejercicio", d["corte"], "Ficha del encargo"],
        ["Marco y ruta de cálculo", norma, ruta],
        [ETIQUETAS_PARAM["vr_fiable"], p["vr_fiable"], "Se aplica en NIIF completas; cada lote puede indicar otra cosa en su columna «VR fiable»"],
        [ETIQUETAS_PARAM["vr_sin_esfuerzo_desproporcionado"], p["vr_sin_esfuerzo_desproporcionado"], "Se aplica en PYMES; juicio documentado del auditor"],
        ["Saldo de activos biológicos según el mayor", p["saldoMayor"], "Mayor contable (en blanco: se toma el anexo)"],
    ]
    gen = _pa("vr_sin_esfuerzo_desproporcionado" if pymes else "vr_fiable")

    act, exi, val, tra, con, cst = [], [], [], [], [], []
    for k, a in enumerate(its):
        r = FILA0 + k
        f_ruta = (f'IF(V{r}="Sí","{VR}","{COSTO}")' if pymes else
                  f'IF(D{r}="Sí","{NIC16}",IF(AND(V{r}="No",E{r}="{COSTO}"),"{COSTO}","{VR}"))')
        act.append([a["id"], a["cat"], a["unidad"], a["pp"] or None, a["mc"] or None, a["vm"] or None, a["qi"], a["cf"], a["cc"], a["vi"], a["vc"],
                    a["cvRaw"], a["vl"], a["li"], a["comRaw"], a["bajRaw"], a["gr"], a["ca"], a["dep"], a["det"], a["rec"],
                    fx(f'IF(F{r}<>"",F{r},{gen})', a["med"]), fx(f_ruta, a["ruta"]), fx(f'IF(I{r}<>"",I{r},H{r})', a["q"]),
                    fx(f'IF(K{r}="","",K{r}-L{r})', a["fu"]), fx(f'IF(J{r}="","",J{r}-L{r})', a["fi"])])
        exi.append([a["id"], a["cat"], a["unidad"], fx(f"{ACT}H{r}", a["cf"]), fx(_si(f"{ACT}I{r}"), a["cc"]),
                    fx(f'IF(E{r}="","",E{r}-D{r})', a["difQ"]),
                    fx(f'IF({ACT}Y{r}<>"",{ACT}Y{r},IF({ACT}H{r}=0,"",{ACT}M{r}/{ACT}H{r}))', a["vu"]),
                    fx(f'IF(OR(F{r}="",G{r}=""),"",F{r}*G{r})', a["difFis"])])
        val.append([a["id"], a["cat"], fx(f"{ACT}W{r}", a["ruta"]), fx(f"{ACT}X{r}", a["q"]), fx(_si(f"{ACT}K{r}"), a["vc"]),
                    fx(f"{ACT}L{r}", a["cv"]), fx(f'IF(E{r}="","",E{r}-F{r})', a["fu"]),
                    fx(f'IF(OR(C{r}<>"{VR}",G{r}=""),"",D{r}*G{r})', a["ftot"]),
                    fx(f'IF(C{r}="{COSTO}",{_si(f"{CST}I{r}")},"")', a["vCosto"] if a["ruta"] == COSTO else None),
                    fx(f'IF(C{r}="{NIC16}",K{r},IF(C{r}="{VR}",H{r},I{r}))', a["aud"]), fx(f"{ACT}M{r}", a["vl"]),
                    fx(f'IF(J{r}="","",J{r}-K{r})', a["aj"])])
        tra.append([a["id"], fx(f"{VAL}C{r}", a["ruta"]), fx(_si(f"{ACT}G{r}"), a["qi"]), fx(f"{ACT}X{r}", a["q"]),
                    fx(_si(f"{ACT}Z{r}"), a["fi"]), fx(_si(f"{ACT}Y{r}"), a["fu"]),
                    fx(f'IF(OR(B{r}<>"{VR}",C{r}="",E{r}=""),"",(D{r}-C{r})*E{r})', a["cFis"]),
                    fx(f'IF(OR(B{r}<>"{VR}",E{r}="",F{r}=""),"",D{r}*(F{r}-E{r}))', a["cPre"]),
                    fx(f'IF(OR(G{r}="",H{r}=""),"",G{r}+H{r})', a["cTot"]),
                    fx(_si(f"{ACT}N{r}"), a["li"]), fx(_z(f"{ACT}O{r}"), a["com"]), fx(_z(f"{ACT}P{r}"), a["baj"]),
                    fx(_si(f"{VAL}H{r}"), a["ftot"]), fx(f'IF(OR(M{r}="",J{r}=""),"",M{r}-J{r}-K{r}+L{r})', a["gan"]),
                    fx(_si(f"{ACT}Q{r}"), a["gr"]), fx(f'IF(OR(N{r}="",O{r}=""),"",N{r}-O{r})', a["noRec"])])
        con.append([a["id"], a["cat"], fx(_si(f"{ACT}N{r}"), a["li"]), fx(_z(f"{ACT}O{r}"), a["com"]), fx(_z(f"{ACT}P{r}"), a["baj"]),
                    fx(_si(f"{ACT}Q{r}"), a["gr"]), fx(f'IF(C{r}="","",C{r}+D{r}-E{r}+IF(F{r}="",0,F{r}))', a["finCalc"]),
                    fx(f"{ACT}M{r}", a["vl"]), fx(f'IF(G{r}="","",H{r}-G{r})', a["difConc"])])
        cst.append([a["id"], fx(f"{ACT}W{r}", a["ruta"]), fx(_si(f"{ACT}R{r}"), a["ca"]), fx(_si(f"{ACT}S{r}"), a["dep"]),
                    fx(_si(f"{ACT}T{r}"), a["det"]),
                    fx(f'IF(OR(B{r}<>"{COSTO}",C{r}=""),"",C{r}-IF(D{r}="",0,D{r})-IF(E{r}="",0,E{r}))', a["neto"]),
                    fx(_si(f"{ACT}U{r}"), a["rec"]), fx(f'IF(OR(F{r}="",G{r}=""),"",MAX(0,F{r}-G{r}))', a["detAd"]),
                    fx(f'IF(F{r}="","",F{r}-IF(H{r}="",0,H{r}))', a["vCosto"])])

    cosecha = []
    for k, x in enumerate(cos):
        r = FILA0 + k
        cosecha.append([x["id"], x["prod"], x["fecha"], x["q"], x["vu"], x["cvRaw"], fx(f"E{r}-F{r}", x["fu"]), fx(f"D{r}*G{r}", x["tot"]),
                        x["reg"], fx(f"H{r}-I{r}", x["dif"])])

    fr = {k: FILA0 + i for i, k in enumerate(res["labels"])}
    rb = lambda k: f"B{fr[k]}"
    ref_res = {
        "valorAuditado": f"SUM({_rg(VAL, 'J', na)})", "valorLibros": f"SUM({_rg(ACT, 'M', na)})", "ajuste": f"SUM({_rg(VAL, 'L', na)})",
        "saldoMayor": f'IF({_pa("saldoMayor")}="",SUM({_rg(ACT, "M", na)}),{_pa("saldoMayor")})',
        "difAnexoMayor": f"{rb('valorLibros')}-{rb('saldoMayor')}", "difFisicas": f"SUM({_rg(EXI, 'H', na)})",
        "cambioFisico": f"SUM({_rg(TRA, 'G', na)})", "cambioPrecio": f"SUM({_rg(TRA, 'H', na)})", "cambioTotal": f"SUM({_rg(TRA, 'I', na)})",
        "gananciaRecalculada": f"SUM({_rg(TRA, 'N', na)})", "gananciaRegistrada": f"SUM({_rg(ACT, 'Q', na)})",
        "gananciaNoReconocida": f"SUM({_rg(TRA, 'P', na)})", "difConciliacion": f"SUM({_rg(CON, 'I', na)})",
        "deterioroAdicional": f"SUM({_rg(CST, 'H', na)})",
        "plantasProductoras": f'SUMIF({_rg(VAL, "C", na)},"{NIC16}",{_rg(VAL, "K", na)})',
        "cosechaRecalculada": f"SUM({_rg(COS, 'H', nc)})", "cosechaRegistrada": f"SUM({_rg(COS, 'I', nc)})", "difCosecha": f"SUM({_rg(COS, 'J', nc)})",
    }
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    S = lambda xs: sum(x for x in xs if x is not None)
    n_ = "n"
    return [
        hoja("01_Resumen", CEDULAS[0][1], [["Concepto", "t"], ["Importe", n_]], resumen),
        hoja("02_Parametros", CEDULAS[1][1], [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Activos", CEDULAS[2][1],
             [["Lote", "t"], ["Categoría", "t"], ["Unidad", "t"], ["Planta productora", "t"], ["Modelo del cliente", "t"], ["VR fiable (lote)", "t"],
              ["Cantidad inicial", n_], ["Cantidad según registros", n_], ["Cantidad contada", n_], ["VR unitario inicial", n_], ["VR unitario al corte", n_],
              ["Costo de venta unitario", n_], ["Valor en libros", n_], ["Libros al inicio", n_], ["Compras e incrementos", n_], ["Disminuciones", n_],
              ["Ganancia VR registrada", n_], ["Costo acumulado", n_], ["Depreciación acumulada", n_], ["Deterioro registrado", n_],
              ["Importe recuperable", n_], ["VR medible (aplicado)", "t"], ["Modelo auditado", "t"], ["Cantidad auditada", n_],
              ["VR − costos de venta unitario", n_], ["VR − costos de venta unitario inicial", n_]],
             act, ["TOTAL", "", "", "", "", "", None, None, None, None, None, None, _tot("M", na, t["valorLibros"]), None, None, None,
                   _tot("Q", na, t["gananciaRegistrada"]), None, None, None, None, "", "", None, None, None]),
        hoja("04_Existencia", CEDULAS[3][1],
             [["Lote", "t"], ["Categoría", "t"], ["Unidad", "t"], ["Cantidad según registros", n_], ["Cantidad contada", n_], ["Diferencia (unidades)", n_],
              ["Valor unitario", n_], ["Diferencia valorizada", n_]],
             exi, ["TOTAL", "", "", None, None, None, None, _tot("H", na, t["difFisicas"])]),
        hoja("05_Valoracion", CEDULAS[4][1],
             [["Lote", "t"], ["Categoría", "t"], ["Modelo auditado", "t"], ["Cantidad auditada", n_], ["VR unitario al corte", n_],
              ["Costo de venta unitario", n_], ["VR − costos de venta unitario", n_], ["VR − costos de venta total", n_], ["Valor modelo del costo", n_],
              ["Valor auditado", n_], ["Valor en libros", n_], ["Ajuste", n_]],
             val, ["TOTAL", "", "", None, None, None, None, _tot("H", na, S(a["ftot"] for a in its)), _tot("I", na, S(a["vCosto"] for a in its)),
                   _tot("J", na, t["valorAuditado"]), _tot("K", na, t["valorLibros"]), _tot("L", na, t["ajuste"])]),
        hoja("06_Transformacion", CEDULAS[5][1],
             [["Lote", "t"], ["Modelo auditado", "t"], ["Cantidad inicial", n_], ["Cantidad final auditada", n_], ["VR − CV unitario inicial", n_],
              ["VR − CV unitario final", n_], ["Cambio físico", n_], ["Cambio de precio", n_], ["Cambio total", n_], ["Libros al inicio", n_],
              ["Compras", n_], ["Disminuciones", n_], ["VR − CV final total", n_], ["Ganancia recalculada", n_], ["Ganancia registrada", n_],
              ["No reconocido", n_]],
             tra, ["TOTAL", "", None, None, None, None, _tot("G", na, t["cambioFisico"]), _tot("H", na, t["cambioPrecio"]),
                   _tot("I", na, t["cambioTotal"]), None, None, None, None, _tot("N", na, t["gananciaRecalculada"]), None,
                   _tot("P", na, t["gananciaNoReconocida"])]),
        hoja("07_Conciliacion", CEDULAS[6][1] if not pymes else "Conciliación de cambios (34.7 c)",
             [["Lote", "t"], ["Categoría", "t"], ["Libros al inicio", n_], ["(+) Compras e incrementos", n_], ["(−) Disminuciones", n_],
              ["(+) Ganancia VR registrada", n_], ["Saldo final calculado", n_], ["Saldo final en libros", n_], ["Diferencia", n_]],
             con, ["TOTAL", "", _tot("C", na, S(a["li"] for a in its)), _tot("D", na, S(a["com"] for a in its)), _tot("E", na, S(a["baj"] for a in its)),
                   _tot("F", na, t["gananciaRegistrada"]), _tot("G", na, S(a["finCalc"] for a in its)), _tot("H", na, t["valorLibros"]),
                   _tot("I", na, t["difConciliacion"])]),
        hoja("08_Modelo_costo", CEDULAS[7][1],
             [["Lote", "t"], ["Modelo auditado", "t"], ["Costo acumulado", n_], ["Depreciación acumulada", n_], ["Deterioro registrado", n_],
              ["Valor neto al costo", n_], ["Importe recuperable", n_], ["Deterioro adicional", n_], ["Valor auditado al costo", n_]],
             cst, ["TOTAL", "", None, None, None, _tot("F", na, S(a["neto"] for a in its)), None, _tot("H", na, t["deterioroAdicional"]),
                   _tot("I", na, S(a["vCosto"] for a in its))]),
        hoja("09_Cosecha", CEDULAS[8][1],
             [["Lote / documento", "t"], ["Producto", "t"], ["Fecha", "d"], ["Cantidad", n_], ["VR unitario en cosecha", n_], ["Costo de venta unitario", n_],
              ["VR − costos de venta unitario", n_], ["VR − costos de venta total", n_], ["Valor registrado", n_], ["Diferencia", n_]],
             cosecha, ["TOTAL", "", None, None, None, None, None, _tot("H", nc, t["cosechaRecalculada"]), _tot("I", nc, t["cosechaRegistrada"]),
                       _tot("J", nc, t["difCosecha"])] if nc else None),
        hoja("10_Problemas", CEDULAS[9][1], [["Código", "t"], ["Descripción", "t"], ["Importe", n_]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición ------------------------------------------------------------------

def definicion() -> dict:
    activos = ("Una fila por lote o grupo homogéneo (ganado, plantación, camarón, flores…): categoría, unidad, si es planta productora, "
               "modelo del cliente, cantidad inicial, cantidad final según registros, cantidad contada, VR unitario inicial y al corte, costo de "
               "venta unitario, valor en libros al corte y al inicio, compras, disminuciones y ganancia por cambio de VR registrada; si mide al "
               "costo, costo acumulado, depreciación, deterioro e importe recuperable. Sin filas de total.")
    prog = lambda code, obj, risk, asr, proc, ev, crit, src: {"code": code, "objective": obj, "risk": risk, "assertion": asr, "procedure": proc,
                                                               "evidence": ev, "criterion": crit, "source": src}
    return {
        "name": "Activos biológicos y agricultura",
        "area": "Activos biológicos",
        "processor": "activos_biologicos",
        "frameworks": ["NIIF completas", "NIIF para las PYMES"],
        "summary": ("Prueba del rubro activos biológicos: existencia física (conteo vs registros), valoración a valor razonable menos costos de "
                    "venta, desglose del cambio de VR en físico y de precio, ganancia por cambio de VR recalculada contra la registrada, "
                    "conciliación de cambios del importe en libros, modelo del costo con deterioro cuando procede y medición del producto "
                    "agrícola en el punto de cosecha; propone el ajuste contra el valor en libros."),
        "source": {"organization": "IFRS Foundation · Reglamento (UE) 2023/1803 (texto en español)", "type": "Norma contable", "date": "",
                   "document": "NIC 41 Agricultura · párr. 1-2 (alcance; plantas productoras a NIC 16, su producto en NIC 41), 5-5C (definiciones: "
                               "costos de venta, planta productora), 10 (reconocimiento), 12 (VR menos costos de venta), 13 y 32 (producto "
                               "agrícola en el punto de cosecha), 26-29 (ganancias y pérdidas en resultados), 30-31 (presunción de fiabilidad "
                               "refutable solo en el reconocimiento inicial; modelo del costo), 33 (NIC 2, 16 y 36), 40, 46 (cantidades físicas), "
                               "50 (conciliación de cambios), 51 (cambios físicos y de precio, recomendado), 54-55 (revelaciones al costo). "
                               "NIIF 13 para la medición del VR, párr. 72–90 (jerarquía: nivel 1: 76; nivel 2: 81; nivel 3: 86)",
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable",
                         "document": "NIIF para las PYMES 2015 · Sección 34 Actividades especiales, 34.2-34.10: modelo del valor razonable cuando "
                                     "el VR es fácilmente determinable sin costo o esfuerzo desproporcionado (34.2, 34.4-34.7; producto agrícola a "
                                     "VR menos costos de venta en la cosecha 34.5); en los demás casos modelo del costo, costo menos depreciación y "
                                     "deterioro (34.8-34.10). Conciliación de cambios: 34.7 c). PYMES 2025 (tercera edición): Sección 12 para el valor "
                                     "razonable (34.6 remite a ella; se sustituye la guía de 2015); las plantas productoras que puedan medirse por separado sin costo o esfuerzo "
                                     "desproporcionado pasan a la Sección 17 (34.2 y 34.2A; 17.3 a; si no pueden medirse por separado, toda la planta sigue en la Sección 34) y su producto sigue en la Sección 34; vigente "
                                     "desde el 1-1-2027; para cortes 2025–2026 solo con adopción anticipada. 34.3 reconocimiento; 34.9 producto agrícola en el modelo del costo",
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 501", "section": "párr. 4 (aplicada por analogía; el párr. 4 trata de inventarios)", "requirement": "Presenciar el recuento de los activos biológicos materiales y probar sus resultados."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 16–17, 18–27 y 28–30", "requirement": "El VR menos costos de venta es una estimación: evaluar método, datos y supuestos."},
            {"document": "NIA 500", "section": "párr. 8 si el perito es del cliente (NIA 620 solo si lo contrata el auditor)", "requirement": "Evaluar el trabajo del experto (veterinario, ingeniero forestal, biólogo o valuador)."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del anexo contra el mayor y los registros de campo."},
            {"document": "NIA 330", "section": "párr. 18 y 20", "requirement": "Procedimientos sustantivos y conciliación de los estados con los registros."},
        ],
        "calculo": [
            "Cantidad auditada = contada (o según registros si no se contó); diferencia física = (contada − registros) × VR menos costos de venta unitario.",
            "FVLCTS unitario = VR unitario − costo de venta unitario; FVLCTS total = cantidad auditada × FVLCTS unitario (NIC 41.12; PYMES 34.4).",
            "Ruta: NIIF completas → plantas productoras a NIC 16; costo solo si el VR no es fiable y el cliente ya medía al costo (41.30-41.31). "
            "PYMES → VR si es fácilmente determinable sin costo o esfuerzo desproporcionado; si no, costo (34.2). PYMES 2025: la exclusión de plantas "
            "productoras separables (34.2A) aún no se aplica en el cálculo: pendiente de decisión del socio.",
            "Modelo del costo: costo − depreciación − deterioro registrado; deterioro adicional = MAX(0, neto − importe recuperable).",
            "Ajuste = valor auditado − valor en libros.",
            "Cambio físico = (cantidad final − inicial) × FVLCTS unitario inicial; cambio de precio = cantidad final × (FVLCTS final − inicial) (NIC 41.51).",
            "Ganancia por cambio de VR recalculada = FVLCTS final − libros al inicio − compras + disminuciones; se compara con la registrada en resultados (41.26).",
            "Conciliación NIC 41.50: libros al inicio + compras − disminuciones + ganancia registrada = saldo final en libros.",
            "Cosecha: cantidad × (VR − costo de venta) en el punto de cosecha vs valor registrado en inventario (NIC 41.13, 41.32).",
        ],
        "fields": _ACTIVOS, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            prog("BIO-01", "Clasificación", "Plantas productoras o activos fuera de alcance medidos con NIC 41", "Clasificación",
                 "Clasificar cada lote: consumo/productor, planta productora (NIC 16) o activo biológico (NIC 41)", "Descripción de lotes, políticas",
                 "Cada lote en la norma que le corresponde", "NIC 41.1-2, 41.5-5C · PYMES 34.2, BIO-07"),
            prog("BIO-02", "Existencia", "Animales o plantas inexistentes, mortalidad no registrada", "Existencia", "Presenciar el conteo o la estimación de biomasa y compararlo con los registros",
                 "Actas de conteo, registros de campo, informes de mortalidad", "Diferencias valorizadas y ajustadas", "NIA 501"),
            prog("BIO-03", "Valoración", "Activos no medidos a VR menos costos de venta", "Valoración", "Recalcular VR menos costos de venta con precios de mercado y costos de venta",
                 "Cotizaciones de mercado, informes de peritos, costos de flete y comisiones", "Valor auditado = libros", "NIC 41.12, NIIF 13 · PYMES 34.4"),
            prog("BIO-04", "Transformación biológica", "Cambio de VR no reconocido en resultados", "Exactitud", "Separar el cambio físico y de precio y recalcular la ganancia del ejercicio",
                 "Anexo inicial y final, mayor de resultados", "Ganancia registrada = recalculada", "NIC 41.26, 41.50-41.51 · PYMES 34.4, BIO-05"),
            prog("BIO-05", "Producto agrícola", "Cosecha registrada al costo y no a VR menos costos de venta", "Valoración",
                 "Recalcular la cosecha a VR menos costos de venta en el punto de cosecha", "Reportes de cosecha, precios a la fecha de cosecha",
                 "Inventario inicial del producto = VR menos costos de venta", "NIC 41.13, 41.32 · PYMES 34.5"),
            prog("BIO-06", "Modelo del costo y deterioro", "Modelo del costo sin justificación; deterioro no reconocido", "Valoración",
                 "Evaluar la justificación del modelo del costo y comparar el neto con el importe recuperable", "Análisis de fiabilidad del VR, costeo, tasación",
                 "Costo solo si procede; sin exceso sobre el recuperable", "NIC 41.30-41.33, NIC 36 · PYMES 34.8-34.10, 27"),
            prog("BIO-07", "Conciliación y revelaciones", "Conciliación de cambios incompleta", "Presentación", "Conciliar los cambios del importe en libros y el anexo con el mayor",
                 "Movimiento del rubro, mayor", "Conciliación cuadrada y revelada", "NIC 41.50 · PYMES 34.7 c)"),
        ],
        "requests": [
            req("RQ-001", "Anexo de activos biológicos por lote con conteo, precios y movimiento", "activos", "BIO-02", "Existencia, valoración, cambio de VR y conciliación", content=activos),
            req("RQ-002", "Producción agrícola cosechada en el ejercicio", "cosecha", "BIO-05", "Medición del producto agrícola en el punto de cosecha", required=False,
                content="Una fila por cosecha o producto: lote, producto, fecha, cantidad, VR unitario en la cosecha, costo de venta unitario y valor registrado en inventario."),
            req("RQ-003", "Precios de mercado o informe del perito valuador al corte", None, "BIO-03", "Soporte del VR (NIIF 13)", formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-004", "Detalle de costos de venta (fletes, comisiones, tasas)", None, "BIO-03", "Soporte del costo de venta unitario", formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-005", "Actas de conteo y registros de campo (nacimientos, mortalidad, biomasa)", None, "BIO-02", "Soporte de la existencia", formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-006", "Análisis de plantas productoras y de la fiabilidad del VR", None, "BIO-01", "Clasificación y justificación del modelo del costo",
                formats=("pdf", "docx"), use="soporte", required=False),
            req("RQ-007", "Mayor de activos biológicos y de resultados por cambio de VR", None, "BIO-07", "Conciliación con libros", formats=("xlsx", "pdf"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) ---------------------------------------------------------

def _a(id, cat, un, qi, qf, cc, vi, vc, cv, vl, li, com, baj, gr, mc="Valor razonable", pp="No", vm="", ca="", dep="", det="", rec=""):
    return {"id": id, "categoria": cat, "unidad": un, "planta_productora": pp, "modelo_cliente": mc, "vr_medible": vm, "cant_inicial": qi,
            "cant_final": qf, "cant_contada": cc, "vr_inicial": vi, "vr_corte": vc, "costo_venta": cv, "valor_libros": vl, "libros_inicial": li,
            "compras": com, "bajas": baj, "ganancia_registrada": gr, "costo_acumulado": ca, "depreciacion": dep, "deterioro": det,
            "recuperable": rec, "_row": 2}


def _h(id, prod, q, vu, cv, reg):
    return {"id": id, "producto": prod, "fecha": "2025-12-31", "cantidad": q, "vr_unitario": vu, "costo_venta": cv, "valor_registrado": reg, "_row": 2}


# Cifras a mano (NIIF completas, corte 31-12-2025): valor auditado 1.524.120; libros 1.501.800; ajuste 22.320
# (G-01 123 × 1.560 = 191.880 − 195.000 = −3.120; G-02 280 × 825 − 224.000 = 7.000; C-01 45.000 × 3,0 − 130.000 = 5.000;
# G-03 al costo 60.000 − 18.000 = 42.000, recuperable 38.000 → −4.000; G-04 418 × 180 − 63.000 = 12.240; P-02 80 × 850 −
# 64.000 = 4.000; C-02 12.500 × 2,4 − 28.800 = 1.200). Cosecha 796.000 vs 782.000 → 14.000.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"vr_fiable": "Sí", "vr_sin_esfuerzo_desproporcionado": "Sí", "saldoMayor": 1500000},
    "datasets": {
        "activos": [
            _a("G-01", "Ganado lechero", "cabezas", 120, 125, 123, 1500, 1600, 40, 195000, 175200, 6000, 4500, 18300),
            _a("G-02", "Ganado de engorde", "cabezas", 300, 280, 280, 800, 850, 25, 224000, 232500, 40000, 48500, 0),
            _a("P-01", "Plantación de teca", "hectáreas", 50, 50, 50, 12000, 13500, 500, 650000, 575000, 0, 0, 75000),
            _a("C-01", "Camarón en piscinas", "kg", 20000, 45000, "", 3.0, 3.2, 0.2, 130000, 56000, 30000, 0, 44000),
            _a("F-01", "Rosales en producción", "plantas", 100000, 100000, 100000, "", "", "", 80000, 80000, 0, 0, "", mc="Costo", pp="Sí"),
            _a("F-02", "Botones de rosa en crecimiento", "tallos", 200000, 250000, 250000, 0.10, 0.12, 0.02, 25000, 16000, 0, 0, 8000),
            _a("G-03", "Toros reproductores importados", "cabezas", 5, 5, 5, "", "", "", 42000, 48000, 0, 6000, "", mc="Costo", vm="No",
               ca=60000, dep=18000, det=0, rec=38000),
            _a("G-04", "Cerdos de engorde", "cabezas", 400, 420, 418, 180, 190, 10, 63000, 60000, 20000, 17000, 0, mc="Costo", ca=63000),
            _a("P-02", "Cultivo de maíz", "hectáreas", 0, 80, 80, "", 900, 50, 64000, 0, 64000, 0, 0),
            _a("C-02", "Tilapia en estanques", "kg", 10000, 12000, 12500, 2.5, 2.4, "", 28800, 25000, 5000, 3000, 1800),
        ],
        "cosecha": [
            _h("H-01", "Leche", 900000, 0.45, 0.03, 378000),
            _h("H-02", "Madera de teca (raleo)", 200, 180, 20, 25000),
            _h("H-03", "Camarón cosechado", 60000, 3.4, 0.2, 192000),
            _h("H-04", "Rosas (tallos)", 1200000, 0.15, 0.02, 150000),
            _h("H-05", "Tilapia cosechada", 8000, 2.6, 0.1, 20000),
            _h("H-06", "Cerdos sacrificados", 100, 190, 10, 17000),
        ],
    },
}

_E = EJEMPLO
ESCENARIOS = [
    ("niif_completas", _E["datasets"], {**_E["parametros"], "_marco": "NIIF completas"}, _E["corte"]),
    ("completas_vr_no_fiable", _E["datasets"], {**_E["parametros"], "vr_fiable": "No", "_marco": "NIIF completas"}, _E["corte"]),
    ("pymes_2015", _E["datasets"], {**_E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"}, _E["corte"]),
    ("pymes_2025_costo", _E["datasets"], {"vr_sin_esfuerzo_desproporcionado": "No", "_marco": "NIIF para las PYMES", "_edicion": "2025"}, _E["corte"]),
    ("solo_activos_sin_mayor", {"activos": _E["datasets"]["activos"]}, {}, _E["corte"]),
]
