# AuditBrain — Preview Environments en Render

> Documento de instrucciones para Claude Code. Versión: 2026-10-08.
> Repo: `jcalupinia/auditbrain-python-runner` · Blueprint de Render: `auditbrain-python-runner-bp` (rama `main`).

---

## 0. Léeme primero (resumen para Claude)

**Objetivo único:** que cualquier desarrollador (X, Y, Z), o tú mismo cuando un usuario te pida un cambio, pueda **probar ese cambio en un entorno aislado** (frontend + backend + base de datos propios) **antes** de que llegue a `main` o a producción.

**Reglas de oro (no negociables):**

1. **Nunca toques producción.** Nada de cambiar planes, disco, dominios, base de datos de producción, ni variables de producción.
2. **Nunca hagas push a `main`.** Todo va por rama + Pull Request.
3. **Nunca escribas secretos** (claves, tokens, contraseñas, JSON de credenciales) en `render.yaml`, en commits, en logs ni en tus respuestas. Si necesitas verificar que una variable existe, comprueba su nombre, no imprimas su valor.
4. **No crees otro Blueprint.** El existente ya administra los cuatro servicios (ver sección 3). Dos Blueprints sobre el mismo recurso rompen la sincronización.
5. **Mínimo cambio.** El propósito es poder probar, no rediseñar la infraestructura. Si dudas entre hacer más o menos, haz menos y pregunta.
6. **Las fases tienen puertas de aprobación.** No pases a la siguiente fase sin que el humano lo confirme por escrito.

**Qué debes hacer ahora:** ejecutar **solo la Fase 0 (diagnóstico, solo lectura)** y reportar en el chat. No edites ningún archivo hasta recibir aprobación.

---

## 1. Contexto

AuditBrain es una aplicación web con frontend, backend y PostgreSQL, desplegada en Render. Antes, una sola persona trabajaba directamente sobre la Lenovo principal. Ahora tres desarrolladores (X, Y y Z) trabajan simultáneamente con Claude, cada uno desde su laptop.

### 1.1 Acceso y carpetas

```text
Laptop del desarrollador
   ↓ Tailscale
SSH hacia la Lenovo principal
   ↓
VS Code Remote-SSH
   ↓
Carpeta independiente del proyecto
   ↓
Claude Code → Git/GitHub → Pull Request → Render Preview → Pruebas → Review → Merge a main → Producción
```

Cada desarrollador tiene su propio clon del repo (no comparten carpeta):

```text
C:\Proyectos\
├── usuario-x\auditbrain\
├── usuario-y\auditbrain\
└── usuario-z\auditbrain\
```

Claude Code usa la **misma cuenta compartida** en la Lenovo. Esto significa que el límite de uso se comparte entre todos: evita tareas pesadas innecesarias.

### 1.2 Git y GitHub

- `main` = producción. Está protegida: exige Pull Request y status checks (ver sección 13 sobre los checks).
- **1 tarea = 1 rama = 1 Pull Request = 1 Preview Environment.**
- Las ramas representan **tareas**, no personas. Ejemplos: `feat/exportacion-reportes`, `fix/error-sri`. No se usan ramas permanentes por persona.

---

## 2. Qué se quiere lograr

```text
PR #101 (feat/exportacion-reportes)         PR #102 (feat/mejora-login)
   └── Preview #101                            └── Preview #102
        ├── Frontend #101                           ├── Frontend #102
        ├── Clientes #101                           ├── Clientes #102
        ├── Backend  #101                           ├── Backend  #102
        └── DB       #101                           └── DB       #102
```

Lo que **no** se quiere:

```text
Frontend Preview → Backend de PRODUCCIÓN      ✗
Backend  Preview → DB de PRODUCCIÓN           ✗
```

Los previews deben poder existir **a la vez**, actualizarse con cada push al PR y eliminarse cuando el PR se cierre o se mergee.

---

## 3. Estado actual

### 3.1 Servicios que pertenecen a AuditBrain

