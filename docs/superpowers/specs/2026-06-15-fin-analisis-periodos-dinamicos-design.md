# Diseño · Análisis Financiero Empresarial — Períodos dinámicos

**Fecha:** 2026-06-15
**Módulo:** FIN · CFO Intelligence → Análisis → "Análisis Financiero Empresarial" (Fase 1)
**Estado:** Aprobado por el usuario (luz verde). Pendiente plan de implementación.

## 1. Contexto y objetivo

La herramienta "Análisis Financiero Empresarial" (Fase 1 · Análisis de estados
financieros) hoy compara **3 años fijos (2023-2024-2025)**. El usuario (gerente
financiero) necesita **elegir libremente los períodos a analizar y compararlos**,
con cualquier fuente de información.

Casos de uso reales:
- Comparar 2 o 3 años completos.
- Comparar un corte parcial contra un período anterior (ej. **Balance Dic-2025 vs
  Balance a Jun-2026**).
- Comparar el mismo corte interanual (**Jun-2025 vs Jun-2026**).

## 2. Concepto central: STOCK vs FLUJO

| Estado | Naturaleza | Tratamiento al comparar períodos de distinta longitud |
|---|---|---|
| **Balance (ESF)** | Stock (saldo acumulado a una fecha) | **Directo, sin ajuste.** Cada corte es la foto a su fecha. |
| **Estado de Resultados (ER)** | Flujo del período | **Normalización temporal (prorrateo)** a una base común cuando las longitudes difieren. |

Regla de oro: **el balance nunca se prorratea; el ER sí cuando hace falta.**

## 3. Período de análisis

Selector: **Anual / Semestral / Trimestral / Mensual** → factor de meses:

| Período | Meses |
|---|---|
| Anual | 12 |
| Semestral | 6 |
| Trimestral | 3 |
| Mensual | 1 |

Cada **período cargado** tiene: `label` (ej. "Jun 2025"), `meses` (longitud real
del corte del ER) y los datos ESF/ER.

## 4. Flujo guiado

1. Usuario elige **Período de análisis**.
2. Sistema indica el **formato a subir** (columnas/plantilla según el período).
3. Usuario carga 2..N cortes (cada archivo = un período). Fuente: F-101 /
   balances internos / auditados (reúso de parsers existentes).
4. Tras la carga, si el ER no coincide con la granularidad elegida, mensaje:
   > *"¿Tienes el estado de resultados {trimestral}, o lo proyectamos?"*
   - **Lo tengo** → usa el dato real.
   - **Proyectarlo** → prorratea: `valor_normalizado = valor / meses_origen × meses_objetivo`.
     Aviso obligatorio: *"Prorrateo lineal, no ajustado por estacionalidad."*
     Factor editable por el usuario.
5. Dashboard comparativo con los períodos elegidos.

## 5. Metodología financiera (plugin finance · variance-analysis)

- **Comparación primaria:** Actual vs Período Anterior (PoP).
- **Umbral de materialidad PoP:** 15% (o umbral en USD configurable). Las
  variaciones que lo superen se **marcan** para investigación.
- **Narrativa de variación** por línea material: *[Favorable/Desfavorable] de
  $X (Y%) · Driver · Outlook · Acción*. Evitar anti-patrones (explicaciones
  circulares/vagas).
- **Bridge/waterfall** para descomponer la variación de utilidad (inicio +
  drivers = fin; reconcilia exacto).
- Para el ER, la variación se calcula **sobre la base ya normalizada** (mismo
  número de meses); el balance se compara en términos absolutos (stock).

## 6. Cambios de arquitectura

### 6.1 Modelo de datos (frontend)
- Reemplazar `FIN_YRS` fijo por `PERIODOS = [{ id, label, meses, tipoER }]`
  dinámico (2..N).
- El modelo `D` pasa de `{key:[a,b,c]}` (3 fijos) a `{key:[...N]}` indexado por
  período.
- `mapToDashboard` y `buildDetailedBalance` ya iteran sobre `FIN_YRS`; se
  generalizan para `PERIODOS` (longitud variable, labels string).
- La plantilla del dashboard ya usa `YRS` dinámico (cambio previo); se alimenta
  con `PERIODOS.map(p => p.label)`.

### 6.2 Normalización del ER
- Nueva función `normalizarER(D, periodos, baseMeses)` que prorratea solo las
  claves de ER (`ventas, otrosIng, otrosIngFin, costo, gAdmin, gFin, partTrab,
  irCausado, impDif`) por `baseMeses / p.meses`. **No toca claves de balance.**
- El balance (ESF) se compara sin tocar.

### 6.3 Backend / ingesta
- Reúso de parsers existentes (`f101`, `balance_resumido`, `balance_interno`).
- El parser de balances internos ya detecta columnas por año; se extiende para
  reconocer **una sola columna de corte** (período parcial) y devolver 1 período.
- Cada llamada `/extract` devuelve uno o más períodos; el frontend los acumula
  en la lista de `PERIODOS` con su label/meses.

### 6.4 Proyección
- La proyección automática a 3 estados **solo se habilita** cuando los períodos
  son **años completos** (`meses === 12`) y hay ≥1 período. Para cortes parciales
  se oculta (prorratear medio año a proyección no tiene sentido contable).

## 7. UI

- Selector "Período de análisis" (Anual/Semestral/Trimestral/Mensual).
- Gestor de períodos: lista editable (label, meses, eliminar), botón "Agregar
  período" que abre la fuente de información.
- Mensaje guiado "¿lo tienes o lo proyectamos?" con factor editable.
- Toggle de normalización del ER (ON/OFF) con etiqueta de aviso.
- Dashboard adapta KPIs, balance (resumido/detallado), resultados, variaciones,
  gastos, atípicos, activos, inversiones a los períodos seleccionados.

## 8. Verificación (regla suprema)

- **Balance:** A = Pasivo + Patrimonio cuadra en cada período cargado.
- **Prorrateo:** ER 2025 (12m) ÷12×6 = mitad exacta; validar con dato real.
- **Caso de prueba:** Balance Dic-2025 vs Balance a Jun-2026 (stock, sin ajuste)
  + ER 2025 prorrateado a 6m vs ER Jun-2026 (flujo, normalizado).
- **Datos reales:** usar el balance interno ya entregado (Galápagos) simulando un
  corte a junio; si el usuario entrega un archivo "a junio" real, validar con él.
- `vite build` compila; parser corre sobre archivo real; sin errores JS.

## 9. Fuera de alcance (esta iteración)

- Parsing de balances internos/auditados en **PDF/Word** (solo Excel por ahora).
- Ajuste por **estacionalidad** del prorrateo (se documenta como aproximación).
- Decomposición price/volume del ER (requiere unidades/cantidades; el ER interno
  no las trae).

## 10. Reúso

- Parsers: `f101`, `balance_resumido`, `balance_interno` (ya hechos/verificados).
- Motor: `engine.js` (proyección, índices), `mapToDashboard`, `buildDetailedBalance`.
- Export: HTML autocontenido, Excel, informe gerencial pptx.
- Plantilla del dashboard (períodos dinámicos, nivel resumido/detallado).
