# Encargo: catálogo de pruebas de auditoría NIIF (completas y PYMES)

**Para:** ChatGPT
**De:** AuditConsulting Auditores Cía. Ltda. — plataforma AUDIT-IA
**Uso del resultado:** cada ficha que entregues se carga en el Command Center de
AUDIT-IA, que la convierte en una herramienta ejecutable y la publica en el
catálogo de su cuenta contable. Por eso la estructura de este documento **no es
opcional**: cualquier dato que falte o que no respete el formato obliga a
devolver la ficha.

---

## 1 · Qué te pedimos

Construir el catálogo completo de **pruebas sustantivas de auditoría** sobre la
aplicación de las NIIF, en sus dos marcos:

- **NIIF completas** (NIC, NIIF, CINIIF vigentes emitidas por el IASB).
- **NIIF para las PYMES** (edición vigente; indicar la edición usada).

Contexto: auditoría de estados financieros en **Ecuador**, moneda **USD**,
normas de auditoría **NIA**. Cuando la prueba tenga efecto tributario, señalar
la norma ecuatoriana (LRTI, RALRTI, resoluciones del SRI).

### Entrega en tres pasos

1. **Índice** (una sola respuesta): tabla de todas las pruebas, agrupadas por
   cuenta. Columnas: código · nombre de la prueba · cuenta · norma NIIF
   completas (NIC/NIIF y párrafos) · sección NIIF PYMES equivalente · ¿aplica
   en ambos marcos o solo en uno? · complejidad (baja/media/alta).
2. **Fichas**, una por prueba y **un archivo Markdown por ficha**, en lotes por
   cuenta. Nombre del archivo: `<código>_<nombre-corto>.md`
   (ej. `INV-01_valor-neto-realizacion.md`).
3. Al final de cada lote, la **lista de control** de la sección 6, llena.

### Cuentas mínimas que debe cubrir el índice

Efectivo y equivalentes · Instrumentos financieros y cuentas por cobrar
(incluida la pérdida crediticia esperada) · Inventarios · Propiedades, planta y
equipo · Propiedades de inversión · Activos intangibles · Deterioro de activos
(NIC 36 / Secc. 27) · Arrendamientos · Activos biológicos · Inversiones en
asociadas y negocios conjuntos · Cuentas por pagar y préstamos (costo
amortizado) · Provisiones y contingencias · Beneficios a empleados (incluida
jubilación patronal y desahucio) · Impuesto a las ganancias e impuesto diferido ·
Ingresos de contratos con clientes · Patrimonio · Moneda extranjera · Hechos
posteriores · Partes relacionadas · Presentación y revelaciones.

Si una cuenta necesita varias pruebas (por ejemplo, PP&E: depreciación,
vidas útiles, bajas, revaluación), cada una es una ficha distinta.

---

## 2 · Estructura obligatoria de cada ficha

Cada ficha tiene **cinco bloques, en este orden**. Es el mismo orden en que el
auditor la ve en pantalla: primero la norma, luego lo que se pide al cliente,
luego la carga de los documentos y al final el procesamiento.

### Bloque A · Base técnica (lo que dice la norma)

| Dato | Contenido |
|---|---|
| Código y nombre | `INV-01 · Valor neto de realización` |
| Cuenta | La cuenta del catálogo (una sola) |
| Objetivo de la prueba | Una o dos frases |
| Norma NIIF completas | Norma y **párrafos exactos** (ej. NIC 2 párr. 9, 28–33) |
| Norma NIIF PYMES | Sección y **párrafos exactos** (ej. Secc. 13 párr. 13.19; Secc. 27 párr. 27.2–27.4) |
| Diferencias entre marcos | Qué cambia en la prueba si el cliente aplica PYMES. Si no cambia nada, decirlo |
| Resumen técnico | Qué exige la norma, **con tus palabras** (no copies el texto de la norma), en 5 a 12 líneas |
| NIA aplicables | Ej. NIA 500, NIA 540 (estimaciones), NIA 501 (inventarios) |
| Tributario Ecuador | Norma y artículo, o «No aplica» |
| Fuentes oficiales | Enlaces **HTTPS** solo de `ifrs.org` (normas) y `iaasb.org` / `ifac.org` (NIA). Para tributario, `sri.gob.ec` |