| Servicio | Tipo | Notas |
|---|---|---|
| `auditbrain-python-runner` | Web (Docker) | Backend/API FastAPI. Plan `standard`. Disco persistente `auditbrain-storage` (1 GB en `/var/data`). Health check `/healthz`. |
| `auditbrain-frontend` | Static | Consola principal. `rootDir: frontend`. Dominio propio `consola.audit-ia.ec`. |
| `auditbrain-clientes` | Static | Portal de clientes. `rootDir: frontend-client` (depende de `frontend-shared`). Dominio propio `clientes.audit-ia.ec`. |
| `auditbrain-db` | PostgreSQL 18 | Plan `basic-1gb` (de pago). |

**Confirmado en el dashboard:** el Blueprint `auditbrain-python-runner-bp` ya administra estos **cuatro** recursos.

### 3.2 Servicios que NO pertenecen a este entorno (no incluir ni modificar)

```text
sri-robot-audit
smart-budget-builder
audit-ia-recursos
hg-abogados-ia-render
```

### 3.3 Ya configurado

- Tailscale, SSH, VS Code Remote-SSH, Claude en la Lenovo.
- Tres clones independientes del repo.
- GitHub: `main` protegida (PR obligatorio; "Require status checks to pass before merging" activado).
- Render producción funcionando.

### 3.4 Pendiente

- Habilitar Preview Environments en el `render.yaml`.
- DB de preview, frontend → backend de preview, backend → DB de preview.
- CORS para URLs de preview.
- Separar variables de producción y de preview.
- (Opcional, futuro) CI y exigir checks antes del merge.

---

## 4. Hallazgos del `render.yaml` actual

Estos puntos salen de la lectura del archivo. **Verifica cada uno en la Fase 0**, no los asumas.

| # | Hallazgo | Riesgo | Acción |
|---|---|---|---|
| 1 | `auditbrain-frontend` tiene `pullRequestPreviewsEnabled: true` y `VITE_API_BASE` fijo al backend de **producción**. | **Hoy**, cada PR crea un frontend de prueba conectado a datos reales. | Reemplazar por la configuración de Preview Environments (sección 6). Mientras tanto, nadie debe crear ni modificar datos en esos previews. |
| 2 | `auditbrain-clientes` tiene `pullRequestPreviewsEnabled: false` y `VITE_API_BASE` también fijo a producción. | Si se activa previews sin cambiar esto, apunta a producción. | Mismo tratamiento que el frontend. |
| 3 | Todas las variables `sync: false` **no se copian a los previews**. | El backend de un preview no arranca (falta JWT, API key, CORS…). | Dar valores de prueba por el mecanismo de Render (sección 7). |
| 4 | `DATABASE_URL` viene de `fromDatabase: auditbrain-db`. | Si el preview resuelve esto a su propia DB, bien. Si no, apuntaría a producción. | Verificar en el primer preview que la DB es distinta. |
| 5 | `CORS_ALLOW_ORIGINS` es `sync: false` y producción lista dominios fijos. | Los previews usan URLs temporales de Render y serían bloqueados. | Ver sección 8. |
| 6 | El backend usa disco persistente en `/var/data` y `AUD_OF_TMP_DIR=/var/data/obligaciones_fiscales`. | Si el preview no tiene ese disco, falla la generación/descarga de archivos ICT. | Verificar en el primer preview; la documentación de Render habla de inicialización de previews incluyendo archivos en disco. |
| 7 | Valores versionados que apuntan a recursos reales: `CLIENT_PORTAL_URL` (producción), `EVENTS_NOTIFY_EMAIL`, `RESEND_FROM_EMAIL`, `CHARLA_WHATSAPP_GROUP_URL`, `CHARLA_ZOOM_URL`, `DOCUMENT_SERVICE`. | Un preview podría generar links o correos hacia producción o contactar servicios compartidos. | Usar `previewValue` o neutralizar en preview (sección 7). |
| 8 | `CHARLA_ZOOM_URL` contiene el enlace de Zoom **con su contraseña** escrito en el archivo. | Secreto versionado en el repo. | Recomendar al humano moverlo al dashboard como `sync: false`. No lo repitas en ningún output. |
| 9 | `CLIENT_PORTAL_SESSION_CHECK_ENABLED=true` (sesión única por cuenta). | En previews dificulta que varias personas prueben con la misma cuenta. | Proponer `previewValue: "false"` y que decida el humano. |
| 10 | El backend es `plan: standard` porque con `starter` (512 MB) hubo OOM en producción (ICT/NIIF, OCR, PDF). | Un preview en `starter` puede morir con tareas pesadas; en `standard` cuesta más. | Decide el humano (sección 12). |
| 11 | Los frontends declaran `domains` propios. | Un preview no debe reclamar esos dominios. | Verificar que Render no los aplica a previews. |
| 12 | `autoDeploy: true` en producción. | Al mergear a `main`, se redespliega producción y el Blueprint se sincroniza. | Revisar el diff con mucho cuidado antes de mergear (Fase 1). |
| 13 | El bloque `databases` tiene un comentario: Render **bloqueó** una sincronización por intentar degradar el plan de la DB. | Cualquier cambio mal hecho en ese bloque puede bloquear **todo** el sync. | **No tocar** `plan`, `databaseName` ni `user` de `auditbrain-db`. |
| 14 | La lógica de proveedores LLM hace failover; si no hay ningún proveedor, la skill se detiene. | Un preview sin ninguna clave de LLM no puede probar funciones de IA. | Ver sección 7. |
| 15 | `ANTHROPIC_API_KEY` y `ANTHROPIC_MODEL` existen en el dashboard del servicio, pero **no** en el `render.yaml`. | Fueron configuradas a mano; no hay definición versionada. | No las copies a ningún archivo. Decide con el humano si el preview las usa (sección 7). |

