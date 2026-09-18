"""Pydantic schemas de la API de AUD.PCE_CXC (pérdidas crediticias esperadas).

``parametros`` viaja como un campo de formulario (JSON libre, ver
``router.py``), no como cuerpo JSON tipado: su forma depende del servicio
(``service.analizar``) y no se fija aquí para no acoplar el endpoint a la
forma interna del cálculo. Lo que sí tiene una forma fija y estable es la
corrida ya guardada, que es lo que expone este módulo.
"""
from __future__ import annotations

from pydantic import BaseModel


class CorridaPCEOut(BaseModel):
    """Corrida guardada: permite reproducir el papel de trabajo sin recargar archivos."""

    corrida_id: int
    entidad: str
    fecha_corte: str | None
    parametros: dict
    resultado: dict
    created_at: str
