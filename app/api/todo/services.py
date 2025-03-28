from sqlalchemy.orm import Session
from app.db.models.todo import ToDo
from app.api.todo import schemas

def create_todo(db: Session, todo: schemas.ToDoCreate, user_id: int):
    db_todo = ToDo(**todo.dict(), user_id=user_id)
    db.add(db_todo)
    db.commit()
    db.refresh(db_todo)
    return db_todo

def get_user_todos(db: Session, user_id: int):
    return db.query(ToDo).filter(ToDo.user_id == user_id).all()
