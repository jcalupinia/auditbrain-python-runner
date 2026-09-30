"""Efectivo y equivalentes (Caja-Bancos): la carga de cada requerimiento admite
PDF e imagen (JPG) además del tabular xlsx/csv.

Decisión del dueño (2026-09-30): en las tarjetas de «Requerimientos de
información» de la herramienta de efectivo el auditor debe poder subir el
documento fuente (anexos, conciliaciones, estados de cuenta, mayores) en PDF o
JPG, no solo en Excel. La evidencia no tabular se guarda pero NO altera la
población: el cálculo sigue tomándose del xlsx/csv (el mapeador filtra por
`esTabular`), por eso xlsx/csv siguen siendo los primeros formatos de los
requerimientos de datos.

Estos casos atrapan una regresión si alguien vuelve a restringir el `formats`
de un requerimiento a solo xlsx/csv, o si el camino de validación de la
plataforma (`_validar_plan`) o de la subida (`check_upload`) dejara de
aceptarlos.
"""
from backend.app.aud.niif.procesadores import efectivo_equivalentes as efectivo
from backend.app.aud.niif.ciclo import datos
from backend.app.aud.niif.requerimiento import check_upload

# RQ que arman población (datasets) y RQ de soporte/evidencia.
_RQ_DATOS = {"RQ-001", "RQ-002", "RQ-009", "RQ-010", "RQ-011", "RQ-012"}


def _requests():
    return efectivo.definicion()["requests"]


def test_todos_los_requerimientos_admiten_pdf_y_jpg():
    for r in _requests():
        fmts = set(r.get("formats") or [])
        assert "pdf" in fmts, f"{r['id']} debería admitir PDF: {fmts}"
        assert "jpg" in fmts, f"{r['id']} debería admitir JPG: {fmts}"
        assert "jpeg" in fmts, f"{r['id']} debería admitir JPEG: {fmts}"


def test_requerimientos_de_datos_conservan_el_tabular():
    # El cálculo se arma del tabular: xlsx/csv no pueden perderse en los RQ de datos.
    por_id = {r["id"]: set(r.get("formats") or []) for r in _requests()}
    for rid in _RQ_DATOS:
        assert {"xlsx", "csv"} <= por_id[rid], f"{rid} perdió el tabular: {por_id[rid]}"


def test_la_definicion_pasa_la_validacion_de_la_plataforma():
    # Mismo camino que `_definicion_procesador`: el procesador y el plan del ciclo.
    d = {**efectivo.definicion(), "id": "custom"}
    efectivo.validar_definicion(d)
    datos._validar_plan(d)  # valida cada `formats` contra datos.FORMATS


def test_check_upload_acepta_pdf_jpg_y_sigue_aceptando_el_tabular():
    reqs = _requests()
    items = datos.requests_as_items(reqs)
    id_item = {r["id"]: it["id"] for r, it in zip(reqs, items)}
    # Un requerimiento de datos (Anexo de Caja y Bancos) acepta las 4 vías.
    for nombre in ("anexo.xlsx", "anexo.csv", "conciliacion.pdf", "foto_arqueo.jpg"):
        check_upload(items, id_item["RQ-001"], None, nombre)
    # Un formato no admitido sigue rechazándose.
    try:
        check_upload(items, id_item["RQ-001"], None, "anexo.exe")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("check_upload debería rechazar .exe")
