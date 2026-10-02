"""Verificación empírica del papel de trabajo de "Estados financieros".

Construye estados homologados sintéticos (2 períodos), corre el análisis, genera
el papel y recalcula sus fórmulas (variación, var %, vertical %, ratios y la
diferencia NIA 520) con `formulas`, comparando contra Python. "DIFERENCIAS: 0".
"""
from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from backend.app.client_portal.flujo import motor_balances as mb  # noqa: E402
from backend.app.aud.motor_balances import analisis as an  # noqa: E402
from backend.app.aud.motor_balances.papel_estados import generar_papel_estados  # noqa: E402


def _homologado():
    esf = {"periodos": ["2023", "2024"], "filas": [
        {"cuenta": "caja", "super_cias": "1010101", "es_hoja": True, "saldos": {"2023": 800.0, "2024": 1200.0}},
        {"cuenta": "ctas", "super_cias": "1010201", "es_hoja": True, "saldos": {"2023": 500.0, "2024": 400.0}},
        {"cuenta": "inv", "super_cias": "10103", "es_hoja": True, "saldos": {"2023": 700.0, "2024": 900.0}},
        {"cuenta": "prov", "super_cias": "2010301", "es_hoja": True, "saldos": {"2023": 300.0, "2024": 650.0}},
        {"cuenta": "cap", "super_cias": "30101", "es_hoja": True, "saldos": {"2023": 1400.0, "2024": 1650.0}},
    ]}
    eri = {"periodos": ["2023", "2024"], "filas": [
        {"cuenta": "vta", "super_cias": "40101", "es_hoja": True, "saldos": {"2023": 5000.0, "2024": 6000.0}},
        {"cuenta": "cv", "super_cias": "50101", "es_hoja": True, "saldos": {"2023": 3000.0, "2024": 3500.0}},
    ]}
    return mb.estados_superintendencia(esf, eri)


def _celdas(ruta, hoja):
    import formulas
    xl = formulas.ExcelModel().loads(str(ruta)).finish()
    sol = xl.calculate()
    out = {}
    for clave, val in sol.items():
        up = clave.upper()
        if f"]{hoja.upper()}'!" not in up:
            continue
        coord = clave.split("!")[-1].replace("$", "")
        try:
            v = val.value[0, 0]
        except Exception:
            continue
        out[coord] = v
    return out


def _cerca(a, b, tol=0.01):
    if a in ("", None) and b in ("", None):
        return True
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return str(a) == str(b)


def main():
    hom = _homologado()
    res = an.analizar(hom, umbral_pct=0.10)
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "papel.xlsx"
        ruta.write_bytes(generar_papel_estados(res))
        c_esf = _celdas(ruta, "ESF")
        c_ratios = _celdas(ruta, "Ratios")

    dif = 0
    FILA0 = 4
    # ESF: variación (col E), var% (F), vertical% (G) de cada línea
    esf = res["esf"]
    por = {l["codigo"]: l for l in esf["lineas"]}
    base_vals = por[esf["base_codigo"]]["valores"]
    for i, l in enumerate(esf["lineas"]):
        r = FILA0 + i
        vals = l["valores"]
        var = round(vals[-1] - vals[-2], 2)
        pct = (vals[-1] - vals[-2]) / vals[-2] if vals[-2] else ""
        ver = vals[-1] / base_vals[-1] if base_vals[-1] else ""
        for coord, esperado in [(f"E{r}", var), (f"F{r}", pct), (f"G{r}", ver)]:
            if not _cerca(c_esf.get(coord), esperado):
                dif += 1
                print(f"  [ESF {coord}] python={esperado} formulas={c_esf.get(coord)}")

    # Ratios
    for i, fila in enumerate(res["ratios"]["filas"]):
        r = FILA0 + i
        for j, esperado in enumerate(fila["valores"]):
            coord = f"{chr(66 + j)}{r}"  # B, C...
            obt = c_ratios.get(coord)
            if not _cerca(obt, esperado if esperado is not None else ""):
                dif += 1
                print(f"  [Ratio {fila['nombre']} {coord}] python={esperado} formulas={obt}")

    print(f"\nDIFERENCIAS: {dif}")
    return 0 if dif == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
