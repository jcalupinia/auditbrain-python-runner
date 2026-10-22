# Preview Environments por Pull Request en Coolify (mismo servidor de producción)

Estado: **preparado, no desplegado**. Este documento acompaña a `docker-compose.preview.yml`, a los Dockerfiles de preview de los frontends y a los workflows `preview-*`. Nada de esto crea aplicaciones ni contenedores por sí solo; la aplicación de previews en Coolify, los registros DNS, los secretos de GitHub y las credenciales de GHCR son acciones administrativas separadas que requieren aprobación.

## 1. Qué es un preview

Por cada Pull Request, un conjunto aislado de cinco contenedores en el mismo servidor de producción, administrado por Coolify como **aplicación Docker Compose** del entorno `previews`:

| Servicio | Imagen | Para qué |
|---|---|---|
| `init` | `alpine:3.20` | Genera una sola vez, en el volumen `secrets` del PR, la contraseña de Postgres y el secreto JWT (modo 600) y queda en espera (`sleep`) con un healthcheck que confirma ambos archivos; `db` arranca cuando ese healthcheck pasa. Sin claves propias de Coolify (`exclude_from_hc`), para que el Compose sea estándar. |
| `db` | `postgres:18-alpine` | Base exclusiva del PR. Volumen `pgdata` montado en `/var/lib/postgresql` (PostgreSQL 18 coloca `PGDATA` en `/var/lib/postgresql/18/docker`; verificar con `SHOW data_directory`). Sin puerto publicado. |
| `backend` | `ghcr.io/jcalupinia/auditbrain-preview-backend:sha-<commit>` | FastAPI con `APP_ENV=preview`. Arma `DATABASE_URL` desde el archivo de secretos en su `command`. |
| `consola` | `ghcr.io/jcalupinia/auditbrain-preview-consola:sha-<commit>` | nginx con el `dist` de Vite. Resuelve el backend por hostname. |
| `clientes` | `ghcr.io/jcalupinia/auditbrain-preview-clientes:sha-<commit>` | nginx con el `dist` del portal (incluye `frontend-shared`). |

Dominios por servicio con la plantilla `{{pr_id}}.{{domain}}` de Coolify: `<n>.api.preview.audit-ia.ec` (puerto 10000), `<n>.consola.preview.audit-ia.ec`, `<n>.clientes.preview.audit-ia.ec`.

## 2. Mismo commit en todos los servicios: identidad por `SOURCE_COMMIT` (F1)

**Estado (2026-10-20): el redespliegue del commit `abc9d4b8` falló en `docker compose pull` (`sha-SOURCE_COMMIT requerido`, ver 4b); corrección en código local, NO desplegada; el preview anterior sigue operativo.** El preview del PR #384 que sigue en ejecución es la versión manual anterior (imágenes elegidas con la variable de preview compartida `PREVIEW_IMAGE_TAG`, que todavía existe en Coolify y **no debe tocarse** hasta F2). La validación real de que Coolify interpola `SOURCE_COMMIT` al descargar las imágenes con este Compose requiere una autorización posterior; lo comprobado en F0-R es que el contenedor recibe `SOURCE_COMMIT=<head>` y que `docker compose config --images` con un Compose de prueba interpola `sha-${SOURCE_COMMIT}`.

