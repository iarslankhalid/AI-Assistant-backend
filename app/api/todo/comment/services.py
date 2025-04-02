from sqlalchemy.orm import Session
from app.db.models.todo.comment import Comment
from . import schemas
from datetime import datetime

def create_comment(db: Session, comment: schemas.CommentCreate, user_id: int):
    db_comment = Comment(**comment.dict(), user_id=user_id, posted_at=datetime.utcnow())
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

def get_comment(db: Session, comment_id: int, user_id: int):
    return db.query(Comment).filter(Comment.id == comment_id, Comment.user_id == user_id).first()

def get_comments_for_task(db: Session, task_id: int, user_id: int):
    return db.query(Comment).filter(Comment.task_id == task_id, Comment.user_id == user_id).all()

def get_comments_for_project(db: Session, project_id: int, user_id: int):
    return db.query(Comment).filter(Comment.project_id == project_id, Comment.user_id == user_id).all()

def update_comment(db: Session, comment_id: int, comment: schemas.CommentUpdate, user_id: int):
    db_comment = get_comment(db, comment_id, user_id)
    if db_comment:
        for key, value in comment.dict(exclude_unset=True).items():
            setattr(db_comment, key, value)
        db.commit()
        db.refresh(db_comment)
    return db_comment

def delete_comment(db: Session, comment_id: int, user_id: int):
    db_comment = get_comment(db, comment_id, user_id)
    if db_comment:
        db.delete(db_comment)
        db.commit()
    return db_comment
