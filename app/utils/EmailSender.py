import smtplib
import ssl
import logging
from email.message import EmailMessage
from typing import Optional, List

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Custom exception for email sending failures."""
    pass


def send_email(
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
    Send an email using SMTP with TLS encryption.

    Args:
        smtp_server: SMTP host (e.g., smtp.gmail.com)
        smtp_port: SMTP port (usually 587 for TLS)
        sender_email: Sender email address
        app_password: App password or SMTP password
        recipients: List of recipient email addresses
        subject: Email subject
        text_content: Plain text content
        html_content: Optional HTML content
        timeout: Connection timeout in seconds

    Returns:
        bool: True if sent successfully

    Raises:
        EmailSendError: If email fails to send
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