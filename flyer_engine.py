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
    if len(raw_desc) > 500:
        raw_desc = raw_desc[:500].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    d["description"] = raw_desc

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
# Premium editorial design system — shared by all three flyer styles
# ─────────────────────────────────────────────────────────────────────────────

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700;9..144,900'
    '&family=Inter:wght@400;500;600;700;800&display=swap">'
)

_TOKENS = """
:root{
  --ink:#0E2A3B; --ink2:#12374C; --teal:#17A39B; --teal-d:#0E6B66; --teal-l:#EAF6F5;
  --gold:#E0A43B; --paper:#FCFBF8; --line:#E7E3DC; --line2:#EEEAE2;
  --text:#26313A; --muted:#7C8894; --white:#fff;
  --serif:'Fraunces',Georgia,'Times New Roman',serif;
  --sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI','Helvetica Neue',sans-serif;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{font-family:var(--sans);background:#c9cdd3;color:var(--text);
  padding:2.5rem 1rem;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;}
.sheet{background:var(--paper);margin:0 auto;box-shadow:0 10px 50px rgba(14,42,59,.22);
  border-radius:4px;overflow:hidden;display:flex;flex-direction:column;position:relative;}
.eyebrow{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.22em;}
.stars{color:var(--gold);letter-spacing:.04em;}
img{display:block;}
@media print{ body{background:#fff;padding:0;} .sheet{box-shadow:none;border-radius:0;} }
"""

# Shared components used by every style (a style may override with a more specific selector).
_COMPONENTS = """
.h2{font-family:var(--serif);font-size:1.12rem;font-weight:600;color:var(--ink);
  display:flex;align-items:center;gap:.6rem;margin-bottom:.7rem;}
.h2::after{content:"";flex:1;height:1px;background:var(--line);}
.photo-strip{display:grid;gap:.55rem;}
.photo-strip.cols-2{grid-template-columns:1fr 1fr;}
.photo-strip.cols-3{grid-template-columns:1fr 1fr 1fr;}
.ps-cell{height:128px;border-radius:4px;overflow:hidden;background:var(--line2);}
.ps-cell img{width:100%;height:100%;object-fit:cover;}
.incl{list-style:none;display:flex;flex-direction:column;gap:.5rem;}
.incl li{display:flex;align-items:flex-start;gap:.55rem;font-size:.88rem;color:var(--text);line-height:1.4;}
.tick{width:18px;height:18px;border-radius:50%;background:var(--teal-l);color:var(--teal-d);
  font-size:.66rem;font-weight:800;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:.05rem;}
.hotel-list{list-style:none;display:flex;flex-direction:column;gap:.5rem;}
.hotel-list li{display:flex;align-items:baseline;justify-content:space-between;gap:.6rem;
  font-size:.9rem;border-bottom:1px dotted var(--line);padding-bottom:.5rem;}
.hotel-list li:last-child{border-bottom:none;}
.h-main{display:flex;align-items:baseline;gap:.5rem;min-width:0;}
.h-name{font-weight:600;color:var(--ink);}
.h-nights{font-size:.76rem;color:var(--muted);font-style:italic;flex-shrink:0;}
.act-list{list-style:none;display:flex;flex-direction:column;gap:.45rem;}
.act-list li{font-size:.88rem;color:var(--text);padding-left:1rem;position:relative;line-height:1.4;}
.act-list li::before{content:"◆";position:absolute;left:0;color:var(--gold);font-size:.6rem;top:.28rem;}
.dep-chips{display:flex;flex-wrap:wrap;gap:.45rem;}
.dep-chip{font-size:.8rem;color:var(--ink2);font-weight:500;background:var(--white);
  border:1px solid var(--line);border-radius:3px;padding:.32rem .7rem;white-space:nowrap;}
"""


def _page(title_html: str, css: str, body_html: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{title_html}</title>\n{_FONTS}\n<style>{_TOKENS}{_COMPONENTS}{css}</style>\n"
        f"</head>\n<body>\n{body_html}\n</body>\n</html>"
    )


def _fact_chips(d: dict) -> str:
    """Inline editorial fact list (duration · round trip · transport · hotels · activities)."""
    facts = []
    if d["duration"]:
        facts.append(("◷", d["duration"]))
    if d["is_round_trip"]:
        facts.append(("⇄", "Round trip"))
    for icon, txt in d["transport_items"]:
        facts.append((icon, txt))
    if d["hotels_count"]:
        facts.append(("⌂", f"{d['hotels_count']} hotel" + ("s" if d["hotels_count"] != 1 else "")))
    if d["activities"]:
        n = len(d["activities"])
        facts.append(("◆", f"{n} activit" + ("ies" if n != 1 else "y")))
    if not facts:
        return ""
    return "".join(
        f'<span class="fact"><span class="fact-i">{icon}</span>{_esc(txt)}</span>'
        for icon, txt in facts
    )


