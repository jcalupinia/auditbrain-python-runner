"""Endpoint de salud de la plataforma v1."""

import datetime

from fastapi import APIRouter

from backend.app.core.config import settings

router = APIRouter(tags=["platform"])


def _llm_providers() -> dict:
    """Diagnóstico no sensible de proveedores LLM configurados.

    NO devuelve las API keys ni sus prefijos: solo qué proveedores tienen
    clave en el entorno y en qué orden los probaría chat_complete().
    """
    try:
        from backend.app.chat.providers import _providers_with_keys
        chain = _providers_with_keys()
        return {"configured": chain, "primary": chain[0] if chain else None}
    except Exception:  # pragma: no cover
        return {"configured": [], "primary": None}


def _ocr_status() -> dict:
    """Estado del módulo OCR (Google Cloud Vision).

    NO devuelve credenciales: solo si está disponible y qué motor usa.
    Útil para que la UI muestre indicador y para validar el deploy.
    """
    try:
        from backend.app.utils import ocr
        return {
            "available": ocr.is_available(),
            "engine": "google-cloud-vision",
        }
    except Exception:  # pragma: no cover
        return {"available": False, "engine": None}


def _formats_status() -> dict:
    """Lista qué tipos de documentos puede procesar el backend.

    Útil para que la UI muestre capacidades y para que los GPTs sepan
    qué formatos pueden enviar.
    """
    formats: dict[str, bool] = {
        "xlsx": True,        # openpyxl + pandas (siempre)
        "docx": True,        # python-docx
        "pptx": True,        # python-pptx
        "pdf": True,         # pdfplumber (digital)
        "xml": True,         # lxml
        "csv": True,         # pandas
        "json": True,        # stdlib
        "image_ocr": False,  # se actualiza abajo
        "pdf_ocr": False,
        "pbix": False,
        "qvd": False,
        "canva_native": False,  # Canva via MCP
    }
    # OCR
    try:
        from backend.app.utils import ocr
        if ocr.is_available():
            formats["image_ocr"] = True
            formats["pdf_ocr"] = True
    except Exception:
        pass
    # Power BI .pbix nativo
    try:
        from backend.app.utils import pbix_native
        formats["pbix"] = pbix_native.is_available()
    except Exception:
        pass
    # QlikView .qvd
    try:
        from backend.app.utils import qlikview
        formats["qvd"] = qlikview.is_available()
    except Exception:
        pass
    # Canva via MCP
    try:
        from backend.app.utils import canva_mcp
        formats["canva_native"] = canva_mcp.is_available()
    except Exception:
        pass
    return formats


def _canva_status() -> dict:
    """Estado del MCP de Canva (igual filosofía que _ocr_status)."""
    try:
        from backend.app.utils import canva_mcp
        return {
            "available": canva_mcp.is_available(),
            "engine": "anthropic-mcp-canva",
        }
    except Exception:
        return {"available": False, "engine": None}


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "AuditBrain Platform v1",
        "version": settings.APP_VERSION,
        "auth_enabled": settings.auth_enabled,
        "llm": _llm_providers(),
        "ocr": _ocr_status(),
        "canva": _canva_status(),
        "formats": _formats_status(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(),
    }
