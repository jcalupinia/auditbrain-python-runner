"""Dependencies de autenticación/autorización.

- get_current_user / require_admin: para el frontend (JWT Bearer).
- require_runner_access: protege el runner. Acepta:
    * JWT de un usuario con rol admin (frontend), o
    * X-API-Key válida (GPTs server-to-server), o
    * modo legacy abierto (si NO hay API Key configurada y no se envía
      Bearer) -> preserva el comportamiento actual y los tests.
  Un JWT de usuario NO admin recibe 403 explícito (runner solo admin).
"""

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.auth import service
from backend.app.auth.jwt_tokens import decode_token
from backend.app.auth.models import Role, User
from backend.app.core.config import settings
from backend.app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.PLATFORM_API_PREFIX}/auth/login", auto_error=True
)

_CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o token expirado.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _user_from_token(token: str, db: Session) -> User:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise _CRED_EXC
    email = payload.get("sub")
    if not email:
        raise _CRED_EXC
    user = service.get_user_by_email(db, email)
    if not user or not user.is_active:
        raise _CRED_EXC
    # Defense-in-depth: client-role JWTs must NEVER pass through staff dependencies.
    # The portal cliente uses require_client_with_device which validates separately.
    if user.role == Role.client:
        raise _CRED_EXC
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    return _user_from_token(token, db)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere rol admin.",
        )
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    """Operadores del Command Center: admin o user.

    Los operadores (rol user) tienen las mismas capacidades de trabajo que el
    admin (ver/crear/usar clientes y proyectos). La ÚNICA excepción, que sigue
    siendo admin-only, es la gestión de cuentas: crear usuarios de clientes de
    portal y crear/administrar operadores (staff_portal + auth). Excluye el rol
    client de portal.
    """
    if user.role not in (Role.admin, Role.user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere rol operador (admin o user).",
        )
    return user


async def require_runner_access(
    request: Request, db: Session = Depends(get_db)
) -> None:
    authz = request.headers.get("Authorization", "")
    if authz.lower().startswith("bearer "):
        token = authz.split(" ", 1)[1].strip()
        user = _user_from_token(token, db)
        # Política de firma: operadores (admin o user) pueden usar el runner.
        if user.role not in (Role.admin, Role.user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El runner está restringido a operadores (admin o user).",
            )
        return

    # Sin Bearer -> ruta server-to-server (GPTs) o modo legacy.
    if settings.auth_enabled:
        if request.headers.get(settings.API_KEY_HEADER, "") != settings.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key inválida o ausente.",
                headers={"WWW-Authenticate": settings.API_KEY_HEADER},
            )
        return
    # auth_enabled False => modo legacy abierto (idéntico al actual).
    return


async def require_user_access(
    request: Request, db: Session = Depends(get_db)
) -> None:
    """Acceso para cualquier usuario autenticado (JWT, cualquier rol) o
    X-API-Key (GPTs server-to-server) o modo legacy abierto. NO restringe
    por rol: usado por endpoints disponibles a admin y user (p. ej.
    generación de documentos). El runner sigue con require_runner_access.
    """
    authz = request.headers.get("Authorization", "")
    if authz.lower().startswith("bearer "):
        token = authz.split(" ", 1)[1].strip()
        _user_from_token(token, db)  # valida JWT y usuario activo
        return

    if settings.auth_enabled:
        if request.headers.get(settings.API_KEY_HEADER, "") != settings.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key inválida o ausente.",
                headers={"WWW-Authenticate": settings.API_KEY_HEADER},
            )
        return
    return


# ---------------------------------------------------------------------------
# Portal Cliente: triple capa de seguridad
# ---------------------------------------------------------------------------

from fastapi import Cookie  # noqa: E402

from backend.app.auth.device import compute_fingerprint_hash, validate_device  # noqa: E402

CLIENT_SESSION_INVALIDATED_CODE = "session_invalidated"
CLIENT_DEVICE_UNAUTHORIZED_CODE = "device_unauthorized"


def _device_check_enabled() -> bool:
    """Toggle para desactivar la triple validación cliente durante pruebas.

    Lectura PEREZOSA (cada request) — permite encender/apagar via env var
    sin redeploy: basta con cambiar CLIENT_PORTAL_DEVICE_CHECK_ENABLED en
    Render y restart del servicio. Default: True (seguridad ON).

    Valores aceptados como False: "0", "false", "no", "off" (case-insensitive).
    Cualquier otro valor → True.
    """
    import os
    v = os.getenv("CLIENT_PORTAL_DEVICE_CHECK_ENABLED", "true").strip().lower()
    return v not in {"0", "false", "no", "off"}


