from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.session import Base

class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Task Description (e.g., "Tell me the weather")
    task_description = Column(Text, nullable=False)
    
    # Schedule configuration
    # For simplicity, supporting:
    # - frequency: "daily", "hourly" (default: "daily")
    # - time: "HH:MM" (for daily)
    priority = Column(Integer, default=1)
    frequency = Column(String, default="daily") # daily, hourly
    schedule_time = Column(String, nullable=True) # "10:00"
    timezone = Column(String, default="UTC")
    
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="scheduled_tasks")
