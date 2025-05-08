from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from cachetools import TTLCache
import base64
from typing import Optional, List

from app.core.security import get_current_user
from app.db.models.email import Email
from app.db.models.email_thread import EmailThread
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.outlook_credentials import OutlookCredentials
from app.api.email.sync import sync_user_inbox, sync_user_inbox_bulk

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


##########################################
########### TESTING APIs #################

from app.api.email.ai_tasks import process_email_with_ai, process_email_thread_with_ai
@router.get("/ai-process/{email_id}")
def process_email(
    email_id,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    
    return process_email_with_ai(email_id, current_user.id, background_tasks)


@router.get("/ai-process/thread/{conversation_id}")
def process_email(conversation_id):
    return process_email_thread_with_ai(conversation_id)



##########################################
##########################################

# -------------------------------
# 📥 Email Cache (expires in 5 min)
# -------------------------------
EMAIL_CACHE = TTLCache(maxsize=1, ttl=300)


# -------------------------------
# 🔹 Fetch Inbox Emails with Pagination + Refresh
# -------------------------------
# @router.get("/inbox")
# def get_inbox_emails(
#     background_tasks: BackgroundTasks,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db),
#     skip: int = 0,
#     limit: int = 50,
#     refresh: bool = False
# ):
#     """
#     Fetch paginated inbox emails.
#     - `skip`: Number of emails to skip (for pagination)
#     - `limit`: Max number of emails to return
#     - `refresh`: If true, force refresh from Microsoft
#     """
#     outlook_creds = db.query(OutlookCredentials).filter_by(user_id=current_user.id).first()
#     if not outlook_creds:
#         raise HTTPException(status_code=400, detail="Outlook account not linked")

#     cache_key = f"user:{current_user.id}"

#     if refresh or cache_key not in EMAIL_CACHE:
#         fetched = fetch_user_emails(current_user.id, db, limit=100)
#         EMAIL_CACHE[cache_key] = fetched
#     else:
#         fetched = EMAIL_CACHE[cache_key]

#     all_emails = fetched["emails"]
#     paginated = all_emails[skip:skip + limit]

#     return {
#         "total": len(all_emails),
#         "skip": skip,
#         "limit": limit,
#         "emails": paginated,
#         "nextPage": fetched.get("nextPage")
#     }
    

# # -------------------------------
# # 🔹 Fetch Email by ID
# # -------------------------------
# @router.get("/inbox/{email_id}")
# def get_email_by_id_route(
#     background_tasks: BackgroundTasks,
#     email_id: str,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """Fetch specific email and mark as read."""
#     email = fetch_email_by_id(current_user.id, db, email_id)

#     if not email.get("isRead", False):
#         background_tasks.add_task(mark_email_as_read, current_user.id, db, email_id)

#     return email


# # -------------------------------
# # 🤖 Generate AI Reply
# # -------------------------------
# @router.get("/inbox/{email_id}/generate-reply")
# def generate_ai_reply_route(
#     email_id: str,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """Generate AI-powered reply from email body"""
#     email = fetch_email_by_id(current_user.id, db, email_id)
#     # ai_reply = generate_ai_reply(email)  # You implement this
#     return {"email_id": email_id, "generated_reply": "2"} #ai_reply}


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


# # -------------------------------
# # 🔄 Optional: Manual Mailbox Refresh Endpoint
# # -------------------------------
# @router.get("/refresh-mailbox")
# def refresh_mailbox_api(
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     emails = fetch_user_emails(current_user.id, db, limit=100)
#     EMAIL_CACHE["latest_emails"] = emails
#     return {"message": "Mailbox refreshed", "total_emails": len(emails)}



# -------------------------------
# 🧵 Get All Email Threads from DB (Paginated, with optional Category filter)
# -------------------------------
@router.get("/threads")
def get_email_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, description="Number of threads to skip for pagination"),
    limit: int = Query(50, description="Maximum number of threads to return per page"),
    category: Optional[str] = Query(None, description="Filter threads by category (normal, urgent, informational)"),
):
    """
    Fetch paginated email threads for the current user from the database,
    with an optional filter for the thread category.
    """
    query = db.query(EmailThread).filter_by(user_id=current_user.id)

    if category:
        if category.lower() in ["normal", "urgent", "informational"]:
            query = query.filter(func.lower(EmailThread.category) == category.lower())
        else:
            raise HTTPException(status_code=400, detail="Invalid category. Allowed values: normal, urgent, informational")

    threads = (
        query.order_by(EmailThread.last_email_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "conversation_id": t.conversation_id,
            "subject": t.subject,
            "last_sender": t.last_sender,
            "last_sender_name": t.last_sender_name,
            "last_email_at": t.last_email_at,
            "last_email_id": t.last_email_id,
            "last_body_preview": t.last_body_preview,
            "is_read": t.is_read,
            "has_attachments": t.has_attachments,
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
# 📬 Get Full Emails in a Thread from DB
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
            "thread_subject": e.thread_subject,
            "sender": e.sender,
            "sender_name": e.sender_name,
            "recipients": e.recipients,
            "cc": e.cc,
            "received_at": e.received_at,
            "sent_at": e.sent_at,
            "synced_at": e.synced_at,
            "is_read": e.is_read,
            "has_attachments": e.has_attachments,
            "body_preview": e.body_preview,
            "body_plain": e.body_plain,
            "body_html": e.body_html,
            "web_link": e.web_link,
            "message_id": e.message_id,
            "importance": e.importance,
            
            # AI-related fields
            "summary": e.summary,
            "quick_replies": e.quick_replies,
            "ai_draft": e.ai_draft,
            "priority_score": e.priority_score,
            "categories": e.categories,
            "topic": e.topic,
            "extracted_tasks": e.extracted_tasks
        }
        for e in emails
    ]


