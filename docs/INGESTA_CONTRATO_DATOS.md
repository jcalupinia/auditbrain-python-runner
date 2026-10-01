# Contrato de datos — Motor de Ingesta y Normalización (Fase 1)

Este documento describe el **contrato de datos común** que emite el Motor de
Ingesta y Normalización. Es el esquema único de salida para que las
herramientas de auditoría, NIIF y tributación consuman un **dataset
normalizado** en lugar de volver a leer cada documento.

> **Estado:** Fase 1 (aditiva y reversible). Define el contrato (`contract.py`)
> y el motor de confianza (`confidence.py`). Todavía **nada en la plataforma
> importa este paquete**: no cambia ningún flujo existente. Las fases 2+
> (clasificador, orquestador, normalización) lo poblarán.

Ubicación: `backend/app/ingesta/`.

## Principios

1. **Determinístico primero.** `extraction_method` deja explícito cómo se
   obtuvo el dato (nativo → parser → regla → regex → tabla → OCR → IA). La IA
   es el último recurso.
2. **Separar extracción de conclusión.** El contrato SOLO transporta datos
   extraídos con su confianza y su evidencia. NO emite conclusiones NIIF ni de
   auditoría: eso es trabajo de los motores consumidores.
3. **No ocultar la incertidumbre.** Un dato con confianza `LOW` o
   `REVIEW_REQUIRED` queda marcado `review_required=True` automáticamente.
4. **Trazabilidad hasta el origen.** Cada dato puede regresar a
   archivo · página · hoja · fila · celda, y el dataset se puede sellar con
   SHA-256 reproducible.

## Motor de confianza (`confidence.py`)

Niveles (`NivelConfianza`): `HIGH`, `MEDIUM`, `LOW`, `REVIEW_REQUIRED`.

`clasificar_confianza(score)` traduce un puntaje en `[0, 1]`:

| Puntaje | Nivel |
|---|---|
| `>= 0.90` (`UMBRAL_ALTA`) | `HIGH` |
| `>= 0.70` (`UMBRAL_MEDIA`) | `MEDIUM` |
| `>= 0.50` (`UMBRAL_BAJA`) | `LOW` |
| `< 0.50` | `REVIEW_REQUIRED` |

Un puntaje fuera de rango se acota a `[0, 1]`; `NaN` → `REVIEW_REQUIRED`
(nunca lanza: un valor inválido degrada a revisión, no rompe la ingesta).

`requiere_revision(nivel)` → `True` para `LOW` y `REVIEW_REQUIRED`.

Los umbrales son constantes de módulo, ajustables sin tocar la lógica.

## Dato puntual (`CampoExtraido`)

| Campo | Tipo | Descripción |
|---|---|---|
| `document_id` | str | Identificador del documento de origen |
| `document_type` | `TipoDocumento` | f101/f103/f104/ats/balance/mayor/… |
| `entity` | str? | RUC / razón social / tercero |
| `field` | str | Nombre del campo o casillero |
| `raw_value` | str? | Valor tal cual aparece en el origen |
| `normalized_value` | any? | Valor normalizado (Decimal, date, str…) |
| `data_type` | `TipoDato` | texto/entero/decimal/moneda/fecha/ruc/… |
| `currency` | str? | p. ej. `USD` |
| `confidence` | `NivelConfianza` | nivel de confianza |
| `confidence_score` | float? | puntaje `[0,1]` opcional |
| `extraction_method` | `MetodoExtraccion` | cómo se extrajo |
| `evidence` | `Evidencia`? | archivo/página/hoja/fila/celda |
| `warnings` | list[str] | advertencias |
| `review_required` | bool | se fuerza si la confianza lo exige |

Invariantes del validador:

- Si `confidence` es `LOW`/`REVIEW_REQUIRED` ⇒ `review_required=True`.
- Si se da `confidence_score`, se toma el nivel **más conservador** entre el
  explícito y el derivado del puntaje (nunca sube la confianza por encima de
  lo que el puntaje sostiene).

Constructor de conveniencia:

```python
CampoExtraido.desde_score(
    document_id="F104-2025-07", field="cas_799", score=0.97,
    raw_value="178,259.63", normalized_value=Decimal("178259.63"),
    data_type=TipoDato.MONEDA, currency="USD",
    extraction_method=MetodoExtraccion.PARSER, document_type=TipoDocumento.F104,
)
```

## Dataset homologado (`DatasetNormalizado`)

