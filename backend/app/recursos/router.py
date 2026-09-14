"""Endpoints /api/v1/recursos/* — registro, ingreso y clave (públicos) + gestión staff."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_admin, require_staff
from backend.app.auth.models import User
from backend.app.client_portal.rate_limit import check_and_record, reset_for_key
from backend.app.db.session import get_db
from backend.app.events.router import _client_ip
from backend.app.recursos import notify, service
from backend.app.recursos.catalog import Recurso, get_recurso
from backend.app.recursos.models import RecursoCuenta
from backend.app.recursos.schemas import (
    AccesoOut,
    AccesosOut,
    ActivoIn,
    ActivoOut,
    CuentaOut,
    IngresarIn,
    LeadCreate,
    LeadOut,
    LeadResponse,
    MensajeOut,
    OlvideIn,
    ResetClaveIn,
    ResetClaveOut,
)

router = APIRouter(prefix="/recursos", tags=["recursos"])
log = logging.getLogger(__name__)

MSG_REGISTRO = "Registro recibido. Le enviamos su usuario y clave a su correo."
MSG_OLVIDE = "Si el correo está registrado, le enviamos una clave nueva."
MSG_401 = "Usuario o clave incorrectos."
MSG_403 = (
    "Su usuario aún no tiene acceso a esta herramienta. Solicítelo por WhatsApp "
    "0990 609 811 o a jcalupinia@auditconsulting.ec."
)


def _recurso_o_404(slug: str) -> Recurso:
    rec = get_recurso(slug)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado.")
    return rec


def _limite(request: Request) -> str:
    ip = _client_ip(request)
    if not check_and_record(f"recurso-reg:{ip}", max_hits=10, window_seconds=600):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos desde esta red. Intente en unos minutos.",
        )
    return ip


def _limite_login(request: Request) -> None:
    """Límite por IP propio del ingreso (más holgado: oficinas detrás de una IP)."""
    ip = _client_ip(request)
    if not check_and_record(f"recurso-login-ip:{ip}", max_hits=30, window_seconds=600):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos desde esta red. Intente en unos minutos.",
        )


def _puede_enviar(email: str) -> bool:
    """Tope de correos con clave: 3/hora por correo y 30/hora en total."""
    correo = email.strip().lower()
    if not check_and_record(f"recurso-mail:{correo}", max_hits=3, window_seconds=3600):
        return False
    if not check_and_record("recurso-mail:global", max_hits=30, window_seconds=3600):
        # Visible en los logs de Render: nadie recibe su clave hasta que baje el pico.
        log.warning("Tope global de correos de recursos alcanzado (30/hora).")
        return False
    return True


# ---- públicos --------------------------------------------------------------
# Las claves solo se crean/rotan si el correo va a salir (si no, la persona se
# quedaría con una clave que nunca recibió).

@router.post(
    "/{slug}/registros", response_model=LeadResponse, status_code=status.HTTP_201_CREATED
)
def registrar_endpoint(
    slug: str,
    payload: LeadCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    rec = _recurso_o_404(slug)
    if not rec.registro_abierto:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado.")
    ip = _limite(request)
    if payload.website:  # bot: se le responde igual, sin guardar ni enviar
        return LeadResponse(ok=True, mensaje=MSG_REGISTRO)
    email = str(payload.email)
    service.registrar(db, slug=slug, data=payload, ip=ip)
    cuenta = service.obtener_cuenta(db, email)
    if cuenta is not None:
        if not cuenta.activo:  # desactivada por la firma: no se reactiva por registro
            return LeadResponse(ok=True, mensaje=MSG_REGISTRO)
        service.asegurar_acceso(db, cuenta, slug, "registro")
    if _puede_enviar(email):
        if cuenta is None:
            cuenta, clave = service.crear_cuenta(db, email, [slug])
        else:
            clave = service.rotar_clave(db, cuenta)
        if clave is not None:
            background_tasks.add_task(notify.enviar_clave, cuenta.id, clave, slug)
    return LeadResponse(ok=True, mensaje=MSG_REGISTRO)


@router.post("/{slug}/ingresar", response_model=AccesoOut)
def ingresar_endpoint(
    slug: str, payload: IngresarIn, request: Request, db: Session = Depends(get_db)
):
    _recurso_o_404(slug)
    _limite_login(request)
    email = str(payload.email).strip().lower()
    clave_login = f"recurso-login:{email}"
    # Cuenta intentos desde el último ingreso válido; bloqueado, ni la clave correcta pasa.
    if not check_and_record(clave_login, max_hits=10, window_seconds=600):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos con este usuario. Intente en unos minutos.",
        )
    cuenta = service.obtener_cuenta(db, email)
    # verificar() corre bcrypt siempre (señuelo si no hay cuenta): sin atajos de tiempo.
    if not service.verificar(cuenta, payload.clave) or not cuenta.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=MSG_401)
    reset_for_key(clave_login)
    if slug not in service.accesos(db, cuenta):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=MSG_403)
    return AccesoOut(ok=True, nombre=service.registrar_ingreso(db, cuenta, slug))


@router.post("/{slug}/olvide-clave", response_model=MensajeOut)
def olvide_clave_endpoint(
    slug: str,
    payload: OlvideIn,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    _recurso_o_404(slug)
    _limite(request)
    email = str(payload.email)
    cuenta = service.obtener_cuenta(db, email)
    # El correo lleva el recurso de la página si la cuenta lo tiene; si no, el
    # primero que tenga otorgado (sin accesos no hay a dónde mandarla).
    if cuenta is None:
        # Registros previos a v2: lead sin cuenta → se crea con acceso a sus recursos.
        slugs = [s for s in service.slugs_de_leads(db, email) if get_recurso(s)]
        destino = service.slug_para_correo(slugs, slug)
        if destino is not None and _puede_enviar(email):
            cuenta, clave = service.crear_cuenta(db, email, slugs)
            if clave is not None:
                background_tasks.add_task(notify.enviar_clave, cuenta.id, clave, destino)
    elif cuenta.activo:
        destino = service.slug_para_correo(service.accesos(db, cuenta), slug)
        if destino is None:
            log.warning("Cuenta de recurso %s sin accesos; no se envía clave.", cuenta.id)
        elif _puede_enviar(email):
            clave = service.rotar_clave(db, cuenta)
            background_tasks.add_task(notify.enviar_clave, cuenta.id, clave, destino)
    return MensajeOut(ok=True, mensaje=MSG_OLVIDE)


# ---- staff (leer: require_staff; modificar: require_admin) ------------------

@router.get(
    "/registros", response_model=list[LeadOut], dependencies=[Depends(require_staff)]
)
def listar_endpoint(
    slug: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return [LeadOut.model_validate(r) for r in service.listar(db, slug=slug, limit=limit)]


@router.get("/cuentas", response_model=list[CuentaOut], dependencies=[Depends(require_staff)])
def listar_cuentas_endpoint(db: Session = Depends(get_db)):
    return service.listar_cuentas(db)


def _cuenta_o_404(db: Session, cuenta_id: int) -> RecursoCuenta:
    cuenta = db.get(RecursoCuenta, cuenta_id)
    if cuenta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada.")
    return cuenta


@router.put("/cuentas/{cuenta_id}/accesos/{slug}", response_model=AccesosOut)
def otorgar_acceso_endpoint(
    cuenta_id: int,
    slug: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    cuenta = _cuenta_o_404(db, cuenta_id)
    _recurso_o_404(slug)
    service.asegurar_acceso(db, cuenta, slug, admin.email)
    return AccesosOut(ok=True, accesos=service.accesos(db, cuenta))


@router.delete(
    "/cuentas/{cuenta_id}/accesos/{slug}",
    response_model=AccesosOut,
    dependencies=[Depends(require_admin)],
)
def quitar_acceso_endpoint(cuenta_id: int, slug: str, db: Session = Depends(get_db)):
    cuenta = _cuenta_o_404(db, cuenta_id)
    _recurso_o_404(slug)
    service.quitar_acceso(db, cuenta, slug)
    return AccesosOut(ok=True, accesos=service.accesos(db, cuenta))


@router.post(
    "/cuentas/{cuenta_id}/reset-clave",
    response_model=ResetClaveOut,
    dependencies=[Depends(require_admin)],
)
def reset_clave_endpoint(
    cuenta_id: int,
    payload: ResetClaveIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Clave escrita por el admin o generada; se devuelve en claro UNA sola vez."""
    cuenta = _cuenta_o_404(db, cuenta_id)
    clave = service.rotar_clave(db, cuenta, payload.new_password)
    if payload.enviar_correo:
        destino = service.slug_para_correo(service.accesos(db, cuenta))
        if destino is None:
            log.warning("Cuenta de recurso %s sin accesos; no se envía clave.", cuenta.id)
        else:
            background_tasks.add_task(notify.enviar_clave, cuenta.id, clave, destino)
    return ResetClaveOut(email=cuenta.email, temp_password=clave)


@router.post(
    "/cuentas/{cuenta_id}/activo",
    response_model=ActivoOut,
    dependencies=[Depends(require_admin)],
)
def activo_endpoint(cuenta_id: int, payload: ActivoIn, db: Session = Depends(get_db)):
    cuenta = _cuenta_o_404(db, cuenta_id)
    cuenta.activo = payload.activo
    db.commit()
    return ActivoOut(ok=True, activo=cuenta.activo)