def _hotels_list(d: dict, limit: int = 6) -> str:
    if not d["hotel_items"]:
        return ""
    rows = []
    for name, nights, stars in d["hotel_items"][:limit]:
        st = f'<span class="stars">{"★" * stars}</span>' if stars else ""
        ni = f'<span class="h-nights">{nights} nights</span>' if nights else ""
        rows.append(f'<li><span class="h-main">{st}<span class="h-name">{_esc(name)}</span></span>{ni}</li>')
    return f'<ul class="hotel-list">{"".join(rows)}</ul>'


def _checklist(d: dict) -> str:
    if not d["included_items"]:
        return ""
    items = "".join(f'<li><span class="tick">✓</span>{_esc(x)}</li>' for x in d["included_items"])
    return f'<ul class="incl">{items}</ul>'


def _photo_strip(d: dict, n: int = 3) -> str:
    imgs = d["gallery_extra"][:n]
    if len(imgs) < 2:
        return ""
    cells = "".join(f'<div class="ps-cell"><img src="{_esc(u)}" alt=""></div>' for u in imgs)
    return f'<div class="photo-strip cols-{len(imgs)}">{cells}</div>'


def _qr_block(qr_uri: str, label: str = "Scan to book") -> str:
    if not qr_uri:
        return ""
    return f'<div class="qr"><img src="{qr_uri}" alt="{label}"><span>{label}</span></div>'


def _contacts(d: dict) -> str:
    parts = []
    if d["agency_phone"]:
        parts.append(f'<span class="ct"><span class="ct-i">✆</span>{_esc(d["agency_phone"])}</span>')
    if d["agency_email"]:
        parts.append(f'<span class="ct"><span class="ct-i">✉</span>{_esc(d["agency_email"])}</span>')
    if d["site"]:
        parts.append(f'<span class="ct"><span class="ct-i">◐</span>{_esc(d["site"])}</span>')
    return "".join(parts)


def _logo(d: dict, dark: bool = False) -> str:
    # d holds no logo html; rebuild from agent-derived pieces stored on d
    return d["logo_html"] if dark else d["logo_html"]


# ─────────────────────────────────────────────────────────────────────────────
# Style A — Portrait editorial (the shop-window flyer)
# ─────────────────────────────────────────────────────────────────────────────

