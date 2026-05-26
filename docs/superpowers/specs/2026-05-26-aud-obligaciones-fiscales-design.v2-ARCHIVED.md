# Spec — Herramienta `AUD.IMPUESTOS.OBLIGACIONES_FISCALES`

**Fecha:** 2026-05-26
**Autor:** Jorge Calupiña (jcalupinia@auditconsulting.ec)
**Co-diseño:** Claude (Opus 4.7)
**Estado:** Diseño v2 — espera revisión del usuario
**Reemplaza:** `2026-05-26-aud-retenciones-fuente-design.v1-ARCHIVED.md` (alcance subestimado por desconocer la plantilla real)

---

## 0. Resumen ejecutivo

AuditBrain construye una **plataforma de pruebas de auditoría a través de herramientas**, organizada en un catálogo de 15 categorías dentro del módulo AUD (External Audit). La primera herramienta concreta del catálogo es **"Auditoría de Obligaciones Fiscales"** bajo la categoría "Impuestos", que automatiza la generación del papel de trabajo `DM Obligaciones Fiscales` (Ecuador SRI) — 11 cédulas integradas con cross-references.

El modelo de dominio introduce el concepto de **WorkingPaper persistente** (una instancia por Cliente × Período × Herramienta) con workflow de auditoría (borrador → en revisión → firmado → archivado). Los archivos subidos por el cliente y los resultados de cada cédula se acumulan en el WorkingPaper a lo largo del tiempo, y el output final es un Excel idéntico a la plantilla.

**Alcance del spec:** plataforma base + herramienta completa, descompuesta en **7 milestones** (M1.1 a M1.7) construidos incrementalmente. Duración estimada: ~6 meses con el equipo actual (usuario + Claude).

---

## 1. Contexto

### Plataforma existente (no se modifica)

AuditBrain v4.0.0 desplegado en Render: FastAPI + React (SPA Vite) + PostgreSQL + JWT auth multi-tenant. Modelo de contexto: Organization → Client → Project. Módulos sectoriales (ADV, AUD, TAX, LEG, FIN, CYB, DATA, AUT, GOV, MKT, CRE) y de operación (DSH, DOC, RUN, WKS, USR, SEC). Tier 0 sandbox para ejecución Python. Servicio documental externo (`universal-creador-documentos.onrender.com`).

### Caso de uso motivador real

El usuario ejecuta auditorías tributarias a empresas ecuatorianas. Hoy lo hace **manualmente** llenando un Excel plantilla "DM Obligaciones Fiscales" con 11 cédulas para cada cliente × período. Inputs típicos: 12 declaraciones F-103 (retenciones en la fuente) en PDF, 12 declaraciones F-104 (IVA) en PDF, 12 anexos ATS en XML, mayores contables (Excel), declaración anual de renta F-101 (PDF). Outputs: el Excel completo conciliado con hallazgos.

Volumen real esperado: 10–50 clientes × 1 papel/año cada uno = ~50 papeles activos simultáneos.

### Plantilla de referencia analizada

`DM - Obligaciones Fiscales Final.xlsx` (304 KB, 11 pestañas). Cliente referencia: NEGOCIOS MORACOSTA S.A., período 2025-12-31. Cada pestaña tiene encabezado estándar (cliente, periodo, preparado por, revisado por, fecha, referencia DM*), fórmulas inter-celda (ej `{7}={1*6}`) y formato visual específico.

---

## 2. Decisiones arquitectónicas (capturadas durante brainstorming v2)

