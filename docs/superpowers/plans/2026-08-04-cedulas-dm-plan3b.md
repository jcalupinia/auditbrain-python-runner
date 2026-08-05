# Libro DM · Cédulas DM3–DM7 — Plan 3b de 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir las cinco cédulas del papel de trabajo —DM3, DM4, DM5, DM6 y DM7— donde se cruza lo registrado en libros contra lo declarado al SRI, con **todas las cifras como fórmulas** hacia las hojas de datos.

**Architecture:** Un módulo por cédula bajo `libro/cedulas/`, cada uno recibiendo los mapas de direcciones que publican las hojas de datos y devolviendo el suyo, porque las cédulas se referencian entre sí. Orden de construcción obligatorio: **DM4 → DM5 → DM6 → DM7 → DM3** (DM6 lee de DM4 y DM5; DM7 de DM5 y DM6; DM3 de DM7).

**Tech Stack:** openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md`, sección "Lógica confirmada por DM".
**Depende de:** Plan 3a (hojas de datos y sus mapas de direcciones).

---

## La regla que gobierna todo este plan

**Ninguna celda de dato se escribe como valor.** Todo importe que provenga de otra hoja va como fórmula. En el archivo modelo del auditor los casilleros estaban tecleados a mano —y venían del ICT de otro cliente—, y las sumas de DM6 eran literales como `=736,68+3034,04`. Aquí eso pasa a ser `='DATOS F-104'!H23+'DATOS F-104'!H24`. Si el auditor corrige una homologación y se regenera el libro, todo se recalcula solo.

## Limitación conocida de la verificación

`openpyxl` **no evalúa fórmulas**: al leer un libro recién generado, una celda con fórmula devuelve la cadena `"=SUM(...)"`, no su resultado. Por eso la verificación de este plan es doble:

1. **Estructural** (en los tests): que cada fórmula apunte a la celda correcta de la hoja correcta.
2. **Numérica** (Task 9): calcular en Python lo que la fórmula debería dar y contrastarlo contra los valores cacheados del archivo modelo del auditor.

Nunca afirmes "los números cuadran" leyendo el libro generado con openpyxl: ahí no hay números todavía.

## Mapeo de casilleros confirmado empíricamente

| Cédula | Concepto | Casilleros |
|---|---|---|
| DM3 | Crédito tributario | **615 + 617** |
| DM3 | IVA Diferido | **485** |
| DM3 | SRI por pagar | **859** de diciembre + total retenciones de renta de diciembre |
| DM4 | IVA en compras declarado | 520, 521, 522, 523, 524, 525, 526, 555, 560 |
| DM4 | Base imponible declarada | 510, 511, 512 |
| DM5 | Ventas ≠0% declaradas | 411, 412, 444 |
| DM5 | Ventas 0% declaradas | 412, 413, 414, 415, 417, 418, 444 |
| DM5 | IVA en ventas declarado | 421, 422, 423, 424, 454 |
| DM6 | `F {5}` transferencias a contado | **480** |
| DM6 | `I {8}` IVA en la diferencia | **424** (puede ser 423) |
| DM6 | `J {9}` impuesto a liquidar mes anterior | **483** (enero); resto = `{11}` del mes previo |
| DM6 | `T {19}` crédito del mes anterior | **605 + 606** (enero); resto = `{22}` del mes previo |
| DM6 | `AF` retenciones de IVA declaradas | **609** |
| DM6 | `Z {25}` saldo para el próximo mes | **615 + 617** |
| DM6 | `AA {26}` impuesto por percepción | **699** |
| DM7 | Retenciones de IVA declaradas | 721, 723, 725, 727, 729, 731, 799 |
| DM7 | Retenciones de renta declaradas | **499** del F-103 |

`DM4` calcula la base imponible **dividiendo el IVA de libros para la tarifa**, no la toma del mayor. La tarifa de IVA es **parametrizable por mes** (el ejercicio puede cruzar el cambio de 12 % a 15 %).

---

### Task 1: El resumen publica también la dirección de cada cuenta

Hoy `build_hoja_mayores` solo devuelve los subtotales por categoría. Las cédulas necesitan además la fila de cada cuenta, porque listan las cuentas una por una antes de sumarlas.

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/libro/hoja_mayores.py`
- Modify: `tests/test_of_libro_hoja_mayores.py`

- [ ] **Step 1: Escribir el test que falla**

