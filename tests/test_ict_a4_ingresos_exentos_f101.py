"""Regression test: cuando F-101 declara valores en cas de ingresos
exentos / no objeto, A4 Cuadro 1 debe trasladarlos automaticamente.

Reportado por cliente 2026-06-17: si el F-101 declara valor en cas
6081/6083/6085/6094/6150 (RENTAS EXENTAS / NO OBJETO DE IMPUESTO), el
A4 debe poblar:
  - Col B (casillero) desde B16 con el numero del casillero
  - Col G (valor) desde G16 con referencia al valor F-101

Antes: B16:B25 quedaba vacio cuando no habia `mayor_exentos` ni cuentas
del balance mapeadas a cas 804/805/812/1112. La col G era SUMIF reactivo
al balance pero como B estaba vacio, evaluaba a "" → el detalle de los
ingresos exentos declarados en F-101 nunca aparecia.

Ahora: cas 6081, 6083, 6085, 6094, 6150 con valor != 0 en F-101 se
trasladan a las primeras filas libres de B16:B25 y la formula G
correspondiente sigue funcionando reactivamente.
"""
from __future__ import annotations

import pytest


# Cas oficiales SRI de ingresos exentos / no objeto (rango 6001-6999)
# que NO empiezan con "VALOR EXENTO" (esos son subitems informativos).
CAS_EXENTOS_NO_OBJETO = ["6081", "6083", "6085", "6094", "6150"]


def _build_wb_a4_con_exentos(valores_f101: dict[str, float]):
    """Genera workbook ICT con valores F-101 en cas exentos y devuelve
    la hoja A4 ya rellenada."""
    from openpyxl import Workbook
    from backend.app.ict.cell_maps.a4 import A4_SHEET
    from backend.app.ict.fillers.a4_conciliacion_ingresos import A4Filler
    from backend.app.ict.fillers.source_data_sheets import build_f101_sheet
    from backend.app.ict.fillers.base import load_template

    wb = load_template()  # incluye la hoja A4 con sus fórmulas de template
    # Necesitamos también DATOS F-101 para que las referencias funcionen.
    f101_data = dict(valores_f101)
    f101_lookup = build_f101_sheet(wb, f101_data, {})

    filler = A4Filler()
    session_data = {"razon_social": "TEST", "ruc": "T",
                    "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    anexo_data = {
        "f101": f101_data,
        "balance_mapeado": [],
        "_f101_lookup": f101_lookup,
        "_balance_lookup": [],
    }
    filler.fill(wb, session_data, anexo_data)
    return wb[A4_SHEET], f101_lookup


def test_a4_traslada_cas_6094_otras_rentas_exentas_con_valor():
    """Cliente declara cas 6094 (OTRAS RENTAS EXENTAS) = 800.00 en F-101.
    El A4 debe poblar B16='6094' y G16 con la formula referencial."""
    ws, f101_lookup = _build_wb_a4_con_exentos({"6094": 800.0})
    assert ws["B16"].value == "6094", (
        f"B16 debe ser '6094' (cas exento con valor en F-101), "
        f"encontrado: {ws['B16'].value!r}"
    )
    g16 = ws["G16"].value
    # G16 puede ser la formula SUMIF reactiva existente O una formula que
    # apunta al valor F-101 del cas. Lo importante: no debe estar vacia y
    # debe ser una fórmula.
    assert isinstance(g16, str) and g16.startswith("="), (
        f"G16 debe ser fórmula, encontrado: {g16!r}"
    )


def test_a4_traslada_multiples_cas_exentos():
    """Si hay 3 cas exentos con valor, llena 3 filas (B16/B17/B18)
    en el orden del catalogo (6081 < 6083 < 6085 < 6094 < 6150)."""
    ws, _ = _build_wb_a4_con_exentos({
        "6081": 100.0,
        "6094": 800.0,
        "6150": 500.0,
    })
    valores_b = [ws.cell(r, 2).value for r in range(16, 26)]
    presentes = [v for v in valores_b if v]
    assert "6081" in presentes, f"Cas 6081 debe aparecer. B16:B25 = {presentes}"
    assert "6094" in presentes, f"Cas 6094 debe aparecer. B16:B25 = {presentes}"
    assert "6150" in presentes, f"Cas 6150 debe aparecer. B16:B25 = {presentes}"
    # Orden creciente por número de cas
    nums = [int(v) for v in presentes if str(v).isdigit()]
    assert nums == sorted(nums), (
        f"Cas deben ir en orden creciente. Encontrado: {nums}"
    )


def test_a4_cas_exentos_con_valor_cero_no_aparecen():
    """Cas exentos con valor 0 en F-101 no deben trasladarse."""
    ws, _ = _build_wb_a4_con_exentos({
        "6081": 0.0,    # No debe aparecer
        "6094": 800.0,  # Sí debe aparecer
        "6150": 0.0,    # No debe aparecer
    })
    valores_b = [ws.cell(r, 2).value for r in range(16, 26) if ws.cell(r, 2).value]
    assert "6094" in valores_b, f"Cas 6094 con valor debe estar. {valores_b}"
    assert "6081" not in valores_b, f"Cas 6081 con valor 0 NO debe estar. {valores_b}"
    assert "6150" not in valores_b, f"Cas 6150 con valor 0 NO debe estar. {valores_b}"


def test_a4_sin_cas_exentos_no_modifica_B16():
    """Si el F-101 no declara cas exentos, B16 queda como antes (vacio
    si no hay balance_mapeado a cas 804/805/812/1112)."""
    ws, _ = _build_wb_a4_con_exentos({"6001": 5000.0})  # cas no-exento
    valores_b = [ws.cell(r, 2).value for r in range(16, 26) if ws.cell(r, 2).value]
    # Ningún cas exento debe estar
    for cas in CAS_EXENTOS_NO_OBJETO:
        assert cas not in valores_b, (
            f"Cas {cas} no debe aparecer si F-101 no lo declara. {valores_b}"
        )
