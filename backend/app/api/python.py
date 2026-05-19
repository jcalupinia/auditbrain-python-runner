"""Endpoint v1 para ejecutar código Python.

Acceso: admin (JWT) o X-API-Key (GPTs server-to-server). Ver
require_runner_access. El runner queda restringido al rol admin.
"""

from fastapi import APIRouter, Depends

from backend.app.api.models import PythonRunRequest
from backend.app.auth.deps import require_runner_access
from backend.app.services import python_runner_service

router = APIRouter(tags=["python"], dependencies=[Depends(require_runner_access)])


@router.post("/python/run")
async def python_run(body: PythonRunRequest):
    return await python_runner_service.run_python_code(
        code=body.script,
        inputs=body.inputs,
        response_mode=body.response_mode,
    )
