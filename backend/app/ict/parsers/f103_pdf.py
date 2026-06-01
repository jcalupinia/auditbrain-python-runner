"""F-103 PDF parser — Declaración mensual de Retenciones en la Fuente IR.

El F-103 del SRI Ecuador captura las retenciones de Impuesto a la Renta
que el agente de retención efectuó durante el mes a:

  - Residentes y establecimientos permanentes (302-350)
  - No residentes con convenio de doble tributación (402-411)
  - No residentes sin convenio (413-421)
  - Residentes en paraísos fiscales (424-433)
  - Totales (497-499)

Datos útiles para el ICT:
  - A5 Conciliación Costos/Gastos: validar c.7041/7050 F-101 vs retenciones efectuadas
  - A7 Crédito Tributario: el c.499 acumulado por la contraparte aparece en c.857 F-101
  - A8 Comercio Exterior: los casilleros 402-433 son la fuente directa de
    pagos al exterior por concepto (intereses, dividendos, regalías, servicios
    técnicos, seguros, etc.) con su retención aplicada según CDI o sin CDI.

Como es declaración mensual, se necesitan 12 archivos por ejercicio fiscal
y el parser de lista los agrega por mes.
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import pdfplumber

# Casilleros principales a capturar (subset estable; el F-103 tiene ~200)
# Ordenados por bloque.
F103_CASILLEROS_RESIDENTES = {
    # Trabajo y servicios
    "302": "relacion_dependencia",
    "303": "honorarios_profesionales",
    "3030": "servicios_profesionales_sociedades",
    "304": "predomina_intelecto",
    "307": "predomina_mano_obra",
    "308": "imagen_renombre",
    "309": "publicidad_comunicacion",
    "310": "transporte",
    # Bienes y servicios
    "312": "bienes_muebles",
    "322": "seguros_reaseguros",
    "343": "pagos_1_pct",
    "344": "pagos_2_pct",
    "332": "pagos_no_sujetos_retencion",
    # Regalías y arrendamientos
    "314": "regalias_derechos",
    "319": "arrendamiento_mercantil",
    "320": "arrendamiento_inmuebles",
    # Dividendos y rendimientos
    "323": "rendimientos_financieros",
    "327": "dividendos_pn_residentes",
    "328": "dividendos_sociedades_residentes",
    # Autorretenciones y otros
    "350": "otras_autorretenciones",
    "3440": "otras_2_75_pct",
    "345": "otras_8_pct",
    # Total país
    "349": "subtotal_pais",
    "399": "subtotal_pais_retenido",
}

# Pagos al exterior por bloque (clave para A8 Comercio Exterior)
F103_CASILLEROS_EXTERIOR = {
    # Con CDI
    "402": "cdi_intereses_proveedores",
    "403": "cdi_intereses_creditos",
    "404": "cdi_anticipo_dividendos",
    "405": "cdi_dividendos_pn",
    "406": "cdi_dividendos_sociedades",
    "407": "cdi_dividendos_fideicomisos",
    "408": "cdi_enajenacion_capital",
    "409": "cdi_seguros_reaseguros",
    "410": "cdi_servicios_tecnicos_regalias",
    "411": "cdi_otros_gravados",
    "412": "cdi_otros_no_sujetos",
    # Sin CDI
    "413": "sin_cdi_intereses_proveedores",
    "414": "sin_cdi_intereses_creditos",
    "415": "sin_cdi_anticipo_dividendos",
    "416": "sin_cdi_dividendos_pn",
    "417": "sin_cdi_dividendos_sociedades",
    "418": "sin_cdi_dividendos_fideicomisos",
    "419": "sin_cdi_seguros_reaseguros",
    "420": "sin_cdi_servicios_tecnicos_regalias",
    "421": "sin_cdi_otros_gravados",
    "422": "sin_cdi_otros_no_sujetos",
    # Paraísos fiscales
    "424": "paraisos_intereses",
    "425": "paraisos_anticipo_dividendos",
    "426": "paraisos_dividendos_pn",
    "427": "paraisos_dividendos_sociedades",
    "428": "paraisos_dividendos_fideicomisos",
    "429": "paraisos_enajenacion_capital",
    "430": "paraisos_seguros_reaseguros",
    "431": "paraisos_servicios_tecnicos_regalias",
    "432": "paraisos_otros_gravados",
    "433": "paraisos_otros_no_sujetos",
    # Totales exterior
    "497": "subtotal_exterior_base",
    "498": "subtotal_exterior_retenido",
    "499": "total_retencion_ir",
}

ALL_CASILLEROS = {**F103_CASILLEROS_RESIDENTES, **F103_CASILLEROS_EXTERIOR}

# Casilleros que tienen "valor retenido" además de base. La diferencia
# es 50 puntos para residentes (c302 base, c352 retenido) y 50 para
# exterior (c402 base, c452 retenido). Capturamos solo la BASE en el dict
# principal; los retenidos son metadata.
RETAINED_OFFSET_BLOCKS = [
    (range(302, 351), 50),   # residentes: base + 50 = retenido
    (range(402, 434), 50),   # exterior con CDI: base + 50 = retenido
]

MONTH_MAP = {
    "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04",
    "MAYO": "05", "JUNIO": "06", "JULIO": "07", "AGOSTO": "08",
    "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12",
}


def _parse_amount(s: str) -> float | None:
    """Convert SRI-format number to float. Returns None if not numeric."""
    if not s:
        return None
    s = s.strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _extract_periodo(text: str) -> str | None:
    """Extract YYYY-MM from the period line."""
    m = re.search(r"Per[íi]odo\s+Fiscal:\s*([A-Z]+)\s+(\d{4})", text, re.IGNORECASE)
    if not m:
        return None
    month_name = m.group(1).upper()
    year = m.group(2)
    month_num = MONTH_MAP.get(month_name)
    if not month_num:
        return None
    return f"{year}-{month_num}"


def _extract_casilleros(text: str) -> dict[str, float]:
    """Scan the F-103 text and pull values for every casillero in ALL_CASILLEROS.

    The SRI PDF layout shows casillero number then its base, then a few cells
    later the retained value. We do a robust regex that captures the FIRST
    number after the casillero label.
    """
    result: dict[str, float] = {}
    for casillero in ALL_CASILLEROS:
        # Match: 3-4 digit casillero, optional space, then numeric value
        # We look for the casillero number at word boundary, then capture
        # the next number that follows (within ~80 chars).
        pattern = rf"\b{casillero}\b[\s\S]{{0,80}}?(-?\d[\d.]*)"
        m = re.search(pattern, text)
        if m:
            val = _parse_amount(m.group(1))
            if val is not None:
                result[casillero] = val
    return result


def parse_f103(pdf_bytes: bytes) -> dict | None:
    """Parse a single F-103 PDF. Returns {'periodo', 'casilleros'} or None on error.

    Args:
        pdf_bytes: raw PDF bytes from the uploaded file

    Returns:
        {
            'periodo': 'YYYY-MM',  # e.g. '2025-01'
            'casilleros': {
                '302': 178259.63,
                '349': 620109.94,
                ...
            },
            'razon_social': 'PROPHAR S.A',  # optional
            'ruc': '1791859596001',
        }
    """
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        return None

    if not text or "RETENCIONES EN LA FUENTE" not in text.upper():
        return None

    periodo = _extract_periodo(text)
    casilleros = _extract_casilleros(text)

    if not periodo or not casilleros:
        return None

    # Razón social y RUC son útiles para validación cruzada con la sesión
    ruc_match = re.search(r"Identificaci[óo]n:\s*(\d{10,13})", text)
    razon_match = re.search(r"Raz[óo]n\s+Social:\s*([^\n]+)", text)

    return {
        "periodo": periodo,
        "casilleros": casilleros,
        "ruc": ruc_match.group(1).strip() if ruc_match else None,
        "razon_social": razon_match.group(1).strip() if razon_match else None,
    }


def parse_all_f103(paths: list[Path]) -> tuple[dict[str, dict], list[str]]:
    """Parse a list of F-103 PDFs and group them by month.

    Returns:
        (monthly_data, errors)
        monthly_data: {'YYYY-MM': {'casilleros': {...}, 'ruc': ..., 'razon_social': ...}}
        errors: list of human-readable error strings for files that failed
    """
    monthly: dict[str, dict] = {}
    errors: list[str] = []

    for path in paths:
        try:
            data = parse_f103(path.read_bytes())
        except Exception as e:
            errors.append(f"{path.name}: {e}")
            continue
        if not data:
            errors.append(f"{path.name}: no se pudo extraer F-103 (¿formato inválido?)")
            continue
        periodo = data["periodo"]
        if periodo in monthly:
            errors.append(f"{path.name}: duplicado para período {periodo} (se ignora)")
            continue
        monthly[periodo] = data

    return monthly, errors


def aggregate_annual(monthly: dict[str, dict]) -> dict[str, float]:
    """Sum each casillero across all months to get annual totals.

    Returns:
        {'302': sum_jan_to_dec, '349': sum_jan_to_dec, ...}
    """
    annual: dict[str, float] = {}
    for periodo, data in monthly.items():
        for casillero, value in (data.get("casilleros") or {}).items():
            annual[casillero] = annual.get(casillero, 0.0) + (value or 0.0)
    return annual
