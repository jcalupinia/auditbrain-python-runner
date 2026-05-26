# AUD Retenciones en la Fuente — M1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el plumbing mínimo de la herramienta `AUD.RETENCIONES_FUENTE`: subir PDFs y verlos guardados en Cloudflare R2, asociados a un proyecto del módulo AUD, con persistencia en DB y autorización multi-tenant. **Sin lógica de extracción** (eso es M1.2).

**Architecture:** Módulo aditivo bajo `backend/app/aud/retenciones_fuente/` siguiendo el patrón de `backend/app/context/` y `backend/app/chat/`. Storage R2 vía boto3 con cliente reusable en `backend/app/core/storage.py`. Frontend: componente React nuevo en `frontend/src/RetencionesFuenteTool.jsx` integrado al `CognitiveWorkspace` del módulo AUD.

**Tech Stack:** FastAPI 0.115 · SQLAlchemy 2.0 · Pydantic 2 · boto3 (S3-compatible para R2) · moto (mock S3 en tests) · React 18 + Vite · pytest.

**Spec referencia:** `docs/superpowers/specs/2026-05-26-aud-retenciones-fuente-design.md`

---

## File Structure

### Backend — nuevos archivos
```
backend/app/core/storage.py                              # Cliente R2 reusable (boto3 wrapper)
backend/app/aud/__init__.py                              # vacío
backend/app/aud/retenciones_fuente/__init__.py           # vacío
backend/app/aud/retenciones_fuente/models.py             # SQLAlchemy: ToolExecution, UploadedFile, ExtractedRetention
backend/app/aud/retenciones_fuente/schemas.py            # Pydantic
backend/app/aud/retenciones_fuente/service.py            # CRUD multi-tenant
backend/app/aud/retenciones_fuente/router.py             # Endpoints FastAPI
```

### Backend — archivos modificados
```
backend/app/db/session.py                                # registrar nuevos modelos en init_db()
backend/app/api/__init__.py                              # include_router del nuevo módulo
backend/app/core/config.py                               # nuevas settings R2 + límites upload
requirements.txt                                          # +boto3 +moto (dev)
requirements-prod.txt                                     # +boto3
requirements-dev.txt                                      # +moto
render.yaml                                              # nuevas env vars R2
```

### Backend — tests nuevos
```
tests/test_aud_retenciones_storage.py                    # R2 client con moto
tests/test_aud_retenciones_service.py                    # service layer
tests/test_aud_retenciones_router.py                     # endpoints + multi-tenant
```

### Frontend — nuevos archivos
```
frontend/src/RetencionesFuenteTool.jsx                   # Componente principal de la herramienta
```

### Frontend — archivos modificados
```
frontend/src/api.js                                      # Métodos para los nuevos endpoints
frontend/src/App.jsx                                     # Integrar tab "Análisis" con la herramienta cuando module.id === "AUD"
frontend/src/styles.css                                  # Estilos del UploadZone y tabla
```

---

## Pre-requisitos (resolución de bloqueos antes de empezar)

Antes de la Task 1, el usuario debe tener:

1. **Cuenta Cloudflare R2 lista** con:
   - Account ID
   - Access Key ID y Secret Access Key (con permisos de read/write al bucket)
   - Bucket creado (sugerido: `auditbrain-storage`)
   - Endpoint URL (formato: `https://<account_id>.r2.cloudflarestorage.com`)

2. **Variables guardadas en Render Dashboard** del servicio `auditbrain-python-runner` (más adelante las referenciaremos en `render.yaml` con `sync: false`):
   - `R2_ACCOUNT_ID`
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_BUCKET`

Si el usuario no tiene esto listo, NO empezar la implementación todavía.

---

## Task 1: Dependencias + variables de entorno

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-prod.txt`
- Modify: `requirements-dev.txt`
- Modify: `render.yaml`

- [ ] **Step 1.1: Agregar boto3 a `requirements.txt`**

Abrir `requirements.txt` y agregar en la sección `# === Data Management / ETL ===`:

```
boto3==1.35.0
```

- [ ] **Step 1.2: Agregar boto3 a `requirements-prod.txt`**

Abrir `requirements-prod.txt`. Si no existe la sección de storage, agregarla al final:

```
# === Object storage (Cloudflare R2 vía S3 API) ===
boto3==1.35.0
```

- [ ] **Step 1.3: Agregar moto a `requirements-dev.txt`**

Abrir `requirements-dev.txt` y agregar:

```
moto[s3]==5.0.16
```

- [ ] **Step 1.4: Agregar env vars R2 a `render.yaml`**

Abrir `render.yaml`. En la sección `envVars` del servicio `auditbrain-python-runner`, agregar antes de la sección de F2/Postgres:

```yaml
      # --- Cloudflare R2 (object storage para uploads de herramientas) ---
      - key: R2_ACCOUNT_ID
        sync: false

      - key: R2_ACCESS_KEY_ID
        sync: false

      - key: R2_SECRET_ACCESS_KEY
        sync: false

      - key: R2_BUCKET
        sync: false

      - key: AUD_RETENCIONES_MAX_FILE_MB
        value: "20"

      - key: AUD_RETENCIONES_MAX_FILES_PER_EXECUTION
        value: "500"
```

- [ ] **Step 1.5: Instalar localmente las nuevas deps**

Run: `pip install -r requirements.txt -r requirements-dev.txt`
Expected: instala boto3 y moto sin error.

- [ ] **Step 1.6: Commit**

```bash
git add requirements.txt requirements-prod.txt requirements-dev.txt render.yaml
git commit -m "feat(aud/retenciones): add boto3 + R2 env vars for M1.1 storage"
```

---

## Task 2: Settings R2 en config.py

**Files:**
- Modify: `backend/app/core/config.py`

- [ ] **Step 2.1: Agregar settings R2 a `Settings`**

Abrir `backend/app/core/config.py`. Justo antes de `# Auth mínima por API Key`, agregar:

```python
    # --- Cloudflare R2 (object storage) ---
    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "").strip()
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "").strip()
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
    R2_BUCKET: str = os.getenv("R2_BUCKET", "auditbrain-storage").strip()

    # --- Límites de carga de la herramienta de retenciones ---
    AUD_RETENCIONES_MAX_FILE_MB: int = int(
        os.getenv("AUD_RETENCIONES_MAX_FILE_MB", "20")
    )
    AUD_RETENCIONES_MAX_FILES_PER_EXECUTION: int = int(
        os.getenv("AUD_RETENCIONES_MAX_FILES_PER_EXECUTION", "500")
    )

    @property
    def r2_endpoint_url(self) -> str:
        if not self.R2_ACCOUNT_ID:
            return ""
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    @property
    def r2_enabled(self) -> bool:
        return bool(
            self.R2_ACCOUNT_ID
            and self.R2_ACCESS_KEY_ID
            and self.R2_SECRET_ACCESS_KEY
            and self.R2_BUCKET
        )
```

- [ ] **Step 2.2: Verificar import**

Run: `python -c "from backend.app.core.config import settings; print(settings.r2_enabled)"`
Expected: imprime `False` (sin env vars locales) sin errores de import.

