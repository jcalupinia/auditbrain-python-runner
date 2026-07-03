# Extractor EEFF multi-formato y multi-período — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que FIN/CFO lea estados financieros resumidos por nombre de concepto (sin códigos ni plantilla), con N períodos variables/mixtos (parcial 5m vs anual 12m), y exponga las comparaciones encadenadas ESF y ERI — sin romper los formatos ya soportados.

**Architecture:** Se añade un detector de formato y un extractor "resumido por nombre" nuevos; `extract_balance_interno` se vuelve una fachada que detecta y delega (el camino codificado queda intacto). Piezas puras y aisladas: períodos, layout, mapeo por nombre, comparaciones.

**Tech Stack:** Python 3, pandas, openpyxl, pytest. Todo bajo `backend/app/tax/planificacion_utilidades/`.

**Confidencialidad:** el repo es PÚBLICO. Los tests usan **fixtures sintéticos** (números inventados, misma estructura). La validación contra `EEFF SIGMAN 2026.xlsx` real se hace **localmente** en la Task de cierre y se reporta; NO se commitea data del cliente.

---

## Archivos

- Create: `backend/app/tax/planificacion_utilidades/parsers/periodos.py` — clasifica una cabecera → label/tipo/meses/año.
- Create: `backend/app/tax/planificacion_utilidades/parsers/layout.py` — detecta el formato del libro.
- Create: `backend/app/tax/planificacion_utilidades/parsers/mapeo_nombres.py` — nombre de concepto → (sección, clave NIIF).
- Create: `backend/app/tax/planificacion_utilidades/parsers/balance_resumido_nombre.py` — extractor nuevo.
- Create: `backend/app/tax/planificacion_utilidades/comparaciones.py` — arma pares de comparación.
- Modify: `backend/app/tax/planificacion_utilidades/parsers/balance_interno.py` — fachada detect+delega.
- Create: `backend/tests/fixtures/eeff_sintetico.py` — genera libros sintéticos en memoria.
- Test: `backend/tests/test_eeff_periodos.py`, `test_eeff_layout.py`, `test_eeff_mapeo.py`, `test_eeff_resumido_nombre.py`, `test_eeff_comparaciones.py`, `test_eeff_fachada_sin_regresion.py`.

---

### Task 1: Clasificación de períodos

**Files:**
- Create: `backend/app/tax/planificacion_utilidades/parsers/periodos.py`
- Test: `backend/tests/test_eeff_periodos.py`

- [ ] **Step 1: Write the failing test**

```python
import datetime as dt
from backend.app.tax.planificacion_utilidades.parsers.periodos import clasificar_periodo

def test_fecha_es_parcial_con_meses():
    p = clasificar_periodo(dt.datetime(2026, 5, 1))
    assert p == {"label": "may-26", "tipo": "parcial", "meses": 5, "anio": 2026}

def test_anio_entero_es_anual():
    assert clasificar_periodo(2025) == {"label": "2025", "tipo": "anual", "meses": 12, "anio": 2025}

def test_anio_texto_es_anual():
    assert clasificar_periodo("2024") == {"label": "2024", "tipo": "anual", "meses": 12, "anio": 2024}

def test_iso_string_es_parcial():
    assert clasificar_periodo("2025-05-01")["tipo"] == "parcial"
    assert clasificar_periodo("2025-05-01")["meses"] == 5

def test_no_periodo_devuelve_none():
    assert clasificar_periodo("Activo") is None
    assert clasificar_periodo(None) is None
    assert clasificar_periodo(123.45) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eeff_periodos.py -v`
Expected: FAIL (ModuleNotFoundError / no `clasificar_periodo`).

- [ ] **Step 3: Write minimal implementation**

