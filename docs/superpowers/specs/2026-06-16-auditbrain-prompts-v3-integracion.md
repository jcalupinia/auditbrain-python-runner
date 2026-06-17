# Integración AuditBrain Prompts Dashboard v3 — Revisión y mapa de implementación

**Fuente:** `auditbrain_prompts_dashboard_v3.json` / `.ts` (v3.0, es).
**Ubicación destino en el repo:** `frontend/src/fin/prompts/auditbrainDashboardPromptsV3.ts` (pendiente de copia mecánica; ver nota al final).
**Revisado con:** marco NIIF (NIC 1/2/16/36/37, NIC 12) + criterio CFO/auditoría.

## 1. Qué es v3
Sistema de **12 módulos** de análisis financiero para Directorio/Gerencia/Accionistas, con **reglas globales** que aplican a todos:

- **Anti-invención (dura):** nunca inventar datos; si falta → `[DATO NO DISPONIBLE — solicitar: X]`; clasificar cada dato como `[DATO PROPORCIONADO]/[DATO CALCULADO]/[INFERENCIA]`; inferencias con ⚠️; sin evidencia → `[EVIDENCIA INSUFICIENTE]`. **(Refuerza la REGLA SUPREMA del CLAUDE.md y [[regla-no-fusionar-cuentas]].)**
- **Flujo obligatorio (12 pasos):** diagnóstico → materialidad → comparación período anterior → tendencia → riesgos → KPIs → gráficos → análisis dashboard → análisis KPIs → hallazgos/riesgos/recomendaciones → semáforo → acciones priorizadas.
- **Materialidad:** Alta >10% · Media 5–10% · Baja <5% (solo profundizar materiales, salvo riesgo legal/tributario/intercompany/garantías/relacionadas).
- **Sin sesgo positivo:** no concluir favorable por crecer ventas/activos si utilidad/EBITDA/flujo/DSCR empeoran.
- **Salida estándar A/B/C/D:** A análisis dashboard · B análisis KPIs · C alertas · D recomendaciones. Todo KPI crítico termina con HALLAZGO/RIESGO/RECOMENDACIÓN/SEMÁFORO (🟢🟡🔴).

### Módulos
00 reglas maestras · 01 activos · 02 pasivos · 03 patrimonio · 04 inversiones · 05 rentabilidad por unidad de negocio · 06 mapa de riesgo de grupo · 07 gobierno corporativo/intercompany · 08 matriz de decisiones · 09 calidad del crecimiento · 10 control interno/riesgo SRI · 11 resumen ejecutivo · 12 presentación ejecutiva.

## 2. Estado vs. lo implementado en el dashboard FIN

| Módulo v3 | Estado actual | Brecha principal |
|---|---|---|
| 00 Reglas maestras | 🟡 Parcial | Falta el marcado explícito `[DATO NO DISPONIBLE]`/⚠️ y bloques C/D (alertas/recomendaciones) homogéneos en todas las secciones. |
| 01 Activos | ✅ Hecho (≈90%) | Falta: matriz de riesgo (activo material vs recuperabilidad), "activos improductivos/activos", alerta inventario +20% sin ventas, CAPEX. |
| 02 Pasivos | 🟡 Básico | Falta calidad de deuda (productiva/especulativa/supervivencia), DSCR/ICR/Deuda-EBITDA con umbrales, vencimientos, negocio en marcha, garantías cruzadas. **Requiere datos de servicio de deuda (no disponibles aún).** |
| 03 Patrimonio | 🟡 Básico | Falta calidad patrimonial (capital+reservas)/patrimonio, **utilidades retenidas Ecuador 2025** (umbrales SRI), crédito tributario, relacionadas/patrimonio, fortalecimiento. |
| 04 Inversiones | ⬜ Pendiente | Necesita data de proyectos (monto, financiamiento, flujo esperado/real, contratos, ocupación). |
| 05 Rentabilidad por unidad | ⬜ Pendiente | Necesita resultados por línea/centro de costo. |
| 06 Mapa de riesgo de grupo | ⬜ Pendiente | Necesita multi-empresa + intercompany + garantías. |
| 07 Gobierno/intercompany | ⬜ Pendiente | Necesita matriz de partes relacionadas. |
| 08 Matriz de decisiones | ⬜ Pendiente | Necesita actas/decisiones. |
| 09 Calidad del crecimiento | 🟡 Parcial (en ER) | Formalizar clasificación saludable/frágil/destructivo + precio vs volumen. |
| 10 Control interno/SRI | ⬜ Pendiente | Cuestionario/score de control + riesgos SRI. |
| 11 Resumen ejecutivo | 🟡 Parcial | Existe Resumen pero falta semáforo integral + plan de acción priorizado + negocio en marcha + conclusión para accionistas. |
| 12 Presentación ejecutiva | 🟡 Parcial | Existe export PPT; falta la estructura de 18 slides v3. |

