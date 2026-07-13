# Motor de Balances · Fase 1c — Endpoint AUD + herramienta frontend · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (para el BACKEND) o ejecución interactiva (para el FRONTEND). Steps con checkbox (`- [ ]`).

**Goal:** Exponer el servicio de homologación N-períodos (Fase 1b) por HTTP (endpoint AUD `require_staff`) y construir la herramienta frontend "Motor de balances" en AUD → Análisis, manteniendo la línea gráfica del portal Flujo.

**Architecture:** La orquestación (parse → detectar mapeado/crudo → consolidar → propagar → cuadre) vive en **funciones puras** en `motor_balances.py` (`homologar_archivos`, `recalcular_homologado`), testeables sin HTTP. El endpoint AUD es un envoltorio delgado (auth + IO). El frontend reutiliza el patrón/estilo de `BalanzasEditor`/`FlujoDashboard`.

**Tech Stack:** Python 3.13, FastAPI, pytest (backend); React (frontend `frontend/src/aud`).

**Fuente de diseño:** `docs/superpowers/specs/2026-07-12-motor-balances-homologacion-design.md` (§5.0, §5b, §6). Depende de Fase 1b (funciones en `motor_balances.py`), PR #96.

---

## PARTE A — BACKEND (ejecutable por subagente, TDD con pytest)

### File Structure (backend)
- `backend/app/client_portal/flujo/motor_balances.py` — MODIFICAR: `homologar_archivos`, `recalcular_homologado`.
- `backend/app/aud/motor_balances/__init__.py` + `router.py` — CREAR: endpoint AUD.
- Registro del router en la app (donde se hace `include_router` de los demás AUD).
- `tests/test_flujo_motor_balances_orquestacion.py`, `tests/test_aud_motor_balances_endpoint.py` — CREAR.

---

### Task A1: Orquestación `homologar_archivos` (detecta mapeado vs crudo, consolida, propaga, cuadra)

**Files:**
- Modify: `backend/app/client_portal/flujo/motor_balances.py` (agregar función)
- Test: `tests/test_flujo_motor_balances_orquestacion.py` (crear)

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_flujo_motor_balances_orquestacion.py`:

```python
import io
from datetime import datetime

from openpyxl import Workbook

from backend.app.client_portal.flujo import motor_balances as mb


def _xlsx(headers, rows):
    wb = Workbook(); ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()


def test_homologar_archivos_propaga_mapeo_a_crudo():
    # archivo "mapeado" (Mapeo Año Actual): tiene columnas Super Cías/SRI
    mapeado = _xlsx(
        ["Cod.Cuenta.Contable", "Descripción", "CODIFO SUPER CIAS", "Códigos SRI", "Saldos 31 DIC"],
        [("1.01.01.02.001", "Produbanco", "1010103", "311", 100.0)],
    )
    # archivo crudo ESF multi-período: sin Super Cías
    crudo = _xlsx(
        ["Código", "Cuenta", datetime(2023, 12, 31), datetime(2024, 12, 31)],
        [("1.01.01.02.001", "Produbanco", 100.0, 110.0),
         ("1.01.01.01.002", "Caja Chica", 0.0, 5.0)],
    )
    out = mb.homologar_archivos([("mapeo.xlsx", mapeado), ("balance.xlsx", crudo)])
    esf = out["esf"]
    fichas = {f["cuenta"]: f for f in esf["filas"]}
    assert esf["periodos"] == ["31-dic-2023", "31-dic-2024"]
    assert fichas["1.01.01.02.001"]["super_cias"] == "1010103"     # propagada
    assert fichas["1.01.01.01.002"]["super_cias"] == ""            # huérfana
    assert esf["huerfanas"] == ["1.01.01.01.002"]
    assert "31-dic-2024" in esf["cuadre"]


