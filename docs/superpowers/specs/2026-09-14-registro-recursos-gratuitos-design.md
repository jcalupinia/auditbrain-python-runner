# Registro de recursos gratuitos (acceso por correo) — Diseño

Fecha: 2026-09-14 · Estado: aprobado por el usuario en conversación

## Objetivo

El video "Auditoría Externa 2026" ofrece la **Calculadora del Anticipo IR 2026** gratis
("registre su correo, acepte la política de protección de datos y reciba su clave").
Hoy la calculadora (`recursos.audit-ia.ec/anticipo-ir-2026/`) está abierta. Se necesita
que, para usarla, la persona deje **nombre, empresa y correo**, acepte la política de
protección de datos (LOPDP) y reciba **por correo** el enlace de acceso. Así la firma
captura contactos con correo verificado.

Decisiones tomadas con el usuario:

- El acceso llega **por correo** (no se muestra en pantalla al instante).
- Los registros se guardan en el **portal AUDIT-IA** (backend FastAPI en Render,
  Postgres, Resend ya integrado) y se ven en la consola.
- "Su usuario es su correo". **No hay clave que recordar**: el correo trae un enlace
  firmado; al abrirlo, la calculadora queda habilitada en ese dispositivo.

Fuera de alcance: cuentas reales del portal para los inscritos, aviso interno por correo
por cada registro (se ve en la consola; se agrega después si se pide), captcha,
analítica de uso de la calculadora.

## Experiencia del usuario

1. En `recursos.audit-ia.ec` la tarjeta de la calculadora dice **"Quiero la calculadora
   gratis"** y lleva a `anticipo-ir-2026/`.
2. Sin acceso válido, la calculadora se ve de fondo (atenuada, sin interacción) con un
   recuadro encima:
   - Campos: **Nombre** (3–160), **Empresa** (1–200), **Correo** (válido).
   - Casilla obligatoria: *"Acepto la [política de protección de datos](../politica-datos/)
     de AuditConsulting Group"*.
   - Campo trampa oculto (`website`) contra bots.
   - Botón **Enviar** (se deshabilita y muestra "Enviando…" mientras espera).
   - Enlace **"¿Ya se registró? Reenviar mi acceso"** → pide solo el correo.
3. Tras enviar: *"Listo, {nombre}. Su usuario es su correo. Le enviamos el enlace de
   acceso a {correo}. Revise también la bandeja de correo no deseado."*
4. Correo desde `no-reply@auditconsulting.ec`, asunto *"Su acceso a la Calculadora del
   Anticipo IR 2026"*: saludo, "Usuario: {correo}", botón **Abrir mi calculadora**,
   contacto (jcalupinia@auditconsulting.ec · WhatsApp 0990 609 811), texto LOPDP.
5. El botón abre `…/anticipo-ir-2026/?acceso=<token>`. La página valida el token con el
   backend, guarda el acceso en `localStorage`, quita `?acceso=` de la URL y oculta el
   recuadro. En visitas siguientes, en ese dispositivo, entra directo.
6. Otro dispositivo: "¿Ya se registró?" → se reenvía el enlace. La respuesta es siempre
   la misma ("Si el correo está registrado, le reenviamos el acceso") para no revelar
   qué correos existen.

Mensajes de error visibles: datos inválidos (texto del campo), demasiados intentos
(429: "Demasiados intentos desde esta red. Intente en unos minutos."), servidor sin
respuesta ("No pudimos conectar. Intente de nuevo."), enlace inválido o vencido
("Su enlace no es válido o venció. Solicite uno nuevo." + formulario de reenvío).

## Arquitectura

Dos repos:

- **Portal** `jcalupinia/auditbrain-python-runner` — módulo nuevo `backend/app/recursos/`
  (copia reducida del patrón `backend/app/events/`) + pestaña en la consola.
- **Mini-sitio** `jcalupinia/audit-ia-recursos` — recuadro en la calculadora, texto de la
  tarjeta, página de política de datos.

