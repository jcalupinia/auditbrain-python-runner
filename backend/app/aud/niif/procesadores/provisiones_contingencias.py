"""Provisiones y contingencias: obligación presente, probabilidad, mejor estimación, cartas de abogados,
garantías, litigios, contratos onerosos, desmantelamiento, valor presente, reversión del descuento,
diferencia con libros y pasivos/activos contingentes a revelar.

Norma leída (texto oficial en español, Reglamento (UE) 2023/1803, NIC 37):
- 14: se reconoce una provisión solo si hay obligación presente (legal o implícita) por un suceso pasado,
  salida de recursos probable y estimación fiable; si no, ninguna provisión.
- 23: probable = «mayor probabilidad de que se produzca que de que no»; si no es probable, pasivo contingente
  salvo que la salida sea remota. 24: obligaciones similares (garantías) se evalúan como clase.
- 27–28: el pasivo contingente no se reconoce; se revela (párr. 86) salvo remota. 31, 33–34: el activo contingente
  no se reconoce (salvo realización prácticamente cierta) y se revela si la entrada es probable (párr. 89).
- 36–37: mejor estimación al cierre. 39: población grande → valor esperado; rango continuo igual de probable →
  valor intermedio. 40: obligación aislada → desenlace individual más probable (considerando los demás).
- 45–47: valor actual cuando el efecto del valor temporal es importante; tasa antes de impuestos.
- 59: revisión al cierre; 60: el aumento por el paso del tiempo es coste por intereses.
- 10 y 66: el contrato es oneroso cuando los costes inevitables exceden los beneficios económicos que se esperan
  recibir; 68: los costes inevitables son los menores costes netos por resolver el contrato = el menor entre el coste
  de cumplir sus cláusulas (neto de los beneficios esperados) y las compensaciones o multas por incumplirlo;
  69: antes, el deterioro de los activos del contrato (NIC 36).
- NIC 10.9 a): el litigio resuelto después del cierre que confirma la obligación ajusta la provisión.
- CINIIF 1: los cambios en el pasivo por desmantelamiento se suman o restan del costo del activo.
PYMES (leído en 2015 (ES) y 2025 (EN): misma numeración para los párrafos citados): 21.4, 21.7 a) y b), 21.7 (valor
presente, tasa antes de impuestos), 21.11 (reversión del descuento como costo financiero), 21.12, 21.13, 21.15,
21.16, 21A.2 (onerosos) y 21A.4 (garantías). El cálculo es el mismo en NIIF completas y PYMES: no se enruta.

Cálculo por partida:
1. Clasificación: obligación presente Sí + probable (o prácticamente cierta) → reconocer; posible, u obligación
   No con salida probable/posible → pasivo contingente (revelar); remota → nada. Activo contingente: solo se
   reconoce si es prácticamente cierto; si es probable, se revela.
2. Mejor estimación (sin descontar), en este orden: hecho posterior que confirma (NIC 10.9 a) → oneroso =
   mín(máx(costo de cumplir − beneficios esperados, 0), penalización) → garantías = Σ unidades × % reclamos × costo medio → escenarios
   (valor esperado Σ importe × prob ÷ Σ prob, o el más probable si así se indica) → punto medio del rango →
   importe de la carta del abogado → estimación de la gerencia.
3. Valor presente = estimación ÷ (1 + tasa)^plazo cuando el plazo supera el parámetro (tasa de la partida o
   la tasa por defecto); reversión del descuento del período = saldo inicial × tasa.
4. Provisión requerida (reconocer = valor presente; contingente/remota = 0); ajuste = requerida − libros.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja,
    m, norm, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "provisiones_contingencias 1.0"
RUBRO = "PROVISIONES"

_PROV = [
    campo("id", "Código de la provisión o contingencia", alias=("codigo", "código", "id", "referencia", "caso"), ejemplo="LIT-01"),
    campo("descripcion", "Descripción", alias=("detalle", "concepto", "descripcion del caso", "nombre"), ejemplo="Demanda laboral ex gerente"),
    campo("tipo", "Tipo (Litigio/Garantía/Oneroso/Desmantelamiento/Reestructuración/Otro/Activo contingente)",
          alias=("tipo", "clase", "naturaleza", "categoria"), ejemplo="Litigio"),
    campo("obligacion_presente", "¿Existe obligación presente? (Sí/No)", requerido=False,
          alias=("obligacion presente", "obligación presente", "obligacion"), ejemplo="Sí"),
    campo("probabilidad_abogado", "Probabilidad según el abogado (Probable/Posible/Remota)", requerido=False,
          alias=("probabilidad abogado", "evaluacion abogado", "opinion abogado"), ejemplo="Probable"),
    campo("probabilidad_gerencia", "Probabilidad según la gerencia (Probable/Posible/Remota)", requerido=False,
          alias=("probabilidad gerencia", "evaluacion gerencia", "probabilidad"), ejemplo="Probable"),
    campo("importe_abogado", "Importe según la carta del abogado", "number", False, ("importe abogado", "monto abogado", "valor carta"), "120000"),
    campo("importe_gerencia", "Estimación de la gerencia (sin descontar)", "number", False,
          ("estimacion gerencia", "importe estimado", "monto estimado", "costo estimado"), ""),
    campo("importe_minimo", "Importe mínimo del rango", "number", False, ("minimo", "importe minimo", "rango minimo"), ""),
    campo("importe_maximo", "Importe máximo del rango", "number", False, ("maximo", "importe maximo", "rango maximo"), ""),
    campo("importe_1", "Escenario 1: importe", "number", False, ("importe 1", "escenario 1"), "150000"),
    campo("prob_1", "Escenario 1: probabilidad (%)", "number", False, ("prob 1", "probabilidad 1"), "60"),
    campo("importe_2", "Escenario 2: importe", "number", False, ("importe 2", "escenario 2"), "80000"),
    campo("prob_2", "Escenario 2: probabilidad (%)", "number", False, ("prob 2", "probabilidad 2"), "30"),
    campo("importe_3", "Escenario 3: importe", "number", False, ("importe 3", "escenario 3"), "0"),
    campo("prob_3", "Escenario 3: probabilidad (%)", "number", False, ("prob 3", "probabilidad 3"), "10"),
    campo("metodo", "Método para escenarios (Valor esperado/Más probable)", requerido=False, alias=("metodo", "método", "base de medicion"), ejemplo=""),
    campo("costo_cumplir", "Oneroso: costo de cumplir", "number", False, ("costo de cumplir", "costo cumplir"), ""),
    campo("penalizacion", "Oneroso: penalización por incumplir", "number", False, ("penalizacion", "penalidad", "multa"), ""),
    campo("beneficios_contrato", "Oneroso: beneficios económicos esperados del contrato", "number", False,
          ("beneficios esperados", "beneficios economicos", "beneficios del contrato", "ingresos esperados del contrato"), ""),
    campo("importe_posterior", "Importe fijado después del corte (sentencia o acuerdo)", "number", False,
          ("importe posterior", "sentencia", "hecho posterior", "liquidacion posterior"), ""),
    campo("plazo_anios", "Plazo esperado de salida (años)", "number", False, ("plazo", "plazo anios", "años", "anios"), "1"),
    campo("tasa_descuento", "Tasa de descuento antes de impuestos (%)", "number", False, ("tasa", "tasa descuento", "tasa de descuento"), ""),
    campo("saldo_libros", "Saldo registrado en libros al corte", "number", alias=("saldo libros", "saldo", "saldo contable", "registrado"), ejemplo="100000"),
    campo("saldo_inicial", "Saldo inicial del período", "number", False, ("saldo inicial", "saldo anterior"), ""),
    campo("reversion_registrada", "Reversión del descuento registrada en el período", "number", False,
          ("reversion registrada", "gasto financiero registrado", "actualizacion financiera"), ""),
    campo("respuesta_abogado", "¿Se recibió respuesta del abogado? (Sí/No)", requerido=False, alias=("respuesta abogado", "carta recibida"), ejemplo="Sí"),
    campo("fecha_carta", "Fecha de la carta del abogado", "date", False, ("fecha carta", "fecha de la carta"), "2026-02-10"),
    campo("revelado", "¿Revelado en notas? (Sí/No)", requerido=False, alias=("revelado", "revelacion", "en notas"), ejemplo="No"),
]
_GAR = [
    campo("id", "Código de la línea de garantía", alias=("codigo", "código", "linea", "producto"), ejemplo="GA-A"),
    campo("provision", "Código de la provisión a la que pertenece", alias=("provision", "provisión", "codigo provision"), ejemplo="GAR-01"),
    campo("descripcion", "Descripción", requerido=False, alias=("detalle", "producto", "descripcion"), ejemplo="Refrigeradoras"),
    campo("unidades", "Ventas con garantía vigente al corte (unidades)", "number", alias=("unidades", "ventas", "ventas con garantia"), ejemplo="12000"),
    campo("pct_reclamos", "% de reclamos histórico", "number", alias=("% reclamos", "porcentaje reclamos", "tasa reclamos"), ejemplo="3"),
    campo("costo_medio", "Costo medio por reclamo", "number", alias=("costo medio", "costo por reclamo", "costo promedio"), ejemplo="85"),
]
CAMPOS = {"provisiones": _PROV, "garantias": _GAR}
TIPOS = {"provisiones": "provisiones", "garantias": "garantias"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "provisiones"
CONTROL = "saldo_libros"
TOTAL_EJEMPLO = "provisionRequerida"

PARAMETROS = {"tasaDescuento": None, "plazoDescuento": 1, "materialidad": None, "tolerancia": 1, "mayorProvisiones": None}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "tasaDescuento": "Tasa de descuento antes de impuestos por defecto (%)",
    "plazoDescuento": "Descontar cuando el plazo de salida supere (años)",
    "materialidad": "Materialidad (importe)",
    "tolerancia": "Tolerancia de diferencias (importe)",
    "mayorProvisiones": "Mayor: provisiones al corte",
}

_ORDEN = [c["key"] for c in _PROV]
_NUM = [c["key"] for c in _PROV if c["type"] == "number"]
_NUM_G = ("unidades", "pct_reclamos", "costo_medio")

TIPOS_PROV = {norm(x): x for x in ("Litigio", "Garantía", "Oneroso", "Desmantelamiento", "Reestructuración", "Otro", "Activo contingente")}
TIPOS_PROV.update({"contratooneroso": "Oneroso", "garantias": "Garantía", "juicio": "Litigio", "demanda": "Litigio",
                   "litigios": "Litigio", "restauracion": "Desmantelamiento", "activo": "Activo contingente"})
_PROBS = {norm(x): x for x in ("Prácticamente cierta", "Probable", "Posible", "Remota")}
_PROBS.update({"practicamentecierto": "Prácticamente cierta", "remoto": "Remota", "posibles": "Posible"})
_SINO = {"si": "Sí", "s": "Sí", "no": "No", "n": "No"}
_METODOS = {"valoresperado": "Valor esperado", "masprobable": "Más probable", "resultadomasprobable": "Más probable",
            "desenlacemasprobable": "Más probable"}


def _col(i: int) -> str:
    return chr(65 + i) if i < 26 else "A" + chr(65 + i - 26)


L = {k: _col(i) for i, k in enumerate(_ORDEN)}


def _t(v) -> str:
    return str(v if v is not None else "").strip()


def _opc(v):
    return a_num(v) if _t(v) else None


def _p(p, k):
    v = p.get(k)
    return None if v is None or _t(v) == "" else float(a_num(v))


def _canon(tabla: dict, v):
    """Texto de opción normalizado: '' si vacío, None si no se reconoce."""
    if not _t(v):
        return ""
    return tabla.get(norm(v))


_OPCIONES = {"tipo": TIPOS_PROV, "obligacion_presente": _SINO, "probabilidad_abogado": _PROBS,
             "probabilidad_gerencia": _PROBS, "respuesta_abogado": _SINO, "revelado": _SINO, "metodo": _METODOS}


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    v = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        fila = f.get("_row")
        err = lambda k, msg: v["errors"].append({"row": fila, "field": k, "message": msg})
        if tipo == "provisiones":
            for k, tabla in _OPCIONES.items():
                if _canon(tabla, f.get(k)) is None:
                    err(k, f"Valor no reconocido: «{_t(f.get(k))}».")
            for k in _NUM:
                x = _opc(f.get(k))
                if x is not None and x < 0:
                    err(k, "Use importes positivos.")
            for i in (1, 2, 3):
                a, b = _opc(f.get(f"importe_{i}")), _opc(f.get(f"prob_{i}"))
                if (a is None) != (b is None):
                    err(f"prob_{i}", f"Escenario {i}: indique importe y probabilidad juntos.")
                if b is not None and b > 100:
                    err(f"prob_{i}", "Probabilidad entre 0 y 100.")
            t = _opc(f.get("tasa_descuento"))
            if t is not None and t > 100:
                err("tasa_descuento", "Tasa entre 0 y 100.")
            lo, hi = _opc(f.get("importe_minimo")), _opc(f.get("importe_maximo"))
            if lo is not None and hi is not None and lo > hi:
                err("importe_maximo", "El máximo del rango debe ser mayor o igual al mínimo.")
        else:
            for k in _NUM_G:
                x = _opc(f.get(k))
                if x is not None and x < 0:
                    err(k, "Use valores positivos.")
            x = _opc(f.get("pct_reclamos"))
            if x is not None and x > 100:
                err("pct_reclamos", "Porcentaje entre 0 y 100.")
    v["ok"] = not v["errors"]
    return v


# --- cálculo -----------------------------------------------------------------

def _clasificar(tipo, obl, prob) -> str:
    """Misma lógica que la columna G de 05_Obligacion_prob."""
    if tipo == "Activo contingente":
        if prob == "":
            return "Sin evaluación"
        return {"Prácticamente cierta": "Activo reconocible", "Probable": "Activo contingente: revelar"}.get(prob, "Activo contingente: no revelar")
    if prob == "" or obl == "":
        return "Sin evaluación"
    if prob == "Remota":
        return "Remota: no revelar"
    if obl == "Sí" and prob in ("Probable", "Prácticamente cierta"):
        return "Reconocer provisión"
    return "Pasivo contingente: revelar"


def _contrapartida(tipo, clasif) -> str:
    if tipo == "Activo contingente":
        return "Otros ingresos / cuenta por cobrar (NIC 37.33)"
    if tipo == "Desmantelamiento":
        return "Costo del activo (NIC 16.16 c, 16.18; CINIIF 1)"
    return "Gasto del período (provisión)" if clasif == "Reconocer provisión" else "Reversión contra resultados (NIC 37.59)"


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    pymes = es_pymes(p)
    tdef, plazo_min = _p(p, "tasaDescuento"), _p(p, "plazoDescuento")
    tol, mat, mayor = _p(p, "tolerancia") or 0.0, _p(p, "materialidad"), _p(p, "mayorProvisiones")
    if tdef is not None and not 0 <= tdef <= 100:
        raise ValueError("La tasa de descuento por defecto debe ser un porcentaje entre 0 y 100.")
    if plazo_min is None or plazo_min < 0:
        raise ValueError("Indique desde qué plazo (años) se descuenta; cero o más.")

    # Garantías (10_Garantias): provisión por línea = unidades × % reclamos ÷ 100 × costo medio.
    gars = []
    for f in datasets.get("garantias") or []:
        if not _t(f.get("id")):
            continue
        g = {"id": _t(f.get("id")), "prov": _t(f.get("provision")), "desc": _t(f.get("descripcion")),
             "u": _opc(f.get("unidades")), "pct": _opc(f.get("pct_reclamos")), "costo": _opc(f.get("costo_medio")), "_row": f.get("_row")}
        if g["u"] is None or g["pct"] is None or g["costo"] is None:
            raise ValueError(f"Garantía {g['id']}: indique unidades, % de reclamos y costo medio.")
        g["calc"] = g["u"] * g["pct"] / 100 * g["costo"]
        gars.append(g)

    filas_p = []
    for f in datasets.get("provisiones") or []:
        if not _t(f.get("id")):
            continue
        r = {"id": _t(f.get("id")), "descripcion": _t(f.get("descripcion")), "_row": f.get("_row")}
        for k, tabla in _OPCIONES.items():
            c = _canon(tabla, f.get(k))
            if c is None:
                raise ValueError(f"{r['id']}: valor no reconocido en {k}: «{_t(f.get(k))}».")
            r[k] = c
        for k in _NUM:
            r[k] = _opc(f.get(k))
        r["fecha_carta"] = fecha(f.get("fecha_carta"))
        if r["tipo"] == "":
            raise ValueError(f"{r['id']}: indique el tipo (litigio, garantía, oneroso, desmantelamiento, reestructuración, otro o activo contingente).")
        if r["saldo_libros"] is None:
            raise ValueError(f"{r['id']}: indique el saldo registrado en libros al corte (0 si no hay registro).")
        if min(r[k] for k in _NUM if r[k] is not None) < 0:
            raise ValueError(f"{r['id']}: los importes deben ser positivos.")
        filas_p.append(r)
    if not filas_p:
        raise ValueError("Cargue el detalle de provisiones, litigios y contingencias con su saldo en libros.")
    ids = {r["id"].lower() for r in filas_p}

    for r in filas_p:
        activo = r["tipo"] == "Activo contingente"
        r["naturaleza"] = "Activo" if activo else "Pasivo"
        # 05 · obligación y probabilidad.
        r["prob"] = r["probabilidad_abogado"] or r["probabilidad_gerencia"]
        r["discrepancia"] = "Discrepancia" if (r["probabilidad_abogado"] and r["probabilidad_gerencia"]
                                                and r["probabilidad_abogado"] != r["probabilidad_gerencia"]) else ""
        r["clasif"] = _clasificar(r["tipo"], r["obligacion_presente"], r["prob"])
        # 06 · mejor estimación.
        r["est_post"] = r["importe_posterior"]
        # Oneroso (NIC 37.10, 66–68; PYMES 21A.2): costo neto de cumplir = costo de cumplir − beneficios esperados
        # (mínimo 0); costos inevitables = el menor entre ese costo neto y la penalización por incumplir.
        r["costo_neto"] = None if r["costo_cumplir"] is None else max(r["costo_cumplir"] - (r["beneficios_contrato"] or 0), 0)
        cands = [x for x in (r["costo_neto"], r["penalizacion"]) if x is not None]
        r["est_oner"] = min(cands) if r["tipo"] == "Oneroso" and cands else None
        r["sin_beneficios"] = r["tipo"] == "Oneroso" and r["costo_cumplir"] is not None and r["beneficios_contrato"] is None
        ligadas = [g for g in gars if g["prov"].lower() == r["id"].lower()]
        r["est_gar"] = sum(g["calc"] for g in ligadas) if r["tipo"] == "Garantía" and ligadas else None
        i1, p1, i2, p2, i3, p3 = (r[k] or 0.0 for k in ("importe_1", "prob_1", "importe_2", "prob_2", "importe_3", "prob_3"))
        r["sprob"] = p1 + p2 + p3
        r["est_ve"] = None if r["sprob"] == 0 else (i1 * p1 + i2 * p2 + i3 * p3) / (p1 + p2 + p3)
        r["est_mp"] = None if r["sprob"] == 0 else (r["importe_1"] if p1 >= p2 and p1 >= p3 else (r["importe_2"] if p2 >= p3 else r["importe_3"]))
        r["est_mid"] = None if r["importe_minimo"] is None or r["importe_maximo"] is None else (r["importe_minimo"] + r["importe_maximo"]) / 2
        mas_prob = r["metodo"] == "Más probable"
        opciones = [
            (r["est_post"], "Hecho posterior (NIC 10.9 a)"), (r["est_oner"], "Oneroso: menor costo (37.68)"),
            (r["est_gar"], "Garantías: valor esperado (37.39)"),
            ((r["est_mp"] if mas_prob else r["est_ve"]) if r["sprob"] > 0 else None,
             "Desenlace más probable (37.40)" if mas_prob else "Valor esperado (37.39)"),
            (r["est_mid"], "Punto medio del rango (37.39)"), (r["importe_abogado"], "Carta del abogado"),
            (r["importe_gerencia"], "Estimación de la gerencia"),
        ]
        r["est"], r["base"] = next(((v, b) for v, b in opciones if v is not None), (None, "Sin estimación"))
        # 07 · valor presente.
        r["tasa"] = r["tasa_descuento"] if r["tasa_descuento"] is not None else tdef
        r["descontar"] = "Sí" if r["plazo_anios"] is not None and r["plazo_anios"] > plazo_min else "No"
        r["factor"] = 1 if r["descontar"] == "No" else (None if r["tasa"] is None else 1 / (1 + r["tasa"] / 100) ** r["plazo_anios"])
        r["vp"] = None if r["est"] is None or r["factor"] is None else r["est"] * r["factor"]
        r["descuento"] = None if r["vp"] is None else r["est"] - r["vp"]
        # 08 · reversión del descuento (actualización financiera).
        r["rev_calc"] = (r["saldo_inicial"] * r["tasa"] / 100
                         if r["saldo_inicial"] is not None and r["tasa"] is not None and r["descontar"] == "Sí" else None)
        r["rev_dif"] = None if r["rev_calc"] is None or r["reversion_registrada"] is None else r["rev_calc"] - r["reversion_registrada"]
        # 13 · reconocimiento.
        if r["clasif"] == "Sin evaluación":
            r["requerida"] = None
        elif r["clasif"] in ("Reconocer provisión", "Activo reconocible"):
            r["requerida"] = r["vp"]
        else:
            r["requerida"] = 0.0
        r["dif"] = None if r["requerida"] is None else r["requerida"] - r["saldo_libros"]
        r["contrapartida"] = _contrapartida(r["tipo"], r["clasif"])
        r["dias_carta"] = None if r["fecha_carta"] is None else (r["fecha_carta"] - corte_a).days
        r["eval_lit"] = ("Sin respuesta: limitación (NIA 501)" if r["respuesta_abogado"] != "Sí" else
                         ("Carta anterior al corte" if r["dias_carta"] is not None and r["dias_carta"] < 0 else "Respuesta recibida"))
        if "contingente" in r["clasif"]:
            if r["clasif"] == "Activo contingente: no revelar":
                r["eval_cont"] = "No revelar (no probable); no reconocer (37.31)"
            elif r["revelado"] == "Sí":
                r["eval_cont"] = "Revelado (NIC 37.86)" if not activo else "Revelado (NIC 37.89)"
            else:
                r["eval_cont"] = "Revelar: NIC 37.86 · PYMES 21.15" if not activo else "Revelar: NIC 37.89 · PYMES 21.16"

    pas = [r for r in filas_p if r["naturaleza"] == "Pasivo"]
    act = [r for r in filas_p if r["naturaleza"] == "Activo"]
    sn = lambda it, k: sum(r[k] for r in it if r[k] is not None)
    cont = [r for r in pas if r["clasif"] == "Pasivo contingente: revelar"]
    k = {
        "librosProvisiones": sn(pas, "saldo_libros"), "provisionRequerida": sn(pas, "requerida"), "ajusteProvisiones": sn(pas, "dif"),
        "descuento": sn(filas_p, "descuento"), "reversionCalculada": sn(filas_p, "rev_calc"),
        "reversionRegistrada": sn(filas_p, "reversion_registrada"), "difReversion": sn(filas_p, "rev_dif"),
        "garantiasCalculadas": sum(g["calc"] for g in gars), "pasivosContingentes": sn(cont, "vp"),
        "contingentesSinRevelar": sn([r for r in cont if r["revelado"] != "Sí"], "vp"),
        "activoContingenteReconocido": sn([r for r in act if r["clasif"] != "Activo reconocible"], "saldo_libros"),
    }
    k["ajusteActivoContingente"] = -k["activoContingenteReconocido"]
    k["mayorProvisiones"] = mayor
    k["difMayor"] = None if mayor is None else k["librosProvisiones"] - mayor
    k["materialidad"] = mat
    k["superaMaterialidad"] = "" if mat is None else ("Sí" if abs(k["ajusteProvisiones"]) > mat else "No")

    # Problemas.
    pr = []
    for r in filas_p:
        i, lib, cl = r["id"], r["saldo_libros"], r["clasif"]
        if cl == "Sin evaluación":
            pr.append(problema("SIN_EVALUACION", f"{i} ({r['descripcion']}): falta la probabilidad o la existencia de obligación presente; "
                               "no se puede concluir sobre su reconocimiento (NIC 37.14–16, 23; PYMES 21.4).", lib))
        if r["discrepancia"]:
            pr.append(problema("DISCREPANCIA_PROBABILIDAD", f"{i}: el abogado evalúa «{r['probabilidad_abogado']}» y la gerencia «{r['probabilidad_gerencia']}»; "
                               "se usó la del abogado. Discuta la diferencia con la gerencia (NIA 501, NIA 540).", 0))
        if r["sprob"] > 0 and abs(r["sprob"] - 100) > 0.01:
            pr.append(problema("PROBABILIDADES_NO_SUMAN_100", f"{i}: las probabilidades de los escenarios suman {r['sprob']:g} %; el valor "
                               "esperado se calculó sobre esa suma. Pida escenarios completos.", 0))
        if r["sin_beneficios"]:
            pr.append(problema("ONEROSO_SIN_BENEFICIOS", f"{i} ({r['descripcion']}): contrato oneroso sin los beneficios económicos que se esperan "
                               f"recibir; se usó el costo de cumplir completo {m(r['costo_cumplir'])}, sin restarlos: la provisión puede quedar "
                               "sobrestimada. Pida los beneficios esperados del contrato (NIC 37.10, 66–68; PYMES 21A.2).", r["costo_cumplir"]))
        if r["tipo"] == "Litigio":
            if r["respuesta_abogado"] != "Sí":
                pr.append(problema("SIN_RESPUESTA_ABOGADO", f"{i}: no hay respuesta del abogado a la carta de confirmación; posible limitación al "
                                   "alcance (NIA 501 párr. 10–11; NIA 705).", max(lib, r["vp"] or 0)))
            elif r["dias_carta"] is not None and r["dias_carta"] < 0:
                pr.append(problema("CARTA_ANTERIOR_AL_CORTE", f"{i}: la carta del abogado es del {r['fecha_carta'].isoformat()}, anterior al corte; "
                                   "pida una actualización cercana a la fecha del informe (NIA 501, NIA 560).", 0))
        if r["naturaleza"] == "Activo":
            if lib > tol and cl != "Activo reconocible":
                pr.append(problema("ACTIVO_CONTINGENTE_RECONOCIDO", f"{i} ({r['descripcion']}): activo contingente registrado por {m(lib)} sin que su "
                                   "realización sea prácticamente cierta; revertir (NIC 37.31, 33; PYMES 21.13).", lib))
            if cl == "Activo contingente: revelar" and r["revelado"] != "Sí":
                pr.append(problema("ACTIVO_CONTINGENTE_SIN_REVELAR", f"{i}: entrada probable sin revelación en notas (NIC 37.89; PYMES 21.16).", r["vp"] or 0))
            continue
        if cl == "Reconocer provisión":
            if r["est"] is None:
                pr.append(problema("SIN_ESTIMACION", f"{i}: obligación probable sin datos para estimarla (escenarios, rango, carta o estimación); "
                                   "pida la estimación (NIC 37.25–26, 36; NIA 540).", lib))
            elif r["vp"] is None:
                pr.append(problema("DESCUENTO_SIN_TASA", f"{i}: plazo de {r['plazo_anios']:g} años sin tasa de descuento; indique la tasa antes de impuestos "
                                   "(NIC 37.45–47; PYMES 21.7).", r["est"]))
            elif lib <= tol and r["requerida"] > tol:
                cod = "ONEROSO_NO_PROVISIONADO" if r["tipo"] == "Oneroso" else "PROVISION_NO_REGISTRADA"
                extra = (" Costos inevitables = menor entre el costo neto de cumplir (costo − beneficios esperados) y la penalización "
                         "(NIC 37.10, 66–68; PYMES 21A.2).") if r["tipo"] == "Oneroso" else ""
                pr.append(problema(cod, f"{i} ({r['descripcion']}): obligación probable no registrada; provisión requerida {m(r['requerida'])} "
                                   f"({r['base']}).{extra}", r["requerida"]))
            elif abs(r["dif"]) > tol:
                pr.append(problema("DIFERENCIA_PROVISION", f"{i}: provisión requerida {m(r['requerida'])} ({r['base']}) ≠ libros {m(lib)}; "
                                   f"ajuste contra {r['contrapartida'].lower()}.", r["dif"]))
            if r["importe_abogado"] is not None and abs(lib - r["importe_abogado"]) > tol:
                pr.append(problema("DIFERENCIA_CARTA_ABOGADO", f"{i}: libros {m(lib)} ≠ importe de la carta del abogado {m(r['importe_abogado'])} (NIA 501).",
                                   lib - r["importe_abogado"]))
        elif lib > tol:
            if r["obligacion_presente"] == "No":
                pr.append(problema("PROVISION_SIN_OBLIGACION", f"{i}: provisión registrada por {m(lib)} sin obligación presente; revertir y evaluar "
                                   "revelación (NIC 37.14, 59; PYMES 21.4).", lib))
            else:
                pr.append(problema("PROVISION_POSIBLE_O_REMOTA", f"{i}: provisión registrada por {m(lib)} con salida «{r['prob']}» (no probable); "
                                   "revertir (NIC 37.14, 23, 59; PYMES 21.4).", lib))
        if cl == "Pasivo contingente: revelar" and r["revelado"] != "Sí":
            pr.append(problema("CONTINGENCIA_SIN_REVELAR", f"{i} ({r['descripcion']}): pasivo contingente «{r['prob']}» sin revelación en notas "
                               "(NIC 37.28, 86; PYMES 21.15).", r["vp"] or 0))
        if (r["descontar"] == "Sí" and r["vp"] is not None and lib > tol and abs(lib - r["est"]) <= tol and r["descuento"] > tol):
            pr.append(problema("DESCUENTO_NO_APLICADO", f"{i}: libros {m(lib)} = importe sin descontar a {r['plazo_anios']:g} años; valor presente "
                               f"{m(r['vp'])} a {r['tasa']:g} % (NIC 37.45–47; PYMES 21.7).", r["descuento"]))
        if r["rev_calc"] is not None and r["reversion_registrada"] is None and r["rev_calc"] > tol:
            pr.append(problema("REVERSION_NO_REGISTRADA", f"{i}: reversión del descuento del período {m(r['rev_calc'])} no registrada como costo "
                               "financiero (NIC 37.60; CINIIF 1.8 en desmantelamiento; PYMES 21.11).", r["rev_calc"]))
        elif r["rev_dif"] is not None and abs(r["rev_dif"]) > tol:
            pr.append(problema("REVERSION_DIFERENCIA", f"{i}: reversión del descuento calculada {m(r['rev_calc'])} ≠ registrada "
                               f"{m(r['reversion_registrada'])}: reclasificar a costo financiero (NIC 37.60; CINIIF 1.8 en desmantelamiento; PYMES 21.11).", r["rev_dif"]))
    for g in gars:
        if g["prov"].lower() not in ids:
            pr.append(problema("GARANTIA_SIN_PROVISION", f"Garantía {g['id']} ({g['desc']}): {m(g['calc'])} estimados sin provisión «{g['prov']}» "
                               "en el detalle (NIC 37.24; PYMES 21A.4).", g["calc"]))
    if mayor is None:
        pr.append(problema("SIN_MAYOR", "Ingrese el saldo de provisiones según el mayor para conciliar el detalle.", 0))
    elif abs(k["difMayor"]) > tol:
        pr.append(problema("CONCILIACION_MAYOR", f"Provisiones del detalle {m(k['librosProvisiones'])} ≠ mayor {m(mayor)}.", k["difMayor"]))
    if k["superaMaterialidad"] == "Sí":
        pr.append(problema("AJUSTE_SUPERA_MATERIALIDAD", f"El ajuste neto de provisiones {m(k['ajusteProvisiones'])} supera la materialidad {m(mat)}.",
                           k["ajusteProvisiones"]))

    totales, etiquetas = {}, {}
    for key, lab in (
        ("librosProvisiones", "Provisiones registradas en libros"), ("provisionRequerida", "Provisión requerida (NIC 37 · Secc. 21)"),
        ("ajusteProvisiones", "Ajuste propuesto (requerida − libros)"), ("descuento", "Efecto del descuento a valor presente"),
        ("reversionCalculada", "Reversión del descuento calculada"), ("reversionRegistrada", "Reversión del descuento registrada"),
        ("difReversion", "Reversión: calculada − registrada (reclasificación)"), ("garantiasCalculadas", "Garantías calculadas"),
        ("pasivosContingentes", "Pasivos contingentes a revelar (efecto estimado)"), ("contingentesSinRevelar", "Pasivos contingentes sin revelar"),
        ("activoContingenteReconocido", "Activo contingente reconocido indebidamente"), ("ajusteActivoContingente", "Ajuste del activo contingente"),
        ("difMayor", "Diferencia detalle − mayor"),
    ):
        if k[key] is not None:
            totales[key], etiquetas[key] = r2(k[key]), lab

    filas = [{"id": r["id"], "descripcion": r["descripcion"], "tipo": r["tipo"], "clasificacion": r["clasif"], "base": r["base"],
              "mejorEstimacion": "" if r["est"] is None else r2(r["est"]), "valorPresente": "" if r["vp"] is None else r2(r["vp"]),
              "requerida": "" if r["requerida"] is None else r2(r["requerida"]), "libros": r2(r["saldo_libros"]),
              "diferencia": "" if r["dif"] is None else r2(r["dif"]), "_row": r["_row"]} for r in filas_p]
    limpia = lambda it: [{kk: (v.isoformat() if hasattr(v, "isoformat") else v) for kk, v in x.items()} for x in it]
    detalle = {"corte": corte_a.isoformat(), "marco": MARCO_PYMES if pymes else MARCO_COMPLETAS, "edicion": edicion_pymes(p) if pymes else "",
               "provisiones": limpia(filas_p), "garantias": limpia(gars), "kpi": k, "parametros": p}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "ajusteProvisiones",
            "exceptions": pr, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Provisiones", "Provisiones y contingencias (datos del cliente)"),
    ("04_Garantias", "Garantías (datos del cliente)"), ("05_Obligacion_prob", "Obligación presente y probabilidad"),
    ("06_Mejor_estimacion", "Mejor estimación"), ("07_Valor_presente", "Valor presente (descuento)"),
    ("08_Reversion_descuento", "Actualización financiera (reversión del descuento)"), ("09_Litigios_abogados", "Litigios y cartas de abogados"),
    ("10_Garantias_calculo", "Garantías: cálculo"), ("11_Onerosos", "Contratos onerosos"), ("12_Desmantelamiento", "Desmantelamiento"),
    ("13_Reconocimiento", "Provisión requerida vs libros"), ("14_Contingencias", "Contingencias a revelar"),
    ("15_Ajustes", "Ajustes propuestos y conciliación"), ("16_Problemas", "Problemas encontrados"),
]
P = ref("02_Parametros")
PRV, GAR, OBL, EST, VPR, REV, GCA, REC, CON, AJ = (ref(n) for n in (
    "03_Provisiones", "04_Garantias", "05_Obligacion_prob", "06_Mejor_estimacion", "07_Valor_presente", "08_Reversion_descuento",
    "10_Garantias_calculo", "13_Reconocimiento", "14_Contingencias", "15_Ajustes"))
_PAR = ["corte", "marco", "edicion", "tasaDescuento", "plazoDescuento", "materialidad", "tolerancia", "mayorProvisiones"]
PAR = {k: f"{P}$B${FILA0 + i}" for i, k in enumerate(_PAR)}


def _rng(h: str, col: str, n: int) -> str:
    return f"{h}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _si(celda: str) -> str:
    """Celda opcional: vacía queda vacía (M22)."""
    return f'IF({celda}="","",{celda})'


_D03 = "hoja 03 (datos del cliente)"

# Explicaciones humanas de «Cómo se calcula esta hoja» (una por columna calculada).
EXPLICA = {
    "01_Resumen": {
        "Importe": ("Trae cada importe de la hoja 15 (Ajustes propuestos y conciliación), concepto por concepto, para que el "
                    "resumen y el detalle coincidan siempre."),
    },
    "05_Obligacion_prob": {
        "Tipo": f"Copia el tipo de la partida (litigio, garantía, oneroso, etc.) desde la {_D03}, en la misma fila.",
        "Obligación presente": (f"Copia de la {_D03} si existe obligación presente (Sí/No); si el cliente la dejó vacía, "
                                "queda en blanco."),
        "Prob. abogado": f"Copia la probabilidad que asigna el abogado desde la {_D03}; si no la informó, queda en blanco.",
        "Prob. gerencia": f"Copia la probabilidad que asigna la gerencia desde la {_D03}; si no la informó, queda en blanco.",
        "Probabilidad usada": "Usa la probabilidad del abogado y, si no la hay, la probabilidad de la gerencia.",
        "Clasificación (NIC 37.14, 23, 27–35)": (
            "En un activo contingente: prácticamente cierto → reconocible, probable → revelar y lo demás → no revelar. En el "
            "resto: sin obligación o sin probabilidad queda «Sin evaluación»; remota → no revelar; obligación presente y "
            "probable (o prácticamente cierta) → reconocer provisión; si no, pasivo contingente a revelar."),
        "Discrepancia": ("Marca «Discrepancia» cuando el abogado y la gerencia informaron probabilidades distintas; si "
                         "coinciden o falta alguna, queda vacío."),
    },
    "06_Mejor_estimacion": {
        "Hecho posterior": (f"Copia de la {_D03} el importe fijado después del corte por sentencia o acuerdo; vacío si no "
                            "lo hay."),
        "Oneroso: mín(costo neto, penalización)": (
            f"Solo en contratos onerosos, con datos de la {_D03}: costo de cumplir menos beneficios esperados (nunca "
            "negativo) y, si hay penalización, el menor entre ese costo neto y la penalización; si falta uno, usa el otro."),
        "Garantías": ("Solo en provisiones de tipo garantía: suma la provisión calculada en la hoja 10 (Garantías: cálculo) "
                      "de las líneas de la hoja 04 vinculadas a este código; vacío si no tiene líneas."),
        "Σ probabilidades %": (f"Suma las probabilidades (%) de los tres escenarios informados en la {_D03}; las vacías "
                               "cuentan como cero."),
        "Valor esperado": ("Pondera el importe de cada escenario de la hoja 03 por su probabilidad y divide para la suma de "
                           "probabilidades; en blanco si ningún escenario tiene probabilidad."),
        "Más probable": ("Toma el importe del escenario con mayor probabilidad (en empate gana el de menor número); en "
                         "blanco si ningún escenario tiene probabilidad."),
        "Punto medio del rango": ("Promedia el importe mínimo y el máximo del rango informado en la hoja 03; en blanco si "
                                  "falta alguno de los dos."),
        "Carta del abogado": f"Copia el importe que indica la carta del abogado en la {_D03}; vacío si no lo informó.",
        "Estimación gerencia": f"Copia la estimación de la gerencia (sin descontar) de la {_D03}; vacío si no la informó.",
        "Base usada": ("Indica qué dato se tomó como mejor estimación, en este orden: hecho posterior, contrato oneroso, "
                       "garantías, escenarios (valor esperado o más probable según el método), punto medio del rango, "
                       "carta del abogado y estimación de la gerencia."),
        "Mejor estimación": ("Toma el importe de la primera base disponible en ese mismo orden; con escenarios usa el más "
                             "probable si el método de la hoja 03 lo pide y, si no, el valor esperado; vacío si no hay "
                             "ninguna base."),
    },
    "07_Valor_presente": {
        "Mejor estimación": "Trae la mejor estimación de la hoja 06 (Mejor estimación), en la misma fila; vacío si no hay.",
        "Plazo (años)": f"Copia de la {_D03} el plazo esperado de salida de recursos, en años; vacío si no se informó.",
        "Tasa antes de impuestos %": ("Usa la tasa antes de impuestos informada para la partida en la hoja 03 y, si falta, "
                                      "la tasa por defecto de la hoja 02 (Parámetros); vacío si no hay ninguna."),
        "¿Descontar?": ("Marca «Sí» cuando el plazo de salida supera los años a partir de los cuales se descuenta, fijados "
                        "en la hoja 02 (Parámetros)."),
        "Factor de descuento": ("Si no se descuenta, el factor es 1; si se descuenta, es 1 ÷ (1 + tasa)^plazo; queda en "
                                "blanco si falta la tasa."),
        "Valor presente": "Multiplica la mejor estimación por el factor de descuento; en blanco si falta alguno de los dos.",
        "Efecto del descuento": ("Resta el valor presente a la mejor estimación: es cuánto baja la provisión por "
                                 "descontarla."),
    },
    "08_Reversion_descuento": {
        "Saldo inicial": f"Copia de la {_D03} el saldo de la provisión al inicio del período; vacío si no se informó.",
        "Tasa %": "Trae la tasa de descuento aplicada a la partida en la hoja 07 (Valor presente).",
        "¿Descontada?": "Trae de la hoja 07 (Valor presente) si la partida se descuenta o no (Sí/No).",
        "Reversión calculada": ("Si la partida se descuenta y hay saldo inicial y tasa, multiplica el saldo inicial por la "
                                "tasa: es el aumento de la provisión por el paso del tiempo."),
        "Reversión registrada": (f"Copia de la {_D03} la reversión del descuento que el cliente registró en el período; "
                                 "vacío si no la informó."),
        "Calculada − registrada": "Resta la reversión registrada a la calculada; en blanco si falta cualquiera de las dos.",
    },
    "09_Litigios_abogados": {
        "Respuesta del abogado": (f"Copia de la {_D03} si se recibió respuesta del abogado (Sí/No); vacío si no se "
                                  "informó."),
        "Días desde el corte": ("Resta la fecha de corte de la hoja 02 (Parámetros) a la fecha de la carta: un número "
                                "negativo indica una carta anterior al corte."),
        "Prob. abogado": "Trae la probabilidad del abogado de la hoja 05 (Obligación presente y probabilidad) para este litigio.",
        "Prob. gerencia": ("Trae la probabilidad de la gerencia de la hoja 05 (Obligación presente y probabilidad) para este "
                           "litigio."),
        "Importe carta": f"Copia el importe que el abogado indica en su carta, tomado de la {_D03}; vacío si no lo hay.",
        "Libros": f"Copia el saldo registrado en libros al corte para este litigio desde la {_D03}.",
        "Libros − carta": "Resta el importe de la carta del abogado al saldo en libros; en blanco si la carta no trae importe.",
        "Evaluación": ("Sin respuesta del abogado marca una limitación; si la carta tiene fecha anterior al corte lo "
                       "advierte; en otro caso, «Respuesta recibida»."),
    },
    "10_Garantias_calculo": {
        "Provisión": "Trae de la hoja 04 (Garantías) el código de la provisión a la que pertenece esta línea de producto.",
        "Unidades": "Trae de la hoja 04 (Garantías) las unidades vendidas con garantía vigente al corte.",
        "% reclamos": "Trae de la hoja 04 (Garantías) el porcentaje histórico de reclamos de esta línea.",
        "Costo medio": "Trae de la hoja 04 (Garantías) lo que cuesta, en promedio, atender cada reclamo.",
        "Provisión calculada": ("Multiplica las unidades por el % de reclamos y por el costo medio por reclamo: es el "
                                "costo esperado de las garantías."),
        "Vínculo": (f"Revisa si el código de la provisión existe en la {_D03}: «Vinculada» si existe; si no, «Sin "
                    "provisión en el detalle»."),
    },
    "11_Onerosos": {
        "Costo de cumplir": f"Copia de la {_D03} el costo de cumplir el contrato; vacío si no se informó.",
        "Beneficios esperados (37.10)": (f"Copia de la {_D03} los beneficios económicos que se esperan del contrato; vacío "
                                         "si no se informaron."),
        "Costo neto de cumplir": ("Resta los beneficios esperados al costo de cumplir, sin bajar de cero; en blanco si no "
                                  "hay costo de cumplir."),
        "Penalización": f"Copia de la {_D03} la penalización por incumplir el contrato; vacío si no se informó.",
        "Costos inevitables (37.68)": ("Toma el menor entre el costo neto de cumplir y la penalización; si solo hay uno de "
                                       "los dos, usa ese; vacío si faltan ambos."),
        "Valor presente": "Trae el valor presente de esta partida desde la hoja 07 (Valor presente).",
        "Libros": f"Copia el saldo registrado en libros al corte para este contrato desde la {_D03}.",
        "Ajuste": ("Trae el ajuste (provisión requerida − libros) calculado para este contrato en la hoja 13 (Provisión "
                   "requerida vs libros)."),
    },
    "12_Desmantelamiento": {
        "Costo estimado": ("Trae de la hoja 07 (Valor presente) la mejor estimación del costo de desmantelar, antes de "
                           "descontarla."),
        "Plazo (años)": "Trae de la hoja 07 (Valor presente) el plazo en años hasta el desmantelamiento.",
        "Tasa %": "Trae de la hoja 07 (Valor presente) la tasa de descuento aplicada a esta partida.",
        "Valor presente": "Trae de la hoja 07 (Valor presente) el costo estimado ya descontado a la fecha de corte.",
        "Libros": f"Copia el saldo registrado en libros al corte para esta obligación desde la {_D03}.",
        "Ajuste contra el costo (CINIIF 1)": ("Trae el ajuste (provisión requerida − libros) de la hoja 13 (Provisión "
                                              "requerida vs libros); en desmantelamiento se registra contra el costo del "
                                              "activo."),
        "Reversión calculada": ("Trae de la hoja 08 (Reversión del descuento) el aumento de la provisión por el paso del "
                                "tiempo que calcula el auditor."),
        "Reversión registrada": "Trae de la hoja 08 (Reversión del descuento) la reversión que el cliente registró en el período.",
    },
    "13_Reconocimiento": {
        "Tipo": "Trae el tipo de la partida desde la hoja 05 (Obligación presente y probabilidad).",
        "Clasificación": ("Trae la clasificación (reconocer, revelar o no revelar) de la hoja 05 (Obligación presente y "
                          "probabilidad)."),
        "Valor presente": "Trae el valor presente de la mejor estimación desde la hoja 07 (Valor presente).",
        "Provisión requerida": ("Si la partida se clasificó como «Reconocer provisión» o «Activo reconocible», toma su "
                                "valor presente; si solo se revela o es remota, cero; en blanco si está sin evaluación."),
        "Libros": f"Copia el saldo registrado en libros al corte desde la {_D03}.",
        "Ajuste (requerida − libros)": ("Resta el saldo en libros a la provisión requerida: positivo significa que falta "
                                        "provisión y negativo que sobra; en blanco si está sin evaluación."),
    },
    "14_Contingencias": {
        "Clasificación": ("Trae la clasificación de la partida desde la hoja 05 (Obligación presente y probabilidad); aquí "
                          "solo aparecen pasivos y activos contingentes."),
        "Probabilidad": ("Trae la probabilidad usada (la del abogado o, si falta, la de la gerencia) de la hoja 05 "
                         "(Obligación presente y probabilidad)."),
        "Efecto estimado": ("Trae el valor presente de la mejor estimación de la hoja 07 (Valor presente): es el efecto "
                            "financiero que se revela."),
        "Revelado": f"Copia de la {_D03} si la contingencia está revelada en notas (Sí/No); vacío si no se informó.",
        "Evaluación": ("Si es un activo contingente que no se revela, lo indica; si no, dice «Revelado» cuando la nota ya "
                       "lo incluye o «Revelar» cuando falta, distinguiendo pasivo de activo contingente."),
        "Registrado en libros": f"Copia el saldo que el cliente tiene en libros para esta contingencia, desde la {_D03}.",
    },
    "15_Ajustes": {
        "Importe": ("Libros, requerida y ajuste suman la hoja 13 (Provisión requerida vs libros) sin los activos "
                    "contingentes; descuento, reversiones y garantías traen los totales de las hojas 07, 08 y 10; los "
                    "contingentes salen de las hojas 13 y 14; mayor y materialidad vienen de la hoja 02 y la diferencia es "
                    "detalle − mayor."),
        "Base": ("Solo en la última fila: indica «Sí» si el ajuste propuesto, en valor absoluto, supera la materialidad; "
                 "vacío si no hay materialidad."),
    },
}

# Panel del dashboard (formato en graficos.py): la población son los saldos en libros de todas las partidas evaluadas;
# el auditor recalcula la provisión requerida y la compara con las provisiones registradas.
PANEL = {
    "poblacion": {"rotulo": "Saldos en libros evaluados", "hoja": "13_Reconocimiento", "col": "Libros"},
    "recalculado": {"rotulo": "Provisión requerida", "total": "provisionRequerida"},
    "registrado": {"rotulo": "Provisiones en libros", "total": "librosProvisiones"},
    "composicion": {"rotulo": "Provisión requerida por tipo", "hoja": "13_Reconocimiento", "etiqueta": "Tipo",
                    "valor": "Provisión requerida"},
    "distribucion": {"rotulo": "Saldos en libros por tipo", "hoja": "13_Reconocimiento", "etiqueta": "Tipo",
                     "valor": "Libros"},
}


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p, R, G, k = d["parametros"], d["provisiones"], d["garantias"], d["kpi"]
    n, ng = len(R), len(G)
    fila = {r["id"]: FILA0 + i for i, r in enumerate(R)}
    pv = lambda kk: None if p.get(kk) in (None, "") else float(a_num(p.get(kk)))
    fin = lambda nn: FILA0 + nn - 1

    parametros = [
        ["Corte del ejercicio", d["corte"], "Ficha del encargo"],
        ["Marco contable", d["marco"], "Mismo cálculo en NIIF completas (NIC 37) y PYMES (Sección 21): no se enruta"],
        ["Edición PYMES", d["edicion"], "2015 y 2025: misma numeración en los párrafos citados y sin diferencias de cálculo (leído en PYMES 2015 ES y 2025 EN)"],
        ["Tasa de descuento por defecto (%)", pv("tasaDescuento"), "Tasa antes de impuestos, riesgos específicos (NIC 37.47; PYMES 21.7)"],
        ["Descontar si el plazo supera (años)", pv("plazoDescuento"), "Efecto material del valor temporal (NIC 37.45–46): juicio del auditor"],
        ["Materialidad (importe)", pv("materialidad"), "Plan de auditoría (NIA 320)"],
        ["Tolerancia (importe)", pv("tolerancia"), "Materialidad de ejecución / diferencias triviales"],
        ["Mayor: provisiones al corte", pv("mayorProvisiones"), "Mayor contable"],
    ]

    prv = [[(r["fecha_carta"] if kk == "fecha_carta" else r[kk]) for kk in _ORDEN] for r in R]
    gar = [[g["id"], g["prov"], g["desc"], g["u"], g["pct"], g["costo"]] for g in G]

    def X(c, r):
        return f"{PRV}{L[c]}{r}"

    # 05 · obligación y probabilidad (fila alineada con 03).
    obl = []
    for i, x in enumerate(R):
        r = FILA0 + i
        obl.append([
            x["id"], fx(X("tipo", r), x["tipo"]), fx(_si(X("obligacion_presente", r)), x["obligacion_presente"]),
            fx(_si(X("probabilidad_abogado", r)), x["probabilidad_abogado"]), fx(_si(X("probabilidad_gerencia", r)), x["probabilidad_gerencia"]),
            fx(f'IF(D{r}<>"",D{r},E{r})', x["prob"]),
            fx(f'IF(B{r}="Activo contingente",IF(F{r}="","Sin evaluación",IF(F{r}="Prácticamente cierta","Activo reconocible",'
               f'IF(F{r}="Probable","Activo contingente: revelar","Activo contingente: no revelar"))),'
               f'IF(OR(F{r}="",C{r}=""),"Sin evaluación",IF(F{r}="Remota","Remota: no revelar",'
               f'IF(AND(C{r}="Sí",OR(F{r}="Probable",F{r}="Prácticamente cierta")),"Reconocer provisión","Pasivo contingente: revelar"))))', x["clasif"]),
            fx(f'IF(AND(D{r}<>"",E{r}<>"",D{r}<>E{r}),"Discrepancia","")', x["discrepancia"]),
        ])

    # 06 · mejor estimación (fila alineada con 03).
    gp, gc = _rng(GAR, "B", ng), _rng(GCA, "F", ng)
    est = []
    for i, x in enumerate(R):
        r = FILA0 + i
        c = lambda kk: X(kk, r)
        nsum = f'N({c("prob_1")})+N({c("prob_2")})+N({c("prob_3")})'
        est.append([
            x["id"], fx(_si(c("importe_posterior")), x["est_post"]),
            fx(f'IF({c("tipo")}<>"Oneroso","",IF(AND({c("costo_cumplir")}="",{c("penalizacion")}=""),"",'
               f'IF({c("costo_cumplir")}="",{c("penalizacion")},IF({c("penalizacion")}="",MAX({c("costo_cumplir")}-N({c("beneficios_contrato")}),0),'
               f'MIN(MAX({c("costo_cumplir")}-N({c("beneficios_contrato")}),0),{c("penalizacion")})))))', x["est_oner"]),
            fx(f'IF({c("tipo")}="Garantía",IF(COUNTIF({gp},A{r})=0,"",SUMIF({gp},A{r},{gc})),"")', x["est_gar"]),
            fx(nsum, x["sprob"]),
            fx(f'IF(E{r}=0,"",(N({c("importe_1")})*N({c("prob_1")})+N({c("importe_2")})*N({c("prob_2")})+N({c("importe_3")})*N({c("prob_3")}))/({nsum}))',
               x["est_ve"]),
            fx(f'IF(E{r}=0,"",IF(AND(N({c("prob_1")})>=N({c("prob_2")}),N({c("prob_1")})>=N({c("prob_3")})),{c("importe_1")},'
               f'IF(N({c("prob_2")})>=N({c("prob_3")}),{c("importe_2")},{c("importe_3")})))', x["est_mp"]),
            fx(f'IF(AND({c("importe_minimo")}<>"",{c("importe_maximo")}<>""),({c("importe_minimo")}+{c("importe_maximo")})/2,"")', x["est_mid"]),
            fx(_si(c("importe_abogado")), x["importe_abogado"]), fx(_si(c("importe_gerencia")), x["importe_gerencia"]),
            fx(f'IF(B{r}<>"","Hecho posterior (NIC 10.9 a)",IF(C{r}<>"","Oneroso: menor costo (37.68)",IF(D{r}<>"","Garantías: valor esperado (37.39)",'
               f'IF(E{r}>0,IF({c("metodo")}="Más probable","Desenlace más probable (37.40)","Valor esperado (37.39)"),'
               f'IF(H{r}<>"","Punto medio del rango (37.39)",IF(I{r}<>"","Carta del abogado",IF(J{r}<>"","Estimación de la gerencia","Sin estimación")))))))',
               x["base"]),
            fx(f'IF(B{r}<>"",B{r},IF(C{r}<>"",C{r},IF(D{r}<>"",D{r},IF(E{r}>0,IF({c("metodo")}="Más probable",G{r},F{r}),'
               f'IF(H{r}<>"",H{r},IF(I{r}<>"",I{r},IF(J{r}<>"",J{r},"")))))))', x["est"]),
        ])

    # 07 · valor presente (fila alineada con 03).
    vpr = []
    for i, x in enumerate(R):
        r = FILA0 + i
        vpr.append([
            x["id"], fx(_si(f"{EST}L{r}"), x["est"]), fx(_si(X("plazo_anios", r)), x["plazo_anios"]),
            fx(f'IF({X("tasa_descuento", r)}<>"",{X("tasa_descuento", r)},IF({PAR["tasaDescuento"]}<>"",{PAR["tasaDescuento"]},""))', x["tasa"]),
            fx(f'IF(AND(C{r}<>"",C{r}>{PAR["plazoDescuento"]}),"Sí","No")', x["descontar"]),
            fx(f'IF(E{r}="No",1,IF(D{r}="","",1/(1+D{r}/100)^C{r}))', x["factor"]),
            fx(f'IF(OR(B{r}="",F{r}=""),"",B{r}*F{r})', x["vp"]),
            fx(f'IF(G{r}="","",B{r}-G{r})', x["descuento"]),
        ])

    # 08 · reversión del descuento (fila alineada con 03).
    rev = []
    for i, x in enumerate(R):
        r = FILA0 + i
        rev.append([
            x["id"], fx(_si(X("saldo_inicial", r)), x["saldo_inicial"]), fx(f"{VPR}D{r}", x["tasa"]), fx(f"{VPR}E{r}", x["descontar"]),
            fx(f'IF(AND(B{r}<>"",C{r}<>"",D{r}="Sí"),B{r}*C{r}/100,"")', x["rev_calc"]),
            fx(_si(X("reversion_registrada", r)), x["reversion_registrada"]),
            fx(f'IF(OR(E{r}="",F{r}=""),"",E{r}-F{r})', x["rev_dif"]),
        ])

    # 09 · litigios y cartas de abogados.
    LI = [x for x in R if x["tipo"] == "Litigio"]
    lit = []
    for j, x in enumerate(LI):
        s, r = fila[x["id"]], FILA0 + j
        lit.append([
            x["id"], x["descripcion"], fx(_si(X("respuesta_abogado", s)), x["respuesta_abogado"]), x["fecha_carta"],
            fx(f'IF(D{r}="","",D{r}-{PAR["corte"]})', x["dias_carta"]),
            fx(f"{OBL}D{s}", x["probabilidad_abogado"]), fx(f"{OBL}E{s}", x["probabilidad_gerencia"]),
            fx(_si(X("importe_abogado", s)), x["importe_abogado"]), fx(X("saldo_libros", s), x["saldo_libros"]),
            fx(f'IF(H{r}="","",I{r}-H{r})', None if x["importe_abogado"] is None else x["saldo_libros"] - x["importe_abogado"]),
            fx(f'IF(C{r}<>"Sí","Sin respuesta: limitación (NIA 501)",IF(AND(E{r}<>"",E{r}<0),"Carta anterior al corte","Respuesta recibida"))', x["eval_lit"]),
        ])

    # 10 · garantías (fila alineada con 04).
    rid = _rng(PRV, "A", n)
    gca = []
    for i, g in enumerate(G):
        r = FILA0 + i
        gca.append([
            g["id"], fx(f"{GAR}B{r}", g["prov"]), fx(f"{GAR}D{r}", g["u"]), fx(f"{GAR}E{r}", g["pct"]), fx(f"{GAR}F{r}", g["costo"]),
            fx(f"C{r}*D{r}/100*E{r}", g["calc"]),
            fx(f'IF(COUNTIF({rid},B{r})=0,"Sin provisión en el detalle","Vinculada")',
               "Vinculada" if g["prov"].lower() in {x["id"].lower() for x in R} else "Sin provisión en el detalle"),
        ])

    # 11 · contratos onerosos.
    ON = [x for x in R if x["tipo"] == "Oneroso"]
    one = []
    for j, x in enumerate(ON):
        s, r = fila[x["id"]], FILA0 + j
        one.append([
            x["id"], x["descripcion"], fx(_si(X("costo_cumplir", s)), x["costo_cumplir"]),
            fx(_si(X("beneficios_contrato", s)), x["beneficios_contrato"]),
            fx(f'IF(C{r}="","",MAX(C{r}-N(D{r}),0))', x["costo_neto"]), fx(_si(X("penalizacion", s)), x["penalizacion"]),
            fx(f'IF(AND(E{r}="",F{r}=""),"",IF(E{r}="",F{r},IF(F{r}="",E{r},MIN(E{r},F{r}))))', x["est_oner"]),
            fx(f"{VPR}G{s}", x["vp"]), fx(X("saldo_libros", s), x["saldo_libros"]), fx(f"{REC}G{s}", x["dif"]),
        ])

    # 12 · desmantelamiento.
    DE = [x for x in R if x["tipo"] == "Desmantelamiento"]
    des = []
    for x in DE:
        s = fila[x["id"]]
        des.append([
            x["id"], x["descripcion"], fx(f"{VPR}B{s}", x["est"]), fx(f"{VPR}C{s}", x["plazo_anios"]), fx(f"{VPR}D{s}", x["tasa"]),
            fx(f"{VPR}G{s}", x["vp"]), fx(X("saldo_libros", s), x["saldo_libros"]), fx(f"{REC}G{s}", x["dif"]),
            fx(f"{REV}E{s}", x["rev_calc"]), fx(f"{REV}F{s}", x["reversion_registrada"]),
        ])

    # 13 · reconocimiento (fila alineada con 03).
    rec = []
    for i, x in enumerate(R):
        r = FILA0 + i
        rec.append([
            x["id"], fx(f"{OBL}B{r}", x["tipo"]), fx(f"{OBL}G{r}", x["clasif"]), fx(f"{VPR}G{r}", x["vp"]),
            fx(f'IF(C{r}="Sin evaluación","",IF(OR(C{r}="Reconocer provisión",C{r}="Activo reconocible"),D{r},0))', x["requerida"]),
            fx(X("saldo_libros", r), x["saldo_libros"]), fx(f'IF(E{r}="","",E{r}-F{r})', x["dif"]), x["contrapartida"],
        ])

    # 14 · contingencias a revelar.
    CO = [x for x in R if "contingente" in x["clasif"]]
    con = []
    for j, x in enumerate(CO):
        s, r = fila[x["id"]], FILA0 + j
        con.append([
            x["id"], x["descripcion"], fx(f"{OBL}G{s}", x["clasif"]), fx(f"{OBL}F{s}", x["prob"]), fx(f"{VPR}G{s}", x["vp"]),
            fx(_si(X("revelado", s)), x["revelado"]),
            fx(f'IF(C{r}="Activo contingente: no revelar","No revelar (no probable); no reconocer (37.31)",IF(F{r}="Sí",'
               f'IF(LEFT(C{r},6)="Pasivo","Revelado (NIC 37.86)","Revelado (NIC 37.89)"),'
               f'IF(LEFT(C{r},6)="Pasivo","Revelar: NIC 37.86 · PYMES 21.15","Revelar: NIC 37.89 · PYMES 21.16")))', x["eval_cont"]),
            fx(X("saldo_libros", s), x["saldo_libros"]),
        ])
    nc = len(CO)

    # 15 · ajustes y conciliación.
    rb, rt = _rng(REC, "B", n), _rng(REC, "C", n)
    b = lambda kk: f"B{FILA0 + kk}"
    sif = lambda col: f'SUMIFS({_rng(REC, col, n)},{rb},"<>Activo contingente")'
    ajus = [
        ["Provisiones registradas en libros (pasivos)", fx(sif("F"), k["librosProvisiones"]), "", "", "Detalle del cliente"],
        ["Provisión requerida (NIC 37.36–47; PYMES 21.7)", fx(sif("E"), k["provisionRequerida"]), "", "", "13_Reconocimiento"],
        ["Ajuste propuesto = requerida − libros", fx(sif("G"), k["ajusteProvisiones"]), "Gasto / costo del activo", "Provisión",
         "Si es negativo: débito a la provisión y crédito a resultados (NIC 37.59)"],
        ["Efecto del descuento a valor presente", fx(f"SUM({_rng(VPR, 'H', n)})", k["descuento"]), "", "", "NIC 37.45–47; PYMES 21.7"],
        ["Reversión del descuento calculada (saldo inicial × tasa)", fx(f"SUM({_rng(REV, 'E', n)})", k["reversionCalculada"]), "", "",
         "NIC 37.60; PYMES 21.11"],
        ["Reversión del descuento registrada", fx(f"SUM({_rng(REV, 'F', n)})", k["reversionRegistrada"]), "", "", "Mayor de gastos financieros"],
        ["Reversión: calculada − registrada (reclasificación)", fx(f"SUM({_rng(REV, 'G', n)})", k["difReversion"]), "Costo financiero",
         "Gasto operativo / provisión", "Reclasificación dentro de resultados"],
        ["Garantías calculadas (unidades × % reclamos × costo)", fx(f"SUM({_rng(GCA, 'F', ng)})", k["garantiasCalculadas"]), "", "",
         "NIC 37.24, 39; PYMES 21A.4"],
        ["Pasivos contingentes a revelar (efecto estimado)", fx(f'SUMIF({rt},"Pasivo contingente: revelar",{_rng(REC, "D", n)})', k["pasivosContingentes"]),
         "", "", "NIC 37.86; PYMES 21.15"],
        ["Pasivos contingentes sin revelar", fx(f'SUMIFS({_rng(CON, "E", nc)},{_rng(CON, "C", nc)},"Pasivo contingente: revelar",'
                                                f'{_rng(CON, "G", nc)},"Revelar*")', k["contingentesSinRevelar"]) if nc else fx("0", 0.0),
         "", "", "Revelación en notas"],
        ["Activo contingente reconocido indebidamente", fx(f'SUMIFS({_rng(REC, "F", n)},{rb},"Activo contingente",{rt},"<>Activo reconocible")',
                                                           k["activoContingenteReconocido"]), "", "", "NIC 37.31, 33; PYMES 21.13"],
        ["Ajuste del activo contingente = −(reconocido indebidamente)", fx(f"-{b(10)}", k["ajusteActivoContingente"]), "Resultados",
         "Activo contingente", "Revertir el activo"],
        ["Provisiones según el mayor", fx(_si(PAR["mayorProvisiones"]), k["mayorProvisiones"]), "", "", "Mayor contable"],
        ["Diferencia detalle − mayor", fx(f'IF({b(12)}="","",{b(0)}-{b(12)})', k["difMayor"]), "", "", ""],
        ["Materialidad", fx(_si(PAR["materialidad"]), k["materialidad"]), "", "", "NIA 320"],
        ["¿El ajuste propuesto supera la materialidad?", None, "", "",
         fx(f'IF({b(14)}="","",IF(ABS({b(2)})>{b(14)},"Sí","No"))', k["superaMaterialidad"])],
    ]
    celda = {"librosProvisiones": 0, "provisionRequerida": 1, "ajusteProvisiones": 2, "descuento": 3, "reversionCalculada": 4,
             "reversionRegistrada": 5, "difReversion": 6, "garantiasCalculadas": 7, "pasivosContingentes": 8, "contingentesSinRevelar": 9,
             "activoContingenteReconocido": 10, "ajusteActivoContingente": 11, "difMayor": 13}
    resumen = [[res["labels"][kk], fx(f"{AJ}B{FILA0 + celda[kk]}", k[kk])] for kk in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Provisiones", "Provisiones y contingencias (datos del cliente)",
             [[c["label"], "d" if c["type"] == "date" else ("n" if c["type"] == "number" else "t")] for c in _PROV], prv),
        hoja("04_Garantias", "Garantías (datos del cliente)",
             [["Línea", "t"], ["Provisión", "t"], ["Descripción", "t"], ["Unidades con garantía", "n"], ["% reclamos", "n"], ["Costo medio", "n"]], gar),
        hoja("05_Obligacion_prob", "Obligación presente y probabilidad",
             [["Código", "t"], ["Tipo", "t"], ["Obligación presente", "t"], ["Prob. abogado", "t"], ["Prob. gerencia", "t"],
              ["Probabilidad usada", "t"], ["Clasificación (NIC 37.14, 23, 27–35)", "t"], ["Discrepancia", "t"]], obl, explica=EXPLICA["05_Obligacion_prob"]),
        hoja("06_Mejor_estimacion", "Mejor estimación",
             [["Código", "t"], ["Hecho posterior", "n"], ["Oneroso: mín(costo neto, penalización)", "n"], ["Garantías", "n"], ["Σ probabilidades %", "n"],
              ["Valor esperado", "n"], ["Más probable", "n"], ["Punto medio del rango", "n"], ["Carta del abogado", "n"], ["Estimación gerencia", "n"],
              ["Base usada", "t"], ["Mejor estimación", "n"]], est, explica=EXPLICA["06_Mejor_estimacion"]),
        hoja("07_Valor_presente", "Valor presente (descuento)",
             [["Código", "t"], ["Mejor estimación", "n"], ["Plazo (años)", "n"], ["Tasa antes de impuestos %", "n"], ["¿Descontar?", "t"],
              ["Factor de descuento", "x"], ["Valor presente", "n"], ["Efecto del descuento", "n"]], vpr,
             ["TOTAL", None, None, None, "", None, None, suma("H", fin(n), k["descuento"])], explica=EXPLICA["07_Valor_presente"]),
        hoja("08_Reversion_descuento", "Actualización financiera (reversión del descuento)",
             [["Código", "t"], ["Saldo inicial", "n"], ["Tasa %", "n"], ["¿Descontada?", "t"], ["Reversión calculada", "n"], ["Reversión registrada", "n"],
              ["Calculada − registrada", "n"]], rev,
             ["TOTAL", None, None, "", suma("E", fin(n), k["reversionCalculada"]), suma("F", fin(n), k["reversionRegistrada"]),
              suma("G", fin(n), k["difReversion"])], explica=EXPLICA["08_Reversion_descuento"]),
        hoja("09_Litigios_abogados", "Litigios y cartas de abogados",
             [["Código", "t"], ["Descripción", "t"], ["Respuesta del abogado", "t"], ["Fecha de la carta", "d"], ["Días desde el corte", "i"],
              ["Prob. abogado", "t"], ["Prob. gerencia", "t"], ["Importe carta", "n"], ["Libros", "n"], ["Libros − carta", "n"], ["Evaluación", "t"]], lit, explica=EXPLICA["09_Litigios_abogados"]),
        hoja("10_Garantias_calculo", "Garantías: cálculo",
             [["Línea", "t"], ["Provisión", "t"], ["Unidades", "n"], ["% reclamos", "n"], ["Costo medio", "n"], ["Provisión calculada", "n"],
              ["Vínculo", "t"]], gca,
             ["TOTAL", "", None, None, None, suma("F", fin(ng), k["garantiasCalculadas"]), ""] if ng else None, explica=EXPLICA["10_Garantias_calculo"]),
        hoja("11_Onerosos", "Contratos onerosos",
             [["Código", "t"], ["Descripción", "t"], ["Costo de cumplir", "n"], ["Beneficios esperados (37.10)", "n"],
              ["Costo neto de cumplir", "n"], ["Penalización", "n"], ["Costos inevitables (37.68)", "n"],
              ["Valor presente", "n"], ["Libros", "n"], ["Ajuste", "n"]], one, explica=EXPLICA["11_Onerosos"]),
        hoja("12_Desmantelamiento", "Desmantelamiento",
             [["Código", "t"], ["Descripción", "t"], ["Costo estimado", "n"], ["Plazo (años)", "n"], ["Tasa %", "n"], ["Valor presente", "n"],
              ["Libros", "n"], ["Ajuste contra el costo (CINIIF 1)", "n"], ["Reversión calculada", "n"], ["Reversión registrada", "n"]], des, explica=EXPLICA["12_Desmantelamiento"]),
        hoja("13_Reconocimiento", "Provisión requerida vs libros",
             [["Código", "t"], ["Tipo", "t"], ["Clasificación", "t"], ["Valor presente", "n"], ["Provisión requerida", "n"], ["Libros", "n"],
              ["Ajuste (requerida − libros)", "n"], ["Contrapartida", "t"]], rec,
             ["TOTAL", "", "", None, suma("E", fin(n), sum(x["requerida"] or 0 for x in R)), suma("F", fin(n), sum(x["saldo_libros"] for x in R)),
              suma("G", fin(n), sum(x["dif"] or 0 for x in R)), ""], explica=EXPLICA["13_Reconocimiento"]),
        hoja("14_Contingencias", "Contingencias a revelar",
             [["Código", "t"], ["Descripción", "t"], ["Clasificación", "t"], ["Probabilidad", "t"], ["Efecto estimado", "n"], ["Revelado", "t"],
              ["Evaluación", "t"], ["Registrado en libros", "n"]], con, explica=EXPLICA["14_Contingencias"]),
        hoja("15_Ajustes", "Ajustes propuestos y conciliación",
             [["Concepto", "t"], ["Importe", "n"], ["Débito (si positivo)", "t"], ["Crédito (si positivo)", "t"], ["Base", "t"]], ajus, explica=EXPLICA["15_Ajustes"]),
        hoja("16_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -------------------------------------------------------------------

def definicion() -> dict:
    prov = ("Una fila por provisión, litigio, garantía, contrato oneroso, desmantelamiento, reestructuración o activo contingente: código, "
            "descripción, tipo, obligación presente (Sí/No), probabilidad según abogado y gerencia (Probable/Posible/Remota/Prácticamente "
            "cierta), importe de la carta, estimación de la gerencia, rango mínimo/máximo, hasta 3 escenarios (importe y probabilidad %), "
            "método (Valor esperado/Más probable), costo de cumplir, beneficios económicos esperados y penalización (onerosos), importe fijado después del corte, plazo en años, "
            "tasa antes de impuestos, saldo en libros, saldo inicial, reversión del descuento registrada, respuesta del abogado (Sí/No), fecha "
            "de la carta y si está revelado (Sí/No). Sin filas de total.")
    gar = ("Opcional: una fila por línea de producto con garantía: código, código de la provisión a la que pertenece, descripción, unidades "
           "vendidas con garantía vigente al corte, % de reclamos histórico y costo medio por reclamo.")
    return {
        "name": "Provisiones y contingencias",
        "area": "Provisiones",
        "processor": "provisiones_contingencias",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Evalúa cada provisión, litigio y contingencia: obligación presente, probabilidad (abogado y gerencia), mejor estimación "
                    "(valor esperado, más probable, punto medio, carta del abogado, garantías, onerosos), valor presente a la tasa antes de "
                    "impuestos, reversión del descuento, diferencia con libros (ajuste propuesto) y pasivos y activos contingentes a revelar."),
        "source": {"organization": "IFRS Foundation (texto en español del Reglamento (UE) 2023/1803)", "type": "Norma contable", "date": "",
                   "document": ("NIC 37 párr. 10 (definiciones), 14 (reconocimiento), 15–16 (obligación presente), 23 (probable = más "
                                "probable que no), 24 (obligaciones similares: garantías), 27–28 (pasivo contingente: solo revelación), 31, 33–35 "
                                "(activo contingente), 36–37 (mejor estimación), 39 (valor esperado; valor intermedio del rango), 40 (desenlace más "
                                "probable), 45–47 (valor actual, tasa antes de impuestos), 59–60 (revisión; aumento por el paso del tiempo como "
                                "coste por intereses), 53–56 (reembolsos), 66–69 (contratos onerosos; 68: costes inevitables = menores costes netos por resolver el contrato = el menor entre el coste de cumplir sus cláusulas y las compensaciones o multas por incumplirlo; 68A: coste de cumplir = costes directamente relacionados con el contrato, incrementales más una asignación de otros costes directos), 86 y 89 (revelación). "
                                "NIC 37.39, ejemplo de garantías (valor esperado). NIC 10 párr. 9 a) (litigio resuelto después del cierre). CINIIF 1 "
                                "párr. 5 (modelo del costo: cambios contra el costo del activo; 5 b): lo deducido no puede superar el importe en libros del activo, el exceso va a resultados) y 8 (reversión del descuento en resultados como costo financiero)."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES, Sección 21: 21.4 (reconocimiento), 21.6 (obligación presente), 21.7 a) valor esperado "
                                      "y valor medio del rango, b) desenlace más probable, y valor presente con tasa antes de impuestos, 21.9 "
                                      "(reembolsos), 21.11 (revisión; reversión del descuento como costo financiero), 21.12 (pasivo contingente), "
                                      "21.13 (activo contingente), 21.14–21.16 (revelaciones), 21A.2 (contratos onerosos), 21A.4 (garantías); el Apéndice 21A es guía, no forma parte de la Sección. "
                                      "Leído en PYMES 2015 (ES) y 2025 (EN): misma numeración para los párrafos citados. Mismo cálculo que la NIC 37."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 501", "section": "párr. 9–12", "requirement": "Litigios y reclamaciones: indagación y carta a los abogados externos; negativa o falta de respuesta → opinión modificada (NIA 705)."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 22–26, 28–29 y 37", "requirement": "Estimaciones contables: método, supuestos (probabilidades, tasa) y datos; rango del auditor."},
            {"document": "NIA 560", "section": "párr. 6–9", "requirement": "Hechos posteriores: sentencias o acuerdos después del corte que confirman la obligación."},
            {"document": "NIA 501 y NIA 580", "section": "NIA 501 párr. 12; NIA 580 párr. 13", "requirement": "Manifestaciones escritas sobre litigios, reclamaciones y contingencias conocidas."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del detalle de provisiones frente al mayor."},
        ],
        "calculo": [
            "Clasificación: obligación presente Sí + salida probable → reconocer provisión; posible (u obligación No con salida no remota) → pasivo contingente a revelar; remota → nada (NIC 37.14, 23, 27–28; PYMES 21.4, 21.12).",
            "Probabilidad usada: la del abogado; si falta, la de la gerencia. Diferencia entre ambas se señala.",
            "Mejor estimación: hecho posterior (NIC 10.9 a) → oneroso = mín(máx(costo de cumplir − beneficios económicos esperados, 0), penalización) (NIC 37.10 y 66: el contrato es oneroso cuando los costes inevitables exceden los beneficios económicos que se esperan recibir; 37.68: costes inevitables = menores costes netos por resolver el contrato = el menor entre el coste de cumplir sus cláusulas y las compensaciones o multas por incumplirlo; 37.68A: coste de cumplir = costes directamente relacionados. Si el contrato es oneroso y no se informan los beneficios esperados, se usa el costo de cumplir completo y se emite el problema ONEROSO_SIN_BENEFICIOS) → garantías = Σ unidades × % reclamos × costo medio (37.24, 39) → escenarios: valor esperado Σ importe × prob ÷ Σ prob (37.39) o el más probable (37.40) → punto medio del rango (37.39) → carta del abogado → estimación de la gerencia.",
            "Valor presente = mejor estimación ÷ (1 + tasa)^plazo cuando el plazo supera el parámetro; tasa antes de impuestos de la partida o la tasa por defecto (37.45–47; PYMES 21.7).",
            "Reversión del descuento del período = saldo inicial × tasa, frente a la registrada como costo financiero (37.60; CINIIF 1.8 en desmantelamiento; PYMES 21.11; 21.10 = uso de la provisión).",
            "Provisión requerida = valor presente si se reconoce; 0 si es contingente o remota. Ajuste = requerida − libros (desmantelamiento: contra el costo del activo, CINIIF 1.5; el límite de 5 b) —lo deducido no supera el importe en libros; el exceso, a resultados— no se aplica aún: pendiente de decisión del socio).",
            "Activo contingente: no se reconoce salvo realización prácticamente cierta; se revela si la entrada es probable (37.31–35, 89; PYMES 21.13, 21.16).",
        ],
        "fields": _PROV, "rules": [], "control": CONTROL, "primary": "ajusteProvisiones",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[a, b] for a, b in CEDULAS],
        "program": [
            {"code": "PROV-01", "objective": "Obligación presente", "risk": "Provisión sin obligación presente por un suceso pasado", "assertion": "Existencia",
             "procedure": "Revisar el suceso que origina cada partida y la existencia de obligación legal o implícita", "evidence": "Contratos, demandas, actas",
             "criterion": "NIC 37.14–16; PYMES 21.4–21.6", "source": "NIC 37 · Sección 21"},
            {"code": "PROV-02", "objective": "Probabilidad", "risk": "Provisión con salida posible o remota; probable no registrada", "assertion": "Existencia / Integridad",
             "procedure": "Comparar la evaluación del abogado y de la gerencia y clasificar (probable/posible/remota)", "evidence": "Cartas de abogados, informe de gerencia",
             "criterion": "Probable = más probable que no (NIC 37.23)", "source": "NIC 37.23 · NIA 501"},
            {"code": "PROV-03", "objective": "Mejor estimación", "risk": "Provisión subestimada o sobrestimada", "assertion": "Valoración",
             "procedure": "Recalcular valor esperado, desenlace más probable o punto medio y comparar con libros", "evidence": "Escenarios, rango, cálculo de la gerencia",
             "criterion": "NIC 37.36–40; PYMES 21.7", "source": "NIC 37 · NIA 540"},
            {"code": "PROV-04", "objective": "Cartas de abogados y litigios", "risk": "Litigios no informados o evaluados sin evidencia externa", "assertion": "Integridad",
             "procedure": "Enviar cartas a los abogados, obtener respuesta posterior al corte y conciliar importes con libros", "evidence": "Respuestas de abogados",
             "criterion": "Respuesta recibida y concordante", "source": "NIA 501 · NIA 560"},
            {"code": "PROV-05", "objective": "Garantías", "risk": "Provisión de garantías sin base histórica", "assertion": "Valoración",
             "procedure": "Recalcular unidades con garantía × % de reclamos × costo medio", "evidence": "Ventas con garantía, reclamos históricos",
             "criterion": "NIC 37.24, 39; PYMES 21A.4", "source": "NIC 37 · Sección 21"},
            {"code": "PROV-06", "objective": "Contratos onerosos", "risk": "Contrato oneroso no provisionado", "assertion": "Integridad / Valoración",
             "procedure": "Restar los beneficios esperados del costo de cumplir, comparar con la penalización y provisionar el menor (previo deterioro de activos, NIC 37.69)",
             "evidence": "Contratos, presupuestos, ingresos esperados del contrato",
             "criterion": "NIC 37.66–69; PYMES 21A.2", "source": "NIC 37"},
            {"code": "PROV-07", "objective": "Desmantelamiento y descuento", "risk": "Descuento no aplicado o reversión no registrada", "assertion": "Valoración / Presentación",
             "procedure": "Recalcular el valor presente a la tasa antes de impuestos y la reversión del descuento del período", "evidence": "Estudio técnico, tasas",
             "criterion": "NIC 37.45–47, 60; CINIIF 1; PYMES 21.7, 21.11", "source": "NIC 37 · CINIIF 1"},
            {"code": "PROV-08", "objective": "Contingencias y revelación", "risk": "Pasivo contingente sin revelar; activo contingente reconocido", "assertion": "Presentación y revelación",
             "procedure": "Listar pasivos y activos contingentes y verificar su revelación; obtener manifestaciones escritas", "evidence": "Notas, carta de manifestaciones",
             "criterion": "NIC 37.86, 89; PYMES 21.15–21.16", "source": "NIC 37 · NIA 580"},
        ],
        "requests": [
            req("RQ-001", "Detalle de provisiones, litigios, garantías, onerosos, desmantelamiento y contingencias", "provisiones", "PROV-01",
                "Población a evaluar y conciliar con el mayor", content=prov),
            req("RQ-002", "Cálculo de garantías por línea de producto", "garantias", "PROV-05", "Base del valor esperado de garantías",
                required=False, content=gar),
            req("RQ-003", "Respuestas de los abogados a la carta de confirmación", None, "PROV-04", "Evidencia externa de litigios",
                formats=("pdf",), use="soporte"),
            req("RQ-004", "Contratos onerosos y estudio técnico de desmantelamiento", None, "PROV-06", "Sustento de costos y plazos",
                required=False, formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-005", "Sentencias o acuerdos posteriores al corte", None, "PROV-04", "Hechos posteriores (NIA 560)", required=False,
                formats=("pdf",), use="soporte"),
            req("RQ-006", "Mayor de provisiones y de gastos financieros", None, "PROV-07", "Conciliación y reversión del descuento",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-007", "Carta de manifestaciones de la gerencia (litigios y contingencias)", None, "PROV-08", "NIA 580",
                formats=("pdf",), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


def _pr(id, desc, tipo, libros, **x):
    return {"id": id, "descripcion": desc, "tipo": tipo, "saldo_libros": libros, "_row": 2, **x}


def _g(id, prov, desc, u, pct, costo):
    return {"id": id, "provision": prov, "descripcion": desc, "unidades": u, "pct_reclamos": pct, "costo_medio": costo, "_row": 2}


# Ejemplo de control (M19), corte 2025-12-31, tasa por defecto 8 %, se descuenta si el plazo supera 1 año:
# LIT-01 valor esperado = 150.000×60 % + 80.000×30 % + 0×10 % = 114.000; libros 100.000 → ajuste 14.000; carta 120.000 ≠ libros.
# LIT-02 punto medio (60.000 + 100.000)/2 = 80.000 a 2,5 años al 8 % → 80.000 ÷ 1,08^2,5 (1,212158) = 65.997,97; no registrada.
# LIT-03 posible con 40.000 en libros → revertir; LIT-04 posible sin revelar, sin respuesta del abogado.
# GAR-01 = 12.000×3 %×85 + 5.000×2 %×120 = 30.600 + 12.000 = 42.600; libros 30.000 → 12.600. GA-C sin provisión (5.000).
# ONE-01: costo neto de cumplir = 75.000 − 40.000 de beneficios esperados = 35.000; mín(35.000; 45.000) = 35.000 no provisionado. DES-01 = 500.000 ÷ 1,07^10 = 254.174,65; libros 240.000 → 14.174,65
#   contra el costo; reversión 225.000 × 7 % = 15.750 no registrada. AMB-01 200.000 sin descontar (5 años al 9 % = 129.986,28).
# ACT-01 activo contingente probable registrado por 50.000 → revertir. LIT-05 sentencia posterior 32.000 vs 25.000.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tasaDescuento": 8, "plazoDescuento": 1, "materialidad": 50000, "tolerancia": 1,
                   "mayorProvisiones": 730000},
    "datasets": {
        "provisiones": [
            _pr("LIT-01", "Demanda laboral ex gerente", "Litigio", "100000", obligacion_presente="Sí", probabilidad_abogado="Probable",
                probabilidad_gerencia="Probable", importe_abogado="120000", importe_1="150000", prob_1="60", importe_2="80000", prob_2="30",
                importe_3="0", prob_3="10", plazo_anios="1", respuesta_abogado="Sí", fecha_carta="2026-02-10", revelado="Sí"),
            _pr("LIT-02", "Juicio de impugnación tributaria", "Litigio", "0", obligacion_presente="Sí", probabilidad_abogado="Probable",
                probabilidad_gerencia="Posible", importe_abogado="85000", importe_minimo="60000", importe_maximo="100000", plazo_anios="2.5",
                respuesta_abogado="Sí", fecha_carta="2025-12-15", revelado="No"),
            _pr("LIT-03", "Demanda civil de proveedor", "Litigio", "40000", obligacion_presente="Sí", probabilidad_abogado="Posible",
                importe_abogado="40000", plazo_anios="1", respuesta_abogado="Sí", fecha_carta="2026-02-12", revelado="Sí"),
            _pr("LIT-04", "Reclamo de cliente por entrega tardía", "Litigio", "0", obligacion_presente="No", probabilidad_gerencia="Posible",
                importe_minimo="10000", importe_maximo="30000", respuesta_abogado="No", revelado="No"),
            _pr("GAR-01", "Garantías de electrodomésticos", "Garantía", "30000", obligacion_presente="Sí", probabilidad_gerencia="Probable",
                plazo_anios="1"),
            _pr("ONE-01", "Contrato de suministro con pérdida", "Oneroso", "0", obligacion_presente="Sí", probabilidad_gerencia="Probable",
                costo_cumplir="75000", beneficios_contrato="40000", penalizacion="45000", plazo_anios="0.5"),
            _pr("DES-01", "Desmantelamiento de planta en terreno arrendado", "Desmantelamiento", "240000", obligacion_presente="Sí",
                probabilidad_gerencia="Probable", importe_gerencia="500000", plazo_anios="10", tasa_descuento="7", saldo_inicial="225000"),
            _pr("REE-01", "Reestructuración de la línea textil (plan comunicado)", "Reestructuración", "60000", obligacion_presente="Sí",
                probabilidad_gerencia="Probable", importe_gerencia="60000", plazo_anios="0.5"),
            _pr("AMB-01", "Remediación ambiental de relaves", "Otro", "200000", obligacion_presente="Sí", probabilidad_gerencia="Probable",
                importe_gerencia="200000", plazo_anios="5", tasa_descuento="9", saldo_inicial="190000", reversion_registrada="5000"),
            _pr("LIT-05", "Juicio laboral de operario", "Litigio", "25000", obligacion_presente="Sí", probabilidad_abogado="Probable",
                importe_abogado="25000", importe_posterior="32000", plazo_anios="0.25", respuesta_abogado="Sí", fecha_carta="2026-02-10"),
            _pr("LIT-06", "Demanda por uso de marca", "Litigio", "0", obligacion_presente="No", probabilidad_abogado="Remota",
                respuesta_abogado="Sí", fecha_carta="2026-02-10"),
            _pr("OTR-01", "Multa de la autoridad ambiental", "Otro", "30000", obligacion_presente="Sí", probabilidad_gerencia="Probable",
                importe_1="30000", prob_1="50", importe_2="60000", prob_2="30", importe_3="90000", prob_3="20", metodo="Más probable",
                plazo_anios="1"),
            _pr("ACT-01", "Demanda a la aseguradora por siniestro", "Activo contingente", "50000", probabilidad_abogado="Probable",
                importe_abogado="50000", respuesta_abogado="Sí", fecha_carta="2026-02-10", revelado="No"),
        ],
        "garantias": [
            _g("GA-A", "GAR-01", "Refrigeradoras", "12000", "3", "85"),
            _g("GA-B", "GAR-01", "Lavadoras", "5000", "2", "120"),
            _g("GA-C", "GAR-09", "Microondas", "2000", "5", "50"),
        ],
    },
}

_MIN = {"provisiones": [_pr("P-1", "Provisión sin evaluar", "Otro", "1000")], "garantias": []}
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025"}, EJEMPLO["corte"]),
    ("minimo", _MIN, {}, "2025-12-31"),
]
