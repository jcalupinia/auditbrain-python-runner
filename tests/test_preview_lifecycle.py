"""Controlador de previews (scripts/preview_lifecycle.py): política de capacidad, puertas de seguridad y ciclo de
vida, con Coolify, GitHub, GHCR y la lectura de capacidad simulados. Nada toca la red."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "preview_lifecycle.py"
spec = importlib.util.spec_from_file_location("preview_lifecycle", RUTA)
pl = importlib.util.module_from_spec(spec)
sys.modules["preview_lifecycle"] = pl  # los dataclasses con anotaciones diferidas resuelven tipos vía sys.modules
spec.loader.exec_module(pl)

SHA_A, SHA_B = "a" * 40, "b" * 40
REPO = "jcalupinia/auditbrain-python-runner"


def _ahora_iso(delta_s: int = 0) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=delta_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


def metricas(**kw) -> dict:
    base = {"observed_at": _ahora_iso(), "mem_available_mib": 3000, "swap_used_pct": 10.0, "psi_mem_some_avg60": 1.0,
            "load1": 0.5, "cpus": 2, "disk_free_gib": 20.0, "oom_recent": None}
    base.update(kw)
    return base


# ------------------------------------------------------------------ dobles de prueba
class CoolifyFalso:
    def __init__(self, previews=None, en_vuelo=None, estado_final="finished"):
        self._previews = list(previews or [])
        self._en_vuelo = list(en_vuelo or [])
        self.estado_final = estado_final
        self.llamadas = []
        self.app = "lrv8o1j8cyqbm3nry5qpziqj"
        self.deploy_429 = False

    def previews(self):
        return list(self._previews)

    def preview(self, pr):
        return next((p for p in self._previews if p["pull_request_id"] == pr), None)

    def despliegues_en_vuelo(self):
        return list(self._en_vuelo)

    def asegurar_preview(self, pr, html_url):
        self.llamadas.append(("crear", pr))
        if not self.preview(pr):
            self._previews.append({"pull_request_id": pr, "status": "exited", "uuid": f"pv{pr}"})

    def desplegar(self, pr):
        self.llamadas.append(("deploy", pr))
        if self.deploy_429:
            return "429"
        self._en_vuelo.append({"pull_request_id": pr, "status": "in_progress", "deployment_uuid": f"dep{pr}"})
        return f"dep{pr}"

    def despliegue(self, uuid):
        # el primer sondeo lo ve en curso; el segundo, terminado (y sale de la lista en vuelo)
        self._en_vuelo = [d for d in self._en_vuelo if d.get("deployment_uuid") != uuid]
        return {"status": self.estado_final}

    def borrar(self, pr):
        self.llamadas.append(("borrar", pr))
        self._previews = [p for p in self._previews if p["pull_request_id"] != pr]


class GitHubFalso:
    def __init__(self, prs: dict, blobs: dict | None = None, checks: dict | None = None):
        self.prs, self.blobs, self.checks = prs, blobs or {}, checks or {}
        self.comentarios, self.etiquetas = {}, {}

    def pr(self, n):
        return self.prs[n]

    def abiertos(self):
        return [p for p in self.prs.values() if p["state"] == "open"]

    def check_runs(self, sha):
        return self.checks.get(sha, [{"name": "pytest (python 3.12) · grupo 1/4", "status": "completed", "conclusion": "success"}])

    def blob_sha(self, path, ref):
        return self.blobs.get((path, ref), "mismo")

    def ultima_actividad_humana(self, pr):
        return dt.datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))

    def etiquetar(self, n, poner=None, quitar=()):
        s = self.etiquetas.setdefault(n, set())
        s.difference_update(quitar)
        if poner:
            s.add(poner)
        self.prs[n]["labels"] = [{"name": e} for e in s]

    def comentar(self, n, texto):
        self.comentarios[n] = texto


def pr_de(n, sha=SHA_A, autor="jcalupinia", estado="open", fork=False, draft=False, labels=(), merged=False, creado="2026-10-20T10:00:00Z"):
    return {"number": n, "state": estado, "draft": draft, "merged": merged, "created_at": creado, "html_url": f"https://github.com/{REPO}/pull/{n}",
            "head": {"sha": sha, "repo": {"full_name": "otro/fork" if fork else REPO}}, "base": {"ref": "main"},
            "user": {"login": autor}, "labels": [{"name": l} for l in labels]}


def fetch_ok(prs_desplegados: dict):
    """Simula producción sana, la lectura de capacidad y la verificación del preview (health y build-info)."""
    def fetch(method, url, token=None, body=None, headers=None, timeout=30):
        if url.endswith("/api/v1/host-capacity"):
            return (200, fetch.capacidad, {}) [:2] if fetch.capacidad is not None else (503, None)
        if "api.audit-ia.ec/api/v1/health" in url:
            return (200, {"status": "ok"}) if fetch.prod_sana else (503, None)
        for n, sha in prs_desplegados.items():
            if url == f"https://{n}.api.preview.audit-ia.ec/api/v1/health":
                return 200, {"build": {"commit": sha}, "preview": {"pr": str(n)}}
            if url in (f"https://{n}.consola.preview.audit-ia.ec/build-info.json", f"https://{n}.clientes.preview.audit-ia.ec/build-info.json"):
                return 200, {"commit": sha}
        return 404, None
    fetch.capacidad = metricas()
    fetch.prod_sana = True
    return fetch


def contexto(co, gh, fetch, imagenes=None, autores="", dry=False, **kw):
    import os
    os.environ["GITHUB_REPOSITORY"] = REPO
    os.environ["PREVIEW_AUTHORS_ALLOWED"] = autores
    return pl.Contexto(co=co, gh=gh, repo=REPO, politica=pl.Politica(), fuentes_capacidad=["https://api.audit-ia.ec"], token_capacidad="t" * 32,
                       fetch=fetch, imagenes_fn=imagenes or (lambda sha, tok: list(pl.SERVICIOS)), sleep=lambda s: None, dry=dry, **kw)


# ------------------------------------------------------------------ CapacityDecision
def test_sin_telemetria_es_defer():
    d = pl.decidir_capacidad(None, [], [], True, pl.Politica(), 1, SHA_A)
    assert (d.decision, d.reason_code) == ("DEFER", "TELEMETRY_UNAVAILABLE") and d.retry_after


@pytest.mark.parametrize("cambios, codigo", [
    ({"observed_at": "ANTIGUA"}, "TELEMETRY_UNAVAILABLE"),
    ({"observed_at": None}, "TELEMETRY_UNAVAILABLE"),
    ({"mem_available_mib": 1500}, "RAM_HEADROOM"),              # 1500 − 1296 − 576 < 512
    ({"psi_mem_some_avg60": 35.0}, "CPU_PRESSURE"),
    ({"load1": 9.0, "cpus": 2}, "CPU_PRESSURE"),
    ({"swap_used_pct": 90.0}, "SWAP_PRESSURE"),
    ({"disk_free_gib": 1.0}, "DISK"),
    ({"disk_free_gib": None}, "DISK"),
    ({"oom_recent": 2}, "OOM_RECENT"),
])
def test_umbrales_producen_defer(cambios, codigo):
    # Las métricas se construyen DENTRO del test: la frescura (180 s) se mide respecto al momento de la decisión y en
    # CI la recolección puede ocurrir minutos antes de la ejecución.
    if cambios.get("observed_at") == "ANTIGUA":
        cambios = {"observed_at": _ahora_iso(-600)}
    m = metricas(**cambios)
    d = pl.decidir_capacidad(m, [], [], True, pl.Politica(), 1, SHA_A)
    assert d.decision == "DEFER" and d.reason_code == codigo, d


def test_produccion_enferma_o_desconocida_es_defer():
    for sana in (False, None):
        d = pl.decidir_capacidad(metricas(), [], [], sana, pl.Politica(), 1, SHA_A)
        assert (d.decision, d.reason_code) == ("DEFER", "PRODUCTION_UNHEALTHY")


def test_memoria_cuenta_previews_existentes_y_reservas_en_vuelo():
    pol = pl.Politica()
    # 3000 MiB libres: con un preview de otro PR (headroom 1296) el margen = 3000 − 1296 − 1296 − 576 < 512
    d = pl.decidir_capacidad(metricas(), [{"pull_request_id": 7, "status": "running"}], [], True, pol, 1, SHA_A)
    assert d.reason_code == "RAM_HEADROOM" and d.metrics["headroom_existentes_mib"] == 1296
    # el propio preview del PR no cuenta como «otro» (actualizarlo no añade una pila permanente)
    d = pl.decidir_capacidad(metricas(), [{"pull_request_id": 1, "status": "running"}], [], True, pol, 1, SHA_A)
    assert d.decision == "ADMIT" and d.metrics["headroom_existentes_mib"] == 0
    # un despliegue en vuelo de otro PR bloquea aunque sobre memoria (candado de reservas)
    d = pl.decidir_capacidad(metricas(mem_available_mib=3600), [], [{"pull_request_id": 9, "status": "queued"}], True, pol, 1, SHA_A)
    assert d.reason_code == "IN_FLIGHT_RESERVATION" and d.metrics["reservas_en_vuelo_mib"] == 1296 + 576
    # con factor de headroom medido (0.5) y 3600 libres, dos previews pueden coexistir
    d = pl.decidir_capacidad(metricas(mem_available_mib=3600), [{"pull_request_id": 7, "status": "running"}], [], True,
                             pl.Politica(factor_headroom=0.5), 1, SHA_A)
    assert d.decision == "ADMIT", d.metrics


def test_admit_lleva_metricas_redactadas_y_sin_secretos():
    d = pl.decidir_capacidad(metricas(), [], [], True, pl.Politica(), 42, SHA_A)
    j = json.dumps(d.to_dict())
    assert d.decision == "ADMIT" and '"pr": 42' in j and "token" not in j.lower()
    assert set(d.metrics) >= {"mem_available_mib", "headroom_existentes_mib", "reservas_en_vuelo_mib", "limite_nuevo_mib", "reserva_seguridad_mib", "previews_activos", "disco_libre_gib"}


def test_politica_desde_entorno(monkeypatch):
    monkeypatch.setenv("PREVIEW_FACTOR_HEADROOM", "0.5")
    monkeypatch.setenv("PREVIEW_RESERVA_SEGURIDAD_MIB", "700")
    p = pl.Politica.desde_entorno()
    assert p.factor_headroom == 0.5 and p.reserva_seguridad_mib == 700 and p.limite_nuevo_mib == 1296


# ------------------------------------------------------------------ puertas de seguridad
def test_puerta_pr_rechaza_forks_cerrados_borradores_y_autores_no_autorizados():
    aut = {"jcalupinia"}
    assert pl.puerta_pr(pr_de(1), REPO, aut) is None
    assert "fork" in pl.puerta_pr(pr_de(1, fork=True), REPO, aut)
    assert "abierto" in pl.puerta_pr(pr_de(1, estado="closed"), REPO, aut)
    assert "no autorizado" in pl.puerta_pr(pr_de(1, autor="desconocido"), REPO, aut)
    assert "borrador" in pl.puerta_pr(pr_de(1, draft=True), REPO, aut)
    p = pr_de(1); p["base"]["ref"] = "develop"
    assert "main" in pl.puerta_pr(p, REPO, aut)


def test_autores_autorizados_incluye_al_propietario_y_la_lista(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    monkeypatch.setenv("PREVIEW_AUTHORS_ALLOWED", "Julio-Dev, alexis,  ")
    assert pl.autores_autorizados() == {"jcalupinia", "julio-dev", "alexis"}


def test_plantilla_confiable_compose_y_dockerfiles():
    gh = GitHubFalso({}, blobs={("docker-compose.preview.yml", SHA_A): "x", ("docker-compose.preview.yml", "main"): "x"})
    assert pl.plantilla_confiable(gh, SHA_A, "main", set()) is None
    gh.blobs[("docker-compose.preview.yml", SHA_A)] = "distinto"
    assert "docker-compose.preview.yml difiere" in pl.plantilla_confiable(gh, SHA_A, "main", set())
    gh.blobs[("docker-compose.preview.yml", SHA_A)] = "x"
    gh.blobs[("Dockerfile.render", SHA_A)] = "d1"; gh.blobs[("Dockerfile.render", "main")] = "d2"
    assert "Dockerfile.render difiere" in pl.plantilla_confiable(gh, SHA_A, "main", set())
    assert pl.plantilla_confiable(gh, SHA_A, "main", {pl.ETIQUETA_DOCKERFILES_OK}) is None
    gh.blobs[("docker-compose.preview.yml", "main")] = None
    assert "no se pudo leer" in pl.plantilla_confiable(gh, SHA_A, "main", set())


def test_checks_obligatorios():
    pend = [{"name": "pytest (python 3.12) · grupo 1/4", "status": "in_progress", "conclusion": None}]
    ok = [{"name": "pytest (python 3.12) · grupo 1/4", "status": "completed", "conclusion": "success"}]
    mal = ok + [{"name": "pytest (python 3.12) · grupo 2/4", "status": "completed", "conclusion": "failure"}]
    pref = ("pytest (python 3.12)",)
    assert pl.checks_obligatorios([], pref)[0] == "pendiente"
    assert pl.checks_obligatorios(pend, pref)[0] == "pendiente"
    assert pl.checks_obligatorios(ok, pref)[0] == "ok"
    assert pl.checks_obligatorios(mal, pref)[0] == "fallido"


def test_coolify_solo_https_y_lista_blanca_de_endpoints():
    with pytest.raises(SystemExit, match="https"):
        pl.Coolify("http://5.161.193.182:8000", "t", "lrv8o1j8cyqbm3nry5qpziqj", True)
    co = pl.Coolify("https://coolify.audit-ia.ec", "t", "lrv8o1j8cyqbm3nry5qpziqj", True)
    app = co.app
    for ok in (f"/applications/{app}/previews", f"/applications/{app}/previews/384", f"/deploy?uuid={app}&pr=384",
               f"/deployments/applications/{app}?take=50", "/deployments/abc123XYZ"):
        assert co._permitido(ok), ok
    for mal in ("/applications/otraapp/previews", f"/applications/{app}", f"/applications/{app}/envs", "/servers/x", "/deploy?uuid=otra&pr=1",
                f"/applications/{app}/previews/384/logs", "/teams", f"/applications/{app}/restart"):
        assert not co._permitido(mal), mal
    with pytest.raises(SystemExit, match="lista blanca"):
        co._call("GET", "/servers/x")


# ------------------------------------------------------------------ sincronizar (flujo completo simulado)
def test_sincronizar_despliega_verifica_y_publica_enlaces():
    gh = GitHubFalso({5: pr_de(5)})
    co = CoolifyFalso()
    ctx = contexto(co, gh, fetch_ok({5: SHA_A}))
    assert pl.sincronizar(ctx, 5, SHA_A) == 0
    assert co.llamadas == [("crear", 5), ("deploy", 5)]
    assert gh.etiquetas[5] == {pl.ETIQUETA_ACTIVO}
    c = gh.comentarios[5]
    assert "https://5.consola.preview.audit-ia.ec" in c and "https://5.clientes.preview.audit-ia.ec" in c and SHA_A in c
    assert '"decision": "ADMIT"' in c and "t" * 32 not in c


def test_sincronizar_actualiza_preview_existente_sin_recrearlo():
    gh = GitHubFalso({5: pr_de(5, sha=SHA_B)})
    co = CoolifyFalso(previews=[{"pull_request_id": 5, "status": "running"}])
    ctx = contexto(co, gh, fetch_ok({5: SHA_B}))
    assert pl.sincronizar(ctx, 5) == 0
    assert co.llamadas == [("deploy", 5)]  # sin «crear»: el preview ya existía


def test_sincronizar_ignora_un_head_superado():
    gh = GitHubFalso({5: pr_de(5, sha=SHA_B)})
    co = CoolifyFalso()
    assert pl.sincronizar(contexto(co, gh, fetch_ok({})), 5, SHA_A) == 0
    assert co.llamadas == [] and 5 not in gh.comentarios


def test_sincronizar_rechaza_fork_autor_no_autorizado_y_plantilla_distinta():
    gh = GitHubFalso({1: pr_de(1, fork=True), 2: pr_de(2, autor="intruso"), 3: pr_de(3)},
                     blobs={("docker-compose.preview.yml", SHA_A): "cambiado"})
    co = CoolifyFalso()
    ctx = contexto(co, gh, fetch_ok({}))
    for n in (1, 2, 3):
        pl.sincronizar(ctx, n)
        assert gh.etiquetas[n] == {pl.ETIQUETA_RECHAZO}, n
        assert '"reason_code": "SECURITY"' in gh.comentarios[n]
    assert co.llamadas == []


def test_sincronizar_espera_por_imagenes_checks_y_capacidad():
    gh = GitHubFalso({5: pr_de(5)}, checks={SHA_A: [{"name": "pytest (python 3.12) · grupo 1/4", "status": "queued", "conclusion": None}]})
    co = CoolifyFalso()
    f = fetch_ok({})
    ctx = contexto(co, gh, f)
    pl.sincronizar(ctx, 5)
    assert gh.etiquetas[5] == {pl.ETIQUETA_ESPERA} and "CHECKS_PENDING" in gh.comentarios[5]
    gh.checks = {}
    ctx.imagenes_fn = lambda sha, tok: ["backend"]
    pl.sincronizar(ctx, 5)
    assert "IMAGES_MISSING" in gh.comentarios[5] and "consola, clientes" in gh.comentarios[5]
    ctx.imagenes_fn = lambda sha, tok: list(pl.SERVICIOS)
    f.capacidad = None
    pl.sincronizar(ctx, 5)
    assert "TELEMETRY_UNAVAILABLE" in gh.comentarios[5]
    f.capacidad = metricas(mem_available_mib=1000)
    pl.sincronizar(ctx, 5)
    assert "RAM_HEADROOM" in gh.comentarios[5] and "No se detiene ningún otro preview" in gh.comentarios[5]
    assert co.llamadas == []


def test_sincronizar_checks_fallidos_rechaza_sin_desplegar():
    gh = GitHubFalso({5: pr_de(5)}, checks={SHA_A: [{"name": "pytest (python 3.12) · grupo 1/4", "status": "completed", "conclusion": "failure"}]})
    co = CoolifyFalso()
    pl.sincronizar(contexto(co, gh, fetch_ok({})), 5)
    assert gh.etiquetas[5] == {pl.ETIQUETA_RECHAZO} and co.llamadas == []


def test_solicitudes_simultaneas_la_segunda_espera_por_la_reserva_en_vuelo():
    """Dos PR admitidos casi a la vez: el primero deja un despliegue en vuelo; el segundo, aunque haya memoria,
    recibe DEFER/IN_FLIGHT_RESERVATION hasta que termine (además del candado del workflow)."""
    gh = GitHubFalso({5: pr_de(5), 6: pr_de(6, sha=SHA_B)})
    co = CoolifyFalso()
    co.despliegue = lambda uuid: {"status": "in_progress"}  # nunca termina durante la prueba
    f = fetch_ok({5: SHA_A, 6: SHA_B})
    f.capacidad = metricas(mem_available_mib=3600)
    ctx = contexto(co, gh, f, espera_max_s=0)
    pl.sincronizar(ctx, 5)
    assert ("deploy", 5) in co.llamadas
    pl.sincronizar(ctx, 6)
    assert ("deploy", 6) not in co.llamadas
    assert gh.etiquetas[6] == {pl.ETIQUETA_ESPERA} and "IN_FLIGHT_RESERVATION" in gh.comentarios[6]


def test_coolify_429_es_defer_corto():
    gh = GitHubFalso({5: pr_de(5)})
    co = CoolifyFalso(); co.deploy_429 = True
    pl.sincronizar(contexto(co, gh, fetch_ok({5: SHA_A})), 5)
    assert gh.etiquetas[5] == {pl.ETIQUETA_ESPERA} and '"retry_after": 60' in gh.comentarios[5]


def test_despliegue_fallido_o_verificacion_fallida_no_marca_activo():
    gh = GitHubFalso({5: pr_de(5)})
    co = CoolifyFalso(estado_final="failed")
    pl.sincronizar(contexto(co, gh, fetch_ok({5: SHA_A})), 5)
    assert gh.etiquetas[5] == {pl.ETIQUETA_ESPERA} and "failed" in gh.comentarios[5]
    gh2 = GitHubFalso({5: pr_de(5)})
    co2 = CoolifyFalso()
    pl.sincronizar(contexto(co2, gh2, fetch_ok({5: SHA_B})), 5)  # el preview sirve OTRO commit
    assert gh2.etiquetas[5] == {pl.ETIQUETA_ESPERA} and "verificación falló" in gh2.comentarios[5]


def test_dry_run_no_escribe_en_coolify():
    gh = GitHubFalso({5: pr_de(5)})
    co = CoolifyFalso()
    ctx = contexto(co, gh, fetch_ok({5: SHA_A}), dry=True)
    # en dry-run el doble sigue registrando llamadas; el Coolify real las convierte en log. Aquí se comprueba el flujo.
    pl.sincronizar(ctx, 5)
    assert "dry-run" in gh.comentarios[5]


def test_verificar_preview_detecta_commit_distinto_y_pr_distinto():
    f = fetch_ok({5: SHA_A})
    assert pl.verificar_preview(5, SHA_A, "preview.audit-ia.ec", f) == []
    assert any("build.commit" in p for p in pl.verificar_preview(5, SHA_B, "preview.audit-ia.ec", f))
    assert pl.verificar_preview(6, SHA_A, "preview.audit-ia.ec", f)  # nada responde para el PR 6


# ------------------------------------------------------------------ reintentar, cerrar, caducidad
def test_reintentar_atiende_el_mas_antiguo_y_un_despliegue_por_ciclo():
    gh = GitHubFalso({8: pr_de(8, labels=(pl.ETIQUETA_ESPERA,), creado="2026-10-19T10:00:00Z"),
                      7: pr_de(7, sha=SHA_B, labels=(pl.ETIQUETA_ESPERA,), creado="2026-10-18T10:00:00Z")})
    co = CoolifyFalso()
    f = fetch_ok({7: SHA_B, 8: SHA_A}); f.capacidad = metricas(mem_available_mib=3600)
    pl.reintentar(contexto(co, gh, f))
    assert [c for c in co.llamadas if c[0] == "deploy"] == [("deploy", 7)]
    assert gh.etiquetas[7] == {pl.ETIQUETA_ACTIVO}
    assert pl.ETIQUETA_ESPERA in {l["name"] for l in gh.prs[8]["labels"]} and 8 not in gh.comentarios  # intacto: un despliegue por ciclo


def test_cerrar_verifica_identidad_antes_de_borrar():
    gh = GitHubFalso({5: pr_de(5, estado="closed", merged=True), 6: pr_de(6), 7: pr_de(7, estado="closed", fork=True), 9: pr_de(9, estado="closed")})
    co = CoolifyFalso(previews=[{"pull_request_id": 5, "status": "running"}, {"pull_request_id": 7, "status": "running"}])
    ctx = contexto(co, gh, fetch_ok({}))
    pl.cerrar(ctx, 6)   # abierto: nada
    pl.cerrar(ctx, 7)   # fork: nada
    pl.cerrar(ctx, 9)   # sin preview: nada
    assert co.llamadas == []
    pl.cerrar(ctx, 5)
    assert co.llamadas == [("borrar", 5)] and co.preview(7) is not None
    assert "fusionado" in gh.comentarios[5] and "únicamente el preview `5`" in gh.comentarios[5]


def test_caducidad_respeta_keep_y_elimina_inactivos():
    viejo = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    gh = GitHubFalso({1: pr_de(1, creado=viejo), 2: pr_de(2, creado=viejo, labels=(pl.ETIQUETA_KEEP,)), 3: pr_de(3)})
    co = CoolifyFalso(previews=[{"pull_request_id": n, "status": "running"} for n in (1, 2, 3)] + [{"pull_request_id": 99, "status": "running"}])
    pl.caducidad(contexto(co, gh, fetch_ok({})), 3)
    assert co.llamadas == [("borrar", 1)]
    assert pl.ETIQUETA_ESPERA in gh.etiquetas[1]


def test_cli_exige_variables_y_no_ejecuta_nada_sin_ellas(monkeypatch):
    for k in ("COOLIFY_URL", "COOLIFY_API_TOKEN", "COOLIFY_PREVIEW_APP_UUID", "GITHUB_TOKEN", "GITHUB_REPOSITORY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(SystemExit, match="Faltan variables"):
        pl.main(["reintentar", "--dry-run"])


def test_dry_run_bloquea_toda_escritura_en_coolify_y_github():
    """Garantía del punto 1 del cierre: con --dry-run ninguna escritura llega a Coolify ni a GitHub, ni siquiera
    si una rama de código llama a los métodos de escritura directamente."""
    co = pl.Coolify("https://coolify.audit-ia.ec", "t", "lrv8o1j8cyqbm3nry5qpziqj", dry=True)
    with pytest.raises(SystemExit, match="dry-run"):
        co._call("POST", f"/applications/{co.app}/previews", {"pull_request_id": 1})
    with pytest.raises(SystemExit, match="dry-run"):
        co._call("DELETE", f"/applications/{co.app}/previews/1")
    gh = pl.GitHub(REPO, "g", dry=True)
    with pytest.raises(SystemExit, match="dry-run"):
        gh._escribir("POST", "https://api.github.com/repos/x/y/issues/1/comments", {"body": "x"})
    # Las operaciones de alto nivel en dry-run solo registran (no llegan a _escribir/_call)
    gh.etiquetar(1, "preview:activo"); gh.comentar(1, "hola"); co.asegurar_preview(1, ""); co.borrar(1)
    assert co.desplegar(1) is None


def test_accion_capacidad_es_solo_lectura_y_diagnostica_la_telemetria(capsys):
    gh = GitHubFalso({})
    co = CoolifyFalso()
    f = fetch_ok({})
    ctx = contexto(co, gh, f, dry=True)
    assert pl.capacidad(ctx) == 0
    salida = capsys.readouterr().out
    assert '"decision": "ADMIT"' in salida and "telemetría OK" in salida and co.llamadas == []
    f.capacidad = None
    assert pl.capacidad(ctx) == 3
    assert "TELEMETRY_UNAVAILABLE" in capsys.readouterr().out


def test_cli_rechaza_coolify_http(monkeypatch):
    monkeypatch.setenv("COOLIFY_URL", "http://5.161.193.182:8000")
    for k, v in (("COOLIFY_API_TOKEN", "t"), ("COOLIFY_PREVIEW_APP_UUID", "lrv8o1j8cyqbm3nry5qpziqj"), ("GITHUB_TOKEN", "g"), ("GITHUB_REPOSITORY", REPO)):
        monkeypatch.setenv(k, v)
    with pytest.raises(SystemExit, match="https"):
        pl.main(["reintentar", "--dry-run"])