@router.get("/sync-mailbox-bulk")
def sync_mailbox_bulk(
    background_tasks: BackgroundTasks,
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

    result = sync_user_inbox_bulk(current_user.id, db, background_tasks)

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
    background_tasks: BackgroundTasks,
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
        force=force,
        background_tasks=background_tasks
    )

    return {
        "message": "Mailbox synced (standard mode)" if result["synced"] else "Sync skipped",
        "synced": result["synced"],
        "emails_fetched": result["emails_fetched"],
        "threads_added": result.get("threads_added", 0),
        "reason": result.get("reason"),
        "last_synced_at": creds.last_synced_at
    }
    
    
    
# @router.post("{email_id}/ai-process")
# def enrich_email_api(
#     req: email_id,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     email = db.query(Email).filter_by(id=req.email_id, user_id=current_user.id).first()
#     if not email:
#         raise HTTPException(status_code=404, detail="Email not found")

#     try:
#         enrich_email_with_ai(req.email_id)
#         return {"message": "AI enrichment complete", "email_id": req.email_id}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"AI enrichment failed: {e}")


from typing import Optional

@router.get("/search", summary="Search user emails (case-insensitive)")
def search_emails_route(
    query: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, description="Number of emails to skip for pagination"),
    limit: int = Query(50, description="Maximum number of emails to return per page"),
    search_in: Optional[str] = Query(None, enum=["subject", "body_plain", "sender", "recipients"], description="Optional field to specify where to search"),
):
    """
    Search user emails based on a query (case-insensitive).

    - `query`: The search term.
    - `skip`: Number of emails to skip for pagination.
    - `limit`: Maximum number of emails to return.
    - `search_in`: Optional field to specify where to search (subject, body_plain, sender, recipients).
                   If None, search across all relevant fields.
    """
    outlook_creds = db.query(OutlookCredentials).filter_by(user_id=current_user.id).first()
    if not outlook_creds:
        raise HTTPException(status_code=400, detail="Outlook account not linked")

    emails_query = db.query(Email).filter(Email.user_id == current_user.id)

    if query:
        search_expression = func.lower(query)
        if search_in == "subject":
            emails_query = emails_query.filter(func.lower(Email.subject).contains(search_expression))
        elif search_in == "body_plain":
            emails_query = emails_query.filter(func.lower(Email.body_plain).contains(search_expression))
        elif search_in == "sender":
            emails_query = emails_query.filter(func.lower(Email.sender).contains(search_expression))
        elif search_in == "recipients":
            emails_query = emails_query.filter(func.lower(Email.recipients).contains(search_expression))
        else:
            emails_query = emails_query.filter(
                func.lower(Email.subject).contains(search_expression) |
                func.lower(Email.body_plain).contains(search_expression) |
                func.lower(Email.sender).contains(search_expression) |
                func.lower(Email.recipients).contains(search_expression)
            )

    total = emails_query.count()
    paginated_emails = emails_query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "emails": [{"id": e.id, "subject": e.subject, "sender": e.sender} for e in paginated_emails], # Adjust response as needed
    }