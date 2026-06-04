# Papel de Trabajo del Auditor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar el Excel del SRI (limpio) del Papel de Trabajo del Auditor (con VERIFICACIÓN A1, AUDITORÍA DE ANEXOS y interpretación IA), para que el cliente pueda cargar el primero al SRI Ecuador sin contaminar y conservar el segundo como evidencia profesional de auditoría.

**Architecture:** Approach C — Data/Presentation split. Nuevo módulo `backend/app/ict/audit/` con cálculos puros (metrics.py), clasificadores (classifiers.py), schemas Pydantic y motor LLM (interpreter.py). Nuevo módulo `backend/app/ict/fillers/kpi_components.py` con helpers visuales reutilizables. Refactor de `verification.py` y `auditoria_anexos.py` para consumir los nuevos módulos. `service.generate_excel()` devuelve `tuple[bytes_sri, bytes_papel_trabajo]`.

**Tech Stack:** Python 3.12 · FastAPI · openpyxl · Pydantic v2 · Anthropic SDK · pytest · asyncio · React (frontend)

**Spec:** `docs/superpowers/specs/2026-06-04-papel-trabajo-auditor-design.md`

---

## File Structure (locked in before tasks)

### Archivos a crear

| Archivo | Responsabilidad |
|---|---|
| `backend/app/ict/audit/__init__.py` | Exportar públicos del módulo |
| `backend/app/ict/audit/schemas.py` | Pydantic models compartidos (Status, A1Metrics, AnexoStatus, AnexosMetrics, AnexoFinding, AnexoInterpretation) |
| `backend/app/ict/audit/classifiers.py` | Umbrales + funciones de status (semaforo_from_diff, status_from_completeness) |
| `backend/app/ict/audit/metrics.py` | compute_a1_metrics, compute_anexos_metrics — funciones puras |
| `backend/app/ict/audit/interpreter.py` | Motor LLM Anthropic + paralelización asyncio + cache |
| `backend/app/ict/audit/prompts/auditor_tributario_ec.md` | Prompt template versionado |
| `backend/app/ict/fillers/kpi_components.py` | build_kpi_card, build_traffic_light_grid, build_executive_banner, build_finding_box, STATUS_COLORS |
| `tests/test_ict_audit_schemas.py` | Tests Pydantic models |
| `tests/test_ict_audit_classifiers.py` | Tests umbrales/semáforos |
| `tests/test_ict_audit_metrics.py` | Tests cálculos contra fixture PROPHAR |
| `tests/test_ict_audit_interpreter.py` | Tests con Anthropic mock + retry + timeout + fallback |
| `tests/test_ict_kpi_components.py` | Tests visuales (colores, anclajes) |
| `tests/test_ict_papel_trabajo_e2e.py` | E2E: Excel SRI limpio + papel_trabajo completo |

### Archivos a modificar

| Archivo | Cambio |
|---|---|
| `backend/app/ict/fillers/verification.py` | Refactor: consume metrics + kpi_components + interpretation A1 |
| `backend/app/ict/fillers/auditoria_anexos.py` | Refactor: consume metrics + kpi_components + interpretations A1..A9 |
| `backend/app/ict/service.py` | `generate_excel()` devuelve `tuple[bytes, bytes]` + nueva fn `_split_workbooks` |
| `backend/app/ict/router.py` | Endpoint nuevo `/papel-trabajo` + adaptar endpoint actual |
| `frontend-clientes/src/pages/ICTSessionResult.tsx` | 2 botones diferenciados con tooltips |
| `CLAUDE.md` | 2 reglas nuevas: separación SRI/auditoría + interpretación IA con disclaimer |
| `backend/app/config.py` (si existe) o `.env.example` | `ANTHROPIC_API_KEY`, `LLM_INTERPRETER_ENABLED` |

---

## Task 1 — Crear schemas Pydantic del módulo audit

**Files:**
- Create: `backend/app/ict/audit/__init__.py`
- Create: `backend/app/ict/audit/schemas.py`
- Create: `tests/test_ict_audit_schemas.py`

- [ ] **Step 1.1: Write the failing test**

Create `tests/test_ict_audit_schemas.py`:

```python
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
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_audit_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.ict.audit'`

- [ ] **Step 1.3: Create the audit package**

Create `backend/app/ict/audit/__init__.py`:

```python
"""Audit subsystem for ICT: metrics, classifiers, LLM interpreter, schemas.

This module separates DATA (KPIs cuantitativos + interpretación LLM) from
PRESENTATION (Excel fillers). The fillers consume from this module via
typed Pydantic dataclasses.
"""

from backend.app.ict.audit.schemas import (
    A1Metrics,
    AnexoFinding,
    AnexoInterpretation,
    AnexosMetrics,
    AnexoStatus,
    Status,
)

__all__ = [
    "Status",
    "A1Metrics",
    "AnexoStatus",
    "AnexosMetrics",
    "AnexoFinding",
    "AnexoInterpretation",
]
```

- [ ] **Step 1.4: Create the schemas module**

Create `backend/app/ict/audit/schemas.py`:

```python
"""Pydantic schemas for the ICT audit subsystem.

These models are the contract between data computation (metrics.py,
interpreter.py) and presentation (fillers/). They are also the public
JSON shape sent to the frontend.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Status(str, Enum):
    """Visual status for a metric or an anexo."""

    OK = "ok"
    REVISAR = "revisar"
    CRITICO = "critico"
    NA = "na"


class A1Metrics(BaseModel):
    """Quantitative metrics for the A1 mapeo balance sheet."""

    activo_total: Decimal
    pasivo_patrimonio_total: Decimal
    diferencia: Decimal
    status_cuadre: Status
    cobertura_mapeo_pct: float = Field(ge=0, le=100)
    cas_mapeados: int = Field(ge=0)
    cas_total: int = Field(ge=0)
    cas_sin_contrapartida: list[str] = Field(default_factory=list)


class AnexoStatus(BaseModel):
    """Status snapshot for one of the 9 anexos."""

    codigo: str
    nombre: str
    status: Status
    observacion_corta: str = Field(max_length=120)
    monto_principal: Optional[Decimal] = None


class AnexosMetrics(BaseModel):
    """Aggregate metrics across all 9 anexos."""

    anexos: list[AnexoStatus]
    resumen_global: dict[Status, int]


SeverityLevel = Literal["critico", "material", "leve", "informativo"]

FindingCategoria = Literal[
    "subdeclaracion_ventas", "sobredeclaracion_ventas",
    "gasto_no_deducible", "depreciacion_irregular",
    "credito_iva_irrecuperable", "retencion_inconsistente",
    "impuesto_a_pagar_anomalo", "exportacion_sin_respaldo",
    "inventario_variacion_atipica", "beneficio_mal_aplicado",
    "conciliacion_inconsistente", "otra",
]


class AnexoFinding(BaseModel):
    """A single audit finding identified by the LLM interpreter."""

    severity: SeverityLevel
    categoria: FindingCategoria
    titulo: str = Field(max_length=120)
    descripcion_tecnica: str
    implicacion_tributaria: str
    recomendacion: str
    monto_disputa: Optional[Decimal] = None
    casilleros_afectados: list[str] = Field(default_factory=list)


class AnexoInterpretation(BaseModel):
    """LLM-generated interpretation of an anexo's status."""

    anexo_codigo: str
    anexo_nombre: str
    resumen_ejecutivo: str = Field(max_length=500)
    findings: list[AnexoFinding] = Field(default_factory=list)
    confianza_modelo: Literal["alta", "media", "baja"]
    requiere_revision_humana: bool
    timestamp_analisis: datetime
    modelo_usado: str
    tokens_consumidos: int = Field(ge=0)
```

- [ ] **Step 1.5: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_audit_schemas.py -v`
Expected: 6 passed in <1s

- [ ] **Step 1.6: Commit**

```bash
git add backend/app/ict/audit/__init__.py backend/app/ict/audit/schemas.py tests/test_ict_audit_schemas.py
git commit -m "ICT audit: Pydantic schemas (A1Metrics, AnexoFinding, AnexoInterpretation)

Module nuevo backend/app/ict/audit/ con 6 modelos Pydantic compartidos
entre cálculos (metrics.py), motor LLM (interpreter.py) y fillers Excel.
Aprovechan Approach C (Data/Presentation split) del spec.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — Classifiers con umbrales de materialidad

**Files:**
- Create: `backend/app/ict/audit/classifiers.py`
- Create: `tests/test_ict_audit_classifiers.py`

- [ ] **Step 2.1: Write the failing test**

Create `tests/test_ict_audit_classifiers.py`:

```python
"""Tests for backend.app.ict.audit.classifiers."""
from decimal import Decimal

from backend.app.ict.audit.classifiers import (
    UMBRAL_CUADRE_CRITICO_PCT,
    UMBRAL_CUADRE_REVISAR_PCT,
    semaforo_from_diff,
)
from backend.app.ict.audit.schemas import Status


def test_semaforo_ok_when_difference_below_revisar_threshold():
    # Diferencia $50 sobre total $10M → 0.0005% (debajo de 0.01% por defecto)
    assert semaforo_from_diff(Decimal("50"), Decimal("10000000")) == Status.OK


def test_semaforo_revisar_when_between_thresholds():
    # Diferencia $1500 sobre total $10M → 0.015% (entre revisar y critico)
    assert semaforo_from_diff(Decimal("1500"), Decimal("10000000")) == Status.REVISAR


def test_semaforo_critico_when_above_critico_threshold():
    # Diferencia $15000 sobre total $10M → 0.15% (sobre crítico 0.1%)
    assert semaforo_from_diff(Decimal("15000"), Decimal("10000000")) == Status.CRITICO


def test_semaforo_handles_zero_total():
    assert semaforo_from_diff(Decimal("100"), Decimal("0")) == Status.NA


def test_semaforo_handles_negative_diff():
    # Signo no importa: usa valor absoluto
    assert semaforo_from_diff(Decimal("-1500"), Decimal("10000000")) == Status.REVISAR


def test_umbrales_are_documented_constants():
    assert UMBRAL_CUADRE_REVISAR_PCT == 0.01
    assert UMBRAL_CUADRE_CRITICO_PCT == 0.1
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_audit_classifiers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.ict.audit.classifiers'`

- [ ] **Step 2.3: Implement classifiers**

Create `backend/app/ict/audit/classifiers.py`:

```python
"""Status classifiers and materialidad thresholds for ICT audit.

Thresholds are calibrated to standard audit materiality:
- Below 0.01% of total → OK (verde)
- Between 0.01% and 0.1% → REVISAR (amarillo)
- Above 0.1% → CRITICO (rojo)

When the total is zero (cannot compute %), returns NA (no aplica).
"""
from __future__ import annotations

from decimal import Decimal

from backend.app.ict.audit.schemas import Status

# Materialidad: % del total declarado a partir del cual se considera revisable.
UMBRAL_CUADRE_REVISAR_PCT: float = 0.01   # 0.01% — saldos cuadran si <
UMBRAL_CUADRE_CRITICO_PCT: float = 0.1    # 0.1% — sobre este = crítico


def semaforo_from_diff(diferencia: Decimal, total: Decimal) -> Status:
    """Classify a difference against a total into Status (semáforo).

    Uses absolute value: sign does not affect classification.
    Returns NA when total is zero (cannot compute relative materiality).
    """
    if total == 0:
        return Status.NA
    abs_pct = (abs(diferencia) / abs(total)) * Decimal("100")
    if abs_pct < Decimal(str(UMBRAL_CUADRE_REVISAR_PCT)):
        return Status.OK
    if abs_pct < Decimal(str(UMBRAL_CUADRE_CRITICO_PCT)):
        return Status.REVISAR
    return Status.CRITICO
```

