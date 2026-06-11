# Diseño — Landing de inscripción a la charla (Anexos Tributarios)

- **Fecha:** 2026-06-11
- **Autor:** Jorge V. (Audit Consulting Group) + AuditBrain
- **Estado:** Aprobado para planificación
- **Repo:** `auditbrain-python-runner`

---

## 1. Objetivo

Construir una **landing pública de inscripción** para la próxima charla gratuita
de Audit Consulting Group (*"Elaboración de Anexos Tributarios con Herramienta de
Automatización"*), alojada en la sección de clientes
(`frontend-client` / `auditbrain-clientes.onrender.com`). Al inscribirse, el
lead recibe **automáticamente** la confirmación de su reserva por **email** y por
**WhatsApp**, y Audit Consulting recibe un email por cada inscripción nueva.

## 2. Contexto del codebase (lo que ya existe y se reutiliza)

| Pieza existente | Cómo se reutiliza |
|---|---|
| `frontend-client` (React + `react-router-dom` v6) | Se agrega una ruta pública `/charla`. Ya tiene `src/landing/` como referencia de estilo. |
| `public/assets/logo-auditconsulting-group.png` | Logo de marca en la landing. |
| `backend/app/notifications/email.py` (Resend + retry) | Envío de email de confirmación y aviso interno. Patrón `send_email()` + render de plantilla HTML. |
| `backend/app/notifications/templates/` | Carpeta donde vive la plantilla nueva `charla_confirmacion.html`. |
| `backend/app/client_portal/rate_limit.py` (`check_and_record`) | Rate-limit del endpoint público de inscripción. |
| `backend/app/db/session.py` (`Base`, `init_db`, `get_db`) | Modelo nuevo se registra en `init_db()` con `Base.metadata.create_all`. |
| `backend/app/api/__init__.py` (`api_router`) | Se monta el router nuevo con prefijo `/api/v1`. |
| Patrón `BackgroundTasks` de `client_portal/router.py` | Envío de notificaciones fuera del request. |

**Decisión clave:** la landing es **pública** (sin login). No reutiliza el flujo
`require_client_with_device`; los inscritos son prospectos, no clientes con cuenta.

## 3. Alcance

### Dentro
- Ruta pública `/charla` en `frontend-client` con la landing + formulario.
- Endpoint público de inscripción + persistencia en Postgres.
- Email de confirmación al inscrito (Resend).
- Email de aviso interno a Audit Consulting por cada inscripción.
- WhatsApp de confirmación al inscrito (Cloud API), con degradación elegante.
- Endpoint admin para listar inscritos.

### Fuera (YAGNI)
- Pasarela de pago (la charla es gratuita).
- Recordatorios programados pre-evento (posible fase 2).
- Panel visual admin dedicado (por ahora basta el endpoint `GET` + export).
- Multi-evento con CMS (se modela 1 evento configurable; el slug queda
  parametrizable para futuros eventos sin rediseño).

## 4. Arquitectura

```
[Navegador]
   │  GET /charla
   ▼
frontend-client (React Router)
   src/charla/CharlaLanding.jsx ── src/charla/CharlaForm.jsx
   │  POST /api/v1/events/charla-anexos-2026-06/registrations
   ▼
backend/app/events/router.py  (público, rate-limited)
   │  1. valida payload (Pydantic)
   │  2. persiste EventRegistration (Postgres)
   │  3. BackgroundTask → notificaciones
   ▼
backend/app/events/notify.py
   ├── email.send_email(...)  → confirmación al inscrito   (Resend)
   ├── email.send_email(...)  → aviso interno a la firma    (Resend)
   └── whatsapp.send_template_message(...) → confirmación   (WhatsApp Cloud API)
```

## 5. Modelo de datos

`backend/app/events/models.py` → tabla `event_registrations`:

| Columna | Tipo | Notas |
|---|---|---|
| `id` | Integer PK | |
| `event_slug` | VARCHAR(64), index | ej. `charla-anexos-2026-06` |
| `nombre` | VARCHAR(160) | nombre y apellido |
| `email` | VARCHAR(320), index | validado |
| `telefono_e164` | VARCHAR(20) | normalizado a E.164 (ej. `+593987654321`) |
| `documento` | VARCHAR(20) | cédula (10) o RUC (13) |
| `empresa` | VARCHAR(200) | |
| `estado` | VARCHAR(16) | `registrado` / `cancelado` (default `registrado`) |
| `email_enviado` | Boolean default False | confirmación al inscrito |
| `whatsapp_enviado` | Boolean default False | |
| `aviso_interno_enviado` | Boolean default False | |
| `created_at` | TIMESTAMP default now (UTC naive, como el resto del repo) | |

- Registrar el módulo en `init_db()` (`from backend.app.events import models`).
- **Idempotencia de inscripción:** índice único compuesto
  `(event_slug, email)`. Si el mismo email se reinscribe al mismo evento → se
  trata como "ya inscrito" (200 idempotente, reenvía confirmación), no error 500.

## 6. Configuración del evento

`backend/app/events/catalog.py` — un dict de eventos (arranca con uno):

```python
EVENTS = {
    "charla-anexos-2026-06": EventInfo(
        slug="charla-anexos-2026-06",
        titulo="Elaboración de Anexos Tributarios con Herramienta de Automatización",
        subtitulo="Charla gratuita en Zoom",
        fecha_texto="Jueves 18 de junio",
        hora_texto="19h00 (Ecuador)",
        duracion_texto="2 horas",
        modalidad="Zoom",
        zoom_url=os.getenv("CHARLA_ZOOM_URL", ""),   # configurable
        beneficios=[
            "Automatiza tus anexos tributarios",
            "Descarga inteligente de información del SRI",
            "Validaciones automáticas y control de inconsistencias",
            "Reduce tiempos y minimiza errores",
            "Casos prácticos para empresas y profesionales",
        ],
        activo=True,
    ),
}
```

El `zoom_url` se inyecta como env var y se incluye en el email de confirmación.

## 7. Contratos de API (`backend/app/events/`)

### `POST /api/v1/events/{slug}/registrations` — público
Request:
```json
{
  "nombre": "María Pérez",
  "email": "maria@empresa.ec",
  "telefono": "0987654321",
  "telefono_pais": "+593",
  "documento": "1791240154001",
  "empresa": "Empresa S.A."
}
```
Respuesta `201`:
```json
{ "ok": true, "estado": "registrado", "ya_inscrito": false,
  "mensaje": "Inscripción confirmada. Te enviamos los detalles por email y WhatsApp." }
```
Errores: `404` slug inexistente/inactivo · `422` validación · `429` rate-limit.

### `GET /api/v1/events/{slug}/registrations` — admin (`require_admin`)
Lista de inscritos (para que la firma vea/exporte). Soporta `?limit=` y orden
desc por `created_at`.

## 8. Validaciones (Pydantic, módulo `schemas.py`)

- `nombre`: 3–160 chars, no vacío.
- `email`: formato válido (Pydantic `EmailStr` — agregar `email-validator` si falta).
- `telefono` + `telefono_pais`: se normaliza a **E.164**. Default país `+593`
  (Ecuador). Se quitan espacios/guiones; si el número local empieza con `0`, se
  elimina ese `0` al anteponer el código de país. Resultado debe matchear
  `^\+\d{8,15}$`.
- `documento`: solo dígitos; longitud **10 (cédula)** o **13 (RUC)**. (Validación
  de formato; no se consulta al SRI en esta fase.)
- `empresa`: 1–200 chars.

## 9. Notificaciones

### 9.1 Email de confirmación al inscrito
- Plantilla `templates/charla_confirmacion.html` (mismo estilo que
  `job_ready.html`: header azul `#0a2540`, marca, botón verde de acción).
- Variables: `{{nombre}}`, `{{titulo}}`, `{{fecha}}`, `{{hora}}`, `{{modalidad}}`,
  `{{zoom_url}}`.
- Asunto: `Confirmación de tu reserva — {{titulo}}`.
- Función `send_charla_confirmacion(...)` en `notifications/email.py`.

### 9.2 Email de aviso interno
- A `EVENTS_NOTIFY_EMAIL` (env var; default casilla de Audit Consulting).
- Plantilla simple con los datos del inscrito.

### 9.3 WhatsApp de confirmación — `notifications/whatsapp.py` (nuevo)
- WhatsApp **Cloud API**: `POST https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages`.
- **Mensaje de plantilla aprobada** (obligatorio: el lead no inició la
  conversación, no hay ventana de 24h). Tipo `template`, idioma `es`.
- Parámetros del body de plantilla: nombre, fecha, hora (según la plantilla que
  se apruebe en Meta).
- Env vars: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE_NAME`,
  `WHATSAPP_TEMPLATE_LANG` (default `es`).
- **Degradación elegante** (igual que email sin `RESEND_API_KEY`): si falta
  config → loguea warning, `whatsapp_enviado=False`, **no** rompe la inscripción.
- Retry x3 con backoff (mismo patrón que `send_email`).

## 10. Manejo de errores y resiliencia

- La inscripción se **persiste primero**; las notificaciones van en
  `BackgroundTask`. Si una notificación falla, la inscripción ya quedó guardada
  y los flags `*_enviado` reflejan qué se envió (auditable desde el `GET` admin).
- Ninguna falla de Resend/WhatsApp devuelve 5xx al usuario: la landing siempre
  confirma "te inscribimos" si la fila se guardó.
- Todas las funciones de notificación son defensivas (try/except + log), nunca
  propagan excepción al background runner.

## 11. Seguridad

- Endpoint público con **rate-limit** por IP (reusar `check_and_record`, ej.
  10 inscripciones / 10 min / IP) para frenar spam de formularios.
- CORS: agregar el origen del portal cliente a `CORS_ALLOW_ORIGINS` si aún no
  está (ya contemplado en `app.py`).
- El `GET` de inscritos exige `require_admin` (no se expone PII públicamente).
- Sanitización de inputs antes de renderizarlos en HTML de email (escapar para
  evitar inyección en el template).

## 12. Frontend — `frontend-client/src/charla/`

- `CharlaLanding.jsx`: hero con el contenido del flyer (título, "Charla gratuita
  en Zoom", datos del evento, 5 beneficios) + `<CharlaForm />`. Paleta:
  fondo `#0a2540`, acento verde lima, logo de marca. Responsive (mobile-first;
  el flyer es vertical).
