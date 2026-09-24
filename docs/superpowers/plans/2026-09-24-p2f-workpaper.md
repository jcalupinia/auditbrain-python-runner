# P2-F · Extensiones del papel de trabajo ICT (excepciones, parámetros, conclusión, control, cierre PDF, export BI, sello) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para implementar este plan task-by-task. Los pasos usan checkbox (`- [ ]`) para seguimiento.

**Goal:** que el papel de trabajo del ICT incorpore las 7 salidas que hoy no existe (REP-005/006/007/008/009/011/013): una hoja de EXCEPCIONES del motor con hash/NIA/monto, una de PARÁMETROS del encargo, una de CONCLUSIÓN con firma, una de CONTROL DE REVISIÓN, un informe PDF de cierre, un export tabular a Power BI y un sello inmutable del libro. Todo respetando la separación SRI/papel de trabajo y sin romper las fórmulas referenciales de A1..A9.

**Architecture:** cada salida vive en un archivo NUEVO en `backend/app/ict/` (Agente F, conjunto DISJUNTO del resto). Las 4 hojas (`*_sheet.py`) reciben el `wb` ya cargado y un dict de datos YA calculados por el motor o por las otras hojas; NO recalculan (principio "Python calcula, la presentación no recalcula"). El sello (`sealing.py`) y las excepciones (`exceptions_sheet.py`) consumen el contrato del motor `motor/exportar_excepciones.py` (Agente C, aún inexistente): `especificar_hoja_excepciones(...) -> EspecHojaExcepciones` y `sellar_salida(...) -> SelloSalida`. El PDF de cierre (`pdf_cierre.py`) y el export BI (`export_bi.py`) reúnen esas salidas y las presentan reutilizando el patrón HTML→PDF / CSV-ZIP de `backend/app/aud/niif/procesadores/libro.py`. La integración en `service.generate_excel` / `process_session` se especifica en la sección "Integración" (los cambios a `service.py` los hace el controlador en el servidor, NO este agente).

**Tech Stack:** Python 3.12, openpyxl, WeasyPrint (degradación graciosa), csv/zipfile/hashlib de stdlib, Decimal, pytest, FastAPI/SQLAlchemy. Repo `auditbrain-python-runner`. Las dependencias no corren en el contenedor del scaffold: este plan se ejecuta a verde en el servidor.

**Estado de entrega:** los 7 archivos ya existen como SCAFFOLD tipado (firmas + docstrings + `NotImplementedError`), compilan con `python -m py_compile`. Este plan los lleva a verde.

**Contrato del motor (bloqueante parcial):** `motor/exportar_excepciones.py` lo entrega el Agente C. Mientras no exista, las Tasks 1 y 7 se implementan y prueban contra **fixtures** que imitan `EspecHojaExcepciones` y `SelloSalida` (definidos como `TypedDict` en `exceptions_sheet.py` y `sealing.py`). El cableado real motor→runner es la Task 9.

**Convenciones:** español en comunicación y docstrings; código sigue las convenciones del repo. Importes en `Decimal` (nunca float para dinero). Todo texto libre a Excel pasa por `source_data_sheets._safe_text`. Ninguna hoja generada puede levantar el cuadro "Excel pudo abrir el archivo reparando…". `python -m pytest tests/ -k ict -q` desde la raíz.

**Verificación empírica de referencia (CLAUDE.md, REGLA SUPREMA):** PROPHAR S.A. (RUC 1791859596001, 2025). Antes de decir "listo": generar el Excel real, abrirlo en Excel y confirmar (a) que NO pide reparación, (b) que las hojas nuevas se ven profesionales, (c) que en el archivo SRI las hojas nuevas quedan OCULTAS y las fórmulas A1..A9 siguen resolviendo (sin `#REF!`).

---

## Estructura de archivos

| Archivo | Estado | Responsabilidad | REP |
|---|---|---|---|
| `backend/app/ict/exceptions_sheet.py` | scaffold ✔ | Hoja "EXCEPCIONES" (hash/NIA/monto) desde la spec del motor | REP-006 |
| `backend/app/ict/parametros_sheet.py` | scaffold ✔ | Hoja "PARÁMETROS" (bloque U del encargo) | REP-005 |
| `backend/app/ict/conclusion_sheet.py` | scaffold ✔ | Hoja "CONCLUSIÓN" (síntesis validada + firma; disclaimer IA) | REP-007 |
| `backend/app/ict/review_control_sheet.py` | scaffold ✔ | Hoja "CONTROL DE REVISIÓN" (preparó/revisó/fecha/estado) | REP-008 |
| `backend/app/ict/pdf_cierre.py` | scaffold ✔ | Informe PDF de cierre (HTML autónomo → WeasyPrint) | REP-009 |
| `backend/app/ict/export_bi.py` | scaffold ✔ | Export tabular/CSV (esquema estrella) para Power BI | REP-011 |
| `backend/app/ict/sealing.py` | scaffold ✔ | Sello inmutable (version+timestamp+hash) del motor al libro | REP-013 |
| `backend/app/ict/service.py` | **NO tocar aquí** | Puntos de integración (sección Integración; los aplica el controlador) | — |
| `tests/test_ict_exceptions_sheet.py` … `test_ict_sealing.py` | crear | Pruebas por salida | — |

