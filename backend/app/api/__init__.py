"""Router agregado de la API v1.

Expone ``api_router`` con prefijo /api/v1 para montarlo sobre la app legacy
sin alterar su estructura.
"""

from fastapi import APIRouter

from backend.app.api import documents, health, python, router as router_module
from backend.app.core.config import settings

api_router = APIRouter(prefix=settings.PLATFORM_API_PREFIX)
api_router.include_router(health.router)
api_router.include_router(router_module.router)
api_router.include_router(python.router)
api_router.include_router(documents.router)

__all__ = ["api_router"]
