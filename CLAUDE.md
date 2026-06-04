# Reglas del proyecto

## ⚠️ REGLA SUPREMA — Verificación previa antes de entregar
**NUNCA entregar un trabajo como concluido sin antes verificar empíricamente
que lo que afirmas está correcto.** Esto significa:

1. Si afirmo "todos los casilleros del formulario se trasladan" → ANTES de decirlo
   tengo que: (a) contar cuántos casilleros tiene el PDF real, (b) contar cuántos
   tiene mi Excel/output, (c) comparar y reportar honestamente cualquier diferencia.

2. Si afirmo "tests pasan" → tengo que correr `pytest` y confirmar el output, no
   asumir que pasa porque "no debería romperse".

3. Si afirmo "el bug está arreglado" → tengo que generar el Excel con datos reales
   del cliente y verificar que el caso reportado funciona, no solo correr unit
   tests aislados.

4. Si entrego una funcionalidad supuestamente completa pero después el usuario
   descubre que falta el 84% del trabajo (caso F-104: 22 cas en Excel vs 145 en
   PDF), eso es FALLA GRAVE. El usuario confía en lo que yo afirmo. Cada error
   no detectado erosiona esa confianza.

5. **Protocolo obligatorio antes de decir "listo":**
   - ¿Comparé contra la fuente original (PDF, Excel oficial, documento del cliente)?
   - ¿Conté las filas/casilleros del PDF vs lo que generé?
   - ¿Probé con datos reales del cliente (no solo fixtures)?
   - ¿Hay bloques enteros que pude haber omitido?
   - Si alguna respuesta es "no" → NO entregar, decir "verificando" y verificar.

6. **Specifically para Excel generados**: el archivo NO puede levantar el
   cuadro "Excel pudo abrir el archivo reparando o quitando el contenido que
   no se podía leer" al abrirse. Antes de entregar:
   - Cargar el .xlsx con openpyxl después de guardar
   - Recorrer todas las hojas buscando celdas problemáticas (texto que
     empieza con `=`, `+`, `-`, `@` y NO es una fórmula intencional)
   - Verificar paréntesis balanceados en fórmulas
   - Usar `_safe_text()` en `source_data_sheets.py` para escapar texto
     que podría ser interpretado como fórmula

## Idioma
- **SIEMPRE responder en español.** Toda comunicación con el usuario (explicaciones,
  resúmenes, preguntas, mensajes de estado) debe ser en español. Nunca en inglés.
- El código, nombres de variables y comentarios técnicos pueden seguir las
  convenciones existentes del repositorio, pero la conversación con el usuario es
  siempre en español.

## Formato de los anexos del ICT (Informe de Cumplimiento Tributario)
- **REGLA OBLIGATORIA**: cada anexo del ICT (INDICE, A1, A2, A3, A4, A5, A6, A7,
  A8, A9) generado por el sistema **DEBE verse profesionalmente presentado**,
  equivalente al formato oficial del SRI Ecuador. La referencia visual es el
  archivo `1791240154001_Anexo ICT_2024_07.xlsx` (ARCOLANDS 2024) que ya está
  validado por el SRI.
- Estándares a aplicar en cada filler (`backend/app/ict/fillers/a*.py`):
  - **Bordes**: thin en todas las filas con datos, doble para filas TOTAL.
  - **Fuentes**: Calibri 9 para datos, 10 negrita para TOTAL, 11 negrita para
    encabezados de bloque.
  - **Separación visual**: insertar fila en blanco entre bloques mayores
    (Activos Corrientes / No Corrientes / Pasivos / Patrimonio / Resultados).
  - **Merged cells**: las columnas que identifican el casillero (A, B, C, G en
    A1) deben fusionarse verticalmente cuando un casillero agrupa múltiples
    cuentas contables.
  - **Anchos de columna**: definir explícitamente para todas las columnas con
    datos (sin dejar el default de Excel).
  - **Alineación**: numéricos a la derecha con formato `#,##0.00`, texto a la
    izquierda, identificadores al centro.
  - **Filas TOTAL**: en negrita con fondo azul claro y borde doble superior/inferior.
- El módulo `backend/app/ict/fillers/formatting.py` centraliza los helpers
  reutilizables (`format_a1_sheet`, `apply_column_widths`, constantes de estilo).
  Cuando se cree el formatter de A2..A9, debe vivir en ese mismo módulo.
- Antes de cerrar la implementación de cualquier anexo nuevo o modificación de
  uno existente, comparar visualmente contra el oficial 2024 y validar que el
  cliente NO tendría que perder tiempo dándole formato manualmente al Excel
  descargado.

## Catálogos oficiales SRI (F-101, F-103, F-104) — fuente de verdad y actualización anual

Los tres catálogos canónicos (`backend/app/ict/catalogo_f101.py`,
`catalogo_f103.py`, `catalogo_f104.py`) son la **única fuente de verdad** sobre
qué casillero existe y cómo se llama. Toda la lógica de extracción, mapeo,
fillers y verificación dependen de ellos.

