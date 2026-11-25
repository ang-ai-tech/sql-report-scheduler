"""Send the report by e-mail through any SMTP server (Mailpit for local tests)."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class SmtpSettings:
    host: str = "localhost"
    port: int = 1025
    sender: str = "reports@example.com"
    user: str = ""
    password: str = ""
    starttls: bool = False

    @classmethod
    def from_env(cls) -> SmtpSettings:
        """Read the SMTP settings from environment variables (see .env.example)."""
        return cls(
            host=os.environ.get("SMTP_HOST", "localhost"),
            port=int(os.environ.get("SMTP_PORT", "1025")),
            sender=os.environ.get("SMTP_FROM", "reports@example.com"),
            user=os.environ.get("SMTP_USER", ""),
            password=os.environ.get("SMTP_PASSWORD", ""),
            starttls=os.environ.get("SMTP_STARTTLS", "false").lower() == "true",
        )


def build_message(
    sender: str, to: list[str], cc: list[str], subject: str, body: str, attachment: Path
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message.set_content(body)
    maintype, subtype = XLSX.split("/")
    message.add_attachment(
        attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment.name
    )
    return message


def send(message: EmailMessage, settings: SmtpSettings, smtp_factory=smtplib.SMTP) -> None:
    with smtp_factory(settings.host, settings.port, timeout=30) as smtp:
        if settings.starttls:
            smtp.starttls()
        if settings.user:
            smtp.login(settings.user, settings.password)
        smtp.send_message(message)
