"""
Per-agent wrapper around social_kit.py.

social_kit.py is untouched (it stays a clean library for the Momira TC tool
and for any scheduled jobs that iterate both brands).  This module adapts it
for the SaaS context: one agent = one implicit brand, with a logo image on
the poster instead of a text wordmark.

Key decisions:
  - Every agent uses Momira's TC credentials (TRAVELC_* env vars).
  - Language / currency are always English / EUR (Momira Travel defaults).
  - The Brand's wordmark is set to "" so social_kit.render() does not draw
    a text pill.  We composite the agent's logo image over the finished
    poster ourselves.
  - If the agent has no logo yet, we draw the agency name as a text pill
    (same position, same style as the original wordmark).
  - The ribbon (NEW / SALE / BESTSELLER / HOT or free text) is composited
    over the top-right corner after the logo.
"""

from __future__ import annotations

import io
from typing import Optional
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont

import social_kit as sk
from models import Agent

# Re-export so callers need only import this module
TCClient = sk.TCClient
TCError = sk.TCError
Package = sk.Package


# --------------------------------------------------------------------------
# Brand factory
# --------------------------------------------------------------------------

def agent_brand(agent: Agent) -> sk.Brand:
    """
    Build a social_kit Brand from an Agent row.

    wordmark="" suppresses the teal text pill; we paint the logo instead.
    site drives the URL shown at the bottom of photo-first posters.
    caption_lang / tc_lang / currency come from the agent's settings so each
    agency can generate captions and posters in their own language and currency.
    """
    site = agent.agency_site or (
        urlparse(agent.agency_url).netloc if agent.agency_url else ""
    )
    caption_lang = (agent.caption_lang or "en").lower()
    tc_lang = (agent.tc_lang or "EN").upper()
    currency = agent.currency or "EUR"

    # Ensure caption_lang and tc_lang stay in sync if only one is set
    _lang_map = {"en": "EN", "pl": "PL", "de": "DE", "es": "ES", "fr": "FR", "it": "IT", "nl": "NL"}
    _tc_map = {v: k for k, v in _lang_map.items()}
    if caption_lang not in sk._COPY:
        caption_lang = "en"
    tc_lang = _lang_map.get(caption_lang, "EN")

    return sk.Brand(
        key=agent.id,
        name=agent.agency_name or "Travel Agent",
        lang=caption_lang,
        tc_lang=tc_lang,
        currency=currency,
        site=site,
        wordmark="",         # suppressed — logo image drawn separately
        url=agent.agency_url or "https://momira.travel/",
        tags=(),
    )


# --------------------------------------------------------------------------
# Logo loading (cached per URL in memory for the request lifetime)
# --------------------------------------------------------------------------

def _load_image_url(url: str) -> Image.Image:
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGBA")


# --------------------------------------------------------------------------
# Post-process: logo + ribbon
# --------------------------------------------------------------------------

_FONT_DIR = sk._FONT_DIR   # reuse the same font directory


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return sk._font(weight, size)


BRAND_COLOR = sk.BRAND        # (23, 163, 152) teal
WHITE = (255, 255, 255)
DARK_GREY = (30, 30, 30)

_RIBBON_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "NEW":        ((0, 168, 107),   WHITE),
    "SALE":       ((220, 38, 38),   WHITE),
    "BESTSELLER": ((202, 138, 4),   WHITE),
    "HOT":        ((234, 88, 12),   WHITE),
    "_default":   (DARK_GREY,       WHITE),
}


