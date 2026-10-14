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


def leer_mayores_del_job(job_id: int):
    """Lee el Mayor General (completo) y los Mayores específicos de un job.

    El Mayor General ya no es indispensable: basta con él o con al menos un
    Mayor específico. Cada Mayor específico trae su categoría declarada (un
    archivo = una categoría; puede incluir varias cuentas, todas de esa
    categoría), que se devuelve en ``declaradas`` {codigo: categoria} para que
    la clasificación la respete.

    Devuelve: (movimientos, declaradas, hojas, errores, ilegibles), donde
    ``ilegibles`` lista (nombre, columnas_faltantes) de los archivos cuyo
    encabezado no se reconoció.
    """
    from backend.app.aud.obligaciones_fiscales.mayor.reader import leer_mayor

    job_dir = file_storage.job_dir(job_id)
    movimientos: list = []
    declaradas: dict[str, str] = {}
    hojas: list[str] = []
    errores: list[str] = []
    ilegibles: list[tuple[str, list[str]]] = []

    # Mapeo MANUAL de columnas por archivo (cuando el auditor lo asignó porque
    # el detector no reconoció el encabezado). Aplica a general y específicos.
    col_map = file_storage.read_mayor_columnas_mapeo(job_dir)

    def _acumular(ruta, categoria: str | None = None) -> None:
        lectura = leer_mayor(ruta.read_bytes(), mapeo_manual=col_map.get(ruta.name))
        if not lectura.mapeo_suficiente:
            ilegibles.append((ruta.name, list(lectura.columnas_faltantes)))
            return
        movimientos.extend(lectura.movimientos)
        hojas.extend(lectura.hojas_leidas)
        errores.extend(lectura.errores)
        if categoria:
            for m in lectura.movimientos:
                if m.codigo:
                    declaradas[m.codigo] = categoria

    for ruta in file_storage.list_inputs(job_dir, "mayor_general"):
        _acumular(ruta)

    mapeo = file_storage.read_mayor_especifico_mapeo(job_dir)
    for ruta in file_storage.list_inputs(job_dir, "mayor_especifico"):
        _acumular(ruta, categoria=mapeo.get(ruta.name) or None)

    return movimientos, declaradas, hojas, errores, ilegibles


def clasificar_mayor_job(job_id: int) -> None:
    """FASE 1: lee los mayores (general y/o específicos), clasifica sus cuentas
    y deja el job en 'revision' para que el auditor apruebe."""
    from backend.app.aud.obligaciones_fiscales.mayor import (
        clasificacion_service,
        homologaciones,
    )
    from backend.app.aud.obligaciones_fiscales.mayor.clasificador import clasificar
    from backend.app.aud.obligaciones_fiscales.mayor.cuentas import perfilar
    from backend.app.context.models import Project

    db = SessionLocal()
    try:
        service.mark_running(db, job_id)
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("clasificar_mayor_job: ToolJob %s not found", job_id)
            return

        movimientos, declaradas, hojas, errores, ilegibles = leer_mayores_del_job(job_id)

        if not movimientos:
            if ilegibles:
                nombre, faltan = ilegibles[0]
                service.mark_failed(
                    db, job_id,
                    f"{nombre}: no se reconocieron las columnas mínimas "
                    f"(faltan {', '.join(faltan)}).",
                )
            else:
                service.mark_failed(
                    db, job_id,
                    "No hay un Mayor General ni Mayores específicos legibles cargados.",
                )
            return
        # Archivos que no se pudieron leer, pero había otros que sí: se avisa.
        for nombre, faltan in ilegibles:
            errores.append(f"{nombre}: no se reconocieron las columnas (faltan {', '.join(faltan)}).")

        proyecto = db.get(Project, job.project_id)
        historial = homologaciones.historial_de_cliente(db, client_id=proyecto.client_id)

        perfiles = perfilar(movimientos)
        resultados = clasificar(perfiles, historial=historial, declaradas=declaradas)
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


