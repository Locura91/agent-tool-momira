"""
Social kit — a Holiday Package ID in, a finished post out.

A port of the tool built into the multiwander.com WordPress plugin, rewritten
for this platform: same Travel Compositor calls, same Polish copy, same two
poster templates, but drawn with Pillow instead of PHP's GD and with no
WordPress anywhere in it.

Deliberately self-contained. It talks to Travel Compositor itself rather than
borrowing api_client.py, because api_client is built for WRITING products
(ClosedTour, Ticket, Transfer…) and knows nothing about reading a published
holiday package. The three endpoints needed here are read-only and unrelated
to anything that module does, so coupling them would buy nothing and risk
breaking uploads. It does read the same four environment variables app.py
already reads, so there is nothing new to configure.

What it produces, from one ID:

    captions(data, url)              three Polish captions, ready to paste
    hashtags(data)                   the tag set
    render(data, fmt, style, photo)  a finished JPG at the exact network size

Everything the copy claims is taken from the package itself — the route, the
length, the real departure dates, the price. Nothing is invented, which is
what makes the output safe to post without reading it first.

Requires: requests, Pillow.
"""

from __future__ import annotations

MODULE_BUILD = "2026-09-27-social-kit-momira-only-and-image-fallback"

import io
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import fx

# --------------------------------------------------------------------------
# Travel Compositor
# --------------------------------------------------------------------------

_TIMEOUT = 45


class TCError(RuntimeError):
    """Anything Travel Compositor refused to do."""


@dataclass
class TCConfig:
    base: str
    microsite: str
    username: str
    password: str

    # The live Momira TC tool (momira-tc-tool/travelcompositor_api.py) uses this
    # base URL. `api.travelcompositor.com` is the Travel Compositor *website*,
    # which answers /authentication/authenticate with an HTML 404 page — the
    # exact "Login refused (HTTP 404)" symptom. These defaults keep login working
    # even if TRAVELC_BASE_URL / TRAVELC_MICROSITE_ID are unset or mis-set.
    DEFAULT_BASE = "https://online.travelcompositor.com/resources"
    DEFAULT_MICROSITE = "momiratravel"

    @classmethod
    def from_env(cls) -> "TCConfig":
        """Only the username and password must be set; the base URL and microsite
        fall back to Momira's known-good values so a wrong TRAVELC_BASE_URL can't
        break login."""
        missing = [
            k
            for k in ("TRAVELC_USERNAME", "TRAVELC_PASSWORD")
            if not os.environ.get(k)
        ]
        if missing:
            raise TCError("Missing environment variables: " + ", ".join(missing))

        base = (os.environ.get("TRAVELC_BASE_URL") or cls.DEFAULT_BASE).rstrip("/")
        # api.travelcompositor.com is the website, not the REST API — correct it.
        if "api.travelcompositor.com" in base:
            base = cls.DEFAULT_BASE

        return cls(
            base=base,
            microsite=os.environ.get("TRAVELC_MICROSITE_ID") or cls.DEFAULT_MICROSITE,
            username=os.environ["TRAVELC_USERNAME"],
            password=os.environ["TRAVELC_PASSWORD"],
        )


class TCClient:
    """
    Three GETs and a login.

    The token arrives as a RESPONSE HEADER called `auth-token`, not in the
    body, and subsequent requests send it back as a REQUEST header of the same
    name — Travel Compositor does not use `Authorization: Bearer`. That single
    detail is the thing that wastes an afternoon if you assume otherwise.
    """

    def __init__(self, config: Optional[TCConfig] = None) -> None:
        self.config = config or TCConfig.from_env()
        self._token: Optional[str] = None

    # -- auth ---------------------------------------------------------------

    def authenticate(self, force: bool = False) -> str:
        if self._token and not force:
            return self._token

        response = requests.post(
            f"{self.config.base}/authentication/authenticate",
            json={
                "username": self.config.username,
                "password": self.config.password,
                "micrositeId": self.config.microsite,
            },
            timeout=30,
        )

        if not response.ok:
            raise TCError(f"Login refused (HTTP {response.status_code}): {response.text[:300]}")

        token = response.headers.get("auth-token")

        if not token:  # documented fallback; not seen in practice
            try:
                body = response.json()
                token = body.get("token") or body.get("authToken") or body.get("auth-token")
            except ValueError:
                token = response.text.strip('" \n\r\t')

        if not token:
            raise TCError("Login succeeded but no auth-token came back.")

        self._token = token
        return token

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """One GET, retried once against an expired token."""
        for attempt in (0, 1):
            token = self.authenticate(force=bool(attempt))
            response = requests.get(
                f"{self.config.base}{path}",
                params=params or {},
                headers={"auth-token": token, "Accept": "application/json"},
                timeout=_TIMEOUT,
            )

            if response.status_code == 401 and attempt == 0:
                continue  # token expired; log in again and retry

            if not response.ok:
                raise TCError(f"GET {path} failed (HTTP {response.status_code}): {response.text[:300]}")

            return response.json()

        raise TCError(f"GET {path} failed after re-authenticating.")

    # -- the three package endpoints ----------------------------------------

    def info(self, package_id: str, lang: str = "PL") -> Dict[str, Any]:
        return self.get(f"/package/{self.config.microsite}/info/{package_id}", {"lang": lang})

    def detail(self, package_id: str, lang: str = "PL") -> Dict[str, Any]:
        return self.get(f"/package/{self.config.microsite}/{package_id}", {"lang": lang})

    def calendar(self, package_id: str, lang: str = "PL") -> Dict[str, Any]:
        return self.get(f"/package/calendar/{self.config.microsite}/{package_id}", {"lang": lang})


# --------------------------------------------------------------------------
# Normalising what comes back
# --------------------------------------------------------------------------


def _pick(source: Dict[str, Any], names: Iterable[str], default: Any = None) -> Any:
    """First of several spellings that carries a value. TC is inconsistent."""
    if not isinstance(source, dict):
        return default

    lowered = {str(k).lower(): k for k in source}

    for name in names:
        key = lowered.get(name.lower())
        if key is not None and source[key] not in (None, ""):
            return source[key]

    return default


@dataclass
class Package:
    """Everything a post needs, and nothing else."""

    id: str = ""
    title: str = ""
    description: str = ""
    days: int = 0
    nights: int = 0
    price: float = 0.0
    currency: str = "EUR"
    destinations: List[Dict[str, str]] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    gallery: List[str] = field(default_factory=list)
    departures: List[str] = field(default_factory=list)
    flights: int = 0
    hotels: int = 0
    hotel_names: List[str] = field(default_factory=list)          # names of accommodations
    hotel_nights: List[int] = field(default_factory=list)         # nights per hotel (parallel to hotel_names)
    hotel_stars: List[int] = field(default_factory=list)          # star category per hotel (0 = unknown)
    hotel_boards: List[str] = field(default_factory=list)         # board basis per hotel ("" = unknown)
    transport_counts: Dict[str, int] = field(default_factory=dict) # e.g. {"flights":2,"ferries":1}
    activities: List[str] = field(default_factory=list)           # ticket/activity names
    is_round_trip: bool = False                                    # departs and returns to same origin
    # CONFIRMED REAL GAP (2026-09-27): Holiday Package's image/gallery field names were never
    # confirmed against a live response before this module was written (see
    # claude/multiwander-tc-api-briefing-2026-09-05.md: "Images/gallery field names for a
    # Holiday Package specifically are NOT covered by anything confirmed... this is genuinely
    # unmapped territory, treat it the same as the itinerary fields: inspect a real response
    # before parsing"). The first live test (Chris, 2026-09-27) hit exactly this - "no
    # photographs" on a package that has them in Travel Compositor. `raw` keeps the untouched
    # `info`/`detail`/`calendar` responses so the UI can show them for on-the-spot diagnosis
    # instead of a dead end, and `_find_image_urls` below is a field-name-agnostic fallback that
    # finds photographs even before the real field name is confirmed.
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def fixed_departures(self) -> bool:
        return bool(self.departures)


_IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|webp|gif)(\?|$)", re.IGNORECASE)


