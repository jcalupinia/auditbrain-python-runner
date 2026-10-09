# Validación de Preview Environments (Render)

Archivo de prueba, sin efecto funcional. Existe sólo para que un Pull Request
con cambios **fuera** de `frontend/` y `frontend-client/` dispare la creación
del Preview Environment completo definido en `render.yaml`
(`previews.generation: automatic`).

## Qué cubre este archivo

| Recurso (`render.yaml`) | Cómo detecta cambios | Lo cubre |
|---|---|---|
| `auditbrain-python-runner` (backend, Docker) | `dockerContext: .` sin `buildFilter`: cualquier ruta del repo | este archivo (`docs/`) |
| `auditbrain-db` (Postgres) | no depende de archivos; el preview crea una base propia | n/a |
| `auditbrain-frontend` (estático) | `rootDir: frontend` sin `buildFilter` | `frontend/PREVIEW_VALIDATION.md` |
| `auditbrain-clientes` (estático) | `rootDir: frontend-client` sin `buildFilter` | `frontend-client/PREVIEW_VALIDATION.md` |

## Qué verificar en el preview

1. Render crea cuatro recursos con sufijo `-pr-<n>`: backend, frontend, clientes y base de datos.
2. El backend arranca con `APP_ENV=preview` y una base vacía propia (admin inicial creado al primer arranque).
3. La consola y el portal del preview llaman al backend **del mismo preview** (no a producción); ver `frontend/src/api.js` y `frontend-client/src/api.js`.
4. Los correos y retornos de Stripe del preview apuntan al portal del preview (`backend/app/core/preview.py`).
5. Producción (`main`) no recibe ningún despliegue por este PR.

## Inocuidad

- No cambia código, secretos ni `render.yaml`.
- Entra en la imagen Docker del backend (como `README.md`), pero ningún módulo lo lee.
- Puede borrarse junto con la rama `test/render-preview-validation` al cerrar la prueba.
