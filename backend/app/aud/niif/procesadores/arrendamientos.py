"""Arrendamientos (arrendatario): NIIF 16 en NIIF completas y Sección 20 en la NIIF para las PYMES.

Versión simple que cumple la norma, contrato por contrato:

1. Identificación y exenciones (NIIF 16 párr. 5–8, B3–B8 y definición de «arrendamiento a corto plazo»):
   corto plazo = plazo ≤ 12 meses y sin opción de compra; bajo valor = declarado por el cliente, con el valor del
   activo nuevo dentro del límite del auditor (B3; sin ese dato no es elegible), usable por sí solo y sin depender de
   otros activos (B5), que no sea un automóvil (B6) y que no se subarriende (B7). La exención solo vale si el cliente
   la aplicó y es elegible.
   PYMES: clasificación financiero/operativo con los indicadores de 20.5 (20.4–20.8).
2. Plazo (18–21, B34–B41): período no cancelable + renovación razonablemente cierta.
3. Medición inicial: pasivo = VP de los pagos no abonados (26–27) con la tasa implícita o incremental;
   derecho de uso = pasivo + pagos al comienzo o antes + costos directos + desmantelamiento − incentivos (24).
   PYMES financiero: activo y pasivo al menor entre valor razonable y VP de los pagos mínimos (20.9–20.10);
   si manda el valor razonable, la tasa de interés constante se recalcula (TASA de Excel).
4. Tabla de amortización por contrato: interés = saldo inicial × tasa periódica (36–37 / 20.11).
5. Remedición y modificaciones (39–46): nuevo pago, tasa y plazo desde la fecha del evento; el ajuste del
   pasivo va contra el derecho de uso (39, 46 b).
6. Al corte: pasivo, corriente = capital que se paga en los 12 meses siguientes (NIC 1 párr. 69), interés
   y pagos del ejercicio, depreciación del derecho de uso (31–32 / 20.12) y deterioro (33 / Sección 27).
7. Exentos y operativos PYMES: gasto lineal (6 / 20.15). Venta con arrendamiento posterior (98–103 /
   20.32–20.34).
8. Pago base y componente ligado a un índice de inflación, separados y enrutados por marco:
   · NIIF completas: el componente indexado SÍ entra en la medición del pasivo, con el índice de la fecha
     de comienzo (27 b y 28); solo se remide cuando cambian los flujos (42 b), con la tasa sin cambios (43).
   · NIIF para las PYMES (2015 y 2025, Sección 20 sin cambios de fondo): NO se capitaliza como pago fijo.
     En el financiero es una cuota contingente que se carga como gasto en los períodos en que se incurre
     (20.11) y en el operativo queda fuera del gasto lineal (20.15 b); se revela en 20.13 c / 20.16 c.
   Los pagos variables no ligados a un índice son gasto del período en los dos marcos (38 b / 20.11).
9. Venta con arrendamiento posterior, medición posterior (102A): el pasivo sigue los párrafos 36–46 y el
   derecho de uso conservado los párrafos 29–35, con el control de que después de la fecha de inicio no se
   reconozca ninguna ganancia o pérdida atribuible al derecho de uso conservado.

Cada importe del libro Excel es una fórmula viva que remite a 02_Parametros y 03_Contratos.
"""
from __future__ import annotations

from datetime import date, timedelta

from openpyxl.utils import get_column_letter

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, a_fecha, a_num, campo, es_pymes, edicion_pymes, filas_mapeadas, fx, hoja, m as _m, norm, problema,
    r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "arrendamientos 1.0"
RUBRO = "ARRENDAMIENTOS"

_CONTRATOS = [
    campo("id", "Contrato", alias=("contrato", "codigo", "numero de contrato", "n contrato"), ejemplo="C-01"),
    campo("activo", "Activo subyacente", alias=("activo", "bien", "activo arrendado", "descripcion"), ejemplo="Local comercial"),
    campo("inicio", "Fecha de comienzo", "date", alias=("fecha de comienzo", "fecha inicio", "inicio", "comienzo"), ejemplo="2024-01-01"),
    campo("plazo", "Plazo no cancelable (meses)", "number", alias=("plazo", "plazo meses", "meses"), ejemplo=36),
    campo("renov_meses", "Meses de la opción de renovación", "number", False, ("meses adicionales", "renovacion meses")),
    campo("renov_cierta", "Renovación razonablemente cierta (sí/no)", "text", False, ("renovacion cierta", "razonablemente cierta")),
    campo("plazo_cliente", "Plazo usado por el cliente (meses)", "number", False, ("plazo cliente", "plazo registrado")),
    campo("pago", "Pago periódico total del contrato (incluye el componente indexado)", "number",
          alias=("pago", "cuota", "canon", "pago periodico"), ejemplo=1500),
    campo("periodicidad", "Periodicidad (mensual/trimestral/semestral/anual)", alias=("periodicidad", "frecuencia"), ejemplo="Mensual"),
    campo("momento", "Pago al inicio o al final del período", "text", False, ("momento", "pago anticipado o vencido")),
    campo("indexado", "El pago se ajusta por un índice de inflación (sí/no)", "text", False,
          ("indexado", "ajuste por inflacion", "pago indexado", "ligado a indice")),
    campo("pago_indexado", "Componente del pago ligado al índice (importe por período)", "number", False,
          ("componente indexado", "importe indexado", "ajuste inflacion", "parte variable indexada")),
    campo("indice", "Índice o referencia del ajuste", "text", False, ("indice", "referencia del ajuste", "indice de inflacion")),
    campo("pago_variable", "Pago variable del período no ligado a un índice", "number", False,
          ("pago variable", "renta variable", "cuota contingente")),
    campo("tasa", "Tasa anual (%)", "number", alias=("tasa", "tasa anual", "tasa de descuento"), ejemplo=12),
    campo("tipo_tasa", "Tipo de tasa (implícita/incremental)", "text", False, ("tipo de tasa",)),
    campo("anticipados", "Pagos anticipados antes del comienzo", "number", False, ("pagos anticipados", "anticipos")),
    campo("costos", "Costos directos iniciales", "number", False, ("costos directos",)),
    campo("desmantelamiento", "Costo estimado de desmantelamiento", "number", False, ("desmantelamiento", "restauracion")),
    campo("incentivos", "Incentivos recibidos", "number", False, ("incentivos",)),
    campo("opcion_compra", "Precio de la opción de compra", "number", False, ("opcion de compra", "precio opcion")),
    campo("compra_cierta", "Compra razonablemente cierta (sí/no)", "text", False, ("compra cierta",)),
    campo("vida_util", "Vida útil del activo (meses)", "number", False, ("vida util",)),
    campo("valor_razonable", "Valor razonable del activo (nuevo)", "number", False, ("valor razonable", "valor nuevo")),
    campo("bajo_valor", "Activo de bajo valor (sí/no)", "text", False, ("bajo valor", "escaso valor")),
    campo("bajo_valor_b5b7", "Bajo valor: se usa por sí solo, no depende de otros activos y no se subarrienda (B5, B7) (sí/no)", "text", False,
          ("b5 b7", "uso independiente", "bajo valor b5", "no subarrendado")),
    campo("exencion", "El cliente aplicó la exención (sí/no)", "text", False, ("exencion", "exento")),
    campo("clasif_pymes", "Clasificación PYMES del cliente (financiero/operativo)", "text", False, ("clasificacion", "tipo de arrendamiento")),
    campo("pasivo_reg", "Pasivo por arrendamiento registrado al corte", "number", alias=("pasivo registrado", "saldo pasivo"), ejemplo=0),
    campo("pasivo_cp_reg", "Pasivo corriente registrado", "number", False, ("pasivo corriente", "porcion corriente")),
    campo("activo_reg", "Derecho de uso / activo registrado neto", "number", False, ("derecho de uso", "rou", "activo registrado")),
    campo("dep_reg", "Depreciación registrada del ejercicio", "number", False, ("depreciacion registrada", "amortizacion registrada")),
    campo("int_reg", "Interés registrado del ejercicio", "number", False, ("interes registrado", "gasto financiero")),
    campo("fecha_evento", "Fecha de modificación o nueva evaluación", "date", False, ("fecha modificacion", "fecha evento")),
    campo("tipo_evento", "Tipo de evento (modificación/índice/plazo)", "text", False, ("tipo de evento", "tipo modificacion")),
    campo("nuevo_pago", "Nuevo pago periódico", "number", False, ("nuevo pago",)),
    campo("nueva_tasa", "Tasa anual revisada (%)", "number", False, ("nueva tasa", "tasa revisada")),
    campo("nuevo_plazo", "Plazo total revisado (meses desde el comienzo)", "number", False, ("nuevo plazo", "plazo revisado")),
    campo("remedido", "El cliente remidió el pasivo (sí/no)", "text", False, ("remedido", "remedicion registrada")),
    campo("recuperable", "Importe recuperable del activo", "number", False, ("importe recuperable",)),
    campo("venta_posterior", "Venta con arrendamiento posterior (sí/no)", "text", False, ("sale and leaseback", "venta con arrendamiento")),
    campo("precio_venta", "Precio de venta", "number", False, ("precio de venta",)),
    campo("libros_previo", "Importe en libros antes de la venta", "number", False, ("importe en libros", "valor en libros")),
    campo("ganancia_reg", "Ganancia registrada en la venta", "number", False, ("ganancia registrada", "utilidad en venta")),
    campo("ganancia_post_reg", "Ganancia o pérdida reconocida después de la venta por la medición posterior del arrendamiento",
          "number", False, ("ganancia posterior", "ganancia remedicion", "resultado posterior venta")),
]
CAMPOS = {"contratos": _CONTRATOS}
TIPOS = {"contratos": "contratos"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "contratos"
CONTROL = "pasivo_reg"
TOTAL_EJEMPLO = "pasivo"

CONVENCIONES = ("Efectiva anual", "Nominal anual")
PARAMETROS = {"convencionTasa": "Efectiva anual", "umbralVida": 75, "umbralVP": 90, "limiteBajoValor": 5000}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "convencionTasa": "Tasa anual del contrato (efectiva o nominal)",
    "umbralVida": "PYMES: plazo ≥ % de la vida económica (indicador 20.5 c)",
    "umbralVP": "PYMES: VP de los pagos mínimos ≥ % del valor razonable (indicador 20.5 d)",
    "limiteBajoValor": "Límite de «bajo valor» del activo nuevo (USD)",
}

COL = {c["key"]: get_column_letter(i + 1) for i, c in enumerate(_CONTRATOS)}
MESES = {"Mensual": 1, "Trimestral": 3, "Semestral": 6, "Anual": 12}


def kind(dataset: str) -> str:
    return TIPOS[dataset]


# --- normalización de textos (lo que se escribe en 03_Contratos) ----------------------

def _si(v) -> str:
    s = norm(v)
    if not s:
        return ""
    if s in ("si", "s", "yes", "y", "x", "1", "true", "verdadero"):
        return "Sí"
    if s in ("no", "n", "0", "false", "falso"):
        return "No"
    return "?"


def _periodicidad(v) -> str:
    s = norm(v)
    for k, pref in (("Mensual", ("mens", "1")), ("Trimestral", ("trim", "3")), ("Semestral", ("sem", "6")), ("Anual", ("anu", "12"))):
        if s.startswith(pref[0]) or s == pref[1]:
            return k
    return ""


def _momento(v) -> str:
    return "Inicio" if norm(v).startswith(("inicio", "anticip", "adelant")) else "Final"


# NIIF 16 B6: «los arrendamientos de automóviles no se considerarían arrendamientos de activos de escaso valor, ya
# que un coche nuevo no tiene habitualmente escaso valor». Se deduce del texto del activo, sin pedir un campo nuevo.
# Las variantes con y sin tilde están para que la búsqueda de Excel (SEARCH no ignora tildes) dé lo mismo que Python.
AUTOMOVIL = ("automovil", "automóvil", "vehiculo", "vehículo", "camioneta", "coche", "furgoneta")


def _es_automovil(activo: str) -> bool:
    t = str(activo or "").lower()
    return any(k in t for k in AUTOMOVIL)


def _clasif(v) -> str:
    s = norm(v)
    return "Financiero" if s.startswith("fin") else ("Operativo" if s.startswith("oper") else "")


def _tipo_tasa(v) -> str:
    s = norm(v)
    return "Implícita" if s.startswith("impl") else ("Incremental" if s.startswith("incr") else "")


def _tipo_evento(v) -> str:
    s = norm(v)
    return "Cambio de índice" if "indic" in s or "indice" in s else ("Cambio de plazo" if "plazo" in s else "Modificación")


def validar_filas(tipo: str, filas: list) -> dict:
    r = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        fila = f.get("_row")
        if str(f.get("periodicidad", "") or "").strip() and not _periodicidad(f.get("periodicidad")):
            r["errors"].append({"row": fila, "field": "periodicidad", "message": "Periodicidad: use mensual, trimestral, semestral o anual."})
        for k in ("plazo", "pago", "tasa", "pago_indexado", "pago_variable"):
            x = a_num(f.get(k))
            if x is not None and (x < 0 or (k == "plazo" and x == 0) or (k == "tasa" and x > 100)):
                r["errors"].append({"row": fila, "field": k, "message": f"{next(c['label'] for c in _CONTRATOS if c['key'] == k)}: valor fuera de rango."})
        pi, pg = a_num(f.get("pago_indexado")), a_num(f.get("pago"))
        if pi is not None and pg is not None and pi > pg:
            r["errors"].append({"row": fila, "field": "pago_indexado",
                                "message": "El componente ligado al índice no puede superar el pago periódico total del contrato."})
        for c in _CONTRATOS:
            if "(sí/no)" in c["label"] and _si(f.get(c["key"])) == "?":
                r["errors"].append({"row": fila, "field": c["key"], "message": f"{c['label']}: responda sí o no."})
    r["ok"] = not r["errors"]
    return r


