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