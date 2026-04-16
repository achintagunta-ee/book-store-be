# app/utils/google_auth.py

from google.oauth2 import id_token
from app.config import settings
from google.auth.transport import requests

def verify_google_token(token: str):
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )
        return idinfo
    except ValueError as e:
        print("Token validation failed:", e)  # This will tell you exactly why
        return None