| Campo | Tipo | Descripción |
|---|---|---|
| `dataset_id` | str | Identificador del dataset |
| `source_file` | str | Archivo de origen |
| `document_type` | `TipoDocumento` | tipo de documento |
| `schema_detected` | list[str] | columnas/campos detectados |
| `schema_normalized` | list[str] | esquema normalizado |
| `mapping` | dict[str,str] | detectado → normalizado |
| `validation_results` | list[`ResultadoValidacion`] | reglas aplicadas |
| `quality_score` | float | calidad `[0,1]` |
| `row_count` | int | filas (se deriva de `rows` si viene en 0) |
| `rows` | list[dict] | filas normalizadas (opcional) |
| `campos` | list[`CampoExtraido`] | datos puntuales (opcional) |
| `exceptions` | list[str] | excepciones encontradas |
| `warnings` | list[str] | advertencias |
| `extraction_method` | `MetodoExtraccion` | método predominante |
| `review_required` | bool | se fuerza por calidad baja o campo dudoso |
| `sello` | `Sello`? | sello SHA-256 (ver abajo) |

Invariantes del validador:

- `row_count` se deriva de `rows` si llegó en `0`.
- Calidad que clasifica como `LOW`/`REVIEW_REQUIRED` ⇒ `review_required=True`.
- Cualquier `CampoExtraido` con `review_required` contagia al dataset.

## Trazabilidad (`Sello` y `huella`)

`huella(contenido)` calcula un SHA-256 estable (claves ordenadas; maneja
`Decimal` y `datetime`), reproducible ante el mismo dato.

`DatasetNormalizado.sellar()` adjunta un `Sello` con `contrato_version`,
`generado_en` (UTC) y `sha256` del contenido (excluyendo el propio sello). Es
el equivalente, del lado del contrato, al sello REP-013 del motor forense.

`CONTRATO_VERSION = "1.0.0"`.

## Pruebas

`tests/test_ingesta_contrato.py` (26 pruebas): umbrales de confianza, coacción
de `review_required`, derivación conservadora por puntaje, validación de campos
obligatorios, derivación de `row_count`, contagio de revisión, y sello/huella
reproducibles. Se corren con la versión de producción de Pydantic (2.8.2).

## Fase 2 — Clasificador + orquestador de ingesta

Añade `classifier.py` y `orchestrator.py` (+ `adapters.py`), todavía **sin IA** y
sin cablear a ninguna ruta de la plataforma.

### Clasificador (`classifier.py`)

`clasificar_documento(filename, *, contenido=None, tipo_declarado=None)` →
`ResultadoClasificacion` (tipo, confianza, puntaje, método, razones). Escalera
determinística:

1. **Tipo declarado** por el usuario (nombre de *slot* como en
   `ict/router.py::SLOT_PARSERS`, o valor de `TipoDocumento`) → `HIGH`.
2. **Firma de contenido** (raíz XML del ATS/comprobante SRI, texto
   "FORMULARIO 104/103/101") → `HIGH`.
3. **Palabra clave en el nombre** + extensión → `MEDIUM`.
4. **Solo extensión** (`.xml` ambiguo) → `LOW`.
5. **Nada reconocible** → `DESCONOCIDO` + `REVIEW_REQUIRED`.

Nunca lanza: ante la duda, degrada a revisión.

### Orquestador (`orchestrator.py`)

`ingerir(filename, contenido, *, tipo_declarado=None, extractores=None,
dataset_id=None, sellar=True)` → `DatasetNormalizado`. Flujo:
**clasificar → elegir extractor determinista → normalizar → sellar**.

- Registro `TipoDocumento → Extractor` (un `Extractor` es
  `(bytes, filename) -> DatasetNormalizado`). Por defecto,
  `extractores_por_defecto()` mapea los 8 tipos SRI a adaptadores reales con
  **import perezoso** (importar el orquestador NO carga pdfplumber/openpyxl).
- Nunca tumba la ingesta: si no hay extractor, o el extractor falla, devuelve un
  dataset `review_required` con la excepción registrada.
- Una clasificación dudosa (`LOW`/`REVIEW_REQUIRED`) contagia revisión al dataset.

### Adaptadores (`adapters.py`)

Delegan en los parsers que ya existen (`backend/app/ict/parsers/*`) y traducen su
salida al contrato: F-101/103/104 (casilleros → `CampoExtraido`), mayor, kardex,
ATS, balance mapeado, facturación (→ `rows`). No recalculan nada; solo presentan
lo que el parser entrega, con evidencia (archivo) y confianza. Import perezoso.

Pruebas: `tests/test_ingesta_orquestador.py` (19 pruebas, con extractores falsos;
no requiere dependencias pesadas). Total ingesta: **45 pruebas en verde**.

## Qué viene (fases siguientes, aún no implementadas)

- **Fase 3** — Normalización (tipado/moneda/fechas/duplicados) apoyada en las
  primitivas del motor analítico.
- **Fase 4–6** — Cablear OCR a parsers, Confidence Engine en vivo, AI Semantic
  Resolver (IA solo ante ambigüedad).
- **Fase 7+** — API `/api/v1/ingesta/*` y target real en `master_router`.
