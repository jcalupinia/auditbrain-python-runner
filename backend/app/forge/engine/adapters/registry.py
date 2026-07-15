"""Registro de adaptadores disponibles."""

from __future__ import annotations

from .base import Adapter
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .copilot import CopilotAdapter
from .cursor import CursorAdapter
from .gemini import GeminiAdapter
from .windsurf import WindsurfAdapter

_REGISTRY: dict[str, Adapter] = {}


def register(adapter: Adapter) -> None:
    _REGISTRY[adapter.name] = adapter


def get_adapter(name: str) -> Adapter:
    """Devuelve el adaptador ``name`` o lanza ``KeyError`` con la lista disponible."""
    if name not in _REGISTRY:
        disponibles = ", ".join(list_adapters()) or "(ninguno)"
        raise KeyError(f"Adaptador '{name}' no encontrado. Disponibles: {disponibles}")
    return _REGISTRY[name]


def list_adapters() -> list[str]:
    return sorted(_REGISTRY)


# Registro de adaptadores integrados.
register(ClaudeCodeAdapter())
register(CursorAdapter())
register(CopilotAdapter())
register(CodexAdapter())
register(GeminiAdapter())
register(WindsurfAdapter())