```python
"""Clasificación de cabeceras de período de un estado financiero."""
from __future__ import annotations
import re
import datetime as dt

_MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

def _de_fecha(anio: int, mes: int) -> dict:
    return {"label": f"{_MESES[mes]}-{str(anio)[2:]}", "tipo": "parcial", "meses": mes, "anio": anio}

def clasificar_periodo(cell):
    """Devuelve {label,tipo,meses,anio} o None si la celda no es un período."""
    if isinstance(cell, dt.datetime):
        return _de_fecha(cell.year, cell.month)
    if isinstance(cell, dt.date):
        return _de_fecha(cell.year, cell.month)
    if isinstance(cell, bool):
        return None
    if isinstance(cell, int) and 1900 < cell < 2100:
        return {"label": str(cell), "tipo": "anual", "meses": 12, "anio": cell}
    if isinstance(cell, str):
        s = cell.strip()
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return _de_fecha(int(m.group(1)), int(m.group(2)))
        if s.isdigit() and len(s) == 4 and 1900 < int(s) < 2100:
            return {"label": s, "tipo": "anual", "meses": 12, "anio": int(s)}
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eeff_periodos.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tax/planificacion_utilidades/parsers/periodos.py backend/tests/test_eeff_periodos.py
git commit -m "feat(fin): clasificacion de periodos parcial/anual con meses"
```

---

### Task 2: Fixture sintético

**Files:**
- Create: `backend/tests/fixtures/eeff_sintetico.py`

- [ ] **Step 1: Write the fixture helper (no test; se usa en tasks siguientes)**

```python
"""Genera libros Excel sintéticos (números inventados) que imitan la estructura
de un EEFF resumido por nombre: ESF (4 períodos: parcial + 3 anuales) y ERI
(5 períodos: 2 parciales + 3 anuales), con tipos de cabecera MEZCLADOS y un
descuadre deliberado. NO contiene datos de clientes."""
from __future__ import annotations
import io
import datetime as dt
from openpyxl import Workbook

def libro_resumido_nombre() -> bytes:
    wb = Workbook(); ws = wb.active; ws.title = "Hoja1"
    filas = [
        ["ESTADO DE SITUACIÓN FINANCIERA RESUMIDO"],
        ["Activo", dt.datetime(2026, 5, 1), "2025", "2024", 2023],   # tipos mezclados a propósito
        ["Efectivo y equivalentes de efectivo", 100, 90, 80, 70],
        ["Cuentas por cobrar comerciales", 200, 150, 160, 170],
        ["Inventario", 300, 320, 250, 240],
        ["Total activos corrientes", 600, 560, 490, 480],
        ["Propiedades y equipo", 400, 410, 420, 430],
        ["TOTAL ACTIVOS", 1000, 970, 910, 910],
        ["Pasivo y patrimonio", dt.datetime(2026, 5, 1), "2025", "2024", 2023],
        ["Cuentas por pagar comerciales", 250, 240, 300, 400],
        ["Total pasivos", 250, 240, 300, 400],
        ["Capital", 500, 500, 500, 500],
        ["Resultado del ejercicio", 250, 231, 110, 10],  # 2025: 231 -> descuadre de 1 (970 vs 971)
        ["TOTAL PASIVO + PATRIMONIO", 1000, 971, 910, 910],
        [],
        ["ESTADO DE RESULTADO INTEGRAL RESUMIDO"],
        ["Concepto", dt.datetime(2026, 5, 1), dt.datetime(2025, 5, 1), "2025", "2024", 2023],
        ["Ingresos ordinarios", 500, 450, 1200, 1500, 1400],
        ["Costo de venta", -300, -280, -700, -900, -850],
        ["De administración, ventas y otros", -150, -120, -350, -400, -380],
        ["Participación trabajadores", 0, 0, -20, -30, -25],
        ["Impuesto a la renta", 0, 0, -30, -40, -35],
        ["Resultado del ejercicio", 50, 50, 100, 130, 110],
    ]
    for r in filas:
        ws.append(r)
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/fixtures/eeff_sintetico.py
git commit -m "test(fin): fixture sintetico de EEFF resumido por nombre"
```

---

### Task 3: Detector de layout

**Files:**
- Create: `backend/app/tax/planificacion_utilidades/parsers/layout.py`
- Test: `backend/tests/test_eeff_layout.py`

- [ ] **Step 1: Write the failing test**

```python
import io
import pandas as pd
from backend.app.tax.planificacion_utilidades.parsers.layout import detect_layout
from backend.tests.fixtures.eeff_sintetico import libro_resumido_nombre

def _df(bytes_):
    return pd.ExcelFile(io.BytesIO(bytes_), engine="openpyxl").parse("Hoja1", header=None)

def test_detecta_resumido_nombre():
    assert detect_layout(_df(libro_resumido_nombre())) == "resumido_nombre"

def test_detecta_codificado():
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Cuenta", 2024, 2025])
    ws.append(["1", "ACTIVO", 100, 110])
    ws.append(["1.1.01", "Caja", 100, 110])
    buf = io.BytesIO(); wb.save(buf)
    assert detect_layout(_df(buf.getvalue())) == "codificado"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eeff_layout.py -v`
