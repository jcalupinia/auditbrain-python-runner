# Validación visual del frontend AuditBrain (Playwright)

Arnés aislado: **no toca app, backend ni producción**. Solo abre el
frontend, hace login y captura pantallas.

## Por qué hace falta un entorno nuevo

La política de red y el browser se fijan **al crear el entorno/sesión**;
no se pueden cambiar dentro de una sesión en curso. En el entorno actual
están bloqueados `cdn.playwright.dev` y `*.onrender.com` (403) y no hay
Chromium, así que la validación visual debe correrse en un entorno nuevo
configurado con una de las opciones de abajo.

## Configuración del entorno nuevo

### Browser (elige UNA)

- **Opción A (recomendada):** imagen/setup con Chromium ya instalado.
- **Opción B:** allowlist de red para descargar el Chromium de Playwright:
  `cdn.playwright.dev`, `playwright.azureedge.net`, `*.blob.core.windows.net`
- **Opción C:** allowlist para Chrome for Testing:
  `googlechromelabs.github.io`, `storage.googleapis.com`

### Setup script del entorno (pégalo en el campo "setup script")

```bash
cd e2e && npm install && npx playwright install --with-deps chromium
```

(Opción A: si la imagen ya trae Chromium, basta `cd e2e && npm install`.)

### Red para el modo Render (solo si validas el sitio desplegado)

Allowlist: `auditbrain-frontend.onrender.com`,
`auditbrain-python-runner.onrender.com` (o `*.onrender.com`).
El modo **local** no necesita esto.

## Ejecutar

### Modo local (sin Render, recomendado para CI)

Levanta stub documental + backend + frontend en `localhost` y valida:

```bash
export PYBIN=/ruta/python/con/requirements-prod   # o python3 con deps
cd e2e && bash run-local.sh
```

### Modo Render (sitio real desplegado)

```bash
export FRONTEND_URL="https://auditbrain-frontend.onrender.com"
export ADMIN_EMAIL=...  ADMIN_PASSWORD=...
export USER_EMAIL=...    USER_PASSWORD=...
cd e2e && bash run-render.sh
```

## Qué valida y entrega

Screenshots en `e2e/screenshots/`:

1. `01-admin-dashboard.png` — login admin + Dashboard (Runner/Usuarios visibles)
2. `02-admin-documentos.png` — panel Documentos
3. `03-doc-pdf.png` — generar PDF
4. `04-doc-word.png` — generar Word
5. `05-user-dashboard.png` — login user (sin Runner ni Usuarios)
6. `06-user-documentos.png` — Documentos sí disponible para user

Además falla si Runner/Usuarios aparecen para `user` y reporta errores
de consola/CORS al final.
