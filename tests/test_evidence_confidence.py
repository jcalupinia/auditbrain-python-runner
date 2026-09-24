"""Confianza por dato en dos ejes (P1-E, DOC-011)."""
from backend.app.evidence import confidence as CF
from backend.app.evidence.citation import SourceReference
from backend.app.evidence.confidence import (
    NivelConfianza,
    confianza_extraccion,
    confianza_interpretacion,
    evaluar_campo,
    nivel_de,
)
from backend.app.evidence.matcher import (
    Coincidencia,
    EstadoEmparejamiento,
    ModoEmparejamiento,
    ResultadoEmparejamiento,
)


def _match(estado, score):
    coin = Coincidencia(candidato={}, score=score, por_campo={}, es_match=(score >= 0.8))
    return ResultadoEmparejamiento(consulta={}, coincidencias=[coin], estado=estado,
                                   modo=ModoEmparejamiento.NORMALIZADO)


def test_confianza_extraccion():
    ce, _ = confianza_extraccion("excel")
    assert abs(ce - 0.98) < 1e-9
    ce_ocr, _ = confianza_extraccion("ocr", ocr_word_confidence=0.5)
    assert ce_ocr < 0.70  # baja proporcional
    sr = SourceReference(source_id="s", file_hash="h", filename="f", page=2, bounding_box=None)
    ce_bbox, aportes = confianza_extraccion("pdfplumber", source_ref=sr)
    assert ce_bbox < 0.90 and any(a.factor == "bbox_ausente" for a in aportes)
    assert confianza_extraccion("desconocido")[0] == 0.50


def test_confianza_interpretacion():
    alta, _ = confianza_interpretacion(resultado_match=_match(EstadoEmparejamiento.UNICA, 0.95))
    assert alta >= 0.9
    amb, _ = confianza_interpretacion(resultado_match=_match(EstadoEmparejamiento.AMBIGUA, 0.95))
    assert amb < 0.60  # penaliza fuerte
    sinc, _ = confianza_interpretacion(resultado_match=_match(EstadoEmparejamiento.SIN_COINCIDENCIA, 0.0))
    assert 0.0 < sinc < 0.5
    con_map, _ = confianza_interpretacion(resultado_match=_match(EstadoEmparejamiento.UNICA, 0.95),
                                          mapeo_conocido=False)
    assert con_map < alta  # heurística penaliza


def test_nivel_de():
    assert nivel_de(0.9) is NivelConfianza.ALTA
    assert nivel_de(0.7) is NivelConfianza.MEDIA
    assert nivel_de(0.4) is NivelConfianza.BAJA


def test_evaluar_campo_global_es_minimo():
    cc = evaluar_campo("cas550", "excel",
                       resultado_match=_match(EstadoEmparejamiento.AMBIGUA, 0.9))
    assert cc.confianza_extraccion > 0.9        # excel alto
    assert cc.confianza_interpretacion < 0.6    # ambigua bajo
    assert cc.confianza_global == min(cc.confianza_extraccion, cc.confianza_interpretacion)
    assert cc.requiere_revision_humana is True  # interpretación bajo el umbral medio
    assert cc.nivel_extraccion is NivelConfianza.ALTA
