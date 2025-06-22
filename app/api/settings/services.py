from sqlalchemy.orm import Session
from app.db.models.user import User
from . import schemas

def update_user_settings(db: Session, user_id: int, settings: schemas.SettingsUpdate) -> User:
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user:
        update_data = settings.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user