_CSS_A = """
.sheet-a{width:794px;min-height:1123px;}
.a-head{display:flex;align-items:center;justify-content:space-between;
  padding:1.15rem 2.2rem;border-bottom:1px solid var(--line);background:var(--white);}
.a-head .agency-logo{max-height:38px;max-width:180px;object-fit:contain;}
.a-head .agency-name-text{font-family:var(--serif);font-weight:600;font-size:1.3rem;color:var(--ink);letter-spacing:.01em;}
.a-head-right{display:flex;align-items:center;gap:1rem;}
.a-site{font-size:.8rem;color:var(--muted);letter-spacing:.02em;}
.a-tag{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.18em;
  color:var(--teal-d);border:1px solid var(--teal);border-radius:2px;padding:.34rem .7rem;}
/* Hero */
.a-hero{position:relative;height:392px;overflow:hidden;background:linear-gradient(135deg,var(--ink),var(--teal-d));}
.a-hero>img{width:100%;height:100%;object-fit:cover;}
.a-hero-grad{position:absolute;inset:0;background:
  linear-gradient(to top,rgba(9,22,33,.90) 4%,rgba(9,22,33,.35) 40%,rgba(9,22,33,.05) 70%);}
.a-hero-in{position:absolute;left:0;right:0;bottom:0;padding:2.2rem 2.2rem 1.7rem;color:#fff;}
.a-hero .eyebrow{color:#8FE3DC;margin-bottom:.7rem;}
.a-h1{font-family:var(--serif);font-weight:600;font-size:2.9rem;line-height:1.04;
  letter-spacing:-.01em;text-wrap:balance;max-width:620px;text-shadow:0 2px 18px rgba(0,0,0,.35);}
.a-hero-sub{margin-top:.7rem;font-size:.98rem;color:rgba(255,255,255,.86);font-weight:500;
  display:flex;align-items:center;gap:.5rem;}
.a-hero-sub::before{content:"";width:26px;height:1px;background:var(--gold);display:inline-block;}
/* Fact + price bar */
.a-bar{display:flex;align-items:center;justify-content:space-between;gap:1.4rem;
  padding:1.05rem 2.2rem;background:var(--white);border-bottom:1px solid var(--line);flex-wrap:wrap;}
.a-facts{display:flex;flex-wrap:wrap;gap:.55rem 1.35rem;}
.fact{display:inline-flex;align-items:center;gap:.42rem;font-size:.84rem;font-weight:600;color:var(--ink2);}
.fact-i{color:var(--teal);font-size:.95rem;line-height:1;}
.a-price{text-align:right;flex-shrink:0;display:flex;align-items:baseline;gap:.5rem;}
.a-price .lab{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.16em;color:var(--muted);}
.a-price .amt{font-family:var(--serif);font-weight:600;font-size:2.05rem;color:var(--teal-d);line-height:1;}
.a-price .pp{font-size:.72rem;color:var(--muted);}
/* Body */
.a-body{flex:1;padding:1.7rem 2.2rem 1.4rem;display:flex;flex-direction:column;gap:1.5rem;}
.a-lead{font-size:1.02rem;line-height:1.62;font-weight:700;color:var(--ink);}
.a-lead::first-letter{font-family:var(--serif);}
.photo-strip{display:grid;gap:.55rem;}
.photo-strip.cols-2{grid-template-columns:1fr 1fr;}
.photo-strip.cols-3{grid-template-columns:1fr 1fr 1fr;}
.ps-cell{height:132px;border-radius:4px;overflow:hidden;background:var(--line2);}
.ps-cell img{width:100%;height:100%;object-fit:cover;}
.h2{font-family:var(--serif);font-size:1.12rem;font-weight:600;color:var(--ink);
  display:flex;align-items:center;gap:.6rem;margin-bottom:.8rem;}
.h2::after{content:"";flex:1;height:1px;background:var(--line);}
.a-two{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem 2.4rem;}
.incl{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:.5rem 1.4rem;}
.a-two .incl{grid-template-columns:1fr;}
.incl li{display:flex;align-items:flex-start;gap:.55rem;font-size:.88rem;color:var(--text);line-height:1.4;}
.tick{width:18px;height:18px;border-radius:50%;background:var(--teal-l);color:var(--teal-d);
  font-size:.66rem;font-weight:800;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:.05rem;}
.hotel-list{list-style:none;display:flex;flex-direction:column;gap:.5rem;}
.hotel-list li{display:flex;align-items:baseline;justify-content:space-between;gap:.6rem;
  font-size:.9rem;border-bottom:1px dotted var(--line);padding-bottom:.5rem;}
.hotel-list li:last-child{border-bottom:none;}
.h-main{display:flex;align-items:baseline;gap:.5rem;min-width:0;}
.stars{font-size:.82rem;flex-shrink:0;}
.h-name{font-weight:600;color:var(--ink);}
.h-nights{font-size:.76rem;color:var(--muted);font-style:italic;flex-shrink:0;}
.act-list{list-style:none;display:flex;flex-direction:column;gap:.45rem;}
.act-list li{font-size:.88rem;color:var(--text);padding-left:1rem;position:relative;line-height:1.4;}
.act-list li::before{content:"◆";position:absolute;left:0;color:var(--gold);font-size:.6rem;top:.28rem;}
.dep-chips{display:flex;flex-wrap:wrap;gap:.45rem;}
.dep-chip{font-size:.8rem;color:var(--ink2);font-weight:500;background:var(--white);
  border:1px solid var(--line);border-radius:3px;padding:.32rem .7rem;}
/* Customise callout */
.promise{display:flex;align-items:center;gap:1.1rem;margin:0 2.2rem;padding:1.05rem 1.4rem;
  background:var(--teal-l);border:1px solid #CFEBE8;border-radius:6px;}
.promise-mark{width:44px;height:44px;border-radius:50%;background:var(--teal);color:#fff;
  font-size:1.2rem;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.promise-title{font-family:var(--serif);font-weight:600;font-size:1.02rem;color:var(--teal-d);}
.promise-text{font-size:.83rem;color:var(--ink2);line-height:1.45;margin-top:.1rem;}
/* Benefits */
.benefits{display:flex;justify-content:space-around;gap:1rem;padding:1rem 2.2rem;margin-top:1.3rem;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--white);}
.benefit{display:flex;flex-direction:column;align-items:center;gap:.35rem;}
.benefit-i{font-size:1.15rem;}
.benefit-l{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--teal-d);}
.a-disc{font-size:.66rem;color:var(--muted);font-style:italic;text-align:center;padding:.9rem 2.2rem;line-height:1.5;}
/* CTA */
.cta{background:var(--ink);color:#fff;padding:1.5rem 2.2rem;display:flex;align-items:center;
  justify-content:space-between;gap:1.5rem;flex-wrap:wrap;}
.cta-hl{font-family:var(--serif);font-weight:600;font-size:1.5rem;}
.cta-agency{font-size:.92rem;color:var(--gold);font-weight:600;margin-top:.15rem;}
.cta-contacts{display:flex;flex-wrap:wrap;gap:.3rem 1.2rem;margin-top:.55rem;}
.ct{font-size:.78rem;color:rgba(255,255,255,.78);display:inline-flex;align-items:center;gap:.35rem;}
.ct-i{color:var(--teal);}
.cta-right{display:flex;align-items:center;gap:1.3rem;flex-shrink:0;}
.qr{display:flex;flex-direction:column;align-items:center;gap:.3rem;}
.qr img{width:78px;height:78px;background:#fff;padding:4px;border-radius:4px;}
.qr span{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:rgba(255,255,255,.65);}
.cta-price{text-align:right;}
.cta-price .lab{font-size:.6rem;font-weight:700;letter-spacing:.16em;color:rgba(255,255,255,.6);text-transform:uppercase;}
.cta-price .amt{font-family:var(--serif);font-weight:600;font-size:1.8rem;color:#fff;line-height:1.05;}
.cta-price .pp{font-size:.66rem;color:rgba(255,255,255,.6);}
.cta-btn{background:var(--teal);color:#fff;text-decoration:none;font-weight:700;font-size:.9rem;
  padding:.7rem 1.3rem;border-radius:4px;white-space:nowrap;}
"""


