from pydantic import BaseModel

class ToDoBase(BaseModel):
    title: str
    description: str | None = None

class ToDoCreate(ToDoBase):
    pass

class ToDoOut(ToDoBase):
    id: int
    completed: bool

    class Config:
        orm_mode = True
