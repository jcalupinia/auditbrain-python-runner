# Motor de Mayores Generales — Plan 1 de 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el motor que lee un Mayor General de impuestos en Excel y devuelve cada cuenta clasificada en su categoría fiscal, con su confianza y las señales que la justifican.

**Architecture:** Python puro, sin base de datos ni HTTP. Cuatro capas con contratos de dataclasses: `reader` (Excel → movimientos normalizados) → `cuentas` (movimientos → perfil por cuenta) → `senales` (perfil → puntajes por categoría) → `clasificador` (puntajes → categoría + confianza). El historial de homologaciones entra como un `dict` inyectado; su persistencia es el Plan 2.

**Tech Stack:** Python 3.12, openpyxl, pytest. Se reutiliza `_parse_amount_sri` de `cedulas/base.py` (regla de formatos numéricos del `CLAUDE.md`).

**Spec:** `docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md`

---

## Estructura de archivos

| Archivo | Responsabilidad única |
|---|---|
| `backend/app/aud/obligaciones_fiscales/mayor/__init__.py` | Marca el paquete |
| `backend/app/aud/obligaciones_fiscales/mayor/tipos.py` | Dataclasses del dominio: `Movimiento`, `LecturaMayor`, `PerfilCuenta`, `Senal`, `ResultadoClasificacion` |
| `backend/app/aud/obligaciones_fiscales/mayor/reader.py` | Excel/CSV → `LecturaMayor`. Autodetecta hoja, fila de encabezado y columnas |
| `backend/app/aud/obligaciones_fiscales/mayor/cuentas.py` | Movimientos → `PerfilCuenta` (mensualización, tendencia, prefijos, contrapartidas) |
| `backend/app/aud/obligaciones_fiscales/mayor/catalogo.py` | Catálogo semilla de categorías fiscales |
| `backend/app/aud/obligaciones_fiscales/mayor/senales.py` | Un extractor por señal |
| `backend/app/aud/obligaciones_fiscales/mayor/clasificador.py` | Combina señales → categoría + confianza + justificación |
| `tests/_mayor_fixtures.py` | Constructor de Excel sintéticos para los tests |
| `tests/test_of_mayor_reader.py` | Tests del reader |
| `tests/test_of_mayor_cuentas.py` | Tests de perfiles |
| `tests/test_of_mayor_senales.py` | Tests de cada señal |
| `tests/test_of_mayor_clasificador.py` | Tests del clasificador |
| `tests/test_of_mayor_real_medi.py` | Verificación empírica contra el mayor real del cliente |

**Datos reales de referencia** (no se commitean, el repo es público). Se leen de la carpeta apuntada por `AUD_OF_FIXTURES_DIR`; los tests hacen `skip` si no está.

| Categoría | Cuentas | Movimientos |
|---|---|---|
| IVA_COMPRAS | `1.1.5.1.1`, `1.1.5.1.3` | 550 |
| IVA_RETENIDO | `1.1.5.2.1` | 58 |
| RET_RENTA | `2.1.7.2.1/.3/.4/.5/.6/.7/.8/.9/.11` | 1.254 |
| RET_IVA | `2.1.7.3.1/.2/.3` | 236 |
| IVA_VENTAS | `2.1.7.4.1` | 155 |
| VENTAS | `4.1.1.x`, `4.1.2.x`, `4.1.4`, `4.1.11` | 2.427 |
| **Total** | **28 cuentas** | **4.680** |

---

### Task 1: Tipos del dominio y paquete

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/__init__.py`
- Create: `backend/app/aud/obligaciones_fiscales/mayor/tipos.py`
- Test: `tests/test_of_mayor_tipos.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Contratos del dominio del motor de mayores."""

from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    LecturaMayor,
    Movimiento,
    PerfilCuenta,
    Senal,
)


def test_movimiento_calcula_su_importe_neto():
    m = Movimiento(codigo="1.1.5.1.1", cuenta="IVA sobre Compras", debe=100.0, haber=25.0)
    assert m.neto == 75.0


def test_movimiento_expone_el_mes_de_su_fecha():
    import datetime

    m = Movimiento(codigo="1", cuenta="x", fecha=datetime.date(2025, 3, 17))
    assert m.mes == "03"


def test_movimiento_sin_fecha_no_tiene_mes():
    assert Movimiento(codigo="1", cuenta="x").mes is None


def test_lectura_sabe_si_pudo_mapear_las_columnas_minimas():
    completa = LecturaMayor(columnas_detectadas={"codigo": 0, "debe": 9, "haber": 10})
    incompleta = LecturaMayor(columnas_detectadas={"codigo": 0})
    assert completa.mapeo_suficiente is True
    assert incompleta.mapeo_suficiente is False


def test_perfil_reporta_su_tendencia_de_saldo():
    assert PerfilCuenta(codigo="1", nombre="x", debe=10.0, haber=2.0).tendencia == "deudor"
    assert PerfilCuenta(codigo="2", nombre="x", debe=2.0, haber=10.0).tendencia == "acreedor"
    assert PerfilCuenta(codigo="3", nombre="x", debe=5.0, haber=5.0).tendencia == "neutro"


def test_senal_es_comparable_por_puntaje():
    assert Senal("VENTAS", 40, "por nombre") > Senal("IVA_VENTAS", 15, "por código")
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_tipos.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.aud.obligaciones_fiscales.mayor'`

- [ ] **Step 3: Implementación mínima**

`backend/app/aud/obligaciones_fiscales/mayor/__init__.py`:

```python
"""Motor de clasificación del Mayor General de impuestos."""
```

`backend/app/aud/obligaciones_fiscales/mayor/tipos.py`:

```python
"""Contratos entre las capas del motor de mayores.

Deliberadamente sin dependencias de SQLAlchemy ni FastAPI: el motor se
prueba sin base de datos ni servidor.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

# Columnas mínimas para poder trabajar: sin código no hay cuenta, y sin
# debe/haber no hay importes.
COLUMNAS_MINIMAS = ("codigo", "debe", "haber")


@dataclass
class Movimiento:
    """Una fila del mayor, ya normalizada."""

    codigo: str
    cuenta: str = ""
    fecha: datetime.date | None = None
    asiento: str = ""
    documento: str = ""
    identificacion: str = ""
    persona: str = ""
    descripcion: str = ""
    debe: float = 0.0
    haber: float = 0.0
    saldo: float = 0.0
    fila: int = 0

    @property
    def neto(self) -> float:
        return round(self.debe - self.haber, 2)

    @property
    def mes(self) -> str | None:
        return f"{self.fecha.month:02d}" if self.fecha else None


@dataclass
class LecturaMayor:
    """Resultado de leer un archivo de mayor."""

    movimientos: list[Movimiento] = field(default_factory=list)
    columnas_detectadas: dict[str, int] = field(default_factory=dict)
    columnas_faltantes: list[str] = field(default_factory=list)
    hoja: str = ""
    fila_encabezado: int = 0
    filas_descartadas: int = 0
    errores: list[str] = field(default_factory=list)

    @property
    def mapeo_suficiente(self) -> bool:
        return all(c in self.columnas_detectadas for c in COLUMNAS_MINIMAS)


@dataclass
class PerfilCuenta:
    """Todo lo que sabemos de una cuenta a partir de sus movimientos."""

    codigo: str
    nombre: str
    n_movimientos: int = 0
    debe: float = 0.0
    haber: float = 0.0
    por_mes: dict[str, float] = field(default_factory=dict)
    prefijos_asiento: dict[str, int] = field(default_factory=dict)
    contrapartidas: list[tuple[str, int]] = field(default_factory=list)
    descripciones: list[str] = field(default_factory=list)

    @property
    def saldo(self) -> float:
        return round(self.debe - self.haber, 2)

    @property
    def tendencia(self) -> str:
        """deudor / acreedor / neutro.

        Las cuentas de impuestos se liquidan cada mes, así que muchas quedan
        en 'neutro' (debe == haber). En ese caso la señal no debe opinar.
        """
        if round(self.debe, 2) > round(self.haber, 2):
            return "deudor"
        if round(self.haber, 2) > round(self.debe, 2):
            return "acreedor"
        return "neutro"


@dataclass(order=True)
class Senal:
    """Aporte de una señal a una categoría, con su justificación."""

    categoria: str = field(compare=False)
    puntaje: int = 0
    motivo: str = field(default="", compare=False)


