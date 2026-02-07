from app.notifications.rules import NOTIFICATION_RULES
from app.notifications.channels import Channel
from app.notifications.popup import popup
from app.notifications.email_handlers import send_user_email, send_admin_email
from app.services.notification_service import create_notification
from app.models.notifications import RecipientRole
from app.notifications.events import OrderEvent


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
    """
    Central notification dispatcher.

    Handles:
    - popup messages
    - user email
    - admin email
    - admin in-app notifications
    """

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
    # ADMIN IN-APP NOTIFICATION
    # -------------------------
    if notify_admin and rules.get(Channel.INAPP_ADMIN):
        create_notification(
            session=session,
            recipient_role=RecipientRole.admin,
            user_id=None,
            trigger_source=event.value,
            related_id=getattr(order, "id", None),
            title=extra.get("admin_title", "Order Update"),
            content=extra.get("admin_content", ""),
        )
        session.commit()

    # -------------------------
    # USER EMAIL
    # -------------------------
    if notify_user and rules.get(Channel.EMAIL_USER) and user:
        try:
            send_user_email(
                template=extra["user_template"],
                subject=extra["user_subject"],
                user=user,
                **extra,
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
