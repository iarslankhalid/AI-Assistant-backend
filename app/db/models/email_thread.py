from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Boolean
from datetime import datetime, timezone
from app.db.session import Base

class EmailThread(Base):
    __tablename__ = "email_threads"

    conversation_id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    # Thread metadata
    subject = Column(String)
    last_email_id = Column(String, ForeignKey("emails.id"), nullable=True)
    last_email_at = Column(DateTime)
    last_sender = Column(String)
    last_body_preview = Column(Text, nullable=True)  # Optional for quick view

    # Thread stats
    unread_count = Column(Integer, default=0)
    total_count = Column(Integer, default=1)  # 🆕 total emails in thread

    # AI features
    summary = Column(Text, nullable=True)
    topic = Column(String, nullable=True)
    category = Column(String, nullable=True)
    priority_score = Column(Integer, nullable=True)
    extracted_tasks = Column(Text, nullable=True)
    is_processing = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