---

### Task 1: Hoja EXCEPCIONES (REP-006)

**Files:**
- Modify: `backend/app/ict/exceptions_sheet.py`
- Test: `tests/test_ict_exceptions_sheet.py`

- [ ] **Step 1: Pruebas que fallan** — `tests/test_ict_exceptions_sheet.py`

```python
"""Hoja EXCEPCIONES del papel de trabajo ICT (P2-F, REP-006)."""
import io
from openpyxl import Workbook, load_workbook

from backend.app.ict.exceptions_sheet import (
    SHEET_NAME, build_exceptions_sheet,
)

ESPEC = {
    "titulo": "Excepciones detectadas",
    "columnas": [
        {"clave": "hash", "titulo": "Hash", "tipo": "hash"},
        {"clave": "anexo", "titulo": "Anexo", "tipo": "texto"},
        {"clave": "nia", "titulo": "NIA", "tipo": "nia"},
        {"clave": "monto", "titulo": "Monto", "tipo": "monto"},
        {"clave": "severidad", "titulo": "Severidad", "tipo": "severidad"},
        {"clave": "mensaje", "titulo": "Detalle", "tipo": "texto"},
    ],
    "filas": [
        {"hash": "a1b2c3d4", "anexo": "A5", "nia": "NIA 240",
         "monto": "12500.00", "severidad": "P0", "mensaje": "Gasto no deducible"},
        {"hash": "e5f6a7b8", "anexo": "A2", "nia": "NIA 500",
         "monto": "800.00", "severidad": "P2", "mensaje": "=OJO diferencia"},
    ],
    "resumen": {"total_excepciones": 2, "monto_total": "13300.00",
                "por_severidad": {"P0": 1, "P2": 1},
                "monto_por_severidad": {"P0": "12500.00", "P2": "800.00"}},
    "engine_version": "motor-1.4.0", "generado_en": "2026-09-24T10:00:00Z",
    "run_id": "run_123",
}
SESSION = {"razon_social": "PROPHAR S.A.", "ruc": "1791859596001",
           "ejercicio_fiscal": "2025"}


def _roundtrip(wb):
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return load_workbook(buf)


def test_crea_hoja_con_una_fila_por_excepcion():
    wb = Workbook()
    r = build_exceptions_sheet(wb, ESPEC, session_data=SESSION)
    assert r.filas_escritas == 2
    assert SHEET_NAME in wb.sheetnames
    wb2 = _roundtrip(wb)  # no debe corromperse (regla "sin reparación")
    assert SHEET_NAME in wb2.sheetnames


def test_fila_total_desde_el_resumen():
    wb = Workbook()
    r = build_exceptions_sheet(wb, ESPEC, session_data=SESSION)
    assert r.monto_total == "13300.00"
    assert r.por_severidad == {"P0": 1, "P2": 1}


def test_texto_que_parece_formula_se_escapa():
    """La celda mensaje "=OJO diferencia" NO debe quedar como fórmula."""
    wb = Workbook()
    build_exceptions_sheet(wb, ESPEC, session_data=SESSION)
    ws = wb[SHEET_NAME]
    valores = [c.value for row in ws.iter_rows() for c in row
               if isinstance(c.value, str) and "OJO" in c.value]
    assert valores and all(not v.startswith("=") or v.startswith("'=") is False
                           for v in valores)
    # criterio real: ninguna celda tiene data_type "f" con ese texto
    formulas = [c.value for row in ws.iter_rows() for c in row
                if getattr(c, "data_type", None) == "f"]
    assert not any("OJO" in str(f) for f in formulas)


def test_espec_vacia_genera_hoja_con_mensaje():
    wb = Workbook()
    vacia = {**ESPEC, "filas": [], "resumen": {"total_excepciones": 0,
             "monto_total": "0.00", "por_severidad": {}}}
    r = build_exceptions_sheet(wb, vacia, session_data=SESSION)
    assert r.filas_escritas == 0 and SHEET_NAME in wb.sheetnames


def test_montos_son_numericos_no_texto():
    wb = Workbook()
    build_exceptions_sheet(wb, ESPEC, session_data=SESSION)
    ws = wb[SHEET_NAME]
    # la columna monto debe escribirse como número (float/Decimal), no str
    numeros = [c.value for row in ws.iter_rows() for c in row
               if isinstance(c.value, (int, float)) and float(c.value) == 12500.0]
    assert numeros
```

