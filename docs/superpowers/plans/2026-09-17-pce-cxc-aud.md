# Matriz de pérdidas crediticias esperadas (CxC) en el Command Center — Plan de implementación

> **Para quien lo ejecute:** usar `superpowers:subagent-driven-development` (recomendado) o
> `superpowers:executing-plans`, tarea por tarea. Los pasos llevan casilla (`- [ ]`) para control.
>
> **Repositorio destino:** `C:\Users\LENOVO\Desktop\PROYECTOS CLAUDE\auditbrain-python-runner`.
> Copiar este archivo a `docs/superpowers/plans/2026-09-17-pce-cxc-aud.md` del repositorio antes de empezar.

**Goal:** activar la tarjeta "Cuentas por cobrar" del módulo AUD con una herramienta que mida la
pérdida crediticia esperada de la cartera comercial bajo el enfoque simplificado de NIIF 9, a partir de
tres análisis de antigüedad, y entregue un Excel auditable como papel de trabajo.

**Architecture:** el cálculo vive en un motor determinístico en Python dentro del backend
(`backend/app/aud/pce_cxc/`), expuesto por un router propio con `require_staff`, igual que el Motor de
balances. El frontend es un componente React en `frontend/src/aud/` que sube los tres cortes, muestra los
resultados por pestañas y descarga el Excel. El navegador no calcula nada: la cifra oficial la produce el
motor, se persiste con sus parámetros y se puede reproducir.

**Tech Stack:** FastAPI · SQLAlchemy · openpyxl · pytest (backend) · React + Vite · Vitest (frontend).

## Global Constraints

- Rama `feat/aud-cxc-pce` desde `main` actualizado. **Nunca push a `main`**: `render.yaml` tiene
  `autoDeploy: true` y publica en `consola.audit-ia.ec`. Se entrega por pull request y no se fusiona.
- Commits en español con el formato del repositorio: `feat(aud): …`, `fix(aud): …`, `test(aud): …`.
- **No agregar dependencias.** Se usa lo ya presente en `requirements-prod.txt`: `openpyxl==3.1.5`,
  `pandas==2.1.4`, `numpy==1.26.4`, `fastapi`, `sqlalchemy`, `pydantic`. `polars` y `duckdb` están
  **excluidos a propósito** por consumo de memoria en el plan starter; no reintroducirlos.
- Idioma: español en interfaz, mensajes, nombres de función y comentarios, igual que el resto de `aud/`.
- Moneda USD, formato `#,##0.00`, redondeo a dos decimales **medio hacia arriba** (nunca `round()` de
  Python, que redondea al par).
- Regla suprema del `CLAUDE.md` del repositorio: nada se declara terminado sin evidencia empírica. Cada
  tarea termina con la salida real de sus pruebas.
- Reglas de medición que el código debe hacer cumplir (NIIF 9 y registro de decisiones del encargo):
  1. Enfoque simplificado: pérdida esperada de toda la vida, sin etapas (párr. 5.5.15).
  2. La matriz se aplica al **importe en libros bruto**, es decir, el saldo pendiente (párr. B5.5.35).
  3. **Sin descuento** por defecto: en cartera comercial de corto plazo la tasa efectiva es cero
     (párr. B5.5.44). Descontar exige tasa y horizonte declarados.
  4. El **ajuste prospectivo exige justificación escrita**; sin ella no se aplica (párr. B5.5.51-52).
     Un factor 1,000 sin sustento se reporta como hallazgo, no como simplificación.
  5. Una banda **sin historia queda sin medir**, nunca en cero. Se resuelve con una tasa sustituta
     justificada o se declara limitación de alcance.
  6. Los saldos que superan el umbral de evaluación individual **salen de la matriz** y se miden uno por
     uno; su exposición no se mide dos veces.
  7. La exposición se **ancla a la cartera contabilizada**; la diferencia contra el archivo analítico se
     informa como partida conciliatoria y nunca se absorbe en silencio.
  8. La mora se cuenta **desde la fecha de vencimiento contractual**, nunca desde la emisión.
  9. La banda más antigua se **desdobla en el umbral de incumplimiento** antes de calcular.
  10. Ninguna fila se descarta en silencio: lo excluido se cuantifica y se reporta.
  11. El 1% y el 10% de la LORTI son **límites de deducción**, jamás piso ni techo de la estimación.
- Variables que el sistema **no inventa** y que entran como parámetros del encargo: materialidad de
  desempeño, umbral de evaluación individual, factor prospectivo y su justificación, tasas sustitutas.
  Si faltan, el resultado las reporta como pendientes y no concluye.

---

## Estructura de archivos

**Backend (nuevo paquete `backend/app/aud/pce_cxc/`):**

| Archivo | Responsabilidad |
|---|---|
| `bandas.py` | Bandas de mora, clasificación por días y desdoblamiento en el umbral |
| `lectura.py` | Lectura de importes y fechas de cualquier formato, y del archivo de cartera |
| `cohortes.py` | Tasas de pérdida por permanencia entre dos cortes |
| `motor.py` | Medición: matriz colectiva, evaluación individual, conciliación, cuadro tributario |
| `service.py` | Orquesta lectura → cohortes → medición; arma hallazgos y pendientes |
| `schemas.py` | Modelos Pydantic de entrada y salida |
| `models.py` | Tabla de corridas persistidas |
| `exporter.py` | Excel del papel de trabajo con fórmulas visibles |
| `router.py` | Endpoints HTTP con `require_staff` |

**Backend (modificar):** `backend/app/api/__init__.py` (registrar el router), `backend/app/db/session.py`
(crear la tabla nueva en el arranque, siguiendo el patrón existente).

**Frontend:** `frontend/src/aud/PceCxcTool.jsx` y `pceCxc.css` (nuevos); `frontend/src/aud/catalog.js`,
`frontend/src/aud/ToolCatalog.jsx` y `frontend/src/api.js` (modificar).

**Pruebas:** `tests/test_pce_bandas.py`, `test_pce_lectura.py`, `test_pce_cohortes.py`,
`test_pce_motor.py`, `test_pce_service.py`, `test_pce_router.py`, `test_pce_exporter.py`;
`frontend/src/aud/pceCxc.test.js`.

**Fuente de referencia ya escrita y probada** (repositorio `audit-ia-artefactos`, 28 pruebas en verde):
`auditbrain-external-audit-work/engine/ecl_niif9.py` y `tests/test_ecl_niif9.py`. La tarea 5 lo porta.

---

### Task 1: Bandas de mora

**Files:**
- Create: `backend/app/aud/pce_cxc/__init__.py` (vacío)
- Create: `backend/app/aud/pce_cxc/bandas.py`
- Test: `tests/test_pce_bandas.py`

**Interfaces:**
- Consumes: nada.
- Produces: `BANDAS_POR_DEFECTO: list[dict]` con claves `nombre`, `desde`, `hasta`, `origen`;
  `clasificar(dias: int, bandas: list[dict]) -> str`;
  `desdoblar(bandas: list[dict], umbral_dias: int) -> list[dict]`.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_pce_bandas.py
"""Bandas de mora del papel de trabajo de cuentas por cobrar."""
import pytest

from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO, clasificar, desdoblar


def test_una_factura_no_vencida_esta_por_vencer():
    assert clasificar(0, BANDAS_POR_DEFECTO) == "Por vencer"
    assert clasificar(-30, BANDAS_POR_DEFECTO) == "Por vencer"


def test_limites_de_cada_banda():
    casos = {1: "0 a 30 días", 30: "0 a 30 días", 31: "31 a 60 días", 60: "31 a 60 días",
             61: "61 a 90 días", 90: "61 a 90 días", 91: "91 a 180 días", 180: "91 a 180 días",
             181: "181 a 360 días", 360: "181 a 360 días", 361: "Más de 360 días", 5000: "Más de 360 días"}
    for dias, esperado in casos.items():
        assert clasificar(dias, BANDAS_POR_DEFECTO) == esperado, dias


def test_la_banda_abierta_se_desdobla_en_el_umbral():
    b = desdoblar(BANDAS_POR_DEFECTO, 730)
    assert [x["nombre"] for x in b][-2:] == ["361 a 730 días", "Más de 730 días"]
    assert clasificar(500, b) == "361 a 730 días"
    assert clasificar(731, b) == "Más de 730 días"


def test_la_banda_desdoblada_recuerda_su_banda_de_origen():
    b = desdoblar(BANDAS_POR_DEFECTO, 730)
    assert b[-1]["origen"] == "Más de 360 días"
    assert b[-2]["origen"] == "Más de 360 días"


def test_no_se_desdobla_si_el_umbral_cae_fuera_de_la_banda_abierta():
    assert desdoblar(BANDAS_POR_DEFECTO, 200) == BANDAS_POR_DEFECTO


def test_dias_sin_banda_es_error():
    with pytest.raises(ValueError):
        clasificar(50, [{"nombre": "1 a 30", "desde": 1, "hasta": 30, "origen": "1 a 30"}])
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_pce_bandas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.aud.pce_cxc'`

- [ ] **Step 3: Implementar**

```python
# backend/app/aud/pce_cxc/bandas.py
"""Bandas de mora de la matriz de pérdidas esperadas.

La mora se cuenta desde la fecha de vencimiento contractual. Una factura cuyo
vencimiento es posterior o igual a la fecha de corte está POR VENCER y nunca cae
en el primer tramo de mora.
"""
from __future__ import annotations

from typing import Any

BANDA_POR_VENCER = "Por vencer"

BANDAS_POR_DEFECTO: list[dict[str, Any]] = [
    {"nombre": BANDA_POR_VENCER, "desde": None, "hasta": 0, "origen": BANDA_POR_VENCER},
    {"nombre": "0 a 30 días", "desde": 1, "hasta": 30, "origen": "0 a 30 días"},
    {"nombre": "31 a 60 días", "desde": 31, "hasta": 60, "origen": "31 a 60 días"},
    {"nombre": "61 a 90 días", "desde": 61, "hasta": 90, "origen": "61 a 90 días"},
    {"nombre": "91 a 180 días", "desde": 91, "hasta": 180, "origen": "91 a 180 días"},
    {"nombre": "181 a 360 días", "desde": 181, "hasta": 360, "origen": "181 a 360 días"},
    {"nombre": "Más de 360 días", "desde": 361, "hasta": None, "origen": "Más de 360 días"},
]


def clasificar(dias: int, bandas: list[dict[str, Any]]) -> str:
    """Devuelve el nombre de la banda que corresponde a esos días de mora."""
    if dias <= 0:
        for b in bandas:
            if b["desde"] is None:
                return b["nombre"]
    for b in bandas:
        if b["desde"] is None:
            continue
        if dias >= b["desde"] and (b["hasta"] is None or dias <= b["hasta"]):
            return b["nombre"]
    raise ValueError(f"No hay banda definida para {dias} días de mora")


def desdoblar(bandas: list[dict[str, Any]], umbral_dias: int) -> list[dict[str, Any]]:
    """Parte la banda abierta en el umbral de incumplimiento.

    Una banda abierta mezcla cartera todavía gestionable con cartera perdida; el
    desdoblamiento separa las dos antes de calcular. Cada mitad conserva el nombre
    de la banda de la que proviene para poder compararla con la política del cliente.
    """
    ultima = bandas[-1]
    if ultima["hasta"] is not None or ultima["desde"] is None or umbral_dias <= ultima["desde"]:
        return bandas
    return bandas[:-1] + [
        {"nombre": f"{ultima['desde']} a {umbral_dias} días", "desde": ultima["desde"],
         "hasta": umbral_dias, "origen": ultima["nombre"]},
        {"nombre": f"Más de {umbral_dias} días", "desde": umbral_dias + 1,
         "hasta": None, "origen": ultima["nombre"]},
    ]
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `.venv\Scripts\python -m pytest tests/test_pce_bandas.py -v`
Expected: PASS, 6 pruebas.

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/pce_cxc/__init__.py backend/app/aud/pce_cxc/bandas.py tests/test_pce_bandas.py
git commit -m "feat(aud): bandas de mora con desdoblamiento en el umbral de incumplimiento"
```

---

### Task 2: Lectura de importes y fechas

