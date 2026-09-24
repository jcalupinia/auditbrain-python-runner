"""Matriz de evidencia con validación humana (P1-E, DOC-010)."""
from decimal import Decimal

from backend.app.evidence.citation import SourceReference
from backend.app.evidence.confidence import ConfianzaCampo
from backend.app.evidence.crossref import EstadoValidacion, MatrizEvidencia


def _ref(sid, filename="F101.pdf", page=1):
    return SourceReference(source_id=sid, file_hash="h", filename=filename, page=page,
                           column="cas550", original_value="1000", normalized_value=Decimal("1000"))


def _conf(ext, interp):
    return ConfianzaCampo(campo="c", metodo_extraccion="pdfplumber",
                          confianza_extraccion=ext, confianza_interpretacion=interp)


def test_agregar_dedup_y_corroboracion():
    m = MatrizEvidencia()
    e = m.agregar("F101.cas550", "Total ingresos", Decimal("1000"), [_ref("s1")])
    assert e.estado_validacion is EstadoValidacion.PENDIENTE and not e.es_corroborado
    # mismo dato_id: suma fuentes sin duplicar s1
    m.agregar("F101.cas550", "Total ingresos", Decimal("1000"), [_ref("s1"), _ref("s2")])
    assert e.num_fuentes == 2 and e.es_corroborado


def test_marcar():
    m = MatrizEvidencia()
    e = m.agregar("d1", "x", 1, [_ref("s1")])
    e.marcar(EstadoValidacion.VALIDADO, por="jvinicio")
    assert e.estado_validacion is EstadoValidacion.VALIDADO
    assert e.validado_por == "jvinicio" and e.validado_en is not None


def test_por_estado_pendientes_y_sin_evidencia():
    m = MatrizEvidencia()
    m.agregar("alta", "a", 1, [_ref("s1")], confianza=_conf(0.95, 0.95))
    baja = m.agregar("baja", "b", 2, [_ref("s2")], confianza=_conf(0.4, 0.9))
    m.agregar("vacia", "c", 3, [])  # sin evidencia
    validada = m.agregar("val", "d", 4, [_ref("s3")], confianza=_conf(0.95, 0.95))
    validada.marcar(EstadoValidacion.VALIDADO, por="x")

    assert len(m.por_estado(EstadoValidacion.PENDIENTE)) == 3
    pend = m.pendientes_de_revision()
    # la de confianza baja está primera (más dudosa) y la validada no aparece
    assert pend[0].dato_id == "baja"
    assert "val" not in [e.dato_id for e in pend]
    assert [e.dato_id for e in m.sin_evidencia()] == ["vacia"]


def test_resumen_y_a_filas():
    m = MatrizEvidencia()
    m.agregar("d1", "Total", Decimal("1000"), [_ref("s1"), _ref("s2")],
              confianza=_conf(0.9, 0.8))
    m.agregar("d2", "Sin fuente", 0, [])
    r = m.resumen()
    assert r["total"] == 2 and r["pendiente"] == 2 and r["sin_evidencia"] == 1
    filas = m.a_filas()
    # d1 tiene 2 fuentes → 2 filas; d2 sin fuente → 1 fila
    assert len(filas) == 3
    f0 = filas[0]
    assert f0["dato_id"] == "d1" and f0["confianza_extraccion"] == 0.9
    assert f0["pagina"] == 1 and f0["estado"] == "pendiente"
