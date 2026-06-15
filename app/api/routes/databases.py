"""
/databases - lightweight database selection helpers for the global frontend context.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.metadata import ConnectedDatabase

router = APIRouter(prefix="/databases", tags=["Databases"])


class DatabaseListItem(BaseModel):
    database_id: int
    database_name: str
    db_type: str
    status: str
    connected_at: Optional[datetime] = None


class DefaultDatabaseResponse(BaseModel):
    database_id: Optional[int] = None
    database_name: Optional[str] = None
    db_type: Optional[str] = None
    connected_at: Optional[datetime] = None


@router.get("")
async def list_databases(db: AsyncSession = Depends(get_db)) -> list[DatabaseListItem]:
    result = await db.execute(select(ConnectedDatabase).order_by(ConnectedDatabase.created_at.desc()))
    rows = result.scalars().all()
    return [
        DatabaseListItem(
            database_id=row.id,
            database_name=row.name,
            db_type=row.db_type.value if hasattr(row.db_type, "value") else str(row.db_type),
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            connected_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/default", response_model=DefaultDatabaseResponse)
async def get_default_database(
    selected_database_id: Optional[int] = Query(default=None, alias="database_id"),
    db: AsyncSession = Depends(get_db),
) -> DefaultDatabaseResponse:
    if selected_database_id is not None:
        row = await db.get(ConnectedDatabase, selected_database_id)
        if row:
            return DefaultDatabaseResponse(
                database_id=row.id,
                database_name=row.name,
                db_type=row.db_type.value if hasattr(row.db_type, "value") else str(row.db_type),
                connected_at=row.created_at,
            )

    result = await db.execute(select(ConnectedDatabase).order_by(ConnectedDatabase.created_at.desc()))
    row = result.scalars().first()
    if not row:
        return DefaultDatabaseResponse()
    return DefaultDatabaseResponse(
        database_id=row.id,
        database_name=row.name,
        db_type=row.db_type.value if hasattr(row.db_type, "value") else str(row.db_type),
        connected_at=row.created_at,
    )


@router.get("/connection-defaults")
async def connection_defaults() -> dict[str, int]:
    return {
        "mysql": 3306,
        "postgresql": 5432,
        "sqlserver": 1433,
        "oracle": 1521,
        "mongodb": 27017,
        "mariadb": 3306,
    }
