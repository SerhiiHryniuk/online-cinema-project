import asyncio

from celery import Task
from loguru import logger

from app.core.celery_app import celery_app
from app.notifications.emails import (
    send_activation_complete_email,
    send_activation_email,
    send_password_reset_complete_email,
    send_password_reset_email,
)


@celery_app.task(
    name="app.tasks.emails.send_activation_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_activation_email_task(self: Task, email: str, activation_link: str) -> None:
    try:
        asyncio.run(send_activation_email(email, activation_link))
    except Exception as error:
        logger.error(f"Failed to send activation email to {email}: {error}")
        raise self.retry(exc=error)


@celery_app.task(
    name="app.tasks.emails.send_activation_complete_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_activation_complete_email_task(self: Task, email: str, login_link: str) -> None:
    try:
        asyncio.run(send_activation_complete_email(email, login_link))
    except Exception as error:
        logger.error(f"Failed to send activation-complete email to {email}: {error}")
        raise self.retry(exc=error)


@celery_app.task(
    name="app.tasks.emails.send_password_reset_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_password_reset_email_task(self: Task, email: str, token: str) -> None:
    try:
        asyncio.run(send_password_reset_email(email, token))
    except Exception as error:
        logger.error(f"Failed to send password reset email to {email}: {error}")
        raise self.retry(exc=error)


@celery_app.task(
    name="app.tasks.emails.send_password_reset_complete_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_password_reset_complete_email_task(self: Task, email: str, login_link: str) -> None:
    try:
        asyncio.run(send_password_reset_complete_email(email, login_link))
    except Exception as error:
        logger.error(f"Failed to send password-reset-complete email to {email}: {error}")
        raise self.retry(exc=error)
