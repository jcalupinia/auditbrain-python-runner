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

**Transición e incompatibilidad con el controlador anterior:** `scripts/preview_lifecycle.py` sigue fijando `PREVIEW_IMAGE_TAG`, que este Compose ya no lee; queda **incompatible** y **no debe activarse** (ni `preview-lifecycle.yml` ni `PREVIEW_PIPELINE_ENABLED`) hasta que F2 lo sustituya por el reconciliador del informe D3A.

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

## 7. Ciclo de vida (workflows deshabilitados para ejecución real)

| Workflow | Disparo | Puertas | Qué hace |
|---|---|---|---|
| `preview-validate.yml` | PR que toque los artefactos de preview | Ninguna (no usa secretos) | `docker compose config` con valores ficticios y prueba de fallo con etiqueta vacía; build sin push de las tres imágenes verificando el commit en la metadata; pruebas de resolución de ambos frontends |
| `preview-images.yml` | `workflow_dispatch`, o `push` de una etiqueta `ghcr-preview-pr384-backend-<sha>` / `ghcr-preview-pr384-frontends-<sha>` (publicación por etapas autorizada el 2026-10-15) | Credencial dedicada `GHCR_PUBLISH_TOKEN` presente, del propietario y con `write:packages`. Dispatch: `vars.PREVIEW_PIPELINE_ENABLED == "true"` y sin forks. Etiqueta: repositorio exacto, SHA de 40 caracteres igual al commit apuntado, PR #384 abierto, sin fusionar, contra `main`, sin fork y con ese HEAD exacto; etapa `frontends` solo si el backend del commit existe y es privado; cualquier discrepancia termina sin publicar | Publica solo `sha-<sha>` de `auditbrain-preview-*` (sin `latest` ni alias) con la label OCI `revision`, y verifica tras el push visibilidad `private` y rechazo del acceso anónimo |
| `preview-lifecycle.yml` | Solo `workflow_dispatch` | `PREVIEW_PIPELINE_ENABLED`; `COOLIFY_URL` debe ser `https://`; `dry_run=true` por defecto | `admitir` (cupo `MAX_ACTIVE_PREVIEWS=1`, imágenes presentes, crear sin desplegar, fijar etiqueta, desplegar, comentar), `liberar`, `caducidad` (3 días sin commit, comentario humano ni despliegue; `preview:keep` exime). **Obsoleto (v3, 2026-10-19):** su política `MAX_ACTIVE_PREVIEWS=1` ya no es la política final; F2 la sustituye por admisión dinámica conservadora según la capacidad real del host (ver §11). No activar. |

El despliegue por API queda **inhabilitado** hasta que el panel de Coolify tenga un dominio HTTPS: el script aborta ante una `COOLIFY_URL` que no empiece por `https://`. Hoy el panel responde en `http://IP:8000`.

Secretos del repositorio que harán falta (no creados): `COOLIFY_URL`, `COOLIFY_API_TOKEN` (permisos `read` + `deploy` + `write` acotados a la aplicación de previews), `COOLIFY_PREVIEW_APP_UUID`. Variable: `PREVIEW_PIPELINE_ENABLED`.

## 8. Recursos (presupuesto por preview; concurrencia por capacidad real, no por cupo fijo)

| Servicio | RAM (`mem_limit` = `memswap_limit`) | CPU | `cpu_shares` | `oom_score_adj` |
|---|---|---|---|---|
| backend | 1024 MiB | 1.5 | 256 | 900 |
| db | 192 MiB | 0.5 | 256 | 700 |
| consola / clientes | 32 MiB cada uno | 0.2 | 128 | 600 |
| init | 16 MiB | 0.1 | — | — |
| **Total** | **1296 MiB** | | | |

