# NIIF 18 Studio V4 — recurso estático del portal

`studio.html` **se genera**, no se edita a mano.

Fuente: repositorio privado `jcalupinia/herramienta-niif-18`.

```bash
# en ese repositorio
python3 scripts/integrar-studio.py docs/NIIF18_STUDIO_V3_original.html public/index.html
```

Después se copia aquí:

```bash
cp ../herramienta-niif-18/public/index.html frontend-client/public/niif18/studio.html
```

La página se abre desde `/tools/NIIF_18_STUDIO` dentro de un marco del portal.
Lee el token de sesión del portal (`ab_client_token`, mismo origen) y llama a
`/api/v1/client/niif18/*` con `Authorization: Bearer`. No tiene login propio.
