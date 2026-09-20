# Motor de cálculo NIIF — diseño

2026-09-19 · sitio AuditBrain (`auditbrain-site`), versión publicada 25

## 1 · Qué problema resuelve

El motor actual solo sabe aritmética de dos operandos por fila: `add`, `subtract`,
`multiply`, `divide`, `min`, `max`. Con eso no se puede medir un arrendamiento,
ni el costo amortizado de una cartera, ni una provisión descontada. El 19 de
septiembre se le añadieron **series por períodos**, que cubren la recurrencia,
pero siguen asumiendo períodos enteros y flujos nivelados.

Este diseño define hasta dónde llega el motor y, sobre todo, **dónde se corta**.

## 2 · Decisiones tomadas

Tres decisiones del dueño, que condicionan todo lo demás:

| Decisión | Consecuencia de diseño |
|---|---|
| **Cada cálculo se implementa en todos los motores.** El servidor y Python se **contrastan** entre sí; el portátil es una **copia generada** del servidor que no debe divergir (D1) | El motor tiene que ser **declarativo**: lo que se escribe tres veces es el vocabulario, no cada norma. Un motor de propósito general exigiría escribir cada norma tres veces, en dos lenguajes |
| **El auditor escribe la definición** en el Diseñador | El motor debe **hacer visible el error**. No se puede suponer que quien escribe entiende una recurrencia |
| **El éxito se mide con una batería de casos de referencia** | Una norma se declara soportada cuando su caso numérico pasa en los tres motores, no antes |

Cartera del despacho: **70% NIIF completas, 30% NIIF para las PYMES**. Por eso
NIIF 16 conserva prioridad alta.

## 3 · Restricción dura: son tres motores, no dos

| Motor | Aritmética | Quién lo ejecuta |
|---|---|---|
| `lib/tools/domain.mjs` | BigInt, escala 1e6 | Worker de Cloudflare — **la autoridad** |
| `public/engine/audit_engine.py` | `Decimal`, precisión 50 | Pyodide, navegador del auditor |
| `lib/tools/portable-engine.mjs` | BigInt, copia del primero | Navegador de quien abra el HTML descargado |

El tercero se genera con `Function.prototype.toString()` sobre funciones de
`domain.mjs` (`scripts/export-portable-engine.mjs`). **Eso obliga a que el motor
sea funciones de nivel superior autocontenidas: sin imports, sin closures, sin
clases.** Es la restricción que descarta un intérprete de propósito general.

## 4 · Arquitectura: dos capas

### Capa 1 · Vocabulario declarativo

El auditor lo compone en el Diseñador. Cubre las primitivas de mayor reuso.

| Primitiva | Qué añade | Normas que desbloquea |
|---|---|---|
| **Serie por períodos** *(ya construida)* | Pases `backward`/`forward`, operandos `@anterior` y `^primero`, semilla de borde, orden declarable | NIIF 16.36 · NIIF 9.5.4.1 · NIC 37.60 · NIIF 15.60 · NIC 19.120(b) · NIIF 2.20 |
| **Flujos irregulares con fechas** | Una **segunda población** que el cliente entrega como calendario de pagos: filas `{contrato, fecha, importe}`, vinculadas por el identificador del contrato. Sustituye al período entero: el descuento va por días reales. La población principal sigue siendo una fila por contrato | NIIF 16.26/27 · NIC 36.31/33 · NIC 37.45 · NIIF 9.5.4.3 |
| **Resolución de raíz** | Declara la incógnita (una tasa), el vector de flujos y el objetivo | NIIF 9 Ap. A (TIE y TIE ajustada por crédito) · NIIF 16 Ap. A (TIIA) · NIC 36.A20 (tasa antes de impuestos) |
| **Matriz** | Celdas de dos dimensiones —tramo de mora × segmento— con su tasa | NIIF 9.B5.5.35 · NIC 12.47/51 |
| **Ponderación de escenarios** | Lista de escenarios con probabilidad, y **modo declarado**: valor esperado o importe más probable | NIIF 9.5.5.17 · NIIF 15.53 · NIC 37.39/40 · NIC 36.A7 |

El modo de la ponderación **se registra en el papel**: NIIF 15.53(b) y NIC 37.40
permiten el importe más probable, y cuál se eligió es materia de revisión.

