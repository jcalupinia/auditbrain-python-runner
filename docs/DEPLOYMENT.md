# Despliegue de AuditBrain (Hetzner + Coolify)

> **Arquitectura vigente (verificada 2026-10-29).** Producción corre en un
> servidor **Hetzner** administrado con **Coolify** (proxy Traefik). **Render ya
> no se usa**; el antiguo `render.yaml` se retiró del repositorio. La
> configuración operativa (variables, dominios, planes, base de datos) vive **en
> Coolify**, no versionada en el repo.

## Aplicaciones en Coolify (proyecto, rama, dominio)

| App Coolify | Rama | Build | Dominio público |
|---|---|---|---|
| `auditbrain-backend` | `main` | Docker (`Dockerfile.render`) | `https://api.audit-ia.ec` |
| `auditbrain-frontend` (consola) | `main` | nixpacks | `https://consola.audit-ia.ec` |
| `auditbrain-portal-clientes` | `coolify-hetzner` | Docker | `https://clientes.audit-ia.ec` |
| `auditbrain-recursos` | `main` | static | `https://recursos.audit-ia.ec` |
| `auditbrain-preview` | `main` | docker compose | Previews por PR (`<n>.api|consola|clientes.preview.audit-ia.ec`) |

> El backend se construye desde `Dockerfile.render` (el nombre es **legado**; la
> imagen es la de producción en Coolify, no Render). Expone el puerto `10000`.

## Despliegue de producción: automático en `main`

- `auditbrain-backend` tiene **`is_auto_deploy_enabled: true`** en Coolify: un
  **push/merge a `main`** dispara, vía webhook de GitHub, un **redespliegue
  automático** de producción (build de la imagen + rolling update). **No es
  manual.** Lo mismo aplica al frontend/consola (rama `main`).
- El portal de clientes sigue la rama **`coolify-hetzner`** (no `main`).
- Previews por PR: los gestiona el controlador del repo
  (`scripts/preview_lifecycle.py` + workflows `preview-images`/`preview-deploy`),
  con admisión por capacidad y aislamiento por PR. Ver `docs/previews-coolify.md`.

> Implicación al fusionar: cualquier merge a `main` **redespliega producción**.
> Revisa el diff con cuidado y fusiona en ventana controlada.

## Variables de entorno (se definen en Coolify, nunca en el repo)

Mínimas del backend (valores en Coolify → app `auditbrain-backend` → Environment,
como secretos cuando corresponda):

| Variable | Obligatoria | Notas |
|---|---|---|
| `AUDITBRAIN_API_KEY` | Sí | Sin ella el runner server-a-servidor queda abierto. GPTs envían `X-API-Key`. |
| `AUDITBRAIN_JWT_SECRET` | Sí | Firma de los JWT; sin él se usa uno de dev inseguro. |
| `DATABASE_URL` | Sí | Postgres de producción (gestionado en Coolify). |
| `CORS_ALLOW_ORIGINS` | No | Orígenes del frontend; vacío = CORS inerte. |
| `DOCUMENT_SERVICE` | Sí | URL del servicio documental (`universal-creador-documentos`, en Coolify). |
| `ANTHROPIC_API_KEY` / `ICT_LLM_MODEL` | Según IA | Ver la sección de IA en `CLAUDE.md`. |
| `AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` | Recom. | Admin inicial al primer arranque. |

> El esquema de BD se crea con `create_all` + migraciones aditivas al arrancar.

## NIIF 18 Studio — Biblioteca Normativa (volumen persistente)

Las normas de la IFRS Foundation y los modelos de estados financieros de EY,
KPMG, PwC, Deloitte y Grant Thornton **no están en este repositorio, que es
público**, y **tampoco van dentro de la imagen**: se montan como **volumen
persistente** del servidor.

