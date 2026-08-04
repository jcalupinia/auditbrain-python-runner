# Mayor General de Impuestos — ETL clasificador y workspace estilo ICT

**Fecha:** 2026-08-04
**Herramienta:** AUD · Auditoría de Obligaciones Fiscales (`AUD.IMPUESTOS.OBLIGACIONES_FISCALES`)
**Estado:** diseño aprobado, pendiente de plan de implementación

## Problema

La herramienta pide hoy un mayor separado por concepto (`Mayor de Compras`, `Mayor de Ventas`).
Ambos slots están **muertos**: el router los guarda en disco
(`router.py:132-135`) y `jobs.py:34-35` los lista, pero ninguna cédula los consume —
DM6 y DM7 leen únicamente los PDFs F-104. El auditor termina armando a mano, en Excel,
la separación del mayor por categoría fiscal (archivo `BASE DE IMPUESTOS.xlsx` del cliente).

Además la pantalla es un formulario plano, mientras que el ICT del portal de clientes ya
tiene un lenguaje de *workspace* (panel maestro, chips de documentos, barra de progreso,
grid numerado de anexos) que el usuario quiere replicar.

## Objetivo

1. **Un solo slot principal**: `Mayor General de Impuestos`. El auditor deja de subir un
   mayor por concepto.
2. Un **ETL determinista** que lee ese mayor, clasifica cada cuenta en su categoría fiscal,
   reconoce naturaleza (activo/pasivo/ingreso), identifica contrapartidas y aprende de las
   correcciones del auditor.
3. El papel de trabajo pasa a incluir **hoja de clasificación** (trazabilidad) y **cédulas de
   conciliación libros vs. declaraciones**, además de las DM6/DM7 actuales.
4. Se conserva una **modalidad manual** para subir un mayor específico cuando el auditor
   ejecuta una prueba puntual.
5. La pantalla adopta el **diseño del workspace ICT**.

## Decisiones tomadas (con el usuario, 2026-08-04)

| # | Decisión | Alternativas descartadas |
|---|---|---|
| 1 | Salida: **cruce libros vs declaraciones + hoja de clasificación** | Solo alimentar DM6/DM7; solo hoja de clasificación |
| 2 | Formato del mayor: **varía por ERP** → autodetección de encabezados + mapeo manual de columnas como respaldo | Asumir un layout fijo |
| 3 | Taxonomía: **catálogo abierto configurable** (semilla de sistema con las categorías reales) | Catálogo hardcodeado |
| 4 | Historial de homologaciones: **solo por cliente** | Dos niveles cliente+firma; global; sin persistencia |
| 5 | **Paso de revisión en pantalla** antes de generar el Excel | Directo al Excel |
| 6 | Modalidad manual: **slot secundario plegable + categoría declarada** | Toggle de modalidad; autodetección de "prueba puntual" |
| 7 | Motor: **reglas deterministas con scoring multi-señal, sin IA** | Reglas + LLM para el residuo; LLM-first |
| 8 | UI: **portar las clases `pc-*` del ICT** al Command Center | Extraer un design system a `frontend-shared`; recrear con clases propias |
| 9 | **Sesión persistente con subida incremental** de slots, como el ICT | Envío único; persistencia solo del mayor |

## Datos reales de referencia (cliente MEDI, ejercicio 2025)

Carpeta del auditor: `IMPUESTOS MEDI/` (12 F-103, 12 F-104, 12 ATS, y tres Excel).
**No se commitean al repo: `auditbrain-python-runner` es público.**

`MAYOR DE IMPUESTOS.xlsx` — 4.680 movimientos, 28 cuentas, 12 columnas:

```
Código | Cuenta | Fecha | Asiento | Documento | Identificación | Persona |
Persona Cruce Cuenta | Descripción | Debe | Haber | Saldo
```

Prefijos de asiento observados: `VTA` (2.554), `RET` (1.393), `COM` (490), `ASI` (226),
`EGR` (10), `NOM` (7). Documentos: `FAC`, `NCT`, `LQC`, `Transf.`, `Asiento`.

`BASE DE IMPUESTOS.xlsx` es el mismo mayor **partido a mano en hojas por categoría**
(IVA COMPRAS, IVA RETENIDO, IVA VENTAS, VENTAS, RET RETNA, RET IVA, IVA DIFERIDO, COMPRAS 0)
con tablas dinámicas. **Es la verdad empírica del ETL**: lo que el sistema produzca debe
coincidir con esas hojas.

Correspondencia verificada (conteo de filas):

