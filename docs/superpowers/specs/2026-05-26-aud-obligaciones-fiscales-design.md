# Spec v3 — Herramienta `AUD.IMPUESTOS.OBLIGACIONES_FISCALES` (modelo efímero)

**Fecha:** 2026-05-26
**Autor:** Jorge Calupiña (jcalupinia@auditconsulting.ec)
**Co-diseño:** Claude (Opus 4.7)
**Estado:** v3 — espera revisión del usuario
**Reemplaza:** v1 (retenciones sola) y v2 (WorkingPaper persistente). Ambos archivados.

---

## 0. Resumen

Herramienta que recibe los documentos fiscales del auditor (PDFs F-103, F-104, ATS XML, mayores Excel), procesa todo con Python y devuelve un **Excel descargable** idéntico a la plantilla `DM Obligaciones Fiscales`. **Procesamiento efímero** — no se almacena nada en la nube; los archivos viven solo en `/tmp` del contenedor mientras dura el job (máximo 1h) y se borran tras la descarga.

La plantilla Excel `DM Obligaciones Fiscales` está **baked-in en el código** del sistema (no se sube por ejecución). El usuario solo sube los inputs (PDFs y mayores). El sistema produce las 11 cédulas pobladas.

**Alcance:** plataforma minimal + las 11 cédulas en **2 milestones** (~6 semanas).

---

## 1. Decisiones (capturadas durante brainstorming v3)

| Decisión | Valor |
|---|---|
| Storage | **Ninguno en la nube**. Solo `/tmp` del contenedor con TTL 1h. |
| Plantilla Excel | **Baked-in** en `backend/app/aud/obligaciones_fiscales/templates/dm_obligaciones_fiscales.xlsx` |
| Persistencia | Solo metadata del job (job_id, status, tiempos, summary). NO archivos NI cédulas calculadas en DB. |
| Workflow | **Ninguno** — no hay borradores, revisión, firma ni archivo. Solo: pending → running → done|failed |
| Multi-tenant | Sí, el job se asocia a `project_id` para autorización (sigue siendo SaaS multi-tenant con login) |
| Procesamiento | Síncrono dentro de BackgroundTask. 300-600s típicos. Cliente hace polling. |
| Generación de la herramienta | Por ejecución: cliente sube → procesa → descarga → borra |
| Otras cédulas (DM, DM1...) | Se calculan en el mismo job con datos disponibles. Si falta archivo (ej: no se subió F-101 para DM9), esa cédula queda con plantilla vacía marcada "Sin datos". |
| Modelo de datos | 1 tabla nueva (`tool_jobs`). Cero tablas para WorkingPapers, archivos, cédulas, audit log. |
| Catálogo de 15 categorías | Mostrado en UI con todas en "Próximamente" excepto "Impuestos" |
| Stack | El existente: FastAPI + React + Postgres + boto3 NO necesario (sin R2) |
| Idioma | Español únicamente |
| Auth | JWT existente |
| Capacidad dev | Usuario + Claude |

---

## 2. Ubicación en UI

```
Módulo AUD > Workspace cognitivo > Tab "Análisis"
 └─ "Pruebas de auditoría a través de herramientas"
     └─ 15 categorías (las otras 14 muestran "Próximamente")
         └─ 📁 Impuestos
             └─ 🔧 Auditoría de Obligaciones Fiscales
                 └─ Vista de la herramienta:
                     ├─ Zona de carga con sub-secciones por tipo:
                     │     · F-103 (Retenciones en la fuente) — 12 PDFs
                     │     · F-104 (IVA) — 12 PDFs
                     │     · ATS — 12 XMLs
                     │     · Mayor Compras — Excel
                     │     · Mayor Ventas — Excel
                     │     · F-101 (Renta anual) — 1 PDF (opcional)
                     ├─ Inputs de contexto:
                     │     · Cliente auditado (texto)
                     │     · Período (date range)
                     │     · Preparado por / Revisado por (text, opcionales)
                     ├─ Botón "Generar papel de trabajo"
                     ├─ Vista de progreso (procesando 5 de 12 archivos...)
                     ├─ Resumen al terminar (totales, hallazgos detectados)
                     └─ Botón "Descargar Excel"
```

