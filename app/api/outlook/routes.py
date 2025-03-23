from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.api.outlook.services import get_authorization_url, exchange_code_for_token, save_tokens_to_db
from app.db.models.user import User


router = APIRouter()

@router.get("/outlook/login")
def login_to_outlook():
    return RedirectResponse(get_authorization_url())

@router.get("/outlook/callback")
def outlook_callback(code: str, db: Session = Depends(get_db)):
    
    # ✅ TEMP: hardcoded fallback user (change as needed)
    user = db.query(User).filter_by(email="abc@example.com").first()
    print(f"{user = }")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    print("Exchanging code for token...")
    token_data = exchange_code_for_token(code)
    
    print("exchange_code_for_token:", exchange_code_for_token)


    print("Saving token to DB...")
    save_tokens_to_db(db, user.id, token_data)

    return {
        "message": "✅ Outlook account linked (dev mode)",
        "user_email": user.email
    }
