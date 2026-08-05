# Ciclo del job y API — Plan 2 de 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir el job de Obligaciones Fiscales en una sesión persistente de dos fases: se sube archivo por archivo, el motor clasifica el mayor, el auditor revisa y aprueba, y recién entonces se genera el Excel — guardando cada corrección como homologación del cliente.

**Architecture:** Se conserva `ToolJob` y se le agregan los estados `borrador` y `revision`. Tres tablas nuevas (categorías configurables, homologaciones por cliente, clasificación por job) creadas por `Base.metadata.create_all`, más una columna nueva en `tool_jobs` vía la migración aditiva idempotente que ya usa `init_db()`. El motor del Plan 1 se consume tal cual: sigue sin saber que existe una base de datos.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Pydantic v2, pytest + TestClient.

**Spec:** `docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md`
**Depende de:** Plan 1 (motor de mayores), ya implementado y verificado.

---

## Estado actual del que se parte

- `backend/app/aud/obligaciones_fiscales/`: `router.py` (un único `POST /jobs` multipart que recibe TODOS los archivos y dispara `jobs.process_job`), `service.py` (CRUD + autorización), `models.py` (`ToolJob`), `schemas.py` (`JobOut`), `file_storage.py` (`inputs/<slot>/<archivo>`), `jobs.py` (fase única), `excel_assembler.py`.
- `mayor/`: `tipos.py`, `reader.py`, `cuentas.py`, `catalogo.py`, `senales.py`, `clasificador.py`. Punto de entrada: `leer_mayor(bytes) → LecturaMayor`, `perfilar(movimientos) → dict[str, PerfilCuenta]`, `clasificar(perfiles, historial=...) → list[ResultadoClasificacion]`.
- Los slots `mayor_compras` y `mayor_ventas` existen en `router.py:43-51,92-93,132-135` y `jobs.py:34-35` pero **ninguna cédula los consume**: se eliminan en la Task 5.
- Tests de referencia para el estilo: `tests/test_aud_of_router.py` (helpers `_mk_admin_project`, `_login`, `_h`).

## Ciclo de vida objetivo

```
POST /jobs                → borrador
PUT  /jobs/{id}/slots/{s} → borrador   (repetible; DELETE quita)
POST /jobs/{id}/procesar  → running → revision   (fase 1: leer mayor + clasificar)
PUT  /jobs/{id}/clasificacion → revision          (correcciones del auditor)
POST /jobs/{id}/aprobar   → running → done        (fase 2: cédulas + Excel)
```

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `mayor/models.py` (nuevo) | `MayorCategoria`, `MayorHomologacion`, `MayorClasificacionJob` |
| `mayor/catalogo_service.py` (nuevo) | Semilla idempotente y consulta del catálogo por organización |
| `mayor/homologaciones.py` (nuevo) | Historial por cliente: leer como `dict`, guardar upsert |
| `mayor/clasificacion_service.py` (nuevo) | Persistir/leer/corregir la clasificación de un job |
| `obligaciones_fiscales/models.py` (modificar) | +columna `mayor_especifico_categoria` |
| `obligaciones_fiscales/service.py` (modificar) | +`mark_revision`, +`create_job` en `borrador` |
| `obligaciones_fiscales/schemas.py` (modificar) | +schemas de slots y clasificación |
| `obligaciones_fiscales/router.py` (modificar) | Nuevos endpoints; fuera `mayor_compras`/`mayor_ventas` |
| `obligaciones_fiscales/jobs.py` (modificar) | Fase 1 (`clasificar_mayor_job`) y fase 2 (`process_job`) |
| `backend/app/db/session.py` (modificar) | Registrar los modelos nuevos + ALTER idempotente |

---

### Task 1: Modelos de persistencia del motor

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/models.py`
- Modify: `backend/app/db/session.py`
- Test: `tests/test_of_mayor_models.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Persistencia del motor de mayores: catálogo, homologaciones y clasificación."""

import pytest
from sqlalchemy import inspect

from backend.app.aud.obligaciones_fiscales.mayor.models import (
    MayorCategoria,
    MayorClasificacionJob,
    MayorHomologacion,
)
from backend.app.db.session import SessionLocal, engine, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_las_tres_tablas_se_crean_con_init_db():
    tablas = set(inspect(engine).get_table_names())
    assert {"mayor_categorias", "mayor_homologaciones", "mayor_clasificacion_job"} <= tablas


def test_una_homologacion_es_unica_por_cliente_y_codigo_de_cuenta():
    db = SessionLocal()
    try:
        db.add(MayorHomologacion(client_id=1, codigo_cuenta="1.1.5.1.1",
                                 nombre_norm="iva sobre compras", categoria="IVA_COMPRAS"))
        db.commit()
        db.add(MayorHomologacion(client_id=1, codigo_cuenta="1.1.5.1.1",
                                 nombre_norm="otro", categoria="VENTAS"))
        with pytest.raises(Exception):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_el_mismo_codigo_puede_existir_para_otro_cliente():
    db = SessionLocal()
    try:
        db.add(MayorHomologacion(client_id=101, codigo_cuenta="4.1.1.1",
                                 nombre_norm="ventas", categoria="VENTAS"))
        db.add(MayorHomologacion(client_id=102, codigo_cuenta="4.1.1.1",
                                 nombre_norm="ventas", categoria="VENTAS"))
        db.commit()
        n = db.query(MayorHomologacion).filter_by(codigo_cuenta="4.1.1.1").count()
        assert n == 2
    finally:
        db.rollback()
        db.close()


def test_la_clasificacion_de_un_job_guarda_las_senales_como_json():
    db = SessionLocal()
    try:
        fila = MayorClasificacionJob(
            job_id=1, codigo_cuenta="2.1.7.3.2", nombre_cuenta="Ret. 70% Servicios",
            categoria_sugerida="RET_IVA", categoria_final="RET_IVA", tarifa=70.0,
            confianza="alta", origen="reglas",
            senales_json=[{"categoria": "RET_IVA", "puntaje": 40, "motivo": "por nombre"}],
        )
        db.add(fila)
        db.commit()
        leida = db.query(MayorClasificacionJob).filter_by(job_id=1).one()
        assert leida.senales_json[0]["puntaje"] == 40
        assert leida.tarifa == 70.0
    finally:
        db.rollback()
        db.close()


def test_una_categoria_de_sistema_no_pertenece_a_ninguna_organizacion():
    """La semilla es global; una organización puede añadir las suyas."""
    cat = MayorCategoria(codigo="IVA_COMPRAS", nombre="IVA en compras",
                         naturaleza_esperada="activo", orden=1, es_sistema=True)
    assert cat.organization_id is None
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_models.py -q`
Expected: FAIL — `ModuleNotFoundError: ...mayor.models`

- [ ] **Step 3: Implementación mínima**

`backend/app/aud/obligaciones_fiscales/mayor/models.py`:

```python
"""Persistencia del motor de mayores.

