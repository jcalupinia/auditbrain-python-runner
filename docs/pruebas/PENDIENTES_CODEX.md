# Pendientes para publicar desde Codex

Lista acumulativa de cambios al sitio **AuditBrain Sites**
(`auditbrain-auditoria.auditconsult-8110.chatgpt.site`).

**Por qué existe esta lista.** Publicar el sitio solo se puede desde Codex, y
cada ejecución consume créditos. En vez de publicar cambio por cambio, se
acumulan aquí y se hace **una sola publicación**.

- **Checkout que publica:** `C:\Users\jcalu\Documents\Codex\2026-09-17\sites-x20`
- **Réplica local de trabajo:** `PROYECTOS CLAUDE\auditbrain-site`
- **project_id:** `appgprj_6aac4365f6288191a6d65fea99a71373`

> Todo cambio debe aplicarse en **ambas** carpetas. Si solo se toca la réplica,
> se pierde en la próxima publicación.

---

## A · Listos en el checkout, esperando publicación

| # | Cambio | Archivos | Estado |
|---|---|---|---|
| A16 | **Motor de cálculo NIIF, fase 1.** Series por períodos espejadas en el motor Python; contraste servidor/Python simetrizado (recorre la unión de claves e incluye `totals`); cédula `13_Cuadro` alimentada desde `run.schedule`, que antes se calculaba y se tiraba; **flujos irregulares con fechas** en convención `actual/365`, con el mismo algoritmo entero en los tres motores; guardarraíl que avisa si un cuadro de amortización no cierra en cero; y el motor portátil con script de regeneración y prueba que detecta la divergencia | `lib/tools/domain.mjs`, `lib/tools/exports.mjs`, `lib/tools/workbook-presentation.mjs`, `lib/tools/html-presentation.mjs`, `lib/tools/explanations.mjs`, `lib/tools/lifecycle.ts`, `lib/tools/portable-engine.mjs`, `public/engine/audit_engine.py`, `app/api/tools/route.ts`, `app/herramientas/tool-studio.tsx`, `scripts/export-portable-engine.mjs`, `package.json`, `tests/tools/*`, **`drizzle/0000_mixed_cyclops.sql` eliminado** | ✅ **60/60 pruebas** (antes 24/25 con un fallo crónico) · `tsc` sin errores · build limpio · Excel abierto con openpyxl sin reparaciones |

### ⚠️ Aviso para esta publicación: `drizzle/` SÍ cambia

A diferencia de las versiones 24 y 25, **esta vez hay un cambio en `drizzle/`**: se
**eliminó** `0000_mixed_cyclops.sql`. No es una migración nueva y **nunca estuvo en
`_journal.json`**, así que D1 jamás lo aplicó — era un archivo muerto con el esquema
viejo de `engagements`. Eliminarlo es justamente lo que arregla el
`table engagements already exists` que tumbó las versiones 20 y 22.

Lo que hay que decirle a Codex: **no hay migraciones nuevas; siguen siendo las 7 del
journal; se eliminó un `.sql` huérfano que no estaba en el journal.**

---

## A-histórico · Publicado en la versión 25 (2026-09-19)

| # | Cambio | Archivos | Estado |
|---|---|---|---|
| A14 | **El sitio seguía prometiendo «12 cédulas» en cuatro sitios**, contradiciendo B5.3. Encontrado revisando el sitio **publicado**, no el local. La tarjeta del formato y la nota del estudio pasan a «Cédulas según la prueba»; los entregables de una herramienta concreta **calculan** el número real con `sheetLabels(tool.definition).length`; y el manual dejó de describir el recorrido viejo («cuatro fuentes sintéticas… doce cédulas») | `app/audit-app.tsx`, `app/herramientas/tool-studio.tsx`, `app/herramientas/tool-overview.tsx`, `lib/methodology.mjs` (manual a **1.3.1**) | ✅ compila limpio · `npx tsc --noEmit` sin errores · cero coincidencias de «12 cédulas» en el código y en el HTML servido de `/`, `/herramientas` y `/demostracion` |

`sheetLabels(undefined)` devuelve las doce, así que el panel de entregables no
puede romperse si a una herramienta le faltara la definición.

