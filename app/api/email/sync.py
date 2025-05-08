from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from dateutil import parser
from bs4 import BeautifulSoup
from typing import Optional, List, Dict
import traceback
from collections import defaultdict
import time
from fastapi import BackgroundTasks
from app.api.email.ai_tasks import process_email_thread_with_ai, process_email_with_ai

from app.db.models.email import Email
from app.db.models.email_thread import EmailThread
from app.db.models.outlook_credentials import OutlookCredentials
from app.api.email.get_emails_from_ms import fetch_user_emails_from_ms
from app.api.email.ai_tasks import process_email_with_ai



def sync_result(synced: bool, emails_fetched: int, threads_added: int = 0, reason: Optional[str] = None) -> dict:
    return {
        "synced": synced,
        "emails_fetched": emails_fetched,
        "threads_added": threads_added,
        "reason": reason
    }


def calculate_thread_counts(ms_emails: List[dict]) -> tuple[Dict[str, int], Dict[str, int]]:
    total_counts = defaultdict(int)
    unread_counts = defaultdict(int)

    for email in ms_emails:
        cid = email["conversationId"]
        total_counts[cid] += 1
        if not email.get("isRead", False):
            unread_counts[cid] += 1

    return total_counts, unread_counts


def extract_sender(email: dict) -> tuple:
    sender = email.get("from", {}).get("emailAddress", {})
    return sender.get("address", ""), sender.get("name", "")


def parse_email_data(email: dict, user_id: int, now: datetime) -> Email:
    email_id = email["id"]
    conversation_id = email["conversationId"]
    subject = email.get("subject", "(No Subject)")
    sender_email, sender_name = extract_sender(email)
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
    body = email.get("body", {})
    body_content_type = body.get("contentType", "").lower()
    body_content = body.get("content", "")
    body_plain = BeautifulSoup(body_content, "html.parser").get_text() if body_content_type == "html" else body_content
    body_html = body_content if body_content_type == "html" else None

    return Email(
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
    )


def prepare_email_thread(email: dict, email_id: str, now: datetime, user_id: int, total_count: int = 1, unread_count: int = 0) -> EmailThread:
    conversation_id = email["conversationId"]
    subject = email.get("subject", "(No Subject)")
    sender_email, sender_name = extract_sender(email)
    received_at = parser.isoparse(email["receivedDateTime"])
    body_preview = email.get("bodyPreview", "")
    is_read = email.get("has_read", False)
    has_attachments = email.get("has_attachments", False)

    return EmailThread(
        conversation_id=conversation_id,
        user_id=user_id,
        subject=subject,
        last_email_id=email_id,
        last_email_at=received_at,
        last_sender=sender_email,
        last_sender_name=sender_name,
        last_body_preview=body_preview,
        unread_count=unread_count,
        total_count=total_count,
        is_processing=False,
        created_at=now,
        updated_at=now,
        is_read=is_read,
        has_attachments=has_attachments
    )


