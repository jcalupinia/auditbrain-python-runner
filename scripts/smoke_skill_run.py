#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_skill_run.py — Prueba real del endpoint /api/v1/skill_run (el "cerebro").

Confirma, contra producción, que el endpoint que pegarás en los GPTs responde:
- 200 + output  -> el cerebro funciona (LLM con prompt oficial server-side).
- 401           -> la X-API-Key falta o es incorrecta.
- 503           -> el endpoint vive, pero NO hay proveedor LLM configurado en Render
                   (faltan GEMINI/GROQ/ANTHROPIC keys). Es un error honesto del server.

USO (Windows PowerShell):
    cd "C:\\Users\\jcalu\\Desktop\\PROYECTOS CLAUDE\\auditbrain-python-runner"
    $env:AUDITBRAIN_API_KEY = "<TU_API_KEY>"
    python scripts/smoke_skill_run.py

Opcionales:
    $env:BENCH_URL = "https://auditbrain-python-runner.onrender.com"  (default)

NO imprime ni guarda la API key.
"""
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("Falta 'requests'. Instala con:  pip install requests")

BASE_URL = os.getenv("BENCH_URL", "https://auditbrain-python-runner.onrender.com").rstrip("/")
API_KEY = os.getenv("AUDITBRAIN_API_KEY", "")

# Caso de prueba: módulo AUD, tarea breve para que el LLM responda corto/rápido.
PAYLOAD = {
    "module_code": "AUD",
    "input": "En 3 vinetas breves, explica que es la materialidad en una auditoria financiera.",
}


def main() -> None:
    print(f"→ Servidor: {BASE_URL}")
    print(f"→ Auth:     {'X-API-Key presente' if API_KEY else 'SIN key (esperado 401 si la auth esta activa)'}")
    print(f"→ Caso:     module_code=AUD · input='{PAYLOAD['input'][:50]}...'")
    print("-" * 74)

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    t0 = time.perf_counter()
    try:
        r = requests.post(
            BASE_URL + "/api/v1/skill_run",
            headers=headers,
            data=json.dumps(PAYLOAD),
            timeout=60,
        )
    except Exception as exc:
        sys.exit(f"ERROR de red: {exc}")
    rtt = time.perf_counter() - t0

    print(f"HTTP {r.status_code}  ·  {rtt:.2f}s")
    print("-" * 74)

    if r.status_code == 200:
        body = r.json()
        print("✓ EL CEREBRO RESPONDE. Resumen:")
        print(f"  skill aplicada : {body.get('skill')}  ({body.get('skill_name')})")
        print(f"  modelo LLM     : {body.get('model')}")
        print("  output:")
        out = body.get("output", "")
        for line in out.splitlines():
            print(f"    {line}")
        print("-" * 74)
        print("RESULTADO: el endpoint skill_run esta LISTO para pegar en los GPTs.")
    elif r.status_code == 401:
        print("✗ 401: la X-API-Key falta o no coincide con AUDITBRAIN_API_KEY en Render.")
        print("  Revisa que pegaste la key correcta. (El endpoint EXISTE y la auth funciona.)")
    elif r.status_code == 503:
        print("✗ 503: el endpoint vive, pero NO hay proveedor LLM disponible en el server.")
        print("  Configura en Render al menos una: GEMINI_API_KEY / GROQ_API_KEY / ANTHROPIC_API_KEY.")
        try:
            print(f"  detalle: {r.json().get('detail')}")
        except Exception:
            pass
    else:
        print(f"✗ Respuesta inesperada {r.status_code}:")
        print(f"  {r.text[:300]}")


if __name__ == "__main__":
    main()
