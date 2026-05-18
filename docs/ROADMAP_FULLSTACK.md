# Roadmap Full-Stack — AuditBrain (NO construido aún)

Documento de planificación. Nada de esto está implementado; cada punto
es una **feature nueva** que requiere aprobación explícita (regla
"solo hardening/deployment" de la Fase Operativa).

## Estado actual (lo que SÍ existe)

- Backend FastAPI: `/api/v1/{health,router/execute,python/run,documents/generate}`
  + legacy `/run_python`.
- Auth: API Key simple (gated). Sin usuarios ni sesiones.
- Persistencia: ninguna (no hay base de datos).
- Frontend: ninguno.

## Fase F1 — Seguridad real del runner (prioritaria)

- Sandbox de ejecución: límites CPU/memoria, sin red, FS efímero
  aislado (gVisor / nsjail / contenedor por job).
- Allowlist de imports o ejecución en worker desechable.
- Rate limiting por API Key.

## Fase F2 — Autenticación JWT

- Modelo de usuarios, login, emisión/validación de JWT.
- Sustituir/复合 API Key por roles (admin, gpt, viewer).
- Requiere persistencia (ver F3).

## Fase F3 — PostgreSQL

- `sqlalchemy` ya está en `requirements.txt` pero **sin uso**.
- Definir esquema (usuarios, jobs, auditoría de ejecuciones).
- Servicio `pserv`/DB en Render + `DATABASE_URL` + migraciones (Alembic).
- Conexión async (asyncpg) y pool.

## Fase F4 — Frontend

- App web (p. ej. React/Vite) en `frontend/`.
- Consumo de `/api/v1/*` con JWT.
- Desplegar como **Static Site** en Render; configurar
  `CORS_ALLOW_ORIGINS` con su dominio.
- Pantallas: login, ejecutar análisis, ver/descargar entregables.

## Fase F5 — Uploads y entregables

- Endpoint de subida (`UploadFile`) con validación de tipo/tamaño.
- Almacenamiento (disco persistente de Render u objeto externo).
- Ciclo de vida/expiración de `resultados/`.

## Dependencias entre fases

```
F1 (seguridad)  -> independiente, hacer YA antes de tráfico real
F3 (Postgres)   -> requisito de F2
F2 (JWT)        -> requisito de F4
F4 (frontend)   -> requiere F2 + CORS
F5 (uploads)    -> independiente; idealmente tras F1
```

Recomendación: **F1 antes de cualquier exposición pública seria**; el
resto según prioridad de producto.
