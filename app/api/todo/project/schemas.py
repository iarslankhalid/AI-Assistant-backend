from pydantic import BaseModel
from typing import Optional

class ProjectBase(BaseModel):
    name: str
    color: Optional[str] = "charcoal"
    order: Optional[int] = 0
    is_shared: Optional[bool] = False
    is_favorite: Optional[bool] = False
    is_inbox_project: Optional[bool] = False
    is_team_inbox: Optional[bool] = False
    view_style: Optional[str] = "list"

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    pass

class ProjectOut(ProjectBase):
    id: int
    url: Optional[str]
    user_id: int

    model_config = {
        "from_attributes": True
    }
