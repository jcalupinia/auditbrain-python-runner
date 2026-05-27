"""Generación de designs Canva via Claude API con MCP (Model Context Protocol).

Arquitectura:
    AuditBrain backend → Anthropic Messages API con mcp_servers config →
        Claude orquesta tools de Canva (generate, edit, export) →
            Devuelve URLs del design + exports.

A diferencia del antiguo /generate_canva (SVG estático), este módulo:
- Genera designs REALES en la cuenta Canva del operador.
- Aplica brand kit si está disponible.
- Devuelve PDF/PPTX descargables con calidad profesional.

Configuración requerida (env vars):
- ANTHROPIC_API_KEY:     ya existe, se reutiliza.
- CANVA_MCP_URL:         URL del MCP server de Canva (default oficial).
- CANVA_MCP_OAUTH_TOKEN: OAuth token de Canva (paso 5 de la guía).
- ANTHROPIC_MODEL:       modelo a usar (default claude-sonnet-4-6).

Ver `docs/CANVA_MCP_SETUP.md` para el setup paso a paso.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class CanvaMCPUnavailable(RuntimeError):
    """MCP de Canva no configurado en el servidor."""


class CanvaMCPError(RuntimeError):
    """Error invocando el MCP de Canva."""


# ---------------------------------------------------------------------------
# Configuración resuelta cada llamada (soporta tests con monkeypatch)
# ---------------------------------------------------------------------------

def _anthropic_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "").strip()


def _canva_mcp_url() -> str:
    # URL oficial del MCP de Canva. Sobrescribible via env si Anthropic
    # cambia el endpoint o si el operador usa un proxy interno.
    return os.getenv(
        "CANVA_MCP_URL",
        "https://mcp.canva.com/sse",
    ).strip()


def _canva_mcp_token() -> str:
    return os.getenv("CANVA_MCP_OAUTH_TOKEN", "").strip()


def _model() -> str:
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()


def _max_tokens() -> int:
    try:
        return int(os.getenv("CANVA_MCP_MAX_TOKENS", "8192"))
    except ValueError:
        return 8192


# ---------------------------------------------------------------------------
# Disponibilidad
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """True si Anthropic + token de Canva MCP están configurados."""
    if not _anthropic_key() or not _canva_mcp_token():
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _require_available():
    if not _anthropic_key():
        raise CanvaMCPUnavailable(
            "ANTHROPIC_API_KEY no configurado. Necesario para llamar Claude API."
        )
    if not _canva_mcp_token():
        raise CanvaMCPUnavailable(
            "CANVA_MCP_OAUTH_TOKEN no configurado. Ver docs/CANVA_MCP_SETUP.md "
            "para obtenerlo del Canva developer portal."
        )
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:
        raise CanvaMCPUnavailable(
            "Librería anthropic no instalada. Añadir a requirements-prod.txt."
        ) from exc


# ---------------------------------------------------------------------------
# Resultado normalizado
# ---------------------------------------------------------------------------

@dataclass
class CanvaDesignResult:
    """Resultado de generar un design via MCP."""
    design_id: str | None
    design_url: str | None
    edit_url: str | None
    view_url: str | None
    title: str | None
    page_count: int | None
    exports: dict[str, str] = field(default_factory=dict)  # {"pdf": url, "pptx": url}
    tokens_in: int | None = None
    tokens_out: int | None = None
    raw_response: str = ""  # Última respuesta del modelo (debugging)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cliente principal
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Eres un asistente especializado en generar designs profesionales en Canva para una firma de auditoría y consultoría (AuditBrain).

Tu rol: orquestar las herramientas del MCP de Canva para producir designs corporativos de alta calidad. Pasos esperados:

1. Si el usuario menciona un brand kit, úsalo via list-brand-kits para encontrar el ID.
2. Llama generate-design (o generate-design-structured para presentaciones) con los parámetros adecuados.
3. Selecciona el PRIMER candidato (índice 0) del resultado, salvo que el usuario especifique otro.
4. Convierte el candidato en design editable con create-design-from-candidate.
5. Si el usuario pide PDF/PPTX, llama export-design para cada formato.
6. Devuelve un resumen estructurado con TODAS las URLs:
   - design_id
   - edit_url (canva.com/d/...)
   - view_url
   - URLs de exports (PDF, PPTX)
   - page_count

REGLAS CRÍTICAS:
- NO inventes URLs ni IDs. Devuelve solo lo que las tools retornen REALMENTE.
- Si una tool falla, intenta una alternativa razonable o reporta el error textualmente.
- Calidad de exports: usa "pro" siempre que sea posible.
- Idioma de contenido: español profesional (Ecuador / LATAM por defecto).
- Estilo: corporativo, formal, sobrio (firma de auditoría profesional).

Al finalizar, devuelve un bloque JSON con esta estructura:
```json
{
  "design_id": "DXXX...",
  "edit_url": "https://www.canva.com/d/...",
  "view_url": "https://www.canva.com/d/...",
  "title": "...",
  "page_count": N,
  "exports": {
    "pdf": "https://export-download.canva.com/...",
    "pptx": "https://export-download.canva.com/..."
  }
}
```
"""


