# Spec — Herramienta `AUD.RETENCIONES_FUENTE`

**Fecha:** 2026-05-26
**Autor:** Jorge Calupiña (jcalupinia@auditconsulting.ec)
**Co-diseño:** Claude (Opus 4.7)
**Estado:** Diseño aprobado por usuario · pendiente plan de implementación
**Alcance:** Primera herramienta concreta del módulo AUD (External Audit). Encaja sobre la plataforma AuditBrain existente sin reemplazar nada.
**Documento siguiente:** `docs/superpowers/plans/2026-05-26-aud-retenciones-fuente-plan.md` (vía skill `writing-plans`).

---

## 1. Contexto

AuditBrain es la plataforma operativa de inteligencia empresarial de Audit Consulting Group, desplegada en Render como FastAPI + React (SPA Vite) sobre PostgreSQL. Está organizada en módulos sectoriales (ADV, AUD, TAX, LEG, FIN, CYB, DATA, AUT, GOV, MKT, CRE) y módulos de operación (DSH, DOC, RUN, WKS, USR, SEC). La plataforma tiene auth JWT multi-tenant, contexto operativo (Organization → Client → Project), workspace cognitivo con LLM, servicio documental externo y sandbox Python Tier 0.

Este spec define la **primera herramienta sectorial concreta**: una herramienta que recibe comprobantes de retención en la fuente del SRI (Ecuador) en PDF, los procesa automáticamente y genera un papel de trabajo Excel con extracción, validaciones inteligentes y hallazgos.

### Caso de uso real motivador

Caso recurrente del usuario: tiene 98 PDFs de comprobantes de retención (formato estándar SRI Ecuador) de un cliente auditado y necesita generar un papel de trabajo Excel con columnas: Comprobante, Número, Fecha Emisión, Ejercicio Fiscal, Base Imponible, Impuesto, % Retención, Valor Retenido. Hoy lo hace manualmente.

### Por qué encaja en la plataforma existente

| Necesidad | Componente existente reusado |
|---|---|
| Auth multi-tenant | `backend/app/auth/` + `backend/app/context/` |
| Selección de cliente/proyecto | `Workspaces` (M1) — ya construido |
| Storage de credenciales | env vars + Render dashboard (patrón ya en uso) |
| Servicio de generación documental | `universal-creador-documentos.onrender.com` (alternativa al openpyxl directo) |
| UI shell + tema oscuro premium | `App.jsx` Command Center |
| Librerías Python (pdfplumber, openpyxl, pandas) | Ya en `requirements.txt` |

### GAPS identificados que este spec aborda

1. **Storage de archivos persistente** — Render disk es efímero; no hay object storage configurado.
2. **Concepto de "herramienta sectorial registrada"** — actualmente cada ejecución es un Python script ad-hoc; el spec introduce el modelo `ToolExecution` reusable.
3. **Jobs asíncronos** — el sandbox actual es síncrono con 300s timeout; este spec usa `BackgroundTasks` de FastAPI (suficiente para MVP).
4. **Modelo de DB para resultados de herramientas** — no existe; el spec lo crea.

---

## 2. Decisiones arquitectónicas (capturadas durante el brainstorming)

| Decisión | Valor | Justificación |
|---|---|---|
| Usuarios | SaaS multi-tenant (empresas auditadas + equipo + admin) | Confirmado por usuario |
| Flujo | Cliente sube → sistema procesa auto → equipo revisa → papel queda para auditor | Auditoría externa clásica |
| Volumen target | 10-50 clientes × >1000 docs/mes + archivos grandes | Confirmado por usuario |
| Hosting | Cloud (Render, USA) | Reconciliado tras decisión inicial confusa de on-premise |
| Marca / UI | AuditBrain v4.0.0 (existente) | Confirmado |
| Idioma plataforma | Español + inglés (i18n diferida a futuro) | MVP en español únicamente |
| Auth | Email + password (ya implementado) | Sin cambios |
| Onboarding clientes | Invitación manual (ya implementado) | Sin cambios |
| Funcionalidad target retenciones | Máximo: extracción + duplicados + tabla SRI + cruce ATS + WS SRI + alertas | Descompuesto en milestones M1.1-M1.4 |
| Capacidad de desarrollo | Usuario + Claude | Implica simplicidad arquitectónica, descomposición incremental, stack conocido |
| Stack | El existente: FastAPI + React + Postgres + Render | No se introduce nada nuevo salvo Cloudflare R2 |
| Storage de uploads | **Cloudflare R2** (S3-compatible, sin egress fees) | Escalable, costo bajo, decisión del usuario |
| Jobs async | **FastAPI BackgroundTasks** para MVP | Decisión del usuario; migrable a RQ/Celery si crece |
| Plantilla Excel del papel de trabajo | Provista por el usuario | A entregar al iniciar M1.2 |

