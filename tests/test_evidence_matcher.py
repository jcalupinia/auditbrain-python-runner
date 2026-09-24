"""Emparejador de evidencia: helpers, fuzzy, emparejar, lotes (P1-E)."""
import datetime
from decimal import Decimal

import pytest

from backend.app.evidence import matcher as M
from backend.app.evidence.matcher import (
    CampoEmparejamiento,
    CriterioEmparejamiento,
    EstadoEmparejamiento,
    ModoEmparejamiento,
    TipoCampo,
    dentro_de_tolerancia_fecha,
    dentro_de_tolerancia_numerica,
    emparejar,
    emparejar_lotes,
    normalizar_texto,
)

F = datetime.date(2026, 3, 1)


# --- Task 4: helpers --------------------------------------------------------
def test_normalizar_texto():
    assert normalizar_texto(" ANDES  S.A. ") == "andes sa"
    assert normalizar_texto(None) == ""
    assert normalizar_texto("Café Ñoño") == "cafe nono"


def test_tolerancia_numerica():
    assert dentro_de_tolerancia_numerica(Decimal("100.00"), Decimal("100.00")) == (True, 1.0)
    casa, sim = dentro_de_tolerancia_numerica(Decimal("100.00"), Decimal("100.01"),
                                              tolerancia_absoluta=Decimal("0.01"))
    assert casa and sim > 0.99
    casa, sim = dentro_de_tolerancia_numerica(Decimal("100.00"), Decimal("101.00"),
                                              tolerancia_relativa=0.005)
    assert not casa and sim < 1.0


def test_tolerancia_fecha():
    assert dentro_de_tolerancia_fecha(F, F) == (True, 1.0)
    casa, sim = dentro_de_tolerancia_fecha(F, F + datetime.timedelta(days=3), tolerancia_dias=5)
    assert casa and abs(sim - 0.5) < 1e-9
    assert dentro_de_tolerancia_fecha(F, F + datetime.timedelta(days=6), tolerancia_dias=5) == (False, 0.0)


def test_pesos_normalizados():
    crit = CriterioEmparejamiento(campos=(
        CampoEmparejamiento("a", peso=3.0), CampoEmparejamiento("b", peso=1.0)))
    pesos = crit.pesos_normalizados()
    assert abs(sum(pesos.values()) - 1.0) < 1e-9 and abs(pesos["a"] - 0.75) < 1e-9


# --- Task 5: fuzzy ----------------------------------------------------------
def test_fuzzy():
    pytest.importorskip("rapidfuzz")
    assert M.similitud_fuzzy("ANDES S.A.", "Andes S A") > 0.85
    assert M.similitud_fuzzy("ANDES S.A.", "COMERCIAL XYZ") < 0.5


# --- Task 6: emparejar ------------------------------------------------------
def _crit_factura_auxiliar():
    return CriterioEmparejamiento(campos=(
        CampoEmparejamiento("numero", modo=ModoEmparejamiento.NORMALIZADO),
        CampoEmparejamiento("ruc", modo=ModoEmparejamiento.EXACTO, obligatorio=True),
        CampoEmparejamiento("total", tipo=TipoCampo.NUMERO, tolerancia_absoluta=Decimal("0.01")),
        CampoEmparejamiento("fecha", tipo=TipoCampo.FECHA),
    ), umbral=0.80)


def test_factura_auxiliar_unica():
    consulta = {"numero": "001-001-000123", "ruc": "1790011", "total": Decimal("500.00"), "fecha": F}
    candidatos = [
        {"numero": "001-001-000123", "ruc": "1790011", "total": Decimal("500.00"), "fecha": F},
        {"numero": "999", "ruc": "0000", "total": Decimal("10.00"), "fecha": F},
    ]
    r = emparejar(consulta, candidatos, criterio=_crit_factura_auxiliar())
    assert r.estado is EstadoEmparejamiento.UNICA and r.mejor.score >= 0.80


