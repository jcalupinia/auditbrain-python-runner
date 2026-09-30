# Efectivo y Equivalentes de Efectivo — Arquitectura funcional y técnica

> **Estado del documento:** entregable previo a la implementación (prompt definitivo, secciones 34 y 38).
> **Regla:** este documento se genera ANTES de programar. La construcción del módulo NO empieza
> hasta que el dueño apruebe esta arquitectura y el plan por etapas.
> **Alcance:** módulo `AUD – External Audit → Efectivo y equivalentes de efectivo`, procesador
> `efectivo_equivalentes` (RUBRO `CAJA_BANCOS`). No se rediseña el frontend ni se cambian los botones ya aprobados.

Referencias de código verificadas (rutas relativas a la raíz del repo):
`backend/app/aud/niif/procesadores/efectivo_equivalentes.py`,
`conciliacion_reestructurada.py`, `caja_bancos_armado.py`, `caja_bancos_papel.py`, `base.py`;
`backend/app/aud/niif/ciclo/{datos.py, reglas.py, servicio.py, router.py, models.py}`;
`frontend/src/aud/niif/{PruebasEncargo.jsx, CicloVista.jsx, cicloLogic.js, api.js}`.
Papel de trabajo de referencia (cliente real): `DA_-_Efectivos_y_Equivalentes.xlsx` (LANSEY S.A., corte 31-08-2026).

---

## 0. Resumen ejecutivo — ¿tenemos la lógica completa?

**La mayor parte de la lógica YA EXISTE en el backend determinista.** El procesador
`efectivo_equivalentes.ejecutar(...)` calcula la conciliación por cuenta, la antigüedad de partidas,
confirmaciones, restringidos, equivalentes, efectivo auditado y ajuste, produce 14 cédulas con fórmulas
Excel vivas + panel/tableros, y existe además un papel de trabajo formulado **DA** (DA-1..DA-6 + Libro
Mayor) descargable. Todo es Python determinista, sin IA, con huella SHA-256 (`runHash`) y trazabilidad
por fila (`_file/_sheet/_row`).

**Brechas reales frente al prompt (lo que hay que construir o completar):**

| # | Brecha | Severidad | Sección |
|---|---|---|---|
| B1 | **Motor de reproceso / matching**: hoy es 1:1 voraz de criterio único (naturaleza + valor ±½ centavo + ventana de fecha), **sin niveles**, **sin usar la referencia**, **sin 1:N / N:1**, **sin detectar duplicados ni diferencias de valor**, y **desconectado** del cálculo/excepciones del procesador (solo alimenta un Excel DA aparte). | **Alta** | §8, §11 |
| B2 | **Comparación reproceso vs. conciliación de la compañía**: no existe. | **Alta** | §8 |
| B3 | **Validaciones cruzadas de ingesta** entre datasets (estado de cuenta / mayor / conciliación anterior ↔ anexo de cuentas) y **moneda**: no existen (solo se cruza partida↔cuenta). | Media | §5, §7-lógica Procesar |
| B4 | **Integrar el reproceso al ciclo**: que el reproceso alimente resultados/excepciones y no solo un Excel descargable. | Media | §8 |
| B5 | **Estados por requerimiento** con la taxonomía del prompt (PENDIENTE/CARGADO/VALIDANDO/VALIDADO/ERROR) y de prueba (BLOQUEADA/DISPONIBLE/PROCESANDO/EJECUTADA/CON EXCEPCIONES/REVISADA): el ciclo tiene 13 estados con otra taxonomía; hay que mapear/exponer los del prompt. | Media | §10 |
| B6 | **Huella SHA-256 por archivo de entrada** (audit trail NIA 230 por documento): hoy solo hay `runHash` global; falta la huella por archivo (el procesador no declara `USA_REGISTROS_ENCARGO`). | Baja | §9 |
| B7 | **Fecha de prescripción de partidas**: hoy es fórmula fija `fecha+390` solo en el papel DA; conviene parametrizarla. | Baja | §7-Partidas |
| B8 | **Frontend de 3 pasos** (Requerimientos → Procesamiento → Ejecución) tema oscuro, solo Efectivo, tarjetas que abren la vista detallada: la UI actual es un apilado largo; hay que condensarla. | Media (UI) | §3, §12 |

