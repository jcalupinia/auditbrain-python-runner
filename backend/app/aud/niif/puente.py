"""Puente planificación → pruebas del piloto.

La planificación NIA ya decide, para cada cuenta principal, si se revisa y con qué
herramienta del catálogo (``planificacion_nia.HERRAMIENTAS`` y el campo ``herr`` de
``run["detalle"]["revisar"]``). Este módulo traduce esa decisión a la lista ordenada
de **pruebas del piloto** a ejecutar: agrupa las cuentas a revisar por herramienta,
resuelve el id del procesador del piloto y adjunta los riesgos y el saldo que
justifican cada prueba.

No inventa nada: solo reordena lo que la planificación ya calculó. El id del piloto
se DERIVA en runtime (no hay lista paralela hardcoded, prohibida por el CLAUDE.md):
se cruza el nombre de la herramienta de la planificación con el ``name`` de cada
procesador. La regla la mantiene vivo ``tests/test_aud_puente.py``.
"""
from __future__ import annotations

from backend.app.aud.niif import procesadores
from backend.app.aud.niif.procesadores import planificacion_nia as pn


def indice_por_herramienta() -> dict[str, str]:
    """{nombre de herramienta de la planificación: id de la prueba del piloto}.

    Se resuelve por contención de nombre (uno es prefijo del otro). Las áreas sin
    prueba del catálogo del piloto (p. ej. «Asientos de diario» → motor analítico)
    quedan fuera del índice a propósito."""
    nombres = {pid: mod.definicion().get("name", "") for pid, mod in procesadores.PROCESADORES.items()}
    idx: dict[str, str] = {}
    for herr in pn.HERRAMIENTAS.values():
        pid = next((p for p, n in nombres.items() if n and (n.startswith(herr) or herr.startswith(n))), None)
        if pid:
            idx[herr] = pid
    return idx


def _cuenta(entrada: dict, riesgos: list[dict]) -> dict:
    x = entrada.get("x", {})
    rb = [riesgos[i] for i in entrada.get("rbi", []) if 0 <= i < len(riesgos)]
    return {
        "codigo": x.get("codigo", ""),
        "cuenta": x.get("cuenta", ""),
        "seccion": x.get("sec", ""),
        "saldo": x.get("act"),
        "material": x.get("material"),
        "variacion_material": x.get("varMaterial"),
        "riesgos": [r.get("codigo") or r.get("cod") for r in rb if r.get("presenta") == "Sí"],
    }


def sugerencias(plan_run: dict) -> dict:
    """De la corrida de la planificación, la lista ordenada de pruebas del piloto a
    ejecutar (una por herramienta, con sus cuentas, riesgos y saldo acumulado).

    Estructura de salida:
      {"pruebas": [{prueba_id, prueba, rubro, herramienta, cuentas:[...], n_cuentas,
                    saldo, con_riesgo}], "sin_prueba": [{herramienta, cuentas}],
       "cuentas_a_revisar": N}
    """
    detalle = (plan_run or {}).get("detalle") or {}
    revisar = detalle.get("revisar") or []
    riesgos = detalle.get("riesgos") or []
    idx = indice_por_herramienta()

    grupos: dict[str, dict] = {}
    sin_prueba: dict[str, dict] = {}
    for entrada in revisar:
        if entrada.get("revisa") != "Sí":
            continue
        herr = entrada.get("herr") or pn.SIN_HERRAMIENTA
        cuenta = _cuenta(entrada, riesgos)
        pid = idx.get(herr)
        destino = grupos if pid else sin_prueba
        clave = pid or herr
        if clave not in destino:
            if pid:
                mod = procesadores.PROCESADORES[pid]
                destino[clave] = {"prueba_id": pid, "prueba": mod.definicion().get("name", pid),
                                  "rubro": getattr(mod, "RUBRO", "") or "", "herramienta": herr,
                                  "cuentas": [], "n_cuentas": 0, "saldo": 0.0, "con_riesgo": False}
            else:
                destino[clave] = {"herramienta": herr, "cuentas": [], "n_cuentas": 0, "saldo": 0.0}
        g = destino[clave]
        g["cuentas"].append(cuenta)
        g["n_cuentas"] += 1
        try:
            g["saldo"] += abs(float(cuenta["saldo"] or 0))
        except (TypeError, ValueError):
            pass
        if pid and cuenta["riesgos"]:
            g["con_riesgo"] = True

    # Orden: primero las que tienen riesgo, luego por saldo acumulado (mayor primero).
    pruebas = sorted(grupos.values(), key=lambda g: (not g["con_riesgo"], -g["saldo"]))
    for g in pruebas:
        g["saldo"] = round(g["saldo"], 2)
    otras = sorted(sin_prueba.values(), key=lambda g: -g["saldo"])
    for g in otras:
        g["saldo"] = round(g["saldo"], 2)
    return {"pruebas": pruebas, "sin_prueba": otras,
            "cuentas_a_revisar": sum(g["n_cuentas"] for g in pruebas) + sum(g["n_cuentas"] for g in otras)}
