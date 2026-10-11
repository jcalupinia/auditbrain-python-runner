# Estado — Grupo Motor de Datos y Evidencia (BLOQUE 1)

> **Etapa de VERIFICACIÓN (solo lectura).** Este informe diagnostica; no se
> modifica código de los motores. Se construye **ficha por ficha**: cada motor
> se agrega **después** del visto bueno del socio sobre el anterior (M23).
>
> Repo: `jcalupinia/auditbrain-python-runner` · rama de verificación
> `claude/estado-datos-evidencia` · base `main` · fecha 2026-10-11.
>
> Método: las seis preguntas de la §2 del plan, con evidencia `archivo:línea`.
> Lo no verificado se declara **pendiente** (regla M01/M37: no se inventa).

## Avance del bloque

| Paso | Motor | Estado de la ficha |
|---|---|---|
| 1.0 | Ingesta y normalización | Pendiente (el plan lo da por «ya verificado»; se confirmará que nada cambió) |
| **1.1** | **Extractor de documentos narrativos** | ✅ **Verificado (esta entrega)** |
| 1.2 | Resolución semántica por IA | Pendiente (tras visto bueno) |
| 1.3 | Capa de Mapeo Universal | Pendiente (en pausa; solo verificar) |
| 1.4 | Piezas de soporte | Pendiente |
| 1.5 | Consolidación (3 huecos + veredicto) | Pendiente |

---

## Ficha 1.1 — Extractor de documentos narrativos
**Archivo:** `backend/app/ingesta/narrativo.py` (345 líneas)

### 1. ¿Qué hace?
Extrae de un documento narrativo (contrato, carta de control interno, informe,
notas a los EEFF) los **datos puntuales** —fechas, montos con moneda, RUCs y
porcentajes— por **regex determinista** con trazabilidad al origen (línea +
fragmento), y **opcionalmente** enumera obligaciones/partes/cláusulas por IA
(solo texto). `narrativo.py:1-22`; orquestador `extraer_narrativo` en `:291`.

### 2. ¿Está completo?
**Sí para su alcance declarado.**
- Núcleo determinista `extraer_campos_narrativos` (`:86-159`): RUC/fecha/%/monto
  con **prioridad de spans** para no confundir un RUC o una fecha con un monto
  (`:122-157`, `_solapa` `:82`), deduplicación (`:94-100`) y tope de 200 campos
  (`:52`, `:118`).
- Capa IA opcional `enriquecer_con_ia` (`:214-274`): esquema Pydantic estricto
  (`:182-190`), **tope MEDIUM** (`:174-178`), disclaimer (`:269`) y **degradación
  graciosa** sin lanzar ante proveedor caído o JSON inválido (`:245-246`, `:274`).
- Orquestación `extraer_narrativo` (`:291-345`): nunca lanza; lee texto plano o
  vía OCR (`_texto_de` `:280-288`); el dataset narrativo **siempre** queda a
  revisión (`:342`).
- *No es hueco, es diseño:* la extracción es best-effort y se verifica contra el
  documento (warnings `:315-318`).

### 3. ¿Está conectado?
**Sí.** Exportado en `backend/app/ingesta/__init__.py:82-85,133-135`; endpoint
HTTP `POST /ingesta/narrativo` en `backend/app/api/ingesta.py:128-145`
(`extraer_narrativo` en `:142`); frontend `frontend/src/aud/ingesta/ExtractorNarrativoTool.jsx`,
entrada de catálogo `AUD.INGESTA.NARRATIVO` (`frontend/src/aud/catalog.js`), ruta
en `frontend/src/aud/ToolCatalog.jsx` y cliente `frontend/src/aud/ingesta/api.js`.
→ **El «Hueco 2 (desconectado)» NO aplica a este motor.**

### 4. ¿Está probado?
- **M14 (pruebas automatizadas): SÍ.** `tests/test_ingesta_narrativo.py`, **10
  pruebas, 10/10 verdes** (ejecutadas el 2026-10-11). Cubren: determinista
  (evidencia por línea, no confunde RUC/fecha con monto, texto vacío), IA (solo
  texto, tope MEDIUM, degradación graciosa, JSON inválido tras reintentos),
  orquestación (siempre `review_required`, la IA suma sin tocar los
  deterministas) y endpoint (`200` + `400` con archivo vacío).
- **M20 (prueba de mutación): PENDIENTE.** No existe una prueba de mutación
  dedicada que **falle** al alterar un umbral: los scores de confianza
  `0.92/0.90/0.85/0.70` (`:124`, `:134`, `:144`, `:156`), el mapa de confianza de
  la IA (`:174-178`) o los regex (`:57-74`) podrían cambiarse sin que ninguna
  prueba rompa. Es un hueco real frente al criterio del plan.

### 5. ¿Respeta el contrato?
**Sí.**
- Devuelve `DatasetNormalizado` (`:332-345`) con `CampoExtraido` + `Evidencia`
  por dato (`:111-113`, `:265-268`) y **sello SHA-256** (`:345`).
- **«La IA nunca calcula cifras»: garantizado.** Los numéricos salen solo de la
  capa determinista por regex (`:122-157`); la IA produce **siempre**
  `TipoDato.TEXTO` (`:261`) y el prompt del sistema se lo prohíbe explícitamente
  (`:168-170`).
- **«La incertidumbre no se oculta»:** el dataset narrativo siempre queda
  `review_required=True` (`:342`) y cada dato IA lleva disclaimer (`:269`); tope
  de confianza IA = MEDIUM (`:174-178`).

### 6. ¿Qué le falta para estar terminado?
- **Bloqueante:** ninguno para su alcance (completo, conectado, M14 verde).
- **Recomendado:** **prueba de mutación M20** que falle si se alteran los
  scores/umbrales de confianza o el tope MEDIUM de la IA.
- **Opcional:** más formatos regionales de fecha/monto en los regex; una prueba
  dedicada de que el *fallback* por OCR marca la nota cuando el PDF viene
  escaneado (`_texto_de` `:280-288`, hoy sin test propio).

**Veredicto de la ficha 1.1:** *Completo y conectado; M14 verde (10/10). Único
faltante frente al plan: la prueba de mutación M20 (recomendado). Sin
bloqueantes.*

---

_Las fichas 1.0 y 1.2–1.5 se agregan a este mismo archivo tras el visto bueno del
socio, en el orden de la §3 del plan._