```python
def test_publica_tambien_la_direccion_de_cada_cuenta():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    assert ("cuenta:1.1.5.1.1", "01") in lookup
    assert ("cuenta:1.1.5.1.1", "TOTAL") in lookup


def test_la_direccion_de_una_cuenta_apunta_a_su_valor_mensual():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    assert ws[lookup[("cuenta:1.1.5.1.1", "01")]].value == 659.57
    assert ws[lookup[("cuenta:1.1.5.1.3", "01")]].value == 9252.0


def test_las_cuentas_de_una_categoria_se_pueden_listar_en_orden():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    assert lookup[("orden:IVA_COMPRAS", "cuentas")] == ["1.1.5.1.1", "1.1.5.1.3"]
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python -m pytest tests/test_of_libro_hoja_mayores.py -q`
Expected: FAIL — `KeyError: ('cuenta:1.1.5.1.1', '01')`

- [ ] **Step 3: Implementación mínima**

En `hoja_mayores.py`, dentro del bucle de cuentas, después de escribir cada celda de mes:

```python
                lookup[(f"cuenta:{f.codigo_cuenta}", MESES[j])] = (
                    f"{get_column_letter(COL_PRIMER_MES + j)}{fila}"
                )
```

Tras escribir la celda de total de la cuenta:

```python
            lookup[(f"cuenta:{f.codigo_cuenta}", "TOTAL")] = (
                f"{get_column_letter(COL_TOTAL)}{fila}"
            )
```

Y al cerrar cada bloque de categoría:

```python
        lookup[(f"orden:{categoria}", "cuentas")] = [f.codigo_cuenta for f in cuentas]
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `python -m pytest tests/test_of_libro_hoja_mayores.py -q`
Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/libro/hoja_mayores.py tests/test_of_libro_hoja_mayores.py
git commit -m "feat(libro): el resumen publica la direccion de cada cuenta"
```

---

### Task 2: Constructor de bloques de cédula

Las cinco cédulas repiten la misma anatomía: una tabla de 12 meses + total, con filas de detalle, una fila "Según libros", filas de casilleros, una fila "Según declaraciones" y una fila "Diferencia". Se extrae aquí una sola vez.

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/libro/cedulas/__init__.py`, `libro/cedulas/bloques.py`
- Test: `tests/test_of_libro_bloques.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Constructor de bloques de cédula: la anatomía común de DM3..DM7."""

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.cedulas.bloques import (
    MESES,
    escribir_encabezado_meses,
    fila_diferencia,
    fila_referencias,
    fila_suma_rango,
)


def _ws():
    return Workbook().active


def test_el_encabezado_pone_los_doce_meses_y_el_total():
    ws = _ws()
    escribir_encabezado_meses(ws, fila=13, titulo="IVA EN COMPRAS")
    assert ws.cell(13, 1).value == "IVA EN COMPRAS"
    assert ws.cell(13, 3).value == "Enero"
    assert ws.cell(13, 14).value == "Diciembre"
    assert ws.cell(13, 15).value == "Total"


def test_una_fila_de_referencias_escribe_una_formula_por_mes():
    ws = _ws()
    direcciones = {m: f"'Mayores homologados'!D{i}" for i, m in enumerate(MESES, 4)}
    fila_referencias(ws, fila=16, etiqueta="IVA EN COMPRAS", direcciones=direcciones)
    assert ws.cell(16, 2).value == "IVA EN COMPRAS"
    assert ws.cell(16, 3).value == "='Mayores homologados'!D4"
    assert ws.cell(16, 14).value == "='Mayores homologados'!D15"


def test_un_mes_sin_direccion_queda_en_cero_no_vacio():
    ws = _ws()
    fila_referencias(ws, fila=16, etiqueta="x", direcciones={"01": "'H'!A1"})
    assert ws.cell(16, 4).value == 0


def test_la_fila_de_suma_totaliza_el_rango_indicado():
    ws = _ws()
    fila_suma_rango(ws, fila=20, etiqueta="Según libros", desde=16, hasta=19)
    assert ws.cell(20, 3).value == "=SUM(C16:C19)"
    assert ws.cell(20, 15).value == "=SUM(O16:O19)"


def test_la_fila_de_diferencia_resta_dos_filas():
    ws = _ws()
    fila_diferencia(ws, fila=33, etiqueta="Diferencia", fila_libros=20, fila_declarado=31)
    assert ws.cell(33, 3).value == "=ROUND(C20-C31,2)"


def test_los_importes_llevan_formato_contable():
    ws = _ws()
    fila_suma_rango(ws, fila=20, etiqueta="Según libros", desde=16, hasta=19)
    assert ws.cell(20, 3).number_format == "#,##0.00"
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python -m pytest tests/test_of_libro_bloques.py -q`
Expected: FAIL — `ModuleNotFoundError: ...libro.cedulas.bloques`

- [ ] **Step 3: Implementación mínima**

`libro/cedulas/__init__.py`:

```python
"""Cédulas DM del papel de trabajo de Obligaciones Fiscales."""
```

`libro/cedulas/bloques.py`:

```python
"""Anatomía común de las cédulas DM.

