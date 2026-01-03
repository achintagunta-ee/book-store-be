import requests
import logging
from app.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

def send_email(to: str, subject: str, html: str) -> bool:
    payload = {
        "sender": {
            "email": settings.MAIL_FROM,
            "name": settings.STORE_NAME,
        },
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
    }

    headers = {
        "api-key": settings.BREVO_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers=headers,
            timeout=10,
        )

        if response.status_code >= 400:
            logger.error(
                f"Brevo email failed ({response.status_code}): {response.text}"
            )
            return False

        logger.info(f"Brevo email sent to {to}")
        return True

    except Exception as e:
        logger.exception("Brevo email exception")
        return False
