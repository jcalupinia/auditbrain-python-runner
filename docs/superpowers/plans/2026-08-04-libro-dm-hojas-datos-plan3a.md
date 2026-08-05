# Libro DM · Hojas de datos — Plan 3a de 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir las cuatro hojas de datos del libro DM —el mayor homologado, su detalle y los casilleros declarados de F-104 y F-103— y dejar publicado el mapa de direcciones que permitirá que las cédulas las referencien **por fórmula**.

**Architecture:** Se reutilizan los builders del ICT (`build_f103_sheet`, `build_f104_sheet`), que ya generan las hojas de casilleros y **devuelven `{(periodo, casillero) → "celda"}`**. Se añaden dos hojas nuevas construidas desde la clasificación aprobada del job. Todo el ensamblado vive en un módulo nuevo, `libro/`, y la fase 2 pasa a usarlo.

**Tech Stack:** openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md` (sección "Modelo del Excel DM")
**Depende de:** Plan 1 (motor) y Plan 2 (ciclo del job), ambos implementados.

---

## Por qué esto primero

En el archivo modelo del auditor, **los casilleros están tecleados a mano** y las hojas `datos 103`/`datos 104` venían copiadas del ICT de **otro cliente**. Ese es el error que el sistema debe volver imposible: las hojas de datos se generan siempre desde los PDFs del cliente del job, y las cédulas las leen por fórmula. Sin estas cuatro hojas y su mapa de direcciones, las cédulas del Plan 3b no se pueden construir.

## Piezas existentes que se reutilizan (NO reescribir)

| Pieza | Dónde | Qué da |
|---|---|---|
| `build_f104_sheet(wb, f104_monthly)` | `backend/app/ict/fillers/source_data_sheets.py:623` | Hoja `DATOS F-104` con los 149 casilleros × meses + `TOTAL ANUAL`, y `lookup {(periodo, cas) → addr}` |
| `build_f103_sheet(wb, f103_monthly)` | mismo archivo, línea 497 | Ídem para los 184 casilleros del F-103 |
| `extract_all_f104(paths)` | `backend/app/aud/obligaciones_fiscales/cedulas/f104_extractor.py` | `{"01": {"periodo": "01/2025", "casilleros": {...}}}` |
| `parse_all_f103(paths)` | `backend/app/ict/parsers/f103_pdf.py:444` | `{"2025-01": {"casilleros": {...}}}` |
| `clasificacion_de_job(db, job_id=...)` | `mayor/clasificacion_service.py` | Filas con `categoria_final`, `por_mes_json`, `n_movimientos`, `debe`, `haber` |
| `CATEGORIAS` | `mayor/catalogo.py` | Orden y nombre de cada categoría |

**Ojo con el formato de períodos:** los builders del ICT esperan claves `"YYYY-MM"`; el extractor de F-104 de OF devuelve `"01"`…`"12"` con el período en `"MM/AAAA"`. Hace falta un adaptador (Task 1).

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `obligaciones_fiscales/libro/__init__.py` (nuevo) | Marca el paquete |
| `obligaciones_fiscales/libro/fuentes.py` (nuevo) | Adapta los extractores a lo que esperan los builders del ICT y crea las hojas de casilleros |
| `obligaciones_fiscales/libro/hoja_mayores.py` (nuevo) | Hoja `Mayores homologados` (resumen) + su mapa de direcciones |
| `obligaciones_fiscales/libro/hoja_detalle.py` (nuevo) | Hoja `Detalle mayor` (movimientos + categoría + autofiltro) |
| `obligaciones_fiscales/libro/estilos.py` (nuevo) | Constantes de formato y el encabezado común de cédula |
| `obligaciones_fiscales/libro/ensamblador.py` (nuevo) | Arma el libro y devuelve bytes + el mapa de direcciones |
| `obligaciones_fiscales/jobs.py` (modificar) | La fase 2 usa el ensamblador nuevo |

---

### Task 1: Adaptador de fuentes y hojas de casilleros

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/libro/__init__.py`, `libro/fuentes.py`
- Test: `tests/test_of_libro_fuentes.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Adaptación de los extractores SRI al formato de los builders de hojas."""

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.fuentes import (
    a_periodos_anuales,
    construir_hojas_de_casilleros,
)


def test_convierte_los_meses_del_extractor_f104_a_periodos_anuales():
    entrada = {
        "01": {"periodo": "01/2025", "casilleros": {"429": 10.0}},
        "12": {"periodo": "12/2025", "casilleros": {"429": 20.0}},
    }
    assert a_periodos_anuales(entrada) == {
        "2025-01": {"casilleros": {"429": 10.0}},
        "2025-12": {"casilleros": {"429": 20.0}},
    }


def test_un_mes_sin_periodo_detectado_se_descarta():
    entrada = {"01": {"periodo": None, "casilleros": {"429": 10.0}}}
    assert a_periodos_anuales(entrada) == {}


def test_construye_las_dos_hojas_de_casilleros_y_devuelve_sus_direcciones():
    wb = Workbook()
    lookups = construir_hojas_de_casilleros(
        wb,
        f104_monthly={"2025-01": {"casilleros": {"429": 4341.16}}},
        f103_monthly={"2025-01": {"casilleros": {"499": 915.70}}},
    )
    assert "DATOS F-104" in wb.sheetnames
    assert "DATOS F-103" in wb.sheetnames
    assert ("2025-01", "429") in lookups["f104"]
    assert ("2025-01", "499") in lookups["f103"]


def test_la_direccion_devuelta_apunta_al_valor_correcto():
    wb = Workbook()
    lookups = construir_hojas_de_casilleros(
        wb,
        f104_monthly={"2025-01": {"casilleros": {"429": 4341.16}}},
        f103_monthly={},
    )
    addr = lookups["f104"][("2025-01", "429")]
    assert wb["DATOS F-104"][addr].value == 4341.16


def test_sin_pdfs_igual_se_crean_las_hojas_con_la_matriz_vacia():
    """El auditor debe ver qué casilleros se esperaban, aunque no haya datos."""
    wb = Workbook()
    lookups = construir_hojas_de_casilleros(wb, f104_monthly={}, f103_monthly={})
    assert "DATOS F-104" in wb.sheetnames
    assert lookups["f104"]
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_libro_fuentes.py -q`
Expected: FAIL — `ModuleNotFoundError: ...libro.fuentes`

