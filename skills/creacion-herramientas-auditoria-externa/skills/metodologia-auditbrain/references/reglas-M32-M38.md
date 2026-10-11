# Reglas M32–M38 · destiladas del módulo «Pasivos Acumulados y Gastos de Nómina» (v1.5.0)

Origen: construcción y verificación del módulo de nómina con el cliente piloto (bitácora v1.0 → v1.22, 2026). Son
requisitos para toda herramienta nueva, no descripción de la de nómina. Cada regla trae el caso que la motivó.

## M32 · Toda prueba nace de un requerimiento o de otra prueba, y vive en el panel
- Cada prueba declara de qué requerimientos (RQ) y de qué pruebas previas se alimenta; esa matriz de dependencias va en
  el FLUJOS del dominio y en el panel (`RQS[].nb`, tarjetas con `prog`/`prog2`).
- Las fuentes base se procesan primero (en nómina: planillas IESS DO-3 → roles DO-3.1) y después los reprocesos, cruces y
  conciliaciones que las consumen; la hoja de hallazgos va al final y consume todas.
- Un requerimiento **opcional** (en nómina RQ-007 solicitudes de acumulación y RQ-008 kárdex de vacaciones) **no bloquea**
  «Procesar»: si falta, la prueba queda en estado «NO SOPORTADO» y genera **una observación automática** (condición,
  criterio, efecto, recomendación) que sube a la hoja de hallazgos.
- Ninguna prueba se entrega como Excel suelto: si no tiene tarjeta y modal en el panel, no existe para el auditor.
- *Caso:* la calculadora de vacaciones y el muestreo de solicitudes se construyeron primero como libros sueltos; se
  rehicieron como pruebas del panel con su RQ y su observación automática.

## M33 · Libros provisionales hasta tener el mayor; el mayor se concilia con el anexo antes de usarlo
- Mientras el cliente no entrega el mayor, las cifras «según libros» que salen del anexo o de una estimación se marcan en
  **naranja (provisional)** con su nota; se sustituyen por fórmula al mayor cuando llega.
- Antes de usar un mayor: saldo inicial (anexo) + movimientos = saldo final (ESF) en **cada** cuenta de pasivo; gasto del
  mayor = anexo en las cuentas comunes; las cuentas que el anexo omite se listan en la sumaria (no se ignoran).
- Signo único del mayor: débito +, crédito −. La clasificación de movimientos sale del **concepto** del asiento por reglas
  explícitas, no de una agrupación hecha a mano por el equipo. Ver `patrones/mayores-rq004.md`.
- *Caso:* el anexo omitía 36 cuentas de gasto; una reversión de febrero parecía un pago; la diferencia de vacaciones era
  de ajustes manuales. Todo apareció al conciliar el mayor contra el anexo.

## M34 · Un generador reproducible por cédula; ninguna cifra del cliente en el código ni en los textos
- Cada cédula sale de un script (`mk_<cédula>.py`) que lee los insumos y escribe el libro con fórmulas; regenerar con datos
  nuevos (otro año, otro cliente) no exige tocar el código.
- Prohibido escribir importes, nombres o conteos del cliente en el código o en los textos de conclusión: los textos se
  arman con la celda calculada (`TEXT()`/`FIXED()` o f-string sobre el valor del motor).
- Los hallazgos de la hoja final salen de **reglas** (umbral, signo, estado de la prueba), no de una lista fija.
- Antes de entregar a integración se hace el **inventario de literales** (cifras del cliente que quedaron en el código) y
  se entrega como pendiente si no se eliminaron.
- *Caso:* en nómina quedaron 393 literales del cliente en los generadores; se declararon en el encargo como trabajo por
  hacer, no se ocultaron.

## M35 · Valores de control y privacidad de los datos del cliente
- Toda herramienta verificada con datos reales entrega `valores_control/VALORES_DE_CONTROL_<CLIENTE>_<AÑO>.json` (cifras
  finales por cédula) e `intermedios/*.csv` (resultados intermedios), con tolerancia declarada (0,01).
- Los datos reales del cliente **nunca** entran al repositorio, a `tests/fixtures` ni a ejemplos públicos: viajan en una
  carpeta separada `DATOS_PRIVADOS_<CLIENTE>_NO_SUBIR_AL_REPO/`, se usan solo para la aceptación local y se borran.
- Los ejemplos y pruebas automáticas del repositorio usan datos **ficticios**; un segundo juego alterado demuestra que
  no queda ninguna cifra del cliente en los textos.

## M36 · Rastro de cada cambio y año auditado visible
- Tras cada cambio: bitácora de versiones (vX.Y con qué cambió y por qué), FLUJOS del dominio, capturas del panel, ZIP
  acumulado de las pruebas y republicación del panel.
- El año auditado se declara en cada libro y en el panel. Si las cédulas se construyen con la plantilla de otro año
  (datos del año anterior mientras llega el del encargo), cada libro lleva la nota y se regeneran con los mismos
  generadores al recibir los datos.

## M37 · Normativa verificada en la fuente, con su estado
- La norma legal/laboral/tributaria se verifica en la web contra la fuente oficial (Registro Oficial, MDT, IESS, SRI) y se
  cita con su enlace en REGLAS. Lo no cotejado con texto oficial queda «pendiente de texto oficial» (o «†»), nunca como
  regla confirmada.
- Un criterio del socio que va más allá de la ley (p. ej. tope de acumulación de vacaciones a 5 períodos) se documenta
  como **decisión del socio**, en un parámetro editable (0 = sin tope), no como norma.
- Cuando la ley admite dos bases (p. ej. valor día = remuneración de corte / 30 o promedio de 12 meses / 30), la base es
  un parámetro seleccionable y el libro muestra la alternativa.

## M38 · Inspeccionar el repositorio antes de integrar
- Antes de preparar la entrega al Command Center: buscar si ya existe una herramienta del rubro (id, versión, qué
  cubre), leer el contrato del procesador y los precedentes (procesador declarativo/especializado frente a **artefacto
  HTML embebido** con su propio motor, como la planificación).
- Presentar al socio las opciones (reemplazar, convivir, extender) y registrar su decisión en el encargo; no decidir
  por él.
- Decir con honestidad cuánto falta: generadores pendientes, dependencias de papeles del equipo, literales del cliente.
  «Solo falta conectar» se afirma solo si se verificó. Ver `patrones/entrega-command-center.md`.
