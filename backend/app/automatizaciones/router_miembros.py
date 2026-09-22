"""Endpoints /api/v1/app/miembros — Tarea 9 del plan.

A diferencia de ``router.py`` (Command Center, staff/JWT propio), aquí quien
llama es el ADMINISTRADOR de la empresa cliente ya logueado en la app de
presupuestos: manda su ``access_token`` de Supabase y el portal se lo
reenvía a ``agregar_miembro``/``es_admin_empresa`` (vía
``supabase_admin.rpc(..., token_usuario=...)``) para que las reglas de la
base (solo el admin de SU empresa, unicidad, auditoría) se apliquen
exactamente igual que si llamara la app. El navegador nunca ve la llave de
servicio.

Esa llave de servicio solo se usa donde la base no da otra vía: crear la
cuenta de autenticación (GoTrue admin) y generar el enlace de acceso.

La baja/el borrado de miembros NO se duplican aquí: la app ya los resuelve
con sus propias reglas RLS.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.app.automatizaciones import service
from backend.app.automatizaciones import supabase_admin as sa
from backend.app.client_portal.tool_registry import TOOLS
from backend.app.notifications import email as email_mod
from backend.app.recursos.catalog import CONTACTO

router = APIRouter(prefix="/app/miembros", tags=["automatizaciones-app"])
log = logging.getLogger(__name__)

MSG_502 = "No se pudo contactar al servidor de Presupuestos IA."
_ETIQUETA_HERRAMIENTA = TOOLS["PRESUPUESTOS_IA"].label

# Enum public.app_role de smart-budget-builder (supabase/migrations).
ROLES_APP = ("administrador", "gerencia", "finanzas", "responsable", "revisor", "consulta")


# --- Schemas -----------------------------------------------------------


class MiembroCreate(BaseModel):
    empresa_id: UUID
    email: EmailStr
    nombre: str | None = Field(default=None, max_length=200)
    role: str = "consulta"
    departamento_id: UUID | None = None

    @field_validator("role")
    @classmethod
    def _role_valido(cls, v: str) -> str:
        if v not in ROLES_APP:
            raise ValueError(f"«{v}» no es un rol válido de la app de presupuestos.")
        return v


class ReenviarAccesoBody(BaseModel):
    empresa_id: UUID
    email: EmailStr


class MiembroOut(BaseModel):
    id: str
    empresa_id: str
    email: str
    nombre: str | None
    role: str | None
    departamento_id: str | None
    estado: str


# --- Autenticación (token de la app, no el JWT del Command Center) ---------


def _token_bearer(request: Request) -> str:
    authz = request.headers.get("Authorization", "")
    if not authz.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falta el token de acceso.")
    token = authz.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falta el token de acceso.")
    return token


def _actor(token: str = Depends(_token_bearer)) -> tuple[str, str]:
    """Valida el token contra Supabase y devuelve ``(token, email del actor)``.

    401 solo cuando GoTrue REALMENTE rechaza el token (4xx); un fallo de red
    o un 5xx es un problema de infraestructura (502), no de sesión expirada.
    """
    try:
        perfil = sa.usuario_de_token(token)
    except sa.SupabaseAdminError as e:
        if e.status is not None and e.status < 500:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado.") from None
        log.error("aut miembros: fallo Supabase validando el token: %s", e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=MSG_502) from None
    return token, (perfil or {}).get("email", "")


def _no_es_administrador(e: sa.SupabaseAdminError) -> bool:
    return "administrador de la empresa" in str(e)


def _empresa_nombre(empresa_id: str) -> str:
    """Mejor esfuerzo: si la app no responde, el correo sale sin el nombre
    en vez de tumbar el alta (ya completada del lado de la app)."""
    try:
        filas = sa.consultar("empresas", {"id": f"eq.{empresa_id}", "select": "nombre", "limit": "1"})
    except sa.SupabaseAdminError:
        log.warning("aut miembros: no se pudo leer el nombre de la empresa %s", empresa_id)
        return ""
    return (filas or [{}])[0].get("nombre") or ""


def _enviar_acceso(email: str, empresa_id: str) -> None:
    """Genera el enlace de un solo uso y lo manda. Lanza si algo falla (el
    llamador decide si hay que revertir una cuenta recién creada)."""
    enlace = sa.enlace_acceso(email, service._redirect_nueva_contrasena())
    enviado = email_mod.send_automatizacion_acceso(
        to=email,
        herramienta=_ETIQUETA_HERRAMIENTA,
        empresa=_empresa_nombre(empresa_id),
        enlace=enlace,
        contacto=CONTACTO,
    )
    if enviado is None:
        raise RuntimeError("El correo de acceso no se pudo enviar.")


# --- Alta ----------------------------------------------------------------


@router.post("", response_model=MiembroOut, status_code=status.HTTP_201_CREATED)
def alta_miembro(payload: MiembroCreate, actor: tuple[str, str] = Depends(_actor)):
    token, actor_email = actor
    empresa_id = str(payload.empresa_id)
    departamento_id = str(payload.departamento_id) if payload.departamento_id else None

    try:
        miembro_id = sa.rpc(
            "agregar_miembro",
            {
                "_empresa_id": empresa_id,
                "_email": payload.email,
                "_nombre": payload.nombre,
                "_role": payload.role,
                "_departamento_id": departamento_id,
            },
            token_usuario=token,
        )
    except sa.SupabaseAdminError as e:
        if _no_es_administrador(e):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="No es administrador de esta empresa."
            ) from None
        log.error("aut miembros alta: fallo Supabase actor=%s empresa=%s: %s", actor_email, empresa_id, e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=MSG_502) from None

    cuenta_nueva = False
    nuevo_uid: str | None = None
    try:
        usuario = sa.crear_usuario(payload.email, payload.nombre or payload.email)
        cuenta_nueva = True
        nuevo_uid = (usuario or {}).get("id")
    except sa.SupabaseAdminError:
        # ponytail: con el correo ya validado por Pydantic, el único 4xx real
        # de GoTrue al crear es "ya registrado" -> se asume eso y se sigue.
        # Si esto da falsos positivos en producción, distinguir por código.
        log.info("aut miembros alta: %s ya tenía cuenta de autenticación", payload.email)

    try:
        _enviar_acceso(payload.email, empresa_id)
    except Exception:
        if cuenta_nueva and nuevo_uid:
            try:
                sa.borrar_usuario(nuevo_uid)
            except sa.SupabaseAdminError:
                log.error("aut miembros alta: no se pudo deshacer el usuario nuevo de %s", payload.email)
        log.error(
            "aut miembros alta: fallo al enviar el acceso actor=%s empresa=%s email=%s",
            actor_email,
            empresa_id,
            payload.email,
        )
        # La membresía en ``empresa_miembros`` SÍ queda registrada (la base
        # tiene sus propias reglas; no se borra desde aquí): se documenta
        # cómo recuperarla en vez de dejar un 502 genérico.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="El miembro quedó registrado pero no se pudo enviar el correo. "
            "Use «Reenviar acceso».",
        ) from None

    log.info("aut miembros alta: actor=%s empresa=%s email=%s", actor_email, empresa_id, payload.email)

    filas = sa.consultar(
        "empresa_miembros",
        {
            "id": f"eq.{miembro_id}",
            "select": "id,empresa_id,email,nombre,role,departamento_id,estado",
            "limit": "1",
        },
    )
    fila = (filas or [{}])[0]
    return MiembroOut(
        id=str(fila.get("id", miembro_id)),
        empresa_id=str(fila.get("empresa_id", empresa_id)),
        email=fila.get("email", payload.email),
        nombre=fila.get("nombre"),
        role=fila.get("role", payload.role),
        departamento_id=fila.get("departamento_id"),
        estado=fila.get("estado", ""),
    )


# --- Reenviar acceso ---------------------------------------------------


@router.post("/reenviar-acceso")
def reenviar_acceso(payload: ReenviarAccesoBody, actor: tuple[str, str] = Depends(_actor)):
    token, actor_email = actor
    empresa_id = str(payload.empresa_id)

    try:
        es_admin = sa.rpc("es_admin_empresa", {"_empresa_id": empresa_id}, token_usuario=token)
    except sa.SupabaseAdminError as e:
        log.error("aut miembros reenvio: fallo Supabase actor=%s empresa=%s: %s", actor_email, empresa_id, e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=MSG_502) from None
    if not es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No es administrador de esta empresa.")

    try:
        filas = sa.consultar(
            "empresa_miembros",
            {
                "empresa_id": f"eq.{empresa_id}",
                "email": f"eq.{payload.email}",
                "select": "id,nombre",
                "limit": "1",
            },
            token_usuario=token,
        )
    except sa.SupabaseAdminError as e:
        log.error("aut miembros reenvio: fallo Supabase actor=%s empresa=%s: %s", actor_email, empresa_id, e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=MSG_502) from None
    if not filas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ese correo no es miembro de esta empresa.")

    # El miembro puede no tener todavía cuenta de autenticación: si el alta
    # original se quedó a medias (correo fallido, ver alta_miembro) o si es
    # la primera vez que se le reenvía el acceso, generar el enlace sin
    # crear antes la cuenta no serviría de nada.
    nombre = (filas[0] or {}).get("nombre") or payload.email
    try:
        sa.crear_usuario(payload.email, nombre)
    except sa.SupabaseAdminError:
        # ponytail: mismo patrón que el alta (router_miembros.alta_miembro) —
        # con el correo ya validado por Pydantic, el único 4xx real de GoTrue
        # al crear es "ya existe" -> se asume eso y se sigue.
        log.info("aut miembros reenvio: %s ya tenía cuenta de autenticación", payload.email)

    try:
        _enviar_acceso(payload.email, empresa_id)
    except Exception:
        log.error(
            "aut miembros reenvio: fallo al enviar el acceso actor=%s empresa=%s email=%s",
            actor_email,
            empresa_id,
            payload.email,
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=MSG_502) from None

    log.info("aut miembros reenvio: actor=%s empresa=%s email=%s", actor_email, empresa_id, payload.email)
    return {"ok": True}
