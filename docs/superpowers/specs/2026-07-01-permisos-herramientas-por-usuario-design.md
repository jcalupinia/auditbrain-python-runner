# Diseño — Permisos de herramientas por usuario (gating comercial del portal cliente)

- **Fecha:** 2026-07-01
- **Autor:** AuditConsulting (jcalupinia) + Claude
- **Estado:** Aprobado (pendiente revisión final del usuario antes del plan)
- **Repo:** `auditbrain-python-runner`

## 1. Problema

Hoy el endpoint `GET /client/catalog`
(`backend/app/client_portal/router.py:361`) devuelve **todas** las herramientas
habilitadas a **todos** los clientes del portal, sin importar qué contrataron.
El propio código lo marca como deuda: *"Por ahora retorna TODAS las tools
habilitadas. Filtrado por organización es upgrade futuro (gating comercial)."*

El negocio necesita que **cada cuenta de cliente vea y pueda ejecutar solo las
herramientas que pagó** (según su suscripción). El administrador debe poder,
desde el Command Center, hacer clic en una cuenta de cliente y activar/desactivar
individualmente a qué herramientas accede.

## 2. Alcance

**Incluye:**
- Persistencia de permisos herramienta↔usuario.
- Filtrado del catálogo del portal cliente por permisos.
- Enforcement real al crear un job (no solo ocultar en la UI).
- Endpoints de administración (solo `admin`).
- Pantalla de detalle por cuenta en el Command Center (`Users`/Cuentas) con
  toggles por sección y herramienta.
- Backfill de los clientes existentes.

**NO incluye (YAGNI, descartado explícitamente):**
- Planes/perfiles reutilizables (suscripción por tiers). Se decidió **manual por
  usuario**. Si en el futuro hay muchos clientes con el mismo paquete, se puede
  agregar una capa de "planes" encima sin rehacer esto.
- Límites de uso (cuotas, max jobs/mes), fechas de expiración, cobros.
- Gating a nivel de operadores (`admin`/`user`): los operadores siguen viendo todo.

## 3. Decisiones de diseño (confirmadas con el usuario)

- **A — Granularidad: por USUARIO (`user_id`)**, no por empresa. Motivo: una
  empresa puede comprar una sola herramienta; si fuera por empresa, todas sus
  cuentas verían todo. El permiso vive por cada cuenta/correo del portal.
- **B — Comportamiento por defecto:**
  - **Usuario nuevo = sin acceso a nada** (deny-by-default). El admin enciende
    lo que corresponda.
  - **Backfill de los 56 clientes actuales:** conceder acceso **solo a las
    herramientas de la sección `TRIBUTARIAS`** (hoy = `ICT_2025`), para que
    nadie pierda el acceso que ya usa el día del deploy.
- **Enforcement doble:** el catálogo filtra (cosmético) **y** la creación de job
  valida (seguridad). Adivinar la URL no basta.

## 4. Modelo de datos

Nueva tabla `user_tool_entitlements` (una fila = una concesión de una herramienta
a una cuenta):

| Columna      | Tipo                | Notas                                        |
|--------------|---------------------|----------------------------------------------|
| `id`         | Integer PK          |                                              |
| `user_id`    | FK `users.id` CASCADE, index, not null | cuenta del portal (rol `client`) |
| `tool_code`  | String(64), index, not null | ej. `ICT_2025`                       |
| `enabled`    | Boolean, default True, not null | permite apagar sin borrar la fila |
| `created_at` | DateTime, default utcnow (naive) | patrón del repo                  |

- `UniqueConstraint(user_id, tool_code)` → `uq_entitle_user_tool`.
- **Ubicación del modelo:** `backend/app/auth/models.py` (junto a `User` y
  `ClientDevice`, ya que la FK es a `users`). Alternativa aceptable:
  `backend/app/context/models.py`. Elegimos `auth/models.py` por cohesión con `User`.
- **Creación:** `Base.metadata.create_all()` en `init_db()`
  (`backend/app/db/session.py`) la crea automáticamente. El import del módulo
  ya está registrado, no hace falta tocar `init_db` salvo para el backfill (§7).

## 5. Capa de servicio

