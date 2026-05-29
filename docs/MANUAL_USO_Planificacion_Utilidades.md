# Manual de uso — Planificación del Impuesto sobre Utilidades No Distribuidas

**Para:** consultores tributarios / equipo de auditoría
**Dónde está:** AuditBrain → Command Center → módulo **TAX** → pestaña **Análisis**
→ "Planificación Impuesto Utilidades Retenidas"
**Qué es:** un tablero interactivo para calcular y planificar el *pago a cuenta sobre
utilidades no distribuidas* (Ecuador), simular escenarios y entregar un informe y un
Excel al cliente.
**Versión:** 1.0 · 2026-05-29

---

## 0. Antes de empezar (en 1 minuto)

- Trabajas sobre un **proyecto** activo (el cliente sobre el que estás analizando).
- La herramienta tiene **una sola fuente de datos**: los estados financieros. Todo lo
  demás (índices, impuesto, proyecciones) **se calcula solo** y se actualiza en vivo
  cuando cambias un dato.
- Las **celdas azules** son las únicas que se editan a mano. Lo que no es azul es un
  resultado calculado: no lo toques.
- Puedes cargar datos de tres formas: **a mano**, desde el **Formulario 101 (PDF)** o
  desde una **plantilla de balance resumido (Excel)**.
- Al final obtienes un **informe gerencial** (para imprimir/PDF) y un **Excel con
  fórmulas** que sigue calculando fuera de la plataforma.

> ⚠️ **Importante:** las tarifas y tasas vienen como valores de referencia y **deben
> validarse** con la normativa vigente antes de entregar cifras al cliente. La
> herramienta es de planificación, no reemplaza la asesoría legal ni la declaración
> oficial.

---

## 1. La barra superior (controles globales)

En la parte de arriba siempre tienes:

| Control | Para qué sirve |
|---|---|
| **Nombre de empresa** | Caja de texto editable; identifica el análisis. |
| **Escenario** | Botones: **Sin acción · Capitalización · Distribución · Mixto**. Cambian automáticamente las palancas y recalculan todo. |
| **⬆ Formulario 101** | Abre el panel para subir el PDF del F-101 del SRI. |
| **⬆ Balance resumido** | Abre el panel para descargar la plantilla y/o subir el balance en Excel. |
| **⬇ Excel** | Descarga el análisis completo en Excel con fórmulas nativas. |
| **🖨 PDF** | Imprime / guarda el informe en PDF. |
| **↺ Ejemplo** | Restaura los datos de ejemplo (empresa demo). Úsalo para practicar. |

Debajo está la **barra de navegación** con las 10 secciones del análisis (puntos 2 a 11
de este manual). Haz clic en cada una para moverte.

---

## 2. Datos del cliente

Es la primera sección. Aquí defines la cabecera del informe. Campos:

| Campo | Qué poner |
|---|---|
| **Nombre / razón social** | Nombre legal de la compañía. |
| **RUC** | RUC del contribuyente (13 dígitos). |
| **Representante legal** | A quién se dirige el informe. |
| **Fecha de corte** | Fecha de corte del análisis (normalmente 31 de julio). |
| **Fecha del análisis** | Fecha del cálculo. Si la dejas vacía, se usa la fecha de hoy. |

Estos datos aparecen en la portada del **Informe gerencial** y en el saludo al
representante legal.

---

## 3. Base legal y normativa

Sección informativa (solo lectura). Resume el marco del régimen de utilidades no
distribuidas: naturaleza del anticipo, base de cálculo, tarifa, crédito y devolución.
Léela para tener el contexto y para explicárselo al cliente. **No se edita.**

---

## 4. Estados financieros (la fuente de datos)

Es el corazón de la herramienta. Tiene dos bloques: **ESF** (situación financiera /
balance) y **ER** (resultados), con tres columnas de año (por defecto 2023, 2024, 2025).

**Cómo se usa:**

- Edita solo las **celdas azules** (efectivo, cuentas por cobrar, inventario, ventas,
  costo, gastos, etc.).