- [ ] **Step 2: Correr y ver que falla** — `python -m pytest tests/test_ict_exceptions_sheet.py -q` → `NotImplementedError`.

- [ ] **Step 3: Implementar** `build_exceptions_sheet` + `_write_header` + `_write_total_row`:
  - reutilizar estilos de `source_data_sheets` (`_safe_text`, `_write_title`, `_write_header`, `FONT_*`, `FILL_*`, `BORDER`) y los helpers de `formatting.py` (`apply_column_widths`, `safe_apply_style`).
  - crear/reemplazar la hoja; cabecera de marca + encargo; encabezados desde `columnas`; una fila por `filas` mapeando por `tipo` (monto→`Decimal(str)`+`#,##0.00`+derecha; hash→monoespaciada+`_safe_text`; severidad→color P0 rojo/P1 naranja/P2 amarillo; texto→`_safe_text`).
  - fila TOTAL desde `resumen` (negrita, borde doble, fondo azul claro).
  - `AutoFilter` + `freeze_panes` sobre la tabla; anchos explícitos.
  - registrar escrituras clave con `base.safe_set` (para que TRAZABILIDAD las tome).
  - devolver `ExceptionsSheetResult`.

- [ ] **Step 4: Correr pruebas** — `python -m pytest tests/test_ict_exceptions_sheet.py -q` → 5 passed.

- [ ] **Step 5: Commit** — `git add backend/app/ict/exceptions_sheet.py tests/test_ict_exceptions_sheet.py && git commit -m "feat(ict): hoja EXCEPCIONES del papel de trabajo (REP-006)"`

---

### Task 2: Hoja PARÁMETROS (REP-005)

**Files:**
- Modify: `backend/app/ict/parametros_sheet.py`
- Test: `tests/test_ict_parametros_sheet.py`

- [ ] **Step 1: Pruebas que fallan**

```python
"""Hoja PARÁMETROS del papel de trabajo ICT (P2-F, REP-005)."""
import io
from openpyxl import Workbook, load_workbook
from backend.app.ict.parametros_sheet import SHEET_NAME, build_parametros_sheet

PARAMS = {
    "ejercicio_inicio": "2025-01-01", "ejercicio_fin": "2025-12-31",
    "materialidad": "50000.00", "materialidad_ejecucion": "37500.00",
    "umbral_insignificante": "2500.00", "umbral_aprobacion": "5000.00",
    "error_tolerable": "37500.00", "feriados": ["2025-05-01", "2025-08-10"],
    "hora_inicio": 8, "hora_fin": 18, "confianza": 95, "semilla": 20250101,
    "fecha_registro_es_contable": False,
}
SESSION = {"razon_social": "PROPHAR S.A.", "ruc": "1791859596001", "ejercicio_fiscal": "2025"}


def test_escribe_los_parametros_presentes():
    wb = Workbook()
    r = build_parametros_sheet(wb, PARAMS, session_data=SESSION)
    assert r.parametros_escritos == 13 and SHEET_NAME in wb.sheetnames


def test_materialidad_es_numerica_con_formato():
    wb = Workbook()
    build_parametros_sheet(wb, PARAMS, session_data=SESSION)
    ws = wb[SHEET_NAME]
    montos = [c for row in ws.iter_rows() for c in row
              if isinstance(c.value, (int, float)) and float(c.value) == 50000.0]
    assert montos and montos[0].number_format == "#,##0.00"


def test_parametro_faltante_no_rompe_y_advierte():
    wb = Workbook()
    incompletos = {k: v for k, v in PARAMS.items() if k != "semilla"}
    r = build_parametros_sheet(wb, incompletos, session_data=SESSION)
    assert any("semilla" in a for a in r.advertencias)
    assert SHEET_NAME in wb.sheetnames


def test_no_corrompe_el_libro():
    wb = Workbook()
    build_parametros_sheet(wb, PARAMS, session_data=SESSION)
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    assert SHEET_NAME in load_workbook(buf).sheetnames
```

- [ ] **Step 2: Correr y ver que falla** — `NotImplementedError`.
- [ ] **Step 3: Implementar** recorriendo `PARAMETROS_LAYOUT`; formatear por tipo (monto/fecha/lista_fechas/entero/booleano); "(no informado)" + advertencia si falta; anchos + bordes + trace.
- [ ] **Step 4: Correr pruebas** — 4 passed.
- [ ] **Step 5: Commit** — `feat(ict): hoja PARÁMETROS del encargo (REP-005)`.

---

### Task 3: Hoja CONCLUSIÓN (REP-007)

**Files:**
- Modify: `backend/app/ict/conclusion_sheet.py`
- Test: `tests/test_ict_conclusion_sheet.py`

