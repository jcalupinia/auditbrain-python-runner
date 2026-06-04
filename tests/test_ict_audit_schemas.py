"""Tests for backend.app.ict.audit.schemas — Pydantic models."""
from datetime import datetime
from decimal import Decimal

import pytest

from backend.app.ict.audit.schemas import (
    A1Metrics,
    AnexoFinding,
    AnexoInterpretation,
    AnexosMetrics,
    AnexoStatus,
    Status,
)


def test_status_enum_has_four_values():
    assert Status.OK.value == "ok"
    assert Status.REVISAR.value == "revisar"
    assert Status.CRITICO.value == "critico"
    assert Status.NA.value == "na"


def test_a1_metrics_minimum_valid():
    m = A1Metrics(
        activo_total=Decimal("100.00"),
        pasivo_patrimonio_total=Decimal("100.00"),
        diferencia=Decimal("0.00"),
        status_cuadre=Status.OK,
        cobertura_mapeo_pct=87.0,
        cas_mapeados=47,
        cas_total=54,
        cas_sin_contrapartida=["302", "303"],
    )
    assert m.cobertura_mapeo_pct == 87.0
    assert len(m.cas_sin_contrapartida) == 2


def test_a1_metrics_rejects_cobertura_over_100():
    with pytest.raises(ValueError):
        A1Metrics(
            activo_total=Decimal("100"),
            pasivo_patrimonio_total=Decimal("100"),
            diferencia=Decimal("0"),
            status_cuadre=Status.OK,
            cobertura_mapeo_pct=101.0,  # invalid
            cas_mapeados=47,
            cas_total=54,
            cas_sin_contrapartida=[],
        )


def test_anexo_status_construction():
    s = AnexoStatus(
        codigo="A2",
        nombre="Conciliación de Ingresos",
        status=Status.REVISAR,
        observacion_corta="Δ $1.2K",
        monto_principal=Decimal("4200000.00"),
    )
    assert s.codigo == "A2"
    assert s.monto_principal == Decimal("4200000.00")


def test_anexos_metrics_resumen_global():
    statuses = [
        AnexoStatus(codigo=f"A{i}", nombre=f"Anexo {i}", status=Status.OK,
                    observacion_corta="OK")
        for i in range(1, 10)
    ]
    metrics = AnexosMetrics(
        anexos=statuses,
        resumen_global={Status.OK: 9, Status.REVISAR: 0,
                        Status.CRITICO: 0, Status.NA: 0},
    )
    assert len(metrics.anexos) == 9
    assert metrics.resumen_global[Status.OK] == 9


def test_anexo_finding_required_fields():
    f = AnexoFinding(
        severity="critico",
        categoria="subdeclaracion_ventas",
        titulo="Subdeclaración Q4",
        descripcion_tecnica="cas 6999: $4.2M vs balance $5.4M",
        implicacion_tributaria="Riesgo glosa IVA y Renta",
        recomendacion="Conciliar facturación Q4",
        monto_disputa=Decimal("1200000.00"),
        casilleros_afectados=["6999", "6001"],
    )
    assert f.severity == "critico"
    assert f.categoria == "subdeclaracion_ventas"


def test_anexo_interpretation_full():
    f = AnexoFinding(
        severity="material",
        categoria="gasto_no_deducible",
        titulo="Gastos agasajos",
        descripcion_tecnica="$15K sin sustento",
        implicacion_tributaria="No deducible art 28 LORTI",
        recomendacion="Documentar o reclasificar",
        casilleros_afectados=["7299"],
    )
    interp = AnexoInterpretation(
        anexo_codigo="A3",
        anexo_nombre="Costos y Gastos",
        resumen_ejecutivo="Anexo con 1 finding material.",
        findings=[f],
        confianza_modelo="alta",
        requiere_revision_humana=False,
        timestamp_analisis=datetime(2026, 6, 4, 20, 50),
        modelo_usado="claude-sonnet-4-7-20260101",
        tokens_consumidos=1543,
    )
    assert len(interp.findings) == 1
    assert interp.confianza_modelo == "alta"