1. `preview-images` construye las tres imágenes del `head.sha` del PR en GitHub Actions y las publica con una sola etiqueta inmutable por imagen, `sha-<sha completo>` (sin `latest` ni alias). Cada imagen lleva `org.opencontainers.image.revision=<sha>` y `ENV BUILD_COMMIT=<sha>` (en los frontends, además `/build-info.json`).
2. El Compose referencia `ghcr.io/jcalupinia/auditbrain-preview-<servicio>:sha-${SOURCE_COMMIT:?SOURCE_COMMIT requerido}`. Coolify 4.4.6 escribe `SOURCE_COMMIT` (el `head` del PR, resuelto con `git ls-remote refs/pull/N/head` o el `commit` que se le pase) en el `.env` que `docker compose` recibe con `--env-file` para `pull` y `up`; por eso cada PR usa **solo** sus imágenes, sin ninguna variable compartida entre previews (las variables de preview de Coolify son comunes a todos los previews de la aplicación). Si `SOURCE_COMMIT` falta o está vacío, `docker compose` falla antes de arrancar nada.
3. El backend recibe `SOURCE_COMMIT` porque Coolify adjunta el mismo `.env` a **todos** los servicios (`env_file: .env`, `ApplicationDeploymentJob`), y `PREVIEW_EXPECTED_IMAGE_TAG=sha-${SOURCE_COMMIT}` declarado en el Compose; `preview_bootstrap` exige, en el proveedor Coolify, `BUILD_COMMIT`, `SOURCE_COMMIT` y la etiqueta esperada como SHA de 40 caracteres idénticos; si no, **no arranca** (código 3). En Render, `SOURCE_COMMIT` sigue siendo opcional (compatibilidad), pero si llega debe coincidir. `init` aplica la misma puerta antes que nadie: etiqueta `sha-<40 hex>` obligatoria y, si el entorno trae `SOURCE_COMMIT`, coincidencia exacta; db, backend, consola y clientes dependen de init.
4. Un push sin imágenes publicadas hace fallar el `pull` (seguro); un `SOURCE_COMMIT` que no coincida con la imagen hace fallar el arranque (seguro).
4b. **Regla del analizador de Coolify (incidente del 2026-10-20).** `parseDockerComposeFile` (`bootstrap/helpers/shared.php`, Coolify 4.4.6) recorre las entradas de `environment` de cada servicio y, si el **valor empieza por `$`**, crea una variable de la aplicación (`is_preview=false`) con la clave de dentro de `${…}` y, como valor, el texto que sigue a `:-`, `-`, `:?` o `?`. La entrada `SOURCE_COMMIT=${SOURCE_COMMIT:?SOURCE_COMMIT requerido}` del primer Compose F1 creó así la variable `SOURCE_COMMIT = "SOURCE_COMMIT requerido"`. Al desplegar, `generate_runtime_environment_variables` escribe primero `SOURCE_COMMIT=<head>` (solo si no existe una variable de preview con esa clave) y **después** vuelca las variables de producción no sobreescritas por las de preview; en un `.env` la última línea gana, así que `docker compose pull` resolvió `…:sha-SOURCE_COMMIT requerido` (`invalid reference format`). Reproducido localmente con `docker compose config --env-file` y un `.env` con la clave duplicada. Consecuencias: (a) ninguna entrada de `environment` puede tener un valor que empiece por `$` salvo las mágicas `${SERVICE_FQDN_*}`/`${SERVICE_URL_*}` (lo vigila `tests/test_preview_compose.py::test_regresion_analizador_coolify_no_crea_variables_desde_environment` y el workflow `preview-validate`); el campo `image` no pasa por esa regla y `sha-${…}` tampoco; (b) **antes del siguiente redespliegue hay que borrar en Coolify la variable `SOURCE_COMMIT` que el analizador creó** (aplicación `auditbrain-preview` → Environment Variables, pestaña Production; comprobar que la pestaña Preview tampoco la tenga): el Compose corregido no basta mientras esa variable siga en la base de Coolify, porque seguirá entrando al final del `.env`. El guion P1D `posterior` y el propio backend detectan el caso (`SOURCE_COMMIT` distinto de 40 hex ⇒ no arranca).
5. Verificación en el piloto: etiqueta de imagen en `docker ps` = `head.sha` del PR = label `revision` = `build.commit` en `/api/v1/health` = `SOURCE_COMMIT` del entorno = `commit` en `/build-info.json` de consola y portal.

**Controlador:** `scripts/preview_lifecycle.py` (F2/F3) ya no usa `PREVIEW_IMAGE_TAG` ni cupos fijos: cada PR se despliega con las imágenes de su propio `head.sha` y la admisión la decide la capacidad real (§7, §11). `preview-lifecycle.yml` fue retirado; los workflows vigentes son `preview-images`, `preview-deploy` y `preview-cleanup`, inactivos hasta `PREVIEW_PIPELINE_ENABLED=true` (§13).

## 3. Identidad del PR y fallo seguro

- Fuente primaria única: `PREVIEW_PUBLIC_HOST=${SERVICE_FQDN_BACKEND_10000}` (la variable mágica que Coolify rellena con el dominio del preview para el servicio `backend`, puerto 10000). Fuentes de confirmación: `COOLIFY_FQDN` y, en Render, `RENDER_EXTERNAL_HOSTNAME`. Todas se normalizan (`backend/app/core/hostnames.py`) y deben coincidir.
- `backend/app/core/preview.py::preview_bootstrap()` se ejecuta al importar `app.py`. En preview exige: identidad válida y no ambigua; `DATABASE_URL` con host `db`; `CORS_ALLOW_ORIGINS` sin dominios de producción; `CLIENT_PORTAL_URL` que no sea de producción; secreto JWT legible en `PREVIEW_SECRETS_DIR`; imagen del commit esperado. Cualquier incumplimiento → log `PREVIEW: configuración inválida` y salida con código 3. No existe ningún fallback a «cualquier PR».
- CORS: `cors_origin_regex_for()` acepta únicamente `https://<n>.consola|clientes.preview.audit-ia.ec` y, mientras conviva Render, `https://auditbrain-frontend|clientes-pr-<n>.onrender.com`, con `fullmatch`, sin puerto.
- Frontends: `previewResolver.js` (idéntico en consola y portal) deriva el backend del hostname normalizado; cualquier host no reconocido deja al cliente sin backend (fallo cerrado), nunca producción.
- `/api/v1/health` expone `preview` (`active`, `provider`, `pr`, `config`) y `build.commit`.

