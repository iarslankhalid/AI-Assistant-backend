from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.db.models.user import User
from app.api.email.sync import sync_user_inbox

scheduler = BackgroundScheduler()

@scheduler.scheduled_job("interval", minutes=5)
def auto_sync():
    db = SessionLocal()
    users = db.query(User).all()
    for user in users:
        try:
            sync_user_inbox(user.id, db)
        except Exception as e:
            print(f"[ERROR] - Error syncing user {user.id}: {e}")
    db.close()

def start_scheduler():
    scheduler.start()
    print("[INFO] - Email Sync Scheduler started...")
