from sqlalchemy.orm import Session
from app.db.models.todo.task import Task
from . import schemas

from datetime import date
from app.db.models.todo.task_label import TaskLabel

def get_tasks_by_project(db: Session, project_id: int, user_id: int):
    return db.query(Task).filter(
        Task.project_id == project_id,
        Task.creator_id == user_id,
        Task.is_deleted == False
    ).all()

def get_tasks_by_label(db: Session, label_id: int, user_id: int):
    return db.query(Task).join(Task.labels).filter(
        TaskLabel.label_id == label_id,
        Task.creator_id == user_id,
        Task.is_deleted == False
    ).all()

def get_completed_tasks(db: Session, user_id: int):
    return db.query(Task).filter(
        Task.is_completed == True,
        Task.creator_id == user_id,
        Task.is_deleted == False
    ).all()

def get_pending_tasks(db: Session, user_id: int):
    return db.query(Task).filter(
        Task.is_completed == False,
        Task.creator_id == user_id,
        Task.is_deleted == False
    ).all()


def create_task(db: Session, task: schemas.TaskCreate, user_id: int):
    db_task = Task(**task.model_dump(), creator_id=user_id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_tasks_by_user(db: Session, user_id: int):
    return db.query(Task).filter(Task.creator_id == user_id).all()

def get_task(db: Session, task_id: int, user_id: int):
    return db.query(Task).filter(Task.id == task_id, Task.creator_id == user_id).first()

def update_task(db: Session, task_id: int, task: schemas.TaskUpdate, user_id: int):
    db_task = get_task(db, task_id, user_id)
    if db_task:
        for key, value in task.dict(exclude_unset=True).items():
            setattr(db_task, key, value)
        db.commit()
        db.refresh(db_task)
    return db_task

def delete_task(db: Session, task_id: int, user_id: int):
    db_task = get_task(db, task_id, user_id)
    if db_task:
        db.delete(db_task)
        db.commit()
    return db_task