## 4. Secretos exclusivos por preview

- `init` genera **cuatro** secretos alfanuméricos con `/dev/urandom` dentro del volumen `secrets` del PR: `pg_password` (40), `jwt_secret` (64), `admin_password` (32) y `api_key` (48). Escritura atómica (archivo temporal + `mv`), `umask 077` y modo 600; si un archivo existe no se toca, así que un redespliegue del mismo PR conserva los valores y otro PR, con su propio volumen `-pr-<n>`, obtiene otros. El guion no imprime ningún valor.
- `db` lee `POSTGRES_PASSWORD_FILE`; el backend arma la URL de conexión en su `command` y `jwt_tokens.py` lee `jwt_secret` del volumen. Nada pasa por variables de Coolify, logs ni repositorio.
- No se usan `SERVICE_PASSWORD_*` de Coolify: se almacenan en la aplicación con `is_preview=false` y se comparten entre previews (verificado en el código fuente de Coolify 4.4.x).
- Grupo «Preview» de variables de la aplicación: con el Compose de F1 **ninguna** es necesaria (`PREVIEW_IMAGE_TAG` permanece en Coolify solo mientras siga desplegada la versión manual; se retirará en F2). La contraseña del administrador de prueba y la API key ya no son variables de Coolify: el `command` del backend exporta `AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD` y `AUDITBRAIN_API_KEY` desde `/run/secrets/admin_password` y `/run/secrets/api_key` (con `set -eu`: sin archivo, no arranca). El guion comprueba primero que ninguna de esas credenciales llegue heredada del entorno de Coolify (si `AUDITBRAIN_JWT_SECRET`, `AUDITBRAIN_API_KEY` o `AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD` ya existen, termina con código 3), exige los cuatro archivos de `/run/secrets` y lee cada valor con una asignación independiente antes de exportar (un `export VAR="$(cat f)"` bajo `set -e` no abortaría si `cat` fallara). `preview_bootstrap` repite las comprobaciones en Python: credenciales de prueba no vacías, secreto JWT del volumen (en Coolify el JWT se firma **siempre** con `/run/secrets/jwt_secret`, nunca con una variable) y ausencia de credenciales productivas heredadas (lista explícita en `backend/app/core/preview.py`). El correo del administrador es fijo, `preview-admin@audit-ia.ec` (no es una identidad productiva; el admin vive en la base propia del PR), elegido porque el validador `EmailStr` del bootstrap rechaza dominios de uso especial como `.invalid`. Acceso del administrador autorizado, sin pasar por logs: `docker exec <backend-pr-n> sh -c 'cat /run/secrets/admin_password; echo'` (ídem `api_key`). Sin proveedores de IA, correo, Stripe, OCR ni Canva. Nunca valores de producción.

## 5. Aislamiento de red en el mismo host (mecanismo verificable; nada aplicado todavía)

Coolify conecta a la red compartida `coolify` (la del proxy Traefik) los servicios con dominio y, según el ajuste «Connect To Predefined Network», potencialmente todos. En esa red el backend del preview puede alcanzar por nombre al Postgres de producción (`z4wy8ngriiesg6z20n7ftcnj:5432`) y al backend de producción. El preview no tiene sus credenciales y su arranque exige `DATABASE_URL` → `db`, pero la **garantía de red** requiere una regla en el host:

```bash
# Propuesta (NO aplicada). Bloquea tráfico desde la red del preview hacia la red de producción
# y hacia la red del proxy, salvo el retorno de conexiones establecidas. Se evalúa en la cadena
# DOCKER-USER, que Docker respeta. Requiere identificar las subredes reales con `docker network inspect`.
PREVIEW_NET=$(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}' <red-del-preview>)
PROD_NET=$(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}' <red-de-producción>)
iptables -I DOCKER-USER -s "$PREVIEW_NET" -d "$PROD_NET" -m conntrack --ctstate NEW -j DROP
# Para que Traefik (en la red coolify) siga llegando al preview, no se bloquea el tráfico ENTRANTE
# desde la red coolify; sí el saliente NUEVO desde el preview hacia contenedores de producción.
```

