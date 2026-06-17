"""Salvaguarda de codificación del parser de balances internos.

Verifica que `_fix_mojibake` repara el mojibake clásico "UTF-8 leído como
Windows-1252" (p.ej. "AÃ‘O" -> "AÑO") y, CRÍTICO, que NO altera texto que ya
está correcto (incluidos nombres legítimos con Ñ/tildes y con 'Ã' real).
"""

from backend.app.tax.planificacion_utilidades.parsers.balance_interno import (
    _fix_mojibake,
    _add_det,
)


def _moji(s: str) -> str:
    """Construye el mojibake real: UTF-8 correcto decodificado como cp1252."""
    return s.encode("utf-8").decode("cp1252")


def test_repara_enie_mayuscula():
    roto = _moji("GANANCIAS ACUMULADAS AÑO N")
    assert "Ã" in roto  # precondición: está corrompido
    assert _fix_mojibake(roto) == "GANANCIAS ACUMULADAS AÑO N"


def test_repara_varios_acentos_y_enie():
    for original in [
        "AGASAJO NAVIDEÑO",
        "CONTRIBUCION SUPERINTENDENCIA DE COMPAÑIAS",
        "BONOS POR DESEMPEÑO",
        "Gestión de Operación · Logística",
        "DÉBITOS Y CRÉDITOS",
    ]:
        assert _fix_mojibake(_moji(original)) == original


def test_no_altera_texto_ya_correcto():
    # Texto UTF-8 correcto con Ñ/tildes NO debe tocarse (no contiene 'Ã').
    for ok in [
        "GANANCIAS ACUMULADAS AÑO N",
        "GAL- SERVICIOS DE AMA DE LLAVES",
        "CAÑON DEL PASTAZA",
        "Depreciación acumulada edificios",
        "",
    ]:
        assert _fix_mojibake(ok) == ok


def test_no_altera_ascii_puro():
    assert _fix_mojibake("BANCO PACIFICO CTA CTE 5334907") == "BANCO PACIFICO CTA CTE 5334907"


def test_a_tilde_legitima_no_se_rompe():
    # 'Ã' seguido de algo que NO forma UTF-8 válido -> se deja intacto.
    assert _fix_mojibake("ÃREA TECNICA") == "ÃREA TECNICA"


def test_add_det_aplica_el_fix():
    det: dict = {}
    _add_det(det, "resultado", "gAdmin", "5.1.04", _moji("GAL - AGASAJO NAVIDEÑO"), 0, 100.0, 3)
    (entry,) = det.values()
    assert entry["nombre"] == "GAL - AGASAJO NAVIDEÑO"