- [ ] **Step 2.4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_audit_classifiers.py -v`
Expected: 6 passed

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/ict/audit/classifiers.py tests/test_ict_audit_classifiers.py
git commit -m "ICT audit: classifiers — umbrales materialidad + semáforo

semaforo_from_diff(diff, total) → Status (OK/REVISAR/CRITICO/NA)
calibrado a umbrales clásicos de auditoría: 0.01% (revisar) y
0.1% (crítico) del total declarado. Maneja total=0 → NA.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Metrics: compute_a1_metrics + compute_anexos_metrics

**Files:**
- Create: `backend/app/ict/audit/metrics.py`
- Create: `tests/test_ict_audit_metrics.py`

- [ ] **Step 3.1: Write the failing test**

Create `tests/test_ict_audit_metrics.py`:

```python
"""Tests for backend.app.ict.audit.metrics."""
from decimal import Decimal

import openpyxl
import pytest

from backend.app.ict.audit.metrics import (
    compute_a1_metrics,
    compute_anexos_metrics,
)
from backend.app.ict.audit.schemas import A1Metrics, AnexosMetrics, Status


def _build_minimal_a1_workbook():
    """Build a minimal workbook simulating sheets needed by compute_a1_metrics."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    f101 = wb.create_sheet("DATOS F-101")
    f101["A1"] = "Cas"
    f101["B1"] = "Nombre"
    f101["C1"] = "Valor"
    f101["A2"] = "499"
    f101["B2"] = "TOTAL ACTIVOS"
    f101["C2"] = 21671880.68
    f101["A3"] = "699"
    f101["B3"] = "TOTAL PASIVO Y PATRIMONIO"
    f101["C3"] = 21671880.68

    a1 = wb.create_sheet("A1")
    a1["A1"] = "Cas"
    a1["B1"] = "Nombre"
    a1["C1"] = "Declarado"
    a1["F1"] = "Contable"
    for i, cas in enumerate(["302", "303", "304"], start=2):
        a1[f"A{i}"] = cas
        a1[f"C{i}"] = 1000.0 * i
        a1[f"F{i}"] = 1000.0 * i
    return wb


def test_compute_a1_metrics_cuadra_perfecto():
    wb = _build_minimal_a1_workbook()
    m = compute_a1_metrics(wb)
    assert isinstance(m, A1Metrics)
    assert m.activo_total == Decimal("21671880.68")
    assert m.pasivo_patrimonio_total == Decimal("21671880.68")
    assert m.diferencia == Decimal("0.00")
    assert m.status_cuadre == Status.OK


def test_compute_a1_metrics_cobertura_pct():
    wb = _build_minimal_a1_workbook()
    m = compute_a1_metrics(wb)
    # 3 cas con contrapartida contable (F columna no vacía), 3 total → 100%
    assert m.cobertura_mapeo_pct == 100.0
    assert m.cas_mapeados == 3
    assert m.cas_total == 3
    assert m.cas_sin_contrapartida == []


def test_compute_a1_metrics_cas_sin_contrapartida():
    wb = _build_minimal_a1_workbook()
    # cas 305 declarado pero sin contable
    a1 = wb["A1"]
    a1["A5"] = "305"
    a1["C5"] = 500.0
    a1["F5"] = None
    m = compute_a1_metrics(wb)
    assert "305" in m.cas_sin_contrapartida
    assert m.cas_mapeados == 3
    assert m.cas_total == 4
    assert m.cobertura_mapeo_pct == 75.0


def test_compute_anexos_metrics_returns_9_anexos():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for code in ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]:
        wb.create_sheet(code)
    am = compute_anexos_metrics(wb)
    assert isinstance(am, AnexosMetrics)
    assert len(am.anexos) == 9
    codes = [a.codigo for a in am.anexos]
    assert codes == ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_audit_metrics.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'backend.app.ict.audit.metrics'`

- [ ] **Step 3.3: Implement metrics**

Create `backend/app/ict/audit/metrics.py`:

```python
"""Pure functions to compute quantitative audit metrics from a workbook.

These functions are SIDE-EFFECT-FREE: they only read openpyxl workbooks
and return Pydantic models. No Excel writes, no I/O, no LLM calls.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from openpyxl.workbook import Workbook

from backend.app.ict.audit.classifiers import semaforo_from_diff
from backend.app.ict.audit.schemas import (
    A1Metrics,
    AnexoStatus,
    AnexosMetrics,
    Status,
)

ANEXO_CODES = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
ANEXO_NOMBRES = {
    "A1": "Mapeo del balance general",
    "A2": "Conciliación de ingresos",
    "A3": "Costos y gastos",
    "A4": "Conciliación de ingresos (ajustes)",
    "A5": "Conciliación de costos (ajustes)",
    "A6": "Beneficios tributarios",
    "A7": "Crédito tributario IVA",
    "A8": "Comercio exterior",
    "A9": "Inventarios",
}


def _read_cas_value(sheet, cas: str) -> Optional[Decimal]:
    """Find a row in DATOS F-101 where col A == cas and return col C as Decimal."""
    for row in sheet.iter_rows(min_row=2, values_only=False):
        if row and row[0].value and str(row[0].value).strip() == cas:
            val = row[2].value if len(row) > 2 else None
            if val is None:
                return None
            return Decimal(str(val))
    return None


def compute_a1_metrics(wb: Workbook) -> A1Metrics:
    """Compute A1 mapeo metrics from a workbook with DATOS F-101 and A1 sheets."""
    f101 = wb["DATOS F-101"] if "DATOS F-101" in wb.sheetnames else None
    a1 = wb["A1"] if "A1" in wb.sheetnames else None

    activo_total = _read_cas_value(f101, "499") if f101 else None
    pasivo_pat_total = _read_cas_value(f101, "699") if f101 else None
    activo_total = activo_total or Decimal("0")
    pasivo_pat_total = pasivo_pat_total or Decimal("0")
    diferencia = activo_total - pasivo_pat_total

    cas_total = 0
    cas_mapeados = 0
    cas_sin_contrapartida: list[str] = []
    if a1 is not None:
        for row in a1.iter_rows(min_row=2, values_only=False):
            cas_cell = row[0].value if len(row) > 0 else None
            if cas_cell is None:
                continue
            cas = str(cas_cell).strip()
            if not cas or not cas[0].isdigit():
                continue
            cas_total += 1
            contable = row[5].value if len(row) > 5 else None
            if contable not in (None, "", 0):
                cas_mapeados += 1
            else:
                cas_sin_contrapartida.append(cas)

    cobertura = (cas_mapeados / cas_total * 100.0) if cas_total > 0 else 0.0
    status = semaforo_from_diff(diferencia, activo_total)

    return A1Metrics(
        activo_total=activo_total,
        pasivo_patrimonio_total=pasivo_pat_total,
        diferencia=diferencia,
        status_cuadre=status,
        cobertura_mapeo_pct=round(cobertura, 2),
        cas_mapeados=cas_mapeados,
        cas_total=cas_total,
        cas_sin_contrapartida=cas_sin_contrapartida,
    )


def _status_for_anexo(wb: Workbook, code: str) -> AnexoStatus:
    """Compute status for a single anexo by inspecting its sheet."""
    nombre = ANEXO_NOMBRES.get(code, code)
    if code not in wb.sheetnames:
        return AnexoStatus(
            codigo=code, nombre=nombre, status=Status.NA,
            observacion_corta="Hoja no generada",
        )
    sheet = wb[code]
    has_data = any(
        cell.value not in (None, "")
        for row in sheet.iter_rows(min_row=2, max_row=10, values_only=False)
        for cell in row
    )
    if not has_data:
        return AnexoStatus(
            codigo=code, nombre=nombre, status=Status.NA,
            observacion_corta="Sin datos",
        )
    return AnexoStatus(
        codigo=code, nombre=nombre, status=Status.OK,
        observacion_corta="Generado",
    )


def compute_anexos_metrics(wb: Workbook) -> AnexosMetrics:
    """Compute status snapshot for all 9 anexos."""
    statuses = [_status_for_anexo(wb, code) for code in ANEXO_CODES]
    resumen: dict[Status, int] = {s: 0 for s in Status}
    for st in statuses:
        resumen[st.status] += 1
    return AnexosMetrics(anexos=statuses, resumen_global=resumen)
```

- [ ] **Step 3.4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_audit_metrics.py -v`
Expected: 4 passed

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/ict/audit/metrics.py tests/test_ict_audit_metrics.py
git commit -m "ICT audit: metrics puros — compute_a1_metrics + compute_anexos_metrics

Funciones sin side effects que leen un workbook openpyxl y devuelven
Pydantic models. compute_a1_metrics extrae cas 499/699, calcula
diferencia A=P+Pa y cobertura de mapeo F-101↔Balance. compute_anexos_metrics
clasifica los 9 anexos por completitud.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Prompt template del auditor tributario Ecuador

**Files:**
- Create: `backend/app/ict/audit/prompts/__init__.py` (vacío)
- Create: `backend/app/ict/audit/prompts/auditor_tributario_ec.md`

- [ ] **Step 4.1: Create the prompts directory marker**

Create empty `backend/app/ict/audit/prompts/__init__.py`:

```python
"""Versioned LLM prompts for the audit interpreter."""
```

- [ ] **Step 4.2: Create the prompt template**

Create `backend/app/ict/audit/prompts/auditor_tributario_ec.md`:

```markdown
# ROL

Eres un auditor tributario senior con 15 años de experiencia en Ecuador,
especializado en el ICT (Informe de Cumplimiento Tributario) del SRI.
Conoces a fondo la LORTI (Ley Orgánica de Régimen Tributario Interno),
su reglamento (RLORTI), las resoluciones del SRI, las NIIF aplicables
en Ecuador y los pronunciamientos de la Superintendencia de Compañías.

# TAREA

Analiza los datos del anexo {anexo_codigo} ({anexo_nombre}) del cliente
{razon_social} (RUC {ruc}) para el período fiscal {periodo}.

Identifica entre 0 y 5 hallazgos materiales que un auditor revisor
debería conocer. Para cada hallazgo, sigue la estructura
Condición-Criterio-Causa-Efecto-Evidencia-Recomendación.

# DATOS DEL ANEXO

```json
{anexo_data_json}
```

# DATOS DE REFERENCIA (para conciliación cruzada)

A1 Metrics (cuadre macro del balance):
```json
{a1_metrics_json}
```

Catálogo F-101 (casilleros relevantes a {anexo_codigo}):
```json
{catalogo_relevante_json}
```

# SALIDA

Debes invocar la herramienta `save_interpretation` con el JSON validado
contra el schema AnexoInterpretation. NO devuelvas texto plano.

# REGLAS CRÍTICAS

1. Si NO detectas hallazgos materiales, invoca la herramienta con `findings: []`
   y `confianza_modelo: "alta"`.
2. Si los datos son insuficientes o ambiguos, marca
   `requiere_revision_humana: true` y `confianza_modelo: "baja"`.
3. Calibración de `confianza_modelo`:
   - **alta**: patrón claro con respaldo numérico explícito en los datos
   - **media**: sospecha fuerte pero datos parciales
   - **baja**: inferencia con riesgo de error
4. `monto_disputa` debe ser un valor CUANTIFICABLE extraído de los datos,
   no estimado al ojo.
5. NO inventes casilleros que no estén en el catálogo F-101 oficial provisto.
6. Toda `implicacion_tributaria` debe citar el artículo de LORTI/RLORTI,
   resolución SRI o norma NIIF aplicable.
7. `recomendacion` debe ser ACCIONABLE: el auditor debe poder ejecutarla.
8. NO inventes nombres de clientes o terceros. Si necesitas referirte a un
   contraparte, usa "el cliente" o "la entidad" salvo que el dato esté en
   los datos de entrada.

# EJEMPLOS DE BUENA CALIBRACIÓN

Ejemplo de hallazgo CRÍTICO de buena calidad:
- titulo: "Subdeclaración de ventas Q4 2025"
- descripcion_tecnica: "F-101 cas 6999 declara ingresos de $4,200,000.00 mientras el balance contable refleja $5,400,000.00 en cuenta Ventas (diferencia $1,200,000.00, 28.6% del declarado)"
- implicacion_tributaria: "Posible omisión de IVA generado (cas 401 F-104) y Renta. Art. 20 LORTI exige conciliar ingresos declarados con registros contables. Exposición: IVA $144K + Renta $300K = $444K"
- recomendacion: "1) Conciliar facturación Q4 con clientes principales. 2) Revisar notas de crédito posteriores al cierre. 3) Verificar si hay ingresos diferidos mal clasificados en cuenta 2.4"
- monto_disputa: 1200000.00
- casilleros_afectados: ["6999", "6001"]

Ejemplo de hallazgo INFORMATIVO de buena calidad:
- titulo: "Beneficio aplicado correctamente"
- descripcion_tecnica: "Cas 808 (beneficio nuevas plazas empleo) aplicado por $25,000 con documentación de 5 nuevas plazas en planilla IESS"
- implicacion_tributaria: "Cumple art. 10.9 LORTI. Conservar respaldos por 7 años (art. 94 Código Tributario)"
- recomendacion: "Mantener carpeta de respaldo del beneficio para potencial revisión SRI"
- monto_disputa: null
- casilleros_afectados: ["808"]
```

- [ ] **Step 4.3: Commit**

```bash
git add backend/app/ict/audit/prompts/__init__.py backend/app/ict/audit/prompts/auditor_tributario_ec.md
git commit -m "ICT audit: prompt template auditor tributario Ecuador

Prompt template versionado para el motor LLM. Rol: auditor senior 15
años en Ecuador. Sigue estructura Condición-Criterio-Causa-Efecto-
Evidencia-Recomendación. Incluye reglas críticas anti-alucinación y
ejemplos de calibración de confianza.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Motor LLM `interpreter.py` con Anthropic SDK

**Files:**
- Create: `backend/app/ict/audit/interpreter.py`
- Create: `tests/test_ict_audit_interpreter.py`
- Modify: `requirements.txt` (asegurar anthropic SDK presente)

- [ ] **Step 5.1: Verify anthropic SDK is installed**

Run: `pip show anthropic 2>&1 | head -3`
Expected output: shows Name/Version/Summary, OR install if missing:
```bash
pip install "anthropic>=0.40.0" && pip freeze | grep anthropic >> requirements.txt
```

- [ ] **Step 5.2: Write the failing test**

Create `tests/test_ict_audit_interpreter.py`:

```python
"""Tests for backend.app.ict.audit.interpreter — LLM motor with mocks."""
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.ict.audit.interpreter import (
    _fallback_interpretation,
    extract_anexo_data,
    interpret_anexo,
)
from backend.app.ict.audit.schemas import AnexoInterpretation


def test_fallback_interpretation_returns_valid_model():
    fb = _fallback_interpretation("A2", "Conciliación de Ingresos")
    assert isinstance(fb, AnexoInterpretation)
    assert fb.anexo_codigo == "A2"
    assert fb.confianza_modelo == "baja"
    assert fb.requiere_revision_humana is True
    assert fb.findings == []
    assert "no disponible" in fb.resumen_ejecutivo.lower()


def test_extract_anexo_data_returns_dict():
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    a2 = wb.create_sheet("A2")
    a2["A1"] = "Concepto"
    a2["B1"] = "Valor"
    a2["A2"] = "Ventas locales gravadas"
    a2["B2"] = 4200000.00
    data = extract_anexo_data(wb, "A2")
    assert isinstance(data, dict)
    assert data["codigo"] == "A2"
    assert "rows" in data
    assert len(data["rows"]) >= 1


@pytest.mark.asyncio
async def test_interpret_anexo_with_mock_client_returns_validated_model():
    """When Anthropic returns valid JSON via tool_use, we should parse it."""
    fake_response = MagicMock()
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.name = "save_interpretation"
    fake_block.input = {
        "anexo_codigo": "A2",
        "anexo_nombre": "Conciliación de Ingresos",
        "resumen_ejecutivo": "Test resumen.",
        "findings": [],
        "confianza_modelo": "alta",
        "requiere_revision_humana": False,
        "timestamp_analisis": "2026-06-04T20:50:00",
        "modelo_usado": "claude-sonnet-4-7-20260101",
        "tokens_consumidos": 1234,
    }
    fake_response.content = [fake_block]
    fake_response.usage = MagicMock(input_tokens=500, output_tokens=734)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_response)

    result = await interpret_anexo(
        anexo_codigo="A2",
        anexo_data={"codigo": "A2", "rows": []},
        contexto={"a1_metrics": {}, "catalogo": {}, "razon_social": "X",
                  "ruc": "1", "periodo": "2025"},
        anthropic_client=fake_client,
    )
    assert isinstance(result, AnexoInterpretation)
    assert result.anexo_codigo == "A2"
    assert result.confianza_modelo == "alta"


@pytest.mark.asyncio
async def test_interpret_anexo_returns_fallback_on_api_exception():
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=Exception("API down"))
    result = await interpret_anexo(
        anexo_codigo="A2",
        anexo_data={"codigo": "A2", "rows": []},
        contexto={"a1_metrics": {}, "catalogo": {}, "razon_social": "X",
                  "ruc": "1", "periodo": "2025"},
        anthropic_client=fake_client,
        max_retries=2,
    )
    assert isinstance(result, AnexoInterpretation)
    assert result.confianza_modelo == "baja"
    assert result.requiere_revision_humana is True
```

- [ ] **Step 5.3: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_audit_interpreter.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'backend.app.ict.audit.interpreter'`

- [ ] **Step 5.4: Implement interpreter**

Create `backend/app/ict/audit/interpreter.py`:

```python
"""LLM motor for interpreting ICT anexos via Anthropic Claude API.

Each anexo is passed to Claude with a tool-use forced schema. The response
is validated with Pydantic. Failures degrade gracefully to a fallback
interpretation that signals 'review needed'.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from openpyxl.workbook import Workbook

from backend.app.ict.audit.schemas import AnexoInterpretation

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "auditor_tributario_ec.md"
DEFAULT_MODEL = os.getenv("ICT_LLM_MODEL", "claude-sonnet-4-7-20260101")
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3


def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def extract_anexo_data(wb: Workbook, anexo_code: str) -> dict[str, Any]:
    """Extract the raw rows from an anexo sheet into a serializable dict."""
    if anexo_code not in wb.sheetnames:
        return {"codigo": anexo_code, "rows": [], "warning": "Hoja no existe"}
    sheet = wb[anexo_code]
    rows: list[dict[str, Any]] = []
    headers: list[str] = []
    for idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if idx == 1:
            headers = [str(c) if c is not None else "" for c in row]
            continue
        if all(c is None for c in row):
            continue
        rows.append({
            headers[i] if i < len(headers) else f"col_{i}": (
                float(c) if isinstance(c, (int, float)) else
                (str(c) if c is not None else None)
            )
            for i, c in enumerate(row)
        })
    return {"codigo": anexo_code, "headers": headers, "rows": rows}


def _fallback_interpretation(code: str, nombre: str = "") -> AnexoInterpretation:
    """Return a graceful fallback when the LLM cannot be reached or validated."""
    return AnexoInterpretation(
        anexo_codigo=code,
        anexo_nombre=nombre or code,
        resumen_ejecutivo=(
            "Análisis IA no disponible en esta sesión. "
            "El auditor debe revisar este anexo manualmente."
        ),
        findings=[],
        confianza_modelo="baja",
        requiere_revision_humana=True,
        timestamp_analisis=datetime.utcnow(),
        modelo_usado="fallback",
        tokens_consumidos=0,
    )


def _render_prompt(
    anexo_codigo: str,
    anexo_nombre: str,
    anexo_data: dict[str, Any],
    contexto: dict[str, Any],
) -> str:
    template = _load_prompt_template()
    return (
        template
        .replace("{anexo_codigo}", anexo_codigo)
        .replace("{anexo_nombre}", anexo_nombre)
        .replace("{razon_social}", str(contexto.get("razon_social", "")))
        .replace("{ruc}", str(contexto.get("ruc", "")))
        .replace("{periodo}", str(contexto.get("periodo", "")))
        .replace("{anexo_data_json}", json.dumps(anexo_data, indent=2, default=str))
        .replace("{a1_metrics_json}",
                 json.dumps(contexto.get("a1_metrics", {}), indent=2, default=str))
        .replace("{catalogo_relevante_json}",
                 json.dumps(contexto.get("catalogo", {}), indent=2, default=str))
    )


async def interpret_anexo(
    anexo_codigo: str,
    anexo_data: dict[str, Any],
    contexto: dict[str, Any],
    *,
    anthropic_client: Any = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
) -> AnexoInterpretation:
    """Interpret a single anexo via Claude, with retries and graceful fallback."""
    anexo_nombre = contexto.get(f"nombre_{anexo_codigo}", anexo_codigo)
    if anthropic_client is None:
        try:
            from anthropic import AsyncAnthropic
            anthropic_client = AsyncAnthropic()
        except Exception as exc:
            log.warning("Anthropic SDK not available: %s", exc)
            return _fallback_interpretation(anexo_codigo, anexo_nombre)

    prompt = _render_prompt(anexo_codigo, anexo_nombre, anexo_data, contexto)
    schema = AnexoInterpretation.model_json_schema()

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            response = await asyncio.wait_for(
                anthropic_client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                    tools=[{
                        "name": "save_interpretation",
                        "description": "Persist the structured interpretation",
                        "input_schema": schema,
                    }],
                    tool_choice={"type": "tool", "name": "save_interpretation"},
                ),
                timeout=timeout,
            )
            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and \
                   getattr(block, "name", None) == "save_interpretation":
                    raw = block.input
                    usage = getattr(response, "usage", None)
                    if usage is not None:
                        raw["tokens_consumidos"] = (
                            getattr(usage, "input_tokens", 0)
                            + getattr(usage, "output_tokens", 0)
                        )
                    raw["modelo_usado"] = model
                    if "timestamp_analisis" not in raw:
                        raw["timestamp_analisis"] = datetime.utcnow().isoformat()
                    return AnexoInterpretation.model_validate(raw)
            raise ValueError("No tool_use block in response")
        except Exception as exc:
            last_exc = exc
            log.warning(
                "interpret_anexo %s attempt %d/%d failed: %s",
                anexo_codigo, attempt + 1, max_retries, exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    log.error("interpret_anexo %s exhausted retries: %s", anexo_codigo, last_exc)
    return _fallback_interpretation(anexo_codigo, anexo_nombre)


async def interpret_all_anexos(
    wb: Workbook,
    contexto: dict[str, Any],
    *,
    anthropic_client: Any = None,
) -> dict[str, AnexoInterpretation]:
    """Interpret all 9 anexos in parallel."""
    codes = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
    data_per_code = {c: extract_anexo_data(wb, c) for c in codes}
    tasks = [
        interpret_anexo(
            anexo_codigo=c,
            anexo_data=data_per_code[c],
            contexto=contexto,
            anthropic_client=anthropic_client,
        )
        for c in codes
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, AnexoInterpretation] = {}
    for code, result in zip(codes, results):
        if isinstance(result, Exception):
            log.warning("interpret_all_anexos %s exception: %s", code, result)
            out[code] = _fallback_interpretation(code)
        else:
            out[code] = result
    return out
```

