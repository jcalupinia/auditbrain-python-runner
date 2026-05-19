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


async def require_runner_access(
    request: Request, db: Session = Depends(get_db)
) -> None:
    authz = request.headers.get("Authorization", "")
    if authz.lower().startswith("bearer "):
        token = authz.split(" ", 1)[1].strip()
        user = _user_from_token(token, db)
        if user.role != Role.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El runner está restringido al rol admin.",
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
