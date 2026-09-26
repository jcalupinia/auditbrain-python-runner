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
- **REGLA OBLIGATORIA (decisión del dueño, 2026-09-26: «escribe en español y ponlo como
  regla»):** la regla no tiene excepciones. Se escribe en español también:
  - los mensajes automáticos y breves: revisiones programadas del PR (check-ins),
    avisos de CI, «sin cambios», confirmaciones de una sola línea;
  - los informes de agentes o subagentes que se entregan al usuario y los encargos que
    se les dan;
  - las descripciones de PR, los comentarios en GitHub y los mensajes de commit.
  Si un texto llega en inglés (herramienta, notificación, agente), se traduce antes de
  mostrarlo. Solo quedan en su idioma original el código, los nombres técnicos y las
  citas textuales.
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
- **Tests legacy fallando** (6 fallos pre-existentes, NO bloquean ICT). Lista
  actualizada y verificada el 2026-08-05 (el PR de operadores renombró dos y
  agregó uno; la nota anterior listaba 5 con nombres viejos):
  `test_chat.py::test_conversation_with_cross_org_project_rejected`,
  `test_context.py::test_operator_can_create_clients`,
  `test_context.py::test_admin_creates_client_and_project_and_user_is_scoped`,
  `test_context.py::test_operator_can_set_same_org_but_not_cross_org_project_active`,
  `test_context.py::test_cross_org_isolation`,
  `test_sandbox.py::test_make_rlimit_preexec_optin`.
  **Diagnóstico:** los 5 primeros son de AISLAMIENTO, no de lógica: pasan al
  ejecutarlos solos y fallan al correr la suite completa, con
  `sqlalchemy.exc.IntegrityError` por estado compartido en la base SQLite de
  desarrollo. `test_sandbox` sí falla también en aislamiento.
  Investigar y arreglar antes de cualquier release a producción de esos módulos.
- **API keys pendientes de rotar**: revocar en el panel de Render la API key que
  estuvo escrita en este archivo (retirada del texto el 2026-09-24; sigue en el
  historial de git, por eso hay que revocarla) y configurar Resend email API key.
  Nunca escribir claves ni tokens en archivos del repo: van en variables de
  entorno de Render.
- **QA pendiente**: re-habilitar checks estrictos de device/session una vez
  terminada la fase de QA con clientes piloto.

## La suite NUNCA corre contra la base de desarrollo

**REGLA OBLIGATORIA (2026-08-06):** `tests/conftest.py` fija `DATABASE_URL` a
`auditbrain_tests.db` (borrada al arrancar la sesión) **ANTES** de importar la
app. Motivo: `session.py` resuelve `DATABASE_URL` en tiempo de import con
default `sqlite:///./auditbrain.db`, que es la misma base del `uvicorn` local.
Sin el override, `pytest` ensucia la base de trabajo del programador y la
suite deja de ser reproducible a partir de la segunda corrida.

- El override va en `os.environ`, no sólo en el módulo ya importado, para que
  cualquier módulo que relea la variable vea la misma base.
- `TEST_DATABASE_URL` permite apuntar la suite a otro motor (p. ej. un
  Postgres de pruebas) sin tocar código.
- Tests que mantienen viva la regla: `tests/test_suite_hermetica.py` (2).

## Fórmulas referenciales del libro DM (Obligaciones Fiscales)

