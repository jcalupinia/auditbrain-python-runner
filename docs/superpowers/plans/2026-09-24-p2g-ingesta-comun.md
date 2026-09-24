# P2-G · Ingesta común — `checked_zip` compartido, `.xls` legado, sha256 en ICT y perfiles de preparación por cliente

> **For agentic workers:** REQUIRED SUB-SKILL: usar `superpowers:subagent-driven-development` o `superpowers:executing-plans`. Pasos con checkbox (`- [ ]`).
>
> **Entorno:** corre en el **servidor** (`auditbrain-python-runner`), con FastAPI/SQLAlchemy/openpyxl/xlrd. Las dependencias NO corren en el contenedor donde se escribió el plan; cada tarea se lleva **a verde con `pytest`** en el servidor.

**Goal:** que la ingesta de archivos deje de estar dispersa y a medias: promover el guardián anti-zip-bomb a utilidad común, aceptar `.xls` legado, sellar con sha256 los archivos que entran al flujo ICT, y externalizar sinónimos/mapeos a **perfiles de preparación reutilizables por cliente** (para no re-mapear a mano cada vez).

**Capacidades que cierra:** DATA-004 (ZIP ingestion, hoy en un solo módulo), DATA-001 (Excel import, sin `.xls` legado), DATA-008 (source hash, falta en el flujo ICT), DATA-009 (schema inference, sinónimos hardcodeados), DATA-010 (field mapping, sin re-mapeo por cliente), DQ-014 (reusable prep profile, sin perfil por cliente).

## Architecture

- **Un solo guardián de archivos.** `backend/app/aud/inventarios_vnr/parsers.py::checked_zip` (anti-zip-bomb: tope de entradas, ratio de compresión, rutas absolutas/`..`, cifrado) es hoy la única defensa y vive en un módulo de negocio. Se **promueve** a `backend/app/ingesta_comun/archivos.py` sin cambiar su lógica ni sus límites; `inventarios_vnr` pasa a importarla desde ahí (alias retrocompat) para no romper su comportamiento ni sus tests.
- **Lector Excel común con `.xls`.** Ya existe la detección correcta por _magic bytes_ en `backend/app/tax/planificacion_utilidades/parsers/_shared.py::_read_excel` (`data[:4] == b"\xd0\xcf\x11\xe0"` → `xlrd`, si no → `openpyxl`). Se extrae a `ingesta_comun/excel.py::abrir_libro(data)` como fuente única, para que el lector de mayor y los parsers ICT (`ict/parsers/*_excel.py`, hoy solo `.xlsx` vía `load_workbook`) acepten `.xls` sin duplicar la heurística.
- **sha256 en el flujo ICT.** `leer_mayor` ya calcula sha256; el flujo ICT no. El chokepoint es `ict/service.py::save_uploaded_file(..., data: bytes, ...)`: ahí se calcula y persiste la huella del archivo. Cierra el lineage del ICT (DATA-008) sin tocar los parsers.
- **Perfiles de preparación por cliente.** Los `SINONIMOS`/`MAPEO` viven hardcodeados en `mayor/reader.py` y `ingesta/mayor.py`. Se introduce `PerfilPreparacion` (por cliente/RUC): overrides de sinónimos, mapeo de columnas fijo, formato numérico regional y descartes. El lector acepta un perfil opcional que **extiende/pisa** los sinónimos base; sin perfil, el comportamiento actual no cambia. El perfil se guarda por cliente y se reutiliza entre sesiones (DQ-014), y es la base de la futura UI de re-mapeo (DATA-010).

**Principios que se conservan (benchmark §6 / `CLAUDE.md`):** nada se rellena con ceros inventados; una columna ausente queda ausente; formatos numéricos `.`/`,` soportados (regla de `CLAUDE.md`); `Decimal` para dinero en el motor.

**Tech Stack:** Python 3.12, openpyxl, xlrd (para `.xls`), SQLAlchemy, pytest. Repo `auditbrain-python-runner`, rama sugerida `p2g-ingesta-comun`.

