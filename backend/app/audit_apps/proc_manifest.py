"""Fábrica de manifests de Audit App para los procesadores de rubro (AUT-002).

Genera un ``AuditAppManifest`` (como dict) por procesador con ``RUBRO``, todos
apuntando a los adaptadores genéricos ``fn(ctx)`` de
``backend.app.aud.niif.procesadores.app_adapters_rubro``. Así cada rubro NIIF
queda publicado como una Audit App ejecutable (``AUD-<RUBRO>``) sin escribir un
manifest a mano por prueba: el manifest se deriva de ``mod.definicion()``.

``cxc_cartera`` se excluye del lote: ya tiene su app dedicada ``AUD-CXC-CARTERA``.
"""
from __future__ import annotations

from backend.app.aud.niif import procesadores

#: Procesadores que NO entran al lote genérico (tienen app dedicada).
EXCLUIDOS: frozenset[str] = frozenset({"cxc_cartera"})

_REF = "backend.app.aud.niif.procesadores.app_adapters_rubro"


def _app_id(rubro: str) -> str:
    """RUBRO (p.ej. ``ACTIVOS_FIJOS``) → id de app ``AUD-ACTIVOS-FIJOS``."""
    return "AUD-" + rubro.replace("_", "-")


def ids_del_lote() -> list[str]:
    """proc_ids con RUBRO que forman el lote (excluye los dedicados)."""
    return [
        pid for pid, mod in procesadores.PROCESADORES.items()
        if getattr(mod, "RUBRO", None) and pid not in EXCLUIDOS
    ]


def manifest_de(proc_id: str) -> dict:
    """Manifest (dict) de la Audit App del procesador ``proc_id``.

    Deriva metadatos de ``mod.definicion()`` y liga los pasos a los adaptadores
    genéricos (``<proc_id>__extraer`` …). Pasa ``AuditAppManifest.validate()``.
    """
    mod = procesadores.PROCESADORES[proc_id]
    d = mod.definicion() or {}
    rubro = getattr(mod, "RUBRO")
    nombre = d.get("name") or proc_id
    ref = lambda paso: f"{_REF}.{proc_id}__{paso}"  # noqa: E731

    return {
        "id": _app_id(rubro),
        "name": f"Prueba NIIF — {nombre}",
        "version": "1.0.0",
        "owner": "AuditConsulting Auditores Cía. Ltda.",
        "frameworks": list(d.get("frameworks") or ["NIIF completas", "NIIF para las PYMES"]),
        "assertions": list(d.get("assertions") or ["Valoración", "Existencia", "Exactitud"]),
        "risks": list(d.get("risks") or [f"Riesgos de {nombre.lower()} (medición, existencia, corte)."]),
        "inputs": [{
            "id": "solicitud",
            "kind": "tabla",
            "formats": ["json", "xlsx", "csv", "zip"],
            "columns": [],
            "required": True,
            "description": (
                "Solicitud del rubro en JSON: datasets (tablas del procesador), "
                "corte, parametros (opc.) y engagement (opc.)."
            ),
        }],
        "parameters": [{
            "id": "marco",
            "type": "enum",
            "options": ["full", "sme"],
            "required": False,
            "description": "Marco NIIF (completas/PYMES); override sobre la solicitud.",
        }],
        "steps": [
            {"id": "extraer", "engine_ref": ref("extraer"), "inputs": ["solicitud"],
             "produces": "entrada", "description": "Normaliza la solicitud del rubro."},
            {"id": "calcular", "engine_ref": ref("calcular"), "inputs": ["entrada"],
             "parameters": ["marco"], "produces": "resultado",
             "description": f"Corre el procesador determinista {proc_id} (recalcula el rubro)."},
            {"id": "papel_excel", "engine_ref": ref("papel_excel"), "inputs": ["resultado"],
             "produces": "xlsx_bytes", "description": "Papel de trabajo Excel con fórmulas."},
            {"id": "papel_html", "engine_ref": ref("papel_html"), "inputs": ["resultado"],
             "produces": "html_bytes", "description": "Papel de trabajo HTML autónomo."},
        ],
        "outputs": [
            {"id": "papel_excel", "kind": "excel", "from_step": "papel_excel", "sealed": True},
            {"id": "papel_html", "kind": "html", "from_step": "papel_html"},
            {"id": "excepciones", "kind": "excepciones", "from_step": "calcular"},
        ],
        "permissions": ["aud:ciclo"],
    }


def manifests_del_lote() -> list[dict]:
    """Todos los manifests del lote (uno por procesador de rubro no excluido)."""
    return [manifest_de(pid) for pid in ids_del_lote()]
