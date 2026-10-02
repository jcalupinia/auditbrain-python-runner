"""Fase 5 del Motor de Ingesta: Confidence Engine en vivo.

Verifica la consolidación del veredicto de confianza, el umbral de dudosos, la
integración en el orquestador y la cola de revisión.
"""
from __future__ import annotations

from backend.app.ingesta import (
    CampoExtraido,
    DatasetNormalizado,
    MetodoExtraccion,
    NivelConfianza,
    TipoDocumento,
    cola_de_revision,
    consolidar_confianza,
    ingerir,
    resumen_confianza,
)


def _campo(nivel: NivelConfianza, field: str = "c") -> CampoExtraido:
    return CampoExtraido(
        document_id="d", field=field, confidence=nivel,
        extraction_method=MetodoExtraccion.PARSER,
    )


def _ds(campos, quality=0.95, review=False) -> DatasetNormalizado:
    return DatasetNormalizado(
        dataset_id="ds", source_file="f.pdf", document_type=TipoDocumento.F103,
        campos=campos, quality_score=quality, review_required=review,
    )


# --------------------------------------------------------------------------- #
#  resumen_confianza                                                           #
# --------------------------------------------------------------------------- #
class TestResumen:
    def test_todos_altos_sin_revision(self):
        r = resumen_confianza(_ds([_campo(NivelConfianza.HIGH, "a"),
                                   _campo(NivelConfianza.HIGH, "b")]))
        assert r.veredicto is NivelConfianza.HIGH
        assert r.review_required is False
        assert r.dudosos == 0

    def test_peor_nivel_es_el_mas_severo(self):
        r = resumen_confianza(_ds([_campo(NivelConfianza.HIGH, "a"),
                                   _campo(NivelConfianza.MEDIUM, "b")]))
        assert r.peor_nivel is NivelConfianza.MEDIUM

    def test_un_campo_review_fuerza_revision(self):
        r = resumen_confianza(_ds([_campo(NivelConfianza.HIGH, "a"),
                                   _campo(NivelConfianza.REVIEW_REQUIRED, "b")]))
        assert r.review_required is True
        assert r.peor_nivel is NivelConfianza.REVIEW_REQUIRED

    def test_umbral_no_altos_supera_con_mediums(self):
        # Campos MEDIUM no fuerzan revisión por sí solos (el contrato solo fuerza
        # con LOW/REVIEW); pero si demasiados están por debajo de HIGH, el umbral
        # manda el dataset a revisión. 1 de 3 no-altos = 33% > 20%.
        campos = [_campo(NivelConfianza.HIGH, "a"), _campo(NivelConfianza.HIGH, "b"),
                  _campo(NivelConfianza.MEDIUM, "c")]
        r = resumen_confianza(_ds(campos))
        assert r.pct_no_altos > 0.20
        assert r.review_required is True

    def test_umbral_personalizado(self):
        # 9 HIGH + 1 MEDIUM = 10% no-altos. Con umbral 0.05 va a revisión; con 0.20 no
        # (ningún MEDIUM fuerza revisión por sí solo).
        campos = [_campo(NivelConfianza.HIGH, f"h{i}") for i in range(9)] + [
            _campo(NivelConfianza.MEDIUM, "x")]
        assert resumen_confianza(_ds(campos), umbral_pct_dudosos=0.05).review_required is True
        assert resumen_confianza(_ds(campos), umbral_pct_dudosos=0.20).review_required is False

    def test_sin_campos_usa_calidad(self):
        r_alta = resumen_confianza(_ds([], quality=0.98))
        assert r_alta.veredicto is NivelConfianza.HIGH and r_alta.review_required is False
        r_baja = resumen_confianza(_ds([], quality=0.3))
        assert r_baja.review_required is True


