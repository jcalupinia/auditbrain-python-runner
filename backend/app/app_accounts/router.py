"""API de las Cuentas de Aplicaciones AUDIT-IA.

- Gestión (solo admin): catálogo de apps, alta, listado, reseteo de clave, activar/
  desactivar, permisos por app y borrado. Prefijo `/apps`.
- Autenticación de las apps (AUDIT SOUND, etc.): `POST /apps/auth/login` (cuerpo form) y
  `GET /apps/auth/me` (Bearer). El parámetro `app` valida el acceso a esa app concreta.
"""

import logging

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.app.app_accounts import catalog, service
from backend.app.app_accounts.models import AppAccount
from backend.app.app_accounts.schemas import (
    AppAccountCreate,
    AppAccountCreated,
    AppAccountOut,
    AppAccountUpdate,
    AppCatalogItem,
    AppChangePassword,
    AppLoginResponse,
    AppMeResponse,
    ResetPasswordIn,
    ResetPasswordOut,
)
from backend.app.notifications import email as email_svc

log = logging.getLogger(__name__)


def _send_access_email(acct: AppAccount, temp: str) -> bool | None:
    """Envía el acceso (usuario+clave) por correo. True enviado, False falló.

    No propaga excepciones: el alta/reset no debe romperse si el correo falla.
    """
    try:
        res = email_svc.send_app_account_access(to=acct.email, clave=temp)
        return res is not None
    except Exception:  # noqa: BLE001
        log.exception("Fallo enviando el correo de acceso a %s", acct.email)
        return False
from backend.app.auth.deps import require_admin
from backend.app.auth.jwt_tokens import create_access_token, decode_token
from backend.app.client_portal.rate_limit import check_and_record
from backend.app.db.session import get_db

router = APIRouter(prefix="/apps", tags=["app-accounts"])


def _out(db: Session, acct: AppAccount) -> AppAccountOut:
    return AppAccountOut(
        id=acct.id,
        email=acct.email,
        display_name=acct.display_name,
        client_label=acct.client_label,
        is_active=acct.is_active,
        password_reset_required=acct.password_reset_required,
        apps=service.account_apps(db, acct.id),
        created_by=acct.created_by,
        created_at=acct.created_at.isoformat(),
    )


# ---------------------------------------------------------------- Gestión (admin)

@router.get("/catalog", response_model=list[AppCatalogItem], dependencies=[Depends(require_admin)])
def apps_catalog():
    return catalog.app_catalog()


@router.get("/accounts", response_model=list[AppAccountOut], dependencies=[Depends(require_admin)])
def list_accounts(db: Session = Depends(get_db)):
    return [_out(db, a) for a in service.list_accounts(db)]


@router.post("/accounts", response_model=AppAccountCreated, status_code=201)
def create_account(
    payload: AppAccountCreate,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        acct, temp = service.create_account(
            db,
            email=payload.email,
            display_name=payload.display_name,
            client_label=payload.client_label,
            apps=payload.apps,
            created_by=getattr(admin, "email", None),
            password=payload.password,
        )
    except service.AppAccountError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Envía el acceso por correo (usuario + clave) si se pidió, ya sea la clave
    # generada por el sistema o la que fijó el administrador.
    email_sent = None
    if payload.send_email:
        email_sent = _send_access_email(acct, temp)
    return AppAccountCreated(account=_out(db, acct), temp_password=temp, email_sent=email_sent)


def _require_account(db: Session, account_id: int) -> AppAccount:
    acct = service.get(db, account_id)
    if not acct:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="cuenta no encontrada")
    return acct


@router.patch("/accounts/{account_id}", response_model=AppAccountOut)
def update_account(
    account_id: int,
    payload: AppAccountUpdate,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    acct = _require_account(db, account_id)
    try:
        if payload.display_name is not None or payload.client_label is not None:
            service.update_profile(db, acct, display_name=payload.display_name, client_label=payload.client_label)
        if payload.is_active is not None:
            service.set_active(db, acct, payload.is_active)
        if payload.apps is not None:
            service.set_apps(db, acct, payload.apps)
    except service.AppAccountError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _out(db, acct)


@router.post("/accounts/{account_id}/reset-password", response_model=ResetPasswordOut)
def reset_account_password(
    account_id: int,
    admin=Depends(require_admin),
    send_email: bool = Query(default=True, description="reenviar el acceso por correo al cliente"),
    payload: ResetPasswordIn | None = Body(default=None),
    db: Session = Depends(get_db),
):
    acct = _require_account(db, account_id)
    manual = (payload.password.strip() if payload and payload.password else "") or None
    try:
        temp = service.reset_password(db, acct, password=manual)
    except service.AppAccountError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    email_sent = _send_access_email(acct, temp) if send_email else None
    return ResetPasswordOut(temp_password=temp, email_sent=email_sent, manual=manual is not None)


@router.delete("/accounts/{account_id}", status_code=200)
def delete_account(
    account_id: int,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    acct = _require_account(db, account_id)
    service.delete_account(db, acct)
    return {"ok": True}


# ---------------------------------------------------------------- Auth de las apps

def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/auth/login", response_model=AppLoginResponse)
def app_login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    app: str | None = Query(default=None, description="clave de la app que valida el acceso"),
    db: Session = Depends(get_db),
):
    ip = _client_ip(request)
    if not check_and_record(f"applogin:{ip}:{form.username.lower()}", max_hits=8, window_seconds=300):
        raise HTTPException(429, detail="Demasiados intentos. Espere unos minutos.")
    acct = service.authenticate(db, form.username, form.password)
    if not acct:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas.",
                            headers={"WWW-Authenticate": "Bearer"})
    apps = service.account_apps(db, acct.id)
    if app is not None and app not in apps:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail={"code": "app_forbidden", "message": "La cuenta no tiene acceso a esta aplicación."})
    token = create_access_token(subject=acct.email, role="app",
                                extra_claims={"typ": "app", "acct": acct.id, "apps": apps})
    return AppLoginResponse(access_token=token, apps=apps,
                            password_reset_required=acct.password_reset_required)


def current_app_account(authorization: str | None = Header(default=None),
                        db: Session = Depends(get_db)) -> AppAccount:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="no autorizado")
    try:
        payload = decode_token(authorization[7:])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="token inválido")
    if payload.get("role") != "app" or payload.get("typ") != "app":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="el token no es de una cuenta de aplicación")
    acct = service.get(db, int(payload.get("acct", 0) or 0))
    if not acct or not acct.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="cuenta no disponible")
    return acct


@router.get("/auth/me", response_model=AppMeResponse)
def app_me(acct: AppAccount = Depends(current_app_account), db: Session = Depends(get_db)):
    return AppMeResponse(email=acct.email, display_name=acct.display_name,
                         apps=service.account_apps(db, acct.id),
                         password_reset_required=acct.password_reset_required)


@router.post("/auth/change-password", response_model=AppMeResponse)
def app_change_password(
    payload: AppChangePassword,
    acct: AppAccount = Depends(current_app_account),
    db: Session = Depends(get_db),
):
    """El cliente cambia su propia clave desde la app (verifica la clave actual)."""
    if service.authenticate(db, acct.email, payload.current_password) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta.")
    try:
        service.set_password(db, acct, payload.new_password)
    except service.AppAccountError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return AppMeResponse(email=acct.email, display_name=acct.display_name,
                         apps=service.account_apps(db, acct.id),
                         password_reset_required=acct.password_reset_required)
