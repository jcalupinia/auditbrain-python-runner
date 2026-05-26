"""BackgroundTask orquestador del job de generación del Excel."""

from __future__ import annotations

import logging

from backend.app.aud.obligaciones_fiscales import (
    excel_assembler,
    file_storage,
    service,
)
from backend.app.aud.obligaciones_fiscales.cedulas import dm6_iva, dm7_retenciones
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)


def process_job(job_id: int) -> None:
    """Procesa un job: lee inputs de /tmp, computa cédulas, escribe output.xlsx."""
    db = SessionLocal()
    try:
        service.mark_running(db, job_id)
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("process_job: ToolJob %s not found", job_id)
            return

        job_dir = file_storage.job_dir(job_id)
        inputs = {
            "f103": file_storage.list_inputs(job_dir, "f103"),
            "f104": file_storage.list_inputs(job_dir, "f104"),
            "ats": file_storage.list_inputs(job_dir, "ats"),
            "mayor_compras": file_storage.list_inputs(job_dir, "mayor_compras"),
            "mayor_ventas": file_storage.list_inputs(job_dir, "mayor_ventas"),
            "f101": file_storage.list_inputs(job_dir, "f101"),
        }

        dm6_result = dm6_iva.compute(inputs)
        dm7_result = dm7_retenciones.compute(inputs)

        excel_bytes = excel_assembler.assemble(
            cliente_name=job.cliente_name,
            period_label=job.period_label,
            period_end=job.period_end,
            prepared_by_name=job.prepared_by_name,
            reviewed_by_name=job.reviewed_by_name,
            dm6_data=dm6_result,
            dm7_data=dm7_result,
        )

        out = file_storage.output_path(job_dir)
        out.write_bytes(excel_bytes)

        summary = {
            "dm6_months_with_data": dm6_result.get("total_months_with_data", 0),
            "dm7_months_with_data": dm7_result.get("total_months_with_data", 0),
            "f104_files_received": len(inputs.get("f104", [])),
            "f103_files_received": len(inputs.get("f103", [])),
            "errors": {
                "dm6": dm6_result.get("errors", []),
                "dm7": dm7_result.get("errors", []),
            },
            "excel_size_bytes": len(excel_bytes),
        }
        service.mark_done(db, job_id, summary)
        log.info("job %s done", job_id)
    except Exception as e:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        try:
            service.mark_failed(db, job_id, str(e))
        except Exception:
            log.exception("could not mark job %s as failed", job_id)
    finally:
        db.close()