**Regla de honestidad:** si no estás seguro de un número de párrafo, escribe
`VERIFICAR` al lado. Un párrafo inventado es peor que uno marcado para revisar.

### Bloque B · Programa de auditoría

De 3 a 8 procedimientos. Una fila por procedimiento:

| Campo | Contenido |
|---|---|
| `code` | `<código de la prueba>-01`, `-02`… (ej. `INV01-01`) |
| `objective` | Qué se busca |
| `risk` | Riesgo que cubre |
| `assertion` | Afirmación: Existencia, Integridad, Valoración, Exactitud, Corte, Derechos y obligaciones, Presentación |
| `procedure` | Qué hace el auditor, paso a paso |
| `evidence` | Evidencia que se obtiene |
| `criterion` | Cuándo se da por satisfecho el procedimiento |
| `source` | Norma y párrafo que lo sustenta |

El **procedimiento 01 siempre es integridad**: conciliar la población con el
saldo contable al corte.

### Bloque C · Requerimientos de información al cliente

Una fila por documento que el cliente debe entregar:

| Campo | Contenido |
|---|---|
| `id` | `RQ-001`, `RQ-002`… |
| `document` | Nombre del documento, claro para el cliente (ej. «Inventario valorado al 31-12-2025») |
| `purpose` | Para qué lo usa el auditor |
| `procedure` | `code` del procedimiento del Bloque B que lo usa (obligatorio, debe existir) |
| `formats` | Lista solo con: `xlsx`, `csv`, `pdf`, `docx`, `xml`, `txt`, `md`, `zip`, `png`, `jpg`, `webp` |
| `required` | `true` / `false` |
| `components` | Opcional: partes en que se entrega **un mismo reporte**, un archivo por parte con el mismo formato (ej. `["Quito", "Guayaquil", "Cuenca"]` por bodega, o `["Enero", …, "Diciembre"]` por mes). La herramienta **une todas las partes en una sola población** al procesar. Si no aplica, `[]` |
| `group` | Opcional: agrupa requerimientos alternativos (ej. «Precios» si sirve la lista de precios **o** las facturas posteriores) |
| `use` | `calculo` si la herramienta **procesa** ese archivo; `soporte` si el auditor solo lo revisa |
| `report` | El reporte exacto y de dónde sale: módulo o informe típico del sistema contable, o quién lo prepara (ej. «Kardex valorado exportado del módulo de inventarios») |
| `cutoff` | Fecha o período que debe cubrir (ej. «al 31-12-2025», «enero a marzo 2026 para hechos posteriores») |
| `content` | Contenido mínimo para aceptarlo |

**`RQ-001` es siempre la población** que se procesa (`use: calculo`): un archivo
`xlsx` o `csv`, una fila por partida.

**Modelo para el cliente.** Con la tabla de columnas, la plataforma genera un
**modelo Excel** por cada requerimiento de cálculo (hoja «Datos» con esas
columnas exactas y hoja «Instrucciones»), que el auditor envía al cliente para
que todos entreguen igual. Por eso los nombres de columna deben ser claros y
estables.

**Todo requerimiento con `use: calculo`** debe traer además la **tabla de
columnas**: nombre de la columna tal como la verá el cliente, `key` del campo
del Bloque E al que corresponde, tipo (número, fecha AAAA-MM-DD o texto), si es
obligatoria y un valor de ejemplo. Con esa tabla el cliente sabe exactamente qué
exportar y el sistema propone el mapeo de columnas solo. Si la prueba usa
flujos con fechas (sección 3.3), el calendario de pagos es un segundo
requerimiento de cálculo con las columnas contrato, fecha del pago e importe.

Ninguna columna que use un cálculo puede faltar en la tabla, y ninguna columna
de la tabla puede quedar sin usar.

### Bloque D · Carga de documentos (botones)

Por cada requerimiento del Bloque C, qué debe revisar el auditor al recibirlo
(esto se muestra junto al botón de subida):

- Qué debe contener el archivo para aceptarlo.
- Motivos para **rechazarlo** (ej. «sin fecha de corte», «no cuadra con el mayor»).
- Si es tabular, qué hoja y desde qué fila empiezan los datos, si es habitual.

### Bloque E · Procesamiento

Aquí está lo que ejecuta el motor. Tiene que respetar **exactamente** las
reglas de la sección 3.

