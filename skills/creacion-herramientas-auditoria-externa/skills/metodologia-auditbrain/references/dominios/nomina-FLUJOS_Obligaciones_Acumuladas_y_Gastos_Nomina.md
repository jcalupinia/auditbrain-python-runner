---
nombre: flujos-obligaciones-acumuladas-gastos-nomina
modulo: AUD › Pruebas de Auditoría › Pasivos Acumulados
version: 1.8
fecha: 2026-10-06
responsable: Jorge — Socio de Auditoría (Lider Audit-IA)
firma: Auditconsulting Auditores Cía. Ltda.
estado: 5 de 11 pruebas terminadas
ubicacion: SharePoint › Account Consulting › Audit Consulting Group › Ecosistema Auditoría Externa › Herramientas de Auditoría Externa › Obligaciones Acumuladas y Gastos Nómina
---

# Flujos y procesos — Obligaciones Acumuladas y Gastos Nómina

Documento de referencia del ecosistema de herramientas de auditoría externa para el rubro de pasivos acumulados laborales y gastos de nómina. Registra la arquitectura, los requerimientos, las dependencias y el flujo operativo de las pruebas ya terminadas. Sirve como base de la memoria del ecosistema y como insumo de la entrega a Claude Code para su integración en AuditBrain.

## 1. Principios de diseño

1. **Todo nace relacionado.** La herramienta recibe los datos del encargo desde el Command Center; nunca los incrusta. Lección aprendida en la herramienta de planificación LANSEY v19, donde el objeto `PERFIL` quedó fijo en el HTML y el Command Center y la herramienta se divorciaron.
2. **Los datos del encargo nunca se recapturan.** Identidad del cliente, RUC, ejercicio, visita, marco técnico y logos viajan desde la Ficha del Encargo.
3. **Artefactos HTML autónomos.** La lógica de cálculo vive en el código; no se invoca a Claude en tiempo de ejecución.
4. **100% de la población, sin muestreo.** El cálculo es determinístico sobre todos los registros.
5. **Formato del papel de trabajo respetado.** Las cédulas conservan el formato original de la firma (encabezado, columnas, marcas y referencias); no se agregan columnas visibles.
6. **Revisión humana obligatoria.** Las conclusiones son borradores condicionados que firma el auditor.

## 2. Flujo general del módulo

```
Ficha del Encargo (Command Center)
        │  postMessage {type:'auditbrain:encargo'}  o  hash #encargo=<base64>
        ▼
Selección de la prueba: Pasivos Acumulados y Gastos Nómina
        ▼
BLOQUE 1 — REQUERIMIENTOS (RQ-001 … RQ-006)
   carga por lotes · multiformato · eliminación individual (✕)
        ▼  6/6 documentos validados
BLOQUE 2 — PROCESAMIENTO
   [Procesar] habilitado solo con 6/6 · [Encerar] con doble confirmación
   Motor en 3 capas: consolidación → cálculo determinístico → conciliación y hallazgos
        ▼
BLOQUE 3 — EJECUCIÓN (11 pruebas)
   Fuentes base primero: Resumen de Planillas IESS (DO-3) → Resumen de Roles de Pago (DO-3.1)
   → luego reprocesos, cruces y conciliaciones que las consumen
   Orquestador: verifica dependencias, ejecuta en cadena,
   escribe en un espacio de resultados compartido
        ▼
Cada prueba: botón → subpantalla/modal → trabajo → cierre → siguiente
        ▼
Hallazgos y Ajustes de Auditoría (al final, consume todas)
```

Regla de interfaz: al presionar el botón de una prueba se despliega su HTML en un modal; se trabaja, se cierra y se continúa con la siguiente. Nada queda colgando debajo del botón.

## 3. Requerimientos al cliente

| Código | Documento | Observación |
|---|---|---|
| RQ-001 | Cuestionario laboral IESS–MDT | Plantilla incorporada; la ejecuta el auditor en campo |
| RQ-002 | Anexo de Pasivos y Gastos de Nómina | Saldos comparativos por cuenta |
| RQ-003 | Consolidado IESS (por región) | Dos sub-compartimentos: Sierra / Amazonía y Costa / Galápagos; basta una región para cubrir el requerimiento. Reporte `detallePlanillaConsolidado` del IESS: un registro por trabajador y mes. **Fuente base de los cálculos posteriores** (beneficios sociales, base imponible) |
| RQ-004 | Mayores de Nómina | Base para cuadre de saldos |
| RQ-005 | Comprobantes de Pago IESS | 4 sub-compartimentos: aportes, fondos de reserva, préstamos quirografarios, préstamos hipotecarios |
| RQ-006 | Rol de Pagos | Detalle por trabajador y mes |
| RQ-007 | Por definir con el socio | Aparece en la tarjeta del panel para el Reproceso. Propuesta alineada al Manual de Beneficios Sociales 2026: nómina con fecha de ingreso, región del lugar de trabajo, opción de pago de décimos con solicitudes escritas de acumulación, y kárdex de vacaciones |

La extracción de PDF e imágenes se resuelve con Python en Claude Code.

## 4. Matriz de dependencias de las pruebas

| # | Prueba | Requerimientos | Papel de trabajo | Estado |
|---|---|---|---|---|
| 1 | Procedimiento de Auditoría Nómina | RQ-001, RQ-002, RQ-004 | — | Pendiente |
| 2 | Evaluación de Control Interno Laboral | RQ-001 | DO-1 | **Terminada** |
| 3 | Sumaria de Nómina | RQ-002, RQ-004 | DO-2 | **Terminada** |
| 4 | Resumen de Planillas de Aportes IESS | RQ-003 | DO-3 | **Terminada** |
| 5 | **Resumen de Roles de Pago** | RQ-006 | DO-3.1 | **Terminada** |
| 6 | Reproceso de Beneficios Sociales por Pagar | RQ-003, RQ-005, RQ-006, RQ-007 | DO-4 Reproceso | **Terminada** — reajustada con DO-3.1 (fondos de reserva incluidos) |
| 7 | Reproceso de Gastos y Beneficios Sociales | RQ-004, RQ-006 | DO-6 / DO-7 | Pendiente |
| 8 | Análisis de Base Imponible IESS | RQ-003, RQ-004, RQ-006 | DO-8 | Pendiente |
| 9 | Conciliación Libros vs Planillas IESS | RQ-004, RQ-005 | DO-9 | Pendiente |
| 10 | Conciliación Libros vs Roles de Pago | RQ-004, RQ-006 | DO-10 | Pendiente |
| 11 | Hallazgos y Ajustes de Auditoría | Todas | DO-12 | Pendiente |

## 5. Prueba terminada 1 — Evaluación de Control Interno Laboral (DO-1)

**Naturaleza.** Prueba que ejecuta el auditor en campo; no es un documento del cliente. Figura como RQ-001 (plantilla incorporada) y su ejecución vive en el botón de Control Interno Laboral.

**Artefacto.** `Control_Interno_Laboral.html` — autónomo, publicado en https://claude.ai/artifact/T6DUJER2AiDfBqoiDKcU9x

**Base normativa.** Cuestionario Laboral IESS–MDT 2026 consolidado, versión 2026.1, corte 05-oct-2026: 72 ítems en 10 bloques.

