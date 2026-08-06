"""Parser del ATS (Talón Resumen del SRI): texto sintético que replica la
estructura literal real, incluidos los nombres de concepto de retención de
renta partidos en varias líneas (trampa #2 del formato) y los códigos sin
nombre propio (310, en este texto).

Todos los datos son ficticios (CLAUDE.md: nunca cifras/RUC/razón social de
clientes reales en el repo público).
"""

from __future__ import annotations

from backend.app.aud.obligaciones_fiscales.libro.ats import (
    ResumenATS,
    parse_ats,
    parse_ats_texto,
    parse_ats_xml,
)

TEXTO_ATS = """\
TALÓN RESUMEN
SERVICIO DE RENTAS INTERNAS
ANEXO TRANSACCIONAL
EMPRESA DE PRUEBA CIA LTDA
RUC: 1790000000001
Periodo: MARZO 2025
Fecha de Generación: 05-04-2025 09:00:00
Estado: CARGA DEFINITIVA
Secuencial Anexo: 12345678
COMPRAS
Cod. Transacción No. Registros BI tarifa 0% BI tarifa 12% BI No Objeto IVA Valor IVA
01 FACTURA 10 1000.00 2000.00 0.00 300.00
TOTAL: 1000.00 2000.00 0.00 300.00
VENTAS
Cod. Transacción No. Registros BI tarifa 0% BI tarifa 12% BI No Objeto IVA Valor IVA
18 DOCUMENTOS AUTORIZADOS EN VENTAS EXCEPTO ND Y NC 20 500.00 8000.00 0.00 1200.00
TOTAL: 500.00 8000.00 0.00 1200.00
COMPROBANTES ANULADOS
Total de Comprobantes Anulados en el período informado (no incluye los dados de baja) 2
RESUMEN DE RETENCIONES - AGENTE DE RETENCION
RETENCION EN LA FUENTE DE IMPUESTO A LA RENTA
No. Base Valor
Cod. Concepto de Retención
Registros Imponible Retenido
HONORARIOS PROFESIONALES Y DEMÁS PAGOS POR SERVICIOS RELACIONADOS CON EL TÍTULO
303 5 1000.00 100.00
PROFESIONAL
310 2 200.00 2.00
312 TRANSFERENCIA DE BIENES MUEBLES DE NATURALEZA CORPORAL 3 300.00 3.00
TOTAL: 1500.00 105.00
RETENCION EN LA FUENTE DE IVA
Operación Concepto de Retención Valor Retenido
COMPRA Retencion IVA 30% 50.00
COMPRA Retencion IVA 70% 70.00
COMPRA Retencion IVA NC 0.00
TOTAL: 120.00
RESUMEN DE RETENCIONES QUE LE EFECTUARON EN EL PERIODO
Operación Concepto de Retención Valor Retenido
VENTA Valor de IVA que le han retenido 400.00
VENTA Valor de Renta que le han retenido 150.00
TOTAL: 550.00
"""


def _resumen() -> ResumenATS:
    return parse_ats_texto(TEXTO_ATS)


def test_detecta_el_periodo_en_formato_anio_mes():
    r = _resumen()
    assert r.periodo == "2025-03"


def test_detecta_ruc_razon_social_estado_y_secuencial():
    r = _resumen()
    assert r.ruc == "1790000000001"
    assert r.razon_social == "EMPRESA DE PRUEBA CIA LTDA"
    assert r.estado == "CARGA DEFINITIVA"
    assert r.secuencial == "12345678"


def test_lee_los_totales_de_compras_por_posicion_no_por_rotulo():
    """'BI tarifa 12%' es el rótulo histórico: es la base con tarifa
    distinta de cero. Se lee por posición de columna."""
    r = _resumen()
    assert r.compras.bi_0 == 1000.00
    assert r.compras.bi_gravada == 2000.00
    assert r.compras.bi_no_objeto == 0.00
    assert r.compras.iva == 300.00


def test_lee_los_totales_de_ventas():
    r = _resumen()
    assert r.ventas.bi_0 == 500.00
    assert r.ventas.bi_gravada == 8000.00
    assert r.ventas.iva == 1200.00


