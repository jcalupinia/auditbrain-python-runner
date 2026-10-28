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
        "CORS_ALLOW_ORIGINS", "BUILD_COMMIT", "PREVIEW_EXPECTED_IMAGE_TAG", "SOURCE_COMMIT",
        "AUDITBRAIN_API_KEY", "AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD",
        *preview.FORBIDDEN_INHERITED_IN_COOLIFY_PREVIEW)


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
    """Entorno de un preview de Coolify válido según el contrato F1 (identidad por SOURCE_COMMIT)."""
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", host or f"{pr}.api.preview.audit-ia.ec")
    monkeypatch.setenv("DATABASE_URL", "postgresql://auditbrain:x@db:5432/auditbrain")
    monkeypatch.setenv("BUILD_COMMIT", SHA)
    monkeypatch.setenv("SOURCE_COMMIT", SHA)
    monkeypatch.setenv("PREVIEW_EXPECTED_IMAGE_TAG", f"sha-{SHA}")
    monkeypatch.setenv("AUDITBRAIN_API_KEY", "k" * 48)
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "p" * 32)


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
    ("DATABASE_URL", "postgresql://auditbrain:x@z4wy8ngriiesg6z20n7ftcnj:5432/auditbrain", "producción"),  # F1: la base productiva se detecta antes como valor heredado
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


@pytest.mark.parametrize("valor", ["", "unknown", "abc123", SHA[:39], "g" * 40, "b" * 40, " " + SHA[:20]])
def test_coolify_exige_source_commit_de_40_hex_igual_a_build_commit(monkeypatch, secretos, valor):
    """F1 (C-01): en Coolify SOURCE_COMMIT ausente, vacío, unknown, corto, no hexadecimal o distinto => código 3."""
    _preview_valido(monkeypatch)
    if valor == "":
        monkeypatch.delenv("SOURCE_COMMIT")
    else:
        monkeypatch.setenv("SOURCE_COMMIT", valor)
    with pytest.raises(preview.PreviewConfigError, match="SOURCE_COMMIT"):
        preview.preview_bootstrap(exit_on_error=False)
    with pytest.raises(SystemExit) as e:
        preview.preview_bootstrap()
    assert e.value.code == 3


def test_coolify_source_commit_correcto_arranca(monkeypatch, secretos):
    _preview_valido(monkeypatch)
    info = preview.preview_bootstrap(exit_on_error=False)
    assert info["config"] == "ok" and info["commit"] == SHA and info["provider"] == "coolify"


def test_etiqueta_esperada_debe_ser_sha_del_source_commit(monkeypatch, secretos):
    _preview_valido(monkeypatch)
    monkeypatch.setenv("PREVIEW_EXPECTED_IMAGE_TAG", "sha-" + "d" * 40)
    with pytest.raises(preview.PreviewConfigError, match="no corresponde"):
        preview.preview_bootstrap(exit_on_error=False)


def _render_valido(monkeypatch, pr="55"):
    """Preview de Render existente: sin SOURCE_COMMIT y con su propio AUDITBRAIN_JWT_SECRET."""
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", f"auditbrain-python-runner-pr-{pr}.onrender.com")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", f"auditbrain-python-runner-pr-{pr}.onrender.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql://auditbrain:x@db:5432/auditbrain")
    monkeypatch.setenv("BUILD_COMMIT", SHA)
    monkeypatch.setenv("PREVIEW_EXPECTED_IMAGE_TAG", f"sha-{SHA}")
    monkeypatch.setenv("AUDITBRAIN_JWT_SECRET", "r" * 64)


def test_render_sin_source_commit_sigue_arrancando(monkeypatch, secretos):
    """Compatibilidad: los previews de Render no reciben SOURCE_COMMIT ni credenciales de prueba por volumen."""
    _render_valido(monkeypatch)
    info = preview.preview_bootstrap(exit_on_error=False)
    assert info["provider"] == "render" and info["pr"] == "55" and info["config"] == "ok"
    monkeypatch.setenv("SOURCE_COMMIT", "unknown")
    assert preview.preview_bootstrap(exit_on_error=False)["config"] == "ok"
    monkeypatch.setenv("SOURCE_COMMIT", "c" * 40)
    with pytest.raises(preview.PreviewConfigError, match="SOURCE_COMMIT"):
        preview.preview_bootstrap(exit_on_error=False)