| Bloque | Tema | Ítems |
|---|---|---|
| A | Documentos habilitantes | 5 |
| B | Contratación / SUT | 3 |
| C | Remuneraciones | 15 |
| D | Terminación | 2 |
| E | IESS | 7 |
| F | Inclusión | 9 |
| G | Seguridad y salud | 14 |
| H | Regímenes especiales | 7 |
| I | Soporte SRI | 3 |
| J | Gobierno corporativo | 7 |

**Parámetros 2026.** SBU USD 482; salario digno 2025 USD 506,99; fondos de reserva 8,33%; aporte personal 9,45%.

**Flujo dentro del modal.**

1. **Inicio:** el auditor registra el número de trabajadores; una tabla de umbrales reactiva determina qué ítems aplican.
2. **Bloques A a J:** un bloque por pantalla. Respuestas Sí / No / Parcial / N/A, referencia de papel de trabajo y observación.
3. **Resumen:** KPIs de cumplimiento por bloque y total.
4. **Salidas:** impresión, PDF A4 horizontal, HTML y Word .docx generado sin librerías externas.

**Reglas automáticas.**

- *N/A por umbral de trabajadores*, con opción "Evaluar de todas formas": 1–10 (ítem 44); 10+ (38, 46, 47); >10 (45, 48, 49); 25+ (33); 50+ (36, 41).
- *Marca "Confirmar" en Fiel Web* para los ítems 7, 27, 46, 47, 52 y 54.
- *Referencia PT precargada:* 10 → DO-10; 28 → DO-8; 29 y 32 → DO-9; 16, 17 y 20 → DO-4 / DO-5.
- *Borradores de observación* editables por el auditor.
- *Persistencia* local por clave `RUC-ejercicio-visita`.

**Logos.** AUDIT-IA siempre; firma según quién audita (Auditconsulting o Partner Auditing); logo del cliente opcional. Los tres viajan desde la Ficha del Encargo.

**Calificación de riesgo (propuesta, pendiente de confirmar).** % de cumplimiento = Sí / (Sí + No + Parcial). Un "No" en ítem de riesgo Alto o cumplimiento menor al 70% → ALTO; entre 70% y 90%, o "Parcial" en ítem de riesgo Alto → MEDIO; 90% o más → BAJO.

## 6. Prueba terminada 2 — Sumaria de Nómina (DO-2)

**Artefacto.** `DO-2_Cedula_Sumaria_Nomina.xlsx` (48.541 bytes), construido sobre el formato original DO-2 de la firma.

**Insumos.** RQ-002 Anexo de Nómina (165 cuentas: 10 de pasivo acumulado y 155 de gasto de nómina). RQ-004 Mayores, para el cuadre de saldos (pendiente de integrar en la herramienta).

**Formato conservado.** Logo Partner Auditing, banda azul "OBLIGACIONES ACUMULADAS", encabezado (cliente, período, preparado, revisado, fecha, referencia DO-2) y columnas B–N: Código, Descripción, Saldo 31-dic-24, Variación, Porcentaje, Saldo 31-dic-25, marca, Debe, Haber, marca, Saldo Auditado, marca, Referencia. Totales con Σ. Pasivo en filas 11–21 (total fila 23); gasto desde la fila 25 (total fila 187).

**Reglas de cálculo aprobadas.**

| Concepto | Regla |
|---|---|
| Saldo auditado | `= Saldo 2025 + Debe − Haber` (corrige el modelo anterior, incorrecto con pasivos en negativo) |
| Porcentaje de variación | `= IF(Saldo 2024 = 0, 0, Variación / ABS(Saldo 2024))`; las cuentas sin saldo 2024 muestran 0% |
| Marca ✓ de cuadre | En la herramienta solo aparece al cuadrar contra Mayores (RQ-004); en el Excel se mantiene fija como en el modelo |
| Conclusión | Borrador condicionado, firmado por el auditor |
| Encabezado | Campos alimentados desde la Ficha del Encargo |

**Resumen del gasto por concepto.** Bloque añadido desde la fila 189 (datos 192–199, total fila 200) mediante COUNTIF / SUMIF sobre una columna auxiliar oculta (P) y el nombre definido `resumen_concepto`, para cruzar con las pruebas siguientes.

| Concepto | Nº cuentas | Saldo auditado 2025 (USD) |
|---|---:|---:|
| Sueldos | 20 | 1.589.628,97 |
| Horas Extras | 17 | 170.746,03 |
| Bono Desempeño | 20 | 538.111,47 |
| Décimo Tercer | 22 | 183.639,53 |
| Décimo Cuarto | 19 | 63.953,92 |
| Fondos de Reserva | 23 | 193.660,36 |
| Aporte Patronal | 30 | 297.457,82 |
| Otros gastos de nómina | 4 | 349,18 |
| **Total** | **155** | **3.037.547,28** |

Reglas del clasificador por palabra clave en la descripción: patronal → Aporte Patronal; hora → Horas Extras; bono / desempeño → Bono Desempeño; tercer → Décimo Tercer; cuarto → Décimo Cuarto; fondo + reserva → Fondos de Reserva; vacación → Vacaciones; sueldo → Sueldos; resto → Otros gastos de nómina.

**Controles de integridad (hoja Controles).** Los 10 controles dan OK con diferencia 0,00: 165 cuentas trasladadas; pasivo 2024 y 2025; gasto 2024 y 2025; subtotales por concepto igual al total del gasto; 155 cuentas agrupadas; saldo auditado = 2025 + Debe − Haber en pasivo y en gasto; asiento cuadrado (Σ Debe = Σ Haber). Verificación de recálculo: 576 fórmulas, 0 errores.

**Prueba de funcionamiento sugerida.** Registrar un Debe de 1.000 en Aporte Patronal por pagar: el saldo auditado pasa de −26.463,99 a −25.463,99 y el control de cuadre muestra "REVISAR" hasta registrar la contrapartida.

**Revisión analítica preliminar.**

- Pasivo acumulado: USD −414.464,24 (2024) → USD −235.722,63 (2025).
- Gasto de nómina: USD 3.280.285,67 (2024) → USD 3.037.547,28 (2025), −7,4%.
- 59 cuentas nuevas en 2025 y 8 cuentas sin saldo en 2025, por reorganización de centros de costo.
- Décimo tercero por pagar ≈ 0,95 meses; décimo cuarto Sierra ≈ 4,6 de 5 meses esperados; aporte patronal por pagar ≈ 1,07 meses.
- **Variaciones que exigen explicación del cliente:** Sueldos por pagar (−98,7%, de 163.461 a 2.166) y Liquidaciones e indemnizaciones por pagar (−87,2%, de 35.029 a 4.478). Se cruzarán en DO-10 contra roles de pago.

## 7. Prueba terminada 3 — Resumen de Planillas de Aportes IESS (DO-3)

**Alcance (decisión del socio).** Solo aportes al IESS. El Consolidado IESS (RQ-003) queda como reporte base para los cálculos de beneficios sociales y base imponible de las pruebas siguientes; por eso la DO-3 ya no depende del Rol de Pagos (RQ-006).

