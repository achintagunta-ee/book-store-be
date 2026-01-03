from app.services.order_email_service import send_payment_success_email

def mark_payment_success(payment, order, user, session):
    payment.status = "success"
    session.commit()

    # 🔔 Trigger email here
    send_payment_success_email(order)