**Limitación aceptada:** Si el usuario refresca o cierra la ventana durante el procesamiento, pierde la sesión del job. El Excel queda 1h en `/tmp` y luego se borra. Si lo necesita, debe volver a ejecutar.

---

## 3. Arquitectura efímera

```
┌──────────────────────┐
│  React (browser)     │
│  Upload UI           │
└──────────┬───────────┘
           │ 1. POST /jobs (multipart con TODOS los archivos)
           ▼
┌──────────────────────────────────────────────────┐
│  FastAPI                                          │
│  ├─ Crea ToolJob en DB (id, user, status=pending)│
│  ├─ Escribe archivos a /tmp/auditbrain/<id>/in/  │
│  ├─ Dispara BackgroundTask de procesamiento      │
│  └─ Responde {job_id, status: "running"}          │
└──────────┬───────────────────────────────────────┘
           │
           │ (en background, paralelo a HTTP)
           ▼
┌──────────────────────────────────────────────────┐
│  BackgroundTask jobs.process_job(job_id)         │
│  ├─ Lee inputs de /tmp/auditbrain/<id>/in/        │
│  ├─ Por cada cédula DM*:                          │
│  │     extractor + builder → dict de datos        │
│  ├─ excel_assembler:                              │
│  │     carga plantilla baked-in                   │
│  │     puebla las 11 pestañas con datos           │
│  │     guarda a /tmp/auditbrain/<id>/output.xlsx  │
│  ├─ UPDATE ToolJob status=done, summary_json     │
│  └─ (si falla) status=failed, error_message      │
└──────────────────────────────────────────────────┘

┌──────────────────────┐
│  React               │
│  Polling cada 2s     │ ─── GET /jobs/{id} ──► FastAPI ──► DB
└──────────┬───────────┘                                   │
           │ status: "done"                                 │
           │                                                ▼
           │ GET /jobs/{id}/download                       Lee /tmp/.../output.xlsx
           │ ◄────── stream del Excel ───────────────────  Marca downloaded_at
           │                                                Dispara borrado en 5min
           ▼
       Excel descargado en PC del usuario

┌────────────────────────────────────────────┐
│  Cron task (cada 5 min) — cleanup:        │
│  - Borra /tmp/auditbrain/<id>/ si          │
│      created_at > 1h O                     │
│      downloaded_at > 5min                  │
│  - Marca ToolJob status="expired"          │
└────────────────────────────────────────────┘
```

---

## 4. Estructura del módulo backend

```
backend/app/aud/
├── __init__.py
└── obligaciones_fiscales/
    ├── __init__.py
    ├── models.py                    # SQLAlchemy: ToolJob
    ├── schemas.py                   # Pydantic
    ├── service.py                   # create/get/cleanup jobs + autorización
    ├── router.py                    # Endpoints
    ├── jobs.py                      # BackgroundTask orquestador
    ├── cleanup.py                   # Cleanup periódico de /tmp y jobs expirados
    ├── excel_assembler.py           # Carga plantilla baked-in + puebla 11 pestañas
    ├── templates/
    │   └── dm_obligaciones_fiscales.xlsx   # Plantilla original (baked-in)
    └── cedulas/
        ├── __init__.py
        ├── base.py                  # Interface CedulaCompute
        ├── dm.py                    # DM Programa (plantilla)
        ├── dm1.py                   # DM1 Cuestionario
        ├── dm2.py                   # DM2 Sumaria
        ├── dm3.py                   # DM3 Revisión saldos
        ├── dm4.py                   # DM4 Compras
        ├── dm5.py                   # DM5 Ventas
        ├── dm6_iva.py               # DM6 IVA (F-104 → conciliación)
        ├── dm7_retenciones.py       # DM7 Retenciones (F-103 → conciliación)
        ├── dm8_ats.py               # DM8 ATS XML + cruce
        ├── dm9_limites.py           # DM9 Límite gastos (F-101)
        └── dm10_hallazgos.py        # DM10 Hallazgos (deriva de DM3-DM8)
```

