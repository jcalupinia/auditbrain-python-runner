---
nombre: reglas-beneficios-sociales-ecuador
modulo: AUD › Pruebas de Auditoría › Pasivos Acumulados
version: 1.4
fecha: 2026-10-09
fuente: Manual Consolidado de Capacitación — Beneficios Sociales del Trabajador, Ecuador 2026 (AuditSmart Pro)
aplica_a: DO-4 Reproceso de Beneficios Sociales · DO-4 V08 Muestreo · DO-4V Vacaciones no gozadas · DO-4 Cruce Global · DO-5 · DO-6 · DO-7 · DO-8 · DO-9 · DO-10 · DO-12
relacionado: FLUJOS_Obligaciones_Acumuladas_y_Gastos_Nomina.md
---

# Reglas — Beneficios sociales del trabajador (Ecuador)

Reglas normativas que gobiernan el cálculo y la auditoría de décimo tercero, décimo cuarto, fondos de reserva y vacaciones. Cada regla tiene un identificador estable para que las cédulas, el motor de AuditBrain y el Command Center la citen. Toda fórmula de las herramientas debe trazarse a una regla de este archivo; si una fórmula no tiene regla, es un supuesto y debe declararse como tal.

## 1. Parámetros por ejercicio

| ID | Parámetro | 2025 | 2026 | Uso |
|---|---|---:|---:|---|
| P-01 | Salario Básico Unificado (SBU) | USD 470,00 | USD 482,00 | Décimo cuarto |
| P-02 | Porcentaje de fondos de reserva | 8,33% | 8,33% | Fondos de reserva |
| P-03 | Divisor décimo tercero | 12 | 12 | Décimo tercero |
| P-04 | Divisor vacaciones | 24 | 24 | Vacaciones |
| P-05 | Base diaria décimo cuarto | SBU ÷ 360 | SBU ÷ 360 | Décimo cuarto proporcional |

Regla de uso: el parámetro se toma del **ejercicio auditado**, no del año en que se ejecuta la prueba. El encargo actual es 2026 (SBU USD 482); las cédulas de plantilla con datos 2025 usan SBU USD 470.

## 2. Reglas generales

| ID | Regla |
|---|---|
| RG-01 | Los beneficios aplican a trabajadores con relación bajo el Código del Trabajo (incluida la jornada parcial). Pasantes, internos y becarios no generan beneficios sociales. |
| RG-02 | La relación de trabajo se determina por el contrato y la planilla, no por el esquema de aportación. Un trabajador con relación Código del Trabajo reportado con esquema de pasante conserva sus beneficios y genera hallazgo en aportes. |
| RG-03 | Por ley, décimo tercero y décimo cuarto se pagan **mensualmente**. La acumulación solo procede con **solicitud escrita** del trabajador. |
| RG-04 | Si un décimo ya se pagó mensualmente, no se provisiona ni se vuelve a pagar en diciembre, agosto, marzo o en el finiquito. |
| RG-05 | Vacaciones no se mensualizan: se provisionan para todo trabajador con derecho. |
| RG-06 | El cálculo se hace sobre el 100% de la población, por trabajador y por mes. Única excepción: la prueba de atributos de solicitudes de acumulación de décimos (DO-4 V08, NIA 530). |

## 3. Décimo tercero (D13)

| ID | Elemento | Regla |
|---|---|---|
| D13-01 | Devengo mensual | Base remunerativa computable del mes ÷ 12 |
| D13-02 | Período | 1 de diciembre del año anterior al 30 de noviembre |
| D13-03 | Incluye | Sueldo, horas ordinarias, suplementarias y extraordinarias, comisiones y accesorios normales (Art. 95 del Código del Trabajo) |
| D13-04 | Excluye | Décimos, utilidades legales, fondo de reserva, reembolsos e indemnizaciones |
| D13-05 | Pago | Regla: mensual. Acumulado hasta el 24 de diciembre solo con solicitud escrita del trabajador (art. 111) |
| D13-08 | Solicitud de acumulación | Se presenta por escrito en los primeros 15 días de enero; quien ingresa en el año, al firmar el contrato o en sus primeros 15 días. **No se renueva cada año**: en la muestra se aceptan solicitudes de años anteriores vigentes |
| D13-06 | Cese | Parte proporcional menos los valores ya mensualizados |
| D13-07 | Pasivo al 31-dic | Devengo de diciembre de los trabajadores que acumulan |