Expected: FAIL (no module `layout`).

- [ ] **Step 3: Write minimal implementation**

```python
"""Detecta el formato de un libro de EEFF."""
from __future__ import annotations
import re
from .periodos import clasificar_periodo

def _segs(code):
    return [p.strip() for p in re.split(r"[-.]", str(code)) if p.strip() != ""]

def detect_layout(df) -> str:
    """'codificado' | 'plantilla' | 'resumido_nombre'."""
    hay_codigos = False
    hay_periodos = False
    for _, row in df.iterrows():
        vals = row.tolist()
        c0 = _segs(vals[0]) if vals and vals[0] is not None else []
        if c0 and c0[0] in ("1", "2", "3", "4", "5", "6") and c0[0].isdigit():
            hay_codigos = True
        for v in vals[1:]:
            if clasificar_periodo(v):
                hay_periodos = True
        for v in vals:
            if isinstance(v, str) and v.strip().lower() == "clave":
                return "plantilla"
    if hay_codigos:
        return "codificado"
    if hay_periodos:
        return "resumido_nombre"
    return "resumido_nombre"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eeff_layout.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tax/planificacion_utilidades/parsers/layout.py backend/tests/test_eeff_layout.py
git commit -m "feat(fin): detector de layout codificado/plantilla/resumido_nombre"
```

---

### Task 4: Mapeo por nombre → rubro NIIF

**Files:**
- Create: `backend/app/tax/planificacion_utilidades/parsers/mapeo_nombres.py`
- Test: `backend/tests/test_eeff_mapeo.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.app.tax.planificacion_utilidades.parsers.mapeo_nombres import mapear_concepto

def test_activos_no_se_fusionan():
    assert mapear_concepto("Efectivo y equivalentes de efectivo")[1] == "efectivo"
    assert mapear_concepto("Inventario")[1] == "inventario"
    assert mapear_concepto("Propiedades y equipo")[1] == "ppe"
    assert mapear_concepto("Cuentas por cobrar comerciales")[1] == "cxc"

def test_pasivo_y_patrimonio():
    assert mapear_concepto("Cuentas por pagar comerciales")[1] == "cxp"
    assert mapear_concepto("Anticipos de clientes")[1] == "anticipos"
    assert mapear_concepto("Capital")[1] == "capital"
    assert mapear_concepto("Resultado del ejercicio")[1] == "utilEjercicio"

def test_resultados():
    assert mapear_concepto("Ingresos ordinarios")[1] == "ventas"
    assert mapear_concepto("Costo de venta")[1] == "costo"
    assert mapear_concepto("De administración, ventas y otros")[1] == "gAdmin"

def test_no_mapeado_devuelve_none():
    assert mapear_concepto("Concepto rarísimo XYZ") == (None, None)

def test_totales_se_reconocen_como_total():
    assert mapear_concepto("TOTAL ACTIVOS")[0] == "total"
    assert mapear_concepto("Total pasivos corrientes")[0] == "total"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eeff_mapeo.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write minimal implementation**

```python
"""Mapea el NOMBRE de un concepto de un EEFF resumido a (seccion, clave).

Diccionario EXPLÍCITO y auditado — sin herencia stateful (política CLAUDE.md).
seccion ∈ {'activo','pasivo','patrimonio','resultado','total'}.
"""
from __future__ import annotations
import unicodedata

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())

