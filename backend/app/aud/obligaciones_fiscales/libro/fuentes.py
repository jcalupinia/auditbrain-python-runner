"""Hojas de datos fuente: los casilleros declarados al SRI.

Se apoyan en los builders del ICT, que ya generan la matriz completa de
casilleros por mes y devuelven el mapa de direcciones que las cédulas usan
para referenciarlas POR FÓRMULA.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl.workbook import Workbook

from backend.app.ict.fillers.source_data_sheets import (
    build_f103_sheet,
    build_f104_sheet,
)


def a_periodos_anuales(month_data: dict) -> dict:
    """{"01": {"periodo": "01/2025", ...}} → {"2025-01": {"casilleros": {...}}}.

    Los builders del ICT indexan por período completo; el extractor de F-104
    de esta herramienta indexa por mes. Los meses sin período detectado se
    descartan: sin año no se puede ubicar la columna.
    """
    salida: dict[str, dict] = {}
    for datos in (month_data or {}).values():
        periodo = (datos or {}).get("periodo")
        if not periodo or "/" not in str(periodo):
            continue
        mes, anio = str(periodo).split("/", 1)
        salida[f"{anio}-{int(mes):02d}"] = {"casilleros": datos.get("casilleros", {})}
    return salida


def construir_hojas_de_casilleros(
    wb: Workbook, *, f104_monthly: dict, f103_monthly: dict
) -> dict[str, dict]:
    """Crea DATOS F-104 y DATOS F-103. Devuelve {"f104": lookup, "f103": lookup}."""
    return {
        "f104": build_f104_sheet(wb, f104_monthly or {}),
        "f103": build_f103_sheet(wb, f103_monthly or {}),
    }


def leer_declaraciones(job_dir: Path) -> tuple[dict, dict]:
    """Lee los PDFs subidos del job y los deja en formato de períodos anuales."""
    from backend.app.aud.obligaciones_fiscales import file_storage
    from backend.app.aud.obligaciones_fiscales.cedulas.f104_extractor import (
        extract_all_f104,
    )
    from backend.app.ict.parsers.f103_pdf import parse_all_f103

    f104_mes, _ = extract_all_f104(file_storage.list_inputs(job_dir, "f104"))
    f103_monthly, _ = parse_all_f103(file_storage.list_inputs(job_dir, "f103"))
    return a_periodos_anuales(f104_mes), (f103_monthly or {})
