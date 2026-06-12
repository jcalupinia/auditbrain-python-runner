import pytest
from pydantic import ValidationError

from backend.app.events.schemas import RegistrationCreate


def _valid(**over):
    base = dict(
        nombre="María Pérez",
        email="maria@empresa.ec",
        telefono="0987654321",
        telefono_pais="+593",
        documento="1791240154001",
        empresa="Empresa S.A.",
    )
    base.update(over)
    return RegistrationCreate(**base)


def test_phone_normalized_to_e164_strips_leading_zero():
    m = _valid()
    assert m.telefono_e164 == "+593987654321"


def test_phone_accepts_spaces_and_dashes():
    m = _valid(telefono="098-765 4321")
    assert m.telefono_e164 == "+593987654321"


def test_documento_cedula_10_ok():
    m = _valid(documento="1712345678")
    assert m.documento == "1712345678"


def test_documento_invalid_length_rejected():
    with pytest.raises(ValidationError):
        _valid(documento="12345")


def test_email_invalid_rejected():
    with pytest.raises(ValidationError):
        _valid(email="no-es-email")


def test_nombre_too_short_rejected():
    with pytest.raises(ValidationError):
        _valid(nombre="A")
