"""
Travel Flyer generator.

Returns a self-contained HTML page (A4 layout with print CSS) that the
browser can print directly to PDF via Ctrl+P / ⌘P.
"""
from __future__ import annotations

import html
import textwrap
from typing import Optional
import social_kit as sk
from models import Agent


def _esc(s: object) -> str:
    return html.escape(str(s)) if s is not None else ""


def render_flyer(pack: sk.Package, agent: Agent) -> str:
    """Return a complete HTML document for the redesigned A4 flyer."""

    hero_url = pack.gallery[0] if pack.gallery else ""
    gallery_extra = pack.gallery[1:4]  # up to 3 more thumbnails

    logo_html = (
        f'<img class="agency-logo" src="{_esc(agent.logo_url)}" alt="{_esc(agent.agency_name)}">'
        if agent.logo_url
        else f'<span class="agency-name-text">{_esc(agent.agency_name or "Travel Agent")}</span>'
    )

    site = agent.agency_site or ""
    if not site and agent.agency_url:
        from urllib.parse import urlparse
        site = urlparse(agent.agency_url).netloc

    # Destinations
    destinations = ", ".join(
        d.get("name", str(d)) if isinstance(d, dict) else str(d)
        for d in (pack.destinations or [])
    )

    # Duration string
    if pack.days and pack.nights:
        duration = f"{pack.days} days / {pack.nights} nights"
    elif pack.days:
        duration = f"{pack.days} days"
    else:
        duration = ""

    # Description – wrap to ~90 chars, max 4 lines for print
    description = ""
    if pack.description:
        # Strip to ~400 chars, clean whitespace
        raw = " ".join(pack.description.split())
        description = raw[:420] + ("…" if len(raw) > 420 else "")

    # Departures (show up to 8)
    departures = pack.departures[:8] if pack.departures else []
    dep_html = ""
    if departures:
        dep_items = "".join(
            f'<span class="dep-chip">{_esc(d)}</span>' for d in departures
        )
        dep_html = f"""
    <div class="section">
      <div class="section-heading">
        <span class="section-icon">📅</span> Departure dates
      </div>
      <div class="dep-chips">{dep_items}</div>
    </div>"""

    # Themes / tags
    themes_html = ""
    if pack.themes:
        chips = "".join(
            f'<span class="theme-chip">{_esc(t)}</span>'
            for t in pack.themes[:10]
        )
        themes_html = f"""
    <div class="section">
      <div class="section-heading">
        <span class="section-icon">🏷</span> Holiday type
      </div>
      <div class="themes">{chips}</div>
    </div>"""

    # Description section
    desc_html = ""
    if description:
        desc_html = f"""
    <div class="section description-section">
      <p class="description-text">{_esc(description)}</p>
    </div>"""

    # Gallery strip
    gallery_html = ""
    if gallery_extra:
        thumbs = "".join(
            f'<div class="thumb"><img src="{_esc(u)}" alt="photo"></div>'
            for u in gallery_extra
        )
        gallery_html = f'<div class="gallery-strip">{thumbs}</div>'

    # Inclusions badge row
    inclusions = []
    if pack.flights:
        inclusions.append(("✈️", f"{pack.flights} flight{'s' if pack.flights > 1 else ''}"))
    if pack.hotels:
        inclusions.append(("🏨", f"{pack.hotels} hotel{'s' if pack.hotels > 1 else ''}"))
    if duration:
        inclusions.append(("🕐", duration))

    incl_html = ""
    if inclusions:
        badges = "".join(
            f'<div class="incl-badge"><span class="incl-icon">{ic}</span><span class="incl-text">{_esc(txt)}</span></div>'
            for ic, txt in inclusions
        )
        incl_html = f'<div class="inclusions">{badges}</div>'

    # Price
    price_html = ""
    if pack.price:
        currency = pack.currency or "EUR"
        price_html = f"""
      <div class="price-box">
        <div class="price-from">From</div>
        <div class="price-amount">{_esc(currency)} {pack.price:,.0f}</div>
        <div class="price-pp">per person</div>
      </div>"""

    # Book-now CTA
    book_url = agent.agency_url or "#"
    cta_html = f'<a class="cta-btn" href="{_esc(book_url)}">Book now →</a>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(pack.title)} — Travel Flyer</title>
<style>
/* ─── Reset ─────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

/* ─── Web preview shell ──────────────────────────────────── */
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif;
  background: #c9cdd3;
  padding: 2.5rem 1rem;
  color: #1a1a2e;
}}

/* ─── A4 card ────────────────────────────────────────────── */
.a4 {{
  background: #fff;
  width: 794px;
  min-height: 1123px;
  margin: 0 auto;
  box-shadow: 0 8px 48px rgba(0,0,0,.22);
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}}

/* ─── Header bar ─────────────────────────────────────────── */
.flyer-header {{
  background: #0d2137;
  padding: .7rem 1.8rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}}
