from pydantic import BaseModel

class TaskLabelCreate(BaseModel):
    task_id: int
    label_id: int

class TaskLabelOut(TaskLabelCreate):
    pass  # No additional fields, but still useful for validation

class TaskLabelDelete(BaseModel):
    task_id: int
    label_id: int
