import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.auth.services import refresh_token
from app.db.models.email import Email
from app.db.models.outlook_credentials import OutlookCredentials

GRAPH_API_URL = "https://graph.microsoft.com/v1.0/me/messages"
SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/me/sendMail"


# -------------------------------
# 📥 Fetch Inbox Emails (Paginated)
# -------------------------------
def fetch_user_emails(user_id: int, db: Session, limit: int = 50):
    access_token = refresh_token(user_id, db)

    creds = db.query(OutlookCredentials).filter_by(user_id=user_id).first()
    last_refreshed = creds.last_refreshed_at if creds else None
    last_refreshed = None

    params = {
        "$top": limit,
        "$orderby": "receivedDateTime DESC"
    }

    # Optional: fetch newer emails only
    
    if last_refreshed:
        # Ensure UTC timezone-aware and remove microseconds
        if last_refreshed.tzinfo is None:
            last_refreshed = last_refreshed.replace(tzinfo=timezone.utc)
        last_refreshed = last_refreshed.replace(microsecond=0)

        iso_timestamp = last_refreshed.isoformat()
        print("Using filter timestamp:", iso_timestamp)
        params["$filter"] = f"receivedDateTime gt {iso_timestamp}"

    response = requests.get(GRAPH_API_URL, headers=_headers(access_token), params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch emails")

    data = response.json()
    emails = data.get("value", [])
    next_page = data.get("@odata.nextLink")

    # ✅ Update last_refreshed_at timestamp
    if creds:
        creds.last_refreshed_at = datetime.now(timezone.utc).replace(microsecond=0)
        db.commit()

    return {
        "emails": [
            {
                "id": email.get("id"),
                "from": {
                    "name": email.get("from", {}).get("emailAddress", {}).get("name", "Unknown"),
                    "email": email.get("from", {}).get("emailAddress", {}).get("address", "No Email")
                },
                "subject": email.get("subject", "(No Subject)"),
                "body_preview": email.get("bodyPreview", ""),
                "date": email.get("receivedDateTime", ""),
                "isRead": email.get("isRead", False),
                "hasAttachments": email.get("hasAttachments", False),
                "conversationId": email.get("conversationId", "")
            }
            for email in emails
        ],
        "nextPage": next_page
    }


# -------------------------------
# 📧 Fetch Email by ID
# -------------------------------
def fetch_email_by_id(user_id: int, db: Session, email_id: str):
    access_token = refresh_token(user_id, db)

    response = requests.get(f"{GRAPH_API_URL}/{email_id}", headers=_headers(access_token))
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch email")

    email_data = response.json()

    # Fetch attachment metadata if present
    attachments = []
    if email_data.get("hasAttachments"):
        att_resp = requests.get(f"{GRAPH_API_URL}/{email_id}/attachments", headers=_headers(access_token))
        if att_resp.status_code == 200:
            attachments = [
                {
                    "id": att.get("id"),
                    "name": att.get("name"),
                    "size": att.get("size"),
                    "contentType": att.get("contentType"),
                    "isInline": att.get("isInline", False)
                }
                for att in att_resp.json().get("value", [])
            ]

    return {
        "id": email_data.get("id"),
        "subject": email_data.get("subject", "(No Subject)"),
        "body_preview": email_data.get("bodyPreview", ""),
        "date": email_data.get("receivedDateTime", ""),
        "isRead": email_data.get("isRead", False),
        "hasAttachments": email_data.get("hasAttachments", False),
        "conversationId": email_data.get("conversationId", ""),
        "sender": {
            "name": email_data.get("from", {}).get("emailAddress", {}).get("name", "Unknown"),
            "email": email_data.get("from", {}).get("emailAddress", {}).get("address", "No Email")
        },
        "toRecipients": [
            {
                "name": r.get("emailAddress", {}).get("name", ""),
                "email": r.get("emailAddress", {}).get("address", "")
            } for r in email_data.get("toRecipients", [])
        ],
        "ccRecipients": [
            {
                "name": r.get("emailAddress", {}).get("name", ""),
                "email": r.get("emailAddress", {}).get("address", "")
            } for r in email_data.get("ccRecipients", [])
        ],
        "webLink": email_data.get("webLink", "#"),
        "body": email_data.get("body", {}).get("content", ""),
        "attachments": attachments
    }


# -------------------------------
# ✅ Mark Email as Read Utility
# -------------------------------
from app.db.session import SessionLocal  # adjust import to match your project

from app.db.session import SessionLocal
from app.db.models.email import Email
from app.db.models.email_thread import EmailThread
import requests

GRAPH_API_URL = "https://graph.microsoft.com/v1.0/me/messages"

def mark_email_as_read(user_id: int, email_id: str):
    db = SessionLocal()
    try:
        access_token = refresh_token(user_id, db)

        # Step 1: Update on Microsoft Graph
        response = requests.patch(
            f"{GRAPH_API_URL}/{email_id}",
            headers=_headers(access_token),
            json={"isRead": True}
        )

        if response.status_code in [200, 204]:
            print(f"[INFO] - Updated read status from Microsoft for {email_id}")

            # Step 2: Update local DB
            email = db.query(Email).filter_by(user_id=user_id, id=email_id).first()
            if email and not email.is_read:
                email.is_read = True
                db.commit()
                print(f"[INFO] - Updated read status in DB for {email_id}")

                # Step 3: Update EmailThread
                thread = db.query(EmailThread).filter_by(user_id=user_id, conversation_id=email.conversation_id).first()
                if thread:
                    unread_count = db.query(Email).filter_by(
                        user_id=user_id,
                        conversation_id=email.conversation_id,
                        is_read=False
                    ).count()

                    thread.unread_count = unread_count
                    thread.is_read = unread_count == 0
                    db.commit()
                    print(f"[INFO] - Updated thread {email.conversation_id}: is_read={thread.is_read}, unread_count={unread_count}")
        else:
            print(f"[ERROR] - Failed to mark email {email_id} as read: {response.status_code}")
    except Exception as e:
        print(f"[EXCEPTION] - Error marking email as read: {e}")
    finally:
        db.close()




# -------------------------------
# 📎 Fetch Attachment Content
# -------------------------------
def fetch_attachment(user_id: int, db: Session, email_id: str, attachment_id: str):
    access_token = refresh_token(user_id, db)

    response = requests.get(
        f"{GRAPH_API_URL}/{email_id}/attachments/{attachment_id}",
        headers=_headers(access_token)
    )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch attachment")

    return response.json()


# -------------------------------
# 📤 Send New Email
# -------------------------------
def send_email(user_id: int, db: Session, to: str, subject: str, body: str, attachments=[]):
    access_token = refresh_token(user_id, db)

    # Build attachments (if any)
    attachment_payload = [
    {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": att.name,
        "contentType": att.content_type,
        "contentBytes": att.content_bytes
    }
    for att in attachments
]


    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
            "attachments": attachment_payload
        }
    }

    response = requests.post(SEND_MAIL_URL, headers=_headers(access_token), json=payload)

    if response.status_code != 202:
        raise HTTPException(status_code=response.status_code, detail="Failed to send email")

    return {"message": "Email sent successfully"}



# -------------------------------
# 🔁 Reply to Email
# -------------------------------
def reply_to_email(user_id: int, db: Session, email_id: str, reply_body: str):
    access_token = refresh_token(user_id, db)

    payload = {
        "message": {
            "body": {
                "contentType": "HTML",
                "content": reply_body
            }
        }
    }

    response = requests.post(
        f"{GRAPH_API_URL}/{email_id}/reply",
        headers=_headers(access_token),
        json=payload
    )

    if response.status_code != 202:
        raise HTTPException(status_code=response.status_code, detail="Failed to send reply")

    return {"message": "Reply sent successfully"}


# -------------------------------
# 🧱 Internal: Header Builder
# -------------------------------
def _headers(access_token: str):
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
def _update_last_refresh(user_id: int, db: Session):
    creds = db.query(OutlookCredentials).filter_by(user_id=user_id).first()
    if creds:
        creds.last_refreshed_at = datetime.utcnow()
        db.commit()



######################################################################################
############################# Threads ###########################

