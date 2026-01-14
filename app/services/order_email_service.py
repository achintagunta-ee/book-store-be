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
    Send payment success email with invoice attachment
    Supports both guest and logged-in users
    """

    # -----------------------------
    # Load invoice PDF (shared)
    # -----------------------------
    pdf_bytes = load_invoice_pdf(order.id)

    # -----------------------------
    # Decide recipient + template
    # -----------------------------
    if order.placed_by == "guest":
        to_email = order.guest_email
        template = "emails/guest_payment_success.html"
        subject = f"Payment Successful – Order #{order.id}"

        context = {
            "order": order,
            "guest_name": order.guest_name,
        }

    else:
        if not user:
            raise ValueError(
                "User must be provided for non-guest payment email"
            )

        to_email = user.email
        template = "emails/user_payment_success.html"
        subject = f"Payment Successful – Order #{order.id}"

        context = {
            "order": order,
            "user": user,
        }

    # -----------------------------
    # Send email with attachment
    # -----------------------------
    send_email_with_retry(
        to_email=to_email,
        subject=subject,
        html=render_template(template, **context),
        attachments=[
            (
                f"Invoice_{order.id}.pdf",
                pdf_bytes,
                "application/pdf",
            )
        ],
    )