Estos límites son **máximos por preview**, no consumos en reposo (el PR #384 usó ~241 MiB en reposo). El número de previews simultáneos lo decidirá en F2 la admisión dinámica con telemetría real del host (§11); la antigua regla «un solo preview activo» queda **obsoleta** y ningún archivo del repositorio debe fijar un cupo. Producción conserva prioridad: sus contenedores tienen `cpu_shares` 1024 y `oom_score_adj` por defecto. `tests/test_preview_compose.py` fija el tope y las reglas. No se afirma que quepan dos o más previews de 1 296 MiB en el servidor actual de ~3,7 GiB: solo la medición de F5 y la admisión de F2 pueden decidirlo, y nunca se ampliará ni contratará infraestructura sin autorización expresa.

## 9. Configuración de Coolify que hará falta (acción administrativa, no incluida aquí)

Aplicación nueva en «My first project → previews» con la GitHub App `auditbrain-preview-github`, rama `main`, build pack Docker Compose, `/docker-compose.preview.yml`; «Include source commit in build» activado (informativo); dominios de los tres servicios; plantilla `{{pr_id}}.{{domain}}`; «Allow Public PR Deployments» desactivado; «Enable preview deployments» desactivado mientras se use el controlador por API (V2); variables de preview de §4; «Concurrent builds» 1; limpieza de Docker diaria. DNS: `*.api.preview`, `*.consola.preview`, `*.clientes.preview` → `5.161.193.182`.

## 10. Pruebas de aceptación del primer PR

Ver el diseño `DISENO_PREVIEWS_MISMO_SERVIDOR.md` (carpeta documental): P-01 a P-15, incluidas la correspondencia imagen–commit, la verificación de redes y el aislamiento con `preview_isolation_check.sh`.

## 11. Preparación para F2: contrato `CapacityDecision` (solo documentado; nada lee el host todavía)

La admisión dinámica de F2 decidirá cuántos previews caben en el servidor actual (~3,7 GiB RAM + 4 GiB swap, compartidos con producción) **sin cupo fijo**. Cada evaluación produce una `CapacityDecision`:

| Campo | Tipo | Significado |
|---|---|---|
| `decision` | `ADMIT` · `DEFER` · `REJECT` | Admitir con reserva atómica; aplazar (`aplazado:capacidad`, reintento automático); rechazar (motivo no transitorio, p. ej. seguridad) |
| `reason_code` | `RAM_HEADROOM` · `CPU_PRESSURE` · `DISK` · `TELEMETRY_UNAVAILABLE` · `IN_FLIGHT_RESERVATION` · `SECURITY` | Causa principal; puede acompañarse de causas secundarias |
| `pr`, `head_sha` | int, SHA de 40 hex | Identidad del PR evaluado |
| `observed_at` | fecha-hora UTC | Instante de la lectura de métricas (métricas más antiguas que el umbral de frescura ⇒ `DEFER` + `TELEMETRY_UNAVAILABLE`) |
| `metrics` | objeto redaccionado | `mem_available_mib`, `headroom_existentes_mib` (Σ máx(0, L_i − U_i)), `reservas_en_vuelo_mib`, `limite_nuevo_mib` (1 296 por defecto), `reserva_seguridad_mib`, `psi_mem_some_60s`, `oom_recientes`, `disco_libre_gib`, `previews_activos`. Sin IP internas, sin métricas sensibles de producción |
| `retry_after` | segundos | Próxima evaluación sugerida (en `DEFER`) |
| `reservation_id` | opcional | Identificador `repo/pr/sha/deployment_uuid` de la reserva creada (en `ADMIT`) |

Regla de memoria (condición necesaria, no suficiente): `MemAvailable − Σ H_i − Σ L_reservas_en_vuelo − L_j ≥ R_seguridad`, con unidades en MiB, swap excluida, `R_seguridad > 0` fijada con evidencia. Además: CPU/PSI dentro de umbral, disco e inodos suficientes, sin OOM reciente, producción sana, métricas frescas. Sin telemetría o sin candado de admisión ⇒ `DEFER` (fallo cerrado). Nunca se detiene ni elimina otro preview para hacer sitio sin política administrativa aprobada. **F1 no implementa nada de esto**; el controlador antiguo (`scripts/preview_lifecycle.py`, `MAX_ACTIVE_PREVIEWS`) queda obsoleto e inactivo hasta F2.

## 12. Plantilla confiable y privilegios del despliegue (bloqueo previo a F7)

**Garantizado por el repositorio y sus pruebas:** el Compose de previews no declara `privileged`, `cap_add`, `network_mode`, `pid`/`ipc` del host, `devices`, `security_opt`, `ports` ni montajes del host (solo volúmenes nombrados), no monta `/var/run/docker.sock` y no lleva credenciales en `environment` (`tests/test_preview_compose.py`).

**Lo que Coolify 4.4.6 hace, verificado en su código:** en un despliegue de PR con build pack Docker Compose, Coolify clona la referencia del PR y **parsea el `docker-compose.preview.yml` de ese commit**. No existe un modo demostrado en 4.4.6 que fije la plantilla a una referencia protegida (por ejemplo `main`) ignorando la del PR. Por tanto, un autor con permiso de push podría modificar el Compose en su rama y pedir un despliegue con privilegios.

**Consecuencia (bloqueo documentado):** la activación automática (F7) **no debe habilitarse para código no confiable** (forks o autores no autorizados) mientras no exista uno de estos mecanismos, a implementar y probar en F2/F3 antes de F7:
1. **Verificación exacta previa al despliegue:** el reconciliador compara el `docker-compose.preview.yml` (y los Dockerfiles de preview) del `head.sha` con la versión de la referencia protegida (`main`) o con una lista de hashes aprobados, y **se niega a desplegar** si difieren, salvo etiqueta administrativa explícita (`preview:compose-aprobado`) puesta por un mantenedor tras revisión.
2. **Puerta en CI:** `preview-validate` ya ejecuta las pruebas anteriores sobre el commit del PR; un Compose privilegiado hace fallar el check. Es necesaria pero no suficiente (un check fallido no impide a Coolify desplegar si se le pide).
3. **Alcance de PRs:** solo PRs del propio repositorio, de autores autorizados; los forks no reciben secretos ni despliegue.

Un lint posterior al despliegue no sustituye nada de lo anterior. Si no se implementan (1) y (3), F7 queda bloqueada aunque la capacidad lo permita.
