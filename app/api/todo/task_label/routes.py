from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from app.api.todo.task_label import services, schemas

router = APIRouter()

@router.post("/", response_model=schemas.TaskLabelOut)
def assign_label(
    payload: schemas.TaskLabelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.assign_label_to_task(db, payload.task_id, payload.label_id)

@router.delete("/", response_model=schemas.TaskLabelOut)
def remove_label(
    payload: schemas.TaskLabelDelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    removed = services.remove_label_from_task(db, payload.task_id, payload.label_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Label not found on task")
    return removed
