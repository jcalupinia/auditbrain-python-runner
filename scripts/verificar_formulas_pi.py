"""Abre el papel de pérdidas incurridas en Excel real (Windows con Excel), recalcula y
compara cada fórmula con el valor que calculó Python.

Uso: python scripts/verificar_formulas_pi.py  -> debe terminar con «DIFERENCIAS: 0».
Correrlo tras cualquier cambio en las cédulas de perdidas_incurridas_s11.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import win32com.client  # noqa: E402

from backend.app.aud.niif.procesadores import libro, perdidas_incurridas_s11 as pi  # noqa: E402

SP = os.environ.get("TEMP", ".")
f = lambda id, c, e, v, s: {"id": id, "cliente": c, "emision": e, "vence": v, "saldo": s, "_row": 2}
DATOS = {
    "a1": [f("101", "Comercial Andina", "2023-06-01", "2023-07-15", "1200"), f("090", "Importadora Costa", "2023-05-01", "2023-06-15", "900"),
           f("070", "Ferretería Norte", "2023-11-10", "2023-12-10", "300")],
    "a2": [f("101", "Comercial Andina", "2024-07-01", "2024-08-15", "1000"), f("110", "Ferretería Norte", "2024-12-15", "2025-01-14", "500"),
           f("090", "Importadora Costa", "2023-05-01", "2023-06-15", "750"), f("120", "Distribuidora Sierra", "2024-10-01", "2024-11-10", "600")],
    "a3": [f("101", "Comercial Andina", "2024-07-01", "2024-08-15", "400"), f("130", "Distribuidora Sierra", "2025-07-01", "2025-08-15", "2000"),
           f("150", "Ferretería Norte", "2025-12-01", "2026-01-15", "1500"), f("090", "Importadora Costa", "2023-05-01", "2023-06-15", "750"),
           f("120", "Distribuidora Sierra", "2024-10-01", "2024-11-10", "250"), f("160", "Comercial Andina", "2025-11-01", "2025-12-01", "-35.50"),
           f("170", "Nuevo Cliente", "2025-10-01", "2025-11-05", "980.40")],
    "provision": [{"id": "101", "cliente": "Comercial Andina", "provision": "200", "diferido": "50"},
                  {"id": "080", "cliente": "Cliente Retirado", "provision": "100", "diferido": "25"},
                  {"id": "075", "cliente": "Ferretería Norte", "provision": "40"}],
    "movimiento": [{"id": "2023", "inicial": "0", "gasto": "150", "castigos": "0", "recuperaciones": "0"},
                   {"id": "2024", "gasto": "190", "castigos": "40", "recuperaciones": "0"},
                   {"id": "2025", "gasto": "0", "castigos": "0", "recuperaciones": "0"}],
}
ESCENARIOS = {
    "base": {},
    "con_parametros": {"tasaDesc": 8, "plazoBase": 18, "tasas": {"t60": 15, "t30": 5}, "provFiscalAnt": 120, "dtaIniManual": 60},
}

excel = win32com.client.DispatchEx("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
fallas = 0
try:
    for nombre, param in ESCENARIOS.items():
        res = pi.ejecutar(DATOS, param, "2025-12-31")
        res["hojas"] = pi.hojas(res)
        reg = {"run": res, "engagement": {"client": "Prueba", "cutoff": "2025-12-31"}, "program": [], "sources": []}
        ruta = os.path.join(SP, f"verif_pi_{nombre}.xlsx")
        open(ruta, "wb").write(libro.xlsx(pi.definicion(), reg, [], 1, "PRUEBA"))
        wb = excel.Workbooks.Open(ruta)
        excel.CalculateFull()
        n = 0
        for h in res["hojas"]:
            ws = wb.Worksheets(h["name"])
            filas = h["rows"] + ([h["total"]] if h["total"] else [])
            for i, fila in enumerate(filas):
                for j, c in enumerate(fila):
                    if not isinstance(c, dict):
                        continue
                    n += 1
                    xl = ws.Cells(pi.FILA0 + i, j + 1).Value
                    py = c["v"]
                    if isinstance(xl, float) and xl < -2e9:  # error de Excel (#N/A, #VALUE!)
                        xl = f"ERROR {xl}"
                    ok = (py in (None, "") and xl in (None, "")) or (isinstance(py, str) and py == xl) or \
                         (isinstance(py, (int, float)) and isinstance(xl, (int, float)) and abs(py - xl) <= (1e-6 if abs(py) <= 1 and h["cols"][j][1] == "p" else 0.005))
                    if not ok:
                        fallas += 1
                        print(f"[{nombre}] {h['name']}!{chr(65 + j)}{pi.FILA0 + i}: Python={py!r} Excel={xl!r}  ={c['f'][:90]}")
        wb.Close(False)
        print(f"[{nombre}] fórmulas comparadas: {n}; pérdida {res['totals']['perdida']}, ajuste {res['totals']['ajuste']}")
finally:
    excel.Quit()
print("DIFERENCIAS:", fallas)
