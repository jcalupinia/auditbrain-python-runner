# backend/app/client_portal/flujo/processor.py
"""Processor de la Herramienta Flujo de Efectivo para el pipeline genérico de
jobs del portal cliente.

Sigue el mismo patrón que ``tool_registry._stub_echo_processor``: recibe un
``job_id``, marca el ToolJob como ``processing``, lee los inputs de sus DOS
slots (``balanza_anterior`` y ``balanza_actual``) desde ``file_storage``,
parsea cada balanza, corre ``generador.generar_excel`` y escribe el resultado
en ``output_path(job_dir)``. Al terminar marca ``done`` con el summary de
cuadraturas, o ``error`` con el mensaje si algo falla.
"""
from __future__ import annotations

from pathlib import Path

from backend.app.aud.obligaciones_fiscales import file_storage

from . import generador, parser

SLOT_ANTERIOR = "balanza_anterior"
SLOT_ACTUAL = "balanza_actual"


def _leer_slot(job_dir: Path, slot: str) -> bytes:
    """Lee el (primer) archivo del slot indicado. Lanza ValueError si falta."""
    archivos = file_storage.list_inputs(job_dir, slot)
    if not archivos:
        raise ValueError(f"No se encontró archivo en el slot '{slot}'.")
    return archivos[0].read_bytes()


def _procesar_job_dir(job_dir: Path) -> tuple[Path, dict]:
    """Núcleo testeable: lee ambos slots del ``job_dir``, parsea, genera el
    Excel a ``output_path(job_dir)`` y devuelve ``(out_path, summary)``.

    Aislado del ToolJob/DB para poder probarse con archivos temporales.
    """
    bytes_ant = _leer_slot(job_dir, SLOT_ANTERIOR)
    bytes_act = _leer_slot(job_dir, SLOT_ACTUAL)

    bal_ant = parser.parse_balanza(bytes_ant)
    bal_act = parser.parse_balanza(bytes_act)
    if not bal_ant:
        raise ValueError(
            f"La balanza del slot '{SLOT_ANTERIOR}' no tiene filas legibles.")
    if not bal_act:
        raise ValueError(
            f"La balanza del slot '{SLOT_ACTUAL}' no tiene filas legibles.")

    data = generador.generar_excel(bal_ant, bal_act)

    out_path = file_storage.output_path(job_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)

    # Recalcula las cuadraturas para el summary (barato: reusa los motores).
    from . import catalogos, motor, motor_flujo

    est_esf = catalogos.cargar_estructura("esf")
    clasificacion = catalogos.cargar_clasificacion_flujo()
    saldos_ant, _ = motor.homologar_balanza(bal_ant)
    saldos_act, _ = motor.homologar_balanza(bal_act)
    tot_ant = motor.totales_por_codigo(est_esf, saldos_ant)
    tot_act = motor.totales_por_codigo(est_esf, saldos_act)
    cuadre_esf = motor.cuadre(tot_act)
    flujo = motor_flujo.flujo_efectivo(tot_ant, tot_act, clasificacion)

    summary = {
        "cuadre_esf": cuadre_esf["diferencia"],
        "cuadre_esf_cuadra": cuadre_esf["cuadra"],
        "cuadre_af": flujo["cuadre_af"],
        "cuadre_af_cuadra": flujo["cuadra"],
        "filas_anterior": len(bal_ant),
        "filas_actual": len(bal_act),
        "output_bytes": len(data),
    }
    return out_path, summary


def flujo_efectivo_processor(job_id: int) -> None:
    """Procesa un ToolJob de la Herramienta Flujo de Efectivo.

    Marca el job ``processing``, genera el Excel a partir de los dos slots y
    marca ``done`` (con summary) o ``error`` (con ``error_message``).
    """
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            return
        job.status = "processing"
        db.commit()

        try:
            job_dir = file_storage.job_dir(job_id)
            _out_path, summary = _procesar_job_dir(job_dir)
        except Exception as exc:  # noqa: BLE001 — se reporta al usuario
            job.status = "error"
            job.error_message = str(exc)[:1000]
            db.commit()
            return

        job.status = "done"
        job.summary_json = summary
        db.commit()
    finally:
        db.close()
