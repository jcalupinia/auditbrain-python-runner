#!/usr/bin/env python3
"""Verifica que el HTML de Planificación generado por el MOTOR DEL ARTEFACTO
(`procesadores/artefacto_html.py`) sea IDÉNTICO, pestaña por pestaña, al artefacto
de referencia AuditBrain.

Compara el render del módulo contra el artefacto abriendo ambos en un navegador
headless (Playwright) y cotejando el contenido de cada pestaña del motor
(`dashboard, perfil, situacion, resultados, analitico, ratios, materia, riesgos,
notas, control, programa`). La única diferencia admitida es la hora «Generado»
(dinámica) y los nombres de archivo del audit-trail.

Uso:
    python scripts/verificar_artefacto_identico.py --artefacto <AuditBrain_...html> \
        --prior <balance_anterior.xlsx> --current <balance_corte.xlsx> [--eri <eri.xlsx>] \
        [--company "Lansey"] [--prelim] [--node <ruta a node>]

Sin balances, hace el round-trip: extrae el ``var LANSEY`` del propio artefacto,
reconstruye xlsx fieles (con los subtotales «Total …») y verifica identidad. Así
sirve de prueba de regresión del empaquetado de la plantilla.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from backend.app.aud.niif.procesadores import artefacto_html as ah  # noqa: E402

TABS = ["dashboard", "perfil", "situacion", "resultados", "analitico", "ratios",
        "materia", "riesgos", "notas", "control", "programa"]

_COMPARADOR = r"""
import pw from '%(pw)s';
const { chromium } = pw;
const TABS = %(tabs)s;
async function dump(path){
  const b = await chromium.launch({ executablePath: '%(chromium)s' });
  const pg = await b.newPage();
  await pg.goto('file://'+path, { waitUntil:'load', timeout:60000 });
  await pg.waitForTimeout(1200);
  const out = {};
  for (const id of TABS){
    await pg.evaluate(i=>{const x=document.querySelector(`.tab-btn[data-tab="${i}"]`); if(x)x.click();}, id);
    await pg.waitForTimeout(120);
    out[id] = await pg.evaluate(i=>{
      const s=document.getElementById('panel-'+i); if(!s) return null;
      let t=(s.innerText||'').replace(/\s+/g,' ').trim();
      t=t.replace(/Generado\s+[0-9:\/,\.\s apm]+/i,'Generado X');   // hora dinámica
      return {tablas:s.querySelectorAll('table').length, filas:s.querySelectorAll('tr').length, txt:t};
    }, id);
  }
  await b.close();
  return out;
}
const A = await dump(process.argv[2]);
const B = await dump(process.argv[3]);
let dif = 0;
for (const id of TABS){
  const ok = JSON.stringify(A[id]) === JSON.stringify(B[id]);
  if(!ok){ dif++; console.log('DIFERENTE '+id); }
}
console.log('RESULTADO ' + (dif===0 ? 'IDENTICO' : (dif+' pestanas distintas')));
process.exit(dif===0?0:1);
"""


def _xlsx_desde_lansey(obj_periodo: dict) -> bytes:
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "Balance"
    ws.append(["Código", "Cuenta", "Saldo"])
    for cod, nom, val in obj_periodo["rows"]:
        ws.append([cod, nom, None if val is None else val])
    for cod, val in (obj_periodo.get("totals") or {}).items():
        ws.append([None, "Total Cuenta " + str(cod), val])
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()


def _lansey_del_artefacto(artefacto: str) -> dict:
    h = open(artefacto, encoding="utf-8", errors="replace").read()
    i = h.find("var LANSEY={")
    if i < 0:
        raise SystemExit("El artefacto no trae `var LANSEY=` (¿es el OFFLINE con datos de ejemplo?).")
    s = h.find("{", i); d = 0; j = s
    while j < len(h):
        if h[j] == "{":
            d += 1
        elif h[j] == "}":
            d -= 1
            if d == 0:
                break
        j += 1
    return json.loads(h[s:j + 1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artefacto", required=True)
    ap.add_argument("--prior"); ap.add_argument("--current"); ap.add_argument("--eri")
    ap.add_argument("--company", default="Lansey")
    ap.add_argument("--prelim", action="store_true")
    ap.add_argument("--node", default="node")
    ap.add_argument("--pw", default="/opt/node22/lib/node_modules/playwright/index.js")
    ap.add_argument("--chromium", default="/opt/pw-browsers/chromium")
    a = ap.parse_args()

    if a.prior and a.current:
        rb = lambda p: open(p, "rb").read()  # noqa: E731
        files = {"prior": ah.archivo_b64(rb(a.prior), os.path.basename(a.prior)),
                 "current": ah.archivo_b64(rb(a.current), os.path.basename(a.current))}
        if a.eri:
            files["eri"] = ah.archivo_b64(rb(a.eri), os.path.basename(a.eri))
        periodos = {}
    else:
        print("Sin balances: round-trip con el `var LANSEY` del artefacto.")
        o = _lansey_del_artefacto(a.artefacto)
        files = {"prior": ah.archivo_b64(_xlsx_desde_lansey(o["dic2025"]), "balances lansey.xlsx"),
                 "current": ah.archivo_b64(_xlsx_desde_lansey(o["ago2026"]), "balances lansey.xlsx"),
                 "eri": ah.archivo_b64(_xlsx_desde_lansey(o["ago2025"]), "balances lansey.xlsx")}
        periodos = {"periodoAnterior": "Diciembre 2025", "periodoCorte": "Agosto 2026", "periodoEri": "Agosto 2025"}

    engagement = {"client": a.company, **periodos}
    parametros = {"tipoRevision": "Preliminar" if (a.prelim or not (a.prior and a.current)) else "Final"}
    html = ah.render(files, engagement, parametros)

    with tempfile.TemporaryDirectory() as td:
        render_path = os.path.join(td, "render.html")
        open(render_path, "wb").write(html)
        js_path = os.path.join(td, "cmp.mjs")
        open(js_path, "w").write(_COMPARADOR % {"pw": a.pw, "chromium": a.chromium,
                                                "tabs": json.dumps(TABS)})
        r = subprocess.run([a.node, js_path, os.path.abspath(a.artefacto), render_path],
                           capture_output=True, text=True)
        print(r.stdout.strip());
        if r.stderr.strip():
            print(r.stderr.strip(), file=sys.stderr)
        return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