def _find_image_urls(node: Any, limit: int = 12, _seen: Optional[List[str]] = None) -> List[str]:
    """
    Walk any nested dict/list looking for strings that are plainly image URLs.

    A field-name-agnostic fallback for exactly the situation documented on `Package.raw`
    above: the named keys this module guesses (`imageUrls`/`images`/`gallery`) are not
    confirmed against a real Holiday Package response, so when they come up empty this finds
    photographs anyway by shape (`http...` + an image extension) rather than by a key name
    that might be wrong. Deliberately conservative - a real photo CDN URL almost always ends
    in a normal image extension, so this rarely mis-fires on unrelated strings (a description
    or a destination name never matches `_IMAGE_EXT_RE`).
    """
    found: List[str] = _seen if _seen is not None else []

    if len(found) >= limit:
        return found

    if isinstance(node, str):
        candidate = node.strip()
        if candidate.startswith("http") and _IMAGE_EXT_RE.search(candidate) and candidate not in found:
            found.append(candidate)
    elif isinstance(node, dict):
        for value in node.values():
            _find_image_urls(value, limit, found)
            if len(found) >= limit:
                break
    elif isinstance(node, list):
        for item in node:
            _find_image_urls(item, limit, found)
            if len(found) >= limit:
                break

    return found


def fetch(client: TCClient, package_id: str, brand: "Brand" = None, lang: Optional[str] = None) -> Package:
    """
    One ID becomes one Package.

    The language comes from the brand, so Travel Compositor returns the
    destination names, the themes and the description already translated —
    Momira reads the English catalogue, MultiWander the Polish one, and
    nothing has to be mapped by hand afterwards. Detail and calendar are
    optional; a package still posts without them.
    """
    lang = lang or (brand.tc_lang if brand else "PL")
    package_id = re.sub(r"\D", "", str(package_id))
    if not package_id:
        raise TCError("That is not a package ID.")

    info = client.info(package_id, lang)

    try:
        detail = client.detail(package_id, lang)
    except TCError:
        detail = {}

    try:
        calendar = client.calendar(package_id, lang)
    except TCError:
        calendar = {}

    return normalise(package_id, info, detail, calendar)


# --------------------------------------------------------------------------
# Board basis (meal plan) — normalised to five labels
# --------------------------------------------------------------------------
#
# Travel Compositor's exact field name for a hotel's board is not confirmed
# against a live Holiday Package response, and it varies (board / boardType /
# mealPlan / regime …), sometimes a two-letter industry code, sometimes a
# translated phrase. So rather than trust one key, _extract_board scans the
# board-ish keys on the hotel-stay object (and any nested room) and maps
# whatever it finds — a code or a phrase in several languages — to one of the
# five labels the agencies use. Anything unrecognised returns "" and simply
# isn't shown, so a wrong guess can never put a false meal plan on the flyer.

BOARD_LABELS = ("Only Room", "With Breakfast", "Half Board", "Full Board", "All Inclusive")

_BOARD_CODES = {
    "ro": "Only Room", "ob": "Only Room", "so": "Only Room", "sa": "Only Room",
    "oa": "Only Room", "nb": "Only Room", "rr": "Only Room",
    "bb": "With Breakfast", "ad": "With Breakfast", "ci": "With Breakfast", "br": "With Breakfast",
    "hb": "Half Board", "mp": "Half Board", "map": "Half Board", "dp": "Half Board",
    "fb": "Full Board", "pc": "Full Board", "ap": "Full Board", "fap": "Full Board",
    "ai": "All Inclusive", "ti": "All Inclusive", "uai": "All Inclusive", "ri": "All Inclusive",
    "todo": "All Inclusive",
}

# Checked in this order so the richer board wins (all-inclusive before full,
# full before half, half before breakfast, breakfast before room-only).
_BOARD_TEXT = [
    ("All Inclusive", ["all inclusive", "all-inclusive", "all in", "todo incluido", "alles inklusive",
                        "tutto incluso", "wszystko w cenie", "ultra all"]),
    ("Full Board", ["full board", "pension completa", "pensión completa", "vollpension", "voll pension",
                    "pensione completa", "volpension", "volledig pension", "pension complete",
                    "pension complète", "pelne wyzywienie", "pełne wyżywienie"]),
    ("Half Board", ["half board", "media pension", "media pensión", "halbpension", "halb pension",
                    "mezza pensione", "halfpension", "half pension", "demi pension", "demi-pension",
                    "niepelne wyzywienie", "niepełne wyżywienie", "2 posilki", "2 posiłki"]),
    ("With Breakfast", ["bed and breakfast", "bed & breakfast", "breakfast", "desayuno", "fruhstuck",
                        "frühstück", "colazione", "ontbijt", "petit dejeuner", "petit-déjeuner",
                        "ze sniadaniem", "ze śniadaniem", "sniadanie", "śniadanie"]),
    ("Only Room", ["room only", "only room", "no meals", "without meals", "solo alojamiento",
                   "sin comidas", "nur ubernachtung", "nur übernachtung", "nur zimmer", "senza pasti",
                   "solo pernottamento", "alleen kamer", "bez wyzywienia", "bez wyżywienia", "tylko nocleg"]),
]


def _board_label(raw: Any) -> str:
    """Map a raw board value (code or phrase, any of several languages) to a label."""
    s = str(raw or "").strip().lower()
    if not s:
        return ""
    token = re.sub(r"[^a-z]", "", s)
    # Short alpha token → treat as an industry code (HB, FB, AI, …).
    if 1 < len(token) <= 4 and token in _BOARD_CODES:
        return _BOARD_CODES[token]
    for label, needles in _BOARD_TEXT:
        if any(n in s for n in needles):
            return label
    if token in _BOARD_CODES:
        return _BOARD_CODES[token]
    return ""


def _extract_board(h: Dict[str, Any]) -> str:
    """Find a hotel stay's board basis without relying on one field name."""
    if not isinstance(h, dict):
        return ""

    def scan(d: Any) -> str:
        if not isinstance(d, dict):
            return ""
        for k, v in d.items():
            kl = str(k).lower()
            if any(t in kl for t in ("board", "meal", "pension", "regime", "basis")):
                if isinstance(v, dict):
                    cand = _pick(v, ["name", "description", "code", "value", "type", "text"], "")
                    lab = _board_label(cand)
                elif isinstance(v, list):
                    lab = next((x for x in (_board_label(i) for i in v) if x), "")
                else:
                    lab = _board_label(v)
                if lab:
                    return lab
        return ""

    label = scan(h)
    if not label and isinstance(h.get("hotelData"), dict):
        label = scan(h["hotelData"])
    if not label:
        for rk in ("room", "rooms", "roomList", "roomOptions"):
            rooms = h.get(rk)
            if isinstance(rooms, dict):
                label = scan(rooms)
            elif isinstance(rooms, list):
                for r in rooms:
                    label = scan(r)
                    if label:
                        break
            if label:
                break
    return label


