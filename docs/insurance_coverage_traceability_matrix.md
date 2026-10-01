# Matriz de Trazabilidad — Herramienta «Cobertura de Seguros»

> Complemento de `docs/insurance_coverage_architecture.md`. **BORRADOR para aprobación.**
> Formato pedido por el Prompt Maestro §35: **REQUERIMIENTO | DATASET | PRUEBA | CÁLCULO |
> OUTPUT | REFERENCIA**. Procesador: `backend/app/aud/niif/procesadores/seguros_cobertura.py`.
>
> Regla de trazabilidad (§29): toda cifra se rastrea RESULTADO → PRUEBA → CÁLCULO → DATASET →
> REGISTRO → DOCUMENTO → PÁGINA/HOJA → FILA/CAMPO. En el Excel cada importe calculado es una
> **fórmula** (celda `fx(formula, valor)`) que remite a su celda de origen; las hojas `D1_…`/
> `D2_…` («Origen del dato» archivo·hoja·fila) las arma `datos_cliente.con_datos`.

## 1. Requerimiento → Dataset → Documento fuente

| Requerimiento | Dataset | Formatos | Documento fuente | Lectura (componente reutilizado) |
|---|---|---|---|---|
| RQ-001 Pólizas de Seguros | `DS_POLIZAS` | pdf·xlsx·csv | Pólizas y endosos | `extraccion_ia` (PDF/Word) + Excel/CSV; OCR si escaneado |
| RQ-002 Facturas de Seguros | `DS_FACTURAS_SEGUROS` | pdf·xlsx·csv | Facturas de prima | `extraccion_ia` + `facturacion_sri` (patrón) |
| RQ-003 Notas de Crédito | `DS_NOTAS_CREDITO` | pdf·xlsx | Notas de crédito | `extraccion_ia` + Excel |
| RQ-004 Anexo de Activos Fijos | `DS_ACTIVOS_FIJOS` | xlsx·csv | Anexo de activos fijos | `filas_mapeadas` (Excel) |
| RQ-005 Anexo de Inventarios | `DS_INVENTARIOS` | xlsx·csv | Anexo de inventarios | `filas_mapeadas` (Excel) |
| RQ-006 Mayores Contables | `DS_MAYORES` | xlsx·csv | Mayor contable | `ict/parsers/mayor_excel.parse_mayor` |

## 2. Dataset → Campos clave (diccionario, resumen)

| Dataset | Campos clave (ver §6 de arquitectura para el detalle) |
|---|---|
| `DS_POLIZAS` | id, aseguradora, ramo, vigencia_desde/hasta, moneda, suma_total, prima_neta, impuestos, prima_total, prima_anticipada, deducible_pct, cobertura, bienes_asegurados, ubicaciones, exclusiones, endosos, siniestro* |
| `DS_FACTURAS_SEGUROS` | id, proveedor, aseguradora, fecha, autorizacion, base, impuestos, total, poliza, referencia, descripcion |
| `DS_NOTAS_CREDITO` | id, emisor, fecha, factura, poliza, base, impuestos, total, motivo |
| `DS_ACTIVOS_FIJOS` | id, categoria, descripcion, ubicacion, fecha_adquisicion, costo, depreciacion_acumulada, valor_libros, estado, centro_costo, poliza, suma_asignada, valor_referencia, deducible_pct |
| `DS_INVENTARIOS` | id, descripcion, categoria, ubicacion, cantidad, costo_unitario, valor_total, bodega, estado, poliza, suma_asignada |
| `DS_MAYORES` | cuenta, descripcion, fecha, comprobante, referencia, debito, credito, saldo, tercero, auxiliar, centro_costo |

## 3. Matriz principal — REQUERIMIENTO | DATASET | PRUEBA | CÁLCULO | OUTPUT | REFERENCIA

