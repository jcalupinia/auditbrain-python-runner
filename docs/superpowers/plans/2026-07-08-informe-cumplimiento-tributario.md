# Informe de Cumplimiento Tributario — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nueva herramienta del módulo AUD (etapa "Conclusión y dictamen") que genera el *Informe de los Auditores Independientes sobre el Cumplimiento de Obligaciones Tributarias* rellenando una de dos plantillas Word (AuditConsulting / Partner) con datos de cabecera manuales + valores extraídos de 2 PDFs (Informe de Auditoría Externa y F-101).

**Architecture:** Clon del patrón `AUD.IMPUESTOS.OBLIGACIONES_FISCALES` (`backend/app/aud/obligaciones_fiscales/`): job async (BackgroundTask) con `ToolJob` reutilizado (nuevo `tool_code`, sin migración), storage efímero reutilizado, y un **ensamblador Word con `docxtpl`** en vez de Excel. Salida: `.docx` lleno.

**Tech Stack:** FastAPI, SQLAlchemy (`ToolJob` existente), `pdfplumber` (parsers), `docxtpl` + `python-docx` (plantillas Word), React (frontend módulo AUD), pytest + TestClient.

**Spec:** `docs/superpowers/specs/2026-07-08-informe-cumplimiento-tributario-design.md`

---

## Convenciones y constantes compartidas

- **Tool code:** `AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO`
- **Prefijo router:** `/aud/informe-cumplimiento-tributario`
- **Firmas válidas:** `"audit_consulting"`, `"partner_auditing"` (mismas que OF)
- **Módulo backend:** `backend/app/aud/informe_cumplimiento_tributario/`
- **Storage:** se **reutiliza** `backend/app/aud/obligaciones_fiscales/file_storage.py`
  (job_dir por id, save_input, list_inputs, delete_job_dir, orphans). Output =
  `job_dir/output.docx`. El `cleanup_once` existente ya cubre estos jobs (consulta
  `ToolJob` por `expires_at`/`status`, agnóstico al tool_code).
- **Fixtures reales:** `tests/fixtures/informe_cumplimiento_tributario/`
  (`informe_auditoria_externa_axxis.pdf`, `f101_axxis.pdf`,
  `reporte_diferencias_axxis.pdf`).

---

## Task 1: Helpers de formato (fechas ES + marco contable)

**Files:**
- Create: `backend/app/aud/informe_cumplimiento_tributario/__init__.py` (vacío)
- Create: `backend/app/aud/informe_cumplimiento_tributario/helpers.py`
- Test: `tests/test_ict_report_helpers.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ict_report_helpers.py
from backend.app.aud.informe_cumplimiento_tributario import helpers


def test_fecha_larga_from_ddmmyyyy():
    assert helpers.fecha_larga_from_ddmmyyyy("09-04-2026") == "09 de abril de 2026"
    assert helpers.fecha_larga_from_ddmmyyyy("31-12-2025") == "31 de diciembre de 2025"


def test_fecha_larga_invalid_returns_none():
    assert helpers.fecha_larga_from_ddmmyyyy("99-99-2026") is None
    assert helpers.fecha_larga_from_ddmmyyyy("basura") is None


def test_normaliza_del():
    assert helpers.normaliza_del("27 de febrero del 2026") == "27 de febrero de 2026"
    assert helpers.normaliza_del("15 de marzo de 2026") == "15 de marzo de 2026"


def test_marco_phrase():
    assert "PYMES" in helpers.marco_phrase("pymes")
    assert helpers.marco_phrase("plenas") == \
        "Normas Internacionales de Información Financiera – NIIF"
    # default seguro
    assert "PYMES" in helpers.marco_phrase("desconocido")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_report_helpers.py -v`
Expected: FAIL con `ModuleNotFoundError: ... helpers`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/aud/informe_cumplimiento_tributario/helpers.py
"""Helpers de formato para el Informe de Cumplimiento Tributario."""

from __future__ import annotations

import re

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

MARCO_PHRASES = {
    "pymes": (
        "Normas Internacionales de Información Financiera para Pequeñas y "
        "Medianas Entidades – NIIF para las PYMES"
    ),
    "plenas": "Normas Internacionales de Información Financiera – NIIF",
}


def fecha_larga_from_ddmmyyyy(s: str) -> str | None:
    """'09-04-2026' -> '09 de abril de 2026'. None si es inválida."""
    m = re.fullmatch(r"\s*(\d{1,2})-(\d{1,2})-(\d{4})\s*", s or "")
    if not m:
        return None
    dd, mm, yyyy = m.group(1), int(m.group(2)), m.group(3)
    if not (1 <= mm <= 12):
        return None
    return f"{int(dd):02d} de {MESES[mm - 1]} de {yyyy}"


def normaliza_del(s: str) -> str:
    """'27 de febrero del 2026' -> '27 de febrero de 2026'."""
    return re.sub(r"\bdel\b", "de", s or "", flags=re.IGNORECASE)