# --- aritmética idéntica a Excel -------------------------------------------------------

def _meses(a: date, b: date) -> int:
    """DATEDIF(a;b;"m"): meses completos."""
    return (b.year - a.year) * 12 + b.month - a.month - (1 if b.day < a.day else 0)


def _edate(d: date, n: int) -> date:
    y, mm = divmod(d.month - 1 + n, 12)
    y, mm = d.year + y, mm + 1
    import calendar
    return date(y, mm, min(d.day, calendar.monthrange(y, mm)[1]))


def _tasa_per(r: float, m: int, conv: str) -> float:
    return r / 100 * m / 12 if conv == "Nominal anual" else (1 + r / 100) ** (m / 12) - 1


def _vp(i: float, n: float, pago: float, fv: float, tipo: int) -> float:
    """VA de Excel con pago = −pago y vf = −fv."""
    if i == 0:
        return pago * n + fv
    return (pago * (1 + i * tipo) * ((1 + i) ** n - 1) / i + fv) / (1 + i) ** n


def _tasa_rate(n: float, pago: float, va: float, fv: float, tipo: int) -> float:
    """TASA de Excel: i tal que VA(i) = va (bisección con precisión de máquina)."""
    lo, hi = 1e-12, 10.0
    if _vp(lo, n, pago, fv, tipo) < va:
        raise ValueError("No existe una tasa positiva que iguale el valor razonable.")
    for _ in range(300):
        mid = (lo + hi) / 2
        if _vp(mid, n, pago, fv, tipo) > va:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _dep(t, roi, md, ev):
    """Depreciación acumulada a t meses (lineal; tras la remedición, el nuevo saldo en el plazo restante)."""
    if not ev:
        return roi * min(t, md) / md
    me, aj, md2 = ev["me"], ev["ajuste"], ev["md2"]
    if t <= me:
        return roi * min(t, md) / md
    return roi * min(me, md) / md + (roi * (1 - min(me, md) / md) + aj) * min(t - me, md2 - me) / (md2 - me)


# --- cálculo ---------------------------------------------------------------------------

def _contratos(filas: list, corte: date, p: dict, pymes: bool, probs: list) -> list:
    out = []
    conv = p["convencionTasa"]
    fin = corte + timedelta(days=1)
    for f in filas or []:
        g = lambda k: a_num(f.get(k))
        n0 = lambda k: g(k) or 0.0
        cid = str(f.get("id", "") or "").strip()
        inicio = a_fecha(f.get("inicio"))
        if not cid or inicio is None or g("plazo") is None or g("pago") is None or g("tasa") is None:
            raise ValueError(f"Contrato {cid or '(sin código)'}: faltan fecha de comienzo, plazo, pago o tasa.")
        per = _periodicidad(f.get("periodicidad"))
        if not per:
            raise ValueError(f"Contrato {cid}: periodicidad no reconocida.")
        if inicio > corte:
            probs.append(problema("NO_COMENZADO", f"{cid}: comienza el {inicio.isoformat()}, después del corte; no se reconoce todavía (22)."))
            continue
        m = MESES[per]
        c = {"id": cid, "activo": str(f.get("activo", "") or "").strip(), "inicio": inicio, "per": per, "periodicidad": per, "m": m,
             "plazo": g("plazo"), "renov_meses": g("renov_meses"), "renov_cierta": _si(f.get("renov_cierta")),
             "plazo_cliente": g("plazo_cliente"), "pago": g("pago"), "momento": _momento(f.get("momento")),
             "indexado": _si(f.get("indexado")), "pago_indexado": g("pago_indexado"), "pago_variable": g("pago_variable"),
             "indice": str(f.get("indice", "") or "").strip(), "ganancia_post_reg": g("ganancia_post_reg"),
             "tasa": g("tasa"), "tipo_tasa": _tipo_tasa(f.get("tipo_tasa")), "anticipados": g("anticipados"),
             "costos": g("costos"), "desmantelamiento": g("desmantelamiento"), "incentivos": g("incentivos"),
             "opcion_compra": g("opcion_compra"), "compra_cierta": _si(f.get("compra_cierta")), "vida_util": g("vida_util"),
             "valor_razonable": g("valor_razonable"), "bajo_valor": _si(f.get("bajo_valor")),
             "bajo_valor_b5b7": _si(f.get("bajo_valor_b5b7")), "exencion": _si(f.get("exencion")),
             "clasif_pymes": _clasif(f.get("clasif_pymes")), "pasivo_reg": n0("pasivo_reg"), "pasivo_cp_reg": g("pasivo_cp_reg"),
             "activo_reg": n0("activo_reg"), "dep_reg": g("dep_reg"), "int_reg": g("int_reg"),
             "fecha_evento": a_fecha(f.get("fecha_evento")), "tipo_evento": _tipo_evento(f.get("tipo_evento")) if a_fecha(f.get("fecha_evento")) else "",
             "nuevo_pago": g("nuevo_pago"), "nueva_tasa": g("nueva_tasa"), "nuevo_plazo": g("nuevo_plazo"), "remedido": _si(f.get("remedido")),
             "recuperable": g("recuperable"), "venta_posterior": _si(f.get("venta_posterior")), "precio_venta": g("precio_venta"),
             "libros_previo": g("libros_previo"), "ganancia_reg": g("ganancia_reg"), "_row": f.get("_row")}
        # 2 · plazo
        c["plazo_total"] = c["plazo"] + ((c["renov_meses"] or 0) if c["renov_cierta"] == "Sí" else 0)
        c["n"] = c["plazo_total"] / m
        if c["n"] != int(c["n"]):
            raise ValueError(f"Contrato {cid}: el plazo de {c['plazo_total']:g} meses no es múltiplo de la periodicidad ({per}).")
        c["M"] = _meses(inicio, fin)
        vu = c["vida_util"]
        c["md"] = (vu if vu is not None else c["plazo_total"]) if c["compra_cierta"] == "Sí" else (c["plazo_total"] if vu is None else min(c["plazo_total"], vu))
        # 1 · identificación
        c["opcion"] = "Sí" if (c["opcion_compra"] or 0) > 0 else "No"
        c["corto"] = "Sí" if c["plazo_total"] <= 12 and c["opcion"] == "No" else "No"
        c["bv"] = c["bajo_valor"] or "No"
        # B3: el valor se evalúa con el del activo en su estado nuevo (sin ese dato no hay exención, ya no se acepta en
        # blanco); B5: debe poder usarse por sí solo o con recursos disponibles y no depender de otros activos;
        # B6: un automóvil (coche nuevo) nunca es de escaso valor; B7: queda excluido si se subarrienda.
        c["bv_auto"] = "Sí" if _es_automovil(c["activo"]) else "No"
        c["bv_limite"] = "No" if (c["bv"] == "No" or c["valor_razonable"] is None or c["valor_razonable"] > p["limiteBajoValor"]
                                  or c["bv_auto"] == "Sí" or c["bajo_valor_b5b7"] == "No") else "Sí"
        c["elegible"] = "Sí" if "Sí" in (c["corto"], c["bv_limite"]) else "No"
        c["ex"] = c["exencion"] or "No"
        # 8 · pago base y componente ligado a un índice de inflación (27 b y 28 / 20.11 y 20.15 b)
        if c["pago_indexado"] is not None and c["pago_indexado"] > c["pago"]:
            raise ValueError(f"Contrato {cid}: el componente ligado al índice ({c['pago_indexado']:g}) supera el pago periódico "
                             f"total del contrato ({c['pago']:g}).")
        c["ind_decl"] = "Sí" if (c["indexado"] == "Sí" or c["pago_indexado"] is not None) else "No"
        if c["ind_decl"] == "Sí" and c["pago_indexado"] is None:
            # M22: sin el importe no se puede separar; base y componente quedan vacíos y se emite el problema.
            c["pago_ind"] = c["pago_base"] = None
            c["pago_medido"] = c["pago"]
        else:
            c["pago_ind"] = c["pago_indexado"] or 0.0
            c["pago_base"] = c["pago"] - c["pago_ind"]
            c["pago_medido"] = c["pago_base"] if pymes else c["pago"]
        # 3 · medición inicial
        c["i"] = _tasa_per(c["tasa"], m, conv)
        c["tipo"] = 1 if c["momento"] == "Inicio" else 0
        c["opt"] = (c["opcion_compra"] or 0) if c["compra_cierta"] == "Sí" else 0
        c["vp"] = _vp(c["i"], c["n"], c["pago_medido"], c["opt"], c["tipo"])
        c["p0"] = c["tipo"] * c["pago_medido"]
        vr = c["valor_razonable"]
        if pymes:
            c["pv_vida"] = None if vu is None else c["plazo_total"] / vu
            c["pv_vr"] = None if vr is None else c["vp"] / vr
            c["cc"] = c["compra_cierta"] or "No"
            ind = c["cc"] == "Sí" or (c["pv_vida"] is not None and c["pv_vida"] >= p["umbralVida"] / 100) \
                or (c["pv_vr"] is not None and c["pv_vr"] >= p["umbralVP"] / 100)
            c["indicador"] = "Sí" if ind else "No"
            c["clasif"] = "Financiero" if ind or c["clasif_pymes"] == "Financiero" else "Operativo"
            c["reconoce"] = "Sí" if c["clasif"] == "Financiero" else "No"
            c["base"] = c["vp"] if vr is None else min(vr, c["vp"])
            c["i_used"] = c["i"] if vr is None or vr >= c["vp"] else _tasa_rate(c["n"], c["pago_medido"], vr, c["opt"], c["tipo"])
            c["pasivo_ini"] = c["base"] - c["p0"]
            c["activo_ini"] = c["base"] + (c["costos"] or 0)
        else:
            c["reconoce"] = "No" if c["ex"] == "Sí" and c["elegible"] == "Sí" else "Sí"
            c["base"] = c["vp"]
            c["i_used"] = c["i"]
            c["pasivo_ini"] = c["vp"] - c["p0"]
            c["activo_ini"] = c["pasivo_ini"] + c["p0"] + (c["anticipados"] or 0) + (c["costos"] or 0) \
                + (c["desmantelamiento"] or 0) - (c["incentivos"] or 0)
        c["trat_indexado"], c["marco_indexado"] = _trato_indexado(c, pymes, edicion_pymes(p))
        c["ev"] = None
        c["nota_evento"] = ""
        c["slb"] = None
        out.append(c)
    return out


def _trato_indexado(c: dict, pymes: bool, edicion: str) -> tuple:
    """Tratamiento del componente ligado a un índice y el marco que lo manda (para la cédula 07)."""
    if c["ind_decl"] == "No":
        return "Sin componente ligado a un índice", ""
    if c["pago_ind"] is None:
        return ("No medible: falta el importe del componente",
                "El pago base y el componente quedan vacíos hasta que el cliente informe el importe")
    if not pymes:
        return ("Incluido en la medición del pasivo con el índice de la fecha de comienzo",
                "NIIF completas · NIIF 16 párr. 27 b y 28; se remide solo cuando cambian los flujos (42 b), "
                "con la tasa de descuento sin cambios (43)")
    marco = f"NIIF para las PYMES {edicion} · Sección 20"
    if c["clasif"] == "Financiero":
        return ("Excluido de los pagos mínimos: cuota contingente, gasto del período en que se incurre",
                f"{marco}.11 (medición posterior) y 20.9–20.10 (pagos mínimos); se revela en 20.13 c")
    return ("Excluido del gasto lineal: gasto del período por el importe devengado",
            f"{marco}.15 b (pagos estructurados para seguir la inflación general esperada); se revela en 20.16 b y c")


