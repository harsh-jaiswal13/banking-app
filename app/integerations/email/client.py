import smtplib
import ssl
import logging
from email.message import EmailMessage
from typing import Optional, List
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from app.integerations.email.templates import *
import anyio  # for async thread-safe execution

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Custom exception for email sending failures."""
    pass


BASE_DIR = Path(__file__).resolve().parent.parent.parent
template_env = Environment(
    loader=FileSystemLoader(BASE_DIR / "integerations/email/templates"),
    autoescape=True
)

async def render_email(template_name: str, context: dict) -> str:
    template = template_env.get_template(template_name)
    return template.render(**context)


async def send_email(
    *,
    smtp_server: str,
    smtp_port: int,
    sender_email: str,
    app_password: str,
    recipients: List[str],
    subject: str,
    text_content: str,
    html_content: Optional[str] = None,
    timeout: int = 10,
) -> bool:
    """
    Asynchronously send an email using SMTP with TLS encryption.

    This uses a thread-safe wrapper around the blocking smtplib call.
    """

    if not recipients:
        raise ValueError("Recipient list cannot be empty.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_content)

    if html_content:
        msg.add_alternative(html_content, subtype="html")

    context = ssl.create_default_context()

    def _send_sync():
        try:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=timeout) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(sender_email, app_password)
                server.send_message(msg)

            logger.info("Email sent successfully to %s", recipients)
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.exception("SMTP authentication failed")
            raise EmailSendError("Authentication failed") from e

        except smtplib.SMTPException as e:
            logger.exception("SMTP error occurred")
            raise EmailSendError("SMTP error occurred") from e

        except Exception as e:
            logger.exception("Unexpected error while sending email")
            raise EmailSendError("Unexpected email sending failure") from e

    # Run the blocking SMTP send in a thread (async-safe)
    return await anyio.to_thread.run_sync(_send_sync)