## 3. Datos que el sistema aún NO captura (gaps de input)
Para cumplir v3 sin inventar, se requieren (por la regla anti-invención, hoy deben salir como `[DATO NO DISPONIBLE]`):
- **Servicio de deuda / debt schedule** (capital, interés, vencimiento, garantía) → DSCR, ICR, Deuda/EBITDA, vencimientos, negocio en marcha.
- **Segmentación por unidad de negocio** → módulo 05.
- **Multi-empresa del grupo + intercompany + garantías** → módulos 06/07.
- **Inversiones/proyectos** (factibilidad, VAN/TIR, flujo esperado vs real, ocupación) → módulo 04.
- **Decisiones/actas** → módulo 08.
- **Cuestionario de control interno** → módulo 10.

El parser de balance interno ya entrega: activos/pasivos/patrimonio por rubro (con materialidad y sin fusionar categorías) y el ER con EBITDA. Eso habilita 01, 03, parte de 02 y 09.

## 4. Roadmap propuesto (fases)
1. **Fase A — Reglas maestras transversales:** helper de semáforo (🟢🟡🔴), bloques A/B/C/D, marcado `[DATO NO DISPONIBLE]`/⚠️, y "sin sesgo positivo" en todas las lecturas. (Reutiliza lo del Activo.)
2. **Fase B — Pasivos v3 (módulo 02):** calidad de deuda, apalancamiento, DSCR/ICR/Deuda-EBITDA con umbrales (marcando faltantes), vencimientos, negocio en marcha. Gráficos dinámicos (donut, corriente vs no corriente, gastos fin. vs EBITDA, cronograma).
3. **Fase C — Patrimonio v3 (módulo 03):** calidad patrimonial, reserva legal 50% (ya parcial), **utilidades retenidas Ecuador 2025** + crédito tributario, relacionadas/patrimonio, waterfall patrimonial.
4. **Fase D — Calidad del crecimiento (09) y Resumen ejecutivo (11)** integrando hallazgos.
5. **Fase E — Módulos que requieren nuevos inputs (04,05,06,07,08,10):** primero diseñar la ingesta de esos datos; mientras tanto, mostrar `[DATO NO DISPONIBLE]` con la lista de lo que se debe solicitar.
6. **Fase F — Presentación ejecutiva v3 (12):** alinear el export PPT a los 18 slides.

## 5. Cómo se consume en el proyecto
- El `.ts` exporta `auditbrainDashboardPromptsV3` → fuente única de los textos-regla; el dashboard implementa cada módulo siguiendo su prompt **línea por línea** (ver [[regla-diagnostico-activo-cfo]], REGLA 0).
- Cada sección del dashboard (Activos ya lo hace) debe producir: KPIs dinámicos por materialidad + varios gráficos dinámicos + bloques A/B (+ C/D) + conclusión ejecutiva con semáforo.

## Nota operativa
Los archivos crudos `auditbrain_prompts_dashboard_v3.{ts,json}` quedan por copiarse a `frontend/src/fin/prompts/` (la copia por shell falló por indisponibilidad temporal del clasificador de comandos; se completa al restablecerse). Esta especificación es la guía de implementación derivada de su lectura completa.
