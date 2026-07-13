# Motor de Balances — Homologación multi-período (Fase 1)

- **Fecha:** 2026-07-12
- **Estado:** Propuesta para revisión del usuario
- **Alcance:** Fase 1 = **solo Motor de balances**. *Asientos* y *cubos de
  información* quedan para Fases 2 y 3 (fuera de este spec).
- **Repo:** `auditbrain-python-runner` (producción).
- **Decisiones fijadas por el usuario:**
  1. **Arquitectura:** extender el stack de homologación del portal Flujo
     (`client_portal/flujo/parser.py`, `motor.homologar_balanza`,
     `BalanzasEditor.jsx`), ya validado, en vez de reescribir sobre los parsers
     tax/FIN.
  2. **Alcance:** homologación multi-período + vista editable unificada + arreglo
     nombre del cliente / Super Cías visible + cuadre sin forzar.

---

## 1. Problema

El proceso actual de ingesta de balances (FIN `balance_interno.py::_route_balance`)
**fuerza el cuadre**: cuando no reconoce una cuenta por keywords, mete el residual
en una cuenta "Otras" para que Activo = Pasivo + Patrimonio. Esto distorsiona los
estados y el cliente no confía en las cifras.

La verificación empírica sobre el cliente real **SIGMAN** confirmó los síntomas:
- El balance del cliente trae **códigos internos propios** (`1.01.01.02.001`) que
  **no coinciden** con la estructura Super Cías; requieren homologación con criterio.
- Un mapeo hecho para un solo período (2025) **cubre solo ~50%** de las cuentas de
  los demás períodos (2023/2024/may-2026), porque las cuentas en cero ese año no
  entran. Por eso SIGMAN mantiene dos hojas de mapeo separadas.

## 2. Objetivo

Homologar cualquier balance de cliente contra un **catálogo oficial** (Super Cías
↔ SRI ↔ nombre NIIF), **sin heurísticas de keywords ni cuadres forzados**: los
estados cuadran porque se **reagrupan saldos reales** por su código Super Cías,
no porque se rellene un residual.

## 3. Fuentes de verdad (archivos del usuario)

1. **`PLAN DE CUENTAS SRI-SUPER.xlsx`** — mapa canónico oficial. 874 cuentas Super
   Cías, 738 con código SRI; jerárquico por longitud de código (1/2/3/5/7/9/11);
   secciones ESF, ERI y ORI (8xxxx). Cumple **doble rol**: (a) diccionario de
   traducción de códigos, (b) **picklist** para homologar cuentas huérfanas.
   - *Observación:* 84 códigos Super mapean a **varios** SRI (1:N, ej. ventas por
     tarifa IVA). La librería no asume 1:1.
   - *Pendiente de confirmar con el usuario:* la columna "DEPRECIACIO" (col E)
     tiene 63 filas no vacías con contenido que parece nombre alterno, no
     depreciación. No se usa hasta aclarar.
2. **`Mapeo Año Actual`** (hoja del modelo de flujo SIGMAN) — instancia por cliente:
   `Cod.Cuenta.Contable | Descripción | CÓDIGO SUPER CIAS | Código SRI | Saldo`.
   Es el "balance mapeado SRI-Super" que el usuario sube. La homologación ahí es
   **manual** (valores, no fórmulas).
3. **`BALANCE SIGMAN.xlsx` / `RESULTADOS SIGMAN.xlsx`** — balances crudos
   multi-período del cliente (`Código | Cuenta | período1 | período2 | …`), **sin**
   columnas Super Cías/SRI. Son "los otros períodos a comparar".

## 4. Flujo funcional (lo que hará el motor)