def normalise(package_id: str, info: Dict[str, Any], detail: Dict[str, Any], calendar: Dict[str, Any]) -> Package:
    pack = Package(id=package_id)
    pack.raw = {"info": info, "detail": detail, "calendar": calendar}

    pack.title = str(_pick(info, ["title", "name"], "")).strip()
    raw_desc = str(_pick(info, ["description", "shortDescription", "remarks"], "") or "").strip()
    # Strip HTML tags from description (TC wraps text in <p>, <strong>, etc.)
    # then decode HTML entities (&nbsp; &amp; &#243; etc.) so no HTML code leaks into the flyer.
    import re as _re
    import html as _html
    _desc = _re.sub(r"<[^>]+>", " ", raw_desc)
    _desc = _html.unescape(_desc)
    pack.description = " ".join(_desc.split())  # collapse whitespace

    pack.days = int(_pick(info, ["days", "duration"], 0) or 0)
    pack.nights = int(_pick(info, ["nights"], max(0, pack.days - 1)) or 0)

    price = _pick(info, ["pricePerPerson", "price", "fromPrice"], None)
    if isinstance(price, dict):
        pack.price = float(_pick(price, ["amount", "value"], 0) or 0)
        pack.currency = str(_pick(price, ["currency"], "EUR"))
    elif price is not None:
        try:
            pack.price = float(price)
        except (TypeError, ValueError):
            pack.price = 0.0

    for stop in _pick(detail, ["destinations"], []) or _pick(info, ["destinations"], []) or []:
        if not isinstance(stop, dict):
            continue
        name = str(_pick(stop, ["name", "destination", "city"], "")).strip()
        if name:
            pack.destinations.append({"name": name, "country": str(_pick(stop, ["country"], "")).strip()})

    for theme in _pick(info, ["themes", "categories"], []) or []:
        if isinstance(theme, dict):
            theme = _pick(theme, ["name", "title"], "")
        theme = str(theme).strip()
        if theme:
            pack.themes.append(theme)

    for source in (info, detail):
        for image in _pick(source, ["imageUrls", "images", "gallery", "galleryImages", "photos", "media"], []) or []:
            if isinstance(image, dict):
                image = _pick(image, ["url", "imageUrl", "src", "fullUrl", "path"], "")
            image = str(image).strip()
            if image.startswith("http") and image not in pack.gallery:
                pack.gallery.append(image)
        # TC API also provides a single imageUrl field on the info object
        single_img = source.get("imageUrl") if isinstance(source, dict) else None
        if single_img and str(single_img).startswith("http") and str(single_img) not in pack.gallery:
            pack.gallery.append(str(single_img))

    # Pull per-destination imageUrls (proper destination photos, not departure city)
    for dest in _pick(detail, ["destinations"], []) or []:
        if not isinstance(dest, dict):
            continue
        for img_url in dest.get("imageUrls") or []:
            img_url = str(img_url).strip()
            if img_url.startswith("http") and img_url not in pack.gallery:
                pack.gallery.append(img_url)

    # Named-field lookup above is a guess (see Package.raw's docstring for why) - when it comes
    # up empty, fall back to finding photographs by shape rather than giving up on a package
    # that may well have them under a field name this module doesn't know about yet.
    if not pack.gallery:
        pack.gallery = _find_image_urls(info) or _find_image_urls(detail)

    transports = _pick(detail, ["transports"], []) or []
    transport_counts: Dict[str, int] = {}
    for t in transports:
        if not isinstance(t, dict):
            continue
        ttype = str(_pick(t, ["transportType", "type"], "")).upper()
        if "FLIGHT" in ttype:
            key = "flights"
        elif "FERRY" in ttype or "BOAT" in ttype or "SHIP" in ttype:
            key = "ferries"
        elif "BUS" in ttype or "COACH" in ttype:
            key = "buses"
        elif "TRANSFER" in ttype:
            key = "transfers"
        elif "TRAIN" in ttype or "RAIL" in ttype:
            key = "trains"
        elif "VAN" in ttype or "CAR" in ttype or "TAXI" in ttype or "PRIVATE" in ttype:
            key = "cars"
        else:
            key = "other"
        transport_counts[key] = transport_counts.get(key, 0) + 1
    # Also count airport transfers from the separate detail.transfers array
    transfer_list = _pick(detail, ["transfers"], []) or []
    if transfer_list:
        transport_counts["transfers"] = transport_counts.get("transfers", 0) + len(transfer_list)
    pack.transport_counts = transport_counts
    pack.flights = transport_counts.get("flights", 0)

    hotel_list = _pick(detail, ["hotels", "accommodations"], []) or []
    pack.hotels = len(hotel_list)
    pack.hotel_names = []
    pack.hotel_stars = []
    for h in hotel_list:
        if isinstance(h, dict):
            # TC API nests hotel name under hotelData.name
            hotel_data = h.get("hotelData") or {}
            if isinstance(hotel_data, dict):
                name = str(_pick(hotel_data, ["name", "hotelName", "title", "accommodationName"], "")).strip()
                # Star category: "category" field is typically "4" or "5" etc.
                raw_cat = hotel_data.get("category") or hotel_data.get("stars") or h.get("category") or h.get("stars") or ""
            else:
                name = ""
                raw_cat = h.get("category") or h.get("stars") or ""
            # Fall back to top-level fields if hotelData had nothing
            if not name:
                name = str(_pick(h, ["name", "hotelName", "title", "accommodationName"], "")).strip()
            try:
                stars = int(str(raw_cat).strip()) if raw_cat else 0
            except (ValueError, TypeError):
                stars = 0
            if name:
                pack.hotel_names.append(name)
                pack.hotel_nights.append(int(h.get("nights") or 0))
                pack.hotel_stars.append(stars)
                pack.hotel_boards.append(_extract_board(h))
            # Also harvest hotel images into the gallery
            hotel_images = hotel_data.get("images") or [] if isinstance(hotel_data, dict) else []
            for img in hotel_images:
                if isinstance(img, dict):
                    img_url = str(_pick(img, ["url", "imageUrl", "src", "fullUrl", "path"], "")).strip()
                else:
                    img_url = str(img).strip()
                if img_url.startswith("http") and img_url not in pack.gallery:
                    pack.gallery.append(img_url)
        elif isinstance(h, str) and h.strip():
            pack.hotel_names.append(h.strip())
            pack.hotel_nights.append(0)
            pack.hotel_stars.append(0)
            pack.hotel_boards.append("")

    # Activities from tickets (day tours, entrance tickets, etc.)
    for ticket in _pick(detail, ["tickets"], []) or []:
        if isinstance(ticket, dict):
            name = str(_pick(ticket, ["name", "title", "description"], "") or "").strip()
            # Strip HTML tags + decode entities from activity names too
            import re as _re2
            import html as _html2
            name = _html2.unescape(_re2.sub(r"<[^>]+>", " ", name))
            name = " ".join(name.split())
            if name and name not in pack.activities:
                pack.activities.append(name)
    for tour in _pick(detail, ["closedTours"], []) or []:
        if isinstance(tour, dict):
            name = str(_pick(tour, ["name", "title"], "") or "").strip()
            if name and name not in pack.activities:
                pack.activities.append(name)

    # Round-trip detection: first and last flight share same origin/destination airport code
    if transports:
        first_t = transports[0] if isinstance(transports[0], dict) else {}
        last_t = transports[-1] if isinstance(transports[-1], dict) else {}
        first_origin = str(first_t.get("originCode") or first_t.get("origin") or "").upper()
        last_target = str(last_t.get("targetCode") or last_t.get("target") or "").upper()
        if first_origin and last_target and first_origin == last_target:
            pack.is_round_trip = True

    # Departures: future dates only, so a package last synced months ago never
    # advertises a sailing that has already gone.
    today = datetime.now().strftime("%Y-%m-%d")
    for row in _pick(calendar, ["holidayPackagesDates", "dates"], []) or []:
        date = row.get("date") if isinstance(row, dict) else row
        date = str(date or "")[:10]
        if date and date >= today:
            pack.departures.append(date)

    pack.departures.sort()

    return pack



# --------------------------------------------------------------------------
# Brands
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Brand:
    """
    One company's voice, currency and language, in one place.

    The two brands sell the same Travel Compositor inventory to different
    people, so almost everything differs: Momira Travel posts in English and
    quotes euro; MultiWander posts in Polish and quotes złoty. Travel
    Compositor itself is asked for the right language too, so the destination
    names, the themes and the description all arrive already translated and
    nothing has to be mapped by hand.

    Adding a third brand is a dictionary entry, not a branch in the code.
    """

    key: str
    name: str
    lang: str            # copy language: "en" or "pl"
    tc_lang: str         # what Travel Compositor is asked for
    currency: str        # what the post quotes
    site: str
    wordmark: str
    url: str
    tags: Tuple[str, ...]

    @property
    def converts_to_pln(self) -> bool:
        return self.currency == "PLN"


BRANDS: Dict[str, Brand] = {
    "momira": Brand(
        key="momira",
        name="Momira Travel",
        lang="en",
        tc_lang="EN",
        currency="EUR",
        site="momira.travel",
        wordmark="MOMIRA TRAVEL",
        url="https://momira.travel/",
        tags=("#MomiraTravel", "#TailorMadeTravel", "#TravelYourWay", "#TripOfALifetime"),
    ),
    "multiwander": Brand(
        key="multiwander",
        name="MultiWander",
        lang="pl",
        tc_lang="PL",
        currency="PLN",
        site="multiwander.com",
        wordmark="MULTIWANDER",
        url="https://multiwander.com/pakiety-podrozy/",
        tags=("#MultiWander", "#PodrozeSzyteNaMiare", "#WakacjeMarzen", "#PodrozujMadrzej"),
    ),
}

DEFAULT_BRAND = BRANDS["multiwander"]


# --------------------------------------------------------------------------
# The words
# --------------------------------------------------------------------------

_MONTHS = {
    "pl": ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
           "lipca", "sierpnia", "września", "października", "listopada", "grudnia"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni",
           "Juli", "August", "September", "Oktober", "November", "Dezember"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio",
           "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
    "nl": ["januari", "februari", "maart", "april", "mei", "juni",
           "juli", "augustus", "september", "oktober", "november", "december"],
}