# (subcadena normalizada, seccion, clave). Primera coincidencia gana; el orden
# importa: reglas más específicas antes que las genéricas.
_REGLAS = [
    ("TOTAL", "total", None),  # cualquier 'total/subtotal' se usa para cuadrar
    ("EFECTIVO", "activo", "efectivo"),
    ("INVENTARIO", "activo", "inventario"),
    ("PROPIEDAD", "activo", "ppe"),
    ("IMPUESTOS DIFERIDOS", "activo", "actImpDif"),
    ("IMPUESTOS CORRIENTES", "activo", "impRec"),
    ("COBRAR", "activo", "cxc"),
    ("PAGOS ANTICIPADOS", "activo", "otrasCxc"),
    ("PAGAR RELACIONAD", "pasivo", "cxpRel"),
    ("IMPUESTO DIFERIDO", "pasivo", "pasImpDif"),
    ("PAGAR", "pasivo", "cxp"),
    ("ANTICIPOS DE CLIENTES", "pasivo", "anticipos"),
    ("BENEFICIOS SOCIALES", "pasivo", "benef"),
    ("OBLIGACIONES ACUMULADAS", "pasivo", "benef"),
    ("BENEFICIOS DEFINIDOS", "pasivo", "benefPost"),
    ("IMPUESTOS CORRIENTES", "pasivo", "impPagar"),
    ("CAPITAL", "patrimonio", "capital"),
    ("RESERVA", "patrimonio", "reservas"),
    ("REVALUACION", "patrimonio", "ori"),
    ("ADOPCION NIIF", "patrimonio", "resAcum"),
    ("RESULTADOS ACUMULADOS", "patrimonio", "resAcum"),
    ("RESULTADO DEL EJERCICIO", "patrimonio", "utilEjercicio"),
    ("INGRESOS ORDINARIOS", "resultado", "ventas"),
    ("COSTO", "resultado", "costo"),
    ("ADMINISTRACION", "resultado", "gAdmin"),
    ("FINANCIER", "resultado", "gFin"),
    ("NO ORDINARIAS", "resultado", "otrosIng"),
    ("PARTICIPACION TRABAJADORES", "resultado", "partTrab"),
    ("IMPUESTO A LA RENTA", "resultado", "irCausado"),
]

