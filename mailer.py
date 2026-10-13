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

    _smtp_send(msg)


def send_feedback_email(
    *,
    to_email: str,
    first_name: str,
    package_title: str,
    agency_name: str,
    agency_google_url: str | None,
    agency_tripadvisor_url: str | None,
    platforms: list[str],   # ["google", "tripadvisor"]
) -> None:
    """Send the post-trip feedback request to the customer."""
    host = _cfg("SMTP_HOST")
    user = _cfg("SMTP_USER")
    password = _cfg("SMTP_PASS")
    from_addr = _cfg("SMTP_FROM") or user

    if not host or not user or not password:
        print("[mailer] SMTP not configured — feedback email skipped")
        return

    MOMIRA_GOOGLE = "https://g.page/r/CeqHXc2-NckXEBM/review"

    # Build review links block
    review_lines = []
    if "google" in platforms and agency_google_url:
        review_lines.append(f"  ★ Review {agency_name} on Google:\n    {agency_google_url}")
    if "tripadvisor" in platforms and agency_tripadvisor_url:
        review_lines.append(f"  ★ Review {agency_name} on TripAdvisor:\n    {agency_tripadvisor_url}")
    review_lines.append(f"  ★ Review Momira Travel on Google:\n    {MOMIRA_GOOGLE}")
    review_block = "\n\n".join(review_lines)

    subject = f"How was your trip, {first_name}? We'd love your feedback!"

    body = f"""\
Dear {first_name},

We hope you had a wonderful time on your {package_title} holiday!

Your experience and feedback mean a lot to us. If you have a moment, \
we would be incredibly grateful if you could share a short review — \
it helps other travellers and supports our team.

{review_block}

Thank you for choosing {agency_name} and Momira Travel.
We look forward to planning your next adventure!

Warm regards,
{agency_name}
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(body)

    _smtp_send(msg)


def _smtp_send(msg: EmailMessage) -> None:
    host = _cfg("SMTP_HOST")
    port = int(_cfg("SMTP_PORT", "587"))
    user = _cfg("SMTP_USER")
    password = _cfg("SMTP_PASS")
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
