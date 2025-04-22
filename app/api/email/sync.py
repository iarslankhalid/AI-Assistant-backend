from app.db.models.email import Email
from app.db.models.email_thread import EmailThread
from app.db.models.outlook_credentials import OutlookCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from dateutil import parser
from app.api.email.get_emails_from_ms import fetch_user_emails_from_ms
from bs4 import BeautifulSoup
import traceback

def sync_user_inbox(user_id: int, db: Session, limit: int = 100, force: bool = False):
    creds = db.query(OutlookCredentials).filter_by(user_id=user_id).first()
    now = datetime.now(timezone.utc)

    if not creds:
        return {
            "synced": False,
            "reason": "Outlook account not linked",
            "emails_fetched": 0
        }

    if not force and creds.last_synced_at:
        last_synced = creds.last_synced_at
        if last_synced.tzinfo is None or last_synced.tzinfo.utcoffset(last_synced) is None:
            last_synced = last_synced.replace(tzinfo=timezone.utc)

        minutes_since = (now - last_synced).total_seconds() / 60
        if minutes_since < 5:
            return {
                "synced": False,
                "reason": f"Last synced {minutes_since:.1f} minutes ago. Minimum interval is 5 mins.",
                "emails_fetched": 0
            }

    print(f"[Syncing] Fetching emails for user {user_id}...")
    ms_emails = fetch_user_emails_from_ms(user_id, db, limit=limit)["emails"]
    emails_fetched = 0

    for email in ms_emails:
        try:
            email_id = email["id"]
            conversation_id = email["conversationId"]
            subject = email.get("subject", "(No Subject)")

            # ✅ Correct nested sender access
            sender_info = email.get("from", {}).get("emailAddress", {})
            sender_email = sender_info.get("address", "")
            sender_name = sender_info.get("name", "")

            # ✅ Correct recipient and cc extraction
            recipients = [r.get("emailAddress", {}).get("address", "") for r in email.get("toRecipients", [])]
            cc = [r.get("emailAddress", {}).get("address", "") for r in email.get("ccRecipients", [])]

            received_at = parser.isoparse(email["receivedDateTime"])
            sent_at = parser.isoparse(email.get("sentDateTime", email["receivedDateTime"]))
            is_read = email.get("isRead", False)
            has_attachments = email.get("hasAttachments", False)
            body_preview = email.get("bodyPreview", "")
            web_link = email.get("webLink", "")
            message_id = email.get("internetMessageId", "")
            importance = email.get("importance", "normal")
            categories = email.get("categories", [])

            # ✅ Handle email body parsing
            body = email.get("body", {})
            body_content_type = body.get("contentType", "").lower()
            body_content = body.get("content", "")
            body_plain, body_html = None, None

            if body_content_type == "html":
                body_html = body_content
                body_plain = BeautifulSoup(body_content, "html.parser").get_text()
            elif body_content_type == "text":
                body_plain = body_content

            # Save Email if not exists
            if not db.query(Email).filter_by(id=email_id).first():
                db.add(Email(
                    id=email_id,
                    user_id=user_id,
                    subject=subject,
                    body_preview=body_preview,
                    sender=sender_email,
                    sender_name=sender_name,
                    recipients=recipients,
                    cc=cc,
                    conversation_id=conversation_id,
                    thread_subject=subject,
                    is_read=is_read,
                    has_attachments=has_attachments,
                    received_at=received_at,
                    sent_at=sent_at,
                    synced_at=now,
                    web_link=web_link,
                    message_id=message_id,
                    importance=importance,
                    categories=categories,
                    body_plain=body_plain,
                    body_html=body_html,
                    is_fully_synced=True
                ))
                emails_fetched += 1

            # Upsert EmailThread
            thread = db.query(EmailThread).filter_by(user_id=user_id, conversation_id=conversation_id).first()

            if thread:
                thread.last_email_id = email_id
                thread.last_email_at = received_at
                thread.last_sender = sender_email
                thread.last_body_preview = body_preview
                thread.updated_at = now
                if not is_read:
                    thread.unread_count += 1
                thread.total_count += 1
            else:
                db.add(EmailThread(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    subject=subject,
                    last_email_id=email_id,
                    last_email_at=received_at,
                    last_sender=sender_email,
                    last_body_preview=body_preview,
                    unread_count=0 if is_read else 1,
                    total_count=1,
                    created_at=now,
                    updated_at=now
                ))

        except Exception as e:
            print(f"❌ Failed to sync email {email.get('id', 'UNKNOWN')} — {str(e)}")
            print(traceback.format_exc())

    # Update credentials sync time
    creds.last_synced_at = now
    db.commit()

    print(f"[✓] Sync complete for user {user_id} — {emails_fetched} emails fetched.")

    return {
        "synced": True,
        "emails_fetched": emails_fetched
    }
