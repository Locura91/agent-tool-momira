"""
Logo storage — database edition.

Logos are stored as base64 data URLs directly in the Agent row.
No external storage service (Cloudflare R2, S3, etc.) is required.

Max logo size after base64 encoding is ~350 KB for a 5 MB PNG, well within
SQLite's text column limits.  For a production deployment with many agents,
swap this module back to the R2 implementation and set the four R2_* env vars.

The public interface (upload_logo / delete_logo) is unchanged so app.py
does not need to be touched.
"""

from __future__ import annotations

import base64
import uuid


def upload_logo(data: bytes, content_type: str, agent_id: str) -> tuple[str, str]:
    """
    Encode a logo as a data URL and return a fake key + the data URL.

    The "key" is stored in logo_r2_key for legacy compatibility but is not
    used for anything — it just needs to be non-None so the delete path works.
    The data URL is stored in logo_url and is served directly to the browser.
    """
    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:{content_type};base64,{b64}"
    key = f"db/{agent_id}/{uuid.uuid4().hex}"   # synthetic key, never hits R2
    return key, data_url


def delete_logo(r2_key: str) -> None:
    """
    Nothing to delete — the data URL is cleared by setting logo_url = None
    on the Agent row, which app.py already does before calling this.
    """
    pass