### Backend: `backend/app/recursos/`

| Archivo | Responsabilidad |
|---|---|
| `catalog.py` | Lista blanca de recursos: `anticipo-ir-2026` → título y URL pública. Slug desconocido = 404. |
| `models.py` | Tabla `recurso_leads`. |
| `schemas.py` | `LeadCreate`, `ReenvioIn`, `LeadResponse`, `AccesoOut`, `LeadOut`. |
| `tokens.py` | Crear/verificar el token del enlace. |
| `service.py` | Alta idempotente, búsqueda por correo, marca de verificación. |
| `notify.py` | Envío del correo en `BackgroundTasks` y marca `email_enviado`. |
| `router.py` | Endpoints. |

Registro: una línea en `backend/app/api/__init__.py` (`include_router`) y una en
`init_db()` (`from backend.app.recursos import models  # noqa: F401`). Sin Alembic:
tabla nueva vía `create_all`.

**Modelo `RecursoLead`** (`recurso_leads`), `UniqueConstraint(recurso_slug, email)`:

| Columna | Tipo | Nota |
|---|---|---|
| id | int PK | |
| recurso_slug | str(64), index | |
| nombre | str(160) | |
| empresa | str(200) | |
| email | str(320), index | normalizado a minúsculas y sin espacios |
| consentimiento_at | datetime | momento en que aceptó la política |
| consentimiento_version | str(16) | `"v1"` = texto de `politica-datos/` vigente |
| ip | str(64) | primer hop de X-Forwarded-For |
| email_enviado | bool | resultado del último envío |
| verificado_at | datetime, null | primera vez que abrió el enlace = correo real |
| created_at | datetime | |

**Token del enlace:** JWT HS256 con `AUDITBRAIN_JWT_SECRET` (PyJWT ya instalado),
claims `sub=<lead id>`, `rs=<slug>`, `aud="recurso-acceso"`, `exp=30 días`. Se firma y
verifica con `jwt.encode/decode` directo (no `create_access_token`, que fija 60 min y
busca el `sub` en usuarios). `decode_token` del staff no pasa `audience`, así que PyJWT
rechaza estos tokens ahí: un token de recurso **nunca** sirve para la consola. Hay una
prueba que lo asegura.

**Endpoints** (prefijo `/api/v1/recursos`):

| Método y ruta | Auth | Comportamiento |
|---|---|---|
| `POST /{slug}/registros` | pública | Valida, límite 10/600 s por IP (`check_and_record("recurso-reg:{ip}")`), honeypot lleno → 201 falso sin guardar. Alta idempotente: si el correo ya existe para ese recurso, conserva el registro, actualiza nombre/empresa/consentimiento y reenvía. Correo en background. 201 `{ok, ya_registrado, mensaje}`. |
| `POST /{slug}/reenviar` | pública | Body `{email}`. Mismo límite (clave compartida). Si existe, reenvía en background. Siempre 200 con mensaje genérico. |
| `GET /{slug}/acceso?token=` | pública | Verifica firma, `aud`, vencimiento y que `rs` = slug y el lead exista. Marca `verificado_at` si es la primera vez. 200 `{ok: true, nombre}`; inválido/vencido → 401. |
| `GET /registros?slug=&limit=` | `require_staff` | Lista más recientes primero (máx. 1000). |

CORS: se reutiliza `CORS_ALLOW_ORIGINS` (se agrega `https://recursos.audit-ia.ec` en
Render). Plantilla de correo `notifications/templates/recurso_acceso.html` con
placeholders escapados (`html.escape`), igual que `charla_confirmacion.html`; función
`send_recurso_acceso(...)` en `notifications/email.py`. El enlace se arma con la URL del
catálogo + `?acceso=<token>`.

### Consola: pestaña "REC · Registros de recursos"

