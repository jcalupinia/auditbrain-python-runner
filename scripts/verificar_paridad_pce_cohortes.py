"""Verificación de paridad del motor de PCE por cohortes (AUD-ECL-01).

Corre el procesador del repo (`pce_cohortes_niif9`) y el motor JS del artefacto de
referencia (`scripts/verificar_paridad_pce_cohortes.mjs`, réplica fiel) sobre el
MISMO dataset y compara dígito a dígito las cifras del recálculo: PCE total,
exposición anclada, provisión registrada, tasa de castigo, trazabilidad y, celda
por celda, exposición, tasa observada, tasa aplicada y pérdida esperada.

Uso:  python scripts/verificar_paridad_pce_cohortes.py
Debe imprimir «DIFERENCIAS: 0».
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend.app.aud.niif.procesadores import pce_cohortes_niif9 as m  # noqa: E402

MJS = RAIZ / "scripts" / "verificar_paridad_pce_cohortes.mjs"


def _fixture(datasets, params, corte):
    def rows(ds):
        return [{"doc": r["id"], "cliente": r.get("cliente", ""), "tipo": r.get("tipo", ""),
                 "vence": r["vence"], "saldo": r["saldo"]} for r in ds]
    prov = [{"saldo_anterior": r.get("saldo_anterior"), "saldo_actual": r.get("saldo_actual")}
            for r in (datasets.get("provision") or [])]
    may = {suf: [{"constitucion": r.get("constitucion"), "reversion": r.get("reversion"), "castigos": r.get("castigos")}
                 for r in (datasets.get(f"mayor_{suf}") or [])] for suf in ("t2", "t1", "t")}
    return {"corte": corte, "params": params, "cartera_t2": rows(datasets["cartera_t2"]),
            "cartera_t1": rows(datasets["cartera_t1"]), "cartera_t": rows(datasets["cartera_t"]),
            "provision": prov, "mayor_t2": may["t2"], "mayor_t1": may["t1"], "mayor_t": may["t"]}


def _py(datasets, params, corte):
    r = m.ejecutar(datasets, params, corte)
    d = r["detalle"]
    cells = {f'{mm["seg"]}|{mm["banda"]}': mm for mm in d["matriz"]}
    return {
        "PCE": float(r["totals"]["pce"]), "totExp": d["totExp"], "provReg": d["provReg"],
        "tasaCastigo": d["tasaCastigo"], "traza": d["traza"],
        "cells": {k: {"e": v["exp"], "tasaObs": v["tasaObs"], "tasaApl": v["tasaApl"], "pce": v["pce"]}
                  for k, v in cells.items()},
    }


def _js(fixture):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(fixture, f)
        ruta = f.name
    out = subprocess.run(["node", str(MJS), ruta], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"node falló: {out.stderr}")
    r = json.loads(out.stdout)
    r["cells"] = {f'{c["s"]}|{c["b"]}': c for c in r["cells"]}
    return r


def _cmp(nombre, a, b, dec=2):
    if a is None and b is None:
        return 0
    if a is None or b is None:
        print(f"  ✗ {nombre}: py={a} js={b}")
        return 1
    if round(float(a), dec) != round(float(b), dec):
        print(f"  ✗ {nombre}: py={a} js={b}")
        return 1
    return 0


ESCENARIOS = [
    ("EJEMPLO (anclaje factor 1, sin desdoblar)", m.EJEMPLO["datasets"], m.EJEMPLO["parametros"], m.EJEMPLO["corte"]),
    ("Desdoblamiento + anclaje ≠ 1 + prospectivo", m.EJEMPLO["datasets"],
     {**m.EJEMPLO["parametros"], "desdoblar": "Sí", "umbral": 730, "eNR_t": 12000, "eR_t": 3000,
      "fT": 1.1, "fR": 1.2}, m.EJEMPLO["corte"]),
]


def main() -> int:
    difs = 0
    for nombre, ds, p, corte in ESCENARIOS:
        print(f"· {nombre}")
        py, js = _py(ds, p, corte), _js(_fixture(ds, p, corte))
        for k in ("PCE", "totExp", "provReg"):
            difs += _cmp(k, py[k], js[k], 2)
        for k in ("tasaCastigo", "traza"):
            difs += _cmp(k, py[k], js[k], 6)
        claves = set(py["cells"]) | set(js["cells"])
        for c in sorted(claves):
            pc, jc = py["cells"].get(c), js["cells"].get(c)
            if pc is None or jc is None:
                print(f"  ✗ celda {c} solo en {'py' if jc is None else 'js'}")
                difs += 1
                continue
            difs += _cmp(f"{c} · exp", pc["e"], jc["e"], 2)
            difs += _cmp(f"{c} · tasaObs", pc["tasaObs"], jc["tasaObs"], 6)
            difs += _cmp(f"{c} · tasaApl", pc["tasaApl"], jc["tasaApl"], 6)
            difs += _cmp(f"{c} · pce", pc["pce"], jc["pce"], 2)
    print(f"\nDIFERENCIAS: {difs}")
    return 1 if difs else 0


if __name__ == "__main__":
    sys.exit(main())