- Las líneas en **negrita** (totales y subtotales: Total activo corriente, Total
  activo, Utilidad bruta, EBIT, Resultado neto, etc.) **se calculan solas**.
- Al cambiar cualquier celda, todos los índices, el impuesto y las proyecciones se
  actualizan al instante.

**Para cargar los datos automáticamente** (en vez de a mano):

### 4.1 Desde el Formulario 101 (PDF del SRI)
1. Clic en **⬆ Formulario 101** (barra superior).
2. Selecciona el PDF y pulsa **Procesar y cargar**.
3. El sistema lee los casilleros, detecta el **año** y llena la columna correspondiente.
4. Verás un mensaje de éxito y, si aplica, **avisos**. Como la numeración de casilleros
   del F-101 varía por versión, **revisa las celdas azules** antes de confiar en las
   cifras.

### 4.2 Desde un balance resumido (Excel)
1. Clic en **⬆ Balance resumido**.
2. Pulsa **⬇ Descargar plantilla en blanco**.
3. Llena la plantilla (columnas por año) y guárdala.
4. Vuelve a la herramienta, selecciónala y pulsa **Procesar y cargar**.

> El F-101 trae **un solo año**, así que solo se llena esa columna; las demás conservan
> lo que ya tuvieras. El balance resumido puede traer los tres años.

---

## 5. Índices financieros

Muestra automáticamente, por año, los principales ratios: **liquidez, prueba ácida,
capital de trabajo, endeudamiento, apalancamiento, márgenes (bruto/operativo/neto),
ROE, ROA, rotación de activos y días de cartera/inventario/proveedores**.

Sirve para diagnosticar la salud financiera y respaldar las recomendaciones. No se
edita; cambia solo si cambias los estados financieros.

---

## 6. Cálculo del impuesto

Aquí ocurre la planificación. Por cada año proyectado (2026–2028) defines las
**palancas** (celdas azules):

| Palanca | Qué significa |
|---|---|
| **Crecimiento (%)** | Cuánto crecen las ventas respecto al año anterior. |
| **Dividendos** | Monto que se distribuye (reduce la base). |
| **Capitalización** | Monto que se capitaliza (reduce la base). |

Y revisas el resultado: **base imponible, tarifa aplicada, pago a cuenta** y cómo se
distribuye el crédito.

También hay **parámetros editables** (validar antes de usar):

| Parámetro | Por defecto |
|---|---|
| Costo / ventas (%) | 60,6 % |
| Gastos operativos / ventas (%) | 34,6 % |
| Tasa de Impuesto a la Renta (%) | 25 % |
| Retención de dividendos (%) | 10 % |

> **Tip:** en vez de configurar las palancas manualmente, usa los **botones de
> escenario** de la barra superior (Sin acción / Capitalización / Distribución /
> Mixto) y luego ajusta lo que necesites.

---

## 7. Retenciones de dividendos

Muestra la retención del impuesto único a los dividendos según el monto distribuido
en cada año (usa el % de retención de los parámetros). Es el **primer eslabón** del
crédito: el pago a cuenta se compensa primero contra esta retención.

---

## 8. Crédito vs. Renta

Explica la **cascada del crédito** del pago a cuenta:
1. Se compensa contra la **retención de dividendos**.
2. El remanente se compensa contra el **Impuesto a la Renta causado**.
3. Lo que sobre se solicita en **devolución**.

Aquí ves cuánto crédito se usa, cuánto queda por devolver y, sobre todo, cuánto queda
**en riesgo de costo muerto** (pago que podría no recuperarse si no hay distribución
ni capitalización).

---

## 9. Estados proyectados

Presenta el estado de resultados y el arrastre patrimonial proyectados a tres años,
en función del crecimiento y de las decisiones de dividendos/capitalización. Permite
ver el efecto de la estrategia sobre patrimonio y resultados acumulados.

---

## 10. Dashboards

Gráficos (barras/líneas) que resumen visualmente la evolución de los indicadores, el
pago a cuenta por escenario y la composición del crédito. Útil para la presentación
al cliente.

---

## 11. Informe gerencial