def mapear_concepto(nombre: str):
    n = _norm(nombre)
    # 'IMPUESTOS CORRIENTES' aparece en activo y pasivo: se desambigua por
    # 'ACTIVOS'/'PASIVOS' si el nombre lo trae; si no, cae en activo.
    for token, sec, key in _REGLAS:
        if token in n:
            if key == "impRec" and "PASIV" in n:
                return ("pasivo", "impPagar")
            return (sec, key)
    return (None, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eeff_mapeo.py -v`
Expected: PASS (5 passed). Si `TOTAL ACTIVOS` fallara por chocar con otra regla, mover la regla `("TOTAL", ...)` al inicio (ya está).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tax/planificacion_utilidades/parsers/mapeo_nombres.py backend/tests/test_eeff_mapeo.py
git commit -m "feat(fin): mapeo por nombre a rubros NIIF sin fusionar grupos"
```

---

### Task 5: Extractor resumido por nombre

**Files:**
- Create: `backend/app/tax/planificacion_utilidades/parsers/balance_resumido_nombre.py`
- Test: `backend/tests/test_eeff_resumido_nombre.py`

- [ ] **Step 1: Write the failing test** (usa el fixture sintético, valores conocidos)

```python
from backend.app.tax.planificacion_utilidades.parsers.balance_resumido_nombre import (
    extract_balance_resumido_nombre,
)
from backend.tests.fixtures.eeff_sintetico import libro_resumido_nombre

def test_periodos_esf_y_eri():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    assert [p["label"] for p in r["periodos_esf"]] == ["may-26", "2025", "2024", "2023"]
    assert [p["tipo"] for p in r["periodos_esf"]] == ["parcial", "anual", "anual", "anual"]
    assert [p["label"] for p in r["periodos_eri"]] == ["may-26", "may-25", "2025", "2024", "2023"]

def test_rubros_no_se_fusionan():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    d = r["data"]
    assert d["efectivo"][0] == 100 and d["inventario"][0] == 300 and d["ppe"][0] == 400
    assert d["cxc"][0] == 200  # CxC separada de efectivo/inventario

def test_ingresos_por_periodo_eri():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    # ventas: may-26=500, may-25=450, 2025=1200, 2024=1500, 2023=1400
    assert r["data"]["ventas"] == [500, 450, 1200, 1500, 1400]

def test_descuadre_emite_warning():
    r = extract_balance_resumido_nombre(libro_resumido_nombre())
    assert any("descuadre" in w.lower() or "cuadr" in w.lower() for w in r["warnings"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eeff_resumido_nombre.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write minimal implementation**

```python
"""Extrae un EEFF resumido por NOMBRE de concepto (ESF + ERI), con N períodos
variables y mixtos. Contrato compatible con extract_balance_interno más
`periodos_esf`, `periodos_eri`."""
from __future__ import annotations
import io
import pandas as pd
from ..schema import INPUT_KEYS
from .periodos import clasificar_periodo
from .mapeo_nombres import mapear_concepto

_TITULO_ESF = ("SITUACION FINANCIERA", "SITUACIÓN FINANCIERA", "BALANCE")
_TITULO_ERI = ("RESULTADO", "RESULTADOS", "PERDIDAS Y GANANCIAS", "P Y G")

def _read(data: bytes) -> pd.DataFrame:
    engine = "xlrd" if data[:4] == b"\xd0\xcf\x11\xe0" else "openpyxl"
    xls = pd.ExcelFile(io.BytesIO(data), engine=engine)
    return xls.parse(xls.sheet_names[0], header=None)

def _fila_periodos(row):
    out = []
    for i, v in enumerate(row.tolist()):
        p = clasificar_periodo(v)
        if p:
            out.append((i, p))
    return out

def extract_balance_resumido_nombre(data: bytes) -> dict:
    df = _read(data)
    n = len(df)
    # localizar cabeceras de cada bloque (col A texto no-período + >=2 periodos)
    bloques = []  # (tipo, fila_cab, [(col,period)])
    for i in range(n):
        row = df.iloc[i]
        pers = _fila_periodos(row)
        a0 = row.iloc[0]
        if len(pers) >= 2 and isinstance(a0, str) and clasificar_periodo(a0) is None:
            bloques.append([i, pers])
    # asignar tipo por el título más cercano hacia arriba
    def _tipo(fila_cab):
        for j in range(fila_cab, max(-1, fila_cab - 4), -1):
            t = str(df.iloc[j, 0]).upper()
            if any(k in t for k in _TITULO_ERI):
                return "eri"
            if any(k in t for k in _TITULO_ESF):
                return "esf"
        return "esf"
    esf = next((b for b in bloques if _tipo(b[0]) == "esf"), None)
    eri = next((b for b in bloques if _tipo(b[0]) == "eri"), None)

    per_esf = [p for _c, p in (esf[1] if esf else [])]
    per_eri = [p for _c, p in (eri[1] if eri else [])]
    ncols = max(len(per_esf), len(per_eri), 1)
    data_out = {k: [0.0] * ncols for k in INPUT_KEYS}
    warnings: list[str] = []

    def _fin_bloque(fila_cab):
        for b in bloques:
            if b[0] > fila_cab:
                return b[0]
        return n

    def _cargar(bloque, periodos):
        if not bloque:
            return {}
        cab, cols = bloque
        totales = {}  # (seccion) -> [vals]
        for i in range(cab + 1, _fin_bloque(cab)):
            nombre = df.iloc[i, 0]
            if not isinstance(nombre, str) or not nombre.strip():
                continue
            sec, key = mapear_concepto(nombre)
            if sec is None:
                warnings.append(f"Concepto no mapeado: '{nombre.strip()}'")
                continue
            vals = [float(df.iloc[i, c]) if pd.notna(df.iloc[i, c]) and isinstance(df.iloc[i, c], (int, float)) else 0.0
                    for c, _p in cols]
            if sec == "total":
                totales[nombre.strip().upper()] = vals
                continue
            for yi, v in enumerate(vals):
                if yi < ncols and key in data_out:
                    data_out[key][yi] += v
        return totales

    tot_esf = _cargar(esf, per_esf)
    _cargar(eri, per_eri)

    # cuadre ESF: TOTAL ACTIVOS vs TOTAL PASIVO + PATRIMONIO por período
    ta = next((v for k, v in tot_esf.items() if "ACTIVO" in k), None)
    tpp = next((v for k, v in tot_esf.items() if "PATRIMONIO" in k), None)
    if ta and tpp:
        for yi in range(min(len(ta), len(tpp))):
            dif = round(ta[yi] - tpp[yi], 2)
            if abs(dif) > 0.01:
                lab = per_esf[yi]["label"] if yi < len(per_esf) else str(yi)
                warnings.append(f"Descuadre en {lab}: Activo − (Pasivo+Patrimonio) = {dif:,.2f}")

    return {
        "data": data_out,
        "detalle": [],
        "params": {},
        "warnings": warnings,
        "source": "resumido_nombre",
        "periodos_esf": per_esf,
        "periodos_eri": per_eri,
        "labels_esf": [p["label"] for p in per_esf],
        "labels_er": [p["label"] for p in per_eri],
        "anios_detectados": [p["anio"] for p in (per_esf or per_eri)],
        "anio_detectado": (per_esf or per_eri)[-1]["anio"] if (per_esf or per_eri) else None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eeff_resumido_nombre.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tax/planificacion_utilidades/parsers/balance_resumido_nombre.py backend/tests/test_eeff_resumido_nombre.py
git commit -m "feat(fin): extractor de EEFF resumido por nombre con cuadre"
```

---

### Task 6: Comparaciones encadenadas

**Files:**
- Create: `backend/app/tax/planificacion_utilidades/comparaciones.py`
- Test: `backend/tests/test_eeff_comparaciones.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.app.tax.planificacion_utilidades.comparaciones import build_comparaciones

def test_esf_encadenado():
    labels = ["may-26", "2025", "2024", "2023"]
    tipos = ["parcial", "anual", "anual", "anual"]
    pares = build_comparaciones(labels, tipos, "esf")
    assert pares == [("may-26", "2025"), ("2025", "2024"), ("2024", "2023")]

def test_eri_parcial_y_anual():
    labels = ["may-26", "may-25", "2025", "2024", "2023"]
    tipos = ["parcial", "parcial", "anual", "anual", "anual"]
    pares = build_comparaciones(labels, tipos, "eri")
    # parcial vs parcial, y anuales encadenados; nunca 5m vs 12m
    assert ("may-26", "may-25") in pares
    assert ("2025", "2024") in pares and ("2024", "2023") in pares
    assert ("may-26", "2025") not in pares  # jamás cruza parcial/anual
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eeff_comparaciones.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write minimal implementation**

```python
"""Arma los pares de comparación período-a-período según el tipo de estado."""
from __future__ import annotations

def build_comparaciones(labels: list[str], tipos: list[str], estado: str) -> list[tuple[str, str]]:
    """estado='esf' → actual vs inmediatamente anterior (cadena completa).
    estado='eri' → parciales entre sí (like-for-like) + anuales encadenados."""
    pares: list[tuple[str, str]] = []
    if estado == "esf":
        for i in range(len(labels) - 1):
            pares.append((labels[i], labels[i + 1]))
        return pares
    # eri: separar por tipo, encadenar dentro de cada grupo
    parc = [labels[i] for i, t in enumerate(tipos) if t == "parcial"]
    anu = [labels[i] for i, t in enumerate(tipos) if t == "anual"]
    for i in range(len(parc) - 1):
        pares.append((parc[i], parc[i + 1]))
    for i in range(len(anu) - 1):
        pares.append((anu[i], anu[i + 1]))
    return pares
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eeff_comparaciones.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tax/planificacion_utilidades/comparaciones.py backend/tests/test_eeff_comparaciones.py
git commit -m "feat(fin): pares de comparacion encadenados ESF/ERI"
```

---

### Task 7: Fachada en `extract_balance_interno` (detect + delega, sin regresión)

**Files:**
- Modify: `backend/app/tax/planificacion_utilidades/parsers/balance_interno.py` (envolver `extract_balance_interno`)
- Test: `backend/tests/test_eeff_fachada_sin_regresion.py`

- [ ] **Step 1: Write the failing test**

```python
import io, openpyxl
from backend.app.tax.planificacion_utilidades.parsers.balance_interno import extract_balance_interno
from backend.tests.fixtures.eeff_sintetico import libro_resumido_nombre

def _codificado_bytes():
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Cuenta", "Nombre", 2024, 2025])
    ws.append(["1", "ACTIVO", 100, 110])
    ws.append(["1.1.01", "Caja", 100, 110])
    ws.append(["2", "PASIVO", 40, 50])
    ws.append(["2.1.01", "Proveedores", 40, 50])
    ws.append(["3", "PATRIMONIO", 60, 60])
    ws.append(["3.1.01", "Capital", 60, 60])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()

def test_resumido_nombre_entra_por_fachada():
    r = extract_balance_interno(libro_resumido_nombre())
    assert r["source"] == "resumido_nombre"
    assert r["data"]["efectivo"][0] == 100

def test_codificado_sigue_funcionando():
    r = extract_balance_interno(_codificado_bytes())
    # el camino codificado NO cambia: efectivo (Caja) sale poblado
    assert r["data"]["efectivo"][-1] == 110
    assert r["source"] == "interno"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_eeff_fachada_sin_regresion.py -v`
Expected: FAIL (`test_resumido_nombre_entra_por_fachada` falla: hoy lanza ValueError).

- [ ] **Step 3: Modify `balance_interno.py`** — renombrar la función actual a `_extract_codificado` y crear la fachada:

En `balance_interno.py`, cambiar la firma `def extract_balance_interno(data_bytes: bytes) -> dict:` (línea ~522) por `def _extract_codificado(data_bytes: bytes) -> dict:` y añadir al final del archivo:

```python
def extract_balance_interno(data_bytes: bytes) -> dict:
    """Fachada: detecta el formato del libro y delega.

    - 'codificado' → lógica histórica (_extract_codificado), sin cambios.
    - 'resumido_nombre' → nuevo extractor por nombre de concepto.
    - 'plantilla' → se deja al parser resumido de plantilla existente.
    """
    from .layout import detect_layout
    from .balance_resumido_nombre import extract_balance_resumido_nombre
    try:
        xls = _read_excel(data_bytes)
        df = xls.parse(xls.sheet_names[0], header=None)
        layout = detect_layout(df)
    except Exception:
        layout = "codificado"
    if layout == "resumido_nombre":
        return extract_balance_resumido_nombre(data_bytes)
    return _extract_codificado(data_bytes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_eeff_fachada_sin_regresion.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run FULL parser suite (no regresión global)**

Run: `cd backend && python -m pytest tests/ -k "tax or balance or eeff or interno" -q`
Expected: PASS (todos verdes; ninguno del camino codificado se rompe).

- [ ] **Step 6: Commit**

```bash
git add backend/app/tax/planificacion_utilidades/parsers/balance_interno.py backend/tests/test_eeff_fachada_sin_regresion.py
git commit -m "feat(fin): fachada extract_balance_interno detecta formato y delega"
```

---

### Task 8: Verificación empírica con archivo real (LOCAL, no se commitea data)

**Files:** ninguno (script efímero).

- [ ] **Step 1: Correr el extractor sobre el archivo real y comparar contra los valores conocidos**

```bash
cd backend && python -c "
from app.tax.planificacion_utilidades.parsers.balance_interno import extract_balance_interno
r = extract_balance_interno(open(r'C:/Users/jcalu/Downloads/EEFF SIGMAN 2026.xlsx','rb').read())
d = r['data']
print('source:', r['source'])
print('labels_esf:', r['labels_esf']); print('labels_er:', r['labels_er'])
print('efectivo:', d['efectivo']); print('inventario:', d['inventario']); print('ppe:', d['ppe'])
print('ventas:', d['ventas']); print('costo:', d['costo'])
print('warnings:', r['warnings'])
"
```

Verificación esperada (cifras del archivo real):
- `source == 'resumido_nombre'`
- `labels_esf == ['may-26','2025','2024','2023']`, `labels_er == ['may-26','may-25','2025','2024','2023']`
- `efectivo[0] == 1033066.60`, `inventario[0] == 2693251.90`, `ppe[0] == 730597.13`
- `ventas == [2930004.99, 2573946.71, 7599669.59, 9788597.05, 9776561.55]`
- warnings incluye el descuadre −261.02 en 2025

- [ ] **Step 2: Si algo no cuadra** → volver a la Task del componente afectado (períodos/mapeo/extractor), agregar el caso al fixture sintético y corregir. NUNCA hardcodear la cifra del cliente.

- [ ] **Step 3: (sin commit de data)** — registrar el resultado en el PR como texto.

---

## Self-Review

- **Cobertura del spec:** §3.1 períodos → Task 1; §4.1 layout → Task 3; §3.3 mapeo → Task 4; §4.2 extractor → Task 5; §3.2 comparaciones → Task 6; §4.3 fachada+alineación (labels separados) → Task 5/7; §6 warnings descuadre → Task 5; §7 tests → Tasks 1-8; verificación real → Task 8. ✔
- **Placeholders:** ninguno; todo el código está escrito. ✔
- **Consistencia de tipos:** `clasificar_periodo` devuelve dict con `label/tipo/meses/anio` usado consistente en layout/extractor/comparaciones; `mapear_concepto` → `(seccion, clave)`; `extract_balance_resumido_nombre` devuelve el contrato + `periodos_esf/eri`. ✔
