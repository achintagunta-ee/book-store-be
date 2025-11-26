from google.oauth2 import id_token
from google.auth.transport import requests
from app.config import settings
from typing import Dict, Optional

def verify_google_token(token: str) -> Optional[Dict[str, str]]:
    """
    Verify Google ID token and return user info
    Returns None if token is invalid
    """
    try:
        # Verify the token
        id_info = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.google_client_id
        )
        
        # Check if token is for our app
        if id_info['aud'] != settings.google_client_id:
            print("Token audience mismatch")
            return None
        
        return {
            "email": id_info.get("email"),
            "name": id_info.get("name", "Google User"),
            "picture": id_info.get("picture")
        }
    
    except ValueError as e:
        # Token is invalid
        print(f"Google token verification failed: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error during token verification: {str(e)}")
        return None