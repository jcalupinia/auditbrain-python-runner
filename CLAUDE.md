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

## Separación SRI vs Papel de trabajo del auditor

**REGLA OBLIGATORIA:** En el archivo Excel que se entrega al cliente para
cargar al portal del SRI Ecuador, las hojas internas del auditor
(`VERIFICACIÓN A1`, `TRAZABILIDAD`, debug/logs) y las hojas de datos fuente
(`DATOS F-101`, `DATOS F-103`, `DATOS F-104`, `DATOS BALANCE`) **NO deben
verse en las pestañas**. El papel de trabajo paralelo
(`ICT_{ejercicio}_{ruc}_PAPEL_TRABAJO.xlsx`) conserva TODAS las hojas
visibles para el auditor.

**CAMBIO 2026-06-26 (decisión del cliente) — OCULTAR, no borrar.** Esas
hojas ya **NO se eliminan** del archivo SRI: se **ocultan**
(`sheet_state="hidden"`). Motivo crítico: las fórmulas referenciales de
A1..A9 apuntan a `'DATOS F-101'!Cxxx`, `'DATOS BALANCE'!..`, `'DATOS F-103'!..`,
`'DATOS F-104'!..`. **Borrar** esas hojas rompería las fórmulas con `#REF!`
al abrir el Excel. **Ocultarlas** deja el archivo limpio a la vista del
cliente (solo `INDICE` + `A1..A9` en las pestañas) y mantiene todas las
fórmulas resolviendo. Nunca volver a `del wb[hoja]` para estas hojas.

Razón SRI: el portal espera la estructura oficial del ICT
(INDICE + A1..A9). Las hojas DATOS/internas ocultas viajan en el libro pero
no estorban la vista; el contenido referenciado sigue disponible para Excel.

**Implementación canónica:**
- `backend/app/ict/service.py::generate_excel()` devuelve
  `tuple[bytes_sri, bytes_papel_trabajo]`.
- La constante `HIDDEN_SHEETS_FOR_SRI` define qué hojas se **ocultan** en el
  archivo SRI (alias retrocompat: `INTERNAL_SHEETS_FOR_SRI`). Si se agregan
  nuevas hojas internas/datos, agregarlas a esa tupla.
- `_apply_sri_sheet_visibility(wb)` aplica `sheet_state="hidden"` y deja una
  hoja visible como activa (`INDICE`), porque Excel avisa si abre un libro
  cuya hoja activa está oculta.
- `process_session` guarda en disco: `ICT_SRI.xlsx`, `ICT_PAPEL_TRABAJO.xlsx`,
  y por compat `ICT.xlsx` (= SRI).
- Endpoint `GET /sessions/{id}/download` devuelve el SRI.
- Endpoint `GET /sessions/{id}/papel-trabajo` devuelve el papel de trabajo.

**Tests obligatorios para mantener la regla viva:**
- `tests/test_ict_service_split.py::test_hidden_sheets_constant_lists_datos_and_internal_sheets`
- `tests/test_ict_service_split.py::test_sri_hides_but_never_deletes_sheets`
- `tests/test_ict_service_split.py::test_sri_active_sheet_is_visible_indice`
- `tests/test_ict_endpoint_papel_trabajo.py` (los 3 tests del router).

**Verificación empírica:** `python scripts/verify_papel_trabajo_prophar.py`
(modo synthetic en CI, modo `--ruc <RUC>` con sesión real en producción).

## Interpretación IA con disclaimer obligatorio

Toda interpretación generada por LLM en artefactos del ICT
(`backend/app/ict/audit/interpreter.py`) debe cumplir 6 controles antes
de escribirse al Excel del papel de trabajo:

1. **Validación schema Pydantic.** La salida pasa por
   `AnexoInterpretation.model_validate`. JSON inválido → reintento
   (máximo 3 con exponential backoff 1s/2s/4s) → fallback graceful.
2. **QA evaluator.** Cada interpretación pasa por la skill
   `auditbrain-ai-response-quality-evaluator` antes de renderizarse.
   Hook documentado en interpreter.py para invocarse cuando la skill
   esté disponible en runtime.
3. **Audit trail.** Cada llamada queda registrada vía
   `auditbrain-audit-trail-generator` (modelo, tokens, hash_input,
   timestamp).