**Conclusión:** la lógica base está sólida y es reutilizable; lo que falta es, sobre todo, **robustecer y
conectar el motor de reproceso (B1–B4)**, **cerrar validaciones cruzadas (B3)**, **exponer los estados del
prompt (B5)** y **rearmar la vista en 3 pasos (B8)**. Ninguna brecha exige rehacer lo existente.

---

## 1. Arquitectura funcional

Flujo canónico del módulo (confirmado por el dueño):

```
Anexo de Caja y Bancos + Conciliaciones + Estados Bancarios + Mayores
        ↓
    PROCESAR  (validación → normalización → mapeo → cruces)
        ↓
    DATASETS ESTÁNDAR
        ↓
    PRUEBAS DE AUDITORÍA
        ├── Sumaria
        ├── Resumen de Conciliaciones
        ├── Análisis de Partidas Conciliatorias
        ├── Reproceso independiente del último mes
        └── Procedimiento general
        ↓
    RESULTADOS → EXCEPCIONES → PAPELES DE TRABAJO → CONCLUSIONES
```

Componentes visuales YA APROBADOS (no se rediseñan; solo se implementa/limpia su lógica):

- **A. Requerimientos de información:** (1) Anexo de Caja y Bancos, (2) Conciliaciones Bancarias,
  (3) Estados de Cuenta Bancarios, (4) Mayores Contables.
- **B. Controles:** (5) Procesar, (6) Encerar.
- **C. Ejecución de auditoría:** (7) Procedimiento de Efectivo y Equivalentes, (8) Sumaria,
  (9) Resumen de Conciliaciones Bancarias, (10) Análisis de Partidas Conciliatorias,
  (11) Reproceso de Conciliación Bancaria – Último Mes.
  **Botones nuevos (autorizados por el dueño, 2026-09-29): procedimientos que el motor ya calcula pero que
  el mockup dejó sin botón** — (12) Corte de Documentos, (13) Confirmaciones Bancarias, (14) Efectivo
  Restringido, (15) Equivalentes de Efectivo, (16) Asientos de Ajuste y Reclasificación, (17) Arqueo de Caja
  (opcional, caja física). Cada uno abre una cédula que YA existe (07/06/08/09/11/05-DA-5), así que su costo
  es bajo: son tarjetas que exponen una cédula ya calculada.

Regla de habilitación: **antes de Procesar** las pruebas de ejecución están BLOQUEADAS; **después de
Procesar correctamente** quedan DISPONIBLES. En el ciclo actual esto se cumple por la guarda de la
transición `execute`, que exige `validation.ok` y `reconciliation.resolved` (`ciclo/reglas.py:80-81`).

---

## 2. Arquitectura de datos

Capas lógicas (el prompt pide separar RAW / STAGING / NORMALIZED / AUDIT / RESULTS). Mapeo a lo existente:

| Capa | Qué es | Dónde vive hoy |
|---|---|---|
| **RAW** | Archivos originales que sube el cliente (Excel/PDF), sin tocar. | Almacén de archivos del ciclo (`ciclo/models.py`, `almacen`), con huella por archivo. |
| **STAGING** | Filas leídas + mapeo de columnas (índice→campo) elegido por el auditor. | `reg["datasets"][tipo]` (filas mapeadas) + `mapping`, calculado con `filas_mapeadas(...)` (`base.py`/`perdidas_incurridas_s11.py:154-181`). |
| **NORMALIZED** | Datasets estándar tipados (fechas ISO, montos float, signos por tipo). | Salida de `validar_filas` + `a_num`/`a_fecha` (deterministas). Objetos `cuentas`, `partidas`, `libro_mayor`, `estado_cuenta`, `conciliacion_anterior`, `arqueo`. |
| **AUDIT** | Cálculos de auditoría (conciliación, antigüedad, reproceso, excepciones). | `efectivo_equivalentes.ejecutar(...)` (+ `conciliacion_reestructurada` para el reproceso). |
| **RESULTS** | Cédulas, panel, papeles de trabajo, exportaciones. | `hojas(res)` (14 cédulas) + `caja_bancos_papel` (DA) + `run["exceptions"]`. |

