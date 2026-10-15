"""
One-time bootstrap script — creates the admin account and then deletes itself.
DELETE THIS FILE from the server after running it.
"""
import asyncio
from sqlalchemy import select
from auth import hash_password
from database import AsyncSessionLocal, init_db
from models import Agent

EMAIL = "info@momira.de"
PASSWORD = "Momi8.Ra"

async def main():
    await init_db()
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Agent).where(Agent.email == EMAIL))
        agent = existing.scalar_one_or_none()
        if agent:
            agent.role = "admin"
            agent.password_hash = hash_password(PASSWORD)
            db.add(agent)
            await db.commit()
            print(f"Updated existing account to admin: {EMAIL}")
        else:
            agent = Agent(
                email=EMAIL,
                password_hash=hash_password(PASSWORD),
                agency_name="Momira Travel (Admin)",
                role="admin",
            )
            db.add(agent)
            await db.commit()
            print(f"Admin account created: {EMAIL}")

    import os, sys
    os.remove(sys.argv[0])
    print("Script deleted. Done.")

asyncio.run(main())