1. **Campos de la población** (`fields`): de 2 a 25. Uno de ellos se llama
   `id`, es de tipo `text` e identifica cada partida.
2. **Parámetros** que aprueba el auditor (tasas, tolerancia, materialidad) y de
   dónde salen.
3. **Cálculos** (`rules`): de 1 a 25, en orden; cada uno explicado en una
   frase de lenguaje contable.
4. **Campo de conciliación** (`control`): una **columna numérica de la
   población** (no un cálculo) que se suma y se compara con el mayor contable
   (ej. el costo total según el inventario del cliente).
5. **Resultado principal** (`primary`): el cálculo que es el hallazgo (ej. el
   ajuste propuesto).
6. **Criterio de excepción**: cuándo una partida es excepción (ej. «ajuste
   distinto de cero» o «diferencia mayor a la tolerancia»).
7. **Cédulas** que genera: de la lista de la sección 3.4.
8. **Conclusión tipo**: el texto modelo de conclusión, con los espacios para
   los valores.
9. **Bloque JSON** de la sección 4, al final de la ficha, con `summary`
   (el resumen técnico del bloque A) y `nia` (la lista de NIA aplicables).

---

## 3 · Reglas del motor de cálculo (no negociables)

El motor es **determinista**: hace aritmética exacta partida por partida. No
interpreta texto ni ejecuta fórmulas libres.

### 3.1 Campos

- `key`: minúsculas, números y guion bajo, empieza con letra, máximo 36
  caracteres, sin espacios ni tildes (ej. `unit_cost`, `fecha_compra`).
- `type`: solo `number`, `date` (formato AAAA-MM-DD) o `text`.
- `label`: el nombre visible, en español.
- `required`: `true` / `false`. `positive`: `true` si el número no puede ser negativo.
- `aliases` (opcional): otros nombres con que suele venir esa columna en los
  reportes de los clientes (ej. `["Cod.", "Código producto"]`); ayudan a
  reconocerla si el cliente no usa el modelo.
- `example` (opcional): un valor de ejemplo, que aparece en el modelo.
- Si la población viene por bodega, sucursal o mes y conviene verlo en las
  cédulas, declare también un campo de texto para eso (ej. `ubicacion`).
- Prohibidas como clave: `constructor`, `prototype`, `__proto__`.

### 3.2 Cálculos

Cada cálculo es `{ "key", "label", "op", "a", "b", "precision" }`:

- `a` y `b`: un campo numérico, un cálculo **anterior**, o una constante
  escrita `#` + número (ej. `#0`, `#12`, `#0.15`, `#-1`).
- `precision`: `2` para importes, `6` para unitarios, tasas y factores.
- Un cálculo con dos operandos por paso. Una fórmula larga se parte en varios
  pasos encadenados.

Operaciones (`op`) disponibles:

| `op` | Qué hace | Ejemplo |
|---|---|---|
| `add`, `subtract`, `multiply`, `divide` | Suma, resta, multiplica, divide A y B | costo total = cantidad × costo unitario |
| `min`, `max` | El menor o el mayor entre A y B | VNR mínimo cero: `max(vnr, #0)` |
| `gt`, `gte`, `lt`, `lte`, `eq` | Compara A con B (mayor, mayor o igual, menor, menor o igual, igual) y da **1 si se cumple, 0 si no**. Sumadas en la sumaria, cuentan partidas | vencida = `gt(dias_mora, #90)` |
| `if` | **Si A no es cero** toma B; si no, toma **C**. Lleva un tercer operando `"c"` | ajuste = `if(vencida, pce, #0)` |
| `days` | **Días desde A hasta B**. A y B son campos de tipo `date` o la palabra `corte` (la fecha de corte del encargo) | días de mora = `days(due_date, corte)` |
| `band` | **Tramos**: devuelve el `value` del último tramo cuyo `from` no supera a A. Solo usa `a` y una tabla `"table"` en orden creciente de `from`. Un valor por debajo del primer tramo es un error, así que el primer `from` debe cubrir todo el rango posible | tasa por mora: `[{"from":"0","value":"0.01"},{"from":"31","value":"0.05"},{"from":"91","value":"0.2"}]` |

Ejemplo de pérdida crediticia por antigüedad (NIIF 9 enfoque simplificado):