En `frontend/src/App.jsx`: entrada `{ id: "recursos", code: "REC", label: "Recursos",
staff: true }` en `OPS`, `case "recursos"` en `render()`, y componente `RecursosLeads()`
copiado de `Inscripciones()` (tabla: fecha, nombre, empresa, correo, recurso,
verificado sí/no, correo enviado sí/no; buscador; descarga CSV). En `frontend/src/api.js`:
`listRecursoLeads(slug, limit)` con `apiFetch` + `authHeaders()`.

### Mini-sitio `audit-ia-recursos`

- `public/anticipo-ir-2026/index.html`: bloque `<div id="gate">` (recuadro + estados:
  formulario, reenvío, confirmación, error) y un `<script>` pequeño al final. Constante
  `API = "https://auditbrain-python-runner.onrender.com/api/v1/recursos/anticipo-ir-2026"`.
  Al cargar: si hay `?acceso=` → valida → guarda `localStorage["acg_acceso_anticipo-ir-2026"]`
  → `history.replaceState` sin el parámetro; si ya hay acceso guardado → no muestra el
  recuadro; si no → muestra el recuadro y hace `fetch(".../healthz")` sin esperar, para
  despertar el servidor mientras la persona escribe. `localStorage` en `try/catch`: si
  falla, el acceso vale solo en esa visita. Estilo con la identidad de la página
  (navy/lime, DM Sans), responsive a 400 px, foco en el primer campo, `Esc` no cierra.
- `public/index.html`: la tarjeta dice "Quiero la calculadora gratis".
- `public/politica-datos/index.html`: política de protección de datos v1 (responsable
  AuditConsulting Group, datos tratados — nombre, empresa, correo —, finalidad: dar
  acceso al recurso y enviar información de la firma, base: consentimiento, derechos de
  acceso/rectificación/eliminación/oposición escribiendo a jcalupinia@auditconsulting.ec,
  conservación mientras no se solicite la eliminación).

## Límites conocidos

- El bloqueo es del lado del navegador: alguien técnico puede saltarlo. Aceptado: es un
  recurso gratuito y el objetivo es capturar contactos verificados.
- Límite de envíos en memoria de una sola instancia (igual que las charlas); se reinicia
  con cada despliegue.
- Plan gratuito de Render: el primer envío tras inactividad puede tardar 30–50 s;
  mitigado con el ping a `/healthz` al abrir la página y un `timeout` de 60 s en el
  `fetch` con mensaje "Conectando con el servidor…".

## Tareas del usuario (requieren su cuenta de Render)

1. Agregar `https://recursos.audit-ia.ec` a `CORS_ALLOW_ORIGINS` del servicio backend.
2. Confirmar que `RESEND_API_KEY` está cargada y que el dominio `auditconsulting.ec` está
   verificado en Resend (si no, el correo no sale y `email_enviado` queda en falso).

## Orden de despliegue

1. PR del portal → merge a `main` → Render despliega backend y consola.
2. Usuario configura CORS (y verifica Resend).
3. Push del mini-sitio (recuadro activo). Antes de esto la calculadora sigue abierta.

## Pruebas

- `tests/test_recursos_router.py` (patrón `test_events_router.py`, notificación
  parcheada, límite reiniciado por prueba): 201 alta; alta repetida = 201 con
  `ya_registrado` y un solo registro; 422 sin consentimiento / correo inválido / nombre
  corto; honeypot → 201 sin registro; slug desconocido → 404; 429 tras 11 envíos;
  reenviar con correo inexistente → 200 genérico sin envío; acceso con token válido →
  200 y `verificado_at`; token alterado, vencido, de otro slug → 401; token de recurso
  contra un endpoint de staff → 401; listado sin token → 401, con staff → 200.
- `tests/test_notifications_recurso_email.py`: la plantilla escapa HTML e incluye el
  enlace y el usuario.
- E2E local (backend `uvicorn app:app` + mini-sitio servido local con CORS local):
  llenar el formulario, capturar el enlace del correo (Resend parcheado → log), abrirlo,
  ver la calculadora desbloqueada y el registro `verificado` en la pestaña REC.
