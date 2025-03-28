from pydantic import BaseModel
from typing import Optional

class LabelBase(BaseModel):
    name: str
    color: Optional[str] = "charcoal"
    order: Optional[int] = 0
    is_favorite: Optional[bool] = False
    is_shared: Optional[bool] = False  # optional for future use

class LabelCreate(LabelBase):
    pass

class LabelUpdate(LabelBase):
    pass

class LabelOut(LabelBase):
    id: int
    user_id: int

    model_config = {
        "from_attributes": True
    }
