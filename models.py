"""
Database models.

SQLite for MVP. Swap DATABASE_URL to postgresql+asyncpg://... for production
— SQLAlchemy async works identically; only the driver changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Boolean, Date, Integer, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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

    # Agency contact details (optional — shown on flyers if provided)
    agency_phone: Mapped[str | None] = mapped_column(String(40))
    agency_email: Mapped[str | None] = mapped_column(String(254))

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


class StopSaleDocument(Base):
    """
    A contract/stop-sale document uploaded by a travel agent.

    On first upload the agent manually matches it to a hotel name or
    closed-tour TC package ID.  Once matched, subsequent uploads for the
    same hotel/tour are auto-processed without human confirmation.
    """

    __tablename__ = "stop_sale_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                     default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), nullable=False, index=True)

    # Original filename and raw bytes (stored in DB for simplicity on free tier)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)   # application/pdf etc.
    raw_bytes: Mapped[bytes] = mapped_column(Text, nullable=False)            # base64-encoded

    # Matching: once confirmed, the human-chosen label is stored here so
    # subsequent uploads for the same hotel/tour skip the matching step.
    # match_key is lowercased for comparison; match_label is the display name.
    match_key: Mapped[str | None] = mapped_column(String(255), index=True)   # e.g. "hotel riu gran canaria"
    match_label: Mapped[str | None] = mapped_column(String(255))             # human-readable
    match_type: Mapped[str | None] = mapped_column(String(20))               # "hotel" | "tour"
    match_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Processing state
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parse_error: Mapped[str | None] = mapped_column(Text)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    stop_sales: Mapped[list["StopSale"]] = relationship("StopSale", back_populates="document",
                                                         cascade="all, delete-orphan")


class StopSale(Base):
    """
    A single stop-sale period extracted from a document.

    A document may contain many stop-sale blocks (e.g. one per room type,
    one per booking-date range).  Each is stored as a separate row so the
    daily list view can filter and sort efficiently.
    """

    __tablename__ = "stop_sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                     default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("stop_sale_documents.id"),
                                              nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id"), nullable=False, index=True)

    # What is stopped
    hotel_or_tour: Mapped[str] = mapped_column(String(255), nullable=False)  # display name
    room_type: Mapped[str | None] = mapped_column(String(255))               # "ALL" if not specified
    market: Mapped[str | None] = mapped_column(String(100))                  # e.g. "DE", "PL", "ALL"

    # Date ranges (travel dates that are stopped)
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    # Booking-window constraints (optional — some stop sales apply only within a booking window)
    booking_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    booking_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    # Raw extracted text snippet for human review
    raw_text: Mapped[str | None] = mapped_column(Text)

    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document: Mapped["StopSaleDocument"] = relationship("StopSaleDocument", back_populates="stop_sales")