**Artefacto.** `DO-3_Resumen_Planillas_IESS.xlsx`, construido sobre el formato `RESUMEN DE PLANILLAS` de la firma. Hojas: DO3 Resumen de Planillas, Parámetros, Detalle RQ-003 y Controles.

**Formato del RQ-003.** Hoja única `detallePlanillaConsolidado`, encabezado en la fila 2, columnas: Período (AAAA-M), Cédula, Nombre, Relación de trabajo, Sueldo (base imponible), Días, Patronal, Individual, Aporte adicional, Cesantía, % CCC (código 0–4, no porcentaje), Valor CCC y Total Aporte (= Patronal + Individual, sin CCC). Cierra con fila `Totales :`. Archivo .xls legado: se convierte a .xlsx antes de leerlo.

**Formato DO-3 conservado.** Logo, banda "OBLIGACIONES ACUMULADAS", encabezado; columnas B Mes · C Nº empleados · D Base imponible · E Aporte personal · F Aporte patronal · G Valor CCC · H Fondos de Reserva · I Días laborados (oculta) · J Total aporte = E+F+G. Meses en filas 22–33, Σ en fila 34, marcas en fila 35, control de discapacidad (4%) en C37. Logo Partner Auditing incrustado dentro de la banda (filas 1–2, columnas B–C), en versión clara para el fondo oscuro y anclado para moverse y ajustarse con las celdas; no se superpone al encabezado.

**Reglas de cálculo.**

| Concepto | Regla |
|---|---|
| Columnas C–G e I | COUNTIFS / SUMIFS por mes sobre la hoja Detalle RQ-003 |
| Fondos de Reserva (H) | 0 en DO-3: no están en el consolidado; se verifican contra comprobantes (RQ-005) en DO-9. Se eliminaron los vínculos externos rotos del modelo |
| Recálculo por registro | Base × tasa según relación de trabajo (hoja Parámetros, editable): 06 Código del Trabajo y 16 Jornada parcial → patronal 11,15%, individual 9,45%, CCC 1%; 74 Pasantes → patronal 0%, individual 17,60%, CCC 0% (esquema de la planilla, base legal por confirmar) |
| Estado | "‡ REVISAR" si alguna diferencia supera USD 0,01 (tolerancia parametrizada) |
| Control de inclusión | C37 = 4% del personal de diciembre; se verifica contra el Bloque F del checklist DO-1 |
| SBU 2025 | USD 470 (el de 2026 es USD 482) |

**Población.** 1.745 registros trabajador-mes, 168 trabajadores (150 Código del Trabajo, 8 jornada parcial, 10 pasantes); 129 trabajaron los 12 meses.

| Concepto | Total 2025 (USD) |
|---|---:|
| Base imponible | 2.437.124,78 |
| Aporte personal | 231.930,42 |
| Aporte patronal | 269.521,55 |
| Valor CCC | 24.238,51 |
| Total aporte DO-3 (E+F+G) | 525.690,48 |

**Controles.** 13 controles en OK con diferencia 0,00 (registros, base, patronal, individual, CCC y total contra la fila Totales del reporte; Total IESS = Patronal + Individual; totales DO-3 = detalle; J = E+F+G). Recálculo: 12.473 fórmulas, 0 errores.

**Resultado del recálculo.** 36 registros con diferencia en 17 trabajadores. Diferencias netas: patronal +530,66 · individual −388,61 · CCC −18,38.

- **Hallazgo principal:** Trabajador A (7 meses) y Trabajador B (4 meses), con relación Código del Trabajo, aportaron con el esquema de pasante (0% patronal, 17,6% individual). Base USD 4.762,66; patronal omitido USD 531,08; individual cobrado en exceso USD 388,11.
- **Valor CCC:** 15 trabajadores con CCC distinto del 1% (valores fijos arrastrados de otros meses; un caso con base 0 y CCC 5,41). Diferencia menor, por explicar.

**Cruces informativos con DO-2.** Patronal + CCC (293.760,06) vs gasto Aporte Patronal (297.457,82): diferencia −3.697,76, se resuelve en DO-6/DO-7. Base imponible vs Sueldos + Horas Extras + Bono (2.298.486,47): diferencia 138.638,31, se resuelve en DO-8.

## 8. Prueba terminada 4 — Reproceso de Beneficios Sociales por Pagar (DO-4 Reproceso)

**Artefacto.** `DO-4_Reproceso_Beneficios_Sociales.xlsx`, construido sobre la pestaña `DO4 REPROCE BEN SOCIA` del papel de trabajo. Hojas: DO4 Reproceso Ben Sociales, Parámetros, Detalle RQ-003 y Controles.

**Origen de datos.** Toma la información del Resumen de Planillas: el mismo Consolidado IESS (RQ-003) que sustenta la DO-3. Las columnas C–H coinciden con DO-3 (controlado contra D34 y J34).

**Formato conservado.** Columnas B Mes · C Nº empleados · D Base imponible · E Aporte personal · F Patronal · G CCC · H Total aporte (= E+F+G, como en DO-3) · I Décimo tercero · J Décimo cuarto · K Vacaciones · L Fondos de reserva · M Días (oculta). Meses en filas 19–30, Σ en fila 31. Se corrigieron arrastres del modelo: título "Reproceso de Beneficios Sociales" (decía "Resumen Planilla IESS"), Ref. PT DO-4 (decía DO-3), objetivo y procedimiento, vínculos externos rotos de Fondos de Reserva. Logo incrustado en la banda.

**Metodología (deducida del modelo y verificada al centavo en los meses sin excepciones).**

| Beneficio | Regla por trabajador-mes |
|---|---|
| Décimo tercero | Base imponible / 12 |
| Décimo cuarto | SBU 470 / 12 × días / 30 (Sierra–Amazonía) |
| Vacaciones | Base imponible / 24 |
| Fondos de reserva | 8,33% de la base desde el mes 13 de servicio; requiere fecha de ingreso (RQ-007) |
| Exclusiones | Pasantes (relación 74); décimos de trabajadores mensualizados (lista editable en Parámetros) |

**Reglas aplicables.** Ver `REGLAS_Beneficios_Sociales_Ecuador.md` (IDs RG, D13, D14, FR, VAC, V01–V10, PR), con la trazabilidad regla → celda de la cédula.

**Fuente normativa.** Manual Consolidado de Capacitación — Beneficios Sociales del Trabajador, Ecuador 2026 (AuditSmart Pro): matriz general, reglas por beneficio y matriz de validaciones V01–V10. La metodología del reproceso coincide con el manual (D14 = SBU/360 × días equivale a SBU/12 × días/30).

**Observación al manual.** Para Sierra y Amazonía indica período 1-sep a 31-ago con pago hasta 15-ago, lo que es inconsistente (el pago caería antes del cierre). El período vigente es 1-ago a 31-jul; el reproceso usa agosto–diciembre como pendiente al 31-dic. Corregir el manual.

**Matriz de validaciones (hoja Controles).** V01, V02 y V03 automáticas: 0 casos. V04–V05 pendientes de fecha de ingreso (RQ-007). V06 se prueba contra la provisión del cliente en DO-10. V07 cubierta por la base de materia gravada (puente en DO-8). V08: 156 trabajadores acumulan décimos, por lo que deben existir sus solicitudes escritas (la ley establece pago mensual salvo solicitud). V09 requiere kárdex; V10 requiere comprobantes de pago.