# The opening line, chosen by theme. It is the only part of a caption most
# people read, so a generic one wastes the post. Matched on a folded fragment
# because Travel Compositor names these differently in each language.
_HOOKS = {
    "pl": {
        "safari": "Poranek na sawannie zaczyna się dźwiękiem, nie budzikiem.",
        "island": "Każdego ranka inna wyspa, inna plaża i inny widok z pokładu.",
        "samoch": "Własne auto, własne tempo — zatrzymujesz się tam, gdzie chcesz.",
        "plaz": "Najpierw miasto, potem morze. Jeden wyjazd, dwa zupełnie różne tygodnie.",
        "city break": "Kilka dni wystarczy, żeby poczuć miasto — reszta to tylko wymówki.",
        "dookola": "Jedna podróż, kilka kontynentów i bilet, który zamyka koło.",
    },
    "en": {
        "safari": "Morning on the savannah begins with a sound, not an alarm clock.",
        "island": "A different island each morning, a different beach, a different view from the deck.",
        "rent a car": "Your own car, your own pace — you stop where you feel like stopping.",
        "self drive": "Your own car, your own pace — you stop where you feel like stopping.",
        "beach": "City first, then the sea. One trip, two completely different weeks.",
        "city break": "A few days is enough to get the measure of a city. The rest is excuses.",
        "around the world": "One journey, several continents, and a ticket that closes the circle.",
    },
}

_COPY = {
    "pl": {
        "hook_place": "{place} — i jeszcze kilka miejsc, o których nie mówi się w folderach.",
        "hook_none": "Podróż ułożona od początku do końca — i wciąż w pełni Twoja.",
        "days": "{days} dni",
        "nights": " / {nights} nocy",
        "any_date": "Wylot w dowolnym terminie — Ty wybierasz datę.",
        "next_date": "Najbliższy termin: {date}. Liczba terminów ograniczona ({count} w kalendarzu).",
        "per_person": "od {price} za osobę",
        "per_person_short": "od {price} / os.",
        "flights": "✈️ Przeloty w cenie ({count})",
        "hotels": "🏨 Hotele: {count}",
        "customisable": [
            "✏️ To propozycja, nie sztywny pakiet:",
            "• zmienisz długość pobytu",
            "• wybierzesz lotnisko wylotu",
            "• dobierzesz hotele i kolejność miejsc",
        ],
        "customisable_plain": (
            "Każdą podróż układamy pod Ciebie: długość pobytu, lotnisko wylotu, hotele "
            "i kolejność miejsc możesz zmienić. Napisz, a przygotujemy wersję dla Ciebie."
        ),
        "cta_inspiracja": "Zobacz cały program i wyślij zapytanie 👇",
        "cta_konkret": "Ułóż tę podróż po swojemu i wyślij zapytanie 👇",
        "gbp_head": "{title} — {duration}{price}.",
        "gbp_price": ", od {price} za osobę",
        "gbp_trip": "podróż",
        "gbp_route": "Trasa: {route}.",
        "gbp_link": "Program, terminy i wycena: {url}",
        "poster_from": "od {price} / os.",
        "poster_cta": "Wybierz swój termin →",
        "poster_cta_short": "Wybierz termin →",
        "poster_days": "{days} dni",
    },
    "en": {
        "hook_place": "{place} — and a few more places the brochures never mention.",
        "hook_none": "A journey planned end to end — and still entirely yours.",
        "days": "{days} days",
        "nights": " / {nights} nights",
        "any_date": "Departs any day you choose.",
        "next_date": "Next departure: {date}. Limited dates ({count} in the calendar).",
        "per_person": "from {price} per person",
        "per_person_short": "from {price} pp",
        "flights": "✈️ Flights included ({count})",
        "hotels": "🏨 Hotels: {count}",
        "customisable": [
            "✏️ A starting point, not a fixed package:",
            "• change how long you stay",
            "• choose your departure airport",
            "• pick the hotels and the order of the stops",
        ],
        "customisable_plain": (
            "We build every trip around you: the length, the departure airport, the hotels and "
            "the order of the stops can all change. Write to us and we will put together your version."
        ),
        "cta_inspiracja": "See the full itinerary and send an enquiry 👇",
        "cta_konkret": "Make it yours and send an enquiry 👇",
        "gbp_head": "{title} — {duration}{price}.",
        "gbp_price": ", from {price} per person",
        "gbp_trip": "trip",
        "gbp_route": "Route: {route}.",
        "gbp_link": "Itinerary, dates and a quote: {url}",
        "poster_from": "from {price} p.p.",
        "poster_cta": "Choose your dates →",
        "poster_cta_short": "Choose dates →",
        "poster_days": "{days} days",
    },
    "de": {
        "hook_place": "{place} — und noch ein paar Orte, die in keinem Katalog stehen.",
        "hook_none": "Eine von Anfang bis Ende geplante Reise — und trotzdem ganz Ihre.",
        "days": "{days} Tage",
        "nights": " / {nights} Nächte",
        "any_date": "Abflug an jedem Tag Ihrer Wahl.",
        "next_date": "Nächster Abflug: {date}. Begrenzte Termine ({count} im Kalender).",
        "per_person": "ab {price} pro Person",
        "per_person_short": "ab {price} p.P.",
        "flights": "✈️ Flüge inklusive ({count})",
        "hotels": "🏨 Hotels: {count}",
        "customisable": [
            "✏️ Ein Ausgangspunkt, kein festes Paket:",
            "• ändern Sie die Reisedauer",
            "• wählen Sie Ihren Abflughafen",
            "• wählen Sie Hotels und die Reihenfolge der Orte",
        ],
        "customisable_plain": (
            "Wir gestalten jede Reise nach Ihren Wünschen: Dauer, Abflughafen, Hotels "
            "und die Reihenfolge der Orte lassen sich anpassen. Schreiben Sie uns, und "
            "wir stellen Ihre Version zusammen."
        ),
        "cta_inspiracja": "Sehen Sie das komplette Programm und senden Sie eine Anfrage 👇",
        "cta_konkret": "Gestalten Sie die Reise nach Ihren Wünschen und senden Sie eine Anfrage 👇",
        "gbp_head": "{title} — {duration}{price}.",
        "gbp_price": ", ab {price} pro Person",
        "gbp_trip": "Reise",
        "gbp_route": "Route: {route}.",
        "gbp_link": "Programm, Termine und Angebot: {url}",
        "poster_from": "ab {price} p.P.",
        "poster_cta": "Wählen Sie Ihren Termin →",
        "poster_cta_short": "Termin wählen →",
        "poster_days": "{days} Tage",
    },
    "es": {
        "hook_place": "{place} — y algunos lugares más que los folletos nunca mencionan.",
        "hook_none": "Un viaje planificado de principio a fin — y aun así totalmente tuyo.",
        "days": "{days} días",
        "nights": " / {nights} noches",
        "any_date": "Salida cualquier día que elijas.",
        "next_date": "Próxima salida: {date}. Fechas limitadas ({count} en el calendario).",
        "per_person": "desde {price} por persona",
        "per_person_short": "desde {price} p.p.",
        "flights": "✈️ Vuelos incluidos ({count})",
        "hotels": "🏨 Hoteles: {count}",
        "customisable": [
            "✏️ Un punto de partida, no un paquete cerrado:",
            "• cambia la duración de la estancia",
            "• elige tu aeropuerto de salida",
            "• elige los hoteles y el orden de los destinos",
        ],
        "customisable_plain": (
            "Diseñamos cada viaje a tu medida: la duración, el aeropuerto de salida, los "
            "hoteles y el orden de los destinos se pueden cambiar. Escríbenos y "
            "prepararemos tu versión."
        ),
        "cta_inspiracja": "Mira el itinerario completo y envía tu consulta 👇",
        "cta_konkret": "Hazlo a tu medida y envía tu consulta 👇",
        "gbp_head": "{title} — {duration}{price}.",
        "gbp_price": ", desde {price} por persona",
        "gbp_trip": "viaje",
        "gbp_route": "Ruta: {route}.",
        "gbp_link": "Itinerario, fechas y presupuesto: {url}",
        "poster_from": "desde {price} p.p.",
        "poster_cta": "Elige tu fecha →",
        "poster_cta_short": "Elegir fecha →",
        "poster_days": "{days} días",
    },
    "fr": {
        "hook_place": "{place} — et quelques endroits que les brochures ne mentionnent jamais.",
        "hook_none": "Un voyage organisé de A à Z — et pourtant entièrement le vôtre.",
        "days": "{days} jours",
        "nights": " / {nights} nuits",
        "any_date": "Départ le jour de votre choix.",
        "next_date": "Prochain départ : {date}. Dates limitées ({count} au calendrier).",
        "per_person": "à partir de {price} par personne",
        "per_person_short": "dès {price}/pers.",
        "flights": "✈️ Vols inclus ({count})",
        "hotels": "🏨 Hôtels : {count}",
        "customisable": [
            "✏️ Un point de départ, pas un forfait figé :",
            "• modifiez la durée du séjour",
            "• choisissez votre aéroport de départ",
            "• choisissez les hôtels et l'ordre des étapes",
        ],
        "customisable_plain": (
            "Nous construisons chaque voyage sur mesure : la durée, l'aéroport de départ, "
            "les hôtels et l'ordre des étapes peuvent changer. Écrivez-nous et nous "
            "préparerons votre version."
        ),
        "cta_inspiracja": "Découvrez l'itinéraire complet et envoyez une demande 👇",
        "cta_konkret": "Personnalisez-le et envoyez une demande 👇",
        "gbp_head": "{title} — {duration}{price}.",
        "gbp_price": ", à partir de {price} par personne",
        "gbp_trip": "voyage",
        "gbp_route": "Itinéraire : {route}.",
        "gbp_link": "Programme, dates et devis : {url}",
        "poster_from": "dès {price}/pers.",
        "poster_cta": "Choisissez votre date →",
        "poster_cta_short": "Choisir la date →",
        "poster_days": "{days} jours",
    },
    "it": {
        "hook_place": "{place} — e qualche altro luogo che le brochure non menzionano mai.",
        "hook_none": "Un viaggio organizzato dall'inizio alla fine — e comunque tutto tuo.",
        "days": "{days} giorni",
        "nights": " / {nights} notti",
        "any_date": "Partenza nel giorno che preferisci.",
        "next_date": "Prossima partenza: {date}. Date limitate ({count} nel calendario).",
        "per_person": "da {price} a persona",
        "per_person_short": "da {price} p.p.",
        "flights": "✈️ Voli inclusi ({count})",
        "hotels": "🏨 Hotel: {count}",
        "customisable": [
            "✏️ Un punto di partenza, non un pacchetto fisso:",
            "• cambia la durata del soggiorno",
            "• scegli il tuo aeroporto di partenza",
            "• scegli gli hotel e l'ordine delle tappe",
        ],
        "customisable_plain": (
            "Costruiamo ogni viaggio su misura per te: durata, aeroporto di partenza, "
            "hotel e ordine delle tappe si possono cambiare. Scrivici e prepareremo "
            "la tua versione."
        ),
        "cta_inspiracja": "Guarda l'itinerario completo e invia una richiesta 👇",
        "cta_konkret": "Personalizzalo e invia una richiesta 👇",
        "gbp_head": "{title} — {duration}{price}.",
        "gbp_price": ", da {price} a persona",
        "gbp_trip": "viaggio",
        "gbp_route": "Itinerario: {route}.",
        "gbp_link": "Programma, date e preventivo: {url}",
        "poster_from": "da {price} p.p.",
        "poster_cta": "Scegli la tua data →",
        "poster_cta_short": "Scegli la data →",
        "poster_days": "{days} giorni",
    },
    "nl": {
        "hook_place": "{place} — en nog een paar plekken die de brochures nooit noemen.",
        "hook_none": "Een reis van begin tot eind gepland — en toch helemaal van jou.",
        "days": "{days} dagen",
        "nights": " / {nights} nachten",
        "any_date": "Vertrek op elke dag die je kiest.",
        "next_date": "Eerstvolgende vertrek: {date}. Beperkte data ({count} in de kalender).",
        "per_person": "vanaf {price} per persoon",
        "per_person_short": "vanaf {price} p.p.",
        "flights": "✈️ Vluchten inbegrepen ({count})",
        "hotels": "🏨 Hotels: {count}",
        "customisable": [
            "✏️ Een startpunt, geen vast pakket:",
            "• pas de duur van je verblijf aan",
            "• kies je vertrekluchthaven",
            "• kies de hotels en de volgorde van de bestemmingen",
        ],
        "customisable_plain": (
            "We stellen elke reis op maat samen: de duur, de vertrekluchthaven, de "
            "hotels en de volgorde van de bestemmingen kunnen allemaal worden aangepast. "
            "Schrijf ons en we stellen jouw versie samen."
        ),
        "cta_inspiracja": "Bekijk de volledige reisroute en stuur een aanvraag 👇",
        "cta_konkret": "Maak het van jou en stuur een aanvraag 👇",
        "gbp_head": "{title} — {duration}{price}.",
        "gbp_price": ", vanaf {price} per persoon",
        "gbp_trip": "reis",
        "gbp_route": "Route: {route}.",
        "gbp_link": "Programma, data en offerte: {url}",
        "poster_from": "vanaf {price} p.p.",
        "poster_cta": "Kies je datum →",
        "poster_cta_short": "Kies datum →",
        "poster_days": "{days} dagen",
    },
}


