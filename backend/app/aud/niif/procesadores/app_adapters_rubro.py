"""Adaptadores ``fn(ctx)`` GENÉRICOS para las Audit Apps de los procesadores RUBRO.

Todos los procesadores de rubro comparten la misma interfaz determinista
(``ejecutar(datasets, parametros, corte)`` → ``hojas(run)``, ``definicion()``,
``EJEMPLO``), así que en vez de escribir un módulo de adaptadores por prueba
(como VNR/CXC) se generan aquí de una sola vez, parametrizados por ``proc_id``.

Para cada procesador con ``RUBRO`` se inyectan en el espacio del módulo cuatro
funciones ``fn(ctx)`` con nombres ``<proc_id>__extraer`` / ``<proc_id>__calcular``
/ ``<proc_id>__papel_excel`` / ``<proc_id>__papel_html``. El manifest de cada app
(``audit_apps.proc_manifest.manifest_de``) apunta sus ``engine_ref`` a esos
nombres, así que el ejecutor los resuelve por su ruta punteada (``getattr``) y el
``proc_id`` queda ligado en el closure — el cliente no lo elige.

Contrato del insumo ``solicitud`` (mismo espíritu que VNR/CXC): un objeto JSON con
la forma del ``EJEMPLO`` del procesador — ``datasets`` (dict de tablas del rubro),
``corte`` ("YYYY-MM-DD"), ``parametros`` (opcional) y ``engagement`` (opcional
para la carátula). El único ``parameter`` del manifest es ``marco`` (full/sme),
override determinista sobre la solicitud. Nada de IA ni de red (§6).

Viven bajo ``backend.app.aud.`` → dentro de la allow-list del ejecutor.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from backend.app.aud.niif import procesadores
from backend.app.aud.niif.procesadores import libro
from backend.app.aud.niif.procesadores.base import MARCO_COMPLETAS, MARCO_PYMES

_MARCOS = {
    "full": MARCO_COMPLETAS,
    "sme": MARCO_PYMES,
    MARCO_COMPLETAS.lower(): MARCO_COMPLETAS,
    MARCO_PYMES.lower(): MARCO_PYMES,
}


def _cargar_solicitud(raw: Any) -> dict:
    """Normaliza el insumo ``solicitud`` (bytes/str/dict) a la entrada del rubro."""
    if raw is None:
        raise ValueError("Falta el insumo 'solicitud' (datos del rubro en JSON).")
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode("utf-8")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"El insumo 'solicitud' no es JSON válido: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError("La solicitud debe ser un objeto JSON.")
    datasets = raw.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise ValueError("La solicitud debe traer 'datasets' (dict de tablas del rubro).")
    if not str(raw.get("corte") or "").strip():
        raise ValueError("La solicitud debe indicar la fecha de corte del encargo.")
    return {
        "datasets": datasets,
        "parametros": dict(raw.get("parametros") or {}),
        "corte": str(raw["corte"]).strip(),
        "engagement": dict(raw.get("engagement") or {}),
    }


def _hacer(proc_id: str) -> tuple[Callable, Callable, Callable, Callable]:
    """Crea las 4 funciones ``fn(ctx)`` ligadas a ``proc_id`` (closure)."""

    def _mod():
        return procesadores.PROCESADORES[proc_id]

    def extraer(ctx: dict) -> dict:
        return _cargar_solicitud(ctx["inputs"].get("solicitud"))

    def calcular(ctx: dict) -> dict:
        entrada = dict(ctx["intermediates"].get("entrada") or {})
        params = ctx.get("parameters") or {}
        parametros = dict(entrada.get("parametros") or {})
        marco = params.get("marco")
        if marco:
            parametros["_marco"] = _MARCOS.get(str(marco).strip().lower(),
                                               parametros.get("_marco") or str(marco))
        parametros.setdefault("_marco", MARCO_COMPLETAS)
        parametros.setdefault("_edicion", "")
        mod = _mod()
        run = mod.ejecutar(entrada.get("datasets") or {}, parametros, entrada["corte"])
        run["hojas"] = mod.hojas(run)
        return run

    def _reg(ctx: dict) -> tuple[dict, dict]:
        inter = ctx["intermediates"]
        definicion = _mod().definicion()
        entrada = inter.get("entrada") or {}
        reg = {
            "engagement": entrada.get("engagement") or {},
            "run": inter["resultado"],
            "program": definicion.get("program") or [],
            "sources": [],
            "reconciliation": {},
        }
        return definicion, reg

    def papel_excel(ctx: dict) -> bytes:
        definicion, reg = _reg(ctx)
        return libro.xlsx(definicion, reg, [], 1, "APROBADO")

    def papel_html(ctx: dict) -> bytes:
        definicion, reg = _reg(ctx)
        html = libro.html(definicion, reg, [], 1, "APROBADO")
        return html if isinstance(html, (bytes, bytearray)) else str(html).encode("utf-8")

    return extraer, calcular, papel_excel, papel_html


#: Ids de los procesadores de rubro (los que exponen ``RUBRO``).
RUBRO_IDS: tuple[str, ...] = tuple(
    pid for pid, mod in procesadores.PROCESADORES.items() if getattr(mod, "RUBRO", None)
)

# Inyecta <proc_id>__extraer / __calcular / __papel_excel / __papel_html por rubro.
for _pid in RUBRO_IDS:
    _e, _c, _x, _h = _hacer(_pid)
    globals()[f"{_pid}__extraer"] = _e
    globals()[f"{_pid}__calcular"] = _c
    globals()[f"{_pid}__papel_excel"] = _x
    globals()[f"{_pid}__papel_html"] = _h
