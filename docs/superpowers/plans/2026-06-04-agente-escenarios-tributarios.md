# Agente de escenarios tributarios — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar al tool de Planificación una sección que compara 4 escenarios del pago a cuenta sobre utilidades no distribuidas (2026–2028), recomienda el óptimo con un agente híbrido (motor determinista + IA), y al aprobarse alimenta el Informe gerencial y la Presentación.

**Architecture:** Se EXTIENDE el motor existente (`frontend/src/tax/engine.js`: `computeModel`, `applyScenario`, `tarifa`) con `compareScenarios()` y un modelo de costo muerto a 2 años. Nueva sección React `SecEscenarios`. Endpoint backend `POST /tax/planificacion-utilidades/recomendacion` que genera la narrativa IA siguiendo los 6 controles de `backend/app/ict/audit/interpreter.py`. Las cifras son siempre del motor; la IA solo redacta.

**Tech Stack:** React 18 + Vite (frontend), FastAPI + Pydantic (backend), Vitest (tests de engine — se agrega), pytest (tests backend, ya existe).

---

## File Structure

**Crear:**
- `frontend/vitest.config.js` — config de tests del engine.
- `frontend/src/tax/__tests__/scenarios.test.js` — tests de `compareScenarios` y costo muerto.
- `frontend/src/tax/SecEscenarios.jsx` — sección nueva (tabla + inputs + panel agente).
- `backend/app/tax/planificacion_utilidades/recomendacion.py` — lógica del agente (prompt + 6 controles).
- `backend/tests/test_tax_recomendacion.py` — tests del endpoint/lógica del agente.

**Modificar:**
- `frontend/package.json` — script `test` + devDeps vitest.
- `frontend/src/tax/engine.js` — `compareScenarios`, `creditAging`, `bestScenario`.
- `frontend/src/tax/AnalisisTributarioTool.jsx` — registrar sección, estado `recomendacion`, pasar a Informe/deck.
- `frontend/src/tax/tax.css` — estilos de la comparación y el panel del agente.
- `frontend/src/api.js` — `generarRecomendacionAgente()`.
- `backend/app/tax/planificacion_utilidades/router.py` — endpoint `/recomendacion`.
- `backend/app/tax/planificacion_utilidades/schemas.py` — `RecomendacionRequest`/`Response`.

**Sin cambios (se reutiliza tal cual):**
- `backend/app/tax/planificacion_utilidades/pptx_builder.py` — el slide
  `_recomendacion` ya renderiza `content["recomendacion"]` y `content["nota"]`.
- `backend/app/chat/providers.py` — `chat_complete(messages, system)` es el cliente IA.

---

## FASE 0 — Setup de tests del engine

### Task 0: Agregar Vitest al frontend

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.js`

- [ ] **Step 1: Instalar vitest**

Run desde `frontend/`:
```bash
npm install -D vitest@^2.1.0
```
Expected: se agrega `vitest` a devDependencies, sin errores.

- [ ] **Step 2: Agregar el script `test` a package.json**

En `frontend/package.json`, en `"scripts"`, agregar:
```json
    "test": "vitest run",
```

- [ ] **Step 3: Crear `frontend/vitest.config.js`**

```js
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "node", include: ["src/**/*.test.js"] },
});
```

- [ ] **Step 4: Crear test trivial de humo y correrlo**

Crear `frontend/src/tax/__tests__/scenarios.test.js`:
```js
import { describe, it, expect } from "vitest";
import { tarifa } from "../engine.js";

describe("smoke", () => {
  it("tarifa tramo exento", () => {
    expect(tarifa(50000)).toBe(0);
    expect(tarifa(500000)).toBe(0.0075);
  });
});
```
Run: `npm test`
Expected: 2 assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.js frontend/src/tax/__tests__/scenarios.test.js
git commit -m "test(tax): agregar vitest para los tests del motor de escenarios"
```

---

## FASE 1 — Motor: comparación de escenarios + costo muerto 2 años

Contexto del motor existente (`engine.js`), NO modificar su lógica:
- `applyScenario(scn, D, CTRL, params)` → devuelve `CTRL` (array de 3 `{g,div,cap}`) para `scn ∈ {"sin","cap","div","mix"}`.
- `computeModel(D, CTRL, params)` → array de 3 filas con, por año: `pago` (impuesto/anticipo), `div`, `cap`, `base`, `tar`, `ret`, `cRet`, `cIR`, `dev` (devolución), `enR` (en riesgo simple), `neta`, `resAcum`, `patrimonio`.

### Task 1: `creditAging` — costo muerto a 2 ejercicios

**Files:**
- Modify: `frontend/src/tax/engine.js`
- Test: `frontend/src/tax/__tests__/scenarios.test.js`

