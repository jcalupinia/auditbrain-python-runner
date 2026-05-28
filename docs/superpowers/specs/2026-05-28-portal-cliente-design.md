# Portal Cliente — Diseño técnico

**Fecha:** 2026-05-28
**Autor:** Jorge Vinicio (Lider Audit-IA) + Claude
**Estado:** Spec aprobado por el usuario, listo para fase de planificación
**Próximo paso:** Generar plan de implementación con `writing-plans`

---

## 0. Resumen ejecutivo

Construir el **Portal Cliente de Audit Consulting Group** (`auditbrain-clientes.onrender.com`), una aplicación web separada del portal interno de AuditBrain donde los clientes externos:

1. Inician sesión con credenciales creadas por el staff
2. Acceden a un catálogo de herramientas de automatización de auditoría
3. Suben sus documentos contables/tributarios
4. Descargan entregables generados automáticamente
5. Sus archivos se eliminan a las 24 horas post-procesamiento

**Branding:** Logo Audit Consulting Group + tagline "Powered by Audit-IA".

**Alcance de ESTE spec:** Solo el **esqueleto del portal** (auth, seguridad, catálogo, shell de upload/proceso/descarga, infraestructura). La lógica de las herramientas específicas (ICT 2025, NIIF 9 ECL, NIIF 16, etc.) va en specs separados que se ejecutarán después.

**Decisión arquitectónica clave:** Opción B — Backend único de FastAPI (extensión del AuditBrain existente) + 2 frontends Vite separados (`frontend/` actual + `frontend-client/` nuevo) desplegados como Static Sites en Render.

---

## 1. Decisiones tomadas (resumen para futura referencia)

| # | Decisión | Valor |
|---|----------|-------|
| 1 | Usuario final del ICT | Self-service total: el cliente descarga y presenta él mismo al SRI |
| 2 | URL portal cliente | `auditbrain-clientes.onrender.com` (subdominio Render, sin DNS propio) |
| 3 | URL portal staff | `auditbrain-app.onrender.com` (existente; nombre exacto se confirma en deploy) |
| 4 | URL backend API | `auditbrain-api.onrender.com` (existente; nombre exacto se confirma en deploy) |
| 5 | Creación de cuentas cliente | Solo el admin staff las crea desde el portal interno. NO hay auto-registro. |
| 6 | Vinculación a dispositivo | 1 dispositivo por usuario. Reseteo solo por admin staff. |
| 7 | Política de sesión | 1 sesión activa a la vez. Nuevo login GANA (expulsa la anterior). |
| 8 | Alcance política seguridad estricta | Solo portal cliente. Staff sin restricción. |
| 9 | Alcance MVP | Solo esqueleto del portal + categorías "Próximamente". Las herramientas concretas van en specs aparte. |
| 10 | Catálogo visual | Tarjetas por categoría (mismo patrón que el catálogo interno de AuditBrain). |
| 11 | Retención de datos | 24h post-procesamiento → eliminación total de inputs y outputs. Solo queda metadata en DB. |
| 12 | Landing page pública | Sí, con marketing + CTA "Ingresar". |
| 13 | Notificaciones | Pantalla en vivo (polling) + email automático al completar. |
| 14 | Arquitectura | Opción B: backend único + 2 frontends separados. |
| 15 | Storage de archivos | `/tmp` (mismo patrón que módulo `obligaciones_fiscales` existente). |
| 16 | Email transaccional | Resend (free tier suficiente para MVP). |

---

## 2. Arquitectura general

### 2.1 Vista en alto nivel

