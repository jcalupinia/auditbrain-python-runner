# Análisis de alineación del sitio AuditBrain

2026-09-19 · sitio en **versión 19** · contrastado contra `ESTRUCTURA_HERRAMIENTA.md`

Revisión de las dos secciones del menú —**Auditoría externa** y **Recursos de
trabajo**— para responder tres preguntas: si funcionan, si están estructuradas
según lo que se reconstruyó, y si los ejemplos están actualizados.

---

## 1 · Funcionamiento

Las once entradas del menú responden. Comprobado con el sitio corriendo:

| Sección | Ruta | Estado |
|---|---|---|
| Centro de trabajo | `/` | 200 |
| Crear con guía | `/crear` | 200 |
| Herramientas | `/herramientas` | 200 |
| Reconstruir Excel | `/reconstruir` | 200 |
| Consola de archivos | `/consola` | 200 |
| En revisión | `/?estado=revision` | 200 |
| Aprobados | `/?estado=aprobado` | 200 |
| Manual y memoria | `/metodologia` | 200 |
| Agente de AuditBrain | `/chatgpt` | 200 |
| Ejemplo Excel / HTML | `/herramientas/ejemplo` | 307 → redirección prevista al recorrido |
| Vista de demostración | `/demostracion` | 200 |

**Nada está caído.** El problema no es de funcionamiento, es de estructura.

---

## 2 · Hallazgo principal: conviven dos modelos de requerimiento

`ESTRUCTURA_HERRAMIENTA.md` define **una** estructura común. Hoy hay **dos**,
y solo una se reconstruyó:

| | Modelo nuevo — `items` | Modelo anterior — `requests` |
|---|---|---|
| Dónde vive | Centro de trabajo (`/`, flujo de 9 pasos) | Herramientas (`/herramientas`) |
| Declara formatos aceptados | ✅ | ❌ |
| Obligatorio / opcional | ✅ | ❌ |
| Componentes esperados | ✅ | ❌ |
| Fuentes alternativas | ✅ | ❌ |
| Plantilla descargable | ✅ | ❌ |
| Estado validado / rechazado | ✅ | ❌ |
| Cobertura que bloquea el avance | ✅ | ❌ |

Evidencia: `lib/tools/lifecycle.ts` crea las herramientas con `requests:[]`, y
`app/api/tool-files/route.ts` valida con `t.requests.some(r=>r.id===requestId)`
— una lista de identificadores sin ninguno de los atributos nuevos.

**Consecuencia práctica.** Un auditor que trabaje por *Centro de trabajo* tiene
control de cobertura; el mismo auditor trabajando por *Herramientas* no lo
tiene. Misma firma, mismo encargo, dos niveles de control distintos.

---

## 3 · Sección por sección

| Sección | ¿Alineada? | Detalle |
|---|:---:|---|
| **Centro de trabajo** | ✅ | Es lo que se reconstruyó: ítems con formatos, obligatoriedad, componentes, alternativas, plantilla, estados y cobertura que bloquea |
| **En revisión** · **Aprobados** | ✅ | Son filtros del Centro de trabajo; heredan todo |
| **Consola de archivos** | ✅ | Se benefició de A2 y A3: procesa XML, ZIP, Word, PDF, imágenes y Markdown con los límites nuevos |
| **Herramientas** | ❌ | Conserva el modelo `requests`. Cero menciones de formatos, componentes u obligatoriedad |
| **Crear con guía** | ✅ | **Diagnóstico corregido + arreglado 2026-09-19.** No crea encargos ni herramientas: arma un prompt y abre una conversación en la Consola, y ya reutilizaba la ficha. Lo que fallaba era qué pedía ese prompt: el paso 4 decía «solicita lo que falte». Ahora exige el requerimiento como lista de ítems con formatos, obligatoriedad, componentes, alternativas y columnas |
| **Reconstruir Excel** | ❌ | No usa el modelo de ítems |
| **Manual y memoria** | ✅ | **Corregido 2026-09-19**: sección 05A «Requerimiento estructurado en ítems» y regla M17 en la memoria. Manual en versión 1.3.0 |
| **Ejemplo Excel / HTML** | ⚠️ | **Parcial 2026-09-19**: sus cuatro fuentes ya declaran formatos, exigencia y componentes. Sigue con 12 cédulas fijas y su propia lógica de «4 de 4» |
| **Agente** · **Demostración** | — | Sin revisar en detalle |