1. **Ingesta.** El usuario sube:
   - un **"balance mapeado SRI-Super"** (hoja tipo `Mapeo Año Actual`) como base de
     homologación, y/o
   - balances crudos multi-período (ESF + ERI).
   **Carga MULTIARCHIVO (regla).** El usuario puede NO tener los años unificados en
   una sola hoja: puede subir **varios archivos**, uno por año (p.ej. `BALANCE 2023`,
   `BALANCE 2024`, `BALANCE 2025` + `RESULTADOS 2023`, `RESULTADOS 2024`,
   `RESULTADOS 2025`). La herramienta debe:
   1. **Reconocer y clasificar cada archivo** como **ESF** o **ERI** — por el dígito
      dominante del código de cuenta (1/2/3 = balance, 4/5/6 = resultados), con el
      nombre del archivo como pista secundaria; **nunca** solo por el nombre.
   2. **Detectar el año/período** de cada archivo (del encabezado de fecha/columna
      si existe; si no, del nombre del archivo; regex `20\d{2}`). Un archivo puede
      traer un año o varios (multi-columna) — ambos casos se soportan.
   3. **Unificar todos los ESF en UNA sola hoja** y todos los ERI en **OTRA**:
      unión de cuentas por `Cod.Cuenta.Contable`, **una columna por año** ordenada
      cronológicamente (por identidad año-mes). Una cuenta presente en unos años y
      no en otros aparece igual, con 0/vacío en los faltantes (la unión multiarchivo
      **aumenta la cobertura** y evita perder cuentas).
   4. **Año duplicado:** si dos archivos declaran el **mismo año** para el mismo
      estado (ej. dos `BALANCE 2024`), la herramienta **avisa del duplicado** y deja
      que el usuario elija cuál conservar — **no suma ni reemplaza en silencio**
      (evita doble conteo).
   Tras consolidar, el flujo sigue idéntico (normalización de columnas → cuadre →
   homologación) sobre esas dos hojas.
   **Normalización de formato (al ingerir):** si el balance viene en formato crudo
   (`Código | Cuenta | período1..N`) **sin** las columnas de homologación, el
   sistema **inserta dos columnas** después de "Cuenta" — `CODIFO SUPER CIAS`
   (encabezado verde) y `Códigos SRI` (encabezado azul) — y corre los períodos a
   la derecha. Es **idempotente**: si el archivo ya trae esas columnas, no las
   duplica. Así todo balance queda con la estructura homologable estándar
   (`Código | Cuenta | Super Cías | SRI | períodos…`).
   **Dos páginas separadas:** el Motor de balances tiene una página
   **"Balances homologados" (ESF)** y otra **"Estados de resultados homologado"
   (ERI)**. Cada una procesa su propio archivo y su propio flujo.
2. **Verificación de cuadre (gate PREVIO a homologar).** Lo **primero** en cada
   página, al subir el archivo, es validar que **esté cuadrado** — como se muestra
   al subir los archivos. Banner ✓/⚠ por período arriba de la tabla. Hay
   cuadratura en **ambos** estados:
   - **ESF:** Activo = Pasivo + Patrimonio por período (totales declarados del
     cliente). *(SIGMAN: cuadra en los 4 períodos.)*
   - **ERI:** el resultado del período (Ingresos − Costos − Gastos) reconcilia con
     el total declarado del ER, y **amarra** con la "Ganancia/Pérdida neta del
     período" del patrimonio en el ESF.
   Si algún período no cuadra, se **avisa** (nunca se fuerza) antes de continuar.
3. **Unión.** Se unen todos los períodos en **una fila por cuenta del cliente**
   (match por `Cod.Cuenta.Contable`), con un saldo por período. Una cuenta que
   existe solo en un período aparece igual, con los demás saldos vacíos.
4. **Propagación.** La homologación (Super Cías/SRI) del balance mapeado se aplica
   a **todos los períodos** por código de cuenta. Se homologa **una vez**, sirve
   para todos.
5. **Homologar huérfanas (interactivo, desplegables enlazados).** La página
   despliega el **balance completo con las dos columnas**. Las cuentas sin Super
   Cías quedan **resaltadas (ámbar) y editables**. Cada una de las dos columnas
   tiene su **flecha/desplegable** (picklist con búsqueda del **PLAN DE CUENTAS**,
   mostrando código + nombre):
   - **Enlace bidireccional:** al elegir en **cualquiera** de las dos, la de al
     lado **se codifica sola** usando el mapeo Super↔SRI del plan (ej. elegir
     `1010101 Caja` completa `311`; y al revés cuando es 1:1).
   - **Caso 1:N** (84 códigos Super con varios SRI, ej. ventas por tarifa IVA): si
     un Super Cías tiene varios SRI posibles, el SRI **queda abierto** para que el
     auditor elija — no se adivina.
   - Al quedar ambos códigos, la fila deja de ser huérfana (verde) y **recalcula
     solo**.
   Reutiliza/extiende el mecanismo `<datalist>` ya existente en `BalanzasEditor`
   (`SUPER_LIST_ID`/`SRI_LIST_ID`), agregando el autocompletado cruzado.
   Opcional futuro (no Fase 1): sugerencia por prefijo/hermano (`1.01.01.01.002`
   hereda de `1.01.01.01.006`).