---

## A · Listos en el checkout, esperando publicación

| # | Cambio | Archivos | Estado |
|---|---|---|---|
| A15 | **Eliminar una herramienta, no solo encerarla.** No existía ningún `DELETE`: «Encerar» borraba datos y archivos pero **dejaba la prueba en la lista** con estado `PRUEBA_SELECCIONADA`, y no había forma de quitarla. `deleteTool` reutiliza el encerado en dos fases (anota las claves de R2 en el propio registro antes de borrar, para que un fallo a medias se reintente sin dejar objetos huérfanos) y luego borra en orden de clave foránea —`tool_files`, `tool_events`, `audit_tools`— con guardia de revisión en cada sentencia | `lib/tools/lifecycle.ts` (`deleteTool`), `app/api/tools/route.ts` (acción `delete`), `app/herramientas/context-controls.tsx` (botón y formulario), `app/herramientas/tool-studio.tsx` (vuelve a la lista) | ✅ compila limpio · `npx tsc --noEmit` sin errores · **verificado de punta a punta en local** — ver abajo |

**Resguardos** (todos probados, ninguno asumido):

| Resguardo | Resultado |
|---|---|
| Solo el propietario (`ADMIN`) | Código 403 |
| Hay que escribir el nombre del cliente | 400 con el cliente mal escrito y 400 sin confirmar |
| Revisión obsoleta | 409, no borra nada |
| Versión **aprobada** | 400: «es evidencia del encargo. Confírmelo expresamente». Con `approvedConfirmed` sí borra |
| Versión con sucesora | 409, hay que borrar primero la más reciente |

**Verificación en la base local**, contando filas antes y después:

| Comprobación | Resultado |
|---|---|
| Prueba con 5 archivos y 13 eventos | 0 filas en `audit_tools`, `tool_events` y `tool_files` |
| Objetos en R2 de esa prueba | **0** (antes 5) |
| Filas huérfanas en toda la base | 0 eventos, 0 archivos |
| Encargos | **9 intactos**: borrar una prueba no toca la ficha |
| Por la interfaz | Avisa «Prueba eliminada definitivamente: …», vuelve a la lista y la fila desaparece |

De paso quedaron verificados los **dos caminos que faltaban** (ver ANALISIS):
el panel de entregables muestra «Excel con **12** cédulas» en una herramienta
normal y «Excel con **7**» en una que declara `sheets:['02_Programa','11_Conclusion']`,
así que **calcula** el número y no lo tiene fijo.

---

## A-histórico · Publicado en la versión 23 (2026-09-19)

| # | Cambio | Archivos | Estado |
|---|---|---|---|
| A13 | **El recorrido usa el motor de cobertura real, no un contador de «4 de 4».** `app/herramientas/recorrido/studio.tsx` ya no lleva su propia lógica: importa `parseItems`, `coverage`, `gaps` y `checkUpload` de `lib/requirement.mjs`, el mismo motor del Centro de trabajo. El requerimiento del ejemplo pasó de tuplas de texto decorativo a **ítems reales** con formatos, exigencia, componentes y grupo. Se añadió el botón de rechazo por documento y un «Probar un formato no admitido» que muestra el mensaje del propio motor | `app/herramientas/recorrido/studio.tsx`, `app/herramientas/recorrido/walkthrough.css`, `lib/requirement.mjs` (redacción del hueco), `app/api/documents/route.ts` (un tipo) | ✅ compila limpio · `npx tsc --noEmit` **sin ningún error** · verificado con clics reales en el navegador — ver abajo |

**Cómo se verificó A13** (clics reales en `/herramientas/recorrido`, no solo auto-test):

| Regla | Prueba | Resultado |
|---|---|---|
| Componentes | Cargar solo «Bodega Quito» del inventario | «Inventario valorado al corte: faltan Bodega Guayaquil» · 0 de 5 ítems · Procesar deshabilitado |
| Fuentes alternativas | Cargar el estado de resultados **sin** los costos por ítem | **4 de 5 ítems cubiertos y cero huecos**: el grupo se satisface con una |
| Rechazo | Rechazar «Bodega Guayaquil» ya procesado | El hueco se reabre, baja a 3 de 5, el resultado se cae y las descargas se deshabilitan |
| Formatos | «Probar un formato no admitido» | «"Inventario valorado al corte" admite XLSX, CSV. Recibido: jpg.» |

