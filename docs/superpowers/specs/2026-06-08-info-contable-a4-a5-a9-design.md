# Diseño: Auto-llenado de "Información contable" en anexos A4, A5, A9

**Fecha:** 2026-06-08
**Autor:** AuditBrain (asistido por IA) + revisión auditor
**Estado:** Aprobado para implementación
**Anexos afectados:** A4 (Conciliación Ingresos), A5 (Conciliación Costos/Gastos), A9 (Inventarios)

---

## 1. Problema

En el ICT, cada anexo de conciliación tiene dos lados:

- **"Datos de la declaración del Impuesto a la Renta (a)"** → ya se llena con fórmulas
  que referencian `DATOS F-101` (trabajo previo, commits hasta `5832d11`).
- **"Información contable"** (código de cuenta contable, nombre de cuenta, valor en
  libros / costo total) → **queda vacía** (formato condicional la marca en rojo).

El lado contable está vacío **tanto en el código (ICT_15) como en el golden master
ICT_14** — el SRI lo diseñó como llenado del auditor. AuditBrain puede agregar valor
trasladando la parte **derivable** del balance del cliente, con **fórmulas vivas**
(nunca valores pegados), respetando la relación casillero → cuentas contables.

### Estado verificado (empírico, 2026-06-08)

| Anexo | Col casillero | Cód. cuenta | Nombre | Valor en libros | Viabilidad auto |
|---|---|---|---|---|---|
| A4 Concil. Ingresos | B (manual auditor) | C | D | G | Reactiva |
| A5 Concil. Costos/Gastos | B (manual auditor) | C | D | K | Reactiva |
| A9 Inventarios | A (9 casilleros fijos) | D | — | G (Costo Total) | Automática |
| A8 Comercio Exterior | A | B | C | *(sin col. saldo)* | Fuera de alcance |
| A6 Beneficios | sin col. casillero | A | B | E | Fuera de alcance |
| A7 Crédito | estructura por años | — | — | — | No aplica |

**Alcance de esta entrega:** A4, A5, A9. (A6, A7, A8 quedan para entrega posterior.)

---

## 2. Decisión técnica clave: fuente de las fórmulas

El usuario pidió "que las fórmulas vengan del mapeo A1". Al diseñarlo se descubrió
(verificado empíricamente) que **el A1 no permite `SUMAR.SI` directo**: el número de
casillero está **fusionado** — aparece solo en la primera fila de cada bloque, y las
filas de cuentas hijas tienen la columna A vacía. Un `SUMAR.SI` por la columna A del
A1 sumaría únicamente la primera cuenta del bloque, no el total.

**Solución:** sumar sobre la hoja **`DATOS BALANCE`**, que es **la fuente exacta que
alimenta el A1** (el A1 referencia esas mismas celdas con `='DATOS BALANCE'!D<row>`).
`DATOS BALANCE` tiene el casillero SRI **repetido en cada fila**:

| Col A | Col B | Col C | Col D | Col E |
|---|---|---|---|---|
| Casillero SRI | Código Contable | Nombre Cuenta | Saldo 31-dic | Origen |

El total por casillero calculado con `SUMAR.SI` sobre `DATOS BALANCE` es **idéntico**
al que el A1 muestra para ese casillero → cumple el requisito "viene del mapeo",
es trazable, robusto (da 0 si el casillero no existe) y permite fórmulas reactivas.

`DATOS BALANCE` se construye **antes** de los fillers (`service.py:520`), por lo que
**no se requiere post-paso** ni dependencia de orden entre fillers.

---

## 3. Fórmulas a generar

> openpyxl escribe las fórmulas en **inglés** (`SUMIF`, `IF`) con **coma** como
> separador de argumentos en el XML. Excel las muestra traducidas (`SUMAR.SI`, `SI`)
> y con `;` según la configuración regional del cliente. **Escribir siempre la forma
> inglesa con coma**, o el Excel levanta el cuadro de reparación / `#¿NOMBRE?`.

### 3.1 A9 — casilleros fijos (automático)

Para cada uno de los 9 casilleros (filas 18–26, `A9_CASILLEROS`):

