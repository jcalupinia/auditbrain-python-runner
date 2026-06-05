"""LLM motor for interpreting ICT anexos via Anthropic Claude API.

Each anexo is passed to Claude with a tool-use forced schema. The response
is validated with Pydantic. Failures degrade gracefully to a fallback
interpretation that signals 'review needed'.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from openpyxl.workbook import Workbook

from backend.app.ict.audit.schemas import AnexoInterpretation

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "auditor_tributario_ec.md"

# Modelo Anthropic por defecto. Sonnet 4.5 es la versión más reciente verificada
# en producción al 2026-06-04 (publicada 2025-09-29). Calibra precio/calidad:
# suficiente capacidad de razonamiento contable + costo ~$0.003/1K input tokens.
#
# IMPORTANTE: el ID debe ser un modelo EXISTENTE en la API Anthropic.
# Sobreescribir via env var ICT_LLM_MODEL cuando Anthropic publique uno nuevo.
# Si el modelo no existe, _fallback_interpretation cubre el caso devolviendo
# confianza_modelo="baja" + requiere_revision_humana=True (no crashea).
#
# Historial de cambios:
#   2026-06-04: claude-sonnet-4-7-20260101 (ID futuro, no existía) →
#              claude-sonnet-4-5-20250929 (verificado adversarial workflow).
DEFAULT_MODEL = os.getenv("ICT_LLM_MODEL", "claude-sonnet-4-5-20250929")

# Performance tuning (calibrado 2026-06-05 tras reporte cliente de demora):
# - TIMEOUT 30s era largo: ~95s peor caso por anexo con 3 retries × backoff.
# - Bajamos a 15s timeout + 1 retry (= 2 intentos max) → ~30s peor caso.
# Si necesitás más resiliencia en alguna sesión, override via env vars.
DEFAULT_TIMEOUT = float(os.getenv("ICT_LLM_TIMEOUT", "15.0"))
DEFAULT_MAX_RETRIES = int(os.getenv("ICT_LLM_MAX_RETRIES", "2"))

# Kill switch: si ICT_LLM_ENABLED=false, NO se llama a la API Anthropic en
# ningún anexo. Todas las interpretaciones devuelven el fallback inmediato
# (confianza=baja, requiere_revision_humana=True). Util para:
#   - Cortes de Anthropic / desactivar IA temporalmente sin redeploy
#   - Sesiones donde el cliente quiere descarga rápida sin esperar el LLM
#   - Desarrollo local sin gastar tokens
# El sistema sigue 100% funcional, solo que las hojas ARTEFACTO A1 /
# AUDITORIA muestran fallback text en lugar de análisis IA real.
ICT_LLM_ENABLED = os.getenv("ICT_LLM_ENABLED", "true").lower() in ("true", "1", "yes")


def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def extract_anexo_data(wb: Workbook, anexo_code: str) -> dict[str, Any]:
    """Extract the raw rows from an anexo sheet into a serializable dict."""
    if anexo_code not in wb.sheetnames:
        return {"codigo": anexo_code, "rows": [], "warning": "Hoja no existe"}
    sheet = wb[anexo_code]
    rows: list[dict[str, Any]] = []
    headers: list[str] = []
    for idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        if idx == 1:
            headers = [str(c) if c is not None else "" for c in row]
            continue
        if all(c is None for c in row):
            continue
        rows.append({
            headers[i] if i < len(headers) else f"col_{i}": (
                float(c) if isinstance(c, (int, float)) else
                (str(c) if c is not None else None)
            )
            for i, c in enumerate(row)
        })
    return {"codigo": anexo_code, "headers": headers, "rows": rows}


def _fallback_interpretation(code: str, nombre: str = "") -> AnexoInterpretation:
    """Return a graceful fallback when the LLM cannot be reached or validated."""
    return AnexoInterpretation(
        anexo_codigo=code,
        anexo_nombre=nombre or code,
        resumen_ejecutivo=(
            "Análisis IA no disponible en esta sesión. "
            "El auditor debe revisar este anexo manualmente."
        ),
        findings=[],
        confianza_modelo="baja",
        requiere_revision_humana=True,
        timestamp_analisis=datetime.utcnow(),
        modelo_usado="fallback",
        tokens_consumidos=0,
    )


def _render_prompt(
    anexo_codigo: str,
    anexo_nombre: str,
    anexo_data: dict[str, Any],
    contexto: dict[str, Any],
) -> str:
    template = _load_prompt_template()
    return (
        template
        .replace("{anexo_codigo}", anexo_codigo)
        .replace("{anexo_nombre}", anexo_nombre)
        .replace("{razon_social}", str(contexto.get("razon_social", "")))
        .replace("{ruc}", str(contexto.get("ruc", "")))
        .replace("{periodo}", str(contexto.get("periodo", "")))
        .replace("{anexo_data_json}", json.dumps(anexo_data, indent=2, default=str))
        .replace("{a1_metrics_json}",
                 json.dumps(contexto.get("a1_metrics", {}), indent=2, default=str))
        .replace("{catalogo_relevante_json}",
                 json.dumps(contexto.get("catalogo", {}), indent=2, default=str))
    )


async def interpret_anexo(
    anexo_codigo: str,
    anexo_data: dict[str, Any],
    contexto: dict[str, Any],
    *,
    anthropic_client: Any = None,
    model: str = DEFAULT_MODEL,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
) -> AnexoInterpretation:
    """Interpret a single anexo via Claude, with retries and graceful fallback.

    Optimización 2026-06-05: si ANTHROPIC_API_KEY no está seteada, devuelve
    fallback inmediato sin intentar conectar (evita ~15-30s de timeout
    inútil por anexo cuando la key está ausente)."""
    anexo_nombre = contexto.get(f"nombre_{anexo_codigo}", anexo_codigo)

    if anthropic_client is None and not os.getenv("ANTHROPIC_API_KEY"):
        log.info(
            "ANTHROPIC_API_KEY no configurada → fallback inmediato para %s",
            anexo_codigo,
        )
        return _fallback_interpretation(anexo_codigo, anexo_nombre)

    if anthropic_client is None:
        try:
            from anthropic import AsyncAnthropic
            anthropic_client = AsyncAnthropic()
        except Exception as exc:
            log.warning("Anthropic SDK not available: %s", exc)
            return _fallback_interpretation(anexo_codigo, anexo_nombre)

    prompt = _render_prompt(anexo_codigo, anexo_nombre, anexo_data, contexto)
    schema = AnexoInterpretation.model_json_schema()

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            response = await asyncio.wait_for(
                anthropic_client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                    tools=[{
                        "name": "save_interpretation",
                        "description": "Persist the structured interpretation",
                        "input_schema": schema,
                    }],
                    tool_choice={"type": "tool", "name": "save_interpretation"},
                ),
                timeout=timeout,
            )
            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and \
                   getattr(block, "name", None) == "save_interpretation":
                    raw = block.input
                    usage = getattr(response, "usage", None)
                    if usage is not None:
                        raw["tokens_consumidos"] = (
                            getattr(usage, "input_tokens", 0)
                            + getattr(usage, "output_tokens", 0)
                        )
                    raw["modelo_usado"] = model
                    if "timestamp_analisis" not in raw:
                        raw["timestamp_analisis"] = datetime.utcnow().isoformat()
                    return AnexoInterpretation.model_validate(raw)
            raise ValueError("No tool_use block in response")
        except Exception as exc:
            last_exc = exc
            log.warning(
                "interpret_anexo %s attempt %d/%d failed: %s",
                anexo_codigo, attempt + 1, max_retries, exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

    log.error("interpret_anexo %s exhausted retries: %s", anexo_codigo, last_exc)
    return _fallback_interpretation(anexo_codigo, anexo_nombre)


async def interpret_all_anexos(
    wb: Workbook,
    contexto: dict[str, Any],
    *,
    anthropic_client: Any = None,
) -> dict[str, AnexoInterpretation]:
    """Interpret all 9 anexos in parallel.

    Si `ICT_LLM_ENABLED=false`, devuelve fallback inmediato sin llamar
    a la API (kill switch para acelerar descarga / evitar costos)."""
    codes = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
    if not ICT_LLM_ENABLED:
        log.info("ICT_LLM_ENABLED=false → devolviendo fallback para los 9 anexos")
        return {c: _fallback_interpretation(c) for c in codes}
    data_per_code = {c: extract_anexo_data(wb, c) for c in codes}
    tasks = [
        interpret_anexo(
            anexo_codigo=c,
            anexo_data=data_per_code[c],
            contexto=contexto,
            anthropic_client=anthropic_client,
        )
        for c in codes
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: dict[str, AnexoInterpretation] = {}
    for code, result in zip(codes, results):
        if isinstance(result, Exception):
            log.warning("interpret_all_anexos %s exception: %s", code, result)
            out[code] = _fallback_interpretation(code)
        else:
            out[code] = result
    return out
