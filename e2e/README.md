# AuditBrain E2E (Playwright)

End-to-end tests del frontend. Los mocks de API (`page.route`) hacen que la suite
no dependa de Render: corre offline contra el dev server de Vite.

## Setup

```bash
cd e2e
npm install
npx playwright install chromium
```

> El navegador se descarga de `cdn.playwright.dev`. Si el entorno bloquea ese
> dominio (por ejemplo el contenedor de Claude Code Web), instala Chromium en
> una máquina con red abierta o ejecútalo en CI.

## Ejecutar

```bash
npm test              # corre toda la suite
npm run list          # solo listar specs
npm run report        # ver HTML report de la última corrida
```

Playwright arranca automáticamente el frontend en `localhost:5173` y le
inyecta `VITE_API_BASE=""` para que `api.js` emita rutas relativas y
`page.route()` pueda interceptarlas en el navegador.

## Estructura

| Archivo | Cobertura |
|---|---|
| `tests/login.spec.js` | Pantalla de login, credenciales válidas/inválidas, Salir |
| `tests/navigation.spec.js` | Sidebar de módulos, Workspace Cognitivo, Centro de Operaciones, footer |
| `tests/rbac.spec.js` | Visibilidad por rol (admin vs user) + ejecución del runner |
| `tests/documents.spec.js` | Generación documental + enlace de descarga |
| `tests/helpers.js` | Mocks de `/api/v1/*` y helper `login()` |

## Selectores

Apuntan a la **UI actual** (`feat/m4-context+chat+skills` mergeado):
- Botón de login: `"Acceder al Command Center"` (no "Entrar").
- Nodo de runner en sidebar: `"Motor de Ejecución"` (no "Python Runner").
- Nodo de usuarios: `"Cuentas"` (no "Usuarios").
- Shell: `aside.cc-side`, `footer.cc-foot` (no `nav.nav`).

Cuando la UI evolucione, esta lista hay que mantenerla.