Efecto secundario en el motor: un ítem **sin** componentes ya no se reporta como
«Lista de precios de venta: faltan Lista de precios de venta». Se nombra una sola
vez. La corrección está en `describe` de `lib/requirement.mjs`, con su aserción.

---

## A-histórico · Publicados en la versión 21 (2026-09-19)

| # | Cambio | Archivos | Verificado |
|---|---|---|---|
| A9 | **Manual y ejemplo alineados con el modelo de ítems.** Sección 05A «Requerimiento estructurado en ítems» y regla M17 en la memoria (manual a versión 1.3.0). Las cuatro fuentes del recorrido declaran formatos aceptados, exigencia y componentes | `lib/methodology.mjs`, `app/herramientas/recorrido/studio.tsx`, `lib/chatgpt/intake.ts` | ✅ compila limpio; verificado en el HTML servido: `/metodologia` muestra 05A y M17, `/herramientas/recorrido` muestra los atributos en las cuatro fuentes. **Crear con guía**: el prompt exige el requerimiento como lista de ítems con formatos, obligatoriedad, componentes, alternativas y columnas; y la regla M17 viaja dentro del prompt |

---

| A10 | **Herramientas unificadas con el motor de cobertura.** `lib/tools/coverage.mjs` adapta los requerimientos de Herramienta a los ítems del motor ya probado, en vez de duplicar la lógica. La carga valida formato y componente; la validación documental exige cobertura completa en vez de «un archivo por requerimiento» | `lib/tools/coverage.mjs` (nuevo), `lib/tools/repository.ts`, `app/api/tool-files/route.ts`, `app/api/tools/route.ts`, `db/schema.ts`, migración `0006` | ✅ verificado de punta a punta — ver abajo |

### Estado de verificación de A10

| Prueba | Resultado |
|---|---|
| Comprobaciones de `lib/tools/coverage.mjs` | ✅ todas pasan |
| Lee los formatos del texto `XLSX / CSV` | ✅ |
| «imágenes» implica png, jpg, webp | ✅ |
| **Un archivo por requerimiento ya no cubre dos componentes** | ✅ *«Mayor general: faltan febrero»* |
| Archivo rechazado reabre el hueco | ✅ |
| Formato no declarado se rechaza nombrando el correcto | ✅ |
| Compilación | ✅ limpia |
| Migración `0006` | ✅ una columna, no destructiva |
| Carga: formato no declarado | ✅ *«"Inventario valorado al 2026-12-31" admite XLSX, CSV. Recibido: pdf.»* |
| Carga: componente no declarado | ✅ *«Componente no declarado…: Bodega centro.»* |
| Carga válida | ✅ 201, componente guardado y contenido extraído |
| **Validar con un componente faltante** | ✅ *«Cobertura incompleta. Inventario valorado al 2026-12-31: faltan Bodega sur»* |
| **Validar con cobertura completa** | ✅ la cobertura deja de bloquear; el flujo avanza a la validación siguiente (parámetros de conciliación, ajena a esto) |

**Cerrado el 2026-09-19.** Se recorrió el flujo completo por la API —investigar
fuentes, generar y aprobar programa, generar y aprobar requerimiento, cargar
evidencia y validar— declarando dos componentes («Bodega norte» y «Bodega sur»)
en el requerimiento del inventario.

---

## B · Pendientes de escribir

### B1 · Conectar el extractor ✅ RESUELTO — ver A2

Al revisarlo se encontró que había **dos rutas de carga**, no una:

| Ruta | Qué carga | Estado antes |
|---|---|---|
| `app/api/tool-files/route.ts` | Fuentes de la herramienta | **Ya estaba conectada**: corría `extractFile` en cada archivo y aceptaba xml, zip, docx, pdf e imágenes |
| `app/api/audit/route.ts` | Evidencia del encargo (flujo de 9 pasos) | **Sin extractor**, y sin XML ni ZIP |

