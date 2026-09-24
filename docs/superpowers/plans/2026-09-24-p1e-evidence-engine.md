# P1-E · Evidence engine (Document AI y evidencia) — Plan TDD

> **For agentic workers:** este plan se implementa **en el servidor** (las
> dependencias FastAPI/SQLAlchemy/rapidfuzz/pdfplumber/Vision no corren en el
> contenedor donde se escribió el scaffold). Implementar task-by-task con TDD:
> prueba en rojo → mínimo para verde → refactor. Los pasos usan checkbox
> (`- [ ]`) para seguimiento.

**Goal:** que cada dato que el sistema afirma (un casillero del F-101/F-103, un
importe del mayor, un total de factura) quede **amarrado a su fuente exacta**
(archivo + página + celda/bounding-box) con un **score de confianza** y pueda
**cruzarse contra otra fuente** (factura↔auxiliar, factura↔XML SRI,
factura↔pago) de forma explicable y con validación humana. Es la capa 7 de la
arquitectura de convergencia (Agente E).

**Architecture:** `backend/app/evidence/` con cuatro módulos independientes y
sin estado global:

- `matcher.py` — empareja registros en cuatro modos (exacto / normalizado /
  fuzzy con rapidfuzz / semántico con embeddings opcional) y con tolerancia
  numérica y de fecha. Cierra DOC-005/006/007, DQ-006, ANA-020.
- `citation.py` — el contrato `SourceReference` (§2) + `BoundingBox`, y las
  funciones que capturan página y caja desde **pdfplumber** (`extract_words`)
  y desde **Google Vision** (`bounding_poly`). Cierra DOC-008/009.
- `confidence.py` — score 0..1 por campo, con dos ejes separados (extracción vs
  interpretación) y desglose trazable. Cierra DOC-011.
- `crossref.py` — la matriz de evidencia dato→fuente→cita con estado de
  validación humana. Cierra DOC-010.

**Principio rector (CLAUDE.md · verificación previa):** una cita nunca se
inventa; si no se pudo localizar el dato, `bounding_box=None` y la confianza de
extracción baja. El emparejador nunca elige por el auditor: ante ambigüedad
devuelve TODOS los candidatos con estado `AMBIGUA`.

**Tech Stack:** Python 3.11, `dataclasses`, `Decimal`, `enum`, `pytest`.
Dependencias nuevas: `rapidfuzz` (fuzzy, obligatoria para ese modo). Opcional:
proveedor de embeddings (Voyage AI) para el modo semántico. Reutiliza
`pdfplumber==0.11.5` y `pypdf==5.1.0` (ya en `requirements-prod.txt`) y el
cliente de `backend/app/utils/ocr.py`.

**Spec / contrato:** `docs/ARQUITECTURA_CONVERGENCIA_v1.md` §2 (SourceReference)
y §3 (fila del Agente E).

**Convenciones:** español en identificadores, docstrings y comentarios;
importes en `Decimal`; `python -m pytest backend/tests/evidence -q` desde la
raíz del repo. Las pruebas del emparejador semántico y del OCR real se marcan
`@pytest.mark.skipif` cuando falta la dependencia/credencial (nunca golpean red
en CI).

---

## Estructura de archivos

