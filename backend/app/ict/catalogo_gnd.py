"""Catálogo de Gastos No Deducibles (GND) — descripción y normativa SRI.

GENERADO automáticamente desde el archivo del cliente
`gastos_no_deducibles_CMGND_final.xlsx` (hoja "gastos no deducibles").
NO editar a mano: regenerar con scripts/generate_catalogo_gnd.py.

Mapea cada casillero de gasto no deducible (rango 7001-7999, "VALOR NO
DEDUCIBLE" en el F-101) a una tupla (descripción, normativa). Lo usa el
A5 Cuadro A para autocompletar las columnas E (descripción del tipo de
gasto) y G (normativa aplicable) cuando traslada un casillero declarado.

Cobertura: 99 casilleros (100%% de los 7xxx no deducibles del F-101).
"""
from __future__ import annotations


# casillero -> (descripcion_tipo_gasto, normativa_aplicable)
GND_CASILLERO_INFO: dict[str, tuple[str, str]] = {
    '7006': ('Compras locales sin sustento o no aceptadas fiscalmente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7009': ('Importaciones sin sustento aduanero/tributario suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7\nArt. 110 COPCI'),
    '7018': ('Compras locales sin sustento o no aceptadas fiscalmente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7021': ('Importaciones sin sustento aduanero/tributario suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7\nArt. 110 COPCI'),
    '7039': ('Ajustes contables no aceptados tributariamente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7042': ('Remuneraciones, beneficios o aportes laborales no aceptados fiscalmente', 'Art. 10 LRTI (9)'),
    '7045': ('Remuneraciones, beneficios o aportes laborales no aceptados fiscalmente', 'Art. 10 LRTI (9)'),
    '7048': ('Remuneraciones, beneficios o aportes laborales no aceptados fiscalmente', 'Art. 10 LRTI (9)'),
    '7051': ('Honorarios profesionales y dietas sin requisitos de deducibilidad', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7\nArt. 35 RALRTI num. 8'),
    '7054': ('Honorarios y pagos a no residentes sin requisitos tributarios', 'Art. 13 LRTI\nArt. 35 RALRTI num. 8'),
    '7057': ('Provisiones laborales por jubilación patronal o desahucio', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7060': ('Provisiones laborales por jubilación patronal o desahucio', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7063': ('Remuneraciones, beneficios o aportes laborales no aceptados fiscalmente', 'Art. 10 LRTI (9)'),
    '7066': ('Depreciación que excede límites tributarios', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6\nArt. innumerado posterior al Art. 28 RALRTI num. 14'),
    '7069': ('Depreciación que excede límites tributarios', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6\nArt. innumerado posterior al Art. 28 RALRTI num. 14'),
    '7072': ('Depreciación que excede límites tributarios', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6\nArt. innumerado posterior al Art. 28 RALRTI num. 14'),
    '7075': ('Depreciación que excede límites tributarios', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6\nArt. innumerado posterior al Art. 28 RALRTI num. 14'),
    '7078': ('Depreciación originada en revaluación no deducible', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6'),
    '7081': ('Depreciación originada en revaluación no deducible', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6'),
    '7084': ('Depreciación originada en revaluación no deducible', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6'),
    '7087': ('Depreciación originada en revaluación no deducible', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6'),
    '7090': ('Depreciación que excede límites tributarios', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6\nArt. innumerado posterior al Art. 28 RALRTI num. 14'),
    '7093': ('Depreciación que excede límites tributarios', 'Art. 10 LRTI (7)\nArt. 28 RALRTI num. 6\nArt. innumerado posterior al Art. 28 RALRTI num. 14'),
    '7096': ('Amortización no aceptada o fuera de plazos tributarios', 'Art. 10 LRTI (8)\nArt. 28 RALRTI num. 7'),
    '7099': ('Amortización no aceptada o fuera de plazos tributarios', 'Art. 10 LRTI (8)\nArt. 28 RALRTI num. 7'),
    '7102': ('Amortización no aceptada o fuera de plazos tributarios', 'Art. 10 LRTI (8)\nArt. 28 RALRTI num. 7'),
    '7105': ('Amortización no aceptada o fuera de plazos tributarios', 'Art. 10 LRTI (8)\nArt. 28 RALRTI num. 7'),
    '7108': ('Amortización no aceptada o fuera de plazos tributarios', 'Art. 10 LRTI (8)\nArt. 28 RALRTI num. 7'),
    '7111': ('Amortización no aceptada o fuera de plazos tributarios', 'Art. 10 LRTI (8)\nArt. 28 RALRTI num. 7'),
    '7114': ('Reversión/provisión de créditos incobrables no aceptada', 'Art. 10 LRTI (11)\nArt. 28 RALRTI num. 3'),
    '7117': ('Deterioro de inventarios con impuesto diferido', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 1'),
    '7120': ('Deterioro de activos no corrientes mantenidos para la venta', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 6'),
    '7123': ('Deterioro o medición de activos biológicos no sujeto en el período', 'Art. innumerado posterior al Art. 28 RALRTI num. 7'),
    '7126': ('Deterioro de activos no corrientes no deducible al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 4'),
    '7129': ('Deterioro de activos no corrientes no deducible al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 4'),
    '7132': ('Deterioro de activos no corrientes no deducible al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 4'),
    '7135': ('Deterioro de activos no corrientes no deducible al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 4'),
    '7138': ('Deterioro de activos no corrientes no deducible al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 4'),
    '7141': ('Deterioro de activos no corrientes no deducible al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 4'),
    '7144': ('Provisión contable no aceptada fiscalmente al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7147': ('Provisión por desmantelamiento y actualización financiera', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 3'),
    '7150': ('Provisión contable no aceptada fiscalmente al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7153': ('Provisión contable no aceptada fiscalmente al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7156': ('Provisión contable no aceptada fiscalmente al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7159': ('Provisión contable no aceptada fiscalmente al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7162': ('Provisión contable no aceptada fiscalmente al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7165': ('Provisión contable no aceptada fiscalmente al registro', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7168': ('Pérdida en venta de activos no aceptada fiscalmente', 'Art. 10 LRTI (5)\nArt. 35 RALRTI num. 3'),
    '7171': ('Pérdida en venta de activos no aceptada fiscalmente', 'Art. 10 LRTI (5)\nArt. 35 RALRTI num. 3'),
    '7174': ('Promoción y publicidad que excede límites tributarios', 'Art. 10 LRTI (1)\nArt. 28 RALRTI num. 11'),
    '7177': ('Gasto operativo sin causalidad o sustento suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7180': ('Gasto operativo sin causalidad o sustento suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7183': ('Gastos de viaje superiores al límite legal', 'Art. 10 LRTI (6) Art. 28 RALRTI num. 9'),
    '7186': ('Gastos de gestión superiores al límite legal', 'Art. 10 LRTI (1) Art. 28 RALRTI num. 10'),
    '7189': ('Gasto operativo sin causalidad o sustento suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7192': ('Gasto operativo sin causalidad o sustento suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7195': ('Pérdida en enajenación de derechos representativos de capital', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7198': ('Gasto operativo sin causalidad o sustento suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7201': ('Mermas o bajas de inventario sin soporte legal', 'Art. 28 RALRTI num. 8 literal b)'),
    '7204': ('Gasto operativo sin causalidad o sustento suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7207': ('Gastos indirectos asignados desde exterior por relacionadas', 'Art. 30 RALRTI num. C'),
    '7210': ('Impuestos, contribuciones, intereses o multas no deducibles', 'Art. 10 LRTI (3)\nArt. 35 RALRTI num. 6'),
    '7213': ('Comisiones sin requisitos de deducibilidad', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7\nArt. 35 RALRTI num. 8'),
    '7216': ('Comisiones sin requisitos de deducibilidad', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7\nArt. 35 RALRTI num. 8'),
    '7219': ('Comisiones sin requisitos de deducibilidad', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7\nArt. 35 RALRTI num. 8'),
    '7222': ('Comisiones sin requisitos de deducibilidad', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7\nArt. 35 RALRTI num. 8'),
    '7225': ('Regalías, servicios técnicos, administrativos o consultoría no deducibles', 'Art. 10 LRTI (19)\nArt. 28 RALRTI num. 16'),
    '7228': ('Regalías, servicios técnicos, administrativos o consultoría no deducibles', 'Art. 10 LRTI (19)\nArt. 28 RALRTI num. 16'),
    '7231': ('Regalías, servicios técnicos, administrativos o consultoría no deducibles', 'Art. 10 LRTI (19)\nArt. 28 RALRTI num. 16'),
    '7234': ('Regalías, servicios técnicos, administrativos o consultoría no deducibles', 'Art. 10 LRTI (19)\nArt. 28 RALRTI num. 16'),
    '7237': ('Gastos de instalación, organización y similares no aceptados', 'Art. 28 RALRTI num. 17'),
    '7240': ('IVA cargado al gasto no aceptado como deducible', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7243': ('Gasto operativo sin causalidad o sustento suficiente', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7246': ('Pérdidas por siniestros sin soporte o indemnización', 'Art. 10 LRTI (5)\nArt. 35 RALRTI num. 7'),
    '7249': ('Otros gastos no deducibles autoglosados o no aceptados', 'Art. 10 LRTI (1)\nArt. 35 RALRTI nums. 2, 6, 7 y 8'),
    '7252': ('Arrendamiento mercantil no deducible', 'Art. 13 LRTI (9)\nArt. 28 RALRTI num. 15'),
    '7255': ('Arrendamiento mercantil no deducible', 'Art. 13 LRTI (9)\nArt. 28 RALRTI num. 15'),
    '7258': ('Arrendamiento mercantil no deducible', 'Art. 13 LRTI (9)\nArt. 28 RALRTI num. 15'),
    '7261': ('Arrendamiento mercantil no deducible', 'Art. 13 LRTI (9)\nArt. 28 RALRTI num. 15'),
    '7264': ('Intereses con partes relacionadas sujetos a límites', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3\nArt. 30 RALRTI'),
    '7267': ('Intereses con partes relacionadas sujetos a límites', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3\nArt. 30 RALRTI'),
    '7270': ('Costos/gastos de transacción financiera no aceptados', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7273': ('Costos/gastos de transacción financiera no aceptados', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 7'),
    '7276': ('Intereses con partes relacionadas sujetos a límites', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3\nArt. 30 RALRTI'),
    '7279': ('Intereses con partes relacionadas sujetos a límites', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3\nArt. 30 RALRTI'),
    '7282': ('Intereses con terceros sujetos a límites tributarios', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3'),
    '7285': ('Intereses con terceros sujetos a límites tributarios', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3'),
    '7288': ('Intereses con partes relacionadas sujetos a límites', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3\nArt. 30 RALRTI'),
    '7291': ('Intereses con partes relacionadas sujetos a límites', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3\nArt. 30 RALRTI'),
    '7294': ('Intereses con terceros sujetos a límites tributarios', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3'),
    '7297': ('Intereses con terceros sujetos a límites tributarios', 'Art. 10 LRTI (2)\nArt. 29 RALRTI num. 3'),
    '7300': ('Reversión del descuento de provisiones a valor presente', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 5'),
    '7303': ('Intereses implícitos por transacciones financieras o pagos diferidos', 'Art. 10 LRTI (2)\nArt. 35 RALRTI num. 7'),
    '7306': ('Otros gastos financieros no deducibles', 'Art. 10 LRTI (2)\nArt. 13 LRTI (3)\nArt. 35 RALRTI num. 7'),
    '7309': ('Pérdidas por método de participación patrimonial', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 2'),
    '7312': ('Otros gastos no operacionales no deducibles', 'Art. 10 LRTI (1)\nArt. 35 RALRTI nums. 2, 7 y 8'),
    '7315': ('Pérdidas de actividades discontinuadas', 'Art. 10 LRTI (1)\nArt. 35 RALRTI num. 2'),
    '7655': ('Amortización de derecho de uso por activos arrendados', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 13'),
    '7793': ('Interés del pasivo por arrendamiento', 'Art. innumerado posterior al Art. 10 LRTI\nArt. innumerado posterior al Art. 28 RALRTI num. 13'),
}


def gnd_descripcion(casillero: str) -> str | None:
    """Descripción del tipo de gasto no deducible, o None si no está."""
    info = GND_CASILLERO_INFO.get(str(casillero).strip())
    return info[0] if info else None


def gnd_normativa(casillero: str) -> str | None:
    """Normativa aplicable al gasto no deducible, o None si no está."""
    info = GND_CASILLERO_INFO.get(str(casillero).strip())
    return info[1] if info else None
