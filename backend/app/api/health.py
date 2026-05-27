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


def _ocr_status() -> dict:
    """Estado del módulo OCR (Google Cloud Vision).

    NO devuelve credenciales: solo si está disponible y qué motor usa.
    Útil para que la UI muestre indicador y para validar el deploy.
    """
    try:
        from backend.app.utils import ocr
        return {
            "available": ocr.is_available(),
            "engine": "google-cloud-vision",
        }
    except Exception:  # pragma: no cover
        return {"available": False, "engine": None}


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "AuditBrain Platform v1",
        "version": settings.APP_VERSION,
        "auth_enabled": settings.auth_enabled,
        "llm": _llm_providers(),
        "ocr": _ocr_status(),
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
