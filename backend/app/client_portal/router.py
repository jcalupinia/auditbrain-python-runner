"""Endpoints /api/v1/client/* (autenticación + perfil)."""

from __future__ import annotations

import os
from io import BytesIO

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.obligaciones_fiscales.schemas import JobOut
from backend.app.auth import device as device_mod
from backend.app.auth.deps import require_client_with_device
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import ClientDevice, User
from backend.app.auth.service import start_new_session, invalidate_session
from backend.app.client_portal import jobs as cp_jobs
from backend.app.client_portal import service as cp_service
from backend.app.client_portal.schemas import (
    CategoryOut,
    ChangePasswordRequest,
    ClientCatalogResponse,
    ClientLoginResponse,
    ClientMeResponse,
    SlotOut,
    ToolOut,
)
from backend.app.client_portal.rate_limit import check_and_record
from backend.app.client_portal.tool_registry import CATEGORIES, get_tool, list_enabled_tools
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
    # Rate limit: 5 intentos / 15 min por IP+email
    ip = request.client.host if request.client else "unknown"
    rl_key = f"login:{ip}:{form.username.lower()}"
    if not check_and_record(rl_key, max_hits=5, window_seconds=900):
        raise HTTPException(
            429,
            detail="Demasiados intentos. Espere 15 minutos o contacte a soporte.",
        )

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


MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB per file


@router.post(
    "/tools/{tool_code}/jobs",
    response_model=JobOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_client_job_endpoint(
    tool_code: str,
    background_tasks: BackgroundTasks,
    request: Request,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Recibe multipart con un campo de archivo por slot.
    Valida MIMEs según el tool registrado, guarda en /tmp, crea ToolJob,
    lanza BackgroundTask.
    """
    try:
        tool = get_tool(tool_code)
    except KeyError:
        raise HTTPException(404, detail=f"Tool {tool_code} no existe.")

    # Parsear multipart manualmente para soportar slots dinámicos
    form = await request.form()

    # Validar cada slot
    files_by_slot: dict[str, list[UploadFile]] = {}
    for slot_name, slot_cfg in tool.slots.items():
        items = form.getlist(slot_name)
        upload_files = [f for f in items if isinstance(f, (UploadFile, StarletteUploadFile))]
        if slot_cfg.required and not upload_files:
            raise HTTPException(
                400, detail=f"Falta archivo obligatorio para slot '{slot_name}'."
            )
        for f in upload_files:
            if f.content_type not in slot_cfg.mimes_allowed:
                raise HTTPException(
                    415,
                    detail=(
                        f"Slot '{slot_name}': MIME '{f.content_type}' no permitido. "
                        f"Esperado: {sorted(slot_cfg.mimes_allowed)}"
                    ),
                )
        if not slot_cfg.multi and len(upload_files) > 1:
            raise HTTPException(
                400, detail=f"Slot '{slot_name}' acepta máximo 1 archivo."
            )
        files_by_slot[slot_name] = upload_files

    # Crear job (verifica que no haya otro activo)
    try:
        job = cp_service.create_client_job(db, user=user, tool_code=tool_code)
    except PermissionError as e:
        raise HTTPException(409, detail=str(e))

    # Guardar archivos
    job_dir = file_storage.create_job_dir(job.id)
    try:
        for slot_name, files in files_by_slot.items():
            for f in files:
                data = await f.read()
                if len(data) > MAX_FILE_BYTES:
                    raise HTTPException(
                        413,
                        detail=f"Archivo {f.filename} excede {MAX_FILE_BYTES // (1024*1024)} MB",
                    )
                file_storage.save_input(job_dir, slot_name, f.filename or "file", data)
    except HTTPException:
        file_storage.delete_job_dir(job.id)
        db.delete(job)
        db.commit()
        raise

    background_tasks.add_task(cp_jobs.process_tool_job, job.id)
    return JobOut.model_validate(job)


@router.get("/tools/jobs/{job_id}", response_model=JobOut)
def get_client_job_endpoint(
    job_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        job = cp_service.get_client_job(db, user=user, job_id=job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return JobOut.model_validate(job)


@router.get("/tools/jobs/{job_id}/download")
def download_client_job_endpoint(
    job_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        job = cp_service.get_client_job(db, user=user, job_id=job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status not in ("done", "error_partial"):
        raise HTTPException(409, detail=f"Job status={job.status}, no listo para descarga")
    out_path = file_storage.output_path(file_storage.job_dir(job.id))
    if not out_path.exists():
        raise HTTPException(410, detail="Archivo expirado (>24h). Reprocese.")
    filename = f"{job.tool_code}_{job.id}.bin"
    return StreamingResponse(
        BytesIO(out_path.read_bytes()),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/tools/jobs", response_model=list[JobOut])
def list_client_jobs_endpoint(
    status: str | None = None,
    limit: int = 20,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    from backend.app.aud.obligaciones_fiscales.models import ToolJob as _ToolJob
    q = select(_ToolJob).where(_ToolJob.user_id == user.id)
    if status:
        q = q.where(_ToolJob.status == status)
    q = q.order_by(_ToolJob.created_at.desc()).limit(limit)
    return [JobOut.model_validate(j) for j in db.execute(q).scalars()]


@router.get("/catalog", response_model=ClientCatalogResponse)
def get_catalog(
    _: User = Depends(require_client_with_device),
):
    """Catálogo de herramientas habilitadas para el cliente.
    Por ahora retorna TODAS las tools habilitadas. Filtrado por organización
    es upgrade futuro (gating comercial).
    """
    tools_by_cat: dict[str, list] = {c["id"]: [] for c in CATEGORIES}
    for t in list_enabled_tools():
        if t.category not in tools_by_cat:
            tools_by_cat[t.category] = []
        slots_out = [
            SlotOut(
                name=name,
                mimes_allowed=sorted(cfg.mimes_allowed),
                required=cfg.required,
                multi=cfg.multi,
            )
            for name, cfg in t.slots.items()
        ]
        tools_by_cat[t.category].append(ToolOut(
            code=t.code, label=t.label, description=t.description,
            category=t.category, slots=slots_out,
        ))
    return ClientCatalogResponse(
        categories=[
            CategoryOut(id=c["id"], label=c["label"], tools=tools_by_cat.get(c["id"], []))
            for c in CATEGORIES
        ]
    )