def _render_style_a(pack: sk.Package, agent: Agent, d: dict, qr_uri: str = "") -> str:
    hero_img = f'<img src="{_esc(d["hero"])}" alt="">' if d["hero"] else ""
    eyebrow = _esc(d["countries_line"] or d["destinations_line"])
    sub = f'<div class="a-hero-sub">{_esc(d["destinations_line"])}</div>' if d["destinations_line"] else ""

    facts = _fact_chips(d)
    price_bar = ""
    if d["price_str"]:
        price_bar = (f'<div class="a-price"><span class="lab">from</span>'
                     f'<span class="amt">{d["price_str"]}</span><span class="pp">/ person</span></div>')

    lead = f'<p class="a-lead">{_esc(d["description"])}</p>' if d["description"] else ""
    strip = _photo_strip(d, 3)

    incl = _checklist(d)
    incl_block = f'<div><div class="h2">What\'s included</div>{incl}</div>' if incl else ""

    hotels = _hotels_list(d)
    hotels_block = f'<div><div class="h2">Where you\'ll stay</div>{hotels}</div>' if hotels else ""
    acts_block = ""
    if d["activities"]:
        li = "".join(f"<li>{_esc(a)}</li>" for a in d["activities"][:6])
        acts_block = f'<div><div class="h2">Experiences</div><ul class="act-list">{li}</ul></div>'
    two = ""
    if hotels_block or acts_block:
        two = f'<div class="a-two">{hotels_block}{acts_block}</div>'

    dep = ""
    if d["departures"]:
        chips = "".join(f'<span class="dep-chip">{_esc(x)}</span>' for x in d["departures"])
        dep = f'<div><div class="h2">Departure dates</div><div class="dep-chips">{chips}</div></div>'

    promise = (f'<div class="promise"><div class="promise-mark">✦</div>'
               f'<div><div class="promise-title">{_esc(CUSTOMISE_TITLE)}</div>'
               f'<div class="promise-text">{_esc(CUSTOMISE_MESSAGE)}</div></div></div>')

    benefits = "".join(
        f'<div class="benefit"><span class="benefit-i">{icon}</span><span class="benefit-l">{_esc(l)}</span></div>'
        for icon, l in d["benefit_items"]
    )

    cta_price = ""
    if d["price_str"]:
        cta_price = (f'<div class="cta-price"><div class="lab">from</div>'
                     f'<div class="amt">{d["price_str"]}</div><div class="pp">per person</div></div>')
    book_btn = ""
    if d["agency_url"] and not cta_price:
        book_btn = f'<a class="cta-btn" href="{_esc(d["agency_url"])}">Book now →</a>'
    elif d["agency_url"]:
        book_btn = f'<a class="cta-btn" href="{_esc(d["agency_url"])}">Enquire →</a>'

    body = f"""<div class="sheet sheet-a">
  <header class="a-head">
    {d["logo_html"]}
    <div class="a-head-right">
      {f'<span class="a-site">{_esc(d["site"])}</span>' if d["site"] else ""}
      <span class="a-tag">Holiday Package</span>
    </div>
  </header>
  <section class="a-hero">
    {hero_img}
    <div class="a-hero-grad"></div>
    <div class="a-hero-in">
      {f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""}
      <h1 class="a-h1">{_esc(pack.title)}</h1>
      {sub}
    </div>
  </section>
  <section class="a-bar">
    <div class="a-facts">{facts}</div>
    {price_bar}
  </section>
  <main class="a-body">
    {lead}
    {strip}
    {incl_block}
    {two}
    {dep}
  </main>
  {promise}
  <div class="benefits">{benefits}</div>
  <div class="a-disc">{_esc(d["disclaimer"])}</div>
  <div class="cta">
    <div class="cta-left">
      <div class="cta-hl">Ready for this trip?</div>
      <div class="cta-agency">{_esc(d["agency_name"])}</div>
      <div class="cta-contacts">{_contacts(d)}</div>
    </div>
    <div class="cta-right">
      {_qr_block(qr_uri)}
      {cta_price}
      {book_btn}
    </div>
  </div>
</div>"""
    return _page(f"{_esc(pack.title)} — Travel Flyer", _CSS_A, body)


# ─────────────────────────────────────────────────────────────────────────────
# Style B — Magazine (light, airy two-column editorial)
# ─────────────────────────────────────────────────────────────────────────────

