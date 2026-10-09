"""The `smtp` mail adapter: the provider's relay over STARTTLS (port 587)."""

import smtplib
import ssl
from email.message import EmailMessage

from ..config import get_settings


def send(msg) -> None:
    settings = get_settings()
    email = EmailMessage()
    email["From"] = msg.sender
    email["To"] = msg.to
    email["Subject"] = msg.subject
    if msg.reply_to:
        email["Reply-To"] = msg.reply_to
    email.set_content(msg.text)
    email.add_alternative(msg.html, subtype="html")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as conn:
        conn.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            conn.login(settings.smtp_user, settings.smtp_password)
        conn.send_message(email)
