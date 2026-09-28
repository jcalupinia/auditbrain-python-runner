"""Asistente de la consola de comunicación por prueba (NIIF Piloto).

Da una respuesta conversacional, anclada al contexto de la prueba (nombre, marco,
resultado principal y problemas detectados), usando la cadena de proveedores LLM
(el servidor de IA LOCAL es el primario: privado y sin costo; ver
``backend/app/chat/providers.py``). La respuesta es SIEMPRE un borrador técnico
sujeto a la validación del auditor responsable: lleva el disclaimer obligatorio y
no inventa cifras (usa solo las que ya calculó el procesador determinista).

Degradación elegante: si no hay proveedor configurado o falla, ``disponible()``
devuelve False y ``responder`` levanta ``providers.ProviderUnavailable``; el router
igual guarda el comentario del usuario y avisa que el asistente no contestó.
"""
from __future__ import annotations

from backend.app.chat import providers

DISCLAIMER = ("Análisis generado por IA. La interpretación debe ser validada por el "
              "auditor responsable antes de cualquier decisión.")

_SISTEMA = (
    "Eres el asistente NIIF de AuditConsulting Auditores Cía. Ltda. en la plataforma "
    "AUDIT-IA, dentro de la consola de una prueba de auditoría. Respondes SIEMPRE en "
    "español, de forma breve y técnica. Reglas inviolables: (1) cero invención: no "
    "inventes normas, cifras ni datos; usa solo el contexto de la prueba que se te da; "
    "(2) toda respuesta es un borrador para el auditor responsable, no una conclusión; "
    "(3) si falta información, pídela con una sola pregunta clara. No repitas el "
    "disclaimer: la plataforma lo agrega sola."
)


def disponible() -> bool:
    """Hay al menos un proveedor LLM configurado (local u otro)."""
    return providers.available_provider() is not None


def _contexto(prueba: dict, registro: dict) -> str:
    run = (registro or {}).get("run") or {}
    prim = run.get("primary")
    marco = (registro.get("engagement") or {}).get("framework") or ", ".join(prueba.get("frameworks", []))
    problemas = run.get("exceptions") or []
    lineas = [
        f"Prueba: {prueba.get('name', '(sin nombre)')}.",
        f"Marco contable: {marco or 'no especificado'}.",
    ]
    if prim:
        etq = (run.get("labels") or {}).get(prim, prim)
        val = (run.get("totals") or {}).get(prim)
        lineas.append(f"Resultado principal — {etq}: {val}.")
    lineas.append(f"Problemas detectados por la prueba: {len(problemas)}.")
    for pb in problemas[:8]:
        detalle = pb.get("detail") or pb.get("message") or pb.get("codigo") or pb
        lineas.append(f"  · {detalle}")
    return "\n".join(str(x) for x in lineas)


def responder(prueba: dict, registro: dict, historial: list[dict], pregunta: str) -> dict:
    """Respuesta del asistente a la última pregunta, con el contexto de la prueba
    y el historial de la consola. Levanta ``providers.ProviderUnavailable`` si no
    hay proveedor. Devuelve ``{texto, modelo, disclaimer}``."""
    system = _SISTEMA + "\n\nContexto de la prueba (única fuente de cifras):\n" + _contexto(prueba, registro)
    mensajes: list[dict[str, str]] = []
    for e in historial:
        if e.get("tipo") != "comentario" or not e.get("texto"):
            continue
        rol = "assistant" if e.get("es_asistente") else "user"
        mensajes.append({"role": rol, "content": e["texto"]})
    mensajes.append({"role": "user", "content": (pregunta or "").strip()})
    r = providers.chat_complete(mensajes, system=system)
    return {"texto": r.content, "modelo": r.model, "disclaimer": DISCLAIMER}
