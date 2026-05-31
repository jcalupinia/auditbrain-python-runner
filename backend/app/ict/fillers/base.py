"""Filler protocol + helpers for ICT 2025 Excel template manipulation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from openpyxl import Workbook, load_workbook

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ict_2025_template.xlsx"


def load_template() -> Workbook:
    """Load the official SRI ICT 2025 template preserving formulas."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"ICT template not found at {TEMPLATE_PATH}. "
            "Copy the official SRI template here before running ICT generation."
        )
    return load_workbook(TEMPLATE_PATH, data_only=False, keep_links=True)


class Filler(Protocol):
    """Protocol every anexo filler implements."""

    anexo_code: str

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill cells in the workbook for this anexo's sheet.

        Returns:
            {filled_cells: int, warnings: list[str]}

        IMPORTANT:
        - Only write cells listed in this anexo's cell_map
        - NEVER overwrite cells with formulas (preserve template)
        """
        ...