# --------------------------------------------------------------------------- #
#  consolidar_confianza                                                        #
# --------------------------------------------------------------------------- #
class TestConsolidar:
    def test_agrega_resultado_confianza(self):
        ds = consolidar_confianza(_ds([_campo(NivelConfianza.HIGH, "a")]))
        reglas = {r.regla: r for r in ds.validation_results}
        assert "confianza" in reglas and reglas["confianza"].ok is True

    def test_marca_revision_por_umbral(self):
        campos = [_campo(NivelConfianza.HIGH, "a"), _campo(NivelConfianza.LOW, "b")]
        ds = consolidar_confianza(_ds(campos))
        assert ds.review_required is True
        reglas = {r.regla: r for r in ds.validation_results}
        assert reglas["confianza"].ok is False

    def test_idempotente(self):
        ds = _ds([_campo(NivelConfianza.HIGH, "a")])
        consolidar_confianza(ds)
        consolidar_confianza(ds)
        confianzas = [r for r in ds.validation_results if r.regla == "confianza"]
        assert len(confianzas) == 1


# --------------------------------------------------------------------------- #
#  Integración en el orquestador                                               #
# --------------------------------------------------------------------------- #
class TestIntegracion:
    def test_ingerir_consolida_confianza(self):
        def extractor(contenido, filename):
            return DatasetNormalizado(
                dataset_id=filename, source_file=filename,
                document_type=TipoDocumento.F103, quality_score=0.95,
                campos=[_campo(NivelConfianza.HIGH, "cas_302")],
            )
        ds = ingerir("f103.pdf", b"...", tipo_declarado="f103",
                     extractores={TipoDocumento.F103: extractor})
        assert any(r.regla == "confianza" for r in ds.validation_results)

    def test_ingerir_consolidar_desactivable(self):
        def extractor(contenido, filename):
            return DatasetNormalizado(
                dataset_id=filename, source_file=filename,
                document_type=TipoDocumento.F103, quality_score=0.95,
                campos=[_campo(NivelConfianza.HIGH, "cas_302")],
            )
        ds = ingerir("f103.pdf", b"...", tipo_declarado="f103",
                     extractores={TipoDocumento.F103: extractor}, consolidar=False)
        assert all(r.regla != "confianza" for r in ds.validation_results)


# --------------------------------------------------------------------------- #
#  cola_de_revision                                                            #
# --------------------------------------------------------------------------- #
class TestColaRevision:
    def test_incluye_campos_dudosos(self):
        ds = _ds([_campo(NivelConfianza.HIGH, "a"),
                  _campo(NivelConfianza.LOW, "b"),
                  _campo(NivelConfianza.REVIEW_REQUIRED, "c")])
        cola = cola_de_revision([ds])
        fields = {i.field for i in cola}
        assert fields == {"b", "c"}
        assert all(i.dataset_id == "ds" for i in cola)

    def test_dataset_sin_campos_dudosos_pero_en_revision(self):
        ds = _ds([], quality=0.3)  # review por calidad baja, sin campos
        cola = cola_de_revision([ds])
        assert len(cola) == 1
        assert cola[0].field is None
        assert "revisión" in cola[0].motivo

    def test_dataset_limpio_no_entra_en_cola(self):
        ds = _ds([_campo(NivelConfianza.HIGH, "a")])
        assert cola_de_revision([ds]) == []

    def test_varios_datasets(self):
        ds1 = _ds([_campo(NivelConfianza.LOW, "x")])
        ds2 = _ds([_campo(NivelConfianza.HIGH, "y")])
        cola = cola_de_revision([ds1, ds2])
        assert len(cola) == 1 and cola[0].field == "x"

    def test_item_lleva_motivo_y_metodo(self):
        c = CampoExtraido(
            document_id="d", field="m", confidence=NivelConfianza.REVIEW_REQUIRED,
            extraction_method=MetodoExtraccion.OCR,
            warnings=["no se pudo normalizar 'N/D' como moneda"],
        )
        cola = cola_de_revision([_ds([c])])
        assert cola[0].extraction_method == "ocr"
        assert "REVIEW_REQUIRED" in cola[0].motivo
        assert "no se pudo normalizar" in cola[0].motivo