Tres tablas:
  · mayor_categorias        — catálogo configurable (semilla global + por organización)
  · mayor_homologaciones    — lo que el auditor confirmó, POR CLIENTE
  · mayor_clasificacion_job — foto inmutable de lo clasificado en cada job
"""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.session import Base


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class MayorCategoria(Base):
    """Categoría fiscal. organization_id NULL = categoría de sistema."""

    __tablename__ = "mayor_categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    codigo: Mapped[str] = mapped_column(String(32), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    naturaleza_esperada: Mapped[str] = mapped_column(String(16), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    es_sistema: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "codigo", name="uq_mayor_categoria_org_codigo"),
    )


class MayorHomologacion(Base):
    """Lo aprendido de un cliente: esta cuenta es de esta categoría.

    La clave es client_id (NO project_id) para que el aprendizaje sobreviva
    de un ejercicio fiscal al siguiente.
    """

    __tablename__ = "mayor_homologaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    codigo_cuenta: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre_norm: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    categoria: Mapped[str] = mapped_column(String(32), nullable=False)
    tarifa: Mapped[float | None] = mapped_column(Float, nullable=True)
    veces_usada: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    creada_por_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_ahora, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_ahora, nullable=False)

    __table_args__ = (
        UniqueConstraint("client_id", "codigo_cuenta", name="uq_mayor_homologacion_cliente_cuenta"),
    )


class MayorClasificacionJob(Base):
    """Qué se clasificó en un job y por qué. Alimenta la hoja de trazabilidad."""

    __tablename__ = "mayor_clasificacion_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("tool_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    codigo_cuenta: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre_cuenta: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    n_movimientos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    debe: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    haber: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    por_mes_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    categoria_sugerida: Mapped[str | None] = mapped_column(String(32), nullable=True)
    categoria_final: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tarifa: Mapped[float | None] = mapped_column(Float, nullable=True)
    confianza: Mapped[str] = mapped_column(String(8), default="baja", nullable=False)
    origen: Mapped[str] = mapped_column(String(16), default="reglas", nullable=False)
    senales_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    corregida: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    aprobada_por_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aprobada_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
```

En `backend/app/db/session.py`, dentro de `init_db()`, junto a los demás imports de modelos (después de la línea que importa `_aud_of_models`):

```python
    from backend.app.aud.obligaciones_fiscales.mayor import models as _mayor_models  # noqa: F401
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_models.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/models.py backend/app/db/session.py tests/test_of_mayor_models.py
git commit -m "feat(mayor): tablas de catalogo, homologaciones y clasificacion por job"
```

---

### Task 2: Catálogo configurable en base de datos

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/catalogo_service.py`
- Test: `tests/test_of_mayor_catalogo_service.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Semilla y consulta del catálogo de categorías."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.catalogo_service import (
    categorias_visibles,
    sembrar_categorias_de_sistema,
)
from backend.app.aud.obligaciones_fiscales.mayor.models import MayorCategoria
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_la_semilla_crea_las_siete_categorias_de_sistema():
    db = SessionLocal()
    try:
        sembrar_categorias_de_sistema(db)
        n = db.query(MayorCategoria).filter_by(es_sistema=True).count()
        assert n == 7
    finally:
        db.close()


def test_sembrar_dos_veces_no_duplica():
    db = SessionLocal()
    try:
        sembrar_categorias_de_sistema(db)
        sembrar_categorias_de_sistema(db)
        n = db.query(MayorCategoria).filter_by(es_sistema=True).count()
        assert n == 7
    finally:
        db.close()


def test_una_organizacion_ve_las_de_sistema_mas_las_suyas():
    db = SessionLocal()
    try:
        sembrar_categorias_de_sistema(db)
        db.add(MayorCategoria(organization_id=777, codigo="ICE", nombre="ICE",
                              naturaleza_esperada="pasivo", orden=8))
        db.commit()
        codigos = {c.codigo for c in categorias_visibles(db, organization_id=777)}
        assert "ICE" in codigos
        assert "IVA_COMPRAS" in codigos
        otra = {c.codigo for c in categorias_visibles(db, organization_id=888)}
        assert "ICE" not in otra
    finally:
        db.close()


def test_las_categorias_inactivas_no_se_listan():
    db = SessionLocal()
    try:
        sembrar_categorias_de_sistema(db)
        db.add(MayorCategoria(organization_id=999, codigo="VIEJA", nombre="Vieja",
                              naturaleza_esperada="pasivo", orden=9, activa=False))
        db.commit()
        codigos = {c.codigo for c in categorias_visibles(db, organization_id=999)}
        assert "VIEJA" not in codigos
    finally:
        db.close()
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_catalogo_service.py -q`
Expected: FAIL — `ModuleNotFoundError: ...mayor.catalogo_service`

- [ ] **Step 3: Implementación mínima**

```python
"""Catálogo de categorías en base de datos.

La semilla sale de `catalogo.CATEGORIAS` (la fuente en memoria que usa el
motor). Una organización puede añadir categorías propias sin tocar código.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import CATEGORIAS
from backend.app.aud.obligaciones_fiscales.mayor.models import MayorCategoria


def sembrar_categorias_de_sistema(db: Session) -> int:
    """Crea las categorías de sistema que falten. Idempotente."""
    existentes = {
        c.codigo
        for c in db.execute(
            select(MayorCategoria).where(MayorCategoria.es_sistema.is_(True))
        ).scalars()
    }
    creadas = 0
    for cat in CATEGORIAS.values():
        if cat.codigo in existentes:
            continue
        db.add(
            MayorCategoria(
                organization_id=None,
                codigo=cat.codigo,
                nombre=cat.nombre,
                naturaleza_esperada=cat.naturaleza_esperada,
                orden=cat.orden,
                es_sistema=True,
            )
        )
        creadas += 1
    if creadas:
        db.commit()
    return creadas


