from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from cachetools import TTLCache
import base64

from app.core.security import get_current_user
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.outlook_credentials import OutlookCredentials

from app.api.email.services import (
    fetch_user_emails,
    fetch_email_by_id,
    mark_email_as_read,
    fetch_attachment,
    send_email,
    reply_to_email
)

from app.api.email.schemas import EmailReplyRequest, EmailRequest
# from app.api.email.nlp import generate_ai_reply  # Replace with your own AI logic

router = APIRouter()

# -------------------------------
# 📥 Email Cache (expires in 5 min)
# -------------------------------
EMAIL_CACHE = TTLCache(maxsize=1, ttl=300)


# -------------------------------
# 🔹 Fetch Inbox Emails with Pagination + Refresh
# -------------------------------
@router.get("/inbox")
def get_inbox_emails(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    refresh: bool = False
):
    """
    Fetch paginated inbox emails.
    - `skip`: Number of emails to skip (for pagination)
    - `limit`: Max number of emails to return
    - `refresh`: If true, force refresh from Microsoft
    """
    outlook_creds = db.query(OutlookCredentials).filter_by(user_id=current_user.id).first()
    if not outlook_creds:
        raise HTTPException(status_code=400, detail="Outlook account not linked")

    cache_key = f"user:{current_user.id}"

    if refresh or cache_key not in EMAIL_CACHE:
        fetched = fetch_user_emails(current_user.id, db, limit=100)
        EMAIL_CACHE[cache_key] = fetched
    else:
        fetched = EMAIL_CACHE[cache_key]

    all_emails = fetched["emails"]
    paginated = all_emails[skip:skip + limit]

    return {
        "total": len(all_emails),
        "skip": skip,
        "limit": limit,
        "emails": paginated,
        "nextPage": fetched.get("nextPage")
    }



# -------------------------------
# 🔹 Fetch Email by ID
# -------------------------------
@router.get("/inbox/{email_id}")
def get_email_by_id_route(
    background_tasks: BackgroundTasks,
    email_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch specific email and mark as read."""
    email = fetch_email_by_id(current_user.id, db, email_id)

    if not email.get("isRead", False):
        background_tasks.add_task(mark_email_as_read, current_user.id, db, email_id)

    return email


# -------------------------------
# 🤖 Generate AI Reply
# -------------------------------
@router.get("/inbox/{email_id}/generate-reply")
def generate_ai_reply_route(
    email_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate AI-powered reply from email body"""
    email = fetch_email_by_id(current_user.id, db, email_id)
    # ai_reply = generate_ai_reply(email)  # You implement this
    return {"email_id": email_id, "generated_reply": "2"} #ai_reply}


# -------------------------------
# ✉️ Reply to Email
# -------------------------------
@router.post("/inbox/{email_id}/reply")
def reply_to_email_route(
    email_id: str,
    request: EmailReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return reply_to_email(current_user.id, db, email_id, request.reply_body)


# -------------------------------
# 📎 Download Attachment
# -------------------------------
@router.get("/inbox/{email_id}/attachments/{attachment_id}")
def download_attachment_route(
    email_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    attachment = fetch_attachment(current_user.id, db, email_id, attachment_id)

    file_name = attachment["name"]
    content_type = attachment["contentType"]
    content_bytes = base64.b64decode(attachment["contentBytes"])

    return StreamingResponse(
        iter([content_bytes]),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )


# -------------------------------
# 📤 Send Email
# -------------------------------
@router.post("/send")
def send_email_route(
    request: EmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return send_email(current_user.id, db, request.to, request.subject, request.body)


# -------------------------------
# 🔄 Optional: Manual Mailbox Refresh Endpoint
# -------------------------------
@router.get("/refresh-mailbox")
def refresh_mailbox_api(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    emails = fetch_user_emails(current_user.id, db, limit=100)
    EMAIL_CACHE["latest_emails"] = emails
    return {"message": "✅ Mailbox refreshed", "total_emails": len(emails)}