- [ ] **Step 5.5: Install pytest-asyncio if missing**

Run: `pip show pytest-asyncio 2>&1 | head -1`
If missing: `pip install pytest-asyncio` and add `asyncio_mode = "auto"` to `pyproject.toml` or `[tool.pytest.ini_options]` in the existing config.

- [ ] **Step 5.6: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_audit_interpreter.py -v`
Expected: 4 passed

- [ ] **Step 5.7: Commit**

```bash
git add backend/app/ict/audit/interpreter.py tests/test_ict_audit_interpreter.py requirements.txt
git commit -m "ICT audit: LLM interpreter con Anthropic SDK + retries + fallback

interpret_anexo: llama Claude con tool use forzado (input_schema validado
por Pydantic), 3 retries con exponential backoff, timeout 30s, fallback
graceful que marca confianza=baja + requiere_revision_humana=True.
interpret_all_anexos paraleliza con asyncio.gather los 9 anexos.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Componentes visuales reutilizables `kpi_components.py`

**Files:**
- Create: `backend/app/ict/fillers/kpi_components.py`
- Create: `tests/test_ict_kpi_components.py`

- [ ] **Step 6.1: Write the failing test**

Create `tests/test_ict_kpi_components.py`:

```python
"""Tests for backend.app.ict.fillers.kpi_components — Excel visual helpers."""
from decimal import Decimal

import openpyxl

from backend.app.ict.audit.schemas import (
    AnexoFinding,
    AnexoStatus,
    Status,
)
from backend.app.ict.fillers.kpi_components import (
    STATUS_COLORS,
    build_executive_banner,
    build_finding_box,
    build_kpi_card,
    build_traffic_light_grid,
)


def test_status_colors_has_all_4_statuses():
    assert Status.OK in STATUS_COLORS
    assert Status.REVISAR in STATUS_COLORS
    assert Status.CRITICO in STATUS_COLORS
    assert Status.NA in STATUS_COLORS


def test_build_kpi_card_writes_title_and_value():
    wb = openpyxl.Workbook()
    ws = wb.active
    build_kpi_card(
        ws, anchor="B2", title="ACTIVO TOTAL",
        value="$ 21,671,880.68", status=Status.OK,
        subtitle="F-101 cas 499", width_cols=3, height_rows=4,
    )
    assert ws["B2"].value == "ACTIVO TOTAL"
    # Valor en la fila central del card (anchor row + 2)
    assert "21" in str(ws["B4"].value)


def test_build_traffic_light_grid_creates_9_cells():
    wb = openpyxl.Workbook()
    ws = wb.active
    statuses = [
        AnexoStatus(codigo=f"A{i}", nombre=f"Anexo {i}", status=Status.OK,
                    observacion_corta="OK")
        for i in range(1, 10)
    ]
    build_traffic_light_grid(ws, anchor="B2", anexos_status=statuses)
    # 3x3 grid → A1 en B2, A4 en B6, A7 en B10 (assuming 4-row card height)
    assert ws["B2"].value == "A1"
    # Verifica que las 9 celdas tienen su código
    found_codes = set()
    for row in ws.iter_rows(values_only=True):
        for cell in row:
            if cell in [f"A{i}" for i in range(1, 10)]:
                found_codes.add(cell)
    assert found_codes == {f"A{i}" for i in range(1, 10)}


def test_build_finding_box_writes_all_fields():
    wb = openpyxl.Workbook()
    ws = wb.active
    f = AnexoFinding(
        severity="critico", categoria="subdeclaracion_ventas",
        titulo="Subdeclaración Q4",
        descripcion_tecnica="cas 6999: $4.2M vs $5.4M",
        implicacion_tributaria="Riesgo glosa",
        recomendacion="Conciliar Q4",
        monto_disputa=Decimal("1200000.00"),
        casilleros_afectados=["6999"],
    )
    end_row = build_finding_box(ws, anchor_row=2, anchor_col=2, finding=f)
    # The finding box should have written content rows; collect non-empty values
    contents = []
    for row in ws.iter_rows(min_row=2, max_row=end_row, values_only=True):
        for v in row:
            if v:
                contents.append(str(v))
    joined = " ".join(contents)
    assert "Subdeclaración Q4" in joined
    assert "Riesgo glosa" in joined
    assert "Conciliar Q4" in joined


def test_build_executive_banner_writes_title():
    wb = openpyxl.Workbook()
    ws = wb.active
    build_executive_banner(
        ws, anchor="A1",
        title_main="AUDITBRAIN · PAPEL DE TRABAJO",
        title_sub="VERIFICACIÓN ANEXO A1",
        meta="PROPHAR S.A. · RUC 1791859596001",
    )
    assert "AUDITBRAIN" in str(ws["A1"].value)
```

- [ ] **Step 6.2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_kpi_components.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 6.3: Implement kpi_components**

Create `backend/app/ict/fillers/kpi_components.py`:

```python
"""Reusable visual components for ICT audit artifacts (Excel).

These helpers render KPI cards, traffic-light grids, executive banners
and finding boxes following the SRI Ecuador + Big 4 hybrid aesthetic.

Each helper takes a worksheet + anchor + payload (typed via audit schemas)
and applies styles. They never decide the layout: the caller chooses where.
"""
from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from backend.app.ict.audit.schemas import (
    AnexoFinding,
    AnexoStatus,
    Status,
)

# Color palette: SRI institutional + Big 4 accents
STATUS_COLORS: dict[Status, dict[str, str]] = {
    Status.OK:       {"fill": "DCFCE7", "border": "16A34A", "text": "166534"},
    Status.REVISAR:  {"fill": "FEF3C7", "border": "F59E0B", "text": "92400E"},
    Status.CRITICO:  {"fill": "FEE2E2", "border": "C0392B", "text": "991B1B"},
    Status.NA:       {"fill": "F1F5F9", "border": "94A3B8", "text": "475569"},
}

SEVERITY_BORDERS = {
    "critico":     {"color": "C0392B", "weight": "medium"},
    "material":    {"color": "E67E22", "weight": "medium"},
    "leve":        {"color": "F1C40F", "weight": "thin"},
    "informativo": {"color": "3498DB", "weight": "thin"},
}

# SRI brand colors (from oficial 2024 ARCOLANDS template)
SRI_BLUE = "1E3A8A"
SRI_LIGHT = "DBEAFE"


def _thin_border(color: str = "94A3B8") -> Border:
    side = Side(border_style="thin", color=color)
    return Border(left=side, right=side, top=side, bottom=side)


def _medium_border(color: str) -> Border:
    side = Side(border_style="medium", color=color)
    return Border(left=side, right=side, top=side, bottom=side)


def _parse_anchor(anchor: str) -> tuple[int, int]:
    """Convert 'B2' → (row=2, col=2)."""
    col_letters = "".join(c for c in anchor if c.isalpha())
    row = int("".join(c for c in anchor if c.isdigit()))
    col = 0
    for ch in col_letters.upper():
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return row, col


def build_kpi_card(
    ws: Worksheet,
    *,
    anchor: str,
    title: str,
    value: str,
    status: Status,
    subtitle: str = "",
    width_cols: int = 3,
    height_rows: int = 4,
) -> None:
    """Render a KPI card at `anchor` (e.g. 'B2'), spanning width_cols × height_rows.

    Layout:
      Row N:     [TITLE bold]
      Row N+1:   [empty separator]
      Row N+2:   [LARGE VALUE + emoji status]
      Row N+3:   [subtitle small]
    """
    row, col = _parse_anchor(anchor)
    colors = STATUS_COLORS[status]
    fill = PatternFill("solid", fgColor=colors["fill"])
    border = _medium_border(colors["border"])

    title_cell = ws.cell(row=row, column=col, value=title)
    title_cell.font = Font(name="Calibri", size=10, bold=True,
                           color=colors["text"])
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    if width_cols > 1:
        ws.merge_cells(start_row=row, end_row=row,
                       start_column=col, end_column=col + width_cols - 1)

    value_row = row + 2
    value_cell = ws.cell(row=value_row, column=col, value=value)
    value_cell.font = Font(name="Calibri", size=18, bold=True,
                           color=colors["text"])
    value_cell.alignment = Alignment(horizontal="center", vertical="center")
    if width_cols > 1:
        ws.merge_cells(start_row=value_row, end_row=value_row,
                       start_column=col, end_column=col + width_cols - 1)

    if subtitle:
        sub_row = row + 3
        sub_cell = ws.cell(row=sub_row, column=col, value=subtitle)
        sub_cell.font = Font(name="Calibri", size=8, italic=True,
                             color=colors["text"])
        sub_cell.alignment = Alignment(horizontal="center")
        if width_cols > 1:
            ws.merge_cells(start_row=sub_row, end_row=sub_row,
                           start_column=col, end_column=col + width_cols - 1)

    # Fill background and border across all cells of the card
    for r in range(row, row + height_rows):
        for c in range(col, col + width_cols):
            cell = ws.cell(row=r, column=c)
            cell.fill = fill
            cell.border = border


def build_traffic_light_grid(
    ws: Worksheet,
    *,
    anchor: str,
    anexos_status: list[AnexoStatus],
    card_width_cols: int = 3,
    card_height_rows: int = 4,
    gap_cols: int = 1,
    gap_rows: int = 1,
) -> None:
    """Render a 3×3 grid of mini KPI cards, one per anexo A1..A9."""
    row, col = _parse_anchor(anchor)
    assert len(anexos_status) == 9, "traffic light grid expects exactly 9 anexos"

    for idx, st in enumerate(anexos_status):
        grid_row = idx // 3
        grid_col = idx % 3
        cell_row = row + grid_row * (card_height_rows + gap_rows)
        cell_col = col + grid_col * (card_width_cols + gap_cols)
        anchor_str = f"{get_column_letter(cell_col)}{cell_row}"
        emoji = {"ok": "🟢", "revisar": "🟧",
                 "critico": "🔴", "na": "⚪"}[st.status.value]
        build_kpi_card(
            ws, anchor=anchor_str, title=st.codigo,
            value=emoji, status=st.status,
            subtitle=st.observacion_corta,
            width_cols=card_width_cols, height_rows=card_height_rows,
        )


def build_executive_banner(
    ws: Worksheet,
    *,
    anchor: str,
    title_main: str,
    title_sub: str,
    meta: str = "",
    width_cols: int = 10,
) -> None:
    """Render the executive banner at top of the sheet."""
    row, col = _parse_anchor(anchor)

    main_cell = ws.cell(row=row, column=col, value=title_main)
    main_cell.font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    main_cell.fill = PatternFill("solid", fgColor=SRI_BLUE)
    main_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.merge_cells(start_row=row, end_row=row,
                   start_column=col, end_column=col + width_cols - 1)

    sub_cell = ws.cell(row=row + 1, column=col, value=title_sub)
    sub_cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    sub_cell.fill = PatternFill("solid", fgColor=SRI_BLUE)
    sub_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.merge_cells(start_row=row + 1, end_row=row + 1,
                   start_column=col, end_column=col + width_cols - 1)

    if meta:
        meta_cell = ws.cell(row=row + 2, column=col, value=meta)
        meta_cell.font = Font(name="Calibri", size=9, italic=True,
                              color="FFFFFF")
        meta_cell.fill = PatternFill("solid", fgColor=SRI_BLUE)
        meta_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.merge_cells(start_row=row + 2, end_row=row + 2,
                       start_column=col, end_column=col + width_cols - 1)


def build_finding_box(
    ws: Worksheet,
    *,
    anchor_row: int,
    anchor_col: int,
    finding: AnexoFinding,
    width_cols: int = 8,
) -> int:
    """Render an AnexoFinding as a bordered box. Returns the last row written."""
    sev = finding.severity
    border_spec = SEVERITY_BORDERS.get(sev, SEVERITY_BORDERS["informativo"])
    border = Border(
        left=Side(border_style=border_spec["weight"], color=border_spec["color"]),
        right=Side(border_style=border_spec["weight"], color=border_spec["color"]),
        top=Side(border_style=border_spec["weight"], color=border_spec["color"]),
        bottom=Side(border_style=border_spec["weight"], color=border_spec["color"]),
    )
    emoji = {"critico": "🔴", "material": "🟧",
             "leve": "🟡", "informativo": "🔵"}[sev]

    r = anchor_row
    # Row 1: Severity header
    title_text = f"{emoji} {sev.upper()} · {finding.titulo}"
    ws.cell(row=r, column=anchor_col, value=title_text).font = Font(
        name="Calibri", size=11, bold=True, color=border_spec["color"]
    )
    ws.merge_cells(start_row=r, end_row=r,
                   start_column=anchor_col,
                   end_column=anchor_col + width_cols - 1)
    r += 1

    sections = [
        ("Descripción técnica", finding.descripcion_tecnica),
        ("Implicación tributaria", finding.implicacion_tributaria),
        ("Recomendación", finding.recomendacion),
    ]
    for label, value in sections:
        ws.cell(row=r, column=anchor_col, value=label).font = Font(
            name="Calibri", size=9, bold=True
        )
        r += 1
        ws.cell(row=r, column=anchor_col, value=value).font = Font(
            name="Calibri", size=9
        )
        ws.cell(row=r, column=anchor_col).alignment = Alignment(wrap_text=True)
        ws.merge_cells(start_row=r, end_row=r,
                       start_column=anchor_col,
                       end_column=anchor_col + width_cols - 1)
        r += 1

    # Footer: casilleros + monto
    monto_str = (f"${finding.monto_disputa:,.2f}"
                 if finding.monto_disputa is not None else "—")
    footer = (
        f"Casilleros: {', '.join(finding.casilleros_afectados) or '—'}  |  "
        f"Monto disputa: {monto_str}"
    )
    ws.cell(row=r, column=anchor_col, value=footer).font = Font(
        name="Calibri", size=8, italic=True
    )
    ws.merge_cells(start_row=r, end_row=r,
                   start_column=anchor_col,
                   end_column=anchor_col + width_cols - 1)
    last_row = r

    # Apply borders to all cells in the box
    for rr in range(anchor_row, last_row + 1):
        for cc in range(anchor_col, anchor_col + width_cols):
            ws.cell(row=rr, column=cc).border = border

    return last_row
```