def categorias_visibles(db: Session, *, organization_id: int | None) -> list[MayorCategoria]:
    """Categorías de sistema + las propias de la organización, activas."""
    sembrar_categorias_de_sistema(db)
    stmt = (
        select(MayorCategoria)
        .where(
            MayorCategoria.activa.is_(True),
            (MayorCategoria.organization_id.is_(None))
            | (MayorCategoria.organization_id == organization_id),
        )
        .order_by(MayorCategoria.orden, MayorCategoria.codigo)
    )
    return list(db.execute(stmt).scalars())
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_catalogo_service.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/catalogo_service.py tests/test_of_mayor_catalogo_service.py
git commit -m "feat(mayor): catalogo de categorias configurable por organizacion"
```

---

### Task 3: Historial de homologaciones por cliente

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/homologaciones.py`
- Test: `tests/test_of_mayor_homologaciones.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Historial de homologaciones: lo que el auditor confirmó, por cliente."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.homologaciones import (
    guardar_homologaciones,
    historial_de_cliente,
)
from backend.app.aud.obligaciones_fiscales.mayor.models import MayorHomologacion
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_un_cliente_sin_historial_devuelve_diccionario_vacio():
    db = SessionLocal()
    try:
        assert historial_de_cliente(db, client_id=4242) == {}
    finally:
        db.close()


def test_guardar_y_recuperar_el_historial_como_diccionario():
    db = SessionLocal()
    try:
        guardar_homologaciones(
            db,
            client_id=4243,
            asignaciones=[
                {"codigo_cuenta": "1.1.5.1.1", "nombre_cuenta": "IVA sobre Compras",
                 "categoria": "IVA_COMPRAS", "tarifa": None},
                {"codigo_cuenta": "2.1.7.3.2", "nombre_cuenta": "Ret. 70% Servicios",
                 "categoria": "RET_IVA", "tarifa": 70.0},
            ],
            user_id=1,
        )
        assert historial_de_cliente(db, client_id=4243) == {
            "1.1.5.1.1": "IVA_COMPRAS",
            "2.1.7.3.2": "RET_IVA",
        }
    finally:
        db.close()


def test_guardar_la_misma_cuenta_otra_vez_actualiza_y_cuenta_el_uso():
    db = SessionLocal()
    try:
        datos = [{"codigo_cuenta": "4.1.1.4", "nombre_cuenta": "Venta insumos",
                  "categoria": "VENTAS", "tarifa": None}]
        guardar_homologaciones(db, client_id=4244, asignaciones=datos, user_id=1)
        guardar_homologaciones(db, client_id=4244, asignaciones=datos, user_id=1)
        fila = db.query(MayorHomologacion).filter_by(
            client_id=4244, codigo_cuenta="4.1.1.4"
        ).one()
        assert fila.veces_usada == 2


        # y si el auditor cambia de opinión, la categoría se actualiza
        guardar_homologaciones(
            db, client_id=4244,
            asignaciones=[{"codigo_cuenta": "4.1.1.4", "nombre_cuenta": "Venta insumos",
                           "categoria": "IVA_VENTAS", "tarifa": None}],
            user_id=1,
        )
        db.expire_all()
        fila = db.query(MayorHomologacion).filter_by(
            client_id=4244, codigo_cuenta="4.1.1.4"
        ).one()
        assert fila.categoria == "IVA_VENTAS"
        assert fila.veces_usada == 3
    finally:
        db.close()


def test_el_historial_de_un_cliente_no_contamina_al_de_otro():
    db = SessionLocal()
    try:
        guardar_homologaciones(
            db, client_id=4245,
            asignaciones=[{"codigo_cuenta": "1.1.5.1.1", "nombre_cuenta": "x",
                           "categoria": "IVA_COMPRAS", "tarifa": None}],
            user_id=1,
        )
        assert historial_de_cliente(db, client_id=4246) == {}
    finally:
        db.close()


def test_una_asignacion_sin_categoria_se_ignora():
    """El auditor puede dejar una cuenta sin resolver."""
    db = SessionLocal()
    try:
        guardar_homologaciones(
            db, client_id=4247,
            asignaciones=[{"codigo_cuenta": "9.9", "nombre_cuenta": "?",
                           "categoria": None, "tarifa": None}],
            user_id=1,
        )
        assert historial_de_cliente(db, client_id=4247) == {}
    finally:
        db.close()
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_homologaciones.py -q`
Expected: FAIL — `ModuleNotFoundError: ...mayor.homologaciones`

- [ ] **Step 3: Implementación mínima**

```python
"""Historial de homologaciones por cliente.

Es la memoria del motor: lo que el auditor confirmó una vez no se vuelve a
preguntar. La clave es el cliente, no el proyecto, para que lo aprendido en
el ejercicio 2025 sirva en el 2026.
"""

from __future__ import annotations

import datetime
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.mayor.models import MayorHomologacion


def _norm(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def historial_de_cliente(db: Session, *, client_id: int) -> dict[str, str]:
    """{codigo_cuenta: categoria} — el formato que espera `clasificar()`."""
    filas = db.execute(
        select(MayorHomologacion).where(MayorHomologacion.client_id == client_id)
    ).scalars()
    return {f.codigo_cuenta: f.categoria for f in filas}


def guardar_homologaciones(
    db: Session,
    *,
    client_id: int,
    asignaciones: list[dict],
    user_id: int | None = None,
) -> int:
    """Upsert de las cuentas que el auditor aprobó. Devuelve cuántas guardó."""
    ahora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    guardadas = 0
    for a in asignaciones:
        categoria = a.get("categoria")
        codigo = (a.get("codigo_cuenta") or "").strip()
        if not categoria or not codigo:
            continue
        fila = db.execute(
            select(MayorHomologacion).where(
                MayorHomologacion.client_id == client_id,
                MayorHomologacion.codigo_cuenta == codigo,
            )
        ).scalar_one_or_none()
        if fila is None:
            db.add(
                MayorHomologacion(
                    client_id=client_id,
                    codigo_cuenta=codigo,
                    nombre_norm=_norm(a.get("nombre_cuenta", "")),
                    categoria=categoria,
                    tarifa=a.get("tarifa"),
                    veces_usada=1,
                    creada_por_user_id=user_id,
                    created_at=ahora,
                    updated_at=ahora,
                )
            )
        else:
            fila.categoria = categoria
            fila.tarifa = a.get("tarifa")
            fila.nombre_norm = _norm(a.get("nombre_cuenta", "")) or fila.nombre_norm
            fila.veces_usada += 1
            fila.updated_at = ahora
            db.add(fila)
        guardadas += 1
    if guardadas:
        db.commit()
    return guardadas
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_homologaciones.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/homologaciones.py tests/test_of_mayor_homologaciones.py
git commit -m "feat(mayor): historial de homologaciones por cliente"
```

---

### Task 4: Persistencia de la clasificación de un job

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/clasificacion_service.py`
- Test: `tests/test_of_mayor_clasificacion_service.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Guardar, leer y corregir la clasificación de un job."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.clasificacion_service import (
    aplicar_correcciones,
    clasificacion_de_job,
    guardar_clasificacion,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    PerfilCuenta,
    ResultadoClasificacion,
    Senal,
)
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _resultado(codigo="2.1.7.3.2", categoria="RET_IVA", confianza="alta"):
    return ResultadoClasificacion(
        codigo=codigo, nombre="Ret. 70% Servicios", categoria=categoria,
        confianza=confianza, origen="reglas", tarifa=70.0,
        puntajes={"RET_IVA": 65},
        senales=[Senal("RET_IVA", 40, "nombre con tarifa 70.0%")],
    )


def _perfil(codigo="2.1.7.3.2"):
    return PerfilCuenta(codigo=codigo, nombre="Ret. 70% Servicios",
                        n_movimientos=149, debe=7490.42, haber=7490.42,
                        por_mes={"01": 0.0})