def _t(brand: Brand, key: str) -> Any:
    return _COPY[brand.lang][key]


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _hook(pack: Package, brand: Brand) -> str:
    themes = " ".join(_fold(t) for t in pack.themes)

    for needle, line in _HOOKS.get(brand.lang, {}).items():
        if _fold(needle) in themes:
            return line

    first = pack.destinations[0]["name"] if pack.destinations else ""

    return (
        _t(brand, "hook_place").format(place=first) if first else _t(brand, "hook_none")
    )


def _format_amount(amount: float, currency: str) -> str:
    """Format a number in a currency the way that currency is usually written."""
    n = round(amount)
    cur = (currency or "").upper()
    if cur == "EUR":
        # Continental style the agencies asked for: dot thousands, € attached.
        return f"{n:,}".replace(",", ".") + "€"
    if cur == "USD":
        return "$" + f"{n:,}"
    if cur == "GBP":
        return "£" + f"{n:,}"
    if cur == "PLN":
        return f"{n:,}".replace(",", " ") + " zł"
    # Everything else: amount, a space, the ISO code (e.g. 2 940 CHF).
    return f"{n:,}".replace(",", " ") + f" {cur}"


def format_price(pack: Package, brand: Brand, pln_rate: Optional[float] = None) -> str:
    """
    What the post quotes, in the agent's chosen currency.

    The package price comes from Travel Compositor in its own currency. If the
    agent has picked a different currency, we convert with a live daily rate
    (fx.convert) and show that. A rate that is wrong is worse than no price at
    all, so if conversion isn't available we fall back to the original currency
    untouched rather than guessing. `pln_rate`, if given, still overrides for the
    EUR→PLN case (legacy callers); otherwise the live rate is used.
    """
    if not pack.price:
        return ""

    amount = pack.price
    src = (pack.currency or "EUR").upper()
    target = (brand.currency or src).upper()

    if target == src:
        return _format_amount(amount, src)

    # Legacy explicit override for EUR→PLN.
    if pln_rate and src == "EUR" and target == "PLN":
        return _format_amount(amount * pln_rate, "PLN")

    converted = fx.convert(amount, src, target)
    if converted is not None:
        return _format_amount(converted, target)

    # No reliable rate — show the real package price, never a guess.
    return _format_amount(amount, src)


def route(pack: Package, limit: int = 5) -> str:
    seen, stops = set(), []
    for stop in pack.destinations:
        if stop["name"] not in seen:
            seen.add(stop["name"])
            stops.append(stop["name"])

    if len(stops) > limit:
        stops = stops[:limit] + ["…"]

    return " → ".join(stops)


def duration_line(pack: Package, brand: Brand) -> str:
    if not pack.days:
        return ""

    text = _t(brand, "days").format(days=pack.days)

    return text + (_t(brand, "nights").format(nights=pack.nights) if pack.nights else "")


def departures_line(pack: Package, brand: Brand) -> str:
    """The most useful fact a travel post can carry, and the one nobody includes."""
    if not pack.departures:
        return _t(brand, "any_date")

    first = datetime.strptime(pack.departures[0], "%Y-%m-%d")
    month = _MONTHS.get(brand.lang, _MONTHS["en"])[first.month - 1]
    # English writes "Month day, year"; every other language here is day-first.
    date = f"{month} {first.day}, {first.year}" if brand.lang == "en" else f"{first.day} {month} {first.year}"

    return _t(brand, "next_date").format(date=date, count=len(pack.departures))


