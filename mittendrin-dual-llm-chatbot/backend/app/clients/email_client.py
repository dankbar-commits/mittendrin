"""
app/clients/email_client.py

Sends transactional emails over standard SMTP — works with Gmail,
SendGrid's SMTP relay (smtp.sendgrid.net, API key as the password),
Outlook/Office365, Amazon SES, or any other provider that speaks SMTP.
Switching providers is a .env change (SMTP_HOST/PORT/USERNAME/PASSWORD),
not a code change. Nothing else in the app should send email directly —
everything goes through send_email() here.
"""

import ssl
from email.message import EmailMessage

import aiosmtplib
import certifi

from app.config import get_settings

# Explicit cert bundle rather than the system default — on some macOS
# Python installs, the default SSL context can't find a local issuer
# certificate at all, failing every TLS connection with
# CERTIFICATE_VERIFY_FAILED. certifi ships a known-good bundle so this
# works the same regardless of how Python was installed.
_TLS_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class EmailError(Exception):
    """Raised when sending an email fails. Callers should generally log
    and continue rather than fail the whole request over this — a missed
    confirmation email shouldn't block a successful registration."""


async def send_email(to_email: str, subject: str, html_content: str) -> None:
    settings = get_settings()

    if not settings.smtp_username or not settings.smtp_password:
        raise EmailError("SMTP_USERNAME / SMTP_PASSWORD are not set — cannot send email")

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("This email requires an HTML-capable client to view.")
    message.add_alternative(html_content, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=True,
            tls_context=_TLS_CONTEXT,
            timeout=15.0,
        )
    except aiosmtplib.SMTPException as e:
        raise EmailError(f"SMTP send failed ({settings.smtp_host}:{settings.smtp_port}): {e}") from e


async def send_registration_confirmation(
    to_email: str,
    name: str,
    event_title: str,
    event_date: str,
    event_address: str,
    participants: int,
) -> None:
    """Convenience wrapper that builds the confirmation email content."""
    subject = f"Anmeldebestätigung: {event_title}"
    html_content = f"""
        <p>Hallo {name},</p>
        <p>vielen Dank für deine Anmeldung! Hier sind deine Details:</p>
        <ul>
            <li><strong>Veranstaltung:</strong> {event_title}</li>
            <li><strong>Datum:</strong> {event_date}</li>
            <li><strong>Ort:</strong> {event_address}</li>
            <li><strong>Anzahl Personen:</strong> {participants}</li>
        </ul>
        <p>Wir freuen uns auf dich!</p>
    """
    await send_email(to_email, subject, html_content)


async def send_submission_confirmation(
    to_email: str,
    title: str,
    brief: str | None,
    address: str | None,
    city: str | None,
) -> None:
    """Confirms receipt of an organizer's draft submission (POST
    /api/submit) — a different flow from registration above: this is the
    organizer confirming *their own* entry was submitted, not a visitor
    confirming attendance."""
    subject = f"Eintrag eingegangen: {title}"
    location_line = ""
    if address or city:
        location_line = f"<li><strong>Ort:</strong> {', '.join(p for p in [address, city] if p)}</li>"

    html_content = f"""
        <p>Hallo,</p>
        <p>dein Eintrag wurde übermittelt und wird geprüft:</p>
        <ul>
            <li><strong>Titel:</strong> {title}</li>
            {f"<li><strong>Kurzbeschreibung:</strong> {brief}</li>" if brief else ""}
            {location_line}
        </ul>
        <p>Vielen Dank!</p>
    """
    await send_email(to_email, subject, html_content)