| Decisión | Valor | Justificación |
|---|---|---|
| Arquitectura general | Extender plataforma AuditBrain existente | Reusa auth, multi-tenant, UI shell, servicio documental |
| Ubicación en UI | Módulo AUD > tab "Análisis" > "Pruebas de auditoría a través de herramientas" > Categoría "Impuestos" > "Auditoría de Obligaciones Fiscales" | Coherente con catálogo de 15 categorías |
| Catálogo en M1.1 | Mostrar las 15 categorías (mayoría con "Próximamente") | Comunica la visión completa |
| Modelo conceptual | **WorkingPaper persistente** (1 por Cliente × Período × Herramienta) | Refleja flujo real de auditoría: el papel se construye a lo largo del tiempo |
| Workflow | borrador → en revisión → firmado → archivado | Workflow estándar de auditoría externa con roles preparador/revisor/firmante |
| Inmutabilidad | Una vez firmado, el WorkingPaper queda inmutable (excepto archivado) | Requisito profesional |
| Granularidad de herramienta | UNA herramienta integral que produce las 11 cédulas | Decisión del usuario |
| Orden de construcción | Plumbing → DM6 IVA → DM7 Retenciones → DM/DM1/DM2 → DM3/DM4/DM5 → DM8 → DM9/DM10 + Excel render | DM6 es la cédula más usada |
| Tipos de archivo aceptados | F-103, F-104, ATS XML, Mayor Compras (Excel), Mayor Ventas (Excel), F-101, OTRO | Cubre todos los inputs del papel real |
| Storage | Cloudflare R2 (S3-compatible) | Decisión confirmada del usuario |
| Jobs async | FastAPI BackgroundTasks (MVP) | Migración a RQ/Celery diferida |
| Idioma plataforma | Español (i18n EN diferido) | Confirmado |
| Auth | JWT existente (email + password) | Sin cambios |
| Onboarding clientes | Solo invitación manual por admin | Sin cambios |
| Stack | El existente: FastAPI + React + Postgres + Render + boto3 (R2) | No se introduce nada nuevo salvo R2 |

---

## 3. Modelo de dominio

### 3.1. Vista conceptual

```
Module AUD (External Audit)
 └─ Workspace cognitivo del proyecto activo
     └─ Tab "Análisis"
         └─ Sección "Pruebas de auditoría a través de herramientas"
             └─ Catálogo de 15 categorías
                 ├─ 📁 Planificación              ← Próximamente (M2+)
                 ├─ 📁 Caja y bancos              ← Próximamente
                 ├─ 📁 Inversiones                ← Próximamente
                 ├─ 📁 Cuentas por cobrar         ← Próximamente
                 ├─ 📁 Inventarios                ← Próximamente
                 ├─ 📁 Activos fijos              ← Próximamente
                 ├─ 📁 Activos intangibles e impuestos diferidos ← Próximamente
                 ├─ 📁 Proveedores y cuentas por pagar ← Próximamente
                 ├─ 📁 Préstamos y obligaciones financieras ← Próximamente
                 ├─ 📁 Patrimonio                 ← Próximamente
                 ├─ 📁 Ingresos                   ← Próximamente
                 ├─ 📁 Costos y gastos            ← Próximamente
                 ├─ 📁 Nómina                     ← Próximamente
                 ├─ 📁 Impuestos                  ← ACTIVA (1 herramienta)
                 │     └─ 🔧 Auditoría de Obligaciones Fiscales
                 │             ├─ WorkingPaper #1: "DM Negocios Moracosta 2025"
                 │             ├─ WorkingPaper #2: "DM Otra Empresa 2024"
                 │             └─ [+ Nuevo papel de trabajo]
                 └─ 📁 Conclusión y dictamen      ← Próximamente
```

### 3.2. Estados del WorkingPaper

```
draft  ─▶  in_review  ─▶  signed  ─▶  archived
   │           │             │
   │           │             └─ inmutable (excepto archive)
   │           │                 audit_events registrados
   │           │
   │           └─ revisor diferente al preparador
   │              puede devolver a draft con comentario
   │
   └─ totalmente editable
      auto-save de cambios
      audit_events registrados
```

| Estado | Quién puede editar | Quién puede transicionar | Acciones permitidas |
|---|---|---|---|
| `draft` | preparado_por o admin | preparado_por → `in_review` | upload, delete files, run cédulas, edit manual |
| `in_review` | revisado_por o admin | revisado_por: → `signed` o → `draft` | comments, sign |
| `signed` | nadie | admin: → `archived` | view, download Excel |
| `archived` | nadie | admin: → `signed` (unarchive) | view |

---

## 4. Modelo de datos (DB schema)

5 tablas nuevas. Migración: agregar a `init_db()` siguiendo el patrón existente (no se introduce Alembic en M1.1; se evalúa para M1.4+).

