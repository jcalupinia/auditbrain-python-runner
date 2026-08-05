"""Endpoints HTTP de AUD.IMPUESTOS.OBLIGACIONES_FISCALES."""

from __future__ import annotations

import datetime
from io import BytesIO

from fastapi import (
    APIRouter,
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
from backend.app.aud.obligaciones_fiscales.schemas import (
    FIRMAS_VALIDAS,
    SLOTS_VALIDOS,
    CorreccionesIn,
    JobOut,
    JobUpdateIn,
)
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
    "mayor_general": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
    },
    "mayor_especifico": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
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
def create_job_endpoint(
    project_id: int = Form(...),
    cliente_name: str = Form(...),
    period_label: str = Form(...),
    period_start: datetime.date | None = Form(None),
    period_end: datetime.date | None = Form(None),
    prepared_by_name: str | None = Form(None),
    reviewed_by_name: str | None = Form(None),
    firma_auditora: str | None = Form(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea el job en estado 'borrador'. Los archivos se suben por slot."""
    if firma_auditora and firma_auditora not in FIRMAS_VALIDAS:
        raise HTTPException(
            400, detail=f"firma_auditora debe ser uno de: {sorted(FIRMAS_VALIDAS)}"
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
    file_storage.create_job_dir(job.id)
    return JobOut.model_validate(job)


def _estado_slots(job_id: int) -> dict[str, dict]:
    d = file_storage.job_dir(job_id)
    estado = {}
    for slot in SLOTS_VALIDOS:
        archivos = file_storage.list_inputs(d, slot)
        estado[slot] = {"n_archivos": len(archivos), "nombres": [p.name for p in archivos]}
    return estado


def _job_editable(db, current, job_id: int):
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status not in ("borrador", "revision"):
        raise HTTPException(
            409, detail=f"El job está en estado {job.status}: ya no admite cambios de archivos."
        )
    return job


@router.put("/jobs/{job_id}/slots/{slot}")
async def upload_slot_endpoint(
    job_id: int,
    slot: str,
    archivos: list[UploadFile] = File(...),
    categoria: str | None = Form(None),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if slot not in SLOTS_VALIDOS:
        raise HTTPException(400, detail=f"Slot desconocido: {slot}")
    job = _job_editable(db, current, job_id)

    if slot == "mayor_especifico" and not categoria:
        raise HTTPException(
            400,
            detail="El mayor específico exige declarar la categoria a la que pertenece.",
        )

    job_dir = file_storage.create_job_dir(job_id)
    await _save_files(job_dir, slot, archivos)

    if slot == "mayor_especifico":
        job.mayor_especifico_categoria = categoria
        db.add(job)
        db.commit()
    return _estado_slots(job_id)


@router.delete("/jobs/{job_id}/slots/{slot}")
def clear_slot_endpoint(
    job_id: int,
    slot: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if slot not in SLOTS_VALIDOS:
        raise HTTPException(400, detail=f"Slot desconocido: {slot}")
    _job_editable(db, current, job_id)
    for p in file_storage.list_inputs(file_storage.job_dir(job_id), slot):
        p.unlink(missing_ok=True)
    return _estado_slots(job_id)


@router.get("/jobs/{job_id}/slots")
def get_slots_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return _estado_slots(job_id)


@router.post("/jobs/{job_id}/procesar", response_model=JobOut)
def procesar_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fase 1: clasifica el Mayor General y deja el job listo para revisión."""
    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status not in ("borrador", "revision", "failed"):
        raise HTTPException(409, detail=f"El job está en estado {job.status}.")
    if not file_storage.list_inputs(file_storage.job_dir(job_id), "mayor_general"):
        raise HTTPException(400, detail="Sube el Mayor General de Impuestos antes de procesar.")

    jobs.clasificar_mayor_job(job_id)
    db.expire_all()
    return JobOut.model_validate(service.get_job(db, current, job_id))


@router.get("/jobs/{job_id}/clasificacion")
def get_clasificacion_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.aud.obligaciones_fiscales.mayor import (
        catalogo_service,
        clasificacion_service,
    )

    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    filas = clasificacion_service.clasificacion_de_job(db, job_id=job_id)
    categorias = catalogo_service.categorias_visibles(
        db, organization_id=getattr(current, "organization_id", None)
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "cuentas": [
            {
                "codigo_cuenta": f.codigo_cuenta,
                "nombre_cuenta": f.nombre_cuenta,
                "n_movimientos": f.n_movimientos,
                "debe": f.debe,
                "haber": f.haber,
                "categoria_sugerida": f.categoria_sugerida,
                "categoria_final": f.categoria_final,
                "tarifa": f.tarifa,
                "confianza": f.confianza,
                "origen": f.origen,
                "corregida": f.corregida,
                "justificacion": [
                    s.get("motivo", "")
                    for s in (f.senales_json or [])
                    if s.get("categoria") == f.categoria_final and s.get("puntaje", 0) > 0
                ],
            }
            for f in filas
        ],
        "categorias": [
            {"codigo": c.codigo, "nombre": c.nombre,
             "naturaleza_esperada": c.naturaleza_esperada}
            for c in categorias
        ],
    }


@router.put("/jobs/{job_id}/clasificacion")
def put_clasificacion_endpoint(
    job_id: int,
    payload: CorreccionesIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.aud.obligaciones_fiscales.mayor import (
        catalogo_service,
        clasificacion_service,
    )

    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status != "revision":
        raise HTTPException(409, detail=f"El job está en estado {job.status}.")

    validas = {
        c.codigo
        for c in catalogo_service.categorias_visibles(
            db, organization_id=getattr(current, "organization_id", None)
        )
    }
    for c in payload.correcciones:
        if c.categoria and c.categoria not in validas:
            raise HTTPException(400, detail=f"Categoría desconocida: {c.categoria}")

    clasificacion_service.aplicar_correcciones(
        db, job_id=job_id,
        correcciones=[c.model_dump() for c in payload.correcciones],
        user_id=current.id,
    )
    return get_clasificacion_endpoint(job_id, current=current, db=db)


@router.post("/jobs/{job_id}/aprobar", response_model=JobOut)
def aprobar_endpoint(
    job_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persiste lo aprendido y dispara la fase 2 (generación del Excel)."""
    from backend.app.aud.obligaciones_fiscales.mayor import (
        clasificacion_service,
        homologaciones,
    )
    from backend.app.context.models import Project

    try:
        job = service.get_job(db, current, job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status != "revision":
        raise HTTPException(
            409, detail=f"El job está en estado {job.status}: no hay nada que aprobar."
        )

    filas = clasificacion_service.clasificacion_de_job(db, job_id=job_id)
    proyecto = db.get(Project, job.project_id)
    homologaciones.guardar_homologaciones(
        db,
        client_id=proyecto.client_id,
        asignaciones=[
            {"codigo_cuenta": f.codigo_cuenta, "nombre_cuenta": f.nombre_cuenta,
             "categoria": f.categoria_final, "tarifa": f.tarifa}
            for f in filas
        ],
        user_id=current.id,
    )

    jobs.process_job(job_id)
    db.expire_all()
    return JobOut.model_validate(service.get_job(db, current, job_id))


@router.get("/categorias")
def list_categorias_endpoint(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.aud.obligaciones_fiscales.mayor import catalogo_service

    return [
        {"codigo": c.codigo, "nombre": c.nombre,
         "naturaleza_esperada": c.naturaleza_esperada, "es_sistema": c.es_sistema}
        for c in catalogo_service.categorias_visibles(
            db, organization_id=getattr(current, "organization_id", None)
        )
    ]


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


@router.patch("/jobs/{job_id}", response_model=JobOut)
def update_job_endpoint(
    job_id: int,
    payload: JobUpdateIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza los metadatos del encargo (cliente, período, corte,
    preparado/revisado por, firma auditora) sin tocar archivos ni
    clasificación. Solo se permite en 'borrador' y 'revision'."""
    _job_editable(db, current, job_id)

    datos = payload.model_dump(exclude_unset=True)
    firma = datos.get("firma_auditora")
    if firma and firma not in FIRMAS_VALIDAS:
        raise HTTPException(
            400, detail=f"firma_auditora debe ser uno de: {sorted(FIRMAS_VALIDAS)}"
        )

    try:
        job = service.update_job(db, current, job_id, **datos)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return JobOut.model_validate(job)


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