Nuevo archivo `backend/app/client_portal/entitlements.py`:

```python
def can_access_tool(db, user_id: int, tool_code: str) -> bool
def list_user_tool_codes(db, user_id: int) -> set[str]
def set_user_entitlements(db, user_id: int, tool_codes: set[str]) -> None
```

- `set_user_entitlements` recibe el **conjunto completo** de herramientas que
  deben quedar activas para ese usuario y hace el upsert/limpieza (enciende las
  que están en el set, apaga/borra las que ya no). Semántica de "reemplazar
  estado", coherente con un `PUT`.
- Todas validan que el `tool_code` exista en `tool_registry.TOOLS` (ignoran
  códigos desconocidos para no persistir basura).

## 6. Backend — API

Todos los endpoints de administración van en el `global_router`
(prefijo `/staff`, `backend/app/staff_portal/router.py:233`) y exigen
`require_admin` (mismo patrón que los `/staff/portal-users/*` existentes).

1. **`GET /staff/tools`** → catálogo COMPLETO sin filtrar, para pintar la
   pantalla de permisos. Estructura: `[{id, label, description, tools:[{code,
   label, description}]}]` derivada de `CATEGORIES` + `TOOLS` (incluye
   categorías vacías; excluye la categoría `TESTING`).

2. **`GET /staff/portal-users/{user_id}/entitlements`** → `{ user_id,
   enabled_tool_codes: [...] }`. 404 si el usuario no existe o no es rol `client`.

3. **`PUT /staff/portal-users/{user_id}/entitlements`** → body
   `{ tool_codes: [...] }`. Reemplaza el set completo vía
   `set_user_entitlements`. Responde el estado resultante. 404 si el usuario no
   existe / no es `client`.

**Modificaciones a endpoints existentes** (`backend/app/client_portal/router.py`):

4. **`GET /client/catalog`** (`:361`): hoy ignora al `user`. Cambiar para:
   - obtener `allowed = list_user_tool_codes(db, user.id)`;
   - incluir en la respuesta solo las tools cuyo `code ∈ allowed`.
   - Requiere inyectar `db: Session = Depends(get_db)` (hoy no lo tiene).
   - Las categorías se siguen devolviendo todas (para que la sidebar del portal
     muestre las secciones); las vacías caen en el estado "Próximamente" que ya
     existe. *(Ver §9, decisión de UX de secciones vacías.)*

5. **`POST /client/tools/{tool_code}/jobs`** (crear job, ~`:239`): antes de crear,
   `if not can_access_tool(db, user.id, tool_code): raise HTTPException(403,
   "No tienes acceso a esta herramienta.")`.

## 7. Migración / Backfill

Backfill idempotente de una sola vez, ejecutado dentro de `init_db()` en
`backend/app/db/session.py` (después de `create_all`), protegido por un guard
para que corra una única vez:

- Detectar herramientas de la sección `TRIBUTARIAS` desde `tool_registry`
  (`[code for code, t in TOOLS.items() if t.category == "TRIBUTARIAS" and
  t.enabled]` → hoy `["ICT_2025"]`).
- Para cada `User` con `role == client`: si **no tiene ninguna** fila en
  `user_tool_entitlements`, insertar las de Tributarias con `enabled=True`.
- Guard de idempotencia: la condición "no tiene ninguna fila" ya evita
  duplicar en re-arranques. (Un usuario al que el admin le quitó todo
  intencionalmente y quedó en 0 filas volvería a recibir Tributarias en el
  próximo boot — por eso el guard correcto es un flag global de "backfill hecho",
  ej. una fila en una tabla `app_flags`/`meta`, o una env var
  `ENTITLEMENTS_BACKFILL_DONE`. **Decisión:** usar una marca persistente simple
  para no re-aplicar. Se define en el plan.)

## 8. Frontend — Command Center (`frontend/src/App.jsx`, componente `Users`)

- Cada fila de "Todas las cuentas de cliente"
  (`frontend/src/App.jsx:731-763`) y de "Clientes del portal" se vuelve
  **clickeable** (además de sus botones Resetear/Deshabilitar) → abre el
  **detalle de permisos** de esa cuenta.