El riesgo residual de salida HTTP(S) del preview hacia las API públicas de producción **sigue pendiente** (fase F5 del informe D3A: guardián de egreso en el host). Verificación en el piloto: `scripts/preview_isolation_check.sh` dentro del backend del preview (intenta conexiones TCP a los objetivos de producción y espera que todas fallen) y `docker inspect` de los cinco contenedores para anotar en qué redes quedan (P-08). El Compose define `preview_internal` (`internal: true`) para `init`, `db` y `backend`; si Coolify sobrescribe las redes, se registra y manda la regla DOCKER-USER.

## 6. GHCR privado y credencial de solo lectura (sin crear nada ahora)

- Paquetes **`auditbrain-preview-backend`, `auditbrain-preview-consola`, `auditbrain-preview-clientes`** en `ghcr.io/jcalupinia`: **privados**.
- **Nunca se publican con `GITHUB_TOKEN`.** Según la documentación de GitHub Packages, un paquete publicado desde un workflow con `GITHUB_TOKEN` «hereda el modelo de visibilidad y permisos del repositorio donde corre el workflow»; este repositorio es público, y así nacieron PÚBLICOS los paquetes `auditbrain-backend|consola|clientes` publicados el 2026-10-15 (no se reutilizan ni se borran sin autorización). El workflow `preview-images` concede a `GITHUB_TOKEN` solo `contents: read`.
- La publicación usa una **credencial dedicada de alcance mínimo**: un token personal classic del propietario con el alcance `write:packages` (los tokens fine-grained no sirven para GHCR), guardado por el propietario como secreto de Actions `GHCR_PUBLISH_TOKEN` (Settings → Secrets and variables → Actions). Un paquete nuevo creado con un token personal nace privado; vincularlo al repositorio (manual o por la etiqueta OCI `source`) hereda permisos, no visibilidad. La credencial se revoca cuando termina la publicación, con confirmación del propietario.
- **Publicación por etapas y verificada:** primero solo el backend; el propio job comprueba con la credencial que `visibility == private` y que el manifiesto no se descarga de forma anónima (`ghcr.io/v2/...`: 401/403, nunca 200); si falla, no se publica nada más. Los frontends solo se publican si el backend de ese commit existe y es privado.
- El servidor necesita una credencial de **solo lectura** (`read:packages`): un token de GitHub de alcance mínimo o una GitHub App con ese permiso, registrado en Coolify como credencial de registro (*Servers → Registries*) o `docker login ghcr.io` en el servidor. Se crea en una acción administrativa posterior; no está en este PR.
- `scripts/preview_lifecycle.py` comprueba por `HEAD` del manifiesto que las tres imágenes existen antes de desplegar.

## 7. Ciclo de vida automático (F2/F3: implementado; activación con un solo interruptor)

| Workflow | Disparo | Código que ejecuta | Qué hace |
|---|---|---|---|
| `preview-validate.yml` | PR que toque los artefactos de preview | El del PR (sin secretos) | `docker compose config`, regla del analizador de Coolify, init en alpine, build sin push, pruebas de resolución |
| `preview-images.yml` | `pull_request` (opened/synchronize/reopened/ready_for_review) del propio repositorio; `push` de etiqueta `ghcr-preview-pr<N>-(backend\|frontends\|all)-<sha>`; `workflow_dispatch` | El del PR, solo para construir | Puerta: credencial `GHCR_PUBLISH_TOKEN` del propietario con `write:packages`; `PREVIEW_PIPELINE_ENABLED` (en PR y dispatch); PR abierto, contra `main`, sin fork, autor autorizado (propietario + `PREVIEW_AUTHORS_ALLOWED`), HEAD = SHA del evento (un push nuevo cancela al anterior). Publica las tres imágenes `sha-<sha>` privadas y verifica visibilidad y rechazo anónimo |
| `preview-deploy.yml` | `workflow_run` de `preview-images` con éxito; `schedule` cada 15 min; `workflow_dispatch` (`dry_run`) | **Siempre el de la rama por defecto** (nunca el PR) | `scripts/preview_lifecycle.py sincronizar --pr N --sha <head>`: seguridad (§12), checks obligatorios (`PREVIEW_REQUIRED_CHECKS`, por defecto `pytest (python 3.12)`), tres imágenes presentes, `CapacityDecision` (§11) y solo con `ADMIT` crea/actualiza el preview por API (`POST /applications/{uuid}/previews` + `POST /deploy?uuid&pr`), espera el despliegue, verifica que API, consola y portal sirvan el commit exacto y publica los enlaces en un único comentario del PR (etiquetas `preview:activo` / `preview:en-espera` / `preview:rechazado`). El ciclo programado ejecuta `reintentar` (en espera, del más antiguo al más nuevo, un despliegue por ciclo) y `caducidad` |
| `preview-cleanup.yml` | `pull_request_target` `closed` | El de la rama base | `cerrar --pr N`: verifica identidad (PR no abierto, del repositorio, preview con ese número en la aplicación de previews) y borra solo ese preview |