**Files:**
- Create: `backend/app/aud/pce_cxc/lectura.py`
- Test: `tests/test_pce_lectura.py`

**Interfaces:**
- Consumes: nada.
- Produces: `a_numero(valor: Any) -> float`; `inferir_formato_fecha(valores: Iterable[Any]) -> str`
  (devuelve `"nativo" | "dmy" | "mdy" | "ambiguo" | "inconsistente"`);
  `a_fecha(valor: Any, formato: str = "dmy") -> date | None`.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_pce_lectura.py
"""Lectura de importes y fechas de los archivos del cliente."""
from datetime import date, datetime

import pytest

from backend.app.aud.pce_cxc.lectura import a_fecha, a_numero, inferir_formato_fecha


@pytest.mark.parametrize("entrada,esperado", [
    ("1234.56", 1234.56), ("1,234.56", 1234.56), ("1.234,56", 1234.56),
    ("8.917.458,00", 8917458.00), ("8,917,458.00", 8917458.00),
    ("(1.500,00)", -1500.00), ("-987,65", -987.65), ("USD 4 758 048,77", 4758048.77),
    ("1.500", 1500.0), ("", 0.0), (None, 0.0), (1234.56, 1234.56),
])
def test_importes_en_cualquier_formato(entrada, esperado):
    assert a_numero(entrada) == pytest.approx(esperado, abs=0.005)


def test_formato_de_fecha_deducido_del_propio_archivo():
    assert inferir_formato_fecha(["31/12/2025", "05/03/2025"]) == "dmy"
    assert inferir_formato_fecha(["12/31/2025", "03/05/2025"]) == "mdy"
    assert inferir_formato_fecha(["05/03/2025", "07/11/2025"]) == "ambiguo"
    assert inferir_formato_fecha(["31/12/2025", "12/31/2025"]) == "inconsistente"
    assert inferir_formato_fecha([datetime(2025, 12, 31)]) == "nativo"


def test_lectura_de_fechas_segun_el_formato():
    assert a_fecha("31/12/2025", "dmy") == date(2025, 12, 31)
    assert a_fecha("12/31/2025", "mdy") == date(2025, 12, 31)
    assert a_fecha("2025-12-31") == date(2025, 12, 31)
    assert a_fecha(datetime(2025, 12, 31)) == date(2025, 12, 31)
    assert a_fecha("no es fecha") is None
    assert a_fecha(None) is None
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_pce_lectura.py -v`
Expected: FAIL con `ImportError: cannot import name 'a_numero'`

- [ ] **Step 3: Implementar**

```python
# backend/app/aud/pce_cxc/lectura.py
"""Lectura de los archivos de cartera del cliente.

Los archivos llegan con el formato regional del sistema que los generó. Aquí se
normalizan importes y fechas antes de que el motor vea un solo número.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable

_PATRON_DMY = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$")
_PATRON_ISO = re.compile(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})")


def a_numero(valor: Any) -> float:
    """Convierte a número respetando cualquier formato regional.

    El separador decimal es el último que aparece; el otro es de miles. Un único
    separador seguido de exactamente tres dígitos es de miles: "1.500" son mil
    quinientos. Los paréntesis indican negativo.
    """
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    s = str(valor).strip()
    if not s:
        return 0.0
    negativo = s.startswith("(") and s.endswith(")") or "-" in s
    s = re.sub(r"[^0-9.,]", "", s)
    if not s:
        return 0.0
    i = max(s.rfind(","), s.rfind("."))
    entero, decimal = s, ""
    if i >= 0:
        cola = s[i + 1:]
        unico = len(re.sub(r"[^.,]", "", s)) == 1
        if not (unico and len(cola) == 3):
            entero, decimal = s[:i], cola
    entero = re.sub(r"[.,]", "", entero)
    try:
        n = float(f"{entero}.{decimal}" if decimal else entero or "0")
    except ValueError:
        return 0.0
    return -n if negativo and n > 0 else n


def inferir_formato_fecha(valores: Iterable[Any]) -> str:
    """Deduce si las fechas del archivo son día/mes/año o mes/día/año."""
    dmy = mdy = total = 0
    for v in valores:
        if isinstance(v, (date, datetime)):
            return "nativo"
        m = _PATRON_DMY.match(str(v or "").strip())
        if not m:
            continue
        total += 1
        if int(m.group(1)) > 12:
            dmy += 1
        if int(m.group(2)) > 12:
            mdy += 1
    if not total:
        return "nativo"
    if dmy and mdy:
        return "inconsistente"
    if dmy:
        return "dmy"
    if mdy:
        return "mdy"
    return "ambiguo"


def a_fecha(valor: Any, formato: str = "dmy") -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if valor is None or valor == "":
        return None
    s = str(valor).strip()
    m = _PATRON_DMY.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        anio = int(m.group(3))
        anio += 2000 if anio < 100 else 0
        dia, mes = (b, a) if formato == "mdy" else (a, b)
        try:
            return date(anio, mes, dia)
        except ValueError:
            return None
    m = _PATRON_ISO.match(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `.venv\Scripts\python -m pytest tests/test_pce_lectura.py -v`
Expected: PASS, 15 pruebas (12 del parametrizado + 3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/pce_cxc/lectura.py tests/test_pce_lectura.py
git commit -m "feat(aud): lectura de importes y fechas independiente del formato regional"
```

---

### Task 3: Lector del análisis de antigüedad

**Files:**
- Modify: `backend/app/aud/pce_cxc/lectura.py` (agregar al final)
- Test: `tests/test_pce_lectura_cartera.py`

**Interfaces:**
- Consumes: `a_numero`, `a_fecha`, `inferir_formato_fecha` de la tarea 2; `clasificar` de la tarea 1.
- Produces: `CAMPOS: dict[str, list[str]]` (pistas por campo);
  `leer_cartera(contenido: bytes, nombre: str, corte: date, bandas: list[dict], hoja: str | None = None,
  mapeo: dict[str, int] | None = None, clave_relacionadas: str = "RELACIONAD") -> dict` con claves
  `filas` (lista de dicts `cliente`, `documento`, `segmento`, `emision`, `vencimiento`, `saldo`,
  `dias`, `banda`, `fila_origen`, `repetido`), `hoja`, `fila_encabezado`, `mapeo`, `formato_fecha`,
  `duplicados_exactos`, `documentos_repetidos`, `descartados`, `total_saldo`.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_pce_lectura_cartera.py
"""Lectura del análisis de antigüedad a nivel de documento."""
import io
from datetime import date

from openpyxl import Workbook

from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO
from backend.app.aud.pce_cxc.lectura import leer_cartera

CORTE = date(2025, 12, 31)


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.title = "Cartera"
    ws.append(["Cliente", "N° Documento", "Tipo de cliente", "Fecha emisión",
               "Fecha vencimiento", "Saldo"])
    for f in filas:
        ws.append(list(f))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_lee_documentos_y_los_clasifica_por_mora():
    datos = _xlsx([
        ("ALFA S.A.", "F-1", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 1000.0),
        ("BETA CIA", "F-2", "RELACIONADOS", date(2025, 1, 1), date(2026, 3, 1), 500.0),
    ])
    r = leer_cartera(datos, "cartera.xlsx", CORTE, BANDAS_POR_DEFECTO)
    assert r["fila_encabezado"] == 1
    assert r["formato_fecha"] == "nativo"
    assert [f["banda"] for f in r["filas"]] == ["0 a 30 días", "Por vencer"]
    assert [f["segmento"] for f in r["filas"]] == ["NO-RELACIONADOS", "RELACIONADOS"]
    assert r["total_saldo"] == 1500.0


def test_descarta_filas_identicas_y_conserva_documentos_repetidos_distintos():
    fila = ("ALFA S.A.", "F-1", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 1000.0)
    distinta = ("ALFA S.A.", "F-1", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 250.0)
    r = leer_cartera(_xlsx([fila, fila, distinta]), "c.xlsx", CORTE, BANDAS_POR_DEFECTO)
    assert r["duplicados_exactos"] == 1
    assert r["documentos_repetidos"] == 1
    assert len(r["filas"]) == 2
    assert r["total_saldo"] == 1250.0


def test_reporta_lo_descartado_sin_perderlo_en_silencio():
    r = leer_cartera(_xlsx([
        ("ALFA S.A.", "F-1", "NO-RELACIONADOS", date(2025, 9, 1), None, 800.0),
        ("BETA CIA", "", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 900.0),
    ]), "c.xlsx", CORTE, BANDAS_POR_DEFECTO)
    assert len(r["filas"]) == 0
    assert [d["motivo"] for d in r["descartados"]] == ["sin fecha de vencimiento", "sin número de documento"]
    assert sum(d["saldo"] for d in r["descartados"]) == 1700.0


def test_el_mapeo_manual_manda_sobre_la_deteccion():
    wb = Workbook()
    ws = wb.active
    ws.append(["A", "B", "C", "D", "E", "F"])
    ws.append(["ALFA", "F-9", "NO-RELACIONADOS", date(2025, 1, 1), date(2025, 6, 1), 700.0])
    bio = io.BytesIO()
    wb.save(bio)
    r = leer_cartera(bio.getvalue(), "c.xlsx", CORTE, BANDAS_POR_DEFECTO,
                     mapeo={"cliente": 0, "documento": 1, "tipo": 2, "emision": 3,
                            "vencimiento": 4, "saldo": 5})
    assert len(r["filas"]) == 1
    assert r["filas"][0]["banda"] == "181 a 360 días"
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_pce_lectura_cartera.py -v`
Expected: FAIL con `ImportError: cannot import name 'leer_cartera'`

- [ ] **Step 3: Implementar (agregar al final de `lectura.py`)**

```python
import io

from openpyxl import load_workbook

from backend.app.aud.pce_cxc.bandas import clasificar

# Pistas para reconocer cada columna en el archivo del cliente.
CAMPOS: dict[str, list[str]] = {
    "cliente": ["cliente", "razon", "razón", "nombre", "deudor"],
    "documento": ["documento", "comprobante", "factura", "numero", "número", "nro", "n°"],
    "tipo": ["tipo", "relacion", "relación", "clasif", "categoria", "categoría"],
    "emision": ["emision", "emisión", "fecha emis", "f. emis"],
    "vencimiento": ["vencimiento", "vence", "venc"],
    "saldo": ["saldo", "monto", "valor", "importe", "total", "cuentas por cobrar"],
}
_OBLIGATORIOS = ("documento", "vencimiento", "saldo")


def _detectar_encabezado(filas: list[tuple]) -> int:
    mejor, puntaje = -1, 0
    for i, fila in enumerate(filas[:45]):
        celdas = [str(c or "").lower() for c in fila]
        p = sum(1 for pistas in CAMPOS.values() if any(any(h in c for h in pistas) for c in celdas))
        if p > puntaje:
            mejor, puntaje = i, p
    return mejor if puntaje >= 3 else -1


def _mapear(encabezado: tuple) -> dict[str, int]:
    celdas = [str(c or "").lower().strip() for c in encabezado]
    mapeo: dict[str, int] = {}
    usadas: set[int] = set()
    for campo, pistas in CAMPOS.items():
        for pista in pistas:
            idx = next((j for j, c in enumerate(celdas) if pista in c and j not in usadas), None)
            if idx is not None:
                mapeo[campo] = idx
                usadas.add(idx)
                break
    return mapeo


def leer_cartera(contenido: bytes, nombre: str, corte, bandas, hoja=None, mapeo=None,
                 clave_relacionadas: str = "RELACIONAD") -> dict:
    """Lee un análisis de antigüedad y devuelve sus documentos clasificados por mora."""
    wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    ws = wb[hoja] if hoja else wb.worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    wb.close()

    i_enc = 0 if mapeo else _detectar_encabezado(filas)
    if i_enc < 0:
        raise ValueError(f"{nombre}: no se identificó la fila de encabezados")
    cols = mapeo or _mapear(filas[i_enc])
    faltantes = [c for c in _OBLIGATORIOS if c not in cols]
    if faltantes:
        raise ValueError(f"{nombre}: no se encontraron las columnas {', '.join(faltantes)}")

    cuerpo = filas[i_enc + 1:]
    formato = inferir_formato_fecha([f[cols["vencimiento"]] for f in cuerpo[:4000]
                                     if len(f) > cols["vencimiento"]])

    salida, descartados = [], []
    vistas: set[tuple] = set()
    documentos: set[str] = set()
    dup_exactos = repetidos = 0

    def valor(fila, campo):
        j = cols.get(campo)
        return fila[j] if j is not None and j < len(fila) else None

    for n, fila in enumerate(cuerpo, start=i_enc + 2):
        if fila is None or all(v is None or str(v).strip() == "" for v in fila):
            continue
        documento = str(valor(fila, "documento") or "").strip()
        saldo = a_numero(valor(fila, "saldo"))
        vencimiento = a_fecha(valor(fila, "vencimiento"), formato)
        if not documento:
            descartados.append({"fila_origen": n, "motivo": "sin número de documento", "saldo": saldo})
            continue
        if vencimiento is None:
            descartados.append({"fila_origen": n, "motivo": "sin fecha de vencimiento", "saldo": saldo})
            continue
        if abs(saldo) < 0.005:
            descartados.append({"fila_origen": n, "motivo": "saldo cero", "saldo": saldo})
            continue
        cliente = str(valor(fila, "cliente") or "").strip()
        firma = (documento, round(saldo, 2), vencimiento, cliente)
        if firma in vistas:
            dup_exactos += 1
            continue
        vistas.add(firma)
        repetido = documento in documentos
        repetidos += 1 if repetido else 0
        documentos.add(documento)
        tipo = str(valor(fila, "tipo") or "").upper()
        es_rel = clave_relacionadas in tipo and f"NO-{clave_relacionadas}" not in tipo \
            and f"NO {clave_relacionadas}" not in tipo
        dias = (corte - vencimiento).days
        salida.append({
            "fila_origen": n, "cliente": cliente, "documento": documento,
            "segmento": "RELACIONADOS" if es_rel else "NO-RELACIONADOS",
            "emision": a_fecha(valor(fila, "emision"), formato),
            "vencimiento": vencimiento, "saldo": saldo, "dias": dias,
            "banda": clasificar(dias, bandas), "repetido": repetido,
        })

    return {"filas": salida, "hoja": ws.title, "fila_encabezado": i_enc + 1, "mapeo": cols,
            "formato_fecha": formato, "duplicados_exactos": dup_exactos,
            "documentos_repetidos": repetidos, "descartados": descartados,
            "total_saldo": round(sum(f["saldo"] for f in salida), 2)}
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `.venv\Scripts\python -m pytest tests/test_pce_lectura_cartera.py -v`
Expected: PASS, 4 pruebas.

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/pce_cxc/lectura.py tests/test_pce_lectura_cartera.py
git commit -m "feat(aud): lector del analisis de antiguedad con deteccion de columnas y control de duplicados"
```

---

### Task 4: Tasas por permanencia (cohortes)

**Files:**
- Create: `backend/app/aud/pce_cxc/cohortes.py`
- Test: `tests/test_pce_cohortes.py`

**Interfaces:**
- Consumes: la salida de `leer_cartera` (tarea 3).
- Produces: `tasas_por_permanencia(cohorte: list[dict], actual: list[dict]) -> dict` con claves
  `tasas` (`{segmento: {banda: float | None}}`), `detalle`
  (`{segmento: {banda: {"inicial": float, "remanente": float, "documentos": int}}}`) y
  `trazabilidad` (proporción de documentos de la cohorte localizables en el corte actual).

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_pce_cohortes.py
"""Derivación de tasas de pérdida por permanencia a 24 meses."""
import pytest

from backend.app.aud.pce_cxc.cohortes import tasas_por_permanencia


def _doc(documento, banda, saldo, segmento="NO-RELACIONADOS"):
    return {"documento": documento, "banda": banda, "saldo": saldo, "segmento": segmento}


def test_la_tasa_es_el_saldo_que_sigue_vivo_sobre_la_cohorte_inicial():
    cohorte = [_doc("F-1", "0 a 30 días", 100000.0), _doc("F-2", "0 a 30 días", 50000.0)]
    actual = [_doc("F-1", "Más de 360 días", 15000.0)]
    r = tasas_por_permanencia(cohorte, actual)
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(0.10)
    assert r["detalle"]["NO-RELACIONADOS"]["0 a 30 días"]["documentos"] == 2


def test_una_banda_sin_cohorte_no_tiene_tasa():
    r = tasas_por_permanencia([_doc("F-1", "0 a 30 días", 1000.0)], [])
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == 0.0
    assert r["tasas"]["NO-RELACIONADOS"].get("181 a 360 días") is None


def test_cada_segmento_tiene_su_propia_tasa():
    cohorte = [_doc("F-1", "Por vencer", 1000.0), _doc("R-1", "Por vencer", 2000.0, "RELACIONADOS")]
    actual = [_doc("R-1", "Por vencer", 1000.0, "RELACIONADOS")]
    r = tasas_por_permanencia(cohorte, actual)
    assert r["tasas"]["NO-RELACIONADOS"]["Por vencer"] == pytest.approx(0.0)
    assert r["tasas"]["RELACIONADOS"]["Por vencer"] == pytest.approx(0.5)


def test_la_trazabilidad_mide_cuantos_documentos_se_reencuentran():
    cohorte = [_doc("F-1", "Por vencer", 10.0), _doc("F-2", "Por vencer", 10.0)]
    r = tasas_por_permanencia(cohorte, [_doc("F-1", "Por vencer", 5.0)])
    assert r["trazabilidad"] == pytest.approx(0.5)
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_pce_cohortes.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.aud.pce_cxc.cohortes'`

- [ ] **Step 3: Implementar**

```python
# backend/app/aud/pce_cxc/cohortes.py
"""Tasas de pérdida derivadas del comportamiento observado de la cartera.