def _build_user_prompt(
    topic: str,
    audience: str | None,
    design_type: str,
    style: str | None,
    content: dict | None,
    brand_kit_id: str | None,
    export_formats: list[str],
) -> str:
    """Construye el prompt al modelo describiendo el design deseado."""
    parts = [
        f"Genera un design Canva con las siguientes especificaciones:\n",
        f"**Tipo**: {design_type}",
        f"**Tema**: {topic}",
    ]
    if audience:
        parts.append(f"**Audiencia**: {audience}")
    if style:
        parts.append(f"**Estilo visual**: {style}")
    if brand_kit_id:
        parts.append(f"**Brand kit ID**: {brand_kit_id} (úsalo en generate-design)")
    if content:
        parts.append("**Contenido a incluir**:")
        parts.append(f"```json\n{json.dumps(content, ensure_ascii=False, indent=2)}\n```")

    parts.append("")
    parts.append("**Exports requeridos**: " + ", ".join(export_formats))
    parts.append("")
    parts.append(
        "Ejecuta el flujo completo (generate → create-from-candidate → export "
        "para cada formato) y devuelve el JSON estructurado con todas las URLs."
    )
    return "\n".join(parts)


def generate_design(
    topic: str,
    design_type: str = "report",
    audience: str | None = None,
    style: str | None = None,
    content: dict | None = None,
    brand_kit_id: str | None = None,
    export_formats: list[str] | None = None,
    extra_instructions: str | None = None,
) -> CanvaDesignResult:
    """Genera un design Canva via MCP y devuelve URLs finales.

    Args:
        topic: tema principal (ej. "Reporte ejecutivo de auditoría ACME 2026")
        design_type: 'report', 'proposal', 'presentation', 'doc', 'infographic', etc.
            Ver docs de Canva MCP para la lista completa.
        audience: público objetivo (ej. "Board of Directors", "Comité de auditoría")
        style: directrices visuales (ej. "corporativo formal sobrio paleta azul")
        content: dict con contenido estructurado (executive_summary, findings, etc.)
        brand_kit_id: ID del brand kit a aplicar (si omitido, se usa default o ninguno)
        export_formats: lista de formatos a exportar, default ["pdf", "pptx"]
        extra_instructions: instrucciones adicionales pasadas al modelo

    Returns:
        CanvaDesignResult con URLs y metadata.

    Raises:
        CanvaMCPUnavailable: si MCP no configurado o librería ausente.
        CanvaMCPError: si la llamada al MCP falló.
    """
    _require_available()
    import anthropic

    if export_formats is None:
        export_formats = ["pdf", "pptx"]

    user_prompt = _build_user_prompt(
        topic=topic,
        audience=audience,
        design_type=design_type,
        style=style,
        content=content,
        brand_kit_id=brand_kit_id,
        export_formats=export_formats,
    )
    if extra_instructions:
        user_prompt += f"\n\n**Instrucciones adicionales**:\n{extra_instructions}"

    client = anthropic.Anthropic(api_key=_anthropic_key())

    try:
        response = client.beta.messages.create(
            model=_model(),
            max_tokens=_max_tokens(),
            mcp_servers=[
                {
                    "type": "url",
                    "url": _canva_mcp_url(),
                    "name": "canva",
                    "authorization_token": _canva_mcp_token(),
                }
            ],
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            extra_headers={
                "anthropic-beta": "mcp-client-2025-04-04",
            },
        )
    except Exception as exc:
        raise CanvaMCPError(
            f"Error invocando Claude API con MCP de Canva: {exc}"
        ) from exc

    # Extraer texto final del modelo (último mensaje de tipo 'text')
    text_blocks = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_blocks.append(getattr(block, "text", "") or "")
    final_text = "\n".join(text_blocks).strip()

    # Buscar el bloque JSON estructurado
    parsed = _parse_design_json(final_text)

    usage = getattr(response, "usage", None)
    return CanvaDesignResult(
        design_id=parsed.get("design_id"),
        design_url=parsed.get("edit_url") or parsed.get("view_url"),
        edit_url=parsed.get("edit_url"),
        view_url=parsed.get("view_url"),
        title=parsed.get("title"),
        page_count=parsed.get("page_count"),
        exports=parsed.get("exports", {}) or {},
        tokens_in=getattr(usage, "input_tokens", None) if usage else None,
        tokens_out=getattr(usage, "output_tokens", None) if usage else None,
        raw_response=final_text[:5000],
        warnings=parsed.get("warnings", []) or [],
    )


