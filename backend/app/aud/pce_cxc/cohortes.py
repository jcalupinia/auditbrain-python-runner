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

from backend.app.aud.pce_cxc.motor import redondear, tasa_perdida


#: Cuántos documentos ambiguos se listan como ejemplo. El conteo completo va
#: aparte: la lista es para que el auditor vea casos concretos, no para
#: materializar en memoria la cartera entera de un archivo con 130.000 filas.
MAX_DOCUMENTOS_AMBIGUOS = 50


def tasas_por_permanencia(cohorte: list[dict[str, Any]], actual: list[dict[str, Any]]) -> dict:
    """Deriva la tasa de cada banda siguiendo la cohorte por número de documento.

    El método depende de que el número de documento sea único: el remanente se
    agrega por ese número, así que si dos clientes comparten número de factura
    sus saldos se fusionan y el numerador de todas las tasas queda mal. Esos
    números se detectan y se devuelven en `documentos_ambiguos` (con el conteo
    completo en `documentos_ambiguos_total`) en vez de calcular como si nada.
    """
    saldo_actual: dict[str, float] = defaultdict(float)
    for f in actual:
        saldo_actual[f["documento"]] += float(f["saldo"])

    # Un solo diccionario documento -> primer cliente visto; solo los documentos
    # que efectivamente colisionan guardan el conjunto de clientes.
    cliente_de: dict[str, str] = {}
    clientes_en_conflicto: dict[str, set[str]] = {}
    for f in cohorte:
        cliente_de.setdefault(f["documento"], str(f.get("cliente") or ""))
    for f in actual:
        doc = f["documento"]
        cliente = str(f.get("cliente") or "")
        previo = cliente_de.setdefault(doc, cliente)
        if previo != cliente:
            clientes_en_conflicto.setdefault(doc, {previo}).add(cliente)
    documentos_ambiguos = [
        {"documento": doc, "clientes": sorted(clientes_en_conflicto[doc]),
         "saldo_actual": redondear(saldo_actual.get(doc, 0.0))}
        for doc in sorted(clientes_en_conflicto)[:MAX_DOCUMENTOS_AMBIGUOS]
    ]

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
                # La proporción de la cohorte que no se recuperó la calcula el
                # motor (`tasa_perdida`), que es donde vive la definición: aquí
                # solo se acota y se declara lo que queda fuera de rango.
                tasa_bruta = tasa_perdida(d["inicial"], d["remanente"])

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
            "anomalias": anomalias,
            "documentos_ambiguos": documentos_ambiguos,
            "documentos_ambiguos_total": len(clientes_en_conflicto)}