**REGLA OBLIGATORIA (2026-08-06, PR #108):** toda dirección que una hoja del
libro DM publique para que OTRA hoja la referencie por fórmula debe ir
**calificada con el nombre de hoja entre comillas simples**
(`'Mayores homologados'!D30`, `'DATOS F-104'!C18`).

`cedulas/bloques.py::fila_referencias` escribe literalmente `f"={addr}"`, así
que una dirección desnuda la resuelve Excel contra la PROPIA hoja de la
cédula. Ese fue el bug que produjo 1.420 fórmulas rotas y 6 referencias
circulares reales en DM5 y DM7: el saldo de libros no llegaba, se perdía la
trazabilidad a DATOS F-104 / F-103, y Excel abría el archivo con aviso de
referencia circular.

**Ojo con el ICT:** `ict/fillers/source_data_sheets.py` (`build_f103_sheet`,
`build_f104_sheet`) devuelve direcciones SIN prefijo **a propósito** — el ICT
lo añade del lado consumidor en `ict/fillers/referential_helpers.py`.
Calificar ahí produciría doble prefijo y rompería A1..A9. El lado OF califica
en `libro/fuentes.py::construir_hojas_de_casilleros`.

**Test que mantiene viva la regla:**
`tests/test_of_libro_direcciones_calificadas.py`. Discriminador: una fórmula
es "publicación de direcciones" si está compuesta exclusivamente por
referencias unidas por `+`; en ellas cada token debe llevar `!`. Las
legítimamente intra-hoja son `=SUM(...)` y `=ROUND(...)`, más la aritmética de
la matriz de DM6 (`=B13*G13`, arrastres `=L13`/`=W13` del mes anterior).

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
- `_apply_sri_sheet_visibility(wb)` aplica `sheet_state="hidden"`, deja una
  hoja visible como activa (`INDICE`, porque Excel avisa si abre un libro
  cuya hoja activa está oculta) y **bloquea la estructura del libro con
  contraseña**.
- `_protect_workbook_structure(wb)` aplica `lockStructure=True` +
  `set_workbook_password(...)`. Con la estructura bloqueada, el cliente NO
  puede usar "Mostrar"/Unhide para des-ocultar las hojas ni insertar/
  eliminar/renombrar hojas. La clave sale de la env var
  `ICT_SRI_PROTECT_PASSWORD` (default `DEFAULT_SRI_PROTECT_PASSWORD` =
  `AuditIA-ICT-2025`). Solo AuditConsulting debe conocerla. NOTA: la
  protección de estructura de Excel NO es cifrado fuerte (es rompible con
  herramientas); es una barrera para que el cliente no manipule por error
  las hojas fuente. El papel de trabajo NO se protege.
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

## Sesión única del portal cliente — "el primero gana"

**REGLA OBLIGATORIA (activada 2026-06-26):** una cuenta del portal cliente
(rol `client`) solo puede estar EN USO por una persona a la vez. Si ya hay una
sesión viva y alguien intenta entrar con la misma cuenta, el **segundo login se
BLOQUEA** (HTTP 409, `code: "session_in_use"`) con el mensaje: *"Esta cuenta ya
está siendo usada… pida a la persona que está usando el sistema que cierre
sesión (botón «Salir»)…"*. NO se expulsa al que ya está dentro ("el primero
gana", a diferencia del comportamiento previo "el último gana").

- Operadores `admin`/`user` quedan EXENTOS (entran al portal con su mismo usuario).
- La sesión se libera con **logout** (botón Salir) o automáticamente tras
  **`CLIENT_PORTAL_SESSION_TIMEOUT_MINUTES`** (default 10) de inactividad.
- La "actividad" se refresca en cada request del cliente
  (`require_client_with_device` → `service.touch_session`). El frontend hace un
  **heartbeat** cada 3 min (`/client/auth/me`) para mantener viva la sesión
  mientras la pestaña esté abierta; al cerrarla, deja de refrescarse y caduca sola.
- Campos: `User.current_session_id` + `User.session_started_at` (este último
  reutilizado como "última actividad"). `auth.service.has_active_session()`
  decide si está viva; `auth.service.touch_session()` la refresca.

**Toggles (env vars en Render):**
- `CLIENT_PORTAL_SESSION_CHECK_ENABLED` = "true" (ON). "false" → modo multi-sesión (QA).
- `CLIENT_PORTAL_SESSION_TIMEOUT_MINUTES` = "10".
- `CLIENT_PORTAL_DEVICE_CHECK_ENABLED` sigue "false" (dispositivo único es aparte).

**Tests:** `tests/test_auth_session.py` (has_active_session / touch_session) y
`tests/test_client_portal_login.py`
(`test_second_login_blocked_while_first_active`, `test_login_allowed_after_logout`,
`test_login_allowed_after_inactivity_timeout`).

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

## Papeles de trabajo de las herramientas NIIF — formatos obligatorios

**REGLA OBLIGATORIA (decisión del dueño, 2026-09-21):** toda herramienta de prueba NIIF del
Command Center entrega su papel de trabajo en estos formatos:

1. **Excel con fórmulas editables, auditables y trazables.** Cada importe calculado es una
   fórmula de Excel que remite a su origen (hoja de parámetros, detalle por partida, matriz),
   no un valor pegado. Si el auditor cambia un parámetro o un saldo, el libro recalcula.
2. **HTML autónomo que funciona sin internet:** sin fuentes, scripts ni estilos externos. Lleva
   dentro, para descargar, el Excel con fórmulas, el Word y el PowerPoint, y el PDF se obtiene
   con «Guardar como PDF» del navegador (formato de impresión horizontal ya preparado).
3. **PDF, Word y PowerPoint** descargables también desde la vista de trabajo.

**Verificación antes de entregar:** abrir el Excel en Excel real, recalcular y comparar cada
fórmula con el valor que calculó Python (diferencia 0). Referencia:
`scripts/verificar_formulas_pi.py` (pérdidas incurridas). Implementación de referencia:
`backend/app/aud/niif/procesadores/libro.py` (celdas `{"f": fórmula, "v": valor}`).

**Sin cifras calculadas pegadas (decisión del dueño, 2026-09-24):** ninguna cifra que resulte
de un cálculo puede ir como valor fijo en el Excel. Los datos que entrega el cliente y los
parámetros del auditor sí son valores (entradas); todo lo demás es fórmula:
- Indicadores de la portada `00_Inicio` («consola»): los mismos 5 del panel del HTML (resultado
  principal, población, recalculado, registrado, problemas), cada uno fórmula a su cédula
  (`libro._kpis_panel`: fila del Resumen, `SUMIFS` sobre la columna del `PANEL` o `COUNTA` de
  Problemas). La tarjeta sin celda de origen no se muestra. Prueba: `test_portada_tarjetas_son_formulas`.
- **La portada del Excel ES el panel del HTML** (decisión del dueño, 2026-09-25:
  «los mismos gráficos del HTML, no otros; mismos colores de fondo y botones»):
  `procesadores/panel_excel.py` usa los colores de `html_ejecutivo.TEMAS["ejecutivo"]`
  (fondo #071B2F, tarjetas #0A2342, botones #0E2C50), las 5 tarjetas con sus colores y los 4
  gráficos del HTML como gráficos nativos: dona de composición, registrado vs recalculado,
  distribución y problemas por severidad (barras + línea dorada). Sus datos son fórmulas
  (SUMIFS/COUNTIFS) con la misma agrupación que el HTML (`graficos.serie_spec`,
  `graficos.severidad`). **Nunca** volcar todas las filas del Resumen en un gráfico: mezcla
  escalas y se ve como un código de barras. Si cambia el panel del HTML, cambia el Excel.
- Importe de cada problema: fórmula a la celda de la cédula donde se origina. Cada procesador
  declara `REF_PROBLEMAS = {código: (hoja, columna) | (hoja, columna, "total") | función}`
  (`procesadores/problemas.py`). Solo se enlaza si la celda tiene ese mismo importe; si no, queda
  como valor y lo reporta `python scripts/verificar_problemas_enlazados.py` (debe dar «PENDIENTES: 0»).
- Un código de problema nuevo exige su entrada en `REF_PROBLEMAS`; lo vigila
  `tests/test_aud_sin_datos_fijos.py`.
- **Datos del cliente dentro del libro (todas las herramientas desde 2026-09-25).** Cada documento que
  entrega el cliente va en su hoja `D1_…`, `D2_…` con la columna «Origen del dato» (archivo · hoja · fila)
  y la guía «¿De dónde saco este dato?» (también visible en el HTML y el Word).
  - Piloto hecho a mano: pérdidas incurridas (`D1_…`–`D5_…`; sus cédulas calculan desde ahí con fórmulas:
    evidencia histórica, reversión, bajas, provisión inicial, mora, tasa ponderada; claves de cruce `F…`,
    `A…`, `C…` en columnas agrupadas y ocultas).
  - Las otras 19: `procesadores/datos_cliente.py` (`con_datos`, llamado al procesar la prueba y en el
    ejercicio modelo) arma una hoja por requerimiento entregado y cambia cada dato del cliente que una
    cédula traía pegado (importes, fechas y textos) por una fórmula a su celda. Por cada columna elige UNA
    columna de datos con encabezado parecido (misma raíz o sigla: «Amort. acum.» = «Amortización acumulada»,
    «MOD» = «Mano de obra directa») y el mismo valor en la fila de la misma partida; si alguna partida la
    contradice, la columna es un cálculo y queda como estaba. Si el cliente dejó el dato en blanco, la fórmula
    es `IF(dato="",otro dato de la fila|valor por defecto,dato)`; un número entregado como texto (año) va con
    `VALUE(...)`. Un enlace nunca cambia una cifra. Lo que no es dato del cliente se escribe como fórmula en el
    procesador (p. ej. «Período» y «Vencimiento» de las tablas de amortización: `COUNTIF` y `EDATE`).
    **Ninguna cifra ni fecha queda pegada en las cédulas** (decisión del dueño, 2026-09-25, «hazlo de todo»):
    solo son valores `02_Parametros` y la carátula/documentación `00_…`; lo vigila
    `test_ninguna_cifra_ni_fecha_queda_pegada`. Verificación: `python scripts/verificar_datos_cliente.py`
    (LibreOffice, «DIFERENCIAS: 0»); prueba `tests/test_aud_datos_cliente.py`.

**Planificación de la auditoría (NIA 300, 315, 320, 330, 510; 2026-09-26):** herramienta del catálogo en la tarjeta
«Planificación» (`procesadores/planificacion_nia.py` v2, `RUBRO = "PLANIFICACION"`), con el mismo papel (Excel con
fórmulas, HTML, Word, PowerPoint, PDF) y el mismo ciclo que las pruebas NIIF. **Los documentos de entrada son los del
cronograma del artefacto de análisis** (decisión del dueño): balance de comprobación del cierre anterior y del corte
que se audita (código, nombre y saldo de TODAS las cuentas y niveles), estado de resultados del año anterior al mismo
corte (revisión preliminar; sin él se prorratea ÷ 12 × meses), carta de control interno (hallazgos con probabilidad,
impacto y control de 1 a 5), informe de auditoría y notas a los estados financieros del año anterior, RUC. Replica el
artefacto: mapa de cuentas por prefijo del código (el más largo gana, hoja `03_Mapa`), nivel y cuentas de detalle por
la jerarquía de los códigos, signo automático por sección, análisis horizontal de todas las cuentas, estados
resumidos, **sumarias por rubro** (`08S_Sumarias`: un bloque por cuenta de nivel 3 con sus subcuentas en jerarquía,
saldo anterior y al corte, ajustes del auditor que suben por fórmula de las cuentas de detalle, saldo ajustado,
variación, nota del año anterior, marca Nueva/Baja/Supera el umbral, total de las cuentas de detalle y cuadre = 0;
estilos por fila `estilos` de `base.hoja()`), **estados detallados** (`08A_ESF_Detalle`, `08B_ERI_Detalle`: todas las
cuentas por nivel, fecha de cada período, filas agrupadas por nivel en Excel con `estilos[i]["grupo"]` y cuadre contra la
hoja 07 y del balance), índices con semáforo (días sobre los días del período; con patrimonio ≤ 0 los índices sobre el
patrimonio salen «Rojo · No significativo»), lectura de cada índice **con su cifra** (FIXED, que usa los separadores del
equipo: el verificador compara las cifras en texto intercambiándolos), tendencia Mejora/Empeora y **días ajustados al
período** en la preliminar (hoja 10, columnas I y J; la hoja 13 compara esas cifras), materialidad (desempeño 50 % y
trivial 5 % por defecto; en la preliminar la base es el año anterior; rango de práctica habitual con aviso «Fuera del
rango» y justificación automática con cifras), matriz de la carta de CI (inherente = P × I; residual =
inherente × (6 − C) ÷ 5; **riesgo significativo** NIA 315/330 cuando el INHERENTE iguala o supera `umbralSignificativo`
(20 por defecto): nivel al menos Alto y «Significativo» en el programa), posibles riesgos (NIA 240, NIA 570, días de cartera e inventario, variaciones, informe
anterior, entendimiento de la entidad), **perfil del encargo NIA 315** (`14_Perfil`: identificación mínima con
«[PENDIENTE]» cuando no hay soporte —no se completa por inferencia—, entendimiento de la entidad y contexto, tipos
Entendimiento y Contexto del RQ-005; cada hallazgo del entendimiento genera su riesgo y su procedimiento), notas contra el balance anterior (NIA 510) con **desglose por nota** (`15D_Notas_Detalle`: cuentas y subcuentas de cada
nota, anterior y corte, total según el balance y conciliación con la nota auditada; al final, los rubros del balance
sin nota) y **composición auditada** (`15C_Composicion`, dato opcional RQ-009 `notas_detalle`: líneas de Saldo,
Movimiento y Total de cada nota, con su cuadre contra el saldo auditado), anomalías, control de calidad, cuentas a revisar, programa
(NIA 330: toda cuenta a revisar tiene su procedimiento, con aseveraciones, evidencia, responsable y los procedimientos
de todo el encargo), narrativa (alertas por nombre, variación % del activo y del resultado, lectura de variaciones con
montos, origen y destino del efectivo) y estrategia (NIA 300). Reglas del prompt FIN-AP aplicadas (2026-09-26, con los agentes del plugin NIIF: Automatización construye y el
Revisor Técnico revisa): **R1** saldo propio de cada cuenta (si falta, suma de sus subcuentas) y totales con la
cuenta más alta de cada sección/clasificación/rubro, con control «cuenta superior que no suma sus subcuentas» (no se
fuerza nada); **R2** signo por la convención del balance entero (con signo o por naturaleza), para que un patrimonio
en déficit siga negativo; **R4** días sobre 365 (en la preliminar los umbrales de días se evalúan × meses ÷ 12);
**R5/R6** margen operativo sobre ventas, DuPont del ROI y del ROE que reconcilian, proveedores y cartera solo
comerciales; base de materialidad ≤ 0 → sin materialidad (nada se marca material); lectura causa-efecto y puente de
orígenes y aplicaciones que cuadra con la variación del efectivo (`22_Origenes`); audit trail NIA 230
(`23_Audit_trail`). Niveles, severidades, semáforos y estados van **coloreados** (`colores` de `base.hoja()`: formato
condicional en Excel, etiqueta en HTML, celda sombreada en Word y PowerPoint). **Los datos del cliente LANSEY del artefacto original NO van al repo**: el
ejemplo es ficticio («Comercial Andina de Ejemplo S.A.»). Los porcentajes y umbrales son **política de la firma** y los
párrafos citados llevan «VERIFICAR». Su panel usa `PANEL["textos"]` (umbrales en lugar de «registrado vs
recalculado»; ver `graficos.TEXTOS`) y `PANEL["tableros"]` con los gráficos del artefacto (índices por grupo:
liquidez, actividad, endeudamiento, rentabilidad; analítico: estructura del balance y estado de resultados; anterior
frente a actual) en HTML, Excel (nativos 3D, datos por fórmula), Word y PowerPoint, en su propia lámina, con diseño
premium: relieve 3D, paleta ejecutiva sin celeste ni verde (un color propio por tablero, sin repetir colores en la
misma lámina), variación ▲▼ coloreada según el sentido favorable del índice y semáforo; ver `docs/niif/CONTRATO_PROCESADOR.md`). Prueba: `tests/test_proc_planificacion_nia.py`; verificación LibreOffice de
los 5 escenarios (final, preliminar con ERI, preliminar con prorrateo, pérdida PYMES, patrimonio en déficit): 0 diferencias.

**Control de calidad NIA de la planificación (2026-09-26, defectos D1–D11 de la revisión de control de calidad):**
- **Ciclo (todas las pruebas, NIA 230 y 220):** una versión **APROBADA no se reinicia ni se elimina** (`encerar`/`eliminar`
  responden 400 `APROBADA_NO_SE_TOCA`; se corrige con una nueva versión) y la vista no ofrece esos botones. Aprobar lo que uno
  mismo envió a revisión **se permite con advertencia** (decisión del dueño): el registro guarda `submittedBy` y
  `segregation`, el comentario de la bitácora lleva `SIN_SEGREGACION` y la carátula muestra «Envió a revisión» y
  «Segregación de funciones (NIA 220)» (`libro._segregacion`).
- **D3:** el control de la carta solo rebaja el riesgo si se probará su eficacia (columna «¿Se probará el control?», campo
  opcional `probar_control`); si no, el «Riesgo valorado» es el inherente.
- **D4:** cada cuenta material (saldo o variación) tiene su propio procedimiento sustantivo en el programa, con la respuesta de
  su sección (`RESPUESTA_SECCION`), aunque haya un riesgo de su área. **D5:** sin materialidad, «¿Aplica?» dice
  `NO_APLICA_SIN_MAT`. **D6:** socio y gerente vacíos quedan `[PENDIENTE]` (programa y estrategia) y el control «Datos de
  gobierno del encargo completos (NIA 300)» dice «Revisar». **D7:** un riesgo pendiente de calificación se trata como alto
  (socio, visita preliminar). **D8:** un riesgo significativo exige pruebas de detalle (`EVIDENCIA_SIGNIFICATIVO`).
- **D9:** en la preliminar con la base al «Corte actual», las bases de resultados (`BASES_FLUJO`) se anualizan × 12 ÷ meses y
  la hoja 11 lo dice; el activo y el patrimonio no se anualizan.
- **D10:** la fila «Opinión» del informe anterior con salvedades, desfavorable o abstención (`_opinion_modificada`) genera un
  riesgo alto (NIA 705 y 710); se aceptan los tipos «Desfavorable» y «Abstención» (y los alias «Adversa», «Denegación»).
- **D11:** en la narrativa, la variación de resultados acumulados (traspaso del resultado anterior) se suma al resultado del
  período (`RESULTADO_NETO_TRASPASOS`) y en la hoja 22 su tipo es «Traspaso de resultados»; en la preliminar el importe de los
  días es el ajustado al período. Pruebas: `tests/test_proc_planificacion_nia.py` (`test_defectos_d4_a_d8_del_programa`,
  `test_defecto_d10_…`, `test_defecto_d11_…`) y `tests/test_aud_ciclo_revision.py`. Los faltantes A1–A19 se resolvieron en
  el bloque siguiente; M1–M21 siguen pendientes.

**Documentación del encargo en la planificación (2026-09-26, faltantes A1–A19 de la revisión de control de calidad):**
`procesadores/planificacion_encargo.py` (complemento de `planificacion_nia`, no es herramienta del catálogo). Lo que prepara
el **equipo de auditoría** entra por cuatro requerimientos marcados «lo prepara el equipo»: RQ-010 cuestionario de
planificación (catálogo fijo `CUESTIONARIO` de 40 preguntas por código: ACE aceptación, CON condiciones previas y carta
de encargo, MES materialidad específica, COM comunicación, DIS discusión del equipo, FRA fraude, CI cinco componentes del
control interno, TI controles generales), RQ-011 equipo e independencia, RQ-012 diferencias (NIA 450) y RQ-013 componentes
del grupo (NIA 600). **Regla de cero invención:** lo no documentado queda «[PENDIENTE]» y el control de calidad (hoja 16,
controles 15–24) lo cuenta. Hojas nuevas: `24_Aceptacion`, `25_Equipo`, `26_Discusion_Fraude`, `27_Control_Interno`,
`28_Afirmaciones` (cuenta × afirmación y nivel de estados financieros), `29_Muestreo` (unidad monetaria: −ln(1−confianza),
factor de expansión, error esperado; confianza por el nivel más alto de la hoja 28), `30_Diferencias`, `31_Grupo`,
`32_Comunicacion` (NIA 260 y asuntos clave candidatos NIA 701); los problemas pasan a `33_Problemas`. Cada respuesta con
alerta es un riesgo de la hoja 13 (fórmula al estado de la pregunta) y un procedimiento del programa; un hallazgo de la carta
que menciona «fraude» es riesgo significativo (A7); el programa suma la columna «Extensión (NIA 330 y 530)», aseveraciones
por área (A13) y el plan de confirmaciones y observación del inventario solo para cuentas de balance materiales (A14); la
hoja 11 trae la materialidad específica (A10); la estrategia, los riesgos significativos por nombre, empresa en marcha,
calendario, independencia y respuestas globales (A16); la hoja 02, «Estados del año anterior» (A17), el rol en el grupo
(A18) y los porcentajes de muestreo, componente y rotación (política de la firma, «VERIFICAR»). **A4:** la definición
declara `firmas` y el libro agrega `00_Firmas` con preparó/revisó y fechas tomados de la bitácora. Escenario nuevo
`grupo_eip`. Pruebas: `tests/test_proc_planificacion_nia.py` (`test_a…`). Verificación LibreOffice de los 6 escenarios:
0 diferencias.

**Diseño del libro (todas las herramientas, 2026-09-25):** portada con botones por sección
(Resultado · Cómo se calculó · Datos del cliente · Documentación) y pestañas del color de su
sección; en cada hoja la botonera Inicio/Anterior/Siguiente arriba a la izquierda; Calibri;
gráficos con título sin superponer (`overlay=False`), rótulos como texto (`strRef`) y datos en la
hoja oculta `00_Datos_graficos`; «Cómo se calcula» en lenguaje sencillo (columna, cómo se calcula,
de dónde viene) y la fórmula de Excel con su ejemplo en la hoja `00_Anexo_tecnico`.

**Word y PowerPoint = el HTML (decisión del dueño, 2026-09-25):** `procesadores/papel_office.py`.
El PowerPoint es el HTML en pantalla (tema «Ejecutivo»: fondo #071B2F, portada con logos y chips,
las 5 tarjetas y los 4 gráficos del panel, cédulas en tablas oscuras). El Word es el HTML impreso
(tema «Claro», el mismo del PDF: un Word no imprime el color de página). Los gráficos son los
MISMOS SVG del HTML dibujados como imagen con matplotlib (`procesadores/svg_png.py`) y las
tarjetas salen de `html_ejecutivo.kpis_datos`: si cambia el HTML, cambian el Word y el PowerPoint.
Sin gráficos nativos distintos en el PowerPoint. Prueba: `tests/test_aud_office_como_html.py`
(incluye el orden del XML de Word, que si falla dispara «contenido ilegible»).

**Agentes que construyen o revisan herramientas NIIF (2026-09-25):** el contrato vigente está en
`docs/niif/CONTRATO_PROCESADOR.md` y el encargo en `docs/niif/ENCARGO_AGENTE_HERRAMIENTA.md`. Cubren `PANEL`,
`REF_PROBLEMAS`, `explica`/`guia`/`ocultas` en `base.hoja()`, las hojas de datos del cliente y los verificadores.
Si cambia una regla de esta sección, actualizar también:
- esos dos documentos;
- las skills `skills/niif-multiagente/` (orquestador, automatización, revisor);
- el encargo «Generar código para Claude» (`frontend/src/aud/niif/fichaLogic.js::textoEncargo`, sección 7);
- la línea «PAPELES DEL COMMAND CENTER» de `docs/gpt/instructions_niif_*.md`.

**Logotipos (2026-09-25):** todo papel lleva el logo de AuditConsulting y el de AUDIT-IA
(`procesadores/marca.py`, archivos en `backend/app/aud/niif/assets/`): banda navy de `00_Inicio`,
encabezado del Word, portada y pie del PowerPoint, barra del HTML y membrete de impresión/PDF.
En el HTML van incrustados en base64 (nunca una URL externa). Prueba: `tests/test_aud_marca_logos.py`.

**Pruebas declarativas (catálogo y fichas sin procesador) = el mismo diseño (decisión del dueño,
2026-09-25: «haz las pruebas declarativas con el diseño nuevo»).** El navegador solo aporta las
cédulas con fórmulas del exportador del sitio (`workbookSheets`, vía `cargaPapel` en
`frontend/src/aud/niif/papelDeclarativo.js`); el servidor arma Excel, HTML, Word, PowerPoint y PDF
con `libro` a través de `procesadores/declarativo.py` (endpoints `POST /aud/ciclo/papel-declarativo`
y, al aprobar, `POST /aud/ciclo/pruebas/{id}/papel-declarativo`, que guarda los cuatro con su huella).
El adaptador no mueve ninguna celda (la fila k del sitio es la fila k del Excel), reemplaza la portada
del sitio por `00_Inicio`, deriva el `PANEL` de la definición (población = columna de conciliación;
registrado vs recalculado = saldo del mayor vs población; composición = resultado principal por
partida), enlaza el importe de cada excepción a su celda, pasa a fórmula el conteo de registros y el
«Cuadro de períodos» de una serie, y hace que las reglas con agregados (`clave_inicial/_final/_total`)
lean el cuadro (el sitio las dejaba apuntando a la columna A: #¡VALOR!). Verificación:
`python scripts/verificar_papel_declarativo.py` (LibreOffice, debe dar «DIFERENCIAS: 0»); pruebas
`tests/test_aud_papel_declarativo.py` y `papelDeclarativo.test.js` (esta falla si los ejemplos de
`tests/fixtures/papel_declarativo` se desactualizan: regenerarlos con
`node frontend/scripts/fixture_papel_declarativo.mjs`). La copia `sitio/` no se edita.
**Calculadora reutilizable (2026-09-25):** el HTML de una prueba declarativa trae la pestaña
«Calculadora» con el MISMO motor portable del sitio (`sitio/tools/portable-engine.mjs`, leído por
`declarativo.motor_portable()`; el `.dockerignore` lo deja entrar a la imagen) y la población de la
versión: editar, agregar/quitar filas, recalcular, restablecer. Es una simulación: no cambia el papel,
no se imprime ni va al PDF. Prueba en el navegador: `node scripts/probar_calculadora.mjs <papel.html> <total>`.