- [ ] **Step 2.3: Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat(config): add R2 + retenciones upload limits settings"
```

---

## Task 3: Cliente R2 reusable (`backend/app/core/storage.py`) — TDD

**Files:**
- Create: `backend/app/core/storage.py`
- Test: `tests/test_aud_retenciones_storage.py`

- [ ] **Step 3.1: Escribir test de upload exitoso (failing)**

Crear `tests/test_aud_retenciones_storage.py`:

```python
"""Tests del cliente de object storage (Cloudflare R2 vía S3 API)."""

import io

import boto3
import pytest
from moto import mock_aws

from backend.app.core import storage


@pytest.fixture()
def fake_r2_env(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "fake-account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret-fake")
    monkeypatch.setenv("R2_BUCKET", "test-bucket")
    # Recargar settings (módulo import-time)
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(storage)
    yield
    reload(config)
    reload(storage)


@mock_aws
def test_upload_and_download_bytes_roundtrip(fake_r2_env):
    # Crear bucket en el mock
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")

    storage.upload_bytes(
        key="test/file.pdf",
        data=b"hello world",
        content_type="application/pdf",
    )

    body = storage.download_bytes("test/file.pdf")
    assert body == b"hello world"
```

- [ ] **Step 3.2: Correr el test (debe fallar)**

Run: `pytest tests/test_aud_retenciones_storage.py::test_upload_and_download_bytes_roundtrip -v`
Expected: FAIL con `ImportError` o `AttributeError` (storage no existe / no tiene `upload_bytes`).

- [ ] **Step 3.3: Implementar `backend/app/core/storage.py` mínimo**

Crear `backend/app/core/storage.py`:

```python
"""Cliente de object storage para Cloudflare R2 (S3-compatible).

Reusable por todas las herramientas. Gated por settings: si no hay
credenciales R2 configuradas, las funciones lanzan StorageNotConfigured.
"""

from __future__ import annotations

import boto3
from botocore.client import Config

from backend.app.core.config import settings


class StorageNotConfigured(RuntimeError):
    """R2 no está configurado en el entorno."""


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not settings.r2_enabled:
        raise StorageNotConfigured(
            "R2 storage no está configurado. Define R2_ACCOUNT_ID, "
            "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET."
        )
    _client = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
    return _client


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Sube un blob de bytes a R2 bajo la key indicada."""
    client = _get_client()
    client.put_object(
        Bucket=settings.R2_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def download_bytes(key: str) -> bytes:
    """Descarga un objeto entero como bytes."""
    client = _get_client()
    obj = client.get_object(Bucket=settings.R2_BUCKET, Key=key)
    return obj["Body"].read()


def reset_client_for_tests() -> None:
    """Limpia el cliente cacheado. Solo para tests."""
    global _client
    _client = None
```

- [ ] **Step 3.4: Ajustar test para invalidar cliente cacheado**

El cliente se cachea en `_client`. El fixture debe resetear. Modificar el final del fixture `fake_r2_env` en `tests/test_aud_retenciones_storage.py`:

```python
@pytest.fixture()
def fake_r2_env(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "fake-account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret-fake")
    monkeypatch.setenv("R2_BUCKET", "test-bucket")
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(storage)
    storage.reset_client_for_tests()
    yield
    reload(config)
    reload(storage)
    storage.reset_client_for_tests()
```

- [ ] **Step 3.5: Correr test (debe pasar)**

Run: `pytest tests/test_aud_retenciones_storage.py::test_upload_and_download_bytes_roundtrip -v`
Expected: PASS.

- [ ] **Step 3.6: Agregar test de "storage no configurado lanza error"**

Agregar al final de `tests/test_aud_retenciones_storage.py`:

```python
def test_upload_raises_when_storage_not_configured(monkeypatch):
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("R2_BUCKET", raising=False)
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(storage)
    storage.reset_client_for_tests()

    with pytest.raises(storage.StorageNotConfigured):
        storage.upload_bytes("x", b"y")
```

- [ ] **Step 3.7: Correr ambos tests**

Run: `pytest tests/test_aud_retenciones_storage.py -v`
Expected: 2 PASS.

- [ ] **Step 3.8: Agregar `generate_presigned_url`**

Agregar al final de `backend/app/core/storage.py`:

```python
def generate_presigned_get_url(key: str, expires_in: int = 300) -> str:
    """Genera URL firmada para GET (descarga) válida por expires_in segundos."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )
```

- [ ] **Step 3.9: Test de presigned URL**

Agregar a `tests/test_aud_retenciones_storage.py`:

```python
@mock_aws
def test_generate_presigned_get_url_contains_key(fake_r2_env):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")
    storage.upload_bytes("path/to/file.pdf", b"content", "application/pdf")

    url = storage.generate_presigned_get_url("path/to/file.pdf", expires_in=60)
    assert "path/to/file.pdf" in url
    assert url.startswith("https://")
```

- [ ] **Step 3.10: Correr todos los tests del archivo**

Run: `pytest tests/test_aud_retenciones_storage.py -v`
Expected: 3 PASS.

- [ ] **Step 3.11: Commit**

```bash
git add backend/app/core/storage.py tests/test_aud_retenciones_storage.py
git commit -m "feat(core/storage): add Cloudflare R2 client (upload, download, presigned URL)"
```

---

## Task 4: Modelos SQLAlchemy

**Files:**
- Create: `backend/app/aud/__init__.py`
- Create: `backend/app/aud/retenciones_fuente/__init__.py`
- Create: `backend/app/aud/retenciones_fuente/models.py`

- [ ] **Step 4.1: Crear `backend/app/aud/__init__.py` (vacío)**

Crear archivo con contenido:

```python
"""Módulo AUD — External Audit. Catálogo de herramientas sectoriales de auditoría externa."""
```

- [ ] **Step 4.2: Crear `backend/app/aud/retenciones_fuente/__init__.py`**

Crear archivo con contenido:

```python
"""Herramienta AUD.RETENCIONES_FUENTE — Comprobantes de Retención SRI.

M1.1: plumbing mínimo (sin lógica de extracción).
"""
```

- [ ] **Step 4.3: Crear `backend/app/aud/retenciones_fuente/models.py`**

```python
"""Modelos SQLAlchemy de la herramienta AUD.RETENCIONES_FUENTE.

Tres tablas:
- ToolExecution: una ejecución (job) de la herramienta.
- UploadedFile: un PDF subido como input de una ejecución.
- ExtractedRetention: una fila extraída de un PDF (poblada en M1.2).

Multi-tenant: cada ejecución pertenece a un Project (que pertenece a una
Organization), heredando el aislamiento del modelo de contexto.
"""

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tool_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    started_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_excel_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("tool_executions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    r2_key: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_uploaded_files_exec_sha", "execution_id", "sha256"),
    )


class ExtractedRetention(Base):
    __tablename__ = "extracted_retentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("tool_executions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    uploaded_file_id: Mapped[int] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Campos extraídos (poblados en M1.2). Nullable porque M1.1 solo sube
    # archivos; ExtractedRetention todavía no se crea hasta el procesamiento.
    comprobante_tipo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comprobante_numero: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    fecha_emision: Mapped[datetime.date | None] = mapped_column(nullable=True)
    ejercicio_fiscal: Mapped[str | None] = mapped_column(String(8), nullable=True)
    base_imponible: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    impuesto: Mapped[str | None] = mapped_column(String(32), nullable=True)
    porcentaje_retencion: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    valor_retenido: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    autorizacion_sri: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agente_retencion_ruc: Mapped[str | None] = mapped_column(String(13), nullable=True)
    # Marcas del validador (M1.3)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_notes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4.4: Verificar que importan sin errores**

