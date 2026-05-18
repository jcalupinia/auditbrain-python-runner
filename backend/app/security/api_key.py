"""Autenticación mínima por API Key.

Diseño deliberado para no romper a los GPTs existentes:
- Si ``AUDITBRAIN_API_KEY`` NO está definida -> auth desactivada, se permite
  todo (idéntico al comportamiento legacy actual).
- Si está definida -> se exige el header ``X-API-Key`` con el valor correcto.

La activación es una decisión explícita del operador (definir la env var);
nada cambia en producción hasta que se decida.
"""

from fastapi import Header, HTTPException, status

from backend.app.core.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """Dependency FastAPI. No-op si la auth está desactivada."""
    if not settings.auth_enabled:
        return

    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente.",
            headers={"WWW-Authenticate": settings.API_KEY_HEADER},
        )