def test_lee_los_comprobantes_anulados():
    r = _resumen()
    assert r.comprobantes_anulados == 2


def test_reconstruye_el_nombre_partido_en_varias_lineas():
    """303: el nombre viene partido antes (línea previa) y después (línea
    siguiente) de la fila código+números. Nunca se debe heredar el nombre
    de la fila anterior para una fila sin nombre propio."""
    r = _resumen()
    fila = next(f for f in r.retenciones_renta if f.codigo == "303")
    assert fila.concepto == (
        "HONORARIOS PROFESIONALES Y DEMÁS PAGOS POR SERVICIOS RELACIONADOS "
        "CON EL TÍTULO PROFESIONAL"
    )
    assert fila.n_registros == 5
    assert fila.base_imponible == 1000.00
    assert fila.valor_retenido == 100.00


def test_codigo_sin_nombre_propio_no_hereda_el_del_anterior():
    """310 no tiene nombre en el talón: debe quedar vacío, NUNCA heredar
    'PROFESIONAL' (nombre de la fila 303 inmediatamente anterior)."""
    r = _resumen()
    fila = next(f for f in r.retenciones_renta if f.codigo == "310")
    assert fila.concepto == ""
    assert fila.valor_retenido == 2.00


def test_codigo_con_nombre_en_la_misma_linea():
    r = _resumen()
    fila = next(f for f in r.retenciones_renta if f.codigo == "312")
    assert fila.concepto == "TRANSFERENCIA DE BIENES MUEBLES DE NATURALEZA CORPORAL"
    assert fila.valor_retenido == 3.00


def test_hay_exactamente_tres_codigos_de_retencion_de_renta():
    r = _resumen()
    assert {f.codigo for f in r.retenciones_renta} == {"303", "310", "312"}


def test_el_total_de_retenciones_de_renta_coincide_con_la_suma_de_filas():
    r = _resumen()
    assert r.retenciones_renta_valor_total == 105.00
    assert sum(f.valor_retenido for f in r.retenciones_renta) == 105.00


def test_lee_retenciones_de_iva_por_porcentaje():
    r = _resumen()
    porcentajes = {f.porcentaje: f.valor_retenido for f in r.retenciones_iva}
    assert porcentajes[30.0] == 50.00
    assert porcentajes[70.0] == 70.00
    assert r.retenciones_iva_total == 120.00


def test_retencion_iva_nc_no_tiene_porcentaje_numerico():
    r = _resumen()
    fila_nc = next(f for f in r.retenciones_iva if f.concepto.upper().endswith(" NC"))
    assert fila_nc.porcentaje is None


def test_lee_retenciones_que_le_efectuaron():
    r = _resumen()
    assert r.iva_que_le_retuvieron == 400.00
    assert r.renta_que_le_retuvieron == 150.00


def test_no_reporta_errores_con_un_talon_bien_formado():
    r = _resumen()
    assert r.errores == []


def test_parse_ats_despacha_por_extension_pdf_o_xml(monkeypatch):
    llamadas = []
    import backend.app.aud.obligaciones_fiscales.libro.ats as mod

    monkeypatch.setattr(mod, "parse_ats_pdf", lambda b: llamadas.append("pdf") or ResumenATS(periodo=None))
    monkeypatch.setattr(mod, "parse_ats_xml", lambda b: llamadas.append("xml") or ResumenATS(periodo=None))

    mod.parse_ats(b"contenido", "anexo.pdf")
    mod.parse_ats(b"<xml/>", "anexo.xml")

    assert llamadas == ["pdf", "xml"]


def test_parse_ats_xml_no_inventa_estructura_devuelve_error_explicito():
    """La rama XML está pendiente de una muestra real: debe fallar honesto,
    no fingir un parseo exitoso con nodos inventados."""
    r = parse_ats_xml(b"<anexoTransaccional><algo/></anexoTransaccional>")
    assert r.periodo is None
    assert r.errores
    assert any("XML" in e or "xml" in e for e in r.errores)
