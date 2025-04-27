import requests
from datetime import datetime, timedelta
from fastapi import HTTPException
from urllib.parse import urlencode

from app.config import settings
from app.db.models.outlook_credentials import OutlookCredentials
from sqlalchemy.orm import Session

AUTHORITY_URL = "https://login.microsoftonline.com/common/oauth2/v2.0"
AUTHORIZATION_URL = f"{AUTHORITY_URL}/authorize"
TOKEN_URL = f"{AUTHORITY_URL}/token"

SCOPE = "offline_access Mail.Read Mail.Send Mail.ReadWrite User.Read"

CLIENT_ID = settings.OUTLOOK_CLIENT_ID
CLIENT_SECRET = settings.OUTLOOK_CLIENT_SECRET
REDIRECT_URI = settings.OUTLOOK_REDIRECT_URI


def get_authorization_url() -> str:
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": SCOPE,
        "prompt": "select_account",
    }
    return f"{AUTHORIZATION_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    response = requests.post(TOKEN_URL, data=data)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {response.text}")

    return response.json()


def refresh_token(user_id: int, db: Session) -> str:
    """Refreshes the user's Outlook token if expired and returns a valid access token."""

    creds = db.query(OutlookCredentials).filter_by(user_id=user_id).first()

    if not creds:
        raise HTTPException(status_code=404, detail="Outlook credentials not found")

    # If not expired, return current token
    if creds.expires_at > datetime.now():
        return creds.access_token

    print("[INFO] --> Token expired — refreshing...")

    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    data = {
        "client_id": settings.OUTLOOK_CLIENT_ID,
        "client_secret": settings.OUTLOOK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": creds.refresh_token,
        "redirect_uri": settings.OUTLOOK_REDIRECT_URI,
        "scope": "offline_access Mail.Read Mail.Send Mail.ReadWrite User.Read"
    }

    response = requests.post(token_url, data=data)

    if response.status_code != 200:
        print("[ERROR] Failed to refresh token:", response.text)  # 👈 ADD THIS
        raise HTTPException(status_code=401, detail="Failed to refresh access token")


    token_data = response.json()

    # Update DB
    creds.access_token = token_data["access_token"]
    creds.refresh_token = token_data.get("refresh_token", creds.refresh_token)
    creds.expires_at = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))
    creds.updated_at = datetime.now()

    db.commit()
    db.refresh(creds)

    return creds.access_token


def save_tokens_to_db(db: Session, user_id: int, token_data: dict):
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    token = db.query(OutlookCredentials).filter_by(user_id=user_id).first()

    if not token:
        token = OutlookCredentials(user_id=user_id)
        db.add(token)

    token.access_token = token_data["access_token"]
    token.refresh_token = token_data.get("refresh_token")
    token.token_type = token_data.get("token_type")
    token.scope = token_data.get("scope")
    token.expires_at = expires_at

    db.commit()


def get_user_info_from_graph(access_token: str) -> dict:
    url = "https://graph.microsoft.com/v1.0/me"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to fetch user info: {response.text}")

    return response.json()
