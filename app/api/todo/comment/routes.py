from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from . import schemas, services

router = APIRouter()

@router.post("/", response_model=schemas.CommentOut)
def create_comment(
    comment: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.create_comment(db, comment, current_user.id)

@router.get("/task/{task_id}", response_model=list[schemas.CommentOut])
def get_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.get_comments_for_task(db, task_id, current_user.id)

@router.get("/project/{project_id}", response_model=list[schemas.CommentOut])
def get_project_comments(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.get_comments_for_project(db, project_id, current_user.id)

@router.put("/{comment_id}", response_model=schemas.CommentOut)
def update_comment(
    comment_id: int,
    comment: schemas.CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    updated = services.update_comment(db, comment_id, comment, current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Comment not found")
    return updated

@router.delete("/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    deleted = services.delete_comment(db, comment_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"message": "Comment deleted"}
