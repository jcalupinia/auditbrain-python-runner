"""Adaptador Windsurf (L2).

Compila el cerebro a las reglas de Windsurf (`.windsurf/rules/*.md`).
Determinista, UTF-8, '\\n'.
"""

from __future__ import annotations

from ..model import Brain, Skill
from ._render import rules_and_memory
from .base import Adapter, FileSet


class WindsurfAdapter(Adapter):
    name = "windsurf"
    version = "1"

    def compile(self, brain: Brain) -> FileSet:
        files: FileSet = {".windsurf/rules/project.md": _project_rule(brain)}
        for skill in brain.skills:
            files[f".windsurf/rules/skill-{skill.slug}.md"] = _skill_rule(skill)
        return dict(sorted(files.items()))

    def outputs(self) -> list[str]:
        return [".windsurf/rules/"]


def _project_rule(brain: Brain) -> str:
    m = brain.meta
    lines = [
        "---",
        "trigger: always_on",
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


def _skill_rule(skill: Skill) -> str:
    body = skill.body.strip("\n")
    return (
        f"---\ntrigger: model_decision\n"
        f"description: {skill.description}\n---\n\n{body}\n"
    )
