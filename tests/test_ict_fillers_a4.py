"""Tests for A4 Conciliación Ingresos filler (2 cuadros)."""

import uuid

from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a4_conciliacion_ingresos import A4Filler


def _session_data():
    return {
        "razon_social": f"Empresa Test {uuid.uuid4().hex[:6]}",
        "ruc": "1799999990001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "",
    }


def test_a4_filler_writes_header():
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    result = filler.fill(wb, sess, {})
    ws = wb["CONCILIACIÓN INGRESOS A4"]
    assert ws["C3"].value == sess["razon_social"]
    assert ws["C4"].value == sess["ruc"]
    assert ws["C5"].value == sess["ejercicio_fiscal"]
    assert result["filled_cells"] >= 3


def test_a4_filler_writes_casilleros():
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    data = {
        "f101": {
            "804": 5000.0,
            "805": 1200.0,
            "812": 0.0,
            "1112": 3500.0,
        }
    }
    result = filler.fill(wb, sess, data)
    ws = wb["CONCILIACIÓN INGRESOS A4"]

    # Cuadro 2: casillero → row mapping
    assert ws["G32"].value == 5000.0    # 804 → row 32
    assert ws["G33"].value == 1200.0   # 805 → row 33
    assert ws["G34"].value == 0.0      # 812 → row 34
    assert ws["G35"].value == 3500.0   # 1112 → row 35
    assert result["filled_cells"] > 3


def test_a4_filler_writes_mayor_detail():
    """CAMBIO 2026-06-17: A4 Cuadro 1 ya NO toma datos del balance_mapeado
    ni del mayor_exentos. La fuente única es DATOS F-101 (cas exentos/no
    objeto con valor declarado).

    Este test ahora valida que cuando F-101 declare valor en un cas exento
    (ej. 6094 OTRAS RENTAS EXENTAS), el A4 lo trasladará a col B y col G
    apuntará a la referencia F-101 correspondiente."""
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    # f101 declara cas 6094 con valor → debe trasladarse a A4 B16
    data = {
        "f101": {"6094": 18000.0},
        "_f101_lookup": {"6094": 557},  # fila simulada en DATOS F-101
    }
    result = filler.fill(wb, sess, data)
    ws = wb["CONCILIACIÓN INGRESOS A4"]

    # B16 debe ser '6094' (codigo del casillero del F-101)
    assert ws["B16"].value == "6094", (
        f"B16 esperado '6094', encontrado {ws['B16'].value!r}"
    )
    # G16 debe ser referencia al F-101, NO SUMIF al balance
    g16 = ws["G16"].value
    assert isinstance(g16, str) and "DATOS F-101" in g16, (
        f"G16 debe ser referencia a F-101. Encontrado: {g16!r}"
    )
    assert result["filled_cells"] >= 2  # B16 + G16 al menos


def test_a4_filler_inserta_filas_con_mas_de_10_exentos():
    """CAMBIO 2026-06-25: si hay más de 10 cas exentos con valor en F-101,
    A4 INSERTA filas dinámicamente para que entren TODOS (no trunca)."""
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    # 11 cas exentos con valor, TODOS en la librería CMIE (6150 se excluye
    # por informativo, así que usamos 6002 en su lugar). Las 10 filas base
    # no alcanzan → +1 fila insertada.
    f101 = {"6042": 100, "6044": 200, "6060": 300, "6094": 400,
            "6116": 500, "6002": 600, "6081": 700, "6083": 800,
            "6085": 900, "6062": 1000, "6064": 1100}
    lookup = {cas: 500 + int(cas) - 6000 for cas in f101.keys()}
    data = {"f101": f101, "_f101_lookup": lookup}
    result = filler.fill(wb, sess, data)
    ws = wb["CONCILIACIÓN INGRESOS A4"]

    # Los 11 casilleros deben estar presentes (B16:B26), ninguno truncado
    presentes = [ws.cell(r, 2).value for r in range(16, 27) if ws.cell(r, 2).value]
    assert len(presentes) == 11, f"Esperado 11 cas, encontrado {len(presentes)}: {presentes}"
    for cas in f101:
        assert cas in presentes, f"Cas {cas} no se trasladó. {presentes}"
    # NO debe haber warning de truncamiento
    assert not any("ocupadas" in w.lower() or "no se trasladó" in w.lower()
                   for w in result["warnings"]), result["warnings"]


def test_a4_filler_no_crash_with_empty_data():
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    result = filler.fill(wb, sess, {})
    assert "filled_cells" in result
    assert isinstance(result["warnings"], list)
    # Should warn about missing data
    assert any("mayor_exentos" in w or "F-101" in w for w in result["warnings"])


def test_a4_filler_preserves_formula_rows():
    """Formula rows (G26 =SUM, G36 =SUM, G37 =diferencia) must NOT be overwritten."""
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    data = {
        "f101": {"804": 1000.0, "805": 2000.0, "812": 500.0, "1112": 0.0},
        "mayor_exentos": [
            {"codigo": "510101", "nombre": "Cuenta exenta", "saldo": 3500.0, "debe": 0.0, "haber": 3500.0, "tipo": ""}
        ],
    }
    filler.fill(wb, sess, data)
    ws = wb["CONCILIACIÓN INGRESOS A4"]

    # G26 should still have the SUM formula
    assert ws["G26"].value is not None
    val = ws["G26"].value
    assert isinstance(val, str) and val.startswith("="), (
        f"G26 formula was overwritten: {val!r}"
    )
    # G36 should still have the SUM formula
    assert ws["G36"].value is not None
    val36 = ws["G36"].value
    assert isinstance(val36, str) and val36.startswith("="), (
        f"G36 formula was overwritten: {val36!r}"
    )
