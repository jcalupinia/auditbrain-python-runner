"""Efectivo y equivalentes: RQ-004 (estados/conciliaciones POSTERIORES al corte)
es obligatorio SOLO en la visita final.

Decisión del dueño (2026-10-01): la documentación posterior a la fecha de corte
(ventana de depuración) recién existe después del corte, así que en la **visita
preliminar** no se dispone de ella y NO debe bloquear el proceso; en la **visita
final** sí es obligatoria. Lo resuelve el overlay de política viva de `servicio`
(`_politica_catalogo_viva`) leyendo la visita del encargo congelado en la prueba
(`reg["engagement"]["visit"]`), más la constante `REQUERIDOS_SOLO_FINAL` del
procesador.
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


def test_rq004_declarado_solo_final():
    assert "RQ-004" in efectivo.REQUERIDOS_SOLO_FINAL


def test_rq004_opcional_en_preliminar():
    assert _rq004_required("Preliminar") is False
    assert _bloquea_posteriores("Preliminar") is False


def test_rq004_obligatorio_en_final():
    assert _rq004_required("Final") is True
    assert _bloquea_posteriores("Final") is True


def test_rq004_opcional_si_no_hay_visita():
    # Sin visita fijada en la ficha, no se bloquea (se trata como no-final).
    assert _rq004_required(None) is False
    assert _bloquea_posteriores(None) is False
