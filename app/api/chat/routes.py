from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.api.chat import schemas, services
from app.db.session import get_db
from app.core.security import get_current_user

router = APIRouter()

# ---------------------------------------------------
# 🚀 Unified Message Endpoint
# ---------------------------------------------------

@router.post("/message", response_model=schemas.ChatUnifiedResponse)
def handle_message(
    payload: schemas.ChatMessageUnifiedRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Get or create session
    if payload.session_id:
        session = services.get_chat_session(db, payload.session_id)
        if not session or session.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        session_data = schemas.ChatSessionCreate(
            model=payload.model,
            system_prompt=payload.system_prompt,
            category=payload.category,
            first_message=payload.content
        )
        session = services.create_chat_session(db, user_id=current_user.id, session_data=session_data)

    # Send the message
    message_data = schemas.ChatMessageCreate(
        chat_session_id=session.id,
        model=payload.model,
        content=payload.content
    )
    ai_reply = services.send_message_and_get_ai_response(db, user_id=current_user.id, message_data=message_data)

    # Auto-title only if new session
    if not payload.session_id:
        suggested_title = services.generate_session_title_from_conversation(payload.content, ai_reply.content)
        session.title = suggested_title
        db.commit()
        db.refresh(session)

    return schemas.ChatUnifiedResponse(session=session, ai_reply=ai_reply)


# ---------------------------------------------------
# 🔁 Other Chat Session Endpoints
# ---------------------------------------------------

@router.get("/sessions", response_model=List[schemas.ChatSessionLiteResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return services.list_user_chat_sessions(db, user_id=current_user.id)


@router.get("/sessions/{session_id}", response_model=schemas.ChatSessionResponse)
def retrieve_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    session = services.get_chat_session(db, session_id=session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.delete("/{session_id}", response_model=schemas.ChatSessionDeleteResponse)
def delete_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    session = services.get_chat_session(db, session_id=session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")

    services.delete_chat_session(db, session)
    return {"detail": "Chat session deleted successfully"}


@router.patch("/{session_id}/rename", response_model=schemas.ChatRenameResponse)
def rename_session(
    session_id: UUID,
    rename_data: schemas.ChatRenameRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    session = services.get_chat_session(db, session_id=session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")

    updated_session = services.rename_chat_session(db, session, new_title=rename_data.title)
    return {
        "detail": "Chat session renamed successfully",
        "new_title": updated_session.title
    }
