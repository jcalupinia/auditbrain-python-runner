"""Endpoint stateless para que los GPTs invoquen una skill con el LLM.

POST /api/v1/skill_run

- Acceso: X-API-Key (AUDITBRAIN_API_KEY) o admin JWT — igual que el runner
  (ver require_runner_access). Pensado para los GPTs server-to-server.
- Reusa los PROMPTS OFICIALES del registry (build_system_prompt) y el cliente
  LLM con fallback multi-proveedor (chat_complete). El razonamiento corre
  server-side: los tokens NO se gastan en la página del GPT.
- Sin estado: no crea conversación ni toca la base de datos. El GPT manda
  el módulo/skill + el input, y recibe el output ya procesado.

Nota de proveedor: chat_complete elige el proveedor según el orden free-first
(gemini > groq > openrouter > anthropic > openai). Para forzar Claude, definir
en Render: AUDITBRAIN_LLM_PROVIDER=anthropic
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.auth.deps import require_runner_access
from backend.app.chat import providers
from backend.app.chat.skills_registry import (
    build_system_prompt,
    default_skill_for_module,
    get_skill,
)

router = APIRouter(tags=["skill_run"], dependencies=[Depends(require_runner_access)])


class SkillRunRequest(BaseModel):
    module_code: str | None = Field(
        default=None,
        max_length=8,
        description="Módulo del GPT: ADV, AUD, TAX, LEG, FIN, CYB, DATA, AUT, GOV, MKT, CRE.",
    )
    skill_id: str | None = Field(
        default=None,
        description="Slug de la skill (ej. 'audit-findings'). Si se omite, se usa la skill por defecto del módulo.",
    )
    input: str = Field(
        ...,
        min_length=1,
        description="Texto o datos del usuario a procesar con la skill seleccionada.",
    )


class SkillRunResponse(BaseModel):
    skill: str | None = Field(description="Slug de la skill efectivamente aplicada.")
    skill_name: str | None = Field(default=None, description="Nombre legible de la skill.")
    module_code: str | None = None
    output: str = Field(description="Resultado generado por el LLM con el prompt oficial.")
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None


@router.post("/skill_run", response_model=SkillRunResponse)
def skill_run(body: SkillRunRequest) -> SkillRunResponse:
    """Aplica una skill oficial al input del GPT y devuelve el resultado."""
    module_code = (body.module_code or "").upper() or None

    # Resolver qué skill se aplica (para reportarla en la respuesta).
    skill = get_skill(body.skill_id) or default_skill_for_module(module_code)

    # System prompt oficial (base + skill). build_system_prompt es tolerante:
    # si no hay skill/módulo válido, devuelve al menos el prompt base.
    system = build_system_prompt(module_code=module_code, skill_id=body.skill_id)

    try:
        llm = providers.chat_complete(
            messages=[{"role": "user", "content": body.input}],
            system=system,
        )
    except providers.ProviderUnavailable as exc:
        # 503: el servidor no tiene proveedor LLM configurado o todos fallaron.
        # No se inventa respuesta — se reporta el error honesto.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return SkillRunResponse(
        skill=skill.id if skill else None,
        skill_name=skill.name if skill else None,
        module_code=module_code,
        output=llm.content,
        model=llm.model,
        tokens_in=llm.tokens_in,
        tokens_out=llm.tokens_out,
    )
