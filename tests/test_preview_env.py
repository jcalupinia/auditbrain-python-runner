"""Preview Environments (Coolify y Render): identidad del PR, fallo seguro y secretos.

- ``backend/app/core/preview.py``: identidad por única fuente (PREVIEW_PUBLIC_HOST) con
  confirmación; sin fallback; ``preview_bootstrap`` termina el proceso ante cualquier
  configuración inválida; portal del mismo PR.
- ``backend/app/auth/jwt_tokens.py``: en preview el secreto sale del volumen del PR; sin
  archivo no hay arranque.
- ``notifications/email.py`` y ``forge/billing.py`` construyen sus enlaces con el helper.
Fuera de preview nada cambia.
"""

import os
from pathlib import Path

import pytest

from backend.app.auth import jwt_tokens
from backend.app.core import preview

PROD = "https://auditbrain-clientes.onrender.com"
DEV_LITERAL = "dev-insecure-secret-change-me"
SHA = "a" * 40
VARS = ("APP_ENV", "PREVIEW_PUBLIC_HOST", "COOLIFY_FQDN", "RENDER_EXTERNAL_HOSTNAME",
        "CLIENT_PORTAL_URL", "AUDITBRAIN_JWT_SECRET", "DATABASE_URL", "PREVIEW_SECRETS_DIR",
        "CORS_ALLOW_ORIGINS", "BUILD_COMMIT", "PREVIEW_EXPECTED_IMAGE_TAG", "SOURCE_COMMIT")


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    for k in VARS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(jwt_tokens, "_PREVIEW_SECRET", None)
    yield


@pytest.fixture
def secretos(tmp_path, monkeypatch):
    d = tmp_path / "secrets"
    d.mkdir()
    (d / "jwt_secret").write_text("S" * 64, encoding="utf-8")
    (d / "pg_password").write_text("p" * 40, encoding="utf-8")
    monkeypatch.setenv("PREVIEW_SECRETS_DIR", str(d))
    return d


def _preview_valido(monkeypatch, pr="123", host=None):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", host or f"{pr}.api.preview.audit-ia.ec")
    monkeypatch.setenv("DATABASE_URL", "postgresql://auditbrain:x@db:5432/auditbrain")
    monkeypatch.setenv("BUILD_COMMIT", SHA)
    monkeypatch.setenv("PREVIEW_EXPECTED_IMAGE_TAG", f"sha-{SHA}")


# --- detección e identidad -------------------------------------------------------------------

@pytest.mark.parametrize("valor,esperado", [
    (None, False), ("production", False), ("", False), ("staging", False),
    ("preview", True), (" Preview ", True),
])
def test_is_preview_solo_con_app_env_preview(monkeypatch, valor, esperado):
    if valor is not None:
        monkeypatch.setenv("APP_ENV", valor)
    assert preview.is_preview() is esperado


@pytest.mark.parametrize("host,esperado", [
    ("123.api.preview.audit-ia.ec", ("coolify", "123")),
    ("123.API.preview.audit-ia.ec.", ("coolify", "123")),          # mayúsculas y punto final
    ("https://123.api.preview.audit-ia.ec:10000/x", ("coolify", "123")),  # URL completa
    ("auditbrain-python-runner-pr-7.onrender.com", ("render", "7")),
])
def test_identidad_desde_la_fuente_primaria(monkeypatch, host, esperado):
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", host)
    assert preview.preview_identity() == esperado


@pytest.mark.parametrize("host", [
    "", "   ", "api.preview.audit-ia.ec", "123.consola.preview.audit-ia.ec",
    "123.api.preview.audit-ia.ec.evil.tld", "x123.api.preview.audit-ia.ec",
    "auditbrain-python-runner.onrender.com", "1.2.3.4", "algo_raro",
])
def test_identidad_ausente_o_incorrecta_falla(monkeypatch, host):
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", host)
    with pytest.raises(preview.PreviewConfigError):
        preview.preview_identity()


def test_identidad_ambigua_entre_fuentes_falla(monkeypatch):
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "123.api.preview.audit-ia.ec")
    monkeypatch.setenv("COOLIFY_FQDN", "124.api.preview.audit-ia.ec, 123.consola.preview.audit-ia.ec")
    with pytest.raises(preview.PreviewConfigError, match="ambigua"):
        preview.preview_identity()


def test_fuentes_de_confirmacion_coherentes_no_fallan(monkeypatch):
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "123.api.preview.audit-ia.ec")
    monkeypatch.setenv("COOLIFY_FQDN", "123.api.preview.audit-ia.ec,123.consola.preview.audit-ia.ec")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "")
    assert preview.preview_identity() == ("coolify", "123")


# --- arranque seguro ---------------------------------------------------------------------------

