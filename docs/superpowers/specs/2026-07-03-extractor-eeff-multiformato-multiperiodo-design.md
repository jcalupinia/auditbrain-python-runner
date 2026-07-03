# Diseño — Extractor de EEFF multi-formato y multi-período (FIN · CFO)

Fecha: 2026-07-03
Autor: AuditConsulting (vía AUDIT-IA)
Estado: propuesta para revisión

## 1. Problema

El módulo FIN · CFO Intelligence permite subir "balances internos" en Excel y
generar un dashboard. Al subir `EEFF SIGMAN 2026.xlsx` (estado de situación
financiera + estado de resultados **resumidos, por nombre de concepto**), el
sistema falla.

Verificado empíricamente sobre el archivo real del cliente:

- `extract_balance_interno` (kind=`interno`, el que usa el botón) **lanza
  `ValueError`**: exige un plan de cuentas **con código** (segmentos 1/2/3 para
  balance, 4/5/6 para resultados). El archivo SIGMAN no tiene códigos.
- `extract_balance_resumido` (kind=`resumido`) **también lo rechaza**: exige la
  **plantilla del sistema** (columna `clave`). El archivo tampoco la tiene.

Es decir: un estado financiero **resumido libre, por nombre de concepto**, con
número de períodos variable y mixto, hoy no entra por ninguna vía.

### 1.1 Estructura real del archivo (verificada)

Hoja única `Hoja1`, dos bloques apilados:

**ESF (Estado de Situación Financiera)** — 4 períodos, cabecera:
`may-26 | 2025 | 2024 | 2023`. Es una **foto** (stock): cada columna es el
saldo a esa fecha.

**ERI (Estado de Resultado Integral)** — 5 períodos, cabecera:
`may-26 | may-25 | 2025 | 2024 | 2023`. Es un **flujo acumulado**: `may-26` y
`may-25` son acumulados de **5 meses** (ene–may); `2025/2024/2023` son años
completos (12 meses).

Basura de datos comprobada, que el extractor debe tolerar:
- Tipos de celda **mezclados en la misma cabecera**: en el ERI los años vienen
  como `[datetime, datetime, str, str, int]` (2025/2024 como texto, 2023 como
  número, los cortes como fecha).
- Descuadre contable en la columna 2025 del balance: Activo `6,544,748.01` vs
  Pasivo+Patrimonio `6,544,486.99` (dif **−261.02**), ya señalado por la fila
  "Comprobación" del propio archivo.

## 2. Objetivo

Una **"función que decide"**: al subir cualquier archivo, detecta su formato,
extrae los N períodos con sus etiquetas correctas, mapea los conceptos a los
rubros NIIF sin fusionar grupos, y expone las comparaciones período-a-período
que el negocio necesita. Sin romper los formatos ya soportados (codificado y
plantilla).

## 3. Reglas de negocio confirmadas con el usuario

### 3.1 Etiquetado de períodos (decisión automática)
- Cabecera tipo **fecha** (`datetime`/ISO/`dd-mm-aaaa`) → período **parcial**;
  `meses = mes de la fecha`; etiqueta corta `may-26`.
- Cabecera tipo **año** (entero **o texto** de 4 dígitos) → **anual**,
  `meses = 12`; etiqueta `2025`.
- Tolerante a tipos mezclados dentro de una misma fila de cabecera.

### 3.2 Comparaciones
- **ESF (Balance):** período **actual vs. inmediatamente anterior, en cadena**:
  `may-26 vs 2025`, `2025 vs 2024`, `2024 vs 2023`.
- **ERI (Resultados):** **parcial vs. parcial** (`may-26 vs may-25`,
  like-for-like 5m) **más** anuales en cadena (`2025 vs 2024`, `2024 vs 2023`).
- **Nunca** se compara un período parcial (5m) contra uno anual (12m).
- Regla NIIF (IAS 34) coherente con lo anterior: el balance intermedio se
  compara contra el cierre anual inmediato anterior; el resultado intermedio,
  contra el mismo período intermedio del año previo.

### 3.3 Mapeo por nombre (NIIF) — sin fusionar grupos
Cada fila del estado resumido se asigna a un rubro NIIF por su **nombre de
concepto**, respetando [[regla-no-fusionar-cuentas]]: inventario, CxC, PP&E,
CxP, capital, ingresos, costo, gastos, etc. cada uno por separado; jamás se
mezclan grupos distintos. El total de cada sección debe cuadrar contra el
`TOTAL` que trae el propio archivo (Activos, Pasivos, Patrimonio, y los
subtotales del ERI).

## 4. Arquitectura propuesta

Se mantiene el contrato de salida existente
(`{data, detalle, params, warnings, source, anios_detectados, labels_esf,
labels_er}`) para no romper el frontend. Se agregan dos piezas:

### 4.1 Detector de formato — `detect_layout(df) -> "codificado" | "plantilla" | "resumido_nombre"`
Módulo nuevo `parsers/layout.py`. Reglas:
- `codificado`: existen filas cuya col A parsea a segmentos `1/2/3` o `4/5/6`.
- `plantilla`: existe la fila de encabezado `clave` (plantilla del sistema).
- `resumido_nombre`: hay filas de cabecera con ≥2 períodos y las filas de datos
  traen **nombre de concepto** en col A (sin código) → nuevo camino.

