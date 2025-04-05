import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.auth.services import refresh_token
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

    params = {
        "$top": limit,
        "$orderby": "receivedDateTime DESC"
    }

    # Optional: fetch newer emails only
    if last_refreshed:
        params["$filter"] = f"receivedDateTime gt {last_refreshed.isoformat()}Z"

    response = requests.get(GRAPH_API_URL, headers=_headers(access_token), params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch emails")

    data = response.json()
    emails = data.get("value", [])
    next_page = data.get("@odata.nextLink")

    # ✅ Update last_refreshed_at timestamp
    if creds:
        creds.last_refreshed_at = datetime.utcnow()
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
# ✅ Mark Email as Read
# -------------------------------
def mark_email_as_read(user_id: int, db: Session, email_id: str):
    access_token = refresh_token(user_id, db)

    response = requests.patch(
        f"{GRAPH_API_URL}/{email_id}",
        headers=_headers(access_token),
        json={"isRead": True}
    )

    if response.status_code not in [200, 204]:
        raise HTTPException(status_code=response.status_code, detail="Failed to mark email as read")

    return {"message": "Email marked as read"}


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
def send_email(user_id: int, db: Session, to: str, subject: str, body: str):
    access_token = refresh_token(user_id, db)

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}]
        }
    }

    response = requests.post(
        SEND_MAIL_URL,
        headers=_headers(access_token),
        json=payload
    )

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
