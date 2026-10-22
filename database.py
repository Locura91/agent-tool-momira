"""Async SQLAlchemy session factory."""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agents.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new columns to existing tables if they don't exist yet (SQLite migration)
        await _migrate(conn)


async def _migrate(conn) -> None:
    """Safe ALTER TABLE statements — each is a no-op if the column already exists."""
    migrations = [
        "ALTER TABLE agents ADD COLUMN google_review_url TEXT",
        "ALTER TABLE agents ADD COLUMN tripadvisor_url TEXT",
        "ALTER TABLE agents ADD COLUMN role TEXT NOT NULL DEFAULT 'agent'",
        "ALTER TABLE registrations ADD COLUMN street TEXT",
        "ALTER TABLE registrations ADD COLUMN postal_code TEXT",
        "ALTER TABLE registrations ADD COLUMN city TEXT",
        "ALTER TABLE registrations ADD COLUMN country_of_residence TEXT",
        "ALTER TABLE registrations ADD COLUMN passengers_json TEXT",
        # bookings table — added incrementally, ensure all columns exist
        "ALTER TABLE bookings ADD COLUMN tc_booking_ref TEXT",
        "ALTER TABLE bookings ADD COLUMN package_title TEXT",
        "ALTER TABLE bookings ADD COLUMN feedback_status TEXT NOT NULL DEFAULT 'pending'",
        "ALTER TABLE bookings ADD COLUMN feedback_sent_at DATETIME",
        "ALTER TABLE bookings ADD COLUMN feedback_platforms TEXT",
    ]
    for sql in migrations:
        try:
            await conn.execute(__import__("sqlalchemy").text(sql))
        except Exception:
            pass  # column already exists — ignore


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
