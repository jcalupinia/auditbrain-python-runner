import datetime as dt
from backend.app.tax.planificacion_utilidades.parsers.periodos import clasificar_periodo


def test_fecha_es_parcial_con_meses():
    p = clasificar_periodo(dt.datetime(2026, 5, 1))
    assert p == {"label": "may-26", "tipo": "parcial", "meses": 5, "anio": 2026}


def test_anio_entero_es_anual():
    assert clasificar_periodo(2025) == {"label": "2025", "tipo": "anual", "meses": 12, "anio": 2025}


def test_anio_texto_es_anual():
    assert clasificar_periodo("2024") == {"label": "2024", "tipo": "anual", "meses": 12, "anio": 2024}


def test_iso_string_es_parcial():
    assert clasificar_periodo("2025-05-01")["tipo"] == "parcial"
    assert clasificar_periodo("2025-05-01")["meses"] == 5


def test_no_periodo_devuelve_none():
    assert clasificar_periodo("Activo") is None
    assert clasificar_periodo(None) is None
    assert clasificar_periodo(123.45) is None
