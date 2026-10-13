"""
Travel Agent Kit — FastAPI application.

Agents log in, upload their logo, set an optional ribbon, paste a Travel
Compositor Holiday Package ID, and get captions + poster images back.
All agents share Momira's TC credentials; each sees only their own account.
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import social_kit as sk
import kit_engine as engine
import r2_upload
import flyer_engine
import video_kit as vk
import mailer
import re as _re


def _dl_slug(s: str, fallback: str = "momira-travel") -> str:
    """A filesystem-friendly slug for download filenames."""
    s = _re.sub(r"[^A-Za-z0-9]+", "-", (s or "")).strip("-").lower()
    return s or fallback


def _download_name(pack, agent, ext: str) -> str:
    """Every download is named with the tour and the agency, e.g.
    8-days-zante-cruise-momira-travel.jpg"""
    return f"{_dl_slug(getattr(pack, 'title', ''), 'tour')}-{_dl_slug(agent.agency_name)}.{ext}"


from auth import (
    create_access_token,
    current_agent,
    hash_password,
    verify_password,
)
from database import get_db, init_db
from models import Agent, Registration
from schemas import (
    AgentProfile,
    GenerateRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
)

# --------------------------------------------------------------------------
# App setup
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Travel Agent Kit",
    description="A Holiday Package ID in — three captions and a finished post image out.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static frontend from /static → /
app.mount("/static", StaticFiles(directory="static"), name="static")


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------
# TC debug — diagnose credential / base-URL problems without Render console
# --------------------------------------------------------------------------

@app.get("/debug/tc")
async def debug_tc(agent: Agent = Depends(current_agent)):
    """
    Shows what TC credentials the app sees and whether authentication works.
    Safe to expose: the password is masked and no package data is returned.
    """
    import os as _os
    base = _os.environ.get("TRAVELC_BASE_URL", "NOT SET")
    microsite = _os.environ.get("TRAVELC_MICROSITE_ID", "NOT SET")
    username = _os.environ.get("TRAVELC_USERNAME", "NOT SET")
    password_set = bool(_os.environ.get("TRAVELC_PASSWORD"))

    auth_ok = False
    auth_error = None
    try:
        client = sk.TCClient()
        client.authenticate()
        auth_ok = True
    except sk.TCError as e:
        auth_error = str(e)

    return {
        "TRAVELC_BASE_URL": base,
        "TRAVELC_MICROSITE_ID": microsite,
        "TRAVELC_USERNAME": username,
        "TRAVELC_PASSWORD_SET": password_set,
        "auth_ok": auth_ok,
        "auth_error": auth_error,
    }


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/login.html", encoding="utf-8") as f:
        return f.read()


@app.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Agent).where(Agent.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with that email already exists.")

    agent = Agent(
        email=req.email,
        password_hash=hash_password(req.password),
        agency_name=req.agency_name,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return TokenResponse(access_token=create_access_token(agent.id))


@app.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.email == req.email, Agent.is_active == True))
    agent = result.scalar_one_or_none()

    if not agent or not verify_password(req.password, agent.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return TokenResponse(access_token=create_access_token(agent.id))


@app.post("/auth/guest", response_model=TokenResponse)
async def guest_login(db: AsyncSession = Depends(get_db)):
    """Auto-login as a built-in guest/demo account for testing."""
    GUEST_EMAIL = "guest@momira.demo"
    result = await db.execute(select(Agent).where(Agent.email == GUEST_EMAIL))
    agent = result.scalar_one_or_none()
    if not agent:
        agent = Agent(
            email=GUEST_EMAIL,
            password_hash=hash_password("guest-demo-2026"),
            agency_name="Momira Travel",
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
    elif agent.agency_name in (None, "", "Momira Demo"):
        # Fix up the demo account name for existing rows
        agent.agency_name = "Momira Travel"
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
    return TokenResponse(access_token=create_access_token(agent.id))


# --------------------------------------------------------------------------
# Agent profile
# --------------------------------------------------------------------------

@app.get("/me", response_model=AgentProfile)
async def get_profile(agent: Agent = Depends(current_agent)):
    return agent


@app.patch("/me", response_model=AgentProfile)
async def update_profile(
    req: UpdateProfileRequest,
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    if req.agency_name is not None:
        agent.agency_name = req.agency_name
    if req.agency_url is not None:
        agent.agency_url = req.agency_url
    if req.agency_site is not None:
        agent.agency_site = req.agency_site
    if req.ribbon_text is not None:
        agent.ribbon_text = req.ribbon_text
    if req.ribbon_preset is not None:
        agent.ribbon_preset = req.ribbon_preset
    if req.tc_lang is not None:
        agent.tc_lang = req.tc_lang
    if req.caption_lang is not None:
        agent.caption_lang = req.caption_lang
    if req.currency is not None:
        agent.currency = req.currency
    if req.agency_phone is not None:
        agent.agency_phone = req.agency_phone
    if req.agency_email is not None:
        agent.agency_email = req.agency_email
    if req.google_review_url is not None:
        agent.google_review_url = req.google_review_url or None
    if req.tripadvisor_url is not None:
        agent.tripadvisor_url = req.tripadvisor_url or None

    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@app.post("/me/logo", response_model=AgentProfile)
async def upload_logo(
    file: UploadFile = File(...),
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Logo must be a JPEG or PNG image.")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo must be smaller than 5 MB.")

    # Delete old logo from R2 if there is one
    if agent.logo_r2_key:
        r2_upload.delete_logo(agent.logo_r2_key)

    key, url = r2_upload.upload_logo(data, file.content_type, agent.id)
    agent.logo_r2_key = key
    agent.logo_url = url

    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@app.delete("/me/logo", response_model=AgentProfile)
async def delete_logo(
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    if agent.logo_r2_key:
        r2_upload.delete_logo(agent.logo_r2_key)
    agent.logo_r2_key = None
    agent.logo_url = None
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


# --------------------------------------------------------------------------
# Package lookup (info only, no image generation)
# --------------------------------------------------------------------------

@app.get("/package/{package_id}")
async def get_package(
    package_id: str,
    agent: Agent = Depends(current_agent),
):
    brand = engine.agent_brand(agent)
    try:
        pack = sk.fetch(sk.TCClient(), package_id, brand)
    except sk.TCError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "id": pack.id,
        "title": pack.title,
        "days": pack.days,
        "nights": pack.nights,
        "price": pack.price,
        "currency": pack.currency,
        "destinations": pack.destinations,
        "themes": pack.themes,
        "gallery_count": len(pack.gallery),
        "gallery": pack.gallery,
        "departures": pack.departures,
        "flights": pack.flights,
        "hotels": pack.hotels,
    }


@app.get("/debug/package/{package_id}")
async def debug_package(
    package_id: str,
    agent: Agent = Depends(current_agent),
):
    """Returns the raw TC API response for a package so image field names can be inspected."""
    brand = engine.agent_brand(agent)
    client = sk.TCClient()
    import re as _re
    pkg_id = _re.sub(r"\D", "", str(package_id))
    try:
        info = client.info(pkg_id, brand.tc_lang)
    except sk.TCError as e:
        info = {"error": str(e)}
    try:
        detail = client.detail(pkg_id, brand.tc_lang)
    except sk.TCError as e:
        detail = {"error": str(e)}
    try:
        calendar = client.calendar(pkg_id, brand.tc_lang)
    except sk.TCError as e:
        calendar = {"error": str(e)}

    # Also show what normalise extracted
    try:
        pack = sk.normalise(pkg_id, info if not isinstance(info, dict) or "error" not in info else {},
                            detail if not isinstance(detail, dict) or "error" not in detail else {},
                            calendar if not isinstance(calendar, dict) or "error" not in calendar else {})
        extracted_gallery = pack.gallery
    except Exception as ex:
        extracted_gallery = [f"normalise error: {ex}"]

    return {
        "extracted_gallery": extracted_gallery,
        "info_keys": list(info.keys()) if isinstance(info, dict) else type(info).__name__,
        "detail_keys": list(detail.keys()) if isinstance(detail, dict) else type(detail).__name__,
        "info": info,
        "detail": detail,
    }


# --------------------------------------------------------------------------
# Caption generation
# --------------------------------------------------------------------------

@app.get("/generate/{package_id}/captions")
async def generate_captions(
    package_id: str,
    link: str | None = None,   # the exact URL the agent pasted, so captions link straight to the package
    agent: Agent = Depends(current_agent),
):
    brand = engine.agent_brand(agent)
    try:
        pack = sk.fetch(sk.TCClient(), package_id, brand)
    except sk.TCError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # If the agent pasted a full package link, the captions should carry that
    # exact link so a reader lands on the package — not the bare homepage.
    caption_url = brand.url
    if link and link.strip().lower().startswith(("http://", "https://")):
        caption_url = link.strip()

    texts = sk.captions(pack, caption_url, brand, pln_rate=None)
    return {
        "package_id": pack.id,
        "title": pack.title,
        "captions": texts,
    }


# --------------------------------------------------------------------------
# Image generation — returns JPEG directly
# --------------------------------------------------------------------------

@app.get("/generate/{package_id}/image")
async def generate_image(
    package_id: str,
    photo_index: int = 0,
    format: str = "square",
    style: str = "photo",
    focus: str = "center",
    zoom: float = 1.0,
    ribbon: str | None = None,   # per-request ribbon override (empty string = clear ribbon)
    agent: Agent = Depends(current_agent),
):
    """
    Returns a JPEG binary.  The frontend fetches this once per format/style
    combination and either shows it inline or triggers a download.
    """
    if format not in sk.FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {list(sk.FORMATS)}")
    if style not in sk.STYLES:
        raise HTTPException(status_code=400, detail=f"style must be one of {list(sk.STYLES)}")

    brand = engine.agent_brand(agent)

    try:
        pack = sk.fetch(sk.TCClient(), package_id, brand)
    except sk.TCError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not pack.gallery:
        raise HTTPException(
            status_code=422,
            detail=(
                "No photographs found for this package. "
                "Check the package ID and try again, or open a raw response via the "
                "/package/{id} endpoint to locate the image field."
            ),
        )

    idx = max(0, min(photo_index, len(pack.gallery) - 1))

    try:
        photo = sk.load_photo(pack.gallery[idx])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not load photograph: {e}")

    # Apply per-request ribbon override without mutating the DB row
    render_agent = agent
    if ribbon is not None:
        from copy import copy as _copy
        render_agent = _copy(agent)
        render_agent.ribbon_text = ribbon or None
        render_agent.ribbon_preset = None  # per-request text wins over stored preset

    # Run Pillow work in a thread pool so it doesn't block the event loop
    loop = asyncio.get_event_loop()
    image = await loop.run_in_executor(
        None,
        lambda: engine.render_for_agent(pack, render_agent, format, style, photo, focus, zoom),
    )

    jpeg_bytes = sk.to_jpeg(image)
    filename = _download_name(pack, agent, "jpg")

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------
# Flyer generation — returns full HTML page
# --------------------------------------------------------------------------

@app.get("/generate/{package_id}/flyer", response_class=HTMLResponse)
async def generate_flyer(
    package_id: str,
    style: str = "a",   # "a" = dark-navy editorial | "b" = white magazine
    qr: bool = False,   # optional QR code linking to the agency website
    agent: Agent = Depends(current_agent),
):
    """Returns a print-ready A4 HTML page."""
    if style not in ("a", "b", "c"):
        style = "a"
    brand = engine.agent_brand(agent)
    try:
        pack = sk.fetch(sk.TCClient(), package_id, brand)
    except sk.TCError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # render_flyer now embeds images (several blocking fetches), so run it off
    # the event loop.
    loop = asyncio.get_event_loop()
    html = await loop.run_in_executor(
        None, lambda: flyer_engine.render_flyer(pack, agent, style=style, show_qr=qr)
    )
    return html


# --------------------------------------------------------------------------
# Video generation — optional branded short clip (Pexels + FFmpeg)
# --------------------------------------------------------------------------

def _video_portrait(fmt: str) -> bool:
    w, h, _ = sk.FORMATS[fmt]
    return h > w


@app.get("/generate/{package_id}/video/search")
async def video_search(
    package_id: str,
    format: str = "story",
    query: str | None = None,       # optional agent-edited search term
    agent: Agent = Depends(current_agent),
):
    """
    Find free stock clips for this package's destination.

    Returns the search query used (so the UI can show / let the agent refine it)
    and up to a handful of clip previews to choose from. No rendering happens
    here — this is the cheap, free-tier-safe step.
    """
    if format not in sk.FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {list(sk.FORMATS)}")

    brand = engine.agent_brand(agent)
    try:
        pack = sk.fetch(sk.TCClient(), package_id, brand)
    except sk.TCError as e:
        raise HTTPException(status_code=502, detail=str(e))

    q = (query or "").strip() or vk.search_query(pack)
    want_portrait = _video_portrait(format)
    try:
        clips = vk.search_clips(q, want_portrait)
    except vk.VideoError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "package_id": pack.id,
        "query": q,
        "format": format,
        "clips": [c.as_dict() for c in clips],
    }


@app.get("/generate/{package_id}/video")
async def generate_video(
    package_id: str,
    clip_id: int,
    format: str = "story",
    query: str | None = None,       # the UI echoes back the query it searched with
    source: str | None = None,      # "pexels" or "pixabay" — which provider the clip came from
    agent: Agent = Depends(current_agent),
):
    """
    Render the branded MP4 for a chosen clip and return it as a download.

    Heavy step (FFmpeg): kept short by a 7-second cap and a 720p source, and
    run in a thread pool so it doesn't block the event loop.
    """
    if format not in sk.FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {list(sk.FORMATS)}")
    if not vk.ffmpeg_available():
        raise HTTPException(status_code=503, detail="Video rendering is unavailable (FFmpeg not installed).")

    brand = engine.agent_brand(agent)
    try:
        pack = sk.fetch(sk.TCClient(), package_id, brand)
    except sk.TCError as e:
        raise HTTPException(status_code=502, detail=str(e))

    want_portrait = _video_portrait(format)
    q = query or vk.search_query(pack)

    try:
        clip = vk.clip_by_id(q, want_portrait, clip_id, source=source)
    except vk.VideoError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if clip is None:
        raise HTTPException(status_code=404, detail="That clip could not be found — search again and pick another.")

    loop = asyncio.get_event_loop()

    def _work() -> bytes:
        overlay = sk.render_video_overlay(pack, format, brand)
        overlay_png = sk.overlay_to_png_bytes(overlay)
        return vk.render_video(clip, overlay_png, format)

    try:
        mp4_bytes = await loop.run_in_executor(None, _work)
    except vk.VideoError as e:
        raise HTTPException(status_code=502, detail=str(e))

    filename = _download_name(pack, agent, "mp4")
    return Response(
        content=mp4_bytes,
        media_type="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------
# Dashboard / settings / tool HTML pages
# --------------------------------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    with open("static/dashboard.html", encoding="utf-8") as f:
        return f.read()


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    with open("static/settings.html", encoding="utf-8") as f:
        return f.read()


@app.get("/tool/social-post", response_class=HTMLResponse)
async def tool_social_post():
    with open("static/tool-social-post.html", encoding="utf-8") as f:
        return f.read()


@app.get("/tool/flyer", response_class=HTMLResponse)
async def tool_flyer():
    with open("static/tool-flyer.html", encoding="utf-8") as f:
        return f.read()


@app.get("/tool/registration", response_class=HTMLResponse)
async def tool_registration():
    with open("static/tool-registration.html", encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------
# Registration: public consumer form  (no auth required)
# --------------------------------------------------------------------------

@app.get("/register/{agent_id}/{package_id}", response_class=HTMLResponse)
async def registration_form(agent_id: str, package_id: str, db: AsyncSession = Depends(get_db)):
    """Public page shown to end consumers — fetches package info and renders the form."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent or not agent.is_active:
        raise HTTPException(status_code=404, detail="Link not found")

    # Fetch package title from TC (best-effort)
    try:
        tc_user = os.getenv("TC_USERNAME", "")
        tc_pass = os.getenv("TC_PASSWORD", "")
        tc_micro = os.getenv("TC_MICROSITE", "momiratravel")
        tc_base = os.getenv("TC_BASE_URL", "https://online.travelcompositor.com/resources")
        pack = sk.fetch_package(package_id, tc_user, tc_pass, tc_micro, tc_base, lang="EN")
        pkg_title = pack.title
        pkg_dest = getattr(pack, "destination", "") or ""
        from_price = getattr(pack, "price_per_person", None)
        price_str = f"from €{int(from_price):,}".replace(",", ".") if from_price else ""
    except Exception:
        pkg_title = f"Holiday Package {package_id}"
        pkg_dest = ""
        price_str = ""

    agency_name = agent.agency_name or "Your Travel Agent"
    logo_html = f'<img src="{agent.logo_url}" alt="{agency_name}" class="agency-logo">' if agent.logo_url else ""

    with open("static/registration-form.html", encoding="utf-8") as f:
        tmpl = f.read()

    html = (tmpl
            .replace("{{AGENT_ID}}", agent_id)
            .replace("{{PACKAGE_ID}}", package_id)
            .replace("{{PKG_TITLE}}", pkg_title)
            .replace("{{PKG_DEST}}", pkg_dest)
            .replace("{{PRICE_STR}}", price_str)
            .replace("{{AGENCY_NAME}}", agency_name)
            .replace("{{LOGO_HTML}}", logo_html))
    return html


