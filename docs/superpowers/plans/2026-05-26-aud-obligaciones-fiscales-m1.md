# AUD Obligaciones Fiscales — M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar la herramienta `AUD.IMPUESTOS.OBLIGACIONES_FISCALES` en modo **efímero** (upload → procesar → descargar → borrar), con las cédulas **DM6 IVA** y **DM7 Retenciones** funcionales. El resto de cédulas se entregan en M2.

**Architecture:** Módulo aditivo bajo `backend/app/aud/obligaciones_fiscales/` siguiendo el patrón existente del repo. Plantilla Excel `DM Obligaciones Fiscales` baked-in. Storage solo en `/tmp` del contenedor con TTL 1h. 1 tabla nueva (`tool_jobs`) para metadata. Frontend en `frontend/src/aud/`.

**Tech Stack:** FastAPI 0.115 · SQLAlchemy 2.0 · pdfplumber · openpyxl · React 18 + Vite · pytest. **No se introduce R2 ni boto3.**

**Spec referencia:** `docs/superpowers/specs/2026-05-26-aud-obligaciones-fiscales-design.md`

---

## File Structure

### Backend — nuevos archivos
```
backend/app/aud/__init__.py
backend/app/aud/obligaciones_fiscales/__init__.py
backend/app/aud/obligaciones_fiscales/models.py                  # ToolJob
backend/app/aud/obligaciones_fiscales/schemas.py                 # Pydantic
backend/app/aud/obligaciones_fiscales/service.py                 # CRUD + autorización
backend/app/aud/obligaciones_fiscales/router.py                  # HTTP endpoints
backend/app/aud/obligaciones_fiscales/jobs.py                    # BackgroundTask orquestador
backend/app/aud/obligaciones_fiscales/file_storage.py            # Helpers para /tmp
backend/app/aud/obligaciones_fiscales/cleanup.py                 # Cleanup de jobs/dirs viejos
backend/app/aud/obligaciones_fiscales/excel_assembler.py         # Carga plantilla + escribe celdas
backend/app/aud/obligaciones_fiscales/templates/dm_obligaciones_fiscales.xlsx  # Plantilla baked-in
backend/app/aud/obligaciones_fiscales/cedulas/__init__.py
backend/app/aud/obligaciones_fiscales/cedulas/base.py            # Interface CedulaCompute
backend/app/aud/obligaciones_fiscales/cedulas/dm6_iva.py         # Extractor F-104 + transformer DM6
backend/app/aud/obligaciones_fiscales/cedulas/dm7_retenciones.py # Extractor F-103 + transformer DM7
```

### Backend — archivos modificados
```
backend/app/db/session.py             # Registrar ToolJob en init_db()
backend/app/api/__init__.py           # include_router del nuevo módulo
backend/app/core/config.py            # AUD_OF_TMP_DIR, AUD_OF_JOB_TTL_MINUTES, AUD_OF_MAX_FILE_MB
app.py                                # Startup hook para iniciar cleanup periódico
```

### Frontend — nuevos archivos
```
frontend/src/aud/catalog.js                  # Lista de 15 categorías
frontend/src/aud/strings.js                  # Strings centralizadas (i18n placeholder)
frontend/src/aud/ToolCatalog.jsx             # UI catálogo
frontend/src/aud/ObligacionesFiscalesTool.jsx # UI principal de la herramienta
```

### Frontend — archivos modificados
```
frontend/src/App.jsx                  # import + bloque condicional en tab Análisis
frontend/src/api.js                   # Métodos para los nuevos endpoints
frontend/src/styles.css               # Estilos de catálogo + upload zone
```

### Tests nuevos
```
tests/test_aud_of_models.py
tests/test_aud_of_storage.py
tests/test_aud_of_cedula_dm6.py
tests/test_aud_of_cedula_dm7.py
tests/test_aud_of_excel_assembler.py
tests/test_aud_of_service.py
tests/test_aud_of_router.py
tests/test_aud_of_jobs.py
tests/test_aud_of_cleanup.py
```

### Fixtures binarias
```
tests/fixtures/obligaciones_fiscales/f103_enero.pdf      # Del usuario
tests/fixtures/obligaciones_fiscales/f104_enero.pdf      # Del usuario
```

### Documentación
```
docs/AUD_OF_M1_E2E.md                # Checklist verificación E2E
docs/AUD_OF_CELL_MAPPING.md          # Mapeo de celdas DM6/DM7 → casilleros SRI
```

---

## Cell Mapping del Excel (referencia para todas las tareas)

Mapeo descubierto en la plantilla `DM - Obligaciones Fiscales Final.xlsx` que el sistema debe poblar.

### Pestaña "DM6 IVA"

| Mes | Fila |
|---|---|
| Enero | 20 |
| Febrero | 21 |
| ... | ... |
| Diciembre | 31 |

| Col | Cell ejemplo (Enero) | Contenido | Origen |
|---|---|---|---|
| A | A20 | Nombre del mes (texto) | Hardcoded en plantilla |
| B | B20 | Ventas netas tarifa diferente 0% (libros) | Linked a `'DM5 Ventas '!C19` — para M1 dejamos sin tocar |
| C | C20 | Ventas netas tarifa 0% (con derecho a crédito) | **De F-104 casillero 411** |
| D | D20 | Ventas netas tarifa 0% (sin derecho a crédito) | **De F-104 casillero 412** |
| E | E20 | Exportaciones de bienes y servicios | **De F-104 casillero 421** |
| F | F20 | Ventas netas gravadas tarifa 15% (12% antes) | Formula `=+B20` — sin tocar |
| G | G20 | Tarifa de IVA vigente | 0.15 (configurable) |
| H-S | H20:S20 | Formulas Excel | Sin tocar |
| N | N20 | Adquisiciones e importaciones | Linked a `'DM4 Compras '!C42+C43` — sin tocar en M1 |

**Decisión M1:** Para DM6 poblamos solo **C20-E20** (y demás meses) con los casilleros 411, 412, 421 del F-104. El resto queda con valores/formulas de la plantilla.

### Pestaña "DM7 Retenciones x pagar"

| Mes | Fila |
|---|---|
| Enero | 21 |
| Febrero | 22 |
| ... | ... |
| Diciembre | 32 |

| Col | Cell ejemplo (Enero) | Contenido | Origen |
|---|---|---|---|
| A | A21 | Nombre del mes | Hardcoded |
| B | B21 | Retención 10% según libros | Mayor de retenciones — **M1 deja vacío (0)** |
| C | C21 | Retención 20% según libros | Mayor — vacío en M1 |
| D | D21 | Retención 30% según libros | Mayor — vacío en M1 |
| E | E21 | Retención 70% según libros | Mayor — vacío en M1 |
| F | F21 | Retención 100% según libros | Mayor — vacío en M1 |
| G | G21 | Total retenciones IVA | Formula `=SUM(B21:F21)` — sin tocar |
| H | H21 | Retención 10% (casillero 721) | **De F-103 casillero 721** |
| I | I21 | Retención 20% (casillero 723) | **De F-103 casillero 723** |
| J | J21 | Retención 30% (casillero 725) | **De F-103 casillero 725** |
| K | K21 | Retención 70% (casillero 729) | **De F-103 casillero 729** |
| L | L21 | Retención 100% (casillero 731) | **De F-103 casillero 731** |
| M | M21 | Retención 50% (casillero 727) | **De F-103 casillero 727** |
| N | N21 | Total IVA retenido (casillero 799) | Formula `=SUM(H21:M21)` — sin tocar |
| O-S | O21:S21 | Diferencias | Formulas — sin tocar |

**Decisión M1:** Para DM7 poblamos **H21-M21** (y demás meses) con los casilleros del F-103. Las diferencias quedan calculadas automáticamente por Excel.

### Encabezado común (todas las pestañas)

Cells visibles en R4-R10 que se actualizan por job:
- B5 / B6: Nombre del cliente (input del usuario)
- E5 / D5: Período terminado (input del usuario, fecha)
- A8: Preparado por
- A10: Revisado por

---

## Pre-requisitos antes de empezar

1. **Plantilla Excel** disponible: ✅ `C:/Users/jcalu/Downloads/Prueba Cloude/Prueba Cloude/DM - Obligaciones Fiscales Final.xlsx`
2. **F-103 muestra**: ✅ `C:/Users/jcalu/Downloads/Prueba Cloude/Prueba Cloude/F-103/Declaracion 103 de enero.pdf`
3. **F-104 muestra**: ✅ `C:/Users/jcalu/Downloads/Prueba Cloude/Prueba Cloude/F-104/Declaracion 104 DE ENERO.pdf`
4. **Anonimización**: la plantilla contiene "NEGOCIOS MORACOSTA S.A.". Para fixtures de tests reemplazar por "EMPRESA DE PRUEBA S.A.".
5. **Permiso para commitear los PDFs como fixtures** — confirmar con el usuario que las muestras pueden ir al repo (anonimizadas).

---

## Task 1: Scaffold + dependencias

**Files:**
- Create: `backend/app/aud/__init__.py`
- Create: `backend/app/aud/obligaciones_fiscales/__init__.py`
- Create: `backend/app/aud/obligaciones_fiscales/cedulas/__init__.py`
- Create: `backend/app/aud/obligaciones_fiscales/templates/.gitkeep`
- Modify: `requirements.txt`, `requirements-prod.txt`

- [ ] **Step 1.1: Crear estructura de carpetas**

```bash
mkdir -p backend/app/aud/obligaciones_fiscales/cedulas
mkdir -p backend/app/aud/obligaciones_fiscales/templates
mkdir -p tests/fixtures/obligaciones_fiscales
```

- [ ] **Step 1.2: Crear `backend/app/aud/__init__.py`**

```python
"""Módulo AUD — External Audit. Catálogo de herramientas sectoriales."""
```

- [ ] **Step 1.3: Crear `backend/app/aud/obligaciones_fiscales/__init__.py`**

```python
"""Herramienta AUD.IMPUESTOS.OBLIGACIONES_FISCALES — modelo efímero.

Recibe PDFs F-103, F-104, ATS XML, mayores Excel.
Procesa con Python.
Devuelve Excel descargable a partir de plantilla baked-in.
Sin storage en la nube.
"""
```

- [ ] **Step 1.4: Crear `backend/app/aud/obligaciones_fiscales/cedulas/__init__.py`**

```python
"""Cédulas DM* del papel de trabajo Obligaciones Fiscales.

Cada módulo expone:
- extract_*(file_bytes) → dict | None
- compute(*extractions) → dict de datos para excel_assembler
"""
```

- [ ] **Step 1.5: Crear `.gitkeep` para templates**

```bash
touch backend/app/aud/obligaciones_fiscales/templates/.gitkeep
```

- [ ] **Step 1.6: Verificar que pdfplumber y openpyxl ya están**

Run: `grep -E "pdfplumber|openpyxl" requirements.txt requirements-prod.txt`
Expected: ambos aparecen. (Ya están: pdfplumber==0.11.5, openpyxl==3.1.5).

Si no están en `requirements-prod.txt`, agregar:
```
pdfplumber==0.11.5
openpyxl==3.1.5
```

- [ ] **Step 1.7: Commit**

