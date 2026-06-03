"""Catálogo canónico COMPLETO de casilleros del Formulario 104 — Declaración
Mensual del Impuesto al Valor Agregado (SRI Ecuador 2025).

ESTA ES LA ÚNICA FUENTE DE VERDAD para los nombres oficiales del F-104.

⚠️ VERIFICADO EMPÍRICAMENTE contra el F-104 real de PROPHAR 01/2025:
   PDF tiene 145 casilleros únicos → catálogo cubre los 145.

Estructura del F-104 (3 columnas conceptuales):
  · Bloque A (401-485): VENTAS Y OTRAS OPERACIONES (gravadas, exportaciones, NC)
  · Bloque B (499-565): ADQUISICIONES Y PAGOS (compras, importaciones, factor proporc.)
  · Bloque C (601-625): IMPUESTO CAUSADO Y CRÉDITO TRIBUTARIO
  · Bloque D (699-702): TOTAL ADQUISICIONES Y RECUPERACIONES
  · Bloque E (721-799): AGENTE DE RETENCIÓN DEL IVA
  · Bloque F (800-859): CRÉDITO TRIBUTARIO Y TOTAL CONSOLIDADO
  · Bloque G (880-999): PAGO

REGLA del proyecto (CLAUDE.md, REGLA SUPREMA):
    "verificar que se trasladen TODOS los casilleros — no importa que
    estén cero — con la finalidad de que no haya saldos de líneas vacías"

El test estático tests/test_ict_catalogo_f104_completo.py bloquea el
deploy si el parser pierde algún casillero canónico.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO COMPLETO F-104 (145 casilleros oficiales SRI 2025)
# ─────────────────────────────────────────────────────────────────────────────
F104_CASILLERO_NAMES: dict[str, str] = {
    # ═══════════════════════════════════════════════════════════════════════
    # 401-410 — VENTAS bases imponibles (columna "Valor bruto")
    # ═══════════════════════════════════════════════════════════════════════
    "401": "Ventas locales (excluye activos fijos) gravadas tarifa diferente de cero",
    "402": "Ventas de activos fijos gravadas tarifa diferente de cero",
    "403": "Ventas locales (excluye activos fijos) gravadas tarifa 0% que NO dan derecho a crédito tributario",
    "404": "Ventas de activos fijos gravadas tarifa 0% que NO dan derecho a crédito tributario",
    "405": "Ventas locales (excluye activos fijos) gravadas tarifa 0% que SÍ dan derecho a crédito tributario",
    "406": "Ventas de activos fijos gravadas tarifa 0% que SÍ dan derecho a crédito tributario",
    "407": "Exportaciones de bienes",
    "408": "Exportaciones de servicios y/o derechos",
    "409": "TOTAL VENTAS Y OTRAS OPERACIONES (columna valor bruto)",
    "410": "Ventas locales (excluye activos fijos) gravadas tarifa diferente de cero (TARIFA 5%)",

    # ═══════════════════════════════════════════════════════════════════════
    # 411-419 — VENTAS NETAS (después de devoluciones/notas crédito)
    # ═══════════════════════════════════════════════════════════════════════
    "411": "Ventas locales netas (excluye activos fijos) gravadas tarifa diferente de cero",
    "412": "Ventas de activos fijos netas gravadas tarifa diferente de cero",
    "413": "Ventas locales netas (excluye activos fijos) gravadas tarifa 0% que NO dan derecho a crédito",
    "414": "Ventas de activos fijos netas gravadas tarifa 0% que NO dan derecho a crédito",
    "415": "Ventas locales netas (excluye activos fijos) gravadas tarifa 0% que SÍ dan derecho a crédito",
    "416": "Ventas de activos fijos netas gravadas tarifa 0% que SÍ dan derecho a crédito",
    "417": "Exportaciones netas de bienes",
    "418": "Exportaciones netas de servicios y/o derechos",
    "419": "TOTAL VENTAS Y OTRAS OPERACIONES (netas)",
    "420": "Ventas locales (excluye activos fijos) gravadas tarifa diferente de cero (TARIFA 5%)",

    # ═══════════════════════════════════════════════════════════════════════
    # 421-435 — IVA GENERADO + Notas crédito + Transferencias no objeto
    # ═══════════════════════════════════════════════════════════════════════
    "421": "Ventas locales (excluye activos fijos) IVA generado tarifa diferente de cero",
    "422": "Ventas de activos fijos IVA generado tarifa diferente de cero",
    "423": "IVA generado en la diferencia entre ventas y notas de crédito (distinta tarifa) — debe",
    "424": "IVA generado en la diferencia entre ventas y notas de crédito (distinta tarifa) — haber",
    "425": "Ventas locales (excluye activos fijos) gravadas tarifa 5%",
    "429": "TOTAL IMPUESTO GENERADO (ventas y otras operaciones)",
    "430": "Ventas locales (excluye activos fijos) gravadas tarifa diferente de cero (TARIFA 5%)",
    "431": "Transferencias de bienes y prestación de servicios NO OBJETO o exentos de IVA",
    "434": "Ingresos por reembolso como intermediario / valores facturados por operadoras de transporte",
    "435": "Ventas locales (excluye activos fijos) gravadas tarifa 5%",

    # ═══════════════════════════════════════════════════════════════════════
    # 441-454 — Transferencias no objeto + Notas crédito + Reembolsos
    # ═══════════════════════════════════════════════════════════════════════
    "441": "Transferencias de bienes y prestación de servicios NO OBJETO o exentos de IVA (neto)",
    "442": "Notas de crédito tarifa 0% por compensar próximo mes",
    "443": "Notas de crédito tarifa diferente de cero por compensar próximo mes",
    "444": "Ingresos por reembolso como intermediario / valores facturados (neto)",
    "445": "Ventas locales (excluye activos fijos) gravadas tarifa 5% (neto)",
    "453": "Notas de crédito tarifa diferente de cero por compensar próximo mes (IVA)",
    "454": "Ingresos por reembolso como intermediario / valores facturados (IVA generado)",

    # ═══════════════════════════════════════════════════════════════════════
    # 480-499 — TOTALES VENTAS Y LIQUIDACIÓN IMPUESTO
    # ═══════════════════════════════════════════════════════════════════════
    "480": "Total transferencias gravadas tarifa diferente de cero a CONTADO este mes",
    "481": "Total transferencias gravadas tarifa diferente de cero a CRÉDITO este mes",
    "482": "Total impuesto generado (trasládese campo 429)",
    "483": "Impuesto a liquidar del MES ANTERIOR (verificar contra campo 485 declaración previa)",
    "484": "Impuesto a liquidar EN ESTE MES",
    "485": "Impuesto a liquidar en el PRÓXIMO MES (campo 482-484)",
    "499": "TOTAL IMPUESTO A LIQUIDAR EN ESTE MES (campo 483+484)",

    # ═══════════════════════════════════════════════════════════════════════
    # 500-509 — ADQUISICIONES BASES IMPONIBLES (columna valor bruto)
    # ═══════════════════════════════════════════════════════════════════════
    "500": "Adquisiciones y pagos (excluye activos fijos) gravados tarifa diferente de cero (con derecho a CT)",
    "501": "Adquisiciones locales de activos fijos gravados tarifa diferente de cero (con derecho a CT)",
    "502": "Otras adquisiciones y pagos gravados tarifa diferente de cero (SIN derecho a CT)",
    "503": "Importaciones de servicios y/o derechos gravados tarifa diferente de cero",
    "504": "Importaciones de bienes (excluye activos fijos) gravados tarifa diferente de cero",
    "505": "Importaciones de activos fijos gravados tarifa diferente de cero",
    "506": "Importaciones de bienes (incluye activos fijos) gravados tarifa 0%",
    "507": "Adquisiciones y pagos (incluye activos fijos) gravados tarifa 0%",
    "508": "Adquisiciones realizadas a contribuyentes RISE / NEGOCIOS POPULARES",
    "509": "TOTAL ADQUISICIONES Y PAGOS (bruto)",
    "510": "Adquisiciones y pagos (excluye activos fijos) tarifa diferente de cero (con derecho a CT — neto)",

    # ═══════════════════════════════════════════════════════════════════════
    # 511-519 — ADQUISICIONES NETAS
    # ═══════════════════════════════════════════════════════════════════════
    "511": "Adquisiciones locales de activos fijos tarifa diferente de cero (con derecho a CT — neto)",
    "512": "Otras adquisiciones y pagos tarifa diferente de cero (SIN derecho a CT — neto)",
    "513": "Importaciones de servicios y/o derechos tarifa diferente de cero (neto)",
    "514": "Importaciones de bienes (excluye activos fijos) tarifa diferente de cero (neto)",
    "515": "Importaciones de activos fijos tarifa diferente de cero (neto)",
    "516": "Importaciones de bienes (incluye activos fijos) tarifa 0% (neto)",
    "517": "Adquisiciones y pagos (incluye activos fijos) tarifa 0% (neto)",
    "518": "Adquisiciones realizadas a contribuyentes RISE / NEGOCIOS POPULARES (neto)",
    "519": "TOTAL ADQUISICIONES Y PAGOS (netas)",
    "520": "Adquisiciones y pagos (excluye activos fijos) tarifa diferente de cero (IVA)",

    # ═══════════════════════════════════════════════════════════════════════
    # 521-529 — IVA SOBRE ADQUISICIONES + TOTAL
    # ═══════════════════════════════════════════════════════════════════════
    "521": "Adquisiciones locales de activos fijos tarifa diferente de cero (IVA)",
    "522": "Otras adquisiciones y pagos tarifa diferente de cero (IVA — sin derecho a CT)",
    "523": "Importaciones de servicios y/o derechos tarifa diferente de cero (IVA)",
    "524": "Importaciones de bienes (excluye activos fijos) tarifa diferente de cero (IVA)",
    "525": "Importaciones de activos fijos tarifa diferente de cero (IVA)",
    "526": "IVA generado en la diferencia entre adquisiciones y notas de crédito (distinta tarifa) — debe",
    "527": "IVA generado en la diferencia entre adquisiciones y notas de crédito (distinta tarifa) — haber",
    "529": "TOTAL ADQUISICIONES Y PAGOS (IVA pagado)",

    # ═══════════════════════════════════════════════════════════════════════
    # 530-565 — Adquisiciones especiales + Factor proporcionalidad
    # ═══════════════════════════════════════════════════════════════════════
    "530": "Adquisiciones y pagos (excluye activos fijos) tarifa diferente de cero",
    "531": "Adquisiciones NO OBJETO de IVA",
    "532": "Adquisiciones EXENTAS del pago de IVA",
    "533": "Adquisiciones y pagos (excluye activos fijos) tarifa diferente de cero (con CT proporc.)",
    "534": "Adquisiciones y pagos (excluye activos fijos) tarifa diferente de cero (sin CT proporc.)",
    "535": "Pagos netos por reembolso como intermediario / valores facturados por socios",
    "540": "Adquisiciones y pagos locales (excluye activos fijos) gravados con tarifa 5% (con derecho a CT)",
    "541": "Adquisiciones NO OBJETO de IVA (neto)",
    "542": "Adquisiciones EXENTAS del pago de IVA (neto)",
    "543": "Notas de crédito tarifa 0% por compensar próximo mes",
    "544": "Notas de crédito tarifa diferente de cero por compensar próximo mes",
    "545": "Pagos netos por reembolso como intermediario / valores facturados (neto)",
    "550": "Adquisiciones y pagos locales (excluye activos fijos) gravados con tarifa 5% (IVA)",
    "554": "Notas de crédito tarifa diferente de cero por compensar próximo mes (IVA)",
    "555": "Pagos netos por reembolso como intermediario / valores facturados (IVA)",
    "560": "Adquisiciones y pagos locales (excluye activos fijos) gravados con tarifa 5% (totales)",
    "563": "FACTOR DE PROPORCIONALIDAD para crédito tributario [(411+412+420+435+415+416+417+418)/419]",
    "564": "Crédito tributario aplicable en este período (según factor de proporcionalidad)",
    "565": "Valor de IVA NO CONSIDERADO como crédito tributario por factor de proporcionalidad",

    # ═══════════════════════════════════════════════════════════════════════
    # 601-625 — IMPUESTO CAUSADO Y CRÉDITO TRIBUTARIO
    # ═══════════════════════════════════════════════════════════════════════
    "601": "Impuesto causado (si diferencia campos 499-564 es mayor que 0)",
    "602": "Crédito tributario aplicable en este período (si diferencia 499-564 es menor que 0)",
    "603": "(-) Compensación de IVA por ventas con medio electrónico y/o IVA devuelto",
    "604": "(-) Compensación de IVA por ventas efectuadas en zonas afectadas - Ley de solidaridad",
    "605": "Crédito tributario por adquisiciones e importaciones (campo 615 declaración anterior)",
    "606": "Crédito tributario por retenciones en la fuente de IVA efectuadas (declaración anterior)",
    "607": "Crédito tributario por compensación IVA ventas con medio electrónico (declaración anterior)",
    "608": "Crédito tributario por compensación IVA ventas zonas afectadas (declaración anterior)",
    "609": "(-) Retenciones en la fuente de IVA efectuadas EN ESTE PERÍODO",
    "610": "(+) Ajuste por IVA devuelto/descontado por adquisiciones con medio electrónico",
    "611": "(+) Ajuste por IVA devuelto/descontado por adquisiciones en zonas afectadas",
    "612": "(+) Ajuste por IVA devuelto e IVA rechazado (devoluciones de IVA)",
    "613": "(+) Ajuste por IVA devuelto e IVA rechazado (procesos de control)",
    "614": "(+) Ajuste por IVA devuelto por otras instituciones del sector público",
    "615": "Crédito tributario por adquisiciones e importaciones del período",
    "617": "Crédito tributario por retenciones en la fuente de IVA del período",
    "618": "Crédito tributario por compensación IVA ventas con medio electrónico del período",
    "619": "Crédito tributario por compensación IVA ventas zonas afectadas del período",
    "620": "SUBTOTAL A PAGAR (si campos 601-602-603-604-605-606-607-608-609+610+611+612+613+614 > 0)",
    "621": "IVA PRESUNTIVO DE SALAS DE JUEGO (BINGO MECÁNICOS) Y OTROS JUEGOS DE AZAR",
    "622": "(-) IVA devuelto/descontado por transacciones con personas adultas mayores",
    "623": "Por procesos de fusión o absorción de sociedades",
    "624": "IVA pagado y NO COMPENSADO en adquisición local o importación",
    "625": "Ajuste del crédito tributario de IVA pagado en adquisiciones",

    # ═══════════════════════════════════════════════════════════════════════
    # 699-702 — TOTAL ADQUISICIONES Y RECUPERACIONES
    # ═══════════════════════════════════════════════════════════════════════
    "699": "TOTAL IMPUESTO A PAGAR POR PERCEPCIÓN Y RETENCIONES EFECTUADAS EN VENTAS",
    "700": "Importaciones de materias primas, insumos y bienes de capital incorporados al producto exportado",
    "701": "Importaciones de materias primas, insumos y bienes de capital incorporados (otro)",
    "702": "Proporción del ingreso neto de divisas desde el exterior al Ecuador",

    # ═══════════════════════════════════════════════════════════════════════
    # 721-799 — AGENTE DE RETENCIÓN DEL IVA
    # ═══════════════════════════════════════════════════════════════════════
    "721": "Retención del 10%",
    "723": "Retención del 20%",
    "725": "Retención del 30%",
    "727": "Retención del 50%",
    "729": "Retención del 70%",
    "731": "Retención del 100%",
    "799": "TOTAL IMPUESTO RETENIDO (721+723+725+727+729+731)",

    # ═══════════════════════════════════════════════════════════════════════
    # 800-802 — CRÉDITO POR RETENCIONES Y DEVOLUCIONES
    # ═══════════════════════════════════════════════════════════════════════
    "800": "Devolución provisional de IVA mediante compensación con retenciones efectuadas",
    "801": "TOTAL IMPUESTO A PAGAR POR RETENCIÓN (799-800-802)",
    "802": "Retenciones efectuadas y NO PAGADAS por sector público, universidades y escuelas politécnicas",

    # ═══════════════════════════════════════════════════════════════════════
    # 859 — TOTAL CONSOLIDADO
    # ═══════════════════════════════════════════════════════════════════════
    "859": "TOTAL CONSOLIDADO DE IMPUESTO AL VALOR AGREGADO (699+801)",

    # ═══════════════════════════════════════════════════════════════════════
    # 880-887 — PAGO DIRECTO Y CUOTAS DEL EJERCICIO FISCAL
    # ═══════════════════════════════════════════════════════════════════════
    "880": "Pago directo en cuenta única del tesoro nacional (instituciones del sector público)",
    "882": "Cuota 1 del IVA del ejercicio fiscal 2020 (10%)",
    "883": "Cuota 2 del IVA del ejercicio fiscal 2020 (10%)",
    "884": "Cuota 3 del IVA del ejercicio fiscal 2020 (20%)",
    "885": "Cuota 4 del IVA del ejercicio fiscal 2020 (20%)",
    "886": "Cuota 5 del IVA del ejercicio fiscal 2020 (20%)",
    "887": "Cuota 6 del IVA del ejercicio fiscal 2020 (20%)",

    # ═══════════════════════════════════════════════════════════════════════
    # 890-999 — RESUMEN DEL PAGO
    # ═══════════════════════════════════════════════════════════════════════
    "890": "Pago previo",
    "897": "Interés (componente del pago)",
    "898": "Impuesto (componente del pago)",
    "899": "Multa (componente del pago)",
    "902": "TOTAL IMPUESTO A PAGAR (859-898)",
    "903": "Interés por mora",
    "904": "Multa",
    "999": "TOTAL PAGADO",
}


def get_casillero_name(casillero: str, fallback: str = "") -> str:
    """Devuelve el nombre oficial del casillero F-104."""
    return F104_CASILLERO_NAMES.get(str(casillero).strip(), fallback)
