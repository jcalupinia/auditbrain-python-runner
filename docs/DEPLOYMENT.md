# Despliegue en Render — AuditBrain (Fase Operativa)

> Alcance real: **solo backend FastAPI**. No hay frontend, PostgreSQL ni
> JWT en el repositorio (ver `ROADMAP_FULLSTACK.md`). Excel/PPTX se
> generan en el **servicio externo** `DOCUMENT_SERVICE`, no aquí.

## 0. Pre-requisitos

- Cuenta en Render con acceso al repo `jcalupinia/auditbrain-python-runner`.
- Decidir el valor de `AUDITBRAIN_API_KEY` (cadena larga aleatoria; p. ej.
  `openssl rand -hex 32`). **Guárdala**: tus GPTs deberán enviarla.

## 1. Crear el servicio

1. Render Dashboard → **New** → **Blueprint**.
2. Conecta el repo y selecciona la rama del PR (`claude/auditbrain-platform-v1-Xh3Ji`)
   o `main` tras el merge.
3. Render detecta `render.yaml`. Confirma el servicio `auditbrain-python-runner`.

### Build / Start (definidos en render.yaml)

- **Build command**:
  ```
  pip install --upgrade pip setuptools wheel
  pip install -r requirements.txt
  ```
- **Start command**:
  ```
  uvicorn app:app --host 0.0.0.0 --port 10000
  ```
- **Python**: 3.12.3 · **Health check**: `/`

> ⚠️ `requirements.txt` incluye dependencias muy pesadas (torch,
> transformers, dask, great_expectations). En el plan **starter** el
> build puede tardar mucho o agotar memoria. Si el build falla por OOM,
> sube de plan temporalmente para el primer deploy. (Reducir
> dependencias sería un cambio de alcance, fuera de esta fase.)

## 2. Variables de entorno

| Variable | Origen | Obligatoria | Notas |
|---|---|---|---|
| `AUDITBRAIN_API_KEY` | Dashboard (secreto, `sync:false`) | **SÍ** | Sin ella el endpoint de ejecución queda abierto a RCE |
| `CORS_ALLOW_ORIGINS` | Dashboard (`sync:false`) | No | Dominios del frontend separados por coma; vacío = CORS inerte |
| `DOCUMENT_SERVICE` | render.yaml | Sí | URL del servicio documental |
| `EXECUTION_TIMEOUT_SECONDS` | render.yaml | Sí | 300 |
| `EXECUTION_CONCURRENCY` | render.yaml | Sí | 1 |
| `AUDITBRAIN_MAX_STREAM_CHARS` | render.yaml | Sí | 200000 |
| `AUDITBRAIN_RESPONSE_MODE` | render.yaml | Sí | compact |
| `AUDITBRAIN_MAX_RESPONSE_TEXT_CHARS` | render.yaml | Sí | 4000 |

**Definir el secreto**: Dashboard → servicio → **Environment** →
`AUDITBRAIN_API_KEY` = (tu valor) → Save → Deploy.

### Sandbox Tier 0 (F1) — knobs opcionales

El subproceso que ejecuta código de los GPTs ya **no recibe**
`AUDITBRAIN_API_KEY` ni secretos (scrub automático, sin configurar nada).
Los límites de recursos son **opt-in** (0 = sin límite) para no romper
cargas pandas/numpy; actívalos según el tamaño de la instancia:

| Variable | Default | Recomendado | Efecto |
|---|---|---|---|
| `AUDITBRAIN_RLIMIT_AS_MB` | 0 | ~70% de la RAM de la instancia | Memoria máx. del script (evita OOM del servicio) |
| `AUDITBRAIN_RLIMIT_CPU_SECONDS` | 0 | ~`EXECUTION_TIMEOUT_SECONDS` | Segundos de CPU (corta bucles de cómputo) |
| `AUDITBRAIN_RLIMIT_FSIZE_MB` | 0 | 100–200 | Tamaño máx. de archivo generado |
| `AUDITBRAIN_RLIMIT_NPROC` | 0 | alto si se activa | Anti fork-bomb (ojo: cuenta procesos del uid) |
| `AUDITBRAIN_RLIMIT_NOFILE` | 0 | 256 | Descriptores de archivo |
| `AUDITBRAIN_JOB_TTL_SECONDS` | 3600 | 3600 | Antigüedad para purgar jobs viejos |
| `AUDITBRAIN_SANDBOX_STRICT_ENV` | 0 | 1 (si los scripts no leen env) | Pasa allowlist mínima en vez de denylist |

> Tier 0 es endurecimiento, **no** una frontera de aislamiento real
> (eso es Tier 2: WASM/microVM, ver `docs/ROADMAP_FULLSTACK.md`).

## 3. Verificación post-deploy

Sustituye `BASE` por la URL pública de Render y `KEY` por tu API key.

```bash
# Health (sin auth) — debe devolver 200
curl -s BASE/api/v1/health

# Auth activa: SIN key -> 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST BASE/api/v1/python/run \
  -H "Content-Type: application/json" -d '{"script":"result=1"}'

# CON key -> 200
curl -s -X POST BASE/api/v1/python/run \
  -H "Content-Type: application/json" -H "X-API-Key: KEY" \
  -d '{"script":"result={\"ok\":True}"}'

# Router inteligente -> 200
curl -s -X POST BASE/api/v1/router/execute \
  -H "Content-Type: application/json" -H "X-API-Key: KEY" \
  -d '{"target":"python_runner","payload":{"script":"result=21*2"}}'

# Documentos (Excel) -> reenvía al servicio externo
curl -s -X POST BASE/api/v1/documents/generate \
  -H "Content-Type: application/json" -H "X-API-Key: KEY" \
  -d '{"result":{"Ingresos":1000},"output_expectations":{"format":"excel"}}'

# Legacy (tus GPTs): ahora EXIGE la key
curl -s -o /dev/null -w "%{http_code}\n" -X POST BASE/run_python \
  -H "Content-Type: application/json" -d '{"script":"result=1"}'   # 401 esperado
```

## 4. Actualizar los GPTs (acción obligatoria)

Al activar `AUDITBRAIN_API_KEY`, **todos** los endpoints (incluido el
legacy `/run_python`) exigen el header `X-API-Key`. Edita la
configuración de cada GPT (AuditSmart, Audit Advisor, H&G Abogados, GPT
Maestro) para enviar `X-API-Key: <tu key>`. Sin esto, dejarán de
funcionar (esperado por diseño de seguridad).
