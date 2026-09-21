# CXC-PI-01 · Deterioro de cuentas por cobrar comerciales — pérdidas incurridas

**Cuenta:** Cuentas por cobrar comerciales · **Marco:** solo **NIIF para las PYMES**
**Origen:** herramienta `AuditBrain_Prueba_Perdidas_Incurridas.html` (motor en navegador), llevada al
proceso de creación de herramientas del Command Center.
**Estado:** construida y probada de punta a punta (procesador `perdidas_incurridas_s11`); pendiente de la
aprobación del dueño para enviarla al catálogo de Cuentas por cobrar.

> Con **NIIF completas** esta prueba no aplica: la NIIF 9 usa **pérdida esperada** (ficha `pce`, párr.
> 5.5.15). Las PYMES siguen el modelo de **pérdida incurrida**: solo hay deterioro si ya ocurrió un
> evento de pérdida.

---

## A · Base técnica

### A.1 · Lo que dice la Sección 11 y cómo se traduce en cálculo

Párrafos según la numeración de la edición 2015 de la NIIF para las PYMES. **VERIFICAR** la numeración
en la edición vigente del encargo antes de aprobar la ficha.

| Párrafo | Qué establece | Cómo lo aplica la herramienta |
|---|---|---|
| **11.13** | Las cuentas por cobrar a corto plazo sin interés contractual se miden al importe no descontado | Tasa de descuento por defecto **0 %**; solo se descuenta si el auditor documenta una financiación implícita |
| **11.21** | Al final de cada período se evalúa si hay **evidencia objetiva** de deterioro; si la hay, la pérdida se reconoce de inmediato en resultados | La evaluación se hace **al corte del ejercicio corriente**; la pérdida del año va a gasto |
| **11.22** | La evidencia objetiva son **datos observables de eventos de pérdida**: (a) dificultades financieras significativas del deudor; (b) infracciones del contrato, como incumplimientos o **moras en los pagos**; (c) concesiones al deudor; (d) probable quiebra o reorganización; (e) datos observables de una **disminución medible de los flujos de un grupo** de activos, aunque no se identifique con un activo individual | (b) → **antigüedad de la mora** por factura; (e) → **tasas de no recuperación observadas** por tramo, medidas comparando las facturas de un año con las del año siguiente |
| **11.23** | Otros factores: cambios adversos significativos en el entorno tecnológico, de mercado, económico o legal | Se documentan como **juicio del auditor** por cliente; no se automatizan |
| **11.24** | Se evalúan **individualmente** los activos significativos; los demás, individualmente o **agrupados por características de riesgo similares** | Evaluación **individual por cliente** si supera el umbral de saldo o la mora grave (361 días); el resto, **agrupado por tramos de mora** |
| **11.25** | Pérdida = **importe en libros − valor presente de los flujos estimados**, descontados a la **tasa efectiva original** | Por factura: `pérdida = saldo − saldo × (1 − tasa del tramo) ÷ (1 + i)^(plazo/12)`, con i = tasa efectiva y plazo esperado de cobro |
| **11.26** | Si la pérdida **disminuye** por un evento posterior objetivo, se **revierte**, sin superar el costo amortizado que habría tenido sin deterioro | Movimiento por factura: provisión inicial − **reversión** − bajas + provisión del año = saldo final; la reversión se señala para verificar su límite |

**Lo que la Sección 11 no permite, y la herramienta respeta:**
- **Provisión general sobre cartera al día.** El tramo «corriente / por vencer» no lleva una tasa
  supuesta: solo la **observada** (facturas que estaban al día y un año después siguen impagas, 11.22 e);
  sin esa evidencia va al **0 %**. Si un cliente al día tiene dificultades, se evalúa individualmente.
- **Inventar la tasa.** Si un tramo no se puede medir con la historia, porque ninguna factura se localiza
  en el año siguiente, se declara **no medible**. No se asume «cobrado al 100 %»: el auditor fija la tasa
  con su evidencia de gestión de cobro.
- **Tramos terminales sin historia** (más de 730 días): pérdida del 100 % del remanente, **solo** si hay
  evidencia objetiva, es decir, sin abonos desde la emisión. La evidencia observada manda sobre el supuesto.

### A.2 · Normas vinculadas