def hashtags(pack: Package, brand: Brand) -> List[str]:
    """
    Destination, theme, then the brand's steady set.

    Instagram and TikTok both search caption text, so these are keywords as
    much as decoration — which is why the country and the theme come first and
    why there are a dozen rather than thirty. A wall of tags reads as spam to
    a person and does nothing for the algorithm.
    """

    def tag(text: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9 ]", "", _fold(text)).title().replace(" ", "")
        return f"#{clean}" if clean else ""

    tags: List[str] = []

    for stop in pack.destinations:
        if stop.get("country"):
            candidate = tag(stop["country"])
            if candidate and candidate not in tags:
                tags.append(candidate)

    for theme in pack.themes[:3]:
        candidate = tag(theme)
        if candidate and candidate not in tags:
            tags.append(candidate)

    for fixed in brand.tags:
        if fixed not in tags:
            tags.append(fixed)

    return tags


def _lead(text: str, chars: int) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()

    if len(text) <= chars:
        return text

    cut = text[:chars]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))

    return cut[: end + 1].strip() if end > 60 else cut.strip() + "…"


def captions(pack: Package, url: str, brand: Brand = None, pln_rate: Optional[float] = None) -> Dict[str, str]:
    """
    Three captions, because they do different jobs.

    "inspiracja" is for the feed, where a post competes with people's own
    holiday photographs and has to earn the read. "konkret" leads with the
    number, for the audience already shopping. "gbp" is a Google Business
    Profile post, which is a short local advert and should not be written like
    social media at all: no hashtags, no emoji wall, hard 1500 characters,
    facts in the first line because that is all that shows before "read more".

    Every one ends with the same two things: the link, and the promise that
    the itinerary can be changed. That combination is what turns a scroll into
    an enquiry — a reader who believes the package is fixed either buys it or
    leaves, and mostly leaves.
    """
    brand = brand or DEFAULT_BRAND

    price = format_price(pack, brand, pln_rate)
    duration = duration_line(pack, brand)
    stops = route(pack)
    dates = departures_line(pack, brand)
    custom = list(_t(brand, "customisable"))

    # --- Google Business Profile ---
    gbp = [
        _t(brand, "gbp_head").format(
            title=pack.title,
            duration=duration or _t(brand, "gbp_trip"),
            price=_t(brand, "gbp_price").format(price=price) if price else "",
        )
    ]
    if stops:
        gbp.append(_t(brand, "gbp_route").format(route=stops))
    lead = _lead(pack.description, 320)
    if lead:
        gbp.append(lead)
    gbp += [dates, _t(brand, "customisable_plain"), _t(brand, "gbp_link").format(url=url)]

    # --- the offer ---
    head = " · ".join(
        p for p in (pack.title, duration, _t(brand, "per_person_short").format(price=price) if price else "") if p
    )
    konkret = [head, ""]
    if stops:
        konkret.append(f"📍 {stops}")
    if duration:
        konkret.append(f"🗓 {duration}")
    if pack.flights:
        konkret.append(_t(brand, "flights").format(count=pack.flights))
    if pack.hotels:
        konkret.append(_t(brand, "hotels").format(count=pack.hotels))
    konkret += ["", dates, ""] + custom + ["", _t(brand, "cta_konkret"), url, "", " ".join(hashtags(pack, brand))]

    # --- inspiration ---
    inspiracja = [_hook(pack, brand), ""]
    lead = _lead(pack.description, 300)
    if lead:
        inspiracja += [lead, ""]
    if stops:
        inspiracja.append(f"📍 {stops}")
    if duration:
        inspiracja.append(f"🗓 {duration}")
    if price:
        inspiracja.append("💰 " + _t(brand, "per_person").format(price=price))
    inspiracja += ["", dates, ""] + custom + ["", _t(brand, "cta_inspiracja"), url, "", " ".join(hashtags(pack, brand))]

    def cap(lines: List[str], limit: int) -> str:
        text = "\n".join(lines)
        return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"

    return {
        "inspiracja": cap(inspiracja, 2200),
        "konkret": cap(konkret, 2200),
        "gbp": cap(gbp, 1500).replace("\n", "\n\n"),
    }


# --------------------------------------------------------------------------
# The picture
# --------------------------------------------------------------------------

FORMATS: Dict[str, Tuple[int, int, str]] = {
    "square": (1080, 1080, "Instagram / Facebook feed"),
    "story": (1080, 1920, "Story / Reel / TikTok"),
    "gbp": (1200, 900, "Google Business Profile"),
}

STYLES = {"photo": "Template 1 — photo-first", "band": "Template 2 — brand band", "collage": "Template 3 — collage with nights"}

