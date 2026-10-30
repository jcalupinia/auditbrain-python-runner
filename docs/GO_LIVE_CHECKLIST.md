# Checklist GO-LIVE — AuditBrain (solo backend)

## Bloqueantes (NO salir a producción sin esto)

- [ ] `AUDITBRAIN_API_KEY` definida en Coolify (secreto, valor robusto).
- [ ] Verificado: `POST /api/v1/python/run` sin key → **401**.
- [ ] Verificado: `POST /api/v1/python/run` con key → **200**.
- [ ] Verificado: `POST /run_python` (legacy) sin key → **401**.
- [ ] Los 4 GPTs actualizados para enviar `X-API-Key`.
- [ ] Build en Coolify completado sin OOM (imagen `Dockerfile.render`).

## Funcional

- [ ] `GET /` → 200 (health check en verde en Coolify).
- [ ] `GET /api/v1/health` → 200, `auth_enabled: true`.
- [ ] `POST /api/v1/router/execute` con `target=python_runner` → 200.
- [ ] `target=future_*` → 501 (stub esperado).
- [ ] `POST /api/v1/documents/generate` (excel/pptx) → llega al
      servicio externo y responde URL o error controlado.
- [ ] `DOCUMENT_SERVICE` accesible desde el backend (probar un formato).

## Seguridad (estado conocido)

- [ ] Aceptado y documentado: el runner ejecuta Python arbitrario; la
      única barrera en esta fase es la API Key (sin sandbox real —
      ver `SECURITY_NOTES.md`, mitigación en roadmap).
- [ ] API Key NO versionada (solo en Coolify → Environment).
- [ ] `CORS_ALLOW_ORIGINS` configurado solo si hay frontend; si no,
      dejar vacío (inerte).
- [ ] Logs de Coolify revisados: sin warning "Plataforma v1 no montada".

## Operación

- [ ] Auto-deploy de Coolify confirmado en `auditbrain-backend` (push a `main` redespliega).
- [ ] Recursos del servidor Hetzner dimensionados para la carga esperada.
- [ ] Rollback claro: revertir al commit previo / branch `main`.
- [ ] Backup de referencia: rama `backup-before-auditbrain-platform`.

## Fuera de alcance esta fase (ver ROADMAP_FULLSTACK.md)

- [ ] Frontend · JWT · PostgreSQL · uploads · sandbox real → roadmap.
