from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.session import get_db
from app.db.models.user import User
from app.db.models.outlook_credentials import OutlookCredentials
from app.api.auth.schemas import UserCreate, Token
from app.core.hashing import Hasher
from app.core.security import create_access_token, get_current_user
from app.api.auth.services import (
    get_authorization_url,
    exchange_code_for_token,
    save_tokens_to_db,
    get_user_info_from_graph,  # make sure this exists
)

router = APIRouter()


@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user.email,
        hashed_password=Hasher.hash_password(user.password),
        auth_provider="local"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully"}


@router.post("/login", response_model=Token)
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not Hasher.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/outlook/login")
def login_to_outlook():
    return RedirectResponse(get_authorization_url())


@router.get("/outlook/callback")
def outlook_callback(code: str, db: Session = Depends(get_db)):
    # Step 1: Exchange code for token
    token_data = exchange_code_for_token(code)

    # Step 2: Use access token to get user info
    user_info = get_user_info_from_graph(token_data["access_token"])
    email = user_info.get("mail") or user_info.get("userPrincipalName")
    provider_user_id = user_info.get("id")
    name = user_info.get("displayName")

    # Step 3: Check if user exists
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            name=name,
            hashed_password=None,
            auth_provider="outlook",
            provider_user_id=provider_user_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Step 4: Save tokens
    expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])

    outlook_creds = db.query(OutlookCredentials).filter_by(user_id=user.id).first()
    if outlook_creds:
        outlook_creds.access_token = token_data["access_token"]
        outlook_creds.refresh_token = token_data.get("refresh_token")
        outlook_creds.token_type = token_data["token_type"]
        outlook_creds.scope = token_data["scope"]
        outlook_creds.expires_at = expires_at
    else:
        outlook_creds = OutlookCredentials(
            user_id=user.id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data["token_type"],
            scope=token_data["scope"],
            expires_at=expires_at,
        )
        db.add(outlook_creds)

    db.commit()

    # Step 5: Issue your app's token
    jwt_token = create_access_token({"sub": user.email})
    return {"access_token": jwt_token, "token_type": "bearer"}


@router.get("/debug/users")
def get_all_users(db: Session = Depends(get_db)):
    return db.query(User).all()
