from sqlalchemy.orm import Session
from app.db.models.todo.label import Label
from . import schemas

def create_label(db: Session, label: schemas.LabelCreate, user_id: int):
    db_label = Label(**label.dict(), user_id=user_id)
    db.add(db_label)
    db.commit()
    db.refresh(db_label)
    return db_label

def get_labels(db: Session, user_id: int):
    return db.query(Label).filter(Label.user_id == user_id).all()

def get_label(db: Session, label_id: int, user_id: int):
    return db.query(Label).filter(Label.id == label_id, Label.user_id == user_id).first()

def update_label(db: Session, label_id: int, label: schemas.LabelUpdate, user_id: int):
    db_label = get_label(db, label_id, user_id)
    if db_label:
        for key, value in label.dict(exclude_unset=True).items():
            setattr(db_label, key, value)
        db.commit()
        db.refresh(db_label)
    return db_label

def delete_label(db: Session, label_id: int, user_id: int):
    db_label = get_label(db, label_id, user_id)
    if db_label:
        db.delete(db_label)
        db.commit()
    return db_label
