#!/usr/bin/env python3
"""Controlador de los Preview Environments de AuditBrain en Coolify 4.4.6 (F2/F3: admisión por capacidad real).

Lo ejecutan los workflows `preview-deploy.yml` (admisión, actualización, reintentos, caducidad) y
`preview-cleanup.yml` (cierre) desde el código de la rama protegida; nunca desde código del PR.

Acciones
  sincronizar --pr N [--sha SHA]  Crea o actualiza el preview del PR N con las imágenes `sha-<head>` de su
                                  propio commit. Solo si: PR abierto del propio repositorio (sin forks), autor
                                  autorizado, checks obligatorios en verde, plantilla confiable, tres imágenes
                                  publicadas y privadas, y una CapacityDecision = ADMIT. Si no: DEFER (etiqueta
                                  `preview:en-espera`, reintento automático) o REJECT (`preview:rechazado`).
  reintentar                      Vuelve a evaluar, del más antiguo al más nuevo, los PR en espera.
  cerrar --pr N                   Elimina el preview del PR N tras verificar su identidad (PR cerrado o fusionado
                                  en GitHub, preview de ESE número en la aplicación de previews). Nunca otra app.
  caducidad                       Elimina previews de PR abiertos con >= DIAS_INACTIVIDAD días sin actividad
                                  humana (salvo etiqueta `preview:keep`).

Política de capacidad (docs/previews-coolify.md §11, CapacityDecision): la memoria disponible real (sin swap)
debe cubrir el crecimiento posible de los previews existentes, las reservas de despliegues en vuelo, el límite
del preview nuevo y una reserva de seguridad; además PSI de memoria, swap usada, carga, disco, OOM y salud de
producción dentro de umbral y métricas frescas. Sin telemetría fiable => DEFER (fallo cerrado). Nunca detiene ni
elimina otro preview para hacer sitio. El candado de admisión es el grupo de concurrencia del workflow.

Seguridad: COOLIFY_URL debe ser https:// (el token no viaja por HTTP plano); el controlador solo llama a los
endpoints de previews/despliegues de la aplicación COOLIFY_PREVIEW_APP_UUID (lista blanca en `Coolify._permitido`);
no imprime tokens; --dry-run no modifica nada.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BOTS = {"coolify", "github-actions[bot]", "render[bot]", "claude[bot]", "dependabot[bot]", "auditbrain-preview-github[bot]"}
SERVICIOS = ("backend", "consola", "clientes")
GHCR_OWNER = "jcalupinia"
PAQUETE = "auditbrain-preview-"
MARCA_COMENTARIO = "<!-- auditbrain-preview-controlador -->"
ETIQUETA_ESPERA, ETIQUETA_RECHAZO, ETIQUETA_ACTIVO, ETIQUETA_KEEP = "preview:en-espera", "preview:rechazado", "preview:activo", "preview:keep"
ETIQUETA_DOCKERFILES_OK = "preview:dockerfiles-aprobados"
ARCHIVOS_PLANTILLA = ("docker-compose.preview.yml",)
ARCHIVOS_DOCKERFILES = ("Dockerfile.render", "frontend/Dockerfile.preview", "frontend-client/Dockerfile.preview")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
ESTADOS_EN_VUELO = ("queued", "in_progress")
# Estados de Coolify de un preview que está DETENIDO: sus contenedores no corren,
# así que NO reserva RAM del host. «Stop» en Coolify deja el preview en «exited».
ESTADOS_DETENIDOS = ("exited", "stopped")


def _preview_consume_recursos(status) -> bool:
    """¿Un preview con este estado reserva recursos del host (cuenta para el headroom)?

    - Detenido (``exited``/``stopped``): NO reserva — sus contenedores no corren.
    - ``running``/``starting``/``degraded``/``restarting``: SÍ reserva.
    - Estado en transición, desconocido o ausente: SÍ reserva, de forma CONSERVADORA,
      para no admitir despliegues de manera insegura ante una respuesta incompleta
      de Coolify. Solo un estado reconocido como detenido libera la reserva.
    """
    s = str(status if status is not None else "").strip().lower()
    if not s:
        return True
    return not s.startswith(ESTADOS_DETENIDOS)


def log(msg: str) -> None:
    print(dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%SZ"), msg, flush=True)


def ahora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _req(method: str, url: str, token: str | None, body: dict | None = None, headers: dict | None = None,
         timeout: int = 30) -> tuple[int, dict | list | None]:
    data = json.dumps(body).encode() if body is not None else None
    h = {"Accept": "application/vnd.github+json" if "api.github.com" in url else "application/json",
         "Content-Type": "application/json", "User-Agent": "auditbrain-preview-controlador"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode() or "null"
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, {"raw": raw[:300]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")[:300]
        return e.code, {"error": raw}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"error": str(e)[:200]}


# ------------------------------------------------------------------ Coolify (solo la aplicación de previews)
class Coolify:
    def __init__(self, base: str, token: str, app_uuid: str, dry: bool):
        if not base.lower().startswith("https://"):
            raise SystemExit("ABORTADO: COOLIFY_URL debe ser https:// (el token no se envía por HTTP plano).")
        if not re.fullmatch(r"[A-Za-z0-9]{10,40}", app_uuid or ""):
            raise SystemExit("ABORTADO: COOLIFY_PREVIEW_APP_UUID inválido.")
        self.base, self.token, self.app, self.dry = base.rstrip("/"), token, app_uuid, dry

    def _permitido(self, path: str) -> bool:
        """Lista blanca: solo previews/despliegues de ESTA aplicación. Ninguna otra aplicación ni servidor."""
        return bool(re.fullmatch(rf"/applications/{self.app}/previews(/\d+)?", path)
                    or re.fullmatch(rf"/deploy\?uuid={self.app}&pr=\d+(&force=(true|false))?", path)
                    or re.fullmatch(rf"/deployments/applications/{self.app}(\?.*)?", path)
                    or re.fullmatch(r"/deployments/[A-Za-z0-9]+", path))

    def _call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
        if not self._permitido(path):
            raise SystemExit(f"ABORTADO: llamada a Coolify fuera de la lista blanca: {method} {path}")
        if self.dry and method != "GET":
            # Garantía de --dry-run: ninguna escritura llega a Coolify aunque una rama de código lo intente.
            raise SystemExit(f"ABORTADO (dry-run): escritura bloqueada {method} {path}")
        return _req(method, f"{self.base}/api/v1{path}", self.token, body)

    def previews(self) -> list[dict]:
        st, data = self._call("GET", f"/applications/{self.app}/previews")
        if st != 200:
            raise SystemExit(f"Coolify GET previews -> {st}")
        return data or []

    def preview(self, pr: int) -> dict | None:
        st, data = self._call("GET", f"/applications/{self.app}/previews/{pr}")
        return data if st == 200 and isinstance(data, dict) else None

    def despliegues_en_vuelo(self) -> list[dict]:
        st, data = self._call("GET", f"/deployments/applications/{self.app}?take=50")
        if st != 200:
            raise SystemExit(f"Coolify GET deployments -> {st}")
        items = data.get("deployments", data) if isinstance(data, dict) else data
        return [d for d in (items or []) if str(d.get("status", "")).lower() in ESTADOS_EN_VUELO]

    def asegurar_preview(self, pr: int, html_url: str) -> None:
        if self.dry:
            return log(f"[dry-run] POST previews pr={pr} instant_deploy=false")
        st, d = self._call("POST", f"/applications/{self.app}/previews",
                           {"pull_request_id": pr, "instant_deploy": False, "pull_request_html_url": html_url})
        if st not in (200, 201):
            raise SystemExit(f"Coolify crear/actualizar preview -> {st} {d}")

    def desplegar(self, pr: int) -> str | None:
        """Lanza el despliegue del preview del PR (Coolify resuelve el head del PR y lo escribe en SOURCE_COMMIT)."""
        if self.dry:
            log(f"[dry-run] POST deploy uuid={self.app} pr={pr}")
            return None
        st, d = self._call("POST", f"/deploy?uuid={self.app}&pr={pr}")
        if st == 429:
            return "429"
        if st != 200:
            raise SystemExit(f"Coolify deploy -> {st} {d}")
        try:
            return (d.get("deployments") or [{}])[0].get("deployment_uuid")
        except (AttributeError, IndexError):
            return None

    def despliegue(self, deployment_uuid: str) -> dict | None:
        st, d = self._call("GET", f"/deployments/{deployment_uuid}")
        return d if st == 200 and isinstance(d, dict) else None

    def borrar(self, pr: int) -> None:
        if self.dry:
            return log(f"[dry-run] DELETE previews/{pr}")
        st, d = self._call("DELETE", f"/applications/{self.app}/previews/{pr}")
        if st not in (200, 204):
            raise SystemExit(f"Coolify borrar preview -> {st} {d}")


# ------------------------------------------------------------------ GitHub
class GitHub:
    def __init__(self, repo: str, token: str, dry: bool):
        self.repo, self.token, self.dry = repo, token, dry

    def _u(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.repo}{path}"

    def pr(self, n: int) -> dict:
        st, d = _req("GET", self._u(f"/pulls/{n}"), self.token)
        if st != 200:
            raise SystemExit(f"GitHub PR {n} -> {st}")
        return d

    def abiertos(self) -> list[dict]:
        st, d = _req("GET", self._u("/pulls?state=open&per_page=100"), self.token)
        return d if st == 200 else []

    def check_runs(self, sha: str) -> list[dict]:
        st, d = _req("GET", self._u(f"/commits/{sha}/check-runs?per_page=100"), self.token)
        return (d or {}).get("check_runs", []) if st == 200 else []

    def blob_sha(self, path: str, ref: str) -> str | None:
        st, d = _req("GET", self._u(f"/contents/{urllib.parse.quote(path)}?ref={urllib.parse.quote(ref)}"), self.token)
        return d.get("sha") if st == 200 and isinstance(d, dict) else None

    def ultima_actividad_humana(self, pr: dict) -> dt.datetime:
        fechas = []
        st, c = _req("GET", self._u(f"/commits/{pr['head']['sha']}"), self.token)
        if st == 200:
            fechas.append(c["commit"]["committer"]["date"])
        for path in (f"/issues/{pr['number']}/comments?per_page=100", f"/pulls/{pr['number']}/reviews?per_page=100"):
            st, items = _req("GET", self._u(path), self.token)
            for it in (items or []) if st == 200 else []:
                if (it.get("user") or {}).get("login", "").lower() not in BOTS:
                    fechas.append(it.get("submitted_at") or it.get("created_at"))
        fechas = [f for f in fechas if f]
        return max(dt.datetime.fromisoformat(f.replace("Z", "+00:00")) for f in fechas) if fechas else dt.datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))

    def _escribir(self, method: str, url: str, body: dict | None = None) -> None:
        """Única vía de escritura en GitHub; en --dry-run se bloquea aunque alguna rama de código la invoque."""
        if self.dry:
            raise SystemExit(f"ABORTADO (dry-run): escritura bloqueada {method} {url}")
        _req(method, url, self.token, body)

    def etiquetar(self, n: int, poner: str | None = None, quitar: tuple[str, ...] = ()) -> None:
        if self.dry:
            return log(f"[dry-run] etiquetas PR {n}: +{poner} -{quitar}")
        for q in quitar:
            self._escribir("DELETE", self._u(f"/issues/{n}/labels/{urllib.parse.quote(q)}"))
        if poner:
            self._escribir("POST", self._u(f"/issues/{n}/labels"), {"labels": [poner]})

    def comentar(self, n: int, texto: str) -> None:
        """Un único comentario del controlador por PR (se edita; no se acumulan)."""
        cuerpo = f"{MARCA_COMENTARIO}\n{texto}"
        if self.dry:
            return log(f"[dry-run] comentario en PR {n}: {texto[:100]}…")
        st, items = _req("GET", self._u(f"/issues/{n}/comments?per_page=100"), self.token)
        previo = next((c for c in (items or []) if st == 200 and MARCA_COMENTARIO in (c.get("body") or "")), None)
        if previo:
            self._escribir("PATCH", self._u(f"/issues/comments/{previo['id']}"), {"body": cuerpo})
        else:
            self._escribir("POST", self._u(f"/issues/{n}/comments"), {"body": cuerpo})


# ------------------------------------------------------------------ imágenes GHCR
ACCEPT_MANIFIESTO = "application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"


def _token_pull_ghcr(paquete: str, pat: str, opener=urllib.request.urlopen) -> str | None:
    """Token de registro (scope pull) para un paquete privado: GHCR no acepta el PAT como Bearer directo; hay
    que canjearlo en /token con autenticación Basic usuario:PAT. Sin PAT se pide un token anónimo (sirve solo
    para paquetes públicos; con uno privado el manifiesto responde 401/403 => «no publicada»)."""
    import base64
    url = f"https://ghcr.io/token?scope=repository:{GHCR_OWNER}/{paquete}:pull&service=ghcr.io"
    headers = {"User-Agent": "auditbrain-preview-controlador"}
    if pat:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{GHCR_OWNER}:{pat}".encode()).decode()
    try:
        with opener(urllib.request.Request(url, headers=headers), timeout=20) as r:
            return json.loads(r.read().decode() or "{}").get("token")
    except Exception:  # noqa: BLE001 - credencial sin read:packages, red caída, etc.
        return None


def imagenes_publicadas(sha: str, token: str, opener=urllib.request.urlopen) -> list[str]:
    """Servicios cuya imagen sha-<sha> existe en GHCR: canje PAT -> token de registro y HEAD del manifiesto."""
    ok = []
    for svc in SERVICIOS:
        paquete = f"{PAQUETE}{svc}"
        reg = _token_pull_ghcr(paquete, token, opener)
        if not reg:
            log(f"GHCR: sin token de lectura para {paquete} (¿GHCR_READ_TOKEN sin read:packages?)")
            continue
        req = urllib.request.Request(f"https://ghcr.io/v2/{GHCR_OWNER}/{paquete}/manifests/sha-{sha}", method="HEAD",
                                     headers={"Authorization": f"Bearer {reg}", "User-Agent": "auditbrain-preview-controlador", "Accept": ACCEPT_MANIFIESTO})
        try:
            with opener(req, timeout=20) as r:
                if r.status == 200:
                    ok.append(svc)
        except Exception:  # noqa: BLE001 - 401/403/404 o red: no publicada (fallo cerrado)
            pass
    return ok


# ------------------------------------------------------------------ capacidad
@dataclasses.dataclass
class Politica:
    limite_nuevo_mib: int = 1296            # presupuesto del Compose por preview (tests/test_preview_compose.py)
    reserva_seguridad_mib: int = 512        # margen que nunca se compromete
    superposicion_despliegue_mib: int = 576 # helper de Coolify + pull + arranque de la pila nueva
    factor_headroom: float = 1.0            # fracción del límite de cada preview existente que se considera crecimiento posible
    psi_max_avg60: float = 20.0
    swap_max_pct: float = 75.0
    carga_max_por_cpu: float = 2.0
    disco_min_gib: float = 3.0
    frescura_max_s: int = 180
    retry_after_s: int = 900
    # Verificación posterior al despliegue (F2, incidente del preview #392): el backend tiene
    # `start_period: 60s` en el healthcheck del Compose, así que un sondeo único e inmediato tras
    # «finished» casi siempre ve el backend aún arrancando (HTTP 0 / 503) y marca el preview «en espera»,
    # lo que dispara un redespliegue en el ciclo siguiente -> bucle. Estas cotas (todas configurables por
    # PREVIEW_*) reintentan el health check con backoff acotado, respetando ese arranque, sin bucle infinito.
    verificacion_intentos: int = 8          # número máximo de sondeos del health check
    verificacion_espera_inicial_s: int = 10 # primera espera entre sondeos
    verificacion_espera_max_s: int = 30     # techo de la espera entre sondeos (backoff progresivo)
    verificacion_tiempo_max_s: int = 180    # tiempo total máximo de verificación (> start_period 60s + margen)

    @classmethod
    def desde_entorno(cls) -> "Politica":
        p = cls()
        for campo in dataclasses.fields(cls):
            v = os.environ.get(f"PREVIEW_{campo.name.upper()}")
            if v:
                setattr(p, campo.name, type(getattr(p, campo.name))(v))
        return p


@dataclasses.dataclass
class CapacityDecision:
    decision: str                      # ADMIT | DEFER | REJECT
    reason_code: str
    pr: int
    head_sha: str
    observed_at: str
    metrics: dict
    retry_after: int | None = None
    reservation_id: str | None = None
    detalle: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def leer_capacidad(fuentes: list[str], token: str, fetch=_req) -> dict | None:
    """Primera fuente que responda 200: GET <base>/api/v1/host-capacity con el token de capacidad."""
    for base in fuentes:
        st, d = fetch("GET", f"{base.rstrip('/')}/api/v1/host-capacity", None, headers={"X-Capacity-Token": token}, timeout=20)
        if st == 200 and isinstance(d, dict) and "mem_available_mib" in d:
            d["fuente"] = base
            return d
        log(f"capacidad: {base} -> HTTP {st}")
    return None


def decidir_capacidad(m: dict | None, previews: list[dict], en_vuelo: list[dict], prod_sana: bool | None,
                      politica: Politica, pr: int, sha: str) -> CapacityDecision:
    obs = ahora().isoformat()
    base = dict(pr=pr, head_sha=sha, observed_at=obs)
    if m is None:
        return CapacityDecision("DEFER", "TELEMETRY_UNAVAILABLE", metrics={}, retry_after=politica.retry_after_s,
                                detalle="sin lectura de capacidad del host", **base)
    try:
        leido = dt.datetime.fromisoformat(str(m.get("observed_at")).replace("Z", "+00:00"))
        edad = (ahora() - leido).total_seconds()
    except (TypeError, ValueError):
        edad = None
    # Solo los previews que realmente consumen recursos reservan headroom. Un preview
    # DETENIDO (exited/stopped) no corre y no debe reservar RAM; los estados en
    # transición o desconocidos se cuentan de forma conservadora (ver helper).
    activos = [p for p in previews if _preview_consume_recursos(p.get("status"))]
    detenidos = len(previews) - len(activos)
    otros_activos = [p for p in activos if int(p.get("pull_request_id", -1)) != pr]
    vuelo_otros = [d for d in en_vuelo if int(d.get("pull_request_id", 0) or 0) != pr]
    headroom = int(len(otros_activos) * politica.limite_nuevo_mib * politica.factor_headroom)
    reservas = len(vuelo_otros) * (politica.limite_nuevo_mib + politica.superposicion_despliegue_mib)
    mem = float(m.get("mem_available_mib") or 0)
    margen = mem - headroom - reservas - politica.limite_nuevo_mib - politica.superposicion_despliegue_mib
    metrics = {
        "mem_available_mib": int(mem), "headroom_existentes_mib": headroom, "reservas_en_vuelo_mib": reservas,
        "limite_nuevo_mib": politica.limite_nuevo_mib, "reserva_seguridad_mib": politica.reserva_seguridad_mib,
        "superposicion_mib": politica.superposicion_despliegue_mib, "margen_mib": int(margen),
        "psi_mem_some_60s": m.get("psi_mem_some_avg60"), "swap_usada_pct": m.get("swap_used_pct"),
        "carga_1m": m.get("load1"), "cpus": m.get("cpus"), "disco_libre_gib": m.get("disk_free_gib"),
        "oom_recientes": m.get("oom_recent"), "previews_activos": len(activos),
        "previews_detenidos": detenidos, "despliegues_en_vuelo": len(en_vuelo),
        "frescura_s": None if edad is None else int(edad), "fuente": m.get("fuente"), "produccion_sana": prod_sana,
    }

    def defer(code, detalle):
        return CapacityDecision("DEFER", code, metrics=metrics, retry_after=politica.retry_after_s, detalle=detalle, **base)

    if edad is None or edad > politica.frescura_max_s or edad < -60:
        return defer("TELEMETRY_UNAVAILABLE", f"lectura sin fecha o con {edad} s de antigüedad (máx {politica.frescura_max_s})")
    if prod_sana is not True:
        return defer("PRODUCTION_UNHEALTHY", "producción no responde 200: no se añade carga al host")
    if vuelo_otros:
        return defer("IN_FLIGHT_RESERVATION", f"{len(vuelo_otros)} despliegue(s) de otros PR en curso")
    if m.get("oom_recent") not in (None, 0, "0", False):
        return defer("OOM_RECENT", f"eventos OOM recientes: {m.get('oom_recent')}")
    if margen < politica.reserva_seguridad_mib:
        return defer("RAM_HEADROOM", f"margen {int(margen)} MiB < reserva de seguridad {politica.reserva_seguridad_mib} MiB")
    psi = m.get("psi_mem_some_avg60")
    if psi is not None and float(psi) > politica.psi_max_avg60:
        return defer("CPU_PRESSURE", f"PSI memoria some avg60={psi} > {politica.psi_max_avg60}")
    swap = m.get("swap_used_pct")
    if swap is not None and float(swap) > politica.swap_max_pct:
        return defer("SWAP_PRESSURE", f"swap usada {swap}% > {politica.swap_max_pct}%")
    carga, cpus = m.get("load1"), m.get("cpus")
    if carga is not None and cpus and float(carga) > politica.carga_max_por_cpu * float(cpus):
        return defer("CPU_PRESSURE", f"carga 1 min {carga} > {politica.carga_max_por_cpu}×{cpus} cpus")
    disco = m.get("disk_free_gib")
    if disco is None or float(disco) < politica.disco_min_gib:
        return defer("DISK", f"disco libre {disco} GiB < {politica.disco_min_gib} GiB")
    return CapacityDecision("ADMIT", "OK", metrics=metrics, detalle=f"margen {int(margen)} MiB", **base)


# ------------------------------------------------------------------ puertas de seguridad
def autores_autorizados() -> set[str]:
    repo_owner = (os.environ.get("GITHUB_REPOSITORY") or "/").split("/")[0].lower()
    extra = {a.strip().lower() for a in os.environ.get("PREVIEW_AUTHORS_ALLOWED", "").split(",") if a.strip()}
    return ({repo_owner} if repo_owner else set()) | extra


def puerta_pr(pr: dict, repo: str, autores: set[str]) -> str | None:
    """Motivo de rechazo (REJECT/SECURITY) o None si el PR es elegible."""
    if pr.get("state") != "open":
        return "el PR no está abierto"
    if (pr.get("head") or {}).get("repo", {}).get("full_name", "").lower() != repo.lower():
        return "el PR proviene de un fork u otro repositorio"
    if (pr.get("base") or {}).get("ref") != "main":
        return "el PR no apunta a main"
    autor = ((pr.get("user") or {}).get("login") or "").lower()
    if autor not in autores:
        return f"autor '{autor}' no autorizado para previews"
    if pr.get("draft"):
        return "el PR es un borrador (draft): se despliega al marcarlo listo"
    return None


def plantilla_confiable(gh: GitHub, head_sha: str, ref_confiable: str, etiquetas: set[str]) -> str | None:
    """El Compose del PR debe ser idéntico al de la referencia protegida (es el que Coolify ejecuta); los
    Dockerfiles distintos exigen la etiqueta administrativa preview:dockerfiles-aprobados."""
    for path in ARCHIVOS_PLANTILLA:
        a, b = gh.blob_sha(path, head_sha), gh.blob_sha(path, ref_confiable)
        if not a or not b:
            return f"no se pudo leer {path} en {head_sha[:12]} o en {ref_confiable}"
        if a != b:
            return f"{path} difiere de {ref_confiable}: el Compose de previews solo se cambia por un PR revisado y fusionado"
    if ETIQUETA_DOCKERFILES_OK not in etiquetas:
        for path in ARCHIVOS_DOCKERFILES:
            a, b = gh.blob_sha(path, head_sha), gh.blob_sha(path, ref_confiable)
            if a and b and a != b:
                return f"{path} difiere de {ref_confiable}; un mantenedor debe revisarlo y poner la etiqueta {ETIQUETA_DOCKERFILES_OK}"
    return None


def checks_obligatorios(check_runs: list[dict], prefijos: tuple[str, ...]) -> tuple[str, str]:
    """('ok'|'pendiente'|'fallido', detalle) para los check-runs cuyo nombre empieza por alguno de los prefijos."""
    vistos = [c for c in check_runs if any(str(c.get("name", "")).startswith(p) for p in prefijos)]
    if not vistos:
        return "pendiente", f"sin check-runs {prefijos} todavía"
    fallidos = [c["name"] for c in vistos if c.get("status") == "completed" and c.get("conclusion") not in ("success", "skipped", "neutral")]
    if fallidos:
        return "fallido", ", ".join(fallidos[:4])
    pend = [c["name"] for c in vistos if c.get("status") != "completed"]
    if pend:
        return "pendiente", ", ".join(pend[:4])
    return "ok", f"{len(vistos)} check(s) en verde"


# ------------------------------------------------------------------ verificación posterior
def urls_preview(n: int, dominio_base: str) -> dict:
    return {"api": f"https://{n}.api.{dominio_base}", "consola": f"https://{n}.consola.{dominio_base}", "clientes": f"https://{n}.clientes.{dominio_base}"}


def verificar_preview(n: int, sha: str, dominio_base: str, fetch=_req) -> list[str]:
    """Problemas encontrados ([] = el preview sirve exactamente el commit sha en los tres servicios)."""
    u = urls_preview(n, dominio_base)
    problemas = []
    st, d = fetch("GET", f"{u['api']}/api/v1/health", None, timeout=20)
    if st != 200 or not isinstance(d, dict):
        problemas.append(f"api: HTTP {st}")
    else:
        commit = (d.get("build") or {}).get("commit")
        if commit != sha:
            problemas.append(f"api: build.commit={commit} ≠ {sha[:12]}")
        if str((d.get("preview") or {}).get("pr")) != str(n):
            problemas.append(f"api: preview.pr={(d.get('preview') or {}).get('pr')} ≠ {n}")
    for svc in ("consola", "clientes"):
        st, d = fetch("GET", f"{u[svc]}/build-info.json", None, timeout=20)
        if st != 200 or not isinstance(d, dict) or d.get("commit") != sha:
            problemas.append(f"{svc}: HTTP {st}, commit={(d or {}).get('commit') if isinstance(d, dict) else None}")
    return problemas


def verificar_con_reintentos(n: int, sha: str, dominio_base: str, politica: Politica,
                             fetch=_req, sleep=time.sleep) -> tuple[list[str], int, int]:
    """Verifica el preview reintentando mientras el backend arranca (respeta su `start_period`).

    Distingue «despliegue finalizado» de «aplicación sana»: tras un despliegue terminado el backend
    puede tardar hasta ~60 s en responder 200. Reintenta con backoff acotado (espera inicial que se
    duplica hasta un techo) y se detiene en cuanto el preview sirve el commit, al agotar los intentos
    o al superar el tiempo total. Nunca es un bucle infinito. Registra evidencia de cada intento.

    Devuelve (problemas, intentos, segundos); problemas == [] significa que el preview está sano.
    """
    inicio = time.monotonic()
    espera = max(1, politica.verificacion_espera_inicial_s)
    intento = 0
    problemas: list[str] = ["sin verificación"]
    while True:
        intento += 1
        problemas = verificar_preview(n, sha, dominio_base, fetch)
        transcurrido = int(time.monotonic() - inicio)
        if not problemas:
            log(f"verificación PR {n}: sana en el intento {intento} (~{transcurrido} s)")
            return [], intento, transcurrido
        agotado = intento >= politica.verificacion_intentos or transcurrido >= politica.verificacion_tiempo_max_s
        log(f"verificación PR {n}: intento {intento} sin éxito ({'; '.join(problemas)})"
            + ("; se agota la verificación" if agotado else f"; reintento en {espera} s"))
        if agotado:
            return problemas, intento, transcurrido
        sleep(espera)
        espera = min(espera * 2, politica.verificacion_espera_max_s)


# ------------------------------------------------------------------ orquestación
@dataclasses.dataclass
class Contexto:
    co: Coolify
    gh: GitHub
    repo: str
    politica: Politica
    dominio_base: str = "preview.audit-ia.ec"
    ref_confiable: str = "main"
    prefijos_checks: tuple[str, ...] = ("pytest (python 3.12)",)
    fuentes_capacidad: list[str] = dataclasses.field(default_factory=list)
    token_capacidad: str = ""
    token_ghcr: str = ""
    urls_produccion: list[str] = dataclasses.field(default_factory=lambda: ["https://api.audit-ia.ec/api/v1/health"])
    fetch: object = _req
    imagenes_fn: object = imagenes_publicadas
    sleep: object = time.sleep
    espera_max_s: int = 1500
    dry: bool = False


def produccion_sana(ctx: Contexto) -> bool:
    for u in ctx.urls_produccion:
        st, _ = ctx.fetch("GET", u, None, timeout=20)
        if st != 200:
            return False
    return True


def _resultado(ctx: Contexto, n: int, estado: str, titulo: str, cuerpo: str, decision: CapacityDecision | None = None) -> int:
    texto = f"### Preview del PR #{n}: {titulo}\n\n{cuerpo}"
    if decision is not None:
        texto += f"\n\n<details><summary>CapacityDecision</summary>\n\n```json\n{json.dumps(decision.to_dict(), indent=2, ensure_ascii=False)}\n```\n</details>"
    ctx.gh.comentar(n, texto)
    quitar = tuple(e for e in (ETIQUETA_ESPERA, ETIQUETA_RECHAZO, ETIQUETA_ACTIVO) if e != estado)
    ctx.gh.etiquetar(n, estado, quitar)
    log(f"PR {n}: {estado} — {titulo}")
    return {ETIQUETA_ACTIVO: 0, ETIQUETA_ESPERA: 0, ETIQUETA_RECHAZO: 0}.get(estado, 1)


def sincronizar(ctx: Contexto, n: int, sha_esperado: str | None = None) -> int:
    pr = ctx.gh.pr(n)
    sha = pr["head"]["sha"]
    if sha_esperado and sha_esperado != sha:
        log(f"PR {n}: el head cambió ({sha_esperado[:12]} → {sha[:12]}); lo atenderá la ejecución del nuevo push")
        return 0
    if not _SHA40.match(sha):
        return _resultado(ctx, n, ETIQUETA_RECHAZO, "rechazado", f"head.sha inválido: {sha}")
    motivo = puerta_pr(pr, ctx.repo, autores_autorizados())
    if motivo:
        if pr.get("state") != "open":
            log(f"PR {n}: {motivo}; nada que hacer")
            return 0
        return _resultado(ctx, n, ETIQUETA_RECHAZO, "rechazado (seguridad)", motivo,
                          CapacityDecision("REJECT", "SECURITY", n, sha, ahora().isoformat(), {}, detalle=motivo))
    etiquetas = {l["name"] for l in pr.get("labels", [])}
    motivo = plantilla_confiable(ctx.gh, sha, ctx.ref_confiable, etiquetas)
    if motivo:
        return _resultado(ctx, n, ETIQUETA_RECHAZO, "rechazado (plantilla no confiable)", motivo,
                          CapacityDecision("REJECT", "SECURITY", n, sha, ahora().isoformat(), {}, detalle=motivo))
    estado, detalle = checks_obligatorios(ctx.gh.check_runs(sha), ctx.prefijos_checks)
    if estado == "fallido":
        return _resultado(ctx, n, ETIQUETA_RECHAZO, "no desplegado: pruebas obligatorias en rojo", f"Fallan: {detalle}. Corrige y vuelve a hacer push.")
    if estado == "pendiente":
        return _resultado(ctx, n, ETIQUETA_ESPERA, "en espera: pruebas obligatorias pendientes", f"{detalle}. Se reintenta automáticamente.",
                          CapacityDecision("DEFER", "CHECKS_PENDING", n, sha, ahora().isoformat(), {}, retry_after=ctx.politica.retry_after_s))
    publicadas = ctx.imagenes_fn(sha, ctx.token_ghcr)
    faltan = [s for s in SERVICIOS if s not in publicadas]
    if faltan:
        return _resultado(ctx, n, ETIQUETA_ESPERA, "en espera: imágenes no publicadas todavía",
                          f"Faltan en GHCR (privado): {', '.join(faltan)} para `sha-{sha[:12]}…`. El workflow `preview-images` las publica; se reintenta automáticamente.",
                          CapacityDecision("DEFER", "IMAGES_MISSING", n, sha, ahora().isoformat(), {}, retry_after=ctx.politica.retry_after_s))
    previews = ctx.co.previews()
    propio = next((p for p in previews if int(p.get("pull_request_id", -1)) == n), None)
    en_vuelo = ctx.co.despliegues_en_vuelo()
    if any(int(d.get("pull_request_id", 0) or 0) == n for d in en_vuelo):
        return _resultado(ctx, n, ETIQUETA_ESPERA, "en espera: ya hay un despliegue de este PR en curso", "Se reintenta cuando termine.",
                          CapacityDecision("DEFER", "IN_FLIGHT_RESERVATION", n, sha, ahora().isoformat(), {}, retry_after=ctx.politica.retry_after_s))
    metricas = leer_capacidad(ctx.fuentes_capacidad, ctx.token_capacidad, ctx.fetch) if ctx.fuentes_capacidad else None
    # Actualizar un preview ya en ejecución no añade un contenedor nuevo de forma permanente: se evalúa como PR propio
    # (sus propios límites no cuentan como «otros»), pero sí exige margen para la superposición temporal del redespliegue.
    decision = decidir_capacidad(metricas, previews, en_vuelo, produccion_sana(ctx), ctx.politica, n, sha)
    if decision.decision != "ADMIT":
        return _resultado(ctx, n, ETIQUETA_ESPERA, f"en espera: capacidad ({decision.reason_code})",
                          f"{decision.detalle}. Reintento automático en ~{(decision.retry_after or 0)//60} min. No se detiene ningún otro preview para hacer sitio.", decision)
    # Anti-bucle de redespliegue (incidente del preview del PR #392): si el preview del PR ya existe,
    # está EN EJECUCIÓN y YA sirve exactamente este commit en los tres servicios, NO se redespliega. Un
    # redespliegue derriba un contenedor sano y arranca otro ciclo de ~60 s en el que la verificación
    # inmediata falla y vuelve a encolar el PR -> bucle. Se comprueba una sola vez (sondeo barato); si el
    # preview no está sano todavía, se continúa con el despliegue normal.
    if propio is not None and str(propio.get("status", "")).lower().startswith(("running", "degraded", "restarting")):
        if not verificar_preview(n, sha, ctx.dominio_base, ctx.fetch):
            u = urls_preview(n, ctx.dominio_base)
            cuerpo = (f"El preview ya servía el commit `{sha}` en los tres servicios; no se redesplegó para no "
                      f"derribar un contenedor sano.\n\n- Consola: {u['consola']}\n- Portal de clientes: {u['clientes']}\n"
                      f"- API: {u['api']}/api/v1/health")
            log(f"PR {n}: preview ya sano con {sha[:12]}; se omite el redespliegue")
            return _resultado(ctx, n, ETIQUETA_ACTIVO, "ya estaba listo (sin redesplegar)", cuerpo, decision)
    if propio is None:
        ctx.co.asegurar_preview(n, pr.get("html_url", ""))
    dep = ctx.co.desplegar(n)
    if dep == "429":
        return _resultado(ctx, n, ETIQUETA_ESPERA, "en espera: Coolify ya tiene un despliegue en cola", "Se reintenta automáticamente.",
                          CapacityDecision("DEFER", "IN_FLIGHT_RESERVATION", n, sha, ahora().isoformat(), decision.metrics, retry_after=60))
    decision.reservation_id = f"{ctx.repo}/{n}/{sha}/{dep or 'dry-run'}"
    if ctx.dry:
        return _resultado(ctx, n, ETIQUETA_ESPERA, "simulación (dry-run): se habría desplegado", "Ninguna llamada de escritura ejecutada.", decision)
    final = _esperar(ctx, dep) if dep else "desconocido"
    if final != "finished":
        return _resultado(ctx, n, ETIQUETA_ESPERA, f"despliegue terminó en «{final}»",
                          f"Coolify no completó el despliegue del commit `{sha[:12]}` (estado {final}). Revisa el registro del despliegue en Coolify; se reintenta con el siguiente push o en el próximo ciclo.", decision)
    problemas, intentos, segundos = verificar_con_reintentos(n, sha, ctx.dominio_base, ctx.politica, ctx.fetch, ctx.sleep)
    u = urls_preview(n, ctx.dominio_base)
    if problemas:
        return _resultado(ctx, n, ETIQUETA_ESPERA, "desplegado pero la verificación falló",
                          f"El preview no sirve el commit esperado en los tres servicios tras {intentos} intento(s) (~{segundos} s): "
                          + "; ".join(problemas), decision)
    cuerpo = (f"Commit `{sha}` · imágenes `sha-{sha[:12]}…` (GHCR privado) · verificado tras {intentos} intento(s) (~{segundos} s): `build.commit` = head en API, consola y portal.\n\n"
              f"- Consola: {u['consola']}\n- Portal de clientes: {u['clientes']}\n- API: {u['api']}/api/v1/health\n\n"
              f"Base de datos y secretos exclusivos de este PR. Cada push actualiza solo este preview; al cerrar o fusionar el PR se elimina.")
    return _resultado(ctx, n, ETIQUETA_ACTIVO, "listo", cuerpo, decision)


def _esperar(ctx: Contexto, deployment_uuid: str) -> str:
    inicio = time.monotonic()
    estado = "desconocido"
    while time.monotonic() - inicio < ctx.espera_max_s:
        d = ctx.co.despliegue(deployment_uuid)
        estado = str((d or {}).get("status", "desconocido")).lower()
        if estado not in ESTADOS_EN_VUELO:
            return estado
        ctx.sleep(20)
    return f"timeout({estado})"


def reintentar(ctx: Contexto) -> int:
    cola = [p for p in ctx.gh.abiertos() if any(l["name"] == ETIQUETA_ESPERA for l in p.get("labels", []))]
    cola.sort(key=lambda p: p["created_at"])
    log(f"PR en espera: {[p['number'] for p in cola]}")
    for p in cola:
        rc = sincronizar(ctx, p["number"])
        pr_actual = ctx.gh.pr(p["number"])
        if any(l["name"] == ETIQUETA_ACTIVO for l in pr_actual.get("labels", [])):
            break  # un despliegue por ciclo: la siguiente evaluación verá la capacidad ya consumida
        if rc not in (0,):
            break
    return 0


def cerrar(ctx: Contexto, n: int) -> int:
    pr = ctx.gh.pr(n)
    if pr.get("state") == "open":
        log(f"PR {n} sigue abierto: no se elimina nada")
        return 0
    if (pr.get("head") or {}).get("repo", {}).get("full_name", "").lower() != ctx.repo.lower():
        log(f"PR {n}: repositorio distinto; no se toca Coolify")
        return 0
    pv = ctx.co.preview(n)
    if not pv or int(pv.get("pull_request_id", -1)) != n:
        log(f"PR {n}: sin preview en la aplicación de previews; nada que eliminar")
        return 0
    ctx.co.borrar(n)
    ctx.gh.etiquetar(n, None, (ETIQUETA_ACTIVO, ETIQUETA_ESPERA))
    ctx.gh.comentar(n, f"### Preview del PR #{n}: eliminado\n\nPR {'fusionado' if pr.get('merged') else 'cerrado'}: se eliminó únicamente el preview `{n}` (contenedores, red y dominios de este PR) de la aplicación de previews.")
    return 0


def caducidad(ctx: Contexto, dias: int) -> int:
    abiertos = {p["number"]: p for p in ctx.gh.abiertos()}
    for pv in ctx.co.previews():
        n = int(pv.get("pull_request_id", 0))
        pr = abiertos.get(n)
        if not pr:
            log(f"preview {n}: PR no abierto (lo elimina el cierre); se omite"); continue
        if any(l["name"] == ETIQUETA_KEEP for l in pr.get("labels", [])):
            log(f"preview {n}: etiqueta {ETIQUETA_KEEP}; se omite"); continue
        ultima = ctx.gh.ultima_actividad_humana(pr)
        upd = pv.get("updated_at")
        if upd:
            ultima = max(ultima, dt.datetime.fromisoformat(str(upd).replace("Z", "+00:00")))
        edad = ahora() - ultima
        log(f"preview {n}: última actividad {ultima.isoformat()} ({edad.days} d)")
        if edad >= dt.timedelta(days=dias):
            ctx.co.borrar(n)
            ctx.gh.etiquetar(n, ETIQUETA_ESPERA, (ETIQUETA_ACTIVO,))
            ctx.gh.comentar(n, f"### Preview del PR #{n}: eliminado por inactividad\n\n{dias} días sin actividad humana (última {ultima:%Y-%m-%d %H:%M} UTC). Se recreará automáticamente con el siguiente push o en el próximo ciclo si hay capacidad.")
    return 0


def capacidad(ctx: Contexto) -> int:
    """Solo lectura: lee la telemetría, los previews y despliegues en vuelo y la salud de producción, e imprime la
    CapacityDecision que recibiría un PR hipotético. Sirve para verificar /api/v1/host-capacity antes de activar."""
    m = leer_capacidad(ctx.fuentes_capacidad, ctx.token_capacidad, ctx.fetch) if ctx.fuentes_capacidad else None
    d = decidir_capacidad(m, ctx.co.previews(), ctx.co.despliegues_en_vuelo(), produccion_sana(ctx), ctx.politica, 0, "0" * 40)
    print(json.dumps(d.to_dict(), indent=2, ensure_ascii=False))
    if d.reason_code == "TELEMETRY_UNAVAILABLE":
        log("telemetría NO disponible: revisar PREVIEW_CAPACITY_SOURCES y PREVIEW_CAPACITY_TOKEN (ver docs §9); con este estado todo PR queda en espera")
        return 3
    log(f"telemetría OK desde {m.get('fuente')}: decisión hipotética {d.decision} ({d.reason_code})")
    return 0


def contexto_desde_entorno(dry: bool) -> Contexto:
    faltan = [k for k in ("COOLIFY_URL", "COOLIFY_API_TOKEN", "COOLIFY_PREVIEW_APP_UUID", "GITHUB_TOKEN", "GITHUB_REPOSITORY") if not os.environ.get(k)]
    if faltan:
        raise SystemExit(f"Faltan variables: {faltan}. Nada ejecutado.")
    co = Coolify(os.environ["COOLIFY_URL"], os.environ["COOLIFY_API_TOKEN"], os.environ["COOLIFY_PREVIEW_APP_UUID"], dry)
    gh = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"], dry)
    return Contexto(
        co=co, gh=gh, repo=os.environ["GITHUB_REPOSITORY"], politica=Politica.desde_entorno(), dry=dry,
        dominio_base=os.environ.get("PREVIEW_DOMAIN_BASE", "preview.audit-ia.ec"),
        ref_confiable=os.environ.get("PREVIEW_TEMPLATE_REF", "main"),
        prefijos_checks=tuple(p.strip() for p in os.environ.get("PREVIEW_REQUIRED_CHECKS", "pytest (python 3.12)").split(";") if p.strip()),
        fuentes_capacidad=[u.strip() for u in os.environ.get("PREVIEW_CAPACITY_SOURCES", "").split(",") if u.strip()],
        token_capacidad=os.environ.get("PREVIEW_CAPACITY_TOKEN", ""),
        token_ghcr=os.environ.get("GHCR_READ_TOKEN") or os.environ.get("GHCR_PUBLISH_TOKEN", ""),
        urls_produccion=[u.strip() for u in os.environ.get("PREVIEW_PRODUCTION_HEALTH_URLS", "https://api.audit-ia.ec/api/v1/health").split(",") if u.strip()],
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["sincronizar", "reintentar", "cerrar", "caducidad", "capacidad"])
    ap.add_argument("--pr", type=int)
    ap.add_argument("--sha")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    ctx = contexto_desde_entorno(a.dry_run)
    if a.accion in ("sincronizar", "cerrar") and not a.pr:
        print("--pr es obligatorio", file=sys.stderr); return 2
    if a.accion == "capacidad":
        return capacidad(ctx)
    if a.accion == "sincronizar":
        return sincronizar(ctx, a.pr, a.sha)
    if a.accion == "reintentar":
        return reintentar(ctx)
    if a.accion == "cerrar":
        return cerrar(ctx, a.pr)
    return caducidad(ctx, int(os.environ.get("DIAS_INACTIVIDAD", "3")))


if __name__ == "__main__":
    sys.exit(main())
