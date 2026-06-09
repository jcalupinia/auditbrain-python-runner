# Auto-llenado "Información contable" A4/A5/A9 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trasladar con fórmulas vivas el lado "Información contable" (valor en libros / costo total + código de cuenta) de los anexos A9, A4 y A5 del ICT, relacionando por casillero tributario contra `DATOS BALANCE`.

**Architecture:** Dos helpers nuevos en `referential_helpers.py` (referencia de código de cuenta y fórmula reactiva SUMIF). El filler A9 usa la infraestructura existente `balance_rows_for_casillero` + `balance_sum_ref(take_abs)` para casilleros fijos. Los fillers A4/A5 colocan una fórmula reactiva `IF(B="","",ABS(SUMIF(...)))` en las filas del cuadro de detalle que no se pre-llenaron, para que se complete sola cuando el auditor escriba el casillero.

**Tech Stack:** Python 3.13, openpyxl, pytest. Fórmulas Excel escritas en inglés con coma (`SUMIF`, `IF`, `ABS`, `TEXTJOIN`) — Excel las muestra como `SUMAR.SI`, `SI`, `UNIRCADENAS` en español.

**Spec de referencia:** `docs/superpowers/specs/2026-06-08-info-contable-a4-a5-a9-design.md`

---

## File Structure

- **Modify** `backend/app/ict/fillers/referential_helpers.py` — agregar `balance_codigo_ref()` y `libros_sumif_reactivo_formula()`.
- **Modify** `backend/app/ict/fillers/a9_inventarios.py` — col G (Costo Total, ABS), col D (código), corregir diferencia H18/H19/H22.
- **Modify** `backend/app/ict/fillers/a4_conciliacion_ingresos.py` — fórmula reactiva en filas vacías del Cuadro 1 (col G).
- **Modify** `backend/app/ict/fillers/a5_conciliacion_costos.py` — fórmula reactiva en filas vacías del Cuadro A (col K).
- **Modify** `tests/test_ict_fillers_a9.py` — actualizar test del warning de Kardex.
- **Create** `tests/test_ict_info_contable.py` — tests de los 2 helpers + fillers con balance simulado.
- **Verify** integración: regenerar PROPHAR y confirmar cuadre A9 = 0.00.

**Datos verificados (PROPHAR, 2026-06-08):**
- `DATOS BALANCE`: col A = Casillero SRI (repetido por fila), col B = Código Contable, col C = Nombre, col D = Saldo. Datos desde fila 4.
- A9 plantilla: col H ya es `=G-C` en filas 20,21,23,24,25,26; **H18, H19, H22 = 0 hardcoded** (corregir).
- Inventarios finales en el balance tienen saldo negativo (`"(-) Inventario final…"`); por eso Costo Total usa `ABS` salvo 7037 (ajustes).

---

## Task 1: Helper `balance_codigo_ref` (código de cuenta, col B)

**Files:**
- Modify: `backend/app/ict/fillers/referential_helpers.py` (agregar tras `balance_sum_ref`, ~línea 107)
- Test: `tests/test_ict_info_contable.py` (crear)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ict_info_contable.py
"""Tests de los helpers de Información contable (A4/A5/A9) y su uso en fillers."""

from backend.app.ict.fillers.referential_helpers import (
    balance_codigo_ref,
    libros_sumif_reactivo_formula,
)


def test_balance_codigo_ref_una_cuenta():
    assert balance_codigo_ref([5]) == "='DATOS BALANCE'!B5"


def test_balance_codigo_ref_varias_cuentas_separa_con_barra():
    f = balance_codigo_ref([5, 7])
    assert f == '=TEXTJOIN(" / ",TRUE,\'DATOS BALANCE\'!B5,\'DATOS BALANCE\'!B7)'