def test_bootstrap_fuera_de_preview_no_hace_nada(monkeypatch):
    assert preview.preview_bootstrap() == {"preview": False}
    monkeypatch.setenv("APP_ENV", "production")
    assert preview.preview_bootstrap() == {"preview": False}


def test_bootstrap_valido(monkeypatch, secretos):
    _preview_valido(monkeypatch)
    info = preview.preview_bootstrap(exit_on_error=False)
    assert info["preview"] and info["pr"] == "123" and info["provider"] == "coolify"
    assert info["config"] == "ok" and info["commit"] == SHA
    assert preview.preview_health_info() == {"active": True, "provider": "coolify", "pr": "123", "config": "ok"}


def test_bootstrap_termina_el_proceso_sin_identidad(monkeypatch, secretos):
    _preview_valido(monkeypatch)
    monkeypatch.delenv("PREVIEW_PUBLIC_HOST")
    with pytest.raises(SystemExit) as e:
        preview.preview_bootstrap()
    assert e.value.code == 3
    assert preview.preview_health_info()["config"] == "invalid"


@pytest.mark.parametrize("variable,valor,motivo", [
    ("DATABASE_URL", "postgresql://auditbrain:x@z4wy8ngriiesg6z20n7ftcnj:5432/auditbrain", "db"),
    ("DATABASE_URL", "sqlite:///./auditbrain.db", "db"),
    ("CORS_ALLOW_ORIGINS", "https://consola.audit-ia.ec", "producción"),
    ("CLIENT_PORTAL_URL", "https://clientes.audit-ia.ec", "producción"),
    ("CLIENT_PORTAL_URL", PROD, "producción"),
    ("PREVIEW_EXPECTED_IMAGE_TAG", "sha-" + "b" * 40, "no corresponde"),
    ("PREVIEW_EXPECTED_IMAGE_TAG", "", "no corresponde"),
    ("BUILD_COMMIT", "unknown", "BUILD_COMMIT"),
    ("SOURCE_COMMIT", "c" * 40, "SOURCE_COMMIT"),
])
def test_bootstrap_falla_ante_configuracion_que_apunta_a_produccion_o_imagen_incorrecta(
        monkeypatch, secretos, variable, valor, motivo):
    _preview_valido(monkeypatch)
    monkeypatch.setenv(variable, valor)
    with pytest.raises(preview.PreviewConfigError, match=motivo):
        preview.preview_bootstrap(exit_on_error=False)


def test_bootstrap_falla_sin_secreto_jwt(monkeypatch, tmp_path):
    _preview_valido(monkeypatch)
    monkeypatch.setenv("PREVIEW_SECRETS_DIR", str(tmp_path / "no_existe"))
    with pytest.raises(preview.PreviewConfigError, match="secreto JWT"):
        preview.preview_bootstrap(exit_on_error=False)


def test_bootstrap_acepta_source_commit_coherente_o_unknown(monkeypatch, secretos):
    _preview_valido(monkeypatch)
    monkeypatch.setenv("SOURCE_COMMIT", SHA)
    assert preview.preview_bootstrap(exit_on_error=False)["config"] == "ok"
    monkeypatch.setenv("SOURCE_COMMIT", "unknown")
    assert preview.preview_bootstrap(exit_on_error=False)["config"] == "ok"


# --- CORS: sin fallback -----------------------------------------------------------------------

def test_cors_sin_identidad_no_hay_regex_ni_arranque(monkeypatch, secretos):
    _preview_valido(monkeypatch, host="api.preview.audit-ia.ec")  # sin número de PR
    with pytest.raises(SystemExit):
        preview.preview_bootstrap()
    assert preview.cors_origin_regex_for({"preview": False}) is None


# --- URL del portal ------------------------------------------------------------------------------

def test_portal_en_produccion_usa_env_o_default(monkeypatch):
    assert preview.client_portal_url() == PROD
    monkeypatch.setenv("CLIENT_PORTAL_URL", "https://clientes.audit-ia.ec")
    assert preview.client_portal_url() == "https://clientes.audit-ia.ec"


def test_portal_en_preview_es_el_del_mismo_pr(monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "123.api.preview.audit-ia.ec")
    monkeypatch.setenv("CLIENT_PORTAL_URL", PROD)  # se ignora
    assert preview.client_portal_url() == "https://123.clientes.preview.audit-ia.ec"
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "auditbrain-python-runner-pr-55.onrender.com")
    assert preview.client_portal_url() == "https://auditbrain-clientes-pr-55.onrender.com"


def test_portal_en_preview_sin_identidad_nunca_es_produccion(monkeypatch, caplog):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "")
    monkeypatch.setenv("CLIENT_PORTAL_URL", PROD)
    with caplog.at_level("ERROR", logger="auditbrain"):
        url = preview.client_portal_url()
    assert url == preview.PREVIEW_PORTAL_UNRESOLVED and url.endswith(".invalid")


