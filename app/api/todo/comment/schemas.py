from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CommentBase(BaseModel):
    content: str
    task_id: Optional[int] = None
    project_id: Optional[int] = None
    attachment_url: Optional[str] = None

class CommentCreate(CommentBase):
    pass

class CommentUpdate(BaseModel):
    content: Optional[str] = None
    attachment_url: Optional[str] = None

class CommentOut(CommentBase):
    id: int
    user_id: int
    posted_at: datetime

    model_config = {
        "from_attributes": True
    }