```json
"rules": [
  { "key": "dias", "label": "Días desde el vencimiento", "op": "days", "a": "due_date", "b": "corte", "precision": 2 },
  { "key": "dias_mora", "label": "Días de mora", "op": "max", "a": "dias", "b": "#0", "precision": 2 },
  { "key": "tasa", "label": "Tasa del tramo", "op": "band", "a": "dias_mora", "precision": 6,
    "table": [ { "from": "0", "value": "0.01" }, { "from": "31", "value": "0.05" }, { "from": "91", "value": "0.2" }, { "from": "181", "value": "0.5" }, { "from": "361", "value": "1" } ] },
  { "key": "pce", "label": "Pérdida esperada", "op": "multiply", "a": "exposure", "b": "tasa", "precision": 2 },
  { "key": "vencida", "label": "Más de 90 días", "op": "gt", "a": "dias_mora", "b": "#90", "precision": 2 },
  { "key": "ajuste", "label": "Ajuste frente a provisión", "op": "subtract", "a": "pce", "b": "recorded_allowance", "precision": 2 }
]
```

**Lo que el motor todavía NO hace:** cruces entre filas (por ejemplo, sumar
todas las facturas de un mismo cliente), búsquedas en otra tabla del cliente,
potencias fuera de los flujos, ni redondeos especiales. Si una prueba lo
necesita, **no lo disfraces**: escribe una sección
**«Requiere ampliar el motor»** describiendo exactamente la lógica (con un
ejemplo numérico) y entrega igual el resto de la ficha. Nosotros ampliamos el
motor antes de publicarla.

### 3.3 Series por períodos y flujos descontados (solo si la prueba lo necesita)

- **Serie** (cuadros de amortización, depreciación período a período):
  `"series": { "count": "<campo con el número de períodos>", "forward": [...], "backward": [...] }`.
  Dentro de la serie, `@clave` es el valor de ese cálculo en el período
  anterior, `^clave` el del primer período, y están disponibles `periodo` y
  `periodos`. `seed` fija el valor inicial. Máximo 40 cálculos. El motor crea
  `<clave>_inicial`, `<clave>_final` y `<clave>_total` para usarlos en los
  cálculos normales.
- **Flujos con fechas** (valor presente de pagos irregulares, NIIF 16, NIIF 9,
  NIC 37): `"flows": { "date": "<campo fecha de medición>", "rate": "<campo tasa anual>" }`.
  Los pagos se cargan en un archivo aparte (contrato, fecha, importe). Convención
  **actual/365**. El motor entrega `flujos_vp`, `flujos_total` y `flujos_dias`.

### 3.4 Cédulas disponibles

`01_Caratula`, `02_Programa`, `03_Parametros`, `04_Fuentes`, `05_Data_Original`,
`06_Data_Procesada`, `07_Calculos`, `08_Pruebas`, `09_Excepciones`,
`10_Sumaria`, `11_Conclusion`, `12_Control_Revision`, `13_Cuadro` (solo con
serie).

---

## 4 · Bloque JSON (al final de cada ficha)

Un único bloque de código `json` con la definición. Debe ser JSON válido (sin
comentarios ni comas sobrantes). Este es el ejemplo real de la prueba de valor
neto de realización que ya funciona en la plataforma; úsalo como modelo:

