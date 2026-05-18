# Arquitectura — AuditBrain Platform v1

## Principio rector

Migración **aditiva y reversible**. El servicio legacy (`app.py` +
`auditbrain_exec_runner.py`) sigue siendo el entrypoint de producción
(`uvicorn app:app`). La plataforma v1 vive bajo `backend/` y se *monta*
sobre la app existente sin reemplazarla.

## Componentes

```
app.py                         # Legacy + montaje aditivo de api_router (defensivo)
auditbrain_exec_runner.py      # Motor de ejecución real (INTOCADO)
backend/app/
  core/config.py               # Settings centralizados (espejo de env vars legacy)
  security/api_key.py           # Auth mínima por API Key (gated por entorno)
  services/python_runner_service.py        # Orquesta el subproceso del runner
  document_services/universal_document_client.py  # Cliente servicio documental
  router_engine/master_router.py           # Despacho por 'target'
  api/                          # Routers FastAPI /api/v1/*
```

## API v1

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET  | `/api/v1/health` | No | Estado de la plataforma |
| POST | `/api/v1/router/execute` | API Key (gated) | Master Router |
| POST | `/api/v1/python/run` | API Key (gated) | Ejecuta código Python |
| POST | `/api/v1/documents/generate` | API Key (gated) | Genera documento |

## Master Router — targets

- Operativos: `python_runner`, `document_generator`
- Stubs (501): `future_audit_module`, `future_tax_module`,
  `future_legal_module`, `future_finance_module`,
  `future_marketing_module`, `future_creative_module`

## Compatibilidad legacy

- `/`, `/run_python`, `/resultados/{filename}` intactos.
- El montaje de la plataforma es defensivo: si `backend/` falla al
  importar, se loguea un warning y el legacy sigue sirviendo.
