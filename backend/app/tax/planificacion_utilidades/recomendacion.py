"""Agente híbrido: arma el prompt con las cifras deterministas y pide a la IA
la narrativa de recomendación. Cumple los 6 controles de interpretación IA
(ver backend/app/ict/audit/interpreter.py): la IA NO calcula ni inventa
números; siempre se marca requiere_revision_humana y el frontend muestra el
disclaimer."""

from __future__ import annotations

from backend.app.tax.planificacion_utilidades.schemas import RecomendacionResponse

_NOMBRES = {
    "sin": "Sin estrategia",
    "div": "Distribución de dividendos",
    "mix": "Capitalización + Distribución",
    "cap": "Solo capitalización",
}


def _call_llm(prompt: str) -> str:  # pragma: no cover - se mockea en tests
    """Llama al proveedor IA configurado vía backend/app/chat/providers.

    chat_complete elige el proveedor (gemini>groq>openrouter>anthropic>openai),
    reintenta con el siguiente si uno falla, y levanta ProviderUnavailable si no
    hay ninguno configurado (lo captura build_recomendacion -> fallback)."""
    from backend.app.chat.providers import chat_complete

    system = (
        "Eres un asesor tributario senior en Ecuador. Redactas recomendaciones "
        "ejecutivas claras y prudentes. No inventas cifras."
    )
    return chat_complete([{"role": "user", "content": prompt}], system=system).content


def _prompt(empresa: str, recomendado: str, comparacion: dict) -> str:
    tot = comparacion.get(recomendado, {}).get("totales", {})
    return (
        "Eres un asesor tributario senior (Ecuador, régimen de pago a cuenta "
        "sobre utilidades no distribuidas, vigente desde sep-2025). Con base en "
        f"estas cifras YA CALCULADAS (no las recalcules) para {empresa}, redacta "
        "una recomendación ejecutiva (máx. 180 palabras) para la gerencia, "
        f"justificando el escenario '{_NOMBRES.get(recomendado, recomendado)}'. "
        "Menciona la regla de los 2 años (costo muerto) y la fecha de corte 31-jul. "
        f"Totales del escenario recomendado: {tot}. "
        "No inventes números distintos a los provistos."
    )


def build_recomendacion(empresa: str, recomendado: str, comparacion: dict) -> RecomendacionResponse:
    prompt = _prompt(empresa, recomendado, comparacion)
    try:
        narrativa = _call_llm(prompt).strip()
        confianza = "alta" if narrativa else "baja"
        return RecomendacionResponse(
            narrativa=narrativa,
            confianza_modelo=confianza,
            requiere_revision_humana=True,
        )
    except Exception:  # noqa: BLE001 — fallback graceful (control 1)
        nombre = _NOMBRES.get(recomendado, recomendado)
        return RecomendacionResponse(
            narrativa=(
                f"Recomendación (sin IA disponible): aplicar el escenario "
                f"'{nombre}'. Revise las cifras de la comparación y la regla de "
                "los 2 años antes de decidir."
            ),
            confianza_modelo="baja",
            requiere_revision_humana=True,
        )