```
# Saldos de inventario (7001, 7010, 7013, 7022, 7025, 7028, 7031, 7034):
G<row> = ABS(SUMIF('DATOS BALANCE'!$A:$A, <casillero>, 'DATOS BALANCE'!$D:$D))

# Ajustes (7037) — respeta signo:
G26   = SUMIF('DATOS BALANCE'!$A:$A, 7037, 'DATOS BALANCE'!$D:$D)
```

- `<casillero>` es el número literal (7001, 7010, …) — ya conocido en `a9.py`.
- **Regla de signo (verificada empíricamente, PROPHAR 2026-06-08):** el balance
  guarda los inventarios **finales** con signo **negativo** (nombre de cuenta
  `"(-) Inventario final de …"`) porque restan en el cálculo del costo de ventas.
  El F-101 los declara en **positivo**. Por eso el Costo Total usa `ABS(...)` para
  todos los casilleros de saldo de inventario; **solo 7037 (ajustes)** mantiene el
  signo directo. Sin esta normalización, 7022/7028/7034 darían diferencias **falsas**
  de signo. Con ella, las 9 diferencias dan **0.00** (el inventario contable cuadra
  exacto con lo declarado).
- Diferencia `H<row> = G<row> - C<row>` (si la plantilla aún no la trae como fórmula).
- **Código de cuenta contable, al máximo detalle (col D):** también **fórmula viva**
  (no texto pegado). Como cada casillero de inventario en PROPHAR tiene exactamente
  1 cuenta:

  ```
  D<row> = IFERROR(INDEX('DATOS BALANCE'!$B:$B, MATCH(<cas>, 'DATOS BALANCE'!$A:$A, 0)), "")
  ```

  trae el código (`5PYG.53602.017`) desde el balance; si el casillero no tiene cuenta
  (7001, 7010) → celda vacía (no `#N/A`).
  - **Si un casillero tuviera varias cuentas** (no ocurre en PROPHAR): listar los
    códigos en la misma celda (1 fila por casillero) separados por **" / "**:

    ```
    D<row> = TEXTJOIN(" / ", TRUE, IF('DATOS BALANCE'!$A:$A=<cas>, 'DATOS BALANCE'!$B:$B, ""))
    ```

    Se elige `" / "` (barra con espacios) en vez de `"-"` porque muchos planes de
    cuentas usan guiones dentro del código (ambigüedad); la barra casi nunca aparece
    en un código contable. El desglose cuenta-por-cuenta completo ya vive en el A1
    (que sí expande filas); el A9 queda como resumen y el A1 como máximo detalle.
  - Verificado empíricamente (PROPHAR 2026-06-08): 7 casilleros con 1 cuenta cada uno,
    2 casilleros (7001/7010) sin cuenta → columna D queda vacía en esos dos.

> **Prueba de cuadre A9 (PROPHAR, 2026-06-08):** los 9 casilleros cuadran a 0.00.
> TOTAL declarado = TOTAL costo contable = 4.524.122,81. La lógica SUMIF+ABS está
> validada con datos reales del cliente antes de implementar.

### 3.2 A4 / A5 — casillero lo escribe el auditor (reactivo)

El número de casillero (col B) es input manual. Se coloca una fórmula reactiva en la
columna de valor en libros que se activa cuando el auditor escribe el casillero:

```
A4: G<row> = IF($B<row>="", "", ABS(SUMIF('DATOS BALANCE'!$A:$A, $B<row>, 'DATOS BALANCE'!$D:$D)))
A5: K<row> = IF($B<row>="", "", ABS(SUMIF('DATOS BALANCE'!$A:$A, $B<row>, 'DATOS BALANCE'!$D:$D)))
```

> Se usa `ABS(...)` por consistencia con A9: el valor en libros de ingresos exentos /
> gastos no deducibles se presenta en positivo (a validar cuando el auditor cargue
> casilleros reales en estos cuadros).

- Rangos de filas: A4 Cuadro 1 = filas 16–25 (`A4_CUADRO1_RANGE`); A5 Cuadro A =
  filas 17–21.