@dataclass
class ResultadoClasificacion:
    codigo: str
    nombre: str
    categoria: str | None
    confianza: str  # alta | media | baja
    origen: str  # historial | reglas | declarada | manual
    tarifa: float | None = None
    puntajes: dict[str, int] = field(default_factory=dict)
    senales: list[Senal] = field(default_factory=list)

    @property
    def justificacion(self) -> list[str]:
        return [s.motivo for s in self.senales]
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_tipos.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/ tests/test_of_mayor_tipos.py
git commit -m "feat(mayor): contratos del dominio del motor de mayores"
```

---

### Task 2: Constructor de Excel sintéticos para los tests

**Files:**
- Create: `tests/_mayor_fixtures.py`
- Test: `tests/test_of_mayor_reader.py` (se crea aquí, se completa en la Task 3)

- [ ] **Step 1: Escribir el test que falla**

```python
"""El constructor de fixtures debe producir un xlsx legible por openpyxl."""

from io import BytesIO

from openpyxl import load_workbook

from tests._mayor_fixtures import ENCABEZADO_REAL, mayor_xlsx


def test_construye_un_xlsx_con_el_encabezado_en_la_fila_indicada():
    data = mayor_xlsx(
        [["1.1.5.1.1", "IVA sobre Compras", None, "COM 1", "", "", "", "", "", 10, 0, 10]],
        fila_encabezado=3,
    )
    ws = load_workbook(BytesIO(data)).active
    assert [c.value for c in ws[3]] == list(ENCABEZADO_REAL)
    assert ws.cell(4, 1).value == "1.1.5.1.1"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_reader.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests._mayor_fixtures'`

- [ ] **Step 3: Implementación mínima**

`tests/_mayor_fixtures.py`:

```python
"""Constructores de mayores sintéticos para los tests del motor.

Los importes son inventados: NUNCA se commitean cifras de clientes a este
repositorio público.
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

# Encabezado exacto del ERP del cliente de referencia.
ENCABEZADO_REAL = (
    "Código", "Cuenta", "Fecha", "Asiento", "Documento", "Identificación",
    "Persona", "Persona Cruce Cuenta", "Descripción", "Debe", "Haber", "Saldo",
)


def mayor_xlsx(
    filas: list[list],
    *,
    encabezado: tuple[str, ...] = ENCABEZADO_REAL,
    fila_encabezado: int = 1,
    hoja: str = "Hoja1",
    hojas_previas: tuple[str, ...] = (),
) -> bytes:
    """Devuelve los bytes de un .xlsx con el encabezado y las filas dadas."""
    wb = Workbook()
    ws_primera = wb.active
    for i, nombre in enumerate(hojas_previas):
        (ws_primera if i == 0 else wb.create_sheet()).title = nombre
    ws = ws_primera if not hojas_previas else wb.create_sheet()
    ws.title = hoja

    for col, valor in enumerate(encabezado, start=1):
        ws.cell(fila_encabezado, col, valor)
    for j, fila in enumerate(filas, start=fila_encabezado + 1):
        for col, valor in enumerate(fila, start=1):
            ws.cell(j, col, valor)

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_reader.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/_mayor_fixtures.py tests/test_of_mayor_reader.py
git commit -m "test(mayor): constructor de mayores sinteticos"
```

---

### Task 3: Reader — detección de encabezado y columnas

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/reader.py`
- Modify: `tests/test_of_mayor_reader.py`

- [ ] **Step 1: Escribir el test que falla**

Añadir a `tests/test_of_mayor_reader.py`:

```python
from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor

FILA = ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 202501000004",
        "FAC 006-001-000466564", "1791274156001", "ASERLACO S.A.", "",
        "F .466564 ALMUERZO", 2.39, None, 2.39]


def test_detecta_las_doce_columnas_del_erp_real():
    lectura = leer_mayor(mayor_xlsx([FILA]))
    assert lectura.mapeo_suficiente
    assert lectura.columnas_detectadas["codigo"] == 0
    assert lectura.columnas_detectadas["cuenta"] == 1
    assert lectura.columnas_detectadas["debe"] == 9
    assert lectura.columnas_detectadas["haber"] == 10
    assert lectura.columnas_detectadas["saldo"] == 11


def test_no_confunde_persona_cruce_cuenta_con_la_columna_cuenta():
    """La columna 8 se llama 'Persona Cruce Cuenta' y contiene 'cuenta'."""
    lectura = leer_mayor(mayor_xlsx([FILA]))
    assert lectura.columnas_detectadas["cuenta"] == 1


def test_encuentra_el_encabezado_aunque_no_este_en_la_primera_fila():
    lectura = leer_mayor(mayor_xlsx([FILA], fila_encabezado=6))
    assert lectura.fila_encabezado == 6
    assert len(lectura.movimientos) == 1


def test_reporta_las_columnas_que_no_pudo_mapear():
    lectura = leer_mayor(
        mayor_xlsx([["1.1.5.1.1", 10]], encabezado=("Cta", "Valor"))
    )
    assert lectura.mapeo_suficiente is False
    assert "debe" in lectura.columnas_faltantes


def test_elige_la_hoja_con_mas_columnas_reconocidas():
    data = mayor_xlsx([FILA], hoja="MAYOR", hojas_previas=("Portada",))
    lectura = leer_mayor(data)
    assert lectura.hoja == "MAYOR"


def test_acepta_sinonimos_de_otros_erp():
    lectura = leer_mayor(
        mayor_xlsx(
            [["1.1.5.1.1", "IVA", "2025-01-05", "A1", 10, 0]],
            encabezado=("Cuenta Contable", "Nombre", "Fecha", "Comprobante",
                        "Débito", "Crédito"),
        )
    )
    assert lectura.mapeo_suficiente
    assert lectura.columnas_detectadas["codigo"] == 0
    assert lectura.columnas_detectadas["cuenta"] == 1
    assert lectura.columnas_detectadas["debe"] == 4
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_reader.py -q`
Expected: FAIL — `ImportError: cannot import name 'leer_mayor'`

- [ ] **Step 3: Implementación mínima**

`backend/app/aud/obligaciones_fiscales/mayor/reader.py`:

```python
"""Lectura de un Mayor General en Excel, agnóstica del ERP de origen.

El formato varía por cliente, así que el encabezado y las columnas se
autodetectan por sinónimos. Si no se logra el mapeo mínimo, el resultado lo
reporta en lugar de fallar: el auditor mapea las columnas a mano.
"""

from __future__ import annotations

import datetime
import unicodedata
from io import BytesIO

from openpyxl import load_workbook

from backend.app.aud.obligaciones_fiscales.cedulas.base import _parse_amount_sri
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    COLUMNAS_MINIMAS,
    LecturaMayor,
    Movimiento,
)

# Sinónimos por campo. Se compara por igualdad exacta sobre el encabezado
# normalizado; el "contiene" sólo se usa como respaldo y NUNCA para 'cuenta'
# (porque 'Persona Cruce Cuenta' lo capturaría por error).
SINONIMOS: dict[str, tuple[str, ...]] = {
    "codigo": ("codigo", "cod", "cod cuenta", "codigo cuenta", "cuenta contable",
               "nro cuenta", "numero de cuenta", "cta"),
    "cuenta": ("cuenta", "nombre", "nombre cuenta", "nombre de cuenta",
               "descripcion cuenta", "detalle cuenta"),
    "fecha": ("fecha", "fecha asiento", "fecha movimiento", "f asiento"),
    "asiento": ("asiento", "comprobante", "nro asiento", "numero asiento",
                "no asiento", "diario", "nro comprobante"),
    "documento": ("documento", "doc", "nro documento", "comprobante venta",
                  "factura"),
    "identificacion": ("identificacion", "ruc", "cedula", "ruc cedula", "nit",
                       "identificacion tercero"),
    "persona": ("persona", "razon social", "tercero", "proveedor", "cliente",
                "beneficiario", "nombre tercero"),
    "descripcion": ("descripcion", "glosa", "detalle", "concepto",
                    "observacion", "observaciones"),
    "debe": ("debe", "debito", "cargo", "debitos"),
    "haber": ("haber", "credito", "abono", "creditos"),
    "saldo": ("saldo", "saldo final", "saldo acumulado"),
}

# Campos donde el respaldo por "contiene" sería peligroso.
SOLO_EXACTO = frozenset({"cuenta", "saldo"})

MAX_FILAS_BUSQUEDA_ENCABEZADO = 30


def _norm(valor) -> str:
    """minúsculas, sin tildes, sin puntuación, espacios colapsados."""
    if valor is None:
        return ""
    s = unicodedata.normalize("NFKD", str(valor))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c if c.isalnum() else " " for c in s.lower())
    return " ".join(s.split())


