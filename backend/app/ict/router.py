"""HTTP endpoints for /api/v1/client/ict/*."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from backend.app.ict.parsers.f101_pdf import parse_f101
from backend.app.ict.parsers.balance_mapeado_excel import parse_balance_mapeado
from backend.app.ict.parsers.kardex_excel import parse_kardex
from backend.app.ict.parsers.f104_pdf import parse_f104
from backend.app.ict.parsers.f103_pdf import parse_f103
from backend.app.ict.parsers.facturacion_sri import parse_facturacion
from backend.app.ict.parsers.mayor_excel import parse_mayor
from backend.app.ict.parsers.ats_xml import parse_ats

SLOT_PARSERS = {
    # ----- Documentos PRINCIPALES (visibles en la barra del portal cliente) -----
    "f101": parse_f101,                     # Declaración anual IR Sociedades (1 PDF)
    "balance_mapeado": parse_balance_mapeado,  # Balance Mapeado con casillero SRI (1 Excel)
    "f104": parse_f104,                     # Declaraciones mensuales IVA (12 PDFs)
    "f103": parse_f103,                     # Declaraciones mensuales Retenciones IR (12 PDFs)
    # ----- Documentos OPCIONALES (ocultos en UI, soportados si se suben por flujo legacy) -----
    "kardex": parse_kardex,                 # Detalle de inventarios (A9 Cuadro 2)
    "facturacion": parse_facturacion,       # Reporte Facturación SRI (refuerzo A2)
    "mayor_exentos": parse_mayor,           # Libro Mayor cuentas exentas (A4 Cuadro 1 detalle)
    "mayor_no_deducibles": parse_mayor,     # Libro Mayor no deducibles (A5 Cuadro A detalle)
    "ats": parse_ats,                       # ATS XML SRI (refuerzo A8 con detalle por proveedor)
}

# Cada anexo declara qué slots NECESITA para marcarse como "ready". El
# orquestador (generate_excel) ya hace shared_context: si F-101 y Balance
# se subieron a A1, otros anexos pueden leerlos. Los slots adicionales
# (mayor, ats, kardex) aportan detalle pero no son críticos.
ANEXO_REQUIRED_SLOTS = {
    "A1": ["f101", "balance_mapeado"],
    "A2": ["f101", "f104"],                # IVA anual via 12 F-104 + ingresos F-101
    "A3": ["f101"],
    "A4": ["f101"],
    "A5": ["f101", "f103"],                # retenciones F-103 valida no deducibles
    "A6": ["f101"],
    "A7": ["f101", "f103"],                # retenciones efectuadas dan crédito tributario
    "A8": ["f103"],                        # pagos exterior con/sin CDI + paraísos
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
    FileResult,
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


@router.post("/sessions/{session_id}/process", status_code=200)
def process_session_endpoint(
    session_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Ejecuta el procesamiento completo de los 10 anexos.

    Promueve los anexos con datos disponibles vía shared_context a
    status="ready"/"partial", pre-genera el Excel ICT y lo cachea en disco
    para descarga subsiguiente instantánea.

    Devuelve JSON con resultado por anexo + bandera excel_ready.

    NOTA: ANTES de procesar, re-parsea los archivos guardados con la
    versión actual del parser. Esto garantiza que cuando se mejora un
    parser (ej. más casilleros del F-101), las sesiones existentes se
    benefician sin necesidad de re-subir archivos.
    """
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    # Re-parsear primero — si el parser se actualizó desde la última
    # vez que el cliente subió archivos, esto recupera los casilleros
    # nuevos. Si no hay archivos guardados, no hace nada.
    try:
        ict_service.reparse_session_uploads(db, session=session)
        # Refrescar la sesión por si reparse cambió relaciones
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except Exception:
        import logging
        logging.exception("reparse_session_uploads falló para sesión %s, continúo con datos cacheados", session_id)
    return ict_service.process_session(db, session=session)


