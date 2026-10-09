# Validación de Preview Environments: consola (`auditbrain-frontend`)

Archivo de prueba, sin efecto funcional. Vive bajo `rootDir: frontend` para que
el Pull Request de validación cuente como un cambio de este sitio estático
(sin `buildFilter`, Render sólo considera cambios dentro de su `rootDir`).

- Vite no lo incluye en `dist/` (sólo empaqueta `src/` y `public/`).
- `.dockerignore` lo deja fuera de la imagen del backend.
- Detalle del plan de verificación: `docs/preview-validation/README.md`.
- Puede borrarse al cerrar la rama `test/render-preview-validation`.