Cada bloque es una tabla de 12 meses + total con: filas de detalle (una por
cuenta o por casillero), una fila "Según libros", una fila "Según
declaraciones" y una fila "Diferencia". Todas las cifras son fórmulas.
"""

from __future__ import annotations

from openpyxl.utils import get_column_letter

from backend.app.aud.obligaciones_fiscales.libro.estilos import (
    BORDE, FONT_DATA, FONT_ENCABEZADO_TABLA, FONT_TOTAL, FORMATO_NUM, RELLENO_TOTAL,
)

MESES = [f"{m:02d}" for m in range(1, 13)]
NOMBRES_MES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

COL_TITULO, COL_ETIQUETA, COL_PRIMER_MES = 1, 2, 3
COL_TOTAL = COL_PRIMER_MES + 12


def _col(mes_idx: int) -> str:
    return get_column_letter(COL_PRIMER_MES + mes_idx)


def escribir_encabezado_meses(ws, *, fila: int, titulo: str, etiqueta: str = "Cuenta") -> None:
    ws.cell(fila, COL_TITULO, titulo).font = FONT_ENCABEZADO_TABLA
    ws.cell(fila, COL_ETIQUETA, etiqueta).font = FONT_ENCABEZADO_TABLA
    for j, nombre in enumerate(NOMBRES_MES):
        c = ws.cell(fila, COL_PRIMER_MES + j, nombre)
        c.font = FONT_ENCABEZADO_TABLA
        c.border = BORDE
    c = ws.cell(fila, COL_TOTAL, "Total")
    c.font = FONT_ENCABEZADO_TABLA
    c.border = BORDE


def fila_referencias(ws, *, fila: int, etiqueta: str, direcciones: dict[str, str]) -> None:
    """Una fila cuyos 12 meses apuntan por fórmula a otra hoja.

    Un mes sin dirección se escribe como 0: una celda vacía en un papel de
    trabajo se lee como dato faltante, no como ausencia de movimiento.
    """
    ws.cell(fila, COL_ETIQUETA, etiqueta).font = FONT_DATA
    for j, mes in enumerate(MESES):
        addr = direcciones.get(mes)
        c = ws.cell(fila, COL_PRIMER_MES + j, f"={addr}" if addr else 0)
        c.font = FONT_DATA
        c.number_format = FORMATO_NUM
        c.border = BORDE
    t = ws.cell(fila, COL_TOTAL, f"=SUM({_col(0)}{fila}:{_col(11)}{fila})")
    t.font = FONT_DATA
    t.number_format = FORMATO_NUM
    t.border = BORDE


def fila_suma_direcciones(ws, *, fila: int, etiqueta: str,
                          direcciones_por_mes: dict[str, list[str]]) -> None:
    """Una fila donde cada mes es la SUMA de varias celdas de otra hoja.

    Es el caso de 'Según declaraciones': varios casilleros del mismo mes.
    """
    ws.cell(fila, COL_ETIQUETA, etiqueta).font = FONT_DATA
    for j, mes in enumerate(MESES):
        addrs = direcciones_por_mes.get(mes) or []
        valor = ("=" + "+".join(addrs)) if addrs else 0
        c = ws.cell(fila, COL_PRIMER_MES + j, valor)
        c.font = FONT_DATA
        c.number_format = FORMATO_NUM
        c.border = BORDE
    t = ws.cell(fila, COL_TOTAL, f"=SUM({_col(0)}{fila}:{_col(11)}{fila})")
    t.font = FONT_DATA
    t.number_format = FORMATO_NUM
    t.border = BORDE


def fila_suma_rango(ws, *, fila: int, etiqueta: str, desde: int, hasta: int) -> None:
    """Fila de subtotal sobre un rango vertical de filas de la misma hoja."""
    e = ws.cell(fila, COL_ETIQUETA, etiqueta)
    e.font = FONT_TOTAL
    e.fill = RELLENO_TOTAL
    for j in range(13):
        col = get_column_letter(COL_PRIMER_MES + j)
        c = ws.cell(fila, COL_PRIMER_MES + j, f"=SUM({col}{desde}:{col}{hasta})")
        c.font = FONT_TOTAL
        c.fill = RELLENO_TOTAL
        c.number_format = FORMATO_NUM
        c.border = BORDE


def fila_diferencia(ws, *, fila: int, etiqueta: str, fila_libros: int,
                    fila_declarado: int) -> None:
    """Libros menos declarado, redondeado a 2 decimales.

    El ROUND evita el ruido de coma flotante que en el archivo modelo del
    auditor producía diferencias como -3,6e-12.
    """
    e = ws.cell(fila, COL_ETIQUETA, etiqueta)
    e.font = FONT_TOTAL
    for j in range(13):
        col = get_column_letter(COL_PRIMER_MES + j)
        c = ws.cell(fila, COL_PRIMER_MES + j,
                    f"=ROUND({col}{fila_libros}-{col}{fila_declarado},2)")
        c.font = FONT_TOTAL
        c.number_format = FORMATO_NUM
        c.border = BORDE
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `python -m pytest tests/test_of_libro_bloques.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/libro/cedulas/ tests/test_of_libro_bloques.py
git commit -m "feat(libro): constructor de bloques comunes de cedula"
```

---

### Task 3: DM4 Compras — la cédula de referencia

Es la primera y fija el patrón que siguen las otras cuatro. Dos bloques:

**Bloque 1 — IVA en compras** (fila 13 en adelante): una fila por cuenta de la categoría `IVA_COMPRAS` (fórmula al resumen) → *Según libros* (suma del rango) → una fila por casillero declarado (`520, 521, 522, 523, 524, 525, 526, 555, 560`, fórmula a `DATOS F-104`) → *Según declaraciones* (suma del rango) → *Diferencia*.

**Bloque 2 — Base imponible**: *Compras gravadas* = el IVA de libros **dividido para la tarifa del mes** → una fila por casillero (`510, 511, 512`) → *Según declaraciones* → *Diferencia*.

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/libro/cedulas/dm4_compras.py`
- Test: `tests/test_of_libro_dm4.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""DM4 Compras: IVA en compras y base imponible, libros vs declaraciones."""

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.cedulas.dm4_compras import (
    CASILLEROS_BASE, CASILLEROS_IVA, SHEET_DM4, build_dm4,
)