def _generar_output_libro(db, job: ToolJob, job_id: int) -> dict:
    """Trabajo PESADO del Libro DM: lee inputs del disco, arma el libro (openpyxl, una celda
    por movimiento del mayor) y escribe ``output.xlsx``. Devuelve el ``summary``.

    Lo usan AMBOS caminos: el proceso de uvicorn (flag O2 apagado) y el subproceso aislado
    (``aislado._trabajo``, flag O2 encendido). No toca el estado del job (lo marca el llamador)."""
    from backend.app.aud.obligaciones_fiscales.libro.ensamblador import armar_libro
    from backend.app.aud.obligaciones_fiscales.libro.fuentes import (
        leer_ats,
        leer_declaraciones,
    )
    from backend.app.aud.obligaciones_fiscales.mayor import clasificacion_service

    job_dir = file_storage.job_dir(job_id)
    inputs = {
        "f103": file_storage.list_inputs(job_dir, "f103"),
        "f104": file_storage.list_inputs(job_dir, "f104"),
        "ats": file_storage.list_inputs(job_dir, "ats"),
        "mayor_general": file_storage.list_inputs(job_dir, "mayor_general"),
        "mayor_especifico": file_storage.list_inputs(job_dir, "mayor_especifico"),
        "f101": file_storage.list_inputs(job_dir, "f101"),
    }

    # Movimientos del Mayor General y de los Mayores específicos (ambos
    # entran a los cruces; el general ya no es indispensable).
    movimientos, _declaradas, _hojas, _errores, _ilegibles = leer_mayores_del_job(job_id)
    f104_monthly, f103_monthly = leer_declaraciones(job_dir)

    excel_bytes = armar_libro(
        clasificacion=clasificacion_service.clasificacion_de_job(db, job_id=job_id),
        movimientos=movimientos,
        f104_monthly=f104_monthly,
        f103_monthly=f103_monthly,
        ats_resumenes=leer_ats(job_dir),
        cliente=job.cliente_name,
        periodo=job.period_label,
        preparado_por=job.prepared_by_name,
        revisado_por=job.reviewed_by_name,
    )

    out = file_storage.output_path(job_dir)
    out.write_bytes(excel_bytes)

    return {
        "movimientos": len(movimientos),
        "f104_files_received": len(inputs.get("f104", [])),
        "f103_files_received": len(inputs.get("f103", [])),
        "excel_size_bytes": len(excel_bytes),
    }


def _o2_activo() -> bool:
    """Flag ``OF_O2_SUBPROCESO``: aislar el armado del Libro DM en un subproceso (anti-OOM).
    Apagado por defecto = comportamiento anterior (armado en el proceso de uvicorn)."""
    import os
    return (os.getenv("OF_O2_SUBPROCESO", "") or "").strip().lower() in ("1", "true", "yes", "on")


def process_job(job_id: int) -> None:
    """Procesa un job: lee inputs de /tmp, arma el libro DM, escribe output.xlsx.

    Con ``OF_O2_SUBPROCESO`` el armado corre en un subproceso aislado (vive y muere su pico de
    memoria, sin tumbar uvicorn) bajo el semáforo de proceso pesado; apagado, corre en proceso."""
    db = SessionLocal()
    try:
        service.mark_running(db, job_id)
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("process_job: ToolJob %s not found", job_id)
            return

        if _o2_activo():
            from backend.app.aud.niif.procesadores.concurrencia import (
                ProcesoOcupado,
                limite_proceso_pesado,
            )
            from backend.app.aud.obligaciones_fiscales import aislado
            try:
                with limite_proceso_pesado():
                    summary = aislado.generar_libro_aislado(job_id)
            except ProcesoOcupado as e:
                service.mark_failed(db, job_id, str(e))
                return
        else:
            summary = _generar_output_libro(db, job, job_id)

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
