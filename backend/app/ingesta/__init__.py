"""Motor de Ingesta y Normalización — capa transversal de AuditBrain.

Esta es la capa orquestadora delgada que coordina los motores deterministas
ya existentes (ingesta de mayores, parsers SRI, OCR, analítica del motor
forense) y emite un **contrato de datos común**: todo dato que después usa
una prueba de auditoría, NIIF o tributaria puede regresar hasta su origen
(archivo · página · fila · celda), lleva su nivel de confianza y su método
de extracción.

Fase 1 (esta entrega): el contrato de datos (`contract`) y el motor de
confianza (`confidence`). Es aditivo y reversible: no toca ningún flujo
existente; nada importa este paquete todavía.

Principio rector (igual que el resto de la plataforma): **determinístico
primero, la IA es el último recurso**. El contrato deja explícito el método
de extracción usado y nunca oculta la incertidumbre.
"""
from __future__ import annotations

from backend.app.ingesta.confidence import (
    NivelConfianza,
    UMBRAL_ALTA,
    UMBRAL_MEDIA,
    UMBRAL_BAJA,
    clasificar_confianza,
    requiere_revision,
)
from backend.app.ingesta.contract import (
    CONTRATO_VERSION,
    CampoExtraido,
    DatasetNormalizado,
    Evidencia,
    MetodoExtraccion,
    ResultadoValidacion,
    Sello,
    TipoDato,
    TipoDocumento,
    huella,
)

__all__ = [
    "CONTRATO_VERSION",
    "NivelConfianza",
    "UMBRAL_ALTA",
    "UMBRAL_MEDIA",
    "UMBRAL_BAJA",
    "clasificar_confianza",
    "requiere_revision",
    "CampoExtraido",
    "DatasetNormalizado",
    "Evidencia",
    "MetodoExtraccion",
    "ResultadoValidacion",
    "Sello",
    "TipoDato",
    "TipoDocumento",
    "huella",
]
