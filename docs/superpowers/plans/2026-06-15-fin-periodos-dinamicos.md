# Análisis Financiero Empresarial — Períodos dinámicos · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Permitir que la herramienta FIN compare períodos arbitrarios (anual/semestral/trimestral/mensual, 2..N cortes), tratando el balance como stock (sin ajuste) y el estado de resultados como flujo (con prorrateo a base común).

**Architecture:** Se generaliza el modelo de "3 años fijos" a `PERIODOS` dinámico (labels + meses). El balance se compara directo; el ER se normaliza por meses antes de mapear al dashboard. Reúso de parsers e ingesta existentes; la plantilla del dashboard ya es período-agnóstica.

**Tech Stack:** React+Vite (frontend), FastAPI+pandas (backend), verificación con `vite build`, Node ESM y Playwright.

---

### Task 1: Generalizar finModel a períodos dinámicos + normalización ER

**Files:**
- Modify: `frontend/src/fin/finModel.js`

- [ ] **Step 1: Añadir constantes de período y `ER_KEYS`**

```js
export const PERIODO_MESES = { anual: 12, semestral: 6, trimestral: 3, mensual: 1 };
export const ER_KEYS = ["ventas","otrosIng","otrosIngFin","costo","gAdmin","gFin","partTrab","irCausado","impDif"];
```

- [ ] **Step 2: Añadir `normalizarER(D, periodos, baseMeses)`** — prorratea SOLO claves ER por `baseMeses / meses`, sin tocar balance. Devuelve un D nuevo.

```js
export function normalizarER(D, periodos, baseMeses) {
  const out = {};
  Object.keys(D).forEach((k) => { out[k] = D[k].slice(); });
  periodos.forEach((p, i) => {
    if (!p.normalizar || !p.meses || p.meses === baseMeses) return;
    const f = baseMeses / p.meses;
    ER_KEYS.forEach((k) => { if (out[k]) out[k][i] = Math.round((out[k][i] || 0) * f); });
  });
  return out;
}
```

- [ ] **Step 3: Generalizar `mapToDashboard(D, labels)` y `buildDetailedBalance(D, labels)`** para recibir `labels` (array) en vez de `FIN_YRS` fijo; iterar sobre `labels` (longitud N). Default `labels = FIN_YRS` si no se pasa (compat).

- [ ] **Step 4: Verificar** — `node` ESM: mapear EX con labels `["2024","2025"]` (2 períodos) y `["A","B","C"]`; checar que `mapToDashboard` produce objetos keyed por label y `checkBalance` cuadra.

Run: script en `frontend/` que importa finModel y EX.
Expected: dif≈0 por período.

- [ ] **Step 5: Commit** `feat(fin): finModel con períodos dinámicos + normalización ER`

---

### Task 2: Parser de balance interno — soportar corte parcial (1 columna)

**Files:**
- Modify: `backend/app/tax/planificacion_utilidades/parsers/balance_interno.py`

- [ ] **Step 1:** En `_detect_years`, además de años (4 dígitos), detectar encabezados de corte ("JUNIO", "JUN", "30/06/AAAA", "A JUNIO AAAA") y devolver el set de columnas-período aunque haya solo 1.
- [ ] **Step 2:** En `extract_*`, no forzar `years[-3:]`; devolver TODAS las columnas-período detectadas (1..N) y un `periodos_detectados: [{label, meses?}]`.
- [ ] **Step 3: Verificar** con el archivo real (3 columnas) y con un recorte simulado a 1 columna (copiar ESF a una hoja con solo la col 2025) → parser devuelve 1 período, balance cuadra.
- [ ] **Step 4: Commit** `feat(fin): parser interno soporta cortes parciales (N columnas)`

---

### Task 3: Estado de períodos + selector "Período de análisis" en la herramienta

**Files:**
- Modify: `frontend/src/fin/DashboardEjecutivoTool.jsx`

- [ ] **Step 1:** Reemplazar `D` de 3 columnas por estado `periodos = [{id,label,meses,normalizar}]` + `D` alineado (N columnas). Inicial: cargar EX como 3 períodos anuales.
- [ ] **Step 2:** Añadir selector "Período de análisis" (anual/semestral/trimestral/mensual) que fija `meses` por defecto de los nuevos períodos.
- [ ] **Step 3:** Gestor de períodos: lista editable (label, meses, normalizar, eliminar) + "Agregar período" (abre fuente de información).
- [ ] **Step 4:** Ingesta: cada archivo procesado **añade** sus columnas como períodos nuevos (label auto del año/corte, meses del selector). Merge en `D` por índice de período.
- [ ] **Step 5: Verificar** `vite build` OK.
- [ ] **Step 6: Commit** `feat(fin): selector de período + gestor de períodos dinámicos`

---

### Task 4: Flujo "¿lo tienes o lo proyectamos?" + normalización ER

**Files:**
- Modify: `frontend/src/fin/DashboardEjecutivoTool.jsx`

- [ ] **Step 1:** Tras añadir un período, si `mesesER` del corte ≠ meses del análisis, mostrar el mensaje con dos opciones: "Lo tengo" (normalizar=false) / "Proyectarlo" (normalizar=true) + factor editable.
- [ ] **Step 2:** Aplicar `normalizarER` (Task 1) antes de `mapToDashboard`/`buildStandaloneHTML`; etiqueta de aviso "prorrateo lineal, no ajustado por estacionalidad".
- [ ] **Step 3:** Ocultar proyección 3 estados salvo que todos los períodos sean `meses===12`.
- [ ] **Step 4: Verificar** `vite build` OK.
- [ ] **Step 5: Commit** `feat(fin): prorrateo guiado del ER (stock vs flujo)`

---

### Task 5: Export con períodos + meses

**Files:**
- Modify: `frontend/src/fin/dashboardExport.js`

- [ ] **Step 1:** `buildStandaloneHTML({ D, header, detalle, nivel, periodos })` usa `periodos.map(p=>p.label)` para `__YRS__`, aplica `normalizarER` y `buildDetailedBalance` con esos labels.
- [ ] **Step 2: Verificar** generar HTML con 2 períodos (Dic-2025 vs Jun-2026 prorrateado) y abrir en Playwright: balance sin ajuste, ER prorrateado, sin errores JS.
- [ ] **Step 3: Commit** `feat(fin): export dashboard con períodos dinámicos`

---

### Task 6: Verificación integral con datos reales (caso del usuario)

**Files:**
- Test: script de verificación en `frontend/` (temporal)

- [ ] **Step 1:** Simular corte a junio desde el balance interno Galápagos (balance = saldos 2025 como "Jun-2026" stock; ER 2025 ÷12×6).
- [ ] **Step 2:** Verificar: balance compara directo (cuadra A=P+Pat), ER prorrateado = exactamente la mitad del anual, variaciones PoP calculadas, dashboard renderiza 2 períodos sin error.
- [ ] **Step 3:** Limpiar artefactos temporales.
- [ ] **Step 4: Commit** `test(fin): verificación períodos dinámicos con datos reales`
