"""Preview Environments de Render: un preview nunca apunta a producción.

- ``backend/app/core/preview.py``: detección del preview, número de PR y URL del
  portal de clientes (producción idéntica a antes; preview => mismo preview o
  centinela ``.invalid``).
- ``backend/app/auth/jwt_tokens.py``: en preview sin AUDITBRAIN_JWT_SECRET se usa
  un secreto aleatorio por proceso, NUNCA el literal de desarrollo.
- ``notifications/email.py`` y ``forge/billing.py`` construyen sus enlaces con el
  helper.
"""

import pytest

from backend.app.auth import jwt_tokens
from backend.app.core import preview

PROD = "https://auditbrain-clientes.onrender.com"
DEV_LITERAL = "dev-insecure-secret-change-me"


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    for k in ("APP_ENV", "RENDER_EXTERNAL_HOSTNAME", "CLIENT_PORTAL_URL", "AUDITBRAIN_JWT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(jwt_tokens, "_PREVIEW_SECRET", None)
    yield


# --- detección ---------------------------------------------------------------

@pytest.mark.parametrize("valor,esperado", [
    (None, False), ("production", False), ("", False), ("staging", False),
    ("preview", True), (" Preview ", True),
])
def test_is_preview_solo_con_app_env_preview(monkeypatch, valor, esperado):
    if valor is not None:
        monkeypatch.setenv("APP_ENV", valor)
    assert preview.is_preview() is esperado


@pytest.mark.parametrize("host,esperado", [
    ("auditbrain-python-runner-pr-123.onrender.com", "123"),
    ("AUDITBRAIN-PYTHON-RUNNER-PR-7.ONRENDER.COM", "7"),
    ("auditbrain-python-runner.onrender.com", None),
    ("auditbrain-python-runner-pr-123.onrender.com.evil.tld", None),
    ("", None),
])
def test_preview_pr_number(monkeypatch, host, esperado):
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", host)
    assert preview.preview_pr_number() == esperado


# --- URL del portal ------------------------------------------------------------

def test_portal_en_produccion_usa_env_o_default(monkeypatch):
    assert preview.client_portal_url() == PROD
    monkeypatch.setenv("CLIENT_PORTAL_URL", "https://clientes.audit-ia.ec")
    assert preview.client_portal_url() == "https://clientes.audit-ia.ec"


def test_portal_en_preview_es_el_del_mismo_pr(monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "auditbrain-python-runner-pr-123.onrender.com")
    # Aunque la variable traiga producción (o el centinela), manda el preview.
    monkeypatch.setenv("CLIENT_PORTAL_URL", PROD)
    assert preview.client_portal_url() == "https://auditbrain-clientes-pr-123.onrender.com"


@pytest.mark.parametrize("host", ["", "auditbrain-python-runner.onrender.com"])
def test_portal_en_preview_sin_pr_nunca_es_produccion(monkeypatch, caplog, host):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", host)
    monkeypatch.setenv("CLIENT_PORTAL_URL", PROD)
    with caplog.at_level("WARNING", logger="auditbrain"):
        url = preview.client_portal_url()
    assert url == preview.PREVIEW_PORTAL_UNRESOLVED
    assert url.endswith(".invalid")
    assert "nunca producción" in caplog.text


def test_email_job_ready_enlaza_al_portal_del_preview(monkeypatch):
    from backend.app.notifications import email as email_mod

    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "auditbrain-python-runner-pr-55.onrender.com")
    capturado = {}
    monkeypatch.setattr(email_mod, "render_job_ready", lambda **kw: capturado.update(kw) or "<html/>")
    monkeypatch.setattr(email_mod, "send_email", lambda **kw: {"id": "x"})
    email_mod.send_job_ready_email(job_id=9, to="a@b.c", tool_label="ICT")
    assert capturado["download_url"] == "https://auditbrain-clientes-pr-55.onrender.com/jobs/9"
    assert PROD not in capturado["download_url"]


def test_email_job_ready_en_produccion_no_cambia(monkeypatch):
    from backend.app.notifications import email as email_mod

    capturado = {}
    monkeypatch.setattr(email_mod, "render_job_ready", lambda **kw: capturado.update(kw) or "<html/>")
    monkeypatch.setattr(email_mod, "send_email", lambda **kw: {"id": "x"})
    email_mod.send_job_ready_email(job_id=9, to="a@b.c", tool_label="ICT")
    assert capturado["download_url"] == f"{PROD}/jobs/9"


def test_billing_retorna_al_portal_del_preview(monkeypatch):
    from backend.app.forge import billing

    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "auditbrain-python-runner-pr-55.onrender.com")
    monkeypatch.setenv(billing._PRICE_ENV[next(iter(billing.PAID_PLANS))], "price_test")
    capturado = {}

    class _Session:
        @staticmethod
        def create(**kw):
            capturado.update(kw)
            return type("S", (), {"url": "https://checkout.stripe.test/s"})()

    fake_stripe = type("Stripe", (), {"checkout": type("C", (), {"Session": _Session})()})()
    monkeypatch.setattr(billing, "_require_stripe", lambda: fake_stripe)
    user = type("U", (), {"id": 1})()
    billing.create_checkout_url(user, next(iter(billing.PAID_PLANS)))
    assert capturado["success_url"].startswith("https://auditbrain-clientes-pr-55.onrender.com/forge")
    assert capturado["cancel_url"].startswith("https://auditbrain-clientes-pr-55.onrender.com/forge")
    assert PROD not in capturado["success_url"] + capturado["cancel_url"]


# --- secreto JWT ---------------------------------------------------------------

def test_jwt_en_preview_nunca_usa_el_literal_de_desarrollo(monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")
    s1 = jwt_tokens._secret()
    assert s1 != DEV_LITERAL
    assert len(s1) >= 48
    # Estable dentro del proceso (los tokens emitidos siguen validando).
    assert jwt_tokens._secret() == s1
    tok = jwt_tokens.create_access_token("a@b.c", "client")
    assert jwt_tokens.decode_token(tok)["sub"] == "a@b.c"
    # Otro proceso/preview generaría otro secreto: al reiniciar la caché cambia.
    monkeypatch.setattr(jwt_tokens, "_PREVIEW_SECRET", None)
    assert jwt_tokens._secret() != s1


def test_jwt_en_preview_prefiere_el_secreto_definido(monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("AUDITBRAIN_JWT_SECRET", "secreto-del-grupo-de-preview")
    assert jwt_tokens._secret() == "secreto-del-grupo-de-preview"


def test_jwt_fuera_de_preview_no_cambia(monkeypatch):
    # Comportamiento histórico intacto fuera de preview (dev local / producción
    # mal configurada): literal de desarrollo con aviso.
    assert jwt_tokens._secret() == DEV_LITERAL
    monkeypatch.setenv("AUDITBRAIN_JWT_SECRET", "prod")
    assert jwt_tokens._secret() == "prod"