PERIODOS = [f"2025-{m:02d}" for m in range(1, 13)]

DIR_MAYORES = {
    ("cuenta:1.1.5.1.1", "01"): "'Mayores homologados'!D4",
    ("cuenta:1.1.5.1.3", "01"): "'Mayores homologados'!D5",
    ("orden:IVA_COMPRAS", "cuentas"): ["1.1.5.1.1", "1.1.5.1.3"],
    ("IVA_COMPRAS", "01"): "'Mayores homologados'!D6",
}
DIR_F104 = {("2025-01", cas): f"'DATOS F-104'!C{i}" for i, cas in enumerate(
    CASILLEROS_IVA + CASILLEROS_BASE, start=20)}

NOMBRES = {"1.1.5.1.1": "IVA sobre Compras", "1.1.5.1.3": "IVA en Importaciones"}


def _cedula(**kw):
    wb = Workbook()
    datos = dict(dir_mayores=DIR_MAYORES, dir_f104=DIR_F104, periodos=PERIODOS,
                 nombres_cuenta=NOMBRES, cliente="C", periodo="2025", tarifas={})
    datos.update(kw)
    build_dm4(wb, **datos)
    return wb[SHEET_DM4]


def test_lista_una_fila_por_cuenta_de_iva_en_compras():
    ws = _cedula()
    etiquetas = [ws.cell(r, 2).value for r in range(1, ws.max_row + 1)]
    assert "IVA sobre Compras" in etiquetas
    assert "IVA en Importaciones" in etiquetas


def test_el_valor_de_una_cuenta_es_una_formula_al_resumen():
    ws = _cedula()
    fila = next(r for r in range(1, ws.max_row + 1)
                if ws.cell(r, 2).value == "IVA sobre Compras")
    assert ws.cell(fila, 3).value == "='Mayores homologados'!D4"