@router.post("/sessions/{session_id}/reparse", status_code=200)
def reparse_session_endpoint(
    session_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Re-parsea TODOS los archivos guardados de la sesión con la versión
    actual del parser, sin que el cliente tenga que re-subirlos.

    Útil después de un deploy que mejoró un parser (más casilleros,
    regex más robusta, nuevos formatos soportados). El cliente ve
    inmediatamente los datos nuevos en su próxima generación de Excel.

    Devuelve {session_id, anexos: {code: {slot: {archivos, items}}}}.
    """
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if session.status != "in_progress":
        raise HTTPException(410, detail=f"Sesión está {session.status}")
    return ict_service.reparse_session_uploads(db, session=session)


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

    # Si /process pre-generó el Excel SRI, sírvelo del cache (instantáneo).
    # Sino lo generamos al vuelo y tomamos solo el bytes_sri.
    # Regla CLAUDE.md: este endpoint devuelve SOLO el Excel limpio para SRI
    # (sin VERIFICACIÓN A1, AUDITORÍA DE ANEXOS, TRAZABILIDAD).
    from backend.app.aud.obligaciones_fiscales import file_storage as _fs
    cached_sri = _fs._root() / "ict" / f"{session.id}" / "_output" / "ICT_SRI.xlsx"
    legacy_cached = _fs._root() / "ict" / f"{session.id}" / "_output" / "ICT.xlsx"
    if cached_sri.exists():
        excel_bytes = cached_sri.read_bytes()
    elif legacy_cached.exists():
        # Compatibilidad con sesiones generadas antes del split (PT-9).
        excel_bytes = legacy_cached.read_bytes()
    else:
        excel_bytes, _ = ict_service.generate_excel(db, session=session)

    filename = f"ICT_{session.ejercicio_fiscal}_{session.ruc}_SRI.xlsx"
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/sessions/{session_id}/papel-trabajo",
    summary="Descarga papel de trabajo del auditor",
    description=(
        "Devuelve el archivo Excel COMPLETO incluyendo VERIFICACIÓN A1, "
        "AUDITORÍA DE ANEXOS, TRAZABILIDAD y la interpretación generada por "
        "IA. Este archivo es para uso interno del auditor — NO debe cargarse "
        "al SRI."
    ),
)
def download_papel_trabajo_endpoint(
    session_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Devuelve el Excel PAPEL DE TRABAJO con todas las hojas internas.

    Regla CLAUDE.md (interpretación IA): este archivo contiene resultados
    generados por LLM con disclaimer obligatorio. El auditor responsable
    debe validar antes de cualquier decisión.
    """
    try:
        session = ict_service.get_session(db, session_id=session_id, user=user)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))

    from backend.app.aud.obligaciones_fiscales import file_storage as _fs
    cached_papel = (
        _fs._root() / "ict" / f"{session.id}" / "_output" / "ICT_PAPEL_TRABAJO.xlsx"
    )
    if cached_papel.exists():
        excel_bytes = cached_papel.read_bytes()
    else:
        # Generar al vuelo si no hay cache (sesiones pre-PT-9 también caen acá).
        _sri, excel_bytes = ict_service.generate_excel(db, session=session)

    filename = (
        f"ICT_{session.ejercicio_fiscal}_{session.ruc}_PAPEL_TRABAJO.xlsx"
    )
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
    files: list[UploadFile] = File(...),  # lista; un solo archivo = lista de 1 (backward compat)
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

    MAX_SIZE = 50 * 1024 * 1024
    IS_MULTI = slot_name == "f104"  # solo f104 acumula por mes; el resto toma el primer archivo

    # Para f104 necesitamos el estado previo al iniciar el loop
    existing_anexo = next((a for a in session.anexos if a.anexo_code == anexo_code), None)
    existing_data = (existing_anexo.extracted_data if existing_anexo else None) or {}
    monthly: dict = dict(existing_data.get("f104_monthly") or {}) if IS_MULTI else {}

    total_bytes = 0
    warnings_acc: list[str] = []
    per_file_results: list[FileResult] = []
    last_extracted: dict = {}
    last_filename: str = files[0].filename if files else "archivo"
    last_size: int = 0

    for upload in files:
        data = await upload.read()
        if len(data) > MAX_SIZE:
            raise HTTPException(413, detail=f"Archivo {upload.filename} excede 50 MB")
        total_bytes += len(data)

        parsed = parser(data)

        if parsed.get("errores"):
            warnings_acc.extend([f"{upload.filename}: {e}" for e in parsed["errores"]])
            per_file_results.append(FileResult(
                filename=upload.filename,
                status="error",
                errores=parsed["errores"],
            ))
            # Para slots no-multi, un error en el único archivo es error total
            if not IS_MULTI:
                anexo = ict_service.update_anexo_data(
                    db, session=session, anexo_code=anexo_code,
                    extracted_data={}, warnings=parsed["errores"],
                    uploaded_file_meta={"slot": slot_name, "filename": upload.filename, "size": len(data)},
                    new_status="error",
                )
                return UploadResponse(
                    anexo_code=anexo_code, status=anexo.status,
                    warnings=anexo.warnings or [],
                    filename=upload.filename, size_bytes=len(data),
                    files_processed=0,
                    per_file=per_file_results,
                )
            continue  # para f104: seguir con los demás aunque uno falle

        ict_service.save_uploaded_file(
            session_id=session_id, anexo_code=anexo_code,
            slot_name=slot_name, filename=upload.filename, data=data,
        )

        last_filename = upload.filename
        last_size = len(data)

        if IS_MULTI:
            # f104: acumular por mes
            periodo = parsed.get("periodo")
            if periodo:
                mes_key = periodo.split("/")[0].strip() if "/" in str(periodo) else str(periodo).strip()
                monthly[mes_key] = parsed
                per_file_results.append(FileResult(
                    filename=upload.filename,
                    status="ok",
                    periodo=str(periodo),
                    casilleros_found=len(parsed.get("casilleros", {})),
                ))
            else:
                warnings_acc.append(f"{upload.filename}: no se detectó período")
                per_file_results.append(FileResult(
                    filename=upload.filename,
                    status="warning",
                    message="no se detectó período",
                ))
            last_extracted = {"f104_monthly": monthly}
        else:
            # Slots de un solo archivo: construir extracted y salir al terminar el primero
            if slot_name == "f101":
                last_extracted = {"f101": parsed["casilleros"]}
            elif slot_name == "balance_mapeado":
                last_extracted = {"balance_mapeado": parsed.get("cuentas", [])}
            elif slot_name == "kardex":
                last_extracted = {"kardex_items": parsed["items"]}
            elif slot_name == "facturacion":
                last_extracted = {"facturacion": parsed}
            elif slot_name == "mayor_exentos":
                last_extracted = {"mayor_exentos": parsed.get("movimientos", [])}
            elif slot_name == "mayor_no_deducibles":
                last_extracted = {"mayor_no_deducibles": parsed.get("movimientos", [])}
            elif slot_name == "ats":
                last_extracted = {"ats_pagos_exterior": parsed.get("pagos_exterior", [])}
            else:
                last_extracted = {slot_name: parsed}
            per_file_results.append(FileResult(filename=upload.filename, status="ok"))
            break  # slots de un solo archivo: solo procesar el primero

    # Si no se procesó ningún archivo con éxito
    if not last_extracted and not IS_MULTI:
        # Todos fallaron (solo llega aquí si hubo error y ya se retornó arriba)
        return UploadResponse(
            anexo_code=anexo_code, status="error",
            warnings=warnings_acc,
            filename=last_filename, size_bytes=total_bytes,
            files_processed=0,
            per_file=per_file_results,
        )

    if IS_MULTI:
        last_extracted = {"f104_monthly": monthly}
        # Nombre descriptivo para el meta: "f104_01.pdf" si 1, "3 archivos" si varios
        ok_count = sum(1 for r in per_file_results if r.status == "ok")
        meta_filename = last_filename if ok_count == 1 else f"{ok_count} archivos F-104"
        meta_size = total_bytes
    else:
        meta_filename = last_filename
        meta_size = last_size

    # Calcular nuevo estado del anexo
    required = ANEXO_REQUIRED_SLOTS.get(anexo_code, [])
    # Refrescar existing_anexo porque puede haber sido actualizado durante el loop
    existing_anexo = next((a for a in session.anexos if a.anexo_code == anexo_code), None)
    existing_files = (existing_anexo.uploaded_files if existing_anexo else None) or {}
    new_files_keys = set(existing_files.keys()) | {slot_name}
    new_status = "ready" if all(s in new_files_keys for s in required) else "partial"

    anexo = ict_service.update_anexo_data(
        db, session=session, anexo_code=anexo_code,
        extracted_data=last_extracted,
        warnings=warnings_acc,
        uploaded_file_meta={"slot": slot_name, "filename": meta_filename, "size": meta_size},
        new_status=new_status,
    )
    ict_service.recompute_indice(db, session=session)

    files_ok = sum(1 for r in per_file_results if r.status == "ok")
    first_filename = per_file_results[0].filename if per_file_results else last_filename

    return UploadResponse(
        anexo_code=anexo_code, status=anexo.status,
        warnings=anexo.warnings or [],
        filename=first_filename,
        size_bytes=total_bytes,
        files_processed=files_ok,
        per_file=per_file_results,
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
