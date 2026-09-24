"""Verifica que el importe de cada problema sea una fórmula a su celda de origen.

Uso:  python scripts/verificar_problemas_enlazados.py [<id_procesador> ...] [--detalle]

Recorre, para cada procesador, el ejercicio modelo, el EJEMPLO y los ESCENARIOS del
módulo; enlaza la hoja de problemas con ``REF_PROBLEMAS`` y lista los importes que
quedarían como valor pegado. Con ``--detalle`` muestra además a qué celda remite
cada problema, para revisar que el origen tenga sentido contable.
Debe terminar con «PENDIENTES: 0».
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.aud.niif import ejercicio_modelo as em  # noqa: E402
from backend.app.aud.niif.procesadores import PROCESADORES, problemas  # noqa: E402


def escenarios(pid, mod):
    ds, par, corte = em.escenario(mod)
    yield "modelo", ds, par, corte
    e = getattr(mod, "EJEMPLO", None)
    if e:
        yield "ejemplo", e["datasets"], e.get("parametros", {}), e["corte"]
    for esc in getattr(mod, "ESCENARIOS", None) or []:
        nombre, dsx, parx, cx = esc
        yield f"esc:{nombre}", dsx, parx, cx


def main(ids, detalle):
    total = 0
    for pid in ids:
        mod = PROCESADORES[pid]
        refs = dict(getattr(mod, "REF_PROBLEMAS", {}) or {})
        for nombre, ds, par, corte in escenarios(pid, mod):
            run = mod.ejecutar(ds, par, corte)
            hojas, pend = problemas.enlazar(mod.hojas(run), refs, run.get("exceptions"))
            total += len(pend)
            print(f"[{pid}/{nombre}] pendientes: {len(pend)}")
            for p in pend:
                print(f"    PENDIENTE {p['codigo']} {p['importe']:,.2f} ({p['motivo']})")
            if detalle:
                for h in hojas:
                    if problemas.es_hoja_problemas(h):
                        for f in h["rows"]:
                            if isinstance(f[2], dict):
                                print(f"    {f[0]:34} {f[2]['v']!s:>14}  ={f[2]['f']}")
    print("PENDIENTES:", total)
    return total


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(1 if main(args or list(PROCESADORES), "--detalle" in sys.argv) else 0)