| Archivo | Responsabilidad | Estado |
|---|---|---|
| `backend/app/evidence/__init__.py` | Fachada del paquete (re-exports) | **creado (scaffold)** |
| `backend/app/evidence/matcher.py` | Emparejamiento multi-modo + tolerancias | **creado (scaffold)** |
| `backend/app/evidence/citation.py` | `SourceReference`, `BoundingBox`, captura geometría | **creado (scaffold)** |
| `backend/app/evidence/confidence.py` | Score 0..1 extracción vs interpretación | **creado (scaffold)** |
| `backend/app/evidence/crossref.py` | Matriz de evidencia + validación humana | **creado (scaffold)** |
| `backend/tests/evidence/__init__.py` | Paquete de pruebas | crear |
| `backend/tests/evidence/test_citation_contract.py` | Contrato SourceReference/BoundingBox | crear |
| `backend/tests/evidence/test_citation_pdfplumber.py` | Wrapper de páginas + localización | crear |
| `backend/tests/evidence/test_citation_vision.py` | Geometría de Vision (con fake client) | crear |
| `backend/tests/evidence/test_matcher_helpers.py` | normalización + tolerancias | crear |
| `backend/tests/evidence/test_matcher_fuzzy.py` | fuzzy con rapidfuzz | crear |
| `backend/tests/evidence/test_matcher_emparejar.py` | `emparejar` / `emparejar_lotes` | crear |
| `backend/tests/evidence/test_confidence.py` | dos ejes + niveles + revisión humana | crear |
| `backend/tests/evidence/test_crossref.py` | matriz + estados + `a_filas` | crear |
| `backend/tests/evidence/test_integracion_ict.py` | cita real sobre F-103 de PROPHAR (skip si falta) | crear |
| `requirements-prod.txt`, `requirements.txt` | agregar `rapidfuzz` | modificar |
| `backend/app/evidence/embeddings_voyage.py` | proveedor de embeddings (opcional) | crear (opcional, tarea 9) |

---

## Cómo tocar `ocr.py` y los parsers SIN romperlos (wrappers)

Regla de propiedad: el Agente E **no modifica** `backend/app/utils/ocr.py`,
`backend/app/ict/parsers/f101_pdf.py` ni `f103_pdf.py`. Todo lo nuevo vive en
`backend/app/evidence/`. La geometría que hoy se pierde se recupera con dos
**wrappers paralelos**:

1. **pdfplumber (parsers F-101/F-103).** Hoy hacen
   `"\n".join(p.extract_text() for p in pdf.pages)` → se pierde la página y
   toda coordenada. `citation.extraer_paginas_pdfplumber(pdf_bytes)` itera
   `enumerate(pdf.pages)` y devuelve `list[PaginaTexto]` con `numero` (1-based),
   `texto` y `palabras` (de `page.extract_words()`, con `x0/x1/top/bottom`). Los
   parsers **siguen igual**; este es un segundo camino que consume el crossref y,
   más adelante, el refactor de los parsers. Para que un parser cite sin
   reescribirse, se ofrece además
   `source_reference_desde_pdfplumber(...)`, que dado el texto de una página y el
   ancla del casillero devuelve la `SourceReference` con su caja.

   *Migración futura sugerida (fuera de este PR, Agente F/G):* el
   `find_casillero_value(text, num)` de los parsers puede pasar a operar por
   página (`PaginaTexto.texto`) en lugar de sobre el texto concatenado; así el
   valor y su página salen juntos. Mientras tanto, el join actual y el wrapper
   conviven sin conflicto.

2. **Google Vision (ocr.py).** `ocr.ocr_pdf` descarta `bounding_poly`.
   `citation.ocr_pdf_con_geometria(pdf_bytes)` **reutiliza el cliente cacheado**
   `ocr._get_client()` (mismas credenciales, mismo split de 5 páginas de
   `ocr._split_pdf_pages`) y recorre
   `full_text_annotation.pages[].blocks[].paragraphs[].words[]` quedándose con
   `word.bounding_box` (vértices) y `symbol.confidence`. Devuelve
   `list[PaginaVision]`. `ocr.py` no cambia; si algún día se quiere una única
   fuente, se propone (Agente G) extraer un `ocr._annotate_pdf(pdf_bytes)`
   interno que ambos consuman, pero **no es requisito** de este plan.

   > Nota: importar `ocr._get_client` es acceso a un símbolo "privado" de otro
   > paquete. Es deliberado y está documentado aquí; la alternativa (duplicar la
   > construcción del cliente Vision en evidence) sería peor. Si el Agente G
   > publica un `ocr.get_client()` público, cambiar el import en un renglón.

---

### Task 1: Contrato `SourceReference` + `BoundingBox`

**Files:** Modify `citation.py`; Test `test_citation_contract.py`.
Cierra la base de DOC-008/009 (el contrato §2). Sin dependencias externas.

