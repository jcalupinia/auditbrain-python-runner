"""Endpoint v1 del Master Router (protegido por API Key)."""

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.models import RouterExecuteRequest
from backend.app.router_engine import master_router
from backend.app.security.api_key import require_api_key

router = APIRouter(tags=["router"], dependencies=[Depends(require_api_key)])


@router.post("/router/execute")
async def router_execute(body: RouterExecuteRequest):
    try:
        return await master_router.route(body.model_dump())
    except master_router.RouterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