Regla legal a modelar: el anticipo del año `t` se pierde (gasto no deducible) si NO hay distribución ni capitalización en los años `t`, `t+1`, `t+2`. Si la ventana excede el horizonte (2027, 2028), se marca `fueraHorizonte: true` para señalar riesgo no concluyente.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `scenarios.test.js`:
```js
import { creditAging } from "../engine.js";

describe("creditAging (costo muerto 2 años)", () => {
  // 3 años; anticipo 100 cada uno; acción (div/cap) solo en el año índice indicado
  const rows = (accionEn) =>
    [0, 1, 2].map((i) => ({
      pago: 100,
      div: accionEn.includes(i) ? 50 : 0,
      cap: 0,
    }));

  it("sin acción nunca: el anticipo de 2026 es costo muerto (ventana 0..2)", () => {
    const r = creditAging(rows([]));
    expect(r[0].costoMuerto).toBe(100); // 2026: sin acción en 0,1,2
  });

  it("acción en 2028 recupera el anticipo de 2026 (dentro de ventana)", () => {
    const r = creditAging(rows([2]));
    expect(r[0].costoMuerto).toBe(0); // hubo acción en el año 2 (= 2028)
  });

  it("anticipo de 2028 con ventana fuera de horizonte se marca", () => {
    const r = creditAging(rows([]));
    expect(r[2].fueraHorizonte).toBe(true);
  });
});
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `npm test`
Expected: FAIL — `creditAging is not a function`.

- [ ] **Step 3: Implementar `creditAging` en engine.js**

Agregar al final de `engine.js`:
```js
// Modelo de la "regla mortal": el anticipo del año t se pierde como gasto no
// deducible si NO hay distribución ni capitalización en t, t+1 o t+2. Si la
// ventana de 2 años excede el horizonte proyectado, se marca fueraHorizonte.
export function creditAging(rows) {
  const n = rows.length;
  return rows.map((r, t) => {
    const fin = Math.min(t + 2, n - 1);
    let recuperado = false;
    for (let k = t; k <= fin; k++) {
      if ((rows[k].div || 0) > 0 || (rows[k].cap || 0) > 0) recuperado = true;
    }
    const fueraHorizonte = t + 2 > n - 1;
    return {
      ...r,
      costoMuerto: recuperado ? 0 : r.pago || 0,
      fueraHorizonte,
    };
  });
}
```

- [ ] **Step 4: Correr el test**

Run: `npm test`
Expected: PASS (los 3 nuevos + el de humo).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tax/engine.js frontend/src/tax/__tests__/scenarios.test.js
git commit -m "feat(tax): modelo de costo muerto a 2 años (creditAging)"
```

### Task 2: `compareScenarios` — los 4 escenarios año por año

**Files:**
- Modify: `frontend/src/tax/engine.js`
- Test: `frontend/src/tax/__tests__/scenarios.test.js`

`compareScenarios(D, params, overrides)` devuelve un objeto `{ sin, div, mix, cap }`, cada uno `{ rows, totales }`. `rows[i]` por año: `{ anio, impuesto, repartido, capitalizado, sobrante, devolucion, costoMuerto, fueraHorizonte }`. `overrides` (opcional) = `{ div: CTRL, mix: CTRL }` para los montos editables; si falta, usa `applyScenario`.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `scenarios.test.js`:
```js
import { compareScenarios } from "../engine.js";
import { emptyData } from "../seed.js";

describe("compareScenarios", () => {
  const D = emptyData();
  // Empresa con utilidades acumuladas altas para que haya impuesto.
  D.resAcum = [0, 0, 5000000];
  D.utilAcum = [0, 0, 4000000];
  D.utilEjercicio = [0, 0, 1000000];
  D.ventas = [0, 0, 8000000];
  D.costo = [0, 0, 5000000];
  D.capital = [0, 0, 100000];
  const params = { costoR: 60, gastoR: 25, irR: 25, retDiv: 12, growth: 0 };

  const r = compareScenarios(D, params);

  it("devuelve los 4 escenarios", () => {
    expect(Object.keys(r).sort()).toEqual(["cap", "div", "mix", "sin"]);
  });

  it("'sin' tiene impuesto > 0 en 2026", () => {
    expect(r.sin.rows[0].impuesto).toBeGreaterThan(0);
  });

  it("'cap' (solo capitalización) lleva el impuesto a ~0", () => {
    const total = r.cap.totales.impuesto;
    expect(total).toBeLessThan(r.sin.totales.impuesto);
    expect(total).toBeLessThan(1);
  });

  it("cada escenario tiene 3 años con costoMuerto definido", () => {
    expect(r.sin.rows).toHaveLength(3);
    expect(typeof r.sin.rows[0].costoMuerto).toBe("number");
  });
});
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `npm test`
Expected: FAIL — `compareScenarios is not a function`.

- [ ] **Step 3: Implementar `compareScenarios` en engine.js**

Agregar al final de `engine.js` (usa `applyScenario`, `computeModel`, `creditAging`, `PROJ`, `tPat` ya definidos en el archivo; importar `PROJ` desde seed si no está — `engine.js` ya no importa PROJ, así que define los años localmente):
```js
// Comparación de los 4 escenarios año por año (2026–2028). Reusa el motor
// existente (applyScenario + computeModel) y le agrega el costo muerto a 2 años.
const _PROJ_YEARS = [2026, 2027, 2028];

