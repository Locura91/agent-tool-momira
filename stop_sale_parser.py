"""
Stop-sale document parser.

Reads PDF and Excel/CSV files and extracts stop-sale date ranges, room types,
and markets using pattern matching.  No external AI service is required —
stop-sale documents follow fairly regular patterns (date ranges, room codes,
market codes) that regex handles well.

Supported formats
-----------------
* PDF  — via pdfplumber (text extraction, handles most travel-industry PDFs)
* XLSX / XLS / ODS / CSV — via openpyxl / built-in csv

Returns a list of StopSaleEntry dicts:
    {
        "room_type": str | None,
        "market": str | None,
        "date_from": date | None,
        "date_to": date | None,
        "booking_from": date | None,
        "booking_to": date | None,
        "raw_text": str,
    }

The caller is responsible for storing these alongside the hotel/tour name.
"""

from __future__ import annotations

import base64
import csv
import io
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Optional imports — we catch ImportError so the module loads even if a
# library is not yet installed on the server.
# ---------------------------------------------------------------------------
try:
    import pdfplumber
    _HAS_PDF = True
except ImportError:
    _HAS_PDF = False

try:
    import openpyxl
    _HAS_XLSX = True
except ImportError:
    _HAS_XLSX = False


# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
StopSaleEntry = Dict[str, Any]


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