def marco_phrase(marco: str) -> str:
    """'pymes'|'plenas' -> frase completa. Default seguro: PYMES."""
    return MARCO_PHRASES.get(marco, MARCO_PHRASES["pymes"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_report_helpers.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/informe_cumplimiento_tributario/__init__.py \
        backend/app/aud/informe_cumplimiento_tributario/helpers.py \
        tests/test_ict_report_helpers.py
git commit -m "feat(ict-report): helpers de formato (fechas ES, marco contable)"
```

---

## Task 2: Parser F-101 (fecha de declaración IR)

**Files:**
- Create: `backend/app/aud/informe_cumplimiento_tributario/parsers/__init__.py` (vacío)
- Create: `backend/app/aud/informe_cumplimiento_tributario/parsers/declaracion_ir.py`
- Test: `tests/test_ict_report_parser_f101.py`

- [ ] **Step 1: Write the failing test** (usa el fixture REAL AXXIS)

```python
# tests/test_ict_report_parser_f101.py
from pathlib import Path

from backend.app.aud.informe_cumplimiento_tributario.parsers import declaracion_ir

FIXTURES = Path(__file__).parent / "fixtures" / "informe_cumplimiento_tributario"


def test_parse_f101_real_axxis():
    data = declaracion_ir.parse(( FIXTURES / "f101_axxis.pdf").read_bytes())
    assert data["fecha_declaracion_ir"] == "09 de abril de 2026"
    assert data["ejercicio"] == "2025"
    assert data["errores"] == []


def test_parse_f101_garbage_pdf_degrada():
    data = declaracion_ir.parse(b"%PDF-1.4 basura no es un f101")
    assert data["fecha_declaracion_ir"] is None
    assert data["errores"]  # reporta el problema, no crashea
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_report_parser_f101.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/aud/informe_cumplimiento_tributario/parsers/declaracion_ir.py
"""Parser del F-101 (Declaración IR Sociedades) PDF.

Extrae la FECHA RECAUDACIÓN (= fecha de declaración del IR, param 5) y el
período fiscal. Verificado contra PDF real AXXIS (recaudación 09-04-2026).
"""

from __future__ import annotations

import re
from io import BytesIO

import pdfplumber

from backend.app.aud.informe_cumplimiento_tributario.helpers import (
    fecha_larga_from_ddmmyyyy,
)


def parse(pdf_bytes: bytes) -> dict:
    errores: list[str] = []
    text = _extract_text(pdf_bytes, errores)
    fecha = _fecha_recaudacion(text)
    periodo = _periodo_fiscal(text)
    if fecha is None:
        errores.append("No se encontró la FECHA RECAUDACIÓN en el F-101.")
    return {
        "fecha_declaracion_ir": fecha,
        "ejercicio": periodo,
        "errores": errores,
    }


def _extract_text(pdf_bytes: bytes, errores: list[str]) -> str:
    try:
        out = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                out.append(page.extract_text() or "")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        errores.append(f"No se pudo leer el PDF: {e}")
        return ""


def _fecha_recaudacion(text: str) -> str | None:
    m = re.search(r"FECHA\s+RECAUDACI[OÓ]N", text, re.IGNORECASE)
    scope = text[m.start():] if m else text
    d = re.search(r"(\d{2}-\d{2}-\d{4})", scope)
    if not d:
        return None
    return fecha_larga_from_ddmmyyyy(d.group(1))


def _periodo_fiscal(text: str) -> str | None:
    m = re.search(r"Periodo\s+Fiscal:\s*A[NÑ]O\s*(\d{4})", text, re.IGNORECASE)
    return m.group(1) if m else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_report_parser_f101.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/informe_cumplimiento_tributario/parsers/ \
        tests/test_ict_report_parser_f101.py
git commit -m "feat(ict-report): parser F-101 fecha de declaración IR (verificado AXXIS)"
```

---

## Task 3: Parser Informe de Auditoría Externa (fecha emisión + marco contable)

**Files:**
- Create: `backend/app/aud/informe_cumplimiento_tributario/parsers/informe_auditoria_externa.py`
- Test: `tests/test_ict_report_parser_informe.py`

- [ ] **Step 1: Write the failing test** (fixture REAL AXXIS)

```python
# tests/test_ict_report_parser_informe.py
from pathlib import Path

from backend.app.aud.informe_cumplimiento_tributario.parsers import (
    informe_auditoria_externa as iae,
)

FIXTURES = Path(__file__).parent / "fixtures" / "informe_cumplimiento_tributario"


def test_parse_informe_real_axxis():
    data = iae.parse((FIXTURES / "informe_auditoria_externa_axxis.pdf").read_bytes())
    assert data["fecha_emision"] == "27 de febrero de 2026"  # 'del' normalizado
    assert data["marco_contable"] == "pymes"
    assert data["errores"] == []


def test_marco_plenas_por_defecto_si_no_dice_pymes():
    # texto sintético sin 'PYMES'
    txt = "INFORME DE LOS AUDITORES INDEPENDIENTES\n01 de marzo de 2026\nNIIF plenas"
    assert iae._marco_contable(txt) == "plenas"


def test_parse_informe_garbage_degrada():
    data = iae.parse(b"%PDF-1.4 no es un informe")
    assert data["fecha_emision"] is None
    assert data["marco_contable"] in ("pymes", "plenas")
    assert data["errores"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_report_parser_informe.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/aud/informe_cumplimiento_tributario/parsers/informe_auditoria_externa.py
"""Parser del Informe de Auditoría Externa PDF.

Extrae:
- fecha de emisión (param 4): primera fecha larga tras el título
  'INFORME DE LOS AUDITORES INDEPENDIENTES'. Verificado AXXIS -> 27-feb-2026.
- marco contable (param 7): 'pymes' si menciona NIIF para PYMES, si no 'plenas'.
"""

from __future__ import annotations

import re
from io import BytesIO

import pdfplumber

from backend.app.aud.informe_cumplimiento_tributario.helpers import normaliza_del


def parse(pdf_bytes: bytes) -> dict:
    errores: list[str] = []
    text = _extract_text(pdf_bytes, errores)
    fecha = _fecha_emision(text)
    marco = _marco_contable(text)
    if fecha is None:
        errores.append("No se encontró la fecha de emisión en el informe.")
    return {"fecha_emision": fecha, "marco_contable": marco, "errores": errores}


def _extract_text(pdf_bytes: bytes, errores: list[str]) -> str:
    try:
        out = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                out.append(page.extract_text() or "")
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        errores.append(f"No se pudo leer el PDF: {e}")
        return ""


def _fecha_emision(text: str) -> str | None:
    idx = text.find("INFORME DE LOS AUDITORES INDEPENDIENTES")
    scope = text[idx:] if idx >= 0 else text
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-zA-ZñÑáéíóúÁÉÍÓÚ]+)\s+del?\s+(\d{4})", scope
    )
    if not m:
        return None
    fecha = f"{m.group(1)} de {m.group(2).lower()} del {m.group(3)}"
    return normaliza_del(fecha)


def _marco_contable(text: str) -> str:
    if re.search(
        r"NIIF\s+para\s+(las\s+)?PYMES|Peque[nñ]as\s+y\s+Medianas",
        text,
        re.IGNORECASE,
    ):
        return "pymes"
    return "plenas"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_report_parser_informe.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/informe_cumplimiento_tributario/parsers/informe_auditoria_externa.py \
        tests/test_ict_report_parser_informe.py
git commit -m "feat(ict-report): parser informe auditoría externa (fecha emisión + marco)"
```

---

## Task 4: Tokenizar las dos plantillas Word (docxtpl)

**Files:**
- Create: `backend/app/aud/informe_cumplimiento_tributario/templates/opinion_audit_consulting.docx`
- Create: `backend/app/aud/informe_cumplimiento_tributario/templates/opinion_partner.docx`

Fuente: `C:\Users\jcalu\Downloads\Opinión y recomendaciones AUDITCONSULTING.docx`
y `...\Opinion y recomendaciones PARTNER.docx`.

**Procedimiento (una sola vez, con la skill `docx` — unpack merge-runs, editar XML, repack):**

- [ ] **Step 1: Copiar las plantillas fuente al módulo**

```bash
mkdir -p backend/app/aud/informe_cumplimiento_tributario/templates
cp "/c/Users/jcalu/Downloads/Opinión y recomendaciones AUDITCONSULTING.docx" \
   backend/app/aud/informe_cumplimiento_tributario/templates/opinion_audit_consulting.docx
cp "/c/Users/jcalu/Downloads/Opinion y recomendaciones PARTNER.docx" \
   backend/app/aud/informe_cumplimiento_tributario/templates/opinion_partner.docx
```

- [ ] **Step 2: Unpack cada plantilla (merge de runs)**

Usar el script de la skill docx (fusiona runs adyacentes → los textos de ejemplo
quedan en un solo `<w:t>` y son reemplazables). Ejecutar para ambas:

```bash
python <docx_skill>/scripts/office/unpack.py \
  backend/app/aud/informe_cumplimiento_tributario/templates/opinion_audit_consulting.docx \
  /tmp/tpl_ac/
```

- [ ] **Step 3: Reemplazar valores de ejemplo por tags docxtpl (Jinja) en `word/document.xml`**

Aplicar estos reemplazos literales (con la herramienta Edit sobre el XML
desempacado). **Importante:** reemplazar la variante MAYÚSCULAS antes que la de
minúsculas para no romper coincidencias.

| Buscar (texto literal) | Reemplazar por |
|---|---|
| `EMPRESA MODELO S.A.` | `{{ razon_social }}` |
| `ASESORIA Y REPRESENTACIONES COMERCIALES ARCOLANDS CIA.LTDA.` *(solo Partner — residuo)* | `{{ razon_social }}` |
| `31 DE DICIEMBRE DE 2025` | `{{ fecha_cierre_mayus }}` |
| `31 de diciembre del 2025` | `{{ fecha_cierre }}` |
| `31 de diciembre de 2025` | `{{ fecha_cierre }}` |
| `15 de marzo de 2026` *(todas las ocurrencias, 🟡)* | `{{ fecha_emision }}` |
| `15 de marzo 2026` *(variante sin "de")* | `{{ fecha_emision }}` |
| `09 de 2026` / `abril 09 de 2026` *(bloque 🔴)* | `{{ fecha_declaracion_ir }}` |
| `08 de julio de 2026` *(bloque 🟢)* | `{{ fecha_carga_sri }}` |
| `NIIF para las PYMES` *(cyan, en la frase de normativa)* | `{{ marco_contable }}` |
| `ejercicio fiscal 2025` | `ejercicio fiscal {{ ejercicio }}` |

Luego, **eliminar las notas instructivas** (dejar solo el dato):
- Borrar el texto `(Es la fecha de declaración del impuesto a la renta)`
- Borrar el texto `(Es la fecha de carga del reporte de diferencias al SRI)`
- Borrar el texto `(Fecha en la que se emite el informe de auditoría externa)`
- Borrar el texto `(Excepto por la información sobre la presentación de la
  declaración y pago del impuesto a la renta cuya fecha es …)` que rodea al
  bloque 🔴/🟢, dejando la redacción final:
  `{{ fecha_emision }} (excepto por la declaración y pago del impuesto a la renta,
  cuya fecha es {{ fecha_declaracion_ir }}, y por la carga del reporte de
  diferencias al SRI, cuya fecha es {{ fecha_carga_sri }})`.
- Quitar los resaltados amarillo/rojo/verde/cyan: eliminar los
  `<w:highlight w:val="…"/>` de los `<w:rPr>` de esos runs (para que el informe
  final no salga pintado).

Recomendaciones (M1): tokenizar las dos frases estándar para permitir override:
- Frase de "Otros asuntos" que empieza `…informamos que no existen recomendaciones
  sobre aspectos de carácter tributario.` → `{{ bloque_otros_asuntos }}`
- Frase de la Parte III que empieza `Con base en nuestra revisión de ciertas áreas
  seleccionadas, informamos que no hemos identificado observaciones…` →
  `{{ bloque_parte_iii }}`

- [ ] **Step 4: Repack cada plantilla**

```bash
python <docx_skill>/scripts/office/pack.py /tmp/tpl_ac/ \
  backend/app/aud/informe_cumplimiento_tributario/templates/opinion_audit_consulting.docx \
  --original "/c/Users/jcalu/Downloads/Opinión y recomendaciones AUDITCONSULTING.docx"
