"""Endpoints /api/v1/recursos/* — registro público + acceso + listado staff."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_staff
from backend.app.client_portal.rate_limit import check_and_record
from backend.app.db.session import get_db
from backend.app.events.router import _client_ip
from backend.app.recursos import notify, service
from backend.app.recursos.catalog import get_recurso
from backend.app.recursos.models import RecursoLead
from backend.app.recursos.schemas import (
    AccesoOut,
    LeadCreate,
    LeadOut,
    LeadResponse,
    MensajeOut,
    ReenvioIn,
)
from backend.app.recursos.tokens import leer_token

router = APIRouter(prefix="/recursos", tags=["recursos"])
log = logging.getLogger(__name__)

MSG_REGISTRO = "Registro recibido. Le enviamos el enlace de acceso a su correo."
MSG_REENVIO = "Si el correo está registrado, le reenviamos el enlace de acceso."


def _recurso_o_404(slug: str) -> None:
    if get_recurso(slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado.")


def _limite(request: Request) -> str:
    ip = _client_ip(request)
    if not check_and_record(f"recurso-reg:{ip}", max_hits=10, window_seconds=600):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos desde esta red. Intente en unos minutos.",
        )
    return ip


def _puede_enviar(email: str) -> bool:
    """Tope de correos de acceso: 3/hora por correo y 30/hora en total."""
    correo = email.strip().lower()
    if not check_and_record(f"recurso-mail:{correo}", max_hits=3, window_seconds=3600):
        return False
    if not check_and_record("recurso-mail:global", max_hits=30, window_seconds=3600):
        # Visible en los logs de Render: nadie recibe su enlace hasta que baje el pico.
        log.warning("Tope global de correos de recursos alcanzado (30/hora).")
        return False
    return True


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
    _recurso_o_404(slug)
    ip = _limite(request)
    if payload.website:  # bot: se le responde igual, sin guardar ni enviar
        return LeadResponse(ok=True, mensaje=MSG_REGISTRO)
    lead = service.registrar(db, slug=slug, data=payload, ip=ip)
    if _puede_enviar(str(payload.email)):
        background_tasks.add_task(notify.enviar_acceso, lead.id)
    return LeadResponse(ok=True, mensaje=MSG_REGISTRO)


@router.post("/{slug}/reenviar", response_model=MensajeOut)
def reenviar_endpoint(
    slug: str,
    payload: ReenvioIn,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    _recurso_o_404(slug)
    _limite(request)
    lead = service.buscar(db, slug, str(payload.email))
    if lead is not None and _puede_enviar(str(payload.email)):
        background_tasks.add_task(notify.enviar_acceso, lead.id)
    return MensajeOut(ok=True, mensaje=MSG_REENVIO)


@router.get("/{slug}/acceso", response_model=AccesoOut)
def acceso_endpoint(slug: str, token: str = Query(max_length=2000), db: Session = Depends(get_db)):
    _recurso_o_404(slug)
    lead_id = leer_token(token, slug)
    lead = db.get(RecursoLead, lead_id) if lead_id is not None else None
    if lead is None or lead.recurso_slug != slug:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Enlace inválido o vencido."
        )
    service.marcar_verificado(db, lead)
    return AccesoOut(ok=True, nombre=lead.nombre)


@router.get(
    "/registros", response_model=list[LeadOut], dependencies=[Depends(require_staff)]
)
def listar_endpoint(
    slug: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return [LeadOut.model_validate(r) for r in service.listar(db, slug=slug, limit=limit)]