> **Por qué así.** Traerlos durante el build exigía un token de GitHub, y en
> Coolify una credencial de build solo puede viajar como *build arg*, que queda
> registrado en `docker history` de la imagen. Con el volumen **no hay ninguna
> credencial en el build**: nada que filtrar, nada que rotar y ninguna
> advertencia del linter de Docker. El contenido con licencia restringida vive
> solo en el disco del servidor.

### 1. Copiar la biblioteca al servidor (una sola vez)

Desde su máquina, en el clon del repositorio privado `herramienta-niif-18`:

```bash
ssh root@<servidor> 'mkdir -p /datos/niif18'
```

```bash
scp -r base-normativa/libro base-normativa/manifiesto.json root@<servidor>:/datos/niif18/
```

Debe quedar así en el servidor:

```
/datos/niif18/manifiesto.json
/datos/niif18/libro/index.html
/datos/niif18/libro/normas/            (120 archivos)
/datos/niif18/libro/modelos-niif18/    (EY, KPMG)
/datos/niif18/libro/modelos-2026/      (Deloitte x2, Grant Thornton, KPMG)
```

Compruébelo:

```bash
ssh root@<servidor> 'find /datos/niif18 -type f | wc -l'   # debe dar 129
```

### 2. Montar el volumen en Coolify

En `auditbrain-backend` → **Persistent Storage** → *Add volume*:

| Campo | Valor |
|---|---|
| Source (host) | `/datos/niif18` |
| Destination (contenedor) | `/app/base-normativa` |

**No hace falta ninguna variable de entorno.** El código busca por defecto
`/app/base-normativa/libro`, que es justo donde queda el volumen. Solo si lo
monta en otra ruta hay que definir `NIIF18_BIBLIOTECA_DIR` apuntando a la
carpeta `libro`.

El volumen **persiste entre redespliegues**: el paso 1 se hace una sola vez.

### 3. Si el volumen no está

El módulo NIIF responde **503** con un mensaje claro y **el resto de la
plataforma arranca igual**, como Forge o el Motor de Ingesta cuando no pueden
montarse. Una pieza opcional no tumba el servicio.

### 4. Comprobación tras desplegar

Con un usuario **operador** (no necesita entitlement):

```bash
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
  https://api.audit-ia.ec/api/v1/client/niif18/normas
```

**200** = biblioteca montada. **503** = falta el volumen o está mal la ruta.

### 5. Actualizar la biblioteca más adelante

Se repite el paso 1 (el `scp` sobrescribe) y se reinicia la aplicación. No hace
falta reconstruir la imagen: el contenido no vive en ella.

## Verificación post-deploy

```bash
BASE=https://api.audit-ia.ec

# Health (sin auth) -> 200
curl -s "$BASE/api/v1/health"

# Runner SIN key -> 401 (auth activa)
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE/api/v1/python/run" \
  -H "Content-Type: application/json" -d '{"script":"result=1"}'

# Runner CON key -> 200
curl -s -X POST "$BASE/api/v1/python/run" \
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d '{"script":"result={\"ok\":True}"}'
```

## Sandbox Tier 0 — knobs opcionales

El subproceso que ejecuta código de los GPTs no recibe `AUDITBRAIN_API_KEY` ni
secretos. Los límites de recursos son **opt-in** (0 = sin límite):
`AUDITBRAIN_RLIMIT_AS_MB`, `AUDITBRAIN_RLIMIT_CPU_SECONDS`,
`AUDITBRAIN_RLIMIT_FSIZE_MB`, `AUDITBRAIN_RLIMIT_NPROC`,
`AUDITBRAIN_RLIMIT_NOFILE`, `AUDITBRAIN_JOB_TTL_SECONDS`,
`AUDITBRAIN_SANDBOX_STRICT_ENV`. Es endurecimiento, no una frontera de
aislamiento real.

## GPTs

Todos los endpoints exigen `X-API-Key`. Apunta cada GPT al backend de producción
(`https://api.audit-ia.ec`) con su header `X-API-Key`.
