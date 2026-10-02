# Arquitectura — Herramienta «Cobertura de Seguros» (AUDIT-IA / AUDITBRAIN External Audit)

> **Estado: BORRADOR para aprobación del socio.** Primer entregable exigido por el
> «Prompt Maestro» (§35). **No se ha modificado código ni frontend.** La implementación
> (FASE 1–10, §37) **no comienza hasta aprobación explícita del dueño**.
>
> Procesador base existente: `backend/app/aud/niif/procesadores/seguros_cobertura.py`
> (`VERSION = "seguros_cobertura 1.0"`, `RUBRO = "SEGUROS"`). Rama/worktree aislado:
> `herramienta/seguros-cobertura` · `/home/user/auditbrain-seguros-cobertura`.
>
> **Regla rectora (CLAUDE.md + §36):** el **frontend aprobado manda** sobre la UX; el
> **Excel/lógica base de seguros manda** sobre la metodología ya existente; el backend
> **automatiza, no cambia la metodología** sin aprobación. **Cero invención de datos.
> No IA para cálculos. Sin hard-codear un cliente. No duplicar componentes que
> AuditBrain ya tiene.**

---

## 0. Resumen ejecutivo y decisión central

La herramienta `seguros_cobertura` **ya existe** y está operativa como *prueba de riesgo
de cobertura* (un procesador, 2 datasets `activos`/`polizas`, 6 requerimientos de soporte,
7 procedimientos de programa INS-01..07, 15 cédulas, panel, recalc y tests verdes).

El Prompt Maestro pide **expandirla a un módulo documental completo**: 6 requerimientos
con **extracción documental** (pólizas, facturas, notas de crédito, anexos de activos fijos,
anexos de inventarios, mayores contables), **conciliación documento↔contabilidad**,
**cobertura de activos fijos e inventarios**, y **consolidación de hallazgos y ajustes**;
materializado en **7 pruebas (PR-001..007)** sobre el frontend ya aprobado del screenshot.

**La mayor parte de la infraestructura ya existe y se REUTILIZA** (extracción IA genérica,
OCR Google Vision, motor de conciliación en cascada, ensamblador de papeles Excel/HTML/
Word/PPT/PDF, máquina de estados del ciclo). El trabajo nuevo es **contenido de la
herramienta de seguros** (datasets, cédulas, reglas de las 7 pruebas) + **re-alineación de
los 3 bloques de frontend de seguros** al screenshot aprobado + **un puente OCR→extracción**
(infra compartida, a coordinar).

**Decisión de modelado recomendada (requiere confirmación — ver §18, Duda D-3):**
UN solo procesador `seguros_cobertura` (una ficha, un registro `Prueba`, un libro de papel)
cuyas **7 pruebas PR-001..007 son grupos de cédulas** surfaced como las 7 tarjetas de la
Sección 3 del frontend. Es lo que el frontend aprobado ya soporta (tarjetas `ejecuciones`
config-driven) y lo que menos duplica. La alternativa (7 procesadores/registros separados)
se descarta salvo pedido expreso.

---

## 1. Objetivo

Desarrollar dentro de AUDIT-IA la herramienta **Cobertura de Seguros**, integrada al
frontend aprobado (3 secciones: Requerimientos · Procesamiento · Ejecución), que ejecute
procedimientos de auditoría externa sobre pólizas, facturación de seguros, notas de crédito,
seguros pagados por anticipado, cobertura de activos fijos, cobertura de inventarios,
conciliación contable, diferencias, excepciones, hallazgos y ajustes; manteniendo
**trazabilidad, reproducibilidad, evidencia, control de versiones, auditabilidad** y
**separación estricta entre cálculo determinístico e IA**.

## 2. Alcance

Cubre como mínimo (Prompt Maestro §3, A–T): existencia/integridad/exactitud de pólizas y
primas; valuación del gasto y activo de seguros pagados por anticipado; corte; presentación;
cobertura de activos fijos e inventarios; conciliación póliza↔factura↔nota de crédito↔mayor;
vigencias; sumas aseguradas; deducibles; exclusiones; bienes asegurados; activos e inventarios
sin cobertura; diferencias contables; posibles ajustes; hallazgos; y conclusión.

**Aseveraciones** cubiertas (§4): Existencia, Integridad, Exactitud, Valuación, Derechos y
obligaciones, Corte, Clasificación, Presentación y revelación. Cada prueba declara las suyas
en el `program` del procesador (campo `assertion` de cada `INS-xx`).

