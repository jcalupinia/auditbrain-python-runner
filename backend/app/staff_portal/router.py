"""Endpoints /api/v1/staff/clients/{id}/* (gestión de cuentas y dispositivos)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.app.auth import service as auth_service
from backend.app.auth.deps import get_current_user, require_admin
from backend.app.auth.models import Role, User
from backend.app.client_portal import service as cp_service
from backend.app.context.models import Client
from backend.app.db.session import get_db
from backend.app.staff_portal import service as sp_service

router = APIRouter(prefix="/staff/clients", tags=["staff-clients"])


class CreatePortalUserRequest(BaseModel):
    email: EmailStr


class CreatePortalUserResponse(BaseModel):
    user_id: int
    email: str
    temp_password: str
    note: str = "Comparta este password con el cliente por canal seguro. No se vuelve a mostrar."


class ResetPortalPasswordRequest(BaseModel):
    # Clave que asigna el admin. Si es None/ausente, se genera una temporal.
    new_password: str | None = None


class PortalUserOut(BaseModel):
    id: int
    email: str
    is_active: bool
    password_reset_required: bool


class DeviceOut(BaseModel):
    id: int
    device_id: str
    user_agent: str | None
    ip_first_seen: str | None
    is_active: bool
    registered_at: str
    last_seen_at: str


@router.post(
    "/{client_id}/portal-users",
    response_model=CreatePortalUserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_portal_user_endpoint(
    client_id: int,
    payload: CreatePortalUserRequest,
    db: Session = Depends(get_db),
):
    if db.get(Client, client_id) is None:
        raise HTTPException(404, detail="Cliente no existe.")
    try:
        user, temp = cp_service.create_portal_user(
            db, client_id=client_id, email=payload.email
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return CreatePortalUserResponse(
        user_id=user.id, email=user.email, temp_password=temp
    )


@router.get(
    "/{client_id}/portal-users",
    response_model=list[PortalUserOut],
    dependencies=[Depends(require_admin)],
)
def list_portal_users_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
):
    users = sp_service.list_portal_users(db, client_id=client_id)
    return [PortalUserOut(
        id=u.id, email=u.email, is_active=u.is_active,
        password_reset_required=u.password_reset_required,
    ) for u in users]


@router.post(
    "/{client_id}/portal-users/{user_id}/disable",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def disable_portal_user_endpoint(
    client_id: int, user_id: int, db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404, detail="Usuario no encontrado para este cliente.")
    sp_service.disable_portal_user(db, user=user)
    return {"ok": True}


@router.post(
    "/{client_id}/portal-users/{user_id}/enable",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def enable_portal_user_endpoint(
    client_id: int, user_id: int, db: Session = Depends(get_db)
):
    """Vuelve a habilitar un usuario de portal dado de baja."""
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404, detail="Usuario no encontrado para este cliente.")
    sp_service.enable_portal_user(db, user=user)
    return {"ok": True}


@router.post(
    "/{client_id}/portal-users/{user_id}/reset-password",
    response_model=CreatePortalUserResponse,
    dependencies=[Depends(require_admin)],
)
def reset_portal_user_password_endpoint(
    client_id: int,
    user_id: int,
    body: ResetPortalPasswordRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    """Resetea la clave de un usuario de portal cliente. El admin puede ENVIAR la
    nueva clave (``new_password``); si no, se genera una temporal aleatoria.
    Devuelve la clave en claro una sola vez."""
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404, detail="Usuario no encontrado para este cliente.")
    np = body.new_password if body else None
    try:
        temp = cp_service.reset_portal_user_password(db, user=user, new_password=np)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CreatePortalUserResponse(
        user_id=user.id, email=user.email, temp_password=temp
    )


@router.delete(
    "/{client_id}/portal-users/{user_id}",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def delete_portal_user_endpoint(
    client_id: int, user_id: int, db: Session = Depends(get_db)
):
    """Borra DEFINITIVAMENTE un usuario de portal cliente y sus datos asociados."""
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404, detail="Usuario no encontrado para este cliente.")
    deleted_email = user.email
    auth_service.delete_user_completely(db, user=user)
    return {"ok": True, "deleted": deleted_email}


@router.get(
    "/{client_id}/portal-users/{user_id}/devices",
    response_model=list[DeviceOut],
    dependencies=[Depends(require_admin)],
)
def list_devices_endpoint(
    client_id: int, user_id: int,
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404)
    devices = sp_service.list_devices(db, user_id=user_id)
    return [DeviceOut(
        id=d.id, device_id=d.device_id, user_agent=d.user_agent,
        ip_first_seen=d.ip_first_seen, is_active=d.is_active,
        registered_at=d.registered_at.isoformat(),
        last_seen_at=d.last_seen_at.isoformat(),
    ) for d in devices]


@router.post(
    "/{client_id}/portal-users/{user_id}/reset-device",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def reset_device_endpoint(
    client_id: int, user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404)
    count = sp_service.reset_all_devices(db, user=user, revoked_by=admin)
    return {"ok": True, "devices_revoked": count}


@router.post(
    "/{client_id}/portal-users/{user_id}/force-logout",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def force_logout_endpoint(
    client_id: int, user_id: int, db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404)
    sp_service.force_logout(db, user=user)
    return {"ok": True}


# ===========================================================================
# Gestión GLOBAL de cuentas de portal (sin depender de client_id):
# carga masiva (licencias) + listado + disable/enable/reset/borrar por user_id.
# Prefijo /staff/portal-users.
# ===========================================================================
global_router = APIRouter(prefix="/staff", tags=["staff-portal-global"])


def _require_portal_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or user.role != Role.client:
        raise HTTPException(404, detail="Cuenta de portal (cliente) no encontrada.")
    return user


@global_router.post(
    "/portal-users/bulk",
    dependencies=[Depends(require_admin)],
)
async def bulk_create_portal_users_endpoint(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Carga masiva de cuentas de portal desde un Excel (CLIENTE | RUC | Email
    Contador). Crea UNA cuenta por correo único; omite correos inválidos;
    no duplica los ya existentes. Devuelve la lista de creados con su clave
    temporal (mostrar una sola vez)."""
    data = await file.read()
    try:
        rows = sp_service.parse_clients_workbook(data)
    except Exception as e:  # archivo corrupto / no es xlsx
        raise HTTPException(400, detail=f"No se pudo leer el Excel: {e}")
    if not rows:
        raise HTTPException(400, detail="El Excel no tiene filas de clientes.")
    res = sp_service.bulk_create_portal_clients(
        db, organization_id=admin.organization_id, rows=rows
    )
    res["resumen"] = {
        "total_filas": len(rows),
        "creados": len(res["creados"]),
        "omitidos": len(res["omitidos"]),
        "existentes": len(res["existentes"]),
    }
    return res


