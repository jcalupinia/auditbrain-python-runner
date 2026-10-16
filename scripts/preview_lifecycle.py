#!/usr/bin/env python3
"""Ciclo de vida de los Preview Environments de Coolify por API (admitir / liberar / caducidad).

DESHABILITADO PARA EJECUCIÓN REAL mientras no exista transporte seguro: el script se niega a
usar una COOLIFY_URL que no empiece por https:// (el token nunca viaja por HTTP plano) y arranca
en --dry-run salvo que se pida lo contrario. Lo invoca .github/workflows/preview-lifecycle.yml,
que además exige la variable PREVIEW_PIPELINE_ENABLED. No contiene secretos; los lee del entorno.

Acciones
  admitir --pr N   Si hay cupo (MAX_ACTIVE_PREVIEWS, por defecto 1) y las tres imágenes
                   sha-<head.sha> existen en GHCR, crea el preview sin desplegar
                   (POST /applications/{uuid}/previews, instant_deploy=false), fija la variable
                   de preview PREVIEW_IMAGE_TAG=sha-<head.sha> y despliega (POST /deploy?uuid&pr).
                   Sin cupo: etiqueta `preview:en-cola` y comenta en el PR. Rechaza PRs de forks.
  liberar          Despliega (vía admitir) el PR en cola más antiguo si hay cupo.
  caducidad        Elimina previews de PRs abiertos con >= DIAS_INACTIVIDAD (3) días sin actividad
                   (último commit, último comentario/revisión humana, último despliegue), salvo
                   etiqueta `preview:keep`; comenta y etiqueta `preview:caducado`.

Solo lectura de GitHub salvo etiquetas y comentarios. Nunca imprime tokens.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BOTS = {"coolify", "github-actions[bot]", "render[bot]", "claude[bot]", "dependabot[bot]"}


def log(msg: str) -> None:
    print(dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%SZ"), msg, flush=True)


def _req(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json" if "api.github.com" in url else "application/json",
        "Content-Type": "application/json", "User-Agent": "auditbrain-preview-lifecycle"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode() or "null"
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="ignore")[:300]
        return e.code, {"error": raw}


class Coolify:
    def __init__(self, base: str, token: str, app_uuid: str, dry: bool):
        if not base.lower().startswith("https://"):
            raise SystemExit("ABORTADO: COOLIFY_URL debe ser https:// (el token no se envía por HTTP plano).")
        self.base, self.token, self.app, self.dry = base.rstrip("/"), token, app_uuid, dry

    def _u(self, path: str) -> str:
        return f"{self.base}/api/v1{path}"

    def previews(self) -> list[dict]:
        st, data = _req("GET", self._u(f"/applications/{self.app}/previews"), self.token)
        if st != 200:
            raise SystemExit(f"Coolify GET previews -> {st}")
        return data or []

    def activos(self) -> list[dict]:
        return [p for p in self.previews() if str(p.get("status", "")).lower().startswith(("running", "starting", "in_progress", "queued"))]

    def crear(self, pr: int) -> None:
        if self.dry:
            return log(f"[dry-run] POST previews pr={pr} instant_deploy=false")
        st, d = _req("POST", self._u(f"/applications/{self.app}/previews"), self.token, {"pull_request_id": pr, "instant_deploy": False})
        if st not in (200, 201):
            raise SystemExit(f"Coolify crear preview -> {st} {d}")

    def fijar_tag(self, tag: str) -> None:
        # Variable de preview (is_preview=true). Idempotente: update o create.
        body = {"key": "PREVIEW_IMAGE_TAG", "value": tag, "is_preview": True, "is_build_time": False}
        if self.dry:
            return log(f"[dry-run] PATCH/POST env PREVIEW_IMAGE_TAG={tag} (preview)")
        st, d = _req("PATCH", self._u(f"/applications/{self.app}/envs"), self.token, body)
        if st not in (200, 201):
            st, d = _req("POST", self._u(f"/applications/{self.app}/envs"), self.token, body)
            if st not in (200, 201):
                raise SystemExit(f"Coolify fijar PREVIEW_IMAGE_TAG -> {st} {d}")

    def desplegar(self, pr: int) -> None:
        if self.dry:
            return log(f"[dry-run] POST deploy uuid={self.app} pr={pr}")
        st, d = _req("POST", self._u(f"/deploy?uuid={self.app}&pr={pr}"), self.token)
        if st != 200:
            raise SystemExit(f"Coolify deploy -> {st} {d}")

    def borrar(self, pr: int) -> None:
        if self.dry:
            return log(f"[dry-run] DELETE previews/{pr}")
        st, d = _req("DELETE", self._u(f"/applications/{self.app}/previews/{pr}"), self.token)
        if st not in (200, 204):
            raise SystemExit(f"Coolify borrar preview -> {st} {d}")


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

    def etiquetar(self, n: int, etiqueta: str) -> None:
        if self.dry:
            return log(f"[dry-run] etiqueta {etiqueta} en PR {n}")
        _req("POST", self._u(f"/issues/{n}/labels"), self.token, {"labels": [etiqueta]})

    def comentar(self, n: int, texto: str) -> None:
        if self.dry:
            return log(f"[dry-run] comentario en PR {n}: {texto[:80]}…")
        _req("POST", self._u(f"/issues/{n}/comments"), self.token, {"body": texto})


def imagenes_existen(sha: str, token: str) -> bool:
    """Comprueba en GHCR que las tres imágenes sha-<sha> existen (manifest HEAD)."""
    ok = True
    for svc in ("backend", "consola", "clientes"):
        url = f"https://ghcr.io/v2/jcalupinia/auditbrain-preview-{svc}/manifests/sha-{sha}"
        req = urllib.request.Request(url, method="HEAD", headers={
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                ok = ok and r.status == 200
        except Exception:  # noqa: BLE001
            log(f"imagen ausente en GHCR: auditbrain-preview-{svc}:sha-{sha[:12]}")
            ok = False
    return ok


def admitir(co: Coolify, gh: GitHub, n: int, max_activos: int) -> int:
    pr = gh.pr(n)
    if pr["state"] != "open":
        log(f"PR {n} no está abierto; nada que hacer"); return 0
    if pr["head"]["repo"]["full_name"].lower() != gh.repo.lower():
        log(f"PR {n} viene de un fork: no se despliega"); return 0
    sha = pr["head"]["sha"]
    activos = co.activos()
    if any(int(p.get("pull_request_id", -1)) == n for p in activos):
        log(f"PR {n} ya tiene preview activo"); return 0
    if len(activos) >= max_activos:
        gh.etiquetar(n, "preview:en-cola")
        gh.comentar(n, f"Preview en cola: ya hay {len(activos)} preview(s) activo(s) (máximo {max_activos}). Se desplegará al liberarse el cupo.")
        return 0
    token_ghcr = os.environ.get("GHCR_READ_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not imagenes_existen(sha, token_ghcr):
        gh.comentar(n, f"Preview no desplegado: faltan imágenes `sha-{sha[:12]}…` en GHCR. Ejecutar `preview-images` para este PR.")
        return 2
    co.crear(n)
    co.fijar_tag(f"sha-{sha}")
    co.desplegar(n)
    gh.comentar(n, f"Preview solicitado a Coolify para el commit `{sha[:12]}` (imágenes `sha-{sha[:12]}…`). Las URL las publica Coolify al terminar.")
    return 0


def liberar(co: Coolify, gh: GitHub, max_activos: int) -> int:
    if len(co.activos()) >= max_activos:
        log("sin cupo"); return 0
    cola = [p for p in gh.abiertos() if any(l["name"] == "preview:en-cola" for l in p.get("labels", []))]
    if not cola:
        log("cola vacía"); return 0
    cola.sort(key=lambda p: p["created_at"])
    return admitir(co, gh, cola[0]["number"], max_activos)


def caducidad(co: Coolify, gh: GitHub, dias: int) -> int:
    ahora = dt.datetime.now(dt.timezone.utc)
    abiertos = {p["number"]: p for p in gh.abiertos()}
    for pv in co.previews():
        n = int(pv.get("pull_request_id", 0))
        pr = abiertos.get(n)
        if not pr:
            log(f"preview {n}: PR no abierto (Coolify lo limpia al cerrar); se omite"); continue
        if any(l["name"] == "preview:keep" for l in pr.get("labels", [])):
            log(f"preview {n}: etiqueta preview:keep; se omite"); continue
        ultima = gh.ultima_actividad_humana(pr)
        upd = pv.get("updated_at")
        if upd:
            ultima = max(ultima, dt.datetime.fromisoformat(str(upd).replace("Z", "+00:00")))
        edad = ahora - ultima
        log(f"preview {n}: última actividad {ultima.isoformat()} ({edad.days} d)")
        if edad >= dt.timedelta(days=dias):
            co.borrar(n)
            gh.etiquetar(n, "preview:caducado")
            gh.comentar(n, f"Preview eliminado por {dias} días de inactividad (última actividad {ultima:%Y-%m-%d %H:%M} UTC). Haz push o pide `preview-lifecycle admitir` para recrearlo.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["admitir", "liberar", "caducidad"])
    ap.add_argument("--pr", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    faltan = [k for k in ("COOLIFY_URL", "COOLIFY_API_TOKEN", "COOLIFY_PREVIEW_APP_UUID", "GITHUB_TOKEN", "GITHUB_REPOSITORY") if not os.environ.get(k)]
    if faltan:
        print(f"Faltan variables: {faltan}. Nada ejecutado.", file=sys.stderr); return 3
    co = Coolify(os.environ["COOLIFY_URL"], os.environ["COOLIFY_API_TOKEN"], os.environ["COOLIFY_PREVIEW_APP_UUID"], a.dry_run)
    gh = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"], a.dry_run)
    max_activos = int(os.environ.get("MAX_ACTIVE_PREVIEWS", "1"))
    if a.accion == "admitir":
        if not a.pr:
            print("--pr es obligatorio para admitir", file=sys.stderr); return 2
        return admitir(co, gh, a.pr, max_activos)
    if a.accion == "liberar":
        return liberar(co, gh, max_activos)
    return caducidad(co, gh, int(os.environ.get("DIAS_INACTIVIDAD", "3")))


if __name__ == "__main__":
    sys.exit(main())
