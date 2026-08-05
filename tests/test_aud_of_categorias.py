"""Catálogo de categorías expuesto a la consola."""

from tests.test_aud_of_router import _db, _h, _mk_admin_project  # noqa: F401


def test_lista_las_categorias_de_sistema(client):
    tok, _ = _mk_admin_project(client)
    r = client.get("/api/v1/aud/obligaciones-fiscales/categorias", headers=_h(tok))
    assert r.status_code == 200
    codigos = {c["codigo"] for c in r.json()}
    assert {"IVA_COMPRAS", "IVA_VENTAS", "RET_RENTA", "RET_IVA", "VENTAS"} <= codigos


def test_sin_autenticacion_devuelve_401(client):
    r = client.get("/api/v1/aud/obligaciones-fiscales/categorias")
    assert r.status_code == 401
