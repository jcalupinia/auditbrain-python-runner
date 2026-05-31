"""Parser for ATS (Anexo Transaccional Simplificado) XML del SRI."""

from __future__ import annotations

from xml.etree import ElementTree as ET


def parse_ats(xml_bytes: bytes) -> dict:
    """Returns {ruc_informante, razon_social, periodo, pagos_exterior: [...], errores: []}."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return {
            "ruc_informante": None, "razon_social": None, "periodo": None,
            "pagos_exterior": [], "errores": [f"XML inválido: {e}"],
        }

    def _text(parent, tag: str) -> str | None:
        el = parent.find(tag)
        return el.text.strip() if el is not None and el.text else None

    ruc = _text(root, "IdInformante")
    razon = _text(root, "razonSocial")
    anio = _text(root, "Anio")
    mes = _text(root, "Mes")
    periodo = f"{mes}/{anio}" if anio and mes else None

    pagos_exterior: list[dict] = []
    for pe in root.findall("pagoExterior"):
        pagos_exterior.append({
            "pago_loc_ext": _text(pe, "pagoLocExt"),
            "tipo_regi": _text(pe, "tipoRegi"),
            "pais": _text(pe, "paisEfecPago"),
            "pais_pago_gen": _text(pe, "paisEfecPagoGen"),
            "denop_reg_fiscal": _text(pe, "denopagoRegFiscal"),
            "sujeto_retencion": _text(pe, "pagExtSujRetNorLeg"),
            "comentario": _text(pe, "comPagExtSujRetNorLeg"),
        })

    return {
        "ruc_informante": ruc,
        "razon_social": razon,
        "periodo": periodo,
        "pagos_exterior": pagos_exterior,
        "errores": [],
    }
