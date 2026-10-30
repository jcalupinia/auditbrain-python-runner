"""El nombre de la cuenta del gasto sale de la columna «Cuenta»/«Nombre» del mayor, no de la
glosa del movimiento «Descripción».

CIDESCOL (2026-10-30): su mayor de gastos trae Código + Cuenta (nombre) + Descripción (glosa del
movimiento, cuya primera fila es «SALDO ANTERIOR»). El motor tomaba el nombre de «Descripción» →
las cuentas del DO-6 Cruce de Gasto salían rotuladas «SALDO ANTERIOR». PROPHAR trae Nºcuenta +
Descripción, donde la descripción ES el nombre: ahí no hay columna «Cuenta» y el nombre debe
seguir saliendo de «Descripción» (comportamiento histórico, verificado aparte con cero diferencias).

Sin datos reales de cliente.
"""
from openpyxl import Workbook

from backend.app.aud.niif.procesadores.nomina import mayores as MY


def _mayor(tmp_path, headers, filas):
    p = tmp_path / "mayor.xlsx"
    wb = Workbook(); ws = wb.active
    ws.append(headers)
    for f in filas:
        ws.append(f)
    wb.save(p)
    return str(p)


def test_nombre_sale_de_columna_cuenta_cuando_existe(tmp_path):
    # Estructura tipo CIDESCOL: Código + Cuenta (nombre) + Descripción (glosa «SALDO ANTERIOR»).
    p = _mayor(
        tmp_path,
        ["Código", "Cuenta", "Fecha L/M", "Descripción", "Debe", "Haber"],
        [
            ["5.2.1.2.1.3", "Decimo tercer sueldo", "2026-01-31", "SALDO ANTERIOR", 0, 0],
            ["5.2.1.2.1.3", "Decimo tercer sueldo", "2026-01-31", "Provisión D13 enero", 100, 0],
        ],
    )
    d = MY._load(p)
    nombres = set(d["nombre_cta"].unique())
    assert "Decimo tercer sueldo" in nombres
    assert "SALDO ANTERIOR" not in nombres          # ya no toma la glosa del movimiento


def test_sin_columna_cuenta_el_nombre_cae_a_descripcion(tmp_path):
    # Estructura tipo PROPHAR: Nºcuenta + Descripción (= el nombre). No hay columna «Cuenta».
    p = _mayor(
        tmp_path,
        ["Nºcuenta", "Descripción", "Fecha L/M", "Importe"],
        [
            ["5ASCA.61101.004", "Décimo Tercer Sueldo", "2025-12-31", 100],
        ],
    )
    d = MY._load(p)
    # El nombre cae a la Descripción (comportamiento histórico): nombre_cta == desc.
    assert list(d["nombre_cta"]) == list(d["desc"]) == ["Décimo Tercer Sueldo"]


def test_el_codigo_no_se_confunde_con_el_nombre(tmp_path):
    # «Código» (código) y «Cuenta» (nombre) son columnas distintas: el código no debe terminar de nombre.
    p = _mayor(
        tmp_path,
        ["Código", "Cuenta", "Fecha L/M", "Descripción", "Debe", "Haber"],
        [["5.2.1.2.1.2", "Aporte patronal IESS", "2026-02-28", "mov", 50, 0]],
    )
    d = MY._load(p)
    assert list(d["cta"]) == ["5.2.1.2.1.2"]        # código intacto
    assert list(d["nombre_cta"]) == ["Aporte patronal IESS"]
