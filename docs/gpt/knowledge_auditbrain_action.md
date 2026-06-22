# Guía AuditBrain — Cómo usar las acciones skillRun y runPython

> Documento de referencia para los GPTs del ecosistema Audit Consulting IA Suite.
> El comportamiento principal va en las Instructions del GPT; este documento amplía
> el detalle (cuándo usar cada acción, módulos y ejemplos).

## Qué es AuditBrain
El servidor `auditbrain-python-runner.onrender.com` es el "cerebro" del ecosistema.
Contiene 54 skills con prompts oficiales y ejecuta el razonamiento server-side, así
los tokens NO se gastan en la página del GPT. El GPT solo orquesta y presenta.

## Acción 1 — skillRun (POST /api/v1/skill_run)  →  el cerebro
Úsala para: análisis experto, redacción de informes, dictámenes, estrategias,
interpretación de datos, recomendaciones profesionales.

Parámetros:
- `module_code` (obligatorio en la práctica): el módulo del GPT. Ver tabla abajo.
- `input` (obligatorio): la tarea del usuario con TODO el contexto (datos, cifras, objetivo).
- `skill_id` (opcional): slug exacto de una skill. Si se omite, el servidor elige la
  skill por defecto del módulo. **Recomendado: omitirlo** y dejar que el servidor decida.

Qué devuelve: el campo `output` (texto ya elaborado). Muéstralo al usuario tal cual.

## Acción 2 — runPython (POST /run_python)  →  el motor
Úsala para: cálculos con datos, tablas, métricas financieras, y generar entregables
(Excel con openpyxl/xlsxwriter, gráficos con matplotlib/plotly).

Parámetros:
- `script` (obligatorio): código Python. **Asigna el resultado a la variable `result`.**
  Los datos de entrada están disponibles como la variable `inputs` (un dict).
- `inputs` (opcional): diccionario de datos accesible dentro del script.
- `output_expectations.send_to_document_service: true` (opcional): para generar un
  archivo descargable (delega al Universal Creador de Documentos).

Qué devuelve: `result` (el valor de tu variable), `stdout`, `stderr`, y `document_service`
(URL del archivo si se generó).

## Códigos de módulo (module_code)
| Código | Módulo |
|--------|--------|
| ADV | Audit Advisor / consultoría |
| AUD | Auditoría (financiera, tributaria, forense, sistemas) |
| TAX | Tributario / impuestos |
| LEG | Legal / societario |
| FIN | Finanzas / valoración |
| CYB | Ciberseguridad |
| DATA | Datos / BI / analítica |
| AUT | Automatización / RPA / scripts |
| GOV | Gobierno corporativo / cumplimiento |
| MKT | Marketing |
| CRE | Crédito / riesgo crediticio |

## Reglas de uso
1. Una sola llamada a la acción por solicitud del usuario (no reintentes salvo que falle).
2. No inventes resultados. Si la acción devuelve error (401/503/otro), dilo con honestidad.
3. Pide los datos que falten antes de llamar; no asumas cifras.
4. Tareas mixtas: primero `runPython` (calcula), luego `skillRun` (interpreta/redacta).
5. Responde siempre en el idioma del usuario, claro y profesional.

## Ejemplos
- "Redacta los hallazgos de auditoría sobre estos saldos" → `skillRun` (module_code=AUD).
- "Calcula el margen y la variación de estas ventas" → `runPython` (script con el cálculo).
- "Genera un Excel con este resumen por sucursal" → `runPython` + send_to_document_service=true.
- "Diseña un flujo de automatización para registrar facturas" → `skillRun` (module_code=AUT).