```
                         INTERNET
                            │
       ┌────────────────────┼─────────────────────────────┐
       ▼                    ▼                             ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│ auditbrain-  │  │ auditbrain-      │  │ www.auditconsulting.ec   │
│ app.onrender │  │ clientes.        │  │ (web pública corporativa,│
│ .com (staff) │  │ onrender.com     │  │  fuera de scope)         │
└──────┬───────┘  └────────┬─────────┘  └──────────────────────────┘
       │                   │
       ▼                   ▼
┌──────────────┐  ┌──────────────────────┐
│ Static Site  │  │ Static Site (NUEVO)  │
│ frontend/    │  │ frontend-client/     │
└──────┬───────┘  └──────────┬───────────┘
       │                     │
       └──────────┬──────────┘
                  ▼
         ┌──────────────────────────┐
         │ auditbrain-api.onrender  │
         │ .com (Backend FastAPI)   │
         └──────────┬───────────────┘
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
    ┌──────────┐   ┌──────────────────┐
    │ Postgres │   │ /tmp (TTL 24h)   │
    │ (Render) │   │ inputs + outputs │
    └──────────┘   └──────────────────┘
```

### 2.2 Nuevos módulos en el backend

```
backend/app/
├── auth/               ← Se extiende
│   ├── models.py       ← Añade ClientDevice + columnas a User
│   ├── deps.py         ← Añade require_client_with_device()
│   └── device.py       ← NUEVO: fingerprint + validación dispositivo
│
├── client_portal/      ← NUEVO
│   ├── router.py       ← /api/v1/client/auth/*, /catalog, /tools/*
│   ├── service.py      ← Lógica negocio del portal cliente
│   ├── schemas.py      ← Pydantic models
│   ├── tool_registry.py← Registry: code → (slots, mimes, processor)
│   └── jobs.py         ← Dispatcher genérico process_tool_job()
│
├── notifications/      ← NUEVO
│   ├── email.py        ← Wrapper de Resend + retry con backoff
│   └── templates/      ← HTML transactional templates
│
├── staff_portal/       ← NUEVO (rutas que el staff usa para gestionar clientes)
│   └── client_admin.py ← /api/v1/staff/clients/{id}/portal-users, /devices
│
└── aud/                ← Sin cambios (módulo OF existente)
```

### 2.3 Nueva carpeta frontend-client

```
frontend-client/                ← Proyecto Vite paralelo
├── public/
│   └── assets/
│       └── logo-auditconsulting-group.png
├── src/
│   ├── landing/                ← Página marketing pública
│   │   ├── Hero.jsx
│   │   ├── Features.jsx
│   │   └── CTAs.jsx
│   ├── auth/
│   │   ├── Login.jsx
│   │   ├── ChangePassword.jsx  ← Forzado al primer login
│   │   └── DeviceBlocked.jsx   ← "Tu dispositivo no está autorizado"
│   ├── catalog/
│   │   └── ClientCatalog.jsx   ← Tarjetas por categoría
│   ├── tools/
│   │   └── ToolShell.jsx       ← Shell común upload/proceso/descarga
│   ├── shared/                 ← Cliente HTTP, hooks, providers
│   └── App.jsx                 ← Router minimalista (react-router opcional)
├── package.json
└── vite.config.js

frontend-shared/                ← NUEVO: componentes UI reutilizables
├── components/
│   ├── Button.jsx
│   ├── Input.jsx
│   ├── Modal.jsx
│   └── ProgressBar.jsx
└── package.json                ← npm workspace local
```

### 2.4 Despliegue en Render

| Servicio | Tipo | URL |
|----------|------|-----|
| `auditbrain-backend` (existente) | Web Service | `auditbrain-api.onrender.com` |
| `auditbrain-frontend-staff` (existente) | Static Site | `auditbrain-app.onrender.com` |
| `auditbrain-frontend-client` (NUEVO) | Static Site | `auditbrain-clientes.onrender.com` |
| `auditbrain-db` (existente) | PostgreSQL | interno |

Los Static Sites en Render son **gratuitos**. Sin costos extra de infraestructura.

---

## 3. Modelos de datos

### 3.1 Extensión del modelo `User` existente