**Mensualizados.** El modelo excluye de ambos décimos a [presidente] y [representante legal] (16.000 mensuales de base de enero a septiembre; 21.872,78 en octubre y noviembre; 31.872,78 en diciembre). Se registraron como inferidos, a confirmar con RQ-007.

**Diferencia con el modelo.** El modelo excluyó todos los registros con patronal 0, incluidos Trabajador A y Trabajador B (Código del Trabajo con esquema de pasante). El reproceso los incluye por su relación de trabajo: +396,89 en D13 y D14 y +198,44 en vacaciones (base 4.762,66). Los demás meses cuadran al centavo.

**Cálculo por región (decisión del socio).** El reproceso se calcula en dos bloques, Sierra/Amazonía y Costa/Galápagos, con un resumen por región, porque el décimo cuarto tiene período y fecha de pago distintos (Sierra: ago–jul, pago 15-ago, 5 meses pendientes al 31-dic; Costa: mar–feb, pago 15-mar, 10 meses pendientes). La región se asigna por registro según el archivo RQ-003 cargado. Este cliente opera solo en Sierra: el bloque Costa queda en cero.

**Resultado anual.** Décimo tercero 183.531,04 · Décimo cuarto 63.466,97 · Vacaciones 100.916,28 · Fondos de reserva pendiente.

**Provisiones al 31-dic-2025 (insumo del Cruce Global del Pasivo).**

| Beneficio | Devengo | Reproceso | DO-2 (ESF) | Diferencia |
|---|---|---:|---:|---:|
| Décimo tercero | Diciembre | 15.137,31 | 14.478,17 | −659,14 |
| Décimo cuarto Sierra | Agosto–diciembre | 26.145,06 | 24.695,21 | −1.449,85 |
| Vacaciones | Saldo 2024 + provisión 2025 | 220.951,85 | 130.720,39 | −90.231,46 (antes de goces y liquidaciones) |
| Fondos de reserva | Diciembre | pendiente | 1.433,34 | pendiente |

**Controles.** 12 controles en OK con diferencia 0,00, más la matriz V01–V10; recálculo con 17.752 fórmulas y 0 errores.

## 8-bis. Decisión de orden — Resumen de Roles de Pago antes de los reprocesos

**Decisión del socio (6-oct-2026).** Las diferencias del Reproceso de Beneficios Sociales son **preliminares**: se calcularon solo contra la provisión del cliente y el rol de pagos explica buena parte de ellas (mensualización real, liquidaciones y finiquitos, goces de vacaciones, ingresos y salidas). Por eso el rol se procesa como **fuente base**, inmediatamente después del Resumen de Planillas IESS y antes de cualquier reproceso.

- **Códigos:** se mantienen. El rol sigue siendo el **RQ-006**; solo cambia el orden de ejecución. La nueva cédula se identifica como **DO-3.1** para no renumerar las referencias existentes.
- **Contenido previsto de DO-3.1:** consolidado por trabajador y mes con sueldo, horas extras, bonos, décimos (mensualizados o acumulados), fondos de reserva pagados en rol, vacaciones gozadas, liquidaciones y finiquitos, fecha de ingreso y salida, y región.
- **Efecto en DO-4 Reproceso:** la lista de mensualizados, la fecha de ingreso (fondos de reserva desde el mes 13) y los goces y liquidaciones dejan de ser supuestos (PR-05) y se toman de DO-3.1. Las diferencias se recalculan y recién entonces pasan a la Hoja de Hallazgos.
- **Efecto en el orquestador:** DO-3.1 escribe en el espacio de resultados compartido; lo leen DO-4, DO-6/DO-7, DO-8 y DO-10.

## 8-ter. Prueba terminada 5 — Resumen de Roles de Pago (DO-3.1)

**Archivo:** `DO-3.1_Resumen_Roles_de_Pago.xlsx` (generador `mk_do31.py`). **Fuente (decisión del socio):** `Rol_historico_2025.xlsx`, **solo la hoja «normal»** (empleados y jubilados). Los pasantes no forman parte del rol que se audita; sus registros quedan identificados en el IESS como «fuera del rol».

**Hojas:** DO3.1 Resumen Roles (mensual por concepto, provisiones del cliente, jubilados) · Detalle Rol (1.723 registros) · Detalle RQ-003 (con marca «En rol normal») · Maestro Trabajadores (160 personas) · Cruce Rol vs IESS · Parámetros · Controles.

**Cruce de identidad:** por nombre contra el RQ-003 (el rol no trae cédula); 0 registros sin cédula.

**Resultados clave:**
- Rol «normal» sin jubilados: **1.699 registros y 158 trabajadores**, todos presentes en el IESS. IESS fuera del rol: **46 registros de pasantes** (base 19.896,64; aporte 3.501,81). 1.699 + 46 = 1.745 (total RQ-003).
- Jubilados patronales: 2 personas, 24 registros, 7.402,30.
- Total ingresos 2.756.785,88 · líquido 2.204.685,05 · vacaciones gozadas 99.322,01 · fondos de reserva en rol 176.931,88 (138 trabajadores) · liquidaciones y finiquitos 129.970,53 (18 liquidados).
- Provisión patronal rol 293.956,01 + aporte pasantes IESS 3.501,81 = **297.457,82 = gasto DO-2**. Aporte adicional 4,41% JP 349,18 = «Otros gastos de nómina» DO-2.
- **Base gravada rol 2.422.139,00 vs base IESS 2.417.228,14: diferencia +4.910,86** en 22 trabajadores (mayores: Pérez Orozco −1.740, Ramos Tapia +1.710, Rivera Jaramillo +1.123,02, Sánchez Naranjo +739,38).
- Aporte personal: dif. 203,73 · aporte patronal (patronal + CCC): dif. 195,95.
- Provisiones del cliente: D13 174.967,98 · D14 62.134,06 · vacaciones 128.050,19 · fondos de reserva 16.728,48 (= gasto FR DO-2 − FR en rol, cuadre exacto).
- **Mensualizados: 10 en D13 y 10 en D14.** El representante legal y el presidente no mensualizan: el supuesto anterior de DO-4 queda refutado (PR-05).
- Trabajador A y Trabajador B: en el rol «normal» solo desde su relación laboral (oct y jul); sus meses de pasantía constan en el IESS fuera del rol con código 06 → el hallazgo de DO-3 se reformula como inconsistencia de código de relación.

**Controles:** 13 en OK, 28.799 fórmulas, 0 errores.

**Siguiente:** reajustar DO-4 Reproceso para leer del Maestro (mensualizados, fecha de ingreso vigente, liquidados, goces) y calcular fondos de reserva.

## 8-quater. Reajuste de DO-4 Reproceso con el rol (DO-3.1)

**Cambios:** hoja «Insumo DO-3.1» (1.699 registros del rol «normal» sin jubilados); por registro IESS se traen presencia en rol, actividad al 31-dic, décimos mensualizados, FR pagado, goces, finiquitos y provisiones del cliente. Reglas RL-01 a RL-06 y FR-08/FR-09.