def test_factura_xml_clave_exacta():
    crit = CriterioEmparejamiento(campos=(
        CampoEmparejamiento("clave_acceso", modo=ModoEmparejamiento.EXACTO, obligatorio=True),
    ))
    consulta = {"clave_acceso": "2603...001", "otro": "x"}
    candidatos = [{"clave_acceso": "2603...001", "otro": "DIFERENTE"}]
    r = emparejar(consulta, candidatos, criterio=crit)
    assert r.es_unica


def test_factura_pago_fuzzy_fecha():
    pytest.importorskip("rapidfuzz")
    crit = CriterioEmparejamiento(campos=(
        CampoEmparejamiento("beneficiario", modo=ModoEmparejamiento.FUZZY),
        CampoEmparejamiento("importe", tipo=TipoCampo.NUMERO, tolerancia_absoluta=Decimal("0.00")),
        CampoEmparejamiento("fecha", tipo=TipoCampo.FECHA, tolerancia_dias=5),
    ), umbral=0.75)
    consulta = {"beneficiario": "ANDES S.A.", "importe": Decimal("500.00"), "fecha": F}
    candidatos = [{"beneficiario": "Andes S A", "importe": Decimal("500.00"),
                   "fecha": F + datetime.timedelta(days=3)}]
    r = emparejar(consulta, candidatos, criterio=crit)
    assert r.es_unica


def test_ambigua():
    crit = _crit_factura_auxiliar()
    q = {"numero": "1", "ruc": "R", "total": Decimal("10.00"), "fecha": F}
    cands = [dict(q), dict(q)]  # dos idénticos
    r = emparejar(q, cands, criterio=crit)
    assert r.estado is EstadoEmparejamiento.AMBIGUA and len(r.coincidencias) == 2
    assert r.mejor is not None  # el de mayor score; nada se descarta


def test_sin_coincidencia():
    crit = _crit_factura_auxiliar()
    q = {"numero": "1", "ruc": "R", "total": Decimal("10.00"), "fecha": F}
    cands = [{"numero": "9", "ruc": "OTRO", "total": Decimal("999.00"),
              "fecha": F + datetime.timedelta(days=40)}]
    r = emparejar(q, cands, criterio=crit)
    assert r.estado is EstadoEmparejamiento.SIN_COINCIDENCIA and r.mejor is None


def test_semantico_sin_embeddings():
    with pytest.raises(ValueError):
        emparejar({"a": "x"}, [{"a": "y"}], modo=ModoEmparejamiento.SEMANTICO)


def test_obligatorio_en_cero_descarta():
    crit = _crit_factura_auxiliar()  # ruc obligatorio
    q = {"numero": "001", "ruc": "R", "total": Decimal("500.00"), "fecha": F}
    cand = {"numero": "001", "ruc": "DISTINTO", "total": Decimal("500.00"), "fecha": F}
    r = emparejar(q, [cand], criterio=crit)
    assert r.estado is EstadoEmparejamiento.SIN_COINCIDENCIA  # ruc=0 descarta


def test_emparejar_lotes_uno_a_uno():
    crit = CriterioEmparejamiento(campos=(
        CampoEmparejamiento("id", modo=ModoEmparejamiento.EXACTO),))
    consultas = [{"id": "A"}, {"id": "B"}, {"id": "Z"}]
    candidatos = [{"id": "A"}, {"id": "B"}]
    res = emparejar_lotes(consultas, candidatos, crit, uno_a_uno=True)
    estados = [r.estado for r in res]
    assert estados[0] is EstadoEmparejamiento.UNICA
    assert estados[1] is EstadoEmparejamiento.UNICA
    assert estados[2] is EstadoEmparejamiento.SIN_COINCIDENCIA  # "Z" sin par
    # ningún candidato reutilizado
    usados = [r.mejor.candidato["id"] for r in res if r.mejor]
    assert sorted(usados) == ["A", "B"]
