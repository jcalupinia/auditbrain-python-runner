# Contrato de un procesador de prueba NIIF (herramientas del catálogo AUD)

Cada herramienta del catálogo es **un módulo Python** en `backend/app/aud/niif/procesadores/<id>.py`
más **una prueba** en `tests/test_proc_<id>.py`. Referencia completa y verificada:
`procesadores/pce_simplificada_niif9.py` (léela antes de escribir). Piezas comunes: `procesadores/base.py`.

Metodología: Memoria AuditBrain v1.4.0 (M01–M24). Lo esencial para este contrato:
- **M03** la norma se lee del texto oficial (NIIF completas en español: EUR-Lex, Reglamento (UE) de adopción;
  PYMES: IFRS Foundation — 2015 y 2025). Párrafo no leído → «VERIFICAR» en el texto de la definición.
- **M19** ejemplo numérico de control resuelto a mano (`EJEMPLO`).
- **M20** cada importe del Excel es una fórmula viva que da el mismo valor que Python: cero diferencias en Excel real.
- **M22** lo que no se puede medir queda vacío y señalado (nunca 0 por omisión, tampoco en fórmulas: usar
  `IF(x<>"",x,"")`); cada «debe» de la norma que el cálculo no garantiza es un `problema(...)`.
- Todo texto al usuario, en español. Nunca inventar tasas, párrafos ni datos.

## Atributos obligatorios del módulo

```python
VERSION = "<id> 1.0"
RUBRO = "CAJA_BANCOS"          # código de la tarjeta del catálogo (ver lista abajo)
CAMPOS = {"<tipo>": [campo(...), ...]}       # base.campo(key, label, tipo, requerido, alias, ejemplo)
TIPOS = {"<dataset>": "<tipo>"}              # un anexo de cálculo por requerimiento
DATASETS = tuple(TIPOS)
PRINCIPAL = "<dataset>"        # población que se concilia con el mayor
CONTROL = "<campo numérico>"   # campo del PRINCIPAL cuya suma es el total de control
PARAMETROS = {...}             # valores por defecto: números, textos (opciones) o None
PARAM_NEGATIVOS = ()           # parámetros numéricos que admiten negativos
ETIQUETAS_PARAM = {...}        # etiqueta en pantalla de cada parámetro
TOTAL_EJEMPLO = "<clave de totals>"  # el total que muestra el Estudio
CEDULAS = [("01_Resumen", "Resumen"), ...]   # mismo orden y nombres que hojas()

# El ciclo usa estas dos piezas del módulo: impórtalas de base.
from backend.app.aud.niif.procesadores.base import a_num, filas_mapeadas  # noqa: F401
def kind(dataset): return TIPOS[dataset]
def validar_filas(tipo, filas): return validar_campos(CAMPOS[tipo], filas)
def ejecutar(datasets, parametros, corte) -> dict
def hojas(res) -> list[dict]
def definicion() -> dict
def validar_definicion(d): return validar_definicion_generica(d, DATASETS, PRINCIPAL)
EJEMPLO = {"corte": "2025-12-31", "parametros": {...}, "datasets": {"<dataset>": [filas...]}}
ESCENARIOS = [("base", datasets, parametros, corte), ...]   # para el verificador de Excel
```

### `ejecutar(datasets, parametros, corte)`
- `datasets[ds]` = lista de filas `{campo: texto, "_row": n}` (texto crudo: usar `num()`/`fecha()` de base).
- `parametros` trae los de `PARAMETROS` más `_marco` («NIIF completas» / «NIIF para las PYMES») y `_edicion`
  («2015»/«2025») de la ficha del encargo. **Si el cálculo cambia por marco o edición, enrutar aquí**
  (`es_pymes(p)`, `edicion_pymes(p)`) y decirlo en la cédula de parámetros.
