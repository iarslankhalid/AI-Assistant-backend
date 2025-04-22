from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class EmailBase(BaseModel):
    id: str
    subject: Optional[str]
    sender: Optional[str]
    recipients: Optional[List[str]]
    cc: Optional[List[str]]
    body_preview: Optional[str]
    conversation_id: Optional[str]
    received_at: Optional[datetime]
    category: Optional[str]
    topic: Optional[str]
    summary: Optional[str]
    ai_draft: Optional[str]

    model_config = {
        "from_attributes": True
    }

class EmailCreate(EmailBase):
    body_plain: Optional[str]
    body_html: Optional[str]


class EmailReplyRequest(BaseModel):
    reply_body: str


class AttachmentSchema(BaseModel):
    name: str
    content_type: str
    content_bytes: str  # base64 string

class EmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    attachments: Optional[List[AttachmentSchema]] = []