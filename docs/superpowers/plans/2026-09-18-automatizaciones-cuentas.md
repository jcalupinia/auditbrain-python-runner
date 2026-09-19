# Automatizaciones en el Command Center · Plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development o superpowers:executing-plans. Los pasos usan casillas (`- [ ]`).

**Objetivo:** que las claves de los cuatro grupos se administren desde el Command Center. Para Automatizaciones, la firma crea la **empresa cliente y su administrador**; ese administrador crea dentro de la app las cuentas de **su propio personal**.

**Decisiones del usuario (18-sep):**
1. Control de cuentas centralizado en el Command Center para los 4 grupos: personal de oficina, clientes, recursos gratuitos y automatizaciones.
2. Dos niveles en Automatizaciones: la firma crea al administrador de la empresa; el administrador crea a su personal.
3. Mismo juego de acciones que hoy existe en cuentas: crear, **restablecer clave**, **dar de baja y reactivar**, **borrar**.
4. Correo por **Resend** con el remitente ya verificado `no-reply@auditconsulting.ec`. No se verifica `audit-ia.ec` por ahora.
5. Registro público cerrado en la app: nadie entra sin ser creado o invitado.

**Arquitectura:** el Command Center (FastAPI en Render) actúa como **central de provisión**. Guarda qué empresa y qué administrador existen por cliente, y ejecuta las operaciones contra el Supabase self-hosted de la app usando la llave de servicio, que nunca sale del backend. La app de presupuestos no cambia su inicio de sesión: sigue autenticando contra su propio Supabase.

```
Command Center (staff)                     Servidor auditia
┌───────────────────────────┐              ┌──────────────────────────┐
│ AUT · Automatizaciones    │  HTTPS       │ Supabase (GoTrue + REST) │
│  crear empresa + admin    │─────────────▶│  admin API               │
│  reset / baja / borrado   │  llave de    │  rpc crear_empresa_...   │
│  suspender licencia       │  servicio    │  tablas empresas,        │
└───────────┬───────────────┘              │  empresa_miembros        │
            │ Resend                        └──────────────────────────┘
            ▼                                          ▲
   correo con enlace de acceso                         │ sesión del admin
                                          App presupuestos (navegador)
                                          pantalla Miembros (nivel 2)
```

## Hechos verificados (18-sep)

| Hecho | Evidencia |
|---|---|
| El portal envía correo con **Resend** (`backend/app/notifications/email.py`), plantillas en `templates/`, y recursos ya manda usuario y clave sin persistirla | lectura del código |
| Remitente configurado: `no-reply@auditconsulting.ec`; único dominio verificado en Resend: `auditconsulting.ec` | Render env + panel de Resend |
| Cuentas del portal ya soportan: reset con clave fijada o temporal (se muestra una vez), baja reversible, borrado con protección de "último administrador" y de "no borrarse a sí mismo" | `backend/app/auth/service.py`, `auth/router.py` |
| Patrón de pantalla a copiar: `RecursosCuentas` (vista REC) en `frontend/src/App.jsx:2109` | lectura |
| La app ya tiene `crear_empresa_completa`, `agregar_miembro`, `activar_mis_invitaciones`, `es_admin_empresa` y tabla `empresa_miembros` (email, role, departamento_id, estado, invitado_por) | migraciones y `src/lib/datos.ts` |
| Categorías del catálogo del portal: TRIBUTARIAS, NIIF, LABORALES, SOCIETARIAS, GERENCIALES, DESARROLLO — **falta AUTOMATIZACIONES** | `client_portal/tool_registry.py:234` |

## Estructura de archivos