Trazabilidad transversal: cada fila conserva `_file`, `_fileId`, `_sheet`, `_row`; cada cifra derivada del
papel es una fórmula Excel que apunta a su celda de origen; cada problema mapea su celda de origen vía
`REF_PROBLEMAS` (`efectivo_equivalentes.py:631-650`).

---

## 3. Frontend del módulo (vista de 3 pasos)

**No se rediseña la arquitectura visual aprobada** (mockup de 3 pasos, tema oscuro). Lo que se hace en el
frontend es **condensar** la vista actual de la prueba en los 3 bloques del mockup, **solo cuando
`prueba.definicion.processor === "efectivo_equivalentes"`**, dejando intacta la vista genérica para las
otras 19 pruebas.

- Componente afectado: `frontend/src/aud/niif/PruebasEncargo.jsx` (componente `Prueba`, línea 249), que hoy
  apila ConsolaChat + VistaTrabajo + Ejecucion + Revision + ConsolaPrueba + circuito detallado + bitácora.
- Para Efectivo se monta una vista especializada de 3 pasos:
  - **Paso 1 · Requerimientos:** 4 tarjetas de carga (reutilizan `ChipDocumento` de `CicloVista.jsx:101`),
    cada una agrupando su(s) dataset(s) y mostrando estado por requerimiento y cobertura.
  - **Paso 2 · Procesamiento:** botón **Procesar** (verde, `pc-chip accent`) → `producir(...)`
    (`cicloOrquestacion.js`); botón **Encerar** (rojo, `pc-chip danger`) → acción `erase`
    (`servicio.encerar`, `router.py:178`), con confirmación (reutiliza `EncerarEliminar` de `CicloRevision.jsx`).
  - **Paso 3 · Ejecución de auditoría:** 5 tarjetas que, al hacer clic, **abren la vista de trabajo
    detallada** posicionada en la cédula correspondiente (decisión del dueño).
- **Consolas y gobierno:** se quitan de esta vista (siguen disponibles en la vista de trabajo detallada).
- **Tema:** navy oscuro del mockup (fondo `#071B2F`, tarjetas `#0A2342`, botón `#0E2C50`, acentos verde/dorado),
  tomado de las variables `[data-theme="navy"]` de `frontend/src/styles.css` y de la paleta ya usada en
  `.nf-consola-chat` de `fichaNiif.css`.

---

## 4. Datasets (modelo estándar)

Las **4 tarjetas de Requerimientos** del mockup agrupan los **6 datasets** del procesador. El nombre lógico
del prompt (`DS_*`) se mapea así a los datasets reales del código (`DATASETS`, `efectivo_equivalentes.py:120-124`):

| Tarjeta (frontend) | Dataset(s) del código | DS lógico del prompt | RQ |
|---|---|---|---|
| **Anexo de Caja y Bancos** | `cuentas` (principal) | `DS_CAJA_BANCOS` | RQ-001 |
| **Conciliaciones Bancarias** | `partidas` + `conciliacion_anterior` | `DS_CONCILIACIONES` | RQ-002 / RQ-011 |
| **Estados de Cuenta Bancarios** | `estado_cuenta` | `DS_ESTADOS_BANCARIOS` | RQ-010 |
| **Mayores Contables** | `libro_mayor` | `DS_MAYORES` | RQ-009 |
| *(Caja física)* | `arqueo` | `DS_ARQUEO` | RQ-012 |

> `arqueo` no tiene tarjeta propia en el mockup de 4 requerimientos; se mantiene como dataset opcional
> (caja física) y su papel es DA-5. Se decide con el dueño si se expone o se pliega dentro de «Anexo».

