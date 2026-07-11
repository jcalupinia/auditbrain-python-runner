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

import io
import zipfile
from pathlib import Path

from backend.app.aud.obligaciones_fiscales import file_storage

from . import generador, parser

SLOT_ANTERIOR = "balanza_anterior"
SLOT_ACTUAL = "balanza_actual"

ARTIFACTS_DIR = "artifacts"

# Nombres de archivo de cada entregable (replican las macros del Excel).
ARCH_EXCEL = "FlujoEfectivo.xlsx"
ARCH_ESF = "EstadoDeSituacionFinanciera.txt"
ARCH_ERI = "EstadoDeResultadoIntegral.txt"
ARCH_FLU = "EstadoDeFlujoDeEfectivo.txt"
ARCH_101 = "Formulario101.xml"
ARCH_ZIP = "FlujoEfectivo_completo.zip"


def _generar_artefactos(job_dir: Path, bal_ant: list[dict], bal_act: list[dict],
                        excel_bytes: bytes) -> list[dict]:
    """Genera los entregables por estado (TXT/XML) + un ZIP con todo, bajo
    ``job_dir/artifacts/``. Devuelve la lista de metadatos de artefactos para
    el ``summary_json`` (que el frontend usa para pintar los botones)."""
    from . import catalogos, motor, motor_er, motor_f101

    est_esf = catalogos.cargar_estructura("esf")
    est_eri = catalogos.cargar_estructura("eri")
    saldos_act, _ = motor.homologar_balanza(bal_act)
    tot_esf = motor.totales_por_codigo(est_esf, saldos_act)
    tot_eri = motor.totales_por_codigo(est_eri, saldos_act)
    cascada = motor_er.cascada_resultados(tot_eri)
    ori = motor_f101.ori_del_periodo(bal_ant, bal_act)

    txt_esf = generador_exportadores().txt_esf(tot_esf, estructura=est_esf)
    txt_eri = generador_exportadores().txt_eri(tot_eri, cascada, ori, estructura=est_eri)
    txt_flu = generador_exportadores().txt_flujo(bal_ant, bal_act)
    xml_101 = generador_exportadores().xml_101(bal_act, balanza_anterior=bal_ant)

    art_dir = job_dir / ARTIFACTS_DIR
    art_dir.mkdir(parents=True, exist_ok=True)

    # Vistas previas EN VIVO (tabla de cada sección) para el portal.
    try:
        import json as _json
        from . import previews as _previews
        prev = _previews.construir_previews(bal_ant, bal_act)
        (art_dir / "previews.json").write_text(
            _json.dumps(prev, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001 — la preview es opcional, no rompe la descarga
        pass

    contenidos = {
        ARCH_EXCEL: excel_bytes,
        ARCH_ESF: txt_esf.encode("utf-8"),
        ARCH_ERI: txt_eri.encode("utf-8"),
        ARCH_FLU: txt_flu.encode("utf-8"),
        ARCH_101: xml_101.encode("utf-8"),
    }
    for nombre, data in contenidos.items():
        (art_dir / nombre).write_bytes(data)

    # ZIP con todo
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, data in contenidos.items():
            zf.writestr(nombre, data)
    (art_dir / ARCH_ZIP).write_bytes(buf.getvalue())

    return [
        {"name": ARCH_EXCEL, "label": "Excel auditable (9 hojas)",
         "estado": "Todos", "kind": "xlsx"},
        {"name": ARCH_ESF, "label": "Estado de Situación Financiera",
         "estado": "ESF", "kind": "txt"},
        {"name": ARCH_ERI, "label": "Estado de Resultados Integral",
         "estado": "ERI", "kind": "txt"},
        {"name": ARCH_FLU, "label": "Estado de Flujo de Efectivo",
         "estado": "FLU", "kind": "txt"},
        {"name": ARCH_101, "label": "Formulario 101",
         "estado": "F-101", "kind": "xml"},
        {"name": ARCH_ZIP, "label": "Descargar todo",
         "estado": "ZIP", "kind": "zip"},
    ]


def generador_exportadores():
    """Import perezoso de exportadores (evita ciclos en carga de módulo)."""
    from . import exportadores
    return exportadores


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

    # Entregables por estado (TXT/XML de envío Super Cías/SRI) + ZIP.
    artefactos = _generar_artefactos(job_dir, bal_ant, bal_act, data)

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
        "artifacts": artefactos,
    }
    return out_path, summary


def recalcular_desde_balanzas(job_id: int, bal_ant: list[dict],
                              bal_act: list[dict]) -> dict:
    """Recalcula TODA la herramienta a partir de balanzas editadas por el
    usuario y devuelve los previews frescos.

    Reusa los motores validados (no duplica lógica en el frontend): regenera el
    Excel + todos los artefactos (TXT/XML/ZIP) y la ``previews.json`` en el
    ``job_dir``, de modo que tanto la vista en vivo como las descargas reflejen
    los cambios. Pensado para el editor de balanzas del portal (edición → todo
    se actualiza).
    """
    if not bal_ant or not bal_act:
        raise ValueError("Ambas balanzas (anterior y actual) deben tener filas.")

    job_dir = file_storage.job_dir(job_id)
    data = generador.generar_excel(bal_ant, bal_act)
    out_path = file_storage.output_path(job_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)

    _generar_artefactos(job_dir, bal_ant, bal_act, data)

    from . import previews as _previews
    return _previews.construir_previews(bal_ant, bal_act)


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
