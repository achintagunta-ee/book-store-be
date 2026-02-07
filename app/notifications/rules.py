from app.notifications.events import OrderEvent
from app.notifications.channels import Channel


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
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },

    OrderEvent.CANCEL_REQUESTED: {
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },

    OrderEvent.CANCEL_REJECTED: {
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
    },

    OrderEvent.CANCEL_APPROVED: {
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },

    OrderEvent.REFUND_PROCESSED: {
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },

    OrderEvent.EBOOK_PURCHASE_CREATED: {
        Channel.POPUP_USER: True,
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },

    OrderEvent.EBOOK_PAYMENT_SUCCESS: {
        Channel.POPUP_USER: True,
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },

    OrderEvent.EBOOK_ACCESS_GRANTED: {
        Channel.EMAIL_USER: True,
        Channel.INAPP_ADMIN: True,
        Channel.EMAIL_ADMIN: True,
    },

}