**Contexto obligatorio a leer antes de empezar:**
- `backend/app/aud/inventarios_vnr/parsers.py` (`checked_zip`, `extract`, límites).
- `backend/app/tax/planificacion_utilidades/parsers/_shared.py` (`_read_excel`, detección `.xls`).
- `backend/app/aud/obligaciones_fiscales/mayor/reader.py` (`SINONIMOS`, `_mapear_encabezado`).
- `backend/app/ict/service.py` (`save_uploaded_file`, `reparse_session_uploads`) e `ict/parsers/*_excel.py`.
- `CLAUDE.md` — regla de formatos numéricos y de `_parse_amount`.

**Convenciones:** español en código/comentarios; `python -m pytest -q`; no cambiar límites de seguridad al mover código; no romper tests existentes de VNR/mayor/ICT.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `backend/app/ingesta_comun/__init__.py` (crear) | Exporta `checked_zip`, `abrir_libro`, `sha256_archivo`, `PerfilPreparacion` |
| `backend/app/ingesta_comun/archivos.py` (crear) | `checked_zip` + límites (movido, sin cambios), `sha256_archivo(data)` |
| `backend/app/ingesta_comun/excel.py` (crear) | `abrir_libro(data)` con detección `.xls`/`.xlsx` |
| `backend/app/ingesta_comun/perfiles.py` (crear) | `PerfilPreparacion`, fusión con sinónimos base, (de)serialización |
| `backend/app/aud/inventarios_vnr/parsers.py` (modificar mínimo) | importar `checked_zip` desde `ingesta_comun` (alias) |
| `backend/app/ict/models.py` (modificar) | columna `sha256` en el modelo de upload del ICT |
| `backend/app/ict/service.py` (modificar) | `save_uploaded_file` calcula/persiste sha256; `reparse` lo conserva |
| migración (crear) | columna `sha256` + backfill de uploads existentes |
| tests (crear) | ver cada tarea |

> **Nota de alcance:** `mayor/reader.py` (runner) y `motor/ingesta/mayor.py` (motor) mantienen sus propios `SINONIMOS` como **default**; los perfiles se aplican encima. El acople del perfil al lector del motor es una tarea del repo `motor-auditoria-analitica` y se enlaza desde su propio plan.

---

### Task 1: Promover `checked_zip` a utilidad común (DATA-004)

**Files:** Create `ingesta_comun/__init__.py`, `ingesta_comun/archivos.py`; Modify `inventarios_vnr/parsers.py`; Test `tests/test_ingesta_comun_archivos.py`.

- [ ] **Step 1: Pruebas que fallan** — portar los casos que hoy cubren `checked_zip` (ZIP con demasiadas entradas, ratio de compresión excesivo, ruta con `..`, entrada cifrada, expansión > tope) apuntando ahora a `from backend.app.ingesta_comun.archivos import checked_zip`, más `test_vnr_sigue_importando_checked_zip` que verifica que `inventarios_vnr.parsers.checked_zip is ingesta_comun.archivos.checked_zip`.
- [ ] **Step 2: Correr y ver que falla** — `ModuleNotFoundError: ...ingesta_comun`.
- [ ] **Step 3: Implementar**:
  - Mover `checked_zip` y sus constantes (`MAX_BYTES`, `MAX_EXPANDED`, `MAX_COLS`, `MAX_ROWS`) a `archivos.py` **sin cambiar ni un límite ni un mensaje** (son barreras de seguridad validadas).
  - Añadir `sha256_archivo(data: bytes) -> str` (una línea, `hashlib.sha256`), para el resto del plan.
  - En `inventarios_vnr/parsers.py`: `from backend.app.ingesta_comun.archivos import checked_zip` (mantener el nombre disponible en el módulo para no romper imports que ya existan).
- [ ] **Step 4: Correr** — `pytest tests/test_ingesta_comun_archivos.py -q` verde; **`pytest tests/ -k vnr -q` sin cambios** (crítico).
- [ ] **Step 5: Commit** — `refactor(ingesta): checked_zip como utilidad común sin cambiar límites`.

---

### Task 2: Lector Excel común con soporte `.xls` legado (DATA-001)

**Files:** Create `ingesta_comun/excel.py`; Test `tests/test_ingesta_comun_excel.py`.

- [ ] **Step 1: Pruebas que fallan**

```python
def test_abre_xlsx():
    libro = abrir_libro(_xlsx_bytes(...))
    assert libro.hojas  # devuelve un contrato uniforme, no un objeto openpyxl crudo

def test_abre_xls_legado():
    # magic bytes OLE2: b"\xd0\xcf\x11\xe0"
    libro = abrir_libro(_xls_bytes_de_fixture())
    assert libro.hojas

def test_archivo_no_excel_da_error_claro():
    with pytest.raises(ValueError, match="No es un Excel"):
        abrir_libro(b"no soy excel")
```

