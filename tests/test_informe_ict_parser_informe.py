# tests/test_ict_report_parser_informe.py
from pathlib import Path

from backend.app.aud.informe_cumplimiento_tributario.parsers import (
    informe_auditoria_externa as iae,
)

FIXTURES = Path(__file__).parent / "fixtures" / "informe_cumplimiento_tributario"


def test_parse_informe_real_axxis():
    data = iae.parse((FIXTURES / "informe_auditoria_externa_axxis.pdf").read_bytes())
    assert data["fecha_emision"] == "27 de febrero de 2026"  # 'del' normalizado
    assert data["marco_contable"] == "pymes"
    assert data["errores"] == []


def test_marco_plenas_por_defecto_si_no_dice_pymes():
    # texto sintético sin 'PYMES'
    txt = "INFORME DE LOS AUDITORES INDEPENDIENTES\n01 de marzo de 2026\nNIIF plenas"
    assert iae._marco_contable(txt) == "plenas"


def test_parse_informe_garbage_degrada():
    data = iae.parse(b"%PDF-1.4 no es un informe")
    assert data["fecha_emision"] is None
    assert data["marco_contable"] in ("pymes", "plenas")
    assert data["errores"]
