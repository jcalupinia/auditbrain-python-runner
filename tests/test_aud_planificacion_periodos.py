"""Períodos de la planificación según el corte y el tipo de revisión.

Incidente 2026-10-05: la ficha guarda «Visita de auditoría = Preliminar» bajo la
clave ``engagement.visit``, pero la lógica de períodos solo miraba
``parametros.tipoRevision`` / ``engagement.mode``, así que una visita PRELIMINAR
salía como FINAL (comparaba contra Diciembre del corte en vez del mes del corte).

Contrato:
  - Preliminar (por tipoRevision, mode o visit): ESF Dic(A-1) → Mes(A); ERI Mes(A-1) → Mes(A);
    meses = mes del corte (para el prorrateo del ERI).
  - Final: ESF/ERI Dic(A-1) → Dic(A); meses = 12.
"""
from backend.app.aud.niif.ciclo.servicio import _periodos_planificacion
from backend.app.aud.niif.procesadores.artefacto_html import construir_config


def test_visita_preliminar_de_la_ficha_da_periodos_preliminares():
    # Tal cual lo guarda la ficha: visit="Preliminar", cutoff fecha completa, SIN tipoRevision.
    eng = {"cutoff": "2026-08-31", "visit": "Preliminar"}
    per = _periodos_planificacion(eng, {})
    assert per == {"periodoAnterior": "Diciembre 2025",
                   "periodoCorte": "Agosto 2026",
                   "periodoEri": "Agosto 2025"}
    cfg = construir_config({}, {**eng, **per}, {})
    assert cfg["mode"] == "preliminar"
    assert cfg["meses"] == 8          # mes del corte (agosto), para el prorrateo del ERI


def test_tipoRevision_preliminar_tambien_funciona():
    eng = {"cutoff": "2026-08-31"}
    per = _periodos_planificacion(eng, {"tipoRevision": "preliminar"})
    assert per["periodoCorte"] == "Agosto 2026" and per["periodoEri"] == "Agosto 2025"


def test_visita_final_compara_diciembre():
    eng = {"cutoff": "2026-12-31", "visit": "Final"}
    per = _periodos_planificacion(eng, {})
    assert per == {"periodoAnterior": "Diciembre 2025",
                   "periodoCorte": "Diciembre 2026",
                   "periodoEri": "Diciembre 2025"}
    assert construir_config({}, {**eng, **per}, {})["mode"] == "final"


def test_meses_preliminar_sigue_el_mes_del_corte():
    # Corte en junio → meses = 6 (no el default fijo 8).
    cfg = construir_config({}, {"cutoff": "2026-06-30", "visit": "Preliminar"}, {})
    assert cfg["mode"] == "preliminar" and cfg["meses"] == 6


def test_sin_eri_del_ano_anterior_activa_el_prorrateo():
    """Carpeta del ERF del año anterior VACÍA (sin archivo eri): el proceso sigue y
    el motor prorratea el estado de resultados del cierre anterior (Diciembre) ÷ 12 ×
    meses. El contrato a nivel config: hasERI=False y meses = mes del corte (variable).
    priorRaw del artefacto usa ese flag para prorratear (template, línea ~1222)."""
    for corte, mes in [("2026-07-31", 7), ("2026-08-31", 8), ("2026-11-30", 11)]:
        cfg = construir_config({}, {"cutoff": corte, "visit": "Preliminar"}, {})  # SIN 'eri'
        assert cfg["hasERI"] is False, f"{corte}: debería prorratear (no hay ERF)"
        assert cfg["meses"] == mes, f"{corte}: el prorrateo debe usar el mes del corte"
    # Con el ERF presente NO se prorratea (se usa el archivo del mismo corte).
    assert construir_config({"eri": {"b64": "x"}},
                            {"cutoff": "2026-08-31", "visit": "Preliminar"}, {})["hasERI"] is True
