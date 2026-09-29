"""Recálculo independiente del resultado principal de «Pérdidas incurridas (Sección 11)».

Re-deriva el **ajuste propuesto** (``totals["ajuste"]``) volviendo a agregar los datos
crudos de ``run["detalle"]`` con una aritmética escrita aparte del procesador. Es la
segunda implementación de la identidad central de la prueba:

    ajuste = pérdida incurrida recalculada − provisión registrada

donde cada operando se re-arma desde su colección de detalle más cruda:

* **Pérdida incurrida** (11.25/11.26): suma del deterioro por factura de la colección
  ``detalle["movimiento"]`` (columna ``provAnio``, el gasto del año por documento; las
  filas de baja y las pendientes aportan 0). Es la agregación factura por factura de la
  pérdida, independiente del acumulado ``perdida_total`` del procesador.
* **Provisión registrada** (según el mayor): se recorre la colección ``detalle["mayor"]``
  año por año reconstruyendo el saldo con los movimientos crudos del cliente
  (``ini + gasto − castigos + recuperaciones``); la provisión registrada es el saldo
  final del último ejercicio. No se copia ``totals["provisionRegistrada"]``: se re-deriva.

El ajuste re-derivado se coteja contra ``totals["ajuste"]``. Si la agregación del
procesador se desvía (un signo, una factura que no suma, un movimiento del mayor mal
armado), el cotejo lo marca y el veredicto de la consola baja a NO APTO.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    if isinstance(v, dict):
        v = v.get("v")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _perdida_incurrida(detalle: dict):
    """Σ del deterioro por factura desde ``detalle["movimiento"]`` (columna ``provAnio``).

    Es el gasto del año documento por documento (11.26); las bajas y pendientes aportan 0.
    Devuelve ``None`` si no hay colección de movimiento de la que partir.
    """
    filas = detalle.get("movimiento")
    if not filas:
        return None
    return round(sum(_num(f.get("provAnio")) or 0.0 for f in filas), 2)


def _provision_registrada(detalle: dict):
    """Saldo final del mayor de la provisión, recorriendo ``detalle["mayor"]`` año a año.

    Reconstruye el saldo con los movimientos crudos del cliente
    (``ini + gasto − castigos + recuperaciones``); si un año no trae inicial, arrastra el
    saldo final del anterior. La provisión registrada es el saldo final del último año.
    Devuelve ``None`` si no hay mayor.
    """
    filas = detalle.get("mayor")
    if not filas:
        return None
    saldo = 0.0
    for m in filas:
        ini = _num(m.get("ini"))
        if ini is None:
            ini = saldo
        saldo = ini + (_num(m.get("gasto")) or 0.0) - (_num(m.get("cast")) or 0.0) + (_num(m.get("rec")) or 0.0)
    return round(saldo, 2)


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}

    # Re-arma cada operando desde su colección de detalle más cruda (independiente del motor).
    perdida = _perdida_incurrida(d)
    prov_reg = _provision_registrada(d)
    ajuste = None if (perdida is None or prov_reg is None) else round(perdida - prov_reg, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Pérdida incurrida recalculada (Σ deterioro por factura)", perdida, "perdida"),
        ("Provisión registrada según el mayor (saldo final)", prov_reg, "provisionRegistrada"),
        ("Ajuste propuesto (pérdida − provisión registrada)", ajuste, "ajuste"),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": "Ajuste propuesto (pérdida incurrida − provisión registrada)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