Candado de admisión: grupo de concurrencia `preview-admision` compartido por `preview-deploy` y `preview-cleanup` (sin cancelación): nunca hay dos admisiones ni una admisión y un cierre a la vez. Coolify añade su propio 429 si ya hay un despliegue en cola de la aplicación; el controlador lo trata como `DEFER` con reintento a 60 s.

El controlador solo llama a `GET/POST /applications/{uuid}/previews`, `GET/DELETE /applications/{uuid}/previews/{pr}`, `POST /deploy?uuid&pr` y `GET /deployments/...` de la aplicación `COOLIFY_PREVIEW_APP_UUID` (lista blanca en `Coolify._permitido`, con prueba); aborta ante una `COOLIFY_URL` que no sea `https://` (el panel ya responde en `https://coolify.audit-ia.ec`). `PREVIEW_IMAGE_TAG` y `MAX_ACTIVE_PREVIEWS` han desaparecido del código.

## 8. Recursos (presupuesto por preview; concurrencia por capacidad real, no por cupo fijo)

| Servicio | RAM (`mem_limit` = `memswap_limit`) | CPU | `cpu_shares` | `oom_score_adj` |
|---|---|---|---|---|
| backend | 1024 MiB | 1.5 | 256 | 900 |
| db | 192 MiB | 0.5 | 256 | 700 |
| consola / clientes | 32 MiB cada uno | 0.2 | 128 | 600 |
| init | 16 MiB | 0.1 | — | — |
| **Total** | **1296 MiB** | | | |

