# Workspace estilo ICT — Plan 4 de 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Devolver la herramienta a un estado usable, con la pantalla de Obligaciones Fiscales rehecha con el lenguaje visual del workspace ICT y la pantalla de revisión de la clasificación.

**Architecture:** Se portan las clases `pc-*` del portal de clientes al Command Center (son dos apps npm independientes, sin build compartido) y se reemplaza el formulario plano por un panel maestro con chips de documentos, barra de progreso y grid de tiles.

**Tech Stack:** React 18, Vite, CSS plano con las variables del tema ya existentes.

**Spec:** `docs/superpowers/specs/2026-08-04-mayor-general-impuestos-design.md`, sección "Frontend".
**Depende de:** Plan 2 (la API de dos fases).

---

## Punto de partida y por qué urge

La API cambió en el Plan 2: `POST /jobs` ya no acepta archivos, hay endpoints por slot, y el ciclo pasa por `procesar → revisión → aprobar`. El componente actual (`frontend/src/aud/ObligacionesFiscalesTool.jsx`) sigue enviando todo en un POST, así que **la herramienta está rota en pantalla**. Hasta terminar este plan, la rama no debe fusionarse a `main`.

## Verificación en este plan

El frontend de este repo **no tiene runner de tests** (revisa `frontend/package.json` para confirmarlo antes de empezar; si lo tiene, escribe tests). La verificación es entonces:

1. `cd frontend && npm run build` sin errores en cada tarea.
2. Al final, **verificación real en el navegador** con el backend local: crear un borrador, subir archivos, procesar, revisar, aprobar y descargar, comprobando cada paso en pantalla.

No des una tarea por terminada porque "compila": compilar no prueba que el flujo funcione.

## La API que hay que consumir

```
POST   /api/v1/aud/obligaciones-fiscales/jobs                 → crea en 'borrador'
PUT    /api/v1/aud/obligaciones-fiscales/jobs/{id}/slots/{s}  → multipart, campo 'archivos'
                                                                 (+ 'categoria' si slot=mayor_especifico)
DELETE /api/v1/aud/obligaciones-fiscales/jobs/{id}/slots/{s}
GET    /api/v1/aud/obligaciones-fiscales/jobs/{id}/slots      → {slot: {n_archivos, nombres}}
POST   /api/v1/aud/obligaciones-fiscales/jobs/{id}/procesar   → estado 'revision'
GET    /api/v1/aud/obligaciones-fiscales/jobs/{id}/clasificacion → {cuentas[], categorias[]}
PUT    /api/v1/aud/obligaciones-fiscales/jobs/{id}/clasificacion → {correcciones: [{codigo_cuenta, categoria}]}
POST   /api/v1/aud/obligaciones-fiscales/jobs/{id}/aprobar    → estado 'done'
GET    /api/v1/aud/obligaciones-fiscales/categorias
GET    /api/v1/aud/obligaciones-fiscales/jobs/{id}/download
```

Slots: `f104, f103, ats, mayor_general, mayor_especifico, f101`.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `frontend/src/api.js` (modificar) | Funciones de la API nueva |
| `frontend/src/aud/of/ofWorkspace.css` (nuevo) | Clases `pc-*` portadas |
| `frontend/src/aud/of/SlotChip.jsx` (nuevo) | Chip de documento con subida y borrado |
| `frontend/src/aud/of/RevisionClasificacion.jsx` (nuevo) | Tabla de cuentas con selector de categoría |
| `frontend/src/aud/of/EditarDatosModal.jsx` (nuevo) | Datos del encargo y firma auditora |
| `frontend/src/aud/of/ObligacionesFiscalesWorkspace.jsx` (nuevo) | Panel maestro |
| `frontend/src/aud/ObligacionesFiscalesTool.jsx` (reemplazar) | Pasa a ser un envoltorio del workspace |
| `frontend/src/aud/strings.js` (modificar) | Textos nuevos |

---

### Task 1: Cliente de la API nueva

**Files:** Modify `frontend/src/api.js`.

- [ ] **Step 1:** Añadir, siguiendo el estilo de las funciones existentes (`apiFetch`, `authHeaders`, `parse`):

`crearJobOF(form)`, `subirSlotOF(jobId, slot, archivos, categoria)`, `quitarSlotOF(jobId, slot)`, `estadoSlotsOF(jobId)`, `procesarOF(jobId)`, `getClasificacionOF(jobId)`, `guardarCorreccionesOF(jobId, correcciones)`, `aprobarOF(jobId)`, `listarCategoriasOF()`.