---

## 5. Hechos de Render que debes tener en cuenta

Basados en la documentación oficial. Verifica los nombres exactos de campos contra el esquema JSON antes de escribir nada: <https://render.com/schema/render.yaml.json>.

- Los Preview Environments requieren un **workspace Professional o superior** (esto es el plan del workspace, no el plan `standard` de un servicio). El humano debe confirmarlo en Billing.
- Se activan en el `render.yaml` con `previews.generation`: `off` (por defecto), `manual` o `automatic`.
- `manual`: el preview solo se crea cuando alguien lo pide (el mecanismo exacto, botón en el dashboard o etiqueta/título del PR, hay que confirmarlo en la documentación vigente). `automatic`: cada PR contra la rama enlazada crea un preview.
- `previews.expireAfterDays` elimina automáticamente el preview pasado ese tiempo. Render también lo elimina al cerrar o mergear el PR.
- Los servicios admiten `previews.plan` para usar una instancia más pequeña en previews. Las bases de datos admiten `previewPlan` (revisar el esquema; hay restricciones con los planes "flexible").
- `previewValue` en una variable de entorno permite darle un valor distinto en previews.
- Las variables `sync: false` **no se copian** a los previews. Para compartir secretos de prueba entre previews, Render documenta usar un **grupo de variables de entorno** (leer esa sección de la documentación antes de implementarlo).
- Un servicio puede optar por no generar previews (`previews.generation: off` a nivel servicio).
- Los PRs con ciertas marcas en el título (por ejemplo `[skip preview]`, `[skip render]`) no generan preview.
- La CLI de Render permite validar el archivo: `render blueprints validate`.
- Docs: <https://render.com/docs/preview-environments> · <https://render.com/docs/blueprint-spec> · <https://render.com/docs/yaml-spec>

---

## 6. Diseño objetivo (esqueleto, NO es el archivo final)

> Los nombres de campos pueden variar según el esquema vigente. Valida con la CLI y ajusta. **No copies esto tal cual.**