- [ ] **Step 1: Pruebas que fallan** — cubrir: (a) se escribe la síntesis; (b) el bloque de firma trae rótulos Preparó/Revisó/Fecha con celdas vacías; (c) si `interpretacion.confianza_modelo == "baja"` aparece "Revisar manualmente" y el disclaimer `DISCLAIMER_IA`; (d) si NO hay `interpretacion`, NO se escribe disclaimer; (e) roundtrip sin corromper.

```python
from backend.app.ict.conclusion_sheet import (
    SHEET_NAME, DISCLAIMER_IA, build_conclusion_sheet,
)

CTX = {"sintesis": "El ejercicio cuadra; 2 excepciones P0.",
       "total_excepciones": 2, "monto_total_excepciones": "13300.00",
       "cuadra_a1": True, "suficiencia_estado": "Parcial",
       "reglas_no_corridas": ["AST-001", "AST-002"]}


def test_escribe_sintesis_y_firma_en_blanco():
    from openpyxl import Workbook
    wb = Workbook()
    build_conclusion_sheet(wb, CTX, session_data={"ruc": "1791859596001"})
    ws = wb[SHEET_NAME]
    textos = [str(c.value) for row in ws.iter_rows() for c in row if c.value]
    assert any("Preparó" in t for t in textos) and any("Revisó" in t for t in textos)


def test_disclaimer_ia_cuando_la_sintesis_es_ia():
    from openpyxl import Workbook
    wb = Workbook()
    ctx = {**CTX, "interpretacion": {"sintesis": CTX["sintesis"],
           "confianza_modelo": "baja", "requiere_revision_humana": True}}
    r = build_conclusion_sheet(wb, ctx)
    assert r.tiene_disclaimer_ia and r.confianza_modelo == "baja"
    textos = [str(c.value) for row in wb[SHEET_NAME].iter_rows() for c in row if c.value]
    assert any(DISCLAIMER_IA[:20] in t for t in textos)
    assert any("Revisar manualmente" in t for t in textos)


def test_sin_ia_no_hay_disclaimer():
    from openpyxl import Workbook
    wb = Workbook()
    r = build_conclusion_sheet(wb, CTX)
    assert not r.tiene_disclaimer_ia
```