```
(idéntico para Partner con su ruta)

- [ ] **Step 5: Verificar que docxtpl detecta las variables**

Run:
```bash
python -c "
from docxtpl import DocxTemplate
for f in ['opinion_audit_consulting.docx','opinion_partner.docx']:
    d = DocxTemplate('backend/app/aud/informe_cumplimiento_tributario/templates/'+f)
    print(f, sorted(d.get_undeclared_template_variables()))
"
```
Expected: cada plantilla lista exactamente:
`['bloque_otros_asuntos','bloque_parte_iii','ejercicio','fecha_carga_sri','fecha_cierre','fecha_cierre_mayus','fecha_declaracion_ir','fecha_emision','marco_contable','razon_social']`

Si aparece una variable extra o falta una, corregir el XML (variable mal escrita
o valor de ejemplo no reemplazado) y repetir.

- [ ] **Step 6: Commit**

```bash
git add backend/app/aud/informe_cumplimiento_tributario/templates/
git commit -m "feat(ict-report): plantillas Word tokenizadas (AuditConsulting + Partner)"
```

---

## Task 5: Ensamblador Word (docxtpl)

**Files:**
- Create: `backend/app/aud/informe_cumplimiento_tributario/docx_assembler.py`
- Test: `tests/test_ict_report_assembler.py`

**Depende de:** Task 4 (plantillas), Task 1 (helpers).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ict_report_assembler.py
import io

from docx import Document

from backend.app.aud.informe_cumplimiento_tributario import docx_assembler


def _ctx(**over):
    base = dict(
        firma_auditora="audit_consulting",
        razon_social="AXXISGASTRO CIA. LTDA.",
        ejercicio="2025",
        fecha_emision="27 de febrero de 2026",
        fecha_declaracion_ir="09 de abril de 2026",
        fecha_carga_sri="08 de julio de 2026",
        marco_contable="pymes",
        bloque_otros_asuntos="…no existen recomendaciones…",
        bloque_parte_iii="…no hemos identificado observaciones…",
    )
    base.update(over)
    return base


def _text(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def test_assemble_audit_consulting_rellena_tokens():
    out = docx_assembler.assemble(**_ctx())
    assert isinstance(out, bytes) and len(out) > 2000
    txt = _text(out)
    assert "AXXISGASTRO CIA. LTDA." in txt
    assert "27 de febrero de 2026" in txt
    assert "09 de abril de 2026" in txt
    assert "31 de diciembre de 2025" in txt
    assert "PYMES" in txt
    assert "{{" not in txt  # no quedan tokens sin rellenar


def test_assemble_partner_usa_su_plantilla():
    out = docx_assembler.assemble(**_ctx(firma_auditora="partner_auditing"))
    txt = _text(out)
    # dato horneado de Partner (socio)
    assert "Cristina Trujillo" in txt
    assert "{{" not in txt


def test_assemble_firma_invalida_lanza():
    import pytest
    with pytest.raises(ValueError):
        docx_assembler.assemble(**_ctx(firma_auditora="inexistente"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_report_assembler.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/aud/informe_cumplimiento_tributario/docx_assembler.py
"""Ensambla el informe Word rellenando la plantilla docxtpl de la firma."""

from __future__ import annotations

import io
from pathlib import Path

from docxtpl import DocxTemplate

from backend.app.aud.informe_cumplimiento_tributario.helpers import marco_phrase

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATES = {
    "audit_consulting": TEMPLATES_DIR / "opinion_audit_consulting.docx",
    "partner_auditing": TEMPLATES_DIR / "opinion_partner.docx",
}


def assemble(
    *,
    firma_auditora: str,
    razon_social: str,
    ejercicio: str,
    fecha_emision: str | None,
    fecha_declaracion_ir: str | None,
    fecha_carga_sri: str | None,
    marco_contable: str,
    bloque_otros_asuntos: str,
    bloque_parte_iii: str,
) -> bytes:
    tpl_path = TEMPLATES.get(firma_auditora)
    if not tpl_path or not tpl_path.exists():
        raise ValueError(f"Plantilla no encontrada para firma '{firma_auditora}'")

    doc = DocxTemplate(str(tpl_path))
    ctx = {
        "razon_social": razon_social,
        "ejercicio": str(ejercicio),
        "fecha_cierre": f"31 de diciembre de {ejercicio}",
        "fecha_cierre_mayus": f"31 DE DICIEMBRE DE {ejercicio}",
        "fecha_emision": fecha_emision or "",
        "fecha_declaracion_ir": fecha_declaracion_ir or "",
        "fecha_carga_sri": fecha_carga_sri or "",
        "marco_contable": marco_phrase(marco_contable),
        "bloque_otros_asuntos": bloque_otros_asuntos,
        "bloque_parte_iii": bloque_parte_iii,
    }
    doc.render(ctx)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_report_assembler.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/informe_cumplimiento_tributario/docx_assembler.py \
        tests/test_ict_report_assembler.py
git commit -m "feat(ict-report): ensamblador Word docxtpl por firma"
```

---

## Task 6: Service layer (reutiliza ToolJob)

**Files:**
- Create: `backend/app/aud/informe_cumplimiento_tributario/service.py`
- Test: `tests/test_ict_report_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ict_report_service.py
import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.aud.informe_cumplimiento_tributario import service
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _admin_and_project():
    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:6]
        user = auth_service.create_user(
            db, email=f"a-{tag}@ex.com", password="Sup3rSecret!", role=Role.admin
        )
        client = ctx_service.create_client(db, name=f"C-{tag}")
        project = ctx_service.create_project(
            db, client_id=client.id, name=f"P-{tag}", module_code="AUD"
        )
        return user, project.id
    finally:
        db.close()


def test_create_and_get_job():
    user, pid = _admin_and_project()
    db = SessionLocal()
    try:
        job = service.create_job(
            db, user=user, project_id=pid,
            cliente_name="AXXISGASTRO CIA. LTDA.", ejercicio="2025",
            firma_auditora="audit_consulting",
        )
        assert job.tool_code == service.TOOL_CODE
        assert job.status == "pending"
        got = service.get_job(db, user, job.id)
        assert got.id == job.id
    finally:
        db.close()


def test_get_job_sin_acceso_lanza_permissionerror():
    user, pid = _admin_and_project()
    other, _ = _admin_and_project()
    db = SessionLocal()
    try:
        job = service.create_job(
            db, user=user, project_id=pid,
            cliente_name="X", ejercicio="2025", firma_auditora="audit_consulting",
        )
        with pytest.raises(PermissionError):
            service.get_job(db, other, job.id)
    finally:
        db.close()
```