```bash
git add backend/app/aud requirements.txt requirements-prod.txt
git commit -m "feat(aud/obligaciones_fiscales): scaffold module structure"
```

---

## Task 2: Settings de configuración

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 2.1: Agregar settings en `Settings` class**

Abrir `backend/app/core/config.py`. Antes de `# Auth mínima por API Key`, agregar:

```python
    # --- AUD.IMPUESTOS.OBLIGACIONES_FISCALES (efímero) ---
    AUD_OF_TMP_DIR: str = os.getenv(
        "AUD_OF_TMP_DIR", "/tmp/auditbrain/obligaciones_fiscales"
    )
    AUD_OF_JOB_TTL_MINUTES: int = int(os.getenv("AUD_OF_JOB_TTL_MINUTES", "60"))
    AUD_OF_POST_DOWNLOAD_TTL_MINUTES: int = int(
        os.getenv("AUD_OF_POST_DOWNLOAD_TTL_MINUTES", "5")
    )
    AUD_OF_MAX_FILE_MB: int = int(os.getenv("AUD_OF_MAX_FILE_MB", "20"))
    AUD_OF_MAX_TOTAL_MB: int = int(os.getenv("AUD_OF_MAX_TOTAL_MB", "100"))
    AUD_OF_CLEANUP_INTERVAL_SECONDS: int = int(
        os.getenv("AUD_OF_CLEANUP_INTERVAL_SECONDS", "300")
    )

    @property
    def aud_of_tmp_dir_path(self):
        from pathlib import Path

        p = Path(self.AUD_OF_TMP_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p
```

- [ ] **Step 2.2: Verificar import**

Run: `python -c "from backend.app.core.config import settings; print(settings.AUD_OF_TMP_DIR, settings.AUD_OF_JOB_TTL_MINUTES)"`
Expected: imprime `/tmp/auditbrain/obligaciones_fiscales 60`

- [ ] **Step 2.3: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat(config): add AUD obligaciones fiscales ephemeral settings"
```

---

## Task 3: `file_storage.py` — helpers para `/tmp` (TDD)

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/file_storage.py`
- Test: `tests/test_aud_of_storage.py`

- [ ] **Step 3.1: Escribir test (failing)**

Crear `tests/test_aud_of_storage.py`:

```python
"""Tests de file_storage.py — helpers para /tmp efímero."""

from pathlib import Path

import pytest

from backend.app.aud.obligaciones_fiscales import file_storage


@pytest.fixture()
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(file_storage)
    yield tmp_path


def test_create_job_dir_makes_inputs_subfolder(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=42)
    assert job_dir.exists()
    assert (job_dir / "inputs").exists()
    assert "42" in str(job_dir)


def test_save_input_writes_file(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=1)
    saved = file_storage.save_input(
        job_dir, slot="f103", filename="enero.pdf", data=b"%PDF-1.4 fake"
    )
    assert saved.exists()
    assert saved.read_bytes() == b"%PDF-1.4 fake"
    assert "f103" in str(saved)


def test_save_input_strips_unsafe_chars(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=2)
    saved = file_storage.save_input(
        job_dir, slot="f104", filename="../../etc/passwd", data=b"x"
    )
    assert ".." not in saved.name


def test_output_path_returns_consistent_location(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=3)
    out = file_storage.output_path(job_dir)
    assert out.name == "output.xlsx"
    assert out.parent == job_dir


def test_delete_job_dir_removes_recursively(tmp_root):
    job_dir = file_storage.create_job_dir(job_id=4)
    file_storage.save_input(job_dir, "f103", "a.pdf", b"x")
    assert job_dir.exists()
    file_storage.delete_job_dir(job_id=4)
    assert not job_dir.exists()


def test_list_orphan_job_dirs_returns_old_ones(tmp_root):
    import time

    j1 = file_storage.create_job_dir(job_id=10)
    j2 = file_storage.create_job_dir(job_id=11)
    # Hacer j1 viejo
    very_old = time.time() - 7200  # 2h atrás
    import os

    os.utime(j1, (very_old, very_old))
    orphans = file_storage.list_orphan_job_dirs(max_age_seconds=3600)
    orphan_ids = [int(p.name) for p in orphans]
    assert 10 in orphan_ids
    assert 11 not in orphan_ids
```

- [ ] **Step 3.2: Correr test (debe fallar)**

Run: `pytest tests/test_aud_of_storage.py -v`
Expected: FAIL (módulo no existe).

- [ ] **Step 3.3: Implementar `file_storage.py`**

Crear `backend/app/aud/obligaciones_fiscales/file_storage.py`:

```python
"""Helpers para storage efímero en /tmp del contenedor.

Estructura:
  <AUD_OF_TMP_DIR>/
    <job_id>/
      inputs/
        f103/<safe_filename>
        f104/<safe_filename>
        ats/...
        mayor_compras/...
        mayor_ventas/...
        f101/...
      output.xlsx
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from backend.app.core.config import settings

OUTPUT_FILENAME = "output.xlsx"
INPUTS_DIR = "inputs"


def _root() -> Path:
    return settings.aud_of_tmp_dir_path


def _safe_filename(name: str) -> str:
    base = Path(name).name  # quita cualquier path
    return re.sub(r"[^a-zA-Z0-9._-]", "_", base)[:200] or "file"


def job_dir(job_id: int) -> Path:
    return _root() / str(job_id)


def create_job_dir(job_id: int) -> Path:
    d = job_dir(job_id)
    (d / INPUTS_DIR).mkdir(parents=True, exist_ok=True)
    return d


def save_input(
    job_dir: Path, slot: str, filename: str, data: bytes
) -> Path:
    """Guarda un archivo de input bajo inputs/<slot>/<safe_filename>."""
    safe = _safe_filename(filename)
    safe_slot = _safe_filename(slot)
    slot_dir = job_dir / INPUTS_DIR / safe_slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    target = slot_dir / safe
    target.write_bytes(data)
    return target


def list_inputs(job_dir: Path, slot: str | None = None) -> list[Path]:
    """Lista archivos de input. Si slot es None, lista todos."""
    base = job_dir / INPUTS_DIR
    if not base.exists():
        return []
    if slot:
        slot_dir = base / _safe_filename(slot)
        return sorted(slot_dir.glob("*")) if slot_dir.exists() else []
    return sorted(base.rglob("*") if base.exists() else [])


def output_path(job_dir: Path) -> Path:
    return job_dir / OUTPUT_FILENAME


def delete_job_dir(job_id: int) -> None:
    d = job_dir(job_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def list_orphan_job_dirs(max_age_seconds: int) -> list[Path]:
    """Lista directorios cuya mtime es > max_age_seconds atrás."""
    root = _root()
    if not root.exists():
        return []
    now = time.time()
    orphans = []
    for child in root.iterdir():
        if not child.is_dir() or not child.name.isdigit():
            continue
        age = now - child.stat().st_mtime
        if age > max_age_seconds:
            orphans.append(child)
    return orphans
```

- [ ] **Step 3.4: Correr tests**

Run: `pytest tests/test_aud_of_storage.py -v`
Expected: 6 PASS.

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/file_storage.py tests/test_aud_of_storage.py
git commit -m "feat(aud/of): add file_storage helpers for ephemeral /tmp"
```

---

## Task 4: Modelo `ToolJob` + registrar en init_db

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/models.py`
- Modify: `backend/app/db/session.py`
- Test: `tests/test_aud_of_models.py`

- [ ] **Step 4.1: Crear `models.py`**

```python
"""Modelos SQLAlchemy de AUD.IMPUESTOS.OBLIGACIONES_FISCALES.

Solo metadata. Los archivos NO se persisten en DB (viven en /tmp del contenedor).
"""

import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


class ToolJob(Base):
    __tablename__ = "tool_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tool_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    cliente_name: Mapped[str] = mapped_column(String(200), nullable=False)
    period_label: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime.date | None] = mapped_column(nullable=True)
    period_end: Mapped[datetime.date | None] = mapped_column(nullable=True)
    prepared_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    downloaded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 4.2: Registrar en `init_db()`**

Abrir `backend/app/db/session.py`. En `init_db()`, agregar el import del nuevo módulo junto a los existentes:

```python
def init_db() -> None:
    ...
    from sqlalchemy import inspect, text

    from backend.app.auth import models as _auth_models  # noqa: F401
    from backend.app.aud.obligaciones_fiscales import models as _aud_of_models  # noqa: F401
    from backend.app.chat import models as _chat_models  # noqa: F401
    from backend.app.context import models as _context_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ...
```

- [ ] **Step 4.3: Test de tabla creada**

Crear `tests/test_aud_of_models.py`:

```python
"""Verifica que ToolJob queda registrado en init_db()."""

from sqlalchemy import inspect

from backend.app.db.session import engine, init_db


def test_tool_jobs_table_exists():
    init_db()
    insp = inspect(engine)
    assert "tool_jobs" in insp.get_table_names()


def test_tool_jobs_required_columns():
    init_db()
    cols = {c["name"] for c in inspect(engine).get_columns("tool_jobs")}
    assert {
        "id", "user_id", "project_id", "tool_code", "status",
        "cliente_name", "period_label", "created_at", "expires_at",
    } <= cols
```

- [ ] **Step 4.4: Correr tests**

Run: `pytest tests/test_aud_of_models.py -v`
Expected: 2 PASS.

- [ ] **Step 4.5: Correr suite completa para verificar no regresiones**

Run: `pytest -v`
Expected: TODOS pasan (los existentes + nuestros nuevos).

- [ ] **Step 4.6: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/models.py backend/app/db/session.py tests/test_aud_of_models.py
git commit -m "feat(aud/of): add ToolJob model + register in init_db"
```

---

## Task 5: Pydantic schemas

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/schemas.py`

- [ ] **Step 5.1: Crear schemas**

```python
"""Pydantic schemas de la API de AUD.IMPUESTOS.OBLIGACIONES_FISCALES."""

import datetime

from pydantic import BaseModel


class JobCreateForm(BaseModel):
    """Datos del form (no incluye archivos — esos van como UploadFile en multipart)."""
    project_id: int
    cliente_name: str
    period_label: str
    period_start: datetime.date | None = None
    period_end: datetime.date | None = None
    prepared_by_name: str | None = None
    reviewed_by_name: str | None = None


class JobOut(BaseModel):
    id: int
    user_id: int | None
    project_id: int
    tool_code: str
    status: str
    cliente_name: str
    period_label: str
    period_start: datetime.date | None
    period_end: datetime.date | None
    prepared_by_name: str | None
    reviewed_by_name: str | None
    error_message: str | None
    summary_json: dict | None
    created_at: datetime.datetime
    finished_at: datetime.datetime | None
    downloaded_at: datetime.datetime | None
    expires_at: datetime.datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5.2: Verificar import**

Run: `python -c "from backend.app.aud.obligaciones_fiscales import schemas; print(list(schemas.JobOut.model_fields.keys()))"`
Expected: imprime lista de campos.

- [ ] **Step 5.3: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/schemas.py
git commit -m "feat(aud/of): add Pydantic schemas"
```

---

## Task 6: Copiar plantilla baked-in + fixtures

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/templates/dm_obligaciones_fiscales.xlsx`
- Create: `tests/fixtures/obligaciones_fiscales/f103_enero.pdf`
- Create: `tests/fixtures/obligaciones_fiscales/f104_enero.pdf`
- Create: `docs/AUD_OF_CELL_MAPPING.md`

