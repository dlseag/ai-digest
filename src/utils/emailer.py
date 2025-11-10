from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


def send_digest_email(
    report_path: Path,
    subject: str,
    recipients: Iterable[str],
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    sender: Optional[str] = None,
    body_text: Optional[str] = None,
) -> None:
    """Send the generated digest report via SMTP."""

    recipients = [addr.strip() for addr in recipients if addr and addr.strip()]
    if not recipients:
        raise ValueError("No email recipients provided")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender or smtp_user
    message["To"] = ", ".join(recipients)

    if body_text is None:
        body_text = report_path.read_text(encoding="utf-8")

    message.set_content(body_text, subtype="plain", charset="utf-8")

    # Attach the markdown report for convenience
    try:
        attachment_bytes = report_path.read_bytes()
        message.add_attachment(
            attachment_bytes,
            maintype="text",
            subtype="markdown",
            filename=report_path.name,
        )
    except Exception as exc:  # pragma: no cover - attachment is optional
        logger.warning("附加报告文件失败，将仅发送正文: %s", exc)

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        with server:
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        logger.info("✓ 邮件已发送至 %s", ", ".join(recipients))
    except Exception as exc:
        logger.error("发送简报邮件失败: %s", exc)
        raise