@global_router.get(
    "/portal-users",
    response_model=list[dict],
    dependencies=[Depends(require_admin)],
)
def list_all_portal_users_endpoint(db: Session = Depends(get_db)):
    return sp_service.list_all_portal_users(db)


@global_router.post(
    "/portal-users/{user_id}/disable",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def disable_portal_user_global(user_id: int, db: Session = Depends(get_db)):
    sp_service.disable_portal_user(db, user=_require_portal_user(db, user_id))
    return {"ok": True, "is_active": False}


@global_router.post(
    "/portal-users/{user_id}/enable",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def enable_portal_user_global(user_id: int, db: Session = Depends(get_db)):
    sp_service.enable_portal_user(db, user=_require_portal_user(db, user_id))
    return {"ok": True, "is_active": True}


@global_router.post(
    "/portal-users/{user_id}/reset-password",
    response_model=CreatePortalUserResponse,
    dependencies=[Depends(require_admin)],
)
def reset_portal_user_password_global(
    user_id: int,
    body: ResetPortalPasswordRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    user = _require_portal_user(db, user_id)
    np = body.new_password if body else None
    try:
        temp = cp_service.reset_portal_user_password(db, user=user, new_password=np)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CreatePortalUserResponse(user_id=user.id, email=user.email, temp_password=temp)


@global_router.delete(
    "/portal-users/{user_id}",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def delete_portal_user_global(user_id: int, db: Session = Depends(get_db)):
    user = _require_portal_user(db, user_id)
    deleted_email = user.email
    auth_service.delete_user_completely(db, user=user)
    return {"ok": True, "deleted": deleted_email}