@app.post("/register/{agent_id}/{package_id}")
async def submit_registration(
    agent_id: str,
    package_id: str,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    nationality: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent or not agent.is_active:
        raise HTTPException(status_code=404, detail="Link not found")

    # Fetch package title for the email
    try:
        tc_user = os.getenv("TC_USERNAME", "")
        tc_pass = os.getenv("TC_PASSWORD", "")
        tc_micro = os.getenv("TC_MICROSITE", "momiratravel")
        tc_base = os.getenv("TC_BASE_URL", "https://online.travelcompositor.com/resources")
        pack = sk.fetch_package(package_id, tc_user, tc_pass, tc_micro, tc_base, lang="EN")
        pkg_title = pack.title
    except Exception:
        pkg_title = f"Holiday Package {package_id}"

    reg = Registration(
        agent_id=agent_id,
        package_id=package_id,
        package_title=pkg_title,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        phone=phone.strip() or None,
        nationality=nationality.strip() or None,
    )
    db.add(reg)
    await db.commit()

    # Send email (best-effort — DB row is already saved)
    agency_email = agent.agency_email or agent.email
    try:
        mailer.send_registration_email(
            to_email=agency_email,
            agency_name=agent.agency_name or "",
            package_id=package_id,
            package_title=pkg_title,
            first_name=first_name,
            last_name=last_name,
            consumer_email=email,
            phone=phone,
            nationality=nationality,
        )
    except Exception as exc:
        print(f"[mailer] send failed: {exc}")

    return HTMLResponse(content=_thank_you_html(pkg_title, agent.agency_name or ""), status_code=200)


def _thank_you_html(pkg_title: str, agency_name: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registration received</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    background:#f9fafb;display:flex;align-items:center;justify-content:center;
    min-height:100vh;margin:0;padding:1rem}}
  .card{{background:#fff;border-radius:16px;padding:2.5rem 2rem;max-width:420px;
    width:100%;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.07)}}
  .check{{font-size:3rem;margin-bottom:1rem}}
  h1{{font-size:1.4rem;font-weight:700;margin-bottom:.5rem;color:#111827}}
  p{{color:#6b7280;font-size:.95rem;line-height:1.6;margin:0}}
</style></head><body>
<div class="card">
  <div class="check">✅</div>
  <h1>Registration received!</h1>
  <p>Thank you for registering your interest in<br>
  <strong>{pkg_title}</strong>.<br><br>
  {agency_name} will be in touch with you soon.</p>
</div>
</body></html>"""


# --------------------------------------------------------------------------
# Bookings — manual trip list + feedback approval
# --------------------------------------------------------------------------

@app.get("/tool/trips", response_class=HTMLResponse)
async def tool_trips():
    with open("static/tool-trips.html", encoding="utf-8") as f:
        return f.read()


@app.post("/api/bookings")
async def add_booking(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    package_id: str = Form(""),
    return_date: str = Form(""),   # YYYY-MM-DD
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as _date
    pkg_title = None
    if package_id.strip():
        try:
            tc_user = os.getenv("TC_USERNAME", "")
            tc_pass = os.getenv("TC_PASSWORD", "")
            tc_micro = os.getenv("TC_MICROSITE", "momiratravel")
            tc_base = os.getenv("TC_BASE_URL", "https://online.travelcompositor.com/resources")
            pack = sk.fetch_package(package_id.strip(), tc_user, tc_pass, tc_micro, tc_base, lang="EN")
            pkg_title = pack.title
        except Exception:
            pkg_title = None

    ret_dt = None
    if return_date.strip():
        try:
            from datetime import datetime as _dt
            ret_dt = _dt.fromisoformat(return_date.strip()).replace(tzinfo=__import__("datetime").timezone.utc)
        except ValueError:
            pass

    from models import Booking
    b = Booking(
        agent_id=agent.id,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        package_id=package_id.strip() or None,
        package_title=pkg_title,
        return_date=ret_dt,
    )
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return {"id": b.id, "package_title": b.package_title}


@app.get("/api/bookings")
async def list_bookings(
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    from models import Booking
    result = await db.execute(
        select(Booking)
        .where(Booking.agent_id == agent.id)
        .order_by(Booking.return_date.asc().nulls_last(), Booking.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "first_name": r.first_name,
            "last_name": r.last_name,
            "email": r.email,
            "package_id": r.package_id,
            "package_title": r.package_title,
            "return_date": r.return_date.date().isoformat() if r.return_date else None,
            "feedback_status": r.feedback_status,
            "feedback_sent_at": r.feedback_sent_at.isoformat() if r.feedback_sent_at else None,
            "feedback_platforms": r.feedback_platforms,
        }
        for r in rows
    ]


@app.post("/api/bookings/{booking_id}/send-feedback")
async def send_feedback(
    booking_id: str,
    platforms: str = Form("google"),   # comma-separated: "google,tripadvisor"
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    from models import Booking
    from datetime import datetime, timezone
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.agent_id == agent.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.feedback_status == "sent":
        raise HTTPException(status_code=409, detail="Feedback email already sent")

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]

    try:
        mailer.send_feedback_email(
            to_email=booking.email,
            first_name=booking.first_name,
            package_title=booking.package_title or booking.package_id or "your trip",
            agency_name=agent.agency_name or "",
            agency_google_url=agent.google_review_url,
            agency_tripadvisor_url=agent.tripadvisor_url,
            platforms=platform_list,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Email send failed: {exc}")

    booking.feedback_status = "sent"
    booking.feedback_sent_at = datetime.now(timezone.utc)
    booking.feedback_platforms = ",".join(platform_list)
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------
# Registration: agent tool — generate + list links
# --------------------------------------------------------------------------

@app.get("/api/registrations", dependencies=[Depends(current_agent)])
async def list_registrations(
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Registration)
        .where(Registration.agent_id == agent.id)
        .order_by(Registration.submitted_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "package_id": r.package_id,
            "package_title": r.package_title,
            "first_name": r.first_name,
            "last_name": r.last_name,
            "email": r.email,
            "phone": r.phone,
            "nationality": r.nationality,
            "submitted_at": r.submitted_at.isoformat(),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
