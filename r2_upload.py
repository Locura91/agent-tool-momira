"""
Cloudflare R2 logo storage.

Thin wrapper. Adapted from the r2_client.py already in the Momira TC repo,
stripped to just the two operations the SaaS app needs: upload and delete.
"""

from __future__ import annotations

import io
import os
import uuid

import boto3
from botocore.config import Config

_R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
_R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
_R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
_R2_BUCKET = os.getenv("R2_BUCKET", "social-kit-logos")
_R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=_R2_ACCESS_KEY_ID,
        aws_secret_access_key=_R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_logo(data: bytes, content_type: str, agent_id: str) -> tuple[str, str]:
    """
    Upload a logo image to R2.

    Returns (r2_key, public_url).  The key is stored in the DB so we can
    delete the old logo when the agent uploads a new one.
    """
    ext = "png" if "png" in content_type else "jpg"
    key = f"logos/{agent_id}/{uuid.uuid4().hex}.{ext}"

    _client().put_object(
        Bucket=_R2_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000",
    )

    public_url = f"{_R2_PUBLIC_URL}/{key}"
    return key, public_url


def delete_logo(r2_key: str) -> None:
    """Best-effort. Called before uploading a replacement logo."""
    try:
        _client().delete_object(Bucket=_R2_BUCKET, Key=r2_key)
    except Exception:
        pass  # stale key — not worth crashing over
