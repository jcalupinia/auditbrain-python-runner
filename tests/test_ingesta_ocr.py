"""Fase 4 del Motor de Ingesta: cableado de OCR a los parsers SRI.

Se prueba con dependencias inyectadas (fake `smart`, fake `extraer`, fake
`casilleros_fn`): no requiere pdfplumber ni Google Vision. Verifica el mapeo de
método, la recuperación de casilleros por OCR y la integración en el orquestador.
"""
from __future__ import annotations

from decimal import Decimal

from backend.app.ingesta import (
    DatasetNormalizado,
    MetodoExtraccion,
    NivelConfianza,
    TipoDocumento,
    extraer_texto,
    ingerir,
    recuperar_por_ocr,
)
from backend.app.ingesta.ocr_support import TextoDocumento


# --------------------------------------------------------------------------- #
#  extraer_texto (mapeo de método, sin tocar disco real de Vision)            #
# --------------------------------------------------------------------------- #
class TestExtraerTexto:
    def test_pdfplumber_es_nativo(self):
        smart = lambda path: {"text": "hola", "method": "pdfplumber", "pages": 1, "ocr_units_used": 0}
        td = extraer_texto(b"%PDF-1.4...", "f.pdf", smart=smart)
        assert td.metodo is MetodoExtraccion.NATIVO
        assert td.texto == "hola" and td.disponible is True

    def test_ocr_vision(self):
        smart = lambda path: {"text": "escaneado", "method": "ocr", "pages": 2, "ocr_units_used": 2}
        td = extraer_texto(b"...", "f.pdf", smart=smart)
        assert td.metodo is MetodoExtraccion.OCR
        assert td.ocr_units == 2 and td.disponible is True

    def test_ocr_no_disponible(self):
        smart = lambda path: {"text": "", "method": "ocr_failed_fallback", "pages": 0, "ocr_units_used": 0}
        td = extraer_texto(b"...", "f.pdf", smart=smart)
        assert td.disponible is False
        assert td.nota and "no disponible" in td.nota

    def test_smart_que_falla_no_lanza(self):
        def smart(path):
            raise RuntimeError("vision caído")
        td = extraer_texto(b"...", "f.pdf", smart=smart)
        assert td.texto == "" and td.disponible is False
        assert "falló" in (td.nota or "")


# --------------------------------------------------------------------------- #
#  recuperar_por_ocr (con casilleros_fn inyectado)                            #
# --------------------------------------------------------------------------- #
def _extraer_ok(contenido, filename):
    return TextoDocumento(texto="RETENCIONES ...", metodo=MetodoExtraccion.OCR, paginas=1)


def _extraer_vacio(contenido, filename):
    return TextoDocumento(texto="", metodo=MetodoExtraccion.OCR, disponible=False)


class TestRecuperarPorOCR:
    def test_recupera_casilleros_f103(self):
        cas = lambda texto: {"periodo": "2025-01", "casilleros": {"302": 178259.63, "349": 620109.94}}
        ds = recuperar_por_ocr(
            TipoDocumento.F103, b"...", "f103_enero.pdf",
            extraer=_extraer_ok, casilleros_fn=cas,
        )
        assert ds is not None
        assert len(ds.campos) == 2
        c = ds.campos[0]
        assert c.extraction_method is MetodoExtraccion.OCR
        assert c.confidence is NivelConfianza.MEDIUM
        assert c.normalized_value == Decimal("178259.63")
        assert ds.review_required is True
        assert any("OCR" in w for w in ds.warnings)

    def test_tipo_no_recuperable_devuelve_none(self):
        ds = recuperar_por_ocr(
            TipoDocumento.MAYOR, b"...", "mayor.xlsx",
            extraer=_extraer_ok, casilleros_fn=lambda t: {"casilleros": {"1": 1}},
        )
        assert ds is None

    def test_sin_texto_devuelve_none(self):
        ds = recuperar_por_ocr(
            TipoDocumento.F101, b"...", "f101.pdf",
            extraer=_extraer_vacio, casilleros_fn=lambda t: {"casilleros": {"x": 1}},
        )
        assert ds is None

    def test_sin_casilleros_devuelve_none(self):
        ds = recuperar_por_ocr(
            TipoDocumento.F103, b"...", "f103.pdf",
            extraer=_extraer_ok, casilleros_fn=lambda t: {"casilleros": {}},
        )
        assert ds is None


# --------------------------------------------------------------------------- #
#  Integración en el orquestador                                               #
# --------------------------------------------------------------------------- #
def _extractor_vacio(contenido, filename):
    # Simula un parser que no recuperó nada (PDF escaneado).
    return DatasetNormalizado(
        dataset_id=filename, source_file=filename, document_type=TipoDocumento.F103,
        quality_score=0.0, exceptions=["el parser no devolvió datos"],
    )


def _extractor_ok(contenido, filename):
    return DatasetNormalizado(
        dataset_id=filename, source_file=filename, document_type=TipoDocumento.F103,
        quality_score=1.0, rows=[{"cas_302": 178259.63}],
    )


class TestIntegracionOrquestador:
    def test_ocr_se_activa_cuando_el_extractor_no_recupera(self):
        from backend.app.ingesta.contract import CampoExtraido

        def recuperador(tipo, contenido, filename):
            return DatasetNormalizado(
                dataset_id=filename, source_file=filename, document_type=tipo,
                quality_score=0.75, extraction_method=MetodoExtraccion.OCR,
                campos=[CampoExtraido(
                    document_id=filename, field="cas_302",
                    confidence=NivelConfianza.MEDIUM,
                    extraction_method=MetodoExtraccion.OCR,
                )],
                review_required=True,
            )

        ds = ingerir(
            "f103_enero.pdf", b"...", tipo_declarado="f103",
            extractores={TipoDocumento.F103: _extractor_vacio},
            recuperar_ocr=recuperador,
        )
        assert ds.extraction_method is MetodoExtraccion.OCR
        assert ds.campos and ds.campos[0].extraction_method is MetodoExtraccion.OCR
        assert ds.review_required is True
        assert ds.sello is not None

    def test_ocr_no_se_activa_si_el_extractor_recupero(self):
        llamado = {"ocr": False}

        def recuperador(tipo, contenido, filename):
            llamado["ocr"] = True
            return None

        ds = ingerir(
            "f103_enero.pdf", b"...", tipo_declarado="f103",
            extractores={TipoDocumento.F103: _extractor_ok},
            recuperar_ocr=recuperador,
        )
        assert llamado["ocr"] is False   # no se intentó OCR porque ya había datos
        assert ds.rows

    def test_ocr_sin_recuperacion_agrega_warning(self):
        ds = ingerir(
            "f103_enero.pdf", b"...", tipo_declarado="f103",
            extractores={TipoDocumento.F103: _extractor_vacio},
            recuperar_ocr=lambda tipo, c, f: None,
        )
        assert any("OCR no recuperó datos" in w for w in ds.warnings)
        assert ds.review_required is True

    def test_ocr_desactivable(self):
        llamado = {"ocr": False}

        def recuperador(tipo, contenido, filename):
            llamado["ocr"] = True
            return None

        ingerir(
            "f103_enero.pdf", b"...", tipo_declarado="f103",
            extractores={TipoDocumento.F103: _extractor_vacio},
            recuperar_ocr=recuperador, ocr=False,
        )
        assert llamado["ocr"] is False