**Reglas de borde:**
- `cedulas/*.py` = lógica pura (extractor + transformer), testeables sin DB ni HTTP
- `excel_assembler.py` = carga plantilla con openpyxl, escribe celdas según datos de cédulas
- `service.py` y `router.py` = capa con efectos
- `jobs.py` orquesta todo en background

---

## 5. DB schema (1 tabla nueva)

```python
class ToolJob(Base):
    __tablename__ = "tool_jobs"
    id: int PK
    user_id: FK users.id ON DELETE SET NULL
    project_id: FK projects.id ON DELETE CASCADE INDEX
    tool_code: str(64)                # "AUD.IMPUESTOS.OBLIGACIONES_FISCALES"
    status: str(16) DEFAULT 'pending' # pending|running|done|failed|expired
    cliente_name: str(200)            # input del usuario
    period_label: str(64)             # input del usuario
    period_start: date | null
    period_end: date | null
    prepared_by_name: str(120) | null # texto libre (no FK a user)
    reviewed_by_name: str(120) | null
    error_message: text | null
    summary_json: jsonb | null        # { cedulas_completed: [...], cedulas_skipped: [...], totals: {...} }
    created_at: datetime DEFAULT now()
    finished_at: datetime | null
    downloaded_at: datetime | null
    expires_at: datetime              # created_at + 1h

    # Notar: NO guardamos referencias a archivos. Los archivos viven en /tmp.
```

**Migración:** agregar a `init_db()` siguiendo el patrón existente del repo.

---

## 6. API REST

Todas bajo `/api/v1/aud/obligaciones-fiscales/`.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/jobs` | JWT user+ con acceso al proyecto | Crea job, sube archivos, dispara procesamiento. Multipart: `files_f103[]`, `files_f104[]`, `files_ats[]`, `mayor_compras`, `mayor_ventas`, `file_f101` + form fields (cliente_name, period_label, etc.). Devuelve `{job_id, status: "running"}`. |
| `GET` | `/jobs/{id}` | JWT + dueño job | Estado actual + summary. |
| `GET` | `/jobs/{id}/download` | JWT + dueño job + status=done | Stream del Excel; marca `downloaded_at`. |
| `DELETE` | `/jobs/{id}` | JWT + dueño job | Cancela job en curso o borra resultado. Limpia `/tmp`. |
| `GET` | `/jobs?project_id=X&limit=20` | JWT + project_id en sus proyectos | Lista de jobs recientes del proyecto (últimas 24h). Solo metadata para que el usuario vea qué ejecutó. |

**Validaciones del POST /jobs:**
- Al menos 1 PDF F-103 o 1 PDF F-104 (no se puede generar nada sin entradas mínimas)
- MIME types validados por slot: pdf para F-103/F-104/F-101, xml para ATS, xlsx para mayores
- Tamaño máx por archivo: 20 MB
- Tamaño total del request: 100 MB (configurable)
- `cliente_name`, `period_label` obligatorios

**Autorización (multi-tenant):**
- `project_id` debe estar en los proyectos del usuario (admin ve todo en su org)
- `GET/download/DELETE /jobs/{id}` valida que el job pertenece a un proyecto del usuario

---

## 7. Job lifecycle

```
                 POST /jobs           BackgroundTask
              ┌──────────────┐      ┌──────────────────┐
              │   pending    │ ───► │     running       │
              └──────────────┘      └─────────┬────────┘
                                              │
                          ┌───────────────────┼─────────────────┐
                          ▼                   ▼                 ▼
                     ┌─────────┐         ┌─────────┐       ┌─────────┐
                     │  done   │         │ failed  │       │ expired │
                     └─────────┘         └─────────┘       └─────────┘
                          │                                      ▲
                          │ download                             │
                          ▼                                      │
                     downloaded_at                               │
                          │                                      │
                          │ (cleanup 5min después)               │
                          └──► borra /tmp ──► (job sigue en DB)  │
                                                                 │
              cron cada 5min: si created_at > 1h ─────────────►──┘
