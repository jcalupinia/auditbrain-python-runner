# backend/app/aud/informe_cumplimiento_tributario/jobs.py
"""BackgroundTask que genera el informe Word."""

from __future__ import annotations

import json
import logging

from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.aud.informe_cumplimiento_tributario import docx_assembler, service
from backend.app.aud.informe_cumplimiento_tributario.parsers import (
    declaracion_ir,
    informe_auditoria_externa as iae,
)
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)

DEFAULT_OTROS_ASUNTOS = (
    "En cumplimiento de lo dispuesto en la Resolución del Servicio de Rentas "
    "Internas No. NAC-DGERCGC15-00003218, publicada en el Registro Oficial No. "
    "660 del 31 de diciembre de 2015, y sus reformas, incluyendo la Resolución "
    "No. NAC-DGERCGC21-00000030, informamos que no existen recomendaciones sobre "
    "aspectos de carácter tributario."
)
DEFAULT_PARTE_III = (
    "Con base en nuestra revisión de ciertas áreas seleccionadas, informamos que "
    "no hemos identificado observaciones en el sistema de control interno "
    "contable que tengan relación con aspectos tributarios, de acuerdo con lo "
    "requerido por el Servicio de Rentas Internas."
)


def _load_params(job_dir) -> dict:
    files = file_storage.list_inputs(job_dir, "params")
    if not files:
        return {}
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _first(job_dir, slot):
    files = file_storage.list_inputs(job_dir, slot)
    return files[0].read_bytes() if files else None


def process_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        service.mark_running(db, job_id)
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("process_job: ToolJob %s no existe", job_id)
            return

        job_dir = file_storage.job_dir(job_id)
        params = _load_params(job_dir)

        # --- Parsers (con override manual del form) ---
        errores: list[str] = []
        inf_bytes = _first(job_dir, "informe_auditoria_externa")
        f101_bytes = _first(job_dir, "declaracion_ir")
        inf = iae.parse(inf_bytes) if inf_bytes else {"fecha_emision": None, "marco_contable": "pymes", "errores": ["Falta el Informe de Auditoría Externa."]}
        f101 = declaracion_ir.parse(f101_bytes) if f101_bytes else {"fecha_declaracion_ir": None, "errores": ["Falta el F-101."]}
        errores += inf.get("errores", []) + f101.get("errores", [])

        fecha_emision = params.get("override_fecha_emision") or inf.get("fecha_emision")
        marco = params.get("override_marco_contable") or inf.get("marco_contable") or "pymes"
        fecha_decl = params.get("override_fecha_declaracion_ir") or f101.get("fecha_declaracion_ir")

        # --- Recomendaciones ---
        if params.get("hay_recomendaciones") and params.get("texto_recomendaciones"):
            bloque = params["texto_recomendaciones"]
            bloque_otros = bloque
            bloque_parte_iii = bloque
        else:
            bloque_otros = DEFAULT_OTROS_ASUNTOS
            bloque_parte_iii = DEFAULT_PARTE_III

        # --- Ensamblar ---
        docx_bytes = docx_assembler.assemble(
            firma_auditora=job.firma_auditora,
            razon_social=job.cliente_name,
            ejercicio=job.period_label,
            fecha_emision=fecha_emision,
            fecha_declaracion_ir=fecha_decl,
            fecha_carga_sri=params.get("fecha_carga_sri", ""),
            marco_contable=marco,
            bloque_otros_asuntos=bloque_otros,
            bloque_parte_iii=bloque_parte_iii,
        )
        (job_dir / "output.docx").write_bytes(docx_bytes)

        service.mark_done(db, job_id, {
            "fecha_emision": fecha_emision,
            "marco_contable": marco,
            "fecha_declaracion_ir": fecha_decl,
            "warnings": errores,
            "docx_size_bytes": len(docx_bytes),
        })
        log.info("ict-report job %s done", job_id)
    except Exception as e:  # noqa: BLE001
        log.exception("ict-report job %s failed", job_id)
        try:
            service.mark_failed(db, job_id, str(e))
        except Exception:
            log.exception("no se pudo marcar failed el job %s", job_id)
    finally:
        db.close()
