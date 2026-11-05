"""Lógica de las Cuentas de Aplicaciones AUDIT-IA."""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.app_accounts import catalog
from backend.app.app_accounts.models import AppAccount, AppAccountEntitlement
from backend.app.auth.password import hash_password, verify_password


class AppAccountError(ValueError):
    """Error de validación de cuentas de aplicación."""


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _valid_apps(apps: list[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for a in apps or []:
        a = (a or "").strip()
        if not a:
            continue
        if not catalog.is_valid_app(a):
            raise AppAccountError(f"app desconocida: {a}")
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def generate_temp_password(length: int = 14) -> str:
    # Sin caracteres ambiguos; suficiente entropía para una clave temporal.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get(db: Session, account_id: int) -> AppAccount | None:
    return db.get(AppAccount, account_id)


def get_by_email(db: Session, email: str) -> AppAccount | None:
    return db.execute(
        select(AppAccount).where(AppAccount.email == _normalize_email(email))
    ).scalar_one_or_none()


def account_apps(db: Session, account_id: int) -> list[str]:
    rows = db.execute(
        select(AppAccountEntitlement.app_key).where(
            AppAccountEntitlement.app_account_id == account_id
        )
    ).scalars().all()
    # Orden estable según el catálogo.
    order = [a["key"] for a in catalog.app_catalog()]
    return [k for k in order if k in set(rows)]


def set_apps(db: Session, account: AppAccount, apps: list[str]) -> list[str]:
    wanted = set(_valid_apps(apps))
    current = db.execute(
        select(AppAccountEntitlement).where(
            AppAccountEntitlement.app_account_id == account.id
        )
    ).scalars().all()
    have = {e.app_key for e in current}
    for e in current:
        if e.app_key not in wanted:
            db.delete(e)
    for key in wanted - have:
        db.add(AppAccountEntitlement(app_account_id=account.id, app_key=key))
    db.commit()
    return account_apps(db, account.id)


def list_accounts(db: Session) -> list[AppAccount]:
    return db.execute(select(AppAccount).order_by(AppAccount.created_at.desc())).scalars().all()


def create_account(
    db: Session,
    *,
    email: str,
    display_name: str | None = None,
    client_label: str | None = None,
    apps: list[str] | None = None,
    created_by: str | None = None,
    password: str | None = None,
) -> tuple[AppAccount, str]:
    """Crea una cuenta de aplicación. Devuelve (cuenta, clave_temporal)."""
    email = _normalize_email(email)
    if not email or "@" not in email:
        raise AppAccountError("correo inválido")
    if get_by_email(db, email) is not None:
        raise AppAccountError("ya existe una cuenta con ese correo")
    if password is not None and len(password) < 8:
        raise AppAccountError("la contraseña debe tener al menos 8 caracteres")
    valid_apps = _valid_apps(apps)
    temp = password or generate_temp_password()
    acct = AppAccount(
        email=email,
        hashed_password=hash_password(temp),
        display_name=(display_name or None),
        client_label=(client_label or None),
        is_active=True,
        password_reset_required=password is None,  # si no se dio clave, debe cambiarla
        created_by=created_by,
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    if valid_apps:
        set_apps(db, acct, valid_apps)
    return acct, temp


def reset_password(db: Session, account: AppAccount) -> str:
    temp = generate_temp_password()
    account.hashed_password = hash_password(temp)
    account.password_reset_required = True
    db.commit()
    return temp


def set_password(db: Session, account: AppAccount, new_password: str) -> None:
    if not new_password or len(new_password) < 8:
        raise AppAccountError("la contraseña debe tener al menos 8 caracteres")
    account.hashed_password = hash_password(new_password)
    account.password_reset_required = False
    db.commit()


def set_active(db: Session, account: AppAccount, active: bool) -> None:
    account.is_active = bool(active)
    db.commit()


def update_profile(db: Session, account: AppAccount, *, display_name=None, client_label=None) -> None:
    if display_name is not None:
        account.display_name = display_name or None
    if client_label is not None:
        account.client_label = client_label or None
    db.commit()


def delete_account(db: Session, account: AppAccount) -> None:
    db.delete(account)
    db.commit()


def authenticate(db: Session, email: str, password: str) -> AppAccount | None:
    acct = get_by_email(db, email)
    if not acct or not acct.is_active:
        return None
    if not verify_password(password, acct.hashed_password):
        return None
    return acct


def has_app(db: Session, account: AppAccount, app_key: str) -> bool:
    return app_key in set(account_apps(db, account.id))
