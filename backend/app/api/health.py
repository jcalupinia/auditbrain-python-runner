"""Endpoint de salud de la plataforma v1."""

import datetime

from fastapi import APIRouter

from backend.app.core.config import settings

router = APIRouter(tags=["platform"])


def _llm_providers() -> dict:
    """Diagnóstico no sensible de proveedores LLM configurados.

    NO devuelve las API keys ni sus prefijos: solo qué proveedores tienen
    clave en el entorno y en qué orden los probaría chat_complete().
    """
    try:
        from backend.app.chat.providers import _providers_with_keys
        chain = _providers_with_keys()
        return {"configured": chain, "primary": chain[0] if chain else None}
    except Exception:  # pragma: no cover
        return {"configured": [], "primary": None}


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "AuditBrain Platform v1",
        "version": settings.APP_VERSION,
        "auth_enabled": settings.auth_enabled,
        "llm": _llm_providers(),
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
