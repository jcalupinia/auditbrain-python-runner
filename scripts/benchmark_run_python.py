#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_run_python.py — Mide el tiempo de respuesta REAL de /run_python
del servidor AuditBrain-Python con volúmenes crecientes de información.

QUÉ MIDE Y POR QUÉ
------------------
El cuello de botella de "volumen importante" no es el tamaño de la respuesta
(ya viene en modo `compact`, ≤ 4.000 chars), sino el TIEMPO de cómputo en el
plan Starter (0.5 CPU / 512 MB) frente a los tres techos apilados:

    1. Action del GPT (OpenAI) ......... ~45 s  (NO configurable → el binding)
    2. Render / proxy .................. ~100 s
    3. EXECUTION_TIMEOUT_SECONDS ....... 600 s  (servidor)

Este script usa un timeout de cliente GENEROSO (default 120 s) a propósito:
queremos medir el tiempo VERDADERO del servidor incluso más allá de los 45 s
en que un GPT ya se habría rendido. Así encontramos a partir de qué volumen
la tarea cruza el umbral de falla de un GPT.

CÓMO SE USA (Windows PowerShell)
--------------------------------
    $env:AUDITBRAIN_API_KEY = "<tu_api_key_de_Render>"   # si la auth está activa
    python scripts/benchmark_run_python.py

    # opciones:
    #   $env:BENCH_URL   = "https://auditbrain-python-runner.onrender.com"  (default)
    #   $env:BENCH_ROWS  = "1000,10000,50000,100000,250000,500000"          (default)
    #   $env:BENCH_TIMEOUT = "120"   (segundos de timeout del cliente)
    #   $env:BENCH_REPEAT  = "1"     (repeticiones por volumen; toma el mediano)

NOTA OPERATIVA
--------------
Con EXECUTION_CONCURRENCY=1, mientras el benchmark corre OCUPA el único slot de
ejecución del servidor → puede bloquear brevemente tráfico real de los GPTs.
Córrelo en un momento de poca actividad.

NO imprime ni guarda la API key. La lee de la variable de entorno.
"""

import json
import os
import statistics
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("Falta 'requests'. Instala con:  pip install requests")


# --------------------------------------------------------------------------
# Configuración (vía variables de entorno, con defaults sensatos)
# --------------------------------------------------------------------------
BASE_URL = os.getenv("BENCH_URL", "https://auditbrain-python-runner.onrender.com").rstrip("/")
API_KEY = os.getenv("AUDITBRAIN_API_KEY", "")
CLIENT_TIMEOUT = float(os.getenv("BENCH_TIMEOUT", "120"))
REPEAT = max(1, int(os.getenv("BENCH_REPEAT", "1")))
ROWS = [
    int(x.strip())
    for x in os.getenv("BENCH_ROWS", "1000,10000,50000,100000,250000,500000").split(",")
    if x.strip()
]

# Umbrales de referencia (los tres techos del análisis)
GPT_LIMIT_S = 45.0      # techo de la Action del GPT (binding)
PROXY_LIMIT_S = 100.0   # techo aproximado de Render/proxy

# --------------------------------------------------------------------------
# Script remoto: genera un DataFrame de N filas, hace un groupby/agg realista
# (el tipo de cómputo que un GPT pediría sobre "volumen importante") y mide
# el tiempo de cómputo DENTRO del servidor. El runner expone `inputs` y lee la
# variable `result`.
# --------------------------------------------------------------------------
REMOTE_SCRIPT = r"""
import time
import numpy as np
import pandas as pd

n = int(inputs.get("n_rows", 1000))
t0 = time.perf_counter()

# Datos sintéticos deterministas (sin semilla aleatoria para reproducibilidad)
df = pd.DataFrame({
    "grupo": np.arange(n) % 250,
    "monto": (np.arange(n) * 7.13) % 100000,
    "factor": (np.arange(n) % 97) + 1.0,
})
df["ponderado"] = df["monto"] * df["factor"]

# Cómputo representativo: agregación + ordenamiento + derivadas
agg = (
    df.groupby("grupo")
      .agg(suma=("monto", "sum"),
           media=("monto", "mean"),
           max_pond=("ponderado", "max"),
           conteo=("monto", "count"))
      .sort_values("suma", ascending=False)
)
top = agg.head(5)

compute_s = round(time.perf_counter() - t0, 4)

