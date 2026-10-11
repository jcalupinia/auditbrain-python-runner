"""Capa de Mapeo Universal (Fase A3) — field mapping determinista.

Acepta mayores, asientos, balances y bases de datos venga como venga el
formato del cliente, PROPONE el mapeo de columnas sin IA y deja que el auditor
lo confirme antes de normalizar (M07: la máquina propone, el auditor dispone).
Aditivo: reutiliza el contrato, el normalizador y el motor de confianza
existentes; no toca ningún parser ni prueba ya probada.
"""
from __future__ import annotations

from backend.app.ingesta.mapeo.esquemas import (
    CATALOGO_ESQUEMAS,
    CampoCanonico,
    EsquemaCanonico,
    resolver_esquema,
)
from backend.app.ingesta.mapeo.perfilador import (
    PerfilColumna,
    PerfilTabla,
    perfilar,
)
from backend.app.ingesta.mapeo.proponer import (
    MapeoPropuesto,
    PropuestaMapeo,
    proponer_mapeo,
)
from backend.app.ingesta.mapeo.aplicar import aplicar_mapeo
from backend.app.ingesta.mapeo.flujo import (
    PENDIENTE_DE_MAPEO,
    cola_revision_mapeo,
    ingerir_o_pendiente,
    preparar_mapeo,
)

__all__ = [
    "CATALOGO_ESQUEMAS",
    "CampoCanonico",
    "EsquemaCanonico",
    "resolver_esquema",
    "PerfilColumna",
    "PerfilTabla",
    "perfilar",
    "MapeoPropuesto",
    "PropuestaMapeo",
    "proponer_mapeo",
    "aplicar_mapeo",
    "preparar_mapeo",
    "cola_revision_mapeo",
    "ingerir_o_pendiente",
    "PENDIENTE_DE_MAPEO",
]
