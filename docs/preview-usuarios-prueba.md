# Cuentas de prueba del Preview (operadores reales reproducidos)

Cada Preview Environment (PR) nace con **una** cuenta: el admin del bootstrap
(`preview-admin@audit-ia.ec`). Para probar AUDIT-IA como la aplicación real,
`backend/app/core/preview_seed.py` siembra —**solo en previews** (`APP_ENV=preview`),
de forma **idempotente**— las cuentas de **operador** reproducidas del entorno real,
declaradas en `backend/app/core/preview_users.py`. En producción no crea, no modifica
ni borra nada.

## Alcance (decisión del dueño, 2026-10-29)

- Se reproducen **solo los operadores** (rol `user`). Las cuentas de rol `client`
  **no** se reproducen.
- El acceso de cada cuenta se tomó de la **configuración real verificada** en la BD
  de producción (exportación de solo lectura: SQL `SELECT` + control cruzado por los
  endpoints admin). No se asignan permisos por inferencia ni por el correo.

## Cuentas sembradas

| Rol | Alias (login) | Entra por | Cuántas |
|---|---|---|---|
| `admin` | `preview-admin@audit-ia.ec` | Command Center (`/api/v1/auth/login`) | 1 (es el admin del bootstrap; **no** lo crea el seeder) |
| `user` | `pr-op-01@preview.audit-ia.ec` … `pr-op-08@preview.audit-ia.ec` | Command Center (`/api/v1/auth/login`) | 8 operadores |

Los alias son **exclusivos del preview**: no son identidades productivas y viven solo
en la base aislada del PR. El mapa alias → persona real lo conserva el dueño **fuera
del repositorio** (no se versiona).

## Contraseñas (aleatorias e independientes por cuenta)

Cada cuenta recibe una **clave aleatoria propia** (`secrets.token_urlsafe`), distinta
de la del admin y de las demás. **No** se deriva de ninguna clave compartida, **no**
está en el repositorio, **no** va a variables de Coolify ni a los logs.

Se guardan, con permisos 600, en el volumen de datos del preview (read-write y
persistente por PR). Directorio configurable con `PREVIEW_USER_SECRETS_DIR`
(por defecto `/var/data/preview-users`). Para obtener la clave de una cuenta:

```bash
docker exec <contenedor-backend-del-PR> sh -c 'cat /var/data/preview-users/pr-op-01; echo'
```

(`<contenedor-backend-del-PR>` es el backend del preview, p. ej. `backend-pr-412-…`;
`docker ps | grep backend-pr` lo lista. El nombre del archivo es la parte local del
alias, p. ej. `pr-op-01`.)

> Nota: el volumen `secrets` del compose (`/run/secrets`) está montado **read-only**
> en el backend; por eso las claves por cuenta van en `/var/data` (volumen `appdata`),
> no en `/run/secrets`.

## Idempotencia y recuperación

- Si el alias ya existe, no se recrea.
- Si la cuenta existe pero su archivo de clave se perdió (p. ej. se recreó el volumen),
  el seeder **re-emite** la clave para que la cuenta de QA siga siendo usable — solo
  para las cuentas de esta matriz, nunca para el admin ni otras cuentas.

## Verificación automatizada

```bash
python scripts/verificar_usuarios_preview.py
```

Read-only: compara la BD del preview contra la matriz (rol, estado, organización) y
termina con «DIFERENCIAS: 0» si todo coincide. Control cruzado por API (con JWT de
admin): `GET /api/v1/auth/users` debe listar los 8 operadores con rol `user`.

## Garantías

- Solo corre con `APP_ENV=preview`; es un no-op en producción.
- Base del PR aislada; estas cuentas y sus datos no tocan la de producción.
- Idempotente: no duplica cuentas.
- No importa contraseñas, hashes, tokens ni PII de producción; no borra ni modifica
  usuarios ajenos a la matriz; no desactiva la autenticación ni relaja los controles
  de autorización (los roles reales se respetan).

Pruebas: `tests/test_preview_seed.py`.
