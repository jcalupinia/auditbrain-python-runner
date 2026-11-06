from decimal import Decimal
import pytest

from backend.app.ingesta.mapeo.mayores_auto import proponer_mapeo, separar_importe_firmado


def test_encabezados_mayor_importe_firmado():
    r = proponer_mapeo(["Nºcuenta", "Descripción", "Fecha L/M", "Importe"])
    assert r["mapeo"]["cuenta"] == 0
    assert r["mapeo"]["fecha"] == 2
    assert r["mapeo"]["importe"] == 3
    assert r["modo"] == "importe_firmado"
    assert r["requiere_revision"]


def test_debe_haber_estandar():
    r = proponer_mapeo(["Cuenta", "Fecha", "Debe", "Haber"])
    assert r["modo"] == "debe_haber"
    assert not r["requiere_revision"]


def test_ambiguedad_no_se_resuelve_arbitrariamente():
    r = proponer_mapeo(["Cuenta", "Codigo Cuenta", "Fecha", "Debe", "Haber"])
    assert r["requiere_revision"]
    assert "cuenta" in r["ambiguos"]


@pytest.mark.parametrize("importe,esperado", [
    ("125.50", (Decimal("125.50"), Decimal("0"))),
    ("-30", (Decimal("0"), Decimal("30"))),
    ("0", (Decimal("0"), Decimal("0"))),
])
def test_polaridad_confirmada(importe, esperado):
    assert separar_importe_firmado(importe, positivo_es="debe") == esperado


def test_sin_polaridad_confirmada_rechaza():
    with pytest.raises(ValueError):
        separar_importe_firmado("10", positivo_es="auto")