def test_email_job_ready_enlaza_al_portal_del_preview(monkeypatch):
    from backend.app.notifications import email as email_mod

    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "55.api.preview.audit-ia.ec")
    capturado = {}
    monkeypatch.setattr(email_mod, "render_job_ready", lambda **kw: capturado.update(kw) or "<html/>")
    monkeypatch.setattr(email_mod, "send_email", lambda **kw: {"id": "x"})
    email_mod.send_job_ready_email(job_id=9, to="a@b.c", tool_label="ICT")
    assert capturado["download_url"] == "https://55.clientes.preview.audit-ia.ec/jobs/9"


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
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "55.api.preview.audit-ia.ec")
    plan = next(iter(billing.PAID_PLANS))
    monkeypatch.setenv(billing._PRICE_ENV[plan], "price_test")
    capturado = {}

    class _Session:
        @staticmethod
        def create(**kw):
            capturado.update(kw)
            return type("S", (), {"url": "https://checkout.stripe.test/s"})()

    fake_stripe = type("Stripe", (), {"checkout": type("C", (), {"Session": _Session})()})()
    monkeypatch.setattr(billing, "_require_stripe", lambda: fake_stripe)
    billing.create_checkout_url(type("U", (), {"id": 1})(), plan)
    assert capturado["success_url"].startswith("https://55.clientes.preview.audit-ia.ec/forge")
    assert PROD not in capturado["success_url"] + capturado["cancel_url"]


# --- secreto JWT ------------------------------------------------------------------------------------

def test_jwt_en_preview_lee_el_secreto_del_volumen_y_es_estable(monkeypatch, secretos):
    monkeypatch.setenv("APP_ENV", "preview")
    s1 = jwt_tokens._secret()
    assert s1 == "S" * 64 and s1 != DEV_LITERAL
    tok = jwt_tokens.create_access_token("a@b.c", "client")
    assert jwt_tokens.decode_token(tok)["sub"] == "a@b.c"
    # Otro PR (otro volumen) => otro secreto: el token no valida.
    monkeypatch.setattr(jwt_tokens, "_PREVIEW_SECRET", None)
    (Path(secretos) / "jwt_secret").write_text("T" * 64, encoding="utf-8")
    import jwt as pyjwt
    with pytest.raises(pyjwt.PyJWTError):
        jwt_tokens.decode_token(tok)


def test_jwt_en_preview_sin_archivo_no_arranca(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_SECRETS_DIR", str(tmp_path))
    with pytest.raises(SystemExit) as e:
        jwt_tokens._secret()
    assert e.value.code == 3


def test_jwt_en_preview_prefiere_el_secreto_definido(monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("AUDITBRAIN_JWT_SECRET", "secreto-de-prueba-definido")
    assert jwt_tokens._secret() == "secreto-de-prueba-definido"


def test_jwt_fuera_de_preview_no_cambia(monkeypatch):
    assert jwt_tokens._secret() == DEV_LITERAL
    monkeypatch.setenv("AUDITBRAIN_JWT_SECRET", "prod")
    assert jwt_tokens._secret() == "prod"


# --- respaldo COOLIFY_FQDN -> PREVIEW_PUBLIC_HOST en el command del backend (Compose) -------------
# Evidencia del preview del PR #384 en Coolify 4.4.6: SERVICE_FQDN_BACKEND_10000 llegó vacío y
# COOLIFY_FQDN=384.api.preview.audit-ia.ec; el backend terminaba con código 3. El Compose rellena
# PREVIEW_PUBLIC_HOST desde COOLIFY_FQDN solo cuando está vacía; el validador no cambia.

import re as _re
import shutil as _shutil
import subprocess as _subprocess
from pathlib import Path as _Path

import yaml as _yaml

_COMPOSE = _Path(__file__).resolve().parents[1] / "docker-compose.preview.yml"
_FALLBACK = 'export PREVIEW_PUBLIC_HOST="${PREVIEW_PUBLIC_HOST:-${COOLIFY_FQDN:-}}"'


def _command_backend_interpolado() -> str:
    """El command del backend tal como lo entrega Compose ($$ -> $)."""
    c = _yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    return c["services"]["backend"]["command"].replace("$$", "$")


def test_compose_backend_respalda_preview_public_host_con_coolify_fqdn():
    cmd = _command_backend_interpolado()
    assert _FALLBACK in cmd, "el command debe rellenar PREVIEW_PUBLIC_HOST desde COOLIFY_FQDN solo si está vacía"
    assert cmd.index(_FALLBACK) < cmd.index("exec uvicorn"), "el respaldo va antes de arrancar uvicorn"
    crudo = _yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))["services"]["backend"]["command"]
    # Ninguna referencia de shell sin escapar (Compose la tomaría como variable propia); $( no cuenta.
    assert not _re.findall(r"(?<![$])[$](?![$(])(?:[{][^}]*[}]|[A-Za-z_0-9#]+)", crudo)
    assert "384" not in crudo, "no se fija ningún número de PR en el Compose"


