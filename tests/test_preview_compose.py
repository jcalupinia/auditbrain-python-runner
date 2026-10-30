"""docker-compose.preview.yml: reglas de aislamiento y de recursos de los previews.

Fija en código las decisiones aprobadas (2026-10-15, v3 2026-10-19): presupuesto de memoria
por preview <= 1 296 MiB (el número de previews simultáneos lo decide la admisión dinámica de
F2 según la capacidad real del host; el antiguo cupo fijo de 1 es obsoleto y el Compose no fija ninguno), sin puertos publicados, imágenes por commit
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
        assert s[n]["image"] == f"ghcr.io/jcalupinia/auditbrain-preview-{n}:sha-${{SOURCE_COMMIT:?SOURCE_COMMIT requerido}}"
        assert "auditbrain-preview-" in s[n]["image"], "los paquetes públicos antiguos auditbrain-<svc> no se reutilizan"
    assert s["db"]["image"] == "postgres:18-alpine"
    assert s["init"]["image"].startswith("alpine:")
    env = _env(s["backend"])
    # Identidad por commit (F1): la etiqueta esperada y el commit llegan del mismo valor que interpoló las
    # imágenes. SOURCE_COMMIT no se declara con su propio nombre (el analizador de Coolify crearía la variable
    # obsoleta, ver test_regresion_analizador_coolify…): se transporta con prefijo `commit-` y el command lo
    # recupera como SOURCE_COMMIT en el runtime (ver test_source_commit_llega_al_runtime_del_backend).
    assert env["PREVIEW_EXPECTED_IMAGE_TAG"] == "sha-${SOURCE_COMMIT:?SOURCE_COMMIT requerido}"
    assert env["PREVIEW_SOURCE_COMMIT"] == "commit-${SOURCE_COMMIT:?SOURCE_COMMIT requerido}"
    assert "SOURCE_COMMIT" not in env, "declararla con ${SOURCE_COMMIT:?…} hace que el analizador de Coolify cree la variable obsoleta"
    assert _env(s["init"])["PREVIEW_EXPECTED_IMAGE_TAG"] == "sha-${SOURCE_COMMIT:?SOURCE_COMMIT requerido}"
    assert "PREVIEW_IMAGE_TAG" not in COMPOSE.read_text(encoding="utf-8"), "la variable compartida de Coolify ya no se usa"
    assert "latest" not in " ".join(s[n]["image"] for n in ("backend", "consola", "clientes"))


def test_source_commit_llega_al_runtime_del_backend(compose):
    """El backend debe recibir SOURCE_COMMIT en su ENTORNO (lo exige preview_bootstrap). Coolify no lo inyecta
    por env_file (incidente del preview #405: backend en bucle de reinicio por «SOURCE_COMMIT ausente»), así que
    se transporta con el portador PREVIEW_SOURCE_COMMIT=commit-${SOURCE_COMMIT} (valor que NO empieza por `$`,
    a salvo del analizador de Coolify) y el command lo recupera. Dinámico por PR: ningún valor fijo en el archivo."""
    s = compose["services"]
    env = _env(s["backend"])
    # Portador analizador-safe (no empieza por `$`) y con el mismo ${SOURCE_COMMIT} obligatorio que las imágenes.
    assert env["PREVIEW_SOURCE_COMMIT"] == "commit-${SOURCE_COMMIT:?SOURCE_COMMIT requerido}"
    assert not env["PREVIEW_SOURCE_COMMIT"].startswith("$"), "el analizador de Coolify crearía una variable obsoleta"
    # Nunca declarar la variable con su propio nombre (recrearía el incidente del 2026-10-20).
    assert "SOURCE_COMMIT" not in env
    # El command recupera SOURCE_COMMIT del portador, de forma segura bajo `set -u` (`:-` antes de recortar).
    cmd = s["backend"]["command"]
    assert 'export SOURCE_COMMIT="$${PREVIEW_SOURCE_COMMIT:-}"' in cmd
    assert 'export SOURCE_COMMIT="$${SOURCE_COMMIT#commit-}"' in cmd
    assert cmd.index("PREVIEW_SOURCE_COMMIT") < cmd.index("exec uvicorn"), "SOURCE_COMMIT se exporta antes de arrancar"
    # El analizador de Coolify no debe crear ninguna variable a partir de este portador.
    assert _simular_analizador_coolify({"services": {"backend": {"environment": [
        f"PREVIEW_SOURCE_COMMIT={env['PREVIEW_SOURCE_COMMIT']}"]}}}) == []


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
        # El secreto JWT nunca va por variables de entorno (el command solo lo menciona para RECHAZARLO si llega heredado).
        assert "AUDITBRAIN_JWT_SECRET" not in env, f"{nombre}: el secreto JWT no va por variables"
        assert "AUDITBRAIN_JWT_SECRET=" not in str(svc.get("command", "")), f"{nombre}: el command no define el secreto JWT"
    assert s["db"]["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/pg_password"
    assert "secrets:/run/secrets:ro" in s["db"]["volumes"] and "secrets:/run/secrets:ro" in s["backend"]["volumes"]
    assert s["db"]["depends_on"]["init"]["condition"] == "service_healthy"
    hc = s["init"]["healthcheck"]["test"][-1]
    assert all(n in hc for n in SECRETOS), "el healthcheck de init exige los cuatro secretos"
    assert s["backend"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert _env(s["backend"])["PREVIEW_SECRETS_DIR"] == "/run/secrets"
    assert "cat /run/secrets/pg_password" in s["backend"]["command"] and "@db:5432/auditbrain" in s["backend"]["command"]
    assert "postgresql://auditbrain:$$pg@db:5432/auditbrain" in s["backend"]["command"], "el host de la base es exclusivamente db"


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


def _redes(svc: dict) -> set:
    """Nombres de red de un servicio, admitiendo forma corta (lista) y larga (dict con aliases)."""
    nets = svc.get("networks") or []
    return set(nets.keys()) if isinstance(nets, dict) else set(nets)


def test_red_interna_para_init_y_db(compose):
    assert compose["networks"]["preview_internal"]["internal"] is True
    # init y db SOLO en la red interna aislada (db además con alias explícito, ver test siguiente).
    assert _redes(compose["services"]["init"]) == {"preview_internal"}
    assert _redes(compose["services"]["db"]) == {"preview_internal"}
    assert set(compose["volumes"]) == {"secrets", "pgdata", "appdata"}


def test_db_expone_alias_estable_db_para_resolver_en_coolify(compose):
    """El backend arma DATABASE_URL=…@db:5432 y preview_bootstrap EXIGE que el host sea `db`.
    En los previews de Coolify el servicio se publica con sufijo de PR (db-pr-<n>) y su alias DNS por
    defecto deja de ser `db` → «could not translate host name db». El alias explícito `db` en la red
    interna lo mantiene resoluble para CUALQUIER PR, sin fijar números y sin salir de preview_internal."""
    s = compose["services"]
    db_nets = s["db"].get("networks")
    assert isinstance(db_nets, dict) and "preview_internal" in db_nets, "db debe declarar la red en forma larga"
    aliases = (db_nets["preview_internal"] or {}).get("aliases") or []
    assert "db" in aliases, "el servicio db debe exponer el alias de red estable `db`"
    # El alias vive SOLO en la red interna aislada (internal: true), nunca en una red hacia producción.
    assert _redes(s["db"]) == {"preview_internal"}
    assert compose["networks"]["preview_internal"]["internal"] is True
    # El host de conexión sigue siendo exactamente `db` (lo exige _check_database_url del backend).
    assert "postgresql://auditbrain:$$pg@db:5432/auditbrain" in s["backend"]["command"]
    # El backend comparte esa red interna, así que resuelve el alias `db`.
    assert "preview_internal" in _redes(s["backend"])
    # Ningún número de PR fijo (la corrección es dinámica para todos los previews).
    for alias in aliases:
        assert "-pr-" not in alias and alias == "db"


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
    # Compose interpola `$var` en command/healthcheck: las variables del shell van como `$$` en el
    # YAML y Compose las entrega como `$`. Aquí se deshace igual que lo haría `docker compose config`.
    return m.group(1).replace("$$", "$").replace("exec sleep infinity", "")


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
    # Nada que Compose pueda interpolar como variable propia (un `$f` sin escapar quedaría vacío en silencio).
    for texto in (s["init"]["command"], hc):
        assert not re.findall(r"(?<!\$)\$(?!\$)(?:\{[^}]*\}|[A-Za-z_0-9#]+)", texto), "variables de shell sin escapar ($$) en init"
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
    # F1 (S-05): nunca `export VAR="$(cat f)"` (ocultaría el fallo de cat); lectura independiente y luego export.
    assert not re.search(r'export [A-Z_]+="\$\$?\(cat ', cmd), "export con sustitución de comandos: el fallo de cat quedaría oculto"
    for var, archivo in (("pg", "pg_password"), ("adm", "admin_password"), ("key", "api_key")):
        assert f"{var}=$$(cat /run/secrets/{archivo}) || exit 3" in cmd
    assert 'export AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD="$$adm"' in cmd and 'export AUDITBRAIN_API_KEY="$$key"' in cmd
    assert "for f in pg_password admin_password api_key jwt_secret" in cmd and '[ -s "/run/secrets/$$f" ]' in cmd
    assert "AUDITBRAIN_JWT_SECRET:-" in cmd and "exit 3" in cmd, "rechaza credenciales heredadas antes de sobrescribirlas"
    assert "set -x" not in cmd and "echo $$" not in cmd and 'echo "$$' not in cmd, "el guion no imprime valores"
    assert env["AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL"] == ADMIN_EMAIL_PREVIEW
    # La única variable obligatoria (:?) que queda es la etiqueta de la imagen.
    sin_comentarios = "\n".join(l for l in COMPOSE.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
    assert set(re.findall(r"\$\{([A-Z_]+):\?", sin_comentarios)) == {"SOURCE_COMMIT"}


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


@pytest.mark.skipif(shutil.which("sh") is None, reason="requiere un sh POSIX")
def test_t5_generador_local_idempotente_e_independiente(compose, tmp_path):
    """Aproximación local (sh del sistema, no busybox ash): la versión con alpine:3.20 corre en CI."""
    guion = _script_init(compose).replace("/secrets", "$SECRETS")
    script = tmp_path / "init.sh"
    script.write_text(guion, encoding="utf-8")

    def correr(vol: Path) -> str:
        # Puerta de identidad (2026-10-20): init exige la etiqueta sha-<40 hex> antes de generar nada.
        env = dict(os.environ, SECRETS=str(vol).replace("\\", "/"), PREVIEW_EXPECTED_IMAGE_TAG="sha-" + "0" * 40)
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
                # Única lectura permitida: las asignaciones independientes del command del backend en el Compose.
                assert f == COMPOSE and re.fullmatch(r"\s*(pg|adm|key)=\$\$\(cat /run/secrets/[a-z_]+\) \|\| exit 3", linea), f"{f.name}:{n} lee un secreto fuera de las asignaciones del backend"
            assert not re.search(r"echo\s+\"?\$s\b", linea), f"{f.name}:{n} imprime el valor generado"


# ---------------------------------------------------------------------------------------
# F1 v3 — el código del PR no controla privilegios del despliegue (A-09) y sin máximo fijo
# ---------------------------------------------------------------------------------------
_CLAVES_PRIVILEGIADAS = ("privileged", "cap_add", "network_mode", "pid", "ipc", "userns_mode", "security_opt",
                         "devices", "sysctls", "ports", "extra_hosts", "cgroup_parent", "runtime", "uts")


def test_compose_sin_privilegios_ni_acceso_al_host(compose):
    """Ningún servicio puede escalar privilegios ni tocar el host: sin privileged, socket de Docker,
    red/PID del host, puertos publicados ni montajes del sistema de archivos del host."""
    for nombre, svc in compose["services"].items():
        for clave in _CLAVES_PRIVILEGIADAS:
            assert clave not in svc, f"{nombre}: clave '{clave}' no permitida en un preview"
        for v in svc.get("volumes", []) or []:
            origen = v["source"] if isinstance(v, dict) else str(v).split(":")[0]
            assert not origen.startswith(("/", "./", "../", "~")), f"{nombre}: montaje del host no permitido ({origen})"
            assert origen in compose["volumes"], f"{nombre}: solo volúmenes nombrados declarados ({origen})"
            assert "docker.sock" not in str(v)
        assert "user" not in svc or svc["user"] != "root"
    texto = COMPOSE.read_text(encoding="utf-8")
    assert "/var/run/docker.sock" not in texto and "privileged" not in texto.replace("# ", "")


def test_compose_sin_maximo_fijo_de_previews(compose):
    """La concurrencia la decide la admisión dinámica (F2); el Compose no fija cupos ni réplicas."""
    texto = COMPOSE.read_text(encoding="utf-8")
    assert "MAX_ACTIVE_PREVIEWS" not in texto
    for nombre, svc in compose["services"].items():
        assert "deploy" not in svc or "replicas" not in svc["deploy"], f"{nombre}: sin réplicas fijas"
    # El presupuesto de memoria es POR preview; es el dato de entrada de la admisión dinámica.
    assert sum(_mib(v["mem_limit"]) for v in compose["services"].values()) == PRESUPUESTO_MIB


def test_compose_sin_secretos_en_environment(compose):
    """Ningún valor del bloque environment es una credencial: las de prueba llegan por volumen y las
    únicas referencias ${…} son la identidad (SERVICE_FQDN_*, SOURCE_COMMIT)."""
    sospechosas = ("KEY", "SECRET", "PASSWORD", "TOKEN")
    for nombre, svc in compose["services"].items():
        for k, v in _env(svc).items():
            if any(s in k for s in sospechosas) and not k.endswith(("_FILE", "_DIR")):  # rutas a archivos, no valores
                assert v == "", f"{nombre}: {k} lleva un valor en environment"
            assert "ghp_" not in v and "sk-" not in v


# --- Regresión del redespliegue fallido del 2026-10-20: analizador de Coolify y resolución de imágenes --------------
# Coolify 4.4.6 (`bootstrap/helpers/shared.php`, parseDockerComposeFile, ~líneas 4133-4228) recorre las entradas de
# `environment` de cada servicio: si el VALOR empieza por `$`, crea una variable de la aplicación con la clave de
# dentro de `${…}` y, como valor, el texto que sigue a `:-`, `-`, `:?` o `?`. Al desplegar, esa variable entra al
# FINAL del .env del preview (fallback de producción) y, como la última línea gana, `${SOURCE_COMMIT:?…}` se resolvió
# como «SOURCE_COMMIT requerido» => imágenes `…:sha-SOURCE_COMMIT requerido` => `invalid reference format`.
import os
import re
import shutil
import subprocess


def _simular_analizador_coolify(compose: dict) -> list:
    """Réplica de la regla de parseDockerComposeFile: devuelve (servicio, clave, valor) por cada variable que
    Coolify crearía a partir de `environment`. Las mágicas ${SERVICE_FQDN_*}/${SERVICE_URL_*} siguen otra rama."""
    creadas = []
    for nombre, svc in compose["services"].items():
        for _k, v in _env(svc).items():
            if not v.startswith("$"):
                continue
            interior = v[2:-1] if v.startswith("${") and v.endswith("}") else v[1:]
            if interior.startswith("SERVICE_"):
                continue
            for sep in (":-", "-", ":?", "?"):  # mismo orden que el código PHP
                if sep in interior:
                    clave, valor = interior.split(sep, 1)
                    break
            else:
                clave, valor = interior, None
            creadas.append((nombre, clave, valor))
    return creadas


def test_regresion_analizador_coolify_no_crea_variables_desde_environment(compose):
    """Ninguna entrada de environment empieza por `$` salvo las mágicas: Coolify no debe crear variable alguna."""
    assert _simular_analizador_coolify(compose) == []
    for nombre, svc in compose["services"].items():
        for k, v in _env(svc).items():
            assert not (k == "SOURCE_COMMIT" or v.startswith("${SOURCE_COMMIT")), f"{nombre}: {k}={v} recrearía el incidente"


def test_regresion_el_compose_f1_original_si_creaba_la_variable_obsoleta():
    """La simulación reproduce el incidente: el Compose de abc9d4b8 creaba SOURCE_COMMIT="SOURCE_COMMIT requerido"."""
    roto = {"services": {"backend": {"environment": [
        "SOURCE_COMMIT=${SOURCE_COMMIT:?SOURCE_COMMIT requerido}",
        "PREVIEW_EXPECTED_IMAGE_TAG=sha-${SOURCE_COMMIT:?SOURCE_COMMIT requerido}",
        "PREVIEW_PUBLIC_HOST=${SERVICE_FQDN_BACKEND_10000}",
    ]}}}
    assert _simular_analizador_coolify(roto) == [("backend", "SOURCE_COMMIT", "SOURCE_COMMIT requerido")]


def test_init_es_la_puerta_de_identidad_y_todos_dependen_de_init(compose):
    s = compose["services"]
    cmd = s["init"]["command"]
    assert 'grep -Eq "^sha-[0-9a-f]{40}$$"' in cmd
    assert '[ "sha-$$SOURCE_COMMIT" = "$$tag" ]' in cmd
    assert cmd.index("grep -Eq") < cmd.index("mkdir -p /secrets"), "la puerta va antes de generar nada"
    assert s["db"]["depends_on"]["init"]["condition"] == "service_healthy"
    assert s["backend"]["depends_on"]["db"]["condition"] == "service_healthy"
    for n in ("consola", "clientes"):
        assert s[n]["depends_on"]["init"]["condition"] == "service_healthy", f"{n} debe esperar la puerta de init"
    # Variables del shell escapadas como `$$` (Compose vaciaría en silencio un `$var` sin escapar).
    assert not re.findall(r"(?<![$])[$](?![$(])(?:[{][^}]*[}]|[A-Za-z_0-9#]+)", cmd)


_SH = shutil.which("sh")


def _guion_init(compose: dict, secretos_dir) -> str:
    """El guion real de init (`_script_init`) con /secrets redirigido a un directorio temporal."""
    return _script_init(compose).replace("/secrets", str(secretos_dir).replace("\\", "/"))


def _correr_init(compose, raiz, **env):
    e = {k: v for k, v in os.environ.items() if k not in ("PREVIEW_EXPECTED_IMAGE_TAG", "SOURCE_COMMIT")}
    e.update(env)
    return subprocess.run([_SH, "-c", _guion_init(compose, raiz / "secrets")], env=e, capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(_SH is None, reason="requiere sh POSIX")
@pytest.mark.parametrize("tag", ["", "sha-SOURCE_COMMIT requerido", "sha-" + "0" * 39, "latest", "sha-" + "g" * 40, "SHA-" + "0" * 40])
def test_init_rechaza_etiqueta_ausente_o_invalida_sin_generar_nada(compose, tmp_path, tag):
    r = _correr_init(compose, tmp_path, PREVIEW_EXPECTED_IMAGE_TAG=tag)
    assert r.returncode == 1 and "etiqueta de imagen invalida" in r.stderr, (r.returncode, r.stderr)
    assert not (tmp_path / "secrets").exists(), "no debe generar secretos con una etiqueta inválida"


@pytest.mark.skipif(_SH is None, reason="requiere sh POSIX")
def test_init_rechaza_source_commit_contradictorio(compose, tmp_path):
    r = _correr_init(compose, tmp_path, PREVIEW_EXPECTED_IMAGE_TAG="sha-" + "a" * 40, SOURCE_COMMIT="b" * 40)
    assert r.returncode == 1 and "contradice la etiqueta" in r.stderr, (r.returncode, r.stderr)
    assert not (tmp_path / "secrets").exists()


@pytest.mark.skipif(_SH is None, reason="requiere sh POSIX")
def test_init_acepta_etiqueta_valida_y_genera_los_secretos(compose, tmp_path):
    sha = "a" * 40
    r = _correr_init(compose, tmp_path, PREVIEW_EXPECTED_IMAGE_TAG=f"sha-{sha}", SOURCE_COMMIT=sha)
    assert r.returncode == 0 and r.stdout.strip() == "secrets listos", (r.returncode, r.stderr)
    for f, n in SECRETOS.items():
        assert len((tmp_path / "secrets" / f).read_text(encoding="utf-8")) == n
    # Sin SOURCE_COMMIT en el entorno (CI, fuera de Coolify) la puerta solo valida la etiqueta.
    r = _correr_init(compose, tmp_path / "b", PREVIEW_EXPECTED_IMAGE_TAG=f"sha-{sha}")
    assert r.returncode == 0, r.stderr


_SIN_DOCKER = shutil.which("docker") is None


def _compose_config(env_extra: dict, env_file=None):
    """Solo `docker compose config --images`: interpola, no crea ni levanta nada."""
    env = dict(os.environ, SERVICE_FQDN_BACKEND_10000="1.api.preview.audit-ia.ec",
               SERVICE_FQDN_CONSOLA_80="1.consola.preview.audit-ia.ec", SERVICE_FQDN_CLIENTES_80="1.clientes.preview.audit-ia.ec")
    env.pop("SOURCE_COMMIT", None)
    env.update(env_extra)
    cmd = ["docker", "compose", "-f", str(COMPOSE), *(["--env-file", str(env_file)] if env_file else []), "config", "--images"]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    if r.returncode != 0 and "Cannot connect" in (r.stderr or ""):
        pytest.skip("docker instalado pero sin demonio accesible")
    return r


@pytest.mark.skipif(_SIN_DOCKER, reason="requiere docker compose (solo `config`, no levanta nada)")
def test_resolucion_de_imagenes_por_source_commit_completo():
    sha = "7" * 40
    r = _compose_config({"SOURCE_COMMIT": sha})
    assert r.returncode == 0, r.stderr
    imgs = {l.strip() for l in r.stdout.splitlines() if l.startswith("ghcr.io/")}
    assert imgs == {f"ghcr.io/jcalupinia/auditbrain-preview-{s}:sha-{sha}" for s in ("backend", "consola", "clientes")}


@pytest.mark.skipif(_SIN_DOCKER, reason="requiere docker compose (solo `config`, no levanta nada)")
@pytest.mark.parametrize("valor", [None, ""])
def test_resolucion_rechaza_source_commit_ausente_o_vacio(valor):
    r = _compose_config({} if valor is None else {"SOURCE_COMMIT": valor})
    assert r.returncode != 0 and "SOURCE_COMMIT requerido" in (r.stderr + r.stdout)


@pytest.mark.skipif(_SIN_DOCKER, reason="requiere docker compose (solo `config`, no levanta nada)")
def test_resolucion_reproduce_el_incidente_con_la_variable_obsoleta_de_coolify(tmp_path):
    """Mecanismo del fallo del 2026-10-20: en el .env que arma Coolify la variable obsoleta entra al final y gana.
    Por eso, además del Compose corregido, hay que BORRAR en Coolify la variable SOURCE_COMMIT que creó el analizador."""
    sha = "7" * 40
    envf = tmp_path / "env"
    envf.write_text(f"SOURCE_COMMIT={sha}\nCOOLIFY_URL=x\nSOURCE_COMMIT=SOURCE_COMMIT requerido\n", encoding="utf-8")
    r = _compose_config({}, env_file=envf)
    assert "sha-SOURCE_COMMIT requerido" in r.stdout + r.stderr
    envf.write_text(f"SOURCE_COMMIT={sha}\n", encoding="utf-8")  # variable obsoleta borrada en Coolify
    r = _compose_config({}, env_file=envf)
    assert r.returncode == 0 and r.stdout.count(f"sha-{sha}") == 3 and "requerido" not in r.stdout