def _evento(c: dict, corte: date, pymes: bool, conv: str, probs: list):
    """Remedición o modificación (39–46): devuelve los datos del evento aplicado o None con nota."""
    fe = c["fecha_evento"]
    if fe is None:
        return
    if pymes:
        c["nota_evento"] = "No aplica: la Sección 20 no tiene remedición; evalúe reclasificación (20.8)"
        probs.append(problema("PYMES_EVENTO", f"{c['id']}: evento del {fe.isoformat()} no remedido con el modelo NIIF 16; la Sección 20 solo exige reevaluar la clasificación si arrendador y arrendatario acuerdan cambiar las cláusulas, distinto de una simple renovación (20.8)."))
        return
    if c["reconoce"] == "No":
        c["nota_evento"] = "No aplica: contrato exento (si es de corto plazo, la modificación lo convierte en arrendamiento nuevo, 7; si es de escaso valor, sigue el párrafo 6)"
        return
    ke = int(_meses(c["inicio"], fe) // c["m"]) if fe >= c["inicio"] else -1
    plazo2 = c["nuevo_plazo"] if c["nuevo_plazo"] is not None else c["plazo_total"]
    n2 = plazo2 / c["m"]
    if fe > corte or ke < 1 or ke >= c["n"] or ke >= n2 or n2 != int(n2):
        c["nota_evento"] = "No aplica: fecha fuera del plazo, posterior al corte o plazo revisado no múltiplo de la periodicidad"
        probs.append(problema("EVENTO_NO_APLICADO", f"{c['id']}: el evento del {fe.isoformat()} no se aplicó (debe ocurrir al menos un período después del comienzo, dentro del plazo y hasta el corte)."))
        return
    p2 = c["nuevo_pago"] if c["nuevo_pago"] is not None else c["pago_medido"]
    t2 = c["nueva_tasa"] if c["nueva_tasa"] is not None else c["tasa"]
    i2 = _tasa_per(t2, c["m"], conv)
    revisado = _vp(i2, n2 - ke, p2, c["opt"], c["tipo"]) - c["tipo"] * p2
    vu = c["vida_util"]
    md2 = c["md"] if c["compra_cierta"] == "Sí" else (plazo2 if vu is None else min(plazo2, vu))
    c["ev"] = {"ke": ke, "plazo2": plazo2, "n2": n2, "p2": p2, "t2": t2, "i2": i2, "revisado": revisado, "me": ke * c["m"], "md2": md2}
    if c["tipo_evento"] == "Cambio de índice" and c["nueva_tasa"] is not None:
        probs.append(problema("TASA_EN_CAMBIO_DE_INDICE", f"{c['id']}: un cambio de índice se remide con la tasa sin cambios (42 b, 43), salvo tasas variables; se usó la tasa revisada indicada: justifíquela."))


def _tabla(c: dict) -> list:
    ev = c["ev"]
    nmax = int(ev["n2"] if ev else c["n"])
    filas, saldo = [], c["pasivo_ini"]
    for j in range(1, nmax + 1):
        nuevo = ev is not None and j > ev["ke"]
        i = ev["i2"] if nuevo else c["i_used"]
        pg = ev["p2"] if nuevo else c["pago_medido"]
        ne = ev["n2"] if nuevo else c["n"]
        ini = saldo
        inte = ini * i
        pago = pg if j < ne else (c["opt"] + (1 - c["tipo"]) * pg if j == ne else 0)
        fin = ini + inte - pago
        aj = ev["revisado"] - fin if ev is not None and j == ev["ke"] else 0
        saldo = fin + aj
        filas.append({"id": c["id"], "j": j, "vence": _edate(c["inicio"], j * c["m"]).isoformat(), "tasa": i, "ini": ini,
                      "interes": inte, "pago": pago, "fin": fin, "ajuste": aj, "saldo": saldo, "nuevo": nuevo})
    return filas


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = a_fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    if p["convencionTasa"] not in CONVENCIONES:
        raise ValueError("Tasa anual: elija «Efectiva anual» o «Nominal anual».")
    for k in ("umbralVida", "umbralVP"):
        v = a_num(p[k])
        if v is None or not 0 < v <= 100:
            raise ValueError(f"{ETIQUETAS_PARAM[k]}: use un porcentaje entre 0 y 100.")
        p[k] = v
    p["limiteBajoValor"] = a_num(p["limiteBajoValor"])
    if p["limiteBajoValor"] is None or p["limiteBajoValor"] < 0:
        raise ValueError("Límite de bajo valor: indique un importe no negativo.")
    pymes = es_pymes(p)
    if not datasets.get("contratos"):
        raise ValueError("Cargue el anexo de contratos de arrendamiento.")
    probs = []
    cs = _contratos(datasets.get("contratos"), corte_a, p, pymes, probs)
    if not cs:
        raise ValueError("Ningún contrato ha comenzado a la fecha de corte.")
    vistos = set()
    for c in cs:
        if c["id"].lower() in vistos:
            raise ValueError(f"Contrato repetido: {c['id']}. Cada contrato debe tener un código único.")
        vistos.add(c["id"].lower())

    tabla = []
    for c in cs:
        _evento(c, corte_a, pymes, p["convencionTasa"], probs)
        c["tabla"] = _tabla(c) if c["reconoce"] == "Sí" else []
        tabla += c["tabla"]
        ev = c["ev"]
        if ev:
            ev["antes"] = _fin_ke(c)
            ev["ajuste"] = ev["revisado"] - ev["antes"]
        # venta con arrendamiento posterior (NIIF 16 100–102 / Sección 20.32–20.34)
        if c["venta_posterior"] == "Sí":
            pv_, vr, lb = c["precio_venta"], c["valor_razonable"], c["libros_previo"]
            if pv_ is None or lb is None or vr is None or vr <= 0:
                probs.append(problema("VENTA_SIN_DATOS", f"{c['id']}: venta con arrendamiento posterior sin precio, valor razonable o importe en libros previo."))
            elif pymes:
                fin_ = c["clasif"] == "Financiero"
                c["slb"] = {"inmediata": min(pv_ - lb, 0) if fin_ else min(pv_, vr) - lb,
                            "diferida": max(pv_ - lb, 0) if fin_ else max(pv_ - vr, 0)}
            else:
                finan, prep = max(pv_ - vr, 0), max(vr - pv_, 0)
                parte = c["pasivo_ini"] - finan + prep
                c["slb"] = {"financiacion": finan, "prepago": prep, "parte": parte, "rou": lb * parte / vr,
                            "total": vr - lb, "inmediata": (vr - lb) * (vr - parte) / vr}
                if c["reconoce"] == "Sí":
                    c["activo_ini"] = c["slb"]["rou"]
        # 6 · al corte
        c["nmax"] = ev["n2"] if ev else c["n"]
        M, m = c["M"], c["m"]
        c["k"] = min(c["nmax"], max(M, 0) // m)
        c["kp"] = min(c["nmax"], max(M - 12, 0) // m)
        c["q"] = 12 / m
        saldo = {x["j"]: x["saldo"] for x in c["tabla"]}
        rango = lambda a, b, key: sum(x[key] for x in c["tabla"] if a < x["j"] <= b)
        if c["reconoce"] == "Sí":
            c["pasivo"] = c["pasivo_ini"] if c["k"] == 0 else saldo[int(c["k"])]
            c["pasivo_ia"] = 0 if M < 12 else (c["pasivo_ini"] if c["kp"] == 0 else saldo[int(c["kp"])])
            c["altas"] = c["pasivo_ini"] if M < 12 else 0
            c["interes"] = rango(c["kp"], c["k"], "interes")
            c["pagos"] = rango(c["kp"], c["k"], "pago")
            c["remedicion"] = rango(c["kp"], c["k"], "ajuste")
            c["comprobacion"] = c["pasivo_ia"] + c["altas"] + c["interes"] - c["pagos"] + c["remedicion"] - c["pasivo"]
            c["pasivo12"] = saldo[int(min(c["k"] + c["q"], c["nmax"]))]
            c["cp"] = c["pasivo"] - c["pasivo12"]
            c["lp"] = c["pasivo12"]
            i_sig = ev["i2"] if ev and c["k"] + 1 > ev["ke"] else c["i_used"]
            c["devengo"] = 0 if c["k"] >= c["nmax"] else c["pasivo"] * i_sig * (M - c["k"] * m) / m
            c["dep_acum"] = _dep(max(M, 0), c["activo_ini"], c["md"], ev)
            c["dep_ia"] = _dep(max(max(M, 0) - 12, 0), c["activo_ini"], c["md"], ev)
            c["dep"] = c["dep_acum"] - c["dep_ia"]
            c["neto_antes"] = c["activo_ini"] + (ev["ajuste"] if ev else 0) - c["dep_acum"]
            c["deterioro"] = 0 if c["recuperable"] is None else max(0, c["neto_antes"] - c["recuperable"])
            c["neto"] = c["neto_antes"] - c["deterioro"]
            c["gasto"] = 0.0
        else:
            for k in ("pasivo", "interes", "pagos", "remedicion", "cp", "lp", "devengo", "dep", "deterioro", "neto"):
                c[k] = 0.0
            # 7 · gasto lineal de exentos y operativos
            c["pagos_tot"] = c["pago_medido"] * c["n"]
            c["meses_anio"] = min(max(M, 0), c["plazo_total"]) - min(max(M - 12, 0), c["plazo_total"])
            c["gasto"] = c["pagos_tot"] / c["plazo_total"] * c["meses_anio"]
        # 8 · gasto del ejercicio por pagos variables (38 b / 20.11 y 20.15 b)
        c["q_anio"] = (c["k"] - c["kp"]) if c["reconoce"] == "Sí" else c["meses_anio"] / c["m"]
        var_ind = c["pago_ind"] if pymes else 0.0
        c["gasto_variable"] = None if var_ind is None else ((var_ind or 0.0) + (c["pago_variable"] or 0.0)) * c["q_anio"]

    # problemas
    for c in cs:
        cid, dif = c["id"], c["pasivo"] - c["pasivo_reg"]
        if abs(dif) > 0.005:
            probs.append(problema("PASIVO_DIFERENCIA", f"{cid}: pasivo recalculado {_m(c['pasivo'])} vs registrado {_m(c['pasivo_reg'])}.", dif))
        if c["bv"] == "Sí" and not pymes:
            if c["bv_auto"] == "Sí":
                probs.append(problema("BAJO_VALOR_VEHICULO", f"{cid}: «{c['activo']}» se declaró de bajo valor, pero un automóvil (coche nuevo) no "
                                      "tiene habitualmente escaso valor y no puede calificar como tal (B6); reconozca el arrendamiento (22).", c["pasivo"]))
            elif c["valor_razonable"] is None:
                probs.append(problema("BAJO_VALOR_SIN_VALOR", f"{cid}: bajo valor declarado sin el valor del activo nuevo. B3 exige evaluarlo sobre el "
                                      "valor del activo en su estado nuevo, con independencia de su antigüedad: sin ese dato la exención no se acepta. "
                                      "Indique el valor del bien nuevo (no el del bien usado ni el valor razonable del contrato).", c["pasivo"]))
            elif c["bajo_valor_b5b7"] == "No":
                probs.append(problema("BAJO_VALOR_B5_B7", f"{cid}: el activo no se puede usar por sí solo o con recursos fácilmente disponibles, depende "
                                      "de otros activos o está subarrendado: no califica como de escaso valor (B5, B7); reconozca el arrendamiento (22).",
                                      c["pasivo"]))
            elif c["bajo_valor_b5b7"] == "":
                probs.append(problema("BAJO_VALOR_B5_B7", f"{cid}: exención de bajo valor sin evidencia de B5 y B7. Confirme que el arrendatario puede "
                                      "beneficiarse del uso del activo por sí solo o junto con recursos fácilmente disponibles, que el activo no depende "
                                      "en medida apreciable de otros ni está estrechamente interrelacionado con ellos (B5) y que no se subarrienda (B7)."))
        if not pymes and c["ex"] == "Sí" and c["elegible"] == "No":
            probs.append(problema("EXENCION_MAL_APLICADA", f"{cid}: se trató como exento pero no es de corto plazo (≤ 12 meses y sin opción de compra) ni de bajo valor (5, B3–B8); debe reconocerse (22).", c["pasivo"]))
        if c["renov_cierta"] == "Sí" and c["plazo_cliente"] is not None and c["plazo_cliente"] < c["plazo_total"]:
            probs.append(problema("RENOVACION_NO_INCLUIDA", f"{cid}: la renovación es razonablemente cierta pero el cliente usó {c['plazo_cliente']:g} meses en vez de {c['plazo_total']:g} (18 a, B37)."))
        if c["reconoce"] == "Sí" and c["pasivo_cp_reg"] is not None and abs(c["cp"] - c["pasivo_cp_reg"]) > 0.005:
            probs.append(problema("CLASIFICACION_CP_LP", f"{cid}: pasivo corriente recalculado {_m(c['cp'])} (capital de los próximos 12 meses) vs registrado {_m(c['pasivo_cp_reg'])}.", c["cp"] - c["pasivo_cp_reg"]))
        if c["ev"] and c["remedido"] == "No":
            probs.append(problema("MODIFICACION_NO_REMEDIDA", f"{cid}: {c['tipo_evento'].lower()} del {c['fecha_evento'].isoformat()} no remedida por el cliente (39–46); ajuste al pasivo y al derecho de uso.", c["ev"]["ajuste"]))
        if pymes and c["reconoce"] == "No" and (c["activo_reg"] > 0.005 or c["pasivo_reg"] > 0.005):
            probs.append(problema("PYMES_DERECHO_USO", f"{cid}: arrendamiento operativo en PYMES con activo o pasivo registrado. La Sección 20 no tiene «derecho de uso»: el pago se reconoce como gasto lineal (20.15).", c["pasivo_reg"]))
        if pymes and c["indicador"] == "Sí" and c["clasif_pymes"] != "Financiero":
            probs.append(problema("CLASIFICACION_PYMES", f"{cid}: los indicadores de 20.5 señalan arrendamiento financiero y el cliente lo clasificó como «{c['clasif_pymes'] or 'sin clasificar'}» (20.4–20.7)."))
        if c["deterioro"] > 0.005:
            probs.append(problema("DETERIORO", f"{cid}: el importe recuperable ({_m(c['recuperable'])}) es menor que el importe en libros; deterioro {'(Sección 27, 20.12)' if pymes else '(33, NIC 36)'}.", c["deterioro"]))
        if c["reconoce"] == "Sí" and abs(c["neto"] - c["activo_reg"]) > 0.005:
            probs.append(problema("ACTIVO_DIFERENCIA", f"{cid}: {'activo arrendado' if pymes else 'derecho de uso'} recalculado {_m(c['neto'])} vs registrado {_m(c['activo_reg'])}.", c["neto"] - c["activo_reg"]))
        if c["reconoce"] == "Sí" and c["dep_reg"] is not None and abs(c["dep"] - c["dep_reg"]) > 0.005:
            probs.append(problema("DEPRECIACION_DIFERENCIA", f"{cid}: depreciación del ejercicio recalculada {_m(c['dep'])} vs registrada {_m(c['dep_reg'])}.", c["dep"] - c["dep_reg"]))
        if c["reconoce"] == "Sí" and c["int_reg"] is not None and abs(c["interes"] - c["int_reg"]) > 0.005:
            probs.append(problema("INTERES_DIFERENCIA", f"{cid}: interés del ejercicio recalculado {_m(c['interes'])} vs registrado {_m(c['int_reg'])}.", c["interes"] - c["int_reg"]))
        if c["compra_cierta"] == "Sí" and c["vida_util"] is None:
            probs.append(problema("VIDA_UTIL_FALTANTE", f"{cid}: compra razonablemente cierta sin vida útil: se depreció en el plazo; la norma exige la vida útil del activo (32 / 20.12)."))
        if c["reconoce"] == "Sí" and c["devengo"] > 0.005:
            probs.append(problema("INTERES_DEVENGADO_NO_VENCIDO", f"{cid}: el corte cae dentro de un período de pago; interés devengado no incluido en el recálculo ≈ {_m(c['devengo'])} (37). Evalúe si es material.", c["devengo"]))
        if c["ind_decl"] == "Sí" and c["pago_ind"] is None:
            probs.append(problema("INDEXADO_SIN_IMPORTE", f"{cid}: el pago se declaró ajustado por un índice de inflación pero no se informó el "
                                  "importe del componente: el pago base y el componente quedan vacíos. Bajo la NIIF para las PYMES no se puede "
                                  "separar la cuota contingente del pago mínimo (20.11) ni del gasto lineal (20.15 b), y bajo NIIF completas no se "
                                  "puede comprobar la medición con el índice del comienzo (27 b) ni la remedición por cambio de índice (42 b). "
                                  "Pida al cliente el detalle de la factura o liquidación del período que separa la renta base del reajuste."))
        elif pymes and (c["pago_ind"] or 0) > 0:
            probs.append(problema("INDEXADO_PYMES_GASTO", f"{cid}: el componente ligado a «{c['indice'] or 'un índice de inflación'}» "
                                  f"({_m(c['pago_ind'])} por período) se excluyó de la medición y se reconoce como gasto del ejercicio por "
                                  f"{_m(c['gasto_variable'])} ({'cuota contingente, 20.11' if c['clasif'] == 'Financiero' else '20.15 b'}). "
                                  f"Revise el mayor de gastos de arrendamiento y la nota de revelación: la Sección 20 exige describir las cuotas "
                                  f"contingentes y las cláusulas de revisión ({'20.13 c' if c['clasif'] == 'Financiero' else '20.16 b y c'}).",
                                  c["gasto_variable"]))
        elif not pymes and (c["pago_ind"] or 0) > 0 and c["ev"] is None:
            probs.append(problema("INDEXADO_REMEDICION", f"{cid}: el pago incluye un componente ligado a «{c['indice'] or 'un índice'}» "
                                  f"({_m(c['pago_ind'])} por período) medido con el índice de la fecha de comienzo (27 b, 28) y en el ejercicio no "
                                  "se registró ninguna remedición. Revise las notificaciones de reajuste del arrendador y las facturas del período: "
                                  "si el ajuste de los pagos surtió efecto, el párrafo 42 b exige remedir el pasivo con la tasa de descuento sin "
                                  "cambios (43).", c["pago_ind"] * c["q_anio"]))
        if c["venta_posterior"] == "Sí" and c["ganancia_post_reg"] is None:
            probs.append(problema("VENTA_102A_SIN_DATO", f"{cid}: venta con arrendamiento posterior sin el resultado reconocido después de la "
                                  "venta por la medición posterior del arrendamiento. El control del párrafo 102A queda vacío y no se puede "
                                  "concluir: no se asume que sea cero. Solicite el mayor de la cuenta de resultados donde se registró la "
                                  "ganancia o pérdida de la operación (o la nota de la venta con arrendamiento posterior) y confirme si después "
                                  "de la fecha de inicio se llevó a resultados algún importe atribuible al derecho de uso conservado."))
        if c["venta_posterior"] == "Sí" and c["ganancia_post_reg"] is not None and abs(c["ganancia_post_reg"]) > 0.005:
            probs.append(problema("VENTA_GANANCIA_POSTERIOR", f"{cid}: después de la fecha de inicio se reconoció en resultados "
                                  f"{_m(c['ganancia_post_reg'])} por la medición posterior de la venta con arrendamiento posterior. El párrafo 102A "
                                  "exige determinar los pagos (y los pagos revisados) de forma que no se reconozca ningún importe de ganancia o "
                                  "pérdida relacionado con el derecho de uso que el vendedor-arrendatario conserva; la remedición va contra el "
                                  "derecho de uso (39). Solo se admite el resultado de una terminación parcial o total del arrendamiento (46 a): "
                                  "revise el detalle del asiento y el soporte de la terminación.", c["ganancia_post_reg"]))
        if c["slb"] and c["ganancia_reg"] is not None and abs(c["slb"]["inmediata"] - c["ganancia_reg"]) > 0.005:
            probs.append(problema("VENTA_GANANCIA", f"{cid}: ganancia a reconocer en la venta {_m(c['slb']['inmediata'])} vs registrada {_m(c['ganancia_reg'])} ({'20.33–20.34' if pymes else '100 a'}).", c["slb"]["inmediata"] - c["ganancia_reg"]))

    T = lambda k: sum(c.get(k) or 0 for c in cs)
    pasivo, reg = T("pasivo"), T("pasivo_reg")
    activo, activo_reg = T("neto"), sum(c["activo_reg"] for c in cs)
    totales = {"pasivoRegistrado": reg, "pasivo": pasivo, "ajuste": pasivo - reg, "corriente": T("cp"), "noCorriente": T("lp"),
               "activo": activo, "activoRegistrado": activo_reg, "ajusteActivo": activo - activo_reg, "depreciacion": T("dep"),
               "intereses": T("interes"), "deterioro": T("deterioro"), "gastoLineal": T("gasto"),
               "gastoVariable": T("gasto_variable"), "remedicion": sum(c["ev"]["ajuste"] for c in cs if c["ev"])}
    etiquetas = {"pasivoRegistrado": "Pasivo por arrendamiento registrado (mayor)", "pasivo": "Pasivo por arrendamiento recalculado",
                 "ajuste": "Ajuste propuesto al pasivo", "corriente": "Pasivo corriente recalculado", "noCorriente": "Pasivo no corriente recalculado",
                 "activo": ("Activo arrendado neto recalculado" if pymes else "Derecho de uso neto recalculado"), "activoRegistrado": "Activo registrado neto",
                 "ajusteActivo": "Ajuste propuesto al activo", "depreciacion": "Depreciación del ejercicio", "intereses": "Interés del ejercicio",
                 "deterioro": "Deterioro del activo", "gastoLineal": "Gasto lineal (exentos / operativos)",
                 "gastoVariable": "Gasto del ejercicio por pagos variables (38 b / 20.11 y 20.15 b)", "remedicion": "Remedición del pasivo"}
    rows = [{"id": c["id"], "activo": c["activo"], "inicio": c["inicio"].isoformat(), "plazo": f"{c['plazo_total']:g}",
             "reconoce": c["reconoce"], "pasivo": r2(c["pasivo"]), "pasivo_reg": r2(c["pasivo_reg"]), "ajuste": r2(c["pasivo"] - c["pasivo_reg"]),
             "cp": r2(c["cp"]), "activo_neto": r2(c["neto"]), "_row": c["_row"]} for c in cs]
    for c in cs:
        c["inicio"] = c["inicio"].isoformat()
        c["fecha_evento"] = c["fecha_evento"].isoformat() if c["fecha_evento"] else None
    detalle = {"contratos": cs, "tabla": tabla, "parametros": p, "pymes": pymes, "edicion": edicion_pymes(p) if pymes else "",
               "corte": corte_a.isoformat(), "totales": totales}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(v) for k, v in totales.items()}, "labels": etiquetas,
            "primary": "ajuste", "exceptions": probs, "schedule": [], "detalle": detalle}


def _fin_ke(c: dict) -> float:
    """Saldo final (antes de la remedición) del período del evento."""
    ke = c["ev"]["ke"]
    return next(x["fin"] for x in c["tabla"] if x["j"] == ke)


# --- cédulas con fórmulas -------------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Contratos", "Universo de contratos"),
    ("04_Identificacion", "Identificación, clasificación y exenciones"), ("05_Plazo", "Plazo y opciones"),
    ("06_Medicion_inicial", "Medición inicial: pasivo y activo"),
    ("07_Pagos_variables", "Pago base, componente indexado y pagos variables"),
    ("08_Remedicion", "Remedición y modificaciones"), ("09_Tabla_amortizacion", "Tabla de amortización"),
    ("10_Pasivo_corte", "Pasivo al corte: corriente y no corriente"), ("11_Derecho_uso", "Depreciación y deterioro del activo"),
    ("12_Gasto_lineal", "Gasto lineal: exentos y operativos"),
    ("13_Venta_arr_posterior", "Venta con arrendamiento posterior: medición inicial"),
    ("14_Venta_medicion_post", "Venta con arrendamiento posterior: medición posterior"),
    ("15_Conciliacion", "Conciliación y ajuste"), ("16_Problemas", "Problemas encontrados"),
]
P = ref("02_Parametros")
CT, ID, PL, MI, PG, RE, TA, PC, DU, GL, VA = (ref(n) for n in ("03_Contratos", "04_Identificacion", "05_Plazo", "06_Medicion_inicial",
                                                              "07_Pagos_variables", "08_Remedicion", "09_Tabla_amortizacion",
                                                              "10_Pasivo_corte", "11_Derecho_uso", "12_Gasto_lineal",
                                                              "13_Venta_arr_posterior"))
