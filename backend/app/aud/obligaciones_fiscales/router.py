"""Endpoints HTTP de AUD.IMPUESTOS.OBLIGACIONES_FISCALES."""

from __future__ import annotations

import datetime
from io import BytesIO

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.aud.obligaciones_fiscales import (
    file_storage,
    jobs,
    service,
)
from backend.app.aud.obligaciones_fiscales.schemas import JobOut
from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(
    prefix="/aud/obligaciones-fiscales",
    tags=["aud-obligaciones-fiscales"],
)


ALLOWED_MIMES = {
    "f103": {"application/pdf"},
    "f104": {"application/pdf"},
    "f101": {"application/pdf"},
    "ats": {"application/xml", "text/xml"},
    "mayor_compras": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    },
    "mayor_ventas": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    },
}


async def _save_files(job_dir, slot: str, files: list[UploadFile]) -> int:
    """Valida + persiste a /tmp. Devuelve count guardado."""
    allowed = ALLOWED_MIMES.get(slot, set())
    max_bytes = settings.AUD_OF_MAX_FILE_MB * 1024 * 1024
    count = 0
    for f in files:
        if not f.filename:
            continue
        if allowed and f.content_type not in allowed:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"{f.filename}: tipo {f.content_type} no permitido para slot {slot}",
            )
        data = await f.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{f.filename}: excede {settings.AUD_OF_MAX_FILE_MB} MB",
            )
        file_storage.save_input(job_dir, slot, f.filename, data)
        count += 1
    return count


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job_endpoint(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    cliente_name: str = Form(...),
    period_label: str = Form(...),
    period_start: datetime.date | None = Form(None),
    period_end: datetime.date | None = Form(None),
    prepared_by_name: str | None = Form(None),
    reviewed_by_name: str | None = Form(None),
    firma_auditora: str | None = Form(None),
    files_f103: list[UploadFile] = File(default=[]),
    files_f104: list[UploadFile] = File(default=[]),
    files_ats: list[UploadFile] = File(default=[]),
    mayor_compras: UploadFile | None = File(None),
    mayor_ventas: UploadFile | None = File(None),
    file_f101: UploadFile | None = File(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    has_any = (
        (files_f103 and any(f.filename for f in files_f103))
        or (files_f104 and any(f.filename for f in files_f104))
    )
    if not has_any:
        raise HTTPException(400, detail="Sube al menos 1 PDF F-103 o F-104.")

    # Validar firma_auditora si viene
    from backend.app.aud.obligaciones_fiscales.schemas import FIRMAS_VALIDAS
    if firma_auditora and firma_auditora not in FIRMAS_VALIDAS:
        raise HTTPException(
            400,
            detail=f"firma_auditora debe ser uno de: {sorted(FIRMAS_VALIDAS)}",
        )

    try:
        job = service.create_job(
            db, user=current, project_id=project_id,
            cliente_name=cliente_name, period_label=period_label,
            period_start=period_start, period_end=period_end,
            prepared_by_name=prepared_by_name, reviewed_by_name=reviewed_by_name,
            firma_auditora=firma_auditora,
        )
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    job_dir = file_storage.create_job_dir(job.id)
    try:
        if files_f103:
            await _save_files(job_dir, "f103", files_f103)
        if files_f104:
            await _save_files(job_dir, "f104", files_f104)
        if files_ats:
            await _save_files(job_dir, "ats", files_ats)
        if mayor_compras and mayor_compras.filename:
            await _save_files(job_dir, "mayor_compras", [mayor_compras])
        if mayor_ventas and mayor_ventas.filename:
            await _save_files(job_dir, "mayor_ventas", [mayor_ventas])
        if file_f101 and file_f101.filename:
            await _save_files(job_dir, "f101", [file_f101])
    except HTTPException:
        # Si la validación de archivos falla, limpia y elimina el job
        file_storage.delete_job_dir(job.id)
        db.delete(job)
        db.commit()
        raise

    background_tasks.add_task(jobs.process_job, job.id)
    return JobOut.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return JobOut.model_validate(job)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs_endpoint(
    project_id: int,
    limit: int = 20,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        items = service.list_jobs_for_project(db, current, project_id, limit=limit)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return [JobOut.model_validate(i) for i in items]


@router.get("/jobs/{job_id}/download")
def download_job_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status != "done":
        raise HTTPException(
            409, detail=f"Job status={job.status}, no listo para descarga"
        )
    out_path = file_storage.output_path(file_storage.job_dir(job.id))
    if not out_path.exists():
        raise HTTPException(410, detail="Excel ya no disponible (expirado).")
    service.mark_downloaded(db, job.id)
    safe_cliente = (job.cliente_name or "cliente").replace(" ", "_").replace("/", "_")
    safe_periodo = (job.period_label or "").replace(" ", "_").replace("/", "_")
    filename = f"DM_Obligaciones_Fiscales_{safe_cliente}_{safe_periodo}.xlsx"
    return StreamingResponse(
        BytesIO(out_path.read_bytes()),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.delete_job(db, current, job_id)
        file_storage.delete_job_dir(job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return None