_CSS_B = """
.sheet-b{width:794px;min-height:1123px;background:var(--white);}
.b-hero{position:relative;height:340px;overflow:hidden;}
.b-hero>img{width:100%;height:100%;object-fit:cover;}
.b-hero-grad{position:absolute;inset:0;background:linear-gradient(to top,rgba(9,22,33,.78),rgba(9,22,33,.04) 60%);}
.b-hero-top{position:absolute;top:0;left:0;right:0;display:flex;align-items:center;justify-content:space-between;padding:1.4rem 2.4rem;}
.b-hero-top .agency-logo{max-height:40px;max-width:190px;object-fit:contain;filter:drop-shadow(0 1px 4px rgba(0,0,0,.4));}
.b-hero-top .agency-name-text{font-family:var(--serif);font-weight:600;font-size:1.3rem;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.5);}
.b-hero-tag{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.18em;color:#fff;
  border:1px solid rgba(255,255,255,.6);border-radius:2px;padding:.34rem .7rem;}
.b-hero-in{position:absolute;bottom:0;left:0;right:0;padding:2rem 2.4rem 1.6rem;color:#fff;}
.b-hero .eyebrow{color:#8FE3DC;margin-bottom:.6rem;}
.b-h1{font-family:var(--serif);font-weight:600;font-size:2.7rem;line-height:1.05;text-wrap:balance;
  max-width:600px;text-shadow:0 2px 16px rgba(0,0,0,.4);}
.b-sub{margin-top:.6rem;font-size:.95rem;color:rgba(255,255,255,.85);}
.b-cols{display:grid;grid-template-columns:1fr 300px;gap:0;flex:1;}
.b-main{padding:1.8rem 2rem 1.6rem 2.4rem;display:flex;flex-direction:column;gap:1.5rem;}
.b-side{background:var(--paper);border-left:1px solid var(--line);padding:1.8rem 1.6rem;display:flex;flex-direction:column;gap:1.45rem;}
.b-lead{font-size:1rem;line-height:1.64;font-weight:700;color:var(--ink);}
.b-price-card{background:var(--ink);color:#fff;border-radius:6px;padding:1.3rem 1.4rem;text-align:center;}
.b-price-card .lab{font-size:.64rem;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:rgba(255,255,255,.65);}
.b-price-card .amt{font-family:var(--serif);font-weight:600;font-size:2.3rem;line-height:1.1;margin:.15rem 0;}
.b-price-card .pp{font-size:.72rem;color:rgba(255,255,255,.7);}
.b-price-card .btn{display:block;margin-top:.9rem;background:var(--teal);color:#fff;text-decoration:none;
  font-weight:700;font-size:.85rem;padding:.6rem;border-radius:4px;}
.b-side .h2{font-family:var(--serif);font-size:1.02rem;font-weight:600;color:var(--ink);margin-bottom:.7rem;}
.b-side .fact{display:flex;align-items:center;gap:.5rem;font-size:.84rem;padding:.28rem 0;color:var(--ink2);}
.b-facts-list{display:flex;flex-direction:column;gap:.1rem;}
.b-qr{display:flex;flex-direction:column;align-items:center;gap:.4rem;padding-top:.4rem;}
.b-qr img{width:100px;height:100px;background:#fff;padding:5px;border:1px solid var(--line);border-radius:4px;}
.b-qr span{font-size:.64rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;}
.b-contacts{display:flex;flex-direction:column;gap:.4rem;}
.b-contacts .ct{font-size:.82rem;color:var(--ink2);display:flex;align-items:center;gap:.45rem;}
.b-contacts .ct-i{color:var(--teal);}
.b-foot{padding:1.1rem 2.4rem;background:var(--ink);color:#fff;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;}
.b-foot-agency{font-family:var(--serif);font-size:1.1rem;font-weight:600;color:#fff;}
.b-foot .promise-inline{font-size:.78rem;color:var(--gold);font-weight:600;}
.b-disc{font-size:.64rem;color:var(--muted);font-style:italic;text-align:center;padding:.7rem 2.4rem;line-height:1.5;}
"""


