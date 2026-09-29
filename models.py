"""
Database models.

SQLite for MVP. Swap DATABASE_URL to postgresql+asyncpg://... for production
— SQLAlchemy async works identically; only the driver changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Agent(Base):
    """One row per travel agency that has signed up."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Agency identity — used to build the Brand passed to social_kit.render()
    agency_name: Mapped[str | None] = mapped_column(String(120))     # e.g. "Sunshine Travels"
    agency_url: Mapped[str | None] = mapped_column(String(2048))     # link in captions
    agency_site: Mapped[str | None] = mapped_column(String(253))     # domain shown on poster

    # Logo — stored as a base64 data URL in the DB (no external storage needed).
    # logo_r2_key kept as a nullable column so old rows don't break; unused now.
    logo_r2_key: Mapped[str | None] = mapped_column(String(512))     # legacy R2 key (unused)
    logo_url: Mapped[str | None] = mapped_column(Text)               # data: URL or public URL

    # Ribbon (drawn over the top-right corner of every poster)
    ribbon_text: Mapped[str | None] = mapped_column(String(40))      # free text: "Summer Sale 2026"
    ribbon_preset: Mapped[str | None] = mapped_column(String(20))    # NEW | SALE | BESTSELLER | HOT

    # Caption / poster language and currency
    # tc_lang: what TC is asked for ("EN" / "PL" / "DE" / "ES" etc.)
    # caption_lang: the language of the generated copy ("en" / "pl" / "de" / "es")
    # currency: what the poster quotes ("EUR" / "PLN" / "USD" / "GBP")
    tc_lang: Mapped[str | None] = mapped_column(String(5))            # default "EN"
    caption_lang: Mapped[str | None] = mapped_column(String(5))       # default "en"
    currency: Mapped[str | None] = mapped_column(String(5))           # default "EUR"

    # Account state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def ribbon_label(self) -> str | None:
        """The text that actually appears on the poster (preset wins over free text)."""
        return self.ribbon_preset or self.ribbon_text or None