def _mapear_encabezado(celdas: list) -> dict[str, int]:
    """Devuelve {campo: índice de columna} para una fila candidata."""
    normalizadas = [_norm(c) for c in celdas]
    mapeo: dict[str, int] = {}
    usadas: set[int] = set()

    for campo, opciones in SINONIMOS.items():
        for i, texto in enumerate(normalizadas):
            if i in usadas or not texto:
                continue
            if texto in opciones:
                mapeo[campo] = i
                usadas.add(i)
                break

    for campo, opciones in SINONIMOS.items():
        if campo in mapeo or campo in SOLO_EXACTO:
            continue
        for i, texto in enumerate(normalizadas):
            if i in usadas or not texto:
                continue
            if any(texto.startswith(o) for o in opciones):
                mapeo[campo] = i
                usadas.add(i)
                break
    return mapeo


def _fecha(valor) -> datetime.date | None:
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    if valor is None:
        return None
    texto = str(valor).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _importe(valor) -> float:
    if isinstance(valor, (int, float)):
        return float(valor)
    parsed = _parse_amount_sri(_texto(valor))
    return parsed if parsed is not None else 0.0


def leer_mayor(contenido: bytes) -> LecturaMayor:
    """Lee un mayor en .xlsx/.xlsm y devuelve sus movimientos normalizados."""
    try:
        wb = load_workbook(BytesIO(contenido), data_only=True, read_only=True)
    except Exception as e:  # noqa: BLE001
        return LecturaMayor(errores=[f"No se pudo abrir el Excel: {e}"])

    mejor = None  # (n_campos, hoja, fila, mapeo)
    for nombre in wb.sheetnames:
        ws = wb[nombre]
        for fila_idx, fila in enumerate(
            ws.iter_rows(max_row=MAX_FILAS_BUSQUEDA_ENCABEZADO, values_only=True),
            start=1,
        ):
            mapeo = _mapear_encabezado(list(fila))
            puntaje = len(mapeo)
            if mejor is None or puntaje > mejor[0]:
                mejor = (puntaje, nombre, fila_idx, mapeo)

    if mejor is None or mejor[0] == 0:
        wb.close()
        return LecturaMayor(
            errores=["No se detectó una fila de encabezado reconocible."],
            columnas_faltantes=list(COLUMNAS_MINIMAS),
        )

    _, hoja, fila_encabezado, mapeo = mejor
    lectura = LecturaMayor(
        columnas_detectadas=mapeo,
        columnas_faltantes=[c for c in COLUMNAS_MINIMAS if c not in mapeo],
        hoja=hoja,
        fila_encabezado=fila_encabezado,
    )
    if not lectura.mapeo_suficiente:
        wb.close()
        return lectura

    ws = wb[hoja]
    col = mapeo

    def celda(fila, campo):
        i = col.get(campo)
        return fila[i] if i is not None and i < len(fila) else None

    for n, fila in enumerate(
        ws.iter_rows(min_row=fila_encabezado + 1, values_only=True),
        start=fila_encabezado + 1,
    ):
        codigo = _texto(celda(fila, "codigo"))
        if not codigo:
            lectura.filas_descartadas += 1
            continue
        lectura.movimientos.append(
            Movimiento(
                codigo=codigo,
                cuenta=_texto(celda(fila, "cuenta")),
                fecha=_fecha(celda(fila, "fecha")),
                asiento=_texto(celda(fila, "asiento")),
                documento=_texto(celda(fila, "documento")),
                identificacion=_texto(celda(fila, "identificacion")),
                persona=_texto(celda(fila, "persona")),
                descripcion=_texto(celda(fila, "descripcion")),
                debe=_importe(celda(fila, "debe")),
                haber=_importe(celda(fila, "haber")),
                saldo=_importe(celda(fila, "saldo")),
                fila=n,
            )
        )
    wb.close()
    return lectura
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_reader.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/reader.py tests/test_of_mayor_reader.py
git commit -m "feat(mayor): reader con autodeteccion de encabezado y columnas"
```

---

### Task 4: Reader — formatos numéricos y filas basura

**Files:**
- Modify: `tests/test_of_mayor_reader.py`
- Modify: `backend/app/aud/obligaciones_fiscales/mayor/reader.py`

- [ ] **Step 1: Escribir el test que falla**

Añadir a `tests/test_of_mayor_reader.py`:

```python
import pytest


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("178.259,63", 178259.63),   # europeo
        ("178,259.63", 178259.63),   # US
        ("183724.10", 183724.10),    # plano
        ("-150,00", -150.0),         # negativo con coma decimal
        ("0,00", 0.0),
    ],
)
def test_importes_en_cualquier_formato_regional(texto, esperado):
    lectura = leer_mayor(
        mayor_xlsx([["1.1.5.1.1", "IVA", "2025-01-05", "A1", "", "", "", "",
                     "", texto, None, texto]])
    )
    assert lectura.movimientos[0].debe == esperado


def test_descarta_filas_de_total_sin_codigo_de_cuenta():
    filas = [
        ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 1", "", "", "",
         "", "", 10, 0, 10],
        [None, "TOTAL GENERAL", None, None, None, None, None, None, None,
         999, 0, 999],
    ]
    lectura = leer_mayor(mayor_xlsx(filas))
    assert len(lectura.movimientos) == 1
    assert lectura.filas_descartadas == 1


def test_descarta_un_encabezado_repetido_a_mitad_del_listado():
    filas = [
        ["1.1.5.1.1", "IVA sobre Compras", "2025-01-05", "COM 1", "", "", "",
         "", "", 10, 0, 10],
        list(ENCABEZADO_REAL),
        ["1.1.5.1.3", "IVA en Importaciones", "2025-01-06", "COM 2", "", "",
         "", "", "", 20, 0, 20],
    ]
    lectura = leer_mayor(mayor_xlsx(filas))
    assert [m.codigo for m in lectura.movimientos] == ["1.1.5.1.1", "1.1.5.1.3"]


def test_celda_vacia_de_haber_cuenta_como_cero():
    lectura = leer_mayor(
        mayor_xlsx([["1.1.5.1.1", "IVA", "2025-01-05", "A1", "", "", "", "",
                     "", 2.39, None, 2.39]])
    )
    assert lectura.movimientos[0].haber == 0.0
    assert lectura.movimientos[0].neto == 2.39
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_reader.py -q`
Expected: FAIL en `test_descarta_un_encabezado_repetido_a_mitad_del_listado` — el encabezado repetido entra como movimiento con `codigo="Código"`.

- [ ] **Step 3: Implementación mínima**

En `reader.py`, dentro del bucle de filas, después de obtener `codigo`, añadir el descarte del encabezado repetido:

```python
        codigo = _texto(celda(fila, "codigo"))
        if not codigo:
            lectura.filas_descartadas += 1
            continue
        if _norm(codigo) in SINONIMOS["codigo"]:
            # Encabezado repetido a mitad del listado (paginación del ERP).
            lectura.filas_descartadas += 1
            continue
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_reader.py -q`
Expected: `15 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/reader.py tests/test_of_mayor_reader.py
git commit -m "feat(mayor): formatos numericos regionales y descarte de filas basura"
```

---

### Task 5: Perfiles de cuenta

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/cuentas.py`
- Test: `tests/test_of_mayor_cuentas.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Agregación de movimientos en perfiles por cuenta."""

import datetime

from backend.app.aud.obligaciones_fiscales.mayor.cuentas import perfilar
from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento


def _mov(codigo, cuenta, mes, debe=0.0, haber=0.0, asiento="COM 1"):
    return Movimiento(
        codigo=codigo, cuenta=cuenta, fecha=datetime.date(2025, mes, 15),
        asiento=asiento, debe=debe, haber=haber,
    )


def test_agrupa_por_codigo_y_suma_debe_y_haber():
    perfiles = perfilar([
        _mov("1.1.5.1.1", "IVA sobre Compras", 1, debe=10.0),
        _mov("1.1.5.1.1", "IVA sobre Compras", 2, debe=5.0),
        _mov("1.1.5.1.1", "IVA sobre Compras", 2, haber=15.0),
    ])
    p = perfiles["1.1.5.1.1"]
    assert p.n_movimientos == 3
    assert p.debe == 15.0
    assert p.haber == 15.0
    assert p.tendencia == "neutro"


def test_mensualiza_el_neto_por_mes():
    perfiles = perfilar([
        _mov("4.1.1.4", "Venta insumos", 1, haber=100.0),
        _mov("4.1.1.4", "Venta insumos", 1, haber=50.0),
        _mov("4.1.1.4", "Venta insumos", 3, haber=20.0),
    ])
    p = perfiles["4.1.1.4"]
    assert p.por_mes["01"] == -150.0
    assert p.por_mes["03"] == -20.0
    assert "02" not in p.por_mes


def test_cuenta_los_prefijos_de_asiento():
    perfiles = perfilar([
        _mov("4.1.1.4", "Venta", 1, asiento="VTA 202501000001"),
        _mov("4.1.1.4", "Venta", 1, asiento="VTA 202501000002"),
        _mov("4.1.1.4", "Venta", 2, asiento="ASI 202502000001"),
    ])
    assert perfiles["4.1.1.4"].prefijos_asiento == {"VTA": 2, "ASI": 1}


def test_conserva_el_nombre_de_la_cuenta():
    perfiles = perfilar([_mov("2.1.7.4.1", "IVA sobre Ventas", 1, haber=9.0)])
    assert perfiles["2.1.7.4.1"].nombre == "IVA sobre Ventas"


def test_movimiento_sin_fecha_no_rompe_la_mensualizacion():
    perfiles = perfilar([Movimiento(codigo="1", cuenta="x", debe=5.0)])
    assert perfiles["1"].por_mes == {}
    assert perfiles["1"].n_movimientos == 1
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_cuentas.py -q`
Expected: FAIL — `ImportError: cannot import name 'perfilar'`