Se conectó la segunda. Criterio aplicado: si un archivo no se puede leer, la
carga **no falla** — queda recibido con estado `error` y su motivo, para no
convertir un error de lectura en un dato ausente (M07).

| A11 | **Las fuentes apuntan al texto de la norma, no a su índice.** NIC 2 y NIIF 9 al HTML oficial; NIIF para las PYMES a la tercera edición. El manual (§05) exige que una URL genérica no valga como verificación | `lib/tools/domain.mjs`, `lib/tools/research.ts` | ✅ los tres HTML responden 200 **sin registro**; compila limpio |
| A12 | **Cédulas variables: el libro sale de la definición, no de una lista fija.** `definition.sheets` declara qué cédulas lleva la herramienta; sin declararlas siguen saliendo las doce. Cuatro son núcleo (`01_Caratula`, `03_Parametros`, `05_Data_Original`, `06_Data_Procesada`, `07_Calculos`) porque otras hojas las referencian por fórmula: el plan las conserva siempre. `validateDefinition` rechaza un nombre de cédula inexistente al crear la herramienta, no al descargar | `lib/tools/exports.mjs` (`sheetPlan`, `sheetNames`, `sheetLabels`), `lib/tools/domain.mjs` (`SHEETS` + validación), `lib/tools/workbook-presentation.mjs`, `lib/tools/html-presentation.mjs`, `lib/tools/portable-engine.mjs` regenerado | ✅ compila limpio · `node lib/tools/exports.mjs` pasa · verificado abriendo los Excel con openpyxl — ver abajo |

---

### B2 · Límites de tamaño ✅ RESUELTO — ver A4

Medición previa a la decisión, sobre el encargo real de PROPHAR:

| | Real | Límite que había | |
|---|---|---|---|
| Archivos | **27** | 20 | ❌ se pasaba |
| Peso total | 7 MB | 20 MB | ✅ |
| Archivo más grande | 1,54 MB | 10 MB | ✅ |

El cuello de botella no eran los MB sino **la cantidad de archivos**: un encargo
tributario lleva 12 F-103 + 12 F-104 + F-101 + mayores y ya supera 20.

Valores definidos: **200 archivos**, **300 MB por encargo**, **25 MB por archivo**.

**Defecto encontrado al hacerlo.** `TEXT_LIMIT` (240.000 caracteres) hacía que la
capacidad de 100.000 filas de A1 fuera **inalcanzable por CSV**: un mayor de
100.000 filas pesa 4,3 MB y se rechazaba antes de llegar al motor. Se corrigió
subiendo el tope a 5.000.000 y, sobre todo, **sacando al CSV del límite por
caracteres**: su control es `MAX_ROWS`, no la longitud del texto.

### B3 · Requerimiento al cliente

| # | Cambio | Detalle |
|---|---|---|
| ~~B3.1~~ | ~~Obligatorio / opcional por documento~~ | ✅ **Resuelto — ver A6** |
| ~~B3.2~~ | ~~Fuentes alternativas~~ | ✅ **Resuelto — ver A7** |
| ~~B3.3~~ | ~~Plantilla descargable con instrucciones~~ | ✅ **Resuelto — ver A7** |
| ~~B3.4~~ | ~~Estados completos del documento~~ | ✅ **Resuelto — ver A7** |
| ~~B3.5~~ | ~~Evidencia por componentes~~ | ✅ **Resuelto — ver A6** |
| ~~B3.6~~ | ~~Aceptar Markdown (.md)~~ | ✅ **Resuelto — ver A3** |

#### B3.5 · Evidencia por componentes — detalle

**Ya funciona a medias.** `app/api/audit/route.ts` no impone unicidad por
`requestId`: se pueden subir varias piezas y todas quedan vinculadas al mismo
requerimiento. Lo que falta no es la carga, es el **control de cobertura**.

El Manual §08 lo advierte expresamente:

> *«Una categoría con doce archivos no son doce requisitos; tener todas las
> categorías tampoco prueba cobertura mensual.»*

Sin ese control, partir la evidencia **empeora** el riesgo: es más fácil que
falte un pedazo y que nadie lo note. Lo que hay que agregar:

| Requisito | Qué hace |
|---|---|
| Declarar los componentes esperados | El requerimiento dice en cuántas piezas viene y cuáles: doce meses, tres bodegas, rangos de cuentas |
| Marcar los que faltan | Cobertura visible: «9 de 12 meses recibidos; faltan abril, julio y noviembre» |
| Conciliar al procesar | Las partes sumadas deben cuadrar contra un total de control antes de calcular |
| Bloquear el cálculo si hay huecos | Un componente ausente no puede leerse como cero (M07) |

**Beneficio colateral:** resuelve buena parte de B2. Un mayor general de 80 MB
partido por trimestre entra sin tocar los límites.

### B4 · Ficha del encargo

| # | Cambio | Detalle |
|---|---|---|
| ~~B4.1~~ | ~~Casilla «Aplica impuestos diferidos»~~ | ✅ **Resuelto — ver A8** |

### B5 · Limpieza de pantalla

| # | Se quita | Estado |
|---|---|---|
| ~~B5.1~~ | ~~Población sintética y parámetros de cálculo~~ | ✅ **Resuelto — ver A8** |
| ~~B5.2~~ | ~~«Confirmar ficha del ejemplo»~~ | ✖ **Ítem mal planteado. No se quita** |
| ~~B5.3~~ | ~~Número fijo de 12 cédulas~~ | ✅ **Resuelto — ver A12** |

**B5.2 — por qué no se quita.** Ese botón es el que desbloquea las fuentes
(`disabled={editing||!ctx.framework}`). Quitarlo deja el recorrido inutilizable.
Y el archivo entero *es* la demostración (`/herramientas/recorrido`), así que
«pertenece al recorrido» no es motivo para eliminarlo. El ítem estaba mal
planteado en la versión 0.1 de esta lista.

**B5.3 — resuelto el 2026-09-19.** El diagnóstico era correcto: las 12
etiquetas estaban cableadas en el motor que arma el libro, no en una pantalla.
Se midió el grafo de dependencias entre hojas antes de tocar nada:

| Hoja | Referencias entrantes por fórmula |
|---|---|
| `03_Parametros` | 6 |
| `05_Data_Original` | 5 |
| `06_Data_Procesada` | 4 |
| `07_Calculos` | 2 |
| Las otras ocho | **ninguna** |

De ahí el diseño: `sheetPlan(definition)` devuelve los índices de las cédulas
que lleva la herramienta. Las cuatro con referencias entrantes —más la portada,
que es el índice del libro— son núcleo y no se pueden omitir; las otras siete
salen si la definición las declara. `workbookSheets` sigue armando las doce y
filtra al final, así que ninguna fórmula cambió de dirección.

Verificación empírica (no solo el auto-test):

| Caso | Hojas | Partes / rels / Content_Types | Referencias rotas | openpyxl |
|---|---|---|---|---|
| Sin declarar cédulas | 12 | 12 / 12 / 12 | ninguna | abre y se recorre completo |
| Declarando `02_Programa` y `11_Conclusion` | 7 | 7 / 7 / 7 | ninguna | abre y se recorre completo |
| Declarando solo `11_Conclusion` | 6 | 6 / 6 / 6 | ninguna | abre y se recorre completo |

Los hipervínculos de la portada, sus celdas combinadas y las dos filas de pie
se calculan desde el plan: en el libro recortado bajan de 11 enlaces a 6 y el
pie se mueve de la fila 29/30 a la 24/25, sin dejar enlaces a hojas ausentes.
El motor portátil se **regeneró** con `scripts/export-portable-engine.mjs` para
que la copia de `validateDefinition` que viaja dentro del HTML conozca `SHEETS`;
el diff contra la versión anterior son exactamente esos dos cambios.

---

## C · Verificado, sin trabajo pendiente

| Punto | Resultado |
|---|---|
| HTML autónomo sin internet | `lib/tools/html-presentation.mjs` **no contiene ninguna URL externa**. La salida ya es autónoma |
| División por cero | El motor **bloquea**; no devuelve cero silencioso |
| Diferencia neta del deterioro contabilizado | Ya implementada (`adjustment = impairment - recorded_allowance`) |

