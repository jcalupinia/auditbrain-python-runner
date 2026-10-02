"""Papeles de muestra (ejercicio modelo) de las 20 herramientas NIIF (18 de catálogo
+ pérdidas incurridas + PCE) en todos los formatos, con un índice (INDICE.html).

Los datos son el ejemplo REALISTA del manifiesto: los mismos archivos que el
cliente descarga con «↓ Ejemplo», leídos con el lector del ciclo
(``ejercicio_modelo.escenario`` → ``ejemplos_manifiesto``). En pérdidas incurridas
y PCE: 6 clientes y 3 ejercicios.

Uso: python scripts/papeles_muestra.py <carpeta_salida> [<id> ...]
"""
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.aud.niif import ejercicio_modelo, procesadores  # noqa: E402
from backend.app.aud.niif.procesadores import libro  # noqa: E402

FORMATOS = (("xlsx", "xlsx", "Excel"), ("html", "html", "HTML"), ("pdf", "pdf", "PDF"), ("docx", "docx", "Word"),
            ("pptx", "pptx", "PowerPoint"), ("zip", "csv_zip", "CSV"))

salida = sys.argv[1] if len(sys.argv) > 1 else "papeles_muestra"
ids = sys.argv[2:] or list(procesadores.PROCESADORES)
os.makedirs(salida, exist_ok=True)
filas = []
for pid in ids:
    m = procesadores.PROCESADORES[pid]
    d = m.definicion()
    datasets, param, corte = ejercicio_modelo.escenario(m)
    reg = ejercicio_modelo._reg(d, m, datasets, param, corte)
    res = reg["run"]
    base = f"{pid}__ejemplo_realista"
    hechos = []
    for ext, fn, etq in FORMATOS:
        try:
            contenido = getattr(libro, fn)(d, reg, [], 1, "MUESTRA")
        except libro.PDFNoDisponible:
            continue  # sin WeasyPrint en este entorno: el índice no enlaza el PDF
        with open(os.path.join(salida, f"{base}.{ext}"), "wb") as fh:
            fh.write(contenido)
        hechos.append((ext, etq))
    prim = res["primary"]
    poblacion = ", ".join(f"{k}: {len(v)}" for k, v in datasets.items())
    filas.append((getattr(m, "RUBRO", "") or "DETERIORO", d["name"], reg["engagement"]["framework"],
                  res["labels"].get(prim, prim), libro._celda({"v": res["totals"].get(prim)}, "n"),
                  len(res["exceptions"]), poblacion, base, hechos))
    print(pid, res["totals"].get(prim), poblacion)

cuerpo = "".join(
    f"<tr><td>{html.escape(r)}</td><td>{html.escape(n)}</td><td>{html.escape(mc)}</td><td>{html.escape(str(lp))}</td>"
    f"<td class='num'>{v}</td><td class='num'>{x}</td><td>{html.escape(pob)}</td><td>"
    + " · ".join(f"<a href='{b}.{ext}'>{etq}</a>" for ext, etq in hechos) + "</td></tr>"
    for r, n, mc, lp, v, x, pob, b, hechos in filas)
with open(os.path.join(salida, "INDICE.html"), "w", encoding="utf-8") as fh:
    fh.write("<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Papeles de muestra</title><style>"
             "body{font-family:'Segoe UI',Calibri,Arial,sans-serif;margin:24px;color:#0A2342;background:#F4F6F9}"
             "h1{font-size:20px}table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}"
             "th{background:#0A2342;color:#fff;padding:7px;text-align:left}td{border-bottom:1px solid #E3E8EF;padding:6px}"
             "td.num{text-align:right;font-variant-numeric:tabular-nums}a{color:#0D7377}</style></head><body>"
             "<h1>Herramientas NIIF · papeles de muestra con el ejemplo realista del manifiesto</h1>"
             "<table><thead><tr><th>Rubro</th><th>Herramienta</th><th>Marco</th><th>Resultado principal</th>"
             "<th>Importe</th><th>Problemas</th><th>Población cargada</th><th>Descargas</th></tr></thead><tbody>"
             + cuerpo + "</tbody></table></body></html>")
print("índice:", os.path.join(salida, "INDICE.html"))