def test_homologar_archivos_clasifica_eri_aparte():
    crudo_eri = _xlsx(
        ["Código", "Cuenta", 2024],
        [("4.01.01", "Ventas", -100.0), ("5.1.01", "Costo", 60.0)],
    )
    out = mb.homologar_archivos([("resultados.xlsx", crudo_eri)])
    assert out["eri"]["periodos"] == ["2024"]
    assert out["esf"]["periodos"] == []
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_flujo_motor_balances_orquestacion.py -q`
Expected: FAIL — `homologar_archivos` no existe.

- [ ] **Step 3: Implementar `homologar_archivos`**

Agregar a `motor_balances.py` (importar `parser` de forma diferida para evitar ciclos):

```python
def _vacio() -> dict:
    return {"periodos": [], "filas": [], "avisos": []}


def homologar_archivos(archivos: list[tuple[str, bytes]]) -> dict:
    """Orquesta la ingesta: por cada archivo detecta si es un "balance mapeado"
    (trae columnas Super Cías/SRI → fuente de homologación) o un balance CRUDO
    multi-período; consolida los crudos por estado (ESF/ERI), propaga la
    homologación del mapeado, y calcula huérfanas y cuadre por período.
    ``archivos``: lista de ``(nombre, bytes)``.
    Devuelve ``{"esf": {periodos, filas, avisos, cuadre, huerfanas},
    "eri": {periodos, filas, avisos, huerfanas}}``."""
    from . import parser  # import diferido
    mapeo: dict[str, tuple[str, str]] = {}
    esf_raw: list[dict] = []
    eri_raw: list[dict] = []
    for _nombre, contenido in archivos:
        mapeados = parser.parse_balanza(contenido)   # no vacío solo si trae Super Cías + saldo
        if mapeados:
            for f in mapeados:
                if f.get("super_cias") and f["cuenta"] not in mapeo:
                    mapeo[f["cuenta"]] = (f["super_cias"], f.get("sri", ""))
            continue
        res = parser.parse_balanza_multiperiodo(contenido)
        (esf_raw if res["estado"] == "esf" else eri_raw).append(res)
    cons_esf = consolidar_multiarchivo(esf_raw) if esf_raw else _vacio()
    cons_eri = consolidar_multiarchivo(eri_raw) if eri_raw else _vacio()
    esf_h = propagar_homologacion(cons_esf["filas"], mapeo)
    eri_h = propagar_homologacion(cons_eri["filas"], mapeo)
    return {
        "esf": {"periodos": cons_esf["periodos"], "filas": esf_h,
                "avisos": cons_esf["avisos"],
                "cuadre": cuadre_por_periodo(esf_h, cons_esf["periodos"]),
                "huerfanas": huerfanas(esf_h)},
        "eri": {"periodos": cons_eri["periodos"], "filas": eri_h,
                "avisos": cons_eri["avisos"], "huerfanas": huerfanas(eri_h)},
    }
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_flujo_motor_balances_orquestacion.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/client_portal/flujo/motor_balances.py tests/test_flujo_motor_balances_orquestacion.py
git commit -m "feat(flujo): homologar_archivos (orquesta ingesta multiarchivo mapeado+crudo)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task A2: `recalcular_homologado` (recalcula cuadre + huérfanas tras editar)

**Files:**
- Modify: `backend/app/client_portal/flujo/motor_balances.py`
- Test: `tests/test_flujo_motor_balances_orquestacion.py` (agregar)

- [ ] **Step 1: Agregar el test que falla**

```python
def test_recalcular_homologado_actualiza_cuadre_y_huerfanas():
    esf = {"periodos": ["2024"], "filas": [
        {"cuenta": "a", "nombre": "Caja", "super_cias": "1010101", "sri": "311", "saldos": {"2024": 100.0}},
        {"cuenta": "b", "nombre": "X", "super_cias": "", "sri": "", "saldos": {"2024": -60.0}},
    ]}
    eri = {"periodos": [], "filas": []}
    out = mb.recalcular_homologado(esf, eri)
    assert out["esf"]["huerfanas"] == ["b"]                 # 'b' sin super_cias
    assert out["esf"]["cuadre"]["2024"]["cuadra"] is False  # falta homologar 'b'
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_flujo_motor_balances_orquestacion.py::test_recalcular_homologado_actualiza_cuadre_y_huerfanas -q`
Expected: FAIL — no existe.