---

## Cómo publicar cuando la lista esté cerrada

Un solo comando, desde el checkout de Codex:

```bash
codex exec --cd "C:\Users\jcalu\Documents\Codex\2026-09-17\sites-x20" "Publica los cambios del sitio AuditBrain"
```

Antes de publicar:

1. Confirmar que cada cambio de esta lista está en **las dos carpetas**
2. Correr `npm run build` en la réplica y que compile
3. Verificar en `http://127.0.0.1:3100` que el sitio levanta
4. Recién ahí publicar

Después de publicar, mover lo publicado de la sección A a un historial y
registrar la versión del sitio.

---

## Historial

| Fecha | Versión publicada | Qué entró |
|---|---|---|
| 2026-09-19 | 17 | Estado al sincronizar el checkout |
| 2026-09-19 | **19** | **A1 a A8 en una sola publicación**: motor a 100.000 filas · extractor conectado a la evidencia del encargo con XML, ZIP y WebP · Markdown · límites 200 archivos / 300 MB / 25 MB · ruta muerta eliminada · requerimiento estructurado en ítems con cobertura por componentes · fuentes alternativas, plantilla descargable y estados del documento · casilla de impuestos diferidos y limpieza de pantalla. Migración `0005` aplicada y columnas `item_id`/`component` verificadas en D1. Acceso conservado como privado del propietario |
| 2026-09-19 | **21** | **A9 a A12 en una sola publicación**: manual y ejemplo alineados con el modelo de ítems (sección 05A, regla M17, manual 1.3.0) · Herramientas unificadas con el motor de cobertura vía `lib/tools/coverage.mjs`, con migración `0006` (`tool_files.component`) · fuentes apuntando al texto de la norma y no a su índice · **cédulas variables**: el libro sale de `definition.sheets` y conserva solo el núcleo referenciado por fórmulas. La versión 20 falló y no quedó activa |
| 2026-09-19 | **23** | **A13**: el recorrido usa el motor de cobertura real (`parseItems`/`coverage`/`gaps`/`checkUpload`) en vez de contar «4 de 4»; el requerimiento del ejemplo pasó a ítems con formatos, exigencia, componentes y grupo; botón de rechazo por documento. Redacción del hueco corregida en `lib/requirement.mjs` y un tipo en `app/api/documents/route.ts` (`npx tsc --noEmit` queda **sin errores**). La versión 22 volvió a fallar por migraciones ya aplicadas |
| 2026-09-19 | **24** | **A14**: se quitaron las cuatro afirmaciones de «12 cédulas» que contradecían B5.3, incluida la del manual, que además describía el recorrido anterior a A13. Manual a 1.3.1. Primera publicación **sin intento fallido**, tras avisarle a Codex que no había migraciones |
| 2026-09-19 | **25** | **A15**: eliminar herramientas de verdad (`deleteTool`), con cinco resguardos y limpieza de R2. Commit `11cc938`. Migraciones incluidas: 0, otra vez a la primera |

Verificación independiente tras publicar: la URL responde `HTTP 401`, es decir
el sitio está sirviendo y conserva su protección por sesión de ChatGPT.

**Por qué falló la versión 20 (guardar para la próxima publicación).** El
paquete de despliegue llevaba **las ocho migraciones históricas**, no solo la
pendiente. D1 las rechaza por duplicadas. La versión 21 se armó con un paquete
de 211 entradas que contiene **únicamente `0006`**, más el Worker y su
configuración. Si una publicación futura falla en la migración, ese es el primer
lugar donde mirar.

**Pasó otra vez en la versión 22** (`table engagements already exists`), con las
ocho migraciones ya aplicadas en el paquete. Codex las quitó del paquete temporal
—no del checkout, que conserva las ocho— y la 23 salió bien. **Conviene decírselo
por adelantado en el próximo `codex exec`**: «no hay migraciones nuevas; empaqueta
solo las pendientes». Ahorra un intento fallido por publicación.

Verificación de la versión 21: `HTTP 401` en dos intentos (1,4 s y 0,3 s), con
`Cache-Control: no-store`. El sitio sirve y sigue siendo privado.