def sync_user_inbox(user_id: int, db: Session, background_tasks: BackgroundTasks, limit: int = 100, force: bool = False, ignore_time: bool = False) -> dict:
    start_time = time.time()
    creds = db.query(OutlookCredentials).filter_by(user_id=user_id).first()
    now = datetime.now(timezone.utc)

    if not creds:
        return sync_result(False, 0, reason="Outlook account not linked")

    last_synced_display = "never"
    if creds.last_synced_at:
        last_synced_display = creds.last_synced_at.strftime("%Y-%m-%d %H:%M:%S %Z")

    if not force and creds.last_synced_at:
        last_synced = creds.last_synced_at
        if last_synced.tzinfo is None or last_synced.tzinfo.utcoffset(last_synced) is None:
            last_synced = last_synced.replace(tzinfo=timezone.utc)

        minutes_since = (now - last_synced).total_seconds() / 60
        if minutes_since < 5:
            return sync_result(False, 0, reason=f"Last synced {minutes_since:.1f} mins ago. Minimum interval is 5 mins.")

    # Log the sync attempt
    print(f"[📨 Syncing] User {user_id}")
    print(f"  └── Last synced at: {last_synced_display}")
    print(f"  └── Fetching emails after: {creds.last_refreshed_at or creds.last_synced_at} (UTC)")

    # Determine the timestamp to filter by
    last_synced = creds.last_synced_at

    # Fetch emails
    ms_emails = fetch_user_emails_from_ms(
        user_id, db, limit=limit,
        last_refreshed=None if ignore_time else last_synced
    )["emails"]
    print(f"  └── {len(ms_emails)} emails fetched from Microsoft")

    fetched_count = len(ms_emails)
    emails_fetched = 0
    threads_added = 0

    latest_received_at = None

    for email in ms_emails:
        try:
            email_id = email["id"]
            conversation_id = email["conversationId"]
            received_at = parser.isoparse(email["receivedDateTime"])

            if not db.query(Email).filter_by(id=email_id).first():
                try:
                    db.add(parse_email_data(email, user_id, now))
                    db.flush()
                    emails_fetched += 1
                    
                    ## background_task for Email
                    print(f'[INFO] -- Processing AI for email subject: {email["subject"]}')
                    background_tasks.add_task(
                        process_email_with_ai,
                        email_id=email["id"],
                        user_id = user_id,
                        background_tasks=background_tasks
                    )
                    
                    print(f'[INFO] -- Processing AI for thread (conversation_id): {email["conversationId"]}')
                    background_tasks.add_task(
                        process_email_thread_with_ai,
                        conversation_id=email["conversationId"]
                    )
                    
                    if not latest_received_at or received_at > latest_received_at:
                        latest_received_at = received_at
                except IntegrityError:
                    db.rollback()
                    print(f"⚠️ Duplicate email skipped (ID: {email_id})")
                    continue

            thread = db.query(EmailThread).filter_by(conversation_id=conversation_id).first()
            if thread:
                thread.last_email_id = email_id
                thread.last_email_at = received_at
                thread.last_sender = extract_sender(email)[0]
                thread.last_body_preview = email.get("bodyPreview", "")
                thread.updated_at = now
                if not email.get("isRead", False):
                    thread.unread_count += 1
                thread.total_count += 1
            else:
                try:
                    db.add(prepare_email_thread(email, email_id, now, user_id))
                    threads_added += 1
                    
                except IntegrityError:
                    db.rollback()
                    print(f"⚠️ Duplicate thread skipped (Conversation ID: {conversation_id})")

        except Exception as e:
            db.rollback()
            print(f"❌ Failed to sync email {email.get('id', 'UNKNOWN')} — {str(e)}")
            print(traceback.format_exc())

    try:
        creds.last_synced_at = now
        if latest_received_at:
            creds.last_refreshed_at = latest_received_at
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"❌ Commit failed: {e}")
        return sync_result(False, emails_fetched, reason="Failed to commit changes")

    end_time = time.time()
    duration = end_time - start_time
    print(f"[Done] Synced {emails_fetched}/{fetched_count} new emails in {duration:.2f} seconds.")

    return sync_result(True, emails_fetched, threads_added)



def sync_user_inbox_bulk(user_id: int, db: Session, background_tasks: BackgroundTasks, limit: int = 100) -> dict:
    creds = db.query(OutlookCredentials).filter_by(user_id=user_id).first()
    now = datetime.now(timezone.utc)

    if not creds:
        return sync_result(False, 0, 0, reason="Outlook account not linked")

    ms_emails = fetch_user_emails_from_ms(user_id, db, limit=limit)["emails"]
    new_emails = []
    thread_map = {}

    total_counts, unread_counts = calculate_thread_counts(ms_emails)

    for email in ms_emails:
        try:
            email_id = email["id"]
            conversation_id = email["conversationId"]
            received_at = parser.isoparse(email["receivedDateTime"])

            if not db.query(Email).filter_by(id=email_id).first():
                new_emails.append(parse_email_data(email, user_id, now))

            
            if (conversation_id not in thread_map) or (thread_map[conversation_id].last_email_at < received_at):
                thread_map[conversation_id] = prepare_email_thread(
                    email=email,
                    email_id=email_id,
                    now=now,
                    user_id=user_id,
                    total_count=total_counts[conversation_id],
                    unread_count=unread_counts[conversation_id]
                )

        except Exception as e:
            print(f"❌ Failed to prepare email {email.get('id', 'UNKNOWN')} — {str(e)}")
            print(traceback.format_exc())

    if new_emails:
        db.bulk_save_objects(new_emails)

    existing_ids = {
        r[0] for r in db.query(EmailThread.conversation_id)
        .filter(EmailThread.conversation_id.in_(thread_map.keys())).all()
    }

    threads_to_insert = [t for cid, t in thread_map.items() if cid not in existing_ids]
    if threads_to_insert:
        db.bulk_save_objects(threads_to_insert)
        
        # Background task to add summary and category of the threads
        for thread in threads_to_insert:
            print(f"[INFO] -- Processing AI for thread subject: {thread.subject} ")
            background_tasks.add_task(
                process_email_thread_with_ai,
                conversation_id=thread.conversation_id
                )

    creds.last_synced_at = now
    db.commit()
    
    
    return sync_result(True, len(new_emails), len(threads_to_insert))
