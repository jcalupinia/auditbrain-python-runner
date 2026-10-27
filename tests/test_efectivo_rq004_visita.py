"""Efectivo y equivalentes: RQ-004 (estados/conciliaciones POSTERIORES al corte)
NUNCA bloquea el proceso — ni en la visita final.

Decisión del dueño (2026-10-27, revisa la del 2026-10-01): la documentación
posterior a la fecha de corte (ventana de depuración) puede no estar disponible al
momento de ejecutar la prueba, incluso en la visita final (p. ej. el banco aún no
emite el estado del período siguiente). Su ausencia NO debe impedir «Procesar»: se
trata como **limitación de alcance / hallazgo documentado** (NIA 560/500), no como
bloqueo. En consecuencia RQ-004 es SIEMPRE opcional (`required=False`) y jamás entra
en los huecos obligatorios que bloquean. La limitación queda en el papel de trabajo
por la marca de partidas «sin liquidación posterior» del propio motor (CASH-04/05).

Antes, RQ-004 estaba en `REQUERIDOS_SOLO_FINAL` y se volvía obligatorio en la visita
final; esa constante queda vacía para efectivo.
"""
from types import SimpleNamespace

from backend.app.aud.niif.procesadores import efectivo_equivalentes as efectivo
from backend.app.aud.niif.ciclo import datos, servicio


def _prueba(visit):
    reqs = efectivo.definicion()["requests"]
    engagement = {"visit": visit} if visit is not None else {}
    return SimpleNamespace(
        origen="proc:efectivo_equivalentes", estado="REQUERIMIENTO_APROBADO",
        registro={"engagement": engagement, "requests": [dict(r) for r in reqs]},
        definicion={"processor": "efectivo_equivalentes", "requests": [dict(r) for r in reqs]},
    )


def _rq004_required(visit):
    p = _prueba(visit)
    reqs = servicio._con_politica_viva(p.registro["requests"], servicio._politica_catalogo_viva(p))
    return next(r for r in reqs if r["id"] == "RQ-004")["required"]


def _bloquea_posteriores(visit):
    p = _prueba(visit)
    reqs = servicio._con_politica_viva(p.registro["requests"], servicio._politica_catalogo_viva(p))
    return any("posterior" in h.lower() for h in datos.tool_gaps(reqs, [], []))


def test_rq004_ya_no_esta_en_requeridos_solo_final():
    # RQ-004 dejó de forzarse como obligatorio en la visita final.
    assert "RQ-004" not in efectivo.REQUERIDOS_SOLO_FINAL


def test_rq004_opcional_en_preliminar():
    assert _rq004_required("Preliminar") is False
    assert _bloquea_posteriores("Preliminar") is False


def test_rq004_opcional_tambien_en_final():
    # El cambio: en la visita final RQ-004 ya NO es obligatorio ni bloquea.
    assert _rq004_required("Final") is False
    assert _bloquea_posteriores("Final") is False


def test_rq004_opcional_si_no_hay_visita():
    assert _rq004_required(None) is False
    assert _bloquea_posteriores(None) is False