**Naturaleza NIIF (se preserva del Excel base):** es una prueba de **riesgo y continuidad**
(NIA 315/330/570); **no concluye cumplimiento NIIF por cobertura**. Lo contable que mide es:
(a) la **prima pagada por anticipado** (devengo NIC 1.27–28 / PYMES 2.36) y (b) los
**siniestros pendientes** por tipo (daño a activo propio NIC 16.65–66 y NIC 36; reclamo de
terceros NIC 37.53/86; activo contingente NIC 37.31–35/89; equivalentes PYMES 17.25 y 21).

## 3. Roles (equipo senior simulado)

Se adoptan los 14 roles del §2 del Prompt Maestro como marco de responsabilidad de la
construcción: Socio de Auditoría (metodología, alcance, riesgos, aseveraciones, conclusiones);
Gerente Senior (diseño y supervisión de procedimientos); Auditor Senior de Seguros (pólizas,
coberturas, vigencias, deducibles, exclusiones, primas, endosos); Especialista NIIF/PYMES
(reconocimiento, medición, prima anticipada, presentación, revelaciones); Especialista NIA
(evidencia, pruebas, respuestas a riesgos); Contador Senior (mayores, conciliaciones,
facturación, notas de crédito, asientos); Especialista en Activos Fijos; Especialista en
Inventarios; Data Engineer (ingesta, ETL, datasets, calidad); Arquitecto de Software; Ingeniero
Python (cálculos, reglas, matching); Especialista Document Intelligence (lectura, OCR,
extracción, confidence); QA Engineer; UX Functional Analyst. En el repo, esos roles se
operativizan con las skills `skills/niif-multiagente/` (orquestador, automatización, revisor).

## 4. Requerimientos de información (RQ-001..006)

El frontend aprobado (screenshot) y el Prompt Maestro definen **6 requerimientos**. Hoy el
procesador declara 6 `requests` **con otro mapeo** (RQ-001 Activos, RQ-002 Pólizas, RQ-003
Pólizas/endosos, RQ-004 Tasaciones, RQ-005 Siniestros, RQ-006 Mayor). **Se re-alinea** al
mapeo aprobado (ver Duda D-1):

| RQ | Nombre (frontend aprobado) | Formatos | Dataset generado | Uso | Obligatorio |
|----|----------------------------|----------|------------------|-----|-------------|
| RQ-001 | Pólizas de Seguros | .pdf · .xlsx · .csv | `DS_POLIZAS` | cálculo | Sí |
| RQ-002 | Facturas de Seguros | .pdf · .xlsx · .csv | `DS_FACTURAS_SEGUROS` | cálculo | Sí |
| RQ-003 | Notas de Crédito | .pdf · .xlsx | `DS_NOTAS_CREDITO` | cálculo | Sí |
| RQ-004 | Anexo de Activos Fijos | .xlsx · .csv | `DS_ACTIVOS_FIJOS` | cálculo | Sí |
| RQ-005 | Anexo de Inventarios | .xlsx · .csv | `DS_INVENTARIOS` | cálculo | Sí |
| RQ-006 | Mayores Contables | .xlsx · .csv | `DS_MAYORES` | cálculo | Sí |

Cada RQ permite (ya lo da el frontend genérico): cargar, validar, visualizar, reemplazar,
eliminar, versionar (`ChipDocumento` + `PruebaArchivo` + `prueba.revision`). Los documentos de
soporte opcionales (tasaciones RQ-004 antiguo, reclamos de siniestros) pasan a **«Documentos de
soporte»** del frontend (desplegable), sin perder la evidencia del Excel base.

> **Nota de preservación (Excel base manda):** las sumas aseguradas, deducibles, exclusiones,
> endosos, tasaciones y siniestros que hoy viven en el dataset `polizas` **se conservan**; se
> reorganizan bajo RQ-001 (Pólizas) y sus soportes. Ningún cálculo auditado existente se pierde.

## 5. Arquitectura (componentes y flujo)