**Repo `auditbrain-python-runner` (rama `feat/automatizaciones-presupuestos`)**
- Crear `backend/app/automatizaciones/__init__.py`
- Crear `backend/app/automatizaciones/models.py` — tabla `aut_cuentas`
- Crear `backend/app/automatizaciones/supabase_admin.py` — cliente HTTP contra el Supabase de la app (única pieza que conoce la llave de servicio)
- Crear `backend/app/automatizaciones/service.py` — reglas: alta atómica, reset, baja, borrado, suspensión
- Crear `backend/app/automatizaciones/router.py` — endpoints `/api/v1/staff/automatizaciones/*` (solo staff) y `/api/v1/app/miembros` (nivel 2, autenticado con el token de la app)
- Crear `backend/app/automatizaciones/schemas.py`
- Crear `backend/app/notifications/templates/automatizacion_acceso.html`
- Modificar `backend/app/notifications/email.py` — función `send_automatizacion_acceso`
- Modificar `backend/app/api/__init__.py` — incluir el router
- Modificar `backend/app/client_portal/tool_registry.py` — categoría `AUTOMATIZACIONES` y herramientas `PRESUPUESTOS_IA`, `PLANIFICACION_IA`
- Modificar `frontend/src/App.jsx` — vista `AUT · Automatizaciones`, calcada de `RecursosCuentas`
- Modificar `frontend/src/api.js` — llamadas nuevas
- Crear `backend/tests/test_automatizaciones.py`

**Servidor `auditia`**
- `.env` de Supabase: `DISABLE_SIGNUP=true`

**Repo `smart-budget-builder` (rama `produccion`)**
- Modificar `src/routes/auth.tsx` — quitar el registro público
- Modificar `src/routes/_authenticated/miembros.tsx` — el alta de miembro llama al portal (crea la cuenta y envía el correo) en vez de solo registrar la invitación

---

## Tarea 1: Categoría y herramientas en el catálogo

**Archivos:** Modificar `backend/app/client_portal/tool_registry.py`

- [ ] **Paso 1: prueba que falla**

```python
def test_categoria_automatizaciones_y_herramientas():
    from backend.app.client_portal.tool_registry import CATEGORIES, TOOLS
    assert any(c["id"] == "AUTOMATIZACIONES" for c in CATEGORIES)
    assert TOOLS["PRESUPUESTOS_IA"].category == "AUTOMATIZACIONES"
    assert TOOLS["PLANIFICACION_IA"].enabled is False
```

- [ ] **Paso 2: correr y ver el fallo**

Run: `pytest backend/tests/test_automatizaciones.py::test_categoria_automatizaciones_y_herramientas -q`
Expected: FAIL por `KeyError: 'PRESUPUESTOS_IA'`.

- [ ] **Paso 3: implementar** — agregar al final de `TOOLS`:

```python
    "PRESUPUESTOS_IA": ToolConfig(
        code="PRESUPUESTOS_IA",
        label="Presupuestos con IA",
        description=(
            "Elaboración inteligente del presupuesto empresarial: diagnóstico "
            "sectorial, matriz de requerimientos, supuestos trazables, estado "
            "de resultados, flujo de caja y escenarios."
        ),
        category="AUTOMATIZACIONES",
        slots={},
        processor=None,
        enabled=True,
    ),
    "PLANIFICACION_IA": ToolConfig(
        code="PLANIFICACION_IA",
        label="Planificación Estratégica con IA",
        description="Objetivos, iniciativas, responsables e indicadores conectados al presupuesto.",
        category="AUTOMATIZACIONES",
        slots={},
        processor=None,
        enabled=False,
    ),
```

y a `CATEGORIES`:

```python
    {
        "id": "AUTOMATIZACIONES",
        "label": "Automatizaciones",
        "description": "Herramientas con IA: presupuestos y planificación estratégica.",
    },
```

- [ ] **Paso 4: verificar** — `pytest backend/tests/test_automatizaciones.py -q` → 1 passed.
- [ ] **Paso 5: commit** — `feat(aut): categoría Automatizaciones y herramientas en el catálogo`

## Tarea 2: Tabla de cuentas de automatizaciones

**Archivos:** Crear `backend/app/automatizaciones/models.py`

- [ ] **Paso 1: prueba que falla** — crear la tabla en SQLite de test y comprobar columnas y unicidad `(client_id, herramienta)`.

