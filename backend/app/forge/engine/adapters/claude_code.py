"""Adaptador Claude Code (L2).

Compila el cerebro a los artefactos nativos de Claude Code con el formato
byte-exacto de `docs/FASE1_SPEC.md` §2. Determinista: UTF-8, saltos '\\n'.
"""

from __future__ import annotations

from ..model import Brain
from ._mcp import mcp_servers_json
from .base import Adapter, FileSet


class ClaudeCodeAdapter(Adapter):
    name = "claude-code"
    version = "1"

    def compile(self, brain: Brain) -> FileSet:
        files: FileSet = {
            "CLAUDE.md": _claude_md(brain),
            ".mcp.json": mcp_servers_json(brain),
        }
        for skill in brain.skills:
            files[f".claude/skills/{skill.slug}/SKILL.md"] = _skill_md(skill)
        for agent in brain.agents:
            files[f".claude/agents/{agent.slug}.md"] = _agent_md(agent)
        return dict(sorted(files.items()))

    def outputs(self) -> list[str]:
        return ["CLAUDE.md", ".claude/skills/", ".claude/agents/", ".mcp.json"]


def _claude_md(brain: Brain) -> str:
    m = brain.meta
    lines = [
        f"# {m.name}",
        "",
        f"> Proyecto: {m.name} ({m.slug})",
        f"> Organización: {m.organization}",
        f"> Lenguaje: {m.language}",
        "> Generado por AuditBrain Forge — no editar a mano; "
        "edita el cerebro y recompila.",
    ]
    if brain.rules:
        lines += ["", "## Reglas"]
        for rule in brain.rules:
            lines += ["", f"### {rule.id}", "", rule.body.strip("\n")]
    if brain.memory:
        lines += ["", "## Memoria del proyecto", ""]
        lines += [f"- **{mem.name}** — {mem.description}" for mem in brain.memory]
    return "\n".join(lines) + "\n"


def _skill_md(skill) -> str:  # type: ignore[no-untyped-def]
    body = skill.body.strip("\n")
    return f"---\nname: {skill.name}\ndescription: {skill.description}\n---\n\n{body}\n"


def _agent_md(agent) -> str:  # type: ignore[no-untyped-def]
    fm = [f"name: {agent.name}", f"description: {agent.description}"]
    if agent.tools:
        fm.append(f"tools: {', '.join(agent.tools)}")
    if agent.model:
        fm.append(f"model: {agent.model}")
    prompt = agent.prompt.strip("\n")
    return "---\n" + "\n".join(fm) + "\n---\n\n" + prompt + "\n"
