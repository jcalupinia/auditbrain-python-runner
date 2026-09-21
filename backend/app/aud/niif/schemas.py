"""Schemas Pydantic de la ficha de diseño NIIF.

La validación de aquí es la del **límite de confianza**: el frontend ya valida
con ``validarFicha`` (frontend/src/aud/niif/fichaLogic.js), pero la API no
puede confiar en eso. Se exige lo mínimo que hace a una ficha utilizable:
identificación completa, al menos un ítem con formato y al menos una salida.
"""

import datetime

from pydantic import BaseModel, Field, field_validator

ESTADO_EN_DISENO = "en_diseño"
ESTADO_PROBADA = "probada"
ESTADO_ENVIADA = "enviada"

ESTADOS_VALIDOS = (ESTADO_EN_DISENO, ESTADO_PROBADA, ESTADO_ENVIADA)


class ItemIn(BaseModel):
    """Un documento pedido al cliente (bloque 2 de la estructura)."""

    que_se_pide: str = Field(min_length=1, max_length=500)
    formatos: list[str] = Field(min_length=1)
    obligatorio: bool = True
    componentes: int = Field(default=1, ge=1)
    grupo_alternativas: str = ""


class SalidaIn(BaseModel):
    """Una cédula que produce la herramienta (bloque 4)."""

    nombre: str = Field(min_length=1, max_length=300)
    formatos: list[str] = Field(min_length=1)


class FichaIn(BaseModel):
    """Cuerpo de creación/actualización. Ignora campos extra del cliente
    (``estado``, ``id``, ``actualizado``): el estado lo gobierna el backend."""

    nombre: str = Field(min_length=1, max_length=200)
    rubro: str = Field(min_length=1, max_length=64)
    norma: str = Field(min_length=1, max_length=160)
    parrafo: str = Field(min_length=1, max_length=160)
    items: list[ItemIn] = Field(min_length=1)
    salidas: list[SalidaIn] = Field(min_length=1)

    @field_validator("nombre", "rubro", "norma", "parrafo")
    @classmethod
    def _no_solo_espacios(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("no puede quedar en blanco")
        return v


class EstadoIn(BaseModel):
    estado: str


class FichaOut(BaseModel):
    id: int
    nombre: str
    rubro: str
    norma: str
    parrafo: str
    items: list
    salidas: list
    estado: str
    autor_user_id: int | None
    autor_email: str | None
    probada_por_user_id: int | None
    probada_por_email: str | None
    probada_en: datetime.datetime | None
    enviada_por_user_id: int | None
    enviada_por_email: str | None
    enviada_en: datetime.datetime | None
    devuelta_por_email: str | None = None
    devuelta_en: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class CoberturaIn(BaseModel):
    """Documentos recibidos, para medir la cobertura del requerimiento.

    La forma de cada documento es la del sitio: ``kind`` siempre ``"source"``,
    ``itemId`` el ítem al que se vinculó, ``component`` el componente cuando el
    ítem los tiene, y ``state`` para que un documento ``"rechazado"`` no tape
    el hueco.
    """

    documentos: list[dict] = Field(default_factory=list)


class MotorIn(BaseModel):
    """Definición de la prueba y datos con los que correrla.

    La definición no sale de la ficha: la escribe Claude a partir del código
    que genera el botón del diseñador. Correrla aquí es lo que habilita marcar
    la ficha como probada con algo más que una impresión.
    """

    definicion: dict
    filas: list[dict]
    parametros: dict = Field(default_factory=dict)
    flujos: list[dict] = Field(default_factory=list)
