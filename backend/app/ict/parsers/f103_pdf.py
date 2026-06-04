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

ALL_CASILLEROS = {
    "302": "cas_302",
    "303": "cas_303",
    "304": "cas_304",
    "307": "cas_307",
    "308": "cas_308",
    "309": "cas_309",
    "310": "cas_310",
    "311": "cas_311",
    "312": "cas_312",
    "314": "cas_314",
    "319": "cas_319",
    "320": "cas_320",
    "322": "cas_322",
    "323": "cas_323",
    "324": "cas_324",
    "325": "cas_325",
    "326": "cas_326",
    "327": "cas_327",
    "328": "cas_328",
    "329": "cas_329",
    "330": "cas_330",
    "331": "cas_331",
    "332": "cas_332",
    "333": "cas_333",
    "334": "cas_334",
    "335": "cas_335",
    "336": "cas_336",
    "337": "cas_337",
    "338": "cas_338",
    "339": "cas_339",
    "340": "cas_340",
    "341": "cas_341",
    "342": "cas_342",
    "343": "cas_343",
    "344": "cas_344",
    "345": "cas_345",
    "346": "cas_346",
    "348": "cas_348",
    "349": "cas_349",
    "350": "cas_350",
    "352": "cas_352",
    "353": "cas_353",
    "354": "cas_354",
    "357": "cas_357",
    "358": "cas_358",
    "359": "cas_359",
    "360": "cas_360",
    "361": "cas_361",
    "362": "cas_362",
    "364": "cas_364",
    "369": "cas_369",
    "370": "cas_370",
    "372": "cas_372",
    "373": "cas_373",
    "374": "cas_374",
    "375": "cas_375",
    "376": "cas_376",
    "377": "cas_377",
    "378": "cas_378",
    "379": "cas_379",
    "380": "cas_380",
    "383": "cas_383",
    "384": "cas_384",
    "385": "cas_385",
    "386": "cas_386",
    "387": "cas_387",
    "388": "cas_388",
    "389": "cas_389",
    "390": "cas_390",
    "391": "cas_391",
    "392": "cas_392",
    "393": "cas_393",
    "394": "cas_394",
    "395": "cas_395",
    "396": "cas_396",
    "398": "cas_398",
    "399": "cas_399",
    "400": "cas_400",
    "402": "cas_402",
    "403": "cas_403",
    "404": "cas_404",
    "405": "cas_405",
    "406": "cas_406",
    "407": "cas_407",
    "408": "cas_408",
    "409": "cas_409",
    "410": "cas_410",
    "411": "cas_411",
    "412": "cas_412",
    "413": "cas_413",
    "414": "cas_414",
    "415": "cas_415",
    "416": "cas_416",
    "417": "cas_417",
    "418": "cas_418",
    "419": "cas_419",
    "420": "cas_420",
    "421": "cas_421",
    "422": "cas_422",
    "423": "cas_423",
    "424": "cas_424",
    "425": "cas_425",
    "426": "cas_426",
    "427": "cas_427",
    "428": "cas_428",
    "429": "cas_429",
    "430": "cas_430",
    "431": "cas_431",
    "432": "cas_432",
    "433": "cas_433",
    "452": "cas_452",
    "453": "cas_453",
    "454": "cas_454",
    "456": "cas_456",
    "457": "cas_457",
    "458": "cas_458",
    "459": "cas_459",
    "460": "cas_460",
    "461": "cas_461",
    "463": "cas_463",
    "464": "cas_464",
    "465": "cas_465",
    "467": "cas_467",
    "468": "cas_468",
    "469": "cas_469",
    "470": "cas_470",
    "471": "cas_471",
    "472": "cas_472",
    "474": "cas_474",
    "475": "cas_475",
    "476": "cas_476",
    "477": "cas_477",
    "478": "cas_478",
    "479": "cas_479",
    "480": "cas_480",
    "481": "cas_481",
    "482": "cas_482",
    "497": "cas_497",
    "498": "cas_498",
    "499": "cas_499",
    "510": "cas_510",
    "520": "cas_520",
    "530": "cas_530",
    "540": "cas_540",
    "550": "cas_550",
    "880": "cas_880",
    "890": "cas_890",
    "897": "cas_897",
    "898": "cas_898",
    "899": "cas_899",
    "902": "cas_902",
    "903": "cas_903",
    "904": "cas_904",
    "999": "cas_999",
    "3120": "cas_3120",
    "3380": "cas_3380",
    "3400": "cas_3400",
    "3440": "cas_3440",
    "3480": "cas_3480",
    "3620": "cas_3620",
    "3880": "cas_3880",
    "3900": "cas_3900",
    "3940": "cas_3940",
    "3980": "cas_3980",
    "4050": "cas_4050",
    "4060": "cas_4060",
    "4070": "cas_4070",
    "4160": "cas_4160",
    "4170": "cas_4170",
    "4180": "cas_4180",
    "4260": "cas_4260",
    "4270": "cas_4270",
    "4280": "cas_4280",
    "4550": "cas_4550",
    "4560": "cas_4560",
    "4570": "cas_4570",
    "4660": "cas_4660",
    "4670": "cas_4670",
    "4680": "cas_4680",
    "4760": "cas_4760",
    "4770": "cas_4770",
    "4780": "cas_4780",
    "5100": "cas_5100",
    "5300": "cas_5300",
}