Ejemplo: sueldo 800 + horas extras 120 + comisión 80 = base 1.000; D13 del mes = 83,33. Si la empresa usó solo el sueldo, omitió 16,66.

## 4. Décimo cuarto (D14)

| ID | Elemento | Regla |
|---|---|---|
| D14-01 | Valor anual | Un SBU del ejercicio (P-01), proporcional al tiempo trabajado |
| D14-02 | Mensual completo | SBU ÷ 12 (2025: 39,1667; 2026: 40,1667) |
| D14-03 | Proporcional | SBU ÷ 360 × días computables (equivale a SBU ÷ 12 × días ÷ 30) |
| D14-04 | Independencia del sueldo | El sueldo individual no interviene: dos trabajadores con sueldos distintos y período completo generan el mismo D14 |
| D14-05 | Costa y Galápagos | Período 1-mar a fin de febrero; pago hasta el 15-mar; pasivo al 31-dic = marzo a diciembre |
| D14-06 | Sierra y Amazonía | Período 1-ago a 31-jul; pago hasta el 15-ago; pasivo al 31-dic = agosto a diciembre |
| D14-07 | Región | Se determina por el lugar de trabajo, no por el domicilio del trabajador |
| D14-10 | Cálculo por bloques | El Consolidado IESS (RQ-003) se carga por región (Sierra/Amazonía y Costa/Galápagos). Cada región se calcula en su propio bloque y se consolida en un resumen; el pasivo del D14 se determina con el período de cada región |
| RL-01 | Fuente por trabajador | El rol de pagos «normal» (DO-3.1) es la fuente de mensualización, fecha de ingreso, salida, goces, finiquitos y provisiones del cliente; reemplaza cualquier dato inferido (PR-05) |
| RL-02 | Mensualización | Se determina por registro trabajador-mes: si el rol pagó D13 o D14 mensualizado ese mes, ese registro no se provisiona |
| RL-03 | Pasantías | Solo generan beneficios los registros IESS presentes en el rol «normal»; los meses de pasantía no aplican aunque el IESS los reporte con código 06 |
| RL-04 | Pasivo al 31-dic | Solo trabajadores activos al 31-dic; los liquidados no generan pasivo porque sus décimos se pagaron en la liquidación |
| RL-05 | Vacaciones | Pasivo = saldo inicial + provisión del año − vacaciones gozadas − vacaciones de finiquito |
| RL-06 | Cuadre de gasto | Pagado mensual en rol + provisión del cliente = gasto DO-2, por concepto (D13, D14, FR) |
| D14-08 | Cese | Proporcional del período menos los valores mensualizados |
| D14-09 | Jornada parcial | Proporcional a la jornada; requiere horas contratadas. Mientras no se tengan, se calcula por días y se declara como supuesto |

**Corrección al Manual (D14-06).** El Manual indica para Sierra y Amazonía el período 1-sep a 31-ago con pago hasta el 15-ago, lo que es inconsistente porque el pago caería antes del cierre. Se adopta el período 1-ago a 31-jul. Pendiente corregir el Manual.

## 5. Fondos de reserva (FR)

| ID | Elemento | Regla |
|---|---|---|
| FR-01 | Elegibilidad | Después del primer año con el mismo empleador (art. 196); operativamente desde el mes 13 |
| FR-02 | Base | Materia gravada o remuneración de aportación al IESS |
| FR-03 | Porcentaje | 8,33% mensual (P-02) |
| FR-04 | Pago directo | Regla general: pago mensual en el rol (Ley para el Pago Mensual del Fondo de Reserva, RO 644, 29-jul-2009); se omite solo si el trabajador pidió la acumulación en el IESS |
| FR-05 | Acumulación IESS | Se deposita mensualmente con los aportes |
| FR-06 | Control | No calcular antes del mes 13; verificar fecha de ingreso y opción de pago |
| FR-07 | Total a verificar | FR pagado en rol + FR depositado en el IESS = 8,33% de la base de los trabajadores con derecho |
| FR-08 | Mes de aniversario | En el mes en que se cumple el año, el fondo se calcula proporcional a los días posteriores al aniversario: base × 8,33% × (fin de mes − aniversario + 1) / días del mes |
| FR-09 | Fuente de fecha | Fecha de ingreso vigente del rol de pagos (DO-3.1); si el trabajador fue pasante, cuenta desde su ingreso en relación laboral |