---

## 3. Ubicación funcional

```
Command Center
 └─ Sidebar > Módulo AUD (External Audit)
     └─ Workspace cognitivo del proyecto activo
         └─ Tab "Análisis"
             └─ Catálogo de herramientas
                 └─ 🆕 Comprobantes de Retención SRI (AUD.RETENCIONES_FUENTE)
                     └─ Vista de la herramienta (upload, ejecutar, ver, descargar)
```

**Pre-requisito UX:** El usuario debe tener un proyecto AUD activo. Si no, la UI muestra mensaje "Selecciona un proyecto del módulo AUD primero" y la API devuelve `400`.

---

## 4. Filosofía aditiva

Sigue la regla del `docs/ARCHITECTURE.md` actual: **migración aditiva y reversible**.

- Nuevo código vive en `backend/app/aud/` sin tocar `app.py` legacy, `auditbrain_exec_runner.py`, ni rutas existentes.
- Si el módulo nuevo falla al importar, el sistema sigue funcionando (defensive mount, mismo patrón que `backend/` actual).
- No refactorizamos `App.jsx` (~1000 líneas) aunque sea tentador — agregamos componentes nuevos. Refactor sería spec separado.
- No introducimos React Router (el sistema usa estado `section`). Limitación conocida documentada abajo.

---

## 5. Estructura del módulo backend

```
backend/app/aud/
├── __init__.py
└── retenciones_fuente/
    ├── __init__.py
    ├── models.py          # SQLAlchemy: ToolExecution, UploadedFile, ExtractedRetention
    ├── schemas.py         # Pydantic
    ├── router.py          # FastAPI router (montado bajo /api/v1/aud/retenciones-fuente)
    ├── service.py         # Orquestación con DB; capa que conoce SQLAlchemy
    ├── extractor.py       # Pure logic: bytes PDF → dict extraído
    ├── validator.py       # Pure logic: lista de filas → marcas de duplicados/anomalías
    ├── sri_table.py       # Tabla oficial de retenciones SRI (estática, versionada)
    ├── excel_builder.py   # Pure logic: lista de filas → bytes Excel
    └── jobs.py            # BackgroundTask: orquesta extractor + validator + excel_builder
```

**Reglas de borde:**
- `extractor`, `validator`, `excel_builder`, `sri_table` son **lógica pura** (sin DB, sin HTTP, sin estado FastAPI). Testeables aislados.
- `service` y `router` son la capa con efectos (DB, HTTP, R2).
- `jobs` orquesta pero delega cómputo a módulos puros.
- El módulo no toca `app.py`, no toca el runner Tier 0, no toca otros módulos del backend.

**Cliente R2 reusable:** Para que futuras herramientas no reinventen, se crea utilidad compartida:
```
backend/app/core/storage.py   # R2 client wrapper sobre boto3
```

---

## 6. Schema de base de datos

3 tablas nuevas. Migración: Alembic si está configurado; si no, `Base.metadata.create_all()` (a confirmar al implementar — el repo tiene SQLAlchemy 2.0.36 pero no se ve Alembic en requirements).

