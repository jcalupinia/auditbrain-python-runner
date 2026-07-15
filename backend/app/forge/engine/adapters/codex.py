"""Adaptador OpenAI Codex (L2).

Compila el cerebro al archivo de instrucciones de agente de Codex (`AGENTS.md`).
Determinista, UTF-8, '\\n'. En v1 solo el archivo de instrucciones.
"""

from __future__ import annotations

from ..model import Brain
from ._render import instructions_doc
from .base import Adapter, FileSet


class CodexAdapter(Adapter):
    name = "codex"
    version = "1"

    def compile(self, brain: Brain) -> FileSet:
        return {"AGENTS.md": instructions_doc(brain)}

    def outputs(self) -> list[str]:
        return ["AGENTS.md"]