# Casilleros que tienen "valor retenido" además de base. La diferencia
# es 50 puntos para residentes (c302 base, c352 retenido) y 50 para
# exterior (c402 base, c452 retenido).
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
    """Convert SRI-format number to float. Returns None if not numeric.

    Soporta:
      - "178,259.63"  (formato US: coma=miles, punto=decimal)
      - "178.259,63"  (formato europeo: punto=miles, coma=decimal)
      - "178259.63"   (sin separador de miles)
      - "0.00", "0", ""
    """
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # Detectar formato: si tiene MAS de 1 coma o el último separador es coma → euro
    has_dot = "." in s
    has_comma = "," in s
    if has_dot and has_comma:
        # Ambos: decimal es el ÚLTIMO que aparece
        if s.rfind(",") > s.rfind("."):
            # formato euro: 178.259,63 → quitar puntos, coma → punto
            s = s.replace(".", "").replace(",", ".")
        else:
            # formato US: 178,259.63 → quitar comas
            s = s.replace(",", "")
    elif has_comma:
        # Solo coma: si tiene 2 decimales detrás, es coma decimal (euro)
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            s = s.replace(",", ".")
        else:
            # Es separador de miles US sin centavos
            s = s.replace(",", "")
    # else: solo punto o ningún separador → ya es válido
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

    El PDF F-103 SRI tiene formato tabular:
        CAS  CONCEPTO  BASE_IMPONIBLE  CAS_RET  VALOR_RETENIDO

    Estrategia: para cada cas conocido, buscar el patrón
    `\b{cas}\b` seguido de un NÚMERO con formato monetario (acepta
    comas como separador de miles y puntos como decimal, o viceversa).

    El regex captura el primer número MONETARIO válido (mínimo 1 dígito
    + opcional separador miles + opcional decimal) dentro de 100 chars
    del cas. NO captura números que sean otros codigos de casillero.
    """
    result: dict[str, float] = {}
    # Patrón monetario robusto:
    #   `\d+`               → uno o más dígitos (cubre "183724" sin separador)
    #   `(?:[.,]\d+)*`      → cero o más grupos "separador + dígitos"
    #                         (cubre "183,724.10" formato US,
    #                          "183.724,10" formato europeo,
    #                          "1,234,567.89" tres grupos, etc.)
    # La interpretación coma/punto la hace _parse_amount() según contexto.
    monetario = r"(-?\d+(?:[.,]\d+)*)"
    for casillero in ALL_CASILLEROS:
        # Buscar cas + cualquier whitespace/texto NO numérico + primer monto.
        # El whitespace `\s` antes del monto es OBLIGATORIO para evitar
        # capturar dígitos contiguos al cas (ej. "30201" no debe matchear cas 302).
        pattern = rf"\b{casillero}\b\s+{monetario}"
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
