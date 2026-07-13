import textwrap

from backend.app.client_portal.flujo import catalogos


def _csv(tmp_path):
    p = tmp_path / "plan.csv"
    p.write_text(textwrap.dedent("""\
        codigo_super_cias,nombre_cuenta,codigo_sri,nombre_sri
        1010101,CAJA,311,Efectivo y equivalentes
        1010103,INSTITUCIONES FINANCIERAS PRIVADAS,311,Efectivo y equivalentes
        40101,VENTA DE BIENES,6001,Gravadas tarifa distinta 0%
        40101,VENTA DE BIENES,6003,Gravadas tarifa 0%
        """), encoding="utf-8")
    return str(p)


def test_mapa_super_a_sri_soporta_1_a_n(tmp_path):
    m = catalogos.cargar_mapa_super_sri(_csv(tmp_path))
    assert m["super_a_sri"]["1010101"] == ["311"]
    assert m["super_a_sri"]["40101"] == ["6001", "6003"]


def test_mapa_sri_a_super_y_nombres(tmp_path):
    m = catalogos.cargar_mapa_super_sri(_csv(tmp_path))
    assert set(m["sri_a_super"]["311"]) == {"1010101", "1010103"}
    assert m["nombre_super"]["1010101"] == "CAJA"
    assert m["nombre_sri"]["6001"] == "Gravadas tarifa distinta 0%"


def test_mapa_usa_csv_real_por_defecto():
    m = catalogos.cargar_mapa_super_sri()
    assert m["super_a_sri"] and m["nombre_super"]
