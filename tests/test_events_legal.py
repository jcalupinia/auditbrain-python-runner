from backend.app.events.legal import data_protection_text


def test_data_protection_text_includes_contact_and_law():
    txt = data_protection_text("datos@x.ec")
    assert "datos@x.ec" in txt
    assert "Protección de Datos Personales" in txt
    assert "Audit Consulting Group" in txt
