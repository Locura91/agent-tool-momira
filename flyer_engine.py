"""
Travel Flyer generator — two styles.

render_flyer(pack, agent, style="a", show_qr=False) returns a self-contained
HTML page (A4 layout with print CSS) ready for Ctrl+P / ⌘P → PDF.

  style "a" — Dark-navy + teal, editorial / luxury feel
  style "b" — White + accent, magazine two-column
"""
from __future__ import annotations

import html
import base64
import io
from typing import Optional
import social_kit as sk
from models import Agent


TRANSPORT_ICONS = {
    "flights":   ("✈", "Flight"),
    "ferries":   ("⛴", "Ferry"),
    "buses":     ("🚌", "Bus/Coach"),
    "transfers": ("🚐", "Transfer"),
    "trains":    ("🚆", "Train"),
    "cars":      ("🚗", "Private Transfer"),
    "other":     ("🚙", "Transport"),
}

DISCLAIMER = (
    "Prices are dynamic and subject to availability, so they may change and cannot be guaranteed."
)

# Positive selling point — shown as a round seal/ribbon near the bottom.
CUSTOMISE_TITLE = "Fully Customisable"
CUSTOMISE_MESSAGE = (
    "Get inspired, then make it yours. We tailor every journey to your individual travel ideas and preferences."
)


def _esc(s: object) -> str:
    return html.escape(str(s)) if s is not None else ""


def _qr_data_uri(url: str) -> str:
    """Generate a QR code PNG as a data URI. Returns '' on any failure."""
    if not url:
        return ""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=6, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0d2137", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_shared(pack: sk.Package, agent: Agent):
    """Compute all the shared data fragments used by both templates."""
    d = {}

    # Gallery — use up to 6 images
    d["hero"] = pack.gallery[0] if pack.gallery else ""
    d["gallery_extra"] = pack.gallery[1:6]
    d["collage"] = pack.gallery[:4]

    # Logo
    d["logo_html"] = (
        f'<img class="agency-logo" src="{_esc(agent.logo_url)}" alt="{_esc(agent.agency_name)}">'
        if agent.logo_url
        else f'<span class="agency-name-text">{_esc(agent.agency_name or "Travel Agent")}</span>'
    )

    # Website shown as plain text
    site = agent.agency_site or ""
    if not site and agent.agency_url:
        from urllib.parse import urlparse
        site = urlparse(agent.agency_url).netloc
    d["site"] = site

    # Destinations — unique city names + unique country names
    cities = [
        (dest.get("name", str(dest)) if isinstance(dest, dict) else str(dest)).strip()
        for dest in (pack.destinations or [])
    ]
    countries = list(dict.fromkeys(
        dest.get("country", "").strip()
        for dest in (pack.destinations or [])
        if isinstance(dest, dict) and dest.get("country", "").strip()
    ))
    d["cities"] = [c for c in cities if c]
    d["countries"] = countries
    d["destinations_line"] = ", ".join(d["cities"])
    d["countries_line"] = ", ".join(countries)

    # Duration
    nights = pack.nights or (pack.days - 1 if pack.days > 1 else pack.days)
    if pack.days and nights:
        d["duration"] = f"{pack.days} days / {nights} nights"
    elif pack.days:
        d["duration"] = f"{pack.days} days"
    elif nights:
        d["duration"] = f"{nights} nights"
    else:
        d["duration"] = ""
    d["days"] = pack.days
    d["nights"] = nights

    # Description — already HTML-stripped + entity-decoded in normalise()
    raw_desc = " ".join(pack.description.split()) if pack.description else ""
    d["description"] = raw_desc[:500] + ("…" if len(raw_desc) > 500 else "")

    # Departures
    d["departures"] = pack.departures[:8]

    # Price
    d["price_str"] = f"{_esc(pack.currency or 'EUR')} {pack.price:,.0f}" if pack.price else ""

    # Hotels with nights
    hotel_names = pack.hotel_names or []
    hotel_nights = pack.hotel_nights or []
    hotel_stars = pack.hotel_stars or []
    hotel_items = []
    for i, name in enumerate(hotel_names):
        nights_n = hotel_nights[i] if i < len(hotel_nights) else 0
        stars_n = hotel_stars[i] if i < len(hotel_stars) else 0
        hotel_items.append((name, nights_n, stars_n))
    d["hotel_items"] = hotel_items   # list of (name, nights, stars)
    d["hotel_names"] = hotel_names
    d["hotels_count"] = pack.hotels

    # Transport counts → icon+label list (ordered: flights first, then others)
    transport_items = []
    tc = pack.transport_counts or {}
    order = ["flights", "ferries", "trains", "buses", "cars", "transfers", "other"]
    for key in order:
        count = tc.get(key, 0)
        if count:
            icon, label = TRANSPORT_ICONS.get(key, ("🚗", key.title()))
            transport_items.append((icon, f"{count}× {label}"))
    for key, count in tc.items():
        if key not in order and count:
            icon, label = TRANSPORT_ICONS.get(key, ("🚗", key.title()))
            transport_items.append((icon, f"{count}× {label}"))
    if not transport_items and pack.flights:
        transport_items.append(("✈", f"{pack.flights}× Flight"))
    d["transport_items"] = transport_items

    # Round trip indicator
    d["is_round_trip"] = getattr(pack, "is_round_trip", False)

    # Activities
    d["activities"] = getattr(pack, "activities", [])

    # ── "What's included" checklist — built from real data + service promises ──
    total_nights = sum(hotel_nights) if hotel_nights else 0
    d["total_nights"] = total_nights
    included = []
    flights_n = tc.get("flights", 0) or pack.flights
    if flights_n:
        if d["is_round_trip"]:
            included.append("Return flights")
        else:
            included.append(f"{flights_n}× flight" + ("s" if flights_n != 1 else ""))
    if tc.get("transfers"):
        included.append("Airport transfers")
    if tc.get("cars"):
        included.append("Private transfers")
    if hotel_items:
        hn = len(hotel_items)
        label = f"{hn} hotel" + ("s" if hn != 1 else "")
        if total_nights:
            label += f" · {total_nights} nights"
        included.append(label)
    elif nights:
        included.append(f"{nights} nights accommodation")
    if d["activities"]:
        an = len(d["activities"])
        included.append(f"{an} guided activit" + ("ies" if an != 1 else "y"))
    # Always-on service promises
    included.append("Personal travel expert")
    included.append("Support before, during and after your trip")
    included.append("Fully customisable")
    d["included_items"] = included

    # ── Benefits / trust strip ──
    d["benefit_items"] = [
        ("✨", "Tailor-made"),
        ("🔒", "Secure booking"),
        ("💬", "Always here for you"),
        ("🧭", "Expert advice"),
    ]

    # Agency contact
    d["agency_name"] = agent.agency_name or "Travel Agent"
    d["agency_url"] = agent.agency_url or ""
    d["agency_phone"] = getattr(agent, "agency_phone", None) or ""
    d["agency_email"] = getattr(agent, "agency_email", None) or ""
    d["disclaimer"] = DISCLAIMER

    return d


