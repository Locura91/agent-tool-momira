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

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import social_kit as sk
import kit_engine as engine
import r2_upload
import flyer_engine
import video_kit as vk
import mailer
import tc_sync
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
    current_admin,
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

_sync_task: asyncio.Task | None = None


async def _weekly_tc_sync_loop() -> None:
    """Background task: run TC booking sync every 7 days."""
    INTERVAL = 7 * 24 * 3600  # weekly
    await asyncio.sleep(60)  # short startup delay so DB is ready
    while True:
        try:
            from database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                await tc_sync.sync_tc_bookings(db)
        except Exception as e:
            print(f"[tc_sync] Weekly sync error: {e}")
        await asyncio.sleep(INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sync_task
    await init_db()
    _sync_task = asyncio.create_task(_weekly_tc_sync_loop())
    try:
        yield
    finally:
        if _sync_task:
            _sync_task.cancel()


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


@app.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.email == req.email, Agent.is_active == True))
    agent = result.scalar_one_or_none()

    if not agent or not verify_password(req.password, agent.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return TokenResponse(access_token=create_access_token(agent.id), role=agent.role)


# Admin-only: create a new Travel Agent account
@app.post("/admin/agents", response_model=TokenResponse, status_code=201)
async def admin_create_agent(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _admin: Agent = Depends(current_admin),
):
    existing = await db.execute(select(Agent).where(Agent.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with that email already exists.")

    agent = Agent(
        email=req.email,
        password_hash=hash_password(req.password),
        agency_name=req.agency_name,
        role="agent",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return TokenResponse(access_token=create_access_token(agent.id), role=agent.role)


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
    pack = None
    pack_fields = {}
    try:
        pack = sk.normalise(pkg_id, info if not isinstance(info, dict) or "error" not in info else {},
                            detail if not isinstance(detail, dict) or "error" not in detail else {},
                            calendar if not isinstance(calendar, dict) or "error" not in calendar else {})
        pack_fields = {
            "id": pack.id,
            "title": pack.title,
            "description": pack.description,
            "days": pack.days,
            "nights": pack.nights,
            "price": pack.price,
            "currency": pack.currency,
            "destinations": pack.destinations,
            "themes": pack.themes,
            "gallery": pack.gallery,
            "departures": [str(d) for d in (pack.departures or [])],
            "hotel_names": pack.hotel_names,
            "hotel_nights": pack.hotel_nights,
            "hotel_stars": pack.hotel_stars,
            "hotel_boards": pack.hotel_boards,
            "transport_counts": pack.transport_counts,
            "activities": pack.activities,
            "is_round_trip": pack.is_round_trip,
        }
    except Exception as ex:
        pack_fields = {"normalise_error": str(ex)}

    return {
        "package": pack_fields,
        "info_keys": list(info.keys()) if isinstance(info, dict) else type(info).__name__,
        "detail_keys": list(detail.keys()) if isinstance(detail, dict) else type(detail).__name__,
        "calendar_keys": list(calendar.keys()) if isinstance(calendar, dict) else type(calendar).__name__,
        "info": info,
        "detail": detail,
        "calendar": calendar,
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
        overlay = engine.render_video_overlay_for_agent(pack, agent, format)
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
# Admin area
# --------------------------------------------------------------------------

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    html_path = os.path.join(os.path.dirname(__file__), "static", "admin.html")
    with open(html_path, encoding="utf-8") as f:
        return f.read()


@app.get("/admin/agents", response_model=list)
async def admin_list_agents(
    db: AsyncSession = Depends(get_db),
    _admin: Agent = Depends(current_admin),
):
    result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
    agents = result.scalars().all()
    return [
        {
            "id": a.id,
            "email": a.email,
            "agency_name": a.agency_name,
            "role": a.role,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in agents
    ]


@app.patch("/admin/agents/{agent_id}")
async def admin_update_agent(
    agent_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: Agent = Depends(current_admin),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    # Protect admin accounts from being deactivated or having their role changed.
    if agent.role == "admin" and ("is_active" in body or "role" in body):
        raise HTTPException(status_code=403, detail="Admin accounts cannot be deactivated or demoted.")
    allowed = {"is_active", "agency_name", "role"}
    for key, value in body.items():
        if key in allowed:
            setattr(agent, key, value)
    db.add(agent)
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------
# Dashboard / settings / tool HTML pages
# --------------------------------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    with open(html_path, encoding="utf-8") as f:
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

    # Fetch full package data from TC (best-effort)
    pack = None
    pkg_title = f"Holiday Package {package_id}"
    pkg_dest = ""
    price_str = ""
    num_adults = 2
    num_children = 0
    itinerary_json = "null"

    try:
        # Use TCClient() directly so it reads TRAVELC_USERNAME/PASSWORD from env
        # via TCConfig.from_env() — passing empty strings as explicit args breaks auth
        _tc_client = sk.TCClient()
        pack = sk.fetch(_tc_client, package_id, lang="EN")
        pkg_title = pack.title or pkg_title
        # Destination: first destination name
        if pack.destinations:
            pkg_dest = pack.destinations[0].get("name", "")
        from_price = pack.price if pack.price else None
        if from_price:
            price_str = f"from €{int(from_price):,}".replace(",", ".")

        # --- Extract passenger counts from raw TC data ---
        raw_info = pack.raw.get("info", {}) or {}
        raw_detail = pack.raw.get("detail", {}) or {}

        def _pick_raw(src, keys, default=None):
            for k in keys:
                for kk in (k, k.lower(), k.upper()):
                    if kk in src:
                        return src[kk]
            return default

        # TC may have pax info at top level or inside occupancy/rooms
        pax_fields = ["pax", "passengers", "personsCount", "numberOfPersons",
                      "numberOfPassengers", "totalPax"]
        adults_fields = ["adults", "adultsCount", "numAdults", "numberAdults"]
        children_fields = ["children", "childrenCount", "numChildren", "numberChildren", "kids"]

        # TC HolidayPackageVO has a top-level "travelers" int field
        tc_travelers = raw_info.get("travelers") or raw_info.get("travellers") or raw_detail.get("travelers") or 0
        try:
            tc_travelers = int(tc_travelers)
        except Exception:
            tc_travelers = 0

        raw_adults = _pick_raw(raw_info, adults_fields) or _pick_raw(raw_detail, adults_fields)
        raw_children = _pick_raw(raw_info, children_fields) or _pick_raw(raw_detail, children_fields)

        if raw_adults is not None:
            try:
                num_adults = max(1, int(raw_adults))
            except (ValueError, TypeError):
                pass

        if raw_children is not None:
            try:
                num_children = max(0, int(raw_children))
            except (ValueError, TypeError):
                pass

        # If TC gives a total traveler count but no adult/child split, use it as adults
        if tc_travelers > 0 and raw_adults is None and raw_children is None:
            num_adults = tc_travelers
            num_children = 0

        # Fallback: look inside occupancy / rooms arrays
        if num_adults == 2 and num_children == 0:
            for src in (raw_info, raw_detail):
                for occ_key in ("occupancy", "room", "rooms", "roomOccupancy", "paxDetails"):
                    occ = src.get(occ_key)
                    if isinstance(occ, list) and occ:
                        occ = occ[0]
                    if isinstance(occ, dict):
                        a = occ.get("adults") or occ.get("adultsCount") or 0
                        c = occ.get("children") or occ.get("childrenCount") or 0
                        try:
                            a = int(a); c = int(c)
                        except (ValueError, TypeError):
                            a = 0; c = 0
                        if a > 0:
                            num_adults = a
                            num_children = c
                            break

        # --- Build full chronological itinerary for the registration form ---
        import json as _json
        from datetime import datetime as _dt

        def _fmt_date(raw) -> str:
            """Return 'Mon DD' label from any date string, or '' if unparseable."""
            s = str(raw or "").strip()
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
                try:
                    return _dt.strptime(s[:len(fmt.replace("%Y","0000").replace("%m","00").replace("%d","00").replace("%H","00").replace("%M","00").replace("%S","00"))], fmt).strftime("%d %b")
                except Exception:
                    pass
            # Try just stripping time part
            if "T" in s:
                try:
                    return _dt.strptime(s.split("T")[0], "%Y-%m-%d").strftime("%d %b")
                except Exception:
                    pass
            return ""

        def _fmt_date_iso(raw) -> str:
            """Return sortable YYYY-MM-DD or '' for chronological sorting."""
            s = str(raw or "").strip()
            if len(s) >= 10 and s[4] == "-":
                return s[:10]
            return ""

        def _duration_str(minutes) -> str:
            try:
                m = int(minutes)
                h, mn = divmod(m, 60)
                return f"{h}h {mn:02d}m" if h else f"{mn}m"
            except Exception:
                return ""

        def _baggage_str(t) -> str:
            # TC can return baggage as: bool, int (kg), string, list of {type,weight} dicts
            b = (t.get("baggage") or t.get("luggageIncluded") or t.get("baggageIncluded") or
                 t.get("includedBaggage") or t.get("checkedBaggage") or t.get("luggage") or "")
            if isinstance(b, bool):
                return "Luggage incl." if b else ""
            if isinstance(b, (int, float)):
                return f"{int(b)} kg" if b else ""
            if isinstance(b, list) and b:
                parts = []
                for item in b:
                    if isinstance(item, dict):
                        w = item.get("weight") or item.get("kg") or ""
                        pc = item.get("pieces") or item.get("quantity") or item.get("pcs") or ""
                        label = item.get("type") or item.get("name") or ""
                        if pc:
                            parts.append(f"{pc}PC" + (f" {int(w)}kg" if w else ""))
                        elif w:
                            parts.append(f"{int(w)}kg")
                        elif label:
                            parts.append(str(label))
                    else:
                        parts.append(str(item))
                return " + ".join(p for p in parts if p) or ""
            s = str(b).strip()
            # If it looks like a raw number treat as kg
            try:
                return f"{int(float(s))} kg" if s and float(s) > 0 else ""
            except Exception:
                return s if s and s not in ("0", "false", "False", "null") else ""

        def _board_label(board: str) -> str:
            return sk._board_label(board)

        TRANSPORT_LABELS = {
            "FLIGHT": ("Flight", "flight"),
            "BUS": ("Bus", "bus"),
            "FERRY": ("Ferry", "ferry"),
            "TRAIN": ("Train", "train"),
            "CAR": ("Car rental", "car"),
            "TRANSFER": ("Transfer", "transfer"),
            "CRUISE": ("Cruise", "cruise"),
        }

        import html as _html_mod, re as _re_mod
        def _clean_html(s):
            return " ".join(_html_mod.unescape(_re_mod.sub(r"<[^>]+>", " ", str(s or ""))).split())

        def _room_name(h_raw):
            """Extract room type string from a raw TC hotel object."""
            if not isinstance(h_raw, dict):
                return ""
            for rk in ("rooms", "room", "roomList", "roomOptions"):
                rooms = h_raw.get(rk)
                if isinstance(rooms, list) and rooms:
                    r = rooms[0]
                    if isinstance(r, dict):
                        n = r.get("name") or r.get("roomType") or r.get("type") or r.get("description") or ""
                        n = _clean_html(n)
                        if n:
                            return n
                elif isinstance(rooms, dict):
                    n = rooms.get("name") or rooms.get("roomType") or rooms.get("type") or ""
                    n = _clean_html(n)
                    if n:
                        return n
            n = h_raw.get("roomName") or h_raw.get("roomType") or h_raw.get("roomDescription") or ""
            return _clean_html(n)

        def _stops_str(t):
            s = t.get("stops") or t.get("numberOfStops") or t.get("numStops") or t.get("layovers") or 0
            try:
                n = int(s)
                return "Direct" if n == 0 else f"{n} stop{'s' if n > 1 else ''}"
            except Exception:
                return str(s).strip() if s else ""

        def _provider_str(t):
            return str(t.get("airline") or t.get("carrier") or t.get("company") or
                       t.get("operator") or t.get("provider") or "").strip()

        def _loc_name(val) -> str:
            """TC location fields can be a plain string, an airport code, or a
            dict like {'latitude':1.35,'longitude':103.99,'name':'Changi Intl'}.
            Always return a human-readable name."""
            if not val:
                return ""
            if isinstance(val, dict):
                return str(val.get("name") or val.get("code") or val.get("iata") or "").strip()
            return str(val).strip()

        items = []  # each: {sort_key, date_label, kind, chip, title, detail, ...}

        # 1. Transports (flights, ferries, buses, trains — detail.transports)
        transports_raw = _pick_raw(raw_detail, ["transports", "transport"], []) or []
        for t in (transports_raw or []):
            if not isinstance(t, dict):
                continue
            ttype = str(t.get("transportType") or t.get("type") or "OTHER").upper()
            chip_label, chip_kind = TRANSPORT_LABELS.get(ttype, (ttype.title(), "flight"))

            dep_raw = (t.get("departureDate") or t.get("departureDateTime") or
                       t.get("date") or t.get("startDate") or "")
            dep_time = str(t.get("departureTime") or t.get("departureHour") or "")
            if not dep_time and dep_raw and "T" in str(dep_raw):
                dep_time = str(dep_raw).split("T")[1][:5]
            arr_time = str(t.get("arrivalTime") or t.get("arrivalHour") or "")
            arr_raw  = (t.get("arrivalDate") or t.get("arrivalDateTime") or "")
            # detect next-day arrival
            arr_suffix = ""
            if arr_raw and dep_raw:
                arr_day = _fmt_date_iso(arr_raw)
                dep_day = _fmt_date_iso(dep_raw)
                if arr_day and dep_day and arr_day > dep_day:
                    try:
                        from datetime import date as _date_cls
                        diff = (_date_cls.fromisoformat(arr_day) - _date_cls.fromisoformat(dep_day)).days
                        arr_suffix = f" +{diff}" if diff > 0 else ""
                    except Exception:
                        pass

            origin  = (_loc_name(t.get("originCode") or t.get("originAirport") or t.get("originCity") or t.get("origin") or t.get("from")) or "")
            dest_c  = (_loc_name(t.get("targetCode") or t.get("destinationCode") or t.get("destinationAirport") or t.get("destinationCity") or t.get("destination") or t.get("target") or t.get("to")) or "")
            title   = f"{origin} → {dest_c}" if (origin and dest_c) else chip_label

            time_str = ""
            if dep_time and dep_time[:5]:
                time_str = dep_time[:5]
                if arr_time and arr_time[:5]:
                    time_str += f" → {arr_time[:5]}{arr_suffix}"

            dur     = _duration_str(t.get("duration") or t.get("flightDuration") or 0)
            stops   = _stops_str(t)
            bag     = _baggage_str(t)
            provider = _provider_str(t)
            flight_no = str(t.get("flightNumber") or t.get("flightNo") or t.get("serviceNumber") or "")

            items.append({
                "sort_key":   _fmt_date_iso(dep_raw) + "A",
                "date_label": _fmt_date(dep_raw),
                "kind":       chip_kind,
                "chip":       chip_label,
                "title":      title,
                "time":       time_str,
                "duration":   dur,
                "stops":      stops,
                "baggage":    bag,
                "provider":   (provider + (f" {flight_no}" if flight_no else "")).strip(),
            })

        # 2. Hotels (detail.hotels) — name, stars, room, board, nights, check-in
        raw_hotels = _pick_raw(raw_detail, ["hotels", "accommodations", "hotel"], []) or []
        for idx, h_name in enumerate(pack.hotel_names):
            nights   = pack.hotel_nights[idx] if idx < len(pack.hotel_nights) else 0
            stars    = pack.hotel_stars[idx]   if idx < len(pack.hotel_stars)  else 0
            board    = pack.hotel_boards[idx]  if idx < len(pack.hotel_boards) else ""
            h_raw    = raw_hotels[idx] if isinstance(raw_hotels, list) and idx < len(raw_hotels) else {}
            checkin_raw = ""
            if isinstance(h_raw, dict):
                checkin_raw = (h_raw.get("checkIn") or h_raw.get("checkInDate") or
                               h_raw.get("startDate") or h_raw.get("arrivalDate") or "")
            room_name = _room_name(h_raw) if isinstance(h_raw, dict) else ""
            board_label = _board_label(board)
            items.append({
                "sort_key":   _fmt_date_iso(checkin_raw) + "B",
                "date_label": _fmt_date(checkin_raw),
                "kind":       "hotel",
                "chip":       "Stay",
                "title":      h_name,
                "stars":      stars,
                "nights":     nights,
                "board":      board_label,
                "room":       room_name,
            })

        # 3. Transfers (detail.transfers) — airport ↔ hotel
        for t in (_pick_raw(raw_detail, ["transfers", "transfer"], []) or []):
            if not isinstance(t, dict):
                continue
            # TC location fields can be dicts {latitude, longitude, name}
            origin_t = _loc_name(t.get("origin") or t.get("originCode") or t.get("from") or t.get("pickup"))
            dest_t   = _loc_name(t.get("destination") or t.get("target") or t.get("targetCode") or t.get("to") or t.get("dropoff"))
            if origin_t and dest_t:
                title_t = f"{origin_t} → {dest_t}"
            else:
                title_t = _clean_html(t.get("name") or t.get("title") or t.get("description") or "Airport Transfer")
            dep_raw    = t.get("date") or t.get("startDate") or t.get("departureDate") or ""
            dep_time_t = str(t.get("departureTime") or t.get("pickupTime") or "")
            arr_time_t = str(t.get("arrivalTime") or t.get("dropoffTime") or "")
            time_t = ""
            if dep_time_t and dep_time_t[:5]:
                time_t = dep_time_t[:5]
                if arr_time_t and arr_time_t[:5]:
                    time_t += f" → {arr_time_t[:5]}"
            # Use a sort key that places transfers after flights/hotels on the same day
            items.append({
                "sort_key":   _fmt_date_iso(dep_raw) + "C",
                "date_label": _fmt_date(dep_raw),
                "kind":       "transfer",
                "chip":       "Transfer",
                "title":      title_t,
                "time":       time_t,
                "provider":   _provider_str(t),
            })

        # 4. Tickets / excursions (detail.tickets)
        for ticket in (_pick_raw(raw_detail, ["tickets"], []) or []):
            if not isinstance(ticket, dict):
                continue
            name = _clean_html(ticket.get("name") or ticket.get("title") or ticket.get("description") or "")
            if not name:
                continue
            date_raw = ticket.get("date") or ticket.get("startDate") or ticket.get("ticketDate") or ""
            items.append({
                "sort_key":   _fmt_date_iso(date_raw) + "D",
                "date_label": _fmt_date(date_raw),
                "kind":       "activity",
                "chip":       "Ticket",
                "title":      name,
            })

        # 5. Cruises (detail.cruises)
        for cruise in (_pick_raw(raw_detail, ["cruises"], []) or []):
            if not isinstance(cruise, dict):
                continue
            name    = _clean_html(cruise.get("name") or cruise.get("title") or cruise.get("shipName") or "Cruise")
            date_raw = cruise.get("departureDate") or cruise.get("date") or cruise.get("startDate") or ""
            nights_c = cruise.get("nights") or cruise.get("duration") or 0
            items.append({
                "sort_key":   _fmt_date_iso(date_raw) + "E",
                "date_label": _fmt_date(date_raw),
                "kind":       "cruise",
                "chip":       "Cruise",
                "title":      name,
                "nights":     int(nights_c) if nights_c else 0,
                "provider":   _provider_str(cruise),
            })

        # 6. Closed tours / tripSpots (detail.closedTours / detail.tripSpots)
        for spot in (_pick_raw(raw_detail, ["closedTours", "tripSpots"], []) or []):
            if not isinstance(spot, dict):
                continue
            name = _clean_html(spot.get("name") or spot.get("title") or spot.get("description") or "")
            if not name:
                continue
            date_raw = spot.get("date") or spot.get("startDate") or ""
            items.append({
                "sort_key":   _fmt_date_iso(date_raw) + "F",
                "date_label": _fmt_date(date_raw),
                "kind":       "activity",
                "chip":       "Tour",
                "title":      name,
            })

        # 7. Guaranteed fallback from pack.* fields when raw detail yielded nothing
        if not items:
            flight_n = pack.transport_counts.get("flights", 0) if pack.transport_counts else 0
            if flight_n:
                items.append({
                    "sort_key": "AAA", "date_label": "",
                    "kind": "flight", "chip": "Flight",
                    "title": f"Flights included ({flight_n})",
                    "time": "", "duration": "", "stops": "",
                    "baggage": "", "provider": "",
                })
            for idx2, h_name in enumerate(pack.hotel_names or []):
                nights2 = pack.hotel_nights[idx2] if idx2 < len(pack.hotel_nights or []) else 0
                stars2  = pack.hotel_stars[idx2]   if idx2 < len(pack.hotel_stars or [])  else 0
                board2  = pack.hotel_boards[idx2]  if idx2 < len(pack.hotel_boards or []) else ""
                items.append({
                    "sort_key": f"BBB{idx2:03d}", "date_label": "",
                    "kind": "hotel", "chip": "Stay",
                    "title": h_name, "stars": stars2,
                    "nights": nights2, "board": _board_label(board2), "room": "",
                })
            t_count = pack.transport_counts.get("transfers", 0) if pack.transport_counts else 0
            if t_count:
                items.append({
                    "sort_key": "CCC", "date_label": "",
                    "kind": "transfer", "chip": "Transfer",
                    "title": f"Transfers included ({t_count})",
                    "time": "", "provider": "",
                })
            for a in (pack.activities or []):
                items.append({
                    "sort_key": "DDD", "date_label": "",
                    "kind": "activity", "chip": "Included",
                    "title": str(a),
                })

        # Sort chronologically; items without a date float to their natural position
        items.sort(key=lambda x: (x.get("sort_key") or "ZZZZ"))

        itinerary = {
            "items": items,
            "days": pack.days,
            "nights": pack.nights,
        }
        # Use ensure_ascii=False so names render correctly; HTML-escape < > & for safe embedding
        itinerary_json = _json.dumps(itinerary, ensure_ascii=False).replace("</", "<\\/")

    except Exception as exc:
        print(f"[registration_form] TC fetch failed: {exc}")

    agency_name = agent.agency_name or "Your Travel Agent"
    logo_html = (
        f'<img src="{agent.logo_url}" alt="{agency_name}" class="agency-logo">'
        if agent.logo_url else ""
    )

    # Hero image — use first gallery photo if available
    hero_img_html = ""
    if pack and pack.gallery:
        hero_url = pack.gallery[0]
        hero_img_html = f'<img src="{hero_url}" alt="{pkg_title}" class="hero-img" loading="lazy">'
    if not hero_img_html:
        hero_img_html = '<div class="hero-img-placeholder">✈️</div>'

    # Package description
    pkg_desc = (pack.description or "") if pack else ""

    # Route chips: destination names joined as a strip
    route_html = ""
    if pack and pack.destinations:
        chips = []
        for i, d in enumerate(pack.destinations):
            name = d.get("name", "")
            if name:
                arrow = " <span class='route-arrow'>→</span> " if i > 0 else ""
                chips.append(f"{arrow}<span class='route-chip'>{name}</span>")
        if chips:
            route_html = "".join(chips)

    # Upcoming departures (up to 3 nearest)
    departures_html = ""
    if pack and pack.departures:
        import json as _json2
        from datetime import date as _today_cls
        today_str = _today_cls.today().isoformat()
        upcoming = sorted([d for d in pack.departures if str(d) >= today_str])[:3]
        if upcoming:
            dep_parts = [f"<span class='dep-chip'>{d}</span>" for d in upcoming]
            departures_html = "Departures: " + " &nbsp; ".join(dep_parts)

    import registration_form_template as _rft
    tmpl = _rft.TEMPLATE

    html = (tmpl
            .replace("{{AGENT_ID}}", agent_id)
            .replace("{{PACKAGE_ID}}", package_id)
            .replace("{{PKG_TITLE}}", pkg_title)
            .replace("{{PKG_DEST}}", pkg_dest)
            .replace("{{PRICE_STR}}", price_str)
            .replace("{{PKG_DESC}}", pkg_desc)
            .replace("{{HERO_IMG_HTML}}", hero_img_html)
            .replace("{{ROUTE_HTML}}", route_html)
            .replace("{{DEPARTURES_HTML}}", departures_html)
            .replace("{{AGENCY_NAME}}", agency_name)
            .replace("{{LOGO_HTML}}", logo_html)
            .replace("{{NUM_ADULTS}}", str(num_adults))
            .replace("{{NUM_CHILDREN}}", str(num_children))
            .replace("{{ITINERARY_JSON}}", itinerary_json))
    return html


@app.post("/register/{agent_id}/{package_id}")
async def submit_registration(
    agent_id: str,
    package_id: str,
    # Shared contact fields
    email: str = Form(...),
    phone: str = Form(""),
    street: str = Form(""),
    house_number: str = Form(""),
    postal_code: str = Form(""),
    city: str = Form(""),
    country_of_residence: str = Form(""),
    nationality: str = Form(""),
    # Per-passenger data (JSON blob built on the client side)
    passengers_json: str = Form("[]"),
    db: AsyncSession = Depends(get_db),
):
    import json as _json
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent or not agent.is_active:
        raise HTTPException(status_code=404, detail="Link not found")

    # Fetch package title for the email
    try:
        tc_user = os.getenv("TC_USERNAME") or os.getenv("TRAVELC_USERNAME", "")
        tc_pass = os.getenv("TC_PASSWORD") or os.getenv("TRAVELC_PASSWORD", "")
        tc_micro = os.getenv("TC_MICROSITE") or os.getenv("TRAVELC_MICROSITE_ID", "momiratravel")
        tc_base = os.getenv("TC_BASE_URL") or os.getenv("TRAVELC_BASE_URL", "https://online.travelcompositor.com/resources")
        pack = sk.fetch_package(package_id, tc_user, tc_pass, tc_micro, tc_base, lang="EN")
        pkg_title = pack.title
    except Exception:
        pkg_title = f"Holiday Package {package_id}"

    # Parse passengers — [{type:"adult"|"child", full_name:"…", dob:"YYYY-MM-DD"}]
    try:
        passengers = _json.loads(passengers_json) if passengers_json else []
    except Exception:
        passengers = []

    # Primary passenger (first adult) for backward-compat fields
    primary = next((p for p in passengers if p.get("type") == "adult"), passengers[0] if passengers else {})
    first_name = primary.get("full_name", "").split()[0] if primary.get("full_name") else ""
    last_name = " ".join(primary.get("full_name", "").split()[1:]) if primary.get("full_name") else ""

    reg = Registration(
        agent_id=agent_id,
        package_id=package_id,
        package_title=pkg_title,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email.strip(),
        phone=phone.strip() or None,
        nationality=nationality.strip() or None,
        street=f"{street.strip()} {house_number.strip()}".strip() or None,
        postal_code=postal_code.strip() or None,
        city=city.strip() or None,
        country_of_residence=country_of_residence.strip() or None,
        passengers_json=_json.dumps(passengers, ensure_ascii=False) if passengers else None,
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
            passengers=passengers,
            address=f"{street} {house_number}, {postal_code} {city}, {country_of_residence}".strip(", "),
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


@app.get("/api/bookings/lookup")
async def lookup_booking(
    ref: str,
    agent: Agent = Depends(current_agent),
):
    """Look up a TC booking by reference number and return customer details."""
    import os as _os
    microsite = _os.environ.get("TRAVELC_MICROSITE_ID", "momiratravel")
    try:
        client = sk.TCClient()
        data = client.get(f"/booking/getBookings/{microsite}/{ref.strip()}")
    except sk.TCError as e:
        msg = str(e)
        if "404" in msg:
            raise HTTPException(status_code=404, detail="Booking not found")
        raise HTTPException(status_code=502, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TC lookup failed: {e}")

    # TC returns a list or a single object depending on version
    if isinstance(data, list):
        data = data[0] if data else None
    if not data:
        raise HTTPException(status_code=404, detail="Booking not found")

    cp = data.get("contactPerson") or {}
    # TC may surface the trip name under several keys depending on version
    pkg_title = (
        data.get("name")
        or data.get("title")
        or data.get("packageName")
        or data.get("productName")
        or ""
    )
    return {
        "first_name": cp.get("name") or "",
        "last_name": cp.get("lastName") or "",
        "email": cp.get("email") or "",
        "return_date": data.get("endDate") or "",  # YYYY-MM-DD
        "package_title": pkg_title,
        "booking_ref": ref.strip(),
    }


@app.post("/api/bookings")
async def add_booking(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    package_id: str = Form(""),
    package_title: str = Form(""),   # pre-filled from BNR lookup; skips TC fetch when provided
    return_date: str = Form(""),     # YYYY-MM-DD
    tc_booking_ref: str = Form(""),
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as _date
    pkg_title = package_title.strip() or None
    if not pkg_title and package_id.strip():
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
        tc_booking_ref=tc_booking_ref.strip() or None,
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
            "tc_booking_ref": r.tc_booking_ref,
        }
        for r in rows
    ]


@app.get("/api/bookings/{booking_id}/preview-email")
async def preview_feedback_email(
    booking_id: str,
    platforms: str = "google",   # comma-separated: "google,tripadvisor"
    lang: str = "en",            # "en" or "de"
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Return the feedback email subject + HTML body without sending it."""
    from models import Booking
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.agent_id == agent.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    MOMIRA_GOOGLE = "https://g.page/r/CeqHXc2-NckXEBM/review"
    btn_style = (
        "display:inline-block;margin:6px 0;padding:12px 24px;"
        "background:#17a39b;color:#ffffff;text-decoration:none;"
        "border-radius:8px;font-size:15px;font-weight:600;"
    )
    agency = agent.agency_name or "Momira Travel"
    first = booking.first_name
    pkg = booking.package_title or booking.package_id or ""

    if lang == "de":
        pkg_phrase = f"deiner {pkg}-" if pkg else "deiner "
        subject = f"Wie war deine Reise, {first}? Wir freuen uns über dein Feedback!"
        review_buttons_html = ""
        if "google" in platform_list and agent.google_review_url:
            review_buttons_html += f'<a href="{agent.google_review_url}" style="{btn_style}">★ {agency} auf Google bewerten</a><br>'
        if "tripadvisor" in platform_list and agent.tripadvisor_url:
            review_buttons_html += f'<a href="{agent.tripadvisor_url}" style="{btn_style}">★ {agency} auf TripAdvisor bewerten</a><br>'
        review_buttons_html += f'<a href="{MOMIRA_GOOGLE}" style="{btn_style}">★ Momira Travel auf Google bewerten</a><br>'
        html_body = f"""\
<!DOCTYPE html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111827;max-width:560px;margin:0 auto;padding:24px;">
<p>Liebe/r {first},</p>
<p>wir hoffen, du hattest eine tolle {pkg_phrase}Reise! Falls du kurz eine Bewertung hinterlassen magst, würden wir uns sehr freuen — das hilft anderen Reisenden und unterstützt unser Team.</p>
<div style="margin:20px 0;">{review_buttons_html}</div>
<p>Danke fürs Vertrauen — wir freuen uns auf dein nächstes Abenteuer!<br>Bei Fragen erreichst du uns unter <a href="mailto:info@momira.de" style="color:#17a39b;">info@momira.de</a>.</p>
<p>Herzliche Grüße,<br><strong>Dein Momira Travel Team</strong></p>
</body></html>"""
    else:
        pkg_phrase = f"your {pkg} " if pkg else ""
        subject = f"How was your trip, {first}? We'd love your feedback!"
        review_buttons_html = ""
        if "google" in platform_list and agent.google_review_url:
            review_buttons_html += f'<a href="{agent.google_review_url}" style="{btn_style}">★ Review {agency} on Google</a><br>'
        if "tripadvisor" in platform_list and agent.tripadvisor_url:
            review_buttons_html += f'<a href="{agent.tripadvisor_url}" style="{btn_style}">★ Review {agency} on TripAdvisor</a><br>'
        review_buttons_html += f'<a href="{MOMIRA_GOOGLE}" style="{btn_style}">★ Review Momira Travel on Google</a><br>'
        thanks_line = f"Thank you for choosing <strong>{agency}</strong>." if agency == "Momira Travel" else f"Thank you for choosing <strong>{agency}</strong> and Momira Travel."
        html_body = f"""\
<!DOCTYPE html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111827;max-width:560px;margin:0 auto;padding:24px;">
<p>Dear {first},</p>
<p>We hope you had a wonderful time on {pkg_phrase}your holiday! If you have a moment, we'd love to hear your feedback — it helps other travellers and supports our team.</p>
<div style="margin:20px 0;">{review_buttons_html}</div>
<p>{thanks_line} For any future requests, feel free to contact us at <a href="mailto:info@momira.de" style="color:#17a39b;">info@momira.de</a>.</p>
<p>Warm regards,<br><strong>Your Momira Travel Team</strong></p>
</body></html>"""

    return {"subject": subject, "html_body": html_body, "to_email": booking.email}


@app.post("/api/bookings/{booking_id}/send-feedback")
async def send_feedback(
    booking_id: str,
    platforms: str = Form("google"),       # comma-separated: "google,tripadvisor"
    lang: str = Form("en"),                # "en" or "de"
    override_email: str = Form(""),        # non-empty = test send, do not mark as sent
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

    is_test = bool(override_email.strip())
    if not is_test and booking.feedback_status == "sent":
        raise HTTPException(status_code=409, detail="Feedback email already sent")

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    to_email = override_email.strip() if is_test else booking.email

    try:
        cc = None if is_test else (agent.agency_email or agent.email or "info@momira.de")
        mailer.send_feedback_email(
            to_email=to_email,
            first_name=booking.first_name,
            package_title=booking.package_title or booking.package_id or "",
            agency_name=agent.agency_name or "Momira Travel",
            agency_google_url=agent.google_review_url,
            agency_tripadvisor_url=agent.tripadvisor_url,
            platforms=platform_list,
            lang=lang,
            agent_email=cc,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Email send failed: {exc}")

    if not is_test:
        booking.feedback_status = "sent"
        booking.feedback_sent_at = datetime.now(timezone.utc)
        booking.feedback_platforms = ",".join(platform_list)
        await db.commit()
    return {"ok": True, "test": is_test}


@app.delete("/api/bookings/{booking_id}")
async def delete_booking(
    booking_id: str,
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    from models import Booking
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.agent_id == agent.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    await db.delete(booking)
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------
# TC booking sync
# --------------------------------------------------------------------------

@app.post("/api/sync/tc-bookings")
async def trigger_tc_sync(
    agent: Agent = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: manually trigger a TC booking sync across all agents."""
    stats = await tc_sync.sync_tc_bookings(db)
    return {"ok": True, **stats}


@app.post("/api/sync/tc-bookings/me")
async def trigger_tc_sync_me(
    agent: Agent = Depends(current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Agent: sync TC bookings that belong to this agent's agency."""
    if not agent.agency_name:
        raise HTTPException(status_code=400, detail="No agency_name set in your profile — set it first so TC bookings can be matched.")
    stats = await tc_sync.sync_tc_bookings_for_agent(db, agent)
    return {"ok": True, **stats}


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

