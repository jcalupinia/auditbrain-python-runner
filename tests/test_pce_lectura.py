"""Lectura de importes y fechas de los archivos del cliente."""
from datetime import date, datetime

import pytest

from backend.app.aud.pce_cxc.lectura import a_fecha, a_numero, inferir_formato_fecha


@pytest.mark.parametrize("entrada,esperado", [
    ("1234.56", 1234.56), ("1,234.56", 1234.56), ("1.234,56", 1234.56),
    ("8.917.458,00", 8917458.00), ("8,917,458.00", 8917458.00),
    ("(1.500,00)", -1500.00), ("-987,65", -987.65), ("USD 4 758 048,77", 4758048.77),
    ("1.500", 1500.0), ("", 0.0), (None, 0.0), (1234.56, 1234.56),
])
def test_importes_en_cualquier_formato(entrada, esperado):
    assert a_numero(entrada) == pytest.approx(esperado, abs=0.005)


def test_formato_de_fecha_deducido_del_propio_archivo():
    assert inferir_formato_fecha(["31/12/2025", "05/03/2025"]) == "dmy"
    assert inferir_formato_fecha(["12/31/2025", "03/05/2025"]) == "mdy"
    assert inferir_formato_fecha(["05/03/2025", "07/11/2025"]) == "ambiguo"
    assert inferir_formato_fecha(["31/12/2025", "12/31/2025"]) == "inconsistente"
    assert inferir_formato_fecha([datetime(2025, 12, 31)]) == "nativo"


def test_lectura_de_fechas_segun_el_formato():
    assert a_fecha("31/12/2025", "dmy") == date(2025, 12, 31)
    assert a_fecha("12/31/2025", "mdy") == date(2025, 12, 31)
    assert a_fecha("2025-12-31") == date(2025, 12, 31)
    assert a_fecha(datetime(2025, 12, 31)) == date(2025, 12, 31)
    assert a_fecha("no es fecha") is None
    assert a_fecha(None) is None


@pytest.mark.parametrize("entrada,esperado", [
    ("8.917.458", 8917458.0), ("1,234,567", 1234567.0), ("12.345.678,90", 12345678.90),
])
def test_miles_multiples_sin_decimales(entrada, esperado):
    assert a_numero(entrada) == pytest.approx(esperado, abs=0.005)


def test_sin_fechas_parseables_el_formato_es_ambiguo():
    assert inferir_formato_fecha([]) == "ambiguo"
    assert inferir_formato_fecha(["", None, "sin fecha"]) == "ambiguo"


def test_mezcla_de_fechas_nativas_y_texto_es_inconsistente():
    assert inferir_formato_fecha([datetime(2025, 12, 31), "05/03/2025"]) == "inconsistente"
