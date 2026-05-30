"""Registry de herramientas del portal cliente.

Cada tool declara:
- code: string único (ej. "STUB_ECHO", "ICT_2025", "NIIF_9_ECL")
- label, description, category (para el catálogo)
- slots: dict de nombre → {mimes_allowed, required, multi}
- processor: callable(job_id) -> None que el worker invoca

Nuevas tools se añaden registrando aquí. El resto del pipeline es agnóstico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class SlotConfig:
    mimes_allowed: frozenset[str]
    required: bool = True
    multi: bool = False  # True permite múltiples archivos en el slot


@dataclass(frozen=True)
class ToolConfig:
    code: str
    label: str
    description: str
    category: str
    slots: dict[str, SlotConfig]
    processor: Callable[[int], None]
    enabled: bool = True


# Stub processor para validar pipeline end-to-end sin lógica real
def _stub_echo_processor(job_id: int) -> None:
    """Procesador stub: copia el primer input como output.xlsx, marca done."""
    from backend.app.aud.obligaciones_fiscales import file_storage
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            return
        job.status = "processing"
        db.commit()

        job_dir = file_storage.job_dir(job_id)
        all_inputs = file_storage.list_inputs(job_dir)
        if not all_inputs:
            job.status = "error"
            job.error_message = "No se encontraron inputs."
            db.commit()
            return

        # Copia byte-a-byte del primer input como output
        out_path = file_storage.output_path(job_dir)
        out_path.write_bytes(all_inputs[0].read_bytes())

        job.status = "done"
        job.summary_json = {"echo_bytes": len(out_path.read_bytes())}
        db.commit()
    finally:
        db.close()


TOOLS: dict[str, ToolConfig] = {
    "STUB_ECHO": ToolConfig(
        code="STUB_ECHO",
        label="Stub Echo (testing)",
        description="Herramienta de prueba: copia el archivo subido como output.",
        category="TESTING",
        slots={
            "input": SlotConfig(
                mimes_allowed=frozenset({"application/pdf", "text/plain"}),
                required=True,
                multi=False,
            ),
        },
        processor=_stub_echo_processor,
        enabled=True,
    ),
}


def get_tool(code: str) -> ToolConfig:
    if code not in TOOLS:
        raise KeyError(f"Tool {code} no está registrada.")
    return TOOLS[code]


def list_enabled_tools() -> list[ToolConfig]:
    return [t for t in TOOLS.values() if t.enabled]


# Categorías para el catálogo (más adelante, herramientas NIIF se añaden aquí)
CATEGORIES = [
    {"id": "CUMPLIMIENTO_TRIBUTARIO", "label": "Cumplimiento Tributario"},
    {"id": "NIIF_CXC", "label": "NIIF - Cuentas por Cobrar"},
    {"id": "NIIF_INVENTARIOS", "label": "NIIF - Inventarios"},
    {"id": "NIIF_ACTIVOS_FIJOS", "label": "NIIF - Activos Fijos"},
    {"id": "NIIF_INGRESOS", "label": "NIIF - Ingresos"},
    {"id": "TESTING", "label": "Pruebas (interno)"},
]
