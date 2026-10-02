"""Verificador de las explicaciones HUMANAS de «Cómo se calcula esta hoja» y del
PANEL (KPIs y gráficos del dashboard) de cada herramienta NIIF.

Recorre TODOS los escenarios de cada procesador (EJEMPLO, ESCENARIOS y, en
pérdidas incurridas, el ejemplo realista de ``ejemplos_pi``), porque algunas
cédulas tienen columnas que dependen de los datos. Para cada columna calculada
exige una explicación escrita en la definición de la cédula
(``hoja(..., explica={"Columna": "texto"})``) que:

- no sea la plantilla genérica («… se obtiene con la fórmula indicada …»);
- tenga al menos 40 caracteres (una frase completa, no un rótulo);
- no esté repetida literalmente en otra columna de la misma cédula.

Y exige que ``PANEL`` resuelva población, recalculado, registrado, composición y
distribución con números.

Uso:
    python scripts/verificar_explicaciones.py                  # las 20 herramientas
    python scripts/verificar_explicaciones.py cxc_cartera       # solo esa
    python scripts/verificar_explicaciones.py --detalle cxc_cartera   # muestra fórmula y ejemplo de lo que falta
Sale con código 1 si algo falta.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.aud.niif.procesadores import PROCESADORES, graficos, libro  # noqa: E402
from backend.app.aud.niif.procesadores import datos_cliente  # noqa: E402

MIN_LARGO = 40


def escenarios(mod):
    out = []
    if getattr(mod, "__name__", "").endswith("perdidas_incurridas_s11"):
        from backend.app.aud.niif import ejemplos_pi
        e = ejemplos_pi.ejercicio_modelo()
        out.append(("ejemplo realista", e["datasets"], e["parametros"], e["corte"]))
    E = getattr(mod, "EJEMPLO", None)
    if E and E.get("datasets"):
        out.append(("EJEMPLO", E["datasets"], E.get("parametros", {}), E["corte"]))
    for i, esc in enumerate(getattr(mod, "ESCENARIOS", None) or []):
        nombre, ds, par, corte = esc
        out.append((f"ESCENARIO {i}: {nombre}", ds, par, corte))
    return out


def revisar(pid: str, detalle: bool = False) -> list[str]:
    mod = PROCESADORES[pid]
    problemas: list[str] = []
    vistos = set()
    panel_ok = False
    for nombre_esc, ds, par, corte in escenarios(mod):
        try:
            run = mod.ejecutar(ds, par, corte)
            hojas = datos_cliente.con_datos(mod, run, ds)
        except Exception as e:  # noqa: BLE001 — un escenario de error intencional no aporta columnas
            continue
        for h in hojas:
            textos = {}
            for b in libro.como_se_calcula(h, hojas):
                clave = (h["name"], b["columna"])
                exp = b["explicacion"]
                falla = None
                if not b.get("escrita"):
                    falla = "SIN EXPLICACIÓN"
                elif libro.PLANTILLA_GENERICA in exp:
                    falla = "PLANTILLA GENÉRICA"
                elif len(exp.strip()) < MIN_LARGO:
                    falla = f"MUY CORTA (<{MIN_LARGO})"
                elif exp in textos and textos[exp] != b["columna"]:
                    falla = f"REPETIDA (igual que «{textos[exp]}»)"
                textos.setdefault(exp, b["columna"])
                if falla and clave not in vistos:
                    vistos.add(clave)
                    linea = f"  {falla}: [{h['name']}] «{b['columna']}»"
                    if detalle:
                        linea += f"\n      fórmula: {b['formula']}\n      ejemplo: {b['ejemplo']}"
                    problemas.append(linea)
        if not panel_ok:
            p = graficos.panel(mod, run, hojas)
            if p["faltan"]:
                problemas.append(f"  PANEL no resuelve: {', '.join(p['faltan'])} (escenario {nombre_esc})")
            panel_ok = True
    return problemas


def main():
    detalle = "--detalle" in sys.argv
    pids = [a for a in sys.argv[1:] if not a.startswith("--")] or list(PROCESADORES)
    total = 0
    for pid in pids:
        pr = revisar(pid, detalle)
        total += len(pr)
        print(f"{'OK ' if not pr else 'FALTA'} {pid}: {len(pr)} pendiente(s)")
        for linea in pr:
            print(linea)
    print("RESULTADO:", "OK" if total == 0 else f"{total} pendiente(s)")
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