def _session_check_enabled() -> bool:
    """Igual que device check pero para la unicidad de sesión (sid).
    Cuando está apagado, un cliente puede tener múltiples sesiones
    simultáneas. Útil mientras se hace QA con varias pestañas/browsers.
    """
    import os
    v = os.getenv("CLIENT_PORTAL_SESSION_CHECK_ENABLED", "true").strip().lower()
    return v not in {"0", "false", "no", "off"}


def require_client_with_device(
    request: Request,
    device_id: str | None = Cookie(default=None, alias="device_id"),
    db: Session = Depends(get_db),
) -> User:
    """Triple validación para endpoints /client/*:
    1. JWT firmado válido + rol == client
    2. Cookie device_id presente, activa, fingerprint coincide
    3. JWT.sid == User.current_session_id (sesión única)

    Las capas 2 y 3 se pueden desactivar individualmente vía env vars
    CLIENT_PORTAL_DEVICE_CHECK_ENABLED y CLIENT_PORTAL_SESSION_CHECK_ENABLED
    (útil durante QA / pruebas piloto). La capa 1 (JWT + rol) siempre activa.
    """
    authz = request.headers.get("Authorization", "")
    if not authz.lower().startswith("bearer "):
        raise HTTPException(401, detail="Falta token Bearer.")
    token = authz.split(" ", 1)[1].strip()

    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise _CRED_EXC

    email = payload.get("sub")
    jwt_role = payload.get("role")
    jwt_sid = payload.get("sid")
    jwt_did = payload.get("did")

    _staff_roles = {Role.admin.value, Role.user.value}
    if jwt_role != Role.client.value and jwt_role not in _staff_roles:
        raise HTTPException(403, detail="Acceso reservado a clientes u operadores.")

    user = service.get_user_by_email(db, email)
    if not user or not user.is_active or user.role not in (Role.client, Role.admin, Role.user):
        raise _CRED_EXC

    # Operadores (admin/user) entran al portal con su mismo usuario, sin los
    # chequeos de dispositivo/sesión única (esos son específicos del cliente).
    if user.role in (Role.admin, Role.user):
        return user

    # Layer 3: session uniqueness (puede deshabilitarse via env)
    if _session_check_enabled():
        if not jwt_sid or jwt_sid != user.current_session_id:
            raise HTTPException(
                401,
                detail={
                    "code": CLIENT_SESSION_INVALIDATED_CODE,
                    "message": "Su sesión fue cerrada porque inició sesión desde otro lugar.",
                },
            )
        # Heartbeat: refresca la última actividad para mantener viva la sesión
        # mientras el cliente usa el sistema. Si deja de haber requests, la
        # sesión se libera sola tras el timeout de inactividad (~10 min) y otra
        # persona podrá ingresar (regla "el primero gana").
        service.touch_session(db, user=user)

    # Layer 2: device binding (puede deshabilitarse via env)
    if not _device_check_enabled():
        return user  # bypass — solo se exigió JWT + rol

    # Layer 2: device binding
    # Preferimos la cookie ``device_id`` (httponly, protección anti-XSS y
    # anti-replay), pero los browsers modernos (Chrome incógnito + Privacy
    # Sandbox) bloquean cookies cross-site aunque tengan
    # ``SameSite=None; Secure`` cuando el frontend y backend viven en
    # subdominios distintos bajo la Public Suffix List (caso *.onrender.com).
    # Fallback: el ``did`` claim que ya viaja en el JWT permite validar el
    # dispositivo aunque la cookie no llegue. El JWT está firmado, por lo
    # que un atacante no puede forjar el ``did``. Sigue requiriéndose que
    # el fingerprint del request coincida con el del registro persistido.
    effective_device_id = device_id or jwt_did
    if not effective_device_id:
        raise HTTPException(
            409,
            detail={
                "code": CLIENT_DEVICE_UNAUTHORIZED_CODE,
                "message": "Falta identificador de dispositivo. Inicie sesión nuevamente.",
            },
        )

    fingerprint = compute_fingerprint_hash(
        user_agent=request.headers.get("user-agent", ""),
        accept_language=request.headers.get("accept-language", ""),
        accept_encoding=request.headers.get("accept-encoding", ""),
    )
    device = validate_device(
        db, user=user, device_id=effective_device_id, fingerprint_hash=fingerprint
    )
    if device is None:
        raise HTTPException(
            409,
            detail={
                "code": CLIENT_DEVICE_UNAUTHORIZED_CODE,
                "message": "Este dispositivo no está autorizado. Solicite reseteo a soporte.",
            },
        )

    return user
