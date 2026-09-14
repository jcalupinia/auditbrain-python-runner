# Recursos v2 — Cuentas y accesos · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Cuentas con clave personal generada, accesos por recurso administrados desde la consola, pantalla de acceso tipo app en ambas calculadoras, tarjeta "NUEVO" del anticipo y botones 3D arriba.

**Architecture:** Tablas nuevas `recurso_cuentas` y `recurso_accesos` en `backend/app/recursos/`; endpoints públicos `registros`/`ingresar`/`olvide-clave`; endpoints staff `cuentas`. Consola: pestaña REC reescrita sobre `/cuentas`. Mini-sitio: recuadro `#gate` reescrito con vistas Ingresar/Registro/Olvidé, aplicado a las dos calculadoras.

**Spec:** `docs/superpowers/specs/2026-09-14-recursos-cuentas-y-accesos-design.md` (fuente de verdad de textos, rutas y reglas).

**Repos:** portal = worktree `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\ab-recursos-leads` rama `feat/recursos-cuentas` (desde origin/main 4b7e3b7). Mini-sitio = `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\audit-ia-recursos` rama `main` (**sin push**). Tests backend SIEMPRE con base aparte: `TEST_DATABASE_URL="sqlite:///C:/Users/jcalu/AppData/Local/Temp/<nombre>.db"`.

---

### Task 1: Backend — cuentas, accesos, login y staff

**Files:** `backend/app/recursos/{catalog,models,schemas,service,notify,router}.py`, nuevo `backend/app/recursos/claves.py`; borrar `backend/app/recursos/tokens.py` y `tests/test_recursos_tokens.py`; `backend/app/notifications/{email.py,templates/recurso_acceso.html}`; tests `tests/test_recursos_router.py`, `tests/test_notifications_recurso_email.py`, nuevo `tests/test_recursos_cuentas.py`; spec ya escrita.

- [ ] **1. claves.py** (TDD, test primero):

```python
"""Clave personal de recursos: legible, sin caracteres ambiguos."""
from __future__ import annotations
import secrets

ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

def generar_clave() -> str:
    c = "".join(secrets.choice(ALFABETO) for _ in range(9))
    return f"{c[:3]}-{c[3:6]}-{c[6:]}"

def normalizar(clave: str) -> str:
    """Forma canónica de una clave GENERADA: sin guiones/espacios, mayúsculas."""
    return "".join(ch for ch in clave if ch.isalnum()).upper()
```
Regla de hash: al generar se guarda `hash_password(normalizar(clave))` y se marca
`clave_generada=True` en la cuenta; al verificar, si `clave_generada` se compara
`verify_password(normalizar(escrita), hashed)`, si no (clave escrita por admin) se compara
`verify_password(escrita, hashed)` exacta. (Añadir columna `clave_generada: bool` a
`recurso_cuentas`.)

- [ ] **2. models.py**: `RecursoCuenta` (id, email único, hashed_clave, clave_generada, activo, ultimo_ingreso_at, clave_actualizada_at, created_at) y `RecursoAcceso` (id, cuenta_id FK, recurso_slug, otorgado_por, created_at, UniqueConstraint). Reusar `_utcnow`.
- [ ] **3. catalog.py**: `Recurso` + `registro_abierto: bool`; entradas `ir-personas-naturales-2026` (True) y `anticipo-ir-2026` (False, título "Calculadora del Anticipo IR sobre Utilidades No Distribuidas 2026", URL `https://recursos.audit-ia.ec/anticipo-ir-2026/`). Helper `recursos()` que devuelve la lista (para la consola).
- [ ] **4. service.py**: funciones puras con `db`: `obtener_cuenta(email)`, `crear_cuenta(email) -> (cuenta, clave)`, `rotar_clave(cuenta, nueva: str|None) -> clave` (None → generada), `asegurar_acceso(cuenta, slug, otorgado_por)`, `quitar_acceso`, `accesos(cuenta) -> set[str]`, `verificar(cuenta, clave) -> bool`, `listar_cuentas()` (con datos del lead más reciente por email). Mantener `registrar` (lead) sin cambios de comportamiento.
- [ ] **5. notify.py**: `enviar_clave(cuenta_id: int, clave: str, slug: str)` en background: `email_mod.send_recurso_acceso(to, titulo, enlace=rec.url, clave=clave, contacto=CONTACTO)`; `email_enviado` del lead de ese slug se pone True solo si hay éxito (no se baja). La clave viaja como argumento del task (no se persiste en claro).
- [ ] **6. email.py + plantilla**: `render_recurso_acceso(*, titulo, email, enlace, clave, contacto)` y `send_recurso_acceso(*, to, titulo, enlace, clave, contacto)` con asunto `f"Su usuario y clave — {titulo}"`, `max_retries=2`. Plantilla: mantener la línea gráfica actual (navy/lime, logo, pie) y cambiar el cuerpo según la spec (usuario, **clave** en recurso destacado monoespaciado, botón "Ingresar a mi calculadora", texto de guardar el correo y "¿Olvidó su clave?"). Escapar todo con `html.escape`.
- [ ] **7. router.py**: endpoints de la spec (`registros`, `ingresar`, `olvide-clave`, `cuentas` GET, accesos PUT/DELETE, `reset-clave`, `activo`); eliminar `acceso` y `reenviar`. `ingresar`: limitar primero por IP (`_limite`), luego `check_and_record(f"recurso-login:{email}", max_hits=10, window_seconds=600)` → 429. Mensajes exactos de la spec. `reset-clave` responde `{email, temp_password, note: "Comparta esta clave con la persona por un canal seguro. No se vuelve a mostrar."}`. Modificaciones con `Depends(require_admin)`; lectura con `require_staff`.
- [ ] **8. Tests** (TDD por endpoint; parchear `backend.app.recursos.notify.enviar_clave` capturando `(cuenta_id, clave, slug)` para poder ingresar con la clave real en el test): todos los casos de la sección Pruebas de la spec, incluidos: registro nuevo → cuenta + acceso PN + envío; login con la clave capturada (también en minúsculas y sin guiones) → 200; clave errada → 401; anticipo sin acceso → 403 con el mensaje; admin otorga acceso → login anticipo 200; operador (rol user) no puede otorgar (403) pero sí listar (200); reset con clave escrita y sin clave; cuenta inactiva → 401; olvidé clave con lead previo sin cuenta crea cuenta; registro en `anticipo-ir-2026` → 404; 11 fallos del mismo correo → 429. Mantener tests de límites/honeypot/IP existentes. Correr además `tests/test_client_ip.py tests/test_events_router.py tests/test_notifications_email.py tests/test_notifications_charla_email.py`.
- [ ] **9. Commit** `feat(recursos): cuentas con clave personal, accesos por recurso y login` + trailer.

