# Cuentas de prueba del Preview (por rol)

Cada Preview Environment (PR) nace con **una** cuenta (el admin del bootstrap).
Para probar AuditBrain como la aplicación real, `backend/app/core/preview_seed.py`
siembra —**solo en previews** (`APP_ENV=preview`), de forma **idempotente**— una
cuenta por cada rol real del sistema (`admin` / `user` / `client`, definidos en
`backend/app/auth/models.py::Role`). En producción no crea, no modifica ni borra nada.

## Cuentas

| Rol | Email | Entra por | Para qué sirve |
|---|---|---|---|
| `admin` | `preview-admin@audit-ia.ec` | Command Center (`/api/v1/auth/login`) | Administración: gestiona operadores y clientes, ve todo. Es el admin del bootstrap (no lo crea el seeder). |
| `user` | `preview-operador@audit-ia.ec` | Command Center (`/api/v1/auth/login`) | Operador del Command Center (`require_staff`). |
| `client` | `preview-cliente@audit-ia.ec` | Portal de clientes (`/client/auth/login`) | Cliente externo del portal; ligado a un «Cliente de prueba (preview)» con herramientas concedidas. |

## Contraseña (exclusiva del preview, nunca de producción)

Las tres cuentas usan **la misma clave exclusiva de ese preview**: la del admin,
generada por PR en el volumen de secretos (`/run/secrets/admin_password`). **No
está en el repositorio** ni en variables de Coolify. Para obtenerla, en el
servidor:

```bash
docker exec <contenedor-backend-del-PR> sh -c 'cat /run/secrets/admin_password; echo'
```

(`<contenedor-backend-del-PR>` es el backend del preview, p. ej. `backend-pr-405-…`;
`docker ps | grep backend-pr` lo lista.)

Si el preview arranca sin esa clave en el entorno, el seeder **no** crea las
cuentas `user`/`client` (y lo registra en el log). Nunca se hardcodea una clave.

## Datos de prueba

- La cuenta `client` queda ligada a la organización por defecto y a un `Client`
  llamado **«Cliente de prueba (preview)»**, con entitlements a las herramientas
  listadas en `preview_seed.PREVIEW_CLIENTE_TOOL_CODES` (validadas contra el
  catálogo real `client_portal.tool_registry.TOOLS`).
- La base del preview es exclusiva del PR; estas cuentas y sus datos no salen de
  esa base aislada y no tocan la de producción.

## Garantías

- Solo corre con `APP_ENV=preview`; es un no-op en producción.
- Idempotente: no duplica cuentas ni el `Client` en cada despliegue.
- No importa contraseñas, hashes, tokens ni PII de producción; no borra ni
  modifica usuarios existentes; no desactiva la autenticación ni relaja los
  controles de autorización (los roles reales se respetan).

Pruebas: `tests/test_preview_seed.py`.