def test_guarda_una_fila_por_cuenta_con_su_justificacion():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9001,
                              resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        filas = clasificacion_de_job(db, job_id=9001)
        assert len(filas) == 1
        assert filas[0].categoria_sugerida == "RET_IVA"
        assert filas[0].categoria_final == "RET_IVA"
        assert filas[0].n_movimientos == 149
        assert filas[0].senales_json[0]["motivo"].startswith("nombre")
    finally:
        db.close()


def test_guardar_de_nuevo_reemplaza_la_clasificacion_anterior_del_job():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9002, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        guardar_clasificacion(db, job_id=9002, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        assert len(clasificacion_de_job(db, job_id=9002)) == 1
    finally:
        db.close()


def test_una_correccion_del_auditor_cambia_la_categoria_final_y_queda_marcada():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9003, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        n = aplicar_correcciones(
            db, job_id=9003,
            correcciones=[{"codigo_cuenta": "2.1.7.3.2", "categoria": "RET_RENTA"}],
            user_id=7,
        )
        assert n == 1
        fila = clasificacion_de_job(db, job_id=9003)[0]
        assert fila.categoria_sugerida == "RET_IVA"   # se conserva lo que dijo el motor
        assert fila.categoria_final == "RET_RENTA"    # y lo que decidió el humano
        assert fila.corregida is True
        assert fila.origen == "manual"
    finally:
        db.close()


def test_confirmar_sin_cambiar_no_marca_la_fila_como_corregida():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9004, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        aplicar_correcciones(
            db, job_id=9004,
            correcciones=[{"codigo_cuenta": "2.1.7.3.2", "categoria": "RET_IVA"}],
            user_id=7,
        )
        fila = clasificacion_de_job(db, job_id=9004)[0]
        assert fila.corregida is False
        assert fila.origen == "reglas"
    finally:
        db.close()


def test_una_correccion_para_una_cuenta_inexistente_se_ignora():
    db = SessionLocal()
    try:
        guardar_clasificacion(db, job_id=9005, resultados=[_resultado()],
                              perfiles={"2.1.7.3.2": _perfil()})
        n = aplicar_correcciones(
            db, job_id=9005,
            correcciones=[{"codigo_cuenta": "0.0.0", "categoria": "VENTAS"}],
            user_id=7,
        )
        assert n == 0
    finally:
        db.close()
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_clasificacion_service.py -q`
Expected: FAIL — `ModuleNotFoundError: ...mayor.clasificacion_service`

- [ ] **Step 3: Implementación mínima**

```python
"""Clasificación de un job: se guarda, se muestra al auditor, se corrige."""

from __future__ import annotations

import datetime
from dataclasses import asdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.mayor.models import MayorClasificacionJob
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    PerfilCuenta,
    ResultadoClasificacion,
)


def guardar_clasificacion(
    db: Session,
    *,
    job_id: int,
    resultados: list[ResultadoClasificacion],
    perfiles: dict[str, PerfilCuenta],
) -> int:
    """Reemplaza la clasificación del job por la recién calculada."""
    db.execute(delete(MayorClasificacionJob).where(MayorClasificacionJob.job_id == job_id))
    for r in resultados:
        p = perfiles.get(r.codigo)
        db.add(
            MayorClasificacionJob(
                job_id=job_id,
                codigo_cuenta=r.codigo,
                nombre_cuenta=r.nombre,
                n_movimientos=p.n_movimientos if p else 0,
                debe=p.debe if p else 0.0,
                haber=p.haber if p else 0.0,
                por_mes_json=dict(p.por_mes) if p else None,
                categoria_sugerida=r.categoria,
                categoria_final=r.categoria,
                tarifa=r.tarifa,
                confianza=r.confianza,
                origen=r.origen,
                senales_json=[asdict(s) for s in r.senales],
            )
        )
    db.commit()
    return len(resultados)


def clasificacion_de_job(db: Session, *, job_id: int) -> list[MayorClasificacionJob]:
    stmt = (
        select(MayorClasificacionJob)
        .where(MayorClasificacionJob.job_id == job_id)
        .order_by(MayorClasificacionJob.codigo_cuenta)
    )
    return list(db.execute(stmt).scalars())


def aplicar_correcciones(
    db: Session,
    *,
    job_id: int,
    correcciones: list[dict],
    user_id: int | None = None,
) -> int:
    """Aplica lo que decidió el auditor. Devuelve cuántas filas tocó."""
    ahora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    por_codigo = {f.codigo_cuenta: f for f in clasificacion_de_job(db, job_id=job_id)}
    tocadas = 0
    for c in correcciones:
        fila = por_codigo.get((c.get("codigo_cuenta") or "").strip())
        if fila is None:
            continue
        nueva = c.get("categoria")
        if nueva != fila.categoria_final:
            fila.categoria_final = nueva
            fila.corregida = True
            fila.origen = "manual"
        fila.aprobada_por_user_id = user_id
        fila.aprobada_at = ahora
        db.add(fila)
        tocadas += 1
    if tocadas:
        db.commit()
    return tocadas
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_clasificacion_service.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/clasificacion_service.py tests/test_of_mayor_clasificacion_service.py
git commit -m "feat(mayor): persistencia y correccion de la clasificacion por job"
```

---

### Task 5: El job nace en borrador y mueren los slots de mayores separados

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/models.py`, `service.py`, `router.py`, `jobs.py`, `file_storage.py` (docstring)
- Modify: `backend/app/db/session.py` (ALTER idempotente)
- Test: `tests/test_aud_of_router.py`

- [ ] **Step 1: Escribir el test que falla**

Añadir a `tests/test_aud_of_router.py`:

```python
def test_crear_job_sin_archivos_lo_deja_en_borrador(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "borrador"


def test_ya_no_existen_los_slots_de_mayor_de_compras_y_ventas(client):
    from backend.app.aud.obligaciones_fiscales import router as router_mod

    assert "mayor_compras" not in router_mod.ALLOWED_MIMES
    assert "mayor_ventas" not in router_mod.ALLOWED_MIMES
    assert "mayor_general" in router_mod.ALLOWED_MIMES
    assert "mayor_especifico" in router_mod.ALLOWED_MIMES
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_aud_of_router.py -q -k "borrador or slots_de_mayor"`
Expected: FAIL — el primero da 400 (`Sube al menos 1 PDF F-103 o F-104`); el segundo falla por `mayor_compras` presente.

- [ ] **Step 3: Implementación mínima**

En `models.py`, dentro de `ToolJob`, después de `firma_auditora`:

```python
    # Modalidad manual: mayor de una sola categoría declarada por el auditor.
    mayor_especifico_categoria: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
```

En `service.py::create_job`, cambiar el `status` inicial:

```python
        status="borrador",
```

En `db/session.py::init_db()`, después del bloque de ALTER de `users`, añadir:

```python
    # Migración aditiva en ``tool_jobs``: modalidad manual del mayor.
    if "tool_jobs" in inspector.get_table_names():
        cols_jobs = {c["name"] for c in inspector.get_columns("tool_jobs")}
        if "mayor_especifico_categoria" not in cols_jobs:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE tool_jobs ADD COLUMN mayor_especifico_categoria VARCHAR(32)")
                )
```

