# app/api/chat/schemas.py
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

class ChatMessageCreate(BaseModel):
    chat_session_id: UUID
    role: str  # 'user' or 'assistant'
    content: str

class ChatSessionCreate(BaseModel):
    model: str
    system_prompt: Optional[str] = None
    title: Optional[str] = None    # <<-- NEW
    category: Optional[str] = None # <<-- NEW


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class ChatSessionResponse(BaseModel):
    id: UUID
    model: str
    system_prompt: Optional[str]
    title: Optional[str]
    category: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []

    model_config = {
        "from_attributes": True
    }


class ChatRenameRequest(BaseModel):
    title: str

class ChatRenameResponse(BaseModel):
    detail: str
    new_title: str

class ChatSessionDeleteResponse(BaseModel):
    detail: str