result = {
    "n_rows": n,
    "server_compute_s": compute_s,
    "n_grupos": int(len(agg)),
    "suma_total": round(float(df["monto"].sum()), 2),
    "top5_grupos": [int(g) for g in top.index.tolist()],
}
"""


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def warmup() -> None:
    """GET / para medir latencia base y confirmar que el servicio está vivo."""
    print(f"→ Servidor: {BASE_URL}")
    print(f"→ Auth:     {'X-API-Key presente' if API_KEY else 'sin API key (auth desactivada o fallará 401)'}")
    print(f"→ Timeout cliente: {CLIENT_TIMEOUT:.0f}s · repeticiones por volumen: {REPEAT}")
    print("-" * 78)
    try:
        t0 = time.perf_counter()
        r = requests.get(BASE_URL + "/", timeout=30)
        rtt = time.perf_counter() - t0
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        print(f"Warm-up GET /  →  {r.status_code}  en {rtt*1000:.0f} ms"
              f"  (versión: {data.get('version', '?')})")
    except Exception as exc:
        print(f"Warm-up GET / FALLÓ: {exc}")
        print("No se puede continuar si el servidor no responde el health check.")
        sys.exit(1)
    print("-" * 78)


def run_one(n_rows: int) -> dict:
    """Una llamada a /run_python con n_rows. Devuelve métricas de tiempo."""
    payload = {
        "script": REMOTE_SCRIPT,
        "inputs": {"n_rows": n_rows},
        "response_mode": "compact",
    }
    t0 = time.perf_counter()
    try:
        r = requests.post(
            BASE_URL + "/run_python",
            headers=_headers(),
            data=json.dumps(payload),
            timeout=CLIENT_TIMEOUT,
        )
        rtt = time.perf_counter() - t0
    except requests.exceptions.Timeout:
        return {"rtt": CLIENT_TIMEOUT, "status": "TIMEOUT_CLIENTE", "compute": None, "error": f">{CLIENT_TIMEOUT:.0f}s"}
    except Exception as exc:
        return {"rtt": time.perf_counter() - t0, "status": "ERROR_RED", "compute": None, "error": str(exc)[:80]}

    if r.status_code != 200:
        return {"rtt": rtt, "status": f"HTTP_{r.status_code}", "compute": None, "error": r.text[:120]}

    try:
        body = r.json()
    except Exception:
        return {"rtt": rtt, "status": "JSON_INVALIDO", "compute": None, "error": r.text[:120]}

    if "error" in body and body["error"]:
        return {"rtt": rtt, "status": "ERROR_SCRIPT", "compute": None, "error": str(body["error"])[:120]}

    res = body.get("result") or {}
    return {
        "rtt": rtt,
        "status": "OK",
        "compute": res.get("server_compute_s"),
        "error": None,
        "n_grupos": res.get("n_grupos"),
    }


def verdict(rtt: float, status: str) -> str:
    if status != "OK":
        return "✗ FALLO"
    if rtt <= GPT_LIMIT_S:
        return "✓ OK para GPT"
    if rtt <= PROXY_LIMIT_S:
        return "⚠ supera 45s (GPT timeout)"
    return "✗ supera 100s (proxy)"


def main() -> None:
    warmup()
    print(f"{'Filas':>10} │ {'Round-trip':>11} │ {'Cómputo srv':>12} │ {'Red/overhead':>13} │ {'Estado':>14} │ Veredicto vs techos")
    print("─" * 10 + "─┼─" + "─" * 11 + "─┼─" + "─" * 12 + "─┼─" + "─" * 13 + "─┼─" + "─" * 14 + "─┼─" + "─" * 24)

    rows_out = []
    for n in ROWS:
        runs = [run_one(n) for _ in range(REPEAT)]
        oks = [x for x in runs if x["status"] == "OK"]
        chosen = (
            sorted(oks, key=lambda x: x["rtt"])[len(oks) // 2] if oks else runs[-1]
        )
        rtt = chosen["rtt"]
        comp = chosen["compute"]
        overhead = (rtt - comp) if (comp is not None) else None
        v = verdict(rtt, chosen["status"])

        comp_str = f"{comp:.3f}s" if comp is not None else "—"
        over_str = f"{overhead:.3f}s" if overhead is not None else "—"
        print(f"{n:>10,} │ {rtt:>10.3f}s │ {comp_str:>12} │ {over_str:>13} │ {chosen['status']:>14} │ {v}")
        if chosen["error"]:
            print(f"{'':>10}   └─ {chosen['error']}")
        rows_out.append({"n_rows": n, **chosen, "overhead": overhead})

    print("─" * 78)
    # Resumen: ¿a partir de qué volumen un GPT empezaría a fallar?
    cruza_gpt = next((r["n_rows"] for r in rows_out if r["status"] == "OK" and r["rtt"] > GPT_LIMIT_S), None)
    fallos = [r for r in rows_out if r["status"] != "OK"]
    print("RESUMEN")
    if cruza_gpt:
        print(f"  • Un GPT empieza a dar TIMEOUT (~45s) a partir de ~{cruza_gpt:,} filas.")
    else:
        print(f"  • Ningún volumen probado cruzó el techo de 45s del GPT (en este rango).")
    if fallos:
        print(f"  • {len(fallos)} volumen(es) FALLARON en el servidor (posible OOM/timeout): "
              f"{', '.join(f'{r['n_rows']:,}' for r in fallos)}.")
    oks = [r for r in rows_out if r["status"] == "OK" and r["compute"]]
    if len(oks) >= 2:
        # crecimiento aproximado del cómputo por 10x de datos
        print(f"  • Cómputo servidor: {oks[0]['compute']:.3f}s @ {oks[0]['n_rows']:,} filas "
              f"→ {oks[-1]['compute']:.3f}s @ {oks[-1]['n_rows']:,} filas.")
    print("─" * 78)
    print("Interpretación: si el cruce de 45s ocurre con volúmenes que tus clientes")
    print("usan de verdad → el patrón síncrono NO alcanza y conviene el endpoint async")
    print("(job_id + polling). Si todo queda < 45s → el síncrono actual es suficiente.")


if __name__ == "__main__":
    main()
