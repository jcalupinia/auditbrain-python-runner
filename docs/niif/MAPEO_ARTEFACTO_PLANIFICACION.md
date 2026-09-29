# Mapeo: artefacto FIN-AP ↔ motor de planificación (planificacion_nia)

Referencia de correspondencia entre el **artefacto de referencia** de la prueba de
Planificación de Auditoría Externa (Análisis Financiero y Revisión Analítica Preliminar,
"AuditBrain_Analisis_LANSEY") y su implementación en este runner
(`backend/app/aud/niif/procesadores/planificacion_nia.py` + frontend `motorAnalitico`).

**Para qué sirve.** El artefacto y el prompt FIN-AP son la fuente de verdad de la
prueba. Este runner la implementa en Python con nomenclatura propia (español) y con más
documentos que el artefacto. Como los nombres difieren, un revisor externo puede creer
que "faltan" documentos cuando en realidad están bajo otro nombre. Esta tabla evita esa
confusión y sirve de guía al equipo y a la revisión de conformidad.

> La revisión de conformidad y el recálculo exacto viven en el repositorio
> `jcalupinia/audit-ia-artefactos`, carpeta `auditbrain-external-audit-work/`
> (agente `audit_planning_review_agent`, `engine/planning_conformance.py`,
> `engine/planning_review.py`, `engine/planning_runner_adapter.py`). Este documento es
> solo la referencia de nombres del lado del runner.

## Documentos (artefacto → runner)

El artefacto genera 11 pestañas HTML y 13 hojas de Excel. El runner las reproduce (y
amplía a 24 cédulas). Correspondencia:

| Documento del artefacto | Cédula / vista en el runner |
|---|---|
| Perfil del Encargo | `14_Perfil` |
| Situación Financiera | `08A_ESF_Detalle` + `09_Estados` |
| Estado de Resultados | `08B_ERI_Detalle` + `06_ERI_Anterior` |
| Analítico Preliminar | `08_Horizontal` (análisis horizontal y vertical) |
| Índices Financieros | `10_Indices` |
| Materialidad | `11_Materialidad` |
| Matriz de Riesgos | `12_Riesgos_CCI` + `13_Riesgos_Balance` |
| Cuentas a Revisar | `18_Cuentas_Revisar` |
| Programa | `19_Programa` |
| Tablero Ejecutivo | `01_Resumen` + narrativa |
| Notas a los EEFF | `15_Notas` + `15D_Notas_Detalle` + `15C_Composicion` |
| Control & Anomalías | `16_Control` + `17_Anomalias` |
| Lectura de Variaciones | `22_Origenes` (orígenes y aplicaciones de efectivo) |
| *(sólo en el runner)* | `20_Narrativa`, `21_Estrategia`, `23_Audit_trail`, `24_Problemas` |

## Motor de cálculo (capacidad del artefacto → dónde está en el runner)

| Capacidad (artefacto, JS) | Implementación en el runner |
|---|---|
| `computeAggregates` / `sectionTotal` | `sec7` (totales por sección con signo) en `ejecutar()` |
| `computeIndicadores` | `_indices(e, dias)` |
| `buildEriLines` | estados resumidos `est9` (Ventas netas, Utilidad bruta/operativa/neta) |
| `matGlobal` / `matBaseAmounts` | bloque de materialidad (NIA 320) en `ejecutar()` |
| DuPont (R5) | `_indices`: `dupontRoi`, `dupont` (usan utilidad operativa) |
| `niaIndicios` (NIA 570) | reglas de empresa en marcha en `_problemas` / matriz de riesgos |
| `posiblesRiesgos` | `13_Riesgos_Balance` / matriz de riesgos del balance |
| `detectAnomalies` | bloque de anomalías (`Signo`, `Nueva`, `Baja`, `Variación`, `Duplicado`) |
| `cuadreEstados` | "Diferencia de cuadre" en `sec7` y `est9` |
| `qaChecklist` | `_problemas` (asuntos para la planificación) |
| `auditTrail` (NIA 230) | `23_Audit_trail` |

## Índices: nombres equivalentes y unidades

| Artefacto (fracción) | Runner (`ind`) | Unidad en el runner |
|---|---|---|
| razonCorriente | razonCorriente | razón (x) |
| pruebaAcida | pruebaAcida | razón (x) |
| capitalTrabajo | capitalTrabajo | monto |
| diasCartera / diasInventario / diasProveedores | iguales | días (÷365, R4) |
| cicloEfectivo | ciclo | días |
| eficienciaActivos | rotacionActivo | razón (x) |
| endTotal / endLP | endTotal / endLP | **porcentaje** (×100) |
| endFinanciero / endPatrimonial | iguales | razón (x) |
| apalancamiento | multiplicador | razón (x) |
| margenBruto / margenOperativo / margenNeto | iguales | **porcentaje** (×100) |
| roi / roe | roi / roe | **porcentaje** (×100) |
| — | dupontRoi / dupont | **porcentaje** (×100) |

## Diferencias conocidas frente al artefacto

- **Días de inventario — semáforo (REV-UMBRAL-01).** El artefacto marca rojo por encima
  de **150 días**; el runner, por encima de **120 días** (unificado con el umbral de
  detección de riesgo de inventario). No afecta el cálculo del indicador, solo su
  calificación de color. Conviene documentar cuál umbral gobierna.
- **Alcance mayor.** El runner añade cédulas no presentes en el artefacto
  (`20_Narrativa`, `21_Estrategia`, `23_Audit_trail`, `24_Problemas`) y anexos NIA 510
  (saldos de apertura).

## Verificación reproducible

Recálculo exacto de la salida real del runner (desde `audit-ia-artefactos`):

```python
from backend.app.aud.niif.procesadores import planificacion_nia as m
from engine.planning_runner_adapter import review_runner_result   # audit-ia-artefactos
r = m.ejecutar(m.EJEMPLO["datasets"], m.EJEMPLO["parametros"], m.EJEMPLO["corte"])
rep = review_runner_result(r)   # índices desde est9 + agregados + puerta de calidad
```

Contra el ejemplo del runner: índices 40/40 y agregados 14/14 sin diferencias; veredicto
"APTO PARA REVISIÓN DEL SOCIO" (la aprobación del socio es humana por diseño).
