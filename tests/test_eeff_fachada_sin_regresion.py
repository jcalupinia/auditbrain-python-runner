import io, openpyxl
from backend.app.tax.planificacion_utilidades.parsers.balance_interno import extract_balance_interno
from tests.fixtures.eeff_sintetico import libro_resumido_nombre


def _codificado_bytes():
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Cuenta", "Nombre", 2024, 2025])
    ws.append(["1", "ACTIVO", 100, 110])
    # El camino codificado mapea a 'efectivo' por el nombre (contiene EFECTIVO).
    ws.append(["1.1.01", "Efectivo y equivalentes", 100, 110])
    ws.append(["2", "PASIVO", 40, 50])
    ws.append(["2.1.01", "Proveedores", 40, 50])
    ws.append(["3", "PATRIMONIO", 60, 60])
    ws.append(["3.1.01", "Capital", 60, 60])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def test_resumido_nombre_entra_por_fachada():
    r = extract_balance_interno(libro_resumido_nombre())
    assert r["source"] == "resumido_nombre"
    assert r["data"]["efectivo"][0] == 100


def test_codificado_sigue_funcionando():
    r = extract_balance_interno(_codificado_bytes())
    # el camino codificado NO cambia: efectivo (Caja) sale poblado
    assert r["data"]["efectivo"][-1] == 110
    assert r["source"] == "interno"
