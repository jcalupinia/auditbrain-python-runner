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

## 2. Mismo commit en todos los servicios (y por qué no se confía en `SOURCE_COMMIT`)

1. `preview-images` construye las tres imágenes del `head.sha` del PR en GitHub Actions y las publica con una sola etiqueta inmutable por imagen, `sha-<sha completo>` (sin `latest` ni alias). Cada imagen lleva `org.opencontainers.image.revision=<sha>` y `ENV BUILD_COMMIT=<sha>` (en los frontends, además `/build-info.json`).
2. El Compose referencia `${PREVIEW_IMAGE_TAG:?…}`: si la variable falta o está vacía, `docker compose` falla antes de arrancar nada. Coolify no aplica `:?` al recoger variables, pero Docker Compose sí al interpolar.
3. `PREVIEW_IMAGE_TAG` la fija el controlador (`scripts/preview_lifecycle.py admitir`) como variable **de preview** con el valor `sha-<head.sha>` y solo después despliega. Mientras el despliegue por API esté inhabilitado, la fija el administrador a mano en la variable de preview antes de desplegar.
4. El backend comprueba al arrancar que `PREVIEW_EXPECTED_IMAGE_TAG` (= `${PREVIEW_IMAGE_TAG}`) es exactamente `sha-<BUILD_COMMIT>`; si no, **no arranca**. Si Coolify entrega además `SOURCE_COMMIT`, también debe coincidir, pero no se depende de él.
5. Verificación en el piloto: etiqueta de imagen en `docker ps` = `head.sha` del PR = label `revision` = `build.commit` en `/api/v1/health` = `commit` en `/build-info.json` de consola y portal.

## 3. Identidad del PR y fallo seguro

- Fuente primaria única: `PREVIEW_PUBLIC_HOST=${SERVICE_FQDN_BACKEND_10000}` (la variable mágica que Coolify rellena con el dominio del preview para el servicio `backend`, puerto 10000). Fuentes de confirmación: `COOLIFY_FQDN` y, en Render, `RENDER_EXTERNAL_HOSTNAME`. Todas se normalizan (`backend/app/core/hostnames.py`) y deben coincidir.
- `backend/app/core/preview.py::preview_bootstrap()` se ejecuta al importar `app.py`. En preview exige: identidad válida y no ambigua; `DATABASE_URL` con host `db`; `CORS_ALLOW_ORIGINS` sin dominios de producción; `CLIENT_PORTAL_URL` que no sea de producción; secreto JWT legible en `PREVIEW_SECRETS_DIR`; imagen del commit esperado. Cualquier incumplimiento → log `PREVIEW: configuración inválida` y salida con código 3. No existe ningún fallback a «cualquier PR».
- CORS: `cors_origin_regex_for()` acepta únicamente `https://<n>.consola|clientes.preview.audit-ia.ec` y, mientras conviva Render, `https://auditbrain-frontend|clientes-pr-<n>.onrender.com`, con `fullmatch`, sin puerto.
- Frontends: `previewResolver.js` (idéntico en consola y portal) deriva el backend del hostname normalizado; cualquier host no reconocido deja al cliente sin backend (fallo cerrado), nunca producción.
- `/api/v1/health` expone `preview` (`active`, `provider`, `pr`, `config`) y `build.commit`.

## 4. Secretos exclusivos por preview

- `init` genera `pg_password` (40 caracteres alfanuméricos) y `jwt_secret` (64) con `/dev/urandom` dentro del volumen `secrets` del PR; si existen no los toca (persisten entre redespliegues del mismo PR; mueren con el PR).
- `db` lee `POSTGRES_PASSWORD_FILE`; el backend arma la URL de conexión en su `command` y `jwt_tokens.py` lee `jwt_secret` del volumen. Nada pasa por variables de Coolify, logs ni repositorio.
- No se usan `SERVICE_PASSWORD_*` de Coolify: se almacenan en la aplicación con `is_preview=false` y se comparten entre previews (verificado en el código fuente de Coolify 4.4.x).
- Grupo «Preview» de variables de la aplicación: `PREVIEW_ADMIN_EMAIL`, `PREVIEW_ADMIN_PASSWORD`, `PREVIEW_API_KEY` (valores nuevos de prueba) y `PREVIEW_IMAGE_TAG`. Sin proveedores de IA, correo, Stripe, OCR ni Canva. Nunca valores de producción.

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

Verificación en el piloto: `scripts/preview_isolation_check.sh` dentro del backend del preview (intenta conexiones TCP a los objetivos de producción y espera que todas fallen) y `docker inspect` de los cinco contenedores para anotar en qué redes quedan (P-08). El Compose define `preview_internal` (`internal: true`) para `init` y `db`; si Coolify sobrescribe las redes, se registra y manda la regla DOCKER-USER.

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
| `preview-lifecycle.yml` | Solo `workflow_dispatch` | `PREVIEW_PIPELINE_ENABLED`; `COOLIFY_URL` debe ser `https://`; `dry_run=true` por defecto | `admitir` (cupo `MAX_ACTIVE_PREVIEWS=1`, imágenes presentes, crear sin desplegar, fijar etiqueta, desplegar, comentar), `liberar`, `caducidad` (3 días sin commit, comentario humano ni despliegue; `preview:keep` exime) |

El despliegue por API queda **inhabilitado** hasta que el panel de Coolify tenga un dominio HTTPS: el script aborta ante una `COOLIFY_URL` que no empiece por `https://`. Hoy el panel responde en `http://IP:8000`.

Secretos del repositorio que harán falta (no creados): `COOLIFY_URL`, `COOLIFY_API_TOKEN` (permisos `read` + `deploy` + `write` acotados a la aplicación de previews), `COOLIFY_PREVIEW_APP_UUID`. Variable: `PREVIEW_PIPELINE_ENABLED`.

## 8. Recursos (un solo preview activo)

| Servicio | RAM (`mem_limit` = `memswap_limit`) | CPU | `cpu_shares` | `oom_score_adj` |
|---|---|---|---|---|
| backend | 1024 MiB | 1.5 | 256 | 900 |
| db | 192 MiB | 0.5 | 256 | 700 |
| consola / clientes | 32 MiB cada uno | 0.2 | 128 | 600 |
| init | 16 MiB | 0.1 | — | — |
| **Total** | **1296 MiB** | | | |

Producción conserva prioridad: sus contenedores tienen `cpu_shares` 1024 y `oom_score_adj` por defecto. `tests/test_preview_compose.py` fija el tope y las reglas. Ampliar a dos previews exige medir con uno activo y una nueva decisión.

## 9. Configuración de Coolify que hará falta (acción administrativa, no incluida aquí)

Aplicación nueva en «My first project → previews» con la GitHub App `auditbrain-preview-github`, rama `main`, build pack Docker Compose, `/docker-compose.preview.yml`; «Include source commit in build» activado (informativo); dominios de los tres servicios; plantilla `{{pr_id}}.{{domain}}`; «Allow Public PR Deployments» desactivado; «Enable preview deployments» desactivado mientras se use el controlador por API (V2); variables de preview de §4; «Concurrent builds» 1; limpieza de Docker diaria. DNS: `*.api.preview`, `*.consola.preview`, `*.clientes.preview` → `5.161.193.182`.

## 10. Pruebas de aceptación del primer PR

Ver el diseño `DISENO_PREVIEWS_MISMO_SERVIDOR.md` (carpeta documental): P-01 a P-15, incluidas la correspondencia imagen–commit, la verificación de redes y el aislamiento con `preview_isolation_check.sh`.