- **No** se tocan las filas SUM/total ni de diferencia que la plantilla ya trae como
  fórmula (documentadas en los cell_maps como "NOT touched").
- Código + nombre de cuenta en A4/A5 quedan como input del auditor (dependen de la
  cuenta específica que desglose; no hay relación 1:1 automática a una sola cuenta).

---

## 4. Arquitectura

### Componente nuevo — helper en `referential_helpers.py`

```
set_libros_sumif_ref(ws, cell_addr, casillero=None, casillero_cell=None,
                     balance_sheet="DATOS BALANCE", anexo=None) -> bool
```

- Si `casillero` (literal) → escribe `SUMIF(...)` con criterio numérico.
- Si `casillero_cell` (ej. `"$B17"`) → escribe `IF($B17="","",SUMIF(...,$B17,...))`.
- Usa `safe_set_formula` (escapado/registro de origen ya existente).
- Devuelve `bool` (escrita / no escrita).

Helper auxiliar (mismo módulo o `formatting.py`):

```
cuentas_por_casillero(balance_lookup_raw) -> dict[str, list[(codigo, nombre)]]
```

para decidir, en A9, si un casillero tiene 1 sola cuenta (rellenar código+nombre) o
varias (dejar en blanco).

### Cambios en fillers

- `a9_inventarios.py`: tras escribir el valor declarado, escribir `G<row>` SUMIF por
  casillero fijo + diferencia `H` + código/nombre si 1 cuenta.
- `a4_conciliacion_ingresos.py`: escribir fórmula reactiva en `G16:G25`.
- `a5_conciliacion_costos.py`: escribir fórmula reactiva en `K17:K21`.

### Sin cambios

- No se modifica el A1 ni `DATOS BALANCE`.
- No se modifica el lado "Datos de la declaración (F-101)" (ya correcto).
- No se modifican filas de totales/diferencia que ya son fórmula en plantilla.

---

## 5. Separación SRI vs Papel de trabajo

Las columnas de información contable son parte de la **estructura oficial** del anexo
(el SRI las pide), así que van en **ambos** archivos (SRI y papel). Las fórmulas
referencian `DATOS BALANCE`, que ya viaja en el archivo SRI (es hoja de datos fuente,
no interna). **Verificar** que `DATOS BALANCE` **no** esté en `INTERNAL_SHEETS_FOR_SRI`.

---

## 6. Pruebas y verificación

### Tests automáticos (pytest)

- `tests/test_ict_fillers_a9.py`: G18 = `=SUMIF('DATOS BALANCE'!$A:$A,7001,'DATOS BALANCE'!$D:$D)`
  (o forma equivalente), por los 9 casilleros; diferencia H = G−C.
- `tests/test_ict_fillers_a4.py` / `a5`: fórmula reactiva `IF($B..="",...)` presente
  en el rango correcto; filas total/diferencia intactas.
- Regresión: no se rompe ningún test ICT existente (suite completa en verde).

### Verificación empírica (regla suprema CLAUDE.md)

1. Regenerar PROPHAR (`scripts/generate_ict15_prophar.py`).
2. Abrir A9: confirmar que el Costo Total por casillero (col G) = la suma de las
   cuentas del balance con ese casillero (comparar contra `DATOS BALANCE` filtrado).
3. Confirmar que la diferencia (col H) ya no es "todo el valor declarado" (deja de
   estar en rojo donde hay saldo contable).
4. Cargar el .xlsx con openpyxl tras guardar y recorrer hojas buscando celdas
   problemáticas — el Excel **no** debe levantar el cuadro de reparación.
5. Confirmar que el archivo **SRI** conserva las fórmulas (DATOS BALANCE presente).

---

## 7. Fuera de alcance (futuro)

- A8 Comercio Exterior (lista de cuentas por casillero, sin columna de saldo).
- A6 Beneficios (sin columna de casillero; requiere otra lógica de relación).
- A7 Crédito Tributario (estructura por años, no por casillero→cuenta).
- Columnas de juicio del auditor (forma de valoración, técnica de medición, cantidad
  física, observaciones) — no derivables del balance, quedan manuales por diseño.
