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
from sqlmodel import Session

from app.models.payment import Payment
from app.models.order import Order
from app.models.user import User
from app.services.inventory_service import reduce_inventory
from app.services.order_email_service import send_payment_success_email


def finalize_payment(
    *,
    session: Session,
    order: Order,
    txn_id: str,
    amount: float,
    method: str,
    payment_mode: str,
    user: Optional[User] = None,
    gateway_order_id: Optional[str] = None,
    gateway_signature: Optional[str] = None,
    gateway_response: Optional[Dict[str, Any]] = None,
) -> Payment:
    """
    Single source of truth for completing payments
    """

    if order.status == "paid":
        raise ValueError("Order already paid")

    payment = Payment(
        order_id=order.id,
        user_id=user.id if user else None,
        txn_id=txn_id,
        amount=amount,
        status="success",
        method=method,
        payment_mode=payment_mode,
        gateway_order_id=gateway_order_id,
        gateway_signature=gateway_signature,
        gateway_response=gateway_response,
        created_at=datetime.utcnow(),
    )

    session.add(payment)

    # 🔒 Atomic state change
    order.status = "paid"

    # 📦 Reduce inventory ONCE
    reduce_inventory(session, order.id)

    session.commit()
    session.refresh(payment)

    # 📧 Email (guest OR user)
    send_payment_success_email(order,user)

    return payment
