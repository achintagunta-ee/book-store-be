from enum import Enum


class Channel(str, Enum):
    POPUP_USER = "popup_user"
    EMAIL_USER = "email_user"
    EMAIL_ADMIN = "email_admin"
    INAPP_ADMIN = "inapp_admin"