export function compareScenarios(D, params, overrides = {}) {
  const build = (scn) => {
    const ctrl = overrides[scn] || applyScenario(scn, D, _emptyCtrl(), params);
    const model = computeModel(D, ctrl, params);
    const aged = creditAging(
      model.map((m) => ({ pago: m.pago, div: m.div, cap: m.cap })),
    );
    const rows = model.map((m, i) => ({
      anio: _PROJ_YEARS[i],
      impuesto: m.pago,
      repartido: m.div,
      capitalizado: m.cap,
      // sobrante = utilidad no distribuida que queda tras dividendos/capitalización
      sobrante: Math.max(0, m.resAcum),
      devolucion: m.dev,
      costoMuerto: aged[i].costoMuerto,
      fueraHorizonte: aged[i].fueraHorizonte,
    }));
    const sum = (k) => rows.reduce((a, r) => a + (r[k] || 0), 0);
    return {
      rows,
      totales: {
        impuesto: sum("impuesto"),
        repartido: sum("repartido"),
        capitalizado: sum("capitalizado"),
        devolucion: sum("devolucion"),
        costoMuerto: sum("costoMuerto"),
        // costo neto = lo efectivamente perdido (no recuperable)
        costoNeto: sum("costoMuerto"),
      },
    };
  };
  return { sin: build("sin"), div: build("div"), mix: build("mix"), cap: build("cap") };
}

function _emptyCtrl() {
  return [
    { g: 0, div: 0, cap: 0 },
    { g: 0, div: 0, cap: 0 },
    { g: 0, div: 0, cap: 0 },
  ];
}
```

- [ ] **Step 4: Correr el test**

Run: `npm test`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tax/engine.js frontend/src/tax/__tests__/scenarios.test.js
git commit -m "feat(tax): compareScenarios — 4 escenarios año por año con costo muerto"
```

### Task 3: `bestScenario` — selección determinista del óptimo

**Files:**
- Modify: `frontend/src/tax/engine.js`
- Test: `frontend/src/tax/__tests__/scenarios.test.js`

Óptimo = el escenario con menor **costo neto** = impuesto no recuperable (costo muerto) + impuesto pagado que no se devuelve. Empate → preferir el que elimina el impuesto (cap > mix > div > sin).

- [ ] **Step 1: Escribir el test que falla**

```js
import { bestScenario } from "../engine.js";

describe("bestScenario", () => {
  it("elige 'cap' cuando elimina el impuesto", () => {
    const D = emptyData();
    D.resAcum = [0, 0, 5000000]; D.utilEjercicio = [0, 0, 1000000];
    D.ventas = [0, 0, 8000000]; D.costo = [0, 0, 5000000]; D.capital = [0, 0, 100000];
    const params = { costoR: 60, gastoR: 25, irR: 25, retDiv: 12, growth: 0 };
    const r = compareScenarios(D, params);
    expect(bestScenario(r).key).toBe("cap");
  });
});
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `npm test`
Expected: FAIL — `bestScenario is not a function`.

- [ ] **Step 3: Implementar**

```js
export function bestScenario(comparison) {
  const orden = ["cap", "mix", "div", "sin"]; // desempate: preferir eliminar
  let best = null;
  for (const key of orden) {
    const c = comparison[key];
    const costo = c.totales.impuesto - c.totales.devolucion + c.totales.costoMuerto;
    if (best === null || costo < best.costo - 0.5) {
      best = { key, costo, totales: c.totales };
    }
  }
  return best;
}
```

- [ ] **Step 4: Correr el test**

Run: `npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tax/engine.js frontend/src/tax/__tests__/scenarios.test.js
git commit -m "feat(tax): bestScenario — selección determinista del óptimo"
```

### Task 4: Verificación empírica con F-101 real (regla suprema)

**Files:**
- Create (temporal, NO commitear): `frontend/src/tax/__tests__/_verif_real.test.js`

- [ ] **Step 1: Script de verificación con valores reales de ARCOLANDS**

Crear el archivo de test (valores extraídos del F-101 real 2025 de ARCOLANDS, ver `git log`): resAcum 9.337.339,48; ventas 23.615.573,51; costo 17.384.130,77; capital 100.000:
```js
import { describe, it, expect } from "vitest";
import { compareScenarios, bestScenario } from "../engine.js";
import { emptyData } from "../seed.js";

