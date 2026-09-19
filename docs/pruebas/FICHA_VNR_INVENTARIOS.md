# Ficha de prueba · Valor neto de realización (inventarios)

Estado: **especificación** · no liberada · 2026-09-19
Memoria metodológica aplicada: v1.1.0 (M01–M15)

Esta ficha es el producto del paso de fábrica (M01: AuditBrain diseña, GitHub
conserva, AUDIT-IA ejecuta). Define entradas, reglas, cédulas y controles
**antes del código**. Ninguna afirmación de esta ficha es una liberación.

---

## 1 · Identificación

| Campo | Valor |
|---|---|
| Prueba | Valor neto de realización de inventarios |
| Rubro | Inventarios |
| Marcos verificados | NIIF completas (NIC 2, NIC 12) y NIIF para las PYMES (Secciones 13 y 27) |
| Jurisdicción verificada | Ecuador (RALRTI) |
| Normas de auditoría | NIA 501 |

**Advertencia de terminología.** En NIIF para las PYMES **no se usa el término
«valor neto de realización»**. El módulo educativo oficial de la IFRS Foundation
para la Sección 13 lo dice expresamente:

> *«Section 13 describes inventory as being measured at the lower of cost and
> "estimated selling price less costs to complete and sell", instead of using
> the term "net realisable value" as in IAS 2.»*

El concepto sí está en la Sección 13 (¶13.4) y es sustancialmente equivalente,
pero la herramienta **no debe rotular «VNR» en un cliente PYMES**.

---

## 2 · Matriz normativa

Estado `verificado` = texto leído en fuente oficial, con párrafo.

### 2.1 Medición · NIIF completas (NIC 2)

| ¶ | Texto verificado | Estado |
|---|---|---|
| **6** | *«Net realisable value is the estimated selling price in the ordinary course of business less the estimated costs of completion and the estimated costs necessary to make the sale.»* | verificado |
| **9** | *«Inventories shall be measured at the lower of cost and net realisable value.»* | verificado |
| **33** | *«A new assessment is made of net realisable value in each subsequent period. When the circumstances that previously caused inventories to be written down below cost no longer exist or when there is clear evidence of an increase in net realisable value because of changed economic circumstances, the amount of the write-down is reversed (ie the reversal is limited to the amount of the original write-down) so that the new carrying amount is the lower of the cost and the revised net realisable value.»* | verificado |
| **34** | *«The amount of any write-down of inventories to net realisable value and all losses of inventories shall be recognised as an expense in the period the write-down or loss occurs.»* | verificado |

Fuente: texto oficial HTML de NIC 2, edición 2024.
https://www.ifrs.org/content/dam/ifrs/publications/html-standards/english/2024/issued/ias2.html
Consultado 2026-09-19.

### 2.2 Medición · NIIF para las PYMES

| ¶ | Contenido verificado | Estado |
|---|---|---|
| **13.4** | *«An entity shall measure inventories at the lower of cost and estimated selling price less costs to complete and sell.»* | verificado |
| **27.2** | Evaluar en cada fecha de reporte si hay deterioro, comparando el importe en libros de **cada partida** (o grupo de partidas similares) con su precio de venta menos costos de terminación y venta. La reducción es pérdida por deterioro reconocida de inmediato en resultados | verificado |
| **27.3** | Si es **impracticable** determinarlo partida por partida, se pueden **agrupar** partidas de la misma línea de producto con características similares | verificado |
| **27.4** | Exige la **reversión** de un deterioro previo en determinadas circunstancias | verificado |

Fuente: texto oficial HTML, tercera edición (2025).
https://www.ifrs.org/content/dam/ifrs/publications/html-standards/english/2025/issued/html-ifrs-for-smes.html

**Diferencias frente a NIC 2, relevantes para el diseño:**
1. El deterioro de inventarios **no está en la Sección 13 sino en la Sección 27**.
2. La Sección 27.3 permite **agrupar por línea de producto** cuando el análisis
   ítem por ítem es impracticable. NIC 2 no ofrece esa salida.
3. No se usa el término «valor neto de realización».

**Vigencia.** La tercera edición (2025) rige para períodos iniciados desde el
1-ene-2027, con aplicación anticipada permitida. Para ejercicios anteriores
debe confirmarse la edición aplicable y su adopción local.

### 2.3 Impuesto diferido · NIC 12