Método de permanencia: se toma el saldo de cada documento en el corte más antiguo
y se rastrea por su número en el corte actual. Lo que sigue vivo veinticuatro meses
después es lo que no se recuperó, y esa permanencia sí es directamente observable.
La inferencia "si desapareció, se cobró" solo es válida si los castigos del período
fueron inmateriales: por eso el servicio exige el mayor de la provisión.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def tasas_por_permanencia(cohorte: list[dict[str, Any]], actual: list[dict[str, Any]]) -> dict:
    saldo_actual: dict[str, float] = defaultdict(float)
    for f in actual:
        saldo_actual[f["documento"]] += float(f["saldo"])

    detalle: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for f in cohorte:
        d = detalle[f["segmento"]].setdefault(f["banda"], {"inicial": 0.0, "remanente": 0.0, "documentos": 0})
        d["inicial"] += float(f["saldo"])
        d["remanente"] += saldo_actual.get(f["documento"], 0.0)
        d["documentos"] += 1

    tasas: dict[str, dict[str, float | None]] = {}
    for segmento, bandas in detalle.items():
        tasas[segmento] = {}
        for banda, d in bandas.items():
            tasas[segmento][banda] = (d["remanente"] / d["inicial"]) if d["inicial"] > 0 else None

    encontrados = sum(1 for f in cohorte if f["documento"] in saldo_actual)
    return {"tasas": tasas, "detalle": {s: dict(b) for s, b in detalle.items()},
            "trazabilidad": (encontrados / len(cohorte)) if cohorte else 0.0}
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `.venv\Scripts\python -m pytest tests/test_pce_cohortes.py -v`
Expected: PASS, 4 pruebas.

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/pce_cxc/cohortes.py tests/test_pce_cohortes.py
git commit -m "feat(aud): tasas de perdida por permanencia a 24 meses por segmento y banda"
```

---

### Task 5: Motor de medición

**Files:**
- Create: `backend/app/aud/pce_cxc/motor.py`
- Test: `tests/test_pce_motor.py`
- Copiar desde: `audit-ia-artefactos/auditbrain-external-audit-work/engine/ecl_niif9.py` y
  `.../tests/test_ecl_niif9.py` (ya escritos y con 28 pruebas en verde).

**Interfaces:**
- Consumes: nada del repositorio; recibe exposiciones ya clasificadas.
- Produces: `redondear(valor: float) -> float`;
  `ParametrosECL(tasas_perdida: dict[str, float], lgd: float | dict = 1.0, ajuste_prospectivo: float = 0.0,
  justificacion_ajuste: str = "", tasa_descuento: float | None = None, horizontes: dict | None = None,
  fuente_tasas: str = "")`;
  `medir_ecl(exposiciones: dict[str, float], parametros: ParametrosECL) -> dict`;
  `evaluar_individual(casos: list[dict]) -> dict`;
  `resumen_deterioro(exposiciones, parametros, casos_individuales=None, saldo_contable=None) -> dict`.

- [ ] **Step 1: Copiar el motor y sus pruebas**

```bash
copy "..\audit-ia-artefactos\auditbrain-external-audit-work\engine\ecl_niif9.py" "backend\app\aud\pce_cxc\motor.py"
copy "..\audit-ia-artefactos\auditbrain-external-audit-work\tests\test_ecl_niif9.py" "tests\test_pce_motor.py"
```

- [ ] **Step 2: Ajustar los imports al paquete del repositorio**

En `tests/test_pce_motor.py` reemplazar la línea de import por:

```python
from backend.app.aud.pce_cxc.motor import (
    ParametrosECL, evaluar_individual, medir_ecl, promediar_tasas, resumen_deterioro, tasa_perdida,
)
```

- [ ] **Step 3: Adaptar el motor a las bandas del encargo**

En `motor.py`, reemplazar la medición sin tasa para que una banda sin tasa quede **sin medir** en lugar
de excluirse del diccionario (el resto del archivo queda igual):

```python
    filas = []
    total = 0.0
    exposicion_total = 0.0
    sin_medir = 0.0
    for tramo, saldo in exposiciones.items():
        saldo = float(saldo or 0)
        exposicion_total += saldo
        tasa = parametros.tasas_perdida.get(tramo)
        if tasa is None:
            sin_medir += saldo
            filas.append({"tramo": tramo, "exposicion": redondear(saldo), "tasa_perdida": None,
                          "tasa_ajustada": None, "lgd": None, "horizonte": None,
                          "factor_descuento": None, "ecl": None})
            continue
        tasa_ajustada = float(tasa) * (1 + parametros.ajuste_prospectivo)
        lgd = parametros.lgd_de(tramo)
        if parametros.tasa_descuento is None:
            factor, t = 1.0, None
        else:
            t = parametros.horizontes.get(tramo)
            if t is None:
                raise ValueError(f"Falta el horizonte del tramo '{tramo}' para descontar")
            factor = 1 / (1 + parametros.tasa_descuento) ** float(t)
        ecl = redondear(saldo * tasa_ajustada * lgd * factor)
        total += ecl
        filas.append({"tramo": tramo, "exposicion": redondear(saldo), "tasa_perdida": float(tasa),
                      "tasa_ajustada": tasa_ajustada, "lgd": lgd, "horizonte": t,
                      "factor_descuento": factor, "ecl": ecl})
```

y agregar `"exposicion_sin_medir": redondear(sin_medir)` al diccionario devuelto por `medir_ecl`.

- [ ] **Step 4: Escribir la prueba de la regla nueva**

```python
# añadir a tests/test_pce_motor.py
def test_una_banda_sin_tasa_queda_sin_medir_y_no_en_cero():
    p = ParametrosECL(tasas_perdida={"1-60": 0.10}, lgd=1.0)
    r = medir_ecl({"1-60": 100000.0, "361+": 50000.0}, p)
    fila = next(t for t in r["tramos"] if t["tramo"] == "361+")
    assert fila["ecl"] is None
    assert r["exposicion_sin_medir"] == pytest.approx(50000.0)
    assert r["ecl_total"] == pytest.approx(10000.0)