- [ ] **Step 2: Correr y ver que falla** — `NotImplementedError`.
- [ ] **Step 3: Implementar** los 6 controles de IA de CLAUDE.md en `_render_disclaimer_ia` (disclaimer Calibri 8 italic #6B7280; borde rojo + "Revisar manualmente" si confianza baja; ícono si `requiere_revision_humana`). Firma en blanco en `_render_firma`.
- [ ] **Step 4: Correr pruebas** — 3 passed.
- [ ] **Step 5: Commit** — `feat(ict): hoja CONCLUSIÓN con firma y disclaimer IA (REP-007)`.

---

### Task 4: Hoja CONTROL DE REVISIÓN (REP-008)

**Files:**
- Modify: `backend/app/ict/review_control_sheet.py`
- Test: `tests/test_ict_review_control_sheet.py`

- [ ] **Step 1: Pruebas que fallan** — (a) una fila por evento en orden; (b) `estado_final` = último `estado_nuevo`; (c) lista vacía → fila "Sin eventos…"; (d) fechas como datetime con `number_format` `yyyy-mm-dd hh:mm`; (e) roundtrip.

```python
from openpyxl import Workbook
from backend.app.ict.review_control_sheet import SHEET_NAME, build_review_control_sheet

EVENTOS = [
    {"fecha": "2026-09-20T09:00:00", "accion": "preparó", "estado_anterior": "borrador",
     "estado_nuevo": "en_revision", "actor": "J. Calderón", "comentario": "v1"},
    {"fecha": "2026-09-22T15:30:00", "accion": "aprobó", "estado_anterior": "en_revision",
     "estado_nuevo": "aprobado", "actor": "Socio", "comentario": "OK"},
]


def test_una_fila_por_evento_y_estado_final():
    wb = Workbook()
    r = build_review_control_sheet(wb, EVENTOS)
    assert r.eventos_escritos == 2 and r.estado_final == "aprobado"


def test_lista_vacia_escribe_placeholder():
    wb = Workbook()
    r = build_review_control_sheet(wb, [])
    assert r.eventos_escritos == 0 and SHEET_NAME in wb.sheetnames
```

- [ ] **Step 2: Correr y ver que falla** — `NotImplementedError`.
- [ ] **Step 3: Implementar** con las `COLUMNAS`; resaltar estado final (verde/rojo/ámbar); `_safe_text`; freeze panes; trace.
- [ ] **Step 4: Correr pruebas** — 2+ passed.
- [ ] **Step 5: Commit** — `feat(ict): hoja CONTROL DE REVISIÓN (REP-008)`.

---

### Task 5: Informe PDF de cierre (REP-009)

**Files:**
- Modify: `backend/app/ict/pdf_cierre.py`
- Test: `tests/test_ict_pdf_cierre.py`

- [ ] **Step 1: Pruebas que fallan** — (a) `build_cierre_html` devuelve bytes con `<!doctype html>`, marca "AuditConsulting", los KPIs y el texto de la síntesis; (b) sin recursos externos (`assert b"http://" not in out and b"https://" not in out` salvo dentro de textos escapados — mejor: `assert b"<link" not in out and b"cdn" not in out`); (c) `para_pdf=True` no incluye `<script`; (d) `build_cierre_pdf` levanta `PDFCierreNoDisponible` cuando WeasyPrint no está (monkeypatch del import) o devuelve bytes `%PDF` cuando sí.

```python
from backend.app.ict.pdf_cierre import (
    build_cierre_html, build_cierre_pdf, PDFCierreNoDisponible,
)

CTX = {"session_data": {"razon_social": "PROPHAR S.A.", "ruc": "1791859596001",
        "ejercicio_fiscal": "2025"}, "sintesis": "Cierre sin salvedades.",
       "excepciones": {"filas": [], "resumen": {"total_excepciones": 0,
        "monto_total": "0.00"}, "columnas": []},
       "parametros": {"materialidad": "50000.00"},
       "sello": {"version_app": "1.0", "timestamp": "2026-09-24T10:00:00Z",
                 "hash_salida": "abcd1234"},
       "cuadra_a1": True, "suficiencia_estado": "Parcial"}


def test_html_autonomo_sin_recursos_externos():
    out = build_cierre_html(CTX)
    assert out.startswith(b"<!doctype html")
    assert b"AuditConsulting" in out
    assert b"<link" not in out and b"cdn" not in out.lower()


def test_para_pdf_no_lleva_javascript():
    assert b"<script" not in build_cierre_html(CTX, para_pdf=True)


def test_pdf_degradado_si_no_hay_weasyprint(monkeypatch):
    import builtins, pytest
    real = builtins.__import__
    def fake(name, *a, **k):
        if name == "weasyprint":
            raise ImportError("sin weasyprint")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(PDFCierreNoDisponible):
        build_cierre_pdf(CTX)
```

- [ ] **Step 2: Correr y ver que falla** — `NotImplementedError`.
- [ ] **Step 3: Implementar** copiando el andamiaje de `libro.html`/`libro.pdf` (CSS embebido, `@page landscape`, KPIs, secciones excepciones/parámetros/sello, `html.escape`), con las constantes de marca locales del scaffold. `build_cierre_pdf`: try/except del import y `PDFCierreNoDisponible`.
- [ ] **Step 4: Correr pruebas** — passed (el test de PDF real se salta si no hay WeasyPrint, como `libro`).
- [ ] **Step 5: Commit** — `feat(ict): informe PDF de cierre HTML->PDF (REP-009)`.

---

### Task 6: Export tabular para Power BI (REP-011)

**Files:**
- Modify: `backend/app/ict/export_bi.py`
- Test: `tests/test_ict_export_bi.py`

- [ ] **Step 1: Pruebas que fallan** — (a) `build_bi_dataset` devuelve las 5 `TABLAS`; (b) `hechos_excepciones` tiene una fila por excepción; (c) `export_bi_csv_zip` devuelve un ZIP con 5 `.csv`, cada uno UTF-8 BOM y separador `;`; (d) los montos van con punto decimal sin separador de miles.

```python
import io, zipfile
from backend.app.ict.export_bi import TABLAS, build_bi_dataset, export_bi_csv_zip

CTX = {"session_data": {"razon_social": "PROPHAR S.A.", "ruc": "1791859596001",
        "ejercicio_fiscal": "2025"},
       "excepciones": {"columnas": [{"clave": "monto", "titulo": "Monto", "tipo": "monto"}],
        "filas": [{"hash": "a1", "anexo": "A5", "severidad": "P0", "monto": "12500.00",
                   "nia": "NIA 240", "mensaje": "x"}],
        "resumen": {"total_excepciones": 1, "monto_total": "12500.00"}, "run_id": "run_1"},
       "parametros": {"materialidad": "50000.00"},
       "sello": {"version_app": "1.0", "hash_salida": "abcd"}}


def test_dataset_tiene_las_cinco_tablas():
    ds = build_bi_dataset(CTX)
    assert {t.nombre for t in ds.tablas} == set(TABLAS)
    assert len(ds.por_nombre("hechos_excepciones").filas) == 1


def test_zip_trae_cinco_csv_con_bom_y_puntoycoma():
    data = export_bi_csv_zip(CTX)
    z = zipfile.ZipFile(io.BytesIO(data))
    nombres = set(z.namelist())
    assert nombres == {f"{t}.csv" for t in TABLAS}
    hechos = z.read("hechos_excepciones.csv")
    assert hechos.startswith(b"\xef\xbb\xbf")   # BOM
    assert b";" in hechos and b"12500.00" in hechos  # punto decimal
```

- [ ] **Step 2: Correr y ver que falla** — `NotImplementedError`.
- [ ] **Step 3: Implementar** `build_bi_dataset` (esquema estrella) y `export_bi_csv_zip` (patrón `libro.csv_zip`, BOM + `;`).
- [ ] **Step 4: Correr pruebas** — 2 passed.
- [ ] **Step 5: Commit** — `feat(ict): export tabular/CSV para Power BI (REP-011)`.

---

### Task 7: Sello inmutable del libro (REP-013)

**Files:**
- Modify: `backend/app/ict/sealing.py`
- Test: `tests/test_ict_sealing.py`

- [ ] **Step 1: Pruebas que fallan** — (a) `apply_seal` crea la hoja "SELLO" con version/timestamp/hash_salida/run_id y una fila por `input_hashes`; (b) escribe el sello también en `wb.properties`; (c) `hash_workbook_bytes` es determinista (mismos bytes → mismo hash; hex de 64 chars para sha256); (d) `verify_seal` True cuando coincide, False cuando no; (e) roundtrip sin corromper.

```python
import io
from openpyxl import Workbook, load_workbook
from backend.app.ict.sealing import (
    SHEET_NAME, apply_seal, hash_workbook_bytes, verify_seal,
)

SELLO = {"version_app": "1.0.0", "version_motor": "motor-1.4.0",
         "timestamp": "2026-09-24T10:00:00Z", "hash_salida": "deadbeef",
         "algoritmo": "sha256", "run_id": "run_123",
         "input_hashes": {"F-101": "aaa", "F-103": "bbb"}}


def test_apply_seal_crea_hoja_y_propiedades():
    wb = Workbook()
    apply_seal(wb, SELLO, session_data={"ruc": "1791859596001"})
    assert SHEET_NAME in wb.sheetnames
    textos = [str(c.value) for row in wb[SHEET_NAME].iter_rows() for c in row if c.value]
    assert any("deadbeef" in t for t in textos)
    assert any("F-101" in t for t in textos)


def test_hash_workbook_es_determinista():
    wb = Workbook(); buf = io.BytesIO(); wb.save(buf); data = buf.getvalue()
    h1, h2 = hash_workbook_bytes(data), hash_workbook_bytes(data)
    assert h1 == h2 and len(h1) == 64


def test_verify_seal_detecta_discrepancia():
    wb = Workbook(); apply_seal(wb, SELLO)
    assert verify_seal(wb, SELLO) is True
    assert verify_seal(wb, {**SELLO, "hash_salida": "otro"}) is False


def test_roundtrip_conserva_el_sello():
    wb = Workbook(); apply_seal(wb, SELLO)
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    assert SHEET_NAME in load_workbook(buf).sheetnames
```

- [ ] **Step 2: Correr y ver que falla** — `NotImplementedError`.
- [ ] **Step 3: Implementar** `apply_seal` (hoja "SELLO" + `wb.properties`), `hash_workbook_bytes` (= `hashlib.new(algoritmo, wb_bytes).hexdigest()`), `verify_seal`. Respetar la NOTA DE CIRCULARIDAD del scaffold: NO embeber el hash del propio .xlsx.
- [ ] **Step 4: Correr pruebas** — 4 passed.
- [ ] **Step 5: Commit** — `feat(ict): sello inmutable del libro (REP-013)`.

---

### Task 8: Integración en `service.py` (la aplica el controlador en el servidor)

> Este agente NO modifica `service.py`. Aquí se especifica EXACTAMENTE qué cambiar, dónde y por qué, sin romper la separación SRI/papel de trabajo ni las fórmulas referenciales.

**Files:**
- Modify: `backend/app/ict/service.py`
- Test: `tests/test_ict_service_split.py` (ampliar), `tests/test_ict_workpaper_integration.py` (crear)

**8.1 — Ocultar las hojas nuevas en el archivo SRI.** Las 5 hojas nuevas (`EXCEPCIONES`, `PARÁMETROS`, `CONCLUSIÓN`, `CONTROL DE REVISIÓN`, `SELLO`) son papel de trabajo del auditor: NO forman parte del formato oficial del SRI (INDICE + A1..A9). Agregarlas a `HIDDEN_SHEETS_FOR_SRI` para que **se oculten, no se borren** (siguen la misma regla que DATOS/VERIFICACIÓN):

```python
HIDDEN_SHEETS_FOR_SRI: tuple[str, ...] = (
    "DATOS F-101", "DATOS F-103", "DATOS F-104", "DATOS BALANCE",
    "VERIFICACIÓN A1", "TRAZABILIDAD",
    # P2-F (REP-005..013): papel de trabajo del auditor, ocultas en SRI
    "EXCEPCIONES", "PARÁMETROS", "CONCLUSIÓN", "CONTROL DE REVISIÓN", "SELLO",
)
```

Actualizar el test `test_hidden_sheets_constant_lists_datos_and_internal_sheets` para incluirlas. Como estas hojas NO las referencian fórmulas de A1..A9 (a diferencia de DATOS), ocultarlas o incluso borrarlas no rompería fórmulas; se OCULTAN igual por consistencia con la regla y para no re-introducir `del wb[hoja]`.

**8.2 — Punto de inserción dentro de `generate_excel`.** Insertar el bloque DESPUÉS de `build_verification_sheet` y ANTES de `write_trace_sheet` (para que las escrituras de estas hojas entren al trace, y para que el sello sea de lo último). Es decir, entre la línea `logging.exception("build_verification_sheet falló…")`/su `except` y `write_trace_sheet(wb)`:

```python
    # === P2-F · Extensiones del papel de trabajo (REP-005..013) ===
    # Solo se generan si el motor entregó su salida en el shared_context bajo
    # las claves "_motor_excepciones" / "_motor_sello" / "_parametros_encargo".
    # Si no vienen (sesión sin corrida del motor), se OMITEN silenciosamente:
    # el ICT clásico sigue generándose igual (no regresión).
    try:
        from backend.app.ict.exceptions_sheet import build_exceptions_sheet
        from backend.app.ict.parametros_sheet import build_parametros_sheet
        from backend.app.ict.conclusion_sheet import build_conclusion_sheet
        from backend.app.ict.review_control_sheet import build_review_control_sheet
        from backend.app.ict.sealing import apply_seal

        espec_exc = shared_context.get("_motor_excepciones")
        if espec_exc:
            build_exceptions_sheet(wb, espec_exc, session_data=session_data)
        params = shared_context.get("_parametros_encargo")
        if params:
            build_parametros_sheet(wb, params, session_data=session_data)
        concl = shared_context.get("_conclusion_contexto")
        if concl:
            build_conclusion_sheet(wb, concl, session_data=session_data)
        eventos = shared_context.get("_eventos_revision")
        if eventos is not None:
            build_review_control_sheet(wb, eventos, session_data=session_data)
        sello = shared_context.get("_motor_sello")
        if sello:
            apply_seal(wb, sello, session_data=session_data)   # SIEMPRE el último
    except Exception:
        import logging
        logging.exception("P2-F workpaper extensions fallaron para sesión %s", session.id)
```

Motivos:
- **No romper el orden de serialización.** El bloque va antes de guardar el papel de trabajo (`wb.save(buf_papel)`) y antes de `_apply_sri_sheet_visibility(wb)`, de modo que ambas copias (papel y SRI) contengan las hojas; la copia SRI luego las oculta vía 8.1.
- **`apply_seal` de último** entre los fillers para que el sello refleje el libro ya armado (aunque el hash del sello es de la SALIDA del motor, no de los bytes; ver 8.4).
- **Degradación graciosa**: si el motor no corrió, las claves no están y no se genera ninguna hoja nueva → el ICT actual no cambia (test de no-regresión).

**8.3 — De dónde salen los datos del motor (`shared_context`).** El motor (`motor/exportar_excepciones.py`, Agente C) y la capa de ejecución (`backend/app/execution/`, Agente D) producen `EspecHojaExcepciones` y `SelloSalida`. La ruta más limpia, sin tocar los fillers, es que `process_session` (u otro orquestador de servidor) inyecte estas claves en el `extracted_data` de un anexo (o en un registro de corrida) para que `generate_excel` las lea en el `shared_context` que ya construye en su bucle. Alternativa: pasar un parámetro `motor_output: dict | None = None` a `generate_excel` (cambio de firma retrocompatible con default `None`). Decidir en 8.5.

**8.4 — Hash del .xlsx final (fuera del libro).** En `process_session`, tras `bytes_sri, bytes_papel = generate_excel(...)` y antes de escribir a disco, calcular `hash_workbook_bytes(bytes_papel)` y registrarlo en el `ExecutionRun.output_hashes` / bitácora (NO dentro del libro). Esto cierra el lineado REP-013 sin circularidad.

**8.5 — Endpoints nuevos (opcional, fuera del split Excel).** Para REP-009 (PDF de cierre) y REP-011 (export BI), agregar dos endpoints en `router.py` espejo de `/papel-trabajo`:
- `GET /sessions/{id}/cierre-pdf` → `pdf_cierre.build_cierre_pdf(ctx)`; captar `PDFCierreNoDisponible` y responder 200 con aviso + link al HTML (igual criterio que NIIF), no 500.
- `GET /sessions/{id}/export-bi` → `export_bi.export_bi_csv_zip(ctx)` con `media_type="application/zip"`.
Ambos reúnen el `ctx` desde la corrida del motor cacheada de la sesión.

- [ ] **Step 1..5 (servidor):** ampliar `test_ict_service_split.py` (constante + oculta/no borra + activa visible sigue INDICE), crear `test_ict_workpaper_integration.py` (con motor_output presente → 5 hojas nuevas en papel y ocultas en SRI; sin motor_output → ICT idéntico al actual), correr `pytest -k ict`, commit.

---

### Task 9: Cableado real motor → runner (cuando exista `motor/exportar_excepciones.py`)

**Depende de:** Agente C (motor) + Agente D (execution engine).

- [ ] Reemplazar los fixtures de las Tasks 1 y 7 por la salida real de `motor.exportar_excepciones.especificar_hoja_excepciones` y `sellar_salida`.
- [ ] Verificar que los `TypedDict` (`EspecHojaExcepciones`, `SelloSalida`) coinciden campo a campo con lo que el motor emite; si el motor difiere, ajustar los `TypedDict` del runner (son el borde del contrato), NO inventar campos en las hojas.
- [ ] Prueba de contrato: `tests/test_ict_contrato_motor.py` importa del motor (si está instalado) y valida que un `ExecutionRun` real produce hojas sin error.

---

### Task 10: Verificación empírica y cierre (lo hace el controlador)

- [ ] **Empírica PROPHAR** (CLAUDE.md, REGLA SUPREMA): cargar F-101/F-103/F-104 reales, correr el motor, generar el Excel, ABRIRLO en Excel real y confirmar: (a) NO pide reparación; (b) las 5 hojas nuevas se ven profesionales; (c) en el SRI están OCULTAS y A1..A9 no muestran `#REF!`; (d) el sello y el hash del .xlsx quedan registrados.
- [ ] `security-review` de la rama (entra la salida del motor y se genera PDF/ZIP).
- [ ] `git push` + `gh pr create` hacia la rama de integración P2.
- [ ] Desplegar en Render con las dependencias (WeasyPrint nativo para el PDF; si falta, degrada a HTML "Guardar como PDF").

---

## Integración — resumen de puntos de contacto en `service.py`

| Qué | Dónde en `service.py` | Cómo | Riesgo evitado |
|---|---|---|---|
| Ocultar hojas nuevas en SRI | `HIDDEN_SHEETS_FOR_SRI` (línea ~423) | agregar los 5 nombres | portal SRI solo quiere INDICE+A1..A9; se OCULTAN, no se borran |
| Generar las 4 hojas + sello | `generate_excel`, entre `build_verification_sheet` y `write_trace_sheet` (línea ~690) | bloque try/except leyendo `shared_context` | entra al trace; ambas copias las traen antes del split |
| Datos del motor | `shared_context` (línea ~587) o nuevo `motor_output=None` en la firma | inyectar `_motor_excepciones/_motor_sello/...` | sin motor → ICT idéntico (no regresión) |
| Hash del .xlsx final | `process_session`, tras `generate_excel` (línea ~873) | `hash_workbook_bytes(bytes_papel)` → ExecutionRun/bitácora | sin circularidad (no se embebe en el libro) |
| PDF cierre / export BI | `router.py` | 2 endpoints espejo de `/papel-trabajo` | `PDFCierreNoDisponible` → aviso, no 500 |

**Invariantes que NO se pueden romper (tests que deben seguir verdes):**
- `test_ict_service_split.py::test_sri_hides_but_never_deletes_sheets` — jamás `del wb[hoja]` para hojas referenciadas.
- `test_ict_service_split.py::test_sri_active_sheet_is_visible_indice` — la hoja activa del SRI sigue siendo INDICE visible.
- `test_ict_a1_no_saldos_de_linea.py`, `test_ict_a1_totales_regla.py` — las fórmulas de A1 no cambian.
- El archivo SRI NO levanta el cuadro "Reparaciones".

## Qué queda para el servidor (no ejecutable en este contenedor)

1. **Implementar los 7 scaffolds a verde** (Tasks 1-7): requieren openpyxl y, para el PDF, WeasyPrint. Aquí solo compilan (`py_compile`); `pytest` corre en el servidor.
2. **Los cambios a `service.py`/`router.py`** (Task 8): los aplica el controlador; este agente solo los especifica.
3. **El contrato real del motor** (Task 9): bloqueado hasta que Agente C entregue `motor/exportar_excepciones.py`. Hasta entonces, fixtures.
4. **Verificación empírica PROPHAR y despliegue** (Task 10): requiere datos de cliente y entorno Render con dependencias nativas.
5. **`ANTHROPIC_API_KEY`/`ICT_LLM_MODEL`** si la síntesis de CONCLUSIÓN se genera por IA (controles 1-6 de CLAUDE.md); sin la key, la síntesis debe venir del auditor (texto libre) y la hoja se genera igual sin disclaimer IA.