- [ ] **Step 1 — Pruebas en rojo:**
  - `hash_de_archivo(b"abc")` es hex de 64 chars y determinista (ya
    implementado en el scaffold; test lo fija como contrato).
  - `source_id_de(hash, "p3#cas550")` es estable entre llamadas y distinto para
    ubicaciones distintas.
  - `BoundingBox.desde_palabra_pdfplumber({"x0":1,"x1":9,"top":2,"bottom":5})`
    → `x0=1,y0=2,x1=9,y1=5,unidad="pt"`, `ancho==8`, `alto==3`.
  - `BoundingBox.desde_bounding_poly_vision(poly_normalizado)` con
    `normalized_vertices` → `unidad="norm"`; con `vertices` → `unidad="px"`;
    toma el envolvente min/max.
  - `BoundingBox(...,unidad="px",ancho_pagina=100,alto_pagina=200).normalizado()`
    → coords en 0..1; si ya es `norm`, se devuelve igual.
  - `SourceReference(...).con_cita_documental(3, bbox)` devuelve copia con
    `page=3` y `bounding_box=bbox` (frozen → copia, no mutación).
- [ ] **Step 2 — Rojo:** `pytest ...test_citation_contract.py -q` →
  `NotImplementedError`.
- [ ] **Step 3 — Verde:** implementar los `classmethod`/métodos y
  `source_id_de` (hash corto de `file_hash+"|"+ubicacion`). `normalizado()`
  divide por ancho/alto; valida que estén presentes salvo `norm`.
- [ ] **Step 4 — Refactor + correr:** suite de la tarea en verde.
- [ ] **Step 5 — Commit:** `feat(evidence): contrato SourceReference y BoundingBox`.

---

### Task 2: Wrapper pdfplumber — páginas + localización (DOC-008/009)

**Files:** Modify `citation.py`; Test `test_citation_pdfplumber.py`.

- [ ] **Step 1 — Pruebas en rojo** (construir un PDF de prueba con `pypdf`/
  `reportlab` mínimo, o un PDF fixture pequeño en `backend/tests/evidence/fixtures/`):
  - `extraer_paginas_pdfplumber(bytes)` de un PDF de 2 páginas → 2 `PaginaTexto`
    con `numero` 1 y 2, cada una con `ancho/alto>0` y `palabras` no vacío.
  - `localizar_en_pagina(pagina, "550")` devuelve el `BoundingBox` de esa
    palabra; `localizar_en_pagina(pagina, "NO_EXISTE")` → `None`.
  - Con el valor repetido, `cerca_de="cas550"` elige la ocurrencia más cercana
    al ancla (test con dos "1,234.56", ancla junto a una de ellas).
  - `source_reference_desde_pdfplumber(...)` arma la `SourceReference` con
    `page`, `bounding_box`, `column`, `original_value`, `normalized_value` y
    `metodo="pdfplumber"`.
- [ ] **Step 2 — Rojo.**
- [ ] **Step 3 — Verde:** `extract_words()` por página; búsqueda case/space
  tolerante; desempate por distancia euclídea del centro de la palabra al centro
  del ancla.
- [ ] **Step 4 — Correr.**
- [ ] **Step 5 — Commit:** `feat(evidence): páginas y bounding-box desde pdfplumber (wrapper, sin tocar parsers)`.

---

### Task 3: Wrapper Google Vision — geometría del OCR (DOC-008/009)

**Files:** Modify `citation.py`; Test `test_citation_vision.py`.

- [ ] **Step 1 — Pruebas en rojo (con FAKE client, sin red):**
  - Monkeypatch de `ocr._get_client` por un doble que devuelve un
    `full_text_annotation` fabricado (pages→blocks→paragraphs→words→symbols con
    `bounding_box.vertices` y `confidence`). `ocr_pdf_con_geometria(bytes)` →
    `list[PaginaVision]` con palabras geolocalizadas y su `confianza`.
  - `source_reference_desde_vision(...)` arma la `SourceReference` con
    `metodo="ocr"` y la caja en `unidad="px"` (o `norm` según el fake).
  - Si `ocr.is_available()` es False → levanta `OCRUnavailable` (mismo contrato
    que el resto de la plataforma).
