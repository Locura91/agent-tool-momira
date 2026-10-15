"""
CLI script to create the first admin account.

Usage (on the server):
    cd /opt/momira-agent-tool
    source /opt/agent-env12/bin/activate
    python create_admin.py

The script prompts for email and password, then writes the admin row
directly to the database. Run it once to bootstrap the admin account;
after that, all agent accounts are created through the admin UI.
"""

import asyncio
import getpass
import sys

from sqlalchemy import select

from auth import hash_password
from database import AsyncSessionLocal, init_db
from models import Agent


async def main() -> None:
    print("=== Momira Travel Agent Kit — Create Admin Account ===\n")

    email = input("Admin email: ").strip()
    if not email:
        print("Email cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    await init_db()

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Agent).where(Agent.email == email))
        agent = existing.scalar_one_or_none()

        if agent:
            if agent.role == "admin":
                print(f"\n⚠️  An admin account for {email} already exists.")
                sys.exit(0)
            # Upgrade existing agent account to admin
            agent.role = "admin"
            agent.password_hash = hash_password(password)
            db.add(agent)
            await db.commit()
            print(f"\n✅ Existing account {email} upgraded to admin.")
        else:
            agent = Agent(
                email=email,
                password_hash=hash_password(password),
                agency_name="Momira Travel (Admin)",
                role="admin",
            )
            db.add(agent)
            await db.commit()
            print(f"\n✅ Admin account created for {email}.")

    print("You can now log in at https://agent.momira.travel")


if __name__ == "__main__":
    asyncio.run(main())
