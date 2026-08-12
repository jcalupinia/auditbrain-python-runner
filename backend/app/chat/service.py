"""Servicio del chat cognitivo: conversaciones, mensajes y orquestación LLM."""

from __future__ import annotations

import datetime
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import User
from backend.app.chat.models import Conversation, Message
from backend.app.chat.providers import (
    LLMResponse,
    ProviderUnavailable,
    chat_complete,
    stream_chat_complete,
)
from backend.app.chat.schemas import MessageOut
from backend.app.chat.skills_registry import build_system_prompt
from backend.app.context.service import ensure_user_has_organization
from backend.app.db.session import SessionLocal


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _sse(event: str, data: dict) -> str:
    """Serializa un evento SSE (Server-Sent Events)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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


def _compose_with_attachments(
    user_content: str, attachments=None
) -> tuple[str, str]:
    """Devuelve (contenido_guardado, contenido_para_el_modelo).

    - contenido_guardado: lo que se persiste y se muestra en el historial —
      la pregunta del usuario más una nota discreta de los adjuntos (sin volcar
      el documento entero en la conversación).
    - contenido_para_el_modelo: la misma pregunta con el texto de cada documento
      inyectado, para que el modelo lo lea SOLO en este turno.
    """
    atts = list(attachments or [])
    if not atts:
        return user_content, user_content

    def _name(a):
        return getattr(a, "name", None) or (a.get("name") if isinstance(a, dict) else "documento")

    def _text(a):
        return getattr(a, "text", None) or (a.get("text") if isinstance(a, dict) else "")

    names = ", ".join(_name(a) for a in atts)
    stored = f"{user_content}\n\n📎 Adjunto: {names}"

    bloques = [user_content, ""]
    for a in atts:
        bloques.append(f"--- Documento adjunto: {_name(a)} ---")
        bloques.append(_text(a))
        bloques.append("--- fin del documento ---")
        bloques.append("")
    model_content = "\n".join(bloques).strip()
    return stored, model_content


def _system_prompt(module_code: str | None, skill_id: str | None = None) -> str:
    """Construye el system prompt usando el skills registry.

    Si el módulo tiene una skill default mapeada, se aplica automáticamente.
    Si el caller pasa skill_id explícito, ese prevalece sobre el default.
    Si no hay skill ni módulo, se usa solo el prompt base de AuditBrain.
    """
    return build_system_prompt(module_code=module_code, skill_id=skill_id)


def add_user_message_and_respond(
    db: Session,
    conversation: Conversation,
    user_content: str,
    skill_id: str | None = None,
    attachments=None,
) -> tuple[Message, Message | None, str | None]:
    """Persiste el mensaje del usuario, llama al LLM, persiste respuesta.

    Retorna (mensaje_usuario, mensaje_assistant_o_None, error_string_o_None).

    skill_id (opcional) permite forzar una skill específica del registry.
    Si no se pasa, se usa la skill default del módulo de la conversación.
    attachments (opcional) inyecta el texto de documentos adjuntos SOLO en el
    prompt de este turno (el historial guarda el mensaje limpio).
    """
    stored_content, model_content = _compose_with_attachments(user_content, attachments)
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=stored_content,
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
    # El último mensaje de usuario va al modelo con los documentos inyectados.
    if api_messages and api_messages[-1]["role"] == "user":
        api_messages[-1]["content"] = model_content

    try:
        llm: LLMResponse = chat_complete(
            messages=api_messages,
            system=_system_prompt(conversation.module_code, skill_id),
        )
    except ProviderUnavailable as exc:
        # No fingir respuesta: dejar el mensaje del usuario persistido y
        # devolver el error real para que la UI lo muestre.
        conversation.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
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
    conversation.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    # Si la conversación aún tiene el título por defecto, autotitular con
    # los primeros 60 chars del mensaje del usuario.
    if conversation.title == "Nueva conversación":
        conversation.title = (user_content.strip().splitlines() or [""])[0][:60] or "Conversación"
    db.add(conversation)
    db.commit()
    db.refresh(assistant_msg)
    return user_msg, assistant_msg, None


def stream_user_message_and_respond(
    conversation_id: int,
    user_content: str,
    skill_id: str | None = None,
    attachments=None,
):
    """Versión en streaming (SSE) de add_user_message_and_respond.

    Es un GENERADOR que emite eventos SSE. Abre su PROPIA sesión de BD porque
    la sesión del endpoint (Depends get_db) ya está cerrada cuando el
    StreamingResponse comienza a iterar. Persiste el mensaje del usuario al
    inicio y el del assistant al terminar el stream.

    Eventos emitidos: user_message, token (x N), assistant_message, error, done.
    """
    db = SessionLocal()
    try:
        # Primer chunk "primer" (comentario SSE + padding) para forzar a los
        # proxies (Render/nginx/Cloudflare) a ABRIR el stream y dejar de
        # bufferizar: sin bytes iniciales algunos proxies retienen la respuesta
        # hasta llenar su buffer y el usuario no ve nada en vivo.
        yield ": stream-start\n" + (":" + " " * 2048 + "\n") + "\n"

        conv = db.get(Conversation, conversation_id)
        if conv is None:
            yield _sse("error", {"detail": "Conversación no encontrada."})
            yield _sse("done", {})
            return

        stored_content, model_content = _compose_with_attachments(user_content, attachments)
        user_msg = Message(conversation_id=conv.id, role="user", content=stored_content)
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)
        yield _sse("user_message", MessageOut.model_validate(user_msg).model_dump(mode="json"))

        history_rows = list_messages(db, conv)
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in history_rows
            if m.role in ("user", "assistant")
        ]
        # El último mensaje de usuario va al modelo con los documentos inyectados.
        if api_messages and api_messages[-1]["role"] == "user":
            api_messages[-1]["content"] = model_content
        system = _system_prompt(conv.module_code, skill_id)

        acc: list[str] = []
        model_used: str | None = None
        tin: int | None = None
        tout: int | None = None
        error_detail: str | None = None

        try:
            for delta in stream_chat_complete(api_messages, system):
                dtype = delta.get("type")
                if dtype == "reasoning":
                    # Heartbeat de razonamiento: mantiene el stream vivo y le
                    # dice a la UI que muestre "Analizando…" durante los
                    # segundos previos al primer token de respuesta.
                    yield _sse("reasoning", {})
                elif dtype == "token":
                    acc.append(delta["text"])
                    yield _sse("token", {"text": delta["text"]})
                elif dtype == "done":
                    model_used = delta.get("model")
                    tin = delta.get("tokens_in")
                    tout = delta.get("tokens_out")
        except ProviderUnavailable as exc:
            # Failover: si NADA se emitió aún, caer al path no-streaming (que
            # recorre toda la cadena: local→gemini→groq→anthropic→openai).
            if not acc:
                try:
                    llm: LLMResponse = chat_complete(api_messages, system)
                    acc = [llm.content]
                    model_used = llm.model
                    tin, tout = llm.tokens_in, llm.tokens_out
                    yield _sse("token", {"text": llm.content})
                except ProviderUnavailable as exc2:
                    error_detail = str(exc2)
            else:
                # Ya se entregó texto parcial: no hay failover transparente.
                error_detail = str(exc)

        content = "".join(acc)
        if content:
            assistant_msg = Message(
                conversation_id=conv.id,
                role="assistant",
                content=content,
                model=model_used,
                tokens_in=tin,
                tokens_out=tout,
            )
            db.add(assistant_msg)
            conv.updated_at = _now()
            if conv.title == "Nueva conversación":
                conv.title = (user_content.strip().splitlines() or [""])[0][:60] or "Conversación"
            db.add(conv)
            db.commit()
            db.refresh(assistant_msg)
            yield _sse(
                "assistant_message",
                MessageOut.model_validate(assistant_msg).model_dump(mode="json"),
            )

        if error_detail:
            yield _sse("error", {"detail": error_detail})
        yield _sse("done", {})
    except Exception as exc:  # red de seguridad: nunca colgar el stream sin cerrar
        logging.getLogger("auditbrain").exception("Error en stream de chat")
        yield _sse("error", {"detail": f"Error interno: {exc}"})
        yield _sse("done", {})
    finally:
        db.close()
