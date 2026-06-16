from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metadata import ConnectedDatabase, DatabaseLifecycleStatus


async def get_database_or_none(db: AsyncSession, database_id: int) -> Optional[ConnectedDatabase]:
    return await db.get(ConnectedDatabase, database_id)


async def validate_database_access(
    db: AsyncSession,
    database_id: int,
    *,
    allow_inactive: bool = False,
) -> ConnectedDatabase:
    database = await get_database_or_none(db, database_id)
    if database is None:
        raise ValueError(f"Database {database_id} not found")

    lifecycle_status = getattr(database, "lifecycle_status", DatabaseLifecycleStatus.active)
    lifecycle_value = getattr(lifecycle_status, "value", str(lifecycle_status))
    if not allow_inactive and lifecycle_value != DatabaseLifecycleStatus.active.value:
        raise ValueError(f"Database {database_id} is {lifecycle_value} and cannot be used")
    return database


async def ensure_connected(db: AsyncSession, database_id: int) -> ConnectedDatabase:
    return await validate_database_access(db, database_id, allow_inactive=False)
