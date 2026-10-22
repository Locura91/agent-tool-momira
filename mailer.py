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
    passengers: list | None = None,
    address: str = "",
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

    # Build passenger section
    pax_lines = ""
    if passengers:
        adults = [p for p in passengers if p.get("type") == "adult"]
        children = [p for p in passengers if p.get("type") == "child"]
        pax_lines = "\nPassengers\n──────────\n"
        for i, p in enumerate(adults, 1):
            pax_lines += f"Adult {i}:     {p.get('full_name', '—')}  (DOB: {p.get('dob', '—')})\n"
        for i, p in enumerate(children, 1):
            pax_lines += f"Child {i}:     {p.get('full_name', '—')}  (DOB: {p.get('dob', '—')})\n"

    # Use first passenger name if available, else the split first/last
    display_name = passengers[0].get("full_name", f"{first_name} {last_name}") if passengers else f"{first_name} {last_name}"
    subject = f"New Registration: {package_title or package_id} — {display_name}"

    body = f"""\
New travel registration received via Travel Agent Kit.

Package:     {package_title or '—'} (ID: {package_id})
Agency:      {agency_name}

Contact details
───────────────
E-mail:      {consumer_email}
Phone:       {phone or '—'}
Address:     {address or '—'}
Nationality: {nationality or '—'}
{pax_lines}
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
    agent_email: str | None = None,
) -> None:
    """Send the post-trip feedback request to the customer (HTML email)."""
    host = _cfg("SMTP_HOST")
    user = _cfg("SMTP_USER")
    password = _cfg("SMTP_PASS")
    from_addr = _cfg("SMTP_FROM") or user

    if not host or not user or not password:
        print("[mailer] SMTP not configured — feedback email skipped")
        return

    MOMIRA_GOOGLE = "https://g.page/r/CeqHXc2-NckXEBM/review"

    subject = f"How was your trip, {first_name}? We'd love your feedback!"

    # Build HTML review buttons
    btn_style = (
        "display:inline-block;margin:6px 0;padding:12px 24px;"
        "background:#17a39b;color:#ffffff;text-decoration:none;"
        "border-radius:8px;font-size:15px;font-weight:600;"
    )
    review_buttons_html = ""
    review_lines_text = []

    if "google" in platforms and agency_google_url:
        review_buttons_html += f'<a href="{agency_google_url}" style="{btn_style}">★ Review {agency_name} on Google</a><br>'
        review_lines_text.append(f"★ Review {agency_name} on Google: {agency_google_url}")
    if "tripadvisor" in platforms and agency_tripadvisor_url:
        review_buttons_html += f'<a href="{agency_tripadvisor_url}" style="{btn_style}">★ Review {agency_name} on TripAdvisor</a><br>'
        review_lines_text.append(f"★ Review {agency_name} on TripAdvisor: {agency_tripadvisor_url}")
    review_buttons_html += f'<a href="{MOMIRA_GOOGLE}" style="{btn_style}">★ Review Momira Travel on Google</a><br>'
    review_lines_text.append(f"★ Review Momira Travel on Google: {MOMIRA_GOOGLE}")

    html_body = f"""\
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111827;max-width:560px;margin:0 auto;padding:24px;">
  <p>Dear {first_name},</p>

  <p>We hope you had a wonderful time on your <strong>{package_title}</strong> holiday! If you have a moment, we'd love to hear your feedback — it helps other travellers and supports our team.</p>

  <div style="margin:20px 0;">
    {review_buttons_html}
  </div>

  <p>{"Thank you for choosing <strong>" + agency_name + "</strong>." if agency_name == "Momira Travel" else "Thank you for choosing <strong>" + agency_name + "</strong> and Momira Travel."} For any future requests, feel free to contact us at <a href="mailto:info@momira.de" style="color:#17a39b;">info@momira.de</a>.</p>

  <p>Warm regards,<br>
  <strong>Your Momira Travel Team</strong></p>
</body>
</html>"""

    # Plain-text fallback
    thanks = f"Thank you for choosing {agency_name}." if agency_name == "Momira Travel" else f"Thank you for choosing {agency_name} and Momira Travel."
    text_body = f"""\
Dear {first_name},

We hope you had a wonderful time on your {package_title} holiday! If you have a moment, we'd love to hear your feedback — it helps other travellers and supports our team.

{chr(10).join(review_lines_text)}

{thanks} For any future requests, feel free to contact us at info@momira.de.

Warm regards,
Your Momira Travel Team
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    if agent_email:
        msg["Cc"] = agent_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

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