- [ ] **Step 3: Implementación mínima**

`backend/app/aud/obligaciones_fiscales/mayor/cuentas.py`:

```python
"""Movimientos → perfil por cuenta."""

from __future__ import annotations

from collections import Counter, defaultdict

from backend.app.aud.obligaciones_fiscales.mayor.tipos import Movimiento, PerfilCuenta

MAX_DESCRIPCIONES = 20


def _prefijo(asiento: str) -> str:
    partes = asiento.split()
    return partes[0].upper() if partes else ""


def perfilar(movimientos: list[Movimiento]) -> dict[str, PerfilCuenta]:
    """Agrupa los movimientos por código de cuenta."""
    perfiles: dict[str, PerfilCuenta] = {}
    prefijos: dict[str, Counter] = defaultdict(Counter)

    for m in movimientos:
        p = perfiles.get(m.codigo)
        if p is None:
            p = PerfilCuenta(codigo=m.codigo, nombre=m.cuenta)
            perfiles[m.codigo] = p
        if not p.nombre and m.cuenta:
            p.nombre = m.cuenta
        p.n_movimientos += 1
        p.debe = round(p.debe + m.debe, 2)
        p.haber = round(p.haber + m.haber, 2)
        if m.mes:
            p.por_mes[m.mes] = round(p.por_mes.get(m.mes, 0.0) + m.neto, 2)
        pref = _prefijo(m.asiento)
        if pref:
            prefijos[m.codigo][pref] += 1
        if m.descripcion and len(p.descripciones) < MAX_DESCRIPCIONES:
            p.descripciones.append(m.descripcion)

    for codigo, contador in prefijos.items():
        perfiles[codigo].prefijos_asiento = dict(contador)
    return perfiles
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_cuentas.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/cuentas.py tests/test_of_mayor_cuentas.py
git commit -m "feat(mayor): perfiles por cuenta con mensualizacion y prefijos de asiento"
```

---

### Task 6: Contrapartidas por número de asiento

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/mayor/cuentas.py`
- Modify: `tests/test_of_mayor_cuentas.py`

- [ ] **Step 1: Escribir el test que falla**

Añadir a `tests/test_of_mayor_cuentas.py`:

```python
def test_detecta_las_contrapartidas_del_mismo_asiento():
    movs = [
        _mov("4.1.1.4", "Venta", 1, haber=100.0, asiento="VTA 1"),
        _mov("2.1.7.4.1", "IVA Ventas", 1, haber=15.0, asiento="VTA 1"),
        _mov("1.1.2.1", "Clientes", 1, debe=115.0, asiento="VTA 1"),
        _mov("4.1.1.4", "Venta", 2, haber=200.0, asiento="VTA 2"),
        _mov("1.1.2.1", "Clientes", 2, debe=200.0, asiento="VTA 2"),
    ]
    perfiles = perfilar(movs)
    assert perfiles["4.1.1.4"].contrapartidas[0] == ("1.1.2.1", 2)
    assert ("2.1.7.4.1", 1) in perfiles["4.1.1.4"].contrapartidas


def test_una_cuenta_no_es_contrapartida_de_si_misma():
    movs = [
        _mov("4.1.1.4", "Venta", 1, haber=100.0, asiento="VTA 1"),
        _mov("4.1.1.4", "Venta", 1, debe=10.0, asiento="VTA 1"),
    ]
    assert perfilar(movs)["4.1.1.4"].contrapartidas == []


def test_mayor_filtrado_sin_asientos_compartidos_no_produce_contrapartidas():
    """Caso real: el mayor viene filtrado a cuentas de impuestos."""
    movs = [
        _mov("1.1.5.1.1", "IVA Compras", 1, debe=2.39, asiento="COM 1"),
        _mov("1.1.5.1.1", "IVA Compras", 1, debe=12.0, asiento="COM 2"),
    ]
    assert perfilar(movs)["1.1.5.1.1"].contrapartidas == []
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_cuentas.py -q`
Expected: FAIL — `assert [] ... IndexError: list index out of range` en el primer test

- [ ] **Step 3: Implementación mínima**

En `cuentas.py`, añadir la constante, la función auxiliar y la llamada al final de `perfilar`:

```python
MAX_CONTRAPARTIDAS = 5


def _contrapartidas(movimientos: list[Movimiento]) -> dict[str, list[tuple[str, int]]]:
    """Cuentas que aparecen en el mismo número de asiento.

    Con un mayor filtrado a cuentas de impuestos casi no hay asientos
    compartidos: la señal simplemente no aporta, no penaliza.
    """
    por_asiento: dict[str, set[str]] = defaultdict(set)
    for m in movimientos:
        if m.asiento:
            por_asiento[m.asiento].add(m.codigo)

    conteo: dict[str, Counter] = defaultdict(Counter)
    for cuentas in por_asiento.values():
        if len(cuentas) < 2:
            continue
        for codigo in cuentas:
            for otra in cuentas:
                if otra != codigo:
                    conteo[codigo][otra] += 1

    return {
        codigo: c.most_common(MAX_CONTRAPARTIDAS) for codigo, c in conteo.items()
    }
```

Y antes del `return perfiles`:

```python
    for codigo, pares in _contrapartidas(movimientos).items():
        if codigo in perfiles:
            perfiles[codigo].contrapartidas = pares
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_cuentas.py -q`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/cuentas.py tests/test_of_mayor_cuentas.py
git commit -m "feat(mayor): contrapartidas derivadas del numero de asiento"
```

---

### Task 7: Catálogo semilla de categorías

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/catalogo.py`
- Test: `tests/test_of_mayor_catalogo.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Catálogo semilla de categorías fiscales."""

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import (
    CATEGORIAS,
    naturaleza_por_codigo,
)


def test_estan_las_siete_categorias_del_modelo_del_auditor():
    assert set(CATEGORIAS) == {
        "IVA_COMPRAS", "IVA_VENTAS", "IVA_RETENIDO",
        "RET_RENTA", "RET_IVA", "VENTAS", "IVA_DIFERIDO",
    }


def test_cada_categoria_declara_su_naturaleza_esperada():
    assert CATEGORIAS["IVA_COMPRAS"].naturaleza_esperada == "activo"
    assert CATEGORIAS["IVA_RETENIDO"].naturaleza_esperada == "activo"
    assert CATEGORIAS["IVA_VENTAS"].naturaleza_esperada == "pasivo"
    assert CATEGORIAS["RET_RENTA"].naturaleza_esperada == "pasivo"
    assert CATEGORIAS["RET_IVA"].naturaleza_esperada == "pasivo"
    assert CATEGORIAS["IVA_DIFERIDO"].naturaleza_esperada == "pasivo"
    assert CATEGORIAS["VENTAS"].naturaleza_esperada == "ingreso"


def test_deriva_la_naturaleza_del_primer_digito_del_codigo():
    assert naturaleza_por_codigo("1.1.5.1.1") == "activo"
    assert naturaleza_por_codigo("2.1.7.2.5") == "pasivo"
    assert naturaleza_por_codigo("3.1") == "patrimonio"
    assert naturaleza_por_codigo("4.1.1.4") == "ingreso"
    assert naturaleza_por_codigo("5.2.1") == "gasto"
    assert naturaleza_por_codigo("6.1") == "gasto"
    assert naturaleza_por_codigo("X") is None
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_catalogo.py -q`
Expected: FAIL — `ModuleNotFoundError: ...mayor.catalogo`

- [ ] **Step 3: Implementación mínima**

`backend/app/aud/obligaciones_fiscales/mayor/catalogo.py`:

```python
"""Catálogo de categorías fiscales.

Esta es la SEMILLA de sistema. En el Plan 2 el catálogo pasa a ser
configurable por organización en base de datos, tomando estas entradas como
valores iniciales.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Categoria:
    codigo: str
    nombre: str
    naturaleza_esperada: str  # activo | pasivo | ingreso | gasto
    orden: int


