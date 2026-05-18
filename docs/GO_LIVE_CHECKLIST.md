# Checklist GO-LIVE — AuditBrain (solo backend)

## Bloqueantes (NO salir a producción sin esto)

- [ ] `AUDITBRAIN_API_KEY` definida en Render (secreto, valor robusto).
- [ ] Verificado: `POST /api/v1/python/run` sin key → **401**.
- [ ] Verificado: `POST /api/v1/python/run` con key → **200**.
- [ ] Verificado: `POST /run_python` (legacy) sin key → **401**.
- [ ] Los 4 GPTs actualizados para enviar `X-API-Key`.
- [ ] Build de Render completado sin OOM (vigilar plan starter).

## Funcional

- [ ] `GET /` → 200 (health check de Render en verde).
- [ ] `GET /api/v1/health` → 200, `auth_enabled: true`.
- [ ] `POST /api/v1/router/execute` con `target=python_runner` → 200.
- [ ] `target=future_*` → 501 (stub esperado).
- [ ] `POST /api/v1/documents/generate` (excel/pptx) → llega al
      servicio externo y responde URL o error controlado.
- [ ] `DOCUMENT_SERVICE` accesible desde Render (probar un formato).

## Seguridad (estado conocido)

- [ ] Aceptado y documentado: el runner ejecuta Python arbitrario; la
      única barrera en esta fase es la API Key (sin sandbox real —
      ver `SECURITY_NOTES.md`, mitigación en roadmap).
- [ ] API Key NO versionada (solo en dashboard, `sync:false`).
- [ ] `CORS_ALLOW_ORIGINS` configurado solo si hay frontend; si no,
      dejar vacío (inerte).
- [ ] Logs de Render revisados: sin warning "Plataforma v1 no montada".

## Operación

- [ ] `autoDeploy` confirmado (o desactivado si se prefiere deploy manual).
- [ ] Plan de Render dimensionado para la carga esperada.
- [ ] Rollback claro: revertir al commit previo / branch `main`.
- [ ] Backup de referencia: rama `backup-before-auditbrain-platform`.

## Fuera de alcance esta fase (ver ROADMAP_FULLSTACK.md)

- [ ] Frontend · JWT · PostgreSQL · uploads · sandbox real → roadmap.
