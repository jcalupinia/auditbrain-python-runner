"""Regresión del off-by-one de columna en la matriz PCE (AUD-ECL-01).

La "Pérdida esperada" de 05_Matriz_PCE está en la columna H. Un bug hacía que los
agregadores (01_Resumen, 06_Por_banda, 08_Conciliacion y el total propio de la matriz)
referenciaran la columna I (vacía): el SUM/SUMIF daba 0 en Excel aunque Python calculaba
el valor correcto, dejando el papel sin trazabilidad. Este test lo atrapa sin necesidad
de Excel: inspecciona las fórmulas generadas por `hojas()`.
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores import pce_cohortes_niif9 as m


def _formulas(hojas):
    out = []
    for h in hojas:
        filas = list(h["rows"]) + ([h["total"]] if h.get("total") else [])
        for fila in filas:
            for c in fila:
                if isinstance(c, dict) and "f" in c:
                    out.append((h["name"], c["f"]))
    return out


def test_matriz_pce_se_agrega_por_columna_h_no_i():
    res = m.ejecutar(m.EJEMPLO["datasets"], m.EJEMPLO["parametros"], m.EJEMPLO["corte"])
    hojas = m.hojas(res)
    fs = _formulas(hojas)

    # Ningún agregador debe referenciar la columna I (vacía) de la matriz.
    malas = [(n, f) for n, f in fs if "'05_Matriz_PCE'!$I$" in f]
    assert not malas, f"referencias a la columna I vacía de la matriz: {malas[:3]}"

    # Debe existir al menos un agregado sobre la columna H (Pérdida esperada) de la matriz.
    assert any("'05_Matriz_PCE'!$H$" in f for _, f in fs), "ningún agregado sobre 05_Matriz_PCE!H"

    # El total propio de la matriz (columna H = Pérdida esperada) suma H, no I.
    h05 = next(h for h in hojas if h["name"] == "05_Matriz_PCE")
    tot_pce = h05["total"][7]
    assert isinstance(tot_pce, dict) and "SUM(H" in tot_pce["f"] and "SUM(I" not in tot_pce["f"], tot_pce
