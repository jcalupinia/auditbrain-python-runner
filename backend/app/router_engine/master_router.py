"""Master Router de la plataforma v1.

Recibe una solicitud con un campo ``target`` y decide a qué módulo enviarla.
Sólo ``python_runner`` y ``document_generator`` están operativos en esta fase;
los módulos futuros responden como stub (501) sin lógica de negocio.
"""

from backend.app.document_services import universal_document_client
from backend.app.services import python_runner_service

OPERATIONAL_TARGETS = {"python_runner", "document_generator"}

FUTURE_TARGETS = {
    "future_audit_module",
    "future_tax_module",
    "future_legal_module",
    "future_finance_module",
    "future_marketing_module",
    "future_creative_module",
}

VALID_TARGETS = OPERATIONAL_TARGETS | FUTURE_TARGETS


class RouterError(Exception):
    """Error de enrutamiento con código HTTP asociado."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


async def route(payload: dict) -> dict:
    """Despacha la solicitud al módulo destino.

    payload esperado:
        {
          "target": "python_runner" | "document_generator" | "future_*",
          "payload": { ... datos específicos del módulo ... }
        }
    """
    target = str(payload.get("target", "")).strip().lower()
    inner = payload.get("payload", {}) or {}

    if not target:
        raise RouterError(400, "Campo 'target' requerido.")
    if target not in VALID_TARGETS:
        raise RouterError(
            400,
            f"target '{target}' no reconocido. Válidos: {sorted(VALID_TARGETS)}",
        )

    if target in FUTURE_TARGETS:
        raise RouterError(
            501,
            f"El módulo '{target}' aún no está implementado en esta fase.",
        )

    if target == "python_runner":
        result = await python_runner_service.run_python_code(
            code=inner.get("script", ""),
            inputs=inner.get("inputs", {}),
            response_mode=inner.get("response_mode"),
        )
        return {"target": target, "status": "ok", "result": result}

    if target == "document_generator":
        result = universal_document_client.generate_document(
            result=inner.get("result"),
            output_expectations=inner.get("output_expectations", {}),
            execution_context=inner.get("execution_context", {}),
            document_service=inner.get("document_service", {}),
        )
        return {"target": target, "status": "ok", "result": result}

    raise RouterError(500, "Estado de enrutamiento inesperado.")