- [ ] **Step 2 — Rojo.**
- [ ] **Step 3 — Verde:** reutilizar `ocr._split_pdf_pages` para el batch de 5;
  recorrer la jerarquía de Vision; `word` sin símbolos legibles → confianza 0 y
  caja igual, texto de la unión de símbolos.
- [ ] **Step 4 — Correr.**
- [ ] **Step 5 — Commit:** `feat(evidence): geometría OCR desde Vision reutilizando ocr._get_client`.

---

### Task 4: Helpers del emparejador — normalización y tolerancias

**Files:** Modify `matcher.py`; Test `test_matcher_helpers.py`. Sin rapidfuzz.

- [ ] **Step 1 — Pruebas en rojo:**
  - `normalizar_texto(" ANDES  S.A. ")` == `"andes sa"` (trim, minúsculas,
    colapsa espacios, quita tildes y puntuación); `normalizar_texto(None)==""`.
  - `dentro_de_tolerancia_numerica(Decimal("100.00"), Decimal("100.00"))` →
    `(True, 1.0)`; `(100.00, 100.01, tol_abs=0.01)` → `(True, ~1.0)`;
    `(100.00, 101.00, tol_rel=0.005)` → `(False, <1.0)`; diferencia 0 → 1.0.
  - `dentro_de_tolerancia_fecha(d1, d1)` → `(True,1.0)`;
    `(f, f+3d, tol_dias=5)` → `(True, ~0.33)`; `(f, f+6d, tol_dias=5)` → `(False,0.0)`.
  - `CriterioEmparejamiento(campos).pesos_normalizados()` suma 1.0.
  - `similitud_campo` despacha por tipo (NUMERO/FECHA/TEXTO exacto y normalizado)
    sin tocar rapidfuzz.
- [ ] **Step 2 — Rojo.**
- [ ] **Step 3 — Verde:** implementar helpers en `Decimal`; `normalizar_texto`
  con `unicodedata.normalize("NFKD", ...)` y filtro de `str.isalnum()`/espacios.
- [ ] **Step 4 — Correr.**
- [ ] **Step 5 — Commit:** `feat(evidence): normalización de texto y tolerancias numérica/fecha`.

---

### Task 5: Modo fuzzy con rapidfuzz (dependencia nueva)

**Files:** Modify `matcher.py`, `requirements-prod.txt`, `requirements.txt`;
Test `test_matcher_fuzzy.py`.

- [ ] **Step 1 — Agregar dependencia:** `rapidfuzz>=3.9,<4` en
  `requirements-prod.txt` y `requirements.txt` (es C-extension, wheels
  disponibles para el buildpack Python de Render; no requiere Docker buildpack,
  a diferencia de Tesseract — ver nota en `ocr.py`).
- [ ] **Step 2 — Pruebas en rojo:**
  - `similitud_fuzzy("ANDES S.A.", "Andes S A")` > 0.85.
  - `similitud_fuzzy("ANDES S.A.", "COMERCIAL XYZ")` < 0.5.
  - `similitud_texto(a, b, ModoEmparejamiento.FUZZY)` usa el wrapper y respeta
    orden de tokens (`token_sort_ratio`).
- [ ] **Step 3 — Rojo → Verde:** `similitud_fuzzy` = `token_sort_ratio/100`
  sobre texto ya normalizado; import de rapidfuzz aislado en esa función.
- [ ] **Step 4 — Correr** (skip elegante si rapidfuzz no está instalado en el
  entorno de dev: `pytest.importorskip("rapidfuzz")`).
- [ ] **Step 5 — Commit:** `feat(evidence): modo fuzzy con rapidfuzz`.

---

### Task 6: `emparejar` y `emparejar_lotes` (DOC-005/006/007, DQ-006, ANA-020)

**Files:** Modify `matcher.py`; Test `test_matcher_emparejar.py`.