`subirSlotOF` arma un `FormData` con **todos** los archivos bajo el campo `archivos`, y agrega `categoria` solo si viene.

Conserva `getObligacionesFiscalesJob`, `listObligacionesFiscalesJobs` y `downloadObligacionesFiscalesJob` tal cual. **Elimina** `createObligacionesFiscalesJob`, que ya no corresponde a la API.

- [ ] **Step 2:** `cd frontend && npm run build` → sin errores.
- [ ] **Step 3:** Commit `feat(of-ui): cliente de la API de dos fases`

---

### Task 2: Portar el sistema visual `pc-*`

**Files:** Create `frontend/src/aud/of/ofWorkspace.css`.

- [ ] **Step 1:** Copiar desde `frontend-client/src/shell/shell.css` **solo** las clases que el workspace usa: `pc-panel`, `pc-panel-h`, `pc-panel-t`, `pc-panel-m`, `pc-panel-b`, `pc-code`, `pc-scenarios`, `pc-scenarios-l`, `pc-chip` (con sus variantes `on`, `accent`, `danger`, `warn`), `pc-tiles`, `pc-tile`, `pc-tile-n`, `pc-tile-txt`, `pc-tile-t`, `pc-tile-d`, `pc-tile-st`, `pc-btn`.

Los tokens (`--accent`, `--panel-2`, `--line`, `--text-soft`, `--accent-dim`) **ya existen** en `frontend/src/styles.css` con los mismos valores, así que no se copian: el workspace hereda los 4 temas del Command Center automáticamente.

Encabeza el archivo con un comentario que explique que es una copia deliberada del portal de clientes, que los nombres de clase se conservan idénticos para que una futura extracción a `frontend-shared` sea mecánica, y que si se corrige un estilo aquí conviene revisar allá.

- [ ] **Step 2:** `npm run build` → sin errores.
- [ ] **Step 3:** Commit `feat(of-ui): sistema visual pc-* portado al Command Center`

---

### Task 3: Chip de documento

**Files:** Create `frontend/src/aud/of/SlotChip.jsx`.

Un chip por slot que muestra `✓ Etiqueta (n)` cuando tiene archivos y `Etiqueta` cuando está vacío. Al hacer clic abre el selector de archivos; con archivos cargados muestra una `×` que llama a `quitarSlotOF`. Usa `pc-chip on` cuando tiene archivos, `pc-chip warn` cuando es requerido y está vacío, `pc-chip` en el resto.

Para `mayor_especifico`, antes de subir pide la categoría con un `select` poblado desde `listarCategoriasOF()`; **no permite subir sin categoría** (el backend responde 400).

Muestra estado de carga mientras sube y el mensaje de error del backend si falla (415 tipo no permitido, 413 muy grande, 409 job ya no editable).

- [ ] **Step 1:** Implementar. - [ ] **Step 2:** `npm run build`. - [ ] **Step 3:** Commit `feat(of-ui): chip de documento con subida incremental`

---

### Task 4: Pantalla de revisión de la clasificación

**Files:** Create `frontend/src/aud/of/RevisionClasificacion.jsx`.

Es el corazón de la herramienta: aquí el auditor confirma lo que el motor propuso.

Tabla con una fila por cuenta: **Código · Cuenta · Movs · Debe · Haber · Categoría (select) · Confianza · Por qué**.

- El `select` se puebla con `categorias` de la respuesta.
- **Ordena primero lo que necesita atención**: confianza `baja`, luego `media`, luego `alta`. Un auditor no debería tener que buscar las dudosas.
- La confianza se muestra como chip: `alta` en verde (`pc-chip on`), `media` en ámbar (`pc-chip warn`), `baja` en rojo (`pc-chip danger`).
- La columna "Por qué" muestra la `justificacion` (lista de motivos). Si es larga, colapsada en un `<details>`.
- Una fila corregida se marca visualmente y muestra también la sugerencia original del motor.
- Cabecera con el resumen: *"N cuentas · X requieren revisión"*.
- Botón **Guardar correcciones** (`guardarCorreccionesOF`, solo envía las que cambiaron) y botón **Aprobar y generar** (`aprobarOF`), este último deshabilitado mientras haya cambios sin guardar.

