import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import settings


def send_password_reset_email(recipient: str, token: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Reset your NSS BloodConnect password"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password#{urlencode({'token': token})}"
    message.set_content(
        "A password reset was requested for your NSS BloodConnect account.\n\n"
        f"Use this single-use link within {settings.password_reset_token_expire_minutes} minutes:\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