**Cuadre de gasto (RL-06):** D13 9.218,99 + 174.420,54 = 183.639,53 = DO-2 · D14 2.294,06 + 61.659,84 = 63.953,90 (−0,02) · FR 176.931,88 + 16.728,48 = 193.660,36 = DO-2. Los libros reflejan el rol.

**Pasivo al 31-dic (reproceso vs DO-2):** D13 17.112,85 vs 14.478,17 (−2.634,68) · D14 24.993,56 vs 24.695,21 (−298,35) · vacaciones 105.906,73 vs 130.720,39 (+24.813,66, sobreprovisión) · FR 1.433,30 vs 1.433,34 (cuadra).

**Hallazgos:**
1. **D13 no provisionado a [representante legal] (−11.724,03) y [presidente] (−6.577,50):** no mensualizan según el rol y figuran en el IESS con relación 06; el cliente no les provisiona D13 (sí FR y vacaciones). Confirmar naturaleza del vínculo (mandato vs Código del Trabajo). Explica el 98% de la diferencia anual de D13 (−17.796,15) y casi toda la del pasivo.
2. **Vacaciones sobreprovisionadas:** el cliente provisiona ≈5,25% de la base contra 4,17% (1/24); exceso anual 27.332,35 y pasivo sobrestimado en 24.813,66 (mayor efecto en directivos).
3. **V04 – Rivera Jaramillo:** FR pagado en rol (45,03, junio) en un mes con base IESS 0; ligado a su diferencia de base rol vs IESS (+1.123,02, DO-3.1).

**Validaciones:** V01–V03 = 0 · V04 = 1 · V05 = 0 · V08 = 148 trabajadores que acumulan (exigir solicitudes escritas). **Controles:** 28 en OK, 45.944 fórmulas, 0 errores.

## 9. Decisiones pendientes

1. Reclasificar las 4 cuentas (USD 349,18) de "Otros gastos de nómina": identificadas en el rol como aporte adicional 4,41% JP; confirmar la cuenta destino.
2. Confirmar la regla de calificación de riesgo del checklist.
3. Definir si el checklist bloquea Procesar o solo se exige antes de cerrar la Hoja de Hallazgos.
4. Confirmar el contrato de datos del encargo (identidad, logo del cliente, marco técnico, gobernanza, estado del flujo).
5. Confirmar si la herramienta debe funcionar fuera de Claude Code (sin Python).
6. Resolver si el saldo auditado de la Sumaria alimenta las cédulas de cruce o cada una toma sus propios valores.
7. Integrar la Sumaria DO-2 al panel como segundo botón activo.
8. Obtener la versión horizontal del logo Partner Auditing.
9. Trasladar la estructura al sitio propio "Audit Consulting Group" cuando se cree.
10. Confirmar con el cliente la relación de trabajo de Trabajador A y Trabajador B (pasantes mal clasificados o error de planilla).
12. Definir el contenido y formato del RQ-007 (con el rol ya disponible, se limita a solicitudes escritas de acumulación y kárdex de vacaciones). La lista de mensualizados, la fecha de ingreso y los goces se tomarán del rol de pagos (DO-3.1); el RQ-007 queda solo para lo que el rol no contenga (solicitudes escritas de acumulación, kárdex de vacaciones).
13. Décimo cuarto de jornada parcial: hoy por días; confirmar horas para prorratear por jornada.
14. Actualizar la matriz de requerimientos del panel: las tarjetas pueden mostrar requerimientos distintos de los definidos inicialmente (caso Reproceso: RQ-003, RQ-005, RQ-007). Ya actualizado en el panel: Resumen de Planillas → RQ-003; Reproceso → RQ-003, RQ-005, RQ-007.
11. Confirmar la base legal de la tasa de pasantes (0% patronal / 17,60% individual) y el significado del "Valor CCC" (indicio: IECE 0,5% + SECAP 0,5%).

## 10. Próximos pasos

**Inmediato:** recibir el formato del rol de pagos (RQ-006), construir DO-3.1 y reajustar DO-4 Reproceso para que consuma sus datos. Después, continuar prueba por prueba (DO-4 Cruce Global, DO-5 a DO-10 y DO-12), tomando el Consolidado IESS como base de cálculo, con el patrón botón → modal → cierre, y preparar la entrega a Claude Code conforme a la receta de la skill de creación de herramientas de auditoría externa.

## 8-quinquies. Exclusiones de beneficios por decisión del auditor (DO-4, v1.9)

- **Código 109** (representante legal / administrador por nombramiento) agregado a Parámetros como «No aplica beneficios»: exclusión automática de todos los beneficios.
- **Nuevo insumo opcional del RQ-003: «Exclusiones»** (`RQ-003_Exclusiones_Beneficios.xlsx`). Se listan solo las personas con código 06 que no deben generar uno o más beneficios; «X» por beneficio (D13, D14, vacaciones, FR) y motivo obligatorio. No bloquea el procesamiento.
- DO-4: hoja «Exclusiones», columnas AM–AU del detalle (marcas, motivo y valores excluidos), columna «Excluido por el auditor» en la conciliación con el rol y bloque «Exclusiones aplicadas» por persona. Validación nueva **V11** (FR pagado en rol a persona excluida).
- Caso cliente piloto: [representante legal] (representante legal) y [presidente] (presidente) — se excluyen D13, D14 y FR; conservan vacaciones. Excluido: D13 18.301,53 · D14 940,00 · FR 18.294,21.
- Pendiente en el panel: compartimento «Exclusiones» dentro de la tarjeta RQ-003.

## 8-sexies. DO-4C Cruce Global y DO-5 Cruce Mensual del Pasivo (v1.11)

**Referencia de formato:** papel de trabajo «DO - Pasivos Acumulados.xlsx» (pestañas DO4 Cruc Global Pasivo y DO5 Cruce MensPasivo). El módulo pasa a **13 pruebas**: las dos nuevas tarjetas van inmediatamente después del Reproceso de Beneficios. Los códigos RQ no cambian.

**Archivo:** `DO-4C_DO-5_Cruce_Pasivo_Beneficios.xlsx` (generador `mk_do45.py`). Hojas: DO4 Cruce Global Pasivo · DO5 Cruce Mensual Pasivo · Ficha · Libros · Insumo Auditoría · Controles. 9 controles OK, 209 fórmulas, 0 errores.

**DO-4C — fórmula del papel:** Total diferencia = (Según ESF − Según auditoría bruto) + Liquidaciones + Ajuste + Finiquito + Pago mensual.
- D13: bruto = devengado de diciembre (base/12, sin exclusiones) 15.137,31; pago mensual rol 680,53.
- D14 Sierra: bruto ago–dic 26.090,22; finiquito (devengado de salidos) 569,22; pago mensual 919,16.
- Vacaciones: saldo inicial 120.035,57 + provisión 100.717,84; liquidaciones (vac. finiquito) 15.524,67; pago mensual (goces) 99.322,01.
- Ajuste: columna amarilla editable, cero por defecto (antes el papel traía 14.770,63 y 2.518,69 digitados sin soporte).
- Resultado: D13 21,39 · D14 93,37 · Vacaciones 24.813,65 (19%) · Total 24.928,41. Neto del cruce = pasivo DO-4 v3 al centavo (tolerancia de mensualizados).

