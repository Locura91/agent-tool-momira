"""
Currency conversion using a free live exchange-rate API.

Travel Compositor only exposes *manual* exchange rates (ones an operator types
in), so there is no automatic daily rate to read from it. Instead we use a free,
no-key rate feed (open.er-api.com, ~160 currencies incl. the exotic ones travel
packages hit — EGP, MAD, AED …), cached so we call it at most twice a day.

Design rules, so a rate problem can never put a wrong price on a post:
  • Every lookup returns Optional[float]. None means "no reliable rate" and the
    caller must then show the original currency untouched — never a guess.
  • Failures are swallowed: on a network/API error we serve the last good cached
    rates if we have them, otherwise None.
  • Converting a currency to itself is always exactly 1.0, no network call.

Requires: requests. The rate host must be reachable from the server (it is on
Render; it is blocked from the sandbox dev proxy, which is why conversion simply
falls back to the base currency there).
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple

import requests

MODULE_BUILD = "2026-10-06-fx-open-er-api"

_API = "https://open.er-api.com/v6/latest/{base}"
_TTL = 12 * 3600          # refresh at most twice a day
_TIMEOUT = 12

# base currency -> (fetched_at, {CURRENCY: rate})
_cache: Dict[str, Tuple[float, Dict[str, float]]] = {}
_lock = threading.Lock()


def _fetch(base: str) -> Dict[str, float]:
    resp = requests.get(_API.format(base=base), timeout=_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if data.get("result") != "success":
        raise ValueError(data.get("error-type", "fx: unsuccessful response"))
    rates = data.get("rates") or {}
    if not rates:
        raise ValueError("fx: empty rates")
    return {str(k).upper(): float(v) for k, v in rates.items()}


def _rates(base: str) -> Optional[Dict[str, float]]:
    base = (base or "").upper()
    if not base:
        return None
    now = time.time()
    with _lock:
        hit = _cache.get(base)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        rates = _fetch(base)
    except Exception:
        # Serve stale rates if we have any; otherwise give up (caller falls back).
        return hit[1] if hit else None
    with _lock:
        _cache[base] = (now, rates)
    return rates


def rate(frm: str, to: str) -> Optional[float]:
    """Units of `to` per 1 unit of `frm`, or None if no reliable rate."""
    frm, to = (frm or "").upper(), (to or "").upper()
    if not frm or not to:
        return None
    if frm == to:
        return 1.0
    rates = _rates(frm)
    if rates and to in rates:
        return rates[to]
    # Fall back to the inverse table (fetch `to` as base and invert).
    inv = _rates(to)
    if inv and frm in inv and inv[frm]:
        return 1.0 / inv[frm]
    return None


def convert(amount: float, frm: str, to: str) -> Optional[float]:
    """Convert `amount` from `frm` to `to`, or None if no reliable rate."""
    r = rate(frm, to)
    return amount * r if r is not None else None