PAR = {k: FILA0 + i for i, k in enumerate(["corte", "conv", "umbralVida", "umbralVP", "limiteBajoValor", "marco"])}


def _x(key: str, r: int) -> str:
    return f"{CT}{COL[key]}{r}"


def _conv(tasa: str, meses: str) -> str:
    return f'IF({P}$B${PAR["conv"]}="Nominal anual",{tasa}/100*{meses}/12,(1+{tasa}/100)^({meses}/12)-1)'


def _txt(key, r, v, defecto=""):
    """Texto de 03_Contratos sin que la celda vacía se lea como 0."""
    return fx(f'IF({_x(key, r)}="","{defecto}",{_x(key, r)})', v or defecto)


def _dep_f(t: str, r: int, ev: bool) -> str:
    C, D, F, G, H = f"C{r}", f"D{r}", f"F{r}", f"G{r}", f"H{r}"
    base = f"{C}*MIN({t},{D})/{D}"
    if not ev:
        return base
    return f"IF({t}<={F},{base},{C}*MIN({F},{D})/{D}+({C}*(1-MIN({F},{D})/{D})+{G})*MIN({t}-{F},{H}-{F})/({H}-{F}))"


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    cs, p, pymes = d["contratos"], d["parametros"], d["pymes"]
    N = len(cs)
    tab = d["tabla"]
    nt = max(len(tab), 1)
    rng = lambda hoja_, col: f"{hoja_}${col}${FILA0}:${col}${FILA0 + nt - 1}"
    TA_A, TA_B = rng(TA, "A"), rng(TA, "B")
    reconoce_col = "M"

    parametros = [
        ["Fecha de corte", d["corte"], "Ficha del encargo"],
        ["Tasa anual del contrato", p["convencionTasa"], "Efectiva: (1 + r)^(meses/12) − 1 · Nominal: r × meses/12"],
        ["PYMES: plazo ≥ % de la vida económica", float(p["umbralVida"]), "Indicador 20.5 c; umbral de juicio del auditor; la Sección 20 no fija porcentajes"],
        ["PYMES: VP de los pagos mínimos ≥ % del valor razonable", float(p["umbralVP"]), "Indicador 20.5 d; umbral de juicio del auditor; la Sección 20 no fija porcentajes"],
        ["Límite de bajo valor del activo nuevo (USD)", float(p["limiteBajoValor"]), "NIIF 16 B3–B8 no fija importe; el IASB pensó en activos de unos USD 5.000 o menos cuando son nuevos (Fundamentos BC100, no forman parte de la norma). Además de no pasar del límite, el bajo valor exige el valor del activo nuevo (B3), que el arrendatario pueda usarlo por sí solo o con recursos disponibles y que no dependa ni esté interrelacionado con otros activos (B5), que no sea un automóvil (coche nuevo, B6) y que no se subarriende (B7)."],
        ["Marco y ruta de cálculo", ("NIIF para las PYMES " + d["edicion"] + " · Sección 20 (financiero/operativo)") if pymes
         else "NIIF completas · NIIF 16 (modelo único del arrendatario)",
         "Tercera edición: Sección 20 con modificaciones solo editoriales; se mantiene financiero/operativo; vigente desde el 1-1-2027; para cortes 2025–2026 solo con adopción anticipada" if pymes
         else "NIIF 16 párr. 22–46"],
    ]

    # 03 · universo (datos del cliente normalizados)
    contratos = []
    for c in cs:
        fila = []
        for k in COL:
            v = c.get(k)
            fila.append(v if v not in ("",) else None)
        contratos.append(fila)
    fmt03 = {"text": "t", "number": "n", "date": "d"}
    cols03 = [[cc["label"], fmt03[cc["type"]]] for cc in _CONTRATOS]

    ident, plazo, medi, pagvar, reme, pasi, rou, gasto, venta, slbpost, conc = ([] for _ in range(11))
    for i, c in enumerate(cs):
        r = FILA0 + i
        # 05 · plazo
        plazo.append([
            c["id"], fx(_x("plazo", r), c["plazo"]), _txt("renov_cierta", r, c["renov_cierta"]),
            fx(f"N({_x('renov_meses', r)})", c["renov_meses"] or 0), fx(f'B{r}+IF(C{r}="Sí",D{r},0)', c["plazo_total"]),
            fx(f'IF({_x("plazo_cliente", r)}="","",{_x("plazo_cliente", r)})', c["plazo_cliente"]),
            fx(f'IF({_x("periodicidad", r)}="Mensual",1,IF({_x("periodicidad", r)}="Trimestral",3,IF({_x("periodicidad", r)}="Semestral",6,12)))', c["m"]),
            fx(f"E{r}/G{r}", c["n"]), fx(f'DATEDIF({_x("inicio", r)},{P}$B${PAR["corte"]}+1,"m")', c["M"]),
            fx(f'IF({_x("compra_cierta", r)}="Sí",IF({_x("vida_util", r)}="",E{r},{_x("vida_util", r)}),'
               f'IF({_x("vida_util", r)}="",E{r},MIN(E{r},{_x("vida_util", r)})))', c["md"]),
        ])
        # 04 · identificación
        if pymes:
            ident.append([
                c["id"], c["activo"], fx(f"{PL}E{r}", c["plazo_total"]), fx(f'IF({_x("vida_util", r)}="","",{_x("vida_util", r)})', c["vida_util"]),
                fx(f'IF(D{r}="","",C{r}/D{r})', c["pv_vida"]), fx(f"{MI}G{r}", c["vp"]),
                fx(f'IF({_x("valor_razonable", r)}="","",{_x("valor_razonable", r)})', c["valor_razonable"]),
                fx(f'IF(G{r}="","",F{r}/G{r})', c["pv_vr"]), _txt("compra_cierta", r, c["compra_cierta"], "No"),
                fx(f'IF(OR(I{r}="Sí",AND(E{r}<>"",E{r}>={P}$B${PAR["umbralVida"]}/100),AND(H{r}<>"",H{r}>={P}$B${PAR["umbralVP"]}/100)),"Sí","No")', c["indicador"]),
                _txt("clasif_pymes", r, c["clasif_pymes"]),
                fx(f'IF(J{r}="Sí","Financiero",IF(K{r}="Financiero","Financiero","Operativo"))', c["clasif"]),
                fx(f'IF(L{r}="Financiero","Sí","No")', c["reconoce"]),
            ])
        else:
            auto = "OR(" + ",".join(f'ISNUMBER(SEARCH("{k}",B{r}))' for k in AUTOMOVIL) + ")"
            ident.append([
                c["id"], c["activo"], fx(f"{PL}E{r}", c["plazo_total"]), fx(f'IF(N({_x("opcion_compra", r)})>0,"Sí","No")', c["opcion"]),
                fx(f'IF(AND(C{r}<=12,D{r}="No"),"Sí","No")', c["corto"]), _txt("bajo_valor", r, c["bajo_valor"], "No"),
                fx(f'IF({_x("valor_razonable", r)}="","",{_x("valor_razonable", r)})', c["valor_razonable"]),
                fx(f'IF({auto},"Sí","No")', c["bv_auto"]), _txt("bajo_valor_b5b7", r, c["bajo_valor_b5b7"]),
                fx(f'IF(OR(F{r}="No",G{r}="",G{r}>{P}$B${PAR["limiteBajoValor"]},H{r}="Sí",I{r}="No"),"No","Sí")', c["bv_limite"]),
                fx(f'IF(OR(E{r}="Sí",J{r}="Sí"),"Sí","No")', c["elegible"]), _txt("exencion", r, c["exencion"], "No"),
                fx(f'IF(AND(L{r}="Sí",K{r}="Sí"),"No","Sí")', c["reconoce"]), _txt("tipo_tasa", r, c["tipo_tasa"]),
            ])
        # 06 · medición inicial
        vr = c["valor_razonable"]
        fila = [c["id"], _txt("tipo_tasa", r, c["tipo_tasa"]), fx(_x("tasa", r), c["tasa"]), fx(_conv(f"C{r}", f"{PL}G{r}"), c["i"]),
                fx(f'IF({_x("momento", r)}="Inicio",1,0)', c["tipo"]),
                fx(f'IF({_x("compra_cierta", r)}="Sí",N({_x("opcion_compra", r)}),0)', c["opt"]),
                fx(f"PV(D{r},{PL}H{r},-{PG}G{r},-F{r},E{r})", c["vp"]),
                fx(f'IF({_x("valor_razonable", r)}="","",{_x("valor_razonable", r)})', vr)]
        if pymes:
            fila += [fx(f'IF(H{r}="",G{r},MIN(H{r},G{r}))', c["base"]),
                     fx(f'IF(OR(H{r}="",H{r}>=G{r}),D{r},RATE({PL}H{r},-{PG}G{r},H{r},-F{r},E{r}))', c["i_used"])]
        else:
            fila += [fx(f"G{r}", c["base"]), fx(f"D{r}", c["i_used"])]
        fila += [fx(f"E{r}*{PG}G{r}", c["p0"]), fx(f"I{r}-K{r}", c["pasivo_ini"]),
                 fx(f"N({_x('anticipados', r)})", c["anticipados"] or 0), fx(f"N({_x('costos', r)})", c["costos"] or 0),
                 fx(f"N({_x('desmantelamiento', r)})", c["desmantelamiento"] or 0), fx(f"N({_x('incentivos', r)})", c["incentivos"] or 0)]
        if pymes:
            fila.append(fx(f"I{r}+N{r}", c["activo_ini"]))
        elif c["slb"] and c["reconoce"] == "Sí":
            fila.append(fx(f"{VA}I{r}", c["activo_ini"]))
        else:
            fila.append(fx(f"L{r}+K{r}+M{r}+N{r}+O{r}-P{r}", c["activo_ini"]))
        medi.append(fila)
        # 07 · pago base, componente indexado y pagos variables
        ix, pi_, pv_c = _x("indexado", r), _x("pago_indexado", r), _x("pago_variable", r)
        q_f = f"{PC}E{r}-{PC}F{r}" if c["reconoce"] == "Sí" else f"{GL}E{r}/{PL}G{r}"
        gv_f = (f'IF(AND(C{r}="Sí",E{r}=""),"",(N(E{r})+N(J{r}))*K{r})' if pymes else f"N(J{r})*K{r}")
        pagvar.append([
            c["id"], fx(_x("pago", r), c["pago"]), fx(f'IF(OR({ix}="Sí",{pi_}<>""),"Sí","No")', c["ind_decl"]),
            _txt("indice", r, c["indice"]), fx(f'IF(C{r}="No",0,IF({pi_}="","",{pi_}))', c["pago_ind"]),
            fx(f'IF(E{r}="","",B{r}-E{r})', c["pago_base"]),
            fx(f'IF(F{r}="",B{r},F{r})' if pymes else f"B{r}", c["pago_medido"]),
            c["trat_indexado"], c["marco_indexado"], fx(f'IF({pv_c}="","",{pv_c})', c["pago_variable"]),
            fx(q_f, c["q_anio"]), fx(gv_f, c["gasto_variable"]),
        ])
        # 08 · remedición
        ev = c["ev"]
        if ev:
            reme.append([c["id"], c["fecha_evento"], c["tipo_evento"],
                         fx(f'INT(DATEDIF({_x("inicio", r)},B{r},"m")/{PL}G{r})', ev["ke"]),
                         fx(f'IF({_x("nuevo_plazo", r)}="",{PL}E{r},{_x("nuevo_plazo", r)})', ev["plazo2"]), fx(f"E{r}/{PL}G{r}", ev["n2"]),
                         fx(f'IF({_x("nuevo_pago", r)}="",{PG}G{r},{_x("nuevo_pago", r)})', ev["p2"]),
                         fx(f'IF({_x("nueva_tasa", r)}="",{MI}C{r},{_x("nueva_tasa", r)})', ev["t2"]), fx(_conv(f"H{r}", f"{PL}G{r}"), ev["i2"]),
                         fx(f"SUMIFS({rng(TA, 'H')},{TA_A},A{r},{TA_B},D{r})", ev["antes"]),
                         fx(f"PV(I{r},F{r}-D{r},-G{r},-{MI}F{r},{MI}E{r})-{MI}E{r}*G{r}", ev["revisado"]),
                         fx(f"K{r}-J{r}", ev["ajuste"]), _txt("remedido", r, c["remedido"])])
        else:
            reme.append([c["id"], c["fecha_evento"], c["nota_evento"] or "Sin evento", None, None, None, None, None, None, None, None, None, None])
        # 09 · pasivo al corte
        if c["reconoce"] == "Sí":
            nm = f"{RE}F{r}" if ev else f"{PL}H{r}"
            saldo_en = lambda k: f"SUMIFS({rng(TA, 'J')},{TA_A},A{r},{TA_B},{k})"
            entre = lambda col: f'SUMIFS({rng(TA, col)},{TA_A},A{r},{TA_B},">"&F{r},{TA_B},"<="&E{r})'
            tasa_sig = f"{RE}I{r}" if ev and c["k"] + 1 > ev["ke"] else f"{MI}J{r}"
            pasi.append([
                c["id"], fx(f"{ID}{reconoce_col}{r}", "Sí"), fx(nm, c["nmax"]), fx(f"{PL}I{r}", c["M"]),
                fx(f"MIN(C{r},INT(MAX(D{r},0)/{PL}G{r}))", c["k"]), fx(f"MIN(C{r},INT(MAX(D{r}-12,0)/{PL}G{r}))", c["kp"]),
                fx(f"IF(E{r}=0,{MI}L{r},{saldo_en(f'E{r}')})", c["pasivo"]),
                fx(f"IF(D{r}<12,0,IF(F{r}=0,{MI}L{r},{saldo_en(f'F{r}')}))", c["pasivo_ia"]),
                fx(f"IF(D{r}<12,{MI}L{r},0)", c["altas"]), fx(entre("F"), c["interes"]), fx(entre("G"), c["pagos"]), fx(entre("I"), c["remedicion"]),
                fx(f"H{r}+I{r}+J{r}-K{r}+L{r}-G{r}", c["comprobacion"]),
                fx(saldo_en(f"MIN(E{r}+12/{PL}G{r},C{r})"), c["pasivo12"]), fx(f"G{r}-N{r}", c["cp"]), fx(f"N{r}", c["lp"]),
                fx(f"N({_x('pasivo_reg', r)})", c["pasivo_reg"]), fx(f"G{r}-Q{r}", c["pasivo"] - c["pasivo_reg"]),
                fx(f'IF({_x("pasivo_cp_reg", r)}="","",{_x("pasivo_cp_reg", r)})', c["pasivo_cp_reg"]),
                fx(f'IF(S{r}="","",O{r}-S{r})', None if c["pasivo_cp_reg"] is None else c["cp"] - c["pasivo_cp_reg"]),
                fx(f'IF({_x("int_reg", r)}="","",{_x("int_reg", r)})', c["int_reg"]),
                fx(f'IF(U{r}="","",J{r}-U{r})', None if c["int_reg"] is None else c["interes"] - c["int_reg"]),
                fx(f"IF(E{r}>=C{r},0,G{r}*{tasa_sig}*(D{r}-E{r}*{PL}G{r})/{PL}G{r})", c["devengo"]),
            ])
            # 10 · activo
            me, aj = (f"{RE}D{r}*{PL}G{r}", f"{RE}L{r}") if ev else (None, None)
            md2f = (f'IF({_x("compra_cierta", r)}="Sí",D{r},IF({_x("vida_util", r)}="",{RE}E{r},MIN({RE}E{r},{_x("vida_util", r)})))') if ev else None
            rou.append([
                c["id"], fx(f"{ID}{reconoce_col}{r}", "Sí"), fx(f"{MI}Q{r}", c["activo_ini"]), fx(f"{PL}J{r}", c["md"]),
                fx(f"MAX({PL}I{r},0)", max(c["M"], 0)),
                fx(me, ev["me"]) if ev else None, fx(aj, ev["ajuste"]) if ev else 0, fx(md2f, ev["md2"]) if ev else None,
                fx(_dep_f(f"E{r}", r, bool(ev)), c["dep_acum"]), fx(_dep_f(f"MAX(E{r}-12,0)", r, bool(ev)), c["dep_ia"]),
                fx(f"I{r}-J{r}", c["dep"]), fx(f"C{r}+G{r}-I{r}", c["neto_antes"]),
                fx(f'IF({_x("recuperable", r)}="","",{_x("recuperable", r)})', c["recuperable"]),
                fx(f'IF(M{r}="",0,MAX(0,L{r}-M{r}))', c["deterioro"]), fx(f"L{r}-N{r}", c["neto"]),
                fx(f"N({_x('activo_reg', r)})", c["activo_reg"]), fx(f"O{r}-P{r}", c["neto"] - c["activo_reg"]),
                fx(f'IF({_x("dep_reg", r)}="","",{_x("dep_reg", r)})', c["dep_reg"]),
                fx(f'IF(R{r}="","",K{r}-R{r})', None if c["dep_reg"] is None else c["dep"] - c["dep_reg"]),
            ])
            gasto.append([c["id"], "Reconocido en balance", None, None, None, None])
        else:
            trat = "Operativo (20.15)" if pymes else ("Exento: corto plazo" if c["corto"] == "Sí" else "Exento: bajo valor")
            pasi.append([c["id"], fx(f"{ID}{reconoce_col}{r}", "No"), None, fx(f"{PL}I{r}", c["M"]), None, None, 0, None, None, None, None,
                         None, None, None, 0, 0, fx(f"N({_x('pasivo_reg', r)})", c["pasivo_reg"]), fx(f"G{r}-Q{r}", -c["pasivo_reg"]),
                         fx(f'IF({_x("pasivo_cp_reg", r)}="","",{_x("pasivo_cp_reg", r)})', c["pasivo_cp_reg"]), None, None, None, None])
            rou.append([c["id"], fx(f"{ID}{reconoce_col}{r}", "No"), None, None, None, None, None, None, None, None, 0, None, None, 0, 0,
                        fx(f"N({_x('activo_reg', r)})", c["activo_reg"]), fx(f"O{r}-P{r}", -c["activo_reg"]), None, None])
            gasto.append([c["id"], trat, fx(f"{PG}G{r}*{PL}H{r}", c["pagos_tot"]), fx(f"{PL}E{r}", c["plazo_total"]),
                          fx(f"MIN(MAX({PL}I{r},0),D{r})-MIN(MAX({PL}I{r}-12,0),D{r})", c["meses_anio"]), fx(f"C{r}/D{r}*E{r}", c["gasto"])])
        # 12 · venta con arrendamiento posterior
        s = c["slb"]
        if s and pymes:
            venta.append([c["id"], fx(_x("precio_venta", r), c["precio_venta"]),
                          fx(f'IF({_x("valor_razonable", r)}="","",{_x("valor_razonable", r)})', c["valor_razonable"]),
                          fx(_x("libros_previo", r), c["libros_previo"]), fx(f"{ID}L{r}", c["clasif"]),
                          fx(f'IF(E{r}="Financiero",MIN(B{r}-D{r},0),MIN(B{r},C{r})-D{r})', s["inmediata"]),
                          fx(f'IF(E{r}="Financiero",MAX(B{r}-D{r},0),MAX(B{r}-C{r},0))', s["diferida"]),
                          fx(f'IF({_x("ganancia_reg", r)}="","",{_x("ganancia_reg", r)})', c["ganancia_reg"]),
                          fx(f'IF(H{r}="","",F{r}-H{r})', None if c["ganancia_reg"] is None else s["inmediata"] - c["ganancia_reg"])])
        elif s:
            venta.append([c["id"], fx(_x("precio_venta", r), c["precio_venta"]), fx(_x("valor_razonable", r), c["valor_razonable"]),
                          fx(_x("libros_previo", r), c["libros_previo"]), fx(f"MAX(B{r}-C{r},0)", s["financiacion"]),
                          fx(f"MAX(C{r}-B{r},0)", s["prepago"]), fx(f"{MI}L{r}", c["pasivo_ini"]), fx(f"G{r}-E{r}+F{r}", s["parte"]),
                          fx(f"D{r}*H{r}/C{r}", s["rou"]), fx(f"C{r}-D{r}", s["total"]), fx(f"J{r}*(C{r}-H{r})/C{r}", s["inmediata"]),
                          fx(f'IF({_x("ganancia_reg", r)}="","",{_x("ganancia_reg", r)})', c["ganancia_reg"]),
                          fx(f'IF(L{r}="","",K{r}-L{r})', None if c["ganancia_reg"] is None else s["inmediata"] - c["ganancia_reg"])])
        else:
            venta.append([c["id"], "No aplica"] + [None] * ((7 if pymes else 11)))
        # 14 · venta con arrendamiento posterior: medición posterior (102A)
        gp = _x("ganancia_post_reg", r)
        # M22: sin el dato del cliente el control del 102A queda vacío, nunca en cero.
        ctrl = [fx(f'IF({gp}="","",{gp})', c["ganancia_post_reg"]), fx(f'IF(O{r}<>"",O{r},"")', c["ganancia_post_reg"])]
        if c["venta_posterior"] != "Sí":
            slbpost.append([c["id"], "No aplica"] + [None] * 14)
        elif s and c["reconoce"] == "Sí":
            slbpost.append([
                c["id"], ("Sección 20.32–20.34: el activo y el pasivo siguen el arrendamiento financiero (20.11, 20.12)" if pymes
                          else "NIIF 16 párr. 102A: párr. 29–35 al derecho de uso conservado y 36–46 al pasivo"),
                fx(f"{PC}H{r}", c["pasivo_ia"]), fx(f"{PC}I{r}", c["altas"]), fx(f"{PC}J{r}", c["interes"]),
                fx(f"{PC}K{r}", c["pagos"]), fx(f'IF({PG}L{r}="","",{PG}L{r})', c["gasto_variable"]),
                fx(f"{PC}L{r}", c["remedicion"]), fx(f"{PC}G{r}", c["pasivo"]), fx(f"{PC}M{r}", c["comprobacion"]),
                fx(f"{DU}C{r}", c["activo_ini"]), fx(f"{DU}K{r}", c["dep"]), fx(f"{DU}O{r}", c["neto"]),
                fx(f"{VA}F{r}" if pymes else f"{VA}K{r}", s["inmediata"]),
            ] + ctrl)
        else:
            nota = ("Operativo en la Sección 20: no hay derecho de uso ni pasivo que medir después (20.15, 20.34)" if pymes
                    else "Sin medición posterior: faltan precio, valor razonable o importe en libros previo, o el contrato no se reconoce")
            slbpost.append([c["id"], nota] + [None] * 12 + ctrl)
        # 15 · conciliación
        conc.append([c["id"], fx(f"{PC}G{r}", c["pasivo"]), fx(f"{PC}Q{r}", c["pasivo_reg"]), fx(f"B{r}-C{r}", c["pasivo"] - c["pasivo_reg"]),
                     fx(f"{DU}O{r}", c["neto"]), fx(f"{DU}P{r}", c["activo_reg"]), fx(f"E{r}-F{r}", c["neto"] - c["activo_reg"]),
                     fx(f"{DU}K{r}" if c["reconoce"] == "Sí" else "0", c["dep"]),
                     fx(f"{PC}J{r}" if c["reconoce"] == "Sí" else "0", c["interes"]), fx(f"{PC}O{r}" if c["reconoce"] == "Sí" else "0", c["cp"])])

    # 08 · tabla de amortización
    fila_c = {c["id"]: FILA0 + i for i, c in enumerate(cs)}
    tabla = []
    for k, x in enumerate(tab):
        rr = FILA0 + k
        rc = fila_c[x["id"]]
        c = next(y for y in cs if y["id"] == x["id"])
        ev = c["ev"]
        tasa = f"{RE}I{rc}" if x["nuevo"] else f"{MI}J{rc}"
        pg = f"{RE}G{rc}" if x["nuevo"] else f"{PG}G{rc}"
        ne = f"{RE}F{rc}" if x["nuevo"] else f"{PL}H{rc}"
        ini = f"{MI}L{rc}" if x["j"] == 1 else f"J{rr - 1}"
        es_ev = ev is not None and x["j"] == ev["ke"]
        tabla.append([x["id"], x["j"], x["vence"], fx(tasa, x["tasa"]), fx(ini, x["ini"]), fx(f"E{rr}*D{rr}", x["interes"]),
                      fx(f"IF(B{rr}<{ne},{pg},IF(B{rr}={ne},{MI}F{rc}+(1-{MI}E{rc})*{pg},0))", x["pago"]),
                      fx(f"E{rr}+F{rr}-G{rr}", x["fin"]), fx(f"{RE}K{rc}-H{rr}", x["ajuste"]) if es_ev else 0,
                      fx(f"H{rr}+I{rr}", x["saldo"])])

    t = d["totales"]
    fin = FILA0 + N - 1
    fin_t = FILA0 + len(tab) - 1
    tot = FILA0 + N  # fila TOTAL de las cédulas por contrato
    fila_res = {k: FILA0 + i for i, k in enumerate(res["labels"])}
    CO = ref("15_Conciliacion")
    ref_res = {"pasivoRegistrado": f"{CO}C{tot}", "pasivo": f"{CO}B{tot}", "ajuste": f"B{fila_res['pasivo']}-B{fila_res['pasivoRegistrado']}",
               "corriente": f"SUM({PC}O{FILA0}:O{fin})", "noCorriente": f"SUM({PC}P{FILA0}:P{fin})", "activo": f"{CO}E{tot}",
               "activoRegistrado": f"{CO}F{tot}", "ajusteActivo": f"B{fila_res['activo']}-B{fila_res['activoRegistrado']}",
               "depreciacion": f"{CO}H{tot}", "intereses": f"{CO}I{tot}", "deterioro": f"SUM({DU}N{FILA0}:N{fin})",
               "gastoLineal": f"SUM({GL}F{FILA0}:F{fin})", "gastoVariable": f"SUM({PG}L{FILA0}:L{fin})",
               "remedicion": f"SUM({RE}L{FILA0}:L{fin})"}
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    n_ = "n"
    cols_ident = ([["Contrato", "t"], ["Activo", "t"], ["Plazo (meses)", "i"], ["Vida útil (meses)", "i"], ["Plazo / vida útil", "p"],
                   ["VP de los pagos mínimos", n_], ["Valor razonable", n_], ["VP / valor razonable", "p"], ["Compra razonablemente cierta", "t"],
                   ["Indicador de financiero (20.5)", "t"], ["Clasificación del cliente", "t"], ["Clasificación auditada", "t"], ["Reconoce pasivo", "t"]]
                  if pymes else
                  [["Contrato", "t"], ["Activo", "t"], ["Plazo (meses)", "i"], ["Opción de compra", "t"], ["Corto plazo (≤ 12 m, sin opción)", "t"],
                   ["Bajo valor declarado", "t"], ["Valor del activo nuevo (B3)", n_], ["Automóvil (B6)", "t"],
                   ["Uso independiente y sin subarriendo (B5, B7)", "t"], ["Bajo valor elegible (B3, B5–B7)", "t"], ["Exención elegible (5)", "t"],
                   ["Exención aplicada por el cliente", "t"], ["Reconoce pasivo", "t"], ["Tipo de tasa (26)", "t"]])
    cols_venta = ([["Contrato", "t"], ["Precio de venta", n_], ["Valor razonable", n_], ["Importe en libros previo", n_], ["Clasificación", "t"],
                   ["Ganancia inmediata (20.33–20.34)", n_], ["Ganancia diferida", n_], ["Ganancia registrada", n_], ["Diferencia", n_]]
                  if pymes else
                  [["Contrato", "t"], ["Precio de venta", n_], ["Valor razonable", n_], ["Importe en libros previo", n_],
                   ["Financiación adicional (101 b)", n_], ["Pago anticipado (101 a)", n_], ["Pasivo inicial", n_], ["Parte del arrendamiento", n_],
                   ["Derecho de uso conservado (100 a)", n_], ["Ganancia total", n_], ["Ganancia reconocida (derechos transferidos)", n_],
                   ["Ganancia registrada", n_], ["Diferencia", n_]])
    S = lambda col, v: suma(col, fin, v)
    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Contratos", "Universo de contratos", cols03, contratos),
        hoja("04_Identificacion", "Identificación, clasificación y exenciones", cols_ident, ident),
        hoja("05_Plazo", "Plazo y opciones",
             [["Contrato", "t"], ["Plazo no cancelable (meses)", "i"], ["Renovación razonablemente cierta", "t"], ["Meses de renovación", "i"],
              ["Plazo del arrendamiento (18)", "i"], ["Plazo usado por el cliente", "i"], ["Meses por período", "i"], ["Períodos", "i"],
              ["Meses transcurridos al corte", "i"], ["Meses de depreciación (32 / 20.12)", "i"]], plazo),
        hoja("06_Medicion_inicial", "Medición inicial: pasivo y activo",
             [["Contrato", "t"], ["Tipo de tasa", "t"], ["Tasa anual (%)", "x"], ["Tasa periódica", "p"], ["Pago al inicio (1) / al final (0)", "i"],
              ["Opción de compra incluida (27 d)", n_], ["VP de los pagos", n_], ["Valor razonable", n_],
              ["Base de medición" + (" (menor VR / VP, 20.9)" if pymes else " (26)"), n_], ["Tasa usada en la tabla", "p"],
              ["Pago en el comienzo", n_], ["Pasivo inicial", n_], ["Pagos anticipados", n_], ["Costos directos iniciales", n_],
              ["Desmantelamiento", n_], ["Incentivos", n_], ["Activo arrendado (20.9)" if pymes else "Derecho de uso (24)", n_]], medi,
             ["TOTAL", "", None, None, None, None, S("G", sum(c["vp"] for c in cs)), None, None, None, None,
              S("L", sum(c["pasivo_ini"] for c in cs)), None, None, None, None, S("Q", sum(c["activo_ini"] for c in cs))]),
        hoja("07_Pagos_variables", "Pago base, componente indexado y pagos variables",
             [["Contrato", "t"], ["Pago periódico total del contrato", n_], ["Ligado a un índice de inflación", "t"],
              ["Índice o referencia", "t"], ["Componente ligado al índice", n_], ["Pago base", n_],
              ["Pago usado en la medición del pasivo", n_], ["Tratamiento del componente indexado", "t"],
              ["Marco que lo manda", "t"], ["Pago variable no ligado a un índice (38 b)", n_],
              ["Períodos del ejercicio", "x"], ["Gasto del ejercicio por pagos variables", n_]], pagvar,
             ["TOTAL", S("B", sum(c["pago"] for c in cs)), "", "", S("E", sum(c["pago_ind"] or 0 for c in cs)),
              S("F", sum(c["pago_base"] or 0 for c in cs)), S("G", sum(c["pago_medido"] for c in cs)), "", "",
              S("J", sum(c["pago_variable"] or 0 for c in cs)), None, S("L", t["gastoVariable"])]),
        hoja("08_Remedicion", "Remedición y modificaciones",
             [["Contrato", "t"], ["Fecha del evento", "d"], ["Tipo / nota", "t"], ["Períodos al evento", "i"], ["Plazo revisado (meses)", "i"],
              ["Períodos revisados", "i"], ["Pago revisado", n_], ["Tasa anual revisada (%)", "x"], ["Tasa periódica revisada", "p"],
              ["Pasivo antes del evento", n_], ["Pasivo remedido (40–45)", n_], ["Ajuste al pasivo y al derecho de uso", n_], ["Remedido por el cliente", "t"]],
             reme, ["TOTAL", None, "", None, None, None, None, None, None, None, None, S("L", t["remedicion"]), ""]),
        hoja("09_Tabla_amortizacion", "Tabla de amortización",
             [["Contrato", "t"], ["Período", "i"], ["Vencimiento", "d"], ["Tasa periódica", "p"], ["Saldo inicial", n_], ["Interés (37)", n_],
              ["Pago", n_], ["Saldo final", n_], ["Remedición", n_], ["Saldo final ajustado", n_]], tabla,
             ["TOTAL", None, None, None, None, suma("F", fin_t, sum(x["interes"] for x in tab)), suma("G", fin_t, sum(x["pago"] for x in tab)),
              None, suma("I", fin_t, sum(x["ajuste"] for x in tab)), None] if tab else None),
        hoja("10_Pasivo_corte", "Pasivo al corte: corriente y no corriente",
             [["Contrato", "t"], ["Reconoce", "t"], ["Períodos finales", "i"], ["Meses transcurridos", "i"], ["Períodos vencidos al corte", "i"],
              ["Períodos vencidos al inicio del año", "i"], ["Pasivo al corte", n_], ["Pasivo al inicio del año", n_], ["Altas del año", n_],
              ["Interés del ejercicio", n_], ["Pagos del ejercicio", n_], ["Remedición del ejercicio", n_], ["Comprobación (0)", n_],
              ["Pasivo dentro de 12 meses", n_], ["Corriente", n_], ["No corriente", n_], ["Pasivo registrado", n_], ["Diferencia", n_],
              ["Corriente registrado", n_], ["Diferencia corriente", n_], ["Interés registrado", n_], ["Diferencia interés", n_],
              ["Interés devengado no vencido (informativo)", n_]], pasi,
             ["TOTAL", "", None, None, None, None, S("G", t["pasivo"]), S("H", sum(c.get("pasivo_ia") or 0 for c in cs)),
              S("I", sum(c.get("altas") or 0 for c in cs)), S("J", t["intereses"]), S("K", sum(c["pagos"] for c in cs)),
              S("L", sum(c["remedicion"] for c in cs)), None, None, S("O", t["corriente"]), S("P", t["noCorriente"]), S("Q", t["pasivoRegistrado"]),
              S("R", t["ajuste"]), None, None, None, None, S("W", sum(c["devengo"] for c in cs))]),
        hoja("11_Derecho_uso", "Depreciación y deterioro del activo",
             [["Contrato", "t"], ["Reconoce", "t"], ["Costo inicial", n_], ["Meses de depreciación", "i"], ["Meses transcurridos", "i"],
              ["Meses al evento", "i"], ["Ajuste por remedición", n_], ["Meses de depreciación revisados", "i"], ["Depreciación acumulada al corte", n_],
              ["Depreciación acumulada al inicio del año", n_], ["Depreciación del ejercicio", n_], ["Neto antes de deterioro", n_],
              ["Importe recuperable", n_], ["Deterioro (33 / Secc. 27)", n_], ["Neto recalculado", n_], ["Registrado neto", n_], ["Diferencia", n_],
              ["Depreciación registrada", n_], ["Diferencia depreciación", n_]], rou,
             ["TOTAL", "", None, None, None, None, None, None, None, None, S("K", t["depreciacion"]), None, None, S("N", t["deterioro"]),
              S("O", t["activo"]), S("P", t["activoRegistrado"]), S("Q", t["ajusteActivo"]), None, None]),
        hoja("12_Gasto_lineal", "Gasto lineal: exentos y operativos",
             [["Contrato", "t"], ["Tratamiento", "t"], ["Pagos totales del plazo", n_], ["Plazo (meses)", "i"], ["Meses del contrato en el año", "i"],
              ["Gasto lineal del ejercicio (6 / 20.15)", n_]], gasto,
             ["TOTAL", "", None, None, None, S("F", t["gastoLineal"])]),
        hoja("13_Venta_arr_posterior", "Venta con arrendamiento posterior: medición inicial", cols_venta, venta),
        hoja("14_Venta_medicion_post", "Venta con arrendamiento posterior: medición posterior",
             [["Contrato", "t"], ["Tratamiento y marco", "t"], ["Pasivo al inicio del ejercicio", n_], ["Altas del ejercicio", n_],
              ["Interés del ejercicio (36–37)", n_], ["Pagos fijos del ejercicio", n_], ["Pagos variables del ejercicio (38 b)", n_],
              ["Remedición del ejercicio (40–43)", n_], ["Pasivo al corte", n_], ["Comprobación del pasivo (0)", n_],
              ["Derecho de uso conservado inicial (100 a)", n_], ["Depreciación del ejercicio (29–35)", n_],
              ["Derecho de uso neto al corte", n_], ["Ganancia reconocida en la venta", n_],
              ["Ganancia posterior registrada", n_], ["Control 102A: ganancia sobre el derecho de uso conservado (0)", n_]], slbpost,
             ["TOTAL", "", None, None, None, None, None, None, S("I", sum(c["pasivo"] for c in cs if c["venta_posterior"] == "Sí" and c["slb"] and c["reconoce"] == "Sí")),
              None, None, None, S("M", sum(c["neto"] for c in cs if c["venta_posterior"] == "Sí" and c["slb"] and c["reconoce"] == "Sí")),
              None, None, S("P", sum(c["ganancia_post_reg"] or 0 for c in cs if c["venta_posterior"] == "Sí"))]),
        hoja("15_Conciliacion", "Conciliación y ajuste",
             [["Contrato", "t"], ["Pasivo recalculado", n_], ["Pasivo registrado", n_], ["Ajuste pasivo", n_], ["Activo recalculado", n_],
              ["Activo registrado", n_], ["Ajuste activo", n_], ["Depreciación del ejercicio", n_], ["Interés del ejercicio", n_], ["Pasivo corriente", n_]],
             conc, ["TOTAL", S("B", t["pasivo"]), S("C", t["pasivoRegistrado"]), S("D", t["ajuste"]), S("E", t["activo"]),
                    S("F", t["activoRegistrado"]), S("G", t["ajusteActivo"]), S("H", t["depreciacion"]), S("I", t["intereses"]), S("J", t["corriente"])]),
        hoja("16_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición ------------------------------------------------------------------------

def definicion() -> dict:
    contenido = ("Una fila por contrato: código, activo, fecha de comienzo, plazo no cancelable, renovación (meses y si es razonablemente "
                 "cierta), pago y periodicidad, tasa anual, pagos anticipados, costos directos, desmantelamiento, incentivos, opción de compra, "
                 "vida útil, valor razonable, bajo valor y exención, clasificación PYMES, saldos registrados (pasivo, corriente, activo, "
                 "depreciación e interés del año) y, si hubo, modificación, deterioro o venta con arrendamiento posterior. Si la renta se "
                 "ajusta por un índice, indique además si está indexada, el importe del componente ligado al índice por período, el índice de "
                 "referencia y el pago variable no ligado a un índice; en la venta con arrendamiento posterior, la ganancia o pérdida "
                 "reconocida después de la venta por la medición posterior. Sin filas de total.")
    return {
        "name": "Arrendamientos",
        "area": "Arrendamientos",
        "processor": "arrendamientos",
        "frameworks": ["NIIF completas", "NIIF para las PYMES"],
        "summary": ("Recalcula por contrato el pasivo por arrendamiento (VP de los pagos con la tasa implícita o incremental), el derecho de uso, "
                    "la tabla de amortización, el interés, la depreciación, la porción corriente, las remediciones y modificaciones, las exenciones "
                    "y la venta con arrendamiento posterior con su medición posterior y el control del párrafo 102A (NIIF 16). Separa el pago "
                    "base del componente ligado a un índice de inflación y lo enruta por marco: en NIIF completas entra en la medición con el "
                    "índice del comienzo (27 b) y en PYMES queda fuera, como gasto del período (20.11 / 20.15 b). En PYMES aplica la Sección 20: "
                    "clasificación financiero/operativo, financiero al menor entre valor razonable y VP, operativo como gasto lineal, y detecta "
                    "el «derecho de uso» indebido."),
        "source": {"organization": "IFRS Foundation / Unión Europea", "type": "Norma contable", "date": "",
                   "document": ("NIIF 16 Arrendamientos (texto en español, Reglamento (UE) 2023/1803): párr. 5–8, 9, 18–21, 22–27 (27 b: pagos "
                                "variables que dependen de un índice, medidos con el índice de la fecha de comienzo), 28, 29–33, 36–38 (38 b: "
                                "pagos variables no incluidos en la medición), 39–46 (42 b y 43: remedición por cambio de índice con la tasa sin "
                                "cambios), 47, 98–103 y 102A (medición posterior de la venta con arrendamiento posterior, incorporado por la "
                                "modificación de 2022 «Pasivo por arrendamiento en una venta con arrendamiento posterior»), B3–B8, B34–B41 y "
                                "Apéndice A (arrendamiento a corto plazo); NIC 1 párr. 69 (corriente; desde 2027 la NIIF 18 sustituye a la NIC 1: párr. 101)"),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015, Sección 20 Arrendamientos: 20.4–20.8 (clasificación), 20.9–20.10 (medición inicial "
                                      "del financiero, por los pagos mínimos), 20.11 (carga financiera con tasa constante; las cuotas contingentes "
                                      "se cargan como gasto en los períodos en que se incurren), 20.12 (depreciación y deterioro, Sección 27), "
                                      "20.13 c y 20.16 c (revelación de las cuotas contingentes y las cláusulas de revisión), 20.15 (operativo: "
                                      "gasto lineal; 20.15 b: pagos estructurados para seguir la inflación general esperada según índices o "
                                      "estadísticas publicadas), 20.32–20.34 (venta con arrendamiento posterior). Edición 2025 (tercera): "
                                      "Sección 20 con modificaciones solo editoriales; se mantiene financiero/operativo; vigente desde el 1-1-2027; "
                                      "para cortes 2025–2026 solo con adopción anticipada."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 16–17, 18–27 y 28–30 (28: el recálculo del auditor es una estimación puntual propia; 30: NIA 500)",
             "requirement": "Estimación contable: evaluar método (VP, tabla), datos (contratos) y supuestos (tasa incremental, plazo, opciones)."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del anexo de contratos contra el mayor y los contratos firmados."},
            {"document": "NIA 505", "section": "párr. 7 (decisión de confirmar: NIA 330 párr. 19)", "requirement": "Confirmar con arrendadores condiciones y pagos cuando sea significativo."},
            {"document": "NIA 560", "section": "párr. 6", "requirement": "Modificaciones, renovaciones o terminaciones posteriores al cierre."},
        ],
        "calculo": [
            "Exención (NIIF 16 párr. 5–8): corto plazo = plazo ≤ 12 meses sin opción de compra. Bajo valor = valor del activo en su estado nuevo dentro del "
            "límite del auditor (B3; sin ese dato no es elegible) y, además, activo utilizable por sí solo o con recursos fácilmente disponibles y no "
            "dependiente ni interrelacionado con otros (B5), que no sea un automóvil (B6) y que no se subarriende (B7). Solo vale si el cliente la aplicó y es elegible.",
            "PYMES: financiero si la compra es razonablemente cierta, el plazo cubre la mayor parte de la vida útil o el VP cubre sustancialmente el valor razonable (20.5); si no, operativo. 20.5 c habla de vida económica y el cálculo usa la vida útil del anexo: pendiente de decisión del socio.",
            "Plazo = período no cancelable + meses de renovación razonablemente cierta (18, B37).",
            "Tasa periódica: efectiva (1 + r)^(meses/12) − 1 o nominal r × meses/12. VP = VA(tasa; períodos; −pago; −opción de compra cierta; tipo).",
            "Pasivo inicial = VP − pago hecho en el comienzo (26–27). Derecho de uso = pasivo + pagos al comienzo o antes + costos directos + desmantelamiento − incentivos (24).",
            "PYMES financiero: base = mínimo entre valor razonable y VP (20.9); si manda el valor razonable, tasa constante = TASA(…) (20.11); activo = base + costos directos.",
            "Tabla: interés = saldo inicial × tasa periódica; saldo final = saldo inicial + interés − pago (37 / 20.11).",
            "Remedición y modificación: pasivo remedido = VP de los pagos revisados con la tasa revisada (40–45); ajuste contra el derecho de uso (39, 46 b), que se deprecia en el plazo restante.",
            "Al corte: pasivo = saldo del último período vencido; corriente = pasivo − saldo dentro de 12 meses; interés y pagos del ejercicio de la tabla.",
            "Depreciación lineal desde el comienzo hasta el menor entre plazo y vida útil, o la vida útil si la compra es cierta (31–32 / 20.12); deterioro = neto − importe recuperable (33 / Sección 27).",
            "Exentos y operativos: gasto lineal = pagos del plazo ÷ plazo × meses del año (6 / 20.15).",
            "Venta con arrendamiento posterior: derecho de uso conservado = libros × (pasivo − financiación adicional + prepago) ÷ valor razonable; ganancia reconocida = (VR − libros) × (VR − parte del arrendamiento) ÷ VR (100–102). PYMES: 20.33–20.34.",
            "Venta con arrendamiento posterior, medición posterior (102A): el pasivo sigue los párrafos 36 a 46 (interés, pagos fijos, pagos "
            "variables, remedición) y el derecho de uso conservado los párrafos 29 a 35 (depreciación y deterioro); el control comprueba que "
            "después de la fecha de inicio no se reconozca ninguna ganancia o pérdida relacionada con el derecho de uso conservado, salvo la de "
            "una terminación parcial o total (46 a).",
            "Pago base y componente ligado a un índice de inflación: pago base = pago periódico total − componente indexado. En NIIF completas el "
            "componente entra en la medición del pasivo con el índice de la fecha de comienzo (27 b, 28) y solo se remide cuando cambian los "
            "flujos (42 b), con la tasa de descuento sin cambios (43). En la NIIF para las PYMES no se capitaliza como pago fijo: en el "
            "financiero es una cuota contingente que se carga como gasto en los períodos en que se incurre (20.11) y en el operativo queda fuera "
            "del gasto lineal (20.15 b); en ambos casos se revela (20.13 c / 20.16 b y c). Los pagos variables no ligados a un índice son gasto "
            "del período en los dos marcos (38 b / 20.11). Si el cliente declara la indexación pero no informa el importe del componente, el pago "
            "base y el componente quedan vacíos y se emite un problema.",
        ],
        "fields": _CONTRATOS, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, lbl] for n, lbl in CEDULAS],
        "program": [
            {"code": "ARR-01", "objective": "Integridad del universo de contratos", "risk": "Arrendamientos no identificados o contratos que contienen un arrendamiento sin registrar",
             "assertion": "Integridad", "procedure": "Conciliar el anexo con el mayor; revisar contratos de servicios, actas y gastos de alquiler para identificar arrendamientos (9, B9–B31)",
             "evidence": "Anexo de contratos, contratos firmados, mayor de gastos de alquiler", "criterion": "Universo completo y conciliado", "source": "NIIF 16 párr. 9 · NIA 500"},
            {"code": "ARR-02", "objective": "Exenciones y clasificación", "risk": "Exención de corto plazo o bajo valor mal aplicada; en PYMES, financiero clasificado como operativo",
             "assertion": "Presentación", "procedure": "Evaluar plazo, opción de compra, valor del activo nuevo (B3) y las condiciones de B5 a B7 (uso "
             "independiente, no automóvil, sin subarriendo); en PYMES, los indicadores de 20.5",
             "evidence": "Contratos, cotizaciones del activo nuevo, contratos de subarriendo", "criterion": "Tratamiento conforme a 5–8, B3–B8 / 20.4–20.8",
             "source": "NIIF 16 párr. 5–8, B3–B8 · Sección 20.4–20.8"},
            {"code": "ARR-03", "objective": "Plazo y opciones", "risk": "Renovación o compra razonablemente cierta no incluida",
             "assertion": "Valoración", "procedure": "Evaluar incentivos económicos para renovar o comprar (mejoras, penalidades, importancia del activo)",
             "evidence": "Contratos, presupuestos, historial de renovaciones", "criterion": "Plazo conforme a 18–21 y B37", "source": "NIIF 16 párr. 18–21, 27 d, B34–B41"},
            {"code": "ARR-04", "objective": "Tasa de descuento", "risk": "Tasa incremental sin sustento", "assertion": "Valoración",
             "procedure": "Verificar la tasa implícita o la incremental con préstamos recientes y plazos comparables", "evidence": "Contratos de préstamo, cotizaciones bancarias",
             "criterion": "Tasa sustentada", "source": "NIIF 16 párr. 26 · Sección 20.10 · NIA 540"},
            {"code": "ARR-05", "objective": "Medición del pasivo y del activo", "risk": "Pasivo, derecho de uso, interés o depreciación mal calculados",
             "assertion": "Valoración", "procedure": "Recalcular VP, tabla de amortización, interés, depreciación y compararlos con lo registrado",
             "evidence": "Cédulas 06, 08, 09 y 10", "criterion": "Diferencias cuantificadas", "source": "NIIF 16 párr. 23–38 · Sección 20.9–20.12"},
            {"code": "ARR-06", "objective": "Presentación corriente / no corriente", "risk": "Porción corriente mal clasificada", "assertion": "Presentación",
             "procedure": "Recalcular el capital que se paga en los 12 meses siguientes al corte", "evidence": "Tabla de amortización",
             "criterion": "Clasificación conforme a NIC 1 párr. 69", "source": "NIIF 16 párr. 47 · NIC 1 párr. 69"},
            {"code": "ARR-07", "objective": "Modificaciones y remediciones", "risk": "Cambio de pagos, plazo o tasa no remedido", "assertion": "Valoración",
             "procedure": "Revisar adendas y cambios de índice; recalcular el pasivo remedido y el ajuste al derecho de uso", "evidence": "Adendas, comunicaciones del arrendador",
             "criterion": "Remedición conforme a 39–46", "source": "NIIF 16 párr. 39–46 · NIA 560"},
            {"code": "ARR-08", "objective": "Deterioro del activo", "risk": "Derecho de uso sobrevalorado (locales cerrados, subutilización)", "assertion": "Valoración",
             "procedure": "Evaluar indicios y comparar el neto con el importe recuperable", "evidence": "Evaluación de deterioro del cliente",
             "criterion": "Deterioro reconocido", "source": "NIIF 16 párr. 33 · NIC 36 · Sección 20.12 y 27"},
            {"code": "ARR-09", "objective": "Venta con arrendamiento posterior", "risk": "Ganancia reconocida en exceso", "assertion": "Ocurrencia",
             "procedure": "Verificar que la transferencia es venta (NIIF 15), medir el derecho de uso conservado y la ganancia de los derechos transferidos",
             "evidence": "Contrato de compraventa, tasación, contrato de arrendamiento", "criterion": "Ganancia conforme a 99–103 / 20.32–20.34",
             "source": "NIIF 16 párr. 98–103 · Sección 20.32–20.34"},
            {"code": "ARR-10", "objective": "Pago base y componente ligado a un índice de inflación",
             "risk": "El componente indexado se capitaliza como pago fijo bajo la Sección 20, o se excluye de la medición bajo NIIF completas, o no se revela",
             "assertion": "Valoración", "procedure": "Separar en la factura o liquidación del período la renta base del reajuste por índice; "
             "comprobar que en NIIF completas el componente se midió con el índice de la fecha de comienzo y que en PYMES se cargó como gasto del período",
             "evidence": "Facturas y liquidaciones de renta, cláusula de revisión del contrato, índice publicado (INEC u organismo oficial)",
             "criterion": "Componente medido o expensado según el marco y revelado", "source": "NIIF 16 párr. 27 b, 28, 38 b, 42 b y 43 · Sección 20.11, 20.13 c, 20.15 b y 20.16 c"},
            {"code": "ARR-11", "objective": "Medición posterior de la venta con arrendamiento posterior",
             "risk": "Se reconoce en resultados una ganancia atribuible al derecho de uso conservado después de la fecha de inicio",
             "assertion": "Valoración", "procedure": "Recorrer el movimiento del pasivo (saldo inicial, interés, pagos fijos y variables, remedición, "
             "saldo final) y del derecho de uso conservado (costo, depreciación, neto); revisar los asientos posteriores a la venta que afecten resultados",
             "evidence": "Mayor del pasivo y del derecho de uso, asientos de remedición, contrato de arrendamiento",
             "criterion": "Sin ganancia ni pérdida sobre el derecho de uso conservado, salvo terminación (46 a)", "source": "NIIF 16 párr. 102A, 29–35 y 36–46"},
        ],
        "requests": [
            req("RQ-001", "Anexo de contratos de arrendamiento al corte", "contratos", "ARR-01", "Población a recalcular y conciliar con el mayor", content=contenido),
            req("RQ-002", "Contratos de arrendamiento firmados y adendas", None, "ARR-03", "Plazo, opciones, pagos y modificaciones",
                formats=("pdf", "docx"), use="soporte"),
            req("RQ-003", "Sustento de la tasa implícita o incremental", None, "ARR-04", "Tasa de descuento (26 / 20.10)",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-004", "Mayor y auxiliares del pasivo, derecho de uso, depreciación e intereses", None, "ARR-05", "Saldos registrados",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-005", "Evaluación de deterioro y tasaciones del activo", None, "ARR-08", "Importe recuperable y valor razonable",
                formats=("pdf", "xlsx"), use="soporte", required=False),
            req("RQ-006", "Contrato de compraventa de la venta con arrendamiento posterior", None, "ARR-09", "Precio, valor razonable e importe en libros",
                formats=("pdf",), use="soporte", required=False),
            req("RQ-007", "Facturas o liquidaciones de renta del ejercicio y cláusula de revisión por índice", None, "ARR-10",
                "Separar la renta base del componente ligado al índice y de los pagos variables (27 b, 38 b / 20.11, 20.15 b)",
                formats=("pdf", "xlsx"), use="soporte", required=False),
            req("RQ-008", "Mayor y asientos posteriores a la venta con arrendamiento posterior", None, "ARR-11",
                "Movimiento del pasivo y del derecho de uso conservado y control del párrafo 102A",
                formats=("xlsx", "pdf"), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejercicio modelo (M19) -------------------------------------------------------------

def _k(id, activo, inicio, plazo, pago, per, tasa, pasivo_reg, **x):
    return {"id": id, "activo": activo, "inicio": inicio, "plazo": plazo, "pago": pago, "periodicidad": per, "tasa": tasa,
            "pasivo_reg": pasivo_reg, "_row": 2, **x}


# Cifras de control resueltas a mano (corte 31-12-2025, tasa efectiva):
# · C-02 bodega, 5 pagos anuales vencidos de 10.000 al 10 %: VP = 10.000 × (1 − 1,1^−5) ÷ 0,1 = 37.907,87.
#   Tras 3 años: 31.698,65 → 24.868,52 → 17.355,37 (interés 2025 = 24.868,52 × 10 % = 2.486,85);
#   corriente = 17.355,37 − 9.090,91 = 8.264,46 (el cliente registró 10.000).
# · C-07 oficina, 5 pagos anuales de 12.000 al 8 %: VP 47.912,52; tras 2 años 30.925,16. Adenda al 01-01-2025:
#   3 pagos de 13.500 al 9 % → VP 34.172,48; ajuste 3.247,31 no remedido; interés 2025 3.075,52; pasivo 23.748,00.
# · C-08 venta con arrendamiento posterior (NIIF 16 Ejemplo ilustrativo 24): 18 pagos anuales de 120.000 al 4,5 %
#   = 1.459.199,02; financiación adicional 200.000; derecho de uso = 1.000.000 × 1.259.199,02 ÷ 1.800.000 = 699.555,01;
#   ganancia = 800.000 × 540.800,98 ÷ 1.800.000 = 240.355,99 (el cliente registró 800.000).
# · C-08 medición posterior (102A): el cliente reconoció 18.500 en resultados después de la venta → problema con ese importe.
# · C-09 local cerrado: neto 71.307,75 vs importe recuperable 50.000 → deterioro 21.307,75.
# · C-05 parqueo 12 meses exento: gasto 2025 = 300 × 12 ÷ 12 × 6 = 1.800. C-03 vehículo: exención mal aplicada.
# · C-10 bodega sur, 36 pagos mensuales de 2.000 (200 ligados al IPC) + 50 variables, 12 % efectivo → i = 1,12^(1/12) − 1 =
#   0,00948879. NIIF completas: el componente indexado entra en la medición (27 b) → VP con 2.000 = 60.749,51; tras 24 meses
#   pasivo = 2.000 × (1 − (1 + i)^−12) ÷ i = 22.583,03, interés 2025 = 24.000 − (42.746,45 − 22.583,03) = 3.836,58,
#   depreciación = 60.749,51 ÷ 36 × 12 = 20.249,84 y gasto variable del año = 50 × 12 = 600.
#   PYMES (operativo): se mide con el pago base 1.800 → gasto lineal 1.800 × 12 = 21.600 y gasto variable (200 + 50) × 12 = 3.000.
# · C-11 oficina regional: indexación declarada sin el importe → pago base y componente vacíos y problema (M22).
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"convencionTasa": "Efectiva anual", "umbralVida": 75, "umbralVP": 90, "limiteBajoValor": 5000},
    "datasets": {"contratos": [
        _k("C-01", "Local comercial matriz", "2024-01-01", "36", "1500", "Mensual", "12", "17000", renov_meses="24", renov_cierta="Sí",
           plazo_cliente="36", tipo_tasa="Incremental", clasif_pymes="Operativo", activo_reg="16500", pasivo_cp_reg="17000", int_reg="2600"),
        _k("C-02", "Bodega norte", "2023-01-01", "60", "10000", "Anual", "10", "17355.37", tipo_tasa="Incremental", costos="500",
           valor_razonable="40000", clasif_pymes="Operativo", pasivo_cp_reg="10000", activo_reg="15363.15", dep_reg="7681.57", int_reg="2486.85"),
        _k("C-03", "Vehículo de gerencia", "2025-04-01", "36", "900", "Mensual", "11", "0", momento="Inicio", bajo_valor="Sí",
           exencion="Sí", valor_razonable="45000", clasif_pymes="Operativo"),
        _k("C-04", "Computadores portátiles", "2025-01-01", "24", "80", "Mensual", "12", "0", bajo_valor="Sí", exencion="Sí",
           valor_razonable="1200", clasif_pymes="Operativo"),
        _k("C-05", "Parqueadero temporal", "2025-07-01", "12", "300", "Mensual", "10", "0", exencion="Sí", clasif_pymes="Operativo"),
        _k("C-06", "Montacargas con opción de compra", "2024-07-01", "48", "6000", "Trimestral", "9", "57428.43", opcion_compra="5000",
           compra_cierta="Sí", vida_util="120", valor_razonable="85000", tipo_tasa="Implícita", clasif_pymes="Financiero",
           activo_reg="71291.60", pasivo_cp_reg="19626.90", dep_reg="8387.25", int_reg="5993.67"),
        _k("C-07", "Oficina sucursal", "2023-01-01", "60", "12000", "Anual", "8", "19925.16", fecha_evento="2025-01-01",
           tipo_evento="Modificación", nuevo_pago="13500", nueva_tasa="9", remedido="No", clasif_pymes="Operativo",
           activo_reg="19165.01", int_reg="2474.01"),
        _k("C-08", "Edificio administrativo (venta con arrendamiento posterior)", "2025-01-01", "216", "120000", "Anual", "4.5", "1404862.97",
           valor_razonable="1800000", venta_posterior="Sí", precio_venta="2000000", libros_previo="1000000", ganancia_reg="800000",
           ganancia_post_reg="18500", clasif_pymes="Operativo", activo_reg="660690.84"),
        _k("C-09", "Local cerrado en centro comercial", "2024-01-01", "60", "2500", "Mensual", "10", "77966.15", recuperable="50000",
           clasif_pymes="Operativo", activo_reg="71307.75"),
        _k("C-10", "Bodega sur con renta ajustada por inflación", "2024-01-01", "36", "2000", "Mensual", "12", "0",
           indexado="Sí", pago_indexado="200", indice="IPC del INEC (Ecuador)", pago_variable="50", clasif_pymes="Operativo"),
        _k("C-11", "Oficina regional con reajuste sin detalle", "2025-01-01", "24", "1000", "Mensual", "10", "0",
           indexado="Sí", indice="Índice de precios del contrato", clasif_pymes="Operativo"),
    ]},
}

_BASE = EJEMPLO["parametros"]
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], {**_BASE, "_marco": "NIIF completas"}, EJEMPLO["corte"]),
    ("tasa_nominal", EJEMPLO["datasets"], {**_BASE, "convencionTasa": "Nominal anual", "_marco": "NIIF completas"}, EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**_BASE, "_marco": "NIIF para las PYMES", "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**_BASE, "_marco": "NIIF para las PYMES", "_edicion": "2025"}, EJEMPLO["corte"]),
]