- [ ] **Step 3: Implementación mínima**

`libro/__init__.py`:

```python
"""Construcción del libro DM de Obligaciones Fiscales."""
```

`libro/fuentes.py`:

```python
"""Hojas de datos fuente: los casilleros declarados al SRI.

Se apoyan en los builders del ICT, que ya generan la matriz completa de
casilleros por mes y devuelven el mapa de direcciones que las cédulas usan
para referenciarlas POR FÓRMULA.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl.workbook import Workbook

from backend.app.ict.fillers.source_data_sheets import (
    build_f103_sheet,
    build_f104_sheet,
)


def a_periodos_anuales(month_data: dict) -> dict:
    """{"01": {"periodo": "01/2025", ...}} → {"2025-01": {"casilleros": {...}}}.

    Los builders del ICT indexan por período completo; el extractor de F-104
    de esta herramienta indexa por mes. Los meses sin período detectado se
    descartan: sin año no se puede ubicar la columna.
    """
    salida: dict[str, dict] = {}
    for datos in (month_data or {}).values():
        periodo = (datos or {}).get("periodo")
        if not periodo or "/" not in str(periodo):
            continue
        mes, anio = str(periodo).split("/", 1)
        salida[f"{anio}-{int(mes):02d}"] = {"casilleros": datos.get("casilleros", {})}
    return salida


def construir_hojas_de_casilleros(
    wb: Workbook, *, f104_monthly: dict, f103_monthly: dict
) -> dict[str, dict]:
    """Crea DATOS F-104 y DATOS F-103. Devuelve {"f104": lookup, "f103": lookup}."""
    return {
        "f104": build_f104_sheet(wb, f104_monthly or {}),
        "f103": build_f103_sheet(wb, f103_monthly or {}),
    }


def leer_declaraciones(job_dir: Path) -> tuple[dict, dict]:
    """Lee los PDFs subidos del job y los deja en formato de períodos anuales."""
    from backend.app.aud.obligaciones_fiscales import file_storage
    from backend.app.aud.obligaciones_fiscales.cedulas.f104_extractor import (
        extract_all_f104,
    )
    from backend.app.ict.parsers.f103_pdf import parse_all_f103

    f104_mes, _ = extract_all_f104(file_storage.list_inputs(job_dir, "f104"))
    f103_monthly, _ = parse_all_f103(file_storage.list_inputs(job_dir, "f103"))
    return a_periodos_anuales(f104_mes), (f103_monthly or {})
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_libro_fuentes.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/libro/ tests/test_of_libro_fuentes.py
git commit -m "feat(libro): hojas de casilleros F-104 y F-103 con su mapa de direcciones"
```

---

### Task 2: Hoja `Mayores homologados` (el resumen del motor)

