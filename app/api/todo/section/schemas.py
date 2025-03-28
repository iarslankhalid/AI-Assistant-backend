from pydantic import BaseModel
from typing import Optional

class SectionBase(BaseModel):
    name: str
    order: Optional[int] = 0

class SectionCreate(SectionBase):
    project_id: int

class SectionUpdate(SectionBase):
    pass

class SectionOut(SectionBase):
    id: int
    project_id: int

    model_config = {
        "from_attributes": True
    }
