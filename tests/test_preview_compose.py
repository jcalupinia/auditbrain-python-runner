"""docker-compose.preview.yml: reglas de aislamiento y de recursos de los previews.

Fija en código las decisiones aprobadas (2026-10-15): un solo preview activo con un
presupuesto total de memoria <= 1 296 MiB, sin puertos publicados, imágenes por commit
exacto del PR (etiqueta obligatoria), secretos generados dentro del preview, ninguna
variable hacia producción, PostgreSQL 18 montado en /var/lib/postgresql y prioridad de
producción ante el OOM killer.
"""

from pathlib import Path

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.preview.yml"
PRESUPUESTO_MIB = 1296
PRODUCCION = ("audit-ia.ec", "onrender.com", "z4wy8ngriiesg6z20n7ftcnj")
# Secretos generados por init dentro del volumen del PR y su longitud (Etapa 3B).
SECRETOS = {"pg_password": 40, "jwt_secret": 64, "admin_password": 32, "api_key": 48}
ADMIN_EMAIL_PREVIEW = "preview-admin@audit-ia.ec"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _mib(valor: str) -> int:
    v = str(valor).lower()
    return int(v[:-1]) * (1024 if v.endswith("g") else 1)


def _env(servicio: dict) -> dict:
    env = servicio.get("environment") or []
    if isinstance(env, dict):
        return {k: ("" if v is None else str(v)) for k, v in env.items()}
    out = {}
    for e in env:
        k, _, v = e.partition("=")
        out[k] = v
    return out


def test_servicios_y_sin_puertos_publicados(compose):
    assert list(compose["services"]) == ["init", "db", "backend", "consola", "clientes"]
    for n, s in compose["services"].items():
        assert "ports" not in s, f"{n} no debe publicar puertos"


def test_presupuesto_de_memoria_y_prioridad_de_produccion(compose):
    s = compose["services"]
    total = sum(_mib(v["mem_limit"]) for v in s.values())
    assert total <= PRESUPUESTO_MIB, f"tope total {total} MiB > {PRESUPUESTO_MIB}"
    for n in ("db", "backend", "consola", "clientes"):
        assert s[n]["mem_limit"] == s[n]["memswap_limit"], f"{n}: el swap del host no amplía el límite"
        assert s[n]["oom_score_adj"] >= 600, f"{n}: debe morir antes que producción"
        assert s[n]["cpu_shares"] <= 256, f"{n}: prioridad de CPU por debajo de producción (1024)"
        assert "pids_limit" in s[n] and "healthcheck" in s[n]
    assert _mib(s["backend"]["mem_limit"]) <= 1024


def test_imagenes_por_commit_exacto_y_sin_build_en_el_servidor(compose):
    s = compose["services"]
    for n in ("backend", "consola", "clientes"):
        assert "build" not in s[n], f"{n}: nada se construye en el servidor"
        assert s[n]["image"].startswith(f"ghcr.io/jcalupinia/auditbrain-preview-{n}:${{PREVIEW_IMAGE_TAG:?")
        assert "auditbrain-preview-" in s[n]["image"], "los paquetes públicos antiguos auditbrain-<svc> no se reutilizan"
    assert s["db"]["image"] == "postgres:18-alpine"
    assert s["init"]["image"].startswith("alpine:")
    env = _env(s["backend"])
    assert env["PREVIEW_EXPECTED_IMAGE_TAG"] == "${PREVIEW_IMAGE_TAG}"
    assert "SOURCE_COMMIT" not in " ".join(s["backend"]["image"] for _ in [0]), "no se confía en SOURCE_COMMIT"


def test_identidad_del_pr_desde_la_variable_magica_correcta(compose):
    env = _env(compose["services"]["backend"])
    assert "SERVICE_FQDN_BACKEND_10000" in env
    assert env["PREVIEW_PUBLIC_HOST"] == "${SERVICE_FQDN_BACKEND_10000}"
    assert env["APP_ENV"] == "preview"
    assert "SERVICE_FQDN_CONSOLA_80" in _env(compose["services"]["consola"])
    assert "SERVICE_FQDN_CLIENTES_80" in _env(compose["services"]["clientes"])


