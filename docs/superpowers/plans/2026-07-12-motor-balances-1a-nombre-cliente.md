# Motor de Balances · Fase 1a — Nombre del cliente + Super Cías visible · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la balanza homologada del portal Flujo capture y muestre el **nombre de la cuenta del cliente** junto al código, con el **Código Super Cías visible** (sin cortarse), sin romper el flujo 2-períodos existente.

**Architecture:** Se extiende la ficha de balanza de `{cuenta, super_cias, sri, saldo}` a `{cuenta, nombre, super_cias, sri, saldo}` en el parser; `previews._fila_map` agrega la columna Nombre; el `BalanzasEditor` muestra código + nombre en la primera columna y conserva `nombre` en el round-trip de recálculo. El `nombre` es solo presentación — no entra a ningún cálculo (`homologar_balanza` sigue usando `super_cias`/`saldo`).

**Tech Stack:** Python 3.13, openpyxl, pytest (backend); React (frontend `frontend-client`); sin cambios de dependencias.

**Fuente de diseño:** `docs/superpowers/specs/2026-07-12-motor-balances-homologacion-design.md` (§5a, §6).

---

## File Structure

- `backend/app/client_portal/flujo/parser.py` — MODIFICAR: detectar y capturar `nombre`.
- `backend/app/client_portal/flujo/previews.py` — MODIFICAR: `_fila_map` incluye `nombre`; cols MAP/MAP_ANT.
- `frontend-client/src/flujo/BalanzasEditor.jsx` — MODIFICAR: `fusionar`, `construir`, y la celda "Cuenta contable" (código + nombre); Super Cías visible.
- `tests/test_flujo_parser.py` — MODIFICAR: actualizar aserción de igualdad exacta + test de `nombre`.
- `tests/test_flujo_previews_nombre.py` — CREAR: `construir_previews` expone `nombre` en MAP.

No se toca `processor.py`: `recalcular_desde_balanzas` pasa las fichas tal cual a `generar_excel`/`construir_previews`, así que `nombre` viaja sin cambios (los motores lo ignoran).

---

### Task 1: parser.py captura el nombre de la cuenta del cliente

**Files:**
- Modify: `backend/app/client_portal/flujo/parser.py:13-18` (`_CLAVES`) y `parser.py:94-99` (dict de salida en `_leer_filas`)
- Test: `tests/test_flujo_parser.py:20-29` (actualizar) y nuevo test

- [ ] **Step 1: Actualizar el test existente y agregar el test de `nombre`**

En `tests/test_flujo_parser.py`, reemplazar `test_parse_balanza_detecta_columnas_por_encabezado` (líneas 20-29) por:

```python
def test_parse_balanza_detecta_columnas_por_encabezado():
    data = _wb_bytes([
        ("1.01.01.01", "Caja", "1010101", "311", 1000.0),
        ("2.01.03.01", "Proveedores", "2010301", "413", -500.0),
    ])
    filas = parser.parse_balanza(data)
    assert len(filas) == 2
    assert filas[0] == {"cuenta": "1.01.01.01", "nombre": "Caja",
                        "super_cias": "1010101", "sri": "311", "saldo": 1000.0}
    assert filas[1]["saldo"] == -500.0
    assert filas[1]["nombre"] == "Proveedores"


def test_parse_balanza_captura_nombre_del_cliente():
    data = _wb_bytes([
        ("1.01.01.02.001", "Produbanco Quito 02005093682", "1010103", "311", 351257.23),
    ])
    filas = parser.parse_balanza(data)
    assert filas[0]["nombre"] == "Produbanco Quito 02005093682"


def test_parse_balanza_nombre_vacio_si_no_hay_columna():
    # Encabezados sin descripción/nombre: nombre debe quedar "" (no romper)
    data = _wb_bytes(
        [("1.01", "1010101", "311", 10.0)],
        headers=("Cod.Cuenta.Contable", "CODIFO SUPER CIAS", "Códigos SRI", "Saldo"),
    )
    filas = parser.parse_balanza(data)
    assert filas[0]["nombre"] == ""
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_flujo_parser.py -q`
Expected: FAIL — `test_parse_balanza_detecta_columnas_por_encabezado` (falta `nombre` en el dict) y `test_parse_balanza_captura_nombre_del_cliente` (KeyError/`""`).

- [ ] **Step 3: Agregar la clave `nombre` a `_CLAVES`**

En `parser.py`, reemplazar el dict `_CLAVES` (líneas 13-18) por:

```python
_CLAVES = {
    "cuenta": ("cuenta", "cta", "cod.cuenta", "codigo cuenta", "cod cuenta"),
    "nombre": ("descrip", "nombre", "detalle", "concepto"),
    "super_cias": ("super", "supercias", "super cias"),
    "sri": ("sri",),
    "saldo": ("saldo", "31 dic", "valor"),
}
```

- [ ] **Step 4: Agregar `nombre` al dict de salida de `_leer_filas`**