```python
class WorkingPaper(Base):
    """Una instancia de un papel de trabajo de auditoría."""
    __tablename__ = "working_papers"
    id: int PK
    project_id: FK projects.id ON DELETE CASCADE INDEX
    tool_code: str(64)                # "AUD.IMPUESTOS.OBLIGACIONES_FISCALES"
    cliente_name_snapshot: str(200)   # snapshot del cliente al crear el WP
    period_label: str(64)             # ej "Ejercicio Fiscal 2025"
    period_start: date | null
    period_end: date | null
    status: str(16) DEFAULT 'draft'   # draft|in_review|signed|archived
    prepared_by_user_id: FK users.id | null
    reviewed_by_user_id: FK users.id | null
    signed_by_user_id: FK users.id | null
    prepared_at, reviewed_at, signed_at, archived_at: datetime | null
    created_at: datetime
    updated_at: datetime
    notes: text | null

class WorkingPaperFile(Base):
    """Archivo subido asociado a un WorkingPaper, taggeado por tipo."""
    __tablename__ = "working_paper_files"
    id: int PK
    working_paper_id: FK working_papers.id ON DELETE CASCADE INDEX
    file_type: str(32)                # F_103|F_104|ATS|MAYOR_COMPRAS|MAYOR_VENTAS|F_101|OTRO
    period_label: str(32) | null      # ej "01" (enero) si aplica
    original_name: str(255)
    r2_key: str(512)
    size_bytes: int
    mime_type: str(64)
    sha256: str(64) INDEX
    uploaded_at: datetime
    uploaded_by_user_id: FK users.id

    UNIQUE(working_paper_id, sha256)  # evita duplicados exactos en mismo WP

class CedulaResult(Base):
    """Resultado computado de una cédula DM* del WorkingPaper."""
    __tablename__ = "cedula_results"
    id: int PK
    working_paper_id: FK working_papers.id ON DELETE CASCADE INDEX
    cedula_code: str(8)               # DM, DM1, DM2, ... DM10
    status: str(16) DEFAULT 'empty'   # empty|computing|partial|complete|failed
    data_json: jsonb | null           # datos calculados de esa cédula
    last_computed_at: datetime | null
    computed_by_user_id: FK users.id | null
    error_message: text | null
    manual_overrides_json: jsonb | null  # ediciones manuales del auditor sobre el resultado auto

    UNIQUE(working_paper_id, cedula_code)

class ExcelRender(Base):
    """Snapshot del Excel final generado (versiones acumulativas)."""
    __tablename__ = "excel_renders"
    id: int PK
    working_paper_id: FK working_papers.id ON DELETE CASCADE INDEX
    version_number: int               # 1, 2, 3... (incremental por WP)
    r2_key: str(512)                  # ubicación del Excel renderizado
    has_all_cedulas: bool             # true si las 11 cédulas estaban completas
    generated_at: datetime
    generated_by_user_id: FK users.id
    notes: text | null

    UNIQUE(working_paper_id, version_number)

class AuditEvent(Base):
    """Audit log de cambios en WorkingPapers (compliance)."""
    __tablename__ = "audit_events"
    id: int PK
    working_paper_id: FK working_papers.id ON DELETE CASCADE INDEX
    user_id: FK users.id | null
    event_type: str(32)               # status_change|file_upload|file_delete|cedula_run|excel_render|comment|sign
    timestamp: datetime DEFAULT now()
    payload_json: jsonb               # detalles del evento (estructura por event_type)
    ip_address: str(45) | null
    user_agent: str(255) | null
```

**Notas:**
- `tool_code = "AUD.IMPUESTOS.OBLIGACIONES_FISCALES"` (jerarquía categoría.herramienta). El sistema deriva categoría del prefijo.
- `manual_overrides_json` permite al auditor corregir manualmente valores calculados sin perder el cómputo original.
- `audit_events` se activa en M1.1 (compliance crítico para papeles firmables).

---

## 5. Estructura del módulo backend

