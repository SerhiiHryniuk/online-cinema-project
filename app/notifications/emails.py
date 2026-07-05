from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from app.core.config import settings
from app.exceptions import BaseEmailError

_env = Environment(loader=FileSystemLoader(settings.EMAIL_TEMPLATE_DIR))


async def _send_email(recipient: str, subject: str, html_content: str) -> None:
    message = MIMEMultipart()
    message["From"] = settings.EMAIL_HOST_USER
    message["To"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(html_content, "html"))

    try:
        smtp = aiosmtplib.SMTP(
            hostname=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            start_tls=settings.EMAIL_USE_TLS,
        )
        await smtp.connect()
        if settings.EMAIL_USE_TLS:
            await smtp.starttls()
        await smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        await smtp.sendmail(settings.EMAIL_HOST_USER, [recipient], message.as_string())
        await smtp.quit()
    except aiosmtplib.SMTPException as error:
        logger.error(f"Failed to send email to {recipient}: {error}")
        raise BaseEmailError(f"Failed to send email to {recipient}: {error}")


async def send_activation_email(email: str, activation_link: str) -> None:
    template = _env.get_template(settings.ACTIVATION_EMAIL_TEMPLATE_NAME)
    html_content = template.render(email=email, activation_link=activation_link)
    await _send_email(email, "Account Activation", html_content)


async def send_activation_complete_email(email: str, login_link: str) -> None:
    template = _env.get_template(settings.ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME)
    html_content = template.render(email=email, login_link=login_link)
    await _send_email(email, "Account Activated Successfully", html_content)


async def send_password_reset_email(email: str, token: str) -> None:
    template = _env.get_template(settings.PASSWORD_EMAIL_TEMPLATE_NAME)
    html_content = template.render(email=email, token=token)
    await _send_email(email, "Password Reset Request", html_content)


async def send_password_reset_complete_email(email: str, login_link: str) -> None:
    template = _env.get_template(settings.PASSWORD_COMPLETE_EMAIL_TEMPLATE_NAME)
    html_content = template.render(email=email, login_link=login_link)
    await _send_email(email, "Your Password Has Been Successfully Reset", html_content)
