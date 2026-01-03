import time
import random
import logging
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

def send_email_with_retry(
    to_email: str,
    subject: str,
    html: str,
    attachments=None,
    max_retries: int = 3
):
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            send_email(
                to=to_email,
                subject=subject,
                html=html,
                attachments=attachments
            )
            logger.info(f"Email sent to {to_email} (attempt {attempt})")
            return True

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Attempt {attempt} failed: {last_error}")

            if "api-key" in last_error.lower():
                break  # auth error → no retry

            sleep = (2 ** attempt) + random.random()
            time.sleep(sleep)

    logger.error(f"Email permanently failed: {last_error}")
    return False
