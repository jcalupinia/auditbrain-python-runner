# Informe de Cumplimiento Tributario — Diseño (M1)

**Fecha:** 2026-07-08
**Módulo:** AUD · External Audit → etapa **Conclusión y dictamen**
**Tool code:** `AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO`
**Estado:** diseño aprobado, pendiente de implementación

---

## 1. Objetivo

Nueva herramienta, **independiente del módulo ICT**, dentro de la etapa
`CONCLUSION` del módulo AUD. Genera el **Informe de los Auditores Independientes
sobre el Cumplimiento de Obligaciones Tributarias** (opinión + recomendaciones)
rellenando automáticamente una de las dos plantillas Word preestablecidas de las
firmas del grupo, a partir de datos extraídos de PDFs cargados y unos pocos
campos manuales.

La arquitectura es un **clon del patrón de `AUD.IMPUESTOS.OBLIGACIONES_FISCALES`**
(`backend/app/aud/obligaciones_fiscales/`), cambiando el ensamblador de Excel por
uno de Word.

## 2. Alcance

**En alcance (M1):**
- Dos plantillas Word (AuditConsulting / Partner), seleccionadas por firma.
- Dos inputs PDF con extracción automática (parsers).
- Campos manuales + override manual de los campos autocompletados.
- Salida: el informe Word (`.docx`) lleno, listo para revisar/firmar.

**Fuera de alcance (M2):**
- **Parte IV — Reporte de diferencias del ICT** (tabla), alimentada por un slot
  opcional **"Anexo de Diferencias SRI"**. En M1 ese slot puede existir en la UI
  pero no se procesa; la **fecha de carga al SRI se ingresa manual en la
  cabecera** (Param 6). Cuando en M2 se suba el anexo, de ahí saldrá la Parte IV
  (y potencialmente la fecha de carga).
- Salida en PDF (solo Word por ahora).

## 3. Las dos plantillas (fuente de verdad)

Archivos de referencia entregados por el cliente:
- `Opinión y recomendaciones AUDITCONSULTING.docx`
- `Opinion y recomendaciones PARTNER.docx`

Ambas son **el mismo informe palabra por palabra** (boilerplate legal SRI:
Resolución NAC-DGERCGC15-00003218 y reformas). Solo difieren en el **bloque de
firma del socio**, que va **horneado en cada plantilla** (no se rellena):

| Firma | Socio | Licencia | Registro | RUC firma | Superintendencia |
|---|---|---|---|---|---|
| **AuditConsulting** | Dr. Jorge Calupiña | 28525 | 555 | 1791961048001 | SC-RNAE-555 |
| **Partner** | Ing. Cristina Trujillo V. | 170110742 | 756 | 1792260957001 | SC-RNAE-756 |

Datos de firma **confirmados vigentes** por el usuario (2026-07-08).

### Leyenda de colores (verificada empíricamente = spec de campos)

Los colores de resaltado en las plantillas codifican los campos variables:

| Color | Texto marcado (ejemplo) | Campo |
|---|---|---|
| 🟡 Amarillo | `15 de marzo de 2026` (×4) | Fecha de emisión del informe |
| 🔴 Rojo | `09 de 2026` + *"(Es la fecha de declaración del IR)"* | Fecha de declaración del IR |
| 🟢 Verde | `08 de julio de 2026` + *"(…carga del reporte de diferencias al SRI)"* | Fecha de carga del reporte de diferencias al SRI |
| 🔵 Cyan | *"(Revisar la normativa…)"* / `NIIF para las PYMES` | Marco contable (NIIF plenas / PYMES) |
| 🔺 Rojo de fuente | *"(Fecha en la que se emite el informe…)"* | Nota instructiva (NO va en el informe final) |

**Regla de render:** los textos instructivos entre paréntesis (rojo de fuente y
las coletillas *"(Es la fecha…)"*) se **eliminan** en el informe generado; solo
queda el dato.

**Normalización:** la plantilla Partner tiene un residuo — en el encabezado de la
Parte III dice `ASESORIA Y REPRESENTACIONES COMERCIALES ARCOLANDS CIA.LTDA.` en
lugar de la razón social. Se corrige al tokenizar (pasa a `{{RAZON_SOCIAL}}`).

## 4. Parámetros y su origen

| # | Parámetro | Marca | Origen |
|---|---|---|---|
| 1 | Razón social del cliente (Cliente auditado) | — | **Manual (cabecera)** |
| 2 | Fecha de cierre (`31 de diciembre de YYYY`) | — | **Derivado** de ejercicio |
| 3 | Ejercicio fiscal (`YYYY`) | — | **Manual (cabecera)** |
| 4 | Fecha de emisión del informe | 🟡 | Parser Informe Aud. Externa |
| 5 | Fecha de declaración del IR | 🔴 | Parser Declaración IR (F-101 PDF) |
| 6 | Fecha de carga del reporte de diferencias al SRI | 🟢 | **Manual (cabecera)** |
| 7 | Marco contable (NIIF plenas / PYMES) | 🔵 | Parser Informe Aud. Externa |
| 8 | ¿Existen recomendaciones? (Parte III / Otros asuntos) | — | Manual (sí/no + texto) |
| 9 | Firma auditora (AuditConsulting / Partner) | — | Radio → elige plantilla |

