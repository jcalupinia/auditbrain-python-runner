"""AUD-CXC-CARTERA — Cuentas por cobrar y deterioro (cartera), como manifest.

Traduce la prueba que ya existe en
``backend/app/aud/niif/procesadores/cxc_cartera.py`` al contrato
``AuditAppManifest`` (benchmark §4.4), siguiendo el mismo patrón que
``aud_inv_vnr.py``. Cada paso apunta a un adaptador determinista de
``cxc_app_adapters`` — el ejecutor no reimplementa el cálculo, lo declara.

``AUD_CXC_CARTERA`` es un dict; se convierte con
``AuditAppManifest.from_dict(AUD_CXC_CARTERA).validate()``.

Nota de diseño: la matriz de tasas de deterioro por tramo del procesador es un
dict (``tasas`` = {tramo: %}) que no encaja en los ``PARAM_TYPES`` planos del
manifest, así que —igual que la VNR con su ``inventario``— la cartera, sus
parámetros y el corte viajan dentro del insumo ``cartera`` (ver el docstring de
``cxc_app_adapters``). Los ``parameters`` del manifest son overrides opcionales.
"""

from __future__ import annotations

_ADAPT = "backend.app.aud.niif.procesadores.cxc_app_adapters."

AUD_CXC_CARTERA: dict = {
    "id": "AUD-CXC-CARTERA",
    "name": "Cuentas por cobrar y deterioro (cartera, cobros, circularización y costo amortizado)",
    "version": "1.0.0",
    "owner": "AuditConsulting Auditores Cía. Ltda.",
    "frameworks": [
        "NIIF 9 (5.1.1, B5.1.1, 5.4.1, 5.5.15, B5.5.35)",
        "NIIF 15 (31, 38, 60-63)",
        "NIIF para las PYMES secc. 11 (11.13, 11.21-11.26)",
        "NIA 505 · NIA 540 (Revisada) · NIA 560",
    ],
    "assertions": ["Valoración", "Existencia", "Integridad", "Corte", "Presentación"],
    "risks": [
        "Deterioro insuficiente o mal estimado (pérdida esperada / incurrida)",
        "Cartera de plazo largo medida por su nominal (financiación implícita no reconocida)",
        "Ventas registradas en un período distinto al del despacho (corte)",
        "Saldos inexistentes o mal medidos (circularización)",
        "Cartera vencida no recuperable sin cobro posterior",
    ],
    "inputs": [
        {
            "id": "cartera",
            "kind": "tabla",
            "formats": ["json", "xlsx", "csv"],
            "columns": [
                "id", "cliente", "emision", "vence", "saldo",
                "importe", "cobro", "fecha_cobro", "confirmado", "despacho", "tasa_individual",
            ],
            "required": True,
            "description": ("Solicitud CXC en JSON: datasets.cartera (una fila por factura al corte), "
                            "corte, parametros (tasaMercado, plazoFinanciacion, provisionRegistrada, "
                            "descuentoRegistrado, tasas por tramo) y engagement opcional."),
        },
    ],
    "parameters": [
        {
            "id": "marco",
            "type": "enum",
            "required": True,
            "description": ("Marco contable: 'full' (NIIF completas → pérdida crediticia esperada) o "
                            "'sme' (NIIF para las PYMES → pérdida incurrida)."),
            "constraints": {"choices": ["full", "sme"]},
        },
        {
            "id": "tasa_mercado",
            "type": "decimal",
            "required": False,
            "default": None,
            "description": "Override de la tasa de mercado anual (%) para el valor presente; sin default.",
            "constraints": {"ge": "0", "le": "100"},
        },
        {
            "id": "plazo_financiacion",
            "type": "int",
            "required": False,
            "default": None,
            "description": "Override del plazo de crédito que se considera financiación (meses).",
            "constraints": {"ge": "0"},
        },
    ],
    "steps": [
        {
            "id": "extraer_cartera",
            "engine_ref": _ADAPT + "extraer_cartera",
            "inputs": ["cartera"],
            "produces": "entrada_cxc",
            "description": "Normaliza el insumo JSON a la solicitud CXC (datasets/parametros/corte/engagement).",
        },
        {
            "id": "calcular_cxc",
            "engine_ref": _ADAPT + "calcular_cxc",
            "inputs": ["entrada_cxc"],
            "parameters": ["marco", "tasa_mercado", "plazo_financiacion"],
            "produces": "resultado_cxc",
            "description": ("Antigüedad, cobros posteriores, circularización, corte de ventas, costo amortizado "
                            "y deterioro requerido vs. registrado; adjunta las cédulas con fórmulas. Determinista."),
        },
        {
            "id": "papel_trabajo_excel",
            "engine_ref": _ADAPT + "papel_trabajo_excel",
            "inputs": ["entrada_cxc", "resultado_cxc"],
            "produces": "xlsx_bytes",
            "description": "Papel de trabajo Excel con fórmulas editables y trazables (12 cédulas + contexto).",
        },
        {
            "id": "papel_trabajo_html",
            "engine_ref": _ADAPT + "papel_trabajo_html",
            "inputs": ["entrada_cxc", "resultado_cxc"],
            "produces": "html_bytes",
            "description": "HTML autónomo sin internet, con Excel/Word/PowerPoint/CSV embebidos para descargar.",
        },
    ],
    "outputs": [
        {
            "id": "cxc_excel",
            "kind": "excel",
            "from_step": "papel_trabajo_excel",
            "sealed": True,
            "description": "Papel de trabajo CXC sellado (versión/timestamp/hash).",
        },
        {
            "id": "cxc_html",
            "kind": "html",
            "from_step": "papel_trabajo_html",
            "sealed": False,
            "description": "Vista de trabajo autónoma para revisión offline.",
        },
        {
            "id": "excepciones_cxc",
            "kind": "excepciones",
            "from_step": "calcular_cxc",
            "sealed": True,
            "description": "Resultado calculado (totales, matriz y excepciones) para revisión del auditor.",
        },
    ],
    "permissions": ["ADMIN", "GERENTE", "SOCIO", "REVISOR"],
    "requires_ai": False,
    "requires_ml": False,
    "acceptance_tests": [
        {
            "id": "deterioro_no_negativo",
            "description": "El deterioro requerido por factura nunca es negativo.",
            "expects": "min(deterioro) >= 0",
        },
        {
            "id": "ajuste_es_diferencia",
            "description": "El ajuste propuesto es deterioro requerido − deterioro registrado.",
            "expects": "ajuste == deterioroRequerido - provisionRegistrada",
        },
        {
            "id": "financiacion_requiere_tasa",
            "description": "Sin tasa de mercado, la cartera de plazo largo no se mide a costo amortizado; se señala.",
            "expects": "financia and tasaMercado is None => FINANCIACION_SIN_TASA",
        },
        {
            "id": "circularizacion_sin_forzar",
            "description": "Las diferencias de circularización se listan, no se fuerzan a cero.",
            "expects": "difCircularizacion listadas",
        },
    ],
}