```
                         ┌──────────────────── FRONTEND APROBADO (sin rediseño) ───────────────────┐
                         │  VistaProceso.jsx  →  PruebasEncargo.jsx → configDeProcesador("seguros")  │
                         │  Secc.1 Requerimientos · Secc.2 Procesar/Encerar · Secc.3 7 pruebas       │
                         └───────────────▲──────────────────────────────────────────┬──────────────┘
                                         │  GET /pruebas/{id}  (objeto `prueba`)      │ POST /pruebas/{id}/acciones
                                         │                                            │ GET  /pruebas/{id}/libro?formato=
     ┌───────────────────────────────── CICLO (reutilizado, agnóstico al rubro) ─────▼──────────────┐
     │ ciclo/router.py · ciclo/servicio.py (aplicar_accion) · ciclo/reglas.py (13 estados)           │
     │ map_validate (Procesar) · execute · validate · configure · approve · encerar · versiones       │
     │ PruebaArchivo (evidencia) · PruebaEvento (bitácora NIA 230) · revision/base.py (revisor)        │
     └───────┬─────────────────────┬───────────────────────┬────────────────────────┬────────────────┘
             │                     │                        │                        │
   ┌─────────▼────────┐  ┌─────────▼─────────┐   ┌──────────▼──────────┐   ┌─────────▼──────────┐
   │ DOCUMENT INTEL.  │  │  DATASETS (ETL)   │   │  MOTOR DETERMINÍSTICO│   │  PAPEL DE TRABAJO  │
   │ extraccion_ia.py │  │  CAMPOS/validar_  │   │  seguros_cobertura.  │   │  libro.py (xlsx/   │
   │ + ocr.py (puente)│→ │  filas/filas_     │ → │  ejecutar() + recalc │ → │  html/docx/pptx/pdf)│
   │ providers.py     │  │  mapeadas         │   │  conciliacion cascada│   │  datos_cliente/    │
   │ parsers (mayor…) │  │  DS_POLIZAS…      │   │  (N1–N7, importado)  │   │  problemas/marca   │
   └──────────────────┘  └───────────────────┘   └─────────────────────┘   └────────────────────┘
      IA: solo transcribir     determinístico            determinístico          determinístico
```

**Principios de separación (§30/§31):**
- **Determinístico (Python):** todos los cálculos, sumatorias, devengo/amortización,
  conciliaciones matemáticas, porcentajes, diferencias y clasificación por reglas claras.
  Vive en `seguros_cobertura.py::ejecutar()` y en el recalc. Toda cifra del Excel es **fórmula**.
- **IA (solo apoyo):** transcripción/extracción de campos desde documentos (pólizas, facturas,
  NC), interpretación de cláusulas/exclusiones ambiguas, redacción de observaciones/conclusiones
  preliminares. Nunca calcula. Cada salida IA guarda modelo, prompt, respuesta, confidence,
  fuente, usuario y marca de revisión humana (`reg["extraccion"][fileId]`, `auto/revisado`).

## 6. Datasets (DS_*) y diccionario de datos

Cada dataset se declara en el procesador con `campo(key,label,tipo,requerido,alias,ejemplo)`
(helper de `base.py`), se mapea desde el archivo con `filas_mapeadas()` y se valida con
`validar_filas()`. Tipos: `text` · `number` · `date`.

### DS_POLIZAS (RQ-001) — amplía el `polizas` actual
`id` (N° póliza), `aseguradora`, `ramo`, `asegurado`, `beneficiario`, `fecha_emision`,
`vigencia_desde` (date), `vigencia_hasta` (date), `moneda`, `suma_total` (number),
`prima_neta` (number), `impuestos` (number), `prima_total` (number), `prima_anticipada`
(number), `deducible_pct` (number), `cobertura` (text), `bienes_asegurados` (text),
`ubicaciones` (text), `exclusiones` (text), `endosos` (text), `observaciones` (text),
`siniestro` / `monto_siniestro` / `siniestro_revelado` / `tipo_siniestro` / `cobro_exigible`
(se conservan del dataset actual).

### DS_FACTURAS_SEGUROS (RQ-002) — nuevo
`id` (N° factura), `proveedor`, `aseguradora`, `fecha` (date), `autorizacion`, `base` (number),
`impuestos` (number), `total` (number), `poliza` (N° póliza relacionada), `referencia`,
`descripcion`.

### DS_NOTAS_CREDITO (RQ-003) — nuevo
`id` (N° NC), `emisor`, `fecha` (date), `factura` (factura relacionada), `poliza` (póliza
relacionada), `base` (number), `impuestos` (number), `total` (number), `motivo`.

### DS_ACTIVOS_FIJOS (RQ-004) — amplía el `activos` actual
`id` (código), `categoria`, `descripcion`, `ubicacion`, `fecha_adquisicion` (date),
`costo` (number), `depreciacion_acumulada` (number), `valor_libros` (number), `estado`,
`centro_costo`, `poliza` (asignada), `suma_asignada` (number), `valor_referencia` (number),
`deducible_pct` (number). (`valor_libros` sigue siendo el `CONTROL` del procesador.)

### DS_INVENTARIOS (RQ-005) — nuevo
`id` (código), `descripcion`, `categoria`, `ubicacion`, `cantidad` (number),
`costo_unitario` (number), `valor_total` (number), `bodega`, `estado`, `poliza`,
`suma_asignada` (number).

### DS_MAYORES (RQ-006) — nuevo (reusa `ict/parsers/mayor_excel.py::parse_mayor`)
`cuenta`, `descripcion`, `fecha` (date), `comprobante`, `referencia`, `debito` (number),
`credito` (number), `saldo` (number), `tercero`, `auxiliar`, `centro_costo`.

