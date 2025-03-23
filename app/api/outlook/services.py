import requests
import json
from datetime import datetime, timedelta
from ...config import settings
from ...db.models.outlook_token import OutlookToken
from fastapi import HTTPException
from urllib.parse import urlencode

AUTHORITY_URL = "https://login.microsoftonline.com/common/oauth2/v2.0"
AUTHORIZATION_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
SCOPE = "https://graph.microsoft.com/.default offline_access Mail.ReadWrite Mail.Send"

CLIENT_ID = settings.OUTLOOK_CLIENT_ID
CLIENT_SECRET = settings.OUTLOOK_CLIENT_SECRET
REDIRECT_URI = settings.OUTLOOK_REDIRECT_URI

def get_authorization_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": "offline_access Mail.Read Mail.Send Mail.ReadWrite",
        "prompt": "select_account",
    }
    return f"{AUTHORIZATION_URL}?{urlencode(params)}"

def exchange_code_for_token(code: str):
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    
    response = requests.post(TOKEN_URL, data=data)
    
    if response.status_code != 200:
        raise Exception(f"Error fetching token: {response.json()}")
    
    return response.json()

def save_tokens_to_db(db, user_id: str, token_data: dict):
    expires_in = token_data.get("expires_in")
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    token = db.query(OutlookToken).filter_by(user_id=user_id).first()
    if not token:
        token = OutlookToken(user_id=user_id)
        db.add(token)

    token.access_token = token_data["access_token"]
    token.refresh_token = token_data["refresh_token"]
    token.expires_at = expires_at

    db.commit()
