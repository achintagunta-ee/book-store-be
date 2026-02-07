from app.services.email_service import send_email
from app.utils.template import render_template
from app.config import settings


def send_user_email(template, subject, user, **ctx):
    html = render_template(template, **ctx)
    send_email(to=user.email, subject=subject, html=html)


def send_admin_email(template, subject, **ctx):
    html = render_template(template, **ctx)
    send_email(to=settings.ADMIN_EMAILS, subject=subject, html=html)
