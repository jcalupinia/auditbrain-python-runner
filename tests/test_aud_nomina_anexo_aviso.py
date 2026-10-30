"""Aviso de cuentas de pasivo del anexo NO reconocidas (Fase 2 del desacople de PROPHAR).

El anexo (RQ-002) es el mapa de cuentas de cada cliente. Cuando una cuenta de pasivo del anexo
tiene una descripción que el motor no reconoce, NO se inventa ni se descarta en silencio: se
registra en ``ANEXO_PASIVO_NO_RECONOCIDO`` para que la sumaria la avise y el auditor confirme a
qué concepto corresponde (decisión del dueño, 2026-10-30).

Sin datos de cliente: códigos y descripciones genéricos.
"""
from openpyxl import Workbook

from backend.app.aud.niif.procesadores.nomina import perfil_cuentas as pc


def _anexo(tmp_path, filas):
    p = tmp_path / "anexo.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Código", "Descripción", "Saldo ant", "", "", "Saldo corte"])
    ws.append([None] * 6)   # fila de fechas (vacía)
    for f in filas:
        ws.append(f)
    wb.save(p)
    return str(p)


def test_pasivo_no_reconocido_se_registra_para_avisar(tmp_path):
    p = _anexo(tmp_path, [
        ["2.01.07.03.01", "APORTE PATRONAL Y PERSONAL", 100, "", "", 120],  # reconocida
        ["2.01.07.03.02", "PRESTAMOS IESS", 50, "", "", 60],                # NO reconocida
    ])
    pc.reescribir_anexo(p, str(tmp_path / "adapt.xlsx"))
    cods = [c for c, *_ in pc.ANEXO_PASIVO_NO_RECONOCIDO]
    assert "2.01.07.03.02" in cods      # la no reconocida se registra (para el aviso)
    assert "2.01.07.03.01" not in cods  # la reconocida NO


def test_plan_de_referencia_no_genera_aviso(tmp_path):
    # Códigos canónicos (5BS/5PYG, como PROPHAR) no entran a la rama de pasivo «2…»:
    # ANEXO_PASIVO_NO_RECONOCIDO queda vacío → PROPHAR no muestra el aviso.
    p = _anexo(tmp_path, [
        ["5BS.21203.001", "Aporte Patronal", -100, "", "", -120],
        ["5PYG.53101.001", "Sueldos", 500, "", "", 480],
    ])
    pc.reescribir_anexo(p, str(tmp_path / "adapt.xlsx"))
    assert pc.ANEXO_PASIVO_NO_RECONOCIDO == []