6. **Agrupación y cuadre (post-homologación).** Se agrupa por Super Cías/SRI con
   `motor.homologar_balanza` + `totales_por_codigo`. El cuadre A = P + Patrimonio
   se **reporta** (banner ✓/⚠ por período con el monto de descuadre); **nunca se
   fuerza** metiendo residuales. (Distinto del gate del paso 2, que valida el
   archivo crudo del cliente antes de tocar nada.)
7. **Traslado al formato Superintendencia de Compañías (hand-off a FLUJO_EFECTIVO).**
   Una vez homologados ESF y ERI, su salida `{cuenta, super_cias, sri, saldos[]}`
   **es exactamente el contrato de balanza** que la herramienta `FLUJO_EFECTIVO`
   (`tool_registry.py`, slots `balanza_anterior`/`balanza_actual`, contrato
   `{cuenta, super_cias, sri, saldo}`) ya consume para generar el **formato oficial
   Super Cías** (`generador.generar_excel`): Situación Financiera, Resultados
   Integral, Evolución del Patrimonio, **Flujo de Efectivo 95xx**, Movimiento no
   Efectivo, Formulario 101, Notas, Indicadores, Balance resumido — validado 71/71.
   - El Motor **automatiza la homologación** que hoy el cliente hace a mano antes de
     subir la balanza al Flujo.
   - **REGLA: el balance Superintendencia lleva TODOS los períodos homologados.**
     La **Situación Financiera (ESF)** y el **Resultados Integral (ERI)** en formato
     Super Cías se presentan con **N columnas comparativas** (una por cada período
     que el usuario pidió homologar: 2023, 2024, 2025, may-2026…), agrupadas por
     Código Super Cías. **No** se limita a un período ni se muestra la balanza fuente
     cruda. *(Nota de implementación: hoy `generador._hoja_estructura` es de 2
     columnas anterior/actual; hay que extenderlo a N períodos.)*
   - **Solo el Flujo de Efectivo 95xx y el Formulario 101 son de 2 períodos / 1 año**
     (restricción de la norma: el flujo exige dos puntos de balance y el F-101 es
     anual). Se generan para el par de años a presentar, **sin** recortar la vista
     comparativa multi-período de los estados.
   - **No se reconstruye** el formato Super Cías: se **reutiliza/extiende** el
     existente (comparten `motor.homologar_balanza`). Confirma la decisión de
     extender el stack Flujo.
8. **Persistencia = el archivo.** El usuario descarga el **balance homologado
   completo** (todos los períodos + Super Cías/SRI). La próxima vez lo re-sube y
   solo homologa cuentas nuevas. **Sin BD de mapeos** (decisión del usuario).

## 5. Arquitectura

Se **reutiliza** el stack de homologación de `client_portal/flujo`, generalizándolo
de 2 períodos (anterior/actual) a **N períodos**, y se expone una **herramienta
nueva en AUD → Análisis** ("Motor de balances, asientos y cubos de información";
Fase 1 solo balances).

### 5.0. Principio: Motor de balances = SERVICIO COMPARTIDO (no duplicar)

**REGLA DE ARQUITECTURA.** El Motor de balances es un **servicio central único**,
NO se copia ni se reimplementa en cada sección. Una sola implementación del
backend de homologación (consolidación multiarchivo, unión de períodos,
propagación, homologación contra el plan, agrupación por Super Cías, cuadre) que
**cualquier herramienta consume** por API/import:

- **FIN · Análisis Financiero Empresarial** (dashboard CFO).
- **FIN · Presupuesto y forecast**.
- **AUD** (herramienta "Motor de balances" y pruebas por ciclo).
- **Portal cliente · Flujo de Efectivo** (formato Superintendencia).

El servicio vive en **un módulo** (`client_portal/flujo/` — `motor.py` +
`motor_balances.py` para N períodos) y se expone por endpoints reutilizables; los
componentes de UI (grilla editable de homologación, banner de cuadre, picklist del
plan) se comparten, no se clonan por sección.

