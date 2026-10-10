# Entrega a integración en el Command Center

Superada la puerta de calidad, la herramienta pasa a Claude Code para integrarse en el Command Center de AUDIT-IA. Probar el Excel no es integrar, y escribir el código de integración no es desplegar (M01).

Preparar el paquete de entrega —sin él la integración reconstruye criterios por su cuenta—:

1. **Artefacto validado**: archivo, versión, huella SHA-256 y fecha. Es la autoridad numérica de la integración.
2. **Especificación aprobada**: entradas, reglas con fórmula, unidades y redondeo, cédulas, controles y parámetros.
3. **Recorrido de prueba**: casos con datos ficticios ya ejecutados —entradas, resultado esperado y obtenido— incluidos cero, negativo, duplicado, denominador cero y moneda distinta.
4. **Contrato técnico** mapeado a las entidades del manual §15: EngagementContext, ToolDefinition, SourceRequirement, Evidence/Dataset, NormativeReference, Rule/Run, ScheduleResult, Artifact/Cleanup.
5. **Pendientes declarados**: normas sin consultar, formatos sin lector probado, políticas de retención sin confirmar.

Exigencias de la integración: inspeccionar el repositorio real antes de escribir código, sin asumir rutas por analogía; motor determinista en Python como autoridad del servidor; si hay cálculo en navegador o en HTML portátil, las tres copias dan el mismo dígito y la divergencia bloquea la ejecución; paridad dígito a dígito con el artefacto validado; backend y UI comparten las mismas condiciones de obligatoriedad; toda fuente anunciada tiene lector probado y consumidor real; toda hoja generada es localizable desde un índice; firma, cliente, período, visita y corte se propagan a todos los entregables; ningún TTL por defecto; solo datos ficticios en el repositorio; plan aprobado antes del código.

El prompt completo para Claude Code y los criterios de aceptación están en `metodologia/Prompt_integracion_command_center.md`.

## Contrato de un procesador especializado (M18)

Cuando el cálculo exige procesador, la entrega incluye lo que el Command Center necesita para instalarlo en la ficha:

- `CAMPOS` por tipo de anexo (clave, etiqueta, tipo, obligatoria, alias) → de ahí salen los modelos Excel para el cliente.
- `TIPOS` / `DATASETS`: un anexo por requerimiento de cálculo (`dataset` en el requerimiento) y cuál es la población
  principal que se concilia con el mayor.
- `PARAMETROS` con valores por defecto y cuáles admiten negativos; etiquetas para la pantalla.
- `ejecutar(datasets, parámetros, corte)` determinista → filas, totales con etiquetas, resultado principal, problemas.
- `hojas(resultado)`: cédulas con celdas `{"f": fórmula, "v": valor}` para el Excel con fórmulas (M20, M21).
- `definicion()` de la ficha (base técnica, NIA, programa, requerimientos, `frameworks`, `calculo` legible) y
  `EJEMPLO` = el ejemplo numérico de la ficha (M19).
