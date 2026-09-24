"""Adaptadores ``fn(ctx)`` de la Audit App AUD-INV-VNR (AUT-002).

El ejecutor de Audit Apps (``backend/app/audit_apps/executor.py``) invoca cada
paso como ``fn(ctx)`` con ``ctx = {"inputs", "intermediates", "parameters"}``.
Las funciones reales del motor VNR tienen firmas propias
(``engine.calculate(data)``, ``exports.build_xlsx(r)``…), así que estos
adaptadores hacen el puente: desempaquetan ``ctx``, arman los argumentos y
llaman al motor DETERMINISTA real. El LLM no interviene (§6).

Contrato del insumo ``inventario``: la **solicitud VNR completa en JSON** (el
mismo ``data`` que acepta ``engine.calculate``: ``context``/``policy``/``tax``/
``rows``/``ledger_cost``/``ledger_impairment``/``tolerance``). Los parámetros del
manifest (``framework``/``selling_method``/``tax_rate``) son *overrides* opcionales
que se sobreponen a esa solicitud.

Viven bajo ``backend.app.aud.`` para quedar dentro de la allow-list del ejecutor
(``ENGINE_ALLOWLIST``); nunca importan red, IA ni la web.
"""
from __future__ import annotations

import json
from typing import Any

from . import engine, exports


def _cargar_solicitud(raw: Any) -> dict:
    if raw is None:
        raise ValueError("Falta el insumo 'inventario' (solicitud VNR en JSON).")
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode("utf-8")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"El insumo 'inventario' no es JSON válido: {e}") from e
    if not isinstance(raw, dict) or not isinstance(raw.get("rows"), list):
        raise ValueError("La solicitud VNR debe ser un objeto JSON con la lista 'rows'.")
    return raw


def extraer_inventario(ctx: dict) -> dict:
    """Paso 1: normaliza el insumo ``inventario`` a la solicitud VNR (dict)."""
    return _cargar_solicitud(ctx["inputs"].get("inventario"))


def calcular_vnr(ctx: dict) -> dict:
    """Paso 2: sobrepone los parámetros declarados y corre el motor VNR real.

    ``engine.calculate`` valida a fondo (contexto, política, evidencia, tolerancia,
    fila por fila) y devuelve el papel calculado con sus totales y controles.
    """
    data = dict(ctx["intermediates"].get("filas_inventario") or {})
    params = ctx.get("parameters") or {}

    fw = params.get("framework")
    if fw in ("full", "sme"):
        data["context"] = {**(data.get("context") or {}), "framework": fw}
    metodo = params.get("selling_method")
    if metodo in ("unit", "ratio"):
        data["policy"] = {**(data.get("policy") or {}), "selling_method": metodo}
    tasa = params.get("tax_rate")
    if tasa not in (None, "", 0, "0"):
        data["tax"] = {**(data.get("tax") or {}), "enabled": True, "rate": str(tasa)}

    return engine.calculate(data)


def papel_trabajo_excel(ctx: dict) -> bytes:
    """Paso 3: Excel del papel VNR (bytes) desde el resultado calculado."""
    return exports.build_xlsx(ctx["intermediates"]["resultado_vnr"])


def papel_trabajo_html(ctx: dict) -> bytes:
    """Paso 4: HTML autónomo del papel VNR (bytes) desde el resultado calculado."""
    html = exports.build_html(ctx["intermediates"]["resultado_vnr"])
    return html.encode("utf-8") if isinstance(html, str) else html
