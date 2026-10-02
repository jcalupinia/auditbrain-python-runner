"""Verificación en Excel real de cualquier procesador (M20).

Uso:  python scripts/verificar_formulas.py <id_procesador> [<id> ...]
Abre el papel de cada escenario (ESCENARIOS del módulo, o su EJEMPLO) en Excel, recalcula y compara cada celda
con fórmula contra el valor que calculó Python. Debe terminar con «DIFERENCIAS: 0».
Requiere Windows con Excel (pywin32).
"""
import importlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import win32com.client  # noqa: E402

from backend.app.aud.niif.procesadores import libro  # noqa: E402
from backend.app.aud.niif.procesadores import datos_cliente  # noqa: E402

FILA0 = 5


def escenarios(m):
    if getattr(m, "ESCENARIOS", None):
        return m.ESCENARIOS
    e = m.EJEMPLO
    return [("ejemplo", e["datasets"], e.get("parametros", {}), e["corte"])]


def comparar(py, xl, fmt):
    if isinstance(xl, float) and xl < -2e9:          # #N/A, #VALUE!, #REF!
        return False
    if py in (None, "") and xl in (None, ""):
        return True
    if isinstance(py, str) and len(py) == 10 and py[4] == "-" and hasattr(xl, "year"):  # fecha ISO vs fecha de Excel
        return f"{xl.year:04d}-{xl.month:02d}-{xl.day:02d}" == py
    if isinstance(py, str):
        return py == xl
    if isinstance(py, bool):
        return bool(xl) == py
    if isinstance(py, (int, float)) and isinstance(xl, (int, float)):
        tol = 1e-6 if (fmt == "p" or abs(py) <= 2) else 0.005
        return abs(py - xl) <= tol
    return False


def verificar(excel, nombre_mod):
    m = importlib.import_module(f"backend.app.aud.niif.procesadores.{nombre_mod}")
    fallas, total = 0, 0
    for esc, datasets, param, corte in escenarios(m):
        res = m.ejecutar(datasets, param, corte)
        res["hojas"] = datos_cliente.con_datos(m, res, datasets)
        reg = {"run": res, "engagement": {"client": "Verificación", "cutoff": corte}, "program": [], "sources": []}
        ruta = os.path.join(tempfile.gettempdir(), f"verif_{nombre_mod}_{esc}.xlsx")
        with open(ruta, "wb") as fh:
            fh.write(libro.xlsx(m.definicion(), reg, [], 1, "VERIFICACION"))
        wb = excel.Workbooks.Open(ruta)
        excel.CalculateFull()
        n = 0
        try:
            for h in res["hojas"]:
                ws = wb.Worksheets(h["name"][:31])
                for i, fila in enumerate(h["rows"] + ([h["total"]] if h.get("total") else [])):
                    for j, c in enumerate(fila):
                        if not isinstance(c, dict):
                            continue
                        n += 1
                        xl = ws.Cells(FILA0 + i, j + 1).Value
                        if not comparar(c["v"], xl, h["cols"][j][1]):
                            fallas += 1
                            col = chr(65 + j) if j < 26 else "A" + chr(65 + j - 26)
                            print(f"[{nombre_mod}/{esc}] {h['name']}!{col}{FILA0 + i}: Python={c['v']!r} Excel={xl!r}  ={c['f'][:110]}")
        finally:
            wb.Close(False)
        total += n
        print(f"[{nombre_mod}/{esc}] fórmulas comparadas: {n}")
    return fallas, total


if __name__ == "__main__":
    mods = sys.argv[1:]
    if not mods:
        sys.exit("Indique el id del procesador.")
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    fallas = 0
    try:
        for md in mods:
            f, t = verificar(excel, md)
            fallas += f
            if t == 0:
                print(f"[{md}] ATENCIÓN: ninguna celda con fórmula; el Excel no sería trazable (M20).")
                fallas += 1
    finally:
        excel.Quit()
    print("DIFERENCIAS:", fallas)
    sys.exit(1 if fallas else 0)
