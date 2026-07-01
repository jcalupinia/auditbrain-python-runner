"""Registry de herramientas del portal cliente.

Cada tool declara:
- code: string único (ej. "STUB_ECHO", "ICT_2025", "NIIF_9_ECL")
- label, description, category (para el catálogo)
- slots: dict de nombre → {mimes_allowed, required, multi}
- processor: callable(job_id) -> None que el worker invoca, o None para
  herramientas con flujo propio (caso ICT_2025 que tiene su propio
  router /client/ict/* y frontend dedicado en /tools/ICT_2025).

Nuevas tools se añaden registrando aquí. El resto del pipeline es agnóstico.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


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
    # Processor opcional: las tools "externas" (con dashboard propio como
    # ICT_2025) no usan el pipeline genérico de jobs y no necesitan
    # processor — el frontend navega a su ruta dedicada y la tool gestiona
    # su propio ciclo de vida.
    processor: Optional[Callable[[int], None]] = None
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
    # =========================================================
    # TRIBUTARIAS
    # =========================================================
    "ICT_2025": ToolConfig(
        code="ICT_2025",
        label="ICT 2025 · Informe de Cumplimiento Tributario",
        description=(
            "Genera los 10 anexos oficiales del Informe de Cumplimiento "
            "Tributario para el SRI (INDICE + A1 a A9) a partir de F-101, "
            "F-104, ATS y balance mapeado del cliente."
        ),
        category="TRIBUTARIAS",
        slots={},  # vacío — gestiona sus propios uploads vía /client/ict/*
        processor=None,  # flujo propio, no pipeline genérico
        enabled=True,
    ),

    # =========================================================
    # TESTING (oculto del catálogo público)
    # =========================================================
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


# Categorías visibles del catálogo. Orden = orden de presentación.
# Las herramientas dentro de una categoría aún vacía aparecen como
# "Próximamente" en el portal para señalar la hoja de ruta.
# La categoría TESTING existe pero NO se incluye aquí para que no aparezca
# en el catálogo del cliente final (sólo se usa en suites internas).
CATEGORIES = [
    {
        "id": "TRIBUTARIAS",
        "label": "Herramientas Tributarias",
        "description": "Cumplimiento fiscal, declaraciones SRI, anexos, conciliaciones.",
    },
    {
        "id": "NIIF",
        "label": "Herramientas NIIF",
        "description": "Cuentas por cobrar, inventarios, activos fijos, ingresos.",
    },
    {
        "id": "LABORALES",
        "label": "Herramientas Laborales",
        "description": "Nómina, IESS, décimos, utilidades, contratos.",
    },
    {
        "id": "SOCIETARIAS",
        "label": "Herramientas Societarias",
        "description": "Superintendencia, juntas, actas, distribución de utilidades.",
    },
    {
        "id": "GERENCIALES",
        "label": "Reportes Gerenciales",
        "description": "Reportes financieros y gerenciales, KPIs, análisis CFO, dashboards ejecutivos.",
    },
]
