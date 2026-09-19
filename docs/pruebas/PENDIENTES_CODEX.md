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
| A4 | **Límites definidos** por el responsable: 200 archivos y 300 MB por encargo, 25 MB por archivo. `TEXT_LIMIT` de 240.000 a 5.000.000 y el **CSV pasa a limitarse por filas, no por caracteres** | `lib/console/extract.mjs`, `app/api/audit/route.ts`, `app/api/tool-files/route.ts` | ✅ compila; CSV de 100.000 filas (4,3 MB) leído en 0,18 s; 150.000 filas rechazado por el límite de filas |

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
| B3.1 | Obligatorio / opcional por documento | Existe en Obligaciones Fiscales, no en el sitio |
| B3.2 | Fuentes alternativas | No existe en ninguna de las tres |
| B3.3 | Plantilla descargable con instrucciones | Existe en el ICT, no en el sitio |
| B3.4 | Estados completos del documento | Recibido / extraído / pendiente de OCR o mapeo / validado / rechazado. Hoy parcial |
| B3.5 | **Evidencia por componentes** | Que el cliente entregue una fuente grande **partida en varias piezas** (por mes, por bodega, por rango de cuentas) en vez de un archivo único. Ver detalle abajo |
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
| B4.1 | Casilla **«Aplica impuestos diferidos»** | Si se marca, la prueba habilita sus cédulas de diferido; si no, quedan ocultas. No existe en ninguna de las tres |

### B5 · Limpieza de pantalla

| # | Se quita | Dónde | Motivo |
|---|---|---|---|
| B5.1 | Población sintética y parámetros de cálculo | `app/herramientas/recorrido/studio.tsx` | Ya queda definido en la ficha de la prueba |
| B5.2 | «Confirmar ficha del ejemplo» | `app/herramientas/recorrido/studio.tsx` | Pertenece al recorrido de demostración |
| B5.3 | Número fijo de 12 cédulas | `lib/tools/workbook-presentation.mjs` | Las cédulas son variables por prueba (Manual §11) |

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
