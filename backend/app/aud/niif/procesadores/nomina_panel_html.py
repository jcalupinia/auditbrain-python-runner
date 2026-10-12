# -*- coding: utf-8 -*-
"""Render del panel propio de la herramienta de nómina 2.0 (la «cara»).

Igual que ``artefacto_html`` hace con la planificación: toma la plantilla del panel
entregado por la firma (``assets/nomina_panel.tmpl.html``) y le inyecta el encargo del
Command Center (cliente, RUC, ejercicio, corte, visita, marco, preparado/revisado y el
logo del cliente) en el placeholder ``__NOMINA_ENC__``, más ``__NOMINA_API__`` con la
base del API y el id de la prueba para que los botones de descarga pidan las cédulas al
MOTOR Python. El motor y las 15 cédulas los produce ``nomina_beneficios.correr_prueba``;
esto solo arma el HTML del panel.
"""
from __future__ import annotations

import html as _html
import json
import os
import re

_TMPL = os.path.join(os.path.dirname(__file__), "..", "assets", "nomina_panel.tmpl.html")

# Firmas que la plantilla reconoce (constante FIRMS del panel): la del encargo decide cuál.
_FIRMAS = ("partner", "audit")


def _firma(engagement: dict) -> str:
    """'audit' (AuditConsulting, por defecto) o 'partner' (Partner Auditing) según la ficha."""
    f = str(engagement.get("firm") or engagement.get("firma") or "").strip().lower()
    if "partner" in f:
        return "partner"
    return "audit"


def _corte_ddmmyyyy(engagement: dict) -> str:
    """Corte en dd/mm/aaaa para el panel; acepta 'AAAA-MM-DD' o ya formateado."""
    raw = str(engagement.get("cutoff") or engagement.get("corte") or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return raw


def construir_encargo(engagement: dict) -> dict:
    """Objeto ``ENC`` del panel desde el encargo del Command Center (``reg['engagement']``)."""
    e = engagement or {}
    marco = str(e.get("framework") or e.get("marco") or "NIIF para las PYMES").strip()
    enc = {
        "cliente": str(e.get("client") or e.get("cliente") or ""),
        "ruc": str(e.get("ruc") or ""),
        "actividad": str(e.get("activity") or e.get("actividad") or ""),
        "ejercicio": str(e.get("year") or e.get("ejercicio") or ""),
        "corte": _corte_ddmmyyyy(e),
        "visita": str(e.get("visit") or e.get("visita") or "Preliminar"),
        "preparado": str(e.get("preparer") or e.get("preparado") or ""),
        "revisado": str(e.get("reviewer") or e.get("revisado") or ""),
        "firma": _firma(e),
        "marco": marco,
        "edicion": str(e.get("edition") or e.get("edicion") or ""),
        "pais": str(e.get("country") or e.get("pais") or "Ecuador"),
        "moneda": str(e.get("currency") or e.get("moneda") or "USD"),
    }
    logo = str(e.get("logoCliente") or e.get("clienteLogo") or "").strip()
    if logo:
        enc["clienteLogo"] = logo
    return enc


def marca_panel(engagement: dict) -> dict:
    """Logos de la cabecera (los mismos de ``marca.py`` que usa la planificación)."""
    from backend.app.aud.niif.procesadores import marca
    return {"audit": marca.data_uri("auditconsulting_blanco"),
            "auditOscuro": marca.data_uri("auditconsulting_oscuro"),
            "partner": marca.data_uri("partner_auditing"),
            "auditia": marca.data_uri("audit_ia")}


def render(engagement: dict, prueba_id: int | None = None, base: str = "/aud/ciclo",
           carpeta_cedulas: str | None = None) -> bytes:
    """HTML del panel con el encargo inyectado. ``prueba_id`` enlaza los botones al motor.

    ``carpeta_cedulas``: carpeta con las cédulas YA RECALCULADAS (LibreOffice) que produjo el
    motor para esta prueba. Si viene, el visor del panel muestra cada cédula pestaña por pestaña
    (patrón artefacto, como la planificación); si no, las tarjetas quedan «PENDIENTE DE PROCESAR».
    """
    from backend.app.aud.niif.procesadores.nomina import visor

    enc = construir_encargo(engagement)
    api = {"base": base, "pruebaId": prueba_id}
    with open(_TMPL, encoding="utf-8") as fh:
        tmpl = fh.read()
    datos_visor = None
    if carpeta_cedulas and os.path.isdir(carpeta_cedulas):
        datos_visor = visor.empaquetar(carpeta_cedulas)
    html = (tmpl
            .replace("__NOMINA_ENC__", json.dumps(enc, ensure_ascii=False))
            .replace("__NOMINA_API__", json.dumps(api, ensure_ascii=False))
            .replace("__NOMINA_MARCA__", json.dumps(marca_panel(engagement)))
            .replace("__NOMINA_VISOR__", json.dumps(datos_visor)))
    return html.encode("utf-8")
