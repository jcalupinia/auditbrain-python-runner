"""Endpoints /api/v1/events/* — inscripción pública + listado admin."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_admin
from backend.app.client_portal.rate_limit import check_and_record
from backend.app.db.session import get_db
from backend.app.events import notify, service
from backend.app.events.catalog import get_event
from backend.app.events.schemas import (
    RegistrationCreate,
    RegistrationOut,
    RegistrationResponse,
)

router = APIRouter(prefix="/events", tags=["events"])


def _client_ip(request: Request) -> str:
    """IP real del cliente. Detrás de un proxy (Render) usa el primer hop
    de X-Forwarded-For; si no, la IP directa de la conexión."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/{slug}/registrations",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_registration_endpoint(
    slug: str,
    payload: RegistrationCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    event = get_event(slug)
    if event is None or not event.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Evento no encontrado o inactivo.")

    ip = _client_ip(request)
    if not check_and_record(f"event-reg:{ip}", max_hits=10, window_seconds=600):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas inscripciones desde esta red. Intente más tarde.",
        )

    reg, ya_inscrito = service.create_registration(db, event_slug=slug, data=payload)
    background_tasks.add_task(notify.process_registration_notifications, reg.id)

    mensaje = (
        "Ya estabas inscrito; te reenviamos los detalles por email y WhatsApp."
        if ya_inscrito
        else "Inscripción confirmada. Te enviamos los detalles por email y WhatsApp."
    )
    return RegistrationResponse(
        ok=True, estado=reg.estado, ya_inscrito=ya_inscrito, mensaje=mensaje
    )


@router.get(
    "/{slug}/registrations",
    response_model=list[RegistrationOut],
    dependencies=[Depends(require_admin)],
)
def list_registrations_endpoint(
    slug: str,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    rows = service.list_registrations(db, event_slug=slug, limit=limit)
    return [RegistrationOut.model_validate(r) for r in rows]