```
backend/app/aud/
├── __init__.py
└── obligaciones_fiscales/                     # módulo de la herramienta
    ├── __init__.py
    ├── models.py                              # WorkingPaper, WorkingPaperFile, CedulaResult, ExcelRender, AuditEvent
    ├── schemas.py                             # Pydantic
    ├── service.py                             # CRUD multi-tenant + workflow
    ├── router.py                              # Endpoints HTTP
    ├── workflow.py                            # Lógica de transiciones de estado
    ├── audit_log.py                           # Helper para AuditEvent
    ├── file_types.py                          # Enum de tipos de archivo + validaciones
    └── cedulas/                               # Una carpeta por cédula
        ├── __init__.py
        ├── base.py                            # Interface CedulaCompute
        ├── dm.py                              # DM Programa (plantilla)            [M1.4]
        ├── dm1.py                             # DM1 Cuestionario (plantilla)       [M1.4]
        ├── dm2.py                             # DM2 Sumaria                        [M1.4]
        ├── dm3.py                             # DM3 Revisión saldos                [M1.5]
        ├── dm4.py                             # DM4 Compras                        [M1.5]
        ├── dm5.py                             # DM5 Ventas                         [M1.5]
        ├── dm6_iva.py                         # DM6 IVA — extractor F-104 + builder [M1.2]
        ├── dm7_retenciones.py                 # DM7 Retenciones — extractor F-103   [M1.3]
        ├── dm8_ats.py                         # DM8 ATS XML + cruce                [M1.6]
        ├── dm9_limites.py                     # DM9 Límite gastos                  [M1.7]
        └── dm10_hallazgos.py                  # DM10 Hoja de Hallazgos             [M1.7]

backend/app/core/
└── storage.py                                 # cliente R2 reusable (NUEVO en M1.1)
```

**Reglas de borde:**
- `cedulas/*.py` son lógica pura (extractor + builder) — testeables aislados.
- `service.py` y `router.py` son la capa con efectos (DB, HTTP, R2).
- `workflow.py` encapsula transiciones de estado (validación + side effects).
- `audit_log.py` se invoca desde service en cada cambio (NO se llama desde router).

---

## 6. API REST

Todas bajo `/api/v1/aud/obligaciones-fiscales/`.

### WorkingPapers

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/working-papers` | JWT user+ con acceso al proyecto | Crea WP. Body: `{ project_id, cliente_name, period_label, period_start, period_end }`. |
| `GET` | `/working-papers?project_id=X` | JWT + project_id en sus proyectos | Lista de WPs del proyecto. |
| `GET` | `/working-papers/{id}` | JWT + dueño del WP | Detalle completo: estado, archivos, cédulas, renders. |
| `PATCH` | `/working-papers/{id}` | JWT + dueño + estado `draft` | Actualizar metadata (period_label, notes, etc.). |
| `DELETE` | `/working-papers/{id}` | JWT admin | Borra WP + cascade (archivos R2 + DB). |

### Workflow (transiciones de estado)

| Método | Ruta | Auth | Transición |
|---|---|---|---|
| `POST` | `/working-papers/{id}/submit-for-review` | preparado_por | `draft` → `in_review` |
| `POST` | `/working-papers/{id}/return-to-draft` | revisado_por o admin | `in_review` → `draft` (con comment) |
| `POST` | `/working-papers/{id}/sign` | revisado_por (≠ preparado_por) | `in_review` → `signed` |
| `POST` | `/working-papers/{id}/archive` | admin | `signed` → `archived` |
| `POST` | `/working-papers/{id}/unarchive` | admin | `archived` → `signed` |

### Files

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/working-papers/{id}/files` | JWT + dueño + estado `draft` | Sube uno o más archivos. Form: `files` (multipart) + `file_type` + `period_label?`. |
| `GET` | `/working-papers/{id}/files` | JWT + dueño | Lista archivos. |
| `DELETE` | `/working-papers/{id}/files/{file_id}` | JWT + dueño + estado `draft` | Borra archivo (R2 + DB). |
| `GET` | `/working-papers/{id}/files/{file_id}/download` | JWT + dueño | 302 redirect a URL firmada de R2 (5 min). |

### Cédulas

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/working-papers/{id}/cedulas/{code}/compute` | JWT + dueño + estado `draft` | Encola cómputo de la cédula. Devuelve `{ status: 'computing' }`. |
| `GET` | `/working-papers/{id}/cedulas/{code}` | JWT + dueño | Estado + `data_json` + `manual_overrides_json`. |
| `PATCH` | `/working-papers/{id}/cedulas/{code}/overrides` | JWT + dueño + estado `draft` | Aplica overrides manuales (auditor corrige). |

### Excel render

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/working-papers/{id}/render` | JWT + dueño | Genera nueva versión del Excel con cédulas actuales. |
| `GET` | `/working-papers/{id}/renders` | JWT + dueño | Lista de versiones renderizadas. |
| `GET` | `/working-papers/{id}/renders/{version}/download` | JWT + dueño | 302 a URL firmada del Excel. |

