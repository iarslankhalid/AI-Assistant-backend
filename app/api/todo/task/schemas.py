from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TaskBase(BaseModel):
    content: str
    description: Optional[str] = None
    is_completed: Optional[bool] = False
    order: Optional[int] = 0
    priority: Optional[int] = 1
    project_id: int
    section_id: Optional[int] = None
    parent_id: Optional[int] = None
    assignee_id: Optional[int] = None
    assigner_id: Optional[int] = None

    due_date: Optional[datetime] = None         # 🗓 Due Date
    reminder_at: Optional[datetime] = None      # ⏰ Reminder
    recurrence: Optional[str] = None            # 🔁 Recurrence type

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    content: Optional[str] = None
    description: Optional[str] = None
    is_completed: Optional[bool] = None
    order: Optional[int] = None
    priority: Optional[int] = None
    section_id: Optional[int] = None
    parent_id: Optional[int] = None
    assignee_id: Optional[int] = None
    assigner_id: Optional[int] = None

    due_date: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    recurrence: Optional[str] = None

class TaskOut(TaskBase):
    id: int
    creator_id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
