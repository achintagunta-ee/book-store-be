import base64
import logging
import requests
import re
from typing import List, Optional, Tuple

from app.config import settings
from app.utils.template import render_template
from app.models.user import User
from app.models.order import Order
from sqlmodel import Session

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

def is_valid_email(email):
    if isinstance(email, list):
        return all(is_valid_email(e) for e in email)

    if not email:
        return False

    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None


def send_email(
    to: str,
    subject: str,
    html: str,
    attachments: Optional[List[Tuple[str, bytes, str]]] = None,
) -> bool:
    """
    Send email via Brevo.

    attachments: List of tuples
        (filename, file_bytes, mime_type)
    """

    # ✅ Validate email BEFORE calling Brevo
    # ✅ Normalize emails into a list
    if isinstance(to, list):
        valid_emails = [e for e in to if is_valid_email(e)]
    else:
        valid_emails = [to] if is_valid_email(to) else []

    if not valid_emails:
        logger.warning(f"No valid emails found: {to}")
        return False
    
    payload = {
        "sender": {
            "email": settings.MAIL_FROM,
            "name": settings.STORE_NAME,
        },
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
    }

    # ✅ Attach files if provided
    if attachments:
        payload["attachment"] = [
            {
                "name": filename,
                "content": base64.b64encode(file_bytes).decode("utf-8"),
            }
            for filename, file_bytes, mime_type in attachments
        ]

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

        logger.info(f"Brevo email sent to {valid_emails}")
        return True

    except Exception:
        logger.exception("Brevo email exception")
        return False


def send_order_confirmation(order: Order, user: User, session: Session):
    """Send order confirmation email to customer"""
    html = render_template(
        "user_emails/user_order_confirmation.html",
        order=order,
        user=user
    )

    send_email(
        to=user.email,
        subject=f"Order Confirmed #{order.id}",
        html=html
    )
    
    # Send to admin emails (if configured)
    from app.config import settings
    if hasattr(settings, "ADMIN_EMAILS"):
        send_email(
        to=settings.ADMIN_EMAILS,
        subject=f"New Order Received #{order.id}",
        html=html
    )
