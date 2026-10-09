# Validación de Preview Environments: portal de clientes (`auditbrain-clientes`)

Archivo de prueba, sin efecto funcional. Vive bajo `rootDir: frontend-client`
para que el Pull Request de validación cuente como un cambio de este sitio
estático (sin `buildFilter`, Render sólo considera cambios dentro de su
`rootDir`).

- Vite no lo incluye en `dist/` (sólo empaqueta `src/` y `public/`).
- `.dockerignore` excluye `frontend-client/` de la imagen del backend.
- Detalle del plan de verificación: `docs/preview-validation/README.md`.
- Puede borrarse al cerrar la rama `test/render-preview-validation`.