**Consola/catálogo de herramientas.** Habrá un **catálogo/consola** que liste
todas las herramientas que se van creando y marque **cuáles consumen el Motor de
balances** (metadato en el registro de herramientas). Objetivo: visibilidad y evitar
que alguien reimplemente la homologación en una sección nueva. *(La consola en sí es
un entregable pequeño de reporting/registro; el núcleo Fase 1 es el servicio
compartido y sus consumidores.)*

Dos entregables:

### 5a. Corrección + generalización del editor existente (portal cliente)
Arregla la vista actual `BalanzasEditor.jsx` (la de la captura) que hoy:
- **no muestra el nombre de la cuenta del cliente** (el parser lo descarta), y
- **no deja ver bien el código Super Cías** (se corta en pantalla).

### 5b. Nueva herramienta AUD "Motor de balances" (frontend staff)
Nuevo tool en el catálogo AUD (`frontend/src/aud/catalog.js`) que reutiliza el
backend de homologación y presenta la vista editable **multi-período**. Mantiene la
**línea gráfica del portal** (reutiliza `PortalShell` + clases `pc-*`/`fx-*` del
Flujo de Efectivo; no inventa estilos nuevos).

**Secciones (tarjetas numeradas, estilo Flujo):**
1. **Balances homologados (ESF)** — workspace editable (homologación + huérfanas).
2. **Resultados homologado (ERI)** — workspace editable.
3. **Traslado Superintendencia** — hand-off que genera el formato oficial.
4. **Situación Financiera Superintendencia** — ESF oficial por Código Super Cías,
   **N períodos comparativos**.
5. **Resultados Integral Superintendencia** — ERI oficial (cascada), **N períodos**.

Distinción: 1–2 son el **workspace de homologación** (editable, huérfanas, cuadre);
4–5 son los **estados finales en formato oficial Superintendencia** (solo lectura,
generados desde lo homologado). El Flujo 95xx y el F-101 siguen siendo de 2 períodos.

## 6. Cambios por componente

### Backend (`backend/app/client_portal/flujo/` + nuevo router AUD)

- **`parser.py`**
  - Capturar el **nombre de la cuenta del cliente**: agregar la clave `nombre`
    a `_CLAVES` (`"descripcion", "nombre", "detalle cuenta"`) y al dict de salida
    de `_leer_filas`. Fila pasa de `{cuenta, super_cias, sri, saldo}` a
    `{cuenta, nombre, super_cias, sri, saldo}`.
  - **Nuevo `parse_balanza_multiperiodo(bytes)`**: lee un balance crudo
    `Código | Cuenta | período1..N` (encabezados de fecha/año como en
    `balance_interno::_period_label`) y devuelve
    `{"periodos": [labels], "filas": [{cuenta, nombre, saldos:[…]}]}`. Reutiliza
    `_parse_saldo` (formato regional) y la tipificación de períodos.
  - Compatibilidad: `parse_balanza` sigue existiendo (2 períodos, portal Flujo).

- **`previews.py`** — `_fila_map` incluye `nombre`; cols MAP pasan a
  `["Cuenta", "Nombre", "Super Cías", "SRI", "Saldo"]` (y su variante N-período).

- **`processor.recalcular_desde_balanzas`** — conservar `nombre` en el round-trip
  (viaja en cada ficha; no afecta el cálculo, solo se preserva para mostrar).

- **Nuevo módulo `motor_balances.py`** (o extensión de `motor.py`): homologación
  **multi-período** — unión por cuenta, propagación del código a todos los
  períodos, y `totales_por_codigo` aplicado por período. No duplica la lógica de
  agrupación (reusa `homologar_balanza`), solo la envuelve para N columnas.

- **Nuevo endpoint AUD** (`backend/app/aud/…/router.py`): `POST …/motor-balances/homologar`
  (recibe balances subidos → devuelve la tabla unificada + catálogo del plan) y
  `POST …/motor-balances/recalcular` (recibe la tabla editada → devuelve estados
  agrupados + cuadre por período). Gating `require_staff` (política de firma).

- **Catálogo del plan** — cargar `PLAN DE CUENTAS SRI-SUPER.xlsx` como datos del
  repo (CSV/JSON en `flujo/data/`, junto a `plan_cuentas_super_sri.csv`) y servirlo
  como picklist (código + nombre Super Cías + código SRI + nombre SRI).

### Frontend