En `router.py`:
- Reemplazar las entradas `mayor_compras`/`mayor_ventas` de `ALLOWED_MIMES` por:

```python
    "mayor_general": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
    },
    "mayor_especifico": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
    },
```

- En `create_job_endpoint`: eliminar los parámetros `files_f103`, `files_f104`, `files_ats`, `mayor_compras`, `mayor_ventas`, `file_f101`, la validación `has_any`, el bloque `try` que guarda archivos y el `background_tasks.add_task(...)`. El endpoint queda:

```python
@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job_endpoint(
    project_id: int = Form(...),
    cliente_name: str = Form(...),
    period_label: str = Form(...),
    period_start: datetime.date | None = Form(None),
    period_end: datetime.date | None = Form(None),
    prepared_by_name: str | None = Form(None),
    reviewed_by_name: str | None = Form(None),
    firma_auditora: str | None = Form(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea el job en estado 'borrador'. Los archivos se suben por slot."""
    from backend.app.aud.obligaciones_fiscales.schemas import FIRMAS_VALIDAS

    if firma_auditora and firma_auditora not in FIRMAS_VALIDAS:
        raise HTTPException(
            400, detail=f"firma_auditora debe ser uno de: {sorted(FIRMAS_VALIDAS)}"
        )
    try:
        job = service.create_job(
            db, user=current, project_id=project_id,
            cliente_name=cliente_name, period_label=period_label,
            period_start=period_start, period_end=period_end,
            prepared_by_name=prepared_by_name, reviewed_by_name=reviewed_by_name,
            firma_auditora=firma_auditora,
        )
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    file_storage.create_job_dir(job.id)
    return JobOut.model_validate(job)
```

- En `jobs.py`, quitar de `inputs` las claves `mayor_compras` y `mayor_ventas`.
- En `file_storage.py`, actualizar el docstring de la estructura de carpetas (`mayor_general/`, `mayor_especifico/`).
- En `schemas.py`, añadir `mayor_especifico_categoria: str | None` a `JobOut`.

**Tests existentes que van a romperse**: los de `test_aud_of_router.py` que creaban el job con archivos en el mismo POST. Actualízalos para el flujo nuevo (crear borrador → subir slot), NO los borres. Repórtalo en tu resumen.

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_aud_of_router.py tests/test_aud_of_service.py tests/test_aud_of_models.py -q`
Expected: todos verdes.

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/ backend/app/db/session.py tests/test_aud_of_router.py
git commit -m "feat(aud-of): el job nace en borrador y se eliminan los mayores separados"
```

---

### Task 6: Subida incremental por slot

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/router.py`, `schemas.py`
- Test: `tests/test_aud_of_slots.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Subida incremental de archivos por slot (chips del workspace)."""

import io

import pytest

from tests.test_aud_of_router import _h, _mk_admin_project  # noqa: F401
from tests.test_aud_of_router import _db  # noqa: F401


def _crear_borrador(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    return tok, r.json()["id"]


def _pdf():
    return ("d.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")


def test_subir_un_pdf_al_slot_f104(client):
    tok, jid = _crear_borrador(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(tok), files=[("archivos", _pdf())],
    )
    assert r.status_code == 200, r.text
    assert r.json()["f104"]["n_archivos"] == 1


def test_subir_dos_veces_al_mismo_slot_acumula(client):
    tok, jid = _crear_borrador(client)
    url = f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104"
    client.put(url, headers=_h(tok), files=[("archivos", ("a.pdf", io.BytesIO(b"%PDF a"), "application/pdf"))])
    r = client.put(url, headers=_h(tok), files=[("archivos", ("b.pdf", io.BytesIO(b"%PDF b"), "application/pdf"))])
    assert r.json()["f104"]["n_archivos"] == 2


def test_quitar_un_slot_lo_deja_vacio(client):
    tok, jid = _crear_borrador(client)
    url = f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104"
    client.put(url, headers=_h(tok), files=[("archivos", _pdf())])
    r = client.delete(url, headers=_h(tok))
    assert r.status_code == 200
    assert r.json()["f104"]["n_archivos"] == 0


def test_el_estado_de_los_slots_sobrevive_a_una_recarga(client):
    tok, jid = _crear_borrador(client)
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(tok), files=[("archivos", _pdf())],
    )
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots", headers=_h(tok))
    assert r.status_code == 200
    assert r.json()["f104"]["n_archivos"] == 1
    assert r.json()["f103"]["n_archivos"] == 0


def test_un_slot_inexistente_da_400(client):
    tok, jid = _crear_borrador(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/inventado",
        headers=_h(tok), files=[("archivos", _pdf())],
    )
    assert r.status_code == 400


def test_un_excel_en_el_slot_de_pdfs_es_rechazado(client):
    tok, jid = _crear_borrador(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(tok),
        files=[("archivos", ("m.xlsx", io.BytesIO(b"PK"), "application/vnd.ms-excel"))],
    )
    assert r.status_code == 415


def test_el_mayor_especifico_exige_declarar_la_categoria(client):
    tok, jid = _crear_borrador(client)
    xlsx = ("m.xlsx", io.BytesIO(b"PK"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/mayor_especifico",
        headers=_h(tok), files=[("archivos", xlsx)],
    )
    assert r.status_code == 400
    assert "categoria" in r.text.lower()


def test_el_mayor_especifico_guarda_la_categoria_declarada(client):
    tok, jid = _crear_borrador(client)
    xlsx = ("m.xlsx", io.BytesIO(b"PK"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/mayor_especifico",
        headers=_h(tok), files=[("archivos", xlsx)], data={"categoria": "RET_IVA"},
    )
    assert r.status_code == 200
    r2 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r2.json()["mayor_especifico_categoria"] == "RET_IVA"


def test_un_usuario_de_otra_organizacion_no_puede_subir_al_job(client):
    tok, jid = _crear_borrador(client)
    otro_tok, _ = _mk_admin_project(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(otro_tok), files=[("archivos", _pdf())],
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_aud_of_slots.py -q`
Expected: FAIL con 404/405 — los endpoints de slots no existen.

- [ ] **Step 3: Implementación mínima**

En `schemas.py`:

```python
class SlotEstado(BaseModel):
    n_archivos: int
    nombres: list[str]


SLOTS_VALIDOS = (
    "f104", "f103", "ats", "mayor_general", "mayor_especifico", "f101",
)
```

En `router.py`, añadir:

```python
from backend.app.aud.obligaciones_fiscales.schemas import SLOTS_VALIDOS


def _estado_slots(job_id: int) -> dict[str, dict]:
    d = file_storage.job_dir(job_id)
    estado = {}
    for slot in SLOTS_VALIDOS:
        archivos = file_storage.list_inputs(d, slot)
        estado[slot] = {"n_archivos": len(archivos), "nombres": [p.name for p in archivos]}
    return estado


def _job_editable(db, current, job_id: int):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status not in ("borrador", "revision"):
        raise HTTPException(
            409, detail=f"El job está en estado {job.status}: ya no admite cambios de archivos."
        )
    return job


@router.put("/jobs/{job_id}/slots/{slot}")
async def upload_slot_endpoint(
    job_id: int,
    slot: str,
    archivos: list[UploadFile] = File(...),
    categoria: str | None = Form(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if slot not in SLOTS_VALIDOS:
        raise HTTPException(400, detail=f"Slot desconocido: {slot}")
    job = _job_editable(db, current, job_id)

    if slot == "mayor_especifico" and not categoria:
        raise HTTPException(
            400,
            detail="El mayor específico exige declarar la categoria a la que pertenece.",
        )

    job_dir = file_storage.create_job_dir(job_id)
    await _save_files(job_dir, slot, archivos)

    if slot == "mayor_especifico":
        job.mayor_especifico_categoria = categoria
        db.add(job)
        db.commit()
    return _estado_slots(job_id)


@router.delete("/jobs/{job_id}/slots/{slot}")
def clear_slot_endpoint(
    job_id: int,
    slot: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if slot not in SLOTS_VALIDOS:
        raise HTTPException(400, detail=f"Slot desconocido: {slot}")
    _job_editable(db, current, job_id)
    for p in file_storage.list_inputs(file_storage.job_dir(job_id), slot):
        p.unlink(missing_ok=True)
    return _estado_slots(job_id)


@router.get("/jobs/{job_id}/slots")
def get_slots_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return _estado_slots(job_id)
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_aud_of_slots.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/router.py backend/app/aud/obligaciones_fiscales/schemas.py tests/test_aud_of_slots.py
git commit -m "feat(aud-of): subida incremental de archivos por slot"
```

---

### Task 7: Fase 1 — procesar el mayor y pasar a revisión

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/jobs.py`, `service.py`, `router.py`
- Test: `tests/test_aud_of_fase1.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Fase 1: leer el mayor, clasificar y dejar el job en revisión."""

