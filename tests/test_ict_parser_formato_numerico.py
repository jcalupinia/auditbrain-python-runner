"""REGLA del proyecto — los parsers SRI aceptan cualquier formato numérico.

El cliente puede tener su computadora configurada con `.` o con `,` como
separador decimal. Los parsers deben extraer valores correctamente sin
importar el formato del PDF.

Bug detectado 2026-06-04: el regex `\\d{1,3}` del parser F-103 capturaba
solo los primeros 3 dígitos de "183724.10" → "183" → 183.0 en lugar de
183,724.10. Causaba que la pestaña DATOS F-103 mostrara TODOS los valores
en 0.00.

Estos tests blindan contra ese patrón.
"""
from backend.app.ict.parsers.f103_pdf import _extract_casilleros, _parse_amount
from backend.app.aud.obligaciones_fiscales.cedulas.base import _parse_amount_sri


class TestParseAmountFormatosNumericos:
    """_parse_amount debe aceptar TODOS los formatos: US, europeo, plano."""

    def test_formato_us_con_coma_miles(self):
        assert _parse_amount("178,259.63") == 178259.63

    def test_formato_europeo_con_punto_miles(self):
        assert _parse_amount("178.259,63") == 178259.63

    def test_formato_plano_sin_separador_de_miles(self):
        assert _parse_amount("183724.10") == 183724.10

    def test_formato_plano_grande(self):
        assert _parse_amount("637268.59") == 637268.59

    def test_formato_us_tres_grupos(self):
        assert _parse_amount("1,234,567.89") == 1234567.89

    def test_formato_europeo_tres_grupos(self):
        assert _parse_amount("1.234.567,89") == 1234567.89

    def test_cero_con_decimal(self):
        assert _parse_amount("0.00") == 0.0
        assert _parse_amount("0,00") == 0.0

    def test_negativo(self):
        assert _parse_amount("-150.00") == -150.0
        assert _parse_amount("-178,259.63") == -178259.63

    def test_coma_decimal_sin_miles(self):
        assert _parse_amount("25,50") == 25.5

    def test_entero(self):
        assert _parse_amount("100") == 100.0

    def test_vacio(self):
        assert _parse_amount("") is None
        assert _parse_amount(None) is None


class TestParseAmountSriBase:
    """_parse_amount_sri en base.py debe tener el mismo comportamiento."""

    def test_formato_us(self):
        assert _parse_amount_sri("178,259.63") == 178259.63

    def test_formato_europeo(self):
        assert _parse_amount_sri("178.259,63") == 178259.63

    def test_formato_plano(self):
        assert _parse_amount_sri("183724.10") == 183724.10

    def test_coma_decimal(self):
        assert _parse_amount_sri("25,50") == 25.5


class TestExtractCasillerosF103:
    """_extract_casilleros debe extraer correctamente del texto del PDF F-103.

    Regresión del bug: cas 302 con valor "183724.10" devolvía 183.0.
    """

    def test_cas_con_valor_grande_sin_separador_de_miles(self):
        """Reproduce el formato exacto del PDF PROPHAR febrero 2025:
        '302 183724.10 352 8908.25'"""
        text = "302 183724.10 352 8908.25"
        res = _extract_casilleros(text)
        # Cas 302 debe capturar 183724.10 COMPLETO (no 183)
        assert res.get("302") == 183724.10, (
            f"cas 302 capturó {res.get('302')}, esperado 183724.10. "
            "Bug histórico: regex \\d{1,3} cortaba a 183."
        )
        assert res.get("352") == 8908.25

    def test_cas_con_coma_separador_de_miles(self):
        text = "302 183,724.10 352 8,908.25"
        res = _extract_casilleros(text)
        assert res.get("302") == 183724.10
        assert res.get("352") == 8908.25

    def test_cas_con_punto_separador_de_miles_formato_europeo(self):
        text = "302 183.724,10 352 8.908,25"
        res = _extract_casilleros(text)
        assert res.get("302") == 183724.10
        assert res.get("352") == 8908.25

    def test_cas_con_cero(self):
        text = "302 0.00 352 0.00"
        res = _extract_casilleros(text)
        assert res.get("302") == 0.0
        assert res.get("352") == 0.0


class TestExtractCasillerosPDFRealPROPHAR:
    """Verificación empírica con PDF real del cliente PROPHAR (febrero 2025).

    El PDF está en C:\\Users\\jcalu\\Downloads\\Información PROPHAR\\... y
    NO se commit al repo. Si el path no existe (CI), el test se skipea.
    """

    PDF_PATH = (
        r"C:\Users\jcalu\Downloads\Información PROPHAR"
        r"\Información PROPHAR\103\02 103.pdf"
    )

    def test_parse_pdf_real_prophar_extrae_valores_reales(self):
        import os
        import pytest
        if not os.path.exists(self.PDF_PATH):
            pytest.skip(f"PDF real no disponible (CI): {self.PDF_PATH}")
        from backend.app.ict.parsers.f103_pdf import parse_f103
        with open(self.PDF_PATH, "rb") as f:
            result = parse_f103(f.read())
        assert result is not None, "parse_f103 devolvió None con PDF real"
        assert result["periodo"] == "2025-02"
        cas = result["casilleros"]
        # Valores verificados manualmente del PDF (febrero 2025 PROPHAR)
        assert cas["302"] == 183724.10, (
            f"cas 302 = {cas.get('302')}, esperado 183724.10. "
            "Regresión del bug 2026-06-04."
        )
        assert cas["352"] == 8908.25
        assert cas["999"] == 18572.74  # TOTAL PAGADO