def _host_resuelto_por_el_shell(public_host, coolify_fqdn) -> str:
    """Ejecuta el respaldo real del command en un sh POSIX y devuelve el PREVIEW_PUBLIC_HOST resultante."""
    env = {"PATH": os.environ.get("PATH", "")}
    if public_host is not None:
        env["PREVIEW_PUBLIC_HOST"] = public_host
    if coolify_fqdn is not None:
        env["COOLIFY_FQDN"] = coolify_fqdn
    r = _subprocess.run(["sh", "-c", "set -eu; " + _FALLBACK + '; printf "%s" "$PREVIEW_PUBLIC_HOST"'],
                        env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


_SIN_SH = _shutil.which("sh") is None


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
@pytest.mark.parametrize("public_host,coolify_fqdn,esperado", [
    ("", "384.api.preview.audit-ia.ec", ("coolify", "384")),        # caso real del PR #384
    (None, "384.api.preview.audit-ia.ec", ("coolify", "384")),      # variable ausente del todo
    ("384.api.preview.audit-ia.ec", "384.api.preview.audit-ia.ec", ("coolify", "384")),  # ambas coherentes
    ("77.api.preview.audit-ia.ec", "", ("coolify", "77")),          # el valor explícito manda
])
def test_respaldo_hostname_correcto(monkeypatch, public_host, coolify_fqdn, esperado):
    host = _host_resuelto_por_el_shell(public_host, coolify_fqdn)
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", host)
    if coolify_fqdn is not None:
        monkeypatch.setenv("COOLIFY_FQDN", coolify_fqdn)
    assert preview.preview_identity() == esperado


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
@pytest.mark.parametrize("public_host,coolify_fqdn,motivo", [
    ("", "", "ausente"),                                   # hostname ausente: sigue fallando cerrado
    (None, None, "ausente"),
    ("", "api.audit-ia.ec", "no coincide"),                # hostname productivo: rechazado
    ("", "consola.audit-ia.ec", "no coincide"),
    ("", "auditbrain-python-runner.onrender.com", "no coincide"),
    ("384.api.preview.audit-ia.ec", "385.api.preview.audit-ia.ec", "ambigua"),   # identidad contradictoria
    ("", "384.api.preview.audit-ia.ec,385.api.preview.audit-ia.ec", "ambigua"),
])
def test_respaldo_no_relaja_el_validador(monkeypatch, public_host, coolify_fqdn, motivo):
    host = _host_resuelto_por_el_shell(public_host, coolify_fqdn)
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", host)
    if coolify_fqdn is not None:
        monkeypatch.setenv("COOLIFY_FQDN", coolify_fqdn)
    with pytest.raises(preview.PreviewConfigError, match=motivo):
        preview.preview_identity()
    with pytest.raises(SystemExit) as e:
        preview.preview_bootstrap()
    assert e.value.code == 3


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
def test_respaldo_arranque_completo_del_caso_real(monkeypatch, secretos):
    """PREVIEW_PUBLIC_HOST vacío + COOLIFY_FQDN del PR #384 + resto de la configuración válida => arranca."""
    sha = "9175fe82cc4e78e22cfa5a7c4b70c1ea8ecf9e6b"
    host = _host_resuelto_por_el_shell("", "384.api.preview.audit-ia.ec")
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", host)
    monkeypatch.setenv("COOLIFY_FQDN", "384.api.preview.audit-ia.ec")
    monkeypatch.setenv("DATABASE_URL", "postgresql://auditbrain:x@db:5432/auditbrain")
    monkeypatch.setenv("BUILD_COMMIT", sha)
    monkeypatch.setenv("PREVIEW_EXPECTED_IMAGE_TAG", f"sha-{sha}")
    info = preview.preview_bootstrap(exit_on_error=False)
    assert info["preview"] is True and info["provider"] == "coolify" and info["pr"] == "384"
    assert info["config"] == "ok" and info["commit"] == sha
    regex = _re.compile(preview.cors_origin_regex_for(info))
    assert regex.fullmatch("https://384.consola.preview.audit-ia.ec") and regex.fullmatch("https://384.clientes.preview.audit-ia.ec")
    for otro in ("https://385.consola.preview.audit-ia.ec", "https://consola.audit-ia.ec", "https://384.consola.preview.audit-ia.ec:8443", "http://384.consola.preview.audit-ia.ec"):
        assert not regex.fullmatch(otro), otro
