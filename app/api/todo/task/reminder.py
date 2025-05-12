# app/tasks/reminders.py
from datetime import datetime
from app.celery import celery_app
from app.db.session import SessionLocal
from app.db.models.todo import Task

@celery_app.task
def check_and_send_reminders():
    db = SessionLocal()
    now = datetime.utcnow()

    # Fetch tasks whose reminder time is <= now and not completed
    tasks = db.query(Task).filter(
        Task.reminder_at != None,
        Task.reminder_at <= now,
        Task.is_completed == False,
        Task.is_deleted == False
    ).all()

    for task in tasks:
        # TODO: Replace this with real email or notification logic
        print(f"🔔 Reminder: Task '{task.content}' is due soon!")

        # Optional: Clear reminder so it's not triggered again
        task.reminder_at = None
        db.add(task)

    db.commit()
    db.close()
