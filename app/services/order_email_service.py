from typing import Optional

from app.models.order import Order
from app.models.user import User
from app.services.email_retry import send_email_with_retry
from app.services.invoice_service import load_invoice_pdf
from app.utils.template import render_template


def send_payment_success_email(
    order: Order,
    user: Optional[User] = None,
):
    """
    Send payment success email.
    - Supports guest + logged-in users
    - Attaches invoice if available
    - NEVER crashes payment flow
    """

    # -----------------------------
    # Load invoice (optional)
    # -----------------------------
    pdf_bytes = load_invoice_pdf(order.id)

    attachments = []
    if pdf_bytes:
        attachments.append(
            (
                f"Invoice_{order.id}.pdf",
                pdf_bytes,
                "application/pdf",
            )
        )

    # -----------------------------
    # Guest order
    # -----------------------------
    if order.placed_by == "guest":
        to_email = order.guest_email
        subject = f"Payment Successful – Order #{order.id}"
        template = "user_emails/guest_user_payment_success.html"

        context = {
            "order": order,
            "guest_name": order.guest_name,
        }

    # -----------------------------
    # Logged-in user order
    # -----------------------------
    else:
        if not user:
            raise ValueError(
                "User must be provided for non-guest payment email"
            )

        to_email = user.email
        subject = f"Payment Successful – Order #{order.id}"
        template = "user_emails/user_payment_success.html"

        context = {
            "order": order,
            "user": user,
        }

    # -----------------------------
    # Send email (with retry)
    # -----------------------------
    send_email_with_retry(
        to_email=to_email,
        subject=subject,
        html=render_template(template, **context),
        attachments=attachments if attachments else None,
    )
