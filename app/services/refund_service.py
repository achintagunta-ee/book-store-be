from sqlmodel import Session
from app.models.payment import Payment
from app.models.order import Order
from app.services.inventory_service import restore_inventory
from app.services.payment_service import payment_gateway


async def refund_payment(
    *,
    session: Session,
    payment: Payment,
    order: Order,
    amount: float,
):
    if payment.status == "refunded":
        raise ValueError("Payment already refunded")

    # Call gateway
    result = await payment_gateway.refund(payment.txn_id, amount)

    if not result["success"]:
        raise Exception("Refund failed")

    # Restore inventory
    restore_inventory(session, order.id)

    # Update states
    payment.status = "refunded"
    order.status = "refunded"

    session.commit()

    return result