| ¶ | Contenido verificado | Estado |
|---|---|---|
| **5** | Diferencias temporarias deducibles: diferencias entre el importe en libros de un activo o pasivo y su base fiscal que darán lugar a importes deducibles al determinar la ganancia (pérdida) fiscal de períodos futuros cuando el importe en libros sea recuperado o liquidado | verificado |
| **7 y 8** | *«The tax base of an asset is the amount that will be deductible for tax purposes against any taxable economic benefits that will flow to an entity when it recovers the carrying amount of the asset.»* | verificado |
| **24** | *«A deferred tax asset shall be recognised for all deductible temporary differences to the extent that it is probable that taxable profit will be available against which the deductible temporary difference can be utilised.»* | verificado |
| **27** | Las diferencias deducibles se utilizan cuando su reversión produce deducciones compensadas contra ganancias fiscales de períodos futuros; el beneficio fluye solo si se obtienen ganancias fiscales suficientes | verificado |
| **28–29** | Tres fuentes de ganancia fiscal: (a) reversión futura de diferencias temporarias imponibles existentes; (b) ganancia fiscal de períodos futuros; (c) oportunidades de planificación fiscal | verificado |
| **47** | *«Deferred tax assets and liabilities shall be measured at the tax rates that are expected to apply to the period when the asset is realised or the liability is settled, based on tax rates (and tax laws) that have been enacted or substantively enacted by the end of the reporting period.»* | verificado |
| **53** | *«Deferred tax assets and liabilities shall not be discounted.»* | verificado |
| **56** | *«The carrying amount of a deferred tax asset shall be reviewed at the end of each reporting period. An entity shall reduce the carrying amount of a deferred tax asset to the extent that it is no longer probable that sufficient taxable profit will be available… Any such reduction shall be reversed to the extent that it becomes probable that sufficient taxable profit will be available.»* | verificado |

Fuente: texto oficial HTML de NIC 12, edición 2021.
https://www.ifrs.org/content/dam/ifrs/publications/html-standards/english/2021/issued/ias12.html

### 2.4 Tributación · Ecuador (RALRTI)

| Norma | Contenido verificado | Estado |
|---|---|---|
| **Art. (…) Impuestos diferidos, numeral 1** | *«Las pérdidas por deterioro producto del ajuste realizado para alcanzar el valor neto de realización del inventario, serán consideradas como no deducibles en el periodo en el que se registren contablemente; sin embargo, se reconocerá un impuesto diferido por este concepto, el cual podrá ser utilizado en el momento en que se produzca la venta, baja o autoconsumo del inventario.»* Agregado por D.E. 539, R.O. 407-3S, 31-XII-2014; reformado por D.E. 617, R.O. 392-S, 20-XII-2018 | verificado |
| **Art. (…) Impuestos diferidos, encabezado** | *«…se permite el reconocimiento de impuestos diferidos, **únicamente** en los siguientes casos y condiciones»* — la lista es **cerrada** | verificado |
| **Art. 28, numeral 8, literal b)** | *«Las pérdidas por las bajas de inventarios se justificarán mediante declaración juramentada realizada ante un notario o juez, por el representante legal, bodeguero y contador, en la que se establecerá la destrucción o donación de los inventarios…»* El SRI puede solicitar en cualquier momento actas, documentos y registros contables que respalden la baja | verificado |
| **Art. 28, numeral 8, literal a)** | Deducibles las pérdidas por destrucción, daños, desaparición y otros eventos debidos a caso fortuito, fuerza mayor o delitos, en la parte no cubierta por indemnización o seguros. Conservar documentos probatorios no menos de seis años | verificado |

Fuente: Reglamento para la Aplicación de la LRTI, texto del SRI actualizado al
24-nov-2023, 218 páginas.
https://www.sri.gob.ec/o/sri-portlet-biblioteca-alfresco-internet/descargar/aa569bb7-b871-458c-a8c7-6bcf49841843/Reglamento_LRTI_24Nov2023.pdf
Consultado 2026-09-19.

**Verificación negativa registrada:** se buscó «valor neto de realización» en
las 218 páginas del Reglamento. Aparece **una sola vez**, en el numeral 1 citado
arriba. No existe otra disposición sobre deterioro de inventarios.

### 2.5 Procedimiento de auditoría · NIA 501

| Contenido verificado | Estado |
|---|---|
| Si el inventario es material, el auditor debe obtener evidencia sobre existencia y condición **asistiendo al conteo físico**, salvo que sea impracticable; la mera incomodidad del auditor no lo es. Incluye recuentos de prueba y observación del cumplimiento de las instrucciones de la dirección | verificado |
| Si la asistencia es impracticable, procedimientos alternativos, por ejemplo inspección de documentación de **ventas posteriores** | verificado |