CATEGORIAS: dict[str, Categoria] = {
    c.codigo: c
    for c in (
        Categoria("IVA_COMPRAS", "IVA en compras", "activo", 1),
        Categoria("IVA_RETENIDO", "IVA retenido por clientes", "activo", 2),
        Categoria("IVA_VENTAS", "IVA en ventas", "pasivo", 3),
        Categoria("IVA_DIFERIDO", "IVA diferido", "pasivo", 4),
        Categoria("RET_RENTA", "Retenciones en la fuente de renta por pagar", "pasivo", 5),
        Categoria("RET_IVA", "Retenciones de IVA por pagar", "pasivo", 6),
        Categoria("VENTAS", "Ventas", "ingreso", 7),
    )
}

_NATURALEZA_POR_DIGITO = {
    "1": "activo", "2": "pasivo", "3": "patrimonio",
    "4": "ingreso", "5": "gasto", "6": "gasto",
}


def naturaleza_por_codigo(codigo: str) -> str | None:
    """Naturaleza contable según el primer dígito del código de cuenta."""
    primero = (codigo or "").strip()[:1]
    return _NATURALEZA_POR_DIGITO.get(primero)


def categorias_por_naturaleza(naturaleza: str | None) -> list[str]:
    if not naturaleza:
        return []
    return [c.codigo for c in CATEGORIAS.values() if c.naturaleza_esperada == naturaleza]
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_catalogo.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/catalogo.py tests/test_of_mayor_catalogo.py
git commit -m "feat(mayor): catalogo semilla de categorias fiscales"
```

---

### Task 8: Señal de nombre y extracción de tarifa

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/senales.py`
- Test: `tests/test_of_mayor_senales.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Extractores de señal, uno por fuente de evidencia."""

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.senales import (
    extraer_tarifa,
    senal_nombre,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import PerfilCuenta


def _perfil(codigo, nombre, **kw):
    return PerfilCuenta(codigo=codigo, nombre=nombre, **kw)


def _mejor(senales):
    return max(senales, key=lambda s: s.puntaje).categoria if senales else None


@pytest.mark.parametrize(
    "nombre,esperada",
    [
        ("IVA sobre Compras", 1.0),          # sin tarifa en el nombre
        ("Ret. 1% Bienes Muebles de Naturaleza Corporal", 1.0),
        ("Ret. 1.75% Bienes Muebles de Naturaleza Corporal", 1.75),
        ("Ret. 2.75% Servicios", 2.75),
        ("Ret. 10% Honorarios Profesionales y Dietas", 10.0),
        ("Ret. 100% Honorarios, Arrendamientos", 100.0),
        ("Retención del 70%", 70.0),
    ],
)
def test_extrae_la_tarifa_del_nombre(nombre, esperada):
    tarifa = extraer_tarifa(nombre)
    if "%" not in nombre:
        assert tarifa is None
    else:
        assert tarifa == esperada


def test_no_confunde_el_10_dentro_de_100():
    assert extraer_tarifa("Ret. 100% Honorarios, Arrendamientos") == 100.0


@pytest.mark.parametrize(
    "nombre,categoria",
    [
        ("IVA sobre Compras", "IVA_COMPRAS"),
        ("IVA en Importaciones", "IVA_COMPRAS"),
        ("IVA sobre Ventas", "IVA_VENTAS"),
        ("IVA Retenido", "IVA_RETENIDO"),
        ("IVA Diferido", "IVA_DIFERIDO"),
        ("Ret. 10% Honorarios Profesionales y Dietas", "RET_RENTA"),
        ("Ret. 2.75% Servicios", "RET_RENTA"),
        ("Ret. 30% Bienes", "RET_IVA"),
        ("Ret. 70% Servicios", "RET_IVA"),
        ("Ret. 100% Honorarios, Arrendamientos", "RET_IVA"),
        ("Venta de insumos odontologicos", "VENTAS"),
        ("Servicios Odontologicos", "VENTAS"),
        ("Rebaja y/o Descuentos sobre Ventas", "VENTAS"),
    ],
)
def test_el_nombre_apunta_a_la_categoria_correcta(nombre, categoria):
    assert _mejor(senal_nombre(_perfil("9", nombre))) == categoria


def test_retencion_sin_porcentaje_queda_ambigua_entre_renta_e_iva():
    senales = senal_nombre(_perfil("2.1.7.2.11", "Retencion imptos relacion dependencia"))
    categorias = {s.categoria for s in senales}
    assert categorias == {"RET_RENTA", "RET_IVA"}


def test_nombre_irreconocible_no_produce_senales():
    assert senal_nombre(_perfil("9.9", "Cuenta puente varios")) == []


def test_la_senal_explica_su_motivo():
    senal = senal_nombre(_perfil("1.1.5.1.1", "IVA sobre Compras"))[0]
    assert "nombre" in senal.motivo.lower()
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_senales.py -q`
Expected: FAIL — `ModuleNotFoundError: ...mayor.senales`

- [ ] **Step 3: Implementación mínima**

`backend/app/aud/obligaciones_fiscales/mayor/senales.py`:

```python
"""Extractores de señal.

Cada función recibe un PerfilCuenta y devuelve una lista de Senal
(categoría, puntaje, motivo). El motivo es lo que se imprime en la hoja de
trazabilidad del papel de trabajo: ninguna clasificación es una caja negra.
"""

from __future__ import annotations

import re
import unicodedata

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import (
    CATEGORIAS,
    categorias_por_naturaleza,
    naturaleza_por_codigo,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import PerfilCuenta, Senal

PESO_NOMBRE = 40
PESO_NOMBRE_AMBIGUO = 20

# Tarifas de retención de IVA en Ecuador; el resto son de renta.
TARIFAS_RET_IVA = {10.0, 20.0, 30.0, 50.0, 70.0, 100.0}
# El 10% existe en ambos regímenes (arriendos/honorarios de renta), así que
# solo las tarifas altas discriminan por sí solas.
TARIFAS_SOLO_RET_IVA = {20.0, 30.0, 50.0, 70.0, 100.0}

_RE_TARIFA = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _norm(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def extraer_tarifa(nombre: str) -> float | None:
    """Porcentaje declarado en el nombre de la cuenta, si lo hay."""
    m = _RE_TARIFA.search(nombre or "")
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def senal_nombre(perfil: PerfilCuenta) -> list[Senal]:
    """Patrones de dominio sobre el nombre de la cuenta."""
    n = _norm(perfil.nombre)
    if not n:
        return []

    if "iva" in n and "diferido" in n:
        return [Senal("IVA_DIFERIDO", PESO_NOMBRE, f"nombre contiene 'IVA diferido': {perfil.nombre!r}")]
    if "iva" in n and "retenido" in n:
        return [Senal("IVA_RETENIDO", PESO_NOMBRE, f"nombre contiene 'IVA retenido': {perfil.nombre!r}")]
    if "iva" in n and re.search(r"compra|adquisic|importac", n):
        return [Senal("IVA_COMPRAS", PESO_NOMBRE, f"nombre indica IVA de compras: {perfil.nombre!r}")]
    if "iva" in n and "venta" in n:
        return [Senal("IVA_VENTAS", PESO_NOMBRE, f"nombre indica IVA de ventas: {perfil.nombre!r}")]

    if re.search(r"\bret\b|retenc", n):
        tarifa = extraer_tarifa(perfil.nombre)
        if tarifa in TARIFAS_SOLO_RET_IVA:
            return [Senal("RET_IVA", PESO_NOMBRE, f"nombre con tarifa {tarifa}% de retención de IVA")]
        if tarifa is not None:
            return [Senal("RET_RENTA", PESO_NOMBRE, f"nombre con tarifa {tarifa}% de retención de renta")]
        return [
            Senal("RET_RENTA", PESO_NOMBRE_AMBIGUO, "nombre menciona retención, sin tarifa"),
            Senal("RET_IVA", PESO_NOMBRE_AMBIGUO, "nombre menciona retención, sin tarifa"),
        ]

    if re.search(r"venta|ingreso|servicio|descuento|rebaja", n):
        return [Senal("VENTAS", PESO_NOMBRE, f"nombre indica ventas o ingresos: {perfil.nombre!r}")]

    return []
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_senales.py -q`
Expected: `22 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/senales.py tests/test_of_mayor_senales.py
git commit -m "feat(mayor): senal de nombre con extraccion de tarifa"
```

---

### Task 9: Señales de código, naturaleza, movimientos y contrapartidas

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/mayor/senales.py`
- Modify: `tests/test_of_mayor_senales.py`

- [ ] **Step 1: Escribir el test que falla**

Añadir a `tests/test_of_mayor_senales.py`:

```python
from backend.app.aud.obligaciones_fiscales.mayor.senales import (
    senal_codigo,
    senal_contrapartidas,
    senal_movimientos,
    senal_naturaleza,
)


