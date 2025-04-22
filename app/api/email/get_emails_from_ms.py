import requests
from fastapi import HTTPException
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models.outlook_credentials import OutlookCredentials
from app.api.auth.services import refresh_token

GRAPH_API_URL = "https://graph.microsoft.com/v1.0/me/messages"

def _headers(access_token: str):
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

def fetch_user_emails_from_ms(user_id: int, db: Session, limit: int = 50, last_refreshed=None):
    # Refresh token if needed and get access token
    access_token = refresh_token(user_id, db)

    params = {
        "$top": limit,
        "$orderby": "receivedDateTime DESC",
    }

    # Optional: filter by last refresh time
    if last_refreshed:
        if last_refreshed.tzinfo is None:
            last_refreshed = last_refreshed.replace(tzinfo=timezone.utc)
        last_refreshed = last_refreshed.replace(microsecond=0)

        iso_timestamp = last_refreshed.isoformat()
        params["$filter"] = f"receivedDateTime gt {iso_timestamp}"

    response = requests.get(GRAPH_API_URL, headers=_headers(access_token), params=params)

    if response.status_code != 200:
        print("❌ Email fetch failed:", response.text)
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch emails")

    data = response.json()
    emails = data.get("value", [])
    next_page = data.get("@odata.nextLink")

    return {
        "emails": emails,
        "@odata.nextLink": next_page
    }