```python
def test_aut_cuenta_unica_por_cliente_y_herramienta(db):
    from backend.app.automatizaciones.models import AutCuenta
    db.add(AutCuenta(client_id=1, herramienta="PRESUPUESTOS_IA", empresa_nombre="X",
                     admin_email="a@x.ec", admin_nombre="A", creado_por="op@firma.ec"))
    db.commit()
    db.add(AutCuenta(client_id=1, herramienta="PRESUPUESTOS_IA", empresa_nombre="Y",
                     admin_email="b@y.ec", admin_nombre="B", creado_por="op@firma.ec"))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Paso 2: correr y ver el fallo.**
- [ ] **Paso 3: implementar el modelo** con columnas: `id`, `client_id` (FK clients), `herramienta`, `empresa_nombre`, `empresa_id_app` (UUID de la app, nullable hasta el alta), `admin_email`, `admin_nombre`, `admin_user_id_app` (UUID), `estado` (`activa`/`suspendida`), `vigencia_hasta` (date, nullable), `creado_por`, `created_at`, `updated_at`, y `UniqueConstraint("client_id", "herramienta")`.
- [ ] **Paso 4: verificar** — pytest en verde.
- [ ] **Paso 5: commit** — `feat(aut): tabla aut_cuentas`

## Tarea 3: Cliente del Supabase de la app

**Archivos:** Crear `backend/app/automatizaciones/supabase_admin.py`

Única pieza que usa `PRESUPUESTOS_SUPABASE_URL` y `PRESUPUESTOS_SERVICE_ROLE_KEY` (variables nuevas en Render, `sync: false`). Funciones puras de transporte, sin reglas de negocio:

- `crear_usuario(email, nombre) -> dict` → `POST /auth/v1/admin/users` con `email_confirm=true`, sin contraseña.
- `enlace_acceso(email, redirect_to) -> str` → `POST /auth/v1/admin/generate_link` tipo `recovery`.
- `bloquear_usuario(user_id, bloquear: bool)` → `PUT /auth/v1/admin/users/{id}` con `ban_duration` (`"876000h"` o `"none"`).
- `borrar_usuario(user_id)` → `DELETE /auth/v1/admin/users/{id}`.
- `rpc(nombre, payload)` → `POST /rest/v1/rpc/{nombre}`.
- `consultar(tabla, params)` → `GET /rest/v1/{tabla}`.

- [ ] **Paso 1: pruebas con `responses`/`requests_mock`** verificando método, ruta, cabeceras (`apikey` y `Authorization`) y que **nunca** se registre la llave en logs.
- [ ] **Paso 2: correr y ver el fallo.**
- [ ] **Paso 3: implementar** con `requests`, timeout 20 s, 2 reintentos y error tipado `SupabaseAdminError` con el cuerpo truncado a 200 caracteres.
- [ ] **Paso 4: verificar** — pytest en verde.
- [ ] **Paso 5: commit** — `feat(aut): cliente admin del Supabase de presupuestos`

## Tarea 4: Reglas de negocio del alta y del ciclo de vida

**Archivos:** Crear `backend/app/automatizaciones/service.py`

Reglas a implementar y probar, calcadas de las cuentas del portal:

1. **Alta atómica:** crear usuario → crear empresa con `crear_empresa_completa` → marcar al usuario como `administrador` en `empresa_miembros` → guardar `aut_cuentas`. Si un paso falla, se deshace lo anterior (borrar usuario creado) y no queda registro a medias.
2. **Correo:** al terminar el alta se envía el enlace de acceso por Resend (Tarea 5). El enlace es de un solo uso y lo define el propio administrador.
3. **Restablecer clave:** genera un enlace nuevo y lo envía. La firma nunca ve ni fija la contraseña.
4. **Baja reversible:** bloquea al usuario en Supabase y marca `estado='suspendida'`; reactivar hace lo inverso.
5. **Borrado:** elimina el usuario administrador y la fila de `aut_cuentas`; **no borra la empresa ni su histórico** en la app.
6. **Protecciones:** no se puede dejar una empresa sin administrador activo, ni borrar la última cuenta activa de una empresa.
7. **Suspensión por licencia:** `vigencia_hasta` vencida ⇒ la cuenta cuenta como suspendida al listar, sin tocar los datos.

- [ ] **Paso 1: pruebas** (una por regla, con el cliente Supabase simulado), incluida la de reversa cuando falla la creación de la empresa.
- [ ] **Paso 2: correr y ver fallos.**
- [ ] **Paso 3: implementar.**
- [ ] **Paso 4: verificar** — pytest en verde.
- [ ] **Paso 5: commit** — `feat(aut): servicio de provisión de cuentas`

## Tarea 5: Correo de acceso

**Archivos:** Crear `backend/app/notifications/templates/automatizacion_acceso.html`; Modificar `backend/app/notifications/email.py`

- [ ] **Paso 1: prueba** de que `render_automatizacion_acceso` reemplaza `{{herramienta}}`, `{{empresa}}`, `{{enlace}}` y `{{contacto}}`, y que **no** contiene contraseñas.
- [ ] **Paso 2: correr y ver el fallo.**
- [ ] **Paso 3: implementar** la plantilla con la línea gráfica de `recurso_acceso.html` (azul `#0B1E36`, verde `#B7CE3B`, DM Sans) y la función `send_automatizacion_acceso(...)` que usa `send_email`.
- [ ] **Paso 4: verificar** — pytest en verde y revisión visual del HTML renderizado.
- [ ] **Paso 5: commit** — `feat(aut): correo de acceso a automatizaciones`