# ─────────────────────────────────────────────────────────────────────────────
# Style A — Dark-navy + teal, editorial
# ─────────────────────────────────────────────────────────────────────────────

def _render_style_a(pack: sk.Package, agent: Agent, d: dict, qr_uri: str = "") -> str:

    # Overlapping-circle photo collage
    collage_html = ""
    if len(d["collage"]) >= 2:
        circles = "".join(
            f'<img class="collage-circle" src="{_esc(u)}" alt="photo">'
            for u in d["collage"][:4]
        )
        collage_html = f'<div class="collage">{circles}</div>'
    elif d["gallery_extra"]:
        thumbs = "".join(
            f'<div class="thumb"><img src="{_esc(u)}" alt="photo"></div>'
            for u in d["gallery_extra"]
        )
        collage_html = f'<div class="gallery-strip">{thumbs}</div>'

    # Inclusions bar: duration + round-trip + transport + hotels + activities
    incl_items = []
    if d["duration"]:
        incl_items.append(f'<div class="incl-badge"><span class="incl-icon">🕐</span><span class="incl-text">{_esc(d["duration"])}</span></div>')
    if d["is_round_trip"]:
        incl_items.append(f'<div class="incl-badge"><span class="incl-icon">🔄</span><span class="incl-text">Round trip</span></div>')
    for icon, txt in d["transport_items"]:
        incl_items.append(f'<div class="incl-badge"><span class="incl-icon">{icon}</span><span class="incl-text">{_esc(txt)}</span></div>')
    if d["hotels_count"]:
        hotels_label = f"{d['hotels_count']} hotel{'s' if d['hotels_count'] != 1 else ''}"
        incl_items.append(f'<div class="incl-badge"><span class="incl-icon">🏨</span><span class="incl-text">{_esc(hotels_label)}</span></div>')
    if d["activities"]:
        incl_items.append(f'<div class="incl-badge"><span class="incl-icon">🎫</span><span class="incl-text">{len(d["activities"])} activit{"ies" if len(d["activities"]) != 1 else "y"}</span></div>')
    incl_html = f'<div class="inclusions">{"".join(incl_items)}</div>' if incl_items else ""

    # Price (top highlights row)
    price_html = ""
    if d["price_str"]:
        price_html = f"""<div class="price-box">
        <div class="price-from">From</div>
        <div class="price-amount">{d["price_str"]}</div>
        <div class="price-pp">per person</div>
      </div>"""

    # "What's included" checklist
    checklist_html = ""
    if d["included_items"]:
        checks = "".join(
            f'<div class="incl-check"><span class="check">✓</span>{_esc(item)}</div>'
            for item in d["included_items"]
        )
        checklist_html = f"""<div class="section">
      <div class="section-heading"><span class="section-icon">✓</span> What's included</div>
      <div class="incl-grid">{checks}</div>
    </div>"""

    # Hotels + activities side by side (two-col)
    hotel_block = ""
    if d["hotel_items"]:
        _li = []
        for name, nights, stars in d["hotel_items"][:6]:
            stars_html = '<span class="hotel-stars">' + "★" * stars + '</span>' if stars else ""
            nights_html = f' <span class="hotel-nights">({nights} nights)</span>' if nights else ""
            _li.append(f"<li>{stars_html}<span class='hotel-name'>{_esc(name)}</span>{nights_html}</li>")
        items = "".join(_li)
        hotel_block = f"""<div class="col-block">
        <div class="section-heading"><span class="section-icon">🏨</span> Hotels</div>
        <ul class="hotel-list">{items}</ul>
      </div>"""

    activity_block = ""
    if d["activities"]:
        items = "".join(f"<li>{_esc(a)}</li>" for a in d["activities"][:6])
        activity_block = f"""<div class="col-block">
        <div class="section-heading"><span class="section-icon">🎫</span> Activities &amp; tours</div>
        <ul class="activity-list">{items}</ul>
      </div>"""

    two_col_html = ""
    if hotel_block or activity_block:
        two_col_html = f'<div class="two-col">{hotel_block}{activity_block}</div>'

    # Departure chips
    dep_html = ""
    if d["departures"]:
        chips = "".join(f'<span class="dep-chip">{_esc(dep)}</span>' for dep in d["departures"])
        dep_html = f"""<div class="section">
      <div class="section-heading"><span class="section-icon">📅</span> Departure dates</div>
      <div class="dep-chips">{chips}</div>
    </div>"""

    # Benefits strip
    benefits_html = ""
    if d["benefit_items"]:
        bits = "".join(
            f'<div class="benefit"><span class="benefit-icon">{icon}</span><span class="benefit-label">{_esc(label)}</span></div>'
            for icon, label in d["benefit_items"]
        )
        benefits_html = f'<div class="benefits">{bits}</div>'

    # CTA band (bottom) — contact + price badge + optional QR
    contact_parts = []
    if d["agency_phone"]:
        contact_parts.append(f'<span class="cta-contact">📞 {_esc(d["agency_phone"])}</span>')
    if d["agency_email"]:
        contact_parts.append(f'<span class="cta-contact">✉ {_esc(d["agency_email"])}</span>')
    if d["site"]:
        contact_parts.append(f'<span class="cta-contact">🌐 {_esc(d["site"])}</span>')
    contact_html = "".join(contact_parts)

    price_badge_html = ""
    if d["price_str"]:
        price_badge_html = f"""<div class="cta-price-badge">
        <div class="cta-price-from">FROM</div>
        <div class="cta-price-amount">{d["price_str"]}</div>
        <div class="cta-price-pp">per person</div>
      </div>"""

    qr_html = f'<div class="cta-qr"><img src="{qr_uri}" alt="Scan to book"><span>Scan to book</span></div>' if qr_uri else ""

    cta_band_html = f"""<div class="cta-band">
    <div class="cta-left">
      <div class="cta-headline">Ready for this trip?</div>
      <div class="cta-agency">{_esc(d["agency_name"])}</div>
      <div class="cta-contacts">{contact_html}</div>
    </div>
    <div class="cta-right">
      {qr_html}
      {price_badge_html}
      {f'<a class="cta-btn" href="{_esc(d["agency_url"])}">Book now →</a>' if d["agency_url"] and not price_badge_html else ""}
    </div>
  </div>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(pack.title)} — Travel Flyer</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif;
  background: #c9cdd3; padding: 2.5rem 1rem; color: #1a1a2e;
}}
.a4 {{
  background: #fff; width: 794px; min-height: 1123px; margin: 0 auto;
  box-shadow: 0 8px 48px rgba(0,0,0,.22); border-radius: 6px;
  overflow: hidden; display: flex; flex-direction: column;
}}
/* Header */
.flyer-header {{
  background: #0d2137; padding: .7rem 1.8rem;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}}
.agency-logo {{ max-height: 34px; max-width: 150px; object-fit: contain; }}
.agency-name-text {{ font-weight: 800; font-size: 1rem; color: #fff; letter-spacing: .02em; }}
.header-site {{ font-size: .78rem; color: rgba(255,255,255,.55); }}
.header-badge {{
  background: #17a39b; color: #fff; border-radius: 4px;
  padding: .25rem .7rem; font-size: .72rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .08em;
}}
/* Hero */
.hero {{
  position: relative; height: 300px; overflow: hidden;
  background: linear-gradient(135deg, #0d2137 0%, #17a39b 100%); flex-shrink: 0;
}}
.hero img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.hero-scrim {{
  position: absolute; inset: 0;
  background:
    linear-gradient(to top, rgba(10,18,35,.82) 0%, transparent 52%),
    linear-gradient(to bottom-right, rgba(10,18,35,.25) 0%, transparent 45%);
}}
.hero-text {{
  position: absolute; bottom: 0; left: 0; right: 0; padding: 1.4rem 1.8rem; color: #fff;
}}
.hero-eyebrow {{
  font-size: .72rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .1em; color: #5eddd7; margin-bottom: .45rem;
}}
.hero-title {{
  font-size: 1.75rem; font-weight: 900; line-height: 1.2;
  text-shadow: 0 1px 6px rgba(0,0,0,.45); margin-bottom: .35rem; max-width: 560px;
}}
.hero-dest {{ font-size: .88rem; color: rgba(255,255,255,.82); text-shadow: 0 1px 3px rgba(0,0,0,.3); }}
/* Highlights row */
.highlights-row {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem 1.8rem; background: #f7f9fb;
  border-bottom: 1px solid #e4e8ed; flex-shrink: 0; gap: 1rem; flex-wrap: wrap;
}}
.inclusions {{ display: flex; gap: .6rem; flex-wrap: wrap; }}
.incl-badge {{
  display: flex; align-items: center; gap: .35rem;
  background: #fff; border: 1px solid #dce1e8; border-radius: 6px; padding: .35rem .75rem;
}}
.incl-icon {{ font-size: 1rem; line-height: 1; }}
.incl-text {{ font-size: .8rem; font-weight: 600; color: #374151; }}
/* Price */
.price-box {{ text-align: right; flex-shrink: 0; }}
.price-from {{ font-size: .7rem; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: .06em; }}
.price-amount {{ font-size: 1.7rem; font-weight: 900; color: #17a39b; line-height: 1.1; }}
.price-pp {{ font-size: .72rem; color: #6b7280; }}
/* Body */
.flyer-body {{ flex: 1; padding: 1.4rem 1.8rem; display: flex; flex-direction: column; gap: 1.2rem; }}
.section-heading {{
  font-size: .72rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: .09em; color: #9ca3af; margin-bottom: .55rem;
  display: flex; align-items: center; gap: .3rem;
}}
.section-icon {{ font-size: .9rem; }}
.description-text {{ font-size: .95rem; color: #1f2937; line-height: 1.7; font-weight: 700; }}
/* Collage */
.collage {{ display: flex; justify-content: center; align-items: center; padding: .4rem 0; }}
.collage-circle {{
  width: 160px; height: 160px; border-radius: 50%; border: 4px solid #fff;
  box-shadow: 0 3px 14px rgba(13,33,55,.22); object-fit: cover; margin-left: -28px;
}}
.collage-circle:first-child {{ margin-left: 0; }}
.gallery-strip {{ display: flex; gap: .5rem; }}
.thumb {{ flex: 1; border-radius: 6px; overflow: hidden; height: 80px; }}
.thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
/* Checklist */
.incl-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: .55rem 1.2rem; }}
.incl-check {{ display: flex; align-items: center; gap: .55rem; font-size: .86rem; color: #374151; font-weight: 500; }}
.incl-check .check {{
  width: 19px; height: 19px; border-radius: 50%; background: #16a34a; color: #fff;
  font-size: .7rem; font-weight: 900; display: inline-flex; align-items: center;
  justify-content: center; flex-shrink: 0;
}}
/* Two-column hotels/activities */
.two-col {{ display: flex; gap: 1.6rem; }}
.col-block {{ flex: 1; min-width: 0; }}
.dep-chips {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
.dep-chip {{
  background: #eef2f7; border-radius: 5px; padding: .28rem .65rem;
  font-size: .8rem; color: #374151; font-weight: 500;
}}
.hotel-list, .activity-list {{ list-style: none; display: flex; flex-direction: column; gap: .4rem; }}
.hotel-list li {{ font-size: .85rem; color: #374151; line-height: 1.45; display: flex; flex-wrap: wrap; align-items: baseline; gap: .25rem; }}
.hotel-stars {{ color: #f59e0b; font-size: .78rem; letter-spacing: -.02em; flex-shrink: 0; }}
.hotel-name {{ font-weight: 600; color: #111827; }}
.activity-list li {{ font-size: .85rem; color: #374151; padding-left: .9rem; position: relative; line-height: 1.4; }}
.activity-list li::before {{ content: "🎫"; position: absolute; left: 0; font-size: .7rem; top: .1rem; }}
.hotel-nights {{ font-size: .75rem; color: #9ca3af; font-style: italic; }}
/* Disclaimer */
.disclaimer {{
  font-size: .68rem; color: #9ca3af; line-height: 1.5; text-align: center;
  border-top: 1px solid #e5e7eb; padding-top: .8rem;
  font-style: italic;
}}
/* Benefits strip */
.benefits {{
  display: flex; justify-content: space-around; align-items: center; gap: .8rem;
  padding: .95rem 1.8rem; background: #f0fafa;
  border-top: 1px solid #d5ebe9; border-bottom: 1px solid #d5ebe9; flex-shrink: 0;
}}
.benefit {{ display: flex; flex-direction: column; align-items: center; gap: .28rem; text-align: center; }}
.benefit-icon {{ font-size: 1.3rem; line-height: 1; }}
.benefit-label {{ font-size: .72rem; font-weight: 700; color: #0e6b66; text-transform: uppercase; letter-spacing: .04em; }}
/* Customise seal / round ribbon */
.seal-band {{ display: flex; justify-content: center; align-items: center; padding: 1.3rem 1rem; background: #fff; flex-shrink: 0; }}
.custom-seal {{
  width: 178px; height: 178px; border-radius: 50%;
  background: radial-gradient(circle at 50% 34%, #17a39b, #0e6b66);
  color: #fff; display: flex; align-items: center; justify-content: center;
  text-align: center; padding: 1.5rem 1.3rem;
  box-shadow: 0 6px 22px rgba(13,33,55,.28);
  border: 3px dashed rgba(255,255,255,.55); position: relative;
}}
.custom-seal::after {{
  content: ""; position: absolute; inset: 9px; border-radius: 50%;
  border: 1px solid rgba(255,255,255,.35);
}}
.custom-seal-inner {{ display: flex; flex-direction: column; align-items: center; gap: .3rem; padding: 0 24px; text-align: center; }}
.seal-star {{ font-size: 1.15rem; }}
.seal-title {{ font-size: .78rem; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; text-align: center; }}
.seal-text {{ font-size: .64rem; line-height: 1.4; font-weight: 500; color: rgba(255,255,255,.94); text-align: center; }}
/* CTA band */
.cta-band {{
  background: linear-gradient(120deg, #0d2137 0%, #17a39b 100%);
  padding: 1.2rem 1.8rem; display: flex; align-items: center; justify-content: space-between;
  gap: 1.2rem; flex-shrink: 0; color: #fff;
}}
.cta-left {{ display: flex; flex-direction: column; gap: .25rem; }}
.cta-headline {{ font-size: 1.25rem; font-weight: 900; letter-spacing: .01em; }}
.cta-agency {{ font-size: .9rem; font-weight: 700; color: rgba(255,255,255,.9); }}
.cta-contacts {{ display: flex; flex-wrap: wrap; gap: .2rem 1rem; margin-top: .2rem; }}
.cta-contact {{ font-size: .76rem; color: rgba(255,255,255,.72); }}
.cta-right {{ display: flex; align-items: center; gap: 1rem; flex-shrink: 0; }}
.cta-qr {{ display: flex; flex-direction: column; align-items: center; gap: .2rem; }}
.cta-qr img {{ width: 74px; height: 74px; border-radius: 6px; background: #fff; padding: 3px; display: block; }}
.cta-qr span {{ font-size: .62rem; color: rgba(255,255,255,.7); text-transform: uppercase; letter-spacing: .06em; }}
.cta-price-badge {{
  background: #fff; color: #0d2137; border-radius: 10px; padding: .55rem 1.1rem;
  text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,.25);
}}
.cta-price-from {{ font-size: .6rem; font-weight: 700; letter-spacing: .1em; color: #6b7280; }}
.cta-price-amount {{ font-size: 1.5rem; font-weight: 900; color: #17a39b; line-height: 1.1; }}
.cta-price-pp {{ font-size: .62rem; color: #6b7280; }}
.cta-btn {{
  background: #fff; color: #0d2137; border-radius: 7px;
  padding: .6rem 1.4rem; font-size: .9rem; font-weight: 800;
  text-decoration: none; white-space: nowrap;
}}
@media print {{
  body {{ background: #fff; padding: 0; }}
  .a4 {{ box-shadow: none; border-radius: 0; width: 100%; min-height: 0; }}
}}
</style>
</head>
<body>
<div class="a4">
  <div class="flyer-header">
    {d["logo_html"]}
    {f'<span class="header-site">{_esc(d["site"])}</span>' if d["site"] else ""}
    <span class="header-badge">Holiday Package</span>
  </div>
  <div class="hero">
    {f'<img src="{_esc(d["hero"])}" alt="Package photo">' if d["hero"] else ""}
    <div class="hero-scrim"></div>
    <div class="hero-text">
      {f'<div class="hero-eyebrow">📍 {_esc(d["countries_line"] or d["destinations_line"])}</div>' if (d["countries_line"] or d["destinations_line"]) else ""}
      <div class="hero-title">{_esc(pack.title)}</div>
      {f'<div class="hero-dest">{_esc(d["destinations_line"])}</div>' if d["destinations_line"] else ""}
    </div>
  </div>
  <div class="highlights-row">
    {incl_html}
    {price_html}
  </div>
  <div class="flyer-body">
    {f'<div class="section"><p class="description-text">{_esc(d["description"])}</p></div>' if d["description"] else ""}
    {collage_html}
    {checklist_html}
    {two_col_html}
    {dep_html}
    <div class="disclaimer">{_esc(d["disclaimer"])}</div>
  </div>
  <div class="seal-band">
    <div class="custom-seal"><div class="custom-seal-inner">
      <span class="seal-star">✦</span>
      <span class="seal-title">{_esc(CUSTOMISE_TITLE)}</span>
      <span class="seal-text">{_esc(CUSTOMISE_MESSAGE)}</span>
    </div></div>
  </div>
  {benefits_html}
  {cta_band_html}
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Style B — White magazine, two-column
# ─────────────────────────────────────────────────────────────────────────────

def _render_style_b(pack: sk.Package, agent: Agent, d: dict, qr_uri: str = "") -> str:

    # Right-column photos (rounded stack)
    right_photos = ""
    for u in d["gallery_extra"][:3]:
        right_photos += f'<img class="grid-photo" src="{_esc(u)}" alt="photo">'

    # Departure dates (first 6)
    dep_html = ""
    if d["departures"]:
        items = "".join(f'<span class="dep-pill">{_esc(dep)}</span>' for dep in d["departures"][:6])
        dep_html = f"""<div class="info-row">
        <span class="info-label">📅 Travel dates</span>
        <div class="dep-pills">{items}</div>
      </div>"""

    # Transport block
    trans_html = ""
    if d["transport_items"]:
        icons_html = "".join(
            f'<div class="trans-item"><span class="trans-icon">{icon}</span><span class="trans-txt">{_esc(txt)}</span></div>'
            for icon, txt in d["transport_items"]
        )
        trans_html = f"""<div class="info-row">
        <span class="info-label">🗺 Transport</span>
        <div class="trans-grid">{icons_html}</div>
      </div>"""

    # Hotel list with nights
    hotel_html = ""
    if d["hotel_items"]:
        _li = []
        for name, nights_n, stars_n in d["hotel_items"][:5]:
            stars_html = '<span class="hotel-stars">' + "★" * stars_n + '</span>' if stars_n else ""
            span = f' <span class="hotel-nights">({nights_n} nights)</span>' if nights_n else ""
            _li.append(f"<li>{stars_html}<span class='hotel-name'>{_esc(name)}</span>{span}</li>")
        items = "".join(_li)
        hotel_html = f"""<div class="info-row">
        <span class="info-label">🏨 Hotels</span>
        <ul class="hotel-list">{items}</ul>
      </div>"""
    elif d["hotels_count"]:
        hotel_html = f"""<div class="info-row">
        <span class="info-label">🏨 Hotels</span>
        <span class="info-value">{d["hotels_count"]} accommodation{"s" if d["hotels_count"] != 1 else ""}</span>
      </div>"""

    # Activities
    activity_html_b = ""
    if d["activities"]:
        items = "".join(f"<li>{_esc(a)}</li>" for a in d["activities"][:5])
        activity_html_b = f"""<div class="info-row">
        <span class="info-label">🎫 Included Activities</span>
        <ul class="activity-list">{items}</ul>
      </div>"""

    # Round trip
    roundtrip_html_b = ""
    if d["is_round_trip"]:
        roundtrip_html_b = """<div class="info-row">
        <span class="info-label">🔄 Trip type</span>
        <span class="info-value">Round trip</span>
      </div>"""

    # Duration row
    dur_html = ""
    if d["duration"]:
        dur_html = f"""<div class="info-row">
        <span class="info-label">🕐 Duration</span>
        <span class="info-value">{_esc(d["duration"])}</span>
      </div>"""

    # "What's included" checklist
    checklist_html = ""
    if d["included_items"]:
        checks = "".join(
            f'<div class="incl-check"><span class="check">✓</span>{_esc(item)}</div>'
            for item in d["included_items"]
        )
        checklist_html = f"""<div class="info-row">
        <span class="info-label">✓ What's included</span>
        <div class="incl-grid">{checks}</div>
      </div>"""

    # Agency contact block (+ optional QR)
    contact_rows = ""
    if d["agency_phone"]:
        contact_rows += f'<div class="contact-item"><span class="contact-icon">📞</span><span>{_esc(d["agency_phone"])}</span></div>'
    if d["agency_email"]:
        contact_rows += f'<div class="contact-item"><span class="contact-icon">✉</span><span>{_esc(d["agency_email"])}</span></div>'
    if d["site"]:
        contact_rows += f'<div class="contact-item"><span class="contact-icon">🌐</span><span>{_esc(d["site"])}</span></div>'
    qr_block = f'<div class="contact-qr"><img src="{qr_uri}" alt="Scan to book"><span>Scan to book</span></div>' if qr_uri else ""

    # Benefits strip
    benefits_html = ""
    if d["benefit_items"]:
        bits = "".join(
            f'<div class="benefit"><span class="benefit-icon">{icon}</span><span class="benefit-label">{_esc(label)}</span></div>'
            for icon, label in d["benefit_items"]
        )
        benefits_html = f'<div class="benefits">{bits}</div>'

    # Countries/destinations headline
    dest_headline = d["destinations_line"] or pack.title
    country_line = d["countries_line"]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(pack.title)} — Travel Flyer</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif;
  background: #c9cdd3; padding: 2.5rem 1rem; color: #1a1a2e;
}}
.a4 {{
  background: #fff; width: 794px; min-height: 1123px; margin: 0 auto;
  box-shadow: 0 8px 48px rgba(0,0,0,.22); border-radius: 6px;
  overflow: hidden; display: flex; flex-direction: column;
}}
/* Top header bar */
.top-bar {{
  display: flex; align-items: center; justify-content: space-between;
  padding: .65rem 1.8rem; border-bottom: 3px solid #17a39b; flex-shrink: 0;
}}
.agency-logo {{ max-height: 34px; max-width: 150px; object-fit: contain; }}
.agency-name-text {{ font-weight: 800; font-size: 1rem; color: #0d2137; }}
.top-bar-right {{ text-align: right; }}
.top-tagline {{ font-size: .72rem; color: #6b7280; }}
.top-site {{ font-size: .78rem; font-weight: 600; color: #17a39b; }}
/* Hero strip */
.hero-strip {{
  position: relative; height: 240px; overflow: hidden; flex-shrink: 0;
  background: linear-gradient(120deg, #0d2137, #17a39b);
}}
.hero-strip img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.hero-strip-scrim {{
  position: absolute; inset: 0;
  background: linear-gradient(to right, rgba(13,33,55,.78) 0%, rgba(13,33,55,.2) 60%, transparent 100%);
}}
.hero-strip-text {{
  position: absolute; top: 0; bottom: 0; left: 0;
  padding: 1.4rem 1.8rem; display: flex; flex-direction: column; justify-content: flex-end;
  color: #fff; max-width: 460px;
}}
.strip-country {{
  font-size: .75rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: .12em; color: #5eddd7; margin-bottom: .3rem;
}}
.strip-dest {{ font-size: 2rem; font-weight: 900; line-height: 1.15; text-shadow: 0 2px 8px rgba(0,0,0,.5); }}
.strip-title {{ font-size: .9rem; color: rgba(255,255,255,.78); margin-top: .35rem; font-weight: 400; font-style: italic; }}
/* Price badge on hero */
.price-badge {{
  position: absolute; top: 1.2rem; right: 1.6rem;
  background: #e8163c; color: #fff; border-radius: 8px;
  padding: .6rem 1.1rem; text-align: center; box-shadow: 0 3px 14px rgba(0,0,0,.3);
}}
.price-badge-from {{ font-size: .62rem; text-transform: uppercase; letter-spacing: .08em; opacity: .85; }}
.price-badge-amount {{ font-size: 1.35rem; font-weight: 900; line-height: 1.1; }}
.price-badge-pp {{ font-size: .62rem; opacity: .85; }}
/* Two-column body */
.body-cols {{ display: flex; flex: 1; overflow: hidden; }}
.col-left {{
  flex: 1; padding: 1.4rem 1.4rem 1.4rem 1.8rem;
  display: flex; flex-direction: column; gap: 1rem; border-right: 1px solid #e5e7eb; min-width: 0;
}}
.col-right {{
  width: 240px; flex-shrink: 0;
  padding: 1.4rem 1.8rem 1.4rem 1.2rem;
  display: flex; flex-direction: column; gap: .8rem;
}}
/* Info rows */
.info-row {{ display: flex; flex-direction: column; gap: .4rem; }}
.info-label {{ font-size: .68rem; font-weight: 800; text-transform: uppercase; letter-spacing: .09em; color: #9ca3af; }}
.info-value {{ font-size: .88rem; color: #374151; font-weight: 500; }}
/* Checklist */
.incl-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: .45rem 1rem; }}
.incl-check {{ display: flex; align-items: center; gap: .5rem; font-size: .82rem; color: #374151; font-weight: 500; }}
.incl-check .check {{
  width: 18px; height: 18px; border-radius: 50%; background: #16a34a; color: #fff;
  font-size: .68rem; font-weight: 900; display: inline-flex; align-items: center;
  justify-content: center; flex-shrink: 0;
}}
/* Departure pills */
.dep-pills {{ display: flex; flex-wrap: wrap; gap: .35rem; }}
.dep-pill {{ background: #f0fafa; border: 1px solid #b2e5e2; color: #0e6b66; border-radius: 5px; padding: .2rem .55rem; font-size: .78rem; font-weight: 600; }}
/* Transport grid */
.trans-grid {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
.trans-item {{ display: flex; align-items: center; gap: .3rem; background: #f7f9fb; border: 1px solid #e4e8ed; border-radius: 5px; padding: .22rem .6rem; }}
.trans-icon {{ font-size: .95rem; }}
.trans-txt {{ font-size: .8rem; color: #374151; font-weight: 500; }}
/* Hotel + activity lists */
.hotel-list, .activity-list {{ list-style: none; display: flex; flex-direction: column; gap: .4rem; }}
.hotel-list li {{ font-size: .83rem; color: #374151; line-height: 1.45; display: flex; flex-wrap: wrap; align-items: baseline; gap: .25rem; }}
.hotel-stars {{ color: #f59e0b; font-size: .78rem; letter-spacing: -.02em; flex-shrink: 0; }}
.hotel-name {{ font-weight: 600; color: #111827; }}
.activity-list li {{ font-size: .83rem; color: #374151; padding-left: 1rem; position: relative; line-height: 1.4; }}
.activity-list li::before {{ content: "🎫"; position: absolute; left: 0; font-size: .7rem; top: .12rem; }}
.hotel-nights {{ font-size: .75rem; color: #9ca3af; font-style: italic; }}
/* Description */
.desc-text {{ font-size: .93rem; color: #1f2937; line-height: 1.7; font-weight: 700; }}
/* Right column photos */
.grid-photo {{ width: 100%; border-radius: 8px; object-fit: cover; display: block; aspect-ratio: 3/2; }}
/* Right column contact card */
.contact-card {{
  background: #f7f9fb; border: 1px solid #e4e8ed; border-radius: 8px;
  padding: .9rem; display: flex; flex-direction: column; gap: .45rem; margin-top: auto;
}}
.contact-card-title {{ font-size: .72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; color: #17a39b; margin-bottom: .1rem; }}
.contact-item {{ display: flex; align-items: flex-start; gap: .45rem; font-size: .8rem; color: #374151; }}
.contact-icon {{ font-size: .9rem; flex-shrink: 0; margin-top: .05rem; }}
.contact-qr {{ display: flex; flex-direction: column; align-items: center; gap: .25rem; margin-top: .5rem; padding-top: .6rem; border-top: 1px solid #e4e8ed; }}
.contact-qr img {{ width: 96px; height: 96px; display: block; }}
.contact-qr span {{ font-size: .64rem; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; }}
/* Benefits strip */
.benefits {{
  display: flex; justify-content: space-around; align-items: center; gap: .8rem;
  padding: .9rem 1.8rem; background: #f0fafa;
  border-top: 1px solid #d5ebe9; border-bottom: 1px solid #d5ebe9; flex-shrink: 0;
}}
.benefit {{ display: flex; flex-direction: column; align-items: center; gap: .28rem; text-align: center; }}
.benefit-icon {{ font-size: 1.3rem; line-height: 1; }}
.benefit-label {{ font-size: .72rem; font-weight: 700; color: #0e6b66; text-transform: uppercase; letter-spacing: .04em; }}
/* Customise seal / round ribbon */
.seal-band {{ display: flex; justify-content: center; align-items: center; padding: 1.2rem 1rem; background: #fff; flex-shrink: 0; }}
.custom-seal {{
  width: 168px; height: 168px; border-radius: 50%;
  background: radial-gradient(circle at 50% 34%, #17a39b, #0e6b66);
  color: #fff; display: flex; align-items: center; justify-content: center;
  text-align: center; padding: 1.4rem 1.2rem;
  box-shadow: 0 6px 22px rgba(13,33,55,.28);
  border: 3px dashed rgba(255,255,255,.55); position: relative;
}}
.custom-seal::after {{ content: ""; position: absolute; inset: 9px; border-radius: 50%; border: 1px solid rgba(255,255,255,.35); }}
.custom-seal-inner {{ display: flex; flex-direction: column; align-items: center; gap: .3rem; padding: 0 22px; text-align: center; }}
.seal-star {{ font-size: 1.1rem; }}
.seal-title {{ font-size: .76rem; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; text-align: center; }}
.seal-text {{ font-size: .62rem; line-height: 1.4; font-weight: 500; color: rgba(255,255,255,.94); text-align: center; }}
/* Footer bar */
.bottom-bar {{
  background: #0d2137; flex-shrink: 0; padding: .9rem 1.8rem;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
}}
.disclaimer-text {{ font-size: .65rem; color: rgba(255,255,255,.45); line-height: 1.5; flex: 1; font-style: italic; }}
.cta-btn {{
  background: #17a39b; color: #fff; border-radius: 7px;
  padding: .55rem 1.3rem; font-size: .88rem; font-weight: 800;
  text-decoration: none; white-space: nowrap; flex-shrink: 0;
}}
@media print {{
  body {{ background: #fff; padding: 0; }}
  .a4 {{ box-shadow: none; border-radius: 0; width: 100%; min-height: 0; }}
}}
</style>
</head>
<body>
<div class="a4">
  <div class="top-bar">
    {d["logo_html"]}
    {f'<div class="top-bar-right"><div class="top-tagline">Holiday Package</div><div class="top-site">{_esc(d["site"])}</div></div>' if d["site"] else '<div class="top-bar-right"><div class="top-tagline">Holiday Package</div></div>'}
  </div>
  <div class="hero-strip">
    {f'<img src="{_esc(d["hero"])}" alt="Package photo">' if d["hero"] else ""}
    <div class="hero-strip-scrim"></div>
    <div class="hero-strip-text">
      {f'<div class="strip-country">📍 {_esc(country_line)}</div>' if country_line else ""}
      <div class="strip-dest">{_esc(dest_headline.upper())}</div>
      {f'<div class="strip-title">{_esc(pack.title)}</div>' if dest_headline != pack.title else ""}
    </div>
    {f'''<div class="price-badge">
      <div class="price-badge-from">From</div>
      <div class="price-badge-amount">{d["price_str"]}</div>
      <div class="price-badge-pp">per person</div>
    </div>''' if d["price_str"] else ""}
  </div>
  <div class="body-cols">
    <div class="col-left">
      {f'<p class="desc-text">{_esc(d["description"])}</p>' if d["description"] else ""}
      {dur_html}
      {roundtrip_html_b}
      {trans_html}
      {hotel_html}
      {activity_html_b}
      {checklist_html}
      {dep_html}
    </div>
    <div class="col-right">
      {right_photos}
      {f'''<div class="contact-card">
        <div class="contact-card-title">{_esc(d["agency_name"])}</div>
        {contact_rows}
        {qr_block}
      </div>''' if (contact_rows or qr_block) else f'<div class="contact-card"><div class="contact-card-title">{_esc(d["agency_name"])}</div></div>'}
    </div>
  </div>
  <div class="seal-band">
    <div class="custom-seal"><div class="custom-seal-inner">
      <span class="seal-star">✦</span>
      <span class="seal-title">{_esc(CUSTOMISE_TITLE)}</span>
      <span class="seal-text">{_esc(CUSTOMISE_MESSAGE)}</span>
    </div></div>
  </div>
  {benefits_html}
  <div class="bottom-bar">
    <span class="disclaimer-text">{_esc(d["disclaimer"])}</span>
    {f'<a class="cta-btn" href="{_esc(d["agency_url"])}">Book now →</a>' if d["agency_url"] else ""}
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_flyer(pack: sk.Package, agent: Agent, style: str = "a", show_qr: bool = False) -> str:
    """
    Render a print-ready A4 HTML flyer.
    style "a" = dark-navy editorial
    style "b" = white magazine two-column
    show_qr   = embed an optional QR code linking to the agency website
    """
    d = _build_shared(pack, agent)
    qr_uri = _qr_data_uri(d["agency_url"]) if (show_qr and d["agency_url"]) else ""
    if style == "b":
        return _render_style_b(pack, agent, d, qr_uri)
    return _render_style_a(pack, agent, d, qr_uri)
