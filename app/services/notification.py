import logging
from typing import Optional, Dict, Any, List
from sqlmodel import Session, select
from app.models import User, Notification
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

async def send_push_to_admins(title: str, body: str, data: Optional[Dict[str, Any]] = None):
    """Send push notification to admin devices"""
    logger.info(f"Push to admins: {title} - {body}")
    # Implement Firebase/APNS here if needed

async def notify_customer_refund_processed(
    db: Session,
    order_id: int,
    customer_email: str,
    refund_amount: float,
    refund_method: str,
    refund_reference: str
):
    """Notify customer about refund processing"""
    # Create notification in database
    notification = Notification(
        title="Refund Processed",
        message=f"Your refund of ${refund_amount} for order #{order_id} has been processed",
        type="refund_processed",
        priority="normal"
    )
    db.add(notification)
    db.commit()
    
    # Send email
    await send_email(
        to_email=customer_email,
        subject="Your Refund Has Been Processed",
        template_name="refund_processed",
        context={
            "order_id": order_id,
            "refund_amount": refund_amount,
            "refund_method": refund_method,
            "refund_reference": refund_reference
        }
    )

async def notify_admin_cancellation_request(
    db: Session,
    order_id: int,
    customer_name: str,
    amount: float,
    reason: str
):
    """Notify admins about cancellation request"""
    # Get all admin users
    statement = select(User).where(User.is_admin == True)
    admins = db.exec(statement).all()
    
    for admin in admins:
        notification = Notification(
            user_id=admin.id,
            type="cancellation_request",
            title=f"Cancellation Request - Order #{order_id}",
            message=f"{customer_name} requested cancellation for order #{order_id}",
            priority="high"
        )
        notification.set_data({
            "order_id": order_id,
            "customer": customer_name,
            "amount": amount,
            "reason": reason
        })
        db.add(notification)
    
    db.commit()
    
    # Send email to admins
    admin_emails = [admin.email for admin in admins]
    await send_email(
        to_email=admin_emails,
        subject=f"📋 New Cancellation Request - Order #{order_id}",
        template_name="cancellation_request",
        context={
            "order_id": order_id,
            "customer": customer_name,
            "amount": amount,
            "reason": reason
        }
    )