```

**Garantías:**
- **No reentrant:** un job no se puede re-correr. Si el usuario quiere repetir, crea uno nuevo.
- **Cleanup robusto:** triple safety net:
  1. Después de descarga exitosa (5 min después)
  2. Después de 1h sin descarga (TTL natural)
  3. Cron cada 5min barre `/tmp/auditbrain/` por carpetas huérfanas
- **Concurrencia:** sin limit explícito por ahora. Render Starter aguanta 2-3 jobs concurrentes en /tmp sin saturar.

---

## 8. Cédulas — comportamiento por inputs disponibles

| Cédula | Inputs requeridos | Si faltan inputs |
|---|---|---|
| DM Programa | Solo metadata (cliente, periodo) | Siempre se llena con datos del job |
| DM1 Cuestionario | Ninguno (es manual) | Plantilla vacía con preguntas Si/No para llenar después en Excel |
| DM2 Cédula Sumaria | Mayor (Balance) — opcional | Si no hay mayor, plantilla con descripción de cuentas; valores en blanco |
| DM3 Revisión saldos | F-104 + Mayor | Si falta uno, queda parcialmente poblada con nota "Sin datos: Mayor" o "Sin datos: F-104" |
| DM4 Compras | Mayor Compras + F-104 (para casillero 480, etc.) | Si falta, vacía con nota |
| DM5 Ventas | Mayor Ventas + F-104 (para casillero 419, etc.) | Si falta, vacía con nota |
| **DM6 IVA** | 12 F-104 (mínimo 1) | Por cada mes faltante, fila con nota "Sin declaración" |
| **DM7 Retenciones** | 12 F-103 (mínimo 1) | Por cada mes faltante, fila con nota "Sin declaración" |
| DM8 ATS vs F-103/F-104 | ATS XML + F-103 + F-104 | Si falta ATS, cédula queda en blanco; si faltan los formularios, similar |
| DM9 Límite gastos | F-101 | Si no se sube F-101, cédula vacía con nota "Sin F-101 anual" |
| DM10 Hoja de Hallazgos | Resultados de DM3-DM8 | Lista los hallazgos que se detectaron en las cédulas que SÍ se pudieron computar |

**Diseño clave:** el sistema NUNCA falla por falta de inputs. Siempre produce el Excel — algunas cédulas vendrán con notas en celdas explicando qué falta.

---

## 9. Frontend (sin persistencia de UI)

**Archivos nuevos en `frontend/src/aud/`:**

```
frontend/src/aud/
├── catalog.js                   # Definición de las 15 categorías
├── ToolCatalog.jsx              # UI del catálogo (la mayoría "Próximamente")
├── ObligacionesFiscalesTool.jsx # UI principal de la herramienta
└── strings.js                   # i18n placeholder (solo ES en MVP)
```

**Cambios en `App.jsx`:** UN import + UN bloque condicional cuando `tab === "análisis" && module.id === "AUD"`.

**Flujo de UI (sin React Router, todo en estado):**

```
Estado 1: Lista de slots de upload + form (cliente, periodo)
  └─ Click "Generar papel de trabajo"
       └─ POST /jobs → job_id
            Estado 2: Procesando (polling, progress bar)
              └─ status=done
                   Estado 3: Resumen + botón "Descargar Excel"
                     └─ GET /jobs/{id}/download
                          Estado 4: "Descargado. Listo." 
                            └─ Botón "Nuevo papel de trabajo" → Estado 1