- [ ] **Step 1:** Implementar. - [ ] **Step 2:** `npm run build`. - [ ] **Step 3:** Commit `feat(of-ui): pantalla de revision de la clasificacion`

---

### Task 5: Panel maestro del workspace

**Files:** Create `ObligacionesFiscalesWorkspace.jsx` y `EditarDatosModal.jsx`; reemplazar `ObligacionesFiscalesTool.jsx`.

Estructura, calcada del ICT:

```
┌ AUD · Workspace de Obligaciones Fiscales        <periodo> · N/M CÉDULAS ┐
│ CONTRIBUYENTE [cliente] [✏ Editar datos]  [▶ Procesar] [📤 Excel] [🔄]  │
│ 📂 SUBIR DOCUMENTOS  [chips de los 6 slots]                             │
│ ▓▓▓▓▓░░░░  X de 6 documentos subidos                                    │
│ [0] Clasificación  [1] DM3  [2] DM4  [3] DM5  [4] DM6  [5] DM7          │
└──────────────────────────────────────────────────────────────────────────┘
┌ Panel inferior: el tile seleccionado                                     │
│  [0] → RevisionClasificacion                                             │
│  [n] → estado de esa cédula y qué documentos usa                         │
└──────────────────────────────────────────────────────────────────────────┘
```

Comportamiento:
- Al montar, si no hay job en curso para el proyecto, crea uno en `borrador`; si lo hay (estado `borrador` o `revision`), lo retoma. **Recargar la página no pierde nada.**
- `▶ Procesar` deshabilitado mientras no haya `mayor_general`, con `title` que lo explique.
- `📤 Descargar Excel` habilitado solo en estado `done`.
- `🔄 Encerar` pide confirmación y borra el job en borrador.
- Los datos del encargo (cliente, período, corte, preparado/revisado por y **firma auditora como chips**, no radios) viven en `EditarDatosModal`.
- Estados de los tiles: Pendiente / Parcial / Completado, según el estado del job.
- Mantener la lista "Generados recientemente" que ya existe.

`ObligacionesFiscalesTool.jsx` queda como envoltorio delgado que renderiza el workspace, para no tocar el catálogo de herramientas.

- [ ] **Step 1:** Implementar. - [ ] **Step 2:** `npm run build`. - [ ] **Step 3:** Commit `feat(of-ui): workspace de Obligaciones Fiscales estilo ICT`

---

### Task 6: Verificación end-to-end en el navegador

**Nada de esto se da por bueno sin verlo funcionando.**

- [ ] **Step 1:** Levantar el backend local y el frontend. El `CLAUDE.md` y la memoria del proyecto documentan el arranque: backend SQLite con `uvicorn app:app`, y Vite con `VITE_PROXY_TARGET=127.0.0.1:8000`. Sembrar un admin y un proyecto AUD.
- [ ] **Step 2:** Recorrer el ciclo completo en pantalla, con los archivos reales del cliente si están disponibles: crear borrador → subir F-104, F-103 y Mayor General → `Procesar` → revisar la tabla (comprobar que las de baja confianza salen primero) → corregir una cuenta → guardar → `Aprobar` → descargar el Excel y abrirlo.
- [ ] **Step 3:** Revisar la consola del navegador y la red: **cero errores**.
- [ ] **Step 4:** Capturas del workspace y de la pantalla de revisión.
- [ ] **Step 5:** Commit de cualquier corrección que salga de la verificación.

---

## Criterio de terminado del Plan 4

- [ ] Las 6 tareas están commiteadas y `npm run build` pasa.
- [ ] El ciclo completo funciona **en el navegador**, no solo en tests.
- [ ] Recargar la página no pierde los documentos subidos.
- [ ] La pantalla de revisión ordena primero lo que requiere atención y explica el porqué de cada clasificación.
- [ ] Cero errores en consola.
- [ ] Ya no queda ninguna referencia a `mayor_compras`, `mayor_ventas` ni a `createObligacionesFiscalesJob`.
- [ ] **La rama puede fusionarse a `main`.**

## Fuera de alcance

- La pantalla de mapeo manual de columnas (el backend ya reporta `columnas_faltantes`; la UI queda para cuando aparezca un ERP que lo necesite).
- DM8 y `ingresos iva vs facturacion`: siguen pendientes de definición del usuario.