La **cabecera tiene 3 campos manuales**: Cliente auditado (1), Ejercicio fiscal
(3) y Fecha de carga del reporte de diferencias al SRI (6). La **fecha de cierre
(2) se deriva** como `31 de diciembre de {ejercicio}` (no es un campo). Los campos
autocompletados por parser (4, 5, 7) son **editables** (override) por si la
extracción falla o requiere ajuste. Recomendaciones (8) y firma (9) son controles
aparte, fuera de la cabecera.

### Param 8 — Recomendaciones

- **No** (default): se mantiene el texto boilerplate *"…informamos que no existen
  recomendaciones sobre aspectos de carácter tributario."* y la Parte III queda
  con su texto estándar de "no hemos identificado observaciones".
- **Sí:** se inyecta el texto de recomendaciones provisto (Parte III / Otros
  asuntos). Redacción exacta de la variante "sí" a afinar en implementación
  contra ejemplos reales.

## 5. Inputs (botones de carga) — ambos PDF

| Slot | Botón | Formato | Requerido | Extrae |
|---|---|---|---|---|
| `informe_auditoria_externa` | "Subir Informe de Auditoría Externa" | PDF | Sí | Params 4, 7 |
| `declaracion_ir` | "Subir Declaración de Impuesto a la Renta (F-101)" | PDF | Sí | Param 5 |
| `anexo_diferencias_sri` | "Subir Anexo de Diferencias SRI" | PDF | No (M2) | Parte IV (no se procesa en M1) |

### Parser `informe_auditoria_externa.py`  (verificado con PDF real AXXIS)
- **Fecha de emisión (4):** primera fecha larga (`\d{1,2} de <mes> del? \d{4}`)
  tras el título `INFORME DE LOS AUDITORES INDEPENDIENTES`. En la muestra AXXIS →
  `27 de febrero del 2026`. Se normaliza `del` → `de`.
- **Marco contable (7):** si el texto contiene `NIIF para (las) PYMES` o
  `Pequeñas y Medianas` → `pymes`; si no → `plenas`. Muestra AXXIS → `pymes`.

Ambos campos autocompletan el form pero quedan **editables** (override).

### Parser `declaracion_ir.py` (F-101 PDF)  (verificado con PDF real AXXIS)
- **Fecha de declaración del IR (5):** el pie de cada página del F-101 trae
  `FECHA RECAUDACIÓN` con la fecha `dd-mm-yyyy`. Muestra AXXIS → `09-04-2026` →
  se formatea a `09 de abril de 2026` (día/mes/año completos; corrige el
  "09 de 2026" incompleto de la plantilla Partner).

### Fixtures reales (en `tests/fixtures/informe_cumplimiento_tributario/`)
- `informe_auditoria_externa_axxis.pdf` (AXXISGASTRO CIA. LTDA., NIIF PYMES,
  emisión 27-feb-2026)
- `f101_axxis.pdf` (período 2025, recaudación 09-04-2026)
- `reporte_diferencias_axxis.pdf` (para M2 — Parte IV)

> **Independencia del ICT:** aunque el módulo ICT ya tiene un `parse_f101`, esta
> herramienta es independiente. Se puede reutilizar lógica de parsing de fechas
> del F-101 si conviene, pero SIN acoplar esta tool al motor ICT.

## 6. Backend — `backend/app/aud/informe_cumplimiento_tributario/`

Estructura espejo de `obligaciones_fiscales/`:

- `models.py` — **reutiliza `ToolJob`** (tabla `tool_jobs`) con
  `tool_code = "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO"`. **Sin migración
  nueva.** Se guardan además los campos del informe en `summary_json` o, si hace
  falta persistir overrides, se pasan como Form y se guardan en columnas
  existentes / JSON. Los archivos NO van a DB (viven en `/tmp`).
- `file_storage.py` — patrón de storage efímero `/tmp/<job_id>/inputs/<slot>/…`
  + `output.docx`. Se puede reutilizar el helper genérico existente.
- `service.py` — CRUD + `_ensure_project_access` (multi-tenant por proyecto),
  con su propio `TOOL_CODE`.
- `parsers/informe_auditoria_externa.py`, `parsers/declaracion_ir.py` — ver §5.
- `docx_assembler.py` — carga la plantilla de la firma, reemplaza tokens, elimina
  notas instructivas, devuelve bytes `.docx`.
- `templates/opinion_audit_consulting.docx`, `templates/opinion_partner.docx` —
  plantillas tokenizadas (trabajo previo de una sola vez).
- `jobs.py` — `process_job(job_id)`: `mark_running` → lee inputs → corre parsers
  → `docx_assembler.assemble(...)` → escribe `output.docx` → `mark_done(summary)`.
  Excepción → `mark_failed`.
