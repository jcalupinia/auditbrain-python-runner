"""Endpoint v1 para ejecutar código Python (protegido por API Key)."""

from fastapi import APIRouter, Depends

from backend.app.api.models import PythonRunRequest
from backend.app.security.api_key import require_api_key
from backend.app.services import python_runner_service

router = APIRouter(tags=["python"], dependencies=[Depends(require_api_key)])


@router.post("/python/run")
async def python_run(body: PythonRunRequest):
    return await python_runner_service.run_python_code(
        code=body.script,
        inputs=body.inputs,
        response_mode=body.response_mode,
    )
