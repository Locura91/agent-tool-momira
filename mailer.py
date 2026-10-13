"""
Simple SMTP mailer used for registration confirmations.

Environment variables (set in Render dashboard):
  SMTP_HOST     e.g. smtp.gmail.com or mail.your-host.de
  SMTP_PORT     465 (SSL) or 587 (STARTTLS) — default 587
  SMTP_USER     sender address / login
  SMTP_PASS     password / app-password
  SMTP_FROM     display name + address, e.g. "Travel Agent Kit <noreply@momira.de>"
                defaults to SMTP_USER if not set
  CC_EMAIL      always-CC address, default info@momira.de
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def send_registration_email(
    *,
    to_email: str,
    agency_name: str,
    package_id: str,
    package_title: str,
    first_name: str,
    last_name: str,
    consumer_email: str,
    phone: str,
    nationality: str,
) -> None:
    """
    Send one registration notification email.
    - to_email  : the agency's email address
    - CC always goes to CC_EMAIL (default info@momira.de)
    Raises on SMTP failure so the caller can surface the error.
    """
    host = _cfg("SMTP_HOST")
    port = int(_cfg("SMTP_PORT", "587"))
    user = _cfg("SMTP_USER")
    password = _cfg("SMTP_PASS")
    from_addr = _cfg("SMTP_FROM") or user
    cc_addr = _cfg("CC_EMAIL", "info@momira.de")

    if not host or not user or not password:
        # SMTP not configured — log and skip (so the submission still saves to DB)
        print("[mailer] SMTP not configured — email skipped")
        return

    subject = f"New Registration: {package_title or package_id} — {first_name} {last_name}"

    body = f"""\
New travel registration received via Travel Agent Kit.

Package:     {package_title or '—'} (ID: {package_id})
Agency:      {agency_name}

Customer details
────────────────
Name:        {first_name} {last_name}
E-mail:      {consumer_email}
Phone:       {phone or '—'}
Nationality: {nationality or '—'}

This registration was submitted through your shareable booking link.
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg["Cc"] = cc_addr
    msg.set_content(body)

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)
