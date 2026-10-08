"""CORS en Preview Environments de Render (app.py::_preview_cors_origin_regex).

Regla: en producción (APP_ENV != "preview") NO hay regex (comportamiento
idéntico al histórico). En preview, el regex queda anclado a los frontends del
MISMO PR cuando RENDER_EXTERNAL_HOSTNAME lo permite; si no, cae a cualquier PR
del repositorio y lo avisa por log.
"""

import re

import pytest

from app import _preview_cors_origin_regex


@pytest.mark.parametrize("app_env", ["production", "", "staging", "PREVIEW "])
def test_fuera_de_preview_no_hay_regex(app_env):
    # El llamador normaliza APP_ENV con strip().lower(); aquí se pasa tal cual
    # para fijar que SOLO el valor exacto "preview" activa el regex.
    assert _preview_cors_origin_regex(app_env, "auditbrain-python-runner-pr-7.onrender.com") is None


def test_preview_anclado_al_mismo_pr():
    rx = _preview_cors_origin_regex("preview", "auditbrain-python-runner-pr-123.onrender.com")
    assert rx is not None
    assert re.match(rx, "https://auditbrain-frontend-pr-123.onrender.com")
    assert re.match(rx, "https://auditbrain-clientes-pr-123.onrender.com")
    # Otro PR del mismo repo: rechazado.
    assert not re.match(rx, "https://auditbrain-frontend-pr-124.onrender.com")
    assert not re.match(rx, "https://auditbrain-frontend-pr-1230.onrender.com")
    # Sin bypass por prefijo/sufijo, http plano ni producción.
    assert not re.match(rx, "https://auditbrain-frontend-pr-123.onrender.com.evil.tld")
    assert not re.match(rx, "https://evil-auditbrain-frontend-pr-123.onrender.com")
    assert not re.match(rx, "http://auditbrain-frontend-pr-123.onrender.com")
    assert not re.match(rx, "https://auditbrain-frontend.onrender.com")
    assert not re.match(rx, "https://consola.audit-ia.ec")


@pytest.mark.parametrize("hostname", ["", "auditbrain-python-runner.onrender.com", "algo-raro"])
def test_preview_sin_numero_de_pr_cae_a_cualquier_pr_y_avisa(hostname, caplog):
    with caplog.at_level("WARNING", logger="auditbrain"):
        rx = _preview_cors_origin_regex("preview", hostname)
    assert rx is not None
    assert re.match(rx, "https://auditbrain-frontend-pr-1.onrender.com")
    assert re.match(rx, "https://auditbrain-clientes-pr-999.onrender.com")
    assert not re.match(rx, "https://auditbrain-frontend.onrender.com")
    assert not re.match(rx, "https://auditbrain-frontend-pr-1.onrender.com.evil.tld")
    assert any("CUALQUIER preview" in r.getMessage() for r in caplog.records)