- [ ] **Step 6.1: Copiar plantilla**

```bash
cp "C:/Users/jcalu/Downloads/Prueba Cloude/Prueba Cloude/DM - Obligaciones Fiscales Final.xlsx" backend/app/aud/obligaciones_fiscales/templates/dm_obligaciones_fiscales.xlsx
```

- [ ] **Step 6.2: Copiar PDFs de muestra como fixtures**

```bash
cp "C:/Users/jcalu/Downloads/Prueba Cloude/Prueba Cloude/F-103/Declaracion 103 de enero.pdf" tests/fixtures/obligaciones_fiscales/f103_enero.pdf
cp "C:/Users/jcalu/Downloads/Prueba Cloude/Prueba Cloude/F-104/Declaracion 104 DE ENERO.pdf" tests/fixtures/obligaciones_fiscales/f104_enero.pdf
```

> **CONFIRMAR CON USUARIO**: ¿están OK con que estos archivos vayan al repo? Si tienen datos sensibles, anonimizar antes (reemplazar RUC, nombres, etc.) o usar archivos de prueba sintéticos.

- [ ] **Step 6.3: Documentar mapeo de celdas**

Crear `docs/AUD_OF_CELL_MAPPING.md` con el contenido de la sección "Cell Mapping del Excel" de este plan (copiar las dos tablas).

- [ ] **Step 6.4: Verificar tamaño y commit**

```bash
ls -la backend/app/aud/obligaciones_fiscales/templates/ tests/fixtures/obligaciones_fiscales/
git add backend/app/aud/obligaciones_fiscales/templates/dm_obligaciones_fiscales.xlsx \
        tests/fixtures/obligaciones_fiscales/*.pdf \
        docs/AUD_OF_CELL_MAPPING.md
git commit -m "chore(aud/of): add baked-in template + sample fixtures + cell mapping doc"
```

---

## Task 7: Cédula DM7 Retenciones (extractor F-103)

> **Por qué empezamos por DM7:** estructura más directa (5 casilleros), más datos hardcoded en plantilla, valida nuestro pipeline. DM6 IVA viene después.

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/cedulas/base.py`
- Create: `backend/app/aud/obligaciones_fiscales/cedulas/dm7_retenciones.py`
- Test: `tests/test_aud_of_cedula_dm7.py`

- [ ] **Step 7.1: Crear interface `base.py`**

```python
"""Interface base para cédulas DM*.

Cada cédula expone:
- expected_inputs(): list[str] de slots de archivos requeridos
- compute(inputs: dict[slot, list[Path]]) -> dict de datos para excel_assembler
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class CedulaCompute(Protocol):
    code: str  # "DM6", "DM7", etc.

    def expected_inputs(self) -> list[str]:
        ...

    def compute(self, inputs: dict[str, list[Path]]) -> dict:
        ...
```

- [ ] **Step 7.2: Escribir test del extractor F-103 (failing)**

Crear `tests/test_aud_of_cedula_dm7.py`:

```python
"""Tests de la cédula DM7 Retenciones (extractor F-103)."""

from pathlib import Path

import pytest

from backend.app.aud.obligaciones_fiscales.cedulas import dm7_retenciones

FIXTURES = Path(__file__).parent / "fixtures" / "obligaciones_fiscales"


def test_extract_f103_returns_casilleros():
    pdf_path = FIXTURES / "f103_enero.pdf"
    assert pdf_path.exists(), "fixture missing"
    data = dm7_retenciones.extract_f103(pdf_path.read_bytes())
    # F-103 enero del cliente de muestra — valores específicos pueden variar.
    # Solo validamos estructura.
    assert data is not None
    assert "periodo" in data        # ej. "01/2025"
    assert "casilleros" in data
    cas = data["casilleros"]
    # Casilleros clave de retención de IVA
    for k in ["721", "723", "725", "727", "729", "731", "799"]:
        assert k in cas, f"falta casillero {k}"
        assert isinstance(cas[k], (int, float)) or cas[k] is None


def test_compute_dm7_one_month():
    rows_per_month = {
        "01": {"casilleros": {"721": 8594.74, "723": 25.41, "725": 304.62,
                              "727": 0, "729": 997.3, "731": 37.5, "799": 9959.57}}
    }
    result = dm7_retenciones.compute_from_months(rows_per_month)
    assert "rows" in result
    assert len(result["rows"]) == 12  # siempre 12 meses
    enero = result["rows"][0]
    assert enero["mes"] == "Enero"
    assert enero["c721"] == 8594.74
    assert enero["c723"] == 25.41
    febrero = result["rows"][1]
    assert febrero["c721"] is None  # sin datos
```

- [ ] **Step 7.3: Correr tests (deben fallar)**

Run: `pytest tests/test_aud_of_cedula_dm7.py -v`
Expected: FAIL.

- [ ] **Step 7.4: Implementar `dm7_retenciones.py` (extractor mínimo)**

Crear `backend/app/aud/obligaciones_fiscales/cedulas/dm7_retenciones.py`:

```python
"""Cédula DM7 — Retenciones en la fuente (extractor F-103)."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import pdfplumber

code = "DM7"

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# Casilleros del F-103 relevantes para DM7
CASILLEROS_F103 = ["721", "723", "725", "727", "729", "731", "799"]


def expected_inputs() -> list[str]:
    return ["f103"]


def _parse_money(text: str) -> float | None:
    """Convierte '8.594,74' o '8,594.74' o '8594.74' a float."""
    if not text:
        return None
    s = text.strip().replace(" ", "")
    # Detectar separador decimal: si tiene coma decimal (ej '8.594,74')
    if re.match(r"^-?\d{1,3}(\.\d{3})*,\d+$", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def extract_f103(pdf_bytes: bytes) -> dict | None:
    """Extrae datos de un PDF F-103 (declaración de retenciones en la fuente SRI Ecuador).

    Devuelve: { "periodo": "MM/AAAA", "casilleros": {numero: valor} }
    o None si el PDF no se puede parsear.
    """
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return None
    if not text.strip():
        return None

    # Período: buscar patrones tipo "Mes: 01 Año: 2025" o "01/2025"
    periodo = _find_periodo(text)

    # Casilleros: línea como "721 ... 8.594,74" o tabular "721\t8594.74"
    casilleros = {}
    for num in CASILLEROS_F103:
        val = _find_casillero_value(text, num)
        casilleros[num] = val

    return {"periodo": periodo, "casilleros": casilleros}


def _find_periodo(text: str) -> str | None:
    # Patrones comunes en F-103
    m = re.search(r"Mes[:\s]*0?(\d{1,2})\s*A[ñn]o[:\s]*(\d{4})", text, re.IGNORECASE)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}"
    m = re.search(r"\b(0?\d|1[0-2])\s*/\s*(20\d{2})\b", text)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}"
    return None


def _find_casillero_value(text: str, casillero: str) -> float | None:
    # Patron 1: "721 ... <number>" en la misma línea
    pattern = rf"\b{casillero}\b[^\n0-9-]*?(-?[\d.,]+)"
    matches = re.findall(pattern, text)
    for raw in matches:
        v = _parse_money(raw)
        if v is not None:
            return v
    return None


def compute_from_months(month_data: dict[str, dict]) -> dict:
    """Combina datos extraídos de los 12 meses en estructura para excel_assembler.

    month_data: { "01": {casilleros: {...}}, "02": {...}, ... }
    Devuelve: { "rows": [{mes, c721, c723, c725, c727, c729, c731, c799}, ...] }
    """
    rows = []
    for i, mes in enumerate(MESES, start=1):
        key = f"{i:02d}"
        m = month_data.get(key, {})
        cas = m.get("casilleros", {}) if m else {}
        rows.append({
            "mes": mes,
            "c721": cas.get("721"),
            "c723": cas.get("723"),
            "c725": cas.get("725"),
            "c727": cas.get("727"),
            "c729": cas.get("729"),
            "c731": cas.get("731"),
            "c799": cas.get("799"),
            "has_data": bool(m),
        })
    return {"rows": rows, "total_months_with_data": sum(1 for r in rows if r["has_data"])}


def compute(inputs: dict[str, list[Path]]) -> dict:
    """Lee los PDFs F-103 del slot 'f103', extrae cada uno, agrupa por mes."""
    pdfs = inputs.get("f103", []) or []
    month_data: dict[str, dict] = {}
    errors: list[str] = []
    for path in pdfs:
        data = extract_f103(path.read_bytes())
        if data is None:
            errors.append(f"No se pudo parsear: {path.name}")
            continue
        periodo = data.get("periodo")
        if not periodo:
            errors.append(f"Sin período detectado: {path.name}")
            continue
        mes_key = periodo.split("/")[0]
        month_data[mes_key] = data
    out = compute_from_months(month_data)
    out["errors"] = errors
    return out
```

- [ ] **Step 7.5: Correr tests**

Run: `pytest tests/test_aud_of_cedula_dm7.py -v`
Expected: PASS para `test_compute_dm7_one_month`. `test_extract_f103_returns_casilleros` puede fallar si los regex no matchean el formato exacto del PDF — ajustar `_find_casillero_value` o `_find_periodo` iterando con el PDF real.

- [ ] **Step 7.6: Si el test de extracción falla, debug iterativo**

Si falla, hacer:

```bash
python -c "
import pdfplumber
with pdfplumber.open('tests/fixtures/obligaciones_fiscales/f103_enero.pdf') as pdf:
    print(pdf.pages[0].extract_text()[:3000])
"
```

Inspeccionar el output y ajustar los regex en `dm7_retenciones.py` hasta que el test pase. Casos típicos:
- El SRI usa formato 8.594,74 (decimal coma) — el `_parse_money` ya lo maneja
- El casillero puede estar en líneas separadas del valor — ajustar regex con `re.DOTALL` o `re.MULTILINE`
- Pueden aparecer múltiples valores en el PDF — preferir el que esté después de la palabra "Total" o en la sección "Resumen"

- [ ] **Step 7.7: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/cedulas/base.py \
        backend/app/aud/obligaciones_fiscales/cedulas/dm7_retenciones.py \
        tests/test_aud_of_cedula_dm7.py
git commit -m "feat(aud/of): add DM7 Retenciones cedula (F-103 extractor + transformer)"
```

---

## Task 8: Cédula DM6 IVA (extractor F-104)

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/cedulas/dm6_iva.py`
- Test: `tests/test_aud_of_cedula_dm6.py`

Análogo a Task 7 pero para F-104. Casilleros relevantes: 411 (ventas 0% c/derecho), 412 (ventas 0% s/derecho), 421 (exportaciones), 419 (ventas tarifa diferente de 0), 429 (IVA en ventas), 480 (compras tarifa 12%/15%), etc.

- [ ] **Step 8.1: Test (failing)**

Crear `tests/test_aud_of_cedula_dm6.py`:

```python
"""Tests de la cédula DM6 IVA (extractor F-104)."""

from pathlib import Path

import pytest

from backend.app.aud.obligaciones_fiscales.cedulas import dm6_iva

FIXTURES = Path(__file__).parent / "fixtures" / "obligaciones_fiscales"