def test_el_codigo_apunta_a_las_categorias_de_su_naturaleza():
    senales = senal_codigo(_perfil("2.1.7.2.5", "Ret. 10% Honorarios"))
    categorias = {s.categoria for s in senales}
    assert categorias == {"IVA_VENTAS", "IVA_DIFERIDO", "RET_RENTA", "RET_IVA"}
    assert all(s.puntaje == 15 for s in senales)


def test_codigo_sin_primer_digito_conocido_no_opina():
    assert senal_codigo(_perfil("XYZ", "algo")) == []


def test_saldo_deudor_penaliza_las_categorias_de_pasivo_e_ingreso():
    senales = senal_naturaleza(_perfil("1.1.5.1.2", "Credito Tributario", debe=100.0))
    positivas = {s.categoria for s in senales if s.puntaje > 0}
    negativas = {s.categoria for s in senales if s.puntaje < 0}
    assert positivas == {"IVA_COMPRAS", "IVA_RETENIDO"}
    assert "VENTAS" in negativas
    assert all(s.puntaje == -30 for s in senales if s.puntaje < 0)


def test_cuenta_liquidada_cada_mes_queda_neutra_y_la_senal_calla():
    """Caso real: las cuentas de impuestos cierran en cero cada mes."""
    perfil = _perfil("1.1.5.1.1", "IVA sobre Compras", debe=21167.49, haber=21167.49)
    assert perfil.tendencia == "neutro"
    assert senal_naturaleza(perfil) == []


def test_prefijo_de_asiento_dominante_refuerza_la_categoria():
    perfil = _perfil("4.1.1.4", "Venta", prefijos_asiento={"VTA": 90, "ASI": 10})
    categorias = {s.categoria for s in senal_movimientos(perfil)}
    assert categorias == {"VENTAS", "IVA_VENTAS"}


def test_sin_prefijo_dominante_la_senal_calla():
    perfil = _perfil("4.1.1.4", "Venta", prefijos_asiento={"VTA": 5, "COM": 5})
    assert senal_movimientos(perfil) == []


def test_contrapartida_dominante_ya_clasificada_refuerza_su_categoria():
    perfil = _perfil("4.1.1.9", "Otra venta", contrapartidas=[("4.1.1.4", 30)])
    senales = senal_contrapartidas(perfil, {"4.1.1.4": "VENTAS"})
    assert senales[0].categoria == "VENTAS"
    assert senales[0].puntaje == 15


def test_contrapartida_de_otra_naturaleza_no_aporta():
    perfil = _perfil("2.1.7.4.1", "IVA Ventas", contrapartidas=[("4.1.1.4", 30)])
    assert senal_contrapartidas(perfil, {"4.1.1.4": "VENTAS"}) == []


def test_sin_contrapartidas_la_senal_calla_y_no_penaliza():
    assert senal_contrapartidas(_perfil("1.1.5.1.1", "IVA Compras"), {}) == []
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_senales.py -q`
Expected: FAIL — `ImportError: cannot import name 'senal_codigo'`

- [ ] **Step 3: Implementación mínima**

Añadir a `senales.py` las constantes y funciones:

```python
PESO_CODIGO = 15
PESO_NATURALEZA = 10
PENALIZACION_NATURALEZA = -30
PESO_MOVIMIENTOS = 10
PESO_CONTRAPARTIDA = 15

UMBRAL_PREFIJO_DOMINANTE = 0.6

# Qué categorías sugiere cada prefijo de asiento del ERP.
PREFIJOS = {
    "VTA": ("VENTAS", "IVA_VENTAS"),
    "COM": ("IVA_COMPRAS",),
    "RET": ("RET_RENTA", "RET_IVA", "IVA_RETENIDO"),
}

# Tendencia del saldo → naturalezas compatibles.
_TENDENCIA_A_NATURALEZAS = {
    "deudor": ("activo", "gasto"),
    "acreedor": ("pasivo", "ingreso"),
}


def senal_codigo(perfil: PerfilCuenta) -> list[Senal]:
    """El primer dígito del código acota las categorías posibles."""
    naturaleza = naturaleza_por_codigo(perfil.codigo)
    if not naturaleza:
        return []
    return [
        Senal(cat, PESO_CODIGO, f"código {perfil.codigo} es de naturaleza {naturaleza}")
        for cat in categorias_por_naturaleza(naturaleza)
    ]


def senal_naturaleza(perfil: PerfilCuenta) -> list[Senal]:
    """La tendencia del saldo confirma o veta categorías.

    Si la cuenta se liquida cada mes (debe == haber) la tendencia es neutra
    y la señal no opina: penalizar ahí sería un falso negativo.
    """
    compatibles = _TENDENCIA_A_NATURALEZAS.get(perfil.tendencia)
    if not compatibles:
        return []
    senales: list[Senal] = []
    for cat in CATEGORIAS.values():
        if cat.naturaleza_esperada in compatibles:
            senales.append(
                Senal(cat.codigo, PESO_NATURALEZA,
                      f"saldo {perfil.tendencia} coincide con naturaleza {cat.naturaleza_esperada}")
            )
        else:
            senales.append(
                Senal(cat.codigo, PENALIZACION_NATURALEZA,
                      f"saldo {perfil.tendencia} contradice naturaleza {cat.naturaleza_esperada}")
            )
    return senales


def senal_movimientos(perfil: PerfilCuenta) -> list[Senal]:
    """El prefijo de asiento dominante indica el tipo de transacción."""
    total = sum(perfil.prefijos_asiento.values())
    if not total:
        return []
    prefijo, veces = max(perfil.prefijos_asiento.items(), key=lambda kv: kv[1])
    if veces / total < UMBRAL_PREFIJO_DOMINANTE:
        return []
    categorias = PREFIJOS.get(prefijo.upper())
    if not categorias:
        return []
    pct = round(100 * veces / total)
    return [
        Senal(cat, PESO_MOVIMIENTOS,
              f"{pct}% de los asientos son '{prefijo}'")
        for cat in categorias
    ]


def senal_contrapartidas(
    perfil: PerfilCuenta, clasificadas: dict[str, str]
) -> list[Senal]:
    """Refuerza la categoría de la contrapartida dominante ya clasificada.

    Solo aplica si comparten naturaleza: el IVA de ventas (pasivo) tiene por
    contrapartida a las ventas (ingreso) y NO debe heredar su categoría.
    """
    if not perfil.contrapartidas:
        return []
    codigo_cp, veces = perfil.contrapartidas[0]
    categoria = clasificadas.get(codigo_cp)
    if not categoria or categoria not in CATEGORIAS:
        return []
    if CATEGORIAS[categoria].naturaleza_esperada != naturaleza_por_codigo(perfil.codigo):
        return []
    return [
        Senal(categoria, PESO_CONTRAPARTIDA,
              f"contrapartida dominante {codigo_cp} ({veces} asientos) es {categoria}")
    ]
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_senales.py -q`
Expected: `31 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/senales.py tests/test_of_mayor_senales.py
git commit -m "feat(mayor): senales de codigo, naturaleza, movimientos y contrapartidas"
```

---

### Task 10: Señales de historial y de rama

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/mayor/senales.py`
- Modify: `tests/test_of_mayor_senales.py`

- [ ] **Step 1: Escribir el test que falla**

Añadir a `tests/test_of_mayor_senales.py`:

```python
from backend.app.aud.obligaciones_fiscales.mayor.senales import (
    PESO_HISTORIAL,
    senal_historial,
    senal_rama,
)


def test_el_historial_del_cliente_manda_sobre_todo_lo_demas():
    senales = senal_historial(
        _perfil("2.1.7.2.11", "Retencion imptos relacion dependencia"),
        {"2.1.7.2.11": "RET_RENTA"},
    )
    assert senales[0].categoria == "RET_RENTA"
    assert senales[0].puntaje == PESO_HISTORIAL
    assert PESO_HISTORIAL > 100


def test_sin_historial_para_esa_cuenta_no_hay_senal():
    assert senal_historial(_perfil("9.9", "x"), {"1.1": "VENTAS"}) == []


def test_una_cuenta_hereda_la_categoria_de_sus_hermanas_de_rama():
    """2.1.7.2.11 hereda de 2.1.7.2.5 y 2.1.7.2.8, sus hermanas."""
    senales = senal_rama(
        _perfil("2.1.7.2.11", "Retencion imptos relacion dependencia"),
        {"2.1.7.2.5": "RET_RENTA", "2.1.7.2.8": "RET_RENTA"},
    )
    assert senales[0].categoria == "RET_RENTA"
    assert senales[0].puntaje == 25


def test_hermanas_en_desacuerdo_ganan_por_mayoria():
    senales = senal_rama(
        _perfil("2.1.7.2.11", "x"),
        {"2.1.7.2.5": "RET_RENTA", "2.1.7.2.8": "RET_RENTA", "2.1.7.2.1": "RET_IVA"},
    )
    assert senales[0].categoria == "RET_RENTA"


def test_una_cuenta_de_otra_rama_no_contamina():
    assert senal_rama(_perfil("4.1.1.4", "Venta"), {"2.1.7.2.5": "RET_RENTA"}) == []


def test_codigo_de_un_solo_segmento_no_tiene_rama():
    assert senal_rama(_perfil("4", "Ingresos"), {"5": "VENTAS"}) == []
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_senales.py -q`
Expected: FAIL — `ImportError: cannot import name 'PESO_HISTORIAL'`

