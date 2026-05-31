"""HTTP endpoints for /api/v1/client/ict/*."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from backend.app.ict.parsers.f101_pdf import parse_f101
from backend.app.ict.parsers.balance_excel import parse_balance
from backend.app.ict.parsers.kardex_excel import parse_kardex
from backend.app.ict.parsers.f104_pdf import parse_f104
from backend.app.ict.parsers.facturacion_sri import parse_facturacion
from backend.app.ict.parsers.mayor_excel import parse_mayor

SLOT_PARSERS = {
    "f101": parse_f101,
    "balance": parse_balance,
    "kardex": parse_kardex,
    "f104": parse_f104,
    "facturacion": parse_facturacion,
    "mayor_exentos": parse_mayor,          # Libro Mayor de cuentas exentas (A4 Cuadro 1)
    "mayor_no_deducibles": parse_mayor,    # Libro Mayor de cuentas no deducibles (A5 Cuadro A)
}

ANEXO_REQUIRED_SLOTS = {
    "A1": ["f101", "balance"],
    "A2": ["f104", "facturacion"],
    "A3": ["f101"],
    "A4": ["f101"],          # mayor_exentos is optional (Cuadro 1 detail)
    "A5": ["f101", "mayor_no_deducibles"],  # mayor_no_deducibles required (Cuadro A detail)
    "A6": ["f101"],          # contratos_inversion + exoneraciones are optional manual data
    "A7": ["f101"],          # f101_multiyear + f108_multiyear are optional multi-year uploads
    "A9": ["f101"],
}
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
    UploadResponse,
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


@router.get("/sessions/{session_id}/download")
def download_excel_endpoint(
    session_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    excel_bytes = ict_service.generate_excel(db, session=session)
    filename = f"ICT_{session.ejercicio_fiscal}_{session.ruc}.xlsx"
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/sessions/{session_id}/anexos/{anexo_code}/upload",
    response_model=UploadResponse,
)
async def upload_for_anexo_endpoint(
    session_id: int,
    anexo_code: str,
    slot_name: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    if session.status != "in_progress":
        raise HTTPException(410, detail=f"Sesión está {session.status}")

    parser = SLOT_PARSERS.get(slot_name)
    if parser is None:
        raise HTTPException(400, detail=f"Slot '{slot_name}' no soportado")

    data = await file.read()
    MAX_SIZE = 50 * 1024 * 1024
    if len(data) > MAX_SIZE:
        raise HTTPException(413, detail="Archivo excede 50 MB")

    parsed = parser(data)
    if parsed.get("errores"):
        anexo = ict_service.update_anexo_data(
            db, session=session, anexo_code=anexo_code,
            extracted_data={}, warnings=parsed["errores"],
            uploaded_file_meta={"slot": slot_name, "filename": file.filename, "size": len(data)},
            new_status="error",
        )
        return UploadResponse(
            anexo_code=anexo_code, status=anexo.status,
            warnings=anexo.warnings or [],
            filename=file.filename, size_bytes=len(data),
        )

    ict_service.save_uploaded_file(
        session_id=session_id, anexo_code=anexo_code,
        slot_name=slot_name, filename=file.filename, data=data,
    )

    if slot_name == "f101":
        extracted = {"f101": parsed["casilleros"]}
    elif slot_name == "balance":
        extracted = {"balance": parsed["cuentas"]}
    elif slot_name == "kardex":
        extracted = {"kardex_items": parsed["items"]}
    elif slot_name == "f104":
        # F-104 uploads one month at a time; accumulate into f104_monthly dict
        existing_anexo = next((a for a in session.anexos if a.anexo_code == anexo_code), None)
        existing_data = (existing_anexo.extracted_data if existing_anexo else None) or {}
        monthly: dict = dict(existing_data.get("f104_monthly") or {})
        periodo = parsed.get("periodo") if parsed else None
        if periodo:
            # Key by the month portion: "01/2025" → "01"
            mes_key = periodo.split("/")[0].strip() if "/" in str(periodo) else str(periodo).strip()
            monthly[mes_key] = parsed
        extracted = {"f104_monthly": monthly}
    elif slot_name == "facturacion":
        extracted = {"facturacion": parsed}
    elif slot_name == "mayor_exentos":
        extracted = {"mayor_exentos": parsed.get("movimientos", [])}
    elif slot_name == "mayor_no_deducibles":
        extracted = {"mayor_no_deducibles": parsed.get("movimientos", [])}
    else:
        extracted = {slot_name: parsed}

    required = ANEXO_REQUIRED_SLOTS.get(anexo_code, [])
    existing_anexo = next((a for a in session.anexos if a.anexo_code == anexo_code), None)
    existing_files = (existing_anexo.uploaded_files if existing_anexo else None) or {}
    new_files_keys = set(existing_files.keys()) | {slot_name}
    new_status = "ready" if all(s in new_files_keys for s in required) else "partial"

    anexo = ict_service.update_anexo_data(
        db, session=session, anexo_code=anexo_code,
        extracted_data=extracted, warnings=parsed.get("errores", []),
        uploaded_file_meta={"slot": slot_name, "filename": file.filename, "size": len(data)},
        new_status=new_status,
    )
    ict_service.recompute_indice(db, session=session)

    return UploadResponse(
        anexo_code=anexo_code, status=anexo.status,
        warnings=anexo.warnings or [],
        filename=file.filename, size_bytes=len(data),
    )


@router.delete(
    "/sessions/{session_id}/anexos/{anexo_code}/upload/{slot_name}",
    status_code=200,
)
def reset_slot_endpoint(
    session_id: int,
    anexo_code: str,
    slot_name: str,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    try:
        anexo = ict_service.reset_anexo_slot(
            db, session=session, anexo_code=anexo_code, slot_name=slot_name
        )
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    ict_service.recompute_indice(db, session=session)
    return {"anexo_code": anexo_code, "status": anexo.status}


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
