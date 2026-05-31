# Manual — Planificación Impuesto sobre Utilidades No Distribuidas

**Módulo:** TAX (Tax Structuring) › pestaña **Análisis**
**Herramienta:** "Planificación Impuesto Utilidades Retenidas"
**Plataforma:** AuditBrain — Command Center
**Versión del documento:** 1.0 · 2026-05-29

---

## 1. Qué hace

Es una herramienta de **planificación tributaria interactiva** para el régimen
ecuatoriano de **pago a cuenta sobre utilidades no distribuidas** (vigente desde
septiembre de 2025).

Permite al consultor:

- Cargar los estados financieros de una empresa (a mano, desde el **Formulario 101**
  del SRI, o desde un **balance resumido** de auditoría externa).
- Calcular en vivo el **pago a cuenta** sobre las utilidades acumuladas que no se
  distribuyen ni capitalizan.
- Simular **escenarios** (sin acción, capitalización, distribución, mixto) y ver al
  instante el impacto en caja, patrimonio y riesgo de "costo muerto".
- Proyectar tres años (2026–2028) y analizar el **crédito tributario en cascada**
  (retención de dividendos → Impuesto a la Renta → devolución).
- Generar un **informe gerencial** y descargar un **Excel con fórmulas nativas**
  que sigue recalculando fuera de la plataforma.

**Problema que resuelve:** convierte un cálculo normativo complejo y cambiante en
un tablero que el consultor ajusta en segundos, sin rehacer hojas de cálculo, y
entrega un producto presentable al cliente con trazabilidad de los supuestos.

---

## 2. Conceptos tributarios que modela

> ⚠️ **La lógica tributaria no se altera sin validación humana.** Los parámetros
> normativos (tarifa por tramo, tasa de IR, retención de dividendos, reserva legal)
> son **editables** y deben validarse contra la normativa vigente y los criterios
> del SRI antes de presentar cifras como firmes.

- **Naturaleza:** no es un impuesto definitivo, sino un **anticipo recuperable**
  que paga la sociedad por mantener utilidades acumuladas sin distribuir ni
  capitalizar.
- **Base imponible:** utilidades acumuladas − dividendos − capitalización
  (con corte normativo al **31 de julio**).
- **Tarifa única por tramo (no progresiva):** la tarifa del tramo se aplica a
  **toda** la base. Tramos por defecto (editables):

  | Base hasta | Tarifa |
  |---|---|
  | 100.000 | 0,00 % |
  | 1.000.000 | 0,75 % |
  | 10.000.000 | 1,25 % |
  | 100.000.000 | 1,75 % |
  | 500.000.000 | 2,25 % |
  | > 500.000.000 | 2,50 % |

- **Crédito en cascada:** el pago a cuenta se compensa (1) contra la retención del
  impuesto único a dividendos, (2) contra el Impuesto a la Renta causado, y el
  excedente (3) se solicita en **devolución**.
- **Riesgo de "costo muerto":** si no hay distribución ni capitalización, el pago
  queda **en riesgo** de no recuperarse.
- **Roll-forward patrimonial:** `Patrimonio_t = Patrimonio_{t-1} + utilidad neta − dividendos`.

---

## 3. Alcance

**Incluye:**

- 3 años históricos (por defecto 2023–2024–2025) + 3 años proyectados (2026–2028).
- Estados financieros resumidos (ESF y ER) como **única fuente de datos**; todo lo
  demás se deriva por fórmula.
- Índices financieros (liquidez, prueba ácida, endeudamiento, márgenes, ROE/ROA,
  rotación, días de cartera/inventario/proveedores).
- Cálculo del impuesto, retenciones de dividendos, crédito vs. renta y estados
  proyectados.
- Dashboards (Chart.js) e informe gerencial.
- Ingesta automática (F-101 PDF / balance resumido .xlsx) y exportación a Excel.

**No incluye / límites:**

- No sustituye la **asesoría legal-tributaria** ni los criterios administrativos del SRI.
- El **mapeo de casilleros del F-101** es un *default editable*: la numeración varía
  por versión del formulario y **requiere validación humana**.
- Los parámetros normativos son supuestos editables, no cifras oficiales.
- Es una herramienta de planificación/simulación, no una declaración oficial.

---

## 4. Cómo lo hace (arquitectura)

