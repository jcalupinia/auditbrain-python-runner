"""Efectivo y equivalentes: RQ-008 (política contable + actas de arqueo) es OPCIONAL.

Decisión del dueño (2026-10-01): la política contable de efectivo y equivalentes y
las actas de arqueo NO deben impedir procesar la prueba. Son soporte documental; su
ausencia no puede bloquear el cálculo (el arqueo que SÍ alimenta una cédula es el
dataset RQ-012, que ya era opcional). Los estados bancarios (RQ-003/004) y las
confirmaciones (RQ-005) siguen siendo obligatorios porque sin ellos la conciliación
no se puede medir.

El cambio del catálogo (`required=False`) llega también a pruebas ya creadas por el
overlay de política viva de `servicio` (`_politica_catalogo_viva` / `_con_politica_viva`).
"""
from types import SimpleNamespace

from backend.app.aud.niif.procesadores import efectivo_equivalentes as efectivo
from backend.app.aud.niif.ciclo import datos
from backend.app.aud.niif.ciclo import servicio


def _req(rq_id: str) -> dict:
    return next(r for r in efectivo.definicion()["requests"] if r["id"] == rq_id)


def test_rq008_es_opcional():
    assert _req("RQ-008").get("required") is False


def test_rq008_no_bloquea_el_proceso():
    # Sin ningún documento cargado, los huecos NO deben incluir la política/arqueo.
    huecos = datos.tool_gaps(efectivo.definicion()["requests"], [], [])
    assert not any(("arqueo" in h.lower()) or ("política" in h.lower()) or ("politica" in h.lower())
                   for h in huecos), huecos


def test_estados_y_confirmaciones_siguen_obligatorios():
    # Solo política/arqueo se volvió opcional; el resto del soporte de conciliación no.
    for rq in ("RQ-003", "RQ-004", "RQ-005"):
        assert _req(rq).get("required") is not False, rq


def test_prueba_vieja_hereda_rq008_opcional_por_overlay_vivo():
    # Prueba creada cuando RQ-008 era obligatorio: el overlay vigente lo vuelve opcional.
    viejos = [{"id": "RQ-008", "document": "Política contable y actas de arqueo",
               "formats": ["pdf", "docx"], "required": True}]
    p = SimpleNamespace(
        origen="proc:efectivo_equivalentes", estado="REQUERIMIENTO_APROBADO",
        registro={"requests": [dict(r) for r in viejos]},
        definicion={"processor": "efectivo_equivalentes", "requests": [dict(r) for r in viejos]},
    )
    politica = servicio._politica_catalogo_viva(p)
    salida = servicio._con_politica_viva(p.registro["requests"], politica)
    assert salida[0]["required"] is False
