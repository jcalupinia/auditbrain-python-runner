"""Pruebas del informe PDF/HTML de cierre del ICT (P2-F, REP-009)."""
import builtins

import pytest

from backend.app.ict.pdf_cierre import (
    PDFCierreNoDisponible,
    build_cierre_html,
    build_cierre_pdf,
)

CTX = {
    "session_data": {"razon_social": "PROPHAR S.A.", "ruc": "1791859596001",
                     "ejercicio_fiscal": "2025"},
    "sintesis": "Cierre sin salvedades relevantes.",
    "excepciones": {"filas": [], "resumen": {"total_excepciones": 0,
                    "monto_total": "0.00"}, "columnas": []},
    "parametros": {"materialidad": "50000.00"},
    "sello": {"version_app": "1.0", "timestamp": "2026-09-24T10:00:00Z",
              "hash_salida": "abcd1234"},
    "cuadra_a1": True, "suficiencia_estado": "Parcial",
}


def test_html_autonomo_sin_recursos_externos():
    out = build_cierre_html(CTX)
    assert out.startswith(b"<!doctype html")
    assert b"AuditConsulting" in out
    assert b"AUDIT-IA" in out
    assert b"<link" not in out
    assert b"cdn" not in out.lower()
    assert b"http://" not in out and b"https://" not in out
    # KPIs y síntesis presentes
    assert b"Cierre sin salvedades" in out
    assert "Síntesis".encode("utf-8") in out


def test_para_pdf_no_lleva_javascript():
    out = build_cierre_html(CTX, para_pdf=True)
    assert b"<script" not in out
    assert b"window.print" not in out


def test_html_interactivo_trae_guardar_como_pdf():
    out = build_cierre_html(CTX, para_pdf=False)
    assert "Guardar como PDF".encode("utf-8") in out


def test_tabla_excepciones_con_filas():
    ctx = {
        **CTX,
        "excepciones": {
            "columnas": [
                {"clave": "hash", "titulo": "Hash", "tipo": "hash"},
                {"clave": "nia", "titulo": "NIA", "tipo": "nia"},
                {"clave": "monto", "titulo": "Monto", "tipo": "monto"},
            ],
            "filas": [{"hash": "a1b2", "nia": "NIA 240", "monto": "12500.00"}],
            "resumen": {"total_excepciones": 1, "monto_total": "12500.00"},
        },
    }
    out = build_cierre_html(ctx)
    assert b"a1b2" in out
    assert b"12,500.00" in out  # formateado con miles en el HTML


def test_pdf_degradado_si_no_hay_weasyprint(monkeypatch):
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "weasyprint":
            raise ImportError("sin weasyprint")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(PDFCierreNoDisponible):
        build_cierre_pdf(CTX)
