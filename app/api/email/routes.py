from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.outlook_credentials import OutlookCredentials
from app.api.email.services import fetch_user_emails

router = APIRouter()

@router.get("/inbox")
def get_inbox_emails(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    outlook_creds = db.query(OutlookCredentials).filter_by(user_id=current_user.id).first()

    if not outlook_creds:
        raise HTTPException(status_code=400, detail="Outlook account not linked")

    if outlook_creds.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Access token expired. Please re-authenticate.")

    emails = fetch_user_emails(current_user.id, db)
    return {"emails": emails}
