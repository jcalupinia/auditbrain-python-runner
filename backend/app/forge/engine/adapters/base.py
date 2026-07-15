"""L2 — Contrato común de los adaptadores de proveedor.

Un adaptador compila el `Brain` (neutral) a los artefactos nativos de una
herramienta, de forma **determinista**. Todo lo específico de una herramienta
vive en su adaptador; el núcleo nunca lo conoce.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..model import Brain

# FileSet: ruta relativa (POSIX) -> contenido (str, UTF-8, saltos '\n').
FileSet = dict[str, str]


class AdapterError(RuntimeError):
    """Error al compilar con un adaptador."""


class Adapter(ABC):
    """Base de todos los adaptadores."""

    #: nombre estable del destino (p. ej. "claude-code")
    name: str = ""
    #: versión del adaptador (contrato de salida versionado)
    version: str = "0"

    @abstractmethod
    def compile(self, brain: Brain) -> FileSet:
        """Compila el cerebro a un FileSet determinista."""
        raise NotImplementedError

    def outputs(self) -> list[str]:
        """Rutas o prefijos que este adaptador puede producir (para docs/tests)."""
        return []