def test_balance_codigo_ref_sin_cuentas_devuelve_none():
    assert balance_codigo_ref([]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_info_contable.py::test_balance_codigo_ref_una_cuenta -v`
Expected: FAIL with `ImportError: cannot import name 'balance_codigo_ref'`

- [ ] **Step 3: Write minimal implementation**

En `referential_helpers.py`, agregar tras la función `balance_sum_ref` (después de la línea 106):

```python
def balance_codigo_ref(rows_in_balance_sheet: list[int], column: str = "B",
                       sep: str = " / ") -> str | None:
    """Fórmula que trae el/los código(s) de cuenta contable (texto, col B de
    DATOS BALANCE) de las filas dadas.

      [5]      → ='DATOS BALANCE'!B5
      [5, 7]   → =TEXTJOIN(" / ",TRUE,'DATOS BALANCE'!B5,'DATOS BALANCE'!B7)
      []       → None
    """
    if not rows_in_balance_sheet:
        return None
    refs = [f"'{SHEET_BALANCE}'!{column}{r}" for r in rows_in_balance_sheet]
    if len(refs) == 1:
        return f"={refs[0]}"
    joined = ",".join(refs)
    return f'=TEXTJOIN("{sep}",TRUE,{joined})'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_info_contable.py -k balance_codigo_ref -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/ict/fillers/referential_helpers.py tests/test_ict_info_contable.py
git commit -m "feat(ict): helper balance_codigo_ref para código de cuenta en info contable

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Helper `libros_sumif_reactivo_formula` (fórmula reactiva A4/A5)

**Files:**
- Modify: `backend/app/ict/fillers/referential_helpers.py` (agregar tras `balance_codigo_ref`)
- Test: `tests/test_ict_info_contable.py`

- [ ] **Step 1: Write the failing test**

```python
def test_libros_sumif_reactivo_con_abs():
    f = libros_sumif_reactivo_formula("$B17")
    assert f == ('=IF($B17="","",ABS(SUMIF(\'DATOS BALANCE\'!$A:$A,$B17,'
                 '\'DATOS BALANCE\'!$D:$D)))')


def test_libros_sumif_reactivo_sin_abs():
    f = libros_sumif_reactivo_formula("$B17", take_abs=False)
    assert f == ('=IF($B17="","",SUMIF(\'DATOS BALANCE\'!$A:$A,$B17,'
                 '\'DATOS BALANCE\'!$D:$D))')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_info_contable.py -k reactivo -v`
Expected: FAIL with `ImportError: cannot import name 'libros_sumif_reactivo_formula'`

- [ ] **Step 3: Write minimal implementation**

En `referential_helpers.py`, agregar tras `balance_codigo_ref`:

```python
def libros_sumif_reactivo_formula(casillero_cell: str, *,
                                  take_abs: bool = True) -> str:
    """Fórmula REACTIVA para la columna 'valor en libros' de A4/A5: cuando el
    auditor escribe el casillero en ``casillero_cell`` (ej. '$B17'), suma en
    DATOS BALANCE todas las cuentas con ese casillero. Vacía si la celda lo está.

      $B17 → =IF($B17="","",ABS(SUMIF('DATOS BALANCE'!$A:$A,$B17,'DATOS BALANCE'!$D:$D)))
    """
    inner = (f"SUMIF('{SHEET_BALANCE}'!$A:$A,{casillero_cell},"
             f"'{SHEET_BALANCE}'!$D:$D)")
    if take_abs:
        inner = f"ABS({inner})"
    return f'=IF({casillero_cell}="","",{inner})'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_info_contable.py -k reactivo -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/ict/fillers/referential_helpers.py tests/test_ict_info_contable.py
git commit -m "feat(ict): helper libros_sumif_reactivo_formula para valor en libros A4/A5

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: A9 — Costo Total (col G) con ABS por casillero

**Files:**
- Modify: `backend/app/ict/fillers/a9_inventarios.py`
- Test: `tests/test_ict_info_contable.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a9_inventarios import A9Filler


def _a9_session():
    return {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025",
            "numero_adhesivo": ""}


def test_a9_costo_total_inventario_final_usa_abs():
    """7022 (inv. final) tiene saldo negativo en balance → Costo Total con ABS."""
    wb = load_template()
    anexo_data = {
        "balance_mapeado": [
            {"casillero_sri": "7022", "codigo": "5PYG.53602.017",
             "descripcion": "(-) Inventario final de materia prima",
             "saldo": -930768.56},
        ],
        "_balance_lookup": [5],   # la cuenta está en DATOS BALANCE fila 5
    }
    A9Filler().fill(wb, _a9_session(), anexo_data)
    ws = wb["INVENTARIOS A9"]
    assert ws["G21"].value == "=ABS('DATOS BALANCE'!D5)"   # fila 21 = cas 7022


def test_a9_costo_total_ajustes_7037_respeta_signo():
    """7037 (ajustes) NO usa ABS — mantiene el signo del balance."""
    wb = load_template()
    anexo_data = {
        "balance_mapeado": [
            {"casillero_sri": "7037", "codigo": "5PYG.53602.017",
             "descripcion": "(+/-) Ajustes", "saldo": -223636.86},
        ],
        "_balance_lookup": [9],
    }
    A9Filler().fill(wb, _a9_session(), anexo_data)
    ws = wb["INVENTARIOS A9"]
    assert ws["G26"].value == "='DATOS BALANCE'!D9"        # fila 26 = cas 7037, sin ABS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_info_contable.py -k "a9_costo_total" -v`
Expected: FAIL — `ws["G21"].value` es `None` (el filler aún no escribe col G desde el balance)

- [ ] **Step 3: Write minimal implementation**

En `a9_inventarios.py`, actualizar imports (líneas 16-20):

```python
from backend.app.ict.fillers.base import safe_set, safe_set_formula
from backend.app.ict.fillers.referential_helpers import (
    lookups_from_context,
    set_casillero_ref,
    balance_rows_for_casillero,
    balance_sum_ref,
    balance_codigo_ref,
)
```

Dentro del `for row_idx, casillero in A9_CASILLEROS.items():`, justo después del bloque que escribe col C (después de la línea 65, el `else: warnings.append(...)`), agregar:

```python
            # ── Información contable (col D código, col G costo total) ─────
            rows_bal = balance_rows_for_casillero(
                anexo_data, str(casillero), balance_lookup
            )
            # Col G (Costo Total): ABS para saldos de inventario; 7037 (ajustes)
            # mantiene signo (validado contra PROPHAR — ver spec).
            take_abs = str(casillero) != "7037"
            g_formula = balance_sum_ref(rows_bal, column="D", take_abs=take_abs)
            if g_formula and safe_set_formula(
                ws, f"G{row_idx}", g_formula, anexo="A9", casillero=str(casillero),
                origen=f"A9 fila {row_idx} · Costo Total (balance, "
                       f"{'ABS' if take_abs else 'signo directo'})",
            ):
                filled += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_info_contable.py -k "a9_costo_total" -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/ict/fillers/a9_inventarios.py tests/test_ict_info_contable.py
git commit -m "feat(ict): A9 Costo Total (col G) desde balance con ABS (signo directo en 7037)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: A9 — código de cuenta (col D), diferencia (col H) y test de Kardex

**Files:**
- Modify: `backend/app/ict/fillers/a9_inventarios.py`
- Modify: `tests/test_ict_fillers_a9.py`
- Test: `tests/test_ict_info_contable.py`

- [ ] **Step 1: Write the failing test**

En `tests/test_ict_info_contable.py`:

```python
def test_a9_codigo_cuenta_col_d_es_referencia():
    wb = load_template()
    anexo_data = {
        "balance_mapeado": [
            {"casillero_sri": "7013", "codigo": "5PYG.53602.017",
             "descripcion": "Inventario inicial de materia prima",
             "saldo": 1018613.72},
        ],
        "_balance_lookup": [4],
    }
    A9Filler().fill(wb, _a9_session(), anexo_data)
    ws = wb["INVENTARIOS A9"]
    assert ws["D20"].value == "='DATOS BALANCE'!B4"   # fila 20 = cas 7013
    # diferencia col H = G-C (fila 20 ya es fórmula en plantilla)
    assert ws["H20"].value == "=G20-C20"


def test_a9_diferencia_h22_corregida_a_formula():
    """H22 (cas 7025) estaba hardcodeada en 0 en la plantilla → debe ser =G22-C22."""
    wb = load_template()
    A9Filler().fill(wb, _a9_session(), {"balance_mapeado": [], "_balance_lookup": []})
    ws = wb["INVENTARIOS A9"]
    assert ws["H22"].value == "=G22-C22"
    assert ws["H18"].value == "=G18-C18"
    assert ws["H19"].value == "=G19-C19"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_info_contable.py -k "a9_codigo or a9_diferencia" -v`
Expected: FAIL — `ws["D20"].value` es `None`; `ws["H22"].value` es `0`

- [ ] **Step 3: Write minimal implementation**

En `a9_inventarios.py`, dentro del mismo loop, justo después del bloque de col G agregado en Task 3, añadir:

```python
            # Col D (código de cuenta, al máximo detalle): referencia(s) al balance
            d_formula = balance_codigo_ref(rows_bal, column="B")
            if d_formula and safe_set_formula(
                ws, f"D{row_idx}", d_formula, anexo="A9", casillero=str(casillero),
                origen=f"A9 fila {row_idx} · código de cuenta (balance)",
            ):
                filled += 1

            # Col H (diferencia): la plantilla deja H18/H19/H22 en 0 hardcoded;
            # uniformizar a =G-C para que el cuadre sea consistente en todas las filas.
            safe_set_formula(
                ws, f"H{row_idx}", f"=G{row_idx}-C{row_idx}",
                anexo="A9", casillero=str(casillero),
                origen=f"A9 fila {row_idx} · diferencia costo - declarado",
            )
```

Además, en el bloque del Kardex (líneas ~68-81 originales), **quitar** la escritura de `D{row_idx}` y `G{row_idx}` desde el kardex (ahora vienen del balance). El bloque del kardex queda solo con E (forma valoración) y F (cantidad):

```python
            # Cols E-F: del Kardex (literal) si el cliente lo subió.
            # D (código) y G (costo total) ya vienen del balance (arriba).
            if kardex_items:
                first_match = kardex_items[0]
                if _safe_set(ws, f"E{row_idx}", first_match.get("forma_valoracion", "PROMEDIO")):
                    filled += 1
                if _safe_set(ws, f"F{row_idx}", first_match.get("cantidad", "")):
                    filled += 1
```

- [ ] **Step 4: Update the existing Kardex warning test**

En `tests/test_ict_fillers_a9.py`, reemplazar `test_a9_filler_warns_when_kardex_missing_and_valor_exists` por una versión coherente con el nuevo flujo (el Costo Total ya no depende del Kardex):

```python
def test_a9_filler_warns_when_no_source_for_casillero():
    """Sin F-101 ni balance para un casillero con concepto, se emite warning."""
    wb = load_template()
    filler = A9Filler()
    session_data = {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    anexo_data = {"f101": {}, "balance_mapeado": [], "_balance_lookup": [], "kardex_items": []}
    result = filler.fill(wb, session_data, anexo_data)
    assert any("no detectado" in w.lower() or "no se subió" in w.lower()
               for w in result["warnings"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_ict_info_contable.py tests/test_ict_fillers_a9.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/ict/fillers/a9_inventarios.py tests/test_ict_info_contable.py tests/test_ict_fillers_a9.py
git commit -m "feat(ict): A9 código de cuenta (col D) + corrige diferencia H18/H19/H22 hardcodeada

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: A4 — fórmula reactiva en filas vacías del Cuadro 1

**Files:**
- Modify: `backend/app/ict/fillers/a4_conciliacion_ingresos.py`
- Test: `tests/test_ict_info_contable.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.app.ict.fillers.a4_conciliacion_ingresos import A4Filler


def test_a4_cuadro1_filas_vacias_tienen_formula_reactiva():
    """Sin cuentas exentas pre-llenadas, cada fila del Cuadro 1 lleva una
    fórmula reactiva al casillero (col B) en la col G (valor en libros)."""
    wb = load_template()
    session = {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    A4Filler().fill(wb, session, {"mayor_exentos": [], "balance_mapeado": []})
    ws = wb["CONCILIACIÓN INGRESOS A4"]
    # fila 16 = primera fila del Cuadro 1 (A4_CUADRO1_RANGE=(16,25))
    assert ws["G16"].value == ('=IF($B16="","",ABS(SUMIF(\'DATOS BALANCE\'!$A:$A,'
                               '$B16,\'DATOS BALANCE\'!$D:$D)))')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_info_contable.py -k a4_cuadro1 -v`
Expected: FAIL — `ws["G16"].value` es `None`

- [ ] **Step 3: Write minimal implementation**

En `a4_conciliacion_ingresos.py`:

1. Añadir al import de `referential_helpers` (líneas 28-32) la función:

```python
from backend.app.ict.fillers.referential_helpers import (
    lookups_from_context,
    set_balance_item_ref,
    set_casillero_ref,
    libros_sumif_reactivo_formula,
)
```

2. Añadir el import de `safe_set_formula`:

```python
from backend.app.ict.fillers.base import safe_set, safe_set_formula
```

3. Justo **antes** del comentario `# ── Cuadro 2:` (línea 131), agregar:

```python
        # Filas del Cuadro 1 SIN pre-llenado: fórmula reactiva al casillero (col B).
        # Cuando el auditor escribe el Nº de casillero, el valor en libros (col G)
        # se calcula solo sumando DATOS BALANCE por ese casillero.
        num_prellenadas = min(len(balance_indexed), max_rows) if balance_indexed else 0
        col_b_a4 = A4_CUADRO1_COLS["casillero"]
        col_g_a4 = A4_CUADRO1_COLS["valor"]
        for row in range(start_row + num_prellenadas, end_row + 1):
            formula = libros_sumif_reactivo_formula(f"${col_b_a4}{row}", take_abs=True)
            if safe_set_formula(
                ws, f"{col_g_a4}{row}", formula, anexo="A4",
                origen="A4 Cuadro 1 · valor en libros reactivo al casillero",
            ):
                filled += 1
```

> Nota: `balance_indexed`, `max_rows`, `start_row`, `end_row` ya existen en el scope
> (definidos en el bloque del Cuadro 1, líneas 63-84).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_info_contable.py -k a4_cuadro1 -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/ict/fillers/a4_conciliacion_ingresos.py tests/test_ict_info_contable.py
git commit -m "feat(ict): A4 Cuadro 1 valor en libros reactivo al casillero (col G)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: A5 — fórmula reactiva en filas vacías del Cuadro A

**Files:**
- Modify: `backend/app/ict/fillers/a5_conciliacion_costos.py`
- Test: `tests/test_ict_info_contable.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.app.ict.fillers.a5_conciliacion_costos import A5Filler


def test_a5_cuadro_a_filas_vacias_tienen_formula_reactiva():
    wb = load_template()
    session = {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    A5Filler().fill(wb, session, {"mayor_no_deducibles": [], "balance_mapeado": []})
    ws = wb["CONCILIACIÓN COSTOS Y GASTOS A5"]
    # fila 17 = primera fila del Cuadro A (A5_CUADRO_A_RANGE=(17,21)); valor en col K
    assert ws["K17"].value == ('=IF($B17="","",ABS(SUMIF(\'DATOS BALANCE\'!$A:$A,'
                               '$B17,\'DATOS BALANCE\'!$D:$D)))')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_info_contable.py -k a5_cuadro_a -v`
Expected: FAIL — `ws["K17"].value` es `None`

- [ ] **Step 3: Write minimal implementation**

En `a5_conciliacion_costos.py`:

1. Añadir al import de `referential_helpers` (líneas 27-31):

```python
from backend.app.ict.fillers.referential_helpers import (
    lookups_from_context,
    set_balance_item_ref,
    set_casillero_ref,
    libros_sumif_reactivo_formula,
)
```

2. Añadir el import de `safe_set_formula`:

```python
from backend.app.ict.fillers.base import safe_set, safe_set_formula
```

3. Justo **antes** del comentario `# ── Cuadro B:` (línea 122), agregar:

```python
        # Filas del Cuadro A SIN pre-llenado: fórmula reactiva al casillero (col B).
        # La col B (Nº casillero) la escribe el auditor; al hacerlo, el valor en
        # libros (col K) se calcula solo sumando DATOS BALANCE por ese casillero.
        num_prellenadas_a = min(len(items_indexed), max_rows_a) if items_indexed else 0
        col_k_a5 = A5_CUADRO_A_COLS["valor"]
        for row in range(start_a + num_prellenadas_a, end_a + 1):
            formula = libros_sumif_reactivo_formula(f"$B{row}", take_abs=True)
            if safe_set_formula(
                ws, f"{col_k_a5}{row}", formula, anexo="A5",
                origen="A5 Cuadro A · valor en libros reactivo al casillero",
            ):
                filled += 1
```

> Nota: `items_indexed`, `max_rows_a`, `start_a`, `end_a` ya existen en el scope
> (definidos en el bloque del Cuadro A, líneas 63-80). La col B del casillero es
> literal `"B"` (no está en `A5_CUADRO_A_COLS`, que solo mapea las que el filler
> escribe).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_info_contable.py -k a5_cuadro_a -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/ict/fillers/a5_conciliacion_costos.py tests/test_ict_info_contable.py
git commit -m "feat(ict): A5 Cuadro A valor en libros reactivo al casillero (col K)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Verificación empírica (cuadre PROPHAR + suite + Excel sano)

**Files:**
- Test: `tests/test_ict_info_contable.py` (test de cuadre con datos PROPHAR si el fixture está disponible)

- [ ] **Step 1: Regenerar el ICT de PROPHAR**

Run: `python scripts/generate_ict15_prophar.py`
Expected: genera `audit_artifacts/ict15_papel_trabajo.xlsx` sin error.

- [ ] **Step 2: Escribir el test de cuadre A9 (skip si no hay artefacto)**

```python
import os
import pytest
from openpyxl import load_workbook

ARTIFACT = r"audit_artifacts/ict15_papel_trabajo.xlsx"


@pytest.mark.skipif(not os.path.exists(ARTIFACT),
                    reason="requiere ICT15 PROPHAR regenerado")
def test_a9_cuadre_prophar_cero_diferencias():
    """En PROPHAR, el inventario contable (col G, ABS) cuadra con lo declarado:
    todas las diferencias = 0 una vez resueltas las fórmulas."""
    wb = load_workbook(ARTIFACT, data_only=False)
    db = wb["DATOS BALANCE"]
    suma = {}
    for r in range(4, db.max_row + 1):
        c = db.cell(r, 1).value
        if c is None:
            continue
        c = str(c).strip()
        s = db.cell(r, 4).value or 0
        suma[c] = suma.get(c, 0) + (s if isinstance(s, (int, float)) else 0)
    f1 = wb["DATOS F-101"]
    dec = {}
    for r in range(1, f1.max_row + 1):
        v = f1.cell(r, 1).value
        if v:
            dec[str(v).strip()] = f1.cell(r, 3).value
    for cas in ["7013", "7022", "7025", "7028", "7031", "7034", "7037"]:
        d = dec.get(cas) or 0
        g = suma.get(cas, 0)
        g = g if cas == "7037" else abs(g)
        assert abs(g - (d if isinstance(d, (int, float)) else 0)) < 0.01, \
            f"cas {cas}: costo {g} != declarado {d}"
```

Run: `python -m pytest tests/test_ict_info_contable.py::test_a9_cuadre_prophar_cero_diferencias -v`
Expected: PASS (o SKIP si no hay artefacto).

- [ ] **Step 3: Verificar que el Excel NO se rompe (regla CLAUDE.md)**

Run:
```bash
python -c "from openpyxl import load_workbook; wb=load_workbook(r'audit_artifacts/ict15_papel_trabajo.xlsx'); [print('OK', s) for s in ['INVENTARIOS A9','CONCILIACIÓN INGRESOS A4','CONCILIACIÓN COSTOS Y GASTOS A5']]"
```
Expected: carga sin excepción; imprime OK de las 3 hojas.

- [ ] **Step 4: Suite ICT completa en verde**

Run: `python -m pytest tests/ -k ict -q --tb=short`
Expected: todos los tests ICT pasan (0 failed).

- [ ] **Step 5: Inspección manual del A9 generado (opcional pero recomendado)**

Run:
```bash
python -c "from openpyxl import load_workbook; ws=load_workbook(r'audit_artifacts/ict15_papel_trabajo.xlsx')['INVENTARIOS A9']; [print(f'{r}: C={ws.cell(r,3).value!r} D={ws.cell(r,4).value!r} G={ws.cell(r,7).value!r} H={ws.cell(r,8).value!r}') for r in range(18,27)]"
```
Expected: col G = fórmulas `=ABS('DATOS BALANCE'!...)` (signo directo en fila 26/7037), col D = referencias `='DATOS BALANCE'!B...`, col H = `=G-C` en todas.

- [ ] **Step 6: Commit final**

```bash
git add tests/test_ict_info_contable.py
git commit -m "test(ict): verificación empírica cuadre A9 PROPHAR + Excel sano

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notas de cierre

- **Desviación del spec (mejora):** el spec planteaba `SUMIF`/`INDEX-MATCH` para A9.
  El plan usa **referencias directas a las filas exactas** del balance
  (`balance_rows_for_casillero` + `balance_sum_ref`/`balance_codigo_ref`), porque
  reutiliza infraestructura ya probada, es consistente con cómo el A1 referencia
  `DATOS BALANCE`, y el resultado es **equivalente**. `SUMIF` reactivo se mantiene
  **solo en A4/A5**, donde el casillero es variable (lo escribe el auditor) y no se
  conocen las filas al generar.
- **Separación SRI/papel:** `DATOS BALANCE` ya viaja en el archivo SRI (es hoja de
  datos fuente). Confirmar que no esté en `INTERNAL_SHEETS_FOR_SRI` (si lo estuviera,
  las fórmulas darían `#REF!` en el SRI — verificar en Task 7 Step 3 abriendo el SRI).
- **Fuera de alcance** (no tocar en este plan): A6, A7, A8; columnas de juicio del
  auditor (forma de valoración E, cantidad F en A9 — solo se llenan del Kardex si el
  cliente lo sube).
- **Recordatorio:** el `BALANCE MAPEADO.xlsx` corregido es dato del cliente; debe
  subirse al regenerar el ICT (no se despliega por código).