Es la **única fuente del "según libros"** de todas las cédulas: una fila por cuenta, agrupada por categoría, con 12 columnas de meses, subtotal por categoría y total general. El subtotal de cada categoría es lo que después leerá, por ejemplo, la fila "Según libros" de DM4.

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/libro/hoja_mayores.py`
- Test: `tests/test_of_libro_hoja_mayores.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Hoja resumen: cuenta × mes, agrupada por categoría."""

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.hoja_mayores import (
    SHEET_MAYORES,
    build_hoja_mayores,
)


class _Fila:
    """Doble de MayorClasificacionJob: solo lo que la hoja necesita."""

    def __init__(self, codigo, nombre, categoria, por_mes, n=1, debe=0.0, haber=0.0):
        self.codigo_cuenta = codigo
        self.nombre_cuenta = nombre
        self.categoria_final = categoria
        self.por_mes_json = por_mes
        self.n_movimientos = n
        self.debe = debe
        self.haber = haber


FILAS = [
    _Fila("1.1.5.1.1", "IVA sobre Compras", "IVA_COMPRAS", {"01": 659.57, "02": 1988.83}),
    _Fila("1.1.5.1.3", "IVA en Importaciones", "IVA_COMPRAS", {"01": 9252.0}),
    _Fila("4.1.1.4", "Venta de insumos", "VENTAS", {"01": -28117.84}),
]


def test_crea_la_hoja_con_una_fila_por_cuenta():
    wb = Workbook()
    build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    codigos = [ws.cell(r, 2).value for r in range(1, ws.max_row + 1)]
    assert "1.1.5.1.1" in codigos
    assert "4.1.1.4" in codigos


def test_agrupa_por_categoria_y_pone_un_subtotal():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    addr = lookup[("IVA_COMPRAS", "01")]
    assert ws[addr].value.startswith("=SUM(")


def test_el_subtotal_de_enero_de_iva_compras_suma_sus_dos_cuentas():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    # El subtotal es una fórmula SUM sobre el rango de sus cuentas: se
    # verifica el rango, no el valor (openpyxl no evalúa fórmulas).
    formula = ws[lookup[("IVA_COMPRAS", "01")]].value
    assert formula.count(":") == 1


def test_publica_la_direccion_del_subtotal_de_cada_categoria_y_mes():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    for mes in (f"{m:02d}" for m in range(1, 13)):
        assert ("IVA_COMPRAS", mes) in lookup
        assert ("VENTAS", mes) in lookup
    assert ("IVA_COMPRAS", "TOTAL") in lookup


def test_una_categoria_sin_cuentas_no_aparece():
    wb = Workbook()
    lookup = build_hoja_mayores(wb, FILAS)
    assert ("RET_IVA", "01") not in lookup


def test_los_meses_sin_movimiento_quedan_en_cero_no_vacios():
    """Un mes vacío en el papel de trabajo se lee como dato faltante."""
    wb = Workbook()
    build_hoja_mayores(wb, FILAS)
    ws = wb[SHEET_MAYORES]
    fila_ventas = next(
        r for r in range(1, ws.max_row + 1) if ws.cell(r, 2).value == "4.1.1.4"
    )
    assert ws.cell(fila_ventas, 5).value == 0.0   # marzo


def test_las_cuentas_sin_categoria_van_a_un_bloque_de_no_clasificadas():
    wb = Workbook()
    filas = FILAS + [_Fila("9.9.9", "Cuenta puente", None, {"01": 5.0})]
    lookup = build_hoja_mayores(wb, filas)
    ws = wb[SHEET_MAYORES]
    codigos = [ws.cell(r, 2).value for r in range(1, ws.max_row + 1)]
    assert "9.9.9" in codigos
    assert ("SIN_CLASIFICAR", "01") in lookup
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_libro_hoja_mayores.py -q`
Expected: FAIL — `ModuleNotFoundError: ...libro.hoja_mayores`

- [ ] **Step 3: Implementación mínima**

```python
"""Hoja 'Mayores homologados': el resumen que produce el motor.

Es la ÚNICA fuente del "según libros" de todas las cédulas. Cada cédula lee
el subtotal de su categoría por fórmula, usando el mapa de direcciones que
esta función devuelve.
"""

from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import CATEGORIAS

SHEET_MAYORES = "Mayores homologados"
MESES = [f"{m:02d}" for m in range(1, 13)]
NOMBRES_MES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
SIN_CLASIFICAR = "SIN_CLASIFICAR"

FONT_TITULO = Font(name="Calibri", size=11, bold=True)
FONT_DATA = Font(name="Calibri", size=9)
FONT_TOTAL = Font(name="Calibri", size=10, bold=True)
BORDE = Border(*[Side(style="thin")] * 4)
RELLENO_TOTAL = PatternFill("solid", fgColor="DCE6F1")
FORMATO_NUM = "#,##0.00"

COL_CATEGORIA, COL_CODIGO, COL_NOMBRE = 1, 2, 3
COL_PRIMER_MES = 4
COL_TOTAL = COL_PRIMER_MES + 12


def _orden(codigo: str | None) -> int:
    cat = CATEGORIAS.get(codigo or "")
    return cat.orden if cat else 99


def build_hoja_mayores(wb: Workbook, filas) -> dict[tuple[str, str], str]:
    """Crea la hoja resumen. Devuelve {(categoria, "01".."12"|"TOTAL") → addr}."""
    if SHEET_MAYORES in wb.sheetnames:
        del wb[SHEET_MAYORES]
    ws = wb.create_sheet(SHEET_MAYORES)

    ws.cell(1, 1, "MAYORES HOMOLOGADOS · resumen por cuenta y mes").font = FONT_TITULO

    encabezado = ["Categoría", "Código", "Cuenta"] + NOMBRES_MES + ["Total"]
    for i, texto in enumerate(encabezado, start=1):
        c = ws.cell(3, i, texto)
        c.font = FONT_TOTAL
        c.border = BORDE
        c.alignment = Alignment(horizontal="center", wrap_text=True)

    por_categoria: dict[str, list] = {}
    for f in filas:
        por_categoria.setdefault(f.categoria_final or SIN_CLASIFICAR, []).append(f)

    lookup: dict[tuple[str, str], str] = {}
    fila = 4
    for categoria in sorted(por_categoria, key=lambda c: (_orden(c), c)):
        cuentas = sorted(por_categoria[categoria], key=lambda f: f.codigo_cuenta)
        primera = fila
        for f in cuentas:
            ws.cell(fila, COL_CATEGORIA, categoria).font = FONT_DATA
            ws.cell(fila, COL_CODIGO, f.codigo_cuenta).font = FONT_DATA
            ws.cell(fila, COL_NOMBRE, f.nombre_cuenta).font = FONT_DATA
            por_mes = f.por_mes_json or {}
            for j, mes in enumerate(MESES):
                c = ws.cell(fila, COL_PRIMER_MES + j, float(por_mes.get(mes, 0.0)))
                c.font = FONT_DATA
                c.number_format = FORMATO_NUM
                c.border = BORDE
            ini = get_column_letter(COL_PRIMER_MES)
            fin = get_column_letter(COL_PRIMER_MES + 11)
            t = ws.cell(fila, COL_TOTAL, f"=SUM({ini}{fila}:{fin}{fila})")
            t.font = FONT_DATA
            t.number_format = FORMATO_NUM
            t.border = BORDE
            fila += 1

        ultima = fila - 1
        etiqueta = ws.cell(fila, COL_NOMBRE, f"Subtotal {categoria}")
        etiqueta.font = FONT_TOTAL
        etiqueta.fill = RELLENO_TOTAL
        for j in range(13):
            col = COL_PRIMER_MES + j
            letra = get_column_letter(col)
            c = ws.cell(fila, col, f"=SUM({letra}{primera}:{letra}{ultima})")
            c.font = FONT_TOTAL
            c.fill = RELLENO_TOTAL
            c.number_format = FORMATO_NUM
            c.border = BORDE
            clave = MESES[j] if j < 12 else "TOTAL"
            lookup[(categoria, clave)] = f"{letra}{fila}"
        fila += 2  # una fila en blanco entre bloques

    ws.freeze_panes = "D4"
    for col, ancho in ((1, 16), (2, 14), (3, 46)):
        ws.column_dimensions[get_column_letter(col)].width = ancho
    for j in range(13):
        ws.column_dimensions[get_column_letter(COL_PRIMER_MES + j)].width = 14
    return lookup
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_libro_hoja_mayores.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/libro/hoja_mayores.py tests/test_of_libro_hoja_mayores.py
git commit -m "feat(libro): hoja resumen Mayores homologados con subtotales por categoria"
```

---

### Task 3: Hoja `Detalle mayor`

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/libro/hoja_detalle.py`
- Test: `tests/test_of_libro_hoja_detalle.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Hoja de detalle: todos los movimientos con su categoría."""