- [ ] **Step 3: Implementación mínima**

Añadir a `senales.py`:

```python
from collections import Counter

# El historial del cliente es evidencia directa: domina cualquier heurística.
PESO_HISTORIAL = 1000
PESO_RAMA = 25


def senal_historial(perfil: PerfilCuenta, historial: dict[str, str]) -> list[Senal]:
    """Homologación previa del MISMO cliente para el MISMO código."""
    categoria = historial.get(perfil.codigo)
    if not categoria:
        return []
    return [
        Senal(categoria, PESO_HISTORIAL,
              f"homologación previa del cliente para la cuenta {perfil.codigo}")
    ]


def _rama(codigo: str) -> str | None:
    """Prefijo de la cuenta sin su último segmento ('2.1.7.2.5' → '2.1.7.2')."""
    partes = (codigo or "").split(".")
    return ".".join(partes[:-1]) if len(partes) > 1 else None


def senal_rama(perfil: PerfilCuenta, clasificadas: dict[str, str]) -> list[Senal]:
    """Las cuentas hermanas del mismo prefijo suelen ser de la misma categoría."""
    rama = _rama(perfil.codigo)
    if not rama:
        return []
    votos = Counter(
        categoria
        for codigo, categoria in clasificadas.items()
        if codigo != perfil.codigo and _rama(codigo) == rama
    )
    if not votos:
        return []
    categoria, n = votos.most_common(1)[0]
    return [
        Senal(categoria, PESO_RAMA,
              f"{n} cuenta(s) hermana(s) de la rama {rama} están en {categoria}")
    ]
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_senales.py -q`
Expected: `37 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/senales.py tests/test_of_mayor_senales.py
git commit -m "feat(mayor): senales de historial del cliente y propagacion por rama"
```

---

### Task 11: Clasificador

**Files:**
- Create: `backend/app/aud/obligaciones_fiscales/mayor/clasificador.py`
- Test: `tests/test_of_mayor_clasificador.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Combinación de señales en una categoría con confianza y justificación."""

from backend.app.aud.obligaciones_fiscales.mayor.clasificador import (
    clasificar,
    clasificar_cuenta,
)
from backend.app.aud.obligaciones_fiscales.mayor.tipos import PerfilCuenta


def _perfil(codigo, nombre, **kw):
    return PerfilCuenta(codigo=codigo, nombre=nombre, **kw)


def test_iva_sobre_compras_se_clasifica_con_confianza_alta():
    r = clasificar_cuenta(
        _perfil("1.1.5.1.1", "IVA sobre Compras", prefijos_asiento={"COM": 100})
    )
    assert r.categoria == "IVA_COMPRAS"
    assert r.confianza == "alta"
    assert r.origen == "reglas"


def test_retencion_del_70_por_ciento_va_a_retenciones_de_iva():
    r = clasificar_cuenta(
        _perfil("2.1.7.3.2", "Ret. 70% Servicios", prefijos_asiento={"RET": 149})
    )
    assert r.categoria == "RET_IVA"
    assert r.tarifa == 70.0


def test_retencion_del_10_por_ciento_va_a_retenciones_de_renta():
    r = clasificar_cuenta(
        _perfil("2.1.7.2.5", "Ret. 10% Honorarios Profesionales y Dietas",
                prefijos_asiento={"RET": 889})
    )
    assert r.categoria == "RET_RENTA"
    assert r.tarifa == 10.0


def test_el_historial_gana_aunque_las_reglas_digan_otra_cosa():
    r = clasificar_cuenta(
        _perfil("1.1.5.1.1", "IVA sobre Compras"),
        historial={"1.1.5.1.1": "IVA_DIFERIDO"},
    )
    assert r.categoria == "IVA_DIFERIDO"
    assert r.confianza == "alta"
    assert r.origen == "historial"


def test_una_cuenta_irreconocible_queda_en_baja_confianza():
    r = clasificar_cuenta(_perfil("9.9.9", "Cuenta puente varios"))
    assert r.confianza == "baja"


def test_el_resultado_explica_por_que():
    r = clasificar_cuenta(_perfil("1.1.5.1.1", "IVA sobre Compras"))
    assert any("nombre" in m.lower() for m in r.justificacion)
    assert r.puntajes["IVA_COMPRAS"] > 0


def test_la_segunda_pasada_propaga_la_categoria_a_las_hermanas():
    """2.1.7.2.11 no tiene tarifa en el nombre; sus hermanas la resuelven."""
    perfiles = {
        "2.1.7.2.5": _perfil("2.1.7.2.5", "Ret. 10% Honorarios Profesionales",
                             prefijos_asiento={"RET": 889}),
        "2.1.7.2.8": _perfil("2.1.7.2.8", "Ret. 2.75% Servicios",
                             prefijos_asiento={"RET": 170}),
        "2.1.7.2.11": _perfil("2.1.7.2.11", "Retencion imptos relacion dependencia",
                              prefijos_asiento={"NOM": 18}),
    }
    resultados = {r.codigo: r for r in clasificar(perfiles)}
    assert resultados["2.1.7.2.11"].categoria == "RET_RENTA"


def test_clasificar_devuelve_un_resultado_por_cuenta():
    perfiles = {
        "1.1.5.1.1": _perfil("1.1.5.1.1", "IVA sobre Compras"),
        "4.1.1.4": _perfil("4.1.1.4", "Venta de insumos odontologicos"),
    }
    assert len(clasificar(perfiles)) == 2
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_of_mayor_clasificador.py -q`
Expected: FAIL — `ModuleNotFoundError: ...mayor.clasificador`

- [ ] **Step 3: Implementación mínima**

`backend/app/aud/obligaciones_fiscales/mayor/clasificador.py`:

```python
"""Combina las señales de una cuenta en una decisión explicable.

Dos pasadas: la primera clasifica con la evidencia propia de cada cuenta; la
segunda agrega las señales que dependen de cómo quedaron las demás
(contrapartidas y propagación por rama).
"""

from __future__ import annotations

from collections import defaultdict

from backend.app.aud.obligaciones_fiscales.mayor import senales as sig
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    PerfilCuenta,
    ResultadoClasificacion,
    Senal,
)

UMBRAL_ALTA = 60
UMBRAL_MEDIA = 35
VENTAJA_MINIMA_ALTA = 25


def _acumular(senales: list[Senal]) -> dict[str, int]:
    puntajes: dict[str, int] = defaultdict(int)
    for s in senales:
        puntajes[s.categoria] += s.puntaje
    return dict(puntajes)


def _decidir(puntajes: dict[str, int]) -> tuple[str | None, str]:
    if not puntajes:
        return None, "baja"
    orden = sorted(puntajes.items(), key=lambda kv: kv[1], reverse=True)
    lider, punt_lider = orden[0]
    punt_segundo = orden[1][1] if len(orden) > 1 else 0
    if punt_lider <= 0:
        return None, "baja"
    if punt_lider >= sig.PESO_HISTORIAL:
        return lider, "alta"
    if punt_lider >= UMBRAL_ALTA and (punt_lider - punt_segundo) >= VENTAJA_MINIMA_ALTA:
        return lider, "alta"
    if punt_lider >= UMBRAL_MEDIA:
        return lider, "media"
    return lider, "baja"


def clasificar_cuenta(
    perfil: PerfilCuenta,
    *,
    historial: dict[str, str] | None = None,
    clasificadas: dict[str, str] | None = None,
) -> ResultadoClasificacion:
    """Clasifica una cuenta con toda la evidencia disponible."""
    historial = historial or {}
    clasificadas = clasificadas or {}

    senales: list[Senal] = []
    senales += sig.senal_historial(perfil, historial)
    senales += sig.senal_nombre(perfil)
    senales += sig.senal_codigo(perfil)
    senales += sig.senal_naturaleza(perfil)
    senales += sig.senal_movimientos(perfil)
    senales += sig.senal_contrapartidas(perfil, clasificadas)
    senales += sig.senal_rama(perfil, clasificadas)

    puntajes = _acumular(senales)
    categoria, confianza = _decidir(puntajes)
    origen = "historial" if perfil.codigo in historial else "reglas"

    return ResultadoClasificacion(
        codigo=perfil.codigo,
        nombre=perfil.nombre,
        categoria=categoria,
        confianza=confianza,
        origen=origen,
        tarifa=sig.extraer_tarifa(perfil.nombre),
        puntajes=puntajes,
        senales=[s for s in senales if s.puntaje > 0],
    )


def clasificar(
    perfiles: dict[str, PerfilCuenta],
    *,
    historial: dict[str, str] | None = None,
) -> list[ResultadoClasificacion]:
    """Clasifica todas las cuentas del mayor en dos pasadas."""
    historial = historial or {}

    primera = {
        codigo: clasificar_cuenta(p, historial=historial)
        for codigo, p in perfiles.items()
    }
    # Solo lo resuelto con confianza alta sirve de apoyo para las demás.
    apoyo = {
        codigo: r.categoria
        for codigo, r in primera.items()
        if r.categoria and r.confianza == "alta"
    }

    segunda = [
        clasificar_cuenta(p, historial=historial, clasificadas=apoyo)
        for p in perfiles.values()
    ]
    return sorted(segunda, key=lambda r: r.codigo)
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_of_mayor_clasificador.py -q`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/obligaciones_fiscales/mayor/clasificador.py tests/test_of_mayor_clasificador.py
git commit -m "feat(mayor): clasificador en dos pasadas con confianza y justificacion"
```

---

### Task 12: Verificación empírica contra el mayor real

Esta es la tarea que hace cumplir la **REGLA SUPREMA** del `CLAUDE.md`: el motor no está listo hasta que reproduce el trabajo manual del auditor sobre datos reales.

**Files:**
- Create: `tests/test_of_mayor_real_medi.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Verificación empírica del motor contra el mayor real de un cliente.

