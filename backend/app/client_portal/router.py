"""Endpoints /api/v1/client/* (autenticación + perfil)."""

from __future__ import annotations

import os
from io import BytesIO

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.obligaciones_fiscales.schemas import JobOut
from backend.app.auth import device as device_mod
from backend.app.auth.deps import require_client_with_device, _session_check_enabled
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import ClientDevice, Role, User
from backend.app.auth.service import (
    start_new_session,
    invalidate_session,
    has_active_session,
)
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

    # Sesión única "el primero gana": si esta cuenta ya tiene una sesión viva,
    # se rechaza este segundo login (no se expulsa al que ya está dentro).
    # Aplica solo a clientes (rol client); los operadores admin/user quedan
    # exentos. La sesión se libera con "Salir" (logout) o automáticamente tras
    # ~10 min de inactividad (ver has_active_session / touch_session).
    if (
        user.role == Role.client
        and _session_check_enabled()
        and has_active_session(user)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "session_in_use",
                "message": (
                    "Esta cuenta ya está siendo usada en este momento. Para "
                    "ingresar, pida a la persona que está usando el sistema que "
                    "cierre sesión (botón «Salir»). Si nadie la está usando, la "
                    "sesión se libera automáticamente en unos minutos."
                ),
            },
        )

    fingerprint = device_mod.compute_fingerprint_hash(
        user_agent=request.headers.get("user-agent", ""),
        accept_language=request.headers.get("accept-language", ""),
        accept_encoding=request.headers.get("accept-encoding", ""),
    )
    ip = request.client.host if request.client else None

    # Flag global: si está apagado, el login no exige device check estricto.
    # Aún registramos UN device (el primero) para que el did del JWT tenga
    # algún valor consistente, pero saltamos los chequeos 409.
    import os as _os
    device_check_on = _os.getenv("CLIENT_PORTAL_DEVICE_CHECK_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}

    device = None
    if device_id and device_check_on:
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
    elif device_id and not device_check_on:
        # Check apagado: aceptar cualquier cookie sin validar. Si existe un
        # device con ese id lo usamos; sino registramos uno nuevo abajo.
        device = device_mod.validate_device(
            db, user=user, device_id=device_id, fingerprint_hash=fingerprint
        )

    if device is None:
        # Multi-device: permitimos hasta MAX_DEVICES_PER_USER dispositivos
        # activos por usuario (laptop + oficina + casa + incógnito ocasional).
        # Mantiene la seguridad porque sigue requiriéndose password correcta
        # para registrar un device nuevo; el JWT sigue siendo "sesión única"
        # vía el sid claim (login nuevo invalida sesión anterior, aunque sean
        # del mismo o de distinto device).
        # Si el check está apagado (modo QA), subimos el límite a 999 para
        # nunca pegar contra él durante pruebas.
        MAX_DEVICES_PER_USER = 5 if device_check_on else 999
        active_devices = db.execute(
            select(ClientDevice).where(
                ClientDevice.user_id == user.id,
                ClientDevice.is_active.is_(True),
            )
        ).scalars().all()

        if len(active_devices) >= MAX_DEVICES_PER_USER:
            # Revocar el device más antiguo para hacer espacio (FIFO).
            # Alternativa: rechazar; preferimos rotación silenciosa para
            # que el cliente no se vea bloqueado.
            oldest = min(active_devices, key=lambda d: d.last_seen_at or d.registered_at)
            # revoke_device usa kwarg ``revoked_by`` (objeto User), no
            # ``revoked_by_user_id``. Pasar el id como kwarg incorrecto
            # provocaba TypeError → HTTP 500 al sobrepasar el 5º dispositivo.
            device_mod.revoke_device(db, device=oldest, revoked_by=user)

        device = device_mod.register_device(
            db,
            user=user,
            fingerprint_hash=fingerprint,
            user_agent=request.headers.get("user-agent"),
            ip=ip,
        )
        # Cookie del dispositivo: cross-site obligatorio porque el backend
        # (auditbrain-python-runner.onrender.com) y el portal cliente
        # (auditbrain-clientes.onrender.com) viven bajo *.onrender.com, que
        # está en la Public Suffix List y por tanto el navegador trata cada
        # subdominio como un sitio distinto. ``samesite="strict"`` impide que
        # la cookie viaje en cross-site fetch desde el portal, causando
        # ``device_unauthorized`` en todas las llamadas siguientes y
        # rompiendo el cambio de contraseña / ICT / etc. Solución: en
        # producción ``samesite="none"`` + ``secure=True`` (httponly mantiene
        # la cookie inaccesible a JS, y el modelo de seguridad descansa en
        # la triple validación Bearer+sid+device, no en CSRF tradicional).
        response.set_cookie(
            key="device_id",
            value=device.device_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=not _is_test,
            samesite="lax" if _is_test else "none",
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

    # Enforcement de permiso: los operadores (admin/user) hacen bypass (QA/soporte),
    # coherente con el gating del catálogo; cualquier otro rol se filtra por
    # entitlement (fail-closed vía is_operator).
    from backend.app.client_portal.entitlements import can_access_tool, is_operator
    if not is_operator(user) and not can_access_tool(db, user.id, tool_code):
        raise HTTPException(
            403,
            detail="No tienes acceso a esta herramienta. Contacta a tu administrador.",
        )

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


_ARTIFACT_MEDIA = {
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".zip": "application/zip",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".json": "application/json; charset=utf-8",
}


@router.get("/tools/jobs/{job_id}/artifacts/{name}")
def download_job_artifact_endpoint(
    job_id: int,
    name: str,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Descarga un artefacto individual del job (ej. el TXT de un estado
    financiero, el XML del 101, o el ZIP con todo). Cada tool que produce
    varios entregables los deja en ``<job_dir>/artifacts/``."""
    try:
        job = cp_service.get_client_job(db, user=user, job_id=job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status not in ("done", "error_partial"):
        raise HTTPException(409, detail=f"Job status={job.status}, no listo para descarga")

    safe = os.path.basename(name)
    if safe != name or not safe or "/" in name or "\\" in name:
        raise HTTPException(400, detail="Nombre de artefacto inválido.")
    art_path = file_storage.job_dir(job.id) / "artifacts" / safe
    if not art_path.exists() or not art_path.is_file():
        raise HTTPException(410, detail="Artefacto no disponible (expirado o inexistente).")

    ext = os.path.splitext(safe)[1].lower()
    media = _ARTIFACT_MEDIA.get(ext, "application/octet-stream")
    return StreamingResponse(
        BytesIO(art_path.read_bytes()),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


class _BalanzaFila(BaseModel):
    cuenta: str = ""
    super_cias: str = ""
    sri: str = ""
    saldo: float = 0.0


class RecalcularFlujoRequest(BaseModel):
    bal_ant: list[_BalanzaFila]
    bal_act: list[_BalanzaFila]


@router.get("/tools/flujo/catalogos")
def flujo_catalogos_endpoint(
    user: User = Depends(require_client_with_device),
):
    """Plan de cuentas oficial (Super Cías + SRI) para poblar los selectores del
    editor de balanzas. Estático: el frontend lo cachea y lo pide una sola vez."""
    from backend.app.client_portal.flujo import catalogos as flujo_catalogos

    return flujo_catalogos.cargar_plan_cuentas()


@router.post("/tools/jobs/{job_id}/flujo/recalcular")
def recalcular_flujo_endpoint(
    job_id: int,
    payload: RecalcularFlujoRequest,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Recalcula TODA la Herramienta Flujo de Efectivo a partir de las balanzas
    editadas por el usuario en el portal. Reusa los motores validados en el
    servidor (no duplica lógica en el navegador), regenera Excel/TXT/XML/ZIP y
    la vista previa, y devuelve los previews frescos para refrescar el tablero.
    """
    try:
        job = cp_service.get_client_job(db, user=user, job_id=job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.tool_code != "FLUJO_EFECTIVO":
        raise HTTPException(400, detail="El recálculo solo aplica a la Herramienta Flujo de Efectivo.")
    if job.status not in ("done", "error_partial"):
        raise HTTPException(409, detail=f"Job status={job.status}, no listo para recalcular.")

    from backend.app.client_portal.flujo import processor as flujo_processor

    bal_ant = [f.model_dump() for f in payload.bal_ant]
    bal_act = [f.model_dump() for f in payload.bal_act]
    try:
        previews = flujo_processor.recalcular_desde_balanzas(job.id, bal_ant, bal_act)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    return previews


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
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Catálogo filtrado por los permisos (entitlements) del usuario.

    - Rol client: ve **solo** las secciones que tengan al menos una herramienta
      concedida; las secciones sin nada asignado NO aparecen. Sin permisos →
      catálogo vacío.
    - Operadores (admin/user): ven TODAS las secciones (incluidas las vacías,
      como 'Próximamente'), sin filtrar — entran al portal con su mismo usuario
      para QA/soporte."""
    from backend.app.client_portal.entitlements import is_operator, list_user_tool_codes

    operator = is_operator(user)
    # allowed=None → sin filtro (operadores). Rol client → set de sus permisos.
    allowed = None if operator else list_user_tool_codes(db, user.id)

    tools_by_cat: dict[str, list] = {c["id"]: [] for c in CATEGORIES}
    for t in list_enabled_tools():
        if allowed is not None and t.code not in allowed:
            continue
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
    cats_out = [
        CategoryOut(
            id=c["id"],
            label=c["label"],
            description=c.get("description"),
            tools=tools_by_cat.get(c["id"], []),
        )
        for c in CATEGORIES
    ]
    # Para clientes, ocultar las secciones sin herramientas asignadas: el cliente
    # ve solo lo suyo. Los operadores ven todas las secciones (incl. vacías).
    if not operator:
        cats_out = [c for c in cats_out if c.tools]
    return ClientCatalogResponse(categories=cats_out)