@pytest.mark.parametrize("variable", ["AUDITBRAIN_API_KEY", "AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD"])
@pytest.mark.parametrize("valor", [None, "", "   "])
def test_coolify_rechaza_credenciales_de_prueba_ausentes_o_vacias(monkeypatch, secretos, variable, valor):
    """F1 (S-05): sin API key o sin contraseña de admin el backend no arranca (código 3)."""
    _preview_valido(monkeypatch)
    if valor is None:
        monkeypatch.delenv(variable)
    else:
        monkeypatch.setenv(variable, valor)
    with pytest.raises(preview.PreviewConfigError, match=variable):
        preview.preview_bootstrap(exit_on_error=False)
    with pytest.raises(SystemExit) as e:
        preview.preview_bootstrap()
    assert e.value.code == 3


@pytest.mark.parametrize("variable", list(preview.FORBIDDEN_INHERITED_IN_COOLIFY_PREVIEW))
def test_coolify_rechaza_credenciales_productivas_heredadas(monkeypatch, secretos, variable, caplog):
    """F1 (S-06): una credencial heredada de la app base hace fallar el arranque; el valor nunca se registra."""
    _preview_valido(monkeypatch)
    monkeypatch.setenv(variable, "VALOR-SECRETO-QUE-NO-DEBE-APARECER")
    with pytest.raises(preview.PreviewConfigError, match=variable):
        preview.preview_bootstrap(exit_on_error=False)
    with caplog.at_level("CRITICAL", logger="auditbrain"), pytest.raises(SystemExit) as e:
        preview.preview_bootstrap()
    assert e.value.code == 3
    assert "VALOR-SECRETO-QUE-NO-DEBE-APARECER" not in caplog.text


def test_coolify_rechaza_valores_que_apuntan_a_produccion(monkeypatch, secretos):
    _preview_valido(monkeypatch)
    monkeypatch.setenv("CUALQUIER_VARIABLE", "postgresql://u:p@z4wy8ngriiesg6z20n7ftcnj:5432/x")
    with pytest.raises(preview.PreviewConfigError, match="CUALQUIER_VARIABLE"):
        preview.preview_bootstrap(exit_on_error=False)
    monkeypatch.delenv("CUALQUIER_VARIABLE")
    monkeypatch.setenv("OTRA", "https://api.audit-ia.ec/v1")
    with pytest.raises(preview.PreviewConfigError, match="OTRA"):
        preview.preview_bootstrap(exit_on_error=False)
    monkeypatch.delenv("OTRA")
    assert preview.preview_bootstrap(exit_on_error=False)["config"] == "ok"


def test_fuera_de_preview_el_arranque_no_cambia(monkeypatch):
    """Producción conserva su semántica: nada de esto actúa sin APP_ENV=preview."""
    monkeypatch.setenv("AUDITBRAIN_JWT_SECRET", "prod")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-prod")
    assert preview.preview_bootstrap() == {"preview": False}
    assert preview.preview_provider() is None


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


def test_jwt_en_preview_coolify_ignora_la_variable_heredada(monkeypatch, secretos):
    """F1 (S-06): en Coolify el JWT se firma y valida SIEMPRE con el archivo del PR, aun con la variable presente."""
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "123.api.preview.audit-ia.ec")
    monkeypatch.setenv("AUDITBRAIN_JWT_SECRET", "secreto-heredado-que-no-debe-usarse")
    assert jwt_tokens._secret() == "S" * 64
    token = jwt_tokens.create_access_token("u", "admin")
    assert jwt_tokens.decode_token(token)["sub"] == "u"
    # Sin identidad válida tampoco se usa la variable: archivo del PR o nada.
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "")
    assert jwt_tokens._secret() == "S" * 64