- Lanzar `ValueError("mensaje en español")` si falta lo indispensable.
- Devolver:
  - `engine`: VERSION
  - `rows`: filas de detalle del principal, cada una con `"id"` y `"_row"` (valores como texto, importes con `r2`)
  - `totals`: `{clave: "1234.56"}` (texto con 2 decimales, `r2`) y `labels`: `{clave: etiqueta}` en el mismo orden;
    el primero suele ser el saldo auditado y debe existir la clave `primary`
  - `primary`: clave del resultado principal (normalmente el ajuste propuesto neto de lo registrado, M09)
  - `exceptions`: lista de `problema(code, mensaje, importe)`
  - `schedule`: `[]`
  - `detalle`: lo que necesiten `hojas()` (con fechas en ISO); incluir `"parametros": p`

### `hojas(res)` (Excel con fórmulas)
- Diseño fijo: datos desde la fila `FILA0 = 5` (fila 4 encabezados). Nombres `NN_Nombre` ≤ 31 caracteres.
- Celda calculada = `fx("FÓRMULA sin =", valor_python)`. El valor debe ser **idéntico** al que dará Excel
  (misma aritmética, sin redondear antes de tiempo; importes con `n2()` solo al final).
- Referencias entre hojas con `ref("05_Detalle")` → `'05_Detalle'!`; rangos absolutos `$A$5:$A$20`.
- Hoja de parámetros con valores numéricos reales (fechas ISO se convierten solas en fecha de Excel si el formato
  de columna es `"x"` o `"d"`); los demás importes remiten a ella.
- Filas TOTAL con `suma(col, fin_fila, valor)`.
- Formatos de columna: `t` texto, `n` importe, `p` porcentaje (valor 0–1), `i` entero, `d` fecha, `x` libre.
- Al menos: 01_Resumen, 02_Parametros, detalle, cálculo(s) de la norma, conciliación/ajuste, problemas.

### `definicion()`
Como `pce_simplificada_niif9.definicion()`: `name`, `area` (etiqueta del rubro), `processor` (= id del módulo),
`frameworks` (["NIIF completas", "NIIF para las PYMES"] salvo que solo aplique a uno), `summary`,
`source` y `source_pymes` (documento + párrafos/secciones, citando PYMES 2015 y 2025), `nia` (norma, párrafos,
exigencia), `calculo` (pasos en lenguaje contable), `fields` (= CAMPOS del principal), `rules: []`, `control`,
`primary`, `campos`, `tipos`, `parametros` (sin internos), `etiquetas_parametros`,
`tramos` (solo si hay tasas por tramo), `cedulas`, `program` (≥5 procedimientos con code/objective/risk/assertion/
procedure/evidence/criterion/source) y `requests` (con `req()`: uno por anexo de cálculo + los de soporte).
Códigos de programa y requerimientos: `<PREFIJO>-01…`, `RQ-001…`.

### `EJEMPLO` (ejercicio modelo, M19)
Datos ficticios realistas (8–20 filas por anexo) que **ejerciten todas las cédulas y al menos dos problemas**.
Las cifras clave se recalculan a mano en la prueba. Si hay rutas por marco, `ESCENARIOS` incluye ambas.

## Prueba `tests/test_proc_<id>.py` (sin base de datos)
- Import: `from backend.app.aud.niif.procesadores import <id> as m`
- Ejemplo de la ficha con cifras recalculadas a mano (`assert` exactos).
- Casos límite: anexo vacío (ValueError), negativos, faltantes, ruta por marco, parámetro fuera de rango.
- `hojas()`: nombres = CEDULAS y todas las filas con el ancho de `cols`.
- Ejecutar: `python -m pytest tests/test_proc_<id>.py -q -p no:warnings`

## Verificación en Excel real (obligatoria)
`python scripts/verificar_formulas.py <id>` → debe terminar con `DIFERENCIAS: 0`.

## Prohibido
Editar archivos compartidos (`procesadores/__init__.py`, `ciclo/*.py`, frontend, otros procesadores). Solo se crean
el módulo y su prueba. No correr la suite completa (usa una base compartida).

## Códigos de rubro (tarjetas)
CAJA_BANCOS · CXC · INVERSIONES · INVENTARIOS · ACTIVOS_FIJOS · ARRENDAMIENTOS · PROPIEDADES_INVERSION ·
INTANGIBLES · BIOLOGICOS · SEGUROS · PROVEEDORES · PRESTAMOS · NOMINA · INGRESOS · COSTOS_GASTOS · PROVISIONES ·
IMPUESTOS · PATRIMONIO
