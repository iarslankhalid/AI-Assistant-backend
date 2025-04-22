from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from cachetools import TTLCache
import base64

from app.api.auth.services import refresh_token
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
    reply_to_email,
    fetch_full_thread_by_conversation
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
    return send_email(current_user.id, db, request.to, request.subject, request.body, request.attachments)


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
    return {"message": "Mailbox refreshed", "total_emails": len(emails)}



@router.get("/inbox/{conversation_id}/thread")
def get_email_thread(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return full email thread with message details."""
    return fetch_full_thread_by_conversation(current_user.id, db, conversation_id)


from app.db.models.outlook_credentials import OutlookCredentials
from app.db.models.email_thread import EmailThread
from app.db.models.email import Email

@router.get("/sync-status")
def email_sync_status(
    db: Session = Depends(get_db)
):
    users = (
        db.query(User)
        .join(OutlookCredentials, OutlookCredentials.user_id == User.id)
        .filter(User.auth_provider == "outlook")
        .all()
    )

    result = []
    for user in users:
        creds = db.query(OutlookCredentials).filter_by(user_id=user.id).first()
        thread_count = db.query(EmailThread).filter_by(user_id=user.id).count()
        email_count = db.query(Email).filter_by(user_id=user.id).count()

        result.append({
            "user_id": user.id,
            "email": user.email,
            "last_synced_at": creds.last_synced_at if creds else None,
            "total_threads": thread_count,
            "total_emails": email_count
        })

    return result


# -------------------------------
# 🧵 Get All Email Threads (Paginated)
# -------------------------------
@router.get("/threads")
def get_email_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50
):
    threads = (
        db.query(EmailThread)
        .filter_by(user_id=current_user.id)
        .order_by(EmailThread.last_email_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "conversation_id": t.conversation_id,
            "subject": t.subject,
            "last_sender": t.last_sender,
            "last_email_at": t.last_email_at,
            "last_email_id": t.last_email_id,
            "last_body_preview": t.last_body_preview,
            "unread_count": t.unread_count,
            "total_count": t.total_count,
            # AI Features
            "summary": t.summary,
            "topic": t.topic,
            "category": t.category,
            "priority_score": t.priority_score,
            "extracted_tasks": t.extracted_tasks,
            "is_processing": t.is_processing,
            # Timestamps
            "created_at": t.created_at,
            "updated_at": t.updated_at
        }
        for t in threads
    ]



# -------------------------------
# 📬 Get Full Emails in a Thread
# -------------------------------
@router.get("/threads/{conversation_id}")
def get_thread_emails(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    emails = (
        db.query(Email)
        .filter_by(user_id=current_user.id, conversation_id=conversation_id)
        .order_by(Email.received_at.asc())
        .all()
    )

    return [
        {
            "id": e.id,
            "subject": e.subject,
            "sender": e.sender,
            "recipients": e.recipients,
            "cc": e.cc,
            "received_at": e.received_at,
            "is_read": e.is_read,
            "has_attachments": e.has_attachments,
            "body_preview": e.body_preview,
            "body_plain": e.body_plain,
            "body_html": e.body_html
        }
        for e in emails
    ]


from app.api.email.sync import sync_user_inbox, sync_user_inbox_bulk

@router.get("/sync-mailbox-bulk")
def sync_mailbox_bulk(
    force: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ⚡️ Fast sync: Bulk insert emails and threads.
    """
    creds = db.query(OutlookCredentials).filter_by(user_id=current_user.id).first()
    if not creds:
        raise HTTPException(status_code=400, detail="Outlook account not linked")

    result = sync_user_inbox_bulk(current_user.id, db)

    return {
        "message": "Mailbox synced (bulk mode)" if result["synced"] else "Sync skipped",
        "synced": result["synced"],
        "emails_fetched": result["emails_fetched"],
        "threads_added": result.get("threads_added", 0),
        "reason": result.get("reason"),
        "last_synced_at": creds.last_synced_at
    }

@router.get("/sync-mailbox")
def sync_mailbox_to_db(
    force: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    📥 Sync new emails into DB based on last_synced_at.
    """
    creds = db.query(OutlookCredentials).filter_by(user_id=current_user.id).first()
    if not creds:
        raise HTTPException(status_code=400, detail="Outlook account not linked")

    result = sync_user_inbox(
        user_id=current_user.id,
        db=db,
        limit=100,
        force=force
    )

    return {
        "message": "Mailbox synced (standard mode)" if result["synced"] else "Sync skipped",
        "synced": result["synced"],
        "emails_fetched": result["emails_fetched"],
        "threads_added": result.get("threads_added", 0),  # Optional if standard sync doesn't track this
        "reason": result.get("reason"),
        "last_synced_at": creds.last_synced_at
    }