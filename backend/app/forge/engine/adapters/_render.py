"""Bloques de render compartidos entre adaptadores (reglas + memoria)."""

from __future__ import annotations

from ..model import Brain


def rules_and_memory(brain: Brain) -> list[str]:
    """Devuelve las líneas de las secciones '## Reglas' y '## Memoria del proyecto'.

    Vacío si el cerebro no tiene reglas ni memoria. Determinista (colecciones ya
    ordenadas por el cargador).
    """
    lines: list[str] = []
    if brain.rules:
        lines.append("## Reglas")
        for rule in brain.rules:
            lines += ["", f"### {rule.id}", "", rule.body.strip("\n")]
    if brain.memory:
        if lines:
            lines.append("")
        lines += ["## Memoria del proyecto", ""]
        lines += [f"- **{mem.name}** — {mem.description}" for mem in brain.memory]
    return lines


def instructions_doc(brain: Brain) -> str:
    """Documento de instrucciones en markdown plano (identidad + reglas + memoria).

    Formato nativo de varias herramientas que consumen un único archivo de
    contexto (Copilot, Codex, Gemini CLI). Determinista.
    """
    m = brain.meta
    lines = [
        f"# {m.name}",
        "",
        f"- Organización: {m.organization}",
        f"- Lenguaje: {m.language}",
        "",
        "Generado por AuditBrain Forge — no editar a mano; "
        "edita el cerebro y recompila.",
    ]
    body = rules_and_memory(brain)
    if body:
        lines += ["", *body]
    return "\n".join(lines) + "\n"
