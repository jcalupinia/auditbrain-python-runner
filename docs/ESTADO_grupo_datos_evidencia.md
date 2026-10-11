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
| **1.1** | **Extractor de documentos narrativos** | ✅ **Verificado** |
| **1.2** | **Resolución semántica por IA** | ✅ **Verificado** |
| **1.3** | **Capa de Mapeo Universal** | ✅ **Verificado (esta entrega)** |
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

## Ficha 1.2 — Resolución semántica por IA
**Archivo:** `backend/app/ingesta/semantic_resolver.py` (186 líneas)

### 1. ¿Qué hace?
Último recurso de la escalera determinístico-primero: **desambigua por IA solo
los campos de TEXTO/DESCONOCIDO** que quedaron en la cola de revisión; nunca
cifras ni fechas. `semantic_resolver.py:1-23`; `resolver_dataset` `:171`,
`resolver_campo` `:101`, `resoluble` `:92`.

### 2. ¿Está completo?
**Sí.**
- `resoluble` gatea solo texto/desconocido en revisión (`:92-98`, `_RESOLUBLE_TIPOS`
  `:46`).
- `resolver_campo` con esquema Pydantic estricto (`ResolucionSemantica` `:65-72`),
  reintentos acotados (`:123`), **degradación graciosa** sin lanzar (`:131-136`) y
  **tope MEDIUM** (`_MAP_CONFIANZA` `:49-53`, `_nivel_desde` `:85-89`).
- `resolver_dataset` pasa por los campos y **recalcula** `review_required`
  (`:182-185`).

### 3. ¿Está conectado?
**Sí.** Exportado en `backend/app/ingesta/__init__.py:75-80,128-132`; endpoint
`POST /ingesta/resolver` en `backend/app/api/ingesta.py:160-174` (usa `resoluble`
`:167` y `resolver_dataset` `:168`); `DISCLAIMER_IA` lo reutiliza
`narrativo.py:44,269`; frontend `ResolutorSemanticoTool.jsx` + catálogo
`AUD.INGESTA.RESOLVER`. → **El «Hueco 2» NO aplica.**

### 4. ¿Está probado?
- **M14: SÍ.** `tests/test_ingesta_resolutor_ia.py` (13) + `tests/test_ingesta_resolver.py`
  (4) = **17/17 verdes** (ejecutadas el 2026-10-11).
- **M20 (mutación): cubierto de facto en lo crítico, falta formalizarlo.** Las
  invariantes duras ya están protegidas por pruebas que **fallarían ante la
  mutación correspondiente**: `test_confianza_nunca_sube_a_high` (`:84`) cubre el
  tope MEDIUM; `test_moneda_no_es_resoluble` (`:57`) y `test_fecha_no_es_resoluble`
  (`:62`) cubren «la IA no toca cifras ni fechas». No hay una prueba **rotulada**
  como mutación, pero el riesgo que M20 busca atajar aquí ya está cubierto.

### 5. ¿Respeta el contrato?
**Sí.** Trabaja sobre `CampoExtraido`/`DatasetNormalizado`.
- **«La IA no calcula cifras»: garantizado** por `_RESOLUBLE_TIPOS` (solo
  TEXTO/DESCONOCIDO, `:46`, `:92-98`) y el prompt del sistema (`:55-60`, `:140-151`).
- **«La incertidumbre no se oculta»:** tope MEDIUM (`:49-53`); si el modelo no está
  seguro, el campo queda LOW/REVIEW (`:85-89`); disclaimer disponible (`:40-43`) y
  método IA + warning por campo (`:161-167`).
- **Punto menor a notar (no bloqueante):** `resolver_dataset` modifica los campos
  **in situ pero NO vuelve a sellar** el dataset (`:171-186`, no llama `sellar()`);
  el endpoint `/resolver` selló el dataset en la ingesta previa y lo devuelve con
  ese sello, que queda **desactualizado respecto al contenido ya resuelto por IA**.
  Conviene re-sellar tras resolver, o documentar que el sello corresponde al
  dataset **pre-IA**.

### 6. ¿Qué le falta para estar terminado?
- **Bloqueante:** ninguno.
- **Recomendado:** (a) **re-sellar** el dataset tras `resolver_dataset` (o
  documentar que el sello es pre-IA); (b) rotular/formalizar una **prueba de
  mutación M20** (las invariantes críticas ya están cubiertas de facto).
- **Opcional:** pasar `contexto` por campo en el endpoint (ya soportado en
  `resolver_campo` `:105,146`, pero el endpoint no lo expone).

**Veredicto de la ficha 1.2:** *Completo y conectado; M14 verde (17/17) y las
invariantes críticas (tope MEDIUM, «la IA no toca cifras ni fechas») protegidas
por pruebas. Faltantes recomendados: re-sello tras resolución y una prueba de
mutación rotulada. Sin bloqueantes.*

---