- `CharlaForm.jsx`: campos nombre, email, celular (con selector de país, default
  `+593`), documento (cédula/RUC), empresa. Validación en cliente + manejo de
  estados (enviando / éxito / error). En éxito muestra pantalla de
  "¡Reserva confirmada!" con los datos del evento.
- `charlaApi.js`: `POST` al endpoint (sin token; público).
- Ruta nueva en `App.jsx`: `<Route path="/charla" element={<CharlaLanding />} />`.
- Reusar estilo de `landing/` y `auth/login.css` donde aplique; CSS propio
  `charla.css` para lo específico.

## 13. Variables de entorno nuevas (Render)

| Var | Requerida | Default | Uso |
|---|---|---|---|
| `CHARLA_ZOOM_URL` | No | `""` | Link de Zoom en el email de confirmación. |
| `EVENTS_NOTIFY_EMAIL` | No | casilla firma | Destino del aviso interno. |
| `WHATSAPP_TOKEN` | Sí (para WA real) | — | Token Cloud API de Meta. |
| `WHATSAPP_PHONE_NUMBER_ID` | Sí (para WA real) | — | ID del número WhatsApp Business. |
| `WHATSAPP_TEMPLATE_NAME` | Sí (para WA real) | — | Nombre de la plantilla aprobada. |
| `WHATSAPP_TEMPLATE_LANG` | No | `es` | Idioma de la plantilla. |
| `RESEND_API_KEY` | Sí (para email real) | — | Ya existente; pendiente de configurar. |

