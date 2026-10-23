"""
tc_sync.py — Travel Compositor booking sync.

Fetches all bookings from TC for the shared microsite, matches each booking's
`agency` field to an Agent's `agency_name`, and upserts a Booking row so agents
see their customers' completed trips automatically.

De-duplication key: tc_booking_ref.  If a booking already exists with that ref
for the same agent, it is skipped (not re-imported, not overwritten).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import social_kit as sk


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _parse_date(value: str | None) -> Optional[datetime]:
    """Parse YYYY-MM-DD or ISO datetime from TC; return UTC-aware datetime or None."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(value[:19], fmt[:len(value[:19].replace("T", "T"))])
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    # Try full ISO
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_booking_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw TC booking dict into fields we care about."""
    cp = data.get("contactPerson") or data.get("customer") or {}

    first = cp.get("name") or cp.get("firstName") or ""
    last = cp.get("lastName") or cp.get("surname") or ""
    email = cp.get("email") or cp.get("emailAddress") or ""

    pkg_title = (
        data.get("name")
        or data.get("title")
        or data.get("packageName")
        or data.get("productName")
        or data.get("packageTitle")
        or ""
    )
    pkg_id = (
        data.get("packageId")
        or data.get("productId")
        or data.get("holidayPackageId")
        or ""
    )
    agency = (
        data.get("agency")
        or data.get("agencyName")
        or data.get("agencyId")
        or ""
    )
    end_date = (
        data.get("endDate")
        or data.get("returnDate")
        or data.get("departureEndDate")
        or ""
    )
    ref = (
        str(data.get("id") or data.get("bookingId") or data.get("reference") or data.get("bookingReference") or "")
    )

    return {
        "ref": ref.strip(),
        "first_name": first.strip(),
        "last_name": last.strip(),
        "email": email.strip(),
        "package_id": str(pkg_id).strip() if pkg_id else "",
        "package_title": pkg_title.strip(),
        "agency": agency.strip(),
        "return_date": _parse_date(str(end_date)) if end_date else None,
    }


def fetch_tc_bookings(
    status_filter: str = "CONFIRMED",
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    Fetch bookings from Travel Compositor.

    TC endpoint: GET /booking/getBookings/{micrositeId}
    Returns a list of normalized booking dicts.
    """
    microsite = _env("TRAVELC_MICROSITE_ID", _env("TC_MICROSITE", "momiratravel"))
    client = sk.TCClient()

    try:
        data = client.get(
            f"/booking/getBookings/{microsite}",
            params={"status": status_filter, "limit": limit},
        )
    except Exception as e:
        print(f"[tc_sync] TC API error fetching bookings: {e}")
        return []

    # TC may return a list directly or wrap it
    if isinstance(data, dict):
        bookings_raw = (
            data.get("bookings")
            or data.get("booking")
            or data.get("results")
            or data.get("data")
            or []
        )
    elif isinstance(data, list):
        bookings_raw = data
    else:
        bookings_raw = []

    return [_extract_booking_fields(b) for b in bookings_raw if isinstance(b, dict)]


async def sync_tc_bookings(db: AsyncSession) -> Dict[str, int]:
    """
    Pull TC bookings and upsert into the local DB.

    Returns {"imported": N, "skipped": N, "no_agent": N, "errors": N}.
    """
    from models import Agent, Booking  # local import to avoid circular

    stats = {"imported": 0, "skipped": 0, "no_agent": 0, "errors": 0}

    # Load all agents that have an agency_name set
    agents_result = await db.execute(
        select(Agent).where(Agent.is_active == True, Agent.agency_name.isnot(None))
    )
    agents: List[Agent] = list(agents_result.scalars().all())
    if not agents:
        print("[tc_sync] No active agents with agency_name set — nothing to match.")
        return stats

    # Build a lookup: lowercase agency_name → agent
    agency_map: Dict[str, Agent] = {
        (a.agency_name or "").strip().lower(): a
        for a in agents
        if (a.agency_name or "").strip()
    }

    print(f"[tc_sync] Fetching TC bookings for {len(agency_map)} agencies…")
    tc_bookings = fetch_tc_bookings()
    print(f"[tc_sync] Got {len(tc_bookings)} bookings from TC.")

    for b in tc_bookings:
        if not b["ref"] or not b["email"]:
            stats["errors"] += 1
            continue

        # Match TC agency → local agent
        tc_agency_key = b["agency"].lower()
        agent = agency_map.get(tc_agency_key)
        if not agent:
            stats["no_agent"] += 1
            continue

        # Check for existing booking with same tc_booking_ref for this agent
        existing = await db.execute(
            select(Booking).where(
                Booking.agent_id == agent.id,
                Booking.tc_booking_ref == b["ref"],
            )
        )
        if existing.scalar_one_or_none():
            stats["skipped"] += 1
            continue

        # Create new booking
        try:
            booking = Booking(
                agent_id=agent.id,
                first_name=b["first_name"] or "Unknown",
                last_name=b["last_name"] or "",
                email=b["email"],
                package_id=b["package_id"] or None,
                package_title=b["package_title"] or None,
                return_date=b["return_date"],
                tc_booking_ref=b["ref"],
                feedback_status="pending",
            )
            db.add(booking)
            stats["imported"] += 1
        except Exception as e:
            print(f"[tc_sync] Error creating booking {b['ref']}: {e}")
            stats["errors"] += 1

    await db.commit()
    print(f"[tc_sync] Done. {stats}")
    return stats


async def sync_tc_bookings_for_agent(db: AsyncSession, agent: Any) -> Dict[str, int]:
    """
    Sync TC bookings for a single agent (by their agency_name).
    Same logic as sync_tc_bookings but scoped to one agent.
    """
    from models import Booking

    stats = {"imported": 0, "skipped": 0, "no_agent": 0, "errors": 0}
    agency_key = (agent.agency_name or "").strip().lower()
    if not agency_key:
        return stats

    print(f"[tc_sync] Fetching TC bookings for '{agent.agency_name}'…")
    tc_bookings = fetch_tc_bookings()
    print(f"[tc_sync] Got {len(tc_bookings)} total TC bookings.")

    for b in tc_bookings:
        if not b["ref"] or not b["email"]:
            stats["errors"] += 1
            continue

        if b["agency"].strip().lower() != agency_key:
            stats["no_agent"] += 1
            continue

        existing = await db.execute(
            select(Booking).where(
                Booking.agent_id == agent.id,
                Booking.tc_booking_ref == b["ref"],
            )
        )
        if existing.scalar_one_or_none():
            stats["skipped"] += 1
            continue

        try:
            booking = Booking(
                agent_id=agent.id,
                first_name=b["first_name"] or "Unknown",
                last_name=b["last_name"] or "",
                email=b["email"],
                package_id=b["package_id"] or None,
                package_title=b["package_title"] or None,
                return_date=b["return_date"],
                tc_booking_ref=b["ref"],
                feedback_status="pending",
            )
            db.add(booking)
            stats["imported"] += 1
        except Exception as e:
            print(f"[tc_sync] Error creating booking {b['ref']}: {e}")
            stats["errors"] += 1

    await db.commit()
    print(f"[tc_sync] Agent sync done. {stats}")
    return stats