- **`frontend-client/src/flujo/BalanzasEditor.jsx`** (arreglo 5a):
  - Columna "Cuenta contable" muestra **código + nombre del cliente**.
  - Reordenar/anclar columnas para que **Super Cías (código + nombre NIIF)** quede
    visible sin cortarse. Fila = una cuenta = unión anterior+actual, homologación
    única que aplica a ambos.

- **`frontend/src/aud/` (herramienta nueva 5b):**
  - Entrada en `catalog.js` (nueva categoría/tool "Motor de balances").
  - Componente de ingesta (subir mapeado + balances crudos) y **tabla editable
    N-período** (generalización del patrón de `BalanzasEditor`: columnas de saldo
    dinámicas por período), con resaltado de cuentas huérfanas y picklist del plan.
  - Banner de cuadre por período (✓/⚠), sin forzar.

## 7. Modelo de datos

Ficha de cuenta (unificada, N períodos):
```
{
  "cuenta":     "1.01.01.02.001",         # código interno del cliente
  "nombre":     "Produbanco Quito 020...", # descripción del cliente (NUEVO)
  "super_cias": "1010103",                 # homologado (editable)
  "sri":        "311",                     # homologado (editable)
  "saldos":     { "2023-12-31": 341440.43, "2024-12-31": 144362.32, ... }
}
```
La ficha de 2 períodos del portal Flujo (`{cuenta, nombre, super_cias, sri, saldo}`)
es el caso particular N=2 (anterior/actual).

## 8. Verificación (obligatoria antes de decir "listo" — REGLA SUPREMA)

Caso de referencia: **SIGMAN** (los archivos reales de este spec).
1. **Conteo:** las 226 cuentas hoja del BALANCE y 92 del RESULTADOS aparecen en la
   tabla unificada (ninguna se pierde).
2. **Cobertura:** tras propagar el `Mapeo Año Actual`, las huérfanas reportadas
   coinciden con las 112 (ESF) / 18 (ERI) medidas; ninguna se homologa sola de
   forma silenciosa.
3. **Cuadre:** el banner refleja los **descuadres reales de la fuente** por período
   (medidos al implementar, directo sobre `BALANCE SIGMAN.xlsx` / `RESULTADOS
   SIGMAN.xlsx` — no sobre el Papel de Trabajo, que trae otras cifras), **sin**
   ocultarlos con residuales. En la exploración preliminar del Papel se vieron
   descuadres materiales en 2024 y 2025; hay que recalcularlos contra el balance
   crudo antes de fijar los valores esperados del test.
4. **Nombre del cliente:** cada fila muestra la descripción real (ej. "Produbanco
   Quito").
5. **Tests** (`tests/test_flujo_*`): agregar cobertura de parser con `nombre`,
   multi-período, y no-regresión del flujo 2-período existente. `pytest` en verde.

## 9. Fuera de alcance (Fase 1)

- **Asientos** (ajustes/reclasificaciones, "información extracontable"): Fase 2.
- **Cubos de información** (análisis multidimensional): Fase 3.
- Sugerencia automática de homologación por prefijo/hermano o IA.
- Memoria/BD de mapeos por cliente (decisión: el archivo homologado es la
  persistencia).
- PDF/Word de balance (solo Excel).

## 10. Riesgos y decisiones abiertas

- **N períodos rompe supuestos 2-período** del portal Flujo (flujo de efectivo y
  F-101 son intrínsecamente anterior/actual). Mitigación: el Motor de balances es
  una **herramienta nueva** que reutiliza las primitivas de homologación; **no**
  altera el tool `FLUJO_EFECTIVO` (que sigue 2-período). El arreglo 5a al editor
  del portal es compatible hacia atrás.
- **Reuso de `BalanzasEditor` entre dos frontends** (portal cliente vs staff):
  en Fase 1 se **arregla** el del portal y se **crea** el de AUD siguiendo el mismo
  patrón (no se comparte el componente físico para no acoplar los dos frontends).
  Si la duplicación pesa, se extrae a un paquete común en una iteración futura.
- **Columna "DEPRECIACIO"** del plan: pendiente de aclarar con el usuario antes de
  usarla.
- **Mapeo 1:N Super→SRI:** al homologar, un código Super puede sugerir varios SRI;
  el usuario elige. La agrupación de estados usa el Super Cías (que sí es único por
  cuenta).
