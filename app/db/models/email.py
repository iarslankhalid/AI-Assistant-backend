from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON, ARRAY, Index
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.session import Base

class Email(Base):
    __tablename__ = "emails"

    id = Column(String, primary_key=True)  # Microsoft Graph email ID
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    subject = Column(String)
    sender = Column(String, nullable=False)
    sender_name = Column(String)  # NEW: display name of sender
    recipients = Column(ARRAY(String))
    cc = Column(ARRAY(String))

    conversation_id = Column(String, index=True)
    thread_subject = Column(String)

    received_at = Column(DateTime)
    sent_at = Column(DateTime)  # NEW
    synced_at = Column(DateTime, default=datetime.utcnow)

    body_preview = Column(Text)
    body_plain = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)

    web_link = Column(String, nullable=True)  # NEW: open in Outlook
    message_id = Column(String, nullable=True)  # Optional, internetMessageId
    importance = Column(String, nullable=True)

    is_read = Column(Boolean, default=False)
    has_attachments = Column(Boolean, default=False)
    is_fully_synced = Column(Boolean, default=True)

    # AI fields
    summary = Column(Text, nullable=True)
    quick_replies = Column(ARRAY(String), nullable=True)
    ai_draft = Column(Text, nullable=True)
    priority_score = Column(Integer, nullable=True)
    categories = Column(String, nullable=True)
    topic = Column(String, nullable=True)
    extracted_tasks = Column(JSON, nullable=True)

    fulltext_vector = Column(TSVECTOR)

    __table_args__ = (
        Index('ix_emails_fulltext_vector', 'fulltext_vector', postgresql_using='gin'),
    )
