# Ciclo real de una prueba NIIF en el Command Center — Diseño

**Fecha:** 2026-09-21 · **Estado:** propuesto, pendiente de aprobación del dueño
**Antecede:** réplica del sitio AuditBrain en la pestaña «Generación de herramientas
NIIF» (merge `b4ac220`, en producción desde el 21-09-2026).

---

## 1 · Qué resuelve

Hoy el Command Center tiene el **diseño** (fichas y su estudio), la **demostración**
(recorrido VNR) y las **utilidades** (consola, reconstruir Excel, manual). Le falta
lo principal: **aplicar una prueba a un cliente real**, con su evidencia, su
revisión y su aprobación. En el sitio eso son 13 estados y 27 acciones sobre un
encargo; en el Command Center, ninguno.

Este diseño cubre ese ciclo completo para las herramientas del catálogo (VNR, PCE)
y para las fichas NIIF «enviadas» con su definición.

**Fuera de este diseño** (fases posteriores, cada una con su propio documento):
carga de evidencia por el cliente desde su portal · componentes con nombre en el
diseñador de fichas · demostración con datos ficticios · asistencia IA en
investigación y análisis.

---

## 2 · Decisiones del dueño (2026-09-21)

| Tema | Decisión | Consecuencia en el diseño |
|---|---|---|
| Almacenamiento | Empezar con el disco persistente de **1 GB** | Guardas de espacio (§6); ampliar más adelante es un cambio de configuración, no de código |
| Quién aprueba | **Admin y operadores** del portal | Se usa `require_staff`. Se pierde la separación preparador/revisor del sitio: queda documentado (§5) |
| Portal del cliente | Carga del cliente en **segunda fase** | En esta fase la evidencia la sube el auditor; el modelo de datos ya la deja preparada |
| Método | **Diseño escrito y etapas** | Este documento; luego una etapa a la vez, probada con clics y publicada |
| Sitio de ChatGPT | **Se deja como está**, no se congela | Sigue siendo la referencia de reglas; A16–A20 esperan su publicación |

---

## 3 · Arquitectura: dónde vive la autoridad

**Hecho que manda:** el servidor del portal en Render es **solo Python**. En el sitio
la autoridad del ciclo es JavaScript en el Worker; aquí no puede serlo.

Por eso:

1. **La máquina de estados y sus reglas se portan a Python**
   (`backend/app/aud/niif/ciclo/`), igual que ya se hizo con la cobertura
   (`requerimiento.py`): mismas reglas, mismos mensajes, y una **batería de casos
   espejo** que se escribe contra el sitio. Origen de cada regla:
   `transition`, `createProgram`, `createRequests`, `validateRows`, `reconcile`,
   `preliminary` (de `lib/tools/domain.mjs`); `checkSources`, `officialSources`
   (de `lib/tools/research.ts`); las 27 acciones de `app/api/tools/route.ts`; `readSpreadsheet` (de
   `lib/tools/files.mjs`) para el mapeo de datos.
2. **El cálculo autoridad es el motor Python** ya vendorizado
   (`backend/app/aud/niif/motor/audit_engine.py`, el mismo archivo que corre en el
   navegador del sitio). **El contraste se invierte respecto al sitio:** el
   navegador corre `domain.mjs` (copia intacta) y el servidor compara sobre la
   unión de claves de filas y totales, con la regla ya portada en `contraste.js`.
   Si difieren, no se guarda la ejecución.
3. **Las excepciones** (`RESULT`, `NEGATIVE_NRV`, `REVERSAL`, `SERIES_NO_CIERRA`)
   hoy solo las produce `domain.mjs`. Se portan a Python con su batería espejo,
   para que el servidor no dependa de lo que envía el navegador.
4. **Cédulas:** el exportador del sitio (vendorizado) arma Excel y HTML en el
   navegador a partir del registro guardado. El papel **aprobado** se genera una
   vez, se guarda con su huella y ya no cambia.

Lo que **no** se hace: ejecutar Node en Render, ni reescribir el exportador, ni
duplicar el motor.

---

## 4 · Modelo de datos (tablas nuevas)

Se reutiliza el **proyecto AUD** del portal como «encargo». No se tocan tablas
existentes.

