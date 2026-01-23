from functools import lru_cache
import time
from sqlmodel import select
from app.database import get_session
from app.models.cart import CartItem
from app.models.address import Address
from app.models.payment import Payment

CACHE_TTL = 60 * 60  # 60 minutes

def _ttl_bucket():
    return int(time.time() // CACHE_TTL)


@lru_cache(maxsize=512)
def cached_addresses(user_id: int, bucket: int):
    with next(get_session()) as session:
        return session.exec(
            select(Address).where(Address.user_id == user_id)
        ).all()


@lru_cache(maxsize=512)
def cached_address_and_cart(user_id: int, bucket: int):
    with next(get_session()) as session:
        addresses = session.exec(
            select(Address).where(Address.user_id == user_id)
        ).all()
        cart = session.exec(
            select(CartItem).where(CartItem.user_id == user_id)
        ).all()
        return {"addresses": addresses, "cart": cart}


@lru_cache(maxsize=512)
def cached_my_payments(user_id: int, bucket: int):
    with next(get_session()) as session:
        return session.exec(
            select(Payment).where(Payment.user_id == user_id)
        ).all()
@lru_cache(maxsize=256)
def cached_payment_detail(payment_id: int, user_id: int, bucket: int):
    from app.database import get_session
    from app.models.payment import Payment
    from app.models.user import User
    from sqlmodel import select

    with next(get_session()) as session:
        result = session.exec(
            select(Payment, User)
            .join(User, User.id == Payment.user_id)
            .where(Payment.id == payment_id)
        ).first()

        if not result:
            return None

        payment, user = result

        if user.id != user_id:
            return None

        return {
            "payment_id": payment.id,
            "txn_id": payment.txn_id,
            "order_id": payment.order_id,
            "amount": payment.amount,
            "status": payment.status,
            "method": payment.method,
            "customer": {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
            },
            "created_at": payment.created_at,
        }
