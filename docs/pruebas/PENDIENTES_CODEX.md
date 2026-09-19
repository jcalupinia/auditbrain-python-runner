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
| A9 | **Manual y ejemplo alineados con el modelo de ítems.** Sección 05A «Requerimiento estructurado en ítems» y regla M17 en la memoria (manual a versión 1.3.0). Las cuatro fuentes del recorrido declaran formatos aceptados, exigencia y componentes | `lib/methodology.mjs`, `app/herramientas/recorrido/studio.tsx`, `lib/chatgpt/intake.ts` | ✅ compila limpio; verificado en el HTML servido: `/metodologia` muestra 05A y M17, `/herramientas/recorrido` muestra los atributos en las cuatro fuentes. **Crear con guía**: el prompt exige el requerimiento como lista de ítems con formatos, obligatoriedad, componentes, alternativas y columnas; y la regla M17 viaja dentro del prompt |

---

| A10 | **Herramientas unificadas con el motor de cobertura.** `lib/tools/coverage.mjs` adapta los requerimientos de Herramienta a los ítems del motor ya probado, en vez de duplicar la lógica. La carga valida formato y componente; la validación documental exige cobertura completa en vez de «un archivo por requerimiento» | `lib/tools/coverage.mjs` (nuevo), `lib/tools/repository.ts`, `app/api/tool-files/route.ts`, `app/api/tools/route.ts`, `db/schema.ts`, migración `0006` | ⚠️ **verificación parcial** — ver abajo |

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
| **Cableado de punta a punta por la API** | ❌ **no probado** |

**Por qué quedó pendiente.** El flujo de Herramientas exige pasos previos que
encadenan varias puertas: investigación de fuentes oficiales (`sourcesVerified`)
y rol de revisor para aprobar. Llegar hasta `validate` por API requiere
recorrerlas todas.

**Qué falta probar antes de publicar:** que `toolGaps` bloquee de verdad al
validar con un componente faltante, y que `checkToolUpload` rechace un formato
no declarado en la carga real. Es la misma situación de A6, donde esa
verificación destapó un defecto real (`docs()` sin las columnas nuevas).

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
| 2026-09-19 | 17 | Estado al sincronizar el checkout |
| 2026-09-19 | **19** | **A1 a A8 en una sola publicación**: motor a 100.000 filas · extractor conectado a la evidencia del encargo con XML, ZIP y WebP · Markdown · límites 200 archivos / 300 MB / 25 MB · ruta muerta eliminada · requerimiento estructurado en ítems con cobertura por componentes · fuentes alternativas, plantilla descargable y estados del documento · casilla de impuestos diferidos y limpieza de pantalla. Migración `0005` aplicada y columnas `item_id`/`component` verificadas en D1. Acceso conservado como privado del propietario |

Verificación independiente tras publicar: la URL responde `HTTP 401`, es decir
el sitio está sirviendo y conserva su protección por sesión de ChatGPT.