def test_secretos_dentro_del_preview_y_nunca_de_coolify(compose):
    s = compose["services"]
    # Se inspeccionan los servicios ya parseados (no el texto): los comentarios del archivo pueden
    # mencionar SERVICE_PASSWORD_* para explicar por qué NO se usa.
    for nombre, svc in s.items():
        env = _env(svc)
        volcado = " ".join([*env.keys(), *map(str, env.values()), str(svc.get("command", ""))])
        assert "SERVICE_PASSWORD" not in volcado, f"{nombre}: SERVICE_PASSWORD_* se comparte entre previews"
        assert "AUDITBRAIN_JWT_SECRET" not in volcado, f"{nombre}: el secreto JWT no va por variables"
    assert s["db"]["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/pg_password"
    assert "secrets:/run/secrets:ro" in s["db"]["volumes"] and "secrets:/run/secrets:ro" in s["backend"]["volumes"]
    assert s["db"]["depends_on"]["init"]["condition"] == "service_healthy"
    hc = s["init"]["healthcheck"]["test"][-1]
    assert all(n in hc for n in SECRETOS), "el healthcheck de init exige los cuatro secretos"
    assert s["backend"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert _env(s["backend"])["PREVIEW_SECRETS_DIR"] == "/run/secrets"
    assert "cat /run/secrets/pg_password" in s["backend"]["command"] and "@db:5432/auditbrain" in s["backend"]["command"]


def test_postgres_18_monta_el_volumen_en_var_lib_postgresql(compose):
    assert "pgdata:/var/lib/postgresql" in compose["services"]["db"]["volumes"]
    assert not any(v.endswith("/var/lib/postgresql/data") for v in compose["services"]["db"]["volumes"])


def test_ninguna_variable_apunta_a_produccion(compose):
    env = _env(compose["services"]["backend"])
    assert env["CORS_ALLOW_ORIGINS"] == ""
    assert env["CLIENT_PORTAL_URL"].endswith(".invalid")
    assert env["DOCUMENT_SERVICE"] == "http://127.0.0.1:9"
    for k, v in env.items():
        if k in ("PREVIEW_PUBLIC_HOST", "AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL"):
            continue
        assert not any(p in v for p in PRODUCCION), f"{k}={v} apunta a producción"
    for clave in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "RESEND_API_KEY", "STRIPE_SECRET_KEY",
                  "GOOGLE_API_KEY", "CANVA_MCP_OAUTH_TOKEN", "LOCAL_LLM_BASE_URL"):
        assert clave not in env


def test_red_interna_para_init_y_db(compose):
    assert compose["networks"]["preview_internal"]["internal"] is True
    for n in ("init", "db"):
        assert compose["services"][n]["networks"] == ["preview_internal"]
    assert set(compose["volumes"]) == {"secrets", "pgdata", "appdata"}


def test_sin_claves_propias_de_coolify(compose):
    """`docker compose config` rechaza claves ajenas al esquema (p. ej. `exclude_from_hc` de Coolify)."""
    for nombre, svc in compose["services"].items():
        assert "exclude_from_hc" not in svc, f"{nombre}: clave propia de Coolify, inválida para docker compose"


# ---------------------------------------------------------------------------------------
# Etapa 3B — credenciales de prueba exclusivas por PR (T1..T6 del diseño aprobado)
# ---------------------------------------------------------------------------------------
import os
import re
import shutil
import subprocess


def _script_init(compose) -> str:
    """El guion real de init (sin el `sleep` que lo mantiene vivo)."""
    cmd = compose["services"]["init"]["command"].strip()
    m = re.fullmatch(r"sh -c '(.*)'", cmd, re.S)
    assert m, "el command de init debe ser sh -c '<guion>'"
    return m.group(1).replace("exec sleep infinity", "")


def test_t1_orden_de_inicializacion_y_cuatro_secretos(compose):
    s = compose["services"]
    guion = _script_init(compose)
    for nombre, largo in SECRETOS.items():
        assert f"gen {nombre} {largo}" in guion, f"init debe generar {nombre} de {largo} caracteres"
    assert "umask 077" in guion and "chmod 600" in guion and ".tmp" in guion and "mv " in guion
    assert '[ -s "/secrets/$1" ] && return 0' in guion, "idempotencia: un archivo existente no se regenera"
    assert "/dev/urandom" in guion
    hc = s["init"]["healthcheck"]["test"][-1]
    assert all(n in hc for n in SECRETOS)
    assert s["db"]["depends_on"]["init"]["condition"] == "service_healthy"
    assert s["backend"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert "secrets:/run/secrets:ro" in s["backend"]["volumes"]
    assert "secrets:/secrets" in s["init"]["volumes"]


def test_t2_sin_variables_compartidas_de_credenciales(compose):
    s = compose["services"]
    prohibidas = ("PREVIEW_ADMIN_EMAIL", "PREVIEW_ADMIN_PASSWORD", "PREVIEW_API_KEY")
    for nombre, svc in s.items():
        env = _env(svc)
        volcado = " ".join([*env.keys(), *env.values(), str(svc.get("command", ""))])
        for p in prohibidas:
            assert p not in volcado, f"{nombre}: {p} es una variable compartida entre previews"
    env = _env(s["backend"])
    assert "AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD" not in env and "AUDITBRAIN_API_KEY" not in env
    cmd = s["backend"]["command"]
    assert "set -eu" in cmd
    assert 'export AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD="$(cat /run/secrets/admin_password)"' in cmd
    assert 'export AUDITBRAIN_API_KEY="$(cat /run/secrets/api_key)"' in cmd
    assert env["AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL"] == ADMIN_EMAIL_PREVIEW
    # La única variable obligatoria (:?) que queda es la etiqueta de la imagen.
    sin_comentarios = "\n".join(l for l in COMPOSE.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
    assert set(re.findall(r"\$\{([A-Z_]+):\?", sin_comentarios)) == {"PREVIEW_IMAGE_TAG"}


def test_t3_nombres_reales_de_las_variables_del_backend(compose):
    import inspect

    from backend.app.auth import service as auth_service
    from backend.app.core import config as core_config

    fuente = inspect.getsource(auth_service.ensure_bootstrap_admin)
    assert "AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL" in fuente and "AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD" in fuente
    assert "AUDITBRAIN_API_KEY" in inspect.getsource(core_config)
    cmd = compose["services"]["backend"]["command"]
    for var in ("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "AUDITBRAIN_API_KEY"):
        assert f"export {var}=" in cmd


def test_t4_el_correo_del_admin_pasa_el_validador_real(compose):
    from backend.app.auth.service import _email_valido

    assert _email_valido(_env(compose["services"]["backend"])["AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL"])
    assert not _email_valido("admin@preview.invalid"), "regresión: .invalid lo rechaza EmailStr y el admin no se crearía"
    # No es una identidad de la configuración productiva del repositorio.
    render = (COMPOSE.parent / "render.yaml").read_text(encoding="utf-8")
    assert ADMIN_EMAIL_PREVIEW not in render


@pytest.mark.skipif(shutil.which("sh") is None, reason="requiere un sh POSIX")
def test_t5_generador_local_idempotente_e_independiente(compose, tmp_path):
    """Aproximación local (sh del sistema, no busybox ash): la versión con alpine:3.20 corre en CI."""
    guion = _script_init(compose).replace("/secrets", "$SECRETS")
    script = tmp_path / "init.sh"
    script.write_text(guion, encoding="utf-8")

    def correr(vol: Path) -> str:
        env = dict(os.environ, SECRETS=str(vol).replace("\\", "/"))
        r = subprocess.run(["sh", str(script).replace("\\", "/")], env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return r.stdout + r.stderr

    a, b = tmp_path / "a", tmp_path / "b"
    salida = correr(a)
    assert salida.strip() == "secrets listos"
    valores = {}
    for nombre, largo in SECRETOS.items():
        v = (a / nombre).read_bytes()
        assert len(v) == largo, f"{nombre}: {len(v)} bytes, se esperaban {largo} (sin salto de línea final)"
        assert re.fullmatch(rb"[A-Za-z0-9]+", v), f"{nombre}: solo alfanumérico"
        valores[nombre] = v
        if os.name != "nt":
            assert oct((a / nombre).stat().st_mode & 0o777) == "0o600"
    assert not list(a.glob(".*.tmp")), "sin temporales residuales"
    for v in valores.values():
        assert v.decode() not in salida, "la salida del guion no debe contener secretos"
    correr(a)  # segunda ejecución = redespliegue del mismo PR
    for nombre, v in valores.items():
        assert (a / nombre).read_bytes() == v, f"{nombre} se regeneró en la segunda ejecución"
    correr(b)  # otro volumen = otro PR
    for nombre, v in valores.items():
        assert (b / nombre).read_bytes() != v, f"{nombre} se repite entre dos PR"


def test_t6_ningun_archivo_imprime_secretos():
    raiz = COMPOSE.parent
    archivos = [COMPOSE, *sorted((raiz / "scripts").glob("preview_*")), *sorted((raiz / ".github/workflows").glob("preview-*.yml"))]
    patron_lectura = re.compile(r"\bcat\s+(/run)?/secrets/")
    for f in archivos:
        for n, linea in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if patron_lectura.search(linea):
                # Única lectura permitida: el export del command del backend en el Compose.
                assert f == COMPOSE and "export " in linea and "$(cat /run/secrets/" in linea, f"{f.name}:{n} lee un secreto fuera del export del backend"
            assert not re.search(r"echo\s+\"?\$s\b", linea), f"{f.name}:{n} imprime el valor generado"