| Categoría | Cuentas del mayor | Filas |
|---|---|---|
| IVA COMPRAS | `1.1.5.1.1`, `1.1.5.1.3` | 550 |
| IVA RETENIDO | `1.1.5.2.1` | 58 |
| IVA VENTAS | `2.1.7.4.1` | 155 |
| VENTAS | `4.1.1.x`, `4.1.2.x`, `4.1.4`, `4.1.11` | 2.427 |
| RET RENTA | `2.1.7.2.1/.3/.4/.5/.6/.7/.8/.9/.11` | 1.254 |
| RET IVA | `2.1.7.3.1/.2/.3` | 236 |

`COMPRAS 0%.xlsx` **no sale del mayor**: es un reporte de compras del ERP con otra
estructura (Fecha, Tipo Documento, Autorización, Subtotal IVA 0%…). Queda fuera del alcance
del clasificador; si se necesita, entra como fuente propia en una fase posterior.

**Advertencia de alcance:** el mayor de MEDI está *pre-filtrado* a cuentas de impuestos.
Un Mayor General completo trae todas las cuentas, y solo en ese caso las contrapartidas por
número de asiento están completas. El ETL debe funcionar con ambos.

## Arquitectura

### Ciclo de vida del job (2 fases)

```
[borrador] ──subida incremental de slots──> [borrador]
     │
     └── ▶ Procesar ──> [running] fase 1: leer mayor + clasificar
                              │
                              v
                        [revision]  ← el auditor corrige y aprueba
                              │
                              └──> [running] fase 2: cédulas + Excel ──> [done]
```

`ToolJob.status` gana los valores `borrador` y `revision`. La columna ya es `String(16)`:
no requiere migración. Los estados `pending`/`running`/`done`/`failed`/`expired` se conservan.

### Módulos backend nuevos — `backend/app/aud/obligaciones_fiscales/mayor/`

| Archivo | Responsabilidad única | Depende de |
|---|---|---|
| `reader.py` | Excel/CSV → `list[Movimiento]` normalizados. Autodetecta hoja, fila de encabezado y columnas por sinónimos. Devuelve además `columnas_detectadas` y `columnas_faltantes` | openpyxl |
| `cuentas.py` | Movimientos → `PerfilCuenta`: n° movs, debe, haber, saldo, naturaleza observada, meses activos, prefijos de asiento, contrapartidas | `reader` |
| `senales.py` | Un extractor por señal; cada uno devuelve `[(categoria_codigo, puntaje, motivo)]` | `cuentas`, `catalogo` |
| `clasificador.py` | Combina señales → `(categoria, confianza, justificacion)` | `senales` |
| `catalogo.py` | Categorías configurables + semilla de sistema | modelos |
| `homologaciones.py` | Lectura/escritura del historial por cliente | modelos |
| `conciliacion.py` | Cédula de cruce libros vs. casilleros declarados | `cuentas`, extractores F-104/F-103 |

Contratos entre módulos: dataclasses simples (`Movimiento`, `PerfilCuenta`,
`ResultadoClasificacion`), sin dependencia de SQLAlchemy salvo en `catalogo`/`homologaciones`.
Así el motor se testea sin base de datos.

### Modelo de datos (tablas nuevas, las crea `Base.metadata.create_all`)

**`mayor_categorias`** — catálogo configurable
`id, organization_id (nullable ⇒ semilla global), codigo, nombre, naturaleza_esperada
(activo|pasivo|ingreso|gasto), casillero_f104, casillero_f103, orden, es_sistema, activa`.
Semilla: `IVA_COMPRAS, IVA_VENTAS, IVA_RETENIDO, RET_RENTA, RET_IVA, VENTAS, IVA_DIFERIDO`.

**`mayor_homologaciones`** — historial por cliente
`id, client_id, codigo_cuenta, nombre_norm, categoria_id, tarifa, veces_usada,
creada_por_user_id, created_at, updated_at`, `UNIQUE(client_id, codigo_cuenta)`.
Se escribe al aprobar la revisión, tanto para correcciones como para confirmaciones.
La clave es `client_id` (no `project_id`) para que el aprendizaje sobreviva de un ejercicio
al siguiente.

**`mayor_clasificacion_job`** — foto inmutable por job
`id, job_id, codigo_cuenta, nombre_cuenta, naturaleza, n_movimientos, debe, haber, saldo,
categoria_sugerida_id, categoria_final_id, tarifa, confianza, origen
(historial|reglas|manual|declarada), senales_json, aprobada_por_user_id, aprobada_at`.

### Endpoints nuevos / modificados