| Norma | Párrafos | Qué exige en esta prueba |
|---|---|---|
| NIIF PYMES Sección 29 | 29.9–29.18 (**VERIFICAR**) | Activo por impuesto diferido por la diferencia temporaria entre la provisión contable y la deducible |
| NIIF PYMES Sección 32 | 32.2–32.5 (**VERIFICAR**) | Cobros posteriores al cierre como evidencia de hechos que ya existían |

### A.3 · Qué dicen las NIA sobre esta prueba

| Norma | Párrafos | Qué exige en esta prueba |
|---|---|---|
| NIA 540 (Revisada) | párr. 13 y 17–30 | La provisión es una **estimación**: evaluar el método (migración por tramos), los datos (anexos de 3 años) y los supuestos (plazo, tasa, umbrales), y el posible sesgo |
| NIA 500 | párr. 9 | Los anexos de cartera los produce la entidad: evaluar su **exactitud e integridad** contra el mayor antes de usarlos |
| NIA 505 | párr. 7 | Considerar **confirmaciones** de saldos de clientes significativos |
| NIA 560 | párr. 6 | Revisar **cobros posteriores** al cierre como evidencia de recuperabilidad |
| NIA 330 | párr. 18 | Procedimientos sustantivos sobre la valoración de la cartera, que es un saldo material |

### A.4 · Tributario Ecuador

| Norma | Qué exige | Cómo lo aplica |
|---|---|---|
| LRTI Art. 10 num. 11 y RALRTI Art. 28 num. 3 (**VERIFICAR** texto y reformas vigentes al corte) | Deducción anual del **1 %** sobre los créditos comerciales del ejercicio pendientes al cierre, sin que la provisión acumulada supere el **10 %** de la cartera total | Límite anual = 1 % de la cartera corriente; límite acumulado = 10 % de la cartera total; deducible = mínimo entre el gasto del año, el límite anual y el margen acumulado |
| RALRTI, artículo innumerado de impuestos diferidos (**VERIFICAR** si la provisión por deterioro de cartera está entre los casos admitidos al corte) | Reconocimiento del activo por impuesto diferido | Diferencia temporaria = provisión contable − provisión deducible acumulada; activo = diferencia × tasa del impuesto (25 % por defecto, editable) |

Los porcentajes fiscales son **parámetros editables**: se contrastan con la norma vigente al corte.

---

## B · Programa de auditoría

| code | objective | risk | assertion | procedure | evidence | criterion | source |
|---|---|---|---|---|---|---|---|
| CXCPI-01 | Integridad de la cartera | Anexo incompleto o no conciliado | Integridad | Conciliar el anexo de cartera del ejercicio con el mayor al corte | Anexo de cartera y mayor | Diferencia dentro de tolerancia o explicada | NIA 500 párr. 9 |
| CXCPI-02 | Evidencia histórica de recuperación | Tasas sin sustento | Valoración | Emparejar las facturas de cada año con las del año siguiente y medir la no recuperación por tramo | Anexos de cartera de 3 ejercicios | Tasa por tramo medida, o declarada no medible con su causa | Secc. 11 párr. 11.22(e) · NIA 540 |
| CXCPI-03 | Evaluación individual | Clientes significativos o en mora grave sin evaluar | Valoración | Evaluar individualmente los clientes sobre el umbral de saldo o con mora ≥ 361 días | Antigüedad por cliente, gestión de cobro | Tasa y plazo por cliente documentados | Secc. 11 párr. 11.24 |
| CXCPI-04 | Medición de la pérdida | Pérdida mal calculada | Valoración | Recalcular por factura y por cliente: importe en libros − valor presente de los flujos estimados | Detalle por factura | Pérdida recalculada | Secc. 11 párr. 11.25 |
| CXCPI-05 | Movimiento de la provisión | Reversiones o bajas sin sustento | Exactitud | Conciliar provisión inicial − reversiones − bajas + provisión del año con el mayor | Anexo de provisión inicial, mayor | Movimiento conciliado; reversiones dentro del límite | Secc. 11 párr. 11.26 |
| CXCPI-06 | Tratamiento fiscal e impuesto diferido | Deducción excesiva o diferido mal medido | Presentación | Aplicar los límites de deducibilidad y medir el activo por impuesto diferido | Parámetros fiscales, provisión fiscal anterior | Deducible y diferido recalculados | LRTI Art. 10 num. 11 · Secc. 29 |
| CXCPI-07 | Cobros posteriores | Recuperaciones no consideradas | Valoración | Cotejar cobros posteriores al cierre con las facturas deterioradas | Estados de cuenta, depósitos posteriores | Excepciones evaluadas | NIA 560 párr. 6 · Secc. 32 |