### Capa 2 · Catálogo cerrado de métodos con nombre

Cálculos que no son operadores sino procedimientos completos. El auditor los
**elige por nombre**; nunca escribe código. Siguen siendo datos.

| Método | Norma | Caso de referencia |
|---|---|---|
| `unidad_de_credito_proyectada` | NIC 19.67/68 | **La tabla publicada por el IASB en el párrafo 68**: 89 / 196 / 324 / 476 / 655 |
| `black_scholes` | NIIF 2.B4/B6 | S=50, K=50, r=5%, q=0, σ=30%, T=4 → call = 15,8246 |

La NIC 19 exige además separar dos bolsas que en Ecuador suelen ir juntas y no
deben: **jubilación patronal** (post-empleo, remediciones a ORI, párr. 120(c)) y
**desahucio** (otro beneficio de largo plazo, remediciones a **resultados**,
párr. 155-156). El método las expone como salidas distintas.

## 5 · Determinismo entre los tres motores

Es donde se cuelan las diferencias. Reglas obligatorias:

- **Nada de coma flotante.** BigInt con escala 1e6 en JavaScript, `Decimal` en Python.
- **Mismo límite de cómputo** que hoy: redondeo a 6 decimales con `ROUND_HALF_UP`, y después a la precisión declarada de la regla.
- **La raíz se busca por bisección con número fijo de iteraciones**, no por Newton-Raphson. Newton converge distinto según el punto de partida; la bisección con intervalo e iteraciones fijos da el mismo resultado en los tres motores.
- **Convención de días explícita y única**: `actual/365`. Las fechas viajan como `AAAA-MM-DD`.
- Ninguna primitiva puede depender del orden de iteración de un diccionario.

## 6 · Las tres deudas, antes de ampliar nada

| # | Deuda | Por qué bloquea |
|---|---|---|
| D1 | **Los tres motores divergen en silencio** | No hay script que regenere el portátil ni prueba que falle al divergir. Se desincronizó el 19-sep sin que nada avisara. Entregable: `npm run engine:export` y una prueba que compare el portátil contra `domain.mjs` |
| D2 | **El contraste es asimétrico** | `app/api/tools/route.ts:69-71` compara solo `rows`, y solo las claves del servidor. `totals` y `exceptions` —que sostienen la sumaria y el bloqueo de aprobación— **nunca se contrastan**. Entregable: comparar la unión de claves e incluir `totals` y `exceptions`; Python debe calcularlos |
| D3 | **`run.schedule` no tiene dónde vivir** | Se calcula, se guarda y no lo lee nadie. Entregable: cédula propia del cuadro en el libro, generada desde ese arreglo, en vez de forzar los períodos dentro de `07_Calculos` |

D2 tiene un efecto inmediato: **hoy toda herramienta con serie falla la ejecución**
con el mensaje «La ejecución Python no coincide», porque `audit_engine.py` no
implementa series y la comparación recorre las claves del servidor.

## 7 · Guardarraíles, porque la definición la escribe el auditor

Sin esto, una definición mal planteada produce números con apariencia correcta.

- **Vista previa obligatoria**: antes de guardar, el Diseñador muestra la tabla de períodos con datos de ejemplo. Una semilla mal puesta se ve a simple vista.
- **Comprobaciones de cierre automáticas**, emitidas como excepciones del papel: un cuadro de amortización debe cerrar en cero dentro de la tolerancia; el cierre de un período debe enlazar con la apertura del siguiente.
- **Colisiones de nombres rechazadas al validar**, no al ejecutar (ya funciona: cazó dos durante el desarrollo).
- **La tasa y su fuente se guardan como dato de auditoría.** En NIC 19.83 es el input de mayor sensibilidad de toda la valuación.

## 8 · Batería de casos de referencia

Cada primitiva y cada método entra con al menos un caso: entrada, resultado
esperado calculado aparte, y verificación en los tres motores. Casos ya
disponibles, con párrafo verificado contra el HTML oficial de ifrs.org:

| Caso | Norma | Resultado esperado |
|---|---|---|
| Arrendamiento 5×10.000 al 5% | NIIF 16.26/36 | Pasivo 43.294,77; cuadro que cierra en 0,00 |
| Remedición por índice, **tasa sin cambiar** | NIIF 16.42/43 | Nuevo pasivo 28.866,43; ajuste +1.633,95 |
| Modificación que reduce alcance, **tasa revisada** | NIIF 16.45(c)/46(a) | Ganancia 666,59; AUD final 10.390,74 |
| TIE con comisión | NIIF 9 Ap. A · B5.4.1 | 8,507633%; el saldo cierra en 0,00 |
| Valor en uso con valor terminal | NIC 36.31/33/55 | 1.585.872,75 |
| Desmantelamiento a 10 años al 6% | NIC 37.45/60 | Provisión 279.197,39; al año 10 vuelve a 500.000,00 |
| Matriz de provisión, 5 tramos | NIIF 9.B5.5.35 | 37.700,00 sobre 900.000 |
| Valor esperado | NIC 36.A7 | 220 — **ejemplo del propio texto de la norma** |
| Unidad de crédito proyectada | NIC 19.68 | 89 / 196 / 324 / 476 / 655 — **tabla publicada por el IASB** |
| Black-Scholes | NIIF 2.B6 | call 15,8246 |

Los dos últimos son los más valiosos: el resultado esperado lo publica el emisor
de la norma, no lo calculamos nosotros.

## 9 · Fuera de alcance, y por qué

- **Optimización.** Ninguna norma revisada la exige. NIIF 13.61 la menciona como criterio de calibración, no como programa matemático.
- **Monte Carlo y árboles binomiales.** NIIF 2.B5 advierte que Black-Scholes puede no bastar con ejercicio anticipado, pero ese es el momento de contratar un valuador, no de construir un motor. Solo se implementa Black-Scholes cerrado.
- **Reescribir el generador de Excel.** `lib/tools/exports.mjs` arma `07_Calculos` fórmula a fórmula asumiendo una regla = una columna y operadores de dos operandos. Se conserva tal cual: el cuadro va a su **cédula propia** (D3), no dentro de esa hoja.

## 10 · Orden de construcción

**Este diseño es mayor que un solo plan de implementación.** Se parte en dos:
la **fase 1** son los puntos 1 a 3 —las deudas, el espejo en Python y los flujos
con fechas—, que es lo que deja el motor ejecutable y cubre NIIF 16 de verdad.
La **fase 2**, puntos 4 a 8, toma su propio plan cuando la primera esté cerrada.

1. **D1, D2, D3** — las tres deudas. Sin D2 nada de lo nuevo se puede ejecutar.
2. **Serie en `audit_engine.py`** — espejo de lo ya construido en JavaScript.
3. **Flujos irregulares con fechas** — desbloquea NIIF 16 real, NIC 36 y NIC 37.
4. **Resolución de raíz** — se apoya en el vector de flujos del punto anterior.
5. **Matriz de provisión** — toca al 100% de los clientes con cartera comercial.
6. **Unidad de crédito proyectada** — con la tabla de NIC 19.68 como prueba.
7. **Ponderación de escenarios** — barata, se enchufa a lo anterior.
8. **Black-Scholes** — último.

## 11 · Lo que no está verificado

Declarado explícitamente para que nadie lo dé por cierto:

- **NIIF para las PYMES**: las URLs de ifrs.org devuelven 404 para esa norma. No se cita ningún párrafo. Existe la sospecha —**sin fuente**— de que mantiene la distinción arrendamiento operativo/financiero y por tanto no tendría activo por derecho de uso. Afecta al 30% de la cartera y **hay que confirmarlo contra el texto oficial** antes de construir nada específico de PYMES.
- **IFRIC 1** (cambios en pasivos por desmantelamiento): 404 en el mismo patrón de URL. La remedición contra el costo del activo queda descrita solo por NIC 37.45/47/59/60, que sí se verificaron.
- **NIIF 15.64** (tasa del componente financiero): citado por referencia cruzada desde 15.60 y 15.63; su texto no se extrajo.
- **Normativa ecuatoriana**: Código del Trabajo, tasas de impuesto a la renta y resoluciones de la Superintendencia de Compañías quedan fuera de esta verificación. Los porcentajes usados en los ejemplos son ilustrativos.