### Política de extracción
- **PROHIBIDO** extraer un catálogo nuevo con lógica stateful que "hereda" el
  nombre del concepto previo cuando una fila no tiene nombre propio. Ese fue el
  bug del F-103 (cas 499/880/890/897-904/999 → "SUBTOTAL EXTERIOR") que el
  usuario detectó manualmente y costó horas de re-trabajo.
- Si una fila del PDF/Excel oficial NO tiene nombre propio, **dejarla fuera del
  catálogo** o asignar el nombre real (revisándolo a mano contra la fuente),
  nunca "el último que vimos".
- Test de regresión obligatorio:
  `tests/test_ict_catalogos_no_heredan_nombres.py` debe pasar (5/5) tras
  cualquier modificación a un catálogo. Ese test atrapa el patrón de bug
  "nombres consecutivos iguales por herencia stateful".

### Procedimiento anual de actualización (cuando SRI publica formularios del año siguiente)
Se hace una vez al año, típicamente entre noviembre y febrero. Pasos:

1. **Descargar las guías oficiales del SRI** del año vigente:
   - F-101: "Guía para el contribuyente llenado de XML y JSON formulario
     Renta Sociedades" (PDF, ~28 págs, tiene Tabla 1 con todos los cas)
   - F-103: "GUIA DEL CONTRIBUYENTE LLENADO DEL XML Y JSON RETENCIONES EN LA
     FUENTE" (PDF, Tabla 1)
   - F-104: "FORMULARIO IVA.xlsx" (Excel oficial, hoja "1 Disenio",
     cols 9/11/13 = Valor Bruto / Valor Neto / Impuesto Generado)

2. **Ejecutar los extractores** (cuando se muevan a `scripts/extractors/`,
   ejecutarlos desde ahí; mientras tanto viven en la raíz del repo como
   `extract_f101_*.py`, `extract_f103_*.py`, `extract_f104_*.py`):
   ```bash
   python extract_f101_oficial.py    # genera catalogo_f101.py
   python extract_f103_oficial.py    # genera catalogo_f103.py
   python extract_f104_oficial.py    # genera catalogo_f104.py
   ```

3. **Aplicar correcciones manuales conocidas** (parche `CORRECCIONES`
   al final del catálogo):
   - F-103: cas 499, 880, 890, 897, 898, 899, 902, 903, 904, 999 —
     verificar que tengan los nombres correctos según `CORRECCIONES`
     dict en `catalogo_f103.py`. Si el extractor cambia y deja de
     necesitarlas, BORRAR el dict; no dejar correcciones obsoletas.

4. **Validar con tests** (TODOS deben pasar en VERDE):
   ```bash
   python -m pytest tests/test_ict_catalogo_f101_completo.py -v
   python -m pytest tests/test_ict_catalogo_f103_f104_completo.py -v
   python -m pytest tests/test_ict_catalogos_no_heredan_nombres.py -v
   python -m pytest tests/ -k ict --tb=no -q
   ```

5. **Validar empíricamente con cliente real** (PROPHAR S.A., RUC
   1791859596001, año 2025 es el caso de referencia):
   - Cargar los 12 F-103, 12 F-104, 1 F-101 del cliente
   - Generar el Excel ICT
   - Verificar:
     - A=P+Pa cuadra en A1 (activos = pasivos + patrimonio)
     - DATOS F-101 tiene los 888 casilleros (o el número del año vigente)
     - DATOS F-103 tiene los 184 cas
     - DATOS F-104 tiene los 141 cas
     - Excel NO levanta cuadro "Reparaciones" al abrirse
     - VERIFICACIÓN A1 categoriza las diferencias correctamente

6. **Documentar el cambio**: si el SRI agregó/eliminó/renombró casilleros entre
   años, registrar el delta en un nuevo bloque al final de este archivo
   (sección "Historial de cambios SRI").

### Deuda técnica conocida (a ejecutar cuando haya tiempo)
- **Action Item 5**: Mover `extract_f101_oficial.py`, `extract_f103_oficial.py`,
  `extract_f104_oficial.py` desde la raíz del repo a `scripts/extractors/` con
  docstring explicando cuándo correrlos. Razón: hoy contaminan el root y un
  developer nuevo no sabe que son one-shot tools, no parte del runtime.
- **Tests legacy fallando** (5 fallos pre-existentes, NO bloquean ICT):
  `test_chat.py::test_conversation_with_inaccessible_project_rejected`,
  `test_context.py::test_admin_creates_client_and_project_and_user_is_scoped`,
  `test_context.py::test_user_cannot_set_inaccessible_project_active`,
  `test_context.py::test_cross_org_isolation`,
  `test_sandbox.py::test_make_rlimit_preexec_optin`.
  Investigar y arreglar antes de cualquier release a producción de esos módulos.
- **API keys pendientes de rotar**: revocar Render API key
  `rnd_CXjUFxFmYQNZ2l2lAy8Ho2ebthhw` y configurar Resend email API key.
- **QA pendiente**: re-habilitar checks estrictos de device/session una vez
  terminada la fase de QA con clientes piloto.
