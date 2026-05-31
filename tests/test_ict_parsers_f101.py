"""Tests for F-101 PDF parser."""
from backend.app.ict.parsers.f101_pdf import parse_f101, ALL_F101_CASILLEROS


def test_all_f101_casilleros_includes_required_for_a1_a9():
    required_a1 = {"311", "315", "325", "336", "337", "339", "342", "343", "358", "361", "362", "499", "513", "534", "699"}
    required_a9 = {"7001", "7010", "7013", "7022", "7025", "7028", "7031", "7034", "7037"}
    required_a3 = {"6999", "7185", "7186", "7992", "7182", "7183", "7173", "7174"}

    assert required_a1.issubset(set(ALL_F101_CASILLEROS))
    assert required_a9.issubset(set(ALL_F101_CASILLEROS))
    assert required_a3.issubset(set(ALL_F101_CASILLEROS))


def test_parse_f101_returns_empty_for_invalid_pdf():
    result = parse_f101(b"not a pdf")
    assert result["casilleros"] == {}
    assert "errores" in result
    assert len(result["errores"]) > 0


def test_parse_f101_handles_empty_text():
    empty_pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\nxref\n0 1\ntrailer<<>>\nstartxref\n0\n%%EOF\n"
    result = parse_f101(empty_pdf)
    assert "casilleros" in result
    assert "errores" in result
