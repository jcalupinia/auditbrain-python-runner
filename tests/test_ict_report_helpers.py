# tests/test_ict_report_helpers.py
from backend.app.aud.informe_cumplimiento_tributario import helpers


def test_fecha_larga_from_ddmmyyyy():
    assert helpers.fecha_larga_from_ddmmyyyy("09-04-2026") == "09 de abril de 2026"
    assert helpers.fecha_larga_from_ddmmyyyy("31-12-2025") == "31 de diciembre de 2025"


def test_fecha_larga_invalid_returns_none():
    assert helpers.fecha_larga_from_ddmmyyyy("99-99-2026") is None
    assert helpers.fecha_larga_from_ddmmyyyy("basura") is None
    assert helpers.fecha_larga_from_ddmmyyyy("32-01-2026") is None
    assert helpers.fecha_larga_from_ddmmyyyy("00-01-2026") is None


def test_normaliza_del():
    assert helpers.normaliza_del("27 de febrero del 2026") == "27 de febrero de 2026"
    assert helpers.normaliza_del("15 de marzo de 2026") == "15 de marzo de 2026"


def test_marco_phrase():
    assert "PYMES" in helpers.marco_phrase("pymes")
    assert helpers.marco_phrase("plenas") == \
        "Normas Internacionales de Información Financiera – NIIF"
    # default seguro
    assert "PYMES" in helpers.marco_phrase("desconocido")
