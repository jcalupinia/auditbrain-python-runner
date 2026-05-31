"""F-104 IVA PDF parser. Reuses obligaciones_fiscales extract_f104."""

from __future__ import annotations

from pathlib import Path

from backend.app.aud.obligaciones_fiscales.cedulas.f104_extractor import (
    extract_f104 as _of_extract_f104,
    extract_all_f104 as _of_extract_all_f104,
)


def parse_f104(pdf_bytes: bytes) -> dict | None:
    """Parse single F-104 PDF. Returns {'periodo', 'casilleros'} or None."""
    return _of_extract_f104(pdf_bytes)


def parse_all_f104(paths: list[Path]) -> tuple[dict[str, dict], list[str]]:
    """Parse multiple F-104 PDFs, group by month."""
    return _of_extract_all_f104(paths)
