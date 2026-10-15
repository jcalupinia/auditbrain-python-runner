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
        assert s[n]["image"].startswith(f"ghcr.io/jcalupinia/auditbrain-{n}:${{PREVIEW_IMAGE_TAG:?")
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
    assert "pg_password" in s["init"]["healthcheck"]["test"][-1] and "jwt_secret" in s["init"]["healthcheck"]["test"][-1]
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
        if k in ("PREVIEW_PUBLIC_HOST",):
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
