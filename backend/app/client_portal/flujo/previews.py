# backend/app/client_portal/flujo/previews.py
"""Vistas previas (tabla de cada sección) para mostrarlas EN VIVO en el portal,
sin descargar el archivo. Cada sección devuelve columnas + filas listas para
renderizar, con los mismos valores que el Excel/TXT.
"""
from __future__ import annotations

from . import (
    catalogos,
    motor,
    motor_er,
    motor_f101,
    motor_flujo,
    motor_indicadores,
    motor_no_efectivo,
    motor_patrimonio,
)
from .exportadores import (
    _ERI_ORI_CODES,
    _ERI_RESULTADO_INTEGRAL,
    _ERI_SUBTOTAL_KEYS,
    _ESF_TXT_EXCLUIR,
)

_PAT_LABEL = {
    "capital": "Capital",
    "aportes_socios": "Aportes de socios",
    "prima_emision": "Prima por emisión",
    "reservas": "Reservas",
    "otros_resultados_integrales": "Otros resultados integrales",
    "resultados_acumulados": "Resultados acumulados",
    "resultado_ejercicio": "Resultado del ejercicio",
}
_IND_LABEL = {
    "razon_corriente": "Razón corriente",
    "capital_trabajo": "Capital de trabajo",
    "endeudamiento_total": "Endeudamiento total",
    "apalancamiento": "Apalancamiento",
    "margen_neto": "Margen neto",
    "roa": "ROA",
    "roe": "ROE",
}
# indicadores que se muestran como porcentaje
_IND_PCT = {"endeudamiento_total", "margen_neto", "roa", "roe"}


def _r(v) -> float:
    return round(float(v or 0.0), 2)


def construir_previews(bal_ant: list[dict], bal_act: list[dict]) -> dict:
    """Devuelve ``{seccion: {"cols": [...], "rows": [[...]]}}`` para cada sección."""
    est_esf = catalogos.cargar_estructura("esf")
    est_eri = catalogos.cargar_estructura("eri")
    sa, _ = motor.homologar_balanza(bal_ant)
    sc, _ = motor.homologar_balanza(bal_act)
    tot_esf_ant = motor.totales_por_codigo(est_esf, sa)
    tot_esf = motor.totales_por_codigo(est_esf, sc)
    tot_eri = motor.totales_por_codigo(est_eri, sc)
    cascada = motor_er.cascada_resultados(tot_eri)
    ori = motor_f101.ori_del_periodo(bal_ant, bal_act)

    prev: dict = {}

    # ---- ESF ----
    rows = []
    vistos: set[str] = set()
    for n in est_esf:
        if n.codigo in vistos or n.codigo in _ESF_TXT_EXCLUIR:
            continue
        vistos.add(n.codigo)
        raw = tot_esf.get(n.codigo, 0.0)
        val = raw if n.codigo.startswith("1") else -raw
        rows.append([n.codigo, n.etiqueta, _r(val)])
    prev["ESF"] = {"cols": ["Código", "Cuenta", "Saldo 31-Dic"], "rows": rows}

    # ---- ERI ----
    rows = []
    for n in est_eri:
        c = n.codigo
        if c in _ERI_SUBTOTAL_KEYS:
            val = cascada.get(_ERI_SUBTOTAL_KEYS[c], 0.0)
        elif c in _ERI_ORI_CODES:
            val = ori
        elif c == _ERI_RESULTADO_INTEGRAL:
            val = cascada.get("utilidad_neta", 0.0) + ori
        else:
            val = tot_eri.get(c, 0.0)
        rows.append([c, n.etiqueta, _r(val)])
    prev["ERI"] = {"cols": ["Código", "Cuenta", "Valor"], "rows": rows}

    # ---- Patrimonio ----
    pat = motor_patrimonio.evolucion(tot_esf_ant, tot_esf)
    rows = []
    for key, label in _PAT_LABEL.items():
        c = pat.get(key)
        if c:
            rows.append([label, _r(c["saldo_inicial"]), _r(c["variacion"]), _r(c["saldo_final"])])
    tp = pat.get("total_patrimonio", {})
    rows.append(["TOTAL PATRIMONIO", _r(tp.get("saldo_inicial")), _r(tp.get("variacion")), _r(tp.get("saldo_final"))])
    prev["PAT"] = {"cols": ["Componente", "Saldo inicial", "Variación", "Saldo final"], "rows": rows}

    # ---- Flujo de Efectivo ----
    clas = catalogos.cargar_clasificacion_flujo()
    fl = motor_flujo.flujo_efectivo(tot_esf_ant, tot_esf, clas)
    prev["FLU"] = {"cols": ["Concepto", "Valor"], "rows": [
        ["Flujo de actividades de operación", _r(fl["operacion"])],
        ["Flujo de actividades de inversión", _r(fl["inversion"])],
        ["Flujo de actividades de financiamiento", _r(fl["financiamiento"])],
        ["Incremento neto en el efectivo", _r(fl["incremento_neto"])],
        ["Efectivo al inicio del período", _r(fl["efectivo_inicial"])],
        ["Efectivo al final del período", _r(fl["efectivo_final_calculado"])],
        ["Cuadre (AF)", _r(fl["cuadre_af"])],
    ]}

    # ---- Movimiento no Efectivo ----
    mne = motor_no_efectivo.gastos_no_efectivo(tot_eri, catalogos.cargar_no_efectivo())
    rows = [
        ["Depreciación", _r(mne.get("DEPRECIACION"))],
        ["Amortización", _r(mne.get("AMORTIZACION"))],
        ["Deterioro", _r(mne.get("DETERIORO"))],
        ["TOTAL no efectivo", _r(mne.get("total"))],
    ]
    prev["MNE"] = {"cols": ["Concepto", "Del período"], "rows": rows}

    # ---- Homologación (Mapeo) ----
    rows = [[str(f.get("cuenta") or ""), f.get("super_cias", ""), f.get("sri", ""), _r(f.get("saldo"))]
            for f in bal_act]
    prev["MAP"] = {"cols": ["Cuenta", "Super Cías", "SRI", "Saldo"], "rows": rows}

    # ---- Formulario 101 ----
    cas = motor_f101.casilleros_completos(
        bal_act, catalogos.cargar_agregados_f101(), extras={"885": ori})
    rows = [[c, _r(cas[c])] for c in sorted(cas, key=lambda x: int(x)) if cas[c]]
    prev["101"] = {"cols": ["Casillero", "Valor"], "rows": rows}

    # ---- Indicadores ----
    eri_ind = dict(cascada)
    eri_ind["_ingresos_totales"] = cascada.get("ingresos_ordinarios", 0.0) + cascada.get("otros_ingresos", 0.0)
    ind = motor_indicadores.indicadores(tot_esf, eri_ind)
    rows = []
    for key, label in _IND_LABEL.items():
        if key in ind:
            v = ind[key]
            txt = f"{round(v * 100, 2)}%" if key in _IND_PCT else _r(v)
            rows.append([label, txt])
    prev["IND"] = {"cols": ["Indicador", "Valor"], "rows": rows}

    return prev
