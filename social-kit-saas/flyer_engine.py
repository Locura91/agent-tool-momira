"""
Travel Flyer generator.

Returns a self-contained HTML page (A4 layout with print CSS) that the
browser can print directly to PDF via Ctrl+P / ⌘P.
"""
from __future__ import annotations

import html
from typing import Optional
import social_kit as sk
from models import Agent


def _esc(s: object) -> str:
    return html.escape(str(s)) if s is not None else ""


def _stat(label: str, value: str) -> str:
    return f"""
    <div class="stat">
      <span class="stat-label">{_esc(label)}</span>
      <span class="stat-value">{_esc(value)}</span>
    </div>"""


def render_flyer(pack: sk.Package, agent: Agent) -> str:
    """Return a complete HTML document for the A4 flyer."""

    hero_url = pack.gallery[0] if pack.gallery else ""
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

    # Departures (first 6)
    departures = pack.departures[:6] if pack.departures else []
    dep_html = ""
    if departures:
        dep_items = "".join(f"<li>{_esc(d)}</li>" for d in departures)
        dep_html = f"""
        <div class="section">
          <div class="section-title">Departure dates</div>
          <ul class="dep-list">{dep_items}</ul>
        </div>"""

    # Themes / tags
    themes_html = ""
    if pack.themes:
        chips = "".join(f'<span class="theme-chip">{_esc(t)}</span>' for t in pack.themes[:8])
        themes_html = f'<div class="themes">{chips}</div>'

    # Price block
    price_html = ""
    if pack.price:
        price_html = f"""
        <div class="price-block">
          <span class="price-label">From</span>
          <span class="price-amount">{_esc(pack.currency or "EUR")} {pack.price:,.0f}</span>
          <span class="price-pp">per person</span>
        </div>"""

    # Stats row
    stats = []
    if pack.days:
        stats.append(_stat("Duration", f"{pack.days} days / {pack.nights} nights" if pack.nights else f"{pack.days} days"))
    if pack.flights:
        stats.append(_stat("Flights", str(pack.flights)))
    if pack.hotels:
        stats.append(_stat("Hotels", str(pack.hotels)))
    if destinations:
        stats.append(_stat("Destinations", destinations))
    stats_html = "".join(stats)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(pack.title)} — Travel Flyer</title>
<style>
  /* ── Web preview ── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #e8eaed;
    padding: 2rem 1rem;
    color: #111827;
  }}
  .a4 {{
    background: #fff;
    width: 794px;
    min-height: 1123px;
    margin: 0 auto;
    box-shadow: 0 4px 32px rgba(0,0,0,.15);
    border-radius: 4px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }}

  /* ── Hero ── */
  .hero {{
    position: relative;
    height: 300px;
    overflow: hidden;
    background: #17a39b;
  }}
  .hero img {{
    width: 100%; height: 100%; object-fit: cover; display: block;
  }}
  .hero-scrim {{
    position: absolute; inset: 0;
    background: linear-gradient(to bottom, rgba(0,0,0,.1) 0%, rgba(0,0,0,.55) 100%);
  }}
  .hero-content {{
    position: absolute; bottom: 0; left: 0; right: 0;
    padding: 1.5rem 2rem;
    color: #fff;
  }}
  .hero-title {{
    font-size: 1.8rem; font-weight: 800; line-height: 1.2;
    text-shadow: 0 1px 3px rgba(0,0,0,.4);
    margin-bottom: .4rem;
  }}
  .hero-dest {{
    font-size: .95rem; opacity: .9;
    text-shadow: 0 1px 2px rgba(0,0,0,.3);
  }}

  /* ── Body ── */
  .body {{ flex: 1; padding: 1.8rem 2rem; display: flex; flex-direction: column; gap: 1.4rem; }}

  /* Stats bar */
  .stats-bar {{
    display: flex; gap: 0; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden;
  }}
  .stat {{
    flex: 1; display: flex; flex-direction: column; gap: .2rem;
    padding: .8rem 1rem; border-right: 1px solid #e5e7eb;
  }}
  .stat:last-child {{ border-right: none; }}
  .stat-label {{ font-size: .72rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; }}
  .stat-value {{ font-size: .95rem; font-weight: 700; color: #111827; }}

  /* Price */
  .price-block {{
    display: flex; align-items: baseline; gap: .5rem;
    background: #e6f7f6; border: 1px solid #b2e5e2; border-radius: 10px;
    padding: .9rem 1.2rem;
  }}
  .price-label {{ font-size: .85rem; color: #128a81; font-weight: 600; }}
  .price-amount {{ font-size: 1.8rem; font-weight: 800; color: #17a39b; }}
  .price-pp {{ font-size: .8rem; color: #128a81; }}

  /* Sections */
  .section-title {{
    font-size: .8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .06em; color: #6b7280; margin-bottom: .6rem;
  }}
  .dep-list {{ list-style: none; display: flex; flex-wrap: wrap; gap: .4rem; }}
  .dep-list li {{
    background: #f3f4f6; border-radius: 6px; padding: .25rem .65rem;
    font-size: .82rem; color: #374151;
  }}
  .themes {{ display: flex; flex-wrap: wrap; gap: .4rem; }}
  .theme-chip {{
    background: #e6f7f6; color: #17a39b; border-radius: 6px;
    padding: .25rem .65rem; font-size: .82rem; font-weight: 600;
  }}

  /* Footer */
  .flyer-footer {{
    background: #111827; color: #fff;
    padding: 1rem 2rem;
    display: flex; align-items: center; justify-content: space-between;
  }}
  .agency-logo {{ max-height: 36px; max-width: 140px; object-fit: contain; }}
  .agency-name-text {{ font-weight: 700; font-size: 1rem; }}
  .footer-site {{ font-size: .85rem; color: rgba(255,255,255,.7); }}
  .footer-cta {{
    background: #17a39b; color: #fff; border-radius: 8px;
    padding: .5rem 1.1rem; font-size: .85rem; font-weight: 700;
    text-decoration: none;
  }}

  /* ── Print ── */
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .a4 {{ box-shadow: none; border-radius: 0; width: 100%; }}
    .no-print {{ display: none !important; }}
  }}
</style>
</head>
<body>
<div class="a4">
  <!-- Hero -->
  <div class="hero">
    {f'<img src="{_esc(hero_url)}" alt="Package photo">' if hero_url else ""}
    <div class="hero-scrim"></div>
    <div class="hero-content">
      <div class="hero-title">{_esc(pack.title)}</div>
      {f'<div class="hero-dest">📍 {_esc(destinations)}</div>' if destinations else ""}
    </div>
  </div>

  <!-- Body -->
  <div class="body">
    {f'<div class="stats-bar">{stats_html}</div>' if stats_html else ""}
    {price_html}
    {dep_html}
    {themes_html}
  </div>

  <!-- Footer -->
  <div class="flyer-footer">
    {logo_html}
    {f'<span class="footer-site">{_esc(site)}</span>' if site else ""}
    {f'<a class="footer-cta" href="{_esc(agent.agency_url or "#")}">Book now →</a>' if agent.agency_url else ""}
  </div>
</div>
</body>
</html>"""