- Detalle (panel o vista dentro del mismo módulo `USR`):
  - Encabezado con correo · empresa de la cuenta.
  - Lista de **secciones** (Tributarias, NIIF, Laborales, Societarias, Reportes
    Gerenciales) y dentro cada **herramienta** con un **switch on/off**.
  - Estado inicial = respuesta de `GET /staff/portal-users/{id}/entitlements`.
  - Catálogo de opciones = `GET /staff/tools`.
  - Botón **Guardar** → `PUT /staff/portal-users/{id}/entitlements` con el set
    de códigos activos. Feedback de éxito/error.
  - Botón **Volver** a la lista.
- Nuevas funciones en `frontend/src/api.js`: `getStaffTools()`,
  `getUserEntitlements(userId)`, `setUserEntitlements(userId, toolCodes)`.
- Estilo: reutiliza el tema oscuro premium y los componentes existentes
  (`Panel`, `ViewHead`, chips de código, switches). No introducir un sistema de
  diseño nuevo.

## 9. Detalles de UX a resolver en el plan (no bloquean el diseño)

- **Secciones vacías en el portal cliente:** hoy una categoría sin tools muestra
  "Próximamente". Con gating, un cliente sin ninguna herramienta de NIIF verá
  "Próximamente" en NIIF igual que hoy. Aceptable. Si se quiere ocultar por
  completo las secciones donde el cliente no tiene nada, se decide en el plan
  (opción menor de presentación).
- **Herramienta sin permiso pero URL directa** (`/tools/ICT_2025`): el front del
  portal debería manejar el 403 con un mensaje claro; el backend ya lo bloquea.

## 10. Pruebas (obligatorias por CLAUDE.md — verificación empírica)

Backend (`pytest`):
- `test_entitlements_service`: upsert/replace de `set_user_entitlements`,
  `can_access_tool`, `list_user_tool_codes`.
- `test_catalog_filtra_por_usuario`: usuario con solo `ICT_2025` recibe únicamente
  esa tool; usuario sin nada recibe categorías vacías.
- `test_crear_job_sin_permiso_403`: crear job de una tool no concedida → 403.
- `test_staff_entitlements_endpoints`: GET/PUT con `require_admin`; 404 para
  user inexistente o no-cliente; no-admin → 403.
- `test_backfill_tributarias`: tras backfill, un cliente preexistente tiene
  exactamente los códigos de la sección Tributarias; es idempotente en el
  segundo arranque.

Verificación empírica end-to-end (además de unit tests):
- Conceder a una cuenta real solo `ICT_2025`, iniciar sesión en el portal y
  confirmar que ve solo Tributarias con la tool, y que las demás secciones no
  ofrecen herramientas.
- Quitar `ICT_2025`, refrescar y confirmar que desaparece y que abrir la URL
  directa devuelve 403.
- Confirmar que los 56 clientes actuales conservan Tributarias tras el deploy.

## 11. Archivos afectados (resumen)

| Acción | Archivo |
|--------|---------|
| Nuevo modelo `UserToolEntitlement` | `backend/app/auth/models.py` |
| Nuevo servicio | `backend/app/client_portal/entitlements.py` |
| Endpoints admin `GET /staff/tools`, GET/PUT entitlements | `backend/app/staff_portal/router.py` |
| Filtrar catálogo + 403 en crear job + inyectar `db` | `backend/app/client_portal/router.py` |
| Backfill + (posible) flag de idempotencia | `backend/app/db/session.py` |
| Schemas Pydantic (entitlements, staff tools) | `backend/app/client_portal/schemas.py` y/o `staff_portal/schemas.py` |
| Pantalla de detalle de permisos + fila clickeable | `frontend/src/App.jsx` |
| Funciones API front | `frontend/src/api.js` |
| Tests | `backend/tests/` |

## 12. Riesgos

- **Romper acceso de clientes actuales** → mitigado por el backfill de
  Tributarias (§7) y test dedicado.
- **Enforcement incompleto** (solo ocultar en UI) → mitigado con el 403 en crear
  job (§6.5).
- **Backfill re-aplicándose** y re-otorgando acceso que el admin quitó →
  mitigado con marca persistente de "backfill hecho" (§7).