```

- [ ] **Step 5: Correr las pruebas**

Run: `.venv\Scripts\python -m pytest tests/test_pce_motor.py -v`
Expected: PASS, 29 pruebas (las 28 portadas más la nueva). La prueba de aceptación que reproduce el
archivo del cliente (190.655,33) debe seguir en verde.

- [ ] **Step 6: Commit**

```bash
git add backend/app/aud/pce_cxc/motor.py tests/test_pce_motor.py
git commit -m "feat(aud): motor de medicion de perdidas esperadas NIIF 9 con bandas sin medir"
```

---

### Task 6: Servicio de análisis

**Files:**
- Create: `backend/app/aud/pce_cxc/service.py`
- Test: `tests/test_pce_service.py`

**Interfaces:**
- Consumes: `leer_cartera` (tarea 3), `tasas_por_permanencia` (tarea 4), `ParametrosECL`,
  `resumen_deterioro` (tarea 5), `desdoblar` (tarea 1).
- Produces: `analizar(cortes: list[dict], parametros: dict) -> dict`, donde cada corte es
  `{"nombre": str, "contenido": bytes, "fecha": date, "hoja": str | None, "mapeo": dict | None}` y
  `parametros` acepta `umbral_dias_incumplimiento` (730), `umbral_individual`, `eeff`
  (`{"no_relacionados": float, "relacionados": float}`), `politica` (`{banda: tasa}`),
  `factor_prospectivo` (`{segmento: float}`), `justificacion_prospectivo`, `tasas_sustitutas`
  (`{"SEGMENTO|banda": {"tasa": float, "justificacion": str}}`), `evaluaciones_individuales`,
  `mayor_provision` (lista por ejercicio), `materialidad`.
  Devuelve `{"exposicion": …, "tasas": …, "matriz": …, "individual": …, "conciliacion": …,
  "tributario": …, "politica": …, "hallazgos": [...], "pendientes": [...], "bitacora": {...}}`.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_pce_service.py
"""Servicio que orquesta el análisis completo de pérdidas esperadas."""
import io
from datetime import date

import pytest
from openpyxl import Workbook

from backend.app.aud.pce_cxc.service import analizar


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Documento", "Tipo", "Emisión", "Vencimiento", "Saldo"])
    for f in filas:
        ws.append(list(f))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _cortes():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0),
                 ("BETA", "F-2", "NO-RELACIONADOS", date(2023, 1, 1), date(2023, 3, 1), 50000.0)])
    c24 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 20000.0)])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0),
                 ("GAMMA", "F-9", "NO-RELACIONADOS", date(2025, 9, 1), date(2025, 12, 1), 200000.0)])
    return [{"nombre": "2023.xlsx", "contenido": c23, "fecha": date(2023, 12, 31)},
            {"nombre": "2024.xlsx", "contenido": c24, "fecha": date(2024, 12, 31)},
            {"nombre": "2025.xlsx", "contenido": c25, "fecha": date(2025, 12, 31)}]


def test_mide_la_cartera_con_las_tasas_de_la_cohorte():
    r = analizar(_cortes(), {"umbral_dias_incumplimiento": 730})
    # F-1 estaba en "0 a 30 días" en 2023 con 100.000 y quedaron vivos 10.000 -> 10 %
    assert r["tasas"]["NO-RELACIONADOS"]["0 a 30 días"] == pytest.approx(0.10)
    # F-9 (200.000, 30 días de mora) se mide al 10 %; F-1 cayó en "Más de 730 días",
    # banda sin historia en la cohorte, así que queda sin medir y no suma cero.
    assert r["matriz"]["ecl_total"] == pytest.approx(20000.0)
    assert r["matriz"]["exposicion_sin_medir"] == pytest.approx(10000.0)


def test_el_saldo_contable_manda_sobre_el_archivo_y_la_diferencia_se_informa():
    r = analizar(_cortes(), {"eeff": {"no_relacionados": 220000.0, "relacionados": 0.0}})
    # La exposición se ancla a los estados financieros y la conciliación cierra...
    assert r["exposicion"]["total"] == pytest.approx(220000.0)
    assert r["conciliacion"]["cuadra"] is True
    # ...pero la diferencia contra el archivo queda a la vista como partida conciliatoria.
    assert r["exposicion"]["segun_archivo"] == pytest.approx(210000.0)
    assert r["exposicion"]["factores_anclaje"]["NO-RELACIONADOS"] == pytest.approx(220000 / 210000)


def test_el_factor_prospectivo_sin_justificacion_genera_hallazgo():
    r = analizar(_cortes(), {})
    titulos = [h["titulo"] for h in r["hallazgos"]]
    assert "Ausencia del componente prospectivo" in titulos


def test_sin_materialidad_no_concluye():
    r = analizar(_cortes(), {})
    assert any(p["variable"] == "Materialidad de desempeño" for p in r["pendientes"])


def test_exige_los_tres_cortes():
    with pytest.raises(ValueError, match="tres"):
        analizar(_cortes()[:2], {})
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_pce_service.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.aud.pce_cxc.service'`

- [ ] **Step 3: Implementar**

