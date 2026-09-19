"""Reglas de provisión de cuentas de Automatizaciones (Tarea 4 del plan).

El Command Center es la central de provisión: crea el usuario administrador de
la empresa cliente en el Supabase de la app de presupuestos, le manda el enlace
de acceso y administra después su ciclo de vida (reenvío, baja reversible,
borrado). El transporte vive en ``supabase_admin.py``; aquí solo hay reglas.

**[ADAPTATION] La empresa NO se crea desde aquí.** ``crear_empresa_completa``
exige ``auth.uid()`` y con la llave de servicio eso es NULL, así que la empresa
la crea el propio administrador cuando entra por primera vez (él conoce sector,
período y unidades, que es justo lo que el formulario de la app pide). Esta
tabla guarda ``empresa_nombre`` como referencia comercial y completa
``empresa_id_app`` cuando la empresa ya aparece en la app
(``refrescar_empresa``).

**Protecciones (regla 5 del plan).** Hoy la unicidad es ``(client_id,
herramienta)``: un cliente tiene exactamente una cuenta por herramienta, así
que "no dejar al cliente sin cuenta activa" no se puede resolver contando
hermanas — cualquier baja o borrado deja al cliente sin acceso. Por eso el
control es explícito: **el borrado exige ``confirmado=True`` del llamador** (el
router lo pide con confirmación escrita, como en Cuentas) y el servicio
**nunca borra en cascada** nada de la app: ni la empresa, ni sus miembros, ni
su histórico de presupuestos. Suspender es reversible y por eso no necesita
confirmación aquí.
"""

from __future__ import annotations

import datetime
import logging
import os

from sqlalchemy.orm import Session

from backend.app.automatizaciones import supabase_admin as sa
from backend.app.automatizaciones.models import AutCuenta
from backend.app.client_portal.tool_registry import TOOLS
from backend.app.notifications import email as email_mod
from backend.app.recursos.catalog import CONTACTO

log = logging.getLogger(__name__)

_APP_URL_DEFECTO = "https://presupuestos.audit-ia.ec"


class AutomatizacionError(RuntimeError):
    """Error de negocio (duplicada, inexistente, borrado sin confirmar).

    ``SupabaseAdminError`` NO se captura aquí: sube tal cual para que el router
    lo traduzca a un mensaje de infraestructura."""


def _redirect_nueva_contrasena() -> str:
    base = os.getenv("PRESUPUESTOS_APP_URL", _APP_URL_DEFECTO).strip().rstrip("/")
    return f"{base}/nueva-contrasena"


def _etiqueta(herramienta: str) -> str:
    tool = TOOLS.get(herramienta)
    return tool.label if tool else herramienta


def _obtener(db: Session, cuenta_id: int) -> AutCuenta:
    cuenta = db.get(AutCuenta, cuenta_id)
    if cuenta is None:
        raise AutomatizacionError(f"La cuenta {cuenta_id} no existe.")
    return cuenta


def _enviar_acceso(cuenta: AutCuenta) -> None:
    """Genera el enlace de un solo uso y lo manda. Nunca fija la contraseña."""
    enlace = sa.enlace_acceso(cuenta.admin_email, _redirect_nueva_contrasena())
    enviado = email_mod.send_automatizacion_acceso(
        to=cuenta.admin_email,
        herramienta=_etiqueta(cuenta.herramienta),
        empresa=cuenta.empresa_nombre,
        enlace=enlace,
        contacto=CONTACTO,
    )
    if enviado is None:
        raise AutomatizacionError(
            f"No se pudo enviar el correo de acceso a {cuenta.admin_email}."
        )


# --- Alta (reglas 1 y 2) ----------------------------------------------------


def crear(
    db: Session,
    *,
    client_id: int,
    herramienta: str,
    empresa_nombre: str,
    admin_email: str,
    admin_nombre: str,
    creado_por: str,
    vigencia_hasta: datetime.date | None = None,
) -> AutCuenta:
    """Alta atómica: usuario en Supabase → fila ``aut_cuentas`` → correo.

    Si falla cualquier paso posterior a la creación del usuario se borra el
    usuario y no queda fila a medias.
    """
    admin_email = admin_email.strip().lower()
    ya = (
        db.query(AutCuenta)
        .filter_by(client_id=client_id, herramienta=herramienta)
        .first()
    )
    if ya is not None:
        raise AutomatizacionError(
            f"El cliente {client_id} ya tiene una cuenta de {_etiqueta(herramienta)}."
        )

    usuario = sa.crear_usuario(admin_email, admin_nombre)
    user_id = (usuario or {}).get("id")

    cuenta = AutCuenta(
        client_id=client_id,
        herramienta=herramienta,
        empresa_nombre=empresa_nombre,
        admin_email=admin_email,
        admin_nombre=admin_nombre,
        admin_user_id_app=user_id,
        estado="activa",
        vigencia_hasta=vigencia_hasta,
        creado_por=creado_por,
    )
    try:
        db.add(cuenta)
        db.flush()
        _enviar_acceso(cuenta)
        db.commit()
    except Exception:
        db.rollback()
        if user_id:
            try:
                sa.borrar_usuario(user_id)
            except Exception:  # noqa: BLE001
                log.error(
                    "aut alta: no se pudo deshacer el usuario %s del cliente %s",
                    user_id,
                    client_id,
                )
        raise

    db.refresh(cuenta)
    log.info(
        "aut alta: actor=%s cuenta=%s cliente=%s herramienta=%s admin=%s",
        creado_por,
        cuenta.id,
        client_id,
        herramienta,
        admin_email,
    )
    return cuenta