---

## 5. Diccionario de campos

Definición por campo: `campo(key, label, tipo, requerido, alias=(...), ejemplo=...)`
(`base.py:20-26`); `tipo ∈ {text, number, date}`; `alias` = sinónimos de encabezado.
**Mapeo flexible:** se sugiere automáticamente por alias (igualdad exacta normalizada, sin acentos ni
símbolos; `cicloLogic.js:90-104`) y el auditor lo confirma; una columna sin coincidencia queda vacía (nunca
se inventa dato). Normalización determinista de montos `.`/`,` (`a_num`) y fechas ISO/`dd/mm/aaaa`/serial
Excel (`a_fecha`).

**`cuentas` (DS_CAJA_BANCOS)** — `efectivo_equivalentes.py:49-68`
`id`(req; alias código/cuenta/cuenta contable), `nombre`(req; banco/descripción), `tipo`(clase/tipo de cuenta),
`saldo_libros`(number, req), `saldo_banco`(number; estado de cuenta/arqueo), `saldo_confirmado`(number),
`restringido`, `monto_restringido`(number), `motivo_restriccion`, `fin_restriccion`(date),
`presentado_separado`, `fecha_adquisicion`(date), `fecha_vencimiento`(date).
*(Brecha B3: falta `moneda` y validaciones de "cuenta sin banco".)*

**`partidas` (DS_CONCILIACIONES)** — `:69-78`
`id`(req), `cuenta`(req), `tipo`(req; concepto), `referencia`(descripción/documento/cheque),
`fecha_origen`(date, req), `importe`(number, req), `fecha_liquidacion`(date).

**`estado_cuenta` (DS_ESTADOS_BANCARIOS)** — `:95-101`
`cuenta`(req), `fecha`(date), `documento`(referencia/concepto/detalle), `debito`(number), `credito`(number).

**`libro_mayor` (DS_MAYORES)** — `:82-92`
`cuenta`(req), `descripcion`, `fecha`(date), `comprobante`, `detalle`, `tercero`, `debito`(number), `credito`(number).

**`conciliacion_anterior`** — `:104-111`
`cuenta`(req), `fecha`(date), `categoria`, `documento`, `valor`(number), `observacion`.

**`arqueo` (DS_ARQUEO)** — `:113-119`
`denominacion`(req), `cantidad`(number), `valor_unitario`(number), `observacion`.

Campos conceptuales del prompt que **no** están hoy y se evaluarán: `MONEDA` (todos), `CENTRO_COSTO`/`AUXILIAR`
(mayor, opcionales), `SALDO`/`FECHA_VALOR` corridos (estado de cuenta).

---

## 6. Flujo de procesamiento (botón Procesar, paso a paso)

Mapa del flujo del prompt (§9) contra lo que hace hoy el ciclo + `ejecutar`:

| Paso del prompt | Hoy | Estado |
|---|---|---|
| 1. Validar que existan los archivos requeridos | Cobertura/huecos (`datos.tool_coverage/tool_gaps`) | COMPLETO |
| 2. Leer todas las fuentes | Lectura de hojas + `filas_mapeadas` | COMPLETO |
| 3. Detectar columnas | `mejorEncabezado`/`mapeoSugerido` (frontend) | COMPLETO |
| 4. Solicitar mapeo cuando sea necesario | UI de mapeo (`ChipDocumento` / convertir formato) | COMPLETO |
| 5. Normalizar formatos | `a_num`/`a_fecha`, signos por tipo | COMPLETO |
| 6. Homologar fechas/monedas/signos/cuentas/refs | fechas/signos/cuentas sí; **moneda no** | PARCIAL (B3) |
| 7. Generar datasets estándar | `reg["datasets"]` normalizados | COMPLETO |
| 8. Relacionar Anexo↔Concil↔Estados↔Mayores | solo partida↔cuenta | **PARCIAL (B3)** |
| 9. Validar integridad | `validation` + guardas de transición | COMPLETO (falta cruce inter-dataset) |
| 10. Preparar datasets de trabajo | `ejecutar(...)` | COMPLETO |
| 11. Habilitar botones de ejecución | guarda `execute` (validation.ok + reconciliation.resolved) | COMPLETO |
| 12. Registrar log completo | eventos del ciclo + `runHash` SHA-256 | COMPLETO (falta huella por archivo, B6) |