```python
# backend/app/aud/pce_cxc/service.py
"""Orquesta el análisis de pérdidas crediticias esperadas de cuentas por cobrar.

Secuencia: leer los tres cortes -> derivar tasas de la cohorte más antigua ->
anclar la exposición a los estados financieros -> separar los saldos de evaluación
individual -> medir -> comparar contra la política del cliente -> armar hallazgos
y pendientes. Ningún parámetro se inventa: lo que falta se reporta.
"""
from __future__ import annotations

from typing import Any

from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO, desdoblar
from backend.app.aud.pce_cxc.cohortes import tasas_por_permanencia
from backend.app.aud.pce_cxc.lectura import leer_cartera
from backend.app.aud.pce_cxc.motor import (
    ParametrosECL, evaluar_individual, medir_ecl, redondear,
)

SEGMENTOS = ("NO-RELACIONADOS", "RELACIONADOS")


def analizar(cortes: list[dict[str, Any]], parametros: dict[str, Any]) -> dict[str, Any]:
    if len(cortes) != 3:
        raise ValueError("Se requieren los tres análisis de antigüedad: sin tres cierres no existe "
                         "una cohorte con ventana completa de 24 meses")
    umbral_dias = int(parametros.get("umbral_dias_incumplimiento") or 730)
    bandas = desdoblar(BANDAS_POR_DEFECTO, umbral_dias)
    nombres = [b["nombre"] for b in bandas]

    leidos = [leer_cartera(c["contenido"], c["nombre"], c["fecha"], bandas,
                           c.get("hoja"), c.get("mapeo")) for c in cortes]
    cohorte, _intermedio, actual = leidos

    coh = tasas_por_permanencia(cohorte["filas"], actual["filas"])
    tasas = coh["tasas"]

    # Evaluación individual: los clientes por encima del umbral salen de la matriz.
    umbral_ind = float(parametros.get("umbral_individual") or 0)
    por_cliente: dict[tuple[str, str], float] = {}
    for f in actual["filas"]:
        por_cliente[(f["segmento"], f["cliente"] or "(sin nombre)")] = \
            por_cliente.get((f["segmento"], f["cliente"] or "(sin nombre)"), 0.0) + f["saldo"]
    individuales = {k for k, v in por_cliente.items() if umbral_ind and v > umbral_ind}

    # Exposición por segmento y banda, anclada a los estados financieros.
    eeff = parametros.get("eeff") or {}
    meta = {"NO-RELACIONADOS": float(eeff.get("no_relacionados") or 0),
            "RELACIONADOS": float(eeff.get("relacionados") or 0)}
    ancla = sum(meta.values()) > 0
    total_seg = {s: 0.0 for s in SEGMENTOS}
    for f in actual["filas"]:
        total_seg[f["segmento"]] += f["saldo"]
    factor, sin_estratificar = {}, {}
    for s in SEGMENTOS:
        if not ancla:
            factor[s], sin_estratificar[s] = 1.0, 0.0
        elif total_seg[s] > 0:
            factor[s], sin_estratificar[s] = meta[s] / total_seg[s], 0.0
        else:
            factor[s], sin_estratificar[s] = 1.0, meta[s]

    # La matriz se mide POR SEGMENTO: terceros y relacionadas tienen comportamiento
    # de pago distinto y no pueden agruparse (NIIF 9 B5.5.35).
    colectiva = {s: {b: 0.0 for b in nombres} for s in SEGMENTOS}
    casos: dict[tuple[str, str], dict[str, Any]] = {}
    for f in actual["filas"]:
        clave = (f["segmento"], f["cliente"] or "(sin nombre)")
        saldo = f["saldo"] * factor[f["segmento"]]
        if clave in individuales:
            caso = casos.setdefault(clave, {"identificacion": clave[1], "segmento": clave[0],
                                            "saldo": 0.0, "bandas": {}})
            caso["saldo"] += saldo
            caso["bandas"][f["banda"]] = caso["bandas"].get(f["banda"], 0.0) + saldo
        else:
            colectiva[f["segmento"]][f["banda"]] += saldo

    # Tasas aplicadas: las observadas de cada segmento, o las sustituidas con
    # justificación escrita. Sin ninguna de las dos, la banda queda sin medir.
    sustitutas = parametros.get("tasas_sustitutas") or {}
    factores = parametros.get("factor_prospectivo") or {}
    justificacion = str(parametros.get("justificacion_prospectivo") or "")
    aplicadas: dict[str, dict[str, float]] = {}
    for s in SEGMENTOS:
        aplicadas[s] = {}
        for b in nombres:
            obs = tasas.get(s, {}).get(b)
            sus = sustitutas.get(f"{s}|{b}")
            if sus and str(sus.get("justificacion", "")).strip():
                aplicadas[s][b] = float(sus["tasa"])
            elif obs is not None:
                aplicadas[s][b] = obs

    evaluaciones = parametros.get("evaluaciones_individuales") or {}
    lista_casos = []
    for clave, caso in casos.items():
        est = evaluaciones.get(f"{clave[0]}|{clave[1]}")
        provisional = sum(v * aplicadas[clave[0]].get(b, 0.0) for b, v in caso["bandas"].items())
        propia = bool(est and str(est.get("justificacion", "")).strip())
        ecl_caso = float(est["ecl"]) if propia else provisional
        lista_casos.append({
            "identificacion": f"{caso['identificacion']} ({clave[0]})", "tramo": None,
            "saldo": caso["saldo"], "recuperacion_estimada": caso["saldo"] - ecl_caso,
            "sustento": (est or {}).get("justificacion",
                                        "Medido con la tasa de la matriz (provisional)"),
        })

    saldo_contable = sum(meta.values()) if ancla else None
    # Se mide cada segmento por separado y luego se consolidan los tramos.
    medidos, tramos, ecl_colectiva, exp_colectiva, sin_medir = {}, [], 0.0, 0.0, 0.0
    for s in SEGMENTOS:
        p = ParametrosECL(tasas_perdida=aplicadas[s], lgd=1.0,
                          ajuste_prospectivo=float(factores.get(s, 1.0)) - 1.0,
                          justificacion_ajuste=justificacion,
                          fuente_tasas="Permanencia a 24 meses sobre la cohorte del corte más antiguo")
        medidos[s] = medir_ecl(colectiva[s], p)
        for t in medidos[s]["tramos"]:
            tramos.append({**t, "segmento": s})
        ecl_colectiva += medidos[s]["ecl_total"]
        exp_colectiva += medidos[s]["exposicion_total"]
        sin_medir += medidos[s]["exposicion_sin_medir"]

    individual = evaluar_individual(lista_casos)
    exposicion_total = redondear(exp_colectiva + individual["saldo_total"])
    ecl_total = redondear(ecl_colectiva + individual["ecl_total"])
    resumen = {
        "colectivo": {"tramos": tramos, "exposicion_total": redondear(exp_colectiva),
                      "ecl_total": redondear(ecl_colectiva),
                      "exposicion_sin_medir": redondear(sin_medir),
                      "descuento_aplicado": False,
                      "ajuste_prospectivo": {s: factores.get(s, 1.0) for s in SEGMENTOS},
                      "justificacion_ajuste": justificacion,
                      "fuente_tasas": "Permanencia a 24 meses"},
        "individual": individual,
        "exposicion_total": exposicion_total,
        "ecl_total": ecl_total,
        "tributario": {
            "limite_ejercicio_1pct": redondear(exposicion_total * 0.01),
            "tope_acumulado_10pct": redondear(exposicion_total * 0.10),
            "excede_limite_ejercicio": ecl_total > exposicion_total * 0.01,
            "nota": "Límite de deducción (LORTI art. 10 num. 11). No condiciona la estimación "
                    "contable; la diferencia es temporaria.",
        },
    }
    if saldo_contable is not None:
        diferencia = redondear(exposicion_total - float(saldo_contable))
        resumen["conciliacion"] = {"cartera_medida": exposicion_total,
                                   "saldo_contable": redondear(float(saldo_contable)),
                                   "diferencia": diferencia, "cuadra": abs(diferencia) < 0.01}

    total_sin_estratificar = redondear(sum(sin_estratificar.values()))
    exposicion = {
        "colectiva": resumen["colectivo"]["exposicion_total"],
        "individual": resumen["individual"]["saldo_total"],
        "sin_estratificar": total_sin_estratificar,
        "total": redondear(resumen["exposicion_total"] + total_sin_estratificar),
        "segun_archivo": actual["total_saldo"],
        "factores_anclaje": factor,
    }

    politica = _comparar_politica(parametros.get("politica") or {}, bandas, colectiva,
                                 resumen["colectivo"]["tramos"])
    hallazgos = _hallazgos(resumen, politica, parametros, factor_prospectivo, justificacion)
    pendientes = _pendientes(resumen, parametros, coh, leidos)

    return {
        "exposicion": exposicion, "tasas": tasas, "detalle_cohorte": coh["detalle"],
        "trazabilidad": coh["trazabilidad"], "matriz": resumen["colectivo"],
        "individual": resumen["individual"], "conciliacion": resumen.get("conciliacion", {
            "cartera_medida": exposicion["total"], "saldo_contable": None,
            "diferencia": None, "cuadra": None}),
        "tributario": resumen["tributario"], "politica": politica,
        "ecl_total": resumen["ecl_total"], "hallazgos": hallazgos, "pendientes": pendientes,
        "bitacora": {
            "bandas": nombres, "umbral_incumplimiento": umbral_dias,
            "umbral_individual": umbral_ind,
            "cortes": [{"archivo": c["nombre"], "fecha": c["fecha"].isoformat(),
                        "hoja": l["hoja"], "fila_encabezado": l["fila_encabezado"],
                        "mapeo": l["mapeo"], "formato_fecha": l["formato_fecha"],
                        "documentos": len(l["filas"]), "duplicados_exactos": l["duplicados_exactos"],
                        "documentos_repetidos": l["documentos_repetidos"],
                        "descartados": len(l["descartados"]), "total": l["total_saldo"]}
                       for c, l in zip(cortes, leidos)],
            "metodo": "Permanencia a 24 meses", "descuento": "No aplicado (NIIF 9 B5.5.44)",
        },
    }


def _comparar_politica(politica, bandas, colectiva, tramos):
    filas, total = [], 0.0
    medidos = {t["tramo"]: t for t in tramos}
    for b in bandas:
        nombre = b["nombre"]
        tasa = float(politica.get(nombre, politica.get(b["origen"], 0)) or 0)
        exposicion = colectiva.get(nombre, 0.0)
        provision = redondear(exposicion * tasa)
        total += provision
        ecl = medidos.get(nombre, {}).get("ecl")
        filas.append({"banda": nombre, "banda_origen": b["origen"], "exposicion": redondear(exposicion),
                      "tasa_politica": tasa, "provision_politica": provision, "ecl": ecl,
                      "diferencia": None if ecl is None else redondear(ecl - provision)})
    bruta = sum(abs(f["diferencia"]) for f in filas if f["diferencia"] is not None)
    return {"filas": filas, "provision_politica_total": redondear(total),
            "diferencia_bruta": redondear(bruta)}


def _hallazgos(resumen, politica, parametros, factor, justificacion):
    h = []
    if factor == 1.0 or not justificacion.strip():
        h.append({"titulo": "Ausencia del componente prospectivo", "riesgo": "Alto",
                  "condicion": "La estimación no incorpora información sobre condiciones futuras: el factor aplicado es 1,000.",
                  "criterio": "NIIF 9 párr. 5.5.17(c).",
                  "causa": "No se ha desarrollado un procedimiento para incorporar información prospectiva.",
                  "efecto": "Incumplimiento de un requerimiento explícito de la norma.",
                  "recomendacion": "Documentar las variables prospectivas con fuente identificada y su traslación al factor."})
    sub = [f for f in politica["filas"] if f["tasa_politica"] == 0 and f["ecl"] and f["exposicion"] > 0
           and f["ecl"] / f["exposicion"] > 0.05]
    if sub:
        h.append({"titulo": "Política de deterioro no sustentada en el comportamiento observado",
                  "riesgo": "Alto",
                  "condicion": "Bandas sin provisionar pese a registrar pérdida observada: " +
                               ", ".join(f["banda"] for f in sub) + ".",
                  "criterio": "NIIF 9 párr. 5.5.15 y B5.5.35.",
                  "causa": "La política se definió sobre criterios de gestión y no sobre el comportamiento de pago.",
                  "efecto": f"Diferencia bruta de {politica['diferencia_bruta']:,.2f}.",
                  "recomendacion": "Reemplazar los porcentajes fijos por la matriz derivada del comportamiento observado."})
    if resumen["colectivo"].get("exposicion_sin_medir", 0) > 0.005:
        h.append({"titulo": "Cartera sin tasa histórica", "riesgo": "Alto",
                  "condicion": f"Quedan {resumen['colectivo']['exposicion_sin_medir']:,.2f} sin medir por falta de historia en su banda.",
                  "criterio": "NIIF 9 B5.5.35: la matriz se sustenta en la experiencia propia de la entidad.",
                  "causa": "La cohorte no tiene documentos en esas bandas.",
                  "efecto": "La pérdida esperada no cubre la totalidad de la cartera.",
                  "recomendacion": "Resolver por analogía con un segmento comparable, dejando constancia, o declarar la limitación."})
    return h


def _pendientes(resumen, parametros, coh, leidos):
    p = []
    if not parametros.get("materialidad"):
        p.append({"variable": "Materialidad de desempeño", "responsable": "Socio", "criticidad": "Alta",
                  "efecto": "Impide concluir sobre la significatividad del ajuste"})
    if not parametros.get("umbral_individual"):
        p.append({"variable": "Umbral de evaluación individual", "responsable": "Socio", "criticidad": "Alta",
                  "efecto": "Impide segregar de la matriz los saldos relevantes"})
    if not str(parametros.get("justificacion_prospectivo") or "").strip():
        p.append({"variable": "Información prospectiva documentada", "responsable": "Cliente",
                  "criticidad": "Alta", "efecto": "El factor permanece en 1,000"})
    if not parametros.get("mayor_provision"):
        p.append({"variable": "Mayores de la provisión de los tres ejercicios", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": "Sin ellos no se puede demostrar que los castigos fueron inmateriales, y el método de permanencia queda sin sustento"})
    if coh["trazabilidad"] < 0.8:
        p.append({"variable": "Trazabilidad por número de documento", "responsable": "Cliente",
                  "criticidad": "Alta",
                  "efecto": f"Solo el {coh['trazabilidad']:.1%} de la cohorte se localizó en el corte actual: el método de cohortes podría no ser aplicable"})
    for l in leidos:
        if l["formato_fecha"] in ("ambiguo", "inconsistente"):
            p.append({"variable": f"Formato de fecha de {l['hoja']}", "responsable": "Equipo",
                      "criticidad": "Alta", "efecto": "Toda la mora depende del orden día/mes"})
    return p
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `.venv\Scripts\python -m pytest tests/test_pce_service.py -v`
Expected: PASS, 5 pruebas.

- [ ] **Step 5: Correr toda la suite del paquete**

Run: `.venv\Scripts\python -m pytest tests/test_pce_*.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/aud/pce_cxc/service.py tests/test_pce_service.py
git commit -m "feat(aud): servicio que orquesta cohortes, anclaje, medicion y hallazgos"
```

---

### Task 7: Persistencia de la corrida

**Files:**
- Create: `backend/app/aud/pce_cxc/models.py`
- Modify: `backend/app/db/session.py` (crear la tabla en el arranque, junto a las demás)
- Test: `tests/test_pce_models.py`

**Interfaces:**
- Consumes: `Base` de `backend.app.db.base`, patrón de `backend/app/aud/obligaciones_fiscales/models.py`.
- Produces: `CorridaPCE` con columnas `id`, `project_id`, `user_id`, `entidad`, `fecha_corte`,
  `parametros` (JSON), `resultado` (JSON), `created_at`; y `guardar_corrida(db, **campos) -> CorridaPCE`.

- [ ] **Step 1: Leer el patrón existente**

Abrir `backend/app/aud/obligaciones_fiscales/models.py` y `backend/app/db/session.py`. Replicar la forma
en que se declara el modelo y cómo `init_db()` crea las tablas nuevas.

- [ ] **Step 2: Escribir la prueba que falla**

```python
# tests/test_pce_models.py
"""Persistencia de las corridas del papel de trabajo de pérdidas esperadas."""
from datetime import date

from backend.app.aud.pce_cxc.models import CorridaPCE, guardar_corrida
from backend.app.db.session import SessionLocal, init_db


def test_la_corrida_guarda_parametros_y_resultado():
    init_db()
    db = SessionLocal()
    try:
        c = guardar_corrida(db, project_id=None, user_id=None, entidad="PRUEBA S.A.",
                            fecha_corte=date(2025, 12, 31),
                            parametros={"umbral_individual": 100000},
                            resultado={"ecl_total": 1234.56})
        assert c.id is not None
        leida = db.get(CorridaPCE, c.id)
        assert leida.resultado["ecl_total"] == 1234.56
        assert leida.parametros["umbral_individual"] == 100000
        assert leida.created_at is not None
    finally:
        db.close()
```

- [ ] **Step 3: Correr la prueba y verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_pce_models.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.aud.pce_cxc.models'`

- [ ] **Step 4: Implementar el modelo**

```python
# backend/app/aud/pce_cxc/models.py
"""Corridas del papel de trabajo de pérdidas esperadas.

Se guardan los parámetros y el resultado completo: el papel de trabajo debe poder
reproducirse tal como se emitió, sin volver a cargar los archivos.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.app.db.base import Base


class CorridaPCE(Base):
    __tablename__ = "aud_pce_corridas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    entidad: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    fecha_corte: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    parametros: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resultado: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None))


def guardar_corrida(db: Session, **campos) -> CorridaPCE:
    corrida = CorridaPCE(**campos)
    db.add(corrida)
    db.commit()
    db.refresh(corrida)
    return corrida
```

- [ ] **Step 5: Registrar el modelo para que `init_db()` cree la tabla**

En `backend/app/db/session.py`, junto a los demás imports de modelos que hace `init_db`, agregar:

```python
    from backend.app.aud.pce_cxc import models as _pce_models  # noqa: F401
```

- [ ] **Step 6: Correr la prueba y verificar que pasa**

Run: `.venv\Scripts\python -m pytest tests/test_pce_models.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/aud/pce_cxc/models.py backend/app/db/session.py tests/test_pce_models.py
git commit -m "feat(aud): persistencia de las corridas de perdidas esperadas"
```

---

### Task 8: Endpoints HTTP

**Files:**
- Create: `backend/app/aud/pce_cxc/schemas.py`
- Create: `backend/app/aud/pce_cxc/router.py`
- Modify: `backend/app/api/__init__.py` (import en la línea 15 y `include_router` tras la línea 38)
- Test: `tests/test_pce_router.py`

**Interfaces:**
- Consumes: `analizar` (tarea 6), `guardar_corrida` (tarea 7), `require_staff` de
  `backend.app.auth.deps`, `get_db` del patrón de `backend/app/aud/obligaciones_fiscales/router.py`.
- Produces: `POST /api/v1/aud/pce-cxc/analizar` (multipart: `archivos` ×3 + campo `parametros` JSON) →
  `{"corrida_id": int, ...resultado}`; `GET /api/v1/aud/pce-cxc/corridas/{id}` → resultado guardado.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_pce_router.py
"""Endpoints de la herramienta de pérdidas esperadas (AUD, require_staff)."""
import io
import json
import uuid
from datetime import date

from openpyxl import Workbook

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db

