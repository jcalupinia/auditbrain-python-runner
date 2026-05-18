"""Endpoint v1 para generar documentos vía el servicio externo."""

from fastapi import APIRouter, Depends

from backend.app.api.models import DocumentGenerateRequest
from backend.app.document_services import universal_document_client
from backend.app.security.api_key import require_api_key

router = APIRouter(tags=["documents"], dependencies=[Depends(require_api_key)])


@router.post("/documents/generate")
async def documents_generate(body: DocumentGenerateRequest):
    return universal_document_client.generate_document(
        result=body.result,
        output_expectations=body.output_expectations,
        execution_context=body.execution_context,
        document_service=body.document_service,
    )