def test_jwt_en_preview_render_conserva_su_variable(monkeypatch, tmp_path):
    """Compatibilidad: un preview de Render firma con la AUDITBRAIN_JWT_SECRET que Render genera para él."""
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "auditbrain-python-runner-pr-55.onrender.com")
    monkeypatch.setenv("PREVIEW_SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("AUDITBRAIN_JWT_SECRET", "secreto-de-render")
    assert jwt_tokens._secret() == "secreto-de-render"


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
    monkeypatch.setenv("SOURCE_COMMIT", sha)
    monkeypatch.setenv("PREVIEW_EXPECTED_IMAGE_TAG", f"sha-{sha}")
    monkeypatch.setenv("AUDITBRAIN_API_KEY", "k" * 48)
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "p" * 32)
    info = preview.preview_bootstrap(exit_on_error=False)
    assert info["preview"] is True and info["provider"] == "coolify" and info["pr"] == "384"
    assert info["config"] == "ok" and info["commit"] == sha
    regex = _re.compile(preview.cors_origin_regex_for(info))
    assert regex.fullmatch("https://384.consola.preview.audit-ia.ec") and regex.fullmatch("https://384.clientes.preview.audit-ia.ec")
    for otro in ("https://385.consola.preview.audit-ia.ec", "https://consola.audit-ia.ec", "https://384.consola.preview.audit-ia.ec:8443", "http://384.consola.preview.audit-ia.ec"):
        assert not regex.fullmatch(otro), otro


# --- F1: el guion real del command del backend (arranque seguro de secretos) ---------------------

_SCRIPT_BACKEND_CACHE = {}


def _script_backend_para_prueba(tmp_dir: _Path) -> _Path:
    """El command del backend interpolado por Compose, con /run/secrets en un directorio temporal y
    `exec uvicorn …` sustituido por una marca inofensiva. No arranca el backend real."""
    cmd = _command_backend_interpolado().strip()
    m = _re.fullmatch(r"sh -c '(.*)'", cmd, _re.S)
    assert m, "el command del backend debe ser sh -c '<guion>'"
    guion = m.group(1)
    assert "exec uvicorn app:app --host 0.0.0.0 --port 10000" in guion
    guion = guion.replace("exec uvicorn app:app --host 0.0.0.0 --port 10000", 'printf "%s" ARRANQUE_OK')
    guion = guion.replace("/run/secrets", str(tmp_dir).replace("\\", "/"))
    script = tmp_dir.parent / "backend_command.sh"
    script.write_text(guion, encoding="utf-8")
    return script


def _correr_backend_command(script: _Path, extra_env: dict | None = None) -> _subprocess.CompletedProcess:
    env = {"PATH": os.environ.get("PATH", ""), "COOLIFY_FQDN": "384.api.preview.audit-ia.ec"}
    env.update(extra_env or {})
    return _subprocess.run(["sh", str(script).replace("\\", "/")], env=env, capture_output=True, text=True, timeout=60)