Las hojas `D1_…`/`D2_…` «Origen del dato» (`datos_cliente.con_datos`) se generan solas para
cada dataset entregado, con la columna archivo·hoja·fila (trazabilidad §29).

## 7. Dependencias

- **Runtime ya presente** (requirements): `openpyxl`, `pandas`, `pdfplumber`, `pypdf`, `xlrd`
  (.xls legacy), `python-docx`, `python-pptx`, `Pillow`, `matplotlib`. PDF del papel vía
  `weasyprint` (en imagen Docker; si falta, se obtiene con «Guardar como PDF» del navegador).
- **OCR (opcional):** `google-cloud-vision` + `GOOGLE_APPLICATION_CREDENTIALS_JSON`
  (`utils/ocr.py`, `docs/OCR_SETUP_GOOGLE.md`). Sin esto, PDF escaneado → se pide Excel/CSV.
- **LLM:** cadena `local > gemini > groq > openrouter > anthropic > openai`
  (`chat/providers.py`); `NIIF_EXTRACCION_ENABLED` gobierna la extracción IA.
- **Módulos del repo reutilizados** (importar, no editar; ver §13).

## 8. Document Intelligence Engine (§13 — reutilizar, no duplicar)

**AuditBrain YA dispone de motor transversal.** No se crea un lector documental exclusivo.

| Capacidad | Componente reutilizado (ruta · función) |
|-----------|------------------------------------------|
| Extracción de campos por IA (genérica) | `ciclo/extraccion_ia.py::extraer_filas(campos, texto, …)` + `texto_de_documento` |
| Esquema de extracción | se deriva de los `CAMPOS` del procesador (opt-in `EXTRACCION_DATASETS`) |
| OCR (PDF/imagen escaneada) | `utils/ocr.py::extract_text_smart / ocr_pdf` (Google Vision) |
| Cadena de proveedores LLM | `chat/providers.py::chat_complete` |
| Lectura de mayor contable (Excel) | `ict/parsers/mayor_excel.py::parse_mayor` + `balance_excel.py::_find_header_row/_norm` |
| Lectura de facturación SRI (patrón) | `ict/parsers/facturacion_sri.py::parse_facturacion` |
| Ingesta multiformato segura | `confirmaciones_saldos/parsers.py::extract/bounded_table` (CSV/XLSX/XML/DOCX/PDF/ZIP/img) |

**Puente faltante (a construir, infra compartida → coordinar, Duda D-5):** hoy
`extraccion_ia._texto_pdf` **no invoca OCR**; ante una póliza escaneada lanza error pidiendo
Excel. Para «OCR si corresponde» (§14 PASO 5) hay que puentear `ocr.extract_text_smart` dentro
de `texto_de_documento`. Toca `extraccion_ia.py`/`utils/ocr.py` (compartidos): requiere
coordinación y actualizar `docs/niif/CONTRATO_PROCESADOR.md`.

**Habilitación en seguros:** declarar en `seguros_cobertura.py`
`EXTRACCION_DATASETS = ("polizas","facturas","notas_credito")` (+ opcional `EXTRACCION_ENUMS`
/`EXTRACCION_INSTRUCCIONES`). Con eso, `map_validate` auto-extrae los PDF/Word sin tocar el
motor. Los anexos (activos fijos, inventarios, mayores) siguen siendo Excel/CSV deterministas.

## 9. Botón PROCESAR (§14) — mapeo a `map_validate`

El botón **Procesar** del frontend ya ejecuta la acción `map_validate` de `ciclo/servicio.py`.
Los 13 pasos del §14 se cubren así:

1. Validar requerimientos → cruce `datos["datasets"]` × `reg["requests"]` por `dataset`.
2. Leer archivos → `almacen` + `confirmaciones_saldos/parsers.extract`.
3. Clasificar documentos → por `requerimiento`/`componente` del `PruebaArchivo`.
4. Extraer texto y tablas → `texto_de_documento` / parsers Excel.
5. OCR **solo si corresponde** → puente `ocr.extract_text_smart` (Duda D-5).
6. Mapear campos → `proc.filas_mapeadas(sheet, header, mapping, campos, archivo)` (alias).
7. Normalizar → `validar_filas` + normalización numérica regional (`.`/`,`).
8. Crear datasets → `reg["datasets"]`, `reg["rows"]`, `reg["mappings"]`.
9. Relacionar pólizas↔facturas↔NC↔mayores↔activos↔inventarios → **en `execute`**, motor de
   conciliación (ver §12 PR-004) — no en `map_validate` (que solo arma datasets).
10. Validaciones → `validar_filas` + controles §32.
11. Indicadores preliminares → KPIs del `PANEL` (§24), tras `execute`.
12. Habilitar pruebas → estado `DOCUMENTACION_RECIBIDA` → tarjetas Secc.3 DISPONIBLES.
13. Registrar logs → `PruebaEvento` (bitácora NIA 230).