| Requerimiento(s) | Dataset(s) | Prueba | Cálculo | Output (KPI / excepción) | Referencia (cédula · código) |
|---|---|---|---|---|---|
| Todos | Todos | **PR-001** Procedimiento | Consolidación del programa INS-01..07; sin cálculo nuevo | Objetivo, aseveraciones, conclusión | `00_Programa` · `01_Resumen` · `12_Conclusion` · `15_Lectura` |
| RQ-001 | `DS_POLIZAS` | **PR-002** Resumen de Pólizas | `DIAS_VIGENCIA`, `DIAS_TRANSCURRIDOS`, `DIAS_POR_VENCER`; clasificación ACTIVA/VENCIDA/PRÓXIMA/PENDIENTE | nVencidas, nPorVencer; `POLIZA_VENCIDA`, `POLIZA_POR_VENCER`, `POLIZA_NO_INICIADA` | `05_Vigencia` · `R_Resumen_Polizas` |
| RQ-001,002,003,006 | `DS_POLIZAS`,`DS_FACTURAS_SEGUROS`,`DS_NOTAS_CREDITO`,`DS_MAYORES` | **PR-003** Reproceso Prima Anticipada | `PRIMA_DIARIA=BASE/PLAZO_DIAS`; `GASTO_CALCULADO`, `ACTIVO_CALCULADO`; `DIFERENCIA_GASTO/ACTIVO` vs libros | `primaRecalculada`, `primaRegistrada`, `difPrima`, **`ajustePrima` (principal)**; `PRIMA_MAL_DEVENGADA`, `PRIMA_ANTICIPADA_NO_INFORMADA` | `10_Prima_anticipada` · `R_Devengo` · `REF_PROBLEMAS` |
| RQ-001,002,003,006 | idem | **PR-004** Conciliación | Matching cascada N1–N7 (`conciliacion_reestructurada`): póliza↔factura↔NC↔mayor; diferencias de base/impuestos/total | `ESTADO_CONCILIACION`, `DIFERENCIA`; `FACTURA_SIN_POLIZA`, `POLIZA_SIN_FACTURA`, `FACTURA_DUPLICADA`, `NC_NO_APLICADA`, `DIFERENCIA_MAYOR`, `CONCILIACION_PRIMA_MAYOR` | `C_Conciliacion` · `C_Excepciones` |
| RQ-001,004 | `DS_POLIZAS`,`DS_ACTIVOS_FIJOS` | **PR-005** Cobertura Activos Fijos | `%COBERTURA=ASEGURADO/LIBROS`; `DIFERENCIA_COBERTURA`; `%NO_ASEGURADO`; regla proporcional + deducible; `exposicionMaxima` | `coberturaGlobal`, `deficitCobertura`, `sobreseguro`, `exposicionMaxima`, nSinCobertura, nInfraseguro; `ACTIVO_SIN_COBERTURA`, `INFRASEGURO`, `SOBRESEGURO`, `EXPOSICION_MAXIMA`, `REFERENCIA_EN_LIBROS` | `06_Cobertura_activo` · `07_Cobertura_poliza` · `08_Deducibles_exposicion` · `09_Sin_cobertura` |
| RQ-001,005 | `DS_POLIZAS`,`DS_INVENTARIOS` | **PR-006** Cobertura Inventarios | `%CUBIERTO=ASEGURADA/VALOR_INV`; `DIFERENCIA`; `%NO_CUBIERTO` | coberturaInventario, inventarioSinCobertura; `INVENTARIO_SIN_COBERTURA`, `INVENTARIO_INSUFICIENTE`, `UBICACION_NO_INCLUIDA`, `RIESGO_EXCLUIDO` | `I_Cobertura_inv` · `I_Sin_cobertura` |
| Todas | Todas | **PR-007** Hallazgos y Ajustes | Consolidación de excepciones de PR-002..006; esquema Condición-Criterio-Causa-Efecto; tratamiento de siniestros | Hallazgos (ID, PRUEBA_ORIGEN, VALOR_USD, RIESGO, REFERENCIA_PT); `siniestrosSinRevelar`, `compensacionesExigibles` | `11_Siniestros` · `13_Ajustes` · `14_Problemas` |

## 4. Aseveración → Prueba (NIA)

| Aseveración | Pruebas que la cubren |
|---|---|
| Existencia | PR-002, PR-004, PR-005, PR-006 |
| Integridad | PR-002, PR-004 |
| Exactitud | PR-003, PR-004 |
| Valuación | PR-003, PR-005, PR-006 |
| Derechos y obligaciones | PR-001, PR-004 |
| Corte | PR-002, PR-003 |
| Clasificación | PR-005, PR-006 |
| Presentación y revelación | PR-001, PR-007 (siniestros) |

## 5. Resultado → Trazabilidad completa (ejemplo `ajustePrima`)

`ajustePrima` (RESULTADO principal) → **PR-003** (PRUEBA) → `PRIMA_DIARIA × DIAS_PENDIENTES − activo libros`
(CÁLCULO, celda `fx` en `10_Prima_anticipada`) → `DS_POLIZAS` + `DS_MAYORES` (DATASET) →
`reg["datasets"]` (REGISTRO) → póliza PDF / mayor xlsx (DOCUMENTO) → hoja·fila del anexo
(PÁGINA/HOJA · FILA/CAMPO, visible en `D1_…`/`D2_…`). Verificación independiente:
`ciclo/revision/recalc/seguros_cobertura.py::recalcular` (recomputa desde fechas crudas).

## 6. Estado actual vs objetivo (qué existe / qué se agrega)

| Elemento | Hoy en el repo | Objetivo Prompt Maestro | Acción |
|---|---|---|---|
| Datasets | `activos`, `polizas` (2) | 6 (`DS_POLIZAS`,`FACTURAS`,`NC`,`ACTIVOS_FIJOS`,`INVENTARIOS`,`MAYORES`) | Ampliar + 4 nuevos |
| Requerimientos | 6 (otro mapeo) | 6 (Pólizas…Mayores) | Re-alinear (D-1) |
| Pruebas | 7 procedimientos INS-01..07 (1 libro) | 7 pruebas PR-001..007 (7 tarjetas) | Mapear a 7 grupos de cédulas (D-3) |
| Cédulas | 15 | +6 nuevas (Resumen, Devengo, Conciliación×2, Inventarios×2) | Agregar |
| Conciliación documental | no existe | PR-004 | Reusar cascada N1–N7 |
| Inventarios | no existe | PR-006 | Nuevo (D-6) |
| OCR en extracción | no puenteado | «OCR si corresponde» | Puente (D-5, compartido) |
| Frontend seguros | 4 primarias + 9 ejecuciones (labels viejos) | 6 RQ + 7 PR (screenshot) | Re-alinear 3 bloques |

> Pendiente de las 6 dudas bloqueantes (D-1…D-6) del documento de arquitectura. Sin esas
> respuestas y la aprobación, no se inicia implementación ni se toca el frontend.