```

Si el usuario cierra la pestaña en Estado 2: el job sigue corriendo en backend pero se pierde la referencia. En `GET /jobs?project_id=X` aparecen los últimos jobs por si quiere recuperar uno.

---

## 10. Errores y edge cases

| Caso | Manejo |
|---|---|
| PDF F-104 corrupto | Cédula DM6 queda parcial con nota en la fila del mes correspondiente. Job termina `done`, no `failed`. |
| Faltan archivos críticos (ni 1 F-103 ni 1 F-104) | `POST /jobs` rechaza con 400. |
| Usuario cancela mid-job | `DELETE /jobs/{id}` mata el BackgroundTask (best-effort) + borra `/tmp`. |
| Render reinicia mid-job | Job queda `running` huérfano → cleanup lo marca `failed` con mensaje "container restart". |
| Excel resultado > 50 MB | OK — stream directo. Render no impone límite específico de response size. |
| Usuario descarga el Excel pero pierde el archivo | Tiene hasta 5 min para re-descargar antes del cleanup. Después debe regenerar. |
| Job tarda más de 1h | Marcamos `expired`, borramos `/tmp`. Usuario debe reintentar (job nunca debe tardar tanto realmente — sospechoso). |
| Usuario sin proyecto activo | UI bloquea con mensaje; backend 400. |
| Cross-tenant access | 403 + log. |
| Concurrencia: 10 usuarios disparan jobs simultáneos | Cada uno crea su propio `/tmp/auditbrain/<id>/`; FastAPI BackgroundTask los procesa en serie en cada worker. Render Starter tiene ~1-2 workers. Si saturamos, el polling muestra "running" por más tiempo — degradación graceful. |

---

## 11. Observabilidad

- Logs JSON en stdout: `job_id`, `user_id`, `project_id`, `step`, `duration_ms`, `error?`.
- `summary_json` siempre poblado con totales por cédula y conteos.
- `GET /jobs?project_id=X` da visibilidad de los jobs recientes para debugging.
- **Sin audit log persistente** — no aplica al modelo efímero.

---

## 12. Testing

| Capa | Tipo | Ubicación |
|---|---|---|
| `cedulas/dm*.py` (lógica pura) | Unit | `tests/test_aud_of_cedula_<code>.py` |
| `excel_assembler.py` | Unit (carga plantilla baked-in + assert celdas) | `tests/test_aud_of_excel_assembler.py` |
| `service.py` + `jobs.py` | Integration (sqlite + tmp_path fixture) | `tests/test_aud_of_service.py`, `test_aud_of_jobs.py` |
| `router.py` | Integration (TestClient + JWT) | `tests/test_aud_of_router.py` |
| `cleanup.py` | Unit | `tests/test_aud_of_cleanup.py` |
| End-to-end | Manual con checklist | `docs/AUD_OF_M*_E2E.md` |

**Fixtures binarios** en `tests/fixtures/obligaciones_fiscales/`:
- 1 F-103 anonimizado (✅ tenemos `Declaracion 103 de enero.pdf` del usuario)
- 1 F-104 anonimizado (✅ tenemos `Declaracion 104 DE ENERO.pdf`)
- 1 ATS XML (pendiente del usuario)
- 1 mayor Compras Excel (pendiente)
- 1 mayor Ventas Excel (pendiente)
- 1 F-101 PDF (pendiente)

---

## 13. Milestones

Solo **2 milestones**.

### M1 — Plumbing efímero + cédulas DM6 (IVA) y DM7 (Retenciones)
**Objetivo:** Subir F-103 y F-104, generar Excel con las 2 cédulas más importantes pobladas; el resto de cédulas aparecen como plantilla vacía con nota.

Deliverables:
- 1 tabla `tool_jobs` + migración en `init_db()`
- Endpoints `POST/GET/DELETE /jobs` + `GET /jobs/{id}/download`
- `excel_assembler.py` carga la plantilla baked-in (`templates/dm_obligaciones_fiscales.xlsx`) y puebla DM6 + DM7
- `cedulas/dm6_iva.py` + `cedulas/dm7_retenciones.py` con extractor pdfplumber + transformer
- Cleanup task de `/tmp` y jobs expirados
- Frontend: `ToolCatalog.jsx` (15 categorías) + `ObligacionesFiscalesTool.jsx` (flujo upload → proceso → descarga)
- Tests: ~20 nuevos

Criterio de éxito: login → AUD → Análisis → Impuestos → "Auditoría de Obligaciones Fiscales" → subir los 12 F-103 + 12 F-104 reales → "Generar" → ver progreso → descargar Excel con pestañas DM6 IVA y DM7 Retenciones POBLADAS y conciliadas con valores reales (resto de pestañas con datos del header + nota "Sin datos").

Estimación: ~4-5 semanas.

**Bloqueos:** Plantilla Excel ✅; F-103 muestra ✅; F-104 muestra ✅.

### M2 — Resto de cédulas
**Objetivo:** Cédulas DM, DM1, DM2 (plantillas/manuales), DM3-DM5 (con mayores Excel), DM8 (ATS XML), DM9 (F-101), DM10 (hallazgos derivados).

Deliverables:
- 9 cédulas adicionales en `cedulas/`
- Parser de mayor Excel + parser ATS XML + extractor F-101
- Excel assembler completo (11 pestañas pobladas)
- Tests por cada cédula

Criterio de éxito: subir TODOS los inputs → descargar Excel con las 11 pestañas pobladas, equivalente al hecho manualmente.

Estimación: ~6-8 semanas.

**Bloqueos:** mayores Excel muestra; ATS XML muestra; F-101 muestra.

---

## 14. Out of scope

- WorkingPaper persistente / workflow / firma / archivo — descartado por decisión del usuario (modelo efímero)
- Cloudflare R2 o cualquier object storage — descartado
- Audit log persistente — descartado (los logs van solo a stdout)
- Multi-tenant separación física (esquema por org) — no aplica al modelo efímero
- Otras categorías del catálogo (las 14 fuera de "Impuestos") — placeholders "Próximamente"
- Otros módulos (TAX, FIN, etc.) — sin cambios
- React Router — diferido
- Refactor de `App.jsx` — diferido; nuevo código va a `frontend/src/aud/`
- i18n inglés — diferido
- Notificaciones por email cuando termina un job — diferido
- Validación SRI por web service — diferido (solo si el usuario lo pide en M2+)
- Versionado de plantillas — la plantilla es 1 sola baked-in. Si cambia, se actualiza el archivo y se redeploya.

---

## 15. Bloqueos y dependencias

| # | Bloqueo | Estado |
|---|---|---|
| 1 | Plantilla `DM - Obligaciones Fiscales Final.xlsx` | ✅ disponible en `C:/Users/jcalu/Downloads/Prueba Cloude/Prueba Cloude/` |
| 2 | F-103 muestra (enero) | ✅ disponible |
| 3 | F-104 muestra (enero) | ✅ disponible |
| 4 | F-103 y F-104 de meses adicionales (al menos 3-4 más para validar variaciones) | ⏳ pendiente del usuario |
| 5 | ATS XML muestra | ⏳ pendiente (requerido para M2) |
| 6 | Mayor Compras Excel muestra | ⏳ pendiente (requerido para M2) |
| 7 | Mayor Ventas Excel muestra | ⏳ pendiente (requerido para M2) |
| 8 | F-101 PDF muestra | ⏳ pendiente (requerido para M2) |
| 9 | Confirmación del usuario: ¿OK con que /tmp en Render no es estrictamente "ningún disco"? Es tmpfs (RAM) o disco efímero según config Render. | ⏳ se asume OK basado en "no se queda en la nube" |

---

## 16. Documento siguiente

`docs/superpowers/plans/2026-05-26-aud-obligaciones-fiscales-m1.md` — plan detallado de M1 (a generar tras aprobación de este spec).