Fuente: https://www.iaasb.org/_flysystem/azure-private/publications/files/A023%202013%20IAASB%20Handbook%20ISA%20501.pdf

---

## 3 · Requerimiento al cliente

Cada requerimiento deriva de un término de la norma (M06). Se solicita por
contenido, no por extensión de archivo.

### 3.1 Medición

| Requerimiento | Obligatoriedad | Deriva de |
|---|---|---|
| Inventario valorado al corte: código/lote, descripción, unidad, cantidad, costo unitario y total | obligatorio | El «costo» de la comparación (NIC 2 ¶9 / PYMES ¶13.4) |
| Lista de precios vigente al corte **y ventas posteriores al corte** | obligatorio | Precio estimado en el curso ordinario (NIC 2 ¶6). Las ventas posteriores son además el procedimiento alternativo de NIA 501 |
| Costos de terminación por ítem | obligatorio si hay producto en proceso o por acondicionar | NIC 2 ¶6 |
| Costos necesarios para vender por ítem, con base de asignación sustentada | obligatorio | NIC 2 ¶6 |
| Políticas contables de inventario y método de costeo | obligatorio | Contraste con el marco |
| **Deterioro ya contabilizado al corte, por ítem** | obligatorio | Sin este dato la diferencia se duplica (M09) |
| Deterioros reconocidos en períodos anteriores y su importe original | obligatorio si hay indicios de recuperación | Límite de la reversión (NIC 2 ¶33) |
| Conciliación del inventario con el mayor | obligatorio | Integridad de la población |
| Instrucciones y actas del conteo físico | obligatorio si el inventario es material | NIA 501 |

### 3.2 Impuesto diferido (Ecuador)

| Requerimiento | Deriva de |
|---|---|
| Confirmación de que el deterioro registrado corresponde al ajuste a valor neto de realización | RALRTI Impuestos diferidos num. 1 |
| Tasa de impuesto a la renta esperada al momento de la reversión y norma que la promulga | NIC 12 ¶47 |
| Evidencia de ganancia fiscal futura: proyecciones, diferencias temporarias imponibles existentes, planificación fiscal | NIC 12 ¶24, ¶28-29 |
| Movimientos del período por **venta, baja o autoconsumo** de inventario previamente deteriorado, por ítem y cantidad | RALRTI: disparador de la utilización del diferido |
| Actas de baja con declaración juramentada ante notario o juez, firmadas por representante legal, bodeguero y contador | RALRTI Art. 28 num. 8 lit. b) |

---

## 4 · Cédulas

| # | Cédula | Depende de | Estado |
|---|---|---|---|
| 1 | Base de inventarios conciliada con el mayor | Req. 3.1 | especificada |
| 2 | Parámetros y criterio (marco, edición, fuente del precio, base de asignación, redondeo, tasa) | Ficha del encargo | especificada |
| 3 | Cálculo por ítem y comparación con el costo | 1, 2 | especificada |
| 4 | Deterioro requerido frente al contabilizado · **diferencia neta** | 3, req. deterioro contabilizado | especificada |
| 5 | Excepciones y controles | 3, 4 | especificada |
| 6 | Reversión de deterioros previos, con límite del deterioro original | 3, 4 | especificada |
| 7 | Diferencias temporarias por ítem: libros, base fiscal, diferencia y tipo | 4, req. 3.2 | especificada |
| 8 | Reconocimiento y medición del impuesto diferido | 7 | especificada |
| 9 | Seguimiento de la utilización del diferido por venta, baja o autoconsumo | 7, 8 | especificada |
| 10 | Conclusión y fuentes normativas | 1–9 | especificada |

**Variante PYMES.** Si el marco es NIIF para las PYMES, la cédula 3 debe
rotularse con la terminología de la Sección 13 y admitir la agrupación por línea
de producto del ¶27.3 cuando el análisis ítem por ítem sea impracticable,
documentando por qué lo es.

---

## 5 · Reglas de cálculo

### 5.1 Medición (verificadas contra NIC 2 ¶6 y ¶9)

Implementadas en el motor del sitio AuditBrain, `lib/tools/domain.mjs`:

```
net_price     = selling_price - completion_cost      precisión 6
nrv_unit      = net_price - selling_cost             precisión 6
nrv_floor     = MAX(nrv_unit, 0)                     precisión 6
carrying_unit = MIN(unit_cost, nrv_floor)            precisión 6
cost          = quantity * unit_cost                 precisión 2
recoverable   = quantity * carrying_unit             precisión 2
impairment    = cost - recoverable                   precisión 2
adjustment    = impairment - recorded_allowance      precisión 2
```

Campo de conciliación: `cost`. Resultado principal: `impairment`.

### 5.2 Reversión (NIC 2 ¶33)

| Regla | Definición |
|---|---|
| RV1 | Nueva evaluación en cada período posterior |
| RV2 | Procede solo si desaparecieron las circunstancias que causaron la rebaja, o hay evidencia clara de aumento del valor por circunstancias económicas cambiadas |
| RV3 | **Límite**: la reversión no puede exceder el importe de la rebaja original |
| RV4 | El nuevo importe en libros es el menor entre el costo y el valor revisado |

No se revierte por la mera etiqueta «VENDIDO» o «BAJA»: esos son eventos de
realización, no de recuperación de valor.

### 5.3 Impuesto diferido (NIC 12 + RALRTI)

| Regla | Definición | Norma |
|---|---|---|
| R1 · Importe en libros por ítem | `recoverable`, posterior al deterioro | NIC 2 |
| R2 · Base fiscal por ítem | En Ecuador, **el costo**: la pérdida por deterioro no es deducible al registrarse, luego el importe deducible futuro sigue siendo el costo | NIC 12 ¶7-8 + RALRTI num. 1 |
| R3 · Diferencia temporaria | libros − base fiscal. Al ser libros < base fiscal, la diferencia es **deducible** → corresponde un **activo** por impuesto diferido | NIC 12 ¶5 |
| R4 · Admisibilidad tributaria | Solo los conceptos de la lista cerrada del Reglamento. El deterioro a VNR de inventarios **está** en la lista (numeral 1) | RALRTI |
| R5 · Reconocimiento contable | Solo en la medida en que sea **probable** que exista ganancia fiscal futura, evaluando las tres fuentes. R4 y R5 son condiciones **acumulativas** | NIC 12 ¶24, ¶27, ¶28-29 |
| R6 · Medición | Tasa esperada al momento de la reversión, promulgada o sustancialmente promulgada al cierre | NIC 12 ¶47 |
| R7 · Sin descuento | No se descuentan activos ni pasivos por impuesto diferido | NIC 12 ¶53 |
| R8 · Revisión al cierre | Revisar el importe del activo; reducirlo si deja de ser probable la ganancia fiscal, y reponerlo si vuelve a serlo | NIC 12 ¶56 |
| R9 · Utilización | El diferido se utiliza al producirse **venta, baja o autoconsumo** del inventario. Para la baja se exige declaración juramentada ante notario o juez | RALRTI num. 1 y Art. 28 num. 8 lit. b) |

**Limitación técnica registrada.** El motor solo admite `add, subtract,
multiply, divide, min, max` sobre campos numéricos. R3 requiere clasificación
por signo, R4 una verificación contra una lista cerrada, y R5 y R8 son
decisiones sustentadas en evidencia. Implementarlas con las piezas actuales
produciría `diferencia × tasa`, que la memoria declara insuficiente (Manual §10).

### 5.4 Controles exigidos

| Control | Comportamiento exigido |
|---|---|
| División por cero | **Bloquea** el cálculo. Nunca devolver cero (Manual §12) |
| VNR negativo | Excepción; el deterioro se limita al costo; evaluar obligaciones por separado |
| Deterioro > 0 | Excepción para revisión del auditor |
| Reversión propuesta | Excepción; verificar límite del deterioro original (RV3) y sustento antes de registrar |
| Celda de origen sin recalcular | Rechazar y exigir recálculo del Excel fuente (Manual §08) |
| Fila de total o subtotal | Rechazar; pedir archivo de detalle |
| Duplicado exacto | Error, sin eliminar la fila |
| Identificador repetido | Advertencia: comprobar lotes o partidas |
| Marco PYMES con agrupación | Exigir documentar por qué es impracticable el análisis ítem por ítem (¶27.3) |

---

## 6 · Diagnóstico del Excel del auditor

Archivo evaluado: `plantilla_vnr_inventarios_auditbrain_final.xlsx`, 11 hojas.
Revisión de fórmulas celda por celda, 2026-09-19.

