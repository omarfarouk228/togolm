"""E-mail sending over SMTP, with the same settings as the showcase's sign-in
e-mails (EMAIL_SERVER_HOST / PORT / USER / PASSWORD, EMAIL_FROM)."""

import os
import smtplib
from email.message import EmailMessage


def email_configured() -> bool:
    return bool(os.getenv("EMAIL_SERVER_HOST") and os.getenv("EMAIL_FROM"))


def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    message = EmailMessage()
    message["From"] = os.environ["EMAIL_FROM"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    host = os.environ["EMAIL_SERVER_HOST"]
    port = int(os.getenv("EMAIL_SERVER_PORT", "587"))
    user, password = os.getenv("EMAIL_SERVER_USER"), os.getenv("EMAIL_SERVER_PASSWORD")
    smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with smtp_class(host, port, timeout=30) as smtp:
        if port != 465:
            smtp.starttls()
        if user:
            smtp.login(user, password or "")
        smtp.send_message(message)
