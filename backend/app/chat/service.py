"""Servicio del chat cognitivo: conversaciones, mensajes y orquestación LLM."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import User
from backend.app.chat.models import Conversation, Message
from backend.app.chat.providers import (
    LLMResponse,
    ProviderUnavailable,
    chat_complete,
)
from backend.app.context.service import ensure_user_has_organization


def list_user_conversations(db: Session, user: User) -> list[Conversation]:
    user = ensure_user_has_organization(db, user)
    return list(
        db.execute(
            select(Conversation)
            .where(
                Conversation.organization_id == user.organization_id,
                Conversation.user_id == user.id,
            )
            .order_by(Conversation.updated_at.desc())
        ).scalars()
    )


def get_conversation(
    db: Session, conversation_id: int, user: User
) -> Conversation | None:
    user = ensure_user_has_organization(db, user)
    return db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == user.organization_id,
            Conversation.user_id == user.id,
        )
    ).scalar_one_or_none()


def list_messages(db: Session, conversation: Conversation) -> list[Message]:
    return list(
        db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        ).scalars()
    )


def create_conversation(
    db: Session,
    user: User,
    project_id: int | None = None,
    module_code: str | None = None,
    title: str | None = None,
) -> Conversation:
    user = ensure_user_has_organization(db, user)
    conv = Conversation(
        organization_id=user.organization_id,
        user_id=user.id,
        project_id=project_id,
        module_code=(module_code or "").upper() or None,
        title=(title or "Nueva conversación")[:200],
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _system_prompt(module_code: str | None) -> str:
    base = (
        "Eres AuditBrain IA, un copiloto cognitivo para auditoría, consultoría "
        "y gobierno corporativo. Eres preciso, conciso y profesional. Si una "
        "pregunta requiere datos del cliente que no tienes, lo dices explícitamente."
    )
    if not module_code:
        return base
    from backend.app.modules.registry import get_module

    m = get_module(module_code)
    if not m:
        return f"{base}\n\nMódulo activo: {module_code}."
    return (
        f"{base}\n\n"
        f"Módulo activo: {m.code} · {m.label}.\n"
        f"{m.system_prompt}"
    )


def add_user_message_and_respond(
    db: Session,
    conversation: Conversation,
    user_content: str,
) -> tuple[Message, Message | None, str | None]:
    """Persiste el mensaje del usuario, llama al LLM, persiste respuesta.

    Retorna (mensaje_usuario, mensaje_assistant_o_None, error_string_o_None).
    """
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_content,
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    history_rows = list_messages(db, conversation)
    api_messages = [
        {"role": m.role, "content": m.content}
        for m in history_rows
        if m.role in ("user", "assistant")
    ]

    try:
        llm: LLMResponse = chat_complete(
            messages=api_messages,
            system=_system_prompt(conversation.module_code),
        )
    except ProviderUnavailable as exc:
        # No fingir respuesta: dejar el mensaje del usuario persistido y
        # devolver el error real para que la UI lo muestre.
        conversation.updated_at = datetime.datetime.utcnow()
        db.add(conversation)
        db.commit()
        return user_msg, None, str(exc)

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=llm.content,
        model=llm.model,
        tokens_in=llm.tokens_in,
        tokens_out=llm.tokens_out,
    )
    db.add(assistant_msg)
    conversation.updated_at = datetime.datetime.utcnow()
    # Si la conversación aún tiene el título por defecto, autotitular con
    # los primeros 60 chars del mensaje del usuario.
    if conversation.title == "Nueva conversación":
        conversation.title = (user_content.strip().splitlines() or [""])[0][:60] or "Conversación"
    db.add(conversation)
    db.commit()
    db.refresh(assistant_msg)
    return user_msg, assistant_msg, None
