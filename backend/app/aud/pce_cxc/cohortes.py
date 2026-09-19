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

from backend.app.aud.pce_cxc.motor import (
    PISO_CERO, TASA_MAXIMA, acotar, redondear, tasa_perdida,
)


#: Cuántos documentos ambiguos se listan como ejemplo. El conteo completo va
#: aparte: la lista es para que el auditor vea casos concretos, no para
#: materializar en memoria la cartera entera de un archivo con 130.000 filas.
MAX_DOCUMENTOS_AMBIGUOS = 50

#: Cuántas inconsistencias del corte intermedio se listan como ejemplo. El
#: conteo completo va aparte, por la misma razón que arriba.
MAX_INCONSISTENCIAS_INTERMEDIO = 50

#: Por debajo de este importe una diferencia es ruido de redondeo, no un hecho.
TOLERANCIA = 0.005


def _controlar_corte_intermedio(
    cohorte: list[dict[str, Any]],
    saldo_intermedio: dict[str, float],
    saldo_actual: dict[str, float],
) -> dict[str, Any]:
    """Contrasta la cohorte (t-2) contra su propio rastro en t-1 y en t.

    El método de permanencia solo mira dos puntos -el saldo inicial en t-2 y el
    remanente en t-, así que el corte intermedio es la única forma de saber si
    el camino entre ambos tiene sentido. Dos trayectorias no lo tienen:

    - Un documento que ya no está en t-1 y vuelve a aparecer en t. Si se cobró
      o se dio de baja no puede resucitar: o la numeración se reutilizó, o una
      factura nueva heredó el número, o el corte intermedio está incompleto.
      En cualquiera de los tres casos el remanente que alimenta las tasas no es
      lo que quedó vivo de la cohorte.
    - Un remanente en t MAYOR que el saldo del mismo documento en t-1. Un saldo
      por cobrar no crece sin facturación nueva; si crece, algo se imputó al
      mismo número.

    Se recorre la cohorte una sola vez y solo se guardan los documentos que
    fallan: no se materializa ninguna copia de la cartera.
    """
    saldo_cohorte: dict[str, float] = defaultdict(float)
    for f in cohorte:
        saldo_cohorte[f["documento"]] += float(f["saldo"])

    inconsistencias: list[dict[str, Any]] = []
    total_inconsistencias = 0
    importe_afectado = 0.0
    vivos_en_intermedio = 0
    total_intermedio = 0.0
    total_actual = 0.0
    for documento, inicial in saldo_cohorte.items():
        en_intermedio = float(saldo_intermedio.get(documento, 0.0))
        en_actual = float(saldo_actual.get(documento, 0.0))
        total_intermedio += en_intermedio
        total_actual += en_actual
        if abs(en_intermedio) > TOLERANCIA:
            vivos_en_intermedio += 1
        tipo = None
        if abs(en_intermedio) <= TOLERANCIA and abs(en_actual) > TOLERANCIA:
            tipo = "reaparece_tras_desaparecer"
        elif en_actual > en_intermedio + TOLERANCIA:
            tipo = "remanente_mayor_que_intermedio"
        if tipo is None:
            continue
        total_inconsistencias += 1
        importe_afectado += en_actual
        if len(inconsistencias) < MAX_INCONSISTENCIAS_INTERMEDIO:
            inconsistencias.append({
                "documento": documento, "tipo": tipo,
                "saldo_cohorte": redondear(inicial),
                "saldo_intermedio": redondear(en_intermedio),
                "saldo_actual": redondear(en_actual),
            })

    documentos = len(saldo_cohorte)
    return {
        "documentos_cohorte": documentos,
        "saldo_cohorte": redondear(sum(saldo_cohorte.values())),
        "vivos_en_intermedio": vivos_en_intermedio,
        "saldo_en_intermedio": redondear(total_intermedio),
        "saldo_en_actual": redondear(total_actual),
        "permanencia_intermedia": (vivos_en_intermedio / documentos) if documentos else 0.0,
        "inconsistencias": sorted(inconsistencias, key=lambda c: c["documento"]),
        "inconsistencias_total": total_inconsistencias,
        "inconsistencias_importe": redondear(importe_afectado),
        "consistente": total_inconsistencias == 0,
    }


def tasas_por_permanencia(cohorte: list[dict[str, Any]], actual: list[dict[str, Any]],
                          intermedio: list[dict[str, Any]] | None = None) -> dict:
    """Deriva la tasa de cada banda siguiendo la cohorte por número de documento.

    El método depende de que el número de documento sea único: el remanente se
    agrega por ese número, así que si dos clientes comparten número de factura
    sus saldos se fusionan y el numerador de todas las tasas queda mal. Esos
    números se detectan y se devuelven en `documentos_ambiguos` (con el conteo
    completo en `documentos_ambiguos_total`) en vez de calcular como si nada.

    `intermedio` es el corte t-1. No entra en las tasas -el método mide
    permanencia entre t-2 y t- pero sí controla que el camino entre los dos
    extremos sea coherente: el resultado va en `control_corte_intermedio`.
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

                # La tasa observada se acota a [0 %; 100 %] con `motor.acotar`,
                # como TODA cota de este módulo: el helper devuelve el par
                # (valor, motivo), así que el motivo no se puede tirar por
                # descuido y `motor.COTAS` obliga a que llegue al papel
                # (04-Tasas: la columna «Tasa aplicada» lo RECALCULA desde el
                # ratio de 03-Cohorte y la columna «Origen» lo DECLARA). Antes
                # era un `if/elif` escrito a mano: el comportamiento era el
                # mismo, pero la invariante que el módulo declara -ningún
                # recorte fuera del helper- no era literal.
                tasa, cota = acotar(tasa_bruta, piso=0.0, techo=1.0,
                                    motivo_piso=PISO_CERO, motivo_techo=TASA_MAXIMA)
                tasas[segmento][banda] = tasa
                if cota is not None:
                    anomalias.append({
                        "segmento": segmento,
                        "banda": banda,
                        "inicial": d["inicial"],
                        "remanente": d["remanente"],
                        "tasa_bruta": tasa_bruta,
                        # El motivo tal como lo nombra el motor, junto al tipo
                        # que esta lista ya usaba: el papel traduce el tipo y
                        # `tests/test_pce_cotas.py` comprueba el motivo.
                        "cota": cota,
                        "tipo": ("remanente_negativo" if cota == PISO_CERO
                                 else "remanente_mayor_que_inicial"),
                    })
            else:
                tasas[segmento][banda] = None

    control = None
    if intermedio is not None:
        # Un solo diccionario documento -> saldo del corte intermedio; se
        # construye aquí y se descarta al salir, y `saldo_actual` se reutiliza
        # en vez de recorrer el corte actual por segunda vez.
        saldo_intermedio: dict[str, float] = defaultdict(float)
        for f in intermedio:
            saldo_intermedio[f["documento"]] += float(f["saldo"])
        control = _controlar_corte_intermedio(cohorte, saldo_intermedio, saldo_actual)

    encontrados = sum(1 for f in cohorte if f["documento"] in saldo_actual)
    return {"tasas": tasas, "detalle": {s: dict(b) for s, b in detalle.items()},
            "trazabilidad": (encontrados / len(cohorte)) if cohorte else 0.0,
            "anomalias": anomalias,
            "documentos_ambiguos": documentos_ambiguos,
            "documentos_ambiguos_total": len(clientes_en_conflicto),
            "control_corte_intermedio": control}
