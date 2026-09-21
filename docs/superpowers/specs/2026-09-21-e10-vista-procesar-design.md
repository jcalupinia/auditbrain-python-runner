# E10 · Vista de trabajo en cuatro bloques con «Procesar»

**Fecha:** 2026-09-21 · **Aprobado por el dueño** en la conversación del mismo día.
**Antecede:** `2026-09-21-ciclo-prueba-command-center-design.md` (E6–E9).

## 1 · Qué resuelve

El dueño trabaja así: el cliente entrega los documentos (correo o repositorio de
la firma), **el auditor los sube** y pulsa **Procesar**; la herramienta alimenta
todas sus pestañas y entrega ajustes, diferencias y problemas encontrados. El
cliente no sube nada: **la «fase 2 · portal del cliente» queda descartada.**

El circuito de E6–E9 (13 estados del sitio) se conserva como autoridad y
rastro de auditoría, pero la pantalla de cada prueba pasa a ser:

| Bloque | Contenido | Acción |
|---|---|---|
| 1 · Base técnica | NIIF completas, NIIF PYMES, NIA, tributario, resumen y enlaces oficiales (de la ficha) | «Confirmar base técnica y preparar el requerimiento» |
| 2 · Qué se calcula | Cada cálculo en lenguaje contable, resultado principal y campo de conciliación | — |
| 3 · Requerimiento y documentos | Cada documento con su botón **Subir**, formatos, rechazo y lo que falta; en los de cálculo, **Descargar modelo** | Descargar modelo / Subir / Rechazar |
| 4 · Procesar | Saldo del mayor (opcional) y **Procesar** → resultados, excepciones, problemas, cédulas y descargas | Procesar |

Revisión, puntos, aprobación y papel final (E9) siguen debajo, para cerrar el
papel de trabajo cuando se quiera. El detalle paso a paso queda en «Circuito
detallado», plegado.

## 2 · Cómo se implementa (sin reglas nuevas)

Los dos botones **orquestan en el navegador las acciones que ya existen**; cada
una la valida el servidor y queda en la bitácora con su actor. El orquestador
mira el estado actual y ejecuta solo lo que falta, así que si algo falla a
mitad se puede volver a pulsar.

- **Confirmar base técnica:** `research` → `generate_program` →
  `approve_program` (las fuentes oficiales se marcan verificadas con la
  referencia de la ficha y **la confirmación del auditor que pulsa**, y cada
  procedimiento queda vinculado) → `generate_request` → `approve_request`.
- **Procesar:** mapeo automático del reporte de cálculo → `map_validate` →
  `validate` → `configure` → `approve_methodology` → `execute` (contraste de
  los dos motores). Si ya se procesó y cambió la evidencia, «Reprocesar»
  devuelve a datos con su motivo y vuelve a correr.

Decisiones:

1. **Varios archivos, una población** (decisión del dueño): un requerimiento
   de cálculo puede declarar sus partes (12 meses de IVA; bodegas Quito,
   Guayaquil, Cuenca). Se sube un archivo por parte, en Excel o CSV, con el
   mismo modelo; **Procesar los une en una sola población** (`map_validate`
   con `files`) y cada fila conserva su archivo (`_file`) y su parte
   (`_component`). Un archivo rechazado no entra.
2. **Modelo universal.** Cada requerimiento de cálculo tiene su **modelo
   Excel** (`GET /aud/ciclo/pruebas/{id}/modelo/{requerimiento}`): hoja
   «Datos» con las columnas exactas de la ficha y su formato, y hoja
   «Instrucciones» con el documento, período, contenido mínimo y, por columna,
   tipo, obligatoriedad, formato y ejemplo. El auditor lo envía al cliente
   para que todos entreguen igual.
3. **Mapeo automático.** Se elige la hoja «Datos» (o la que más campos
   reconozca) y la fila de encabezados donde se reconocen más campos, por
   etiqueta, código o `aliases` de la ficha. Con el modelo el reconocimiento
   es total; si falta un campo, Procesar se detiene y muestra el mapeo manual
   de E7.
4. **Conciliación.** Si el auditor escribe el saldo del mayor, se concilia con
   tolerancia 0. Si no, se procesa igual y queda la aceptación «Conciliación
   con el mayor pendiente…», que aparece como **problema** en el resultado y
   debe resolverse antes de aprobar el papel (E9 no cambia).
5. **Revisión de evidencia y sustento de parámetros.** Se registran con texto
   automático que dice quién procesó, cuántos archivos y de qué ficha salen
   los parámetros. La PCE del catálogo sigue pidiendo sus tramos de mora.
6. **Resultado.** Totales, ajuste principal, excepciones por partida, errores
   y advertencias de validación y conciliación, en un solo bloque; debajo, las
   cédulas y las descargas Excel/HTML.

## 3 · Ficha

La ficha puede traer además `summary` (resumen técnico), `nia` (lista) y, en
cada campo, `aliases` (nombres de columna habituales) y `example` (valor de
ejemplo para el modelo). El encargo a ChatGPT se
actualiza para pedirlos.

## 4 · Verificación

pytest del modelo (abre con openpyxl, columnas = campos de la ficha, se
procesa de vuelta sin mapeo manual); vitest del mapeo automático, de las
fórmulas legibles y del orquestador; recorrido con clics: crear, confirmar base
técnica, descargar el modelo, llenarlo, subirlo, Procesar, ver el resultado y
descargar las cédulas.