| Tabla | Contenido | Por qué así |
|---|---|---|
| `aud_ficha_encargo` | 1:1 con `projects`. RUC, actividad, ejercicio, corte, marco, edición, adopción, país, moneda, visita, firma, preparado por, revisado por, impuesto diferido | El proyecto del portal solo tiene cliente, nombre y período. Validación portada de `parseEngagement` (RUC de 13 dígitos en Ecuador, corte dentro del ejercicio) |
| `aud_pruebas` | proyecto, versión, `parent_id` (versión anterior), estado (13 estados), `definicion` (JSON), `registro` (JSON: programa, fuentes, requerimiento, parámetros, validación, conciliación, ejecución, análisis, conclusión, puntos de revisión), `revision` (concurrencia), aprobada por/en, huellas del papel aprobado | Es la forma del registro del sitio. Las consultas solo filtran por proyecto y estado; normalizar el resto no compra nada hoy |
| `aud_prueba_archivos` | prueba, ítem, componente, nombre, SHA-256, tamaño, ruta en disco, clase (`source` / `workpaper`), estado (`recibido` / `rechazado`), subido por/en | Es lo que la cobertura necesita. El campo «subido por» ya distingue auditor de cliente para la fase 2 |
| `aud_prueba_eventos` | acción, estado anterior y nuevo, actor, comentario, versión, fecha | Bitácora; alimenta la cédula 12 «Control de revisión» |

**Fichas NIIF «enviadas»:** para poder usarse con un cliente necesitan su
definición. Se agrega a `niif_fichas` el campo `definicion` (JSON): se guarda la
definición que corrió en el Estudio **al marcar la ficha como probada**. Una ficha
sin definición probada no aparece al crear una prueba.

---

## 5 · El circuito

Los 13 estados del sitio (`STATES` de `domain.mjs`), agrupados en las 9 etapas
de su flujo:

| Etapa | Estados | Acciones | Requisito para avanzar |
|---|---|---|---|
| 1 · Datos del encargo | — | editar ficha del encargo | Ficha completa y válida |
| 2 · Selección de prueba | PRUEBA_SELECCIONADA | crear desde catálogo o ficha probada | La definición existe y valida |
| 3 · Programa | PROGRAMA_PROPUESTO → PROGRAMA_APROBADO | consultar fuentes, generar, guardar, aprobar programa | Fuentes NIIF y NIA (y tributaria si aplica) verificadas, con documento, párrafo y vigencia; cada procedimiento vinculado a una fuente verificada |
| 4 · Requerimiento | REQUERIMIENTO_GENERADO → REQUERIMIENTO_APROBADO | generar, guardar, aprobar requerimiento | Cada ítem con documento, propósito y procedimiento del programa |
| 5 · Documentación | DOCUMENTACION_RECIBIDA → DOCUMENTACION_VALIDADA | subir, rechazar, mapear y validar datos | Cobertura sin huecos (misma regla ya en producción), filas válidas, conciliación resuelta, revisión de evidencia documentada |
| 6 · Ejecución | PRUEBA_CONFIGURADA → METODOLOGIA_APROBADA → PRUEBA_EJECUTADA | configurar parámetros, aprobar metodología, ejecutar | Sustento de parámetros; los dos motores coinciden |
| 7 · Análisis | RESULTADOS_ANALIZADOS | analizar, guardar análisis | Análisis y conclusión preliminar escritos |
| 8 · Revisión | EN_REVISION | enviar, puntos de revisión (abrir, responder, resolver), devolver a datos | Todos los puntos resueltos y con respuesta |
| 9 · Aprobación | APROBADO | aprobar | Conclusión revisada; excepciones evaluadas si las hay. Queda **inmutable**: los cambios exigen una nueva versión |

**Aprobaciones:** admin y operadores (`require_staff`), por decisión del dueño.
**Consecuencia declarada:** la misma persona puede preparar y aprobar. El registro
de quién hizo cada acción queda en la bitácora y en la cédula 12, así la revisión
posterior puede verlo. Si más adelante se quiere separación de funciones, se
añaden roles por encargo sin cambiar el circuito.

**Siempre disponibles:** encerar (borra evidencia, resultados e historial de la
prueba; conserva ficha y diseño) y eliminar (quita la prueba; si está aprobada
exige confirmación expresa). Ambos piden escribir el nombre del cliente, como en
el sitio.

