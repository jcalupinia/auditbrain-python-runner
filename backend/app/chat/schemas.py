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


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


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


class ChatTurnResult(BaseModel):
    """Resultado de enviar un mensaje: el mensaje del usuario y la respuesta del assistant."""

    user_message: MessageOut
    assistant_message: MessageOut | None
    provider_error: str | None = None