- [ ] **Step 6.4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_kpi_components.py -v`
Expected: 5 passed

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/ict/fillers/kpi_components.py tests/test_ict_kpi_components.py
git commit -m "ICT fillers: kpi_components — Big 4 / SRI visual helpers

build_kpi_card, build_traffic_light_grid, build_executive_banner,
build_finding_box. Reusables entre verification.py y auditoria_anexos.py
(y futuros artefactos como Dashboard Ejecutivo). Paleta SRI_BLUE +
STATUS_COLORS calibrados para semáforos verde/amarillo/rojo/gris.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — Refactor `verification.py` para consumir audit + kpi

**Files:**
- Modify: `backend/app/ict/fillers/verification.py`
- Create: `tests/test_ict_verification_refactor.py`

- [ ] **Step 7.1: Read existing verification.py to find the entry point**

Run: `grep -n "^def build\|^def fill" backend/app/ict/fillers/verification.py`
Identify the public entry function (likely `build_verification_sheet` or
`fill_verification`). Note the signature.

- [ ] **Step 7.2: Write the failing test**

Create `tests/test_ict_verification_refactor.py`:

```python
"""Tests for the refactored verification.py that uses audit + kpi_components."""
from decimal import Decimal
from datetime import datetime

import openpyxl
import pytest

from backend.app.ict.audit.schemas import (
    A1Metrics, AnexoFinding, AnexoInterpretation, Status,
)


@pytest.fixture
def fake_a1_metrics():
    return A1Metrics(
        activo_total=Decimal("21671880.68"),
        pasivo_patrimonio_total=Decimal("21671880.68"),
        diferencia=Decimal("0.00"),
        status_cuadre=Status.OK,
        cobertura_mapeo_pct=87.0,
        cas_mapeados=47,
        cas_total=54,
        cas_sin_contrapartida=["302", "305"],
    )


@pytest.fixture
def fake_a1_interpretation():
    return AnexoInterpretation(
        anexo_codigo="A1",
        anexo_nombre="Mapeo del balance",
        resumen_ejecutivo="Balance cuadra. 2 cas sin contrapartida.",
        findings=[
            AnexoFinding(
                severity="leve",
                categoria="conciliacion_inconsistente",
                titulo="2 cas sin contrapartida contable",
                descripcion_tecnica="cas 302, 305 declarados pero sin balance",
                implicacion_tributaria="Verificar art. 19 LORTI",
                recomendacion="Revisar mapeo manual",
                casilleros_afectados=["302", "305"],
            ),
        ],
        confianza_modelo="alta",
        requiere_revision_humana=False,
        timestamp_analisis=datetime(2026, 6, 4),
        modelo_usado="claude-sonnet-4-7-20260101",
        tokens_consumidos=1500,
    )


def test_fill_verification_writes_executive_banner_and_kpis(
    fake_a1_metrics, fake_a1_interpretation
):
    from backend.app.ict.fillers.verification import fill_verification_a1
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("VERIFICACIÓN A1")
    contexto = {"razon_social": "PROPHAR S.A.",
                "ruc": "1791859596001", "periodo": "2025"}
    fill_verification_a1(
        ws,
        metrics=fake_a1_metrics,
        interpretation=fake_a1_interpretation,
        contexto=contexto,
    )
    # Banner present
    found_banner = False
    for row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
        for v in row:
            if v and "AUDITBRAIN" in str(v):
                found_banner = True
                break
    assert found_banner, "Banner ejecutivo no encontrado"
    # At least one cell shows the activo total
    found_activo = False
    for row in ws.iter_rows(values_only=True):
        for v in row:
            if v and "21,671,880" in str(v):
                found_activo = True
    assert found_activo, "Activo total no renderizado"
```

- [ ] **Step 7.3: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_verification_refactor.py -v`
Expected: FAIL (either ImportError if function doesn't exist yet or
AttributeError if signature differs)

- [ ] **Step 7.4: Refactor verification.py**

Open `backend/app/ict/fillers/verification.py`. Add a NEW public function
`fill_verification_a1` that consumes the audit metrics + interpretation.
Keep the old function as deprecated wrapper for backward compat.

Add at the top of `verification.py`:

```python
from backend.app.ict.audit.schemas import A1Metrics, AnexoInterpretation, Status
from backend.app.ict.fillers.kpi_components import (
    STATUS_COLORS,
    build_executive_banner,
    build_finding_box,
    build_kpi_card,
)
```

Add the new function (place near the existing public entry):

```python
def fill_verification_a1(
    ws,
    *,
    metrics: A1Metrics,
    interpretation: AnexoInterpretation,
    contexto: dict,
) -> None:
    """Fill the VERIFICACIÓN A1 sheet using audit data + kpi_components.

    This is the new entry point for the refactor. The old function
    `build_verification_sheet` is kept as a thin wrapper.
    """
    razon = contexto.get("razon_social", "")
    ruc = contexto.get("ruc", "")
    periodo = contexto.get("periodo", "")

    # 1. Executive banner (rows 1..3)
    build_executive_banner(
        ws,
        anchor="A1",
        title_main="AUDITBRAIN · PAPEL DE TRABAJO DEL AUDITOR",
        title_sub="VERIFICACIÓN ANEXO A1 · MAPEO BALANCE",
        meta=f"{razon} · RUC {ruc} · Período {periodo}",
        width_cols=12,
    )

    # 2. KPI cards row (rows 5..8)
    activo_fmt = f"$ {metrics.activo_total:,.2f}"
    pasivo_fmt = f"$ {metrics.pasivo_patrimonio_total:,.2f}"
    diff_fmt = f"$ {metrics.diferencia:,.2f}"

    build_kpi_card(
        ws, anchor="A5",
        title="ACTIVO TOTAL", value=activo_fmt, status=Status.OK,
        subtitle="F-101 cas 499", width_cols=4, height_rows=4,
    )
    build_kpi_card(
        ws, anchor="E5",
        title="PASIVO + PATRIMONIO", value=pasivo_fmt, status=Status.OK,
        subtitle="F-101 cas 699", width_cols=4, height_rows=4,
    )
    build_kpi_card(
        ws, anchor="I5",
        title="DIFERENCIA A=P+Pa", value=diff_fmt,
        status=metrics.status_cuadre,
        subtitle={
            Status.OK: "Cuadra",
            Status.REVISAR: "Revisar",
            Status.CRITICO: "Crítico",
            Status.NA: "Sin datos",
        }[metrics.status_cuadre],
        width_cols=4, height_rows=4,
    )

    # 3. Coverage bar (row 11)
    cobertura_txt = (
        f"COBERTURA DE MAPEO F-101 ↔ BALANCE CONTABLE: "
        f"{metrics.cobertura_mapeo_pct:.0f}%  "
        f"({metrics.cas_mapeados} de {metrics.cas_total} cas con balance)"
    )
    ws.cell(row=11, column=1, value=cobertura_txt).font = (
        __import__("openpyxl").styles.Font(name="Calibri", size=11, bold=True)
    )
    if metrics.cas_sin_contrapartida:
        warn_txt = (
            f"⚠ {len(metrics.cas_sin_contrapartida)} casilleros declarados "
            f"sin contrapartida contable: "
            f"{', '.join(metrics.cas_sin_contrapartida[:10])}"
            + (" ..." if len(metrics.cas_sin_contrapartida) > 10 else "")
        )
        ws.cell(row=12, column=1, value=warn_txt)

    # 4. Section title: existing 6.5 diferencias por revisar
    # (keep existing logic — call old function from row 14 onward)
    _fill_legacy_diferencias_section(ws, start_row=14, contexto=contexto)

    # 5. Section nueva: interpretación IA
    interp_start = _find_last_used_row(ws) + 2
    ws.cell(row=interp_start, column=1,
            value="🤖 INTERPRETACIÓN A1 · Análisis del agente").font = (
        __import__("openpyxl").styles.Font(name="Calibri", size=12, bold=True)
    )
    confianza_emoji = {"alta": "🟢", "media": "🟡", "baja": "🔴"}[
        interpretation.confianza_modelo
    ]
    ws.cell(row=interp_start + 1, column=1,
            value=f"Confianza modelo: {confianza_emoji} {interpretation.confianza_modelo.upper()}")
    ws.cell(row=interp_start + 2, column=1,
            value=f"Resumen: {interpretation.resumen_ejecutivo}").alignment = (
        __import__("openpyxl").styles.Alignment(wrap_text=True)
    )

    finding_row = interp_start + 4
    for f in interpretation.findings:
        finding_row = build_finding_box(
            ws, anchor_row=finding_row, anchor_col=1, finding=f, width_cols=12,
        ) + 2

    # 6. Disclaimer footer
    disc_row = finding_row + 2
    ws.cell(row=disc_row, column=1,
            value=("Análisis generado por IA. La interpretación debe ser "
                   "validada por el auditor responsable antes de cualquier "
                   "decisión.")).font = (
        __import__("openpyxl").styles.Font(name="Calibri", size=8, italic=True,
                                            color="6B7280")
    )


def _find_last_used_row(ws) -> int:
    last = 1
    for row in ws.iter_rows():
        for cell in row:
            if cell.value not in (None, ""):
                if cell.row > last:
                    last = cell.row
    return last


def _fill_legacy_diferencias_section(ws, *, start_row: int, contexto: dict) -> None:
    """Placeholder for the legacy section 6.5 that exists in the current
    verification.py. The refactor keeps it unchanged; callers can replace
    this body with the existing logic verbatim."""
    ws.cell(row=start_row, column=1,
            value="🔬 ARTEFACTO · DIFERENCIAS POR REVISAR").font = (
        __import__("openpyxl").styles.Font(name="Calibri", size=12, bold=True)
    )
    # TODO during execution: paste the existing 6.5 logic body here.
```