| # | Hallazgo | Evidencia | Regla incumplida |
|---|---|---|---|
| 1 | **Costo de venta cero en silencio.** Con `Metodo_VNR = GLOBAL` (valor por defecto) y ventas y gastos en cero, `B7 = IFERROR(B6/B5, 0)` devuelve 0. El VNR queda sobreestimado y el deterioro subestimado, sin aviso | `Parametros_VNR!B4..B7` | Manual §12 |
| 2 | **No captura el deterioro contabilizado.** `Base_Inventarios` tiene 15 columnas y ninguna lo registra; `Asientos!D3 = SUM(Calculo_VNR!O2:O18)` propone el deterioro completo | `Base_Inventarios`, `Asientos` | M09 |
| 3 | **Tasa fija tecleada** sin sustento ni referencia a la esperada en la reversión | `Parametros_VNR!B8 = 0.25` | NIC 12 ¶47 |
| 4 | **Sin prueba de recuperabilidad.** Reconoce el activo por diferido sin evaluar ganancia fiscal futura probable | `Asientos!B4` | NIC 12 ¶24, ¶28-29 |
| 5 | **La columna «Base Fiscal» no es una base fiscal.** Contiene el importe deducible del deterioro | `Calculo_VNR!P` | NIC 12 ¶7-8 |
| 6 | **Impuesto diferido calculado dos veces.** `Calculo_VNR!R` y `Tributario!H` hacen la misma operación; pueden divergir | ambas hojas | Reproducibilidad |
| 7 | **Nombres inconsistentes entre hojas.** `Calculo_VNR!Q` («Diferencia Temporaria») aparece en `Tributario` como «No Deducible» | `Tributario!F` | M10 |
| 8 | **Período fijo en el nombre de hoja**: `Seguimiento_2026` | hoja | Manual §12 |
| 9 | **Sin seguimiento por causa legal.** El Reglamento condiciona la utilización del diferido a venta, baja o autoconsumo; la plantilla no distingue esas causas ni exige el acta notariada | `Reversos`, `Seguimiento_2026` | RALRTI num. 1 y Art. 28 num. 8 lit. b) |
| 10 | **Sin límite de reversión** al importe de la rebaja original | `Reversos` | NIC 2 ¶33 |

**Lo correcto de la plantilla**, registrado para no perderlo:
- `M = MAX(0, I-J-L)` y `O = MAX(0, G-N)` coinciden con NIC 2 ¶6 y ¶9.
- La trazabilidad entre hojas por fórmula está bien construida.
- Con `Permite Deduccion Fiscal Inmediata = NO`, el importe de la diferencia
  temporaria que produce **coincide con lo que manda el Reglamento ecuatoriano**,
  porque el deterioro a VNR no es deducible al registrarse. El método es pobre
  (una casilla global), pero el número resultante es defendible en Ecuador.

**Conclusión del diagnóstico**: la herramienta del catálogo se construye sobre
el motor del sitio, no sobre esta plantilla. El motor ya corrige los hallazgos
1 y 2, y no arrastra del 3 al 10 porque no implementa diferido ni reversión.

---

## 7 · Pendientes

Los cuatro pendientes de investigación de la versión anterior quedaron
cerrados el 2026-09-19. Permanecen:

| Pendiente | Qué bloquea | Responsable |
|---|---|---|
| El motor no puede expresar R3, R4, R5 ni R8 | Implementación del impuesto diferido | Diseño técnico |
| Edición de NIIF para las PYMES aplicable y su adopción local | Uso en clientes PYMES antes de 2027 | Criterio de la firma por encargo |
| Política de la firma sobre evidencia mínima de ganancia fiscal futura | Cédula 8 | Criterio de la firma |

---

## 8 · Trazabilidad de esta ficha

| Dato | Valor |
|---|---|
| Fecha | 2026-09-19 |
| Memoria aplicada | v1.1.0 |
| Motor de referencia | `auditbrain-site/lib/tools/domain.mjs`, `portable-engine.mjs` (ENGINE_VERSION 3.0.0) |
| Excel diagnosticado | `plantilla_vnr_inventarios_auditbrain_final.xlsx`, 11 hojas |
| Fuentes normativas | Textos oficiales de NIC 2 (2024), NIC 12 (2021), NIIF para las PYMES (2025), módulo educativo Sección 13, NIA 501 y RALRTI del SRI (24-nov-2023) |
| Limitación de acceso | Los PDF de NIC 2, NIC 12 y NIIF PYMES en `pdf-standards` requieren registro. La verificación se hizo sobre las versiones HTML oficiales, de acceso público |
| Estado | Especificación. Sin código, sin pruebas, sin liberación |