Run: `python -c "from backend.app.aud.retenciones_fuente import models; print(models.ToolExecution.__tablename__)"`
Expected: imprime `tool_executions` sin errores.

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/aud/__init__.py backend/app/aud/retenciones_fuente/__init__.py backend/app/aud/retenciones_fuente/models.py
git commit -m "feat(aud/retenciones): add SQLAlchemy models (ToolExecution, UploadedFile, ExtractedRetention)"
```

---

## Task 5: Registrar modelos en `init_db()`

**Files:**
- Modify: `backend/app/db/session.py`

- [ ] **Step 5.1: Agregar import del módulo de modelos a `init_db()`**

Abrir `backend/app/db/session.py`. En la función `init_db()`, agregar el import del nuevo módulo junto a los existentes:

```python
def init_db() -> None:
    """Crea las tablas si no existen y aplica migraciones ligeras.
    ...
    """
    from sqlalchemy import inspect, text

    # Registrar todas las tablas conocidas (orden importa: organizations y
    # projects deben existir antes de que users referencie sus columnas).
    from backend.app.auth import models as _auth_models  # noqa: F401
    from backend.app.aud.retenciones_fuente import models as _aud_ret_models  # noqa: F401
    from backend.app.chat import models as _chat_models  # noqa: F401
    from backend.app.context import models as _context_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ...
```

(El resto de la función queda igual.)

- [ ] **Step 5.2: Escribir test que verifique que las tablas se crean**

Agregar a `tests/test_aud_retenciones_storage.py` (que ya existe; o crear nuevo archivo de test si prefieres separar — sigue convención del repo manteniendo en `test_aud_retenciones_*`):

Mejor crear `tests/test_aud_retenciones_models.py`:

```python
"""Tests de que los modelos de retenciones se crean en init_db()."""

from sqlalchemy import inspect

from backend.app.db.session import engine, init_db


def test_tool_executions_table_exists():
    init_db()
    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "tool_executions" in tables
    assert "uploaded_files" in tables
    assert "extracted_retentions" in tables


def test_tool_executions_columns():
    init_db()
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("tool_executions")}
    assert {"id", "project_id", "tool_code", "status", "summary_json"} <= cols
```

- [ ] **Step 5.3: Correr tests**

Run: `pytest tests/test_aud_retenciones_models.py -v`
Expected: 2 PASS.

- [ ] **Step 5.4: Correr la suite completa para asegurarnos de no romper nada**

Run: `pytest -v`
Expected: TODOS los tests existentes siguen pasando (los 9 originales + nuestros nuevos).

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/db/session.py tests/test_aud_retenciones_models.py
git commit -m "feat(aud/retenciones): register models in init_db()"
```

---

## Task 6: Pydantic Schemas

**Files:**
- Create: `backend/app/aud/retenciones_fuente/schemas.py`

- [ ] **Step 6.1: Crear schemas**

```python
"""Pydantic schemas de la API de la herramienta AUD.RETENCIONES_FUENTE."""

import datetime

from pydantic import BaseModel, Field


class ExecutionCreate(BaseModel):
    project_id: int


class ExecutionOut(BaseModel):
    id: int
    project_id: int
    tool_code: str
    status: str
    started_by_user_id: int | None
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None
    error_message: str | None
    output_excel_key: str | None
    summary_json: dict | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class UploadedFileOut(BaseModel):
    id: int
    execution_id: int
    original_name: str
    r2_key: str
    size_bytes: int
    mime_type: str
    sha256: str
    uploaded_at: datetime.datetime

    model_config = {"from_attributes": True}


class ExecutionDetailOut(ExecutionOut):
    """Detalle de ejecución con sus archivos subidos."""
    files: list[UploadedFileOut] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """Respuesta de POST /executions/{id}/files."""
    uploaded: list[UploadedFileOut]
    duplicates: list[int] = Field(
        default_factory=list,
        description="IDs de UploadedFile existentes que coincidieron por SHA256.",
    )
```

- [ ] **Step 6.2: Verificar import**

Run: `python -c "from backend.app.aud.retenciones_fuente import schemas; print(schemas.ExecutionCreate.model_fields)"`
Expected: imprime un dict con la clave `project_id`.

- [ ] **Step 6.3: Commit**

```bash
git add backend/app/aud/retenciones_fuente/schemas.py
git commit -m "feat(aud/retenciones): add Pydantic schemas"
```

---

## Task 7: Service layer

**Files:**
- Create: `backend/app/aud/retenciones_fuente/service.py`
- Test: `tests/test_aud_retenciones_service.py`

- [ ] **Step 7.1: Escribir tests del service (failing)**

Crear `tests/test_aud_retenciones_service.py`:

```python
"""Tests del service layer de AUD.RETENCIONES_FUENTE."""

import uuid
from io import BytesIO

import boto3
import pytest
from moto import mock_aws

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.aud.retenciones_fuente import service
from backend.app.aud.retenciones_fuente.models import ToolExecution, UploadedFile
from backend.app.context import service as ctx_service
from backend.app.core import storage
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture()
def fake_r2_env(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "fake-account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret-fake")
    monkeypatch.setenv("R2_BUCKET", "test-bucket")
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(storage)
    storage.reset_client_for_tests()
    yield
    reload(config)
    reload(storage)
    storage.reset_client_for_tests()


def _mk_admin_with_project():
    """Crea admin + cliente + proyecto AUD. Retorna (user_id, project_id)."""
    db = SessionLocal()
    try:
        email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
        user = auth_service.create_user(db, email=email, password="Sup3rSecret!", role=Role.admin)
        user = ctx_service.ensure_user_has_organization(db, user)
        client = ctx_service.create_client(
            db,
            organization_id=user.organization_id,
            name="Cliente Demo",
        )
        proj = ctx_service.create_project(
            db,
            organization_id=user.organization_id,
            client_id=client.id,
            name="Auditoría 2026",
            module_code="AUD",
            period_label="AF 2026",
        )
        ctx_service.add_project_member(db, proj.id, user.id, "lead")
        return user.id, proj.id
    finally:
        db.close()


def test_create_execution_admin_returns_pending():
    user_id, project_id = _mk_admin_with_project()
    db = SessionLocal()
    try:
        exe = service.create_execution(db, user_id=user_id, project_id=project_id)
        assert exe.id is not None
        assert exe.project_id == project_id
        assert exe.status == "pending"
        assert exe.tool_code == "AUD.RETENCIONES_FUENTE"
        assert exe.started_by_user_id == user_id
    finally:
        db.close()


def test_create_execution_user_without_project_access_raises():
    """Un user que no es member del proyecto no puede crear ejecuciones."""
    _, project_id = _mk_admin_with_project()
    # Crear otro user sin acceso
    db = SessionLocal()
    try:
        other = auth_service.create_user(
            db,
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="Sup3rSecret!",
            role=Role.user,
        )
        other = ctx_service.ensure_user_has_organization(db, other)
        with pytest.raises(PermissionError):
            service.create_execution(db, user_id=other.id, project_id=project_id)
    finally:
        db.close()


@mock_aws
def test_upload_file_writes_to_r2_and_db(fake_r2_env):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")

    user_id, project_id = _mk_admin_with_project()
    db = SessionLocal()
    try:
        exe = service.create_execution(db, user_id=user_id, project_id=project_id)
        result = service.upload_file(
            db,
            execution_id=exe.id,
            user_id=user_id,
            original_name="retencion.pdf",
            content_type="application/pdf",
            data=b"%PDF-1.4\nfake pdf content",
        )
        assert result.uploaded
        f = result.uploaded[0]
        assert f.original_name == "retencion.pdf"
        assert f.size_bytes == len(b"%PDF-1.4\nfake pdf content")
        # Verificar que está en R2 (vía storage)
        body = storage.download_bytes(f.r2_key)
        assert body == b"%PDF-1.4\nfake pdf content"
        # Verificar en DB
        saved = db.get(UploadedFile, f.id)
        assert saved is not None
        assert saved.execution_id == exe.id
    finally:
        db.close()


@mock_aws
def test_upload_file_detects_duplicate_by_sha256(fake_r2_env):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")

    user_id, project_id = _mk_admin_with_project()
    db = SessionLocal()
    try:
        exe = service.create_execution(db, user_id=user_id, project_id=project_id)
        data = b"identical bytes"
        r1 = service.upload_file(
            db, execution_id=exe.id, user_id=user_id,
            original_name="a.pdf", content_type="application/pdf", data=data,
        )
        r2 = service.upload_file(
            db, execution_id=exe.id, user_id=user_id,
            original_name="b.pdf", content_type="application/pdf", data=data,
        )
        assert len(r1.uploaded) == 1
        assert len(r2.uploaded) == 0
        assert r2.duplicates == [r1.uploaded[0].id]
    finally:
        db.close()


def test_get_execution_enforces_project_access():
    user_id, project_id = _mk_admin_with_project()
    db = SessionLocal()
    try:
        exe = service.create_execution(db, user_id=user_id, project_id=project_id)
        # Otro user sin acceso
        other = auth_service.create_user(
            db,
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="Sup3rSecret!",
            role=Role.user,
        )
        other = ctx_service.ensure_user_has_organization(db, other)
        with pytest.raises(PermissionError):
            service.get_execution(db, user_id=other.id, execution_id=exe.id)
    finally:
        db.close()


def test_list_executions_only_returns_user_visible():
    user_id, project_id = _mk_admin_with_project()
    db = SessionLocal()
    try:
        service.create_execution(db, user_id=user_id, project_id=project_id)
        service.create_execution(db, user_id=user_id, project_id=project_id)
        items = service.list_executions(db, user_id=user_id, project_id=project_id)
        assert len(items) == 2
    finally:
        db.close()
```

- [ ] **Step 7.2: Correr tests (deben fallar — service no existe)**

Run: `pytest tests/test_aud_retenciones_service.py -v`
Expected: FAIL con `ImportError` o `AttributeError`.

- [ ] **Step 7.3: Implementar service**

Crear `backend/app/aud/retenciones_fuente/service.py`:

```python
"""Service layer de AUD.RETENCIONES_FUENTE.

Funciones que operan sobre la DB y autorizan acceso multi-tenant.
Capa que conoce SQLAlchemy y storage; no conoce FastAPI.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import User
from backend.app.aud.retenciones_fuente.models import (
    ExtractedRetention,
    ToolExecution,
    UploadedFile,
)
from backend.app.aud.retenciones_fuente.schemas import (
    UploadedFileOut,
    UploadResponse,
)
from backend.app.context import service as ctx_service
from backend.app.context.models import Project
from backend.app.core import storage

TOOL_CODE = "AUD.RETENCIONES_FUENTE"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise PermissionError("Usuario no encontrado.")
    return user


def _get_project(db: Session, project_id: int) -> Project:
    proj = db.get(Project, project_id)
    if not proj:
        raise PermissionError("Proyecto no encontrado.")
    return proj


def _ensure_user_can_access_project(db: Session, user_id: int, project_id: int) -> tuple[User, Project]:
    user = _get_user(db, user_id)
    proj = _get_project(db, project_id)
    if not ctx_service.user_can_access_project(db, user, proj):
        raise PermissionError("El usuario no tiene acceso al proyecto.")
    return user, proj


def _ensure_user_can_access_execution(db: Session, user_id: int, execution_id: int) -> tuple[User, ToolExecution]:
    user = _get_user(db, user_id)
    exe = db.get(ToolExecution, execution_id)
    if not exe:
        raise PermissionError("Ejecución no encontrada.")
    proj = _get_project(db, exe.project_id)
    if not ctx_service.user_can_access_project(db, user, proj):
        raise PermissionError("El usuario no tiene acceso al proyecto de esta ejecución.")
    return user, exe


def _r2_key_for_input(org_slug: str, project_id: int, execution_id: int, filename: str) -> str:
    safe_name = filename.replace("/", "_").replace("\\", "_")[:200]
    return f"auditbrain/{org_slug}/{project_id}/{execution_id}/inputs/{uuid.uuid4().hex}_{safe_name}"


# ---------------------------------------------------------------------------
# Executions
# ---------------------------------------------------------------------------

def create_execution(db: Session, user_id: int, project_id: int) -> ToolExecution:
    _ensure_user_can_access_project(db, user_id, project_id)
    exe = ToolExecution(
        project_id=project_id,
        tool_code=TOOL_CODE,
        status="pending",
        started_by_user_id=user_id,
        summary_json={"total": 0, "processed": 0, "errors": 0},
    )
    db.add(exe)
    db.commit()
    db.refresh(exe)
    return exe


def get_execution(db: Session, user_id: int, execution_id: int) -> ToolExecution:
    _, exe = _ensure_user_can_access_execution(db, user_id, execution_id)
    return exe


def list_execution_files(db: Session, execution_id: int) -> list[UploadedFile]:
    return list(
        db.execute(
            select(UploadedFile)
            .where(UploadedFile.execution_id == execution_id)
            .order_by(UploadedFile.uploaded_at)
        ).scalars()
    )


def list_executions(db: Session, user_id: int, project_id: int) -> list[ToolExecution]:
    _ensure_user_can_access_project(db, user_id, project_id)
    return list(
        db.execute(
            select(ToolExecution)
            .where(
                ToolExecution.project_id == project_id,
                ToolExecution.tool_code == TOOL_CODE,
            )
            .order_by(ToolExecution.created_at.desc())
        ).scalars()
    )


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------

def upload_file(
    db: Session,
    execution_id: int,
    user_id: int,
    original_name: str,
    content_type: str,
    data: bytes,
) -> UploadResponse:
    user, exe = _ensure_user_can_access_execution(db, user_id, execution_id)
    proj = _get_project(db, exe.project_id)
    # Resolver org slug del proyecto
    from backend.app.context.models import Organization

    org_obj = db.get(Organization, proj.organization_id)
    org_slug = org_obj.slug if org_obj else "default"

    sha = hashlib.sha256(data).hexdigest()

    # Detectar duplicado por (execution_id, sha256)
    existing = db.execute(
        select(UploadedFile).where(
            UploadedFile.execution_id == execution_id,
            UploadedFile.sha256 == sha,
        )
    ).scalar_one_or_none()
    if existing:
        return UploadResponse(uploaded=[], duplicates=[existing.id])

    key = _r2_key_for_input(org_slug, proj.id, exe.id, original_name)
    storage.upload_bytes(key=key, data=data, content_type=content_type)

    f = UploadedFile(
        execution_id=execution_id,
        original_name=original_name,
        r2_key=key,
        size_bytes=len(data),
        mime_type=content_type,
        sha256=sha,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return UploadResponse(uploaded=[UploadedFileOut.model_validate(f)], duplicates=[])
```

