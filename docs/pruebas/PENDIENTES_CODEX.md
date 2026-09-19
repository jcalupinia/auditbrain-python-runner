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

| # | Cambio | Archivos | Verificado |
|---|---|---|---|
| A1 | Capacidad del motor: `MAX_ROWS` de 10.000 a **100.000** | `lib/tools/domain.mjs`, `lib/tools/portable-engine.mjs` | ✅ 100.000 filas en 4,08 s con la definición VNR real; 100.001 rechazado con mensaje claro |
| A2 | Extractor conectado a la evidencia del encargo. Formatos **+ XML, + ZIP, + WebP**; límite por archivo 5 MB → **10 MB**; cada archivo se extrae y el resultado se guarda junto a él | `app/api/audit/route.ts`, `lib/audit.ts` | ✅ compila; XML, CSV y TXT extraen; **ZIP recursivo probado con la plantilla real: encontró el .xlsx dentro y leyó sus 11 hojas por nombre** |
| A3 | **Markdown (.md)** aceptado en las dos rutas de carga y en el extractor, con tipo propio `kind:'md'` para que la cédula muestre de qué formato vino la evidencia | `lib/console/extract.mjs`, `app/api/audit/route.ts`, `app/api/tool-files/route.ts` | ✅ compila; `.md` suelto y **`.md` dentro de un ZIP** extraen correctamente |
| A5 | **Ruta muerta eliminada.** `app/api/audit/route.ts`, `lib/audit.ts` y `lib/export.ts` no los llamaba nadie: eran la API de la versión anterior | borrados | ✅ compila sin ellos |
| A6 | **Requerimiento estructurado en ítems.** Cada ítem declara qué se pide, **a qué formatos debe acogerse el cliente**, si es obligatorio y en **cuántos componentes** viene. La carga se vincula a su ítem y componente; el avance de etapa exige **cobertura completa**, no "algún documento" | `lib/requirement.mjs` (nuevo), `lib/workflow.mjs`, `lib/audit-store.ts`, `app/api/documents/route.ts`, `app/api/engagements/route.ts`, `app/audit-app.tsx`, `db/schema.ts`, migración `0005` | ✅ verificado de punta a punta — ver abajo |
| A4 | **Límites definidos** por el responsable: 200 archivos y 300 MB por encargo, 25 MB por archivo. `TEXT_LIMIT` de 240.000 a 5.000.000 y el **CSV pasa a limitarse por filas, no por caracteres** | `lib/console/extract.mjs`, `app/api/audit/route.ts`, `app/api/tool-files/route.ts` | ✅ compila; CSV de 100.000 filas (4,3 MB) leído en 0,18 s; 150.000 filas rechazado por el límite de filas |

| A7 | **Fuentes alternativas, plantilla descargable y estados del documento.** El ítem declara `group` (los del mismo grupo son intercambiables), `columns` e `instructions` (de ahí sale la plantilla CSV, sin archivos que mantener), y el auditor marca cada documento **validado o rechazado**: un rechazado deja de contar para la cobertura | `lib/requirement.mjs`, `app/api/engagements/route.ts`, `app/audit-app.tsx` | ✅ verificado contra la API viva — ver abajo |

| A8 | **Casilla «Aplica impuestos diferidos»** en la ficha del encargo, y **fuera la población sintética** con sus cifras fijas de la pantalla del recorrido | `lib/engagement-context.ts`, `app/herramientas/context-controls.tsx`, `app/herramientas/recorrido/studio.tsx` | ✅ `true`, `false` y **sin declarar → `false`**; compila limpio |

### Estado de verificación de A7

| Prueba | Resultado |
|---|---|
| Grupo sin cubrir | ✅ *«Costos de venta: entregue una de estas fuentes — Costos por item o Estado de resultados»* |
| Una alternativa satisface el grupo | ✅ el grupo desaparece del reclamo |
| Todo cubierto | ✅ avanza a etapa 6 |
| **Documento marcado rechazado** | ✅ **reabre el hueco y bloquea** |
| Documento marcado validado | ✅ avanza a etapa 6 |
| Plantilla CSV con columnas e instrucciones | ✅ a nivel de módulo (`templateCsv`) |

**No probado en pantalla:** el botón «Plantilla» de la etapa 4 descarga el CSV
en el navegador. La generación está verificada; el clic en la interfaz no.

### Estado de verificación de A6

Probado contra la API viva, con el servidor local y la migración aplicada:

| Prueba | Resultado |
|---|---|
| Guardar ítems con formatos y componentes | ✅ `i1` con 3 componentes, `i2` sin componentes |
| Cargar un PDF en un ítem que pide XLSX/CSV | ✅ rechazado: *«"Mayor general" admite XLSX, CSV. Recibido: pdf.»* |
| Cargar un componente no declarado | ✅ rechazado: *«Componente no declarado…: abril.»* |
| Cargar `.md` en un ítem que lo declara | ✅ aceptado y extraído como `kind: md` |
| Bloquear el avance con un componente faltante | ✅ bloquea |
| **Avanzar con cobertura completa** | ✅ **avanza a etapa 6** |
| Sigue bloqueando cuando falta un componente (regresión) | ✅ *«Cobertura incompleta. Mayor general: faltan febrero»* |
| Comprobaciones propias de `requirement.mjs` | ✅ todas pasan |

**Causa encontrada:** `docs()` en `lib/audit-store.ts` no seleccionaba
`item_id` ni `component`, así que la cobertura veía todos los documentos sin
vínculo y nunca se cumplía. Corregido con
`SELECT … item_id AS itemId, component …`.

**Resuelto y reverificado** el 2026-09-19: recompilado, servidor levantado y
prueba repetida. Los documentos vuelven con su `itemId` y `component`, la
cobertura se cumple y el encargo avanza a etapa 6. El caso negativo sigue
bloqueando, así que no se cambió un error por otro.

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
| **B5.3** | Número fijo de 12 cédulas | ⚠️ **No es limpieza: es reescribir el motor de exportación** |

**B5.2 — por qué no se quita.** Ese botón es el que desbloquea las fuentes
(`disabled={editing||!ctx.framework}`). Quitarlo deja el recorrido inutilizable.
Y el archivo entero *es* la demostración (`/herramientas/recorrido`), así que
«pertenece al recorrido» no es motivo para eliminarlo. El ítem estaba mal
planteado en la versión 0.1 de esta lista.

**B5.3 — el alcance real.** Las 12 etiquetas están cableadas en el motor que
arma el libro, no en una pantalla:

| Archivo | Uso |
|---|---|
| `lib/tools/workbook-presentation.mjs` | `labels[index]` en encabezados e hipervínculos entre hojas |
| `lib/tools/exports.mjs` | `labels.slice(1)` arma la hoja índice |
| `lib/tools/html-presentation.mjs` | misma fuente |

Hacer las cédulas variables exige **rediseñar cómo se ensambla el libro**, para
que las hojas salgan de la definición de cada prueba. Es el trabajo grande que
queda pendiente para que la decisión «cédulas todas variables» sea real en el
Excel, y no solo en el documento de estructura.

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
| 2026-09-19 | 17 | Estado al sincronizar el checkout. Nada de esta lista está publicado todavía |