## 6. Vacaciones (VAC)

| ID | Elemento | Regla |
|---|---|---|
| VAC-01 | Derecho | 15 días ininterrumpidos por año, incluidos los no laborables |
| VAC-02 | Valor anual | Total de remuneración computable del año ÷ 24 |
| VAC-03 | Devengo de días | 1,25 días por mes completo |
| VAC-04 | Base | Sueldo, horas y retribuciones accesorias normales |
| VAC-05 | Cese | Se paga el saldo proporcional no gozado |
| VAC-06 | Control | Separar el kárdex de días del cálculo monetario: la fórmula 1/24 no prueba que el descanso se haya gozado |
| VAC-07 | Pasivo al 31-dic | Saldo inicial + provisión del año − goces − liquidaciones y finiquitos |
| VAC-08 | Días adicionales (art. 69) | +1 día por cada año que exceda de cinco con el mismo empleador (desde el 6.º año), máximo 15 adicionales; el empleador elige concederlos o pagarlos |
| VAC-09 | Valor (art. 71) | 1/24 de lo percibido en el año completo, incluidas horas suplementarias y extraordinarias, sin décimos |
| VAC-10 | Acumulación (art. 75) | Hasta tres años consecutivos para gozarlas en el cuarto (60 días). La calculadora DO-4V aplica un **tope de 5 años** por criterio del socio (parámetro editable; más conservador que el art. 75) y alerta desde 3 períodos |
| VAC-11 | Liquidación hipotética (art. 76) | Pasivo exigible al corte = (días devengados desde el ingreso − gozados o pagados según kárdex) × valor día. Valor día por defecto: remuneración de corte / 30 (decisión del socio); alternativa art. 71: promedio de los últimos 12 meses / 30. La cédula presenta ambas |
| VAC-12 | Años anteriores (NIC 8) | Ajuste a resultados acumulados = pasivo correcto al cierre anterior − libros a esa fecha; el resto, gasto del año auditado |
| VAC-13 | Sin kárdex | Visita preliminar: observación OBS-VAC automática; el pasivo queda NO SOPORTADO hasta la visita final |

## 6-bis. Pasantías (PAS) — v1.4

Fuente: Ley de Pasantías en el Sector Empresarial, arts. 4, 5 y 7 (reforma RO 234-S, 20-ene-2023).

| ID | Elemento | Regla |
|---|---|---|
| PAS-01 | Naturaleza | Relación civil, no laboral; no aplican beneficios del Código del Trabajo (RG-01, RL-03) |
| PAS-02 | Estipendio | No menor a 1/3 del SBU (2025: 156,67; 2026: 160,67) por mes completo; proporcional en meses parciales |
| PAS-03 | Afiliación | Obligatoria; la empresa aporta **la totalidad** sobre el SBU vigente (17,6%: 82,72 en 2025), sin descuento al pasante. La diferencia entre base IESS (SBU) y estipendio en libros es **esperada**, no incumplimiento |
| PAS-04 | Duración | Máximo 6 meses sin generar relación de dependencia; al exceder, evaluar contingencia laboral (remuneración mínima, décimos, vacaciones y aportes como trabajador) |
| PAS-05 | Riesgo normativo | La sentencia de la Corte Constitucional 16-16-IN/22 declaró inconstitucional la reducción del estipendio a 1/3 del SBU con efectos diferidos; el plazo a la Asamblea venció en ene-2024 sin nueva ley. Requiere criterio legal antes de concluir sobre el estipendio mínimo |

## 7. Matriz de validaciones de auditoría

| ID | Prueba | Resultado esperado | Insumo |
|---|---|---|---|
| V01 | Duplicado por cédula y período | Rechazar o explicar | RQ-003 |
| V02 | Sueldo ≤ 0 con días > 0 | Error | RQ-003 |
| V03 | Días fuera de 0–30 | Error | RQ-003 |
| V04 | Fondo de reserva antes del mes 13 | Pago indebido o fecha de ingreso errada | RQ-007 + RQ-005 / roles |
| V05 | Fondo de reserva posterior al mes 13 no pagado ni depositado | Diferencia | RQ-007 + RQ-005 / roles |
| V06 | Décimo cuarto calculado con sueldo | Error de base | Provisión del cliente (DO-10) |
| V07 | Décimo tercero sin variables normales | Base incompleta | DO-8 |
| V08 | Acumulación sin solicitud escrita (muestra 10%, D13 y D14) | Incumplimiento documental | RQ-007 |
| V09 | Vacaciones con saldo negativo o más de 3 períodos | Error de integridad / alerta | Kárdex (RQ-008) |
| V12 | Pasantía mayor a 6 meses o estipendio < 1/3 SBU | Contingencia laboral | Rol pestaña «pasantes» (RQ-006) |
| V10 | Pago fuera de fecha | Incumplimiento de plazo | RQ-005 / roles |