- [ ] **Step 7.4: Correr tests del service**

Run: `pytest tests/test_aud_retenciones_service.py -v`
Expected: 6 PASS.

- [ ] **Step 7.5: Correr suite completa**

Run: `pytest -v`
Expected: TODOS los tests pasan (existentes + nuevos).

- [ ] **Step 7.6: Commit**

```bash
git add backend/app/aud/retenciones_fuente/service.py tests/test_aud_retenciones_service.py
git commit -m "feat(aud/retenciones): add service layer (create/get/list executions, upload with dedup)"
```

---

## Task 8: Router con endpoints (POST /executions + GET endpoints)

**Files:**
- Create: `backend/app/aud/retenciones_fuente/router.py`
- Test: `tests/test_aud_retenciones_router.py`

- [ ] **Step 8.1: Escribir tests del router (failing)**

Crear `tests/test_aud_retenciones_router.py`:

```python
"""Tests de los endpoints HTTP de AUD.RETENCIONES_FUENTE."""

import io
import uuid

import boto3
import pytest
from moto import mock_aws

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.context import service as ctx_service
from backend.app.core import storage
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture()
def fake_r2_env(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "fake-account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret-fake")
    monkeypatch.setenv("R2_BUCKET", "test-bucket")
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(storage)
    storage.reset_client_for_tests()
    yield
    reload(config)
    reload(storage)
    storage.reset_client_for_tests()


def _mk_user(role=Role.user):
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=password, role=role)
    finally:
        db.close()
    return email, password


def _login(client, email, password):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _mk_admin_project_via_api(client):
    admin_email, admin_pw = _mk_user(Role.admin)
    tok = _login(client, admin_email, admin_pw)
    r = client.post(
        "/api/v1/context/clients",
        headers=_h(tok),
        json={"name": "Cliente Demo"},
    )
    cid = r.json()["id"]
    r = client.post(
        "/api/v1/context/projects",
        headers=_h(tok),
        json={"client_id": cid, "name": "Auditoría 2026", "module_code": "AUD"},
    )
    pid = r.json()["id"]
    return tok, pid


def test_create_execution_returns_201(client):
    tok, pid = _mk_admin_project_via_api(client)
    r = client.post(
        "/api/v1/aud/retenciones-fuente/executions",
        headers=_h(tok),
        json={"project_id": pid},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["project_id"] == pid
    assert body["status"] == "pending"
    assert body["tool_code"] == "AUD.RETENCIONES_FUENTE"


def test_create_execution_requires_auth(client):
    r = client.post(
        "/api/v1/aud/retenciones-fuente/executions",
        json={"project_id": 1},
    )
    assert r.status_code == 401


def test_create_execution_user_without_project_access_403(client):
    tok_admin, pid = _mk_admin_project_via_api(client)
    user_email, user_pw = _mk_user(Role.user)
    user_tok = _login(client, user_email, user_pw)
    r = client.post(
        "/api/v1/aud/retenciones-fuente/executions",
        headers=_h(user_tok),
        json={"project_id": pid},
    )
    assert r.status_code == 403


def test_get_execution_returns_details(client):
    tok, pid = _mk_admin_project_via_api(client)
    r = client.post(
        "/api/v1/aud/retenciones-fuente/executions",
        headers=_h(tok),
        json={"project_id": pid},
    )
    eid = r.json()["id"]
    r = client.get(f"/api/v1/aud/retenciones-fuente/executions/{eid}", headers=_h(tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == eid
    assert body["files"] == []


def test_list_executions_filters_by_project(client):
    tok, pid = _mk_admin_project_via_api(client)
    client.post("/api/v1/aud/retenciones-fuente/executions", headers=_h(tok), json={"project_id": pid})
    client.post("/api/v1/aud/retenciones-fuente/executions", headers=_h(tok), json={"project_id": pid})
    r = client.get(
        f"/api/v1/aud/retenciones-fuente/executions?project_id={pid}",
        headers=_h(tok),
    )
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 2


@mock_aws
def test_upload_file_201_creates_record_and_uploads_to_r2(client, fake_r2_env):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")

    tok, pid = _mk_admin_project_via_api(client)
    r = client.post(
        "/api/v1/aud/retenciones-fuente/executions",
        headers=_h(tok),
        json={"project_id": pid},
    )
    eid = r.json()["id"]
    files = {"files": ("ret.pdf", b"%PDF-1.4\nfoo", "application/pdf")}
    r = client.post(
        f"/api/v1/aud/retenciones-fuente/executions/{eid}/files",
        headers=_h(tok),
        files=files,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["uploaded"]) == 1
    assert body["uploaded"][0]["original_name"] == "ret.pdf"


@mock_aws
def test_upload_file_rejects_non_pdf(client, fake_r2_env):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")

    tok, pid = _mk_admin_project_via_api(client)
    r = client.post(
        "/api/v1/aud/retenciones-fuente/executions",
        headers=_h(tok),
        json={"project_id": pid},
    )
    eid = r.json()["id"]
    files = {"files": ("ret.xlsx", b"not a pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post(
        f"/api/v1/aud/retenciones-fuente/executions/{eid}/files",
        headers=_h(tok),
        files=files,
    )
    assert r.status_code == 415
```

- [ ] **Step 8.2: Correr tests (deben fallar)**

Run: `pytest tests/test_aud_retenciones_router.py -v`
Expected: FAIL (router no existe, ruta no registrada).

- [ ] **Step 8.3: Implementar router**

Crear `backend/app/aud/retenciones_fuente/router.py`:

```python
"""Endpoints HTTP de AUD.RETENCIONES_FUENTE.

Bajo /api/v1/aud/retenciones-fuente/*

Acceso: JWT autenticado (cualquier rol con membresía del proyecto).
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.aud.retenciones_fuente import service
from backend.app.aud.retenciones_fuente.schemas import (
    ExecutionCreate,
    ExecutionDetailOut,
    ExecutionOut,
    UploadedFileOut,
    UploadResponse,
)
from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(
    prefix="/aud/retenciones-fuente",
    tags=["aud-retenciones-fuente"],
)


ALLOWED_MIME = {"application/pdf"}


@router.post(
    "/executions",
    response_model=ExecutionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_execution_endpoint(
    payload: ExecutionCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        exe = service.create_execution(db, user_id=current.id, project_id=payload.project_id)
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    return ExecutionOut.model_validate(exe)


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionDetailOut,
)
def get_execution_endpoint(
    execution_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        exe = service.get_execution(db, user_id=current.id, execution_id=execution_id)
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    files = service.list_execution_files(db, execution_id)
    return ExecutionDetailOut(
        **ExecutionOut.model_validate(exe).model_dump(),
        files=[UploadedFileOut.model_validate(f) for f in files],
    )


@router.get(
    "/executions",
    response_model=list[ExecutionOut],
)
def list_executions_endpoint(
    project_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        items = service.list_executions(db, user_id=current.id, project_id=project_id)
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    return [ExecutionOut.model_validate(i) for i in items]


@router.post(
    "/executions/{execution_id}/files",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file_endpoint(
    execution_id: int,
    files: list[UploadFile],
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    max_bytes = settings.AUD_RETENCIONES_MAX_FILE_MB * 1024 * 1024
    uploaded_all: list[UploadedFileOut] = []
    duplicates_all: list[int] = []

    for uf in files:
        if uf.content_type not in ALLOWED_MIME:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Tipo MIME no permitido: {uf.content_type}. Solo {sorted(ALLOWED_MIME)}.",
            )
        data = await uf.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Archivo {uf.filename} excede el límite de {settings.AUD_RETENCIONES_MAX_FILE_MB} MB.",
            )
        try:
            resp = service.upload_file(
                db,
                execution_id=execution_id,
                user_id=current.id,
                original_name=uf.filename or "sin_nombre.pdf",
                content_type=uf.content_type,
                data=data,
            )
        except PermissionError as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
        uploaded_all.extend(resp.uploaded)
        duplicates_all.extend(resp.duplicates)

    return UploadResponse(uploaded=uploaded_all, duplicates=duplicates_all)
```

- [ ] **Step 8.4: Registrar router en `backend/app/api/__init__.py`**

Abrir `backend/app/api/__init__.py`. Agregar el import y `include_router`:

```python
"""Router agregado de la API v1.
..."""

from fastapi import APIRouter

from backend.app.api import documents, health, python, router as router_module
from backend.app.auth import router as auth_router
from backend.app.aud.retenciones_fuente import router as aud_retenciones_router
from backend.app.chat import router as chat_router
from backend.app.context import router as context_router
from backend.app.core.config import settings

api_router = APIRouter(prefix=settings.PLATFORM_API_PREFIX)
api_router.include_router(health.router)
api_router.include_router(auth_router.router)
api_router.include_router(router_module.router)
api_router.include_router(python.router)
api_router.include_router(documents.router)
api_router.include_router(context_router.router)
api_router.include_router(chat_router.router)
api_router.include_router(aud_retenciones_router.router)

__all__ = ["api_router"]
```

- [ ] **Step 8.5: Correr tests del router**

Run: `pytest tests/test_aud_retenciones_router.py -v`
Expected: 7 PASS.

- [ ] **Step 8.6: Correr suite completa**

Run: `pytest -v`
Expected: TODOS PASAN.

- [ ] **Step 8.7: Commit**

```bash
git add backend/app/aud/retenciones_fuente/router.py backend/app/api/__init__.py tests/test_aud_retenciones_router.py
git commit -m "feat(aud/retenciones): add HTTP endpoints (create/get/list executions, upload files)"
```

---

## Task 9: Frontend — métodos en api.js

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 9.1: Leer api.js actual para entender el patrón**

Run: `cat frontend/src/api.js | head -60`
Expected: ves funciones como `login`, `me`, `runPython`, `generateDocument`, `health`, `createUser`, `listClients`, etc. Hay un patrón `apiFetch` o similar.

- [ ] **Step 9.2: Agregar métodos al final de `frontend/src/api.js`**

Antes del último `export` (o donde corresponda según patrón existente), agregar:

```javascript
// === AUD.RETENCIONES_FUENTE ===

export async function createRetencionesExecution(projectId) {
  const r = await fetch(`${getApiBase()}/api/v1/aud/retenciones-fuente/executions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!r.ok) throw new Error((await r.json()).detail || "Error creando ejecución");
  return r.json();
}