# --- Ciclo de vida (reglas 3, 4 y 5) ----------------------------------------


def reenviar_acceso(db: Session, cuenta_id: int, *, actor: str) -> AutCuenta:
    cuenta = _obtener(db, cuenta_id)
    _enviar_acceso(cuenta)
    log.info("aut reenvio: actor=%s cuenta=%s admin=%s", actor, cuenta.id, cuenta.admin_email)
    return cuenta


def _cambiar_estado(db: Session, cuenta_id: int, *, actor: str, suspender_: bool) -> AutCuenta:
    cuenta = _obtener(db, cuenta_id)
    if not cuenta.admin_user_id_app:
        raise AutomatizacionError(
            f"La cuenta {cuenta_id} no tiene usuario en la app; no se puede bloquear."
        )
    sa.bloquear_usuario(cuenta.admin_user_id_app, suspender_)
    cuenta.estado = "suspendida" if suspender_ else "activa"
    db.commit()
    db.refresh(cuenta)
    log.info(
        "aut %s: actor=%s cuenta=%s admin=%s",
        "suspension" if suspender_ else "reactivacion",
        actor,
        cuenta.id,
        cuenta.admin_email,
    )
    return cuenta


def suspender(db: Session, cuenta_id: int, *, actor: str) -> AutCuenta:
    return _cambiar_estado(db, cuenta_id, actor=actor, suspender_=True)


def reactivar(db: Session, cuenta_id: int, *, actor: str) -> AutCuenta:
    return _cambiar_estado(db, cuenta_id, actor=actor, suspender_=False)


def borrar(db: Session, cuenta_id: int, *, actor: str, confirmado: bool) -> None:
    """Borra el usuario administrador y la fila. NO toca la app: la empresa,
    sus miembros y su histórico de presupuestos quedan intactos."""
    if not confirmado:
        raise AutomatizacionError(
            "El borrado de una cuenta de automatizaciones requiere confirmación explícita."
        )
    cuenta = _obtener(db, cuenta_id)
    admin_email = cuenta.admin_email
    if cuenta.admin_user_id_app:
        sa.borrar_usuario(cuenta.admin_user_id_app)
    db.delete(cuenta)
    db.commit()
    log.info("aut borrado: actor=%s cuenta=%s admin=%s", actor, cuenta_id, admin_email)


# --- Vigencia y listado (regla 6) -------------------------------------------


def esta_vigente(cuenta: AutCuenta) -> bool:
    """Sin fecha, vigente para siempre; el último día cuenta como vigente."""
    if cuenta.vigencia_hasta is None:
        return True
    return cuenta.vigencia_hasta >= datetime.date.today()


def estado_efectivo(cuenta: AutCuenta) -> str:
    """Una licencia vencida se ve suspendida aunque el dato diga ``activa``."""
    if cuenta.estado != "activa" or not esta_vigente(cuenta):
        return "suspendida"
    return "activa"


def listar(db: Session, *, client_id: int | None = None) -> list[dict]:
    q = db.query(AutCuenta)
    if client_id is not None:
        q = q.filter_by(client_id=client_id)
    return [
        {
            "id": c.id,
            "client_id": c.client_id,
            "herramienta": c.herramienta,
            "herramienta_label": _etiqueta(c.herramienta),
            "empresa_nombre": c.empresa_nombre,
            "empresa_id_app": c.empresa_id_app,
            "admin_email": c.admin_email,
            "admin_nombre": c.admin_nombre,
            "estado": estado_efectivo(c),
            "vencida": not esta_vigente(c),
            "vigencia_hasta": c.vigencia_hasta,
            "creado_por": c.creado_por,
            "created_at": c.created_at,
        }
        for c in q.order_by(AutCuenta.id.desc()).all()
    ]


# --- Enlazar la empresa de la app (regla 7) ---------------------------------


def refrescar_empresa(db: Session, cuenta: AutCuenta) -> str | None:
    """Busca en la app la empresa del administrador y guarda su UUID.

    Es un enriquecimiento de mejor esfuerzo: mientras el administrador no haya
    creado su empresa (o si el servidor de la app no responde) devuelve ``None``
    sin romper el listado.
    """
    if cuenta.empresa_id_app:
        return cuenta.empresa_id_app
    try:
        filas = sa.consultar(
            "empresa_miembros",
            {"email": f"eq.{cuenta.admin_email}", "select": "empresa_id", "limit": "1"},
        )
    except sa.SupabaseAdminError:
        log.warning("aut refrescar_empresa: la app no respondió (cuenta=%s)", cuenta.id)
        return None
    empresa_id = (filas or [{}])[0].get("empresa_id")
    if not empresa_id:
        return None
    cuenta.empresa_id_app = empresa_id
    db.commit()
    log.info("aut empresa enlazada: cuenta=%s empresa=%s", cuenta.id, empresa_id)
    return empresa_id