def _secretos_completos(d: _Path) -> dict:
    d.mkdir(parents=True, exist_ok=True)
    valores = {"pg_password": "P" * 40, "jwt_secret": "J" * 64, "admin_password": "A" * 32, "api_key": "K" * 48}
    for k, v in valores.items():
        (d / k).write_text(v, encoding="utf-8")
    return valores


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
def test_command_backend_arranca_solo_con_los_cuatro_secretos(tmp_path):
    valores = _secretos_completos(tmp_path / "secrets")
    r = _correr_backend_command(_script_backend_para_prueba(tmp_path / "secrets"))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "ARRANQUE_OK"
    salida = r.stdout + r.stderr
    for v in valores.values():
        assert v not in salida, "el guion no debe imprimir secretos"


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
@pytest.mark.parametrize("faltante", ["pg_password", "admin_password", "api_key", "jwt_secret"])
def test_command_backend_no_arranca_si_falta_o_esta_vacio_un_secreto(tmp_path, faltante):
    """F1 (S-05): a diferencia de `export VAR="$(cat f)"`, el guion termina con error sin ejecutar uvicorn."""
    d = tmp_path / "secrets"
    valores = _secretos_completos(d)
    (d / faltante).unlink()
    r = _correr_backend_command(_script_backend_para_prueba(d))
    assert r.returncode == 3 and "ARRANQUE_OK" not in r.stdout
    assert faltante in r.stderr and not any(v in r.stdout + r.stderr for v in valores.values())
    (d / faltante).write_text("", encoding="utf-8")  # existe pero vacío
    r = _correr_backend_command(_script_backend_para_prueba(d))
    assert r.returncode == 3 and "ARRANQUE_OK" not in r.stdout


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
def test_command_backend_no_arranca_si_falla_la_lectura(tmp_path):
    """Un `cat` que falla (archivo ilegible: es un directorio) también detiene el arranque."""
    d = tmp_path / "secrets"
    _secretos_completos(d)
    (d / "api_key").unlink()
    (d / "api_key").mkdir()  # `-s` es verdadero para un directorio no vacío en algunos sh; `cat` falla
    (d / "api_key" / "x").write_text("x", encoding="utf-8")
    r = _correr_backend_command(_script_backend_para_prueba(d))
    assert r.returncode == 3 and "ARRANQUE_OK" not in r.stdout


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
@pytest.mark.parametrize("heredada", ["AUDITBRAIN_JWT_SECRET", "AUDITBRAIN_API_KEY", "AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD"])
def test_command_backend_rechaza_credenciales_heredadas_antes_de_sobrescribirlas(tmp_path, heredada):
    """F1 (S-06): si Coolify inyectara la credencial, el guion sale con 3 antes de leer los archivos."""
    d = tmp_path / "secrets"
    _secretos_completos(d)
    r = _correr_backend_command(_script_backend_para_prueba(d), {heredada: "valor-heredado"})
    assert r.returncode == 3 and "ARRANQUE_OK" not in r.stdout and "valor-heredado" not in r.stdout + r.stderr


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
def test_command_backend_exporta_las_variables_reales(tmp_path):
    """Las tres variables reales del backend quedan exportadas con el contenido de los archivos."""
    d = tmp_path / "secrets"
    valores = _secretos_completos(d)
    script = _script_backend_para_prueba(d)
    g = script.read_text(encoding="utf-8").replace('printf "%s" ARRANQUE_OK',
        'printf "%s|%s|%s|%s" "$DATABASE_URL" "$AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD" "$AUDITBRAIN_API_KEY" "$PREVIEW_PUBLIC_HOST"')
    script.write_text(g, encoding="utf-8")
    r = _correr_backend_command(script)
    assert r.returncode == 0, r.stderr
    url, adm, key, host = r.stdout.split("|")
    assert url == f"postgresql://auditbrain:{valores['pg_password']}@db:5432/auditbrain"
    assert adm == valores["admin_password"] and key == valores["api_key"]
    assert host == "384.api.preview.audit-ia.ec"


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
def test_command_backend_exporta_source_commit_desde_el_portador(tmp_path):
    """El command recupera SOURCE_COMMIT del portador PREVIEW_SOURCE_COMMIT=commit-<sha> que entrega Coolify.
    Es la corrección del preview #405 (backend en bucle por «SOURCE_COMMIT ausente»). Cada PR trae el suyo."""
    sha = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
    d = tmp_path / "secrets"
    _secretos_completos(d)
    script = _script_backend_para_prueba(d)
    g = script.read_text(encoding="utf-8").replace('printf "%s" ARRANQUE_OK', 'printf "%s" "$SOURCE_COMMIT"')
    script.write_text(g, encoding="utf-8")
    r = _correr_backend_command(script, {"PREVIEW_SOURCE_COMMIT": f"commit-{sha}"})
    assert r.returncode == 0, r.stderr
    assert r.stdout == sha, f"SOURCE_COMMIT exportado = {r.stdout!r}, se esperaba {sha!r}"


@pytest.mark.skipif(_SIN_SH, reason="requiere un sh POSIX")
def test_command_backend_source_commit_vacio_si_falta_el_portador_sin_abortar(tmp_path):
    """Sin PREVIEW_SOURCE_COMMIT (p. ej. fuera de Coolify) el command no aborta bajo `set -u`: SOURCE_COMMIT
    queda vacío y el rechazo lo hace después preview_bootstrap (cubierto en test_coolify_exige_source_commit…)."""
    d = tmp_path / "secrets"
    _secretos_completos(d)
    script = _script_backend_para_prueba(d)
    g = script.read_text(encoding="utf-8").replace('printf "%s" ARRANQUE_OK', 'printf "[%s]" "$SOURCE_COMMIT"')
    script.write_text(g, encoding="utf-8")
    r = _correr_backend_command(script)  # sin PREVIEW_SOURCE_COMMIT en el entorno
    assert r.returncode == 0, r.stderr
    assert r.stdout == "[]", f"se esperaba SOURCE_COMMIT vacío, salió {r.stdout!r}"