- [ ] **Step 3: Implementar**

```python
def recalcular_homologado(esf: dict, eri: dict) -> dict:
    """Recalcula cuadre (ESF) y huérfanas (ESF y ERI) a partir de las tablas
    editadas por el usuario (mismos dicts que devuelve ``homologar_archivos``,
    con super_cias/sri corregidos). No re-parsea archivos."""
    return {
        "esf": {**esf,
                "cuadre": cuadre_por_periodo(esf.get("filas", []), esf.get("periodos", [])),
                "huerfanas": huerfanas(esf.get("filas", []))},
        "eri": {**eri, "huerfanas": huerfanas(eri.get("filas", []))},
    }
```

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_flujo_motor_balances_orquestacion.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/client_portal/flujo/motor_balances.py tests/test_flujo_motor_balances_orquestacion.py
git commit -m "feat(flujo): recalcular_homologado (recalcula cuadre y huerfanas tras editar)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task A3: Endpoint AUD `require_staff` (envoltorio delgado) + registro

**Files:**
- Create: `backend/app/aud/motor_balances/__init__.py` (vacío)
- Create: `backend/app/aud/motor_balances/router.py`
- Modify: el módulo donde se hace `include_router` de los routers AUD (buscar dónde se incluye `obligaciones_fiscales.router`; agregar el nuevo al lado, mismo patrón).
- Test: `tests/test_aud_motor_balances_endpoint.py` (crear)

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_aud_motor_balances_endpoint.py`. Reutilizá el patrón de TestClient y el fixture de autenticación STAFF que usan los tests de endpoints existentes (buscá en `tests/` uno que autentique como staff/admin, ej. los de `obligaciones_fiscales` o `test_context.py`; imitá su forma de obtener el cliente autenticado). El test debe:
1. Confirmar que `POST /aud/motor-balances/homologar` SIN auth devuelve 401/403 (gating `require_staff`).
2. Con auth staff, subir un xlsx crudo mínimo y recibir 200 con las claves `esf`/`eri` en el JSON.

Estructura (completá el fixture de auth según el patrón del repo):
```python
import io
from openpyxl import Workbook
# from tests... import <fixture staff/testclient del repo>


def _xlsx_crudo():
    wb = Workbook(); ws = wb.active
    ws.append(["Código", "Cuenta", 2024])
    ws.append(["1.01", "Caja", 100.0])
    bio = io.BytesIO(); wb.save(bio); return bio.getvalue()


def test_homologar_requiere_staff(client):
    r = client.post("/aud/motor-balances/homologar", files=[("archivos", ("b.xlsx", _xlsx_crudo()))])
    assert r.status_code in (401, 403)


