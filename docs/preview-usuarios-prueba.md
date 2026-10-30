# Cuentas de prueba del Preview (admin real + operadores, sin PII en Git)

Para probar AUDIT-IA como la aplicación real, el preview reproduce **1 admin** (el
jefe) y los **operadores** del equipo, cada uno con su correo real y su rol
verificado. Se siembra **solo en previews** (`APP_ENV=preview`), de forma
**idempotente**, sobre la base **aislada del PR**. En producción es un no-op.

## Los correos reales NUNCA están en Git ni en variables globales

El repositorio es **público**, así que ningún correo real se versiona. Tampoco se
usan variables de entorno del app en Coolify: **se heredarían en todos los previews**
(cada preview es un despliegue del mismo app con las mismas variables), lo que
expondría la PII a cualquier preview autorizado. En su lugar, los correos se leen de
un **archivo de identidades** que vive **solo en el volumen aislado del preview
autorizado**.

### Archivo de identidades (por PR, aislado)

- Ruta (configurable con `PREVIEW_IDENTITIES_FILE`): por defecto
  `/var/data/preview-seed/identidades.json`, en el volumen `appdata` del PR.
- Formato:
  ```json
  { "admin": "correo-del-jefe@dominio", "operators": ["op1@dominio", "…", "op8@dominio"] }
  ```
- Lo coloca un operador de confianza, **solo en el preview autorizado**, por la
  terminal del contenedor:
  ```bash
  docker exec <backend-pr-N> sh -c 'umask 077; mkdir -p /var/data/preview-seed; cat > /var/data/preview-seed/identidades.json'
  ```
  (pega el JSON y Ctrl-D). Persiste entre redeploys del PR; se hace una sola vez.
- Tras colocarlo, siembra sin reiniciar:
  ```bash
  docker exec <backend-pr-N> python -c "from backend.app.db.session import SessionLocal; from backend.app.core import preview_seed; print(preview_seed.seed_preview_users(SessionLocal()))"
  ```

> ⚠️ **Aislamiento del volumen:** esto depende de que `appdata` esté aislado por
> preview (Coolify lo sufija `appdata-pr-N`). **Verifícalo en el servidor** antes de
> colocar correos reales: `docker volume ls | grep appdata` debe mostrar un volumen
> por PR. Si no puedes demostrarlo, **no coloques correos reales**.

## Administrador

- Con un `admin` válido en el archivo, esa cuenta se crea/asegura como **`admin`**
  con clave aleatoria propia, y el **admin genérico de reserva**
  `preview-admin@audit-ia.ec` se **desactiva** (no se borra), para no tener dos admins
  activos ni claves compartidas.
- Sin archivo válido, queda el **admin genérico de reserva** (`preview-admin@audit-ia.ec`),
  que crea `ensure_bootstrap_admin` solo en previews. Es un correo genérico NO-PII.

## Operadores

Rol `user`, activos, organización por defecto (configuración verificada). Cada uno con
clave **aleatoria e independiente** (`secrets.token_urlsafe`). No se copian credenciales
de producción. El correo del admin se excluye de la lista de operadores.

## Contraseñas

Se guardan con permisos 600 en el volumen RW del PR (`PREVIEW_USER_SECRETS_DIR`, por
defecto `/var/data/preview-users`), con **nombre de archivo hash** del correo (no se
expone la identidad en el volumen). Nunca van al repo, a variables de Coolify ni a los
logs (el seeder registra solo conteos).

### Recuperar / listar claves (solo preview, controlado)

```bash
# Re-emitir (clave nueva) una cuenta por su correo:
docker exec <backend-pr-N> python scripts/recuperar_clave_preview.py correo@dominio

# Listar correo→clave de todas las cuentas configuradas (para repartir en privado):
docker exec <backend-pr-N> python scripts/recuperar_clave_preview.py --listar
```

## Idempotencia y seguridad

- Idempotente por correo; **no resetea** contraseñas en el arranque (si falta el
  archivo de clave, solo avisa; la recuperación es explícita).
- Fallo de escritura de una clave → la cuenta queda **inactiva** y se reporta como
  fallida (nunca como provisionada).
- Solo corre con `APP_ENV=preview`; base del PR aislada (`DATABASE_URL` host `db`);
  **no toca producción**; no copia PII/credenciales de producción; no debilita la
  autenticación ni los roles.

## Verificación

```bash
python scripts/verificar_usuarios_preview.py     # DIFERENCIAS: 0
```
Control cruzado por API (JWT admin): `GET /api/v1/auth/users` lista admin + operadores.

Pruebas: `tests/test_preview_seed.py` (incluye una guarda anti-PII que falla si un
correo real aparece en archivos versionados).