## Ficha 1.3 — Capa de Mapeo Universal
**Carpeta:** `backend/app/ingesta/mapeo/` (`esquemas.py`, `perfilador.py`,
`proponer.py`, `aplicar.py`, `flujo.py`, `__init__.py`)

> ⚠️ **Reencuadre honesto (M01): el plan quedó desactualizado.** El plan trata a
> este motor como «hueco sin construir / en pausa». **No lo está:** su
> construcción base se terminó y se **mergeó** (Fase A3 = librería, PR #349; Fase B
> = endpoints + pantalla, PR #350). Lo que sigue **en pausa/archivado** por
> decisión del socio (PR #351, `docs/INGESTA_MAPEO_MOTOR_ANALITICO_FACTIBILIDAD.md`)
> es su **expansión** (más tipos: gastos/costos/ingresos, kardex…) y su
> **conexión a otras herramientas** — no el motor en sí.

### 1. ¿Qué hace?
*Field-mapping* determinista: acepta un mayor, asiento de diario, balance, ventas
o compras **venga como venga el formato** del cliente y normaliza las columnas al
**esquema canónico** del motor. La máquina **propone** el mapeo columna→campo; el
auditor **confirma** antes de normalizar. **Sin IA.** `esquemas.py`, `perfilador.py`,
`proponer.py`, `aplicar.py`, `flujo.py`.

### 2. ¿Está completo?
**Sí para su alcance base (5 esquemas).** Construido y mergeado: perfilado de la
tabla + detección de encabezado (`perfilador.py`), propuesta con score y confianza
(`proponer.py`), aplicación con `DatasetNormalizado` (`aplicar.py`), flujo en dos
tiempos + hook opt-in (`flujo.py`). **En pausa (confirmado), por decisión del socio
—no es un faltante del motor—:** (a) ampliar a más tipos y (b) conectar su salida a
otras herramientas (PR #351).

### 3. ¿Está conectado?
**Como herramienta independiente: SÍ.** Endpoints `POST /ingesta/mapeo/preparar` y
`POST /ingesta/mapeo/aplicar` (`backend/app/api/ingesta.py:280,326`); frontend
`frontend/src/aud/ingesta/CapaMapeoTool.jsx`, catálogo `AUD.INGESTA.MAPEO`
(`catalog.js:51`), ruta en `ToolCatalog.jsx:100`.
**Como paso del pipeline de ingesta: NO (deliberado).** El hook `ingerir_o_pendiente`
(`mapeo/flujo.py:74`) es **opt-in** y **ningún** caller lo invoca; `orchestrator.py`
**no importa** `mapeo` (intacto). → Disponible como herramienta ✔; no enganchada al
orquestador (por diseño, para no tocar lo probado).

### 4. ¿Está probado?
- **M14: SÍ.** `tests/test_ingesta_mapeo.py` (11) + `tests/test_ingesta_mapeo_api.py`
  (10) = **21/21 verdes** (ejecutadas el 2026-10-11).
- **M20 (mutación): SÍ, formal y rotulada.** `test_caso10_mutacion_sinonimo_rompe_el_caso2`
  (`tests/test_ingesta_mapeo.py:216`) quita un sinónimo del esquema y el caso 2
  **cambia de veredicto** → prueba de que el sinónimo importa. **Es el único motor
  del grupo con una prueba de mutación declarada como tal.**

### 5. ¿Respeta el contrato?
**Sí.** `aplicar_mapeo` devuelve `DatasetNormalizado` con **evidencia por celda**
(hoja·fila·celda), **sello SHA-256** y `quality_score` honesto; aplica **M22**
(campo obligatorio vacío → `None`, **nunca cero**). «La IA no calcula cifras»: **no
aplica** porque el motor es **100 % determinista** (no usa IA).

### 6. ¿Qué le falta para estar terminado?
- **Bloqueante:** ninguno (base completa, conectada como herramienta, M14 + M20
  verdes).
- **Confirmación que pedía el plan:** la **expansión** y la **integración al
  pipeline** siguen **en pausa por decisión del socio** (PR #351). Aquí **no se
  construye nada**.
- **Recomendado (solo si en el futuro se decide integrarla al pipeline):** activar
  el hook opt-in `ingerir_o_pendiente` (hoy inerte) y dejarlo documentado.
- **Acción sobre el plan (no sobre el código):** actualizar el «Hueco 1» — M4 no es
  un hueco sin construir; es una herramienta **terminada** cuya expansión está en
  pausa.

**Veredicto de la ficha 1.3:** *Base COMPLETA, conectada como herramienta y probada
(21/21, M20 incluida). La «pausa» aplica solo a su expansión/integración (decisión
PR #351), no a su construcción. Sin bloqueantes; el plan debe reencuadrar el «Hueco 1».*

---

_Las fichas 1.0 y 1.4–1.5 se agregan a este mismo archivo tras el visto bueno del
socio, en el orden de la §3 del plan._