# Patterns we expect in travel-industry stop-sale documents.
# Order matters — more specific patterns first.
_DATE_PATTERNS = [
    # DD.MM.YYYY / DD/MM/YYYY / DD-MM-YYYY
    (re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b"), "dmy"),
    # YYYY-MM-DD (ISO)
    (re.compile(r"\b(\d{4})[.\-/](\d{2})[.\-/](\d{2})\b"), "ymd"),
    # DD MMM YYYY  e.g. "01 Jan 2025"
    (re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b"), "dmonthy"),
    # MMM DD, YYYY  e.g. "Jan 01, 2025"
    (re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b"), "mondyy"),
    # DD.MM.YY  e.g. "01.12.25"
    (re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2})\b"), "dmy2"),
]

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    # German
    "jan": 1, "feb": 2, "mär": 3, "mrz": 3, "apr": 4, "mai": 5,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
    # Spanish/Polish
    "ene": 1, "sty": 1, "lut": 2, "maz": 3, "kwi": 4, "maj": 5,
    "cze": 6, "lip": 7, "sie": 8, "wrz": 9, "paź": 10, "paz": 10,
    "lis": 11, "gru": 12,
}


def _parse_date(text: str) -> Optional[date]:
    """Try each pattern and return the first date found in `text`."""
    text = text.strip()
    for pat, fmt in _DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        try:
            if fmt == "dmy":
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return date(y, mo, d)
            elif fmt == "ymd":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return date(y, mo, d)
            elif fmt == "dmonthy":
                d = int(m.group(1))
                mo = _MONTH_MAP.get(m.group(2).lower()[:3])
                y = int(m.group(3))
                if mo:
                    return date(y, mo, d)
            elif fmt == "mondyy":
                mo = _MONTH_MAP.get(m.group(1).lower()[:3])
                d = int(m.group(2))
                y = int(m.group(3))
                if mo:
                    return date(y, mo, d)
            elif fmt == "dmy2":
                d, mo, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
                y = 2000 + y2 if y2 < 100 else y2
                return date(y, mo, d)
        except (ValueError, TypeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Stop-sale block detection
# ---------------------------------------------------------------------------

# Keywords that signal a stop-sale section header
_SS_HEADER = re.compile(
    r"\b(stop[\s\-]?sale|stop[\s\-]?sell|closed[\s\-]?sale|stopp|no[\s\-]?venta|"
    r"gesperrt|gesperrer[\s\-]?zeitraum|bloqueo|blocage|chiusura)\b",
    re.IGNORECASE,
)

# A range separator between two dates
_RANGE_SEP = re.compile(r"\s*(?:[-–—]|to|bis|a|au|al|do)\s*", re.IGNORECASE)

# Room type patterns (very common codes in hotel stop sales)
_ROOM_PAT = re.compile(
    r"\b(ALL(?:[\s\-]ROOMS?)?|SGL|DBL|TWN|TRP|SUI?TE?|STD|SUP(?:ERIOR)?|"
    r"JR\.?\s*SUI?TE?|FAM(?:ILY)?|BUNGALOW|VILLA|STUDIO|APT(?:ARTMENT)?|"
    r"ROOM[\s\-]TYPE[\s:]+[\w\s/]+)\b",
    re.IGNORECASE,
)

# Market/country codes (2-letter ISO codes or well-known market labels)
_MARKET_PAT = re.compile(
    r"\b(ALL|DE|PL|ES|FR|IT|GB|UK|NL|BE|AT|CH|CZ|SK|HU|RU|SE|NO|DK|"
    r"GERMAN[Y]?|POLISH?|SPANISH?|FRENCH?|ITALIAN?|BRITISH?|DUTCH)\b",
    re.IGNORECASE,
)

# "booking" window keywords
_BOOKING_KW = re.compile(r"\b(book(?:ing)?[\s\-]?(?:period|window|date|from|by)?|buchung)\b",
                          re.IGNORECASE)

# "travel" / "stay" / "departure" keywords
_TRAVEL_KW = re.compile(r"\b(travel(?:ling)?|stay|arrival|departure|check[\s\-]?in|"
                         r"aufenthalt|reise(?:zeitraum)?|periodo\s+de\s+viaje)\b",
                         re.IGNORECASE)


def _extract_date_pair(line: str) -> tuple[Optional[date], Optional[date]]:
    """
    Find up to two dates in a line and return (from_date, to_date).
    Handles ranges written as "01.01.2025 – 31.03.2025" or "01.01 to 31.03.2025".
    """
    # Find all date-like spans
    found: list[tuple[int, date]] = []
    for pat, fmt in _DATE_PATTERNS:
        for m in pat.finditer(line):
            try:
                if fmt == "dmy":
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    found.append((m.start(), date(y, mo, d)))
                elif fmt == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    found.append((m.start(), date(y, mo, d)))
                elif fmt == "dmonthy":
                    d = int(m.group(1))
                    mo = _MONTH_MAP.get(m.group(2).lower()[:3])
                    y = int(m.group(3))
                    if mo:
                        found.append((m.start(), date(y, mo, d)))
                elif fmt == "mondyy":
                    mo = _MONTH_MAP.get(m.group(1).lower()[:3])
                    d = int(m.group(2))
                    y = int(m.group(3))
                    if mo:
                        found.append((m.start(), date(y, mo, d)))
                elif fmt == "dmy2":
                    d, mo, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    y = 2000 + y2
                    found.append((m.start(), date(y, mo, d)))
            except (ValueError, TypeError):
                continue

    # Deduplicate by position; keep earliest per position
    seen_pos = {}
    for pos, dt in found:
        if pos not in seen_pos:
            seen_pos[pos] = dt
    ordered = sorted(seen_pos.items())

    if not ordered:
        return None, None
    if len(ordered) == 1:
        return ordered[0][1], None
    return ordered[0][1], ordered[-1][1]


def _parse_lines(lines: list[str]) -> list[StopSaleEntry]:
    """
    Parse a flat list of text lines into StopSaleEntry dicts.

    Strategy: we look for lines that:
    1. Contain stop-sale header keywords (start a new stop-sale block), or
    2. Contain a date range (and we inherit context from the most recent block).

    We accumulate room_type, market, date pair and booking date pair per block.
    """
    entries: list[StopSaleEntry] = []
    current: dict = {}
    in_block = False

    def _flush():
        nonlocal current
        if current.get("date_from") or current.get("date_to"):
            entries.append({
                "room_type": current.get("room_type"),
                "market": current.get("market"),
                "date_from": current.get("date_from"),
                "date_to": current.get("date_to"),
                "booking_from": current.get("booking_from"),
                "booking_to": current.get("booking_to"),
                "raw_text": current.get("raw_text", ""),
            })
        current = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        is_header = bool(_SS_HEADER.search(line))
        if is_header:
            _flush()
            in_block = True
            current["raw_text"] = line
            # Room type may be on the same line as the header
            rm = _ROOM_PAT.search(line)
            if rm:
                current["room_type"] = rm.group(0).upper()
            mk = _MARKET_PAT.search(line)
            if mk:
                current["market"] = mk.group(0).upper()
            df, dt = _extract_date_pair(line)
            if df:
                current["date_from"] = df
                current["date_to"] = dt
            continue

        if not in_block:
            # Look for date pairs even outside explicit headers — many stop-sale
            # spreadsheets are just rows of date ranges.
            df, dt = _extract_date_pair(line)
            if df:
                _flush()
                in_block = True
                current["raw_text"] = line
                rm = _ROOM_PAT.search(line)
                if rm:
                    current["room_type"] = rm.group(0).upper()
                mk = _MARKET_PAT.search(line)
                if mk:
                    current["market"] = mk.group(0).upper()
                current["date_from"] = df
                current["date_to"] = dt
            continue

        # Inside a block — enrich with more details
        if "raw_text" in current:
            current["raw_text"] += "\n" + line
        else:
            current["raw_text"] = line

        rm = _ROOM_PAT.search(line)
        if rm and not current.get("room_type"):
            current["room_type"] = rm.group(0).upper()

        mk = _MARKET_PAT.search(line)
        if mk and not current.get("market"):
            current["market"] = mk.group(0).upper()

        df, dt = _extract_date_pair(line)
        if df:
            is_booking = bool(_BOOKING_KW.search(line))
            if is_booking:
                current.setdefault("booking_from", df)
                current.setdefault("booking_to", dt)
            else:
                current.setdefault("date_from", df)
                current.setdefault("date_to", dt)

    _flush()
    return entries


# ---------------------------------------------------------------------------
# Table-aware parsing (for Excel/CSV where each row is one stop-sale)
# ---------------------------------------------------------------------------

def _parse_table(headers: list[str], rows: list[list[str]]) -> list[StopSaleEntry]:
    """
    Parse a table (list of header strings + list of row strings) into entries.

    We detect column roles by keyword matching the headers.
    """
    h = [str(x).lower().strip() for x in headers]

    def _col(*kws):
        for kw in kws:
            for i, hdr in enumerate(h):
                if kw in hdr:
                    return i
        return None

    ci_room = _col("room", "category", "type", "zimmer", "habitacion")
    ci_market = _col("market", "country", "nation", "markt", "mercado")
    ci_df = _col("from", "start", "von", "desde", "date_from", "travel from",
                 "arrival", "check-in", "ab")
    ci_dt = _col("to", "end", "bis", "hasta", "date_to", "travel to",
                 "departure", "check-out", "stop")
    ci_bf = _col("book from", "booking from", "buchung von", "book start")
    ci_bt = _col("book to", "booking to", "buchung bis", "book end")

    entries: list[StopSaleEntry] = []
    for row in rows:
        def _cell(i):
            if i is None or i >= len(row):
                return ""
            return str(row[i]).strip()

        raw = " | ".join(_cell(i) for i in range(len(row)) if _cell(i))
        df_raw, dt_raw = _cell(ci_df), _cell(ci_dt)
        df = _parse_date(df_raw) if df_raw else None
        dt = _parse_date(dt_raw) if dt_raw else None

        if not df:
            # Fall back to line scanning
            df, dt = _extract_date_pair(raw)

        if not df:
            continue  # skip rows with no recognisable date

        entry: StopSaleEntry = {
            "room_type": (_cell(ci_room) or "ALL").upper() or None,
            "market": (_cell(ci_market) or "ALL").upper() or None,
            "date_from": df,
            "date_to": dt,
            "booking_from": _parse_date(_cell(ci_bf)) if ci_bf is not None else None,
            "booking_to": _parse_date(_cell(ci_bt)) if ci_bt is not None else None,
            "raw_text": raw,
        }
        entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Format-specific extractors
# ---------------------------------------------------------------------------

def _extract_text_from_pdf(raw: bytes) -> str:
    if not _HAS_PDF:
        raise RuntimeError("pdfplumber is not installed — cannot parse PDF files.")
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        parts = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
            # Also try to extract tables
            for table in page.extract_tables():
                for row in table:
                    parts.append("\t".join(str(c or "") for c in row))
        return "\n".join(parts)


def _parse_pdf(raw: bytes) -> list[StopSaleEntry]:
    text = _extract_text_from_pdf(raw)
    lines = text.splitlines()
    return _parse_lines(lines)


def _parse_excel(raw: bytes) -> list[StopSaleEntry]:
    if not _HAS_XLSX:
        raise RuntimeError("openpyxl is not installed — cannot parse Excel files.")
    wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    all_entries: list[StopSaleEntry] = []
    for ws in wb.worksheets:
        rows_data = []
        header = None
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            if not any(cells):
                continue
            if header is None:
                # Heuristic: first non-empty row that contains date-like or keyword headers
                if any(_SS_HEADER.search(str(c)) or _BOOKING_KW.search(str(c)) or
                       re.search(r"\b(from|to|date|room|market|von|bis)\b", str(c), re.I)
                       for c in cells):
                    header = cells
                else:
                    # Treat as a data row and try line parsing
                    rows_data.append(cells)
            else:
                rows_data.append(cells)

        if header and rows_data:
            all_entries.extend(_parse_table(header, rows_data))
        else:
            # Fall back to line parsing
            all_lines = []
            for row in rows_data:
                all_lines.append("\t".join(row))
            all_entries.extend(_parse_lines(all_lines))

    return all_entries


def _parse_csv(raw: bytes) -> list[StopSaleEntry]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    # Detect if first row looks like a header
    first = rows[0]
    if any(re.search(r"\b(from|to|date|room|market|von|bis)\b", str(c), re.I) for c in first):
        return _parse_table(first, rows[1:])
    # Treat all rows as data
    lines = [",".join(r) for r in rows]
    return _parse_lines(lines)


def _parse_text(raw: bytes) -> list[StopSaleEntry]:
    text = raw.decode("utf-8-sig", errors="replace")
    return _parse_lines(text.splitlines())


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_document(filename: str, raw_bytes: bytes) -> list[StopSaleEntry]:
    """
    Parse a stop-sale document and return a list of StopSaleEntry dicts.

    Parameters
    ----------
    filename   : original filename (used to detect format by extension)
    raw_bytes  : file content bytes

    Returns
    -------
    list of StopSaleEntry dicts (may be empty if nothing is found).

    Raises
    ------
    RuntimeError  if a required library is missing or the format is unsupported.
    """
    name = filename.lower()
    if name.endswith(".pdf"):
        return _parse_pdf(raw_bytes)
    elif name.endswith((".xlsx", ".xlsm")):
        return _parse_excel(raw_bytes)
    elif name.endswith((".xls",)):
        # openpyxl cannot read old .xls — try as text with csv fallback
        try:
            return _parse_excel(raw_bytes)
        except Exception:
            return _parse_text(raw_bytes)
    elif name.endswith(".csv"):
        return _parse_csv(raw_bytes)
    elif name.endswith((".txt", ".tsv")):
        return _parse_text(raw_bytes)
    else:
        # Try PDF first, then fall back to text
        try:
            return _parse_pdf(raw_bytes)
        except Exception:
            return _parse_text(raw_bytes)
