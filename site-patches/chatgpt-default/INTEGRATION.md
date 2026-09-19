# Integración del cambio en AuditBrain Site

## Destino verificado

- Project id conocido: `appgprj_6aac4365f6288191a6d65fea99a71373`
- Slug observado: `auditbrain-auditoria`
- Regla: verificar nuevamente id/versión antes de publicar.

## Cambio

Sustituir cualquier acción que envíe **Trabajar en ChatGPT** hacia Work/Codex/Astra por el flujo de este paquete:

1. Construir `AUDITBRAIN_HANDOFF_INPUT` con el contexto mínimo de la herramienta activa.
2. Mantener `chatgpt: true` como ruta predeterminada cuando Chat normal esté disponible.
3. Consultar o recibir disponibilidad real de Work/Codex/Astra; si no hay una API verificable, tratarlos como opcionales sin prometer disponibilidad.
4. `Trabajar en ChatGPT` prepara/copia el contexto portable. No debe crear una tarea Work ni invocar Codex/Astra.
5. Si en el futuro Sites expone una acción verificada para abrir un chat normal con payload, reemplazar solamente el adaptador de salida; conservar `handoff.mjs`.

## Estado

Este paquete implementa la lógica y el contrato. **No constituye evidencia de que el Site publicado ya fue modificado.** La publicación requiere una capacidad de escritura sobre el proyecto Site y una verificación posterior de la versión publicada.

## Rollback

Revertir únicamente el selector/handoff visual. No revertir metodología v1.2.0, motores Python, archivos de clientes ni entregables existentes. Mientras el runtime anterior continúe activo, marcarlo como no conforme con v1.2.0 en la ficha de despliegue.
