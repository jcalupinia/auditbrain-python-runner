---
nombre: reglas-beneficios-sociales-ecuador
modulo: AUD › Pruebas de Auditoría › Pasivos Acumulados
version: 1.2
fecha: 2026-10-06
fuente: Manual Consolidado de Capacitación — Beneficios Sociales del Trabajador, Ecuador 2026 (AuditSmart Pro)
aplica_a: DO-4 Reproceso de Beneficios Sociales · DO-4 Cruce Global · DO-5 · DO-6 · DO-7 · DO-9 · DO-10
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

Regla de uso: el parámetro se toma del **ejercicio auditado**, no del año en que se ejecuta la prueba. Una auditoría del ejercicio 2025 usa SBU USD 470.

## 2. Reglas generales

| ID | Regla |
|---|---|
| RG-01 | Los beneficios aplican a trabajadores con relación bajo el Código del Trabajo (incluida la jornada parcial). Pasantes, internos y becarios no generan beneficios sociales. |
| RG-02 | La relación de trabajo se determina por el contrato y la planilla, no por el esquema de aportación. Un trabajador con relación Código del Trabajo reportado con esquema de pasante conserva sus beneficios y genera hallazgo en aportes. |
| RG-03 | Por ley, décimo tercero y décimo cuarto se pagan **mensualmente**. La acumulación solo procede con **solicitud escrita** del trabajador. |
| RG-04 | Si un décimo ya se pagó mensualmente, no se provisiona ni se vuelve a pagar en diciembre, agosto, marzo o en el finiquito. |
| RG-05 | Vacaciones no se mensualizan: se provisionan para todo trabajador con derecho. |
| RG-06 | El cálculo se hace sobre el 100% de la población, por trabajador y por mes. No se usa muestreo. |

## 3. Décimo tercero (D13)

| ID | Elemento | Regla |
|---|---|---|
| D13-01 | Devengo mensual | Base remunerativa computable del mes ÷ 12 |
| D13-02 | Período | 1 de diciembre del año anterior al 30 de noviembre |
| D13-03 | Incluye | Sueldo, horas ordinarias, suplementarias y extraordinarias, comisiones y accesorios normales (Art. 95 del Código del Trabajo) |
| D13-04 | Excluye | Décimos, utilidades legales, fondo de reserva, reembolsos e indemnizaciones |
| D13-05 | Pago | Mensual; acumulado hasta el 24 de diciembre solo con solicitud escrita |
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
| FR-01 | Elegibilidad | Después de más de un año con el mismo empleador; operativamente desde el mes 13 |
| FR-02 | Base | Materia gravada o remuneración de aportación al IESS |
| FR-03 | Porcentaje | 8,33% mensual (P-02) |
| FR-04 | Pago directo | Se incluye en el rol cuando el trabajador no pidió acumulación en el IESS |
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
| V08 | Acumulación sin solicitud escrita | Incumplimiento documental | RQ-007 |
| V09 | Vacaciones con saldo negativo | Error de integridad | Kárdex (RQ-007) |
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
