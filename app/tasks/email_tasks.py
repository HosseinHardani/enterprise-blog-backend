"""
Background email tasks. Kept thin -- all the templating logic lives in
app.services.email_service so it's reusable and unit-testable without Celery.
"""

import logging

from app.services.email_service import build_password_reset_email, build_verification_email, send_email
from app.tasks.celery_app import celery_app

logger = logging.getLogger("blog_api.tasks")


@celery_app.task(
    name="send_verification_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def send_verification_email_task(self, to: str, token: str) -> None:
    subject, html = build_verification_email(token)
    send_email(to=to, subject=subject, html_body=html)


@celery_app.task(
    name="send_password_reset_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
)
def send_password_reset_email_task(self, to: str, token: str) -> None:
    subject, html = build_password_reset_email(token)
    send_email(to=to, subject=subject, html_body=html)


@celery_app.task(name="send_notification_email")
def send_notification_email_task(to: str, subject: str, message: str) -> None:
    html = f"<p>{message}</p>"
    send_email(to=to, subject=subject, html_body=html, text_body=message)
