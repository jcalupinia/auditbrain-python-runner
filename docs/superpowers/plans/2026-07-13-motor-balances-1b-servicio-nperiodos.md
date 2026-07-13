# Motor de Balances · Fase 1b — Servicio de homologación N-períodos (backend) · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el **núcleo backend** del Motor de balances: mapa de homologación Super↔SRI, parser de balances crudos multi-período, consolidación multiarchivo (ESF/ERI + años), y el motor que unifica, propaga la homologación y calcula el cuadre por período — todo como funciones puras testeables con pytest.

**Architecture:** Funciones puras nuevas en `client_portal/flujo/` (extendiendo `catalogos.py`/`parser.py` y un módulo nuevo `motor_balances.py`). Reutiliza `_parse_saldo` (parser) y `homologar_balanza`/`totales_por_codigo` (motor). Sin endpoint ni frontend (eso es 1c). No altera el flujo 2-períodos existente.

**Tech Stack:** Python 3.13, openpyxl, csv, pytest.

**Fuente de diseño:** `docs/superpowers/specs/2026-07-12-motor-balances-homologacion-design.md` (§4.1 multiarchivo, §5.0, §6). Depende de Fase 1a (ficha con `nombre`), ya en `main`/PR #95.

---

## Modelos de datos (contrato entre tareas)

**Fila cruda multi-período** (salida de `parse_balanza_multiperiodo`):
```python
{"periodos": ["2023", "2024", "2025", "may-2026"],   # etiquetas ordenadas
 "estado": "esf" | "eri",                              # clasificado por código dominante
 "filas": [{"cuenta": "1.01.01.02.001", "nombre": "Produbanco Quito",
            "saldos": [341440.43, 144362.32, 351257.23, 89723.89]}]}  # lista alineada a periodos
```

**Ficha unificada** (salida de consolidación/homologación):
```python
{"cuenta": "1.01.01.02.001", "nombre": "Produbanco Quito",
 "super_cias": "1010103", "sri": "311",         # "" si huérfana
 "saldos": {"2023": 341440.43, "2024": 144362.32, ...}}  # dict por etiqueta de período
```

---

## File Structure

- `backend/app/client_portal/flujo/catalogos.py` — MODIFICAR: agregar `cargar_mapa_super_sri()`.
- `backend/app/client_portal/flujo/parser.py` — MODIFICAR: agregar `parse_balanza_multiperiodo()` + helper `_etiqueta_periodo`.
- `backend/app/client_portal/flujo/motor_balances.py` — CREAR: `clasificar_estado`, `consolidar_multiarchivo`, `homologar_multiperiodo`, `cuadre_por_periodo`.
- `tests/test_flujo_catalogos_mapa.py`, `tests/test_flujo_parser_multiperiodo.py`, `tests/test_flujo_motor_balances.py` — CREAR.

---

### Task 1: Mapa de homologación Super↔SRI (para desplegables enlazados y homologación)

**Files:**
- Modify: `backend/app/client_portal/flujo/catalogos.py` (agregar función al final)
- Test: `tests/test_flujo_catalogos_mapa.py` (crear)

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_flujo_catalogos_mapa.py`:

```python
import os
import textwrap

from backend.app.client_portal.flujo import catalogos


def _csv(tmp_path):
    p = tmp_path / "plan.csv"
    p.write_text(textwrap.dedent("""\
        codigo_super_cias,nombre_cuenta,codigo_sri,nombre_sri
        1010101,CAJA,311,Efectivo y equivalentes
        1010103,INSTITUCIONES FINANCIERAS PRIVADAS,311,Efectivo y equivalentes
        40101,VENTA DE BIENES,6001,Gravadas tarifa distinta 0%
        40101,VENTA DE BIENES,6003,Gravadas tarifa 0%
        """), encoding="utf-8")
    return str(p)


def test_mapa_super_a_sri_soporta_1_a_n(tmp_path):
    m = catalogos.cargar_mapa_super_sri(_csv(tmp_path))
    assert m["super_a_sri"]["1010101"] == ["311"]
    assert m["super_a_sri"]["40101"] == ["6001", "6003"]        # 1:N


