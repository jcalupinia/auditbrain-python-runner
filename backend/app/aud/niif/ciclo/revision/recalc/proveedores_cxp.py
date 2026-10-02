"""Recálculo independiente del resultado principal de «Proveedores y cuentas por pagar».

Re-deriva el **ajuste neto propuesto** (``totals["ajusteNeto"]``) volviendo a agregar
los datos crudos de ``run["detalle"]`` con una suma escrita aparte del procesador, y lo
coteja contra lo que declaró el motor. Es la segunda implementación de la identidad
central de la prueba.

En el procesador el saldo auditado se arma como
``auditado = libros + omitido − anticipado − ajusteFin + deudores`` y el ajuste neto es
``ajusteNeto = auditado − libros``; al cancelarse ``libros`` la identidad queda::

    ajusteNeto = pasivoNoRegistrado − corteAnticipado − ajusteFinanciacion + saldosDeudores

Cada componente se re-arma desde su detalle más crudo, sin reutilizar los totales del
procesador:

- **Pasivos no registrados** (+): suma del ``importe`` de cada pago/factura de
  ``detalle["busqueda"]`` que es posterior al corte, con causa hasta el corte y sin
  registrar (``registrado == "No"``).
- **Compras registradas antes de la recepción** (−): suma del ``saldo`` de cada fila de
  ``detalle["filas"]`` con recepción informada pero aún no recibida al corte
  (``recepcion`` presente y ``recibida`` falso).
- **Ajuste por financiación implícita** (−): suma del interés implícito por devengar de
  cada fila (``interes``) menos el descuento ya registrado (``detalle["descuentoRegistrado"]``).
- **Saldos deudores reclasificados al activo** (+): suma de ``−saldo`` de cada fila con
  saldo negativo (anticipos / notas de crédito dentro de proveedores).

Si algún operando falta se devuelve ``None`` (no revienta), y el cotejo marca la
divergencia si la agregación del procesador se desvía (un signo, una fila que no suma).
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _es_no(v) -> bool:
    return str(v).strip().lower() in ("no", "n", "false")


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    filas = d.get("filas") or []
    busqueda = d.get("busqueda") or []
    desc_reg = _num(d.get("descuentoRegistrado")) or 0.0

    # (+) Pasivos no registrados: pagos/facturas posteriores al corte, con causa hasta
    #     el corte y sin registrar, re-sumados desde su importe crudo.
    pasivo_no_reg = round(sum(
        _num(b.get("importe")) or 0.0
        for b in busqueda
        if b.get("posterior") and b.get("causa") and _es_no(b.get("registrado"))
    ), 2)

    # (-) Compras registradas antes de la recepción: saldo de las filas con recepción
    #     informada que todavía no se había recibido al corte.
    corte_anticipado = round(sum(
        _num(x.get("saldo")) or 0.0
        for x in filas
        if x.get("recepcion") and not x.get("recibida")
    ), 2)

    # (-) Ajuste por financiación implícita: intereses implícitos por devengar
    #     requeridos menos los ya registrados.
    interes_req = round(sum(_num(x.get("interes")) or 0.0 for x in filas), 2)
    ajuste_fin = round(interes_req - desc_reg, 2)

    # (+) Saldos deudores a reclasificar al activo: −saldo de cada fila con saldo
    #     negativo (anticipos / notas de crédito).
    saldos_deudores = round(sum(
        -(_num(x.get("saldo")) or 0.0)
        for x in filas
        if (_num(x.get("saldo")) or 0.0) < 0
    ), 2)

    # Identidad central: ajuste neto propuesto a proveedores.
    ajuste = round(pasivo_no_reg - corte_anticipado - ajuste_fin + saldos_deudores, 2)

    declarado = _num(tot.get("ajusteNeto"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("(+) Pasivos no registrados", pasivo_no_reg, "pasivoNoRegistrado"),
        ("(−) Compras registradas antes de la recepción", corte_anticipado, "corteAnticipado"),
        ("(−) Ajuste por financiación implícita", ajuste_fin, "ajusteFinanciacion"),
        ("(+) Saldos deudores reclasificados al activo", saldos_deudores, "saldosDeudores"),
        ("Ajuste neto propuesto a proveedores", ajuste, "ajusteNeto"),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": "Ajuste neto propuesto a proveedores",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
