"""Router agregado de la API v1.

Expone ``api_router`` con prefijo /api/v1 para montarlo sobre la app legacy
sin alterar su estructura.
"""

from fastapi import APIRouter

from backend.app.api import canva, documents, health, python, router as router_module
from backend.app.auth import router as auth_router
from backend.app.aud.obligaciones_fiscales import router as aud_of_router
from backend.app.tax.planificacion_utilidades import router as tax_pu_router
from backend.app.chat import router as chat_router
from backend.app.context import router as context_router
from backend.app.core.config import settings

api_router = APIRouter(prefix=settings.PLATFORM_API_PREFIX)
api_router.include_router(health.router)
api_router.include_router(auth_router.router)
api_router.include_router(router_module.router)
api_router.include_router(python.router)
api_router.include_router(documents.router)
api_router.include_router(context_router.router)
api_router.include_router(chat_router.router)
api_router.include_router(aud_of_router.router)
api_router.include_router(tax_pu_router.router)
api_router.include_router(canva.router)

__all__ = ["api_router"]
