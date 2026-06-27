"""Service layer del staff portal: gestión de cuentas y dispositivos cliente."""

from __future__ import annotations

import re
from io import BytesIO

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth import device as device_mod
from backend.app.auth import service as auth_service
from backend.app.auth.models import ClientDevice, Role, User
from backend.app.auth.service import invalidate_session
from backend.app.client_portal import service as cp_service
from backend.app.context.models import Client


def list_portal_users(db: Session, *, client_id: int) -> list[User]:
    return list(
        db.execute(
            select(User).where(User.client_id == client_id, User.role == Role.client)
        ).scalars()
    )


def disable_portal_user(db: Session, *, user: User) -> None:
    user.is_active = False
    db.add(user)
    db.commit()


def enable_portal_user(db: Session, *, user: User) -> None:
    user.is_active = True
    db.add(user)
    db.commit()


def list_devices(db: Session, *, user_id: int) -> list[ClientDevice]:
    return list(
        db.execute(
            select(ClientDevice).where(ClientDevice.user_id == user_id)
            .order_by(ClientDevice.registered_at.desc())
        ).scalars()
    )


def reset_all_devices(db: Session, *, user: User, revoked_by: User) -> int:
    return device_mod.revoke_all_devices_for_user(db, user=user, revoked_by=revoked_by)


def force_logout(db: Session, *, user: User) -> None:
    invalidate_session(db, user=user)


# ---------------------------------------------------------------------------
# Carga masiva de clientes (licencias) — UNA cuenta por correo único
# ---------------------------------------------------------------------------
# Buscamos el correo DENTRO del texto (no exigimos que la celda sea solo el
# correo): así recuperamos casos reales como "EDWIN ORTIZ <e@x.com>", celdas
# con varios correos ("a@x.com; b@y.com" → toma el primero), comillas o saltos
# de línea. Si no hay ningún correo válido → la fila se omite.
_EMAIL_FIND = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _extract_email(raw) -> str | None:
    """Devuelve el primer correo válido encontrado en ``raw`` (en minúsculas),
    o None si no hay ninguno."""
    if not raw:
        return None
    m = _EMAIL_FIND.search(str(raw))
    return m.group(0).strip().lower() if m else None


def password_from_email_ruc(email: str, ruc: str | None) -> str:
    """Clave temporal de la carga masiva = nombre del dominio del correo (sin
    el .com/.ec) + los 4 primeros dígitos del RUC. Ej:
    contador@corpogranja.com + 1792470013001 → 'corpogranja1792'.

    Es una clave TEMPORAL y predecible a propósito (fácil de comunicar al
    cliente); el portal obliga a cambiarla en el primer ingreso
    (password_reset_required=True)."""
    dominio = ""
    if email and "@" in email:
        dominio = email.split("@", 1)[1].split(".", 1)[0].lower()
    digitos = "".join(c for c in str(ruc or "") if c.isdigit())[:4]
    return f"{dominio}{digitos}" or "cliente"


def parse_clients_workbook(file_bytes: bytes) -> list[dict]:
    """Parsea un .xlsx con columnas CLIENTE | RUC | Email Contador (en ese
    orden). Salta filas en blanco y la fila de encabezado. Devuelve una lista
    de dicts {cliente, ruc, email} con los valores en texto."""
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.active
    out: list[dict] = []
    for row in ws.iter_rows(values_only=True):
        if not row or not row[0]:
            continue
        cliente = str(row[0]).strip()
        if cliente.upper() == "CLIENTE":  # encabezado
            continue
        ruc = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        email = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        out.append({"cliente": cliente, "ruc": ruc, "email": email})
    return out


def _get_or_create_client(
    db: Session, *, organization_id: int, name: str, tax_id: str | None
) -> Client:
    """Devuelve un Client por (organización, nombre); lo crea si no existe.
    Maneja la restricción única (organization_id, name) reutilizando el
    existente en vez de fallar."""
    name = name[:200]
    existing = db.execute(
        select(Client).where(
            Client.organization_id == organization_id, Client.name == name
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    client = Client(
        organization_id=organization_id,
        name=name,
        tax_id=(tax_id or None),
        is_active=True,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def bulk_create_portal_clients(
    db: Session, *, organization_id: int, rows: list[dict]
) -> dict:
    """Crea cuentas de portal en bloque: UNA por correo único.

    - Correos inválidos/ausentes → ``omitidos`` (con motivo).
    - Correos ya registrados → ``existentes`` (no se duplican).
    - Resto → ``creados`` con la clave temporal generada (mostrar una vez).

    Cuando varios clientes comparten el mismo correo (un contador), se crea una
    sola cuenta y se listan todas sus empresas asociadas.
    """
    creados: list[dict] = []
    omitidos: list[dict] = []
    existentes: list[dict] = []

    # Agrupar por correo válido, preservando orden de aparición.
    by_email: dict[str, list[dict]] = {}
    for row in rows:
        email = _extract_email(row.get("email"))
        if not email:
            omitidos.append({
                "cliente": row.get("cliente", ""),
                "ruc": row.get("ruc", ""),
                "motivo": f"sin correo válido: {row.get('email', '')!r}",
            })
            continue
        by_email.setdefault(email, []).append(row)

    for email, empresas in by_email.items():
        if auth_service.get_user_by_email(db, email):
            existentes.append({
                "email": email,
                "empresas": [e.get("cliente", "") for e in empresas],
            })
            continue
        nombre = empresas[0].get("cliente", "") or email
        if len(empresas) > 1:
            nombre = f"{nombre} (+{len(empresas) - 1})"
        ruc = empresas[0].get("ruc") or None
        client = _get_or_create_client(
            db, organization_id=organization_id, name=nombre, tax_id=ruc
        )
        pwd = password_from_email_ruc(email, ruc)
        user, temp = cp_service.create_portal_user(
            db, client_id=client.id, email=email, password=pwd
        )
        creados.append({
            "user_id": user.id,
            "email": email,
            "temp_password": temp,
            "ruc": ruc or "",
            "empresas": [e.get("cliente", "") for e in empresas],
        })

    return {"creados": creados, "omitidos": omitidos, "existentes": existentes}


def list_all_portal_users(db: Session) -> list[dict]:
    """Lista TODAS las cuentas de portal (rol client) con el nombre de su
    cliente asociado, para la gestión global en el panel admin."""
    users = list(
        db.execute(
            select(User).where(User.role == Role.client).order_by(User.email)
        ).scalars()
    )
    out: list[dict] = []
    for u in users:
        cliente = ""
        if u.client_id:
            c = db.get(Client, u.client_id)
            cliente = c.name if c else ""
        out.append({
            "id": u.id,
            "email": u.email,
            "is_active": u.is_active,
            "password_reset_required": u.password_reset_required,
            "cliente": cliente,
        })
    return out