```json
{
  "id": "inv01",
  "name": "Valor neto de realización",
  "area": "Inventarios",
  "framework": ["NIIF completas", "NIIF para las PYMES"],
  "description": "Compara el costo con el precio estimado de venta menos los costos de terminación y venta, por partida.",
  "summary": "La NIC 2 exige medir los inventarios al menor entre costo y valor neto de realización; el VNR es el precio estimado de venta menos los costos de terminación y los necesarios para la venta. La rebaja se reconoce partida por partida y se revierte si las circunstancias cambian.",
  "nia": ["NIA 500", "NIA 501", "NIA 540"],
  "source": {
    "organization": "IFRS Foundation",
    "document": "NIC 2 Inventarios, párr. 9 y 28-33",
    "url": "https://www.ifrs.org/issued-standards/list-of-standards/ias-2-inventories/",
    "type": "Norma contable"
  },
  "source_pymes": {
    "organization": "IFRS Foundation",
    "document": "NIIF para las PYMES, Sección 13 párr. 13.19 y Sección 27 párr. 27.2-27.4",
    "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/",
    "type": "Norma contable"
  },
  "fields": [
    { "key": "id", "label": "Código / lote", "type": "text", "required": true, "positive": false, "aliases": ["Código", "Cod. producto"], "example": "INV-0001" },
    { "key": "description", "label": "Descripción", "type": "text", "required": true, "positive": false },
    { "key": "quantity", "label": "Cantidad", "type": "number", "required": true, "positive": true },
    { "key": "unit_cost", "label": "Costo unitario", "type": "number", "required": true, "positive": false },
    { "key": "selling_price", "label": "Precio de venta unitario", "type": "number", "required": true, "positive": false },
    { "key": "completion_cost", "label": "Costo de terminación unitario", "type": "number", "required": true, "positive": false },
    { "key": "selling_cost", "label": "Costo necesario de venta unitario", "type": "number", "required": true, "positive": false },
    { "key": "recorded_allowance", "label": "Deterioro registrado total", "type": "number", "required": true, "positive": false },
    { "key": "book_cost", "label": "Costo total según inventario", "type": "number", "required": true, "positive": true }
  ],
  "rules": [
    { "key": "net_price", "label": "Precio menos terminación", "op": "subtract", "a": "selling_price", "b": "completion_cost", "precision": 6 },
    { "key": "nrv_unit", "label": "VNR unitario", "op": "subtract", "a": "net_price", "b": "selling_cost", "precision": 6 },
    { "key": "nrv_floor", "label": "VNR recuperable (mínimo cero)", "op": "max", "a": "nrv_unit", "b": "#0", "precision": 6 },
    { "key": "carrying_unit", "label": "Menor entre costo y VNR", "op": "min", "a": "unit_cost", "b": "nrv_floor", "precision": 6 },
    { "key": "cost", "label": "Costo total", "op": "multiply", "a": "quantity", "b": "unit_cost", "precision": 2 },
    { "key": "recoverable", "label": "Valor recuperable total", "op": "multiply", "a": "quantity", "b": "carrying_unit", "precision": 2 },
    { "key": "impairment", "label": "Deterioro requerido", "op": "subtract", "a": "cost", "b": "recoverable", "precision": 2 },
    { "key": "adjustment", "label": "Ajuste frente a deterioro registrado", "op": "subtract", "a": "impairment", "b": "recorded_allowance", "precision": 2 },
    { "key": "cost_difference", "label": "Diferencia costo recalculado vs. inventario", "op": "subtract", "a": "cost", "b": "book_cost", "precision": 2 }
  ],
  "control": "book_cost",
  "primary": "adjustment",
  "exception": "adjustment distinto de cero",
  "sheets": ["01_Caratula", "02_Programa", "03_Parametros", "04_Fuentes", "05_Data_Original", "06_Data_Procesada", "07_Calculos", "08_Pruebas", "09_Excepciones", "10_Sumaria", "11_Conclusion", "12_Control_Revision"],
  "program": [
    { "code": "INV01-01", "objective": "Integridad de la población", "risk": "Población incompleta", "assertion": "Integridad", "procedure": "Conciliar el inventario valorado con el saldo del mayor al corte.", "evidence": "Inventario valorado y mayor contable", "criterion": "Diferencia dentro de la tolerancia aprobada o aceptación documentada.", "source": "NIA 500 párr. A49" },
    { "code": "INV01-02", "objective": "Valorar al menor entre costo y VNR", "risk": "Inventario sobrevaluado", "assertion": "Valoración", "procedure": "Recalcular el VNR por partida y compararlo con el costo.", "evidence": "Precios de venta y costos de terminación y venta", "criterion": "Ajuste recalculado por partida.", "source": "NIC 2 párr. 9 y 28-33" },
    { "code": "INV01-03", "objective": "Evaluar supuestos y deterioro registrado", "risk": "Supuestos sin sustento", "assertion": "Exactitud", "procedure": "Verificar precios con ventas posteriores y contrastar el deterioro registrado.", "evidence": "Facturas posteriores, política contable", "criterion": "Excepciones resueltas y conclusión documentada.", "source": "NIA 540" }
  ],
  "requests": [
    { "id": "RQ-001", "document": "Inventario valorado al corte (una fila por ítem, con las 9 columnas de la población)", "purpose": "Población de la prueba", "procedure": "INV01-01", "formats": ["xlsx", "csv"], "required": true, "components": [], "group": "", "use": "calculo", "report": "Kardex o inventario valorado exportado del módulo de inventarios", "cutoff": "Al cierre del ejercicio" },
    { "id": "RQ-002", "document": "Lista de precios de venta vigente al corte", "purpose": "Sustentar el precio estimado de venta", "procedure": "INV01-02", "formats": ["xlsx", "csv", "pdf"], "required": true, "components": [], "group": "Precios", "use": "soporte", "report": "Lista de precios del área comercial", "cutoff": "Vigente al cierre" },
    { "id": "RQ-003", "document": "Facturas de venta posteriores al corte (muestra)", "purpose": "Sustentar el precio estimado de venta", "procedure": "INV01-02", "formats": ["pdf", "xml", "zip"], "required": true, "components": [], "group": "Precios", "use": "soporte", "report": "Facturas electrónicas emitidas (XML del SRI o PDF)", "cutoff": "Hasta 60 días después del cierre" },
    { "id": "RQ-004", "document": "Política contable de inventarios y cálculo del deterioro registrado", "purpose": "Contrastar el deterioro registrado", "procedure": "INV01-03", "formats": ["pdf", "docx", "xlsx"], "required": true, "components": [], "group": "", "use": "soporte", "report": "Política contable aprobada y hoja de cálculo del deterioro", "cutoff": "Vigente al cierre" }
  ]
}
```