```yaml
# --- A nivel raíz: activar Preview Environments ---
previews:
  generation: manual        # Fase 1. Se cambia a "automatic" en la Fase 4.
  expireAfterDays: 3        # Valor sugerido; lo decide el humano.

databases:
  - name: auditbrain-db
    # NO modificar plan / databaseName / user (producción).
    # Opcional y SOLO con aprobación explícita del humano: previewPlan menor,
    # para reducir el costo de cada DB de preview.

services:
  - type: web
    name: auditbrain-python-runner
    # ... todo lo existente sin cambios ...
    previews:
      plan: starter         # Decide el humano (ver hallazgo 10).
    envVars:
      # Marca para que el código distinga producción de preview.
      - key: APP_ENV
        value: production
        previewValue: preview
      # Ejemplos de variables que necesitan un valor distinto en preview:
      # - CLIENT_PORTAL_URL, EVENTS_NOTIFY_EMAIL, CLIENT_PORTAL_SESSION_CHECK_ENABLED
      # (ver matriz de la sección 7)

  - type: web
    name: auditbrain-frontend
    env: static
    # Quitar el campo antiguo pullRequestPreviewsEnabled (reemplazado por la
    # configuración de previews). Confirmar contra el esquema.
    envVars:
      - key: VITE_API_BASE
        value: "https://auditbrain-python-runner.onrender.com"
        # previewValue: resolver según la sección 9 (frontend → backend del preview)

  - type: web
    name: auditbrain-clientes
    env: static
    envVars:
      - key: VITE_API_BASE
        value: "https://auditbrain-python-runner.onrender.com"
        # previewValue: igual que el frontend
```

---

## 7. Variables de entorno: producción vs preview

Principio: **producción y preview jamás comparten secretos ni destinos.** Los previews usan credenciales de prueba y tienen efectos laterales neutralizados.

| Variable | Producción | Preview | Notas |
|---|---|---|---|
| `DATABASE_URL` | `fromDatabase` → DB de producción | `fromDatabase` → **DB del preview** | Verificar que es distinta (hallazgo 4). |
| `VITE_API_BASE` (frontend y clientes) | Backend de producción | **Backend del preview** | Sección 9. |
| `CORS_ALLOW_ORIGINS` | Dominios de producción | Permitir solo los frontends del preview | Sección 8. |
| `AUDITBRAIN_JWT_SECRET` | Secreto de producción | Secreto **distinto**, solo para previews | Que un token de preview no valga en producción. |
| `AUDITBRAIN_API_KEY` | Clave de producción | Clave distinta, solo para previews | |
| `AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` | Admin real | Credenciales de **prueba** | La DB del preview nace vacía; el admin se crea solo al primer arranque (idempotente). |
| `RESEND_API_KEY` | Clave real | **No definir** | Sin clave no se envían correos reales. |
| `EVENTS_NOTIFY_EMAIL`, `RESEND_FROM_EMAIL` | Reales | Neutralizar | Evita avisos a casillas reales. |
| `CLIENT_PORTAL_URL` | URL de producción | URL del frontend/clientes del preview | Para que los links generados no apunten a producción. |
| `CLIENT_PORTAL_SESSION_CHECK_ENABLED` | `true` | `false` (propuesta) | Decide el humano. |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | Reales | Claves de prueba o planes gratuitos | Necesitas **al menos un proveedor de LLM** para probar funciones de IA. |
| `ANTHROPIC_API_KEY` | En el dashboard | Clave aparte con límite de gasto, o sin definir | Decide el humano. |
| `LOCAL_LLM_*`, `COMFY_BRIDGE_*`, `MOTOR_*` | Servidores propios | **No definir** por defecto | Las funciones asociadas degradan o responden 503 (documentado en los comentarios del yaml). |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` (OCR) | Real | No definir, o cuenta de prueba | Tiene costo. |
| `CANVA_MCP_OAUTH_TOKEN` | Real | No definir | |
| `CHARLA_ZOOM_URL`, `CHARLA_WHATSAPP_GROUP_URL` | Reales | Neutralizar con `previewValue` | |
| `DOCUMENT_SERVICE` | Servicio externo compartido | Decidir con el humano | Es un servicio compartido, no aislado por PR. |

**Cómo entregar los secretos de prueba a los previews:** usa el mecanismo que documenta Render (grupo de variables de entorno para previews). **Antes y después** de aplicar el cambio, el humano debe comparar las variables de entorno de producción para confirmar que **no cambió ninguna**. Si el mecanismo elegido pudiera añadir variables a producción, no lo uses y pregunta.

---

## 8. CORS

- Producción debe seguir aceptando solo sus dominios.
- El backend del preview debe aceptar **únicamente** las URLs de los frontends de **su** preview (por ejemplo, el patrón `https://auditbrain-frontend-pr-<n>.onrender.com`, que ya aparece en un comentario del yaml; **verifica el patrón real** en el primer preview).
- Revisa cómo el backend lee `CORS_ALLOW_ORIGINS` (lista exacta, regex, comodín). Si hay que añadir soporte para un patrón, hazlo **solo cuando `APP_ENV=preview`**.
- **Nunca** pongas `*` como origen permitido en producción.

