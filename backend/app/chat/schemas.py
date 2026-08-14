"""Schemas Pydantic del chat cognitivo."""

import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    project_id: int | None = None
    module_code: str | None = Field(default=None, max_length=8)
    title: str | None = Field(default=None, max_length=200)


class ConversationOut(BaseModel):
    id: int
    organization_id: int
    project_id: int | None
    user_id: int
    module_code: str | None
    title: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class AttachmentIn(BaseModel):
    """Documento adjunto ya extraído (texto plano) que acompaña al mensaje.

    El texto se genera en el endpoint /chat/attachments/extract; aquí solo se
    reenvía para inyectarlo como contexto del turno actual del modelo.
    """

    name: str = Field(min_length=1, max_length=260)
    text: str = Field(min_length=1, max_length=30000)


class AttachmentExtractOut(BaseModel):
    """Resultado de extraer el texto de un archivo subido."""

    name: str
    kind: str
    chars: int
    truncated: bool
    text: str


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    attachments: list[AttachmentIn] = Field(default_factory=list, max_length=6)


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    model: str | None
    tokens_in: int | None
    tokens_out: int | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class MediaImageIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    model: str = Field(default="flux", max_length=16)
    width: int = Field(default=1024, ge=256, le=1536)
    height: int = Field(default=1024, ge=256, le=1536)


class MediaVideoIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    width: int = Field(default=704, ge=256, le=1280)
    height: int = Field(default=480, ge=256, le=1280)
    length: int = Field(default=65, ge=9, le=161)


class ChatTurnResult(BaseModel):
    """Resultado de enviar un mensaje: el mensaje del usuario y la respuesta del assistant."""

    user_message: MessageOut
    assistant_message: MessageOut | None
    provider_error: str | None = None