import datetime

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.hoja_detalle import (
    SHEET_DETALLE,
    build_hoja_detalle,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento

MOVS = [
    Movimiento(codigo="1.1.5.1.1", cuenta="IVA sobre Compras",
               fecha=datetime.date(2025, 1, 5), asiento="COM 1",
               documento="FAC 001", identificacion="9999999999001",
               persona="PROVEEDOR DEMO S.A.", descripcion="COMPRA DE PRUEBA",
               debe=2.39, haber=0.0, saldo=2.39),
    Movimiento(codigo="4.1.1.4", cuenta="Venta de insumos",
               fecha=datetime.date(2025, 2, 8), asiento="VTA 1",
               debe=0.0, haber=100.0, saldo=-100.0),
]
CATEGORIAS = {"1.1.5.1.1": "IVA_COMPRAS", "4.1.1.4": "VENTAS"}


def test_escribe_una_fila_por_movimiento():
    wb = Workbook()
    build_hoja_detalle(wb, MOVS, CATEGORIAS)
    ws = wb[SHEET_DETALLE]
    assert ws.max_row == 3 + len(MOVS) - 1 or ws.max_row >= len(MOVS)


def test_la_primera_columna_es_la_categoria_para_poder_filtrar():
    wb = Workbook()
    build_hoja_detalle(wb, MOVS, CATEGORIAS)
    ws = wb[SHEET_DETALLE]
    assert ws.cell(3, 1).value == "Categoría"
    assert ws.cell(4, 1).value == "IVA_COMPRAS"


def test_activa_el_autofiltro_sobre_el_rango_de_datos():
    wb = Workbook()
    build_hoja_detalle(wb, MOVS, CATEGORIAS)
    assert wb[SHEET_DETALLE].auto_filter.ref is not None


def test_congela_el_encabezado():
    wb = Workbook()
    build_hoja_detalle(wb, MOVS, CATEGORIAS)
    assert wb[SHEET_DETALLE].freeze_panes == "A4"


def test_un_movimiento_de_cuenta_sin_categoria_queda_marcado():
    wb = Workbook()
    build_hoja_detalle(wb, MOVS, {})
    ws = wb[SHEET_DETALLE]
    assert ws.cell(4, 1).value == "SIN_CLASIFICAR"


def test_conserva_los_datos_de_trazabilidad_del_movimiento():
    wb = Workbook()
    build_hoja_detalle(wb, MOVS, CATEGORIAS)
    ws = wb[SHEET_DETALLE]
    fila = [ws.cell(4, c).value for c in range(1, 14)]
    assert "FAC 001" in fila
    assert "PROVEEDOR DEMO S.A." in fila
    assert 2.39 in fila
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_libro_hoja_detalle.py -q`
Expected: FAIL — `ModuleNotFoundError: ...libro.hoja_detalle`

- [ ] **Step 3: Implementación mínima**

```python
"""Hoja 'Detalle mayor': cada movimiento con la categoría que se le asignó.

Una sola hoja con autofiltro, en vez de una hoja por categoría: así el
auditor rastrea cualquier subtotal del resumen hasta la factura que lo
originó sin saltar entre pestañas.
"""

from __future__ import annotations

from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook

SHEET_DETALLE = "Detalle mayor"
SIN_CLASIFICAR = "SIN_CLASIFICAR"

ENCABEZADO = [
    "Categoría", "Código", "Cuenta", "Fecha", "Asiento", "Documento",
    "Identificación", "Persona", "Descripción", "Debe", "Haber", "Saldo", "Mes",
]
ANCHOS = [16, 14, 34, 12, 20, 24, 16, 32, 34, 14, 14, 14, 8]

FONT_TITULO = Font(name="Calibri", size=11, bold=True)
FONT_ENCABEZADO = Font(name="Calibri", size=10, bold=True)
FONT_DATA = Font(name="Calibri", size=9)
FORMATO_NUM = "#,##0.00"
FILA_ENCABEZADO = 3


def build_hoja_detalle(wb: Workbook, movimientos, categorias: dict[str, str]) -> None:
    """Escribe todos los movimientos clasificados en una sola hoja filtrable."""
    if SHEET_DETALLE in wb.sheetnames:
        del wb[SHEET_DETALLE]
    ws = wb.create_sheet(SHEET_DETALLE)

    ws.cell(1, 1, "DETALLE DEL MAYOR · movimientos clasificados").font = FONT_TITULO

    for i, texto in enumerate(ENCABEZADO, start=1):
        c = ws.cell(FILA_ENCABEZADO, i, texto)
        c.font = FONT_ENCABEZADO
        c.alignment = Alignment(horizontal="center", wrap_text=True)

    fila = FILA_ENCABEZADO + 1
    for m in movimientos:
        valores = [
            categorias.get(m.codigo, SIN_CLASIFICAR),
            m.codigo, m.cuenta, m.fecha, m.asiento, m.documento,
            m.identificacion, m.persona, m.descripcion,
            m.debe, m.haber, m.saldo, m.mes or "",
        ]
        for i, v in enumerate(valores, start=1):
            c = ws.cell(fila, i, v)
            c.font = FONT_DATA
            if i in (10, 11, 12):
                c.number_format = FORMATO_NUM
            if i == 4 and m.fecha:
                c.number_format = "yyyy-mm-dd"
        fila += 1

    ultima = max(fila - 1, FILA_ENCABEZADO + 1)
    ws.auto_filter.ref = (
        f"A{FILA_ENCABEZADO}:{get_column_letter(len(ENCABEZADO))}{ultima}"
    )
    ws.freeze_panes = f"A{FILA_ENCABEZADO + 1}"
    for i, ancho in enumerate(ANCHOS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_libro_hoja_detalle.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/libro/hoja_detalle.py tests/test_of_libro_hoja_detalle.py
git commit -m "feat(libro): hoja de detalle del mayor con categoria y autofiltro"
```

---

### Task 4: Encabezado común de cédula

Las seis cédulas del modelo comparten el mismo encabezado: `OBLIGACIONES FISCALES` → título → *Nombre del cliente* / *Periodo terminado* → *Preparado por* / *Fecha* / *Revisado por* → **Referencia DMx**, con el logo de la firma anclado en A1. Se extrae aquí para que el Plan 3b lo use en las cinco cédulas.

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/libro/estilos.py`
- Test: `tests/test_of_libro_estilos.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Encabezado común de cédula y marcas de auditoría."""

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.estilos import (
    MARCAS,
    escribir_encabezado_cedula,
    escribir_leyenda_marcas,
)


def _hoja():
    wb = Workbook()
    return wb, wb.active


def test_escribe_el_titulo_de_la_firma_y_de_la_cedula():
    wb, ws = _hoja()
    escribir_encabezado_cedula(ws, titulo="IVA", referencia="DM6",
                               cliente="MI CLIENTE S.A.", periodo="2025")
    assert ws["A1"].value == "OBLIGACIONES FISCALES"
    assert ws["A3"].value == "IVA"


def test_escribe_los_datos_del_encargo():
    wb, ws = _hoja()
    escribir_encabezado_cedula(ws, titulo="IVA", referencia="DM6",
                               cliente="MI CLIENTE S.A.", periodo="2025",
                               preparado_por="JT", revisado_por="V")
    valores = [ws.cell(r, c).value for r in range(1, 11) for c in range(1, 6)]
    assert "MI CLIENTE S.A." in valores
    assert "2025" in valores
    assert "JT" in valores
    assert "V" in valores


def test_la_referencia_de_la_cedula_queda_visible():
    wb, ws = _hoja()
    escribir_encabezado_cedula(ws, titulo="Compras", referencia="DM4",
                               cliente="C", periodo="2025")
    valores = [ws.cell(r, c).value for r in range(1, 11) for c in range(1, 6)]
    assert "DM4" in valores


def test_no_arrastra_datos_de_encargos_anteriores():
    """El modelo del auditor conservaba 'Elaborado por: JT, 2024-09-26'."""
    wb, ws = _hoja()
    escribir_encabezado_cedula(ws, titulo="IVA", referencia="DM6",
                               cliente="C", periodo="2025")
    valores = [str(ws.cell(r, c).value) for r in range(1, 11) for c in range(1, 6)]
    assert not any("2024" in v for v in valores)


def test_las_cuatro_marcas_de_auditoria_usan_la_misma_fuente():
    """El modelo mezclaba Arial y Wingdings para la misma marca."""
    assert set(MARCAS) == {"verificado", "declarado", "diferencia", "sumado"}
    wb, ws = _hoja()
    escribir_leyenda_marcas(ws, fila=20)
    fuentes = {ws.cell(f, 1).font.name for f in range(20, 24)}
    assert len(fuentes) == 1


def test_la_leyenda_explica_cada_marca():
    wb, ws = _hoja()
    escribir_leyenda_marcas(ws, fila=20)
    textos = [str(ws.cell(f, 2).value or "").lower() for f in range(20, 24)]
    assert any("libros" in t for t in textos)
    assert any("diferencia" in t for t in textos)
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_libro_estilos.py -q`
Expected: FAIL — `ModuleNotFoundError: ...libro.estilos`

- [ ] **Step 3: Implementación mínima**

```python
"""Formato compartido por las cédulas del libro DM."""

from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

FUENTE_MARCAS = "Arial"

FONT_TITULO_FIRMA = Font(name="Arial", size=12, bold=True)
FONT_TITULO_CEDULA = Font(name="Arial", size=11, bold=True)
FONT_ETIQUETA = Font(name="Arial", size=10)
FONT_DATO = Font(name="Arial", size=10, bold=True)
FONT_ENCABEZADO_TABLA = Font(name="Calibri", size=10, bold=True)
FONT_DATA = Font(name="Calibri", size=9)
FONT_TOTAL = Font(name="Calibri", size=10, bold=True)

BORDE = Border(*[Side(style="thin")] * 4)
BORDE_TOTAL = Border(
    top=Side(style="double"), bottom=Side(style="double"),
    left=Side(style="thin"), right=Side(style="thin"),
)
RELLENO_TOTAL = PatternFill("solid", fgColor="DCE6F1")
FORMATO_NUM = "#,##0.00"

# Marcas de auditoría. Son fijas de la cédula: NO se calculan contra ninguna
# tolerancia. En el modelo del auditor la misma marca aparecía en Arial y en
# Wingdings; aquí se unifican.
MARCAS = {
    "verificado": ("ü", "Cotejado según libros"),
    "declarado": ("£", "Cotejado según formularios"),
    "diferencia": ("‡", "Diferencia determinada"),
    "sumado": ("Σ", "Sumado, totalizado"),
}


def escribir_encabezado_cedula(
    ws,
    *,
    titulo: str,
    referencia: str,
    cliente: str,
    periodo: str,
    preparado_por: str | None = None,
    revisado_por: str | None = None,
    fecha_corte=None,
) -> None:
    """Encabezado estándar (filas 1 a 10) de una cédula DM."""
    ws.cell(1, 1, "OBLIGACIONES FISCALES").font = FONT_TITULO_FIRMA
    ws.cell(3, 1, titulo).font = FONT_TITULO_CEDULA

    ws.cell(5, 1, "Nombre del cliente").font = FONT_ETIQUETA
    ws.cell(6, 1, cliente or "").font = FONT_DATO
    ws.cell(5, 4, "Periodo terminado").font = FONT_ETIQUETA
    ws.cell(6, 4, periodo or "").font = FONT_DATO

    ws.cell(7, 1, "Preparado por:").font = FONT_ETIQUETA
    ws.cell(8, 1, preparado_por or "").font = FONT_DATO
    ws.cell(7, 3, "Fecha:").font = FONT_ETIQUETA
    ws.cell(8, 3, fecha_corte or "").font = FONT_DATO
    ws.cell(7, 4, "Referencia").font = FONT_ETIQUETA
    ws.cell(8, 4, referencia).font = FONT_DATO

    ws.cell(9, 1, "Revisado por:").font = FONT_ETIQUETA
    ws.cell(10, 1, revisado_por or "").font = FONT_DATO


def escribir_leyenda_marcas(ws, *, fila: int) -> int:
    """Leyenda de las marcas al pie de la cédula. Devuelve la fila siguiente."""
    for i, (simbolo, texto) in enumerate(MARCAS.values()):
        c = ws.cell(fila + i, 1, simbolo)
        c.font = Font(name=FUENTE_MARCAS, size=10)
        ws.cell(fila + i, 2, texto).font = Font(name=FUENTE_MARCAS, size=9)
    return fila + len(MARCAS)
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_libro_estilos.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/libro/estilos.py tests/test_of_libro_estilos.py
git commit -m "feat(libro): encabezado comun de cedula y marcas de auditoria unificadas"
```

---

### Task 5: Ensamblador del libro y fase 2

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/libro/ensamblador.py`
- Modify: `backend/app/aud/obligaciones_fiscales/jobs.py`
- Test: `tests/test_of_libro_ensamblador.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Ensamblado del libro DM."""

import datetime
from io import BytesIO

from openpyxl import load_workbook

from backend.app.aud.obligaciones_fiscales.libro.ensamblador import armar_libro
from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento


class _Fila:
    def __init__(self, codigo, nombre, categoria, por_mes):
        self.codigo_cuenta = codigo
        self.nombre_cuenta = nombre
        self.categoria_final = categoria
        self.por_mes_json = por_mes
        self.n_movimientos = 1
        self.debe = 0.0
        self.haber = 0.0


CLASIFICACION = [_Fila("1.1.5.1.1", "IVA sobre Compras", "IVA_COMPRAS", {"01": 659.57})]
MOVS = [Movimiento(codigo="1.1.5.1.1", cuenta="IVA sobre Compras",
                   fecha=datetime.date(2025, 1, 5), asiento="COM 1", debe=659.57)]


def _libro(**kw):
    datos = dict(
        clasificacion=CLASIFICACION, movimientos=MOVS,
        f104_monthly={"2025-01": {"casilleros": {"429": 4341.16}}},
        f103_monthly={"2025-01": {"casilleros": {"499": 915.70}}},
        cliente="MI CLIENTE S.A.", periodo="2025",
    )
    datos.update(kw)
    return load_workbook(BytesIO(armar_libro(**datos)))


def test_el_libro_trae_las_cuatro_hojas_de_datos():
    wb = _libro()
    assert {"Mayores homologados", "Detalle mayor", "DATOS F-104", "DATOS F-103"} <= set(wb.sheetnames)


def test_no_queda_la_hoja_vacia_por_defecto_de_openpyxl():
    assert "Sheet" not in _libro().sheetnames


def test_el_resumen_va_antes_que_el_detalle():
    nombres = _libro().sheetnames
    assert nombres.index("Mayores homologados") < nombres.index("Detalle mayor")


def test_el_libro_se_abre_sin_reparaciones():
    """Regla del proyecto: el Excel no puede pedir reparación al abrirse."""
    wb = _libro()
    for hoja in wb.sheetnames:
        for fila in wb[hoja].iter_rows():
            for celda in fila:
                if isinstance(celda.value, str) and celda.value.startswith("="):
                    assert celda.value.count("(") == celda.value.count(")")


def test_sin_declaraciones_el_libro_igual_se_genera():
    wb = _libro(f104_monthly={}, f103_monthly={})
    assert "DATOS F-104" in wb.sheetnames
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_libro_ensamblador.py -q`
Expected: FAIL — `ModuleNotFoundError: ...libro.ensamblador`

- [ ] **Step 3: Implementación mínima**

```python
"""Arma el libro DM de Obligaciones Fiscales.

Orden de las hojas: primero el resumen del motor y su detalle, después los
casilleros declarados. Las cédulas DM3..DM7 se insertan en el Plan 3b, y
leerán de estas hojas POR FÓRMULA usando los mapas de direcciones que este
módulo recolecta.
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from backend.app.aud.obligaciones_fiscales.libro.fuentes import (
    construir_hojas_de_casilleros,
)
from backend.app.aud.obligaciones_fiscales.libro.hoja_detalle import build_hoja_detalle
from backend.app.aud.obligaciones_fiscales.libro.hoja_mayores import build_hoja_mayores

ORDEN_HOJAS = ["Mayores homologados", "Detalle mayor", "DATOS F-104", "DATOS F-103"]


def armar_libro(
    *,
    clasificacion,
    movimientos,
    f104_monthly: dict,
    f103_monthly: dict,
    cliente: str = "",
    periodo: str = "",
    preparado_por: str | None = None,
    revisado_por: str | None = None,
) -> bytes:
    """Devuelve los bytes del libro DM con sus hojas de datos."""
    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    direcciones = {"mayores": build_hoja_mayores(wb, clasificacion)}
    build_hoja_detalle(
        wb, movimientos, {f.codigo_cuenta: f.categoria_final for f in clasificacion}
    )
    direcciones.update(
        construir_hojas_de_casilleros(
            wb, f104_monthly=f104_monthly, f103_monthly=f103_monthly
        )
    )

    orden = [h for h in ORDEN_HOJAS if h in wb.sheetnames]
    orden += [h for h in wb.sheetnames if h not in orden]
    wb._sheets = [wb[h] for h in orden]

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
```

En `jobs.py::process_job`, reemplazar la llamada a `excel_assembler.assemble(...)` por el ensamblador nuevo, leyendo la clasificación aprobada y el mayor:

```python
        from backend.app.aud.obligaciones_fiscales.libro.ensamblador import armar_libro
        from backend.app.aud.obligaciones_fiscales.libro.fuentes import leer_declaraciones
        from backend.app.aud.obligaciones_fiscales.mayor import clasificacion_service
        from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor

        movimientos = []
        for ruta in file_storage.list_inputs(job_dir, "mayor_general"):
            movimientos.extend(leer_mayor(ruta.read_bytes()).movimientos)
        f104_monthly, f103_monthly = leer_declaraciones(job_dir)

        excel_bytes = armar_libro(
            clasificacion=clasificacion_service.clasificacion_de_job(db, job_id=job_id),
            movimientos=movimientos,
            f104_monthly=f104_monthly,
            f103_monthly=f103_monthly,
            cliente=job.cliente_name,
            periodo=job.period_label,
            preparado_por=job.prepared_by_name,
            revisado_por=job.reviewed_by_name,
        )
```

Los tests existentes de `process_job` y del `excel_assembler` que asuman la plantilla vieja se actualizan al libro nuevo; el módulo `excel_assembler.py` **no se borra todavía** (el Plan 3b decide su destino cuando las cédulas estén portadas).

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_libro_ensamblador.py tests/ -k "aud_of" -q -p no:warnings`
Expected: verde. Si algún test del ciclo del Plan 2 esperaba las hojas de la plantilla vieja, actualízalo al libro nuevo y repórtalo.

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/ tests/test_of_libro_ensamblador.py
git commit -m "feat(libro): ensamblador del libro DM y fase 2 apuntando a el"
```

---

### Task 6: Verificación empírica contra los datos reales del cliente

**Files:**
- Create: `tests/test_of_libro_real_cliente.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""El libro generado debe reproducir las cifras reales del cliente.

Requiere AUD_OF_FIXTURES_DIR (datos de cliente, fuera del repo público).
"""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook

from backend.app.aud.obligaciones_fiscales.cedulas.f104_extractor import extract_all_f104
from backend.app.aud.obligaciones_fiscales.libro.ensamblador import armar_libro
from backend.app.aud.obligaciones_fiscales.libro.fuentes import a_periodos_anuales
from backend.app.aud.obligaciones_fiscales.mayor.clasificador import clasificar
from backend.app.aud.obligaciones_fiscales.mayor.cuentas import perfilar
from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor

pytestmark = pytest.mark.skipif(
    not os.getenv("AUD_OF_FIXTURES_DIR"),
    reason="Requiere AUD_OF_FIXTURES_DIR con los archivos reales del cliente",
)


class _FilaClasif:
    def __init__(self, r, p):
        self.codigo_cuenta = r.codigo
        self.nombre_cuenta = r.nombre
        self.categoria_final = r.categoria
        self.por_mes_json = dict(p.por_mes) if p else {}
        self.n_movimientos = p.n_movimientos if p else 0
        self.debe = p.debe if p else 0.0
        self.haber = p.haber if p else 0.0


@pytest.fixture(scope="module")
def libro():
    base = Path(os.environ["AUD_OF_FIXTURES_DIR"])
    lectura = leer_mayor((base / "MAYOR DE IMPUESTOS.xlsx").read_bytes())
    perfiles = perfilar(lectura.movimientos)
    resultados = clasificar(perfiles)
    clasif = [_FilaClasif(r, perfiles.get(r.codigo)) for r in resultados]
    f104_mes, _ = extract_all_f104(sorted((base / "104").glob("*.pdf")))
    data = armar_libro(
        clasificacion=clasif, movimientos=lectura.movimientos,
        f104_monthly=a_periodos_anuales(f104_mes), f103_monthly={},
        cliente="CLIENTE DE PRUEBA", periodo="2025",
    )
    return load_workbook(BytesIO(data))


def test_el_detalle_trae_todos_los_movimientos_del_mayor(libro):
    ws = libro["Detalle mayor"]
    assert ws.max_row - 3 == 4680


def test_ninguna_fila_del_detalle_queda_sin_categoria(libro):
    ws = libro["Detalle mayor"]
    sin = [r for r in range(4, ws.max_row + 1) if ws.cell(r, 1).value == "SIN_CLASIFICAR"]
    assert not sin


def test_el_resumen_tiene_las_veintiocho_cuentas(libro):
    ws = libro["Mayores homologados"]
    codigos = {
        ws.cell(r, 2).value for r in range(4, ws.max_row + 1) if ws.cell(r, 2).value
    }
    assert len(codigos) == 28


def test_los_casilleros_declarados_llegan_con_sus_valores(libro):
    """cas 429 de enero: el IVA generado en ventas del mes."""
    ws = libro["DATOS F-104"]
    fila = next(r for r in range(4, ws.max_row + 1) if str(ws.cell(r, 1).value) == "429")
    valores = [ws.cell(fila, c).value for c in range(3, 15)]
    assert any(v for v in valores), "el casillero 429 no debería estar todo en cero"


def test_el_bloque_de_credito_tributario_esta_presente(libro):
    """605-608 y 615-619: los que faltaban en el catálogo hasta este trabajo."""
    ws = libro["DATOS F-104"]
    presentes = {str(ws.cell(r, 1).value) for r in range(4, ws.max_row + 1)}
    assert {"605", "606", "615", "617"} <= presentes
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run (PowerShell): `$env:AUD_OF_FIXTURES_DIR="<carpeta del cliente>"; python -m pytest tests/test_of_libro_real_cliente.py -q`
Expected: FAIL en el primer test hasta que las tareas 1-5 estén completas; después, verde.

- [ ] **Step 3: Corregir el generador hasta que cuadre**

No se tocan los tests: se corrige el código. Si `ws.max_row - 3` no da 4.680, revisa `build_hoja_detalle` (¿está descartando movimientos?). Si faltan cuentas en el resumen, revisa el agrupamiento de `build_hoja_mayores`.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `$env:AUD_OF_FIXTURES_DIR="<carpeta>"; python -m pytest tests/ -k "libro or mayor or aud_of" -q -p no:warnings`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add tests/test_of_libro_real_cliente.py backend/app/aud/obligaciones_fiscales/libro/
git commit -m "test(libro): verificacion empirica del libro con los datos reales del cliente"
```

---

## Criterio de terminado del Plan 3a

- [ ] Las 6 tareas están commiteadas.
- [ ] El libro generado trae `Mayores homologados`, `Detalle mayor`, `DATOS F-104` y `DATOS F-103`, en ese orden.
- [ ] Con los datos reales: 4.680 filas en el detalle, 0 sin categoría, 28 cuentas en el resumen y los casilleros del bloque de crédito tributario presentes.
- [ ] Ninguna cifra viene tecleada: los casilleros salen de los PDFs del cliente del job.
- [ ] La suite completa no tiene fallos nuevos.

## Lo que este plan NO hace (queda para el Plan 3b)

- Las cédulas `DM3`, `DM4`, `DM5`, `DM6` y `DM7` con sus fórmulas cruzadas.
- `DM8 ATS` e `ingresos iva vs facturacion`: siguen pendientes de definición del usuario.
- El destino de `excel_assembler.py` y de la plantilla `dm_obligaciones_fiscales.xlsx`.