def test_homologar_ok_con_staff(client_staff):
    r = client_staff.post("/aud/motor-balances/homologar",
                          files=[("archivos", ("b.xlsx", _xlsx_crudo()))])
    assert r.status_code == 200
    body = r.json()
    assert "esf" in body and "eri" in body
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_aud_motor_balances_endpoint.py -q`
Expected: FAIL (404: ruta no registrada).

- [ ] **Step 3: Crear el router y registrarlo**

`backend/app/aud/motor_balances/__init__.py`: archivo vacío.

`backend/app/aud/motor_balances/router.py`:
```python
"""Endpoints HTTP del Motor de balances (AUD, staff)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.client_portal.flujo import motor_balances

router = APIRouter(prefix="/aud/motor-balances", tags=["aud-motor-balances"])


@router.post("/homologar")
async def homologar(archivos: list[UploadFile] = File(...),
                    _user: User = Depends(require_staff)) -> dict:
    leidos = [(f.filename or "", await f.read()) for f in archivos]
    return motor_balances.homologar_archivos(leidos)


class RecalcularBody(BaseModel):
    esf: dict
    eri: dict


@router.post("/recalcular")
def recalcular(body: RecalcularBody, _user: User = Depends(require_staff)) -> dict:
    return motor_balances.recalcular_homologado(body.esf, body.eri)
```

Registro: buscá el módulo que hace `app.include_router(...)` para los routers AUD (grep `obligaciones_fiscales` + `include_router`). Agregá:
```python
from backend.app.aud.motor_balances.router import router as motor_balances_router
app.include_router(motor_balances_router)
```
siguiendo exactamente el patrón/orden de los demás.

- [ ] **Step 4: Correr y ver pasar**

Run: `python -m pytest tests/test_aud_motor_balances_endpoint.py -q`
Expected: PASS. Si el fixture de auth staff es difícil de montar, como MÍNIMO dejá pasando `test_homologar_requiere_staff` (401/403) y marcá el de staff con `@pytest.mark.skip("requiere fixture auth staff")` explicando por qué; repórtalo.

- [ ] **Step 5: No-regresión + commit**

Run: `python -m pytest tests/ -k "flujo or motor_balances or aud" -q` → verde.
```bash
git add backend/app/aud/motor_balances/ tests/test_aud_motor_balances_endpoint.py <archivo_registro_router>
git commit -m "feat(aud): endpoint /aud/motor-balances (homologar + recalcular, require_staff)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Verificación empírica del backend 1c (REGLA SUPREMA, la corre el controlador)

Con datos reales SIGMAN: llamar `homologar_archivos([("mapeo", Mapeo Año Actual bytes), ("balance", BALANCE SIGMAN bytes), ("resultados", RESULTADOS SIGMAN bytes)])` y confirmar:
- `esf.periodos` = 4, `eri.periodos` = 5.
- `esf.huerfanas` ≈ 109 (dedup) y `esf.filas` con 114 homologadas.
- El JSON serializa sin error (dict plano).

---

## PARTE B — FRONTEND (ejecución INTERACTIVA verificada, NO subagente a ciegas)

> Esta parte se construye paso a paso levantando el backend + el portal y verificando en el navegador con archivos reales de SIGMAN. NO se ejecuta con subagentes que solo compilan.

### Componentes (frontend/src/aud/ y api)
1. **`api.js`**: `motorBalancesHomologar(files)` y `motorBalancesRecalcular(esf, eri)` (POST a los endpoints).
2. **`catalog.js`**: nueva categoría/tool "Motor de balances" en el catálogo AUD.
3. **`MotorBalances.jsx`** (nuevo): estructura estilo `FlujoDashboard` (PortalShell + panel + barras de chips + tarjetas numeradas + preview), reutilizando clases `pc-*`/`fx-*`.
   - **Ingesta multiarchivo**: chips para subir balances/resultados (varios) + mapeado base (opcional).
   - **Barra de cuadre** por período (✓/⚠) arriba de cada tabla.
   - **Grilla editable N-períodos** (generalización de `BalanzasEditor`): columnas de saldo dinámicas por período; cuentas huérfanas en ámbar; **desplegables enlazados Super↔SRI** usando `plan.super_a_sri`/`sri_a_super` (elegir uno completa el otro; 1:N deja el SRI abierto).
   - **5 secciones** (tarjetas): 1 Balances homologados (ESF), 2 Resultados homologado (ERI), 3 Traslado Superintendencia, 4 Situación Financiera Superintendencia (N columnas), 5 Resultados Integral Superintendencia.
   - **Recálculo**: al editar código/saldo → `motorBalancesRecalcular` → actualiza cuadre + huérfanas.

### Verificación (interactiva, obligatoria antes de dar por hecho)
- Levantar backend + `frontend` (staff), entrar a AUD → Análisis → Motor de balances.
- Subir BALANCE + RESULTADOS + Mapeo Año Actual de SIGMAN.
- Confirmar visualmente: períodos como columnas, código+nombre del cliente, huérfanas en ámbar, elegir Super Cías en una huérfana autocompleta el SRI y la fila se vuelve verde, el banner de cuadre reacciona. Screenshot como evidencia.

### Fuera de alcance de 1c (fase posterior)
- `generador._hoja_estructura` a N columnas para exportar las secciones Superintendencia a Excel (hoy 2 columnas). Se hará cuando la UI esté verificada.
- Descarga del balance homologado / traslado real al Flujo 95xx + F-101.
