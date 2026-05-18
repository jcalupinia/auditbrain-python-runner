"""Cliente del servicio externo 'Universal Creador de Documentos'.

Encapsula el armado de payloads por formato y la llamada HTTP. Replica el
comportamiento del bloque documental de app.py de forma deliberada durante la
migración (ver docs/MIGRATION_PLAN.md para la consolidación de fase 2).
"""

import datetime
import json

import requests

from backend.app.core.config import settings

_FORMAT_ALIASES = {
    "xlsx": "excel",
    "docx": "word",
    "pptx": "ppt",
    "power_bi": "powerbi",
    "bi": "powerbi",
    "zipfile": "zip",
}


def _normalize_format(fmt: str) -> str:
    fmt = (fmt or "excel").lower().strip()
    return _FORMAT_ALIASES.get(fmt, fmt)


def _resolve_base(document_service: dict) -> str:
    base = settings.DOCUMENT_SERVICE
    if isinstance(document_service, dict):
        custom = str(document_service.get("endpoint", "")).strip()
        if custom:
            if not custom.startswith(("http://", "https://")):
                custom = f"https://{custom.lstrip('/')}"
            base = custom.rstrip("/")
    return base


def _build_payload(format_type: str, result, execution_context: dict):
    ctx = execution_context or {}
    now = datetime.datetime.utcnow().isoformat()

    if format_type == "excel":
        return {
            "titulo": ctx.get("task_name", "Reporte generado por AuditBrain"),
            "data": {
                "headers": list(result.keys()),
                "rows": [[str(v) for v in result.values()]],
            },
        }
    if format_type == "pdf":
        return {
            "title": "Informe de Resultados",
            "sections": [
                {"type": "h1", "text": "Resultados Analíticos"},
                {"type": "p", "text": json.dumps(result, indent=2)},
                {"type": "p", "text": f"Generado por AuditBrain el {now}"},
            ],
        }
    if format_type == "word":
        return {
            "placeholders": {
                "titulo": ctx.get("task_name", "Informe Corporativo"),
                "subtitulo": ctx.get("module_area", "Resultados de Análisis"),
                "autor": "Audit Consulting IA Suite",
                "fecha": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
            },
            "content": [
                {"type": "heading", "text": "Resultados Generales"},
                {"type": "paragraph", "text": json.dumps(result, indent=2)},
            ],
        }
    if format_type == "ppt":
        return {
            "title": ctx.get("task_name", "Presentación Ejecutiva"),
            "subtitle": "Análisis generado automáticamente por AuditBrain",
            "slides": [
                {
                    "type": "title",
                    "title": "Resumen Ejecutivo",
                    "bullets": ["Resultados clave del análisis", "Integración completa con IA Suite"],
                },
                {
                    "type": "content",
                    "title": "Datos Principales",
                    "bullets": [json.dumps(result, indent=2)],
                },
            ],
        }
    if format_type == "csv":
        return {
            "headers": list(result.keys()),
            "rows": [[str(v) for v in result.values()]],
        }
    if format_type == "canva":
        return {
            "title": ctx.get("task_name", "Presentación Canva"),
            "subtitle": ctx.get("module_area", "Resultados de análisis"),
            "sections": [
                {"type": "heading", "text": "Resumen"},
                {"type": "paragraph", "text": json.dumps(result, indent=2)},
            ],
        }
    if format_type == "powerbi":
        return {
            "dataset_name": ctx.get("task_name", "Dataset AuditBrain"),
            "headers": list(result.keys()),
            "rows": [[v for v in result.values()]],
            "metadata": {
                "module_area": ctx.get("module_area", "general"),
                "generated_at": now,
            },
        }
    if format_type == "zip":
        return {
            "title": ctx.get("task_name", "Paquete AuditBrain"),
            "files": [
                {
                    "filename": "resultado.json",
                    "content_type": "application/json",
                    "content": json.dumps(result, indent=2),
                }
            ],
        }
    return {
        "title": "Reporte General",
        "sections": [{"type": "p", "text": json.dumps(result)}],
    }


def generate_document(result, output_expectations: dict = None,
                       execution_context: dict = None,
                       document_service: dict = None) -> dict:
    """Envía ``result`` al servicio documental externo y devuelve su respuesta."""
    output_expectations = output_expectations or {}
    format_type = _normalize_format(output_expectations.get("format", "excel"))
    base = _resolve_base(document_service or {})
    endpoint_format = "powerbi" if format_type == "csv" else format_type
    endpoint = f"{base}/generate_{endpoint_format}"

    try:
        payload = _build_payload(format_type, result, execution_context or {})
        response = requests.post(endpoint, json=payload, timeout=90)

        if response.status_code != 200 and format_type == "pdf":
            fallback = {
                "titulo": (execution_context or {}).get("task_name", "Informe de Resultados"),
                "contenido": [json.dumps(result, indent=2)],
                "incluir_grafico": False,
            }
            response = requests.post(endpoint, json=fallback, timeout=90)

        if response.status_code == 200:
            return {"status": "ok", "endpoint": endpoint, "response": response.json()}
        return {
            "status": "error",
            "error": f"Fallo al generar documento ({response.status_code})",
            "endpoint": endpoint,
            "details": (response.text or "")[:500],
        }
    except Exception as exc:  # noqa: BLE001 - se reporta al cliente
        return {"status": "error", "error": str(exc), "endpoint": endpoint}
