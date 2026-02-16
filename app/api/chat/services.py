# app/api/chat/services.py

from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

import openai

from app.db.models.chat.chat_session import ChatSession
from app.db.models.chat.chat_message import ChatMessage
from app.api.chat import schemas
from app.config import settings

# Initialize OpenAI API key
openai.api_key = settings.OPENAI_API_KEY


# ---------------------------------------------------
# 🛠️ Chat Session Management
# ---------------------------------------------------

def create_chat_session(db: Session, user_id: int, session_data: schemas.ChatSessionCreate) -> ChatSession:
    """Create a new chat session."""
    chat_session = ChatSession(
        user_id=user_id,
        model=session_data.model,
        system_prompt=session_data.system_prompt,
        category=session_data.category
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session


def get_chat_session(db: Session, session_id: UUID) -> ChatSession:
    """Fetch a chat session by ID."""
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def list_user_chat_sessions(db: Session, user_id: int) -> list[ChatSession]:
    """List all chat sessions for a user."""
    return db.query(ChatSession)\
             .filter(ChatSession.user_id == user_id)\
             .order_by(ChatSession.updated_at.desc())\
             .all()


def delete_chat_session(db: Session, chat_session: ChatSession) -> None:
    """Delete a chat session."""
    db.delete(chat_session)
    db.commit()


def rename_chat_session(db: Session, chat_session: ChatSession, new_title: str) -> ChatSession:
    """Rename a chat session."""
    chat_session.title = new_title
    chat_session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(chat_session)
    return chat_session


# ---------------------------------------------------
# 🛠️ Message Handling
# ---------------------------------------------------

def add_message_to_session(db: Session, message_data: schemas.ChatMessageCreate) -> ChatMessage:
    """Add a new message to a chat session."""
    chat_message = ChatMessage(
        chat_session_id=message_data.chat_session_id,
        role=message_data.role,
        content=message_data.content
    )
    db.add(chat_message)

    # Update session's updated_at
    session = db.query(ChatSession).filter(ChatSession.id == message_data.chat_session_id).first()
    if session:
        session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(chat_message)
    return chat_message


# ---------------------------------------------------
# 🤖 OpenAI AI Integration
# ---------------------------------------------------

def send_message_and_get_ai_response(db: Session, user_id: int, message_data: schemas.ChatMessageCreate) -> ChatMessage:
    """Send a user message, get AI response, and save both messages."""

    # Step 1: Save user's message first
    user_message = ChatMessage(
        chat_session_id=message_data.chat_session_id,
        role="user",
        content=message_data.content
    )
    db.add(user_message)

    # Step 2: Fetch session details
    session = db.query(ChatSession).filter(ChatSession.id == message_data.chat_session_id).first()
    if not session:
        db.rollback()
        raise Exception("Chat session not found.")

    # Step 3: Build messages for OpenAI
    openai_messages = []

    if session.system_prompt:
        openai_messages.append({
            "role": "system",
            "content": session.system_prompt
        })

    previous_messages = db.query(ChatMessage)\
                           .filter(ChatMessage.chat_session_id == message_data.chat_session_id)\
                           .order_by(ChatMessage.created_at.asc())\
                           .all()

    for msg in previous_messages:
        openai_messages.append({
            "role": msg.role.lower(),  # Always lowercase: user/assistant
            "content": msg.content
        })

    # Add current user message at the end
    openai_messages.append({
        "role": "user",
        "content": message_data.content
    })

    # Step 4: Call OpenAI API
    model_to_use = message_data.model if message_data.model else session.model
    print("INFO: model to use: ", model_to_use)
    
    # Determine token parameter based on model
    token_param = "max_completion_tokens" if model_to_use.startswith("o") or "gpt-5" in model_to_use else "max_tokens"
    
    completion_args = {
        "model": model_to_use,
        "messages": openai_messages,
        "temperature": 0.5,
        token_param: 500,
    }

    try:
        response = openai.chat.completions.create(**completion_args)
        assistant_content = response.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] OpenAI API call failed: {e}")
        assistant_content = "I'm sorry, I couldn't generate a response right now. Please try again."

    # Step 5: Save AI assistant message
    ai_message = ChatMessage(
        chat_session_id=message_data.chat_session_id,
        role="assistant",
        content=assistant_content
    )
    db.add(ai_message)

    # Step 6: Update session's updated_at
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ai_message)

    return ai_message



def generate_session_title_from_conversation(user_msg: str, ai_msg: str) -> str:
    prompt = [
        {"role": "system", "content": "Create a short and relevant title for the following chat."},
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": ai_msg}
    ]
    try:
        result = openai.chat.completions.create(
            model="gpt-4",
            messages=prompt,
            max_tokens=5,
            temperature=0.4
        )
        return result.choices[0].message.content.strip().replace('"', '')
    except Exception as e:
        print("[ERROR] Failed to generate session title:", e)
        return "New Chat"