### Audit events

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/working-papers/{id}/events` | JWT + dueño | Lista de eventos (audit log) ordenados por timestamp desc. |

---

## 7. Storage (Cloudflare R2)

Idéntico al spec v1: boto3, S3-compatible, presigned URLs para descarga directa. Convenciones de keys:

```
auditbrain/{org_slug}/{project_id}/{working_paper_id}/files/{file_type}/{uuid}_{filename}
auditbrain/{org_slug}/{project_id}/{working_paper_id}/renders/v{version}.xlsx
```

Env vars: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`.

Validaciones de upload:
- MIME por `file_type`:
  - F_103, F_104, F_101: `application/pdf`
  - ATS: `application/xml`, `text/xml`
  - MAYOR_COMPRAS, MAYOR_VENTAS: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/vnd.ms-excel`
  - OTRO: cualquiera (con warning)
- Tamaño máx: 20 MB por archivo (configurable)
- Máx archivos por WP: 100 (configurable, suficiente para 12 F-103 + 12 F-104 + 12 ATS + mayores + extra)

---

## 8. Frontend (extensión de App.jsx existente)

### 8.1. Nuevos componentes (en archivos separados)

```
frontend/src/aud/
├── ToolCatalog.jsx              # 15 categorías, mayoría "Próximamente"
├── ObligacionesFiscalesHome.jsx # Lista de WorkingPapers del proyecto
├── WorkingPaperView.jsx         # Vista de un WP: estado + archivos + cédulas + renders
├── WorkingPaperFileZone.jsx     # Upload zone con selector de file_type
├── CedulaCard.jsx               # Card por cédula con su estado y acciones
├── ExcelRenderHistory.jsx       # Lista de renders Excel descargables
└── AuditEventLog.jsx            # Timeline del audit log
```

**Decisión arquitectónica:** mover el código nuevo a archivos separados bajo `frontend/src/aud/` para evitar inflar `App.jsx` aún más. El `App.jsx` solo importa `ToolCatalog` y lo monta en la tab Análisis cuando `module.id === "AUD"`.

### 8.2. Flujo de UI

```
Sidebar AUD > Workspace > tab "Análisis"
   └─ ToolCatalog (15 categorías)
       └─ click "Impuestos" > "Auditoría de Obligaciones Fiscales"
           └─ ObligacionesFiscalesHome
               ├─ Lista de WorkingPapers existentes (estado + cliente + periodo)
               └─ Botón "+ Nuevo papel de trabajo"
                   └─ Modal: seleccionar cliente del proyecto + período
                       └─ Crear → redirect a WorkingPaperView
                           ├─ Header con estado + acciones de workflow
                           ├─ Panel "Archivos subidos" con tabs por file_type
                           ├─ Panel "Cédulas DM/DM1.../DM10" — grid de cards
                           ├─ Panel "Versiones Excel" — historial de renders
                           └─ Panel "Audit log" (colapsable)