⚠️ **Note for executor:** the placeholder `_fill_legacy_diferencias_section`
needs the existing body from the current verification.py copy-pasted in.
Search for "DIFERENCIAS POR REVISAR" in the current file and migrate that
code into this function. Keep the visual output identical — only the
positioning (start_row) changes.

- [ ] **Step 7.5: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_verification_refactor.py -v`
Expected: 1 passed

- [ ] **Step 7.6: Verify legacy tests still pass**

Run: `python -m pytest tests/ -k "verification" --tb=short`
Expected: all existing verification tests pass (no regressions)

- [ ] **Step 7.7: Commit**

```bash
git add backend/app/ict/fillers/verification.py tests/test_ict_verification_refactor.py
git commit -m "ICT verification: refactor para consumir audit metrics + kpi_components

fill_verification_a1(ws, metrics, interpretation, contexto) reemplaza el
entry point antiguo. Renderiza banner ejecutivo SRI/Big 4 + 3 KPI cards
(activo/pasivo+pat/diferencia) + barra de cobertura + sección legacy 6.5
diferencias + sección nueva interpretación IA + disclaimer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — Refactor `auditoria_anexos.py` con matriz 3×3 + interpretaciones A1..A9

**Files:**
- Modify: `backend/app/ict/fillers/auditoria_anexos.py`
- Create: `tests/test_ict_auditoria_anexos_refactor.py`

- [ ] **Step 8.1: Write the failing test**

Create `tests/test_ict_auditoria_anexos_refactor.py`:

```python
"""Tests for the refactored auditoria_anexos.py."""
from datetime import datetime
from decimal import Decimal

import openpyxl
import pytest

from backend.app.ict.audit.schemas import (
    AnexoInterpretation, AnexoStatus, AnexosMetrics, Status,
)


@pytest.fixture
def fake_anexos_metrics():
    statuses = []
    statuses.append(AnexoStatus(codigo="A1", nombre="Mapeo",
                                status=Status.OK, observacion_corta="Cuadra"))
    statuses.append(AnexoStatus(codigo="A2", nombre="Ingresos",
                                status=Status.OK, observacion_corta="$4.2M"))
    statuses.append(AnexoStatus(codigo="A3", nombre="Costos",
                                status=Status.REVISAR,
                                observacion_corta="Δ $1.2K"))
    for c in ["A4", "A5", "A7", "A9"]:
        statuses.append(AnexoStatus(codigo=c, nombre=c,
                                    status=Status.OK, observacion_corta="OK"))
    statuses.append(AnexoStatus(codigo="A6", nombre="Beneficios",
                                status=Status.CRITICO,
                                observacion_corta="Falta"))
    statuses.append(AnexoStatus(codigo="A8", nombre="Com. exterior",
                                status=Status.REVISAR,
                                observacion_corta="Revisar"))
    statuses_sorted = sorted(statuses, key=lambda s: s.codigo)
    return AnexosMetrics(
        anexos=statuses_sorted,
        resumen_global={Status.OK: 6, Status.REVISAR: 2,
                        Status.CRITICO: 1, Status.NA: 0},
    )


@pytest.fixture
def fake_interpretations():
    return {
        c: AnexoInterpretation(
            anexo_codigo=c, anexo_nombre=c,
            resumen_ejecutivo=f"Resumen {c}",
            findings=[], confianza_modelo="alta",
            requiere_revision_humana=False,
            timestamp_analisis=datetime(2026, 6, 4),
            modelo_usado="claude-sonnet-4-7-20260101",
            tokens_consumidos=1000,
        )
        for c in ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
    }


def test_fill_auditoria_anexos_writes_banner_and_grid(
    fake_anexos_metrics, fake_interpretations,
):
    from backend.app.ict.fillers.auditoria_anexos import fill_auditoria_anexos
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("AUDITORÍA DE ANEXOS")
    contexto = {"razon_social": "PROPHAR S.A.",
                "ruc": "1791859596001", "periodo": "2025"}
    fill_auditoria_anexos(
        ws,
        metrics=fake_anexos_metrics,
        interpretations=fake_interpretations,
        contexto=contexto,
    )

    # Banner present
    found_banner = False
    found_codes = set()
    for row in ws.iter_rows(values_only=True):
        for v in row:
            sv = str(v) if v is not None else ""
            if "AUDITBRAIN" in sv:
                found_banner = True
            for code in [f"A{i}" for i in range(1, 10)]:
                if sv == code:
                    found_codes.add(code)
    assert found_banner
    assert found_codes == {f"A{i}" for i in range(1, 10)}
```

- [ ] **Step 8.2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_auditoria_anexos_refactor.py -v`
Expected: FAIL

- [ ] **Step 8.3: Refactor auditoria_anexos.py**

Add at the top of `backend/app/ict/fillers/auditoria_anexos.py`:

```python
from openpyxl.styles import Alignment, Font

from backend.app.ict.audit.schemas import (
    AnexoInterpretation, AnexosMetrics,
)
from backend.app.ict.fillers.kpi_components import (
    build_executive_banner,
    build_finding_box,
    build_traffic_light_grid,
)
```

Add the new public function near the existing entry:

```python
def fill_auditoria_anexos(
    ws,
    *,
    metrics: AnexosMetrics,
    interpretations: dict[str, AnexoInterpretation],
    contexto: dict,
) -> None:
    """Fill AUDITORÍA DE ANEXOS sheet with banner + 3x3 matrix + interpretations."""
    razon = contexto.get("razon_social", "")
    ruc = contexto.get("ruc", "")
    periodo = contexto.get("periodo", "")

    # 1. Banner
    build_executive_banner(
        ws, anchor="A1",
        title_main="AUDITBRAIN · PAPEL DE TRABAJO DEL AUDITOR",
        title_sub="AUDITORÍA INTEGRAL DE ANEXOS A1..A9",
        meta=f"{razon} · RUC {ruc} · Período {periodo}",
        width_cols=14,
    )

    # 2. Section title: matriz
    ws.cell(row=5, column=1,
            value="MATRIZ DE ESTADO POR ANEXO").font = Font(
        name="Calibri", size=12, bold=True
    )

    # 3. 3x3 grid
    build_traffic_light_grid(
        ws, anchor="A7", anexos_status=metrics.anexos,
        card_width_cols=4, card_height_rows=4, gap_cols=1, gap_rows=1,
    )

    # 4. Legend
    legend_row = 7 + 3 * (4 + 1) + 1
    legend_txt = (
        f"🟢 OK ({metrics.resumen_global.get('ok', 0)})   "
        f"🟧 Revisar ({metrics.resumen_global.get('revisar', 0)})   "
        f"🔴 Crítico ({metrics.resumen_global.get('critico', 0)})   "
        f"⚪ N/A ({metrics.resumen_global.get('na', 0)})"
    )
    ws.cell(row=legend_row, column=1, value=legend_txt).font = Font(
        name="Calibri", size=10, italic=True
    )

    # 5. Section: legacy detail per anexo (preserve existing logic)
    detail_start = legend_row + 2
    ws.cell(row=detail_start, column=1,
            value="DETALLE POR ANEXO").font = Font(
        name="Calibri", size=12, bold=True
    )
    _fill_legacy_anexos_section(ws, start_row=detail_start + 1, contexto=contexto)

    # 6. Section: interpretaciones IA
    interp_start = _find_last_used_row(ws) + 3
    ws.cell(row=interp_start, column=1,
            value="🤖 INTERPRETACIÓN POR ANEXO · Análisis del agente").font = Font(
        name="Calibri", size=12, bold=True
    )
    r = interp_start + 2
    for code in ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]:
        interp = interpretations.get(code)
        if interp is None:
            continue
        emoji = {"alta": "🟢", "media": "🟡", "baja": "🔴"}[interp.confianza_modelo]
        header = f"▸ {code} — {interp.anexo_nombre}  [Confianza: {emoji} {interp.confianza_modelo}]"
        ws.cell(row=r, column=1, value=header).font = Font(
            name="Calibri", size=11, bold=True
        )
        r += 1
        ws.cell(row=r, column=1, value=interp.resumen_ejecutivo).alignment = (
            Alignment(wrap_text=True)
        )
        r += 2
        for f in interp.findings:
            r = build_finding_box(ws, anchor_row=r, anchor_col=1,
                                   finding=f, width_cols=14) + 2

    # 7. Disclaimer
    disc_row = r + 2
    ws.cell(row=disc_row, column=1,
            value=("Análisis generado por IA. Toda interpretación debe ser "
                   "validada por el auditor responsable antes de cualquier "
                   "decisión, glosa o entrega al cliente.")).font = Font(
        name="Calibri", size=8, italic=True, color="6B7280"
    )


def _find_last_used_row(ws) -> int:
    last = 1
    for row in ws.iter_rows():
        for cell in row:
            if cell.value not in (None, "") and cell.row > last:
                last = cell.row
    return last


def _fill_legacy_anexos_section(ws, *, start_row: int, contexto: dict) -> None:
    """Placeholder: paste the existing per-anexo detail rendering body here
    when executing this task. Keep visual output identical."""
    pass
```

⚠️ Same as Task 7: copy the legacy per-anexo section body from the current
`auditoria_anexos.py` into `_fill_legacy_anexos_section`.

- [ ] **Step 8.4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_auditoria_anexos_refactor.py -v`
Expected: 1 passed

- [ ] **Step 8.5: Commit**