```python
class ToolExecution(Base):
    __tablename__ = "tool_executions"
    id: int (PK)
    project_id: FK projects.id ON DELETE CASCADE  # multi-tenant
    tool_code: str(32)                            # "AUD.RETENCIONES_FUENTE"
    status: str(16)                               # pending|running|done|failed
    started_by_user_id: FK users.id
    started_at, finished_at: datetime
    error_message: text | null
    output_excel_key: str(512) | null             # R2 key del Excel generado
    summary_json: jsonb                           # totales, hallazgos
    created_at: datetime

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id: int (PK)
    execution_id: FK tool_executions.id ON DELETE CASCADE
    original_name: str(255)
    r2_key: str(512)                              # key en Cloudflare R2
    size_bytes: int
    mime_type: str(64)
    sha256: str(64) INDEX                         # detección de duplicado exacto
    uploaded_at: datetime

class ExtractedRetention(Base):
    __tablename__ = "extracted_retentions"
    id: int (PK)
    execution_id: FK tool_executions.id ON DELETE CASCADE INDEX
    uploaded_file_id: FK uploaded_files.id ON DELETE CASCADE
    # Campos extraídos del comprobante SRI:
    comprobante_tipo: str(32)                     # "RETENCION"
    comprobante_numero: str(64) INDEX
    fecha_emision: date
    ejercicio_fiscal: str(8)                      # "04/2026"
    base_imponible: numeric(18,2)
    impuesto: str(32)                             # "IVA" | "Impuesto a la Renta" | "ISD"
    porcentaje_retencion: numeric(5,2)
    valor_retenido: numeric(18,2)
    autorizacion_sri: str(64) | null
    agente_retencion_ruc: str(13) | null
    # Marcas del validador:
    is_duplicate: bool DEFAULT false
    has_anomaly: bool DEFAULT false
    anomaly_notes: jsonb | null
    extraction_error: text | null                 # si el PDF no se pudo parsear
```

**Justificación:**
- 3 tablas normalizadas, cada una con un concepto claro.
- `tool_code` deja la puerta abierta a futuras herramientas sin re-schema.
- `summary_json` evita columnas variables.
- Cascade delete asegura que al borrar la ejecución se limpia todo.

---

## 7. API REST

Todas bajo `/api/v1/aud/retenciones-fuente/`.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/executions` | JWT user+ + project activo | Crea ejecución vacía. Body: `{ project_id: int }`. Devuelve `{ execution_id, status: "pending" }`. |
| `POST` | `/executions/{id}/files` | JWT + dueño ejecución | Sube uno o más PDFs (multipart). Stream directo a R2. Devuelve lista de `UploadedFile`. |
| `POST` | `/executions/{id}/run` | JWT + dueño ejecución | Encola BackgroundTask de procesamiento. Devuelve `{ status: "running" }`. |
| `GET` | `/executions/{id}` | JWT + dueño | Estado + summary + lista de filas extraídas (paginada si > 200). |
| `GET` | `/executions/{id}/download` | JWT + dueño | 302 redirect a URL firmada R2 del Excel (validez 5 min). |
| `GET` | `/executions?project_id=X` | JWT + project activo | Lista ejecuciones del proyecto activo. |
| `DELETE` | `/executions/{id}` | JWT admin | Borra ejecución, archivos R2, registros DB. |

**Autorización (multi-tenant):**
- Todo endpoint valida `execution.project_id IN user.projects` (vía `project_members`).
- Admin ve todo dentro de su `organization`.
- 403 si el usuario no es miembro del proyecto y no es admin.

**Validaciones de upload:**
- MIME permitido: `application/pdf` únicamente.
- Tamaño máx por archivo: 20 MB (configurable vía env var).
- Máx archivos por ejecución: 500 (configurable).
- Hash SHA256 del cuerpo → si ya existe en la misma ejecución, devuelve `409 Conflict` con `{ duplicate_of: <file_id> }`.

---

## 8. Storage — Cloudflare R2

**Librería:** `boto3` (S3-compatible). Endpoint custom: `https://<account_id>.r2.cloudflarestorage.com`.

**Env vars nuevas (en `render.yaml` con `sync: false`):**
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET` (ej: `auditbrain-storage`)
- `R2_PUBLIC_ENDPOINT` (opcional, para presigned URLs)

**Convención de keys:**
```
auditbrain/{org_slug}/{project_id}/{execution_id}/inputs/{uuid}_{filename_safe}
auditbrain/{org_slug}/{project_id}/{execution_id}/output.xlsx
```

**Flujo de subida:**
1. Frontend envía multipart al backend.
2. Backend valida tamaño/MIME/hash en memoria por chunks.
3. Backend hace `put_object` streaming a R2 sin guardar en disco.
4. Backend graba `UploadedFile` en DB.

**Flujo de descarga:**
1. Frontend pide `GET /executions/{id}/download`.
2. Backend genera presigned URL (5 min) y responde 302 redirect.
3. Navegador descarga directo de R2 (el backend no proxy).

**Lifecycle:**
- Política R2: borra `inputs/` con > 90 días (configurable, plan futuro).
- `output.xlsx` se mantiene indefinidamente hasta borrado manual de la ejecución.

---

## 9. Job lifecycle (procesamiento asíncrono)

```
                  ┌─────────────────────────────────────┐
                  │  BackgroundTask (proceso FastAPI)   │
                  │  jobs.process_execution(exec_id)    │
                  └─────────────────────────────────────┘
                                  │
                                  │ por cada UploadedFile:
                                  │   1. download from R2 (stream)
                                  │   2. extractor.extract(bytes) → dict | error
                                  │   3. INSERT ExtractedRetention
                                  │   4. UPDATE summary_json processed++
                                  │
                                  │ cuando termina todos los archivos:
                                  │   5. validator.validate(all_rows)
                                  │      → set is_duplicate, has_anomaly, anomaly_notes
                                  │   6. excel_builder.build(all_rows) → bytes
                                  │   7. upload bytes a R2 (output.xlsx)
                                  │   8. UPDATE execution status=done, output_excel_key,
                                  │             summary_json (totales finales)
                                  │
   pending ──POST .../run──► running ──────► done
                                │
                                └────────► failed (con error_message)