- [ ] **Step 2: Correr y ver que falla.**
- [ ] **Step 3: Implementar** `abrir_libro(data: bytes)`:
  - Reusar la heurística de `_shared.py::_read_excel`: `b"\xd0\xcf\x11\xe0"` (OLE2) → `.xls` con `xlrd`; ZIP (`PK\x03\x04`) → `.xlsx` con `openpyxl` (`read_only=True, data_only=True`). Otro → `ValueError("No es un Excel (.xls/.xlsx) legible")`.
  - Devolver un **contrato uniforme** (`LibroLeido` con `hojas: list[HojaLeida]`, cada una con `nombre` y `filas()` que rinde tuplas de valores), para que mayor/ICT no dependan del engine subyacente.
  - Para `.xls`, respetar los mismos topes de filas/hojas que el camino `.xlsx` (portar de `inventarios_vnr` los límites de hojas/filas).
  - `xlrd` solo lee `.xls` moderno; documentar que `.xls` cifrado o corrupto cae en el `ValueError` claro (no crash).
- [ ] **Step 4: Correr** — `pytest tests/test_ingesta_comun_excel.py -q` verde. (Fixture `.xls`: generar uno pequeño con xlwt o incluir un binario mínimo en `tests/fixtures/`.)
- [ ] **Step 5: Commit** — `feat(ingesta): lector Excel común con .xls legado (xlrd) y contrato uniforme`.

> **Adopción incremental (misma rama, tareas siguientes o PR aparte):** `ict/parsers/*_excel.py` y `mayor/reader.py::leer_mayor` migran su `load_workbook(...)` a `abrir_libro(...)`. Cada migración es un cambio pequeño con su test de regresión (mismo resultado con `.xlsx`, más un caso `.xls`). No hacerlas todas de golpe: una por parser, verde entre cada una.

---

### Task 3: sha256 de cada archivo en el flujo ICT (DATA-008)

**Files:** Modify `ict/models.py`, `ict/service.py`; Create migración; Test `tests/test_ict_ingesta_sha256.py`.

- [ ] **Step 1: Pruebas que fallan**

```python
def test_save_uploaded_file_registra_sha256(db, session):
    up = save_uploaded_file(db, session=session, anexo_code="F103",
                            filename="feb.pdf", data=PDF_BYTES, ...)
    assert up.sha256 == hashlib.sha256(PDF_BYTES).hexdigest()

def test_reparse_conserva_la_huella(db, session):
    # Reprocesar no recalcula distinto ni borra la huella original.
    ...
```

- [ ] **Step 2: Correr y ver que falla** — el modelo de upload no tiene `sha256`.
- [ ] **Step 3: Implementar**:
  - Añadir columna `sha256: str` al modelo de upload del ICT (el que persiste `save_uploaded_file`; si hoy solo escribe a disco sin fila, crear la fila mínima o registrar la huella en el registro de la sesión — inspeccionar `ict/models.py` para elegir el lugar correcto).
  - En `save_uploaded_file(...)`: `sha256 = ingesta_comun.archivos.sha256_archivo(data)` antes de `target.write_bytes(data)`; persistir la huella.
  - En `reparse_session_uploads(...)`: al leer `f.read_bytes()`, conservar/verificar la huella ya registrada (no sobreescribir la original; si difiere, dejar rastro — un archivo en disco no debería cambiar bajo la misma sesión).
- [ ] **Step 4: Migración**: `ADD COLUMN sha256` (nullable), backfill recalculando desde el archivo en disco de los uploads existentes, luego `SET NOT NULL` si aplica.
- [ ] **Step 5: Correr** — `pytest tests/test_ict_ingesta_sha256.py -q` verde; `pytest tests/ -k ict --tb=no -q` sin nuevos fallos frente a la línea base de `CLAUDE.md`.
- [ ] **Step 6: Commit** — `feat(ict): sha256 de cada archivo ingerido para cerrar el lineage`.

---

### Task 4: Perfiles de preparación reutilizables por cliente (DQ-014, DATA-009/010)