```bash
git add backend/app/ict/fillers/auditoria_anexos.py tests/test_ict_auditoria_anexos_refactor.py
git commit -m "ICT auditoria_anexos: refactor con matriz 3x3 + interpretaciones IA

fill_auditoria_anexos(ws, metrics, interpretations, contexto) reemplaza
el entry point antiguo. Renderiza banner + matriz 3x3 semáforos + leyenda
+ detalle legacy + sección interpretación IA por anexo + disclaimer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — `service.generate_excel()` devuelve tuple + split de workbooks

**Files:**
- Modify: `backend/app/ict/service.py` (function `generate_excel` line ~397)
- Modify: `backend/app/ict/router.py` (caller line ~232)
- Create: `tests/test_ict_service_split.py`

- [ ] **Step 9.1: Read existing generate_excel signature**

Run: `sed -n '395,420p' backend/app/ict/service.py`
Note the current signature and return type.

- [ ] **Step 9.2: Write the failing test**

Create `tests/test_ict_service_split.py`:

```python
"""Tests for service.generate_excel returning (bytes_sri, bytes_papel)."""
from io import BytesIO

import openpyxl
import pytest


def test_generate_excel_returns_tuple_of_two_bytes(prophar_fixture_session, db_session):
    """generate_excel must return (bytes_sri, bytes_papel_trabajo)."""
    from backend.app.ict.service import generate_excel
    result = generate_excel(db_session, session=prophar_fixture_session)
    assert isinstance(result, tuple)
    assert len(result) == 2
    bytes_sri, bytes_papel = result
    assert isinstance(bytes_sri, bytes)
    assert isinstance(bytes_papel, bytes)
    assert len(bytes_sri) > 1000
    assert len(bytes_papel) > 1000


def test_excel_sri_does_not_contain_internal_sheets(
    prophar_fixture_session, db_session,
):
    from backend.app.ict.service import generate_excel
    bytes_sri, _ = generate_excel(db_session, session=prophar_fixture_session)
    wb = openpyxl.load_workbook(BytesIO(bytes_sri))
    internal_sheets = {"VERIFICACIÓN A1", "AUDITORÍA DE ANEXOS"}
    assert internal_sheets.isdisjoint(set(wb.sheetnames)), (
        f"Excel SRI no debe contener hojas internas, encontró: "
        f"{set(wb.sheetnames) & internal_sheets}"
    )


def test_excel_papel_trabajo_contains_internal_sheets(
    prophar_fixture_session, db_session,
):
    from backend.app.ict.service import generate_excel
    _, bytes_papel = generate_excel(db_session, session=prophar_fixture_session)
    wb = openpyxl.load_workbook(BytesIO(bytes_papel))
    assert "VERIFICACIÓN A1" in wb.sheetnames
    assert "AUDITORÍA DE ANEXOS" in wb.sheetnames
```

⚠️ This requires a fixture `prophar_fixture_session` + `db_session`. If they
don't exist in `conftest.py`, the executing engineer should create minimal
fixtures or skip these tests temporarily marking them `@pytest.mark.skip` and
implement them in Task 12 (verification empírica).

- [ ] **Step 9.3: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_service_split.py -v`
Expected: either fixture errors OR assertion errors (function returns single bytes)

- [ ] **Step 9.4: Refactor generate_excel**

In `backend/app/ict/service.py`, change the signature and add splitting logic:

```python
import copy
from io import BytesIO

INTERNAL_SHEETS = ("VERIFICACIÓN A1", "AUDITORÍA DE ANEXOS")


def generate_excel(
    db: Session, *, session: ICTSession,
) -> tuple[bytes, bytes]:
    """Build workbook, return (bytes_for_sri, bytes_for_papel_trabajo).

    The SRI bytes are the cleaned workbook without internal audit sheets.
    The papel_trabajo bytes are the FULL workbook including VERIFICACIÓN A1
    and AUDITORÍA DE ANEXOS with the new KPI banners + LLM interpretations.
    """
    # 1. Build the full workbook (existing logic)
    wb_full = _build_full_workbook(db, session)  # rename of existing fn body

    # 2. Save full → papel_trabajo bytes
    buf_papel = BytesIO()
    wb_full.save(buf_papel)
    bytes_papel = buf_papel.getvalue()

    # 3. Reload, remove internal sheets → SRI bytes
    wb_sri = openpyxl.load_workbook(BytesIO(bytes_papel))
    for name in INTERNAL_SHEETS:
        if name in wb_sri.sheetnames:
            del wb_sri[name]
    buf_sri = BytesIO()
    wb_sri.save(buf_sri)
    bytes_sri = buf_sri.getvalue()

    return bytes_sri, bytes_papel
```

⚠️ Renaming the body: extract the EXISTING content of `generate_excel`
into a helper `_build_full_workbook(db, session) -> openpyxl.Workbook`
that returns the workbook in memory (before saving to bytes). Move the
final `wb.save(buf)` out of that helper.

- [ ] **Step 9.5: Update caller in router.py line ~232**

```python
# Before:
excel_bytes = ict_service.generate_excel(db, session=session)
# After:
bytes_sri, _ = ict_service.generate_excel(db, session=session)
return Response(
    content=bytes_sri,
    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    headers={"Content-Disposition": f'attachment; filename="ICT_{session.ruc}_{session.periodo}_SRI.xlsx"'},
)
```

- [ ] **Step 9.6: Update internal regeneration caller in service.py line ~642**

```python
# Before:
excel_bytes = generate_excel(db, session=session)
# After:
bytes_sri, _ = generate_excel(db, session=session)
# (or keep both if the regeneration also stores papel_trabajo)
```

- [ ] **Step 9.7: Run all tests, fix breakage**

Run: `python -m pytest tests/ -k "ict" --tb=short -q`
Expected: ICT tests pass. Fix any caller that the test suite reveals.

- [ ] **Step 9.8: Commit**

```bash
git add backend/app/ict/service.py backend/app/ict/router.py tests/test_ict_service_split.py
git commit -m "ICT service: generate_excel devuelve tuple (sri, papel_trabajo)

Cambio breaking: generate_excel ahora devuelve dos bytes. SRI = workbook
limpio sin VERIFICACIÓN A1 ni AUDITORÍA DE ANEXOS, cargable al portal
SRI sin contaminación. papel_trabajo = workbook completo con hojas
internas. Callers en router.py y service.py adaptados.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 — Endpoint nuevo `GET /papel-trabajo`

**Files:**
- Modify: `backend/app/ict/router.py`
- Modify: `tests/test_ict_service_split.py` (add endpoint test)

- [ ] **Step 10.1: Write the failing test**

Append to `tests/test_ict_service_split.py`:

```python
def test_papel_trabajo_endpoint_returns_xlsx(client, prophar_fixture_session):
    response = client.get(
        f"/ict/sessions/{prophar_fixture_session.id}/papel-trabajo"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "PAPEL_TRABAJO" in response.headers.get("content-disposition", "")
    assert len(response.content) > 1000
```

- [ ] **Step 10.2: Add the endpoint in router.py**

Add to `backend/app/ict/router.py` near the existing excel endpoint:

```python
@router.get("/sessions/{session_id}/papel-trabajo")
def download_papel_trabajo(
    session_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_authenticated),
):
    session = ict_service.get_session_or_404(db, session_id, current)
    _, bytes_papel = ict_service.generate_excel(db, session=session)
    filename = f"ICT_{session.ruc}_{session.periodo}_PAPEL_TRABAJO.xlsx"
    return Response(
        content=bytes_papel,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 10.3: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_service_split.py::test_papel_trabajo_endpoint_returns_xlsx -v`
Expected: 1 passed

- [ ] **Step 10.4: Commit**

```bash
git add backend/app/ict/router.py tests/test_ict_service_split.py
git commit -m "ICT router: endpoint GET /papel-trabajo

Nuevo endpoint que devuelve el Excel papel de trabajo del auditor
(con VERIFICACIÓN A1 y AUDITORÍA DE ANEXOS). El endpoint actual
/excel sigue devolviendo el SRI limpio.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11 — Frontend: 2 botones de descarga diferenciados

**Files:**
- Modify: `frontend-clientes/src/pages/ICTSessionResult.tsx` (o el componente equivalente)

- [ ] **Step 11.1: Find the existing download component**

Run: `grep -rln "papel\|excel\|/ict/sessions" frontend-clientes/src/ | head -5`
Identify the file with the current single download button.

- [ ] **Step 11.2: Replace single button with two**

Replace the current download button with:

```tsx
<div className="flex flex-col gap-3 mt-6">
  <button
    onClick={() => downloadFile(`/ict/sessions/${sessionId}/excel`, "SRI")}
    className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg flex items-center gap-2 text-base"
    title="Archivo limpio listo para cargar al portal del SRI Ecuador"
  >
    📤 Descargar Excel para el SRI
  </button>

  <button
    onClick={() => downloadFile(`/ict/sessions/${sessionId}/papel-trabajo`, "PAPEL_TRABAJO")}
    className="bg-slate-200 hover:bg-slate-300 text-slate-900 font-medium py-2 px-4 rounded-lg flex items-center gap-2 text-sm"
    title="Incluye VERIFICACIÓN A1, AUDITORÍA DE ANEXOS e interpretación IA. NO subir al SRI."
  >
    📋 Descargar papel de trabajo del auditor
  </button>

  <p className="text-xs text-slate-500 italic mt-1">
    Sube al SRI solamente el archivo azul. Conserva el archivo gris como
    evidencia interna de auditoría.
  </p>
</div>
```

Where `downloadFile` is:

```tsx
async function downloadFile(url: string, kind: string) {
  const response = await api.get(url, { responseType: "blob" });
  const blobUrl = URL.createObjectURL(response.data);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = response.headers["content-disposition"]?.match(/filename="(.+)"/)?.[1]
                 ?? `ICT_${kind}.xlsx`;
  a.click();
  URL.revokeObjectURL(blobUrl);
}
```

- [ ] **Step 11.3: Build the frontend**

Run: `cd frontend-clientes && npm run build`
Expected: build succeeds with no errors

- [ ] **Step 11.4: Commit**

```bash
git add frontend-clientes/src/pages/ICTSessionResult.tsx
git commit -m "Frontend ICT: 2 botones diferenciados — SRI vs papel de trabajo

Botón azul primario para Excel SRI (limpio, listo para cargar).
Botón gris secundario para papel de trabajo del auditor (incluye
VERIFICACIÓN A1, AUDITORÍA DE ANEXOS, interpretación IA).
Tooltip en cada uno + nota debajo aclarando cuál NO subir al SRI.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12 — Verificación empírica con PROPHAR (regla suprema CLAUDE.md)

**Files:**
- Create: `scripts/verify_papel_trabajo_prophar.py`
- Use: `tests/fixtures/prophar/` (debe existir; si no, el script falla con instrucciones)

- [ ] **Step 12.1: Create the verification script**

Create `scripts/verify_papel_trabajo_prophar.py`:

```python
"""Verificación empírica: genera papel_trabajo con PROPHAR y valida.

Cumple regla suprema de CLAUDE.md: no declarar trabajo concluido sin
verificar empíricamente que lo que afirmamos es correcto.
"""
import sys
from io import BytesIO
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Run: python scripts/verify_papel_trabajo_prophar.py
def main():
    from backend.app.db import SessionLocal  # adjust import to project
    from backend.app.ict import service as ict_service
    from backend.app.ict.models import ICTSession

    db = SessionLocal()
    session = db.query(ICTSession).filter(
        ICTSession.ruc == "1791859596001"
    ).order_by(ICTSession.id.desc()).first()
    if session is None:
        print("ERROR: no hay sesión ICT de PROPHAR en la BD")
        sys.exit(1)

    bytes_sri, bytes_papel = ict_service.generate_excel(db, session=session)

    # CHECK 1: ambos bytes > 0
    assert len(bytes_sri) > 1000, "Excel SRI vacío"
    assert len(bytes_papel) > 1000, "Excel papel de trabajo vacío"
    print(f"OK · Excel SRI: {len(bytes_sri):,} bytes")
    print(f"OK · Papel trabajo: {len(bytes_papel):,} bytes")

    # CHECK 2: Excel SRI NO tiene hojas internas
    wb_sri = openpyxl.load_workbook(BytesIO(bytes_sri))
    for forbidden in ("VERIFICACIÓN A1", "AUDITORÍA DE ANEXOS"):
        assert forbidden not in wb_sri.sheetnames, (
            f"Excel SRI contiene hoja prohibida: {forbidden}"
        )
    print(f"OK · Excel SRI hojas: {wb_sri.sheetnames}")

    # CHECK 3: Papel trabajo SÍ tiene hojas internas
    wb_papel = openpyxl.load_workbook(BytesIO(bytes_papel))
    assert "VERIFICACIÓN A1" in wb_papel.sheetnames
    assert "AUDITORÍA DE ANEXOS" in wb_papel.sheetnames
    print(f"OK · Papel trabajo incluye hojas internas")

    # CHECK 4: Banner ejecutivo presente en ambas hojas internas
    for sheet_name in ("VERIFICACIÓN A1", "AUDITORÍA DE ANEXOS"):
        ws = wb_papel[sheet_name]
        found_banner = any(
            "AUDITBRAIN" in str(cell.value or "")
            for row in ws.iter_rows(min_row=1, max_row=5)
            for cell in row
        )
        assert found_banner, f"Banner ejecutivo ausente en {sheet_name}"
        print(f"OK · {sheet_name}: banner ejecutivo presente")

    # CHECK 5: write to disk para inspección manual
    out_dir = ROOT / "_verify_output"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "ICT_PROPHAR_SRI.xlsx").write_bytes(bytes_sri)
    (out_dir / "ICT_PROPHAR_PAPEL_TRABAJO.xlsx").write_bytes(bytes_papel)
    print(f"\nArchivos guardados en {out_dir}/ para inspección manual.")
    print("\nAbrir manualmente y verificar:")
    print("  1. ICT_PROPHAR_SRI.xlsx — NO debe levantar cuadro 'Reparaciones'")
    print("  2. ICT_PROPHAR_SRI.xlsx — NO debe contener VERIFICACIÓN ni AUDITORÍA")
    print("  3. ICT_PROPHAR_PAPEL_TRABAJO.xlsx — KPIs visibles, semáforos correctos")
    print("  4. ICT_PROPHAR_PAPEL_TRABAJO.xlsx — Sección INTERPRETACIÓN IA con findings legibles")

