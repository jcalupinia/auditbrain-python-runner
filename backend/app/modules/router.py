"""Endpoints del registry de módulos sectoriales: /api/v1/modules."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.auth.deps import get_current_user
from backend.app.modules.registry import all_modules, get_module

router = APIRouter(prefix="/modules", tags=["modules"])


def _serialize(m) -> dict:
    return {
        "code": m.code,
        "label": m.label,
        "tagline": m.tagline,
        "description": m.description,
        "suggested_actions": list(m.suggested_actions),
        "kpi_hints": list(m.kpi_hints),
    }


@router.get("")
def list_modules(_: object = Depends(get_current_user)):
    """Catálogo de módulos. NO incluye el system_prompt (es server-side)."""
    return [_serialize(m) for m in all_modules()]


@router.get("/{code}")
def get_module_endpoint(code: str, _: object = Depends(get_current_user)):
    m = get_module(code)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Módulo no encontrado.")
    return _serialize(m)