---

## 4 · Los ejemplos: estado original y qué se corrigió

`app/herramientas/recorrido/studio.tsx` declara sus cuatro fuentes así:

```js
requirements=[['inventario','Inventario valorado al corte','Cantidades, costo unitario…'],
              ['precios','Lista de precios de venta','…'],
              ['gastos','Gastos y costos de venta / terminación','…'],
              ['politicas','Políticas y deterioro registrado','…']]
```

Una tripleta `id / título / nota`. **No declara formatos aceptados, ni
obligatoriedad, ni componentes, ni plantilla.** Las únicas coincidencias de
`formats` y `components` en ese archivo son importaciones de
`components/ui/...` y un tipo MIME: ninguna es el modelo nuevo.

Además sigue produciendo **12 cédulas fijas**, que es exactamente lo que la
estructura descartó (`B5.3`, pendiente).

Resultado: **el ejemplo que un auditor abría para aprender el formato le
enseñaba el modelo anterior.**

**Corregido el mismo día.** Las cuatro fuentes ahora declaran formatos
aceptados, exigencia y componentes, y el texto introductorio explica que la
cobertura se mide componente por componente y que un documento rechazado
reabre el hueco. Verificado en el HTML servido.

**Lo que sigue pendiente ahí:** el motor interno del recorrido conserva su
lógica de «4 de 4 fuentes cargadas» —que no es el motor de cobertura real— y
sus 12 cédulas fijas (`B5.3`).

---

## 5 · Qué corregir, por orden de daño

| # | Qué | Por qué primero |
|---|---|---|
| ~~1~~ | ~~Manual y memoria~~ | ✅ **Hecho**: sección 05A + M17, versión 1.3.0 |
| ~~2~~ | ~~Ejemplo: declarar formatos y componentes~~ | ✅ **Hecho**. Queda su motor interno, que no usa el de cobertura real |
| ~~3~~ | ~~Crear con guía~~ | ✅ **Hecho**. El diagnóstico original estaba mal planteado: ver la fila de la sección 3 |
| 4 | **Herramientas** | Unificar `requests` con `items`. Es el más grande: toca el ciclo de vida, la carga de fuentes y la interfaz |
| 5 | **B5.3 · cédulas variables** | Ya registrado. Reescribir el ensamblado del libro |

---

## 6 · Conclusión

Lo reconstruido **funciona y está bien**, pero **llegó a una sola de las cinco
secciones operativas** del menú. El sitio hoy es coherente consigo mismo en el
Centro de trabajo y desalineado en el resto.

La afirmación «la herramienta está estructurada según lo nuevo» **sería falsa
si se dijera del sitio completo**. Es cierta solo del Centro de trabajo.

El diagnóstico se hizo sin tocar código. Después, en la misma jornada, se
corrigieron los tres primeros puntos del orden propuesto: **Manual y memoria**
(sección 05A y regla M17, versión 1.3.0), **Ejemplo** (las cuatro fuentes
declaran sus atributos) y **Crear con guía** (el prompt exige el requerimiento
como lista de ítems).

Efecto colateral útil: `METHODOLOGY_MEMORY` viaja completo dentro de cada
prompt que genera la guía, así que la regla M17 llega al asistente sin
necesidad de repetirla.

Quedan los dos de mayor alcance: **unificar Herramientas** con el modelo de
ítems, y las **cédulas variables** (`B5.3`).