**Encerar (botón 6):** `erase` (`servicio.encerar`, `router.py:178`) resetea `reg` (conserva engagement/
país/impuesto, vacía program/requests/rows/run/analysis/conclusion), pone estado `PRUEBA_SELECCIONADA`,
borra archivos y eventos del proceso, `revision += 1`; **bloqueado si la prueba está APROBADA**
(`APROBADA_NO_SE_TOCA`); exige confirmación del nombre del cliente. Cumple el §11 del prompt (no borra
cliente/proyecto/período/metodología).

---

## 7. Lógica de cada botón (ejecución)

**7 · Procedimiento de Efectivo y Equivalentes** — papel general del rubro. Consolida objetivo, riesgos,
aseveraciones (Existencia, Integridad, Derechos y obligaciones, Exactitud, Valuación, Corte, Clasificación,
Presentación), procedimientos, información utilizada, resultados, excepciones, conclusión y referencias.
Hoy: cédulas `01_Resumen` + `13_Conclusion` (indicadores + semáforo) + `14_Lectura` (causa-efecto) + el
programa CAJ-01..08. *Falta: pantalla de procedimiento con marcado de procedimientos completados y registro
de conclusión (se apoya en la vista detallada).*

**8 · Sumaria** — lead sheet por cuenta (fuente `libro_mayor` + `cuentas`). Campos: cuenta, descripción,
saldo inicial, débitos, créditos, saldo final, ajustes, reclasificaciones, saldo auditado, variación
absoluta/porcentual, referencia. Hoy: cédula `10_Efectivo_auditado` + papel **DA-1** (`=E-C` variación,
Ref.→DA-3). *Falta: validaciones "cuenta del anexo no está en mayor" y viceversa (B3).*

**9 · Resumen de Conciliaciones Bancarias** — dashboard por cuenta: banco, cuenta, moneda, saldo banco,
saldo libros, total partidas, saldo conciliado, diferencia, N.º partidas, estado (CONCILIADA / CON
DIFERENCIA / INCOMPLETA / SIN SOPORTE / PENDIENTE DE REVISIÓN), referencia. Hoy: cédula `03_Conciliacion`
+ papel **DA-3**. Fórmula central (existe, `:314-316`):
`esperado = banco + dt − cp − nc + nd + ot`; `dif = libros − esperado`; `ajustado = libros + nc − nd`.
*Falta: campo estado con esa taxonomía y filtros/orden/enlaces a detalle (moneda depende de B3).*

**10 · Análisis de Partidas Conciliatorias** — todas las partidas clasificadas (Cheques girados y no
cobrados, Depósitos en tránsito, Notas de débito, Notas de crédito, Transferencias, Comisiones, Intereses,
Errores, Otras). Antigüedad = `corte − fecha_partida`; tramos configurables (0-30/31-60/61-90/91-180/>180).
Excepciones: antiguas, duplicadas, sin soporte, valores significativos, no regularizadas, recurrentes,
inusuales. Hoy: cédulas `04_Partidas` + `05_Antiguedad` (COUNTIFS/SUMIFS por tramo) + papel **DA-4**.
*Falta: clasificación completa por tipo (hoy usa tipos internos), detección de duplicadas/recurrentes, y
fecha de prescripción parametrizable (B7).*

**11 · Reproceso de Conciliación Bancaria – Último Mes** — ver §8 (matching). Es la brecha principal.

### Botones nuevos (procedimientos ya calculados por el motor, sin botón en el mockup)

Todos exponen una cédula que `ejecutar(...)` ya produce; el botón la abre en la vista detallada (misma
interacción que las tarjetas 8–11). Costo bajo: no hay cálculo nuevo, solo la tarjeta y su enlace.