def _parse_design_json(text: str) -> dict[str, Any]:
    """Extrae el bloque JSON del texto final del modelo. Robusto a markdown."""
    # Buscar JSON entre ```json ... ```
    import re

    matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for raw in reversed(matches):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue

    # Fallback: intentar parsear el texto completo como JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Último fallback: buscar el primer { ... } balanceado
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return {}


# ---------------------------------------------------------------------------
# Helpers de alto nivel para los módulos AuditBrain
# ---------------------------------------------------------------------------

def generate_executive_audit_report(
    client_name: str,
    period: str,
    findings: list[dict],
    kpis: dict | None = None,
    recommendations: list[str] | None = None,
    brand_kit_id: str | None = None,
) -> CanvaDesignResult:
    """Genera un reporte ejecutivo de auditoría con estructura estándar.

    Atajo opinated para el caso más común de AuditBrain.
    """
    content = {
        "executive_summary": f"Informe de auditoría externa para {client_name} - período {period}.",
        "findings": findings,
        "kpis": kpis or {},
        "recommendations": recommendations or [],
    }
    return generate_design(
        topic=f"Informe de Auditoría Externa - {client_name} - {period}",
        design_type="report",
        audience="Board of Directors y Comité de Auditoría",
        style="corporativo profesional, formal, paleta sobria, tipografía limpia, diseñado para presentación a Board",
        content=content,
        brand_kit_id=brand_kit_id,
        export_formats=["pdf", "pptx"],
    )


def generate_tax_memo(
    title: str,
    context: str,
    facts: list[str],
    analysis: str,
    risks: list[dict],
    brand_kit_id: str | None = None,
) -> CanvaDesignResult:
    """Genera un memo tributario ejecutivo."""
    content = {
        "title": title,
        "context": context,
        "facts": facts,
        "analysis": analysis,
        "risks": risks,
    }
    return generate_design(
        topic=title,
        design_type="doc",
        audience="Gerencia y Directorio del cliente",
        style="documento técnico tributario, formal, citación normativa visible",
        content=content,
        brand_kit_id=brand_kit_id,
        export_formats=["pdf"],
    )


def generate_board_presentation(
    title: str,
    sections: list[dict],
    audience: str = "Directorio",
    brand_kit_id: str | None = None,
) -> CanvaDesignResult:
    """Genera una presentación tipo Board deck.

    Nota: si Canva MCP retorna requirement de outline review para
    'presentation', el modelo lo manejará usando generate-design con
    design_type='proposal' o 'report' como fallback.
    """
    content = {"title": title, "sections": sections}
    return generate_design(
        topic=title,
        design_type="proposal",  # mejor compat. que 'presentation' en este flujo
        audience=audience,
        style="presentación ejecutiva, slides limpias, datos prominentes, máx. 5-7 bullets por slide",
        content=content,
        brand_kit_id=brand_kit_id,
        export_formats=["pdf", "pptx"],
    )