---

## C · Requerimientos al cliente

| id | document | use | formats | components | required |
|---|---|---|---|---|---|
| RQ-001 | Anexo de cartera por factura al cierre del **ejercicio corriente** | cálculo | xlsx, csv | — | Sí |
| RQ-002 | Anexo de cartera por factura al cierre del **ejercicio anterior** | cálculo | xlsx, csv | — | Sí, para medir la historia |
| RQ-003 | Anexo de cartera por factura al cierre de **dos ejercicios antes** | cálculo | xlsx, csv | — | Recomendado: da una segunda ventana |
| RQ-004 | Anexo de provisión y diferidos por factura al **inicio** del ejercicio | cálculo | xlsx, csv | — | Sí |
| RQ-005 | Movimiento de la provisión según el mayor (3 ejercicios: inicial, gasto, castigos, recuperaciones) | cálculo | xlsx, csv, pdf | — | Sí |
| RQ-006 | Cobros posteriores al cierre | soporte | xlsx, pdf | — | Sí |
| RQ-007 | Política de crédito y cobranza, gestión de cobro de clientes en mora | soporte | pdf, docx | — | Sí |
| RQ-008 | Ventas por factura de los 3 ejercicios | soporte | xlsx, csv | — | Opcional: el HTML las carga pero **no intervienen en el cálculo** |

**Columnas de los anexos de cartera (RQ-001 a RQ-003, un modelo para los tres años):**

| Columna en el archivo | key | Tipo | Obligatoria | Ejemplo | También puede llamarse |
|---|---|---|---|---|---|
| N° de factura | factura | texto | Sí | 001-001-000123 | numfac, documento, comprobante |
| Cliente | cliente | texto | Sí | Comercial Andina S.A. | nomcli, razón social, deudor |
| Fecha de emisión | emision | fecha | Sí | 2025-03-15 | fecha, fecemi |
| Fecha de vencimiento | vence | fecha | Sí | 2025-04-14 | vencimiento, fecvto |
| Saldo por cobrar | saldo | número | Sí | 1250.00 | saldo pendiente, por cobrar |
| Importe original | importe | número | No | 1250.00 | monto factura, valor original |
| RUC / identificación | ruc | texto | No | 1790000000001 | cédula, código cliente |

**Columnas del anexo de provisión inicial (RQ-004):** N° de factura · Cliente · Provisión · Impuesto
diferido (opcional).

---

## D · Carga de documentos

- **Aceptar** un anexo de cartera si trae **una fila por factura** con saldo y fechas, al corte que
  corresponde a su año, y **cuadra con el mayor** (RQ-001).
- **Rechazar** si viene agrupado por cliente (sin factura), sin fecha de vencimiento, con filas de total
  o con un corte distinto al del año pedido.
- Para que la historia se pueda medir, **el número de factura debe escribirse igual en los tres años**. Si
  no coincide, la herramienta intenta emparejar por cliente y fechas, y avisa cuánto no pudo localizar.

---

## E · Procesamiento

### E.1 · Parámetros (editables y documentados)

| Parámetro | Por defecto | Sustento |
|---|---|---|
| Tasa efectiva para descontar | 0 % | 11.13 y 11.25: cartera de corto plazo sin interés |
| Plazo esperado de cobro | 12 meses | Juicio del auditor, por cliente si hace falta |
| Umbral de mora grave (evaluación individual) | 361 días | 11.24 |
| Umbral de saldo significativo | 0 (desactivado) | 11.24 |
| Límite anual deducible | 1 % | LRTI Art. 10 num. 11 |
| Límite acumulado | 10 % | LRTI Art. 10 num. 11 |
| Tasa de impuesto | 25 % | Tarifa del contribuyente |

### E.2 · Qué se calcula, en orden

1. **Días de mora** de cada factura al corte de su año y **tramo**: corriente, 1–30, 31–60, 61–90,
   91–180, 181–360, 361–730, más de 730 (los dos últimos son graves).
