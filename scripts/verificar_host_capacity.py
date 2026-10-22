#!/usr/bin/env python3
"""Verifica, solo con lecturas HTTP, que una URL base sirve /api/v1/host-capacity con la semántica esperada
(docs/previews-coolify.md §9 y §13) antes de activar los previews automáticos:

  python scripts/verificar_host_capacity.py https://384.api.preview.audit-ia.ec

El token se lee de la variable PREVIEW_CAPACITY_TOKEN (nunca se pasa por argumento ni se imprime).
Comprobaciones: sin cabecera => 401 (la función existe y está protegida); con token incorrecto => 401; con el
token => 200 y los campos de la política; un 404 significa que ese backend no tiene PREVIEW_CAPACITY_TOKEN
configurado (función apagada) o no incluye todavía el endpoint. Código de salida 0 solo si todo cuadra.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

CAMPOS = ("observed_at", "mem_available_mib", "swap_used_pct", "load1", "cpus", "disk_free_gib")


def _get(url: str, token: str | None) -> tuple[int, dict | None]:
    headers = {"User-Agent": "auditbrain-verificar-host-capacity"}
    if token is not None:
        headers["X-Capacity-Token"] = token
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, OSError) as e:
        print(f"sin conexión: {str(e)[:120]}")
        return 0, None


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[1].startswith("https://"):
        print(__doc__); return 2
    token = (os.environ.get("PREVIEW_CAPACITY_TOKEN") or "").strip()
    if len(token) < 24:
        print("PREVIEW_CAPACITY_TOKEN ausente o demasiado corto (mínimo 24 caracteres) en el entorno"); return 2
    url = argv[1].rstrip("/") + "/api/v1/host-capacity"
    fallos = []
    st, _ = _get(url, None)
    print(f"sin cabecera        -> HTTP {st} (esperado 401)")
    if st == 404:
        print("  404: ese backend tiene la función apagada (sin PREVIEW_CAPACITY_TOKEN) o no incluye el endpoint todavía"); return 3
    st == 401 or fallos.append("sin cabecera no devuelve 401")
    st, _ = _get(url, "x" * 32)
    print(f"token incorrecto    -> HTTP {st} (esperado 401)")
    st == 401 or fallos.append("token incorrecto no devuelve 401")
    st, body = _get(url, token)
    print(f"token correcto      -> HTTP {st} (esperado 200)")
    if st != 200 or not isinstance(body, dict):
        fallos.append("con el token no responde 200")
    else:
        faltan = [c for c in CAMPOS if c not in body]
        faltan and fallos.append(f"faltan campos: {faltan}")
        print("  lectura:", json.dumps({k: body.get(k) for k in ("observed_at", "mem_total_mib", "mem_available_mib", "swap_used_pct", "psi_mem_some_avg60", "load1", "cpus", "disk_free_gib", "oom_recent")}, ensure_ascii=False))
    if fallos:
        print("RESULTADO: NO APTO —", "; ".join(fallos)); return 1
    print("RESULTADO: APTO como fuente de PREVIEW_CAPACITY_SOURCES"); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