def test_los_casilleros_son_formulas_a_la_hoja_de_datos_no_valores():
    ws = _cedula()
    fila = next(r for r in range(1, ws.max_row + 1)
                if str(ws.cell(r, 2).value or "").startswith("Casillero 520"))
    valor = ws.cell(fila, 3).value
    assert isinstance(valor, str) and valor.startswith("='DATOS F-104'!")


def test_estan_los_nueve_casilleros_de_iva_en_compras():
    ws = _cedula()
    etiquetas = [str(ws.cell(r, 2).value or "") for r in range(1, ws.max_row + 1)]
    for cas in CASILLEROS_IVA:
        assert any(e.startswith(f"Casillero {cas}") for e in etiquetas), cas


def test_la_diferencia_resta_libros_menos_declarado_y_redondea():
    ws = _cedula()
    fila = next(r for r in range(1, ws.max_row + 1)
                if ws.cell(r, 2).value == "Diferencia")
    assert ws.cell(fila, 3).value.startswith("=ROUND(")


def test_la_base_imponible_divide_el_iva_para_la_tarifa_del_mes():
    ws = _cedula(tarifas={"01": 0.15})
    fila = next(r for r in range(1, ws.max_row + 1)
                if str(ws.cell(r, 2).value or "").startswith("Compras gravadas"))
    assert "/0.15" in ws.cell(fila, 3).value


def test_la_tarifa_por_defecto_es_quince_por_ciento():
    ws = _cedula()
    fila = next(r for r in range(1, ws.max_row + 1)
                if str(ws.cell(r, 2).value or "").startswith("Compras gravadas"))
    assert "/0.15" in ws.cell(fila, 3).value


def test_una_tarifa_distinta_en_un_mes_se_respeta():
    """El ejercicio puede cruzar el cambio de 12% a 15%."""
    ws = _cedula(tarifas={"01": 0.12})
    fila = next(r for r in range(1, ws.max_row + 1)
                if str(ws.cell(r, 2).value or "").startswith("Compras gravadas"))
    assert "/0.12" in ws.cell(fila, 3).value


def test_lleva_el_encabezado_de_cedula_con_su_referencia():
    ws = _cedula()
    valores = [ws.cell(r, c).value for r in range(1, 11) for c in range(1, 6)]
    assert "OBLIGACIONES FISCALES" in valores
    assert "DM4" in valores
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python -m pytest tests/test_of_libro_dm4.py -q`
Expected: FAIL — `ModuleNotFoundError: ...cedulas.dm4_compras`

- [ ] **Step 3: Implementación mínima**

```python
"""DM4 Compras — IVA en compras y base imponible, libros vs declaraciones."""

from __future__ import annotations

from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook

from backend.app.aud.obligaciones_fiscales.libro.cedulas.bloques import (
    COL_PRIMER_MES, COL_TOTAL, MESES, escribir_encabezado_meses, fila_diferencia,
    fila_referencias, fila_suma_direcciones, fila_suma_rango,
)
from backend.app.aud.obligaciones_fiscales.libro.estilos import (
    FONT_DATA, FORMATO_NUM, escribir_encabezado_cedula, escribir_leyenda_marcas,
)

SHEET_DM4 = "DM4 Compras"
CASILLEROS_IVA = ["520", "521", "522", "523", "524", "525", "526", "555", "560"]
CASILLEROS_BASE = ["510", "511", "512"]
TARIFA_POR_DEFECTO = 0.15


def _dirs_cuenta(dir_mayores: dict, codigo: str) -> dict[str, str]:
    return {
        mes: dir_mayores[(f"cuenta:{codigo}", mes)]
        for mes in MESES
        if (f"cuenta:{codigo}", mes) in dir_mayores
    }


def _dirs_casillero(dir_f104: dict, periodos: list[str], cas: str) -> dict[str, str]:
    salida = {}
    for periodo in periodos:
        mes = periodo.split("-")[-1]
        addr = dir_f104.get((periodo, cas))
        if addr:
            salida[mes] = addr
    return salida