4. **Disclaimer visible.** Toda hoja con interpretación IA debe llevar
   al pie (font Calibri 8 italic color #6B7280):
   "Análisis generado por IA. La interpretación debe ser validada por
   el auditor responsable antes de cualquier decisión."
   Esto se renderiza tanto en `fill_verification_a1` como en
   `fill_auditoria_anexos`.
5. **Confianza autoreportada.** El campo `confianza_modelo` (alta/media/
   baja) debe renderizarse visualmente. Si es "baja", marcar el bloque
   con borde rojo + leyenda "Revisar manualmente".
6. **`requiere_revision_humana`.** Si es `True`, agregar ícono dedicado.

Nunca renderizar un bloque interpretado al Excel sin estos 6 controles
en su lugar.

### Configuración del modelo LLM (env var `ICT_LLM_MODEL`)

`backend/app/ict/audit/interpreter.py::DEFAULT_MODEL` define el modelo
Anthropic por defecto. Actual: `claude-sonnet-4-5-20250929`.

**Reglas operativas:**
1. El ID del modelo DEBE existir en la API Anthropic vigente. Si se
   pinea un ID futuro/inventado, el sistema NO crashea (cae a
   `_fallback_interpretation` que marca confianza=baja), pero las
   interpretaciones IA reales NUNCA se generarán.
2. Cuando Anthropic publique un modelo nuevo (Sonnet 4.6, etc.) y
   quieras usarlo, hacelo via env var en Render:
   ```
   ICT_LLM_MODEL=claude-sonnet-4-6-XXXXXXXX
   ```
   NO modifiques el default en `interpreter.py` salvo en bump de versión
   verificado y commit con changelog.
3. Síntoma de problema: si las hojas `ARTEFACTO A1` / `ARTEFACTO AUDITORIA`
   muestran *"Análisis IA no disponible en esta sesión..."* en TODOS los
   anexos, probablemente el `DEFAULT_MODEL` apunta a un ID inválido o
   falta `ANTHROPIC_API_KEY` en el entorno. Diagnosticar primero el log
   server-side y luego el ID del modelo.

### Variables de entorno requeridas en Render

| Variable | Requerida | Default | Notas |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Sí (para IA real) | — | `sk-ant-api03-...` del Anthropic Console. Sin esto → fallback graceful en todos los anexos. |
| `ICT_LLM_MODEL` | No (tiene default) | `claude-sonnet-4-5-20250929` | Sobreescribir solo cuando Anthropic publique un modelo nuevo verificado. |

## A1 sin "saldos de línea" — TODOS los cas del balance del catálogo OFICIAL

**REGLA OBLIGATORIA:** El anexo A1 (`backend/app/ict/cell_maps/a1.py`,
constante `A1_CASILLEROS_ORDERED`) debe contener **TODOS** los casilleros
del balance (rango 311-699) que estén en el catálogo OFICIAL F-101
(`backend/app/ict/catalogo_f101.py::F101_CASILLERO_NAMES`).

NO se permiten listas hardcoded paralelas: la lista del A1 se DERIVA en
runtime del catálogo oficial. Esto evita el bug "saldos de línea": cuando
el F-101 declara un valor en un casillero (ej. cas 490 DERECHOS DE USO,
cas 491 (-) AMORTIZACIÓN, cas 593 PASIVO POR ARRENDAMIENTO) pero el A1
NO lo muestra porque la lista hardcoded no lo incluía.

### Detección automática de casilleros negativos

`A1Filler.NEGATIVE_CASILLEROS` se construye en init estático como
`_NEGATIVE_CORE ∪ {cas : nombre del catálogo empieza con "(-)" }`. Esto
asegura que cuando SRI agrega un nuevo cas de naturaleza (-) (deterioro,
amortización, depreciación, etc.), queda automáticamente clasificado sin
necesidad de tocar `a1_mapeo.py`.

### Tests obligatorios (no remover sin agregar reemplazo)

- `tests/test_ict_a1_no_saldos_de_linea.py` (6 tests)
  - `test_a1_contiene_todos_los_casilleros_del_balance_oficial`
  - `test_a1_cas_specicos_del_screenshot_estan_presentes` (regresión
    del bug 2026-06-04: cas 490, 491, 593)
  - `test_a1_usa_nombres_oficiales_del_catalogo`
  - `test_a1_negative_casilleros_incluye_cas_491`
  - `test_a1_todos_los_negativos_del_balance_son_minoradores`
  - `test_a1_conteo_minimo_267_casilleros_balance`
- `tests/test_ict_a1_totales_regla.py` (8 tests) — orden de filas y
  cuadratura de TOTALES.

### Procedimiento al detectar saldos de línea nuevos

Si el cliente reporta que un cas no se traslada al A1:
1. Verificar que está en `F101_CASILLERO_NAMES`. Si no → bug del extractor
   F-101 (ver "Procedimiento anual de actualización SRI" más arriba).
2. Verificar que `_en_rango_a1(cas)` devuelve `True`. Si no → ampliar el
   rango en `cell_maps/a1.py`.
3. Si está en el rango y en el catálogo pero NO aparece → ejecutar el
   test `test_a1_contiene_todos_los_casilleros_del_balance_oficial`
   para diagnosticar.
4. NUNCA arreglar manualmente agregando una línea hardcoded — eso causa
   exactamente el bug que esta regla intenta prevenir.

## Formatos numéricos en parsers SRI — soporte automático `.` y `,`

**REGLA OBLIGATORIA:** Todos los parsers de PDFs SRI (F-101, F-103, F-104)
deben aceptar números en cualquier formato regional:

| Formato | Ejemplo | Resultado esperado |
|---|---|---|
| US (coma=miles, punto=decimal) | `178,259.63` | `178259.63` |
| Europeo (punto=miles, coma=decimal) | `178.259,63` | `178259.63` |
| Plano sin separador de miles | `183724.10` | `183724.10` |
| Solo decimal | `0.00` / `0,00` | `0.0` |
| Solo entero | `100` | `100.0` |
| Negativo | `-150.00` / `-178,259.63` | `-150.0` / `-178259.63` |

**Razón:** los computadores de los clientes están configurados con
"Configuración regional" diferente. Algunos exportan PDFs con `.`
decimal, otros con `,`. El sistema debe abstraer eso del usuario.

**Implementación canónica:**
- `backend/app/ict/parsers/f103_pdf.py::_parse_amount()`
- `backend/app/aud/obligaciones_fiscales/cedulas/base.py::_parse_amount_sri()`

Ambos siguen la heurística: si el string tiene `.` y `,`, el separador
DECIMAL es el que aparece **al final**. Si solo tiene `,` y los caracteres
después son 1-2 dígitos, es coma decimal. Si solo `.`, es separador estándar.

**Regex para extracción de montos en PDFs:**
```python
# CORRECTO: captura cualquier cantidad de dígitos + grupos de separadores
monetario = r"(-?\d+(?:[.,]\d+)*)"
```
```python
# INCORRECTO (bug histórico 2026-06-04): limitaba a 3 dígitos
monetario = r"(-?\d{1,3}(?:[,.]\d{3})*(?:[,.]\d{1,2})?)"
# → para "183724.10" capturaba solo "183"
```

**Tests obligatorios** (no remover sin reemplazo):
- `tests/test_ict_parser_formato_numerico.py` (20 tests)
  - `TestParseAmountFormatosNumericos` — 11 casos de _parse_amount
  - `TestParseAmountSriBase` — 4 casos del helper en base.py
  - `TestExtractCasillerosF103` — 4 casos de regresión con texto simulado
  - `TestExtractCasillerosPDFRealPROPHAR` — verificación empírica con
    PDF real de PROPHAR febrero 2025 (skipea si no está disponible)

**Procedimiento al detectar valores 0 en DATOS F-103/F-104:**
1. Confirmar que el PDF se subió correctamente al slot
2. Correr `parse_f103(pdf_bytes)` localmente con el PDF problemático
3. Si devuelve `casilleros={}` o valores != esperados → bug en parser
4. Agregar test con texto simulado a `test_ict_parser_formato_numerico.py`
5. Corregir el regex/`_parse_amount` para que el test pase
6. NUNCA hardcodear el valor en el filler — el filler solo presenta lo
   que el parser le da

## Marca — AuditConsulting Auditores Cía. Ltda. (firma) y AUDIT-IA (plataforma)

**Identidad oficial:**
- **Marca única (empresa):** **AuditConsulting Auditores Cía. Ltda.** — presta los
  servicios de auditoría y consultoría; es la única marca. Todo contenido se firma
  con este nombre.
- **Plataforma:** **AUDIT-IA** — la aplicación de auditoría + advisory + IA que esta
  firma creó (este repo es su backend/"cerebro"). El Manual v1 la nombraba
  "AuditBrain Executive Advisory"; el nombre vigente es **AUDIT-IA**. A nivel técnico
  el repo conserva el nombre `auditbrain-python-runner`.
  Slogan de la plataforma: *"Auditoría, advisory e inteligencia artificial para
  decisiones estratégicas."*

**Fuentes de verdad de marca (no duplicar el contenido en otros archivos):**
- **Manual de Marca v1** (capa verbal/estratégica): `docs/MANUAL_MARCA_AUDITBRAIN.docx`
  — propósito, visión, misión, posicionamiento, personalidad, voz/tono, estructura
  de informes (Problema→Impacto→Riesgo→Diagnóstico→Recomendación→Beneficio) y KPIs.
- **Estilo visual (capa Canva, aprobada e implementada):** `docs/CANVA_ESTILO_PoC.md`
  — DM Sans, tema "Dark Executive Dashboard" oscuro premium, Gold `#C7A83C` /
  Deep Blue `#071B2F` / Navy `#0A2342`. *(El manual referencia además
  Montserrat/Poppins/Roboto; la implementación vigente usa DM Sans.)*
- **Perfil consolidado para skills de contenido:** `../MARCA_FIRMA.md` (raíz de
  `PROYECTOS CLAUDE`) — lo aplican las skills del plugin Marketing de Cowork.
- **Perfil contable-financiero:** `../PERFIL_FINANCIERO.md` — marco NIIF/SRI/USD que
  aplican las skills del plugin Finance de Cowork.

**REGLA:** cualquier entregable de comunicación (informe, deck, propuesta, carta de
gerencia, contenido de marketing) o reporte financiero generado por el sistema o por
las skills de Cowork debe respetar estas fuentes. Si la marca cambia, editar el
Manual / `MARCA_FIRMA.md` / `PERFIL_FINANCIERO.md`, no este archivo.

> **Contexto Cowork (2026-06-19):** se personalizaron los plugins **Marketing** y
> **Finance** de Claude Cowork con el contexto real de la firma (perfiles enlazados
> en el `CLAUDE.md` de la raíz para aplicación automática). Conectores externos
> (HubSpot, BigQuery, Microsoft 365, Canva MCP, etc.) quedaron sin autenticar a
> pedido del usuario; los plugins funcionan sin ellos.
