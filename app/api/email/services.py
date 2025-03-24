import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.api.auth.services import refresh_token


GRAPH_API_URL = "https://graph.microsoft.com/v1.0/me/messages"
SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/me/sendMail"


def get_headers(access_token: str):
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


def fetch_user_emails(user_id: int, db: Session, limit: int = 25):
    access_token = refresh_token(user_id, db)
    params = {"$top": limit, "$orderby": "receivedDateTime DESC"}
    response = requests.get(GRAPH_API_URL, headers=get_headers(access_token), params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch emails")

    emails = response.json().get("value", [])
    return [
        {
            "id": email["id"],
            "subject": email.get("subject", ""),
            "body_preview": email.get("bodyPreview", ""),
            "from": email.get("from", {}).get("emailAddress", {}),
            "isRead": email.get("isRead", False),
            "date": email.get("receivedDateTime", ""),
        }
        for email in emails
    ]


def fetch_email_by_id(user_id: int, db: Session, email_id: str):
    access_token = refresh_token(user_id, db)
    url = f"{GRAPH_API_URL}/{email_id}"
    response = requests.get(url, headers=get_headers(access_token))

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch email")

    return response.json()


def send_email(user_id: int, db: Session, to: str, subject: str, body: str):
    access_token = refresh_token(user_id, db)

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}]
        }
    }

    response = requests.post(SEND_MAIL_URL, headers=get_headers(access_token), json=payload)

    if response.status_code != 202:
        raise HTTPException(status_code=500, detail="Failed to send email")

    return {"message": "✅ Email sent successfully"}


def reply_to_email(user_id: int, db: Session, email_id: str, reply_body: str):
    access_token = refresh_token(user_id, db)

    url = f"{GRAPH_API_URL}/{email_id}/reply"
    payload = {
        "message": {
            "body": {
                "contentType": "HTML",
                "content": reply_body
            }
        }
    }

    response = requests.post(url, headers=get_headers(access_token), json=payload)

    if response.status_code != 202:
        raise HTTPException(status_code=500, detail="Failed to send reply")

    return {"message": "✅ Reply sent successfully"}


def mark_email_as_read(user_id: int, db: Session, email_id: str):
    access_token = refresh_token(user_id, db)

    url = f"{GRAPH_API_URL}/{email_id}"
    payload = {"isRead": True}

    response = requests.patch(url, headers=get_headers(access_token), json=payload)

    if response.status_code not in [200, 204]:
        raise HTTPException(status_code=500, detail="Failed to mark email as read")

    return {"message": "✅ Email marked as read"}


def fetch_attachment(user_id: int, db: Session, email_id: str, attachment_id: str):
    access_token = refresh_token(user_id, db)

    url = f"{GRAPH_API_URL}/{email_id}/attachments/{attachment_id}"
    response = requests.get(url, headers=get_headers(access_token))

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch attachment")

    return response.json()