2. **Evidencia histórica.** Por cada par de años (año 1 → año 2; año 2 → año 3), una factura que sigue viva
   al año siguiente **no se recuperó** en la parte que persiste (mínimo entre ambos saldos). Por tramo:
   tasa de no recuperación = saldo que persiste ÷ saldo inicial del tramo. Una ventana solo se usa si logra
   emparejar una parte razonable de los documentos (2 % o más).
3. **Tasa aplicada por tramo:** la observada, en todos los tramos. Si no hay historia: en los tramos graves,
   100 % cuando hay saldos de más de 730 días (incumplimiento sostenido); en el corriente, 0 %; en los demás,
   **no medible** (la fija el auditor en «Parámetros de la prueba», con su evidencia de gestión de cobro).
4. **Pérdida por factura** (11.25): saldo − valor presente de (saldo × (1 − tasa)).
5. **Por cliente:** tasa ponderada por sus tramos, evaluación individual (11.24) con ajustes del auditor.
6. **Movimiento por factura** (11.26): provisión inicial − reversión − bajas + provisión del año = saldo
   final, conciliado con el mayor (RQ-005). Las facturas de la provisión inicial que ya no están en la
   cartera y cuyo cliente tampoco tiene saldo se presumen **dadas de baja**; si el cliente sigue activo,
   quedan **pendientes** para el juicio del auditor.
7. **Fiscal:** límite anual, límite acumulado, deducible y no deducible del ejercicio.
8. **Impuesto diferido:** diferencia temporaria acumulada × tasa; movimiento del año.
9. **Asientos:** gasto por deterioro, reversiones, castigos y activo por impuesto diferido.

### E.3 · Resultado principal y problemas que debe mostrar

- **Resultado principal:** ajuste = pérdida recalculada − provisión registrada al cierre.
- **Problemas:** tramos no medibles; baja cobertura de emparejamiento entre años; clientes en mora grave
  sin evaluación individual; diferencia del movimiento con el mayor; provisión inicial pendiente de
  resolver; exceso sobre los límites fiscales.

### E.4 · Cédulas

Las 12 cédulas del papel de trabajo más las propias de la prueba: evidencia histórica, matriz de
deterioro, por cliente, movimiento por cliente, fiscal, impuestos diferidos y asientos.

### E.5 · Cómo entra al Command Center

El motor declarativo no puede hacer los pasos 2, 5, 6, 7 y 8 (comparar años, totales por cliente, límites
sobre totales). La ficha declarará un **procesador especializado** en Python, `perdidas_incurridas_s11`,
con esta lógica. Todo lo demás es el proceso normal:
- encargo;
- base técnica con los párrafos de arriba y las NIA;
- requerimientos con sus **modelos** y botones de subida;
- **Procesar**;
- resultado y problemas;
- revisión y aprobación.

### E.6 · Ejemplo numérico de control

Anexo del año 2 con la factura F-1 (cliente A, 91–180 días, saldo 1.000) y F-2 (cliente B, corriente,
saldo 500). En el año 3, F-1 sigue con 400 y F-2 ya no aparece.
- Tramo 91–180: no recuperación = 400 ÷ 1.000 = **40 %**.
- Tramo corriente: F-2 no persiste = **0 %** (la Sección 11 lo exige de todas formas).
- Si en el año 3 hay una factura de 2.000 en el tramo 91–180, con tasa efectiva 0 %, su pérdida es
  2.000 − 2.000 × 0,60 = **800,00**.

### E.7 · Verificación (2026-09-21)

- Procesador: `backend/app/aud/niif/procesadores/perdidas_incurridas_s11.py`; pruebas
  `tests/test_aud_procesador_pi.py` (ejemplo E.6 → 800,00) y `tests/test_aud_ciclo_procesador_pi.py` (ciclo HTTP
  completo, del modelo Excel al papel aprobado).
- Prueba local en pantalla con 4 facturas de 3 clientes y 2 años: pérdida 1.950,00 (400 + 800 + 0 + 750),
  provisión del mayor 300,00, ajuste 1.650,00, gasto deducible 15,00 (1 % de 1.500 corriente), no deducible
  1.635,00, diferido al cierre 408,75. Cada cifra se recalculó a mano.
- Papel aprobado que arma el servidor: 17 hojas (carátula, programa, base técnica, 12 cédulas, conclusión y
  bitácora), sin celdas de texto que Excel tome por fórmula.