BRAND = (23, 163, 152)
BRAND_DARK = (18, 138, 129)
MINT = (127, 227, 216)
INK = (17, 24, 39)

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# Drop poppins-bold.ttf / poppins-regular.ttf in fonts/ and the brand face
# takes over. The bundled Carlito subset is OFL, carries every Polish
# diacritic and costs 110 KB.
_FONT_FILES = {
    "bold": ("poppins-bold.ttf", "mw-bold.ttf"),
    "regular": ("poppins-regular.ttf", "mw-regular.ttf"),
}


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    preferred, fallback = _FONT_FILES[weight]
    path = os.path.join(_FONT_DIR, preferred)
    if not os.path.exists(path):
        path = os.path.join(_FONT_DIR, fallback)
    return ImageFont.truetype(path, size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> List[str]:
    """Measured in the real font at the real size — a headline that overruns
    its box is the one mistake that makes a generated post look generated."""
    words, lines, line = text.split(), [], ""

    for index, word in enumerate(words):
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not line:
            line = candidate
            continue

        lines.append(line)
        line = word

        if len(lines) >= max_lines:
            line = ""
            remaining = words[index:]
            break
    else:
        remaining = []

    if line and len(lines) < max_lines:
        lines.append(line)
        remaining = []

    if remaining and lines:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"

    return lines


def _scrim(canvas: Image.Image, start: float, peak: float = 0.90) -> None:
    """A soft dark gradient so white type stays readable over any photograph.
    Cubed, so it stays nearly invisible high up and darkens only near the type."""
    width, height = canvas.size
    top = int(height * start)
    mask = Image.new("L", (1, height - top))

    for y in range(height - top):
        t = y / max(1, height - top)
        mask.putpixel((0, y), int(255 * peak * (t ** 3)))

    overlay = Image.new("RGB", (width, height - top), (8, 20, 26))
    canvas.paste(overlay, (0, top), mask.resize((width, height - top)))


def _place(photo: Image.Image, width: int, height: int, focus: str = "center", zoom: float = 1.0,
           max_upscale: float = 1.45) -> Image.Image:
    """
    Fit the photograph to the frame, honestly.

    Travel Compositor's photographs are about 900 × 720 — measured, and there
    is no larger original behind them. A 1080 × 1920 story therefore cannot be
    filled without enlarging two and a half times and cutting away two thirds
    of the width, which is how a cruise ship becomes three cabin windows. So
    the frame is filled when the picture can stand it, and when it cannot the
    picture is shown whole over a blurred, darkened copy of itself — the
    treatment Instagram itself uses for this exact problem.
    """
    photo = photo.convert("RGB")
    source_w, source_h = photo.size
    zoom = max(1.0, min(3.0, zoom))
    cover = max(width / source_w, height / source_h) * zoom

    if cover <= max_upscale:
        crop_w = min(source_w, int(round(width / cover)))
        crop_h = min(source_h, int(round(height / cover)))
        x = (source_w - crop_w) // 2
        y = 0 if focus == "top" else (source_h - crop_h if focus == "bottom" else (source_h - crop_h) // 2)

        return photo.crop((x, max(0, y), x + crop_w, max(0, y) + crop_h)).resize((width, height), Image.LANCZOS)

    backdrop = photo.resize((60, max(1, int(60 * source_h / source_w))), Image.LANCZOS).filter(ImageFilter.GaussianBlur(6))
    scale = max(width / backdrop.width, height / backdrop.height)
    backdrop = backdrop.resize((int(backdrop.width * scale), int(backdrop.height * scale)), Image.LANCZOS)

    canvas = Image.new("RGB", (width, height))
    canvas.paste(backdrop, ((width - backdrop.width) // 2, (height - backdrop.height) // 2))
    canvas.paste(Image.blend(canvas, Image.new("RGB", (width, height), (8, 20, 26)), 0.55), (0, 0))

    inner_w = int(width * min(1.0, zoom))
    inner = photo.resize((inner_w, int(inner_w * source_h / source_w)), Image.LANCZOS)
    top = int(height * (0.06 if focus == "top" else 0.34 if focus == "bottom" else 0.20))
    canvas.paste(inner, ((width - inner_w) // 2, top))

    return canvas


def _pill(draw: ImageDraw.ImageDraw, xy: Tuple[int, int], text: str, font: ImageFont.FreeTypeFont,
          bg: Tuple[int, int, int], fg: Tuple[int, int, int], pad_x: int) -> Tuple[int, int]:
    x, y = xy
    text_w = int(draw.textlength(text, font=font))
    w, h = text_w + pad_x * 2, int(font.size * 2.4)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg)
    draw.text((x + pad_x, y + h / 2), text, font=font, fill=fg, anchor="lm")
    return w, h


def _render_collage(pack: Package, fmt: str, photo: Image.Image, brand: "Brand",
                    pln_rate: Optional[float]) -> Image.Image:
    """
    Style C — premium editorial collage.
    Layout (square):
      • Full-bleed hero photo top 65%
      • Inset accent photo (top-right corner, ~30% wide) with teal border
      • Nights circle badge floats on the hero/panel boundary
      • Dark ink bottom panel: destination chips row + large title + price/CTA row
      • Wordmark pill top-left
    Story format stacks the same elements differently (hero 55%, taller panel).
    """
    width, height, _ = FORMATS[fmt]
    unit = width / 1080
    pad = int(56 * unit)

    INK_DARK = (10, 18, 30)
    TEAL_LIGHT = (200, 242, 240)
    WHITE = (255, 255, 255)
    GOLD = (255, 196, 60)  # brighter amber for visibility

    is_story = height > width

    # ── Layout geometry ──────────────────────────────────────────────────────
    hero_ratio = 0.52 if is_story else 0.62
    hero_h = int(height * hero_ratio)
    panel_h = height - hero_h

    # ── Paint hero ───────────────────────────────────────────────────────────
    hero_img = _place(photo, width, hero_h, focus="center")
    canvas = Image.new("RGB", (width, height), INK_DARK)
    canvas.paste(hero_img, (0, 0))

    # gradient scrim over bottom third of hero so text on panel boundary reads
    _hero_area = canvas.crop((0, 0, width, hero_h))
    _scrim(_hero_area, 0.55, peak=0.75)
    canvas.paste(_hero_area, (0, 0))

    # ── Dark bottom info panel ───────────────────────────────────────────────
    panel_y = hero_h
    panel = Image.new("RGB", (width, panel_h), INK_DARK)
    canvas.paste(panel, (0, panel_y))

    # Teal accent line at top of panel
    draw = ImageDraw.Draw(canvas)
    accent_h = int(5 * unit)
    draw.rectangle([0, panel_y, width, panel_y + accent_h], fill=BRAND)

    # ── Nights badge — straddles hero/panel border ───────────────────────────
    nights = pack.nights or (pack.days - 1 if pack.days and pack.days > 1 else pack.days or 0)
    badge_r = int(50 * unit)
    bx = int(pad + badge_r)
    by = panel_y  # centre on the boundary
    if nights:
        badge_img = Image.new("RGBA", (badge_r * 2, badge_r * 2), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(badge_img)
        bdraw.ellipse([0, 0, badge_r * 2, badge_r * 2], fill=(*BRAND, 255))
        canvas.paste(badge_img.convert("RGB"), (bx - badge_r, by - badge_r), badge_img.split()[3])
        # White ring
        draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r], outline=WHITE, width=int(2 * unit))
        draw.text((bx, by - int(8 * unit)), str(nights),
                  font=_font("bold", int(30 * unit)), fill=WHITE, anchor="mm")
        draw.text((bx, by + int(20 * unit)), "nights",
                  font=_font("regular", int(16 * unit)), fill=TEAL_LIGHT, anchor="mm")

    # ── Panel content: destinations row ─────────────────────────────────────
    dests = [d.get("name", "") for d in (pack.destinations or []) if d.get("name")]
    y = panel_y + accent_h + int(22 * unit)
    dest_font = _font("regular", int(22 * unit))
    sep_x = pad + (badge_r * 2 + int(20 * unit) if nights else 0)
    dest_text = "  ·  ".join(dests[:4]) if dests else ""
    if dest_text:
        draw.text((sep_x, y), dest_text.upper(), font=dest_font, fill=(*BRAND[:3], 255) if False else BRAND, anchor="lt")
        y += int(dest_font.size * 1.6)
    else:
        y += int(28 * unit)

    # ── Title ────────────────────────────────────────────────────────────────
    title_font_size = int(64 * unit) if not is_story else int(72 * unit)
    title_font = _font("bold", title_font_size)
    title_max_w = width - pad * 2
    title_lines = _wrap(draw, pack.title, title_font, title_max_w, 3)
    for line in title_lines:
        # Dark drop-shadow offset for extra punch
        draw.text((pad + int(2 * unit), y + int(2 * unit)), line, font=title_font, fill=(0, 0, 0))
        draw.text((pad, y), line, font=title_font, fill=WHITE)
        y += int(title_font.size * 1.18)

    # ── Days pill + themes ────────────────────────────────────────────────────
    y += int(8 * unit)
    meta_parts = []
    if pack.days:
        meta_parts.append(f"{pack.days} days")
    if pack.themes:
        meta_parts.extend(pack.themes[:2])
    if meta_parts:
        meta_text = "  ·  ".join(meta_parts)
        meta_font = _font("regular", int(24 * unit))
        draw.text((pad, y), meta_text, font=meta_font, fill=(160, 185, 195))
        y += int(meta_font.size * 1.8)

    # ── Price + CTA row at bottom of panel ───────────────────────────────────
    foot = height - int(40 * unit)
    price = format_price(pack, brand, pln_rate)
    cta = _t(brand, "poster_cta_short")
    cta_font = _font("bold", int(26 * unit))
    cta_w = int(draw.textlength(cta, font=cta_font)) + int(56 * unit)

    if price:
        price_line = _t(brand, "poster_from").format(price=price)
        price_font = _font("bold", int(50 * unit))
        # Shadow then text
        draw.text((pad + int(2 * unit), foot + int(2 * unit)), price_line, font=price_font, fill=(0, 0, 0), anchor="ls")
        draw.text((pad, foot), price_line, font=price_font, fill=GOLD, anchor="ls")

    _pill(draw, (width - pad - cta_w, foot - int(cta_font.size * 2.2)),
          cta, cta_font, BRAND, WHITE, int(28 * unit))

    # ── Wordmark pill — top-left hero ────────────────────────────────────────
    _pill(draw, (pad, pad), brand.wordmark,
          _font("bold", int(22 * unit)), INK_DARK, WHITE, int(24 * unit))

    return canvas


def render_video_overlay(pack: Package, fmt: str, brand: "Brand",
                         pln_rate: Optional[float] = None) -> Image.Image:
    """
    A transparent-topped branded overlay (RGBA) for burning onto a video clip.

    This is the collage design with the hero photograph removed: the top is
    fully transparent so the moving clip shows through, a soft gradient fades
    into a solid dark info panel at the bottom, and the panel carries the same
    destinations row, title, meta, price, CTA and wordmark pill as the still
    collage. FFmpeg then only has to scale the clip and composite this PNG on
    top — the brand design lives here in Pillow, where the fonts, Polish
    diacritics and wrapping already work, not in FFmpeg's drawtext.
    """
    width, height, _ = FORMATS[fmt]
    unit = width / 1080
    pad = int(56 * unit)

    INK_DARK = (10, 18, 30)
    TEAL_LIGHT = (200, 242, 240)
    WHITE = (255, 255, 255)
    GOLD = (255, 196, 60)

    is_story = height > width

    hero_ratio = 0.52 if is_story else 0.62
    hero_h = int(height * hero_ratio)
    panel_h = height - hero_h
    panel_y = hero_h

    # Fully transparent canvas — the video plays through the hero region.
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    # Soft gradient band above the panel so the clip fades into the dark panel
    # rather than meeting a hard edge (last ~16% of the hero).
    band_h = int(hero_h * 0.16)
    if band_h > 0:
        band = Image.new("RGBA", (width, band_h), (*INK_DARK, 0))
        bmask = Image.new("L", (1, band_h))
        for yy in range(band_h):
            t = yy / max(1, band_h - 1)
            bmask.putpixel((0, yy), int(255 * (t ** 2)))
        band.putalpha(bmask.resize((width, band_h)))
        canvas.alpha_composite(band, (0, panel_y - band_h))

    # Solid dark info panel (opaque).
    panel = Image.new("RGBA", (width, panel_h), (*INK_DARK, 255))
    canvas.alpha_composite(panel, (0, panel_y))

    draw = ImageDraw.Draw(canvas)

    # Teal accent line at top of panel.
    accent_h = int(5 * unit)
    draw.rectangle([0, panel_y, width, panel_y + accent_h], fill=(*BRAND, 255))

    # Nights badge — straddles the hero/panel boundary.
    nights = pack.nights or (pack.days - 1 if pack.days and pack.days > 1 else pack.days or 0)
    badge_r = int(50 * unit)
    bx = int(pad + badge_r)
    by = panel_y
    if nights:
        draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r], fill=(*BRAND, 255))
        draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r], outline=(*WHITE, 255), width=int(2 * unit))
        draw.text((bx, by - int(8 * unit)), str(nights),
                  font=_font("bold", int(30 * unit)), fill=WHITE, anchor="mm")
        draw.text((bx, by + int(20 * unit)), "nights",
                  font=_font("regular", int(16 * unit)), fill=TEAL_LIGHT, anchor="mm")

    # Destinations row.
    dests = [d.get("name", "") for d in (pack.destinations or []) if d.get("name")]
    y = panel_y + accent_h + int(22 * unit)
    dest_font = _font("regular", int(22 * unit))
    sep_x = pad + (badge_r * 2 + int(20 * unit) if nights else 0)
    dest_text = "  ·  ".join(dests[:4]) if dests else ""
    if dest_text:
        draw.text((sep_x, y), dest_text.upper(), font=dest_font, fill=BRAND, anchor="lt")
        y += int(dest_font.size * 1.6)
    else:
        y += int(28 * unit)

    # Title.
    title_font_size = int(64 * unit) if not is_story else int(72 * unit)
    title_font = _font("bold", title_font_size)
    for line in _wrap(draw, pack.title, title_font, width - pad * 2, 3):
        draw.text((pad + int(2 * unit), y + int(2 * unit)), line, font=title_font, fill=(0, 0, 0))
        draw.text((pad, y), line, font=title_font, fill=WHITE)
        y += int(title_font.size * 1.18)

    # Days + themes.
    y += int(8 * unit)
    meta_parts = []
    if pack.days:
        meta_parts.append(f"{pack.days} days")
    if pack.themes:
        meta_parts.extend(pack.themes[:2])
    if meta_parts:
        meta_font = _font("regular", int(24 * unit))
        draw.text((pad, y), "  ·  ".join(meta_parts), font=meta_font, fill=(160, 185, 195))

    # Price + CTA row.
    foot = height - int(40 * unit)
    price = format_price(pack, brand, pln_rate)
    cta = _t(brand, "poster_cta_short")
    cta_font = _font("bold", int(26 * unit))
    cta_w = int(draw.textlength(cta, font=cta_font)) + int(56 * unit)
    if price:
        price_line = _t(brand, "poster_from").format(price=price)
        price_font = _font("bold", int(50 * unit))
        draw.text((pad + int(2 * unit), foot + int(2 * unit)), price_line, font=price_font, fill=(0, 0, 0), anchor="ls")
        draw.text((pad, foot), price_line, font=price_font, fill=GOLD, anchor="ls")
    _pill(draw, (width - pad - cta_w, foot - int(cta_font.size * 2.2)),
          cta, cta_font, BRAND, WHITE, int(28 * unit))

    # Wordmark pill — top-left.
    _pill(draw, (pad, pad), brand.wordmark,
          _font("bold", int(22 * unit)), INK_DARK, WHITE, int(24 * unit))

    return canvas


