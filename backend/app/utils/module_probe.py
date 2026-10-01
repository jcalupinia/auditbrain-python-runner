"""Sonda de disponibilidad de módulos SIN importarlos.

Varios módulos (OCR con Google Vision, Canva MCP, PBIX, QlikView) ofrecen un
`is_available()` para que el resto del código degrade con elegancia cuando una
librería pesada y opcional no está instalada. El problema de usar `import` como
prueba es que Python **nunca descarga** un módulo una vez importado: cada chequeo
de disponibilidad (p. ej. en `/api/v1/health`) dejaría esa memoria —grpcio,
protobuf, google-api-core…— residente para siempre en el proceso web, aunque
nadie use la funcionalidad.

`importlib.util.find_spec` responde lo mismo (¿está instalada?) consultando el
sistema de imports **sin ejecutar** el módulo. El import real se hace recién en
la función que de verdad usa la librería.
"""

from __future__ import annotations

import importlib.util
import logging

log = logging.getLogger(__name__)


def module_installed(nombre: str) -> bool:
    """Devuelve True si el módulo `nombre` está instalado, sin importarlo.

    Usa `importlib.util.find_spec`, que no ejecuta el módulo ni deja memoria
    residente. Nunca levanta: ante cualquier error (p. ej. un paquete padre que
    falla al resolver su spec) devuelve False, para que el llamador caiga a su
    respaldo en vez de romperse.
    """
    try:
        return importlib.util.find_spec(nombre) is not None
    except (ImportError, ValueError, ModuleNotFoundError) as e:  # pragma: no cover
        log.debug("find_spec(%r) falló (%s); se asume no instalado", nombre, e)
        return False