## 10. Botón ENCERAR (§15) — mapeo a `encerar`

El botón **Encerar** ejecuta `ciclo/servicio.encerar` (exige confirmar nombre del cliente y
descarga previa): reinicia `reg` a vacío, borra `PruebaArchivo` y `PruebaEvento`, estado vuelve
a `PRUEBA_SELECCIONADA`. **NO borra** cliente, proyecto, ficha, metodología ni catálogos. Una
versión `APROBADO` responde `400 APROBADA_NO_SE_TOCA` (NIA 230).

## 11. Pruebas de auditoría PR-001..007 (§16)

Materializadas como las **7 tarjetas** de la Sección 3 (config `procesoConfig.SEGUROS.ejecuciones`,
hoy 9 → se ajusta a 7) y como **grupos de cédulas** del único libro de papel:

| PR | Nombre | Requerimientos | Cédulas (hojas del libro) |
|----|--------|----------------|----------------------------|
| PR-001 | Procedimiento de Cobertura de Seguros | Todos | `00_Programa`, `01_Resumen`, `12_Conclusion`, `15_Lectura` |
| PR-002 | Resumen de Pólizas | RQ-001 | `04_Polizas`, `05_Vigencia`, nueva `R_Resumen_Polizas` |
| PR-003 | Reproceso de Seguros Pagados por Anticipado | RQ-001,002,003,006 | `10_Prima_anticipada`, nueva `R_Devengo` |
| PR-004 | Conciliación Pólizas/Facturación/Contabilidad | RQ-001,002,003,006 | nuevas `C_Conciliacion`, `C_Excepciones` |
| PR-005 | Cobertura de Activos Fijos | RQ-001,004 | `06_Cobertura_activo`, `07_Cobertura_poliza`, `08_Deducibles_exposicion`, `09_Sin_cobertura` |
| PR-006 | Cobertura de Inventarios | RQ-001,005 | nuevas `I_Cobertura_inv`, `I_Sin_cobertura` |
| PR-007 | Hallazgos y Ajustes | Todas | `11_Siniestros`, `13_Ajustes`, `14_Problemas` (consolida excepciones) |

## 12. Lógica, fórmulas y reglas de cada prueba

Notación: `FECHA_CORTE` = corte del encargo; umbrales de `PARAMETROS`
(`coberturaMinima=80`, `sobreseguroDesde=120`, `diasAlerta=30`, `tolerancia=1`, más nuevos
`materialidad`, `toleranciaConciliacion`). **Toda fórmula es auditable y va como fórmula de
Excel** (celdas `fx(formula, valor)`), con su «cómo se calcula» por columna.

### PR-002 — Resumen de Pólizas (RQ-001)
Matriz consolidada con: aseguradora, ramo, N° póliza, fechas (emisión/inicio/vencimiento),
moneda, suma asegurada, prima base, impuestos, prima total, deducible, estado, cobertura,
exclusiones, ubicaciones, observaciones. Cálculos:
- `DIAS_VIGENCIA = vigencia_hasta − vigencia_desde`
- `DIAS_TRANSCURRIDOS = min(FECHA_CORTE, vigencia_hasta) − vigencia_desde`
- `DIAS_POR_VENCER = max(vigencia_hasta − FECHA_CORTE, 0)`
- Clasificación: `ACTIVA` (corte∈[desde,hasta]) · `VENCIDA` (hasta<corte) · `PRÓXIMA A VENCER`
  (`0<por_vencer≤diasAlerta`) · `PENDIENTE DE REVISIÓN` (datos faltantes). Reusa `05_Vigencia`.

### PR-003 — Reproceso de Seguros Pagados por Anticipado (RQ-001,002,003,006)
Recalcula el devengo y el activo por póliza vigente (reusa `10_Prima_anticipada` + recalc):
- `PLAZO_DIAS = vigencia_hasta − vigencia_desde`
- `PRIMA_DIARIA = BASE_POLIZA / PLAZO_DIAS`  (BASE = prima base de póliza/factura, neta de NC)
- `DIAS_CONSUMIDOS = min(FECHA_CORTE, vigencia_hasta) − vigencia_desde`
- `DIAS_PENDIENTES = max(vigencia_hasta − FECHA_CORTE, 0)`
- `GASTO_CALCULADO = PRIMA_DIARIA × DIAS_CONSUMIDOS`
- `ACTIVO_CALCULADO = PRIMA_DIARIA × DIAS_PENDIENTES`
- `DIFERENCIA_GASTO = GASTO_CALCULADO − gasto_según_libros` (RQ-006)
- `DIFERENCIA_ACTIVO = ACTIVO_CALCULADO − activo_según_libros` (RQ-006)
- Clasificación por `materialidad`: `SIN DIFERENCIA` · `DIFERENCIA NO MATERIAL` ·
  `DIFERENCIA MATERIAL` · `REQUIERE AJUSTE`. El resultado principal `ajustePrima` del
  procesador **se conserva** y pasa a leer la base neta de facturas/NC.

