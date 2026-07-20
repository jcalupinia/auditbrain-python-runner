"""Router agregado de la API v1.

Expone ``api_router`` con prefijo /api/v1 para montarlo sobre la app legacy
sin alterar su estructura.
"""

import logging

from fastapi import APIRouter

from backend.app.api import canva, documents, health, python, router as router_module, skill_run
from backend.app.auth import router as auth_router
from backend.app.aud.obligaciones_fiscales import router as aud_of_router
from backend.app.aud.informe_cumplimiento_tributario import router as aud_informe_ict_router
from backend.app.aud.motor_balances import router as aud_motor_balances_router
from backend.app.tax.planificacion_utilidades import router as tax_pu_router
from backend.app.chat import router as chat_router
from backend.app.client_portal import router as client_portal_router
from backend.app.context import router as context_router
from backend.app.events import router as events_router
from backend.app.staff_portal import router as staff_portal_router
from backend.app.ict.router import router as ict_router
from backend.app.core.config import settings

_log = logging.getLogger(__name__)

api_router = APIRouter(prefix=settings.PLATFORM_API_PREFIX)
api_router.include_router(health.router)
api_router.include_router(auth_router.router)
api_router.include_router(router_module.router)
api_router.include_router(python.router)
api_router.include_router(skill_run.router)
api_router.include_router(documents.router)
api_router.include_router(context_router.router)
api_router.include_router(chat_router.router)
api_router.include_router(aud_of_router.router)
api_router.include_router(aud_informe_ict_router.router)
api_router.include_router(aud_motor_balances_router.router)
api_router.include_router(tax_pu_router.router)
api_router.include_router(canva.router)
api_router.include_router(client_portal_router.router)
api_router.include_router(staff_portal_router.router)
api_router.include_router(staff_portal_router.global_router)
api_router.include_router(ict_router)
api_router.include_router(events_router.router)


def _montar_forge(router: APIRouter) -> bool:
    """Monta los routers de Forge de forma AISLADA. Devuelve si se montaron.

    Forge (L0-L11) es funcionalidad nueva y opcional. Un import roto o un router
    mal formado en ``forge/`` **no puede tumbar /api/v1 entero** —auth, portal
    cliente, ICT, AUD— para los clientes en producción. El import de Forge vive
    aquí dentro (no arriba con los demás) justo para que su fallo se contenga:
    si algo revienta, se registra y la API arranca sin Forge en vez de no
    arrancar en absoluto.

    El resto de routers (auth, ICT, etc.) siguen al top level a propósito: son el
    núcleo del producto; si uno de ellos no importa, es un fallo que SÍ debe
    detener el despliegue, no esconderse. Forge es lo añadido y opcional.
    """
    try:
        from backend.app.forge import client_router as forge_client_router
        from backend.app.forge import governance_router as forge_governance_router
        from backend.app.forge import router as forge_router

        router.include_router(forge_router.router)
        router.include_router(forge_client_router.client_router)
        router.include_router(forge_governance_router.governance_router)
    except Exception:  # noqa: BLE001 - aislar Forge es justo el objetivo
        _log.exception(
            "Forge no se pudo montar; /api/v1 arranca SIN Forge "
            "(auth, portal e ICT quedan intactos)."
        )
        return False
    return True


#: ¿Quedó Forge montado? Lo consulta el healthcheck para no mentir sobre el estado.
forge_montado = _montar_forge(api_router)

__all__ = ["api_router", "forge_montado"]
