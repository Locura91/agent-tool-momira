"""Pydantic request / response shapes."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, EmailStr, HttpUrl, field_validator


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    agency_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --------------------------------------------------------------------------
# Agent / branding
# --------------------------------------------------------------------------

RIBBON_PRESETS = ("NEW", "SALE", "BESTSELLER", "HOT", "")


CAPTION_LANGS = {
    "en": "English",
    "pl": "Polish",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "nl": "Dutch",
}

TC_LANGS = {v: k.upper() for k, v in {
    "EN": "en", "PL": "pl", "DE": "de", "ES": "es",
    "FR": "fr", "IT": "it", "NL": "nl",
}.items()}

CURRENCIES = ("EUR", "PLN", "USD", "GBP", "CHF", "SEK", "NOK", "DKK")


class AgentProfile(BaseModel):
    id: str
    email: str
    agency_name: Optional[str]
    agency_url: Optional[str]
    agency_site: Optional[str]
    agency_phone: Optional[str]
    agency_email: Optional[str]
    logo_url: Optional[str]
    ribbon_text: Optional[str]
    ribbon_preset: Optional[str]
    tc_lang: Optional[str]
    caption_lang: Optional[str]
    currency: Optional[str]

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    agency_name: Optional[str] = None
    agency_url: Optional[str] = None
    agency_site: Optional[str] = None
    agency_phone: Optional[str] = None
    agency_email: Optional[str] = None
    ribbon_text: Optional[str] = None
    ribbon_preset: Optional[str] = None
    tc_lang: Optional[str] = None
    caption_lang: Optional[str] = None
    currency: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CURRENCIES:
            raise ValueError(f"currency must be one of {CURRENCIES}")
        return v or None

    @field_validator("ribbon_preset")
    @classmethod
    def valid_preset(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in RIBBON_PRESETS:
            raise ValueError(f"ribbon_preset must be one of {RIBBON_PRESETS}")
        return v or None

    @field_validator("ribbon_text")
    @classmethod
    def text_length(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 40:
            raise ValueError("ribbon_text must be 40 characters or fewer.")
        return v or None


# --------------------------------------------------------------------------
# Package / generate
# --------------------------------------------------------------------------

class DepartureDate(BaseModel):
    date: str   # YYYY-MM-DD


class PackageInfo(BaseModel):
    id: str
    title: str
    days: Optional[int]
    nights: Optional[int]
    price: Optional[float]
    currency: Optional[str]
    destinations: List[dict]
    themes: List[str]
    gallery_count: int
    departures: List[str]
    flights: int
    hotels: int


class GenerateRequest(BaseModel):
    package_id: str
    photo_index: int = 0       # which gallery image (0-based)
    format: str = "square"     # square | story | gbp
    style: str = "photo"       # photo | band
    focus: str = "center"      # top | center | bottom
    zoom: float = 1.0


class Caption(BaseModel):
    inspiracja: str
    konkret: str
    gbp: str


class GenerateResponse(BaseModel):
    package_id: str
    captions: Caption
    # image is returned as a separate binary download endpoint
    image_urls: dict   # {format: {style: "/download/..." url}}
