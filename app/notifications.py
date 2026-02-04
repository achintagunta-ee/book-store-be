# app/notifications/events.py
from enum import Enum

class OrderEvent(str, Enum):
    ORDER_PLACED = "order_placed"
    PAYMENT_SUCCESS = "payment_success"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCEL_REQUESTED = "cancel_requested"
    CANCEL_REJECTED = "cancel_rejected"
    CANCEL_APPROVED = "cancel_approved"
    REFUND_PROCESSED = "refund_processed"
    EBOOK_PURCHASE_CREATED = "ebook_purchase_created"
    EBOOK_PAYMENT_SUCCESS = "ebook_payment_success"
    EBOOK_ACCESS_GRANTED = "ebook_access_granted"
# app/notifications/channels.py
from enum import Enum

class Channel(str, Enum):
    POPUP_USER = "popup_user"
    EMAIL_USER = "email_user"
    EMAIL_ADMIN = "email_admin"
    INAPP_ADMIN = "inapp_admin"
# app/notifications/rules.py


NOTIFICATION_RULES = {
    OrderEvent.ORDER_PLACED: {
        Channel.POPUP_USER: True,
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },
    OrderEvent.PAYMENT_SUCCESS: {
        Channel.POPUP_USER: True,
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },
    OrderEvent.SHIPPED: {
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },
    OrderEvent.DELIVERED: {
        Channel.EMAIL_USER: True,
        Channel.EMAIL_ADMIN: True,
        Channel.INAPP_ADMIN: True,
    },
    OrderEvent.CANCEL_REQUESTED: {
        Channel.EMAIL_USER: True,
        Channel.EMAIL_ADMIN: True,
        Channel.INAPP_ADMIN: True,
    },
    OrderEvent.CANCEL_REJECTED: {
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
    },
    OrderEvent.CANCEL_APPROVED: {
        Channel.EMAIL_USER: True,
        Channel.EMAIL_ADMIN: True,
        Channel.INAPP_ADMIN: True,
    },
    OrderEvent.REFUND_PROCESSED: {
    Channel.EMAIL_USER: True,
    Channel.EMAIL_ADMIN: True,
    Channel.INAPP_ADMIN: True,
},

OrderEvent.EBOOK_PURCHASE_CREATED: {
        Channel.POPUP_USER: True,
        Channel.EMAIL_USER: True,
        Channel.EMAIL_ADMIN: True,
        Channel.INAPP_ADMIN: True,
    },

    OrderEvent.EBOOK_PAYMENT_SUCCESS: {
        Channel.POPUP_USER: True,
        Channel.EMAIL_USER: True,
        Channel.EMAIL_ADMIN: True,
        Channel.INAPP_ADMIN: True,
    },

    OrderEvent.EBOOK_ACCESS_GRANTED: {
        Channel.EMAIL_USER: True,
        Channel.EMAIL_ADMIN: True,
        Channel.INAPP_ADMIN: True,
    },


}
# app/notifications/popup.py
def popup(message: str, type: str = "success"):
    return {
        "popup": {
            "type": type,
            "message": message
        }
    }
# app/notifications/email_handlers.py
from app.services.email_service import send_email
from app.utils.template import render_template
from app.config import settings

def send_user_email(template, subject, user, **ctx):
    html = render_template(template, **ctx)
    send_email(to=user.email, subject=subject, html=html)

def send_admin_email(template, subject, **ctx):
    html = render_template(template, **ctx)
    send_email(to=settings.ADMIN_EMAILS, subject=subject, html=html)
# app/notifications/inapp_handlers.py
from app.routes.admin import create_notification
from app.models.notifications import RecipientRole

def notify_admin(session, title, content, related_id):
    create_notification(
        session=session,
        recipient_role=RecipientRole.admin,
        user_id=None,
        trigger_source="order",
        related_id=related_id,
        title=title,
        content=content
    )
# app/notifications/dispatcher.py


def dispatch_order_event(
    *,
    event: OrderEvent,
    order,
    user,
    session,
    extra: dict | None = None,
    notify_user: bool = True,
    notify_admin: bool = True,
):
    rules = NOTIFICATION_RULES.get(event, {})
    extra = extra or {}

    response_popup = None

    # -------------------------
    # USER POPUP
    # -------------------------
    if notify_user and rules.get(Channel.POPUP_USER):
        response_popup = popup(
            extra.get("popup_message", "Success")
        )

    # -------------------------
    # ADMIN IN-APP
    # -------------------------
    if notify_admin and rules.get(Channel.INAPP_ADMIN):
        create_notification(
        session=session,
        recipient_role=RecipientRole.admin,
        user_id=None,
        trigger_source=event.value,
        related_id=order.id,
        title=extra.get("admin_title", "Order Update"),
        content=extra.get("admin_content", ""),
    )

    # -------------------------
    # USER EMAIL
    # -------------------------
    if notify_user and rules.get(Channel.EMAIL_USER):
        try:
            if user:
                send_user_email(
                    template=extra["user_template"],
                    subject=extra["user_subject"],
                    user=user,
                    **extra,
                )
            else:
                send_email(
                    to=extra.get("user_email"),
                    subject=extra["user_subject"],
                    template=extra["user_template"],
                    context=extra,
                )
        except Exception as e:
            print("User email failed:", e)

    # -------------------------
    # ADMIN EMAIL
    # -------------------------
    if notify_admin and rules.get(Channel.EMAIL_ADMIN):
        try:
            send_admin_email(
                template=extra["admin_template"],
                subject=extra["admin_subject"],
                **extra,
            )
        except Exception as e:
            print("Admin email failed:", e)

    return response_popup