# AuditBrain Frontend (F2 — Fase B)

SPA React (Vite) privada. Login con email/contraseña contra
`/api/v1/auth/login` (JWT). **La API Key nunca vive en el navegador**:
el frontend solo usa el token JWT del usuario. El runner solo es visible
para el rol `admin`.

## Desarrollo local

```bash
cd frontend
npm ci
cp .env.example .env   # ajusta VITE_API_BASE si tu backend es local
npm run dev
```

## Build de producción

```bash
npm ci && npm run build   # genera frontend/dist
```

## Despliegue (Render Static Site)

Definido en `render.yaml` (servicio `auditbrain-frontend`). Tras el
deploy, añade el origin del static site a `CORS_ALLOW_ORIGINS` del
backend para que el navegador pueda llamarlo.