En `parser.py`, en `_leer_filas`, reemplazar el `out.append({...})` (líneas 94-99) por:

```python
        out.append({
            "cuenta": str(fila[col["cuenta"]]).strip() if "cuenta" in col and fila[col["cuenta"]] is not None else "",
            "nombre": str(fila[col["nombre"]]).strip() if "nombre" in col and fila[col["nombre"]] is not None else "",
            "super_cias": sc,
            "sri": str(fila[col["sri"]]).strip() if "sri" in col and fila[col["sri"]] is not None else "",
            "saldo": saldo,
        })
```

Nota: `_leer_filas` usa `imax = max(col.values())`; al agregar `nombre` la fila debe tener suficientes columnas — ya se cubre porque `nombre` va entre `cuenta` y `super_cias`.

- [ ] **Step 5: Correr los tests para verificar que pasan**

Run: `python -m pytest tests/test_flujo_parser.py -q`
Expected: PASS (todos, incluidos los 3 nuevos/actualizados y los 2 preexistentes de saldo).

- [ ] **Step 6: Commit**

```bash
git add backend/app/client_portal/flujo/parser.py tests/test_flujo_parser.py
git commit -m "feat(flujo): parser captura el nombre de la cuenta del cliente"
```

---

### Task 2: previews.py expone el nombre en la Homologación (MAP)

**Files:**
- Modify: `backend/app/client_portal/flujo/previews.py:231-238` (`_fila_map` y cols MAP/MAP_ANT)
- Test: `tests/test_flujo_previews_nombre.py` (crear)

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_flujo_previews_nombre.py`:

```python
from backend.app.client_portal.flujo import previews


def test_map_incluye_columna_nombre():
    bal = [{"cuenta": "1.01.01.02.001", "nombre": "Produbanco Quito",
            "super_cias": "1010103", "sri": "311", "saldo": 351257.23}]
    prev = previews.construir_previews(bal, bal)
    assert prev["MAP"]["cols"] == ["Cuenta", "Nombre", "Super Cías", "SRI", "Saldo"]
    fila = prev["MAP"]["rows"][0]
    assert fila[0] == "1.01.01.02.001"
    assert fila[1] == "Produbanco Quito"
    assert fila[2] == "1010103"
    assert fila[3] == "311"


def test_map_nombre_vacio_no_rompe():
    bal = [{"cuenta": "1.01", "super_cias": "1010101", "sri": "311", "saldo": 10.0}]
    prev = previews.construir_previews(bal, bal)
    assert prev["MAP"]["rows"][0][1] == ""
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_flujo_previews_nombre.py -q`
Expected: FAIL — `cols` es `["Cuenta", "Super Cías", "SRI", "Saldo"]` (sin "Nombre") y la fila no tiene el nombre en el índice 1.

- [ ] **Step 3: Actualizar `_fila_map` y las columnas MAP/MAP_ANT**

En `previews.py`, reemplazar el bloque "Homologación (Mapeo)" (líneas 231-238) por:

```python
    # ---- Homologación (Mapeo) ----
    def _fila_map(f):
        return [str(f.get("cuenta") or ""), str(f.get("nombre") or ""),
                f.get("super_cias", ""), f.get("sri", ""), _r(f.get("saldo"))]
    rows = [_fila_map(f) for f in bal_act]
    rows_ant = [_fila_map(f) for f in bal_ant]
    _cols_map = ["Cuenta", "Nombre", "Super Cías", "SRI", "Saldo"]
    prev["MAP"] = {"cols": _cols_map, "rows": rows}
    prev["MAP_ANT"] = {"cols": _cols_map, "rows": rows_ant}
    prev["WP_MAP"] = {"rows": rows}
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_flujo_previews_nombre.py -q`
Expected: PASS (los 2 tests).

- [ ] **Step 5: Correr la suite de flujo para no-regresión**

Run: `python -m pytest tests/ -k flujo -q`
Expected: PASS — ninguna regresión (los motores no leen `nombre`; solo cambió la forma de la fila MAP).

- [ ] **Step 6: Commit**

```bash
git add backend/app/client_portal/flujo/previews.py tests/test_flujo_previews_nombre.py
git commit -m "feat(flujo): previews MAP expone el nombre de la cuenta del cliente"
```

---

### Task 3: BalanzasEditor muestra código + nombre y conserva `nombre` en el recálculo

**Files:**
- Modify: `frontend-client/src/flujo/BalanzasEditor.jsx:24-39` (`fusionar`), `:78-89` (`construir`), `:150-175` (comentario y celda de la cuenta), `:107` (filtro)

Nota: la fila MAP ahora es `[cuenta, nombre, super_cias, sri, saldo]` (índices corridos +1 desde `super_cias`). `fusionar` y `construir` deben usar los nuevos índices.

- [ ] **Step 1: Actualizar `fusionar` para leer los nuevos índices y llevar `nombre`**

En `BalanzasEditor.jsx`, reemplazar `fusionar` (líneas 24-39) por:

```javascript
// Une ambas balanzas por cuenta (código contable completo, único).
// Fila de entrada: [cuenta, nombre, super_cias, sri, saldo].
function fusionar(rowsAnt, rowsAct) {
  const idx = new Map();
  const push = (r, col) => {
    const cuenta = String(r[0] || "");
    const nombre = String(r[1] || "");
    const key = cuenta || `${r[2]}·${col}`;
    if (!idx.has(key)) idx.set(key, { cuenta, nombre, super_cias: r[2] || "", sri: r[3] || "", ant: "", act: "" });
    const o = idx.get(key);
    o[col] = r[4];
    if (!o.super_cias) o.super_cias = r[2] || "";
    if (!o.sri) o.sri = r[3] || "";
    if (!o.nombre) o.nombre = nombre;
  };
  (rowsAnt || []).forEach((r) => push(r, "ant"));
  (rowsAct || []).forEach((r) => push(r, "act"));
  return Array.from(idx.values());
}
```

- [ ] **Step 2: Conservar `nombre` en `construir` (round-trip del recálculo)**

En `BalanzasEditor.jsx`, dentro de `construir` (líneas 78-89), reemplazar la línea del `meta`:

```javascript
      const meta = { cuenta: row.cuenta, super_cias: String(valSuper(i) || ""), sri: String(valSri(i) || "") };