**DO-5 — cruce mensual libros vs auditoría y cierre con DO-4C:**
- D13 (dic) cierra en 0.
- D14 (ago–dic) por conciliar −60,01 = finiquitos en libros (509,21) vs auditoría (569,22).
- Vacaciones por conciliar 1.416,97 = débitos del año en libros (116.263,65) vs goces y finiquitos del rol (114.846,68).

**Libros:** provisionalmente tomados del papel de trabajo (hoja «Libros», celdas azules). **Pendiente:** automatizar con los mayores de nómina (RQ-004) y confirmar con ellos las dos partidas por conciliar.

## 8-septies. DO-6 Cruce Global y DO-7 Cruce Mensual del Gasto (v1.12)

**Formato:** pestañas DO6 Cruce Gsto Benefi. y DO7 Cruce Mens Gasto Beneficios del papel de referencia. **Archivo:** `DO-6_DO-7_Cruce_Gasto_Beneficios.xlsx` (generador `mk_do67.py`). Hojas: DO6 Cruce Global Gasto · DO7 Cruce Mensual Gasto · Ficha · Libros mensuales · Insumo Auditoría · Controles. 14 controles OK, 361 fórmulas, 0 errores.

**DO-6 (libros por cuenta y centro de costo vs devengado de auditoría):**
| Beneficio | Libros | Auditoría | Diferencia |
|---|---|---|---|
| Décimo tercero | 183.639,53 | 183.134,14 | 505,39 |
| Décimo cuarto | 63.953,92 | 63.070,08 | 883,84 |
| Aporte patronal + CCC | 293.956,01 | 293.760,06 | 195,95 |
| Fondos de reserva | 193.660,36 | 174.834,73 | 18.825,63 |
| Vacaciones | 125.552,86 | 100.717,85 | 24.835,01 |
| Aporte pasantes | 3.501,81 | 3.501,81 | 0,00 |
| **Total** | 864.264,49 | 819.018,67 | **45.245,82** |

- **Fondos de reserva** se explica al centavo: FR de representantes legales excluidos 18.294,20 + pagado en exceso del devengado 486,40 + libros vs pagado 45,03 (Rivera Jaramillo, V04).
- **DO-7:** cada beneficio cuadra con la DO-6. Aporte pasantes cuadra mes a mes (el papel anterior tenía la columna de auditoría desordenada por mes). D14: mayor diferencia en enero (614,44). Vacaciones: exceso sistemático por tasa de provisión.
- **Coherencia gasto vs pasivo:** vacaciones, gasto en libros 125.552,86 vs provisión acreditada al pasivo 126.948,47 (−1.395,61). Confirmar con el mayor RQ-004.
- Libros provisionales del papel; se automatizan con los mayores RQ-004.

## 8-octies. DO-8 Base imponible IESS vs libros (v1.13)

**Formato:** pestaña DO8 Calculo Base imponible Apor del papel de referencia. **Archivo:** `DO-8_Base_Imponible_IESS_vs_Libros.xlsx` (generador `mk_do8.py`). Hojas: DO8 Base Imponible IESS · Ficha · Insumos mensuales · Controles. 11 controles OK, 260 fórmulas, 0 errores.

**Revisión del papel anterior:**
- Su base «según planilla» (2.423.874,50) era la base IESS total menos la diferencia de pasantes IESS vs libros: mezclaba dos poblaciones. Se separa en **A. Empleados** y **B. Pasantes**.
- La columna IESS de pasantes estaba **desordenada por mes**, igual que en la DO-7; se corrige con el Consolidado.
- Encabezado con `#REF!` y doble referencia «DO-8»; se vincula a la Ficha.

**Resultados:**
- **Empleados:** planilla 2.417.228,14 vs libros 2.416.978,68 (sueldos, horas extras, bonos, comisiones, premios y vacaciones tomadas del rol) → **249,46 (0,01%)**, igual a la diferencia del papel anterior.
- **Pasantes:** base IESS sobre SBU 19.896,64 vs estipendio en libros 6.646,36 → 13.250,28. Confirmar base legal de la aportación de pasantes.
- **Rol vs IESS:** la base gravada del rol excede la reportada al IESS en **4.910,86** (22 trabajadores, DO-3.1): posible subdeclaración de aportes. Se muestra por mes.
- Libros provisionales del papel; se automatizan con los mayores RQ-004.

## 8-nonies. Verificación de trazabilidad y RQ-004 (v1.14)

**Regla (decisión del socio):** toda cédula debe provenir de un botón de requerimientos o de una prueba anterior, y tener su tarjeta en el panel.

**Matriz de trazabilidad:**
| Cédula | Origen | Estado |
|---|---|---|
| DO-1 | RQ-001 | OK |
| DO-2 | RQ-002 | OK |
| DO-3 | RQ-003 | OK |
| DO-3.1 | RQ-006 + RQ-003 | Tarjeta corregida (se agregó RQ-003) |
| DO-4 | RQ-003 (+ Exclusiones), DO-3.1, DO-2 | Tarjeta: RQ-005 y RQ-007 marcados «· validación» |
| DO-4C | RQ-002 (saldos ESF e iniciales), DO-4, DO-3.1 | Fuente corregida a RQ-002 |
| DO-5 | Provisiones mensuales: papel del equipo | **Provisional** → RQ-004 Mayor de pasivos |
| DO-6 | 150 cuentas RQ-002; 23 cuentas de vacaciones del papel | Parcial; cuentas del papel en naranja |
| DO-7 | Gasto mensual: papel del equipo | **Provisional** → RQ-004 Mayor de gastos |
| DO-8 | Sueldos, HE y bonos RQ-002; comisiones, premios y estipendio del papel; mensual del papel | Parcial; cuentas del papel en naranja |

**Cambios aplicados:**
- Cédulas: las cuentas se leen del Anexo RQ-002 cuando existen (azul); las demás en naranja. Banda amarilla de «Libros provisionales» en DO-4C (fuente), DO-5, DO-6, DO-7 y DO-8.
- Panel: RQ-004 con dos compartimentos obligatorios, **Mayor de pasivos (5BS.212…)** y **Mayor de gastos (5PYG / 5D…)**, y texto de ayuda.
- **Modelo `RQ-004_Mayores_Nomina.xlsx`:** Instrucciones · Catálogo (195 cuentas: 10 de pasivo y 185 de gasto, con concepto, cédulas que la usan y saldo RQ-002; 35 marcadas «No está en RQ-002») · Mayor pasivos (asiento por fila, tipo de movimiento clasificado por el auditor, control de saldo final vs RQ-002) · Mayor gastos (saldo mensual por cuenta con control anual vs RQ-002 y resumen por concepto que alimenta DO-5 a DO-8).

**Pendiente:** al recibir el RQ-004 del cliente, reemplazar los libros provisionales de DO-5, DO-6, DO-7 y DO-8 y confirmar las partidas por conciliar.

## 8-decies. DO-9 IESS por pagar: libros vs comprobantes de pago (v1.15)

