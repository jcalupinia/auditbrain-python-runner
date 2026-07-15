"""Adaptador GitHub Copilot (L2).

Compila el cerebro a las instrucciones de repositorio de Copilot
(`.github/copilot-instructions.md`). Determinista, UTF-8, '\\n'.

Nota: Copilot no tiene equivalente nativo de skills/subagentes ni un formato MCP
propio estable; en v1 se compila solo el archivo de instrucciones.
"""

from __future__ import annotations

from ..model import Brain
from ._render import instructions_doc
from .base import Adapter, FileSet


class CopilotAdapter(Adapter):
    name = "copilot"
    version = "1"

    def compile(self, brain: Brain) -> FileSet:
        return {".github/copilot-instructions.md": instructions_doc(brain)}

    def outputs(self) -> list[str]:
        return [".github/copilot-instructions.md"]
