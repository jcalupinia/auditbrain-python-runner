"""Adaptador Gemini CLI (L2).

Compila el cerebro al archivo de contexto de Gemini CLI (`GEMINI.md`).
Determinista, UTF-8, '\\n'. En v1 solo el archivo de contexto.
"""

from __future__ import annotations

from ..model import Brain
from ._render import instructions_doc
from .base import Adapter, FileSet


class GeminiAdapter(Adapter):
    name = "gemini"
    version = "1"

    def compile(self, brain: Brain) -> FileSet:
        return {"GEMINI.md": instructions_doc(brain)}

    def outputs(self) -> list[str]:
        return ["GEMINI.md"]
