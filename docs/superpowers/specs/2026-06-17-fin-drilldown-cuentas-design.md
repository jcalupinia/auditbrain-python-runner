# FIN · Detalle por cuenta + drill-down en Resumido/Detallado — Diseño

**Fecha:** 2026-06-17
**Módulo:** FIN · CFO Intelligence → Análisis Financiero Empresarial → Fase 1 (tablero ejecutivo).
**Aprobado por el usuario:** sí (alcance Balance **y** Estado de Resultados; interacción inline).

## 1. Problema
Hoy, al subir balances internos, el parser **descarta el detalle por cuenta** y solo
guarda los rubros sumados (`efectivo`, `cxc`, `ventas`…). En el tablero:
- **Detallado** muestra un detalle *sintético* (lista de rubros estándar), no las
  cuentas reales del Excel.
- **Resumido** no permite ver qué cuentas componen cada rubro.

El usuario necesita: lo subido (todas las cuentas) va al **Detallado**; el **Resumido**
muestra los rubros agrupados y, al **hacer clic** en un rubro (ej. "Efectivo y
equivalentes"), **despliega inline** las cuentas que lo componen (con saldos por año).
Aplica a **Balance** (Activo/Pasivo/Patrimonio) y a **Estado de Resultados**.

## 2. Enfoque elegido
**A · El parser etiqueta cada cuenta con su rubro.** El parser ya clasifica cada cuenta
hoja en un rubro; además devolverá la lista de cuentas con la etiqueta del rubro al que
sumó. El front las fusiona por año (igual que los totales) y la plantilla arma el
desglose. Mapeo exacto → `Σ cuentas del rubro = total del rubro` → A = P + Patrimonio
se mantiene.

(Rechazados: B árbol crudo reclasificado en el front = duplica lógica; C detallado
sintético = no permite drill-down.)

## 3. Diseño por capa

### 3.1 Backend — `parsers/balance_interno.py`
`extract_balance_interno` devuelve, además de lo actual, `detalle`: lista de cuentas
hoja, cada una:
```
{ sec: "activo"|"pasivo"|"patrimonio"|"resultado",
  key: <rubro del modelo, p.ej. "efectivo","cxc","ventas">,
  codigo: "1.1.01.02.01", nombre: "BANCO PACIFICO…", vals: [v0, v1, …] }
```
- Las cuentas hoja son las que el parser ya suma (sin hijos), con signo normalizado
  igual que el rubro (pasivo/patrimonio/costos en positivo de presentación).
- **Residual:** si `Σ cuentas(key) ≠ total(key)` (por el residual "otras" que el
  parser asigna para cuadrar), se agrega una cuenta `{codigo:"", nombre:"(otras / no
  clasificadas)", key, vals: total−Σ}` por período afectado, para que el desglose
  **siempre sume el total**.
- `_parse_balance_block` y `_parse_resultados_block` reciben/llenan una lista `detalle`
  paralela a `data`. Sin romper la firma pública (el `data` y labels actuales intactos).

### 3.2 Front — `finModel.js` + `DashboardEjecutivoTool.jsx`
- `cargarInternos` ya fusiona por año. Se extiende para fusionar también `detalle`:
  clave de cuenta = `(sec, key, codigo, nombre)`; los valores se alinean por año
  (mismo `byYear`/orden que los totales). Balance(ESF) + Resultados(ER) aportan sus
  cuentas a los mismos períodos.
- Nuevo estado `cuentas` (array fusionado). Se limpia con "Limpiar" y con `cargarEjemplo`
  (el ejemplo no trae detalle → drill-down inactivo, cae al detallado sintético).

### 3.3 Plumbing — `dashboardExport.js`
Nuevo token `__CUENTAS__` = `JSON.stringify(cuentas || [])`, inyectado en la plantilla
junto a `__BALANCE_DET__`. Igual en `buildStandaloneHTML` y `downloadStandaloneHTML`.

### 3.4 Plantilla — `dashboard_template.html`
- `const CUENTAS = __CUENTAS__;` (IIFE try/catch → `[]`).
- Índices derivados: `cuentasPorKey[key] = [cuentas…]` y `cuentasPorSec[sec][key]`.
- **Detallado** (`detTabla`): si `CUENTAS.length`, renderiza las **cuentas reales**
  agrupadas por sección → rubro → cuentas (código + nombre + saldos por año). Si no hay,
  cae al detallado actual (sintético).
- **Resumido** (`renderBalance` tabla agrupada y bloque ER en `renderResultados`):
  cada fila de rubro **con** cuentas muestra un disclosure **▸/▾**; al hacer clic
  inserta/quita filas hijas (cuentas, indentadas, saldos por año). Estado de expandido
  en memoria (`Set` de keys abiertas) + re-render del bloque, o toggle de `display` por
  CSS sobre filas pre-renderizadas ocultas (preferido: sin re-render, robusto offline).
- Aplica a **Balance** (Activo/Pasivo/Patrimonio) y **Estado de Resultados**.

## 4. Cuadratura / consistencia
`Σ cuentas(key) = total(key)` por construcción (mismas cuentas + residual). Verificación
empírica con los Excel reales del cliente (BALANCE/RESULTADOS HOTEL): cada rubro
expandido debe sumar su total, y A = P + Patrimonio seguir en 0.

## 5. Fuera de alcance (YAGNI)
- Editar cuentas individuales del detalle (el detalle es de solo lectura).
- Drill-down para fuentes sin detalle (F-101 PDF, carga manual) → usan el detallado
  sintético actual.

## 6. Verificación
1. Parser sobre BALANCE/RESULTADOS HOTEL → `detalle` no vacío; `Σ cuentas(key)=total(key)`.
2. Fusión front (simulada) → cuentas alineadas a 3 períodos; Balance+ER combinados.
3. `npm run build` exit 0; CI (pytest + Playwright) verde.
4. En la app: subir los 2 Excel → Detallado muestra cuentas reales; en Resumido,
   clic en "Efectivo y equivalentes" despliega BANCOS/CAJA…; A=P+Patrimonio cuadra.