import io

from openpyxl import Workbook

from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401

ENCABEZADO = ("Código", "Cuenta", "Fecha", "Asiento", "Documento", "Identificación",
              "Persona", "Persona Cruce Cuenta", "Descripción", "Debe", "Haber", "Saldo")

FILAS = [
    ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 1", "", "", "", "", "", 10.0, 0, 10.0],
    ["4.1.1.4", "Venta de insumos", "2025-01-06", "VTA 1", "", "", "", "", "", 0, 100.0, -100.0],
    ["2.1.7.3.2", "Ret. 70% Servicios", "2025-01-07", "RET 1", "", "", "", "", "", 0, 7.0, -7.0],
]


def _mayor_bytes():
    wb = Workbook()
    ws = wb.active
    ws.append(list(ENCABEZADO))
    for f in FILAS:
        ws.append(f)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _borrador_con_mayor(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/mayor_general",
        headers=_h(tok),
        files=[("archivos", ("mayor.xlsx", io.BytesIO(_mayor_bytes()),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    return tok, jid


def test_procesar_deja_el_job_en_revision(client):
    tok, jid = _borrador_con_mayor(client)
    r = client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    assert r.status_code == 200, r.text
    r2 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r2.json()["status"] == "revision"


def test_la_clasificacion_queda_disponible_para_la_pantalla_de_revision(client):
    tok, jid = _borrador_con_mayor(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion", headers=_h(tok))
    assert r.status_code == 200
    cuentas = {c["codigo_cuenta"]: c for c in r.json()["cuentas"]}
    assert cuentas["1.1.5.1.1"]["categoria_final"] == "IVA_COMPRAS"
    assert cuentas["4.1.1.4"]["categoria_final"] == "VENTAS"
    assert cuentas["2.1.7.3.2"]["categoria_final"] == "RET_IVA"
    assert cuentas["2.1.7.3.2"]["tarifa"] == 70.0


def test_la_respuesta_trae_las_categorias_disponibles_para_el_selector(client):
    tok, jid = _borrador_con_mayor(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion", headers=_h(tok))
    codigos = {c["codigo"] for c in r.json()["categorias"]}
    assert "IVA_COMPRAS" in codigos and "VENTAS" in codigos


def test_cada_cuenta_explica_por_que_quedo_ahi(client):
    tok, jid = _borrador_con_mayor(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion", headers=_h(tok))
    cuenta = next(c for c in r.json()["cuentas"] if c["codigo_cuenta"] == "1.1.5.1.1")
    assert cuenta["justificacion"], "la pantalla necesita el porqué de cada clasificación"


def test_procesar_sin_mayor_general_da_400(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    r2 = client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    assert r2.status_code == 400
    assert "mayor" in r2.text.lower()


def test_un_mayor_ilegible_deja_el_job_en_failed_con_el_motivo(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/mayor_general",
        headers=_h(tok),
        files=[("archivos", ("roto.xlsx", io.BytesIO(b"no soy un excel"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    r2 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r2.json()["status"] == "failed"
    assert r2.json()["error_message"]
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_aud_of_fase1.py -q`
Expected: FAIL — no existe `/procesar`.

- [ ] **Step 3: Implementación mínima**

En `service.py`, añadir:

```python
def mark_revision(db: Session, job_id: int, summary: dict | None = None) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = "revision"
        if summary is not None:
            job.summary_json = summary
        db.add(job)
        db.commit()
```

En `jobs.py`, añadir la fase 1 (arriba de `process_job`):

```python
def clasificar_mayor_job(job_id: int) -> None:
    """FASE 1: lee el Mayor General, clasifica sus cuentas y deja el job en
    'revision' para que el auditor apruebe."""
    from backend.app.aud.obligaciones_fiscales.mayor import (
        clasificacion_service,
        homologaciones,
    )
    from backend.app.aud.obligaciones_fiscales.mayor.clasificador import clasificar
    from backend.app.aud.obligaciones_fiscales.mayor.cuentas import perfilar
    from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor
    from backend.app.context.models import Project

    db = SessionLocal()
    try:
        service.mark_running(db, job_id)
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("clasificar_mayor_job: ToolJob %s not found", job_id)
            return

        rutas = file_storage.list_inputs(file_storage.job_dir(job_id), "mayor_general")
        if not rutas:
            service.mark_failed(db, job_id, "No hay Mayor General cargado.")
            return

        movimientos = []
        errores: list[str] = []
        hojas: list[str] = []
        for ruta in rutas:
            lectura = leer_mayor(ruta.read_bytes())
            if not lectura.mapeo_suficiente:
                service.mark_failed(
                    db, job_id,
                    f"{ruta.name}: no se reconocieron las columnas mínimas "
                    f"(faltan {', '.join(lectura.columnas_faltantes)}). "
                    f"Errores: {'; '.join(lectura.errores) or 'ninguno'}",
                )
                return
            movimientos.extend(lectura.movimientos)
            errores.extend(lectura.errores)
            hojas.extend(lectura.hojas_leidas)

        proyecto = db.get(Project, job.project_id)
        historial = homologaciones.historial_de_cliente(db, client_id=proyecto.client_id)

        perfiles = perfilar(movimientos)
        resultados = clasificar(perfiles, historial=historial)
        clasificacion_service.guardar_clasificacion(
            db, job_id=job_id, resultados=resultados, perfiles=perfiles
        )

        por_confianza: dict[str, int] = {}
        for r in resultados:
            por_confianza[r.confianza] = por_confianza.get(r.confianza, 0) + 1

        service.mark_revision(db, job_id, {
            "movimientos_leidos": len(movimientos),
            "cuentas": len(perfiles),
            "hojas_leidas": hojas,
            "por_confianza": por_confianza,
            "requieren_revision": sum(
                n for c, n in por_confianza.items() if c in ("media", "baja")
            ),
            "errores_lectura": errores[:10],
        })
        log.info("job %s clasificado: %s cuentas", job_id, len(perfiles))
    except Exception as e:  # noqa: BLE001
        log.exception("clasificar_mayor_job %s failed", job_id)
        try:
            service.mark_failed(db, job_id, str(e))
        except Exception:
            log.exception("could not mark job %s as failed", job_id)
    finally:
        db.close()
```

En `router.py`:

```python
@router.post("/jobs/{job_id}/procesar", response_model=JobOut)
def procesar_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fase 1: clasifica el Mayor General y deja el job listo para revisión."""
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status not in ("borrador", "revision", "failed"):
        raise HTTPException(409, detail=f"El job está en estado {job.status}.")
    if not file_storage.list_inputs(file_storage.job_dir(job_id), "mayor_general"):
        raise HTTPException(400, detail="Sube el Mayor General de Impuestos antes de procesar.")

    jobs.clasificar_mayor_job(job_id)
    db.expire_all()
    return JobOut.model_validate(service.get_job(db, current, job_id))


@router.get("/jobs/{job_id}/clasificacion")
def get_clasificacion_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.aud.obligaciones_fiscales.mayor import (
        catalogo_service,
        clasificacion_service,
    )

    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    filas = clasificacion_service.clasificacion_de_job(db, job_id=job_id)
    categorias = catalogo_service.categorias_visibles(
        db, organization_id=getattr(current, "organization_id", None)
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "cuentas": [
            {
                "codigo_cuenta": f.codigo_cuenta,
                "nombre_cuenta": f.nombre_cuenta,
                "n_movimientos": f.n_movimientos,
                "debe": f.debe,
                "haber": f.haber,
                "categoria_sugerida": f.categoria_sugerida,
                "categoria_final": f.categoria_final,
                "tarifa": f.tarifa,
                "confianza": f.confianza,
                "origen": f.origen,
                "corregida": f.corregida,
                "justificacion": [
                    s.get("motivo", "")
                    for s in (f.senales_json or [])
                    if s.get("categoria") == f.categoria_final and s.get("puntaje", 0) > 0
                ],
            }
            for f in filas
        ],
        "categorias": [
            {"codigo": c.codigo, "nombre": c.nombre,
             "naturaleza_esperada": c.naturaleza_esperada}
            for c in categorias
        ],
    }
```

Nota de diseño: la fase 1 se ejecuta **síncrona** dentro del request. Leer y clasificar un mayor de 4.680 movimientos toma ~1 segundo; no justifica un BackgroundTask, y así el frontend recibe el estado final sin hacer polling.

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_aud_of_fase1.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/ tests/test_aud_of_fase1.py
git commit -m "feat(aud-of): fase 1 clasifica el mayor y deja el job en revision"
```

---

### Task 8: Correcciones del auditor y aprobación

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/router.py`, `jobs.py`
- Test: `tests/test_aud_of_aprobacion.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""El auditor corrige, aprueba, y lo aprendido queda para el próximo año."""

from tests.test_aud_of_fase1 import _borrador_con_mayor  # noqa: F401
from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401


def _procesado(client):
    tok, jid = _borrador_con_mayor(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/procesar", headers=_h(tok))
    return tok, jid


def test_corregir_una_cuenta_cambia_su_categoria_final(client):
    tok, jid = _procesado(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion",
        headers=_h(tok),
        json={"correcciones": [{"codigo_cuenta": "4.1.1.4", "categoria": "IVA_VENTAS"}]},
    )
    assert r.status_code == 200, r.text
    cuentas = {c["codigo_cuenta"]: c for c in r.json()["cuentas"]}
    assert cuentas["4.1.1.4"]["categoria_final"] == "IVA_VENTAS"
    assert cuentas["4.1.1.4"]["categoria_sugerida"] == "VENTAS"
    assert cuentas["4.1.1.4"]["corregida"] is True


def test_no_se_puede_corregir_hacia_una_categoria_inexistente(client):
    tok, jid = _procesado(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion",
        headers=_h(tok),
        json={"correcciones": [{"codigo_cuenta": "4.1.1.4", "categoria": "NO_EXISTE"}]},
    )
    assert r.status_code == 400


def test_aprobar_genera_el_excel_y_deja_el_job_en_done(client):
    tok, jid = _procesado(client)
    r = client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/aprobar", headers=_h(tok))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"
    d = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/download", headers=_h(tok))
    assert d.status_code == 200


def test_aprobar_guarda_lo_aprendido_en_el_historial_del_cliente(client):
    tok, jid = _procesado(client)
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/aprobar", headers=_h(tok))

    from backend.app.aud.obligaciones_fiscales.mayor.models import MayorHomologacion
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        filas = db.query(MayorHomologacion).all()
        por_codigo = {f.codigo_cuenta: f.categoria for f in filas}
        assert por_codigo["1.1.5.1.1"] == "IVA_COMPRAS"
        assert por_codigo["2.1.7.3.2"] == "RET_IVA"
    finally:
        db.close()


def test_el_segundo_job_del_mismo_cliente_ya_llega_clasificado_por_historial(client):
    tok, jid = _procesado(client)
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/clasificacion",
        headers=_h(tok),
        json={"correcciones": [{"codigo_cuenta": "4.1.1.4", "categoria": "IVA_VENTAS"}]},
    )
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/aprobar", headers=_h(tok))

    # mismo proyecto (mismo cliente), nuevo job
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    pid = r.json()["project_id"]
    from tests.test_aud_of_fase1 import _mayor_bytes
    import io

    r2 = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2026"},
    )
    jid2 = r2.json()["id"]
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid2}/slots/mayor_general",
        headers=_h(tok),
        files=[("archivos", ("mayor.xlsx", io.BytesIO(_mayor_bytes()),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid2}/procesar", headers=_h(tok))
    r3 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid2}/clasificacion", headers=_h(tok))
    cuentas = {c["codigo_cuenta"]: c for c in r3.json()["cuentas"]}
    assert cuentas["4.1.1.4"]["categoria_final"] == "IVA_VENTAS"
    assert cuentas["4.1.1.4"]["origen"] == "historial"


def test_aprobar_un_job_que_no_esta_en_revision_da_409(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs", headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    r2 = client.post(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/aprobar", headers=_h(tok))
    assert r2.status_code == 409
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_aud_of_aprobacion.py -q`
Expected: FAIL — no existen `PUT /clasificacion` ni `POST /aprobar`.

- [ ] **Step 3: Implementación mínima**

En `schemas.py`:

```python
class CorreccionIn(BaseModel):
    codigo_cuenta: str
    categoria: str | None = None


class CorreccionesIn(BaseModel):
    correcciones: list[CorreccionIn] = []
```

En `router.py`:

```python
@router.put("/jobs/{job_id}/clasificacion")
def put_clasificacion_endpoint(
    job_id: int,
    payload: CorreccionesIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.aud.obligaciones_fiscales.mayor import (
        catalogo_service,
        clasificacion_service,
    )

    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status != "revision":
        raise HTTPException(409, detail=f"El job está en estado {job.status}.")

    validas = {
        c.codigo
        for c in catalogo_service.categorias_visibles(
            db, organization_id=getattr(current, "organization_id", None)
        )
    }
    for c in payload.correcciones:
        if c.categoria and c.categoria not in validas:
            raise HTTPException(400, detail=f"Categoría desconocida: {c.categoria}")

    clasificacion_service.aplicar_correcciones(
        db, job_id=job_id,
        correcciones=[c.model_dump() for c in payload.correcciones],
        user_id=current.id,
    )
    return get_clasificacion_endpoint(job_id, current=current, db=db)


@router.post("/jobs/{job_id}/aprobar", response_model=JobOut)
def aprobar_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persiste lo aprendido y dispara la fase 2 (generación del Excel)."""
    from backend.app.aud.obligaciones_fiscales.mayor import (
        clasificacion_service,
        homologaciones,
    )
    from backend.app.context.models import Project

    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status != "revision":
        raise HTTPException(
            409, detail=f"El job está en estado {job.status}: no hay nada que aprobar."
        )

    filas = clasificacion_service.clasificacion_de_job(db, job_id=job_id)
    proyecto = db.get(Project, job.project_id)
    homologaciones.guardar_homologaciones(
        db,
        client_id=proyecto.client_id,
        asignaciones=[
            {"codigo_cuenta": f.codigo_cuenta, "nombre_cuenta": f.nombre_cuenta,
             "categoria": f.categoria_final, "tarifa": f.tarifa}
            for f in filas
        ],
        user_id=current.id,
    )

    jobs.process_job(job_id)
    db.expire_all()
    return JobOut.model_validate(service.get_job(db, current, job_id))
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_aud_of_aprobacion.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/ tests/test_aud_of_aprobacion.py
git commit -m "feat(aud-of): correccion, aprobacion y aprendizaje de homologaciones"
```

---

### Task 9: Endpoint del catálogo de categorías

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/router.py`
- Test: `tests/test_aud_of_categorias.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Catálogo de categorías expuesto a la consola."""

from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401


def test_lista_las_categorias_de_sistema(client):
    tok, _ = _mk_admin_project(client)
    r = client.get("/api/v1/aud/obligaciones-fiscales/categorias", headers=_h(tok))
    assert r.status_code == 200
    codigos = {c["codigo"] for c in r.json()}
    assert {"IVA_COMPRAS", "IVA_VENTAS", "RET_RENTA", "RET_IVA", "VENTAS"} <= codigos


def test_sin_autenticacion_devuelve_401(client):
    r = client.get("/api/v1/aud/obligaciones-fiscales/categorias")
    assert r.status_code == 401
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_aud_of_categorias.py -q`
Expected: FAIL — 404.

- [ ] **Step 3: Implementación mínima**

```python
@router.get("/categorias")
def list_categorias_endpoint(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.aud.obligaciones_fiscales.mayor import catalogo_service

    return [
        {"codigo": c.codigo, "nombre": c.nombre,
         "naturaleza_esperada": c.naturaleza_esperada, "es_sistema": c.es_sistema}
        for c in catalogo_service.categorias_visibles(
            db, organization_id=getattr(current, "organization_id", None)
        )
    ]
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_aud_of_categorias.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/router.py tests/test_aud_of_categorias.py
git commit -m "feat(aud-of): endpoint del catalogo de categorias fiscales"
```

---

### Task 10: Limpieza de textos y cierre

**Files:**
- Modify: `frontend/src/aud/strings.js`
- Modify: `docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md`

- [ ] **Step 1: Actualizar los textos del frontend**

En `frontend/src/aud/strings.js`, eliminar `of_slot_mayor_compras` y `of_slot_mayor_ventas`, y añadir:

```javascript
  of_slot_mayor_general: "Mayor General de Impuestos (Excel) — requerido",
  of_slot_mayor_especifico: "Mayor específico para prueba puntual (Excel) — opcional",
  of_mayor_especifico_categoria: "¿A qué categoría corresponde?",
```

(El componente que los consume se reescribe en el Plan 4; aquí solo se dejan los textos listos y se quitan los muertos.)

- [ ] **Step 2: Verificar que el frontend sigue compilando**

Run: `cd frontend && npm run build`
Expected: build sin errores.

- [ ] **Step 3: Marcar el avance en el spec**

En la sección "Endpoints nuevos / modificados" del spec, añadir al final: `Implementado en el Plan 2 (2026-08-04).`

- [ ] **Step 4: Correr la suite completa**

Run: `python -m pytest tests/ -q -p no:warnings --tb=no -rf`
Expected: sin fallos nuevos respecto de la línea base conocida (6 fallos legacy pre-existentes en `test_chat.py`, `test_context.py` ×4 y `test_sandbox.py`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/aud/strings.js docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md
git commit -m "chore(aud-of): textos del mayor general y cierre del plan 2"
```

---

## Criterio de terminado del Plan 2

- [ ] Las 10 tareas están commiteadas.
- [ ] El ciclo completo funciona end-to-end vía HTTP: crear borrador → subir slots → procesar → revisar → corregir → aprobar → descargar.
- [ ] Lo corregido por el auditor se guarda como homologación del cliente, y un segundo job del mismo cliente llega con esas cuentas ya clasificadas con `origen="historial"`.
- [ ] Un usuario de otra organización recibe 403 en todos los endpoints nuevos.
- [ ] `mayor_compras` y `mayor_ventas` no existen en ninguna parte del backend.
- [ ] La suite completa no tiene fallos nuevos.

## Lo que este plan deliberadamente NO hace

- No genera aún el libro DM de 11 pestañas: la fase 2 sigue llamando al `excel_assembler` actual (Plan 3 lo reemplaza).
- No toca el frontend más allá de los textos (Plan 4).
- No implementa la pantalla de mapeo manual de columnas: el backend ya reporta `columnas_faltantes`, la UI llega en el Plan 4.
- No implementa DM8 (ATS) ni la facturación electrónica: siguen pendientes de definición.