### Task 2: Consola — pestaña REC con cuentas y accesos

**Files:** `frontend/src/api.js`, `frontend/src/App.jsx` (componente `RecursosLeads` → `RecursosCuentas`), test vitest si aplica.

- [ ] api.js: `listRecursoCuentas()`, `setRecursoAcceso(id, slug, on)` (PUT/DELETE), `resetRecursoClave(id, newPassword|null, enviarCorreo)`, `setRecursoActivo(id, activo)`.
- [ ] App.jsx: tabla de cuentas según la spec; casillas por recurso (lista fija `[{slug:"ir-personas-naturales-2026", label:"IR PN"}, {slug:"anticipo-ir-2026", label:"Anticipo"}]`), deshabilitadas si no es admin; **Resetear clave** reutilizando el mismo patrón visual/flujo de `askAssign`/reveal de Cuentas (leer `App.jsx` ~l.540-700 y copiar el patrón, no inventar otro): campos clave + confirmar (opcional), casilla "Enviar la clave por correo", resultado mostrado una vez con el `note`; **Desactivar/Activar**. CSV con accesos y estado (reusar `_descargarCsv`). Recibir `isAdmin` como prop desde `render()`.
- [ ] `npx vitest run` + `npm run build` verdes. Commit `feat(consola): REC gestiona cuentas, accesos y claves de recursos`.

### Task 3: Mini-sitio — acceso tipo app, tarjetas y botones 3D

**Files:** `public/ir-personas-naturales-2026/index.html`, `public/anticipo-ir-2026/index.html`, `public/index.html`.

- [ ] Reescribir el bloque `#gate` (dentro de los marcadores `<!-- ===== Registro de acceso` … `/Registro de acceso ===== -->`) con las vistas Ingresar / Registro / Olvidé / OK de la spec, parametrizado por `SLUG` y `REGISTRO_ABIERTO`. API: `POST {API}/ingresar`, `POST {API}/registros`, `POST {API}/olvide-clave`. Conservar: `#gate[hidden]{display:none}`, `inert` en header/main/footer, host local/producción, `AbortController` 60 s, ping `/healthz`, `try/catch` en localStorage, `textContent` (nunca innerHTML con datos). Quitar el manejo de `?acceso=`. Soportar `#ingresar` y `#registro`. Botón mostrar/ocultar clave. En anticipo, recuadro de acceso restringido con WhatsApp `https://wa.me/593990609811?text=Hola%2C%20quiero%20acceso%20a%20la%20Calculadora%20del%20Anticipo%20IR%202026` y `mailto:jcalupinia@auditconsulting.ec`.
- [ ] Insertar el `#gate` en `anticipo-ir-2026/index.html` antes de `</body>` + `<meta name="referrer" content="no-referrer">`.
- [ ] Mover la fila de botones de cada calculadora debajo de la tarjeta de datos (PN: tras "Identificación y Parámetros"; Anticipo: tras datos de la empresa con Guardar/Cargar/Eliminar cliente y el selector de clientes) sin romper ids ni listeners; `statusMsg` va con ellos.
- [ ] CSS 3D común para `.btn` en ambas calculadoras y botones del `#gate` y tarjetas (spec). Íconos en el texto de los botones.
- [ ] `public/index.html`: tarjetas según la spec (01: Ingresar + Quiero; 02: badge NUEVO animado con `@media (prefers-reduced-motion: reduce)` sin animación, "Acceso bajo solicitud", Ingresar + Solicitar acceso). Mantener el resto.
- [ ] Checks: html.parser, `node --check` de cada `<script>` nuevo/modificado, `git diff` limitado a lo previsto. Commit local (sin push).

### Task 4: Verificación E2E local y capturas

- [ ] Levantar API local (`api-recursos-local`, base temporal) + mini-sitio (`recursos-local`) + consola (`consola-recursos-local`).
- [ ] Recorrido: registro PN → capturar clave del log/patch (sin RESEND: leer la clave vía un parche local o endpoint admin reset) → ingresar PN → ingresar anticipo 403 → admin otorga acceso en REC → ingresar anticipo 200 → resetear clave en REC → ingresar con la nueva → desactivar → 401. Móvil 375 px. Capturas de botones 3D y pantalla de acceso para el dueño.

### Task 5: PR, aprobación y publicación

- [ ] PR del portal; esperar CI; **pedir aprobación al dueño** para fusionar; verificar deploy; **pedir aprobación** para push del mini-sitio; verificar en producción (incl. cuenta del dueño: olvidé clave → correo con clave → ingresar).