def build_dm4(
    wb: Workbook,
    *,
    dir_mayores: dict,
    dir_f104: dict,
    periodos: list[str],
    nombres_cuenta: dict[str, str],
    cliente: str,
    periodo: str,
    tarifas: dict[str, float] | None = None,
    preparado_por: str | None = None,
    revisado_por: str | None = None,
) -> dict[tuple[str, str], str]:
    """Construye DM4. Devuelve {("libros"|"declarado"|"base", mes) → addr}."""
    if SHEET_DM4 in wb.sheetnames:
        del wb[SHEET_DM4]
    ws = wb.create_sheet(SHEET_DM4)
    tarifas = tarifas or {}

    escribir_encabezado_cedula(
        ws, titulo="Compras e IVA en compras", referencia="DM4",
        cliente=cliente, periodo=periodo,
        preparado_por=preparado_por, revisado_por=revisado_por,
    )

    # --- Bloque 1: IVA en compras ---
    escribir_encabezado_meses(ws, fila=13, titulo="IVA EN COMPRAS")
    fila = 14
    primera_cuenta = fila
    for codigo in dir_mayores.get(("orden:IVA_COMPRAS", "cuentas"), []):
        fila_referencias(ws, fila=fila, etiqueta=nombres_cuenta.get(codigo, codigo),
                         direcciones=_dirs_cuenta(dir_mayores, codigo))
        fila += 1
    ultima_cuenta = fila - 1

    fila_libros = fila
    fila_suma_rango(ws, fila=fila_libros, etiqueta="Según libros",
                    desde=primera_cuenta, hasta=ultima_cuenta)
    fila += 2

    primer_cas = fila
    for cas in CASILLEROS_IVA:
        fila_referencias(ws, fila=fila, etiqueta=f"Casillero {cas}",
                         direcciones=_dirs_casillero(dir_f104, periodos, cas))
        fila += 1
    fila_declarado = fila
    fila_suma_rango(ws, fila=fila_declarado, etiqueta="Según declaraciones",
                    desde=primer_cas, hasta=fila - 1)
    fila += 1

    fila_dif = fila
    fila_diferencia(ws, fila=fila_dif, etiqueta="Diferencia",
                    fila_libros=fila_libros, fila_declarado=fila_declarado)
    fila += 3

    # --- Bloque 2: base imponible = IVA de libros / tarifa del mes ---
    escribir_encabezado_meses(ws, fila=fila, titulo="BASE IMPONIBLE DE COMPRAS")
    fila += 1
    fila_base = fila
    ws.cell(fila, 2, "Compras gravadas (IVA ÷ tarifa)").font = FONT_DATA
    for j, mes in enumerate(MESES):
        col = get_column_letter(COL_PRIMER_MES + j)
        tarifa = tarifas.get(mes, TARIFA_POR_DEFECTO)
        c = ws.cell(fila, COL_PRIMER_MES + j, f"={col}{fila_libros}/{tarifa}")
        c.font = FONT_DATA
        c.number_format = FORMATO_NUM
    ini = get_column_letter(COL_PRIMER_MES)
    fin = get_column_letter(COL_PRIMER_MES + 11)
    ws.cell(fila, COL_TOTAL, f"=SUM({ini}{fila}:{fin}{fila})").number_format = FORMATO_NUM
    fila += 2

    primer_cas_base = fila
    for cas in CASILLEROS_BASE:
        fila_referencias(ws, fila=fila, etiqueta=f"Casillero {cas}",
                         direcciones=_dirs_casillero(dir_f104, periodos, cas))
        fila += 1
    fila_declarado_base = fila
    fila_suma_rango(ws, fila=fila_declarado_base, etiqueta="Según declaraciones",
                    desde=primer_cas_base, hasta=fila - 1)
    fila += 1
    fila_diferencia(ws, fila=fila, etiqueta="Diferencia",
                    fila_libros=fila_base, fila_declarado=fila_declarado_base)
    fila += 3

    escribir_leyenda_marcas(ws, fila=fila)

    for col, ancho in ((1, 24), (2, 30)):
        ws.column_dimensions[get_column_letter(col)].width = ancho
    for j in range(13):
        ws.column_dimensions[get_column_letter(COL_PRIMER_MES + j)].width = 15

    return {
        **{("libros", m): f"'{SHEET_DM4}'!{get_column_letter(COL_PRIMER_MES + j)}{fila_libros}"
           for j, m in enumerate(MESES)},
        **{("base", m): f"'{SHEET_DM4}'!{get_column_letter(COL_PRIMER_MES + j)}{fila_base}"
           for j, m in enumerate(MESES)},
    }
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `python -m pytest tests/test_of_libro_dm4.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/libro/cedulas/dm4_compras.py tests/test_of_libro_dm4.py
git commit -m "feat(libro): cedula DM4 Compras con casilleros por formula"
```

---

### Task 4: DM5 Ventas

Mismo patrón que DM4, con **tres** bloques y filas dinámicas: la cantidad de cuentas de venta varía por cliente.

