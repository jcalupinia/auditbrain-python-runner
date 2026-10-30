"""Las cédulas muestran las cuentas REALES del cliente, no las de PROPHAR.

``reescribir_anexo`` puebla ``perfil_cuentas.MAPA_PRESENTACION`` con el código y el nombre
REALES del cliente por cada cuenta de pasivo que mapea a un código canónico del motor. Así la
sumaria (y las demás cédulas que lo usen) muestran la cuenta del cliente en vez de disfrazarla
con los códigos de PROPHAR. Para el plan de referencia (PROPHAR) el anexo ya trae los códigos
reales, el mapa queda vacío y la presentación usa el código tal cual.

Sin datos de cliente: códigos y descripciones genéricas.
"""
from openpyxl import Workbook

from backend.app.aud.niif.procesadores.nomina import perfil_cuentas as pc


def _anexo(tmp_path, filas):
    p = tmp_path / "anexo.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Anexo de nómina"])
    ws.append([None, None, "2024-12-31", None, None, "2025-12-31"])
    ws.append(["Código", "Descripción", "Saldo anterior", None, None, "Saldo corte"])
    for f in filas:
        ws.append(f)
    wb.save(p)
    return str(p)


def test_mapa_presentacion_guarda_los_codigos_reales_del_cliente(tmp_path):
    pc.MAPA_PRESENTACION.clear()
    p = _anexo(tmp_path, [
        ["2.01.07.03.01", "Aporte patronal y personal por pagar", 100, None, None, 120],
        ["2.01.07.01.01", "Décimo tercero por pagar", 10, None, None, 12],
        ["5.2.02.01.01", "Sueldos", 0, None, None, 0],   # gasto: ya es código real
    ])
    pc.reescribir_anexo(p, str(tmp_path / "anexo_adaptado.xlsx"))
    reales = [cod for lst in pc.MAPA_PRESENTACION.values() for cod, _ in lst]
    assert "2.01.07.03.01" in reales
    assert "2.01.07.01.01" in reales
    # Se guarda el código REAL del cliente, nunca el canónico de PROPHAR.
    assert all(not c.startswith("5BS") for c in reales)


def test_plan_de_referencia_no_puebla_el_mapa(tmp_path):
    # Un anexo que ya viene en el plan del motor (PROPHAR, pasivo en «5BS.212») no se remapea por
    # «2.»: el mapa de presentación queda vacío → la cédula muestra el código tal cual.
    pc.MAPA_PRESENTACION.clear()
    p = _anexo(tmp_path, [
        ["5BS.21204.001", "Décimo Tercer Sueldo", 10, None, None, 12],
    ])
    pc.reescribir_anexo(p, str(tmp_path / "anexo_adaptado.xlsx"))
    assert pc.MAPA_PRESENTACION == {}
