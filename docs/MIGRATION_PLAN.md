# Plan de Migración — AuditBrain Platform

## Fase 1 (ESTA ENTREGA) — Estructura paralela aditiva

- [x] Estructura `backend/` (core, security, services, document_services,
      router_engine, api).
- [x] `python_runner_service` encapsula el subproceso hacia
      `auditbrain_exec_runner.py` (intocado).
- [x] `universal_document_client` encapsula el servicio documental externo.
- [x] Master Router con targets operativos y stubs futuros.
- [x] API versionada `/api/v1/*`.
- [x] API Key mínima **gated por entorno** (desactivada por defecto).
- [x] Compatibilidad total con `/run_python` legacy.
- [x] Tests básicos (9) verdes.
- [x] Sin cambios en deployment (Dockerfile / render.yaml / runtime.txt).

## Deuda técnica conocida (intencional en fase 1)

La orquestación del subproceso y el armado de payloads documentales están
**replicados** entre `app.py` (legacy) y `backend/` (v1). Es deliberado
para mantener la dependencia en una sola dirección y no acoplar la
plataforma al legacy. Riesgo: *drift* si se modifica uno y no el otro.

## Fase 2 (FUTURA) — Consolidación

- [ ] Refactorizar `/run_python` legacy para delegar en
      `python_runner_service` (elimina la duplicación).
- [ ] Migrar el bloque documental de `app.py` a
      `universal_document_client`.

## Fase 3 (FUTURA) — Endurecimiento y deploy

- [ ] Sandbox real de ejecución (límites de recursos, red/FS).
- [ ] Activar API Key en producción (definir `AUDITBRAIN_API_KEY` y
      actualizar configuración de los GPTs).
- [ ] Cambiar entrypoint de deploy a la app de plataforma si procede.

## Fase 4 (FUTURA) — No incluido aún

- [ ] Frontend (`frontend/`).
- [ ] Integración LLM (OpenAI / Claude).
- [ ] Módulos `future_*` con lógica real.
