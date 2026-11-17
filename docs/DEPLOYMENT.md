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

## NIIF 18 Studio — Biblioteca Normativa (build arg)

Las normas de la IFRS Foundation y los modelos de estados financieros de EY,
KPMG, PwC, Deloitte y Grant Thornton **no están en este repositorio, que es
público**. La imagen los trae durante el build desde el repositorio privado
`jcalupinia/herramienta-niif-18` y quedan dentro de la imagen, que se
construye y permanece en nuestro servidor.

En Coolify, en la aplicación `auditbrain-backend`, sección **Build** →
*Build Arguments*:

| Build arg | Valor | ¿Obligatorio? |
|---|---|---|
| `NIIF18_REPO_TOKEN` | token de GitHub de **grano fino, solo lectura**, limitado a `herramienta-niif-18` | Sí, para que el módulo NIIF funcione |
| `NIIF18_REF` | `main` | No (por defecto `main`) |
| `NIIF18_REPO` | `jcalupinia/herramienta-niif-18` | No (ya es el valor por defecto) |

No hace falta definir `NIIF18_BIBLIOTECA_DIR`: el código usa por defecto
`/app/base-normativa/libro`, que es donde el Dockerfile deja la biblioteca.
Esa variable queda solo para entornos donde la biblioteca viva en otro sitio
(por ejemplo un volumen persistente).

**Si el token falta o falla, el build NO se rompe**: la imagen queda sin
biblioteca y el módulo NIIF responde 503 con un mensaje claro, igual que Forge
o el Motor de Ingesta cuando no pueden montarse. El resto de la plataforma
arranca normalmente. En el log del build se ve `AVISO NIIF 18: …` o
`ERROR NIIF 18: …`.

> **Contrapartida conocida:** un build arg queda registrado en el
> `docker history` de la imagen. Por eso el token debe ser de grano fino, de
> solo lectura y limitado a ese único repositorio: su alcance es exactamente
> el contenido que la imagen ya lleva dentro. Se eligió build arg —y no un
> secreto de BuildKit— porque funciona con o sin BuildKit y así el build no
> depende de esa capacidad de Coolify. Si se confirma que el builder soporta
> secretos, puede endurecerse cambiando el bloque del `Dockerfile.render` por
> `RUN --mount=type=secret,id=niif18_token`.

Comprobación tras desplegar (con un usuario **operador**, que no necesita
entitlement):

```bash
# Catálogo de normas -> 200
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
  https://api.audit-ia.ec/api/v1/client/niif18/normas
```

Si responde **503**, la imagen se construyó sin el token.

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
