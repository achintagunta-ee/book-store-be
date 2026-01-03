from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.models.order import Order
from app.models.payment import Payment
from app.models.user import User
from app.services.order_email_service import send_payment_success_email
from app.utils.template import render_template
from app.utils.token import get_current_admin
from app.config import settings

router=APIRouter()

from app.services.invoice_service import load_invoice_pdf
from app.services.email_retry import send_email_with_retry

@router.post("/dev/payments/{payment_id}/mark-success")
def mark_payment_success_dev(
    payment_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_admin)
):
    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")

    if payment.status == "success":
        return {"message": "Already successful"}

    payment.status = "success"
    session.commit()

    order = session.get(Order, payment.order_id)
    user = session.get(User, order.user_id)

    # load invoice
    pdf_path = f"invoices/invoice_{order.id}.pdf"
    pdf_bytes = open(pdf_path, "rb").read()

    html = render_template(
        "user_emails/user_payment_success.html",
        order=order,
        user=user
    )

    # user email
    send_email_with_retry(
        to_email=user.email,
        subject=f"Payment Successful – Order #{order.id}",
        html=html,
        attachments=[(
            f"Invoice_{order.id}.pdf",
            pdf_bytes,
            "application/pdf"
        )]
    )

    # admin email
    for admin_email in settings.ADMIN_EMAILS:
        send_email_with_retry(
            to_email=admin_email,
            subject=f"Payment Received – Order #{order.id}",
            html=html
        )

    return {"message": "Payment marked success & emails sent"}