def overlay_to_png_bytes(image: Image.Image) -> bytes:
    """Serialise an RGBA overlay to PNG bytes for FFmpeg."""
    buf = io.BytesIO()
    image.convert("RGBA").save(buf, format="PNG")
    return buf.getvalue()


def render(pack: Package, fmt: str = "square", style: str = "photo", photo: Optional[Image.Image] = None,
           focus: str = "center", zoom: float = 1.0, brand: "Brand" = None,
           pln_rate: Optional[float] = None) -> Image.Image:
    """One finished post, at the exact size the network wants, in the brand's
    own language, currency and wordmark."""
    brand = brand or DEFAULT_BRAND

    if fmt not in FORMATS:
        raise ValueError(f"Unknown format {fmt!r}")

    width, height, _ = FORMATS[fmt]

    if photo is None:
        raise ValueError("A photograph is required.")

    # Style C — collage with nights badge
    if style == "collage":
        return _render_collage(pack, fmt, photo, brand, pln_rate)

    unit = width / 1080
    pad = int(72 * unit)
    band = int(height * (0.34 if height > width else 0.40))

    if style == "band":
        canvas = Image.new("RGB", (width, height), (255, 255, 255))
        canvas.paste(_place(photo, width, height - band, focus, zoom), (0, 0))
    else:
        canvas = _place(photo, width, height, focus, zoom)
        _scrim(canvas, 0.30)

    draw = ImageDraw.Draw(canvas)

    price = format_price(pack, brand, pln_rate)
    price_line = _t(brand, "poster_from").format(price=price) if price else ""
    days = _t(brand, "poster_days").format(days=pack.days) if pack.days else ""
    meta = "  ·  ".join(p for p in (days, route(pack, 3)) if p)
    kicker = next((s["country"] for s in pack.destinations if s.get("country")), pack.themes[0] if pack.themes else "")

    # Stories keep a deeper margin: Instagram and TikTok paint their own reply
    # bar and username over the bottom of the frame.
    safe = int(200 * unit) if height / width > 1.5 else 0

    if style == "band":
        top = height - band
        draw.rectangle([0, top, width, top + int(8 * unit)], fill=BRAND)

        y = top + int(62 * unit)
        if kicker:
            draw.text((pad, y), kicker.upper(), font=_font("bold", int(24 * unit)), fill=BRAND_DARK)
            y += int(48 * unit)

        title_font = _font("bold", int(48 * unit))
        for line in _wrap(draw, pack.title, title_font, width - pad * 2, 2):
            draw.text((pad, y), line, font=title_font, fill=INK)
            y += int(title_font.size * 1.24)

        if meta:
            small = _font("regular", int(26 * unit))
            draw.text((pad, y + int(8 * unit)), _wrap(draw, meta, small, width - pad * 2, 1)[0], font=small, fill=(91, 100, 112))

        foot = height - pad - safe
        if price_line:
            draw.text((pad, foot), price_line, font=_font("bold", int(42 * unit)), fill=INK, anchor="ls")

        cta_font = _font("bold", int(26 * unit))
        cta = _t(brand, "poster_cta_short")
        cta_w = int(draw.textlength(cta, font=cta_font)) + int(56 * unit)
        _pill(draw, (width - pad - cta_w, foot - int(cta_font.size * 1.9)), cta, cta_font, BRAND, (255, 255, 255), int(28 * unit))

        return canvas

    # --- template 1: photo-first, laid out from the bottom up so a long title
    # can never push the price off the image.
    small = _font("regular", int(26 * unit))
    y = height - pad - safe - int(18 * unit)

    draw.text((pad, y), brand.site, font=small, fill=(255, 255, 255), anchor="ls")
    cta_font = _font("bold", int(26 * unit))
    draw.text((width - pad, y), _t(brand, "poster_cta"), font=cta_font, fill=MINT, anchor="rs")

    y -= int(58 * unit)
    if price_line:
        draw.text((pad, y), price_line, font=_font("bold", int(44 * unit)), fill=(255, 255, 255), anchor="ls")
        y -= int(62 * unit)

    if meta:
        draw.text((pad, y), _wrap(draw, meta, small, width - pad * 2, 1)[0], font=small, fill=(226, 232, 236), anchor="ls")
        y -= int(56 * unit)

    title_font = _font("bold", int((54 if height > width else 52) * unit))
    for line in reversed(_wrap(draw, pack.title, title_font, width - pad * 2, 3)):
        draw.text((pad, y), line, font=title_font, fill=(255, 255, 255), anchor="ls")
        y -= int(title_font.size * 1.26)

    if kicker:
        draw.text((pad, y - int(10 * unit)), kicker.upper(), font=_font("bold", int(26 * unit)), fill=MINT, anchor="ls")

    _pill(draw, (pad, pad), brand.wordmark, _font("bold", int(22 * unit)), BRAND, (255, 255, 255), int(24 * unit))

    return canvas


def load_photo(url: str) -> Image.Image:
    """Travel Compositor's storage, fetched once."""
    response = requests.get(url, timeout=_TIMEOUT)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content))


def to_jpeg(image: Image.Image, quality: int = 88) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()