def test_extract_f104_returns_casilleros():
    pdf_path = FIXTURES / "f104_enero.pdf"
    assert pdf_path.exists()
    data = dm6_iva.extract_f104(pdf_path.read_bytes())
    assert data is not None
    assert "periodo" in data
    assert "casilleros" in data
    for k in ["411", "412", "419", "421", "429", "480"]:
        assert k in data["casilleros"]


def test_compute_dm6_one_month():
    month_data = {
        "01": {"casilleros": {"411": 0, "412": 0, "419": 717710.66,
                              "421": 0, "429": 107656.60, "480": 568191.02}}
    }
    result = dm6_iva.compute_from_months(month_data)
    assert len(result["rows"]) == 12
    enero = result["rows"][0]
    assert enero["mes"] == "Enero"
    assert enero["c411"] == 0
    assert enero["c419"] == 717710.66
```

- [ ] **Step 8.2: Implementar `dm6_iva.py`**

Mirror exactly the structure of `dm7_retenciones.py` but with F-104 casilleros:

```python
"""Cédula DM6 — IVA (extractor F-104)."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import pdfplumber

from backend.app.aud.obligaciones_fiscales.cedulas.dm7_retenciones import (
    MESES,
    _find_periodo,
    _find_casillero_value,
    _parse_money,
)

code = "DM6"

# Casilleros del F-104 relevantes para DM6 IVA
CASILLEROS_F104 = ["411", "412", "419", "421", "429", "480", "499", "529"]


def expected_inputs() -> list[str]:
    return ["f104"]


def extract_f104(pdf_bytes: bytes) -> dict | None:
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return None
    if not text.strip():
        return None
    periodo = _find_periodo(text)
    casilleros = {num: _find_casillero_value(text, num) for num in CASILLEROS_F104}
    return {"periodo": periodo, "casilleros": casilleros}


def compute_from_months(month_data: dict[str, dict]) -> dict:
    rows = []
    for i, mes in enumerate(MESES, start=1):
        key = f"{i:02d}"
        m = month_data.get(key, {})
        cas = m.get("casilleros", {}) if m else {}
        rows.append({
            "mes": mes,
            "c411": cas.get("411"),
            "c412": cas.get("412"),
            "c419": cas.get("419"),
            "c421": cas.get("421"),
            "c429": cas.get("429"),
            "c480": cas.get("480"),
            "c499": cas.get("499"),
            "c529": cas.get("529"),
            "has_data": bool(m),
        })
    return {"rows": rows, "total_months_with_data": sum(1 for r in rows if r["has_data"])}


def compute(inputs: dict[str, list[Path]]) -> dict:
    pdfs = inputs.get("f104", []) or []
    month_data: dict[str, dict] = {}
    errors: list[str] = []
    for path in pdfs:
        data = extract_f104(path.read_bytes())
        if data is None:
            errors.append(f"No se pudo parsear: {path.name}")
            continue
        periodo = data.get("periodo")
        if not periodo:
            errors.append(f"Sin período detectado: {path.name}")
            continue
        mes_key = periodo.split("/")[0]
        month_data[mes_key] = data
    out = compute_from_months(month_data)
    out["errors"] = errors
    return out
```

- [ ] **Step 8.3: Correr tests**

Run: `pytest tests/test_aud_of_cedula_dm6.py -v`
Expected: similar a DM7 — `compute_from_months` pasa, extract puede requerir ajuste de regex iterativo.

- [ ] **Step 8.4: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/cedulas/dm6_iva.py \
        tests/test_aud_of_cedula_dm6.py
git commit -m "feat(aud/of): add DM6 IVA cedula (F-104 extractor + transformer)"
```

---

## Task 9: Excel assembler (carga plantilla + escribe DM6/DM7)

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/excel_assembler.py`
- Test: `tests/test_aud_of_excel_assembler.py`

- [ ] **Step 9.1: Test del assembler (failing)**

Crear `tests/test_aud_of_excel_assembler.py`:

```python
"""Tests del excel_assembler que puebla la plantilla baked-in."""

import datetime
import io
from openpyxl import load_workbook

from backend.app.aud.obligaciones_fiscales import excel_assembler


def test_assemble_returns_bytes_of_valid_xlsx():
    dm6_data = {"rows": [{"mes": "Enero", "c411": 0, "c412": 0, "c419": 717710.66,
                          "c421": 0, "c429": 107656.60, "c480": 568191.02,
                          "c499": None, "c529": None, "has_data": True}] +
                        [{"mes": m, "c411": None, "c412": None, "c419": None,
                          "c421": None, "c429": None, "c480": None, "c499": None,
                          "c529": None, "has_data": False}
                         for m in ["Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                   "Julio", "Agosto", "Septiembre", "Octubre",
                                   "Noviembre", "Diciembre"]]}
    dm7_data = {"rows": [{"mes": "Enero", "c721": 8594.74, "c723": 25.41,
                          "c725": 304.62, "c727": 0, "c729": 997.3, "c731": 37.5,
                          "c799": 9959.57, "has_data": True}] +
                        [{"mes": m, "c721": None, "c723": None, "c725": None,
                          "c727": None, "c729": None, "c731": None, "c799": None,
                          "has_data": False}
                         for m in ["Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                   "Julio", "Agosto", "Septiembre", "Octubre",
                                   "Noviembre", "Diciembre"]]}

    out = excel_assembler.assemble(
        cliente_name="EMPRESA TEST S.A.",
        period_label="Ejercicio 2025",
        period_end=datetime.date(2025, 12, 31),
        prepared_by_name="JC",
        reviewed_by_name="AU",
        dm6_data=dm6_data,
        dm7_data=dm7_data,
    )
    assert isinstance(out, bytes)
    wb = load_workbook(io.BytesIO(out))
    assert "DM6 IVA" in wb.sheetnames
    assert "DM7 Retenciones x pagar" in wb.sheetnames


def test_assembled_dm7_enero_row_has_casilleros():
    dm6_data = {"rows": [{"mes": m, "c411": None, "c412": None, "c419": None,
                          "c421": None, "c429": None, "c480": None, "c499": None,
                          "c529": None, "has_data": False}
                         for m in ["Enero", "Febrero", "Marzo", "Abril", "Mayo",
                                   "Junio", "Julio", "Agosto", "Septiembre",
                                   "Octubre", "Noviembre", "Diciembre"]]}
    dm7_data = {"rows": [{"mes": "Enero", "c721": 1000.50, "c723": 200.25,
                          "c725": 50.0, "c727": 10.0, "c729": 20.0, "c731": 5.0,
                          "c799": 1285.75, "has_data": True}] +
                        [{"mes": m, "c721": None, "c723": None, "c725": None,
                          "c727": None, "c729": None, "c731": None, "c799": None,
                          "has_data": False}
                         for m in ["Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                   "Julio", "Agosto", "Septiembre", "Octubre",
                                   "Noviembre", "Diciembre"]]}
    out = excel_assembler.assemble(
        cliente_name="X", period_label="2025", period_end=None,
        prepared_by_name=None, reviewed_by_name=None,
        dm6_data=dm6_data, dm7_data=dm7_data,
    )
    wb = load_workbook(io.BytesIO(out))
    dm7 = wb["DM7 Retenciones x pagar"]
    # Enero está en fila 21
    assert dm7["H21"].value == 1000.50  # casillero 721
    assert dm7["I21"].value == 200.25   # casillero 723
```

- [ ] **Step 9.2: Implementar `excel_assembler.py`**

Crear `backend/app/aud/obligaciones_fiscales/excel_assembler.py`:

```python
"""Carga la plantilla baked-in y la puebla con los datos calculados."""

from __future__ import annotations

import datetime
import io
from pathlib import Path

from openpyxl import load_workbook

TEMPLATE_PATH = Path(__file__).parent / "templates" / "dm_obligaciones_fiscales.xlsx"


# Mapping mes -> fila por hoja
DM6_FIRST_ROW = 20    # Enero
DM7_FIRST_ROW = 21    # Enero
MONTHS_COUNT = 12

# Columnas a poblar en DM6 (índices 1-based)
DM6_COLS = {
    "c411": 3,    # C — Ventas netas tarifa 0% (con derecho)
    "c412": 4,    # D — Ventas netas tarifa 0% (sin derecho)
    "c421": 5,    # E — Exportaciones
}

# Columnas a poblar en DM7 (índices 1-based)
DM7_COLS = {
    "c721": 8,    # H
    "c723": 9,    # I
    "c725": 10,   # J
    "c729": 11,   # K
    "c731": 12,   # L
    "c727": 13,   # M (nota: orden no monotónico — sigue la plantilla)
}

# Hojas con encabezado de cliente/período
HEADER_SHEETS = [
    "DM  Programa de Auditoria",
    "DM1 Cuestionario de Auditoria ",
    "DM2 Cédula Sumaria",
    "DM3 Revisión de saldos",
    "DM4 Compras ",
    "DM5 Ventas ",
    "DM6 IVA",
    "DM7 Retenciones x pagar",
    "DM8 ATS",
    "DM9 Límite costos y gastos",
    "DM10 Hoja de hallazgos",
]


def assemble(
    *,
    cliente_name: str,
    period_label: str,
    period_end: datetime.date | None,
    prepared_by_name: str | None,
    reviewed_by_name: str | None,
    dm6_data: dict,
    dm7_data: dict,
) -> bytes:
    """Carga la plantilla, escribe encabezados + DM6 + DM7, devuelve bytes."""
    wb = load_workbook(TEMPLATE_PATH)

    # Encabezados (las celdas exactas pueden variar — ver Cell Mapping doc)
    for name in HEADER_SHEETS:
        if name not in wb.sheetnames:
            continue
        ws = wb[name]
        # B6/D6 patterns observados en plantilla: cliente en col A o B fila 5/6
        # depende de la cédula. Se hace best-effort tolerante.
        _try_write(ws, "A5", cliente_name)
        _try_write(ws, "B5", cliente_name)
        if period_end:
            _try_write(ws, "D5", period_end)
        _try_write(ws, "A7", prepared_by_name or "")
        _try_write(ws, "A9", reviewed_by_name or "")

    # Poblar DM7 Retenciones
    if "DM7 Retenciones x pagar" in wb.sheetnames:
        ws = wb["DM7 Retenciones x pagar"]
        for i, row_data in enumerate(dm7_data.get("rows", [])):
            excel_row = DM7_FIRST_ROW + i
            for key, col in DM7_COLS.items():
                v = row_data.get(key)
                if v is not None:
                    ws.cell(row=excel_row, column=col, value=v)

    # Poblar DM6 IVA
    if "DM6 IVA" in wb.sheetnames:
        ws = wb["DM6 IVA"]
        for i, row_data in enumerate(dm6_data.get("rows", [])):
            excel_row = DM6_FIRST_ROW + i
            for key, col in DM6_COLS.items():
                v = row_data.get(key)
                if v is not None:
                    ws.cell(row=excel_row, column=col, value=v)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _try_write(ws, coord: str, value) -> None:
    """Escribe si la celda existe; ignora errores."""
    try:
        ws[coord] = value
    except Exception:
        pass
```

- [ ] **Step 9.3: Correr tests**

Run: `pytest tests/test_aud_of_excel_assembler.py -v`
Expected: 2 PASS.

- [ ] **Step 9.4: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/excel_assembler.py tests/test_aud_of_excel_assembler.py
git commit -m "feat(aud/of): add excel_assembler that loads baked-in template and populates DM6/DM7"
```

---

## Task 10: Job orchestrator + service

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/jobs.py`
- Create: `backend/app/aud/obligaciones_fiscales/service.py`
- Test: `tests/test_aud_of_service.py`

- [ ] **Step 10.1: Implementar `service.py`**

```python
"""Service layer: CRUD de ToolJob + autorización multi-tenant."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.context import service as ctx_service
from backend.app.context.models import Project
from backend.app.core.config import settings

