"""
app.db.session
===============
Single Motor client for the process. Import the collection handles in
app.db.collections rather than constructing a new client anywhere else —
one client per process is the documented Motor usage pattern and avoids
exhausting connections under load.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

client: AsyncIOMotorClient = AsyncIOMotorClient(settings.mongo_uri)
db: AsyncIOMotorDatabase = client[settings.database_name]


async def ping() -> None:
    await db.command("ping")
