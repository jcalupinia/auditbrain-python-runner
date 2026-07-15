"""Schemas Pydantic v2 del módulo Forge."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BrainCreate(BaseModel):
    name: str
    slug: str
    organization: str = ""
    language: str = "python"
    version: str = "0.1.0"
    targets: list[str] = Field(default_factory=lambda: ["claude-code"])
    rules: list[dict] = Field(default_factory=list)
    memory: list[dict] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    agents: list[dict] = Field(default_factory=list)
    personas: list[dict] = Field(default_factory=list)
    connectors: list[dict] = Field(default_factory=list)
    capabilities: list[dict] = Field(default_factory=list)


class BrainOut(BaseModel):
    id: int
    name: str
    slug: str
    organization: str
    language: str
    version: str
    targets: list[str]


class CompileRequest(BaseModel):
    target: str = "claude-code"


class CompileOut(BaseModel):
    target: str
    files: dict[str, str]
    count: int
