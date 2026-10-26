"""Mayor por secciones: prueba sintetica, solo memoria/disco temporal."""
from openpyxl import Workbook
from backend.app.ingesta.mayor_secciones import transformar_mayor_secciones


def _libro(path, total="15"):
    w = Workbook()
    s = w.active
    s.append(["Fecha", "Asiento", "Comp.", None, "Cheque", "Referencia", "Debito", "Credito", "Deudor", "Acreedor"])
    s.append(["110101", "Caja", "Saldo Inicial--->", 0])
    s.append(["2026-01-01", 1, "BI", 1, "", "Apertura", 10, 0, 10])
    s.append(["2026-01-02", 2, "CE", 2, "", "Cobro", 5, 0, 15])
    s.append(["Saldo Final de la Cuenta-------->", 15])
    s.append(["210101", "Banco", "Saldo Inicial--->", 0])
    s.append(["2026-01-03", 3, "CP", 3, "", "Pago", 0, 15, 15])
    s.append(["Saldo Final de la Cuenta-------->", 15])
    s.append([None, None, None, None, None, "Totales  -------->", total, 15])
    w.save(path)


def test_mayor_secciones_concilia_y_no_cuenta_saldos(tmp_path):
    src, dst = tmp_path / "origen.xlsx", tmp_path / "normalizado.csv"
    _libro(src)
    r = transformar_mayor_secciones(src, dst)
    assert r["cuentas"] == 2
    assert r["movimientos"] == 3
    assert r["debe"] == "15"
    assert r["haber"] == "15"
    assert r["cuadra_reporte"] is True
    lines = dst.read_text().splitlines()
    assert len(lines) == 4
    assert lines[1].startswith("110101,")
    assert lines[3].startswith("210101,")


def test_mayor_secciones_detecta_desbalance(tmp_path):
    src, dst = tmp_path / "origen.xlsx", tmp_path / "normalizado.csv"
    _libro(src, total=99)
    r = transformar_mayor_secciones(src, dst)
    assert r["cuadra_reporte"] is False