## 14. Pasos manuales fuera del código (responsabilidad del cliente)

1. **WhatsApp Cloud API:** crear/usar cuenta Meta Business, verificar número
   WhatsApp Business, crear y **obtener aprobación de Meta** para la plantilla de
   confirmación (categoría *utility*). Cargar las 3 env vars `WHATSAPP_*`.
2. **Resend:** generar `RESEND_API_KEY` y verificar dominio remitente.
3. **Zoom:** generar el link de la reunión y cargarlo en `CHARLA_ZOOM_URL`.

> Hasta que existan estas credenciales, el sistema funciona en modo degradado:
> la inscripción se guarda y (si Resend está configurado) se envía email; el
> WhatsApp queda marcado como no enviado sin romper nada.

## 15. Testing (obligatorio antes de "listo" — regla suprema CLAUDE.md)

- `tests/test_events_registration.py`:
  - inscripción válida → `201`, fila creada, flags coherentes.
  - reinscripción mismo email → idempotente (no duplica, no 500).
  - validación: email inválido, documento ≠ 10/13 dígitos, teléfono normalizado.
  - normalización E.164 (`0987654321` + `+593` → `+593987654321`).
  - slug inexistente → `404`.
  - rate-limit → `429` al superar el umbral.
  - `GET` admin exige rol admin (`401/403` sin admin).