---

## 9. Frontend → backend del preview

Es el punto técnico más delicado: `VITE_API_BASE` se resuelve **en tiempo de build** y hoy está fijo.

Opciones, en orden de preferencia (prueba cuál funciona, no asumas):

1. **Referencia dinámica de Render** entre servicios del Blueprint (`fromService` u otra propiedad que exponga la URL pública del backend del preview). Revisa la documentación del esquema para saber qué propiedades existen para un servicio web y si sirve para un sitio estático.
2. **Resolución en el navegador:** que el frontend derive la URL del backend a partir de su propio hostname **solo si** coincide con el patrón de preview (`...-pr-<n>.onrender.com`). En producción debe seguir usando la URL de producción sin ningún cambio de comportamiento.
3. **`previewValue` explícito**, si Render genera URLs de preview predecibles.

Sea cual sea la opción: **el comportamiento en producción debe ser idéntico al actual.**

---

## 10. Plan por fases (con puertas de aprobación)

### Fase 0 — Diagnóstico (solo lectura) ← **empieza aquí**

No edites nada. Revisa y responde en el chat:

1. Qué define hoy `render.yaml` (servicios, DB, disco, dominios, variables) y si coincide con la sección 3 y 4 de este documento.
2. En el frontend y clientes: cómo se usa `VITE_API_BASE` y si hay otras URLs fijas a producción.
3. En el backend: cómo se lee `CORS_ALLOW_ORIGINS`; si ya existe algún indicador de entorno (`APP_ENV` u otro); cómo se crean las tablas (migraciones o creación automática) y si el arranque con una DB vacía funciona; cómo se crea el admin inicial.
4. Qué variables son necesarias para que el backend **arranque** y cuáles solo habilitan funciones opcionales.
5. Qué tests existen y cómo se ejecutan; si `render` (CLI) y `gh` están instalados en la Lenovo.
6. Qué hace falta para resolver la sección 9 y qué opción propones.
7. Riesgos adicionales que veas.

**Puerta:** el humano revisa y aprueba pasar a la Fase 1.

### Fase 1 — Cambio mínimo en el `render.yaml` (rama `feat/render-previews`)

1. Antes de editar, el humano exporta o captura las variables de entorno de producción de los tres servicios (para comparar después).
2. Crea la rama desde `main` actualizado.
3. Aplica solo los cambios necesarios: sección `previews`, `previewValue`, `APP_ENV`, reemplazo del flag antiguo de previews del frontend, ajustes de CORS y de URL del backend (secciones 8 y 9).
4. Valida: `render blueprints validate`. Compila ambos frontends localmente y ejecuta los tests existentes.
5. Muestra el **diff completo** al humano. Debe ser pequeño y no tocar nada de producción.
6. Abre el PR.

**Puerta:** el humano revisa el diff línea por línea. Pregunta explícita: *"¿Algo de este diff cambia producción?"*.

> Nota: Render lee la configuración de previews del `render.yaml` de la rama enlazada (`main`), por eso se necesitan **dos PRs**: este (que activa los previews) y uno de prueba (Fase 3).

### Fase 2 — Merge y verificación de producción

1. El humano mergea.
2. Render sincroniza el Blueprint. El humano comprueba: sync sin errores, producción sirve normal (frontend, clientes, `/healthz`), variables de producción idénticas a las exportadas.
3. Si algo falla: `git revert` del merge y nuevo sync. Avisa de inmediato.

**Puerta:** producción verificada.

### Fase 3 — Prueba con `feat/test-preview`

Cambio trivial y visible: por ejemplo, un texto en el frontend y un campo en una respuesta de la API. Crea el PR y el preview (manual o automático según la configuración) y ejecuta los **tests de aceptación** de la sección 11.

**Puerta:** todos los tests de aceptación en verde.

### Fase 4 — Apertura al equipo

1. Si se desea, cambiar `previews.generation` a `automatic` mediante un PR pequeño (el humano decide).
2. Compartir la guía de la sección 12 con X, Y y Z.