```
┌──────────────────────────── FRONTEND (React + Vite) ───────────────────────────┐
│  frontend/src/tax/                                                              │
│   • AnalisisTributarioTool.jsx  Componente principal. Estado en el navegador    │
│                                 (D = datos, CTRL = palancas, params, escenario).│
│                                 Recálculo EN VIVO con useMemo.                   │
│   • engine.js   Motor tributario puro (tarifa por tramo, totales ESF/ER,        │
│                 índices, computeER, computeModel, comparación de escenarios).   │
│   • seed.js     Esquemas ESF/ER, claves de input, años y semilla de ejemplo.    │
│   • format.js   Formateadores (moneda, %, decimales).                           │
│   • TaxChart.jsx / TaxCatalog.jsx / tax.css   Gráficos, catálogo y estilos.     │
└─────────────────────────────────────────────────────────────────────────────────┘
                         │  (HTTP, solo para ingesta y exportación)
                         ▼
┌──────────────────────────── BACKEND (FastAPI, stateless) ──────────────────────┐
│  backend/app/tax/planificacion_utilidades/                                      │
│   • router.py        POST /extract · POST /export · GET /plantilla              │
│   • parsers/f101.py            Lee el F-101 (pdfplumber) → claves ESF/ER         │
│   • parsers/balance_resumido.py Lee la plantilla .xlsx (openpyxl)               │
│   • parsers/sri_text.py        Utilidades de parseo SRI (casilleros, RUC, año)  │
│   • mapping.py       Mapeo casilleros F-101 → claves (editable, validable)      │
│   • exporter.py      Excel con FÓRMULAS NATIVAS (Datos/ESF/ER/Índices/          │
│                      Proyección/Resumen) + generador de plantilla en blanco     │
│   • schema.py        Espejo Python de los esquemas ESF/ER de seed.js            │
│   • schemas.py       Modelos Pydantic de entrada/salida                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Principios de diseño:**

- **Recálculo en vivo en el navegador:** el motor (`engine.js`) es puro; al editar
  cualquier celda azul o parámetro, todos los índices, impuestos y proyecciones se
  recomputan inmediatamente vía `useMemo`. No hay "guardar y recalcular".
- **Backend sin estado (stateless):** no hay base de datos ni trabajos en cola para
  esta herramienta. El backend solo (a) parsea archivos de ingesta y (b) arma el
  Excel. El estado vive en el navegador. Esto lo hace simple, aditivo y reversible.
- **Una sola fuente de datos:** los inputs ESF/ER alimentan todo. Las líneas de
  total/subtotal son fórmulas, nunca números "horneados".
- **Reutilizable:** nada está hardcodeado por empresa fuera de la semilla de ejemplo
  (`EX` en `seed.js`).

---

## 5. Flujo de uso (paso a paso)

1. **Abrir la herramienta:** Command Center → módulo **TAX** → pestaña **Análisis**
   → "Planificación Impuesto Utilidades Retenidas".
2. **Datos del cliente:** nombre/razón social, RUC, representante legal, fecha de
   corte y fecha del análisis. Encabezan el informe gerencial.
3. **Cargar estados financieros**, por cualquiera de tres vías:
   - A mano, editando las **celdas azules** de Estados financieros.
   - **⬆ Formulario 101**: subir el PDF del SRI → el sistema extrae los casilleros
     y puebla ESF/ER (columna del año detectado).
   - **⬆ Balance resumido**: descargar la **plantilla en blanco**, llenarla y subirla.
4. **Revisar índices** y el **cálculo del impuesto**.
5. **Simular escenarios** (Sin acción / Capitalización / Distribución / Mixto) y
   ajustar las palancas por año (crecimiento, dividendos, capitalización).
6. **Analizar** crédito vs. renta, estados proyectados y dashboards.
7. **Informe gerencial:** revisar la portada (dirigida al representante legal) y el
   contenido.
8. **Exportar:** botón **⬇ Excel** → archivo con fórmulas nativas; o **🖨 PDF** para
   imprimir el informe.

---

## 6. Qué te entrega

1. **Análisis interactivo en pantalla** — estados financieros, índices, cálculo del
   impuesto, retenciones, crédito y proyecciones que recalculan en vivo.
2. **Comparación de escenarios** — pago "sin acción" vs. estrategia elegida, con el
   ahorro/diferimiento y el monto en riesgo de costo muerto.
3. **Informe gerencial** — portada con datos del cliente, saludo al representante
   legal y conclusiones; imprimible a PDF.
4. **Excel con fórmulas NATIVAS interactivas** — hojas **Resumen, Datos, ESF, ER,
   Índices, Proyección**. Las celdas de input quedan editables (azules) y todos los
   totales, índices, la tarifa por tramo y el motor de proyección son **fórmulas de
   Excel** que recalculan al abrir y editar el archivo (no son valores estáticos).
5. **Plantilla de balance resumido** (.xlsx en blanco) para estandarizar la entrega
   de datos del cliente o del equipo de auditoría externa.

> **Verificado:** el Excel exportado se recalculó con un motor de fórmulas y produjo
> los mismos números que el motor de la aplicación (p. ej. base 4.258.920 × tarifa
> 1,25 % = pago 53.236,50), confirmando que las fórmulas son nativas y consistentes.

---

## 7. Referencia técnica

### 7.1 Endpoints (backend)

Prefijo: `/api/v1/tax/planificacion-utilidades` · Autenticación: JWT (Bearer).

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/extract` | Ingesta. `multipart`: `kind` = `f101` \| `resumido`, `file`. Devuelve `data` (claves ESF/ER por año), `params` (empresa/RUC), `warnings`, `casilleros_leidos`, `anio_detectado`. |
| `POST` | `/export` | Exportación. `JSON`: `data`, `ctrl`, `params`. Devuelve el `.xlsx` con fórmulas nativas. |
| `GET` | `/plantilla` | Devuelve la plantilla de balance resumido en blanco (`.xlsx`). |

