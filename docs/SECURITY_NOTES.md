# Notas de Seguridad — AuditBrain Platform v1

## Riesgo principal (preexistente, NO resuelto en fase 1)

El servicio ejecuta **código Python arbitrario** vía `exec()` en
`auditbrain_exec_runner.py`. El aislamiento es solo un subproceso con
timeout: NO hay sandbox real (sin límites de CPU/memoria, con acceso a
red y sistema de archivos). Cualquiera que pueda invocar el endpoint
tiene ejecución remota de código en el contenedor.

Mitigación real planificada en Fase 3 (ver `MIGRATION_PLAN.md`).

## API Key — diseño "gated"

- Variable de entorno: `AUDITBRAIN_API_KEY`.
- **Vacía o ausente (estado actual/por defecto)** → autenticación
  DESACTIVADA. El comportamiento es idéntico al legacy; los GPTs
  existentes siguen funcionando sin cambios.
- **Definida** → se exige el header `X-API-Key` con el valor exacto en
  `/run_python` (legacy) y en `/api/v1/{router,python,documents}`.
- `/api/v1/health` nunca requiere auth.

### Al activar en producción (Fase 3)

Definir `AUDITBRAIN_API_KEY` **romperá** los GPTs que no envíen el
header. Antes de activarla hay que actualizar la configuración de cada
GPT para incluir `X-API-Key`. Es una decisión explícita del operador;
nada cambia hasta entonces.

## Buenas prácticas ya aplicadas

- `/resultados/{filename}` valida `os.path.basename` (anti path traversal).
- Import de la plataforma es defensivo: un fallo en `backend/` no tumba
  el servicio legacy.
- `requirements-dev.txt` separado: las dependencias de test no entran a
  la imagen de producción.
