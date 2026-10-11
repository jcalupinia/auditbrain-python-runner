"""Flujo en dos tiempos de la Capa de Mapeo Universal (Fase A3).

Etapa 1  ``preparar_mapeo``  → perfila la tabla y PROPONE el mapeo (antes del
          auditor). No normaliza nada.
[Confirmación humana — M07/M17: el auditor acepta o corrige el mapeo.]
Etapa 2  ``aplicar_mapeo`` (en ``aplicar.py``) → normaliza con el mapeo confirmado.

También expone el **hook opt-in** ``ingerir_o_pendiente``: el camino feliz de los
parsers rígidos queda intacto; solo cuando un parser no reconoce la tabla, el
documento se marca «pendiente de mapeo» (``review_required``) SIN auto-mapear ni
avanzar. El endpoint/estado de confirmación se implementa en la Fase B.
"""
from __future__ import annotations

from typing import Callable, Optional

from backend.app.ingesta.confidence import NivelConfianza, requiere_revision
from backend.app.ingesta.confidence_live import ItemRevision
from backend.app.ingesta.contract import DatasetNormalizado
from backend.app.ingesta.mapeo.esquemas import resolver_esquema
from backend.app.ingesta.mapeo.perfilador import PerfilTabla, perfilar
from backend.app.ingesta.mapeo.proponer import MapeoPropuesto, proponer_mapeo


def preparar_mapeo(
    contenido: bytes, filename: str, tipo_documento
) -> tuple[PerfilTabla, MapeoPropuesto]:
    """Etapa 1: perfila y propone (antes de la confirmación del auditor)."""
    esquema = resolver_esquema(tipo_documento)
    perfil = perfilar(contenido, filename)
    propuesto = proponer_mapeo(perfil, esquema)
    return perfil, propuesto


def cola_revision_mapeo(mapeo: MapeoPropuesto) -> list[ItemRevision]:
    """Ítems de revisión del mapeo propuesto (reutiliza ``ItemRevision``).

    Incluye cada propuesta dudosa (LOW/REVIEW) y cada campo obligatorio sin
    columna. Las propuestas HIGH/MEDIUM no entran: el auditor igual confirma
    todo, pero la cola resalta lo que exige su atención.
    """
    items: list[ItemRevision] = []
    for p in mapeo.propuestas:
        if requiere_revision(p.confianza):
            items.append(ItemRevision(
                dataset_id="(mapeo propuesto)",
                document_type=mapeo.tipo_documento,
                field=p.campo_canonico,
                confidence=p.confianza,
                extraction_method="mapeo",
                motivo=f"columna «{p.columna_nombre_crudo}»: {p.motivo}",
            ))
    for nombre in mapeo.campos_sin_cubrir:
        items.append(ItemRevision(
            dataset_id="(mapeo propuesto)",
            document_type=mapeo.tipo_documento,
            field=nombre,
            confidence=NivelConfianza.REVIEW_REQUIRED,
            extraction_method="mapeo",
            motivo="campo obligatorio sin columna en el archivo",
        ))
    return items


# Mensaje con el que se marca un documento que necesita mapeo manual.
PENDIENTE_DE_MAPEO = (
    "pendiente de mapeo (Fase A3): tabla sin parser rígido; requiere que el "
    "auditor confirme el mapeo de columnas antes de normalizar"
)

IngerirFn = Callable[..., DatasetNormalizado]


def ingerir_o_pendiente(
    filename: str,
    contenido: bytes,
    *,
    tipo_declarado: Optional[str] = None,
    ingerir_fn: Optional[IngerirFn] = None,
    **kwargs,
) -> DatasetNormalizado:
    """Hook: intenta el parser rígido; si no reconoce la tabla, marca el
    documento «pendiente de mapeo» (no auto-mapea, no avanza).

    El camino feliz de los parsers queda **idéntico**: si la ingesta devolvió
    datos, se devuelve tal cual. Solo el caso vacío se reencauza. Los parámetros
    extra (``ocr``, ``consolidar``…) se reenvían a la ingesta sin alterarlos.
    """
    if ingerir_fn is None:
        from backend.app.ingesta.orchestrator import ingerir as ingerir_fn  # import perezoso
    ds = ingerir_fn(filename, contenido, tipo_declarado=tipo_declarado, **kwargs)
    if ds.campos or ds.rows:
        return ds  # camino feliz intacto
    if PENDIENTE_DE_MAPEO not in ds.warnings:
        ds.warnings.append(PENDIENTE_DE_MAPEO)
    ds.review_required = True
    return ds