def _render_style_b(pack: sk.Package, agent: Agent, d: dict, qr_uri: str = "") -> str:
    hero_img = f'<img src="{_esc(d["hero"])}" alt="">' if d["hero"] else ""
    eyebrow = _esc(d["countries_line"] or d["destinations_line"])

    lead = f'<p class="b-lead">{_esc(d["description"])}</p>' if d["description"] else ""
    strip = _photo_strip(d, 3)
    incl = _checklist(d)
    incl_block = f'<div><div class="h2">What\'s included</div>{incl}</div>' if incl else ""
    hotels = _hotels_list(d)
    hotels_block = f'<div><div class="h2">Where you\'ll stay</div>{hotels}</div>' if hotels else ""
    acts_block = ""
    if d["activities"]:
        li = "".join(f"<li>{_esc(a)}</li>" for a in d["activities"][:6])
        acts_block = f'<div><div class="h2">Experiences</div><ul class="act-list">{li}</ul></div>'

    # Side facts
    side_facts = ""
    fchips = []
    if d["duration"]:
        fchips.append(("◷", d["duration"]))
    if d["is_round_trip"]:
        fchips.append(("⇄", "Round trip"))
    for icon, txt in d["transport_items"]:
        fchips.append((icon, txt))
    if d["hotels_count"]:
        fchips.append(("⌂", f"{d['hotels_count']} hotel" + ("s" if d["hotels_count"] != 1 else "")))
    if d["activities"]:
        fchips.append(("◆", f"{len(d['activities'])} experiences"))
    if fchips:
        rows = "".join(f'<div class="fact"><span class="fact-i">{i}</span>{_esc(t)}</div>' for i, t in fchips)
        side_facts = f'<div><div class="h2">At a glance</div><div class="b-facts-list">{rows}</div></div>'

    dep = ""
    if d["departures"]:
        chips = "".join(f'<span class="dep-chip">{_esc(x)}</span>' for x in d["departures"][:6])
        dep = f'<div><div class="h2">Departures</div><div class="dep-chips">{chips}</div></div>'

    price_card = ""
    if d["price_str"]:
        btn = f'<a class="btn" href="{_esc(d["agency_url"])}">Enquire now →</a>' if d["agency_url"] else ""
        price_card = (f'<div class="b-price-card"><div class="lab">from</div>'
                      f'<div class="amt">{d["price_str"]}</div><div class="pp">per person</div>{btn}</div>')

    contacts = ""
    cparts = _contacts(d)
    if cparts:
        contacts = f'<div><div class="h2">Contact</div><div class="b-contacts">{cparts}</div></div>'

    qr = ""
    if qr_uri:
        qr = f'<div class="b-qr"><img src="{qr_uri}" alt="Scan to book"><span>Scan to book</span></div>'

    body = f"""<div class="sheet sheet-b">
  <section class="b-hero">
    {hero_img}
    <div class="b-hero-grad"></div>
    <div class="b-hero-top">
      {d["logo_html"]}
      <span class="b-hero-tag">Holiday Package</span>
    </div>
    <div class="b-hero-in">
      {f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""}
      <h1 class="b-h1">{_esc(pack.title)}</h1>
      {f'<div class="b-sub">{_esc(d["destinations_line"])}</div>' if d["destinations_line"] else ""}
    </div>
  </section>
  <div class="b-cols">
    <main class="b-main">
      {lead}
      {strip}
      {incl_block}
      {hotels_block}
      {acts_block}
      {dep}
    </main>
    <aside class="b-side">
      {price_card}
      {side_facts}
      {contacts}
      {qr}
    </aside>
  </div>
  <div class="b-disc">{_esc(d["disclaimer"])}</div>
  <div class="b-foot">
    <div class="b-foot-agency">{_esc(d["agency_name"])}</div>
    <div class="promise-inline">✦ {_esc(CUSTOMISE_TITLE)} — {_esc(CUSTOMISE_MESSAGE)}</div>
  </div>
</div>"""
    return _page(f"{_esc(pack.title)} — Travel Flyer", _CSS_B, body)


# ─────────────────────────────────────────────────────────────────────────────
# Style C — Landscape panoramic A4 (4-photo mosaic, fills the page)
# ─────────────────────────────────────────────────────────────────────────────