```

**Garantías:**
- Idempotencia parcial: si el proceso muere a mitad, las filas ya extraídas quedan en DB. La ejecución queda `running`.
- Cleanup: job (cron / health check) marca ejecuciones `running` con `started_at > 30 min` como `failed` con mensaje "timeout o reinicio".
- Concurrencia: limitada a 1 (alineada con `EXECUTION_CONCURRENCY=1` actual de Render). Si dos ejecuciones se lanzan simultáneas, la segunda espera.
- Trade-off explícito: si la concurrencia se vuelve un problema real, migración a RQ/Celery con cambio acotado al módulo `jobs.py` y nuevo servicio Redis en Render (~$10/mes).

---

## 10. Frontend

**Estrategia:** agregar componentes nuevos a `App.jsx` (NO refactorizar el archivo completo).

**Nuevos componentes:**

```jsx
// Renderizado en CognitiveWorkspace cuando tab === "análisis" && module.id === "AUD"
<ToolCatalog projectId={ctx?.active_project?.id}>
  <ToolCard
    code="AUD.RETENCIONES_FUENTE"
    title="Comprobantes de Retención SRI"
    description="Extrae datos de PDFs, valida % vs tabla SRI, detecta duplicados, genera papel de trabajo Excel."
    onOpen={() => openTool("AUD.RETENCIONES_FUENTE")}
  />
</ToolCatalog>

<RetencionesFuenteTool projectId>
  // Paso 1: UploadZone (react-dropzone o input nativo, multiple, accept=.pdf)
  //         → POST /executions
  //         → POST /executions/{id}/files (por cada archivo, con progress)
  // Paso 2: Lista de archivos subidos, botón "Ejecutar"
  //         → POST /executions/{id}/run
  // Paso 3: Estado "Procesando X de Y..." con polling cada 2s a GET /executions/{id}
  // Paso 4: Tabla de resultados (sticky header, filas rojas/amarillas según marcas)
  // Paso 5: Botón "Descargar Excel" → GET /executions/{id}/download
  // Paso 6: Historial de ejecuciones previas del proyecto
