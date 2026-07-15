"""Adaptador Cursor (L2).

Compila el cerebro a las reglas de proyecto de Cursor (`.cursor/rules/*.mdc`) y
su configuración MCP (`.cursor/mcp.json`). Determinista, UTF-8, '\\n'.
"""

from __future__ import annotations

from ..model import Brain, Skill
from ._mcp import mcp_servers_json
from ._render import rules_and_memory
from .base import Adapter, FileSet


class CursorAdapter(Adapter):
    name = "cursor"
    version = "1"

    def compile(self, brain: Brain) -> FileSet:
        files: FileSet = {
            ".cursor/rules/project.mdc": _project_mdc(brain),
            ".cursor/mcp.json": mcp_servers_json(brain),
        }
        for skill in brain.skills:
            files[f".cursor/rules/skill-{skill.slug}.mdc"] = _skill_mdc(skill)
        return dict(sorted(files.items()))

    def outputs(self) -> list[str]:
        return [".cursor/rules/", ".cursor/mcp.json"]


def _project_mdc(brain: Brain) -> str:
    m = brain.meta
    lines = [
        "---",
        f"description: Contexto del proyecto {m.name} (AuditBrain Forge)",
        "globs:",
        "alwaysApply: true",
        "---",
        "",
        f"# {m.name}",
        "",
        f"- Organización: {m.organization}",
        f"- Lenguaje: {m.language}",
    ]
    body = rules_and_memory(brain)
    if body:
        lines += ["", *body]
    return "\n".join(lines) + "\n"


def _skill_mdc(skill: Skill) -> str:
    body = skill.body.strip("\n")
    return (
        f"---\ndescription: {skill.description}\n"
        f"globs:\nalwaysApply: false\n---\n\n{body}\n"
    )