- `tests/test_notifications_whatsapp.py`:
  - sin env vars → degradación elegante (retorna `None`, no excepción).
  - con mock de `requests.post` → arma el body de plantilla correcto.
- Notificaciones email: mock de `requests.post` a Resend (sin envíos reales).
- **Verificación empírica final:** correr `pytest` y confirmar verde; levantar la
  landing localmente (`npm run dev` en `frontend-client`), inscribir un caso de
  prueba y verificar que la fila se persiste y los flags reflejan el resultado.

## 16. Criterios de aceptación

1. `GET /charla` renderiza la landing con el contenido del flyer y el formulario.
2. Una inscripción válida persiste en `event_registrations` y devuelve `201`.
3. Con Resend configurado, el inscrito recibe email de confirmación y la firma
   recibe el aviso interno.
4. Con `WHATSAPP_*` configurado + plantilla aprobada, el inscrito recibe el
   WhatsApp; sin configurar, la inscripción no falla.
5. El endpoint admin lista los inscritos solo para rol admin.
6. `pytest` en verde para los tests nuevos; sin romper los existentes.

## 17. Archivos a crear / modificar

**Crear:**
- `backend/app/events/__init__.py`
- `backend/app/events/models.py`
- `backend/app/events/schemas.py`
- `backend/app/events/catalog.py`
- `backend/app/events/service.py`
- `backend/app/events/notify.py`
- `backend/app/events/router.py`
- `backend/app/notifications/whatsapp.py`
- `backend/app/notifications/templates/charla_confirmacion.html`
- `backend/app/notifications/templates/charla_aviso_interno.html`
- `frontend-client/src/charla/CharlaLanding.jsx`
- `frontend-client/src/charla/CharlaForm.jsx`
- `frontend-client/src/charla/charlaApi.js`
- `frontend-client/src/charla/charla.css`
- `tests/test_events_registration.py`
- `tests/test_notifications_whatsapp.py`

**Modificar:**
- `backend/app/api/__init__.py` (montar `events_router`).
- `backend/app/db/session.py` (`init_db` importa `events.models`).
- `backend/app/notifications/email.py` (helpers `send_charla_*`).
- `frontend-client/src/App.jsx` (ruta `/charla`).
- `requirements.txt` (si falta `email-validator` para `EmailStr`).
