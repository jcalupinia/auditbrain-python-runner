"""Endpoints /api/v1/client/* (autenticación + perfil)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth import device as device_mod
from backend.app.auth.deps import require_client_with_device
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import ClientDevice, User
from backend.app.auth.service import start_new_session, invalidate_session
from backend.app.client_portal import service as cp_service
from backend.app.client_portal.schemas import (
    ChangePasswordRequest,
    ClientLoginResponse,
    ClientMeResponse,
)
from backend.app.db.session import get_db

router = APIRouter(prefix="/client", tags=["client-portal"])

_is_test = os.getenv("PYTEST_CURRENT_TEST") is not None


@router.post("/auth/login", response_model=ClientLoginResponse)
def client_login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    device_id: str | None = Cookie(default=None, alias="device_id"),
    db: Session = Depends(get_db),
):
    user = cp_service.authenticate_portal_user(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    fingerprint = device_mod.compute_fingerprint_hash(
        user_agent=request.headers.get("user-agent", ""),
        accept_language=request.headers.get("accept-language", ""),
        accept_encoding=request.headers.get("accept-encoding", ""),
    )
    ip = request.client.host if request.client else None

    device = None
    if device_id:
        device = device_mod.validate_device(
            db, user=user, device_id=device_id, fingerprint_hash=fingerprint
        )
        if device is None:
            raise HTTPException(
                409,
                detail={
                    "code": "device_unauthorized",
                    "message": (
                        "Este dispositivo no está autorizado para esta cuenta. "
                        "Solicite reseteo a soporte."
                    ),
                },
            )

    if device is None:
        existing = db.execute(
            select(ClientDevice).where(
                ClientDevice.user_id == user.id,
                ClientDevice.is_active.is_(True),
            )
        ).scalars().first()
        if existing:
            raise HTTPException(
                409,
                detail={
                    "code": "device_unauthorized",
                    "message": (
                        "Ya existe un dispositivo registrado para esta cuenta. "
                        "Solicite reseteo a soporte si cambió de equipo."
                    ),
                },
            )
        device = device_mod.register_device(
            db,
            user=user,
            fingerprint_hash=fingerprint,
            user_agent=request.headers.get("user-agent"),
            ip=ip,
        )
        response.set_cookie(
            key="device_id",
            value=device.device_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=not _is_test,
            samesite="lax" if _is_test else "strict",
        )

    sid = start_new_session(db, user=user)
    token = create_access_token(
        subject=user.email,
        role=user.role.value,
        extra_claims={"sid": sid, "did": device.device_id},
    )

    return ClientLoginResponse(
        access_token=token,
        password_reset_required=user.password_reset_required,
    )


@router.post("/auth/change-password", status_code=200)
def change_password_endpoint(
    payload: ChangePasswordRequest,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    if not cp_service.authenticate_portal_user(db, user.email, payload.old_password):
        raise HTTPException(400, detail="La contraseña actual no coincide.")
    try:
        cp_service.change_password(db, user=user, new_password=payload.new_password)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"ok": True}


@router.get("/auth/me", response_model=ClientMeResponse)
def me(user: User = Depends(require_client_with_device)):
    return ClientMeResponse(
        email=user.email,
        client_id=user.client_id,
        organization_id=user.organization_id,
        password_reset_required=user.password_reset_required,
    )


@router.post("/auth/logout", status_code=200)
def logout(
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    invalidate_session(db, user=user)
    return {"ok": True}
