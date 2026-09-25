"""Adaptadores ``fn(ctx)`` de la Audit App AUD-CXC-CARTERA.

El ejecutor de Audit Apps (``backend/app/audit_apps/executor.py``) invoca cada
paso como ``fn(ctx)`` con ``ctx = {"inputs", "intermediates", "parameters"}``.
El procesador real ``cxc_cartera`` tiene su propia interfaz
(``ejecutar(datasets, parametros, corte)`` → ``hojas(run)``) y el papel de
trabajo se arma con ``libro.xlsx`` / ``libro.html``. Estos adaptadores hacen el
puente: desempaquetan ``ctx``, arman los argumentos y corren el cálculo
DETERMINISTA real. El LLM no interviene (§6): nada de IA ni de red.

Contrato del insumo ``cartera`` — un objeto JSON con la misma forma que el
``EJEMPLO`` del procesador (``cxc_cartera.EJEMPLO``):

- ``datasets``: dict con la lista ``cartera`` (una fila por factura al corte:
  ``id``, ``cliente``, ``emision``, ``vence``, ``saldo`` y, cuando existan,
  ``importe``, ``cobro``, ``fecha_cobro``, ``confirmado``, ``despacho``,
  ``tasa_individual``…). **Obligatorio.**
- ``corte``: fecha de corte del encargo, ``"YYYY-MM-DD"``. **Obligatorio.**
- ``parametros``: dict con los parámetros del procesador (``tasaMercado``,
  ``plazoFinanciacion``, ``provisionRegistrada``, ``descuentoRegistrado`` y la
  matriz ``tasas`` por tramo). Opcional; se completa con los defaults del
  procesador.
- ``engagement``: dict opcional con los datos del encargo para la carátula del
  papel (``client``, ``ruc``, ``framework``, ``cutoff``, ``preparer``,
  ``reviewer``, ``firm``, ``year``).

**Por qué el insumo carga todo (datasets + parametros + corte)** y no se apoya
solo en los ``parameters`` del manifest: la matriz de tasas por tramo del
procesador es un dict (``tasas`` = {tramo: %}) y no encaja en ninguno de los
``PARAM_TYPES`` planos del contrato del manifest (decimal/int/date/bool/text/
enum). Igual que la VNR mete la solicitud completa en su insumo ``inventario``,
aquí la cartera + su configuración viajan dentro del insumo ``cartera``. Los
``parameters`` del manifest (``marco``/``tasa_mercado``/``plazo_financiacion``)
son *overrides* opcionales que se sobreponen a esa solicitud, deterministas.

Viven bajo ``backend.app.aud.`` para quedar dentro de la allow-list del ejecutor
(``ENGINE_ALLOWLIST``).
"""
from __future__ import annotations

import json
from typing import Any

from backend.app.aud.niif.procesadores import cxc_cartera, libro
from backend.app.aud.niif.procesadores.base import MARCO_COMPLETAS, MARCO_PYMES

# Traducción del parámetro ``marco`` del manifest (enum plano) al texto de marco
# que entiende el procesador vía ``_marco`` (``es_pymes`` lo lee).
_MARCOS = {
    "full": MARCO_COMPLETAS,
    "sme": MARCO_PYMES,
    MARCO_COMPLETAS.lower(): MARCO_COMPLETAS,
    MARCO_PYMES.lower(): MARCO_PYMES,
}


def _cargar_solicitud(raw: Any) -> dict:
    """Normaliza el insumo ``cartera`` (bytes/str/dict) a la solicitud CXC."""
    if raw is None:
        raise ValueError("Falta el insumo 'cartera' (solicitud CXC en JSON).")
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode("utf-8")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"El insumo 'cartera' no es JSON válido: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError("La solicitud CXC debe ser un objeto JSON.")
    datasets = raw.get("datasets")
    if not isinstance(datasets, dict) or not isinstance(datasets.get("cartera"), list):
        raise ValueError("La solicitud CXC debe traer datasets.cartera como lista de facturas.")
    if not str(raw.get("corte") or "").strip():
        raise ValueError("La solicitud CXC debe indicar la fecha de corte del encargo.")
    return {
        "datasets": datasets,
        "parametros": dict(raw.get("parametros") or {}),
        "corte": str(raw["corte"]).strip(),
        "engagement": dict(raw.get("engagement") or {}),
    }


def extraer_cartera(ctx: dict) -> dict:
    """Paso 1: normaliza el insumo ``cartera`` a la solicitud CXC (dict con
    ``datasets``/``parametros``/``corte``/``engagement``)."""
    return _cargar_solicitud(ctx["inputs"].get("cartera"))


def calcular_cxc(ctx: dict) -> dict:
    """Paso 2: sobrepone los parámetros declarados y corre el procesador real.

    ``cxc_cartera.ejecutar`` recalcula antigüedad, cobros posteriores,
    circularización, corte de ventas, costo amortizado y el deterioro requerido
    vs. registrado; se le adjunta ``hojas`` (las cédulas con fórmulas) para el
    papel de trabajo, igual que hace el ciclo del servidor.
    """
    entrada = dict(ctx["intermediates"].get("entrada_cxc") or {})
    params = ctx.get("parameters") or {}
    parametros = dict(entrada.get("parametros") or {})

    # Overrides deterministas del manifest sobre la solicitud.
    marco = params.get("marco")
    if marco:
        parametros["_marco"] = _MARCOS.get(str(marco).strip().lower(), parametros.get("_marco") or str(marco))
    parametros.setdefault("_marco", MARCO_COMPLETAS)
    parametros.setdefault("_edicion", "")
    tasa = params.get("tasa_mercado")
    if tasa not in (None, "", 0, "0"):
        parametros["tasaMercado"] = tasa
    plazo = params.get("plazo_financiacion")
    if plazo not in (None, ""):
        parametros["plazoFinanciacion"] = plazo

    run = cxc_cartera.ejecutar(entrada.get("datasets") or {}, parametros, entrada["corte"])
    run["hojas"] = cxc_cartera.hojas(run)
    return run


def _reg(entrada: dict, run: dict, definicion: dict) -> dict:
    """Registro mínimo que ``libro`` necesita para armar el papel: encargo,
    resultado (con ``hojas``) y programa de la herramienta."""
    return {
        "engagement": entrada.get("engagement") or {},
        "run": run,
        "program": definicion.get("program") or [],
        "sources": [],
        "reconciliation": {},
    }


def papel_trabajo_excel(ctx: dict) -> bytes:
    """Paso 3: Excel del papel CXC (bytes) con fórmulas editables y trazables."""
    inter = ctx["intermediates"]
    definicion = cxc_cartera.definicion()
    reg = _reg(inter.get("entrada_cxc") or {}, inter["resultado_cxc"], definicion)
    return libro.xlsx(definicion, reg, [], 1, "APROBADO")


def papel_trabajo_html(ctx: dict) -> bytes:
    """Paso 4: HTML autónomo del papel CXC (bytes), sin internet, con los
    descargables embebidos."""
    inter = ctx["intermediates"]
    definicion = cxc_cartera.definicion()
    reg = _reg(inter.get("entrada_cxc") or {}, inter["resultado_cxc"], definicion)
    html = libro.html(definicion, reg, [], 1, "APROBADO")
    return html if isinstance(html, (bytes, bytearray)) else str(html).encode("utf-8")
