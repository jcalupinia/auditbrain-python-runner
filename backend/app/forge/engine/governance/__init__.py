"""Gobernanza (L6) vendorizada para la plataforma."""

from .audit import GENESIS, _CAMPOS_FIRMADOS, compute_hash

__all__ = ["compute_hash", "GENESIS", "_CAMPOS_FIRMADOS"]