## Tarea 6: Endpoints del Command Center

**Archivos:** Crear `backend/app/automatizaciones/router.py`, `schemas.py`; Modificar `backend/app/api/__init__.py`

Endpoints, todos con `require_staff` salvo donde se indique:

| Método y ruta | Qué hace |
|---|---|
| `GET /staff/automatizaciones/cuentas` | Lista con cliente, herramienta, empresa, administrador, estado y vigencia |
| `POST /staff/automatizaciones/cuentas` | Alta (Tarea 4, regla 1) |
| `POST /staff/automatizaciones/cuentas/{id}/reset` | Reenvía enlace de acceso |
| `POST /staff/automatizaciones/cuentas/{id}/suspender` y `/reactivar` | Baja reversible |
| `DELETE /staff/automatizaciones/cuentas/{id}` | Borrado, solo admin |

- [ ] **Paso 1: pruebas de API** con cliente de pruebas: 403 para rol `client`, 200 para staff, 403 para borrar siendo `user` no admin.
- [ ] **Paso 2: correr y ver fallos.**
- [ ] **Paso 3: implementar** y registrar el router.
- [ ] **Paso 4: verificar** — `pytest backend/tests/test_automatizaciones.py -q` en verde y la suite existente sin regresiones.
- [ ] **Paso 5: commit** — `feat(aut): endpoints de cuentas de automatizaciones`

## Tarea 7: Pantalla AUT en el Command Center

**Archivos:** Modificar `frontend/src/App.jsx`, `frontend/src/api.js`

- [ ] **Paso 1:** copiar la estructura de `RecursosCuentas` (`App.jsx:2109`) a un componente `AutomatizacionesCuentas`, con columnas: cliente, herramienta, empresa, administrador, estado, vigencia y acciones.
- [ ] **Paso 2:** acciones con confirmación: **Restablecer acceso**, **Suspender/Reactivar**, **Borrar** (solo admin, con confirmación escrita como en cuentas).
- [ ] **Paso 3:** formulario de alta: cliente (selector de `clients`), herramienta, nombre de la empresa, sector, nombre y correo del administrador, vigencia opcional.
- [ ] **Paso 4:** registrar la vista en el menú como `AUT · Automatizaciones` y renombrar el módulo existente `Automation Core`.
- [ ] **Paso 5: verificar** — `npm run build` sin errores y prueba manual contra el backend local: alta, listado, reset, suspensión y borrado.
- [ ] **Paso 6: commit** — `feat(aut): pantalla de cuentas de automatizaciones en el Command Center`

