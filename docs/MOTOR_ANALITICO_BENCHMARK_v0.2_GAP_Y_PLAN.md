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

## 0. Veredicto en una página

El motor es **excepcionalmente fuerte en su núcleo**: analítica determinista
(§13) con partes **superiores** al benchmark (JOIN con ambos anti-joins, MUS con
evaluación de error, muestreo de atributos y variables clásicas), **Decimal** en
todo monto material, evidencia sellada (REP-013 con versión de reglas y
parámetros), permiso JWT de vida corta y gateway LLM local-first **con el motor
deliberadamente SIN LLM** («Python calcula, el LLM no recalcula»).

Lo que falta para igualar el benchmark se concentra en **cuatro frentes**, en
orden de impacto:

1. **Fundación de orquestación/persistencia (§18)** — el gap más caro: el almacén
   de trabajos es un `dict` en memoria con `--workers 1` que **se pierde al
   reiniciar**. De esto dependen scheduler, reintentos, historial y monitoreo
   continuo.
2. **Cableado end-to-end incompleto** — hay **lógica lista que el usuario no puede
   usar**: 2 endpoints que el frontend llama pero el servicio no expone (→ 404),
   3 reglas catalogadas sin ruta de ejecución, y secciones con UI+lógica marcadas
   «en construcción».
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
| **fuzzy duplicates** | 🔴 | no existe; falta `duplicados_difusos()` |
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
| **norma NIA** | 🟡 | 37/38; **VTA-010 sin `nia=`** (`taac_ventas.py:613`) |
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
| **matching fuzzy/semántico** | 🔴 | `rapidfuzz` declarado, sin uso |
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
| **store de trabajos persistente** | 🔴 | `trabajos.py:76` `dict` en memoria, `--workers 1`, se pierde al reiniciar |
| **scheduler, retries, idempotencia, cancelación, colas por prioridad** | 🔴 | no existen |
| límites CPU/mem por job | 🟡 | hay `MAX_BYTES`, rate-limit, `MAX_PENDIENTES` |

### §20 Seguridad y trazabilidad · §7 API
| Capacidad | Estado | Evidencia |
|---|---|---|
| permiso JWT vida corta, verificación robusta | ✅ | `router.py:38`, `servicio/token.py:43` |
| hash de archivos, sello REP-013, versión reglas/parámetros | ✅ | `exportar_excepciones.py:125-191` |
| secretos por env, clave SRI no registrada | ✅ | `token.py:37`, `app.py:454` |
| **audit log append-only persistente del encargo** | 🟡 | solo Forge; overrides en memoria |
| **cifrado en reposo** (si se persiste) | 🔴 | jobs efímeros hoy |
| RBAC real (segregación en el encargo) | 🟡 | roles validados; en NIIF «todo ADMIN» |
| REST + descubribilidad de operaciones | ✅ | `servicio/app.py:278-337` |
| **endpoints `/motor/muestreo` y `/trabajos/{id}/papel`** | 🔴 | el frontend los llama; **no existen → 404** |
| **webhooks / eventos push** | 🔴 | solo polling |

---

## 2. Estado por SECCIÓN del tool (lo que hay que «terminar»)

La UI define 10 páginas (`frontend/src/aud/motorAnalitico/paginas.js`); solo
`mayores` está `operativa:true`.

| # | Sección | Estado real | Qué falta para terminarla |
|---|---|---|---|
| 1 | **Mayores y diarios** | ✅ OPERATIVA. Corren 8 AST + GAS-006 (`programa.py:38-53`); barreras de cuadre previas | Cablear CON/VTA/PRV/GAS al camino «mayor» (o unificar con el de plantilla); ingesta ERP |
| 2 | **Estados financieros** | UI real, pero depende del **Motor de balances** (otro servicio), no del motor forense | Es BLOQUE 2; fuera de este motor |
| 3 | **Bases de datos** (ventas/compras/gastos/proveedores) | Reglas CON/GAS/VTA/PRV **existen y corren** por el camino plantilla (`trabajos.py:131`) | **Falta endpoint de papel** (`/trabajos/{id}/papel` → 404); marcar operativa; 3 reglas huérfanas |
| 4 | **Cumplimiento SRI** | Mucho backend (parseo `sri.py`, robot de descarga, cruces `app.py:380-762`), UI extensa | Unir descarga→parseo→reglas en un encargo; declarar operatividad |
| 5 | **Políticas contables NIIF** | 🔴 solo tarjeta `<EnConstruccion>` | Backend completo (es construcción nueva) |
| 6 | **Selección de muestras** | Backend de cálculo **existe** (MUS/NIA 530, atributos, variables) | **Falta endpoint `/motor/muestreo`** (→ 404) + papel |
| 7 | **Reportes** | 🔴 solo tarjeta; el sellado existe a nivel motor | Endpoint de reporte + UI |