.agency-logo {{ max-height: 34px; max-width: 150px; object-fit: contain; }}
.agency-name-text {{ font-weight: 800; font-size: 1rem; color: #fff; letter-spacing: .02em; }}
.header-site {{ font-size: .78rem; color: rgba(255,255,255,.55); }}
.header-badge {{
  background: #17a39b;
  color: #fff;
  border-radius: 4px;
  padding: .25rem .7rem;
  font-size: .72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .08em;
}}

/* ─── Hero ───────────────────────────────────────────────── */
.hero {{
  position: relative;
  height: 310px;
  overflow: hidden;
  background: linear-gradient(135deg, #0d2137 0%, #17a39b 100%);
  flex-shrink: 0;
}}
.hero img {{
  width: 100%; height: 100%; object-fit: cover; display: block;
}}
/* gradient scrim: dark bottom for text, subtle top-left vignette */
.hero-scrim {{
  position: absolute; inset: 0;
  background:
    linear-gradient(to top, rgba(10,18,35,.8) 0%, transparent 52%),
    linear-gradient(to bottom-right, rgba(10,18,35,.25) 0%, transparent 45%);
}}
.hero-text {{
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 1.4rem 1.8rem;
  color: #fff;
}}
.hero-eyebrow {{
  font-size: .72rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .1em; color: #5eddd7; margin-bottom: .45rem;
}}
.hero-title {{
  font-size: 1.75rem; font-weight: 900; line-height: 1.2;
  text-shadow: 0 1px 6px rgba(0,0,0,.45);
  margin-bottom: .4rem;
  max-width: 540px;
}}
.hero-dest {{
  font-size: .88rem; color: rgba(255,255,255,.82);
  text-shadow: 0 1px 3px rgba(0,0,0,.3);
}}

/* ─── Inclusions + price row ─────────────────────────────── */
.highlights-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.8rem;
  background: #f7f9fb;
  border-bottom: 1px solid #e4e8ed;
  flex-shrink: 0;
  gap: 1rem;
  flex-wrap: wrap;
}}
.inclusions {{
  display: flex; gap: .6rem; flex-wrap: wrap;
}}
.incl-badge {{
  display: flex; align-items: center; gap: .35rem;
  background: #fff; border: 1px solid #dce1e8;
  border-radius: 6px; padding: .35rem .75rem;
}}
.incl-icon {{ font-size: 1rem; line-height: 1; }}
.incl-text {{ font-size: .8rem; font-weight: 600; color: #374151; }}

/* Price box (right side of highlights-row) */
.price-box {{
  text-align: right; flex-shrink: 0;
}}
.price-from {{ font-size: .7rem; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: .06em; }}
.price-amount {{ font-size: 1.7rem; font-weight: 900; color: #17a39b; line-height: 1.1; }}
.price-pp {{ font-size: .72rem; color: #6b7280; }}

/* ─── Body ───────────────────────────────────────────────── */
.flyer-body {{
  flex: 1;
  padding: 1.4rem 1.8rem;
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}}

/* Section headings */
.section-heading {{
  font-size: .72rem; font-weight: 800; text-transform: uppercase;
  letter-spacing: .09em; color: #9ca3af; margin-bottom: .55rem;
  display: flex; align-items: center; gap: .3rem;
}}
.section-icon {{ font-size: .9rem; }}

/* Description */
.description-text {{
  font-size: .88rem; color: #374151; line-height: 1.65;
}}

/* Gallery strip */
.gallery-strip {{
  display: flex; gap: .5rem;
}}
.thumb {{
  flex: 1; border-radius: 6px; overflow: hidden;
  height: 80px;
}}
.thumb img {{
  width: 100%; height: 100%; object-fit: cover; display: block;
}}

/* Departure chips */
.dep-chips {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
.dep-chip {{
  background: #eef2f7; border-radius: 5px;
  padding: .28rem .65rem; font-size: .8rem;
  color: #374151; font-weight: 500;
}}

/* Theme chips */
.themes {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
.theme-chip {{
  background: #e6f7f6; color: #0e8880;
  border-radius: 5px; padding: .28rem .65rem;
  font-size: .8rem; font-weight: 700;
}}

/* ─── Footer ─────────────────────────────────────────────── */
.flyer-footer {{
  background: #0d2137;
  padding: 1rem 1.8rem;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
  gap: 1rem;
}}
.footer-left {{
  display: flex; flex-direction: column; gap: .2rem;
}}
.footer-agency {{
  font-size: .82rem; font-weight: 700; color: rgba(255,255,255,.9);
}}
.footer-site {{
  font-size: .75rem; color: rgba(255,255,255,.45);
}}
.cta-btn {{
  background: #17a39b; color: #fff;
  border-radius: 7px; padding: .55rem 1.4rem;
  font-size: .9rem; font-weight: 800;
  text-decoration: none; white-space: nowrap;
  letter-spacing: .01em;
}}
.cta-btn:hover {{ background: #0e8880; }}

/* ─── Print ──────────────────────────────────────────────── */
@media print {{
  body {{ background: #fff; padding: 0; }}
  .a4 {{
    box-shadow: none; border-radius: 0;
    width: 100%; min-height: 0;
  }}
  .no-print {{ display: none !important; }}
}}
</style>
</head>
<body>

<div class="a4">

  <!-- Top agency bar -->
  <div class="flyer-header">
    {logo_html}
    {f'<span class="header-site">{_esc(site)}</span>' if site else ""}
    <span class="header-badge">Holiday Package</span>
  </div>

  <!-- Hero photo -->
  <div class="hero">
    {f'<img src="{_esc(hero_url)}" alt="Package photo">' if hero_url else ""}
    <div class="hero-scrim"></div>
    <div class="hero-text">
      {f'<div class="hero-eyebrow">📍 {_esc(destinations)}</div>' if destinations else ""}
      <div class="hero-title">{_esc(pack.title)}</div>
    </div>
  </div>

  <!-- Inclusions + price bar -->
  <div class="highlights-row">
    {incl_html}
    {price_html}
  </div>

  <!-- Body content -->
  <div class="flyer-body">
    {desc_html}
    {gallery_html}
    {dep_html}
    {themes_html}
  </div>

  <!-- Footer with CTA -->
  <div class="flyer-footer">
    <div class="footer-left">
      <span class="footer-agency">{_esc(agent.agency_name or "Travel Agent")}</span>
      {f'<span class="footer-site">{_esc(site)}</span>' if site else ""}
    </div>
    {f'<a class="cta-btn" href="{_esc(book_url)}">Book now →</a>' if agent.agency_url else ""}
  </div>

</div>

</body>
</html>"""
