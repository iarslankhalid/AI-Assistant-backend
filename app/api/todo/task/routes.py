from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from app.db.models.todo.task import Task
from . import schemas, services

router = APIRouter()

@router.get("/project/{project_id}")
def tasks_by_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return services.get_tasks_by_project(db, project_id, current_user.id)

@router.get("/label/{label_id}")
def tasks_by_label(label_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return services.get_tasks_by_label(db, label_id, current_user.id)

@router.get("/completed")
def completed_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return services.get_completed_tasks(db, current_user.id)

@router.get("/pending")
def pending_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return services.get_pending_tasks(db, current_user.id)



@router.post("/", response_model=schemas.TaskOut)
def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.create_task(db, task, current_user.id)

@router.get("/", response_model=list[schemas.TaskOut])
def get_my_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.get_tasks_by_user(db, current_user.id)

@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = services.get_task(db, task_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.put("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    task: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    updated = services.update_task(db, task_id, task, current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated

@router.delete("/tasks/{task_id}/soft-delete")
def soft_delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.creator_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.is_deleted = True
    db.commit()
    return {"message": "Task moved to trash"}


@router.get("/tasks/trashed")
def get_trashed_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Task).filter(
        Task.creator_id == user.id,
        Task.is_deleted == True
    ).all()


@router.post("/tasks/{task_id}/restore")
def restore_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.creator_id == user.id).first()
    if not task or not task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not in trash")
    
    task.is_deleted = False
    db.commit()
    return {"message": "Task restored"}


@router.delete("/tasks/{task_id}/hard-delete")
def hard_delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.creator_id == user.id).first()
    if not task or not task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not in trash")

    db.delete(task)
    db.commit()
    return {"message": "Task permanently deleted"}



