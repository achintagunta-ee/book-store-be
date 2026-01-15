from app.services.order_email_service import send_payment_success_email

def mark_payment_success(payment, order, user, session):
    payment.status = "success"
    session.commit()

    # 🔔 Trigger email here
    send_payment_success_email(order)
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PaymentGateway:
    def __init__(self):
        # Initialize your payment gateway (Stripe, Razorpay, etc.)
        pass
    
    async def refund(self, payment_id: str, amount: float) -> Dict[str, Any]:
        """Process refund through payment gateway"""
        # Implement actual payment gateway refund logic here
        logger.info(f"Processing refund: {payment_id}, amount: {amount}")
        
        # Placeholder implementation
        return {
            "success": True,
            "reference_id": f"ref_{payment_id}_{int(amount)}",
            "amount": amount,
            "status": "processed"
        }

payment_gateway = PaymentGateway()

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import Session, select

from app.models.payment import Payment
from app.models.order import Order
from app.models.user import User
from app.services.inventory_service import reduce_inventory
from app.services.order_email_service import send_payment_success_email


def finalize_payment(
    session,
    order,
    txn_id,
    amount,
    method,
    payment_mode,
    user=None,
    gateway_order_id=None,
    gateway_signature=None,
):
    # 🔒 IDEMPOTENCY CHECK
    existing_payment = session.exec(
        select(Payment).where(Payment.txn_id == txn_id)
    ).first()

    if existing_payment:
        # ✅ Payment already processed → return safely
        return existing_payment

    # ✅ Create new payment
    payment = Payment(
        order_id=order.id,
        user_id=user.id if user else None,
        txn_id=txn_id,
        amount=amount,
        status="success",
        method=method,
        payment_mode=payment_mode,
    )

    session.add(payment)

    # ✅ Update order ONCE
    order.status = "paid"
    order.gateway_order_id = gateway_order_id
    order.gateway_payment_id = txn_id
    order.gateway_signature = gateway_signature

    session.commit()
    session.refresh(payment)

    return payment