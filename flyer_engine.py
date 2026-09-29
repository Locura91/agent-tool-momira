"""
Travel Flyer generator — two styles.

render_flyer(pack, agent, style="a") returns a self-contained HTML page
(A4 layout with print CSS) ready for Ctrl+P / ⌘P → PDF.

  style "a" — Dark-navy + teal, editorial / luxury feel
  style "b" — White + accent, magazine two-column, close to the
              reference screenshot (large destination headline, photo grid,
              hotel list, clean info blocks)
"""
from __future__ import annotations

import html
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
    "Prices are dynamic and subject to change. Availability cannot be guaranteed. "
    "This is a travel inspiration — we can fully customise it for each customer individually."
)


def _esc(s: object) -> str:
    return html.escape(str(s)) if s is not None else ""


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_shared(pack: sk.Package, agent: Agent):
    """Compute all the shared data fragments used by both templates."""
    d = {}

    # Gallery
    d["hero"] = pack.gallery[0] if pack.gallery else ""
    d["gallery_extra"] = pack.gallery[1:4]

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
    if pack.days and pack.nights:
        d["duration"] = f"{pack.days} days / {pack.nights} nights"
    elif pack.days:
        d["duration"] = f"{pack.days} days"
    else:
        d["duration"] = ""

    # Description (truncated, clean whitespace)
    raw_desc = " ".join(pack.description.split()) if pack.description else ""
    d["description"] = raw_desc[:440] + ("…" if len(raw_desc) > 440 else "")

    # Departures
    d["departures"] = pack.departures[:8]

    # Price
    d["price_str"] = f"{_esc(pack.currency or 'EUR')} {pack.price:,.0f}" if pack.price else ""

    # Hotels
    d["hotel_names"] = pack.hotel_names or []
    d["hotels_count"] = pack.hotels

    # Transport counts → icon+label list
    transport_items = []
    tc = pack.transport_counts or {}
    if tc:
        for key, count in tc.items():
            icon, label = TRANSPORT_ICONS.get(key, ("🚗", key.title()))
            transport_items.append((icon, f"{count}× {label}"))
    elif pack.flights:
        transport_items.append(("✈", f"{pack.flights}× Flight"))
    d["transport_items"] = transport_items

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