**Insumo nuevo — RQ-005 leído desde PDF:** 85 comprobantes del IESS (plantilla única, texto extraíble). Campos: número, concepto (normales / ajustes), período, emisión, vigencia, valor, intereses, seguro de salud tiempo parcial, honorarios, gastos administrativos, subtotal, notas de crédito y total. Préstamos clasificados por concepto: «PAGO CREDITOS HIPOTECARIOS» = hipotecario; «PAG.DIV.PRESTAMOS» = quirografario. Lector: `parse_comp.py`.

**Archivo:** `DO-9_IESS_por_Pagar_Comprobantes.xlsx` (generador `mk_do9.py`). Hojas: DO9 IESS por Pagar · Comprobantes RQ-005 (detalle con control aritmético y V10) · Insumos · Ficha · Controles. 11 controles OK, 510 fórmulas, 0 errores.

**Resultados:**
| Concepto | Libros | Comprobantes | Diferencia | Explicación |
|---|---|---|---|---|
| Aportes (+ ext. salud 50,12) | 528.136,31 | 525.890,37 | 2.245,94 | Notas de crédito IESS 1.538,60; resto por conciliar con RQ-004 |
| Fondos de reserva | 16.952,78 | 16.491,03 | 461,75 | Enero 238,18 nota de crédito; febrero 223,57 por conciliar |
| Préstamos | 137.698,55 | 137.698,55 | 0,00 | Quirografarios 85.967,02 · hipotecarios 51.731,53 |

- **Tres vías:** aportes comprobantes bruto 527.582,79 vs Consolidado 525.690,48 → 1.892,31; fondos de reserva 16.729,21 vs 16.683,45 → 45,76.
- **Seguro de salud tiempo parcial 349,18** = «Otros gastos de nómina» AD 4,41% JP de la DO-2 (cierra con evidencia externa).
- **Saldos de diciembre** (aportes 46.636,01; FR 1.433,34; quirografarios 6.704,37; hipotecarios 4.411,90) = Anexo RQ-002. Sueldos por pagar: rol «normal» 163.774,65 + pasantes 942,00 = 164.716,65 pagado en el mes; saldo 2.165,73 (un trabajador) por sustentar.
- **V10:** 0 comprobantes emitidos fuera de plazo; margen mínimo 6 días.
- **Correcciones al papel anterior:** préstamos con columnas hipotecario/quirografario cruzadas de enero a agosto (21.250,12 mal clasificados); aportes 525.937,84 incluía el «valor» y no el total de dos comprobantes de extensión de salud.

**Panel:** RQ-005 con 5.º compartimento opcional «Extensión de salud cónyuges» y lectura automática de PDF; tarjeta renombrada «IESS por Pagar: Libros vs Comprobantes de Pago» con RQ-002, RQ-004, RQ-005 y RQ-006.

## 8-undecies. DO-10 Roles de pago vs libros: gastos y provisiones (v1.16)

**Tarjeta renombrada:** «Conciliación Libros vs Roles de Pago» → **«Roles de Pago vs Libros: Gastos y Provisiones»**, alineada al papel («Prov. y Gstos vs Roles») y al estilo de la DO-9. RQ: 002, 004, 005 y 006.

**Archivo:** `DO-10_Roles_vs_Libros.xlsx` (generador `mk_do10.py`). Hojas: DO10 Roles vs Libros · Rol RQ-006 · Ficha · Controles. 12 controles OK, 314 fórmulas, 0 errores.

**Resultados:**
- Rol por mes y 16 conceptos (RQ-006, pestañas «normal» y «pasantes»), igual a la DO-3.1.
- Libros (RQ-002): horas extras 170.746,03, bonos 538.111,47 → cuadran; comisiones 15.170,20, premios 4.000,00 y pasantes 6.646,36 → cuadran (libros provisionales del papel).
- **Sueldos: rol excede a libros en 3.603,33**, abierto por mes (enero 1.262,50 · diciembre 761,10 · julio 639,59 · junio −486,34); apertura por trabajador pendiente del RQ-004.
- **Fondos de reserva:** rol 176.931,88 + depósitos IESS 16.491,03 = 193.422,91 vs gasto 193.660,36 → −237,45 = 45,03 (Rivera Jaramillo, V04) + 192,42 (FR Consolidado vs comprobantes, DO-9).
- **Pagos que debitan el pasivo** (goces 99.322,01; vacaciones de finiquito 15.524,67; D13 mens. + liq. 20.258,93; D14 mens. + liq. 6.675,80): lado de libros pendiente del Mayor de pasivos RQ-004. El papel anterior comparaba vacaciones tomadas del rol contra sí mismo.
- **501,82 de décimos en el rol fuera del IESS = décimos jubilares** (D13 27,60 y D14 474,22) de la jubilada patronal Beltrán Cañizares; no es un error de cruce.

## 8-duodecies. Prueba 1 — Procedimiento de Auditoría de Nómina (DO-0) (v1.17)

**Decisión del socio:** antes de la DO-12, recopilar todos los procedimientos ejecutados con sus indicaciones, y presentarlos en HTML que se despliega al presionar la tarjeta.

**Panel:** la tarjeta «Procedimiento de Auditoría Nómina» queda **DISPONIBLE** y abre un modal con cuatro pestañas:
- **Programa:** 12 pruebas (DO-1 a DO-12) como secciones desplegables; cada una con objetivo, aserciones, insumos (RQ / PT), criterio y normativa, resultado, hallazgo vinculado, estado y pasos numerados (52 pasos). Botón «Desplegar todo».
- **Requerimientos:** RQ-001 a RQ-007, estado para cliente piloto y cédulas que los consumen.
- **Hallazgos:** 14 hallazgos con importe, naturaleza y acción requerida (insumo directo de la DO-12).
- **Normativa:** base legal y códigos de las REGLAS.
- Botones **Imprimir** (versión para papel) y **Excel** (descarga `DO-0_Programa_Auditoria_Nomina.xlsx`, con columnas de «Hecho por» y «Revisado por»).

**Archivo:** `DO-0_Programa_Auditoria_Nomina.xlsx` (generador `mk_pa.py`). Hojas: Programa · Requerimientos · Hallazgos · Normativa · Ficha. Tarjeta: insumo «DO-0 · Todas las pruebas».

## 8-terdecies. DO-12 Hoja de hallazgos y ajustes (v1.18)

**Formato:** pestaña DO12 del papel (No. · Observación · Ref. PT · Recomendación), ampliado según su propio procedimiento: problema (condición), criterio, causa y efecto con el valor en USD. **Archivo:** `DO-12_Hallazgos_y_Ajustes.xlsx` (generador `mk_do12.py`). Hojas: DO12 Hoja de Hallazgos · Ajustes propuestos · Resumen NIA 450 · Carta control interno · Ficha (incluye materialidad) · Controles. 5 controles OK, 0 errores.

**Hallazgos (14; 68.897,83 cuantificados):** ajuste contable 24.813,65 · reclasificación 18.294,20 · ajustes menores 928,87 · por conciliar / sustento 6.699,97 · cumplimiento IESS (código de relación, base rol vs IESS 4.910,86, pasantes 13.250,28 por confirmar) · control interno (148 acumulaciones de D13 sin solicitud) · calidad del papel (interno).