- `router.py` — prefix `/aud/informe-cumplimiento-tributario`:
  - `POST /jobs` (multipart: form + 2 PDFs; valida MIME/size; crea job; guarda
    files; encola BackgroundTask)
  - `GET /jobs/{id}` (poll)
  - `GET /jobs` (lista por proyecto)
  - `GET /jobs/{id}/download` (StreamingResponse del `.docx`; marca descargado)
  - `DELETE /jobs/{id}`
- Registrar el router en el app principal (donde se registra el de
  obligaciones_fiscales).

### Tokens de plantilla

`{{RAZON_SOCIAL}}`, `{{FECHA_CIERRE}}`, `{{EJERCICIO}}`, `{{FECHA_EMISION}}`,
`{{FECHA_DECLARACION_IR}}`, `{{FECHA_CARGA_SRI}}`, `{{MARCO_CONTABLE}}`,
`{{BLOQUE_RECOMENDACIONES}}`.

Las fechas se formatean en español largo (`15 de marzo de 2026`). Tokenizar en
**runs limpios** (un solo `<w:r>` por token) para que el reemplazo sea robusto
frente al split de runs de Word.

## 7. Frontend — `frontend/src/aud/`

- `catalog.js` — a la categoría `CONCLUSION` agregar
  `tools: [{ id: "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO",
  label: "Informe de Cumplimiento Tributario", description: "…" }]`.
- `ToolCatalog.jsx` — enrutar el nuevo `activeTool` al componente.
- `InformeCumplimientoTributarioTool.jsx` — clon de `ObligacionesFiscalesTool.jsx`,
  mismo layout visual (reutiliza clases `of-*`). Orden de la pantalla:
  1. **Cabecera (3 campos manuales):** Cliente auditado (razón social),
     Ejercicio fiscal, **Fecha de carga del reporte de diferencias al SRI** 🟢.
  2. **¿Existen recomendaciones?** (sí/no + textarea) — control aparte.
  3. **Radio de firma** (Audit Consulting Group / Partner Auditing Cía. Ltda.).
  4. **Slots de carga PDF:** Informe de Auditoría Externa (requerido),
     Formulario 101 (requerido), Anexo de Diferencias SRI (opcional, M2).
  5. Campos autocompletados **editables** (override) al procesar: fecha de
     emisión 🟡, marco contable 🔵, fecha de declaración IR 🔴.
  6. Botón Generar → `POST /jobs` → polling cada 2s → descarga `.docx`.
  7. Lista de "recientes".
- `api.js` — `createICTJob`, `getICTJob`, `listICTJobs`, `downloadICTJob`.

## 8. Flujo end-to-end

1. Usuario abre la tool en Conclusión y dictamen.
2. Llena la cabecera (cliente auditado, ejercicio fiscal, fecha de carga SRI 🟢),
   marca recomendaciones, elige firma y sube los 2 PDFs requeridos.
3. `POST /jobs` → job async → parsers extraen params 4 🟡, 7 🔵 (Informe Aud.
   Externa) y 5 🔴 (F-101) → assembler rellena la plantilla de la firma con los
   9 parámetros → `output.docx`.
4. Frontend hace polling; al `done`, descarga el informe Word lleno.
5. El socio revisa/ajusta/firma el `.docx`.

## 9. Verificación (⚠️ regla suprema del proyecto)

Antes de dar por concluida la implementación:
- Probar **ambos parsers contra PDFs reales de cliente** (Informe de Aud. Externa
  y F-101), no solo fixtures. Confirmar que cada param extraído coincide con el
  PDF fuente.
- Generar el `.docx` con datos reales de **ambas firmas** y confirmar que abre en
  Word **sin cuadro de reparación** y que los 9 parámetros aparecen correctos y
  las notas instructivas fueron eliminadas.
- Comparar visualmente el informe generado contra la plantilla oficial de cada
  firma.

## 10. Archivos a crear / modificar

**Crear (backend):**
- `backend/app/aud/informe_cumplimiento_tributario/__init__.py`
- `.../service.py`, `.../jobs.py`, `.../router.py`, `.../docx_assembler.py`
- `.../file_storage.py` (o reutilizar el genérico)
- `.../parsers/__init__.py`, `.../parsers/informe_auditoria_externa.py`,
  `.../parsers/declaracion_ir.py`
- `.../templates/opinion_audit_consulting.docx`,
  `.../templates/opinion_partner.docx` (tokenizadas)
- Tests: parsers (con PDFs reales), assembler (docx abre sin reparación).

**Modificar:**
- Registro del router en el app principal.
- `frontend/src/aud/catalog.js`, `ToolCatalog.jsx`, `api.js`
- **Crear** `frontend/src/aud/InformeCumplimientoTributarioTool.jsx`

## 11. Riesgos / consideraciones

- **Robustez de parsers PDF:** los PDFs de auditoría externa no tienen formato
  fijo garantizado. Mitigación: override manual siempre disponible + confianza
  reportada; si un campo no se extrae, el form queda editable, no bloquea.
- **Reemplazo de tokens en Word:** el split de runs puede romper reemplazos
  ingenuos. Mitigación: tokenizar en runs limpios en el trabajo previo de
  plantilla.
- **Marco contable:** la detección NIIF plenas vs PYMES debe validarse contra
  ejemplos reales; ante ambigüedad, default editable.