---

## 6 · Evidencia y almacenamiento

- Ruta: `/var/data/aud_pruebas/<prueba>/<archivo>` en el disco persistente de
  Render, el mismo que usa el ICT.
- Límite por archivo: **25 MB** (el del sitio). Formatos: los que declara cada ítem.
- **Guarda de espacio:** si el espacio libre del disco baja de **150 MB**, se
  rechaza la subida con un mensaje claro («El almacenamiento del portal está casi
  lleno…») en vez de fallar a medias. El ICT sigue funcionando.
- Uso visible: la pantalla de la prueba muestra cuánto ocupa su evidencia.
- La extracción para **mostrar** el archivo (fórmulas, hojas, texto) la hace el
  navegador con `extract.mjs`. El **mapeo de datos** para el cálculo lo hace el
  servidor en Python, con la regla de `readSpreadsheet` portada y su batería
  espejo, para que las filas no dependan de lo que envía el navegador.
- Encerar y eliminar borran los archivos del disco. Una prueba aprobada conserva
  su evidencia y su papel final.

---

## 7 · Investigación de fuentes

Se porta `officialSources`: la lista fija de fuentes oficiales por marco (IFRS
Foundation, IAASB y, si aplica, SRI) y la verificación **manual** del auditor
(documento, párrafo, vigencia, procedimientos), con las mismas restricciones de
dominio del sitio (NIIF solo de ifrs.org, NIA solo de iaasb.org o ifac.org). La
consulta automática a esas páginas y la asistencia IA quedan para una fase
posterior.

---

## 8 · Pantallas

Dentro de la pestaña «Generación de herramientas NIIF» se añaden dos secciones:

- **«Pruebas del encargo»**: ficha del encargo del proyecto activo, lista de
  pruebas con su estado, botón «Nueva prueba» (catálogo o ficha probada) y la
  pantalla de la prueba con las 9 etapas en fila, como el sitio.
- **«En revisión y aprobados»**: las pruebas de todos los proyectos AUD en esos
  dos estados, para quien revisa.

Las cédulas se ven con el mismo visor del Recorrido y se descargan en Excel y
HTML; en una prueba aprobada se descarga el papel final guardado.

---

## 9 · Verificación (igual que hasta hoy)

- **Batería espejo** por cada regla portada: mismos casos y mensajes que el sitio.
- **pytest** del ciclo completo por HTTP, incluidos todos los rechazos.
- **E2E con clics** en un portal local con base propia: una prueba VNR de punta a
  punta, desde la ficha del encargo hasta el papel aprobado.
- **openpyxl** sobre cada Excel: sin referencias rotas ni texto peligroso.
- **Producción:** tras cada etapa, prueba con la sesión del dueño, sin crear datos
  salvo que él lo autorice.

---

## 10 · Etapas de construcción

| Etapa | Contenido | Se puede usar para |
|---|---|---|
| **E6** | Ficha del encargo · crear prueba (catálogo y ficha probada) · programa y fuentes · definición guardada al marcar una ficha probada | Preparar el programa de una prueba real |
| **E7** | Requerimiento · subida y rechazo de evidencia · cobertura · mapeo y validación · conciliación · guarda de espacio | Recibir y validar la evidencia del cliente |
| **E8** | Parámetros · metodología · ejecución con contraste · excepciones en Python · análisis · cédulas | Obtener resultados auditables |
| **E9** | Envío a revisión · puntos de revisión · devolver a datos · aprobación inmutable · versiones · guardar como plantilla · editar la ficha con alcance (una, varias o todas las pruebas) · bandejas · encerar y eliminar | Cerrar el papel de trabajo |

Después de E9: portal del cliente (fase 2), componentes con nombre, demostración,
asistencia IA.

---

## 11 · Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| 1 GB compartido con el ICT se llena | Guarda de 150 MB libres; uso visible; ampliar el disco es un cambio de configuración |
| Reglas portadas que divergen del sitio | Batería espejo; si el sitio cambia una regla, la prueba del portal no la tiene y lo delata al compararlas |
| Sin separación preparador/revisor | Decisión del dueño; bitácora y cédula 12 muestran quién hizo cada acción |
| Ficha probada sin definición guardada | No aparece al crear una prueba; el Estudio la guarda al marcarla probada |
