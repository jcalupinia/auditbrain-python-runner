"""Catálogo de eventos. Un evento por slug; configurable sin rediseño."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventInfo:
    slug: str
    titulo: str
    subtitulo: str
    fecha_texto: str
    hora_texto: str
    duracion_texto: str
    modalidad: str
    zoom_url: str
    beneficios: list[str] = field(default_factory=list)
    activo: bool = True


def _build_events() -> dict[str, EventInfo]:
    charla = EventInfo(
        slug="charla-anexos-2026-06",
        titulo="Elaboración de Anexos Tributarios con Herramienta de Automatización",
        subtitulo="Charla gratuita en Zoom",
        fecha_texto="Jueves 18 de junio",
        hora_texto="19h00 (Ecuador)",
        duracion_texto="2 horas",
        modalidad="Zoom",
        zoom_url=os.getenv("CHARLA_ZOOM_URL", ""),
        beneficios=[
            "Automatiza tus anexos tributarios",
            "Descarga inteligente de información del SRI",
            "Validaciones automáticas y control de inconsistencias",
            "Reduce tiempos y minimiza errores",
            "Casos prácticos para empresas y profesionales",
        ],
        activo=True,
    )
    return {charla.slug: charla}


EVENTS: dict[str, EventInfo] = _build_events()


def get_event(slug: str) -> EventInfo | None:
    return EVENTS.get(slug)