## Tarea 8: Cerrar el registro público en la app

**Archivos:** servidor `auditia`; `smart-budget-builder/src/routes/auth.tsx`

- [ ] **Paso 1:** en `/opt/supabase-budget/.env` poner `DISABLE_SIGNUP=true` y `docker compose up -d auth`.
- [ ] **Paso 2: verificar** — `curl -s -o /dev/null -w "%{http_code}" $URL/auth/v1/signup -H "apikey: $ANON" -d '{"email":"x@y.ec","password":"..."}'` → **422/403**, no 200.
- [ ] **Paso 3:** en `auth.tsx` quitar el enlace "Regístrate" y el modo registro; dejar un texto: "El acceso lo crea AuditConsulting. Escríbenos si necesitas una cuenta."
- [ ] **Paso 4: verificar** — `npm run build`, y en el navegador que no exista forma de registrarse.
- [ ] **Paso 5: commit** — `feat(track-a): cierra el registro público; las cuentas las crea la firma`

## Tarea 9: Nivel 2 — el administrador crea a su personal

**Archivos:** `backend/app/automatizaciones/router.py` (endpoint `/app/miembros`), `smart-budget-builder/src/routes/_authenticated/miembros.tsx`

El navegador no puede llevar la llave de servicio, así que el alta de personal pasa por el portal:

1. La app envía el token de sesión del administrador al endpoint `/api/v1/app/miembros`.
2. El portal valida ese token contra el Supabase de la app (`GET /auth/v1/user`) y comprueba con `es_admin_empresa` que quien pide es administrador **de esa** empresa.
3. Crea la cuenta, la agrega con `agregar_miembro` con su rol y departamento, y envía el correo de acceso.

- [ ] **Paso 1: pruebas**: token inválido → 401; administrador de otra empresa → 403; alta correcta → 201 y un solo correo enviado.
- [ ] **Paso 2: correr y ver fallos.**
- [ ] **Paso 3: implementar** endpoint y ajustar `miembros.tsx` para usarlo.
- [ ] **Paso 4: verificar** — prueba de punta a punta con dos empresas distintas, comprobando el aislamiento.
- [ ] **Paso 5: commit** — `feat(aut): el administrador de la empresa crea cuentas de su personal`

## Tarea 10: Publicar

- [ ] **Paso 1:** variables nuevas en Render (`PRESUPUESTOS_SUPABASE_URL`, `PRESUPUESTOS_SERVICE_ROLE_KEY`). **La llave la pega el usuario.**
- [ ] **Paso 2:** PR a `main` del portal, revisión de código por subagente y despliegue.
- [ ] **Paso 3: prueba real:** crear desde el Command Center una empresa de prueba con un correo del usuario, recibir el correo, definir la clave, entrar, y desde la app invitar a un segundo usuario.
- [ ] **Paso 4:** publicar la landing de automatizaciones (repo `audit-ia-automatizaciones`, Render y CNAME).

## Fuera de alcance

Inicio de sesión único entre el portal y la app, facturación y cobro de licencias, y la herramienta de Planificación Estratégica, que aquí solo se registra como catálogo deshabilitado.

## Riesgos declarados

| Riesgo | Mitigación |
|---|---|
| La llave de servicio del Supabase de la app queda en el backend del portal | Solo en `supabase_admin.py`, nunca en logs ni respuestas; rotable desde el servidor |
| Si el servidor `auditia` está caído, el alta falla | El error se muestra claro y la operación no deja registros a medias |
| El correo depende de Resend y del dominio `auditconsulting.ec` | Ya está verificado y en uso por recursos |
| Dos sistemas de cuentas conviviendo (portal y app) | Aceptado: el Command Center es la única puerta de alta. El inicio de sesión único queda para después |
