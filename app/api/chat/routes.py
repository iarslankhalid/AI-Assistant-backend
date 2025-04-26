# app/api/chat/routes.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.api.chat import schemas, services
from app.db.session import get_db
from app.core.security import get_current_user

router = APIRouter()

# ---------------------------------------------------
# 🛠️ Chat Session Management
# ---------------------------------------------------

@router.post("/start", response_model=schemas.ChatSessionResponse)
def start_chat(
    session_data: schemas.ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Start a new chat session."""
    return services.create_chat_session(db, user_id=current_user.id, session_data=session_data)


@router.get("/sessions", response_model=List[schemas.ChatSessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all chat sessions for the current user."""
    return services.list_user_chat_sessions(db, user_id=current_user.id)


@router.get("/{session_id}", response_model=schemas.ChatSessionResponse)
def retrieve_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Retrieve a specific chat session."""
    chat_session = services.get_chat_session(db, session_id=session_id)
    if not chat_session or chat_session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat_session


@router.delete("/{session_id}", response_model=schemas.ChatSessionDeleteResponse)
def delete_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a chat session."""
    chat_session = services.get_chat_session(db, session_id=session_id)
    if not chat_session or chat_session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")

    services.delete_chat_session(db, chat_session)
    return {"detail": "Chat session deleted successfully"}


@router.patch("/{session_id}/rename", response_model=schemas.ChatRenameResponse)
def rename_session(
    session_id: UUID,
    rename_data: schemas.ChatRenameRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Rename a chat session."""
    chat_session = services.get_chat_session(db, session_id=session_id)
    if not chat_session or chat_session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")

    updated_session = services.rename_chat_session(db, chat_session, new_title=rename_data.title)
    return {
        "detail": "Chat session renamed successfully",
        "new_title": updated_session.title
    }


# ---------------------------------------------------
# 🛠️ Message Handling
# ---------------------------------------------------

@router.post("/send", response_model=schemas.ChatMessageResponse)
def send_message(
    message_data: schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Send a message to the chat and get AI response."""
    return services.send_message_and_get_ai_response(db, user_id=current_user.id, message_data=message_data)