### Fase 5 — Opcional / futuro

CI y checks obligatorios (sección 14).

---

## 11. Tests de aceptación del primer preview

Marca cada uno antes de dar el flujo por válido:

- [ ] El PR genera un preview con **backend, frontend, clientes y DB** propios (nombres con `-pr-<n>`).
- [ ] Las llamadas de red del frontend del preview van al **backend del preview**, no al de producción.
- [ ] El backend del preview usa una **DB distinta**: los usuarios de producción no existen y el admin de prueba sí.
- [ ] Sin errores de CORS en la consola del navegador.
- [ ] Producción no cambió: URLs sirven normal y las variables de entorno son idénticas a las exportadas.
- [ ] No se enviaron correos reales.
- [ ] Funciones que escriben archivos (ICT/PDF/Excel) funcionan en el preview, o el comportamiento sin disco está documentado.
- [ ] Un segundo PR simultáneo crea un segundo preview independiente.
- [ ] Un nuevo push al PR actualiza el mismo preview (no crea otro).
- [ ] Al cerrar el PR, el preview desaparece.
- [ ] El humano revisó el costo en Billing tras la prueba.

---

## 12. Decisiones que debe tomar el humano

| Decisión | Opciones |
|---|---|
| ¿El workspace tiene el plan necesario? | Verificar en Billing (Professional o superior). |
| `manual` o `automatic` | Empezar en `manual` por costo; pasar a `automatic` tras validar. |
| Plan del backend en preview | `starter` (más barato, riesgo de OOM con tareas pesadas) o `standard`. |
| Plan de la DB de preview (`previewPlan`) | Mantener igual o reducir (cambia el bloque `databases`: solo con aprobación). |
| `expireAfterDays` | 3 días como punto de partida. |
| Qué claves de prueba se dan a los previews | Ver sección 7. |
| ¿Neutralizar sesión única en preview? | Sí/No. |
| Mover `CHARLA_ZOOM_URL` al dashboard | Recomendado. |

---

## 13. Flujo diario: qué haces cuando un usuario te pide un cambio

Cuando X, Y o Z te pide algo ("agrega tal botón", "arregla tal error"):

1. `git fetch origin`, actualizar `main` y crear una rama **desde `main`** con nombre de tarea (`feat/...` o `fix/...`).
2. Implementar el cambio y ejecutar tests/compilación en local.
3. Commit con un mensaje claro y `git push` de la rama. **Nunca a `main`.**
4. Abrir el Pull Request contra `main`. Si `gh` no está instalado, dar al usuario el enlace de GitHub para abrirlo.
5. Esperar el preview y **darle al usuario las URLs** (están en el PR o en el dashboard de Render).
6. Si el usuario encuentra un error: corregir, `push` de nuevo (el mismo preview se actualiza) y volver a probar.
7. Cuando esté aprobado, el usuario mergea desde GitHub. Después, quien siga trabajando actualiza su rama con `main`.

Reglas extra para ti en este flujo:

- No uses datos reales de clientes en pruebas del preview.
- Si un cambio toca `render.yaml`, variables de entorno, la base de datos o CORS, **avisa y pide revisión explícita**.
- Si el preview falla al arrancar, revisa los logs de Render y reporta la causa antes de intentar arreglos grandes.
- Cierra los PRs abandonados: cada preview abierto cuesta dinero.

---

## 14. Fuera de alcance por ahora (futuro)

- **CI** y exigir checks antes del merge. La regla "Require status checks" de GitHub ya está activada, pero solo bloquea si hay checks seleccionados. Tras el primer preview, revisar si Render aparece como check en GitHub y, entonces, decidir si exigirlo.
- Datos de ejemplo (seed) más completos para los previews, si hacen falta.
- Migrar otros servicios (los de la sección 3.2) a este esquema. **No ahora.**

---

## 15. Qué hacer si algo sale mal

- Sync de Blueprint con error: no insistas con cambios en cadena. Reporta el mensaje exacto y revierte con `git revert` si afecta producción.
- Un preview apunta a producción: **detén todo**, avisa al humano y desactiva previews (`previews.generation: off`) en un PR urgente.
- No pulses "Manual sync" en Render sin autorización del humano.
