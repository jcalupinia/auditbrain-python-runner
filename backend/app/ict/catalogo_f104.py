"""Catálogo canónico de casilleros del Formulario 104 — Declaración Mensual
del Impuesto al Valor Agregado (SRI Ecuador 2025).

ESTA ES LA ÚNICA FUENTE DE VERDAD para los nombres oficiales del F-104.
Regla del proyecto (CLAUDE.md / pedido del usuario):

    "se verifique que se traslada TODOS los casilleros con sus códigos,
    nombres, valores — no importa que estén en cero, con la finalidad
    de que no haya saldos de líneas [vacías]"

El test estático tests/test_ict_catalogo_f104_completo.py bloquea el
deploy si algún casillero del parser ALL_CASILLEROS de
backend/app/aud/obligaciones_fiscales/cedulas/f104_extractor.py
queda sin nombre acá.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO COMPLETO F-104 — { casillero_str: nombre_oficial }
# ─────────────────────────────────────────────────────────────────────────────
# Organizado en 2 bloques:
#   - VENTAS Y SERVICIOS (411-499)
#   - AGENTE DE RETENCIÓN DEL IVA (529, 721-799)
F104_CASILLERO_NAMES: dict[str, str] = {
    # ═══════════════════════════════════════════════════════════════════════
    # VENTAS Y SERVICIOS — Ventas locales
    # ═══════════════════════════════════════════════════════════════════════
    "411": "Ventas locales (excluye activos fijos) gravadas tarifa diferente de 0% IVA",
    "412": "Ventas de activos fijos gravadas tarifa diferente de 0% IVA",
    "413": "Ventas locales (excluye activos fijos) gravadas tarifa 0% IVA o exentas — Sin derecho a crédito tributario",
    "414": "Ventas de activos fijos gravadas tarifa 0% IVA o exentas — Sin derecho a crédito tributario",
    "415": "Ventas locales (excluye activos fijos) gravadas tarifa 0% IVA — Con derecho a crédito tributario",
    "416": "Ventas de activos fijos gravadas tarifa 0% IVA — Con derecho a crédito tributario",

    # ═══════════════════════════════════════════════════════════════════════
    # VENTAS Y SERVICIOS — Exportaciones y transferencias no objeto
    # ═══════════════════════════════════════════════════════════════════════
    "417": "Exportaciones de bienes",
    "418": "Exportaciones de servicios",
    "419": "Transferencias no objeto o exentas de IVA",
    "420": "Notas de crédito tarifa diferente de 0% por compensar próximo mes",

    # ═══════════════════════════════════════════════════════════════════════
    # VENTAS Y SERVICIOS — Bases imponibles e impuesto
    # ═══════════════════════════════════════════════════════════════════════
    "421": "Ingresos por reembolso como intermediario",
    "429": "TOTAL TRANSFERENCIAS GRAVADAS TARIFA DIFERENTE DE 0% A CONTADO ESTE MES",
    "480": "TOTAL VENTAS DEL PERÍODO",
    "499": "IMPUESTO CAUSADO",

    # ═══════════════════════════════════════════════════════════════════════
    # AGENTE DE RETENCIÓN DEL IVA — Resumen del período
    # ═══════════════════════════════════════════════════════════════════════
    "529": "TOTAL DEL IMPUESTO A PAGAR POR PERCEPCIÓN",

    # ═══════════════════════════════════════════════════════════════════════
    # AGENTE DE RETENCIÓN DEL IVA — Retenciones a residentes
    # ═══════════════════════════════════════════════════════════════════════
    "721": "Retención del 10% en compras y servicios — Bienes",
    "723": "Retención del 20% en compras y servicios — Servicios profesionales",
    "725": "Retención del 30% en compras y servicios — Bienes",
    "727": "Retención del 70% en compras y servicios — Servicios",
    "729": "Retención del 100% en compras y servicios — Servicios prestados por profesionales",
    "731": "Retención presuntiva y otras retenciones aplicables",
    "799": "TOTAL DE LA RETENCIÓN DEL IVA",
}


def get_casillero_name(casillero: str, fallback: str = "") -> str:
    """Devuelve el nombre oficial del casillero F-104."""
    return F104_CASILLERO_NAMES.get(str(casillero).strip(), fallback)
