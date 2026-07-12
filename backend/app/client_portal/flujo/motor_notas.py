# backend/app/client_portal/flujo/motor_notas.py
"""Notas a los Estados Financieros — desglose por rubro.

Reproduce el formato de la hoja "NOTAS ESTADOS FINANCIEROS" del modelo: por cada
rubro con saldo, una nota que lista sus cuentas de detalle (código + nombre) con
el saldo del año anterior y el actual, y un subtotal del rubro.

Agrupación automática (determinista):
- **ESF**: una nota por cada cuenta mayor (código Super Cías de 5 dígitos, ej.
  10101 Efectivo, 10102 Activos financieros, 10103 Inventarios…) que tenga saldo
  distinto de cero en algún año. Lista sus cuentas hoja con saldo ≠ 0.
- **ERI**: una nota por cada grupo de resultados (código de 3 dígitos, ej. 401
  Ingresos, 501 Costo de ventas, 502 Gastos…) con saldo ≠ 0, listando sus hojas.

Solo se incluyen filas y notas con saldo distinto de cero en al menos un año, para
que el desglose sea legible (no cientos de cuentas del plan en cero).
"""
from __future__ import annotations


def _r2(x) -> float:
    return round(float(x or 0.0), 2)


def _hojas_del_rubro(estructura, prefijo, tot_ant, tot_act):
    """Cuentas hoja descendientes de `prefijo` con saldo ≠ 0 en algún año."""
    filas = []
    for n in estructura:
        if not n.es_hoja or n.codigo == prefijo or not n.codigo.startswith(prefijo):
            continue
        ant = _r2(tot_ant.get(n.codigo, 0.0))
        act = _r2(tot_act.get(n.codigo, 0.0))
        if ant or act:
            filas.append({"codigo": n.codigo, "nombre": n.etiqueta, "ant": ant, "act": act})
    return filas


def _notas_de(estructura, tot_ant, tot_act, nivel: int):
    notas = []
    for n in estructura:
        if len(n.codigo) != nivel:
            continue
        ant = _r2(tot_ant.get(n.codigo, 0.0))
        act = _r2(tot_act.get(n.codigo, 0.0))
        if not ant and not act:
            continue
        filas = _hojas_del_rubro(estructura, n.codigo, tot_ant, tot_act)
        if not filas:
            # El rubro es él mismo una cuenta hoja: la nota es una sola línea.
            filas = [{"codigo": n.codigo, "nombre": n.etiqueta, "ant": ant, "act": act}]
        notas.append({
            "codigo": n.codigo,
            "nombre": n.etiqueta,
            "filas": filas,
            "total_ant": ant,
            "total_act": act,
        })
    return notas


def notas_estados(est_esf, est_eri, tot_esf_ant, tot_esf_act,
                  tot_eri_ant, tot_eri_act) -> dict:
    """Devuelve ``{"esf": [nota...], "eri": [nota...]}``.

    Cada nota = ``{codigo, nombre, filas:[{codigo,nombre,ant,act}], total_ant,
    total_act}``. ESF se agrupa a nivel de cuenta mayor (5 dígitos); ERI a nivel
    de grupo de resultados (3 dígitos).
    """
    return {
        "esf": _notas_de(est_esf, tot_esf_ant, tot_esf_act, 5),
        "eri": _notas_de(est_eri, tot_eri_ant, tot_eri_act, 3),
    }
