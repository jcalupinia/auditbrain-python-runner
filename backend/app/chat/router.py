"""Endpoints del chat cognitivo: /api/v1/chat/*."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.chat import attachments as attachments_mod
from backend.app.chat import media as media_mod
from backend.app.chat import service
from backend.app.chat.schemas import (
    AttachmentExtractOut,
    ChatTurnResult,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    MediaImageIn,
    MediaVideoIn,
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
        db, conv, payload.content, attachments=payload.attachments
    )
    return ChatTurnResult(
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(assistant_msg) if assistant_msg else None,
        provider_error=error,
    )


@router.post("/conversations/{conversation_id}/messages/stream")
def send_message_stream(
    conversation_id: int,
    payload: MessageIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Igual que send_message pero transmite la respuesta token por token (SSE).

    Valida el acceso con la sesión del request; el generador abre su propia
    sesión de BD (la del Depends se cierra cuando esta función retorna, antes
    de que StreamingResponse empiece a iterar).
    """
    conv = service.get_conversation(db, conversation_id, current)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada.")
    generator = service.stream_user_message_and_respond(
        conv.id, payload.content, attachments=payload.attachments
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Anti-buffering: sin esto, el proxy de Render/nginx acumula el body
            # y el usuario recibe todo de golpe en vez de token por token.
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/attachments/extract", response_model=AttachmentExtractOut)
async def extract_attachment(
    file: UploadFile = File(...),
    _current: User = Depends(get_current_user),
):
    """Extrae el texto de un documento subido para adjuntarlo al chat.

    No persiste el archivo: devuelve solo el texto extraído, que el frontend
    reenvía junto al siguiente mensaje. Requiere sesión válida (JWT).
    """
    data = await file.read()
    try:
        result = attachments_mod.extract(file.filename or "documento", data)
    except attachments_mod.AttachmentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return AttachmentExtractOut(**result)


# --- Generación de imágenes/video (proxy al puente ComfyUI local) -----------
# El backend guarda la URL del túnel y la clave; el frontend solo llama aquí con
# su sesión JWT. Así funciona SIN Tailscale en el navegador.
@router.get("/media/status")
def media_status(_current: User = Depends(get_current_user)):
    return {"enabled": media_mod.enabled()}


@router.post("/media/image")
def media_image(payload: MediaImageIn, _current: User = Depends(get_current_user)):
    try:
        return media_mod.generate_image(payload.prompt, payload.model, payload.width, payload.height)
    except media_mod.MediaUnavailable as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/media/video")
def media_video(payload: MediaVideoIn, _current: User = Depends(get_current_user)):
    try:
        return media_mod.generate_video(payload.prompt, payload.width, payload.height, payload.length)
    except media_mod.MediaUnavailable as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))
