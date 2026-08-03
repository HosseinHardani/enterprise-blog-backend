"""
Minimal SMTP email sender. In production this is normally invoked from a
Celery task (see app/tasks/email_tasks.py) so the request/response cycle
never blocks on SMTP I/O.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("blog_api.email")


def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to
    message.set_content(text_body or "Please view this email in an HTML-compatible client.")
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_TLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        logger.info("Email sent to %s: %s", to, subject)
    except Exception:
        # Never let an email failure surface as a 500 to the caller - the
        # calling service should already have committed the DB state.
        logger.exception("Failed to send email to %s", to)


def build_verification_email(token: str) -> tuple[str, str]:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    subject = "Verify your email address"
    html = f"""
    <p>Welcome! Please verify your email address by clicking the link below:</p>
    <p><a href="{link}">Verify my email</a></p>
    <p>This link expires in 24 hours. If you didn't create an account, ignore this email.</p>
    """
    return subject, html


def build_password_reset_email(token: str) -> tuple[str, str]:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    subject = "Reset your password"
    html = f"""
    <p>We received a request to reset your password. Click the link below to choose a new one:</p>
    <p><a href="{link}">Reset my password</a></p>
    <p>This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>
    """
    return subject, html