_CSS_C = """
.sheet-c{width:1123px;height:794px;display:flex;flex-direction:column;}
.c-top{display:flex;height:45%;flex-shrink:0;}
.c-hero{position:relative;width:62%;overflow:hidden;background:linear-gradient(135deg,var(--ink),var(--teal-d));}
.c-hero>img{width:100%;height:100%;object-fit:cover;}
.c-hero-grad{position:absolute;inset:0;background:
  linear-gradient(to top,rgba(9,22,33,.9) 6%,rgba(9,22,33,.25) 46%,transparent 72%),
  linear-gradient(to right,rgba(9,22,33,.5),transparent 42%);}
.c-hero-logo{position:absolute;top:1.4rem;left:1.8rem;}
.c-hero-logo .agency-logo{max-height:38px;max-width:170px;object-fit:contain;filter:drop-shadow(0 1px 5px rgba(0,0,0,.5));}
.c-hero-logo .agency-name-text{font-family:var(--serif);font-weight:600;font-size:1.2rem;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.5);}
.c-hero-in{position:absolute;left:0;right:0;bottom:0;padding:1.8rem 1.9rem;color:#fff;}
.c-hero .eyebrow{color:#8FE3DC;margin-bottom:.55rem;}
.c-h1{font-family:var(--serif);font-weight:600;font-size:2.5rem;line-height:1.03;text-wrap:balance;
  max-width:560px;text-shadow:0 2px 14px rgba(0,0,0,.4);}
.c-hero-sub{margin-top:.55rem;font-size:.92rem;color:rgba(255,255,255,.86);display:flex;gap:.9rem;flex-wrap:wrap;}
.c-hero-sub .pill{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);
  border-radius:3px;padding:.22rem .6rem;font-size:.76rem;font-weight:600;backdrop-filter:blur(2px);}
.c-mosaic{width:38%;display:grid;grid-template-rows:1fr 1fr;grid-template-columns:1fr 1fr;gap:3px;background:var(--paper);}
.c-mosaic .m0{grid-column:1 / span 2;}
.c-mosaic .cell{overflow:hidden;background:var(--line2);}
.c-mosaic .cell img{width:100%;height:100%;object-fit:cover;}
.c-bottom{flex:1;min-height:0;display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:0;border-top:3px solid var(--teal);}
.c-col{padding:1.25rem 1.5rem;border-right:1px solid var(--line);display:flex;flex-direction:column;gap:.55rem;overflow:hidden;}
.c-col:last-child{border-right:none;}
.c-col .h2{font-family:var(--serif);font-size:1rem;font-weight:600;color:var(--ink);
  display:flex;align-items:center;gap:.5rem;margin-bottom:.35rem;}
.c-col .h2::after{content:"";flex:1;height:1px;background:var(--line);}
.c-lead{font-size:.86rem;line-height:1.55;font-weight:700;color:var(--ink);}
.c-col .incl{list-style:none;display:flex;flex-direction:column;gap:.4rem;}
.c-col .incl li{display:flex;align-items:flex-start;gap:.5rem;font-size:.83rem;color:var(--text);line-height:1.35;}
.c-col .tick{width:17px;height:17px;border-radius:50%;background:var(--teal-l);color:var(--teal-d);
  font-size:.62rem;font-weight:800;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:.05rem;}
.c-col .hotel-list{list-style:none;display:flex;flex-direction:column;gap:.42rem;}
.c-col .hotel-list li{display:flex;align-items:baseline;justify-content:space-between;gap:.5rem;
  font-size:.84rem;border-bottom:1px dotted var(--line);padding-bottom:.4rem;}
.c-col .hotel-list li:last-child{border-bottom:none;}
.c-col .h-main{display:flex;align-items:baseline;gap:.45rem;min-width:0;}
.c-col .h-name{font-weight:600;color:var(--ink);}
.c-col .h-nights{font-size:.72rem;color:var(--muted);font-style:italic;flex-shrink:0;}
.c-col .act-list{list-style:none;display:flex;flex-direction:column;gap:.35rem;}
.c-col .act-list li{font-size:.82rem;color:var(--text);padding-left:.9rem;position:relative;line-height:1.35;}
.c-col .act-list li::before{content:"◆";position:absolute;left:0;color:var(--gold);font-size:.55rem;top:.28rem;}
/* CTA band across the very bottom */
.c-cta{background:var(--ink);color:#fff;display:flex;align-items:center;gap:1.3rem;padding:0 1.9rem;
  height:120px;flex-shrink:0;overflow:hidden;}
.c-cta .price{display:flex;flex-direction:column;flex-shrink:0;}
.c-cta .price .lab{font-size:.58rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:rgba(255,255,255,.6);}
.c-cta .price .amt{font-family:var(--serif);font-weight:600;font-size:1.7rem;line-height:1.05;}
.c-cta .price .pp{font-size:.62rem;color:rgba(255,255,255,.6);}
.c-cta .sep{width:1px;align-self:stretch;background:rgba(255,255,255,.18);}
.c-cta .agency{flex-shrink:0;}
.c-cta .agency .nm{font-family:var(--serif);font-size:1.05rem;font-weight:600;}
.c-cta .agency .cts{display:flex;flex-direction:column;gap:.12rem;margin-top:.3rem;}
.c-cta .ct{font-size:.72rem;color:rgba(255,255,255,.75);display:inline-flex;align-items:center;gap:.35rem;white-space:nowrap;}
.c-cta .ct-i{color:var(--teal);}
.c-cta .promise{flex:1;min-width:0;display:flex;align-items:center;gap:.65rem;background:transparent;border:none;margin:0;padding:0;color:rgba(255,255,255,.9);}
.c-cta .promise>div{min-width:0;}
.c-cta .promise .promise-mark{width:34px;height:34px;font-size:.95rem;background:var(--teal);flex-shrink:0;}
.c-cta .promise .promise-title{color:var(--gold);font-size:.9rem;}
.c-cta .promise .promise-text{color:rgba(255,255,255,.78);font-size:.71rem;line-height:1.35;margin-top:.1rem;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.c-cta .qr{flex-shrink:0;}
.c-cta .qr img{width:64px;height:64px;background:#fff;padding:3px;border-radius:4px;}
.c-cta .qr span{font-size:.55rem;color:rgba(255,255,255,.6);text-transform:uppercase;letter-spacing:.08em;}
.c-cta .btn{background:var(--teal);color:#fff;text-decoration:none;font-weight:700;font-size:.85rem;
  padding:.65rem 1.2rem;border-radius:4px;white-space:nowrap;flex-shrink:0;}
@media print{ @page{size:A4 landscape;margin:0;} }
"""