- [ ] **Step 1 — Pruebas en rojo (casos del negocio):**
  - **factura↔auxiliar:** criterio {`numero` normalizado, `ruc` exacto, `total`
    numérico tol 0.01, `fecha` tol 0}; 1 candidato casa → `UNICA`, `mejor.score`
    ≥ umbral.
  - **factura↔XML SRI:** `clave_acceso` exacto casa aunque el resto difiera.
  - **factura↔pago:** `beneficiario` fuzzy + `importe` + `fecha` tol 5 días →
    casa un pago 3 días después.
  - **AMBIGUA:** dos candidatos idénticos sobre el umbral → estado `AMBIGUA`,
    `coincidencias` trae ambos ordenados, `mejor` = el de mayor score, nada se
    descarta.
  - **SIN_COINCIDENCIA:** ningún candidato pasa el umbral.
  - `modo=SEMANTICO` sin `embeddings` → `ValueError` (no cae a otro modo).
  - **campo obligatorio en 0** descarta al candidato aunque el resto sume.
  - `emparejar_lotes(..., uno_a_uno=True)`: un candidato no se reutiliza;
    reporta consultas sin par y candidatos sobrantes (DQ-006).
- [ ] **Step 2 — Rojo.**
- [ ] **Step 3 — Verde:** score = promedio ponderado de `similitud_campo` por
  los campos del criterio; `es_match = score>=umbral`; estado por conteo de
  matches; `emparejar_lotes` = asignación golosa por score desc con pool que se
  consume.
- [ ] **Step 4 — Correr.**
- [ ] **Step 5 — Commit:** `feat(evidence): emparejar y emparejar_lotes con tolerancias y estados`.

---

### Task 7: Confianza por campo, dos ejes (DOC-011)

**Files:** Modify `confidence.py`; Test `test_confidence.py`.

- [ ] **Step 1 — Pruebas en rojo:**
  - `confianza_extraccion("excel")` ≈ 0.98; `("ocr", ocr_word_confidence=0.5)`
    baja proporcional; `source_ref` con `bounding_box=None` penaliza; método
    desconocido → base conservadora.
  - `confianza_interpretacion(resultado_match=<UNICA score 0.95>)` alta;
    `<AMBIGUA>` penaliza fuerte; `<SIN_COINCIDENCIA>` baja pero >0;
    `mapeo_conocido=False` penaliza.
  - `evaluar_campo(...)` arma `ConfianzaCampo` con ambos ejes y sus aportes;
    `confianza_global == min(extraccion, interpretacion)`.
  - `nivel_de(0.9)==ALTA`, `nivel_de(0.7)==MEDIA`, `nivel_de(0.4)==BAJA`.
  - `requiere_revision_humana` True si algún eje < `UMBRAL_MEDIA`.
- [ ] **Step 2 — Rojo → Step 3 — Verde:** sumar `AporteConfianza` firmados
  desde la base y acotar a [0,1]; propiedades leen los umbrales del módulo.
- [ ] **Step 4 — Correr.**
- [ ] **Step 5 — Commit:** `feat(evidence): confianza por campo separando extracción de interpretación`.

---

### Task 8: Matriz de evidencia + validación humana (DOC-010)

**Files:** Modify `crossref.py`; Test `test_crossref.py`.

- [ ] **Step 1 — Pruebas en rojo:**
  - `MatrizEvidencia().agregar("F101.cas550","Total ingresos",Decimal("1000"),[ref])`
    crea entrada `PENDIENTE`; segundo `agregar` del mismo `dato_id` suma fuentes
    sin duplicar por `source_id`; `es_corroborado` True con ≥2 fuentes.
  - `entrada.marcar(VALIDADO, por="jvinicio")` fija estado, `validado_por` y
    `validado_en`.
  - `por_estado`, `pendientes_de_revision` (incluye las de confianza baja,
    ordenadas por confianza asc), `sin_evidencia` (entrada con `source_refs=[]`).
  - `resumen()` cuenta por estado + total + `sin_evidencia`.
  - `a_filas()` produce una fila por (dato × source_ref) con las columnas del
    docstring, lista para el filler del papel de trabajo.
