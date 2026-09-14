from backend.app.recursos.catalog import get_recurso
from backend.app.recursos.tokens import crear_token, leer_token

SLUG = "anticipo-ir-2026"


def test_catalogo_conoce_la_calculadora():
    rec = get_recurso(SLUG)
    assert rec is not None
    assert rec.url == "https://recursos.audit-ia.ec/anticipo-ir-2026/"
    assert get_recurso("no-existe") is None


def test_token_ida_y_vuelta():
    assert leer_token(crear_token(42, SLUG), SLUG) == 42


def test_token_de_otro_recurso_no_vale():
    assert leer_token(crear_token(42, "otro-recurso"), SLUG) is None


def test_token_vencido_no_vale():
    assert leer_token(crear_token(42, SLUG, dias=-1), SLUG) is None


def test_token_basura_no_vale():
    assert leer_token("no-es-un-token", SLUG) is None