| Método | Ruta | Uso |
|---|---|---|
| `POST` | `/aud/obligaciones-fiscales/jobs` | Crea el job en `borrador` (solo metadatos, sin archivos) |
| `PUT` | `/aud/obligaciones-fiscales/jobs/{id}/slots/{slot}` | Sube archivos a un slot (`f104, f103, ats, mayor_general, mayor_especifico, f101`) |
| `DELETE` | `/aud/obligaciones-fiscales/jobs/{id}/slots/{slot}` | Quita los archivos de un slot |
| `POST` | `/aud/obligaciones-fiscales/jobs/{id}/procesar` | Dispara la fase 1 |
| `GET` | `/aud/obligaciones-fiscales/jobs/{id}/clasificacion` | Devuelve las cuentas clasificadas para la pantalla de revisión |
| `PUT` | `/aud/obligaciones-fiscales/jobs/{id}/clasificacion` | Guarda las correcciones del auditor |
| `POST` | `/aud/obligaciones-fiscales/jobs/{id}/aprobar` | Persiste homologaciones y dispara la fase 2 |
| `GET` | `/aud/obligaciones-fiscales/categorias` | Catálogo de categorías de la organización |

Los slots `mayor_compras` y `mayor_ventas` **se eliminan** del router, `jobs.py`,
`file_storage.py`, `strings.js` y del frontend. Los jobs históricos ya generados siguen
siendo descargables: no se toca nada de lo producido.

## Motor de clasificación

Cada señal aporta puntaje a una o más categorías y **deja registrado su motivo**, que es lo
que se imprime en la hoja de trazabilidad.

| Señal | Peso | Comportamiento |
|---|---|---|
| Historial del cliente | dominante | Match exacto `client_id + codigo_cuenta` ⇒ se aplica y corta la evaluación (confianza **alta**, origen `historial`). Match por `nombre_norm` con código distinto ⇒ puntaje 60, pasa por revisión |
| Nombre de la cuenta | 40 | Regex de dominio: `IVA.*(compra\|adquisic\|importac)`, `IVA.*venta`, `IVA\s*retenido`, `diferido`, `venta\|ingreso\|servicio`. Extrae la tarifa con `Ret\.?\s*(\d+[.,]?\d*)\s*%` |
| Código | 15 | Primer dígito ⇒ naturaleza esperada (1 activo, 2 pasivo, 3 patrimonio, 4 ingreso, 5/6 gasto) |
| Propagación por rama | 25 | Si una cuenta hermana del mismo prefijo (`2.1.7.2.*`) ya está homologada, sus hermanas heredan la sugerencia |
| Naturaleza observada | 10 y **veto −30** | Saldo deudor/acreedor persistente. Si contradice la `naturaleza_esperada` de la categoría, la penaliza fuerte |
| Movimientos | 10 | Prefijo de asiento dominante: `VTA`→ventas, `RET`→retenciones, `COM`→IVA compras |
| Contrapartidas | 15 | Cuentas del mismo N° de asiento. Si la contrapartida dominante ya está clasificada, refuerza la categoría coherente. **Si el mayor viene filtrado, la señal no aporta y no penaliza** |
| Descripción/glosa | 5 | Patrones frecuentes (`Asiento de Retención`, `IMPUESTOS <MES> <AÑO>`) |

**Confianza:**
- `alta` — historial exacto, o líder ≥ 60 con ventaja ≥ 25 sobre el segundo ⇒ llega pre-aprobada.
- `media` — líder ≥ 35 ⇒ requiere confirmación.
- `baja` — el resto ⇒ requiere decisión del auditor.

**Tarifa**: se extrae del nombre y se guarda por cuenta; es lo que permite el desglose por
porcentaje de retención (1 %, 1,75 %, 2,75 %, 3 %, 10 %, 30 %, 70 %, 100 %).

**Mayor específico (modalidad manual)**: la categoría la declara el auditor en el formulario.
No pasa por el clasificador (origen `declarada`), pero sí alimenta las hojas de detalle.

**Números**: el parseo de importes reutiliza la heurística obligatoria del proyecto
(`_parse_amount_sri` en `cedulas/base.py`): soporta `178.259,63` y `178,259.63`.

**Filas basura**: se descartan filas sin código de cuenta, filas de totales/subtotales del ERP
(código vacío con importes) y filas de encabezado repetido.

## Salidas del Excel (fase 2)

1. **CLASIFICACIÓN** — trazabilidad: cuenta, naturaleza, categoría final, tarifa, confianza,
   origen y señales que la justificaron.
2. **Una hoja de detalle por categoría** — réplica automática de `BASE DE IMPUESTOS`:
   movimientos clasificados con subtotal por mes.
3. **CONCILIACIÓN** — por categoría y mes: *según libros* vs *según declaración* (casillero
   del F-104/F-103) y diferencia absoluta y relativa.
4. **DM6 y DM7** — sin cambios, siguen saliendo del F-104.