def _render_style_c(pack: sk.Package, agent: Agent, d: dict, qr_uri: str = "") -> str:
    hero_img = f'<img src="{_esc(d["hero"])}" alt="">' if d["hero"] else ""
    eyebrow = _esc(d["countries_line"] or d["destinations_line"])

    # Mosaic — 3 additional photos (hero is #1, so 4 images total)
    extra = d["gallery_extra"][:3]
    mcells = ""
    if extra:
        classes = ["m0", "m1", "m2"]
        mcells = "".join(
            f'<div class="cell {classes[i]}"><img src="{_esc(u)}" alt=""></div>'
            for i, u in enumerate(extra)
        )
    else:
        mcells = '<div class="cell m0"></div>'
    mosaic = f'<div class="c-mosaic">{mcells}</div>'

    # Hero sub pills
    pills = []
    if d["duration"]:
        pills.append(d["duration"])
    if d["is_round_trip"]:
        pills.append("Round trip")
    for _icon, txt in d["transport_items"][:3]:
        pills.append(txt)
    pills_html = "".join(f'<span class="pill">{_esc(p)}</span>' for p in pills)

    # Column 1: description + included
    incl = _checklist(d)
    desc_c = d["description"]
    if len(desc_c) > 210:
        desc_c = desc_c[:210].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    lead = f'<p class="c-lead">{_esc(desc_c)}</p>' if d["description"] else ""
    col1 = f'<div class="c-col"><div class="h2">What\'s included</div>{lead}{incl}</div>'

    # Column 2: hotels
    hotels = _hotels_list(d, 5)
    col2 = f'<div class="c-col"><div class="h2">Where you&#39;ll stay</div>{hotels}</div>'

    # Column 3: experiences + departures
    acts = ""
    if d["activities"]:
        li = "".join(f"<li>{_esc(a)}</li>" for a in d["activities"][:5])
        acts = f'<ul class="act-list">{li}</ul>'
    dep = ""
    if d["departures"]:
        chips = "".join(f'<span class="dep-chip">{_esc(x)}</span>' for x in d["departures"][:5])
        dep = f'<div style="margin-top:.5rem"><div class="h2">Departures</div><div class="dep-chips">{chips}</div></div>'
    col3 = f'<div class="c-col"><div class="h2">Experiences</div>{acts}{dep}</div>'

    # CTA
    price = ""
    if d["price_str"]:
        price = (f'<div class="price"><span class="lab">from</span>'
                 f'<span class="amt">{d["price_str"]}</span><span class="pp">per person</span></div>'
                 f'<div class="sep"></div>')
    agency = (f'<div class="agency"><div class="nm">{_esc(d["agency_name"])}</div>'
              f'<div class="cts">{_contacts(d)}</div></div><div class="sep"></div>')
    promise = (f'<div class="promise"><div class="promise-mark">✦</div>'
               f'<div><div class="promise-title">{_esc(CUSTOMISE_TITLE)}</div>'
               f'<div class="promise-text">{_esc(CUSTOMISE_MESSAGE)}</div></div></div>')
    qr = _qr_block(qr_uri)
    btn = f'<a class="btn" href="{_esc(d["agency_url"])}">Book now →</a>' if d["agency_url"] else ""

    body = f"""<div class="sheet sheet-c">
  <div class="c-top">
    <section class="c-hero">
      {hero_img}
      <div class="c-hero-grad"></div>
      <div class="c-hero-logo">{d["logo_html"]}</div>
      <div class="c-hero-in">
        {f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""}
        <h1 class="c-h1">{_esc(pack.title)}</h1>
        <div class="c-hero-sub">{pills_html}</div>
      </div>
    </section>
    {mosaic}
  </div>
  <div class="c-bottom">
    {col1}
    {col2}
    {col3}
  </div>
  <div class="c-cta">
    {price}
    {agency}
    {promise}
    {qr}
    {btn}
  </div>
</div>"""
    return _page(f"{_esc(pack.title)} — Travel Flyer", _CSS_C, body)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_flyer(pack: sk.Package, agent: Agent, style: str = "a", show_qr: bool = False) -> str:
    """
    Render a print-ready A4 HTML flyer in a premium editorial style.
    style "a" = portrait editorial (shop-window flyer)
    style "b" = light magazine two-column
    style "c" = panoramic landscape, 4-photo mosaic
    show_qr   = embed a QR code linking to the agency website
    """
    d = _build_shared(pack, agent)
    qr_uri = _qr_data_uri(d["agency_url"]) if (show_qr and d["agency_url"]) else ""
    if style == "b":
        return _render_style_b(pack, agent, d, qr_uri)
    if style == "c":
        return _render_style_c(pack, agent, d, qr_uri)
    return _render_style_a(pack, agent, d, qr_uri)
