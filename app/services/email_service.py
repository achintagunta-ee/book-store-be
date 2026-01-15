import base64
import logging
import requests
from typing import List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


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

        logger.info(f"Brevo email sent to {to}")
        return True

    except Exception:
        logger.exception("Brevo email exception")
        return False
from app.services.email_service import send_email
from app.utils.template import render_template
from app.models.user import User
from app.models.order import Order
from sqlmodel import Session

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
    if hasattr(settings, 'ADMIN_EMAILS'):
        for admin_email in settings.ADMIN_EMAILS:
            send_email(
                to=admin_email,
                subject=f"New Order Received #{order.id}",
                html=html
            )