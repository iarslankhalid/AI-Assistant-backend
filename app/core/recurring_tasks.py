import asyncio
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.scheduled_task import ScheduledTask
from app.agent.websocket_handler import session_memory
from app.agent.transcript_processor import process_transcript_streaming 

def check_and_run_scheduled_tasks_sync():
    """
    Checks for scheduled tasks that are due and triggers them 
    if the user is current connected via WebSocket.
    This function is designed to be run by a Scheduler (e.g. APScheduler).
    """
    
    # Session memory structure: 
    # {session_id: {"user_id": 1, "websocket": ws, "timezone": "UTC", "loop": loop, ...}}
    
    # 1. Gather active users
    active_sessions = {}
    active_user_ids = []
    
    if not session_memory:
        return

    for session_id, session_data in session_memory.items():
        if session_data.get("websocket") and session_data.get("user_id"):
            uid = session_data["user_id"]
            active_user_ids.append(uid)
            # Store session info for quick lookup by user_id
            active_sessions[uid] = {
                "session_id": session_id,
                "websocket": session_data["websocket"],
                "loop": session_data.get("loop"), 
                "data": session_data
            }

    if not active_sessions:
        return

    # 2. Check DB for tasks for these users
    db: Session = SessionLocal()
    try:
        # Filter tasks: active, for currently connected users
        tasks = db.query(ScheduledTask).filter(
            ScheduledTask.is_active == True,
            ScheduledTask.user_id.in_(active_user_ids)
        ).all()
        
        if not tasks:
            return

        current_utc = datetime.now(ZoneInfo("UTC"))
        
        for task in tasks:
            user_session = active_sessions.get(task.user_id)
            if not user_session:
                continue

            # Determine User's Timezone
            user_tz_str = user_session["data"].get("timezone") or task.timezone or "UTC"
            try:
                user_tz = ZoneInfo(user_tz_str)
            except:
                user_tz = ZoneInfo("UTC")

            now_local = current_utc.astimezone(user_tz)
            
            should_run = False
            
            # Frequency: daily
            if task.frequency == "daily" and task.schedule_time:
                try:
                    h, m = map(int, task.schedule_time.split(":"))
                    
                    if now_local.hour == h and now_local.minute == m:
                        # Check last_run_at
                        if task.last_run_at:
                            # Normalize last_run_at (ensure aware)
                            if task.last_run_at.tzinfo is None:
                                last_run_aware = task.last_run_at.replace(tzinfo=ZoneInfo("UTC"))
                            else:
                                last_run_aware = task.last_run_at
                            
                            last_run_local = last_run_aware.astimezone(user_tz)
                            
                            if last_run_local.date() == now_local.date():
                                continue # Already ran today
                        should_run = True
                except ValueError:
                    print(f"Invalid time format for task {task.id}: {task.schedule_time}")
            
            elif task.frequency == "hourly":
                if now_local.minute == 0:
                     if task.last_run_at:
                        if task.last_run_at.tzinfo is None:
                                last_run_aware = task.last_run_at.replace(tzinfo=ZoneInfo("UTC"))
                        else:
                            last_run_aware = task.last_run_at
                            
                        last_run_local = last_run_aware.astimezone(user_tz)
                        if last_run_local.hour == now_local.hour and last_run_local.date() == now_local.date():
                            continue
                     should_run = True

            if should_run:
                # Update last_run_at first to prevent re-entry
                task.last_run_at = current_utc
                db.commit()

                # Trigger Agent
                loop = user_session.get("loop")
                ws = user_session.get("websocket")
                sess_id = user_session.get("session_id")
                
                # Construct trigger message
                trigger_text = f"Perform scheduled task: {task.task_description}"
                
                if loop and not loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        process_transcript_streaming(
                            ws,
                            sess_id,
                            trigger_text,
                            session_memory
                        ),
                        loop
                    )
                else:
                    print(f"Loop invalid for user {task.user_id}")

    except Exception as e:
        print(f"Error in check_scheduled_tasks: {e}")
    finally:
        db.close()