```

por:

```javascript
      const meta = { cuenta: row.cuenta, nombre: row.nombre, super_cias: String(valSuper(i) || ""), sri: String(valSri(i) || "") };
```

- [ ] **Step 3: Incluir el nombre en el filtro de búsqueda**

En `BalanzasEditor.jsx`, en el `useMemo` de `filas` (línea 107), reemplazar:

```javascript
      .filter(([r]) => `${r.cuenta} ${r.super_cias} ${r.sri}`.toLowerCase().includes(q));
```

por:

```javascript
      .filter(([r]) => `${r.cuenta} ${r.nombre} ${r.super_cias} ${r.sri}`.toLowerCase().includes(q));
```

- [ ] **Step 4: Mostrar código + nombre en la primera columna**

En `BalanzasEditor.jsx`, reemplazar la celda de la cuenta (línea 165):

```javascript
                  <td className="c1">{r.cuenta}</td>
```

por:

```javascript
                  <td className="c1" title={`${r.cuenta} · ${r.nombre}`}>
                    <span className="fx-ht-cod-cli">{r.cuenta}</span>
                    <span className="fx-ht-nom">{r.nombre}</span>
                  </td>
```

- [ ] **Step 5: Estilo del código de cliente (que no rompa el sticky ni corte el Super Cías)**

En `frontend-client/src/flujo/flujo.css`, agregar al final:

```css
.fx3d .fx-ht-cod-cli { display: block; font: 700 11.5px var(--mono); color: var(--text); }
.fx3d .fx-ht-tbl td.c1 { white-space: normal; line-height: 1.25; vertical-align: top; }
```

(La clase `.fx-ht-nom` ya existe — muestra el nombre en gris pequeño debajo del código.)

- [ ] **Step 6: Verificar en el editor (no hay harness de tests JS en este módulo)**

Arrancar el portal cliente y abrir la herramienta Flujo de Efectivo con una balanza real (SIGMAN):
1. Subir balanza anterior + actual, Procesar.
2. Abrir la sección **6 · Balanzas (editable)**.
3. Confirmar en cada fila: se ve **código (negrita) + nombre de la cuenta del cliente** en la primera columna, y las columnas **Super Cías** y **SRI** (código + nombre NIIF) quedan **visibles** sin cortarse.
4. Editar un código Super Cías y confirmar que **recalcula** y el nombre del cliente **no desaparece** tras el recálculo (viaja en `construir`).

Capturar screenshot de la grilla como evidencia.

- [ ] **Step 7: Commit**

```bash
git add frontend-client/src/flujo/BalanzasEditor.jsx frontend-client/src/flujo/flujo.css
git commit -m "feat(flujo): BalanzasEditor muestra nombre del cliente y conserva el nombre al recalcular"
```

---

## Verificación final (REGLA SUPREMA — antes de decir "listo")

- [ ] `python -m pytest tests/ -k flujo -q` en **verde** (parser, previews, y no-regresión del generador/processor 2-períodos).
- [ ] Evidencia visual: screenshot del `BalanzasEditor` con **código + nombre del cliente** y **Super Cías visible**, usando datos reales de SIGMAN.
- [ ] Confirmar que editar un código **recalcula** y el nombre **persiste** tras el recálculo.

## Fuera de alcance de este plan (van en 1b y 1c)

- `parse_balanza_multiperiodo`, `motor_balances.py`, endpoint AUD, catálogo del plan → **Plan 1b**.
- Nueva herramienta AUD (UI multi-período + secciones Superintendencia, N columnas en `generador._hoja_estructura`) → **Plan 1c**.
- Homologación de huérfanas con desplegables enlazados (picklist del plan) → **Plan 1c** (usa el catálogo del 1b).