TOOL_CODE = "AUD.IMPUESTOS.OBLIGACIONES_FISCALES"


def _ensure_project_access(db: Session, user, project_id: int) -> Project:
    proj = db.get(Project, project_id)
    if not proj or not ctx_service.user_can_access_project(db, user, proj):
        raise PermissionError("Sin acceso al proyecto.")
    return proj


def create_job(
    db: Session,
    *,
    user,
    project_id: int,
    cliente_name: str,
    period_label: str,
    period_start: datetime.date | None = None,
    period_end: datetime.date | None = None,
    prepared_by_name: str | None = None,
    reviewed_by_name: str | None = None,
) -> ToolJob:
    _ensure_project_access(db, user, project_id)
    now = datetime.datetime.utcnow()
    job = ToolJob(
        user_id=user.id,
        project_id=project_id,
        tool_code=TOOL_CODE,
        status="pending",
        cliente_name=cliente_name,
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        prepared_by_name=prepared_by_name,
        reviewed_by_name=reviewed_by_name,
        created_at=now,
        expires_at=now + datetime.timedelta(minutes=settings.AUD_OF_JOB_TTL_MINUTES),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, user, job_id: int) -> ToolJob:
    job = db.get(ToolJob, job_id)
    if not job:
        raise PermissionError("Job no encontrado.")
    _ensure_project_access(db, user, job.project_id)
    return job


