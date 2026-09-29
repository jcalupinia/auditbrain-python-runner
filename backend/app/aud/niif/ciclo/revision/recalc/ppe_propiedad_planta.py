"""Recálculo independiente del resultado principal de «Propiedad, planta y equipo».

Re-deriva el **efecto neto de los ajustes en resultados** (``totals["ajusteResultado"]``,
el ``primary`` del rubro) volviendo a agregar los datos por partida de ``run["detalle"]``
con una aritmética escrita aparte del procesador. Es la segunda implementación de la
identidad central de la prueba: el ajuste a resultados es la suma, con su signo, de los
seis efectos que impactan el estado de resultados (NIC 16 / 36 / 23 / CINIIF 1):

    ajusteResultado = − ajusteDep                (diferencia de depreciación)
                      − deterioroResultado        (deterioro imputado a resultados)
                      + ajusteBajas               (diferencia en el resultado de las bajas)
                      + ajusteIntereses           (diferencia de intereses capitalizados)
                      + revaluacionResultado      (revaluación reconocida en resultados)
                      − desmantelamientoFinanciero (actualización financiera del período)

De qué campos crudos parte cada componente (``detalle``), sin reutilizar el acumulado
``detalle["ajustes"]`` del motor:

- **ajusteDep**: por activo, ``dep − dreg`` (depreciación recalculada menos registrada),
  sumando solo los activos cuya depreciación se pudo recalcular (método lineal).
- **ajusteBajas**: por baja, se re-arma el resultado ``(prod) − (costo − dep.acum − det)``
  y se le resta el resultado registrado ``resreg``.
- **ajusteIntereses**: con anexo de préstamos, por activo ``final − reg`` de la cédula de
  capitalización; sin anexo, por adición ``cap − intereses`` (rama de la tasa del parámetro).
- **deterioroResultado** y **revaluacionResultado**: se suma el importe que el procesador
  imputó a resultados por activo (``detRes`` y ``rev_res``). El reparto contra el superávit
  de revaluación (ORI) es la cascada NIC 36.60-61 / 16.39-40 del procesador; aquí solo se
  re-agrega la parte que llega a resultados (no se re-implementa la cascada).
- **desmantelamientoFinanciero**: la reversión del descuento del período, ``inicial × tasa``
  (saldo inicial de la provisión por la tasa de descuento), que es costo financiero (CINIIF 1.8).

Cada componente se coteja contra el total que declaró el motor y el ajuste re-derivado
contra ``totals[primary]``. Robusto ante operandos faltantes: un dato ausente no revienta,
la partida no suma (o el componente queda en None) y el cotejo lo marca.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    if isinstance(v, bool) or v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _ajuste_dep(activos) -> float:
    """Σ (depreciación recalculada − registrada) de los activos con recálculo (método lineal)."""
    tot = 0.0
    for a in activos:
        dep, dreg = _num(a.get("dep")), _num(a.get("dreg"))
        if dep is not None and dreg is not None:
            tot += dep - dreg
    return tot


def _ajuste_bajas(activos) -> float:
    """Σ del resultado de la baja re-armado: (producto) − (costo − dep.acum − deterioro) − registrado."""
    tot = 0.0
    for a in activos:
        if not a.get("baja"):
            continue
        costo, acum = _num(a.get("costo")), _num(a.get("acum"))
        resreg = _num(a.get("resreg"))
        if costo is None or acum is None or resreg is None:
            continue
        nbv_baja = costo - acum - (_num(a.get("det")) or 0.0)
        res_calc = (_num(a.get("prod")) or 0.0) - nbv_baja
        tot += res_calc - resreg
    return tot


def _ajuste_intereses(detalle) -> float:
    """Diferencia de intereses capitalizados. Con anexo de préstamos: Σ (capitalizable − registrado)
    por activo (cédula de capitalización). Sin anexo: Σ (capitalizable − intereses) por adición."""
    if detalle.get("prestamos"):
        tot = 0.0
        for c in detalle.get("capitalizacion") or []:
            final, reg = _num(c.get("final")), _num(c.get("reg"))
            if final is not None and reg is not None:
                tot += final - reg
        return tot
    tot = 0.0
    for x in detalle.get("adiciones") or []:
        cap = _num(x.get("cap"))
        if cap is not None:
            tot += cap - (_num(x.get("int")) or 0.0)
    return tot


def _suma_campo(activos, clave) -> float:
    """Σ del importe imputado a resultados por activo (``detRes`` o ``rev_res``)."""
    tot = 0.0
    for a in activos:
        v = _num(a.get(clave))
        if v is not None:
            tot += v
    return tot


def _desmantelamiento_financiero(desm) -> float:
    """Actualización financiera del período = saldo inicial de la provisión × tasa de descuento."""
    inicial, tasa = _num(desm.get("inicial")), _num(desm.get("tasa"))
    if inicial is None or tasa is None:
        return 0.0
    return inicial * tasa / 100.0


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    labels = run.get("labels") or {}
    primary = run.get("primary") or "ajusteResultado"
    activos = d.get("activos") or []
    desm = d.get("desmantelamiento") or {}

    # Re-agrega cada componente que impacta resultados desde los datos por partida.
    dep = round(_ajuste_dep(activos), 2)
    det_res = round(_suma_campo(activos, "detRes"), 2)
    bajas = round(_ajuste_bajas(activos), 2)
    intereses = round(_ajuste_intereses(d), 2)
    rev_res = round(_suma_campo(activos, "rev_res"), 2)
    desm_fin = round(_desmantelamiento_financiero(desm), 2)

    # Identidad central: efecto neto de los ajustes en resultados, con su signo.
    ajuste = round(-dep - det_res + bajas + intereses + rev_res - desm_fin, 2)

    declarado = _num(tot.get(primary))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Diferencia de depreciación (recalculada − registrada)", dep, "ajusteDep"),
        ("Deterioro a resultados", det_res, "deterioroResultado"),
        ("Diferencia en resultado de bajas", bajas, "ajusteBajas"),
        ("Ajuste de intereses capitalizados", intereses, "ajusteIntereses"),
        ("Revaluación a resultados", rev_res, "revaluacionResultado"),
        ("Desmantelamiento: actualización financiera del período", desm_fin, "desmantelamientoFinanciero"),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": labels.get(primary) or "Efecto neto de los ajustes en resultados",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
