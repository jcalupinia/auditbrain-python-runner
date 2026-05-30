# Playwright E2E - Portal Cliente

Smoke tests críticos contra el portal cliente (despliegue Render o local).

## Setup

```bash
cd e2e-portal-cliente
npm install
npx playwright install chromium
```

## Run

```bash
# Contra producción Render:
npx playwright test

# Contra local Vite (puerto 5174):
E2E_BASE_URL=http://localhost:5174 npx playwright test
```

## Cobertura actual (MVP)

- `happy-path.spec.js`:
  - Landing → click "Ingresar" → llega a `/login`
  - Login con credenciales inválidas muestra mensaje de error

## Próximos tests (no MVP — requieren backend con datos)

- Login completo + cambio de password forzado al primer login
- Subir documento → ver progreso polling → descargar entregable
- Bloqueo cuando se intenta acceder desde segundo dispositivo
- Sesión cerrada automáticamente al hacer login desde otro lugar
- Descarga fallida después de 24h (TTL expirado)
