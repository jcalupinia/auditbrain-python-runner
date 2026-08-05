"""Verificación empírica del parser ATS contra los 12 anexos reales de un
cliente (ENE25.pdf..DIC25.pdf). Los archivos NO se commitean (repo público):
se leen de AUD_OF_FIXTURES_DIR/ATS y el test hace skip si no está la env var.

Cruces de diciembre 2025 verificados a mano por el auditor (ver el spec
docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md).
Si algo no cuadra, se corrige el parser, no el test (regla suprema CLAUDE.md).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.app.aud.obligaciones_fiscales.libro.ats import parse_all_ats

pytestmark = pytest.mark.skipif(
    not os.getenv("AUD_OF_FIXTURES_DIR"),
    reason="Requiere AUD_OF_FIXTURES_DIR con los 12 ATS reales del cliente",
)

MESES_ARCHIVO = [
    "ENE25", "FEB25", "MAR25", "ABR25", "MAY25", "JUN25",
    "JUL25", "AGO25", "SEP25", "OCT25", "NOV25", "DIC25",
]


@pytest.fixture(scope="module")
def resumenes():
    carpeta = Path(os.environ["AUD_OF_FIXTURES_DIR"]) / "ATS"
    if not carpeta.exists():
        pytest.skip(f"No está {carpeta}")
    rutas = [carpeta / f"{m}.pdf" for m in MESES_ARCHIVO]
    faltantes = [str(r) for r in rutas if not r.exists()]
    if faltantes:
        pytest.skip(f"Faltan archivos: {faltantes}")
    por_periodo, errores = parse_all_ats(rutas)
    return por_periodo, errores


@pytest.fixture(scope="module")
def diciembre(resumenes):
    por_periodo, _ = resumenes
    assert "2025-12" in por_periodo, sorted(por_periodo)
    return por_periodo["2025-12"]


def test_se_parsean_los_doce_periodos_sin_errores(resumenes):
    por_periodo, errores = resumenes
    assert len(por_periodo) == 12, f"períodos encontrados: {sorted(por_periodo)}"
    assert errores == [], errores


def test_periodo_detectado_de_diciembre_es_diciembre_2025(diciembre):
    assert diciembre.periodo == "2025-12"


def test_iva_en_compras_de_diciembre(diciembre):
    assert diciembre.compras.iva == pytest.approx(1635.58, abs=0.01)


def test_ventas_gravadas_e_iva_en_ventas_de_diciembre(diciembre):
    assert diciembre.ventas.bi_gravada == pytest.approx(315439.63, abs=0.01)
    assert diciembre.ventas.iva == pytest.approx(47315.95, abs=0.01)


def test_retencion_de_iva_por_porcentaje_de_diciembre(diciembre):
    porcentajes = {f.porcentaje: f.valor_retenido for f in diciembre.retenciones_iva}
    assert porcentajes.get(30.0) == pytest.approx(9.95, abs=0.01)
    assert porcentajes.get(70.0) == pytest.approx(723.79, abs=0.01)
    assert porcentajes.get(100.0) == pytest.approx(216.40, abs=0.01)
    assert diciembre.retenciones_iva_total == pytest.approx(950.14, abs=0.01)


def test_iva_que_le_retuvieron_en_diciembre(diciembre):
    assert diciembre.iva_que_le_retuvieron == pytest.approx(4241.79, abs=0.01)


def test_ocho_codigos_de_retencion_de_renta_con_total_2388_20(diciembre):
    codigos = {f.codigo for f in diciembre.retenciones_renta}
    assert len(codigos) == 8, sorted(codigos)
    assert diciembre.retenciones_renta_valor_total == pytest.approx(2388.20, abs=0.01)
    assert sum(f.valor_retenido for f in diciembre.retenciones_renta) == pytest.approx(
        2388.20, abs=0.01
    )