def test_mapa_sri_a_super_y_nombres(tmp_path):
    m = catalogos.cargar_mapa_super_sri(_csv(tmp_path))
    assert set(m["sri_a_super"]["311"]) == {"1010101", "1010103"}
    assert m["nombre_super"]["1010101"] == "CAJA"
    assert m["nombre_sri"]["6001"] == "Gravadas tarifa distinta 0%"


def test_mapa_usa_csv_real_por_defecto():
    m = catalogos.cargar_mapa_super_sri()
    assert m["super_a_sri"] and m["nombre_super"]   # el CSV real no está vacío
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_flujo_catalogos_mapa.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'cargar_mapa_super_sri'`.

- [ ] **Step 3: Implementar `cargar_mapa_super_sri`**

Agregar al final de `catalogos.py`:

```python
def cargar_mapa_super_sri(ruta: str | None = None) -> dict:
    """Mapa de homologación derivado de ``plan_cuentas_super_sri.csv`` para los
    desplegables enlazados Super↔SRI y la homologación contra el plan.

    Devuelve ``{"super_a_sri": {sc: [sri...]}, "sri_a_super": {sri: [sc...]},
    "nombre_super": {sc: nombre}, "nombre_sri": {sri: nombre}}``. Soporta 1:N
    (un código Super puede mapear a varios SRI; ej. ventas por tarifa IVA).
    """
    if ruta is None:
        ruta = os.path.join(_DATA, "plan_cuentas_super_sri.csv")
    super_a_sri: dict[str, list[str]] = {}
    sri_a_super: dict[str, list[str]] = {}
    nombre_super: dict[str, str] = {}
    nombre_sri: dict[str, str] = {}
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sc = (row.get("codigo_super_cias") or "").strip()
            sri = (row.get("codigo_sri") or "").strip()
            if sc and sc not in nombre_super:
                nombre_super[sc] = (row.get("nombre_cuenta") or "").strip()
            if sri and sri not in nombre_sri:
                nombre_sri[sri] = (row.get("nombre_sri") or "").strip()
            if sc and sri:
                super_a_sri.setdefault(sc, [])
                if sri not in super_a_sri[sc]:
                    super_a_sri[sc].append(sri)
                sri_a_super.setdefault(sri, [])
                if sc not in sri_a_super[sri]:
                    sri_a_super[sri].append(sc)
    return {"super_a_sri": super_a_sri, "sri_a_super": sri_a_super,
            "nombre_super": nombre_super, "nombre_sri": nombre_sri}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_flujo_catalogos_mapa.py -q`
Expected: PASS (3 tests). Si `test_mapa_usa_csv_real_por_defecto` falla porque el CSV real no trae columnas `codigo_sri`/`nombre_sri`, revisar el CSV real e informar; el resto debe pasar.

- [ ] **Step 5: Commit**

```bash
git add backend/app/client_portal/flujo/catalogos.py tests/test_flujo_catalogos_mapa.py
git commit -m "feat(flujo): cargar_mapa_super_sri para homologacion y desplegables enlazados

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Parser de balance crudo multi-período

**Files:**
- Modify: `backend/app/client_portal/flujo/parser.py` (agregar helper + función)
- Test: `tests/test_flujo_parser_multiperiodo.py` (crear)

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_flujo_parser_multiperiodo.py`:

```python
import io
from datetime import datetime

from openpyxl import Workbook

from backend.app.client_portal.flujo import parser


def _wb(headers, rows):
    wb = Workbook(); ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()


def test_multiperiodo_detecta_periodos_fecha_y_anio():
    data = _wb(
        ["Código", "Cuenta", datetime(2023, 12, 31), datetime(2024, 12, 31), datetime(2026, 5, 31)],
        [("1.01.01.02.001", "Produbanco Quito", 341440.43, 144362.32, 89723.89)],
    )
    res = parser.parse_balanza_multiperiodo(data)
    assert res["periodos"] == ["31-dic-2023", "31-dic-2024", "31-may-2026"]
    assert res["estado"] == "esf"
    fila = res["filas"][0]
    assert fila["cuenta"] == "1.01.01.02.001"
    assert fila["nombre"] == "Produbanco Quito"
    assert fila["saldos"] == [341440.43, 144362.32, 89723.89]