### PR-004 — Conciliación Pólizas/Facturación/Contabilidad (RQ-001,002,003,006)
**Motor determinístico reutilizado:** algoritmo en cascada N1–N7 de
`procesadores/conciliacion_reestructurada.py` (importado; **no** se edita), con semántica
propia de seguros escrita en el recalc/ejecutar de seguros. Niveles de matching (§20):
- N1 N° póliza + N° factura · N2 aseguradora + valor + fecha · N3 referencia + valor ·
  N4 matching asistido con `toleranciaConciliacion` configurable.
Identifica: póliza sin factura; factura sin póliza; factura duplicada; NC no aplicada;
diferencia de base/impuestos/prima total; registro contable faltante; registro duplicado;
diferencia contra mayor. Output por fila: `ESTADO_CONCILIACION`, `DIFERENCIA`, `EXCEPCION`,
`REFERENCIA`. Cédulas nuevas `C_Conciliacion` + `C_Excepciones`.

### PR-005 — Cobertura de Activos Fijos (RQ-001,004)
**Reusa la lógica auditada existente** (`06_Cobertura_activo`/`07`/`08`/`09`). Agrupa activos
por categoría (edificios, muebles, maquinaria, equipo electrónico, vehículos, otros) y relaciona
con coberturas (incendio, multiriesgo, robo, vehículos, equipo electrónico, maquinaria):
- `VALOR_LIBROS` · `VALOR_ASEGURADO` (suma asignada o prorrata si la póliza no asigna)
- `DIFERENCIA_COBERTURA = VALOR_LIBROS − VALOR_ASEGURADO`
- `PORCENTAJE_COBERTURA = VALOR_ASEGURADO / VALOR_LIBROS`
- `PORCENTAJE_NO_ASEGURADO = max(VALOR_LIBROS − VALOR_ASEGURADO, 0) / VALOR_LIBROS`
- Clasificación: `COBERTURA TOTAL` · `COBERTURA PARCIAL` · `SIN COBERTURA` ·
  `POSIBLE SOBRESEGURO` (`>sobreseguroDesde`) · `REQUIERE REVISIÓN`. Se conservan deducible/
  regla proporcional y exposición máxima (`08_Deducibles_exposicion`).

### PR-006 — Cobertura de Inventarios (RQ-001,005) — nueva
Analiza por categoría, bodega, ubicación, valor, póliza, suma asegurada, riesgo, exclusión:
- `VALOR_INVENTARIO` · `SUMA_ASEGURADA` · `DIFERENCIA = VALOR_INVENTARIO − SUMA_ASEGURADA`
- `PORCENTAJE_CUBIERTO = SUMA_ASEGURADA / VALOR_INVENTARIO` · `PORCENTAJE_NO_CUBIERTO = 1 − …`
Identifica: inventario sin cobertura; cobertura insuficiente (`<coberturaMinima`); ubicación no
incluida; riesgo excluido; póliza vencida; posible sobreseguro. Cédulas `I_Cobertura_inv` +
`I_Sin_cobertura`.

### PR-001 — Procedimiento (papel de trabajo principal, todos los RQ)
Documenta objetivo, riesgo, aseveraciones, procedimientos, información utilizada, pruebas
ejecutadas, resultados, excepciones, conclusión y referencias. Se arma del `program`
(INS-01..07 ya existentes, ampliados) + `01_Resumen` + `12_Conclusion` + `15_Lectura`.

### PR-007 — Hallazgos y Ajustes (todas)
Consolida automáticamente las excepciones de PR-002..006 en hallazgos con el esquema §23:
`ID, PRUEBA_ORIGEN, CONDICIÓN, CRITERIO, CAUSA, EFECTO, VALOR_USD, RIESGO, RECOMENDACIÓN,
RESPUESTA_ADMINISTRACIÓN, ESTADO, REFERENCIA_PT`. Reusa `14_Problemas` (`res["exceptions"]` +
`REF_PROBLEMAS`) y la skill `auditbrain-audit-findings` para la redacción (borrador, revisión
humana). Tipos de hallazgo del §23 (activos/inventarios sin cobertura, póliza vencida/por
vencer, diferencia contable/factura, NC no aplicada, prima anticipada incorrecta, posible
ajuste, otro) se mapean a los códigos de `exceptions` (hoy 19; se agregan los de conciliación
e inventarios).

## 13. Componentes reutilizables vs nuevos

