"""Catálogo canónico de casilleros del Formulario 103 — Declaración Mensual de
Retenciones en la Fuente del Impuesto a la Renta (SRI Ecuador 2025).

ESTA ES LA ÚNICA FUENTE DE VERDAD para los nombres oficiales del F-103.
Regla del proyecto (CLAUDE.md / pedido del usuario):

    "se verifique que se traslada TODOS los casilleros con sus códigos,
    nombres, valores — no importa que estén en cero, con la finalidad
    de que no haya saldos de líneas [vacías]"

El test estático tests/test_ict_catalogo_f103_completo.py bloquea el
deploy si algún casillero del parser ALL_CASILLEROS de
backend/app/ict/parsers/f103_pdf.py queda sin nombre acá.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO COMPLETO F-103 — { casillero_str: nombre_oficial }
# ─────────────────────────────────────────────────────────────────────────────
# Organizado en 2 bloques: RESIDENTES (Ecuador, retención local) y PAGOS AL
# EXTERIOR (con CDI, sin CDI, paraísos fiscales).
F103_CASILLERO_NAMES: dict[str, str] = {
    # ═══════════════════════════════════════════════════════════════════════
    # RESIDENTES — Trabajo y servicios
    # ═══════════════════════════════════════════════════════════════════════
    "302": "En relación de dependencia que supera o no la base desgravada",
    "303": "Honorarios profesionales y dietas",
    "3030": "Servicios profesionales prestados por sociedades",
    "304": "Servicios predomina el intelecto",
    "307": "Servicios predomina la mano de obra",
    "308": "Por utilización o aprovechamiento de imagen o renombre",
    "309": "Servicios de publicidad y comunicación",
    "310": "Transporte privado de pasajeros o servicio público o privado de carga",

    # ═══════════════════════════════════════════════════════════════════════
    # RESIDENTES — Bienes y servicios
    # ═══════════════════════════════════════════════════════════════════════
    "312": "Transferencia de bienes muebles de naturaleza corporal",
    "322": "Por pagos a compañías de seguros y reaseguros",
    "343": "Pagos sujetos a retención del 1%",
    "344": "Pagos sujetos a retención del 2%",
    "332": "Pagos no sujetos a retención",

    # ═══════════════════════════════════════════════════════════════════════
    # RESIDENTES — Regalías, arrendamientos y rendimientos
    # ═══════════════════════════════════════════════════════════════════════
    "314": "Regalías, derechos de autor, marcas, patentes y similares",
    "319": "Arrendamiento mercantil",
    "320": "Arrendamiento de bienes inmuebles",
    "323": "Rendimientos financieros",
    "327": "Dividendos distribuidos a personas naturales residentes",
    "328": "Dividendos distribuidos a sociedades residentes",

    # ═══════════════════════════════════════════════════════════════════════
    # RESIDENTES — Autorretenciones y otros
    # ═══════════════════════════════════════════════════════════════════════
    "350": "Otras autorretenciones",
    "3440": "Otras retenciones aplicables al 2.75%",
    "345": "Otras retenciones aplicables al 8%",

    # ═══════════════════════════════════════════════════════════════════════
    # RESIDENTES — Totales
    # ═══════════════════════════════════════════════════════════════════════
    "349": "SUBTOTAL OPERACIONES EFECTUADAS EN EL PAÍS — Base imponible",
    "399": "SUBTOTAL OPERACIONES EFECTUADAS EN EL PAÍS — Valor retenido",

    # ═══════════════════════════════════════════════════════════════════════
    # PAGOS AL EXTERIOR — Con Convenio de Doble Imposición (CDI)
    # ═══════════════════════════════════════════════════════════════════════
    "402": "Con CDI — Intereses pagados a proveedores",
    "403": "Con CDI — Intereses por créditos del exterior",
    "404": "Con CDI — Anticipo de dividendos",
    "405": "Con CDI — Dividendos pagados a personas naturales",
    "406": "Con CDI — Dividendos pagados a sociedades",
    "407": "Con CDI — Dividendos pagados a fideicomisos",
    "408": "Con CDI — Enajenación de capital",
    "409": "Con CDI — Seguros y reaseguros (primas y cesiones)",
    "410": "Con CDI — Servicios técnicos, administrativos y regalías",
    "411": "Con CDI — Otros conceptos gravados",
    "412": "Con CDI — Otros conceptos NO sujetos a retención",

    # ═══════════════════════════════════════════════════════════════════════
    # PAGOS AL EXTERIOR — Sin Convenio de Doble Imposición
    # ═══════════════════════════════════════════════════════════════════════
    "413": "Sin CDI — Intereses pagados a proveedores",
    "414": "Sin CDI — Intereses por créditos del exterior",
    "415": "Sin CDI — Anticipo de dividendos",
    "416": "Sin CDI — Dividendos pagados a personas naturales",
    "417": "Sin CDI — Dividendos pagados a sociedades",
    "418": "Sin CDI — Dividendos pagados a fideicomisos",
    "419": "Sin CDI — Seguros y reaseguros (primas y cesiones)",
    "420": "Sin CDI — Servicios técnicos, administrativos y regalías",
    "421": "Sin CDI — Otros conceptos gravados",
    "422": "Sin CDI — Otros conceptos NO sujetos a retención",

    # ═══════════════════════════════════════════════════════════════════════
    # PAGOS AL EXTERIOR — Paraísos fiscales / regímenes de menor imposición
    # ═══════════════════════════════════════════════════════════════════════
    "424": "Paraísos fiscales — Intereses",
    "425": "Paraísos fiscales — Anticipo de dividendos",
    "426": "Paraísos fiscales — Dividendos pagados a personas naturales",
    "427": "Paraísos fiscales — Dividendos pagados a sociedades",
    "428": "Paraísos fiscales — Dividendos pagados a fideicomisos",
    "429": "Paraísos fiscales — Enajenación de capital",
    "430": "Paraísos fiscales — Seguros y reaseguros",
    "431": "Paraísos fiscales — Servicios técnicos, administrativos y regalías",
    "432": "Paraísos fiscales — Otros conceptos gravados",
    "433": "Paraísos fiscales — Otros conceptos NO sujetos a retención",

    # ═══════════════════════════════════════════════════════════════════════
    # PAGOS AL EXTERIOR — Totales
    # ═══════════════════════════════════════════════════════════════════════
    "497": "SUBTOTAL OPERACIONES EFECTUADAS EN EL EXTERIOR — Base imponible",
    "498": "SUBTOTAL OPERACIONES EFECTUADAS EN EL EXTERIOR — Valor retenido",
    "499": "TOTAL DE LA RETENCIÓN DEL IMPUESTO A LA RENTA",
}


def get_casillero_name(casillero: str, fallback: str = "") -> str:
    """Devuelve el nombre oficial del casillero F-103."""
    return F103_CASILLERO_NAMES.get(str(casillero).strip(), fallback)
