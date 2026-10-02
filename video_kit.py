"""
Video kit — optional short branded video posts for the social media kit.

Instead of a still photograph, a travel agent can pick one free stock clip
from Pexels and the tool burns the same branded overlay used by the collage
style onto it, producing a short MP4 ready to post to Reels / Stories / TikTok.

Design decisions, all driven by keeping this viable on Render's free tier
(512 MB RAM, shared CPU):

  • MAX_VIDEO_SECONDS = 7   — a short cap is the single biggest lever on FFmpeg
                             cost; it also loops well on social and replays more.
  • 720p source cap        — we ask Pexels for the smallest file that is still
                             sharp at output size, never 1080p/4K, to keep RAM
                             and render time down.
  • overlay is a PNG       — the brand design is rendered once by Pillow
    composited by FFmpeg     (social_kit.render_video_overlay), so FFmpeg only
                             scales the clip and lays the PNG on top: cheap.
  • -preset veryfast       — trades a little file size for far less CPU.

The Pexels key is read from the PEXELS_API_KEY environment variable, exactly
like the Travel Compositor credentials — the agent never sees it or needs
their own.

Requires: requests, Pillow (via social_kit), and the `ffmpeg` binary on PATH.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import requests

import social_kit as sk

MODULE_BUILD = "2026-10-02-video-kit-pexels-ffmpeg"

# ── Tunables (all in one place; see module docstring) ──────────────────────
MAX_VIDEO_SECONDS = 7
SOURCE_HEIGHT_CAP = 720      # never download a file taller than this
OUTPUT_FPS = 30
X264_CRF = 24                # 18 (big/sharp) … 28 (small/soft); 24 is a good social default
X264_PRESET = "veryfast"
FFMPEG_TIMEOUT = 90          # hard ceiling so a stuck render can't hang a worker

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
_HTTP_TIMEOUT = 30


class VideoError(RuntimeError):
    """Anything that stops a video from being produced."""


def _api_key() -> str:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise VideoError(
            "Video posts are not configured — PEXELS_API_KEY is not set on the server."
        )
    return key


def ffmpeg_bin() -> Optional[str]:
    """
    Locate an ffmpeg binary.

    On Render's native Python runtime there is no system ffmpeg and no apt, so
    we rely on the `imageio-ffmpeg` wheel, which ships a static ffmpeg binary
    (with libx264) inside the Python environment. Locally we fall back to a
    system ffmpeg on PATH.
    """
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return shutil.which("ffmpeg")


def ffmpeg_available() -> bool:
    return ffmpeg_bin() is not None


# ── Search query from the package ──────────────────────────────────────────

def search_query(pack: sk.Package) -> str:
    """
    A short, strong keyword for Pexels built from the package's destinations.

    Pexels matches best on a plain place name ("Santorini", "Kyoto Japan"),
    not a marketing title, so we prefer the destination names and fall back to
    the title only when there are none.
    """
    dests = [d.get("name", "").strip() for d in (pack.destinations or []) if d.get("name")]
    # De-duplicate while preserving order.
    seen, uniq = set(), []
    for name in dests:
        low = name.lower()
        if low and low not in seen:
            seen.add(low)
            uniq.append(name)
    if uniq:
        # One or two place names is the sweet spot; more narrows Pexels too hard.
        return " ".join(uniq[:2])
    # Fall back to the first few words of the title, stripped of punctuation.
    words = re.sub(r"[^\w\s]", " ", pack.title or "").split()
    return " ".join(words[:3]) or "travel"


# ── Pexels clip search ──────────────────────────────────────────────────────

@dataclass
class Clip:
    id: int
    duration: int                 # seconds, as reported by Pexels
    width: int
    height: int
    preview: str                  # poster image URL (for the picker thumbnail)
    download_url: str             # the chosen video file URL (≤ SOURCE_HEIGHT_CAP tall)
    user: str                     # videographer name (shown as a courtesy credit)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "preview": self.preview,
            "download_url": self.download_url,
            "user": self.user,
        }


def _pick_file(video_files: list, want_portrait: bool) -> Optional[dict]:
    """
    Choose the lightest file that is still sharp enough.

    We want the smallest file whose height is >= a sensible floor but capped at
    SOURCE_HEIGHT_CAP (720p), so FFmpeg never has to chew through 1080p/4K on a
    free-tier box. Prefer .mp4 and an orientation matching the target format.
    """
    usable = []
    for f in video_files:
        h = f.get("height") or 0
        w = f.get("width") or 0
        link = f.get("link") or ""
        if not link or not h or not w:
            continue
        is_portrait = h >= w
        usable.append((f, w, h, is_portrait, f.get("file_type", "")))

    if not usable:
        return None

    def score(item):
        f, w, h, is_portrait, ftype = item
        # Distance from the cap (prefer height closest to, but not far above, the cap).
        over = max(0, h - SOURCE_HEIGHT_CAP)
        under = max(0, SOURCE_HEIGHT_CAP - h)
        orient_penalty = 0 if is_portrait == want_portrait else 400
        type_penalty = 0 if "mp4" in ftype.lower() else 100
        # Overlarge is worse than slightly small on the free tier.
        return over * 2 + under + orient_penalty + type_penalty

    best = min(usable, key=score)
    return best[0]


def search_clips(query: str, want_portrait: bool, per_page: int = 6) -> List[Clip]:
    """Search Pexels and return up to `per_page` usable clips."""
    headers = {"Authorization": _api_key()}
    params = {
        "query": query,
        "per_page": max(1, min(per_page, 15)),
        "orientation": "portrait" if want_portrait else "landscape",
        "size": "medium",
    }
    try:
        resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=_HTTP_TIMEOUT)
    except requests.RequestException as e:
        raise VideoError(f"Could not reach Pexels: {e}")

    if resp.status_code == 401:
        raise VideoError("Pexels rejected the API key (401). Check PEXELS_API_KEY.")
    if resp.status_code == 429:
        raise VideoError("Pexels rate limit reached — try again in a little while.")
    if not resp.ok:
        raise VideoError(f"Pexels search failed (HTTP {resp.status_code}).")

    data = resp.json()
    clips: List[Clip] = []
    for v in data.get("videos", []):
        chosen = _pick_file(v.get("video_files", []), want_portrait)
        if not chosen:
            continue
        clips.append(
            Clip(
                id=v.get("id", 0),
                duration=v.get("duration", 0),
                width=chosen.get("width", 0),
                height=chosen.get("height", 0),
                preview=v.get("image", ""),
                download_url=chosen.get("link", ""),
                user=(v.get("user") or {}).get("name", ""),
            )
        )
    return clips


def clip_by_id(query: str, want_portrait: bool, clip_id: int) -> Optional[Clip]:
    """Re-find a specific clip (the picker sends back only its id)."""
    for c in search_clips(query, want_portrait, per_page=15):
        if c.id == clip_id:
            return c
    return None


# ── Render ──────────────────────────────────────────────────────────────────

def _download(url: str, dest_path: str) -> None:
    try:
        with requests.get(url, stream=True, timeout=_HTTP_TIMEOUT) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
    except requests.RequestException as e:
        raise VideoError(f"Could not download the clip: {e}")


def render_video(clip: Clip, overlay_png: bytes, fmt: str,
                 seconds: int = MAX_VIDEO_SECONDS) -> bytes:
    """
    Produce the branded MP4 — silent by design.

    Scales/crops the clip to the exact output size (cover), trims to `seconds`,
    composites the overlay PNG, and encodes a web-friendly H.264 MP4 with the
    audio track dropped (-an). The output is deliberately soundless: agents add
    their own music or voiceover in the posting app, where they can pick a
    trending track that the platform licenses. Returns the MP4 bytes. Raises
    VideoError on any failure.
    """
    ffmpeg = ffmpeg_bin()
    if not ffmpeg:
        raise VideoError("FFmpeg is not installed on the server, so video posts can't be rendered.")
    if fmt not in sk.FORMATS:
        raise VideoError(f"Unknown format {fmt!r}.")

    width, height, _ = sk.FORMATS[fmt]
    seconds = max(1, min(int(seconds or MAX_VIDEO_SECONDS), MAX_VIDEO_SECONDS))

    workdir = tempfile.mkdtemp(prefix="vk_")
    src = os.path.join(workdir, "src.mp4")
    overlay_path = os.path.join(workdir, "overlay.png")
    out = os.path.join(workdir, "out.mp4")
    try:
        _download(clip.download_url, src)
        with open(overlay_path, "wb") as fh:
            fh.write(overlay_png)

        # Scale to cover the frame, centre-crop, drop SAR quirks, then overlay.
        vf = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1[bg];"
            f"[bg][1:v]overlay=0:0:format=auto[v]"
        )
        cmd = [
            ffmpeg, "-y",
            "-i", src,
            "-i", overlay_path,
            "-filter_complex", vf,
            "-map", "[v]",
            "-t", str(seconds),
            "-r", str(OUTPUT_FPS),
            "-c:v", "libx264",
            "-preset", X264_PRESET,
            "-crf", str(X264_CRF),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",                      # no audio — agents add their own track when posting
            out,
        ]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=FFMPEG_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise VideoError("Rendering took too long and was stopped — try a shorter or smaller clip.")

        if proc.returncode != 0:
            tail = (proc.stderr or b"").decode("utf-8", "replace")[-600:]
            raise VideoError(f"FFmpeg failed to render the video.\n{tail}")

        with open(out, "rb") as fh:
            return fh.read()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
