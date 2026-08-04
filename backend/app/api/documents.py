"""Endpoint v1 para generar documentos vía el servicio externo.

Acceso: cualquier usuario autenticado (JWT, admin o user) o X-API-Key
(GPTs server-to-server). Ver require_user_access. El frontend usa JWT;
la API Key nunca llega al navegador.
"""

from fastapi import APIRouter, Depends

from backend.app.api.models import DocumentGenerateRequest
from backend.app.auth.deps import require_user_access
from backend.app.document_services import universal_document_client

router = APIRouter(tags=["documents"], dependencies=[Depends(require_user_access)])


@router.post("/documents/generate")
def documents_generate(body: DocumentGenerateRequest):
    """Genera un documento vía el servicio externo.

    Declarada SÍNCRONA a propósito (no ``async def``). Todo su cuerpo es
    ``requests.post`` bloqueante con timeout de 90s, y hasta dos intentos:
    como corrutina congelaba el event loop hasta 180s y el health check de
    Render caducaba a los 5s, provocando el reinicio de la instancia. Al ser
    ``def``, Starlette la ejecuta en su threadpool y el loop sigue libre.
    El contrato HTTP (ruta, request, response) es idéntico.
    """
    return universal_document_client.generate_document(
        result=body.result,
        output_expectations=body.output_expectations,
        execution_context=body.execution_context,
        document_service=body.document_service,
    )