### 4.2 Extractor resumido-por-nombre — `parsers/balance_resumido_nombre.py`
Función `extract_balance_resumido_nombre(data_bytes) -> dict` (mismo contrato).
- Reutiliza la detección de bloques/períodos ya probada de `balance_interno`
  (`_find_blocks`, `_detect_periods`, `_period_label`), extendida para clasificar
  `parcial|anual` y `meses` (hoy solo devuelve label+year).
- Mapea cada fila por nombre con un diccionario **explícito y auditado** de
  sinónimos → rubro (NO herencia stateful; ver [[regla-no-fusionar-cuentas]] y la
  política anti-"nombres heredados" del CLAUDE.md). Filas de subtotal/`TOTAL`
  se usan para **cuadrar**, no como cuenta.
- Devuelve además, por período, `tipo` y `meses`, y un bloque
  `comparaciones` calculado según §3.2 para que el dashboard lo consuma directo.

### 4.3 Enrutado — `extract_balance_interno` como fachada
`extract_balance_interno(data_bytes)` pasa a: leer el libro → `detect_layout` →
delegar al extractor correspondiente. Si es `codificado`, ejecuta la lógica
actual **intacta** (cero regresión). Si es `resumido_nombre`, delega al nuevo
extractor. Mantiene el mismo nombre público para no tocar el router.

### 4.4 Alineación ESF vs ERI (períodos distintos)
Como el ESF tiene 4 períodos y el ERI 5, los índices no coinciden (p. ej. `2025`
es índice 1 en ESF pero índice 2 en ERI). La salida mantiene `labels_esf` y
`labels_er` separados, y las `comparaciones` se calculan **por bloque contra sus
propias etiquetas**, nunca por índice compartido.

## 5. Flujo de datos

Excel bytes → `_read_excel` → por hoja `df` → `detect_layout` →
`extract_*` → `{data, detalle, labels_esf, labels_er, periodos:[{label,tipo,meses}],
comparaciones:{esf:[...], eri:[...]}, warnings}` → router `/extract` → frontend.

## 6. Manejo de errores / warnings
- Formato no reconocido → `ValueError` con mensaje accionable (qué se esperaba).
- Descuadre de sección (|Activo − (Pasivo+Patrimonio)| > 0.01 en algún período)
  → **warning** (no frena), citando período y monto (caso −261.02 en 2025).
- Concepto no mapeado → va a "otras/no clasificadas" de su sección + warning con
  el nombre exacto, para revisión del auditor. Nunca se descarta silenciosamente.
- Tipos de cabecera raros → se toleran; si una columna no es período válido, se
  omite con warning.

## 7. Estrategia de pruebas (TDD)
Fixtures = el archivo real `EEFF SIGMAN 2026.xlsx` (verificación con datos reales,
regla suprema) + mini-libros sintéticos para casos borde.

Tests obligatorios (nuevos, en `tests/`):
1. `test_layout_detecta_resumido_nombre` — clasifica SIGMAN como `resumido_nombre`;
   un libro codificado como `codificado`; la plantilla como `plantilla`.
2. `test_periodos_etiqueta_parcial_vs_anual` — ESF: `may-26`=parcial/5m + 3 anuales;
   ERI: 2 parciales/5m + 3 anuales; tolera tipos mezclados `[datetime,str,int]`.
3. `test_extrae_totales_cuadran` — TOTAL ACTIVOS may-26 = 6,748,379.14; Ingresos
   may-26 = 2,930,004.99; etc. (cifras exactas del archivo).
4. `test_no_fusiona_grupos` — inventario, CxC, PP&E, CxP quedan en rubros
   separados; ninguno absorbe a otro.
5. `test_comparaciones_esf_encadenadas` — may-26 vs 2025 = +203,631.13 (+3.1%);
   2025 vs 2024 = −112,800.93 (−1.7%); 2024 vs 2023 = −192,534.28 (−2.8%).
6. `test_comparaciones_eri_parcial_y_anual` — Ingresos may-26 vs may-25 =
   +356,058.28 (+13.8%); 2025 vs 2024 = −2,188,927.46 (−22.4%). Nunca cruza 5m/12m.
7. `test_descuadre_emite_warning` — la dif −261.02 de 2025 aparece como warning.
8. `test_codificado_sin_regresion` — un libro codificado sigue extrayéndose igual
   que antes (comparar contra salida previa fijada).

Comando de verificación: `python -m pytest tests/ -k "extractor or eeff or resumido_nombre" -v`
y una corrida end-to-end del archivo real imprimiendo las comparaciones.

## 8. Fuera de alcance (YAGNI)
- Anualizar los parciales (proyección ×12/5): descartado por el usuario.
- Cambiar el render del dashboard más allá de consumir `periodos`/`comparaciones`.
- OCR/PDF: aquí solo Excel.

## 9. Componentes y responsabilidades (isolación)
| Unidad | Qué hace | Depende de |
|---|---|---|
| `layout.detect_layout` | decide el formato del libro | pandas df |
| `periodos.clasificar` | label + tipo + meses de una cabecera | datetime/regex |
| `balance_resumido_nombre.extract_*` | extrae ESF/ERI por nombre | periodos, mapeo |
| `mapeo_nombres` | nombre de concepto → rubro NIIF (dict auditado) | — |
| `comparaciones.build` | arma pares §3.2 con Δ y Δ% | labels+data |
| `extract_balance_interno` (fachada) | detecta y delega | todos los anteriores |