def test_multiperiodo_clasifica_eri_por_codigo_dominante():
    data = _wb(
        ["Código", "Cuenta", 2024, 2025],
        [("4.01.01", "Ventas", -100.0, -120.0),
         ("5.1.01", "Costo de ventas", 60.0, 70.0)],
    )
    res = parser.parse_balanza_multiperiodo(data)
    assert res["estado"] == "eri"
    assert res["periodos"] == ["2024", "2025"]


def test_multiperiodo_ignora_filas_de_grupo_y_saldo_texto_regional():
    data = _wb(
        ["Código", "Cuenta", 2024],
        [("1.01.01.02.", "BANCOS", ""),               # fila de grupo (termina en punto) -> se conserva pero sin saldo
         ("1.01.01.02.001", "Produbanco", "1.234,56")],  # saldo europeo
    )
    res = parser.parse_balanza_multiperiodo(data)
    fila_leaf = [f for f in res["filas"] if f["cuenta"] == "1.01.01.02.001"][0]
    assert fila_leaf["saldos"] == [1234.56]
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_flujo_parser_multiperiodo.py -q`
Expected: FAIL — `AttributeError: ... 'parse_balanza_multiperiodo'`.

- [ ] **Step 3: Implementar el helper de etiqueta de período y el parser**

Agregar a `parser.py` (después de `_parse_saldo`):

```python
from datetime import datetime, date  # (agregar al bloque de imports superior)

_MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _etiqueta_periodo(cell) -> str | None:
    """Devuelve una etiqueta de período si la celda es una fecha o un año.
    Fecha -> '31-may-2026'; año (int o texto 4 dígitos) -> '2025'. Si no, None."""
    if isinstance(cell, (datetime, date)):
        return f"{cell.day:02d}-{_MESES[cell.month]}-{cell.year}"
    s = str(cell or "").strip()
    if s[:4].isdigit() and len(s) >= 4 and s[:2] in ("19", "20"):
        return s[:4]
    return None
```

Y agregar la función principal:

```python
def parse_balanza_multiperiodo(contenido: bytes) -> dict:
    """Lee un balance CRUDO ``Código | Cuenta | período1..N`` (sin columnas de
    homologación) y devuelve ``{"periodos": [labels], "estado": "esf"|"eri",
    "filas": [{cuenta, nombre, saldos:[...]}]}``. `saldos` va alineado a `periodos`.
    Clasifica el estado por el dígito dominante del código (1/2/3 = esf, 4/5/6 = eri).
    """
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    ws = wb.worksheets[0]
    filas_raw = list(ws.iter_rows(values_only=True))
    if not filas_raw:
        return {"periodos": [], "estado": "esf", "filas": []}
    # localizar la fila de encabezado: la primera con >=1 columna de período
    hr = None
    per_cols: list[int] = []
    labels: list[str] = []
    for i, fila in enumerate(filas_raw[:15]):
        cols, labs = [], []
        for j, v in enumerate(fila):
            lab = _etiqueta_periodo(v)
            if lab:
                cols.append(j); labs.append(lab)
        if cols:
            hr, per_cols, labels = i, cols, labs
            break
    if hr is None:
        return {"periodos": [], "estado": "esf", "filas": []}

    filas: list[dict] = []
    digitos: dict[str, int] = {}
    for fila in filas_raw[hr + 1:]:
        cuenta = str(fila[0]).strip() if fila and fila[0] is not None else ""
        if not cuenta:
            continue
        nombre = str(fila[1]).strip() if len(fila) > 1 and fila[1] is not None else ""
        saldos = [_parse_saldo(fila[c]) if c < len(fila) else None for c in per_cols]
        saldos = [s if s is not None else 0.0 for s in saldos]
        filas.append({"cuenta": cuenta, "nombre": nombre, "saldos": saldos})
        d = cuenta[:1]
        if d.isdigit():
            digitos[d] = digitos.get(d, 0) + 1
    estado = "eri" if sum(digitos.get(d, 0) for d in "456") > sum(digitos.get(d, 0) for d in "123") else "esf"
    return {"periodos": labels, "estado": estado, "filas": filas}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_flujo_parser_multiperiodo.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: No-regresión del parser 2-períodos**