describe("verif real ARCOLANDS", () => {
  const D = emptyData();
  D.resAcum = [0, 0, 9337339.48];
  D.utilAcum = [0, 0, 6550130.89];
  D.utilEjercicio = [0, 0, 2787208.59];
  D.ventas = [0, 0, 23615573.51];
  D.costo = [0, 0, 17384130.77];
  D.capital = [0, 0, 100000];
  const params = { costoR: 73.6, gastoR: 8.2, irR: 25, retDiv: 12, growth: 0 };
  const r = compareScenarios(D, params);

  it("sin acción paga impuesto > 0", () => {
    expect(r.sin.totales.impuesto).toBeGreaterThan(0);
    console.log("Impuesto SIN acción 2026-2028:", r.sin.totales.impuesto);
  });
  it("solo capitalización elimina el impuesto", () => {
    expect(r.cap.totales.impuesto).toBeLessThan(1);
  });
  it("el óptimo no es 'sin'", () => {
    expect(bestScenario(r).key).not.toBe("sin");
  });
});
```

- [ ] **Step 2: Correr y revisar los números**

Run: `npm test src/tax/__tests__/_verif_real.test.js`
Expected: PASS. Anotar el impuesto "sin acción" impreso y confirmar que es coherente con lo que muestra hoy `SecImpuesto`/`SecDashboard` para el escenario Sin acción (deben coincidir; si no, revisar el mapeo de `compareScenarios`).

- [ ] **Step 3: Borrar el archivo temporal**

```bash
rm frontend/src/tax/__tests__/_verif_real.test.js
```
(No se commitea; es verificación puntual.)

---

## FASE 2 — Sección `SecEscenarios` (frontend)

### Task 5: Registrar la sección en el tool

**Files:**
- Modify: `frontend/src/tax/AnalisisTributarioTool.jsx`

- [ ] **Step 1: Importar la sección y `compareScenarios`/`bestScenario`**

En el bloque de imports desde `./engine.js` (donde ya se importan `computeModel`, etc.), agregar `compareScenarios`, `bestScenario`. Y al inicio del archivo, junto a otros componentes, importar:
```jsx
import SecEscenarios from "./SecEscenarios.jsx";
```

- [ ] **Step 2: Agregar la entrada al arreglo `SECTIONS`**

En `SECTIONS` (arreglo `[id, ícono, label]`), insertar después de `["proyectado", "6", "Estados proyectados"]`:
```jsx
  ["escenarios", "✦", "Escenarios + Recomendación"],
```

- [ ] **Step 3: Agregar el estado de la recomendación aprobada**

Junto a los otros `useState` del componente, agregar:
```jsx
  const [recomendacion, setRecomendacion] = useState(null); // { escenario, narrativa, totales, aprobado }
```

- [ ] **Step 4: Renderizar la sección en el switch de secciones**

Donde se renderizan las secciones según `section` (junto a `section === "proyectado" && <SecProyectado .../>`), agregar:
```jsx
      {section === "escenarios" && (
        <SecEscenarios
          D={D}
          params={params}
          recomendacion={recomendacion}
          setRecomendacion={setRecomendacion}
        />
      )}
```

- [ ] **Step 5: Build de humo**

Run desde `frontend/`: `npm run build`
Expected: fallará porque `SecEscenarios.jsx` aún no existe → eso confirma el wiring. Continúa al Task 6 antes de re-buildear.

### Task 6: Componente `SecEscenarios` — tabla comparativa + inputs

**Files:**
- Create: `frontend/src/tax/SecEscenarios.jsx`
- Modify: `frontend/src/tax/tax.css`

- [ ] **Step 1: Crear `SecEscenarios.jsx` con la tabla comparativa y montos editables**

```jsx
import { useMemo, useState } from "react";
import { compareScenarios, bestScenario, applyScenario } from "./engine.js";
import { fmt } from "./format.js";
import { PROJ } from "./seed.js";
import { generarRecomendacionAgente } from "../api.js";

const ESC = [
  { key: "sin", label: "1 · Sin estrategia" },
  { key: "div", label: "2 · Distribución" },
  { key: "mix", label: "3 · Capitalización + Distribución" },
  { key: "cap", label: "4 · Solo capitalización" },
];
const RUBROS = [
  ["impuesto", "Impuesto (pago a cuenta)"],
  ["repartido", "Dividendos repartidos"],
  ["capitalizado", "Capitalizado"],
  ["sobrante", "Sobrante (no distribuido)"],
  ["devolucion", "Devolución"],
  ["costoMuerto", "Costo muerto (gasto no deducible)"],
];

