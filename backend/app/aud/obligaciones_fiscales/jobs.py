"""BackgroundTask orquestador del job de generación del Excel."""

from __future__ import annotations

import logging

from backend.app.aud.obligaciones_fiscales import (
    file_storage,
    service,
)
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)


def clasificar_mayor_job(job_id: int) -> None:
    """FASE 1: lee el Mayor General, clasifica sus cuentas y deja el job en
    'revision' para que el auditor apruebe."""
    from backend.app.aud.obligaciones_fiscales.mayor import (
        clasificacion_service,
        homologaciones,
    )
    from backend.app.aud.obligaciones_fiscales.mayor.clasificador import clasificar
    from backend.app.aud.obligaciones_fiscales.mayor.cuentas import perfilar
    from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor
    from backend.app.context.models import Project

    db = SessionLocal()
    try:
        service.mark_running(db, job_id)
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("clasificar_mayor_job: ToolJob %s not found", job_id)
            return

        rutas = file_storage.list_inputs(file_storage.job_dir(job_id), "mayor_general")
        if not rutas:
            service.mark_failed(db, job_id, "No hay Mayor General cargado.")
            return

        movimientos = []
        errores: list[str] = []
        hojas: list[str] = []
        for ruta in rutas:
            lectura = leer_mayor(ruta.read_bytes())
            if not lectura.mapeo_suficiente:
                service.mark_failed(
                    db, job_id,
                    f"{ruta.name}: no se reconocieron las columnas mínimas "
                    f"(faltan {', '.join(lectura.columnas_faltantes)}). "
                    f"Errores: {'; '.join(lectura.errores) or 'ninguno'}",
                )
                return
            movimientos.extend(lectura.movimientos)
            errores.extend(lectura.errores)
            hojas.extend(lectura.hojas_leidas)

        proyecto = db.get(Project, job.project_id)
        historial = homologaciones.historial_de_cliente(db, client_id=proyecto.client_id)

        perfiles = perfilar(movimientos)
        resultados = clasificar(perfiles, historial=historial)
        clasificacion_service.guardar_clasificacion(
            db, job_id=job_id, resultados=resultados, perfiles=perfiles
        )

        por_confianza: dict[str, int] = {}
        for r in resultados:
            por_confianza[r.confianza] = por_confianza.get(r.confianza, 0) + 1

        service.mark_revision(db, job_id, {
            "movimientos_leidos": len(movimientos),
            "cuentas": len(perfiles),
            "hojas_leidas": hojas,
            "por_confianza": por_confianza,
            "requieren_revision": sum(
                n for c, n in por_confianza.items() if c in ("media", "baja")
            ),
            "errores_lectura": errores[:10],
        })
        log.info("job %s clasificado: %s cuentas", job_id, len(perfiles))
    except Exception as e:  # noqa: BLE001
        log.exception("clasificar_mayor_job %s failed", job_id)
        try:
            service.mark_failed(db, job_id, str(e))
        except Exception:
            log.exception("could not mark job %s as failed", job_id)
    finally:
        db.close()


def process_job(job_id: int) -> None:
    """Procesa un job: lee inputs de /tmp, arma el libro DM, escribe output.xlsx."""
    from backend.app.aud.obligaciones_fiscales.libro.ensamblador import armar_libro
    from backend.app.aud.obligaciones_fiscales.libro.fuentes import leer_declaraciones
    from backend.app.aud.obligaciones_fiscales.mayor import clasificacion_service
    from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor

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
            "mayor_general": file_storage.list_inputs(job_dir, "mayor_general"),
            "mayor_especifico": file_storage.list_inputs(job_dir, "mayor_especifico"),
            "f101": file_storage.list_inputs(job_dir, "f101"),
        }

        movimientos = []
        for ruta in file_storage.list_inputs(job_dir, "mayor_general"):
            movimientos.extend(leer_mayor(ruta.read_bytes()).movimientos)
        f104_monthly, f103_monthly = leer_declaraciones(job_dir)

        excel_bytes = armar_libro(
            clasificacion=clasificacion_service.clasificacion_de_job(db, job_id=job_id),
            movimientos=movimientos,
            f104_monthly=f104_monthly,
            f103_monthly=f103_monthly,
            cliente=job.cliente_name,
            periodo=job.period_label,
            preparado_por=job.prepared_by_name,
            revisado_por=job.reviewed_by_name,
        )

        out = file_storage.output_path(job_dir)
        out.write_bytes(excel_bytes)

        summary = {
            "movimientos": len(movimientos),
            "f104_files_received": len(inputs.get("f104", [])),
            "f103_files_received": len(inputs.get("f103", [])),
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
