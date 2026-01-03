from app.models import order, user
from app.services.email_retry import send_email_with_retry
from app.services.invoice_service import load_invoice_pdf
from app.utils.template import render_template

def send_payment_success_email(order):
    pdf_bytes = load_invoice_pdf(order.id)

    send_email_with_retry(
        to_email=user.email,
    subject=f"Payment Successful - Order #{order.id}",
    html=render_template(
        "emails/user_payment_success.html",
        order=order
    ),
    attachments=[(
        f"Invoice_{order.id}.pdf",
        pdf_bytes,
        "application/pdf"
    )]
)
