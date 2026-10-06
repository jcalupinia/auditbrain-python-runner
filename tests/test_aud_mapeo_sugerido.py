"""Regresión del auto-mapeo de columnas (ejemplos_manifiesto.mapeo_sugerido),
réplica backend de cicloLogic.js::mapeoSugerido.

Caso real (efectivo y equivalentes): el anexo de caja y bancos que entrega el
cliente trae los encabezados con la FECHA del corte pegada
(«Saldo anterior 31-12-2025», «Saldo actual 31-08-2026»). El mapeo exacto no
los reconocía y la Sumaria salía con saldo anterior = 0. El pase 2 (el
encabezado EMPIEZA con un alias ≥ 6 car.) los tolera.
"""
from backend.app.aud.niif.ejemplos_manifiesto import mapeo_sugerido


def test_mapeo_exacto_sin_texto_extra():
    campos = [
        {"key": "id", "label": "Código", "aliases": ["codigo", "cuenta"]},
        {"key": "quantity", "label": "Cantidad", "aliases": []},
        {"key": "unit_cost", "label": "Costo unitario", "aliases": []},
    ]
    assert mapeo_sugerido(["CODIGO", "Descripción", "cantidad", "Costo Unitario"], campos) == {
        "id": 0,
        "quantity": 2,
        "unit_cost": 3,
    }
    assert mapeo_sugerido(["x"], campos) == {}


def test_encabezado_con_fecha_pegada_saldo_anterior_y_actual():
    # Mismos campos relevantes del dataset «cuentas» de efectivo.
    campos = [
        {"key": "id", "label": "Código de cuenta", "aliases": ["codigo", "cuenta"]},
        {"key": "saldo_anterior", "label": "Saldo anterior (cierre previo)",
         "aliases": ["saldo anterior", "anterior", "saldo inicial"]},
        {"key": "saldo_libros", "label": "Saldo según libros",
         "aliases": ["saldo libros", "libros", "saldo actual"]},
    ]
    headers = ["Cuenta", "Saldo anterior 31-12-2025", "Saldo actual  31-08-2026"]
    mapa = mapeo_sugerido(headers, campos)
    assert mapa["id"] == 0            # «Cuenta» == alias exacto de id
    assert mapa["saldo_anterior"] == 1  # empieza con «saldo anterior»
    assert mapa["saldo_libros"] == 2    # empieza con «saldo actual»


def test_no_reasigna_una_columna_a_dos_campos():
    # Si un encabezado ya fue tomado en el pase exacto, el pase por prefijo no lo roba.
    campos = [
        {"key": "saldo_libros", "label": "Saldo según libros", "aliases": ["saldo actual"]},
        {"key": "saldo_anterior", "label": "Saldo anterior", "aliases": ["saldo anterior"]},
    ]
    headers = ["Saldo actual", "Saldo anterior 31-12-2025"]
    mapa = mapeo_sugerido(headers, campos)
    assert mapa["saldo_libros"] == 0
    assert mapa["saldo_anterior"] == 1
