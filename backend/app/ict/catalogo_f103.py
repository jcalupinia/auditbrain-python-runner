"""Catálogo canónico COMPLETO de casilleros del Formulario 103 — Declaración
Mensual de Retenciones en la Fuente del Impuesto a la Renta (SRI Ecuador 2025).

⚠️ VERIFICADO EMPÍRICAMENTE: PDF tiene 83 casilleros únicos detectables
   → este catálogo cubre los 83.

⚠️ REGLA SUPREMA (CLAUDE.md): contar PDF vs Excel ANTES de entregar.
Generado automáticamente desde el PDF oficial.
"""

from __future__ import annotations


F103_CASILLERO_NAMES: dict[str, str] = {
    "302": "En relación de dependencia que supera o no la base desgravada",
    "303": "Honorarios profesionales",
    "304": "Predomina el intelecto",
    "307": "Predomina la mano de obra",
    "308": "Utilización o aprovechamiento de la imagen o renombre (personas naturales, sociedades, influencers)",
    "309": "Publicidad y comunicación",
    "310": "Transporte privado de pasajeros o servicio público o privado de carga",
    "311": "A través de liquidaciones de compra (nivel cultural o rusticidad)",
    "312": "Transferencia de bienes muebles de naturaleza corporal",
    "314": "Por regalías, derechos de autor, marcas, patentes y similares",
    "319": "Mercantil",
    "320": "Bienes inmuebles",
    "322": "Seguros y reaseguros (primas y cesiones)",
    "323": "Rendimientos financieros",
    "324": "Rendimientos financieros entre instituciones del sistema financiero y entidades economía popular y solidaria",
    "325": "Anticipo dividendos",
    "326": "Dividendos distribuidos que correspondan al impuesto a la renta único establecido en el art. 27 de la LRTI",
    "327": "Dividendos distribuidos a personas naturales residentes",
    "328": "Dividendos distribuidos a sociedades residentes",
    "329": "Dividendos distribuidos a fideicomisos residentes",
    "330": "Dividendos gravados distribuidos en acciones (reinversión de utilidades sin derecho a reducción tarifa IR)",
    "331": "Dividendos en acciones (capitalización de utilidades)",
    "332": "Pagos de bienes y servicios no sujetos a retención o con 0% (distintos de rendimientos financieros)",
    "333": "Ganancia en la enajenación de derechos representativos de capital u otros derechos que permitan la exploración, explotación, concesión",
    "334": "Contraprestación en la enajenación de derechos representativos de capital u otros derechos que permitan la exploración, explotación,",
    "335": "Loterías, rifas, apuestas, pronósticos deportivos y similares",
    "336": "A comercializadoras",
    "337": "A distribuidores",
    "338": "Compra local de banano a productor 510 0",
    "339": "Liquidación impuesto único a la venta local de banano de producción propia 520 0",
    "340": "Impuesto único a la exportación de banano de producción propia - componente 1 530 0",
    "341": "Impuesto único a la exportación de banano de producción propia - componente 2 540 0",
    "342": "Impuesto único a la exportación de banano producido por terceros 550 0",
    "343": "Pagos aplicables el 1% (Energía Eléctrica y régimen RIMPE - Emprendedores, para este caso aplica con cualquier forma de pago",
    "344": "Pagos aplicables el 2% (incluye Pago local tarjeta de crédito /débito reportada por la Emisora de tarjeta de crédito / entidades del sistema",
    "345": "Aplicables el 8%",
    "346": "Aplicables a otros porcentajes ( Por Donaciones en dinero -Impuesto a las donaciones )",
    "349": "SUBTOTAL OPERACIONES EFECTUADAS EN EL PAÍS",
    "350": "Otras autorretenciones (inciso 1 y 2 Art.92.1 RLRTI)",
    "402": "…………………Intereses por financiamiento de proveedores",
    "403": "…………………Intereses de créditos",
    "406": "…………………Dividendos distribuidos a sociedades",
    "408": "concesión o similares de sociedades",
    "413": "…………………Intereses por financiamiento de proveedores",
    "414": "…………………Intereses de créditos",
    "417": "…………………Dividendos distribuidos a sociedades",
    "419": "SRIDEC2025123099204 992782491950 10-02-2025 4",
    "424": "…………………Intereses",
    "425": "…………………Anticipo de dividendos",
    "426": "…………………Dividendos distribuidos a personas naturales",
    "427": "…………………Dividendos distribuidos a sociedades",
    "428": "…………………Dividendos distribuidos a fideicomisos",
    "429": "…………………Pago a no residentes - Enajenación de derechos representativos de capital u otros derechos que permitan la",
    "430": "…………………Seguros y reaseguros (primas y cesiones)",
    "431": "…………………Servicios técnicos, administrativos o de consultoría y regalías",
    "432": "…………………Otros conceptos de ingresos gravados",
    "433": "…………………Otros pagos al exterior no sujetos a retención",
    "497": "SUBTOTAL OPERACIONES EFECTUADAS CON EL EXTERIOR",
    "499": "TOTAL DE RETENCIÓN DE IMPUESTO A LA RENTA 399 + 498",
    "880": "Pago directo en cuenta única del tesoro nacional (uso exclusivo para instituciones y empresas del sector público autorizadas)",
    "890": "Pago previo",
    "898": "Impuesto",
    "902": "TOTAL IMPUESTO A PAGAR 499 - 898",
    "903": "Interés por mora",
    "999": "TOTAL PAGADO",
    "3030": "Servicios profesionales prestados por sociedades residentes",
    "3120": "COMPRAS AL PRODUCTOR: de bienes de origen agrícola, avícola, pecuario, apícola, cunícola, bioacuático, forestal y carnes en estado",
    "3121": "COMPRAS AL COMERCIALIZADOR: de bienes de origen agrícola, avícola, pecuario, apícola, cunícola, bioacuático, forestal y carnes en",
    "3140": "Comisiones pagadas a sociedades, nacionales o extranjeras residentes en el Ecuador y establecimientos permanentes domiciliados en el",
    "3230": "Otros Rendimientos financieros 0%",
    "3370": "Retención a cargo del propio sujeto pasivo por la comercialización de productos forestales",
    "3430": "Actividades de construcción de obra material inmueble, urbanización, lotización o actividades similares",
    "3440": "Aplicables el 2,75%",
    "3480": "Impuesto a la renta único sobre los ingresos percibidos por los operadores de pronósticos deportivos",
    "3482": "Autorretenciones Sociedades Grandes Contribuyentes Porcentaje de",
    "3483": "+) Ingresos generados por la actividad económica de pronósticos deportivos",
    "3484": "+) Comisiones derivadas de la actividad de pronósticos deportivos",
    "3485": "Premios pagados por pronósticos deportivos",
    "4260": "…………………Dividendos sin beneficiario efectivo persona natural residente en Ecuador",
    "4270": "…………………Dividendos con beneficiario efectivo persona natural residente en Ecuador",
    "4280": "…………………Dividendos incumpliendo el deber de informar la composición societaria",
    "5100": "Producción y venta local de banano producido o no por el mismo sujeto pasivo",
    "5300": "Impuesto único a la exportación de banano",
}


def get_casillero_name(casillero: str, fallback: str = "") -> str:
    """Devuelve el nombre oficial del casillero F-103."""
    return F103_CASILLERO_NAMES.get(str(casillero).strip(), fallback)
