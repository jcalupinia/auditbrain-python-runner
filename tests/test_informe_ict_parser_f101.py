# tests/test_ict_report_parser_f101.py
from pathlib import Path

from backend.app.aud.informe_cumplimiento_tributario.parsers import declaracion_ir

FIXTURES = Path(__file__).parent / "fixtures" / "informe_cumplimiento_tributario"


def test_parse_f101_real_axxis():
    data = declaracion_ir.parse(( FIXTURES / "f101_axxis.pdf").read_bytes())
    assert data["fecha_declaracion_ir"] == "09 de abril de 2026"
    assert data["ejercicio"] == "2025"
    assert data["errores"] == []


def test_parse_f101_garbage_pdf_degrada():
    data = declaracion_ir.parse(b"%PDF-1.4 basura no es un f101")
    assert data["fecha_declaracion_ir"] is None
    assert data["errores"]  # reporta el problema, no crashea
