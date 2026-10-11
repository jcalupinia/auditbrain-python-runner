# Nómina · catálogo de pruebas, cédulas y generadores (estado v1.22)

Mapa operativo del módulo «Pasivos Acumulados y Gastos de Nómina». Las reglas legales están en
`nomina-REGLAS_Beneficios_Sociales_Ecuador.md` y el detalle de cada prueba en `nomina-FLUJOS_…md`.

## Requerimientos al cliente
| RQ | Documento | Obligatorio | Uso |
|---|---|---|---|
| RQ-001 | Cuestionario laboral IESS–MDT (lo ejecuta el auditor) | Sí | DO-1, DO-0 |
| RQ-002 | Anexo de pasivos y gastos de nómina (comparativo) | Sí | DO-2, saldos iniciales |
| RQ-003 | Consolidado IESS por región (un registro por trabajador y mes) | Sí | Fuente base: DO-3, DO-4, DO-8 |
| RQ-004 | Mayores de pasivos (beneficios, IESS) y de gastos | Sí | DO-2, DO-5, DO-6/7, DO-8, DO-9, DO-10 |
| RQ-005 | Comprobantes de pago IESS (aportes, FR, quirografarios, hipotecarios) | Sí | DO-9 |
| RQ-006 | Rol de pagos por trabajador y mes (incluye pasantes) | Sí | Fuente base: DO-3.1 |
| RQ-007 | Solicitudes escritas de acumulación de décimos | Opcional | DO-4 V08 (muestreo) |
| RQ-008 | Kárdex de vacaciones | Opcional | DO-4V (calculadora) |

## Pruebas y cédulas (orden de ejecución)
| Cédula | Prueba | Insumos | Generador |
|---|---|---|---|
| DO-0 | Programa de auditoría de nómina (procedimientos con referencia a cada cédula) | Todas | `mk_do0` / panel |
| DO-1 | Evaluación de control interno laboral | RQ-001 | panel (cuestionario) |
| DO-2 | Sumaria: anexo vs mayor, cuentas fuera del anexo | RQ-002, RQ-004 | pendiente de generador |
| DO-3 | Resumen de planillas IESS | RQ-003 | pendiente de generador |
| DO-3.1 | Resumen de roles de pago | RQ-006 | pendiente de generador |
| DO-4 | Reproceso de beneficios por pagar (D13, D14, VAC, FR) con exclusiones | RQ-003, RQ-006, DO-3.1 | pendiente de generador |
| DO-4 V08 | Muestreo de solicitudes de acumulación | DO-4, RQ-007 | `mk_rq007.py` |
| DO-4V | Vacaciones no gozadas, liquidación hipotética al corte | RQ-008, rol | `mk_vac.py` |
| DO-4C / DO-5 | Cruce global y mensual del pasivo (rollforward por clase) | DO-4, RQ-004 | `mk_do45.py` |
| DO-6 / DO-7 | Cruce global y mensual del gasto por concepto | DO-4, RQ-004 | `mk_do67.py` |
| DO-8 | Base imponible IESS vs libros; pasantes | DO-3, DO-3.1, RQ-004 | `mk_do8.py` |
| DO-9 | IESS por pagar: libros vs comprobantes (pago m ↔ planilla m−1) | RQ-004, RQ-005 | `mk_do9.py` |
| DO-10 | Roles de pago vs libros (gastos y débitos del pasivo) | DO-3.1, RQ-004 | `mk_do10.py` |
| DO-12 | Hallazgos y ajustes (consume todas; observaciones automáticas de RQ opcionales) | Todas | `mk_do12.py` |

Lector común de mayores: `mayores.py` / `leer_mayores_RQ004.py` (ver `../patrones/mayores-rq004.md`).
Extractor de comprobantes PDF del IESS: `parse_comprobantes_IESS.py` (pdftotext).

## Lecciones del piloto que el analista debe recordar
- El anexo del cliente puede omitir cuentas de gasto: listarlas en DO-2, nunca ignorarlas.
- Una diferencia de pasivo puede ser una reversión del mes (no un pago) o un ajuste manual: revisar el mayor.
- Representantes legales y mandatarios (art. 308 CT, código IESS 109) se excluyen de D13, D14 y FR por decisión
  documentada; si están afiliados con otro código, se observa.
- Pasantes: cumplimiento de la Ley de Pasantías (estipendio ≥ 1/3 SBU, aporte 17,6 % sobre SBU a cargo de la empresa,
  duración ≤ 6 meses); la diferencia de base IESS vs libros por pasantes es esperada.
- Diferencias de sueldos que están en la nómina regular exigen el reporte de nómina por centro de costo.