```python
# backend/app/auth/models.py
class Role(str, enum.Enum):
    admin = "admin"
    user = "user"
    client = "client"   # NUEVO

class User(Base):
    # Campos existentes (id, email, hashed_password, role, is_active, created_at,
    # organization_id, active_project_id)
    
    # NUEVOS:
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    password_reset_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    current_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

**Decisión:** reutilizamos `User` en vez de crear `ClientUser` separada para evitar duplicar lógica de auth.

### 3.2 Nueva tabla `ClientDevice`

```python
class ClientDevice(Base):
    __tablename__ = "client_devices"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    fingerprint_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_first_seen: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
```

### 3.3 Extensión de `ToolJob` existente

```python
# backend/app/aud/obligaciones_fiscales/models.py (ya existe)
class ToolJob(Base):
    # Campos existentes
    
    # NUEVOS:
    initiated_from: Mapped[str] = mapped_column(
        String(16), default="staff", nullable=False  # "staff" | "client"
    )
    notify_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # expires_at YA existe → mantenemos TTL 24h.
```

**Decisión:** se respeta `expires_at` existente. El cron `cleanup.py` actual sigue funcionando sin cambios.

---

## 4. Endpoints HTTP nuevos

Todos prefijados en `/api/v1/`.

### 4.1 Autenticación cliente

| Método | Ruta | Quién | Qué hace |
|--------|------|-------|----------|
| `POST` | `/client/auth/login` | Público | Login (email + password). Devuelve JWT + setea cookie `device_id`. |
| `POST` | `/client/auth/change-password` | Cliente con `password_reset_required=True` | Cambia clave inicial. Obligatorio antes de usar el portal. |
| `GET` | `/client/auth/me` | Cliente autenticado | Devuelve datos + estado del dispositivo. |
| `POST` | `/client/auth/logout` | Cliente | Invalida JWT actual (no toca device_id). |

### 4.2 Gestión de dispositivos (staff)

| Método | Ruta | Quién | Qué hace |
|--------|------|-------|----------|
| `GET` | `/staff/clients/{client_id}/devices` | admin/user | Lista dispositivos del cliente. |
| `POST` | `/staff/clients/{client_id}/devices/{device_id}/revoke` | admin | Revoca dispositivo específico. |
| `POST` | `/staff/clients/{client_id}/reset-device` | admin | Revoca TODOS los dispositivos del cliente. |
| `POST` | `/staff/clients/{client_id}/force-logout` | admin | Invalida `current_session_id`. |

### 4.3 Gestión de cuentas cliente (staff)

| Método | Ruta | Quién | Qué hace |
|--------|------|-------|----------|
| `POST` | `/staff/clients/{client_id}/portal-users` | admin | Crea cuenta de portal. Genera password temporal y lo retorna. |
| `GET` | `/staff/clients/{client_id}/portal-users` | admin/user | Lista usuarios cliente activos. |
| `POST` | `/staff/clients/{client_id}/portal-users/{user_id}/disable` | admin | Suspende cuenta sin borrar. |
| `DELETE` | `/staff/clients/{client_id}/portal-users/{user_id}` | admin | Soft delete (marca `deleted_at`). |

### 4.4 Catálogo y herramientas del cliente

| Método | Ruta | Quién | Qué hace |
|--------|------|-------|----------|
| `GET` | `/client/catalog` | Cliente | Catálogo de categorías + tools habilitados para ESTE cliente (filtro por organización). |
| `POST` | `/client/tools/{tool_code}/jobs` | Cliente | Crea job (patrón OF). Recibe archivos vía multipart. |
| `GET` | `/client/tools/jobs/{job_id}` | Cliente (dueño) | Estado del job. Polling cada 2s desde frontend. |
| `GET` | `/client/tools/jobs/{job_id}/download` | Cliente (dueño) | Descarga el entregable. Valida ownership. |
| `GET` | `/client/tools/jobs?status={status}&limit={n}` | Cliente | Historial (últimas 24h porque después se borran archivos). Query params opcionales: `status` (pending/processing/done/error/error_partial), `limit` (default 20). Usado por el frontend al recargar para retomar polling de job activo. |

### 4.5 Guarda de seguridad transversal

Toda ruta `/client/*` pasa por:

```python
# backend/app/auth/deps.py
def require_client_with_device(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """
    Valida 3 capas:
    1. JWT válido + rol == "client"
    2. Cookie device_id presente y activa para este usuario
    3. JWT.sid == User.current_session_id (sesión única)
    
    Códigos:
    - 401: JWT inválido/expirado
    - 403: rol incorrecto
    - 409: device_id no autorizado
    - 401 + clave "session_invalidated": JWT.sid != current_session_id
    """
```

---

## 5. Flujo de datos paso a paso

### 5.1 Paralelismo con módulo `obligaciones_fiscales`

| Paso | Obligaciones Fiscales (existente) | Portal Cliente (nuevo) |
|------|-----------------------------------|------------------------|
| Endpoint upload | `POST /aud/obligaciones-fiscales/jobs` | `POST /client/tools/{tool_code}/jobs` |
| Guarda seguridad | `get_current_user` | `require_client_with_device` (3 capas) |
| Validar MIMEs | `ALLOWED_MIMES` hardcoded | Cargado desde `tool_registry` |
| Crear ToolJob | `service.create_job(...)` | `service.create_job(...)` + `initiated_from="client"` + `notify_email=user.email` |
| Crear /tmp | `file_storage.create_job_dir(job.id)` | **Idéntico** |
| Guardar archivos | `file_storage.save_input(...)` | **Idéntico** |
| Lanzar worker | `background_tasks.add_task(jobs.process_job, ...)` | `background_tasks.add_task(jobs.process_tool_job, ...)` |
| Worker | `process_job` hardcoded OF | `process_tool_job` lee `tool_code` y delega al módulo del tool |
| Marcar done | `service.mark_done(...)` | **Idéntico** + dispara `notifications.email.send_job_ready(job)` |
| Polling | `GET /jobs/{id}` | `GET /client/tools/jobs/{id}` (distinta guarda) |
| Descarga | `GET /jobs/{id}/download` | **Idéntico** + valida `job.user.client_id == current.client_id` |
| Cron TTL | `cleanup.py` existente | **Mismo cron**, sin cambios |

### 5.2 Lo único realmente nuevo (4 piezas)

1. **`backend/app/auth/device.py`** — fingerprint + validación dispositivo
2. **`backend/app/client_portal/jobs.py`** — dispatcher genérico `process_tool_job`
3. **`backend/app/client_portal/tool_registry.py`** — registry `TOOLS = {"ICT_2025": ict_module, ...}`
4. **`backend/app/notifications/email.py`** — wrapper Resend

### 5.3 Diagrama de secuencia (resumido)

```
Cliente → Frontend → Backend → Worker → DB/tmp

1.  Click "Procesar" + multipart upload
2.  Validar 3 capas seguridad (JWT, device_id, sid)
3.  Crear ToolJob (pending) + /tmp/{id}/inputs/{slot}/*
4.  BackgroundTask: process_tool_job(id)
5.  Frontend hace polling cada 2s → GET /jobs/{id}
6.  Worker: lee inputs → procesa → escribe /tmp/{id}/output.xlsx
7.  Worker: marca status=done + dispara email Resend
8.  Frontend ve status=done → muestra botón "Descargar"
9.  Descarga: GET /jobs/{id}/download → StreamingResponse
10. +24h → cron cleanup borra /tmp/{id}/ y marca expired
```

---

## 6. Manejo de errores y casos borde

### 6.1 Errores de upload

| Caso | HTTP | Mensaje cliente | Acción |
|------|------|-----------------|--------|
| Archivo > 50 MB | 413 | "Archivo {nombre} excede 50 MB" | Limpia /tmp + DB |
| MIME no permitido | 415 | "Tipo {mime} no válido para {slot}" | Limpia /tmp + DB |
| Slot obligatorio vacío | 400 | "Falta archivo obligatorio: {slot}" | No crea job |
| Cierra navegador a mitad | n/a | n/a (reintenta) | Cron limpia órfanos > 1h |
| Suma total > 200 MB | 413 | "Total excede 200 MB" | Limpia parciales |
| Job concurrente existente | 409 | "Tiene otro trabajo en proceso" | Bloquea creación |

### 6.2 Errores de procesamiento (worker)

| Caso | Estado final | Mensaje cliente | Acción |
|------|--------------|-----------------|--------|
| PDF escaneado sin OCR | `error` | "Súbelo en versión digital o con OCR" | Email automático con causa |
| XML no cumple esquema SRI | `error` | "XML inválido. Descárgalo del SRI nuevamente" | Email + log staff |
| Casillero esperado falta | `error_partial` | "Cuadros incompletos por casillero faltante" | Excel parcial con advertencia |
| Estructura Balance no reconocida | `error` | "Verifica formato exportado del ERP" | Email con guía |
| Worker timeout (>300s) | `error` | "Procesamiento tardó más de lo permitido" | Alerta staff |
| Crash no manejado | `error` | "Error técnico. Hemos sido notificados" | Stack trace a log staff |
| Fórmulas Excel con #REF! | `error_partial` | "Excel con errores en algunas fórmulas" | Descarga permitida con advertencia |
| /tmp lleno | `error` | "Error temporal de almacenamiento" | Cron forzado + alerta |

### 6.3 Errores de seguridad/sesión

| Caso | Comportamiento |
|------|----------------|
| JWT expira durante job | Job sigue procesando. Cliente debe relogin. Al volver, ve job en historial. |
| Otra sesión inicia (sid distinto) | Sesión actual fuera. Mensaje: "Sesión cerrada. Otro inició con sus credenciales." Email alerta a cliente + admin. |
| Staff revoca dispositivo durante job | Job sigue corriendo. Cliente queda fuera hasta reseteo. Al volver, ve job completado. |
| IDOR (job_id de otro cliente) | 403. Log intento sospechoso al staff. |
| Upload desde dispositivo no autorizado | 409 + pantalla "Notificar al staff" |

### 6.4 Ciclo de vida

| Caso | Comportamiento |
|------|----------------|
| Cliente cierra navegador durante "Procesando" | Backend sigue. Email automático al completar. Cliente puede volver y descargar. |
| Cliente recarga página de progreso | Frontend al cargar busca job activo con `GET /jobs?status=processing` y retoma polling. |
| 2 pestañas mismo job | Ambas hacen polling al mismo `job_id`. Sin conflicto. |
| Descarga después de 24h | 410 Gone + botón "Reprocesar". |
| Email no llega (Resend caído, spam, inválido) | Job no depende del email. Cliente puede ver en "Mis trabajos". Resend: 3 retries con backoff. |
| Cron de limpieza falla | Próximo run limpia todos los huérfanos pendientes. |

### 6.5 Infraestructura

| Caso | Riesgo | Mitigación |
|------|--------|------------|
| Render reinicia container con jobs activos | BackgroundTasks se pierden, jobs "zombie" en `processing` | Cron detecta jobs `processing` con `started_at > 30 min` → marca `error` + email cliente |
| DB desconecta mid-worker | Output queda huérfano | try/except + rollback + retry. Si persiste, `error` |
| 2 workers procesan mismo job | Output se sobrescribe | Lock optimista: `UPDATE WHERE status='pending'`. Si 0 filas, abandona. |
| Resend caído | Cliente no recibe notificación | 3 retries con backoff. Marca `send_failed`. Cliente ve job en historial. |
| /tmp lleno | Uploads fallan | Cron preventivo si > 80% capacidad |

### 6.6 Acciones administrativas

| Acción staff | Efecto en jobs activos |
|--------------|------------------------|
| Revoca dispositivo | Jobs siguen corriendo. Cliente fuera hasta nuevo login autorizado. |
| Suspende cuenta (`is_active=False`) | Job en curso **se completa normalmente** (worker no tiene checkpoints en MVP, YAGNI). Cliente no podrá hacer login para descargar. Archivos eliminados a las 24h por TTL normal. Si el staff necesita aborto inmediato, ejecuta DELETE manual del job desde portal interno (lo cual sí limpia /tmp inmediatamente). |
| Elimina cliente (soft delete) | Todos sus jobs eliminados, archivos limpiados, metadata preservada. |
| Force logout | Invalida `current_session_id`. Cliente debe relogin. Jobs no afectados. |

### 6.7 Estados posibles de `ToolJob`

```
pending       → Recién creado, archivos guardados, worker en cola
processing    → Worker ejecutándose
done          → Excel generado, disponible para descarga
error         → Falló (causa en error_message)
error_partial → Generó output con advertencias (descargable, con notas)
expired       → Archivos eliminados por TTL (metadata permanece)
cancelled     → Futuro, no MVP
```

### 6.8 Principios de mensajes al cliente

Todos los mensajes:
1. **Dicen QUÉ pasó** (sin jerga técnica)
2. **Dicen QUÉ HACER** (acción concreta)
3. **Ofrecen SALIDA** (botón "Reintentar" o "Contactar soporte")

**Nunca mostrar al cliente:** stack traces, códigos de error técnicos crudos, rutas filesystem, detalles DB.

---

## 7. Estrategia de testing

### 7.1 Pirámide

- **Unit (50-80 tests):** funciones puras — validaciones, helpers, dispatcher, fingerprint
- **Integration (20-30 tests):** API + DB reales con SQLite en memoria
- **E2E (5-8 tests):** Playwright contra stack desplegado

### 7.2 Tests críticos de aislamiento (no negociables)

```python
def test_client_a_cannot_access_client_b_jobs(): ...
def test_client_cannot_access_staff_endpoints(): ...
def test_staff_cannot_access_client_endpoints_with_staff_jwt(): ...
def test_client_catalog_filtered_by_organization(): ...
def test_client_cannot_change_own_role_via_api(): ...
```

### 7.3 Tests de autenticación cliente

- Login primera vez crea device
- Login desde device distinto → rechazado
- Segundo login invalida primer JWT (sesión única)
- `password_reset_required` bloquea otros endpoints hasta cambio
- JWT expirado → 401 con mensaje claro
- Rate limiting en `/client/auth/login` (5 intentos / 15 min / IP)

### 7.4 Tests de flujo completo

- Happy path upload → procesa → descarga
- Upload bloqueado si hay job activo (409)
- Upload con archivo grande limpia /tmp
- Descarga > 24h → 410 con CTA reprocesar
- Worker zombie detectado por cron y marcado `error`

### 7.5 Escenarios E2E (Playwright)

1. Landing → login → cambio password → catálogo
2. Upload → progreso → descarga Excel
3. Login en device A → intento en device B → pantalla bloqueo
4. Sesión abierta + otro login → modal "sesión cerrada"
5. Upload PDF escaneado → mensaje error específico
6. Staff crea cliente, copia password temporal
7. Staff revoca dispositivo → cliente ve pantalla correcta
8. Descarga a 23h ok, a 25h "expirado" con "Reprocesar"

### 7.6 Checklist de seguridad pre-producción

- [ ] JWT secret robusto, no hardcoded
- [ ] Cookie `device_id` con `HttpOnly`, `Secure`, `SameSite=Strict`
- [ ] `/client/*` rechaza SIEMPRE roles admin/user
- [ ] `/staff/*` rechaza SIEMPRE rol client
- [ ] `job_id` validado por ownership en CADA endpoint
- [ ] Filenames sanitizados (sin path traversal)
- [ ] Validación de MIME real (no solo extensión)
- [ ] CORS estricto: solo dominios Render del proyecto
- [ ] Rate limiting login
- [ ] Passwords con bcrypt (ya existe)
- [ ] Logs no exponen secrets
- [ ] Mensajes auth genéricos ("Credenciales incorrectas")

### 7.7 Cobertura mínima exigida

| Capa | Cobertura mínima |
|------|------------------|
| `auth/device.py` + `deps.py` | 95% |
| `client_portal/*` | 85% |
| `notifications/email.py` | 80% |
| Frontend componentes críticos (Login, ToolShell, Catalog) | 70% |
| Frontend landing | No exigido |

### 7.8 Fuera de scope de testing

- Lógica específica de cada herramienta (ICT, NIIF) — va en sus specs
- Render como plataforma
- Cleanup de /tmp — ya testeado en módulo OF
- Performance/load testing — fase 2

### 7.9 CI/CD

```yaml
on: pull_request
jobs:
  - unit + integration tests (pytest)   # obligatorio merge
  - lint (ruff)                         # obligatorio merge
  - frontend build (vite)               # obligatorio merge
  - E2E (playwright)                    # obligatorio antes de deploy producción
```

---

## 8. Lo que queda FUERA de este spec

Este spec define solo el **esqueleto del portal**. Lo siguiente va en specs separados:

- **Spec ICT 2025**: lógica del Anexo de Cumplimiento Tributario (parseo F-101/104/103/108, balance, contratos, generación Excel oficial SRI)
- **Spec NIIF 9 ECL**: Matriz de Pérdidas Esperadas (cuentas por cobrar)
- **Spec NIIF 9 Pérdidas Incurridas**: modelo anterior (referencia)
- **Spec NIIF NIC 2 VNR**: Valor Neto de Realización de inventarios
- **Spec NIIF Obsolescencia inventarios**
- **Spec NIIF NIC 16 Depreciación**: cálculo automático
- **Spec NIIF NIC 36 Deterioro activos fijos**
- **Spec NIIF 16 Arrendamientos**
- **Spec NIIF 15 Reconocimiento de ingresos**

Cada uno seguirá el mismo proceso: brainstorming → spec → plan → implementación.

---

## 9. Riesgos identificados y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Render reinicia con jobs activos | Alta | Medio | Zombie job detector en cron (>30 min) |
| Cliente pierde password temporal del email inicial | Media | Bajo | Admin staff puede regenerar desde portal interno |
| Cliente cambia de laptop y pide reseteo frecuente | Media | Bajo | Endpoint staff "reset-device" 1 click |
| Volumen de uploads simultáneos satura /tmp | Baja | Alto | Cron preventivo + alerta si /tmp > 80% |
| Resend free tier llega a límite | Baja | Bajo | Upgrade a tier pagado (~$20/mes) o swap a SendGrid |
| Cliente sube datos de otro cliente por error | Baja | Alto | Logs de auditoría + aislamiento estricto a nivel DB |
| Bug en device binding deja a TODOS los clientes fuera | Baja | Crítico | Tests de cobertura 95% en `auth/device.py` + endpoint admin "reset-all-devices" de emergencia |

---

## 10. Próximos pasos

1. **Usuario revisa este spec** y aprueba o pide cambios.
2. Una vez aprobado: invocar skill `writing-plans` para generar plan de implementación detallado con tareas, dependencias, secuencia.
3. Implementación incremental siguiendo el plan.
4. Una vez completado MVP del portal: nueva sesión de brainstorming para el spec del **ICT 2025** (primera herramienta concreta).

---

## Apéndice A — Stack técnico (resumen)

| Capa | Tecnología | Versión |
|------|------------|---------|
| Backend | FastAPI | 0.115+ (actual del repo) |
| ORM | SQLAlchemy | 2.0 |
| Auth | JWT (PyJWT) + OAuth2PasswordBearer | actual |
| Password hashing | bcrypt | actual |
| DB producción | PostgreSQL (Render managed) | 15+ |
| DB test | SQLite en memoria | builtin |
| Frontend | React + Vite | 18.3 / 5.4 |
| Email | Resend | API v1 |
| Storage | Filesystem `/tmp` (Render) | n/a |
| Tests | pytest + httpx + Playwright | actuales |
| Lint | ruff | actual |
| Deploy | Render (Web Service + 2 Static Sites) | n/a |
