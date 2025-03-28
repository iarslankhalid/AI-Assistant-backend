from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.todo import schemas, services
from app.db.session import get_db

router = APIRouter()

@router.post("/", response_model=schemas.ToDoOut)
def create_todo(todo: schemas.ToDoCreate, db: Session = Depends(get_db)):
    user_id = 1  # Replace with real user ID from auth
    return services.create_todo(db, todo, user_id)

@router.get("/", response_model=list[schemas.ToDoOut])
def list_todos(db: Session = Depends(get_db)):
    user_id = 1  # Replace with real user ID from auth
    return services.get_user_todos(db, user_id)
