"""Modelos del Project Brain (Pydantic v2).

Fuente de verdad neutral de proveedor. Los esquemas siguen `docs/FASE1_SPEC.md` §1.
`extra="forbid"` hace que un campo desconocido falle la validación (atrapa typos).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT = ConfigDict(extra="forbid")


class BrainMeta(BaseModel):
    """Contenido de `brain.yaml` (identidad del proyecto)."""

    model_config = _STRICT

    name: str
    slug: str
    organization: str = ""
    language: str = "python"
    version: str = "0.1.0"
    inherits: str | None = None
    targets: list[str] = Field(default_factory=lambda: ["claude-code"])


class Rule(BaseModel):
    """Una regla/estándar (proviene de `rules/<id>.md`)."""

    model_config = _STRICT

    id: str
    title: str
    body: str


class MemoryEntry(BaseModel):
    """Entrada de memoria (`memory/<slug>.md` con frontmatter)."""

    model_config = _STRICT

    slug: str
    name: str
    description: str
    type: Literal["user", "feedback", "project", "reference"] = "project"
    body: str = ""


class Skill(BaseModel):
    """Skill del proyecto (`skills/<slug>/skill.yaml` + `body.md`)."""

    model_config = _STRICT

    slug: str
    name: str
    description: str
    body: str = ""


class Agent(BaseModel):
    """Rol/agente (`agents/<slug>.yaml`)."""

    model_config = _STRICT

    slug: str
    name: str
    description: str
    prompt: str
    tools: list[str] | None = None
    model: str | None = None


class Persona(BaseModel):
    """Persona objetivo (`personas/<slug>.yaml`). Solo dato en Fase 1."""

    model_config = _STRICT

    slug: str
    name: str
    description: str
    needs: list[str] = Field(default_factory=list)


class Connector(BaseModel):
    """Conector externo (`connectors/<slug>.yaml`). Sin secretos: solo referencias."""

    model_config = _STRICT

    slug: str
    name: str
    purpose: str
    type: Literal["api", "mcp"] = "api"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    auth_ref: str = ""

    @model_validator(mode="after")
    def _check_mcp(self) -> Connector:
        if self.type == "mcp" and not self.command:
            raise ValueError("un conector 'type: mcp' requiere 'command'")
        return self


class Capability(BaseModel):
    """Entrada de la matriz de capacidades (`capabilities.yaml`)."""

    model_config = _STRICT

    name: str
    modules: list[str] = Field(default_factory=list)
    covered: bool = False


class Brain(BaseModel):
    """El cerebro completo del proyecto. Colecciones ordenadas (determinista)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: BrainMeta
    rules: list[Rule] = Field(default_factory=list)
    memory: list[MemoryEntry] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    agents: list[Agent] = Field(default_factory=list)
    personas: list[Persona] = Field(default_factory=list)
    connectors: list[Connector] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