**REUTILIZAR (importar, no modificar — CLAUDE.local.md):**
`ciclo/*` (estados, `aplicar_accion`, router, revisor, bitácora, archivos), `extraccion_ia.py`,
`chat/providers.py`, `ict/parsers/mayor_excel.py`, `confirmaciones_saldos/parsers.py`,
`procesadores/conciliacion_reestructurada.py` (cascada N1–N7), `libro.py`, `base.py`,
`datos_cliente.py`, `problemas.py`, `html_ejecutivo.py`, `papel_office.py`, `marca.py`,
`graficos*.py`.

**NUEVO / A CONSTRUIR (dentro del alcance de seguros):**
- Datasets `DS_FACTURAS_SEGUROS`, `DS_NOTAS_CREDITO`, `DS_INVENTARIOS`, `DS_MAYORES` y la
  ampliación de `DS_POLIZAS`/`DS_ACTIVOS_FIJOS` en `seguros_cobertura.py`.
- Lógica de PR-004 (conciliación con semántica seguros) y PR-006 (inventarios) en `ejecutar()`.
- Cédulas nuevas (`R_Resumen_Polizas`, `R_Devengo`, `C_Conciliacion`, `C_Excepciones`,
  `I_Cobertura_inv`, `I_Sin_cobertura`), KPIs, códigos de excepción y entradas `REF_PROBLEMAS`.
- Recalc ampliado (`ciclo/revision/recalc/seguros_cobertura.py`) para los nuevos principales.
- Re-alineación de los 3 bloques de frontend de seguros (§15).
- Ejemplos del cliente ficticio (activos/inventarios/facturas/NC/mayor) en `ESCENARIOS`/manifiesto.

**A COORDINAR (infra compartida):** puente OCR→extracción (`extraccion_ia.py`/`utils/ocr.py`)
y declaración `EXTRACCION_DATASETS`.

**NO usar (scaffold/externo):** `motor_analitico/` (solo emite JWT a motor externo), skills
`auditbrain-*` como motor determinista (son prompts, sin código backend).

## 14. Excepciones / validaciones (§32)

Controles (en `validar_filas` + `ejecutar`): pólizas duplicadas; N° de póliza vacío; fechas
inválidas; vencimiento < inicio; suma asegurada cero; pólizas vencidas; factura sin póliza;
póliza sin factura; factura duplicada; NC sin factura; diferencia factura↔mayor; activos sin
categoría; inventarios sin ubicación; valores negativos; cuentas contables no identificadas.
Cada uno produce un código en `res["exceptions"]` con su importe enlazado (`REF_PROBLEMAS`).

## 15. Integración con el frontend (sin rediseño)

El frontend es **genérico y config-driven**; se tocan **solo los 3 bloques de seguros**
(permitido en el worktree aislado):
1. `frontend/src/aud/catalog.js:80` — entrada `SEGUROS` (categoría; sin cambios de estructura).
2. `frontend/src/aud/niif/ejemplosRequerimientos.js` — re-etiquetar `seguros_cobertura` a
   RQ-001 Pólizas … RQ-006 Mayores (archivos de ejemplo nuevos en `public/ejemplos/seguros_cobertura/`).
3. `frontend/src/aud/niif/procesoConfig.js` (`const SEGUROS`) — `principales` = los 6 RQ (o 4
   destacados + 2 en soporte) y `ejecuciones` = las **7** tarjetas PR-001..007.

Lo que **alimenta el backend** vía `GET /pruebas/{id}` (sin endpoints nuevos): `reg.requests`
(6 RQ), `prueba.cobertura` (`[{id,complete,rejected}]`), `prueba.estado`, `reg.run.exceptions`,
`prueba.definicion.processor="seguros_cobertura"`. Las cédulas/resultados salen al Procesar.

**Estados (§26):** el frontend usa 4 estados de requerimiento (Pendiente/Cargado/Validado/Error)
y deriva el de prueba (BLOQUEADA/DISPONIBLE/EJECUTADA/CON EXCEPCIONES/REVISADA). **«VALIDANDO»
y «PROCESANDO» no existen** como estados (son labels transitorios del botón): no se agregan.

## 16. APIs

**No se requieren endpoints nuevos.** Se reutilizan los del ciclo (`ciclo/router.py`):
`GET /pruebas/{id}`, `POST /pruebas/{id}/acciones` (map_validate/execute/validate/configure/
approve/encerar/versiones), `POST|GET /pruebas/{id}/archivos`, `GET /pruebas/{id}/modelo/{RQ}`,
`GET /pruebas/{id}/libro?formato=xlsx|html|docx|pptx|pdf`, `GET /pruebas/{id}/consola-revision`.
El piloto (`/api/v1/aud/niif/piloto/*`) sigue sirviendo como camino alternativo de ejecución.