## 8. Procedimiento y clasificación de hallazgos

| ID | Regla |
|---|---|
| PR-01 | El asistente prepara la población, las bases, los recálculos y los cruces. |
| PR-02 | El senior revisa períodos, criterios de inclusión, supuestos y excepciones. |
| PR-03 | Todo hallazgo se clasifica como **error de cálculo**, **falta de documento** o **diferencia de oportunidad**. |
| PR-04 | La conclusión indica causa, efecto monetario y recomendación, y la firma el auditor. |
| PR-05 | Todo dato inferido (no respaldado en un documento del cliente) se marca como supuesto y se confirma antes de cerrar la cédula. |

## 9. Trazabilidad en las herramientas

| Regla | Herramienta | Ubicación |
|---|---|---|
| D13-01, RG-03, RG-04 | DO-4 Reproceso | Detalle RQ-003, columna P |
| D14-03, P-01 | DO-4 Reproceso | Detalle RQ-003, columna Q; Parámetros C9 |
| VAC-02, RG-05 | DO-4 Reproceso | Detalle RQ-003, columna R |
| FR-01 a FR-03 | DO-4 Reproceso | Detalle RQ-003, columnas S y T; Parámetros C10 |
| RG-01, RG-02 | DO-4 Reproceso | Parámetros B5:D7; Detalle RQ-003, columna L |
| RG-03 (lista de mensualizados) | DO-4 Reproceso | Parámetros B21:E30 — hoy con dos registros **inferidos**, pendientes de confirmar (PR-05) |
| D13-07, D14-06, VAC-07 | DO-4 Reproceso | Bloque "Provisiones al 31-dic-2025", filas 55–61 |
| D14-05, D14-06, D14-07, D14-10 | DO-4 Reproceso | Bloque 1 Sierra (filas 65–79), Bloque 2 Costa (filas 82–96), Resumen por región (filas 99–103); región por registro en Detalle RQ-003, columna W |
| D14-10 | Panel HTML | Tarjeta RQ-003 con sub-compartimentos Sierra / Amazonía y Costa / Galápagos (basta una región) |
| V01 a V10 | DO-4 Reproceso | Controles, filas 40–51 |
| D14-09 | Pendiente | Prorrateo por jornada parcial sin horas contratadas |

## EX — Exclusiones (v1.3)

- **EX-01** Relación de trabajo 109 (representante legal por nombramiento): no genera D13, D14, vacaciones ni FR; se excluye por parámetro.
- **EX-02** Persona afiliada con código 06 que el auditor determina sin derecho a uno o más beneficios: se excluye solo el beneficio marcado, con motivo documentado en el archivo de exclusiones del RQ-003.
- **EX-03** Lo excluido no forma parte del pasivo ni del gasto reprocesado; se presenta aparte como «excluido por el auditor».
- **EX-04** Beneficio pagado por el cliente a una persona excluida (p. ej. FR en rol) = gasto sin sustento: evaluar ajuste o reclasificación (V11).
- **EX-05** Representante legal con poder general = mandatario, no empleado (Código del Trabajo, art. 308). Se afilia con código 109 (sin relación de dependencia), aporte 17,6% a cargo de la empresa sobre lo percibido. Si figura con código 06, además de la exclusión se observa la afiliación ante el IESS.

## Verificación normativa (v1.4, 09-oct-2026)

Confirmado en fuentes web: arts. 69, 71 y 75 (vacaciones), 111 (D13), 196 y Ley de 2009 (FR), Ley de Pasantías art. 7 y sentencia 16-16-IN/22, art. 308 y código IESS 109, SBU 2026 = 482. **Pendiente del texto oficial** (Registro Oficial / Asamblea): art. 76 literal, art. 113 literal, art. 635 (prescripción) y la resolución del IESS que fija el código 109 para representantes legales.