**12 · Corte de Documentos** — prueba de corte de ingresos/egresos alrededor del cierre (NIA 240 párr. 31 y
Anexo 2). Clasifica cada partida por su ventana de corte (posterior al corte / depósito tardío / etc.) usando
`diasCorte`, `diasLiq`, `diasPost` (`efectivo_equivalentes.py:293-306`). Cédula `07_Corte`.

**13 · Confirmaciones Bancarias** — cotejo de las respuestas de confirmación contra libros (NIA 505):
`difConf`, `estadoConf` por cuenta (`:341-357`); excepciones «sin confirmación / no coincide». Cédula
`06_Confirmaciones`.

**14 · Efectivo Restringido** — fondos pignorados/embargados/con restricción: monto, motivo, fecha de fin,
clasificación y reclasificación (`clasif`, `reclasR`), con revelación. Cédula `08_Restringido`.

**15 · Equivalentes de Efectivo** — clasificación de inversiones como equivalente (plazo ≤ `mesesEquivalente`,
NIC 7 / Sección 7 PYMES): `plazo`, `limite`, `califica`, `reclasNE`. Cédula `09_Equivalentes`.

**16 · Asientos de Ajuste y Reclasificación** — ajustes propuestos y reclasificaciones que llevan del saldo
en libros al saldo auditado. Cédula `11_Asientos`.

**17 · Arqueo de Caja** *(opcional, caja física)* — recuento por denominación (billetes/monedas) y su cuadre
contra el saldo. Cédula `05_Arqueo` / papel `DA-5`.

---

## 8. Matching (Reproceso independiente) — diseño objetivo vs. estado actual

**Objetivo del prompt:** rehacer la conciliación del último mes de forma independiente, cruzando
`DS_ESTADOS_BANCARIOS` + `DS_MAYORES` (+ `DS_CONCILIACIONES` para comparar contra la de la compañía), con
matching por niveles y reconstrucción del cuadre.

**Estado actual (`conciliacion_reestructurada.py`, invocado solo desde el papel DA):**
- Normaliza débito/crédito a la óptica del efectivo (invierte el extracto) — `desde_debito_credito` (`:53-74`).
- Matching **1:1 voraz** por (misma naturaleza) + (|Δvalor| ≤ ½ centavo) + (|Δfecha| ≤ ventana, default 5 días)
  — `_emparejar` (`:89-110`). **La referencia no participa.**
- Clasifica lo no emparejado en 4 categorías (Consignación no registrada, Cheque sin cobrar, NC pendiente,
  ND en tránsito) — `_categoria` (`:113-116`).
- Arrastra partidas abiertas del mes anterior (`conciliacion_anterior`) — `reestructurar` (`:119-181`).

**Diseño objetivo (a construir, B1–B4):**
1. **Matching por niveles** (cascada, cada nivel sobre lo aún no emparejado):
   - N1: valor + fecha + referencia (exacto).
   - N2: valor + fecha.
   - N3: valor + referencia.
   - N4: valor + fecha con tolerancia configurable.
   - N5: 1:N (un movimiento del banco = varios del mayor que suman).
   - N6: N:1 (varios del banco = uno del mayor).
   - Cada match registra: `ID_BANCO`, `ID_MAYOR`, `TIPO_MATCH`, `CRITERIO`, `DIFERENCIA_VALOR`, `DIFERENCIA_DIAS`, `ESTADO`.
2. **Clasificación de resultados:** coincidencias, solo en banco, solo en contabilidad, diferencias de fecha,
   diferencias de valor, posibles duplicados, pendientes, no identificadas.
3. **Reconstrucción numérica en Python** (no solo en fórmulas Excel): `saldo banco ± partidas = saldo
   ajustado` vs `saldo mayor` → `diferencia final`; estado CONCILIADA si |dif| ≤ tolerancia, si no DIFERENCIA
   DE REPROCESO.
