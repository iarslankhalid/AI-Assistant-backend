from app.db.models.email_thread import EmailThread
from sqlalchemy.orm import Session
from datetime import datetime

def upsert_email_thread(
    db: Session,
    user_id: int,
    email_id: str,
    subject: str,
    sender: str,
    received_at: datetime,
    conversation_id: str,
    body_preview: str,
    is_read: bool,
    has_attachments: bool
):
    last_email_data = {
        "id": email_id,
        "from": {
            "name": sender or "Unknown",
            "email": sender or "No Email"
        },
        "subject": subject or "(No Subject)",
        "body_preview": body_preview or "",
        "date": received_at.isoformat() if received_at else "",
        "isRead": is_read,
        "hasAttachments": has_attachments,
        "conversationId": conversation_id
    }

    thread = db.query(EmailThread).filter_by(user_id=user_id, conversation_id=conversation_id).first()

    if not thread:
        thread = EmailThread(
            user_id=user_id,
            conversation_id=conversation_id,
            subject=subject,
            last_email_at=received_at,
            last_sender=sender,
            unread_count=0 if is_read else 1,
            last_email_data=last_email_data
        )
        db.add(thread)
    else:
        thread.subject = subject or thread.subject
        thread.last_email_at = received_at
        thread.last_sender = sender
        thread.last_email_data = last_email_data
        if not is_read:
            thread.unread_count += 1

    db.commit()