| Bloque | Filas de libros | Casilleros declarados |
|---|---|---|
| Ventas ≠ 0 % | cuentas de la categoría `VENTAS` con saldo en el mes | 411, 412, 444 |
| Ventas 0 % | mismas cuentas (las de tarifa 0 se distinguen por el F-104, no por el mayor) | 412, 413, 414, 415, 417, 418, 444 |
| IVA en ventas | cuentas de `IVA_VENTAS` | 421, 422, 423, 424, 454 |

Publica `("ventas_libros", mes)`, `("ventas_0_libros", mes)`, `("iva_ventas_libros", mes)` y `("total_declarado", mes)` — esta última es la fila "Total ventas declaradas", que DM6 y DM8 consumen.

**Files:** Create `libro/cedulas/dm5_ventas.py`; test `tests/test_of_libro_dm5.py`.

- [ ] **Step 1: Test que falla** — mismos casos que DM4 adaptados: una fila por cuenta de ventas, casilleros como fórmula, diferencia con `ROUND`, encabezado con referencia `DM5`, y **un test específico**: si el cliente tiene 12 cuentas de venta en vez de 2, el bloque crece y las filas de subtotal se desplazan con él (verificar que `Según libros` sigue sumando el rango correcto).
- [ ] **Step 2: Correr y ver fallar** (`ModuleNotFoundError`).
- [ ] **Step 3: Implementar** siguiendo `dm4_compras.py` como referencia.
- [ ] **Step 4: Correr y ver pasar.**
- [ ] **Step 5: Commit** `feat(libro): cedula DM5 Ventas con bloques dinamicos por cliente`

---

### Task 5: DM6 IVA

La cédula grande: 29 columnas `{1}…{29}`. **No lleva filas de cuentas**: cada fila es un mes y cada columna una fórmula. Las de origen externo salen de la tabla de mapeo de arriba; las derivadas son:

```
{7}  H = B*G                    {10} K = F*G + I
{11} L = (H+I) - K              {12} M = J + K
{14} O = N*G                    {16} Q = IF(SUM(B:E)=0, 0, (B+C+E)/(B+C+D+E))
{17} R = (O+P)*Q                {22} W = ABS(IF((M-R-S-T-U+V)<0, (M-R-S-T-U+V), 0))
{23} X = IF((M-R-S-T-U+V)>0, (M-R-S-T-U+V), 0)
{27} AB = Y-B-C-D-E             {28} AC = Z-W            {29} AD = AA-X
```

Encadenamiento entre meses: `{9} J` de febrero en adelante `= {11} L` del mes anterior; `{19} T` de febrero en adelante `= {22} W` del mes anterior. **Enero** toma `J = casillero 483` y `T = casillero 605 + 606`.

Columnas que vienen de otras cédulas: `B ← DM5 ventas ≠0% libros`, `C ← DM5 ventas 0% libros`, `N ← DM4 base`, `Y ← DM5 total declarado`.

Tres tests irrenunciables: (a) enero usa los casilleros y no una referencia circular; (b) febrero encadena contra enero; (c) el factor de proporcionalidad `Q` no divide por cero cuando el mes no tiene ventas.

**Files:** Create `libro/cedulas/dm6_iva.py`; test `tests/test_of_libro_dm6.py`.
Commit: `feat(libro): cedula DM6 IVA con encadenamiento mensual por formula`

---

### Task 6: DM7 Retenciones por pagar

Dos bloques independientes:

1. **Retenciones de IVA** — libros: cuentas de `RET_IVA`; declarado: casilleros `721, 723, 725, 727, 729, 731` del F-104, con `799` como control del total.
2. **Retenciones de renta** — libros: cuentas de `RET_RENTA`; declarado: casillero **`499` del F-103**.

Publica `("ret_iva_declarado", mes)` y `("ret_renta_declarado", mes)`, que DM3 consume para el pasivo al cierre.

**Files:** Create `libro/cedulas/dm7_retenciones.py`; test `tests/test_of_libro_dm7.py`.
Commit: `feat(libro): cedula DM7 Retenciones por pagar, IVA y renta`

---

### Task 7: DM3 Revisión de saldos

Tres bloques de una sola cifra anual cada uno (no mensual):

| Bloque | Según libros | Según declaración |
|---|---|---|
| Crédito tributario | total anual de la cuenta de crédito tributario | `615 + 617` de **diciembre** |
| IVA Diferido | total anual de la cuenta de IVA diferido | `485` de **diciembre** |
| SRI por Pagar | total anual de la cuenta de SRI por pagar | `859` de diciembre **+** retenciones de renta de diciembre (desde DM7) |