def list_jobs_for_project(db: Session, user, project_id: int, limit: int = 20) -> list[ToolJob]:
    _ensure_project_access(db, user, project_id)
    return list(
        db.execute(
            select(ToolJob)
            .where(ToolJob.project_id == project_id, ToolJob.tool_code == TOOL_CODE)
            .order_by(ToolJob.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def mark_running(db: Session, job_id: int) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = "running"
        db.add(job)
        db.commit()


def mark_done(db: Session, job_id: int, summary: dict) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = "done"
        job.finished_at = datetime.datetime.utcnow()
        job.summary_json = summary
        db.add(job)
        db.commit()


def mark_failed(db: Session, job_id: int, error_message: str) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = "failed"
        job.finished_at = datetime.datetime.utcnow()
        job.error_message = error_message
        db.add(job)
        db.commit()


def mark_downloaded(db: Session, job_id: int) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.downloaded_at = datetime.datetime.utcnow()
        db.add(job)
        db.commit()
```

- [ ] **Step 10.2: Implementar `jobs.py` (orquestador)**

```python
"""BackgroundTask orquestador del job de generación del Excel."""

from __future__ import annotations

import datetime
import logging

from backend.app.aud.obligaciones_fiscales import (
    excel_assembler,
    file_storage,
    service,
)
from backend.app.aud.obligaciones_fiscales.cedulas import dm6_iva, dm7_retenciones
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)


def process_job(job_id: int) -> None:
    """Procesa un job: lee inputs de /tmp, computa cédulas, escribe output.xlsx."""
    db = SessionLocal()
    try:
        service.mark_running(db, job_id)
        job_dir = file_storage.job_dir(job_id)

        # Recolectar inputs por slot
        inputs = {
            "f103": file_storage.list_inputs(job_dir, "f103"),
            "f104": file_storage.list_inputs(job_dir, "f104"),
        }

        # Computar cédulas
        dm6_result = dm6_iva.compute(inputs)
        dm7_result = dm7_retenciones.compute(inputs)

        # Obtener metadata del job
        job = service.get_job_for_processing(db, job_id) if hasattr(service, "get_job_for_processing") else db.get(_job_model(), job_id)
        excel_bytes = excel_assembler.assemble(
            cliente_name=job.cliente_name,
            period_label=job.period_label,
            period_end=job.period_end,
            prepared_by_name=job.prepared_by_name,
            reviewed_by_name=job.reviewed_by_name,
            dm6_data=dm6_result,
            dm7_data=dm7_result,
        )

        out = file_storage.output_path(job_dir)
        out.write_bytes(excel_bytes)

        summary = {
            "dm6_months_with_data": dm6_result.get("total_months_with_data", 0),
            "dm7_months_with_data": dm7_result.get("total_months_with_data", 0),
            "errors": {
                "dm6": dm6_result.get("errors", []),
                "dm7": dm7_result.get("errors", []),
            },
        }
        service.mark_done(db, job_id, summary)
    except Exception as e:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        service.mark_failed(db, job_id, str(e)[:1000])
    finally:
        db.close()


def _job_model():
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    return ToolJob
```

- [ ] **Step 10.3: Test del service**

Crear `tests/test_aud_of_service.py`:

```python
"""Tests del service layer."""

import datetime
import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.aud.obligaciones_fiscales import service as of_service
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _mk_admin_project():
    db = SessionLocal()
    try:
        email = f"a-{uuid.uuid4().hex[:6]}@ex.com"
        u = auth_service.create_user(db, email=email, password="Sup3rSecret!", role=Role.admin)
        u = ctx_service.ensure_user_has_organization(db, u)
        c = ctx_service.create_client(db, organization_id=u.organization_id, name="C")
        p = ctx_service.create_project(
            db, organization_id=u.organization_id, client_id=c.id,
            name="Aud 2025", module_code="AUD",
        )
        ctx_service.add_project_member(db, p.id, u.id, "lead")
        return u.id, p.id
    finally:
        db.close()


def test_create_job_pending():
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        user = db.get(auth_service.User, user_id)
        job = of_service.create_job(
            db, user=user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        assert job.id is not None
        assert job.status == "pending"
        assert job.expires_at > job.created_at
    finally:
        db.close()


def test_create_job_no_access_raises():
    _, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        other = auth_service.create_user(
            db, email=f"o-{uuid.uuid4().hex[:6]}@ex.com",
            password="Sup3rSecret!", role=Role.user,
        )
        other = ctx_service.ensure_user_has_organization(db, other)
        with pytest.raises(PermissionError):
            of_service.create_job(
                db, user=other, project_id=project_id,
                cliente_name="C", period_label="2025",
            )
    finally:
        db.close()


def test_mark_done_updates_status_and_summary():
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        user = db.get(auth_service.User, user_id)
        job = of_service.create_job(
            db, user=user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        of_service.mark_done(db, job.id, {"x": 1})
        reloaded = db.get(of_service.ToolJob if hasattr(of_service, "ToolJob") else _import_tooljob(), job.id)
        assert reloaded.status == "done"
        assert reloaded.summary_json == {"x": 1}
    finally:
        db.close()


def _import_tooljob():
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    return ToolJob
```

- [ ] **Step 10.4: Correr tests**

Run: `pytest tests/test_aud_of_service.py -v`
Expected: 3 PASS.

- [ ] **Step 10.5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/service.py \
        backend/app/aud/obligaciones_fiscales/jobs.py \
        tests/test_aud_of_service.py
git commit -m "feat(aud/of): add service layer + BackgroundTask orchestrator"
```

---

## Task 11: Router HTTP

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/router.py`
- Modify: `backend/app/api/__init__.py`
- Test: `tests/test_aud_of_router.py`

- [ ] **Step 11.1: Implementar `router.py`**

```python
"""Endpoints HTTP de AUD.IMPUESTOS.OBLIGACIONES_FISCALES."""

from __future__ import annotations

import datetime
from io import BytesIO

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.aud.obligaciones_fiscales import (
    file_storage,
    jobs,
    service,
)
from backend.app.aud.obligaciones_fiscales.schemas import JobOut
from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(
    prefix="/aud/obligaciones-fiscales",
    tags=["aud-obligaciones-fiscales"],
)


ALLOWED_MIMES = {
    "f103": {"application/pdf"},
    "f104": {"application/pdf"},
    "f101": {"application/pdf"},
    "ats": {"application/xml", "text/xml"},
    "mayor_compras": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    },
    "mayor_ventas": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    },
}


async def _save_files(job_dir, slot: str, files: list[UploadFile]) -> int:
    """Valida y guarda. Devuelve cantidad guardada. Raises HTTPException."""
    allowed = ALLOWED_MIMES.get(slot, set())
    max_bytes = settings.AUD_OF_MAX_FILE_MB * 1024 * 1024
    count = 0
    for f in files:
        if not f.filename:
            continue
        if allowed and f.content_type not in allowed:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"{f.filename}: tipo {f.content_type} no permitido para slot {slot}",
            )
        data = await f.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{f.filename}: excede {settings.AUD_OF_MAX_FILE_MB} MB",
            )
        file_storage.save_input(job_dir, slot, f.filename, data)
        count += 1
    return count


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job_endpoint(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    cliente_name: str = Form(...),
    period_label: str = Form(...),
    period_start: datetime.date | None = Form(None),
    period_end: datetime.date | None = Form(None),
    prepared_by_name: str | None = Form(None),
    reviewed_by_name: str | None = Form(None),
    files_f103: list[UploadFile] = File(default=[]),
    files_f104: list[UploadFile] = File(default=[]),
    files_ats: list[UploadFile] = File(default=[]),
    mayor_compras: UploadFile | None = File(None),
    mayor_ventas: UploadFile | None = File(None),
    file_f101: UploadFile | None = File(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validación mínima
    if not (files_f103 or files_f104):
        raise HTTPException(400, detail="Sube al menos 1 PDF F-103 o F-104.")

    try:
        job = service.create_job(
            db, user=current, project_id=project_id,
            cliente_name=cliente_name, period_label=period_label,
            period_start=period_start, period_end=period_end,
            prepared_by_name=prepared_by_name, reviewed_by_name=reviewed_by_name,
        )
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    # Guardar archivos en /tmp
    job_dir = file_storage.create_job_dir(job.id)
    if files_f103:
        await _save_files(job_dir, "f103", files_f103)
    if files_f104:
        await _save_files(job_dir, "f104", files_f104)
    if files_ats:
        await _save_files(job_dir, "ats", files_ats)
    if mayor_compras:
        await _save_files(job_dir, "mayor_compras", [mayor_compras])
    if mayor_ventas:
        await _save_files(job_dir, "mayor_ventas", [mayor_ventas])
    if file_f101:
        await _save_files(job_dir, "f101", [file_f101])

    # Dispatch background processing
    background_tasks.add_task(jobs.process_job, job.id)

    return JobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return JobOut.model_validate(job)


@router.get("/jobs")
def list_jobs_endpoint(
    project_id: int,
    limit: int = 20,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        items = service.list_jobs_for_project(db, current, project_id, limit=limit)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return [JobOut.model_validate(i) for i in items]


@router.get("/jobs/{job_id}/download")
def download_job_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status != "done":
        raise HTTPException(409, detail=f"Job status={job.status}, no listo para descarga")
    out_path = file_storage.output_path(file_storage.job_dir(job.id))
    if not out_path.exists():
        raise HTTPException(410, detail="Excel ya no disponible (expirado).")
    service.mark_downloaded(db, job.id)
    return StreamingResponse(
        BytesIO(out_path.read_bytes()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="DM_Obligaciones_Fiscales_{job.cliente_name.replace(" ", "_")}_{job.period_label.replace(" ", "_")}.xlsx"'
        },
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    file_storage.delete_job_dir(job.id)
    db.delete(job)
    db.commit()
    return None
```

- [ ] **Step 11.2: Registrar router en `backend/app/api/__init__.py`**

Agregar el import y el `include_router`:

```python
from backend.app.aud.obligaciones_fiscales import router as aud_of_router
...
api_router.include_router(aud_of_router.router)
```

- [ ] **Step 11.3: Tests del router**

Crear `tests/test_aud_of_router.py`:

```python
"""Tests de los endpoints HTTP."""

import uuid
from pathlib import Path

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db

FIXTURES = Path(__file__).parent / "fixtures" / "obligaciones_fiscales"


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _mk_user(role=Role.user):
    email = f"u-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    return email, pw


def _login(client, email, pw):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _mk_admin_project(client):
    email, pw = _mk_user(Role.admin)
    tok = _login(client, email, pw)
    r = client.post("/api/v1/context/clients", headers=_h(tok), json={"name": "C"})
    cid = r.json()["id"]
    r = client.post(
        "/api/v1/context/projects", headers=_h(tok),
        json={"client_id": cid, "name": "P", "module_code": "AUD"},
    )
    return tok, r.json()["id"]


def test_create_job_requires_files(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
        files=[],
    )
    assert r.status_code == 400


def test_create_job_with_f103_returns_201(client):
    tok, pid = _mk_admin_project(client)
    pdf_bytes = (FIXTURES / "f103_enero.pdf").read_bytes()
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
        files=[("files_f103", ("f103.pdf", pdf_bytes, "application/pdf"))],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] in ("pending", "running", "done")
    assert body["project_id"] == pid


def test_list_jobs_filters_by_project(client):
    tok, pid = _mk_admin_project(client)
    pdf_bytes = (FIXTURES / "f103_enero.pdf").read_bytes()
    for _ in range(2):
        client.post(
            "/api/v1/aud/obligaciones-fiscales/jobs",
            headers=_h(tok),
            data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
            files=[("files_f103", ("f103.pdf", pdf_bytes, "application/pdf"))],
        )
    r = client.get(
        f"/api/v1/aud/obligaciones-fiscales/jobs?project_id={pid}",
        headers=_h(tok),
    )
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_user_without_project_access_403(client):
    tok_admin, pid = _mk_admin_project(client)
    email, pw = _mk_user(Role.user)
    tok = _login(client, email, pw)
    pdf_bytes = (FIXTURES / "f103_enero.pdf").read_bytes()
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
        files=[("files_f103", ("f103.pdf", pdf_bytes, "application/pdf"))],
    )
    assert r.status_code == 403
```

- [ ] **Step 11.4: Correr tests**

Run: `pytest tests/test_aud_of_router.py -v`
Expected: 4 PASS.

- [ ] **Step 11.5: Correr suite completa**

Run: `pytest -v`
Expected: TODOS PASAN (existentes + nuevos).

- [ ] **Step 11.6: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/router.py \
        backend/app/api/__init__.py \
        tests/test_aud_of_router.py
git commit -m "feat(aud/of): add HTTP endpoints (jobs CRUD + download) + register router"
```

---

## Task 12: Cleanup periódico

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/cleanup.py`
- Modify: `app.py` (startup hook)
- Test: `tests/test_aud_of_cleanup.py`

- [ ] **Step 12.1: Implementar `cleanup.py`**

```python
"""Cleanup periódico de jobs expirados y carpetas /tmp huérfanas."""

from __future__ import annotations

import asyncio
import datetime
import logging

from sqlalchemy import select

from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)


def cleanup_once() -> dict:
    """Una pasada de cleanup. Devuelve resumen."""
    now = datetime.datetime.utcnow()
    summary = {"expired_jobs": 0, "post_download_cleanups": 0, "orphan_dirs": 0}

    db = SessionLocal()
    try:
        # 1. Jobs expirados por TTL
        expired = db.execute(
            select(ToolJob).where(
                ToolJob.expires_at < now,
                ToolJob.status.in_(["pending", "running", "done"]),
            )
        ).scalars().all()
        for j in expired:
            file_storage.delete_job_dir(j.id)
            j.status = "expired"
            db.add(j)
            summary["expired_jobs"] += 1

        # 2. Jobs descargados hace > N min
        post_dl_threshold = now - datetime.timedelta(
            minutes=settings.AUD_OF_POST_DOWNLOAD_TTL_MINUTES
        )
        downloaded_old = db.execute(
            select(ToolJob).where(
                ToolJob.downloaded_at.is_not(None),
                ToolJob.downloaded_at < post_dl_threshold,
                ToolJob.status == "done",
            )
        ).scalars().all()
        for j in downloaded_old:
            file_storage.delete_job_dir(j.id)
            summary["post_download_cleanups"] += 1

        db.commit()
    finally:
        db.close()

    # 3. Directorios huérfanos en disco (que no tienen registro en DB)
    orphans = file_storage.list_orphan_job_dirs(
        max_age_seconds=settings.AUD_OF_JOB_TTL_MINUTES * 60
    )
    for d in orphans:
        try:
            file_storage.delete_job_dir(int(d.name))
            summary["orphan_dirs"] += 1
        except Exception:
            pass

    return summary


async def cleanup_loop() -> None:
    """Loop infinito que ejecuta cleanup cada X segundos."""
    interval = settings.AUD_OF_CLEANUP_INTERVAL_SECONDS
    while True:
        try:
            s = cleanup_once()
            if any(s.values()):
                log.info("aud_of cleanup: %s", s)
        except Exception:
            log.exception("cleanup failed")
        await asyncio.sleep(interval)
```

- [ ] **Step 12.2: Disparar cleanup en startup de `app.py`**

Abrir `app.py` y agregar en el bloque de startup events de FastAPI (buscar donde se hace `@app.on_event("startup")` o similar; si no existe, agregar):

```python
import asyncio
import contextlib

# ... después del montaje de api_router defensivo ...

with contextlib.suppress(Exception):
    from backend.app.aud.obligaciones_fiscales import cleanup as _aud_of_cleanup

    @app.on_event("startup")
    async def _start_aud_of_cleanup():
        asyncio.create_task(_aud_of_cleanup.cleanup_loop())
```

(`contextlib.suppress(Exception)` mantiene la filosofía aditiva: si el módulo falla, el resto sigue funcionando.)

- [ ] **Step 12.3: Test del cleanup**

Crear `tests/test_aud_of_cleanup.py`:

```python
"""Tests de cleanup periódico."""

import datetime
import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.aud.obligaciones_fiscales import cleanup, file_storage, service
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload
    from backend.app.core import config
    reload(config)
    reload(file_storage)
    init_db()
    yield


def _mk_admin_project():
    db = SessionLocal()
    try:
        email = f"a-{uuid.uuid4().hex[:6]}@ex.com"
        u = auth_service.create_user(db, email=email, password="Sup3rSecret!", role=Role.admin)
        u = ctx_service.ensure_user_has_organization(db, u)
        c = ctx_service.create_client(db, organization_id=u.organization_id, name="C")
        p = ctx_service.create_project(
            db, organization_id=u.organization_id, client_id=c.id,
            name="P", module_code="AUD",
        )
        ctx_service.add_project_member(db, p.id, u.id, "lead")
        return u, p.id
    finally:
        db.close()


def test_cleanup_marks_expired_jobs():
    user, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        job = service.create_job(
            db, user=user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        # Forzar expires_at en el pasado
        job.expires_at = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        db.add(job)
        db.commit()
        file_storage.create_job_dir(job.id)
        summary = cleanup.cleanup_once()
        assert summary["expired_jobs"] >= 1
        reloaded = db.get(ToolJob, job.id)
        assert reloaded.status == "expired"
    finally:
        db.close()
```

- [ ] **Step 12.4: Correr tests**

Run: `pytest tests/test_aud_of_cleanup.py -v`
Expected: 1 PASS.

- [ ] **Step 12.5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/cleanup.py app.py tests/test_aud_of_cleanup.py
git commit -m "feat(aud/of): add periodic cleanup of expired jobs and orphan tmp dirs"
```

---

## Task 13: Frontend — catálogo de categorías

**Files:**
- Create: `frontend/src/aud/catalog.js`
- Create: `frontend/src/aud/strings.js`
- Create: `frontend/src/aud/ToolCatalog.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 13.1: Crear `catalog.js`**

```javascript
// frontend/src/aud/catalog.js

export const CATEGORIES = [
  { id: "PLANIFICACION", label: "Planificación", type: "etapa" },
  { id: "CAJA_BANCOS", label: "Caja y bancos", type: "ciclo" },
  { id: "INVERSIONES", label: "Inversiones", type: "ciclo" },
  { id: "CXC", label: "Cuentas por cobrar", type: "ciclo" },
  { id: "INVENTARIOS", label: "Inventarios", type: "ciclo" },
  { id: "ACTIVOS_FIJOS", label: "Activos fijos", type: "ciclo" },
  { id: "INTANGIBLES", label: "Activos intangibles e impuestos diferidos", type: "ciclo" },
  { id: "PROVEEDORES", label: "Proveedores y cuentas por pagar", type: "ciclo" },
  { id: "PRESTAMOS", label: "Préstamos y obligaciones financieras", type: "ciclo" },
  { id: "PATRIMONIO", label: "Patrimonio", type: "ciclo" },
  { id: "INGRESOS", label: "Ingresos", type: "resultados" },
  { id: "COSTOS_GASTOS", label: "Costos y gastos", type: "resultados" },
  { id: "NOMINA", label: "Nómina", type: "resultados" },
  {
    id: "IMPUESTOS", label: "Impuestos", type: "cumplimiento",
    tools: [
      {
        id: "AUD.IMPUESTOS.OBLIGACIONES_FISCALES",
        label: "Auditoría de Obligaciones Fiscales",
        description: "Genera el papel de trabajo DM Obligaciones Fiscales a partir de F-103, F-104, ATS y mayores."
      },
    ],
  },
  { id: "CONCLUSION", label: "Conclusión y dictamen", type: "etapa" },
];
```

- [ ] **Step 13.2: Crear `strings.js`**

```javascript
// frontend/src/aud/strings.js
// Strings centralizadas para facilitar i18n futura.

export const STRINGS = {
  catalog_title: "Pruebas de auditoría a través de herramientas",
  coming_soon: "Próximamente",
  no_tools_yet: "Sin herramientas activas todavía",
  back_to_catalog: "← Volver al catálogo",

  // Obligaciones Fiscales
  of_title: "Auditoría de Obligaciones Fiscales",
  of_subtitle: "Sube tus PDFs y mayores, descarga el papel de trabajo Excel",
  of_form_cliente: "Cliente auditado",
  of_form_periodo: "Período (ej: Ejercicio 2025)",
  of_form_period_end: "Fecha de corte",
  of_form_prepared_by: "Preparado por (opcional)",
  of_form_reviewed_by: "Revisado por (opcional)",
  of_slot_f103: "Retenciones en la fuente (F-103) — 12 PDFs",
  of_slot_f104: "IVA (F-104) — 12 PDFs",
  of_slot_ats: "Anexo Transaccional (ATS) — 12 XMLs",
  of_slot_mayor_compras: "Mayor de Compras (Excel)",
  of_slot_mayor_ventas: "Mayor de Ventas (Excel)",
  of_slot_f101: "Declaración de Renta (F-101) — PDF anual",
  of_generate: "Generar papel de trabajo",
  of_processing: "Procesando...",
  of_done: "Listo para descargar",
  of_download: "Descargar Excel",
  of_failed: "Falló",
  of_new: "Nuevo papel de trabajo",
  of_recent: "Generados recientemente (últimas 24h)",
};
```

- [ ] **Step 13.3: Crear `ToolCatalog.jsx`**

```jsx
import { useState } from "react";
import { CATEGORIES } from "./catalog.js";
import { STRINGS } from "./strings.js";
import ObligacionesFiscalesTool from "./ObligacionesFiscalesTool.jsx";

export default function ToolCatalog({ projectId }) {
  const [activeTool, setActiveTool] = useState(null);

  if (activeTool === "AUD.IMPUESTOS.OBLIGACIONES_FISCALES") {
    return (
      <div className="aud-tool-wrap">
        <button className="link aud-back" onClick={() => setActiveTool(null)}>
          {STRINGS.back_to_catalog}
        </button>
        <ObligacionesFiscalesTool projectId={projectId} />
      </div>
    );
  }

  return (
    <div className="aud-catalog">
      <h2>{STRINGS.catalog_title}</h2>
      <div className="aud-cat-grid">
        {CATEGORIES.map((cat) => {
          const hasTools = cat.tools && cat.tools.length > 0;
          return (
            <div key={cat.id} className={`aud-cat-card ${!hasTools ? "soon" : "active"}`}>
              <div className="aud-cat-h">
                <span className="aud-cat-type">{cat.type}</span>
                <h3>{cat.label}</h3>
              </div>
              {hasTools ? (
                <div className="aud-cat-tools">
                  {cat.tools.map((t) => (
                    <button
                      key={t.id}
                      className="aud-tool-item"
                      onClick={() => setActiveTool(t.id)}
                    >
                      <b>{t.label}</b>
                      <span>{t.description}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="aud-cat-soon">{STRINGS.coming_soon}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 13.4: Agregar estilos al final de `frontend/src/styles.css`**

```css
/* === AUD Tool Catalog === */
.aud-catalog { padding: 16px 0; }
.aud-catalog h2 { margin: 0 0 16px; }
.aud-cat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.aud-cat-card {
  border: 1px solid var(--border, #2a2f38);
  border-radius: 8px;
  padding: 14px;
  background: rgba(255,255,255,.02);
}
.aud-cat-card.soon { opacity: .55; }
.aud-cat-card.active { border-color: var(--accent, #6ea8fe); }
.aud-cat-h .aud-cat-type {
  font-size: 10px; text-transform: uppercase;
  color: var(--muted, #9aa3af);
  letter-spacing: .08em;
}
.aud-cat-h h3 { margin: 4px 0 10px; font-size: 15px; }
.aud-cat-soon {
  font-size: 12px; color: var(--muted, #9aa3af);
  padding: 8px; background: rgba(255,255,255,.04); border-radius: 4px;
  text-align: center;
}
.aud-tool-item {
  display: block; width: 100%; text-align: left;
  background: rgba(110,168,254,.08);
  border: 1px solid rgba(110,168,254,.2);
  border-radius: 6px; padding: 10px;
  color: inherit; cursor: pointer; margin-bottom: 6px;
}
.aud-tool-item:hover { background: rgba(110,168,254,.15); }
.aud-tool-item b { display: block; font-size: 13px; }
.aud-tool-item span { font-size: 11px; color: var(--muted, #9aa3af); }
.aud-back { display: inline-block; margin-bottom: 12px; font-size: 12px; }
```

- [ ] **Step 13.5: Verificar build (sin componente ObligacionesFiscalesTool aún, va a fallar import)**

Crear stub temporal `frontend/src/aud/ObligacionesFiscalesTool.jsx`:

```jsx
export default function ObligacionesFiscalesTool() {
  return <div>Próximamente (Task 14)</div>;
}
```

Run: `cd frontend && npm run build`
Expected: build pasa.

- [ ] **Step 13.6: Commit**

```bash
git add frontend/src/aud/catalog.js frontend/src/aud/strings.js \
        frontend/src/aud/ToolCatalog.jsx frontend/src/aud/ObligacionesFiscalesTool.jsx \
        frontend/src/styles.css
git commit -m "feat(frontend/aud): add ToolCatalog with 15 categories + strings + stub tool"
```

---

## Task 14: Frontend — herramienta principal `ObligacionesFiscalesTool`

**Files:**
- Replace stub: `frontend/src/aud/ObligacionesFiscalesTool.jsx`
- Modify: `frontend/src/api.js`

- [ ] **Step 14.1: Agregar métodos API en `api.js`**

Al final de `frontend/src/api.js` (o donde corresponda según convención local):

```javascript
// === AUD Obligaciones Fiscales ===

export async function createObligacionesFiscalesJob(form, files) {
  const fd = new FormData();
  Object.entries(form).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") fd.append(k, v);
  });
  (files.f103 || []).forEach((f) => fd.append("files_f103", f));
  (files.f104 || []).forEach((f) => fd.append("files_f104", f));
  (files.ats || []).forEach((f) => fd.append("files_ats", f));
  if (files.mayor_compras) fd.append("mayor_compras", files.mayor_compras);
  if (files.mayor_ventas) fd.append("mayor_ventas", files.mayor_ventas);
  if (files.f101) fd.append("file_f101", files.f101);

  const r = await fetch(`${getApiBase()}/api/v1/aud/obligaciones-fiscales/jobs`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` },
    body: fd,
  });
  if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
  return r.json();
}

export async function getObligacionesFiscalesJob(jobId) {
  const r = await fetch(
    `${getApiBase()}/api/v1/aud/obligaciones-fiscales/jobs/${jobId}`,
    { headers: { Authorization: `Bearer ${getToken()}` } }
  );
  if (!r.ok) throw new Error((await r.json()).detail || "Error consultando job");
  return r.json();
}

export async function listObligacionesFiscalesJobs(projectId) {
  const r = await fetch(
    `${getApiBase()}/api/v1/aud/obligaciones-fiscales/jobs?project_id=${projectId}`,
    { headers: { Authorization: `Bearer ${getToken()}` } }
  );
  if (!r.ok) throw new Error((await r.json()).detail || "Error listando jobs");
  return r.json();
}

export function obligacionesFiscalesDownloadUrl(jobId) {
  // No usamos fetch; el download es directo al endpoint
  return `${getApiBase()}/api/v1/aud/obligaciones-fiscales/jobs/${jobId}/download`;
}
```

> **Nota:** usa el patrón exacto de `getApiBase()` y `getToken()` que ya existe en `api.js`. Si son nombres distintos, ajustar.

- [ ] **Step 14.2: Reemplazar el stub `ObligacionesFiscalesTool.jsx`**

```jsx
import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "../api.js";
import { STRINGS } from "./strings.js";

const SLOTS = [
  { key: "f103", label: STRINGS.of_slot_f103, accept: "application/pdf", multiple: true },
  { key: "f104", label: STRINGS.of_slot_f104, accept: "application/pdf", multiple: true },
  { key: "ats", label: STRINGS.of_slot_ats, accept: ".xml,application/xml", multiple: true },
  { key: "mayor_compras", label: STRINGS.of_slot_mayor_compras, accept: ".xlsx,.xls", multiple: false },
  { key: "mayor_ventas", label: STRINGS.of_slot_mayor_ventas, accept: ".xlsx,.xls", multiple: false },
  { key: "f101", label: STRINGS.of_slot_f101, accept: "application/pdf", multiple: false },
];

export default function ObligacionesFiscalesTool({ projectId }) {
  const [stage, setStage] = useState("form"); // form | processing | done | failed
  const [form, setForm] = useState({
    cliente_name: "", period_label: "",
    period_start: "", period_end: "",
    prepared_by_name: "", reviewed_by_name: "",
  });
  const [files, setFiles] = useState({});
  const [job, setJob] = useState(null);
  const [recent, setRecent] = useState([]);
  const [err, setErr] = useState("");
  const pollRef = useRef();

  const loadRecent = useCallback(async () => {
    if (!projectId) return;
    try { setRecent(await api.listObligacionesFiscalesJobs(projectId)); }
    catch (e) { setErr(e.message); }
  }, [projectId]);

  useEffect(() => { loadRecent(); }, [loadRecent]);

  useEffect(() => () => clearInterval(pollRef.current), []);

  function setFilesForSlot(slot, fileList) {
    setFiles((prev) => ({ ...prev, [slot]: Array.from(fileList || []) }));
  }

  async function submit(e) {
    e.preventDefault();
    setErr("");
    if (!(files.f103?.length || files.f104?.length)) {
      setErr("Sube al menos 1 PDF F-103 o F-104.");
      return;
    }
    try {
      // Mapear archivos al formato esperado por createObligacionesFiscalesJob
      const fileMap = {
        f103: files.f103,
        f104: files.f104,
        ats: files.ats,
        mayor_compras: files.mayor_compras?.[0],
        mayor_ventas: files.mayor_ventas?.[0],
        f101: files.f101?.[0],
      };
      const j = await api.createObligacionesFiscalesJob(
        { project_id: projectId, ...form }, fileMap
      );
      setJob(j);
      setStage("processing");
      pollRef.current = setInterval(async () => {
        try {
          const updated = await api.getObligacionesFiscalesJob(j.id);
          setJob(updated);
          if (updated.status === "done") {
            clearInterval(pollRef.current);
            setStage("done");
            loadRecent();
          } else if (updated.status === "failed" || updated.status === "expired") {
            clearInterval(pollRef.current);
            setStage("failed");
          }
        } catch (e) { /* sigue intentando */ }
      }, 2000);
    } catch (e) {
      setErr(e.message);
    }
  }

  function reset() {
    setStage("form");
    setJob(null);
    setFiles({});
    setForm({ cliente_name: "", period_label: "", period_start: "",
              period_end: "", prepared_by_name: "", reviewed_by_name: "" });
    setErr("");
  }

  if (!projectId) {
    return <div className="notice warn">Selecciona un proyecto del módulo AUD primero.</div>;
  }

  return (
    <div className="of-tool">
      <header className="of-head">
        <h2>{STRINGS.of_title}</h2>
        <p className="muted">{STRINGS.of_subtitle}</p>
      </header>

      {stage === "form" && (
        <form onSubmit={submit} className="of-form">
          <div className="of-form-row">
            <label>{STRINGS.of_form_cliente}*
              <input value={form.cliente_name} required
                onChange={(e) => setForm({ ...form, cliente_name: e.target.value })} />
            </label>
            <label>{STRINGS.of_form_periodo}*
              <input value={form.period_label} required
                onChange={(e) => setForm({ ...form, period_label: e.target.value })} />
            </label>
          </div>
          <div className="of-form-row">
            <label>{STRINGS.of_form_period_end}
              <input type="date" value={form.period_end}
                onChange={(e) => setForm({ ...form, period_end: e.target.value })} />
            </label>
            <label>{STRINGS.of_form_prepared_by}
              <input value={form.prepared_by_name}
                onChange={(e) => setForm({ ...form, prepared_by_name: e.target.value })} />
            </label>
            <label>{STRINGS.of_form_reviewed_by}
              <input value={form.reviewed_by_name}
                onChange={(e) => setForm({ ...form, reviewed_by_name: e.target.value })} />
            </label>
          </div>

          <div className="of-slots">
            {SLOTS.map((s) => (
              <div key={s.key} className="of-slot">
                <label>
                  {s.label}
                  <input
                    type="file"
                    accept={s.accept}
                    multiple={s.multiple}
                    onChange={(e) => setFilesForSlot(s.key, e.target.files)}
                  />
                </label>
                {files[s.key]?.length > 0 && (
                  <span className="of-slot-count">{files[s.key].length} archivo(s)</span>
                )}
              </div>
            ))}
          </div>

          {err && <div className="err">{err}</div>}
          <button type="submit" className="btn primary lg">{STRINGS.of_generate}</button>
        </form>
      )}

      {stage === "processing" && (
        <div className="of-stage">
          <div className="spinner" />
          <h3>{STRINGS.of_processing}</h3>
          <p className="muted">Job #{job?.id} · {job?.status}</p>
        </div>
      )}

      {stage === "done" && (
        <div className="of-stage">
          <h3>✅ {STRINGS.of_done}</h3>
          {job?.summary_json && (
            <pre className="of-summary">{JSON.stringify(job.summary_json, null, 2)}</pre>
          )}
          <div className="of-stage-actions">
            <a
              className="btn primary lg"
              href={api.obligacionesFiscalesDownloadUrl(job.id)}
              download
            >
              {STRINGS.of_download}
            </a>
            <button className="btn" onClick={reset}>{STRINGS.of_new}</button>
          </div>
        </div>
      )}

      {stage === "failed" && (
        <div className="of-stage">
          <h3>❌ {STRINGS.of_failed}</h3>
          <pre className="of-summary err">{job?.error_message || "Error desconocido"}</pre>
          <button className="btn" onClick={reset}>{STRINGS.of_new}</button>
        </div>
      )}

      {recent.length > 0 && stage === "form" && (
        <div className="of-recent">
          <h3>{STRINGS.of_recent}</h3>
          <ul>
            {recent.slice(0, 10).map((j) => (
              <li key={j.id}>
                #{j.id} · {j.cliente_name} · {j.period_label} ·
                <span className={`badge ${j.status}`}>{j.status}</span>
                {j.status === "done" && (
                  <a href={api.obligacionesFiscalesDownloadUrl(j.id)} download>
                    {" "}↓ descargar
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 14.3: Estilos finales en `frontend/src/styles.css`**

```css
/* === AUD Obligaciones Fiscales Tool === */
.of-tool { padding: 16px 0; max-width: 900px; }
.of-head h2 { margin: 0 0 4px; }
.of-form { display: flex; flex-direction: column; gap: 14px; margin-top: 20px; }
.of-form-row { display: flex; gap: 12px; flex-wrap: wrap; }
.of-form-row label { flex: 1; min-width: 200px; display: flex; flex-direction: column; font-size: 12px; gap: 4px; color: var(--muted); }
.of-form-row input { padding: 8px; border-radius: 4px; }
.of-slots { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; margin-top: 12px; }
.of-slot { border: 1px solid var(--border, #2a2f38); border-radius: 6px; padding: 10px; background: rgba(255,255,255,.02); }
.of-slot label { display: block; font-size: 12px; color: var(--muted); }
.of-slot input[type=file] { width: 100%; margin-top: 6px; }
.of-slot-count { font-size: 11px; color: var(--accent); }
.of-stage { padding: 40px 20px; text-align: center; }
.of-stage h3 { margin: 12px 0; }
.of-stage-actions { display: flex; justify-content: center; gap: 12px; margin-top: 20px; }
.of-summary { background: rgba(255,255,255,.04); padding: 12px; border-radius: 4px; text-align: left; font-size: 12px; max-width: 600px; margin: 12px auto; overflow-x: auto; }
.of-summary.err { color: #f87272; }
.of-recent { margin-top: 30px; padding-top: 20px; border-top: 1px solid var(--border, #2a2f38); }
.of-recent ul { list-style: none; padding: 0; }
.of-recent li { padding: 8px 0; font-size: 13px; border-bottom: 1px solid rgba(255,255,255,.04); }
.spinner { width: 40px; height: 40px; border: 3px solid rgba(255,255,255,.1); border-top-color: var(--accent, #6ea8fe); border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.btn.lg { padding: 12px 24px; font-size: 14px; }
```

- [ ] **Step 14.4: Verificar build**

Run: `cd frontend && npm run build`
Expected: build pasa.

- [ ] **Step 14.5: Commit**

```bash
git add frontend/src/aud/ObligacionesFiscalesTool.jsx frontend/src/api.js frontend/src/styles.css
git commit -m "feat(frontend/aud): full ObligacionesFiscalesTool with upload + polling + download"
```

---

## Task 15: Wire into `App.jsx`

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 15.1: Importar ToolCatalog**

Al inicio de `App.jsx`, junto a otros imports:

```jsx
import ToolCatalog from "./aud/ToolCatalog.jsx";
```

- [ ] **Step 15.2: Modificar el bloque de `CognitiveWorkspace` para tab "análisis" en AUD**

Localizar el bloque que renderiza según `tab` y agregar antes del bloque existente:

```jsx
{tab === "análisis" && module.id === "AUD" ? (
  <div className="cw-tool">
    <ToolCatalog projectId={ctx?.active_project?.id} />
  </div>
) : tab === "documentos" ? (
  <div className="cw-docs">
    <Documents embedded />
  </div>
) : (
  <div className="cw-stage">
    {/* contenido original */}
  </div>
)}
```

- [ ] **Step 15.3: Verificar build**

Run: `cd frontend && npm run build`
Expected: build pasa.

- [ ] **Step 15.4: Verificación dev local (opcional pero recomendado)**

En 2 terminales:
- T1: `uvicorn app:app --reload`
- T2: `cd frontend && npm run dev`

Abrir `http://localhost:5173`. Login. Crear cliente + proyecto AUD. Activar proyecto. Ir a AUD > Análisis. Ver el catálogo de 15 categorías. Click en Impuestos > "Auditoría de Obligaciones Fiscales". Ver el form. Subir un F-103. Click generar. Esperar a "done". Descargar Excel.

- [ ] **Step 15.5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(frontend): wire ToolCatalog into AUD module Análisis tab"
```

---

## Task 16: Checklist E2E + push

**Files:**
- Create: `docs/AUD_OF_M1_E2E.md`

- [ ] **Step 16.1: Crear checklist**

```markdown
# AUD Obligaciones Fiscales · M1 · Checklist E2E

## Pre-requisitos
- [ ] Render auto-deploy verde tras el merge
- [ ] Plantilla `dm_obligaciones_fiscales.xlsx` está en el repo
- [ ] init_db creó la tabla `tool_jobs` en producción

## Verificación funcional
1. [ ] Login con admin
2. [ ] WKS → crear cliente "Test Co" si no existe
3. [ ] WKS → crear proyecto "AUD 2025" con `module_code=AUD`
4. [ ] Activar el proyecto en el header
5. [ ] Ir al módulo AUD
6. [ ] Click tab "Análisis"
7. [ ] Ver el catálogo con 15 categorías (Impuestos con badge "activa")
8. [ ] Click "Impuestos" → "Auditoría de Obligaciones Fiscales"
9. [ ] Llenar form (cliente, período)
10. [ ] Subir 1 PDF F-103
11. [ ] Click "Generar papel de trabajo"
12. [ ] Ver spinner, status="running"
13. [ ] Tras ~30s, status="done"
14. [ ] Click "Descargar Excel"
15. [ ] Abrir el Excel: pestaña "DM7 Retenciones x pagar" tiene casilleros H/I/J... pobladas con valores del PDF de enero
16. [ ] El encabezado de las pestañas tiene el cliente y período del form

## Verificación de cleanup
- [ ] Esperar 1h sin descargar un job → status pasa a "expired"
- [ ] /tmp/auditbrain/obligaciones_fiscales/ queda limpio

## Verificación multi-tenant
- [ ] Crear admin en org distinta (vía SQL o segundo despliegue)
- [ ] Admin B no ve jobs de Admin A en `GET /jobs?project_id=X`
- [ ] Admin B accede a `GET /jobs/<id>` de Admin A → 403

## Criterio de éxito M1
Todo arriba en verde → M1 DONE. Continuar con M2 (resto de cédulas).
```

- [ ] **Step 16.2: Correr suite completa**

Run: `pytest -v`
Expected: TODOS PASAN.

- [ ] **Step 16.3: Build frontend**

Run: `cd frontend && npm run build`
Expected: build limpio.

- [ ] **Step 16.4: Push a branch + PR**

```bash
git checkout -b feat/aud-of-m1
git push -u origin feat/aud-of-m1
gh pr create --title "feat(aud/of): M1 — Obligaciones Fiscales ephemeral with DM6 IVA + DM7 Retenciones" --body "$(cat <<'EOF'
## Summary
- Implementa M1 del spec `docs/superpowers/specs/2026-05-26-aud-obligaciones-fiscales-design.md`
- Nuevo módulo `backend/app/aud/obligaciones_fiscales/` con modelo ephemeral
- 1 tabla nueva (`tool_jobs`) — sin storage en la nube
- Plantilla Excel baked-in
- Endpoints: POST/GET/DELETE /jobs + GET /jobs/{id}/download
- Cédulas DM6 IVA y DM7 Retenciones funcionales
- Cleanup periódico de /tmp y jobs expirados
- Frontend: ToolCatalog (15 categorías) + ObligacionesFiscalesTool
- Tests: ~25 nuevos

## Test plan
- [ ] Render deploy verde
- [ ] Checklist E2E (docs/AUD_OF_M1_E2E.md) completo en producción

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 16.5: Commit final**

```bash
git add docs/AUD_OF_M1_E2E.md
git commit -m "docs(aud/of): add M1 E2E verification checklist"
git push
```

---

## Resumen y siguiente paso

Al completar M1:
- ✅ Catálogo de 15 categorías visible
- ✅ Herramienta "Auditoría de Obligaciones Fiscales" funcional
- ✅ DM6 IVA y DM7 Retenciones pobladas en Excel descargado
- ✅ Resto de cédulas con plantilla original (sin poblar pero con encabezado actualizado)
- ✅ Modelo efímero — nada queda en la nube
- ✅ Sin regresiones

**Siguiente:** spec + plan M2 que cubre cédulas DM, DM1, DM2, DM3, DM4, DM5, DM8, DM9, DM10 + parsers de mayores y ATS XML.