```

### 8.3. Estilo

Reusa primitivas existentes (`Panel`, `ViewHead`, `btn primary`, `badge`, `notice warn`). Tema oscuro consistente.

### 8.4. Limitaciones aceptadas en M1.1

- Sin React Router: la navegación entre catálogo → home → WP usa estado React. Refresh pierde estado.
- Sin i18n: solo español. Strings centralizadas en `frontend/src/aud/strings.js` para facilitar i18n futura.
- Sin notificaciones push: el usuario hace polling cuando una cédula corre.

---

## 9. Workflow de auditoría (detalle)

### 9.1. Transiciones permitidas

| Desde | Hacia | Quién | Validación adicional |
|---|---|---|---|
| `draft` | `in_review` | `prepared_by_user_id` | WP debe tener al menos 1 archivo subido y 1 cédula computada |
| `in_review` | `draft` | `reviewed_by_user_id` o admin | Requiere comment explicando |
| `in_review` | `signed` | `reviewed_by_user_id` (≠ `prepared_by_user_id`) | Doble vista (no se firma uno mismo) |
| `signed` | `archived` | admin | — |
| `archived` | `signed` | admin | — |

### 9.2. Cambios permitidos por estado

| Estado | Editar archivos | Correr cédulas | Editar overrides | Generar Excel | Borrar WP |
|---|---|---|---|---|---|
| `draft` | ✅ | ✅ | ✅ | ✅ | admin |
| `in_review` | ❌ | ❌ | ❌ | ✅ (snapshot del estado revisado) | admin (con warning) |
| `signed` | ❌ | ❌ | ❌ | ✅ (idéntico al snapshot firmado) | ❌ |
| `archived` | ❌ | ❌ | ❌ | ❌ | ❌ |

### 9.3. Audit log

Cada transición de estado, upload/delete de archivo, ejecución de cédula, render de Excel y override manual genera un `AuditEvent`. El log es inmutable (no se puede modificar ni borrar individualmente).

---

## 10. Job lifecycle (cómputo de cédulas)

Cada cédula tiene su propio compute. El patrón:

```
                                ┌──────────────────────────────────┐
                                │  BackgroundTask (FastAPI)         │
                                │  cedulas.{code}.compute(wp_id)    │
                                └──────────────────────────────────┘
                                          │
   empty ── POST /compute ──►  computing  │  1. download from R2 archivos según file_types necesarios
                                          │  2. extractor.parse_*(bytes) → estructura
                                          │  3. builder.compute(estructuras, manual_overrides) → data_json
                                          │  4. UPDATE CedulaResult status=complete|partial|failed
                                          │  5. INSERT AuditEvent
                                          │
                                  ┌────────┴─────────┬─────────┐
                                  ▼                  ▼         ▼
                              complete         partial      failed
                                                  │            │
                                          (faltan archivos)   (error_message)
