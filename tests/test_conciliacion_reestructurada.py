# -*- coding: utf-8 -*-
"""Reestructuración de la conciliación: emparejamiento y clasificación de partidas."""
from backend.app.aud.niif.procesadores import conciliacion_reestructurada as cr
from backend.app.aud.niif.procesadores import caja_bancos_papel as papel

CORTE = "2026-09-30"

# Libro bancos del mes (perspectiva del efectivo del cliente).
LIBRO = [
    {"fecha": "2026-09-10", "documento": "Depósito ventas", "ingreso": 1000, "egreso": 0},
    {"fecha": "2026-09-28", "documento": "Depósito en tránsito", "ingreso": 500, "egreso": 0},   # no en extracto
    {"fecha": "2026-09-15", "documento": "Cheque 101", "ingreso": 0, "egreso": 300},              # coincide
    {"fecha": "2026-09-29", "documento": "Cheque 108", "ingreso": 0, "egreso": 200},              # no cobrado
]
# Estado de cuenta del mes.
EXTRACTO = [
    {"fecha": "2026-09-10", "documento": "Depósito ventas", "ingreso": 1000, "egreso": 0},        # coincide
    {"fecha": "2026-09-16", "documento": "Cheque 101", "ingreso": 0, "egreso": 300},              # coincide (día +1)
    {"fecha": "2026-09-30", "documento": "Comisión mantenimiento", "ingreso": 0, "egreso": 25},   # ND no registrada
    {"fecha": "2026-09-30", "documento": "Interés ganado", "ingreso": 12, "egreso": 0},           # NC no registrada
]


def _por_cat(partidas):
    d = {}
    for p in partidas:
        d.setdefault(p["categoria"], []).append(p)
    return d


def test_identifica_y_clasifica_las_cuatro_categorias():
    r = cr.reestructurar(LIBRO, EXTRACTO, CORTE, banco="BANCO PICHINCHA")
    cats = _por_cat(r["partidas"])
    # 4 partidas: depósito en tránsito, cheque no cobrado, ND, NC.
    assert r["resumen"]["total_partidas"] == 4
    assert cats[papel.CONSIGNACION][0]["valor"] == 500      # ingreso en libros no en extracto
    assert cats[papel.CHEQUE][0]["valor"] == 200            # egreso en libros no en extracto
    assert cats[papel.ND_TRANSITO][0]["valor"] == 25        # egreso en extracto no en libros
    assert cats[papel.NC_PENDIENTE][0]["valor"] == 12       # ingreso en extracto no en libros
    # Los movimientos que coinciden NO generan partida (depósito 1000 y cheque 101).
    assert r["resumen"]["emparejadas_libro"] == 2
    assert r["resumen"]["emparejadas_extracto"] == 2


def test_antiguedad_al_corte():
    r = cr.reestructurar(LIBRO, EXTRACTO, CORTE, banco="X")
    dep = _por_cat(r["partidas"])[papel.CONSIGNACION][0]
    assert dep["dias_vencidos"] == 2   # 2026-09-30 − 2026-09-28


def test_arrastre_de_partidas_del_mes_anterior():
    previas = [
        {"fecha": "2026-08-25", "documento": "Cheque 090", "categoria": papel.CHEQUE,
         "valor": 200, "observacion": "Pendiente"},          # se depura: hay un cheque de 200 este mes
        {"fecha": "2026-08-05", "documento": "Cheque 077", "categoria": papel.CHEQUE,
         "valor": 999, "observacion": "Pendiente"},          # sigue abierta: se arrastra
    ]
    r = cr.reestructurar(LIBRO, EXTRACTO, CORTE, banco="X", partidas_previas=previas)
    arrastradas = [p for p in r["partidas"] if "arrastrada" in p["observacion"]]
    assert len(arrastradas) == 1
    assert arrastradas[0]["valor"] == 999
    assert "arrastrada del mes anterior" in arrastradas[0]["observacion"]


def test_debito_credito_a_perspectiva_cliente():
    libro = cr.desde_debito_credito(
        [{"fecha": "2026-09-10", "documento": "Depósito", "debito": 1000, "credito": 0}], "libro")
    assert libro[0]["ingreso"] == 1000 and libro[0]["egreso"] == 0
    # El extracto viene desde la óptica del banco: crédito del banco = ingreso del cliente.
    ext = cr.desde_debito_credito(
        [{"fecha": "2026-09-10", "documento": "Depósito", "debito": 0, "credito": 1000}], "extracto")
    assert ext[0]["ingreso"] == 1000 and ext[0]["egreso"] == 0


def test_partidas_encajan_en_el_papel_formulado():
    """Las partidas de la reestructuración alimentan directamente el papel (DA-4/DA-3)."""
    r = cr.reestructurar(LIBRO, EXTRACTO, CORTE, banco="BANCO PICHINCHA")
    data = papel.construir({
        "engagement": {"client": "X", "period": "sep-2026", "cutoff": CORTE},
        "cuentas": [{"cuenta": "11010201", "descripcion": "BANCO PICHINCHA",
                     "saldo_anterior": 0, "saldo_actual": 1000, "ncuenta": "1", "extracto": 987}],
        "partidas": r["partidas"],
    })
    assert data[:2] == b"PK"   # xlsx válido (zip)
