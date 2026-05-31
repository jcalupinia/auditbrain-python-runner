"""Tests for ATS XML parser."""
from backend.app.ict.parsers.ats_xml import parse_ats


SAMPLE_ATS = """<?xml version="1.0" encoding="UTF-8"?>
<iva>
  <TipoIDInformante>R</TipoIDInformante>
  <IdInformante>1234567890001</IdInformante>
  <razonSocial>Test S.A.</razonSocial>
  <Anio>2024</Anio>
  <Mes>07</Mes>
  <numEstabRuc>001</numEstabRuc>
  <pagoExterior>
    <pagoLocExt>02</pagoLocExt>
    <tipoRegi>01</tipoRegi>
    <paisEfecPago>USA</paisEfecPago>
    <paisEfecPagoGen>NA</paisEfecPagoGen>
    <denopagoRegFiscal>NA</denopagoRegFiscal>
    <pagExtSujRetNorLeg>SI</pagExtSujRetNorLeg>
    <comPagExtSujRetNorLeg>Pago software</comPagExtSujRetNorLeg>
  </pagoExterior>
</iva>"""


def test_parse_ats_extracts_metadata():
    result = parse_ats(SAMPLE_ATS.encode("utf-8"))
    assert result["errores"] == []
    assert result["ruc_informante"] == "1234567890001"
    assert result["razon_social"] == "Test S.A."
    assert result["periodo"] == "07/2024"


def test_parse_ats_extracts_pagos_exterior():
    result = parse_ats(SAMPLE_ATS.encode("utf-8"))
    pagos = result["pagos_exterior"]
    assert len(pagos) == 1
    assert pagos[0]["pais"] == "USA"
    assert pagos[0]["sujeto_retencion"] == "SI"


def test_parse_ats_returns_error_for_invalid_xml():
    result = parse_ats(b"not xml")
    assert len(result["errores"]) > 0