Run: `python -m pytest tests/test_flujo_parser.py -q`
Expected: PASS (los 5 de Fase 1a intactos — no se tocó `parse_balanza`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/client_portal/flujo/parser.py tests/test_flujo_parser_multiperiodo.py
git commit -m "feat(flujo): parse_balanza_multiperiodo (balance crudo N-periodos, clasifica ESF/ERI)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Consolidación multiarchivo (unión por cuenta, aviso de año duplicado)

**Files:**
- Create: `backend/app/client_portal/flujo/motor_balances.py`
- Test: `tests/test_flujo_motor_balances.py` (crear — parte 1)

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_flujo_motor_balances.py`:

```python
from backend.app.client_portal.flujo import motor_balances as mb


def _archivo(estado, periodos, filas):
    return {"estado": estado, "periodos": periodos, "filas": filas}


def test_consolidar_une_por_cuenta_una_columna_por_periodo():
    a2023 = _archivo("esf", ["2023"], [
        {"cuenta": "1.01", "nombre": "Caja", "saldos": [100.0]},
        {"cuenta": "1.02", "nombre": "Bancos", "saldos": [50.0]},
    ])
    a2024 = _archivo("esf", ["2024"], [
        {"cuenta": "1.01", "nombre": "Caja", "saldos": [110.0]},   # existe en ambos
        {"cuenta": "1.03", "nombre": "Inversiones", "saldos": [70.0]},  # solo 2024
    ])
    cons = mb.consolidar_multiarchivo([a2023, a2024])
    assert cons["periodos"] == ["2023", "2024"]
    fichas = {f["cuenta"]: f for f in cons["filas"]}
    assert fichas["1.01"]["saldos"] == {"2023": 100.0, "2024": 110.0}
    assert fichas["1.02"]["saldos"] == {"2023": 50.0, "2024": 0.0}    # faltante -> 0
    assert fichas["1.03"]["saldos"] == {"2023": 0.0, "2024": 70.0}
    assert cons["avisos"] == []


def test_consolidar_avisa_anio_duplicado_no_suma():
    a = _archivo("esf", ["2024"], [{"cuenta": "1.01", "nombre": "Caja", "saldos": [100.0]}])
    b = _archivo("esf", ["2024"], [{"cuenta": "1.01", "nombre": "Caja", "saldos": [999.0]}])
    cons = mb.consolidar_multiarchivo([a, b])
    assert any("2024" in av and "duplicad" in av.lower() for av in cons["avisos"])
    # no suma ni reemplaza en silencio: conserva el PRIMERO y avisa
    assert cons["filas"][0]["saldos"]["2024"] == 100.0


def test_consolidar_ordena_periodos_cronologicamente():
    a = _archivo("esf", ["2025"], [{"cuenta": "1.01", "nombre": "Caja", "saldos": [3.0]}])
    b = _archivo("esf", ["2023"], [{"cuenta": "1.01", "nombre": "Caja", "saldos": [1.0]}])
    cons = mb.consolidar_multiarchivo([a, b])
    assert cons["periodos"] == ["2023", "2025"]
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_flujo_motor_balances.py -q`
Expected: FAIL — módulo `motor_balances` no existe.

- [ ] **Step 3: Implementar `consolidar_multiarchivo` en el módulo nuevo**

Crear `backend/app/client_portal/flujo/motor_balances.py`:

```python
# backend/app/client_portal/flujo/motor_balances.py
"""Motor de balances multi-período: consolida balances crudos de varios
archivos/años, propaga la homologación por cuenta y calcula el cuadre por
período. Reutiliza ``motor.homologar_balanza`` para la agrupación por Super Cías.
"""
from __future__ import annotations

import re


def _orden_periodo(label: str) -> tuple[int, int]:
    """Clave de orden cronológico: (año, mes). 'may-2026' -> (2026,5); '2025' -> (2025,12)."""
    meses = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
             "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}
    m = re.match(r"(\d{2})-([a-z]{3})-(\d{4})", label)
    if m:
        return (int(m.group(3)), meses.get(m.group(2), 12))
    m = re.search(r"(\d{4})", label)
    return (int(m.group(1)), 12) if m else (0, 0)


def consolidar_multiarchivo(archivos: list[dict]) -> dict:
    """Une varios archivos (cada uno ``{estado, periodos, filas}``) de un MISMO
    estado en una tabla multi-período. Devuelve ``{"periodos": [...ordenados...],
    "filas": [{cuenta, nombre, saldos:{periodo:val}}], "avisos": [...]}``.

    - Unión por ``cuenta``; período faltante -> 0.
    - Año duplicado (mismo período en dos archivos): conserva el PRIMERO y avisa,
      nunca suma ni reemplaza en silencio.
    """
    periodos: list[str] = []
    avisos: list[str] = []
    fichas: dict[str, dict] = {}
    vistos: set[str] = set()
    for arch in archivos:
        for p in arch.get("periodos", []):
            if p in vistos:
                avisos.append(f"Período '{p}' duplicado en más de un archivo; se conserva el primero.")
                continue
            vistos.add(p)
            periodos.append(p)
            idx = arch["periodos"].index(p)
            for fila in arch.get("filas", []):
                cta = fila["cuenta"]
                f = fichas.setdefault(cta, {"cuenta": cta, "nombre": fila.get("nombre", ""), "saldos": {}})
                if not f["nombre"]:
                    f["nombre"] = fila.get("nombre", "")
                saldos = fila.get("saldos", [])
                f["saldos"][p] = float(saldos[idx]) if idx < len(saldos) else 0.0
    periodos.sort(key=_orden_periodo)
    # rellenar faltantes con 0 en cada ficha
    for f in fichas.values():
        for p in periodos:
            f["saldos"].setdefault(p, 0.0)
    return {"periodos": periodos, "filas": list(fichas.values()), "avisos": avisos}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_flujo_motor_balances.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/client_portal/flujo/motor_balances.py tests/test_flujo_motor_balances.py
git commit -m "feat(flujo): consolidar_multiarchivo (union por cuenta, aviso de anio duplicado)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Homologación N-períodos (propagar mapeo, huérfanas, cuadre por período)

**Files:**
- Modify: `backend/app/client_portal/flujo/motor_balances.py` (agregar funciones)
- Test: `tests/test_flujo_motor_balances.py` (agregar tests)

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_flujo_motor_balances.py`:

```python
def test_propagar_homologacion_marca_huerfanas():
    cons = {"periodos": ["2024"], "filas": [
        {"cuenta": "1.01.01.02.001", "nombre": "Produbanco", "saldos": {"2024": 100.0}},
        {"cuenta": "1.01.01.01.002", "nombre": "Caja Chica", "saldos": {"2024": 5.0}},
    ]}
    mapeo = {"1.01.01.02.001": ("1010103", "311")}   # cuenta cliente -> (super, sri)
    out = mb.propagar_homologacion(cons["filas"], mapeo)
    homolog = {f["cuenta"]: f for f in out}
    assert homolog["1.01.01.02.001"]["super_cias"] == "1010103"
    assert homolog["1.01.01.02.001"]["sri"] == "311"
    assert homolog["1.01.01.01.002"]["super_cias"] == ""       # huérfana
    assert mb.huerfanas(out) == ["1.01.01.01.002"]


def test_cuadre_por_periodo_esf_no_fuerza():
    # Activo (1) 100 ; Pasivo (2) -60 ; Patrimonio (3) -40  -> cuadra
    fichas = [
        {"cuenta": "a", "super_cias": "1010101", "sri": "311", "saldos": {"2024": 100.0}},
        {"cuenta": "b", "super_cias": "2010301", "sri": "413", "saldos": {"2024": -60.0}},
        {"cuenta": "c", "super_cias": "3010101", "sri": "601", "saldos": {"2024": -40.0}},
    ]
    cua = mb.cuadre_por_periodo(fichas, ["2024"])
    assert cua["2024"]["cuadra"] is True
    assert abs(cua["2024"]["diferencia"]) < 0.01


def test_cuadre_por_periodo_reporta_descuadre():
    fichas = [
        {"cuenta": "a", "super_cias": "1010101", "sri": "311", "saldos": {"2024": 100.0}},
        {"cuenta": "b", "super_cias": "2010301", "sri": "413", "saldos": {"2024": -60.0}},
    ]
    cua = mb.cuadre_por_periodo(fichas, ["2024"])
    assert cua["2024"]["cuadra"] is False
    assert abs(cua["2024"]["diferencia"] - 40.0) < 0.01     # 100 - 60 = 40 sin patrimonio
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_flujo_motor_balances.py -q`
Expected: FAIL — `propagar_homologacion`/`huerfanas`/`cuadre_por_periodo` no existen.

- [ ] **Step 3: Implementar las funciones**

Agregar a `motor_balances.py`:

```python
def propagar_homologacion(filas: list[dict], mapeo: dict[str, tuple[str, str]]) -> list[dict]:
    """Asigna ``super_cias``/``sri`` a cada ficha según ``mapeo`` (cuenta cliente ->
    (super, sri)). Las que no están en el mapeo quedan con "" (huérfanas). No pierde
    ninguna cuenta. Devuelve nuevas fichas (no muta las de entrada)."""
    out = []
    for f in filas:
        sc, sri = mapeo.get(f["cuenta"], ("", ""))
        out.append({**f, "super_cias": sc, "sri": sri})
    return out


def huerfanas(filas: list[dict]) -> list[str]:
    """Códigos de cuenta cliente sin Super Cías asignado, en orden de aparición."""
    return [f["cuenta"] for f in filas if not f.get("super_cias")]


def cuadre_por_periodo(filas: list[dict], periodos: list[str], tolerancia: float = 1.0) -> dict:
    """Cuadre A = P + Patrimonio por período, agrupando por sección del Código Super
    Cías (1=activo, 2=pasivo, 3=patrimonio; 2 y 3 son crédito/negativo). **Reporta,
    nunca fuerza.** Devuelve ``{periodo: {"activo","pas_pat","diferencia","cuadra"}}``.
    Las cuentas huérfanas (sin super_cias) NO entran al cuadre (se avisan aparte)."""
    out: dict[str, dict] = {}
    for p in periodos:
        sec = {"1": 0.0, "2": 0.0, "3": 0.0}
        for f in filas:
            sc = str(f.get("super_cias") or "")
            if sc[:1] in sec:
                sec[sc[:1]] += float(f["saldos"].get(p, 0.0))
        activo = round(sec["1"], 2)
        pas_pat = round(-(sec["2"] + sec["3"]), 2)
        dif = round(activo - pas_pat, 2)
        out[p] = {"activo": activo, "pas_pat": pas_pat, "diferencia": dif,
                  "cuadra": abs(dif) <= tolerancia}
    return out
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_flujo_motor_balances.py -q`
Expected: PASS (6 tests: 3 de Task 3 + 3 nuevos).

- [ ] **Step 5: No-regresión del módulo flujo completo**

Run: `python -m pytest tests/ -k flujo -q`
Expected: PASS (todo verde, incluidos los tests de Fase 1a y los nuevos de 1b).

- [ ] **Step 6: Commit**

```bash
git add backend/app/client_portal/flujo/motor_balances.py tests/test_flujo_motor_balances.py
git commit -m "feat(flujo): homologacion N-periodos (propagar mapeo, huerfanas, cuadre por periodo sin forzar)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Verificación final (REGLA SUPREMA)

- [ ] `python -m pytest tests/ -k flujo -q` en **verde** (Fase 1a + 1b, sin regresión del flujo 2-períodos).
- [ ] **Verificación con datos reales SIGMAN** (empírica, no solo fixtures): correr un script ad-hoc que:
  1. `parse_balanza_multiperiodo` sobre `BALANCE SIGMAN.xlsx` → confirmar `estado == "esf"`, 4 períodos, 226 cuentas hoja.
  2. `parse_balanza_multiperiodo` sobre `RESULTADOS SIGMAN.xlsx` → `estado == "eri"`, 5 períodos.
  3. `propagar_homologacion` con el mapeo del `Mapeo Año Actual` → confirmar **114 homologadas / 112 huérfanas** en ESF (los números medidos en el spec).
  4. `cuadre_por_periodo` sobre el ESF homologado → confirmar que refleja el cuadre real por período (no forzado).
  Pegar los conteos reales; deben coincidir con el spec §8.

## Fuera de alcance de este plan (va en 1c)

- Endpoint AUD (`POST …/motor-balances/homologar` y `…/recalcular`) + `require_staff`.
- Frontend: nueva herramienta AUD (UI multi-período, huérfanas con desplegables enlazados usando `cargar_mapa_super_sri`, secciones Superintendencia).
- Extensión de `generador._hoja_estructura` a N columnas.