def _composite_logo(canvas: Image.Image, logo_img: Image.Image, unit: float) -> None:
    """
    Paste the agent's logo in the top-left corner, inside a white pill
    that mirrors where the text wordmark would sit.

    The logo is scaled to fit a max height of 44*unit pixels while keeping
    its aspect ratio; a 12*unit horizontal padding is added on each side.
    """
    max_h = int(44 * unit)
    aspect = logo_img.width / logo_img.height
    logo_h = min(max_h, logo_img.height)
    logo_w = int(logo_h * aspect)
    logo_scaled = logo_img.resize((logo_w, logo_h), Image.LANCZOS)

    pad_x = int(20 * unit)
    pad_y = int(20 * unit)
    pill_pad = int(14 * unit)
    pill_w = logo_w + pill_pad * 2
    pill_h = logo_h + int(12 * unit)
    radius = pill_h // 2

    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pill)
    draw.rounded_rectangle([0, 0, pill_w, pill_h], radius=radius, fill=(255, 255, 255, 240))
    logo_x = pill_pad
    logo_y = (pill_h - logo_h) // 2
    pill.paste(logo_scaled, (logo_x, logo_y), logo_scaled if logo_scaled.mode == "RGBA" else None)

    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.paste(pill, (pad_x, pad_y), pill)
    canvas.paste(canvas_rgba.convert("RGB"), (0, 0))


def _draw_text_wordmark(canvas: Image.Image, text: str, unit: float) -> None:
    """Fallback when the agent has no logo: draw their name as a teal pill."""
    draw = ImageDraw.Draw(canvas)
    font = _font("bold", int(22 * unit))
    sk._pill(draw, (int(72 * unit), int(72 * unit)), text, font, BRAND_COLOR, WHITE, int(24 * unit))


def _composite_ribbon(canvas: Image.Image, label: str, unit: float) -> None:
    """
    Draw a ribbon badge in the top-right corner.

    A rounded rectangle with the label, coloured by preset or dark grey for
    free text.  The badge sits just inside the same top padding as the logo.
    """
    bg, fg = _RIBBON_COLORS.get(label.upper(), _RIBBON_COLORS["_default"])
    font = _font("bold", int(22 * unit))
    draw = ImageDraw.Draw(canvas)

    pad_x = int(20 * unit)
    pad_y = int(20 * unit)
    text_w = int(draw.textlength(label.upper(), font=font))
    badge_pad = int(20 * unit)
    badge_w = text_w + badge_pad * 2
    badge_h = int(font.size * 2.4)
    x = canvas.width - pad_x - badge_w

    draw.rounded_rectangle([x, pad_y, x + badge_w, pad_y + badge_h], radius=badge_h // 2, fill=bg)
    draw.text((x + badge_pad, pad_y + badge_h / 2), label.upper(), font=font, fill=fg, anchor="lm")


# --------------------------------------------------------------------------
# Public rendering entry point
# --------------------------------------------------------------------------

def render_for_agent(
    pack: Package,
    agent: Agent,
    fmt: str = "square",
    style: str = "photo",
    photo: Optional[Image.Image] = None,
    focus: str = "center",
    zoom: float = 1.0,
) -> Image.Image:
    """
    Full pipeline: social_kit.render() → logo composite → ribbon composite.

    Returns a finished PIL Image ready for to_jpeg().
    """
    brand = agent_brand(agent)

    canvas = sk.render(
        pack=pack,
        fmt=fmt,
        style=style,
        photo=photo,
        focus=focus,
        zoom=zoom,
        brand=brand,
        pln_rate=None,
    )

    width, _height, _ = sk.FORMATS[fmt]
    unit = width / 1080

    # --- logo or text wordmark ---
    if agent.logo_url:
        try:
            logo_img = _load_image_url(agent.logo_url)
            _composite_logo(canvas, logo_img, unit)
        except Exception:
            # Bad URL / network error: fall back to text
            if agent.agency_name:
                _draw_text_wordmark(canvas, agent.agency_name, unit)
    elif agent.agency_name:
        _draw_text_wordmark(canvas, agent.agency_name, unit)

    # --- ribbon ---
    ribbon = agent.ribbon_label()
    if ribbon:
        _composite_ribbon(canvas, ribbon, unit)

    return canvas