El mapeo categoría → casillero vive en `mayor_categorias.casillero_f104/f103` y se valida
contra los 12 F-104 y 12 F-103 reales de MEDI durante la implementación. **No se asume de
memoria.**

## Frontend

`frontend/src/aud/of/` (nuevo directorio):

| Archivo | Contenido |
|---|---|
| `ObligacionesFiscalesWorkspace.jsx` | Panel maestro: cabecera, barra de contribuyente/acciones, barra de documentos, progreso, grid de tiles |
| `SlotChip.jsx` | Chip de documento con `✓ nombre ×` y subida incremental |
| `RevisionClasificacion.jsx` | Tabla de cuentas con `select` de categoría, confianza, señales y botón *Aprobar y generar* |
| `MapeoColumnas.jsx` | Respaldo cuando el `reader` no detecta las columnas |
| `EditarDatosModal.jsx` | Cliente, período, corte, preparado/revisado por, firma auditora |
| `ofWorkspace.css` | Clases `pc-*` portadas desde `frontend-client/src/shell/shell.css` |

Los tokens (`--accent`, `--panel-2`, `--line`, `--text-soft`, `--accent-dim`) ya existen en
`frontend/src/styles.css` con los mismos valores, así que el workspace respeta los 4 temas
del Command Center sin trabajo adicional.

Mapeo de la interfaz:

| Elemento ICT | Equivalente OF |
|---|---|
| Chip contribuyente + `✏ Editar datos` | Datos del job en modal; la firma auditora pasa de radios a chips |
| `▶ Procesar` | Dispara la fase 1 |
| Grid numerado de anexos | Grid de cédulas/categorías con estado Pendiente/Parcial/Completado |
| Panel inferior del anexo | Detalle de la cédula; el tile `[0] Clasificación` contiene la pantalla de revisión |
| `📤 Descargar Excel` | Habilitado solo tras aprobar la clasificación |
| `🔄 Encerar` | Descarta el job en borrador y sus archivos |

**Duplicación consciente:** `frontend` y `frontend-client` son dos apps npm independientes
(ver `render.yaml`), sin build compartido. Se copian solo las clases `pc-*` que el workspace
usa. Si en el futuro se quiere una sola fuente, la extracción a `frontend-shared` es mecánica
porque los nombres de clase se conservan idénticos.

## Manejo de errores

| Situación | Comportamiento |
|---|---|
| Encabezado no detectado | El job **no falla**: pasa a `revision` con `requiere_mapeo=true` y la pantalla abre en mapeo manual de columnas |
| Columnas mínimas ausentes tras el mapeo (código, debe/haber) | Error explícito con la lista de columnas encontradas |
| Mayor sin ninguna cuenta reconocible | Job en `revision` con todas las cuentas en confianza `baja`; el auditor clasifica |
| Excel corrupto | `failed` con el mensaje de openpyxl |
| Job aprobado sin F-104 | La conciliación se omite con advertencia; las hojas de detalle igual se generan |
| Cuenta con tarifa ambigua (`Ret. varios %`) | Tarifa `null`, confianza `media` |

## Testing

**Unitario (sin DB):**
- `reader`: formatos numéricos `.` y `,`, encabezado fuera de la fila 1, columnas ausentes,
  filas de totales, hojas múltiples.
- `cuentas`: naturaleza observada, contrapartidas por asiento, meses activos.
- `senales`: un test por extractor, incluido el regex de tarifas.
- `clasificador`: las 28 cuentas reales de MEDI como casos de tabla, veto por naturaleza,
  precedencia del historial, propagación por rama.

**Regresión empírica (la regla suprema del proyecto):**
`tests/test_of_mayor_clasificacion_medi.py` clasifica el `MAYOR DE IMPUESTOS.xlsx` real y
exige los conteos de la tabla de datos de referencia (550 / 58 / 155 / 2.427 / 1.254 / 236).
Los archivos se leen de una ruta local vía variable de entorno `AUD_OF_FIXTURES_DIR` y el test
hace `skip` si no está — mismo patrón que `TestExtractCasillerosPDFRealPROPHAR`.
**Nunca se commitean datos de cliente a este repo público.**

**Integración:**
- Ciclo completo: crear borrador → subir slots → procesar → revisar → aprobar → descargar.
- Aislamiento multi-tenant: un usuario de otra organización no ve ni el job ni sus
  homologaciones.
- Idempotencia: aprobar dos veces no duplica homologaciones.

## Fuera de alcance (explícito)

- Sugerencia por LLM del residuo no clasificado (posible fase 2 del motor; la interfaz del
  clasificador queda preparada).
- Ingestión de `COMPRAS 0%.xlsx` (reporte del ERP con estructura propia).
- Cruce contra el Anexo Transaccional (ATS).
- Homologaciones compartidas entre clientes de la firma.