## 17. Exportaciones y papel de trabajo (§27/§28)

El libro único (`libro.py`) entrega **Excel con fórmulas · HTML autónomo · Word · PowerPoint ·
PDF** con todas las cédulas; cada cédula lleva carátula (cliente, proyecto, periodo, rubro,
referencia, preparado/revisado por, fecha), objetivo, aseveraciones, información utilizada,
procedimiento, resultados, excepciones, conclusión y referencias. Los «7 exports» del §28
(`RESUMEN_POLIZAS.xlsx`, `REPROCESO_…`, `CONCILIACION_…`, `COBERTURA_ACTIVOS_FIJOS.xlsx`,
`COBERTURA_INVENTARIOS.xlsx`, `HALLAZGOS_SEGUROS.xlsx`, `PAPEL_TRABAJO_SEGUROS.xlsx`) se
obtienen del mismo libro (hoja/grupo por PR) — se evalúa si además se exponen como descargas
por-prueba (Duda D-4).

## 18. Testing (§33) y plan de implementación (§37)

**Testing** (patrón del repo, cifras recalculadas a mano): extender
`tests/test_proc_seguros_cobertura.py` y `tests/test_recalc_seguros_cobertura.py`, y añadir
`frontend` vitest para los 3 bloques. Casos §33: una/múltiples pólizas; póliza escaneada/
digital/vencida/por vencer/con endosos; factura con NC; activo cubierto/parcial/sin cobertura;
inventario cubierto/sin cobertura; diferencia contra mayor; devengo correcto/incorrecto; cambio
de fecha de corte. Verificadores: `scripts/verificar_problemas_enlazados.py`
(«PENDIENTES: 0»), reapertura del Excel con openpyxl (0 celdas de texto riesgosas),
`test_aud_sin_datos_fijos.py` (ninguna cifra pegada).

**Plan por fases (no inicia hasta aprobación):**
- **F1** Document Intelligence: puente OCR→extracción + `EXTRACCION_DATASETS` (coordinar).
- **F2** Ingesta y normalización: datasets DS_* (campos, alias, `validar_filas`, mayor parser).
- **F3** PR-002 Resumen de Pólizas.
- **F4** PR-003 Reproceso de prima anticipada (sobre lógica existente).
- **F5** PR-004 Conciliación (motor cascada adaptado).
- **F6** PR-005 Cobertura de Activos Fijos (sobre lógica existente).
- **F7** PR-006 Cobertura de Inventarios (nueva).
- **F8** PR-007 Hallazgos y Ajustes.
- **F9** Papeles de trabajo (cédulas/exports por PR).
- **F10** QA e integración completa (frontend + verificadores LibreOffice + tests).

## 19. Decisiones del dueño (resueltas 2026-10-01)

Las seis dudas bloqueantes fueron resueltas por el dueño. Quedan fijadas así:

- **D-1 · Re-mapeo de requerimientos — RESUELTO: SÍ.** Se re-alinea al screenshot aprobado:
  RQ-001 Pólizas, RQ-002 Facturas, RQ-003 Notas de Crédito, RQ-004 Activos Fijos,
  RQ-005 Inventarios, RQ-006 Mayores (backend + 3 bloques de frontend de seguros).
- **D-2 · Preservar lógica auditada — RESUELTO: SÍ (default).** Se conserva toda la lógica NIIF
  existente (infraseguro, deducibles/regla proporcional, exposición máxima, prima anticipada
  devengada, siniestros por tipo) y se integra en PR-003/PR-005/PR-007, sin reemplazarla.
- **D-3 · Modelado de las 7 pruebas — RESUELTO: UN procesador.** Un solo `seguros_cobertura`
  con 7 grupos de cédulas surfaced como las 7 tarjetas del frontend (no 7 registros separados).
- **D-4 · Exports por prueba — RESUELTO: libro único (default).** Un solo libro con una hoja/
  grupo por PR. Las 7 descargas `.xlsx` independientes del §28 quedan para fase posterior si se
  piden.
- **D-5 · Puente OCR — RESUELTO: puentear coordinando.** Se agrega el puente OCR→extracción en
  infra compartida (`extraccion_ia.py`/`utils/ocr.py`) y se actualiza
  `docs/niif/CONTRATO_PROCESADOR.md`. Habilita pólizas escaneadas desde F1.
- **D-6 · Inventarios — RESUELTO: SÍ.** Se incorpora `DS_INVENTARIOS` y la prueba PR-006
  Cobertura de Inventarios (alcance nuevo real).

> Arquitectura cerrada. La implementación procede por FASES (§18) **solo tras la luz verde
> explícita del dueño para iniciar la FASE 1**. Hasta entonces: no se modifica frontend ni se
> implementa.
