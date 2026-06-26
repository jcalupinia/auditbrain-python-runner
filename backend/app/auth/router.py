"""Endpoints de autenticación (/api/v1/auth/*)."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.app.auth import service
from backend.app.auth.deps import get_current_user, require_admin
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import Role, User
from backend.app.auth.schemas import Token, UserCreate, UserOut
from backend.app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login OAuth2 password flow. ``username`` = email."""
    user = service.authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.email, role=user.role.value)
    return Token(access_token=token, role=user.role)


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current


@router.get("/sri-protection-key", dependencies=[Depends(require_admin)])
def get_sri_protection_key():
    """Devuelve la contraseña que bloquea la estructura del Excel SRI del ICT.

    Solo accesible para rol admin. La clave la conoce únicamente
    AuditConsulting; sirve para des-proteger un Excel SRI si fuera necesario
    (Excel: Revisar → Proteger libro). Sale de la env var
    ICT_SRI_PROTECT_PASSWORD o del default de la firma. Import perezoso de
    ict.service para no acoplar el módulo auth al módulo ict.
    """
    import os
    from backend.app.ict.service import DEFAULT_SRI_PROTECT_PASSWORD

    password = os.getenv("ICT_SRI_PROTECT_PASSWORD", DEFAULT_SRI_PROTECT_PASSWORD)
    return {
        "password": password,
        "scope": "Excel SRI del ICT (estructura del libro bloqueada)",
        "note": (
            "Solo AuditConsulting. Para des-proteger: en Excel, "
            "Revisar → Proteger libro → escribir esta clave."
        ),
    }


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db)):
    """Alta de usuario. Solo admin (no hay self-registration abierto)."""
    if service.get_user_by_email(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email.",
        )
    return service.create_user(
        db, email=payload.email, password=payload.password, role=payload.role
    )


@router.get(
    "/users",
    response_model=list[UserOut],
    dependencies=[Depends(require_admin)],
)
def list_users_endpoint(db: Session = Depends(get_db)):
    """Lista operadores (admin/user) para gestión. Solo admin."""
    return service.list_operators(db)


@router.post(
    "/users/{user_id}/reset-password",
    dependencies=[Depends(require_admin)],
)
def reset_user_password_endpoint(user_id: int, db: Session = Depends(get_db)):
    """Resetea la clave de un operador. Devuelve la clave temporal una sola vez."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    temp = service.reset_user_password(db, user=user)
    return {
        "user_id": user.id,
        "email": user.email,
        "temp_password": temp,
        "note": "Comparta este password por canal seguro. No se vuelve a mostrar.",
    }


@router.post(
    "/users/{user_id}/disable",
    dependencies=[Depends(require_admin)],
)
def disable_user_endpoint(
    user_id: int,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deshabilita (baja reversible) un operador. No permite deshabilitarse a sí
    mismo ni al último administrador activo."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="No puedes deshabilitar tu propia cuenta.")
    if user.role == Role.admin and service.count_active_admins(db) <= 1:
        raise HTTPException(
            status_code=400, detail="No puedes deshabilitar al último administrador activo."
        )
    service.set_user_active(db, user=user, active=False)
    return {"ok": True, "is_active": False}


@router.post(
    "/users/{user_id}/enable",
    dependencies=[Depends(require_admin)],
)
def enable_user_endpoint(user_id: int, db: Session = Depends(get_db)):
    """Vuelve a habilitar un operador dado de baja."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    service.set_user_active(db, user=user, active=True)
    return {"ok": True, "is_active": True}


@router.delete(
    "/users/{user_id}",
    dependencies=[Depends(require_admin)],
)
def delete_user_endpoint(
    user_id: int,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Borra DEFINITIVAMENTE un operador. Solo admin. No permite borrarse a sí
    mismo ni al último administrador activo."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="No puedes borrar tu propia cuenta.")
    if user.role == Role.admin and service.count_active_admins(db) <= 1:
        raise HTTPException(
            status_code=400, detail="No puedes borrar el último administrador activo."
        )
    deleted_email = user.email
    service.delete_user_completely(db, user=user)
    return {"ok": True, "deleted": deleted_email}
