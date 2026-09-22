"""Papeles de muestra (ejercicio modelo) de las herramientas del catálogo, en los cuatro formatos, con un índice.

Uso: python scripts/papeles_muestra.py <carpeta_salida> [<id> ...]
"""
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.aud.niif import procesadores  # noqa: E402
from backend.app.aud.niif.procesadores import libro  # noqa: E402

salida = sys.argv[1] if len(sys.argv) > 1 else "papeles_muestra"
ids = sys.argv[2:] or sorted(p for p, m in procesadores.PROCESADORES.items() if getattr(m, "RUBRO", None))
os.makedirs(salida, exist_ok=True)
filas = []
for pid in ids:
    m = procesadores.PROCESADORES[pid]
    esc = getattr(m, "ESCENARIOS", None) or [("ejemplo", m.EJEMPLO["datasets"], m.EJEMPLO.get("parametros", {}), m.EJEMPLO["corte"])]
    d = m.definicion()
    for nombre, datasets, param, corte in esc:
        res = m.ejecutar(datasets, param, corte)
        res["hojas"] = m.hojas(res)
        marco = param.get("_marco") or d["frameworks"][0]
        reg = {"run": res, "program": [{**x, "reference": x.get("source", "")} for x in d["program"]], "sources": [],
               "engagement": {"client": "Cliente de muestra S.A.", "ruc": "1790000000001", "cutoff": corte, "year": corte[:4],
                              "framework": marco, "firm": "AuditConsulting Auditores Cía. Ltda.",
                              "preparer": "Ejercicio modelo", "reviewer": "Pendiente"}}
        base = f"{pid}__{nombre}"
        for ext in ("xlsx", "docx", "pptx", "html"):
            with open(os.path.join(salida, f"{base}.{ext}"), "wb") as fh:
                fh.write(getattr(libro, ext)(d, reg, [], 1, "MUESTRA"))
        prim = res["primary"]
        filas.append((m.RUBRO, d["name"], nombre, marco, res["labels"].get(prim, prim), res["totals"].get(prim), len(res["exceptions"]), base))
        print(pid, nombre, res["totals"].get(prim))

cuerpo = "".join(
    f"<tr><td>{html.escape(r)}</td><td>{html.escape(n)}</td><td>{html.escape(e)}</td><td>{html.escape(mc)}</td>"
    f"<td>{html.escape(str(lp))}</td><td style='text-align:right'>{html.escape(str(v))}</td><td style='text-align:right'>{x}</td>"
    f"<td><a href='{b}.xlsx'>Excel</a> · <a href='{b}.html'>HTML</a> · <a href='{b}.docx'>Word</a> · <a href='{b}.pptx'>PowerPoint</a></td></tr>"
    for r, n, e, mc, lp, v, x, b in filas)
with open(os.path.join(salida, "INDICE.html"), "w", encoding="utf-8") as fh:
    fh.write("<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Papeles de muestra</title><style>"
             "body{font-family:Calibri,Arial,sans-serif;margin:24px;color:#0A2342}table{border-collapse:collapse;width:100%;font-size:13px}"
             "th{background:#0A2342;color:#fff;padding:6px}td{border:1px solid #B7C0CC;padding:5px}</style></head><body>"
             "<h1>Herramientas del catálogo · papeles de muestra (ejercicio modelo)</h1>"
             "<table><thead><tr><th>Rubro</th><th>Herramienta</th><th>Escenario</th><th>Marco</th><th>Resultado principal</th>"
             "<th>Importe</th><th>Problemas</th><th>Descargas</th></tr></thead><tbody>" + cuerpo + "</tbody></table></body></html>")
print("índice:", os.path.join(salida, "INDICE.html"))