</RetencionesFuenteTool>
```

**Estilo:**
- Reusa primitivas existentes: `Panel`, `ViewHead`, `btn primary`, `notice warn`, `Metric`, `kv`, `table`.
- Tema oscuro consistente con Command Center.
- Strings en español únicamente; preparados en constante `STRINGS` para i18n futura.

**Estado del cliente:**
- La herramienta vive en estado React (`section + subview`), no en URL.
- Si el usuario refresca, vuelve al inicio del módulo AUD. **Limitación conocida**, resuelve spec separado de React Router.

**Sin cambios** al `Workspaces` (M1), `Documents`, `Runner`, `Users`, `Security`, login, sidebar de módulos.

---

## 11. Errores y edge cases

| Caso | Manejo |
|---|---|
| PDF corrupto o ilegible | `extractor` devuelve error → `ExtractedRetention.extraction_error` poblado, sigue con los demás. No falla la ejecución completa. |
| PDF que NO es comprobante de retención SRI | Igual al anterior, mensaje específico "formato no reconocido". |
| Mismo PDF subido dos veces en la misma ejecución | Hash SHA256 idéntico → `409 Conflict` en upload con `duplicate_of: <file_id>`. |
| Cliente sube 1000 PDFs (job de 20+ min) | Job corre; frontend polling muestra progreso; backend mantiene conexión cerrada. |
| Usuario cierra navegador a mitad | Job continúa; al volver ve estado actualizado. |
| Render reinicia contenedor a mitad de job | Ejecución queda `running` huérfana; cleanup la marca `failed` con mensaje "restart durante procesamiento". |
| Tabla SRI desactualizada | `sri_table.py` versionado; cambio explícito en commit + rerun manual de ejecuciones afectadas. |
| Usuario sin proyecto activo | UI bloquea con mensaje; backend devuelve `400`. |
| Excel generado > 10 MB | R2 lo guarda; navegador descarga directo. |
| Usuario sin permisos sobre el proyecto | `403 Forbidden`. |
| Validación SRI por WS falla (M1.4) | Marca `autorizacion_validada: pending`, ejecución se completa igual. Job retry posterior. |

---

## 12. Observabilidad

- **Logs estructurados (JSON)** vía stdout. Cada paso del job loguea: `execution_id`, `file_id`, `step`, `duration_ms`, `error?`.
- **summary_json siempre poblado** con: `{ total, processed, errors, duplicates, anomalies, retencion_iva_total, retencion_renta_total, retencion_isd_total }`.
- **Audit log:** decisión MVP: **diferido**. Verificado que NO existe tabla `audit_events` en el repo. Para MVP, los logs estructurados en stdout (con `execution_id`, `user_id`, `project_id`) son suficientes. Si se requiere audit log persistido (compliance, normativa), será spec separado.
- **Render dashboard:** métricas estándar (CPU, memoria, requests) ya disponibles; no se agrega nada.

---

## 13. Testing

| Capa | Tipo | Herramienta | Fuente de datos |
|---|---|---|---|
| `extractor.py` | Unit | pytest + fixtures | PDFs reales del SRI en `tests/fixtures/retenciones/` (5-10 muestras anonimizadas) |
| `validator.py` | Unit | pytest | Listas Python sintéticas |
| `excel_builder.py` | Unit | pytest + openpyxl assert | Fixtures de filas → bytes → re-abrir y verificar celdas |
| `sri_table.py` | Unit | pytest | Casos conocidos match/no-match |
| `service.py` | Integration | pytest + sqlite in-memory + mock boto3 | DB temporal + mock S3 con moto |
| `router.py` | Integration | FastAPI TestClient + auth fixture | DB temporal |
| End-to-end | Manual | Playwright o navegador | Login real → crear proyecto AUD → subir 5 PDFs → ejecutar → descargar Excel |

**Convenciones del repo (a respetar):**
- pytest ya configurado en `tests/`.
- **Tests planos** (no anidados) siguiendo el patrón existente: `tests/test_aud_retenciones_extractor.py`, `tests/test_aud_retenciones_validator.py`, `tests/test_aud_retenciones_excel_builder.py`, `tests/test_aud_retenciones_router.py`, etc.
- Fixtures compartidas en `tests/conftest.py`.
- Fixtures binarios (PDFs de muestra) en `tests/fixtures/retenciones/`.

**Fuera del scope de testing en MVP:**
- WS del SRI (mockeado siempre — depender de uptime externo en CI es frágil).
- Performance bajo carga real (>500 archivos): se mide en producción con cliente piloto.

---

## 14. Milestones incrementales

Descomposición obligatoria dada la capacidad de desarrollo (usuario + Claude). Cada milestone es entregable independiente y útil.

### M1.1 — Plumbing mínimo
**Objetivo:** Subir PDFs y verlos guardados en R2, asociados a proyecto AUD. Sin lógica de extracción.

Entregables:
- Carpeta `backend/app/aud/retenciones_fuente/` con archivos vacíos correctos.
- `backend/app/core/storage.py` (cliente R2 reusable).
- 3 tablas nuevas creadas + migración.
- Endpoints: `POST /executions`, `POST /executions/{id}/files`, `GET /executions/{id}`, `GET /executions`.
- Frontend: `RetencionesFuenteTool` con UploadZone funcional + lista de ejecuciones previas.
- Tests: router (autorización, validaciones de upload) + storage (con mock R2).
- Env vars R2 configuradas en Render.

Criterio de éxito: Login → módulo AUD → crear ejecución → subir 5 PDFs reales → verlos guardados en R2 → ver lista en UI.

### M1.2 — Extractor real + Excel básico
**Objetivo:** Procesar PDFs reales, generar papel de trabajo Excel descargable.

Entregables:
- `extractor.py` con `pdfplumber` + regex específicos de retenciones SRI.
- `excel_builder.py` replicando plantilla Excel del usuario.
- `jobs.py` con BackgroundTask orquestador.
- Endpoints: `POST /executions/{id}/run`, `GET /executions/{id}/download`.
- Frontend: botón "Ejecutar", polling de estado, tabla de filas, botón "Descargar Excel".
- Tests: extractor con fixtures + excel_builder asserts.

Criterio de éxito: Subir los 98 PDFs reales del caso motivador → ejecutar → descargar Excel equivalente al hecho manualmente.

**Bloqueo:** Requiere la plantilla Excel del usuario y 5-10 PDFs muestra antes de empezar.

### M1.3 — Validaciones inteligentes (duplicados + tabla SRI)
**Objetivo:** Pasar de "extractor automatizado" a "asistente de auditoría".

Entregables:
- `sri_table.py` con tabla oficial SRI versionada.
- `validator.py`: duplicados (mismo número), % aplicado vs % legal, anomalías.
- Marcas visuales en UI (fila roja = duplicado, amarillo = % atípico).
- `summary_json` con métricas totales y por tipo de impuesto.
- Tests del validator con fixtures sintéticos cubriendo cada regla.

Criterio de éxito: Subir set con duplicados intencionales y % equivocados → marcados correctamente en UI y resumen.

### M1.4 — Integración SRI WS + alertas (opcional/diferible)
**Objetivo:** Verificación oficial y alertas avanzadas.

Entregables:
- `sri_client.py` para WS de validación de autorizaciones SRI.
- Reglas configurables de alertas (montos redondeados, fines de semana, fuera de periodo).
- Cruce con ATS (parser XML) si el cliente sube ese archivo.
- Panel UI "Hallazgos para revisión humana".

Criterio de éxito: Sistema marca 3 tipos distintos de hallazgos automáticamente.

**Recomendación:** Empezar a usar la herramienta con clientes en M1.3. Construir M1.4 según demanda real.

---

## 15. Out of scope (explícito)

Estas cosas NO están en este spec — irán en specs separados si se priorizan:

- **Tool registry generalizado** (catálogo dinámico de herramientas por módulo) — se construye al agregar la segunda herramienta del módulo AUD, no antes.
- **React Router / URLs por herramienta** — el sistema actual usa estado `section`; el cambio requiere spec dedicado.
- **Refactor de `App.jsx`** (1000 líneas en un archivo).
- **Otras herramientas tributarias** (declaración IVA mensual, retención mensual declarada, conciliación bancaria) — cada una será spec independiente.
- **Motor ACL para mayores contables** (análisis Benford, gaps, redondeos sobre datasets grandes) — Fase 3 del roadmap original del usuario.
- **i18n EN/ES** — diferido; MVP solo español.
- **Multi-tenant separación física** (esquema por organización) — el modelo actual con `organization_id` en cada tabla es suficiente para volumen target.
- **Notificaciones por email** cuando termina un job.
- **Audit log avanzado** (qué usuario descargó qué Excel, cuándo).
- **Worker pool real (RQ/Celery)** — se evalúa si MVP demuestra cuello de botella.

---

## 16. Preguntas abiertas / bloqueos para implementar

Estas se resuelven antes o durante la implementación, no son bloqueos del diseño:

1. **¿Hay Alembic configurado en el repo?** Si no, M1.1 incluye decisión: agregar Alembic o usar `Base.metadata.create_all()` por ahora.
2. **Plantilla Excel exacta del usuario** (papel de trabajo manual actual) — requerida para M1.2.
3. **Set de 5-10 PDFs reales del SRI** (anonimizados está OK) — requerido para M1.2 fixtures.
4. **Cuenta Cloudflare R2** del usuario con bucket creado y credenciales — requerido para M1.1.
5. **Política de retención de archivos** — actualmente propuesta 90 días para `inputs/`; el usuario debe confirmar según sus prácticas de papeles de trabajo de auditoría.
6. ~~`audit_events` table~~ — RESUELTO: diferido. No existe en repo, MVP usa logs stdout (ver sección 12).

---

## 17. Documento de plan siguiente

Tras aprobación de este spec, se invoca la skill `superpowers:writing-plans` para generar:

`docs/superpowers/plans/2026-05-26-aud-retenciones-fuente-plan.md`

Que descompondrá M1.1 en pasos concretos de implementación (archivos a crear, orden, tests específicos, criterios de done por paso). Los milestones M1.2-M1.4 tendrán sus propios planes.