### 7.2 Funciones cliente (frontend, `src/api.js`)

- `extractTaxPlan(kind, file)` — sube F-101 / balance resumido y devuelve los datos mapeados.
- `exportTaxPlan({ data, ctrl, params })` — descarga el Excel del modelo actual.
- `downloadTaxPlantilla()` — descarga la plantilla en blanco.

### 7.3 Motor (frontend, `src/tax/engine.js`)

- `tarifa(base)` — tarifa única por tramo.
- `tAC/tActivo/tPC/tPasivo/tPat`, `ub/ebit/uai/neta` — totales ESF/ER.
- `ind(D, año)` — índices financieros.
- `computeER(D, CTRL, params)` — proyección del estado de resultados.
- `computeModel(D, CTRL, params)` — motor del pago a cuenta + crédito + roll-forward.
- `scenarioCompare(...)` / `applyScenario(...)` — comparación y armado de escenarios.

### 7.4 Esquemas de datos

- `ESF_SCHEMA` / `ER_SCHEMA` (en `seed.js` y su espejo `schema.py`) definen las filas
  de input y de cálculo. Los nombres de clave coinciden 1:1 entre frontend y backend;
  esa coincidencia es lo que hace que ingesta y exportación encajen.

---

## 8. Operación (local y producción)

### Producción
- Frontend estático apunta al backend mediante el proxy/`VITE_API_BASE`.
- El router TAX está montado en `backend/app/api/__init__.py` bajo `/api/v1`.
- **Pendiente operativo:** desplegar el backend con el módulo TAX para que la ingesta
  y exportación funcionen en producción.

### Desarrollo local
```bash
# Backend local (FastAPI + SQLite)
cd auditbrain-python-runner
CORS_ALLOW_ORIGINS="http://localhost:5173" python -m uvicorn app:app --port 8000

# Frontend apuntando al backend local (proxy de Vite)
cd frontend
VITE_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```
> En modo desarrollo, el frontend usa el **proxy de `vite.config.js`** (no
> `VITE_API_BASE`, que `.env.development` deja vacío a propósito). Por defecto el
> proxy apunta a Render; `VITE_PROXY_TARGET` lo redirige al backend local.

Dependencias backend relevantes: `fastapi`, `pdfplumber` (lectura de F-101),
`openpyxl` (lectura de plantilla y escritura del Excel con fórmulas).

---

## 9. Restricciones y validación humana

- **Tarifa, retención de dividendos, reserva legal y tasa de IR** son editables y
  **requieren validación humana**; no se presentan como cifras firmes.
- El **mapeo de casilleros F-101** se entrega con valores por defecto, pero el parser
  devuelve `casilleros_leidos` (qué leyó exactamente) y `warnings` para que el
  profesional **audite y ajuste** antes de confiar en las cifras.
- Caso particular **SIGMANSERVICES**: no recomendar capitalización vía inventarios
  (inventario sobredimensionado); preferir activos productivos/empleo.
- El runner legacy (`auditbrain_exec_runner.py`) y los endpoints legacy permanecen
  intactos; esta integración es **aditiva y reversible**.

---

## 10. Glosario rápido

| Término | Significado |
|---|---|
| ESF | Estado de Situación Financiera (balance). |
| ER | Estado de Resultados. |
| Pago a cuenta | Anticipo recuperable sobre utilidades no distribuidas. |
| Costo muerto | Pago a cuenta que queda en riesgo de no recuperarse. |
| Roll-forward | Arrastre del patrimonio/resultados acumulados año a año. |
| F-101 | Formulario 101 del SRI (Impuesto a la Renta Sociedades). |
| Celdas azules | Inputs editables; única fuente de datos del modelo. |