4. **Comparación contra la conciliación de la compañía** (`DS_CONCILIACIONES`): partidas omitidas/adicionales,
   diferencias de valor/fecha/clasificación/saldo, partidas no justificadas.
5. **Matriz de resultados por cuenta:** banco, cuenta, saldo banco, saldo mayor, ajustes reprocesados, saldo
   reprocesado, saldo conciliación cliente, diferencia, N.º excepciones.
6. **Conectar al ciclo:** que el reproceso alimente `run["exceptions"]` y el papel (no solo el Excel DA aparte).

Motor determinístico: Python + (pandas/polars si se decide) + numpy. **Sin IA para el matching.**

---

## 9. Trazabilidad

Regla del prompt: `RESULTADO → PRUEBA → REGLA → DATASET → REGISTRO → ARCHIVO → HOJA → FILA`.

- **Registro→archivo→hoja→fila:** `_file/_fileId/_sheet/_row` inyectados por `filas_mapeadas` (`:171`) y
  conservados en cuentas/partidas y en las filas de salida. **COMPLETO.**
- **Resultado→cifra de origen:** fórmulas Excel vivas en todas las cédulas y en el papel DA (SUMIFS entre
  DA-3↔DA-4, `=Sumaria!E..`), más `REF_PROBLEMAS` para el origen del importe de cada problema. **COMPLETO.**
- **Reproducibilidad:** `runHash` = SHA-256 del JSON determinista {definition, rows, parameters, flows, run}
  (`servicio.py:510-514`). **COMPLETO.**
- **Huella por archivo de entrada (NIA 230):** hoy no se genera para efectivo (falta declarar
  `USA_REGISTROS_ENCARGO` o un equivalente). **A construir (B6).**

---

## 10. Estados y control

Estados del ciclo hoy (13, `reglas.py:33-38`) con guardas de transición; `execute` exige datos validados y
conciliados. Se **mapea/expone** la taxonomía del prompt sin romper la existente:

- **Requerimiento:** PENDIENTE / CARGADO / VALIDANDO / VALIDADO / ERROR ← derivado de cobertura
  (`coverage/gaps`), estado del archivo (recibido/rechazado) y `reg["validation"]`.
- **Prueba de ejecución:** BLOQUEADA (antes de Procesar) / DISPONIBLE / PROCESANDO / EJECUTADA / CON
  EXCEPCIONES (`run.exceptions` no vacío) / REVISADA (EN_REVISION/APROBADO).

Log de auditoría: eventos del ciclo (usuario, fecha/hora, acción, estado anterior/nuevo) + `runHash`.
No sobrescribir evidencia: cada carga conserva versión (el ciclo versiona por `revision`).

Manejo de errores (prompt §32): no mostrar «ERROR» crudo; mostrar Archivo / Problema / Acción + botón
[MAPEAR CAMPOS]. Hoy `erroresLegibles` (`cicloLogic.js:107`) ya humaniza; se completa el patrón Archivo/
Problema/Acción en la vista nueva.

---

## 11. Exportaciones

El prompt pide como mínimo: `SUMARIA.xlsx`, `RESUMEN_CONCILIACIONES.xlsx`, `PARTIDAS_CONCILIATORIAS.xlsx`,
`REPROCESO_CONCILIACION.xlsx`, cada uno con trazabilidad. Hoy existen:

- Papel del ciclo (14 cédulas) en **Excel/HTML/Word/PowerPoint/PDF** (`GET /pruebas/{id}/libro`).
- Papel **DA formulado** (DA-1..DA-6 + Libro Mayor) en Excel (`GET /pruebas/{id}/papel-bancos`).

*A construir:* exportaciones por prueba individual (Sumaria / Resumen conciliaciones / Partidas / Reproceso)
si el dueño las quiere como archivos separados, además del papel consolidado. El reproceso robustecido
alimenta `REPROCESO_CONCILIACION.xlsx`.

---

## 12. Testing (obligatorio)