export async function uploadRetencionesFile(executionId, file, onProgress) {
  const fd = new FormData();
  fd.append("files", file);
  // Para barra de progreso usar XMLHttpRequest (fetch no expone progress).
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(
      "POST",
      `${getApiBase()}/api/v1/aud/retenciones-fuente/executions/${executionId}/files`
    );
    xhr.setRequestHeader("Authorization", `Bearer ${getToken()}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)); }
        catch { reject(new Error("Respuesta inválida del servidor.")); }
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new Error(body.detail || `HTTP ${xhr.status}`));
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      }
    };
    xhr.onerror = () => reject(new Error("Error de red al subir."));
    xhr.send(fd);
  });
}

export async function getRetencionesExecution(executionId) {
  const r = await fetch(
    `${getApiBase()}/api/v1/aud/retenciones-fuente/executions/${executionId}`,
    { headers: { Authorization: `Bearer ${getToken()}` } }
  );
  if (!r.ok) throw new Error((await r.json()).detail || "Error consultando ejecución");
  return r.json();
}

export async function listRetencionesExecutions(projectId) {
  const r = await fetch(
    `${getApiBase()}/api/v1/aud/retenciones-fuente/executions?project_id=${projectId}`,
    { headers: { Authorization: `Bearer ${getToken()}` } }
  );
  if (!r.ok) throw new Error((await r.json()).detail || "Error listando ejecuciones");
  return r.json();
}
```

> **Nota:** Si `getApiBase` y `getToken` no son exports — están como funciones internas — usa los nombres exactos del archivo. Lee `frontend/src/api.js` primero y adapta el código de arriba a la convención local (probablemente `import.meta.env.VITE_API_BASE` y un helper para el token en localStorage).

- [ ] **Step 9.3: Verificar build frontend**

Run: `cd frontend && npm run build`
Expected: build pasa sin errores (sin lint warning del nuevo código).

- [ ] **Step 9.4: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(frontend/api): add methods for retenciones executions (create/get/list/upload)"
```

---

## Task 10: Frontend — Componente `RetencionesFuenteTool`

**Files:**
- Create: `frontend/src/RetencionesFuenteTool.jsx`
- Modify: `frontend/src/styles.css` (estilos del UploadZone)

- [ ] **Step 10.1: Crear el componente principal**

Crear `frontend/src/RetencionesFuenteTool.jsx`:

```jsx
import { useState, useEffect, useCallback, useRef } from "react";
import * as api from "./api.js";

/**
 * Componente principal de la herramienta AUD.RETENCIONES_FUENTE.
 * M1.1: solo subir PDFs y ver ejecuciones. Procesamiento real es M1.2.
 *
 * Props:
 *   - projectId: id del proyecto activo (módulo AUD). Requerido.
 */
export default function RetencionesFuenteTool({ projectId }) {
  const [executions, setExecutions] = useState([]);
  const [activeExecution, setActiveExecution] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState({}); // { filename: 0..1 }
  const [err, setErr] = useState("");
  const fileInputRef = useRef();

  const reload = useCallback(async () => {
    if (!projectId) return;
    try {
      const items = await api.listRetencionesExecutions(projectId);
      setExecutions(items);
    } catch (e) {
      setErr(e.message);
    }
  }, [projectId]);

  useEffect(() => { reload(); }, [reload]);

  async function startNewExecution() {
    setErr("");
    try {
      const exe = await api.createRetencionesExecution(projectId);
      setActiveExecution(exe);
      await reload();
      // Auto-trigger file picker
      setTimeout(() => fileInputRef.current?.click(), 50);
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onFilesPicked(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length || !activeExecution) return;
    setUploading(true);
    setErr("");
    try {
      for (const f of files) {
        await api.uploadRetencionesFile(activeExecution.id, f, (frac) => {
          setProgress((p) => ({ ...p, [f.name]: frac }));
        });
      }
      // Refrescar detalle
      const detail = await api.getRetencionesExecution(activeExecution.id);
      setActiveExecution(detail);
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setUploading(false);
      e.target.value = ""; // permite re-seleccionar mismo archivo
    }
  }

  async function openExecution(id) {
    setErr("");
    try {
      const detail = await api.getRetencionesExecution(id);
      setActiveExecution(detail);
    } catch (e) {
      setErr(e.message);
    }
  }

  if (!projectId) {
    return (
      <div className="notice warn">
        Selecciona un proyecto del módulo AUD para usar esta herramienta.
      </div>
    );
  }

  return (
    <div className="ret-tool">
      <div className="ret-tool-h">
        <div>
          <h2>Comprobantes de Retención SRI</h2>
          <p className="muted">
            Sube los PDFs de retenciones. El procesamiento automático se habilita en M1.2.
          </p>
        </div>
        <button className="btn primary" onClick={startNewExecution} disabled={uploading}>
          + Nueva ejecución
        </button>
      </div>

      {err && <div className="err">{err}</div>}

      {activeExecution && (
        <div className="ret-tool-active">
          <h3>
            Ejecución #{activeExecution.id}
            <span className={`badge ${activeExecution.status}`}>
              {activeExecution.status}
            </span>
          </h3>

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            multiple
            onChange={onFilesPicked}
            style={{ display: "none" }}
          />
          <button
            className="btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            Subir PDFs
          </button>

          {Object.entries(progress).length > 0 && (
            <div className="ret-progress">
              {Object.entries(progress).map(([name, frac]) => (
                <div key={name} className="ret-progress-row">
                  <span className="ret-progress-name">{name}</span>
                  <div className="ret-progress-bar">
                    <div style={{ width: `${Math.round(frac * 100)}%` }} />
                  </div>
                  <span className="ret-progress-pct">{Math.round(frac * 100)}%</span>
                </div>
              ))}
            </div>
          )}

          {activeExecution.files?.length > 0 && (
            <div className="ret-files">
              <div className="ret-files-h">
                Archivos subidos ({activeExecution.files.length})
              </div>
              <ul>
                {activeExecution.files.map((f) => (
                  <li key={f.id}>
                    <span className="mono">{f.original_name}</span>
                    <span className="muted">
                      {" "}· {(f.size_bytes / 1024).toFixed(1)} KB
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="ret-history">
        <h3>Ejecuciones previas</h3>
        {executions.length === 0 ? (
          <div className="muted">No hay ejecuciones registradas para este proyecto.</div>
        ) : (
          <table className="ret-table">
            <thead>
              <tr>
                <th>#</th><th>Estado</th><th>Creada</th><th>Resumen</th><th></th>
              </tr>
            </thead>
            <tbody>
              {executions.map((e) => (
                <tr key={e.id}>
                  <td>{e.id}</td>
                  <td><span className={`badge ${e.status}`}>{e.status}</span></td>
                  <td className="muted">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="muted">
                    {e.summary_json ?
                      `${e.summary_json.processed ?? 0}/${e.summary_json.total ?? 0}` :
                      "—"}
                  </td>
                  <td>
                    <button className="link" onClick={() => openExecution(e.id)}>
                      Abrir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 10.2: Agregar estilos al final de `frontend/src/styles.css`**

```css
/* === AUD.RETENCIONES_FUENTE === */
.ret-tool { padding: 16px 0; }
.ret-tool-h { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 16px; }
.ret-tool-h h2 { margin: 0; }
.ret-tool-active { border: 1px solid var(--border, #2a2f38); border-radius: 8px; padding: 16px; margin-bottom: 24px; }
.ret-tool-active h3 { margin: 0 0 12px; display: flex; align-items: center; gap: 8px; }
.badge { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: rgba(255,255,255,.06); text-transform: uppercase; }
.badge.pending { color: #9aa3af; }
.badge.running { color: #f5c842; }
.badge.done { color: #36d399; }
.badge.failed { color: #f87272; }
.ret-progress { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.ret-progress-row { display: grid; grid-template-columns: 1fr 200px 50px; gap: 8px; align-items: center; }
.ret-progress-name { font-size: 12px; color: var(--muted, #9aa3af); }
.ret-progress-bar { height: 6px; background: rgba(255,255,255,.08); border-radius: 3px; overflow: hidden; }
.ret-progress-bar > div { height: 100%; background: var(--accent, #6ea8fe); transition: width .2s; }
.ret-progress-pct { font-size: 11px; color: var(--muted, #9aa3af); text-align: right; }
.ret-files { margin-top: 12px; }
.ret-files-h { font-size: 12px; color: var(--muted, #9aa3af); margin-bottom: 6px; }
.ret-files ul { margin: 0; padding-left: 18px; }
.ret-history { margin-top: 24px; }
.ret-table { width: 100%; border-collapse: collapse; margin-top: 8px; }
.ret-table th, .ret-table td { padding: 8px; text-align: left; border-bottom: 1px solid var(--border, #2a2f38); font-size: 13px; }
.ret-table th { color: var(--muted, #9aa3af); font-weight: 500; font-size: 11px; text-transform: uppercase; }
```

- [ ] **Step 10.3: Verificar build**

Run: `cd frontend && npm run build`
Expected: build pasa sin errores ni warnings críticos.

- [ ] **Step 10.4: Commit**

```bash
git add frontend/src/RetencionesFuenteTool.jsx frontend/src/styles.css
git commit -m "feat(frontend): add RetencionesFuenteTool component + styles"
```

---

## Task 11: Frontend — Integrar en App.jsx

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 11.1: Importar el componente**

Abrir `frontend/src/App.jsx`. Al inicio, junto al import de `api`, agregar:

```jsx
import RetencionesFuenteTool from "./RetencionesFuenteTool.jsx";
```

- [ ] **Step 11.2: Modificar el `CognitiveWorkspace` para renderizar la herramienta cuando AUD + tab "análisis"**

Localizar en `App.jsx` la función `CognitiveWorkspace` y el bloque que renderiza según `tab`:

```jsx
{tab === "documentos" ? (
  <div className="cw-docs">
    <Documents embedded />
  </div>
) : (
  <div className="cw-stage">
    ...
```

Agregar antes del bloque `documentos` un nuevo bloque para `análisis` cuando el módulo es AUD:

```jsx
{tab === "análisis" && module.id === "AUD" ? (
  <div className="cw-tool">
    <RetencionesFuenteTool projectId={ctx?.active_project?.id} />
  </div>
) : tab === "documentos" ? (
  <div className="cw-docs">
    <Documents embedded />
  </div>
) : (
  <div className="cw-stage">
    ...
```

- [ ] **Step 11.3: Agregar estilo para `.cw-tool`**

Abrir `frontend/src/styles.css` y agregar al final:

```css
.cw-tool { padding: 16px 8px; }
```

- [ ] **Step 11.4: Verificar build**

Run: `cd frontend && npm run build`
Expected: build pasa.

- [ ] **Step 11.5: Verificar dev server localmente (opcional pero recomendado)**

Run: `cd frontend && npm run dev` (en otra terminal correr el backend con `uvicorn app:app --reload`)
Expected:
- Abrir `http://localhost:5173`
- Login con un admin
- Crear cliente + proyecto AUD desde Workspaces
- Activar el proyecto
- Ir a módulo AUD
- Click en tab "Análisis"
- Ver el panel "Comprobantes de Retención SRI" con botón "+ Nueva ejecución"

Si esto funciona, listo. Si no, debug antes de commitear.

- [ ] **Step 11.6: Commit**

```bash
git add frontend/src/App.jsx frontend/src/styles.css
git commit -m "feat(frontend): wire RetencionesFuenteTool into AUD module Análisis tab"
```

---

## Task 12: Documentación + checklist E2E

**Files:**
- Create: `docs/AUD_RETENCIONES_M1_1_E2E.md`

- [ ] **Step 12.1: Escribir checklist de verificación end-to-end**

Crear `docs/AUD_RETENCIONES_M1_1_E2E.md`:

```markdown
# AUD Retenciones · M1.1 · Checklist E2E

## Pre-requisitos
- [ ] Variables R2 configuradas en Render dashboard del servicio backend.
- [ ] Bucket R2 creado (sugerido: `auditbrain-storage`).
- [ ] Última versión desplegada (auto-deploy de Render desde `main`).

## Verificación

1. [ ] **Login** en https://auditbrain-frontend.onrender.com con admin.
2. [ ] **Ir a WKS (Workspaces)** y crear un cliente nuevo si no existe.
3. [ ] **Crear proyecto** con `module_code = AUD`, período "AF 2026" o similar.
4. [ ] **Activar el proyecto** desde el selector "Workspace" en el header.
5. [ ] **Ir al módulo AUD** desde el sidebar.
6. [ ] **Click en tab "Análisis"**.
7. [ ] **Ver el panel "Comprobantes de Retención SRI"** con botón "+ Nueva ejecución".
8. [ ] **Click "+ Nueva ejecución"** → se abre el selector de archivos automáticamente.
9. [ ] **Seleccionar 5 PDFs reales** del SRI.
10. [ ] **Verificar barras de progreso** suben a 100% por cada archivo.
11. [ ] **Ver que aparecen** en "Archivos subidos (5)" debajo.
12. [ ] **Refrescar la página**, ir a tab Análisis nuevamente → ver la ejecución en "Ejecuciones previas".
13. [ ] **Click "Abrir"** sobre la ejecución previa → ver los 5 archivos.

## Verificación en R2 (manualmente vía Cloudflare dashboard)
- [ ] Bucket `auditbrain-storage` contiene objetos bajo `auditbrain/auditbrain/<project_id>/<execution_id>/inputs/`.
- [ ] Los nombres tienen formato `<uuid>_<original_name>`.

## Verificación de aislamiento multi-tenant
- [ ] Crear un segundo admin en una organización distinta (vía SQL directo en DB o crear otro despliegue de pruebas).
- [ ] Verificar que el admin de Org B NO ve las ejecuciones del admin de Org A.
- [ ] Verificar que intentar `GET /api/v1/aud/retenciones-fuente/executions/<id_de_org_A>` desde Org B retorna 403.

## Criterio de éxito M1.1
Todo lo anterior funcionando sin errores en producción → M1.1 DONE.
Listo para arrancar M1.2 (extractor + Excel builder).
```

- [ ] **Step 12.2: Commit**

```bash
git add docs/AUD_RETENCIONES_M1_1_E2E.md
git commit -m "docs(aud/retenciones): add M1.1 E2E verification checklist"
```

---

## Task 13: Verificación final + push

- [ ] **Step 13.1: Correr toda la suite de tests**

Run: `pytest -v`
Expected: TODOS pasan (los 9+ originales + ~16 nuevos).

- [ ] **Step 13.2: Build de frontend**

Run: `cd frontend && npm run build`
Expected: build limpio.

- [ ] **Step 13.3: Push a una rama feature**

```bash
git checkout -b feat/aud-retenciones-m1-1
git push -u origin feat/aud-retenciones-m1-1
```

- [ ] **Step 13.4: Crear PR**

Run: `gh pr create --title "feat(aud/retenciones): M1.1 plumbing — upload PDFs to R2 + multi-tenant scoping" --body "$(cat <<'EOF'
## Summary
- Implementa M1.1 del spec `docs/superpowers/specs/2026-05-26-aud-retenciones-fuente-design.md`
- Nuevo módulo backend `backend/app/aud/retenciones_fuente/` con modelos, schemas, service, router
- Cliente R2 reusable en `backend/app/core/storage.py`
- Frontend: nuevo componente `RetencionesFuenteTool.jsx` integrado al tab Análisis del módulo AUD
- Tests: 16+ nuevos cubriendo storage (con moto), service (multi-tenant), router (autorización)

## Test plan
- [ ] Render auto-deploy verde
- [ ] Variables R2 configuradas en dashboard antes del merge
- [ ] Checklist `docs/AUD_RETENCIONES_M1_1_E2E.md` completo en producción
- [ ] No regresión en tests existentes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"`

Expected: PR creado. Esperar review humana.

- [ ] **Step 13.5: NO mergear hasta validar checklist E2E**

Recordatorio: el PR queda en "draft" o "ready for review" hasta que la verificación de `docs/AUD_RETENCIONES_M1_1_E2E.md` pase en producción. Si falla en producción tras deploy preview, revertir o ajustar antes de merge a main.

---

## Resumen y próximos pasos

**Al completar este plan:**

✅ Plumbing completo: usuarios pueden crear ejecuciones, subir PDFs y verlos persistidos.
✅ Storage R2 reusable para futuras herramientas (M1.2+, futuros módulos).
✅ Multi-tenant scoping validado por tests.
✅ Frontend integrado al Command Center existente, sin tocar componentes ya entregados.
✅ Sin regresiones — toda la suite existente sigue pasando.

**Lo que NO está hecho (intencional, va en M1.2+):**

- ❌ Extracción real de datos de los PDFs (`extractor.py`).
- ❌ Generación del Excel papel de trabajo (`excel_builder.py`).
- ❌ BackgroundTask de procesamiento (`jobs.py`).
- ❌ Endpoint `/run` y `/download`.
- ❌ Validaciones inteligentes (M1.3).
- ❌ Integración SRI web service (M1.4).

**Siguiente paso:** Spec + plan de M1.2.

Antes de empezar M1.2 necesitamos:
1. Plantilla Excel del papel de trabajo de retenciones (del usuario).
2. 5-10 PDFs reales del SRI anonimizados como fixtures de tests.