BASE = "/api/v1/aud/pce-cxc"


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    ws.append(["Cliente", "Documento", "Tipo", "Emisión", "Vencimiento", "Saldo"])
    for f in filas:
        ws.append(list(f))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _archivos():
    c23 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 100000.0)])
    c24 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 20000.0)])
    c25 = _xlsx([("ALFA", "F-1", "NO-RELACIONADOS", date(2023, 9, 1), date(2023, 12, 1), 10000.0)])
    return [("archivos", ("2023.xlsx", c23)), ("archivos", ("2024.xlsx", c24)),
            ("archivos", ("2025.xlsx", c25))]


def _token(client, role=Role.staff):
    init_db()
    tag = uuid.uuid4().hex[:6]
    email, pw = f"pce-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r.json()["access_token"]


def test_sin_rol_staff_no_se_puede_calcular(client):
    token = _token(client, Role.user)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_calcula_y_guarda_la_corrida(client):
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos(),
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31", "2025-12-31"],
                                                    "entidad": "PRUEBA S.A."})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["corrida_id"]
    assert cuerpo["ecl_total"] >= 0
    g = client.get(f"{BASE}/corridas/{cuerpo['corrida_id']}", headers={"Authorization": f"Bearer {token}"})
    assert g.status_code == 200
    assert g.json()["resultado"]["ecl_total"] == cuerpo["ecl_total"]


