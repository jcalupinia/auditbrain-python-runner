# Diseño — Agente de escenarios tributarios (utilidades no distribuidas)

**Fecha:** 2026-06-04
**Módulo:** TAX · Planificación Impuesto Utilidades Retenidas
**Estado:** Aprobado (brainstorming) — pendiente plan de implementación

## 1. Objetivo

Crear un **agente** dentro del tool de Planificación que, a partir de la base
legal y de los estados financieros proyectados, calcule el **pago a cuenta sobre
utilidades no distribuidas** (vigente desde sep-2025) bajo **4 escenarios**,
recomiende a la gerencia la acción óptima para **disminuir o eliminar** el
impuesto **evitando que se pierda como crédito** (costo muerto), y al aprobarse
**alimente el Informe gerencial y la Presentación**.

## 2. Decisiones de diseño (confirmadas)

- **Agente híbrido:** los cálculos son **deterministas** (motor `engine.js`);
  la **IA** (proveedor ya configurado, p. ej. Claude) redacta el análisis de la
  base legal y la recomendación, **siempre anclada a las cifras del motor**.
- **Hogar:** una **sección nueva** "Escenarios + Recomendación" en el tool.
- **Montos por año (escenarios 2 y 3):** **editables con defaults inteligentes**
  (excedente sobre el tramo exento de 100.000), recálculo en vivo.
- **Al aprobar** un escenario, su resultado + recomendación **fluyen** al
  Informe gerencial (`SecInforme`) y a la Presentación (`pptx_builder`).

## 3. Los 4 escenarios

| # | Nombre | Mapeo motor | Salidas clave |
|---|--------|-------------|---------------|
| 1 | Sin estrategia | `sin` (div=0, cap=0) | Impuesto por año 2026–2028; costo muerto |
| 2 | Distribución de dividendos | `div` | + dividendo/año (editable), **sobrante**, regla de 2 años |
| 3 | Capitalización + Distribución | `mix` | + línea que **resta de utilidades el valor a capitalizar** |
| 4 | Solo capitalización | `cap` | Impuesto = 0 (se capitaliza el excedente) |

## 4. Base legal relevante (ya documentada en `SecLegal`)

- Naturaleza: **anticipo recuperable**, no impuesto definitivo.
- Fecha de corte: **31 de julio**; planificación debe perfeccionarse antes.
- Base: utilidad contable − 15% trab. − IR − reserva legal (+) acumuladas
  (−) dividendos/capitalizaciones ene–jul.
- Tarifa única por tramo (no progresiva): 0% / 0,75% / 1,25% / 1,75% / 2,25% / 2,5%.
- Recuperación del crédito: dividendos, capitalización, IR, devolución.
- **Regla mortal (2 años):** si se paga el anticipo y NO se distribuye ni
  capitaliza durante los **dos ejercicios siguientes**, el crédito se pierde y
  se registra como **gasto no deducible (costo muerto)**.

## 5. Componentes

### 5.1 Motor — `compareScenarios(D, params, overrides)` (engine.js)
Devuelve, por escenario, filas año-por-año 2026–2028 con:
`impuesto` (pago a cuenta), `repartido`, `capitalizado`, `sobrante`
(utilidad no distribuida remanente), `devolucion`, `costoMuerto`, `resAcum`,
y totales por escenario. Reutiliza `tarifa`, `computeER`, roll-forward
patrimonial y la lógica ya validada de `computeModel`.

### 5.2 Modelo de la regla de 2 años (costo muerto)
Refinar la marca simplificada actual (`enR` = pago del año sin acción) a un
**modelo de antigüedad del crédito**: cada anticipo pagado en el año _t_ se
rastrea; lo no recuperado (vía dividendos/capitalización/IR) hasta el año
_t+2_ se clasifica como **gasto no deducible**. La definición exacta del
recupero se valida empíricamente antes de cerrar (ver §7).

### 5.3 Sección `SecEscenarios` (frontend)
- **Tabla comparativa** 4 escenarios × 3 años (rubros de §5.1) + totales.
- Escenarios 2 y 3: **inputs editables por año** (dividendo / capitalización)
  con defaults; recálculo en vivo (reusa `CTRL`).
- **Panel "Recomendación del agente":**
  - El motor elige el óptimo = **menor costo neto** (impuesto no recuperado +
    costo muerto), respetando objetivos del usuario.
  - La **IA** redacta análisis de base legal + recomendación anclada a las
    cifras, con los **6 controles** del CLAUDE.md (schema Pydantic, QA
    evaluator, audit trail, **disclaimer visible**, `confianza_modelo`,
    `requiere_revision_humana`).
  - Botón **"Aprobar escenario → Informe y Presentación"**.

### 5.4 Endpoint `POST /tax/planificacion-utilidades/recomendacion`
Recibe cifras deterministas (del frontend) + contexto de base legal →
devuelve la narrativa del agente. **La IA no calcula ni inventa números.**
Sigue el patrón de los endpoints existentes (JWT, schemas Pydantic).

### 5.5 Flujo a Informe + Presentación
Al aprobar, el escenario elegido + recomendación se guardan en estado
(`recomendacion`) y se inyectan en `SecInforme` y en el contenido del deck
(`generarPresentacionTax` / `pptx_builder`), que ya existen.

## 6. Flujo de datos

```
D + params
   → compareScenarios()            (4 escenarios × 3 años, deterministas)
   → [usuario edita montos esc. 2/3] → recálculo en vivo
   → POST /recomendacion (IA)      (narrativa anclada a cifras)
   → "Aprobar"                     → estado `recomendacion`
   → Informe gerencial + Presentación
```

## 7. Verificación (regla suprema del proyecto)

- Probar `compareScenarios` con el **F-101 real** (ARCOLANDS 2025) y comparar
  el escenario "Sin acción" contra el cálculo actual del tool (deben coincidir).
- Validar el modelo de **costo muerto a 2 años** con un caso numérico armado a
  mano (anticipo año 1 no recuperado hasta año 3 → gasto no deducible).
- Confirmar que el escenario "Solo capitalización" da **impuesto = 0**.
- Excel/Informe/Presentación deben abrir sin reparación y mostrar la
  recomendación con disclaimer de IA.

## 8. Secuencia de construcción

1. **Motor:** `compareScenarios` + modelo costo muerto 2 años (+ verificación).
2. **UI:** sección `SecEscenarios` (tabla + inputs editables + panel).
3. **Agente IA:** endpoint `recomendacion` con los 6 controles.
4. **Cableado:** aprobación → Informe + Presentación.

## 9. Fuera de alcance (YAGNI)

- No se reescribe la lógica tributaria existente (tarifa, roll-forward).
- No se agregan escenarios adicionales más allá de los 4.
- No se construye un framework de "agentes" genérico; es específico de este tool.
