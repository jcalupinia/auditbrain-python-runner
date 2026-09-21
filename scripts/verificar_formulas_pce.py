"""Abre el papel de pérdida crediticia esperada (NIIF 9 simplificada) en Excel real (Windows con Excel), recalcula y
compara cada fórmula con el valor que calculó Python.

Uso: python scripts/verificar_formulas_pce.py  -> debe terminar con «DIFERENCIAS: 0».
Correrlo tras cualquier cambio en las cédulas de pce_simplificada_niif9.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import win32com.client  # noqa: E402

from backend.app.aud.niif.procesadores import libro, pce_simplificada_niif9 as pce  # noqa: E402

SP = os.environ.get("TEMP", ".")
f = pce._ej
DATOS = {
    "anterior": [f("A1", "Comercial Andina", "2024-12-10", "1000", segmento="Mayorista"), f("A2", "Importadora Costa", "2024-11-01", "800", segmento="Mayorista"),
                 f("A3", "Ferretería Norte", "2024-09-15", "600", segmento="Minorista"), f("A4", "Distribuidora Sierra", "2024-05-01", "400", segmento="Minorista"),
                 f("A5", "Nuevo Sur", "2025-01-20", "900", segmento="Minorista"), f("A6", "Cliente Uno", "2024-12-28", "-50", segmento="Mayorista")],
    "actual": [f("A2", "Importadora Costa", "2024-11-01", "300", segmento="Mayorista"), f("A4", "Distribuidora Sierra", "2024-05-01", "400", segmento="Minorista"),
               f("B1", "Comercial Andina", "2025-12-15", "2500", segmento="Mayorista"), f("B2", "Ferretería Norte", "2025-10-20", "1200", segmento="Minorista"),
               f("B3", "Nuevo Sur", "2026-01-30", "1800", segmento="Minorista"), f("B4", "Importadora Costa", "2025-08-01", "950.75", segmento="Mayorista"),
               f("B5", "Cliente Dudoso", "2025-06-30", "700", segmento="Minorista", tasa_individual="80"), f("B6", "Cliente Uno", "2025-12-20", "-120", segmento="Mayorista")],
    "castigos": [{"id": "A3", "cliente": "Ferretería Norte", "importe": "250", "_row": 2}, {"id": "a1", "cliente": "Comercial Andina", "importe": "100", "_row": 3}],
}
ESCENARIOS = {
    "base": {"escBasePeso": 60, "escBaseAjuste": 0, "escOptPeso": 20, "escOptAjuste": -10, "escPesPeso": 20, "escPesAjuste": 25,
             "tasas": {"t60": 3, "t90": 6, "t180": 25}, "provisionRegistrada": 500, "provisionInicial": 380},
    "descuento": {"tasaDesc": 9, "plazoBase": 8, "tasas": {"t60": 3, "t90": 6, "t180": 25, "tmax": 100, "t30": 1.5},
                  "provisionRegistrada": 900, "provisionInicial": 1200, "provFiscalAnt": 150, "pctDeducible": 2},
}

excel = win32com.client.DispatchEx("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
fallas = 0
try:
    for nombre, param in ESCENARIOS.items():
        res = pce.ejecutar(DATOS, param, "2025-12-31")
        res["hojas"] = pce.hojas(res)
        reg = {"run": res, "engagement": {"client": "Prueba", "cutoff": "2025-12-31"}, "program": [], "sources": []}
        ruta = os.path.join(SP, f"verif_pce_{nombre}.xlsx")
        open(ruta, "wb").write(libro.xlsx(pce.definicion(), reg, [], 1, "PRUEBA"))
        wb = excel.Workbooks.Open(ruta)
        excel.CalculateFull()
        n = 0
        for h in res["hojas"]:
            ws = wb.Worksheets(h["name"])
            for i, fila in enumerate(h["rows"] + ([h["total"]] if h["total"] else [])):
                for j, c in enumerate(fila):
                    if not isinstance(c, dict):
                        continue
                    n += 1
                    xl, py = ws.Cells(pce.FILA0 + i, j + 1).Value, c["v"]
                    if isinstance(xl, float) and xl < -2e9:
                        xl = f"ERROR {xl}"
                    ok = (py in (None, "") and xl in (None, "")) or (isinstance(py, str) and py == xl) or \
                         (isinstance(py, (int, float)) and isinstance(xl, (int, float)) and abs(py - xl) <= (1e-6 if abs(py) <= 2 else 0.005))
                    if not ok:
                        fallas += 1
                        print(f"[{nombre}] {h['name']}!{chr(65 + j)}{pce.FILA0 + i}: Python={py!r} Excel={xl!r}  ={c['f'][:100]}")
        wb.Close(False)
        print(f"[{nombre}] fórmulas comparadas: {n}; pce {res['totals']['pce']}, ajuste {res['totals']['ajuste']}, problemas {[e['code'] for e in res['exceptions']]}")
finally:
    excel.Quit()
print("DIFERENCIAS:", fallas)
