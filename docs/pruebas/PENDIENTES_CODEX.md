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

### B2 · Subir los límites de tamaño

| Límite | Hoy | Objetivo |
|---|---|---|
| Por archivo (encargo) | ~~5 MB~~ **10 MB** | **por definir** |
| Archivos por encargo | 20 | **por definir** |
| Total por encargo | 20 MB | **por definir** |
| Por archivo (extractor) | 10 MB | **por definir** |

Bloqueado hasta que se defina cuánto pesa el archivo más grande de un cliente
real (un mayor general de empresa grande).

### B3 · Requerimiento al cliente

| # | Cambio | Detalle |
|---|---|---|
| B3.1 | Obligatorio / opcional por documento | Existe en Obligaciones Fiscales, no en el sitio |
| B3.2 | Fuentes alternativas | No existe en ninguna de las tres |
| B3.3 | Plantilla descargable con instrucciones | Existe en el ICT, no en el sitio |
| B3.4 | Estados completos del documento | Recibido / extraído / pendiente de OCR o mapeo / validado / rechazado. Hoy parcial |

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