Vista de informe lista para presentar/imprimir:
- **Portada** con razón social, RUC, representante legal, horizonte y fechas.
- **Saludo** dirigido al representante legal.
- Conclusiones y recomendaciones del análisis.

Desde aquí usa **🖨 PDF** (barra superior) para guardarlo o imprimirlo.

---

## 12. Cómo entregar el resultado

| Quieres… | Haz esto |
|---|---|
| Un PDF del informe | Sección **Informe gerencial** → botón **🖨 PDF**. |
| Un Excel que el cliente pueda seguir editando | Botón **⬇ Excel**. Trae hojas Resumen, Datos, ESF, ER, Índices y Proyección; las celdas azules siguen siendo editables y **todo recalcula dentro de Excel**. |
| Estandarizar la captura de datos | **⬆ Balance resumido** → **Descargar plantilla en blanco**. |

---

## 13. Flujo recomendado (resumen)

1. **Datos del cliente** → completa la cabecera.
2. **Estados financieros** → carga por F-101, por plantilla o a mano. Revisa celdas azules.
3. **Índices** → diagnóstico rápido.
4. Elige un **escenario** y ajusta **palancas** en *Cálculo del impuesto*.
5. Revisa **Retenciones**, **Crédito vs. Renta** y **Estados proyectados**.
6. Mira los **Dashboards**.
7. Genera el **Informe gerencial** (PDF) y/o **⬇ Excel**.

---

## 14. Preguntas frecuentes

- **¿Por qué no puedo escribir en una celda?** Solo las azules son editables; el resto
  son resultados calculados.
- **¿Cambié un número y no veo el efecto?** Sí lo ves: todo recalcula al instante. Si no,
  asegúrate de haber editado una celda azul.
- **Subí el F-101 y faltan datos.** El F-101 trae un solo año y algunos casilleros
  pueden no detectarse según la versión del formulario. Completa o ajusta a mano las
  celdas azules; revisa los avisos que muestra el panel de carga.
- **¿Las tarifas son oficiales?** Son valores de referencia **editables**. Valídalos
  antes de presentar cifras.
- **¿El Excel descargado calcula solo?** Sí. Las fórmulas son nativas; al editar las
  celdas azules en Excel, los totales, índices, la tarifa y las proyecciones se
  recalculan.
- **Quiero empezar de cero / con otra empresa.** Sobrescribe los estados financieros o
  usa los botones de carga. **↺ Ejemplo** restaura la empresa demo.

---

## 15. Errores comunes y qué revisar antes de entregar

- [ ] ¿Completaste **Datos del cliente** (razón social, RUC, representante legal, fechas)?
- [ ] ¿Revisaste las **celdas azules** tras una carga automática (F-101 / Excel)?
- [ ] ¿Validaste **tarifa, tasa de IR y retención de dividendos** con la normativa vigente?
- [ ] ¿El **año** que cargó el F-101 es el correcto?
- [ ] ¿Las **palancas** (crecimiento, dividendos, capitalización) reflejan la estrategia real?
- [ ] ¿Revisaste el monto **en riesgo de costo muerto** antes de recomendar "sin acción"?
- [ ] ¿Atendiste los **avisos** del panel de ingesta?

> Nota para el caso de empresas con inventario sobredimensionado: evitar recomendar la
> capitalización vía inventarios; preferir activos productivos/empleo.

---

## 16. Glosario

| Término | Significado |
|---|---|
| Pago a cuenta | Anticipo recuperable sobre utilidades no distribuidas. |
| Base imponible | Utilidades acumuladas − dividendos − capitalización. |
| Tarifa por tramo | Porcentaje único que se aplica a toda la base según su tamaño. |
| Crédito en cascada | Compensación del pago: retención de dividendos → IR → devolución. |
| Costo muerto | Pago a cuenta que queda en riesgo de no recuperarse. |
| Celdas azules | Inputs editables; única fuente de datos. |
| ESF / ER | Estado de Situación Financiera / Estado de Resultados. |
| F-101 | Formulario 101 del SRI (Impuesto a la Renta Sociedades). |