def test_exige_los_tres_cortes(client):
    token = _token(client)
    r = client.post(f"{BASE}/analizar", files=_archivos()[:2],
                    data={"parametros": json.dumps({"fechas": ["2023-12-31", "2024-12-31"]})},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert "tres" in r.json()["detail"].lower()
```

> El `fixture` `client` ya existe en el repositorio (ver `tests/test_aud_of_router.py`); reutilizarlo tal cual.

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_pce_router.py -v`
Expected: FAIL con 404 en todos los casos (la ruta no existe).

- [ ] **Step 3: Implementar el router**

```python
# backend/app/aud/pce_cxc/router.py
"""Endpoints de la matriz de pérdidas crediticias esperadas (AUD, staff)."""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.aud.pce_cxc import service
from backend.app.aud.pce_cxc.models import CorridaPCE, guardar_corrida
from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.db.session import get_db

router = APIRouter(prefix="/aud/pce-cxc", tags=["aud-pce-cxc"])

MAX_BYTES_POR_ARCHIVO = 25 * 1024 * 1024


@router.post("/analizar")
async def analizar(archivos: list[UploadFile] = File(...),
                   parametros: str = Form("{}"),
                   db: Session = Depends(get_db),
                   user: User = Depends(require_staff)) -> dict:
    if len(archivos) != 3:
        raise HTTPException(400, "Se requieren los tres análisis de antigüedad (t-2, t-1 y el corte actual)")
    try:
        params = json.loads(parametros or "{}")
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Parámetros inválidos: {e}") from e

    fechas = params.get("fechas") or []
    if len(fechas) != 3:
        raise HTTPException(400, "Indique la fecha de corte de cada uno de los tres archivos")

    cortes = []
    for archivo, fecha in zip(archivos, fechas):
        contenido = await archivo.read()
        if len(contenido) > MAX_BYTES_POR_ARCHIVO:
            raise HTTPException(413, f"{archivo.filename}: supera el límite de 25 MB por archivo")
        cortes.append({"nombre": archivo.filename or "", "contenido": contenido,
                       "fecha": date.fromisoformat(fecha), "hoja": None, "mapeo": None})

    try:
        resultado = service.analizar(cortes, params)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    corrida = guardar_corrida(db, project_id=params.get("project_id"), user_id=user.id,
                              entidad=str(params.get("entidad") or ""),
                              fecha_corte=date.fromisoformat(fechas[2]),
                              parametros=params, resultado=resultado)
    return {"corrida_id": corrida.id, **resultado}


@router.get("/corridas/{corrida_id}")
def obtener(corrida_id: int, db: Session = Depends(get_db),
            _user: User = Depends(require_staff)) -> dict:
    corrida = db.get(CorridaPCE, corrida_id)
    if not corrida:
        raise HTTPException(404, "Corrida no encontrada")
    return {"corrida_id": corrida.id, "entidad": corrida.entidad,
            "fecha_corte": corrida.fecha_corte.isoformat() if corrida.fecha_corte else None,
            "parametros": corrida.parametros, "resultado": corrida.resultado,
            "created_at": corrida.created_at.isoformat()}
```

- [ ] **Step 4: Registrar el router**

En `backend/app/api/__init__.py`, agregar el import junto a los otros de `aud` (línea 15) y el
`include_router` después del de `aud_motor_balances_router` (línea 38):

```python
from backend.app.aud.pce_cxc import router as aud_pce_cxc_router
...
api_router.include_router(aud_pce_cxc_router.router)
```

- [ ] **Step 5: Correr la prueba y verificar que pasa**

Run: `.venv\Scripts\python -m pytest tests/test_pce_router.py -v`
Expected: PASS, 3 pruebas.

- [ ] **Step 6: Commit**

```bash
git add backend/app/aud/pce_cxc/router.py backend/app/aud/pce_cxc/schemas.py backend/app/api/__init__.py tests/test_pce_router.py
git commit -m "feat(aud): endpoints de la matriz de perdidas esperadas con rol staff"
```

---

### Task 9: Excel del papel de trabajo

**Files:**
- Create: `backend/app/aud/pce_cxc/exporter.py`
- Modify: `backend/app/aud/pce_cxc/router.py` (agregar el endpoint de descarga)
- Test: `tests/test_pce_exporter.py`

**Interfaces:**
- Consumes: el `resultado` de `analizar` (tarea 6) y la `CorridaPCE` (tarea 7).
- Produces: `construir_excel(resultado: dict, parametros: dict) -> bytes`;
  `GET /api/v1/aud/pce-cxc/corridas/{id}/excel` → archivo `.xlsx`.

**Hojas del libro:** `00-Caratula`, `01-Parametros`, `02-Fuentes`, `03-Cohorte`, `04-Tasas`,
`05-Matriz`, `06-Individual`, `07-Politica`, `08-Conciliacion`, `09-Tributario`, `10-Hallazgos`,
`11-Pendientes`, `12-Bitacora`.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_pce_exporter.py
"""Excel del papel de trabajo: hojas, fórmulas y cuadres."""
import io

from openpyxl import load_workbook

from backend.app.aud.pce_cxc.exporter import construir_excel

RESULTADO = {
    "exposicion": {"colectiva": 100000.0, "individual": 0.0, "sin_estratificar": 0.0,
                   "total": 100000.0, "segun_archivo": 100000.0,
                   "factores_anclaje": {"NO-RELACIONADOS": 1.0, "RELACIONADOS": 1.0}},
    "tasas": {"NO-RELACIONADOS": {"Por vencer": 0.01, "0 a 30 días": 0.05}},
    "detalle_cohorte": {"NO-RELACIONADOS": {"Por vencer": {"inicial": 50000.0, "remanente": 500.0, "documentos": 12}}},
    "trazabilidad": 0.99,
    "matriz": {"tramos": [{"tramo": "Por vencer", "exposicion": 80000.0, "tasa_perdida": 0.01,
                           "tasa_ajustada": 0.01, "lgd": 1.0, "horizonte": None,
                           "factor_descuento": 1.0, "ecl": 800.0},
                          {"tramo": "0 a 30 días", "exposicion": 20000.0, "tasa_perdida": 0.05,
                           "tasa_ajustada": 0.05, "lgd": 1.0, "horizonte": None,
                           "factor_descuento": 1.0, "ecl": 1000.0}],
               "exposicion_total": 100000.0, "ecl_total": 1800.0, "exposicion_sin_medir": 0.0,
               "descuento_aplicado": False, "ajuste_prospectivo": 0.0, "justificacion_ajuste": "",
               "fuente_tasas": "Permanencia a 24 meses"},
    "individual": {"casos": [], "saldo_total": 0.0, "ecl_total": 0.0},
    "conciliacion": {"cartera_medida": 100000.0, "saldo_contable": 100000.0, "diferencia": 0.0, "cuadra": True},
    "tributario": {"limite_ejercicio_1pct": 1000.0, "tope_acumulado_10pct": 10000.0,
                   "excede_limite_ejercicio": True, "nota": "Límite de deducción"},
    "politica": {"filas": [{"banda": "Por vencer", "banda_origen": "Por vencer", "exposicion": 80000.0,
                            "tasa_politica": 0.0, "provision_politica": 0.0, "ecl": 800.0, "diferencia": 800.0}],
                 "provision_politica_total": 0.0, "diferencia_bruta": 800.0},
    "ecl_total": 1800.0, "hallazgos": [], "pendientes": [],
    "bitacora": {"bandas": ["Por vencer", "0 a 30 días"], "umbral_incumplimiento": 730,
                 "umbral_individual": 0, "cortes": [], "metodo": "Permanencia a 24 meses",
                 "descuento": "No aplicado (NIIF 9 B5.5.44)"},
}


def _abrir(binario, con_formulas=True):
    return load_workbook(io.BytesIO(binario), data_only=not con_formulas)


def test_el_libro_trae_todas_las_hojas():
    wb = _abrir(construir_excel(RESULTADO, {"entidad": "PRUEBA S.A."}))
    assert wb.sheetnames == ["00-Caratula", "01-Parametros", "02-Fuentes", "03-Cohorte", "04-Tasas",
                             "05-Matriz", "06-Individual", "07-Politica", "08-Conciliacion",
                             "09-Tributario", "10-Hallazgos", "11-Pendientes", "12-Bitacora"]


def test_la_matriz_calcula_con_formulas_y_no_con_valores_pegados():
    ws = _abrir(construir_excel(RESULTADO, {}))["05-Matriz"]
    formulas = [c.value for fila in ws.iter_rows() for c in fila
                if isinstance(c.value, str) and c.value.startswith("=")]
    assert any("*" in f for f in formulas), "la pérdida de cada banda debe ser una fórmula"
    assert any(f.startswith("=SUM(") for f in formulas), "el total debe ser una suma"


def test_los_parametros_estan_en_celdas_con_nombre_y_las_formulas_los_usan():
    wb = _abrir(construir_excel(RESULTADO, {}))
    assert "AjusteProspectivo" in wb.defined_names
    ws = wb["05-Matriz"]
    assert any(isinstance(c.value, str) and "AjusteProspectivo" in c.value
               for fila in ws.iter_rows() for c in fila)


def test_el_libro_abre_sin_reparacion_y_recalcula_al_abrirse():
    wb = _abrir(construir_excel(RESULTADO, {}))
    assert wb.calculation.fullCalcOnLoad is True
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv\Scripts\python -m pytest tests/test_pce_exporter.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.aud.pce_cxc.exporter'`

- [ ] **Step 3: Implementar el exportador**

**Contenido exacto de cada hoja** (columnas en ese orden; "fórmula" significa que la celda es una
fórmula de Excel y no un número pegado):

| Hoja | Columnas | Fórmulas |
|---|---|---|
| `00-Caratula` | Concepto / Valor: entidad, RUC, fecha de corte, moneda, marco, referencia, preparado por, revisado por, fecha de emisión del papel | Ninguna. Incluye índice con hipervínculos a las demás hojas |
| `01-Parametros` | Parámetro / Valor / Fuente: materialidad, umbral individual, umbral de incumplimiento, factor prospectivo por segmento, justificación, cartera según EEFF por segmento | Ninguna. Nombres definidos `Materialidad`, `UmbralIndividual`, `AjusteProspectivo`, `SaldoContable` |
| `02-Fuentes` | Archivo / hoja / fila de encabezado / mapeo de columnas / formato de fecha / documentos / duplicados exactos / documentos repetidos / descartados / total | Total `=SUM(...)` |
| `03-Cohorte` | Segmento / Banda / Documentos / Exposición inicial / Remanente al corte / Resuelto | Resuelto `=D-E`; totales `=SUM(...)` |
| `04-Tasas` | Segmento / Banda / Tasa observada / Origen (observada o sustituida) / Justificación de la sustitución | Tasa observada `='03-Cohorte'!E/'03-Cohorte'!D` |
| `05-Matriz` | Segmento / Banda / Exposición / Tasa aplicada / Factor prospectivo / Pérdida esperada | Pérdida `=C*D*(1+AjusteProspectivo)`; total `=SUM(...)`; banda sin tasa muestra `SIN MEDIR` |
| `06-Individual` | Cliente / Segmento / Exposición / Recuperación estimada / Pérdida esperada / Sustento / Estado | Pérdida `=C-D`; totales `=SUM(...)` |
| `07-Politica` | Banda / Banda de origen / Exposición / Tasa de la política / Provisión política / PCE recálculo / Diferencia | Provisión `=C*D`; diferencia `=F-E`; totales `=SUM(...)` |
| `08-Conciliacion` | Concepto / Importe: cartera del archivo, cartera según EEFF, partida conciliatoria, cartera medida, estado | Partida `=C2-C3`; estado `=IF(ABS(...)<0.01,"CUADRA","DIFERENCIA")` |
| `09-Tributario` | Concepto / Importe: provisión contable, 1% del ejercicio, tope acumulado 10%, exceso no deducible | `=SaldoContable*0.01`, `=SaldoContable*0.1`, exceso `=MAX(0,PCE-límite)` |
| `10-Hallazgos` | # / Hallazgo / Riesgo / Condición / Criterio / Causa / Efecto / Recomendación | Ninguna |
| `11-Pendientes` | Variable / Efecto si no se obtiene / Criticidad / Responsable | Ninguna |
| `12-Bitacora` | Concepto / Detalle: método, descuento, bandas, umbrales, cortes, factores de anclaje, trazabilidad, transformaciones, versión y fecha de generación | Ninguna |

Seguir el formato ya definido en el `CLAUDE.md` del repositorio para los anexos (Calibri 9 en datos,
10 negrita en totales, 11 negrita en encabezados de bloque, bordes finos, doble en TOTAL, anchos
explícitos, numéricos a la derecha con `#,##0.00`). Reglas de fórmulas:

- Solo son valores fijos los datos de las hojas `02-Fuentes`, `03-Cohorte` y `01-Parametros`.
- La pérdida de cada banda es `=exposicion*tasa*(1+AjusteProspectivo)`, nunca un número pegado.
- Los totales son `=SUM(...)`; los cuadres son `=IF(ABS(diferencia)<0.01,"CUADRA","DIFERENCIA")`.
- Nombres definidos: `AjusteProspectivo`, `UmbralIndividual`, `Materialidad`, `SaldoContable`.
- Funciones permitidas: `SUM`, `SUMIFS`, `COUNTIFS`, `INDEX`, `MATCH`, `IF`, `ABS`, `ROUND`.
  Prohibidas: `INDIRECT`, `OFFSET`, matrices dinámicas, vínculos externos.
- Al final: `wb.calculation.fullCalcOnLoad = True`.

```python
# backend/app/aud/pce_cxc/exporter.py  (esqueleto de la hoja 05-Matriz; replicar el patrón en las demás)
from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

FORMATO_MONEDA = "#,##0.00"
FORMATO_PORCENTAJE = "0.00%"


def construir_excel(resultado: dict[str, Any], parametros: dict[str, Any]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    _caratula(wb, resultado, parametros)
    _parametros(wb, resultado, parametros)
    _fuentes(wb, resultado)
    _cohorte(wb, resultado)
    _tasas(wb, resultado)
    _matriz(wb, resultado)
    _individual(wb, resultado)
    _politica(wb, resultado)
    _conciliacion(wb, resultado)
    _tributario(wb, resultado)
    _hallazgos(wb, resultado)
    _pendientes(wb, resultado)
    _bitacora(wb, resultado)
    wb.calculation.fullCalcOnLoad = True
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _matriz(wb: Workbook, resultado: dict[str, Any]) -> None:
    ws = wb.create_sheet("05-Matriz")
    ws.append(["Segmento", "Banda", "Exposición", "Tasa aplicada", "Factor prospectivo",
               "Pérdida esperada"])
    primera = 2
    for i, t in enumerate(resultado["matriz"]["tramos"], start=primera):
        ws.cell(i, 1, t.get("segmento", ""))
        ws.cell(i, 2, t["tramo"])
        ws.cell(i, 3, t["exposicion"]).number_format = FORMATO_MONEDA
        if t["tasa_perdida"] is None:
            ws.cell(i, 4, "sin tasa")
            ws.cell(i, 6, "SIN MEDIR")
            continue
        ws.cell(i, 4, t["tasa_perdida"]).number_format = FORMATO_PORCENTAJE
        ws.cell(i, 5, "=AjusteProspectivo")
        ws.cell(i, 6, f"=C{i}*D{i}*(1+E{i})").number_format = FORMATO_MONEDA
    ultima = primera + len(resultado["matriz"]["tramos"]) - 1
    ws.cell(ultima + 1, 2, "TOTAL")
    ws.cell(ultima + 1, 3, f"=SUM(C{primera}:C{ultima})").number_format = FORMATO_MONEDA
    ws.cell(ultima + 1, 6, f"=SUM(F{primera}:F{ultima})").number_format = FORMATO_MONEDA
    for col, ancho in zip("ABCDEF", (20, 26, 18, 16, 18, 18)):
        ws.column_dimensions[col].width = ancho
    # `AjusteProspectivo` es un nombre definido en 01-Parametros: cambiar ese valor
    # en Excel recalcula toda la matriz, que es lo que hace auditable el papel.
    wb.defined_names.add(DefinedName("AjusteProspectivo", attr_text="'01-Parametros'!$B$5"))
```

- [ ] **Step 4: Agregar el endpoint de descarga en `router.py`**

```python
from fastapi.responses import StreamingResponse

from backend.app.aud.pce_cxc.exporter import construir_excel


@router.get("/corridas/{corrida_id}/excel")
def excel(corrida_id: int, db: Session = Depends(get_db),
          _user: User = Depends(require_staff)) -> StreamingResponse:
    corrida = db.get(CorridaPCE, corrida_id)
    if not corrida:
        raise HTTPException(404, "Corrida no encontrada")
    binario = construir_excel(corrida.resultado, corrida.parametros)
    nombre = f"PT-PCE-CXC_{(corrida.entidad or 'entidad').replace(' ', '_')}_{corrida.fecha_corte}.xlsx"
    return StreamingResponse(
        io.BytesIO(binario),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
```

- [ ] **Step 5: Correr las pruebas**

Run: `.venv\Scripts\python -m pytest tests/test_pce_exporter.py tests/test_pce_router.py -v`
Expected: PASS.

- [ ] **Step 6: Abrir el Excel generado y comprobar que no pide reparación**

```bash
.venv\Scripts\python -c "from tests.test_pce_exporter import RESULTADO; from backend.app.aud.pce_cxc.exporter import construir_excel; open('tmp_pt.xlsx','wb').write(construir_excel(RESULTADO, {'entidad':'PRUEBA'}))"
start tmp_pt.xlsx
```

Expected: Excel abre sin el cuadro de "reparación", la columna de pérdida muestra fórmulas y el total
cuadra con la suma de las bandas. Borrar `tmp_pt.xlsx` después.

- [ ] **Step 7: Commit**

```bash
git add backend/app/aud/pce_cxc/exporter.py backend/app/aud/pce_cxc/router.py tests/test_pce_exporter.py
git commit -m "feat(aud): excel del papel de trabajo con formulas auditables"
```

---

### Task 10: Frontend — catálogo y herramienta

**Files:**
- Modify: `frontend/src/aud/catalog.js` (categoría `CXC`, línea 22)
- Modify: `frontend/src/aud/ToolCatalog.jsx` (bloque nuevo junto a los existentes)
- Modify: `frontend/src/api.js` (funciones nuevas al final del bloque AUD)
- Create: `frontend/src/aud/PceCxcTool.jsx`
- Create: `frontend/src/aud/pceCxc.css`
- Test: `frontend/src/aud/pceCxc.test.js`

**Interfaces:**
- Consumes: `POST /aud/pce-cxc/analizar`, `GET /aud/pce-cxc/corridas/{id}/excel` (tareas 8 y 9).
- Produces: `pceCxcAnalizar(archivos, parametros)`, `pceCxcDescargarExcel(corridaId)` en `api.js`;
  componente `PceCxcTool` con prop `projectId`.

- [ ] **Step 1: Escribir la prueba que falla**

```javascript
// frontend/src/aud/pceCxc.test.js
import { describe, expect, it } from "vitest";
import { CATEGORIES } from "./catalog.js";

describe("catálogo AUD", () => {
  it("la tarjeta de Cuentas por cobrar ya no está vacía", () => {
    const cxc = CATEGORIES.find((c) => c.id === "CXC");
    expect(cxc.tools).toBeDefined();
    expect(cxc.tools[0].id).toBe("AUD.CXC.PCE");
  });

  it("conserva su identificador, etiqueta y tipo", () => {
    const cxc = CATEGORIES.find((c) => c.id === "CXC");
    expect(cxc.label).toBe("Cuentas por cobrar");
    expect(cxc.type).toBe("ciclo");
  });
});
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `cd frontend && npm test -- pceCxc`
Expected: FAIL — `cxc.tools` es `undefined`.

- [ ] **Step 3: Activar la tarjeta en `catalog.js`**

Reemplazar la línea `{ id: "CXC", label: "Cuentas por cobrar", type: "ciclo" },` por:

```javascript
  {
    id: "CXC",
    label: "Cuentas por cobrar",
    type: "ciclo",
    tools: [
      {
        id: "AUD.CXC.PCE",
        label: "Matriz de pérdidas crediticias esperadas · NIIF 9",
        description:
          "Sube los tres análisis de antigüedad y el movimiento de la provisión. Deriva las tasas del comportamiento observado de la cartera, ancla la exposición a los estados financieros, separa los saldos de evaluación individual y entrega el papel de trabajo en Excel con fórmulas auditables.",
      },
    ],
  },
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `cd frontend && npm test -- pceCxc`
Expected: PASS, 2 pruebas.

- [ ] **Step 5: Agregar las llamadas en `api.js`**

```javascript
// ---- AUD.CXC.PCE · matriz de pérdidas crediticias esperadas (staff) ----
export async function pceCxcAnalizar(archivos, parametros) {
  const fd = new FormData();
  (archivos || []).forEach((f) => fd.append("archivos", f));
  fd.append("parametros", JSON.stringify(parametros || {}));
  return parse(
    await apiFetch(
      `${API_BASE}/api/v1/aud/pce-cxc/analizar`,
      { method: "POST", body: fd, headers: authHeaders() },
      { timeoutMs: 300000 }
    )
  );
}

export async function pceCxcDescargarExcel(corridaId) {
  const resp = await apiFetch(
    `${API_BASE}/api/v1/aud/pce-cxc/corridas/${corridaId}/excel`,
    { headers: authHeaders() },
    { timeoutMs: 120000 }
  );
  if (!resp.ok) throw new Error(`No se pudo descargar el papel de trabajo (HTTP ${resp.status})`);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `PT-PCE-CXC-${corridaId}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
```

- [ ] **Step 6: Crear el componente `PceCxcTool.jsx`**

```jsx
import { useState } from "react";
import { pceCxcAnalizar, pceCxcDescargarExcel } from "../api.js";
import "./pceCxc.css";

const CORTES = [
  { k: "a1", t: "Corte más antiguo (t-2)" },
  { k: "a2", t: "Corte intermedio (t-1)" },
  { k: "a3", t: "Corte actual" },
];

const money = (v) =>
  v == null || isNaN(v) ? "—" : Number(v).toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (v) => (v == null || isNaN(v) ? "—" : `${(v * 100).toFixed(2)} %`);

export default function PceCxcTool({ projectId }) {
  const [archivos, setArchivos] = useState({});
  const [fechas, setFechas] = useState({ a1: "", a2: "", a3: "" });
  const [datos, setDatos] = useState({ entidad: "", materialidad: "", umbral_individual: "",
    eeff_nr: "", eeff_r: "", umbral_dias: 730 });
  const [estado, setEstado] = useState("");
  const [res, setRes] = useState(null);

  const listo = CORTES.every((c) => archivos[c.k] && fechas[c.k]);

  async function calcular() {
    setEstado("Procesando los tres cortes…");
    setRes(null);
    try {
      const salida = await pceCxcAnalizar(
        CORTES.map((c) => archivos[c.k]),
        {
          project_id: projectId ?? null,
          entidad: datos.entidad,
          fechas: CORTES.map((c) => fechas[c.k]),
          umbral_dias_incumplimiento: Number(datos.umbral_dias) || 730,
          umbral_individual: Number(datos.umbral_individual) || 0,
          materialidad: Number(datos.materialidad) || 0,
          eeff: { no_relacionados: Number(datos.eeff_nr) || 0, relacionados: Number(datos.eeff_r) || 0 },
        }
      );
      setRes(salida);
      setEstado("");
    } catch (e) {
      setEstado(`No se pudo calcular: ${e.message}`);
    }
  }

  return (
    <div className="pce">
      <h2>Matriz de pérdidas crediticias esperadas · NIIF 9</h2>
      <p className="pce-sub">
        Enfoque simplificado. Las tasas se derivan del comportamiento observado de la cartera; el sistema
        no asume ninguna. Lo que falte se reporta como pendiente.
      </p>

      <div className="pce-grid">
        {CORTES.map((c) => (
          <div key={c.k} className="pce-slot">
            <div className="pce-tag">{c.t}</div>
            <input type="file" accept=".xlsx,.xls,.csv"
              onChange={(e) => setArchivos({ ...archivos, [c.k]: e.target.files[0] })} />
            <label>Fecha de corte</label>
            <input type="date" value={fechas[c.k]}
              onChange={(e) => setFechas({ ...fechas, [c.k]: e.target.value })} />
          </div>
        ))}
      </div>

      <div className="pce-grid">
        <label>Entidad auditada
          <input value={datos.entidad} onChange={(e) => setDatos({ ...datos, entidad: e.target.value })} /></label>
        <label>Materialidad de desempeño
          <input type="number" value={datos.materialidad}
            onChange={(e) => setDatos({ ...datos, materialidad: e.target.value })} /></label>
        <label>Umbral de evaluación individual
          <input type="number" value={datos.umbral_individual}
            onChange={(e) => setDatos({ ...datos, umbral_individual: e.target.value })} /></label>
        <label>Cartera según EEFF · no relacionados
          <input type="number" value={datos.eeff_nr}
            onChange={(e) => setDatos({ ...datos, eeff_nr: e.target.value })} /></label>
        <label>Cartera según EEFF · relacionados
          <input type="number" value={datos.eeff_r}
            onChange={(e) => setDatos({ ...datos, eeff_r: e.target.value })} /></label>
        <label>Incumplimiento (días sin cobro)
          <input type="number" value={datos.umbral_dias}
            onChange={(e) => setDatos({ ...datos, umbral_dias: e.target.value })} /></label>
      </div>

      <button className="pce-btn" disabled={!listo || estado.startsWith("Procesando")} onClick={calcular}>
        Calcular la matriz
      </button>
      {estado && <div className="pce-msg">{estado}</div>}

      {res && (
        <div className="pce-res">
          <div className="pce-kpis">
            <div><span>Cartera medida</span><b>{money(res.exposicion.total)}</b></div>
            <div><span>Pérdida esperada</span><b>{money(res.ecl_total)}</b></div>
            <div><span>Cobertura</span><b>{pct(res.ecl_total / res.exposicion.total)}</b></div>
            <div><span>Trazabilidad</span><b>{pct(res.trazabilidad)}</b></div>
          </div>

          {res.matriz.exposicion_sin_medir > 0.005 && (
            <div className="pce-msg pce-bad">
              Quedan {money(res.matriz.exposicion_sin_medir)} sin medir por falta de tasa histórica en su banda.
              Una tasa cero por ausencia de historia no es evidencia de ausencia de pérdida.
            </div>
          )}

          <table className="pce-tabla">
            <thead><tr><th>Banda</th><th>Exposición</th><th>Tasa</th><th>Pérdida esperada</th></tr></thead>
            <tbody>
              {res.matriz.tramos.map((t) => (
                <tr key={t.tramo}>
                  <td>{t.tramo}</td><td>{money(t.exposicion)}</td>
                  <td>{t.tasa_perdida == null ? "sin medir" : pct(t.tasa_perdida)}</td>
                  <td>{t.ecl == null ? "—" : money(t.ecl)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {res.pendientes.length > 0 && (
            <div className="pce-msg pce-warn">
              <b>Pendientes que impiden concluir:</b>
              <ul>{res.pendientes.map((p, i) => <li key={i}>{p.variable} — {p.efecto} ({p.responsable})</li>)}</ul>
            </div>
          )}

          <button className="pce-btn" onClick={() => pceCxcDescargarExcel(res.corrida_id)}>
            Descargar el papel de trabajo
          </button>
          <div className="pce-nota">
            Papel de trabajo preliminar. Requiere revisión y aprobación del Socio responsable.
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 7: Crear `pceCxc.css` y enlazar el componente en `ToolCatalog.jsx`**

En `ToolCatalog.jsx`, importar el componente y agregar el bloque, con el mismo patrón que los existentes:

```jsx
import PceCxcTool from "./PceCxcTool.jsx";
...
  if (activeTool === "AUD.CXC.PCE") {
    return (
      <div className="aud-tool-wrap">
        <button className="link aud-back" onClick={() => setActiveTool(null)}>
          {STRINGS.back_to_catalog}
        </button>
        <PceCxcTool projectId={projectId} />
      </div>
    );
  }
```

`pceCxc.css`: copiar la estructura de `motorBalances.css` (mismas variables de color y espaciados) y
definir `.pce`, `.pce-sub`, `.pce-grid`, `.pce-slot`, `.pce-tag`, `.pce-btn`, `.pce-msg`, `.pce-bad`,
`.pce-warn`, `.pce-kpis`, `.pce-tabla`, `.pce-res`, `.pce-nota`.

- [ ] **Step 8: Compilar y correr las pruebas del frontend**

Run: `cd frontend && npm test -- pceCxc && npm run build`
Expected: PASS y build sin errores.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/aud/catalog.js frontend/src/aud/ToolCatalog.jsx frontend/src/aud/PceCxcTool.jsx frontend/src/aud/pceCxc.css frontend/src/api.js frontend/src/aud/pceCxc.test.js
git commit -m "feat(aud): activar la tarjeta de cuentas por cobrar con la matriz de perdidas esperadas"
```

---

### Task 11: Medición de volumen y límites

**Files:**
- Create: `scripts/bench_pce_cxc.py`
- Modify: `backend/app/aud/pce_cxc/router.py` (ajustar el límite si la medición lo exige)

**Interfaces:**
- Consumes: `leer_cartera` y `analizar`.
- Produces: `scripts/bench_pce_cxc.py` imprime filas leídas, segundos y memoria máxima por archivo.

- [ ] **Step 1: Escribir el script de medición**

```python
# scripts/bench_pce_cxc.py
"""Mide cuánto tarda y cuánta memoria usa la lectura de un análisis de antigüedad real.

Uso: .venv\\Scripts\\python scripts/bench_pce_cxc.py <archivo.xlsx> <AAAA-MM-DD>
"""
import sys
import time
import tracemalloc
from datetime import date

from backend.app.aud.pce_cxc.bandas import BANDAS_POR_DEFECTO, desdoblar
from backend.app.aud.pce_cxc.lectura import leer_cartera

ruta, corte = sys.argv[1], date.fromisoformat(sys.argv[2])
contenido = open(ruta, "rb").read()
bandas = desdoblar(BANDAS_POR_DEFECTO, 730)

tracemalloc.start()
inicio = time.perf_counter()
r = leer_cartera(contenido, ruta, corte, bandas)
segundos = time.perf_counter() - inicio
_actual, pico = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"archivo      : {ruta} ({len(contenido) / 1024 / 1024:.1f} MB)")
print(f"documentos   : {len(r['filas']):,}")
print(f"descartados  : {len(r['descartados']):,}")
print(f"saldo total  : {r['total_saldo']:,.2f}")
print(f"tiempo       : {segundos:.1f} s")
print(f"memoria pico : {pico / 1024 / 1024:.0f} MB")
```

- [ ] **Step 2: Medir con el archivo real más grande disponible**

Run: `.venv\Scripts\python scripts/bench_pce_cxc.py "<ruta del análisis de antigüedad real>" 2025-12-31`
Expected: imprime las seis líneas. Anotar los valores en el PR.

- [ ] **Step 3: Fijar el límite en función de lo medido**

- Si la lectura de un archivo real tarda **menos de 60 s** y el pico de memoria queda **bajo 250 MB**,
  dejar `MAX_BYTES_POR_ARCHIVO = 25 * 1024 * 1024` y documentar la medición.
- Si supera cualquiera de los dos umbrales, bajar el límite al tamaño medido que sí cumple y agregar en
  el mensaje de error: "el archivo excede lo que el servicio puede procesar en línea; divida el análisis
  por segmento o solicite el procesamiento por lotes". El procesamiento asíncrono queda fuera de este plan.

- [ ] **Step 4: Commit**

```bash
git add scripts/bench_pce_cxc.py backend/app/aud/pce_cxc/router.py
git commit -m "test(aud): medicion de volumen de la lectura de cartera y limite de tamano"
```

---

### Task 12: Verificación de extremo a extremo y pull request

- [ ] **Step 1: Correr toda la suite del backend**

Run: `.venv\Scripts\python -m pytest tests/ -q`
Expected: PASS. Pegar el resumen en el PR.

- [ ] **Step 2: Correr la suite y la compilación del frontend**

Run: `cd frontend && npm test -- --run && npm run build`
Expected: PASS y build sin errores.

- [ ] **Step 3: Prueba manual en la aplicación**

Levantar el entorno como se hace habitualmente en el repositorio, entrar con un usuario staff y
comprobar, con los tres cortes reales:

- [ ] La tarjeta "Cuentas por cobrar" ya no dice "Próximamente".
- [ ] Se suben los tres archivos con sus fechas y el cálculo responde.
- [ ] Las tasas mostradas coinciden con el cálculo manual sobre la cohorte (verificar al menos dos bandas
      a mano: remanente ÷ exposición inicial).
- [ ] La exposición total coincide con la cartera de los estados financieros y la conciliación muestra la
      partida conciliatoria.
- [ ] Una banda sin historia aparece como "sin medir" y el total advierte que no cubre toda la cartera.
- [ ] Los clientes por encima del umbral salen de la matriz y aparecen en evaluación individual.
- [ ] El Excel descarga, abre sin pedir reparación y sus fórmulas recalculan al cambiar el ajuste
      prospectivo en `01-Parametros`.
- [ ] Sin materialidad, la herramienta reporta el pendiente y no concluye.

- [ ] **Step 4: Abrir el pull request**

```bash
git push -u origin feat/aud-cxc-pce
gh pr create --title "feat(aud): matriz de perdidas crediticias esperadas en cuentas por cobrar" --body "<descripción>"
```

La descripción debe incluir: archivos nuevos y modificados, la medición de volumen de la tarea 11, la
salida real de `pytest` y de `npm run build`, el checklist del paso 3 con evidencia, las decisiones que
quedaron como parámetros (materialidad, umbral individual, factor prospectivo, tasas sustitutas) y la
advertencia de que el tratamiento tributario es independiente del contable.

**No fusionar el PR.** La fusión la decide una persona.

---

## Lo que este plan deja fuera a propósito

- **Procesamiento asíncrono** de archivos muy grandes. Se mide en la tarea 11 y, si hace falta, se
  planifica aparte.
- **Portal de clientes.** La herramienta es del auditor: los hallazgos de la matriz y las tasas de
  pérdida no se exponen al cliente auditado.
- **Retiro del libro Excel didáctico y de la aplicación HTML.** Conviven hasta que esta herramienta esté
  aprobada; después hay que decidir cuál es la oficial para no tener dos métodos circulando.
- **NIIF para las PYMES.** La Sección 11 usa pérdida incurrida por evidencia objetiva, no este modelo. Si
  el cliente reporta bajo ese marco, la herramienta no aplica y debe decirlo antes de calcular.
