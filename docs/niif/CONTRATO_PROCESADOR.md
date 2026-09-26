# Contrato de un procesador de prueba NIIF (herramientas del catálogo AUD)

Cada herramienta del catálogo es **un módulo Python** en `backend/app/aud/niif/procesadores/<id>.py`
más **una prueba** en `tests/test_proc_<id>.py`. Referencias verificadas (léelas antes de escribir):
- `procesadores/pce_simplificada_niif9.py`: estructura básica, cédulas con fórmulas, definición, EJEMPLO.
- `procesadores/perdidas_incurridas_s11.py`: **piloto del papel actual**: hojas «Datos del cliente»
  (`D1_…`–`D5_…`) armadas a mano con su guía y origen, cédulas que calculan desde esos datos, `EXPLICA`,
  `PANEL` y `REF_PROBLEMAS`. Las demás herramientas reciben sus hojas de datos de `datos_cliente.py`.

Piezas comunes: `procesadores/base.py`.

> **Actualizado 2026-09-25.** El papel de trabajo cambió: sin cifras calculadas pegadas, portada
> igual al panel del HTML, Word y PowerPoint con el diseño del HTML y logotipos en todos los formatos.
> Lo que eso exige a cada módulo está en «Lo que exige el papel de trabajo», más abajo.
> Las reglas completas, en `CLAUDE.md` › «Papeles de trabajo de las herramientas NIIF».

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
PANEL = {...}                  # tarjetas y gráficos del panel (HTML, portada del Excel, Word, PowerPoint)
REF_PROBLEMAS = {...}          # de qué celda sale el importe de cada problema
```

`PANEL` y `REF_PROBLEMAS` son **obligatorios**: se explican en «Lo que exige el papel de trabajo».

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
- Cada cédula se arma con `base.hoja(name, label, cols, rows, total, explica=…, guia=…, ocultas=…, origen=…)`:
  - `explica`: **obligatorio** para toda columna con fórmula. Es una frase en lenguaje sencillo (≥ 40 caracteres,
    no repetida en la misma hoja) que dice qué hace la columna y con qué dato de qué hoja, como se lo
    explicaría el auditor a un contador o a un gerente financiero. Es lo que muestra «ⓘ Cómo se calcula esta hoja»
    en el Excel, el HTML, el PDF y el Word. La fórmula y un ejemplo con números van solos al `00_Anexo_tecnico`.
  - `guia`: «¿De dónde saco este dato?». Indica qué reporte, cuenta y fecha alimenta la hoja. Obligatoria en las `D…`.
  - `ocultas`: columnas técnicas (claves de cruce); el Excel las agrupa y las oculta.
  - `origen`: {columna: texto} cuando «De dónde viene el dato» no se deduce de la fórmula.
- La hoja de problemas tiene exactamente las columnas `Código`, `Descripción`, `Importe`.
- Nombres y secciones de la portada: `D1_…` → «Datos del cliente»; la primera hoja `[t, n]` (Resumen), la de
  problemas, `…Asiento…`/`…Ajuste…` → «Resultado»; el resto → «Cómo se calculó».
- **No crees** `00_Caratula`, `00_Programa`, `00_Fuentes`, `13_Conclusion` ni `14_Control_Revision`: las agrega
  `libro.cedulas()` desde la definición y el registro del encargo.

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

## Lo que exige el papel de trabajo (decisiones del dueño, 2026-09-24/25)

El módulo solo calcula y describe sus cédulas. **Los formatos los arma `libro.py`, que no se toca.** Todo sale
de lo que declara el módulo, así que lo que falte ahí falta en todos los formatos:

| Formato | Qué produce `libro` | De dónde lo toma |
|---|---|---|
| Excel | Portada `00_Inicio` **igual al panel del HTML** (`panel_excel.py`): fondo #071B2F, logos, chips, 5 tarjetas y 4 gráficos nativos; botones por sección; cada cédula con fórmulas y «Cómo se calcula»; `00_Anexo_tecnico`; datos de gráficos en `00_Datos_graficos` (oculta) | `hojas()`, `PANEL`, `REF_PROBLEMAS`, `explica`/`guia` |
| HTML | Dashboard autónomo, sin internet: panel con tarjetas y gráficos SVG, una pestaña por cédula; trae dentro el Excel, el Word y el PowerPoint | `graficos.panel(PANEL)`, `hojas()` |
| PDF | El HTML en tema claro | ídem |
| Word | El HTML impreso (tema claro): membrete con logos, tarjetas, los 4 gráficos (los mismos SVG como imagen, `svg_png.py`), cada cédula con «Cómo se calcula» | ídem (`papel_office.py`) |
| PowerPoint | El HTML en pantalla (tema «Ejecutivo»): portada, panel, cédulas de lectura (`_EN_PPT`) | ídem (`papel_office.py`) |

Las pruebas **declarativas** (sin procesador) salen con este mismo diseño: `procesadores/declarativo.py`
convierte las cédulas del exportador del sitio al modelo de `libro` y deriva su `PANEL` de la definición.
Un cambio en las piezas compartidas se prueba también con `tests/test_aud_papel_declarativo.py` y
`python scripts/verificar_papel_declarativo.py`.

### `PANEL` — tarjetas y gráficos
```python
PANEL = {
    "poblacion":   {"rotulo": "Cartera al corte", "total": "saldo"},             # clave de totals, o…
    "recalculado": {"rotulo": "Pérdida recalculada", "total": "perdida"},
    "registrado":  {"rotulo": "Provisión registrada", "hoja": "06_Conciliacion", "col": "Libros"},  # …suma de columna
    "composicion": {"rotulo": "Pérdida por tramo", "hoja": "04_Matriz", "etiqueta": "Tramo", "valor": "Pérdida"},
    "distribucion": {"rotulo": "Cartera por tramo", "hoja": "04_Matriz", "etiqueta": "Tramo", "valor": "Saldo"},
}
```
- Las cinco claves son obligatorias. `graficos.panel(mod, run, hojas)["faltan"]` debe quedar vacío.
- Variantes admitidas: `{"total": clave}`; `{"hoja", "col"}` con filtros opcionales `donde={col: [valores]}` y
  `con_valor="col"`; en series, `{"hoja", "etiqueta", "valor"}` (más `donde`) o `{"totales": [(rótulo, clave), …]}`.
- En la portada del Excel cada tarjeta y cada barra es **fórmula**. Una clave `total` se enlaza a la fila del
  Resumen que tiene ese rótulo e importe, o a la fila TOTAL de una cédula. Una columna se enlaza con
  `SUMIFS`/`COUNTIFS`. Por eso el importe de `totals` debe existir en alguna celda del libro.
- **Nunca** volcar todas las filas del Resumen en un gráfico: mezcla escalas y se ve como un código de barras.
- `PANEL["textos"]` (opcional) cambia los rótulos pensados para una prueba sustantiva cuando no aplican
  (p. ej. la planificación no tiene «cifra del cliente»): `comparativo`, `comparativo_sub`, `nota_recalculado`
  (texto en lugar de la flecha de variación), `vs`, `igual`, `nota_registrado` y `problemas`. Por defecto rigen
  los de `graficos.TEXTOS`, iguales en el HTML, la portada del Excel, el Word y el PowerPoint.
- `PANEL["tableros"]` (opcional) agrega gráficos de **columnas agrupadas** (p. ej. anterior frente a actual)
  debajo de los 4 del panel, en los cuatro formatos: HTML (`graficos_svg.agrupadas`), portada del Excel (gráfico
  nativo cuyos datos son fórmulas a la celda de la cédula), Word y PowerPoint (el mismo SVG como imagen). Cada uno:
  `{"rotulo", "sub", "unidad": "veces"|"días"|"%"|"USD", "hoja", "etiqueta", "filas": [rótulo | [rótulo, rótulo del
  gráfico] | {"fila", "rotulo", "mejor": "alto"|"bajo"}], "series": [[nombre, columna], …], "estado": columna del
  semáforo, "seccion": título de página}`. Las filas se buscan por su rótulo en la columna `etiqueta`; si una
  no existe, el tablero va a `faltan`. Ejemplo: la planificación (índices por grupo y analítico del artefacto).
- Diseño **premium** (pedido del dueño, 2026-09-26: «gráficos premium y no gráficos simples»): barras con
  degradado y esquinas redondeadas, escala con cuadrícula punteada, píldora por indicador con el punto del
  semáforo y la variación ▲/▼ (verde si mejora según `mejor`, rojo si empeora, gris sin sentido; «pp» en los
  porcentajes). En el Excel: degradado en las barras y la variación en el rótulo por fórmula (`FIXED`, respeta el
  separador decimal del equipo). Cada página impresa de tableros empieza con una franja con su título de sección:
  LibreOffice, al exportar a PDF, no recorta los degradados en el salto de página.

### `REF_PROBLEMAS` — importe de cada problema como fórmula
```python
REF_PROBLEMAS = {
    "AJUSTE": ("01_Resumen", "Importe"),                 # la fila cuyo importe coincide
    "TRAMO_NO_MEDIBLE": ("04_Matriz", "Saldo"),          # si hay varias, la del identificador citado en el mensaje
    "DIFERENCIA": ("06_Conciliacion", "Diferencia", "total"),   # la fila TOTAL
    "CONCILIACION_INICIAL": _funcion,                    # f(hojas, e) -> ("fórmula sin =", valor)
}
```
Todo código que pueda emitir `problema(...)` necesita su entrada. Solo se enlaza si la celda tiene ese mismo
importe; si no, queda como valor y lo reporta el verificador. Ver `procesadores/problemas.py`.

### Sin cifras calculadas pegadas
Los datos del cliente y los parámetros del auditor son valores (entradas). **Todo lo demás es fórmula** que
remite a su origen. Una cifra calculada escrita como número es un error, aunque el valor sea correcto.

### Datos del cliente dentro del libro (todas las herramientas)
Cada documento que entrega el cliente (RQ-…) va en su hoja `D1_…`, `D2_…`. Lleva lo que entregó, fila por fila,
más la columna «Origen del dato» (archivo · hoja · fila) y `guia`.
- **Lo hace `procesadores/datos_cliente.py` por ti:** a partir de `definicion()["requests"]` (campo `dataset`),
  `CAMPOS` y `kind()`, arma una hoja por requerimiento entregado y cambia cada dato del cliente que tus cédulas
  traen pegado por una fórmula a su celda. Para que el enlace funcione: en cada fila de una cédula de detalle va
  el **identificador de la partida** tal como lo entregó el cliente (1.ª columna del anexo), y el dato con el
  **mismo valor** bajo un **encabezado parecido** al del campo (misma raíz o sigla). Una columna se enlaza si
  ninguna partida la contradice; si el cliente dejó el dato en blanco y usas otro dato de la fila o un valor por
  defecto, el enlazador escribe `IF(dato="",…,dato)`. Si es un cálculo (índices de período, vencimientos, fechas
  derivadas), escríbelo como fórmula (`fx`): **ninguna cifra ni fecha puede quedar pegada** en una cédula
  (solo `02_Parametros` y `00_…`); lo vigila `tests/test_aud_datos_cliente.py::test_ninguna_cifra_ni_fecha_queda_pegada`.
- **Si la herramienta necesita cruces propios** (varios anexos por clave, como pérdidas incurridas), arma sus
  hojas `D…` a mano en `hojas()` (con claves de cruce `F…`, `A…`, `C…` en columnas `ocultas`) y agrega su id a
  `datos_cliente.PROPIAS`.
- Verificación: `python scripts/verificar_datos_cliente.py <id>` (LibreOffice) debe dar «DIFERENCIAS: 0».

## Prueba `tests/test_proc_<id>.py` (sin base de datos)
- Import: `from backend.app.aud.niif.procesadores import <id> as m`
- Ejemplo de la ficha con cifras recalculadas a mano (`assert` exactos).
- Casos límite: anexo vacío (ValueError), negativos, faltantes, ruta por marco, parámetro fuera de rango.
- `hojas()`: nombres = CEDULAS y todas las filas con el ancho de `cols`.
- Ejecutar: `python -m pytest tests/test_proc_<id>.py -q -p no:warnings`

## Verificación (obligatoria, todo en verde antes de entregar)
1. `python -m pytest tests/test_proc_<id>.py -q -p no:warnings`
2. `python scripts/verificar_formulas.py <id>` → `DIFERENCIAS: 0`. Abre cada escenario en **Excel real**
   (Windows + pywin32), recalcula y compara cada fórmula con Python. Sin Windows, recalcular con LibreOffice
   (`soffice --headless --convert-to xlsx`) y comparar con `openpyxl` (`data_only=True`) es una prueba previa
   útil, pero **no reemplaza** la de Excel real.
3. `python scripts/verificar_explicaciones.py <id>` → sin columnas sin explicación humana y con `PANEL` resuelto.
4. `python scripts/verificar_problemas_enlazados.py <id>` → `PENDIENTES: 0`.
5. Pruebas transversales, filtradas a tu herramienta y sin base de datos:
   `python -m pytest -q -p no:warnings tests/test_aud_sin_datos_fijos.py tests/test_aud_html_premium.py tests/test_aud_office_como_html.py -k <id>`
6. El Excel no puede levantar el aviso «Excel pudo abrir el archivo reparando…» (regla suprema del `CLAUDE.md`):
   ningún texto que empiece con `=`, `+`, `-` o `@` sin ser fórmula, y paréntesis balanceados.

## Prohibido
Editar archivos compartidos: `procesadores/__init__.py`, `ciclo/*.py`, frontend, otros procesadores, y las piezas
de los formatos (`libro.py`, `panel_excel.py`, `papel_office.py`, `svg_png.py`, `html_ejecutivo.py`,
`graficos.py`, `graficos_svg.py`, `problemas.py`, `marca.py`, `base.py`, `declarativo.py`). Solo se crean el
módulo y su prueba.
Si una pieza compartida no alcanza, se reporta como duda; no se parchea. No correr la suite completa (usa una
base compartida).

## Códigos de rubro (tarjetas)
CAJA_BANCOS · CXC · INVERSIONES · INVENTARIOS · ACTIVOS_FIJOS · ARRENDAMIENTOS · PROPIEDADES_INVERSION ·
INTANGIBLES · BIOLOGICOS · SEGUROS · PROVEEDORES · PRESTAMOS · NOMINA · INGRESOS · COSTOS_GASTOS · PROVISIONES ·
IMPUESTOS · PATRIMONIO
