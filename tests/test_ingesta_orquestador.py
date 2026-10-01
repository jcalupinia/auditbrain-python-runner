"""Fase 2 del Motor de Ingesta: clasificador determinista + orquestador.

Se prueba con extractores FALSOS (no toca los parsers pesados con pdfplumber/
openpyxl). Verifica la escalera determinística del clasificador y que el
orquestador nunca tumbe la ingesta por un documento problemático.
"""
from __future__ import annotations

from backend.app.ingesta import (
    DatasetNormalizado,
    NivelConfianza,
    TipoDocumento,
    clasificar_documento,
    extractores_por_defecto,
    ingerir,
)
from backend.app.ingesta.classifier import ResultadoClasificacion


# --------------------------------------------------------------------------- #
#  Clasificador                                                                #
# --------------------------------------------------------------------------- #
class TestClasificador:
    def test_tipo_declarado_por_slot_manda(self):
        r = clasificar_documento("cualquier.pdf", tipo_declarado="f104")
        assert r.tipo is TipoDocumento.F104
        assert r.confidence is NivelConfianza.HIGH

    def test_tipo_declarado_por_valor_enum(self):
        r = clasificar_documento("x.pdf", tipo_declarado="mayor")
        assert r.tipo is TipoDocumento.MAYOR
        assert r.confidence is NivelConfianza.HIGH

    def test_tipo_declarado_desconocido_cae_a_nombre(self):
        r = clasificar_documento("F103_enero.pdf", tipo_declarado="xyz")
        assert r.tipo is TipoDocumento.F103
        assert any("no reconocido" in s for s in r.razones)

    def test_firma_contenido_xml_ats(self):
        xml = b'<?xml version="1.0"?><iva><detalleCompras></detalleCompras></iva>'
        r = clasificar_documento("reporte.xml", contenido=xml)
        assert r.tipo is TipoDocumento.ATS
        assert r.confidence is NivelConfianza.HIGH

    def test_firma_contenido_xml_comprobante(self):
        xml = b'<?xml version="1.0"?><factura id="comprobante"></factura>'
        r = clasificar_documento("doc.xml", contenido=xml)
        assert r.tipo is TipoDocumento.COMPROBANTE_SRI

    def test_firma_contenido_texto_formulario_104(self):
        txt = "FORMULARIO 104 declaracion del impuesto al valor agregado".encode()
        r = clasificar_documento("escaneo.pdf", contenido=txt)
        assert r.tipo is TipoDocumento.F104

    def test_nombre_f103(self):
        r = clasificar_documento("F103_febrero_2025.pdf")
        assert r.tipo is TipoDocumento.F103
        assert r.confidence is NivelConfianza.MEDIUM

    def test_nombre_mayor(self):
        r = clasificar_documento("Libro_Mayor_2025.xlsx")
        assert r.tipo is TipoDocumento.MAYOR

    def test_nombre_contrato(self):
        r = clasificar_documento("contrato_arrendamiento_bodega.pdf")
        assert r.tipo is TipoDocumento.CONTRATO

    def test_solo_extension_xml_es_ambiguo(self):
        r = clasificar_documento("1234567890.xml")
        assert r.tipo is TipoDocumento.COMPROBANTE_SRI
        assert r.confidence is NivelConfianza.LOW

    def test_desconocido_va_a_revision(self):
        r = clasificar_documento("archivo_raro.bin")
        assert r.tipo is TipoDocumento.DESCONOCIDO
        assert r.confidence is NivelConfianza.REVIEW_REQUIRED

    def test_resultado_es_pydantic(self):
        r = clasificar_documento("f101.pdf", tipo_declarado="f101")
        assert isinstance(r, ResultadoClasificacion)


# --------------------------------------------------------------------------- #
#  Orquestador (con extractores falsos)                                        #
# --------------------------------------------------------------------------- #
def _fake_ok(contenido: bytes, filename: str) -> DatasetNormalizado:
    return DatasetNormalizado(
        dataset_id=filename, source_file=filename,
        document_type=TipoDocumento.F104, quality_score=0.99,
        rows=[{"cas_799": 100.0}],
    )


def _fake_vacio(contenido: bytes, filename: str) -> DatasetNormalizado:
    # No fija document_type (DESCONOCIDO) para probar que el orquestador lo completa.
    return DatasetNormalizado(dataset_id="", source_file=filename, quality_score=0.99)


def _fake_explota(contenido: bytes, filename: str) -> DatasetNormalizado:
    raise RuntimeError("parser roto")


class TestOrquestador:
    def test_ingesta_feliz_sella_y_marca_tipo(self):
        ds = ingerir(
            "f104_julio.pdf", b"...", tipo_declarado="f104",
            extractores={TipoDocumento.F104: _fake_ok},
        )
        assert ds.document_type is TipoDocumento.F104
        assert ds.sello is not None and len(ds.sello.sha256) == 64
        assert ds.review_required is False
        assert any("clasificación=" in w for w in ds.warnings)

    def test_orquestador_completa_tipo_y_dataset_id(self):
        ds = ingerir(
            "f104_julio.pdf", b"...", tipo_declarado="f104",
            extractores={TipoDocumento.F104: _fake_vacio},
        )
        assert ds.document_type is TipoDocumento.F104
        assert ds.dataset_id == "f104_julio.pdf"

    def test_sin_extractor_va_a_revision(self):
        ds = ingerir(
            "f104_julio.pdf", b"...", tipo_declarado="f104",
            extractores={},  # registro vacío
        )
        assert ds.review_required is True
        assert any("no hay extractor" in w for w in ds.warnings)
        assert ds.quality_score == 0.0

    def test_extractor_que_falla_no_tumba_la_ingesta(self):
        ds = ingerir(
            "f104_julio.pdf", b"...", tipo_declarado="f104",
            extractores={TipoDocumento.F104: _fake_explota},
        )
        assert ds.review_required is True
        assert any("extractor falló" in e for e in ds.exceptions)
        assert ds.sello is not None

    def test_clasificacion_dudosa_contagia_revision(self):
        # "1234.xml" → COMPROBANTE_SRI con confianza LOW; aunque el extractor
        # devuelva calidad alta, el dataset queda en revisión.
        ds = ingerir(
            "1234567890.xml", b"<factura></factura>".replace(b"factura", b"x"),
            extractores={TipoDocumento.COMPROBANTE_SRI: _fake_ok},
        )
        assert ds.review_required is True

    def test_sin_sellar_si_se_pide(self):
        ds = ingerir(
            "f104.pdf", b"...", tipo_declarado="f104",
            extractores={TipoDocumento.F104: _fake_ok}, sellar=False,
        )
        assert ds.sello is None


class TestRegistroPorDefecto:
    def test_registro_tiene_los_tipos_esperados(self):
        reg = extractores_por_defecto()
        esperados = {
            TipoDocumento.F101, TipoDocumento.F103, TipoDocumento.F104,
            TipoDocumento.ATS, TipoDocumento.BALANCE, TipoDocumento.MAYOR,
            TipoDocumento.KARDEX, TipoDocumento.FACTURACION,
        }
        assert esperados.issubset(set(reg.keys()))
        assert all(callable(v) for v in reg.values())