**El "según libros" es el movimiento ACUMULADO DEL AÑO**, o sea la columna *Total* del resumen — no el saldo al cierre.

Si el cliente no tiene alguna de esas cuentas, el bloque se escribe igual con 0 y una nota: el auditor debe ver qué se esperaba.

**Files:** Create `libro/cedulas/dm3_saldos.py`; test `tests/test_of_libro_dm3.py`.
Commit: `feat(libro): cedula DM3 Revision de saldos`

---

### Task 8: Integrar las cédulas al ensamblador

**Files:** Modify `libro/ensamblador.py`; test `tests/test_of_libro_ensamblador.py`.

- [ ] **Step 1: Tests que fallan**: el libro trae las 9 hojas; el orden es `Mayores homologados, Detalle mayor, DM3, DM4, DM5, DM6, DM7, DATOS F-104, DATOS F-103`; y **ninguna fórmula referencia una hoja inexistente** (recorrer todas las celdas con `=` y verificar que cada `'Nombre'!` mencionado está en `wb.sheetnames`).
- [ ] **Step 2: Correr y ver fallar.**
- [ ] **Step 3: Implementar**: construir en el orden obligatorio **DM4 → DM5 → DM6 → DM7 → DM3**, encadenando los mapas de direcciones, y ordenar las hojas al final.
- [ ] **Step 4: Correr y ver pasar.**
- [ ] **Step 5: Commit** `feat(libro): ensamblador integra las cinco cedulas DM`

---

### Task 9: Verificación numérica contra el archivo del auditor

**Files:** Create `tests/test_of_libro_cifras_reales.py`.

Como openpyxl no evalúa fórmulas, esta verificación **calcula en Python** lo que cada fila debería dar, a partir del mayor y los F-104 reales, y lo contrasta contra los valores cacheados del archivo modelo del auditor (`DM - Obligaciones Fiscales FINAL`, disponible en `AUD_OF_FIXTURES_DIR`).

- [ ] **Step 1: Escribir los tests que fallan**

Casos mínimos, todos con `skip` si no está `AUD_OF_FIXTURES_DIR`:

1. **DM4 · IVA en compras según libros**: la suma mensual de las cuentas de `IVA_COMPRAS` del mayor debe coincidir con la fila "Según libros" del modelo (enero 9.911,57).
2. **DM4 · base imponible**: `IVA libros ÷ 0,15` debe dar la base del modelo (enero 66.077,13).
3. **DM6 · columna F**: el casillero 480 extraído de los PDFs debe coincidir con la columna F del modelo en los 12 meses.
4. **DM6 · columna Z**: `615 + 617` de cada mes debe coincidir con la columna Z del modelo (enero 9.541,74).
5. **DM6 · columna T de enero**: `605 + 606` = 3.770,72.
6. **DM3 · crédito tributario**: `615 + 617` de diciembre = 68,07.
7. **DM3 · IVA diferido**: casillero 485 de diciembre = 14.139,28.

Tolerancia: 0,01 por redondeo.

- [ ] **Step 2: Correr y ver fallar** (o pasar directamente si la lógica ya es correcta; en ese caso el test queda como regresión y así debe reportarse, sin fingir un ciclo rojo).
- [ ] **Step 3: Corregir el generador** hasta que cuadre. Nunca el test.
- [ ] **Step 4: Correr toda la suite.**
- [ ] **Step 5: Commit** `test(libro): verificacion numerica de las cedulas contra el archivo del auditor`

---

## Criterio de terminado del Plan 3b

- [ ] Las 9 tareas están commiteadas.
- [ ] El libro trae 9 hojas y **ninguna celda de dato es un valor tecleado**: todo importe que viene de otra hoja es fórmula.
- [ ] Ninguna fórmula apunta a una hoja inexistente ni a un libro externo.
- [ ] Las cifras verificadas contra el archivo del auditor cuadran dentro de 0,01.
- [ ] La suite completa no tiene fallos nuevos.

## Lo que este plan NO hace

- `DM8 ATS`: falta el mapeo fila → campo del XML.
- `ingresos iva vs facturacion`: falta definir el insumo de facturación electrónica.
- El frontend (Plan 4).
- Borrar `excel_assembler.py` y su plantilla: se decide cuando DM8 esté portada.
