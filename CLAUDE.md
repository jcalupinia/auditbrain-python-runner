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
