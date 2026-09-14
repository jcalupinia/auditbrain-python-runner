"""Lógica de negocio de registros, cuentas y accesos de recursos."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth.password import hash_password, verify_password
from backend.app.recursos.claves import generar_clave, normalizar
from backend.app.recursos.models import RecursoAcceso, RecursoCuenta, RecursoLead, _utcnow
from backend.app.recursos.schemas import LeadCreate

# Versión del texto de public/politica-datos/ del mini-sitio.
POLITICA_VERSION = "v1"


def _norm_email(email: str) -> str:
    return email.strip().lower()


# ---- leads -----------------------------------------------------------------

def buscar(db: Session, slug: str, email: str) -> RecursoLead | None:
    return db.execute(
        select(RecursoLead).where(
            RecursoLead.recurso_slug == slug,
            RecursoLead.email == _norm_email(email),
        )
    ).scalar_one_or_none()


def registrar(db: Session, *, slug: str, data: LeadCreate, ip: str) -> RecursoLead:
    """Alta idempotente. Si el (slug, email) ya existe, lo devuelve sin tocarlo."""
    email = _norm_email(str(data.email))
    lead = buscar(db, slug, email)
    if lead is not None:
        return lead
    lead = RecursoLead(
        recurso_slug=slug,
        email=email,
        ip=ip[:64],
        nombre=data.nombre,
        empresa=data.empresa,
        consentimiento_at=_utcnow(),
        consentimiento_version=POLITICA_VERSION,
    )
    db.add(lead)
    try:
        db.commit()
    except IntegrityError:
        # Carrera: otra request insertó el mismo (slug, email) en paralelo.
        db.rollback()
        lead = buscar(db, slug, email)
        if lead is None:
            raise
        return lead
    db.refresh(lead)
    return lead


def listar(db: Session, *, slug: str | None = None, limit: int = 200) -> list[RecursoLead]:
    q = select(RecursoLead)
    if slug:
        q = q.where(RecursoLead.recurso_slug == slug)
    q = q.order_by(RecursoLead.created_at.desc(), RecursoLead.id.desc()).limit(limit)
    return list(db.execute(q).scalars())


def _lead_reciente(db: Session, email: str) -> RecursoLead | None:
    return db.execute(
        select(RecursoLead)
        .where(RecursoLead.email == _norm_email(email))
        .order_by(RecursoLead.created_at.desc(), RecursoLead.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def slugs_de_leads(db: Session, email: str) -> list[str]:
    return list(
        db.execute(
            select(RecursoLead.recurso_slug).where(RecursoLead.email == _norm_email(email))
        ).scalars()
    )


# ---- cuentas ---------------------------------------------------------------

def obtener_cuenta(db: Session, email: str) -> RecursoCuenta | None:
    return db.execute(
        select(RecursoCuenta).where(RecursoCuenta.email == _norm_email(email))
    ).scalar_one_or_none()


def _poner_clave(cuenta: RecursoCuenta, nueva: str | None) -> str:
    """Asigna la clave (solo el hash) y devuelve el texto en claro para el correo/admin."""
    if nueva is None:
        clave = generar_clave()
        cuenta.hashed_clave = hash_password(normalizar(clave))
        cuenta.clave_generada = True
    else:
        clave = nueva
        cuenta.hashed_clave = hash_password(nueva)
        cuenta.clave_generada = False
    cuenta.clave_actualizada_at = _utcnow()
    return clave


def crear_cuenta(
    db: Session, email: str, slugs: list[str], otorgado_por: str = "registro"
) -> tuple[RecursoCuenta, str | None]:
    """Crea la cuenta con clave generada y los accesos dados.

    Si otra request la creó en paralelo (doble clic), devuelve esa cuenta y
    clave None: la otra request ya envía su clave."""
    cuenta = RecursoCuenta(email=_norm_email(email))
    clave = _poner_clave(cuenta, None)
    db.add(cuenta)
    try:
        db.flush()
        for slug in dict.fromkeys(slugs):
            db.add(RecursoAcceso(cuenta_id=cuenta.id, recurso_slug=slug, otorgado_por=otorgado_por))
        db.commit()
    except IntegrityError:
        db.rollback()
        existente = obtener_cuenta(db, email)
        if existente is None:
            raise
        return existente, None
    db.refresh(cuenta)
    return cuenta, clave


def rotar_clave(db: Session, cuenta: RecursoCuenta, nueva: str | None = None) -> str:
    clave = _poner_clave(cuenta, nueva)
    db.commit()
    return clave


def verificar(cuenta: RecursoCuenta, clave: str) -> bool:
    escrita = normalizar(clave) if cuenta.clave_generada else clave
    return bool(escrita) and verify_password(escrita, cuenta.hashed_clave)


def accesos(db: Session, cuenta: RecursoCuenta) -> list[str]:
    return sorted(
        db.execute(
            select(RecursoAcceso.recurso_slug).where(RecursoAcceso.cuenta_id == cuenta.id)
        ).scalars()
    )


def asegurar_acceso(db: Session, cuenta: RecursoCuenta, slug: str, otorgado_por: str) -> None:
    if slug in accesos(db, cuenta):
        return
    db.add(RecursoAcceso(cuenta_id=cuenta.id, recurso_slug=slug, otorgado_por=otorgado_por))
    try:
        db.commit()
    except IntegrityError:  # carrera: ya otorgado en paralelo
        db.rollback()


def quitar_acceso(db: Session, cuenta: RecursoCuenta, slug: str) -> None:
    db.execute(
        delete(RecursoAcceso).where(
            RecursoAcceso.cuenta_id == cuenta.id, RecursoAcceso.recurso_slug == slug
        )
    )
    db.commit()


def registrar_ingreso(db: Session, cuenta: RecursoCuenta, slug: str) -> str:
    """Marca el ingreso (y verifica el lead del recurso). Devuelve el nombre a mostrar."""
    cuenta.ultimo_ingreso_at = _utcnow()
    lead = buscar(db, slug, cuenta.email)
    if lead is not None and lead.verificado_at is None:
        lead.verificado_at = _utcnow()
    db.commit()
    reciente = lead or _lead_reciente(db, cuenta.email)
    return reciente.nombre if reciente else ""


def listar_cuentas(db: Session) -> list[dict]:
    # ponytail: carga todas las cuentas y leads en memoria; paginar si pasan de miles.
    cuentas = db.execute(
        select(RecursoCuenta).order_by(RecursoCuenta.created_at.desc(), RecursoCuenta.id.desc())
    ).scalars()
    accs: dict[int, list[str]] = defaultdict(list)
    for cid, slug in db.execute(select(RecursoAcceso.cuenta_id, RecursoAcceso.recurso_slug)):
        accs[cid].append(slug)
    leads: dict[str, RecursoLead] = {}
    for lead in db.execute(
        select(RecursoLead).order_by(RecursoLead.created_at.desc(), RecursoLead.id.desc())
    ).scalars():
        leads.setdefault(lead.email, lead)
    filas = []
    for c in cuentas:
        lead = leads.get(c.email)
        filas.append(
            {
                "id": c.id,
                "email": c.email,
                "nombre": lead.nombre if lead else "",
                "empresa": lead.empresa if lead else "",
                "activo": c.activo,
                "accesos": sorted(accs.get(c.id, [])),
                "ultimo_ingreso_at": c.ultimo_ingreso_at,
                "created_at": c.created_at,
                "consentimiento_at": lead.consentimiento_at if lead else None,
                "email_enviado": lead.email_enviado if lead else False,
            }
        )
    return filas
