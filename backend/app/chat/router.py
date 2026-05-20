"""Endpoints del chat cognitivo: /api/v1/chat/*."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.chat import service
from backend.app.chat.schemas import (
    ChatTurnResult,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    MessageIn,
    MessageOut,
)
from backend.app.context.service import (
    ensure_user_has_organization,
    user_can_access_project,
)
from backend.app.context.models import Project
from backend.app.db.session import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_user_conversations(db, current)


@router.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = ensure_user_has_organization(db, current)
    if payload.project_id is not None:
        proj = db.get(Project, payload.project_id)
        if not proj or not user_can_access_project(db, current, proj):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Proyecto no accesible para este usuario.",
            )
    return service.create_conversation(
        db,
        user=current,
        project_id=payload.project_id,
        module_code=payload.module_code,
        title=payload.title,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation_detail(
    conversation_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = service.get_conversation(db, conversation_id, current)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada.")
    msgs = service.list_messages(db, conv)
    return ConversationDetail(
        **{c.name: getattr(conv, c.name) for c in conv.__table__.columns},
        messages=[MessageOut.model_validate(m) for m in msgs],
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatTurnResult,
    status_code=status.HTTP_200_OK,
)
def send_message(
    conversation_id: int,
    payload: MessageIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = service.get_conversation(db, conversation_id, current)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada.")
    user_msg, assistant_msg, error = service.add_user_message_and_respond(
        db, conv, payload.content
    )
    return ChatTurnResult(
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(assistant_msg) if assistant_msg else None,
        provider_error=error,
    )
