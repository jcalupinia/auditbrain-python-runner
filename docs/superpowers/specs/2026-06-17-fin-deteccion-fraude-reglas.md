# FIN · Detección de Riesgo de Fraude/Errores — Prompts y reglas de trabajo

**Fecha:** 2026-06-17
**Ámbito:** módulo FIN · CFO Intelligence → sección "Detección de Riesgo de Fraude/Errores".
**Fuente de datos:** cuentas detalladas del **Balance General** (activo/pasivo/patrimonio) y del
**Estado de Resultados** (costos/gastos), revisadas **línea por línea**, comparando todos los períodos.

Estas son las **reglas de trabajo permanentes** (más allá del dashboard): definen qué revisa cada
agente y cómo se construye la matriz de auditoría. Regla transversal del proyecto: **nunca inventar**;
si falta el insumo, escribir `[DATO NO DISPONIBLE]` y declarar la limitación de alcance.

## Salida obligatoria — Matriz de auditoría
Por cada cuenta señalada, una fila con:

| Código contable | Descripción | Hallazgo del problema | Riesgo detectado | Acción para mitigarlo | Norma | Nivel |
|---|---|---|---|---|---|---|

Más: índices financieros del período, riesgos detectados agrupados, posibles problemas de auditoría
externa/interna, nivel de riesgo consolidado y conclusión.

---

## Agente 1 — Auditor forense / antifraude (NIA 240)
**Qué revisa, línea por línea:**
- **Cuentas nuevas** (saldo 0 en el primer período y >0 en el actual) sin sustento.
- **Cuentas eliminadas** (saldo que desaparece): ¿eficiencia, reclasificación u ocultamiento?
- **Volatilidad** (variación > ±30% entre períodos) sin explicación documentada.
- **Cuentas comodín** ("Otros/Varios/Diversos/Generales/Gestión") materiales: destino de gasto sin sustento.
- **Partes relacionadas** (accionistas, vinculadas, matriz, intercompañía): extracción de valor.
- **Gastos discrecionales** (viáticos, representación, consultorías, honorarios, movilización, publicidad).
- **Reversa de provisiones** ("cookie-jar").
- **Traspaso compensatorio**: una cuenta nace y otra desaparece por monto similar (reclasificación).
- **Montos redondos** repetidos idénticos entre períodos.
- **Cut-off de cierre** (concentración del gasto en el último período) — *requiere mayor mensual* → `[DATO NO DISPONIBLE]`.
- **Benford, concentración por proveedor, fraccionamiento** — *requiere detalle transaccional* → `[DATO NO DISPONIBLE]`.

## Agente 2 — Especialista NIIF / errores contables
**Qué revisa:**
- **Reclasificación entre líneas** (NIC 1.45): el total no cambia pero la composición sí.
- **Corte / devengo** (NIC 1, NIC 10): gasto en el período correcto; nº de meses implícito ≠ 12.
- **Gasto vs capitalización indebida** (NIC 16/38): caída anómala de gasto / D&A incoherente.
- **Costo de ventas e inventario** (NIC 2): margen bruto que se mueve sin sustento; deterioro NRV.
- **Provisiones y reversas** (NIC 37).
- **Errores de períodos anteriores / reexpresión** (NIC 8): saltos no explicados.
- **Partes relacionadas** (NIC 24) y **deducibilidad / impuesto diferido** (NIC 12).
- **Consistencia de políticas contables** 2023-2025 (método de depreciación, valuación, capitalización).
- Cada hallazgo se etiqueta con **norma NIIF presunta** y **naturaleza del error** (clasificación / reconocimiento / corte / valuación / política).

## Agente 3 — Control interno y presupuesto (COSO)
**Qué revisa:**
- **Presupuesto vs real** (no solo año vs año): gasto **no presupuestado**, sobre/sub-ejecución — *requiere presupuesto* → `[DATO NO DISPONIBLE]`.
- **Centro de costo / responsable / autorización** por cuenta — *requiere dimensión organizativa* → `[DATO NO DISPONIBLE]`; su ausencia es **en sí misma una debilidad de control**.
- **Gasto fijo/recurrente que se dispara** (debería ser estable).
- **Variación vs inflación** (crecimiento real injustificado) — *requiere tasa de inflación* → `[DATO NO DISPONIBLE]`.
- **Gastos discrecionales** y **cuentas "cajón de sastre"**.
- **Variaciones materiales sin explicación documentada** (bandera de control).
- **Concentración por responsable/centro** y patrones de **fraccionamiento** — *requiere detalle* → `[DATO NO DISPONIBLE]`.

---

## Mapa hallazgo → riesgo → acción (implementado en `renderFraude`)
| Bandera | Riesgo | Acción de mitigación | Norma |
|---|---|---|---|
| Nuevo | Sin historial ni aprobación | Autorización + sustento documental | NIC 8 / control |
| Eliminado | Reclasificación / omisión | Confirmar baja vs reclasificación; rastrear destino | NIC 1 / control |
| Volátil (>30%) | Error de corte / manejo de resultado | Documentar causa; revisar corte | NIC 8 |
| Comodín | Gasto sin sustento | Desglosar y soportar cada partida | NIC 1 |
| Relacionadas | Extracción de valor / PT | Contrato + aprobación Directorio + estudio PT | NIC 24 |
| Discrecional | Gasto personal / no deducible | Límites, aprobación, deducibilidad | NIC 12 |
| Provisión | Cookie-jar | Soportar cálculo y justificar reversas | NIC 37 |
| Traspaso | Maquillaje de márgenes | Validar reclasificación y su efecto | NIC 1.45 |
| Monto redondo | Estimación sin respaldo | Verificar factura/soporte real | Evidencia |

## Capa de machine learning (próxima fase)
Hoy la detección es **basada en reglas** (transparente y trazable para auditoría). Con el **mayor
auxiliar mensual por cuenta y tercero** se incorpora una capa ML **complementaria**:
- **Isolation Forest / LOF** → gastos atípicos (outliers) por cuenta/tercero.
- **Ley de Benford** sobre el primer dígito de los importes.
- **Clustering** de patrones de gasto (k-means/DBSCAN) para detectar comportamientos anómalos.
- **Scoring de riesgo** por cuenta combinando las banderas de reglas + features de comportamiento.
- **NLP** sobre descripciones de cuentas para clasificar y detectar comodines/ambigüedad.
La capa ML corre en backend (Python) sobre datos transaccionales; no sustituye las reglas, las potencia.

## Limitación estructural
Sobre solo el Balance/ER anual por cuenta, el análisis **señala comportamiento sospechoso para
investigar** — no prueba fraude. El salto de "análisis" a "forense" requiere el detalle transaccional/mensual.