if __name__ == "__main__":
    main()
```

- [ ] **Step 12.2: Run the verification script**

Run: `python scripts/verify_papel_trabajo_prophar.py`
Expected: all OK lines, no AssertionError. Files written to `_verify_output/`.

- [ ] **Step 12.3: Manual inspection in Excel**

Open both files in Excel and verify the 4 items printed by the script:
- No "Reparaciones" dialog
- SRI file has NO internal sheets
- Papel trabajo has KPI banner + 3 cards + traffic light grid 3×3
- Interpretation findings are legible

- [ ] **Step 12.4: Run full test suite**

Run: `python -m pytest tests/ -k "ict" --tb=no -q`
Expected: N passed (the new tests + all legacy ICT tests)

- [ ] **Step 12.5: Commit verification script + push**

```bash
git add scripts/verify_papel_trabajo_prophar.py
git commit -m "ICT verify: script empírico con PROPHAR para regla suprema CLAUDE.md

5 checks: bytes>0 · SRI sin hojas internas · papel con hojas · banner
ejecutivo presente · escribir archivos a _verify_output/ para inspección
visual. Cumple obligación de verificar empíricamente antes de declarar
trabajo concluido.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

## Task 13 — Update CLAUDE.md con 2 reglas nuevas

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 13.1: Add the 2 new rules**

Open `CLAUDE.md` and append at the end (before the last section):

```markdown
## Separación SRI vs Papel de trabajo del auditor

**REGLA OBLIGATORIA:** El Excel que se entrega al cliente para cargar al portal
del SRI **NUNCA debe contener hojas internas de uso del auditor** (VERIFICACIÓN A1,
AUDITORÍA DE ANEXOS, debug, logs, trazabilidad). Si una hoja existe solo para
revisión interna, debe ir en un archivo separado `ICT_{ruc}_{periodo}_PAPEL_TRABAJO.xlsx`
generado en paralelo al `ICT_{ruc}_{periodo}_SRI.xlsx`.

Razón: el SRI Ecuador espera la estructura oficial del ICT (INDICE + A1..A9).
Hojas adicionales pueden ser rechazadas, ignoradas o causar inconsistencias.

Implementación: `backend/app/ict/service.py::generate_excel()` devuelve
`tuple[bytes_sri, bytes_papel_trabajo]`. La constante `INTERNAL_SHEETS` define
qué hojas se eliminan del archivo SRI. Si se agregan nuevas hojas internas,
agregar a esa tupla.

Tests obligatorios:
- `test_excel_sri_does_not_contain_internal_sheets`
- `test_excel_papel_trabajo_contains_internal_sheets`

## Interpretación IA con disclaimer obligatorio

Toda interpretación generada por LLM en artefactos del ICT debe cumplir:

1. **Validación schema:** salida pasa por Pydantic (`AnexoInterpretation`).
   JSON inválido → reintento (max 3) → fallback a `_fallback_interpretation()`.
2. **QA evaluator:** cada interpretación pasa por skill
   `auditbrain-ai-response-quality-evaluator` antes de escribirse al Excel.
3. **Audit trail:** cada llamada queda registrada via
   `auditbrain-audit-trail-generator` (modelo, tokens, hash_input, timestamp).
4. **Disclaimer visible:** toda hoja con interpretación IA debe llevar al pie:
   "Análisis generado por IA. La interpretación debe ser validada por el
    auditor responsable antes de cualquier decisión."
5. **Confianza autoreportada:** el campo `confianza_modelo` debe renderizarse
   visualmente. Si es "baja", marcar el bloque con borde rojo + leyenda
   "⚠ Revisar manualmente".
6. **`requiere_revision_humana`:** si es True, agregar ícono dedicado en el
   bloque.

Nunca escribir un bloque interpretado al Excel sin esos 6 controles.
```

- [ ] **Step 13.2: Commit**

```bash
git add CLAUDE.md
git commit -m "CLAUDE.md: 2 reglas nuevas — separación SRI/auditoría + interpretación IA

1. Excel SRI NUNCA contiene hojas internas (VERIFICACIÓN, AUDITORÍA).
   Hojas internas van en archivo separado PAPEL_TRABAJO.
2. Toda interpretación LLM debe cumplir 6 controles: validación schema,
   QA evaluator, audit trail, disclaimer visible, confianza autoreportada,
   marca de revisión humana.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14 — Update OpenAPI/Swagger docs

**Files:**
- Modify: `backend/app/ict/router.py` (docstrings + tags)

- [ ] **Step 14.1: Add docstrings to both endpoints**

In `backend/app/ict/router.py`, add detailed docstrings:

```python
@router.get(
    "/sessions/{session_id}/excel",
    summary="Descarga Excel para cargar al SRI Ecuador",
    description=(
        "Devuelve el archivo Excel ICT LIMPIO listo para ser cargado al portal "
        "del SRI Ecuador. NO incluye hojas internas de auditoría (VERIFICACIÓN A1, "
        "AUDITORÍA DE ANEXOS). Para uso interno del auditor, usar el endpoint "
        "`/papel-trabajo`."
    ),
    response_class=Response,
)
def download_excel(...):
    ...


@router.get(
    "/sessions/{session_id}/papel-trabajo",
    summary="Descarga papel de trabajo del auditor",
    description=(
        "Devuelve el archivo Excel COMPLETO incluyendo VERIFICACIÓN A1, "
        "AUDITORÍA DE ANEXOS y la interpretación generada por IA. "
        "Este archivo es para uso interno del auditor — NO debe cargarse al SRI."
    ),
    response_class=Response,
)
def download_papel_trabajo(...):
    ...
```

- [ ] **Step 14.2: Verify Swagger UI shows the new endpoint**

Run: `python -m uvicorn app:app --port 8001 &` (start temporarily)
Open `http://localhost:8001/docs` and verify both endpoints appear with descriptions.
Kill: `pkill -f "uvicorn app:app"`

- [ ] **Step 14.3: Commit**

```bash
git add backend/app/ict/router.py
git commit -m "ICT router: docstrings + OpenAPI summaries para endpoints excel/papel-trabajo

Swagger UI ahora muestra descripción clara: cuál archivo es para cargar
al SRI y cuál es para uso interno del auditor.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

## Spec Coverage Self-Review

Mapping each spec section to a task:

| Spec section | Cubierto por |
|---|---|
| 3.1 Módulos nuevos | Tasks 1-6 (schemas, classifiers, metrics, prompts, interpreter, kpi_components) |
| 3.2 Pipeline | Task 9 (split workbooks) |
| 3.3 Schemas datos | Task 1 |
| 4.1 Layout VERIFICACIÓN A1 | Task 7 |
| 4.2 Layout AUDITORÍA DE ANEXOS | Task 8 |
| 4.3 Renderizado finding_box | Task 6 |
| 5.1 Prompt template | Task 4 |
| 5.2 Llamada LLM | Task 5 |
| 5.3 Paralelización | Task 5 (interpret_all_anexos) |
| 6.1 Defensa profundidad (1,2,4,5) | Task 5 |
| 6.1 Item 3 QA evaluator | ⚠️ **GAP** — agregar en Task 5 hookpoint, llamar skill desde service.py |
| 6.1 Item 6 audit trail | ⚠️ **GAP** — invocación de skill auditbrain-audit-trail-generator |
| 6.1 Item 7 disclaimer | Tasks 7, 8 |
| 6.2 Resilience | Task 5 |
| 7.1 Backend endpoints | Tasks 9, 10 |
| 7.2 Frontend | Task 11 |
| 8 Testing | Tasks 1-12 (cada task tiene tests + Task 12 E2E) |
| 11 Action item 17 CLAUDE.md | Task 13 |
| 11 Action item 18 OpenAPI | Task 14 |

**GAP detectado** en self-review: las invocaciones de skills internas
(`auditbrain-ai-response-quality-evaluator` y `auditbrain-audit-trail-generator`)
no quedaron como tasks ejecutables porque dependen del subsistema de skills
runtime que vive en otro plano (Claude Code). Se documentan como hooks
intencionales en Task 5: el código deja el punto de extensión preparado pero
la invocación real ocurre cuando se ejecuta dentro del runtime con esas skills
disponibles. Esto debe documentarse en el commit final.

---

## Plan complete and saved to `docs/superpowers/plans/2026-06-04-papel-trabajo-auditor.md`

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints

Which approach?
