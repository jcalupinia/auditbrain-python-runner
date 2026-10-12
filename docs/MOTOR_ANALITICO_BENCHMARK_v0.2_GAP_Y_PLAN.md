# Motor de Auditoría Analítica — Comparación contra benchmark v0.2 y plan de acción

> **Qué es esto.** Comparación a profundidad (archivo:línea) entre lo que **tiene
> hoy** el Motor de Auditoría Analítica y lo que **exige** el benchmark v0.2
> (`arquitectura_audit_ia_benchmark`), más un **plan de acción punto por punto**
> para cubrir todo el benchmark. Verificado contra el código vigente de dos repos:
> `jcalupinia/motor-auditoria-analitica` (motor forense, servicio externo) y
> `jcalupinia/auditbrain-python-runner` (plataforma + frontend del tool).
>
> **Fecha:** 2026-10-11 · **Método:** 3 relevamientos en paralelo, solo lectura.
> Supersede a `motor-auditoria-analitica/docs/BENCHMARK_GAP_MATRIX_v1.md`
> (2026-09-24), hoy desactualizado respecto del código.

> **Actualización 2026-10-12 — HITO 0 ejecutado y corrección de este doc.**
> Al ejecutar el HITO 0 se verificó archivo:línea contra `main` del motor y se
> encontró que **tres de los cinco ítems ya estaban resueltos** cuando este doc
> se escribió (el relevamiento quedó desactualizado en esos puntos):
> - **0.1 `/motor/muestreo`** y **0.2 `/motor/trabajos/{id}/papel`**: **ya
>   existen** en `servicio/app.py:1157` y `:1138` (motor PR #19, 2026-10-02), con
>   sus helpers `muestreo_servicio.py` / `papel_muestreo.py` / `papel_bases.py`.
>   **No había 404 que cerrar.**
> - **0.4 VTA-010**: **ya trae `nia=`** (`taac_ventas.py:624`). El catálogo está
>   completo (38/38 con norma NIA).
> - **0.3** (reglas huérfanas) sí estaba pendiente y **se resolvió**: PRV-006,
>   GAS-004 y GAS-005 recibieron caller en `demo.correr_reglas`
>   (motor PR #20); el demo pasó de 441 → 445 excepciones, con test de regresión
>   que garantiza que las 38 del catálogo tengan caller.
> - **0.5** `paginas.js`: `bases`/`sri`/`muestras` marcadas `operativa:true`
>   (plataforma PR #359).
> - El contador **«38 pruebas»** queda honesto (38 catalogadas = 38 ejecutables).
>
> Las tablas y hallazgos abajo se corrigen en consecuencia (marcados «↻ 2026-10-12»).
> PRs: `motor-auditoria-analitica#20`, `auditbrain-python-runner#359`.

## 0. Veredicto en una página

El motor es **excepcionalmente fuerte en su núcleo**: analítica determinista
(§13) con partes **superiores** al benchmark (JOIN con ambos anti-joins, MUS con
evaluación de error, muestreo de atributos y variables clásicas), **Decimal** en
todo monto material, evidencia sellada (REP-013 con versión de reglas y
parámetros), permiso JWT de vida corta y gateway LLM local-first **con el motor
deliberadamente SIN LLM** («Python calcula, el LLM no recalcula»).

Lo que falta para igualar el benchmark se concentra en **cuatro frentes**, en
orden de impacto:

1. **Fundación de orquestación/persistencia (§18)** — *↻ 2026-10-12: resuelto en
   HITO 1.* El store de trabajos ahora es persistente (Postgres vía `DATABASE_URL`,
   motor #21), con idempotencia (#21), cancelación (#22) y scheduler por cron (#23);
   reintentos e historial ya existían. Default sigue en memoria sin la env.
   Pendiente aparte: persistir las fuentes subidas (raw zone) y repartir la
   ejecución entre procesos.
2. **Cableado end-to-end** — *↻ 2026-10-12: resuelto en HITO 0.* Los 2 endpoints
   (`/motor/muestreo`, `/motor/trabajos/{id}/papel`) **sí existían** en `main`; las
   **3 reglas** catalogadas sin ruta de ejecución (PRV-006, GAS-004, GAS-005)
   **ya tienen caller**; `bases`/`sri`/`muestras` quedaron marcadas operativas.
   Sigue pendiente lo que de verdad falta: secciones nuevas (`reportes`, `niif`).
3. **Ingesta (§11)** — solo entra xlsx/csv/tsv + XML-SRI; falta **ZIP** (lotes de
   XML del SRI), PDF/DOCX, IESS/bancos. (Conectores a BD/API: fuera por decisión.)
4. **Capas de 3.ª/4.ª generación** — ML no supervisado (§15 N2), citación
   documental fina (§16), eventos/webhooks (§7), modos de IA local explícitos (§19).

**Conclusión:** sí es viable tener «todo lo que dice el benchmark», pero no todo
vale lo mismo. Lo primero es **arreglar lo que ya existe y no se puede usar** (bajo
costo, alto impacto) y **poner la fundación de orquestación**; recién después, las
capas nuevas (ML, documental fina, agentic).

---

## 1. Matriz de comparación por capa del benchmark

Estados: ✅ Cubierta · 🟡 Parcial · 🔴 No cubierta · ⭐ Superior · ⚪ N.A.

### §13 Motor analítico determinista
| Capacidad | Estado | Evidencia |
|---|---|---|
| filter, computed fields, append/union | ✅ | `motor/primitivas.py:52,480,442` |
| join / full outer + anti-joins | ⭐ | `primitivas.py:182-250` (6 tipos) |
| duplicates, gaps/seq, aging, stratification, summarization | ✅ | `primitivas.py:256,272,140,95,60` |
| Benford, statistical summaries, MAD | ✅ | `primitivas.py:320,385,634` |
| sampling random/systematic/stratified | ✅ | `muestreo_metodos.py:193,238,299` |
| MUS con evaluación de error, atributos, variables clásicas | ⭐ | `muestreo.py:107-332`, `muestreo_metodos.py:405-594` |
| cross-file reconciliation | ✅ | `conciliacion.py:25-84` |
| **Decimal en montos materiales** | ✅ | `nucleo.py:27,46-81` (float solo en estadística no monetaria) |
| sort/index como primitiva de 1.ª clase | 🟡 | interno (`primitivas.py:492`); falta verbo `ordenar()` |
| relate multi-tabla encadenable | 🟡 | se cubre con JOIN; no hay RELATE sin materializar |
| **fuzzy duplicates** | ✅ | *↻ 2026-10-12:* **sí existe** (`motor/similitud.py`, `rapidfuzz`), expuesto por HTTP (`test_analitica_duplicados_difusos_por_http` pasa) |
| **top/bottom** | 🔴 | no existe verbo dedicado |
| **regresión básica (OLS)** | 🔴 | no existe |

### §11 Ingesta y conectores
| Capacidad | Estado | Evidencia |
|---|---|---|
| XLSX/XLSM, CSV/TSV | ✅ | `ingesta/mayor.py:469,411` |
| XML-SRI (comprobantes) | ✅ | `sri.py:208-293` |
| .xls binario / .txt delimitado | 🟡 | openpyxl no lee .xls; `.txt` no se rutea |
| **ZIP (lotes de XML SRI)** | 🔴 | no hay descompresión |
| **PDF/DOCX/imágenes a modelo canónico** | 🔴 | solo en otro repo (ICT/robot) |
| Conectores BD (SQLServer/PG/MySQL/Oracle), REST/SOAP | 🔴 (por decisión) | `ingesta/conectores.py:16-19` |
| ERPs por archivo (genérico/SIGMAN/Contifico) | 🟡 | `ingesta/conectores.py:60-202` (export, no en vivo) |
| **IESS / bancos** | 🔴 | sin conector |
| Raw Zone inmutable | 🟡 | solo sha256, no se persiste el crudo versionado |

### §12 Preparación y calidad
| Capacidad | Estado | Evidencia |
|---|---|---|
| normalización fechas/números/monedas | ✅ | `calidad.py:59`, `nucleo.py:46` |
| perfilado de nulls, reconciliación de totales | ✅ | `calidad.py:123`, `barreras.py:29` |
| data lineage básico | ✅ | `ingesta/tipos.py:58-80` |
| **inferencia de esquema** | 🔴 | valida contra esquema dado, no lo infiere |
| **máscara de validez por fila** | 🟡 | cuenta inválidos; no bitmap por fila |
| **schema drift entre períodos** | 🟡 | detecta al apilar; no entre corridas |

### §14 Motor de pruebas NIIF/NIA (paquete versionado)
| Atributo | Estado | Evidencia |
|---|---|---|
| objetivo, inputs, parámetros, cálculo, excepciones, evidencia | ✅ | `nucleo.py:226-306`, `suficiencia.py:31` |
| versión + sello (hash ruleset/parámetros) | ✅ | `nucleo.py:237,209`, `exportar_excepciones.py:152,191` |
| tests unitarios | ✅ | `tests/test_taac*.py` |
| **norma NIA** | ✅ | *↻ 2026-10-12:* 38/38; VTA-010 **ya trae `nia=`** (`taac_ventas.py:624`) |
| **conclusión en el paquete** | 🔴 (por diseño) | el motor no concluye; la firma el auditor |
| **tests de aceptación por regla (golden)** | 🟡 | hay aceptación agregada (demo), no golden por regla |

### §15 Motor estadístico / ML
| Nivel | Estado | Evidencia |
|---|---|---|
| N1 z-score, Benford, MAD, histograma/estratos | ✅ | `taac_compras.py:715`, `primitivas.py:320,537,634` |
| N1 **cuartiles/IQR, correlación, regresión** | 🔴 | no existen |
| N1 z-score robusto aplicado en regla | 🟡 | primitiva MAD existe; GAS-006 usa desv. clásica |
| N2 **Isolation Forest/LOF/clustering** | 🔴 | `scikit-learn` declarado, **sin uso** |
| N3 ML supervisado | 🔴 | no existe |
| gobierno de **reglas** (umbral/override/explicabilidad) | ⭐ | `riesgo.py:39,73,114` |
| gobierno de **modelos ML** (registry/fingerprint) | 🔴 | no hay modelos |

### §16 Motor documental y evidencia
| Capacidad | Estado | Evidencia |
|---|---|---|
| OCR | ✅ | plataforma `ingesta/ocr_support.py:61` |
| matching exacto (clave de acceso SRI) | ✅ | `sri.py:1-13` |
| structured extraction | 🟡 | limitado a F101/F103 |
| **layout / bbox** | 🔴 | se descarta la geometría |
| **matching fuzzy/semántico** | 🟡 | *↻ 2026-10-12:* `rapidfuzz` **sí se usa** (dedup difuso, `motor/similitud.py`); falta matching semántico/embeddings para evidencia documental |
| **citación por página/coordenada** | 🟡 | archivo sí; página/bbox no |

### §17 Agentes y LLM · §19 IA local
| Capacidad | Estado | Evidencia |
|---|---|---|
| motor SIN LLM (por diseño) | ⚪✅ | `motor/__init__.py:3`, `riesgo.py:12` |
| LLM router / gateway local-first | ✅ | `backend/app/chat/providers.py:360` |
| human approval gate (ciclo NIIF) | ✅ | `aud/niif/ciclo/` |
| Agent Runtime del encargo | 🔴 | solo Forge (código), no el encargo |
| run-trace hash-chain del encargo | 🟡 | solo Forge |
| **rutas por política de tarea/sensibilidad** | 🟡 | hoy es failover por disponibilidad |
| **modos local-only / hybrid / cloud explícitos** | 🔴 | emergen de qué claves hay |

### §18 Orquestación
| Capacidad | Estado | Evidencia |
|---|---|---|
| jobs asíncronos (202 + polling) | ✅ | `servicio/app.py:835,879` |
| logs estructurados, aislamiento por encargo | ✅🟡 | `app.py:171`, `trabajos.py:110` |
| **store de trabajos persistente** | ✅ | *↻ 2026-10-12 (HITO 1.1, motor #21):* `servicio/store.py` `StoreSQL` (Postgres vía `DATABASE_URL`); sobrevive a reinicios. Default sigue en memoria sin la env |
| **scheduler, retries, idempotencia, cancelación** | ✅ | *↻ 2026-10-12 (HITO 1, #21/#22/#23):* retries (previo), idempotencia (#21), cancelación (#22), scheduler `/motor/continuo/tick` por cron (#23). Colas por prioridad: no (fuera de alcance) |
| límites CPU/mem por job | 🟡 | hay `MAX_BYTES`, rate-limit, `MAX_PENDIENTES` |

### §20 Seguridad y trazabilidad · §7 API
| Capacidad | Estado | Evidencia |
|---|---|---|
| permiso JWT vida corta, verificación robusta | ✅ | `router.py:38`, `servicio/token.py:43` |
| hash de archivos, sello REP-013, versión reglas/parámetros | ✅ | `exportar_excepciones.py:125-191` |
| secretos por env, clave SRI no registrada | ✅ | `token.py:37`, `app.py:454` |
| **audit log append-only persistente del encargo** | 🟡 | solo Forge; overrides en memoria |
| **cifrado en reposo** (si se persiste) | 🟡 | *↻ 2026-10-12:* con `DATABASE_URL` los trabajos se persisten (HITO 1.1); el cifrado en reposo queda a cargo del Postgres gestionado (infra), aún no verificado en el repo |
| RBAC real (segregación en el encargo) | 🟡 | roles validados; en NIIF «todo ADMIN» |
| REST + descubribilidad de operaciones | ✅ | `servicio/app.py:278-337` |
| **endpoints `/motor/muestreo` y `/trabajos/{id}/papel`** | ✅ | *↻ 2026-10-12:* **ya existen** (`servicio/app.py:1157` y `:1138`, motor PR #19); no hay 404 |
| **webhooks / eventos push** | 🔴 | solo polling |

---

## 2. Estado por SECCIÓN del tool (lo que hay que «terminar»)

La UI define 10 páginas (`frontend/src/aud/motorAnalitico/paginas.js`). *↻
2026-10-12:* además de `mayores`, ahora `bases`, `sri` y `muestras` están
`operativa:true` (plataforma PR #359), por tener UI+lógica real sobre endpoints
vivos del motor.

| # | Sección | Estado real | Qué falta para terminarla |
|---|---|---|---|
| 1 | **Mayores y diarios** | ✅ OPERATIVA. Corren 8 AST + GAS-006 (`programa.py:38-53`); barreras de cuadre previas | Cablear CON/VTA/PRV/GAS al camino «mayor» (o unificar con el de plantilla); ingesta ERP |
| 2 | **Estados financieros** | UI real, pero depende del **Motor de balances** (otro servicio), no del motor forense | Es BLOQUE 2; fuera de este motor |
| 3 | **Bases de datos** (ventas/compras/gastos/proveedores) | ✅ *↻ 2026-10-12:* reglas CON/GAS/VTA/PRV corren por plantilla; endpoint de papel `/motor/trabajos/{id}/papel` **existe**; 3 reglas huérfanas **cableadas**; marcada operativa | Ingesta ERP; unificar con el camino mayor |
| 4 | **Cumplimiento SRI** | Mucho backend (parseo `sri.py`, robot de descarga, cruces `app.py:380-762`), UI extensa; *↻ 2026-10-12:* marcada operativa | Unir descarga→parseo→reglas en un solo encargo (HITO 2) |
| 5 | **Políticas contables NIIF** | 🔴 solo tarjeta `<EnConstruccion>` | Backend completo (es construcción nueva) |
| 6 | **Selección de muestras** | ✅ *↻ 2026-10-12:* backend de cálculo (MUS/NIA 530, atributos, variables) + endpoint `/motor/muestreo` **existen**; marcada operativa | — |
| 7 | **Reportes** | 🔴 solo tarjeta; el sellado existe a nivel motor | Endpoint de reporte + UI |

**Hallazgos de coherencia (quick wins) — ↻ 2026-10-12: TODOS RESUELTOS en HITO 0:**
- ~~`/motor/muestreo` y `/motor/trabajos/{id}/papel` no existen → 404.~~ **Falso al
  2026-10-11**: ya existían en `main` (motor PR #19, `servicio/app.py:1157` y `:1138`).
  El doc quedó desactualizado; no había 404.
- ~~PRV-006, GAS-004, GAS-005 sin caller → «38» vs 35 ejecutables.~~ **Cableadas**
  en `demo.correr_reglas` (motor PR #20): 38 catalogadas = 38 ejecutables; el
  contador «38 pruebas» (`MotorAnaliticoTool.jsx:74`) queda honesto.
- ~~VTA-010 sin `nia=`.~~ **Falso al 2026-10-11**: ya traía `nia=` (`taac_ventas.py:624`).
- ~~`bases`, `sri`, `muestras` `operativa:false`.~~ Marcadas `operativa:true`
  (plataforma PR #359).

---

## 3. Plan de acción punto por punto

Orden por **impacto/costo**, no por número de capa. Cada hito: rama `claude/…`,
pruebas (M14) + mutación donde aplique (M20), datos ficticios (M35), PR en
borrador, **compuerta del socio (M23)**. El motor sigue **sin LLM** (decisión de
diseño que el benchmark valida).

### HITO 0 — Coherencia y cableado de lo que YA existe ✅ *(HECHO 2026-10-12)*
PRs: `motor-auditoria-analitica#20`, `auditbrain-python-runner#359`.
- 0.1 Endpoint **`/motor/muestreo`** (+ papel) — ✅ **ya existía** en `main`
  (`servicio/app.py:1157`, motor PR #19). No había 404.
- 0.2 Endpoint **`/motor/trabajos/{id}/papel`** (xlsx/html) — ✅ **ya existía**
  (`servicio/app.py:1138`). No había 404.
- 0.3 **Ruta de ejecución** a PRV-006, GAS-004, GAS-005 — ✅ **cableadas** en
  `demo.correr_reglas` (motor PR #20) sobre la población de gastos; test de
  regresión `tests/test_correr_reglas_cobertura.py` garantiza que ninguna regla
  del catálogo quede sin caller. Contador «38 pruebas» honesto (38 = 38).
- 0.4 `nia=` a **VTA-010** — ✅ **ya lo tenía** (`taac_ventas.py:624`).
- 0.5 `paginas.js`: `bases`, `sri`, `muestras` marcadas `operativa:true`
  (plataforma PR #359) + test `paginas.test.js`.
*Criterio cumplido:* sin 404 desde el frontend; «N pruebas» = N ejecutables; UI
coherente. Verificación: motor `716 passed, 8 skipped`; frontend `53 passed`.
*Nota:* el relevamiento del 2026-10-11 marcó 0.1/0.2/0.4 como pendientes cuando ya
estaban en `main`; el único trabajo de código real fue 0.3 (+ coherencia de UI).

### HITO 1 — Fundación de orquestación/persistencia (§18) ✅ *(HECHO 2026-10-12)*
PRs del motor: #21 (store + idempotencia), #22 (cancelación), #23 (scheduler).
Al ejecutarlo se verificó que **1.2-reintentos y 1.3 ya existían** en `main`.
- 1.1 **Store de trabajos persistente** — ✅ `servicio/store.py`: interfaz
  `StoreTrabajos` + `StoreEnMemoria` (default) y `StoreSQL` (SQLAlchemy, SQLite en
  pruebas / **Postgres en prod vía `DATABASE_URL`**). Un trabajo sobrevive a un
  redeploy y lo ven todos los procesos. (#21)
- 1.2 **Idempotencia** — ✅ `crear()` reutiliza una corrida `listo` idéntica previa
  (clave = encargo + origen + sha del contenido + parámetros + versión del
  catálogo); **reintentos** ✅ (ya existían, backoff 1s/2s/4s); **cancelación** ✅
  `POST /motor/trabajos/{id}/cancelar` (en cola se cancela de verdad; procesando
  termina en `cancelado` en el próximo punto seguro). (#21, #22)
- 1.3 **Historial de corridas + comparación** — ✅ ya existía
  (`servicio/historial.py` SQLite sellado REP-013 + `continuo.py`).
- 1.4 **Scheduler** — ✅ `POST /motor/continuo/tick` (barrido de monitores
  vencidos) disparado por un cron externo (Render Cron / systemd timer), autenticado
  con `MOTOR_CRON_SECRET`. Evalúa las fuentes server-reachable (hoy `demo`); las de
  `mayor`/`plantilla` siguen con el heartbeat del navegador. (#23)
*Criterio cumplido:* un job sobrevive a redeploy; re-ejecución idempotente;
historial consultable. Suite del motor: 749 passed, 8 skipped.
*Activación en prod (Render):* setear `DATABASE_URL` (Postgres) y `MOTOR_CRON_SECRET`
+ un cron al tick. Sin esas variables el servicio sigue idéntico.
*Pendientes del §18 como decisión aparte (no en estos PRs):* persistir las fuentes
subidas (raw zone cifrada) para monitores de `mayor`/`plantilla` desatendidos
(toca privacidad), y el reparto de la ejecución entre procesos (hoy el registro se
comparte, pero la ejecución vive en el proceso que creó el trabajo).

### HITO 2 — Completar las secciones de datos (§13/§14 de entrega)
2.1 **Bases de datos operativa end-to-end**: papel por base (ventas/compras/gastos/
   proveedores), marcar operativa.
2.2 **Cumplimiento SRI unificado**: descarga → parseo `sri.py` → reglas CON/VTA en
   un solo encargo con papel.
2.3 **Mayores**: cablear el resto de familias al camino mayor o unificar con plantilla.
*Criterio:* cada sección entrega papel de trabajo sellado y reproduce un ejemplo de control.

### HITO 3 — Cerrar §13 y §15-N1 (analítica faltante)
3.1 Verbos `ordenar()`, `top()/bottom()`, `duplicados_difusos()` (rapidfuzz, ya
   declarado), **regresión OLS**, **cuartiles/IQR**, correlación. Todo determinista, con tests.
3.2 Aplicar **z-score robusto (MAD)** en GAS-006 (la primitiva ya existe).
*Criterio:* checklist §13 completo; pruebas unitarias + mutación por verbo.

### HITO 4 — Ingesta (§11/§12)
4.1 **ZIP** de XML del SRI (lo más usado en Ecuador), **.txt delimitado**, ruteo por contenido.
4.2 **Inferencia de esquema**, **máscara de validez por fila**, **schema drift** entre períodos.
4.3 Decisión sobre `Polars/DuckDB/PyArrow` (adoptar para volumen o retirar del
   `requirements` para no sobredeclarar). Raw Zone inmutable.
*Criterio:* ingesta de un lote ZIP real (sintético); perfil de calidad por fila.

### HITO 5 — Documental fino (§16)
5.1 Citación por **página/coordenada (bbox)**, matching **fuzzy/semántico**
   (rapidfuzz + embeddings) para evidencia sin clave SRI, extracción de tablas genéricas.
*Criterio:* del hallazgo se vuelve a la página/coordenada del documento fuente.

### HITO 6 — Riesgo/ML no supervisado (§15 N2) *(explicable, no bloqueante)*
6.1 **Isolation Forest/LOF/clustering** (PyOD/sklearn, ya declarados) como
   enriquecimiento aislado y **explicable** (SHAP); con **model registry** (versión,
   features, fingerprint, métricas). Nunca sustituye a las reglas deterministas.
*Criterio:* score ML reproducible, versionado y explicado; el cálculo financiero no depende de él.

### HITO 7 — IA local, API y agentic (§7/§17/§19)
7.1 **Modos explícitos** local-only / hybrid / cloud + enrutado por política de tarea.
7.2 **Webhooks/eventos** push (hoy solo polling).
7.3 (Opcional, 4.ª gen.) Agent Runtime del encargo con tool registry y gates humanos.
*Criterio:* modo local-only verificable; evento push al completar un job.

### HITO 8 — Reportes y Políticas NIIF (secciones nuevas)
8.1 **Reportes**: constructor + exportación sellada end-to-end.
8.2 **Políticas contables NIIF**: backend (hoy placeholder).

---

## 4. Secuencia recomendada y dependencias

```
HITO 0 (coherencia/404)  ── ✅ HECHO (2026-10-12; PRs motor#20, plataforma#359)
HITO 1 (persistencia)    ── ✅ HECHO (2026-10-12; PRs motor#21/#22/#23)
HITO 2 (secciones datos) ── depende de HITO 0 (papel/endpoints) y se apoya en HITO 1
HITO 3 (§13/§15-N1)      ── independiente; aditivo sobre primitivas
HITO 4 (ingesta)         ── independiente; ZIP es el de mayor retorno diario
HITO 5 (documental)      ── tras HITO 4
HITO 6 (ML N2)           ── tras HITO 1 (reproducibilidad) y HITO 3 (estadística)
HITO 7 (IA local/API)    ── tras HITO 1
HITO 8 (reportes/NIIF)   ── último; se apoya en todo lo anterior
```

**Arranque sugerido:** HITO 0 y HITO 1 ✅ hechos. Sigue el **HITO 2** (completar
secciones de datos: Bases de datos end-to-end, Cumplimiento SRI unificado, cablear
familias al camino mayor) o el **HITO 3** (§13/§15-N1, aditivo). Cada hito se cierra
con su PR y tu aprobación (M23).

---

*Documento de trabajo. Comparación verificada contra código 2026-10-11. El plan se
ejecuta hito por hito previa aprobación del socio.*
