# backend/app/client_portal/flujo/motor_resumen.py
"""Balance resumido — Estado de Resultados + ESF condensados (hoja "ER y ESF").

Reproduce la presentación resumida del modelo: un Estado de Resultados en pocas
líneas y un ESF condensado, ambos con columna del año actual y anterior. Cada
línea se arma con el mapeo (código → signo) resuelto de las fórmulas del modelo.
"""
from __future__ import annotations


def _r2(x) -> float:
    return round(float(x or 0.0), 2)


# Líneas basadas en códigos: (etiqueta, estado, [(signo, codigo)...])
# estado: "eri" usa los totales del ERI; "esf" usa los del ESF (con rollup).
_ER_TOKENS = {
    "ventas_netas": ("eri", [(1, "40101"), (1, "40102")]),
    "costo_ventas": ("eri", [(1, "501")]),
    "gastos_operativos": ("eri", [(1, "50201"), (1, "50202")]),
    "gastos_financieros": ("eri", [(1, "50203")]),
    "otros_ingresos": ("eri", [(1, "40106"), (1, "40107"), (1, "40108"),
                                (1, "40109"), (1, "40110"), (1, "403")]),
    "otros_gastos": ("eri", [(1, "50204")]),
    "participacion": ("eri", [(1, "601")]),
    # Impuestos = IR causado + gasto diferido − ingreso diferido
    "impuestos": ("eri", [(1, "603"), (1, "605"), (-1, "606")]),
}
_ESF_TOKENS = {
    "activo_corriente": [(1, "101")],
    "cuentas_cobrar": [(1, "10102050201"), (1, "1010207")],
    "inventarios": [(1, "10103")],
    "activo_no_corriente": [(1, "102")],
    "pasivo_corriente": [(-1, "201")],
    "cuentas_pagar": [(-1, "201030102"), (-1, "201030202")],
    "obligaciones_financieras": [(-1, "20104"), (-1, "20203")],
    "pasivo_no_corriente": [(-1, "202")],
    "patrimonio_base": [(-1, "301"), (-1, "302"), (-1, "303"),
                         (-1, "304"), (-1, "305"), (-1, "306")],
    "resultado_ejercicio": [(-1, "307")],
}


def _suma(tot: dict, tokens) -> float:
    return _r2(sum(sg * float(tot.get(cod, 0.0) or 0.0) for sg, cod in tokens))


def _bloque(tot_eri: dict, tot_esf: dict) -> dict:
    er = {k: _suma(tot_eri, toks) for k, (_e, toks) in _ER_TOKENS.items()}
    er["utilidad_bruta"] = _r2(er["ventas_netas"] - er["costo_ventas"])
    er["utilidad_operacional"] = _r2(er["utilidad_bruta"] - er["gastos_operativos"])
    er["utilidad_antes_part"] = _r2(er["utilidad_operacional"] - er["gastos_financieros"]
                                    + er["otros_ingresos"] - er["otros_gastos"])
    er["utilidad_neta"] = _r2(er["utilidad_antes_part"] - er["participacion"] - er["impuestos"])

    esf = {k: _suma(tot_esf, toks) for k, toks in _ESF_TOKENS.items()}
    esf["total_activo"] = _r2(esf["activo_corriente"] + esf["activo_no_corriente"])
    esf["total_pasivo"] = _r2(esf["pasivo_corriente"] + esf["pasivo_no_corriente"])
    esf["total_patrimonio"] = _r2(esf["patrimonio_base"] + esf["resultado_ejercicio"])
    esf["total_pasivo_patrimonio"] = _r2(esf["total_pasivo"] + esf["total_patrimonio"])
    return {"er": er, "esf": esf}


# Orden y etiquetas de presentación. es_total marca las filas resaltadas.
_ER_ORDEN = [
    ("ventas_netas", "Ventas netas", False),
    ("costo_ventas", "Costo de ventas", False),
    ("utilidad_bruta", "Utilidad bruta", True),
    ("gastos_operativos", "Gastos operativos", False),
    ("utilidad_operacional", "Utilidad operacional", True),
    ("gastos_financieros", "Gastos financieros", False),
    ("otros_ingresos", "Otros ingresos", False),
    ("otros_gastos", "Otros gastos", False),
    ("utilidad_antes_part", "Utilidad antes de participación e impuestos", True),
    ("participacion", "Participación trabajadores 15%", False),
    ("impuestos", "Impuestos", False),
    ("utilidad_neta", "Utilidad neta", True),
]
_ESF_ORDEN = [
    ("activo_corriente", "Activo corriente", False),
    ("cuentas_cobrar", "Cuentas por cobrar", False),
    ("inventarios", "Inventarios", False),
    ("activo_no_corriente", "Activo no corriente", False),
    ("total_activo", "Total activo", True),
    ("pasivo_corriente", "Pasivo corriente", False),
    ("cuentas_pagar", "Cuentas por pagar", False),
    ("obligaciones_financieras", "Obligaciones financieras", False),
    ("pasivo_no_corriente", "Pasivo no corriente", False),
    ("total_pasivo", "Total pasivo", True),
    ("patrimonio_base", "Patrimonio", False),
    ("resultado_ejercicio", "Utilidad/pérdida del ejercicio", False),
    ("total_patrimonio", "Total patrimonio", True),
    ("total_pasivo_patrimonio", "Total pasivo + patrimonio", True),
]


def balance_resumido(tot_esf_ant, tot_esf_act, tot_eri_ant, tot_eri_act) -> dict:
    """Devuelve ``{"er": [fila...], "esf": [fila...]}`` con año actual y anterior.

    fila = ``{clave, concepto, act, ant, es_total}``.
    """
    act = _bloque(tot_eri_act, tot_esf_act)
    ant = _bloque(tot_eri_ant, tot_esf_ant)

    def filas(seccion, orden):
        return [{"clave": k, "concepto": lbl, "es_total": tot,
                 "act": act[seccion][k], "ant": ant[seccion][k]}
                for k, lbl, tot in orden]

    return {"er": filas("er", _ER_ORDEN), "esf": filas("esf", _ESF_ORDEN)}
