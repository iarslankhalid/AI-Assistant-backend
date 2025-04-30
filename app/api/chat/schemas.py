from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# -----------------------------
# 🧾 Message Schemas
# -----------------------------

class ChatMessageCreate(BaseModel):
    chat_session_id: UUID
    model: Optional[str] = None
    content: str

class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------
# 📁 Session Schemas
# -----------------------------

class ChatSessionCreate(BaseModel):
    model: str = "gpt-4-turbo"
    system_prompt: Optional[str] = "You are a helpful AI assistant that responds professionally."
    category: Optional[str] = "general"
    first_message: str

class ChatSessionResponse(BaseModel):
    id: UUID
    model: str
    system_prompt: Optional[str]
    title: Optional[str]
    category: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []

    model_config = {"from_attributes": True}

class ChatSessionLiteResponse(BaseModel):
    id: UUID
    model: str
    system_prompt: Optional[str]
    title: Optional[str]
    category: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------
# ✏️ Rename / Delete
# -----------------------------

class ChatRenameRequest(BaseModel):
    title: str

class ChatRenameResponse(BaseModel):
    detail: str
    new_title: str

class ChatSessionDeleteResponse(BaseModel):
    detail: str


# -----------------------------
# 🚀 Unified Message Endpoint
# -----------------------------

class ChatMessageUnifiedRequest(BaseModel):
    session_id: Optional[UUID] = None
    model: Optional[str] = "gpt-4"
    system_prompt: Optional[str] = "You are a helpful AI assistant that responds professionally."
    category: Optional[str] = "general"
    content: str

class ChatUnifiedResponse(BaseModel):
    session: ChatSessionLiteResponse
    ai_reply: ChatMessageResponse