def _render_style_a(pack: sk.Package, agent: Agent, d: dict) -> str:

    # Gallery strip (extra photos)
    gallery_html = ""
    if d["gallery_extra"]:
        thumbs = "".join(
            f'<div class="thumb"><img src="{_esc(u)}" alt="photo"></div>'
            for u in d["gallery_extra"]
        )
        gallery_html = f'<div class="gallery-strip">{thumbs}</div>'

    # Inclusions bar: transport + hotels + duration
    incl_items = []
    for icon, txt in d["transport_items"]:
        incl_items.append(f'<div class="incl-badge"><span class="incl-icon">{icon}</span><span class="incl-text">{_esc(txt)}</span></div>')
    if d["hotels_count"]:
        hotels_label = f"{d['hotels_count']} hotel{'s' if d['hotels_count'] != 1 else ''}"
        incl_items.append(f'<div class="incl-badge"><span class="incl-icon">🏨</span><span class="incl-text">{_esc(hotels_label)}</span></div>')
    if d["duration"]:
        incl_items.append(f'<div class="incl-badge"><span class="incl-icon">🕐</span><span class="incl-text">{_esc(d["duration"])}</span></div>')
    incl_html = f'<div class="inclusions">{"".join(incl_items)}</div>' if incl_items else ""

    # Price
    price_html = ""
    if d["price_str"]:
        price_html = f"""<div class="price-box">
        <div class="price-from">From</div>
        <div class="price-amount">{d["price_str"]}</div>
        <div class="price-pp">per person</div>
      </div>"""

    # Hotel list
    hotel_html = ""
    if d["hotel_names"]:
        items = "".join(f"<li>{_esc(h)}</li>" for h in d["hotel_names"][:6])
        hotel_html = f"""<div class="section">
      <div class="section-heading"><span class="section-icon">🏨</span> Hotels</div>
      <ul class="hotel-list">{items}</ul>
    </div>"""

    # Departure chips
    dep_html = ""
    if d["departures"]:
        chips = "".join(f'<span class="dep-chip">{_esc(dep)}</span>' for dep in d["departures"])
        dep_html = f"""<div class="section">
      <div class="section-heading"><span class="section-icon">📅</span> Departure dates</div>
      <div class="dep-chips">{chips}</div>
    </div>"""

    # Contact footer extras
    contact_parts = []
    if d["agency_phone"]:
        contact_parts.append(f'<span class="footer-contact">📞 {_esc(d["agency_phone"])}</span>')
    if d["agency_email"]:
        contact_parts.append(f'<span class="footer-contact">✉ {_esc(d["agency_email"])}</span>')
    contact_html = "".join(contact_parts)

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
  position: relative; height: 310px; overflow: hidden;
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
.description-text {{ font-size: .88rem; color: #374151; line-height: 1.65; }}
.gallery-strip {{ display: flex; gap: .5rem; }}
.thumb {{ flex: 1; border-radius: 6px; overflow: hidden; height: 80px; }}
.thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.dep-chips {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
.dep-chip {{
  background: #eef2f7; border-radius: 5px; padding: .28rem .65rem;
  font-size: .8rem; color: #374151; font-weight: 500;
}}
.hotel-list {{ list-style: none; display: flex; flex-direction: column; gap: .3rem; }}
.hotel-list li {{ font-size: .85rem; color: #374151; padding-left: .8rem; position: relative; }}
.hotel-list li::before {{ content: "⭐"; position: absolute; left: 0; font-size: .7rem; top: .05rem; }}
/* Disclaimer */
.disclaimer {{
  font-size: .68rem; color: #9ca3af; line-height: 1.5;
  border-top: 1px solid #e5e7eb; padding-top: .8rem;
  font-style: italic;
}}
/* Footer */
.flyer-footer {{
  background: #0d2137; padding: 1rem 1.8rem;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0; gap: 1rem; flex-wrap: wrap;
}}
.footer-left {{ display: flex; flex-direction: column; gap: .25rem; }}
.footer-agency {{ font-size: .82rem; font-weight: 700; color: rgba(255,255,255,.9); }}
.footer-contact {{ font-size: .75rem; color: rgba(255,255,255,.6); }}
.footer-site {{ font-size: .75rem; color: rgba(255,255,255,.45); }}
.cta-btn {{
  background: #17a39b; color: #fff; border-radius: 7px;
  padding: .55rem 1.4rem; font-size: .9rem; font-weight: 800;
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
    {gallery_html}
    {hotel_html}
    {dep_html}
    <div class="disclaimer">{_esc(d["disclaimer"])}</div>
  </div>
  <div class="flyer-footer">
    <div class="footer-left">
      <span class="footer-agency">{_esc(d["agency_name"])}</span>
      {contact_html}
      {f'<span class="footer-site">{_esc(d["site"])}</span>' if d["site"] else ""}
    </div>
    {f'<a class="cta-btn" href="{_esc(d["agency_url"])}">Book now →</a>' if d["agency_url"] else ""}
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Style B — White magazine, two-column, reference screenshot inspired
# ─────────────────────────────────────────────────────────────────────────────

def _render_style_b(pack: sk.Package, agent: Agent, d: dict) -> str:

    # Two secondary photos for the right column grid
    photo2 = d["gallery_extra"][0] if len(d["gallery_extra"]) > 0 else ""
    photo3 = d["gallery_extra"][1] if len(d["gallery_extra"]) > 1 else ""
    photo4 = d["gallery_extra"][2] if len(d["gallery_extra"]) > 2 else ""

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
    elif d["duration"]:
        # fallback if no transport detail
        pass

    # Hotel list
    hotel_html = ""
    if d["hotel_names"]:
        items = "".join(f"<li>{_esc(h)}</li>" for h in d["hotel_names"][:5])
        hotel_html = f"""<div class="info-row">
        <span class="info-label">🏨 Hotels</span>
        <ul class="hotel-list">{items}</ul>
      </div>"""
    elif d["hotels_count"]:
        hotel_html = f"""<div class="info-row">
        <span class="info-label">🏨 Hotels</span>
        <span class="info-value">{d["hotels_count"]} accommodation{"s" if d["hotels_count"] != 1 else ""}</span>
      </div>"""

    # Duration row
    dur_html = ""
    if d["duration"]:
        dur_html = f"""<div class="info-row">
        <span class="info-label">🕐 Duration</span>
        <span class="info-value">{_esc(d["duration"])}</span>
      </div>"""

    # Agency contact block
    contact_rows = ""
    if d["agency_phone"]:
        contact_rows += f'<div class="contact-item"><span class="contact-icon">📞</span><span>{_esc(d["agency_phone"])}</span></div>'
    if d["agency_email"]:
        contact_rows += f'<div class="contact-item"><span class="contact-icon">✉</span><span>{_esc(d["agency_email"])}</span></div>'
    if d["site"]:
        contact_rows += f'<div class="contact-item"><span class="contact-icon">🌐</span><span>{_esc(d["site"])}</span></div>'

    # Right-column photo grid
    right_photos = ""
    if photo2:
        right_photos += f'<img class="grid-photo" src="{_esc(photo2)}" alt="photo">'
    if photo3:
        right_photos += f'<img class="grid-photo" src="{_esc(photo3)}" alt="photo">'
    if photo4:
        right_photos += f'<img class="grid-photo" src="{_esc(photo4)}" alt="photo">'

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

/* ── Top header bar ── */
.top-bar {{
  display: flex; align-items: center; justify-content: space-between;
  padding: .65rem 1.8rem; border-bottom: 3px solid #17a39b; flex-shrink: 0;
}}
.agency-logo {{ max-height: 34px; max-width: 150px; object-fit: contain; }}
.agency-name-text {{ font-weight: 800; font-size: 1rem; color: #0d2137; }}
.top-bar-right {{ text-align: right; }}
.top-tagline {{ font-size: .72rem; color: #6b7280; }}
.top-site {{ font-size: .78rem; font-weight: 600; color: #17a39b; }}

/* ── Hero strip ── */
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
.strip-dest {{
  font-size: 2rem; font-weight: 900; line-height: 1.15;
  text-shadow: 0 2px 8px rgba(0,0,0,.5);
}}
.strip-title {{
  font-size: .9rem; color: rgba(255,255,255,.78); margin-top: .35rem;
  font-weight: 400; font-style: italic;
}}

/* ── Price badge on hero ── */
.price-badge {{
  position: absolute; top: 1.2rem; right: 1.6rem;
  background: #e8163c; color: #fff; border-radius: 8px;
  padding: .6rem 1.1rem; text-align: center;
  box-shadow: 0 3px 14px rgba(0,0,0,.3);
}}
.price-badge-from {{ font-size: .62rem; text-transform: uppercase; letter-spacing: .08em; opacity: .85; }}
.price-badge-amount {{ font-size: 1.35rem; font-weight: 900; line-height: 1.1; }}
.price-badge-pp {{ font-size: .62rem; opacity: .85; }}

/* ── Two-column body ── */
.body-cols {{
  display: flex; flex: 1; overflow: hidden;
}}
.col-left {{
  flex: 1; padding: 1.4rem 1.4rem 1.4rem 1.8rem;
  display: flex; flex-direction: column; gap: 1rem;
  border-right: 1px solid #e5e7eb;
}}
.col-right {{
  width: 240px; flex-shrink: 0;
  padding: 1.4rem 1.8rem 1.4rem 1.2rem;
  display: flex; flex-direction: column; gap: .8rem;
}}

/* Info rows */
.info-row {{ display: flex; flex-direction: column; gap: .4rem; }}
.info-label {{
  font-size: .68rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: .09em; color: #9ca3af;
}}
.info-value {{ font-size: .88rem; color: #374151; font-weight: 500; }}

/* Departure pills */
.dep-pills {{ display: flex; flex-wrap: wrap; gap: .35rem; }}
.dep-pill {{
  background: #f0fafa; border: 1px solid #b2e5e2; color: #0e6b66;
  border-radius: 5px; padding: .2rem .55rem; font-size: .78rem; font-weight: 600;
}}

/* Transport grid */
.trans-grid {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
.trans-item {{
  display: flex; align-items: center; gap: .3rem;
  background: #f7f9fb; border: 1px solid #e4e8ed;
  border-radius: 5px; padding: .22rem .6rem;
}}
.trans-icon {{ font-size: .95rem; }}
.trans-txt {{ font-size: .8rem; color: #374151; font-weight: 500; }}

/* Hotel list */
.hotel-list {{ list-style: none; display: flex; flex-direction: column; gap: .3rem; }}
.hotel-list li {{
  font-size: .83rem; color: #374151; padding-left: 1rem; position: relative; line-height: 1.4;
}}
.hotel-list li::before {{ content: "★"; position: absolute; left: 0; color: #f59e0b; font-size: .75rem; top: .1rem; }}

/* Description */
.desc-text {{ font-size: .84rem; color: #4b5563; line-height: 1.65; }}

/* Right column photo grid */
.grid-photo {{
  width: 100%; border-radius: 6px; object-fit: cover;
  display: block; aspect-ratio: 4/3;
}}

/* Right column contact card */
.contact-card {{
  background: #f7f9fb; border: 1px solid #e4e8ed; border-radius: 8px;
  padding: .9rem; display: flex; flex-direction: column; gap: .45rem;
  margin-top: auto;
}}
.contact-card-title {{
  font-size: .72rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: .08em; color: #17a39b; margin-bottom: .1rem;
}}
.contact-item {{
  display: flex; align-items: flex-start; gap: .45rem;
  font-size: .8rem; color: #374151;
}}
.contact-icon {{ font-size: .9rem; flex-shrink: 0; margin-top: .05rem; }}

/* Disclaimer + footer */
.bottom-bar {{
  background: #0d2137; flex-shrink: 0;
  padding: .8rem 1.8rem;
  display: flex; align-items: center; justify-content: space-between;
  gap: 1rem;
}}
.disclaimer-text {{
  font-size: .65rem; color: rgba(255,255,255,.45); line-height: 1.5; flex: 1;
  font-style: italic;
}}
.cta-btn {{
  background: #17a39b; color: #fff; border-radius: 7px;
  padding: .5rem 1.2rem; font-size: .85rem; font-weight: 800;
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

  <!-- Top bar with logo -->
  <div class="top-bar">
    {d["logo_html"]}
    {f'<div class="top-bar-right"><div class="top-tagline">Holiday Package</div><div class="top-site">{_esc(d["site"])}</div></div>' if d["site"] else '<div class="top-bar-right"><div class="top-tagline">Holiday Package</div></div>'}
  </div>

  <!-- Hero strip -->
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

  <!-- Two-column body -->
  <div class="body-cols">
    <!-- Left: info + description -->
    <div class="col-left">
      {f'<p class="desc-text">{_esc(d["description"])}</p>' if d["description"] else ""}
      {dur_html}
      {trans_html}
      {hotel_html}
      {dep_html}
    </div>

    <!-- Right: photos + contact -->
    <div class="col-right">
      {right_photos}
      {f'''<div class="contact-card">
        <div class="contact-card-title">{_esc(d["agency_name"])}</div>
        {contact_rows}
      </div>''' if contact_rows else f'<div class="contact-card"><div class="contact-card-title">{_esc(d["agency_name"])}</div></div>'}
    </div>
  </div>

  <!-- Footer bar -->
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

def render_flyer(pack: sk.Package, agent: Agent, style: str = "a") -> str:
    """
    Render a print-ready A4 HTML flyer.
    style "a" = dark-navy editorial
    style "b" = white magazine two-column
    """
    d = _build_shared(pack, agent)
    if style == "b":
        return _render_style_b(pack, agent, d)
    return _render_style_a(pack, agent, d)
