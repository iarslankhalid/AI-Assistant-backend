from sqlalchemy.orm import Session
from app.db.models.todo.task_label import TaskLabel

def assign_label_to_task(db: Session, task_id: int, label_id: int):
    # Prevent duplicates
    existing = db.query(TaskLabel).filter_by(task_id=task_id, label_id=label_id).first()
    if existing:
        return existing

    task_label = TaskLabel(task_id=task_id, label_id=label_id)
    db.add(task_label)
    db.commit()
    db.refresh(task_label)
    return task_label

def remove_label_from_task(db: Session, task_id: int, label_id: int):
    task_label = db.query(TaskLabel).filter_by(task_id=task_id, label_id=label_id).first()
    if task_label:
        db.delete(task_label)
        db.commit()
    return task_label