Los archivos NO se commitean (repo público): se leen de la carpeta apuntada
por AUD_OF_FIXTURES_DIR y el test hace skip si no está.

Verdad de referencia: el archivo BASE DE IMPUESTOS.xlsx que el auditor arma
a mano, cuyas hojas por categoría tienen exactamente estos conteos.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.app.aud.obligaciones_fiscales.mayor.clasificador import clasificar
from backend.app.aud.obligaciones_fiscales.mayor.cuentas import perfilar
from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor

MOVIMIENTOS_POR_CATEGORIA = {
    "IVA_COMPRAS": 550,
    "IVA_RETENIDO": 58,
    "IVA_VENTAS": 155,
    "RET_RENTA": 1254,
    "RET_IVA": 236,
    "VENTAS": 2427,
}
TOTAL_MOVIMIENTOS = 4680
TOTAL_CUENTAS = 28

pytestmark = pytest.mark.skipif(
    not os.getenv("AUD_OF_FIXTURES_DIR"),
    reason="Requiere AUD_OF_FIXTURES_DIR con el mayor real del cliente",
)


@pytest.fixture(scope="module")
def lectura():
    ruta = Path(os.environ["AUD_OF_FIXTURES_DIR"]) / "MAYOR DE IMPUESTOS.xlsx"
    if not ruta.exists():
        pytest.skip(f"No está {ruta}")
    return leer_mayor(ruta.read_bytes())


@pytest.fixture(scope="module")
def resultados(lectura):
    return {r.codigo: r for r in clasificar(perfilar(lectura.movimientos))}


def test_lee_todos_los_movimientos_del_mayor(lectura):
    assert lectura.mapeo_suficiente, lectura.columnas_faltantes
    assert len(lectura.movimientos) == TOTAL_MOVIMIENTOS


def test_identifica_las_veintiocho_cuentas(lectura):
    assert len(perfilar(lectura.movimientos)) == TOTAL_CUENTAS


def test_ninguna_cuenta_queda_sin_categoria(resultados):
    sin_categoria = [r.codigo for r in resultados.values() if r.categoria is None]
    assert not sin_categoria, f"Cuentas sin clasificar: {sin_categoria}"


def test_los_conteos_por_categoria_coinciden_con_el_trabajo_manual(lectura, resultados):
    conteo: dict[str, int] = {}
    for m in lectura.movimientos:
        categoria = resultados[m.codigo].categoria
        conteo[categoria] = conteo.get(categoria, 0) + 1

    assert conteo == MOVIMIENTOS_POR_CATEGORIA


def test_reporta_cuantas_cuentas_necesitan_revision_humana(resultados, capsys):
    """No falla: documenta cuánto trabajo le queda al auditor en el primer uso."""
    por_confianza: dict[str, list[str]] = {}
    for r in resultados.values():
        por_confianza.setdefault(r.confianza, []).append(f"{r.codigo} {r.nombre}")
    with capsys.disabled():
        for nivel in ("alta", "media", "baja"):
            cuentas = por_confianza.get(nivel, [])
            print(f"\n  confianza {nivel}: {len(cuentas)} cuenta(s)")
            for c in cuentas:
                print(f"    - {c}")
    assert len(por_confianza.get("alta", [])) >= 20
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run:
```bash
AUD_OF_FIXTURES_DIR="<carpeta con los archivos del cliente>" python -m pytest tests/test_of_mayor_real_medi.py -q
```
En PowerShell: `$env:AUD_OF_FIXTURES_DIR="<carpeta>"; python -m pytest tests/test_of_mayor_real_medi.py -q`

Expected: FAIL en `test_los_conteos_por_categoria_coinciden_con_el_trabajo_manual` si alguna cuenta cae en la categoría equivocada. El mensaje del `assert` muestra el diccionario obtenido contra el esperado.

- [ ] **Step 3: Ajustar el motor hasta que el conteo cuadre**

No se toca el test: se corrige el motor. Diagnóstico por cuenta:

```bash
python -c "
import os, sys; sys.path.insert(0,'.')
from pathlib import Path
from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor
from backend.app.aud.obligaciones_fiscales.mayor.cuentas import perfilar
from backend.app.aud.obligaciones_fiscales.mayor.clasificador import clasificar
ruta = Path(os.environ['AUD_OF_FIXTURES_DIR'])/'MAYOR DE IMPUESTOS.xlsx'
perfiles = perfilar(leer_mayor(ruta.read_bytes()).movimientos)
for r in clasificar(perfiles):
    print(f'{r.codigo:<14} {r.nombre[:42]:<44} {str(r.categoria):<14} {r.confianza:<6} {r.puntajes}')
"
```

Ajustes previsibles y dónde van:
- Un patrón de nombre que falta → `SINONIMOS`/regex de `senal_nombre` en `senales.py`.
- Un prefijo de asiento del ERP no contemplado (`EGR`, `NOM`) → diccionario `PREFIJOS` en `senales.py`.
- Un umbral mal calibrado → constantes `UMBRAL_ALTA` / `UMBRAL_MEDIA` en `clasificador.py`.

Cada ajuste exige **primero** un test unitario nuevo en el archivo de tests correspondiente que reproduzca el caso con datos sintéticos, y recién después el cambio en el motor.

- [ ] **Step 4: Correr todo y verificar que pasa**

Run: `$env:AUD_OF_FIXTURES_DIR="<carpeta>"; python -m pytest tests/ -k mayor -q`
Expected: todos verdes, incluido el conteo exacto `550 / 58 / 155 / 1254 / 236 / 2427`.

Run también la suite completa para descartar regresiones:
`python -m pytest tests/ -q -p no:warnings`
Expected: sin fallos nuevos respecto de la línea base (527 passed, 2 skipped).

- [ ] **Step 5: Commit**

```bash
git add tests/test_of_mayor_real_medi.py backend/app/aud/obligaciones_fiscales/mayor/
git commit -m "test(mayor): verificacion empirica contra el mayor real del cliente"
```

---

## Criterio de terminado del Plan 1

- [ ] Las 12 tareas están commiteadas.
- [ ] `python -m pytest tests/ -k mayor -q` pasa en verde.
- [ ] La suite completa no tiene fallos nuevos.
- [ ] Con el mayor real: 4.680 movimientos leídos, 28 cuentas perfiladas, 0 cuentas sin categoría y los 6 conteos por categoría idénticos al trabajo manual del auditor.
- [ ] El reporte de confianzas queda documentado en el commit final (cuántas cuentas exigirían revisión humana en el primer uso con un cliente nuevo).

## Lo que este plan deliberadamente NO hace

- No toca la base de datos: el historial de homologaciones entra como `dict` (Plan 2).
- No expone endpoints ni cambia el ciclo de vida del job (Plan 2).
- No genera Excel (Plan 3).
- No toca el frontend (Plan 4).
- No implementa el sugeridor por LLM (fase posterior, si hace falta).