**Hallazgos de coherencia (quick wins, alto impacto al usuario):**
- `/motor/muestreo` y `/motor/trabajos/{id}/papel` **no existen** pero el frontend
  los llama → **404** en Muestras y en el papel de Bases de datos.
- **PRV-006, GAS-004, GAS-005** catalogadas pero **sin caller** → nunca corren; la
  UI dice «38 pruebas» (`MotorAnaliticoTool.jsx:74`) cuando **35** son ejecutables.
- **VTA-010** sin `nia=`.
- `bases`, `sri`, `muestras` marcadas `operativa:false` pese a tener UI+lógica real.

---

## 3. Plan de acción punto por punto

Orden por **impacto/costo**, no por número de capa. Cada hito: rama `claude/…`,
pruebas (M14) + mutación donde aplique (M20), datos ficticios (M35), PR en
borrador, **compuerta del socio (M23)**. El motor sigue **sin LLM** (decisión de
diseño que el benchmark valida).

### HITO 0 — Coherencia y cableado de lo que YA existe *(bajo costo, alto impacto)*
0.1 Crear endpoint **`/motor/muestreo`** (+ papel) — la lógica ya está en
   `muestreo.py`/`muestreo_metodos.py`; solo falta exponerla. Cierra el 404 de la
   sección Muestras.
0.2 Crear endpoint **`/motor/trabajos/{id}/papel`** (xlsx/html) — cierra el 404 de
   Bases de datos; reutiliza `exportar_excepciones` (REP-006/REP-013).
0.3 Dar **ruta de ejecución** a PRV-006, GAS-004, GAS-005 (o retirarlas del
   catálogo). Alinear el contador «38 pruebas» con lo ejecutable.
0.4 Añadir `nia=` a **VTA-010**.
0.5 Corregir `paginas.js`: marcar `bases`, `sri`, `muestras` según su estado real.
*Criterio:* sin 404 desde el frontend; «N pruebas» = N ejecutables; UI coherente.

### HITO 1 — Fundación de orquestación/persistencia (§18) *(el más importante)*
1.1 **Store de trabajos persistente** (Postgres/Redis) en lugar del `dict` en
   memoria (`trabajos.py:76`); sobrevive a reinicios y `--workers > 1`.
1.2 **Idempotencia** (key = `sha256(datos)+parámetros`), **reintentos**, **cancelación**.
1.3 **Historial de corridas** y comparación contra corrida previa (base de monitoreo continuo).
1.4 **Scheduler** (APScheduler/Render Cron) para ejecuciones programadas.
*Criterio:* un job sobrevive a redeploy; re-ejecución idempotente; historial consultable.

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
HITO 0 (coherencia/404)  ── independiente, hacer YA
HITO 1 (persistencia)    ── fundación; habilita scheduler/retries/historial
HITO 2 (secciones datos) ── depende de HITO 0 (papel/endpoints) y se apoya en HITO 1
HITO 3 (§13/§15-N1)      ── independiente; aditivo sobre primitivas
HITO 4 (ingesta)         ── independiente; ZIP es el de mayor retorno diario
HITO 5 (documental)      ── tras HITO 4
HITO 6 (ML N2)           ── tras HITO 1 (reproducibilidad) y HITO 3 (estadística)
HITO 7 (IA local/API)    ── tras HITO 1
HITO 8 (reportes/NIIF)   ── último; se apoya en todo lo anterior
```

**Arranque sugerido:** HITO 0 (cierra 404 y coherencia, se nota de inmediato) en
paralelo con el diseño del HITO 1 (persistencia). Cada hito se cierra con su PR y
tu aprobación (M23).

---

*Documento de trabajo. Comparación verificada contra código 2026-10-11. El plan se
ejecuta hito por hito previa aprobación del socio.*