def test_portador_source_commit_encadenado_con_el_validador(monkeypatch, secretos):
    """Integración: el SHA que el command extrae del portador es el que preview_bootstrap valida contra
    BUILD_COMMIT. Un valor correcto arranca; uno ausente o distinto sigue siendo rechazado (sin debilitar F1)."""
    _preview_valido(monkeypatch)  # SOURCE_COMMIT = BUILD_COMMIT = SHA
    assert preview.preview_bootstrap(exit_on_error=False)["commit"] == SHA
    # Lo que el portador vacío produciría (SOURCE_COMMIT="") debe seguir rechazándose.
    monkeypatch.setenv("SOURCE_COMMIT", "")
    with pytest.raises(preview.PreviewConfigError, match="SOURCE_COMMIT"):
        preview.preview_bootstrap(exit_on_error=False)


def test_command_backend_sin_variables_de_shell_sin_escapar():
    """Compose vaciaría en silencio cualquier `$var`/`${…}` no escapado como `$$` en el command."""
    crudo = _yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))["services"]["backend"]["command"]
    assert not _re.findall(r"(?<![$])[$](?![$(])(?:[{][^}]*[}]|[A-Za-z_0-9#]+)", crudo)
    assert "384" not in crudo


# --- F1 v3: cinco PR simulados sin colisiones (pruebas de IDENTIDAD; no prometen 5 previews en RAM) --------

_PRS = [("384", "c093ab3df36e1ec4a8601a18874040a3a69b063f"), ("385", "1" * 40), ("390", "2" * 40),
        ("401", "3" * 40), ("512", "4" * 40)]


