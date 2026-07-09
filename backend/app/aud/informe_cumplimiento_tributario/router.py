# backend/app/aud/informe_cumplimiento_tributario/router.py
"""Endpoints HTTP del Informe de Cumplimiento Tributario."""

from __future__ import annotations

import json
from io import BytesIO

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.informe_cumplimiento_tributario import jobs, service
from backend.app.aud.informe_cumplimiento_tributario.parsers import (
    declaracion_ir as p_decl,
    informe_auditoria_externa as p_iae,
)
from backend.app.core.config import settings
from backend.app.db.session import get_db

router = APIRouter(
    prefix="/aud/informe-cumplimiento-tributario",
    tags=["aud-informe-cumplimiento-tributario"],
)

FIRMAS_VALIDAS = {"audit_consulting", "partner_auditing"}
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _job_out(job) -> dict:
    return {
        "id": job.id, "project_id": job.project_id, "tool_code": job.tool_code,
        "status": job.status, "cliente_name": job.cliente_name,
        "ejercicio": job.period_label, "firma_auditora": job.firma_auditora,
        "error_message": job.error_message, "summary_json": job.summary_json,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


async def _read_pdf(upload: UploadFile, label: str) -> bytes:
    if upload.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(415, detail=f"{label}: se requiere PDF")
    data = await upload.read()
    if len(data) > settings.AUD_OF_MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, detail=f"{label}: excede {settings.AUD_OF_MAX_FILE_MB} MB")
    return data


@router.post("/parse-preview")
async def parse_preview_endpoint(
    informe_auditoria_externa: UploadFile = File(...),
    declaracion_ir: UploadFile = File(...),
    current: User = Depends(get_current_user),
):
    inf = p_iae.parse(await _read_pdf(informe_auditoria_externa, "Informe Aud. Externa"))
    f101 = p_decl.parse(await _read_pdf(declaracion_ir, "F-101"))
    return JSONResponse({
        "fecha_emision": inf.get("fecha_emision"),
        "marco_contable": inf.get("marco_contable"),
        "fecha_declaracion_ir": f101.get("fecha_declaracion_ir"),
        "warnings": inf.get("errores", []) + f101.get("errores", []),
    })


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job_endpoint(
    background_tasks: BackgroundTasks,
    project_id: int = Form(...),
    cliente_name: str = Form(...),
    ejercicio: str = Form(...),
    firma_auditora: str = Form(...),
    fecha_carga_sri: str = Form(""),
    hay_recomendaciones: bool = Form(False),
    texto_recomendaciones: str = Form(""),
    override_fecha_emision: str = Form(""),
    override_marco_contable: str = Form(""),
    override_fecha_declaracion_ir: str = Form(""),
    informe_auditoria_externa: UploadFile | None = File(None),
    declaracion_ir: UploadFile | None = File(None),
    anexo_diferencias_sri: UploadFile | None = File(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if firma_auditora not in FIRMAS_VALIDAS:
        raise HTTPException(400, detail=f"firma_auditora inválida: {firma_auditora}")
    if not (informe_auditoria_externa and informe_auditoria_externa.filename
            and declaracion_ir and declaracion_ir.filename):
        raise HTTPException(400, detail="Sube el Informe de Auditoría Externa y el F-101.")

    inf_bytes = await _read_pdf(informe_auditoria_externa, "Informe Aud. Externa")
    f101_bytes = await _read_pdf(declaracion_ir, "F-101")

    try:
        job = service.create_job(
            db, user=current, project_id=project_id,
            cliente_name=cliente_name, ejercicio=ejercicio, firma_auditora=firma_auditora,
        )
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    job_dir = file_storage.create_job_dir(job.id)
    file_storage.save_input(job_dir, "informe_auditoria_externa",
                            informe_auditoria_externa.filename, inf_bytes)
    file_storage.save_input(job_dir, "declaracion_ir",
                            declaracion_ir.filename, f101_bytes)
    if anexo_diferencias_sri and anexo_diferencias_sri.filename:
        file_storage.save_input(job_dir, "anexo_diferencias_sri",
                                anexo_diferencias_sri.filename,
                                await _read_pdf(anexo_diferencias_sri, "Anexo Diferencias"))
    file_storage.save_input(job_dir, "params", "params.json", json.dumps({
        "fecha_carga_sri": fecha_carga_sri,
        "hay_recomendaciones": hay_recomendaciones,
        "texto_recomendaciones": texto_recomendaciones,
        "override_fecha_emision": override_fecha_emision,
        "override_marco_contable": override_marco_contable,
        "override_fecha_declaracion_ir": override_fecha_declaracion_ir,
    }).encode("utf-8"))

    background_tasks.add_task(jobs.process_job, job.id)
    return _job_out(job)


@router.get("/jobs/{job_id}")
def get_job_endpoint(job_id: int, current: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    try:
        return _job_out(service.get_job(db, current, job_id))
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))


@router.get("/jobs")
def list_jobs_endpoint(project_id: int, limit: int = 20,
                       current: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    try:
        return [_job_out(j) for j in service.list_jobs_for_project(db, current, project_id, limit=limit)]
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))


@router.get("/jobs/{job_id}/download")
def download_job_endpoint(job_id: int, current: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status != "done":
        raise HTTPException(409, detail=f"Job status={job.status}, no listo")
    out = file_storage.job_dir(job.id) / "output.docx"
    if not out.exists():
        raise HTTPException(410, detail="Informe ya no disponible (expirado).")
    service.mark_downloaded(db, job.id)
    safe = (job.cliente_name or "cliente").replace(" ", "_").replace("/", "_")
    filename = f"Informe_Cumplimiento_Tributario_{safe}_{job.period_label}.docx"
    return StreamingResponse(
        BytesIO(out.read_bytes()), media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_endpoint(job_id: int, current: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    try:
        service.delete_job(db, current, job_id)
        file_storage.delete_job_dir(job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return None