- [ ] **Step 2 — Rojo → Step 3 — Verde.**
- [ ] **Step 4 — Correr.**
- [ ] **Step 5 — Commit:** `feat(evidence): matriz de evidencia con estados de validación humana`.

---

### Task 9: Integración con el ICT + embeddings opcional + verificación empírica

**Files:** `test_integracion_ict.py`; opcional `embeddings_voyage.py`.

- [ ] **Step 1 — Cita real sobre un PDF del cliente (skip si no está):** con un
  F-103 real de PROPHAR (mismo fixture que usa
  `tests/test_ict_parser_formato_numerico.py::TestExtractCasillerosPDFRealPROPHAR`),
  `extraer_paginas_pdfplumber` + `source_reference_desde_pdfplumber` debe
  producir una `SourceReference` con `page` y `bounding_box` para el cas 349
  (subtotal país). **Verificación previa (CLAUDE.md):** contar cuántos casilleros
  devuelve `parse_f103` y verificar que se logra cita para el mismo conjunto (o
  reportar honestamente los que no se pudieron localizar).
- [ ] **Step 2 — Embeddings opcional (modo semántico):** implementar
  `embeddings_voyage.py::VoyageEmbeddings` (cumple el `Protocol`
  `ProveedorEmbeddings`) usando `VOYAGE_API_KEY`. Test con
  `pytest.importorskip`/`skipif` sin credencial. Documentar que Anthropic
  recomienda Voyage para embeddings (el SDK `anthropic` no expone embeddings).
- [ ] **Step 3 — Correr toda la suite:** `pytest backend/tests/evidence -q` en
  verde; `pytest -k "evidence or ict" -q` sin regresiones.
- [ ] **Step 4 — Commit:** `test(evidence): integración con F-103 real + embeddings Voyage opcional`.

---

## Qué queda para el servidor (no se hace en el contenedor de scaffold)

1. **Todo el cuerpo de las funciones** (hoy `NotImplementedError`): los cuatro
   módulos están tipados y con contrato fijo; la lógica se escribe a verde en el
   servidor con `pdfplumber`, `rapidfuzz` y el cliente Vision disponibles.
2. **Instalar `rapidfuzz`** en `requirements-prod.txt`/`requirements.txt` y
   redeploy (Render).
3. **Modo semántico:** decidir proveedor de embeddings (Voyage AI recomendado),
   agregar `VOYAGE_API_KEY` a las env vars de Render y la dependencia
   `voyageai`. Es OPCIONAL: sin él, los modos exacto/normalizado/fuzzy cubren la
   conciliación estándar.
4. **Wiring en la plataforma (Agentes F/G, fuera de este paquete):**
   - que los parsers F-101/F-103 emitan `SourceReference` por casillero usando
     `source_reference_desde_pdfplumber` (o el refactor por página sugerido);
   - que el filler del papel de trabajo (Agente F) vuelque `MatrizEvidencia.a_filas()`
     a una hoja EXCEL nueva (que **no** viaje al archivo SRI — regla de
     separación del CLAUDE.md; va solo en `ICT_PAPEL_TRABAJO.xlsx`);
   - persistencia del estado de validación humana (SQLAlchemy) y su audit trail
     (`auditbrain-audit-trail-generator`), integrados con la cola del Agente D
     (`ExecutionRun`).
5. **OCR con geometría en producción:** requiere
   `GOOGLE_APPLICATION_CREDENTIALS_JSON` (ya documentado en `ocr.py`) y consume
   unidades de Vision igual que `ocr_pdf`.
6. **Verificación empírica final (CLAUDE.md):** correr sobre los 12 F-103 / 12
   F-104 / 1 F-101 de PROPHAR y confirmar que cada dato del A1..A9 tiene su
   `SourceReference` localizable, contando fuente-por-fuente contra el PDF real
   antes de declarar la capacidad IMPLEMENTADA.
