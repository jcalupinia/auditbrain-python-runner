"""HTTP endpoints for /api/v1/client/ict/*."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_client_with_device
from backend.app.auth.models import User
from backend.app.db.session import get_db
from backend.app.ict import service as ict_service
from backend.app.ict.schemas import (
    AnexoOut,
    CreateSessionRequest,
    SessionOut,
    UpdateSessionRequest,
)

router = APIRouter(prefix="/client/ict", tags=["client-ict"])


def _session_to_out(session) -> SessionOut:
    return SessionOut(
        id=session.id,
        ejercicio_fiscal=session.ejercicio_fiscal,
        ruc=session.ruc,
        razon_social=session.razon_social,
        numero_adhesivo=session.numero_adhesivo,
        status=session.status,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        expires_at=session.expires_at,
        anexos=[
            AnexoOut(
                anexo_code=a.anexo_code,
                status=a.status,
                warnings=a.warnings or [],
                uploaded_files=a.uploaded_files or {},
                last_updated_at=a.last_updated_at,
            )
            for a in session.anexos
        ],
    )


@router.post(
    "/sessions",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_session_endpoint(
    payload: CreateSessionRequest,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    session = ict_service.create_session(
        db,
        user=user,
        ejercicio_fiscal=payload.ejercicio_fiscal,
        ruc=payload.ruc,
        razon_social=payload.razon_social,
        numero_adhesivo=payload.numero_adhesivo,
    )
    return _session_to_out(session)


@router.get("/sessions/active", response_model=SessionOut)
def get_active_session_endpoint(
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    session = ict_service.get_active_session(db, user=user)
    if session is None:
        raise HTTPException(404, detail="No hay sesión activa")
    return _session_to_out(session)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session_endpoint(
    session_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return _session_to_out(session)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session_endpoint(
    session_id: int,
    payload: UpdateSessionRequest,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    updated = ict_service.update_session(
        db, session=session,
        ruc=payload.ruc, razon_social=payload.razon_social,
        numero_adhesivo=payload.numero_adhesivo,
    )
    return _session_to_out(updated)


@router.delete("/sessions/{session_id}", status_code=200)
def delete_session_endpoint(
    session_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    ict_service.expire_session(db, session=session)
    return {"ok": True}
