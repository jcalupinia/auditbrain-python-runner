"""Pérdidas incurridas · 11_Detalle: el TOTAL del valor presente que calcula Python
es el mismo que muestra Excel al recalcular.

La columna I lleva por fila `G*(1-H)/DESC` sin redondear y el TOTAL es `SUM(I5:I…)`.
Antes, Python sumaba los valores ya redondeados a centavos por fila, así que en el
ejercicio modelo daba 118.372,05 mientras Excel (y LibreOffice) mostraban 118.372,06.
"""
from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.procesadores import PROCESADORES, problemas


def _detalle():
    mod = PROCESADORES["perdidas_incurridas_s11"]
    ds, par, corte = em.escenario(mod)
    res = mod.ejecutar(ds, par, corte)
    h = next(x for x in mod.hojas(res) if x["name"] == "11_Detalle")
    return res, h


def test_total_valor_presente_igual_al_sum_de_excel():
    res, h = _detalle()
    p = res["detalle"]["parametros"]
    desc = (1 + float(p["tasaDesc"]) / 100) ** (float(p["plazoBase"]) / 12)
    # Lo que calcula Excel: cada fila sin redondear (Saldo G, Tasa H) y luego SUM.
    excel = sum(problemas._num(f[6]) * (1 - f[7]["v"]) / desc for f in h["rows"]
                if isinstance(f[7], dict) and f[7]["v"] is not None)
    total = h["total"][8]
    assert total["f"].startswith("SUM(I")
    assert abs(total["v"] - round(excel, 2)) < 0.005, (total["v"], excel)


def test_ejercicio_modelo_valor_recalculado_en_libreoffice():
    _, h = _detalle()
    assert h["total"][8]["v"] == 118372.06