---

## 5 · Plantilla de ficha (copiar para cada prueba)

~~~markdown
# <CÓDIGO> · <Nombre de la prueba>

## A · Base técnica
| Dato | Contenido |
|---|---|
| Cuenta | |
| Objetivo | |
| NIIF completas | |
| NIIF PYMES | |
| Diferencias entre marcos | |
| NIA aplicables | |
| Tributario Ecuador | |
| Fuentes oficiales | |

**Resumen técnico:** …

## B · Programa de auditoría
| code | objective | risk | assertion | procedure | evidence | criterion | source |
|---|---|---|---|---|---|---|---|

## C · Requerimientos al cliente
| id | document | purpose | procedure | formats | required | components | group |
|---|---|---|---|---|---|---|---|

**Columnas de cada requerimiento de cálculo:**

| Columna en el archivo | key | Tipo | Obligatoria | Ejemplo |
|---|---|---|---|---|

## D · Carga de documentos
### RQ-001
- Aceptar si: …
- Rechazar si: …

## E · Procesamiento
1. Campos: …
2. Parámetros: …
3. Cálculos (explicados): …
4. Conciliación (`control`): …
5. Resultado principal (`primary`): …
6. Criterio de excepción: …
7. Cédulas: …
8. Conclusión tipo: …

### Ejemplo numérico
Tres partidas con valores inventados y el resultado esperado de cada cálculo,
para que podamos comprobar que el motor da lo mismo.

### Requiere ampliar el motor
(Solo si aplica. Si no, escribir «No».)

## JSON
```json
{ … }
```
~~~

El **ejemplo numérico** es obligatorio: con él comprobamos que la herramienta
publicada calcula exactamente lo que dice la ficha.

---

## 6 · Lista de control (llenar al final de cada lote)

| Control | Sí / No |
|---|---|
| Cada ficha tiene los bloques A, B, C, D, E y el JSON, en ese orden | |
| Todos los párrafos citados existen, o están marcados `VERIFICAR` | |
| Las fuentes son HTTPS de ifrs.org, iaasb.org, ifac.org o sri.gob.ec | |
| El marco PYMES está cubierto (o se explica por qué la prueba no aplica) | |
| `RQ-001` es la población tabular y sus columnas coinciden con `fields` |
| Cada requerimiento dice `use`, `report` y `cutoff`; los de cálculo traen su tabla de columnas | |
| Cada requerimiento apunta a un `code` que existe en el programa | |
| Hay un campo `id` de tipo `text` | |
| Solo se usan las operaciones de la sección 3.2 y constantes con `#`; los `band` cubren todo el rango y los `if` traen `c` | |
| Cada cálculo usa campos o cálculos anteriores, nunca posteriores | |
| `control` es una columna numérica de la población (no un cálculo) y `primary` es un cálculo | |
| El JSON es válido | |
| El ejemplo numérico cuadra con los cálculos | |
| Lo que el motor no puede hacer está en «Requiere ampliar el motor» | |
