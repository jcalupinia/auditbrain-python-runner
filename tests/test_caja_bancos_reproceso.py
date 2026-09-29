# -*- coding: utf-8 -*-
"""Matriz del reproceso independiente de la conciliación (caja_bancos_armado.matriz_reproceso)."""
from backend.app.aud.niif.procesadores import caja_bancos_armado as A

CORTE = "2026-09-30"


def _reg():
    return {
        "engagement": {"client": "X", "cutoff": CORTE, "period": "sep-2026"},
        "datasets": {
            "cuentas": [
                {"id": "1101", "nombre": "Banco X", "tipo": "Banco", "saldo_libros": "1000.00", "saldo_banco": "1200.00"},
                {"id": "1001", "nombre": "Caja general", "tipo": "Caja", "saldo_libros": "50.00", "saldo_banco": "50.00"},
            ],
            "libro_mayor": [
                {"cuenta": "1101", "fecha": "2026-09-10", "detalle": "Depósito", "debito": "500.00", "credito": "0.00"},
            ],
            "estado_cuenta": [
                {"cuenta": "1101", "fecha": "2026-09-10", "documento": "Depósito", "debito": "0.00", "credito": "500.00"},
                {"cuenta": "1101", "fecha": "2026-09-30", "documento": "Comisión", "debito": "200.00", "credito": "0.00"},
            ],
            # La compañía también registró la ND de 200 en su conciliación (RQ-002).
            "partidas": [
                {"id": "P1", "cuenta": "1101", "tipo": "Nota de débito", "fecha_origen": "2026-09-30",
                 "importe": "200.00", "referencia": "Comisión"},
            ],
        },
    }


def test_matriz_reproceso_cuadra_y_excluye_caja():
    m = A.matriz_reproceso(_reg())
    assert len(m) == 1                      # solo la cuenta de banco; la caja se excluye
    f = m[0]
    assert f["cuenta"] == "1101"
    # Reconstrucción: 1200 (extracto) − 200 (ND en tránsito) = 1000 = libros → cuadra.
    assert f["saldo_auditoria"] == 1000.0 and f["diferencia"] == 0.0 and f["estado"] == "CONCILIADA"
    assert f["n_partidas_reproceso"] == 1   # la ND de 200 que el banco cargó y el libro no
    assert f["coincidencias"] == 1          # el depósito de 500 se emparejó
    # La compañía registró la misma ND → sin omisiones ni adicionales.
    assert f["omitidas_por_la_compania"] == 0 and f["adicionales_de_la_compania"] == 0


def test_matriz_reproceso_detecta_diferencia_de_la_compania():
    reg = _reg()
    reg["datasets"]["partidas"] = []        # la compañía NO registró la ND: el reproceso la detecta
    f = A.matriz_reproceso(reg)[0]
    assert f["omitidas_por_la_compania"] == 1
    assert f["diferencia"] == 0.0           # el reproceso igual cuadra el saldo


def test_sin_estado_de_cuenta_no_hay_reproceso():
    assert A.matriz_reproceso({"datasets": {"cuentas": [{"id": "1101", "tipo": "Banco"}]}}) is None


def test_prescripcion_parametrizable_en_el_papel_da4():
    import io
    import openpyxl
    from backend.app.aud.niif.procesadores import caja_bancos_papel as papel
    entrada = {
        "engagement": {"client": "X", "period": "sep-2026", "cutoff": CORTE},
        "cuentas": [{"cuenta": "1101", "descripcion": "Banco X", "saldo_anterior": 0, "saldo_actual": 1000, "extracto": 1200}],
        "partidas": [{"fecha": "2026-09-10", "banco": "Banco X", "categoria": papel.ND_TRANSITO,
                      "documento": "Comisión", "beneficiario": "", "valor": 200, "observacion": ""}],
        "dias_prescripcion": 200,
    }
    wb = openpyxl.load_workbook(io.BytesIO(papel.construir(entrada)))
    ws = next(w for w in wb.worksheets if "Partida" in w.title)
    formulas = [ws.cell(r, 8).value for r in range(1, ws.max_row + 1)
                if isinstance(ws.cell(r, 8).value, str) and ws.cell(r, 8).value.startswith("=A")]
    assert any(f.endswith("+200") for f in formulas)   # usó diasPrescripcion=200, no el 390 por defecto