```

**Garantías:**
- Idempotencia: re-correr una cédula reemplaza el resultado anterior (atómico)
- Concurrencia: limitada a 1 cédula por WP a la vez (lock por `working_paper_id + cedula_code`)
- Timeout por cédula: 600s (configurable). Cédulas como DM6 IVA pueden requerir extracción de 12 PDFs.

---

## 11. Manejo de errores y edge cases

| Caso | Manejo |
|---|---|
| PDF F-104 corrupto | `extractor.parse_f104()` retorna `None`, cédula DM6 queda `partial` con mensaje "1 de 12 F-104 no se pudo parsear" |
| Falta 1 mes de F-103 | DM7 queda `partial` con casilleros de ese mes en null + nota |
| Mayor Compras Excel con estructura imprevista | Parser falla, cédula DM4 queda `failed` con `error_message` indicando filas problemáticas |
| Mismo archivo subido dos veces | Hash SHA256 detecta → `409 Conflict` con `duplicate_of: <file_id>` |
| Usuario intenta editar WP en estado `in_review` | UI bloquea, backend `409 Conflict` con `current_status` |
| Usuario sin proyecto activo | UI muestra "Selecciona un proyecto del módulo AUD primero" |
| Revisor intenta firmar siendo el mismo preparador | Backend `409 Conflict` "El revisor debe ser distinto al preparador" |
| WP firmado: alguien intenta agregar archivo | Backend `403 Forbidden` "WP en estado signed es inmutable" |
| Render Excel cuando cédulas incompletas | Permite render con cédulas incompletas marcadas en el Excel ("PENDIENTE" en celdas) |
| Render Excel falla a mitad | `excel_renders` queda sin row; el usuario puede reintentar |
| Cross-tenant access intent | `403 Forbidden` siempre. AuditEvent registra el intento. |

---

## 12. Observabilidad

- Logs estructurados JSON en stdout con: `working_paper_id`, `cedula_code`, `user_id`, `project_id`, `event`, `duration_ms`, `error?`.
- `AuditEvent` table = audit log persistente y consultable.
- Render dashboard: métricas de Postgres (queries lentas, conexiones), HTTP latency, errors.
- Health endpoint `/api/v1/health` ya expone estado de la plataforma; agregar campo `r2_status` (ping a R2).

---

## 13. Testing

| Capa | Tipo | Ubicación |
|---|---|---|
| `cedulas/dm*.py` (lógica pura) | Unit | `tests/test_aud_of_cedula_<code>.py` |
| `service.py` | Integration (sqlite + mock R2 con moto) | `tests/test_aud_of_service.py` |
| `router.py` | Integration (FastAPI TestClient + JWT fixture) | `tests/test_aud_of_router.py` |
| `workflow.py` | Unit | `tests/test_aud_of_workflow.py` |
| `audit_log.py` | Unit | `tests/test_aud_of_audit_log.py` |
| `storage.py` (R2 client) | Unit con moto | `tests/test_aud_of_storage.py` |
| End-to-end | Manual con Playwright + checklist por milestone | `docs/AUD_OF_M*_E2E.md` |

**Fixtures de PDFs/Excel:** En `tests/fixtures/obligaciones_fiscales/` se guardan muestras anonimizadas (1 F-103, 1 F-104, 1 ATS, 1 mayor de cada tipo). El usuario debe proveer estas muestras al iniciar M1.2.

---

## 14. Milestones

Descomposición en 7 milestones. Cada uno entregable independiente con criterio de éxito explícito.

### M1.1 — Plumbing del WorkingPaper
**Objetivo:** Crear WP, subir archivos taggeados por tipo, ver listado, workflow básico de estados.

Deliverables:
- Tabla `working_papers`, `working_paper_files`, `cedula_results` (vacía), `excel_renders` (vacía), `audit_events`.
- `backend/app/core/storage.py` (cliente R2).
- Endpoints: `POST/GET/DELETE/PATCH /working-papers`, `POST/GET/DELETE /files`, `POST /submit-for-review|return-to-draft|sign|archive|unarchive`, `GET /events`.
- Frontend: `ToolCatalog.jsx`, `ObligacionesFiscalesHome.jsx`, `WorkingPaperView.jsx` (solo archivos + estado, sin cédulas aún), `WorkingPaperFileZone.jsx`.
- Audit log activo desde día 1.
- Tests: ~25 nuevos cubriendo storage, service, router, workflow.

Criterio de éxito: login → AUD → tab Análisis → ver 15 categorías → click "Impuestos > Auditoría de Obligaciones Fiscales" → crear WP → subir 12 F-104 (taggeados) → cambiar estado a in_review → otro admin firma → audit log refleja todo.

### M1.2 — Cédula DM6 IVA (primera cédula computacional)
**Objetivo:** Procesar 12 F-104 PDFs + mayor opcional → producir cédula DM6 según plantilla.

Deliverables:
- `cedulas/dm6_iva.py` con extractor de F-104 (pdfplumber + regex sobre casilleros 419, 429, 480, etc.) + builder de la estructura DM6.
- Endpoint `POST /cedulas/DM6/compute` + `GET /cedulas/DM6`.
- Frontend: `CedulaCard.jsx` con estado y resultado en JSON; vista de tabla idéntica a la plantilla.
- `excel_builder.py` (parcial) que rendiriza solo la pestaña DM6 a Excel.
- Tests: extractor con fixtures de F-104 anonimizados + builder asserts sobre celdas.

Criterio de éxito: WP con 12 F-104 subidos → click "Computar DM6 IVA" → ver tabla mensual conciliada → descargar Excel con la pestaña DM6 idéntica a la plantilla.

**Bloqueo:** 12 F-104 reales anonimizados como fixtures.

### M1.3 — Cédula DM7 Retenciones
Análogo a M1.2 pero para F-103 → cédula DM7.

Criterio de éxito: 12 F-103 subidos → DM7 computada → casilleros 723, 725, 727, 729 conciliados.

### M1.4 — Cédulas DM, DM1, DM2 (plantillas + manuales)
**Objetivo:** Las 3 cédulas que NO requieren extracción de PDFs.

Deliverables:
- DM Programa: auto-genera tabla con datos del proyecto + procedimientos estándar.
- DM1 Cuestionario: UI form con 8 preguntas Si/No + cálculo automático de "Calificación del riesgo".
- DM2 Cédula Sumaria: requiere input opcional de "Balance de Comprobación" (nuevo tipo de archivo Excel). Si no hay archivo, queda vacía con plantilla.
- Excel builder cubre pestañas DM, DM1, DM2.

Criterio de éxito: WP arranca con DM/DM1/DM2 auto-pobladas en cuanto se crea + revisión manual.

### M1.5 — Cédulas DM3, DM4, DM5 (requieren mayores Excel)
**Objetivo:** Parser de mayor contable Excel + cédulas mensuales.

Deliverables:
- `cedulas/_excel_mayor_parser.py`: helper común para parsear mayores en formato estándar.
- DM3: Compara saldos según libros vs F-104 casillero 529, 429.
- DM4: Compras e IVA en compras (12 meses).
- DM5: Ventas e IVA en ventas (12 meses).
- Excel builder cubre DM3, DM4, DM5.

Criterio de éxito: WP con F-104s + mayores → DM3/DM4/DM5 conciliadas y mostradas en pestañas del Excel.

### M1.6 — Cédula DM8 ATS XML + cross-references
**Objetivo:** Parser de ATS XML + cruce de datos con cédulas previas.

Deliverables:
- `cedulas/_ats_parser.py`: parsea ATS XML (estructura oficial SRI).
- DM8: cruza ATS vs F-103/F-104 (casilleros 419, 429) + detecta diferencias materiales.
- Excel builder cubre DM8.

Criterio de éxito: 12 ATS XML subidos → DM8 muestra diferencias material (>= umbral) y comparativos.

### M1.7 — Cédulas DM9, DM10 + Excel render integral
**Objetivo:** Cerrar la herramienta con cédulas finales + render Excel completo.

Deliverables:
- DM9 Límite gastos: parser F-101 (declaración anual de renta) — nuevo tipo F_101.
- DM10 Hoja de Hallazgos: agrega hallazgos de DM3-DM8 automáticamente + permite agregar observaciones manuales.
- Excel render integral: las 11 pestañas, formato y fórmulas idénticas a la plantilla.
- Tests E2E completos.

Criterio de éxito: WP con todos los archivos subidos → todas las cédulas computadas → render del Excel descargado pasa visual diff con plantilla original.

---

## 15. Out of scope (explícito)

- **Otros módulos sectoriales activos** — TAX, ADV, FIN, etc. siguen mostrando Workspace cognitivo genérico. Solo AUD recibe la tool catalog en este spec.
- **Otras categorías del catálogo AUD** — todas excepto "Impuestos" muestran "Próximamente" en M1.1-M1.7. Se construyen como specs separados después.
- **i18n EN** — diferido.
- **React Router** — diferido a spec separado de refactor de UI.
- **Refactor de `App.jsx`** — los nuevos componentes viven en `frontend/src/aud/`. El `App.jsx` solo agrega un import.
- **Tool registry dinámico** — el catálogo de 15 categorías está hardcoded en `frontend/src/aud/catalog.js` por simplicidad. Refactor a registry dinámico cuando haya tools en 3+ categorías.
- **Notificaciones push** cuando termina una cédula. El usuario hace polling.
- **Versionado de plantilla DM** — si la plantilla cambia, hay decisión manual de cómo afecta a WPs existentes. Versionado formal de plantillas en spec posterior.
- **Importación masiva** (subir 50 PDFs en bulk con detección automática de tipo) — diferido.
- **Comparativo año-a-año** entre WPs del mismo cliente — diferido.
- **Compartir WP con el cliente auditado** (read-only) — diferido a M2.
- **Web service SRI** (validación de autorizaciones) — diferido.

---

## 16. Bloqueos y dependencias

1. **Cuenta Cloudflare R2** con credenciales y bucket — requerido para M1.1.
2. **12 F-104 reales anonimizados** (1 cliente, 12 meses) — requerido para M1.2.
3. **12 F-103 reales anonimizados** — requerido para M1.3.
4. **Plantilla Excel** `DM - Obligaciones Fiscales Final.xlsx` — ✅ ya disponible en `C:/Users/jcalu/Downloads/Prueba Cloude/Prueba Cloude/`.
5. **Mayores Excel reales** (Compras, Ventas, Balance) — requerido para M1.4-M1.5.
6. **12 ATS XML** — requerido para M1.6.
7. **F-101 real** — requerido para M1.7.
8. **Confirmación del usuario sobre tabla SRI vigente** (para cédulas con porcentajes oficiales) — puede ser hardcoded en M1.3 + actualización manual versionada.

---

## 17. Documentos siguientes

- `docs/superpowers/plans/2026-05-26-aud-obligaciones-fiscales-m1-1.md` — plan detallado de M1.1 (próximo paso).
- Cada milestone tendrá su propio plan generado cuando arrancamos ese milestone.