**Files:** Create `ingesta_comun/perfiles.py`; modelo/tabla de perfil por cliente; Test `tests/test_ingesta_comun_perfiles.py`.

- [ ] **Step 1: Pruebas que fallan**

```python
def test_perfil_extiende_sinonimos_base():
    base = {"debe": ("debe", "debito"), "haber": ("haber", "credito")}
    perfil = PerfilPreparacion(sinonimos={"debe": ("cargo mes",)})
    fusion = perfil.fusionar(base)
    assert "cargo mes" in fusion["debe"] and "debe" in fusion["debe"]  # extiende, no reemplaza salvo que se pida

def test_perfil_mapeo_fijo_gana_sobre_autodeteccion():
    perfil = PerfilPreparacion(mapeo_fijo={"codigo": 0, "debe": 5, "haber": 6})
    assert perfil.aplicar_a_encabezado([...]) == {"codigo": 0, "debe": 5, "haber": 6}

def test_perfil_roundtrip_json():
    p = PerfilPreparacion(cliente_ruc="1791859596001", sinonimos={"debe": ("cargo",)})
    assert PerfilPreparacion.from_dict(p.to_dict()) == p

def test_sin_perfil_el_comportamiento_no_cambia():
    assert PerfilPreparacion.vacio().fusionar(base) == base
```

- [ ] **Step 2: Correr y ver que falla.**
- [ ] **Step 3: Implementar** `perfiles.py`:
  - `PerfilPreparacion` (dataclass, por `cliente_ruc`): `sinonimos: dict[str, tuple[str,...]]` (overrides que **extienden** los base salvo bandera de reemplazo), `mapeo_fijo: dict[str, int]` (cuando el ERP del cliente tiene un encabezado estable, gana sobre la autodetección), `formato_numero` (`"auto"|"us"|"eu"`, alimenta la heurística `.`/`,` de `CLAUDE.md`), `descartes` (prefijos de fila a ignorar además de los base).
  - `fusionar(sinonimos_base) -> dict`, `aplicar_a_encabezado(celdas) -> dict[str,int]`, `to_dict()`/`from_dict()`.
  - Persistencia: tabla/JSON `perfil_preparacion` por cliente (patrón de `FichaEncargo`: PK por cliente, `datos: JSON`). El perfil se guarda una vez y se reutiliza entre sesiones (DQ-014).
- [ ] **Step 4:** El lector de mayor (`mayor/reader.py::leer_mayor`) acepta `perfil: PerfilPreparacion | None = None`; sin perfil, idéntico a hoy (los tests actuales del mayor no cambian). Con perfil, `_mapear_encabezado` parte de `perfil.fusionar(SINONIMOS)` o del `mapeo_fijo`.
- [ ] **Step 5: Correr** — `pytest tests/test_ingesta_comun_perfiles.py -q` verde; `pytest tests/ -k mayor -q` sin cambios (regresión de "sin perfil no cambia nada").
- [ ] **Step 6: Commit** — `feat(ingesta): perfiles de preparación por cliente que extienden sinónimos y fijan mapeos`.

---

## Criterio de aceptación (P2-G ingesta)

- `checked_zip` vive en `ingesta_comun` y VNR lo consume sin cambio de comportamiento; sus tests siguen verdes.
- `abrir_libro` lee `.xlsx` y `.xls` legado con un contrato uniforme y error claro para no-Excel.
- Todo archivo que entra al flujo ICT queda con su sha256 persistido; reprocesar no altera la huella.
- Un perfil por cliente extiende sinónimos y/o fija el mapeo, se reutiliza entre sesiones, y **sin perfil el comportamiento no cambia** (regresión probada).
- Sin nuevos fallos frente a la lista de tests legacy de `CLAUDE.md`; regla de formatos numéricos `.`/`,` intacta.

## Qué queda para el servidor

Migraciones (`sha256`, tabla de perfiles), fixtures binarios `.xls`, dependencia `xlrd` en `requirements`, endpoints de perfil y la adopción incremental de `abrir_libro` en cada parser: todo se ejecuta y se lleva a verde en el servidor. Aquí solo queda **escrito** — las dependencias (openpyxl/xlrd/SQLAlchemy/DB) no corren en el contenedor de origen. El acople de los perfiles al lector del **motor** (`motor-auditoria-analitica`) se coordina desde el plan de ese repo.