def _entorno_pr(monkeypatch, tmp_path, pr, sha):
    d = tmp_path / f"secrets-pr-{pr}"
    d.mkdir()
    (d / "jwt_secret").write_text(f"J{pr}".ljust(64, "x"), encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", "")
    monkeypatch.setenv("COOLIFY_FQDN", f"{pr}.api.preview.audit-ia.ec")
    monkeypatch.setenv("PREVIEW_PUBLIC_HOST", _host_resuelto_por_el_shell("", f"{pr}.api.preview.audit-ia.ec") if not _SIN_SH else f"{pr}.api.preview.audit-ia.ec")
    monkeypatch.setenv("PREVIEW_SECRETS_DIR", str(d))
    monkeypatch.setenv("DATABASE_URL", "postgresql://auditbrain:x@db:5432/auditbrain")
    monkeypatch.setenv("BUILD_COMMIT", sha)
    monkeypatch.setenv("SOURCE_COMMIT", sha)
    monkeypatch.setenv("PREVIEW_EXPECTED_IMAGE_TAG", f"sha-{sha}")
    monkeypatch.setenv("AUDITBRAIN_API_KEY", f"key-{pr}".ljust(48, "k"))
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", f"adm-{pr}".ljust(32, "a"))
    return d


def test_cinco_pr_simulados_identidades_sin_colision(monkeypatch, tmp_path):
    """Cinco PR distintos: imágenes, host, CORS, portal, secreto JWT y directorio de secretos propios; la
    identidad de cada uno rechaza los orígenes de los otros cuatro. Es una prueba de identidad, no de capacidad."""
    resultados = {}
    for pr, sha in _PRS:
        monkeypatch.setattr(jwt_tokens, "_PREVIEW_SECRET", None)
        d = _entorno_pr(monkeypatch, tmp_path, pr, sha)
        info = preview.preview_bootstrap(exit_on_error=False)
        assert info["pr"] == pr and info["commit"] == sha and info["config"] == "ok"
        resultados[pr] = {
            "imagen": f"ghcr.io/jcalupinia/auditbrain-preview-backend:sha-{sha}",
            "host": os.environ["PREVIEW_PUBLIC_HOST"],
            "portal": preview.client_portal_url(),
            "cors": _re.compile(preview.cors_origin_regex_for(info)),
            "jwt": jwt_tokens._secret(),
            "secrets_dir": str(d),
        }
    for campo in ("imagen", "host", "portal", "jwt", "secrets_dir"):
        valores = [r[campo] for r in resultados.values()]
        assert len(set(valores)) == len(_PRS), f"colisión en {campo}"
    for pr, r in resultados.items():
        assert r["cors"].fullmatch(f"https://{pr}.consola.preview.audit-ia.ec")
        for otro in resultados:
            if otro != pr:
                assert not r["cors"].fullmatch(f"https://{otro}.consola.preview.audit-ia.ec"), f"{pr} acepta el origen de {otro}"
        assert r["portal"] == f"https://{pr}.clientes.preview.audit-ia.ec"


def test_cinco_pr_simulados_imagen_de_otro_pr_es_rechazada(monkeypatch, tmp_path):
    """Si a un PR le llegara la imagen (BUILD_COMMIT) de otro, el arranque falla: SOURCE_COMMIT != BUILD_COMMIT."""
    (pr_a, sha_a), (pr_b, sha_b) = _PRS[0], _PRS[1]
    _entorno_pr(monkeypatch, tmp_path, pr_a, sha_a)
    monkeypatch.setenv("BUILD_COMMIT", sha_b)
    monkeypatch.setenv("PREVIEW_EXPECTED_IMAGE_TAG", f"sha-{sha_b}")  # la etiqueta compartida apuntaría al otro PR
    with pytest.raises(preview.PreviewConfigError, match="SOURCE_COMMIT"):
        preview.preview_bootstrap(exit_on_error=False)


_SIN_DOCKER = _shutil.which("docker") is None


@pytest.mark.skipif(_SIN_DOCKER, reason="requiere docker compose (solo `config`, no levanta nada)")
def test_cinco_pr_simulados_docker_compose_config_imagenes_distintas(tmp_path):
    """`docker compose config --images` con cinco SOURCE_COMMIT ficticios: cada PR resuelve sus tres imágenes
    y ninguna coincide con las de otro PR. Solo `config`: no se crea ni levanta ningún recurso."""
    vistas = {}
    for pr, sha in _PRS:
        # Entorno completo del proceso (el CLI de Docker localiza el plugin compose por variables del sistema)
        # con la identidad del PR por encima; `config` solo interpola, no crea ni levanta nada.
        env = dict(os.environ, SOURCE_COMMIT=sha,
                   SERVICE_FQDN_BACKEND_10000=f"{pr}.api.preview.audit-ia.ec",
                   SERVICE_FQDN_CONSOLA_80=f"{pr}.consola.preview.audit-ia.ec",
                   SERVICE_FQDN_CLIENTES_80=f"{pr}.clientes.preview.audit-ia.ec")
        r = _subprocess.run(["docker", "compose", "-f", str(_COMPOSE), "config", "--images"], env=env,
                            capture_output=True, text=True, timeout=120)
        if r.returncode != 0 and "Cannot connect" in (r.stderr or ""):
            pytest.skip("docker instalado pero sin demonio accesible")
        assert r.returncode == 0, r.stderr
        imgs = {l.strip() for l in r.stdout.splitlines() if l.startswith("ghcr.io/")}
        assert imgs == {f"ghcr.io/jcalupinia/auditbrain-preview-{s}:sha-{sha}" for s in ("backend", "consola", "clientes")}
        vistas[pr] = imgs
    todas = [i for v in vistas.values() for i in v]
    assert len(todas) == len(set(todas)) == 15, "las imágenes de los cinco PR deben ser todas distintas"


@pytest.mark.skipif(_SIN_SH or os.name == "nt", reason="requiere sh POSIX y permisos de archivo reales (no Windows)")
def test_command_backend_no_arranca_si_un_secreto_es_ilegible(tmp_path):
    """Permisos fallidos: el archivo existe y no está vacío pero no se puede leer (modo 000)."""
    if os.geteuid() == 0:  # root lee cualquier archivo
        pytest.skip("root ignora los permisos")
    d = tmp_path / "secrets"
    _secretos_completos(d)
    (d / "api_key").chmod(0o000)
    try:
        r = _correr_backend_command(_script_backend_para_prueba(d))
    finally:
        (d / "api_key").chmod(0o600)
    assert r.returncode == 3 and "ARRANQUE_OK" not in r.stdout
