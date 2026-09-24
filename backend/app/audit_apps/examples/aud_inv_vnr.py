"""AUD-INV-VNR — Valor Neto de Realización de inventarios (NIC 2), como manifest.

Traduce la prueba VNR que ya existe en ``backend/app/aud/inventarios_vnr/`` al
contrato ``AuditAppManifest`` (benchmark §4.4). Cada paso apunta a un callable
determinista existente del módulo VNR — el ejecutor no reimplementa el cálculo,
lo declara. Sirve de referencia para escribir manifests de otras pruebas.

``AUD_INV_VNR`` es un dict; se convierte con
``AuditAppManifest.from_dict(AUD_INV_VNR).validate()``.
"""

from __future__ import annotations

AUD_INV_VNR: dict = {
    "id": "AUD-INV-VNR",
    "name": "Valor Neto de Realización de inventarios (NIC 2)",
    "version": "1.0.0",
    "owner": "AuditConsulting Auditores Cía. Ltda.",
    "frameworks": [
        "NIC 2 (6, 9, 28-34)",
        "NIIF para las PYMES secc. 13",
        "NIA 540 (Revisada)",
        "NIC 12",
    ],
    "assertions": ["Valoración", "Existencia", "Exactitud"],
    "risks": [
        "Inventario medido por encima de su VNR (sobrevaloración)",
        "Deterioro no reconocido o mal estimado",
        "Reversión de deterioro sin sustento de recuperación",
        "Impuesto diferido mal reconocido por la diferencia temporaria",
    ],
    "inputs": [
        {
            "id": "inventario",
            "kind": "inventario",
            "formats": ["xlsx", "csv", "zip"],
            "columns": [
                "code", "description", "quantity", "unit_cost",
                "selling_price", "completion_cost", "recorded_impairment",
            ],
            "required": True,
            "description": "Inventario valorado al corte, un ítem/lote por fila.",
        },
        {
            "id": "balance",
            "kind": "balance",
            "formats": ["xlsx", "csv"],
            "columns": ["cuenta", "saldo"],
            "required": False,
            "description": "Saldos del mayor para conciliar costo bruto y deterioro (sin forzar cuadre).",
        },
    ],
    "parameters": [
        {
            "id": "framework",
            "type": "enum",
            "required": True,
            "description": "Marco: 'full' (NIIF completas) o 'sme' (PYMES).",
            "constraints": {"choices": ["full", "sme"]},
        },
        {
            "id": "selling_method",
            "type": "enum",
            "required": True,
            "description": "Gastos de venta: 'unit' (por ítem) o 'ratio' (gastos/ventas).",
            "constraints": {"choices": ["unit", "ratio"]},
        },
        {
            "id": "tax_rate",
            "type": "decimal",
            "required": False,
            "default": None,
            "description": "Tasa para el diferido; sin default (SRI: verificar vigente al período).",
            "constraints": {"gt": "0", "le": "1"},
        },
    ],
    "steps": [
        {
            "id": "extraer_inventario",
            "engine_ref": "backend.app.aud.inventarios_vnr.parsers.extract",
            "inputs": ["inventario"],
            "produces": "filas_inventario",
            "description": "Extracción acotada (anti-zip-bomb) del archivo cargado a filas.",
        },
        {
            "id": "calcular_vnr",
            "engine_ref": "backend.app.aud.inventarios_vnr.engine.calculate",
            "inputs": ["filas_inventario", "balance"],
            "parameters": ["framework", "selling_method", "tax_rate"],
            "produces": "resultado_vnr",
            "description": "VNR unitario = MAX(0, precio - terminación - venta); deterioro = MAX(0, costo - VNR). Decimal.",
        },
        {
            "id": "papel_trabajo_excel",
            "engine_ref": "backend.app.aud.inventarios_vnr.exports.build_xlsx",
            "inputs": ["resultado_vnr"],
            "produces": "xlsx_bytes",
            "description": "Papel de trabajo con fórmulas editables y trazables (12 hojas).",
        },
        {
            "id": "papel_trabajo_html",
            "engine_ref": "backend.app.aud.inventarios_vnr.exports.build_html",
            "inputs": ["resultado_vnr"],
            "produces": "html_bytes",
            "description": "HTML autónomo sin internet, con los descargables embebidos.",
        },
    ],
    "outputs": [
        {
            "id": "vnr_excel",
            "kind": "excel",
            "from_step": "papel_trabajo_excel",
            "sealed": True,
            "description": "Papel de trabajo VNR sellado (versión/timestamp/hash).",
        },
        {
            "id": "vnr_html",
            "kind": "html",
            "from_step": "papel_trabajo_html",
            "sealed": False,
            "description": "Vista de trabajo autónoma para revisión offline.",
        },
        {
            "id": "excepciones_vnr",
            "kind": "excepciones",
            "from_step": "calcular_vnr",
            "sealed": True,
            "description": "Ítems con deterioro/ajuste requerido, para revisión del auditor.",
        },
    ],
    "permissions": ["ADMIN", "GERENTE", "SOCIO", "REVISOR"],
    "requires_ai": False,
    "requires_ml": False,
    "acceptance_tests": [
        {
            "id": "piso_cero",
            "description": "El VNR de cada ítem nunca es negativo.",
            "expects": "min(vnr_unit) >= 0",
        },
        {
            "id": "deterioro_no_negativo",
            "description": "El deterioro por ítem es MAX(0, costo - VNR).",
            "expects": "min(impairment) >= 0",
        },
        {
            "id": "reversion_con_sustento",
            "description": "Un ajuste negativo (reversión) exige base de reversión declarada.",
            "expects": "adjustment < 0 => policy.reversal_basis",
        },
        {
            "id": "conciliacion_sin_forzar",
            "description": "La conciliación contra el mayor muestra diferencias, no las fuerza.",
            "expects": "conciliacion.diferencias listadas",
        },
    ],
}