Casos del prompt §36 a cubrir con pruebas deterministas (pytest) y verificación LibreOffice (0 diferencias):
archivo correcto / vacío; columnas y nombres distintos; duplicados; nulos; fechas inválidas; diferencias
banco/mayor; conciliación cuadrada y descuadrada; múltiples cuentas y bancos; varias monedas; partidas
antiguas; matching 1:1, 1:N, N:1; reproceso; encerar; recarga de archivos.

Base existente: `tests/` del rubro efectivo + verificadores (`scripts/verificar_*`). Se amplía con casos de
matching por niveles y comparación contra la conciliación de la compañía.

---

## 13. Plan de implementación por etapas (para aprobar)

> Todo determinista; sin IA en cálculos; sin rediseñar frontend ni cambiar botones; sin reglas de un solo
> cliente como si fueran generales. Cada etapa se cierra con verificación empírica (pytest + LibreOffice).

| Etapa | Entregable | Toca |
|---|---|---|
| **E0** | Este documento aprobado + confirmación de decisiones abiertas (§14). | — |
| **E1 — Ingesta/validación cruzada (B3)** | Validaciones inter-dataset (estado/mayor/concil ↔ cuentas), moneda opcional, mensajes Archivo/Problema/Acción. | `efectivo_equivalentes.py`, `ciclo/*` |
| **E2 — Motor de reproceso por niveles (B1)** | Matching N1–N6 con referencia, 1:N/N:1, registro por match, clasificación completa, tolerancias parametrizables. | `conciliacion_reestructurada.py` (reescritura ampliada) |
| **E3 — Reconstrucción y comparación (B2, B4)** | Cuadre reprocesado en Python, comparación vs conciliación de la compañía, matriz de resultados, conexión a `run.exceptions`. | `conciliacion_reestructurada.py`, `caja_bancos_armado.py`, `efectivo_equivalentes.py` |
| **E4 — Partidas y prescripción (B7)** | Clasificación por tipo completa, duplicadas/recurrentes, prescripción parametrizable. | `efectivo_equivalentes.py` |
| **E5 — Estados y trazabilidad (B5, B6)** | Exponer estados del prompt; huella SHA-256 por archivo de entrada. | `ciclo/*`, `servicio.py` |
| **E6 — Exportaciones** | Papeles por prueba + `REPROCESO_CONCILIACION.xlsx`. | `caja_bancos_papel.py`, `router.py`, `api.js` |
| **E7 — Frontend 3 pasos (B8)** | Vista especializada de Efectivo (3 pasos, tema oscuro, tarjetas → vista detallada), sin consolas. | `PruebasEncargo.jsx`, `CicloVista.jsx`, `fichaNiif.css` |
| **E8 — QA** | Suite completa §36, verificación LibreOffice, build frontend, revisión. | `tests/`, `scripts/` |

---

## 14. Dudas que realmente impiden continuar (para el dueño)

1. **Tolerancias del reproceso:** ¿ventana de días para el matching (hoy 5) y tolerancia de valor (hoy ½
   centavo) las fija la firma como política, o se parametrizan por encargo?
2. **Moneda:** ¿los clientes manejan cuentas en más de una moneda (USD y otra)? Si no, `moneda` queda opcional
   informativa; si sí, define la regla de conversión/segregación.
3. **1:N / N:1:** ¿hasta qué tamaño de agrupación buscar (ej. combinaciones de hasta N movimientos)? A mayor N,
   más costo; conviene un tope razonable.
4. **Comparación vs la compañía:** ¿la conciliación del cliente llega estructurada (dataset `partidas`) o como
   PDF/soporte? De eso depende cuánto se puede comparar automáticamente.
5. **`arqueo`/caja física:** ¿se expone como 5.ª tarjeta de requerimiento o se pliega dentro de «Anexo»?
6. **Exportaciones separadas:** ¿quieres archivos por prueba (Sumaria/Resumen/Partidas/Reproceso) además del
   papel consolidado y el DA?

---

*Fin del documento. La implementación NO empieza hasta la aprobación del dueño.*