**Ajustes propuestos:**
- **AJ-1:** Dr 5BS.21204.003 Vacaciones por pagar 24.813,65 / Cr gasto de vacaciones (prorrata en 23 centros de costo). Saldo auditado de vacaciones 105.906,74 (= reproceso DO-4). Aumenta la utilidad en 24.813,65.
- **RJ-1:** reclasificación de fondos de reserva a remuneración de administradores: 5DGEN.61101 11.719,34 y 5DIR.61101 6.574,86 (total 18.294,20). Sin efecto en resultado; verificar centro de costo y efecto tributario.

**NIA 450:** incorrecciones de hecho no ajustadas (D13 21,39; D14 93,37; FR 45,03) y de juicio (sueldos 3.603,33; aportes omitidos) evaluadas contra la materialidad que se ingresa en la Ficha. **Carta de control interno:** 6 observaciones (H-1, H-2, H-3, H-6, H-8, H-12).

**Panel:** tarjeta DO-12 DISPONIBLE; abre el modal en la pestaña «Hallazgos (DO-12)» (desplegables con condición, criterio, causa, efecto y recomendación) y «Ajustes propuestos» (asientos y efecto en saldos). El botón Excel descarga la DO-12 desde esas pestañas y la DO-0 desde las demás. El programa DO-0 marca la DO-12 como terminada.

**v1.19 — Decisión del socio: sin materialidad.** Al probarse el 100% de la nómina no se aplica materialidad de muestreo ni proyección. La hoja «Resumen NIA 450» pasa a «Resumen de incorrecciones»: las diferencias son exactas; se proponen los ajustes sustentados (AJ-1, RJ-1) y se comunican todas las demás. Se retiró el bloque de materialidad de la Ficha. Programa DO-0 y tarjeta del panel actualizados.


## 8-quaterdecies. DO-4 V08 muestreo de solicitudes y DO-4V vacaciones no gozadas (v1.20)

**DO-4 V08 — Solicitudes de acumulación de décimos (RQ-007).** Origen: reproceso DO-4 (Detalle RQ-003, después de exclusiones). Población: 147 trabajadores que acumulan D13; 146 también D14. Muestra única para ambos certificados: n = REDONDEAR.MAS(N × %), 10% por defecto = 15; partidas clave = 5 mayores D13; resto por selección sistemática (intervalo = (N − clave)/(n − clave), arranque configurable). El auditor marca Sí/No (D14: N/A si no acumula). Conclusión: PENDIENTE / CONFORME / CON EXCEPCIONES → DO-12 H-8 y ampliar muestra. Archivo `RQ-007_Muestreo_Solicitudes_Decimos.xlsx` (generador `mk_rq007.py`). Es la única prueba con muestra; el resto cubre el 100%.

**DO-4V — Vacaciones no gozadas, liquidación hipotética al corte (RQ-008).**
1. Visita preliminar: sin kárdex → estado NO SOPORTADO y observación automática OBS-VAC (condición, criterio arts. 69/71/76 CT y NIC 19, efecto, recomendación).
2. Visita final, con kárdex, por trabajador activo: días devengados = 15·Y + Σ adicionales (k − 5, máx. 15, desde el 6.º año) + días del año en curso × fracción; saldo = devengados − gozados/pagados; pasivo = saldo × remuneración de corte / 30.
3. Ajuste total = Σ pasivo − libros al corte. Resultados acumulados = pasivo correcto al cierre anterior (remuneración de ese cierre) − libros a esa fecha (NIC 8). Gasto del año = [(a) − (c)] − [(b) − (d)].
4. Estados: NO SOPORTADO (0 con kárdex) · PARCIAL (algunos sin kárdex: no concluyente) · CALCULADO (asiento habilitado). Alertas: saldo negativo, más de tres períodos acumulados (art. 75 CT); tope de acumulación de 5 períodos anuales (decisión del socio, v1.20.1; parámetro editable en Ficha, 0 = sin tope): saldo = MIN(devengados − gozados, 5 × días del año en curso); estado «Tope aplicado».
Archivos `VAC_Calculadora_Vacaciones_No_Gozadas.xlsx` (generador `mk_vac.py`; `python3 mk_vac.py DEMO <salida>` genera una copia de prueba) y `RQ-008_Kardex_Vacaciones.xlsx`.

**Año auditado.** El encargo es 2026; las cédulas se construyeron con la plantilla 2025 (rol, IESS, anexo, comprobantes). Período terminado 31-dic-2026 con nota en cada libro; al recibir la información 2026 se regeneran con los mismos generadores.


## 8-quindecies. Verificación normativa aplicada (v1.21)

- **Pasantes (DO-8 → DO-12 H-5):** prueba de cumplimiento de la Ley de Pasantías art. 7 sobre la pestaña «pasantes» del rol: estipendio ≥ 1/3 SBU (157,00 vs 156,67 ✓), aporte 17,6% sobre el SBU íntegro a cargo de la empresa (82,72; sin aporte personal ✓) y duración ≤ 6 meses (✗ Trabajador C 9,1; Trabajador A 6,3). La diferencia de base IESS vs libros (13.250,28) es esperada.
- **DO-4V:** base del valor día seleccionable en Ficha (C18). Por defecto remuneración de corte / 30; alternativa art. 71: promedio de los últimos 12 meses / 30 (columna W). Fila 27: pasivo con la base alternativa (columna X).
- **Representantes legales:** art. 308 (mandatario) y código IESS 109 respaldan EX-01/EX-02 y RJ-1; la afiliación con código 06 se observa en H-2.
- **Pendientes de texto oficial:** arts. 76, 113 y 635 del Código del Trabajo y resolución IESS del código 109.


## 8-sexdecies. Mayores RQ-004 integrados (v1.22)

**Lectura (`leer_mayores_RQ004.py`).** Signo del mayor: débito +, crédito −. Pasivo de beneficios (5BS.21204): clasificación por el concepto de la explicación — PROVISION (DECIMO 13, DECIMO 14 S, VACACIONES), FINIQUITOS (LIQ.*, VAC.FINIQUIT), GOCES (VAC TOMADAS), PAGOS (TRANSF/PGO/PAGO) y AJUSTES (resto). IESS por pagar (5BS.21203): columna REF del cliente; los pagos se separan en pago al IESS (CANCELACION.IESS), notas de crédito por permisos médicos (CIERR.CXC IESS) y otros. Gasto: concepto por la descripción de la cuenta (las cuentas MQLA se suman a su concepto).

**Controles de integridad.** Saldo inicial (RQ-002) + movimientos = saldo ESF en cada cuenta de pasivo; gasto del mayor = anexo en las cuentas comunes; las cuentas que el anexo omite se presentan en la DO-2.

**Uso por cédula.** DO-5: provisiones mensuales y movimiento anual; DO-6/7: gasto mensual por concepto; DO-8: componentes mensuales y estipendio; DO-9: libros mensuales netos de reversiones, rollforward y pagos por período vs comprobantes; DO-10: débitos del pasivo y mensualizados; DO-2: cuentas fuera del anexo.

**Regla de pagos al IESS.** El pago del mes m corresponde a la planilla del mes m−1; el de enero cancela el saldo inicial y la planilla de diciembre es el saldo final.