Estos límites son **máximos por preview**, no consumos en reposo (el PR #384 usó ~241 MiB en reposo). El número de previews simultáneos lo decidirá en F2 la admisión dinámica con telemetría real del host (§11); la antigua regla «un solo preview activo» queda **obsoleta** y ningún archivo del repositorio debe fijar un cupo. Producción conserva prioridad: sus contenedores tienen `cpu_shares` 1024 y `oom_score_adj` por defecto. `tests/test_preview_compose.py` fija el tope y las reglas. No se afirma que quepan dos o más previews de 1 296 MiB en el servidor actual de ~3,7 GiB: solo la medición de F5 y la admisión de F2 pueden decidirlo, y nunca se ampliará ni contratará infraestructura sin autorización expresa.

## 9. Configuración administrativa que falta (mínima; nada de esto lo hace el código)

Coolify, aplicación `auditbrain-preview`:
1. **Advanced → «Source commit availability» = «Available during build»** (ya activado el 2026-10-20; sin él `docker compose build` falla por `${SOURCE_COMMIT:?}`).
2. **Environment Variables**: ninguna variable llamada `SOURCE_COMMIT` en Production ni en Preview (borradas el 2026-10-20); `PREVIEW_IMAGE_TAG` puede borrarse (obsoleta). Añadir en la pestaña **Preview** `PREVIEW_CAPACITY_TOKEN` (valor aleatorio ≥ 32 caracteres, el mismo que el secreto de GitHub) para que cualquier preview pueda servir `/api/v1/host-capacity`.
3. **Webhooks / preview deployments automáticos de Coolify desactivados** (el controlador es GitHub Actions; Coolify no debe desplegar por su cuenta al abrir un PR).
4. **Rama de la aplicación = `main`** una vez fusionado el PR #384: Coolify lee `docker-compose.preview.yml` de la rama configurada, no del PR (§12).
5. **Token de API** (Keys & Tokens): permisos `read`, `write` y `deploy` (sin `read:sensitive`), creado solo para esta automatización.

**Telemetría antes de activar, sin tocar producción (procedimiento verificable):** el endpoint `/api/v1/host-capacity` lo sirve cualquier backend construido desde este PR, y un preview ve el mismo host que producción. Pasos: (a) en Coolify, pestaña **Preview** de `auditbrain-preview`, crear `PREVIEW_CAPACITY_TOKEN` (aleatorio ≥ 32 caracteres); (b) redesplegar el preview #384 con el head actual del PR (acción manual y autorizada por el propietario; el commit incluye el endpoint); (c) desde cualquier equipo, con el mismo valor en la variable de entorno `PREVIEW_CAPACITY_TOKEN`: `python scripts/verificar_host_capacity.py https://384.api.preview.audit-ia.ec` debe terminar en «APTO» (sin cabecera 401, token incorrecto 401, token correcto 200 con `mem_available_mib`, `swap_used_pct`, `load1`, `cpus`, `disk_free_gib`; un 404 significa que la variable no llegó al backend); (d) en GitHub, secreto `PREVIEW_CAPACITY_TOKEN` y variable `PREVIEW_CAPACITY_SOURCES=https://384.api.preview.audit-ia.ec`; (e) ejecutar `preview-deploy` por `workflow_dispatch` con `accion=capacidad` y `dry_run=true` (permitido con el interruptor apagado; solo lecturas): debe imprimir una `CapacityDecision` con `fuente` y terminar en 0; con `TELEMETRY_UNAVAILABLE` termina en 3 y no se activa nada. Tras fusionar y desplegar producción con este código, añadir la misma variable al backend productivo y poner `PREVIEW_CAPACITY_SOURCES=https://api.audit-ia.ec,https://384.api.preview.audit-ia.ec` (la primera fuente que responda gana). El endpoint no existe (404) donde la variable no esté definida.

GitHub (repositorio): secretos `COOLIFY_URL` (`https://coolify.audit-ia.ec`), `COOLIFY_API_TOKEN`, `COOLIFY_PREVIEW_APP_UUID` (`lrv8o1j8cyqbm3nry5qpziqj`), `GHCR_PUBLISH_TOKEN` (existe), `GHCR_READ_TOKEN` (PAT classic solo `read:packages`; opcional, si falta se usa el de publicación), `PREVIEW_CAPACITY_TOKEN`. Variables: `PREVIEW_PIPELINE_ENABLED` (interruptor único), `PREVIEW_AUTHORS_ALLOWED` (logins de GitHub separados por comas; el propietario siempre está), `PREVIEW_CAPACITY_SOURCES` (`https://api.audit-ia.ec`), y opcionalmente `PREVIEW_FACTOR_HEADROOM`, `PREVIEW_RESERVA_SEGURIDAD_MIB`, `PREVIEW_REQUIRED_CHECKS`, `PREVIEW_DIAS_INACTIVIDAD`. Etiquetas del repositorio: `preview:activo`, `preview:en-espera`, `preview:rechazado`, `preview:keep`, `preview:dockerfiles-aprobados` (se crean solas al usarse).

## 10. Pruebas de aceptación del primer PR

Ver el diseño `DISENO_PREVIEWS_MISMO_SERVIDOR.md` (carpeta documental): P-01 a P-15, incluidas la correspondencia imagen–commit, la verificación de redes y el aislamiento con `preview_isolation_check.sh`.

## 11. Admisión dinámica: contrato `CapacityDecision` (implementado en `scripts/preview_lifecycle.py`)

Cada evaluación produce una `CapacityDecision` (se adjunta al comentario del PR):

| Campo | Tipo | Significado |
|---|---|---|
| `decision` | `ADMIT` · `DEFER` · `REJECT` | Admitir; aplazar con reintento automático (`retry_after`); rechazar (motivo no transitorio) |
| `reason_code` | `OK` · `RAM_HEADROOM` · `CPU_PRESSURE` · `SWAP_PRESSURE` · `DISK` · `OOM_RECENT` · `PRODUCTION_UNHEALTHY` · `TELEMETRY_UNAVAILABLE` · `IN_FLIGHT_RESERVATION` · `IMAGES_MISSING` · `CHECKS_PENDING` · `SECURITY` | Causa principal |
| `pr`, `head_sha`, `observed_at` | int, SHA de 40 hex, UTC | Identidad del PR y momento de la lectura |
| `metrics` | objeto redaccionado | `mem_available_mib`, `headroom_existentes_mib`, `reservas_en_vuelo_mib`, `limite_nuevo_mib` (1 296), `reserva_seguridad_mib` (512), `superposicion_mib` (576), `margen_mib`, `psi_mem_some_60s`, `swap_usada_pct`, `carga_1m`, `cpus`, `disco_libre_gib`, `oom_recientes`, `previews_activos`, `despliegues_en_vuelo`, `frescura_s`, `produccion_sana` |
| `retry_after` | segundos | 900 por defecto; 60 cuando Coolify responde 429 |
| `reservation_id` | `repo/pr/sha/deployment_uuid` | En `ADMIT`, el despliegue lanzado |

**Telemetría:** `GET /api/v1/host-capacity` del backend (cabecera `X-Capacity-Token`; `backend/app/core/host_capacity.py` lee `/proc/meminfo`, `/proc/pressure/memory`, `/proc/loadavg` y el disco; en un contenedor reflejan el host completo). Fuentes en `PREVIEW_CAPACITY_SOURCES` por orden; sin respuesta o con lectura de más de 180 s ⇒ `DEFER TELEMETRY_UNAVAILABLE`.

**Regla de memoria (swap excluida):** `MemAvailable − Σ H_i − Σ L_reservas − L_nuevo − superposición ≥ R_seguridad`, con `H_i = L_i × PREVIEW_FACTOR_HEADROOM` por cada preview activo de OTRO PR (factor 1,0 por defecto = crecimiento posible hasta su límite; bajarlo solo con medición), `L_reservas = (L + superposición)` por cada despliegue de otro PR en `queued`/`in_progress`, `L_nuevo = 1 296`. Actualizar el preview del propio PR no suma `H_i` propio pero sí exige la superposición. Además: producción debe responder 200 (`PREVIEW_PRODUCTION_HEALTH_URLS`), sin OOM reciente (dato `null` = no observable desde un contenedor, se registra), PSI memoria `some avg60 ≤ 20`, swap usada ≤ 75 %, carga 1 min ≤ 2 × CPU, disco ≥ 3 GiB. Con ~3,7 GiB de RAM y producción en el mismo host, el resultado habitual es **un** preview a la vez; coexistirán más solo si `mem_available` lo permite con esas reservas.

**Candado:** grupo de concurrencia `preview-admision` + contabilidad de despliegues en vuelo (`GET /deployments/applications/{uuid}`) + 429 de Coolify. Nunca se detiene ni elimina otro preview para hacer sitio; `caducidad` solo retira previews sin actividad humana (3 días; `preview:keep` exime).

## 12. Plantilla confiable y privilegios del despliegue (implementado; condición de activación)

**Comportamiento real de Coolify 4.4.6, verificado en su código el 2026-10-20 (corrige la versión anterior de esta sección):** en cada despliegue, `Application::loadComposeFile` lee `docker-compose.preview.yml` de la **rama configurada en la aplicación** (`git_branch`, hoy la rama del PR #384; `main` tras fusionar) y es ese archivo el que `applicationParser` convierte en el Compose desplegable; del PR solo se toma el checkout `pull/N/head` para el `SOURCE_COMMIT` y el código. Un PR **no puede** cambiar la plantilla que Coolify ejecuta mientras la rama de la aplicación sea `main`.

Controles implementados por el controlador antes de cualquier despliegue (REJECT/SECURITY si fallan):
1. PR del propio repositorio, abierto, contra `main`, no borrador, autor en la lista autorizada; los forks ni siquiera llegan al workflow con secretos.
2. `docker-compose.preview.yml` del `head.sha` idéntico (mismo blob) al de `PREVIEW_TEMPLATE_REF` (`main`): así las pruebas del PR validan exactamente la plantilla que se despliega.
3. `Dockerfile.render`, `frontend/Dockerfile.preview` y `frontend-client/Dockerfile.preview` idénticos a `main`, salvo etiqueta administrativa `preview:dockerfiles-aprobados` puesta por un mantenedor tras revisión (las imágenes se construyen del código del PR; la plantilla limita recursos, red y privilegios).
4. Checks obligatorios del commit en verde (`PREVIEW_REQUIRED_CHECKS`), tres imágenes privadas publicadas y verificadas, y verificación posterior de que los tres servicios sirven el `head.sha`.
5. `preview-deploy` y `preview-cleanup` ejecutan el código de la rama protegida; el token de Coolify solo se usa contra la aplicación de previews (lista blanca) y por HTTPS.

**Condiciones de activación aún no probadas en el servidor** (no se dan por aprobadas): aislamiento de red del preview hacia servicios internos de producción (§5, regla `DOCKER-USER` pendiente) y medición del consumo real por preview para ajustar `PREVIEW_FACTOR_HEADROOM`. Mientras tanto la política admite con factor 1,0 y producción sana.

## 13. Activación (una sola vez) y prueba controlada

Orden: (1) telemetría verificada según §9 (`verificar_host_capacity.py` en «APTO»); (2) fusionar el PR #384 en `main` (la plantilla pasa a la rama protegida); (3) en Coolify, rama de la aplicación `auditbrain-preview` = `main` y la configuración de §9; (4) crear en GitHub los secretos y variables de §9 con `PREVIEW_PIPELINE_ENABLED` todavía sin definir; (5) ejecutar `preview-deploy` por `workflow_dispatch` con `accion=capacidad` y después `accion=reintentar`, ambas con `dry_run=true` (es el único modo admitido con el interruptor apagado; el script aborta ante cualquier escritura en ese modo) y comprobar en el registro la `CapacityDecision` y la ausencia de llamadas de escritura; (6) definir `PREVIEW_PIPELINE_ENABLED=true`. Desde ese momento cada PR abierto contra `main` por un autor autorizado publica sus imágenes y, si hay capacidad, recibe su preview; cada push lo actualiza; cerrar o fusionar lo elimina. Para pausar todo basta poner la variable en `false`.

Prueba controlada propuesta: una rama de prueba con un cambio trivial (p. ej. un comentario en `README.md`) abierta como PR por el propietario → esperar el comentario «listo» con los tres enlaces y comprobar `build.commit` en `/api/v1/health` = head → hacer un segundo push trivial → el mismo preview se actualiza (mismo número, nuevo commit, `secrets` y `pgdata` conservados: usuario de prueba creado antes sigue existiendo) → abrir un segundo PR de prueba → según la capacidad queda «en espera» con su `CapacityDecision` o se despliega en paralelo → cerrar ambos PR → ambos previews desaparecen y producción (`https://api.audit-ia.ec/api/v1/health`) responde 200 durante todo el ejercicio.


## 14. Conexión privada GitHub Actions → API de Coolify (tailnet; preparado, no activado)

La API de Coolify está restringida por «Allowed API IPs» (middleware `ApiAllowed`, que admite IP y rangos CIDR y
usa la IP real tras Traefik porque `TrustProxies` confía en el proxy). Los runners de GitHub no tienen IP fija, y
abrir la lista a Internet o a los rangos públicos de GitHub queda descartado. La solución elegida es **Tailscale**:
el runner se une a la tailnet existente como nodo **efímero** con etiqueta `tag:ci` (`tailscale/github-action@v4`,
cliente OAuth con alcance `auth_keys` guardado en secretos), fija `coolify.audit-ia.ec` a la IP de tailnet del
servidor en `/etc/hosts` y habla con Traefik por el túnel WireGuard con el certificado TLS real; Coolify ve como
origen una IP `100.64.0.0/10`, que es lo único que se añade a «Allowed API IPs». La acción compuesta
`.github/actions/coolify-tailnet` lo hace y **falla cerrado** antes de que exista cualquier llamada con token;
`preview-deploy` y `preview-cleanup` la ejecutan como primer paso, y `preview-connectivity.yml` es la prueba de
solo lectura (team y previews en 200, y control negativo: la misma consulta por la IP pública debe seguir en 403).

Requisitos administrativos (ninguno aplicado todavía): `tailscaled` en el servidor Hetzner con etiqueta
`tag:coolify`, sin Tailscale SSH ni Funnel (~30 MB de RAM, solo tráfico UDP saliente); ACL de la tailnet con
`tagOwners` para `tag:ci` y `tag:coolify` y una única regla `tag:ci → tag:coolify:443`; cliente OAuth `tag:ci`;
secretos `TS_OAUTH_CLIENT_ID` y `TS_OAUTH_SECRET` y variable `COOLIFY_TAILNET_IP` en GitHub; `100.64.0.0/10`
en «Allowed API IPs». Desactivación inmediata: revocar el cliente OAuth, quitar la regla de la ACL o retirar el
rango de la lista de IP; cualquiera de las tres corta el acceso sin tocar el servidor.

Riesgo residual: `COOLIFY_API_TOKEN` pertenece al Root Team con `read`, `write` y `deploy`, por lo que sus
permisos efectivos alcanzan toda la instancia; el controlador lo acota por código (lista blanca de endpoints de
la aplicación de previews, solo HTTPS, bloqueo de escrituras en simulación) y la tailnet acota desde dónde puede
usarse. Para reducir el alcance en el futuro: equipo propio de Coolify para los previews con su propio token
(requiere que el servidor y el proyecto `previews` pertenezcan a ese equipo) o un token de solo `read` + `deploy`
para el ciclo normal y uno de `write` solo para el cierre.
