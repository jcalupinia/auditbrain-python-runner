# Tablero Ejecutivo · ACTIVO — Blueprint profesional
**Rol:** Ingeniero de Big Data + Analista de Dashboard Ejecutivo.
**Fuente de reglas:** `auditbrainDashboardPromptsV3` módulo `01_activos` (FASE 1–5) + reglas maestras (00).
**Caso de validación:** IAV S.A. (balance interno, ESF 31-dic-2024 vs 30-sep-2025).

---

## 1. Análisis de los datos (IAV) — qué dice el activo
- Activo total **$28,94M** (−1.0% vs Dic-24). **90% corriente** → negocio de capital de trabajo, no de activos fijos.
- Dominan **Inventarios 43.7%** (DIO ~192 d, lento) y **Cartera 31.1%** (DSO ~92 d). Juntos = 75% del activo.
- **Improductivos 8.6%** (>5% → alerta NIC 36): inversiones, relacionadas, anticipos, CxC L/P.
- **CxC relacionadas 5.3% del activo / 7.3% del patrimonio** → vigilar recuperabilidad y precios de transferencia.
- Movimiento del período: ↓ inventario −$1.12M, ↓ relacionadas −$0.58M, ↑ caja +$0.59M (mejora de calidad del activo).
- **Mensaje ejecutivo:** liquidez sobra (4.51x), el problema es **rotación** (capital atrapado >6 meses en bodega y ~3 en cartera).

---

## 2. Modelo de datos (qué alimenta el tablero)
| Dato | Estado | Fuente |
|---|---|---|
| Activo por rubro (corriente/no corriente), 2 períodos | ✅ disponible | parser balance interno (sin fusionar categorías) |
| Costo de ventas, ventas (ER) | ✅ | parser ER (anualizado por nº de meses) |
| Patrimonio (para CxC rel./patrimonio) | ✅ | parser |
| CAPEX, utilización de activos fijos | ❌ `[DATO NO DISPONIBLE]` | requiere detalle de inversiones |
| Aging de cartera, concentración de clientes | ❌ `[DATO NO DISPONIBLE]` | requiere cartera por cliente/antigüedad |
| Control de inventario (manual/sistema), obsolescencia | ❌ `[DATO NO DISPONIBLE]` | requiere kardex/provisión |

Regla anti-invención: lo no disponible se muestra como `[DATO NO DISPONIBLE — solicitar: …]`, nunca se inventa.

---

## 3. Diccionario de KPIs (fórmula · umbral · semáforo)
| KPI | Fórmula | Umbral | 
|---|---|---|
| Activo total / Δ | Σ activos · var % vs anterior | informativo |
| AC/AT · ANC/AT | corriente / total | perfil |
| Capital de trabajo | AC − PC | >0 🟢 |
| Liquidez corriente | AC / PC | ≥1.5 🟢 · 1–1.5 🟡 · <1 🔴 |
| Caja / activos | efectivo / activos | ocioso si >8% y sin inversiones 🟡 |
| Inventario / activos · **DIO** | inv/activos · inv/(costo/días) | DIO >120 d 🟡 · >180 🔴 |
| Cartera / activos · **DSO** | CxC/activos · CxC/(ventas/días) | DSO >60 d 🟡 |
| CxC relacionadas / activos · / patrimonio | — | /patrimonio >10% 🔴 |
| Activos improductivos / activos | (inversiones+relac.+anticipos+L/P)/activos | >5% 🔴 |
| PP&E / activos · Rotación de activos | — · ventas anualizadas/activos | rotación <1 🟡 |
| CAPEX / activos | — | `[DATO NO DISPONIBLE]` |

Cada KPI crítico cierra con **HALLAZGO / RIESGO / RECOMENDACIÓN / SEMÁFORO** (regla 00).

---

## 4. Gráficos sugeridos por el prompt (se mantienen TODOS) — con justificación
| # | Gráfico | Responde a | Cuándo aparece |
|---|---|---|---|
| 1 | **Donut/sunburst — composición del activo** | ¿En qué está invertido el activo? | siempre |
| 2 | **Barras comparativas (ant. vs actual)** por rubro material | ¿Qué creció/bajó? | si hay período anterior |
| 3 | **Waterfall — variación del activo** (Activo ant → Δ rubros → Activo actual) | ¿Qué explica el cambio del activo? | si hay período anterior |
| 4 | **Barras horizontales — cuentas materiales (% activo)** | ranking de concentración | siempre |
| 5 | **Línea — tendencia histórica** | ¿Cómo evoluciona? | si hay 3+ períodos |
| 6 | **Matriz de riesgo — materialidad vs recuperabilidad** | ¿Dónde está el riesgo? | siempre (cuentas materiales) |

> Nota: en la última iteración se habían retirado 3 y 6 por estética; el usuario pide **mantener los 6 del prompt**. Se conservan, mejorando su presentación (ejes legibles, etiquetas sin cortes, paleta navy/gold/teal).

---

## 5. Layout del tablero ejecutivo (zonas, de arriba hacia abajo)
1. **Encabezado de sección** — "Activos · <fecha> — diagnóstico CFO".
2. **Banda de KPIs ejecutivos** — fila de indicadores clave (estilo Command Center) con valor grande + comparación vs anterior + semáforo.
3. **Composición** — donut (1) + barras horizontales materiales (4), lado a lado.
4. **Evolución** — barras comparativas (2) + waterfall de variación (3), lado a lado.
5. **Riesgo** — matriz materialidad vs recuperabilidad (6) + (línea de tendencia (5) si 3+ períodos).
6. **Tabla de indicadores/materialidad** — cuenta · saldo ant. · saldo actual · % activo · Δ% · Δ participación.
7. **Análisis ejecutivo** — bloques **A** (dashboard) · **B** (KPIs) · **C** (alertas) · **D** (recomendaciones) · **Cierre** (Top 3 fortalezas/riesgos/acciones + semáforo general).

Paleta: navy `#071B2F` fondo, paneles grafito, acentos gold/teal/green/red por semáforo. Tipografía Montserrat (títulos) + Roboto Mono (cifras). Coherente con el resto del dashboard.

---

## 6. Decisión pendiente del usuario
- ¿Banda de KPIs como **tarjetas** (estilo Command Center) o como **lista compacta**? (en iteraciones previas: tarjetas planas y lista larga fueron rechazadas; la versión de tarjetas con borde de acento + "vs anterior" es la candidata).
- Confirmar que se mantienen los **6 gráficos** del prompt en el layout anterior.

Una vez aprobado este blueprint, se implementa en `dashboard_template.html` (`renderBalance`, bloque Activos) en una sola pasada y se replica el patrón a Pasivos (02) y Patrimonio (03).
