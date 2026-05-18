"""Endpoint de salud de la plataforma v1."""

import datetime

from fastapi import APIRouter

from backend.app.core.config import settings

router = APIRouter(tags=["platform"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "AuditBrain Platform v1",
        "version": settings.APP_VERSION,
        "auth_enabled": settings.auth_enabled,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
