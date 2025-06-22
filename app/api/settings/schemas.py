from pydantic import BaseModel
from typing import Optional

class SettingsUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    utc_offset: Optional[str] = None

class Settings(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    auth_provider: Optional[str] = None
    timezone: Optional[str] = None
    utc_offset: Optional[str] = None

    class Config:
        orm_mode = True
