"""Servicio que orquesta el análisis completo de pérdidas esperadas."""
import io
from datetime import date

import pytest
from openpyxl import Workbook

from backend.app.aud.pce_cxc.service import analizar


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Documento", "Tipo", "Emisión", "Vencimiento", "Saldo"])
    for f in filas:
        ws.append(list(f))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _cortes():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0),
                 ("BETA", "F-2", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 3, 1), 50000.0)])
    c24 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 20000.0)])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0),
                 ("GAMMA", "F-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 200000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_mide_la_cartera_con_las_tasas_de_la_cohorte():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    # F-1 estaba en "0 a 30 días" en 2023 con 100.000 y quedaron vivos 10.000 -> 10 %
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(0.10)
    # F-9 (200.000, 30 días de mora) se mide al 10 %; F-1 cayó en "Más de 730 días",
    # banda sin historia en la cohorte, así que queda sin medir y no suma cero.
    assert r["matriz"]["ecl_total"] == pytest.approx(20000.0)
    assert r["matriz"]["exposicion_sin_medir"] == pytest.approx(10000.0)


def test_el_saldo_contable_manda_sobre_el_archivo_y_la_diferencia_se_informa():
    r = analizar(_cortes(), {"eeff": {"no_relacionados": 220000.0, "relacionados": 0.0}})
    # La exposición se ancla a los estados financieros y la conciliación cierra...
    assert r["exposicion"]["total"] == pytest.approx(220000.0)
    assert r["conciliacion"]["cuadra"] is True
    # ...pero la diferencia contra el archivo queda a la vista como partida conciliatoria.
    assert r["exposicion"]["segun_archivo"] == pytest.approx(210000.0)
    assert r["exposicion"]["factores_anclaje"]["NO-RELACIONADOS"] == pytest.approx(220000 / 210000)


def test_el_factor_prospectivo_sin_justificacion_genera_hallazgo():
    r = analizar(_cortes(), {})
    titulos = [h["titulo"] for h in r["hallazgos"]]
    assert "Ausencia del componente prospectivo" in titulos


def test_sin_materialidad_no_concluye():
    r = analizar(_cortes(), {})
    assert any(p["variable"] == "Materialidad de desempeño" for p in r["pendientes"])


def test_exige_los_tres_cortes():
    with pytest.raises(ValueError, match="tres"):
        analizar(_cortes()[:2], {})


def _cortes_anomalia():
    # DELTA / F-7 crece de 1.000 (cohorte, 2023) a 5.000 (corte actual, 2025):
    # el remanente supera al inicial, lo que dispara la anomalía de la cohorte
    # (tasas_por_permanencia la acota a 1.0 y la deja registrada).
    c23 = _xlsx([("DELTA", "F-7", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 11, 1), 1000.0)])
    c24 = _xlsx([("DELTA", "F-7", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 11, 1), 3000.0)])
    c25 = _xlsx([("DELTA", "F-7", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 11, 1), 5000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_las_anomalias_de_cohorte_se_exponen_y_generan_pendiente():
    r = analizar(_cortes_anomalia(), {})
    assert len(r["anomalias"]) == 1
    anomalia = r["anomalias"][0]
    assert anomalia["tipo"] == "remanente_mayor_que_inicial"
    assert anomalia["segmento"] == "NO-RELACIONADOS"

    variables = [p["variable"] for p in r["pendientes"]]
    assert "Tasas de cohorte fuera de rango" in variables
    pendiente = next(p for p in r["pendientes"] if p["variable"] == "Tasas de cohorte fuera de rango")
    assert pendiente["responsable"] == "Gerente / Socio"
    assert pendiente["criticidad"] == "Alta"
