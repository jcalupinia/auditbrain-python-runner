"""Endpoint v1 del Master Router.

El router puede invocar el runner, por lo que comparte la misma política
de acceso: admin (JWT) o X-API-Key. Ver require_runner_access.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.models import RouterExecuteRequest
from backend.app.auth.deps import require_runner_access
from backend.app.router_engine import master_router

router = APIRouter(tags=["router"], dependencies=[Depends(require_runner_access)])


@router.post("/router/execute")
async def router_execute(body: RouterExecuteRequest):
    try:
        return await master_router.route(body.model_dump())
    except master_router.RouterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