> Nota: si las firmas de `ctx_service.create_client/create_project` difieren en
> este repo, ajustar el helper `_admin_and_project` para usar los endpoints HTTP
> como en `tests/test_aud_of_router.py::_mk_admin_project`. Verificar primero
> `grep -n "def create_client\|def create_project" backend/app/context/service.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_report_service.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Write minimal implementation** (clon de OF `service.py`, sin
  `period_start/end`, con `ejercicio` guardado en `period_label`)

```python
# backend/app/aud/informe_cumplimiento_tributario/service.py
"""CRUD de ToolJob para el Informe de Cumplimiento Tributario + autorización."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.context import service as ctx_service
from backend.app.context.models import Project
from backend.app.core.config import settings

TOOL_CODE = "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO"


def _ensure_project_access(db: Session, user, project_id: int) -> Project:
    proj = db.get(Project, project_id)
    if not proj or not ctx_service.user_can_access_project(db, user, proj):
        raise PermissionError("Sin acceso al proyecto.")
    return proj


def create_job(
    db: Session,
    *,
    user,
    project_id: int,
    cliente_name: str,
    ejercicio: str,
    firma_auditora: str,
) -> ToolJob:
    _ensure_project_access(db, user, project_id)
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    job = ToolJob(
        user_id=user.id,
        project_id=project_id,
        tool_code=TOOL_CODE,
        status="pending",
        cliente_name=cliente_name,
        period_label=ejercicio,  # reutilizamos period_label para el ejercicio
        firma_auditora=firma_auditora,
        created_at=now,
        expires_at=now + datetime.timedelta(minutes=settings.AUD_OF_JOB_TTL_MINUTES),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, user, job_id: int) -> ToolJob:
    job = db.get(ToolJob, job_id)
    if not job or job.tool_code != TOOL_CODE:
        raise PermissionError("Job no encontrado.")
    _ensure_project_access(db, user, job.project_id)
    return job


def list_jobs_for_project(db: Session, user, project_id: int, limit: int = 20):
    _ensure_project_access(db, user, project_id)
    return list(
        db.execute(
            select(ToolJob)
            .where(ToolJob.project_id == project_id, ToolJob.tool_code == TOOL_CODE)
            .order_by(ToolJob.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def mark_running(db: Session, job_id: int) -> None:
    _set_status(db, job_id, "running")


def mark_done(db: Session, job_id: int, summary: dict) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = "done"
        job.finished_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        job.summary_json = summary
        db.add(job)
        db.commit()


def mark_failed(db: Session, job_id: int, error_message: str) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = "failed"
        job.finished_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        job.error_message = error_message[:5000]
        db.add(job)
        db.commit()


def mark_downloaded(db: Session, job_id: int) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.downloaded_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        db.add(job)
        db.commit()


def delete_job(db: Session, user, job_id: int) -> None:
    job = get_job(db, user, job_id)
    db.delete(job)
    db.commit()


def _set_status(db: Session, job_id: int, status: str) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = status
        db.add(job)
        db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_report_service.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/informe_cumplimiento_tributario/service.py \
        tests/test_ict_report_service.py
git commit -m "feat(ict-report): service layer reutilizando ToolJob"
```

---

## Task 7: Orquestador del job (process_job)

**Files:**
- Create: `backend/app/aud/informe_cumplimiento_tributario/jobs.py`
- Test: `tests/test_ict_report_jobs.py`

**Diseño de datos de entrada:** los campos que no son columnas de `ToolJob`
(fecha_carga_sri, recomendaciones, overrides de los 3 parsers) se guardan como
`params.json` en el job_dir al crear el job (Task 8). `process_job` los lee.

Defaults exactos de recomendaciones (copiados literal de la plantilla):

```python
DEFAULT_OTROS_ASUNTOS = (
    "En cumplimiento de lo dispuesto en la Resolución del Servicio de Rentas "
    "Internas No. NAC-DGERCGC15-00003218, publicada en el Registro Oficial No. "
    "660 del 31 de diciembre de 2015, y sus reformas, incluyendo la Resolución "
    "No. NAC-DGERCGC21-00000030, informamos que no existen recomendaciones sobre "
    "aspectos de carácter tributario."
)
DEFAULT_PARTE_III = (
    "Con base en nuestra revisión de ciertas áreas seleccionadas, informamos que "
    "no hemos identificado observaciones en el sistema de control interno "
    "contable que tengan relación con aspectos tributarios, de acuerdo con lo "
    "requerido por el Servicio de Rentas Internas."
)
```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ict_report_jobs.py
import json
import uuid
from pathlib import Path

import pytest
from docx import Document

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.informe_cumplimiento_tributario import jobs, service
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db

FIX = Path(__file__).parent / "fixtures" / "informe_cumplimiento_tributario"


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload
    from backend.app.core import config
    reload(config)
    reload(file_storage)
    init_db()
    yield


def _job():
    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:6]
        user = auth_service.create_user(
            db, email=f"a-{tag}@ex.com", password="Sup3rSecret!", role=Role.admin
        )
        client = ctx_service.create_client(db, name=f"C-{tag}")
        project = ctx_service.create_project(
            db, client_id=client.id, name=f"P-{tag}", module_code="AUD"
        )
        job = service.create_job(
            db, user=user, project_id=project.id,
            cliente_name="AXXISGASTRO CIA. LTDA.", ejercicio="2025",
            firma_auditora="audit_consulting",
        )
        return job.id
    finally:
        db.close()


def test_process_job_genera_docx_con_datos_reales():
    jid = _job()
    jd = file_storage.create_job_dir(jid)
    file_storage.save_input(jd, "informe_auditoria_externa", "inf.pdf",
                            (FIX / "informe_auditoria_externa_axxis.pdf").read_bytes())
    file_storage.save_input(jd, "declaracion_ir", "f101.pdf",
                            (FIX / "f101_axxis.pdf").read_bytes())
    file_storage.save_input(jd, "params", "params.json", json.dumps({
        "fecha_carga_sri": "08 de julio de 2026",
        "hay_recomendaciones": False,
        "texto_recomendaciones": "",
        "override_fecha_emision": "",
        "override_marco_contable": "",
        "override_fecha_declaracion_ir": "",
    }).encode())

    jobs.process_job(jid)

    db = SessionLocal()
    try:
        from backend.app.aud.obligaciones_fiscales.models import ToolJob
        job = db.get(ToolJob, jid)
        assert job.status == "done", job.error_message
    finally:
        db.close()

    out = (file_storage.job_dir(jid) / "output.docx")
    assert out.exists()
    txt = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "27 de febrero de 2026" in txt   # fecha emisión parseada
    assert "09 de abril de 2026" in txt     # fecha declaración parseada
    assert "31 de diciembre de 2025" in txt # cierre derivado
    assert "PYMES" in txt                    # marco detectado
    assert "{{" not in txt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_report_jobs.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/aud/informe_cumplimiento_tributario/jobs.py
"""BackgroundTask que genera el informe Word."""

from __future__ import annotations

import json
import logging

from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.aud.informe_cumplimiento_tributario import docx_assembler, service
from backend.app.aud.informe_cumplimiento_tributario.parsers import (
    declaracion_ir,
    informe_auditoria_externa as iae,
)
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)

DEFAULT_OTROS_ASUNTOS = (
    "En cumplimiento de lo dispuesto en la Resolución del Servicio de Rentas "
    "Internas No. NAC-DGERCGC15-00003218, publicada en el Registro Oficial No. "
    "660 del 31 de diciembre de 2015, y sus reformas, incluyendo la Resolución "
    "No. NAC-DGERCGC21-00000030, informamos que no existen recomendaciones sobre "
    "aspectos de carácter tributario."
)
DEFAULT_PARTE_III = (
    "Con base en nuestra revisión de ciertas áreas seleccionadas, informamos que "
    "no hemos identificado observaciones en el sistema de control interno "
    "contable que tengan relación con aspectos tributarios, de acuerdo con lo "
    "requerido por el Servicio de Rentas Internas."
)


def _load_params(job_dir) -> dict:
    files = file_storage.list_inputs(job_dir, "params")
    if not files:
        return {}
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _first(job_dir, slot):
    files = file_storage.list_inputs(job_dir, slot)
    return files[0].read_bytes() if files else None


def process_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        service.mark_running(db, job_id)
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("process_job: ToolJob %s no existe", job_id)
            return

        job_dir = file_storage.job_dir(job_id)
        params = _load_params(job_dir)

        # --- Parsers (con override manual del form) ---
        errores: list[str] = []
        inf_bytes = _first(job_dir, "informe_auditoria_externa")
        f101_bytes = _first(job_dir, "declaracion_ir")
        inf = iae.parse(inf_bytes) if inf_bytes else {"fecha_emision": None, "marco_contable": "pymes", "errores": ["Falta el Informe de Auditoría Externa."]}
        f101 = declaracion_ir.parse(f101_bytes) if f101_bytes else {"fecha_declaracion_ir": None, "errores": ["Falta el F-101."]}
        errores += inf.get("errores", []) + f101.get("errores", [])

        fecha_emision = params.get("override_fecha_emision") or inf.get("fecha_emision")
        marco = params.get("override_marco_contable") or inf.get("marco_contable") or "pymes"
        fecha_decl = params.get("override_fecha_declaracion_ir") or f101.get("fecha_declaracion_ir")

        # --- Recomendaciones ---
        if params.get("hay_recomendaciones") and params.get("texto_recomendaciones"):
            bloque = params["texto_recomendaciones"]
            bloque_otros = bloque
            bloque_parte_iii = bloque
        else:
            bloque_otros = DEFAULT_OTROS_ASUNTOS
            bloque_parte_iii = DEFAULT_PARTE_III

        # --- Ensamblar ---
        docx_bytes = docx_assembler.assemble(
            firma_auditora=job.firma_auditora,
            razon_social=job.cliente_name,
            ejercicio=job.period_label,
            fecha_emision=fecha_emision,
            fecha_declaracion_ir=fecha_decl,
            fecha_carga_sri=params.get("fecha_carga_sri", ""),
            marco_contable=marco,
            bloque_otros_asuntos=bloque_otros,
            bloque_parte_iii=bloque_parte_iii,
        )
        (job_dir / "output.docx").write_bytes(docx_bytes)

        service.mark_done(db, job_id, {
            "fecha_emision": fecha_emision,
            "marco_contable": marco,
            "fecha_declaracion_ir": fecha_decl,
            "warnings": errores,
            "docx_size_bytes": len(docx_bytes),
        })
        log.info("ict-report job %s done", job_id)
    except Exception as e:  # noqa: BLE001
        log.exception("ict-report job %s failed", job_id)
        try:
            service.mark_failed(db, job_id, str(e))
        except Exception:
            log.exception("no se pudo marcar failed el job %s", job_id)
    finally:
        db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ict_report_jobs.py -v`
Expected: PASS (1 passed). Verifica extremo-a-extremo con PDFs reales +
generación del `.docx`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/aud/informe_cumplimiento_tributario/jobs.py \
        tests/test_ict_report_jobs.py
git commit -m "feat(ict-report): orquestador process_job (parsers + assembler)"
```

---

## Task 8: Router HTTP + registro

**Files:**
- Create: `backend/app/aud/informe_cumplimiento_tributario/router.py`
- Modify: `backend/app/api/__init__.py`
- Test: `tests/test_ict_report_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ict_report_router.py
import uuid
from pathlib import Path

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.db.session import SessionLocal, init_db

FIX = Path(__file__).parent / "fixtures" / "informe_cumplimiento_tributario"
BASE = "/api/v1/aud/informe-cumplimiento-tributario"


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload
    from backend.app.core import config
    reload(config)
    reload(file_storage)
    init_db()
    yield


def _mk_user(role=Role.admin):
    tag = uuid.uuid4().hex[:6]
    email, pw = f"u-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    return email, pw


def _login(client, email, pw):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _admin_project(client):
    tag = uuid.uuid4().hex[:6]
    email, pw = _mk_user(Role.admin)
    tok = _login(client, email, pw)
    cid = client.post("/api/v1/context/clients", headers=_h(tok),
                      json={"name": f"C-{tag}"}).json()["id"]
    pid = client.post("/api/v1/context/projects", headers=_h(tok),
                      json={"client_id": cid, "name": f"P-{tag}", "module_code": "AUD"}).json()["id"]
    return tok, pid


def _files():
    return [
        ("informe_auditoria_externa", ("inf.pdf",
            (FIX / "informe_auditoria_externa_axxis.pdf").read_bytes(), "application/pdf")),
        ("declaracion_ir", ("f101.pdf",
            (FIX / "f101_axxis.pdf").read_bytes(), "application/pdf")),
    ]


def test_create_requires_both_pdfs(client):
    tok, pid = _admin_project(client)
    r = client.post(f"{BASE}/jobs", headers=_h(tok),
                    data={"project_id": pid, "cliente_name": "X", "ejercicio": "2025",
                          "firma_auditora": "audit_consulting", "fecha_carga_sri": "08 de julio de 2026"},
                    files=[])
    assert r.status_code == 400


def test_end_to_end_create_and_download_docx(client):
    tok, pid = _admin_project(client)
    r = client.post(f"{BASE}/jobs", headers=_h(tok),
                    data={"project_id": pid, "cliente_name": "AXXISGASTRO CIA. LTDA.",
                          "ejercicio": "2025", "firma_auditora": "audit_consulting",
                          "fecha_carga_sri": "08 de julio de 2026",
                          "hay_recomendaciones": "false"},
                    files=_files())
    assert r.status_code == 201, r.text
    jid = r.json()["id"]
    assert r.json()["tool_code"] == "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO"

    # TestClient corre el BackgroundTask sync al cerrar el context.
    r = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok))
    assert r.json()["status"] == "done", r.json()

    r = client.get(f"{BASE}/jobs/{jid}/download", headers=_h(tok))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(r.content) > 2000


def test_parse_preview_devuelve_datos(client):
    tok, pid = _admin_project(client)
    r = client.post(f"{BASE}/parse-preview", headers=_h(tok), files=_files())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fecha_emision"] == "27 de febrero de 2026"
    assert body["marco_contable"] == "pymes"
    assert body["fecha_declaracion_ir"] == "09 de abril de 2026"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ict_report_router.py -v`
Expected: FAIL (404 en las rutas — router no montado)

- [ ] **Step 3: Write the router**

```python
# backend/app/aud/informe_cumplimiento_tributario/router.py
"""Endpoints HTTP del Informe de Cumplimiento Tributario."""

from __future__ import annotations

import json
from io import BytesIO

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.informe_cumplimiento_tributario import jobs, service
from backend.app.aud.informe_cumplimiento_tributario.parsers import (
    declaracion_ir as p_decl,
    informe_auditoria_externa as p_iae,
)
from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(
    prefix="/aud/informe-cumplimiento-tributario",
    tags=["aud-informe-cumplimiento-tributario"],
)

FIRMAS_VALIDAS = {"audit_consulting", "partner_auditing"}
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _job_out(job) -> dict:
    return {
        "id": job.id, "project_id": job.project_id, "tool_code": job.tool_code,
        "status": job.status, "cliente_name": job.cliente_name,
        "ejercicio": job.period_label, "firma_auditora": job.firma_auditora,
        "error_message": job.error_message, "summary_json": job.summary_json,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


async def _read_pdf(upload: UploadFile, label: str) -> bytes:
    if upload.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(415, detail=f"{label}: se requiere PDF")
    data = await upload.read()
    if len(data) > settings.AUD_OF_MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, detail=f"{label}: excede {settings.AUD_OF_MAX_FILE_MB} MB")
    return data


@router.post("/parse-preview")
async def parse_preview_endpoint(
    informe_auditoria_externa: UploadFile = File(...),
    declaracion_ir: UploadFile = File(...),
    current: User = Depends(get_current_user),
):
    inf = p_iae.parse(await _read_pdf(informe_auditoria_externa, "Informe Aud. Externa"))
    f101 = p_decl.parse(await _read_pdf(declaracion_ir, "F-101"))
    return JSONResponse({
        "fecha_emision": inf.get("fecha_emision"),
        "marco_contable": inf.get("marco_contable"),
        "fecha_declaracion_ir": f101.get("fecha_declaracion_ir"),
        "warnings": inf.get("errores", []) + f101.get("errores", []),
    })


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job_endpoint(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    cliente_name: str = Form(...),
    ejercicio: str = Form(...),
    firma_auditora: str = Form(...),
    fecha_carga_sri: str = Form(""),
    hay_recomendaciones: bool = Form(False),
    texto_recomendaciones: str = Form(""),
    override_fecha_emision: str = Form(""),
    override_marco_contable: str = Form(""),
    override_fecha_declaracion_ir: str = Form(""),
    informe_auditoria_externa: UploadFile | None = File(None),
    declaracion_ir: UploadFile | None = File(None),
    anexo_diferencias_sri: UploadFile | None = File(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if firma_auditora not in FIRMAS_VALIDAS:
        raise HTTPException(400, detail=f"firma_auditora inválida: {firma_auditora}")
    if not (informe_auditoria_externa and informe_auditoria_externa.filename
            and declaracion_ir and declaracion_ir.filename):
        raise HTTPException(400, detail="Sube el Informe de Auditoría Externa y el F-101.")

    inf_bytes = await _read_pdf(informe_auditoria_externa, "Informe Aud. Externa")
    f101_bytes = await _read_pdf(declaracion_ir, "F-101")

    try:
        job = service.create_job(
            db, user=current, project_id=project_id,
            cliente_name=cliente_name, ejercicio=ejercicio, firma_auditora=firma_auditora,
        )
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    job_dir = file_storage.create_job_dir(job.id)
    file_storage.save_input(job_dir, "informe_auditoria_externa",
                            informe_auditoria_externa.filename, inf_bytes)
    file_storage.save_input(job_dir, "declaracion_ir",
                            declaracion_ir.filename, f101_bytes)
    if anexo_diferencias_sri and anexo_diferencias_sri.filename:
        file_storage.save_input(job_dir, "anexo_diferencias_sri",
                                anexo_diferencias_sri.filename,
                                await _read_pdf(anexo_diferencias_sri, "Anexo Diferencias"))
    file_storage.save_input(job_dir, "params", "params.json", json.dumps({
        "fecha_carga_sri": fecha_carga_sri,
        "hay_recomendaciones": hay_recomendaciones,
        "texto_recomendaciones": texto_recomendaciones,
        "override_fecha_emision": override_fecha_emision,
        "override_marco_contable": override_marco_contable,
        "override_fecha_declaracion_ir": override_fecha_declaracion_ir,
    }).encode("utf-8"))

    background_tasks.add_task(jobs.process_job, job.id)
    return _job_out(job)


@router.get("/jobs/{job_id}")
def get_job_endpoint(job_id: int, current: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    try:
        return _job_out(service.get_job(db, current, job_id))
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))


@router.get("/jobs")
def list_jobs_endpoint(project_id: int, limit: int = 20,
                       current: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    try:
        return [_job_out(j) for j in service.list_jobs_for_project(db, current, project_id, limit=limit)]
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))


@router.get("/jobs/{job_id}/download")
def download_job_endpoint(job_id: int, current: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status != "done":
        raise HTTPException(409, detail=f"Job status={job.status}, no listo")
    out = file_storage.job_dir(job.id) / "output.docx"
    if not out.exists():
        raise HTTPException(410, detail="Informe ya no disponible (expirado).")
    service.mark_downloaded(db, job.id)
    safe = (job.cliente_name or "cliente").replace(" ", "_").replace("/", "_")
    filename = f"Informe_Cumplimiento_Tributario_{safe}_{job.period_label}.docx"
    return StreamingResponse(
        BytesIO(out.read_bytes()), media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_endpoint(job_id: int, current: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    try:
        service.delete_job(db, current, job_id)
        file_storage.delete_job_dir(job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return None
```

- [ ] **Step 4: Register the router**

En `backend/app/api/__init__.py`, agregar el import y el `include_router`:

```python
# junto a los otros imports aud
from backend.app.aud.informe_cumplimiento_tributario import router as aud_ict_report_router
```
```python
# junto a api_router.include_router(aud_of_router.router)
api_router.include_router(aud_ict_report_router.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_ict_report_router.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/aud/informe_cumplimiento_tributario/router.py \
        backend/app/api/__init__.py tests/test_ict_report_router.py
git commit -m "feat(ict-report): router HTTP + registro en api_router"
```

---

## Task 9: Frontend — catálogo + strings

**Files:**
- Modify: `frontend/src/aud/catalog.js:40`
- Modify: `frontend/src/aud/strings.js`

- [ ] **Step 1: Agregar la tool a la categoría CONCLUSION**

En `frontend/src/aud/catalog.js`, reemplazar la línea:
```javascript
  { id: "CONCLUSION", label: "Conclusión y dictamen", type: "etapa" },
```
por:
```javascript
  {
    id: "CONCLUSION",
    label: "Conclusión y dictamen",
    type: "etapa",
    tools: [
      {
        id: "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO",
        label: "Informe de Cumplimiento Tributario",
        description:
          "Genera el informe de opinión (AuditConsulting / Partner) a partir del Informe de Auditoría Externa y el F-101. Descarga el Word listo para firmar.",
      },
    ],
  },
```

- [ ] **Step 2: Agregar strings**

En `frontend/src/aud/strings.js`, dentro del objeto `STRINGS`, agregar antes del
cierre `};`:
```javascript
  ict_title: "Informe de Cumplimiento Tributario",
  ict_subtitle:
    "Llena los datos del cliente, elige la firma y sube el Informe de Auditoría Externa y el F-101. Descarga el informe Word lleno.",
  ict_cliente: "Cliente auditado",
  ict_ejercicio: "Ejercicio fiscal (ej. 2025)",
  ict_fecha_carga_sri: "Fecha de carga del reporte de diferencias al SRI",
  ict_recomendaciones_q: "¿Existen recomendaciones sobre aspectos tributarios?",
  ict_recomendaciones_txt: "Detalle de las recomendaciones",
  ict_firma: "Firma auditora (elige la plantilla)",
  ict_slot_informe: "Informe de Auditoría Externa (PDF) — requerido",
  ict_slot_f101: "Declaración de Impuesto a la Renta F-101 (PDF) — requerido",
  ict_slot_diferencias: "Anexo de Diferencias SRI (PDF) — opcional",
  ict_fecha_emision: "Fecha de emisión del informe (auto)",
  ict_marco: "Marco contable (auto)",
  ict_fecha_declaracion: "Fecha de declaración del IR (auto)",
  ict_generate: "Generar informe",
  ict_processing: "Generando informe…",
  ict_done: "Informe listo",
  ict_download: "Descargar Word",
  ict_failed: "Falló la generación",
  ict_new: "Nuevo informe",
  ict_recent: "Generados recientemente",
  ict_need_files: "Sube el Informe de Auditoría Externa y el F-101.",
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/aud/catalog.js frontend/src/aud/strings.js
git commit -m "feat(ict-report): catálogo + strings de la tool en AUD/Conclusión"
```

---

## Task 10: Frontend — funciones API

**Files:**
- Modify: `frontend/src/api.js` (al final, tras las funciones de OF)

- [ ] **Step 1: Agregar las funciones**

```javascript
// ---------- AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO ----------

const ICT_BASE = `${API_BASE}/api/v1/aud/informe-cumplimiento-tributario`;

export async function parseIctPreview(files) {
  const fd = new FormData();
  fd.append("informe_auditoria_externa", files.informe);
  fd.append("declaracion_ir", files.f101);
  return parse(await fetch(`${ICT_BASE}/parse-preview`, {
    method: "POST", headers: authHeaders(), body: fd,
  }));
}

export async function createIctJob(form, files) {
  const fd = new FormData();
  Object.entries(form).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== "") fd.append(k, v);
  });
  fd.append("informe_auditoria_externa", files.informe);
  fd.append("declaracion_ir", files.f101);
  if (files.diferencias) fd.append("anexo_diferencias_sri", files.diferencias);
  return parse(await fetch(`${ICT_BASE}/jobs`, {
    method: "POST", headers: authHeaders(), body: fd,
  }));
}

export async function getIctJob(jobId) {
  return parse(await fetch(`${ICT_BASE}/jobs/${jobId}`, { headers: authHeaders() }));
}

export async function listIctJobs(projectId) {
  return parse(await fetch(`${ICT_BASE}/jobs?project_id=${projectId}`, { headers: authHeaders() }));
}

export async function downloadIctJob(jobId, suggestedFilename) {
  const res = await fetch(`${ICT_BASE}/jobs/${jobId}/download`, { headers: authHeaders() });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail || detail; } catch { /* */ }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedFilename || `Informe_Cumplimiento_Tributario_${jobId}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

> Verificar que `API_BASE`, `authHeaders` y `parse` existen en `api.js` (los usa
> OF). Si el nombre difiere, usar el mismo helper que `createObligacionesFiscalesJob`.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(ict-report): funciones API frontend (preview/create/get/list/download)"
```

---

## Task 11: Frontend — componente de la tool

**Files:**
- Create: `frontend/src/aud/InformeCumplimientoTributarioTool.jsx`

- [ ] **Step 1: Crear el componente** (clon de `ObligacionesFiscalesTool.jsx`
  adaptado; reutiliza clases CSS `of-*`)

```jsx
import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "../api.js";
import { STRINGS } from "./strings.js";

export default function InformeCumplimientoTributarioTool({ projectId }) {
  const [stage, setStage] = useState("form"); // form | processing | done | failed
  const [form, setForm] = useState({
    cliente_name: "",
    ejercicio: "",
    fecha_carga_sri: "",
    firma_auditora: "audit_consulting",
    hay_recomendaciones: false,
    texto_recomendaciones: "",
    override_fecha_emision: "",
    override_marco_contable: "",
    override_fecha_declaracion_ir: "",
  });
  const [files, setFiles] = useState({});
  const [job, setJob] = useState(null);
  const [recent, setRecent] = useState([]);
  const [err, setErr] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const pollRef = useRef();

  const loadRecent = useCallback(async () => {
    if (!projectId) return;
    try { setRecent(await api.listIctJobs(projectId)); } catch { /* */ }
  }, [projectId]);

  useEffect(() => { loadRecent(); }, [loadRecent]);
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  function setFile(slot, fileList) {
    setFiles((prev) => ({ ...prev, [slot]: (fileList && fileList[0]) || null }));
  }

  // Autocompletar los 3 campos "auto" al tener ambos PDFs
  async function tryPreview(next) {
    if (!(next.informe && next.f101)) return;
    setPreviewing(true);
    try {
      const p = await api.parseIctPreview(next);
      setForm((f) => ({
        ...f,
        override_fecha_emision: p.fecha_emision || f.override_fecha_emision,
        override_marco_contable: p.marco_contable || f.override_marco_contable,
        override_fecha_declaracion_ir: p.fecha_declaracion_ir || f.override_fecha_declaracion_ir,
      }));
    } catch (e) {
      setErr(`No se pudo autocompletar: ${e.message}`);
    } finally {
      setPreviewing(false);
    }
  }

  function onFile(slot, fileList) {
    const file = (fileList && fileList[0]) || null;
    const next = { ...files, [slot]: file };
    setFiles(next);
    if (slot === "informe" || slot === "f101") tryPreview(next);
  }

  async function submit(e) {
    e.preventDefault();
    setErr("");
    if (!(files.informe && files.f101)) { setErr(STRINGS.ict_need_files); return; }
    try {
      const j = await api.createIctJob({ project_id: projectId, ...form }, files);
      setJob(j);
      setStage("processing");
      pollRef.current = setInterval(async () => {
        try {
          const u = await api.getIctJob(j.id);
          setJob(u);
          if (u.status === "done") { clearInterval(pollRef.current); setStage("done"); loadRecent(); }
          else if (u.status === "failed" || u.status === "expired") { clearInterval(pollRef.current); setStage("failed"); }
        } catch { /* intermitencia */ }
      }, 2000);
    } catch (e2) { setErr(e2.message); }
  }

  function reset() {
    setStage("form"); setJob(null); setFiles({}); setErr("");
    setForm({
      cliente_name: "", ejercicio: "", fecha_carga_sri: "",
      firma_auditora: "audit_consulting", hay_recomendaciones: false,
      texto_recomendaciones: "", override_fecha_emision: "",
      override_marco_contable: "", override_fecha_declaracion_ir: "",
    });
  }

  async function downloadJob(j) {
    try {
      const safe = (j.cliente_name || "cliente").replace(/[^a-zA-Z0-9]/g, "_");
      await api.downloadIctJob(j.id, `Informe_Cumplimiento_Tributario_${safe}_${j.ejercicio}.docx`);
    } catch (e) { setErr(`Error al descargar: ${e.message}`); }
  }

  if (!projectId) {
    return <div className="notice warn">Selecciona un proyecto del módulo AUD primero.</div>;
  }

  return (
    <div className="of-tool">
      <header className="of-head">
        <h2>{STRINGS.ict_title}</h2>
        <p className="muted">{STRINGS.ict_subtitle}</p>
      </header>

      {stage === "form" && (
        <form onSubmit={submit} className="of-form">
          <div className="of-form-row">
            <label>{STRINGS.ict_cliente}*
              <input value={form.cliente_name} required
                onChange={(e) => setForm({ ...form, cliente_name: e.target.value })} />
            </label>
            <label>{STRINGS.ict_ejercicio}*
              <input value={form.ejercicio} required
                onChange={(e) => setForm({ ...form, ejercicio: e.target.value })} />
            </label>
            <label>{STRINGS.ict_fecha_carga_sri}
              <input value={form.fecha_carga_sri} placeholder="08 de julio de 2026"
                onChange={(e) => setForm({ ...form, fecha_carga_sri: e.target.value })} />
            </label>
          </div>

          <div className="of-form-row">
            <label>
              <input type="checkbox" checked={form.hay_recomendaciones}
                onChange={(e) => setForm({ ...form, hay_recomendaciones: e.target.checked })} />
              {" "}{STRINGS.ict_recomendaciones_q}
            </label>
          </div>
          {form.hay_recomendaciones && (
            <div className="of-form-row">
              <label style={{ flex: 1 }}>{STRINGS.ict_recomendaciones_txt}
                <textarea rows={4} value={form.texto_recomendaciones}
                  onChange={(e) => setForm({ ...form, texto_recomendaciones: e.target.value })} />
              </label>
            </div>
          )}

          <div className="of-firma">
            <div className="of-firma-label">{STRINGS.ict_firma}*</div>
            <div className="of-firma-options">
              <label className="of-firma-opt">
                <input type="radio" name="firma" value="audit_consulting"
                  checked={form.firma_auditora === "audit_consulting"}
                  onChange={(e) => setForm({ ...form, firma_auditora: e.target.value })} />
                <span>{STRINGS.of_firma_audit_consulting}</span>
              </label>
              <label className="of-firma-opt">
                <input type="radio" name="firma" value="partner_auditing"
                  checked={form.firma_auditora === "partner_auditing"}
                  onChange={(e) => setForm({ ...form, firma_auditora: e.target.value })} />
                <span>{STRINGS.of_firma_partner_auditing}</span>
              </label>
            </div>
          </div>

          <div className="of-slots">
            <div className="of-slot req">
              <label>{STRINGS.ict_slot_informe}
                <input type="file" accept="application/pdf"
                  onChange={(e) => onFile("informe", e.target.files)} />
              </label>
              {files.informe && <span className="of-slot-count">1 archivo</span>}
            </div>
            <div className="of-slot req">
              <label>{STRINGS.ict_slot_f101}
                <input type="file" accept="application/pdf"
                  onChange={(e) => onFile("f101", e.target.files)} />
              </label>
              {files.f101 && <span className="of-slot-count">1 archivo</span>}
            </div>
            <div className="of-slot">
              <label>{STRINGS.ict_slot_diferencias}
                <input type="file" accept="application/pdf"
                  onChange={(e) => setFile("diferencias", e.target.files)} />
              </label>
              {files.diferencias && <span className="of-slot-count">1 archivo</span>}
            </div>
          </div>

          <div className="of-form-row">
            <label>{STRINGS.ict_fecha_emision}
              <input value={form.override_fecha_emision}
                onChange={(e) => setForm({ ...form, override_fecha_emision: e.target.value })} />
            </label>
            <label>{STRINGS.ict_marco}
              <select value={form.override_marco_contable}
                onChange={(e) => setForm({ ...form, override_marco_contable: e.target.value })}>
                <option value="">(auto)</option>
                <option value="pymes">NIIF para las PYMES</option>
                <option value="plenas">NIIF plenas</option>
              </select>
            </label>
            <label>{STRINGS.ict_fecha_declaracion}
              <input value={form.override_fecha_declaracion_ir}
                onChange={(e) => setForm({ ...form, override_fecha_declaracion_ir: e.target.value })} />
            </label>
          </div>
          {previewing && <p className="muted small">Autocompletando desde los PDFs…</p>}

          {err && <div className="err">{err}</div>}
          <button type="submit" className="btn primary lg">{STRINGS.ict_generate}</button>
        </form>
      )}

      {stage === "processing" && (
        <div className="of-stage">
          <div className="spinner" />
          <h3>{STRINGS.ict_processing}</h3>
          <p className="muted">Job #{job?.id} · {job?.status}</p>
        </div>
      )}

      {stage === "done" && (
        <div className="of-stage">
          <h3>✅ {STRINGS.ict_done}</h3>
          <div className="of-stage-actions">
            <button type="button" className="btn primary lg" onClick={() => downloadJob(job)}>
              {STRINGS.ict_download}
            </button>
            <button className="btn" onClick={reset}>{STRINGS.ict_new}</button>
          </div>
        </div>
      )}

      {stage === "failed" && (
        <div className="of-stage">
          <h3>❌ {STRINGS.ict_failed}</h3>
          <pre className="of-summary err">{job?.error_message || "Error desconocido"}</pre>
          <button className="btn" onClick={reset}>{STRINGS.ict_new}</button>
        </div>
      )}

      {recent.length > 0 && stage === "form" && (
        <div className="of-recent">
          <h3>{STRINGS.ict_recent}</h3>
          <ul className="of-recent-list">
            {recent.slice(0, 10).map((j) => (
              <li key={j.id}>
                #{j.id} · {j.cliente_name} · {j.ejercicio}{" "}
                <span className={`badge ${j.status}`}>{j.status}</span>
                {j.status === "done" && (
                  <button type="button" className="link" onClick={() => downloadJob(j)}>
                    {" "}· ↓ descargar
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/aud/InformeCumplimientoTributarioTool.jsx
git commit -m "feat(ict-report): componente frontend de la tool"
```

---

## Task 12: Frontend — enrutar la tool en ToolCatalog

**Files:**
- Modify: `frontend/src/aud/ToolCatalog.jsx`

- [ ] **Step 1: Import + branch**

En `frontend/src/aud/ToolCatalog.jsx`, agregar el import:
```javascript
import InformeCumplimientoTributarioTool from "./InformeCumplimientoTributarioTool.jsx";
```
Y agregar, junto al branch de OF (`if (activeTool === "AUD.IMPUESTOS.OBLIGACIONES_FISCALES")`),
un segundo branch antes del `return` del catálogo:
```javascript
  if (activeTool === "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO") {
    return (
      <div className="aud-tool-wrap">
        <button className="link aud-back" onClick={() => setActiveTool(null)}>
          {STRINGS.back_to_catalog}
        </button>
        <InformeCumplimientoTributarioTool projectId={projectId} />
      </div>
    );
  }
```

- [ ] **Step 2: Verify build (frontend)**

Run: `cd frontend && npm run build`
Expected: build sin errores; el bundle incluye el nuevo componente.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/aud/ToolCatalog.jsx
git commit -m "feat(ict-report): enrutar la tool en el catálogo AUD"
```

---

## Task 13: Verificación end-to-end (⚠️ regla suprema)

**Objetivo:** probar el flujo real con las dos firmas y confirmar que el `.docx`
abre en Word sin cuadro de reparación.

- [ ] **Step 1: Correr toda la suite backend de la tool**

Run: `python -m pytest tests/ -k "ict_report" -v`
Expected: TODOS verdes (helpers, parsers, assembler, service, jobs, router).

- [ ] **Step 2: Generar el .docx real de las dos firmas y validar apertura**

Run:
```bash
python -c "
from pathlib import Path
from docx import Document
from backend.app.aud.informe_cumplimiento_tributario import docx_assembler, jobs
from backend.app.aud.informe_cumplimiento_tributario.parsers import declaracion_ir, informe_auditoria_externa as iae
FIX = Path('tests/fixtures/informe_cumplimiento_tributario')
inf = iae.parse((FIX/'informe_auditoria_externa_axxis.pdf').read_bytes())
f101 = declaracion_ir.parse((FIX/'f101_axxis.pdf').read_bytes())
for firma in ['audit_consulting','partner_auditing']:
    b = docx_assembler.assemble(
        firma_auditora=firma, razon_social='AXXISGASTRO CIA. LTDA.', ejercicio='2025',
        fecha_emision=inf['fecha_emision'], fecha_declaracion_ir=f101['fecha_declaracion_ir'],
        fecha_carga_sri='08 de julio de 2026', marco_contable=inf['marco_contable'],
        bloque_otros_asuntos=jobs.DEFAULT_OTROS_ASUNTOS, bloque_parte_iii=jobs.DEFAULT_PARTE_III)
    out = Path(f'/tmp/ict_{firma}.docx'); out.write_bytes(b)
    doc = Document(str(out))  # si abre sin excepción, el .docx es válido
    txt = '\n'.join(p.text for p in doc.paragraphs)
    assert '{{' not in txt, 'quedaron tokens sin rellenar'
    for must in ['AXXISGASTRO CIA. LTDA.','27 de febrero de 2026','09 de abril de 2026','31 de diciembre de 2025','PYMES']:
        assert must in txt, f'falta: {must}'
    print(firma, 'OK ->', out, len(b), 'bytes')
"
```
Expected: imprime `audit_consulting OK` y `partner_auditing OK`.

- [ ] **Step 3: Abrir manualmente ambos `/tmp/ict_*.docx` en Word**

Verificar visualmente:
- No aparece el cuadro "Word encontró contenido ilegible / reparar".
- El bloque de firma corresponde a la firma elegida (Calupiña vs Trujillo).
- No quedan textos instructivos entre paréntesis ni resaltados de color.
- Las fechas 🟡🔴🟢 y el marco contable salen correctos.

- [ ] **Step 4: Prueba en el navegador (opcional, con preview del módulo)**

Levantar el frontend, entrar a AUD → Conclusión y dictamen → Informe de
Cumplimiento Tributario, llenar cabecera, subir los 2 PDFs (verificar que los 3
campos "auto" se autocompletan), Generar, descargar y abrir el Word.

- [ ] **Step 5: Commit (si hubo ajustes)**

```bash
git add -A
git commit -m "test(ict-report): verificación e2e con datos reales (2 firmas)"
```

---

## Notas de alcance / deuda

- **Parte IV (Reporte de Diferencias) — M2:** el slot `anexo_diferencias_sri` se
  guarda pero NO se procesa en M1. Fixture real disponible
  (`reporte_diferencias_axxis.pdf`) para cuando se implemente la tabla.
- **Recomendaciones "sí":** en M1 se inyecta el texto libre del auditor en las
  dos secciones. Si el grupo tiene una redacción legal específica para la
  variante "con recomendaciones", incorporarla en M2.
- **Robustez de parsers:** verificados contra la muestra AXXIS. Al aparecer PDFs
  de otras firmas/años con layout distinto, agregar fixtures y ampliar las
  heurísticas; los campos siempre quedan editables (override) para no bloquear.
