"""CORS en Preview Environments (backend/app/core/preview.py::cors_origin_regex_for).

Regla: en producción (``preview: False``) NO hay regex (comportamiento idéntico al
histórico). En preview, el regex queda anclado a los frontends del MISMO PR, tanto en
Coolify (<n>.consola|clientes.preview.audit-ia.ec) como en Render (…-pr-<n>.onrender.com),
y NO existe ningún fallback a «cualquier PR»: sin identidad válida, el backend no arranca
(ver test_preview_env.py).
"""

import re

import pytest

from backend.app.core.preview import cors_origin_regex_for


def _fullmatch(rx: str, origin: str) -> bool:
    # Starlette aplica fullmatch sobre el Origin recibido.
    return re.compile(rx).fullmatch(origin) is not None


def test_fuera_de_preview_no_hay_regex():
    assert cors_origin_regex_for({"preview": False}) is None
    assert cors_origin_regex_for({}) is None


def test_preview_anclado_al_mismo_pr_en_coolify_y_render():
    rx = cors_origin_regex_for({"preview": True, "pr": "123", "provider": "coolify"})
    assert rx is not None
    for ok in (
        "https://123.consola.preview.audit-ia.ec",
        "https://123.clientes.preview.audit-ia.ec",
        "https://auditbrain-frontend-pr-123.onrender.com",
        "https://auditbrain-clientes-pr-123.onrender.com",
    ):
        assert _fullmatch(rx, ok), ok


@pytest.mark.parametrize("origen", [
    "https://124.consola.preview.audit-ia.ec",            # otro PR
    "https://1230.consola.preview.audit-ia.ec",           # prefijo numérico
    "https://123.api.preview.audit-ia.ec",                # el backend no es un origen de frontend
    "https://123.consola.preview.audit-ia.ec:443",        # con puerto
    "http://123.consola.preview.audit-ia.ec",             # http plano
    "https://123.consola.preview.audit-ia.ec.evil.tld",   # sufijo
    "https://evil.123.consola.preview.audit-ia.ec",       # prefijo de host
    "https://123.CONSOLA.preview.audit-ia.ec",            # mayúsculas: el Origin real llega en minúsculas
    "https://consola.audit-ia.ec",                         # producción
    "https://clientes.audit-ia.ec",
    "https://auditbrain-frontend.onrender.com",
    "https://auditbrain-frontend-pr-124.onrender.com",
    "https://auditbrain-frontend-pr-123.onrender.com.evil.tld",
])
def test_preview_rechaza_otros_origenes(origen):
    rx = cors_origin_regex_for({"preview": True, "pr": "123", "provider": "coolify"})
    assert not _fullmatch(rx, origen), origen


def test_el_numero_de_pr_se_escapa_literalmente():
    # Un valor con metacaracteres no puede ampliar el patrón.
    rx = cors_origin_regex_for({"preview": True, "pr": "1.*", "provider": "coolify"})
    assert not _fullmatch(rx, "https://123.consola.preview.audit-ia.ec")
    assert _fullmatch(rx, "https://1.*.consola.preview.audit-ia.ec")


def test_no_existe_fallback_a_cualquier_pr():
    # No hay forma de obtener un regex con \d+ a partir de una identidad ausente.
    assert cors_origin_regex_for({"preview": False, "pr": None}) is None
    rx = cors_origin_regex_for({"preview": True, "pr": "7", "provider": "render"})
    assert r"\d+" not in rx and r"\d{" not in rx
