# app/core/scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.session import SessionLocal
from app.db.models.user import User
from app.api.email.sync import sync_user_inbox
from app.db.models.chat.chat_session import ChatSession

# Initialize the scheduler
scheduler = BackgroundScheduler()


# ---------------------------
# Auto-Delete Old Chat Sessions
# ---------------------------

@scheduler.scheduled_job("cron", hour=0, minute=0)
def auto_delete_old_chats():
    db: Session = SessionLocal()
    try:
        days_to_keep = 30
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        old_sessions = db.query(ChatSession).filter(ChatSession.created_at < cutoff_date).all()

        for session in old_sessions:
            db.delete(session)
        
        db.commit()
        print(f"[INFO] - Auto-deleted {len(old_sessions)} old chat sessions.")
    except Exception as e:
        print(f"[ERROR] - Error deleting old chat sessions: {e}")
    finally:
        db.close()

# ---------------------------
# Start Scheduler
# ---------------------------

def start_scheduler():
    scheduler.start()
    print("[INFO] - Background Scheduler started...")
