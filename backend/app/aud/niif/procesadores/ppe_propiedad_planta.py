"""Propiedad, planta y equipo: recálculo de depreciación, bajas, revaluación, deterioro, costos por
préstamos, componentes, desmantelamiento y conciliación del auxiliar con el mayor.

Versión simple que cumple la norma (NIC 16 / Sección 17):

1. Cada fila del auxiliar es un elemento o una parte (componente) con su propia vida útil: las partes
   significativas se deprecian por separado (NIC 16.43–47; PYMES 17.16). Toda adición del año que no
   forme parte de un elemento ya existente se registra como fila propia con su fecha de disponibilidad.
2. Depreciación lineal del período = (costo − residual) ÷ vida útil (meses) × 12 × días en uso ÷ días del
   año, sin pasar del importe depreciable pendiente (NIC 16.50, 53, 55; PYMES 17.18–17.22). Empieza cuando
   el activo está disponible para su uso y cesa en la baja; las construcciones en curso no se deprecian.
   Otros métodos (unidades producidas, saldo decreciente) no se recalculan: quedan en blanco (M22).
3. Valor neto en libros = costo − depreciación acumulada − deterioro acumulado.
4. Bajas: ganancia/pérdida = producto − valor neto en libros a la fecha de baja (NIC 16.68, 71; PYMES 17.28–17.30).
5. Revaluación (fecha de revaluación = corte): el aumento va a resultados hasta revertir el decremento previo
   del mismo activo reconocido en resultados y el resto a otro resultado integral (NIC 16.39; PYMES 17.15C);
   la disminución va a ORI hasta el superávit previo del activo y el resto a resultados (NIC 16.40; PYMES
   17.15D); clase completa (16.36; 17.15). Sin el dato del decremento previo, todo queda en ORI y se avisa.
6. Deterioro: pérdida = max(importe en libros − importe recuperable, 0) (NIC 36.59; PYMES 27.5). Si el activo
   está revaluado, la pérdida se imputa primero contra el superávit de revaluación de ese activo y solo el
   exceso a resultados (NIC 36.60–61; PYMES 27.6); sin el superávit informado no se reparte y se avisa.
7. Costos por préstamos (NIIF completas). Con el anexo de préstamos para la construcción se calcula por
   activo: el préstamo específico aporta el costo financiero del período realmente incurrido menos los
   rendimientos de la inversión temporal de esos fondos (NIC 23.12) y los préstamos generales aportan la
   tasa de capitalización —media ponderada de sus costos por intereses— aplicada a los desembolsos del
   activo financiados con ellos (NIC 23.14). Lo capitalizado en el período no excede el total de costos
   por préstamos incurridos (tope del párrafo 14). Sin el anexo se mantiene la estimación por desembolso
   con la tasa de capitalización del parámetro y se avisa. En PYMES todo costo por préstamos es gasto
   (Sección 25.2, ediciones 2015 y 2025): no se capitaliza nada y lo capitalizado es ajuste.
8. Desmantelamiento: provisión = costo estimado ÷ (1 + tasa)^años (NIC 16.16 c, NIC 37.45–47; PYMES 17.10 c
   y 21.7 b). El ajuste se separa en dos efectos (CINIIF 1): la actualización financiera del período (saldo
   inicial de la provisión × tasa) es costo financiero de resultados (1.8; NIC 37.60; PYMES 21.11) y el
   cambio de estimación va contra el costo del activo (1.5 a).
9. Conciliación auxiliar-mayor del costo y de la depreciación acumulada (roll-forward).
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja,
    m, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "ppe_propiedad_planta 1.0"
RUBRO = "ACTIVOS_FIJOS"

_ACTIVOS = [
    campo("id", "Código del activo", alias=("codigo", "código", "activo", "codigo activo", "placa"), ejemplo="VEH-01"),
    campo("descripcion", "Descripción", alias=("detalle", "nombre", "descripcion del activo"), ejemplo="Camioneta 4x4"),
    campo("clase", "Clase", alias=("grupo", "tipo de activo", "cuenta", "categoria"), ejemplo="Vehículos"),
    campo("elemento", "Elemento al que pertenece (componente)", requerido=False, alias=("componente de", "elemento principal", "activo padre"), ejemplo=""),
    campo("fecha_uso", "Fecha disponible para uso", "date", requerido=False, alias=("fecha de uso", "fecha de activacion", "fecha inicio depreciacion", "fecha de compra"), ejemplo="2023-07-01"),
    campo("costo_inicial", "Costo al inicio del año", "number", alias=("costo inicial", "saldo inicial costo", "costo historico"), ejemplo="40000"),
    campo("adiciones", "Adiciones del año", "number", requerido=False, alias=("altas", "adiciones", "compras del año"), ejemplo="0"),
    campo("residual", "Valor residual", "number", requerido=False, alias=("valor residual", "residual", "valor de salvamento"), ejemplo="4000"),
    campo("vida_meses", "Vida útil (meses)", "number", requerido=False, alias=("vida util", "vida util meses", "meses de vida"), ejemplo="60"),
    campo("metodo", "Método de depreciación", requerido=False, alias=("metodo", "método"), ejemplo="Lineal"),
    campo("dep_acum_inicial", "Depreciación acumulada inicial", "number", requerido=False, alias=("dep acumulada inicial", "depreciacion acumulada inicial"), ejemplo="10800"),
    campo("dep_registrada", "Depreciación del año registrada", "number", requerido=False, alias=("depreciacion del año", "gasto depreciacion"), ejemplo="6000"),
    campo("deterioro_acum", "Deterioro acumulado", "number", requerido=False, alias=("deterioro", "perdida por deterioro acumulada"), ejemplo="0"),
    campo("importe_recuperable", "Importe recuperable", "number", requerido=False, alias=("valor recuperable", "recuperable"), ejemplo=""),
    campo("valor_revaluado", "Valor revaluado al corte", "number", requerido=False, alias=("valor razonable", "avaluo", "valor de tasacion"), ejemplo=""),
    campo("superavit_previo", "Superávit de revaluación previo", "number", requerido=False, alias=("superavit", "reserva de revaluacion"), ejemplo=""),
    campo("decremento_previo", "Decremento previo del mismo activo reconocido en resultados", "number", requerido=False,
          alias=("decremento previo", "perdida por revaluacion previa", "disminucion previa en resultados"), ejemplo=""),
    campo("fecha_baja", "Fecha de baja", "date", requerido=False, alias=("baja", "fecha venta", "fecha de retiro"), ejemplo=""),
    campo("producto_baja", "Producto de la baja", "number", requerido=False, alias=("precio de venta", "producto", "valor de venta"), ejemplo=""),
    campo("resultado_baja", "Ganancia (pérdida) registrada en la baja", "number", requerido=False, alias=("utilidad en venta", "resultado venta"), ejemplo=""),
]
_ADICIONES = [
    campo("id", "N° de documento", alias=("documento", "factura", "comprobante"), ejemplo="AD-01"),
    campo("activo", "Código del activo", alias=("codigo", "activo"), ejemplo="OBRA-01"),
    campo("fecha", "Fecha del desembolso", "date", alias=("fecha", "fecha factura"), ejemplo="2025-03-01"),
    campo("descripcion", "Descripción", requerido=False, alias=("detalle", "concepto"), ejemplo="Avance de obra"),
    campo("tipo", "Tipo (capitalizable / reparación / mantenimiento)", requerido=False, alias=("tipo", "naturaleza"), ejemplo="Capitalizable"),
    campo("importe", "Importe", "number", alias=("valor", "monto", "importe"), ejemplo="150000"),
    campo("apto", "Activo apto (Sí/No)", requerido=False, alias=("activo apto", "apto"), ejemplo="Sí"),
    campo("intereses", "Intereses capitalizados registrados", "number", requerido=False, alias=("intereses capitalizados", "intereses"), ejemplo="9000"),
]
_PRESTAMOS = [
    campo("id", "N° de préstamo o contrato", alias=("prestamo", "préstamo", "contrato", "credito", "crédito", "documento"), ejemplo="PR-01"),
    campo("tipo", "Tipo (Específico / General)", requerido=False, alias=("tipo", "tipo de prestamo", "naturaleza", "clase de prestamo"), ejemplo="Específico"),
    campo("activo", "Activo u obra financiada (solo los específicos)", requerido=False,
          alias=("activo", "obra", "codigo activo", "activo apto", "destino"), ejemplo="OBRA-01"),
    campo("descripcion", "Descripción", requerido=False, alias=("detalle", "banco", "entidad", "concepto"), ejemplo="Banco X · nave industrial"),
    campo("importe", "Importe del préstamo vigente en el período", "number", requerido=False,
          alias=("capital", "principal", "monto", "saldo del prestamo"), ejemplo="120000"),
    campo("tasa", "Tasa nominal anual (%)", "number", requerido=False, alias=("tasa", "tasa anual", "interes"), ejemplo="9"),
    campo("costo_financiero", "Costo financiero del período realmente incurrido", "number", requerido=False,
          alias=("costo financiero", "intereses del periodo", "intereses devengados", "gasto financiero"), ejemplo="9000"),
    campo("rendimientos", "Rendimientos de la inversión temporal de esos fondos (solo los específicos)", "number", requerido=False,
          alias=("rendimientos", "rendimiento inversion temporal", "intereses ganados", "rendimientos financieros"), ejemplo="1200"),
]
CAMPOS = {"activos": _ACTIVOS, "adiciones": _ADICIONES, "prestamos": _PRESTAMOS}
TIPOS = {"activos": "activos", "adiciones": "adiciones", "prestamos": "prestamos"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "activos"
CONTROL = "costo_inicial"
TOTAL_EJEMPLO = "ajusteResultado"

# Dashboard (formato en graficos.py): la población es el costo de los activos del auxiliar; la cifra
# que el auditor recalcula frente a la registrada es la depreciación del año, comparada solo en los activos
# que se pudieron recalcular (un método no lineal queda sin recálculo), así la brecha es el ajuste de depreciación.
PANEL = {
    "poblacion":    {"rotulo": "Costo de activos evaluados", "hoja": "04_Depreciacion", "col": "Costo"},
    "recalculado":  {"rotulo": "Depreciación recalculada", "total": "depRecalculada"},
    "registrado":   {"rotulo": "Depreciación registrada (activos recalculados)", "hoja": "04_Depreciacion",
                     "col": "Depreciación registrada", "con_valor": "Depreciación recalculada"},
    "composicion":  {"rotulo": "Depreciación por activo", "hoja": "04_Depreciacion", "etiqueta": "Código",
                     "valor": "Depreciación recalculada"},
    "distribucion": {"rotulo": "Costo por clase de activo", "hoja": "05_Vidas_residual", "etiqueta": "Clase", "valor": "Costo"},
}

PARAMETROS = {
    "tolerancia": 1, "tasaCapitalizacion": None, "umbralComponente": 10, "umbralRevisarComponentes": None,
    "costoDesmantelamiento": None, "aniosDesmantelamiento": None, "tasaDesmantelamiento": None,
    "provisionDesmantelamiento": None, "provisionDesmantelamientoInicial": None, "mayorCosto": None, "mayorDepAcum": None,
}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "tolerancia": "Tolerancia por activo (importe)", "tasaCapitalizacion": "Tasa de capitalización de intereses (% anual)",
    "umbralComponente": "Parte significativa desde (% del costo del elemento)",
    "umbralRevisarComponentes": "Revisar componentes de elementos con costo desde",
    "costoDesmantelamiento": "Desmantelamiento: costo estimado futuro", "aniosDesmantelamiento": "Desmantelamiento: años hasta el desembolso",
    "tasaDesmantelamiento": "Desmantelamiento: tasa de descuento antes de impuestos (%)",
    "provisionDesmantelamiento": "Provisión de desmantelamiento registrada (cierre)",
    "provisionDesmantelamientoInicial": "Provisión de desmantelamiento registrada al inicio del ejercicio",
    "mayorCosto": "Mayor: costo al cierre", "mayorDepAcum": "Mayor: depreciación acumulada al cierre",
}


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    v = validar_campos(CAMPOS[tipo], filas)
    if tipo == "activos":
        for f in filas:
            vida = a_num(f.get("vida_meses")) if str(f.get("vida_meses", "") or "").strip() else None
            if vida is not None and vida <= 0:
                v["errors"].append({"row": f.get("_row"), "field": "vida_meses", "message": "Vida útil: use meses mayores que cero (en blanco si no se deprecia, p. ej. terrenos)."})
        v["ok"] = not v["errors"]
    return v


# --- cálculo -----------------------------------------------------------------

def _t(v) -> str:
    return str(v if v is not None else "").strip()


def _opc(v):
    """Número opcional: None si la celda viene vacía."""
    return a_num(v) if _t(v) else None


def _hace_un_anio(d):
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year - 1, day=28)


def _lineal(metodo: str) -> bool:
    return metodo == "" or "lineal" in metodo.lower()


def _tot(filas, k):
    """Total de una columna de la cédula de capitalización: vacío si algún activo quedó sin medir (M22)."""
    return None if any(f[k] is None for f in filas) else sum(f[k] for f in filas)


def _p(p, k):
    v = p.get(k)
    return None if v is None or _t(v) == "" else float(a_num(v))


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    # EDATE(corte;-12)+1: primer día del ejercicio.
    from datetime import timedelta
    inicio = _hace_un_anio(corte_a) + timedelta(days=1)
    dias_anio = (corte_a - inicio).days + 1
    pymes = es_pymes(p)
    tol = _p(p, "tolerancia") or 0.0
    tasa_cap = _p(p, "tasaCapitalizacion")

    activos = []
    for f in datasets.get("activos") or []:
        if not _t(f.get("id")):
            continue
        vida = _opc(f.get("vida_meses"))
        if vida is not None and vida <= 0:
            raise ValueError(f"Activo {_t(f.get('id'))}: la vida útil debe ser mayor que cero.")
        a = {"id": _t(f.get("id")), "desc": _t(f.get("descripcion")), "clase": _t(f.get("clase")), "elemento": _t(f.get("elemento")),
             "uso": fecha(f.get("fecha_uso")) if _t(f.get("fecha_uso")) else None, "ci": _opc(f.get("costo_inicial")) or 0.0,
             "ad": _opc(f.get("adiciones")), "res": _opc(f.get("residual")), "vida": vida, "metodo": _t(f.get("metodo")),
             "dai": _opc(f.get("dep_acum_inicial")), "dreg": _opc(f.get("dep_registrada")), "det": _opc(f.get("deterioro_acum")),
             "rec": _opc(f.get("importe_recuperable")), "rev": _opc(f.get("valor_revaluado")), "sup": _opc(f.get("superavit_previo")),
             "decPrev": _opc(f.get("decremento_previo")),
             "baja": fecha(f.get("fecha_baja")) if _t(f.get("fecha_baja")) else None, "prod": _opc(f.get("producto_baja")),
             "resreg": _opc(f.get("resultado_baja")), "_row": f.get("_row")}
        if a["baja"] and not inicio <= a["baja"] <= corte_a:
            raise ValueError(f"Activo {a['id']}: la fecha de baja debe estar dentro del ejercicio ({inicio.isoformat()} a {corte_a.isoformat()}).")
        activos.append(a)
    if not activos:
        raise ValueError("Cargue el auxiliar de propiedad, planta y equipo por activo.")

    # 2–3 · depreciación y valor neto en libros (misma aritmética que el Excel).
    for a in activos:
        a["costo"] = a["ci"] + (a["ad"] or 0)
        a["depr"] = max(a["costo"] - (a["res"] or 0), 0)
        if a["uso"] is None:
            a["dias"] = 0
        else:
            hasta = min(a["baja"], corte_a) if a["baja"] else corte_a
            a["dias"] = max((hasta - max(a["uso"], inicio)).days + 1, 0)
        if not _lineal(a["metodo"]):
            a["dep"] = None
        elif a["vida"] is None or a["dias"] == 0:
            a["dep"] = 0.0
        else:
            a["dep"] = min(a["depr"] / a["vida"] * 12 * a["dias"] / dias_anio, max(a["depr"] - (a["dai"] or 0), 0))
        a["dif"] = None if a["dep"] is None or a["dreg"] is None else a["dep"] - a["dreg"]
        a["acum"] = None if a["dep"] is None else (a["dai"] or 0) + a["dep"]
        a["nbv"] = None if a["acum"] is None else a["costo"] - a["acum"] - (a["det"] or 0)
        a["total_dep"] = None if a["acum"] is None else ("Sí" if a["depr"] > 0 and a["acum"] >= a["depr"] - 0.005 else "No")
        a["estado"] = "Baja" if a["baja"] else ("En construcción" if a["uso"] is None else "En uso")
        a["remanente"] = None if a["vida"] is None or a["acum"] is None or a["depr"] == 0 else max(a["depr"] - a["acum"], 0) / a["depr"] * a["vida"]
        a["resid_pct"] = None if a["costo"] == 0 else (a["res"] or 0) / a["costo"]
    vivos = [a for a in activos if a["estado"] != "Baja"]

    # Componentes: elementos con más de una fila.
    grupo = lambda a: a["elemento"] or a["id"]
    conteo = {}
    for a in activos:
        conteo[grupo(a)] = conteo.get(grupo(a), 0) + 1
    comp = [a for a in activos if conteo[grupo(a)] > 1]
    umbral = _p(p, "umbralComponente") or 0.0
    for a in comp:
        tot = sum(x["costo"] for x in comp if grupo(x) == grupo(a))
        a["costo_elem"] = tot
        a["part"] = None if tot == 0 else a["costo"] / tot
        a["signif"] = "" if a["part"] is None else ("Sí" if a["part"] >= umbral / 100 else "No")

    # 4 · bajas.
    bajas = [a for a in activos if a["baja"]]
    for a in bajas:
        a["nbv_baja"] = None if a["acum"] is None else a["costo"] - a["acum"] - (a["det"] or 0)
        a["res_calc"] = None if a["nbv_baja"] is None else (a["prod"] or 0) - a["nbv_baja"]
        a["res_dif"] = None if a["res_calc"] is None or a["resreg"] is None else a["res_calc"] - a["resreg"]

    # 5 · revaluación al corte. NIC 16.39 (2.ª frase) y PYMES 17.15C: el aumento va a resultados hasta revertir un
    # decremento anterior del mismo activo reconocido en resultados; sin ese dato, todo queda en ORI y se avisa.
    reval = [a for a in vivos if a["rev"] is not None and a["nbv"] is not None]
    for a in reval:
        d = a["rev"] - a["nbv"]
        s = a["sup"] or 0
        a["rev_dif"] = d
        if d >= 0:
            a["rev_res"] = 0.0 if a["decPrev"] is None else min(d, a["decPrev"])
            a["rev_ori"] = d - a["rev_res"]
        else:
            a["rev_ori"] = -min(-d, s)
            a["rev_res"] = d + min(-d, s)

    # 6 · deterioro. NIC 36.60-61 y PYMES 27.6: en un activo revaluado la pérdida es un decremento de revaluación:
    # primero contra el superávit remanente de ese activo (ORI) y solo el exceso a resultados.
    deter = [a for a in vivos if a["rec"] is not None]
    for a in deter:
        a["libros"] = a["rev"] if a["rev"] is not None else a["nbv"]
        a["perdida"] = None if a["libros"] is None else max(a["libros"] - a["rec"], 0)
        a["supPrev"] = a["sup"] or 0.0
        a["revOri"] = a["rev_ori"] if "rev_ori" in a else 0.0
        a["supRem"] = max(a["supPrev"] + a["revOri"], 0)
        revaluado = a["rev"] is not None or a["sup"] is not None
        if a["perdida"] is None:
            a["detORI"], a["detRes"] = None, None
        elif not revaluado:
            a["detORI"], a["detRes"] = 0.0, a["perdida"]
        elif a["sup"] is None:                       # revaluado sin dato de superávit: no se reparte (M22)
            a["detORI"], a["detRes"] = None, a["perdida"]
        else:
            a["detORI"] = min(a["perdida"], a["supRem"])
            a["detRes"] = a["perdida"] - a["detORI"]

    # 7 · adiciones y costos por préstamos.
    por_id = {a["id"]: a for a in activos}
    adiciones = []
    for f in datasets.get("adiciones") or []:
        if not _t(f.get("id")) and not _t(f.get("activo")):
            continue
        x = {"id": _t(f.get("id")), "activo": _t(f.get("activo")), "fecha": fecha(f.get("fecha")), "desc": _t(f.get("descripcion")),
             "tipo": _t(f.get("tipo")), "importe": _opc(f.get("importe")) or 0.0, "apto": _t(f.get("apto")),
             "int": _opc(f.get("intereses")), "_row": f.get("_row")}
        if x["fecha"] is None:
            raise ValueError(f"Adición {x['id']}: indique la fecha del desembolso.")
        act = por_id.get(x["activo"])
        fin = corte_a if act is None or act["uso"] is None else min(act["uso"], corte_a)
        es_apto = x["apto"].lower() in ("sí", "si")
        x["dias"] = 0 if pymes or not es_apto else max((fin - max(x["fecha"], inicio)).days, 0)
        x["cap"] = 0.0 if x["dias"] == 0 else (None if tasa_cap is None else x["importe"] * tasa_cap / 100 * x["dias"] / dias_anio)
        x["int_dif"] = None if x["cap"] is None else x["cap"] - (x["int"] or 0)
        low = x["tipo"].lower()
        x["capitalizable"] = "No: gasto (NIC 16.12)" if ("repar" in low or "manten" in low) else "Sí"
        x["existe"] = act is not None
        adiciones.append(x)

    # 7 bis · anexo de préstamos para la construcción (NIC 23.12 y 14).
    prestamos = []
    for f in datasets.get("prestamos") or []:
        if not _t(f.get("id")):
            continue
        tp = _t(f.get("tipo")).lower()
        y = {"id": _t(f.get("id")), "tipo": "Específico" if tp.startswith("esp") else ("General" if tp.startswith("gen") else ""),
             "activo": _t(f.get("activo")), "desc": _t(f.get("descripcion")), "importe": _opc(f.get("importe")),
             "tasa": _opc(f.get("tasa")), "costo": _opc(f.get("costo_financiero")), "rend": _opc(f.get("rendimientos")),
             "_row": f.get("_row")}
        # NIC 23.12: en el específico lo capitalizable es el costo realmente asumido menos los rendimientos de la
        # inversión temporal de esos fondos. Sin uno de los dos datos el importe queda vacío (M22).
        y["cap_esp"] = None if y["tipo"] != "Específico" or y["costo"] is None or y["rend"] is None else y["costo"] - y["rend"]
        prestamos.append(y)

    # NIC 23.14: tasa de capitalización = media ponderada de los costos por intereses de los préstamos genéricos.
    generales = [y for y in prestamos if y["tipo"] == "General"]
    if not generales:
        tasa_gen = 0.0
    elif any(y["importe"] is None or y["costo"] is None for y in generales) or sum(y["importe"] or 0 for y in generales) == 0:
        tasa_gen = None
    else:
        tasa_gen = sum(y["costo"] for y in generales) / sum(y["importe"] for y in generales)

    esp_por_activo = {}
    for y in prestamos:
        if y["tipo"] == "Específico" and y["activo"]:
            esp_por_activo.setdefault(y["activo"], []).append(y)
    capit = []
    if prestamos:
        orden = []
        for x in adiciones:
            if (x["dias"] > 0 or (x["int"] or 0) != 0) and x["activo"] not in orden:
                orden.append(x["activo"])
        for k in esp_por_activo:
            if k not in orden:
                orden.append(k)
        for k in orden:
            ads = [x for x in adiciones if x["activo"] == k]
            esps = esp_por_activo.get(k, [])
            des = sum(x["importe"] for x in ads if x["dias"] > 0)
            base = sum(x["importe"] * x["dias"] for x in ads) / dias_anio
            imp = None if any(y["importe"] is None for y in esps) else sum(y["importe"] for y in esps)
            cap_e = 0.0 if pymes else (None if any(y["cap_esp"] is None for y in esps) else sum(y["cap_esp"] for y in esps))
            pct = None if imp is None else (0.0 if des == 0 else max(1 - imp / des, 0))
            bg = None if pct is None else base * pct
            cg = 0.0 if pymes else (None if bg is None or tasa_gen is None else bg * tasa_gen)
            capit.append({"activo": k, "desemb": des, "base": base, "esp_imp": imp, "esp_cap": cap_e, "pct": pct,
                          "base_gen": bg, "tasa": 0.0 if pymes else tasa_gen, "cap_gen": cg,
                          "antes": None if cap_e is None or cg is None else cap_e + cg,
                          "reg": sum(x["int"] or 0 for x in ads)})
    # Tope del párrafo 14: lo capitalizado en el período no excede los costos por préstamos incurridos.
    tope_inc = sum(y["costo"] for y in prestamos if y["costo"] is not None)
    tope_antes = sum(a["antes"] for a in capit if a["antes"] is not None)
    tope_completo = bool(prestamos) and all(y["costo"] is not None for y in prestamos) and all(a["antes"] is not None for a in capit)
    factor = None if not tope_completo else (1.0 if tope_antes <= tope_inc else tope_inc / tope_antes)
    for a in capit:
        a["factor"] = factor
        a["final"] = None if a["antes"] is None else (a["antes"] if factor is None else a["antes"] * factor)
        a["dif"] = None if a["final"] is None else a["final"] - a["reg"]
    if prestamos:                    # con anexo el capitalizable se mide por activo, no por desembolso
        for x in adiciones:
            x["cap"], x["int_dif"] = None, None

    # 8 · desmantelamiento.
    # CINIIF 1.5 a / 1.8 (PYMES 21.7 b y 21.11): el cambio de estimación va contra el costo del activo; la reversión
    # del descuento del período (saldo inicial de la provisión × tasa) es costo financiero del ejercicio.
    cd, an, td = _p(p, "costoDesmantelamiento"), _p(p, "aniosDesmantelamiento"), _p(p, "tasaDesmantelamiento")
    prov_reg = _p(p, "provisionDesmantelamiento")
    prov_ini = _p(p, "provisionDesmantelamientoInicial")
    if prov_ini is None and prov_reg is None:
        prov_ini = 0.0                               # sin provisión registrada al cierre no hay saldo inicial que actualizar
    vp = None if cd is None or an is None or td is None else cd / (1 + td / 100) ** an
    act = None if vp is None or prov_ini is None or td is None else prov_ini * td / 100
    dif = None if vp is None else vp - (prov_reg or 0)
    desm = {"costo": cd, "anios": an, "tasa": td, "vp": vp, "registrada": prov_reg, "inicial": prov_ini, "dif": dif,
            "actualizacion": act, "cambio": None if dif is None or act is None else dif - act}

    # 9 · roll-forward y conciliación con el mayor (datos registrados).
    s = lambda it, k: sum(x[k] or 0 for x in it)
    rf = {"ci": s(activos, "ci"), "ad": s(activos, "ad"), "costoBajas": s(bajas, "costo")}
    rf["costoFinal"] = rf["ci"] + rf["ad"] - rf["costoBajas"]
    rf["mayorCosto"] = _p(p, "mayorCosto")
    rf["difCosto"] = None if rf["mayorCosto"] is None else rf["costoFinal"] - rf["mayorCosto"]
    rf["dai"] = s(activos, "dai")
    rf["dreg"] = s(activos, "dreg")
    rf["depBajas"] = s(bajas, "dai") + s(bajas, "dreg")
    rf["depFinalReg"] = rf["dai"] + rf["dreg"] - rf["depBajas"]
    rf["mayorDep"] = _p(p, "mayorDepAcum")
    rf["difDep"] = None if rf["mayorDep"] is None else rf["depFinalReg"] - rf["mayorDep"]
    rf["depFinalCalc"] = sum(a["acum"] for a in vivos if a["acum"] is not None)
    rf["nbv"] = sum(a["nbv"] for a in vivos if a["nbv"] is not None)
    rf["costoVivos"] = sum(a["costo"] for a in vivos)
    rf["adDetalle"] = sum(x["importe"] for x in adiciones) if adiciones else None
    rf["difAd"] = None if rf["adDetalle"] is None else rf["ad"] - rf["adDetalle"]

    aj = {"ajusteDep": sum(a["dif"] for a in activos if a["dif"] is not None),
          "deterioroAdicional": sum(a["perdida"] for a in deter if a["perdida"] is not None),
          "deterioroORI": sum(a["detORI"] for a in deter if a["detORI"] is not None),
          "deterioroResultado": sum(a["detRes"] for a in deter if a["detRes"] is not None),
          "ajusteBajas": sum(a["res_dif"] for a in bajas if a["res_dif"] is not None),
          "ajusteIntereses": (sum(a["dif"] for a in capit if a["dif"] is not None) if prestamos
                             else sum(x["int_dif"] for x in adiciones if x["int_dif"] is not None)),
          "revaluacionORI": sum(a["rev_ori"] for a in reval), "revaluacionResultado": sum(a["rev_res"] for a in reval),
          "ajusteDesmantelamiento": desm["cambio"], "desmantelamientoFinanciero": desm["actualizacion"]}
    aj["ajusteResultado"] = (-aj["ajusteDep"] - aj["deterioroResultado"] + aj["ajusteBajas"] + aj["ajusteIntereses"]
                             + aj["revaluacionResultado"] - (desm["actualizacion"] or 0))

    # Problemas.
    pr = []
    for a in activos:
        if a["dep"] is None:
            pr.append(problema("METODO_NO_RECALCULADO", f"{a['id']}: método «{a['metodo']}» no se recalcula; pida el cálculo del cliente y evalúe el patrón de consumo (NIC 16.60–62).", 0))
        if a["dif"] is not None and abs(a["dif"]) > tol:
            pr.append(problema("DEPRECIACION_DIFERENTE", f"{a['id']}: depreciación recalculada {m(a['dep'])} ≠ registrada {m(a['dreg'])} (NIC 16.50; PYMES 17.18).", a["dif"]))
        if a["estado"] == "En construcción" and (a["dreg"] or 0) > 0:
            pr.append(problema("DEPRECIACION_EN_CONSTRUCCION", f"{a['id']}: se registró depreciación de un activo que aún no está disponible para su uso (NIC 16.55; PYMES 17.20).", a["dreg"]))
        if a["total_dep"] == "Sí" and a["estado"] == "En uso":
            pr.append(problema("TOTALMENTE_DEPRECIADO_EN_USO", f"{a['id']}: totalmente depreciado y aún en uso; revise la vida útil y el residual (NIC 16.51; PYMES 17.19).", a["costo"]))
        if (a["res"] or 0) > a["costo"]:
            pr.append(problema("RESIDUAL_EXCEDE_COSTO", f"{a['id']}: el valor residual iguala o supera el importe en libros: la depreciación es nula (NIC 16.54); verifique el soporte de la estimación (NIC 16.51; NIA 540).", (a["res"] or 0) - a["costo"]))
    umbral_rev = _p(p, "umbralRevisarComponentes")
    if umbral_rev is not None:
        for a in vivos:
            if conteo[grupo(a)] == 1 and a["costo"] >= umbral_rev and a["vida"] is not None:
                pr.append(problema("REVISAR_COMPONENTES", f"{a['id']}: elemento de costo {m(a['costo'])} sin partes; confirme que no tiene partes significativas con vida distinta (NIC 16.43–44; PYMES 17.16).", 0))
    for a in bajas:
        if a["res_dif"] is not None and abs(a["res_dif"]) > tol:
            pr.append(problema("BAJA_MAL_CALCULADA", f"{a['id']}: resultado de la baja recalculado {m(a['res_calc'])} ≠ registrado {m(a['resreg'])} (NIC 16.71; PYMES 17.30).", a["res_dif"]))
        elif a["res_calc"] is not None and a["resreg"] is None:
            pr.append(problema("BAJA_SIN_RESULTADO", f"{a['id']}: baja sin ganancia o pérdida registrada; la recalculada es {m(a['res_calc'])}.", a["res_calc"]))
    clases_rev = {a["clase"] for a in vivos if a["rev"] is not None}
    for c in sorted(clases_rev):
        faltan = [a["id"] for a in vivos if a["clase"] == c and a["rev"] is None]
        if faltan:
            pr.append(problema("REVALUACION_CLASE_INCOMPLETA", f"Clase {c}: se revaluó una parte; también deben revaluarse {', '.join(faltan)} (NIC 16.36; PYMES 17.15 y 17.15B).", 0))
    for a in deter:
        if a["perdida"]:
            reparto = ("" if a["detORI"] in (None, 0) else
                       f" Activo revaluado: {m(a['detORI'])} contra el superávit de revaluación y {m(a['detRes'])} a resultados (NIC 36.60-61; PYMES 27.6).")
            pr.append(problema("DETERIORO", f"{a['id']}: importe en libros {m(a['libros'])} mayor que el importe recuperable {m(a['rec'])} (NIC 36.59; PYMES 27.5).{reparto}", a["perdida"]))
    sin_sup = [a["id"] for a in deter if a["perdida"] and a["detORI"] is None]
    if sin_sup:
        pr.append(problema("DETERIORO_SIN_SUPERAVIT", f"Activos revaluados con deterioro y sin superávit de revaluación previo informado: {', '.join(sin_sup)}. "
                           "La pérdida debe imputarse primero contra el superávit de ese activo y solo el exceso a resultados (NIC 36.60-61; PYMES 27.6): "
                           "indique el superávit previo; mientras tanto la pérdida queda íntegra en resultados.",
                           sum(a["perdida"] for a in deter if a["perdida"] and a["detORI"] is None)))
    sin_dec = [a["id"] for a in reval if a["decPrev"] is None]
    if sin_dec:
        pr.append(problema("REVALUACION_SIN_DECREMENTO_PREVIO", f"Activos revaluados sin el dato «decremento previo del mismo activo reconocido en resultados»: "
                           f"{', '.join(sin_dec)}. El aumento por revaluación va a resultados hasta revertir ese decremento anterior (NIC 16.39; PYMES 17.15C): "
                           "indique el importe; mientras tanto el aumento queda íntegro en otro resultado integral.",
                           sum(a["rev_ori"] for a in reval if a["decPrev"] is None and a["rev_dif"] > 0)))
    if pymes:
        cap_pymes = sum(x["int"] or 0 for x in adiciones)
        if cap_pymes > 0.005:
            pr.append(problema("INTERESES_CAPITALIZADOS_PYMES", f"En NIIF para las PYMES los costos por préstamos son gasto (Sección 25.2): se capitalizaron {m(cap_pymes)}.", -cap_pymes))
        if prestamos:
            pr.append(problema("PRESTAMOS_NO_SE_CAPITALIZAN_PYMES", "Se cargó el anexo de préstamos para la construcción, pero en NIIF para las PYMES todos los costos por "
                               "préstamos se reconocen como gasto del período (Sección 25.2, igual en las ediciones 2015 y 2025): no hay tasa de capitalización ni "
                               "préstamo específico que capitalizar. El anexo sirve para identificar el costo financiero del período y su presentación en resultados."))
    else:
        if not prestamos:
            if tasa_cap is None and any(x["apto"].lower() in ("sí", "si") for x in adiciones):
                pr.append(problema("TASA_CAPITALIZACION_FALTANTE", "Hay adiciones de activos aptos: ingrese la tasa de capitalización (NIC 23.14).", 0))
            if any(a["estado"] == "En construcción" for a in activos) or any(x["apto"].lower() in ("sí", "si") for x in adiciones):
                pr.append(problema("SIN_ANEXO_PRESTAMOS", "Hay activos en construcción o adiciones de activos aptos y no se cargó el anexo de préstamos para la "
                                   "construcción: no se puede separar el préstamo específico —costo financiero realmente incurrido menos los rendimientos de la inversión "
                                   "temporal de esos fondos (NIC 23.12)— de los préstamos generales —tasa de capitalización (NIC 23.14)— ni comprobar el tope de los "
                                   "costos por préstamos incurridos en el período (NIC 23.14). Pida los contratos y la tabla de amortización de cada préstamo; mientras "
                                   "tanto se aplica la tasa de capitalización del parámetro a cada desembolso.", 0))
            for x in adiciones:
                if x["int_dif"] is not None and abs(x["int_dif"]) > tol:
                    pr.append(problema("INTERESES_DIFERENCIA", f"{x['id']}: intereses capitalizables {m(x['cap'])} ≠ capitalizados {m(x['int'] or 0)} (NIC 23.8, 14).", x["int_dif"]))
        else:
            if tasa_cap is not None and tasa_gen is not None and abs(tasa_gen * 100 - tasa_cap) > 0.005:
                pr.append(problema("TASA_CAPITALIZACION_DIFIERE", f"La tasa de capitalización del parámetro ({tasa_cap:.4f} %) no coincide con la media ponderada de los "
                                   f"préstamos generales del anexo ({tasa_gen * 100:.4f} %): se usa la del anexo (NIC 23.14).", 0))
            if factor is None:
                pr.append(problema("TOPE_NO_VERIFICABLE", "No se puede comprobar el tope del párrafo 14 (lo capitalizado no excede los costos por préstamos incurridos en "
                                   "el período): falta el costo financiero de algún préstamo o el capitalizable de algún activo. Complete el anexo de préstamos.", 0))
            elif factor < 1:
                pr.append(problema("TOPE_COSTOS_PRESTAMOS", f"El capitalizable calculado {m(tope_antes)} excede los costos por préstamos incurridos en el período "
                                   f"{m(tope_inc)}: se limita a estos últimos (NIC 23.14). Exceso que no se capitaliza: {m(tope_antes - tope_inc)}.", tope_antes - tope_inc))
            for a in capit:
                if a["dif"] is not None and abs(a["dif"]) > tol:
                    pr.append(problema("INTERESES_DIFERENCIA", f"{a['activo']}: costos por préstamos capitalizables {m(a['final'])} ≠ capitalizados {m(a['reg'])} "
                                       "(NIC 23.12 el específico, 23.14 los generales y el tope).", a["dif"]))
    for y in prestamos:
        if not y["tipo"]:
            pr.append(problema("PRESTAMO_SIN_TIPO", f"{y['id']}: indique si el préstamo es específico (NIC 23.12) o general (NIC 23.14); sin el tipo no entra en el cálculo.", 0))
        if y["costo"] is None:
            pr.append(problema("PRESTAMO_SIN_COSTO_FINANCIERO", f"{y['id']}: falta el costo financiero del período realmente incurrido; sin él no se mide el capitalizable "
                               "ni el tope del párrafo 14 (NIC 23.12 y 14). Revise la tabla de amortización del préstamo y el mayor de gasto financiero.", 0))
        if y["tipo"] == "Específico":
            if y["rend"] is None:
                pr.append(problema("PRESTAMO_SIN_RENDIMIENTOS", f"{y['id']}: préstamo específico sin el dato de rendimientos de la inversión temporal de esos fondos; lo "
                                   "capitalizable es el costo realmente incurrido menos esos rendimientos (NIC 23.12). Si no hubo inversión temporal, informe 0: no se asume.", 0))
            if not y["activo"]:
                pr.append(problema("PRESTAMO_SIN_ACTIVO", f"{y['id']}: préstamo específico sin el activo u obra financiada; indíquelo para asignarle el costo capitalizable (NIC 23.12).", 0))
            elif y["activo"] not in por_id:
                pr.append(problema("PRESTAMO_ACTIVO_NO_EXISTE", f"{y['id']}: el activo {y['activo']} que financia no está en el auxiliar.", 0))
        if y["tipo"] == "General" and (y["importe"] is None or y["costo"] is None):
            pr.append(problema("PRESTAMO_GENERAL_INCOMPLETO", f"{y['id']}: préstamo general sin importe o sin costo financiero del período; sin ambos no se calcula la tasa "
                               "de capitalización, que es la media ponderada de los costos de todos los préstamos genéricos (NIC 23.14).", 0))
    for x in adiciones:
        if x["capitalizable"] != "Sí":
            pr.append(problema("ADICION_GASTO_CAPITALIZADO", f"{x['id']}: «{x['tipo']}» capitalizado; las reparaciones y el mantenimiento son gasto (NIC 16.12; PYMES 17.15); el mantenimiento mayor o las inspecciones generales pueden capitalizarse (NIC 16.13–14).", x["importe"]))
        if not x["existe"]:
            pr.append(problema("ADICION_SIN_ACTIVO", f"{x['id']}: el activo {x['activo']} no está en el auxiliar.", x["importe"]))
    if rf["difAd"] is not None and abs(rf["difAd"]) > tol:
        pr.append(problema("ADICIONES_NO_CONCILIAN", f"Adiciones del auxiliar {m(rf['ad'])} ≠ detalle de adiciones {m(rf['adDetalle'])}.", rf["difAd"]))
    if vp is None:
        pr.append(problema("DESMANTELAMIENTO_NO_EVALUADO", "No se ingresó la estimación de desmantelamiento: documente si existe la obligación (NIC 16.16 c, NIC 37; PYMES 17.10 c, Sección 21).", 0))
    elif vp > 0.005 and not prov_reg:
        pr.append(problema("DESMANTELAMIENTO_NO_RECONOCIDO", f"Obligación de desmantelamiento no reconocida: valor presente {m(vp)} (NIC 16.16 c, NIC 37.45; Sección 21 (21.7 b)).", vp))
    elif abs(desm["dif"]) > tol:
        pr.append(problema("DESMANTELAMIENTO_DIFERENCIA", f"Provisión de desmantelamiento registrada {m(prov_reg)} ≠ valor presente {m(vp)}: diferencia {m(desm['dif'])}"
                           + ("." if act is None else f", de la que {m(act)} es la actualización financiera del período (a resultados, costo financiero: CINIIF 1.8; "
                              f"NIC 37.60; PYMES 21.11) y {m(desm['cambio'])} el cambio de estimación contra el costo del activo (CINIIF 1.5 a)."), desm["dif"]))
    if vp is not None and prov_ini is None:
        pr.append(problema("SIN_PROVISION_DESMANTELAMIENTO_INICIAL", "Hay provisión de desmantelamiento registrada pero no se informó su saldo al inicio del "
                           "ejercicio: no se puede separar la actualización financiera del período (saldo inicial × tasa, a resultados: CINIIF 1.8; PYMES 21.11) "
                           "del cambio de estimación (contra el costo del activo: CINIIF 1.5 a)."))
    for k, lab in (("difCosto", "del costo"), ("difDep", "de la depreciación acumulada")):
        mk = "mayorCosto" if k == "difCosto" else "mayorDep"
        if rf[mk] is None:
            pr.append(problema("SIN_MAYOR", f"Ingrese el saldo {lab} según el mayor para conciliar el auxiliar.", 0))
        elif abs(rf[k]) > tol:
            pr.append(problema("CONCILIACION_AUXILIAR_MAYOR", f"Auxiliar y mayor no concilian en el saldo {lab}: diferencia {m(rf[k])}.", rf[k]))

    totales, etiquetas = {}, {}
    for k, lab, v in (
        ("costoFinal", "Costo al cierre (auxiliar)", rf["costoFinal"]),
        ("depRecalculada", "Depreciación del año recalculada", sum(a["dep"] for a in activos if a["dep"] is not None)),
        ("depRegistrada", "Depreciación del año registrada", rf["dreg"]),
        ("ajusteDep", "Diferencia de depreciación (recalculada − registrada)", aj["ajusteDep"]),
        ("nbv", "Valor neto en libros recalculado (activos medidos)", rf["nbv"]),
        ("deterioroAdicional", "Pérdida por deterioro adicional", aj["deterioroAdicional"]),
        ("deterioroORI", "Deterioro contra el superávit de revaluación (ORI)", aj["deterioroORI"]),
        ("deterioroResultado", "Deterioro a resultados", aj["deterioroResultado"]),
        ("ajusteBajas", "Diferencia en resultado de bajas", aj["ajusteBajas"]),
        # M22: si algún activo quedó sin medir, el total no se presenta (no es cero, es desconocido).
        ("capitalizableEspecificos", "Capitalizable de préstamos específicos (NIC 23.12)", _tot(capit, "esp_cap") if prestamos else None),
        ("capitalizableGenerales", "Capitalizable de préstamos generales (NIC 23.14)", _tot(capit, "cap_gen") if prestamos else None),
        ("costosPrestamosIncurridos", "Costos por préstamos incurridos en el período (tope NIC 23.14)",
         tope_inc if prestamos and all(y["costo"] is not None for y in prestamos) else None),
        ("capitalizablePeriodo", "Costos por préstamos capitalizables del período (después del tope)",
         _tot(capit, "final") if prestamos else None),
        ("ajusteIntereses", "Ajuste de intereses capitalizados", aj["ajusteIntereses"]),
        ("revaluacionORI", "Revaluación a otro resultado integral", aj["revaluacionORI"]),
        ("revaluacionResultado", "Revaluación a resultados", aj["revaluacionResultado"]),
        ("provDesmantelamiento", "Provisión de desmantelamiento (valor presente)", vp),
        ("ajusteDesmantelamiento", "Desmantelamiento: cambio de estimación (contra el costo del activo)", desm["cambio"]),
        ("desmantelamientoFinanciero", "Desmantelamiento: actualización financiera del período (costo financiero)", desm["actualizacion"]),
        ("difCosto", "Diferencia auxiliar − mayor (costo)", rf["difCosto"]),
        ("difDepAcum", "Diferencia auxiliar − mayor (depreciación acumulada)", rf["difDep"]),
        ("ajusteResultado", "Efecto neto de los ajustes en resultados", aj["ajusteResultado"]),
    ):
        if v is not None:
            totales[k], etiquetas[k] = r2(v), lab

    iso = lambda d: d.isoformat() if d else ""
    filas = [{"id": a["id"], "descripcion": a["desc"], "clase": a["clase"], "estado": a["estado"], "costo": r2(a["costo"]),
              "depRecalculada": "" if a["dep"] is None else r2(a["dep"]), "depRegistrada": "" if a["dreg"] is None else r2(a["dreg"]),
              "diferencia": "" if a["dif"] is None else r2(a["dif"]), "nbv": "" if a["nbv"] is None else r2(a["nbv"]),
              "_row": a["_row"]} for a in activos]
    limpia = lambda it: [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in x.items()} for x in it]
    detalle = {"cortes": {"actual": corte_a.isoformat(), "inicio": inicio.isoformat()}, "diasAnio": dias_anio,
               "marco": MARCO_PYMES if pymes else MARCO_COMPLETAS, "edicion": edicion_pymes(p) if pymes else "",
               "activos": limpia(activos), "adiciones": limpia(adiciones), "prestamos": limpia(prestamos),
               "capitalizacion": limpia(capit), "tope": {"incurridos": tope_inc, "antes": tope_antes, "factor": factor},
               "desmantelamiento": desm, "rollforward": rf, "ajustes": aj, "parametros": p}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "ajusteResultado",
            "exceptions": pr, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Auxiliar", "Auxiliar de activos (datos del cliente)"),
    ("04_Depreciacion", "Recálculo de depreciación y VNL"), ("05_Vidas_residual", "Vidas útiles, residual y método"),
    ("06_Componentes", "Componentes"), ("07_Bajas", "Bajas"), ("08_Revaluacion", "Revaluación"), ("09_Deterioro", "Deterioro"),
    ("10_Adiciones", "Adiciones y costos por préstamos"), ("11_Prestamos", "Préstamos para la construcción"),
    ("12_Capitalizacion", "Capitalización de costos por préstamos por activo"), ("13_Desmantelamiento", "Desmantelamiento"),
    ("14_Roll_forward", "Movimiento del año y conciliación auxiliar-mayor"), ("15_Ajustes", "Ajustes propuestos"),
    ("16_Problemas", "Problemas encontrados"),
]
P = ref("02_Parametros")
AUX, DEP, BAJ, REV, DET, ADI, PRE, CAP, DES, RF, AJ = (
    ref(n) for n in ("03_Auxiliar", "04_Depreciacion", "07_Bajas", "08_Revaluacion", "09_Deterioro", "10_Adiciones",
                     "11_Prestamos", "12_Capitalizacion", "13_Desmantelamiento", "14_Roll_forward", "15_Ajustes"))
_PAR = ["corte", "inicio", "diasAnio", "marco", "edicion", "tolerancia", "tasaCapitalizacion", "umbralComponente",
        "umbralRevisarComponentes", "costoDesmantelamiento", "aniosDesmantelamiento", "tasaDesmantelamiento",
        "provisionDesmantelamiento", "provisionDesmantelamientoInicial", "mayorCosto", "mayorDepAcum"]
PAR = {k: f"{P}$B${FILA0 + i}" for i, k in enumerate(_PAR)}


def _rng(h: str, col: str, n: int) -> str:
    return f"{h}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _si(celda: str) -> str:
    """Celda opcional: vacía queda vacía (M22)."""
    return f'IF({celda}="","",{celda})'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p = d["parametros"]
    A = d["activos"]
    AD = d["adiciones"]
    PRS, CP = d["prestamos"], d["capitalizacion"]
    rf, aj, ds = d["rollforward"], d["ajustes"], d["desmantelamiento"]
    n, nad, npr, ncap = len(A), len(AD), len(PRS), len(CP)
    fila = {a["id"]: FILA0 + i for i, a in enumerate(A)}
    pv = lambda k: None if p.get(k) in (None, "") else float(a_num(p.get(k)))

    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Inicio del ejercicio", d["cortes"]["inicio"], "Un año antes del corte + 1 día"],
        ["Días del ejercicio", fx(f"B{FILA0}-B{FILA0 + 1}+1", d["diasAnio"]), "Base de la fracción de tiempo"],
        ["Marco contable", d["marco"], "PYMES: costos por préstamos a gasto (Sección 25.2)" if d["marco"] == MARCO_PYMES else "NIC 23: capitaliza en activos aptos"],
        ["Edición PYMES", d["edicion"], "2015 y 2025: mismo tratamiento (resumen oficial de cambios 2025: Secc. 25 editorial; Secc. 27 consecuencial; "
                                      "Secc. 17 sin cambios en revaluación, componentes ni bajas); la 3.ª edición rige desde el 1-1-2027"],
        ["Tolerancia por activo (importe)", pv("tolerancia"), "Juicio del auditor (materialidad de ejecución)"],
        ["Tasa de capitalización (% anual)", pv("tasaCapitalizacion"), "NIC 23.14: media ponderada de los préstamos genéricos"],
        ["Parte significativa desde (% del elemento)", pv("umbralComponente"), "NIC 16.43; juicio del auditor"],
        ["Revisar componentes desde (costo)", pv("umbralRevisarComponentes"), "NIC 16.44; en blanco: no se revisa"],
        ["Desmantelamiento: costo estimado futuro", pv("costoDesmantelamiento"), "NIC 16.16 c; PYMES 17.10 c"],
        ["Desmantelamiento: años hasta el desembolso", pv("aniosDesmantelamiento"), "Estimación técnica"],
        ["Desmantelamiento: tasa antes de impuestos (%)", pv("tasaDesmantelamiento"), "NIC 37.47"],
        ["Provisión de desmantelamiento registrada (cierre)", pv("provisionDesmantelamiento"), "Mayor contable"],
        ["Provisión de desmantelamiento registrada al inicio", pv("provisionDesmantelamientoInicial"),
         "Mayor contable: base de la actualización financiera del período (CINIIF 1.8; NIC 37.60; PYMES 21.11). En blanco y sin provisión al cierre: 0"],
        ["Mayor: costo al cierre", pv("mayorCosto"), "Mayor contable"],
        ["Mayor: depreciación acumulada al cierre", pv("mayorDepAcum"), "Mayor contable"],
    ]

    # 03 · auxiliar tal como lo entregó el cliente.
    aux = [[a["id"], a["desc"], a["clase"], a["elemento"], a["uso"] or None, a["ci"], a["ad"], a["res"], a["vida"], a["metodo"],
            a["dai"], a["dreg"], a["det"], a["rec"], a["rev"], a["sup"], a["decPrev"], a["baja"] or None, a["prod"], a["resreg"]] for a in A]

    # 04 · depreciación y VNL (fila alineada con 03).
    dep = []
    for i, a in enumerate(A):
        r = FILA0 + i
        X = lambda c: f"{AUX}{c}{r}"
        dias = f'IF({X("E")}="",0,MAX(IF({X("R")}<>"",MIN({X("R")},{PAR["corte"]}),{PAR["corte"]})-MAX({X("E")},{PAR["inicio"]})+1,0))'
        dep.append([
            a["id"], fx(f'{X("F")}+{X("G")}', a["costo"]), fx(f'MAX(B{r}-{X("H")},0)', a["depr"]), fx(dias, a["dias"]),
            fx(f'IF(NOT(OR({X("J")}="",ISNUMBER(SEARCH("lineal",{X("J")})))),"",IF(OR({X("I")}="",D{r}=0),0,'
               f'MIN(C{r}/{X("I")}*12*D{r}/{PAR["diasAnio"]},MAX(C{r}-{X("K")},0))))', a["dep"]),
            fx(_si(X("L")), a["dreg"]), fx(f'IF(OR(E{r}="",F{r}=""),"",E{r}-F{r})', a["dif"]),
            fx(f'IF(E{r}="","",{X("K")}+E{r})', a["acum"]), fx(f'{X("M")}', a["det"] or 0.0),
            fx(f'IF(H{r}="","",B{r}-H{r}-I{r})', a["nbv"]),
            fx(f'IF(H{r}="","",IF(AND(C{r}>0,H{r}>=C{r}-0.005),"Sí","No"))', a["total_dep"]),
            fx(f'IF({X("R")}<>"","Baja",IF({X("E")}="","En construcción","En uso"))', a["estado"]),
        ])

    # 05 · vidas útiles, residual y método.
    vidas = []
    for i, a in enumerate(A):
        r = FILA0 + i
        vidas.append([a["id"], a["clase"], a["metodo"], fx(_si(f"{AUX}I{r}"), a["vida"]), fx(f"{AUX}H{r}", a["res"] or 0.0),
                      fx(f"{DEP}B{r}", a["costo"]), fx(f'IF(F{r}=0,"",E{r}/F{r})', a["resid_pct"]), fx(_si(f"{DEP}H{r}"), a["acum"]),
                      fx(f'IF(OR(D{r}="",H{r}="",{DEP}C{r}=0),"",MAX({DEP}C{r}-H{r},0)/{DEP}C{r}*D{r})', a["remanente"]),
                      fx(f'IF(AND({DEP}K{r}="Sí",{DEP}L{r}="En uso"),"Sí","No")', "Sí" if a["total_dep"] == "Sí" and a["estado"] == "En uso" else "No"),
                      fx(f'IF(E{r}>F{r},"Sí","No")', "Sí" if (a["res"] or 0) > a["costo"] else "No")])

    # 06 · componentes.
    comp = [a for a in A if "part" in a]
    nc = len(comp)
    componentes = []
    for i, a in enumerate(comp):
        r, s = FILA0 + i, fila[a["id"]]
        componentes.append([a["id"], a["elemento"] or a["id"], fx(f"{DEP}B{s}", a["costo"]),
                            fx(f"SUMIF($B${FILA0}:$B${FILA0 + nc - 1},B{r},$C${FILA0}:$C${FILA0 + nc - 1})", a["costo_elem"]),
                            fx(f'IF(D{r}=0,"",C{r}/D{r})', a["part"]),
                            fx(f'IF(E{r}="","",IF(E{r}>={PAR["umbralComponente"]}/100,"Sí","No"))', a["signif"]),
                            fx(_si(f"{AUX}I{s}"), a["vida"]), a["metodo"]])

    # 07 · bajas.
    B = [a for a in A if a["baja"]]
    bajas = []
    for i, a in enumerate(B):
        r, s = FILA0 + i, fila[a["id"]]
        bajas.append([a["id"], a["baja"], fx(f"{DEP}B{s}", a["costo"]), fx(_si(f"{DEP}H{s}"), a["acum"]), fx(f"{AUX}M{s}", a["det"] or 0.0),
                      fx(f'IF(D{r}="","",C{r}-D{r}-E{r})', a["nbv_baja"]), fx(f"{AUX}S{s}", a["prod"] or 0.0),
                      fx(f'IF(F{r}="","",G{r}-F{r})', a["res_calc"]), fx(_si(f"{AUX}T{s}"), a["resreg"]),
                      fx(f'IF(OR(H{r}="",I{r}=""),"",H{r}-I{r})', a["res_dif"])])

    # 08 · revaluación.
    R = [a for a in A if "rev_dif" in a]
    frev = {a["id"]: FILA0 + i for i, a in enumerate(R)}
    revs = []
    for i, a in enumerate(R):
        r, s = FILA0 + i, fila[a["id"]]
        revs.append([a["id"], a["clase"], fx(f"{DEP}J{s}", a["nbv"]), fx(f"{AUX}O{s}", a["rev"]), fx(f"D{r}-C{r}", a["rev_dif"]),
                     fx(f"{AUX}P{s}", a["sup"] or 0.0), fx(_si(f"{AUX}Q{s}"), a["decPrev"]),
                     fx(f'IF(E{r}>=0,IF(G{r}="",E{r},E{r}-MIN(E{r},G{r})),-MIN(-E{r},F{r}))', a["rev_ori"]),
                     fx(f'IF(E{r}>=0,IF(G{r}="",0,MIN(E{r},G{r})),E{r}+MIN(-E{r},F{r}))', a["rev_res"])])

    # 09 · deterioro (NIC 36.60-61 / PYMES 27.6: primero contra el superávit del activo revaluado).
    D = [a for a in A if "perdida" in a]
    deter = []
    for i, a in enumerate(D):
        r, s = FILA0 + i, fila[a["id"]]
        ori_anio = f"{REV}H{frev[a['id']]}" if a["id"] in frev else "0"
        deter.append([a["id"], a["clase"], fx(f'IF({AUX}O{s}<>"",{AUX}O{s},{DEP}J{s})', a["libros"]), fx(f"{AUX}N{s}", a["rec"]),
                      fx(f'IF(C{r}="","",MAX(C{r}-D{r},0))', a["perdida"]),
                      fx(f'IF({AUX}P{s}="",0,{AUX}P{s})', a["supPrev"]), fx(ori_anio, a["revOri"]), fx(f"MAX(F{r}+G{r},0)", a["supRem"]),
                      fx(f'IF(E{r}="","",IF(AND({AUX}O{s}="",{AUX}P{s}=""),0,IF({AUX}P{s}="","",MIN(E{r},H{r}))))', a["detORI"]),
                      fx(f'IF(E{r}="","",IF(I{r}="",E{r},E{r}-I{r}))', a["detRes"])])

    # 10 · adiciones y costos por préstamos.
    adic = []
    ra, re_ = _rng(AUX, "A", n), _rng(AUX, "E", n)
    for i, x in enumerate(AD):
        r = FILA0 + i
        mt = f"MATCH(B{r},{ra},0)"
        fin = f'IF(ISNA({mt}),{PAR["corte"]},IF(INDEX({re_},{mt})="",{PAR["corte"]},MIN(INDEX({re_},{mt}),{PAR["corte"]})))'
        # Con anexo de préstamos el capitalizable se mide por activo en la cédula 12 (NIC 23.12 y 14).
        cap_f = '""' if npr else f'IF(I{r}=0,0,IF({PAR["tasaCapitalizacion"]}="","",F{r}*{PAR["tasaCapitalizacion"]}/100*I{r}/{PAR["diasAnio"]}))'
        adic.append([x["id"], x["activo"], x["fecha"], x["desc"], x["tipo"], x["importe"], x["apto"], x["int"],
                     fx(f'IF(OR({PAR["marco"]}="{MARCO_PYMES}",NOT(OR(G{r}="Sí",G{r}="Si"))),0,MAX({fin}-MAX(C{r},{PAR["inicio"]}),0))', x["dias"]),
                     fx(cap_f, x["cap"]), fx(f'IF(J{r}="","",J{r}-H{r})', x["int_dif"]),
                     fx(f'IF(OR(ISNUMBER(SEARCH("repar",E{r})),ISNUMBER(SEARCH("manten",E{r}))),"No: gasto (NIC 16.12)","Sí")', x["capitalizable"])])

    # 11 · préstamos para la construcción (datos del cliente).
    prest = []
    for i, y in enumerate(PRS):
        r = FILA0 + i
        prest.append([y["id"], y["tipo"], y["activo"], y["desc"], y["importe"], y["tasa"], y["costo"], y["rend"],
                      fx(f'IF(B{r}<>"Específico","",IF(OR(G{r}="",H{r}=""),"",G{r}-H{r}))', y["cap_esp"])])

    # 12 · capitalización por activo: específico (NIC 23.12) + generales (NIC 23.14) y tope del párrafo 14.
    PB, PC, PE, PG, PI = (_rng(PRE, c, npr) for c in ("B", "C", "E", "G", "I"))
    ADB, ADF, ADH, ADD = (_rng(ADI, c, nad) for c in ("B", "F", "H", "I"))
    ngen, pym = f'COUNTIF({PB},"General")', f'{PAR["marco"]}="{MARCO_PYMES}"'
    okgen = f'SUMPRODUCT(({PB}="General")*ISNUMBER({PE})*ISNUMBER({PG}))'
    tasa_f = (f'IF({pym},0,IF({ngen}=0,0,IF(OR({okgen}<{ngen},SUMIFS({PE},{PB},"General")=0),"",'
              f'SUMIFS({PG},{PB},"General")/SUMIFS({PE},{PB},"General"))))')
    rj = f"$J${FILA0}:$J${FILA0 + max(ncap, 1) - 1}"
    factor_f = (f'IF(OR(SUMPRODUCT(--ISNUMBER({PG}))<{npr},COUNT({rj})<{ncap}),"",'
                f'IF(SUM({rj})<=SUM({PG}),1,SUM({PG})/SUM({rj})))')
    capit = []
    for i, a in enumerate(CP):
        r = FILA0 + i
        nesp = f'SUMPRODUCT(({PB}="Específico")*({PC}=A{r}))'
        okimp = f'SUMPRODUCT(({PB}="Específico")*({PC}=A{r})*ISNUMBER({PE}))'
        okcap = f'SUMPRODUCT(({PB}="Específico")*({PC}=A{r})*ISNUMBER({PI}))'
        capit.append([
            a["activo"],
            fx(f'SUMIFS({ADF},{ADB},A{r},{ADD},">0")' if nad else "0", a["desemb"]),
            fx(f'SUMPRODUCT(({ADB}=A{r})*{ADF}*{ADD})/{PAR["diasAnio"]}' if nad else "0", a["base"]),
            fx(f'IF({nesp}=0,0,IF({okimp}<{nesp},"",SUMIFS({PE},{PB},"Específico",{PC},A{r})))', a["esp_imp"]),
            fx(f'IF({pym},0,IF({nesp}=0,0,IF({okcap}<{nesp},"",SUMIFS({PI},{PB},"Específico",{PC},A{r}))))', a["esp_cap"]),
            fx(f'IF(D{r}="","",IF(B{r}=0,0,MAX(1-D{r}/B{r},0)))', a["pct"]),
            fx(f'IF(F{r}="","",C{r}*F{r})', a["base_gen"]), fx(tasa_f, a["tasa"]),
            fx(f'IF(OR(G{r}="",H{r}=""),"",G{r}*H{r})', a["cap_gen"]),
            fx(f'IF(OR(E{r}="",I{r}=""),"",E{r}+I{r})', a["antes"]), fx(factor_f, a["factor"]),
            fx(f'IF(J{r}="","",IF(K{r}="",J{r},J{r}*K{r}))', a["final"]),
            fx(f'SUMIFS({ADH},{ADB},A{r})' if nad else "0", a["reg"]),
            fx(f'IF(L{r}="","",L{r}-M{r})', a["dif"]),
        ])
    sc = lambda k: sum(a[k] for a in CP if a[k] is not None)

    # 13 · desmantelamiento.
    b = lambda k: f"B{FILA0 + k}"
    desm = [
        ["Costo estimado futuro", fx(_si(PAR["costoDesmantelamiento"]), ds["costo"])],
        ["Años hasta el desembolso", fx(_si(PAR["aniosDesmantelamiento"]), ds["anios"])],
        ["Tasa de descuento antes de impuestos (%)", fx(_si(PAR["tasaDesmantelamiento"]), ds["tasa"])],
        ["Valor presente = costo ÷ (1 + tasa)^años", fx(f'IF(OR({b(0)}="",{b(1)}="",{b(2)}=""),"",{b(0)}/(1+{b(2)}/100)^{b(1)})', ds["vp"])],
        ["Provisión registrada al cierre", fx(_si(PAR["provisionDesmantelamiento"]), ds["registrada"])],
        ["Provisión registrada al inicio del ejercicio",
         fx(f'IF({PAR["provisionDesmantelamientoInicial"]}<>"",{PAR["provisionDesmantelamientoInicial"]},'
            f'IF({PAR["provisionDesmantelamiento"]}="",0,""))', ds["inicial"])],
        ["Actualización financiera del período = inicial × tasa → resultados, costo financiero (CINIIF 1.8; NIC 37.60; PYMES 21.11)",
         fx(f'IF(OR({b(3)}="",{b(5)}="",{b(2)}=""),"",{b(5)}*{b(2)}/100)', ds["actualizacion"])],
        ["Ajuste total = valor presente − registrada al cierre", fx(f'IF({b(3)}="","",{b(3)}-IF({b(4)}="",0,{b(4)}))', ds["dif"])],
        ["Cambio de estimación = ajuste total − actualización → costo del activo (CINIIF 1.5 a; PYMES 21.7 b)",
         fx(f'IF(OR({b(7)}="",{b(6)}=""),"",{b(7)}-{b(6)})', ds["cambio"])],
    ]

    # 14 · roll-forward.
    c = lambda k: f"B{FILA0 + k}"
    rfw = [
        ["Costo al inicio (auxiliar)", fx(f"SUM({_rng(AUX, 'F', n)})", rf["ci"])],
        ["(+) Adiciones del año", fx(f"SUM({_rng(AUX, 'G', n)})", rf["ad"])],
        ["(−) Costo de las bajas", fx(f'SUMIF({_rng(DEP, "L", n)},"Baja",{_rng(DEP, "B", n)})', rf["costoBajas"])],
        ["Costo al cierre (auxiliar)", fx(f"{c(0)}+{c(1)}-{c(2)}", rf["costoFinal"])],
        ["Costo al cierre según el mayor", fx(_si(PAR["mayorCosto"]), rf["mayorCosto"])],
        ["Diferencia auxiliar − mayor (costo)", fx(f'IF({c(4)}="","",{c(3)}-{c(4)})', rf["difCosto"])],
        ["Depreciación acumulada al inicio", fx(f"SUM({_rng(AUX, 'K', n)})", rf["dai"])],
        ["(+) Depreciación del año registrada", fx(f"SUM({_rng(AUX, 'L', n)})", rf["dreg"])],
        ["(−) Depreciación acumulada de las bajas", fx(f'SUMIF({_rng(DEP, "L", n)},"Baja",{_rng(AUX, "K", n)})+SUMIF({_rng(DEP, "L", n)},"Baja",{_rng(AUX, "L", n)})', rf["depBajas"])],
        ["Depreciación acumulada al cierre (registrada)", fx(f"{c(6)}+{c(7)}-{c(8)}", rf["depFinalReg"])],
        ["Depreciación acumulada según el mayor", fx(_si(PAR["mayorDepAcum"]), rf["mayorDep"])],
        ["Diferencia auxiliar − mayor (depreciación)", fx(f'IF({c(10)}="","",{c(9)}-{c(10)})', rf["difDep"])],
        ["Depreciación acumulada al cierre recalculada (activos medidos)", fx(f'SUMIF({_rng(DEP, "L", n)},"<>Baja",{_rng(DEP, "H", n)})', rf["depFinalCalc"])],
        ["Valor neto en libros recalculado (activos medidos)", fx(f'SUMIF({_rng(DEP, "L", n)},"<>Baja",{_rng(DEP, "J", n)})', rf["nbv"])],
        ["Adiciones según el detalle", fx(f"SUM({_rng(ADI, 'F', nad)})", rf["adDetalle"]) if nad else None],
        ["Diferencia adiciones auxiliar − detalle", fx(f"{c(1)}-{c(14)}", rf["difAd"]) if nad else None],
    ]

    # 15 · ajustes propuestos.
    s = lambda col, h, nn: f"SUM({_rng(h, col, nn)})" if nn else "0"
    ajus = [
        ["Depreciación recalculada − registrada", fx(s("G", DEP, n), aj["ajusteDep"]), "Gasto por depreciación", "(−) Depreciación acumulada", "NIC 16.50; PYMES 17.18"],
        ["Deterioro a resultados", fx(s("J", DET, len(D)), aj["deterioroResultado"]), "Pérdida por deterioro", "(−) Deterioro acumulado",
         "NIC 36.59–61; PYMES 27.5–27.6: en un activo revaluado, primero contra el superávit y solo el exceso a resultados"],
        ["Resultado de bajas recalculado − registrado", fx(s("J", BAJ, len(B)), aj["ajusteBajas"]), "Resultado en baja de activos", "Propiedad, planta y equipo", "NIC 16.68, 71; PYMES 17.28–17.30"],
        ["Costos por préstamos capitalizables − capitalizados",
         fx(s("N", CAP, ncap) if npr else s("K", ADI, nad), aj["ajusteIntereses"]),
         "Construcciones en curso / Gasto financiero", "Gasto financiero / Construcciones en curso",
         "Sección 25.2 (PYMES: todo a gasto)" if d["marco"] == MARCO_PYMES else
         ("NIC 23.12 (específico: costo real − rendimientos), 23.14 (generales: tasa de capitalización) y el tope del 23.14"
          if npr else "NIC 23.8, 14 (estimación por desembolso: falta el anexo de préstamos)")],
        ["Revaluación a otro resultado integral", fx(s("H", REV, len(R)), aj["revaluacionORI"]), "Propiedad, planta y equipo", "Superávit de revaluación (ORI)", "NIC 16.39–40; PYMES 17.15C–17.15D"],
        ["Revaluación a resultados", fx(s("I", REV, len(R)), aj["revaluacionResultado"]), "Pérdida por revaluación / Reversión de decremento previo", "Propiedad, planta y equipo",
         "NIC 16.39 (aumento que revierte un decremento previo en resultados) y 16.40; PYMES 17.15C–17.15D"],
        ["Deterioro contra el superávit de revaluación", fx(s("I", DET, len(D)), aj["deterioroORI"]), "Superávit de revaluación (ORI)", "(−) Deterioro acumulado",
         "NIC 36.60–61; PYMES 27.6"],
        ["Desmantelamiento: cambio de estimación", fx(f"{DES}B{FILA0 + 8}", ds["cambio"]) if ds["cambio"] is not None else None,
         "Propiedad, planta y equipo (costo)", "Provisión por desmantelamiento", "CINIIF 1.5 a; NIC 16.16 c; NIC 37.45; PYMES 21.7 b"],
        ["Desmantelamiento: actualización financiera del período", fx(f"{DES}B{FILA0 + 6}", ds["actualizacion"]) if ds["actualizacion"] is not None else None,
         "Costo financiero (resultados)", "Provisión por desmantelamiento", "CINIIF 1.8; NIC 37.60; PYMES 21.11"],
        ["Efecto neto en resultados",
         fx(f'-B{FILA0}-B{FILA0 + 1}+B{FILA0 + 2}+B{FILA0 + 3}+B{FILA0 + 5}-IF(B{FILA0 + 8}="",0,B{FILA0 + 8})', aj["ajusteResultado"]), "", "",
         "− depreciación − deterioro a resultados + bajas + intereses + revaluación a resultados − actualización financiera del desmantelamiento"],
    ]

    celda = {"costoFinal": f"{RF}B{FILA0 + 3}", "depRecalculada": f"SUM({_rng(DEP, 'E', n)})", "depRegistrada": f"{RF}B{FILA0 + 7}",
             "ajusteDep": f"{AJ}B{FILA0}", "nbv": f"{RF}B{FILA0 + 13}", "deterioroAdicional": f"SUM({_rng(DET, 'E', len(D))})",
             "deterioroORI": f"{AJ}B{FILA0 + 6}", "deterioroResultado": f"{AJ}B{FILA0 + 1}",
             "capitalizableEspecificos": f"{CAP}E{FILA0 + ncap}", "capitalizableGenerales": f"{CAP}I{FILA0 + ncap}",
             "costosPrestamosIncurridos": f"{PRE}G{FILA0 + npr}", "capitalizablePeriodo": f"{CAP}L{FILA0 + ncap}",
             "ajusteBajas": f"{AJ}B{FILA0 + 2}", "ajusteIntereses": f"{AJ}B{FILA0 + 3}", "revaluacionORI": f"{AJ}B{FILA0 + 4}",
             "revaluacionResultado": f"{AJ}B{FILA0 + 5}", "provDesmantelamiento": f"{DES}B{FILA0 + 3}",
             "ajusteDesmantelamiento": f"{AJ}B{FILA0 + 7}", "desmantelamientoFinanciero": f"{AJ}B{FILA0 + 8}",
             "difCosto": f"{RF}B{FILA0 + 5}", "difDepAcum": f"{RF}B{FILA0 + 11}", "ajusteResultado": f"{AJ}B{FILA0 + 9}"}
    valor = {"costoFinal": rf["costoFinal"], "depRecalculada": sum(a["dep"] for a in A if a["dep"] is not None), "depRegistrada": rf["dreg"],
             "nbv": rf["nbv"], "provDesmantelamiento": ds["vp"], "difCosto": rf["difCosto"], "difDepAcum": rf["difDep"],
             "capitalizableEspecificos": sc("esp_cap"), "capitalizableGenerales": sc("cap_gen"),
             "costosPrestamosIncurridos": d["tope"]["incurridos"], "capitalizablePeriodo": sc("final"), **aj}
    resumen = [[res["labels"][k], fx(celda[k], valor[k])] for k in res["labels"]]

    # --- «Cómo se calcula esta hoja»: explicación humana por columna calculada -------------
    ex_resumen = {"Importe": "Trae cada concepto de su hoja: costo y diferencias con el mayor de la hoja 14 (Movimiento del año), "
                             "depreciación de las hojas 04 y 14, ajustes de la hoja 15 (Ajustes propuestos), deterioro de la hoja 09, "
                             "costos por préstamos de las hojas 11 y 12 y desmantelamiento de la hoja 13."}
    ex_par = {"Valor": "Son los datos de la ficha del encargo y del mayor; la única fila calculada es «Días del ejercicio»: fecha de "
                       "corte menos fecha de inicio, más un día."}
    ex_dep = {
        "Costo": "Suma el costo inicial y las adiciones del año del activo, tomados de la hoja 03 (Auxiliar de activos).",
        "Importe depreciable": "Costo menos el valor residual de la hoja 03 (Auxiliar de activos), sin bajar de cero: es lo que se "
                               "reparte durante la vida útil.",
        "Días en uso": "Cuenta los días del ejercicio en que el activo estuvo disponible: desde su fecha de disponibilidad (o el "
                       "inicio del ejercicio) hasta el corte o la fecha de baja. Si no tiene fecha de disponibilidad (en "
                       "construcción), es cero.",
        "Depreciación recalculada": "Solo para el método lineal: importe depreciable ÷ vida útil en meses × 12 × días en uso ÷ días "
                                    "del ejercicio, sin pasar de lo que queda por depreciar. Otros métodos quedan en blanco; sin "
                                    "vida útil o sin días en uso da cero.",
        "Depreciación registrada": "Trae la depreciación del año que registró el cliente, desde la hoja 03 (Auxiliar de activos); "
                                   "en blanco si no la informó.",
        "Diferencia": "Depreciación recalculada menos registrada; en blanco si falta alguna de las dos.",
        "Dep. acumulada recalculada": "Suma la depreciación acumulada al inicio de la hoja 03 (Auxiliar de activos) y la "
                                      "depreciación recalculada del año; en blanco si no se recalculó.",
        "Deterioro acumulado": "Trae el deterioro acumulado que registró el cliente para el activo, desde la hoja 03 (Auxiliar de "
                               "activos).",
        "Valor neto en libros": "Costo menos depreciación acumulada recalculada menos deterioro acumulado; en blanco si la "
                                "depreciación no se recalculó.",
        "Totalmente depreciado": "«Sí» cuando la depreciación acumulada recalculada ya cubre todo el importe depreciable; «No» si "
                                 "no; en blanco si no se recalculó.",
        "Estado": "«Baja» si el activo tiene fecha de baja en la hoja 03, «En construcción» si aún no tiene fecha de disponibilidad "
                  "para uso y «En uso» en los demás casos.",
    }
    ex_vidas = {
        "Vida útil (meses)": "Trae la vida útil en meses informada en la hoja 03 (Auxiliar de activos); en blanco si no se informó.",
        "Valor residual": "Trae el valor residual del activo desde la hoja 03 (Auxiliar de activos); si está vacío, cero.",
        "Costo": "Trae el costo del activo (costo inicial más adiciones) desde la hoja 04 (Recálculo de depreciación y VNL).",
        "Residual % del costo": "Divide el valor residual para el costo, para ver si el residual es razonable; en blanco si el "
                                "costo es cero.",
        "Dep. acumulada recalculada": "Trae la depreciación acumulada recalculada desde la hoja 04 (Recálculo de depreciación y "
                                      "VNL); en blanco si allí no se recalculó.",
        "Vida remanente (meses)": "Parte de la vida útil que queda: importe depreciable pendiente (hoja 04) sobre el importe "
                                  "depreciable total, por la vida útil en meses. En blanco si falta la vida útil o la depreciación.",
        "Totalmente depreciado en uso": "«Sí» cuando en la hoja 04 el activo figura totalmente depreciado y sigue en uso: señal "
                                        "de que la vida útil estimada fue corta.",
        "Residual mayor que el costo": "«Sí» si el valor residual supera al costo del activo, lo que no es razonable; «No» en "
                                       "caso contrario.",
    }
    ex_comp = {
        "Costo de la parte": "Trae el costo de esta parte (componente) desde la hoja 04 (Recálculo de depreciación y VNL).",
        "Costo del elemento": "Suma el costo de todas las partes de esta hoja que pertenecen al mismo elemento: es el costo total "
                              "del elemento.",
        "% del elemento": "Divide el costo de la parte para el costo total del elemento; en blanco si el elemento no tiene costo.",
        "Parte significativa": "«Sí» si el % del elemento alcanza el umbral de parte significativa de la hoja 02 (Parámetros), por "
                               "lo que debe depreciarse por separado; «No» si no llega.",
        "Vida útil (meses)": "Trae la vida útil en meses de la parte desde la hoja 03 (Auxiliar de activos); en blanco si no se "
                             "informó.",
    }
    ex_bajas = {
        "Costo": "Trae el costo del activo dado de baja desde la hoja 04 (Recálculo de depreciación y VNL).",
        "Dep. acumulada a la baja": "Trae la depreciación acumulada recalculada hasta la fecha de baja, desde la hoja 04; en blanco "
                                    "si no se pudo recalcular.",
        "Deterioro": "Trae el deterioro acumulado del activo desde la hoja 03 (Auxiliar de activos).",
        "VNL a la baja": "Costo menos depreciación acumulada a la baja menos deterioro: es el valor en libros que sale con la baja "
                         "(en blanco si falta la depreciación acumulada).",
        "Producto": "Trae lo que se cobró por la baja (venta o indemnización) desde la hoja 03 (Auxiliar de activos); si está "
                    "vacío, cero.",
        "Resultado recalculado": "Producto de la baja menos el valor neto en libros a la baja: positivo es ganancia y negativo "
                                 "pérdida.",
        "Resultado registrado": "Trae la ganancia o pérdida en la baja que registró el cliente, desde la hoja 03; en blanco si no "
                                "la informó.",
        "Diferencia": "Resultado recalculado menos resultado registrado; en blanco si falta alguno de los dos.",
    }
    ex_rev = {
        "VNL al corte": "Trae el valor neto en libros recalculado al corte desde la hoja 04 (Recálculo de depreciación y VNL).",
        "Valor revaluado": "Trae el valor revaluado del activo (según el perito) desde la hoja 03 (Auxiliar de activos).",
        "Diferencia": "Valor revaluado menos valor neto en libros: positivo es aumento y negativo disminución por revaluación.",
        "Superávit previo": "Trae el superávit de revaluación que ya tenía el activo, desde la hoja 03 (Auxiliar de activos).",
        "Decremento previo en resultados": "Trae la disminución por revaluación que se llevó antes a resultados, desde la hoja 03; "
                                           "en blanco si no se informó.",
        "A otro resultado integral": "Si es aumento, va a ORI lo que excede al decremento previo llevado a resultados (todo, si ese "
                                     "dato está vacío). Si es disminución, se carga a ORI solo hasta el superávit previo.",
        "A resultados": "Si es aumento, va a resultados solo lo que revierte el decremento previo (cero si ese dato está vacío). "
                        "Si es disminución, va a resultados lo que excede al superávit previo.",
    }
    ex_det = {
        "Importe en libros": "Usa el valor revaluado de la hoja 03 si el activo se revaluó; si no, el valor neto en libros de la "
                             "hoja 04 (Recálculo de depreciación y VNL).",
        "Importe recuperable": "Trae el importe recuperable estimado del activo desde la hoja 03 (Auxiliar de activos).",
        "Pérdida adicional": "Importe en libros menos importe recuperable, sin bajar de cero: es la pérdida por deterioro. En "
                             "blanco si no hay importe en libros.",
        "Superávit previo": "Trae el superávit de revaluación previo del activo desde la hoja 03 (Auxiliar de activos); si está "
                            "vacío, cero.",
        "Revaluación del año a ORI": "Trae lo que la revaluación del año llevó a ORI en la hoja 08 (Revaluación); cero si el "
                                     "activo no se revaluó este año.",
        "Superávit disponible": "Suma el superávit previo y la revaluación del año a ORI, sin bajar de cero: es el colchón contra "
                                "el que se carga primero el deterioro.",
        "Contra el superávit (ORI)": "Carga la pérdida contra el superávit disponible, hasta agotarlo. Si el activo no está "
                                     "revaluado ni tiene superávit, es cero; si está revaluado pero falta el superávit, queda en "
                                     "blanco.",
        "A resultados": "La pérdida que no se cargó al superávit va a resultados; si no se pudo repartir (celda anterior en "
                        "blanco), va toda la pérdida.",
    }
    if npr:
        ex_ad_int = ("Con el anexo de préstamos los intereses capitalizables se miden por activo en la hoja 12 (Capitalización de "
                     "costos por préstamos), por eso aquí quedan en blanco.")
        ex_ad_dif = ("Intereses capitalizables menos intereses capitalizados por el cliente; con el anexo de préstamos queda en "
                     "blanco porque la comparación se hace en la hoja 12.")
    else:
        ex_ad_int = ("Importe de la adición × tasa de capitalización de la hoja 02 (Parámetros) × días de capitalización ÷ días del "
                     "ejercicio. Cero si no hay días; en blanco si no hay tasa.")
        ex_ad_dif = "Intereses capitalizables recalculados menos los intereses que el cliente capitalizó en esta adición."
    ex_adic = {
        "Días de capitalización": "Para adiciones de activos aptos (y solo en NIIF completas): días desde la fecha de la adición (o "
                                  "el inicio del ejercicio) hasta que el activo está disponible para uso según la hoja 03, o hasta el "
                                  "corte. Si no, cero.",
        "Intereses capitalizables": ex_ad_int,
        "Diferencia": ex_ad_dif,
        "Capitalizable": "«No: gasto» si el tipo de adición es una reparación o un mantenimiento, que no se capitalizan; «Sí» en "
                         "los demás casos.",
    }
    ex_pre = {"Capitalizable del específico (NIC 23.12)": "Solo para préstamos específicos: costo financiero del período menos "
                                                          "los rendimientos de la inversión temporal de esos fondos. En blanco "
                                                          "para préstamos generales o si falta un dato."}
    ex_cap = {
        "Desembolsos aptos del período": "Suma las adiciones de este activo en la hoja 10 (Adiciones) que tienen días de "
                                         "capitalización.",
        "Base ponderada por tiempo": "Suma cada adición del activo en la hoja 10 multiplicada por sus días de capitalización y la "
                                     "divide para los días del ejercicio: es el desembolso promedio del año.",
        "Préstamo específico: importe": "Suma el importe de los préstamos específicos de este activo en la hoja 11 (Préstamos); "
                                        "cero si no tiene y en blanco si alguno no trae importe.",
        "Capitalizable del específico (NIC 23.12)": "Suma lo capitalizable de los préstamos específicos del activo en la hoja 11. "
                                                    "Es cero en PYMES o sin préstamo específico, y en blanco si falta un dato.",
        "% financiado con préstamos generales": "Parte de los desembolsos que no cubre el préstamo específico: 1 − importe "
                                                "específico ÷ desembolsos, sin bajar de cero. Cero si no hubo desembolsos.",
        "Base financiada con generales": "Multiplica la base ponderada por tiempo por el % financiado con préstamos generales.",
        "Tasa de capitalización (NIC 23.14)": "Media ponderada de los préstamos generales de la hoja 11: su costo financiero total "
                                              "÷ su importe total. Cero en PYMES o sin generales; en blanco si falta un dato.",
        "Capitalizable de los generales": "Multiplica la base financiada con generales por la tasa de capitalización; en blanco si "
                                          "falta alguno de los dos.",
        "Capitalizable antes del tope": "Suma lo capitalizable del préstamo específico y de los generales para este activo.",
        "Factor del tope (NIC 23.14)": "Si lo capitalizable de todos los activos no supera el costo financiero incurrido de la hoja "
                                       "11, es 1; si lo supera, es costo incurrido ÷ capitalizable total, para no pasar del tope. "
                                       "En blanco si falta algún dato.",
        "Capitalizable del período": "Capitalizable antes del tope multiplicado por el factor del tope (si el factor está en "
                                     "blanco, se deja sin reducir).",
        "Intereses capitalizados registrados": "Suma los intereses que el cliente capitalizó en las adiciones de este activo, según "
                                               "la hoja 10 (Adiciones).",
        "Diferencia": "Capitalizable del período menos intereses capitalizados registrados: positivo falta capitalizar y negativo "
                      "se capitalizó de más.",
    }
    ex_desm = {"Importe": "Toma de la hoja 02 (Parámetros) el costo futuro, los años, la tasa y la provisión registrada; calcula el "
                          "valor presente (costo ÷ (1 + tasa)^años), la actualización del año (provisión inicial × tasa) y separa "
                          "el ajuste total en actualización y cambio de estimación."}
    ex_rf = {"Importe": "Arma el movimiento del año con las sumas de la hoja 03 (costo, adiciones, depreciación) y de la hoja 04 "
                        "(bajas y valores recalculados), lo compara con el mayor de la hoja 02 y cuadra las adiciones con la hoja 10."}
    ex_aj = {"Importe": "Suma la diferencia de cada prueba desde su hoja (04 depreciación, 09 deterioro, 07 bajas, 12 o 10 intereses, "
                        "08 revaluación, 13 desmantelamiento); la última fila combina esos ajustes para dar el efecto neto en "
                        "resultados."}

    fin = lambda nn: FILA0 + nn - 1
    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=ex_resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros, explica=ex_par),
        hoja("03_Auxiliar", "Auxiliar de activos (datos del cliente)",
             [["Código", "t"], ["Descripción", "t"], ["Clase", "t"], ["Elemento", "t"], ["Disponible para uso", "d"], ["Costo inicial", "n"],
              ["Adiciones", "n"], ["Valor residual", "n"], ["Vida útil (meses)", "i"], ["Método", "t"], ["Dep. acum. inicial", "n"],
              ["Dep. del año registrada", "n"], ["Deterioro acumulado", "n"], ["Importe recuperable", "n"], ["Valor revaluado", "n"],
              ["Superávit previo", "n"], ["Decremento previo en resultados", "n"], ["Fecha de baja", "d"], ["Producto de la baja", "n"],
              ["Resultado de baja registrado", "n"]], aux),
        hoja("04_Depreciacion", "Recálculo de depreciación y VNL",
             [["Código", "t"], ["Costo", "n"], ["Importe depreciable", "n"], ["Días en uso", "i"], ["Depreciación recalculada", "n"],
              ["Depreciación registrada", "n"], ["Diferencia", "n"], ["Dep. acumulada recalculada", "n"], ["Deterioro acumulado", "n"],
              ["Valor neto en libros", "n"], ["Totalmente depreciado", "t"], ["Estado", "t"]], dep,
             ["TOTAL", suma("B", fin(n), sum(a["costo"] for a in A)), None, None, suma("E", fin(n), valor["depRecalculada"]),
              suma("F", fin(n), rf["dreg"]), suma("G", fin(n), aj["ajusteDep"]), None, None, None, "", ""], explica=ex_dep),
        hoja("05_Vidas_residual", "Vidas útiles, residual y método",
             [["Código", "t"], ["Clase", "t"], ["Método", "t"], ["Vida útil (meses)", "i"], ["Valor residual", "n"], ["Costo", "n"],
              ["Residual % del costo", "p"], ["Dep. acumulada recalculada", "n"], ["Vida remanente (meses)", "n"],
              ["Totalmente depreciado en uso", "t"], ["Residual mayor que el costo", "t"]], vidas, explica=ex_vidas),
        hoja("06_Componentes", "Componentes",
             [["Código", "t"], ["Elemento", "t"], ["Costo de la parte", "n"], ["Costo del elemento", "n"], ["% del elemento", "p"],
              ["Parte significativa", "t"], ["Vida útil (meses)", "i"], ["Método", "t"]], componentes, explica=ex_comp),
        hoja("07_Bajas", "Bajas",
             [["Código", "t"], ["Fecha de baja", "d"], ["Costo", "n"], ["Dep. acumulada a la baja", "n"], ["Deterioro", "n"],
              ["VNL a la baja", "n"], ["Producto", "n"], ["Resultado recalculado", "n"], ["Resultado registrado", "n"], ["Diferencia", "n"]], bajas,
             ["TOTAL", "", None, None, None, None, None, None, None, suma("J", fin(len(B)), aj["ajusteBajas"])] if B else None, explica=ex_bajas),
        hoja("08_Revaluacion", "Revaluación",
             [["Código", "t"], ["Clase", "t"], ["VNL al corte", "n"], ["Valor revaluado", "n"], ["Diferencia", "n"], ["Superávit previo", "n"],
              ["Decremento previo en resultados", "n"], ["A otro resultado integral", "n"], ["A resultados", "n"]], revs,
             ["TOTAL", "", None, None, None, None, None, suma("H", fin(len(R)), aj["revaluacionORI"]),
              suma("I", fin(len(R)), aj["revaluacionResultado"])] if R else None, explica=ex_rev),
        hoja("09_Deterioro", "Deterioro",
             [["Código", "t"], ["Clase", "t"], ["Importe en libros", "n"], ["Importe recuperable", "n"], ["Pérdida adicional", "n"],
              ["Superávit previo", "n"], ["Revaluación del año a ORI", "n"], ["Superávit disponible", "n"],
              ["Contra el superávit (ORI)", "n"], ["A resultados", "n"]], deter,
             ["TOTAL", "", None, None, suma("E", fin(len(D)), aj["deterioroAdicional"]), None, None, None,
              suma("I", fin(len(D)), aj["deterioroORI"]), suma("J", fin(len(D)), aj["deterioroResultado"])] if D else None, explica=ex_det),
        hoja("10_Adiciones", "Adiciones y costos por préstamos",
             [["Documento", "t"], ["Activo", "t"], ["Fecha", "d"], ["Descripción", "t"], ["Tipo", "t"], ["Importe", "n"], ["Apto", "t"],
              ["Intereses capitalizados", "n"], ["Días de capitalización", "i"], ["Intereses capitalizables", "n"], ["Diferencia", "n"],
              ["Capitalizable", "t"]], adic,
             ["TOTAL", "", "", "", "", suma("F", fin(nad), rf["adDetalle"] or 0), "", suma("H", fin(nad), sum(x["int"] or 0 for x in AD)), None,
              None, suma("K", fin(nad), 0 if npr else aj["ajusteIntereses"]), ""] if nad else None, explica=ex_adic),
        hoja("11_Prestamos", "Préstamos para la construcción",
             [["Préstamo", "t"], ["Tipo", "t"], ["Activo u obra", "t"], ["Descripción", "t"], ["Importe del préstamo", "n"],
              ["Tasa nominal anual (%)", "n"], ["Costo financiero del período", "n"], ["(−) Rendimientos de la inversión temporal", "n"],
              ["Capitalizable del específico (NIC 23.12)", "n"]], prest,
             ["TOTAL", "", "", "", suma("E", fin(npr), sum(y["importe"] or 0 for y in PRS)), None,
              suma("G", fin(npr), d["tope"]["incurridos"]), suma("H", fin(npr), sum(y["rend"] or 0 for y in PRS)),
              suma("I", fin(npr), sum(y["cap_esp"] for y in PRS if y["cap_esp"] is not None))] if npr else None, explica=ex_pre),
        hoja("12_Capitalizacion", "Capitalización de costos por préstamos por activo",
             [["Activo", "t"], ["Desembolsos aptos del período", "n"], ["Base ponderada por tiempo", "n"],
              ["Préstamo específico: importe", "n"], ["Capitalizable del específico (NIC 23.12)", "n"],
              ["% financiado con préstamos generales", "p"], ["Base financiada con generales", "n"],
              ["Tasa de capitalización (NIC 23.14)", "p"], ["Capitalizable de los generales", "n"],
              ["Capitalizable antes del tope", "n"], ["Factor del tope (NIC 23.14)", "p"], ["Capitalizable del período", "n"],
              ["Intereses capitalizados registrados", "n"], ["Diferencia", "n"]], capit,
             ["TOTAL", suma("B", fin(ncap), sc("desemb")), suma("C", fin(ncap), sc("base")), suma("D", fin(ncap), sc("esp_imp")),
              suma("E", fin(ncap), sc("esp_cap")), None, suma("G", fin(ncap), sc("base_gen")), None,
              suma("I", fin(ncap), sc("cap_gen")), suma("J", fin(ncap), sc("antes")), None,
              suma("L", fin(ncap), sc("final")), suma("M", fin(ncap), sc("reg")), suma("N", fin(ncap), sc("dif"))] if ncap else None,
             explica=ex_cap),
        hoja("13_Desmantelamiento", "Desmantelamiento", [["Concepto", "t"], ["Importe", "n"]], desm, explica=ex_desm),
        hoja("14_Roll_forward", "Movimiento del año y conciliación auxiliar-mayor", [["Concepto", "t"], ["Importe", "n"]], rfw, explica=ex_rf),
        hoja("15_Ajustes", "Ajustes propuestos", [["Ajuste", "t"], ["Importe", "n"], ["Débito (si positivo)", "t"], ["Crédito (si positivo)", "t"], ["Base", "t"]], ajus, explica=ex_aj),
        hoja("16_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -------------------------------------------------------------------

def definicion() -> dict:
    aux = ("Una fila por activo o componente: código, descripción, clase, elemento (si es parte), fecha disponible para uso, "
           "costo inicial, adiciones, residual, vida útil en meses, método, depreciación acumulada inicial, depreciación del año "
           "registrada, deterioro acumulado; si aplica: importe recuperable, valor revaluado, superávit previo, fecha y producto de la baja "
           "y resultado registrado. Sin filas de total.")
    return {
        "name": "Propiedad, planta y equipo",
        "area": "Propiedad, planta y equipo",
        "processor": "ppe_propiedad_planta",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Recalcula por activo la depreciación, el valor neto en libros y el resultado de las bajas; evalúa vidas útiles, "
                    "residuales, componentes, revaluación, deterioro y la provisión de desmantelamiento; con el anexo de préstamos separa los "
                    "específicos (costo real menos los rendimientos de la inversión temporal) de los generales (tasa de capitalización) y aplica "
                    "el tope de los costos incurridos (NIC 23.12 y 14; en PYMES todo es gasto, Sección 25.2), y concilia el auxiliar con el mayor."),
        "source": {"organization": "IFRS Foundation — traducción oficial al español (NIIF 2023)", "type": "Norma contable", "date": "2026-09-22",
                   "document": ("NIC 16 párr. 12, 16 c, 31–42 (39, 40), 43–47, 50–62, 67–72; NIC 23 párr. 8, 12, 14, 20, 22; "
                                "NIC 36 párr. 18, 59–60; NIC 37 párr. 45, 47, 60; CINIIF 1 párr. 5 y 8"),
                   "url": "https://www.ifrs.org/content/dam/ifrs/publications/html-standards/spanish/2023/issued/ias16.html"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015 y 2025: Sección 17 (17.6, 17.10 c, 17.15–17.15D revaluación, 17.16 componentes, "
                                      "17.18–17.23 depreciación, 17.27–17.30 bajas), Sección 25 (25.2: costos por préstamos a gasto), "
                                      "Sección 27 (27.5–27.6 deterioro), Sección 21 (21.7 b desmantelamiento, 21.11 reversión del descuento); "
                                      "17.15 (mantenimiento diario a gasto). Numeración verificada en las ediciones 2015 y 2025."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 500", "section": "párr. 6–9", "requirement": "Evidencia suficiente y adecuada sobre existencia, integridad y valoración del auxiliar."},
            {"document": "NIA 510", "section": "párr. 6", "requirement": "Saldos iniciales: el costo y la depreciación acumulada iniciales se concilian con el cierre anterior; aplica en encargos iniciales; en recurrentes NIA 500/330."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13–30 y 32", "requirement": "Estimaciones: vidas útiles, residuales, importe recuperable, valor razonable y desmantelamiento."},
            {"document": "NIA 500", "section": "párr. A18 y A20", "requirement": "Inspección física de activos tangibles."},
            {"document": "NIA 500", "section": "párr. 8", "requirement": "Perito de la dirección (NIA 620 solo si lo contrata el auditor): evaluar su trabajo en revaluaciones y deterioro."},
        ],
        "calculo": [
            "Costo = costo inicial + adiciones del año; importe depreciable = costo − valor residual (NIC 16.53; PYMES 17.18).",
            "Depreciación lineal del período = importe depreciable ÷ vida útil (meses) × 12 × días en uso ÷ días del año, sin pasar del importe pendiente (NIC 16.50, 55; PYMES 17.20).",
            "Valor neto en libros = costo − depreciación acumulada − deterioro acumulado.",
            "Baja: ganancia o pérdida = producto − valor neto en libros a la fecha de baja (NIC 16.71; PYMES 17.30).",
            "Revaluación al corte: el aumento va a resultados hasta revertir el decremento previo del mismo activo reconocido en resultados y el resto a "
            "ORI (NIC 16.39; PYMES 17.15C); la disminución va a ORI hasta el superávit previo y el resto a resultados (NIC 16.40; PYMES 17.15D).",
            "Deterioro: pérdida = max(importe en libros − importe recuperable, 0) (NIC 36.59; PYMES 27.5). En activos revaluados, la pérdida va contra el "
            "superávit de ese activo (superávit previo + revaluación del año a ORI) y solo el exceso a resultados (NIC 36.60–61; PYMES 27.6).",
            "Costos por préstamos con el anexo de préstamos (solo NIIF completas): por activo, capitalizable = (costo financiero del período realmente "
            "incurrido en el préstamo específico − rendimientos de la inversión temporal de esos fondos, NIC 23.12) + (tasa de capitalización de los "
            "préstamos generales × desembolsos del activo financiados con ellos, NIC 23.14). La tasa de capitalización es la media ponderada de los costos "
            "por intereses de los préstamos genéricos (costo del período ÷ importe). Los desembolsos financiados con generales son los desembolsos aptos del "
            "activo ponderados por los días del período, por la proporción no cubierta por el préstamo específico = máx(1 − importe del específico ÷ "
            "desembolsos aptos, 0). Tope: lo capitalizado en el período no excede los costos por préstamos incurridos (NIC 23.14, última frase); si excede, "
            "se prorratea entre los activos.",
            "Costos por préstamos sin el anexo (estimación de respaldo): desembolso × tasa de capitalización del parámetro × días ÷ días del año (NIC 23.14), "
            "y se avisa que falta el anexo. En NIIF para las PYMES todo costo por préstamos es gasto del período (Sección 25.2, ediciones 2015 y 2025): no se "
            "capitaliza nada y lo capitalizado por el cliente es ajuste.",
            "Desmantelamiento: valor presente = costo estimado ÷ (1 + tasa)^años (NIC 37.45–47; PYMES 21.7 b). Ajuste total = valor presente − provisión "
            "registrada al cierre; de él, la actualización financiera del período = provisión al inicio × tasa va a resultados como costo financiero "
            "(CINIIF 1.8; NIC 37.60; PYMES 21.11) y el resto es cambio de estimación contra el costo del activo (CINIIF 1.5 a).",
            "Movimiento del año: costo y depreciación acumulada inicial + movimientos − bajas = cierre, conciliado con el mayor.",
        ],
        "fields": _ACTIVOS, "rules": [], "control": CONTROL, "primary": "ajusteResultado",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[a, b] for a, b in CEDULAS],
        "program": [
            {"code": "PPE-01", "objective": "Conciliación auxiliar-mayor", "risk": "Auxiliar incompleto o distinto del mayor", "assertion": "Integridad",
             "procedure": "Movimiento del año del costo y la depreciación acumulada y conciliación con el mayor", "evidence": "Auxiliar y mayor",
             "criterion": "Diferencia dentro de tolerancia o explicada", "source": "NIA 500 · NIA 510"},
            {"code": "PPE-02", "objective": "Adiciones", "risk": "Gastos capitalizados o adiciones sin soporte", "assertion": "Existencia / Clasificación",
             "procedure": "Examinar las adiciones y separar capital de gasto (reparación y mantenimiento)", "evidence": "Facturas, contratos, actas de recepción",
             "criterion": "Solo costos que cumplen NIC 16.7 y 16.16", "source": "NIC 16.12, 16 · PYMES 17.6, 17.10, 17.15"},
            {"code": "PPE-03", "objective": "Depreciación", "risk": "Depreciación mal calculada", "assertion": "Valoración",
             "procedure": "Recalcular la depreciación por activo desde la fecha disponible para uso", "evidence": "Auxiliar",
             "criterion": "Diferencias dentro de tolerancia", "source": "NIC 16.50–62 · PYMES 17.18–17.23"},
            {"code": "PPE-04", "objective": "Vidas útiles, residual, método y componentes", "risk": "Estimaciones desactualizadas; partes significativas sin separar", "assertion": "Valoración",
             "procedure": "Revisar activos totalmente depreciados en uso, residuales y partes significativas", "evidence": "Política contable, informes técnicos",
             "criterion": "NIIF: revisadas al cierre (NIC 16.51, 61); PYMES: si hay indicios (17.19)", "source": "NIC 16.43–47, 51, 61 · PYMES 17.16, 17.19"},
            {"code": "PPE-05", "objective": "Bajas", "risk": "Resultado de baja mal calculado u omitido", "assertion": "Exactitud",
             "procedure": "Recalcular el valor neto en libros a la baja y la ganancia o pérdida", "evidence": "Facturas de venta, actas de baja",
             "criterion": "Resultado recalculado igual al registrado", "source": "NIC 16.67–72 · PYMES 17.27–17.30"},
            {"code": "PPE-06", "objective": "Revaluación", "risk": "Superávit mal medido o clase incompleta", "assertion": "Valoración",
             "procedure": "Comparar el valor revaluado con el VNL y distribuir entre ORI y resultados", "evidence": "Informe del perito",
             "criterion": "Tratamiento según NIC 16.39–40", "source": "NIC 16.31–42 · PYMES 17.15–17.15D · NIA 620"},
            {"code": "PPE-07", "objective": "Deterioro", "risk": "Importe en libros superior al recuperable", "assertion": "Valoración",
             "procedure": "Comparar el importe en libros con el importe recuperable", "evidence": "Cálculo de valor en uso o valor razonable",
             "criterion": "Pérdida reconocida", "source": "NIC 36.59–61 · PYMES 27.5–27.6 (si el activo está revaluado, primero contra el superávit) · NIA 540"},
            {"code": "PPE-08", "objective": "Costos por préstamos", "risk": "Intereses capitalizados indebidamente o por encima de los incurridos",
             "assertion": "Valoración / Clasificación",
             "procedure": "Separar préstamos específicos y generales; recalcular por activo el capitalizable (específico: costo real menos los rendimientos de la "
                          "inversión temporal; generales: tasa de capitalización) y comprobar el tope de los costos incurridos en el período (NIIF completas); en "
                          "PYMES reversar lo capitalizado",
             "evidence": "Contratos de préstamo, tablas de amortización, mayor de gasto financiero y de rendimientos de inversiones temporales",
             "criterion": "NIC 23.12, 14 (incluido el tope) / Sección 25.2", "source": "NIC 23 · PYMES 25"},
            {"code": "PPE-09", "objective": "Desmantelamiento", "risk": "Obligación no reconocida o mal medida", "assertion": "Integridad / Valoración",
             "procedure": "Recalcular el valor presente de la obligación y compararlo con la provisión", "evidence": "Contratos, permisos ambientales, estimación técnica",
             "criterion": "Provisión igual al valor presente", "source": "NIC 16.16 c · NIC 37.45–47 · CINIIF 1 · Sección 21 (21.7 b)"},
        ],
        "requests": [
            req("RQ-001", "Auxiliar de propiedad, planta y equipo por activo al corte", "activos", "PPE-01", "Población a recalcular y conciliar con el mayor", content=aux),
            req("RQ-002", "Detalle de adiciones del año por documento", "adiciones", "PPE-02", "Examen de adiciones y costos por préstamos", required=False,
                content="Una fila por documento: N° de documento, código del activo, fecha, descripción, tipo, importe, activo apto (Sí/No) e intereses capitalizados."),
            req("RQ-003", "Detalle de los préstamos para la construcción del período", "prestamos", "PPE-08",
                "Separar préstamos específicos y generales y medir el capitalizable por activo", required=False,
                content="Una fila por préstamo vigente en el período: N° de préstamo o contrato, tipo (Específico o General), activo u obra financiada "
                        "(solo los específicos), descripción, importe del préstamo, tasa nominal anual, costo financiero del período realmente incurrido y, "
                        "en los específicos, los rendimientos de la inversión temporal de esos fondos. Si no hubo inversión temporal, escriba 0."),
            req("RQ-004", "Política contable de vidas útiles, residuales y métodos", None, "PPE-04", "Sustento de estimaciones", formats=("pdf", "docx"), use="soporte"),
            req("RQ-005", "Informe del perito de la revaluación", None, "PPE-06", "Sustento del valor revaluado", required=False, formats=("pdf",), use="soporte"),
            req("RQ-006", "Cálculo del importe recuperable (valor en uso o valor razonable)", None, "PPE-07", "Sustento del deterioro", required=False,
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-007", "Contratos de préstamo, tablas de amortización y mayor de rendimientos de inversiones temporales", None, "PPE-08",
                "Sustento del costo financiero incurrido, de la tasa de capitalización y de los rendimientos del párrafo 23.12", required=False,
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-008", "Estimación técnica de desmantelamiento o restauración", None, "PPE-09", "Sustento de la provisión", required=False,
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-009", "Facturas de venta y actas de baja del año", None, "PPE-05", "Sustento de las bajas", required=False, formats=("pdf",), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


def _a(id, desc, clase, uso, ci, **x):
    return {"id": id, "descripcion": desc, "clase": clase, "fecha_uso": uso, "costo_inicial": ci, "_row": 2, **x}


def _ad(id, activo, f, imp, **x):
    return {"id": id, "activo": activo, "fecha": f, "importe": imp, "_row": 2, **x}


def _pr(id, tipo, **x):
    return {"id": id, "tipo": tipo, "_row": 2, **x}


# Ejemplo de control (M19), corte 2025-12-31, año de 365 días:
# VEH-01: (40.000 − 4.000) ÷ 60 × 12 = 7.200 recalculado vs 6.000 registrado → +1.200.
# VEH-02 (baja 30-jun): 27.000 ÷ 60 × 12 × 181 ÷ 365 = 2.677,81; VNL = 30.000 − 21.600 − 2.677,81 = 5.722,19;
#   ganancia = 9.000 − 5.722,19 = 3.277,81 vs 1.500 registrada → +1.777,81.
# MAQ-01: VNL = 120.000 − 72.000 = 48.000 vs recuperable 40.000 → deterioro 8.000.
# Costos por préstamos con el anexo (NIC 23.12 y 14), OBRA-01:
#   desembolsos aptos 150.000 + 45.000 = 195.000; base ponderada (150.000 × 305 + 45.000 × 121) ÷ 365 = 140.260,27.
#   PR-01 específico: 9.000 de costo real − 1.200 de rendimientos = 7.800 (23.12).
#   Tasa de capitalización de los generales = (32.000 + 12.000) ÷ (400.000 + 100.000) = 8,80 % (23.14).
#   Proporción financiada con generales = 1 − 120.000 ÷ 195.000 = 38,4615 %; base 53.946,26 × 8,80 % = 4.747,27.
#   Capitalizable = 7.800 + 4.747,27 = 12.547,27; costos incurridos 53.000 → el tope no muerde (factor 1).
#   Capitalizado por el cliente 9.000 → ajuste +3.547,27. En PYMES no se capitaliza nada: −9.000 (Sección 25.2).
# Desmantelamiento: 50.000 ÷ 1,06^10 = 27.919,74 no reconocido; sin provisión registrada no hay descuento que
#   revertir: actualización financiera del período 0 y los 27.919,74 son cambio de estimación al costo (CINIIF 1.5 a).
# TERR-01 revaluado sin «decremento previo en resultados»: los 60.000 quedan en ORI y se avisa (NIC 16.39).
# MAQ-01 no está revaluado: los 8.000 de deterioro van íntegros a resultados (NIC 36.60-61 no aplica).
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tolerancia": 1, "tasaCapitalizacion": 8, "umbralComponente": 10,
                   "umbralRevisarComponentes": 400000, "costoDesmantelamiento": 50000, "aniosDesmantelamiento": 10,
                   "tasaDesmantelamiento": 6, "mayorCosto": 1297000, "mayorDepAcum": 253000},
    "datasets": {
        "activos": [
            _a("EDIF-01", "Edificio administrativo", "Edificios", "2015-01-01", "500000", residual="50000", vida_meses="480", metodo="Lineal",
               dep_acum_inicial="112500", dep_registrada="11250"),
            _a("TERR-01", "Terreno planta", "Terrenos", "2015-01-01", "300000", dep_registrada="0", valor_revaluado="360000"),
            _a("TERR-02", "Terreno bodega", "Terrenos", "2018-05-01", "80000", dep_registrada="0"),
            _a("VEH-01", "Camioneta 4x4", "Vehículos", "2023-07-01", "40000", residual="4000", vida_meses="60", metodo="Lineal",
               dep_acum_inicial="10800", dep_registrada="6000"),
            _a("VEH-02", "Camión de reparto", "Vehículos", "2021-01-01", "30000", residual="3000", vida_meses="60", metodo="Lineal",
               dep_acum_inicial="21600", dep_registrada="2700", fecha_baja="2025-06-30", producto_baja="9000", resultado_baja="1500"),
            _a("MAQ-01", "Línea de envasado", "Maquinaria", "2020-01-01", "120000", vida_meses="120", metodo="Lineal",
               dep_acum_inicial="60000", dep_registrada="12000", importe_recuperable="40000"),
            _a("MAQ-01-M", "Motor de la línea de envasado", "Maquinaria", "2020-01-01", "30000", elemento="MAQ-01", vida_meses="60",
               metodo="Lineal", dep_acum_inicial="30000", dep_registrada="0"),
            _a("EQC-01", "Servidores", "Equipo de cómputo", "2024-01-01", "15000", vida_meses="36", metodo="Unidades producidas",
               dep_acum_inicial="5000", dep_registrada="4000"),
            _a("OBRA-01", "Nave industrial en construcción", "Construcciones en curso", "", "0", adiciones="200000", dep_registrada="1000"),
            _a("MOB-01", "Mobiliario de oficinas", "Muebles y enseres", "2025-04-01", "0", adiciones="12000", vida_meses="120", metodo="Lineal",
               dep_registrada="904.11"),
        ],
        "adiciones": [
            _ad("AD-01", "OBRA-01", "2025-03-01", "150000", descripcion="Avance de obra 1", tipo="Capitalizable", apto="Sí", intereses="9000"),
            _ad("AD-02", "OBRA-01", "2025-09-01", "45000", descripcion="Avance de obra 2", tipo="Capitalizable", apto="Sí", intereses="0"),
            _ad("AD-03", "OBRA-01", "2025-10-15", "5000", descripcion="Cubierta provisional", tipo="Reparación", apto="No"),
            _ad("AD-04", "MOB-01", "2025-04-01", "12000", descripcion="Escritorios y sillas", tipo="Capitalizable", apto="No"),
        ],
        "prestamos": [
            _pr("PR-01", "Específico", activo="OBRA-01", descripcion="Banco del Pacífico · nave industrial", importe="120000",
                tasa="9", costo_financiero="9000", rendimientos="1200"),
            _pr("PR-02", "General", descripcion="Banco Pichincha · capital de trabajo", importe="400000", tasa="8", costo_financiero="32000"),
            _pr("PR-03", "General", descripcion="Produbanco · línea de crédito", importe="100000", tasa="12", costo_financiero="12000"),
        ],
    },
}

# Sin el anexo de préstamos la herramienta sigue funcionando con la tasa del parámetro y avisa (SIN_ANEXO_PRESTAMOS):
# AD-01: 150.000 × 8 % × 305 ÷ 365 = 10.027,40 y AD-02: 45.000 × 8 % × 121 ÷ 365 = 1.193,42; capitalizado 9.000 → +2.220,82.
_SIN_PRESTAMOS = {k: v for k, v in EJEMPLO["datasets"].items() if k != "prestamos"}

# El tope del párrafo 14 muerde: mismo anexo pero un solo préstamo general de 40.000 con 6.000 de costo (tasa 15 %).
#   Capitalizable de los generales = 53.946,26 × 15 % = 8.091,94; con el específico 7.800 → 15.891,94 antes del tope.
#   Costos por préstamos incurridos en el período = 9.000 + 6.000 = 15.000 → factor 15.000 ÷ 15.891,94 = 0,943876…
#   Capitalizable del período = 15.000,00 (exceso no capitalizable 891,94); capitalizado 9.000 → ajuste +6.000,00.
_PRESTAMOS_TOPE = [
    _pr("PR-01", "Específico", activo="OBRA-01", descripcion="Banco del Pacífico · nave industrial", importe="120000",
        tasa="9", costo_financiero="9000", rendimientos="1200"),
    _pr("PR-02", "General", descripcion="Banco Pichincha · capital de trabajo", importe="40000", tasa="15", costo_financiero="6000"),
]
_TOPE = {**EJEMPLO["datasets"], "prestamos": _PRESTAMOS_TOPE}

# Anexo incompleto: el específico sin rendimientos y el general sin importe → los importes quedan vacíos (M22) y
# el tope no se puede comprobar; se emiten PRESTAMO_SIN_RENDIMIENTOS, PRESTAMO_GENERAL_INCOMPLETO y TOPE_NO_VERIFICABLE.
_MIN = {"activos": [_a("V-1", "Auto", "Vehículos", "2024-01-01", "10000", vida_meses="60", dep_registrada="2000")],
        "prestamos": [_pr("PR-X", "Específico", activo="V-1", importe="5000", tasa="9", costo_financiero="400"),
                      _pr("PR-Y", "General", descripcion="Línea sin importe informado", costo_financiero="800")]}

# Escenario de activos revaluados (NIC 16.39 · NIC 36.60-61 · CINIIF 1.5 y 1.8), recalculado a mano:
# EDIF-R: dep. 200.000 ÷ 480 × 12 = 5.000 (= registrada); acum. 25.000; VNL 175.000. Revaluado 185.000 → +10.000
#   con decremento previo en resultados 12.000 → los 10.000 van a resultados (16.39) y 0 a ORI. Deterioro:
#   185.000 − 170.000 = 15.000 contra el superávit disponible 30.000 + 0 → 15.000 a ORI y 0 a resultados (36.60-61).
# MAQ-R: dep. 100.000 ÷ 120 × 12 = 10.000 (= registrada); acum. 60.000; VNL 40.000. Revaluado 42.000 → +2.000 sin
#   decremento previo informado → todo a ORI y aviso. Deterioro 42.000 − 35.000 = 7.000 sin superávit informado →
#   no se reparte, queda en resultados y se avisa.
# Desmantelamiento: VP 27.919,74; registrada al cierre 26.500 → ajuste total 1.419,74; actualización del período
#   26.000 × 6 % = 1.560 (costo financiero); cambio de estimación 1.419,74 − 1.560 = −140,26 (contra el costo).
# Efecto neto en resultados = −0 − 7.000 + 0 + 0 + 10.000 − 1.560 = 1.440,00.
_REVALUADOS = {"activos": [
    _a("EDIF-R", "Edificio revaluado con deterioro", "Edificios", "2018-01-01", "200000", vida_meses="480", metodo="Lineal",
       dep_acum_inicial="20000", dep_registrada="5000", valor_revaluado="185000", superavit_previo="30000",
       decremento_previo="12000", importe_recuperable="170000"),
    _a("MAQ-R", "Máquina revaluada sin superávit informado", "Maquinaria", "2020-01-01", "100000", vida_meses="120", metodo="Lineal",
       dep_acum_inicial="50000", dep_registrada="10000", valor_revaluado="42000", importe_recuperable="35000"),
]}
PARAMETROS_REVALUADOS = {"_marco": MARCO_COMPLETAS, "tolerancia": 1, "costoDesmantelamiento": 50000, "aniosDesmantelamiento": 10,
                         "tasaDesmantelamiento": 6, "provisionDesmantelamiento": 26500, "provisionDesmantelamientoInicial": 26000,
                         "mayorCosto": 300000, "mayorDepAcum": 85000}
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025"}, EJEMPLO["corte"]),
    ("sin_anexo_prestamos", _SIN_PRESTAMOS, EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("tope_costos_prestamos", _TOPE, EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("revaluados_desmantelamiento", _REVALUADOS, PARAMETROS_REVALUADOS, "2025-12-31"),
    ("minimo", _MIN, {}, "2025-12-31"),
]