export default function SecEscenarios({ D, params, recomendacion, setRecomendacion }) {
  // overrides editables para escenarios 2 (div) y 3 (mix); default = applyScenario
  const [ov, setOv] = useState(() => ({
    div: applyScenario("div", D, _ctrl0(), params),
    mix: applyScenario("mix", D, _ctrl0(), params),
  }));
  const [iaLoading, setIaLoading] = useState(false);
  const [iaError, setIaError] = useState("");

  const cmp = useMemo(() => compareScenarios(D, params, ov), [D, params, ov]);
  const best = useMemo(() => bestScenario(cmp), [cmp]);

  const setMonto = (scn, anioIdx, campo, val) =>
    setOv((p) => ({
      ...p,
      [scn]: p[scn].map((r, i) =>
        i === anioIdx ? { ...r, [campo]: parseFloat(val) || 0 } : r,
      ),
    }));

  async function generar() {
    setIaLoading(true);
    setIaError("");
    try {
      const payload = {
        empresa: params.empresa || "",
        comparacion: cmp,
        recomendado: best.key,
      };
      const res = await generarRecomendacionAgente(payload);
      setRecomendacion({
        escenario: best.key,
        narrativa: res.narrativa,
        confianza: res.confianza_modelo,
        requiereRevision: res.requiere_revision_humana,
        totales: cmp[best.key].totales,
        aprobado: false,
      });
    } catch (e) {
      setIaError(e.message || "No se pudo generar la recomendación.");
    } finally {
      setIaLoading(false);
    }
  }

  return (
    <section>
      <div className="tx-h1">Escenarios + Recomendación del agente</div>
      <p className="tx-lead">
        Comparación del pago a cuenta sobre utilidades no distribuidas bajo 4
        escenarios (2026–2028). Edita los montos a repartir/capitalizar en los
        escenarios 2 y 3; el impuesto, el sobrante y el costo muerto recalculan
        en vivo. El agente recomienda el óptimo citando la base legal.
      </p>

      {ESC.map((e) => (
        <div className="tx-card" key={e.key}>
          <h3>
            {e.label}{" "}
            {best.key === e.key && <span className="tx-best">★ Recomendado</span>}
          </h3>
          {/* inputs editables solo para div y mix */}
          {(e.key === "div" || e.key === "mix") && (
            <div className="tx-scroll">
              <table className="tx-tbl">
                <thead>
                  <tr>
                    <th>Monto por año</th>
                    {PROJ.map((y) => (
                      <th key={y}>{y}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Dividendos a repartir</td>
                    {[0, 1, 2].map((i) => (
                      <td key={i}>
                        <input
                          className="tx-cin"
                          type="number"
                          value={ov[e.key][i].div}
                          onChange={(ev) => setMonto(e.key, i, "div", ev.target.value)}
                        />
                      </td>
                    ))}
                  </tr>
                  {e.key === "mix" && (
                    <tr>
                      <td>Valor a capitalizar</td>
                      {[0, 1, 2].map((i) => (
                        <td key={i}>
                          <input
                            className="tx-cin"
                            type="number"
                            value={ov[e.key][i].cap}
                            onChange={(ev) =>
                              setMonto(e.key, i, "cap", ev.target.value)
                            }
                          />
                        </td>
                      ))}
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
          <div className="tx-scroll">
            <table className="tx-tbl">
              <thead>
                <tr>
                  <th>Concepto (USD)</th>
                  {PROJ.map((y) => (
                    <th key={y}>{y}</th>
                  ))}
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {RUBROS.map(([k, l]) => (
                  <tr key={k} className={k === "costoMuerto" ? "chkrow" : ""}>
                    <td>{l}</td>
                    {cmp[e.key].rows.map((r, i) => (
                      <td key={i} className={k === "costoMuerto" && r[k] > 0 ? "cuadre-bad" : ""}>
                        {fmt(r[k])}
                      </td>
                    ))}
                    <td>{fmt(cmp[e.key].totales[k] || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      <div className="tx-card">
        <h3>Recomendación del agente</h3>
        <button className="tx-btn" onClick={generar} disabled={iaLoading}>
          {iaLoading ? "Generando…" : "Generar recomendación (IA)"}
        </button>
        {iaError && <span className="tx-warn-line">{iaError}</span>}
        {recomendacion && (
          <RecPanel rec={recomendacion} setRec={setRecomendacion} cmp={cmp} best={best} />
        )}
      </div>
    </section>
  );
}

function RecPanel({ rec, setRec, cmp, best }) {
  return (
    <div className={`tx-rec ${rec.confianza === "baja" ? "rec-baja" : ""}`}>
      <p className="tx-rec-narr">{rec.narrativa}</p>
      <p className="tx-disclaimer">
        Análisis generado por IA. La interpretación debe ser validada por el
        profesional responsable antes de cualquier decisión.
        {rec.requiereRevision && " ⚠ Requiere revisión humana."}
      </p>
      {!rec.aprobado ? (
        <button
          className="tx-btn primary"
          onClick={() => setRec({ ...rec, aprobado: true })}
        >
          Aprobar escenario → Informe y Presentación
        </button>
      ) : (
        <span className="tx-ok-line">
          ✓ Escenario aprobado. Disponible en Informe gerencial y Presentación.
        </span>
      )}
    </div>
  );
}

function _ctrl0() {
  return [
    { g: 0, div: 0, cap: 0 },
    { g: 0, div: 0, cap: 0 },
    { g: 0, div: 0, cap: 0 },
  ];
}
```

- [ ] **Step 2: Agregar estilos a `tax.css`**

Al final de `tax.css`:
```css
.tax-root .tx-best { color: #1e8449; font-weight: 700; font-size: 12px; margin-left: 8px; }
.tax-root .tx-rec { margin-top: 12px; padding: 14px; border-left: 4px solid var(--gold); background: #fafbfc; }
.tax-root .tx-rec.rec-baja { border-left-color: #c0392b; }
.tax-root .tx-rec-narr { white-space: pre-wrap; line-height: 1.5; }
.tax-root .tx-disclaimer { font-size: 11px; font-style: italic; color: #6b7280; margin-top: 10px; }
.tax-root .tx-btn.primary { background: var(--navy); color: #fff; }
```

- [ ] **Step 3: Build**

Run desde `frontend/`: `npm run build`
Expected: la API `generarRecomendacionAgente` aún no existe → el build fallará en el import. Continúa al Task 9 (api.js) o crea un stub temporal. Para verificar SOLO la UI sin backend, crear stub en `api.js` (Task 9) primero.

- [ ] **Step 4: Commit (tras agregar el stub de api en Task 9)**

```bash
git add frontend/src/tax/SecEscenarios.jsx frontend/src/tax/tax.css frontend/src/tax/AnalisisTributarioTool.jsx
git commit -m "feat(tax): sección Escenarios + Recomendación (tabla comparativa + montos editables)"
```

---

## FASE 3 — Agente IA (backend)

### Task 7: Schemas del agente

**Files:**
- Modify: `backend/app/tax/planificacion_utilidades/schemas.py`
- Test: `backend/tests/test_tax_recomendacion.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_tax_recomendacion.py`:
```python
from backend.app.tax.planificacion_utilidades.schemas import (
    RecomendacionRequest, RecomendacionResponse,
)

def test_request_acepta_comparacion():
    req = RecomendacionRequest(
        empresa="ARCOLANDS", recomendado="cap",
        comparacion={"sin": {"totales": {"impuesto": 100}}},
    )
    assert req.recomendado == "cap"

def test_response_tiene_controles_ia():
    r = RecomendacionResponse(
        narrativa="texto", confianza_modelo="alta", requiere_revision_humana=False,
    )
    assert r.confianza_modelo == "alta"
```

- [ ] **Step 2: Correr para verificar que falla**

Run desde la raíz del repo: `python -m pytest backend/tests/test_tax_recomendacion.py -v`
Expected: FAIL — ImportError (schemas no existen).

- [ ] **Step 3: Agregar los schemas en `schemas.py`**

```python
class RecomendacionRequest(BaseModel):
    """Cifras deterministas (del frontend) para que la IA redacte la recomendación."""

    empresa: str = ""
    recomendado: str = Field(description="clave del escenario óptimo: sin|div|mix|cap")
    comparacion: dict = Field(description="resultado de compareScenarios (4 escenarios)")


class RecomendacionResponse(BaseModel):
    """Narrativa del agente con los controles de IA obligatorios."""

    narrativa: str
    confianza_modelo: str = Field(default="media", description="alta|media|baja")
    requiere_revision_humana: bool = True
```

- [ ] **Step 4: Correr el test**

Run: `python -m pytest backend/tests/test_tax_recomendacion.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tax/planificacion_utilidades/schemas.py backend/tests/test_tax_recomendacion.py
git commit -m "feat(tax): schemas del agente de recomendación"
```

### Task 8: Lógica del agente + endpoint

**Files:**
- Create: `backend/app/tax/planificacion_utilidades/recomendacion.py`
- Modify: `backend/app/tax/planificacion_utilidades/router.py`
- Test: `backend/tests/test_tax_recomendacion.py`

Sigue el patrón de los 6 controles de `backend/app/ict/audit/interpreter.py` (revisarlo). Para el test, la llamada al LLM se mockea.

- [ ] **Step 1: Escribir el test que falla (lógica con LLM mockeado)**

Agregar a `test_tax_recomendacion.py`:
```python
from unittest.mock import patch
from backend.app.tax.planificacion_utilidades import recomendacion as rec

def test_build_recomendacion_fallback_si_llm_falla():
    # Si el LLM no está disponible, devuelve fallback graceful con revisión humana.
    with patch.object(rec, "_call_llm", side_effect=RuntimeError("no key")):
        out = rec.build_recomendacion(
            empresa="X", recomendado="cap",
            comparacion={"cap": {"totales": {"impuesto": 0, "costoMuerto": 0}}},
        )
    assert out.requiere_revision_humana is True
    assert "cap" in out.narrativa.lower() or "capitaliz" in out.narrativa.lower()

def test_build_recomendacion_usa_texto_del_llm():
    with patch.object(rec, "_call_llm", return_value="Recomendamos capitalizar."):
        out = rec.build_recomendacion(
            empresa="X", recomendado="cap",
            comparacion={"cap": {"totales": {"impuesto": 0, "costoMuerto": 0}}},
        )
    assert out.narrativa == "Recomendamos capitalizar."
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `python -m pytest backend/tests/test_tax_recomendacion.py -v`
Expected: FAIL — módulo `recomendacion` no existe.

- [ ] **Step 3: Implementar `recomendacion.py`**

```python
"""Agente híbrido: arma el prompt con las cifras deterministas y pide a la IA
la narrativa de recomendación. Cumple los 6 controles de interpretación IA
(ver backend/app/ict/audit/interpreter.py)."""

from __future__ import annotations

from backend.app.tax.planificacion_utilidades.schemas import RecomendacionResponse

_NOMBRES = {
    "sin": "Sin estrategia", "div": "Distribución de dividendos",
    "mix": "Capitalización + Distribución", "cap": "Solo capitalización",
}


def _call_llm(prompt: str) -> str:  # pragma: no cover - se mockea en tests
    """Llama al proveedor IA configurado vía backend/app/chat/providers.

    chat_complete elige el proveedor (gemini>groq>openrouter>anthropic>openai),
    reintenta con el siguiente si uno falla, y levanta ProviderUnavailable si no
    hay ninguno configurado (lo captura build_recomendacion → fallback)."""
    from backend.app.chat.providers import chat_complete
    system = (
        "Eres un asesor tributario senior en Ecuador. Redactas recomendaciones "
        "ejecutivas claras y prudentes. No inventas cifras."
    )
    return chat_complete([{"role": "user", "content": prompt}], system=system).content


def _prompt(empresa: str, recomendado: str, comparacion: dict) -> str:
    tot = comparacion.get(recomendado, {}).get("totales", {})
    return (
        "Eres un asesor tributario senior (Ecuador, régimen de pago a cuenta "
        "sobre utilidades no distribuidas, vigente desde sep-2025). Con base en "
        f"estas cifras YA CALCULADAS (no las recalcules) para {empresa}, redacta "
        "una recomendación ejecutiva (máx. 180 palabras) para la gerencia, "
        f"justificando el escenario '{_NOMBRES.get(recomendado, recomendado)}'. "
        "Menciona la regla de los 2 años (costo muerto) y la fecha de corte 31-jul. "
        f"Totales del escenario recomendado: {tot}. "
        "No inventes números distintos a los provistos."
    )


def build_recomendacion(empresa: str, recomendado: str, comparacion: dict) -> RecomendacionResponse:
    prompt = _prompt(empresa, recomendado, comparacion)
    try:
        narrativa = _call_llm(prompt).strip()
        confianza = "alta" if narrativa else "baja"
        return RecomendacionResponse(
            narrativa=narrativa,
            confianza_modelo=confianza,
            requiere_revision_humana=True,
        )
    except Exception:  # noqa: BLE001 — fallback graceful (control 1)
        nombre = _NOMBRES.get(recomendado, recomendado)
        return RecomendacionResponse(
            narrativa=(
                f"Recomendación (sin IA disponible): aplicar el escenario "
                f"'{nombre}'. Revise las cifras de la comparación y la regla de "
                "los 2 años antes de decidir."
            ),
            confianza_modelo="baja",
            requiere_revision_humana=True,
        )
```

(El cliente IA es `backend/app/chat/providers.chat_complete`, ya existente; el test mockea `rec._call_llm`, así que no hace red.)

- [ ] **Step 4: Correr el test**

Run: `python -m pytest backend/tests/test_tax_recomendacion.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Agregar el endpoint en `router.py`**

Importar arriba: `from backend.app.tax.planificacion_utilidades import recomendacion as rec_mod` y `RecomendacionRequest, RecomendacionResponse` desde schemas. Agregar:
```python
@router.post("/recomendacion", response_model=RecomendacionResponse)
def recomendacion_endpoint(
    body: RecomendacionRequest,
    current: User = Depends(get_current_user),
):
    """Genera la narrativa del agente (IA) anclada a las cifras deterministas."""
    return rec_mod.build_recomendacion(
        empresa=body.empresa,
        recomendado=body.recomendado,
        comparacion=body.comparacion,
    )
```

- [ ] **Step 6: Verificar que la app importa**

Run: `PYTHONPATH=. python -c "import backend.app.tax.planificacion_utilidades.router as r; print('OK', [x.path for x in r.router.routes][-1])"`
Expected: imprime `OK` y la ruta `/recomendacion`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/tax/planificacion_utilidades/recomendacion.py backend/app/tax/planificacion_utilidades/router.py backend/tests/test_tax_recomendacion.py
git commit -m "feat(tax): endpoint /recomendacion — agente IA con controles y fallback"
```

### Task 9: Función `generarRecomendacionAgente` en api.js

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Agregar la función (patrón de las otras funciones TAX)**

Junto a `consultarSriRuc`/`extractTaxPlan` en `api.js`:
```js
// Agente: genera la narrativa de recomendación a partir de las cifras
// deterministas de los escenarios. La IA no calcula números.
export async function generarRecomendacionAgente({ empresa, comparacion, recomendado }) {
  return parse(
    await fetch(`${TAX_PU_BASE}/recomendacion`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ empresa, comparacion, recomendado }),
    }),
  );
}
```
(Verificar que `parse`, `authHeaders`, `TAX_PU_BASE` ya existen en `api.js` — sí.)

- [ ] **Step 2: Build del frontend completo**

Run desde `frontend/`: `npm run build`
Expected: PASS (exit 0). Ahora `SecEscenarios` compila.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(tax): api generarRecomendacionAgente"
```

---

## FASE 4 — Cableado a Informe gerencial y Presentación

### Task 10: Inyectar la recomendación aprobada en el Informe gerencial

**Files:**
- Modify: `frontend/src/tax/AnalisisTributarioTool.jsx`

- [ ] **Step 1: Pasar `recomendacion` a `SecInforme`**

Donde se renderiza `<SecInforme .../>`, agregar la prop `recomendacion={recomendacion}`.

- [ ] **Step 2: Renderizar el bloque en `SecInforme`**

En la función `SecInforme(...)`, agregar el parámetro `recomendacion` a la firma. Al inicio del JSX devuelto (tras el título), insertar:
```jsx
      {recomendacion?.aprobado && (
        <div className="tx-card">
          <h3>Recomendación del agente (aprobada)</h3>
          <p className="tx-rec-narr">{recomendacion.narrativa}</p>
          <p className="tx-disclaimer">
            Análisis generado por IA. Validar por el profesional responsable.
          </p>
        </div>
      )}
```

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/tax/AnalisisTributarioTool.jsx
git commit -m "feat(tax): la recomendación aprobada aparece en el Informe gerencial"
```

### Task 11: Alimentar la recomendación al deck (el slide YA existe)

**Files:**
- Modify: `frontend/src/tax/AnalisisTributarioTool.jsx` (incluir `recomendacion` y `nota` en el `content` del deck)
- Test: `backend/tests/test_tax_recomendacion.py`

NOTA: `pptx_builder._recomendacion(prs, c)` (línea ~433) **ya renderiza**
`c.get("recomendacion", "")` (cuerpo del slide) y `c.get("nota", "")` (pie). No
se modifica `pptx_builder`; solo hay que poblar esos campos desde el frontend.

- [ ] **Step 1: Incluir la recomendación en el contenido del deck**

En la función que arma el `content` para `generarPresentacionTax` (buscar
`generarPresentacionTax(` en `AnalisisTributarioTool.jsx`), agregar al objeto
`content` (sobrescribe `recomendacion`/`nota` solo si hay una aprobada):
```jsx
    ...(recomendacion?.aprobado
      ? {
          recomendacion: recomendacion.narrativa,
          nota: "Análisis generado por IA. Validar por el profesional responsable.",
        }
      : {}),
```

- [ ] **Step 2: Test — el deck se genera con la recomendación (slide existente)**

Agregar a `test_tax_recomendacion.py`:
```python
from backend.app.tax.planificacion_utilidades import pptx_builder

def test_deck_se_genera_con_recomendacion():
    data = pptx_builder.build_deck({
        "empresa": "X",
        "recomendacion": "Capitalizar el excedente antes del 31 de julio.",
        "nota": "Análisis generado por IA. Validar por el profesional responsable.",
    })
    assert isinstance(data, (bytes, bytearray)) and len(data) > 1000
```

- [ ] **Step 3: Correr el test**

Run desde la raíz: `python -m pytest backend/tests/test_tax_recomendacion.py -v`
Expected: PASS (incluye el nuevo; el slide `_recomendacion` ya consume el campo).

- [ ] **Step 4: Build del frontend**

Run desde `frontend/`: `npm run build`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tax/AnalisisTributarioTool.jsx backend/tests/test_tax_recomendacion.py
git commit -m "feat(tax): la recomendación aprobada alimenta el slide del deck"
```

### Task 12: Verificación end-to-end (regla suprema)

- [ ] **Step 1: Suite completa**

Run: `python -m pytest backend/tests/test_tax_recomendacion.py -v` → todos PASS.
Run desde `frontend/`: `npm test` → todos PASS.
Run desde `frontend/`: `npm run build` → exit 0.

- [ ] **Step 2: Prueba manual con datos reales**

Levantar backend + frontend, cargar el F-101 real (ARCOLANDS 2025), entrar a "Escenarios + Recomendación":
- Verificar que "Sin estrategia" muestra impuesto por año coherente con la sección de Cálculo del impuesto.
- Editar dividendos en el escenario 2 y ver recálculo de sobrante/costo muerto.
- Verificar que "Solo capitalización" da impuesto ≈ 0.
- Generar recomendación (IA), aprobar, y confirmar que aparece en Informe gerencial y en la Presentación (.pptx descargado, abre sin reparación).

- [ ] **Step 3: Commit final / push (cuando el usuario lo pida)**

```bash
git push origin main
```

---

## Notas de verificación obligatorias (CLAUDE.md)
- El costo muerto a 2 años es una simplificación legal; validar el caso pérdida y los años cuya ventana excede 2028 (`fueraHorizonte`).
- La narrativa IA SIEMPRE lleva disclaimer visible y `requiere_revision_humana`.
- La presentación .pptx debe abrir sin cuadro de reparación.
- Comparar el escenario "Sin acción" de `compareScenarios` contra `SecImpuesto`/`SecDashboard`: deben dar el mismo impuesto.
