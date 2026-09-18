"""Tasas de pérdida derivadas del comportamiento observado de la cartera.

Método de permanencia: se toma el saldo de cada documento en el corte más antiguo
y se rastrea por su número en el corte actual. Lo que sigue vivo veinticuatro meses
después es lo que no se recuperó, y esa permanencia sí es directamente observable.
La inferencia "si desapareció, se cobró" solo es válida si los castigos del período
fueron inmateriales: por eso el servicio exige el mayor de la provisión.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def tasas_por_permanencia(cohorte: list[dict[str, Any]], actual: list[dict[str, Any]]) -> dict:
    saldo_actual: dict[str, float] = defaultdict(float)
    for f in actual:
        saldo_actual[f["documento"]] += float(f["saldo"])

    detalle: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for f in cohorte:
        d = detalle[f["segmento"]].setdefault(f["banda"], {"inicial": 0.0, "remanente": 0.0, "documentos": 0})
        d["inicial"] += float(f["saldo"])
        d["remanente"] += saldo_actual.get(f["documento"], 0.0)
        d["documentos"] += 1

    tasas: dict[str, dict[str, float | None]] = {}
    anomalias: list[dict[str, Any]] = []

    for segmento, bandas in detalle.items():
        tasas[segmento] = {}
        for banda, d in bandas.items():
            if d["inicial"] > 0:
                tasa_bruta = d["remanente"] / d["inicial"]

                # Detectar anomalías y acotar la tasa entre 0 y 1
                if tasa_bruta > 1.0:
                    anomalias.append({
                        "segmento": segmento,
                        "banda": banda,
                        "inicial": d["inicial"],
                        "remanente": d["remanente"],
                        "tasa_bruta": tasa_bruta,
                        "tipo": "remanente_mayor_que_inicial"
                    })
                    tasas[segmento][banda] = 1.0
                elif tasa_bruta < 0.0:
                    anomalias.append({
                        "segmento": segmento,
                        "banda": banda,
                        "inicial": d["inicial"],
                        "remanente": d["remanente"],
                        "tasa_bruta": tasa_bruta,
                        "tipo": "remanente_negativo"
                    })
                    tasas[segmento][banda] = 0.0
                else:
                    tasas[segmento][banda] = tasa_bruta
            else:
                tasas[segmento][banda] = None

    encontrados = sum(1 for f in cohorte if f["documento"] in saldo_actual)
    return {"tasas": tasas, "detalle": {s: dict(b) for s, b in detalle.items()},
            "trazabilidad": (encontrados / len(cohorte)) if cohorte else 0.0,
            "anomalias": anomalias}
