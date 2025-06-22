from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models.user import User
from . import schemas, services

router = APIRouter()

@router.get("/", response_model=schemas.Settings)
def read_user_settings(current_user: User = Depends(get_current_user)):
    """
    Retrieve current user's settings.
    """
    return current_user

@router.put("/", response_model=schemas.Settings)
def update_user_settings(
    settings_update: schemas.SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update user's settings.
    """
    updated_user = services.update_user_settings(db=db, user_id=current_user.id, settings=settings_update)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user
